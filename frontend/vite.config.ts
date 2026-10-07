/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Backend base URL for both REST + WebSocket proxying in dev.
// Override with VITE_BACKEND_HOST / VITE_BACKEND_WS_HOST env vars when needed.
const BACKEND_HOST = process.env.VITE_BACKEND_HOST ?? 'http://localhost:8000';
const BACKEND_WS_HOST = process.env.VITE_BACKEND_WS_HOST ?? BACKEND_HOST;

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      // REST API → FastAPI
      '/api': {
        target: BACKEND_HOST,
        changeOrigin: true,
      },
      // Generated artefacts (PPTX, preview images) → FastAPI
      '/storage': {
        target: BACKEND_HOST,
        changeOrigin: true,
      },
      // WebSocket → FastAPI (bidirectional channel for project workflow)
      '/ws': {
        target: BACKEND_WS_HOST.replace(/^http/, 'ws'),
        ws: true,
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    coverage: {
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'node_modules/',
        'src/test/',
        'src/main.tsx',
        'src/**/*.d.ts',
      ],
    },
  },
});
