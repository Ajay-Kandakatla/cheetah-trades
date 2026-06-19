import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AnalyticsView } from './Trading';

/* AnalyticsView — the Auto-Pilot batting-average view. These lock the
   2026-06-19 "by venue" split: the headline stats stay the COMBINED continuous
   record across the sim -> paper cutover, while a per-venue table shows sim vs
   live-paper accuracy. Negatives: absent by_source still renders (no crash),
   and the error state shows. */

function mk(overrides: Record<string, unknown> = {}) {
  return {
    n_closed: 6, n_open: 0, provisional: true,
    batting_avg: 0.5, avg_gain_pct: 10, avg_loss_pct: 5,
    win_loss_ratio: 2, expectancy_pct: 2.5, expectancy_dollars: 30,
    avg_r: 0.7, total_pnl_dollars: 177.8, avg_holding_days: 3,
    equity_curve: [{ epoch: 1, cum_pnl_dollars: 50 }, { epoch: 2, cum_pnl_dollars: 177.8 }],
    by_trigger: {}, open_risk_dollars: 0,
    vs_book: { target_ratio: 2, stretch_ratio: 3, your_ratio: 2,
               batting_ref: 0.5, half_avg_gain_stop_pct: 5, flags: [] },
    ...overrides,
  };
}

describe('AnalyticsView · by-venue split', () => {
  it('renders sim + paper venue rows and the combined-record note', () => {
    const a = mk({
      by_source: {
        sim: { n: 6, batting_avg: 0.5, avg_gain_pct: 10, avg_loss_pct: 5 },
        paper: { n: 2, batting_avg: 1, avg_gain_pct: 12 },
      },
    });
    render(<AnalyticsView a={a as never} err={false} />);
    expect(screen.getByText(/By venue/)).toBeTruthy();
    expect(screen.getByText('SIM (paper)')).toBeTruthy();
    expect(screen.getByText('Alpaca paper')).toBeTruthy();
    // The headline stays the COMBINED record across both venues.
    expect(screen.getByText(/combined/i)).toBeTruthy();
  });

  it('still renders the venue table when by_source is absent (no crash)', () => {
    render(<AnalyticsView a={mk() as never} err={false} />);
    expect(screen.getByText('SIM (paper)')).toBeTruthy();   // empty row, n=0
    expect(screen.getByText('Alpaca paper')).toBeTruthy();
  });

  it('shows the error state when analytics fails to load', () => {
    render(<AnalyticsView a={null} err={true} />);
    expect(screen.getByText(/Can't load analytics/)).toBeTruthy();
  });
});
