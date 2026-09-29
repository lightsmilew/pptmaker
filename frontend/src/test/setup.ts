// Test environment setup
import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

const observerMock = {
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
  takeRecords: vi.fn(() => []),
};

// Mock IntersectionObserver
(globalThis as unknown as { IntersectionObserver: typeof vi.fn }).IntersectionObserver =
  vi.fn().mockImplementation(() => observerMock);

// Mock ResizeObserver
(globalThis as unknown as { ResizeObserver: typeof vi.fn }).ResizeObserver =
  vi.fn().mockImplementation(() => observerMock);
