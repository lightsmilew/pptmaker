// Frontend API client.
//
// All project workflow actions (parse, plan, generate, review, render) are
// now sent over a bidirectional WebSocket — the REST surface here only
// covers the few endpoints that must remain request/response:
//   - /api/v1/projects                 (creation, history, metadata)
//   - /api/v1/account                  (owned server profile, entitlements, usage)
//   - POST /api/v1/upload/parse        (one-shot file text extraction)
//   - GET  /storage/{filename}         (static download URL builder)

import { prepareImageUpload } from '@/lib/imageUpload';
import type {
  PPTProject,
  CreateProjectRequest,
} from '@/types';
import type { Account, ProfilePatch, ProjectList, PresentationSummary, WorkspaceOverview } from '@/types/workspace';
import type { DesignCatalog } from '@/types/design';
import type { Announcement } from './announcements';

const API_BASE = '/api/v1';
let csrfToken = '';
let sessionVersion = 0;
export function setSessionCsrf(token: string) { if (token !== csrfToken) sessionVersion++; csrfToken = token; }
export function getSessionRequestState() { return { csrf:csrfToken, version:sessionVersion }; }
export interface AuthSession { account: Account; csrf_token: string }
export function sessionExpired() { setSessionCsrf(''); window.dispatchEvent(new Event('folio-session-expired')); }

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const version = sessionVersion;

  const response = await fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Folio-Request': '1',
      ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
      ...options.headers,
    },
  });
  if (!endpoint.startsWith('/auth/') && version !== sessionVersion) throw new Error('账号已切换，请重新打开页面');

  if (!response.ok) {
    if (response.status === 401 && !endpoint.startsWith('/auth/')) sessionExpired();
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    const detail = error.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((item: { msg: string }) => item.msg).join('；') : `HTTP ${response.status}`);
  }

  return response.status === 204 ? undefined as T : response.json();
}

export interface UploadParseResult {
  upload_id: string;
  filename: string;
  content: string;
  content_preview: string;
  notice?: string;
  size?: number;
}

// ==================== REST API surface ====================

export const api = {
  getAnnouncements: () => request<{ items: Announcement[]; day: string; timezone: string }>('/announcements'),
  dismissAnnouncement: (id: string, revision: number) => request<{ ok: boolean; day: string }>('/announcements/'+encodeURIComponent(id)+'/dismiss', { method:'POST', body:JSON.stringify({ revision }) }),
  getDesignCatalog: () => request<DesignCatalog>('/design/catalog'),
  getSession: () => request<AuthSession>('/auth/session'),
  login: (email: string, password: string) => request<AuthSession>('/auth/login', { method:'POST',body:JSON.stringify({ email,password }) }),
  register: (email: string, password: string, display_name: string) => request<AuthSession>('/auth/register', { method:'POST',body:JSON.stringify({ email,password,display_name }) }),
  logout: () => request<void>('/auth/logout', { method:'POST' }),
  changePassword: (current_password: string, new_password: string) => request<AuthSession>('/auth/password', { method:'POST',body:JSON.stringify({ current_password,new_password }) }),
  getProject: (id: string) => request<PPTProject>(`/projects/${encodeURIComponent(id)}`),
  listProjects: (params: Record<string, string | number | boolean> = {}) => request<ProjectList>(`/projects?${new URLSearchParams(Object.entries(params).map(([k,v]) => [k, String(v)]))}`),
  updateMetadata: (id: string, patch: { title?: string; favorite?: boolean; archived?: boolean; tags?: string[] }) => request<PresentationSummary>(`/projects/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  getWorkspace: () => request<WorkspaceOverview>('/workspace'),
  getAccount: () => request<Account>('/account'),
  updateProfile: (patch: ProfilePatch) => request<Account>('/account/profile', { method: 'PATCH', body: JSON.stringify(patch) }),
  // Initial creation. Workflow operations
  // (parse, plan, generate, render, page updates) use the WebSocket.
  createProject: (data: CreateProjectRequest) =>
    request<PPTProject>('/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // One-shot file parsing utility.
  uploadAndParse: async (file: File): Promise<UploadParseResult> => {
    const version = sessionVersion;
    const formData = new FormData();
    const prepared = await prepareImageUpload(file, 'reference');
    if (version !== sessionVersion) throw new Error('账号已切换，请重新添加文档');
    formData.append('file', prepared);
    const response = await fetch(`${API_BASE}/upload/parse`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-Folio-Request':'1', 'X-CSRF-Token':csrfToken },
      body: formData,
    });
    if (version !== sessionVersion) throw new Error('账号已切换，请重新添加文档');
    if (!response.ok) {
      if (response.status === 401) sessionExpired();
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
