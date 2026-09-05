/* ZoneEdgeBoard — the minute-by-minute zone-edge board.
 *
 * Ajay trades real money off this surface, so each rule the component adds on
 * top of the payload is pinned here, negatives included:
 *   - the two sections render from the API's row shape (tags, pills, read);
 *   - mode="breaking" hides the demand side (Deep Demand tab);
 *   - empty sections say a real answer, never blank;
 *   - the header tells no-pass-yet / closed / live apart;
 *   - the poll runs once a minute while visible, skips hidden ticks, and dies
 *     with the component;
 *   - the sparkline read is the last 5 points only, with a flat band, and the
 *     broke tier gets its own words (a break "closing in" would be wrong);
 *   - a payload with no arrays (older backend, wrong stub) renders empty, not
 *     a crash.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import {
  ZoneEdgeBoard, REFRESH_MS, READ_WINDOW, FLAT_EPS, STALE_AFTER_MIN, ageMinutes, capLabel, hhmm, sparkRead,
} from './ZoneEdgeBoard';
import type { TrackPoint, ZoneEdgePayload } from './ZoneEdgeBoard';
import { _resetAlertHistoryCache } from '../hooks/useAlertHistory';

const FIX: ZoneEdgePayload = {
  as_of: '2026-09-03T15:42:07-04:00',
  date: '2026-09-03',
  in_session: true,
  pass_sec: 4.2,
  params: { edge_pct: 1.0, broke_max_pct: 3.0, min_cap_usd: 1e9, min_touches_push: 2 },
  counts: { breaking: 2, near_demand: 2, candidates: 900, priced: 890, stale_print: 3 },
  breaking: [
    {
      symbol: 'NVDA', name: 'NVIDIA', last: 181.2, dist_pct: -1.2, tier: 'broke', side: 'supply',
      role: 'resistance', band: { kind: 'supply', lo: 176, hi: 179, touches: 3, strength: 70 },
      cap: 4.4e12, new_highs: true, high_252: 183.5, pct_to_52w: -1.3, overhead_bands: 0,
      arrival: false, first_seen: '10:12', url: '/sepa/NVDA?tab=supply',
    },
    {
      symbol: 'ANET', name: 'Arista', last: 128.4, dist_pct: 0.7, tier: 'near', side: 'supply',
      role: 'resistance', band: { kind: 'supply', lo: 127.5, hi: 129.3, touches: 2, strength: 55 },
      cap: 1.6e11, new_highs: false, high_252: 140.1, pct_to_52w: 9.1, overhead_bands: 2,
      arrival: false, first_seen: '15:31', url: '/sepa/ANET?tab=supply',
    },
  ],
  near_demand: [
    {
      symbol: 'NTAP', name: 'NetApp', last: 163.2, dist_pct: 0, tier: 'in', side: 'demand',
      role: 'broken supply', band: { kind: 'supply', lo: 162, hi: 168, touches: 1, strength: 40 },
      cap: 3.3e10, new_highs: false, high_252: null, pct_to_52w: null, overhead_bands: null,
      arrival: true, first_seen: '09:33', url: '/sepa/NTAP?tab=supply',
    },
    {
      symbol: 'TJX', name: 'TJX Cos', last: 100.8, dist_pct: 0.8, tier: 'near', side: 'demand',
      role: 'demand', band: { kind: 'demand', lo: 95, hi: 100, touches: 3, strength: 60 },
      cap: 1.2e11, new_highs: false, high_252: null, pct_to_52w: null, overhead_bands: null,
      arrival: false, first_seen: '11:05', url: '/sepa/TJX?tab=supply',
    },
  ],
  track: {
    'supply:NVDA': [['15:38', -0.4], ['15:39', -0.6], ['15:40', -0.9], ['15:41', -1.0], ['15:42', -1.2]],
    'supply:ANET': [['15:38', 1.4], ['15:39', 1.2], ['15:40', 1.0], ['15:41', 0.8], ['15:42', 0.7]],
    'demand:TJX':  [['15:38', 0.4], ['15:39', 0.5], ['15:40', 0.6], ['15:41', 0.7], ['15:42', 0.8]],
  },
  disclaimer: 'Decision support, not advice.',
};

const EMPTY: ZoneEdgePayload = {
  as_of: '2026-09-03T15:42:07-04:00', in_session: true,
  params: { edge_pct: 1.0, broke_max_pct: 3.0 },
  breaking: [], near_demand: [], track: {},
};

/* Routes by URL: the board's call gets the fixture; /notifications/recent (the
 * 🔔 alerted-today chip, 2026-09-05) gets `alerts` — empty by default so the
 * older cases describe a board nobody's phone has heard about; anything else
 * (the watchlist store behind TickerLink) gets a harmless empty body. */
function stubFetch(zoneEdge: unknown, alerts: unknown = { rows: [] }) {
  const fn = vi.fn(async (url: string) => {
    if (String(url).includes('/supply-demand/zone-edge')) {
      return { ok: true, status: 200, json: async () => zoneEdge } as Response;
    }
    if (String(url).includes('/notifications/recent')) {
      return { ok: true, status: 200, json: async () => alerts } as Response;
    }
    return { ok: true, status: 200, json: async () => ({ rows: [] }) } as Response;
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}

const zoneEdgeCalls = (fn: ReturnType<typeof vi.fn>) =>
  fn.mock.calls.filter((c) => String(c[0]).includes('/supply-demand/zone-edge')).length;

const draw = (props: { mode: 'both' | 'breaking'; compact?: boolean }) =>
  render(<MemoryRouter><ZoneEdgeBoard {...props} /></MemoryRouter>);

beforeEach(() => { vi.restoreAllMocks(); _resetAlertHistoryCache(); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('ZoneEdgeBoard — both sections from a live payload', () => {
  it('renders breaking + near-demand rows with their tags, pills and reads', async () => {
    // The fixture is stamped 15:42; pin the clock a minute later so the header
    // reads live (the stale rule is pinned in its own describe below).
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-09-03T15:43:00-04:00'));
    stubFetch(FIX);
    draw({ mode: 'both' });

    expect(await screen.findByText('as of 15:42 ET · refreshes every minute')).toBeInTheDocument();

    // 🚀 side: broke pill + new-highs tag on NVDA, distance line on ANET.
    expect(screen.getByText('broke +1.2%')).toBeInTheDocument();
    expect(screen.getByText('🏁 new highs')).toBeInTheDocument();
    expect(screen.getByText('0.7% under $127.5–129.3')).toBeInTheDocument();
    expect(screen.getByText('clear above')).toBeInTheDocument();
    expect(screen.getByText('2 supply above')).toBeInTheDocument();
    expect(screen.getByText(/52w \$183\.5 \(-1\.3%\)/)).toBeInTheDocument();
    expect(screen.getByText(/52w \$140\.1 \(\+9\.1%\)/)).toBeInTheDocument();
    expect(screen.getByText('since 10:12')).toBeInTheDocument();
    expect(screen.getByText('$4.4T')).toBeInTheDocument();

    // 🧲 side: arrival vs resident, role pill, in-band vs distance line. The
    // help line names both words in <em>; the pills are <span>.
    expect(screen.getByText('arrival', { selector: 'span' })).toBeInTheDocument();
    expect(screen.getByText('resident', { selector: 'span' })).toBeInTheDocument();
    expect(screen.getByText('broken supply', { selector: 'span' })).toBeInTheDocument();
    expect(screen.getByText('in $162–168')).toBeInTheDocument();
    expect(screen.getByText('0.8% above $95–100')).toBeInTheDocument();

    // Sparkline reads: ANET's distance is falling → closing in; TJX's is
    // rising → backing off; NVDA already broke and is extending the break.
    expect(screen.getByText('closing in')).toBeInTheDocument();
    expect(screen.getByText('backing off')).toBeInTheDocument();
    expect(screen.getByText('extending')).toBeInTheDocument();
    // NEGATIVE: a broke row must never read "closing in".
    expect(screen.getAllByText('closing in')).toHaveLength(1);

    // Three names carry a track → three sparklines; NTAP has none → no SVG.
    expect(screen.getAllByTestId('zone-edge-spark')).toHaveLength(3);

    // Ticker links land on the Supply / Demand tab with the Demand board as source.
    const link = screen.getByRole('link', { name: /NVDA/ });
    expect(link.getAttribute('href')).toMatch(/\/sepa\/NVDA\?.*tab=supply/);
    expect(link.getAttribute('href')).toMatch(/from=supply-demand/);
    expect(screen.getByText('Decision support, not advice.')).toBeInTheDocument();
  });

  it('mode="breaking" hides the near-demand section and, compact, the help + disclaimer', async () => {
    stubFetch(FIX);
    draw({ mode: 'breaking', compact: true });

    expect(await screen.findByText('broke +1.2%')).toBeInTheDocument();
    // NEGATIVE: nothing from the demand side leaks onto the Deep Demand tab.
    expect(screen.queryByText(/Near demand/)).not.toBeInTheDocument();
    expect(screen.queryByText('NTAP')).not.toBeInTheDocument();
    expect(screen.queryByText('arrival')).not.toBeInTheDocument();
    expect(screen.queryByText('Decision support, not advice.')).not.toBeInTheDocument();
    expect(screen.queryByText(/phone push wants/)).not.toBeInTheDocument();
  });

  it('empty sections say a real answer, never blank', async () => {
    stubFetch(EMPTY);
    draw({ mode: 'both' });

    expect(await screen.findByText('nothing within 1% of breaking its last supply band right now')).toBeInTheDocument();
    expect(screen.getByText('nothing inside or within 1% above a demand band right now')).toBeInTheDocument();
    expect(screen.queryAllByTestId('zone-edge-row')).toHaveLength(0);
  });

  it('as_of null → "no pass yet today"; in_session false → "market closed — last pass HH:MM"', async () => {
    stubFetch({ as_of: null, in_session: false, breaking: [], near_demand: [], track: {}, reason: 'no pass yet' });
    const first = draw({ mode: 'both' });
    expect(await screen.findByText('no pass yet today')).toBeInTheDocument();
    first.unmount();

    stubFetch({ ...EMPTY, as_of: '2026-09-03T16:00:12-04:00', in_session: false });
    draw({ mode: 'both' });
    expect(await screen.findByText('market closed — last pass 16:00')).toBeInTheDocument();
    // NEGATIVE: the live wording must not show after the close.
    expect(screen.queryByText(/refreshes every minute/)).not.toBeInTheDocument();
  });

  it('a pass stored on ANOTHER day says so, never "market closed" (2026-09-05)', async () => {
    // zone_edge.api_payload: the doc date != today -> in_session false plus this reason.
    stubFetch({ ...EMPTY, as_of: '2026-09-04T16:00:12-04:00', in_session: false,
                reason: 'last pass 2026-09-04; no pass yet today' });
    draw({ mode: 'both' });
    expect(await screen.findByText('last pass 2026-09-04; no pass yet today (16:00 ET)')).toBeInTheDocument();
    // NEGATIVE: neither the closed wording nor the live wording.
    expect(screen.queryByText(/market closed/)).not.toBeInTheDocument();
    expect(screen.queryByText(/refreshes every minute/)).not.toBeInTheDocument();
  });

  it('a cold zone store is named, not hidden behind "no pass yet today"', async () => {
    stubFetch({ as_of: null, in_session: true, breaking: [], near_demand: [], track: {},
                reason: 'zone store empty for today' });
    draw({ mode: 'both' });
    expect(await screen.findByText('no pass yet today — zone store empty for today')).toBeInTheDocument();
  });

  it('survives a payload with no arrays at all (older backend / foreign stub)', async () => {
    // Chart Maps' test stub routes by ?tab= and hands this board a VCP board.
    stubFetch({ tab: 'vcp', count: 1, tiles: [{ symbol: 'AVGO' }] });
    draw({ mode: 'both' });
    expect(await screen.findByText('no pass yet today')).toBeInTheDocument();
    expect(screen.getByText(/nothing within 1% of breaking/)).toBeInTheDocument();
    expect(screen.queryByText('AVGO')).not.toBeInTheDocument();
  });

  it('shows the failure instead of an empty board when the API is down', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503 } as Response)));
    draw({ mode: 'both' });
    expect(await screen.findByText(/zone edge unavailable — HTTP 503/)).toBeInTheDocument();
    // NEGATIVE: with no payload the "nothing within 1% …" real answer must NOT
    // show — it would read as a quiet tape when the truth is "unknown".
    expect(screen.queryByText(/nothing within 1% of breaking/)).not.toBeInTheDocument();
    expect(screen.queryByText(/nothing inside or within/)).not.toBeInTheDocument();
    expect(screen.queryAllByTestId('zone-edge-row')).toHaveLength(0);
  });

  it('keeps the last good list on screen through a failed refresh, and says so', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let n = 0;
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (!String(url).includes('/supply-demand/zone-edge')) {
        return { ok: true, status: 200, json: async () => ({ rows: [] }) } as Response;
      }
      n += 1;
      return n === 1
        ? ({ ok: true, status: 200, json: async () => FIX } as Response)
        : ({ ok: false, status: 503 } as Response);
    }));
    draw({ mode: 'both' });
    expect(await screen.findByText('broke +1.2%')).toBeInTheDocument();

    await act(async () => { await vi.advanceTimersByTimeAsync(REFRESH_MS + 50); });
    expect(n).toBe(2);
    // The rows survive; the header carries the failure next to the stamp.
    expect(screen.getByText('broke +1.2%')).toBeInTheDocument();
    expect(screen.getByText(/refresh failed: HTTP 503/)).toBeInTheDocument();
    expect(screen.queryByText(/zone edge unavailable/)).not.toBeInTheDocument();
  });

  it('a null body lands as "no pass yet today", not a permanent "loading…"', async () => {
    stubFetch(null);
    draw({ mode: 'both' });
    expect(await screen.findByText('no pass yet today')).toBeInTheDocument();
    expect(screen.queryByText('loading…')).not.toBeInTheDocument();
  });

  it('drops a null track point instead of plotting it', async () => {
    const track = {
      ...FIX.track,
      'supply:ANET': [['15:38', 1.4], ['15:39', null], ['15:40', 1.0], ['15:41', 0.8], ['15:42', 0.7]],
    } as unknown as ZoneEdgePayload['track'];
    stubFetch({ ...FIX, track });
    draw({ mode: 'breaking', compact: true });
    expect(await screen.findByText('broke +1.2%')).toBeInTheDocument();
    for (const svg of screen.getAllByTestId('zone-edge-spark')) {
      const pts = svg.querySelector('polyline')?.getAttribute('points') ?? '';
      expect(pts).not.toMatch(/NaN/);
      expect(pts.split(' ')).toHaveLength(svg === screen.getAllByTestId('zone-edge-spark')[1] ? 4 : 5);
    }
  });
});

describe('ZoneEdgeBoard — a stalled cron must not read as live', () => {
  it('in session with a stamp older than STALE_AFTER_MIN → STALE, not "refreshes every minute"', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-09-03T15:50:00-04:00'));
    stubFetch({ ...EMPTY, as_of: '2026-09-03T15:10:00-04:00', in_session: true });
    draw({ mode: 'both' });
    expect(await screen.findByText('as of 15:10 ET · STALE — no pass for 40 min')).toBeInTheDocument();
    expect(screen.queryByText(/refreshes every minute/)).not.toBeInTheDocument();
  });

  it('a two-minute-old stamp in session is live (the normal cron + poll gap)', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-09-03T15:44:30-04:00'));
    stubFetch(FIX); // as_of 15:42:07
    draw({ mode: 'breaking', compact: true });
    expect(await screen.findByText('as of 15:42 ET · refreshes every minute')).toBeInTheDocument();
    expect(screen.queryByText(/STALE/)).not.toBeInTheDocument();
  });

  it('after the close an old stamp is just "market closed", never STALE', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-09-03T18:00:00-04:00'));
    stubFetch({ ...EMPTY, as_of: '2026-09-03T16:00:12-04:00', in_session: false });
    draw({ mode: 'both' });
    expect(await screen.findByText('market closed — last pass 16:00')).toBeInTheDocument();
    expect(screen.queryByText(/STALE/)).not.toBeInTheDocument();
  });

  it('ageMinutes: whole minutes from an offset ISO stamp; null when unparsable', () => {
    const now = Date.parse('2026-09-03T15:50:00-04:00');
    expect(ageMinutes('2026-09-03T15:10:00-04:00', now)).toBe(40);
    expect(ageMinutes('2026-09-03T15:49:30-04:00', now)).toBe(0);
    // A stamp from the future (clock skew) is 0, never negative.
    expect(ageMinutes('2026-09-03T15:51:00-04:00', now)).toBe(0);
    expect(ageMinutes(null, now)).toBeNull();
    expect(ageMinutes('not a date', now)).toBeNull();
    expect(STALE_AFTER_MIN).toBe(4);
  });
});

describe('ZoneEdgeBoard — the minute clock', () => {
  it('fetches on mount, once a minute while visible, and stops on unmount', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fn = stubFetch(EMPTY);
    const view = draw({ mode: 'both' });
    await waitFor(() => expect(zoneEdgeCalls(fn)).toBe(1));

    await act(async () => { await vi.advanceTimersByTimeAsync(REFRESH_MS + 50); });
    expect(zoneEdgeCalls(fn)).toBe(2);

    view.unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(3 * REFRESH_MS); });
    // NEGATIVE: an unmounted board must not keep polling.
    expect(zoneEdgeCalls(fn)).toBe(2);
  });

  it('skips the tick while the tab is hidden and resumes when visible', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fn = stubFetch(EMPTY);
    draw({ mode: 'both' });
    await waitFor(() => expect(zoneEdgeCalls(fn)).toBe(1));

    const vis = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden');
    await act(async () => { await vi.advanceTimersByTimeAsync(2 * REFRESH_MS + 50); });
    expect(zoneEdgeCalls(fn)).toBe(1);

    vis.mockReturnValue('visible');
    await act(async () => { await vi.advanceTimersByTimeAsync(REFRESH_MS + 50); });
    expect(zoneEdgeCalls(fn)).toBe(2);
    vis.mockRestore();
  });

  it('re-reads at once when the tab comes back into view', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fn = stubFetch(EMPTY);
    draw({ mode: 'both' });
    await waitFor(() => expect(zoneEdgeCalls(fn)).toBe(1));

    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
    await waitFor(() => expect(zoneEdgeCalls(fn)).toBe(2));
  });
});

describe('sparkRead — one word from the last 5 points', () => {
  const pts = (vals: number[]): TrackPoint[] => vals.map((v, i) => [`15:${String(i).padStart(2, '0')}`, v]);

  it('falling distance → closing in, rising → backing off', () => {
    expect(sparkRead(pts([1.4, 1.2, 1.0, 0.8, 0.7]))).toBe('closing in');
    expect(sparkRead(pts([0.4, 0.5, 0.6, 0.7, 0.8]))).toBe('backing off');
  });

  it('a move under FLAT_EPS over the window is flat', () => {
    expect(sparkRead(pts([0.70, 0.72, 0.69, 0.75, 0.74]))).toBe('flat');
    // exactly the threshold is NOT flat
    expect(sparkRead(pts([0.7, 0.7 + FLAT_EPS]))).toBe('backing off');
  });

  it('reads only the last READ_WINDOW points', () => {
    // 30 points climbing, then a 5-point drop: the read is the drop.
    const climb = Array.from({ length: 30 }, (_, i) => i * 0.1);
    const tail = [3.0, 2.8, 2.6, 2.4, 2.2];
    expect(sparkRead(pts([...climb, ...tail]))).toBe('closing in');
    expect(READ_WINDOW).toBe(5);
  });

  it('broke tier: falling (more negative) → extending, rising → fading', () => {
    expect(sparkRead(pts([-0.4, -0.6, -0.9, -1.0, -1.2]), 'broke')).toBe('extending');
    expect(sparkRead(pts([-1.2, -1.0, -0.9, -0.6, -0.4]), 'broke')).toBe('fading');
    // NEGATIVE: never the under-resistance words for a break.
    expect(sparkRead(pts([-0.4, -1.2]), 'broke')).not.toBe('closing in');
  });

  it('no read from fewer than two points or a non-numeric point', () => {
    expect(sparkRead(undefined)).toBeNull();
    expect(sparkRead([])).toBeNull();
    expect(sparkRead(pts([0.7]))).toBeNull();
    expect(sparkRead([['15:00', NaN], ['15:01', 0.5]])).toBeNull();
  });
});

describe('helpers', () => {
  it('hhmm takes the clock out of an ET ISO stamp without converting it', () => {
    expect(hhmm('2026-09-03T15:42:07-04:00')).toBe('15:42');
    expect(hhmm('2026-09-03T09:31:00-04:00')).toBe('09:31');
    expect(hhmm(null)).toBeNull();
    expect(hhmm('')).toBeNull();
    expect(hhmm('2026-09-03')).toBeNull();
  });

  it('capLabel matches the backend fmt_cap shape', () => {
    expect(capLabel(4.4e12)).toBe('$4.4T');
    expect(capLabel(1.6e11)).toBe('$160.0B');
    expect(capLabel(8.5e8)).toBe('$850M');
    expect(capLabel(null)).toBeNull();
    expect(capLabel(0)).toBeNull();
  });
});

/* ── 🔔 alerted-today chip (Ajay 2026-09-05) ─────────────────────────────────
 * "Would it be the same list of stocks.." — this board lists every band at any
 * cap; the phone got only the names that passed the gate. The chip marks the
 * overlap on the row itself, in ET, and links to /alerts for that ticker. */

const ALERTED_NVDA = {
  rows: [{
    _id: 'p1', ts: Date.parse('2026-09-03T14:12:00Z') / 1000, ts_iso: '2026-09-03T14:12:00+00:00',
    kind: 'supply_break_alert', ticker: 'nvda', title: '🚀 NVDA breaking $179', body: 'Through the last supply band.',
    url: '/sepa/NVDA?tab=supply', source: 'push', sent: 2, failed: 0, total: 2,
  }],
};

describe('ZoneEdgeBoard — 🔔 alerted-today chip (Ajay 2026-09-05)', () => {
  it('a row whose name pushed today wears the chip with the push\'s ET time, linking to /alerts', async () => {
    stubFetch(FIX, ALERTED_NVDA);
    draw({ mode: 'both' });
    const chip = await screen.findByTestId('alerted-today-chip');
    // 14:12Z is 10:12 EDT; the ticker matched case-insensitively.
    expect(chip).toHaveTextContent('🔔 alerted 10:12 ET');
    expect(chip.getAttribute('href')).toBe('/alerts?ticker=NVDA&days=1');
    // NEGATIVE: ANET, NTAP and TJX did not push — one chip on the board.
    expect(screen.getAllByTestId('alerted-today-chip')).toHaveLength(1);
    expect(screen.getByText('broke +1.2%').closest('[data-testid="zone-edge-row"]')?.contains(chip)).toBe(true);
  });

  it('NEGATIVE: no chip when the ticker is absent from today\'s pushes', async () => {
    stubFetch(FIX, { rows: [{ ...ALERTED_NVDA.rows[0], ticker: 'AAPL' }] });
    draw({ mode: 'both' });
    expect(await screen.findByText('broke +1.2%')).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByTestId('alerted-today-chip')).not.toBeInTheDocument();
  });

  it('NEGATIVE: a failed alerts read leaves the rows bare, the board intact', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (String(url).includes('/supply-demand/zone-edge')) return { ok: true, status: 200, json: async () => FIX } as Response;
      if (String(url).includes('/notifications/recent')) return { ok: false, status: 503 } as Response;
      return { ok: true, status: 200, json: async () => ({ rows: [] }) } as Response;
    }));
    draw({ mode: 'both' });
    expect(await screen.findByText('broke +1.2%')).toBeInTheDocument();
    expect(screen.getAllByTestId('zone-edge-row')).toHaveLength(4);
    expect(screen.queryByTestId('alerted-today-chip')).not.toBeInTheDocument();
  });
});
