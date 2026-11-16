/* 👀 Gajjala's Watch LIVE on the board (2026-11-16, watch-live spec §3.5, WP-D).
 * Ajay: "Can you make the watch list charts live please" · "Realtime updates.. Like the 1 min chart I need it to be live
 * live.. per sec change" · "Also on the Watch list I need live volume to be shown at the bottom" · "Of each chart".
 *
 * The REAL board, the REAL hook (useGgwLive), the REAL reducer / splice (lib/ggwLive) and the REAL PatternChart, over a
 * clone of the 2026-11-15 fixture whose axes carry the live keys (start_epoch / frame_min, from_et as served). fetch is
 * a routed stub; the bus (lib/eventBus) is a hand-driven `subscribe` emitting `gajjala.update` payloads shaped like
 * backend chart_maps/gajjala/live_events.py. Every word is a stand-in for a served one. NEGATIVES: a print inside the
 * served 3-min bucket adds nothing there; the same / an older batch, another variant, an unknown symbol → unchanged; a
 * junk size → no column; a stale row → nothing moves and it goes dark; the next GET wins; owner_only → no POST, no
 * subscription; the 9 / 21 lines, blinkers, held and rang chips never move; a frame with no volume draws no pane; an
 * off-page tile never re-renders on a batch. */
import { act, fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import { CARD_LIVE_MS, GG_UPDATE_EVENT } from '../lib/cardLive';
import { GGW_LIVE_PATH, GGW_PATH, GGW_TAB } from '../lib/gajjalaWatch';
import { ggwBarStamp } from '../lib/ggwLive';
import { volumeColor } from '../lib/volumePane';

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
/* PatternChart's own call to boldNowLines, counted per tile (the off-page tile must never redraw on a batch). */
const nowCalls: any[][] = [];
vi.mock('../lib/chartMaps', async (importOriginal) => {
  const m: any = await importOriginal();
  return { ...m, boldNowLines: (...a: any[]) => { nowCalls.push(a); return m.boldNowLines(...a); } };
});

import GajjalaWatchBoard from './GajjalaWatchBoard';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
/* The fixture session 2026-11-13: 04:00 ET = 09:00 UTC (EST). The server serves this as the axis' start_epoch
 * (build.axis); a self-check below proves the stamp of the last stored bar's bucket equals its served `t`. */
const START = Date.UTC(2026, 10, 13, 9, 0, 0) / 1000;
const FM: Record<string, number> = { '1m': 1, '3m': 3, '5m': 5 };
const at = (min: number, sec = 0) => START + min * 60 + sec;   // a print `min` minutes + `sec` after 04:00 ET
const BLINK: Record<string, any> = {
  '1m': { state: 'crossed_up', tier: 'fresh', blink: true, closeness: 0, tf: '1m', text: '● served 1m fresh', title: 't' },
  '3m': { state: 'closing_in', tier: 'near', blink: true, closeness: 2, tf: '3m', text: '◐ served 3m near', title: 't' },
  '5m': { state: 'none', tier: null, blink: false, closeness: null, tf: '5m', text: null, title: 't' },
};
const RANG = { frame: '1m', at_et: '10:01', text: '🔔 served stand-in rang 10:01' };

/** The live board: OMH (ok; its 1-min frame ends at 10:28 = bucket 387, its 3-/5-min frames at 10:30), XYZQ
 *  (no_prints), NVDA (ok but stale), GP (an ok fresh clone of OMH at ×10 prices, 4th — off the page at 2 per screen).
 *  OMH's 5-min frame serves a 50-bar vol_avg. */
function liveBoard(mut: (b: any) => void = () => {}) {
  const b = clone(fixture) as any;
  b.rows = b.rows.filter((r: any) => r.state !== 'pending');
  delete b.pending_poll_sec;
  delete b.pending_wait_max_sec;
  const omh = b.rows[0];
  const one = omh.frames[0];
  one.tile.bars = one.tile.bars.slice(0, -2);
  one.axis.x = one.axis.x.slice(0, -2);
  for (const c of one.tile.curves) c.values = c.values.slice(0, -2);
  omh.as_of_et = '10:28';
  omh.rang = [RANG];
  for (const f of omh.frames) f.ema_blink = clone(BLINK[f.tf]);
  const five = omh.frames[2];
  five.tile.vol_avg = { period: 50, label: '50-bar avg volume', values: five.tile.bars.map(() => 50_000) };
  const gp = clone(omh);
  gp.symbol = 'GP';
  for (const f of gp.frames) {
    f.tile.symbol = 'GP';
    f.tile.bars = f.tile.bars.map((x: any) => ({ ...x, o: x.o * 10, h: x.h * 10, l: x.l * 10, c: x.c * 10 }));
    f.tile.curves = f.tile.curves.map((c: any) => ({ ...c, values: c.values.map((v: any) => (v == null ? v : v * 10)) }));
    f.tile.markers = [];
  }
  b.rows.push(gp);
  b.symbols = b.rows.map((r: any) => r.symbol);
  for (const r of b.rows) for (const f of r.frames) { f.axis.start_epoch = START; f.axis.frame_min = FM[f.tf]; }
  mut(b);
  return b;
}

type Call = { url: string; method: string; body?: string };
let boardNow: () => any = () => liveBoard();
let liveAnswer: () => any = () => ({ state: 'ok', stream: { on: true, word: 'served feed word: healthy', state: 'live' }, tab: GGW_TAB, symbols: [] });
let calls: Call[] = [];
function stubFetch() {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method || 'GET').toUpperCase();
    calls.push({ url, method, body: init?.body as string | undefined });
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) return { ok: true, json: async () => liveAnswer() } as unknown as Response;
    return { ok: true, json: async () => boardNow() } as unknown as Response;
  }));
}
const posts = () => calls.filter((c) => c.method === 'POST' && c.url.endsWith(GGW_LIVE_PATH));
const fullGets = () => calls.filter((c) => c.method === 'GET' && c.url.endsWith(GGW_PATH));
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
async function mount(per = 9) {
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala_watch&per=${per}`]}><GajjalaWatchBoard /></MemoryRouter>);
  await flush();
  await flush();
  return r;
}
const emit = (payload: unknown) => act(async () => {
  for (const fn of busHandlers.get(GG_UPDATE_EVENT) || []) fn({ type: GG_UPDATE_EVENT, ts: 0, payload });
});
const batch = (quotes: Record<string, unknown>, variant = GGW_TAB) => ({ kind: 'quotes', variant, quotes });
const q = (price: number, asOf: number, size: unknown = 500) => ({ price, as_of_epoch: asOf, vs: null, size });

const svgOf = (root: ParentNode, sym: string, tf: string) =>
  root.querySelector(`[data-testid="ggw-tile-${sym}"] .ggw-frame[data-tf="${tf}"] svg`) as SVGSVGElement;
/** Candle groups: a wick `line` then a body `rect`, nothing else (the PatternChart.frames1026 selector). */
const candles = (svg: Element) => Array.from(svg.querySelectorAll('g'))
  .filter((g) => g.children.length === 2 && g.children[0].tagName.toLowerCase() === 'line'
    && g.children[1].tagName.toLowerCase() === 'rect');
const vols = (svg: Element) => Array.from(svg.querySelectorAll('rect.pc-vol'));
const nowLabel = (svg: Element) => Array.from(svg.querySelectorAll('text')).map((t) => t.textContent || '')
  .find((t) => t.startsWith('now ')) ?? null;
const emaPts = (svg: Element) => Array.from(svg.querySelectorAll('polyline.pc-ema-bold-ema9'))
  .map((p) => (p.getAttribute('points') || '').trim().split(/\s+/).length);
const smaPts = (svg: Element) => Array.from(svg.querySelectorAll('path.pc-vol-sma'))
  .map((p) => (p.getAttribute('d') || '').split('L').length);
const snap = (svg: Element) => ({ c: candles(svg).length, v: vols(svg).length, now: nowLabel(svg), ema: emaPts(svg) });

beforeEach(() => {
  vi.useFakeTimers();
  busHandlers.clear();
  bus.subs = 0;
  nowCalls.length = 0;
  boardNow = () => liveBoard();
  liveAnswer = () => ({ state: 'ok', stream: { on: true, word: 'served feed word: healthy', state: 'live' }, tab: GGW_TAB, symbols: [] });
  stubFetch();
  vi.stubGlobal('EventSource', class {});
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('👀 LIVE fixture self-check', () => {
  it('the served start_epoch puts every frame\'s last stored bar at its served stamp (the server\'s own grid)', () => {
    const b = liveBoard();
    for (const r of b.rows) {
      for (const f of r.frames) {
        const last = f.tile.bars[f.tile.bars.length - 1].t;
        expect(ggwBarStamp(last.slice(0, 10), f.axis.from_et, f.axis.x[f.axis.x.length - 1], FM[f.tf])).toBe(last);
      }
    }
    expect(b.rows[0].frames[0].axis.x.at(-1)).toBe(387);
    expect(b.rows[0].frames[1].axis.x.at(-1)).toBe(129);
  });
});

describe('👀 LIVE — arm', () => {
  it('ONE register POST after the ok board, with HIS list; one subscription; renewed at CARD_LIVE_MS', async () => {
    await mount();
    expect(posts()).toHaveLength(1);
    expect(JSON.parse(posts()[0].body!)).toEqual({ symbols: ['OMH', 'XYZQ', 'NVDA', 'GP'] });
    expect(bus.subs).toBe(1);
    await advance(CARD_LIVE_MS + 10);
    expect(posts()).toHaveLength(2);
  });
  it('[C5] NEGATIVE: the minute GET serving the same list → no extra POST, no re-subscription', async () => {
    await mount();
    await advance(29_000);
    await advance(31_000);                       // 60 s: the second full GET + the 30 s renewal
    expect(fullGets()).toHaveLength(2);
    expect(posts()).toHaveLength(3);             // arm + 2 renewals (30 s, 60 s) — none from the GET
    expect(bus.subs).toBe(1);
  });
  it('NEGATIVE: owner_only → no POST, no subscription', async () => {
    boardNow = () => ({ state: 'owner_only', reason: 'Shown to the account owner only.', title: 'x' });
    await mount();
    await advance(CARD_LIVE_MS * 2);
    expect(posts()).toHaveLength(0);
    expect(bus.subs).toBe(0);
  });
  it('NEGATIVE: out of window (refresh_sec 0) → no POST, no subscription', async () => {
    boardNow = () => liveBoard((b) => { b.refresh_sec = 0; b.next_window_sec = null; });
    await mount();
    await advance(CARD_LIVE_MS * 2);
    expect(posts()).toHaveLength(0);
    expect(bus.subs).toBe(0);
  });
  it('NEGATIVE: no EventSource → no POST; the GETs exactly as the plain board counts them', async () => {
    vi.stubGlobal('EventSource', undefined);
    await mount();
    expect(fullGets()).toHaveLength(1);
    await advance(59_000);
    expect(fullGets()).toHaveLength(1);
    await advance(1_500);
    expect(fullGets()).toHaveLength(2);
    expect(calls.filter((c) => c.method !== 'GET')).toHaveLength(0);
    expect(bus.subs).toBe(0);
  });
});

describe('👀 LIVE — the forming candle and its volume column', () => {
  it('a batch in bucket x[last]+1 → one more candle, one more column (data-vol 500, volumeColor), now label = price', async () => {
    const { container } = await mount();
    const s1 = svgOf(container, 'OMH', '1m');
    const before = snap(s1);
    await emit(batch({ OMH: q(4.37, at(388, 30)) }));
    const s = svgOf(container, 'OMH', '1m');
    expect(candles(s)).toHaveLength(before.c + 1);
    expect(vols(s)).toHaveLength(before.v + 1);
    const col = vols(s).at(-1)!;
    expect(col.getAttribute('data-vol')).toBe('500');
    expect(col.getAttribute('fill')).toBe(volumeColor(4.37, 4.37));
    expect(nowLabel(s)).toBe('now 4.37');
    expect(before.now).not.toBe('now 4.37');
  });
  it('a second print in the same bucket moves the close and sums the column; the colour follows open vs close', async () => {
    const { container } = await mount();
    const before = snap(svgOf(container, 'OMH', '1m'));
    await emit(batch({ OMH: q(4.37, at(388, 10), 500) }));
    await emit(batch({ OMH: q(4.21, at(388, 40), 250) }));
    const s = svgOf(container, 'OMH', '1m');
    expect(candles(s)).toHaveLength(before.c + 1);
    const col = vols(s).at(-1)!;
    expect(col.getAttribute('data-vol')).toBe('750');
    expect(col.getAttribute('fill')).toBe(volumeColor(4.37, 4.21));
    expect(col.getAttribute('fill')).not.toBe(volumeColor(4.37, 4.37));
    expect(nowLabel(s)).toBe('now 4.21');
  });
  it('NEGATIVE: a print that opens a new 1-min bucket but sits inside the served 3-/5-min buckets → those charts gain nothing', async () => {
    const { container } = await mount();
    const b3 = snap(svgOf(container, 'OMH', '3m'));
    const b5 = snap(svgOf(container, 'OMH', '5m'));
    await emit(batch({ OMH: q(4.37, at(388, 30)) }));
    expect(snap(svgOf(container, 'OMH', '3m'))).toEqual(b3);
    expect(snap(svgOf(container, 'OMH', '5m'))).toEqual(b5);
  });
  it('a print past the served 3-/5-min buckets opens a candle on those charts too', async () => {
    const { container } = await mount();
    const b1 = snap(svgOf(container, 'OMH', '1m'));
    const b3 = snap(svgOf(container, 'OMH', '3m'));
    const b5 = snap(svgOf(container, 'OMH', '5m'));
    await emit(batch({ OMH: q(4.37, at(390, 30), 900) }));
    expect(candles(svgOf(container, 'OMH', '1m'))).toHaveLength(b1.c + 1);
    for (const [tf, b] of [['3m', b3], ['5m', b5]] as const) {
      const s = svgOf(container, 'OMH', tf);
      expect(candles(s)).toHaveLength(b.c + 1);
      expect(vols(s).at(-1)!.getAttribute('data-vol')).toBe('900');
      expect(nowLabel(s)).toBe('now 4.37');
    }
  });
  it('NEGATIVE: the same batch again, an older batch, variant gajjala, an unknown symbol → nothing moves', async () => {
    const { container } = await mount();
    await emit(batch({ OMH: q(4.37, at(388, 30)) }));
    const after = () => ['1m', '3m', '5m'].map((tf) => snap(svgOf(container, 'OMH', tf)));
    const once = after();
    expect(vols(svgOf(container, 'OMH', '1m')).at(-1)!.getAttribute('data-vol')).toBe('500');
    await emit(batch({ OMH: q(4.37, at(388, 30)) }));
    await emit(batch({ OMH: q(4.99, at(388, 5), 9_999) }));
    await emit(batch({ OMH: q(4.99, at(389, 30), 9_999) }, 'gajjala'));
    await emit(batch({ ZZZZ: q(4.99, at(389, 30), 9_999) }));
    expect(after()).toEqual(once);
    expect(vols(svgOf(container, 'OMH', '1m')).at(-1)!.getAttribute('data-vol')).toBe('500');
  });
  it('NEGATIVE: size "x" → the close moves on a new candle, no new column', async () => {
    const { container } = await mount();
    const before = snap(svgOf(container, 'OMH', '1m'));
    await emit(batch({ OMH: q(4.37, at(388, 30), 'x') }));
    const s = svgOf(container, 'OMH', '1m');
    expect(candles(s)).toHaveLength(before.c + 1);
    expect(vols(s)).toHaveLength(before.v);
    expect(nowLabel(s)).toBe('now 4.37');
  });
  it('the 9 / 21 lines, the blinkers, the held and the rang chips never move on a batch (EMA tip OFF)', async () => {
    const { container } = await mount();
    const tile = () => container.querySelector('[data-testid="ggw-tile-OMH"]')!;
    const texts = () => ({
      rang: Array.from(tile().querySelectorAll('.ggw-rang')).map((e) => e.textContent),
      held: Array.from(tile().querySelectorAll('.ggw-held')).map((e) => e.textContent),
      blink: Array.from(tile().querySelectorAll('[data-testid^="ggw-ema-blink-"]')).map((e) => `${e.getAttribute('data-testid')}|${e.textContent}`),
      ema: ['1m', '3m', '5m'].map((tf) => emaPts(svgOf(container, 'OMH', tf))),
    });
    const before = texts();
    expect(before.rang).toEqual([RANG.text]);
    expect(before.blink.length).toBeGreaterThan(0);
    await emit(batch({ OMH: q(4.37, at(390, 30)) }));
    expect(texts()).toEqual(before);
  });
  it('a served vol_avg keeps its line at the last CLOSED bar; with none the pane\'s own average takes the forming bar (HIS CALL #8)', async () => {
    const { container } = await mount();
    const sma5 = smaPts(svgOf(container, 'OMH', '5m'));
    const sma1 = smaPts(svgOf(container, 'OMH', '1m'));
    expect(sma5).toEqual([78]);
    await emit(batch({ OMH: q(4.37, at(390, 30)) }));
    expect(smaPts(svgOf(container, 'OMH', '5m'))).toEqual(sma5);
    expect(smaPts(svgOf(container, 'OMH', '1m'))).toEqual([sma1[0] + 1]);
  });
  it('the stretch view\'s charts move on a batch too', async () => {
    const { container, getByTestId } = await mount();
    fireEvent.click(getByTestId('ggw-stretch-btn-OMH'));
    await flush();
    const st = () => document.querySelector('[data-testid="ggw-stretch-charts"] .ggw-frame[data-tf="1m"] svg')!;
    const before = snap(st());
    await emit(batch({ OMH: q(4.37, at(388, 30)) }));
    expect(candles(st())).toHaveLength(before.c + 1);
    expect(nowLabel(st())).toBe('now 4.37');
    expect(candles(svgOf(container, 'OMH', '1m'))).toHaveLength(before.c + 1);
  });
});

describe('👀 LIVE — stale rows and the next GET', () => {
  it('[C2] NEGATIVE: a stale row → a batch changes nothing in its svgs and the ⚠️ stays', async () => {
    const { container } = await mount();
    const all = () => ['1m', '3m', '5m'].map((tf) => snap(svgOf(container, 'NVDA', tf)));
    const before = all();
    await emit(batch({ NVDA: q(170.5, at(400, 30)) }));
    expect(all()).toEqual(before);
    expect(container.querySelector('[data-testid="ggw-tile-NVDA"] [data-testid="ggw-asof"]')!.textContent!.startsWith('⚠️')).toBe(true);
  });
  it('[C2] a GET that turns a live row stale → its live tail disappears (stored bars only)', async () => {
    const { container } = await mount();
    const stored = snap(svgOf(container, 'OMH', '1m'));
    await emit(batch({ OMH: q(4.37, at(388, 30)) }));
    expect(candles(svgOf(container, 'OMH', '1m'))).toHaveLength(stored.c + 1);
    boardNow = () => liveBoard((b) => { b.rows[0].stale = true; b.rows[0].text = 'served stale sentence'; });
    await advance(60_100);
    expect(fullGets()).toHaveLength(2);
    expect(snap(svgOf(container, 'OMH', '1m'))).toEqual(stored);
    await emit(batch({ OMH: q(4.5, at(388, 50)) }));
    expect(snap(svgOf(container, 'OMH', '1m'))).toEqual(stored);
  });
  it('the server wins: the next GET serving the live bucket (v 123) → data-vol 123 and exactly one bar in that slot', async () => {
    const { container } = await mount();
    const stored = snap(svgOf(container, 'OMH', '1m'));
    await emit(batch({ OMH: q(4.37, at(388, 30)) }));
    boardNow = () => liveBoard((b) => {
      const f = b.rows[0].frames[0];
      const last = f.tile.bars.at(-1);
      f.tile.bars.push({ t: '2026-11-13 10:29', o: last.c, h: 4.4, l: last.c, c: 4.31, v: 123 });
      f.axis.x.push(388);
      for (const c of f.tile.curves) c.values.push(c.values.at(-1));
    });
    await advance(60_100);
    const s = svgOf(container, 'OMH', '1m');
    expect(candles(s)).toHaveLength(stored.c + 1);
    expect(vols(s)).toHaveLength(stored.v + 1);
    expect(vols(s).at(-1)!.getAttribute('data-vol')).toBe('123');
    expect(vols(s).some((r) => r.getAttribute('data-vol') === '500')).toBe(false);
    expect(nowLabel(s)).toBe('now 4.31');
  });
});

describe('👀 the volume pane on every Watch chart', () => {
  it('EVERY svg of the board has exactly one .pc-vol-pane', async () => {
    const { container } = await mount();
    const svgs = Array.from(container.querySelectorAll('.ggw-frame svg'));
    expect(svgs).toHaveLength(9);
    for (const s of svgs) expect(s.querySelectorAll('.pc-vol-pane')).toHaveLength(1);
  });
  it('NEGATIVE: a frame whose bars all carry v 0 draws no .pc-vol-pane and no rect.pc-vol', async () => {
    boardNow = () => liveBoard((b) => { for (const x of b.rows[0].frames[1].tile.bars) x.v = 0; });
    const { container } = await mount();
    const s = svgOf(container, 'OMH', '3m');
    expect(s.querySelector('.pc-vol-pane')).toBeNull();
    expect(vols(s)).toHaveLength(0);
    expect(svgOf(container, 'OMH', '1m').querySelectorAll('.pc-vol-pane')).toHaveLength(1);
  });
});

describe('👀 LIVE — the off-page tile and the feed word', () => {
  it('an off-page tile gets no live bars and its charts never re-render on a batch', async () => {
    const { container } = await mount(2);
    expect((container.querySelector('[data-testid="ggw-tile-GP"]') as HTMLElement).hidden).toBe(true);
    const gpO = liveBoard().rows[3].frames[0].tile.bars[0].o;
    const omhO = liveBoard().rows[0].frames[0].tile.bars[0].o;
    const drew = (o: number) => nowCalls.filter((a) => a[1]?.[0]?.o === o).length;
    const gpBefore = drew(gpO);
    const omhBefore = drew(omhO);
    const gpSnap = snap(svgOf(container, 'GP', '1m'));
    await emit(batch({ GP: q(43.7, at(388, 30)), OMH: q(4.37, at(388, 30)) }));
    expect(drew(gpO)).toBe(gpBefore);
    expect(snap(svgOf(container, 'GP', '1m'))).toEqual(gpSnap);
    expect(drew(omhO)).toBeGreaterThan(omhBefore);            // the shown tile does redraw (the spy is live)
  });
  it('the feed word prints only when degraded — one .ggw-line in the head (wraps at 430 px)', async () => {
    const a = await mount();
    expect(a.container.querySelector('[data-testid="ggw-feed-word"]')).toBeNull();
    a.unmount();
    liveAnswer = () => ({ state: 'ok', stream: { on: false, word: 'served feed word: degraded', state: 'kicked' } });
    const b = await mount();
    const w = b.container.querySelector('[data-testid="ggw-feed-word"]')!;
    expect(w.textContent).toBe('served feed word: degraded');
    expect(w.classList.contains('ggw-line')).toBe(true);
    expect(w.closest('.ggw-head')).not.toBeNull();
  });
});

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');

describe('👀 LIVE source guards', () => {
  it('the board imports useGgwLive and ggwRowLive — NEGATIVE: never useCardLive, patchTiles or mergeQuotesEvt', async () => {
    const src = await readSource('src/components/GajjalaWatchBoard.tsx');
    expect(src).toMatch(/import \{ useGgwLive[^}]*\} from '\.\.\/hooks\/useGgwLive'/);
    expect(src).toMatch(/\bggwRowLive\b/);
    expect(noComments(src)).toMatch(/ggwRowLive\(r\)/);
    for (const bad of ['useCardLive', 'patchTiles', 'mergeQuotesEvt']) expect(noComments(src)).not.toContain(bad);
  });
  it('the contract sentences stay in the board header', async () => {
    const src = await readSource('src/components/GajjalaWatchBoard.tsx');
    expect(src).toContain('No house chips on this tab');
    expect(src).toMatch(/his\s+\*?\s*list order orders this board/);   // the contracts.mjs pattern (the comment wraps)
  });
  it('NEGATIVE: no 📡 and no feed state word typed in the board or the hook', async () => {
    for (const f of ['src/components/GajjalaWatchBoard.tsx', 'src/hooks/useGgwLive.ts']) {
      const src = await readSource(f);
      expect(src).not.toContain('📡');
      expect(noComments(src)).not.toMatch(/['"`][^'"`\n]*\b(kicked|quiet|reconnect)/i);
    }
  });
  it('the hook renews on CARD_LIVE_MS imported from lib/cardLive (no number typed) and guards EventSource', async () => {
    const src = noComments(await readSource('src/hooks/useGgwLive.ts'));
    expect(src).toMatch(/import \{[^}]*CARD_LIVE_MS[^}]*\} from '\.\.\/lib\/cardLive'/);
    expect(src).toMatch(/typeof EventSource !== 'undefined'/);
    expect(src).not.toMatch(/\b30_?000\b/);
  });
});
