/* DemandReentryPanel — universe-provenance banners + the bounce·room sort.
 *
 * The panel claims "S&P 500" in its heading, its button, and its empty state.
 * These tests lock the two ways that claim can be false, because each one
 * degrades differently and must be reported differently:
 *
 *   1. WRONG UNIVERSE — fetch_sp500() fell through to the 158-name curated
 *      list. Loud red error; the names are not the S&P 500 at all.
 *   2. STALE UNIVERSE (the 2026-08-13 hole) — the real constituents, but
 *      frozen on the day the live fetch broke. `universe_is_sp500` stays true,
 *      so case 1's banner never fires and the list aged 76 days in silence.
 *
 * 2026-09-05 (Ajay: "for in demand Make sure you sort stocks by bouncing off
 * of demand zone and have big gap in to supply"): the default sort is the
 * shared bounce·room rule from lib/bounceRoom.ts. Locked below: a bouncing
 * +17%-room row outranks a non-bouncing row with a better R:R, a row whose
 * zone coverage is still pending sorts LAST and says so, and R:R is still one
 * click away in the sort menu.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DemandReentryPanel } from './DemandReentryPanel';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

type Overrides = Record<string, unknown>;

function payload(over: Overrides = {}) {
  return {
    rows: [],
    n: 0,
    scanned: 503,
    universe: 503,
    universe_note: 'S&P 500 constituents (503 names)',
    universe_is_sp500: true,
    universe_stale_days: null,
    universe_source: 'wikipedia',
    took_sec: 12.3,
    as_of: '2026-08-13T12:00:00+00:00',
    cached: false,
    disclaimer: 'Not advice.',
    ...over,
  };
}

/* The panel now mounts ZoneEdgeBoard, which makes its own call to
 * /supply-demand/zone-edge on mount, and (2026-09-05) POSTs its row symbols to
 * /supply-demand/bounce-room. The stub routes by URL so each call gets its own
 * shape — one stub answering everything with the same body would hand the
 * board a demand-reentry payload and the panel a zone-edge one, depending on
 * order. */
const ZONE_EDGE_EMPTY = {
  as_of: null, in_session: false, breaking: [], near_demand: [], track: {}, reason: 'no pass yet',
};

const BOUNCE_ROOM_EMPTY = {
  as_of: null, in_session: false, store_date: null, params: {},
  rows: {}, requested: 0, covered: 0, pending: 0, unavailable: 0, disclaimer: 'Not advice.',
};

function routed(body: () => unknown, bounceRoom: () => unknown = () => BOUNCE_ROOM_EMPTY) {
  return vi.fn(async (url: string) => {
    if (String(url).includes('/supply-demand/zone-edge')) {
      return { ok: true, json: async () => ZONE_EDGE_EMPTY };
    }
    if (String(url).includes('/supply-demand/bounce-room')) {
      return { ok: true, json: async () => bounceRoom() };
    }
    return { ok: true, json: async () => body() };
  });
}

function mockFetch(over: Overrides = {}, bounceRoom?: () => unknown) {
  const fn = routed(() => payload(over), bounceRoom);
  vi.stubGlobal('fetch', fn);
  return fn;
}

beforeEach(() => { vi.restoreAllMocks(); _resetBounceRoomCache(); });
afterEach(() => vi.unstubAllGlobals());

describe('DemandReentryPanel — universe provenance', () => {
  it('says nothing about provenance when the list is fresh', async () => {
    mockFetch();
    render(<DemandReentryPanel />);

    await waitFor(() => expect(screen.getByText(/503 scanned/)).toBeInTheDocument());
    // NEGATIVE: neither banner may fire on the happy path.
    expect(screen.queryByText(/NOT the full universe/)).not.toBeInTheDocument();
    expect(screen.queryByText(/days old/)).not.toBeInTheDocument();
  });

  it('warns loudly when the scan fell through to the curated list', async () => {
    mockFetch({
      universe_is_sp500: false,
      universe_source: 'curated',
      universe: 158,
      scanned: 158,
      universe_note: 'S&P 500 unavailable — scanned the curated list instead',
    });
    render(<DemandReentryPanel />);

    await waitFor(() =>
      expect(screen.getByText(/NOT the full universe/)).toBeInTheDocument());
  });

  it('reports a stale-but-real constituent list with its age', async () => {
    /* THE REGRESSION: universe_is_sp500 is TRUE here — these really are the
     * S&P 500 names — so the curated-fallback banner correctly stays silent.
     * Without its own banner the page said nothing at all while the list drifted. */
    mockFetch({
      universe_is_sp500: true,
      universe_source: 'stale-cache',
      universe_stale_days: 76,
    });
    render(<DemandReentryPanel />);

    await waitFor(() =>
      expect(screen.getByText(/76 days old/)).toBeInTheDocument());
    expect(screen.getByText(/live S&P 500 fetch is failing/)).toBeInTheDocument();
    // It must NOT masquerade as the wrong-universe error — different failure.
    expect(screen.queryByText(/NOT the full universe/)).not.toBeInTheDocument();
  });

  it('keeps a mildly stale list muted and escalates a badly stale one', async () => {
    mockFetch({ universe_source: 'stale-cache', universe_stale_days: 40 });
    const mild = render(<DemandReentryPanel />);
    await waitFor(() => expect(screen.getByText(/40 days old/)).toBeInTheDocument());
    expect(screen.getByText(/40 days old/).closest('div'))
      .not.toHaveClass('sepa-err');
    mild.unmount();

    mockFetch({ universe_source: 'stale-cache', universe_stale_days: 200 });
    render(<DemandReentryPanel />);
    await waitFor(() => expect(screen.getByText(/200 days old/)).toBeInTheDocument());
    expect(screen.getByText(/200 days old/).closest('div')).toHaveClass('sepa-err');
  });

  it('survives a payload from an older backend with no provenance fields', async () => {
    /* NEGATIVE: the API and frontend deploy separately. A payload predating
     * universe_stale_days must render normally, not crash or show "undefined
     * days old". */
    const fn = routed(() => {
      const p = payload() as Record<string, unknown>;
      delete p.universe_stale_days;
      delete p.universe_source;
      return p;
    });
    vi.stubGlobal('fetch', fn);
    render(<DemandReentryPanel />);

    await waitFor(() => expect(screen.getByText(/503 scanned/)).toBeInTheDocument());
    expect(screen.queryByText(/days old/)).not.toBeInTheDocument();
  });

  it('row symbol links open the SEPA page on the Supply / Demand tab (2026-09-03), never the old Setup tab', async () => {
    const zone = { kind: 'demand', lo: 95, hi: 100, mid: 97.5, touches: 3, strength: 60, in_price: true } as any;
    mockFetch({ n: 1, rows: [{
      symbol: 'TJX', name: 'TJX Cos', last_price: 98.5, supply_zones: [], demand_zones: [zone],
      nearest_resistance: null, nearest_support: zone, in_demand_band: true, is_reentry: true,
      fell_from_pct: 9.2, bars_since_above: 4, trend_ok: true, zone_quality_ok: true,
      entry_zone: zone, plan: null,
    } as any] });
    render(<MemoryRouter><DemandReentryPanel /></MemoryRouter>);
    const link = await waitFor(() => screen.getByRole('link', { name: /TJX/ }));
    expect(link.getAttribute('href')).toMatch(/\/sepa\/TJX\?.*tab=supply/);
    expect(link.getAttribute('href')).not.toMatch(/tab=setup/);
  });
});

/* ── the bounce·room default sort (Ajay 2026-09-05) ─────────────────────────── */

const zone = { kind: 'demand', lo: 95, hi: 100, mid: 97.5, touches: 3, strength: 60, in_price: true } as any;
const plan = (rr: number) => ({
  entry_low: 96, entry_high: 100, entry_ref: 98, stop: 94, risk_pct: 4.1,
  target: 98 + rr * 4, reward_pct: rr * 4.1, rr, risk_exceeds_max: false, max_stop_pct: 10,
}) as any;
const row = (symbol: string, rr: number) => ({
  symbol, name: `${symbol} Co`, last_price: 98.5, supply_zones: [], demand_zones: [zone],
  nearest_resistance: null, nearest_support: zone, in_demand_band: true, is_reentry: true,
  fell_from_pct: 9.2, bars_since_above: 4, trend_ok: true, zone_quality_ok: true,
  entry_zone: zone, plan: plan(rr),
}) as any;

/* TJX has the best R:R (3.0) but no bounce and a supply band 4% overhead.
 * EOSE bounced +4.2% off a demand band with +17% room to its first supply.
 * PEND is still being built on the server (coverage pending). */
const BOUNCE_ROOM_THREE = {
  as_of: '2026-09-05T13:02:11-04:00', in_session: true, store_date: '2026-09-04',
  params: { touch_tol_pct: 1.0, bounce_min_pct: 3.0, lookback_sessions: 5, near_pct: 2.0 },
  rows: {
    TJX: { symbol: 'TJX', coverage: 'store', print: 98.5, fresh: true, bounce: null,
           room: { state: 'ROOM', room_pct: 4.0, atr_days: 1.6,
                   band: { kind: 'supply', lo: 102.44, hi: 104.1, touches: 2 }, at_highs: false } },
    EOSE: { symbol: 'EOSE', coverage: 'store', print: 15.57, fresh: true,
            bounce: { band: { kind: 'demand', lo: 14.6, hi: 14.95, touches: 3, strength: 62 }, role: 'demand',
                      touch_low: 14.94, touch_date: '2026-09-05', sessions_ago: 0,
                      bounce_pct: 4.2, floor_pct: 3.0, strong: false, atr_x: 1.1 },
            room: { state: 'ROOM', room_pct: 17.0, atr_days: 3.1,
                    band: { kind: 'supply', lo: 18.22, hi: 18.44, touches: 3 }, at_highs: false } },
    PEND: { symbol: 'PEND', coverage: 'pending' },
  },
  requested: 3, covered: 2, pending: 1, unavailable: 0, disclaimer: 'Not advice.',
};

const tickerOrder = () =>
  screen.getAllByRole('link')
    .map((l) => l.textContent ?? '')
    .map((t) => ['TJX', 'EOSE', 'PEND'].find((s) => t.includes(s)))
    .filter((s): s is string => Boolean(s));

describe('DemandReentryPanel — bounce · room sort (Ajay 2026-09-05)', () => {
  it('defaults to the 🪃 bounce · room sort with R:R still in the menu', async () => {
    mockFetch({ n: 3, rows: [row('TJX', 3.0), row('EOSE', 1.2), row('PEND', 2.0)] }, () => BOUNCE_ROOM_THREE);
    render(<MemoryRouter><DemandReentryPanel /></MemoryRouter>);
    const select = await waitFor(() => screen.getByLabelText('Sort by') as HTMLSelectElement);
    expect(select.value).toBe('bounce_room');
    expect(select.options[0].textContent).toMatch(/🪃 Bouncing · room to supply \(default\)/);
    expect(Array.from(select.options).some((o) => o.value === 'rr' && o.textContent === '🎯 R:R')).toBe(true);
  });

  it('puts a bouncing +17%-room row above a non-bouncing row with a better R:R', async () => {
    mockFetch({ n: 2, rows: [row('TJX', 3.0), row('EOSE', 1.2)] }, () => BOUNCE_ROOM_THREE);
    render(<MemoryRouter><DemandReentryPanel /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('🪃 +4.2% off $14.94 · today')).toBeInTheDocument());
    expect(tickerOrder()).toEqual(['EOSE', 'TJX']);
    expect(screen.getByText(/\+17% room → \$18.22 · 3.1 ATR/)).toBeInTheDocument();
    expect(screen.getByText(/\+4.0% room → \$102 · 1.6 ATR/)).toBeInTheDocument();
    // Coverage is spelled out next to the count.
    expect(screen.getByText(/2 of 3 covered · 1 pending · bands 2026-09-04/)).toBeInTheDocument();
  });

  it('a row whose zone coverage is still pending sorts LAST and says "room pending"', async () => {
    mockFetch({ n: 3, rows: [row('PEND', 5.0), row('TJX', 3.0), row('EOSE', 1.2)] }, () => BOUNCE_ROOM_THREE);
    render(<MemoryRouter><DemandReentryPanel /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('room pending')).toBeInTheDocument());
    // PEND has the best R:R of the three — irrelevant under this sort.
    expect(tickerOrder()).toEqual(['EOSE', 'TJX', 'PEND']);
    // NEGATIVE: pending is not "no supply overhead" — no ROW may read as open
    // sky (anchored: the help blurb explains the phrase in running text).
    expect(screen.queryAllByText(/^open sky/)).toHaveLength(0);
  });

  it('switching the select back to R:R restores the R:R order', async () => {
    mockFetch({ n: 3, rows: [row('PEND', 5.0), row('TJX', 3.0), row('EOSE', 1.2)] }, () => BOUNCE_ROOM_THREE);
    render(<MemoryRouter><DemandReentryPanel /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('room pending')).toBeInTheDocument());
    expect(tickerOrder()).toEqual(['EOSE', 'TJX', 'PEND']);
    fireEvent.change(screen.getByLabelText('Sort by'), { target: { value: 'rr' } });
    expect(tickerOrder()).toEqual(['PEND', 'TJX', 'EOSE']);
  });

  it('with no bounce-room rows at all, the board still renders in symbol order (negative)', async () => {
    mockFetch({ n: 2, rows: [row('TJX', 3.0), row('EOSE', 1.2)] });
    render(<MemoryRouter><DemandReentryPanel /></MemoryRouter>);
    await waitFor(() => screen.getByRole('link', { name: /TJX/ }));
    expect(tickerOrder()).toEqual(['EOSE', 'TJX']);
    expect(screen.queryByText(/room pending/)).not.toBeInTheDocument();
    expect(screen.queryByText(/🪃 \+/)).not.toBeInTheDocument();
  });
});
