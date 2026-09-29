// Frontend API client.
//
// All project workflow actions (parse, plan, generate, review, render) are
// now sent over a bidirectional WebSocket — the REST surface here only
// covers the few endpoints that must remain request/response:
//   - POST /api/v1/projects            (one-shot project creation)
//   - POST /api/v1/upload/parse        (one-shot file text extraction)
//   - GET  /storage/{filename}         (static download URL builder)

import type {
  PPTProject,
  CreateProjectRequest,
} from '@/types';

const API_BASE = '/api/v1';

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export interface UploadParseResult {
  filename: string;
  content: string;
  content_preview: string;
}

// ==================== REST API surface ====================

export const api = {
  // The only project REST endpoint — initial creation. Everything else
  // (parse, plan, generate, render, page updates) lives on the WebSocket.
  createProject: (data: CreateProjectRequest) =>
    request<PPTProject>('/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // One-shot file parsing utility.
  uploadAndParse: async (file: File): Promise<UploadParseResult> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE}/upload/parse`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return response.json();
  },
};

// ==================== URL helpers ====================

export function getDownloadUrl(filename: string): string {
  return `/storage/${filename}`;
}

// ==================== WebSocket helpers ====================

export function createWebSocket(projectId: string): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return new WebSocket(`${protocol}//${host}/ws/${projectId}`);
}
