/// <reference types="vitest/config" />
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Frontend unit-test harness (added 2026-06-13). `npm test` runs once,
// `npm run test:watch` for TDD. jsdom gives us a DOM for React Testing Library;
// pure-logic files (lib/*) test without it.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    css: false,
  },
});
