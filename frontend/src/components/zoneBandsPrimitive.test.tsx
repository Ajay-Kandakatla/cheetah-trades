/* The band renderer — the first ISeriesPrimitive in the app.
 *
 * Ajay 2026-08-16: *"may be static makes sense I know it would break the
 * zones"*. The whole point of this primitive is that it does NOT: bands are
 * placed by asking the series where a PRICE sits, so they stay glued to those
 * prices while the chart zooms and pans.
 *
 * That claim is exactly what these tests pin. A fake series with a known
 * price→coordinate mapping stands in for the chart, so the geometry is checked
 * without a canvas or a real chart instance.
 */
import { describe, expect, it, vi } from 'vitest';
import { ZoneBandsPrimitive } from './zoneBandsPrimitive';
import type { BandSpec } from '../lib/zoneChart';

/** A series whose price scale is linear and known: $100 → y=0, $0 → y=400. */
function fakeSeries(map: (price: number) => number | null = (p) => 400 - p * 4) {
  return { priceToCoordinate: vi.fn(map) } as never;
}

type Rect = { x: number; y: number; w: number; h: number; fill: string };

function fakeTarget(width = 600, height = 400) {
  const rects: Rect[] = [];
  const ctx = {
    _fill: '',
    set fillStyle(v: string) { this._fill = v; },
    get fillStyle() { return this._fill; },
    fillRect(x: number, y: number, w: number, h: number) {
      rects.push({ x, y, w, h, fill: this._fill });
    },
  };
  return {
    rects,
    target: {
      useBitmapCoordinateSpace(cb: (scope: unknown) => void) {
        cb({ context: ctx, bitmapSize: { width, height },
             horizontalPixelRatio: 1, verticalPixelRatio: 1 });
      },
    } as never,
  };
}

function draw(bands: BandSpec[], series = fakeSeries(), size: [number, number] = [600, 400]) {
  const prim = new ZoneBandsPrimitive(bands);
  prim.attached({ series, chart: {} as never, requestUpdate: () => {} } as never);
  const { rects, target } = fakeTarget(...size);
  prim.paneViews()[0].renderer()!.draw(target);
  return rects;
}

const band = (o: Partial<BandSpec>): BandSpec =>
  ({ lo: 30, hi: 40, kind: 'demand', isEntry: false, ...o });

describe('band placement', () => {
  it('places a band at the y-coordinates the PRICE scale reports', () => {
    // $40 → y=240, $30 → y=280 under the fake scale.
    const [r] = draw([band({ lo: 30, hi: 40 })]);
    expect(r.y).toBe(240);
    expect(r.h).toBe(40);
  });

  it('spans the full width of the pane — a zone is a price range, not an event', () => {
    const [r] = draw([band({})], fakeSeries(), [812, 400]);
    expect(r.x).toBe(0);
    expect(r.w).toBe(812);
  });

  it('asks the series for BOTH edges, so zoom and pan move the band with them', () => {
    const s = fakeSeries();
    draw([band({ lo: 30, hi: 40 })], s);
    const asked = (s as unknown as { priceToCoordinate: { mock: { calls: number[][] } } })
      .priceToCoordinate.mock.calls.flat();
    expect(asked).toContain(40);
    expect(asked).toContain(30);
  });

  it('survives an inverted coordinate mapping without a negative height', () => {
    const [r] = draw([band({ lo: 30, hi: 40 })], fakeSeries((p) => p * 4));
    expect(r.h).toBeGreaterThan(0);
    expect(r.y).toBe(120);
  });

  it('scales into bitmap space on a retina pane', () => {
    const prim = new ZoneBandsPrimitive([band({ lo: 30, hi: 40 })]);
    prim.attached({ series: fakeSeries(), chart: {} as never, requestUpdate: () => {} } as never);
    const rects: Rect[] = [];
    const ctx = { fillStyle: '', fillRect: (x: number, y: number, w: number, h: number) =>
      rects.push({ x, y, w, h, fill: ctx.fillStyle }) };
    prim.paneViews()[0].renderer()!.draw({
      useBitmapCoordinateSpace: (cb: (s: unknown) => void) => cb({
        context: ctx, bitmapSize: { width: 1200, height: 800 },
        horizontalPixelRatio: 2, verticalPixelRatio: 2,
      }),
    } as never);
    expect(rects[0].y).toBe(480);      // 240 CSS px * 2
    expect(rects[0].h).toBe(80);
  });
});

describe('what each band looks like', () => {
  it('outlines the entry band on both edges and nothing else', () => {
    const rects = draw([band({ isEntry: true })]);
    // fill + top edge + bottom edge
    expect(rects).toHaveLength(3);
  });

  it('gives a supply band a top edge only — that is the line price reacts to', () => {
    expect(draw([band({ kind: 'supply' })])).toHaveLength(2);
  });

  it('leaves an ordinary demand band unoutlined so it cannot be mistaken for the plan', () => {
    expect(draw([band({ kind: 'demand', isEntry: false })])).toHaveLength(1);
  });

  it('fills the entry band more strongly than its neighbours', () => {
    const plain = draw([band({})])[0].fill;
    const entry = draw([band({ isEntry: true })])[0].fill;
    expect(entry).not.toBe(plain);
  });

  it('draws under the candles', () => {
    const prim = new ZoneBandsPrimitive([band({})]);
    expect(prim.paneViews()[0].zOrder!()).toBe('bottom');
  });
});

describe('negatives — the cases that would draw a lie', () => {
  it('SKIPS a band the price scale cannot place rather than pinning it to an edge', () => {
    // priceToCoordinate returns null when the price is outside the visible
    // range. Clamping would draw a zone at a price it does not occupy.
    const rects = draw([band({ lo: 30, hi: 40 })], fakeSeries(() => null));
    expect(rects).toEqual([]);
  });

  it('skips a band with only one placeable edge', () => {
    const rects = draw([band({ lo: 30, hi: 40 })],
                       fakeSeries((p) => (p === 40 ? 240 : null)));
    expect(rects).toEqual([]);
  });

  it('never collapses a thin band to zero height', () => {
    const [r] = draw([band({ lo: 39.99, hi: 40 })]);
    expect(r.h).toBeGreaterThanOrEqual(1);
  });

  it('draws nothing before it is attached to a series', () => {
    const prim = new ZoneBandsPrimitive([band({})]);
    const { rects, target } = fakeTarget();
    prim.paneViews()[0].renderer()!.draw(target);
    expect(rects).toEqual([]);
  });

  it('draws nothing after detach — a torn-down chart must not be painted', () => {
    const prim = new ZoneBandsPrimitive([band({})]);
    prim.attached({ series: fakeSeries(), chart: {} as never, requestUpdate: () => {} } as never);
    prim.detached();
    const { rects, target } = fakeTarget();
    prim.paneViews()[0].renderer()!.draw(target);
    expect(rects).toEqual([]);
  });

  it('draws nothing with no bands', () => {
    expect(draw([])).toEqual([]);
  });
});

describe('setBands', () => {
  it('swaps the bands and asks the chart to repaint', () => {
    const requestUpdate = vi.fn();
    const prim = new ZoneBandsPrimitive([band({ lo: 30, hi: 40 })]);
    prim.attached({ series: fakeSeries(), chart: {} as never, requestUpdate } as never);
    prim.setBands([band({ lo: 10, hi: 20 })]);
    expect(prim.bands[0].lo).toBe(10);
    expect(requestUpdate).toHaveBeenCalledTimes(1);
  });

  it('does not throw when nothing is listening yet', () => {
    const prim = new ZoneBandsPrimitive([]);
    expect(() => prim.setBands([band({})])).not.toThrow();
  });
});
