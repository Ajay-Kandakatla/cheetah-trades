/* TradeAutopsies — failed-trade autopsies from the paper Auto-Pilot.
 *
 * Ajay trades real money next to this page and the paper engine is one switch
 * from live, so every rule the component adds on top of the payload is pinned
 * here, negatives included:
 *   - one row per owner class renders from the API shape (strategy glyph, side,
 *     class pill, gain + R, MFE / MAE, time to exit, status pill, the feedback
 *     line under the row, tags) and an 'incomplete' row full of nulls renders
 *     "—" everywhere — never NaN / null / undefined;
 *   - newest exit first regardless of the server's order;
 *   - the summary strip: losers, one pill per class with its count in the
 *     owner-rule priority order, final / preliminary / incomplete, medians;
 *   - the empty state says a real sentence; a bodyless payload does not crash;
 *   - a failed fetch (reject OR non-2xx) shows the one-line note, never blank,
 *     and keeps the last good table when one exists;
 *   - the poll runs every 5 minutes while visible, skips hidden ticks, re-reads
 *     when the tab comes back, and dies with the component;
 *   - the pure helpers (pct / R / minutes / ET day / sort / labels / colors).
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import {
  TradeAutopsies, REFRESH_MS, DAYS, EMPTY_TEXT, UNAVAILABLE_TEXT, HELP_TEXT, CLASS_ORDER,
  signedPct, fmtR, fmtMinutes, fmtPx, fmtInt, fmtEt, etDay, exitMs, sortNewestFirst,
  strategyLabel, sideLabel, classLabel, classColor, statusColor, classEntries, ruleText,
} from './TradeAutopsies';
import type { AutopsyPayload, AutopsyRow, AutopsyRule } from './TradeAutopsies';

const NULL_ENTRY = {
  ts: null, price: null, qty: null, stop_requested_pct: null, stop_placed_pct: null, clamped: null,
  first_seen: null, entry_lag_sec: null, session_frac: null, chase_pct: null, band: null, tier: null,
};
const NULL_EXIT = { ts: null, price: null, leg: null, gain_pct: null, r_multiple: null, time_to_exit_min: null };
const NULL_EXC = { mfe_pct: null, mfe_r: null, mae_pct: null, reached_1r: null };
const NULL_STRUCT = { band_close_held: null, reclaimed_within_2: null, gap_open_pct: null };
const NULL_MKT = { spy_pct_entry_day: null, rsp_pct_entry_day: null, spy_pct_exit_day: null, rsp_pct_exit_day: null, gauge_now: null };

const SHAKEOUT_FEEDBACK =
  'stop 0.5% under the floor sat inside the noise: MAE −2.1% vs ATR 3.4%; a wider buffer is an owner decision';

/* Server order is deliberately NOT newest-first (an old incomplete row leads,
 * the newest exit sits in the middle) so the sort is proven, not assumed.
 * One row per owner class; ZZZ is the null-soaked 'incomplete' row. */
const FIX: AutopsyPayload = {
  days: 30,
  summary: {
    n: 7,
    by_class: { unclassified: 1, no_follow_through: 1, chased: 1, market_down: 1, band_failed: 1, shakeout: 1, stop_clamped: 1 },
    by_strategy: { zone_edge: 4, minervini: 1, manual: 2 },
    n_final: 4, n_preliminary: 2, n_incomplete: 1,
    median_mfe_r: 0.3, median_time_to_exit_min: 102,
  },
  rules: [
    { class: 'stop_clamped', rule: 'stop placed tighter than requested by > 0.1 pt AND exit >= requested stop', threshold: { clamp_pt: 0.1 } },
    { class: 'shakeout', rule: 'exit.leg == stop AND reclaimed the floor within 2 sessions', threshold: 2 },
  ],
  rows: [
    {
      trade_id: 't-zzz', symbol: 'ZZZ', strategy: 'manual', side: null, status: 'incomplete', retries: 2,
      computed_at: '2026-09-03T12:00:00Z',
      entry: NULL_ENTRY, exit: { ...NULL_EXIT, ts: '2026-09-01T18:30:00Z' }, excursion: NULL_EXC,
      structure: NULL_STRUCT, market: NULL_MKT, classification: 'unclassified', tags: ['partial_data'], feedback: null,
    },
    {
      trade_id: 't-nvda', symbol: 'NVDA', strategy: 'zone_edge', side: 'demand', status: 'final', retries: 0,
      computed_at: '2026-09-03T20:05:00Z',
      entry: { ts: '2026-09-03T14:00:00Z', price: 179.5, qty: 10, stop_requested_pct: 0.5, stop_placed_pct: 1.8, clamped: false,
               first_seen: '09:58', entry_lag_sec: 120, session_frac: 30 / 390, chase_pct: 0.4,
               band: { lo: 176, hi: 179, touches: 3 }, tier: 'A' },
      exit: { ts: '2026-09-03T15:42:00Z', price: 176.27, leg: 'stop', gain_pct: -1.8, r_multiple: -1.0, time_to_exit_min: 102 },
      excursion: { mfe_pct: 0.6, mfe_r: 0.3, mae_pct: -2.1, reached_1r: false },
      structure: { band_close_held: true, reclaimed_within_2: true, gap_open_pct: 0.2 },
      market: { spy_pct_entry_day: 0.3, rsp_pct_entry_day: 0.1, spy_pct_exit_day: 0.3, rsp_pct_exit_day: 0.1, gauge_now: null },
      classification: 'shakeout', tags: ['first_30_min_entry'], feedback: SHAKEOUT_FEEDBACK,
    },
    {
      trade_id: 't-anet', symbol: 'ANET', strategy: 'zone_edge', side: 'supply', status: 'preliminary', retries: 0,
      computed_at: '2026-09-03T20:05:00Z',
      entry: { ts: '2026-09-03T13:45:00Z', price: 129.4, qty: 15, stop_requested_pct: 3.1, stop_placed_pct: 2.0, clamped: true,
               first_seen: '09:41', entry_lag_sec: 240, session_frac: 15 / 390, chase_pct: 0.1,
               band: { lo: 127.5, hi: 129.3, touches: 4 }, tier: 'A' },
      exit: { ts: '2026-09-03T14:20:00Z', price: 128.2, leg: 'stop', gain_pct: -0.9, r_multiple: -1.0, time_to_exit_min: 35 },
      excursion: { mfe_pct: 0.3, mfe_r: 0.15, mae_pct: -1.0, reached_1r: false },
      structure: { band_close_held: true, reclaimed_within_2: null, gap_open_pct: 0.0 },
      market: { spy_pct_entry_day: 0.3, rsp_pct_entry_day: 0.1, spy_pct_exit_day: 0.3, rsp_pct_exit_day: 0.1, gauge_now: null },
      classification: 'stop_clamped', tags: ['first_30_min_entry'],
      feedback: 'the book clamped the stop to 2.0% (signal asked 3.1%); exit $128.20 sat above the requested level $125.39 — the clamp, not the thesis; loosening it is an owner decision',
    },
    {
      trade_id: 't-tjx', symbol: 'TJX', strategy: 'zone_edge', side: 'demand', status: 'final', retries: 0,
      computed_at: '2026-09-03T20:05:00Z',
      entry: { ts: '2026-09-01T18:55:00Z', price: 100.4, qty: 20, stop_requested_pct: 0.5, stop_placed_pct: 3.2, clamped: false,
               first_seen: '11:05', entry_lag_sec: 60, session_frac: 325 / 390, chase_pct: 0.4,
               band: { lo: 95, hi: 100, touches: 2 }, tier: 'B' },
      exit: { ts: '2026-09-02T19:55:00Z', price: 96.99, leg: 'stop', gain_pct: -3.4, r_multiple: -1.1, time_to_exit_min: 1500 },
      excursion: { mfe_pct: 0.2, mfe_r: 0.06, mae_pct: -3.6, reached_1r: false },
      structure: { band_close_held: false, reclaimed_within_2: false, gap_open_pct: -0.4 },
      market: { spy_pct_entry_day: 0.1, rsp_pct_entry_day: 0.0, spy_pct_exit_day: -0.4, rsp_pct_exit_day: -0.6, gauge_now: null },
      classification: 'band_failed', tags: ['thin_band'],
      feedback: 'exit-day close $94.80 under the band floor $95.00: the band failed; MFE +0.2% (0.06R)',
    },
    {
      trade_id: 't-crwd', symbol: 'CRWD', strategy: 'minervini', side: null, status: 'final', retries: 0,
      computed_at: '2026-09-03T20:05:00Z',
      entry: { ts: '2026-08-31T14:31:00Z', price: 420.1, qty: 3, stop_requested_pct: null, stop_placed_pct: 5.0, clamped: false,
               first_seen: null, entry_lag_sec: null, session_frac: 1 / 390, chase_pct: 0.5,
               band: { lo: 418, hi: 418, touches: null }, tier: null },
      exit: { ts: '2026-09-02T17:00:00Z', price: 399.1, leg: 'stop', gain_pct: -5.0, r_multiple: -1.0, time_to_exit_min: 3030 },
      excursion: { mfe_pct: 1.1, mfe_r: 0.22, mae_pct: -5.2, reached_1r: false },
      structure: { band_close_held: true, reclaimed_within_2: false, gap_open_pct: -1.4 },
      market: { spy_pct_entry_day: -0.2, rsp_pct_entry_day: -0.3, spy_pct_exit_day: -1.3, rsp_pct_exit_day: -1.6, gauge_now: null },
      classification: 'market_down', tags: ['gap_down_open', 'first_30_min_entry'],
      feedback: 'exit day SPY −1.3% / RSP −1.6% with MFE 0.22R: the tape, not the level',
    },
    {
      trade_id: 't-avgo', symbol: 'AVGO', strategy: 'zone_edge', side: 'supply', status: 'preliminary', retries: 0,
      computed_at: '2026-09-03T20:05:00Z',
      entry: { ts: '2026-09-03T14:35:00Z', price: 312.4, qty: 5, stop_requested_pct: 0.5, stop_placed_pct: 3.0, clamped: false,
               first_seen: '10:20', entry_lag_sec: 900, session_frac: 65 / 390, chase_pct: 2.6,
               band: { lo: 300, hi: 304.5, touches: 3 }, tier: 'S' },
      exit: { ts: '2026-09-03T17:10:00Z', price: 305.5, leg: 'stop', gain_pct: -2.2, r_multiple: -1.0, time_to_exit_min: 155 },
      excursion: { mfe_pct: 0.4, mfe_r: 0.13, mae_pct: -2.3, reached_1r: false },
      structure: { band_close_held: true, reclaimed_within_2: null, gap_open_pct: 0.8 },
      market: { spy_pct_entry_day: 0.3, rsp_pct_entry_day: 0.1, spy_pct_exit_day: 0.3, rsp_pct_exit_day: 0.1, gauge_now: null },
      classification: 'chased', tags: [],
      feedback: 'entry $312.40 was +2.60% past the band ceiling $304.50 (breakout limit 2.0%): chased',
    },
    {
      trade_id: 't-amd', symbol: 'AMD', strategy: 'manual', side: 'demand', status: 'final', retries: 0,
      computed_at: '2026-09-03T20:05:00Z',
      entry: { ts: '2026-09-01T19:00:00Z', price: 150, qty: 10, stop_requested_pct: null, stop_placed_pct: 1.6, clamped: false,
               first_seen: null, entry_lag_sec: null, session_frac: 330 / 390, chase_pct: null,
               band: null, tier: null },
      exit: { ts: '2026-09-01T20:00:00Z', price: 148.35, leg: 'flatten', gain_pct: -1.1, r_multiple: -0.7, time_to_exit_min: 60 },
      excursion: { mfe_pct: 0.3, mfe_r: 0.2, mae_pct: -1.2, reached_1r: false },
      structure: { band_close_held: null, reclaimed_within_2: null, gap_open_pct: 0.1 },
      market: { spy_pct_entry_day: 0.1, rsp_pct_entry_day: 0.0, spy_pct_exit_day: 0.1, rsp_pct_exit_day: 0.0, gauge_now: null },
      classification: 'no_follow_through', tags: [],
      feedback: 'MFE 0.2R never reached 1R before the flatten: no follow-through',
    },
  ],
};

const EMPTY: AutopsyPayload = {
  days: 30,
  summary: { n: 0, by_class: {}, by_strategy: {}, n_final: 0, n_preliminary: 0, n_incomplete: 0,
             median_mfe_r: null, median_time_to_exit_min: null },
  rules: [],
  rows: [],
};

/* Routes by URL: the autopsies call gets the fixture (or throws / fails when
 * told to); anything else (the watchlist store behind TickerLink) gets a
 * harmless empty body. `answer` may be a function so a test can fail the
 * SECOND call. */
type Answer = unknown | (() => unknown);
function stubFetch(answer: Answer) {
  const fn = vi.fn(async (url: string) => {
    if (String(url).includes('/trading/autopsies')) {
      const body = typeof answer === 'function' ? (answer as () => unknown)() : answer;
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

const autopsyCalls = (fn: ReturnType<typeof vi.fn>) =>
  fn.mock.calls.filter((c) => String(c[0]).includes('/trading/autopsies'));

const draw = () => render(<MemoryRouter><TradeAutopsies /></MemoryRouter>);

const rowBySymbol = (sym: string) =>
  screen.getAllByTestId('autopsy-row').find((r) => within(r).queryByRole('link', { name: new RegExp(sym) }))!;

beforeEach(() => vi.restoreAllMocks());
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('TradeAutopsies — rows and summary from a live payload', () => {
  it('asks for the 30-day autopsies with the session cookie', async () => {
    const fn = stubFetch(FIX);
    draw();
    await waitFor(() => expect(autopsyCalls(fn)).toHaveLength(1));
    const [url, init] = autopsyCalls(fn)[0] as [string, RequestInit];
    expect(url).toMatch(/\/trading\/autopsies\?days=30$/);
    expect(init.credentials).toBe('include');
  });

  it('renders the header, the help line and the summary strip with one pill per class in priority order', async () => {
    stubFetch(FIX);
    draw();
    expect(await screen.findByText('🔬 Failed-trade autopsies (30d)')).toBeInTheDocument();
    expect(screen.getByText('last 30 days · refreshes every 5 minutes')).toBeInTheDocument();
    expect(screen.getByText(HELP_TEXT)).toBeInTheDocument();
    // The help line names every owner class.
    for (const cls of CLASS_ORDER) expect(HELP_TEXT).toContain(classLabel(cls));

    // Scoped to the strip: 'final' is also a status pill text in the rows.
    const strip = within(screen.getByTestId('autopsy-summary'));
    const stat = (label: string) => strip.getByText(label).parentElement!;
    expect(stat('losers')).toHaveTextContent('7');
    expect(stat('final')).toHaveTextContent('4');
    expect(stat('preliminary')).toHaveTextContent('2');
    expect(stat('incomplete')).toHaveTextContent('1');
    expect(stat('median MFE')).toHaveTextContent('+0.3R');
    expect(stat('median time to exit')).toHaveTextContent('1h 42m');

    // Class chips: owner-rule priority order, NOT the server's key order.
    const chips = screen.getAllByTestId('class-chip').map((c) => c.textContent);
    expect(chips).toEqual([
      'stop clamped 1', 'shakeout 1', 'band failed 1', 'market down 1', 'chased 1', 'no follow-through 1', 'unclassified 1',
    ]);
    // The server's rule text rides on the chip as a tooltip when it sent one.
    expect(screen.getAllByTestId('class-chip')[1].getAttribute('title')).toMatch(/reclaimed the floor within 2 sessions/);
  });

  it('renders every row newest-exit-first with the feedback line under each', async () => {
    stubFetch(FIX);
    draw();
    await waitFor(() => expect(screen.getAllByTestId('autopsy-row')).toHaveLength(7));
    const order = screen.getAllByTestId('autopsy-row')
      .map((r) => within(r).getByRole('link').textContent);
    // AVGO 17:10Z · NVDA 15:42Z · ANET 14:20Z (all 9/3) · TJX 9/2 19:55Z · CRWD 9/2 17:00Z · AMD 9/1 20:00Z · ZZZ 9/1 18:30Z
    expect(order.map((t) => t?.replace(/[^A-Z]/g, ''))).toEqual(['AVGO', 'NVDA', 'ANET', 'TJX', 'CRWD', 'AMD', 'ZZZ']);
    expect(screen.getAllByTestId('autopsy-feedback')).toHaveLength(7);
    expect(screen.queryByText(EMPTY_TEXT)).not.toBeInTheDocument();
    expect(screen.queryByText(UNAVAILABLE_TEXT)).not.toBeInTheDocument();
    expect(screen.queryByText('loading…')).not.toBeInTheDocument();
  });

  it('NVDA — a complete shakeout row: every cell formatted, no "—" anywhere', async () => {
    stubFetch(FIX);
    draw();
    await waitFor(() => expect(screen.getAllByTestId('autopsy-row')).toHaveLength(7));
    const row = within(rowBySymbol('NVDA'));
    expect(row.getByText('2026-09-03')).toBeInTheDocument();                  // exit day, ET
    expect(row.getByText('🎯 zone-edge')).toBeInTheDocument();
    expect(row.getByText('🧲 demand')).toBeInTheDocument();
    expect(row.getByTestId('class-pill')).toHaveTextContent('shakeout');
    expect(row.getByTestId('class-pill')).toHaveStyle({ color: '#f59e0b' });   // amber
    expect(row.getByText('−1.8% · −1.0R')).toBeInTheDocument();
    expect(row.getByText('+0.6% / −2.1%')).toBeInTheDocument();
    expect(row.getByText('1h 42m')).toBeInTheDocument();
    expect(row.getByTestId('status-pill')).toHaveTextContent('final');
    expect(row.getByTestId('status-pill')).toHaveStyle({ color: '#10b981' });  // green
    expect(row.getByText(SHAKEOUT_FEEDBACK)).toBeInTheDocument();
    expect(row.getByTestId('autopsy-tag')).toHaveTextContent('first_30_min_entry');
    // Ticker link lands on the Supply / Demand tab (the zone-edge surface).
    expect(row.getByRole('link', { name: /NVDA/ }).getAttribute('href')).toMatch(/^\/sepa\/NVDA\?.*tab=supply/);
    // The class pill's hover carries the structural reads the class rests on.
    const title = row.getByTestId('class-pill').getAttribute('title') ?? '';
    expect(title).toMatch(/reclaimed within 2: yes/);
    expect(title).toMatch(/band close held: yes/);
    expect(title).toMatch(/stop asked \+0\.50% placed \+1\.80%/);
    // NEGATIVE: a complete row has no "—" placeholder anywhere.
    expect(row.queryAllByText('—')).toHaveLength(0);
    // Exit-day cell hover shows entry → exit in ET (UTC−4 in September).
    expect(row.getByText('2026-09-03').getAttribute('title')).toBe('entry 10:00 ET $179.50 → exit 11:42 ET $176.27');
  });

  it('ZZZ — the null-soaked incomplete row renders "—" and the pending line, never NaN / null / undefined', async () => {
    stubFetch(FIX);
    draw();
    await waitFor(() => expect(screen.getAllByTestId('autopsy-row')).toHaveLength(7));
    const el = rowBySymbol('ZZZ');
    const row = within(el);
    expect(row.getByText('2026-09-01')).toBeInTheDocument();
    expect(row.getByText('✋ manual')).toBeInTheDocument();
    expect(row.getByTestId('class-pill')).toHaveTextContent('unclassified');
    expect(row.getByTestId('class-pill')).toHaveStyle({ color: '#94a3b8' });   // muted
    expect(row.getByText('— / —')).toBeInTheDocument();
    expect(row.getAllByText('—')).toHaveLength(3);                             // side · result · time to exit
    expect(row.getByTestId('status-pill')).toHaveTextContent('incomplete');
    expect(row.getByTestId('status-pill').getAttribute('title')).toBe('retries 2');
    expect(row.getByText('feedback pending — inputs missing, retried next tick')).toBeInTheDocument();
    expect(row.getByTestId('autopsy-tag')).toHaveTextContent('partial_data');
    expect(el.textContent).not.toMatch(/NaN|null|undefined/);
  });

  it('the other five classes: label, color, strategy glyph and time-to-exit units', async () => {
    stubFetch(FIX);
    draw();
    await waitFor(() => expect(screen.getAllByTestId('autopsy-row')).toHaveLength(7));

    const anet = within(rowBySymbol('ANET'));
    expect(anet.getByTestId('class-pill')).toHaveTextContent('stop clamped');
    expect(anet.getByTestId('class-pill')).toHaveStyle({ color: '#f59e0b' });
    expect(anet.getByText('🚀 breakout')).toBeInTheDocument();
    expect(anet.getByText('35 m')).toBeInTheDocument();
    expect(anet.getByTestId('status-pill')).toHaveTextContent('preliminary');
    expect(anet.getByTestId('status-pill')).toHaveStyle({ color: '#f59e0b' });
    expect(anet.getByTestId('class-pill').getAttribute('title')).toMatch(/\(clamped\)/);

    const tjx = within(rowBySymbol('TJX'));
    expect(tjx.getByTestId('class-pill')).toHaveTextContent('band failed');
    expect(tjx.getByTestId('class-pill')).toHaveStyle({ color: '#ef4444' });   // red
    expect(tjx.getByText('1d 1h')).toBeInTheDocument();
    expect(tjx.getByText('−3.4% · −1.1R')).toBeInTheDocument();
    expect(tjx.getByTestId('autopsy-tag')).toHaveTextContent('thin_band');

    const crwd = within(rowBySymbol('CRWD'));
    expect(crwd.getByTestId('class-pill')).toHaveTextContent('market down');
    expect(crwd.getByTestId('class-pill')).toHaveStyle({ color: '#64748b' });  // slate
    expect(crwd.getByText('📘 minervini')).toBeInTheDocument();
    expect(crwd.getByText('2d 2h')).toBeInTheDocument();
    expect(crwd.getAllByTestId('autopsy-tag').map((t) => t.textContent)).toEqual(['gap_down_open', 'first_30_min_entry']);
    // A minervini trade has no zone side — "—", not an invented one.
    expect(crwd.getAllByText('—')).toHaveLength(1);

    const avgo = within(rowBySymbol('AVGO'));
    expect(avgo.getByTestId('class-pill')).toHaveTextContent('chased');
    expect(avgo.getByText('2h 35m')).toBeInTheDocument();
    expect(avgo.queryAllByTestId('autopsy-tag')).toHaveLength(0);

    const amd = within(rowBySymbol('AMD'));
    expect(amd.getByTestId('class-pill')).toHaveTextContent('no follow-through');
    expect(amd.getByTestId('class-pill')).toHaveStyle({ color: '#64748b' });
    expect(amd.getByText('1h 00m')).toBeInTheDocument();
    expect(amd.getByText('−1.1% · −0.7R').getAttribute('title')).toBe('exit leg: flatten');
  });

  it('shows gain alone when the R multiple is missing, and an unknown class / strategy verbatim', async () => {
    const row: AutopsyRow = {
      ...FIX.rows![1], symbol: 'CRM', trade_id: 't-crm', strategy: 'weird_path', classification: 'new_rule',
      exit: { ...FIX.rows![1].exit, r_multiple: null },
    };
    stubFetch({ ...FIX, rows: [row], summary: { ...FIX.summary, by_class: { new_rule: 1 } } });
    draw();
    await waitFor(() => expect(screen.getAllByTestId('autopsy-row')).toHaveLength(1));
    const r = within(screen.getByTestId('autopsy-row'));
    expect(r.getByText('−1.8%')).toBeInTheDocument();
    expect(r.getByText('weird_path')).toBeInTheDocument();
    expect(r.getByTestId('class-pill')).toHaveTextContent('new rule');
    expect(screen.getAllByTestId('class-chip').map((c) => c.textContent)).toEqual(['new rule 1']);
  });
});

describe('TradeAutopsies — empty and failed reads', () => {
  it('says the table fills in later when there are no failed trades', async () => {
    stubFetch(EMPTY);
    draw();
    expect(await screen.findByText(EMPTY_TEXT)).toBeInTheDocument();
    expect(screen.getByText('losers').parentElement).toHaveTextContent('0');
    expect(screen.getByText('median MFE').parentElement).toHaveTextContent('—');
    expect(screen.getByText('median time to exit').parentElement).toHaveTextContent('—');
    expect(screen.queryAllByTestId('class-chip')).toHaveLength(0);
    expect(screen.queryAllByTestId('autopsy-row')).toHaveLength(0);
  });

  it('renders the empty state, not a crash, on a payload with no arrays', async () => {
    stubFetch({});
    draw();
    expect(await screen.findByText(EMPTY_TEXT)).toBeInTheDocument();
    expect(screen.getByText(`🔬 Failed-trade autopsies (${DAYS}d)`)).toBeInTheDocument();
    expect(screen.getByText('losers').parentElement).toHaveTextContent('0');
  });

  it('survives a row with no sub-objects at all', async () => {
    stubFetch({ rows: [{ symbol: 'BARE' }] });
    draw();
    await waitFor(() => expect(screen.getAllByTestId('autopsy-row')).toHaveLength(1));
    const el = screen.getByTestId('autopsy-row');
    expect(el.textContent).not.toMatch(/NaN|null|undefined/);
    expect(within(el).getByTestId('class-pill')).toHaveTextContent('—');
    expect(within(el).getByTestId('status-pill')).toHaveTextContent('—');
  });

  it('shows the one-line note when the fetch rejects — never a blank card', async () => {
    stubFetch(new Error('network down'));
    draw();
    const note = await screen.findByRole('status');
    expect(note).toHaveTextContent(UNAVAILABLE_TEXT);
    expect(note.getAttribute('title')).toBe('network down');
    // NEGATIVE: an unreachable ledger must not read as "no failed trades".
    expect(screen.queryByText(EMPTY_TEXT)).not.toBeInTheDocument();
    expect(screen.queryByText('loading…')).not.toBeInTheDocument();
  });

  it('treats a non-2xx (the admin gate 403 included) as unavailable too', async () => {
    stubFetch({ status: 403 });
    draw();
    const note = await screen.findByRole('status');
    expect(note).toHaveTextContent(UNAVAILABLE_TEXT);
    expect(note.getAttribute('title')).toBe('HTTP 403');
    expect(screen.queryByText(EMPTY_TEXT)).not.toBeInTheDocument();
  });

  it('keeps the last good table when a later tick fails', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let calls = 0;
    const fn = stubFetch(() => (++calls === 1 ? FIX : new Error('boom')));
    draw();
    await waitFor(() => expect(screen.getAllByTestId('autopsy-row')).toHaveLength(7));

    await act(async () => { await vi.advanceTimersByTimeAsync(REFRESH_MS + 50); });
    await waitFor(() => expect(autopsyCalls(fn)).toHaveLength(2));
    expect(await screen.findByRole('status')).toHaveTextContent(UNAVAILABLE_TEXT);
    expect(screen.getAllByTestId('autopsy-row')).toHaveLength(7);
  });
});

describe('TradeAutopsies — the 5-minute clock', () => {
  it('fetches on mount, every 5 minutes while visible, and stops on unmount', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fn = stubFetch(EMPTY);
    const view = draw();
    await waitFor(() => expect(autopsyCalls(fn)).toHaveLength(1));

    // NEGATIVE: one minute is not a tick — this card is slower than the race.
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(autopsyCalls(fn)).toHaveLength(1);

    await act(async () => { await vi.advanceTimersByTimeAsync(REFRESH_MS - 60_000 + 50); });
    expect(autopsyCalls(fn)).toHaveLength(2);

    view.unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(3 * REFRESH_MS); });
    // NEGATIVE: an unmounted card must not keep polling.
    expect(autopsyCalls(fn)).toHaveLength(2);
  });

  it('skips the tick while the tab is hidden and resumes when visible', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fn = stubFetch(EMPTY);
    draw();
    await waitFor(() => expect(autopsyCalls(fn)).toHaveLength(1));

    const vis = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden');
    await act(async () => { await vi.advanceTimersByTimeAsync(2 * REFRESH_MS + 50); });
    expect(autopsyCalls(fn)).toHaveLength(1);

    vis.mockReturnValue('visible');
    await act(async () => { await vi.advanceTimersByTimeAsync(REFRESH_MS + 50); });
    expect(autopsyCalls(fn)).toHaveLength(2);
    vis.mockRestore();
  });

  it('re-reads at once when the tab comes back into view', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fn = stubFetch(EMPTY);
    draw();
    await waitFor(() => expect(autopsyCalls(fn)).toHaveLength(1));

    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
    await waitFor(() => expect(autopsyCalls(fn)).toHaveLength(2));
  });
});

describe('helpers', () => {
  it('signedPct / fmtR — explicit sign, unicode minus, "—" for nulls and NaN', () => {
    expect(signedPct(1.24)).toBe('+1.2%');
    expect(signedPct(-2.36)).toBe('−2.4%');
    expect(signedPct(0)).toBe('0.0%');
    expect(signedPct(0.306, 2)).toBe('+0.31%');
    expect(signedPct(null)).toBe('—');
    expect(signedPct(undefined)).toBe('—');
    expect(signedPct(Number.NaN)).toBe('—');
    expect(fmtR(1.2)).toBe('+1.2R');
    expect(fmtR(-0.75)).toBe('−0.8R');
    expect(fmtR(0)).toBe('0.0R');
    expect(fmtR(null)).toBe('—');
    expect(fmtR(Number.POSITIVE_INFINITY)).toBe('—');
  });

  it('fmtMinutes — minutes, hours with zero-padded minutes, days; null; no negative clock', () => {
    expect(fmtMinutes(0)).toBe('0 m');
    expect(fmtMinutes(42)).toBe('42 m');
    expect(fmtMinutes(59.6)).toBe('1h 00m');     // rounds to 60 → an hour, not "60 m"
    expect(fmtMinutes(60)).toBe('1h 00m');
    expect(fmtMinutes(155)).toBe('2h 35m');
    expect(fmtMinutes(1439)).toBe('23h 59m');
    expect(fmtMinutes(1500)).toBe('1d 1h');
    expect(fmtMinutes(3030)).toBe('2d 2h');
    expect(fmtMinutes(-5)).toBe('0 m');          // feed clock skew never prints a minus
    expect(fmtMinutes(null)).toBe('—');
    expect(fmtMinutes(Number.NaN)).toBe('—');
  });

  it('fmtPx / fmtInt — two decimals / rounded; "—" for nulls', () => {
    expect(fmtPx(176.27)).toBe('$176.27');
    expect(fmtPx(null)).toBe('—');
    expect(fmtInt(2.4)).toBe('2');
    expect(fmtInt(null)).toBe('—');
  });

  it('fmtEt / etDay — UTC ISO on the New York clock and calendar; garbage to ""', () => {
    expect(fmtEt('2026-09-03T15:42:00Z')).toBe('11:42');       // EDT = UTC−4
    expect(fmtEt('2026-01-15T14:13:40Z')).toBe('09:13');       // EST = UTC−5
    expect(fmtEt('nope')).toBe('');
    expect(fmtEt(null)).toBe('');
    expect(etDay('2026-09-03T15:42:00Z')).toBe('2026-09-03');
    expect(etDay('2026-09-03T03:30:00Z')).toBe('2026-09-02');  // 23:30 ET the night before — the ET day, not UTC's
    expect(etDay('2026-09-03T11:42:00-04:00')).toBe('2026-09-03');
    expect(etDay('nope')).toBe('');
    expect(etDay(undefined)).toBe('');
  });

  it('exitMs / sortNewestFirst — exit.ts, then entry.ts, then computed_at, unparseable last; stable', () => {
    const a: AutopsyRow = { symbol: 'A', exit: { ts: '2026-09-03T15:42:00Z' } };
    const b: AutopsyRow = { symbol: 'B', exit: { ts: null }, entry: { ts: '2026-09-03T16:00:00Z' } };   // no exit → entry
    const c: AutopsyRow = { symbol: 'C' };                                                            // nothing → last
    const d: AutopsyRow = { symbol: 'D', computed_at: '2026-09-02T12:00:00Z' };                        // computed_at only
    const e: AutopsyRow = { symbol: 'E', exit: { ts: 'garbage' }, entry: { ts: 'garbage' }, computed_at: 'garbage' };
    expect(sortNewestFirst([c, d, a, e, b]).map((r) => r.symbol)).toEqual(['B', 'A', 'D', 'C', 'E']);
    expect(exitMs(c)).toBe(-Infinity);
    expect(exitMs(e)).toBe(-Infinity);
    // Ties keep server order.
    const f: AutopsyRow = { symbol: 'F', exit: { ts: a.exit!.ts } };
    expect(sortNewestFirst([f, a]).map((r) => r.symbol)).toEqual(['F', 'A']);
  });

  it('strategyLabel / sideLabel / classLabel — the known values, verbatim for anything else, "—" for nothing', () => {
    expect(strategyLabel('zone_edge')).toBe('🎯 zone-edge');
    expect(strategyLabel('minervini')).toBe('📘 minervini');
    expect(strategyLabel('manual')).toBe('✋ manual');
    expect(strategyLabel('odd')).toBe('odd');
    expect(strategyLabel(null)).toBe('—');
    expect(sideLabel('supply')).toBe('🚀 breakout');
    expect(sideLabel('demand')).toBe('🧲 demand');
    expect(sideLabel('pivot')).toBe('📍 pivot');       // backend side for a minervini auto-entry
    expect(sideLabel('weird')).toBe('weird');
    expect(sideLabel(undefined)).toBe('—');
    expect(classLabel('stop_clamped')).toBe('stop clamped');
    expect(classLabel('no_follow_through')).toBe('no follow-through');
    expect(classLabel('some_new_rule')).toBe('some new rule');
    expect(classLabel(null)).toBe('—');
  });

  it('classColor / statusColor — the owner palette, muted for anything unknown', () => {
    expect(classColor('stop_clamped')).toBe('#f59e0b');
    expect(classColor('shakeout')).toBe('#f59e0b');
    expect(classColor('chased')).toBe('#f59e0b');
    expect(classColor('band_failed')).toBe('#ef4444');
    expect(classColor('market_down')).toBe('#64748b');
    expect(classColor('no_follow_through')).toBe('#64748b');
    expect(classColor('unclassified')).toBe('#94a3b8');
    expect(classColor('nope')).toBe('#94a3b8');
    expect(classColor(null)).toBe('#94a3b8');
    expect(statusColor('final')).toBe('#10b981');
    expect(statusColor('preliminary')).toBe('#f59e0b');
    expect(statusColor('incomplete')).toBe('#94a3b8');
    expect(statusColor(null)).toBe('#94a3b8');
  });

  it('ruleText — the server sentence only when it is a real string for a real class', () => {
    const rules = [
      { class: 'shakeout', rule: 'r1' },
      { class: 'chased', rule: { nested: true } as unknown as string },
      { class: null, rule: 'ghost' },
      null as unknown as AutopsyRule,
    ];
    expect(ruleText(rules, 'shakeout')).toBe('r1');
    expect(ruleText(rules, 'chased')).toBeUndefined();     // an object never prints as "[object Object]"
    expect(ruleText(rules, null)).toBeUndefined();         // a null class never borrows the 'ghost' rule
    expect(ruleText(rules, undefined)).toBeUndefined();
    expect(ruleText(rules, 'nope')).toBeUndefined();
    expect(ruleText([], 'shakeout')).toBeUndefined();
  });

  it('classEntries — priority order first, unknown keys after, non-numbers dropped, null safe', () => {
    expect(classEntries({ chased: 2, stop_clamped: 1, brand_new: 3, shakeout: 'x' as unknown as number })).toEqual([
      ['stop_clamped', 1], ['chased', 2], ['brand_new', 3],
    ]);
    expect(classEntries(null)).toEqual([]);
    expect(classEntries(undefined)).toEqual([]);
    expect(classEntries({})).toEqual([]);
  });
});

describe('TradeAutopsies — hostile payload shapes never blank the Trading page', () => {
  it('drops null / non-object rows and rules; a row without a symbol prints "—", never "undefined"', async () => {
    stubFetch({
      rows: [null, 'junk', 7, { ...FIX.rows![1] }, { trade_id: 't-nosym', exit: { ts: '2026-09-03T10:00:00Z' } }] as unknown as AutopsyRow[],
      rules: [null, 7, { class: 'shakeout', rule: { nested: true } }, { class: null, rule: 'ghost' }] as unknown as AutopsyPayload['rules'],
      summary: { by_class: { shakeout: 1 } },
    });
    draw();
    await waitFor(() => expect(screen.getAllByTestId('autopsy-row')).toHaveLength(2));
    const card = screen.getByTestId('trade-autopsies');
    expect(card.textContent).not.toMatch(/NaN|null|undefined|\[object Object\]/);
    // NEGATIVE: junk elements are dropped silently — this is not a failed read.
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    // The symbol-less row has no link at all — no /sepa/undefined.
    expect(screen.getAllByRole('link')).toHaveLength(1);
    expect(screen.getByRole('link').getAttribute('href')).toMatch(/^\/sepa\/NVDA\?/);
    const bare = screen.getAllByTestId('autopsy-row').find((r) => !within(r).queryByRole('link'))!;
    expect(within(bare).getByText('—', { selector: 'b' })).toBeInTheDocument();
    // A non-string rule sentence never lands in a tooltip; a null-class rule is never borrowed.
    expect(screen.getByTestId('class-chip').getAttribute('title')).toBeNull();
    expect(within(rowBySymbol('NVDA')).getByTestId('class-pill').getAttribute('title')).not.toMatch(/object|ghost/);
    expect(within(bare).getByTestId('class-pill').getAttribute('title')).not.toMatch(/ghost/);
  });

  it('renders a repeated tag once and drops blanks / non-strings', async () => {
    stubFetch({ rows: [{ ...FIX.rows![1], tags: ['thin_band', 'thin_band', ' ', 42 as unknown as string, 'wide_stop'] }] });
    draw();
    await waitFor(() => expect(screen.getAllByTestId('autopsy-row')).toHaveLength(1));
    expect(screen.getAllByTestId('autopsy-tag').map((t) => t.textContent)).toEqual(['thin_band', 'wide_stop']);
  });

  it('a minervini row carries the backend side "pivot" with its own glyph', async () => {
    stubFetch({ rows: [{ ...FIX.rows![4], side: 'pivot' }] });
    draw();
    await waitFor(() => expect(screen.getAllByTestId('autopsy-row')).toHaveLength(1));
    expect(screen.getByText('📍 pivot')).toBeInTheDocument();
    expect(screen.getByText('📘 minervini')).toBeInTheDocument();
  });
});
