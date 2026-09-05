/* Catalysts — inside Chart Maps since 2026-09-05 (Ajay: "also move catalyst
 * tab in to Chart maps ... for catalyst same deal make sure you sort stocks by
 * bigger gaps in to supply like EOSE stock and CLYM").
 *
 * Locks the three things that would quietly mislead if they broke: the default
 * order (open sky first, then the biggest gap, pending coverage LAST — never a
 * blank that reads as "no supply overhead"), the room stat text on the card,
 * and the old /catalysts deep links (push taps to ?tab=promo) landing on the
 * new home with their sub-tab intact. The scan and the bounce-room hooks are
 * mocked — this is a render test of the page, not of the fetchers. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

const H = vi.hoisted(() => {
  const mk = (ticker: string, composite: number) => ({
    ticker, company_name: `${ticker} Inc`, price: 12.34, prev_close: 11.0, change_pct: 12.2,
    volume: 1_000_000, dollar_volume: 12_340_000, market_cap: 450e6, volume_surge_ratio: 3.2,
    chatter: {
      ticker,
      stocktwits: { n_messages: 0, n_24h: 0, sentiment_pct_bullish: null, n_bullish: 0, n_bearish: 0, blurbs: [] },
      reddit: { n_posts_24h: 0, n_posts_7d: 0, top: null, subreddits: [] },
      velocity_per_hour: 0, sample_blurbs: [],
    },
    evidence: {
      ticker,
      news: { n_total: 0, n_bullish: 0, n_bearish: 0, n_neutral: 0, bullish: [], bearish: [], neutral: [] },
      sec_filings: { n_total: 0, items: [], has_8k: false, has_offering: false, has_13d: false, has_insider_trade: false },
    },
    chatter_score: 40, evidence_score: 50, composite_score: composite, quadrant: 'REAL',
    review: { catalyst_summary: 'test catalyst', bull_pull: null, bear_pull: null, evidence_grade: 'B', is_pump_warning: false },
  });
  // Composite order is PEND > CLYM > EOSE on purpose — the room sort must
  // invert it (EOSE open sky, CLYM +17%, PEND pending).
  const SCAN = {
    as_of: '2026-09-05T13:00:00-04:00',
    market: { state: 'open', is_live: true, label: 'open', next_event: '' },
    candidates: [mk('PEND', 90), mk('CLYM', 80), mk('EOSE', 10)],
    by_quadrant: { REAL: ['PEND', 'CLYM', 'EOSE'], PUMP_RISK: [], OVERLOOKED: [], DEAD: [] },
    n_total: 3, n_real: 3, n_pump_risk: 0, n_overlooked: 0, n_dead: 0,
    filters: { max_share_price: 20, max_market_cap: 2e9, min_abs_change_pct: 8 },
    timing: { scan_sec: 1, enrich_sec: 1, review_sec: 1, total_sec: 3 },
    cached: false, cache_age_sec: 0,
  };
  const rows = {
    EOSE: { symbol: 'EOSE', coverage: 'store', print: 12.34, fresh: true, bounce: null,
            room: { state: 'CLEAR', room_pct: null, atr_days: null, band: null, at_highs: true } },
    CLYM: { symbol: 'CLYM', coverage: 'ondemand', print: 15.57, fresh: false, bounce: null,
            room: { state: 'ROOM', room_pct: 17.0, atr_days: 3.1,
                    band: { kind: 'supply', lo: 18.22, hi: 18.44, touches: 3 }, at_highs: false } },
    PEND: { symbol: 'PEND', coverage: 'pending' },
  };
  const payload = {
    as_of: '2026-09-05T13:02:11-04:00', in_session: true, store_date: '2026-09-04', params: {},
    rows, requested: 3, covered: 2, pending: 1, unavailable: 0, disclaimer: 'Not advice.',
  };
  const map = new Map(Object.entries(rows));
  return { SCAN, map, payload };
});

vi.mock('../hooks/useCatalysts', () => ({
  useCatalystScan: () => ({ data: H.SCAN, loading: false, refreshing: false, refetch: vi.fn(), forceRefresh: vi.fn() }),
  useVolumeAlerts: () => ({ alerts: [], session_date: undefined }),
  useDeepDive: () => ({ data: null, loading: false }),
  usePremarketScan: () => ({ data: null, loading: false, refetch: vi.fn() }),
  useInsiderSignal: () => ({ data: null, loading: false }),
  useCatalystCalendar: () => ({ data: null, loading: false, refetch: vi.fn(), forceRefresh: vi.fn() }),
  useCatalystTimeline: () => ({ data: null, loading: false, refetch: vi.fn() }),
  useCatalystStale: () => ({ data: null, loading: false, refetch: vi.fn() }),
  useCatalystMultiDayAccumulators: () => ({ data: null, loading: false, refetch: vi.fn() }),
  usePredictions: () => ({ data: null, loading: false, refreshing: false, refetch: vi.fn(), forceRefresh: vi.fn() }),
  useFrenzyRadar: () => ({ data: null, loading: false, refetch: vi.fn() }),
}));

vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: H.map, payload: H.payload, loading: false, error: null, pending: 1 }),
}));

vi.mock('../components/MarketGaugeBanner', () => ({
  MarketGaugeBanner: () => <div data-testid="gauge-banner" />,
}));

/* Access features: `catalysts` and `chart-maps` are two separate opt-in
 * grants (backend/access/store.py). Mutable so one test can take Chart Maps
 * away and another can hold the fetch "in flight". */
const FEATS = vi.hoisted(() => ({ loaded: true, set: new Set(['catalysts', 'chart-maps']) }));
vi.mock('../hooks/useMyFeatures', () => ({
  useMyFeatures: () => ({ loaded: FEATS.loaded, features: FEATS.set, catalog: [], email: null }),
}));

import { CatalystsBoard, CatalystsPage } from './Catalysts';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })));
  FEATS.loaded = true;
  FEATS.set = new Set(['catalysts', 'chart-maps']);
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

const tickers = () => screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent);

const drawEmbedded = (search = '?tab=catalysts&sub=now') =>
  render(<MemoryRouter initialEntries={[`/chart-maps${search}`]}><CatalystsBoard embedded /></MemoryRouter>);

describe('CatalystsBoard — room to supply (Ajay 2026-09-05)', () => {
  it('defaults to the room sort: open sky first, then the biggest gap, pending LAST', () => {
    drawEmbedded();
    expect(screen.getByRole('button', { name: 'room to supply' })).toHaveClass('is-active');
    // Composite would be PEND, CLYM, EOSE — room inverts it.
    expect(tickers()).toEqual(['EOSE', 'CLYM', 'PEND']);
  });

  it('prints the room stat on each card and says "room pending" instead of hiding it', () => {
    drawEmbedded();
    expect(screen.getByText('open sky · 52w highs')).toBeInTheDocument();
    expect(screen.getByText('+17% room → $18.22 · 3.1 ATR')).toBeInTheDocument();
    expect(screen.getByText('room pending')).toBeInTheDocument();
    // NEGATIVE: nothing on this board is bouncing, so no 🪃 label anywhere.
    expect(screen.queryByText(/🪃 \+/)).not.toBeInTheDocument();
    // Coverage is spelled out under the sort buttons.
    expect(screen.getByText(/2 of 3 covered · 1 pending · bands 2026-09-04/)).toBeInTheDocument();
  });

  it('the composite sort is still one click away and restores the scanner order', () => {
    drawEmbedded();
    fireEvent.click(screen.getByRole('button', { name: 'composite' }));
    expect(tickers()).toEqual(['PEND', 'CLYM', 'EOSE']);
  });

  it('embedded: no page header, no gauge banner, no cm-page wrapper (the parent is one)', () => {
    const { container } = drawEmbedded();
    expect(screen.queryByText('Tiny Stocks in Motion')).not.toBeInTheDocument();
    expect(screen.queryByTestId('gauge-banner')).not.toBeInTheDocument();
    const root = container.firstElementChild as HTMLElement;
    expect(root).toHaveClass('cat-page');
    expect(root).toHaveClass('cat-page--embedded');
    expect(root).not.toHaveClass('cm-page');
  });

  it('embedded reads the sub-tab from `sub`, not `tab` (negative — `tab` is Chart Maps\' own)', () => {
    // ?tab=now would have selected the Now sub-tab on the old page. Embedded,
    // `tab` belongs to Chart Maps, so this lands on the default Predictions
    // sub-tab and draws no candidate cards.
    drawEmbedded('?tab=now');
    expect(screen.queryAllByRole('heading', { level: 3 })).toHaveLength(0);
    expect(screen.getByRole('button', { name: /Predictions/ })).toHaveClass('is-active');
  });

  it('standalone keeps the full page chrome and reads `tab`', () => {
    render(<MemoryRouter initialEntries={['/catalysts?tab=now']}><CatalystsBoard /></MemoryRouter>);
    expect(screen.getByText('Tiny Stocks in Motion')).toBeInTheDocument();
    expect(screen.getByTestId('gauge-banner')).toBeInTheDocument();
    expect(tickers()).toEqual(['EOSE', 'CLYM', 'PEND']);
  });
});

function Loc() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname + l.search}</div>;
}

const drawRedirect = (from: string) => render(
  <MemoryRouter initialEntries={[from]}>
    <Routes>
      <Route path="/catalysts" element={<CatalystsPage />} />
      <Route path="*" element={<Loc />} />
    </Routes>
  </MemoryRouter>,
);

describe('CatalystsPage — the old route redirects to Chart Maps', () => {
  it('/catalysts?tab=promo → /chart-maps?tab=catalysts&sub=promo (push taps keep their sub-tab)', () => {
    drawRedirect('/catalysts?tab=promo');
    expect(screen.getByTestId('loc')).toHaveTextContent('/chart-maps?tab=catalysts&sub=promo');
  });

  it('/catalysts with no tab → /chart-maps?tab=catalysts, no dangling &sub= (negative)', () => {
    drawRedirect('/catalysts');
    expect(screen.getByTestId('loc')).toHaveTextContent('/chart-maps?tab=catalysts');
    expect(screen.getByTestId('loc').textContent).not.toMatch(/sub=/);
  });

  it('a user WITHOUT the chart-maps feature keeps the board standalone — no redirect onto a page that would bounce them to "/"', () => {
    FEATS.set = new Set(['catalysts']);
    drawRedirect('/catalysts?tab=now');
    expect(screen.queryByTestId('loc')).not.toBeInTheDocument();
    expect(screen.getByText('Tiny Stocks in Motion')).toBeInTheDocument();     // full page chrome
    expect(screen.getByTestId('gauge-banner')).toBeInTheDocument();
    expect(tickers()).toEqual(['EOSE', 'CLYM', 'PEND']);                       // `tab=now` still read
  });

  it('decides only after the features fetch: while loading it renders a loader, not a redirect (negative)', () => {
    FEATS.loaded = false;
    FEATS.set = new Set();
    drawRedirect('/catalysts?tab=promo');
    expect(screen.queryByTestId('loc')).not.toBeInTheDocument();
    expect(screen.getByText('Loading…')).toBeInTheDocument();
    expect(screen.queryByText('Tiny Stocks in Motion')).not.toBeInTheDocument();
  });
});
