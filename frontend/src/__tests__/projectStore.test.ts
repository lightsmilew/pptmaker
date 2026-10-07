// Zustand project store unit tests.
//
// The store is now WebSocket-driven: actions like parseInput / planOutline /
// generateParallel / renderPPTX emit commands via a dispatcher that the
// useWebSocket hook wires to the live socket. Only createProject still
// uses REST.

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useProjectStore, useExamples } from '@/stores/projectStore';
import { api } from '@/api/client';
import type {
  PPTProject,
  PPTProjectSpec,
  PageData,
  PageUpdateEvent,
  ParallelGenerationStatus,
  ReviewCompletedEvent,
  PreviewReadyEvent,
  CompletedEvent,
  WSCommand,
} from '@/types';

// ================== Mock the API ==================
vi.mock('@/api/client', () => ({
  api: {
    createProject: vi.fn(),
    uploadAndParse: vi.fn(),
  },
  getDownloadUrl: vi.fn((filename: string) => `/storage/${filename}`),
  createWebSocket: vi.fn(),
}));

const mockedApi = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

// ================== Fixtures ==================
const sampleSpec: PPTProjectSpec = {
  topic: 'AI产品发布',
  audience: '投资人',
  page_count: 4,
  style: '商务',
};

const createSamplePage = (id: string, status: PageData['status'] = 'pending'): PageData => ({
  page_id: id,
  page_type: 'content',
  content: { title: `Title ${id}`, subtitle: '', key_points: [], bullet_points: [], speaker_notes: '' },
  layout: { layout_type: 'content' },
  iteration: 1,
  max_iterations: 3,
  status,
});

const createProject = (overrides: Partial<PPTProject> = {}): PPTProject => ({
  id: 'proj-1',
  spec: sampleSpec,
  status: 'idle',
  current_step: 'init',
  progress: 0,
  pages: [
    createSamplePage('page-01'),
    createSamplePage('page-02'),
    createSamplePage('page-03'),
    createSamplePage('page-04'),
  ],
  ...overrides,
});

// Capture commands emitted by the store
let lastCommand: WSCommand | null = null;
const captureCommand: (cmd: WSCommand) => void = (cmd) => {
  lastCommand = cmd;
};

const resetStore = () => {
  useProjectStore.setState({
    project: null,
    isLoading: false,
    error: null,
    parallelStatus: null,
    lastDownloadUrl: null,
    sendCommand: captureCommand,
  });
  lastCommand = null;
  Object.values(mockedApi).forEach((fn) => fn.mockReset());
};

beforeEach(() => {
  resetStore();
});

// ================== Initial state ==================
describe('useProjectStore - initial state', () => {
  it('switching projects replaces the download URL and isolates queued commands', () => {
    useProjectStore.setState({ project:createProject(),lastDownloadUrl:'/storage/old.pptx',pendingCommands:[{type:'render_pptx'}] });
    useProjectStore.getState().setProject(createProject({ id:'proj-history',status:'completed',download_url:'/storage/history.pptx' }));
    expect(useProjectStore.getState().lastDownloadUrl).toBe('/storage/history.pptx');
    expect(useProjectStore.getState().pendingCommands).toEqual([]);
    useProjectStore.getState().setProject(createProject({ id:'proj-draft' }));
    expect(useProjectStore.getState().lastDownloadUrl).toBeNull();
  });
  it('starts with empty state and a wired dispatcher', () => {
    const state = useProjectStore.getState();
    expect(state.project).toBeNull();
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
    expect(state.parallelStatus).toBeNull();
    expect(typeof state.sendCommand).toBe('function');
  });
});

// ================== createProject ==================
describe('useProjectStore - createProject', () => {
  it('creates a new project and returns its id', async () => {
    const project = createProject();
    mockedApi.createProject.mockResolvedValueOnce(project);

    const id = await useProjectStore.getState().createProject(sampleSpec, 'some input');

    expect(id).toBe('proj-1');
    expect(mockedApi.createProject).toHaveBeenCalledWith({
      spec: sampleSpec,
      user_input: 'some input',
    });
    expect(useProjectStore.getState().project?.id).toBe('proj-1');
    expect(useProjectStore.getState().isLoading).toBe(false);
  });

  it('sets error state when API fails', async () => {
    mockedApi.createProject.mockRejectedValueOnce(new Error('Network error'));

    await expect(useProjectStore.getState().createProject(sampleSpec)).rejects.toThrow('Network error');
    expect(useProjectStore.getState().error).toBe('Network error');
  });

  it('toggles isLoading during async work', async () => {
    let resolveCreate: (value: PPTProject) => void;
    mockedApi.createProject.mockReturnValueOnce(
      new Promise<PPTProject>((resolve) => {
        resolveCreate = resolve;
      })
    );

    const promise = useProjectStore.getState().createProject(sampleSpec);
    expect(useProjectStore.getState().isLoading).toBe(true);

    resolveCreate!(createProject());
    await promise;

    expect(useProjectStore.getState().isLoading).toBe(false);
  });
});

// ================== Command actions (WebSocket-driven) ==================
describe('useProjectStore - WebSocket command actions', () => {
  it('parseInput emits a parse_input command', () => {
    useProjectStore.setState({ project: createProject() });
    useProjectStore.getState().parseInput();
    expect(lastCommand).toEqual({ type: 'parse_input' });
  });

  it('planOutline emits a plan_outline command', () => {
    useProjectStore.setState({ project: createProject() });
    useProjectStore.getState().planOutline();
    expect(lastCommand).toEqual({ type: 'plan_outline' });
  });

  it('renderPPTX emits a render_pptx command', () => {
    useProjectStore.setState({ project: createProject() });
    useProjectStore.getState().renderPPTX();
    expect(lastCommand).toEqual({ type: 'render_pptx' });
  });

  it('deleteProject emits a delete_project command', () => {
    useProjectStore.setState({ project: createProject() });
    useProjectStore.getState().deleteProject();
    expect(lastCommand).toEqual({ type: 'delete_project' });
  });

  it('generateParallel seeds parallelStatus and emits command', () => {
    useProjectStore.setState({ project: createProject() });
    useProjectStore.getState().generateParallel();

    const state = useProjectStore.getState();
    expect(state.parallelStatus?.total_pages).toBe(4);
    expect(Object.keys(state.parallelStatus?.pages_status || {})).toHaveLength(4);
    expect(lastCommand).toEqual({ type: 'generate_parallel' });
  });

  it('updateSpec emits update_spec with patch', () => {
    useProjectStore.setState({ project: createProject() });
    useProjectStore.getState().updateSpec({ topic: 'New topic' });
    expect(lastCommand).toEqual({
      type: 'update_spec',
      data: { patch: { topic: 'New topic' } },
    });
  });

  it('updatePage emits update_page with page id and patch', () => {
    useProjectStore.setState({ project: createProject() });
    useProjectStore.getState().updatePage('page-02', { status: 'completed' } as any);
    expect(lastCommand).toEqual({
      type: 'update_page',
      data: { page_id: 'page-02', patch: { status: 'completed' } },
    });
  });

  it('triggerReview emits trigger_review with page id', () => {
    useProjectStore.setState({ project: createProject() });
    useProjectStore.getState().triggerReview('page-03');
    expect(lastCommand).toEqual({
      type: 'trigger_review',
      data: { page_id: 'page-03' },
    });
  });

  it('actions queue the command when no dispatcher is wired', () => {
    useProjectStore.setState({
      project: createProject(),
      sendCommand: null,
      pendingCommands: [],
    });
    useProjectStore.getState().parseInput();
    expect(useProjectStore.getState().error).toBeNull();
    expect(useProjectStore.getState().pendingCommands).toEqual([
      { type: 'parse_input' },
    ]);
  });

  it('setSendCommand flushes queued commands to the new dispatcher', () => {
    useProjectStore.setState({
      project: createProject(),
      sendCommand: null,
      pendingCommands: [],
    });

    useProjectStore.getState().parseInput();
    useProjectStore.getState().planOutline();
    expect(useProjectStore.getState().pendingCommands).toHaveLength(2);

    const received: WSCommand[] = [];
    useProjectStore.getState().setSendCommand((cmd) => received.push(cmd));

    expect(received).toEqual([
      { type: 'parse_input' },
      { type: 'plan_outline' },
    ]);
    expect(useProjectStore.getState().pendingCommands).toEqual([]);
  });
});

// ================== Event handlers (WebSocket -> store) ==================
describe('useProjectStore - WebSocket event handlers', () => {
  it('handleStatePatch replaces the project snapshot', () => {
    useProjectStore.setState({ project: createProject() });
    const next = createProject({ status: 'planned', outline: [] });
    useProjectStore.getState().handleStatePatch(next);
    expect(useProjectStore.getState().project?.status).toBe('planned');
  });

  it('handlePageUpdated updates the page status and review/preview', () => {
    useProjectStore.setState({
      project: createProject(),
      parallelStatus: {
        total_pages: 4,
        completed_pages: 0,
        failed_pages: 0,
        pages_status: {
          'page-01': 'pending',
          'page-02': 'pending',
          'page-03': 'pending',
          'page-04': 'pending',
        },
      },
    });

    const event: PageUpdateEvent = {
      page_id: 'page-02',
      status: 'completed',
      iteration: 2,
      review: {
        status: 'approved',
        score: 92,
        issues: [],
        suggestions: [],
        next_action: 'approve',
      },
    };

    useProjectStore.getState().handlePageUpdated(event);

    const state = useProjectStore.getState();
    const updated = state.project?.pages.find((p) => p.page_id === 'page-02');
    expect(updated?.status).toBe('completed');
    expect(updated?.iteration).toBe(2);
    expect(updated?.review?.score).toBe(92);
    expect(state.parallelStatus?.completed_pages).toBe(1);
  });

  it('handlePreviewReady attaches a preview to the matching page', () => {
    useProjectStore.setState({ project: createProject() });

    const event: PreviewReadyEvent = {
      page_id: 'page-01',
      image_path: '/storage/preview.png',
      iteration: 1,
    };
    useProjectStore.getState().handlePreviewReady(event);

    const page = useProjectStore.getState().project?.pages.find((p) => p.page_id === 'page-01');
    expect(page?.preview?.image_path).toBe('/storage/preview.png');
    expect(page?.preview?.width).toBe(1600);
    expect(page?.preview?.height).toBe(900);
  });

  it('handleReviewCompleted stores the review on the page', () => {
    useProjectStore.setState({ project: createProject() });

    const event: ReviewCompletedEvent = {
      page_id: 'page-02',
      status: 'approved',
      score: 88,
      issues: [],
      suggestions: ['looks good'],
    };
    useProjectStore.getState().handleReviewCompleted(event);

    const page = useProjectStore.getState().project?.pages.find((p) => p.page_id === 'page-02');
    expect(page?.review?.status).toBe('approved');
    expect(page?.review?.score).toBe(88);
    expect(page?.review?.suggestions).toEqual(['looks good']);
  });

  it('handleParallelStatus replaces parallel status', () => {
    const status: ParallelGenerationStatus = {
      total_pages: 4,
      completed_pages: 2,
      failed_pages: 0,
      pages_status: {},
    };
    useProjectStore.getState().handleParallelStatus(status);
    expect(useProjectStore.getState().parallelStatus).toEqual(status);
  });

  it('handleProgress updates status with step and progress', () => {
    useProjectStore.setState({ project: createProject() });
    useProjectStore.getState().handleProgress('writing', 50);

    const project = useProjectStore.getState().project!;
    expect(project.status).toBe('generating');
    expect(project.current_step).toBe('writing');
    expect(project.progress).toBe(50);
  });

  it('handleCompleted marks the project as completed and remembers the URL', () => {
    useProjectStore.setState({ project: createProject() });

    const event: CompletedEvent = { download_url: '/storage/output.pptx' };
    useProjectStore.getState().handleCompleted(event);

    const project = useProjectStore.getState().project!;
    expect(project.status).toBe('completed');
    expect(project.progress).toBe(100);
    expect(useProjectStore.getState().lastDownloadUrl).toBe('/storage/output.pptx');
  });
});

// ================== Status helpers ==================
describe('useProjectStore - status helpers', () => {
  it('setStatus updates project status, step, and progress', () => {
    useProjectStore.setState({ project: createProject() });
    useProjectStore.getState().setStatus('generating', 'writing', 30);

    const project = useProjectStore.getState().project!;
    expect(project.status).toBe('generating');
    expect(project.current_step).toBe('writing');
    expect(project.progress).toBe(30);
  });

  it('setStatus keeps existing step/progress when not provided', () => {
    useProjectStore.setState({
      project: createProject({ current_step: 'init', progress: 5 }),
    });
    useProjectStore.getState().setStatus('parsing');

    const project = useProjectStore.getState().project!;
    expect(project.status).toBe('parsing');
    expect(project.current_step).toBe('init');
    expect(project.progress).toBe(5);
  });

  it('setError sets the error field', () => {
    useProjectStore.getState().setError('Something went wrong');
    expect(useProjectStore.getState().error).toBe('Something went wrong');
  });

  it('clearProject resets all state including lastDownloadUrl', () => {
    useProjectStore.setState({
      project: createProject(),
      error: 'some error',
      lastDownloadUrl: '/storage/x.pptx',
      parallelStatus: {
        total_pages: 4,
        completed_pages: 1,
        failed_pages: 0,
        pages_status: {},
      },
    });
    useProjectStore.getState().clearProject();
    expect(useProjectStore.getState().project).toBeNull();
    expect(useProjectStore.getState().error).toBeNull();
    expect(useProjectStore.getState().parallelStatus).toBeNull();
    expect(useProjectStore.getState().lastDownloadUrl).toBeNull();
  });

  it('setSendCommand swaps the dispatcher', () => {
    const other = vi.fn();
    useProjectStore.getState().setSendCommand(other);
    expect(useProjectStore.getState().sendCommand).toBe(other);
  });
});

// ================== useExamples ==================
describe('useExamples - example projects', () => {
  it('returns a non-empty list of examples', () => {
    const examples = useExamples();
    expect(examples.length).toBeGreaterThan(0);
  });

  it('each example has title, description, and spec', () => {
    const examples = useExamples();
    examples.forEach((ex) => {
      expect(typeof ex.title).toBe('string');
      expect(typeof ex.description).toBe('string');
      expect(ex.spec).toBeDefined();
      expect(typeof ex.spec.topic).toBe('string');
      expect(typeof ex.spec.page_count).toBe('number');
    });
  });

  it('includes technical, product, and education style examples', () => {
    const styles = useExamples().map((e) => e.spec.style);
    expect(styles).toContain('学术简约');
    expect(styles).toContain('金融专业');
    expect(styles).toContain('教育培训');
  });
});
