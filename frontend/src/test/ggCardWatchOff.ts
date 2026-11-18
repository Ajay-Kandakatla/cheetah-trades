/* 👀 2026-11-18 (cardview spec §4 WP-B step 6) — the one-line opt-out for the existing GajjalaBoard tests.
 *
 * The 🚩 / 🧪 card grid draws in the 👀 Watch layout BY DEFAULT (Ajay 2026-11-18: "I need the watch list kinda chart formant
 * view video view as default here too from the tabs pages"). The board tests written before it assert the small-card grid
 * (`.cm-grid`, PatternChart props, fetch counts). Importing this module FIRST stores the mode OFF (`gg-card-watch` = '0') in
 * a fresh in-memory localStorage before every test, so those tests keep drawing the grid they were written against — the
 * OFF grid is pinned byte-identical by GajjalaBoard.card_watch_off.snapshot.test.tsx. A side-effect module: never a global
 * setup (that would invert the product default for the whole suite silently). The Watch layout itself is tested in
 * GajjalaBoard.card_watch.test.tsx. */
import { afterEach, beforeEach, vi } from 'vitest';

export function ggMemStorage(seed: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries(seed));
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(),
    key: (i: number) => Array.from(m.keys())[i] ?? null,
    get length() { return m.size; },
  };
}

beforeEach(() => { vi.stubGlobal('localStorage', ggMemStorage({ 'gg-card-watch': '0' })); });
afterEach(() => { vi.unstubAllGlobals(); });
