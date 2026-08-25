/* Tape (order-flow) presentation helpers — pure-logic tests incl. negatives. */
import { describe, expect, it } from 'vitest';
import { accuracyLine, classificationView, darkShareView, deltaTone, fmtDollars, fmtShares, fmtSharesAbs, sparklinePoints, verdictView } from './orderflow';

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

describe('classificationView — delta must say how it was computed', () => {
  it('labels a real quote-rule run and quantifies how wrong the tick rule was', () => {
    const v = classificationView({
      method: 'quote', coverage_pct: 83.3, trustworthy: true, tick_agreement_pct: 76.4,
    });
    expect(v.label).toBe('quote rule');
    expect(v.title).toContain('83.3%');
    expect(v.title).toContain('76.4%');
  });

  it('warns when quote coverage is too thin to headline', () => {
    const v = classificationView({ method: 'mixed', coverage_pct: 41, trustworthy: false, tick_agreement_pct: null });
    expect(v.label).toContain('41');
    expect(v.color).toBe('#d97706');
  });

  it('says plainly when it fell back to the tick rule', () => {
    const v = classificationView({ method: 'tick', coverage_pct: 0, trustworthy: false, tick_agreement_pct: null });
    expect(v.label).toBe('tick rule');
    expect(v.title).toContain('75-80%');
  });

  it('is quiet when there is nothing to classify', () => {
    expect(classificationView(undefined).label).toBe('unclassified');
    expect(classificationView({ method: 'none' } as never).label).toBe('unclassified');
  });
});

describe('darkShareView', () => {
  it('highlights an unusually dark session', () => {
    expect(darkShareView(62, true)).toEqual({ label: '62%', color: '#a78bfa' });
  });
  it('stays neutral on a normal mix', () => {
    expect(darkShareView(39.1, false).label).toBe('39.1%');
    expect(darkShareView(39.1, false).color).toBe('#cbd5e1');
  });
  it('is quiet when venue data is unavailable', () => {
    expect(darkShareView(null).label).toBe('—');
    expect(darkShareView(undefined).label).toBe('—');
  });
});

describe('fmtSharesAbs — volumes are not signed quantities', () => {
  it('drops the sign fmtShares adds for deltas', () => {
    expect(fmtShares(1_500_000)).toBe('+1.5M sh');
    expect(fmtSharesAbs(1_500_000)).toBe('1.5M sh');
    expect(fmtSharesAbs(-1_500_000)).toBe('1.5M sh');
  });
  it('stays quiet on missing values', () => {
    expect(fmtSharesAbs(null)).toBe('—');
    expect(fmtSharesAbs(undefined)).toBe('—');
  });
});

// ── binDelta (Big Delta per candle, Ajay 2026-08-24) ─────────────────────────
import { binDelta } from './orderflow';

describe('binDelta', () => {
  const mk = (vals: number[]): [string, number][] =>
    vals.map((v, i) => [`2026-08-24T14:${String(i).padStart(2, '0')}:00`, v]);

  it('passes a short series through untouched', () => {
    expect(binDelta(mk([5, -3, 8]), 130)).toEqual([5, -3, 8]);
  });

  it('bins by SUMMING, so the total delta is preserved exactly', () => {
    const vals = Array.from({ length: 390 }, (_, i) => (i % 2 ? 100 : -60));
    const total = vals.reduce((a, b) => a + b, 0);
    const bars = binDelta(mk(vals), 130);
    expect(bars.length).toBeLessThanOrEqual(130);
    expect(bars.reduce((a, b) => a + b, 0)).toBe(total);
  });

  it('a single dominant minute survives binning rather than being sampled away', () => {
    // 389 quiet minutes and one +80,000 spike: sampling could drop it entirely;
    // summing cannot — some bar must carry it.
    const vals = Array(390).fill(10);
    vals[200] = 80_000;
    const bars = binDelta(mk(vals), 130);
    expect(Math.max(...bars)).toBeGreaterThanOrEqual(80_000);
  });

  it('ignores non-finite values instead of poisoning a bin', () => {
    expect(binDelta(mk([5, NaN as unknown as number, 7]), 130)).toEqual([5, 7]);
  });

  it('handles an empty or missing series', () => {
    expect(binDelta([], 130)).toEqual([]);
    expect(binDelta(undefined as unknown as [string, number][], 130)).toEqual([]);
  });
});
