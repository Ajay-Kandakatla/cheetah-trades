/* Catalysts → Supply & Demand (Ajay 2026-09-25: "Can you help make all the
 * catalyst pages to be going to Ticker supply and demand please?").
 *
 * Every ticker on every Catalysts sub-tab — the name, the card around it, the
 * row it sits in — opens /sepa/SYM on the Supply & Demand tab, with the source
 * sub-tab riding along so ← Back returns to it. The deep-dive drawer those
 * clicks used to open is one 🔎 away and must NOT navigate.
 *
 * Href assertions, not only click assertions: the ticker is a real <a>, so
 * ⌘-click / middle-click / "copy link" must carry the tab too. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import type { MouseEvent as ReactMouseEvent } from 'react';

const D = vi.hoisted(() => {
  const cand = (ticker: string, composite: number) => ({
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
    review: { catalyst_summary: `${ticker} catalyst summary`, bull_pull: null, bear_pull: null, evidence_grade: 'B', is_pump_warning: false },
  });
  const SCAN = {
    as_of: '2026-09-25T13:00:00-04:00',
    market: { state: 'open', is_live: true, label: 'open', next_event: '' },
    candidates: [cand('EOSE', 90), cand('CLYM', 80)],
    by_quadrant: { REAL: ['EOSE', 'CLYM'], PUMP_RISK: [], OVERLOOKED: [], DEAD: [] },
    n_total: 2, n_real: 2, n_pump_risk: 0, n_overlooked: 0, n_dead: 0,
    filters: { max_share_price: 20, max_market_cap: 2e9, min_abs_change_pct: 8 },
    timing: { scan_sec: 1, enrich_sec: 1, review_sec: 1, total_sec: 3 },
    cached: false, cache_age_sec: 0,
  };
  const pred = (ticker: string) => ({
    ticker, company_name: `${ticker} Corp`, conviction_tier: 'HIGH', conviction_score: 72,
    price: 5.5, change_pct: 9.1, market_cap: 300e6, volume_surge_ratio: 2.4, quadrant: 'REAL',
    bull_thesis: 'bull', bear_thesis: 'bear', signals: [{ type: 'cmf_accum', weight: 10, detail: 'd' }],
    penalties: [], entry_zone: null,
  });
  const PRED = { predictions: [pred('PRDA'), pred('PRDB')], n_total: 2,
                 by_tier: { HIGH: 2, MEDIUM: 0, WATCH: 0, AVOID: 0 } };
  const frz = (ticker: string) => ({
    ticker, company_name: `${ticker} Ltd`, tier: 'SETUP', score: 55, price: 3.2, change_pct: 4.0,
    market_cap: 90e6, volume_surge_ratio: 2.0, float: 20e6, halts_today: null,
    signals: [{ type: 'quiet_volume_surge', weight: 12, detail: 'd' }],
  });
  const FRENZY = { candidates: [frz('FRZA')], n_total: 1,
                   by_tier: { IMMINENT: 0, SETUP: 1, EARLY: 0, QUIET: 0 },
                   snapshots_used: 3, lookback_sessions_indexed: 5, elapsed_sec: 1 };
  const PRE = {
    as_of: '2026-09-25T08:00:00-04:00',
    window: { in_window: true, label: 'pre', minutes_until_open: 90 },
    candidates: [{ ticker: 'PREA', company_name: 'PREA Co', price: 7.0, prev_close: 6.0,
                   change_pct: 16.6, volume: 250_000, market_cap: 200e6, sector: 'Tech' }],
    n_universe_scanned: 100, n_movers_found: 1, n_after_filter: 1,
  };
  const CAL = {
    timeline: [{ type: 'earnings', date: '2026-09-29', ticker: 'CALA', title: 'CALA Q3 earnings', url: null }],
    by_type: { earnings: [], fda: [], macro: [] },
    n_total: 1, days_window: 30, n_earnings: 1, n_fda: 0, n_macro: 0,
  };
  const TL = {
    n_snapshots: 3,
    events: [{
      at: '2026-09-25T11:00:00-04:00',
      entered: [{ ticker: 'TLEN', change_pct: 5.0 }], n_entered: 1,
      chatter_jumpers: [{ ticker: 'TLCH', delta: 12 }], n_chatter_jumps: 1,
      evidence_jumpers: [{ ticker: 'TLEV', delta: 8 }], n_evidence_jumps: 1,
      quadrant_transitions: [{ ticker: 'TLQD', from_quadrant: 'DEAD', to_quadrant: 'REAL' }], n_quadrant_transitions: 1,
      phase_transitions: [{ ticker: 'TLPH', from_phase: 'EARLY', to_phase: 'RUN' }], n_phase_transitions: 1,
      exited: [{ ticker: 'TLEX' }], n_exited: 1,
    }],
  };
  const stale = (ticker: string) => ({ ticker, hours_on_list: 4, change_pct: 3.1, composite_score: 60 });
  const STALE = { stable_winners: [stale('STWN')], stalled_chatter: [stale('STCH')], ambient_dead: [] };
  const MULTI = {
    n_with_strong_accum: 1, n_universe: 4, min_session_appearances: 3,
    accumulators: [{ ticker: 'MDAC', company_name: 'MDAC Inc', n_session_dates_seen: 4,
                     accumulation_score: 65, accumulation_label: 'strong', cmf: 0.12,
                     market_cap: 150e6, latest_quadrant: 'REAL', latest_change_pct: 2.2,
                     latest_volume_surge: 2.1 }],
  };
  const ALERTS = [{ ticker: 'VOLA', fired_at: '2026-09-25T10:00:00-04:00',
                    payload: { surge: 6.2, change_pct: 14.0, price: 2.5, company_name: 'VOLA Inc' } }];
  return { SCAN, PRED, FRENZY, PRE, CAL, TL, STALE, MULTI, ALERTS };
});

vi.mock('../hooks/useCatalysts', () => ({
  useCatalystScan: () => ({ data: D.SCAN, loading: false, refreshing: false, refetch: vi.fn(), forceRefresh: vi.fn() }),
  useVolumeAlerts: () => ({ alerts: D.ALERTS, session_date: undefined }),
  useDeepDive: () => ({ data: null, loading: false }),
  usePremarketScan: () => ({ data: D.PRE, loading: false, refetch: vi.fn() }),
  useInsiderSignal: () => ({ data: null, loading: false }),
  useCatalystCalendar: () => ({ data: D.CAL, loading: false, refetch: vi.fn(), forceRefresh: vi.fn() }),
  useCatalystTimeline: () => ({ data: D.TL, loading: false, refetch: vi.fn() }),
  useCatalystStale: () => ({ data: D.STALE, loading: false, refetch: vi.fn() }),
  useCatalystMultiDayAccumulators: () => ({ data: D.MULTI, loading: false, refetch: vi.fn() }),
  usePredictions: () => ({ data: D.PRED, loading: false, refreshing: false, refetch: vi.fn(), forceRefresh: vi.fn() }),
  useFrenzyRadar: () => ({ data: D.FRENZY, loading: false, refetch: vi.fn() }),
}));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));
vi.mock('../components/MarketGaugeBanner', () => ({ MarketGaugeBanner: () => null }));
vi.mock('../components/RussellWatch', () => ({ RussellWatch: () => <div data-testid="russell" /> }));
vi.mock('../components/PromoCircuit', () => ({ PromoCircuit: () => <div data-testid="promo" /> }));
vi.mock('../components/WatchlistButton', () => ({ WatchlistButton: () => null }));
vi.mock('../hooks/useMyFeatures', () => ({
  useMyFeatures: () => ({ loaded: true, features: new Set(['catalysts', 'chart-maps']), catalog: [], email: null }),
}));

import { CatalystsBoard, CATALYST_TICKER_TAB, isInnerControl } from './Catalysts';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 503, json: async () => ({}) })));
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

function Where() {
  const l = useLocation();
  return <div data-testid="where">{l.pathname + l.search}</div>;
}

const draw = (sub: string) => render(
  <MemoryRouter initialEntries={[`/chart-maps?tab=catalysts&sub=${sub}`]}>
    <Routes>
      <Route path="/chart-maps" element={<><CatalystsBoard embedded /><Where /></>} />
      <Route path="/sepa/:symbol" element={<Where />} />
    </Routes>
  </MemoryRouter>,
);

const where = () => new URL(screen.getByTestId('where').textContent || '', 'http://x');

/** Every in-app ticker link on screen, as parsed URLs. */
const sepaLinks = (root: HTMLElement = document.body) =>
  Array.from(root.querySelectorAll<HTMLAnchorElement>('a[href^="/sepa/"]'))
    .map((a) => new URL(a.getAttribute('href') || '', 'http://x'));

const expectSupply = (u: URL, sym: string, sub: string) => {
  expect(u.pathname).toBe(`/sepa/${sym}`);
  expect(u.searchParams.get('tab')).toBe('supply');
  expect(u.searchParams.get('from')).toBe('chart-maps');
  expect(new URLSearchParams(u.searchParams.get('from_q') || '').get('sub')).toBe(sub);
};

describe('Catalysts — every ticker opens Supply & Demand (2026-09-25)', () => {
  it('the tab constant is supply', () => {
    expect(CATALYST_TICKER_TAB).toBe('supply');
  });

  it.each([
    ['now',         ['EOSE', 'CLYM', 'VOLA']],
    ['predictions', ['PRDA', 'PRDB', 'VOLA']],
    ['frenzy',      ['FRZA', 'VOLA']],
    ['premarket',   ['PREA', 'VOLA']],
    ['calendar',    ['CALA', 'VOLA']],
    ['timeline',    ['MDAC', 'TLEN', 'TLCH', 'TLEV', 'TLQD', 'TLPH', 'TLEX', 'STWN', 'STCH', 'VOLA']],
  ])('%s: every ticker is a real link to its Supply & Demand tab', (sub, syms) => {
    draw(sub);
    const links = sepaLinks();
    expect(links.map((u) => u.pathname.slice('/sepa/'.length)).sort()).toEqual([...syms].sort());
    for (const u of links) expectSupply(u, u.pathname.slice('/sepa/'.length), sub);
  });

  it('NEGATIVE — no ticker link on any sub-tab lands on a bare /sepa/SYM (no tab)', () => {
    for (const sub of ['now', 'predictions', 'frenzy', 'premarket', 'calendar', 'timeline']) {
      const { unmount } = draw(sub);
      for (const u of sepaLinks()) expect(u.searchParams.get('tab'), `${sub} ${u.pathname}`).toBe('supply');
      unmount();
    }
  });

  it('now: a click anywhere on the card body opens Supply & Demand', () => {
    draw('now');
    fireEvent.click(screen.getByText('EOSE catalyst summary'));
    expectSupply(where(), 'EOSE', 'now');
  });

  it('premarket: a click on the card body opens Supply & Demand', () => {
    draw('premarket');
    fireEvent.click(screen.getByText(/Pre-market gap on PREA/));
    expectSupply(where(), 'PREA', 'premarket');
  });

  it('timeline: the accumulator row and the stale row open Supply & Demand off the row, not only the name', () => {
    const { unmount } = draw('timeline');
    fireEvent.click(screen.getByText('MDAC Inc'));
    expectSupply(where(), 'MDAC', 'timeline');
    unmount();
    draw('timeline');
    fireEvent.click(screen.getAllByText('4h')[0]);
    expectSupply(where(), 'STWN', 'timeline');
  });

  it('the volume-alert strip opens Supply & Demand', () => {
    draw('now');
    fireEvent.click(screen.getByText('6.2× vol'));
    expectSupply(where(), 'VOLA', 'now');
  });

  it('NEGATIVE — dismissing a volume alert (×) does not navigate', () => {
    draw('now');
    fireEvent.click(screen.getByTitle('Dismiss'));
    expect(where().pathname).toBe('/chart-maps');
  });

  it('NEGATIVE — ⌘-click on a card opens a NEW tab on Supply & Demand and leaves this page alone', () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);
    draw('now');
    fireEvent.click(screen.getByText('CLYM catalyst summary'), { metaKey: true });
    expect(where().pathname).toBe('/chart-maps');
    expect(open).toHaveBeenCalledTimes(1);
    expectSupply(new URL(open.mock.calls[0][0] as string, 'http://x'), 'CLYM', 'now');
  });

  it.each(['now', 'predictions', 'frenzy', 'premarket'])(
    'NEGATIVE — %s: 🔎 opens the deep-dive drawer and does NOT navigate', (sub) => {
      draw(sub);
      expect(screen.queryByRole('dialog')).toBeNull();
      fireEvent.click(screen.getAllByRole('button', { name: /Catalyst deep-dive for/ })[0]);
      expect(where().pathname).toBe('/chart-maps');
      expect(screen.getByRole('dialog')).toBeTruthy();
    });

  it('NEGATIVE — a chatter link inside a card does not navigate the card', () => {
    draw('now');
    const card = screen.getByText('EOSE catalyst summary').closest('article') as HTMLElement;
    const ext = within(card).getAllByRole('link').find((a) => !(a.getAttribute('href') || '').startsWith('/sepa/'));
    expect(ext).toBeTruthy();
    fireEvent.click(ext!);
    expect(where().pathname).toBe('/chart-maps');
  });

  it('NEGATIVE — the "deep-dive" box in the bar still opens the drawer, not the ticker page', () => {
    draw('now');
    fireEvent.change(screen.getByPlaceholderText(/check a specific ticker/), { target: { value: 'ryoj' } });
    fireEvent.click(screen.getByRole('button', { name: 'deep-dive' }));
    expect(where().pathname).toBe('/chart-maps');
    expect(screen.getByRole('dialog')).toBeTruthy();
  });

  it('Russell and Promo are left to their own components (already Supply & Demand)', () => {
    draw('russell');
    expect(screen.getByTestId('russell')).toBeTruthy();
  });
});

describe('isInnerControl', () => {
  const ev = (target: Element, currentTarget: Element) =>
    ({ target, currentTarget } as unknown as ReactMouseEvent);

  it('a link or button INSIDE the card is the control, not the card', () => {
    const card = document.createElement('article');
    const a = document.createElement('a');
    const span = document.createElement('span');
    a.appendChild(span);
    const b = document.createElement('button');
    card.append(a, b);
    expect(isInnerControl(ev(span, card))).toBe(true);
    expect(isInnerControl(ev(b, card))).toBe(true);
  });

  it('NEGATIVE — plain card text is the card', () => {
    const card = document.createElement('article');
    const p = document.createElement('p');
    card.appendChild(p);
    expect(isInnerControl(ev(p, card))).toBe(false);
    expect(isInnerControl(ev(card, card))).toBe(false);
  });

  it('NEGATIVE — a link OUTSIDE the card (the card sits inside it) does not count', () => {
    const outer = document.createElement('a');
    const card = document.createElement('li');
    const s = document.createElement('span');
    outer.appendChild(card);
    card.appendChild(s);
    expect(isInnerControl(ev(s, card))).toBe(false);
  });
});
