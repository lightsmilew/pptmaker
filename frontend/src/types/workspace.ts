import type { ProjectStatus } from './index';

export interface PresentationSummary {
  id: string; title: string; audience: string; style: string; status: ProjectStatus;
  page_count: number; completed_pages: number; favorite: boolean; archived: boolean;
  tags: string[]; created_at: string; updated_at: string;
  preview_url: string | null; download_url: string | null; file_size: number | null;
}
export interface ProjectList { projects: PresentationSummary[]; total: number; page: number; page_size: number }
export interface WorkspaceOverview {
  name: string; mode: string;
  stats: { total: number; completed: number; favorites: number; in_progress: number; archived: number; pages: number; storage_bytes: number };
  recent: PresentationSummary[];
}
export interface Profile {
  account_id: string; display_name: string; email: string; company: string; occupation: string;
  bio: string; timezone: string; created_at: string; updated_at?: string;
  preferences: { style: string; page_count: number; language: string };
}
export interface Usage {
  period: string; period_start: string; resets_at: string; calls: number; lifetime_calls: number;
  input_tokens: number; output_tokens: number; cached_input_tokens: number; reasoning_tokens: number;
  successful_calls: number; response_cache_hits: number; duration_ms: number;
  provider_cache_hit_rate: number | null; daily: { date: string; output_tokens: number; calls: number }[];
  quota: { unit: string; limit: number | null; used: number; reserved: number; remaining: number | null; is_unlimited: boolean; source: string };
}
export interface Account {
  profile: Profile;
  membership: { tier: string; name: string; is_vip: boolean; status: string; expires_at: string | null; managed_by: string; billing_mode: string; features: string[]; limits: { max_pages: number; concurrency: number } };
  usage: Usage;
  account: { mode: string; status: string; email_verified: boolean; provider_host: string | null; model: string; provider_connected: boolean; authentication: string };
}
export type ProfilePatch = Partial<Omit<Profile, 'account_id' | 'created_at' | 'updated_at' | 'preferences'>> & { preferences?: Partial<Profile['preferences']> };
