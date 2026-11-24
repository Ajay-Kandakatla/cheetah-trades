/* 📈📐 PatternChart — 👀 Watch VWAP + daily zones (2026-11-23, spec vwapzones §3.8, package fe-chart).
 * Ajay 2026-11-23: "can you add vwap and supply demand zone in the daily time frame on the watch list please" · "Add vwap
 * and supply demand too". A `ctx` board band draws the dashed OUTLINE where it falls, with a quiet gutter word, never an
 * edge marker [C9]; a zero-width one is one dashed line [C3]; its title and hover chip print the served label verbatim
 * [C6]. Under bold the VWAP draws thin over the candles and under the two EMAs. NEGATIVES: a tile without either draws
 * exactly as before; a board band WITHOUT ctx keeps its edge marker, title and chip. */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart, bandText } from './PatternChart';
import {
  EMA_BOLD, VWAP_LINE_W, barDomain, toneColor, yFor,
  type CmBand, type CmCurve, type CmTile,
} from '../lib/chartMaps';

afterEach(() => cleanup());

const N = 40;
const stamp = (m: number) => `2026-11-20 ${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const mkBars = (base: number, span: number, v = 1000) => Array.from({ length: N }, (_, i) => ({
  t: stamp(9 * 60 + 31 + i), o: base, h: base + span, l: base - span * 0.66, c: base + (i % 3) * span / 6, v,
}));
const bars = mkBars(10, 0.3);
const EMAS: CmCurve[] = [
  { tone: 'ema9', label: '9 EMA', values: bars.map((_, i) => 10 + i * 0.002) },
  { tone: 'ema21', label: '21 EMA', values: bars.map((_, i) => 10.01 + i * 0.001) },
];
const VWAP: CmCurve = { tone: 'vwap', label: 'VWAP', values: bars.map((_, i) => (i < 5 ? null : 10.05)) };
const MARKERS = [
  { date: bars[10].t, kind: 'ema_cross_up', label: '🔀 9 EMA crossed above 21 EMA', price: 10.02 },
  { date: bars[20].t, kind: 'ema_cross_dn', label: '🔀 9 EMA crossed under 21 EMA' },
];
const IN: CmBand = { kind: 'board_demand', lo: 9.9, hi: 10.0, label: 'Daily demand 9.90–10.00', gutter: 'demand', ctx: true };
const ZERO: CmBand = { kind: 'board_supply', lo: 10.1, hi: 10.1, label: 'Daily supply 10.10', gutter: 'supply', ctx: true };
const OUT: CmBand = { kind: 'board_demand', lo: 12.0, hi: 12.1, label: 'Daily demand 12.00–12.10', gutter: 'demand', ctx: true };

const tile = (over: Partial<CmTile> = {}): CmTile => ({
  symbol: 'OMH', href: '/sepa/OMH', bars, bands: [], lines: [], stats: [], why: '',
  curves: EMAS, markers: MARKERS, ...over,
});
const draw = (t: CmTile, props: Record<string, unknown> = {}) =>
  render(<MemoryRouter><PatternChart tile={t} chartOnly {...props} /></MemoryRouter>);
const texts = (c: HTMLElement) => Array.from(c.querySelectorAll('svg text')).map((n) => n.textContent || '');
const order = (root: Element, a: Element, b: Element) => {
  const all = Array.from(root.querySelectorAll('*'));
  return all.indexOf(a) < all.indexOf(b);
};
const candles = (c: HTMLElement) => Array.from(c.querySelectorAll('svg > g'))
  .filter((g) => g.children.length === 2 && g.children[0].tagName === 'line' && g.children[1].tagName === 'rect');
const candleYs = (c: HTMLElement) => candles(c).map((g) => {
  const [w, r] = Array.from(g.children);
  return [w.getAttribute('y1'), w.getAttribute('y2'), r.getAttribute('y'), r.getAttribute('height')].join('|');
});
/** main's band text, retyped here ONLY as the negative's reference. */
const mainText = (b: CmBand, name: string) => `${b.label || name} ${b.lo.toFixed(2)}–${b.hi.toFixed(2)}`;

// 🟩 CHANGED 2026-11-23 (his "subtle green glassy" — was a dashed outline): a ctx band draws as GLASS.
describe('ctx board band — glass where it falls, quiet gutter word', () => {
  it('inside the range: the GLASS rect (gradient fill, no stroke, no dash), solid edges, and its gutter word in the zone colour', () => {
    const { container } = draw(tile({ bands: [IN] }));
    const g = container.querySelector('g[data-band-kind="board_demand"]')!;
    expect(g).toBeTruthy();
    expect(g.getAttribute('data-band-look')).toBe('glass');
    const r = g.querySelector('rect')!;
    expect(r.getAttribute('fill')).toMatch(/^url\(#pc-gge-[A-Za-z0-9_-]+-glass-board_demand\)$/);
    expect(r.getAttribute('stroke')).toBe('none');
    expect(r.getAttribute('stroke-dasharray')).toBeNull();
    const edges = Array.from(g.querySelectorAll('line'));
    expect(edges.length).toBe(2);
    for (const e of edges) { expect(e.getAttribute('stroke')).toBe('var(--positive, #22c55e)'); expect(e.getAttribute('stroke-dasharray')).toBeNull(); }
    const id = r.getAttribute('fill')!.slice(5, -1);
    const grad = container.querySelector(`linearGradient[id="${id}"]`)!;
    expect(grad).toBeTruthy();
    expect(grad.querySelectorAll('stop').length).toBe(2);
    const word = Array.from(container.querySelectorAll('svg text')).find((n) => n.textContent === 'demand');
    expect(word).toBeTruthy();
    expect(word!.getAttribute('fill')).toBe(toneColor('zone_demand'));
  });
  it('[C3] a zero-width ctx band draws a 1-unit rect with its gutter word', () => {
    const { container } = draw(tile({ bands: [ZERO] }));
    const r = container.querySelector('g[data-band-kind="board_supply"] rect')!;
    expect(r).toBeTruthy();
    expect(r.getAttribute('height')).toBe('1');
    expect(r.getAttribute('fill')).toMatch(/-glass-board_supply\)$/);   // 🟩 supply glass in ITS colour, never green
    expect(r.getAttribute('stroke-dasharray')).toBeNull();
    const word = Array.from(container.querySelectorAll('svg text')).find((n) => n.textContent === 'supply');
    expect(word!.getAttribute('fill')).toBe(toneColor('zone_supply'));
  });
  it('[C9] outside the range: no rect, no gutter word and NO "above / below this chart" edge marker', () => {
    const { container } = draw(tile({ bands: [OUT] }));
    expect(container.querySelector('g[data-band-kind="board_demand"]')).toBeNull();
    expect(container.querySelector('g[data-band-kind="board_demand-off"]')).toBeNull();
    const ts = texts(container);
    expect(ts).not.toContain('demand');
    expect(ts.some((s) => s.includes('this chart'))).toBe(false);
  });
  it('NEGATIVE: a board band WITHOUT ctx outside the range still prints its edge marker (today\'s rule kept)', () => {
    const plain: CmBand = { kind: 'board_demand', lo: 12.0, hi: 12.1, label: 'Board demand' };
    const { container } = draw(tile({ bands: [plain] }));
    const off = container.querySelector('g[data-band-kind="board_demand-off"]')!;
    expect(off).toBeTruthy();
    expect(off.textContent).toBe('Board demand 12.00–12.10 — above this chart');
  });
  it('candle y positions are equal with and without ctx bands (they never move the scale)', () => {
    const without = candleYs(draw(tile()).container);
    cleanup();
    const withCtx = candleYs(draw(tile({ bands: [IN, ZERO, OUT, { ...OUT, kind: 'board_supply', lo: 8.5, hi: 8.6 }] })).container);
    expect(without.length).toBe(N);
    expect(withCtx).toEqual(without);
  });
  it('NEGATIVE: a ctx band with no gutter word adds no label; a non-ctx band never adds one', () => {
    const { container } = draw(tile({ bands: [{ ...IN, gutter: undefined }, { kind: 'board_supply', lo: 10.1, hi: 10.2, gutter: 'supply' }] }));
    const ts = texts(container);
    expect(ts).not.toContain('demand');
    expect(ts).not.toContain('supply');
  });
});

describe('[C6] title and hover chip of a ctx band = the served label exactly', () => {
  const flat = mkBars(10, 0.3, 0);   // no volume pane → the price pane is the whole height
  const t0 = (bands: CmBand[]): CmTile => tile({ bars: flat, bands, curves: [], markers: [] });
  const hoverAt = (c: HTMLElement, t: CmTile, price: number) => {
    const svg = c.querySelector('svg')!;
    svg.getBoundingClientRect = () => ({
      left: 0, top: 0, width: 620, height: 190, right: 620, bottom: 190, x: 0, y: 0, toJSON: () => ({}),
    }) as DOMRect;
    const d = barDomain(t.bars, t.bands, t.lines, 6, t.curves);
    fireEvent.mouseMove(svg, { clientX: 100, clientY: yFor(price, d, 190, 10) });
    return Array.from(c.querySelectorAll('g[pointer-events="none"] text')).map((n) => n.textContent || '');
  };
  it('ctx: <title> === label and the hover chip === label (no second range)', () => {
    const t = t0([IN]);
    const { container } = draw(t);
    expect(container.querySelector('g[data-band-kind="board_demand"] rect title')!.textContent).toBe('Daily demand 9.90–10.00');
    const chip = hoverAt(container, t, 9.95);
    expect(chip).toContain('Daily demand 9.90–10.00');
    expect(chip.some((s) => s.includes('10.00–') || s.split('–').length > 2)).toBe(false);
  });
  it('[C3] a zero-width ctx band\'s title prints its one served price', () => {
    const { container } = draw(t0([ZERO]));
    expect(container.querySelector('g[data-band-kind="board_supply"] rect title')!.textContent).toBe('Daily supply 10.10');
  });
  it('NEGATIVE: a non-ctx band\'s title and chip are byte-equal to main', () => {
    const b: CmBand = { kind: 'board_demand', lo: 9.9, hi: 10.0, label: 'Board demand' };
    const t = t0([b]);
    const { container } = draw(t);
    expect(container.querySelector('g[data-band-kind="board_demand"] rect title')!.textContent)
      .toBe(mainText(b, 'Board demand'));
    expect(hoverAt(container, t, 9.95)).toContain('Board demand 9.90–10.00');
  });
  it('bandText: ctx + label → verbatim; NEGATIVES: ctx without a label, or no ctx → main\'s text', () => {
    expect(bandText(IN)).toBe(IN.label);
    expect(bandText({ ...IN, label: undefined })).toBe('Board demand 9.90–10.00');
    expect(bandText({ ...IN, label: '' })).toBe('Board demand 9.90–10.00');
    expect(bandText({ ...IN, ctx: false })).toBe('Daily demand 9.90–10.00 9.90–10.00');
    expect(bandText({ kind: 'demand', lo: 1, hi: 2 })).toBe('Support 1.00–2.00');
  });
});

describe('VWAP under bold', () => {
  it('.pc-vwap after the candles and before .pc-ema-bold, width VWAP_LINE_W, non-scaling, data-tone vwap', () => {
    const { container } = draw(tile({ curves: [...EMAS, VWAP] }), { emaStyle: 'bold' });
    const vw = Array.from(container.querySelectorAll('polyline.pc-vwap'));
    expect(vw).toHaveLength(1);
    const p = vw[0];
    expect(p.getAttribute('stroke-width')).toBe(String(VWAP_LINE_W));
    expect(p.getAttribute('vector-effect')).toBe('non-scaling-stroke');
    expect(p.getAttribute('data-tone')).toBe('vwap');
    expect(p.getAttribute('fill')).toBe('none');
    const lastCandle = candles(container).pop()!;
    const bold = container.querySelector('g.pc-ema-bold')!;
    expect(order(container, lastCandle, p)).toBe(true);
    expect(order(container, p, bold)).toBe(true);
    expect(order(container, p, container.querySelector('polyline.pc-ema-bold-ema21')!)).toBe(true);
  });
  it('[C9] its colour differs from both bold EMAs, the now line and the two board band colours', () => {
    const { container } = draw(tile({ curves: [...EMAS, VWAP] }), { emaStyle: 'bold' });
    const c = container.querySelector('polyline.pc-vwap')!.getAttribute('stroke');
    expect(c).toBe(toneColor('vwap'));
    const now = container.querySelector('line[data-tone="now"]')!.getAttribute('stroke');
    for (const other of [EMA_BOLD.ema9.color, EMA_BOLD.ema21.color, now, 'var(--positive, #22c55e)', 'var(--negative, #ef4444)']) {
      expect(c).not.toBe(other);
    }
  });
  it('nulls split the path', () => {
    const split: CmCurve = { tone: 'vwap', label: 'VWAP', values: bars.map((_, i) => (i === 20 ? null : 10.05)) };
    const { container } = draw(tile({ curves: [...EMAS, split] }), { emaStyle: 'bold' });
    expect(container.querySelectorAll('polyline.pc-vwap')).toHaveLength(2);
  });
  it('NEGATIVE: all-null / NaN values → no polyline and no "NaN" in the markup', () => {
    for (const values of [bars.map(() => null), bars.map(() => NaN)]) {
      const { container } = draw(tile({ curves: [...EMAS, { tone: 'vwap', label: 'VWAP', values }] }), { emaStyle: 'bold' });
      expect(container.querySelector('polyline.pc-vwap')).toBeNull();
      expect(container.innerHTML).not.toContain('NaN');
      expect(texts(container).some((s) => s.startsWith('VWAP'))).toBe(false);
      cleanup();
    }
  });
  it('gutter "VWAP 0.288" under $1', () => {
    const cheap = mkBars(0.28, 0.01);
    const t = tile({ bars: cheap, curves: [{ tone: 'vwap', label: 'VWAP', values: cheap.map(() => 0.288) }], markers: [] });
    const { container } = draw(t, { emaStyle: 'bold' });
    expect(texts(container)).toContain('VWAP 0.288');
  });
  it('NEGATIVE: not bold → the ordinary curve pass (no .pc-vwap, toneColor at 1.1)', () => {
    const { container } = draw(tile({ curves: [...EMAS, VWAP] }));
    expect(container.querySelector('polyline.pc-vwap')).toBeNull();
    const p = Array.from(container.querySelectorAll('polyline')).find((n) => n.getAttribute('stroke') === toneColor('vwap'));
    expect(p).toBeTruthy();
    expect(p!.getAttribute('stroke-width')).toBe('1.1');
  });
});

describe('NEGATIVE: a tile with neither renders as before', () => {
  it('no .pc-vwap and no zone word', () => {
    const { container } = draw(tile(), { emaStyle: 'bold' });
    expect(container.querySelector('.pc-vwap')).toBeNull();
    const ts = texts(container);
    expect(ts).not.toContain('demand');
    expect(ts).not.toContain('supply');
  });
  it('the dashed now line, the bold 9 / 21 paths and the cross diamonds are in the markup exactly as without the new layers', () => {
    /* x is normalised out: the right gutter is sized from the labels it keeps (gutterWidth), so a new gutter word may
     * re-size it and shift every x by the same plot-width ratio — the price mapping (every y) and every attribute stay. */
    const noX = (html: string) => html
      .replace(/ x[12]="[^"]*"/g, '')
      .replace(/points="([^"]*)"/g, (_, pts: string) => `points="${pts.split(' ').map((p) => p.split(',')[1]).join(' ')}"`);
    const grab = (c: HTMLElement) => [
      c.querySelector('line[data-tone="now"]')!.outerHTML,
      c.querySelector('g.pc-ema-bold')!.outerHTML,
      c.querySelector('g.pc-ema-cross-layer')!.outerHTML,
    ].map(noX);
    const before = grab(draw(tile(), { emaStyle: 'bold' }).container);
    cleanup();
    const after = grab(draw(tile({ curves: [...EMAS, VWAP], bands: [IN, ZERO, OUT] }), { emaStyle: 'bold' }).container);
    expect(after).toEqual(before);
    expect(before[0]).toContain('stroke-dasharray="5,4"');
    expect(before[2]).toContain('pc-ema-cross-up');
  });
  it('NEGATIVE: with no ctx band and no vwap curve the whole svg markup is identical across renders of main\'s inputs', () => {
    const a = draw(tile({ bands: [{ kind: 'board_demand', lo: 9.9, hi: 10.0, label: 'Board demand' }] }), { emaStyle: 'bold' })
      .container.querySelector('svg')!.outerHTML;
    cleanup();
    const b = draw(tile({ bands: [{ kind: 'board_demand', lo: 9.9, hi: 10.0, label: 'Board demand', ctx: false }] }), { emaStyle: 'bold' })
      .container.querySelector('svg')!.outerHTML;
    expect(b).toBe(a);
    expect(a).not.toContain('pc-vwap');
  });
});

describe('🟩 2026-11-23 glass is for ctx daily zones ONLY', () => {
  it('NEGATIVE: a board band WITHOUT ctx keeps the dashed outline, no glass, no gradient defs', () => {
    const plain = { ...IN, ctx: undefined } as CmBand;
    const { container } = draw(tile({ bands: [plain] }));
    const g = container.querySelector('g[data-band-kind="board_demand"]')!;
    expect(g.getAttribute('data-band-look')).toBeNull();
    const r = g.querySelector('rect')!;
    expect(r.getAttribute('fill')).toBe('none');
    expect(r.getAttribute('stroke-dasharray')).toBe('5,3');
    expect(container.querySelector('linearGradient[id*="-glass-"]')).toBeNull();
  });
  it('NEGATIVE: no bands → no glass defs', () => {
    const { container } = draw(tile({ bands: [] }));
    expect(container.querySelector('linearGradient[id*="-glass-"]')).toBeNull();
  });
});
