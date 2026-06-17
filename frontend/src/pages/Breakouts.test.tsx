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
vi.mock('../hooks/useBreakoutBoard', () => ({
  useBreakoutBoard: () => ({ ...mockState, scanTs: 1, reload: vi.fn() }),
}));

import { BreakoutsPage } from './Breakouts';

const verdict = (mPass: boolean, bPass: boolean | null) => ({
  status: mPass ? 'pass' : 'fail', label: mPass ? 'PASS' : 'FAIL', icon: mPass ? '🟢' : '🔴',
  tone: '#10b981', both_pass: mPass && bPass === true, buyable_now: false,
  sales_pending: bPass === null,
  minervini: { passed: mPass, buyable_now: false, stage: 2, reason: 'r', cite: 'p.79' },
  bonde: { passed: bPass, pending: bPass === null, tier: 't', score: 50, growth_yoy_pct: 10, reason: 'r', cite: 'Bonde' },
});

const row = (symbol: string, count: number, mPass: boolean, bPass: boolean | null): BreakoutBoardRow => ({
  symbol, name: `${symbol} Inc`, breakout_count: count, days_since_breakout: 0,
  high_vol_breakout: true, broke_out_today: true, last_close: 100, day_change_pct: 1.2,
  rs_rank: 90, stage: 2, is_etf: false, buy_verdict: verdict(mPass, bPass) as any,
});

const renderPage = () => render(<MemoryRouter><BreakoutsPage /></MemoryRouter>);

beforeEach(() => {
  mockState = {
    rows: [
      row('BBB', 9, true, true),    // both pass
      row('CCC', 5, true, false),   // Minervini pass, Bonde fail
      row('AAA', 2, false, true),   // Minervini fail, Bonde pass
    ],
    summary: { total: 3, broke_out_today: 3, minervini_pass: 2, minervini_fail: 1, bonde_pass: 2, bonde_fail: 1, both_pass: 1 },
    loading: false, error: null,
  };
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
    mockState = { rows: [], summary: { total: 0, broke_out_today: 0, minervini_pass: 0, minervini_fail: 0, bonde_pass: 0, bonde_fail: 0, both_pass: 0 }, loading: false, error: null };
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
  avg_vol_50: o.avg, day_change_pct: o.chg, rs_rank: 90, stage: 2, is_etf: false,
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
      summary: { total: 3, broke_out_today: 3, minervini_pass: 3, minervini_fail: 0, bonde_pass: 3, bonde_fail: 0, both_pass: 3 },
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

  it('defaults to turnover descending (highest dollar volume first)', () => {
    renderPage();
    const rows = dataRows();
    expect(within(rows[0]).getByText('HIGH')).toBeInTheDocument();  // $500M
    expect(within(rows[1]).getByText('MID')).toBeInTheDocument();   // $100M
    expect(within(rows[2]).getByText('LOW')).toBeInTheDocument();   // $10M
    expect(turnoverHeader().textContent).toContain('▼');
  });

  it('toggles the turnover sort direction on each header click (desc → asc → desc)', () => {
    renderPage();
    expect(turnoverHeader().textContent).toContain('▼');          // desc default
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
      summary: { total: 2, broke_out_today: 1, minervini_pass: 2, minervini_fail: 0, bonde_pass: 2, bonde_fail: 0, both_pass: 2 },
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
  avg_vol_50: 1_000_000, day_change_pct: 1.0, rs_rank: 90, stage: o.stage,
  stage_label: o.stage != null ? `Stage ${o.stage}` : null, r1: o.r1, r2: o.r2,
  is_etf: false, buy_verdict: verdict(true, true) as any,
});

const marchHeader = () => screen.getByRole('button', { name: /R1\/R2/ });
const stageHeader = () => screen.getByRole('button', { name: /Stage/ });

describe('BreakoutsPage — Stage + → R1/R2 columns', () => {
  beforeEach(() => {
    mockState = {
      rows: [
        srow('BELOW', { stage: 2, price: 100, r1: 110, r2: 120 }),  // → R1 +10%
        srow('MID',   { stage: 4, price: 112, r1: 110, r2: 120 }),  // cleared R1 → R2
        srow('PAST',  { stage: 1, price: 130, r1: 110, r2: 120 }),  // past R2
      ],
      summary: { total: 3, broke_out_today: 3, minervini_pass: 3, minervini_fail: 0, bonde_pass: 3, bonde_fail: 0, both_pass: 3 },
      loading: false, error: null,
    };
  });

  it('renders the Stage column — ✓ S2 highlighted, S4 / S1 plain', () => {
    renderPage();
    expect(screen.getByText('✓ S2')).toBeInTheDocument();    // Stage 2 = buyable
    expect(screen.getByText('S4')).toBeInTheDocument();      // Stage 4 = avoid
    expect(screen.getByText('S1')).toBeInTheDocument();
  });

  it('renders the marching-toward column for each branch (→ R1 / → R2 / Past R2)', () => {
    renderPage();
    expect(screen.getByText(/→ R1 \+10\.00%/)).toBeInTheDocument();   // below R1
    expect(screen.getByText(/→ R2/)).toBeInTheDocument();             // between R1/R2
    expect(screen.getByText(/Past R2/)).toBeInTheDocument();          // extended
  });

  it('sorts by distance-to-target ascending when → R1/R2 header is clicked', () => {
    renderPage();
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
});
