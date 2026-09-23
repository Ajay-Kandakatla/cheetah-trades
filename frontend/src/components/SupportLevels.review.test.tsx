/* The Support tab, after the review round on the 2026-09-22 frame change.
 *
 * The change made every intraday frame read its OWN bars. These pin the four
 * things the reviewers measured going wrong ON SCREEN as a result — each one
 * on the frames Ajay was told to use for entries:
 *
 *   * the empty "Support below" table named the pinned DAILY zoom ("the last
 *     6 months") for an emptiness that came from 79 five-minute bars, and
 *     pointed at a zoom control that does not render there;
 *   * the Last-tested column printed five-minute bars as trading sessions;
 *   * the signal block promised the forward ledger on a frame that is not
 *     written to it;
 *   * picking an intraday frame and coming back narrowed the daily chart from
 *     the 1 year he was on to 1 month, silently.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SupportLevels } from './SupportLevels';
import { type SupportLevel, type SupportPayload } from '../lib/supportLevels';

vi.mock('./PatternChart', () => ({
  PatternChart: ({ tile }: any) => <div data-testid="chart">{tile.symbol}</div>,
}));

function lvl(over: Partial<SupportLevel> = {}): SupportLevel {
  return {
    lo: 144.50, hi: 145.96, mid: 145.23, origin: 'demand', touches: 13,
    strength: 60, bars_since_test: 6, oldest_touch_bars: 70, recent: true,
    tested: true, distance_pct: 0.4, ...over,
  };
}

/* PTGX on `?tf=5m_today`, measured live 2026-09-22 from the branch worktree:
 * an EMPTY `supports`, one overhead band, price standing inside a 13x-tested
 * band, the window pinned to 6 months and the board's own band below. */
const ENTRY_FRAME: SupportPayload = {
  symbol: 'PTGX',
  name: 'Protagonist Therapeutics',
  window: '6m',
  window_label: '6 months',
  windows: [
    { key: '1m', label: '1 month', bars: 21 },
    { key: '6m', label: '6 months', bars: 126 },
    { key: '1y', label: '1 year', bars: 252 },
  ],
  timeframe: '5m_today',
  timeframe_label: 'Today, for an entry',
  timeframe_bar_label: '5-minute',
  timeframes: [
    { key: '5m_today', label: 'Today, for an entry', bar_label: '5-minute',
      window_label: 'today only, from 04:00 ET',
      span: '5-minute bars · today only, from 04:00 ET', bars: 192, ext: true },
    { key: '24h', label: 'Last 24 hours', bar_label: '5-minute',
      window_label: 'the 24 hours up to the last print',
      span: '5-minute bars · the 24 hours up to the last print', bars: 288, ext: true },
    { key: '15m', label: 'The last two weeks', bar_label: '15-minute',
      window_label: 'the last ~10 sessions',
      span: '15-minute bars · the last ~10 sessions', bars: 260 },
    { key: 'daily', label: 'The big picture', bar_label: 'daily',
      window_label: '1 year by default', span: 'daily bars · 1 year by default',
      bars: 252 },
  ],
  chart_span: '79 x 5-minute bars · today only, from 04:00 ET '
              + '· levels from these 5-minute bars',
  levels_scope: '79 x 5-minute bars',
  levels_bar_label: '5-minute',
  recent_bars: 21,
  last_price: 145.07,
  bars_used: 79,
  short_history: null,
  board: { demand: { lo: 139.46, hi: 144.43, touches: 1, distance_pct: 0.44 },
           supply: null },
  tile: {
    symbol: 'PTGX', href: '/sepa/PTGX?tab=supply', bars: [], bands: [],
    lines: [], markers: [], stats: [], why: 'x',
  } as any,
  supports: [],
  overhead: [lvl({ lo: 145.53, hi: 147.71, origin: 'supply', touches: 13,
                   bars_since_test: 5, distance_pct: 0.3 })],
  standing_in: lvl(),
  levels_capped: false,
  signal: { action: 'WAIT', mood: 20, mood_label: 'flat', reasons: [],
            blockers: [], recorded: false,
            recorded_note: 'This chart’s BUY/SELL is NOT written to the '
                           + 'forward ledger: the ledger scores an outcome '
                           + 'over a per-timeframe horizon and the 5-minute '
                           + 'frames have none.' },
  note: 'Levels are read from this chart’s own 5-minute bars.',
  disclaimer: 'Not advice.',
} as unknown as SupportPayload;

function mockFetch(payload: any) {
  const spy = vi.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => payload,
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

const noop = () => {};

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe('the entry frame’s EMPTY support table', () => {
  it('names the bars the emptiness came from, not the pinned daily zoom', async () => {
    mockFetch(ENTRY_FRAME);
    render(<SupportLevels symbol="PTGX" window="6m" tf="5m_today"
                          onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByTestId('chart')).toBeTruthy());
    const empty = document.querySelector('.sl-empty')!;
    expect(empty.textContent).toContain('79 x 5-minute bars');
    // THE REGRESSION: it said "in the last 6 months", and PTGX's own 6-month
    // read is not empty — the board's band from it is printed on this page.
    expect(empty.textContent).not.toContain('6 months');
  });

  it('does not send him to a zoom control that is not on the page', async () => {
    mockFetch(ENTRY_FRAME);
    const { container } = render(
      <SupportLevels symbol="PTGX" window="6m" tf="5m_today"
                     onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByTestId('chart')).toBeTruthy());
    // the premise: one control only on an intraday frame
    expect(container.querySelectorAll('select').length).toBe(1);
    const empty = document.querySelector('.sl-empty')!;
    expect(empty.textContent).not.toContain('Try a longer zoom');
    expect(empty.textContent).toContain('The big picture');
  });

  it('states what IS known — the band price is in, and the board’s band below', async () => {
    mockFetch(ENTRY_FRAME);
    render(<SupportLevels symbol="PTGX" window="6m" tf="5m_today"
                          onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByTestId('chart')).toBeTruthy());
    const empty = document.querySelector('.sl-empty')!.textContent || '';
    expect(empty).toContain('$144.50 – $145.96');
    expect(empty).toContain('$139.46 – $144.43');
    expect(empty).toMatch(/BOARD/);
  });
});

describe('recency is printed in the unit the bars were counted in', () => {
  it('a five-minute bar is not a trading session, in the table or the header',
     async () => {
    mockFetch(ENTRY_FRAME);
    render(<SupportLevels symbol="PTGX" window="6m" tf="5m_today"
                          onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByTestId('chart')).toBeTruthy());
    // the overhead row: 5 bars = 25 minutes, not five trading days
    expect(screen.getByText('tested 5 × 5-minute bars ago')).toBeTruthy();
    // the header's recency window: RECENT_BARS is a bar count
    expect(screen.getByText(/touched in the last 21 × 5-minute bars/)).toBeTruthy();
    // NEGATIVE: nothing on the page calls a five-minute bar a session
    expect(document.body.textContent).not.toMatch(/sessions ago/);
  });

  it('keeps the session wording on the daily frame', async () => {
    mockFetch({
      ...ENTRY_FRAME, timeframe: 'daily', levels_bar_label: 'daily',
      levels_scope: '6 months', supports: [lvl({ bars_since_test: 6 })],
    });
    render(<SupportLevels symbol="PTGX" window="6m" tf="daily"
                          onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByTestId('chart')).toBeTruthy());
    expect(screen.getAllByText('tested 6 sessions ago').length).toBeGreaterThan(0);
  });
});

describe('the forward-ledger claim', () => {
  it('is withdrawn, with the served reason, on a frame that is not recorded',
     async () => {
    mockFetch(ENTRY_FRAME);
    render(<SupportLevels symbol="PTGX" window="6m" tf="5m_today"
                          onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByTestId('chart')).toBeTruthy());
    const p = screen.getByTestId('sl-signal-ledger').textContent || '';
    expect(p).toContain('never repaints');
    expect(p).toContain('NOT written to the forward ledger');
    // THE REGRESSION: it promised a measured hit rate for a signal nothing
    // records.
    expect(p).not.toContain('the hit rate is measured from your tape');
  });

  it('NEGATIVE: a recorded frame keeps the full claim', async () => {
    mockFetch({ ...ENTRY_FRAME, timeframe: '15m',
                signal: { action: 'BUY', reasons: [], blockers: [], recorded: true } });
    render(<SupportLevels symbol="PTGX" window="1m" tf="15m"
                          onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByTestId('chart')).toBeTruthy());
    const p = screen.getByTestId('sl-signal-ledger').textContent || '';
    expect(p).toContain('the hit rate is measured from your tape');
    expect(p).not.toContain('NOT written');
  });

  it('a payload served before this key is treated as recorded', async () => {
    const { recorded, recorded_note, ...bare } = (ENTRY_FRAME as any).signal;
    mockFetch({ ...ENTRY_FRAME, signal: bare });
    render(<SupportLevels symbol="PTGX" window="6m" tf="5m_today"
                          onSymbol={noop} onWindow={noop} />);
    await waitFor(() => expect(screen.getByTestId('chart')).toBeTruthy());
    expect(screen.getByTestId('sl-signal-ledger').textContent)
      .toContain('the hit rate is measured from your tape');
  });
});

describe('the daily zoom survives a round trip through an intraday frame', () => {
  it('comes back on the year he was reading, not on the intraday pin', async () => {
    /* Ajay: "It does help with 6 months" — the long daily read is the one
     * thing he said works. Every intraday frame PINS its own window into the
     * shared `window` param, so daily 1y -> "The last two weeks" -> "The big
     * picture" handed the daily frame a current of '1m' and came back at ONE
     * MONTH. */
    mockFetch({ ...ENTRY_FRAME, timeframe: 'daily' });
    const onView = vi.fn();
    const { container, rerender } = render(
      <SupportLevels symbol="PTGX" window="1y" tf="daily"
                     onSymbol={noop} onWindow={noop} onView={onView} />);
    await waitFor(() => expect(screen.getByTestId('chart')).toBeTruthy());

    fireEvent.change(container.querySelectorAll('select')[0], { target: { value: '15m' } });
    expect(onView).toHaveBeenLastCalledWith('1m', '15m');

    // the page now re-renders on the frame's pin, exactly as the URL write does
    rerender(<SupportLevels symbol="PTGX" window="1m" tf="15m"
                            onSymbol={noop} onWindow={noop} onView={onView} />);
    await waitFor(() => expect(screen.getByTestId('chart')).toBeTruthy());
    fireEvent.change(container.querySelectorAll('select')[0], { target: { value: 'daily' } });
    expect(onView).toHaveBeenLastCalledWith('1y', 'daily');
  });

  it('NEGATIVE: a link that spells out its own window still carries it', async () => {
    mockFetch({ ...ENTRY_FRAME, timeframe: '15m' });
    const onView = vi.fn();
    const { container } = render(
      <SupportLevels symbol="PTGX" window="3m" tf="15m"
                     onSymbol={noop} onWindow={noop} onView={onView} />);
    await waitFor(() => expect(screen.getByTestId('chart')).toBeTruthy());
    fireEvent.change(container.querySelectorAll('select')[0], { target: { value: 'daily' } });
    expect(onView).toHaveBeenLastCalledWith('3m', 'daily');
  });
});
