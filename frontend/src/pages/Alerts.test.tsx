/* Alerts page — what pushed to the phone, and why it was quiet.
 *
 * Ajay 2026-09-05: "can I go to a dedicated page to see the list of alerts?"
 * Real money rides on reading these right, so the page's own rules are pinned
 * with negatives: the default filter is the three zone kinds ONLY; every time
 * is ET; the day picker moves `since` (and "Yesterday" is yesterday ONLY); the
 * ticker box filters server-side after a debounce; an empty list says how many
 * names the gate skipped (a quiet phone is not "nothing happened"); the status
 * strip never claims a pass is live when `in_session` is false, never says
 * "reported within cadence" over a stale stamp, and renders the pass's own
 * `reason`; an undelivered row is labelled not delivered.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AlertsPage, TICKER_DEBOUNCE_MS, cadenceText, passHealth, staleAfterSec } from './Alerts';
import { _resetAlertHistoryCache } from '../hooks/useAlertHistory';
import { startOfEtDay } from '../lib/alertKinds';

const NOW = Date.parse('2026-09-05T15:00:00Z');           // Sat Sep 5, 11:00 ET
const T = (iso: string) => Date.parse(iso) / 1000;

const ROWS = [
  { _id: 'r1', ts: T('2026-09-05T14:42:00Z'), ts_iso: '2026-09-05T14:42:00+00:00', kind: 'demand_alert', ticker: 'NVDA',
    title: '🧲 NVDA in demand $176–179', url: '/sepa/NVDA?tab=supply', source: 'push', sent: 2, failed: 0, total: 2,
    body: 'Arrived inside the 3× band today (yesterday closed outside). Room +7.2% to the first supply band at $192 (1.8R). Not advice.' },
  { _id: 'r2', ts: T('2026-09-05T13:31:00Z'), ts_iso: '2026-09-05T13:31:00+00:00', kind: 'supply_break_alert', ticker: 'ANET',
    title: '🚀 ANET breaking $129', url: '/sepa/ANET?tab=supply', source: 'push', sent: 1, failed: 1, total: 2,
    body: 'Through the last supply band by +0.8%, new highs.' },
  { _id: 'r3', ts: T('2026-09-04T18:05:00Z'), ts_iso: '2026-09-04T18:05:00+00:00', kind: 'zone_bounce_alert', ticker: 'NTAP',
    title: '🪃 NTAP bounce', url: null, source: 'push', sent: 2, failed: 0, total: 2,
    body: 'Low 161.90 at 09:33 ET, +6.1% off it.' },
];

/* All three passes fresh at 11:00 ET. demand_alert carries no cadence_sec on
 * purpose (an older API) — the fallback must fill it. */
const STATUS_LIVE = {
  in_session: true, now_et: '2026-09-05T11:00:00-04:00',
  gate: { min_room_pct: 5.0, max_above_demand_pct: 1.0 },
  passes: {
    zone_edge: { as_of: '2026-09-05T10:59:07-04:00', date: '2026-09-05', cadence_sec: 60,
      counts: { candidates: 812, priced: 800, stale_print: 4, breaking: 3, near_demand: 5, skipped_room: 14, skipped_cap: 2, unknown_cap: 1, pushed: 2 } },
    zone_bounce_alert: { as_of: '2026-09-05T10:55:02-04:00', date: '2026-09-05', cadence_sec: 300,
      counts: { candidates: 640, hits: 6, skipped_room: 0, skipped_proximity: 3, skipped_cap: 0, unknown_cap: 0, pushed: 1 } },
    demand_alert: { as_of: '2026-09-05T10:58:11-04:00', date: '2026-09-05',
      counts: { candidates: 40, hits: 2, skipped_room: 0, skipped_proximity: 0, pushed: 0 } },
  },
  disclaimer: 'Configured price-structure alerts. Not advice.',
};

/* One pass never recorded today. */
const STATUS_LIVE_MISSING = {
  ...STATUS_LIVE,
  passes: { ...STATUS_LIVE.passes, demand_alert: { as_of: null, date: null, counts: {} } },
};

/* 14:30 ET, zone_edge silent since 10:02 — a dead cron mid-session. */
const STATUS_STALE = {
  ...STATUS_LIVE, now_et: '2026-09-05T14:30:00-04:00',
  passes: {
    zone_edge: { as_of: '2026-09-05T10:02:00-04:00', date: '2026-09-05', cadence_sec: 60, counts: { candidates: 812, pushed: 1 } },
    zone_bounce_alert: { as_of: '2026-09-05T14:29:02-04:00', date: '2026-09-05', cadence_sec: 300, counts: { candidates: 640, pushed: 0 } },
    demand_alert: { as_of: '2026-09-05T14:28:11-04:00', date: '2026-09-05', cadence_sec: 300, counts: { candidates: 40, pushed: 0 } },
  },
};

/* 9:36 ET on a cold store: zone_edge's pre-2026-09-05 doc (as_of null, a reason,
 * today's date); the two recorded passes ran and read nothing. */
const STATUS_REASON = {
  ...STATUS_LIVE, now_et: '2026-09-05T09:36:00-04:00',
  passes: {
    zone_edge: { as_of: null, date: '2026-09-05', cadence_sec: 60, reason: 'zone store empty for today',
      counts: { candidates: 0, pushed: 0, skipped_room: 0 } },
    zone_bounce_alert: { as_of: '2026-09-05T09:35:02-04:00', date: '2026-09-05', cadence_sec: 300, reason: 'zone store empty for today',
      counts: { candidates: 0 } },
    demand_alert: { as_of: '2026-09-05T09:33:11-04:00', date: '2026-09-05', cadence_sec: 300, reason: 'board empty or warming',
      counts: { candidates: 0 } },
  },
};

const STATUS_CLOSED = {
  ...STATUS_LIVE, in_session: false,
  passes: {
    zone_edge: { as_of: '2026-09-04T16:00:12-04:00', date: '2026-09-04', counts: { candidates: 800, pushed: 3, skipped_room: 9 } },
    zone_bounce_alert: { as_of: null, date: '2026-09-04', reason: 'zone store empty for today', counts: { candidates: 0 } },
    demand_alert: { as_of: null, date: null, counts: {} },
  },
};

/* Routes by URL: status, recent (recorded so the query can be asserted),
 * and anything else (the watchlist store behind TickerLink) → empty. */
function stubFetch(recent: unknown = { rows: ROWS }, status: unknown = STATUS_LIVE) {
  const fn = vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/alerts/status')) return { ok: true, status: 200, json: async () => status } as Response;
    if (u.includes('/notifications/recent')) return { ok: true, status: 200, json: async () => recent } as Response;
    return { ok: true, status: 200, json: async () => ({ rows: [] }) } as Response;
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}
const recentUrls = (fn: ReturnType<typeof vi.fn>) =>
  fn.mock.calls.map((c) => String(c[0])).filter((u) => u.includes('/notifications/recent'));
const lastRecent = (fn: ReturnType<typeof vi.fn>) => new URL(recentUrls(fn).slice(-1)[0], 'http://x');

const draw = (entry = '/alerts') =>
  render(<MemoryRouter initialEntries={[entry]}><AlertsPage /></MemoryRouter>);
/* Let the ticker debounce fire, the URL commit and the refetch it triggers all
 * flush inside act (the stubbed fetch resolves on microtasks). */
const settle = () => act(() => new Promise<void>((r) => setTimeout(r, TICKER_DEBOUNCE_MS + 40)));
const flush = () => act(() => new Promise<void>((r) => setTimeout(r, 0)));

beforeEach(() => {
  vi.useFakeTimers({ now: new Date(NOW), toFake: ['Date'] });
  _resetAlertHistoryCache();
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('Alerts page — the query it sends', () => {
  it('defaults to the three zone kinds ONLY, since 00:00 ET today, at the 500 cap', async () => {
    const fn = stubFetch();
    draw();
    await waitFor(() => expect(recentUrls(fn)).toHaveLength(1));
    const u = lastRecent(fn);
    expect(u.searchParams.get('kinds')).toBe('demand_alert,zone_bounce_alert,supply_break_alert');
    // NEGATIVE: none of the other chips are on by default.
    expect(u.searchParams.get('kinds')).not.toMatch(/position_alert|pivot_alert|promo_alert|todo_reminder/);
    expect(u.searchParams.get('since')).toBe(String(startOfEtDay(0, NOW)));
    expect(u.searchParams.get('since')).toBe(String(T('2026-09-05T04:00:00Z')));
    expect(u.searchParams.get('limit')).toBe('500');
    expect(u.searchParams.get('ticker')).toBeNull();
    const [, init] = fn.mock.calls.find((c) => String(c[0]).includes('/notifications/recent')) as unknown as [string, RequestInit];
    expect(init.credentials).toBe('include');
  });

  it('the day picker changes `since` (5 days → 00:00 ET four days back)', async () => {
    const fn = stubFetch();
    draw();
    await waitFor(() => expect(recentUrls(fn)).toHaveLength(1));
    fireEvent.click(screen.getByRole('button', { name: '5 days' }));
    await waitFor(() => expect(recentUrls(fn)).toHaveLength(2));
    expect(lastRecent(fn).searchParams.get('since')).toBe(String(startOfEtDay(4, NOW)));
    expect(lastRecent(fn).searchParams.get('since')).toBe(String(T('2026-09-01T04:00:00Z')));
    expect(screen.getByRole('button', { name: '5 days' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Today' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('"Yesterday" is yesterday ONLY: since 00:00 ET yesterday, today\'s rows cut, one heading', async () => {
    const fn = stubFetch();
    draw('/alerts?days=2');
    const rows = await screen.findAllByTestId('alert-row');
    expect(lastRecent(fn).searchParams.get('since')).toBe(String(startOfEtDay(1, NOW)));
    expect(rows).toHaveLength(1);
    expect(within(rows[0]).getByRole('link', { name: /NTAP/ })).toBeInTheDocument();
    expect(screen.getByText(/Yesterday · Fri, Sep 4 · 1/)).toBeInTheDocument();
    // NEGATIVE: no today group, and the count is the visible rows, not the fetch.
    expect(screen.queryByText(/Today ·/)).not.toBeInTheDocument();
    expect(screen.getByText(/^1 alert /)).toBeInTheDocument();
    expect(screen.getByText(/Pushed yesterday/)).toBeInTheDocument();
  });

  it('the ticker box filters server-side, upper-cased', async () => {
    const fn = stubFetch();
    draw();
    await waitFor(() => expect(recentUrls(fn)).toHaveLength(1));
    fireEvent.change(screen.getByLabelText('Ticker'), { target: { value: 'nvda' } });
    // The URL (and the query) follow the debounce; the box upper-cases at once.
    expect((screen.getByLabelText('Ticker') as HTMLInputElement).value).toBe('NVDA');
    expect(lastRecent(fn).searchParams.get('ticker')).toBeNull();
    await settle();
    expect(lastRecent(fn).searchParams.get('ticker')).toBe('NVDA');
    await flush();
  });

  it('typing A-V-G-O is ONE query for AVGO, not four (debounced); Enter commits at once', async () => {
    const fn = stubFetch();
    draw();
    await waitFor(() => expect(recentUrls(fn)).toHaveLength(1));
    const box = screen.getByLabelText('Ticker');
    for (const v of ['A', 'AV', 'AVG', 'AVGO']) fireEvent.change(box, { target: { value: v } });
    await settle();
    expect(lastRecent(fn).searchParams.get('ticker')).toBe('AVGO');
    await flush();
    const tickers = recentUrls(fn).map((u) => new URL(u, 'http://x').searchParams.get('ticker'));
    expect(tickers.filter(Boolean)).toEqual(['AVGO']);
    // Enter does not wait for the debounce.
    fireEvent.change(box, { target: { value: 'NTAP' } });
    fireEvent.keyDown(box, { key: 'Enter' });
    expect(new URL(recentUrls(fn).slice(-1)[0], 'http://x').searchParams.get('ticker')).toBe('NTAP');
    await flush();
  });

  it('a deep link ?ticker=NVDA&days=1 (the board chip) lands filtered', async () => {
    const fn = stubFetch();
    draw('/alerts?ticker=NVDA&days=1');
    await waitFor(() => expect(recentUrls(fn)).toHaveLength(1));
    expect(lastRecent(fn).searchParams.get('ticker')).toBe('NVDA');
    expect(lastRecent(fn).searchParams.get('kinds')).toBe('demand_alert,zone_bounce_alert,supply_break_alert');
    expect((screen.getByLabelText('Ticker') as HTMLInputElement).value).toBe('NVDA');
  });

  it('kind chips: adding one widens the list; "all pushes" drops the filter; the last chip cannot be turned off', async () => {
    const fn = stubFetch();
    draw();
    await waitFor(() => expect(recentUrls(fn)).toHaveLength(1));
    fireEvent.click(screen.getByRole('button', { name: '💼 Position alert' }));
    await waitFor(() => expect(lastRecent(fn).searchParams.get('kinds')).toBe('demand_alert,zone_bounce_alert,supply_break_alert,position_alert'));
    fireEvent.click(screen.getByRole('button', { name: '📣 all pushes' }));
    // NEGATIVE: "all" means NO kinds param — the endpoint's untouched default.
    await waitFor(() => expect(lastRecent(fn).searchParams.get('kinds')).toBeNull());
    expect(screen.getByRole('button', { name: '📣 all pushes' })).toHaveAttribute('aria-pressed', 'true');
    // From "all", picking one kind narrows to just it…
    fireEvent.click(screen.getByRole('button', { name: '🪃 Demand-level bounce' }));
    await waitFor(() => expect(lastRecent(fn).searchParams.get('kinds')).toBe('zone_bounce_alert'));
    // …and it cannot be turned off (that would silently mean "all").
    const before = recentUrls(fn).length;
    fireEvent.click(screen.getByRole('button', { name: '🪃 Demand-level bounce' }));
    await new Promise((r) => setTimeout(r, 20));
    expect(recentUrls(fn)).toHaveLength(before);
    expect(screen.getByRole('button', { name: '🪃 Demand-level bounce' })).toHaveAttribute('aria-pressed', 'true');
  });
});

describe('Alerts page — the rows', () => {
  it('renders ET time, kind, a Supply/Demand ticker link with the Alerts back-source, and the FULL body', async () => {
    stubFetch();
    draw();
    const rows = await screen.findAllByTestId('alert-row');
    expect(rows).toHaveLength(3);
    // 14:42Z = 10:42 EDT. Never the UTC clock, never the browser's zone.
    expect(within(rows[0]).getByText('10:42 ET')).toBeInTheDocument();
    expect(within(rows[0]).getByText('🧲 Demand-zone approach')).toBeInTheDocument();
    const link = within(rows[0]).getByRole('link', { name: /NVDA/ });
    expect(link.getAttribute('href')).toMatch(/^\/sepa\/NVDA\?.*tab=supply/);
    expect(link.getAttribute('href')).toMatch(/from=alerts/);
    expect(within(rows[0]).getByText(/Room \+7\.2% to the first supply band at \$192 \(1\.8R\)\. Not advice\./)).toBeInTheDocument();
    expect(within(rows[0]).getByText('delivered to 2/2 devices')).toBeInTheDocument();
    // NEGATIVE: no failed marker on a clean delivery.
    expect(within(rows[0]).queryByText(/failed/)).not.toBeInTheDocument();
    // A partial delivery says so.
    expect(within(rows[1]).getByText('1 failed')).toBeInTheDocument();
    expect(within(rows[1]).getByText('09:31 ET')).toBeInTheDocument();
  });

  it('a send that reached no device is labelled NOT delivered — never "delivered to 0/0"', async () => {
    const muted = { ...ROWS[0], _id: 'm1', sent: 0, failed: 0, total: 0 };                 // muted kind / no sub
    const rejected = { ...ROWS[1], _id: 'm2', sent: 0, failed: 2, total: 2 };              // every device failed
    stubFetch({ rows: [muted, rejected] });
    draw();
    const rows = await screen.findAllByTestId('alert-row');
    expect(within(rows[0]).getByText('not delivered — no device targeted (muted kind or no subscription)')).toBeInTheDocument();
    expect(within(rows[1]).getByText('not delivered — 0/2 devices reached')).toBeInTheDocument();
    expect(within(rows[1]).getByText('2 failed')).toBeInTheDocument();
    expect(screen.queryByText(/delivered to 0\//)).not.toBeInTheDocument();
  });

  it('groups by ET day with Today / Yesterday headings', async () => {
    stubFetch();
    draw('/alerts?days=5');
    await screen.findAllByTestId('alert-row');
    expect(screen.getByText(/Today · Sat, Sep 5 · 2/)).toBeInTheDocument();
    expect(screen.getByText(/Yesterday · Fri, Sep 4 · 1/)).toBeInTheDocument();
  });

  it('shows the failure instead of an empty list when the API is down', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => (
      String(url).includes('/alerts/status')
        ? { ok: true, status: 200, json: async () => STATUS_LIVE } as Response
        : { ok: false, status: 503, json: async () => ({}) } as Response
    )));
    draw();
    expect(await screen.findByText(/could not load alerts — HTTP 503/)).toBeInTheDocument();
    // NEGATIVE: a failed read must never render as "No zone alerts today".
    expect(screen.queryByTestId('alerts-empty')).not.toBeInTheDocument();
  });
});

describe('Alerts page — the honest empty state', () => {
  it('names the kinds and the window, and carries today\'s skip counts', async () => {
    stubFetch({ rows: [] }, STATUS_LIVE);
    draw();
    const empty = await screen.findByTestId('alerts-empty');
    expect(empty).toHaveTextContent('No zone alerts today. — the gate skipped 14 (room) / 3 (proximity) today');
  });

  it('with a ticker and a wider window the sentence says both', async () => {
    stubFetch({ rows: [] }, STATUS_LIVE);
    draw('/alerts?ticker=NVDA&days=30');
    const empty = await screen.findByTestId('alerts-empty');
    expect(empty).toHaveTextContent(/^No zone alerts for NVDA in the last 30 days\./);
  });

  it('NEGATIVE: skips from ANOTHER day are not claimed as today\'s', async () => {
    stubFetch({ rows: [] }, STATUS_CLOSED);          // zone_edge skipped 9 on 2026-09-04
    draw();
    const empty = await screen.findByTestId('alerts-empty');
    expect(empty).toHaveTextContent('No zone alerts today.');
    expect(empty).not.toHaveTextContent(/skipped/);
  });

  it('NEGATIVE: the Yesterday window never carries today\'s skip note', async () => {
    stubFetch({ rows: [ROWS[0]] }, STATUS_LIVE);     // only a today row → yesterday is empty
    draw('/alerts?days=2');
    const empty = await screen.findByTestId('alerts-empty');
    expect(empty).toHaveTextContent('No zone alerts yesterday.');
    expect(empty).not.toHaveTextContent(/skipped/);
  });

  it('spells out the non-zone kinds when the filter is changed', async () => {
    stubFetch({ rows: [] }, STATUS_CLOSED);
    draw('/alerts?kinds=position_alert,todo_reminder');
    const empty = await screen.findByTestId('alerts-empty');
    expect(empty).toHaveTextContent('No position / todo reminder alerts today.');
  });
});

describe('Alerts page — the status strip', () => {
  it('per pass: last pass time in ET, candidates + push calls, the skip chips with the gate numbers, cadence from the API', async () => {
    stubFetch();
    draw();
    const ze = await screen.findByTestId('pass-zone_edge');
    expect(within(ze).getByText('last pass 10:59 ET')).toBeInTheDocument();
    expect(within(ze).getByText('candidates 812')).toBeInTheDocument();
    // `pushed` counts send CALLS (a muted kind still counts) — never "pushed" as if delivered.
    expect(within(ze).getByText('push calls 2')).toBeInTheDocument();
    expect(within(ze).queryByText(/^pushed/)).not.toBeInTheDocument();
    expect(within(ze).getByText('14 skipped: room < 5%')).toBeInTheDocument();
    expect(within(ze).getByText('2 skipped: cap')).toBeInTheDocument();
    expect(within(ze).getByText('1 skipped: cap unknown')).toBeInTheDocument();
    expect(within(ze).getByText('4 stale print')).toBeInTheDocument();
    expect(within(ze).getByText('· every minute')).toBeInTheDocument();
    const zb = screen.getByTestId('pass-zone_bounce_alert');
    expect(within(zb).getByText('3 skipped: > 1% above band')).toBeInTheDocument();
    expect(within(zb).getByText('· every 5 min')).toBeInTheDocument();
    // NEGATIVE: zero counters do not render as chips; no reason chip without a reason.
    expect(within(zb).queryByText(/0 skipped/)).not.toBeInTheDocument();
    expect(screen.queryByTestId('pass-reason')).not.toBeInTheDocument();
    // demand_alert sent no cadence_sec → the crontab fallback.
    expect(within(screen.getByTestId('pass-demand_alert')).getByText('· every 5 min')).toBeInTheDocument();
    // All three fresh → the header may say so.
    expect(screen.getByTestId('session-line')).toHaveTextContent('Session open — all three passes reported within cadence.');
    expect(screen.getByText(/Gate: room ≥ 5% to the first band overhead · print ≤ 1% above the demand band/)).toBeInTheDocument();
  });

  it('a pass with as_of null says "no pass yet today" and the header stops short of "within cadence"', async () => {
    stubFetch({ rows: ROWS }, STATUS_LIVE_MISSING);
    draw();
    const da = await screen.findByTestId('pass-demand_alert');
    expect(within(da).getByText('no pass yet today')).toBeInTheDocument();
    expect(within(da).queryByText(/last pass/)).not.toBeInTheDocument();
    expect(screen.getByTestId('session-line')).toHaveTextContent('Session open (clock) — ⚠ 1 of 3 passes not reporting on cadence');
    expect(screen.queryByText(/reported within cadence/)).not.toBeInTheDocument();
  });

  it('a dead cron mid-session reads STALE, not "passes running" (review 2026-09-05)', async () => {
    stubFetch({ rows: ROWS }, STATUS_STALE);
    draw();
    const ze = await screen.findByTestId('pass-zone_edge');
    expect(within(ze).getByText('stale — last pass 10:02 ET, expected every minute')).toBeInTheDocument();
    expect(screen.getByTestId('session-line')).toHaveTextContent('Session open (clock) — ⚠ 1 of 3 passes not reporting on cadence');
    // NEGATIVE: the fresh 5-minute passes are not called stale, and nothing says "running".
    expect(within(screen.getByTestId('pass-zone_bounce_alert')).getByText('last pass 14:29 ET')).toBeInTheDocument();
    expect(screen.queryByText(/passes running/)).not.toBeInTheDocument();
    expect(screen.queryByText(/reported within cadence/)).not.toBeInTheDocument();
  });

  it('a pass that ran and read nothing shows its reason; an unstamped cold-store doc is "ran today", not "no pass yet"', async () => {
    stubFetch({ rows: [] }, STATUS_REASON);
    draw();
    const ze = await screen.findByTestId('pass-zone_edge');
    expect(within(ze).getByText('ran today — no pass time recorded')).toBeInTheDocument();
    expect(within(ze).getByText('⚠ zone store empty for today')).toBeInTheDocument();
    expect(within(ze).queryByText('no pass yet today')).not.toBeInTheDocument();
    const zb = screen.getByTestId('pass-zone_bounce_alert');
    expect(within(zb).getByText('last pass 09:35 ET')).toBeInTheDocument();
    expect(within(zb).getByText('⚠ zone store empty for today')).toBeInTheDocument();
    expect(within(screen.getByTestId('pass-demand_alert')).getByText('⚠ board empty or warming')).toBeInTheDocument();
    // The unstamped pass cannot be verified against its cadence → the header does not vouch for it.
    expect(screen.getByTestId('session-line')).toHaveTextContent('⚠ 1 of 3 passes');
  });

  it('in_session false: never "live" / "in session" / "session open"; a pass stored on ANOTHER day is named as such', async () => {
    stubFetch({ rows: [] }, STATUS_CLOSED);
    draw();
    expect(await screen.findByText(/Outside the session — nothing runs until the next open/)).toBeInTheDocument();
    expect(screen.queryByText(/In session/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Session open/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\blive\b/i)).not.toBeInTheDocument();
    const ze = screen.getByTestId('pass-zone_edge');
    expect(within(ze).getByText('last pass 2026-09-04 16:00 ET — no pass yet today')).toBeInTheDocument();
    // NEGATIVE: outside the session an old stamp is not "stale" — nothing is expected to run.
    expect(screen.queryByText(/stale —/)).not.toBeInTheDocument();
    // NEGATIVE: yesterday's reason is not shown under today's "no pass yet today".
    const zb = screen.getByTestId('pass-zone_bounce_alert');
    expect(within(zb).getByText('no pass yet today')).toBeInTheDocument();
    expect(screen.queryByTestId('pass-reason')).not.toBeInTheDocument();
  });

  it('status endpoint down: the strip says so and the list still loads', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => (
      String(url).includes('/alerts/status')
        ? { ok: false, status: 503, json: async () => ({}) } as Response
        : { ok: true, status: 200, json: async () => ({ rows: ROWS }) } as Response
    )));
    draw();
    expect(await screen.findByText(/status unavailable — HTTP 503/)).toBeInTheDocument();
    expect(await screen.findAllByTestId('alert-row')).toHaveLength(3);
    // The gate numbers still print from the fallback constants.
    expect(screen.getByText(/Gate: room ≥ 5%/)).toBeInTheDocument();
  });
});

describe('passHealth / cadence helpers', () => {
  const clock = { in_session: true, now_et: '2026-09-05T14:30:00-04:00' };
  const today = '2026-09-05';
  it('stale thresholds: 5 min for the minute pass, 15 min for the 5-minute passes', () => {
    expect(staleAfterSec(60)).toBe(300);
    expect(staleAfterSec(300)).toBe(900);
    expect(cadenceText(60)).toBe('every minute');
    expect(cadenceText(300)).toBe('every 5 min');
    expect(cadenceText(90)).toBe('every 90 s');
  });
  it('judges age on the SERVER clock and only while in session', () => {
    const p = { as_of: '2026-09-05T14:20:00-04:00', date: today, counts: {} };
    expect(passHealth(p, clock, today, 60)).toEqual({ health: 'stale', ageSec: 600 });
    expect(passHealth(p, clock, today, 300)).toEqual({ health: 'fresh', ageSec: 600 });
    expect(passHealth(p, { ...clock, in_session: false }, today, 60).health).toBe('fresh');
    expect(passHealth({ ...p, date: '2026-09-04' }, clock, today, 60).health).toBe('other_day');
    expect(passHealth({ as_of: null, date: today, counts: {}, reason: 'zone store empty for today' }, clock, today, 60).health).toBe('ran_unstamped');
    expect(passHealth({ as_of: null, date: null, counts: {} }, clock, today, 60).health).toBe('none');
    expect(passHealth(undefined, clock, today, 60).health).toBe('none');
  });
});
