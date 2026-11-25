/* ▦ 👀 Gajjala's Watch — "per screen" = columns, every tile in one scroll (2026-11-25, spec ggwcols §3.3 / §3.4, WP board).
 * Ajay: "When I say 2 per screen I mean 2 columns do not remove other, I need other to be avtive while I scroll." ·
 * "Can you fix that instead of removing the other?"
 *
 * The REAL board over the 30-row 2026-11-17 fixture (12 of his names + 18 🤖). jsdom has no layout, no
 * IntersectionObserver, no scrollIntoView, no localStorage: each is stubbed; where geometry matters the rects are mocked
 * (board top 0, grid top GRID_TOP, rows ROW_H tall, the tiles' scroll-margin-top INSET). The bus is hand-driven.
 * NEGATIVES: no tile is ever hidden without a chip filter; the greyed ◀ ▶ change nothing; never an empty board; × never
 * toggles; a key only scrolls (no filter clear, no ggw.pickAt, no link write); typing / ⤢ / a phone / 0 × 0 rects → the
 * keys do nothing; a far tile is not redrawn by a batch (fail-open without an observer); the hold never scrolls at the
 * board top, for its own tile removed, for a box add, or on a live batch; `page=` is never honoured nor written. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import autoFixture from './__fixtures__/gajjala_watch_board_auto_2026_11_17.json';

const busHandlers = new Map<string, Set<(e: any) => void>>();
const bus = { subs: 0 };
vi.mock('../lib/eventBus', () => ({
  subscribe: (type: string, fn: (e: any) => void) => {
    bus.subs += 1;
    let s = busHandlers.get(type);
    if (!s) { s = new Set(); busHandlers.set(type, s); }
    s.add(fn);
    return () => { busHandlers.get(type)?.delete(fn); };
  },
}));

import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GG_UPDATE_EVENT } from '../lib/cardLive';
import {
  GGW_LAYOUT_ORDER, GGW_LAYOUTS, GGW_LIVE_PATH, GGW_PATH, GGW_PHONE_MQ, GGW_PICK_AT_KEY, GGW_PICK_KEY, GGW_SEEN_KEY, GGW_TAB,
  ggwFitRowHeight, type GgwLayout,
} from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = autoFixture as any;
const SYMS: string[] = RAW.rows.map((r: any) => r.symbol);
const N = SYMS.length;
const GRID_TOP = 200;
const ROW_H = 500;
const INSET = 60;

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
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');

/* ── the stubs ─────────────────────────────────────────────────────────────────────────────────────────────── */
type Call = { url: string; method: string; body?: string };
let calls: Call[] = [];
let boardNow: () => any = () => clone(RAW);
let delAnswer: () => Promise<any> = () => new Promise(() => {});            // a DELETE that never answers
let postAnswer: () => any = () => ({ state: 'added', symbol: 'NEWX', symbols: [], text: 'served added' });
const liveAnswer = () => ({ state: 'ok', stream: { on: true, word: 'served word', state: 'live' }, tab: GGW_TAB, symbols: [] });
let scrolls: Array<{ id: string; testid: string | null; arg: any }> = [];
let loc = '';
function Probe() { loc = useLocation().search; return null; }
const q = () => new URLSearchParams(loc);

function stubAll(phone = false) {
  vi.stubGlobal('localStorage', memStorage());
  vi.stubGlobal('matchMedia', (m: string) => ({
    matches: phone && m === GGW_PHONE_MQ, media: m, addEventListener: () => {}, removeEventListener: () => {},
  }));
  vi.stubGlobal('EventSource', class {});
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method || 'GET').toUpperCase();
    calls.push({ url, method, body: init?.body as string | undefined });
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) return { ok: true, json: async () => liveAnswer() } as unknown as Response;
    if (method === 'DELETE') return delAnswer();
    if (method === 'POST') return { ok: true, json: async () => postAnswer() } as unknown as Response;
    return { ok: true, json: async () => boardNow() } as unknown as Response;
  }));
  scrolls = [];
  (Element.prototype as any).scrollIntoView = function (this: HTMLElement, arg: any) {
    scrolls.push({ id: this.id, testid: this.getAttribute('data-testid'), arg });
  };
  vi.spyOn(window, 'scrollBy').mockImplementation(() => {});
}
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
async function mount(o: { url?: string } = {}) {
  const r = render(<MemoryRouter initialEntries={[o.url ?? '/chart-maps?tab=gajjala_watch']}><GajjalaWatchBoard /><Probe /></MemoryRouter>);
  for (let i = 0; i < 3; i += 1) await flush();
  return r.container;
}
const refresh = async () => {
  await act(async () => { await vi.advanceTimersByTimeAsync((RAW.refresh_sec || 60) * 1000 + 10); });
  for (let i = 0; i < 3; i += 1) await flush();
};
const grid = (c: HTMLElement) => c.querySelector('.ggw-board > .ggw-grid') as HTMLElement;
const tiles = (c: HTMLElement) => Array.from(grid(c).querySelectorAll(':scope > .ggw-tile')) as HTMLElement[];
const tileOf = (c: HTMLElement, s: string) => c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement | null;
const hiddenN = (c: HTMLElement) => tiles(c).filter((t) => t.hidden).length;
const shownSyms = (c: HTMLElement) => tiles(c).filter((t) => !t.hidden).map((t) => t.id.slice(4));
const chip = (s: string) => screen.getByTestId(`ggw-pager-${s}`);
const lit = () => SYMS.filter((s) => chip(s).getAttribute('aria-pressed') === 'true');
const scrollBy = () => (window.scrollBy as unknown as ReturnType<typeof vi.fn>);

/* the geometry: board top 0, grid top GRID_TOP, visible tiles row-major at ROW_H, minus the window's scroll y */
const view = { y: 0 };
const rectCalls = { tiles: 0 };
function rect(top: number, w: number, h: number): DOMRect {
  return { top, bottom: top + h, left: 0, right: w, width: w, height: h, x: 0, y: top, toJSON: () => ({}) } as DOMRect;
}
function mockGeometry() {
  view.y = 0;
  rectCalls.tiles = 0;
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    const par = this.parentElement;
    if (this.classList.contains('ggw-board')) return rect(0 - view.y, 800, 20_000);
    if (this.classList.contains('ggw-grid') && !this.classList.contains('ggw-grid--stretch')) return rect(GRID_TOP - view.y, 800, 18_000);
    if (this.classList.contains('ggw-tile') && par && par.classList.contains('ggw-grid') && !par.classList.contains('ggw-grid--stretch')) {
      rectCalls.tiles += 1;
      if (this.hidden) return rect(0, 0, 0);
      const vis = Array.from(par.children).filter((e) => e.classList.contains('ggw-tile') && !(e as HTMLElement).hidden);
      const cols = Number((/ggw-grid--cols(\d)/.exec(par.className) || [])[1] || 1);
      const k = vis.indexOf(this);
      return rect(GRID_TOP + Math.floor(k / cols) * ROW_H - view.y, 400, ROW_H);
    }
    return rect(0, 0, 0);
  });
  const real = window.getComputedStyle.bind(window);
  vi.spyOn(window, 'getComputedStyle').mockImplementation((el: Element, pseudo?: string | null) => {
    const cs = real(el, pseudo);
    if (!el.classList.contains('ggw-tile')) return cs;
    return new Proxy(cs, {
      get: (t, k) => {
        if (k === 'scrollMarginTop') return `${INSET}px`;
        const v = (t as any)[k];
        return typeof v === 'function' ? v.bind(t) : v;
      },
    });
  });
}

/* a hand-driven IntersectionObserver */
const ios: FakeIO[] = [];
class FakeIO {
  cb: (e: any[]) => void; opts: any; targets: Element[] = [];
  constructor(cb: (e: any[]) => void, opts: any) { this.cb = cb; this.opts = opts; ios.push(this); }
  observe(el: Element) { this.targets.push(el); }
  unobserve() {}
  disconnect() { this.targets = []; }
  report(near: ReadonlyArray<string>) {
    act(() => { this.cb(this.targets.map((t) => ({ target: t, isIntersecting: near.includes(t.id.slice(4)) }))); });
  }
}

/* live axes on the server's own 04:00 grid (session 2026-11-13: 04:00 ET = 09:00 UTC) */
const START = Date.UTC(2026, 10, 13, 9, 0, 0) / 1000;
const FM: Record<string, number> = { '1m': 1, '3m': 3, '5m': 5 };
const at = (min: number, sec = 0) => START + min * 60 + sec;
function liveRaw() {
  const b = clone(RAW);
  for (const r of b.rows) for (const f of r.frames || []) { if (f.axis) { f.axis.start_epoch = START; f.axis.frame_min = FM[f.tf]; } }
  return b;
}
const emit = (quotes: Record<string, unknown>) => act(async () => {
  for (const fn of busHandlers.get(GG_UPDATE_EVENT) || []) fn({ type: GG_UPDATE_EVENT, ts: 0, payload: { kind: 'quotes', variant: GGW_TAB, quotes } });
});
const qt = (price: number, asOf: number) => ({ price, as_of_epoch: asOf, vs: null, size: 500 });
const svg1 = (root: ParentNode, s: string) => root.querySelector(`[data-testid="ggw-tile-${s}"] .ggw-frame[data-tf="1m"] svg`) as SVGSVGElement;
const html = (el: Element | null) => (el ? el.outerHTML : '');

beforeEach(() => {
  vi.useFakeTimers();
  busHandlers.clear();
  bus.subs = 0;
  ios.length = 0;
  boardNow = () => clone(RAW);
  delAnswer = () => new Promise(() => {});
  postAnswer = () => ({ state: 'added', symbol: 'NEWX', symbols: [], text: 'served added' });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  delete (Element.prototype as any).scrollIntoView;
  document.body.style.overflow = '';
});

describe('▦ every tile in one grid', () => {
  it('1. pick 2 → all N tiles in the DOM, none hidden, two columns, ggw-grid--all', async () => {
    stubAll();
    const c = await mount();
    expect(N).toBeGreaterThan(2);                                              // not vacuous
    expect(tiles(c)).toHaveLength(N);
    expect(hiddenN(c)).toBe(0);
    expect(c.querySelectorAll('.ggw-tile[hidden]')).toHaveLength(0);
    expect(grid(c).dataset.layout).toBe('2');
    expect(grid(c).classList.contains('ggw-grid--cols2')).toBe(true);
    expect(grid(c).classList.contains('ggw-grid--all')).toBe(true);
  });

  it('2. picks 9 / 4 / 1 → 3 / 2 / 1 columns, 0 hidden; the fitted row height is the per-screen one (tile size unchanged)', async () => {
    stubAll();
    mockGeometry();
    const c = await mount();
    const want: Record<number, number> = { 9: 3, 4: 2, 1: 1, 2: 2 };
    for (const l of [9, 4, 1, 2] as GgwLayout[]) {
      fireEvent.click(screen.getByTestId(`ggw-layout-${l}`));
      await flush();
      expect(grid(c).classList.contains(`ggw-grid--cols${want[l]}`)).toBe(true);
      expect(hiddenN(c)).toBe(0);
      expect(tiles(c)).toHaveLength(N);
      expect(grid(c).style.getPropertyValue('--ggw-row-h'))
        .toBe(`${ggwFitRowHeight({ vh: window.innerHeight, top: GRID_TOP, below: 0, gap: 0 }, GGW_LAYOUTS[l].rows)}px`);
    }
  });

  it('3. the ticker row: every chip lit in every pick; ◀ ▶ greyed; no page count — NEGATIVE: the greyed ▶ changes nothing', async () => {
    stubAll();
    const c = await mount();
    for (const l of GGW_LAYOUT_ORDER) {
      fireEvent.click(screen.getByTestId(`ggw-layout-${l}`));
      expect(lit()).toEqual(SYMS);
      expect((screen.getByTestId('ggw-pager-prev') as HTMLButtonElement).disabled).toBe(true);
      expect((screen.getByTestId('ggw-pager-next') as HTMLButtonElement).disabled).toBe(true);
      expect(screen.queryByTestId('ggw-pager-at')).toBeNull();
    }
    const before = { shown: shownSyms(c), loc };
    fireEvent.click(screen.getByTestId('ggw-pager-next'));
    fireEvent.click(screen.getByTestId('ggw-pager-prev'));
    expect(shownSyms(c)).toEqual(before.shown);
    expect(loc).toBe(before.loc);
    expect(scrolls).toHaveLength(0);
  });

  it('4. chips: a tap hides exactly that name; again → no filter at all; all but one → one column; NEGATIVE: never empty, × never toggles, a per-screen tap clears', async () => {
    stubAll();
    const c = await mount();
    const X = SYMS[5];
    fireEvent.click(chip(X));
    expect(tiles(c).filter((t) => t.hidden).map((t) => t.id)).toEqual([`ggw-${X}`]);
    expect(chip(X).getAttribute('aria-pressed')).toBe('false');
    expect(shownSyms(c)).toHaveLength(N - 1);
    expect(q().get('show')!.split(',')).toEqual(SYMS.filter((s) => s !== X));
    fireEvent.click(chip(X));                                                   // the last unlit chip lit → no filter
    expect(hiddenN(c)).toBe(0);
    expect(grid(c).dataset.pick).toBeUndefined();
    expect(q().has('show')).toBe(false);
    expect(window.localStorage.getItem(GGW_PICK_KEY)).toBeNull();
    for (const s of SYMS.slice(1)) fireEvent.click(chip(s));
    expect(shownSyms(c)).toEqual([SYMS[0]]);
    expect(grid(c).classList.contains('ggw-grid--cols1')).toBe(true);
    expect(grid(c).dataset.pick).toBe('1');
    fireEvent.click(chip(SYMS[0]));                                             // the last one off → every tile back
    expect(hiddenN(c)).toBe(0);
    expect(shownSyms(c)).toEqual(SYMS);
    expect(grid(c).dataset.pick).toBeUndefined();
    /* × never toggles: the name leaves at once, nothing else hides, no filter appears */
    fireEvent.click(screen.getByTestId(`ggw-pager-x-${SYMS[2]}`));
    expect(tileOf(c, SYMS[2])).toBeNull();
    expect(hiddenN(c)).toBe(0);
    expect(grid(c).dataset.pick).toBeUndefined();
    /* a per-screen tap clears a filter */
    fireEvent.click(chip(SYMS[0]));
    expect(grid(c).dataset.pick).toBe(String(N - 2));
    fireEvent.click(screen.getByTestId('ggw-layout-9'));
    expect(grid(c).dataset.pick).toBeUndefined();
    expect(hiddenN(c)).toBe(0);
  });

  /* refix (verifier MEDIUM): the all-on rule in the activation pass too — one 🤖 chip off, then the machine drops that
   * name: the pick covers every listed name → no filter (no data-pick, no show=, ggw.pick gone), so the next 🤖 served
   * arrives shown with its chip lit. */
  const BOTS = SYMS.filter((_s, i) => RAW.rows[i].auto != null);
  const newBot = (sym: string) => { const r = clone(RAW.rows[SYMS.indexOf(BOTS[1])]); r.symbol = sym; return r; };
  it('4b. one 🤖 chip off, then that name leaves the list → no filter at all; the next 🤖 served is shown and lit', async () => {
    stubAll();
    const c = await mount();
    expect(BOTS.length).toBeGreaterThan(2);                                     // not vacuous
    const X = BOTS[0];
    fireEvent.click(chip(X));
    expect(grid(c).dataset.pick).toBe(String(N - 1));
    expect(window.localStorage.getItem(GGW_PICK_KEY)).not.toBeNull();
    boardNow = () => { const b = clone(RAW); b.rows = b.rows.filter((r: any) => r.symbol !== X); return b; };
    await refresh();
    expect(tileOf(c, X)).toBeNull();
    expect(hiddenN(c)).toBe(0);
    expect(grid(c).dataset.pick).toBeUndefined();
    expect(q().has('show')).toBe(false);
    expect(window.localStorage.getItem(GGW_PICK_KEY)).toBeNull();
    boardNow = () => { const b = clone(RAW); b.rows = b.rows.filter((r: any) => r.symbol !== X); b.rows.push(newBot('NEWBOT')); return b; };
    await refresh();
    expect(tileOf(c, 'NEWBOT')).not.toBeNull();
    expect(tileOf(c, 'NEWBOT')!.hidden).toBe(false);
    expect(screen.getByTestId('ggw-pager-NEWBOT').getAttribute('aria-pressed')).toBe('true');
    expect(hiddenN(c)).toBe(0);
  });

  it('4b. NEGATIVE: two chips off, only one leaves → the filter stays (the other still hidden, show= kept); a lit name leaving keeps the filter', async () => {
    stubAll();
    const c = await mount();
    const [X, Z, L] = [BOTS[0], BOTS[2], BOTS[3]];
    fireEvent.click(chip(X));
    fireEvent.click(chip(Z));
    boardNow = () => { const b = clone(RAW); b.rows = b.rows.filter((r: any) => r.symbol !== X); return b; };
    await refresh();
    expect(tiles(c).filter((t) => t.hidden).map((t) => t.id)).toEqual([`ggw-${Z}`]);
    expect(chip(Z).getAttribute('aria-pressed')).toBe('false');
    expect(grid(c).dataset.pick).toBe(String(N - 2));
    expect(q().get('show')!.split(',')).not.toContain(Z);
    expect(window.localStorage.getItem(GGW_PICK_KEY)).not.toBeNull();
    /* a LIT name leaving the list: Z stays off, the filter stays */
    boardNow = () => { const b = clone(RAW); b.rows = b.rows.filter((r: any) => r.symbol !== X && r.symbol !== L); return b; };
    await refresh();
    expect(tileOf(c, L)).toBeNull();
    expect(tiles(c).filter((t) => t.hidden).map((t) => t.id)).toEqual([`ggw-${Z}`]);
    expect(grid(c).dataset.pick).toBe(String(N - 3));
    expect(q().has('show')).toBe(true);
  });

  /* refix LOW 2026-11-25: the cover-all rule (ggwCoverAll) on the box-add join too — the board refetch after an
   * "already" serves the SAME rows (no new add time → the load's join pass does not run), so only the box-add updater
   * sees it. Two / three of his names, show= the first, the rest already seen (no fresh join). */
  const OWN2 = SYMS.filter((_s, i) => RAW.rows[i].auto == null);
  const boardOfSyms = (syms: string[]) => () => {
    const b = clone(RAW);
    b.rows = syms.map((s) => (s === 'NEWBOT' ? newBot('NEWBOT') : clone(RAW.rows[SYMS.indexOf(s)])));
    return b;
  };
  async function boxAdd(c: HTMLElement, sym: string) {
    const input = c.querySelector('input.ggw-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: sym } });
    fireEvent.submit(input.closest('form')!);
    for (let i = 0; i < 5; i += 1) await flush();
  }
  it('4c. ➕ "already" on the ONE hidden name → the pick covers every name → no filter; the next 🤖 served is shown and lit', async () => {
    stubAll();
    const [A, B] = OWN2;
    window.localStorage.setItem(GGW_SEEN_KEY, [A, B].join(','));
    boardNow = boardOfSyms([A, B]);
    postAnswer = () => ({ state: 'already', symbol: B, symbols: [], text: `${B} is already on your watch` });
    const c = await mount({ url: `/chart-maps?tab=gajjala_watch&show=${A}` });
    expect(tileOf(c, B)!.hidden).toBe(true);                                    // not vacuous: B starts hidden
    expect(q().get('show')).toBe(A);
    await boxAdd(c, B);
    expect(q().has('show')).toBe(false);
    expect(window.localStorage.getItem(GGW_PICK_KEY)).toBeNull();
    expect(grid(c).dataset.pick).toBeUndefined();
    expect(hiddenN(c)).toBe(0);
    boardNow = boardOfSyms([A, B, 'NEWBOT']);
    await refresh();
    expect(tileOf(c, 'NEWBOT')).not.toBeNull();
    expect(tileOf(c, 'NEWBOT')!.hidden).toBe(false);
    expect(screen.getByTestId('ggw-pager-NEWBOT').getAttribute('aria-pressed')).toBe('true');
    expect(hiddenN(c)).toBe(0);
  });
  it('4c. NEGATIVE: ➕ "already" on one of TWO hidden names → the pick does not cover every name → kept (the other still hidden)', async () => {
    stubAll();
    const [A, B, C] = OWN2;
    window.localStorage.setItem(GGW_SEEN_KEY, [A, B, C].join(','));
    boardNow = boardOfSyms([A, B, C]);
    postAnswer = () => ({ state: 'already', symbol: B, symbols: [], text: `${B} is already on your watch` });
    const c = await mount({ url: `/chart-maps?tab=gajjala_watch&show=${A}` });
    await boxAdd(c, B);
    expect(q().get('show')).toBe(`${B},${A}`);
    expect(window.localStorage.getItem(GGW_PICK_KEY)).not.toBeNull();
    expect(tileOf(c, B)!.hidden).toBe(false);
    expect(tiles(c).filter((t) => t.hidden).map((t) => t.id)).toEqual([`ggw-${C}`]);
  });
  it('4c. source: ONE cover-all helper, called by all three pick updaters (toggle, the load\'s join pass, the box-add join)', async () => {
    const src = noComments(await readSource('src/components/GajjalaWatchBoard.tsx'));
    expect(src.split('const ggwCoverAll = (').length - 1).toBe(1);
    expect(src.split('ggwCoverAll(').length - 1).toBe(3);
    expect(src).toContain('setPick((cur) => ggwCoverAll(ggwJoinPick(cur, list, [s]), list))');
    expect(src).toContain('setPick(ggwCoverAll(ggwToggleShown(');
    expect(src).toContain('const next = ggwCoverAll(ggwJoinPick(');
    /* NEGATIVE: no second hand-rolled copy of the rule */
    expect(src).not.toContain('next.length >= list.length');
    expect(src).not.toMatch(/list\.every\(\(s\) => joined/);
  });
});

describe('▦ ← → scroll one screen row group', () => {
  it('5. → brings the next group\'s first tile under the strip, ← the previous one / the board top', async () => {
    stubAll();
    mockGeometry();
    const c = await mount();
    expect(window.innerHeight).toBeGreaterThan(GRID_TOP + ROW_H);              // group 0 whole in the window
    const last = () => scrolls[scrolls.length - 1];
    const smooth = { block: 'start', behavior: 'smooth' };
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(last()).toEqual({ id: `ggw-${SYMS[2]}`, testid: `ggw-tile-${SYMS[2]}`, arg: smooth });
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(last().testid).toBe('ggw-board');
    expect(last().arg).toEqual(smooth);
    view.y = GRID_TOP + ROW_H - INSET;                                           // group 1 aligned under the strip
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(last().id).toBe(`ggw-${SYMS[4]}`);
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(last().id).toBe(`ggw-${SYMS[0]}`);
    view.y = GRID_TOP + ROW_H + 200;                                             // inside group 1 → back to its start
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(last().id).toBe(`ggw-${SYMS[2]}`);
    expect(hiddenN(c)).toBe(0);                                                  // NEGATIVE: no tile hidden at any step
    expect(scrollBy()).not.toHaveBeenCalled();
  });

  it('5. NEGATIVE: typing, ⤢, plain jsdom rects → nothing; a key never clears a filter, stamps ggw.pickAt or writes the link', async () => {
    stubAll();
    const c = await mount();
    fireEvent.keyDown(document, { key: 'ArrowRight' });                         // 0 × 0 rects → nothing measured
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(scrolls).toHaveLength(0);
    cleanup();
    stubAll();
    mockGeometry();
    const d = await mount();
    fireEvent.keyDown(d.querySelector('.ggw-input') as HTMLInputElement, { key: 'ArrowRight' });
    expect(scrolls).toHaveLength(0);
    fireEvent.click(chip(SYMS[1]));                                             // (a chip tap brings the board top up)
    scrolls.length = 0;
    window.localStorage.removeItem(GGW_PICK_AT_KEY);
    const before = loc;
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(scrolls).toHaveLength(1);
    expect(grid(d).dataset.pick).toBe(String(N - 1));
    expect(window.localStorage.getItem(GGW_PICK_AT_KEY)).toBeNull();
    expect(loc).toBe(before);
    fireEvent.click(screen.getByTestId(`ggw-stretch-btn-${SYMS[0]}`));
    const n = scrolls.length;
    fireEvent.keyDown(document, { key: 'ArrowRight' });                         // ⤢ steps its own stock …
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(scrolls).toHaveLength(n);                                             // … the board never scrolls
    void c;
  });

  it('6. ?focus=SYM far down → scrolled to once; NEGATIVE: every other tile is still shown', async () => {
    stubAll();
    const far = SYMS[25];
    const c = await mount({ url: `/chart-maps?tab=gajjala_watch&focus=${far}` });
    expect(scrolls.filter((s) => s.id === `ggw-${far}`)).toHaveLength(1);
    expect(scrolls).toHaveLength(1);
    expect(hiddenN(c)).toBe(0);
    expect(tileOf(c, far)!.classList.contains('ggw-tile-focus')).toBe(true);
  });
});

describe('▦ unchanged around it', () => {
  it('7. phone: one column, no pick, ◀ ▶ off, no count, no ggw-grid--all — NEGATIVE: no observer, ← → nothing, no scrollBy', async () => {
    stubAll(true);
    vi.stubGlobal('IntersectionObserver', FakeIO);
    mockGeometry();
    boardNow = () => clone(RAW);
    const c = await mount();
    expect(screen.queryByTestId('ggw-layout')).toBeNull();
    expect((screen.getByTestId('ggw-pager-prev') as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId('ggw-pager-next') as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByTestId('ggw-pager-at')).toBeNull();
    expect(grid(c).classList.contains('ggw-grid--all')).toBe(false);
    expect(hiddenN(c)).toBe(0);
    expect(ios).toHaveLength(0);
    view.y = 1500;
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(scrolls).toHaveLength(0);
    boardNow = () => { const b = clone(RAW); b.rows = b.rows.slice(1); return b; };
    await refresh();
    expect(scrollBy()).not.toHaveBeenCalled();
  });

  it('8. ✕ on a tile → it leaves the DOM at once; the others stay shown', async () => {
    stubAll();
    const c = await mount();
    const X = SYMS[7];
    fireEvent.click(tileOf(c, X)!.querySelector('.ggw-remove')!);
    expect(tileOf(c, X)).toBeNull();
    expect(tiles(c)).toHaveLength(N - 1);
    expect(hiddenN(c)).toBe(0);
    await flush();
    expect(calls.filter((x) => x.method === 'DELETE')).toHaveLength(1);
    expect(tileOf(c, X)).toBeNull();                                             // the write never answered: still gone
  });

  it('9. the link: any page= → every tile shown and page= gone after the first write — NEGATIVE: no scroll; per and show still written', async () => {
    for (const pg of ['abc', '999', '-1', '3']) {
      stubAll();
      const c = await mount({ url: `/chart-maps?tab=gajjala_watch&per=4&page=${pg}` });
      expect(hiddenN(c)).toBe(0);
      expect(tiles(c)).toHaveLength(N);
      expect(q().has('page')).toBe(false);
      expect(q().get('per')).toBe('4');
      expect(q().get('tab')).toBe('gajjala_watch');
      expect(scrolls).toHaveLength(0);
      expect(scrollBy()).not.toHaveBeenCalled();
      fireEvent.click(chip(SYMS[0]));
      expect(q().get('show')).toBe(SYMS.slice(1).join(','));
      expect(q().has('page')).toBe(false);
      cleanup();
      vi.restoreAllMocks();
    }
  });
});

describe('▦ live: the render gate is "near the window"', () => {
  it('10. a far tile is not redrawn by a batch; reported near → live bars, NO new GET, NO new POST', async () => {
    stubAll();
    vi.stubGlobal('IntersectionObserver', FakeIO);
    boardNow = liveRaw;
    const c = await mount();
    const io = ios[ios.length - 1];
    expect(ios).toHaveLength(1);
    expect(io.opts.rootMargin).toBe('50% 0px');
    expect(io.targets).toHaveLength(N);
    io.report(SYMS.filter((s) => s !== 'XXII'));
    const far = html(svg1(c, 'XXII'));
    const omh = html(svg1(c, 'OMH'));
    const gets = calls.filter((x) => x.method === 'GET').length;
    const posts = calls.filter((x) => x.method === 'POST').length;
    await emit({ OMH: qt(4.41, at(395, 10)), XXII: qt(3.33, at(395, 10)) });
    expect(html(svg1(c, 'XXII'))).toBe(far);                                     // the far tile: not redrawn
    expect(html(svg1(c, 'OMH'))).not.toBe(omh);                                  // a near one is (the batch is live)
    io.report(SYMS);
    await flush();
    expect(html(svg1(c, 'XXII'))).not.toBe(far);                                 // near again → its live bars
    expect(calls.filter((x) => x.method === 'GET')).toHaveLength(gets);
    expect(calls.filter((x) => x.method === 'POST')).toHaveLength(posts);
  });

  it('10. NEGATIVE: without IntersectionObserver every shown tile is live; under ⤢ no board tile redraws, the ⤢ tile does; after the close they do', async () => {
    stubAll();
    boardNow = liveRaw;
    const c = await mount();
    const far = html(svg1(c, 'XXII'));
    await emit({ XXII: qt(3.33, at(395, 10)) });
    expect(html(svg1(c, 'XXII'))).not.toBe(far);                                 // fail-open: no observer → live
    fireEvent.click(screen.getByTestId('ggw-stretch-btn-OMH'));
    await flush();
    const st = () => document.querySelector('[data-testid="ggw-stretch-charts"] .ggw-frame[data-tf="1m"] svg');
    const stBefore = html(st());
    const nv = html(svg1(c, 'NVDA'));
    const om = html(svg1(c, 'OMH'));
    await emit({ OMH: qt(4.42, at(396, 10)), NVDA: qt(171.5, at(396, 10)) });
    expect(html(st())).not.toBe(stBefore);                                       // the ⤢ tile moves
    expect(html(svg1(c, 'NVDA'))).toBe(nv);                                      // no board tile does
    expect(html(svg1(c, 'OMH'))).toBe(om);
    fireEvent.keyDown(document, { key: 'Escape' });
    await flush();
    expect(html(svg1(c, 'NVDA'))).not.toBe(nv);
  });

  it('10. connection pin: 30 rows → ONE live-interest POST carrying all 30 symbols, ONE bus subscription', async () => {
    stubAll();
    vi.stubGlobal('IntersectionObserver', FakeIO);
    await mount();
    const posts = calls.filter((x) => x.method === 'POST' && x.url.endsWith(GGW_LIVE_PATH));
    expect(posts).toHaveLength(1);
    expect(new Set(JSON.parse(posts[0].body!).symbols)).toEqual(new Set(SYMS));
    expect(JSON.parse(posts[0].body!).symbols).toHaveLength(30);
    expect(bus.subs).toBe(1);
    expect(calls.filter((x) => x.method === 'GET' && x.url.endsWith(GGW_PATH))).toHaveLength(1);
  });
});

describe('▦ the scroll hold and ⤢', () => {
  const noPending = () => { const b = clone(RAW); b.rows = b.rows.filter((r: any) => r.state !== 'pending'); return b; };
  it('11. a re-GET drops a row above the tile in view → scrollBy(0, its shift) once', async () => {
    stubAll();
    mockGeometry();
    boardNow = noPending;
    const c = await mount();
    const list = tiles(c).map((t) => t.id.slice(4));
    view.y = GRID_TOP + 2 * ROW_H + 100;                                         // row 2 (tiles 4, 5) at the strip
    boardNow = () => { const b = noPending(); b.rows = b.rows.filter((r: any) => r.symbol !== list[0]); return b; };
    await refresh();
    /* list[4] was at row 2 (top −100); one slot earlier it is row 1, col 1 → ROW_H higher */
    expect(scrollBy()).toHaveBeenCalledTimes(1);
    expect(scrollBy()).toHaveBeenCalledWith(0, -ROW_H);
    expect(hiddenN(c)).toBe(0);
  });

  it('11. NEGATIVE: that tile removed → none; at the board top → none; a box add → none from the hold; a live batch reads no tile rect', async () => {
    stubAll();
    mockGeometry();
    boardNow = noPending;
    const c = await mount();
    const list = tiles(c).map((t) => t.id.slice(4));
    view.y = GRID_TOP + 2 * ROW_H + 100;
    boardNow = () => { const b = noPending(); b.rows = b.rows.filter((r: any) => r.symbol !== list[4]); return b; };
    await refresh();
    expect(scrollBy()).not.toHaveBeenCalled();                                   // its own tile left the grid
    view.y = 0;
    boardNow = () => { const b = noPending(); b.rows = b.rows.filter((r: any) => r.symbol !== list[0] && r.symbol !== list[4]); return b; };
    await refresh();
    expect(scrollBy()).not.toHaveBeenCalled();                                   // the head is in view
    /* a box add: the new name lands on top while scrolled deep — the focus scroll moves the view, not the hold
     * (one column, so the insert really shifts the tile in view by a row) */
    fireEvent.click(screen.getByTestId('ggw-layout-1'));                         // at the board top: no hold
    await flush();
    expect(scrollBy()).not.toHaveBeenCalled();
    view.y = GRID_TOP + 4 * ROW_H + 100;
    const added = clone(RAW.rows[12]);
    added.symbol = 'NEWX';
    boardNow = () => { const b = noPending(); b.rows = [added, ...b.rows.filter((r: any) => r.symbol !== list[0] && r.symbol !== list[4])]; return b; };
    const input = c.querySelector('.ggw-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'NEWX' } });
    fireEvent.submit(input.closest('form')!);
    for (let i = 0; i < 6; i += 1) await flush();
    expect(tileOf(c, 'NEWX')).not.toBeNull();
    expect(scrolls.filter((s) => s.id === 'ggw-NEWX')).toHaveLength(1);
    expect(scrollBy()).not.toHaveBeenCalled();
    /* a live batch: no tile rect is read */
    rectCalls.tiles = 0;
    await emit({ OMH: qt(4.41, at(395, 10)) });
    expect(rectCalls.tiles).toBe(0);
  });

  it('12. ⤢: step ▶ then close → the last-viewed tile is scrolled to once — NEGATIVE: open + close without stepping → none; phone → none', async () => {
    stubAll();
    let c = await mount();
    fireEvent.click(screen.getByTestId(`ggw-stretch-btn-${SYMS[1]}`));
    fireEvent.keyDown(document, { key: 'Escape' });
    await flush();
    expect(scrolls).toHaveLength(0);
    fireEvent.click(screen.getByTestId(`ggw-stretch-btn-${SYMS[1]}`));
    fireEvent.click(screen.getByTestId('ggw-stretch-next'));
    fireEvent.click(screen.getByTestId('ggw-stretch-next'));
    fireEvent.click(screen.getByTestId('ggw-unstretch'));
    await flush();
    expect(scrolls).toHaveLength(1);
    expect(scrolls[0].id).toBe(`ggw-${SYMS[3]}`);
    expect(hiddenN(c)).toBe(0);
    cleanup();
    stubAll(true);
    c = await mount();
    fireEvent.click(screen.getByTestId(`ggw-stretch-btn-${SYMS[1]}`));
    fireEvent.click(screen.getByTestId('ggw-stretch-next'));
    fireEvent.keyDown(document, { key: 'Escape' });
    await flush();
    expect(scrolls).toHaveLength(0);
  });

  it('12. NEGATIVE: ▶ onto a chip-hidden name then close → no focus left behind: no stray scroll later, the hold still works', async () => {
    stubAll();
    mockGeometry();
    boardNow = noPending;
    const c = await mount();
    const list = tiles(c).map((t) => t.id.slice(4));
    const X = list[10];
    fireEvent.click(chip(X));                                                   // X hidden by a chip filter
    expect(tileOf(c, X)!.hidden).toBe(true);
    scrolls.length = 0;                                                         // the chip tap's own board-top scroll
    fireEvent.click(screen.getByTestId(`ggw-stretch-btn-${list[9]}`));
    fireEvent.click(screen.getByTestId('ggw-stretch-next'));                    // ⤢ now on X (▶ walks every row)
    expect(screen.getByTestId(`ggw-stretch-tile-${X}`)).toBeTruthy();
    fireEvent.click(screen.getByTestId('ggw-unstretch'));
    await flush();
    expect(scrolls).toHaveLength(0);
    /* the hold is alive: a re-GET drops a row above the tile in view → one scrollBy */
    view.y = GRID_TOP + 2 * ROW_H + 100;
    boardNow = () => { const b = noPending(); b.rows = b.rows.filter((r: any) => r.symbol !== list[0]); return b; };
    await refresh();
    expect(scrollBy()).toHaveBeenCalledTimes(1);
    await refresh();
    expect(scrolls.filter((s) => s.id === `ggw-${X}`)).toHaveLength(0);
    /* a per-screen tap shows X again — still no scroll to it nobody asked for */
    fireEvent.click(screen.getByTestId('ggw-layout-9'));
    for (let i = 0; i < 3; i += 1) await flush();
    expect(tileOf(c, X)!.hidden).toBe(false);
    expect(scrolls.filter((s) => s.id === `ggw-${X}`)).toHaveLength(0);
  });
});

describe('▦ order, CSS and source', () => {
  it('13. the tiles keep the served order in every pick; with served sections on a desktop no folded_default tile is hidden', async () => {
    stubAll();
    const c = await mount();
    for (const l of GGW_LAYOUT_ORDER) {
      fireEvent.click(screen.getByTestId(`ggw-layout-${l}`));
      expect(tiles(c).map((t) => t.id.slice(4))).toEqual(SYMS);
    }
    cleanup();
    stubAll();
    const org = (key: string) => ({ group: key, when: { bucket: 'intraday', text: 'served-when', title: 'served-when-title' },
      setup: null, ran: null, past_winner: null });
    boardNow = () => {
      const b = clone(RAW);
      b.rows.forEach((r: any, i: number) => { r.org = org(i < 12 ? 'yours' : i < 21 ? 'auto' : 'rules'); });
      const sec = (key: string, syms: string[], folded = false) => ({ key, title: `served-${key}`, text: `served-head-${key}`,
        hint: null, n: syms.length, symbols: syms, ...(folded ? { folded_default: true } : {}) });
      b.sections = [sec('yours', SYMS.slice(0, 12)), sec('auto', SYMS.slice(12, 21)), sec('rules', SYMS.slice(21), true)];
      return b;
    };
    window.localStorage.setItem('ggw.collapsed', 'yours');
    const d = await mount();
    expect(d.querySelectorAll('.ggw-section')).toHaveLength(0);
    expect(tiles(d).map((t) => t.id.slice(4))).toEqual(SYMS);
    expect(hiddenN(d)).toBe(0);
    expect(lit()).toEqual(SYMS);
  });

  it('14. CSS: the scroll-margin rule is top level (not inside the first fitted @media block); [hidden] and the phone 1fr rules stay', async () => {
    const css = await readSource('src/styles/gajjalaWatch.css');
    const rule = '.ggw-grid--all > .ggw-tile { scroll-margin-top: calc(var(--sticky-top, 0px) + 0.5rem); }';
    const at = css.indexOf(rule);
    expect(at).toBeGreaterThan(0);
    const pre = css.slice(0, at).replace(/\/\*[\s\S]*?\*\//g, '');
    expect((pre.match(/\{/g) || []).length).toBe((pre.match(/\}/g) || []).length);   // brace depth 0 = top level
    const m = css.indexOf('@media (min-width: 641px) {');
    let depth = 0; let end = -1;
    for (let i = css.indexOf('{', m); i < css.length; i += 1) {
      if (css[i] === '{') depth += 1;
      if (css[i] === '}') { depth -= 1; if (depth === 0) { end = i; break; } }
    }
    expect(at > end || at < m).toBe(true);
    expect(css).toMatch(/\.ggw-tile\[hidden\] \{ display: none; \}/);
    expect(css).toMatch(/@media \(max-width: 640px\) \{ \.ggw-grid \{ grid-template-columns: 1fr; \} \}/);
    expect(css).toMatch(/@media \(max-width: 640px\) \{ \.ggw-grid\.ggw-grid--cols2 \{ grid-template-columns: 1fr; \} \}/);
    expect(css).toMatch(/@media \(max-width: 640px\) \{ \.ggw-grid\.ggw-grid--cols3 \{ grid-template-columns: 1fr; \} \}/);
    expect(css).toContain('.ggw-grid--all.ggw-grid--fit > .ggw-tile { content-visibility: auto; }');   // §5.4 lever 1, built and measured
    expect(css.match(/content-visibility/g)).toHaveLength(1);                     // NEGATIVE: no second lever rule
  });

  it('15. source: no page math on the board; page: 0 and paged={false}; useGgwNear( and useGgwHold( once each', async () => {
    const src = noComments(await readSource('src/components/GajjalaWatchBoard.tsx'));
    for (const bad of ['parseGgwPage', 'ggwAnchorPage', 'ggwPageOf', 'ggwClampPage', 'ggwPageCount', 'setPage(']) {
      expect(src).not.toContain(bad);
    }
    expect(src).toMatch(/ggwViewParams\(prev, \{ layout, pick, page: 0 \}\)/);
    expect(src).toContain('paged={false}');
    expect(src.split('useGgwNear(').length - 1).toBe(1);
    expect(src.split('useGgwHold(').length - 1).toBe(1);
    expect(src).toContain("ggw-grid--all");
    expect(src).toMatch(/import \{ useGgwHold, useGgwNear \} from '\.\.\/hooks\/useGgwScroll'/);
    expect(src).toMatch(/import \{ ggwStepNow \} from '\.\.\/lib\/ggwScroll'/);
  });

  it('16. comments: no header still describes the pages view, the page anchor or page 2+ (refix LOW)', async () => {
    const raw = await readSource('src/components/GajjalaWatchBoard.tsx');
    const flat = raw.replace(/\s*\n\s*\*\s*/g, ' ');                      // join wrapped comment lines
    for (const stale of ['pages view', 'page 2+', 'lands on page 1', '(the anchor', 'its page shown', 'a page open',
      'turns into the pages', '→ the pages']) {
      expect(flat).not.toContain(stale);
    }
    /* NEGATIVE: the reworded lines still say what the code does — the hold, and a dead pick = every name shown */
    expect(flat).toContain('a list change keeps the tile he is looking at where it is (the scroll hold, useGgwHold)');
    expect(flat).toContain('a dead pick turns into NO pick (every name shown)');
    expect(flat).toContain('→ no pick (every name shown)');
  });
});
