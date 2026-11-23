/* 🔒 Hard to borrow on the REAL 👀 Watch board (2026-11-22, spec htb §3.4 M4 / M6, §4 fe).
 *
 * The 2026-11-17 auto fixture with fetch routed by PATHNAME: `/short-interest/reg-sho` answers the stand-in payload (the
 * real useRegSho hook + lib + GgHardToBorrow run); every other `?symbols=` keeps the Watch rows branch. The served
 * fault_text prints as ONE `ggw-line ggw-warn` span in the head (M6), right after the refresh-failed slot; the served
 * short chip prints in each listed tile head (M4). NEGATIVES: a clean payload, a null fault while refreshing, a failed
 * GET → no ggw-htb-fault; ONE reg-sho GET for the whole board; the Watch's own GETs keep their counts. */
import { act, cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
vi.mock('../lib/eventBus', () => ({ subscribe: () => () => {} }));
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { _resetShortInterestCache } from '../hooks/useShortInterest';
import { _resetRegShoCache } from '../hooks/useRegSho';
import { GGW_LIVE_PATH, GGW_PATH } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = autoFixture as any;
const ALL: string[] = RAW.rows.map((r: any) => r.symbol);
const RS_PATH = '/short-interest/reg-sho';
const FAULT = '🔒 Hard to borrow tags may be missing or out of date: Nasdaq threshold list not read yet.';
const item = (sym: string) => ({
  state: 'on', symbol: sym, market: 'nasdaq', exchange: 'Nasdaq', as_of: '2026-11-20', stale: false,
  chip: `served long chip ${sym}`, short: `🔒 Hard to borrow · 11/20 ${sym}`, label: `served label ${sym}`, title: `served title ${sym}`,
});
const LISTED = ['OMH', 'XXII'];
const rs = (over: Record<string, unknown> = {}) => ({
  kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true,
  items: Object.fromEntries(LISTED.map((s) => [s, item(s)])), fault_text: null, refreshing: false, retry_after_sec: null, ...over,
});

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}

type Call = { url: string; method: string };
let calls: Call[] = [];
let RS: unknown = rs();
let mode: 'ok' | 'throw' = 'ok';
const pathOf = (u: string) => new URL(u, 'http://x').pathname;
const symsOf = (u: string) => decodeURIComponent(new URL(u, 'http://x').searchParams.get('symbols') || '').split(',').filter(Boolean);
function routedFetch() {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method ?? 'GET').toUpperCase();
    calls.push({ url, method });
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) {
      return { ok: true, json: async () => ({ state: 'ok', stream: { on: true, state: 'live' }, symbols: [] }) } as unknown as Response;
    }
    if (pathOf(url).endsWith(RS_PATH)) {
      if (mode === 'throw') throw new Error('down');
      return { ok: true, json: async () => clone(RS) } as unknown as Response;
    }
    if (pathOf(url).endsWith('/short-interest/map')) {
      return { ok: true, json: async () => ({ items: {}, n: 0, max_symbols: 200 }) } as unknown as Response;
    }
    if (url.includes('?symbols=')) {
      const syms = symsOf(url);
      const b = clone(RAW);
      return { ok: true, json: async () => ({ ...b, rows: b.rows.filter((r: any) => syms.includes(r.symbol)) }) } as unknown as Response;
    }
    return { ok: true, json: async () => clone(RAW) } as unknown as Response;
  }));
}
const gets = () => calls.filter((c) => c.method === 'GET');
const rsGets = () => gets().filter((c) => pathOf(c.url).endsWith(RS_PATH));
const full = () => gets().filter((c) => c.url.endsWith(GGW_PATH));

async function mountBoard() {
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  routedFetch();
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_watch']}><GajjalaWatchBoard /></MemoryRouter>);
  for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  await act(async () => { await vi.advanceTimersByTimeAsync(100); });
  for (let i = 0; i < 3; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  return r.container;
}
const q = (c: HTMLElement, id: string) => c.querySelector(`[data-testid="${id}"]`) as HTMLElement | null;

describe('🔒 on the 👀 Watch board', { timeout: 20000 }, () => {
  beforeEach(() => {
    vi.useFakeTimers();
    _resetShortInterestCache();
    _resetRegShoCache();
    RS = rs();
    mode = 'ok';
    vi.stubGlobal('localStorage', memStorage());
    vi.stubGlobal('EventSource', function EventSource() {} as unknown as typeof EventSource);
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); _resetRegShoCache(); _resetShortInterestCache(); });

  it('M6: a served fault_text draws ONE ggw-htb-fault span in the Watch head, verbatim', async () => {
    RS = rs({ fault_text: FAULT });
    const c = await mountBoard();
    const f = q(c, 'ggw-htb-fault')!;
    expect(f).not.toBeNull();
    expect(f.tagName).toBe('SPAN');
    expect(f.textContent).toBe(FAULT);
    expect(f.className).toBe('ggw-line ggw-warn gg-htb-fault');
    expect(f.parentElement).toBe(c.querySelector('.ggw-head'));
    expect(c.querySelectorAll('[data-testid="ggw-htb-fault"]')).toHaveLength(1);
    /* the card-grid / table testid is never used on the Watch */
    expect(q(c, 'gg-htb-fault')).toBeNull();
  });

  it('M4: every listed tile prints the served short chip in its head; unlisted tiles print none', async () => {
    const c = await mountBoard();
    for (const s of LISTED) {
      const chip = q(c, `ggw-htb-${s}`)!;
      expect(chip, s).not.toBeNull();
      expect(chip.textContent).toBe(item(s).short);
      expect(chip.closest('.ggw-tile-head')).not.toBeNull();
    }
    const tagged = Array.from(c.querySelectorAll('[data-testid^="ggw-htb-"]')).map((e) => e.getAttribute('data-testid'));
    expect(tagged.sort()).toEqual(LISTED.map((s) => `ggw-htb-${s}`).sort());
    expect(ALL.length).toBeGreaterThan(LISTED.length);
  });

  it('ONE reg-sho GET for the whole board, no query string; the Watch\'s own full GET count is unchanged', async () => {
    await mountBoard();
    expect(rsGets()).toHaveLength(1);
    expect(new URL(rsGets()[0].url, 'http://x').search).toBe('');
    expect(full()).toHaveLength(1);
    /* NEGATIVE: the reg-sho GET is never mistaken for a Watch row poll */
    expect(rsGets()[0].url).not.toContain('?symbols=');
  });

  for (const [name, over] of [
    ['a clean payload', {}],
    ['fault_text null while refreshing', { refreshing: true, retry_after_sec: 20, fault_text: null, items: {} }],
    ['a blank fault_text', { fault_text: '   ' }],
  ] as const) {
    it(`NEGATIVE: ${name} → no ggw-htb-fault in the head`, async () => {
      RS = rs(over);
      const c = await mountBoard();
      expect(rsGets()).toHaveLength(1);
      expect(q(c, 'ggw-htb-fault')).toBeNull();
      expect(c.querySelector('.gg-htb-fault')).toBeNull();
    });
  }

  it('NEGATIVE: a failed GET → no fault line, no chip, no crash; the board still renders every tile', async () => {
    RS = rs({ fault_text: FAULT });
    mode = 'throw';
    const c = await mountBoard();
    expect(rsGets()).toHaveLength(1);
    expect(c.querySelector('.gg-htb, .gg-htb-fault')).toBeNull();
    expect(c.querySelectorAll('.ggw-tile').length).toBe(ALL.length);
  });

  it('NEGATIVE: a foreign body on the reg-sho path (the Watch board JSON) → nothing', async () => {
    RS = clone(RAW);
    const c = await mountBoard();
    expect(c.querySelector('.gg-htb, .gg-htb-fault')).toBeNull();
  });
});

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('source guard — GajjalaWatchBoard.tsx', () => {
  it('the fault line sits right after the refresh-failed line, inline, ggw-line ggw-warn', async () => {
    const src = await readSource('src/components/GajjalaWatchBoard.tsx');
    const a = src.indexOf('{refreshFailed ? <span className="ggw-line ggw-warn">');
    const b = src.indexOf('<GgHardToBorrowFault testid="ggw-htb-fault" className="ggw-line ggw-warn" inline />');
    expect(a).toBeGreaterThan(-1);
    expect(b).toBeGreaterThan(a);
    expect(src.slice(a, b).split('\n').length).toBeLessThanOrEqual(3);
  });
});
