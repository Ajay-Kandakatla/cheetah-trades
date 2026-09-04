/* ExecutionRace — engine vs Ajay on the zone-edge signals (paper).
 *
 * Ajay trades real money next to this page and the paper engine is one switch
 * from live, so every rule the component adds on top of the payload is pinned
 * here, negatives included:
 *   - rows render from the API shape: an ordered+filled row with both of his
 *     clocks, a blocked row (reason shown, every lag "—"), and an ordered row
 *     with no fill / no view / no user fill (every null is "—", never NaN);
 *   - newest signal first regardless of the server's order;
 *   - the summary strip formats seconds ("12 s" / "1m 05s") and the gap %;
 *   - the empty state says a real sentence; a bodyless payload does not crash;
 *   - a failed fetch (reject OR non-2xx) shows the one-line note, never blank,
 *     and keeps the last good table when one exists;
 *   - the poll runs once a minute while visible, skips hidden ticks, re-reads
 *     when the tab comes back, and dies with the component;
 *   - the pure helpers (lag / price / gap / ET clock / sort) without a DOM.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import {
  ExecutionRace, REFRESH_MS, DAYS, EMPTY_TEXT, UNAVAILABLE_TEXT,
  fmtLag, fmtPx, fmtEt, signedPct, fillGap, signalMs, sortNewestFirst, sideLabel,
} from './ExecutionRace';
import type { RacePayload, RaceRow } from './ExecutionRace';

const NULLS = {
  engine_order_ts: null, engine_client_order_id: null, engine_fill_ts: null, engine_fill_px: null,
  user_view_ts: null, user_view_px: null, user_fill_ts: null, user_fill_px: null,
  engine_lag_sec: null, engine_fill_lag_sec: null, user_view_lag_sec: null, user_fill_lag_sec: null,
  px_gap_view: null, px_gap_fill: null,
};

/* Server order is deliberately NOT newest-first (TJX from yesterday leads) so
 * the sort is proven, not assumed. */
const FIX: RacePayload = {
  days: 5,
  summary: {
    n: 3, n_engine_filled: 1, n_user_viewed: 1, n_user_filled: 1,
    median_engine_lag_sec: 12, median_user_view_lag_sec: 65, median_user_fill_lag_sec: 190,
    median_px_gap_fill_pct: 0.31,
  },
  rows: [
    {
      ...NULLS,
      symbol: 'TJX', side: 'demand', band: { lo: 95, hi: 100 }, day: '2026-09-02',
      signal_first_seen: '11:05', signal_ts: '2026-09-02T11:05:00-04:00', signal_px: 100.4,
      engine_order_ts: '2026-09-02T15:05:09Z', engine_client_order_id: 'ze-tjx-1', engine_lag_sec: 9,
      outcome: 'ordered', reason: null,
    },
    {
      symbol: 'NVDA', side: 'supply', band: { lo: 176, hi: 179 }, day: '2026-09-03',
      signal_first_seen: '10:12', signal_ts: '2026-09-03T10:12:00-04:00', signal_px: 179.3,
      engine_order_ts: '2026-09-03T14:12:12Z', engine_client_order_id: 'ze-nvda-1',
      engine_fill_ts: '2026-09-03T14:13:40Z', engine_fill_px: 179.5,
      user_view_ts: '2026-09-03T14:13:05Z', user_view_px: 179.6,
      user_fill_ts: '2026-09-03T14:15:10Z', user_fill_px: 180.05,
      outcome: 'ordered', reason: null,
      engine_lag_sec: 12, engine_fill_lag_sec: 100, user_view_lag_sec: 65, user_fill_lag_sec: 190,
      px_gap_view: 0.06, px_gap_fill: 0.31,
    },
    {
      ...NULLS,
      symbol: 'ANET', side: 'supply', band: { lo: 127.5, hi: 129.3 }, day: '2026-09-03',
      signal_first_seen: '09:41', signal_ts: '2026-09-03T09:41:00-04:00', signal_px: 129.4,
      outcome: 'blocked', reason: 'daily cap 4 reached',
    },
  ],
};

const EMPTY: RacePayload = {
  days: 5,
  summary: { n: 0, n_engine_filled: 0, n_user_viewed: 0, n_user_filled: 0,
             median_engine_lag_sec: null, median_user_view_lag_sec: null,
             median_user_fill_lag_sec: null, median_px_gap_fill_pct: null },
  rows: [],
};

/* Routes by URL: the race call gets the fixture (or throws / fails when told
 * to); anything else (the watchlist store behind TickerLink) gets a harmless
 * empty body. `race` may be a function so a test can fail the SECOND call. */
type RaceAnswer = unknown | (() => unknown);
function stubFetch(race: RaceAnswer) {
  const fn = vi.fn(async (url: string) => {
    if (String(url).includes('/trading/race')) {
      const body = typeof race === 'function' ? (race as () => unknown)() : race;
      if (body instanceof Error) throw body;
      if (body && typeof body === 'object' && 'status' in (body as object) && !('rows' in (body as object))) {
        const st = (body as { status: number }).status;
        return { ok: false, status: st, json: async () => ({}) } as Response;
      }
      return { ok: true, status: 200, json: async () => body } as Response;
    }
    return { ok: true, status: 200, json: async () => ({ rows: [] }) } as Response;
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}

const raceCalls = (fn: ReturnType<typeof vi.fn>) =>
  fn.mock.calls.filter((c) => String(c[0]).includes('/trading/race'));

const draw = () => render(<MemoryRouter><ExecutionRace /></MemoryRouter>);

beforeEach(() => vi.restoreAllMocks());
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('ExecutionRace — rows and summary from a live payload', () => {
  it('asks for the 5-day race with the session cookie', async () => {
    const fn = stubFetch(FIX);
    draw();
    await waitFor(() => expect(raceCalls(fn)).toHaveLength(1));
    const [url, init] = raceCalls(fn)[0] as [string, RequestInit];
    expect(url).toMatch(/\/trading\/race\?days=5$/);
    expect(init.credentials).toBe('include');
  });

  it('renders the header, the summary strip and every row newest-first', async () => {
    stubFetch(FIX);
    draw();
    expect(await screen.findByText('⏱️ Execution race — engine vs you (paper)')).toBeInTheDocument();
    expect(screen.getByText('last 5 days · refreshes every minute')).toBeInTheDocument();

    // Summary strip — label next to its formatted value.
    const stat = (label: string) => screen.getByText(label).parentElement!;
    expect(stat('signals')).toHaveTextContent('3');
    expect(stat('engine filled')).toHaveTextContent('1');
    expect(stat('you looked')).toHaveTextContent('1');
    expect(stat('you filled')).toHaveTextContent('1');
    expect(stat('median engine lag')).toHaveTextContent('12 s');
    expect(stat('median your-look lag')).toHaveTextContent('1m 05s');
    expect(stat('median your-fill lag')).toHaveTextContent('3m 10s');
    expect(stat('median price gap')).toHaveTextContent('+0.31%');

    // Newest signal first: NVDA 10:12 today, ANET 09:41 today, TJX yesterday —
    // NOT the server's order.
    const rows = screen.getAllByTestId('race-row');
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByRole('link', { name: /NVDA/ })).toBeInTheDocument();
    expect(within(rows[1]).getByRole('link', { name: /ANET/ })).toBeInTheDocument();
    expect(within(rows[2]).getByRole('link', { name: /TJX/ })).toBeInTheDocument();

    // NVDA — the full race: side, signal, engine order + fill (UTC → ET),
    // his look, his fill, and the gap ($ + %) he paid over the engine.
    const nvda = within(rows[0]);
    expect(nvda.getByText('🚀 breakout')).toBeInTheDocument();
    expect(nvda.getByText('10:12 · $179.30')).toBeInTheDocument();
    expect(nvda.getByText('12 s')).toBeInTheDocument();
    expect(nvda.getByText('fill 10:13 · $179.50')).toBeInTheDocument();
    expect(nvda.getByText('1m 05s')).toBeInTheDocument();
    expect(nvda.getByText('3m 10s · $180.05')).toBeInTheDocument();
    expect(nvda.getByText('+$0.55 (+0.31%)')).toBeInTheDocument();
    // NEGATIVE: a complete row has no "—" placeholder anywhere.
    expect(nvda.queryAllByText('—')).toHaveLength(0);
    // Ticker link lands on the Supply / Demand tab (the zone-edge surface).
    expect(nvda.getByRole('link', { name: /NVDA/ }).getAttribute('href')).toMatch(/^\/sepa\/NVDA\?.*tab=supply/);

    // ANET — blocked: the reason shows in the engine cell, his clocks are "—".
    const anet = within(rows[1]);
    expect(anet.getByText('blocked: daily cap 4 reached')).toBeInTheDocument();
    expect(anet.getAllByText('—')).toHaveLength(3);          // looked · filled · gap
    expect(anet.queryByText(/order/)).not.toBeInTheDocument();

    // TJX — ordered but no fill, never looked at, never filled by him.
    const tjx = within(rows[2]);
    expect(tjx.getByText('🧲 demand')).toBeInTheDocument();
    expect(tjx.getByText('9 s')).toBeInTheDocument();
    expect(tjx.getByText('fill —')).toBeInTheDocument();
    expect(tjx.getAllByText('—')).toHaveLength(3);           // looked · filled · gap
    // NEGATIVE: nulls never leak as NaN / "$NaN" / "null".
    expect(rows[2].textContent).not.toMatch(/NaN|null|undefined/);
    expect(screen.queryByText(EMPTY_TEXT)).not.toBeInTheDocument();
    expect(screen.queryByText(UNAVAILABLE_TEXT)).not.toBeInTheDocument();
  });

  it('shows the error outcome as "error" with the reason on hover', async () => {
    const row: RaceRow = { ...FIX.rows![2], symbol: 'CRWD', outcome: 'error', reason: 'alpaca 502' };
    stubFetch({ ...FIX, rows: [row] });
    draw();
    const cell = await screen.findByText('error');
    expect(cell.getAttribute('title')).toBe('alpaca 502');
  });
});

describe('ExecutionRace — empty and failed reads', () => {
  it('says the race has not started when there are no signals', async () => {
    stubFetch(EMPTY);
    draw();
    expect(await screen.findByText(EMPTY_TEXT)).toBeInTheDocument();
    expect(screen.getByText('median engine lag').parentElement).toHaveTextContent('—');
    expect(screen.getByText('signals').parentElement).toHaveTextContent('0');
    expect(screen.queryAllByTestId('race-row')).toHaveLength(0);
  });

  it('renders the empty state, not a crash, on a payload with no arrays', async () => {
    stubFetch({});
    draw();
    expect(await screen.findByText(EMPTY_TEXT)).toBeInTheDocument();
    expect(screen.getByText(`last ${DAYS} days · refreshes every minute`)).toBeInTheDocument();
  });

  it('shows the one-line note when the fetch rejects — never a blank card', async () => {
    stubFetch(new Error('network down'));
    draw();
    const note = await screen.findByRole('status');
    expect(note).toHaveTextContent(UNAVAILABLE_TEXT);
    expect(note.getAttribute('title')).toBe('network down');
    // NEGATIVE: an unreachable ledger must not read as "no signals".
    expect(screen.queryByText(EMPTY_TEXT)).not.toBeInTheDocument();
    expect(screen.queryByText('loading…')).not.toBeInTheDocument();
  });

  it('treats a non-2xx as unavailable too', async () => {
    stubFetch({ status: 503 });
    draw();
    const note = await screen.findByRole('status');
    expect(note).toHaveTextContent(UNAVAILABLE_TEXT);
    expect(note.getAttribute('title')).toBe('HTTP 503');
    expect(screen.queryByText(EMPTY_TEXT)).not.toBeInTheDocument();
  });

  it('keeps the last good table when a later tick fails', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let calls = 0;
    const fn = stubFetch(() => (++calls === 1 ? FIX : new Error('boom')));
    draw();
    await waitFor(() => expect(screen.getAllByTestId('race-row')).toHaveLength(3));

    await act(async () => { await vi.advanceTimersByTimeAsync(REFRESH_MS + 50); });
    await waitFor(() => expect(raceCalls(fn)).toHaveLength(2));
    expect(await screen.findByRole('status')).toHaveTextContent(UNAVAILABLE_TEXT);
    expect(screen.getAllByTestId('race-row')).toHaveLength(3);
  });
});

describe('ExecutionRace — the minute clock', () => {
  it('fetches on mount, once a minute while visible, and stops on unmount', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fn = stubFetch(EMPTY);
    const view = draw();
    await waitFor(() => expect(raceCalls(fn)).toHaveLength(1));

    await act(async () => { await vi.advanceTimersByTimeAsync(REFRESH_MS + 50); });
    expect(raceCalls(fn)).toHaveLength(2);

    view.unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(3 * REFRESH_MS); });
    // NEGATIVE: an unmounted card must not keep polling.
    expect(raceCalls(fn)).toHaveLength(2);
  });

  it('skips the tick while the tab is hidden and resumes when visible', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fn = stubFetch(EMPTY);
    draw();
    await waitFor(() => expect(raceCalls(fn)).toHaveLength(1));

    const vis = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden');
    await act(async () => { await vi.advanceTimersByTimeAsync(2 * REFRESH_MS + 50); });
    expect(raceCalls(fn)).toHaveLength(1);

    vis.mockReturnValue('visible');
    await act(async () => { await vi.advanceTimersByTimeAsync(REFRESH_MS + 50); });
    expect(raceCalls(fn)).toHaveLength(2);
    vis.mockRestore();
  });

  it('re-reads at once when the tab comes back into view', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fn = stubFetch(EMPTY);
    draw();
    await waitFor(() => expect(raceCalls(fn)).toHaveLength(1));

    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
    await waitFor(() => expect(raceCalls(fn)).toHaveLength(2));
  });
});

describe('helpers', () => {
  it('fmtLag — seconds, minutes with zero-padded seconds, hours; null and sign', () => {
    expect(fmtLag(12)).toBe('12 s');
    expect(fmtLag(0)).toBe('0 s');
    expect(fmtLag(65)).toBe('1m 05s');
    expect(fmtLag(59.6)).toBe('1m 00s');     // rounds to 60 → a minute, not "60 s"
    expect(fmtLag(190)).toBe('3m 10s');
    expect(fmtLag(3720)).toBe('1h 02m');
    expect(fmtLag(-40)).toBe('−40 s');       // he opened the page BEFORE the signal minute
    expect(fmtLag(null)).toBe('—');
    expect(fmtLag(undefined)).toBe('—');
    expect(fmtLag(Number.NaN)).toBe('—');
  });

  it('fmtPx / signedPct — two decimals, explicit sign, "—" for nulls', () => {
    expect(fmtPx(179.5)).toBe('$179.50');
    expect(fmtPx(null)).toBe('—');
    expect(signedPct(0.306)).toBe('+0.31%');
    expect(signedPct(-1.25)).toBe('−1.25%');
    expect(signedPct(0)).toBe('0.00%');
    expect(signedPct(null)).toBe('—');
  });

  it('fmtEt — UTC ISO to New York clock; garbage to ""', () => {
    expect(fmtEt('2026-09-03T14:13:40Z')).toBe('10:13');     // EDT = UTC−4
    expect(fmtEt('2026-01-15T14:13:40Z')).toBe('09:13');     // EST = UTC−5
    expect(fmtEt('nope')).toBe('');
    expect(fmtEt(null)).toBe('');
  });

  it('fillGap — from the two fills only; "—" whenever a side is missing', () => {
    const base: RaceRow = { symbol: 'X' };
    expect(fillGap({ ...base, engine_fill_px: 100, user_fill_px: 100.5 })).toEqual({ dollars: 0.5, pct: 0.5 });
    expect(fillGap({ ...base, engine_fill_px: 100, user_fill_px: 99 })!.dollars).toBeCloseTo(-1);
    expect(fillGap({ ...base, engine_fill_px: null, user_fill_px: 100 })).toBeNull();
    expect(fillGap({ ...base, engine_fill_px: 100, user_fill_px: null })).toBeNull();
    expect(fillGap({ ...base, engine_fill_px: 0, user_fill_px: 100 })).toBeNull();   // no divide-by-zero
    // NEGATIVE: the server's own gap field is not trusted over the prices.
    expect(fillGap({ ...base, engine_fill_px: null, user_fill_px: null, px_gap_fill: 0.3 })).toBeNull();
  });

  it('sortNewestFirst — signal_ts, then day+first-seen, unparseable last; stable', () => {
    const a: RaceRow = { symbol: 'A', signal_ts: '2026-09-03T10:12:00-04:00' };
    const b: RaceRow = { symbol: 'B', day: '2026-09-03', signal_first_seen: '11:00' };   // no ts → fallback
    const c: RaceRow = { symbol: 'C' };                                                     // nothing → last
    const d: RaceRow = { symbol: 'D', signal_ts: '2026-09-02T15:59:00-04:00' };
    expect(sortNewestFirst([c, d, a, b]).map((r) => r.symbol)).toEqual(['B', 'A', 'D', 'C']);
    expect(signalMs(c)).toBe(-Infinity);
    // Ties keep server order.
    const e: RaceRow = { symbol: 'E', signal_ts: a.signal_ts };
    expect(sortNewestFirst([e, a]).map((r) => r.symbol)).toEqual(['E', 'A']);
  });

  it('sideLabel — the two sides, and no invention for anything else', () => {
    expect(sideLabel('supply')).toBe('🚀 breakout');
    expect(sideLabel('demand')).toBe('🧲 demand');
    expect(sideLabel('weird')).toBe('weird');
    expect(sideLabel(null)).toBe('—');
  });
});
