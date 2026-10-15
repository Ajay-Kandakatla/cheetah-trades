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
import {
  AlertsPage, KIND_CHIPS, TAPE_PASSES, TICKER_DEBOUNCE_MS, cadenceText, capFloorPhrase, passHealth, sessionLine, skipsToday,
  staleAfterSec, tapeBurstChipText, tapeWindow,
} from './Alerts';
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

/* All six intraday passes fresh at 11:00 ET (🔑 key levels joined 2026-09-25, 🧬 medical catalysts 2026-09-29,
 * 🚩 Gajjala A+ setups 2026-10-13 — its own 5-minute line, SHADOW counters as chart_maps/gajjala/run.py records them). demand_alert carries no cadence_sec on
 * purpose (an older API) — the fallback must fill it. */
const STATUS_LIVE = {
  in_session: true, now_et: '2026-09-05T11:00:00-04:00',
  /* the cap floor is SERVED (backend gate_payload: min_cap_usd + the words) */
  gate: { min_room_pct: 5.0, max_above_demand_pct: 1.0, min_cap_usd: 700_000_000, min_cap_txt: '$700M' },
  passes: {
    zone_edge: { as_of: '2026-09-05T10:59:07-04:00', date: '2026-09-05', cadence_sec: 60,
      counts: { candidates: 812, priced: 800, stale_print: 4, breaking: 3, near_demand: 5, skipped_room: 14, skipped_cap: 2, unknown_cap: 1, pushed: 2 } },
    zone_bounce_alert: { as_of: '2026-09-05T10:55:02-04:00', date: '2026-09-05', cadence_sec: 300,
      counts: { candidates: 640, hits: 6, skipped_room: 0, skipped_proximity: 3, skipped_cap: 0, unknown_cap: 0, pushed: 1 } },
    demand_alert: { as_of: '2026-09-05T10:58:11-04:00', date: '2026-09-05',
      counts: { candidates: 40, hits: 2, skipped_room: 0, skipped_proximity: 0, pushed: 0 } },
    /* 🔑 2026-09-25: rides zone_edge's minute line; counters as the backend's
     * key_level_alerts.run_pass records them. */
    key_level_alert: { as_of: '2026-09-05T10:59:09-04:00', date: '2026-09-05', cadence_sec: 60,
      counts: { scope: 13, priced: 13, stale_print: 0, members: 78, broken: 2, pierced: 1, closed_beyond: 0, pushed: 0 } },
    /* 🧬 2026-09-29: rides promo_live's 5-minute line; counters as
     * catalysts/medical/routine.run_tick records them. */
    med_catalyst: { as_of: '2026-09-05T10:57:30-04:00', date: '2026-09-05', cadence_sec: 300,
      counts: { roster: 362, sliced: 36, articles_new: 3, events_new: 1, high_impact: 1, pushed: 0, stale: 1 } },
    gajjala_setup: { as_of: '2026-09-05T10:56:30-04:00', date: '2026-09-05', cadence_sec: 300,
      counts: { candidates: 7, listed: 7, qualifiers: 4, aplus: 1, pushed: 0, shadow: 1, shadow_mode: 1, shadow_session: 2,
                suppressed_first15: 0, late: 0 } },
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
    key_level_alert: { as_of: '2026-09-05T14:29:40-04:00', date: '2026-09-05', cadence_sec: 60, counts: { scope: 13, pushed: 0 } },
    med_catalyst: { as_of: '2026-09-05T14:28:30-04:00', date: '2026-09-05', cadence_sec: 300, counts: { roster: 362, pushed: 0 } },
    gajjala_setup: { as_of: '2026-09-05T14:26:30-04:00', date: '2026-09-05', cadence_sec: 300, counts: { candidates: 7, pushed: 0 } },
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
    key_level_alert: { as_of: '2026-09-05T09:35:40-04:00', date: '2026-09-05', cadence_sec: 60, counts: { scope: 13, pushed: 0 } },
    med_catalyst: { as_of: '2026-09-05T09:35:30-04:00', date: '2026-09-05', cadence_sec: 300, counts: { roster: 362, pushed: 0 } },
    gajjala_setup: { as_of: '2026-09-05T09:31:30-04:00', date: '2026-09-05', cadence_sec: 300, counts: { candidates: 0, pushed: 0 } },
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
  it('defaults to EVERY push (no kinds param), since 00:00 ET today, at the 500 cap', async () => {
    // Ajay 2026-09-08: the phone and the page must list the same pushes.
    const fn = stubFetch();
    draw();
    await waitFor(() => expect(recentUrls(fn)).toHaveLength(1));
    const u = lastRecent(fn);
    expect(u.searchParams.get('kinds')).toBeNull();
    expect(screen.getByRole('button', { name: '📣 all pushes' })).toHaveAttribute('aria-pressed', 'true');
    // every kind that pages the phone has a chip; in "all" mode each reads as included
    for (const name of ['⚡ Trade flash at a zone', '🤖 Auto-Pilot', '🎪 Promo mover', '💼 Position alert']) {
      expect(screen.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'true');
    }
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
    expect(lastRecent(fn).searchParams.get('kinds')).toBeNull();
    expect((screen.getByLabelText('Ticker') as HTMLInputElement).value).toBe('NVDA');
  });

  it('kind chips: from "all" one chip narrows; a second widens; "all pushes" drops the filter; the last chip cannot be turned off', async () => {
    const fn = stubFetch();
    draw('/alerts?kinds=demand_alert,zone_bounce_alert,supply_break_alert');
    await waitFor(() => expect(recentUrls(fn)).toHaveLength(1));
    fireEvent.click(screen.getByRole('button', { name: '💼 Position alert' }));
    await waitFor(() => expect(lastRecent(fn).searchParams.get('kinds')).toBe('demand_alert,zone_bounce_alert,supply_break_alert,position_alert'));
    fireEvent.click(screen.getByRole('button', { name: '📣 all pushes' }));
    // NEGATIVE: "all" means NO kinds param — the endpoint's untouched default.
    await waitFor(() => expect(lastRecent(fn).searchParams.get('kinds')).toBeNull());
    expect(screen.getByRole('button', { name: '📣 all pushes' })).toHaveAttribute('aria-pressed', 'true');
    // From "all", picking one kind narrows to just it…
    fireEvent.click(screen.getByRole('button', { name: '🪃 Intraday demand turn' }));
    await waitFor(() => expect(lastRecent(fn).searchParams.get('kinds')).toBe('zone_bounce_alert'));
    // …and it cannot be turned off (that would silently mean "all").
    const before = recentUrls(fn).length;
    fireEvent.click(screen.getByRole('button', { name: '🪃 Intraday demand turn' }));
    await new Promise((r) => setTimeout(r, 20));
    expect(recentUrls(fn)).toHaveLength(before);
    expect(screen.getByRole('button', { name: '🪃 Intraday demand turn' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('REGRESSION: completing the three zone kinds does NOT flip the page to "all pushes"', async () => {
    // Ajay 2026-09-10: "These selections are not working proper sometime it
    // selects all if I click on Breaking resistance".
    //
    // writeKinds used to delete the kinds param when the selection equalled
    // ZONE_KINDS -- correct back when an ABSENT param meant those three. It
    // does not any more (parseKinds(null) === 'all'), so the deletion read
    // back as ALL PUSHES. Breaking Resistance is the third zone kind, so it
    // was the click that completed the set and tripped it.
    const fn = stubFetch();
    draw('/alerts?kinds=demand_alert,zone_bounce_alert');
    await waitFor(() => expect(recentUrls(fn)).toHaveLength(1));
    fireEvent.click(screen.getByRole('button', { name: '🚀 Breaking resistance' }));
    await waitFor(() => expect(lastRecent(fn).searchParams.get('kinds'))
      .toBe('demand_alert,zone_bounce_alert,supply_break_alert'));
    // the param is WRITTEN OUT, never dropped …
    expect(lastRecent(fn).searchParams.get('kinds')).not.toBeNull();
    // … and the all-pushes chip stays off, with all three narrow chips on.
    expect(screen.getByRole('button', { name: '📣 all pushes' })).toHaveAttribute('aria-pressed', 'false');
    for (const name of ['🧲 Reversal at demand', '🪃 Intraday demand turn', '🚀 Breaking resistance']) {
      expect(screen.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'true');
    }
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
    expect(within(rows[0]).getByText('🧲 Reversal at demand')).toBeInTheDocument();
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
    draw('/alerts?kinds=demand_alert,zone_bounce_alert,supply_break_alert');
    const empty = await screen.findByTestId('alerts-empty');
    expect(empty).toHaveTextContent('No zone alerts today. — the gate skipped 14 (room) / 3 (proximity) today');
    // only the reasons that fired are named — a quiet day must not read
    // "0 (falling knife) / 0 (turn not bullish)" (2026-09-09)
    expect(empty.textContent).not.toMatch(/0 \(/);
  });

  it('in the default "all" mode the empty sentence names no kind (2026-09-08)', async () => {
    stubFetch({ rows: [] });
    draw();
    const empty = await screen.findByTestId('alerts-empty');
    expect(empty).toHaveTextContent(/^No alerts today\./);
  });

  it('with a ticker and a wider window the sentence says both', async () => {
    stubFetch({ rows: [] }, STATUS_LIVE);
    draw('/alerts?kinds=demand_alert,zone_bounce_alert,supply_break_alert&ticker=NVDA&days=30');
    const empty = await screen.findByTestId('alerts-empty');
    expect(empty).toHaveTextContent(/^No zone alerts for NVDA in the last 30 days\./);
  });

  it('NEGATIVE: skips from ANOTHER day are not claimed as today\'s', async () => {
    stubFetch({ rows: [] }, STATUS_CLOSED);          // zone_edge skipped 9 on 2026-09-04
    draw('/alerts?kinds=demand_alert,zone_bounce_alert,supply_break_alert');
    const empty = await screen.findByTestId('alerts-empty');
    expect(empty).toHaveTextContent('No zone alerts today.');
    expect(empty).not.toHaveTextContent(/skipped/);
  });

  it('NEGATIVE: the Yesterday window never carries today\'s skip note', async () => {
    stubFetch({ rows: [ROWS[0]] }, STATUS_LIVE);     // only a today row → yesterday is empty
    draw('/alerts?kinds=demand_alert,zone_bounce_alert,supply_break_alert&days=2');
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
    // All six fresh → the header may say so.
    expect(screen.getByTestId('session-line')).toHaveTextContent('Session open — all 6 passes reported within cadence.' /* 5 → 6: 🚩 gajjala_setup joined 2026-10-13 */);
    expect(screen.getByText(/Gate: room ≥ 5% to the first band overhead · print ≤ 1% above the demand band/)).toBeInTheDocument();
    // The cap floor comes from the payload (review 2026-09-14 F5): "$700M+", never a figure typed in the page.
    expect(screen.getByText(/the phone gets \$700M\+ names that pass, once per band per day/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\$1B/);
  });

  it('F5: the cap floor follows the payload — a changed floor changes the words, an older API types no figure', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, gate: { ...STATUS_LIVE.gate, min_cap_usd: 1.5e9, min_cap_txt: '$1.5B' } });
    draw();
    expect(await screen.findByText(/the phone gets \$1\.5B\+ names that pass/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\$700M/);
  });

  it('F5 NEGATIVE: with no min_cap_txt served (older API) the page says "cap-floored" and never invents a figure', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, gate: { min_room_pct: 5.0, max_above_demand_pct: 1.0 } });
    draw();
    expect(await screen.findByText(/the phone gets cap-floored names that pass/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\$\d+(\.\d+)?[MB]\+/);
  });

  it('a pass with as_of null says "no pass yet today" and the header stops short of "within cadence"', async () => {
    stubFetch({ rows: ROWS }, STATUS_LIVE_MISSING);
    draw();
    const da = await screen.findByTestId('pass-demand_alert');
    expect(within(da).getByText('no pass yet today')).toBeInTheDocument();
    expect(within(da).queryByText(/last pass/)).not.toBeInTheDocument();
    expect(screen.getByTestId('session-line')).toHaveTextContent('Session open (clock) — ⚠ 1 of 6 passes not reporting on cadence');  // 5 → 6: 🚩 gajjala_setup joined 2026-10-13
    expect(screen.queryByText(/reported within cadence/)).not.toBeInTheDocument();
  });

  it('a dead cron mid-session reads STALE, not "passes running" (review 2026-09-05)', async () => {
    stubFetch({ rows: ROWS }, STATUS_STALE);
    draw();
    const ze = await screen.findByTestId('pass-zone_edge');
    expect(within(ze).getByText('stale — last pass 10:02 ET, expected every minute')).toBeInTheDocument();
    expect(screen.getByTestId('session-line')).toHaveTextContent('Session open (clock) — ⚠ 1 of 6 passes not reporting on cadence');  // 5 → 6: 🚩 gajjala_setup joined 2026-10-13
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
    expect(screen.getByTestId('session-line')).toHaveTextContent('⚠ 1 of 6 passes');  // 5 → 6: 🚩 gajjala_setup joined 2026-10-13
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
    // NEGATIVE (F5): the fallback carries NO cap figure — nothing typed in the FE can go stale.
    expect(screen.getByText(/the phone gets cap-floored names that pass/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\$1B|\$700M/);
  });
});

describe('capFloorPhrase (F5 — the served words, never a typed figure)', () => {
  it('is the served text plus "+", else "cap-floored"', () => {
    expect(capFloorPhrase({ min_cap_txt: '$700M' })).toBe('$700M+');
    expect(capFloorPhrase({ min_cap_txt: ' $1.5B ' })).toBe('$1.5B+');
    expect(capFloorPhrase({ min_cap_txt: '' })).toBe('cap-floored');
    expect(capFloorPhrase({ min_cap_txt: null })).toBe('cap-floored');
    expect(capFloorPhrase({ min_room_pct: 5, max_above_demand_pct: 1 })).toBe('cap-floored');
    expect(capFloorPhrase(null)).toBe('cap-floored');
    expect(capFloorPhrase(undefined)).toBe('cap-floored');
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


/* 🎯 ENTERABLE on the Alerts page (2026-09-15).
 *
 * The honest read for a PUSHED row is the verdict at PUSH TIME, on the band
 * that alert actually named — so it is persisted with the row and rendered
 * verbatim, never recomputed here from a later print. Rows written before that
 * date carry none and must wear no chip.
 *
 * `skipped_not_enterable` is a DIVERGENCE GUARD, not a gate: every demand push
 * has already passed the same room, proximity and floor reads the verdict is
 * built from, so a non-zero count means the two engines disagree. The label
 * says exactly that, because an unexplained counter is how a quiet phone gets
 * blamed on the wrong thing.
 */
describe('Alerts page — the 🎯 push-time verdict', () => {
  const READ = {
    kind: 'demand', verdict: 'WATCH', reasons: ['weak_day'], reason_short: ['down day'],
    reason_text: ['Down 4.4% today — a −3..−8% day finished up 22% of the time (n=286, 2026-09-08).'],
    print: { px: 176.5, source: 'live' }, measured: { status: 'pending' },
  };

  it('renders the SERVED verdict on the row that carries one', async () => {
    stubFetch({ rows: [{ ...ROWS[0], enterable: READ }] });
    draw();
    const chip = await screen.findByText('🎯 WATCH · down day');
    expect(chip).toHaveClass('cm-badge-enterable-watch');
    expect(chip.getAttribute('title')).toMatch(/a −3\.\.−8% day finished up 22% of the time/);
    expect(chip.closest('[data-testid="alert-row"]')).not.toBeNull();
  });

  it('NEGATIVE: a legacy row with no verdict wears no chip at all', async () => {
    stubFetch({ rows: ROWS });                 // none of the three carries `enterable`
    draw();
    await screen.findByText(/NVDA in demand/);
    expect(screen.queryByText(/🎯 (READY|WATCH)/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^⛔/)).not.toBeInTheDocument();
  });

  it('labels skipped_not_enterable with its count AND says a non-zero count is a bug', async () => {
    stubFetch({ rows: ROWS }, {
      ...STATUS_LIVE,
      passes: {
        ...STATUS_LIVE.passes,
        demand_alert: { as_of: '2026-09-05T10:58:11-04:00', date: '2026-09-05',
          counts: { candidates: 40, hits: 2, skipped_not_enterable: 1, pushed: 0 } },
      },
    });
    draw();
    const chip = await screen.findByText(/skipped: not enterable/);
    expect(chip.textContent).toMatch(/^1 skipped: not enterable/);
    expect(chip.textContent).toMatch(/should be 0; a non-zero count is a bug to report/);
  });

  it('NEGATIVE: a zero count is not printed — the guard is silent when it agrees', async () => {
    stubFetch({ rows: ROWS }, {
      ...STATUS_LIVE,
      passes: {
        ...STATUS_LIVE.passes,
        demand_alert: { as_of: '2026-09-05T10:58:11-04:00', date: '2026-09-05',
          counts: { candidates: 40, hits: 2, skipped_not_enterable: 0, pushed: 0 } },
      },
    });
    draw();
    await screen.findByText(/NVDA in demand/);
    expect(screen.queryByText(/skipped: not enterable/)).not.toBeInTheDocument();
  });
});

/* ── 2026-09-20: digest rows link EVERY name; the three once-a-day passes ──
 *
 * Ajay: a digest push ("AAA, BBB, CCC") linked at most one of its names, so
 * reading it meant typing symbols into the ticker box. And three new passes
 * (📣 earnings reaction, ✨ Bonde / 🚀 growth arrivals) run once a trading day
 * — they have no cadence, so they get their own strip rather than being
 * judged "stale" against a minute clock they never had.
 */

const DIGEST_ROW = {
  _id: 'g1', ts: T('2026-09-05T13:05:00Z'), ts_iso: '2026-09-05T13:05:00+00:00',
  kind: 'growth_demand_alert', ticker: null, tickers: ['AAA', 'BBB', 'CCC'],
  title: '🚀 3 growth names at demand', url: '/chart-maps?tab=growth', source: 'push',
  sent: 1, failed: 0, total: 1, body: 'AAA, BBB, CCC · pushed 09:05 ET',
};
/* A pre-2026-09-20 row: no `tickers` key AND no ticker. */
const NO_TICKER_ROW = {
  _id: 'o1', ts: T('2026-09-05T12:05:00Z'), ts_iso: '2026-09-05T12:05:00+00:00',
  kind: 'todo_reminder', ticker: null, title: '📝 Desk todo', url: null, source: 'push',
  sent: 1, failed: 0, total: 1, body: 'Nothing to link here.',
};

/* The three daily passes as the backend serves them: cadence_sec null, a
 * `schedule` in words, and counters no zone pass has. */
const STATUS_DAILY = {
  ...STATUS_LIVE,
  passes: {
    ...STATUS_LIVE.passes,
    earnings_reaction: {
      as_of: '2026-09-05T08:25:40-04:00', date: '2026-09-05', cadence_sec: null,
      schedule: '08:25 + 17:35 ET, trading days',
      counts: { candidates: 31, pushed: 2, skipped_timing_unknown: 4, fetch_failed: 1, dropped_not_last_bar: 3 },
    },
    'board_arrival:bonde': {
      as_of: '2026-09-05T17:42:03-04:00', date: '2026-09-05', cadence_sec: null,
      schedule: '17:42 ET, trading days',
      counts: { candidates: 12, pushed: 1, fresh: 2, claimed_elsewhere: 1 },
    },
    'board_arrival:growth': {
      as_of: '2026-09-05T08:08:02-04:00', date: '2026-09-05', cadence_sec: null,
      schedule: '08:08 ET, trading days', reason: 'board empty or warming',
      counts: { candidates: 0, pushed: 0, first_pass: true, since_tracking: 0 },
    },
  },
};

describe('Alerts page — every name in a digest is its own link', () => {
  it('a 3-name digest renders 3 Supply/Demand anchors, each with from=alerts', async () => {
    stubFetch({ rows: [DIGEST_ROW] });
    const { container } = draw();
    const rows = await screen.findAllByTestId('alert-row');
    const links = within(rows[0]).getAllByRole('link', { name: /^(AAA|BBB|CCC)$/ });
    expect(links).toHaveLength(3);
    for (const a of links) {
      expect(a.getAttribute('href')).toMatch(/^\/sepa\/(AAA|BBB|CCC)\?/);
      expect(a.getAttribute('href')).toMatch(/tab=supply/);
      expect(a.getAttribute('href')).toMatch(/from=alerts/);
    }
    // NEGATIVE: an anchor inside an anchor is invalid HTML — the browser
    // un-nests it and ⌘-click lands on the wrong URL.
    expect(container.querySelectorAll('a a')).toHaveLength(0);
  });

  it('the single-ticker pin is unchanged — NVDA still links to Supply/Demand from alerts', async () => {
    stubFetch();
    draw();
    const rows = await screen.findAllByTestId('alert-row');
    const link = within(rows[0]).getByRole('link', { name: /NVDA/ });
    expect(link.getAttribute('href')).toMatch(/^\/sepa\/NVDA\?.*tab=supply/);
    expect(link.getAttribute('href')).toMatch(/from=alerts/);
  });

  it('NEGATIVE: an old row with neither tickers nor ticker renders its body and no ticker anchor', async () => {
    stubFetch({ rows: [NO_TICKER_ROW] });
    draw();
    const rows = await screen.findAllByTestId('alert-row');
    expect(within(rows[0]).getByText('Nothing to link here.')).toBeInTheDocument();
    expect(within(rows[0]).queryAllByRole('link')).toHaveLength(0);
  });
});

describe('Alerts page — the once-a-day passes', () => {
  it('renders schedule, ET stamp and counter chips for all three', async () => {
    stubFetch({ rows: ROWS }, STATUS_DAILY);
    draw();
    await screen.findByText(/NVDA in demand/);
    expect(screen.getByText('🗓️ Daily passes')).toBeInTheDocument();

    const er = screen.getByTestId('pass-earnings_reaction');
    expect(within(er).getByText('📣 Earnings beat, institutions bought')).toBeInTheDocument();
    expect(within(er).getByText('· 08:25 + 17:35 ET, trading days')).toBeInTheDocument();
    expect(within(er).getByText('last pass 08:25 ET')).toBeInTheDocument();
    expect(within(er).getByText('4 skipped: report timing unknown')).toBeInTheDocument();
    expect(within(er).getByText('1 surprise fetches failed')).toBeInTheDocument();
    expect(within(er).getByText('3 reacted on an older bar')).toBeInTheDocument();

    const bo = screen.getByTestId('pass-board_arrival:bonde');
    expect(within(bo).getByText('✨ New on 📈 Bonde')).toBeInTheDocument();
    expect(within(bo).getByText('· 17:42 ET, trading days')).toBeInTheDocument();
    expect(within(bo).getByText('2 new this pass')).toBeInTheDocument();
    expect(within(bo).getByText('1 claimed by another pass')).toBeInTheDocument();
    // NEGATIVE: `fresh` is the PRE-send count, so on a wet pass those names
    // were the ones rung. The chip must never call them un-pushed.
    expect(within(bo).queryByText(/not yet pushed/)).not.toBeInTheDocument();

    const gr = screen.getByTestId('pass-board_arrival:growth');
    expect(within(gr).getByText('✨ New on 🚀 Explosive Growth')).toBeInTheDocument();
    expect(within(gr).getByText('first pass — baseline recorded, nothing pushed')).toBeInTheDocument();
    expect(within(gr).getByText('⚠ board empty or warming')).toBeInTheDocument();
    // NEGATIVE: a zero counter never gets a chip.
    expect(within(gr).queryByText(/arrived since tracking began/)).not.toBeInTheDocument();
  });

  it('a wet pass that rang every fresh name still reads right — "3 new this pass", never "not yet pushed"', async () => {
    const wet = {
      ...STATUS_DAILY,
      passes: {
        ...STATUS_DAILY.passes,
        'board_arrival:bonde': {
          ...STATUS_DAILY.passes['board_arrival:bonde'],
          // fresh is counted before the sends; all three were then pushed.
          counts: { candidates: 12, pushed: 3, fresh: 3, individual: 2, digest: 1 },
        },
      },
    };
    stubFetch({ rows: ROWS }, wet);
    draw();
    await screen.findByText(/NVDA in demand/);
    const bo = screen.getByTestId('pass-board_arrival:bonde');
    expect(within(bo).getByText('3 new this pass')).toBeInTheDocument();
    expect(within(bo).queryByText(/not yet pushed/)).not.toBeInTheDocument();
    // NEGATIVE: the wording change touches no other counter's chip.
    expect(within(bo).queryByText(/claimed by another pass/)).not.toBeInTheDocument();
  });

  /* FOUR daily passes since 2026-09-22 — 💎 capital_quality_upgrade joined the
     strip. It is here although its KIND ships OFF, because "why was my phone
     quiet" is exactly the question the day he switches it on. */
  it('NEGATIVE: a status without the new keys says "no pass recorded" once per daily pass, and :380 is unchanged', async () => {
    stubFetch({ rows: ROWS }, STATUS_LIVE);
    draw();
    await screen.findByText(/NVDA in demand/);
    const DAILY = ['earnings_reaction', 'board_arrival:bonde', 'board_arrival:growth',
                   'capital_quality_upgrade'];
    for (const k of DAILY) {
      const strip = screen.getByTestId(`pass-${k}`);
      expect(within(strip).getByText('no pass recorded')).toBeInTheDocument();
      // No schedule served → the words, never an invented slot.
      expect(within(strip).getByText('· once a trading day')).toBeInTheDocument();
    }
    expect(screen.getAllByText('no pass recorded')).toHaveLength(DAILY.length);
    // The intraday-pass sentence speaks for the INTRADAY passes only.
    expect(screen.getByTestId('session-line'))
      .toHaveTextContent('Session open — all 6 passes reported within cadence.' /* 5 → 6: 🚩 gajjala_setup joined 2026-10-13 */);
  });

  it('NEGATIVE: would_skip_room is never folded into the room aggregate', async () => {
    const status = {
      ...STATUS_LIVE,
      passes: {
        ...STATUS_LIVE.passes,
        earnings_reaction: { as_of: '2026-09-05T08:25:40-04:00', date: '2026-09-05', cadence_sec: null,
          schedule: '08:25 + 17:35 ET, trading days', counts: { candidates: 5, would_skip_room: 3, pushed: 1 } },
      },
    };
    stubFetch({ rows: [] }, status);
    draw();
    const empty = await screen.findByTestId('alerts-empty');
    // zone_edge's 14 is the whole room aggregate; the earnings pass's
    // would-have-skipped count is a study counter, not a gate.
    expect(skipsToday(status as never, '2026-09-05').room).toBe(14);
    expect(empty).toHaveTextContent('the gate skipped 14 (room) / 3 (proximity) today');
    expect(empty.textContent).not.toMatch(/17 \(room\)/);
  });

  it('[C11] NEGATIVE: the three new passes leave skipsToday byte-identical', () => {
    const today = '2026-09-05';
    const base = STATUS_LIVE as never;
    const withNew = {
      ...STATUS_LIVE,
      passes: {
        ...STATUS_LIVE.passes,
        earnings_reaction: { as_of: '2026-09-05T08:25:40-04:00', date: today, cadence_sec: null,
          counts: { would_skip_room: 3, fresh: 2, fetch_failed: 1, since_tracking: 4 } },
        'board_arrival:bonde': { as_of: '2026-09-05T17:42:03-04:00', date: today, cadence_sec: null,
          counts: { would_skip_room: 3, fresh: 2, fetch_failed: 1, since_tracking: 4 } },
        'board_arrival:growth': { as_of: '2026-09-05T08:08:02-04:00', date: today, cadence_sec: null,
          counts: { would_skip_room: 3, fresh: 2, fetch_failed: 1, since_tracking: 4 } },
      },
    } as never;
    expect(JSON.stringify(skipsToday(withNew, today)))
      .toBe(JSON.stringify(skipsToday(base, today)));
    // and every one of the six is unchanged by name, not just in aggregate.
    const a = skipsToday(base, today);
    const b = skipsToday(withNew, today);
    for (const k of ['room', 'proximity', 'direction', 'knife', 'mood', 'floor'] as const) {
      expect(b[k]).toBe(a[k]);
    }
  });
});

/* ── 2026-09-21: the feed folds repeated rows ──────────────────────────────
 *
 * push/recent collapses a run of adjacent rows with the same
 * source+kind+ticker+title(+tickers) into the newest one and hands the page a
 * `repeat` block whose `line` is the whole sentence. The page's job is small
 * and pinned here with its negatives: PRINT the line, never compose one; count
 * the pair over what is ON SCREEN; and show the truncation warning on the
 * SERVER's `raw_truncated`, because a folded answer serves fewer rows than it
 * read and `rows.length >= 500` went quiet exactly when the page was least
 * complete.
 */
const LINE = 'served: two more of these';
const REPEAT = {
  count: 3,
  first_ts: T('2026-09-05T11:07:00Z'),          // 07:07 ET — a stamp the page must NOT print
  first_ts_iso: '2026-09-05T11:07:00+00:00',
  last_ts: T('2026-09-05T14:42:00Z'),
  truncated: false,
  line: LINE,
};
const manyRows = (n: number, extra: Record<string, unknown> = {}) =>
  Array.from({ length: n }, (_, i) => ({
    ...ROWS[0], _id: `m${i}`, ts: T('2026-09-05T14:42:00Z') - i * 60, ...extra,
  }));

describe('Alerts page — the fold line is printed, never composed', () => {
  it('prints row.repeat.line VERBATIM inside the row, beside the delivery line and the link', async () => {
    stubFetch({ rows: [{ ...ROWS[0], repeat: REPEAT }, ROWS[1], ROWS[2]] });
    draw('/alerts?days=5');
    const rows = await screen.findAllByTestId('alert-row');
    const line = within(rows[0]).getByTestId('alert-repeat');
    expect(line.textContent).toBe(LINE);
    expect(within(rows[0]).getByText(LINE)).toBe(line);
    // the meta line is one flex row — the delivery read and the link stay put
    expect(within(rows[0]).getByText('delivered to 2/2 devices')).toBeInTheDocument();
    expect(within(rows[0]).getByRole('link', { name: "open the push's page →" })).toBeInTheDocument();
  });

  it('NEGATIVE: a row with no block, and one with repeat: null, render no fold line', async () => {
    stubFetch({ rows: [ROWS[0], { ...ROWS[1], repeat: null }] });
    draw();
    const rows = await screen.findAllByTestId('alert-row');
    expect(rows).toHaveLength(2);
    expect(screen.queryAllByTestId('alert-repeat')).toHaveLength(0);
  });

  it('NEGATIVE: the page composes NOTHING from count or the stamps', async () => {
    stubFetch({ rows: [{ ...ROWS[0], repeat: REPEAT }] });
    draw();
    await screen.findAllByTestId('alert-row');
    const page = document.body.textContent ?? '';
    // not the server's own wording, re-derived
    expect(page).not.toMatch(/more like this/);
    expect(page).not.toMatch(/2 more/);
    expect(page).not.toMatch(/3 more/);
    // not an ET stamp derived from first_ts / last_ts (07:07 ET, 10:42 ET)
    expect(page).not.toMatch(/07:07/);
    expect(page).not.toMatch(/first 07:07/);
    expect(page).not.toMatch(/last 10:42/);
    expect(page).not.toMatch(/ ET, last /);
    // exactly one fold line, and it is the served string
    expect(screen.getAllByTestId('alert-repeat')).toHaveLength(1);
    expect(screen.getByTestId('alert-repeat').textContent).toBe(LINE);
  });

  it('NEGATIVE: no browser clock — 24h later the line is byte-identical', async () => {
    stubFetch({ rows: [{ ...ROWS[0], repeat: REPEAT }] });
    const { rerender } = draw();
    await screen.findAllByTestId('alert-row');
    const before = screen.getByTestId('alert-repeat').textContent;
    _resetAlertHistoryCache();
    act(() => { vi.setSystemTime(new Date(NOW + 86_400_000)); });
    rerender(<MemoryRouter initialEntries={['/alerts']}><AlertsPage /></MemoryRouter>);
    await screen.findAllByTestId('alert-row');
    expect(screen.getByTestId('alert-repeat').textContent).toBe(before);
    expect(screen.getByTestId('alert-repeat').textContent).toBe(LINE);
  });
});

describe('Alerts page — the header counts rows AND alerts', () => {
  it('prints the honest pair when something folded', async () => {
    stubFetch({ rows: [
      { ...ROWS[0], repeat: { ...REPEAT, count: 3 } },
      ROWS[1],
      { ...ROWS[2], repeat: { ...REPEAT, count: 2 } },
    ] });
    draw('/alerts?days=5');
    await screen.findAllByTestId('alert-row');
    // 3 on screen; 2 + 0 + 1 folded away under them
    expect(screen.getByText(/^3 rows · 6 alerts ·/)).toBeInTheDocument();
  });

  it('NEGATIVE: nothing folded → the old "N alerts" string, byte-identical', async () => {
    stubFetch();
    draw('/alerts?days=5');
    await screen.findAllByTestId('alert-row');
    expect(screen.getByText(/^3 alerts · times in ET/)).toBeInTheDocument();
    expect(screen.queryByText(/rows ·/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: the Yesterday view counts only what is visible — a filtered-out fold never inflates it', async () => {
    stubFetch({ rows: [
      { ...ROWS[0], repeat: { ...REPEAT, count: 4 } },   // today — cut client-side
      ROWS[1],                                            // today — cut client-side
      { ...ROWS[2], repeat: { ...REPEAT, count: 2 } },    // yesterday — the only row
    ] });
    draw('/alerts?days=2');
    const rows = await screen.findAllByTestId('alert-row');
    expect(rows).toHaveLength(1);
    expect(screen.getByText(/^1 rows · 2 alerts ·/)).toBeInTheDocument();
    expect(screen.queryByText(/ 5 alerts/)).not.toBeInTheDocument();
    expect(screen.queryByText(/ 6 alerts/)).not.toBeInTheDocument();
  });
});

describe('Alerts page — the truncation warning keys on the SERVER cut', () => {
  it('raw_truncated: true warns although only 10 rows were served', async () => {
    stubFetch({ rows: manyRows(10), raw_truncated: true });
    draw();
    await screen.findAllByTestId('alert-row');
    expect(screen.getByText(/newest 500 only — narrow the window/)).toBeInTheDocument();
  });

  it('NEGATIVE: raw_truncated: false on a short answer warns about nothing', async () => {
    stubFetch({ rows: manyRows(10), raw_truncated: false });
    draw();
    await screen.findAllByTestId('alert-row');
    expect(screen.queryByText(/newest 500 only/)).not.toBeInTheDocument();
  });

  it('a full page with NO raw_truncated key still warns (the old predicate holds)', async () => {
    stubFetch({ rows: manyRows(500) });
    draw();
    await screen.findAllByTestId('alert-row');
    expect(screen.getByText(/newest 500 only — narrow the window/)).toBeInTheDocument();
  });
});

/* ── 2026-09-25: the 🔑 key-levels pass ─────────────────────────────────────
 *
 * Ajay: "I wanna know when key levels are broken for a stock." The push kind
 * key_level_alert rides zone_edge's every-minute crontab line and records its
 * own pass doc, so /alerts carries it as a 4th intraday row. The header used
 * to type "all three"; it now counts PASSES (critic 2 #8).
 */
const KEY_PASS_FRESH = {
  as_of: '2026-09-05T10:59:09-04:00', date: '2026-09-05', cadence_sec: 60,
  reason: 'close verdicts push 16:05–16:30 ET',
  counts: { scope: 13, priced: 13, stale_print: 2, no_frame: 0, stale_frame: 1, unverified: 0,
    members: 78, broken: 2, pierced: 1, reversal: 1, closed_beyond: 0, rearmed: 0,
    pushed: 0, muted: 0, claimed_elsewhere: 0 },
};

describe('Alerts page — the 🔑 key-levels pass (2026-09-25)', () => {
  it('renders the 4th pass row with its label, stamp, minute cadence and its reason', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes, key_level_alert: KEY_PASS_FRESH } });
    draw();
    const kl = await screen.findByTestId('pass-key_level_alert');
    expect(within(kl).getByText('🔑 Key levels')).toBeInTheDocument();
    expect(within(kl).getByText('last pass 10:59 ET')).toBeInTheDocument();
    expect(within(kl).getByText('· every minute')).toBeInTheDocument();
    expect(within(kl).getByText('⚠ close verdicts push 16:05–16:30 ET')).toBeInTheDocument();
    expect(within(kl).getByText('push calls 0')).toBeInTheDocument();
    expect(within(kl).getByText('2 stale print')).toBeInTheDocument();
    // NEGATIVE: the raw kind id is never the row's label.
    expect(within(kl).queryByText('key_level_alert')).not.toBeInTheDocument();
    // Order: the 🔑 row comes after the three zone passes.
    const ids = screen.getAllByTestId(/^pass-/).map((el) => el.getAttribute('data-testid'));
    expect(ids.slice(0, 4)).toEqual(['pass-zone_edge', 'pass-zone_bounce_alert', 'pass-demand_alert', 'pass-key_level_alert']);
    // 🧬 2026-09-29: the medical-catalysts row follows the 🔑 row (the 🔑 reason chip is also a pass-* id).
    const strips = ids.filter((x) => x !== 'pass-reason');
    expect(strips.indexOf('pass-med_catalyst')).toBe(strips.indexOf('pass-key_level_alert') + 1);
    expect(screen.getByTestId('session-line')).toHaveTextContent('Session open — all 6 passes reported within cadence.' /* 5 → 6: 🚩 gajjala_setup joined 2026-10-13 */);
  });

  it('the header scopes the room/proximity gate to the three zone passes; 🔑 is said not to go through it', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes, key_level_alert: KEY_PASS_FRESH } });
    draw();
    await screen.findByTestId('pass-key_level_alert');
    expect(screen.getByText('⚙️ Every-minute passes · the phone gate covers the three zone passes')).toBeInTheDocument();
    expect(screen.getByText(/🔑 Key levels do not go through this gate: they push on a close through a level\./)).toBeInTheDocument();
    // NEGATIVE: the old header that put all four rows under the zone gate is gone.
    expect(screen.queryByText('⚙️ Phone gate · the three zone passes')).not.toBeInTheDocument();
  });

  it('an older API that sends no cadence_sec for it still reads "every minute" (the zone_edge line it rides)', async () => {
    const { cadence_sec: _drop, ...noCadence } = KEY_PASS_FRESH;
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes, key_level_alert: noCadence } });
    draw();
    const kl = await screen.findByTestId('pass-key_level_alert');
    expect(within(kl).getByText('· every minute')).toBeInTheDocument();
  });

  it('NEGATIVE: a status without the 🔑 pass doc renders "no pass yet today", never crashes, and the header does not vouch for it', async () => {
    const { key_level_alert: _gone, ...three } = STATUS_LIVE.passes;
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: three });
    draw();
    const kl = await screen.findByTestId('pass-key_level_alert');
    expect(within(kl).getByText('no pass yet today')).toBeInTheDocument();
    expect(within(kl).queryByText(/last pass/)).not.toBeInTheDocument();
    expect(screen.getByTestId('session-line')).toHaveTextContent('Session open (clock) — ⚠ 1 of 6 passes not reporting on cadence');  // 5 → 6: 🚩 gajjala_setup joined 2026-10-13
    expect(screen.queryByText(/reported within cadence/)).not.toBeInTheDocument();
    // The rest of the page still loads.
    expect(await screen.findAllByTestId('alert-row')).toHaveLength(3);
  });

  it('NEGATIVE: a 🔑 pass silent for 10 minutes mid-session reads STALE on the minute clock', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes,
      key_level_alert: { ...KEY_PASS_FRESH, as_of: '2026-09-05T10:50:00-04:00', reason: null } } });
    draw();
    const kl = await screen.findByTestId('pass-key_level_alert');
    expect(within(kl).getByText('stale — last pass 10:50 ET, expected every minute')).toBeInTheDocument();
    expect(screen.getByTestId('session-line')).toHaveTextContent('⚠ 1 of 6 passes');  // 5 → 6: 🚩 gajjala_setup joined 2026-10-13
  });

  it('NEGATIVE: yesterday\'s 🔑 reason is not shown under today\'s "no pass yet today"', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes,
      key_level_alert: { ...KEY_PASS_FRESH, as_of: '2026-09-04T19:59:09-04:00', date: '2026-09-04' } } });
    draw();
    const kl = await screen.findByTestId('pass-key_level_alert');
    expect(within(kl).getByText('last pass 2026-09-04 19:59 ET — no pass yet today')).toBeInTheDocument();
    expect(within(kl).queryByTestId('pass-reason')).not.toBeInTheDocument();
  });

  it('sessionLine counts the passes and NEGATIVE: never types "three"', () => {
    const today = '2026-09-05';
    const all = { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes, key_level_alert: KEY_PASS_FRESH } } as never;
    expect(sessionLine(all, today)).toBe('Session open — all 6 passes reported within cadence.' /* 5 → 6: 🚩 gajjala_setup joined 2026-10-13 */);
    const { key_level_alert: _gone, ...three } = STATUS_LIVE.passes;
    const missing = { ...STATUS_LIVE, passes: three } as never;
    expect(sessionLine(missing, today)).toMatch(/⚠ 1 of 6 passes/);  // 5 → 6: 🚩 gajjala_setup joined 2026-10-13
    const closed = { ...STATUS_LIVE, in_session: false } as never;
    for (const line of [sessionLine(all, today), sessionLine(missing, today), sessionLine(closed, today)]) {
      expect(line).not.toMatch(/three/i);
    }
  });

  it('NEGATIVE: the 🔑 counters never leak into the gate\'s skip aggregate', () => {
    const today = '2026-09-05';
    const { key_level_alert: _gone, ...three } = STATUS_LIVE.passes;
    const without = skipsToday({ ...STATUS_LIVE, passes: three } as never, today);
    const withKey = skipsToday({ ...STATUS_LIVE, passes: { ...three, key_level_alert: KEY_PASS_FRESH } } as never, today);
    expect(withKey).toEqual(without);
  });

  it('NEGATIVE: the 🔑 pass is an intraday row, not a daily one ("no pass recorded" stays with the daily four)', async () => {
    stubFetch({ rows: ROWS }, STATUS_LIVE);
    draw();
    const kl = await screen.findByTestId('pass-key_level_alert');
    expect(within(kl).queryByText('no pass recorded')).not.toBeInTheDocument();
    expect(screen.getAllByTestId('pass-key_level_alert')).toHaveLength(1);
  });
});

/* ── 2026-09-29: the 🧬 medical-catalysts pass ──────────────────────────────
 *
 * Ajay: "… add right setup and alerts". catalysts/medical rides promo_live's
 * every-5-minutes crontab line (04:00–19:55 ET) and records its own pass doc
 * (alert_status MED_KIND), so /alerts carries it as a 5th intraday row judged
 * on the 5-minute clock.
 */
describe('Alerts page — the 🧬 medical-catalysts pass (2026-09-29)', () => {
  it('renders the row with its label, stamp and "every 5 min"', async () => {
    stubFetch({ rows: ROWS }, STATUS_LIVE);
    draw();
    const mc = await screen.findByTestId('pass-med_catalyst');
    expect(within(mc).getByText('🧬 Medical catalysts')).toBeInTheDocument();
    expect(within(mc).getByText('last pass 10:57 ET')).toBeInTheDocument();
    expect(within(mc).getByText('· every 5 min')).toBeInTheDocument();
    // NEGATIVE: the raw kind id is never the row's label.
    expect(within(mc).queryByText('med_catalyst')).not.toBeInTheDocument();
  });

  it('an older API with no cadence_sec still reads "every 5 min" (the promo_live line it rides)', async () => {
    const { cadence_sec: _drop, ...noCadence } = STATUS_LIVE.passes.med_catalyst;
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes, med_catalyst: noCadence } });
    draw();
    const mc = await screen.findByTestId('pass-med_catalyst');
    expect(within(mc).getByText('· every 5 min')).toBeInTheDocument();
  });

  it('NEGATIVE: a status without the 🧬 doc says "no pass yet today", never crashes, and the header does not vouch for it', async () => {
    const { med_catalyst: _gone, ...four } = STATUS_LIVE.passes;
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: four });
    draw();
    const mc = await screen.findByTestId('pass-med_catalyst');
    expect(within(mc).getByText('no pass yet today')).toBeInTheDocument();
    expect(within(mc).queryByText(/last pass/)).not.toBeInTheDocument();
    expect(screen.getByTestId('session-line')).toHaveTextContent('⚠ 1 of 6 passes');  // 5 → 6: 🚩 gajjala_setup joined 2026-10-13
    expect(await screen.findAllByTestId('alert-row')).toHaveLength(3);
  });

  /* fix round 3 (2026-09-29): SHADOW mode — the pass records what would have
   * pushed and sends nothing; the row says so in words, never as a raw key. */
  it('a shadow pass shows "🧬 shadow — nothing is sent" and "🧬 shadow — N would have pushed this pass"', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes,
      med_catalyst: { ...STATUS_LIVE.passes.med_catalyst, counts: { roster: 362, pushed: 0, shadow: 2, shadow_mode: 1 } } } });
    draw();
    const mc = await screen.findByTestId('pass-med_catalyst');
    expect(within(mc).getByText('🧬 shadow — nothing is sent')).toBeInTheDocument();
    expect(within(mc).getByText('🧬 shadow — 2 would have pushed this pass')).toBeInTheDocument();
    expect(within(mc).queryByText(/shadow_mode/)).not.toBeInTheDocument();
  });

  /* fix round 4 (critic #5): the per-pass count is 0 five minutes after a
   * would-push; the session count (from the stored events) keeps it visible. */
  it('the session count stays visible when the latest pass held nothing back', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes,
      med_catalyst: { ...STATUS_LIVE.passes.med_catalyst,
        counts: { roster: 362, pushed: 0, shadow: 0, shadow_mode: 1, shadow_session: 3 } } } });
    draw();
    const mc = await screen.findByTestId('pass-med_catalyst');
    expect(within(mc).getByText('🧬 shadow — 3 would have pushed this session')).toBeInTheDocument();
    expect(within(mc).queryByText(/this pass/)).not.toBeInTheDocument();
    expect(within(mc).queryByText(/shadow_session/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: a shadow session with nothing held back shows no session count', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes,
      med_catalyst: { ...STATUS_LIVE.passes.med_catalyst,
        counts: { roster: 362, pushed: 0, shadow: 0, shadow_mode: 1, shadow_session: 0 } } } });
    draw();
    const mc = await screen.findByTestId('pass-med_catalyst');
    expect(within(mc).getByText('🧬 shadow — nothing is sent')).toBeInTheDocument();
    expect(within(mc).queryByText(/would have pushed/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: a live pass (shadow_mode 0, shadow 0) wears no shadow chip', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes,
      med_catalyst: { ...STATUS_LIVE.passes.med_catalyst, counts: { roster: 362, pushed: 1, shadow: 0, shadow_mode: 0 } } } });
    draw();
    const mc = await screen.findByTestId('pass-med_catalyst');
    expect(within(mc).queryByText(/🧬 shadow/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: a 🧬 pass silent for 20 minutes mid-session reads STALE on the 5-minute clock', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes,
      med_catalyst: { ...STATUS_LIVE.passes.med_catalyst, as_of: '2026-09-05T10:40:00-04:00' } } });
    draw();
    const mc = await screen.findByTestId('pass-med_catalyst');
    expect(within(mc).getByText('stale — last pass 10:40 ET, expected every 5 min')).toBeInTheDocument();
    expect(screen.getByTestId('session-line')).toHaveTextContent('⚠ 1 of 6 passes');  // 5 → 6: 🚩 gajjala_setup joined 2026-10-13
  });
});

/* ── 2026-10-13: the 🚩 Gajjala A+ setups pass ─────────────────────────────
 *
 * DECISIONS: owner-only kind gajjala_setup, A+ only — and SHADOW first: every A+
 * is recorded on /alerts as "shadow — not sent" and nothing reaches the phone
 * until GAJJALA_PUSH_MODE is flipped. chart_maps/gajjala/run.py has its own
 * every-5-minutes crontab line and records its own pass doc (alert_status
 * GAJJALA_KIND), so the row is a 6th intraday pass judged on the 5-minute clock.
 */
describe('Alerts page — the 🚩 Gajjala A+ setups pass (2026-10-13)', () => {
  it('renders the row after 🧬 with its label, stamp, "every 5 min" and the shadow words', async () => {
    stubFetch({ rows: ROWS }, STATUS_LIVE);
    draw();
    const gg = await screen.findByTestId('pass-gajjala_setup');
    expect(within(gg).getByText('🚩 Gajjala A+ setups')).toBeInTheDocument();
    expect(within(gg).getByText('last pass 10:56 ET')).toBeInTheDocument();
    expect(within(gg).getByText('· every 5 min')).toBeInTheDocument();
    expect(within(gg).getByText('🚩 shadow — not sent (nothing reaches your phone yet)')).toBeInTheDocument();
    expect(within(gg).getByText('🚩 shadow — not sent: 1 A+ recorded this pass')).toBeInTheDocument();
    expect(within(gg).getByText('🚩 shadow — not sent: 2 A+ recorded today')).toBeInTheDocument();
    expect(within(gg).getByText('candidates 7')).toBeInTheDocument();
    // NEGATIVE: never the raw id, never the 🧬 words, never a raw counter key.
    expect(within(gg).queryByText('gajjala_setup')).not.toBeInTheDocument();
    expect(within(gg).queryByText(/🧬/)).not.toBeInTheDocument();
    expect(within(gg).queryByText(/shadow_mode|shadow_session/)).not.toBeInTheDocument();
    const strips = screen.getAllByTestId(/^pass-/).map((el) => el.getAttribute('data-testid')).filter((x) => x !== 'pass-reason');
    expect(strips.indexOf('pass-gajjala_setup')).toBe(strips.indexOf('pass-med_catalyst') + 1);
  });

  it('an older API with no cadence_sec still reads "every 5 min" (its own 5-minute line)', async () => {
    const { cadence_sec: _drop, ...noCadence } = STATUS_LIVE.passes.gajjala_setup;
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes, gajjala_setup: noCadence } });
    draw();
    const gg = await screen.findByTestId('pass-gajjala_setup');
    expect(within(gg).getByText('· every 5 min')).toBeInTheDocument();
  });

  it('the held-A+ counters say why the phone stayed quiet, in words', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes,
      gajjala_setup: { ...STATUS_LIVE.passes.gajjala_setup,
        counts: { candidates: 3, pushed: 0, shadow_mode: 1, suppressed_premarket: 2, suppressed_first15: 1, late: 1,
                  claimed_before: 1, suppressed_window: 1 } } } });
    draw();
    const gg = await screen.findByTestId('pass-gajjala_setup');
    for (const t of ['2 A+ held: pre-market', '1 A+ held: first 15 minutes',
                     '1 A+ found late (bar older than one pass), not sent', '1 A+ already recorded today',
                     '1 A+ held: outside his push windows']) {
      expect(within(gg).getByText(t)).toBeInTheDocument();
    }
    // NEGATIVE: no typed window — a half day ends 17:00, so "09:45–20:00" would be wrong there
    expect(within(gg).queryByText(/09:45–20:00/)).not.toBeInTheDocument();
    expect(within(gg).queryByText(/would have pushed/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: a live pass (shadow_mode 0) wears no shadow chip', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes,
      gajjala_setup: { ...STATUS_LIVE.passes.gajjala_setup, counts: { candidates: 7, pushed: 1, shadow: 0, shadow_mode: 0 } } } });
    draw();
    const gg = await screen.findByTestId('pass-gajjala_setup');
    expect(within(gg).queryByText(/shadow/)).not.toBeInTheDocument();
    expect(within(gg).getByText('push calls 1')).toBeInTheDocument();
  });

  it('NEGATIVE: the 🧬 row keeps its own 🧬 shadow words (the 🚩 words are scoped to the 🚩 row)', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes,
      med_catalyst: { ...STATUS_LIVE.passes.med_catalyst, counts: { roster: 362, pushed: 0, shadow: 2, shadow_mode: 1 } } } });
    draw();
    const mc = await screen.findByTestId('pass-med_catalyst');
    expect(within(mc).getByText('🧬 shadow — 2 would have pushed this pass')).toBeInTheDocument();
    expect(within(mc).queryByText(/🚩/)).not.toBeInTheDocument();
  });

  it('NEGATIVE: a status without the 🚩 doc says "no pass yet today" and the header does not vouch for it', async () => {
    const { gajjala_setup: _gone, ...five } = STATUS_LIVE.passes;
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: five });
    draw();
    const gg = await screen.findByTestId('pass-gajjala_setup');
    expect(within(gg).getByText('no pass yet today')).toBeInTheDocument();
    expect(screen.getByTestId('session-line')).toHaveTextContent('⚠ 1 of 6 passes');
  });

  it('NEGATIVE: a 🚩 pass silent for 20 minutes mid-session reads STALE on the 5-minute clock', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes,
      gajjala_setup: { ...STATUS_LIVE.passes.gajjala_setup, as_of: '2026-09-05T10:40:00-04:00' } } });
    draw();
    const gg = await screen.findByTestId('pass-gajjala_setup');
    expect(within(gg).getByText('stale — last pass 10:40 ET, expected every 5 min')).toBeInTheDocument();
  });

  it('the stale rule for the 5-minute pass is the backend STALE_AFTER_SEC (900 s)', () => {
    expect(staleAfterSec(300)).toBe(900);
  });
});

/* 2026-09-29 — every entry of a consolidated push, each ticker its own link.
 * Ajay, on "⚡ Tape burst at a zone — CRWV +7 more": "I am unable to see the
 * other that are hiddedn her … Can you show them all and make all the tickers
 * clicable individually?" Rows below are as push/recent.served_items serves
 * them. */
const TF_SYMS = ['CRWV', 'KLAC', 'NVDA', 'AVGO', 'CRWV', 'KLAC', 'NVDA', 'AVGO'];
const tfLine = (s: string, i: number) => `${s} 13:${String(10 + i).padStart(2, '0')}:00 — $1.0M buy burst, buyers pushing INTO the supply ceiling`;
const TF_NEW = {
  _id: 'tf1', ts: T('2026-09-05T14:17:30Z'), ts_iso: '2026-09-05T14:17:30+00:00',
  kind: 'trade_flash', ticker: null, tickers: [], source: 'push', sent: 1, failed: 0, total: 1,
  title: '⚡ Tape burst at a zone — CRWV +7 more', url: '/sepa/CRWV?tab=tape&from=supply-demand',
  body: TF_SYMS.slice(0, 4).map(tfLine).join('\n'),
  items: TF_SYMS.map((s, i) => ({ symbol: s, text: tfLine(s, i), url: `/sepa/${s}?tab=tape&from=supply-demand`, pushed: i < 4 })),
  items_not_stored: 0,
};
const HIS_LINES = [
  'CRWV 13:17:30 — $1.8M sell burst, sellers defending the supply ceiling',
  'CRWV 13:14:30 — $1.0M buy burst, buyers pushing INTO the supply ceiling',
  'CRWV 13:15:40 — $897K buy burst, buyers pushing INTO the supply ceiling',
  'KLAC 13:14:30 — $562K buy burst, buyers pushing INTO the supply ceiling',
];
const TF_LEGACY = {
  ...TF_NEW, _id: 'tf0', body: HIS_LINES.join('\n'), sent: 0, total: 0,
  items: HIS_LINES.map((t) => {
    const s = t.split(' ')[0];
    return { symbol: s, text: t, url: `/sepa/${s}?tab=tape&from=supply-demand`, pushed: true };
  }),
  items_not_stored: 4,
};
const KL_ROW = {
  _id: 'kl1', ts: T('2026-09-05T13:00:00Z'), ts_iso: '2026-09-05T13:00:00+00:00',
  kind: 'key_level_alert', ticker: null, tickers: ['PCT'], source: 'push', sent: 1, failed: 0, total: 1,
  title: '🔑 Key levels closed through — PCT over prior-month high', url: '/chart-maps?tab=support&symbol=PCT',
  body: 'PCT closed over prior-month high $1\nUnmeasured — a close through a level, not a signal.',
  items: [
    { symbol: 'PCT', text: 'PCT closed over prior-month high $1', url: '/chart-maps?tab=support&symbol=PCT', pushed: true },
    { symbol: null, text: 'Unmeasured — a close through a level, not a signal.', url: null, pushed: true },
  ],
  items_not_stored: 0,
};
const BRK_ROW = {
  _id: 'brk1', ts: T('2026-09-05T12:30:00Z'), ts_iso: '2026-09-05T12:30:00+00:00',
  kind: 'demand_alert', ticker: null, tickers: ['BRK.B'], source: 'push', sent: 1, failed: 0, total: 1,
  title: '🧲 Nearing demand — BRK.B', url: '/chart-maps?tab=zones&phase=approaching',
  body: 'BRK.B $480 · 2% above $470–475 · $1.0T',
  items: [{ symbol: 'BRK.B', text: 'BRK.B $480 · 2% above $470–475 · $1.0T', url: '/sepa/BRK.B?tab=supply', pushed: true }],
  items_not_stored: 0,
};

describe('Alerts page — every entry of a consolidated push (2026-09-29)', () => {
  it('lists all 8 bursts, each ticker its own tape link from alerts, with the off-push divider', async () => {
    stubFetch({ rows: [TF_NEW] });
    const { container } = draw();
    const rows = await screen.findAllByTestId('alert-row');
    const lines = within(rows[0]).getAllByTestId('alert-item');
    expect(lines).toHaveLength(8);
    expect(lines[4].textContent).toBe(tfLine('CRWV', 4));   // line 5, never on the phone
    expect(lines[4]).toBeVisible();
    const links = within(rows[0]).getAllByRole('link', { name: /^(CRWV|KLAC|NVDA|AVGO)$/ });
    expect(links).toHaveLength(8);
    for (const a of links) {
      expect(a.getAttribute('href')).toMatch(/^\/sepa\/(CRWV|KLAC|NVDA|AVGO)\?tab=tape&from=alerts/);
      expect(a.textContent).toMatch(/^(CRWV|KLAC|NVDA|AVGO)$/);
    }
    expect(within(rows[0]).getByText('+4 more not in the notification:')).toBeInTheDocument();
    // NEGATIVE: the header chip strip is gone on an itemized row
    expect(within(rows[0]).queryByTestId('alert-tks')).toBeNull();
    expect(container.querySelectorAll('a a')).toHaveLength(0);
  });

  it('his legacy row: 4 links and "+4 more not stored in this push", no off-push divider', async () => {
    stubFetch({ rows: [TF_LEGACY] });
    draw();
    const rows = await screen.findAllByTestId('alert-row');
    const links = within(rows[0]).getAllByRole('link', { name: /^(CRWV|KLAC)$/ });
    expect(links).toHaveLength(4);
    expect(within(rows[0]).getByText('+4 more not stored in this push')).toBeInTheDocument();
    // NEGATIVE: every legacy line was on the phone
    expect(within(rows[0]).queryByTestId('alert-items-offpush')).toBeNull();
  });

  it('a key-level entry links to its Support chart; a class share keeps its dot', async () => {
    stubFetch({ rows: [KL_ROW, BRK_ROW] });
    draw();
    const rows = await screen.findAllByTestId('alert-row');
    const pct = within(rows[0]).getByRole('link', { name: 'PCT' });
    expect(pct.getAttribute('href')).toBe('/chart-maps?tab=support&symbol=PCT');
    expect(within(rows[0]).getByText('Unmeasured — a close through a level, not a signal.')).toBeInTheDocument();
    const brk = within(rows[1]).getByRole('link', { name: 'BRK.B' });
    expect(brk.getAttribute('href')!.startsWith('/sepa/BRK.B?tab=supply&from=alerts')).toBe(true);
  });

  it('NEGATIVE: items: [] falls back to the body text and the header chips', async () => {
    stubFetch({ rows: [{ ...DIGEST_ROW, items: [], items_not_stored: 0 }] });
    const { container } = draw();
    const rows = await screen.findAllByTestId('alert-row');
    expect(within(rows[0]).getByText('AAA, BBB, CCC · pushed 09:05 ET')).toBeInTheDocument();
    expect(within(rows[0]).getByTestId('alert-tks')).toBeInTheDocument();
    expect(within(rows[0]).queryByTestId('alert-items')).toBeNull();
    expect(container.querySelectorAll('a a')).toHaveLength(0);
  });
});

/* ── 2026-10-13 E3: the 🚩 shadow A+ listed item by item ──────────────────
 *
 * Ajay round A (DECISIONS): "every A+ is RECORDED to the alerts ledger and
 * shown on /alerts as shadow — not sent". The pass strip counts; the list
 * under it is each record as backend alert_status.read_gajjala_shadow serves
 * it (`passes.gajjala_setup.shadow_items`, today only, newest first).
 */
const ggItem = (sym: string, setup: string, at: string, extra: Record<string, unknown> = {}) => ({
  date: '2026-09-05', symbol: sym, setup, at, entry_bar_t: `2026-09-05 ${at.slice(11, 16)}`, frame: '5m',
  trigger: 11.0, stop: 10.8125, risk_pct: 1.7,
  text: `${sym} · 🚩 Bull Flag A+ · broke 11.00 · stop 10.81 (−1.7%)`,
  url: `/chart-maps?tab=gajjala&sub=${setup}&focus=${sym}`, note: 'shadow — not sent', ...extra,
});
const withGgItems = (items: unknown[], counts?: Record<string, number>) => ({
  ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes,
    gajjala_setup: { ...STATUS_LIVE.passes.gajjala_setup, ...(counts ? { counts } : {}), shadow_items: items } },
});

describe('Alerts page — the 🚩 shadow A+ list (2026-10-13 E3)', () => {
  it('lists each shadow A+ under the 🚩 strip: ET time · the push line · "shadow — not sent", the symbol deep-linking to its tile', async () => {
    stubFetch({ rows: ROWS }, withGgItems([ggItem('GGB', 'kiss_fly', '2026-09-05T10:51:12-04:00',
                                                  { text: 'GGB · 💋 EMA Kiss & Fly A+ · broke 4.20 · stop 4.05 (−3.6%)' }),
                                          ggItem('GGA', 'bull_flag', '2026-09-05T09:51:12-04:00')]));
    const { container } = draw();
    const list = await screen.findByTestId('gg-shadow-list');
    expect(list).toHaveTextContent('🚩 A+ today · recorded, not sent · 2');
    const rows = within(list).getAllByTestId('gg-shadow-row');
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent('10:51 ET');
    expect(rows[0]).toHaveTextContent('GGB · 💋 EMA Kiss & Fly A+ · broke 4.20 · stop 4.05 (−3.6%)');
    expect(rows[1]).toHaveTextContent('09:51 ET');
    expect(rows[1]).toHaveTextContent('GGA · 🚩 Bull Flag A+ · broke 11.00 · stop 10.81 (−1.7%)');
    for (const r of rows) expect(within(r).getByText('shadow — not sent')).toBeInTheDocument();
    expect(within(rows[0]).getByRole('link', { name: 'GGB' }).getAttribute('href'))
      .toBe('/chart-maps?tab=gajjala&sub=kiss_fly&focus=GGB');
    expect(within(rows[1]).getByRole('link', { name: 'GGA' }).getAttribute('href'))
      .toBe('/chart-maps?tab=gajjala&sub=bull_flag&focus=GGA');
    // directly under the 🚩 strip, never inside the 🧬 one
    const strip = screen.getByTestId('pass-gajjala_setup');
    expect(strip.nextElementSibling).toBe(list);
    expect(within(screen.getByTestId('pass-med_catalyst')).queryByTestId('gg-shadow-row')).toBeNull();
    expect(container.querySelectorAll('a a')).toHaveLength(0);
  });

  it('NEGATIVE: a shadow row never shows a "sent" word — only "not sent" — and no delivery line', async () => {
    stubFetch({ rows: ROWS }, withGgItems([ggItem('GGA', 'bull_flag', '2026-09-05T09:51:12-04:00')]));
    draw();
    const row = (await screen.findAllByTestId('gg-shadow-row'))[0];
    const txt = row.textContent || '';
    expect(txt).toMatch(/not sent/);
    expect(txt.replace(/not sent/g, '')).not.toMatch(/\bsent\b|deliver|push calls|rang|device/i);
  });

  it('NEGATIVE: yesterday\'s shadow rows do not appear under today', async () => {
    stubFetch({ rows: ROWS }, withGgItems([
      ggItem('OLD', 'bull_flag', '2026-09-04T15:00:00-04:00', { date: '2026-09-04' }),
      ggItem('NEW', 'bull_flag', '2026-09-05T09:51:12-04:00')]));
    draw();
    const list = await screen.findByTestId('gg-shadow-list');
    expect(within(list).getAllByTestId('gg-shadow-row')).toHaveLength(1);
    expect(within(list).queryByText(/OLD/)).toBeNull();
    expect(list).toHaveTextContent('· 1');
  });

  it('NEGATIVE: only yesterday\'s rows (or none, or an older API) → no list at all', async () => {
    stubFetch({ rows: ROWS }, withGgItems([ggItem('OLD', 'bull_flag', '2026-09-04T15:00:00-04:00', { date: '2026-09-04' })]));
    draw();
    await screen.findByTestId('pass-gajjala_setup');
    expect(screen.queryByTestId('gg-shadow-list')).toBeNull();
  });

  it('NEGATIVE: a live pass with no shadow items lists nothing and keeps "push calls" (a pushed A+ is in the list below, not labelled shadow)', async () => {
    const pushedRow = { _id: 'gg1', ts: T('2026-09-05T14:10:00Z'), ts_iso: '2026-09-05T14:10:00+00:00',
      kind: 'gajjala_setup', ticker: 'GGL', title: '🚩 GGL · Bull Flag A+', url: '/chart-maps?tab=gajjala&sub=bull_flag&focus=GGL',
      source: 'push', sent: 1, failed: 0, total: 1, body: 'Broke 11.00 on the 5m bar closing 10:05 ET · UNMEASURED — his setup, not a buy signal' };
    stubFetch({ rows: [pushedRow] }, withGgItems([], { candidates: 7, pushed: 1, shadow: 0, shadow_mode: 0 }));
    draw();
    const gg = await screen.findByTestId('pass-gajjala_setup');
    expect(within(gg).getByText('push calls 1')).toBeInTheDocument();
    expect(screen.queryByTestId('gg-shadow-list')).toBeNull();
    const row = (await screen.findAllByTestId('alert-row'))[0];
    expect(row).toHaveTextContent('delivered to 1/1 device');
    expect(row.textContent || '').not.toMatch(/shadow/);
  });

  it('NEGATIVE: the 🧬 medical row is unchanged — counts-only chips, no item list, even if a pass doc carried items', async () => {
    stubFetch({ rows: ROWS }, { ...STATUS_LIVE, passes: { ...STATUS_LIVE.passes,
      med_catalyst: { ...STATUS_LIVE.passes.med_catalyst, counts: { roster: 362, pushed: 0, shadow: 2, shadow_mode: 1 },
                      shadow_items: [ggItem('MED', 'bull_flag', '2026-09-05T09:51:12-04:00')] } } });
    draw();
    const mc = await screen.findByTestId('pass-med_catalyst');
    expect(within(mc).getByText('🧬 shadow — nothing is sent')).toBeInTheDocument();
    expect(within(mc).getByText('🧬 shadow — 2 would have pushed this pass')).toBeInTheDocument();
    expect(screen.queryByTestId('gg-shadow-list')).toBeNull();
    expect(screen.queryByText(/MED · /)).toBeNull();
  });

  it('NEGATIVE: an outside url never becomes a link; the line still prints', async () => {
    stubFetch({ rows: ROWS }, withGgItems([ggItem('GGA', 'bull_flag', '2026-09-05T09:51:12-04:00', { url: '//evil.example/x' })]));
    draw();
    const row = (await screen.findAllByTestId('gg-shadow-row'))[0];
    expect(within(row).queryByRole('link')).toBeNull();
    expect(row).toHaveTextContent('GGA · 🚩 Bull Flag A+ · broke 11.00');
  });
});


/* ── 2026-10-14: the two tape-burst passes, their own strip ────────────────
 *
 * Ajay: "I need a tape burst notification specific for High Beta stocks from
 * the reselinet separately and also other tape bursts from the Chart Maps page".
 * Both kinds ride the trade-flash-watch line (every 5 min, 09:32–16:00 ET, the
 * window SERVED by alert_status from trade_flash.WATCH_OPEN_ET / WATCH_CLOSE_ET).
 * They sit in their own strip so the six intraday passes and the "all 6 passes"
 * line stay exactly as they were. Both are LIVE — no row ever says shadow.
 */
const TAPE_WIN = { open: '09:32', close: '16:00' };
const tapePass = (as_of: string, counts: Record<string, number> = {}, extra: Record<string, unknown> = {}) => ({
  as_of, date: as_of.slice(0, 10), cadence_sec: 300, window: TAPE_WIN, counts, ...extra,
});
const STATUS_TAPE = {
  ...STATUS_LIVE,
  passes: {
    ...STATUS_LIVE.passes,
    tape_burst_highbeta: tapePass('2026-09-05T10:57:40-04:00',
      { watched: 150, fetched: 146, no_tape: 4, candidates: 3, new: 2, pushed: 1, dup_trade_flash: 1, dup_kind: 0, skipped_budget: 0 }),
    tape_burst_chartmaps: tapePass('2026-09-05T10:57:55-04:00',
      { watched: 150, fetched: 150, candidates: 1, new: 1, pushed: 1, dup_kind: 1, tabs_read: 22, tabs_old: 2, skipped_budget: 3 }),
  },
};
const withTape = (over: Record<string, unknown>, top: Record<string, unknown> = {}) => ({
  ...STATUS_TAPE, ...top, passes: { ...STATUS_TAPE.passes, ...over },
});
const tapeText = () => ['pass-tape_burst_highbeta', 'pass-tape_burst_chartmaps']
  .map((id) => screen.getByTestId(id).textContent ?? '').join(' | ');

describe('Alerts page — the 🎢 🗺️ tape-burst passes (2026-10-14)', () => {
  it('renders both rows in their own strip, after the six intraday passes, with stamp, cadence and counters', async () => {
    stubFetch({ rows: ROWS }, STATUS_TAPE);
    draw();
    const hb = await screen.findByTestId('pass-tape_burst_highbeta');
    const cm = screen.getByTestId('pass-tape_burst_chartmaps');
    const strip = screen.getByTestId('tape-passes');
    expect(within(strip).getByTestId('pass-tape_burst_highbeta')).toBe(hb);
    expect(within(strip).getByTestId('pass-tape_burst_chartmaps')).toBe(cm);
    expect(within(hb).getByText('🎢 High-Beta tape bursts')).toBeInTheDocument();
    expect(within(cm).getByText('🗺️ Chart Maps tape bursts')).toBeInTheDocument();
    expect(within(hb).getByText('last pass 10:57 ET')).toBeInTheDocument();
    expect(within(hb).getByText('· every 5 min')).toBeInTheDocument();
    expect(within(hb).getByText('candidates 3')).toBeInTheDocument();
    expect(within(hb).getByText('pushes delivered 1')).toBeInTheDocument();
    expect(within(hb).queryByText(/push calls/)).not.toBeInTheDocument();
    expect(within(hb).getByText('1 recorded as ⚡ trade flash (muted on your phone)')).toBeInTheDocument();
    expect(within(hb).getByText('4 names with no regular prints in the window')).toBeInTheDocument();
    expect(within(cm).getByText('1 already sent by the other tape kind')).toBeInTheDocument();
    expect(within(cm).getByText('2 Chart Maps tabs not opened since the last session — not watched')).toBeInTheDocument();
    expect(within(cm).getByText('3 names not read (poll time budget)')).toBeInTheDocument();
    // NEGATIVE: zero counters wear no chip; raw counter keys never render.
    expect(within(hb).queryByText(/^0 /)).not.toBeInTheDocument();
    expect(within(hb).queryByText(/dup_trade_flash|dup_kind|no_tape/)).not.toBeInTheDocument();
    // the six intraday passes are unchanged and still come first, in order
    const ids = screen.getAllByTestId(/^pass-/).map((el) => el.getAttribute('data-testid')).filter((x) => x !== 'pass-reason');
    expect(ids.slice(0, 8)).toEqual(['pass-zone_edge', 'pass-zone_bounce_alert', 'pass-demand_alert', 'pass-key_level_alert',
      'pass-med_catalyst', 'pass-gajjala_setup', 'pass-tape_burst_highbeta', 'pass-tape_burst_chartmaps']);
    expect(screen.getByTestId('session-line')).toHaveTextContent('Session open — all 6 passes reported within cadence.');
  });

  it('NEGATIVE: the two tape rows never say "shadow" — both kinds ring live — even when a counter is named so', async () => {
    stubFetch({ rows: ROWS }, withTape({
      tape_burst_highbeta: tapePass('2026-09-05T10:57:40-04:00', { candidates: 2, pushed: 1, shadow_mode: 1, shadow: 2, shadow_session: 3 }),
    }));
    draw();
    await screen.findByTestId('pass-tape_burst_highbeta');
    expect(tapeText()).not.toMatch(/shadow/i);
    expect(screen.getByTestId('tape-passes-head').textContent).not.toMatch(/shadow/i);
    expect(screen.getByTestId('tape-passes-head').textContent).toMatch(/ring your phone/);
    // and none of the 🚩 / 🧬 shadow words leak onto them
    expect(tapeText()).not.toMatch(/🚩|🧬|not sent|would have pushed/);
  });

  it('NEGATIVE: the six existing pass rows are unchanged — the 🚩 row keeps its own shadow words, the tape kinds never join "N passes"', async () => {
    stubFetch({ rows: ROWS }, withTape({
      // a dead tape cron mid-window: stale on its own row …
      tape_burst_highbeta: tapePass('2026-09-05T10:20:00-04:00', { candidates: 0 }),
    }));
    draw();
    const gg = await screen.findByTestId('pass-gajjala_setup');
    expect(within(gg).getByText('🚩 shadow — not sent (nothing reaches your phone yet)')).toBeInTheDocument();
    expect(within(screen.getByTestId('pass-zone_edge')).getByText('14 skipped: room < 5%')).toBeInTheDocument();
    expect(within(screen.getByTestId('pass-tape_burst_highbeta')).getByText('stale — last pass 10:20 ET, expected every 5 min')).toBeInTheDocument();
    // … and the header line still speaks for the six only.
    expect(screen.getByTestId('session-line')).toHaveTextContent('Session open — all 6 passes reported within cadence.');
    expect(screen.getByTestId('session-line').textContent).not.toMatch(/of 8/);
  });

  it('outside the SERVED window a pass is never stale: after the close and pre-market both say so, in muted words', async () => {
    // 16:30 ET: zone_edge's clock is still open (04:00–20:00); the tape arm stopped at 16:00.
    stubFetch({ rows: ROWS }, withTape({
      tape_burst_highbeta: tapePass('2026-09-05T15:57:40-04:00', { candidates: 0 }),
      tape_burst_chartmaps: tapePass('2026-09-05T15:57:55-04:00', { candidates: 0 }),
    }, { now_et: '2026-09-05T16:30:00-04:00' }));
    draw();
    const hb = await screen.findByTestId('pass-tape_burst_highbeta');
    expect(within(hb).getByText('last pass 15:57 ET — outside its 09:32–16:00 ET window')).toBeInTheDocument();
    expect(tapeText()).not.toMatch(/stale/);
  });

  it('NEGATIVE: pre-market with only yesterday\'s pass reads "outside its window", never an amber alarm', async () => {
    stubFetch({ rows: ROWS }, withTape({
      tape_burst_highbeta: tapePass('2026-09-04T15:57:40-04:00', { candidates: 0 }),
      tape_burst_chartmaps: tapePass('2026-09-04T15:57:55-04:00', { candidates: 0 }),
    }, { now_et: '2026-09-05T08:10:00-04:00' }));
    draw();
    const hb = await screen.findByTestId('pass-tape_burst_highbeta');
    expect(within(hb).getByText('last pass 2026-09-04 15:57 ET — no pass yet today — outside its 09:32–16:00 ET window')).toBeInTheDocument();
    expect(tapeText()).not.toMatch(/stale/);
  });

  it('NEGATIVE: an older API with no window is never judged stale (it cannot be), even 30 minutes silent mid-session', async () => {
    const { window: _w, ...noWin } = tapePass('2026-09-05T10:30:00-04:00', { candidates: 0 });
    stubFetch({ rows: ROWS }, withTape({ tape_burst_highbeta: noWin }));
    draw();
    const hb = await screen.findByTestId('pass-tape_burst_highbeta');
    expect(within(hb).getByText('last pass 10:30 ET')).toBeInTheDocument();
    expect(within(hb).queryByText(/stale|outside its/)).not.toBeInTheDocument();
  });

  it('the kind chips carry both kinds right after ⚡ trade flash and narrow the feed to one', async () => {
    expect(KIND_CHIPS.indexOf('tape_burst_highbeta')).toBe(KIND_CHIPS.indexOf('trade_flash') + 1);
    expect(KIND_CHIPS.indexOf('tape_burst_chartmaps')).toBe(KIND_CHIPS.indexOf('trade_flash') + 2);
    expect(KIND_CHIPS.filter((k) => k.startsWith('tape_burst_'))).toHaveLength(2);
    const fn = stubFetch({ rows: [] }, STATUS_TAPE);
    draw();
    await waitFor(() => expect(recentUrls(fn)).toHaveLength(1));
    fireEvent.click(screen.getByRole('button', { name: '🎢 Tape burst — High Beta' }));
    await waitFor(() => expect(lastRecent(fn).searchParams.get('kinds')).toBe('tape_burst_highbeta'));
    fireEvent.click(screen.getByRole('button', { name: '🗺️ Tape burst — Chart Maps' }));
    await waitFor(() => expect(lastRecent(fn).searchParams.get('kinds')).toBe('tape_burst_highbeta,tape_burst_chartmaps'));
  });

  it('a 🎢 push row lists every burst, each ticker its own link to /sepa/{sym}?tab=tape', async () => {
    const hbLine = (s: string) => `${s} 10:41:20 — $1.2M sell burst · β 2.41 · -7.42% today`;
    const syms = ['NBIS', 'IREN', 'CRWV'];
    const row = {
      _id: 'hb1', ts: T('2026-09-05T14:42:00Z'), ts_iso: '2026-09-05T14:42:00+00:00',
      kind: 'tape_burst_highbeta', ticker: null, tickers: [], source: 'push', sent: 1, failed: 0, total: 1,
      title: '🎢 High-Beta tape burst — NBIS +2 more', url: '/sepa/NBIS?tab=tape&from=chart-maps',
      body: syms.slice(0, 2).map(hbLine).join('\n'),
      items: syms.map((s, i) => ({ symbol: s, text: hbLine(s), url: `/sepa/${s}?tab=tape&from=chart-maps`, pushed: i < 2 })),
      items_not_stored: 0,
    };
    stubFetch({ rows: [row] }, STATUS_TAPE);
    draw();
    const rows = await screen.findAllByTestId('alert-row');
    expect(within(rows[0]).getByText('🎢 Tape burst — High Beta')).toBeInTheDocument();
    const links = within(rows[0]).getAllByRole('link', { name: /^(NBIS|IREN|CRWV)$/ });
    expect(links).toHaveLength(3);
    for (const a of links) expect(a.getAttribute('href')).toMatch(/^\/sepa\/(NBIS|IREN|CRWV)\?tab=tape(&|$)/);
    // NEGATIVE: never the S&D supply tab, never the raw kind id
    for (const a of links) expect(a.getAttribute('href')).not.toMatch(/tab=supply/);
    expect(within(rows[0]).queryByText('tape_burst_highbeta')).not.toBeInTheDocument();
  });
});

describe('tape-burst helpers (2026-10-14)', () => {
  const st = (now: string, in_session = true) => ({ in_session, now_et: `2026-09-05T${now}:00-04:00` });
  const p = { as_of: null, date: null, counts: {}, window: TAPE_WIN };

  it('tapeWindow: inside from the open up to (not at) the close, on the server clock', () => {
    expect(tapeWindow(p, st('09:32')).inside).toBe(true);
    expect(tapeWindow(p, st('15:59')).inside).toBe(true);
    expect(tapeWindow(p, st('12:00'))).toEqual({ open: '09:32', close: '16:00', inside: true });
  });

  it('NEGATIVE tapeWindow: 09:31, 16:00, a closed session, no window, a malformed window → outside', () => {
    expect(tapeWindow(p, st('09:31')).inside).toBe(false);
    expect(tapeWindow(p, st('16:00')).inside).toBe(false);
    expect(tapeWindow(p, st('11:00', false)).inside).toBe(false);
    expect(tapeWindow({ ...p, window: null }, st('11:00'))).toEqual({ open: null, close: null, inside: false });
    expect(tapeWindow({ ...p, window: { open: '9:32', close: '16:00' } }, st('11:00')).inside).toBe(false);
    expect(tapeWindow(undefined, st('11:00')).inside).toBe(false);
    expect(tapeWindow(p, null).inside).toBe(false);
  });

  it('chip words: ⚡ is "recorded" and muted, a 🎢 zone burst is sent as 🎢; unknown counters fall through', () => {
    expect(tapeBurstChipText('dup_trade_flash', 2)).toBe('2 recorded as ⚡ trade flash (muted on your phone)');
    expect(tapeBurstChipText('at_zone', 1)).toBe('1 at a zone — sent as 🎢 (not ⚡)');
    expect(tapeBurstChipText('under_floor', 4)).toBe('4 names under the house share-price floor — not read');
    expect(tapeBurstChipText('dup_kind', 1)).toBe('1 already sent by the other tape kind');
    expect(tapeBurstChipText('tabs_old', 3)).toBe('3 Chart Maps tabs not opened since the last session — not watched');
    expect(tapeBurstChipText('watched', 150)).toBeNull();
    expect(tapeBurstChipText('dup_trade_flash', 1)).not.toMatch(/sent as/);
    expect(tapeBurstChipText('at_zone', 1)).not.toMatch(/sent as ⚡/);
  });

  it('NEGATIVE chip words: claimed_zone (never served) and the re-sighting counters render no words', () => {
    for (const k of ['claimed_zone', 'dup_same', 'dup_earlier']) expect(tapeBurstChipText(k, 2)).toBeNull();
  });

  it('a row shows at_zone + under_floor in words; dup_same / dup_earlier never reach the row or its hover title; pushed says delivered', async () => {
    stubFetch({ rows: ROWS }, withTape({
      tape_burst_highbeta: tapePass('2026-09-05T10:57:40-04:00',
        { watched: 150, candidates: 2, new: 2, pushed: 0, at_zone: 1, under_floor: 3, dup_same: 5, dup_earlier: 2,
          watch_http_fail: 0, claimed_zone: 4 }),
    }));
    draw();
    const hb = await screen.findByTestId('pass-tape_burst_highbeta');
    expect(within(hb).getByText('1 at a zone — sent as 🎢 (not ⚡)')).toBeInTheDocument();
    expect(within(hb).getByText('3 names under the house share-price floor — not read')).toBeInTheDocument();
    const pushed = within(hb).getByText('pushes delivered 0');
    expect(pushed.getAttribute('title')).toMatch(/^Pushes that reached at least one device/);
    // NEGATIVE: never the zone-pass "push calls" tooltip that counts a muted send
    expect(pushed.getAttribute('title')).not.toMatch(/nobody targeted|muted kind still counts/);
    const title = hb.getAttribute('title') ?? '';
    expect(title).not.toMatch(/dup same|dup earlier/);
    expect(hb.textContent).not.toMatch(/dup same|dup earlier|recorded as ⚡ trade flash/);
    // a stray claimed_zone counter is a raw key in the hover title only, never chip words
    expect(hb.textContent).not.toMatch(/claimed/);
    expect(title).toContain('watched 150');
  });

  it('NEGATIVE: the six intraday rows keep "push calls" and their own hover title (dup counters there untouched)', async () => {
    stubFetch({ rows: ROWS }, STATUS_TAPE);
    draw();
    const ze = await screen.findByTestId('pass-zone_edge');
    expect(within(ze).getByText('push calls 2').getAttribute('title')).toMatch(/nobody targeted/);
    expect(within(ze).queryByText(/pushes delivered/)).not.toBeInTheDocument();
  });

  it('TAPE_PASSES is exactly the two kinds on the 5-minute fallback, and sessionLine ignores them', () => {
    expect(TAPE_PASSES.map((m) => [m.key, m.fallbackCadenceSec])).toEqual([['tape_burst_highbeta', 300], ['tape_burst_chartmaps', 300]]);
    const today = '2026-09-05';
    const deadTape = { ...STATUS_TAPE, passes: { ...STATUS_TAPE.passes, tape_burst_highbeta: undefined, tape_burst_chartmaps: undefined } };
    expect(sessionLine(deadTape as never, today)).toBe('Session open — all 6 passes reported within cadence.');
    expect(passHealth(STATUS_TAPE.passes.tape_burst_highbeta, STATUS_TAPE, today, 300).health).toBe('fresh');
  });
});
