/* 🎯 Gajjala's Watch — A+ seats on the board (2026-11-17, spec ggwaplus2 §3.4, WP-1 `ggw-aplus-seats`).
 * Ajay: "Push new Apluses immediately in to watch list and an alert for me please Missed AKAN and GP".
 *
 * The REAL board over the 2026-11-17 auto fixture with two new served fields: the board's `auto.skipped_text` (the
 * loop's last-step A+ names with no seat) and a row's `auto.why` ("aplus" / "potential"). The FE types no words: the
 * skipped line and the A+ row chip print the served strings verbatim. NEGATIVES: null / junk skipped_text → no line;
 * an older payload → no line; the A+ row's chip never carries an FE-composed A+ word. */
import { act, cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
vi.mock('../lib/eventBus', () => ({ subscribe: () => () => {} }));
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GGW_LIVE_PATH, GGW_PHONE_MQ } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = autoFixture as any;
const AUTO: string[] = RAW.auto.symbols;
const SKIPPED = 'SERVED-SKIPPED 🎯 A+ not seated — every seat holds an A+ or your own name: AZI';
const APLUS_TEXT = 'SERVED 🤖 auto · 🚩 1-min · 🎾 Reversal Squeeze · A+ (triggered)';
const APLUS_ADDED = 'SERVED 🎯 A+ 16:44 ET (🚩 1-min 🎾 Reversal Squeeze) · seated 16:45 ET';

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}

async function mount(board: () => any) {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: q === GGW_PHONE_MQ && false, media: q,
    addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method ?? 'GET').toUpperCase();
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) return { ok: true, json: async () => ({ state: 'ok', stream: { on: true, state: 'live' }, symbols: [] }) };
    return { ok: true, json: async () => board() };
  }));
  const r = render(<MemoryRouter><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return r.container;
}
const tile = (c: HTMLElement, s: string) => c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement;

describe('🎯 A+ seats on the board', { timeout: 20000 }, () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('localStorage', memStorage());
    vi.stubGlobal('EventSource', function EventSource() {} as unknown as typeof EventSource);
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('the served skipped_text prints verbatim under the auto head', async () => {
    await mount(() => { const b = clone(RAW); b.auto.skipped_text = SKIPPED; return b; });
    const line = screen.getByTestId('ggw-auto-skipped');
    expect(line.textContent).toBe(SKIPPED);
    expect(line.classList.contains('ggw-warn')).toBe(true);
  });
  it('NEGATIVE: null / empty / junk skipped_text and an older payload → no line', async () => {
    for (const junk of [null, '', '  ', 3, ['AZI'], { x: 1 }, undefined]) {
      await mount(() => { const b = clone(RAW); b.auto.skipped_text = junk; return b; });
      expect(screen.queryByTestId('ggw-auto-skipped')).toBeNull();
      cleanup();
    }
    await mount(() => { const b = clone(RAW); delete b.auto.skipped_text; return b; });
    expect(screen.queryByTestId('ggw-auto-skipped')).toBeNull();
  });
  it('an A+ auto row prints the served text and hover verbatim — the FE composes no A+ word', async () => {
    const sym = AUTO[0];
    const c = await mount(() => {
      const b = clone(RAW);
      const row = b.rows.find((r: any) => r.symbol === sym);
      Object.assign(row.auto, { why: 'aplus', text: APLUS_TEXT, added_text: APLUS_ADDED, volume_text: null,
        leaving_text: null });
      return b;
    });
    const chip = tile(c, sym).querySelector('[data-testid="ggw-auto"]') as HTMLElement;
    expect(chip.textContent).toBe(APLUS_TEXT);
    expect(chip.getAttribute('title')).toBe(APLUS_ADDED);
    /* NEGATIVE: a potential row next to it keeps its own served words (no A+ anywhere in them) */
    const pot = RAW.rows.find((r: any) => r.symbol === AUTO[1]).auto;
    expect((tile(c, AUTO[1]).querySelector('[data-testid="ggw-auto"]') as HTMLElement).textContent).toBe(pot.text);
    expect(pot.text).not.toMatch(/A\+/);
  });
});
