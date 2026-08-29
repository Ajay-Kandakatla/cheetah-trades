/**
 * Desk page — renders the cron-built daily report. Negative cases carry
 * the weight (Rule #6): the no-report-yet state and the
 * nothing-qualifies verdict are both first-class outcomes, not errors
 * to paper over.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Desk } from './Desk';

const REPORT = {
  date: '2026-08-28',
  params: { risk_pct_per_trade: 0.75, max_positions: 5 },
  regime: {
    verdict: 'MIXED', label: 'pressure',
    drivers: ['regime engine: pressure', '4 distribution days in 25', 'VIX 21.3'],
    throttle: { note: 'half size, max 3 ideas, tighter stops' },
  },
  book: [{
    symbol: 'TENB', module: 'B', score: 78.5,
    parts: { catalyst: 22, technical: 21, asymmetry: 15, liquidity: 15, crowding: 5.5 },
    plan: { entry: 38.0, stop: 36.0, target1: 45.6, target2: 47.5, rr: 3.8 },
    size: { shares: 112, risk_dollars: 224, cost: 4256 },
    theme: null, earnings_in_days: 12, time_stop: '10 sessions without trigger → drop',
  }],
  watch: [{ symbol: 'CLS', score: 66, plan: { entry: 55.2 } }],
  cuts: [{ symbol: 'JOBY', module: 'B', reasons: ['extended +14.0% past the pivot — chasing'] }],
  at_the_level: {
    gappers: [],
    gabbar_hits: [{ symbol: 'AMD', price: 171.2, state: 'in', label: 'aggressive', lo: 170, hi: 175, dist_pct: 0 }],
  },
  position_ideas: [{ symbol: 'LPTH', psg: '0.109', rev_yoy: '+109%', why: 'price lags growth' }],
  account: {
    value: 59842.5,
    knives: [{ ticker: 'BIIB', verdict: 'WATCH_SALES', signals: [] }],
  },
  context: { rotation: { leading: ['Energy', 'Financials', 'Health'], lagging: ['Materials', 'REITs', 'Staples'], havens: [] }, gex: {}, macro: null },
  carried_forward: [
    { symbol: 'KTOS', from: '2026-08-27', status: 'open', last_close: 52.1 },
    { symbol: 'AVGO', from: '2026-08-27', status: 'stopped' },
  ],
  prose: {
    regime_lines: ['Tape under pressure — 4 distribution days, breadth thinning.'],
    cards: { TENB: 'Security software breaking out of a 6-week base on accumulation.' },
    bear_case: 'ADX 15 — no trend yet.\nCrowded software tape.',
    tilt_check: 'Book is one software name — fine at this size.',
    mind_changer: 'Distribution count crossing 6/25 flips this to RISK-OFF.',
    provider: 'anthropic',
  },
  unavailable: ['economic calendar (CPI/FOMC dates) — not wired'],
  nothing_qualifies: false,
  disclaimer: 'Not investment advice — verify independently before risking capital.',
};

const HISTORY = { ok: true, runs: [{ date: '2026-08-28', verdict: 'MIXED' }] };

function stubFetch(reportBody: any, ok = true, status = 200) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (String(url).includes('/desk/history')) {
      return { ok: true, status: 200, json: async () => HISTORY } as any;
    }
    return { ok, status, json: async () => reportBody } as any;
  }));
}

afterEach(() => vi.unstubAllGlobals());

describe('Desk page', () => {
  beforeEach(() => stubFetch({ ok: true, report: REPORT }));

  it('renders verdict, throttle, the book row with sizing, and the journal', async () => {
    render(<MemoryRouter><Desk /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('MIXED')).toBeInTheDocument());
    expect(screen.getByText(/half size, max 3 ideas/)).toBeInTheDocument();
    expect(screen.getAllByText('TENB').length).toBeGreaterThan(0);
    expect(screen.getByText('3.8R')).toBeInTheDocument();
    expect(screen.getByText(/112 \(~\$4,256\)/)).toBeInTheDocument();
    // cut list travels, journal graded
    expect(screen.getByText(/extended \+14.0% past the pivot/)).toBeInTheDocument();
    expect(screen.getByText(/🔴 stopped/)).toBeInTheDocument();
    // holdings-first warning and the disclaimer
    expect(screen.getByText('BIIB')).toBeInTheDocument();
    expect(screen.getByText(/Not investment advice/)).toBeInTheDocument();
  });

  it('flags earnings inside the horizon on the book row', async () => {
    render(<MemoryRouter><Desk /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/ER 12d/)).toBeInTheDocument());
  });
});

describe('Desk page — negative states', () => {
  it('nothing_qualifies renders as an answer, not an empty table', async () => {
    stubFetch({
      ok: true,
      report: { ...REPORT, book: [], nothing_qualifies: true, prose: { ...REPORT.prose, cards: {} } },
    });
    render(<MemoryRouter><Desk /></MemoryRouter>);
    await waitFor(() =>
      expect(screen.getByText(/Nothing qualifies today/)).toBeInTheDocument());
    expect(screen.queryByText('Entry')).not.toBeInTheDocument();
  });

  it('no report yet (404) explains the cron schedule instead of erroring', async () => {
    stubFetch({ ok: false, note: 'no desk report yet — the cron writes one at 8:40am ET on weekdays' }, false, 404);
    render(<MemoryRouter><Desk /></MemoryRouter>);
    await waitFor(() =>
      expect(screen.getByText(/no desk report yet/)).toBeInTheDocument());
    expect(screen.getAllByText(/8:40am ET/).length).toBeGreaterThan(0);
  });

  it('deterministic-fallback prose is labeled so he knows the persona was offline', async () => {
    stubFetch({
      ok: true,
      report: { ...REPORT, prose: { ...REPORT.prose, provider: 'deterministic' } },
    });
    render(<MemoryRouter><Desk /></MemoryRouter>);
    await waitFor(() =>
      expect(screen.getByText(/persona prose offline/)).toBeInTheDocument());
  });
});
