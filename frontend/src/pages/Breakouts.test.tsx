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
