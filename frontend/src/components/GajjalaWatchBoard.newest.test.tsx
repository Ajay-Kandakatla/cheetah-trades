/* 🆕 Gajjala's Watch — new names ACTIVE, ON TOP, WITH CHARTS (2026-11-19, watch-newest spec §3.4, WP-FE-board).
 * Ajay: "When I add a new ticket they are gettinf added in to que but not active … charts are not loading I amhaving to
 * click on the chips again". The real board, fetch stubbed, fake clocks:
 *   (a)–(c) the join rule by time (`ggw.pickAt`) and by `ggw.seen`, never writing pickAt on mount;
 *   (d) HIS view actions stamp pickAt; (e)/(e2) 🤖 potentials never join, 🎯 A+ does (and at THE load it turns A+);
 *   (f)/(g) a box add / re-add is joined (or its page shown), outlined and scrolled to ONCE;
 *   (h) a page open outlines only a name of his this browser has not shown yet — a reopen outlines nothing;
 *   (i)/(i2) the pages anchor (HIS CALL #6); (j)/(k)/(k2) the pending poll fills the charts, the late poll out of window
 *   only; (l) a stale partial never overwrites a newer board; (m) the DOM order is the served order. NEGATIVES throughout. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GGW_PATH, GGW_PICK_AT_KEY, GGW_PICK_KEY, GGW_SEEN_KEY } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = fixture as any;
const H = 3600_000;
const NOW = Date.parse('2026-11-19T15:00:00.000Z');
const iso = (ms: number) => new Date(ms).toISOString().replace('Z', '+00:00');
const AUTO = (why = 'potential') => ({ tag: '🤖', text: '🤖 auto', why });
const APLUS = { tag: '🎯', text: '🎯 A+', title: null, items: [] };

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
/** A light row (the no_prints row, no charts) renamed — or the ok row with its 3 charts when `ok`. */
function rowOf(sym: string, o: Record<string, unknown> = {}, ok = false): any {
  const base = clone(RAW.rows[ok ? 0 : 2]);
  base.symbol = sym;
  if (typeof base.text === 'string') base.text = base.text.split('XYZQ').join(sym);
  return { ...base, auto: null, aplus: null, added_at: null, ...o };
}
function boardOf(rows: any[], o: Record<string, unknown> = {}): any {
  const b = clone(RAW);
  b.rows = rows;
  b.symbols = rows.filter((r) => !r.auto).map((r) => r.symbol);
  b.refresh_sec = 0;
  b.next_window_sec = null;
  delete b.pending_poll_sec;
  delete b.pending_wait_max_sec;
  return { ...b, ...o };
}
const res = (body: unknown) => ({ ok: true, json: async () => body }) as unknown as Response;

type Call = { url: string; method: string };
let calls: Call[] = [];
let serve: () => any = () => boardOf([]);
let serveRows: ((syms: string[]) => any) | null = null;
let onWrite: (method: string, sym: string) => any = () => ({ state: 'added', symbols: [], symbol: null, text: null });
let scrolled: string[] = [];
let loc = '';
function Probe() { loc = useLocation().search; return null; }
const q = () => new URLSearchParams(loc);
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
const tick = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

async function mount(search = '') {
  vi.stubGlobal('matchMedia', (qq: string) => ({ matches: false, media: qq, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method || 'GET').toUpperCase();
    calls.push({ url, method });
    if (method !== 'GET' && url.includes('/chart-maps/gajjala-watch/symbols/')) {
      return onWrite(method, decodeURIComponent(url.split('/').pop() as string));
    }
    const qs = url.split('?symbols=')[1];
    if (url.includes(GGW_PATH + '?symbols=') && qs != null) {
      const syms = decodeURIComponent(qs).split(',');
      return serveRows ? serveRows(syms) : res({ ...serve(), rows: serve().rows.filter((r: any) => syms.includes(r.symbol)) });
    }
    return res(serve());
  }));
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala_watch${search}`]}><GajjalaWatchBoard /><Probe /></MemoryRouter>);
  for (let i = 0; i < 4; i += 1) await flush();
  return r.container;
}
const tile = (c: HTMLElement, s: string) => c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement | null;
const isShown = (c: HTMLElement, s: string) => !!tile(c, s) && !tile(c, s)!.hidden;
const outlined = (c: HTMLElement) => Array.from(c.querySelectorAll('.ggw-tile-focus')).map((t) => t.getAttribute('data-testid'));
const rowPolls = () => calls.filter((x) => x.method === 'GET' && x.url.includes(GGW_PATH + '?symbols='));
const fullGets = () => calls.filter((x) => x.method === 'GET' && x.url.endsWith(GGW_PATH));
const store = () => window.localStorage;
function seed(o: { seen?: string[]; pickAt?: number; pick?: string[] }) {
  if (o.seen) store().setItem(GGW_SEEN_KEY, o.seen.join(','));
  if (o.pickAt != null) store().setItem(GGW_PICK_AT_KEY, String(o.pickAt));
  if (o.pick) store().setItem(GGW_PICK_KEY, o.pick.join(','));
}
async function boxAdd(c: HTMLElement, sym: string) {
  const input = c.querySelector('input.ggw-input') as HTMLInputElement;
  fireEvent.change(input, { target: { value: sym } });
  fireEvent.submit(input.closest('form')!);
  for (let i = 0; i < 5; i += 1) await flush();
}

const origScroll = (Element.prototype as any).scrollIntoView;
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
  vi.stubGlobal('localStorage', memStorage());
  calls = [];
  serveRows = null;
  scrolled = [];
  (Element.prototype as any).scrollIntoView = function (this: HTMLElement) { if (this.id) scrolled.push(this.id); };
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  (Element.prototype as any).scrollIntoView = origScroll;
});

describe('🆕 the join rule (his names + 🎯 A+, by time or by seen)', { timeout: 20000 }, () => {
  it('(a) his URL pick + pickAt T: a row of his added after T joins, first in show=, and is shown — NEGATIVE: an older seen row stays hidden', async () => {
    const T = NOW - 2 * H;
    seed({ seen: ['A', 'B', 'X', 'OLD'], pickAt: T });
    serve = () => boardOf([rowOf('X', { added_at: iso(NOW - H) }), rowOf('A'), rowOf('B'), rowOf('OLD', { added_at: iso(NOW - 3 * H) })]);
    const c = await mount('&per=2&show=A');
    expect(q().get('show')).toBe('X,A');
    expect(isShown(c, 'X')).toBe(true);
    expect(isShown(c, 'A')).toBe(true);
    expect(isShown(c, 'OLD')).toBe(false);                               // hidden on purpose: he left it out after seeing it
    expect(isShown(c, 'B')).toBe(false);
  });
  it('(b) a bookmark show= ≠ the stored pick, pickAt older than X → X joins; NEGATIVE: ggw.pickAt is NOT rewritten on mount', async () => {
    const T = NOW - 2 * H;
    seed({ seen: ['A', 'B', 'X'], pickAt: T, pick: ['B'] });
    serve = () => boardOf([rowOf('X', { added_at: iso(NOW - H) }), rowOf('A'), rowOf('B')]);
    const c = await mount('&per=2&show=A');
    expect(q().get('show')).toBe('X,A');
    expect(isShown(c, 'X')).toBe(true);
    expect(store().getItem(GGW_PICK_AT_KEY)).toBe(String(T));
  });
  it('(c) a cold link (no pickAt, no seen): added 1 h ago joins, 30 h ago does not — NEGATIVE: pickAt stays unset, nothing outlined or scrolled', async () => {
    serve = () => boardOf([rowOf('N1', { added_at: iso(NOW - H) }), rowOf('A'), rowOf('N30', { added_at: iso(NOW - 30 * H) })]);
    const c = await mount('&per=2&show=A');
    expect(q().get('show')).toBe('N1,A');
    expect(isShown(c, 'N1')).toBe(true);
    expect(isShown(c, 'N30')).toBe(false);
    expect(store().getItem(GGW_PICK_AT_KEY)).toBeNull();
    expect(outlined(c)).toEqual([]);
    expect(scrolled).toEqual([]);
  });
  it('(d) a ticker toggle, a page move and a per-screen change write ggw.pickAt = now — NEGATIVE: the activation pass alone never does', async () => {
    seed({ seen: ['A', 'B', 'C'] });
    serve = () => boardOf([rowOf('D', { added_at: iso(NOW - H) }), rowOf('A'), rowOf('B'), rowOf('C')]);
    await mount('&per=2');
    expect(store().getItem(GGW_PICK_AT_KEY)).toBeNull();                 // D joined nothing (pages) and pickAt was never written
    vi.setSystemTime(NOW + 5_000);
    fireEvent.click(screen.getByTestId('ggw-pager-A'));
    expect(store().getItem(GGW_PICK_AT_KEY)).toBe(String(NOW + 5_000));
    store().removeItem(GGW_PICK_AT_KEY);
    vi.setSystemTime(NOW + 6_000);
    fireEvent.click(screen.getByTestId('ggw-layout-2'));
    expect(store().getItem(GGW_PICK_AT_KEY)).toBe(String(NOW + 6_000));
    store().removeItem(GGW_PICK_AT_KEY);
    vi.setSystemTime(NOW + 7_000);
    fireEvent.click(screen.getByTestId('ggw-pager-next'));
    expect(store().getItem(GGW_PICK_AT_KEY)).toBe(String(NOW + 7_000));
  });
  it('(e) 🤖 not force-activated: a potential new by seen AND time stays out; a 🎯 A+ seat / tag joins — NEGATIVE: never outlined or scrolled', async () => {
    seed({ seen: ['A'], pickAt: NOW - 2 * H });
    const at = iso(NOW - H);
    serve = () => boardOf([rowOf('A'), rowOf('POT', { auto: AUTO(), added_at: at }),
      rowOf('ASEAT', { auto: AUTO('aplus'), added_at: at }), rowOf('ATAG', { auto: AUTO(), aplus: APLUS, added_at: at })]);
    const c = await mount('&per=2&show=A');
    expect(q().get('show')).toBe('ASEAT,ATAG,A');
    expect(isShown(c, 'POT')).toBe(false);
    expect(isShown(c, 'ASEAT')).toBe(true);
    expect(outlined(c)).toEqual([]);
    expect(scrolled).toEqual([]);
  });
  it('(e2) [C5] a 🤖 potential seated after pickAt turns 🎯 A+ in place → it joins at THAT load', async () => {
    seed({ seen: ['A', 'POT'], pickAt: NOW - 2 * H });
    let v = 1;
    const at = iso(NOW - H);
    serve = () => boardOf([rowOf('A'), rowOf('POT', { auto: AUTO(), added_at: at, ...(v === 2 ? { aplus: APLUS } : {}) })],
      { refresh_sec: 60 });
    const c = await mount('&per=2&show=A');
    expect(q().get('show')).toBe('A');
    expect(isShown(c, 'POT')).toBe(false);
    v = 2;
    await tick(60_500);
    expect(q().get('show')).toBe('POT,A');
    expect(isShown(c, 'POT')).toBe(true);
  });
  it('(e2) NEGATIVE: a 🤖 potential that stays a potential is NOT joined when his next ➕ of another name reloads the board', async () => {
    seed({ seen: ['A', 'POT'], pickAt: NOW - 2 * H });
    let v = 1;
    const pot = () => rowOf('POT', { auto: AUTO(), added_at: iso(NOW - H) });
    serve = () => boardOf(v === 1 ? [rowOf('A'), pot()] : [rowOf('NEW', { added_at: iso(NOW) }), rowOf('A'), pot()]);
    onWrite = () => { v = 2; return res({ state: 'added', symbols: [], symbol: 'NEW', text: 'NEW added' }); };
    const c = await mount('&per=2&show=A');
    await boxAdd(c, 'NEW');
    expect(q().get('show')).toBe('NEW,A');
    expect(isShown(c, 'POT')).toBe(false);
  });
});

describe('🆕 the box add and the first load', { timeout: 20000 }, () => {
  it('(f) pick mode: ➕ NEW → NEW first in show=, shown, outlined alone, scrolled ONCE — NEGATIVE: the next refresh scrolls nothing more', async () => {
    seed({ seen: ['A', 'B'], pickAt: NOW });
    let v = 1;
    serve = () => (v === 1 ? boardOf([rowOf('A'), rowOf('B')])
      : boardOf([rowOf('NEW', { state: 'pending', text: '⏳ reading now', added_at: iso(NOW) }), rowOf('A'), rowOf('B')],
        { refresh_sec: 60, pending_poll_sec: 5, pending_wait_max_sec: 90 }));
    onWrite = () => { v = 2; return res({ state: 'added', symbols: [], symbol: 'NEW', text: 'NEW added' }); };
    const c = await mount('&per=2&show=A');
    await boxAdd(c, 'new');
    expect(q().get('show')).toBe('NEW,A');
    expect(isShown(c, 'NEW')).toBe(true);
    expect(outlined(c)).toEqual(['ggw-tile-NEW']);
    expect(scrolled).toEqual(['ggw-NEW']);
    await tick(61_000);
    expect(scrolled).toEqual(['ggw-NEW']);
    expect(store().getItem(GGW_PICK_AT_KEY)).toBe(String(NOW));          // NEGATIVE: a box add never stamps pickAt
  });
  it('(g) PAGES view on page 2: ➕ NEW → the page moves to NEW\'s page (1)', async () => {
    seed({ seen: ['A', 'B', 'C', 'D'] });
    let v = 1;
    const base = () => [rowOf('A'), rowOf('B'), rowOf('C'), rowOf('D')];
    serve = () => boardOf(v === 1 ? base() : [rowOf('NEW', { added_at: iso(NOW) }), ...base()]);
    onWrite = () => { v = 2; return res({ state: 'added', symbols: [], symbol: 'NEW', text: 'NEW added' }); };
    const c = await mount('&per=2&page=2');
    expect(isShown(c, 'C')).toBe(true);
    await boxAdd(c, 'NEW');
    expect(isShown(c, 'NEW')).toBe(true);
    expect(isShown(c, 'A')).toBe(true);
    expect(q().has('page')).toBe(false);
    expect(q().has('show')).toBe(false);
    expect(outlined(c)).toEqual(['ggw-tile-NEW']);
    expect(scrolled).toEqual(['ggw-NEW']);
  });
  it('(g) ➕ again on a hidden name ("already") → it joins, outlines and scrolls; the pick is not cleared', async () => {
    seed({ seen: ['A', 'B'], pickAt: NOW });
    let v = 1;
    serve = () => boardOf(v === 1 ? [rowOf('A'), rowOf('B')] : [rowOf('B', { added_at: iso(NOW + 1_000) }), rowOf('A')]);
    onWrite = () => { v = 2; return res({ state: 'already', symbols: [], symbol: 'B', text: 'B is already on your watch' }); };
    const c = await mount('&per=2&show=A');
    expect(isShown(c, 'B')).toBe(false);
    await boxAdd(c, 'B');
    expect(q().get('show')).toBe('B,A');
    expect(isShown(c, 'B')).toBe(true);
    expect(outlined(c)).toEqual(['ggw-tile-B']);
    expect(scrolled).toEqual(['ggw-B']);
  });
  it('(h) [C6] a first load where seen lacks his X (a card ➕) → X outlined + scrolled once, pages → its page — NEGATIVE: a reopen does nothing', async () => {
    seed({ seen: ['A', 'B', 'C'], pickAt: NOW - 48 * H });
    serve = () => boardOf([rowOf('X', { added_at: iso(NOW - H) }), rowOf('A'), rowOf('B'), rowOf('C')]);
    let c = await mount('&per=2&page=2');
    expect(isShown(c, 'X')).toBe(true);
    expect(q().has('page')).toBe(false);
    expect(outlined(c)).toEqual(['ggw-tile-X']);
    expect(scrolled).toEqual(['ggw-X']);
    cleanup();
    scrolled = [];
    c = await mount('&per=2&page=2');
    expect(outlined(c)).toEqual([]);
    expect(scrolled).toEqual([]);
    expect(q().get('page')).toBe('2');
    expect(isShown(c, 'X')).toBe(false);
  });
  it('(h) pick mode: first open outlines X; NEGATIVE: the reopen keeps X joined (time rule) without an outline or a scroll', async () => {
    seed({ seen: ['A', 'B'], pickAt: NOW - 2 * H });
    serve = () => boardOf([rowOf('X', { added_at: iso(NOW - H) }), rowOf('A'), rowOf('B')]);
    let c = await mount('&per=2&show=A');
    expect(q().get('show')).toBe('X,A');
    expect(outlined(c)).toEqual(['ggw-tile-X']);
    expect(scrolled).toEqual(['ggw-X']);
    cleanup();
    scrolled = [];
    c = await mount('&per=2&show=A');
    expect(q().get('show')).toBe('X,A');
    expect(isShown(c, 'X')).toBe(true);
    expect(outlined(c)).toEqual([]);
    expect(scrolled).toEqual([]);
  });
});

describe('🆕 the pages anchor', { timeout: 20000 }, () => {
  const four = () => [rowOf('A'), rowOf('B'), rowOf('C'), rowOf('D')];
  it('(i) page 2 shows C,D; a refresh with a new row on top → C still shown', async () => {
    seed({ seen: ['A', 'B', 'C', 'D'] });
    let v = 1;
    serve = () => boardOf(v === 1 ? four() : [rowOf('X', { added_at: iso(NOW) }), ...four()], { refresh_sec: 60 });
    const c = await mount('&per=2&page=2');
    expect(['A', 'B', 'C', 'D'].filter((s) => isShown(c, s))).toEqual(['C', 'D']);
    v = 2;
    await tick(60_500);
    expect(isShown(c, 'C')).toBe(true);
  });
  it('(i) a refresh with a row above removed → C still shown', async () => {
    seed({ seen: ['A', 'B', 'C', 'D'] });
    let v = 1;
    serve = () => boardOf(v === 1 ? four() : four().slice(1), { refresh_sec: 60 });
    const c = await mount('&per=2&page=2');
    v = 2;
    await tick(60_500);
    expect(isShown(c, 'C')).toBe(true);
  });
  it('(i) NEGATIVE: in pick mode the anchor never moves the page', async () => {
    seed({ seen: ['A', 'B', 'C', 'D'] });
    let v = 1;
    serve = () => boardOf(v === 1 ? four() : [rowOf('X', { added_at: iso(NOW) }), rowOf('Y', { added_at: iso(NOW) }), ...four()],
      { refresh_sec: 60 });
    await mount('&per=2&page=2');
    fireEvent.click(screen.getByTestId('ggw-pager-A'));                  // pick mode: A, C, D
    expect(q().has('show')).toBe(true);
    v = 2;
    await tick(60_500);
    fireEvent.click(screen.getByTestId('ggw-layout-2'));                 // back to the pages from the STORED page
    expect(q().get('page')).toBe('2');                                   // an anchor move would have made it 3
  });
  it('(i2) HIS CALL #6 default: page 2 open, a card ➕ X arrives at index 0 → the page stays 2 and X is not shown', async () => {
    // HIS CALL #6 (spec §7): a card ➕ while the Watch tab is open on page 2+ lands on page 1, unseen, chip unlit.
    seed({ seen: ['A', 'B', 'C', 'D'] });
    let v = 1;
    serve = () => boardOf(v === 1 ? four() : [rowOf('X', { added_at: iso(NOW) }), ...four()], { refresh_sec: 60 });
    const c = await mount('&per=2&page=2');
    v = 2;
    await tick(60_500);
    expect(q().get('page')).toBe('2');
    expect(isShown(c, 'X')).toBe(false);
    expect(outlined(c)).toEqual([]);
    expect(scrolled).toEqual([]);
  });
});

describe('🆕 the pending tile fills by itself', { timeout: 20000 }, () => {
  const pendRow = (o: Record<string, unknown> = {}) => rowOf('AMD', { ...clone(RAW.rows[1]), auto: null, aplus: null,
    added_at: iso(NOW), ...o });
  const pendBoard = (o: Record<string, unknown> = {}) => boardOf([rowOf('OMH', {}, true), pendRow()],
    { pending_poll_sec: 5, pending_wait_max_sec: 90, ...o });
  it('(j) a pending row → ?symbols= every 5 s; at 5.1 s it answers ok → 3 charts in that tile, no click', async () => {
    serve = () => pendBoard();
    serveRows = () => res(boardOf([rowOf('AMD', {}, true)]));
    const c = await mount();
    expect(tile(c, 'AMD')!.querySelectorAll('svg')).toHaveLength(0);
    await tick(5_100);
    expect(rowPolls()).toHaveLength(1);
    expect(rowPolls()[0].url).toContain('symbols=AMD');
    expect(tile(c, 'AMD')!.getAttribute('data-state')).toBe('ok');
    expect(tile(c, 'AMD')!.querySelectorAll('svg')).toHaveLength(3);
  });
  it('(k) out of window: past the cap the tile prints the served late_text and a ?symbols= poll still goes out every 60 s', async () => {
    const LATE = '⏳ still reading — not read yet; this tile checks again every 60 s';
    serve = () => pendBoard({ pending_late_poll_sec: 60 });
    serveRows = () => res(boardOf([pendRow({ late_text: LATE })], { pending_poll_sec: 5, pending_wait_max_sec: 90,
      pending_late_poll_sec: 60 }));
    const c = await mount();
    expect(tile(c, 'AMD')!.textContent).not.toContain(LATE);
    await tick(90_500);
    expect(tile(c, 'AMD')!.textContent).toContain(LATE);
    const n = rowPolls().length;
    await tick(60_000);
    expect(rowPolls().length).toBe(n + 1);
    await tick(60_000);
    expect(rowPolls().length).toBe(n + 2);
    expect(fullGets()).toHaveLength(1);
  });
  it('(k) NEGATIVE: without the served key (an older server) → the poll stops at the cap, as before', async () => {
    serve = () => pendBoard();
    const c = await mount();
    await tick(90_500);
    const n = rowPolls().length;
    await tick(600_000);
    expect(rowPolls().length).toBe(n);
    expect(tile(c, 'AMD')!.getAttribute('data-state')).toBe('pending');
  });
  it('(k2) [C7] NEGATIVE in window: refresh 60 + late poll 60 → late_text prints, NO ?symbols= GET after the cap, only the full GET', async () => {
    const LATE = '⏳ still reading — not read yet; this tile checks again every 60 s';
    serve = () => boardOf([rowOf('OMH', {}, true), pendRow({ late_text: LATE })],
      { refresh_sec: 60, pending_poll_sec: 5, pending_wait_max_sec: 90, pending_late_poll_sec: 60 });
    const c = await mount();
    await tick(90_500);
    expect(tile(c, 'AMD')!.textContent).toContain(LATE);
    const n = rowPolls().length;
    const f = fullGets().length;
    await tick(180_000);
    expect(rowPolls().length).toBe(n);
    expect(fullGets().length).toBe(f + 3);
  });
  it('(l) NEGATIVE: a pending poll answer that lands after a newer full board is dropped — the tile stays ok', async () => {
    let v = 1;
    let release: (r: Response) => void = () => {};
    serve = () => boardOf([rowOf('OMH', {}, true), v === 1 ? pendRow() : rowOf('AMD', {}, true)],
      { refresh_sec: 60, pending_poll_sec: 5, pending_wait_max_sec: 90 });
    serveRows = () => new Promise<Response>((r) => { release = r; });
    const c = await mount();
    await tick(5_100);
    expect(rowPolls()).toHaveLength(1);
    v = 2;
    await tick(55_000);
    expect(tile(c, 'AMD')!.getAttribute('data-state')).toBe('ok');
    release(res(boardOf([pendRow()], { pending_poll_sec: 5, pending_wait_max_sec: 90 })));
    for (let i = 0; i < 4; i += 1) await flush();
    expect(tile(c, 'AMD')!.getAttribute('data-state')).toBe('ok');
    expect(tile(c, 'AMD')!.querySelectorAll('svg')).toHaveLength(3);
  });
});

describe('🆕 order', { timeout: 20000 }, () => {
  it('(m) the DOM tile order == the served rows order (newest first, as served)', async () => {
    serve = () => boardOf([rowOf('NVDA', { added_at: iso(NOW) }), rowOf('OMH', { added_at: iso(NOW - H) }), rowOf('XYZQ')]);
    const c = await mount('&per=9');
    expect(Array.from(c.querySelectorAll('.ggw-grid .ggw-tile')).map((t) => t.getAttribute('data-testid')))
      .toEqual(['ggw-tile-NVDA', 'ggw-tile-OMH', 'ggw-tile-XYZQ']);
  });
  it('(m) NEGATIVE: an old server (no added_at anywhere) behaves as before — a seen list + a link pick join nothing, pickAt unwritten', async () => {
    const syms = RAW.rows.map((r: any) => r.symbol) as string[];
    seed({ seen: syms });
    serve = () => clone(RAW);
    const c = await mount(`&per=1&show=${syms[1]}`);
    expect(syms.filter((s) => isShown(c, s))).toEqual([syms[1]]);
    expect(q().get('show')).toBe(syms[1]);
    expect(store().getItem(GGW_PICK_AT_KEY)).toBeNull();
    expect(outlined(c)).toEqual([]);
  });
});
