/// <reference types="vite/client" />
import { describe, it, expect } from 'vitest';

/* Source guard (2026-09-14): the admin's Gmail must never appear as a string
   literal anywhere under frontend/src — everything here ships into the built
   bundle, and anyone can curl the static assets and grep it out. Six files
   were cleaned in 2026; pages/AdminTodos.tsx survived until a live grep of
   the nginx assets caught its chunk. Access gates read `is_admin` /
   `is_primary_admin` off /auth/me instead.

   The address is assembled from parts so this file itself passes the backend
   twin (backend/tests/test_ollama_chat.py walks the same tree, excluding
   nothing). Vitest's cwd is the frontend package root, so the glob below
   covers every .ts/.tsx under src — tests included. */

const ADDRESS = ['ajaykandakatla', 'gmail.com'].join('@');

const sources = import.meta.glob('/src/**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

describe('admin email never reaches the bundle', () => {
  it('walks every .ts/.tsx under src, nothing excluded', () => {
    const files = Object.keys(sources);
    expect(files.length).toBeGreaterThan(100);
    expect(files.some((f) => f.endsWith('/pages/AdminTodos.tsx'))).toBe(true);
    expect(files.some((f) => f.endsWith('/hooks/useUser.ts'))).toBe(true);
  });

  it('no source file contains the address', () => {
    const hits = Object.entries(sources)
      .filter(([, text]) => text.toLowerCase().includes(ADDRESS))
      .map(([file]) => file);
    expect(hits).toEqual([]);
  });

  it('REGRESSION: AdminTodos gates on the server flag, not an email compare', () => {
    const key = Object.keys(sources).find((f) => f.endsWith('/pages/AdminTodos.tsx'))!;
    const src = sources[key];
    expect(src).toMatch(/user\?\.is_primary_admin/);
    expect(src).not.toMatch(/user\?\.email[^\n]*===/);
  });
});
