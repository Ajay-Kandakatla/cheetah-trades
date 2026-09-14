import { describe, it, expect } from 'vitest';
import { compactUsd, dilutionCell, cashDebtCell, evSalesCell, fcfYieldCell,
         metricCells, signedPct, DILUTION_BLANK } from './boardMetrics';
import { SORT_KEYS, SORT_LABEL, initialDir, sortValue } from './growthSort';

/* The four CPA columns (Ajay 2026-09-13).
 *
 * These cells are numbers a reader acts on, so the negatives matter more than
 * the happy path: a blank that reads as a zero, a withheld value that renders
 * as a number, or a refusal with no explanation are each worse than a missing
 * column. */

describe('formatting', () => {
  it('signs percentages with a real minus, not a hyphen', () => {
    expect(signedPct(12.35)).toBe('+12.3%');
    expect(signedPct(-1.04)).toBe('−1.0%');
    expect(signedPct(0)).toBe('0.0%');
  });

  it('compacts dollars at every magnitude, negatives included', () => {
    expect(compactUsd(19_646_000_640)).toBe('$19.6B');
    expect(compactUsd(-6_812_999_936)).toBe('−$6.8B');
    expect(compactUsd(-440_523_992)).toBe('−$441M');
    expect(compactUsd(4_560_999_872)).toBe('$4.6B');
    // Sub-thousand keeps no decimal once it is 3 digits — "$950.0" is false
    // precision on a number this small.
    expect(compactUsd(950)).toBe('$950');
    expect(compactUsd(9.5)).toBe('$9.5');
  });
});

describe('dilution cell', () => {
  it('reads the number and calls a buyback good', () => {
    const c = dilutionCell({ shares_yoy_pct: -1.0, shares_yoy_period: 'Q2 2026' });
    expect(c.text).toBe('−1.0%');
    expect(c.tone).toBe('good');
    expect(c.title).toMatch(/buying back/i);
  });

  it('escalates tone with the size of the issuance', () => {
    expect(dilutionCell({ shares_yoy_pct: 1.8 }).tone).toBe('');
    expect(dilutionCell({ shares_yoy_pct: 11.8 }).tone).toBe('warn');
    expect(dilutionCell({ shares_yoy_pct: 321.2 }).tone).toBe('bad');
  });

  it('NEGATIVE — a blank explains WHICH refusal it was', () => {
    // A blank with no explanation reads as a bug. Each of these is a fact
    // about the filing, and the RKT one names the company so the next reader
    // does not re-diagnose it.
    for (const reason of Object.keys(DILUTION_BLANK)) {
      const c = dilutionCell({ shares_yoy_pct: null, shares_yoy_reason: reason });
      expect(c.text).toBe('—');
      expect(c.tone).toBe('dim');
      expect(c.title.length).toBeGreaterThan(40);
    }
    expect(DILUTION_BLANK.unstable_share_basis).toMatch(/Rocket Companies/);
    expect(DILUTION_BLANK.unstable_share_basis).toMatch(/1,559%/);
  });

  it('NEGATIVE — a missing value is never rendered as zero', () => {
    for (const v of [null, undefined, NaN, Infinity]) {
      expect(dilutionCell({ shares_yoy_pct: v as any }).text).toBe('—');
    }
  });
});

describe('balance cells withhold what they cannot mean', () => {
  const reit = { sector: 'Real Estate', balance_meaningful: false,
                 cash_minus_debt: -17_879_857_024, ev_sales: 40.996, fcf_yield: null };

  it('NEGATIVE — a non-operating sector shows n/a, not the raw number', () => {
    // ARR really does measure EV/Sales at 41x. Printing that next to a
    // software name at 12x invites exactly the wrong comparison.
    for (const cell of [cashDebtCell(reit), evSalesCell(reit), fcfYieldCell(reit)]) {
      expect(cell.text).toBe('n/a');
      expect(cell.tone).toBe('dim');
      expect(cell.title).toMatch(/Real Estate/);
    }
  });

  it('an operating name shows all three', () => {
    const r = { sector: 'Technology', balance_meaningful: true,
                cash: 26_022_000_640, debt: 6_376_000_000,
                cash_minus_debt: 19_646_000_640, ev_sales: 11.984, fcf_yield: 0.69 };
    expect(cashDebtCell(r).text).toBe('$19.6B');
    expect(cashDebtCell(r).tone).toBe('good');
    expect(cashDebtCell(r).title).toMatch(/Cash \$26\.0B against debt \$6\.4B/);
    expect(evSalesCell(r).text).toBe('12×');
    expect(fcfYieldCell(r).text).toBe('+0.7%');
  });

  it('calls a cash burn bad and says so in words', () => {
    const c = fcfYieldCell({ balance_meaningful: true, fcf_yield: -100.49 });
    expect(c.text).toBe('−100.5%');
    expect(c.tone).toBe('bad');
    expect(c.title).toMatch(/BURNING cash/);
  });

  it('NEGATIVE — an empty row yields four dashes and never throws', () => {
    const cells = metricCells({});
    expect(cells).toHaveLength(4);
    expect(cells.map((c) => c.text)).toEqual(['—', '—', '—', '—']);
    for (const c of cells) expect(c.title.length).toBeGreaterThan(10);
  });
});

describe('the columns sort', () => {
  it('all four are sortable keys with labels', () => {
    for (const k of ['shares_yoy_pct', 'cash_minus_debt', 'ev_sales', 'fcf_yield'] as const) {
      expect(SORT_KEYS).toContain(k);
      expect(SORT_LABEL[k].length).toBeGreaterThan(3);
    }
  });

  it('EV/Sales opens CHEAPEST first, dilution opens WORST first', () => {
    // EV/Sales is a price tag — the reason to open it is to find what is cheap.
    // Dilution is a risk column — the row that matters is the heaviest issuer.
    expect(initialDir('ev_sales')).toBe('asc');
    expect(initialDir('shares_yoy_pct')).toBe('desc');
    expect(initialDir('fcf_yield')).toBe('desc');
  });

  it('NEGATIVE — a refused value sorts as UNKNOWN, not as zero', () => {
    // A dilution figure the app refused to compute must never outrank a
    // measured one in either direction.
    expect(sortValue({ symbol: 'A', shares_yoy_pct: null }, 'shares_yoy_pct').known).toBe(false);
    expect(sortValue({ symbol: 'A', shares_yoy_pct: 0 }, 'shares_yoy_pct').known).toBe(true);
  });
});
