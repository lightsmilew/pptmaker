// Bidirectional WebSocket hook.
//
// - On open: wires the project's command dispatcher into the Zustand store.
// - On message: routes every server event to the matching store handler.
// - Auto-reconnects with backoff on close.

import { useEffect, useRef, useCallback } from 'react';
import { createWebSocket } from '@/api/client';
import type {
  WebSocketMessage,
  PageUpdateEvent,
  ParallelGenerationStatus,
  ReviewCompletedEvent,
  PreviewReadyEvent,
  CompletedEvent,
  PPTProject,
  GenerationProgress,
  WSCommand,
} from '@/types';
import { useProjectStore } from '@/stores/projectStore';
import toast from 'react-hot-toast';

export function useWebSocket(projectId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number>();
  const disposedRef = useRef(false);
  const projectIdRef = useRef(projectId);

  const {
    setProject,
    setError,
    handleStatePatch,
    handlePageUpdated,
    handlePreviewReady,
    handleReviewCompleted,
    handleParallelStatus,
    handleProgress,
    handleCompleted,
    setSendCommand,
  } = useProjectStore();

  useEffect(() => {
    projectIdRef.current = projectId;
  }, [projectId]);

  const send = useCallback((cmd: WSCommand) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setError('WebSocket 尚未连接');
      return;
    }
    ws.send(JSON.stringify(cmd));
  }, [setError]);

  const handleMessage = useCallback((message: WebSocketMessage) => {
    const data = message.data as any;
    switch (message.type) {
      case 'initial_state':
      case 'state_patch': {
        if (data && typeof data === 'object') {
          handleStatePatch(data as PPTProject);
          setProject(data as PPTProject);
          if ((data as PPTProject).error) {
            setError((data as PPTProject).error!);
            toast.error((data as PPTProject).error!);
          }
        }
        break;
      }
      case 'progress': {
        const p = data as GenerationProgress;
        handleProgress(p.step, p.progress);
        break;
      }
      case 'page_updated': {
        const event = data as PageUpdateEvent;
        handlePageUpdated(event);
        if (event.status === 'completed') {
          toast.success(`页面 ${event.page_id} 生成完成`);
        }
        break;
      }
      case 'preview_ready': {
        handlePreviewReady(data as PreviewReadyEvent);
        break;
      }
      case 'review_completed': {
        const event = data as ReviewCompletedEvent;
        handleReviewCompleted(event);
        if (event.status === 'approved') {
          toast.success(`页面 ${event.page_id} 评审通过 (${event.score}分)`);
        } else if (event.status === 'needs_revision') {
          toast(`页面 ${event.page_id} 需要调整`, { icon: '🔧' });
        }
        break;
      }
      case 'parallel_status': {
        handleParallelStatus(data as ParallelGenerationStatus);
        break;
      }
      case 'completed': {
        handleCompleted(data as CompletedEvent);
        toast.success('PPT生成完成！');
        break;
      }
      case 'error': {
        const message = data?.message || '未知错误';
        setError(message);
        toast.error(message);
        break;
      }
      case 'pong':
        // Keep-alive ack
        break;
    }
  }, [
    handleStatePatch,
    handlePageUpdated,
    handlePreviewReady,
    handleReviewCompleted,
    handleParallelStatus,
    handleProgress,
    handleCompleted,
    setError,
    setProject,
  ]);

  const connect = useCallback(() => {
    const id = projectIdRef.current;
    if (!id) return;

    disposedRef.current = false;
    // Cancel any pending reconnect timer from a previous connection so it
    // doesn't interfere with this fresh connect() call.
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = undefined;
    }

    if (wsRef.current) {
      const ready = wsRef.current.readyState;
      if (ready === WebSocket.OPEN || ready === WebSocket.CONNECTING) {
        return;
      }
    }

    const ws = createWebSocket(id);
    wsRef.current = ws;

    ws.onopen = () => {
      // Must assign BEFORE setSendCommand so the captured `send` closure
      // holds a reference to the CURRENT open socket — not the stale one
      // that was replaced by this new connection.
      wsRef.current = ws;
      console.log('WebSocket connected');
      setSendCommand(send);
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        handleMessage(message);
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setError('WebSocket 连接错误');
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setSendCommand(null);
      if (disposedRef.current) return;
      reconnectTimeoutRef.current = window.setTimeout(() => {
        if (!disposedRef.current && projectIdRef.current) {
          connect();
        }
      }, 3000);
    };
  }, [handleMessage, send, setError, setSendCommand]);

  const disconnect = useCallback(() => {
    disposedRef.current = true;
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setSendCommand(null);
  }, [setSendCommand]);

  useEffect(() => {
    if (projectId) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [projectId, connect, disconnect]);

  return {
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
    disconnect,
    reconnect: connect,
  };
}
