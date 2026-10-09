// Test environment setup
import '@testing-library/jest-dom/vitest';
// Node channels connect independent test workers; browser tabs are verified
// separately. Component tests keep sessions isolated to their own document.
Object.defineProperty(globalThis, 'BroadcastChannel', { value: undefined, configurable: true, writable: true });
Object.defineProperty(window, 'scrollTo', { value: () => {}, configurable: true, writable: true });
// jsdom has no layout or pointer capture; Radix uses these browser APIs.
Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { value: () => {}, configurable: true });
Object.defineProperty(HTMLElement.prototype, 'hasPointerCapture', { value: () => false, configurable: true });
Object.defineProperty(HTMLElement.prototype, 'setPointerCapture', { value: () => {}, configurable: true });
Object.defineProperty(HTMLElement.prototype, 'releasePointerCapture', { value: () => {}, configurable: true });
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
