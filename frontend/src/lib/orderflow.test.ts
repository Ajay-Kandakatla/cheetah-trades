/* Tape (order-flow) presentation helpers — pure-logic tests incl. negatives. */
import { describe, expect, it } from 'vitest';
import {
  accuracyLine, deltaTone, fmtDollars, fmtShares, sparklinePoints, verdictView,
} from './orderflow';

describe('verdictView', () => {
  it('maps the three verdicts to distinct tones', () => {
    expect(verdictView('BUY').label).toBe('BUY signal');
    expect(verdictView('AVOID').label).toBe('AVOID');
    expect(verdictView('WAIT').label).toBe('WAIT');
    expect(new Set([verdictView('BUY').color, verdictView('WAIT').color, verdictView('AVOID').color]).size).toBe(3);
  });
  it('defaults unknown/missing to WAIT (never a false green light)', () => {
    expect(verdictView(null).label).toBe('WAIT');
    expect(verdictView(undefined).label).toBe('WAIT');
  });
});

describe('formatters', () => {
  it('fmtDollars compacts magnitudes', () => {
    expect(fmtDollars(1_500_000_000)).toBe('$1.5B');
    expect(fmtDollars(4_339_519)).toBe('$4.3M');
    expect(fmtDollars(715_151)).toBe('$715K');
    expect(fmtDollars(42)).toBe('$42');
    expect(fmtDollars(-250_000)).toBe('−$250K');
  });
  it('fmtShares signs share counts', () => {
    expect(fmtShares(5_021_584)).toBe('+5.0M sh');
    expect(fmtShares(-6_314)).toBe('−6K sh');
    expect(fmtShares(0)).toBe('0 sh');
  });
  it('both survive null/undefined/NaN', () => {
    expect(fmtDollars(null)).toBe('—');
    expect(fmtShares(undefined)).toBe('—');
    expect(fmtDollars(NaN)).toBe('—');
  });
});

describe('deltaTone', () => {
  it('positive → buyers, negative → sellers, zero → balanced', () => {
    expect(deltaTone(1).word).toBe('buyers');
    expect(deltaTone(-1).word).toBe('sellers');
    expect(deltaTone(0).word).toBe('balanced');
  });
});

describe('sparklinePoints', () => {
  const series = (n: number): [string, number][] =>
    Array.from({ length: n }, (_, i) => [`t${i}`, i]);
  it('passes short series through untouched', () => {
    expect(sparklinePoints(series(10))).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  });
  it('downsamples long series but keeps the final value exact', () => {
    const pts = sparklinePoints(series(960), 240);
    expect(pts.length).toBe(240);
    expect(pts[pts.length - 1]).toBe(959);
  });
  it('handles empty input', () => {
    expect(sparklinePoints([])).toEqual([]);
  });
});

describe('accuracyLine', () => {
  it('null before any BUY signals exist', () => {
    expect(accuracyLine(null)).toBeNull();
    expect(accuracyLine({ verdicts: {} })).toBeNull();
    expect(accuracyLine({ verdicts: { BUY: { n: 0, hit_1d_pct: null } } })).toBeNull();
  });
  it('reports recorded-but-ungraded signals honestly', () => {
    expect(accuracyLine({ verdicts: { BUY: { n: 3, hit_1d_pct: null } } }))
      .toBe('3 BUY signals recorded — grading starts at T+1');
  });
  it('adds the small-n caveat under 30 signals and drops it after', () => {
    const small = accuracyLine({ verdicts: { BUY: { n: 12, hit_1d_pct: 66.7 } } })!;
    expect(small).toContain('66.7%');
    expect(small).toContain('small n');
    const big = accuracyLine({ verdicts: { BUY: { n: 45, hit_1d_pct: 71.1 } } })!;
    expect(big).not.toContain('small n');
  });
});
