/* 🕯 2026-11-23 — the 1-min candle look. Ajay (a 👀 Watch tile, the 1-min chart on top): "On the 1 mins chart make the
 * bard lil more bright please." · "Make them more separted"; asked what, he answered "The candles".
 * PatternChart candleLook="1m": full-opacity candles (no EMA_BOLD_CANDLE_OPACITY dim), extended hours at
 * ONE_MIN_EXT_OPACITY, the ONE_MIN_CANDLE_UP / DN colours, a 1 device px crisp non-scaling wick, a crisp body of a whole
 * number of DEVICE px (css px × window.devicePixelRatio) with ONE_MIN_CANDLE_GAP_PX between neighbours; a slot under 2 device
 * px falls back to the house anti-aliased body (EMA_BOLD_CANDLE_BODY of the slot) in the 1m colours. The 👀 Frame passes it for a 1-minute frame ONLY (Watch
 * tile, card grid stack, ⤢ Watch view, ⤢ card view). NEGATIVES: no 1m look on 3/5/15-min frames, the rest of the svg
 * (hover readout, markers, curves, volume pane) unchanged, the prop has exactly one caller. Byte-identity of every non-1m
 * chart vs HEAD: PatternChart.one_min_off_2026_11_23.snapshot.test.tsx. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import { PatternChart } from './PatternChart';
import { GgwStretch, Tile } from './GajjalaWatchTile';
import { GGC_STRETCH_ORDER } from '../lib/gajjalaCardView';
import { parseGgw, type GgwBoard, type GgwRow } from '../lib/gajjalaWatch';
import {
  EMA_BOLD_CANDLE_BODY, EMA_BOLD_CANDLE_OPACITY, ONE_MIN_CANDLE_DN, ONE_MIN_CANDLE_GAP_PX, ONE_MIN_CANDLE_UP, ONE_MIN_EXT_OPACITY, ONE_MIN_WICK_PX,
  oneMinBodyWidth, oneMinDpr, type CmAxis, type CmTile,
} from '../lib/chartMaps';

/** jsdom's window.devicePixelRatio is 1; a test sets it (2 = his Retina Mac) and afterEach puts it back. */
const DPR0 = Object.getOwnPropertyDescriptor(window, 'devicePixelRatio');
const setDpr = (v: unknown) => Object.defineProperty(window, 'devicePixelRatio', { value: v, configurable: true, writable: true });
afterEach(() => {
  cleanup(); vi.restoreAllMocks(); document.body.style.overflow = '';
  if (DPR0) Object.defineProperty(window, 'devicePixelRatio', DPR0); else setDpr(1);
});

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
async function listDir(rel: string): Promise<string[]> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readdirSync(`${root}/${rel}`);
}
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');

const N = 40;
const stamp = (m: number) => `2026-11-20 ${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
/* bars 0..7 pre-market (s), the rest regular; alternating up / down closes. */
const bars = Array.from({ length: N }, (_, i) => ({
  t: stamp(9 * 60 + 22 + i), o: 10, h: 10.3, l: 9.8, c: i % 2 ? 9.9 : 10.1, v: 1000 + i, ...(i < 8 ? { s: 'pre' } : {}),
}));
const tile = (): CmTile => ({
  symbol: 'OMH', href: '/sepa/OMH', bars, bands: [], lines: [], stats: [], why: '',
  curves: [
    { tone: 'ema9', label: '9 EMA', values: bars.map((_, i) => 10 + i * 0.002) },
    { tone: 'ema21', label: '21 EMA', values: bars.map((_, i) => 10.01 + i * 0.001) },
  ],
  markers: [{ date: bars[12].t, kind: 'ema_cross_up', label: '🔀 9 EMA crossed above 21 EMA', price: 10.02 }],
} as CmTile);
const axis = (slots: number): CmAxis => ({
  slots, x: bars.map((_, i) => 320 % slots + i),
  shade: [{ from_slot: 0, to_slot: 328 % slots, kind: 'pre' }],
  ticks: [{ slot: 0, label: '04:00' }, { slot: slots, label: '20:00' }],
});
/** The svg renders `renderedW` css px wide (getBoundingClientRect), so px per viewBox unit = renderedW / W. */
const sized = (renderedW: number) => vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue(
  { width: renderedW, height: 200, top: 0, left: 0, right: renderedW, bottom: 200, x: 0, y: 0, toJSON: () => ({}) } as DOMRect);
const draw = (p: Record<string, unknown>) => render(<MemoryRouter><PatternChart tile={tile()} chartOnly emaStyle="bold" {...p} /></MemoryRouter>);
const groups1m = (c: Element) => Array.from(c.querySelectorAll('svg > g.pc-candle-1m'));
const candleGroups = (c: Element) => Array.from(c.querySelectorAll('svg > g'))
  .filter((g) => g.children.length === 2 && g.children[0].tagName === 'line' && g.children[1].tagName === 'rect');
const plotW = (c: Element) => Number((c.querySelector('svg > line') as SVGLineElement).getAttribute('x2'));

describe('oneMinBodyWidth (pure, DEVICE px)', () => {
  it('a whole number of device px, the slot minus at least the gap', () => {
    for (const [slotU, k, d] of [[4.6, 2, 1], [3.1, 1.3, 1], [10, 1, 1], [2.5, 1.3, 1], [1.1, 1, 2], [1.3, 1.3, 2], [0.8, 1, 3]]) {
      const dev = oneMinBodyWidth(slotU, k, d)! * k * d;
      expect(Math.abs(dev - Math.round(dev))).toBeLessThan(1e-9);
      expect(dev).toBeGreaterThanOrEqual(1);
      expect(slotU * k * d - dev).toBeGreaterThanOrEqual(ONE_MIN_CANDLE_GAP_PX - 1e-9);
    }
    expect(oneMinBodyWidth(4.6, 2) ! * 2).toBe(8);
  });
  it('Retina: dpr 2 at 1.1 css px per slot → a 1 device px body and a 1.2 device px gap (css px saw no gap)', () => {
    const w = oneMinBodyWidth(1.1, 1, 2)!;
    expect(w * 2).toBeCloseTo(1, 9);
    expect((1.1 - w) * 2).toBeCloseTo(1.2, 9);
    expect(oneMinBodyWidth(1.9, 1, 2)! * 2).toBeCloseTo(2, 9);                    /* 3.8 device px → 2 + 1.8 */
  });
  it('a slot of exactly 2 device px → the 1 px body + the 1 px gap', () => {
    expect(oneMinBodyWidth(2, 1, 1)).toBeCloseTo(1, 9);
    expect(oneMinBodyWidth(1, 1, 2)! * 2).toBeCloseTo(1, 9);
  });
  it('NEGATIVE: a slot under 2 device px → null (the caller keeps the anti-aliased body), never a crisp 1 px', () => {
    expect(oneMinBodyWidth(1.1, 1, 1)).toBeNull();
    expect(oneMinBodyWidth(1.9, 1, 1)).toBeNull();
    expect(oneMinBodyWidth(1.4, 1.3, 1)).toBeNull();
    expect(oneMinBodyWidth(0.58, 1.3, 2)).toBeNull();
    expect(oneMinBodyWidth(0.9, 1, 2)).toBeNull();
  });
  it('NEGATIVE: junk / unmeasured px-per-unit → 1 css px per unit; junk slot → null', () => {
    expect(oneMinBodyWidth(5, null)).toBe(4);
    expect(oneMinBodyWidth(5, 0)).toBe(4);
    expect(oneMinBodyWidth(5, Number.NaN)).toBe(4);
    expect(oneMinBodyWidth(Number.NaN, 2)).toBeNull();
    expect(oneMinBodyWidth(-3, 1)).toBeNull();
  });
  it('NEGATIVE: junk dpr (NaN, 0, undefined, <1, Infinity, a string) → treated as 1', () => {
    for (const v of [Number.NaN, 0, undefined, null, -2, 0.5, Number.POSITIVE_INFINITY, '2']) {
      expect(oneMinDpr(v)).toBe(1);
      expect(oneMinBodyWidth(5, 1, v)).toBe(oneMinBodyWidth(5, 1, 1));
      expect(oneMinBodyWidth(1.1, 1, v)).toBeNull();
    }
    expect(oneMinDpr(2)).toBe(2);
    expect(oneMinDpr(1.5)).toBe(1.5);
  });
  it('the look values are the documented ones', () => {
    expect(ONE_MIN_EXT_OPACITY).toBe(0.85);
    expect(ONE_MIN_CANDLE_GAP_PX).toBe(1);
    expect(ONE_MIN_WICK_PX).toBe(1);
    expect(ONE_MIN_CANDLE_UP).toBe('rgb(46, 214, 120)');
    expect(ONE_MIN_CANDLE_DN).toBe('rgb(255, 88, 88)');
  });
});

describe('PatternChart candleLook="1m"', () => {
  it('brighter: full opacity (no EMA_BOLD dim), ext-hours at ONE_MIN_EXT_OPACITY, the 1m colours', () => {
    const { container } = draw({ candleLook: '1m', axis: axis(120) });
    const g = groups1m(container);
    expect(g.length).toBe(N);
    expect(EMA_BOLD_CANDLE_OPACITY).toBeLessThan(1);
    g.forEach((el, i) => expect(Number(el.getAttribute('opacity'))).toBe(i < 8 ? ONE_MIN_EXT_OPACITY : 1));
    g.forEach((el, i) => {
      const col = i % 2 ? ONE_MIN_CANDLE_DN : ONE_MIN_CANDLE_UP;
      expect(el.children[0].getAttribute('stroke')).toBe(col);
      expect(el.children[1].getAttribute('fill')).toBe(col);
    });
  });
  it('separated: crisp edges, a 1 px non-scaling wick, a whole-px body < the slot by ≥ the gap (slot ≥ 2 px)', () => {
    sized(1240);
    const { container } = draw({ candleLook: '1m', axis: axis(120) });
    const k = 1240 / 620;
    const slotU = plotW(container) / 120;
    expect(slotU * k).toBeGreaterThan(2);
    for (const el of groups1m(container)) {
      const [wick, body] = el.children;
      expect(wick.getAttribute('stroke-width')).toBe(String(ONE_MIN_WICK_PX));
      expect(wick.getAttribute('vector-effect')).toBe('non-scaling-stroke');
      expect(wick.getAttribute('shape-rendering')).toBe('crispEdges');
      expect(body.getAttribute('shape-rendering')).toBe('crispEdges');
      const px = Number(body.getAttribute('width')) * k;
      expect(Math.abs(px - Math.round(px))).toBeLessThan(1e-6);
      expect(slotU * k - px).toBeGreaterThanOrEqual(ONE_MIN_CANDLE_GAP_PX - 1e-6);
    }
    /* the body is centred on its slot: neighbours' bodies never touch */
    const r = groups1m(container).map((el) => el.children[1]);
    for (let i = 1; i < r.length; i += 1) {
      const prevRight = Number(r[i - 1].getAttribute('x')) + Number(r[i - 1].getAttribute('width'));
      expect((Number(r[i].getAttribute('x')) - prevRight) * k).toBeGreaterThanOrEqual(ONE_MIN_CANDLE_GAP_PX - 1e-6);
    }
  });
  it('the Watch fit (viewW, 1 unit = 1.3 px) on a 960-slot day at dpr 1: slot under 2 px → the anti-aliased fallback', () => {
    sized(1800);
    const { container } = draw({ candleLook: '1m', axis: axis(960), viewW: Math.round(1800 / 1.3) });
    const W = Math.round(1800 / 1.3);
    const k = 1800 / W;
    const slotU = plotW(container) / 960;
    expect(slotU * k).toBeLessThan(2);
    for (const el of groups1m(container)) {
      expect(el.children[1].hasAttribute('shape-rendering')).toBe(false);
      expect(Number(el.children[1].getAttribute('width'))).toBeCloseTo(slotU * EMA_BOLD_CANDLE_BODY, 9);
    }
  });
  it('a window resize re-measures the svg (wider box → wider whole-px bodies); no ResizeObserver of its own', () => {
    const ro = vi.fn();
    vi.stubGlobal('ResizeObserver', class { constructor() { ro(); } observe() {} unobserve() {} disconnect() {} });
    let w = 620;
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(() => (
      { width: w, height: 200, top: 0, left: 0, right: w, bottom: 200, x: 0, y: 0, toJSON: () => ({}) } as DOMRect));
    const { container } = draw({ candleLook: '1m', axis: axis(120) });
    const slotU = plotW(container) / 120;
    const body = () => Number(groups1m(container)[20].children[1].getAttribute('width'));
    expect(body()).toBeCloseTo(Math.max(1, Math.floor(slotU - ONE_MIN_CANDLE_GAP_PX)), 9);
    w = 1860;
    act(() => { window.dispatchEvent(new Event('resize')); });
    expect(body() * 3).toBeCloseTo(Math.max(1, Math.floor(slotU * 3 - ONE_MIN_CANDLE_GAP_PX)), 6);
    expect(ro).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
  /* rendered width giving `css` css px per slot on a `slots` axis (plotW is in viewBox units, independent of the box) */
  const widthFor = (css: number, slots: number) => {
    const pw = plotW(draw({ candleLook: '1m', axis: axis(slots) }).container);
    cleanup();
    return (css * slots / pw) * 620;
  };
  it('Retina (dpr 2) at 1.1 css px per slot: crisp 1 device px bodies with a gap, a 1 device px wick', () => {
    const rw = widthFor(1.1, 120);
    setDpr(2);
    sized(rw);
    const { container } = draw({ candleLook: '1m', axis: axis(120) });
    const k = rw / 620;
    const slotU = plotW(container) / 120;
    expect(slotU * k).toBeCloseTo(1.1, 9);
    const g = groups1m(container);
    expect(g.length).toBe(N);
    for (const el of g) {
      const [wick, body] = el.children;
      expect(wick.getAttribute('stroke-width')).toBe(String(ONE_MIN_WICK_PX / 2));
      expect(body.getAttribute('shape-rendering')).toBe('crispEdges');
      expect(Number(body.getAttribute('width')) * k * 2).toBeCloseTo(1, 6);
    }
    const r = g.map((el) => el.children[1]);
    for (let i = 1; i < r.length; i += 1) {
      const prevRight = Number(r[i - 1].getAttribute('x')) + Number(r[i - 1].getAttribute('width'));
      expect((Number(r[i].getAttribute('x')) - prevRight) * k * 2).toBeGreaterThanOrEqual(ONE_MIN_CANDLE_GAP_PX - 1e-6);
    }
  });
  it('NEGATIVE: dpr 1 at 1.1 css px per slot → the anti-aliased body (0.8 of the slot), still the 1m colours + opacity', () => {
    const rw = widthFor(1.1, 120);
    setDpr(1);
    sized(rw);
    const { container } = draw({ candleLook: '1m', axis: axis(120) });
    const slotU = plotW(container) / 120;
    const g = groups1m(container);
    expect(g.length).toBe(N);
    g.forEach((el, i) => {
      const [wick, body] = el.children;
      expect(body.hasAttribute('shape-rendering')).toBe(false);
      expect(Number(body.getAttribute('width'))).toBeCloseTo(slotU * EMA_BOLD_CANDLE_BODY, 9);
      expect(wick.getAttribute('stroke-width')).toBe(String(ONE_MIN_WICK_PX));
      const col = i % 2 ? ONE_MIN_CANDLE_DN : ONE_MIN_CANDLE_UP;
      expect(body.getAttribute('fill')).toBe(col);
      expect(Number(el.getAttribute('opacity'))).toBe(i < 8 ? ONE_MIN_EXT_OPACITY : 1);
    });
  });
  it('dpr 1 at 2.1 css px per slot → a crisp 1 px body + a ≥ 1 px gap', () => {
    const rw = widthFor(2.1, 120);
    setDpr(1);
    sized(rw);
    const { container } = draw({ candleLook: '1m', axis: axis(120) });
    const k = rw / 620;
    for (const el of groups1m(container)) {
      expect(el.children[1].getAttribute('shape-rendering')).toBe('crispEdges');
      expect(Number(el.children[1].getAttribute('width')) * k).toBeCloseTo(1, 6);
    }
  });
  it('NEGATIVE: junk dpr (NaN, 0, undefined) renders exactly the dpr 1 markup', () => {
    const rw = widthFor(1.1, 120);
    sized(rw);
    setDpr(1);
    const ref = draw({ candleLook: '1m', axis: axis(120) }).container.innerHTML;
    cleanup();
    for (const v of [Number.NaN, 0, undefined]) {
      setDpr(v);
      expect(draw({ candleLook: '1m', axis: axis(120) }).container.innerHTML).toBe(ref);
      cleanup();
    }
  });
  it('NEGATIVE: without the prop the dpr is never read — dpr 2 and dpr 1 give the same markup', () => {
    sized(1240);
    setDpr(1);
    const ref = draw({ axis: axis(120) }).container.innerHTML;
    cleanup();
    setDpr(2);
    expect(draw({ axis: axis(120) }).container.innerHTML).toBe(ref);
  });
  it('hover keeps the house 0.82 dim on the other candles', () => {
    sized(1240);
    const { container } = draw({ candleLook: '1m', axis: axis(120) });
    const svg = container.querySelector('svg')!;
    const c20 = groups1m(container)[20].children[0] as SVGLineElement;
    const x = Number(c20.getAttribute('x1')) * 2;
    fireEvent.mouseMove(svg, { clientX: x, clientY: 50 });
    const g = groups1m(container);
    expect(Number(g[20].getAttribute('opacity'))).toBe(1);
    expect(Number(g[25].getAttribute('opacity'))).toBe(0.82);
    expect(Number(g[2].getAttribute('opacity'))).toBeCloseTo(0.82 * ONE_MIN_EXT_OPACITY, 9);
  });
  it('NEGATIVE: everything that is not a candle is the same markup with and without the prop', () => {
    const strip = (c: Element) => { candleGroups(c).forEach((g) => g.remove()); return c.innerHTML; };
    const a = draw({ axis: axis(120) });
    const off = strip(a.container);
    cleanup();
    const b = draw({ candleLook: '1m', axis: axis(120) });
    expect(candleGroups(b.container).length).toBe(N);
    expect(strip(b.container)).toBe(off);
  });
  it('NEGATIVE: without the prop the bold candles keep EMA_BOLD_CANDLE_OPACITY, the tokens, no crispEdges', () => {
    const { container } = draw({ axis: axis(120) });
    expect(groups1m(container).length).toBe(0);
    const g = candleGroups(container);
    expect(Number(g[20].getAttribute('opacity'))).toBe(EMA_BOLD_CANDLE_OPACITY);
    expect(g[20].children[1].getAttribute('fill')).toBe('var(--positive, #22c55e)');
    expect(g[21].children[1].getAttribute('fill')).toBe('var(--negative, #ef4444)');
    expect(container.innerHTML).not.toContain('crispEdges');
  });
});

/* ── the surfaces: only the 1-minute frame gets the look ─────────────────────────────────────────────────────────── */
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const S = (fixture as any).rows[0].symbol as string;
const watchRow = (): GgwRow => (parseGgw(clone(fixture)) as GgwBoard).rows[0];
function cardRow(): GgwRow {
  const raw = clone(fixture) as any;
  const r = raw.rows[0];
  for (const f of r.frames) if (f.tf === '3m') f.tf = '15m';
  raw.rows = [r];
  return (parseGgw(raw) as GgwBoard).rows[0];
}
const lookByTf = () => Object.fromEntries(Array.from(document.querySelectorAll('figure.ggw-frame')).map((f) => [
  f.getAttribute('data-tf'), { look: f.querySelectorAll('svg > g.pc-candle-1m').length, candles: candleGroups(f).length },
]));
const expectOnlyOneMin = (tfs: string[]) => {
  const m = lookByTf();
  expect(Object.keys(m).sort()).toEqual([...tfs].sort());
  for (const tf of tfs) {
    expect(m[tf].candles).toBeGreaterThan(0);
    expect(m[tf].look).toBe(tf === '1m' ? m[tf].candles : 0);
  }
};

describe('🕯 the prop reaches the 1-minute frame ONLY', () => {
  it('👀 Watch tile (1m on top, the pair under it)', () => {
    render(<MemoryRouter><Tile row={watchRow()} phone={false} fit={false} removeLabel="Remove" focused={false} busy={false} /></MemoryRouter>);
    expectOnlyOneMin(['1m', '3m', '5m']);
  });
  it('🚩 / 🧪 card grid tile (stacked 15 / 5 / 1)', () => {
    render(<MemoryRouter><Tile row={cardRow()} phone={false} fit={false} removeLabel={null} focused={false} busy={false}
                               stack order={GGC_STRETCH_ORDER} /></MemoryRouter>);
    expectOnlyOneMin(['15m', '5m', '1m']);
  });
  it('⤢ the Watch full-screen view', () => {
    render(<MemoryRouter><GgwStretch row={watchRow()} phone={false} removeLabel="Remove" onClose={() => {}} onStep={null} /></MemoryRouter>);
    expectOnlyOneMin(['1m', '3m', '5m']);
  });
  it('⤢ the card view (GgCardView → GgwStretch kind="card")', () => {
    render(<MemoryRouter><GgwStretch row={cardRow()} phone={false} removeLabel={null} onClose={() => {}} onStep={null}
                                     order={GGC_STRETCH_ORDER} kind="card" /></MemoryRouter>);
    expectOnlyOneMin(['15m', '5m', '1m']);
  });
  it('NEGATIVE: a "1m" frame relabelled 2m gets no 1m look (the frame\'s served tf decides, not its bars)', () => {
    const raw = clone(fixture) as any;
    for (const f of raw.rows[0].frames) if (f.tf === '1m') f.tf = '2m';
    const row = (parseGgw(raw) as GgwBoard).rows[0];
    render(<MemoryRouter><Tile row={row} phone={false} fit={false} removeLabel="Remove" focused={false} busy={false} stack
                               order={['2m', '3m', '5m']} /></MemoryRouter>);
    expect(document.querySelectorAll('svg > g.pc-candle-1m').length).toBe(0);
    expect(screen.getByTestId(`ggw-tile-${S}`)).toBeTruthy();
  });
  it('NEGATIVE: candleLook has exactly one caller (the 👀 Frame), keyed on f.tf === \'1m\'; GgCardGrid / GgCardView reach it through Tile / GgwStretch', async () => {
    const callers: string[] = [];
    for (const dir of ['src/components', 'src/pages']) {
      for (const f of (await listDir(dir)).filter((x) => x.endsWith('.tsx') && !x.includes('.test.'))) {
        if (f === 'PatternChart.tsx') continue;
        if (noComments(await readSource(`${dir}/${f}`)).includes('candleLook')) callers.push(f);
      }
    }
    expect(callers).toEqual(['GajjalaWatchTile.tsx']);
    const src = noComments(await readSource('src/components/GajjalaWatchTile.tsx'));
    expect(src).toContain("candleLook={f.tf === '1m' ? '1m' : undefined}");
    expect((src.match(/candleLook=/g) || []).length).toBe(1);
    expect(noComments(await readSource('src/components/GgCardGrid.tsx'))).toMatch(/import \{ Tile \} from '\.\/GajjalaWatchTile'/);
    expect(noComments(await readSource('src/components/GgCardView.tsx'))).toMatch(/import \{ GgwStretch, usePhone \} from '\.\/GajjalaWatchTile'/);
  });
});
