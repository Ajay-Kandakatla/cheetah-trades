import { describe, it, expect } from 'vitest';
import { rowTotals, summarizePnl, tableTotals } from './autopilotPnl';

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

describe('rowTotals — cost / now / ± per position', () => {
  it('computes qty × entry and qty × last (the WST row from the screenshot)', () => {
    const t = rowTotals({ qty: 7, avg_entry: 331.08, last: 354.88 });
    expect(t.cost).toBeCloseTo(2317.56, 2);
    expect(t.value).toBeCloseTo(2484.16, 2);
    expect(t.pnl).toBeCloseTo(166.6, 2);
  });

  it('losing rows go negative', () => {
    const t = rowTotals({ qty: 90, avg_entry: 271.64, last: 263.21 });
    expect(t.pnl).toBeCloseTo(-758.7, 1);
  });

  it('missing/zero/garbage inputs give nulls, never NaN', () => {
    expect(rowTotals({ qty: 10, avg_entry: null, last: 50 }).cost).toBeNull();
    expect(rowTotals({ qty: 0, avg_entry: 100, last: 100 }).cost).toBeNull();
    expect(rowTotals({}).pnl).toBeNull();
    const t = rowTotals({ qty: 10, avg_entry: 100, last: null });
    expect(t.cost).toBeCloseTo(1000, 5);
    expect(t.value).toBeNull();
    expect(t.pnl).toBeNull();
  });
});

describe('tableTotals — the last-row sum of pluses and minuses', () => {
  const ROWS = [
    { qty: 7, avg_entry: 331.08, last: 354.88 },    // +166.60
    { qty: 90, avg_entry: 271.64, last: 263.21 },   // −758.70
    { qty: 649, avg_entry: 38.61, last: 39.87 },    // +817.74
  ];

  it('sums cost, value and net across rows', () => {
    const t = tableTotals(ROWS);
    expect(t.cost).toBeCloseTo(7 * 331.08 + 90 * 271.64 + 649 * 38.61, 2);
    expect(t.value).toBeCloseTo(7 * 354.88 + 90 * 263.21 + 649 * 39.87, 2);
    expect(t.pnl).toBeCloseTo(166.6 - 758.7 + 817.74, 2);
    expect(t.pct).toBeCloseTo((t.pnl / t.cost) * 100, 6);
    expect(t.nPriced).toBe(3);
  });

  it('rows without prices are excluded and counted', () => {
    const t = tableTotals([...ROWS, { qty: 5, avg_entry: 100, last: null }]);
    expect(t.nPriced).toBe(3);
    expect(t.nTotal).toBe(4);
  });

  it('empty table is a clean zero, pct null', () => {
    const t = tableTotals([]);
    expect(t.cost).toBe(0);
    expect(t.pnl).toBe(0);
    expect(t.pct).toBeNull();
  });
});
