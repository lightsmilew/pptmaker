export interface Announcement {
  id: string; title: string; body: string; revision: number;
  status?: 'draft' | 'published' | 'withdrawn';
  duration_days?: number | null; published_at: string | null;
  expires_at: string | null; updated_at?: string;
}
export interface AnnouncementInput { title: string; body: string; duration_days: number | null }
