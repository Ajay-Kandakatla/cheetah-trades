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
