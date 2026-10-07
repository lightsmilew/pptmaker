// API Types for Folio
//
// The architecture is now event-driven through a single bidirectional
// WebSocket. REST handles creation, history, account and upload.
// See WebSocketMessage below for the unified workflow protocol.

// ==================== Domain enums ====================

export type ProjectStatus =
  | 'idle'
  | 'parsing'
  | 'parsed'
  | 'editing'
  | 'planned'
  | 'planning'
  | 'generating'
  | 'reviewing'
  | 'rendering'
  | 'completed'
  | 'failed';

export type PageType =
  | 'cover'
  | 'toc'
  | 'content'
  | 'chart'
  | 'table'
  | 'conclusion'
  | 'reference'
  | 'thankyou';

export type PageStatus =
  | 'pending'
  | 'writing'
  | 'designing'
  | 'rendering'
  | 'reviewing'
  | 'revising'
  | 'completed'
  | 'failed';

export type ReviewStatus =
  | 'approved'
  | 'needs_revision'
  | 'blocked'
  | 'failed';

// ==================== Page data shapes ====================

export interface LayoutElement {
  type: string;
  position: [number, number];
  size: [number, number];
  style: Record<string, unknown>;
}

export interface PreviewInfo {
  image_path: string;
  width: number;
  height: number;
  rendered_at: string;
}

export interface ReviewIssue {
  issue_id: string;
  category: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  target: string;
  description: string;
  suggested_action?: string;
  owner: 'layout' | 'content';
}

export interface ReviewDimensions {
  alignment: number;
  balance: number;
  readability: number;
  hierarchy: number;
  density: number;
  consistency: number;
}

export interface ReviewResult {
  method?: 'local_geometry' | 'vision';
  status: ReviewStatus;
  score: number;
  dimensions?: ReviewDimensions;
  issues: ReviewIssue[];
  suggestions: string[];
  next_action?: 'revise_layout' | 'revise_content' | 'approve' | 'blocked' | 'failed';
}

export interface PageContent {
  title: string;
  subtitle: string;
  key_points: string[];
  bullet_points: string[];
  chart_data?: Record<string, unknown>;
  table_data?: Record<string, unknown>;
  speaker_notes: string;
}

export interface LayoutSpec {
  layout_id: string;
  layout_type: string;
  placeholders: Array<{
    name: string;
    type: string;
    x: number;
    y: number;
    w: number;
    h: number;
  }>;
}

export interface MasterLayout {
  background: { type: string; rgb: number[] };
  logo: { enable: boolean };
  color_scheme: {
    primary: number[];
    secondary: number[];
    accent: number[];
    text: number[];
    light_text: number[];
  };
  font_scheme: {
    title_font: string;
    body_font: string;
    title_size: number;
    body_size: number;
  };
}

export interface PageData {
  page_id: string;
  page_type: PageType;
  content: PageContent;
  layout: {
    layout_type: string;
    layout_json?: LayoutSpec;
    master_json?: MasterLayout;
  };
  preview?: PreviewInfo;
  review?: {
    method?: 'local_geometry' | 'vision';
    status: ReviewStatus;
    score: number;
    issues: ReviewIssue[];
    suggestions: string[];
  };
  iteration: number;
  max_iterations: number;
  status: PageStatus;
  error?: string;
}

// ==================== Project shapes ====================

export interface PPTProjectSpec {
  topic: string;
  audience?: string;
  page_count?: number;
  style?: string;
  needs_cover?: boolean;
  needs_toc?: boolean;
  needs_summary?: boolean;
  needs_chart?: boolean;
  notes?: string;
}

export interface ProjectState {
  project_id: string;
  spec: PPTProjectSpec;
  theme?: Record<string, unknown>;
  page_count: number;
  status: ProjectStatus;
  created_at?: string;
  updated_at?: string;
}

export interface WorkflowState {
  workflow_id: string;
  status: 'idle' | 'running' | 'paused' | 'completed' | 'failed';
  current_node?: string;
  current_page_id?: string;
  total_pages: number;
  completed_pages: string[];
  failed_pages: string[];
}

export interface GlobalReviewResult {
  status: 'approved' | 'global_revision_required';
  score: number;
  page_scores: Record<string, number>;
  consistency_issues: ReviewIssue[];
  recommendations: string[];
  affected_pages: string[];
}

export interface PPTProject {
  id: string;
  spec: PPTProjectSpec;
  user_input?: string;
  status: ProjectStatus;
  current_step?: string;
  progress?: number;
  error?: string;
  pages: PageData[];
  outline?: OutlineItem[];
  global_review?: GlobalReviewResult;
  workflow?: WorkflowState;
  created_at?: string;
  updated_at?: string;
  page_count?: number;
  download_url?: string | null;
  metadata?: { favorite?: boolean; archived?: boolean; tags?: string[] };
}

export interface OutlineItem {
  page_id: string;
  page_type: PageType;
  page_title: string;
  subtitle?: string;
  page_purpose?: string;
  key_points: string[];
  suggest_layout?: string;
}

export interface CreateProjectRequest {
  spec?: PPTProjectSpec;
  user_input?: string;
  uploaded_files?: string[];
}

// ==================== WebSocket protocol ====================

/** All server -> client event types emitted on /ws/{project_id}. */
export type WSServerEventType =
  | 'initial_state'
  | 'state_patch'
  | 'progress'
  | 'parallel_status'
  | 'page_updated'
  | 'preview_ready'
  | 'review_completed'
  | 'completed'
  | 'error'
  | 'pong';

/** All client -> server commands sent on /ws/{project_id}. */
export type WSClientCommandType =
  | 'ping'
  | 'parse_input'
  | 'plan_outline'
  | 'generate_parallel'
  | 'render_pptx'
  | 'update_spec'
  | 'update_page'
  | 'trigger_review'
  | 'delete_project';

export interface WebSocketMessage<T = unknown> {
  type: WSServerEventType;
  data?: T;
}

export interface WSCommand<T = unknown> {
  type: WSClientCommandType;
  data?: T;
}

/* Concrete payloads ============================================== */

export interface GenerationProgress {
  step: string;
  progress: number;
  message?: string;
  current_page?: string;
}

export interface PageUpdateEvent {
  page_id: string;
  status: PageStatus;
  iteration?: number;
  preview?: PreviewInfo;
  review?: ReviewResult;
}

export interface ParallelGenerationStatus {
  total_pages: number;
  completed_pages: number;
  failed_pages: number;
  pages_status: Record<string, PageStatus>;
}

export interface ReviewCompletedEvent {
  method?: 'local_geometry' | 'vision';
  page_id: string;
  status: ReviewStatus;
  score: number;
  issues: ReviewIssue[];
  suggestions: string[];
}

export interface PreviewReadyEvent {
  page_id: string;
  image_path: string;
  iteration?: number;
}

export interface CompletedEvent {
  download_url: string;
}

/* Command payloads ============================================== */

export interface UpdateSpecCommand {
  patch: Partial<PPTProjectSpec>;
}

export interface UpdatePageCommand {
  page_id: string;
  patch: Partial<PageData>;
}

export interface TriggerReviewCommand {
  page_id: string;
}
