import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

/* BreakoutsPage — the dedicated breakout tracker (Ajay 2026-06-16): names ranked
   by # of breakouts (highest first) with the Minervini+Bonde verdict, filterable
   by which side passes. Locks the ranking display, the filter, and the negatives
   (empty / error). The hook is mocked so the test is pure-UI. */

import type { BreakoutBoardRow, BreakoutBoardSummary } from '../hooks/useBreakoutBoard';

let mockState: {
  rows: BreakoutBoardRow[]; summary: BreakoutBoardSummary | null;
  loading: boolean; error: string | null;
};
/* Recorded so a test can prove the stage gate is a SERVER round-trip: it runs
   before the top-250 cut, so it cannot be undone in the browser. */
const boardCalls = vi.hoisted(() => [] as unknown[][]);
/* Lets one test hand the page a PARTIAL rankInfo — the shape a not-yet-redeployed
   server produces, which must degrade to zeros rather than a white screen. */
let partialRank = false;
vi.mock('../hooks/useBreakoutBoard', () => ({
  useBreakoutBoard: (...args: unknown[]) => {
    boardCalls.push(args);
    return { ...mockState, scanTs: 1, reload: vi.fn(),
             stageInfo: { on: false, dropped: 0, qualifying: 2840, scanned: 2840 },
             rankInfo: (partialRank ? { sort: 'qoq' } : {
               sort: 'qoq', scored: 250, income: 250, growth: 247,
               seasonalBasis: 236, seasonalEcho: 53, total: 250 }) as any };
  },
}));

// Dynamic re-scan control (Ajay 2026-06-18): the "Update" button runs a CHEAP
// fast scan over the broad universe, not an expensive full one.
const scanStart = vi.fn();
let scanScanning = false;
vi.mock('../hooks/useSepaScanStream', () => ({
  useSepaScanStream: () => ({
    scanning: scanScanning,
    phase: 'idle',
    phaseMessage: scanScanning ? 'Enriching…' : '',
    start: scanStart,
    reset: vi.fn(),
    close: vi.fn(),
  }),
}));

import { BreakoutsPage } from './Breakouts';

const verdict = (mPass: boolean, bPass: boolean | null) => ({
  status: mPass ? 'pass' : 'fail', label: mPass ? 'PASS' : 'FAIL', icon: mPass ? '🟢' : '🔴',
  tone: '#10b981', both_pass: mPass && bPass === true, buyable_now: false,
  sales_pending: bPass === null,
  minervini: { passed: mPass, buyable_now: false, stage: 2, reason: 'r', cite: 'p.79' },
  bonde: { passed: bPass, pending: bPass === null, tier: 't', score: 50, growth_yoy_pct: 10, reason: 'r', cite: 'Bonde' },
});

const row = (symbol: string, count: number, mPass: boolean, bPass: boolean | null,
            beta: number | null = 1.0, buyable = false): BreakoutBoardRow => ({
  symbol, name: `${symbol} Inc`, breakout_count: count, days_since_breakout: 0,
  high_vol_breakout: true, broke_out_today: true, last_close: 100, day_change_pct: 1.2,
  rs_rank: 90, stage: 2, beta, is_etf: false, is_buyable: buyable, setup_ready: buyable,
  setup_type: 'VCP',
  buy_verdict: verdict(mPass, bPass) as any,
});

const renderPage = () => render(<MemoryRouter><BreakoutsPage /></MemoryRouter>);

beforeEach(() => {
  mockState = {
    rows: [
      row('BBB', 9, true, true, 1.0, true),  // both pass + BUYABLE
      row('CCC', 5, true, false),   // Minervini pass, Bonde fail
      row('AAA', 2, false, true),   // Minervini fail, Bonde pass
    ],
    summary: { total: 3, broke_out_today: 3, buyable: 1, minervini_pass: 2, minervini_fail: 1, bonde_pass: 2, bonde_fail: 1, both_pass: 1 },
    loading: false, error: null,
  };
  scanStart.mockClear();
  scanScanning = false;
});

describe('BreakoutsPage — dynamic re-scan', () => {
  it('Update runs a CHEAP fast scan over the broad universe (not a full scan)', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /Update/i }));
    expect(scanStart).toHaveBeenCalledWith({ fast: true, mode: 'broad' });
  });

  it('shows scan progress + disables Refresh while scanning', () => {
    scanScanning = true;
    renderPage();
    expect(screen.getByText(/Enriching…/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Refresh/i })).toBeDisabled();
  });
});

describe('BreakoutsPage', () => {
  it('lists breakouts ranked by count, highest first', () => {
    renderPage();
    const rows = screen.getAllByRole('row').filter((r) => !r.className.includes('--head'));
    // first data row is the highest-count name (BBB=9)
    expect(within(rows[0]).getByText('BBB')).toBeInTheDocument();
    expect(within(rows[0]).getByText('9')).toBeInTheDocument();
    expect(within(rows[2]).getByText('AAA')).toBeInTheDocument();
  });

  it('badges the buyable row and the "Buyable now" filter narrows to it', () => {
    renderPage();
    // BBB is the only is_buyable row → it carries the 🎯 BUYABLE badge.
    expect(screen.getByText(/BUYABLE/)).toBeInTheDocument();
    // The buyable stat counts 1.
    fireEvent.click(screen.getByRole('button', { name: /🎯 Buyable now/i }));
    const rows = screen.getAllByRole('row').filter((r) => !r.className.includes('--head'));
    expect(rows).toHaveLength(1);
    expect(within(rows[0]).getByText('BBB')).toBeInTheDocument();
  });

  it('explicitly says "wait for pullback" on a SETUP that ran past the pivot (Ajay 2026-06-22)', () => {
    mockState = {
      rows: [
        { ...row('ARM', 7, true, true), is_buyable: false, setup_ready: true,
          setup_note: { kind: 'extended', ext_pct: 4.9, pivot: 418.88 } },
      ],
      summary: { total: 1, broke_out_today: 1, buyable: 0, minervini_pass: 1, minervini_fail: 0, bonde_pass: 1, bonde_fail: 0, both_pass: 1 },
      loading: false, error: null,
    };
    renderPage();
    expect(screen.getByText(/EXTENDED \+4\.9%/)).toBeInTheDocument();
    expect(screen.getByText(/wait for pullback/i)).toBeInTheDocument();
    expect(screen.getByText(/→ \$418\.88/)).toBeInTheDocument();   // the pivot to wait for
    // it is NOT shown as a plain BUYABLE/SETUP — the extended note replaces it
    expect(screen.queryByText(/🎯 BUYABLE/)).not.toBeInTheDocument();
  });

  it('CONVICTION column: Enter-eligible first, then conviction desc (Ajay 2026-06-22; no longer the default after 2026-09-12)', () => {
    const mk = (sym: string, conv: number, buyable: boolean): BreakoutBoardRow => ({
      symbol: sym, name: `${sym} Inc`, breakout_count: 3, days_since_breakout: 0,
      high_vol_breakout: true, broke_out_today: true, last_close: 100, last_vol: 2_000_000,
      avg_vol_50: 1_000_000, day_change_pct: 1, rs_rank: 90, stage: 2, is_etf: false,
      is_buyable: buyable, setup_ready: buyable, conviction: conv, setup_type: 'VCP',
      buy_verdict: verdict(true, true) as any,
    });
    mockState.rows = [
      mk('HICONVNB', 99, false),  // HIGHEST conviction but NOT buyable
      mk('BUYLO', 60, true),      // buyable, lower conviction
      mk('BUYHI', 85, true),      // buyable, higher conviction
    ];
    renderPage();
    // Conviction is one tap away since the default became recency (2026-09-12).
    fireEvent.click(screen.getByRole('button', { name: /Conv\./ }));
    const rows = screen.getAllByRole('row').filter((r) => !r.className.includes('--head'));
    // Enter-eligible (is_buyable) first, conviction-ordered within: BUYHI(85) >
    // BUYLO(60); the non-buyable HICONVNB sinks to last DESPITE the highest conviction.
    expect(within(rows[0]).getByText('BUYHI')).toBeInTheDocument();
    expect(within(rows[1]).getByText('BUYLO')).toBeInTheDocument();
    expect(within(rows[2]).getByText('HICONVNB')).toBeInTheDocument();
  });

  it('renders the Conviction column; a suppressed climax breakout sorts below a clean leader (Ajay 2026-06-22)', () => {
    mockState.rows = [
      { ...row('AMAT', 7, true, true, 1.0, false), conviction: 12, decision: 'AVOID',
        conviction_detail: { conviction: 12, legs: { momentum: 90, coil: 20, demand: 10, reward_risk: 10 },
          suppressed: true, suppress_reason: 'climax-top distribution (TTLAC p.186-188)',
          lead: 'momentum', weights: { momentum: 0.35, coil: 0.30, demand: 0.25, reward_risk: 0.10 } } },
      { ...row('LEAD', 5, true, true, 1.0, true), conviction: 88, decision: 'ENTER' },
    ];
    renderPage();
    // The Conv. column header + both numbers render.
    expect(screen.getByRole('button', { name: /Conv\./ })).toBeInTheDocument();
    expect(screen.getByText('88')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Conv\./ }));
    // Despite AMAT's HIGHER breakout count (7 vs 5), the clean buyable leader
    // sorts first under the conviction sort — the suppressed climax sinks.
    const rows = screen.getAllByRole('row').filter((r) => !r.className.includes('--head'));
    expect(within(rows[0]).getByText('LEAD')).toBeInTheDocument();
    expect(within(rows[1]).getByText('AMAT')).toBeInTheDocument();
  });

  /* Ajay 2026-09-12: "Sort it by recent breakout instead of # of breakouts."
   *
   * The server now ranks by recency too, which is the half that matters: it
   * used to sort by COUNT and only then cut to the top 250, so on the
   * 2026-09-12 scan 47 names that broke out THAT DAY — HPQ, HPE, QRVO, SWKS
   * among them — were discarded before the browser saw anything. */
  it('the RECENCY order is still reachable and still beats the highest count (2026-09-12)', () => {
    const mk = (sym: string, days: number, count: number): BreakoutBoardRow => ({
      symbol: sym, name: `${sym} Inc`, breakout_count: count, days_since_breakout: days,
      high_vol_breakout: true, broke_out_today: days === 0, last_close: 100,
      last_vol: 2_000_000, avg_vol_50: 1_000_000, day_change_pct: 1, rs_rank: 90,
      stage: 2, is_etf: false, is_buyable: true, setup_ready: true, conviction: 50,
      setup_type: 'VCP', buy_verdict: verdict(true, true) as any,
    });
    mockState.rows = [
      mk('OLDMANY', 12, 19),   // the most breakouts, none of them recent
      mk('FRESH', 0, 2),       // broke out TODAY on a low count
      mk('MID', 4, 9),
    ];
    renderPage();
    // The default is now income+growth (Ajay: "prioritize income and growth
    // only quarter over quarter"), and none of these rows carries a QoQ leg —
    // so tap the Last header to ask for recency and check it still holds.
    fireEvent.click(screen.getByTitle('Sort by Last'));
    const rows = screen.getAllByRole('row').filter((r) => !r.className.includes('--head'));
    expect(within(rows[0]).getByText('FRESH')).toBeInTheDocument();
    expect(within(rows[1]).getByText('MID')).toBeInTheDocument();
    expect(within(rows[2]).getByText('OLDMANY')).toBeInTheDocument();
  });

  it('NEGATIVE: a name with NO recorded breakout date sorts LAST, not first', () => {
    const mk = (sym: string, days: number | null): BreakoutBoardRow => ({
      symbol: sym, name: `${sym} Inc`, breakout_count: 5, days_since_breakout: days,
      high_vol_breakout: true, broke_out_today: days === 0, last_close: 100,
      last_vol: 2_000_000, avg_vol_50: 1_000_000, day_change_pct: 1, rs_rank: 90,
      stage: 2, is_etf: false, is_buyable: true, setup_ready: true, conviction: 50,
      setup_type: 'VCP', buy_verdict: verdict(true, true) as any,
    });
    // Unknown is not recent. Scoring it as 0 would put a name nobody dated at
    // the top of a board that now claims to be ordered by recency.
    mockState.rows = [mk('NODATE', null), mk('TODAY', 0)];
    renderPage();
    fireEvent.click(screen.getByTitle('Sort by Last'));
    const rows = screen.getAllByRole('row').filter((r) => !r.className.includes('--head'));
    expect(within(rows[0]).getByText('TODAY')).toBeInTheDocument();
    expect(within(rows[1]).getByText('NODATE')).toBeInTheDocument();
  });

  it('shows the EPS and 🚀 explosive-growth overlay (2026-09-12)', () => {
    mockState.rows = [
      { ...row('DELL', 9, true, true), sales_yoy: 83.4, q_eps_yoy: 144.2 },
      { ...row('IPI', 4, true, true), sales_yoy: 366.8, q_eps_yoy: 120.0,
        explosive: true, explosive_refused: true },
    ];
    renderPage();
    // Year-over-year moved to the small grey line under the sequential number.
    expect(screen.getByText('y/y +83%')).toBeInTheDocument();
    expect(screen.getByText('y/y +144%')).toBeInTheDocument();
    // the 🚀 name that the trading engine still refuses must say so
    expect(screen.getByTitle(/trading engine REFUSES this one/i)).toBeInTheDocument();
  });

  it('NEGATIVE: a name the research cache cannot answer for prints an em-dash, not 0%', () => {
    mockState.rows = [{ ...row('NOFUND', 3, true, true), sales_yoy: null, q_eps_yoy: null }];
    renderPage();
    const rows = screen.getAllByRole('row').filter((r) => !r.className.includes('--head'));
    expect(within(rows[0]).queryByText('+0%')).not.toBeInTheDocument();
    expect(within(rows[0]).getAllByText('—').length).toBeGreaterThan(0);
  });

  it('hides bare-breakout (non-base) names by default; "Base only" toggle reveals them (Ajay 2026-06-22)', () => {
    mockState.rows = [
      { ...row('VCPNAME', 5, true, true), setup_type: 'VCP' },
      { ...row('BAREBO', 9, true, true), setup_type: 'BREAKOUT' },   // bare breakout, no base
    ];
    renderPage();
    // default: Base only ON → VCP shown, bare breakout hidden
    expect(screen.getByText('VCPNAME')).toBeInTheDocument();
    expect(screen.queryByText('BAREBO')).not.toBeInTheDocument();
    // toggle Base only OFF → the bare breakout appears
    fireEvent.click(screen.getByRole('button', { name: /Base only/i }));
    expect(screen.getByText('BAREBO')).toBeInTheDocument();
  });

  it('explains every column from the table info icon', () => {
    renderPage();
    // The table-level ⓘ (distinct from the page-title one) opens a per-column legend.
    const trigger = screen.getByRole('button', { name: /What is Breakout columns\?/i });
    // It's right-anchored so the popover opens leftward (doesn't clip off-screen).
    expect(trigger.closest('.info-button')).toHaveClass('info-button--align-right');
    fireEvent.click(trigger);
    const legend = within(screen.getByRole('dialog', { name: /Breakout columns/i }));
    expect(legend.getByText(/dollar volume traded today/i)).toBeInTheDocument();   // Turnover
    expect(legend.getByText(/none recorded/i)).toBeInTheDocument();                // Last
    expect(legend.getByText(/buyable-stock/i)).toBeInTheDocument();                // Verdict
    expect(legend.getByText(/the 1.5× volume that confirms a breakout/i)).toBeInTheDocument(); // Vol %
    expect(legend.getByText(/sort low-volatility first/i)).toBeInTheDocument();    // Beta
    // Income + growth, quarter over quarter (2026-09-12)
    expect(legend.getByText(/this quarter against last quarter/i)).toBeInTheDocument();
    expect(legend.getByText(/percentile within the whole candidate list/i)).toBeInTheDocument();
  });

  it('shows the Beta column and sorts low-volatility (low beta) first', () => {
    mockState.rows = [
      row('HIVOL', 9, true, true, 1.8),
      row('LOWVOL', 5, true, true, 0.6),
      row('MIDVOL', 3, true, true, 1.1),
    ];
    renderPage();
    // beta values render (2dp)
    expect(screen.getByText('0.60')).toBeInTheDocument();
    expect(screen.getByText('1.80')).toBeInTheDocument();
    // tap the Beta header → ascending = low-volatility first
    fireEvent.click(screen.getByRole('button', { name: /Beta/ }));
    const dataRows = screen.getAllByRole('row').filter((r) => !r.className.includes('--head'));
    expect(within(dataRows[0]).getByText('LOWVOL')).toBeInTheDocument();   // β=0.6 first
    expect(within(dataRows[2]).getByText('HIVOL')).toBeInTheDocument();    // β=1.8 last
  });

  it('renders a — for a missing beta (negative)', () => {
    mockState.rows = [row('NB', 4, true, true, null)];
    renderPage();
    expect(screen.getByTitle(/Beta unavailable/i)).toHaveTextContent('—');
  });

  it('filters to only the Minervini-failing breakouts', () => {
    renderPage();
    // "Minervini ✗" is both a filter chip (button) and a summary label (div) —
    // click the button specifically.
    fireEvent.click(screen.getByRole('button', { name: 'Minervini ✗' }));
    expect(screen.getByText('AAA')).toBeInTheDocument();       // M fail stays
    expect(screen.queryByText('BBB')).not.toBeInTheDocument(); // M pass filtered out
    expect(screen.queryByText('CCC')).not.toBeInTheDocument();
  });

  it('shows the pass/fail summary mix', () => {
    renderPage();
    // both-pass count of 1 appears in the summary strip
    expect(screen.getByText('M + Bonde')).toBeInTheDocument();
  });

  it('shows an empty state when there are no breakouts (negative)', () => {
    mockState = { rows: [], summary: { total: 0, broke_out_today: 0, buyable: 0, minervini_pass: 0, minervini_fail: 0, bonde_pass: 0, bonde_fail: 0, both_pass: 0 }, loading: false, error: null };
    renderPage();
    expect(screen.getByText(/No breakouts in the latest scan/i)).toBeInTheDocument();
  });

  it('shows an honest error (negative)', () => {
    mockState = { rows: [], summary: null, loading: false, error: 'HTTP 500' };
    renderPage();
    expect(screen.getByText(/Couldn't load breakouts/i)).toBeInTheDocument();
  });
});

/* Turnover / Vol % / Total Vol columns + sortable headers (Ajay 2026-06-16).
   Turnover = price × today's volume; Vol % = today's volume vs its 50-day avg —
   both derived client-side from the board payload. */

type VOpts = { count: number; price: number | null; vol: number | null; avg: number | null; chg: number | null };
const vrow = (symbol: string, o: VOpts): BreakoutBoardRow => ({
  symbol, name: `${symbol} Inc`, breakout_count: o.count, days_since_breakout: 0,
  high_vol_breakout: true, broke_out_today: true, last_close: o.price, last_vol: o.vol,
  avg_vol_50: o.avg, day_change_pct: o.chg, rs_rank: 90, stage: 2, is_etf: false, setup_type: 'VCP',
  buy_verdict: verdict(true, true) as any,
});

const dataRows = () =>
  screen.getAllByRole('row').filter((r) => !r.className.includes('--head'));
const turnoverHeader = () => screen.getByRole('button', { name: /Turnover/ });

describe('BreakoutsPage — turnover / volume columns + sorting', () => {
  beforeEach(() => {
    mockState = {
      // HIGH = biggest dollar volume, LOW = smallest; deliberately NOT in count order.
      rows: [
        vrow('MID', { count: 9, price: 50, vol: 2_000_000, avg: 2_000_000, chg: 1.0 }),  // $100.0M, 100%
        vrow('HIGH', { count: 2, price: 100, vol: 5_000_000, avg: 1_000_000, chg: 3.5 }), // $500.0M, 500%
        vrow('LOW', { count: 5, price: 10, vol: 1_000_000, avg: 4_000_000, chg: -2.0 }),  // $10.0M, 25%
      ],
      summary: { total: 3, broke_out_today: 3, buyable: 0, minervini_pass: 3, minervini_fail: 0, bonde_pass: 3, bonde_fail: 0, both_pass: 3 },
      loading: false, error: null,
    };
  });

  it('renders Turnover, Vol % and Total Vol with humanized values', () => {
    renderPage();
    // headers exist as sortable buttons
    for (const h of ['Ticker', '# breakouts', 'Price', 'Vol %', 'Total Vol', 'Turnover']) {
      expect(screen.getByRole('button', { name: new RegExp(h.replace('#', '\\#').replace('%', '%')) })).toBeInTheDocument();
    }
    // HIGH row values: turnover $500.0M, total vol 5.0M, vol% 500%
    expect(screen.getByText('$500.0M')).toBeInTheDocument();
    expect(screen.getByText('5.0M')).toBeInTheDocument();
    expect(screen.getByText('500%')).toBeInTheDocument();
    // LOW row: $10.0M / 1.0M / 25%
    expect(screen.getByText('$10.0M')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
  });

  it('sorts by turnover descending when the Turnover header is clicked', () => {
    // (Default is now BUYABLE-FIRST — none of these are buyable, so clicking
    //  Turnover gives the dollar-volume order.)
    renderPage();
    fireEvent.click(turnoverHeader());
    const rows = dataRows();
    expect(within(rows[0]).getByText('HIGH')).toBeInTheDocument();  // $500M
    expect(within(rows[1]).getByText('MID')).toBeInTheDocument();   // $100M
    expect(within(rows[2]).getByText('LOW')).toBeInTheDocument();   // $10M
    expect(turnoverHeader().textContent).toContain('▼');
  });

  it('toggles the turnover sort direction on each header click (desc → asc → desc)', () => {
    renderPage();
    fireEvent.click(turnoverHeader());                            // activate turnover desc
    expect(turnoverHeader().textContent).toContain('▼');
    expect(within(dataRows()[0]).getByText('HIGH')).toBeInTheDocument();

    fireEvent.click(turnoverHeader());                            // → asc
    expect(turnoverHeader().textContent).toContain('▲');
    expect(within(dataRows()[0]).getByText('LOW')).toBeInTheDocument();

    fireEvent.click(turnoverHeader());                            // → desc
    expect(turnoverHeader().textContent).toContain('▼');
    expect(within(dataRows()[0]).getByText('HIGH')).toBeInTheDocument();
  });

  it('sorts by a different column when its header is clicked (# breakouts desc)', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /# breakouts/ }));
    const rows = dataRows();
    expect(within(rows[0]).getByText('MID')).toBeInTheDocument();  // count 9
    expect(within(rows[1]).getByText('LOW')).toBeInTheDocument();  // count 5
    expect(within(rows[2]).getByText('HIGH')).toBeInTheDocument(); // count 2
  });

  it('shows dashes and sinks rows with no volume to the bottom (negative)', () => {
    mockState = {
      rows: [
        vrow('GOOD', { count: 3, price: 40, vol: 3_000_000, avg: 1_500_000, chg: 1.1 }),
        { ...vrow('NULL', { count: 3, price: null, vol: null, avg: null, chg: null }), broke_out_today: false, days_since_breakout: null },
      ],
      summary: { total: 2, broke_out_today: 1, buyable: 0, minervini_pass: 2, minervini_fail: 0, bonde_pass: 2, bonde_fail: 0, both_pass: 2 },
      loading: false, error: null,
    };
    renderPage();
    const rows = dataRows();
    // null-volume row sinks last under turnover-desc
    expect(within(rows[0]).getByText('GOOD')).toBeInTheDocument();
    expect(within(rows[1]).getByText('NULL')).toBeInTheDocument();
    // its turnover / vol% / total-vol all render as em-dashes
    expect(within(rows[1]).getAllByText('—').length).toBeGreaterThanOrEqual(4);
  });
});

/* Stage + "→ R1/R2" columns (Ajay 2026-06-16: "add the stages to these columns
   now if they are s2 and if they marching towards r1 or r2"). Stage 2 = the
   buyable advancing phase (✓ S2); the march column shows distance to the next
   trade-plan target. */

type SOpts = { stage: number | null; price: number | null; r1: number | null; r2: number | null };
const srow = (symbol: string, o: SOpts): BreakoutBoardRow => ({
  symbol, name: `${symbol} Inc`, breakout_count: 3, days_since_breakout: 0,
  high_vol_breakout: true, broke_out_today: true, last_close: o.price, last_vol: 1_000_000,
  avg_vol_50: 1_000_000, day_change_pct: 1.0, rs_rank: 90, stage: o.stage, setup_type: 'VCP',
  stage_label: o.stage != null ? `Stage ${o.stage}` : null, r1: o.r1, r2: o.r2,
  is_etf: false, buy_verdict: verdict(true, true) as any,
});

const marchHeader = () => screen.getByRole('button', { name: /R1\/R2/ });
const stageHeader = () => screen.getByRole('button', { name: /Stage/ });
const freshToggle = () => screen.getByRole('button', { name: /Fresh only/ });
/** "Fresh only" is ON by default and hides →R2 / Past R2 rows; tests that need
 *  the extended rows visible click it off after rendering. */
const showExtended = () => fireEvent.click(freshToggle());

describe('BreakoutsPage — Stage + → R1/R2 columns', () => {
  beforeEach(() => {
    mockState = {
      rows: [
        srow('BELOW', { stage: 2, price: 100, r1: 110, r2: 120 }),  // → R1 +10%
        srow('MID',   { stage: 4, price: 112, r1: 110, r2: 120 }),  // cleared R1 → R2
        srow('PAST',  { stage: 1, price: 130, r1: 110, r2: 120 }),  // past R2
      ],
      summary: { total: 3, broke_out_today: 3, buyable: 0, minervini_pass: 3, minervini_fail: 0, bonde_pass: 3, bonde_fail: 0, both_pass: 3 },
      loading: false, error: null,
    };
  });

  it('hides →R2 / Past R2 by default (fresh only), shows them when toggled off', () => {
    renderPage();
    // Default ON: only the fresh →R1 name (BELOW) is shown.
    expect(screen.getByText('BELOW')).toBeInTheDocument();
    expect(screen.queryByText('MID')).not.toBeInTheDocument();    // → R2, hidden
    expect(screen.queryByText('PAST')).not.toBeInTheDocument();   // past R2, hidden
    showExtended();
    expect(screen.getByText('MID')).toBeInTheDocument();
    expect(screen.getByText('PAST')).toBeInTheDocument();
  });

  it('renders the Stage column — ✓ S2 highlighted, S4 / S1 plain', () => {
    renderPage();
    showExtended();
    expect(screen.getByText('✓ S2')).toBeInTheDocument();    // Stage 2 = buyable
    expect(screen.getByText('S4')).toBeInTheDocument();      // Stage 4 = avoid
    expect(screen.getByText('S1')).toBeInTheDocument();
  });

  it('renders the marching-toward column for each branch (→ R1 / → R2 / Past R2)', () => {
    renderPage();
    showExtended();
    expect(screen.getByText(/→ R1 \+10\.00%/)).toBeInTheDocument();   // below R1
    expect(screen.getByText(/→ R2/)).toBeInTheDocument();             // between R1/R2
    expect(screen.getByText(/Past R2/)).toBeInTheDocument();          // extended
  });

  it('sorts by distance-to-target ascending when → R1/R2 header is clicked', () => {
    renderPage();
    showExtended();
    fireEvent.click(marchHeader());                          // preferred asc
    expect(marchHeader().textContent).toContain('▲');
    const rows = dataRows();
    // MID is closest to its target (R2 ≈ +7.1%), BELOW next (R1 +10%), PAST sinks (null)
    expect(within(rows[0]).getByText('MID')).toBeInTheDocument();
    expect(within(rows[1]).getByText('BELOW')).toBeInTheDocument();
    expect(within(rows[2]).getByText('PAST')).toBeInTheDocument();
  });

  it('sorts by Stage when the Stage header is clicked', () => {
    renderPage();
    showExtended();
    fireEvent.click(stageHeader());                          // desc default → highest stage first
    expect(stageHeader().textContent).toContain('▼');
    const rows = dataRows();
    expect(within(rows[0]).getByText('MID')).toBeInTheDocument();    // stage 4
    expect(within(rows[2]).getByText('PAST')).toBeInTheDocument();   // stage 1
  });
});

/* Mobile horizontal scroll (Ajay 2026-06-16). The table is wider than a phone
   (many columns), so it MUST scroll horizontally on its own to reach Turnover /
   Vol % / Total Vol on the right — otherwise those columns are unreachable. The
   container exposes overflow-x and the inner table keeps a fixed min-width so it
   doesn't squeeze every column into the viewport. */
describe('BreakoutsPage — table exposes usable horizontal scroll', () => {
  it('wraps the table in an overflow-x scroller with a fixed-width table', () => {
    renderPage();
    const scroller = screen.getByTestId('breakouts-scroll');
    expect(scroller.style.overflowX).toBe('auto');
    // contain the swipe so it scrolls the table, not the page behind it
    expect(scroller.style.overscrollBehaviorX).toBe('contain');
    // inner table is wider than any phone viewport, so columns aren't squeezed
    const table = within(scroller).getByRole('table');
    expect(parseInt(table.style.minWidth, 10)).toBeGreaterThanOrEqual(960);
  });

  it('row links open the SEPA page on its default (Supply / Demand) tab, not the breakout lens (2026-09-03)', () => {
    renderPage();                       // beforeEach rows include AAA
    const link = screen.getAllByRole('row').find((r) => r.getAttribute('href')?.includes('/sepa/AAA'));
    expect(link).toBeTruthy();
    expect(link!.getAttribute('href')).toBe('/sepa/AAA');
    expect(link!.getAttribute('href')).not.toMatch(/tab=breakout/);
  });
});

/* ── The stage gate (2026-09-12) ───────────────────────────────────────────
 * Ajay: "From the breakout remove any S3. Only S2 stocks and if thy have
 * explosive growth its ok to have s1 and s3. If they are newly found explosive
 * growth".
 *
 * The gate itself runs on the SERVER, before the top-250 cut — measured: the
 * board went from 250 rows drawn over stages {1:111, 2:78, 3:35, 4:26} to 250
 * drawn from 350 QUALIFYING names, {1:4, 2:240, 3:6, 4:0}. Filtering the
 * already-cut rows would have left ~80. These tests cover the page's half:
 * the toggle, the count, and the ✨ newly-found badge.
 */
describe('BreakoutsPage — the stage gate', () => {
  it('is OFF by default now — "May show any stage" (2026-09-12)', () => {
    mockState.rows = [row('AAA', 5, true, true)];
    boardCalls.length = 0;
    renderPage();
    expect(boardCalls.at(-1)?.[2]).toBe(false);
    const chip = screen.getByRole('button', { name: /S2 only/ });
    expect(chip.title).toMatch(/Showing EVERY stage/i);
  });

  it('turning it ON RE-REQUESTS with stages=true, not a local hide', () => {
    // 2,840 candidates sit behind a 250-row cut and the gate runs before it,
    // so it cannot be applied in the browser — the chip must refetch.
    mockState.rows = [row('AAA', 5, true, true)];
    boardCalls.length = 0;
    renderPage();
    expect(boardCalls.at(-1)?.[2]).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /S2 only/ }));
    expect(boardCalls.at(-1)?.[2]).toBe(true);
    expect(screen.getByRole('button', { name: /S2 only/ }).title)
      .toMatch(/Stage 4 is never kept/);
  });

  it('✨ marks a NEWLY found explosive grower, and nothing else', () => {
    mockState.rows = [
      { ...row('NEWG', 4, true, true), sales_yoy: 300, q_eps_yoy: 200,
        explosive: true, explosive_new: true },
      { ...row('OLDG', 4, true, true), sales_yoy: 300, q_eps_yoy: 200,
        explosive: true, explosive_new: false },
    ];
    renderPage();
    const badges = screen.getAllByTitle(/NEWLY found on the Explosive Growth board/);
    expect(badges).toHaveLength(1);
  });

  it('NEGATIVE: a non-grower never gets the ✨, however fresh', () => {
    mockState.rows = [{ ...row('PLAIN', 4, true, true), explosive: false,
                        explosive_new: true }];
    renderPage();
    expect(screen.queryByTitle(/NEWLY found on the Explosive Growth board/))
      .not.toBeInTheDocument();
  });

  it('the legend explains the rule, including what is NEVER kept', () => {
    mockState.rows = [row('AAA', 5, true, true)];
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /What is Breakout columns\?/i }));
    const legend = within(screen.getByRole('dialog', { name: /Breakout columns/i }));
    expect(legend.getByText(/off by default/i)).toBeInTheDocument();
    expect(legend.getByText(/stage-2-plus-explosive-grower gate/i)).toBeInTheDocument();
    // the hazard of showing every stage must be named, not left implicit
    expect(legend.getByText(/Fundamentals lag price by up to a quarter/i)).toBeInTheDocument();
  });
});

/* ── Income + growth, quarter over quarter (2026-09-12) ────────────────────
 * Ajay, reversing the stage gate he had asked for three hours earlier:
 * "May show any stage but prioritize income and growth only quarter over
 * quarter."
 *
 * Sequential Q0-vs-Q1, not the quarterly YEAR-over-year the page already
 * carried. MEASURED on his own board before this shipped: the two orderings
 * agree only 0.58 (revenue) / 0.37 (EPS); 11 of the top 20 on the RAW
 * percentage were bought by a base under $0.10 a share; and the raw sequential
 * leaderboard performed WORSE next quarter than the rest of the board
 * (median +0.4% / 50% positive vs a placebo of +24.0% / 70%).
 *
 * These tests cover the page's half: what it shows, what it refuses to show,
 * and what it admits it does not know.
 */
describe('BreakoutsPage — income + growth, quarter over quarter', () => {
  const qrow = (sym: string, o: Partial<BreakoutBoardRow>): BreakoutBoardRow =>
    ({ ...row(sym, 4, true, true), ...o });

  it('ranks by the income+growth blend by default, not by recency', () => {
    mockState.rows = [
      qrow('SLOWER', { days_since_breakout: 0, qoq_score: 20, income_qoq: 5, growth_qoq: 4 }),
      qrow('STRONG', { days_since_breakout: 9, qoq_score: 95, income_qoq: 60, growth_qoq: 40 }),
    ];
    renderPage();
    const rows = screen.getAllByRole('row').filter((r) => !r.className.includes('--head'));
    expect(within(rows[0]).getByText('STRONG')).toBeInTheDocument();
  });

  it('a name that EARNED money last quarter ranks above one that did not', () => {
    // You cannot prioritise income by ignoring whether there is any. A
    // growth-only row can still carry a higher blend on its single leg.
    mockState.rows = [
      qrow('NOEPS', { qoq_score: 99, income_qoq: null, growth_qoq: 80,
                      income_base: 'non_positive' }),
      qrow('EARNS', { qoq_score: 55, income_qoq: 30, growth_qoq: 20,
                      income_base: 'positive' }),
    ];
    renderPage();
    const rows = screen.getAllByRole('row').filter((r) => !r.className.includes('--head'));
    expect(within(rows[0]).getByText('EARNS')).toBeInTheDocument();
  });

  it('shows the SEQUENTIAL number big and the year-over-year small beneath it', () => {
    mockState.rows = [qrow('SEQ', { growth_qoq: 18.4, sales_yoy: 120.0,
                                    income_qoq: 44.0, q_eps_yoy: 9.1 })];
    renderPage();
    expect(screen.getByText('+18%')).toBeInTheDocument();      // sequential
    expect(screen.getByText('y/y +120%')).toBeInTheDocument(); // the check
    expect(screen.getByText('+44%')).toBeInTheDocument();
    expect(screen.getByText('y/y +9%')).toBeInTheDocument();
  });

  it('NEGATIVE: a LOSS-making prior quarter prints "loss", never a percentage', () => {
    /* (now-then)/|then| turns -0.02 -> +0.30 into "+1,600%". Printing that
       beside a real grower's +12% is the whole failure this guards. */
    mockState.rows = [qrow('LOSER', { income_qoq: null, income_base: 'non_positive',
                                      income_turn: 'to_profit' })];
    renderPage();
    expect(screen.getByText('loss')).toBeInTheDocument();
    expect(screen.getByTitle(/would be meaningless/i)).toBeInTheDocument();
    // the turn is still surfaced — it is a real event, just not a growth rate
    // (both the cell tooltip and the ↗ glyph carry it; either is enough)
    expect(screen.getAllByTitle(/First profitable quarter after a loss/i).length)
      .toBeGreaterThan(0);
    expect(screen.getByText('↗')).toBeInTheDocument();
  });

  it('NEGATIVE: a base too near zero says "≈0" and is NOT called a loss', () => {
    mockState.rows = [qrow('TINY', { income_qoq: null, income_base: 'too_small' })];
    renderPage();
    expect(screen.getByText('≈0')).toBeInTheDocument();
    expect(screen.queryByText('loss')).not.toBeInTheDocument();
    expect(screen.getByTitle(/rounding error/i)).toBeInTheDocument();
  });

  it('NEGATIVE: no two quarters on file is an em-dash, never a zero', () => {
    mockState.rows = [qrow('NODATA', { income_qoq: null, income_base: 'unknown',
                                       growth_qoq: null, growth_base: 'unknown' })];
    renderPage();
    const rows = screen.getAllByRole('row').filter((r) => !r.className.includes('--head'));
    expect(within(rows[0]).queryByText('+0%')).not.toBeInTheDocument();
    expect(within(rows[0]).getAllByText('—').length).toBeGreaterThan(0);
  });

  it('🔁 marks a move the name makes EVERY year at this point', () => {
    mockState.rows = [
      qrow('SEASON', { growth_qoq: 66, growth_qoq_ly: 64, growth_vs_seasonal: 2,
                       seasonal_echo: true }),
      qrow('REAL', { growth_qoq: 66, growth_qoq_ly: 4, growth_vs_seasonal: 62,
                     seasonal_echo: false }),
    ];
    renderPage();
    const echoes = screen.getAllByTitle(/same way at this point in its calendar last year/i);
    expect(echoes).toHaveLength(1);
  });

  it('the ranking chip says how much of the board could actually be ranked', () => {
    mockState.rows = [qrow('AAA', { qoq_score: 50, income_qoq: 10, growth_qoq: 10 })];
    renderPage();
    const chip = screen.getByRole('button', { name: /Income \+ growth/i });
    expect(chip).toHaveTextContent('250/250');
    expect(chip.title).toMatch(/ranked against their OWN prior-year transition/i);
    expect(chip.title).toMatch(/53/);            // the seasonal-echo count
  });

  it('switching to most-recent RE-REQUESTS the server, not a local re-sort', () => {
    // The order decides which 250 of ~2,840 candidates survive the cut, so it
    // cannot be a browser-side sort of the 250 already returned.
    mockState.rows = [qrow('AAA', { qoq_score: 50, income_qoq: 10, growth_qoq: 10 })];
    boardCalls.length = 0;
    renderPage();
    expect(boardCalls.at(-1)?.[3]).toBe('qoq');
    fireEvent.click(screen.getByRole('button', { name: /Income \+ growth/i }));
    expect(boardCalls.at(-1)?.[3]).toBe('recent');
  });

  it('NEGATIVE: a partial rankInfo must not blank the board', () => {
    /* `rawRank ?? {...}` only fires when the WHOLE object is missing, so a
       server that has not been redeployed hands over some fields and every
       .toLocaleString() throws. The same shape crashed this page on stageInfo
       earlier the same day. */
    const orig = mockState.rows;
    mockState.rows = [qrow('AAA', { qoq_score: 50 })];
    partialRank = true;
    try {
      renderPage();
      expect(screen.getByText('AAA')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Income \+ growth/i })).toBeInTheDocument();
    } finally {
      partialRank = false;
      mockState.rows = orig;
    }
  });

  it('the legend states the honest limit with its PLACEBO, not just the method', () => {
    mockState.rows = [qrow('AAA', {})];
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: /What is Breakout columns\?/i }));
    const legend = within(screen.getByRole('dialog', { name: /Breakout columns/i }));
    expect(legend.getByText(/did .worse. than the rest of the board|worse/i)).toBeInTheDocument();
    // A placebo beside every rate, per his standing rule — the seasonality
    // spread carries one AND so does the persistence result.
    expect(legend.getAllByText(/placebo/i).length).toBeGreaterThanOrEqual(2);
    expect(legend.getByText(/it does not predict/i)).toBeInTheDocument();
  });
});
