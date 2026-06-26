import { describe, it, expect } from 'vitest';
import { summarizePnl } from './autopilotPnl';

describe('summarizePnl — started → now', () => {
  it('reports now (equity) and the gain together', () => {
    const v = summarizePnl({
      starting_cash: 100000, equity: 100138,
      total_pnl_dollars: 138, total_pnl_pct: 0.138,
      realized_dollars: 0, unrealized_dollars: 138,
    });
    expect(v.startingCash).toBe(100000);
    expect(v.now).toBe(100138);
    expect(v.gain).toBe(138);
    expect(v.up).toBe(true);
  });

  it('falls back to equity − starting when total_pnl_dollars is null', () => {
    const v = summarizePnl({
      starting_cash: 100000, equity: 99000,
      total_pnl_dollars: null, total_pnl_pct: null,
    });
    expect(v.gain).toBe(-1000);
    expect(v.up).toBe(false);
    expect(v.pct).toBeCloseTo(-1.0, 5);
  });

  it('handles zero starting cash without dividing by zero', () => {
    const v = summarizePnl({ starting_cash: 0, equity: 0, total_pnl_dollars: 0, total_pnl_pct: null });
    expect(v.pct).toBeNull();
    expect(v.up).toBe(true);   // 0 gain counts as not-down
  });
});
