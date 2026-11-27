/* 📅 The 👀 Watch board with the 📅 Runners roster (2026-11-26, spec watchrun rev 2 §3.5, WP fe-roster). Ajay 2026-11-26:
 * "Ok then add them to our watch list and track them please.. I know he tracks them for two weeks sometimes.. before he
 * discards them.. Can you do that please". The real board, fetch stubbed, the served all-rules golden + the served roster.
 * TWO ×, TWO LISTS [C4], both directions: the roster × fetches ONLY the seat path (never the tile path), the tile of that
 * name stays, then exactly ONE board re-GET; a tile × fetches ONLY the tile path (never the seat path) and the roster row of
 * that name stays. NEGATIVES: no `runners` key → nothing drawn; junk → nothing; write('DELETE') is never handed down. */
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import boardGold from '../lib/__fixtures__/ggwAllRules.golden.json';
import gold from '../lib/__fixtures__/ggwRunRoster.golden.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GGW_LIVE_PATH, GGW_PATH, ggwSymbolPath } from '../lib/gajjalaWatch';
import { GGW_RUNSEAT_PATH, GGW_RUNTRACK_PATH, ggwRunSeatPath } from '../lib/ggwRunRoster';

vi.mock('../lib/eventBus', () => ({ subscribe: () => () => {} }));

const G = gold as any;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
/* OMH has a tile (his name) AND sits on the roster; BGLC is on the roster only */
function roster(): any {
  const r = clone(G.runners);
  const omh = { ...clone(G.runners.rows[1]), symbol: 'OMH', remove_title: 'served-rr-remove-OMH' };
  r.rows = [omh, clone(G.runners.rows[0])];
  r.text = '📅 Runners · 2';
  r.n = 2;
  return r;
}
let tileList: string[] = [];
let seated: string[] = [];
let withRunners = true;
function board(): any {
  const b = clone(boardGold) as any;
  b.refresh_sec = 0;
  b.next_window_sec = null;
  delete b.pending_poll_sec;
  delete b.pending_wait_max_sec;
  delete b.pending_late_poll_sec;
  b.rows = b.rows.filter((r: any) => tileList.includes(r.symbol));
  b.symbols = b.symbols.filter((s: string) => tileList.includes(s));
  if (withRunners) {
    const r = roster();
    r.rows = r.rows.filter((x: any) => seated.includes(x.symbol));
    b.runners = r;
    const omh = b.rows.find((x: any) => x.symbol === 'OMH');
    if (omh && seated.includes('OMH')) omh.runner = clone(G.row_runner);
  }
  return b;
}
const res = (body: unknown) => ({ ok: true, json: async () => body }) as unknown as Response;
type Call = { url: string; method: string };
let calls: Call[] = [];
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
const flushN = async (n = 6) => { for (let i = 0; i < n; i += 1) await flush(); };

async function mount() {
  vi.stubGlobal('matchMedia', (qq: string) => ({ matches: false, media: qq, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method || 'GET').toUpperCase();
    calls.push({ url, method });
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) return res({ state: 'ok', stream: { on: true, state: 'live' }, symbols: [] });
    if (url.includes(GGW_RUNSEAT_PATH)) {
      const sym = decodeURIComponent(url.split('/').pop() as string);
      seated = seated.filter((s) => s !== sym);
      return res({ state: 'dismissed', symbol: sym, text: `${sym} removed from 📅 Runners` });
    }
    if (url.includes(GGW_RUNTRACK_PATH)) return res(G.track_all);
    if (url.includes('/chart-maps/gajjala-watch/symbols/')) {
      const sym = decodeURIComponent(url.split('/').pop() as string);
      if (method === 'DELETE') {
        tileList = tileList.filter((s) => s !== sym);
        return res({ state: 'removed', symbols: tileList, symbol: sym, text: null });
      }
    }
    if (url.endsWith('/chart-maps/gajjala-watch/symbols')) {
      return res({ state: 'ok', symbols: tileList, full: false, full_text: null,
        labels: { add: '➕', remove: '➖', add_title: 'a {symbol}', remove_title: 'r {symbol}' } });
    }
    if (method === 'GET' && url.includes(GGW_PATH) && !url.includes('/chart-maps/gajjala-watch/')) return res(board());
    return { ok: false, status: 404, json: async () => ({}) } as unknown as Response;
  }));
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_watch']}><GajjalaWatchBoard /></MemoryRouter>);
  await flushN();
  return r.container;
}
const q = (c: HTMLElement, id: string) => c.querySelector(`[data-testid="${id}"]`) as HTMLElement | null;
const isBoardGet = (c: Call) => c.method === 'GET' && c.url.endsWith(GGW_PATH);

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(Date.parse('2026-11-27T15:00:00.000Z'));
  vi.stubGlobal('localStorage', memStorage());
  vi.stubGlobal('EventSource', function EventSource() {} as unknown as typeof EventSource);
  (Element.prototype as any).scrollIntoView = function () {};
  calls = [];
  tileList = (boardGold as any).rows.map((r: any) => r.symbol);
  seated = ['OMH', 'BGLC'];
  withRunners = true;
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('📅 the roster on the board', { timeout: 20000 }, () => {
  it('drawn UNDER the tiles, in served order; the seated tile carries the two served chips', async () => {
    const c = await mount();
    const rr = q(c, 'ggw-rr')!;
    const grid = c.querySelector('.ggw-grid')!;
    expect(rr).not.toBeNull();
    expect(grid.compareDocumentPosition(rr) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(Array.from(rr.querySelectorAll('[data-testid^="ggw-rr-row-"]')).map((e) => e.getAttribute('data-testid')))
      .toEqual(['ggw-rr-row-OMH', 'ggw-rr-row-BGLC']);
    expect(q(c, 'ggw-runner-day-OMH')!.textContent).toBe(G.row_runner.day_text);
    expect(q(c, 'ggw-runner-seat-OMH')!.textContent).toBe(G.row_runner.seat_text);
    expect(q(c, 'ggw-runner-day-NVDA')).toBeNull();
  });
  it('NEGATIVE: no `runners` key → no roster, no chip, and no request to either 📅 route', async () => {
    withRunners = false;
    const c = await mount();
    expect(q(c, 'ggw-rr')).toBeNull();
    expect(c.querySelector('[data-testid^="ggw-runner-"]')).toBeNull();
    expect(calls.some((x) => x.url.includes('/runners/'))).toBe(false);
  });
  it('the roster × → DELETE ggwRunSeatPath only (NEVER ggwSymbolPath); the TILE stays; then exactly ONE board re-GET; the served text shows', async () => {
    const c = await mount();
    expect(q(c, 'ggw-tile-OMH')).not.toBeNull();
    const at = calls.length;
    fireEvent.click(q(c, 'ggw-rr-x-OMH')!);
    expect(q(c, 'ggw-rr-row-OMH')).toBeNull();
    await flushN();
    const after = calls.slice(at);
    expect(after.filter((x) => x.method === 'DELETE').map((x) => x.url)).toEqual([expect.stringMatching(new RegExp(`${ggwRunSeatPath('OMH')}$`))]);
    expect(after.some((x) => x.url.endsWith(ggwSymbolPath('OMH')))).toBe(false);
    expect(after.filter(isBoardGet).length).toBe(1);
    expect(q(c, 'ggw-tile-OMH')).not.toBeNull();
    expect(q(c, 'ggw-rr-row-OMH')).toBeNull();
    expect(q(c, 'ggw-rr-row-BGLC')).not.toBeNull();
    expect(q(c, 'ggw-msg')!.textContent).toBe('OMH removed from 📅 Runners');
    expect(q(c, 'ggw-runner-day-OMH')).toBeNull();                       // the re-GET no longer serves its tag
  });
  it('the tile × → DELETE ggwSymbolPath only (NEVER the seat path); the ROSTER ROW stays', async () => {
    const c = await mount();
    const at = calls.length;
    fireEvent.click(q(c, 'ggw-tile-OMH')!.querySelector('button.ggw-remove') as HTMLButtonElement);
    await flushN();
    const after = calls.slice(at);
    expect(after.filter((x) => x.method === 'DELETE').map((x) => x.url)).toEqual([expect.stringMatching(new RegExp(`${ggwSymbolPath('OMH')}$`))]);
    expect(after.some((x) => x.url.includes(GGW_RUNSEAT_PATH))).toBe(false);
    expect(q(c, 'ggw-tile-OMH')).toBeNull();
    expect(q(c, 'ggw-rr-row-OMH')).not.toBeNull();
  });
  it('NEGATIVE: the board hands the roster ONLY onChanged — write(\'DELETE\') is never passed down, and its DELETE is unchanged', async () => {
    const src = await readSource('src/components/GajjalaWatchBoard.tsx');
    const mountLine = src.split('\n').find((l) => l.includes('<GgwRunRoster'))!;
    expect(mountLine).toContain('onChanged={onRunnersChanged}');
    expect(mountLine).not.toMatch(/write|onRemove|ggwSymbolPath/);
    expect(src.split('<GgwRunRoster').length - 1).toBe(1);
    expect(src).toContain(".then(() => fetch(`${API}${ggwSymbolPath(sym)}`, { method, credentials: 'include', cache: 'no-store' }))");
    expect(src).not.toMatch(/ggwRunSeatPath|GGW_RUNSEAT_PATH|useGgwRunSeatRemove/);
  });
});
