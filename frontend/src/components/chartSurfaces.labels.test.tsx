/* Two sentences that broke when a frame's `label` stopped being a bar size,
 * and one band that is pointed at but not drawn (review round, 2026-09-23).
 *
 * Since 2026-09-22 `tf_spec(key)['label']` names the JOB — "The big picture",
 * "The last two weeks" — because that is what belongs in a dropdown row. Three
 * sentences outside the dropdown still spliced it in adjectivally. And on an
 * intraday frame the board's daily band usually falls outside the plotted
 * domain, so `clipBands` drops it while the served note still calls it "the
 * dashed band".
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import { ZoneMap } from './ZoneMap';
import type { CmTile } from '../lib/chartMaps';

vi.mock('./ZoneChart', () => ({ ZoneChart: () => <div data-testid="zone-chart" /> }));

/* ── the board band that the plot dropped ────────────────────────────────── */

/* NVDA on the 24-hour frame, measured 2026-09-22: candles 225.56-229.44 and
 * a board demand band at 212.19-216.82 — more than one chart-height below, so
 * `barDomain` refuses to stretch to it and `clipBands` discards it. */
const nvdaBars = Array.from({ length: 12 }, (_, i) => {
  const c = 226 + (i % 4) * 0.8;
  return { t: `2026-09-22 09:${String(30 + i * 5).padStart(2, '0')}`,
           o: c - 0.2, h: Math.min(c + 1.2, 229.44), l: Math.max(c - 1.2, 225.56),
           c, v: 1_000 };
});

const NVDA_TILE: CmTile = {
  symbol: 'NVDA',
  href: '/sepa/NVDA?tab=supply',
  bars: nvdaBars,
  bands: [
    { kind: 'demand', lo: 225.56, hi: 229.44, label: 'here · 29× tested' },
    { kind: 'board_demand', lo: 212.19, hi: 216.82, label: 'board demand · 4× tested' },
  ],
  lines: [],
  markers: [],
  stats: [],
  why: 'The dashed band is the demand BOARD’s band.',
} as any;

describe('a board band off the plot says where it went', () => {
  it('prints its numbers and the side it fell off', () => {
    render(<MemoryRouter><PatternChart tile={NVDA_TILE} height={320} /></MemoryRouter>);
    const svg = document.querySelector('svg')!;
    // the premise: no rectangle was drawn for it
    expect(svg.querySelector('[data-band-kind="board_demand"]')).toBeNull();
    const off = svg.querySelector('[data-band-kind="board_demand-off"]');
    expect(off).not.toBeNull();
    const text = off!.textContent || '';
    expect(text).toContain('212.19');
    expect(text).toContain('216.82');
    expect(text).toContain('below this chart');
  });

  it('NEGATIVE: says nothing when the board band IS on the chart', () => {
    const tile = {
      ...NVDA_TILE,
      bands: [{ kind: 'board_demand', lo: 226.0, hi: 227.0, label: 'board demand' }],
    } as CmTile;
    render(<MemoryRouter><PatternChart tile={tile} height={320} /></MemoryRouter>);
    const svg = document.querySelector('svg')!;
    expect(svg.querySelector('[data-band-kind="board_demand-off"]')).toBeNull();
    expect(svg.querySelector('[data-band-kind="board_demand"]')).not.toBeNull();
  });

  it('NEGATIVE: an ordinary overlay off the plot gets no edge note', () => {
    const tile = {
      ...NVDA_TILE,
      bands: [{ kind: 'demand', lo: 100, hi: 101, label: 'far away' }],
    } as CmTile;
    render(<MemoryRouter><PatternChart tile={tile} height={320} /></MemoryRouter>);
    expect(document.querySelector('[data-band-kind="demand-off"]')).toBeNull();
  });
});

/* ── the zone map's two sentences ────────────────────────────────────────── */

const ZONE_PAYLOAD = {
  symbol: 'NVDA',
  name: 'NVIDIA',
  last_price: 228.56,
  timeframe: 'daily',
  timeframe_label: 'The big picture',
  timeframe_bar_label: 'daily',
  supply_zones: [],
  demand_zones: [],
  nearest_resistance: null,
  nearest_support: null,
  // ZoneMap refuses to draw under two bars; ZoneChart itself is mocked.
  series: [
    { date: '2026-09-19', open: 226, high: 229, low: 225, close: 228, volume: 1 },
    { date: '2026-09-22', open: 228, high: 230, low: 227, close: 228.56, volume: 1 },
  ],
  in_demand_band: false,
  is_reentry: false,
  fell_from_pct: null,
  bars_since_above: null,
  trade_levels: [{
    source: 'swing', lo: 224.0, hi: 226.0,
    trade: { side: 'long', entry: 226.0, stop: 223.0, target1: 232.0,
             target_basis: 'band', rr: 2 },
  }],
};

function mockFetch(payload: any) {
  const spy = vi.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => payload,
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe('the zone map names a BAR SIZE where it needs a noun', () => {
  it('"Entry & stop on daily bars", never "on The big picture bars"', async () => {
    mockFetch(ZONE_PAYLOAD);
    render(<MemoryRouter><ZoneMap symbol="NVDA" /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('zone-chart')).toBeTruthy());
    expect(screen.getByText('Entry & stop on daily bars')).toBeTruthy();
    expect(document.body.textContent).not.toContain('The big picture bars');
  });

  it('and the unavailable banner reads as a sentence too', async () => {
    mockFetch({ ...ZONE_PAYLOAD, timeframe: '15m',
                timeframe_label: 'The last two weeks',
                timeframe_bar_label: '15-minute',
                trade_levels: [], tf_error: 'no intraday bars' });
    render(<MemoryRouter><ZoneMap symbol="NVDA" /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('zone-chart')).toBeTruthy());
    expect(document.body.textContent)
      .toContain('15-minute bands unavailable — no intraday bars');
    expect(document.body.textContent).not.toContain('The last two weeks bands');
  });

  it('a payload served before the key still reads as English', async () => {
    const { timeframe_bar_label, ...older } = ZONE_PAYLOAD as any;
    mockFetch(older);
    render(<MemoryRouter><ZoneMap symbol="NVDA" /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId('zone-chart')).toBeTruthy());
    expect(screen.getByText('Entry & stop on these bars')).toBeTruthy();
  });
});
