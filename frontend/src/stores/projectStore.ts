// Zustand store for project state management.
//
// All project mutations flow through the WebSocket gateway. The store holds
// the canonical project snapshot and an outgoing-command dispatcher that
// the useWebSocket hook wires to the actual socket.

import { create } from 'zustand';
import type {
  PPTProject,
  PPTProjectSpec,
  PageData,
  PageUpdateEvent,
  ParallelGenerationStatus,
  ReviewResult,
  WSCommand,
  UpdateSpecCommand,
  UpdatePageCommand,
  TriggerReviewCommand,
  ReviewCompletedEvent,
  PreviewReadyEvent,
  CompletedEvent,
} from '@/types';
import { api } from '@/api/client';

function deepMerge<T extends Record<string, any>>(target: T, source: Partial<T>): T {
  const output = { ...target };
  for (const key of Object.keys(source) as (keyof T)[]) {
    const sourceValue = source[key];
    if (
      sourceValue !== null &&
      typeof sourceValue === 'object' &&
      !Array.isArray(sourceValue) &&
      typeof target[key] === 'object' &&
      target[key] !== null
    ) {
      (output as any)[key] = deepMerge(target[key] as any, sourceValue as any);
    } else {
      (output as any)[key] = sourceValue;
    }
  }
  return output;
}

export type CommandDispatcher = (cmd: WSCommand) => void;

export interface DraftFile { upload_id?: string; filename: string; size: number; source_name?:string; source_size?:number }

interface ProjectState {
  draftInput: string;
  setDraftInput: (value: string | ((previous: string) => string)) => void;
  draftFiles: DraftFile[];
  setDraftFiles: (value: DraftFile[] | ((previous: DraftFile[]) => DraftFile[])) => void;
  draftSpec: PPTProjectSpec;
  setDraftSpec: (patch: Partial<PPTProjectSpec>) => void;
  project: PPTProject | null;
  isLoading: boolean;
  error: string | null;
  parallelStatus: ParallelGenerationStatus | null;
  lastDownloadUrl: string | null;
  workflowPending: boolean;

  /** Wired by useWebSocket once the socket is open. */
  sendCommand: CommandDispatcher | null;

  /** Commands queued before the WebSocket is connected. */
  pendingCommands: WSCommand[];

  // REST helper (only project creation remains on REST)
  createProject: (spec?: PPTProjectSpec, userInput?: string) => Promise<string>;

  // WebSocket-driven actions
  runWorkflow: () => void;
  parseInput: () => void;
  planOutline: () => void;
  generateParallel: () => void;
  renderPPTX: () => void;
  updateSpec: (patch: Partial<PPTProjectSpec>) => void;
  updatePage: (pageId: string, patch: Partial<PageData>) => void;
  triggerReview: (pageId: string) => void;
  deleteProject: () => void;

  // Setters (called from useWebSocket message handlers)
  setProject: (project: PPTProject) => void;
  setError: (error: string | null) => void;
  setLoading: (loading: boolean) => void;
  setSendCommand: (dispatcher: CommandDispatcher | null) => void;

  // Event handlers (called from useWebSocket)
  handleStatePatch: (project: PPTProject) => void;
  handlePageUpdated: (event: PageUpdateEvent) => void;
  handlePreviewReady: (event: PreviewReadyEvent) => void;
  handleReviewCompleted: (event: ReviewCompletedEvent) => void;
  handleParallelStatus: (status: ParallelGenerationStatus) => void;
  handleProgress: (step: string, progress: number) => void;
  handleCompleted: (event: CompletedEvent) => void;

  // Cleanup
  clearProject: () => void;
}

function _send(store: ProjectState, cmd: WSCommand) {
  if (!store.sendCommand) {
    // WebSocket not yet wired — buffer the command and flush on connect.
    store.setError(null);
    useProjectStore.setState({
      pendingCommands: [...store.pendingCommands, cmd],
    });
    return;
  }
  store.sendCommand(cmd);
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  draftInput: '',
  setDraftInput: (value) => set(state => ({ draftInput: typeof value === 'function' ? value(state.draftInput) : value })),
  draftFiles: [],
  setDraftFiles: (value) => set(state => ({ draftFiles: typeof value === 'function' ? value(state.draftFiles) : value })),
  draftSpec: { topic: '', page_count: 8, style: '自动', audience: '通用', needs_cover: true, needs_toc: true, needs_summary: true, needs_chart: false, auto_images: true },
  setDraftSpec: (patch) => set((state) => ({ draftSpec: { ...state.draftSpec, ...patch } })),
  project: null,
  isLoading: false,
  error: null,
  parallelStatus: null,
  lastDownloadUrl: null,
  workflowPending: false,
  sendCommand: null,
  pendingCommands: [],

  // ---------- REST (only creation remains) ----------

  createProject: async (spec?: PPTProjectSpec, userInput?: string) => {
    set({ isLoading: true, error: null });
    try {
      const project = await api.createProject({
        spec,
        user_input: userInput,
        uploaded_files: get().draftFiles.filter(file => file.upload_id).map(file => ({ upload_id:file.upload_id })),
      });
      set({ project, isLoading: false, parallelStatus: null, lastDownloadUrl: null, pendingCommands: [], sendCommand: null, workflowPending:false });
      return project.id;
    } catch (err) {
      set({ error: (err as Error).message, isLoading: false });
      throw err;
    }
  },

  // ---------- WebSocket commands ----------

  runWorkflow: () => { set({workflowPending:true,error:null}); _send(get(), { type:'run_workflow' }); },

  parseInput: () => _send(get(), { type: 'parse_input' }),

  planOutline: () => _send(get(), { type: 'plan_outline' }),

  generateParallel: () => {
    const { project } = get();
    if (!project) return;
    set({workflowPending:true,error:null});
    _send(get(), { type: 'generate_parallel' });
  },

  renderPPTX: () => { set({workflowPending:true,error:null}); _send(get(), { type: 'render_pptx' }); },

  updateSpec: (patch) => {
    const cmd: WSCommand<UpdateSpecCommand> = {
      type: 'update_spec',
      data: { patch },
    };
    _send(get(), cmd);
  },

  updatePage: (pageId, patch) => {
    const cmd: WSCommand<UpdatePageCommand> = {
      type: 'update_page',
      data: { page_id: pageId, patch },
    };
    _send(get(), cmd);
  },

  triggerReview: (pageId) => {
    const cmd: WSCommand<TriggerReviewCommand> = {
      type: 'trigger_review',
      data: { page_id: pageId },
    };
    _send(get(), cmd);
  },

  deleteProject: () => _send(get(), { type: 'delete_project' }),

  // ---------- Setters ----------

  setProject: (project) => set(state => ({ project, lastDownloadUrl: Object.prototype.hasOwnProperty.call(project,'download_url') ? project.download_url ?? null : (state.project?.id === project.id ? state.lastDownloadUrl : null), ...(!state.pendingCommands.length && ['completed','failed'].includes(project.status) ? {workflowPending:false} : {}), ...(state.project?.id !== project.id ? { parallelStatus: null, pendingCommands: [], sendCommand: null, error: null, workflowPending:false } : {}) })),

  setError: (error) => set({ error, ...(error ? {workflowPending:false} : {}) }),

  setLoading: (loading) => set({ isLoading: loading }),

  setSendCommand: (dispatcher) => {
    if (!dispatcher) {
      set({ sendCommand: null });
      return;
    }
    // Flush any commands that were queued before the socket opened.
    const queued = get().pendingCommands;
    set({ sendCommand: dispatcher, pendingCommands: [] });
    for (const cmd of queued) {
      dispatcher(cmd);
    }
  },

  // ---------- Event handlers ----------

  handleStatePatch: (project) => {
    const existing = get().project;
    set({ project: existing ? deepMerge(existing, project) : project,
      ...(Object.prototype.hasOwnProperty.call(project,'download_url') ? {lastDownloadUrl:project.download_url ?? null} : {}),
      ...(project.status ? {workflowPending:false} : {}),
      ...(Object.prototype.hasOwnProperty.call(project,'error') ? {error:project.error || null} : {}) });
  },

  handlePageUpdated: (event) => {
    const { project } = get();
    if (!project) return;

    const updatedPages = (project.pages || []).map((page) => {
      if (page.page_id === event.page_id) {
        return {
          ...page,
          status: event.status,
          iteration: event.iteration ?? page.iteration,
          preview: event.preview ?? page.preview,
          review: event.review ?? page.review,
        };
      }
      return page;
    });

    set({
      project: { ...project, pages: updatedPages },
    });
  },

  handlePreviewReady: (event) => {
    const { project } = get();
    if (!project) return;
    const updatedPages = (project.pages || []).map((page) =>
      page.page_id === event.page_id
        ? {
            ...page,
            preview: event.preview,
            iteration: event.iteration ?? page.iteration,
          }
        : page
    );
    set({ project: { ...project, pages: updatedPages } });
  },

  handleReviewCompleted: (event) => {
    const { project } = get();
    if (!project) return;
    const review: ReviewResult = {
      method: event.method,
      status: event.status,
      score: event.score,
      issues: event.issues,
      suggestions: event.suggestions,
      warning: event.warning,
    };
    const updatedPages = (project.pages || []).map((page) =>
      page.page_id === event.page_id ? { ...page, review } : page
    );
    set({ project: { ...project, pages: updatedPages } });
  },

  handleParallelStatus: (status) => {
    set({ parallelStatus: status });
  },

  handleProgress: (step, progress) => {
    const project = get().project;
    if (project) set({project:{...project,current_step:step,progress}});
  },

  handleCompleted: (event) => {
    const { project } = get();
    if (!project) return;
    set({
      lastDownloadUrl: event.download_url,
      workflowPending: false,
    });
  },

  clearProject: () => {
    set({
      project: null,
      isLoading: false,
      sendCommand: null,
      error: null,
      parallelStatus: null,
      lastDownloadUrl: null,
      pendingCommands: [],
      workflowPending: false,
    });
  },
}));

// ----------------- Example projects (unchanged) -----------------

interface ExampleProject {
  title: string;
  description: string;
  spec: PPTProjectSpec;
}

export const useExamples = () => {
  const examples: ExampleProject[] = [
    {
      title: '技术汇报',
      description: '编译原理核心概念，面向计算机专业学生',
      spec: {
        topic: '编译原理技术汇报',
        audience: '本科学生',
        page_count: 8,
        style: '学术简约',
        needs_cover: true,
        needs_toc: true,
        needs_summary: true,
        needs_chart: true,
      },
    },
    {
      title: '产品介绍',
      description: '新产品发布演示，面向投资人和客户',
      spec: {
        topic: '智能助手产品发布会',
        audience: '投资人与客户',
        page_count: 10,
        style: '金融专业',
        needs_cover: true,
        needs_toc: true,
        needs_summary: true,
        needs_chart: true,
      },
    },
    {
      title: '教学课件',
      description: 'Python 编程入门课程，15页教学内容',
      spec: {
        topic: 'Python 编程入门',
        audience: '初学者',
        page_count: 15,
        style: '教育培训',
        needs_cover: true,
        needs_toc: true,
        needs_summary: true,
        needs_chart: false,
      },
    },
  ];

  return examples;
};
