// Requirement input panel - Soft UI Style

import { useState, useRef, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { ArrowRight, FileUp, X, FileText } from 'lucide-react';
import { Button, Textarea, Card, NumberInput } from '@/components/ui';
import { DesignControls } from './DesignControls';
import type { PPTProjectSpec } from '@/types';
import { api } from '@/api/client';
import { useProjectStore } from '@/stores/projectStore';

interface InputPanelProps {
  onSubmit: (input: string, spec: PPTProjectSpec) => void;
  isLoading?: boolean;
  mode: 'content' | 'settings';
  maxPages?: number;
}

interface UploadedFile {
  upload_id: string;
  filename: string;
  size: number;
}

export function InputPanel({ onSubmit, isLoading, mode, maxPages = 50 }: InputPanelProps) {
  const draftSpec = useProjectStore((s) => s.draftSpec);
  const setDraftSpec = useProjectStore((s) => s.setDraftSpec);
  const input = useProjectStore((s) => s.draftInput);
  const setInput = useProjectStore((s) => s.setDraftInput);
  const uploadedFiles = useProjectStore((s) => s.draftFiles);
  const setUploadedFiles = useProjectStore((s) => s.setDraftFiles);
  const effectiveSpec = draftSpec;
  const updateSpec = setDraftSpec;
  const [isUploading, setIsUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadQueue = useRef(Promise.resolve());
  const mounted = useRef(true); const queuedBatches = useRef(0); const dragDepth = useRef(0);
  useEffect(() => { mounted.current=true; return () => { mounted.current=false; }; }, []);

  const handleFileUpload = useCallback((files: FileList | File[] | null) => {
    if (!files || files.length === 0) return;
    const batch = Array.from(files);
    queuedBatches.current++;
    setIsUploading(true);
    uploadQueue.current = uploadQueue.current.then(async () => {
    const newFiles: UploadedFile[] = [];
    for (const file of batch) {
      if (!mounted.current) break;
      if (!/\.(pdf|docx|md|markdown|txt)$/i.test(file.name)) { toast.error(`${file.name}：支持 PDF、DOCX、Markdown 和 TXT`); continue; }
      if (file.size > 10 * 1024 * 1024) { toast.error(`${file.name}：单文件不能超过 10 MiB`); continue; }
      if ([...useProjectStore.getState().draftFiles,...newFiles].some(f => f.filename===file.name && f.size===file.size)) { toast('已添加此文档'); continue; }
      try {
        const result = await api.uploadAndParse(file);
        if (!mounted.current) break;
        newFiles.push({
          upload_id: result.upload_id,
          filename: result.filename,
          size: result.size ?? file.size,
        });
      } catch (err) {
        if (mounted.current) toast.error(`${file.name}：${(err as Error).message}`);
      }
    }

    if (mounted.current) setUploadedFiles(prev => [...prev, ...newFiles]);
    }).finally(() => { queuedBatches.current--; if (mounted.current && queuedBatches.current===0) setIsUploading(false); });
  }, [setUploadedFiles]);

  useEffect(() => {
    if (mode !== 'content') return;
    const isFile = (e: DragEvent) => Array.from(e.dataTransfer?.types || []).includes('Files');
    const reset = () => { dragDepth.current=0; setDragActive(false); };
    const enter = (e: DragEvent) => { if (!isFile(e)) return; e.preventDefault(); dragDepth.current++; if (!isLoading) setDragActive(true); };
    const over = (e: DragEvent) => { if (!isFile(e)) return; e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect=isLoading ? 'none' : 'copy'; };
    const leave = (e: DragEvent) => { if (!isFile(e)) return; dragDepth.current=Math.max(0,dragDepth.current-1); if (!dragDepth.current) setDragActive(false); };
    const drop = (e: DragEvent) => { if (!isFile(e) && !e.dataTransfer?.files.length) return; e.preventDefault(); reset(); if (isLoading) { toast('正在制作，请完成后再添加文档'); return; } handleFileUpload(e.dataTransfer?.files || null); };
    document.addEventListener('dragenter',enter); document.addEventListener('dragover',over); document.addEventListener('dragleave',leave); document.addEventListener('drop',drop); window.addEventListener('dragend',reset); window.addEventListener('blur',reset);
    return () => { document.removeEventListener('dragenter',enter); document.removeEventListener('dragover',over); document.removeEventListener('dragleave',leave); document.removeEventListener('drop',drop); window.removeEventListener('dragend',reset); window.removeEventListener('blur',reset); };
  }, [mode,isLoading,handleFileUpload]);

  const removeFile = (index: number) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = () => {
    if (isLoading || isUploading) return;
    if (!input.trim() && uploadedFiles.length === 0) return;
    onSubmit(input, effectiveSpec);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      handleSubmit();
    }
  };

  return (
    <div className={mode === 'content' ? 'brief-panel' : 'settings-panel'}>
      {dragActive && mode==='content' && <div className="workbench-drop-overlay" role="status"><FileUp size={36} strokeWidth={1.4} /><strong>松开，把文档放进来。</strong><span>PDF / DOCX / Markdown / TXT · 单文件最大 10 MiB</span></div>}
      {/* Main Input Card */}
      {mode === 'content' && <Card className="brief-card">
        <div className="space-y-6">
          {/* Main input */}
          <div className="relative">
            <Textarea
              id="brief"
              aria-label="演示内容或制作要求"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="这次你想分享什么？

写下主题、关键观点和听众，或者直接粘贴已有大纲。"
              className="min-h-[180px] text-[15px] pb-12"
            />
            <div className="absolute bottom-4 right-4 flex items-center gap-2">
              <span className="text-xs text-gray-400 bg-gray-100 px-2.5 py-1 rounded-full">Ctrl + Enter</span>
            </div>
          </div>

          {/* File upload area */}
          <div
            className={`brief-upload ${dragActive ? 'drag-active' : ''}`}
            role="button" tabIndex={0} aria-label="上传参考文档"
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInputRef.current?.click(); } }}
            aria-disabled={isLoading}
            onClick={() => { if (!isLoading) fileInputRef.current?.click(); }}
          >
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".pdf,.docx,.md,.txt,.markdown"
              multiple
              disabled={isLoading}
              onChange={(e) => { handleFileUpload(e.target.files); e.target.value=''; }}
            />
            <FileUp size={19} />
            <span><strong>{isUploading ? '正在上传和解析…' : '添加参考文档'}</strong><small>点击选择，或将文档拖入页面 · 最大 10 MiB</small></span>
            <span className="upload-plus">+</span>
          </div>

          {/* Uploaded files list */}
          {uploadedFiles.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-600">已上传文件:</p>
              {uploadedFiles.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-xl border border-gray-100"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-[#29483e]" />
                    <div>
                      <p className="text-sm font-medium text-gray-700">{file.filename}</p>
                      <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(1)} KB</p>
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(index);
                    }}
                    aria-label={`移除 ${file.filename}`} className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors"
                  >
                    <X className="w-4 h-4 text-gray-400" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="brief-actions">
            <div className="brief-options"><span className="brief-count-label">页数</span><NumberInput compact aria-label="演示页数" min={1} max={maxPages} value={effectiveSpec.page_count || 8} onValueChange={page_count => updateSpec({page_count})} /><span className="brief-style-name">{effectiveSpec.style}</span></div>
            <Button onClick={handleSubmit} disabled={(!input.trim() && !uploadedFiles.length) || isLoading || isUploading} isLoading={isLoading}>创建演示 <ArrowRight size={16} /></Button>
          </div>
        </div>
      </Card>}

      {mode === 'settings' && <DesignControls />}
    </div>
  );
}
