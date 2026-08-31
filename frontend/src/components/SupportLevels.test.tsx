import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SupportLevels } from './SupportLevels';
import type { SupportLevel, SupportPayload } from '../lib/supportLevels';

// PatternChart draws to a canvas via lightweight-charts, which jsdom has no
// business running. The tab's job is the CONTROLS and the TABLES; the chart is
// the shared component and is covered by PatternChart.test.tsx.
vi.mock('./PatternChart', () => ({
  PatternChart: ({ tile }: any) => <div data-testid="chart">{tile.symbol}</div>,
}));

function lvl(over: Partial<SupportLevel> = {}): SupportLevel {
  return {
    lo: 148.22, hi: 152.74, mid: 150.48, origin: 'demand', touches: 4,
    strength: 72, bars_since_test: 5, oldest_touch_bars: 40, recent: true,
    tested: true,
    distance_pct: 2.4,
    ...over,
  };
}

const PAYLOAD: SupportPayload = {
  symbol: 'DHI',
  name: 'D.R. Horton',
  window: '3m',
  window_label: '3 months',
  windows: [
    { key: '1m', label: '1 month', bars: 21 },
    { key: '3m', label: '3 months', bars: 63 },
    { key: '6m', label: '6 months', bars: 126 },
  ],
  recent_bars: 21,
  last_price: 156.4,
  bars_used: 63,
  short_history: null,
  tile: {
    symbol: 'DHI', href: '/sepa/DHI?tab=supply', bars: [], bands: [],
    lines: [], markers: [], stats: [], why: 'x',
  } as any,
  supports: [lvl(), lvl({ lo: 138.0, hi: 140.5, recent: false,
                          bars_since_test: 44, distance_pct: 10.2, touches: 2 })],
  overhead: [lvl({ lo: 161.0, hi: 163.2, distance_pct: 2.9, origin: 'supply',
                   touches: 3, bars_since_test: 12 })],
  standing_in: null,
  levels_capped: false,
  note: 'Levels are read from this window only.',
  disclaimer: 'Not advice.',
};

function mockFetch(payload: any, ok = true) {
  const spy = vi.fn().mockResolvedValue({
    ok, status: ok ? 200 : 500, json: async () => payload,
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

const noop = () => {};

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe('SupportLevels', () => {
  it('does not fetch until a ticker is chosen, and says what to do', () => {
    const spy = mockFetch(PAYLOAD);
    render(<SupportLevels symbol="" window="3m" onSymbol={noop} onWindow={noop} />);
    expect(spy).not.toHaveBeenCalled();
    expect(screen.getByText(/Search a ticker above/i)).toBeTruthy();
  });

  it('renders the levels table with band, distance, evidence and recency', async () => {
    mockFetch(PAYLOAD);
    render(<SupportLevels symbol="DHI" window="3m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByText('$148.22 – $152.74')).toBeTruthy());
    expect(screen.getByText('2.4% below')).toBeTruthy();
    expect(screen.getByText('4 touches')).toBeTruthy();
    // Twice on purpose: the headline summarises the nearest support and the
    // table row states it. If the two ever disagree, that is the bug.
    expect(screen.getAllByText(/tested 5 sessions ago/).length).toBe(2);
  });

  it('shows the overhead alongside the support', async () => {
    // The DHI read on 2026-08-19 was exactly this shape: supply sitting right
    // above the demand band. A support table that hid the ceiling would be the
    // more dangerous half of the picture.
    mockFetch(PAYLOAD);
    render(<SupportLevels symbol="DHI" window="3m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByText('Overhead')).toBeTruthy());
    expect(screen.getByText('+2.9%')).toBeTruthy();
  });

  it('counts recency and evidence SEPARATELY — neither implies the other', async () => {
    // One support is recent-and-tested, the other is stale-and-tested. A single
    // "1 of 2" would let a level touched yesterday once read as a held floor.
    mockFetch(PAYLOAD);
    render(<SupportLevels symbol="DHI" window="3m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByText(/1 of 2 touched/)).toBeTruthy());
    expect(screen.getByText(/2 of 2 turned at more than once/)).toBeTruthy();
  });

  it('marks a single-touch level as a low rather than a floor', async () => {
    // The live smoke test on 2026-08-19 found NVDA's nearest support was one
    // touch, 0.03% below price, at every zoom. That is the row that must not
    // read like a place to put a stop.
    mockFetch({ ...PAYLOAD, overhead: [],
                supports: [lvl({ touches: 1, tested: false, distance_pct: 0.03 })] });
    render(<SupportLevels symbol="NVDA" window="1m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByText('1 touch · single low')).toBeTruthy());
    expect(screen.getByText(/not a tested floor/)).toBeTruthy();
  });

  it('offers the windows the SERVER sent, not a hardcoded list', async () => {
    mockFetch(PAYLOAD);
    const { container } = render(
      <SupportLevels symbol="DHI" window="3m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByText('$148.22 – $152.74')).toBeTruthy());
    const opts = Array.from(container.querySelectorAll('option')).map((o) => o.textContent);
    expect(opts).toEqual(['1 month', '3 months', '6 months']);   // no 1 year
  });

  it('reports the chosen window upward rather than owning it', async () => {
    mockFetch(PAYLOAD);
    const onWindow = vi.fn();
    const { container } = render(
      <SupportLevels symbol="DHI" window="3m" onSymbol={noop} onWindow={onWindow} />);
    await waitFor(() => expect(screen.getByText('$148.22 – $152.74')).toBeTruthy());
    fireEvent.change(container.querySelector('select')!, { target: { value: '6m' } });
    expect(onWindow).toHaveBeenCalledWith('6m');
  });

  it('refetches when the window changes', async () => {
    const spy = mockFetch(PAYLOAD);
    const { rerender } = render(
      <SupportLevels symbol="DHI" window="3m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    rerender(<SupportLevels symbol="DHI" window="6m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
    expect(String(spy.mock.calls[1][0])).toContain('window=6m');
  });

  /* ── negatives ──────────────────────────────────────────────────────────── */

  it('shows the backend error instead of an empty table', async () => {
    mockFetch({ ...PAYLOAD, tile: undefined, supports: undefined,
                error: 'No swing structure for ZZZZ over 1 month — try a longer window.' });
    render(<SupportLevels symbol="ZZZZ" window="1m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByText(/try a longer window/)).toBeTruthy());
  });

  it('keeps the zoom dropdown usable after a miss, since that is the fix', async () => {
    mockFetch({ ...PAYLOAD, tile: undefined, error: 'No swing structure.' });
    const { container } = render(
      <SupportLevels symbol="ZZZZ" window="1m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByText(/No swing structure/)).toBeTruthy());
    expect(container.querySelector('select')).toBeTruthy();
  });

  it('surfaces a transport failure without blanking the panel', async () => {
    mockFetch({}, false);
    render(<SupportLevels symbol="DHI" window="3m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByText(/Couldn't load DHI/)).toBeTruthy());
  });

  it('warns when the frame was shorter than the window asked for', async () => {
    mockFetch({ ...PAYLOAD, bars_used: 30, short_history: { have: 30, asked: 126 } });
    render(<SupportLevels symbol="IPO" window="6m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByText(/Only 30 sessions of history/)).toBeTruthy());
  });

  it('says there is nothing to lean on rather than showing an empty box', async () => {
    mockFetch({ ...PAYLOAD, supports: [] });
    render(<SupportLevels symbol="DHI" window="3m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() =>
      expect(screen.getByText(/nothing here to place a stop under/)).toBeTruthy());
  });

  it('never prints NaN when the backend omits a distance', async () => {
    mockFetch({ ...PAYLOAD, supports: [lvl({ distance_pct: null })], overhead: [] });
    const { container } = render(
      <SupportLevels symbol="DHI" window="3m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByText('$148.22 – $152.74')).toBeTruthy());
    expect(container.textContent).not.toContain('NaN');
  });
});

/* ── Timeframe dropdown, computed entry/stop, ORB, patterns (2026-08-29) ──
 * Ajay: "ORB and Fair value gap ... in Daily, Market hourly, 15 mins ...
 * Give me stop loss and Entry calculated dynamically" + bullish patterns.
 * The negatives matter most: a shape found on hourly bars must never wear
 * Bulkowski's daily hit rates. */
const TF_PAYLOAD: any = {
  ...PAYLOAD,
  timeframe: '60m',
  timeframe_label: '1 hour',
  timeframes: [
    { key: 'daily', label: 'Daily' },
    { key: '60m', label: '1 hour' },
    { key: '15m', label: '15 min' },
  ],
  atr: 4.04,
  opening_range: { lo: 223.22, hi: 229.26, minutes: 60, session: '2026-08-28' },
  fair_value_gaps: [{ kind: 'demand', lo: 213.6, hi: 216.8, source: 'fvg', fill_pct: 0 }],
  trade_levels: [
    { kind: 'demand', lo: 214.5, hi: 217.27, source: 'swing', touches: 3,
      trade: { side: 'long', entry: 217.27, stop: 213.49, target1: 224.83,
               target_basis: 'next supply band', rr: 2.0, risk_pct: 1.74 } },
    { kind: 'demand', lo: 213.6, hi: 216.8, source: 'fvg', fill_pct: 0,
      trade: { side: 'long', entry: 216.8, stop: 211.88, target1: 226.55,
               target_basis: '2R measured', rr: 1.98, risk_pct: 2.27 } },
  ],
  bullish_patterns: {
    patterns: [
      { kind: 'cup_with_handle', label: 'Cup with handle', confirmed: true,
        cited: true, stats_transfer: false, entry: 220.1, stop: 210.0, target: 236.0 },
      { kind: 'flat_top', label: 'Flat top (ascending triangle)', confirmed: false,
        cited: false, stats_transfer: false, entry: 219.0, stop: 212.0, target: 226.0 },
    ],
    stats_transfer: false,
    out_of_range: ['triple_bottom'],
  },
};

/* ── Market mood + buy/sell signal (Ajay 2026-08-29) ────────────────────── */
const SIGNAL_PAYLOAD: any = {
  ...TF_PAYLOAD,
  mood: {
    score: 42.5, label: 'bullish', rsi: 58.2, bars: 329,
    components: { trend: 25, momentum: 3.3, pressure: 6.2, vwap: 4, location: 4, structure: 0 },
    unavailable: [],
  },
  signal: {
    action: 'BUY', mood: 42.5, mood_label: 'bullish',
    reasons: ['mood 42.5 (bullish)', 'price just above a swing demand band 214.5–217.27'],
    blockers: [],
    level: { lo: 214.5, hi: 217.27, where: 'just above', distance_pct: 0.1 },
    trade: { entry: 217.27, stop: 213.49, target1: 224.83, rr: 2.0, risk_pct: 1.74 },
    no_repaint: true,
  },
};

/* ── Smart Money setups (Ajay 2026-08-29, Brad Goh's model) ─────────────── */
const SMC_PAYLOAD: any = {
  ...TF_PAYLOAD,
  smc: {
    cited: false,
    note: 'Smart Money Concepts — community-taught. No canonical text in the library.',
    setups: [{
      direction: 'bullish', score: 80, mitigated: true, cited: false,
      narrative: 'sell-side liquidity at 99.00 was swept 10 bars ago and rejected, then a CHoCH closed above 101.00.',
      entries: { aggressive: 100.5, conservative: 96.0 },
      legs: {
        aggressive: { entry: 100.5, stop: 95.38, risk_pct: 5.1, rr: 2.0 },
        conservative: { entry: 96.0, stop: 95.38, risk_pct: 0.65, rr: 23.62,
                        too_tight: true, warning: 'stop is 0.20 ATR from entry — inside noise' },
      },
      stop: 95.38, stop_tight: 95.38, target: 110.75, distance_pct: -0.2,
    }],
    sweeps: [], breaks: [], order_blocks: [],
  },
};

describe('SupportLevels — Smart Money setups', () => {
  it('tells the sweep → BOS → order block story with both entry styles', async () => {
    mockFetch(SMC_PAYLOAD);
    render(<SupportLevels symbol="NVDA" window="3m" tf="15m"
                          onSymbol={noop} onWindow={noop} onTf={noop} />);
    await waitFor(() => expect(screen.getByText(/Smart Money setups/i)).toBeTruthy());
    expect(screen.getByText(/was swept 10 bars ago/)).toBeTruthy();
    expect(screen.getByText('aggressive')).toBeTruthy();
    expect(screen.getByText('conservative')).toBeTruthy();
    expect(screen.getByText(/price is at the zone/)).toBeTruthy();
  });

  it('flags a stop inside the noise instead of selling the 23R', async () => {
    mockFetch(SMC_PAYLOAD);
    render(<SupportLevels symbol="NVDA" window="3m" tf="15m"
                          onSymbol={noop} onWindow={noop} onTf={noop} />);
    await waitFor(() => expect(screen.getByText(/23.62R/)).toBeTruthy());
    expect(screen.getByText(/⚠️ noise/)).toBeTruthy();
    expect(screen.getByText(/arithmetic, not a plan/i)).toBeTruthy();
  });

  it('states that SMC has no cited source', async () => {
    mockFetch(SMC_PAYLOAD);
    render(<SupportLevels symbol="NVDA" window="3m" tf="15m"
                          onSymbol={noop} onWindow={noop} onTf={noop} />);
    await waitFor(() =>
      expect(screen.getByText(/No canonical text in the library/i)).toBeTruthy());
  });
});

describe('SupportLevels — market mood and the buy signal', () => {
  it('shows the action, the mood and the plan that justifies it', async () => {
    mockFetch(SIGNAL_PAYLOAD);
    render(<SupportLevels symbol="NVDA" window="3m" tf="60m"
                          onSymbol={noop} onWindow={noop} onTf={noop} />);
    await waitFor(() => expect(screen.getByText(/🟢 BUY/)).toBeTruthy());
    expect(screen.getAllByText(/bullish/).length).toBeGreaterThan(0);
    expect(screen.getByText(/1.74% risk/)).toBeTruthy();
    // the component breakdown is visible so he can argue with the score
    expect(screen.getByText(/trend/)).toBeTruthy();
    // the no-repaint property is stated, not implied
    expect(screen.getByText(/never repaints/i)).toBeTruthy();
  });

  it('a WAIT states what is blocking it rather than showing nothing', async () => {
    mockFetch({
      ...SIGNAL_PAYLOAD,
      signal: {
        action: 'WAIT', mood: 8, mood_label: 'neutral', reasons: [],
        blockers: ['mood 8 below the 25 floor (neutral)',
                   'price is not within 1.5% of a demand band'],
        level: null, trade: null, no_repaint: true,
      },
    });
    render(<SupportLevels symbol="NVDA" window="3m" tf="60m"
                          onSymbol={noop} onWindow={noop} onTf={noop} />);
    await waitFor(() => expect(screen.getByText(/⏸ WAIT/)).toBeTruthy());
    expect(screen.getByText(/below the 25 floor/)).toBeTruthy();
    expect(screen.getByText(/not within 1.5%/)).toBeTruthy();
  });

  it('names the unscored components instead of reading them as neutral', async () => {
    mockFetch({
      ...SIGNAL_PAYLOAD,
      mood: { ...SIGNAL_PAYLOAD.mood, unavailable: ['vwap (intraday frames only)'] },
    });
    render(<SupportLevels symbol="NVDA" window="3m" tf="daily"
                          onSymbol={noop} onWindow={noop} onTf={noop} />);
    await waitFor(() => expect(screen.getByText(/Not scored:/)).toBeTruthy());
    expect(screen.getByText(/never a neutral-positive/)).toBeTruthy();
  });
});

describe('SupportLevels — timeframe, computed levels and patterns', () => {
  it('renders the timeframe dropdown only when the page can handle the change', async () => {
    mockFetch(TF_PAYLOAD);
    const { unmount } = render(
      <SupportLevels symbol="NVDA" window="3m" onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByText(/Support below/i)).toBeTruthy());
    expect(screen.queryByText('Timeframe')).toBeNull();
    unmount();

    mockFetch(TF_PAYLOAD);
    render(<SupportLevels symbol="NVDA" window="3m" tf="60m"
                          onSymbol={noop} onWindow={noop} onTf={noop} />);
    await waitFor(() => expect(screen.getByText('Timeframe')).toBeTruthy());
  });

  it('sends the timeframe to the API and reports the choice back', async () => {
    const spy = mockFetch(TF_PAYLOAD);
    const onTf = vi.fn();
    render(<SupportLevels symbol="NVDA" window="3m" tf="60m"
                          onSymbol={noop} onWindow={noop} onTf={onTf} />);
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(String(spy.mock.calls[0][0])).toContain('tf=60m');
    const select = screen.getByText('Timeframe').querySelector('select')!;
    fireEvent.change(select, { target: { value: '15m' } });
    expect(onTf).toHaveBeenCalledWith('15m');
  });

  it('shows a computed entry, stop and R for every band', async () => {
    mockFetch(TF_PAYLOAD);
    render(<SupportLevels symbol="NVDA" window="3m" tf="60m"
                          onSymbol={noop} onWindow={noop} onTf={noop} />);
    await waitFor(() => expect(screen.getByText(/Entry & stop, computed/i)).toBeTruthy());
    expect(screen.getByText('$217.27')).toBeTruthy();
    expect(screen.getByText('$213.49')).toBeTruthy();
    expect(screen.getByText('2R')).toBeTruthy();
    // the FVG band is labelled as one, not passed off as a swing level
    expect(screen.getByText(/Fair value gap/i)).toBeTruthy();
    expect(screen.getByText(/Opening range/i)).toBeTruthy();
  });

  it('never lets an hourly shape borrow the daily statistics', async () => {
    mockFetch(TF_PAYLOAD);
    render(<SupportLevels symbol="NVDA" window="3m" tf="60m"
                          onSymbol={noop} onWindow={noop} onTf={noop} />);
    await waitFor(() => expect(screen.getByText(/Cup with handle/i)).toBeTruthy());
    expect(screen.getByText(/do not transfer to this timeframe/i)).toBeTruthy();
    // an uncited shape says so
    expect(screen.getByText(/no cited source/i)).toBeTruthy();
    // patterns the bar budget cannot reach are named, not silently missing
    expect(screen.getByText(/triple bottom/i)).toBeTruthy();
  });

  it('renders cleanly when the backend sends no timeframe extras at all', async () => {
    mockFetch(PAYLOAD);
    render(<SupportLevels symbol="NVDA" window="3m" tf="daily"
                          onSymbol={noop} onWindow={noop} onTf={noop} />);
    await waitFor(() => expect(screen.getByText(/Support below/i)).toBeTruthy());
    expect(screen.queryByText(/Entry & stop, computed/i)).toBeNull();
    expect(screen.queryByText(/Opening range/i)).toBeNull();
  });
});
