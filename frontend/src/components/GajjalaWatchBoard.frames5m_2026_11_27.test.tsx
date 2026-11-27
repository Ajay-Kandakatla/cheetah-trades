/* 👀 Gajjala's Watch — 5-min tiles, the dense per-screen picks, the frames menu and the average-volume line on the BOARD
 * (2026-11-27, spec watch5m rev 2 §3.7, WP board).
 * Ajay 2026-11-27: "This is how I want our watch list to be designed.. So I can look at 5 mins charts like 6 in one go..."
 * · "Also on the expanded view I need 5 mins by default to look in detail and not sure what the line on volume is its
 * blocking my story.." · "Give me a drop down or multi select like button to toggle 1 mins and 15 mins 5 mins by
 * default..".
 *
 * The REAL board, the REAL Tile / GgwStretch / PatternChart / GgwFramesMenu / useGgwFrames / useGgwLive and lib/ggwLive,
 * over the real 2026-11-23 payload (1m / 5m / 15m, the live axis keys as served). NO legacy seam here: this file runs the
 * new defaults. fetch is a routed stub; the bus is hand-driven (the …live.test.tsx way); localStorage is in memory;
 * matchMedia is stubbed; rects + the two grid gaps are mocked where a test needs a layout (jsdom has none). Every number
 * expected is computed from the lib (GGW_FIT_ROW_MIN_PX, ggwFitRowHeight, ggwDense*, GGW_CHART_H…), none typed.
 * S = ask 5 (⤢ + volume + menu); G = asks 1–4 (5-min tiles + per-screen picks). */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_23.json';
import { GG_UPDATE_EVENT } from '../lib/cardLive';
import {
  GGW_CHART_H, GGW_CHART_H_PHONE, GGW_FIT_ROW_MIN_PX, GGW_LIVE_PATH, GGW_PATH, GGW_PHONE_MQ, GGW_PICK_AT_KEY, GGW_TAB,
  ggwFitRowHeight, ggwFitViewBoxH,
} from '../lib/gajjalaWatch';
import {
  GGW_DENSE_DEFAULT, GGW_DENSE_KEY, GGW_DENSE_ORDER, GGW_FRAMES_KEY, GGW_FRAMES_WORDS, GGW_STRETCH_FRAMES_KEY,
  GGW_VOL_AVG_KEY, ggwDenseMaxCols, ggwDenseMaxRows, ggwDenseOffered, ggwDenseShown,
} from '../lib/ggwFrames';

const busHandlers = new Map<string, Set<(e: any) => void>>();
vi.mock('../lib/eventBus', () => ({
  subscribe: (type: string, fn: (e: any) => void) => {
    let s = busHandlers.get(type);
    if (!s) { s = new Set(); busHandlers.set(type, s); }
    s.add(fn);
    return () => { busHandlers.get(type)?.delete(fn); };
  },
}));

import GajjalaWatchBoard from './GajjalaWatchBoard';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = fixture as any;
const START: number = RAW.rows[0].frames[0].axis.start_epoch;
const at = (min: number, sec = 0) => START + min * 60 + sec;
const LAST_MIN: number = RAW.rows[0].frames[0].axis.x[RAW.rows[0].frames[0].axis.x.length - 1] + 1;   // the 1-min close

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
function rename(row: any, sym: string): any {
  const r = clone(row);
  r.symbol = sym;
  for (const f of r.frames || []) if (f?.tile) f.tile.symbol = sym;
  return r;
}
function boardOf(rows?: any[], o: Record<string, unknown> = {}): any {
  const b = clone(RAW);
  if (rows) b.rows = rows;
  b.symbols = b.rows.filter((r: any) => !r.auto).map((r: any) => r.symbol);
  return { ...b, ...o };
}
const res = (body: unknown) => ({ ok: true, json: async () => body }) as unknown as Response;

type Call = { url: string; method: string; body?: string };
let calls: Call[] = [];
let serve: () => any = () => boardOf();
let serveRows: ((syms: string[]) => any) | null = null;
let loc = '';
function Probe() { loc = useLocation().search; return null; }
const q = () => new URLSearchParams(loc);
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
const tick = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

function stubAll(phone = false) {
  vi.stubGlobal('EventSource', class {});                                       // the live hook arms only with one
  vi.stubGlobal('matchMedia', (qq: string) => ({
    matches: phone && qq === GGW_PHONE_MQ, media: qq, addEventListener: () => {}, removeEventListener: () => {},
  }));
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method || 'GET').toUpperCase();
    calls.push({ url, method, body: init?.body as string | undefined });
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) {
      return res({ state: 'ok', stream: { on: true, word: null, state: 'live' }, tab: GGW_TAB, symbols: [] });
    }
    if (!url.includes(GGW_PATH)) return res({});
    const qs = url.split('?symbols=')[1];
    if (qs != null && serveRows) return serveRows(decodeURIComponent(qs).split(','));
    return res(serve());
  }));
}
async function mount(url = '/chart-maps?tab=gajjala_watch') {
  const r = render(<MemoryRouter initialEntries={[url]}><GajjalaWatchBoard /><Probe /></MemoryRouter>);
  for (let i = 0; i < 4; i += 1) await flush();
  return r;
}
const watchGets = () => calls.filter((c) => c.method === 'GET' && c.url.includes(GGW_PATH));
const livePosts = () => calls.filter((c) => c.method === 'POST' && c.url.endsWith(GGW_LIVE_PATH));
const watchCalls = () => watchGets().length + livePosts().length;

/* selectors */
const grid = (c: HTMLElement) => c.querySelector('.ggw-board > .ggw-grid') as HTMLElement;
const tiles = (c: HTMLElement) => Array.from(grid(c).querySelectorAll(':scope > .ggw-tile')) as HTMLElement[];
const tile = (c: ParentNode, s: string) => c.querySelector(`[data-testid="ggw-tile-${s}"]`) as HTMLElement;
const tfsIn = (el: ParentNode | null) => (el ? Array.from(el.querySelectorAll('.ggw-frame')).map((f) => f.getAttribute('data-tf')) : []);
const stretch = () => document.querySelector('[data-testid="ggw-stretch"]') as HTMLElement | null;
const stretchTfs = () => tfsIn(document.querySelector('[data-testid="ggw-stretch-charts"]'));
const okSyms = () => (serve().rows as any[]).filter((r) => r.state === 'ok').map((r) => r.symbol as string);
const smaIn = (el: ParentNode | null) => (el ? el.querySelectorAll('path.pc-vol-sma').length : 0);
const volsIn = (el: ParentNode | null) => (el ? el.querySelectorAll('rect.pc-vol').length : 0);
const colsOf = (g: HTMLElement) => Number((/ggw-grid--cols(\d+)/.exec(g.className) || [])[1]);
const rowVar = (g: HTMLElement) => g.style.getPropertyValue('--ggw-row-h');
const pickBtn = (d: number) => screen.getByTestId(`ggw-layout-${d}`) as HTMLButtonElement;
const pickBtns = () => Array.from(document.querySelectorAll('[data-testid="ggw-layout"] button')) as HTMLButtonElement[];
const litPicks = () => pickBtns().filter((b) => b.getAttribute('aria-pressed') === 'true').map((b) => b.textContent);
function openMenu(prefix: string) {
  if (!screen.queryByTestId(`${prefix}-menu`)) fireEvent.click(screen.getByTestId(`${prefix}-btn`));
}
function tickBox(prefix: string, key: string) {
  openMenu(prefix);
  fireEvent.click(screen.getByTestId(`${prefix}-${key}`));
}
const openStretch = (s: string) => fireEvent.click(screen.getByTestId(`ggw-stretch-btn-${s}`));

/* the live batches (a print `min` minutes after 04:00 ET, on the served grid) */
const emit = (quotes: Record<string, unknown>) => act(async () => {
  for (const fn of busHandlers.get(GG_UPDATE_EVENT) || []) fn({ type: GG_UPDATE_EVENT, ts: 0, payload: { kind: 'quotes', variant: GGW_TAB, quotes } });
});
const qt = (price: number, asOf: number, size: number) => ({ price, as_of_epoch: asOf, vs: null, size });
const N1: number = RAW.rows[0].frames[0].tile.bars.length;                      // stored 1-min columns
const C0: number = RAW.rows[0].frames[2].tile.bars[RAW.rows[0].frames[2].tile.bars.length - 1].c;
/** Three prints inside ONE 15-min bucket (after the last stored bar), the critic's C1 shape: 50k, 80k, 5k. */
async function threeBatches(sym = 'ZONE') {
  await emit({ [sym]: qt(C0, at(LAST_MIN, 10), 50_000) });
  await emit({ [sym]: qt(C0 * 1.1, at(LAST_MIN + 3), 80_000) });
  await emit({ [sym]: qt(C0 * 1.03, at(LAST_MIN + 7), 5_000) });
}
/** Candle groups: a wick `line` then a body `rect` (the PatternChart.frames1026 selector). */
const candles = (svg: Element) => Array.from(svg.querySelectorAll('g'))
  .filter((g) => g.children.length === 2 && g.children[0].tagName.toLowerCase() === 'line'
    && g.children[1].tagName.toLowerCase() === 'rect');
const nowLabel = (svg: Element) => Array.from(svg.querySelectorAll('text')).map((t) => t.textContent || '')
  .find((t) => t.startsWith('now ')) ?? null;
/** What a forming candle reads as: every column's data-vol, the last candle's wick + body geometry, the `now` label. */
function snap(svg: Element | null) {
  if (!svg) return null;
  const cs = candles(svg);
  const last = cs[cs.length - 1];
  const attrs = (el: Element, ks: string[]) => ks.map((k) => el.getAttribute(k));
  return {
    n: cs.length,
    vols: Array.from(svg.querySelectorAll('rect.pc-vol')).map((r) => r.getAttribute('data-vol')),
    wick: last ? attrs(last.children[0], ['y1', 'y2']) : null,
    body: last ? attrs(last.children[1], ['y', 'height']) : null,
    now: nowLabel(svg),
  };
}
const stretchSvg = (tf: string) => document.querySelector(`[data-testid="ggw-stretch"] .ggw-frame[data-tf="${tf}"] svg`);
const tileSvg = (c: ParentNode, s: string, tf: string) => c.querySelector(`[data-testid="ggw-tile-${s}"] .ggw-frame[data-tf="${tf}"] svg`);

/* geometry: board top 0, grid top TOP; innerHeight = TOP + free (so free = innerHeight − (grid top − board top)) */
const TOP = 120;
const GAP = 13;
const H0 = window.innerHeight;
const setInner = (h: number) => Object.defineProperty(window, 'innerHeight', { configurable: true, writable: true, value: h });
const rect = (top: number, w: number, h: number) =>
  ({ top, bottom: top + h, left: 0, right: w, width: w, height: h, x: 0, y: top, toJSON: () => ({}) }) as DOMRect;
function geo(width: number, free: number) {
  setInner(TOP + free);
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    if (this.classList.contains('ggw-board')) return rect(0, width, 20_000);
    if (this.classList.contains('ggw-grid') && !this.classList.contains('ggw-grid--stretch')) return rect(TOP, width, 18_000);
    return rect(0, 0, 0);
  });
  const real = window.getComputedStyle.bind(window);
  vi.spyOn(window, 'getComputedStyle').mockImplementation((el: Element, pseudo?: string | null) => {
    const cs = real(el, pseudo);
    if (!el.classList.contains('ggw-grid')) return cs;
    return new Proxy(cs, {
      get: (t, k) => {
        if (k === 'rowGap' || k === 'columnGap') return `${GAP}px`;
        const v = (t as any)[k];
        return typeof v === 'function' ? v.bind(t) : v;
      },
    });
  });
}

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const origScroll = (Element.prototype as any).scrollIntoView;
beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal('localStorage', memStorage());
  busHandlers.clear();
  calls = [];
  serve = () => boardOf();
  serveRows = null;
  loc = '';
  (Element.prototype as any).scrollIntoView = function () {};
  vi.spyOn(window, 'scrollBy').mockImplementation(() => {});
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  setInner(H0);
  (Element.prototype as any).scrollIntoView = origScroll;
  document.body.style.overflow = '';
});

// ── S — ⤢ + volume + menu (ask 5) ────────────────────────────────────────────────────────────────────────────────────
describe('S — ⤢ on 5-min, the volume line, the menu (ask 5)', { timeout: 30000 }, () => {
  it('S1. ⤢ opens with ONE frame: the 5-min, flexGrow 1 — NEGATIVE: no 1-min / 15-min frame in ⤢', async () => {
    stubAll();
    await mount();
    openStretch('ZONE');
    expect(stretchTfs()).toEqual(['5m']);
    const f = document.querySelector('[data-testid="ggw-stretch-charts"] .ggw-frame') as HTMLElement;
    expect(f.style.flexGrow).toBe('1');
    expect(stretch()!.querySelectorAll('[data-tf="1m"], [data-tf="15m"]')).toHaveLength(0);
    expect(screen.getByTestId('ggw-sframes-btn').textContent).toBe('5-min ▾');
  });

  it('S2. tick 15-min + 1-min in ⤢ → 15 / 5 / 1; ▶ keeps them; close + reopen keeps them; Esc closes the menu first, then ⤢', async () => {
    stubAll();
    await mount();
    openStretch('ZONE');
    tickBox('ggw-sframes', '15m');
    tickBox('ggw-sframes', '1m');
    expect(stretchTfs()).toEqual(['15m', '5m', '1m']);
    expect(screen.queryByTestId('ggw-sframes-menu')).not.toBeNull();             // stays open across ticks
    fireEvent.click(screen.getByTestId('ggw-stretch-next'));
    expect(document.querySelector('[data-testid="ggw-stretch-tile-PENNY"]')).not.toBeNull();
    expect(stretchTfs()).toEqual(['15m', '5m', '1m']);
    fireEvent.click(screen.getByTestId('ggw-unstretch'));
    expect(stretch()).toBeNull();
    openStretch('RETRY');
    expect(stretchTfs()).toEqual(['15m', '5m', '1m']);
    openMenu('ggw-sframes');
    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(screen.queryByTestId('ggw-sframes-menu')).toBeNull();
    expect(stretch()).not.toBeNull();
    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(stretch()).toBeNull();
  });

  it('S3. NEGATIVE: with only 5-min on its box is disabled with the served title; a forced click changes nothing; ⤢ never has zero frames', async () => {
    stubAll();
    await mount();
    openStretch('ZONE');
    openMenu('ggw-sframes');
    const box = screen.getByTestId('ggw-sframes-5m') as HTMLInputElement;
    expect(box.disabled).toBe(true);
    expect(box.title).toBe(GGW_FRAMES_WORDS.lastOn);
    fireEvent.click(box);
    expect(stretchTfs()).toEqual(['5m']);
    expect(window.localStorage.getItem(GGW_STRETCH_FRAMES_KEY)).toBeNull();
    /* 15 on, 5 off → 15 alone, then its box is the disabled one */
    tickBox('ggw-sframes', '15m');
    tickBox('ggw-sframes', '5m');
    expect(stretchTfs()).toEqual(['15m']);
    expect((screen.getByTestId('ggw-sframes-15m') as HTMLInputElement).disabled).toBe(true);
    fireEvent.click(screen.getByTestId('ggw-sframes-15m'));
    expect(stretchTfs()).toEqual(['15m']);
  });

  it('S4. volume: default → no average line on the board or in ⤢ (columns kept); the tick brings it back in both; untick → gone', async () => {
    stubAll();
    const { container: c } = await mount();
    const b = grid(c);
    expect(smaIn(b)).toBe(0);
    expect(volsIn(b)).toBeGreaterThan(0);
    openStretch('ZONE');
    expect(smaIn(stretch())).toBe(0);
    expect(volsIn(stretch())).toBeGreaterThan(0);
    tickBox('ggw-sframes', 'volavg');
    expect(smaIn(stretch())).toBeGreaterThan(0);
    expect(smaIn(b)).toBeGreaterThan(0);
    tickBox('ggw-sframes', 'volavg');
    expect(smaIn(stretch())).toBe(0);
    expect(smaIn(b)).toBe(0);
    /* the board menu drives the same switch */
    fireEvent.click(screen.getByTestId('ggw-unstretch'));
    tickBox('ggw-frames', 'volavg');
    expect(smaIn(grid(c))).toBeGreaterThan(0);
  });

  it('S5. [C1] live: ⤢ on 5-min, three batches in one 15-min bucket, then tick 15 + 1 → their forming candles equal a board that had every frame on from the start', async () => {
    /* reference: every frame on from page open (today's live mode) */
    stubAll();
    window.localStorage.setItem(GGW_STRETCH_FRAMES_KEY, '1m,5m,15m');
    window.localStorage.setItem(GGW_FRAMES_KEY, '1m,5m,15m');
    await mount();
    openStretch('ZONE');
    await threeBatches();
    const ref15 = snap(stretchSvg('15m'));
    const ref1 = snap(stretchSvg('1m'));
    const refBody = livePosts()[0]?.body;
    expect(ref15!.vols[ref15!.vols.length - 1]).toBe('135000');                  // 50k + 80k + 5k in ONE 15-min candle
    expect(ref1!.vols.slice(N1)).toEqual(['50000', '80000', '5000']);              // three 1-min candles
    cleanup();
    vi.unstubAllGlobals();
    /* the new default: ⤢ on 5-min alone while the prints arrive */
    vi.stubGlobal('localStorage', memStorage());
    busHandlers.clear();
    calls = [];
    stubAll();
    await mount();
    openStretch('ZONE');
    await threeBatches();
    expect(stretchTfs()).toEqual(['5m']);
    const gets = watchGets().length;
    const posts = livePosts().length;
    tickBox('ggw-sframes', '15m');
    tickBox('ggw-sframes', '1m');
    expect(snap(stretchSvg('15m'))).toEqual(ref15);
    expect(snap(stretchSvg('1m'))).toEqual(ref1);
    /* NEGATIVE: untick + re-tick prunes nothing — identical again */
    tickBox('ggw-sframes', '15m');
    expect(stretchSvg('15m')).toBeNull();
    tickBox('ggw-sframes', '15m');
    expect(snap(stretchSvg('15m'))).toEqual(ref15);
    /* the POST body is the same symbol list; a tick issues no GET and no POST */
    expect(livePosts()[0]?.body).toBe(refBody);
    expect(JSON.parse(refBody as string).symbols).toEqual((serve().rows as any[]).map((r) => r.symbol));
    expect(watchGets().length).toBe(gets);
    expect(livePosts().length).toBe(posts);
  });

  it('S6. persistence: ggw.stretchFrames / ggw.volAvg are written on change and a remount restores them', async () => {
    stubAll();
    await mount();
    openStretch('ZONE');
    tickBox('ggw-sframes', '15m');
    tickBox('ggw-sframes', 'volavg');
    expect(window.localStorage.getItem(GGW_STRETCH_FRAMES_KEY)).toBe('5m,15m');
    expect(window.localStorage.getItem(GGW_VOL_AVG_KEY)).toBe('1');
    cleanup();
    await mount();
    openStretch('ZONE');
    expect(stretchTfs()).toEqual(['15m', '5m']);
    expect(smaIn(stretch())).toBeGreaterThan(0);
  });
  it('S6. NEGATIVE: junk stored values (x, empty) → the defaults; a storage that throws → the board still works in-session', async () => {
    stubAll();
    window.localStorage.setItem(GGW_STRETCH_FRAMES_KEY, 'x');
    window.localStorage.setItem(GGW_FRAMES_KEY, '');
    window.localStorage.setItem(GGW_VOL_AVG_KEY, '');
    const { container: c } = await mount();
    expect(tfsIn(tile(c, 'ZONE'))).toEqual(['5m']);
    openStretch('ZONE');
    expect(stretchTfs()).toEqual(['5m']);
    expect(smaIn(stretch())).toBe(0);
    cleanup();
    const boom = () => { throw new Error('blocked'); };
    vi.stubGlobal('localStorage', { getItem: boom, setItem: boom, removeItem: boom, clear: boom, key: boom, length: 0 });
    await mount();
    openStretch('ZONE');
    expect(stretchTfs()).toEqual(['5m']);
    tickBox('ggw-sframes', '1m');
    expect(stretchTfs()).toEqual(['5m', '1m']);
  });

  it('S7. two separate choices: a tick in ⤢ never changes a board tile; a tick on the board never changes ⤢', async () => {
    stubAll();
    const { container: c } = await mount();
    openStretch('ZONE');
    tickBox('ggw-sframes', '1m');
    expect(stretchTfs()).toEqual(['5m', '1m']);
    for (const s of okSyms()) expect(tfsIn(tile(c, s))).toEqual(['5m']);
    fireEvent.click(screen.getByTestId('ggw-unstretch'));
    tickBox('ggw-frames', '15m');
    for (const s of okSyms()) expect(tfsIn(tile(c, s)).sort()).toEqual(['15m', '5m']);
    openStretch('ZONE');
    expect(stretchTfs()).toEqual(['5m', '1m']);
    expect(window.localStorage.getItem(GGW_FRAMES_KEY)).toBe('5m,15m');
    expect(window.localStorage.getItem(GGW_STRETCH_FRAMES_KEY)).toBe('1m,5m');
  });

  it('S8. unchanged pins (source reads): stretch order, backend FRAMES / PUSH_FRAMES, seed off, the unwrapped link literal, the ungated fold, the card click', async () => {
    const lib = await readSource('src/lib/gajjalaWatch.ts');
    expect(lib).toContain("export const GGW_STRETCH_ORDER = ['15m', '5m', '1m'] as const;");
    expect(lib).toMatch(/export const GGW_SEED_FORMING = false;/);
    const be = await readSource('../backend/chart_maps/gajjala_watch/constants.py');
    expect(be).toContain('FRAMES = (("1m", "1min"), ("5m", "5min"), ("15m", "15min"))');
    expect(be).toMatch(/^PUSH_FRAMES = \("1m",\)/m);
    const board = await readSource('src/components/GajjalaWatchBoard.tsx');
    expect(board).toContain('setParams((prev) => ggwViewParams(prev, { layout, pick, page: 0 }), { replace: true });');
    expect(board).not.toContain('ggwPerParam');
    expect(board).toContain('ggwFrameMetas(load.p.rows)');
    expect(board).not.toMatch(/ggwMetasOn|ggwLiveTfs/);
    expect(board).toContain('frames={fx.board}');
    expect(board).toContain('frames={fx.stretch}');
    const card = await readSource('src/components/GgCardView.tsx');
    expect(card).not.toContain('frames=');
    expect(card).not.toMatch(/ggwFrames/);
  });
});

// ── G — 5-min tiles + per-screen picks (asks 1–4) ───────────────────────────────────────────────────────────────────
describe('G — 5-min tiles and the dense per-screen picks (asks 1–4)', { timeout: 30000 }, () => {
  it('G1. default desktop: every ok row draws ONE 5-min chart; grid 6 · 3 columns — NEGATIVE: no 1-min, no 15-min, no pair', async () => {
    stubAll();
    const { container: c } = await mount();
    for (const s of okSyms()) {
      expect(tfsIn(tile(c, s)), s).toEqual(['5m']);
      expect(tile(c, s).classList.contains('ggw-tile--one')).toBe(true);
      expect(tile(c, s).querySelector('[data-testid="ggw-one-charts"]')).not.toBeNull();
    }
    const g = grid(c);
    expect(g.querySelectorAll('[data-tf="1m"]')).toHaveLength(0);
    expect(g.querySelectorAll('[data-tf="15m"]')).toHaveLength(0);
    expect(g.querySelectorAll('.ggw-frame-pair')).toHaveLength(0);
    expect(g.getAttribute('data-frames')).toBe('5m');
    expect(g.getAttribute('data-layout')).toBe(String(GGW_DENSE_DEFAULT));
    expect(g.className).toContain('ggw-grid--cols3');
    expect(g.className).toContain('ggw-grid--all');
    expect(pickBtns().map((b) => Number(b.textContent))).toEqual([...GGW_DENSE_ORDER]);
    expect(screen.getByTestId('ggw-frames-btn').textContent).toBe('5-min ▾');
  });

  it('G2. board menu: tick 1 + 15 → today\'s tile and 1 · 2 · 4 · 9, the 1-min candle folded since page open [C1]; untick both → one chart and 6 · … · 20', async () => {
    stubAll();
    window.localStorage.setItem(GGW_FRAMES_KEY, '1m,5m,15m');
    const ref = await mount();
    await threeBatches();
    const ref1 = snap(tileSvg(ref.container, 'ZONE', '1m'));
    expect(ref1!.vols.slice(N1)).toEqual(['50000', '80000', '5000']);
    cleanup();
    vi.unstubAllGlobals();
    vi.stubGlobal('localStorage', memStorage());
    busHandlers.clear();
    calls = [];
    stubAll();
    const { container: c } = await mount();
    await threeBatches();
    tickBox('ggw-frames', '1m');
    tickBox('ggw-frames', '15m');
    const t = tile(c, 'ZONE');
    expect(t.classList.contains('ggw-tile--one')).toBe(false);
    expect(t.querySelector('.ggw-frame-pair')).not.toBeNull();
    expect(tfsIn(t)).toEqual(['1m', '5m', '15m']);
    expect(pickBtns().map((b) => b.textContent)).toEqual(['1', '2', '4', '9']);
    expect(grid(c).getAttribute('data-layout')).toBe('2');
    expect(snap(tileSvg(c, 'ZONE', '1m'))).toEqual(ref1);
    expect(snap(tileSvg(c, 'ZONE', '15m'))!.vols.slice(-1)).toEqual(['135000']);
    tickBox('ggw-frames', '1m');
    tickBox('ggw-frames', '15m');
    expect(tfsIn(tile(c, 'ZONE'))).toEqual(['5m']);
    expect(pickBtns().map((b) => Number(b.textContent))).toEqual([...GGW_DENSE_ORDER]);
  });

  /* [C3, C6] density: the offer at four windows, every enabled pick drawn exactly, the two measuring hooks agree */
  const SIZES: Array<[number, number]> = [[1360, 731], [1360, 621], [1840, 940], [2480, 1331]];
  const WANT: Record<string, number[]> = { '1360x731': [6, 9], '1360x621': [6], '1840x940': [6, 9, 12, 16], '2480x1331': [6, 9, 12, 16, 20] };
  for (const [w, free] of SIZES) {
    it(`G3. ${w} × ${free}: the offered picks enabled, the rest greyed with the title; every enabled tap draws exactly that pick at ≥ the floor`, async () => {
      stubAll();
      geo(w, free);
      const { container: c } = await mount();
      const offered = ggwDenseOffered(ggwDenseMaxCols(w, GAP), ggwDenseMaxRows(free, GAP));
      expect(offered).toEqual(WANT[`${w}x${free}`]);
      expect(pickBtns()).toHaveLength(GGW_DENSE_ORDER.length);
      for (const d of GGW_DENSE_ORDER) {
        const b = pickBtn(d);
        expect(b.disabled, `${d}`).toBe(!offered.includes(d));
        if (!offered.includes(d)) expect(b.title).toBe(`${d} per screen — ${GGW_FRAMES_WORDS.tooSmall}`);
      }
      for (const d of offered) {
        fireEvent.click(pickBtn(d));
        await flush();
        const g = grid(c);
        expect(g.getAttribute('data-layout')).toBe(String(d));
        expect(pickBtns()).toHaveLength(GGW_DENSE_ORDER.length);
        const cols = colsOf(g);
        const rows = d / cols;
        expect(Number.isInteger(rows), `${d} at ${cols} cols`).toBe(true);
        const want = ggwFitRowHeight({ vh: window.innerHeight, top: TOP, below: 0, gap: GAP }, rows);
        expect(rowVar(g)).toBe(`${want}px`);
        expect(Math.floor((free - (rows - 1) * GAP) / rows)).toBeGreaterThanOrEqual(GGW_FIT_ROW_MIN_PX);
        expect(litPicks()).toEqual([String(d)]);
      }
    });
  }

  it('G4. [C3] stored 16 at 1360 × 731 → "9" lit, 3 × 3, ggw.dense still 16', async () => {
    stubAll();
    window.localStorage.setItem(GGW_DENSE_KEY, '16');
    geo(1360, 731);
    const { container: c } = await mount();
    expect(litPicks()).toEqual(['9']);
    expect(colsOf(grid(c))).toBe(3);
    expect(rowVar(grid(c))).toBe(`${ggwFitRowHeight({ vh: window.innerHeight, top: TOP, below: 0, gap: GAP }, 3)}px`);
    expect(grid(c).getAttribute('data-layout')).toBe('9');
    expect(window.localStorage.getItem(GGW_DENSE_KEY)).toBe('16');
  });
  it('G4. stored 6 at 1200 × 1100 → "6" lit, 2 columns × 3 rows', async () => {
    stubAll();
    geo(1200, 1100);
    const { container: c } = await mount();
    expect(litPicks()).toEqual(['6']);
    expect(colsOf(grid(c))).toBe(2);
    expect(rowVar(grid(c))).toBe(`${ggwFitRowHeight({ vh: window.innerHeight, top: TOP, below: 0, gap: GAP }, 3)}px`);
  });
  it('G4. NEGATIVE: 1200 × 500 → no pick lit, all five greyed, the 2 × 2 fit grid, data-layout "fit", ggw.dense unchanged', async () => {
    stubAll();
    window.localStorage.setItem(GGW_DENSE_KEY, '9');
    geo(1200, 500);
    const { container: c } = await mount();
    expect(litPicks()).toEqual([]);
    expect(pickBtns().every((b) => b.disabled)).toBe(true);
    const shown = ggwDenseShown(9, ggwDenseMaxCols(1200, GAP), ggwDenseMaxRows(500, GAP));
    expect(shown).toEqual({ pick: null, cols: 2, rows: 2 });
    expect(colsOf(grid(c))).toBe(2);
    expect(rowVar(grid(c))).toBe(`${ggwFitRowHeight({ vh: window.innerHeight, top: TOP, below: 0, gap: GAP }, 2)}px`);
    expect(grid(c).getAttribute('data-layout')).toBe('fit');
    expect(window.localStorage.getItem(GGW_DENSE_KEY)).toBe('9');
  });
  it('G4. NEGATIVE: no width (jsdom default) → no cap: all five enabled, 3 × 2 at the default', async () => {
    stubAll();
    const { container: c } = await mount();
    expect(pickBtns().every((b) => !b.disabled)).toBe(true);
    expect(colsOf(grid(c))).toBe(3);
    expect(litPicks()).toEqual([String(GGW_DENSE_DEFAULT)]);
    expect(grid(c).classList.contains('ggw-grid--fit')).toBe(false);
  });

  it('G5. NEGATIVE: a click on a greyed pick writes nothing — ggw.dense, ggw.pickAt untouched, the chip filter kept', async () => {
    stubAll();
    geo(1360, 621);
    const { container: c } = await mount();
    fireEvent.click(screen.getByTestId('ggw-pager-PENNY'));
    expect(tile(c, 'PENNY').hidden).toBe(true);
    const stamp = window.localStorage.getItem(GGW_PICK_AT_KEY);
    expect(stamp).not.toBeNull();
    await tick(1_000);
    expect(pickBtn(9).disabled).toBe(true);
    fireEvent.click(pickBtn(9));
    await flush();
    expect(window.localStorage.getItem(GGW_DENSE_KEY)).toBeNull();
    expect(window.localStorage.getItem(GGW_PICK_AT_KEY)).toBe(stamp);
    expect(tile(c, 'PENNY').hidden).toBe(true);
    expect(grid(c).getAttribute('data-layout')).toBe('6');
  });

  it('G6. phone: no per-screen pick, the frames menu IS there, one chart per tile at the phone height', async () => {
    stubAll(true);
    const { container: c } = await mount();
    expect(screen.queryByTestId('ggw-layout')).toBeNull();
    expect(screen.getByTestId('ggw-frames')).not.toBeNull();
    for (const s of okSyms()) {
      expect(tfsIn(tile(c, s))).toEqual(['5m']);
      const vb = Array.from(tile(c, s).querySelectorAll('svg')).map((v) => v.getAttribute('viewBox'));
      expect(vb).toEqual([`0 0 620 ${GGW_CHART_H_PHONE}`]);
    }
    expect(grid(c).classList.contains('ggw-grid--fit')).toBe(false);
  });

  it('G7. 30 rows at pick 6: 30 tiles in the DOM, none hidden, no page count, ◀ ▶ greyed; ← → never hide a tile', async () => {
    const zone = RAW.rows[0];
    serve = () => boardOf(Array.from({ length: 30 }, (_x, i) => rename(zone, `S${String(i).padStart(2, '0')}`)));
    stubAll();
    const { container: c } = await mount();
    expect(tiles(c)).toHaveLength(30);
    expect(tiles(c).filter((t) => t.hidden)).toHaveLength(0);
    expect(grid(c).getAttribute('data-layout')).toBe('6');
    expect((screen.getByTestId('ggw-pager-prev') as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId('ggw-pager-next') as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByTestId('ggw-pager').textContent).not.toMatch(/\d+\s*\/\s*\d+/);
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    await flush();
    expect(tiles(c).filter((t) => t.hidden)).toHaveLength(0);
  });

  it('G8. chips: a tap hides that one name; a dense-pick tap clears the filter and stamps ggw.pickAt — NEGATIVE: a frames tick does neither, no GET', async () => {
    stubAll();
    const { container: c } = await mount();
    fireEvent.click(screen.getByTestId('ggw-pager-PENNY'));
    expect(tile(c, 'PENNY').hidden).toBe(true);
    expect(tile(c, 'ZONE').hidden).toBe(false);
    const stamp = window.localStorage.getItem(GGW_PICK_AT_KEY);
    await tick(1_000);
    const gets = watchGets().length;
    tickBox('ggw-frames', '1m');
    expect(tile(c, 'PENNY').hidden).toBe(true);
    expect(window.localStorage.getItem(GGW_PICK_AT_KEY)).toBe(stamp);
    expect(watchGets().length).toBe(gets);
    tickBox('ggw-frames', '1m');                                                 // back to 5-min alone (dense)
    await tick(1_000);
    fireEvent.click(pickBtn(9));
    await flush();
    expect(tile(c, 'PENNY').hidden).toBe(false);
    expect(Number(window.localStorage.getItem(GGW_PICK_AT_KEY))).toBeGreaterThan(Number(stamp));
    expect(window.localStorage.getItem(GGW_DENSE_KEY)).toBe('9');
  });

  it('G9. near gate: a far tile is not redrawn by a batch; reported near → it is (no new GET, no new POST)', async () => {
    const ios: any[] = [];
    class FakeIO {
      cb: (e: any[]) => void; targets: Element[] = [];
      constructor(cb: (e: any[]) => void) { this.cb = cb; ios.push(this); }
      observe(el: Element) { this.targets.push(el); }
      unobserve() {}
      disconnect() { this.targets = []; }
      report(near: ReadonlyArray<string>) {
        act(() => { this.cb(this.targets.map((t) => ({ target: t, isIntersecting: near.includes(t.id.slice(4)) }))); });
      }
    }
    vi.stubGlobal('IntersectionObserver', FakeIO);
    stubAll();
    const { container: c } = await mount();
    const io = ios[ios.length - 1];
    io.report(['ZONE']);
    const z0 = volsIn(tileSvg(c, 'ZONE', '5m'));
    const p0 = volsIn(tileSvg(c, 'PENNY', '5m'));
    await emit({ ZONE: qt(C0, at(LAST_MIN, 10), 1_000), PENNY: qt(C0, at(LAST_MIN, 10), 1_000) });
    expect(volsIn(tileSvg(c, 'ZONE', '5m'))).toBe(z0 + 1);
    expect(volsIn(tileSvg(c, 'PENNY', '5m'))).toBe(p0);
    const n = watchCalls();
    io.report(['ZONE', 'PENNY']);
    expect(volsIn(tileSvg(c, 'PENNY', '5m'))).toBe(p0 + 1);
    expect(watchCalls()).toBe(n);
  });

  it('G10. [C2] link: per=2 as today and no dense value in it; a dense-pick tap leaves the query string unchanged', async () => {
    stubAll();
    await mount('/chart-maps?tab=gajjala_watch&focus=ZONE');
    expect(q().get('per')).toBe('2');
    expect(q().get('tab')).toBe('gajjala_watch');
    expect(q().get('focus')).toBe('ZONE');
    expect(q().has('page')).toBe(false);
    expect(Array.from(q().values())).not.toContain(String(GGW_DENSE_DEFAULT));
    const before = loc;
    fireEvent.click(pickBtn(9));
    await flush();
    expect(loc).toBe(before);
    expect(window.localStorage.getItem(GGW_DENSE_KEY)).toBe('9');
  });
  it('G10. incoming per=9: the dense pick stays the stored / default one, per=9 survives the first write, all three frames on → 9 per screen', async () => {
    stubAll();
    const { container: c } = await mount('/chart-maps?tab=gajjala_watch&per=9&page=3');
    expect(grid(c).getAttribute('data-layout')).toBe(String(GGW_DENSE_DEFAULT));
    expect(q().get('per')).toBe('9');
    expect(q().has('page')).toBe(false);
    tickBox('ggw-frames', '1m');
    tickBox('ggw-frames', '15m');
    expect(grid(c).getAttribute('data-layout')).toBe('9');
    expect(litPicks()).toEqual(['9']);
    expect(q().get('per')).toBe('9');
  });
  it('G10. NEGATIVE: incoming per=12 is junk for the layout exactly as today (rewritten to per=2), never read as a dense pick', async () => {
    stubAll();
    const { container: c } = await mount('/chart-maps?tab=gajjala_watch&per=12');
    expect(q().get('per')).toBe('2');
    expect(grid(c).getAttribute('data-layout')).toBe(String(GGW_DENSE_DEFAULT));
    expect(window.localStorage.getItem(GGW_DENSE_KEY)).toBeNull();
  });

  describe('G11. [C5a] fit on a one-chart tile (the twin of …fixes.test.tsx #3)', () => {
    const stubRect = (r: { width: number; height: number; top: number }) => {
      vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(() => ({
        ...r, left: 0, x: 0, y: r.top, right: r.width, bottom: r.top + r.height, toJSON: () => ({}),
      }) as DOMRect);
    };
    const vbsOf = (c: HTMLElement) => Array.from(tile(c, 'ZONE').querySelectorAll('svg')).map((s) => s.getAttribute('viewBox'));
    it('a laid-out grid → .ggw-grid--fit, the row var from the lib, the ONE chart fills its box, flexGrow 1', async () => {
      stubAll();
      stubRect({ width: 800, height: 150, top: 300 });
      const { container: c } = await mount();
      const g = grid(c);
      expect(g.classList.contains('ggw-grid--fit')).toBe(true);
      const shown = ggwDenseShown(GGW_DENSE_DEFAULT, ggwDenseMaxCols(800, 0), ggwDenseMaxRows(window.innerHeight, 0));
      const want = ggwFitRowHeight({ vh: window.innerHeight, top: 0, below: 0, gap: 0 }, shown.rows);
      expect(rowVar(g)).toBe(`${want}px`);
      expect(vbsOf(c)).toEqual([`0 0 620 ${ggwFitViewBoxH(800, 150, 620)}`]);
      expect((tile(c, 'ZONE').querySelector('.ggw-frame') as HTMLElement).style.flexGrow).toBe('1');
    });
    it('NEGATIVE: phone → no fit class, no row var, the phone height', async () => {
      stubAll(true);
      stubRect({ width: 400, height: 150, top: 300 });
      const { container: c } = await mount();
      expect(grid(c).classList.contains('ggw-grid--fit')).toBe(false);
      expect(rowVar(grid(c))).toBe('');
      expect(vbsOf(c)).toEqual([`0 0 620 ${GGW_CHART_H_PHONE}`]);
    });
    it('NEGATIVE: width 0 → no fit, the GGW_CHART_H 5-min height', async () => {
      stubAll();
      const { container: c } = await mount();
      expect(grid(c).classList.contains('ggw-grid--fit')).toBe(false);
      expect(vbsOf(c)).toEqual([`0 0 620 ${GGW_CHART_H['5m']}`]);
    });
  });

  describe('G12. [C5b, C5c] the pending tile lands ONE chart (the twins of …newest.test.tsx (j) / (l))', () => {
    const okRow = (s: string) => rename(RAW.rows[0], s);
    const pendRow = () => ({ ...rename(RAW.rows[0], 'PEND'), state: 'pending', frames: [], text: '⏳ served first read words', as_of_et: null });
    it('a pending row polls ?symbols=; its ok answer lands ONE 5-min chart in that tile, no click', async () => {
      serve = () => boardOf([okRow('ZONE'), pendRow()], { refresh_sec: 0, next_window_sec: null, pending_poll_sec: 5, pending_wait_max_sec: 90 });
      serveRows = () => res(boardOf([okRow('PEND')], { refresh_sec: 0, next_window_sec: null }));
      stubAll();
      const { container: c } = await mount();
      expect(tile(c, 'PEND').querySelectorAll('svg')).toHaveLength(0);
      await tick(5_100);
      for (let i = 0; i < 3; i += 1) await flush();
      expect(calls.some((x) => x.method === 'GET' && x.url.includes(`${GGW_PATH}?symbols=PEND`))).toBe(true);
      expect(tile(c, 'PEND').getAttribute('data-state')).toBe('ok');
      expect(tile(c, 'PEND').querySelectorAll('svg')).toHaveLength(1);
      expect(tfsIn(tile(c, 'PEND'))).toEqual(['5m']);
    });
    it('NEGATIVE: a pending-poll answer that lands after a newer full board is dropped — the tile stays ok with its one chart', async () => {
      let v = 1;
      let release: (r: Response) => void = () => {};
      serve = () => boardOf([okRow('ZONE'), v === 1 ? pendRow() : okRow('PEND')],
        { refresh_sec: 60, pending_poll_sec: 5, pending_wait_max_sec: 90 });
      serveRows = () => new Promise<Response>((r) => { release = r; });
      stubAll();
      const { container: c } = await mount();
      await tick(5_100);
      v = 2;
      await tick(55_000);
      for (let i = 0; i < 3; i += 1) await flush();
      expect(tile(c, 'PEND').getAttribute('data-state')).toBe('ok');
      release(res(boardOf([pendRow()], { pending_poll_sec: 5, pending_wait_max_sec: 90 })));
      for (let i = 0; i < 4; i += 1) await flush();
      expect(tile(c, 'PEND').getAttribute('data-state')).toBe('ok');
      expect(tile(c, 'PEND').querySelectorAll('svg')).toHaveLength(1);
    });
  });

  it('G13. the ▶ Rules panel opens inside a one-chart tile, as the last child of its chart window', async () => {
    stubAll();
    const { container: c } = await mount();
    fireEvent.click(screen.getByTestId('ggw-run-btn-ZONE'));
    await flush();
    const win = tile(c, 'ZONE').querySelector('[data-testid="ggw-one-charts"]') as HTMLElement;
    expect(win.lastElementChild?.getAttribute('data-testid')).toBe('ggw-run-ZONE');
    expect(tfsIn(win)).toEqual(['5m']);
  });

  it('G14. a dense tile whose 5-min frame is a served placeholder prints the served words — not blank, no other frame drawn', async () => {
    const WORDS = '⏳ served 5-min placeholder words';
    serve = () => {
      const b = boardOf();
      const f5 = b.rows[0].frames.find((f: any) => f.tf === '5m');
      f5.tile.bars = [];
      f5.empty_text = WORDS;
      return b;
    };
    stubAll();
    const { container: c } = await mount();
    const t = tile(c, 'ZONE');
    expect(tfsIn(t)).toEqual(['5m']);
    expect(screen.getByTestId('ggw-frame-empty-ZONE-5m').textContent).toContain(WORDS);
    expect(t.querySelectorAll('[data-tf="1m"], [data-tf="15m"]')).toHaveLength(0);
  });
});
