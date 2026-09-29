// API client unit tests.
// Covers the trimmed REST surface (project creation, file upload) and the
// WebSocket URL factory. Workflow actions live on the WebSocket and are
// covered by projectStore.test.ts.

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { api, getDownloadUrl, createWebSocket } from '@/api/client';
import type { PPTProject, PageData, PPTProjectSpec } from '@/types';

// ================== Mock fetch ==================

type FetchHandler = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

const createJsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const createErrorResponse = (detail: string, status = 500): Response =>
  new Response(JSON.stringify({ detail }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

let fetchMock: ReturnType<typeof vi.fn<Parameters<FetchHandler>, ReturnType<FetchHandler>>>;
let lastRequest: { url: string; init?: RequestInit } = { url: '' };

const setFetchHandler = (handler: FetchHandler) => {
  fetchMock = vi.fn<Parameters<FetchHandler>, ReturnType<FetchHandler>>(
    async (url, init) => handler(url, init)
  );
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
};

beforeEach(() => {
  lastRequest = { url: '' };
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ================== Fixtures ==================

const sampleSpec: PPTProjectSpec = {
  topic: '编译原理',
  audience: '学生',
  page_count: 6,
  style: '学术',
};

const samplePage: PageData = {
  page_id: 'page-01',
  page_type: 'cover',
  content: { title: 'Hello', subtitle: 'World', key_points: [], bullet_points: [], speaker_notes: '' },
  layout: { layout_type: 'cover' },
  iteration: 1,
  max_iterations: 3,
  status: 'pending',
};

const sampleProject: PPTProject = {
  id: 'proj-1',
  spec: sampleSpec,
  status: 'idle',
  pages: [samplePage],
};

// ================== Project creation ==================

describe('api - createProject', () => {
  it('POSTs /projects with body and returns project', async () => {
    setFetchHandler(async (url, init) => {
      lastRequest = { url: String(url), init };
      return createJsonResponse(sampleProject);
    });

    const result = await api.createProject({ spec: sampleSpec, user_input: 'some input' });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(lastRequest.url).toBe('/api/v1/projects');
    expect(lastRequest.init?.method).toBe('POST');
    expect(lastRequest.init?.headers).toMatchObject({ 'Content-Type': 'application/json' });
    const body = JSON.parse(lastRequest.init?.body as string);
    expect(body).toEqual({ spec: sampleSpec, user_input: 'some input' });
    expect(result).toEqual(sampleProject);
  });

  it('createProject without spec still sends the request', async () => {
    setFetchHandler(async (url, init) => {
      lastRequest = { url: String(url), init };
      return createJsonResponse(sampleProject);
    });

    await api.createProject({});
    expect(lastRequest.url).toBe('/api/v1/projects');
    expect(JSON.parse(lastRequest.init?.body as string)).toEqual({});
  });
});

// ================== File upload ==================

describe('api - file upload', () => {
  it('uploadAndParse posts file to /upload/parse', async () => {
    setFetchHandler(async (url, init) => {
      lastRequest = { url: String(url), init };
      return createJsonResponse({
        filename: 'doc.txt',
        content: 'full content',
        content_preview: 'full ...',
      });
    });

    const file = new File(['full content'], 'doc.txt', { type: 'text/plain' });
    const result = await api.uploadAndParse(file);

    expect(lastRequest.url).toBe('/api/v1/upload/parse');
    expect(lastRequest.init?.method).toBe('POST');
    expect(lastRequest.init?.body).toBeInstanceOf(FormData);
    expect(result.content).toBe('full content');
  });

  it('uploadAndParse surfaces server error detail', async () => {
    setFetchHandler(async () => createErrorResponse('不支持的文件类型', 400));

    const file = new File(['x'], 'doc.txt', { type: 'text/plain' });
    await expect(api.uploadAndParse(file)).rejects.toThrow('不支持的文件类型');
  });
});

// ================== Error handling ==================

describe('api - error handling', () => {
  it('throws error with server detail when response is not ok', async () => {
    setFetchHandler(async () => createErrorResponse('Project not found', 404));

    await expect(api.createProject({ user_input: 'x' })).rejects.toThrow('Project not found');
  });

  it('falls back to generic error when response is not JSON', async () => {
    setFetchHandler(async () => new Response('not json', { status: 500 }));

    await expect(api.createProject({})).rejects.toThrow('Request failed');
  });
});

// ================== URL helpers ==================

describe('api - url helpers', () => {
  it('getDownloadUrl returns /storage/{filename}', () => {
    expect(getDownloadUrl('output.pptx')).toBe('/storage/output.pptx');
  });
});

// ================== WebSocket factory ==================

interface FakeWebSocket {
  url: string;
}

const setWebSocketProtocol = (protocol: string, host: string) => {
  Object.defineProperty(window, 'location', {
    value: { protocol, host },
    writable: true,
    configurable: true,
  });
};

describe('createWebSocket', () => {
  it('builds a real WebSocket with the project id', () => {
    setWebSocketProtocol('http:', 'localhost:5173');
    const ws = createWebSocket('proj-1');
    expect(ws).toBeInstanceOf(WebSocket);
  });

  it('uses wss:// when on https', () => {
    setWebSocketProtocol('https:', 'example.com');

    const Original = globalThis.WebSocket;
    class FakeWS {
      url: string;
      constructor(url: string) {
        this.url = url;
      }
    }
    (globalThis as unknown as { WebSocket: typeof FakeWS }).WebSocket = FakeWS;

    const ctor = createWebSocket as unknown as new (id: string) => FakeWS;
    const ws = new ctor('proj-1');
    expect(ws.url).toBe('wss://example.com/ws/proj-1');

    (globalThis as unknown as { WebSocket: typeof WebSocket }).WebSocket = Original;
  });

  it('uses ws:// when on http', () => {
    setWebSocketProtocol('http:', 'localhost:5173');

    const Original = globalThis.WebSocket;
    class FakeWS {
      url: string;
      constructor(url: string) {
        this.url = url;
      }
    }
    (globalThis as unknown as { WebSocket: typeof FakeWS }).WebSocket = FakeWS;

    const ctor = createWebSocket as unknown as new (id: string) => FakeWS;
    const ws = new ctor('proj-1');
    expect(ws.url).toBe('ws://localhost:5173/ws/proj-1');

    (globalThis as unknown as { WebSocket: typeof WebSocket }).WebSocket = Original;
  });
});
