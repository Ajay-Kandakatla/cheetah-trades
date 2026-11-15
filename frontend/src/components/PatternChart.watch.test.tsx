/* 👀 PatternChart's three optional props for Gajjala's Watch (2026-11-15, gajjala-watch spec §3.8). Ajay: "Not the SEPA
 * and I need clear distinction or may be a brighter and thicker 21 EMA and 9 EMA" · "Any chart I view make sure you are
 * showing me from 4 AM for historical behaviour and also the right side with gaps to see where it might go".
 * chartOnly = no Link, no head; emaStyle="bold" = the replay's 9 / 21 over the candles, the cross diamonds after them;
 * axis = the served 04:00 slots, empty space to the close, thin bodies. NEGATIVES: without each prop the chart draws as
 * before (PatternChart is shared by every board). */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import { EMA_BOLD, xFor, type CmAxis, type CmTile } from '../lib/chartMaps';

afterEach(() => cleanup());

const N = 40;
/* N closed 1-min bars, the first closing 09:31 ET. */
const stamp = (m: number) => `2026-11-13 ${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const bars = Array.from({ length: N }, (_, i) => ({
  t: stamp(9 * 60 + 31 + i), o: 10, h: 10.3, l: 9.8, c: 10 + (i % 3) * 0.05, v: 1000 + i,
}));
const tile = (over: Partial<CmTile> = {}): CmTile => ({
  symbol: 'OMH', href: '/sepa/OMH', bars, bands: [], lines: [], stats: [], why: '',
  curves: [
    { tone: 'ema9', label: '9 EMA', values: bars.map((_, i) => 10 + i * 0.002) },
    { tone: 'ema21', label: '21 EMA', values: bars.map((_, i) => 10.01 + i * 0.001) },
  ],
  markers: [{ date: bars[10].t, kind: 'ema_cross_up', label: '🔀 9 EMA crossed above 21 EMA at 09:41 ET', price: 10.02 },
            { date: bars[20].t, kind: 'ema_cross_dn', label: '🔀 9 EMA crossed under 21 EMA at 09:51 ET' }],
  ...over,
});
/* A 1-min axis: 04:00 → 16:00 = 720 slots; bar i (closing 09:31 + i) sits at slot 330 + i. */
const AXIS: CmAxis = {
  slots: 720, x: bars.map((_, i) => 330 + i),
  shade: [{ from_slot: 0, to_slot: 330, kind: 'pre' }],
  ticks: [{ slot: 0, label: '04:00' }, { slot: 360, label: '10:00' }, { slot: 720, label: '16:00' }],
};
const draw = (props: Record<string, unknown> = {}, t: CmTile = tile()) =>
  render(<MemoryRouter><PatternChart tile={t} {...props} /></MemoryRouter>);
const order = (root: Element, a: Element, b: Element) => {
  const all = Array.from(root.querySelectorAll('*'));
  return all.indexOf(a) < all.indexOf(b);
};
/** The candle groups (a <g> holding exactly one wick line and one body rect). */
const candleBodies = (c: HTMLElement) => Array.from(c.querySelectorAll('svg > g'))
  .filter((g) => g.children.length === 2 && g.children[0].tagName === 'line' && g.children[1].tagName === 'rect')
  .map((g) => g.children[1] as SVGRectElement);
const padR = (c: HTMLElement) => {
  const vb = c.querySelector('svg')!.getAttribute('viewBox')!.split(' ').map(Number);
  // plotW = the x2 of the first price-axis grid line
  const ln = c.querySelector('svg > line') as SVGLineElement;
  return vb[2] - Number(ln.getAttribute('x2'));
};

describe('PatternChart emaStyle="bold"', () => {
  it('ema9 polyline: #FACC15, width 2, non-scaling, opacity 1, AFTER the candles and AFTER ema21', () => {
    const { container } = draw({ emaStyle: 'bold' });
    const e9 = container.querySelector('polyline.pc-ema-bold-ema9')!;
    const e21 = container.querySelector('polyline.pc-ema-bold-ema21')!;
    expect(e9.getAttribute('stroke')).toBe(EMA_BOLD.ema9.color);
    expect(e9.getAttribute('stroke')).toBe('#FACC15');
    expect(e9.getAttribute('stroke-width')).toBe('2');
    expect(e9.getAttribute('vector-effect')).toBe('non-scaling-stroke');
    expect(e9.getAttribute('opacity')).toBe('1');
    expect(e21.getAttribute('stroke')).toBe('#BE78FF');
    const lastBody = candleBodies(container).pop()!;
    expect(order(container, lastBody, e21)).toBe(true);
    expect(order(container, e21, e9)).toBe(true);
  });
  it('[C4.3] every pc-ema-cross-* polygon comes after the ema9 polyline in DOM order', () => {
    const { container } = draw({ emaStyle: 'bold' });
    const e9 = container.querySelector('polyline.pc-ema-bold-ema9')!;
    const ds = Array.from(container.querySelectorAll('[data-testid^="pc-ema-cross-"]'));
    expect(ds).toHaveLength(2);
    for (const d of ds) expect(order(container, e9, d)).toBe(true);
  });
  it('NEGATIVE: an other curve keeps its default look and slot (under the candles)', () => {
    const t = tile({ curves: [...tile().curves!, { tone: 'keltner', label: 'KC mid', values: bars.map(() => 10.1) }] });
    const { container } = draw({ emaStyle: 'bold' }, t);
    const kc = Array.from(container.querySelectorAll('polyline')).find((p) => p.getAttribute('stroke-dasharray') === '5,4')!;
    expect(kc.getAttribute('stroke-width')).toBe('1.1');
    expect(order(container, kc, candleBodies(container)[0])).toBe(true);
  });
  it('NEGATIVE: without the prop — width 1.1, toneColor, opacity 0.85, polylines before the candles, diamonds where they were', () => {
    const { container } = draw();
    expect(container.querySelector('.pc-ema-bold')).toBeNull();
    expect(container.querySelector('.pc-ema-cross-layer')).toBeNull();
    const pl = Array.from(container.querySelectorAll('polyline'));
    expect(pl).toHaveLength(2);
    for (const p of pl) {
      expect(p.getAttribute('stroke-width')).toBe('1.1');
      expect(p.getAttribute('opacity')).toBe('0.85');
      expect(p.getAttribute('vector-effect')).toBeNull();
      expect(p.getAttribute('stroke')).toMatch(/^var\(--/);
      expect(order(container, p, candleBodies(container)[0])).toBe(true);
    }
    const d = container.querySelector('[data-testid="pc-ema-cross-up"]')!;
    expect(order(container, d, pl[0])).toBe(true);   // the marker pass runs before the curves, as before
  });
});

describe('PatternChart chartOnly', () => {
  it('no <a>, no head, no rungs — the svg and the markers stay', () => {
    const { container } = draw({ chartOnly: true, emaStyle: 'bold' });
    expect(container.querySelector('a')).toBeNull();
    expect(container.querySelector('.cm-tile-head')).toBeNull();
    expect(container.querySelector('.cm-rungs')).toBeNull();
    expect(container.querySelector('.cm-tile.cm-tile-chart-only svg')).not.toBeNull();
    expect(container.querySelectorAll('[data-testid^="pc-ema-cross-"]')).toHaveLength(2);
  });
  it('the hover crosshair still works', () => {
    const { container } = draw({ chartOnly: true });
    const svg = container.querySelector('svg')!;
    (svg as any).getBoundingClientRect = () => ({ left: 0, top: 0, width: 620, height: 190, right: 620, bottom: 190, x: 0, y: 0 });
    fireEvent.mouseMove(svg, { clientX: 300, clientY: 60 });
    expect(svg.querySelector('g[pointer-events="none"]')).not.toBeNull();
  });
  it('NEGATIVE: by default the tile is wrapped in a Link to its href', () => {
    const { container } = draw();
    const a = container.querySelector('a')!;
    expect(a).not.toBeNull();
    expect(a.getAttribute('href')).toContain('/sepa/OMH');
  });
});

describe('PatternChart axis', () => {
  it('bar x = xFor(axis.x[i], axis.slots); the last bar sits far left of the right edge (empty slots to the close)', () => {
    const { container } = draw({ axis: AXIS });
    const pr = padR(container);
    const bodies = candleBodies(container);
    expect(bodies).toHaveLength(N);
    const bw = (620 - pr) / 720;
    const cx = (r: SVGRectElement) => Number(r.getAttribute('x')) + Number(r.getAttribute('width')) / 2;
    expect(cx(bodies[0])).toBeCloseTo(xFor(330, 720, 620, pr), 6);
    expect(cx(bodies[N - 1])).toBeCloseTo(xFor(330 + N - 1, 720, 620, pr), 6);
    expect(cx(bodies[N - 1])).toBeLessThan((620 - pr) * 0.6);
    // [C4.1] a body narrower than the old 1.4 floor (720 slots)
    expect(Number(bodies[0].getAttribute('width'))).toBeCloseTo(bw * 0.64, 6);
    expect(Number(bodies[0].getAttribute('width'))).toBeLessThan(1.4);
  });
  it('the served shade replaces the extended-hours runs; the served ticks replace the date ticks', () => {
    const { container } = draw({ axis: AXIS });
    const sh = container.querySelectorAll('rect.pc-ext');
    expect(sh).toHaveLength(1);
    expect(sh[0].getAttribute('data-shade')).toBe('pre');
    expect(Number(sh[0].getAttribute('x'))).toBeCloseTo(0, 6);
    const labels = Array.from(container.querySelectorAll('svg text')).map((t) => t.textContent);
    expect(labels).toContain('04:00');
    expect(labels).toContain('16:00');
    expect(labels).not.toContain('Nov 13');
  });
  it('the EMA curves follow the same slots', () => {
    const { container } = draw({ axis: AXIS, emaStyle: 'bold' });
    const pr = padR(container);
    const pts = container.querySelector('polyline.pc-ema-bold-ema9')!.getAttribute('points')!.split(' ');
    expect(Number(pts[0].split(',')[0])).toBeCloseTo(xFor(330, 720, 620, pr), 6);
  });
  it('NEGATIVE: without axis the 1.4 floor holds and every x = xFor(i, bars.length)', () => {
    const many = Array.from({ length: 720 }, (_, i) => ({ ...bars[0], t: stamp(4 * 60 + 1 + i) }));
    const { container } = draw({}, tile({ bars: many, curves: [], markers: [] }));
    const pr = padR(container);
    const bodies = candleBodies(container);
    expect(bodies).toHaveLength(720);
    for (const r of bodies.slice(0, 5)) expect(Number(r.getAttribute('width'))).toBeCloseTo(1.4, 6);
    cleanup();
    const c2 = draw().container;
    const pr2 = padR(c2);
    const b2 = candleBodies(c2);
    b2.forEach((r, i) => {
      const cx = Number(r.getAttribute('x')) + Math.max((620 - pr2) / N * 0.32, 0.8);
      expect(cx).toBeCloseTo(xFor(i, N, 620, pr2), 6);
    });
    expect(pr).toBeGreaterThan(0);
  });
  it('NEGATIVE: an axis whose x does not match the bars is ignored (one slot per bar, as before)', () => {
    const { container } = draw({ axis: { ...AXIS, x: [1, 2, 3] } });
    const pr = padR(container);
    const b = candleBodies(container);
    const cx = Number(b[0].getAttribute('x')) + Number(b[0].getAttribute('width')) / 2;
    expect(cx).toBeCloseTo(xFor(0, N, 620, pr), 6);
  });
});
