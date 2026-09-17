import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import IndexZones, {
  INDEX_ZONE_SYMBOLS, IZ_RES_KEYS, _resetIndexZonesFallback, izBasis, izDefaultRes, izDist,
  izLiveSource,
  izDrawable, izEdge, izLiveLine, izPrice, izRange, izResolutions, izTile, izView, izWhere,
} from './IndexZones';
import { ChartMaps } from '../pages/ChartMaps';
import type { CmBar, CmIndexZoneBand, CmIndexZoneRead, CmIndexZones } from '../lib/chartMaps';

/* 🧭 IndexZones — SPY and QQQ pinned to the Back in Demand tab.
 *
 * Ajay 2026-09-16, verbatim: "Can you create a SPY demand and supply zone
 * please for me? and also QQQ supply and demand zone and keep them always in
 * the in demand zone page. I need everything calculation overnight." then, the
 * same morning: "I wanna see charts with multiple zones" · "For both QQQ and
 * SPY" · "SPX*" · "Sorry SPY only my bad" — SPY and QQQ, and the headline ask
 * is a PICTURE.
 *
 * The rules this strip must never break:
 *   1. KEEP THEM ALWAYS — it renders while the board is warming, while it is
 *      erroring, when nothing matched and when the payload is missing entirely.
 *      When the BOARD gave it nothing it asks the endpoint itself, and the
 *      placeholder says which of three things happened: a request in flight, a
 *      request that failed, or a store with nothing in it.
 *   2. TWO BASES, NEVER MIXED — the bands, the chart and the distances are
 *      last night's CLOSED bars and each one names the session; a live print is
 *      a separate, labelled line that says out loud it does not move a band and
 *      is never drawn on the chart.
 *   3. Supply and demand are distinguishable in the DOM, and the band the close
 *      finished inside is marked.
 *   4. It computes nothing: the ladder is printed in the served order, and
 *      every number comes off the wire.
 *   5. NO CLAIM OF EDGE, and the word is "reversal", never "bounce".
 *
 * The fixtures are the REAL 2026-09-16 structure for both tickers at BOTH
 * geometries — board (demand_reentry.zone_geom: 7 bands each) and fine
 * (price_zones defaults: 14 on SPY, 13 on QQQ) — so this doubles as a contract
 * test against backend/supply_demand/index_zones.py.
 */

/** Deterministic closed daily bars spanning a range, so the chart has
 *  something real to draw. Dates are unique — PatternChart keys candles on
 *  `t`. Nothing here is a measurement; it is a canvas. */
function makeBars(n: number, lo: number, hi: number): CmBar[] {
  const out: CmBar[] = [];
  for (let i = 0; i < n; i += 1) {
    const f = i / Math.max(n - 1, 1);
    const c = lo + (hi - lo) * f;
    const d = new Date(Date.UTC(2026, 5, 1) + i * 86_400_000);
    out.push({
      t: d.toISOString().slice(0, 10),
      o: +(c * 0.997).toFixed(2), h: +(c * 1.006).toFixed(2),
      l: +(c * 0.993).toFixed(2), c: +c.toFixed(2), v: 1_000_000 + i,
    });
  }
  return out;
}

const SPY_BOARD: CmIndexZoneBand[] = [
  { kind: 'supply', lo: 749.53, hi: 779.37, mid: 764.45, touches: 7, strength: 75, side: 'in', dist_pct: 0 },
  { kind: 'demand', lo: 759.48, hi: 762.04, mid: 760.76, touches: 2, strength: 21, side: 'above', dist_pct: 0.28 },
  { kind: 'demand', lo: 716.58, hi: 739.51, mid: 728.05, touches: 5, strength: 63, side: 'below', dist_pct: 2.36 },
  { kind: 'supply', lo: 696.09, hi: 697.84, mid: 696.97, touches: 4, strength: 52, side: 'below', dist_pct: 7.86 },
  { kind: 'supply', lo: 667.34, hi: 693.68, mid: 680.51, touches: 7, strength: 97, side: 'below', dist_pct: 8.41 },
  { kind: 'demand', lo: 661.21, hi: 679.82, mid: 670.52, touches: 6, strength: 93, side: 'below', dist_pct: 10.24 },
  { kind: 'demand', lo: 629.28, hi: 654.40, mid: 641.84, touches: 4, strength: 67, side: 'below', dist_pct: 13.60 },
];

/* 14 bands, median ~1.1% wide — the price_zones module defaults, measured on
 * SPY on 2026-09-16. THIS is what "multiple zones" means on this page. */
const SPY_FINE: CmIndexZoneBand[] = [
  { kind: 'supply', lo: 774.71, hi: 779.37, touches: 3, strength: 41, side: 'above', dist_pct: 2.29 },
  { kind: 'supply', lo: 764.02, hi: 768.60, touches: 2, strength: 24, side: 'above', dist_pct: 0.88 },
  { kind: 'demand', lo: 759.48, hi: 762.04, touches: 2, strength: 21, side: 'above', dist_pct: 0.28 },
  { kind: 'supply', lo: 753.15, hi: 757.67, touches: 4, strength: 47, side: 'in', dist_pct: 0 },
  { kind: 'demand', lo: 745.90, hi: 750.38, touches: 3, strength: 33, side: 'below', dist_pct: 0.93 },
  { kind: 'demand', lo: 736.21, hi: 740.63, touches: 5, strength: 58, side: 'below', dist_pct: 2.21 },
  { kind: 'supply', lo: 728.04, hi: 732.41, touches: 2, strength: 22, side: 'below', dist_pct: 3.30 },
  { kind: 'demand', lo: 716.58, hi: 720.88, touches: 4, strength: 46, side: 'below', dist_pct: 4.82 },
  { kind: 'supply', lo: 696.09, hi: 700.27, touches: 4, strength: 52, side: 'below', dist_pct: 7.54 },
  { kind: 'supply', lo: 689.44, hi: 693.68, touches: 3, strength: 35, side: 'below', dist_pct: 8.41 },
  { kind: 'demand', lo: 675.70, hi: 679.82, touches: 6, strength: 71, side: 'below', dist_pct: 10.24 },
  { kind: 'demand', lo: 661.21, hi: 665.24, touches: 3, strength: 34, side: 'below', dist_pct: 12.16 },
  { kind: 'supply', lo: 650.53, hi: 654.40, touches: 2, strength: 21, side: 'below', dist_pct: 13.60 },
  { kind: 'demand', lo: 629.28, hi: 633.10, touches: 4, strength: 44, side: 'below', dist_pct: 16.40 },
];

const QQQ_BOARD: CmIndexZoneBand[] = [
  { kind: 'supply', lo: 721.89, hi: 748.65, mid: 735.27, touches: 8, strength: 74, side: 'above', dist_pct: 2.46 },
  { kind: 'demand', lo: 695.25, hi: 704.66, mid: 699.96, touches: 5, strength: 48, side: 'in', dist_pct: 0 },
  { kind: 'demand', lo: 661.14, hi: 686.37, mid: 673.76, touches: 2, strength: 25, side: 'below', dist_pct: 2.58 },
  { kind: 'supply', lo: 629.21, hi: 637.01, mid: 633.11, touches: 4, strength: 44, side: 'below', dist_pct: 9.59 },
  { kind: 'supply', lo: 602.87, hi: 625.51, mid: 614.19, touches: 6, strength: 68, side: 'below', dist_pct: 11.22 },
  { kind: 'demand', lo: 607.05, hi: 610.15, mid: 608.60, touches: 2, strength: 25, side: 'below', dist_pct: 13.40 },
  { kind: 'demand', lo: 580.74, hi: 600.28, mid: 590.51, touches: 7, strength: 94, side: 'below', dist_pct: 14.80 },
];

/* 13 bands — QQQ at the fine geometry, measured the same day. */
const QQQ_FINE: CmIndexZoneBand[] = [
  { kind: 'supply', lo: 744.42, hi: 748.65, touches: 3, strength: 36, side: 'above', dist_pct: 5.66 },
  { kind: 'supply', lo: 733.10, hi: 737.25, touches: 4, strength: 45, side: 'above', dist_pct: 4.05 },
  { kind: 'supply', lo: 721.89, hi: 725.97, touches: 5, strength: 57, side: 'above', dist_pct: 2.46 },
  { kind: 'demand', lo: 711.02, hi: 715.05, touches: 2, strength: 23, side: 'above', dist_pct: 0.92 },
  { kind: 'demand', lo: 700.63, hi: 704.66, touches: 5, strength: 48, side: 'in', dist_pct: 0 },
  { kind: 'supply', lo: 691.20, hi: 695.25, touches: 3, strength: 31, side: 'below', dist_pct: 1.32 },
  { kind: 'demand', lo: 682.30, hi: 686.37, touches: 4, strength: 43, side: 'below', dist_pct: 2.58 },
  { kind: 'demand', lo: 661.14, hi: 665.06, touches: 2, strength: 22, side: 'below', dist_pct: 5.60 },
  { kind: 'supply', lo: 633.01, hi: 637.01, touches: 4, strength: 44, side: 'below', dist_pct: 9.59 },
  { kind: 'supply', lo: 621.44, hi: 625.51, touches: 3, strength: 33, side: 'below', dist_pct: 11.22 },
  { kind: 'demand', lo: 607.05, hi: 610.15, touches: 2, strength: 25, side: 'below', dist_pct: 13.40 },
  { kind: 'supply', lo: 596.31, hi: 600.28, touches: 3, strength: 32, side: 'below', dist_pct: 14.80 },
  { kind: 'demand', lo: 580.74, hi: 584.62, touches: 4, strength: 43, side: 'below', dist_pct: 17.02 },
];

const SPY: CmIndexZoneRead = {
  symbol: 'SPY',
  name: 'SPDR S&P 500 ETF Trust',
  as_of: '2026-09-16',
  close: 757.39,
  atr14: 5.86,
  high_252: 779.37,
  bars: makeBars(90, 622.10, 771.40),
  default_resolution: 'fine',
  resolutions: {
    board: {
      bands: SPY_BOARD,
      in_band: SPY_BOARD[0],
      ceiling: { lo: 759.48, hi: 762.04, dist_pct: 0.28, kind: 'demand' },
      floor: { lo: 716.58, hi: 739.51, dist_pct: 2.36, kind: 'demand' },
      room_pct: 0.28,
      drop_pct: 2.36,
      sentence: 'SPY closed 757.39 on 2026-09-16 standing inside a supply band 749.53–779.37 that has been tested 7 times; the nearest band above is 759.48–762.04 (0.28% up) and the nearest below is 716.58–739.51 (2.36% down).',
    },
    fine: {
      bands: SPY_FINE,
      in_band: SPY_FINE[3],
      ceiling: { lo: 759.48, hi: 762.04, dist_pct: 0.28, kind: 'demand' },
      floor: { lo: 745.90, hi: 750.38, dist_pct: 0.93, kind: 'demand' },
      room_pct: 0.28,
      drop_pct: 0.93,
      sentence: 'SPY closed 757.39 on 2026-09-16 standing inside a supply band 753.15–757.67 that has been tested 4 times; the nearest band above is 759.48–762.04 (0.28% up) and the nearest below is 745.90–750.38 (0.93% down).',
    },
  },
  // The flat keys stay populated: a doc written before the two-resolution
  // payload shipped must still render a full card.
  bands: SPY_BOARD,
  in_band: SPY_BOARD[0],
  ceiling: { lo: 759.48, hi: 762.04, dist_pct: 0.28, kind: 'demand' },
  floor: { lo: 716.58, hi: 739.51, dist_pct: 2.36, kind: 'demand' },
  room_pct: 0.28,
  drop_pct: 2.36,
  sentence: 'SPY closed 757.39 on 2026-09-16 standing inside a supply band 749.53–779.37 that has been tested 7 times; the nearest band above is 759.48–762.04 (0.28% up) and the nearest below is 716.58–739.51 (2.36% down).',
  source: 'zone_store',
  price_basis: 'bands from the 2026-09-16 close',
};

const QQQ: CmIndexZoneRead = {
  symbol: 'QQQ',
  name: 'Invesco QQQ Trust',
  as_of: '2026-09-16',
  close: 704.54,
  atr14: 7.76,
  high_252: 748.65,
  bars: makeBars(90, 574.20, 741.80),
  default_resolution: 'fine',
  resolutions: {
    board: {
      bands: QQQ_BOARD,
      in_band: QQQ_BOARD[1],
      ceiling: { lo: 721.89, hi: 748.65, dist_pct: 2.46, kind: 'supply' },
      floor: { lo: 661.14, hi: 686.37, dist_pct: 2.58, kind: 'demand' },
      room_pct: 2.46,
      drop_pct: 2.58,
      sentence: 'QQQ closed 704.54 on 2026-09-16 standing inside a demand band 695.25–704.66 that has been tested 5 times; the nearest band above is 721.89–748.65 (2.46% up) and the nearest below is 661.14–686.37 (2.58% down).',
    },
    fine: {
      bands: QQQ_FINE,
      in_band: QQQ_FINE[4],
      ceiling: { lo: 711.02, hi: 715.05, dist_pct: 0.92, kind: 'demand' },
      floor: { lo: 691.20, hi: 695.25, dist_pct: 1.32, kind: 'supply' },
      room_pct: 0.92,
      drop_pct: 1.32,
      sentence: 'QQQ closed 704.54 on 2026-09-16 standing inside a demand band 700.63–704.66 that has been tested 5 times; the nearest band above is 711.02–715.05 (0.92% up) and the nearest below is 691.20–695.25 (1.32% down).',
    },
  },
  bands: QQQ_BOARD,
  in_band: QQQ_BOARD[1],
  ceiling: { lo: 721.89, hi: 748.65, dist_pct: 2.46, kind: 'supply' },
  floor: { lo: 661.14, hi: 686.37, dist_pct: 2.58, kind: 'demand' },
  room_pct: 2.46,
  drop_pct: 2.58,
  sentence: 'QQQ closed 704.54 on 2026-09-16 standing inside a demand band 695.25–704.66 that has been tested 5 times; the nearest band above is 721.89–748.65 (2.46% up) and the nearest below is 661.14–686.37 (2.58% down).',
  source: 'zone_store',
  price_basis: 'bands from the 2026-09-16 close',
};

const BOTH: CmIndexZones = {
  date: '2026-09-16',
  indexes: { SPY, QQQ },
  stale_days: 0,
  stale_sessions: 0,
  note: null,
};

/* Same two mocks the ChartMaps page suite uses: usage tracking is
 * fire-and-forget, and the access grants decide which TABS exist — neither has
 * anything to do with a pinned strip, and both would otherwise fetch. */
vi.mock('../lib/usageTracker', () => ({ trackFeature: vi.fn() }));
vi.mock('../hooks/useMyFeatures', () => ({
  useMyFeatures: () => ({ loaded: true, features: new Set(['chart-maps']), catalog: [], email: null }),
}));

/** The strip owns a FALLBACK request now, and the chart brings the tile chrome
 *  (the growth-tag lookup, the signal watchlist) with it. Every standalone
 *  render therefore needs a fetch — stubbed to a 404 by default so the
 *  fallback resolves to "nothing stored", which is the state these tests
 *  assert about. `_resetIndexZonesFallback` clears the module cache between
 *  tests; without it the first test's answer would be every later test's. */
function stubQuiet(indexZones?: unknown) {
  return vi.fn(async (url: string) => {
    if (String(url).includes('/supply-demand/index-zones')) {
      return indexZones === undefined
        ? ({ ok: false, status: 404, json: async () => ({}) } as Response)
        : ({ ok: true, status: 200, json: async () => indexZones } as Response);
    }
    return { ok: true, status: 200, json: async () => ({}) } as Response;
  });
}

const draw = (data?: CmIndexZones | null) => render(
  <MemoryRouter><IndexZones data={data} /></MemoryRouter>,
);

describe('IndexZones — the pinned strip', () => {
  beforeEach(() => {
    _resetIndexZonesFallback();
    vi.stubGlobal('fetch', stubQuiet());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('renders BOTH cards with their ladders, in the served order', () => {
    draw(BOTH);
    expect(screen.getByTestId('index-zone-SPY')).toBeTruthy();
    expect(screen.getByTestId('index-zone-QQQ')).toBeTruthy();

    // Default resolution is FINE — 14 on SPY, 13 on QQQ. That IS his "multiple
    // zones", and it is the number the backend measured, not one made up here.
    const spy = within(screen.getByTestId('index-zone-ladder-SPY'));
    expect(spy.getAllByRole('listitem')).toHaveLength(14);
    const qqq = within(screen.getByTestId('index-zone-ladder-QQQ'));
    expect(qqq.getAllByRole('listitem')).toHaveLength(13);

    // The order is the BACKEND's — high to low, never re-sorted here.
    const ranges = screen.getByTestId('index-zone-ladder-SPY')
      .querySelectorAll('.iz-band-range');
    expect(ranges[0].textContent).toBe('774.71 – 779.37');
    expect(ranges[13].textContent).toBe('629.28 – 633.10');
  });

  it('marks the band the CLOSE finished inside, on both cards', () => {
    draw(BOTH);
    const spyIn = screen.getByTestId('index-zone-ladder-SPY')
      .querySelectorAll('[data-side="in"]');
    expect(spyIn).toHaveLength(1);
    expect(spyIn[0].getAttribute('data-kind')).toBe('supply');
    expect(spyIn[0].textContent).toContain('753.15 – 757.67');
    // F4 — it says it is the CLOSE, and which session's close. The old copy
    // read "price is standing in this band" directly under a live line saying
    // price was somewhere else entirely.
    expect(spyIn[0].textContent).toContain('the 2026-09-16 close is inside this band');
    expect(spyIn[0].className).toContain('iz-band-in');

    const qqqIn = screen.getByTestId('index-zone-ladder-QQQ')
      .querySelectorAll('[data-side="in"]');
    expect(qqqIn).toHaveLength(1);
    expect(qqqIn[0].getAttribute('data-kind')).toBe('demand');
    expect(qqqIn[0].textContent).toContain('700.63 – 704.66');
  });

  it('F4 NEGATIVE: no distance is printed without the session it was measured on', () => {
    draw(BOTH);
    const rows = [...screen.getByTestId('index-zone-ladder-SPY')
      .querySelectorAll('.iz-band-where')].map((e) => e.textContent || '');
    for (const r of rows.filter(Boolean)) {
      expect(r).toMatch(/the 2026-09-16 close/);
    }
    expect(rows).toContain('0.28% above the 2026-09-16 close');
    expect(rows).toContain('0.93% below the 2026-09-16 close');
    // …and never the basis-free wording it used to carry.
    expect(screen.getByTestId('index-zones').textContent)
      .not.toMatch(/price is standing in this band/);
  });

  it('makes supply and demand distinguishable in the DOM, not by colour alone', () => {
    draw(BOTH);
    const ladder = screen.getByTestId('index-zone-ladder-SPY');
    expect(ladder.querySelectorAll('[data-kind="supply"]')).toHaveLength(7);
    expect(ladder.querySelectorAll('[data-kind="demand"]')).toHaveLength(7);
    expect(ladder.querySelectorAll('.iz-band-supply')).toHaveLength(7);
    expect(ladder.querySelectorAll('.iz-band-demand')).toHaveLength(7);
    // …and in words, for a reader who cannot use the colour at all.
    const kinds = [...ladder.querySelectorAll('.iz-band-kind')].map((e) => e.textContent);
    expect(kinds.slice(0, 4)).toEqual(['supply', 'supply', 'demand', 'supply']);
  });

  it('states the CLOSED-BAR basis over the numbers, and says the job runs overnight', () => {
    draw(BOTH);
    const basis = screen.getByTestId('index-zone-basis-SPY').textContent || '';
    expect(basis).toMatch(/closed daily bars/i);
    expect(basis).toMatch(/2026-09-16/);
    expect(basis).toMatch(/757\.39/);
    expect(basis).toMatch(/overnight/i);
    // It covers the CHART too, now that there is one.
    expect(basis).toMatch(/bands and chart/i);
    // The strip header says it too, once, for both cards.
    expect(screen.getByTestId('index-zones').textContent)
      .toMatch(/computed overnight from closed daily bars/i);
    expect(screen.getByTestId('index-zone-edges-SPY').textContent)
      .toMatch(/measured from the 2026-09-16 close above, not from a live print/i);
  });

  it('prints the served sentence and the served ceiling/floor, computing neither', () => {
    draw(BOTH);
    expect(screen.getByTestId('index-zone-note-SPY').textContent)
      .toContain(SPY.resolutions!.fine!.sentence);
    const edges = screen.getByTestId('index-zone-edges-SPY').textContent || '';
    // F7 — the KIND of each edge is printed. A demand band overhead is
    // support price has already gone under, which is exactly the flip rule in
    // his source note, and it is invisible if only the colour carries it.
    expect(edges).toContain('Ceiling demand band 759.48 – 762.04, 0.28% up');
    expect(edges).toContain('Floor demand band 745.90 – 750.38, 0.93% down');
    expect(edges).toMatch(/a demand band broken through is overhead from then on/i);
  });
});

/* ── PART A: the chart ────────────────────────────────────────────────────── */

describe('IndexZones — the chart (Ajay: "I wanna see charts with multiple zones")', () => {
  beforeEach(() => {
    _resetIndexZonesFallback();
    vi.stubGlobal('fetch', stubQuiet());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('draws a chart per index with EVERY band in the selected set on it', () => {
    draw(BOTH);
    for (const sym of INDEX_ZONE_SYMBOLS) {
      const chart = screen.getByTestId(`index-zone-chart-${sym}`);
      expect(chart.querySelector('svg.cm-svg')).toBeTruthy();
    }
    // 14 rectangles for SPY's 14 fine bands — one per band, none dropped.
    const spyBands = screen.getByTestId('index-zone-chart-SPY')
      .querySelectorAll('g[data-band-kind]');
    expect(spyBands).toHaveLength(14);
    expect(screen.getByTestId('index-zone-chart-QQQ')
      .querySelectorAll('g[data-band-kind]')).toHaveLength(13);
  });

  it('paints supply and demand as DIFFERENT band kinds on the chart', () => {
    draw(BOTH);
    const chart = screen.getByTestId('index-zone-chart-SPY');
    expect(chart.querySelectorAll('g[data-band-kind="supply"]')).toHaveLength(7);
    expect(chart.querySelectorAll('g[data-band-kind="demand"]')).toHaveLength(7);
  });

  it('marks the band the close finished inside, on the chart as well as the ladder', () => {
    draw(BOTH);
    const titles = [...screen.getByTestId('index-zone-chart-SPY').querySelectorAll('title')]
      .map((t) => t.textContent || '');
    const inside = titles.filter((t) => /close inside/.test(t));
    expect(inside).toHaveLength(1);
    expect(inside[0]).toContain('753.15');
    expect(inside[0]).toMatch(/the 2026-09-16 close inside/);
  });

  it('NEGATIVE: the chart carries the stored close and NEVER the live print', () => {
    draw({
      ...BOTH,
      indexes: {
        SPY: { ...SPY, live_px: 771.11, live_side: 'above',
               price_basis: 'live print, bands from the 2026-09-16 close' },
        QQQ,
      },
    });
    const tile = izTile(SPY, izView(SPY, 'fine'))!;
    expect(tile.lines).toHaveLength(1);
    expect(tile.lines[0].price).toBe(757.39);
    // The label is the bare word: `lineLabels` appends the price itself for
    // this gutter, so `close 757.39` rendered as "close 757.39 757.39". And
    // the tone is 'neutral', not 'now' — 'now' is the LIVE-print colour on
    // every other tile of this page, and this line is a closed-bar close.
    expect(tile.lines[0].label).toBe('close');
    expect(tile.lines[0].tone).toBe('neutral');
    // The live number is on its own line in the card, not on the chart.
    expect(screen.getByTestId('index-zone-live-SPY').textContent).toMatch(/771\.11/);
    expect(screen.getByTestId('index-zone-chart-SPY').textContent).not.toMatch(/771\.11/);
  });

  it('NEGATIVE: a doc with no bars says so and still renders every level', () => {
    draw({ date: '2026-09-16', indexes: { SPY: { ...SPY, bars: undefined }, QQQ } });
    expect(screen.queryByTestId('index-zone-chart-SPY')).toBeNull();
    expect(screen.getByTestId('index-zone-nochart-SPY').textContent)
      .toMatch(/carried no bars/i);
    expect(screen.getByTestId('index-zone-ladder-SPY')
      .querySelectorAll('.iz-band')).toHaveLength(14);
    // The other card is unaffected.
    expect(screen.getByTestId('index-zone-chart-QQQ')).toBeTruthy();
  });

  it('izTile drops unusable bars and unusable bands rather than drawing junk (negative)', () => {
    expect(izTile({ symbol: 'SPY' } as CmIndexZoneRead, {})).toBeNull();
    expect(izTile({ symbol: 'SPY', bars: 'nope' } as unknown as CmIndexZoneRead, {})).toBeNull();
    expect(izTile({ symbol: 'SPY', bars: [{ t: 'x', o: null, h: 1, l: 1, c: 1, v: 1 }] } as unknown as CmIndexZoneRead, {})).toBeNull();

    const tile = izTile(SPY, {
      bands: [
        { kind: 'demand', lo: 700, hi: 710 },
        { kind: 'supply', lo: null as unknown as number, hi: 720 },
        { kind: 'demand', lo: 760, hi: 750 },   // inverted — not a rectangle
        null as unknown as CmIndexZoneBand,
      ],
    })!;
    expect(tile.bands).toHaveLength(1);
    expect(tile.bands[0]).toMatchObject({ kind: 'demand', lo: 700, hi: 710 });
    expect(tile.href).toBe('/sepa/SPY?tab=supply');
  });

  it('izDrawable keeps only bands with two finite edges (negative)', () => {
    expect(izDrawable(null)).toEqual([]);
    expect(izDrawable('nope')).toEqual([]);
    expect(izDrawable([{ lo: 1, hi: 2 }, { lo: NaN, hi: 2 }, { lo: 3, hi: 2 }])).toHaveLength(1);
  });
});

/* ── PART A: the resolution toggle ────────────────────────────────────────── */

describe('IndexZones — the Fine / Board resolution toggle', () => {
  beforeEach(() => {
    _resetIndexZonesFallback();
    vi.stubGlobal('fetch', stubQuiet());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('offers both arms, counts them, and opens on the backend default', () => {
    draw(BOTH);
    const fine = screen.getByTestId('index-zone-res-fine-SPY');
    const board = screen.getByTestId('index-zone-res-board-SPY');
    expect(fine.textContent).toBe('Fine · 14 zones');
    expect(board.textContent).toBe('Board · 7 zones');
    expect(fine.getAttribute('aria-pressed')).toBe('true');
    expect(board.getAttribute('aria-pressed')).toBe('false');
    expect(izDefaultRes(SPY)).toBe('fine');
  });

  it('says which set the REST of the page is drawn with — the point of labelling it', () => {
    draw(BOTH);
    const board = screen.getByTestId('index-zone-res-board-SPY');
    expect(board.getAttribute('title'))
      .toMatch(/the set the demand engine and every tile under this strip are drawn with/i);
    expect(screen.getByTestId('index-zone-res-note-SPY').textContent)
      .toMatch(/Both are the same closed daily bars/i);
  });

  it('switching to Board redraws the chart, the ladder AND the sentence', () => {
    draw(BOTH);
    fireEvent.click(screen.getByTestId('index-zone-res-board-SPY'));
    expect(screen.getByTestId('index-zone-ladder-SPY')
      .querySelectorAll('.iz-band')).toHaveLength(7);
    expect(screen.getByTestId('index-zone-chart-SPY')
      .querySelectorAll('g[data-band-kind]')).toHaveLength(7);
    expect(screen.getByTestId('index-zone-note-SPY').textContent)
      .toContain(SPY.resolutions!.board!.sentence);
    expect(screen.getByTestId('index-zone-edges-SPY').textContent)
      .toContain('Floor demand band 716.58 – 739.51, 2.36% down');
    expect(screen.getByTestId('index-zone-res-board-SPY').getAttribute('aria-pressed'))
      .toBe('true');
    // The OTHER card is untouched — one toggle per index, his ask was per chart.
    expect(screen.getByTestId('index-zone-ladder-QQQ')
      .querySelectorAll('.iz-band')).toHaveLength(13);
  });

  it('NEGATIVE: a legacy doc with no resolutions shows NO toggle and still draws', () => {
    const legacy: CmIndexZoneRead = { ...SPY, resolutions: undefined, default_resolution: undefined };
    draw({ date: '2026-09-16', indexes: { SPY: legacy, QQQ } });
    expect(screen.queryByTestId('index-zone-res-SPY')).toBeNull();
    // …and it falls back to the FLAT keys, which is the board set.
    expect(screen.getByTestId('index-zone-ladder-SPY')
      .querySelectorAll('.iz-band')).toHaveLength(7);
    expect(izResolutions(legacy)).toEqual({});
    expect(izView(legacy, 'fine').bands).toBe(SPY_BOARD);
  });

  it('NEGATIVE: one-armed / malformed resolutions never produce a dead control', () => {
    const oneArm = { ...SPY, resolutions: { fine: SPY.resolutions!.fine } } as CmIndexZoneRead;
    draw({ indexes: { SPY: oneArm } });
    expect(screen.queryByTestId('index-zone-res-SPY')).toBeNull();
    expect(Object.keys(izResolutions(oneArm))).toEqual(['fine']);

    expect(izResolutions({ ...SPY, resolutions: 'nope' } as unknown as CmIndexZoneRead)).toEqual({});
    expect(izResolutions({ ...SPY, resolutions: { fine: { bands: 'nope' } } } as unknown as CmIndexZoneRead))
      .toEqual({});
    // A default naming a resolution the doc did NOT send is not honoured.
    expect(izDefaultRes({ ...SPY, default_resolution: 'board' })).toBe('board');
    expect(izDefaultRes({ ...oneArm, default_resolution: 'board' })).toBe('fine');
    expect(izDefaultRes({ ...SPY, default_resolution: 'hourly' } as CmIndexZoneRead)).toBe('fine');
    expect(izDefaultRes({ symbol: 'SPY' } as CmIndexZoneRead)).toBe('fine');
    expect(IZ_RES_KEYS).toEqual(['fine', 'board']);
  });
});

/* ── the live overlay ─────────────────────────────────────────────────────── */

describe('IndexZones — the live overlay', () => {
  beforeEach(() => {
    _resetIndexZonesFallback();
    vi.stubGlobal('fetch', stubQuiet());
  });
  afterEach(() => vi.unstubAllGlobals());

  it('LABELS a live overlay as live and says it does not move a band', () => {
    draw({
      ...BOTH,
      indexes: {
        SPY: { ...SPY, live_px: 759.92, live_side: 'in', live_in_band: SPY_FINE[2],
               price_basis: 'live print, bands from the 2026-09-16 close' },
        QQQ,
      },
    });
    const live = screen.getByTestId('index-zone-live-SPY').textContent || '';
    expect(live).toMatch(/live print 759\.92/);
    expect(live).toMatch(/standing in the demand band 759\.48 – 762\.04/);
    // F6 — price_basis is LABELLED, never dropped in bare. The old line ended
    // "· live", which says nothing at all.
    expect(live).toMatch(/basis: live print, bands from the 2026-09-16 close/);
    expect(live).not.toMatch(/· live$/);
    expect(live).toMatch(/it does not move a band/i);
    // The stored close is untouched by the live print — same card, both bases,
    // each labelled. That is the hot-sectors correction.
    expect(screen.getByTestId('index-zone-basis-SPY').textContent).toMatch(/757\.39/);
  });

  it('F3: above/below mean above/below EVERY stored band, not "the band it was in"', () => {
    expect(izLiveLine({ ...SPY, live_px: 801.5, live_side: 'above' }))
      .toMatch(/above every stored band/);
    expect(izLiveLine({ ...SPY, live_px: 601.5, live_side: 'below' }))
      .toMatch(/below every stored band/);
    // The stored close may have been in NO band at all, so the old sentence
    // named a band that did not exist.
    for (const side of ['above', 'below'] as const) {
      expect(izLiveLine({ ...SPY, live_px: 700, live_side: side }))
        .not.toMatch(/the band it was last in/);
    }
  });

  it('F5: "between" is rendered — the open-air case used to say nothing', () => {
    const line = izLiveLine({ ...SPY, live_px: 745.01, live_side: 'between' });
    expect(line).toMatch(/in the open air between two stored bands, inside none of them/);
    draw({
      ...BOTH,
      indexes: { SPY: { ...SPY, live_px: 745.01, live_side: 'between' }, QQQ },
    });
    expect(screen.getByTestId('index-zone-live-SPY').textContent)
      .toMatch(/open air between two stored bands/);
  });

  it('a named band WINS over the side word, and an unknown side names no place (negative)', () => {
    expect(izLiveLine({ ...SPY, live_px: 760, live_side: 'in', live_in_band: SPY_FINE[2] }))
      .toMatch(/standing in the demand band/);
    const vague = izLiveLine({ ...SPY, live_px: 760, live_side: null, price_basis: null });
    expect(vague).toBe('live print 760.00 — a live print; it says where price is, it does not move a band.');
    // `in` with NO band sent cannot name one.
    expect(izLiveLine({ ...SPY, live_px: 760, live_side: 'in', price_basis: null }))
      .not.toMatch(/standing in the/);
  });

  it('renders NO live line when the backend sent no live print (negative)', () => {
    draw(BOTH);
    expect(screen.queryByTestId('index-zone-live-SPY')).toBeNull();
    expect(screen.queryByTestId('index-zone-live-QQQ')).toBeNull();
    expect(screen.getByTestId('index-zone-ladder-SPY')).toBeTruthy();
  });
});

/* ── F1 / F2: the placeholders and the age line ───────────────────────────── */

describe('IndexZones — what it says when it has nothing', () => {
  beforeEach(() => { _resetIndexZonesFallback(); });
  afterEach(() => vi.unstubAllGlobals());

  it('F1: with NO board payload it fetches the stored doc ITSELF and renders it', async () => {
    const f = stubQuiet(BOTH);
    vi.stubGlobal('fetch', f);
    draw(undefined);
    await waitFor(() => expect(screen.getByTestId('index-zone-ladder-SPY')).toBeTruthy());
    expect(screen.getByTestId('index-zone-ladder-QQQ')).toBeTruthy();
    const hits = f.mock.calls.filter((c) => String(c[0]).includes('/supply-demand/index-zones'));
    // ONE request for TWO cards — the module promise is shared.
    expect(hits).toHaveLength(1);
  });

  it('F1: a board that ANSWERED never triggers the strip\'s own request (negative)', async () => {
    const f = stubQuiet(BOTH);
    vi.stubGlobal('fetch', f);
    draw(BOTH);
    await waitFor(() => expect(screen.getByTestId('index-zone-ladder-SPY')).toBeTruthy());
    expect(f.mock.calls.filter((c) => String(c[0]).includes('/supply-demand/index-zones')))
      .toHaveLength(0);
  });

  it('F1: a FAILED request and an EMPTY store are different sentences', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline'); }));
    const { unmount } = draw(undefined);
    await waitFor(() => expect(screen.getByTestId('index-zone-failed-SPY')).toBeTruthy());
    const failed = screen.getByTestId('index-zone-failed-SPY').textContent || '';
    expect(failed).toMatch(/request failure, not an empty store/i);
    expect(failed).not.toMatch(/the overnight job has not written one/i);
    expect(screen.queryByTestId('index-zone-empty-SPY')).toBeNull();
    unmount();

    _resetIndexZonesFallback();
    vi.stubGlobal('fetch', stubQuiet({ date: null, indexes: {}, stale_sessions: null }));
    draw(undefined);
    await waitFor(() => expect(screen.getByTestId('index-zone-empty-SPY')).toBeTruthy());
    expect(screen.getByTestId('index-zone-empty-SPY').textContent)
      .toMatch(/the overnight job has not written one/i);
    expect(screen.queryByTestId('index-zone-failed-SPY')).toBeNull();
  });

  it('F1: while its own request is in flight it says so, not that nothing was written', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    draw(undefined);
    expect(screen.getByTestId('index-zone-loading-SPY').textContent)
      .toMatch(/Reading the stored structure for SPY/i);
    expect(screen.queryByTestId('index-zone-empty-SPY')).toBeNull();
    expect(screen.queryByTestId('index-zone-failed-SPY')).toBeNull();
  });

  it('renders BOTH placeholder cards for every shape of missing payload (negative)', async () => {
    for (const payload of [undefined, null, {} as CmIndexZones, { indexes: null } as CmIndexZones]) {
      _resetIndexZonesFallback();
      vi.stubGlobal('fetch', stubQuiet({ indexes: {} }));
      const { unmount } = draw(payload);
      expect(screen.getByTestId('index-zones')).toBeTruthy();
      for (const sym of INDEX_ZONE_SYMBOLS) {
        expect(screen.getByTestId(`index-zone-${sym}`)).toBeTruthy();
      }
      await waitFor(() => expect(screen.getByTestId('index-zone-empty-SPY').textContent)
        .toMatch(/the overnight job has not written one/i));
      unmount();
    }
  });

  it('renders one index present and the other unavailable (negative)', () => {
    vi.stubGlobal('fetch', stubQuiet());
    draw({ date: '2026-09-16', indexes: { SPY }, stale_sessions: 1, stale_days: 3 });
    expect(screen.getByTestId('index-zone-ladder-SPY')).toBeTruthy();
    expect(screen.queryByTestId('index-zone-ladder-QQQ')).toBeNull();
    expect(screen.getByTestId('index-zone-empty-QQQ').textContent).toContain('QQQ');
    // F2 — the SESSION count comes from stale_sessions. The card carries a
    // 3-calendar-day gap at the same time (a Friday doc read on a Monday) and
    // the header must not print that 3 beside the word "session".
    const head = screen.getByTestId('index-zones').textContent || '';
    expect(head).toMatch(/1 session old/);
    expect(head).not.toMatch(/3 session/);
  });

  it('F2 NEGATIVE: calendar days alone are labelled calendar days, never sessions', () => {
    vi.stubGlobal('fetch', stubQuiet());
    draw({ date: '2026-09-12', indexes: { SPY, QQQ }, stale_days: 4 });
    const head = screen.getByTestId('index-zones').textContent || '';
    expect(head).toMatch(/stored 4 calendar days ago/);
    expect(head).not.toMatch(/session[s]? old/);
  });

  it('does NOT crash on a malformed read — bands not an array, lo/hi null (negative)', () => {
    vi.stubGlobal('fetch', stubQuiet());
    const bad = {
      symbol: 'SPY', as_of: null, close: null,
      bands: 'nope',
      ceiling: { lo: null, hi: null, dist_pct: null },
      floor: null,
      sentence: null,
    } as unknown as CmIndexZoneRead;
    const worse = {
      symbol: 'QQQ', close: 704.54, as_of: '2026-09-16',
      bands: [{ kind: 'demand', lo: null, hi: null, touches: null, strength: null, side: 'in' },
              null, { kind: 'wat', lo: 1, hi: 2 }],
      sentence: 'QQQ: structure incomplete.',
    } as unknown as CmIndexZoneRead;

    expect(() => draw({ indexes: { SPY: bad, QQQ: worse } })).not.toThrow();
    expect(screen.getByTestId('index-zone-noladder-SPY').textContent)
      .toMatch(/carried no bands/i);
    // Null prices print an em dash, never a 0.00 that reads as a price.
    expect(screen.getByTestId('index-zone-edges-SPY').textContent)
      .toContain('Ceiling — – —, — up');
    const rows = screen.getByTestId('index-zone-ladder-QQQ').querySelectorAll('.iz-band');
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain('— – —');
    expect(rows[0].textContent).not.toMatch(/0\.00/);
    expect(rows[1].getAttribute('data-kind')).toBe('band');
    // A read with no bars draws no chart and does not take the card with it.
    expect(screen.queryByTestId('index-zone-chart-SPY')).toBeNull();
  });

  it('NEGATIVE: the strip never says "bounce" — the word is reversal', () => {
    vi.stubGlobal('fetch', stubQuiet());
    draw({ ...BOTH, note: 'Structure only.' });
    expect(screen.getByTestId('index-zones').textContent).not.toMatch(/bounce/i);
    const { container } = render(<MemoryRouter><IndexZones /></MemoryRouter>);
    expect(container.textContent).not.toMatch(/bounce/i);
  });

  it('NEGATIVE: no claim of edge, and nothing that reads as buy / sell advice', () => {
    vi.stubGlobal('fetch', stubQuiet());
    draw(BOTH);
    const text = screen.getByTestId('index-zones').textContent || '';
    for (const banned of [
      /\bbuy\b/i, /\bsell\b/i, /\bedge\b/i, /outperform/i, /\bsignal\b/i,
      /forecast/i, /predict/i, /recommend/i, /\bshould\b/i, /\bwill\b/i,
      /high[- ]probability/i, /\bentry\b/i, /\btarget\b/i, /win rate/i,
      /backtest/i,
    ]) {
      expect(text).not.toMatch(banned);
    }
    expect(text).toMatch(/gates nothing, orders nothing, alerts nothing and enters nothing/i);
    expect(text).toMatch(/not advice/i);
    expect(text).toMatch(/never filtered by the board controls below/i);
  });
});

describe('IndexZones helpers', () => {
  it('izPrice / izDist / izRange never turn a missing number into a zero (negative)', () => {
    expect(izPrice(757.39)).toBe('757.39');
    expect(izPrice(null)).toBe('—');
    expect(izPrice(NaN)).toBe('—');
    expect(izPrice('757.39')).toBe('—');
    expect(izDist(2.3649)).toBe('2.36%');
    expect(izDist(-2.36)).toBe('2.36%');
    expect(izDist(undefined)).toBe('—');
    expect(izRange({ lo: 749.53, hi: 779.37 })).toBe('749.53 – 779.37');
    expect(izRange(null)).toBe('— – —');
  });

  it('izWhere reads the SERVED side and distance, and always names the close', () => {
    expect(izWhere(SPY_FINE[3], '2026-09-16')).toBe('the 2026-09-16 close is inside this band');
    expect(izWhere(SPY_FINE[2], '2026-09-16')).toBe('0.28% above the 2026-09-16 close');
    expect(izWhere(SPY_FINE[4], '2026-09-16')).toBe('0.93% below the 2026-09-16 close');
    // No date on the doc: it still says CLOSE, it just cannot name the session.
    expect(izWhere(SPY_FINE[3])).toBe('the close is inside this band');
    expect(izWhere(null)).toBe('');
    expect(izWhere({ kind: 'demand', lo: 1, hi: 2 })).toBe('');
    expect(izWhere({ kind: 'demand', lo: 1, hi: 2, side: 'below' }, '2026-09-16'))
      .toBe('below the 2026-09-16 close');
  });

  it('izEdge names the band KIND, and omits it rather than guessing (negative)', () => {
    expect(izEdge({ lo: 759.48, hi: 762.04, dist_pct: 0.28, kind: 'demand' }))
      .toBe('demand band 759.48 – 762.04');
    expect(izEdge({ lo: 721.89, hi: 748.65, kind: 'supply' }))
      .toBe('supply band 721.89 – 748.65');
    expect(izEdge({ lo: 1, hi: 2 })).toBe('1.00 – 2.00');
    expect(izEdge({ lo: 1, hi: 2, kind: 'wat' } as never)).toBe('1.00 – 2.00');
    expect(izEdge(null)).toBe('');
  });

  it('izBasis names the session and the overnight job; izLiveLine is null without a print', () => {
    expect(izBasis(SPY)).toMatch(/closed daily bars through the 2026-09-16 close \(757\.39\)/);
    expect(izBasis({ as_of: null, close: null })).toMatch(/closed daily bars/);
    expect(izLiveLine(SPY)).toBeNull();
    expect(izLiveLine({ ...SPY, live_px: null })).toBeNull();
    expect(izLiveLine({ ...SPY, live_px: NaN })).toBeNull();
  });
});

/* THE MOUNT — "keep them always in the in demand zone page". These board
 * states are the ones that used to make a strip disappear or lie. */
const ZONES_WITH_INDEXES = {
  tab: 'zones', count: 0, tiles: [], index_zones: BOTH,
  note: 'Nothing matched on this tab right now.',
};

function stubFetch(payload: unknown, indexZones?: unknown) {
  return vi.fn(async (url: string) => {
    if (String(url).includes('/supply-demand/index-zones')) {
      return indexZones === undefined
        ? ({ ok: false, status: 404, json: async () => ({}) } as Response)
        : ({ ok: true, status: 200, json: async () => indexZones } as Response);
    }
    const tab = new URL(url, 'http://x').searchParams.get('tab');
    if (tab === 'zones') return { ok: true, status: 200, json: async () => payload } as Response;
    return { ok: true, status: 200, json: async () => ({ tab, count: 0, tiles: [] }) } as Response;
  });
}

const page = () => render(
  <MemoryRouter initialEntries={['/chart-maps?tab=zones']}><ChartMaps /></MemoryRouter>,
);

describe('IndexZones is pinned to the Back in Demand tab', () => {
  beforeEach(() => { _resetIndexZonesFallback(); });
  afterEach(() => vi.unstubAllGlobals());

  it('renders when the board matched NOTHING', async () => {
    vi.stubGlobal('fetch', stubFetch(ZONES_WITH_INDEXES));
    page();
    await waitFor(() => expect(screen.getByTestId('index-zones')).toBeTruthy());
    expect(screen.getByTestId('index-zone-ladder-SPY')).toBeTruthy();
    expect(screen.getByTestId('index-zone-ladder-QQQ')).toBeTruthy();
    expect(screen.getByTestId('index-zone-chart-SPY')).toBeTruthy();
  });

  it('renders while the board is still WARMING', async () => {
    vi.stubGlobal('fetch', stubFetch({
      tab: 'zones', count: 0, tiles: [], warming: true,
      progress: null, universe_key: 'full', index_zones: BOTH,
    }));
    page();
    await waitFor(() => expect(screen.getByTestId('index-zones')).toBeTruthy());
    expect(screen.getByText(/appear here as soon as it lands/i)).toBeTruthy();
    expect(screen.getByTestId('index-zone-ladder-SPY')).toBeTruthy();
  });

  it('F1: the board 500s and the strip still draws the stored doc, from its own request', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (String(url).includes('/supply-demand/index-zones')) {
        return { ok: true, status: 200, json: async () => BOTH } as Response;
      }
      return { ok: false, status: 500 } as Response;
    }));
    page();
    await waitFor(() => expect(screen.getByTestId('index-zone-ladder-SPY')).toBeTruthy());
    // This is the whole finding: the board failed, and the strip is complete.
    expect(screen.getByTestId('index-zone-chart-SPY')).toBeTruthy();
    expect(screen.queryByTestId('index-zone-empty-SPY')).toBeNull();
  });

  it('F1 NEGATIVE: both requests failing says so, and does not blame the overnight job', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 500 } as Response)));
    page();
    await waitFor(() => expect(screen.getByTestId('index-zones')).toBeTruthy());
    for (const sym of INDEX_ZONE_SYMBOLS) {
      await waitFor(() => expect(screen.getByTestId(`index-zone-failed-${sym}`)).toBeTruthy());
      expect(screen.queryByTestId(`index-zone-empty-${sym}`)).toBeNull();
    }
  });

  it('renders when the payload carries NO index_zones key at all (negative)', async () => {
    vi.stubGlobal('fetch', stubFetch({ tab: 'zones', count: 0, tiles: [] }, { indexes: {} }));
    page();
    await waitFor(() => expect(screen.getByTestId('index-zones')).toBeTruthy());
    await waitFor(() => expect(screen.getByTestId('index-zone-empty-SPY')).toBeTruthy());
    expect(screen.getByTestId('index-zone-empty-QQQ')).toBeTruthy();
  });

  it('does NOT render on another tab — it is the in-demand page pin (negative)', async () => {
    vi.stubGlobal('fetch', stubFetch(ZONES_WITH_INDEXES));
    render(<MemoryRouter initialEntries={['/chart-maps?tab=vcp']}><ChartMaps /></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole('tab', { name: /Strong VCP/ })).toBeTruthy());
    expect(screen.queryByTestId('index-zones')).toBeNull();
  });
});

// ── 2026-09-16 review: the overlay must belong to the set on screen ─────────
describe('IndexZones — the live overlay follows the resolution you are looking at', () => {
  beforeEach(() => { _resetIndexZonesFallback(); });

  const BOARD_BAND = { kind: 'demand' as const, lo: 640, hi: 665, mid: 652.5,
                       touches: 5, strength: 60, side: 'in' as const, dist_pct: 0 };
  const READ = {
    symbol: 'SPY', as_of: '2026-09-16', close: 652,
    bars: [{ t: '2026-09-16', o: 648, h: 660, l: 641, c: 652, v: 1 }],
    // the FLAT (board) overlay says the print is standing IN a band…
    live_px: 652, live_side: 'in' as const, live_in_band: BOARD_BAND,
    price_basis: 'live print, bands from the 2026-09-16 close',
    resolutions: {
      board: { bands: [BOARD_BAND], in_band: BOARD_BAND, sentence: 'board',
               live_px: 652, live_side: 'in' as const, live_in_band: BOARD_BAND },
      // …while the FINE set says it is in the open air between two of them
      fine: {
        bands: [
          { kind: 'demand' as const, lo: 655, hi: 659, mid: 657, touches: 3, strength: 40, side: 'above' as const, dist_pct: 0.46 },
          { kind: 'demand' as const, lo: 645, hi: 649, mid: 647, touches: 3, strength: 40, side: 'below' as const, dist_pct: 0.46 },
        ],
        in_band: null, sentence: 'fine',
        live_px: 652, live_side: 'between' as const, live_in_band: null,
      },
    },
    default_resolution: 'fine',
  };

  it('never names a board band while the FINE chart is on screen', () => {
    render(<MemoryRouter><IndexZones data={{ date: '2026-09-16', default_resolution: 'fine',
      indexes: { SPY: READ } } as never} /></MemoryRouter>);
    const live = screen.getByTestId('index-zone-live-SPY').textContent || '';
    expect(live).not.toMatch(/640/);
    expect(live).not.toMatch(/665/);
    const ladder = screen.getByTestId('index-zone-ladder-SPY').textContent || '';
    expect(ladder).not.toMatch(/640\.00/);
  });

  it('izLiveSource prefers the view overlay and falls back to the flat keys', () => {
    const withOwn = izLiveSource(READ as never, READ.resolutions.fine as never);
    expect(withOwn.live_side).toBe('between');
    expect(withOwn.live_in_band).toBeNull();
    const legacy = izLiveSource(READ as never, { bands: [] } as never);
    expect(legacy.live_side).toBe('in');
  });

  it('NEGATIVE: an arm with no drawable bands is never the arm it opens on', () => {
    const oneArmed = { ...READ, default_resolution: 'fine',
      resolutions: { board: READ.resolutions.board, fine: { bands: [], sentence: 'none' } } };
    render(<MemoryRouter><IndexZones data={{ date: '2026-09-16', default_resolution: 'fine',
      indexes: { SPY: oneArmed } } as never} /></MemoryRouter>);
    expect(screen.getByTestId('index-zone-ladder-SPY').textContent).toMatch(/640/);
  });

  it('honours the PAYLOAD-level default, which is where the backend sends it', () => {
    render(<MemoryRouter><IndexZones data={{ date: '2026-09-16', default_resolution: 'board',
      indexes: { SPY: { ...READ, default_resolution: undefined } } } as never} /></MemoryRouter>);
    expect(screen.getByTestId('index-zone-ladder-SPY').textContent).toMatch(/640/);
  });
});
