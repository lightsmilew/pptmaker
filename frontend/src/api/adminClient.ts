import type { Account } from '@/types/workspace';
import type { Announcement, AnnouncementInput } from './announcements';

export interface AdminSession { account: Account; csrf_token: string }
export interface Plan { tier: string; name: string; description: string; monthly_output_limit: number; max_pages: number; concurrency: number }
export interface AdminUser { id: string; email: string; display_name: string; company: string; created_at: string; status: string; role: string; membership: Account['membership']; usage: Account['usage']; output_limit_override: number | null }
export interface ConfigField { key: string; label: string; kind: string; group: string; value: string; configured: boolean; stored_differs: boolean; minimum?: number; maximum?: number; step?: number; options?: string[] }
export interface AdminConfig { revision: string; fields: ConfigField[]; read_only: string[] }
export interface Activity { id: string; created_at: string; category?: string; email?: string; actor_email?: string; action?: string; target_id?: string; detail?: { fields?: string[]; status?: string; pages?: number }; scope?: string; success?: boolean | number; ip?: string; user_agent?: string; model?: string; role?: string; project_id?: string; input_tokens?: number; output_tokens?: number; cached_tokens?: number; duration_ms?: number }
export interface Overview { period: string; users: number; active_users: number; disabled_users: number; projects: number; completed: number; running: number; failed_logins: number; usage: { calls: number; input_tokens: number; output_tokens: number; failures: number }; provider: string; model: string; provider_connected: boolean; recent: Activity[] }
export interface UsageReport { period: string; summary: { calls: number; input_tokens: number; output_tokens: number; cached_tokens: number; reasoning_tokens: number; cache_hits: number; failures: number; reported_calls: number }; provider_cache_hit_rate: number | null; models: { provider: string; model: string; calls: number; input_tokens: number; output_tokens: number }[]; daily: { date: string; calls: number; output_tokens: number }[] }
export interface Balance { supported: boolean; available: boolean | null; balances: { currency: string; total_balance: string; granted_balance: string; topped_up_balance: string }[]; message: string; checked_at?: string }
export interface Generation { id: string; email: string; title: string; status: string; pages: number; created_at: string; updated_at: string }
export interface Paged<T> { items: T[]; total: number; page: number; page_size: number }
let csrf = ''; let version = 0;
export function setAdminCsrf(value: string) { if (value !== csrf) version++; csrf = value; }
export function getAdminRequestState() { return { csrf,version }; }
async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const ticket = version;
  const response = await fetch('/api/v1/admin'+path, { method, credentials:'same-origin', headers:{ 'Content-Type':'application/json', 'X-Folio-Request':'1', ...(csrf ? { 'X-CSRF-Token':csrf } : {}) }, ...(body === undefined ? {} : { body:JSON.stringify(body) }) });
  if (ticket !== version) throw new Error('管理会话已更新，请重试');
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 401 && !['/login','/session'].includes(path)) window.dispatchEvent(new Event('folio-admin-expired'));
    throw new Error(typeof data.detail === 'string' ? data.detail : '请检查输入内容后重试');
  }
  return response.status === 204 ? undefined as T : response.json();
}
const query = (args: Record<string,string | number>) => '?'+new URLSearchParams(Object.entries(args).map(([k,v]) => [k,String(v)]));
export const adminApi = {
  announcements: (status = 'all', page = 1) => request<Paged<Announcement>>('/announcements'+query({ status,page })),
  createAnnouncement: (data: AnnouncementInput) => request<Announcement>('/announcements','POST',data),
  updateAnnouncement: (id: string, data: AnnouncementInput) => request<Announcement>('/announcements/'+encodeURIComponent(id),'PATCH',data),
  publishAnnouncement: (id: string) => request<Announcement>('/announcements/'+encodeURIComponent(id)+'/publish','POST'),
  withdrawAnnouncement: (id: string) => request<Announcement>('/announcements/'+encodeURIComponent(id)+'/withdraw','POST'),
  session: () => request<AdminSession>('/session'),
  login: (email: string, password: string) => request<AdminSession>('/login','POST',{ email,password }),
  logout: () => request<void>('/logout','POST'),
  password: (current_password: string, new_password: string) => request<AdminSession>('/password','POST',{ current_password,new_password }),
  overview: () => request<Overview>('/overview'),
  users: (q = '', page = 1, status = 'all') => request<Paged<AdminUser>>('/users'+query({ q,page,status })),
  updateUser: (id: string, data: unknown) => request<AdminUser>(`/users/${encodeURIComponent(id)}`,'PATCH',data),
  revoke: (id: string) => request<void>(`/users/${encodeURIComponent(id)}/revoke-sessions`,'POST'),
  resetPassword: (id: string) => request<{ temporary_password: string }>(`/users/${encodeURIComponent(id)}/reset-password`,'POST'),
  plans: () => request<{ items:Plan[] }>('/memberships'),
  updatePlan: (plan: Plan) => { const { tier,...data } = plan; return request<Plan>('/memberships/'+tier,'PATCH',data); },
  config: () => request<AdminConfig>('/config'),
  updateConfig: (revision: string, changes: Record<string,string>) => request<AdminConfig>('/config','PATCH',{ revision,changes }),
  models: () => request<{ models:string[] }>('/provider/models','POST'),
  balance: () => request<Balance>('/provider/balance','POST'),
  usage: (period: string) => request<UsageReport>('/usage'+query({ period })),
  records: (kind: string, q: string, page: number) => request<Paged<Activity>>('/records'+query({ kind,q,page })),
  generations: (q: string, page: number) => request<Paged<Generation>>('/generations'+query({ q,page })),
  generation: (id: string) => request<GenerationDetail>('/generations/'+encodeURIComponent(id)),
};

export interface GenerationDetail extends Omit<Generation,'pages'> {
  style: string; download_url: string | null;
  style_selection?: { mode:string; style:string; reason:string };
  pages: { page_id:string; title:string; status:string; preview_url:string | null; content:{ bullet_points?:string[]; speaker_notes?:string } }[];
}
