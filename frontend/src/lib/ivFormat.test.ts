import { describe, it, expect } from 'vitest';
import { asOfDay, fmtRatio, ivArrow, ivRegimeWord, ivTitle, ordinal, spyCurveText } from './ivFormat';
import type { MarketIv } from '../hooks/useMarketIv';

/* ivFormat — pure formatting behind the nav IvBadge + the /market-gauge card. */

describe('ordinal', () => {
  it('handles the English suffix rules incl. the 11-13 exception', () => {
    expect(ordinal(1)).toBe('1st');
    expect(ordinal(2)).toBe('2nd');
    expect(ordinal(3)).toBe('3rd');
    expect(ordinal(4)).toBe('4th');
    expect(ordinal(11)).toBe('11th');
    expect(ordinal(12)).toBe('12th');
    expect(ordinal(13)).toBe('13th');
    expect(ordinal(21)).toBe('21st');
    expect(ordinal(22)).toBe('22nd');
    expect(ordinal(93)).toBe('93rd');
    expect(ordinal(100)).toBe('100th');
    expect(ordinal(111)).toBe('111th');
  });
  it('rounds a fractional percentile first', () => {
    expect(ordinal(4.6)).toBe('5th');
    expect(ordinal(0.2)).toBe('0th');
  });
});

describe('ivArrow', () => {
  it('▲/▼ with one decimal once the change is at least a tenth', () => {
    expect(ivArrow(0.2)).toBe('▲0.2');
    expect(ivArrow(-1.34)).toBe('▼1.3');
    expect(ivArrow(0.1)).toBe('▲0.1');
  });
  it('empty below a tenth, for null and for non-finite input', () => {
    expect(ivArrow(0.04)).toBe('');
    expect(ivArrow(-0.09)).toBe('');
    expect(ivArrow(0)).toBe('');
    expect(ivArrow(null)).toBe('');
    expect(ivArrow(undefined)).toBe('');
    expect(ivArrow(Number.NaN)).toBe('');
  });
});

describe('ivRegimeWord / fmtRatio / asOfDay', () => {
  it('prefers the backend label, else capitalises the key, else empty', () => {
    expect(ivRegimeWord({ regime: 'stress', regime_label: 'Stress' })).toBe('Stress');
    expect(ivRegimeWord({ regime: 'elevated', regime_label: null })).toBe('Elevated');
    expect(ivRegimeWord({ regime: null, regime_label: null })).toBe('');
  });
  it('fmtRatio renders 2dp or an em dash', () => {
    expect(fmtRatio(1.157)).toBe('1.16');
    expect(fmtRatio(null)).toBe('—');
    expect(fmtRatio(undefined)).toBe('—');
    expect(fmtRatio(Number.NaN)).toBe('—');
  });
  it('asOfDay gives the short weekday from a YYYY-MM-DD without rolling the day', () => {
    expect(asOfDay('2026-09-04')).toBe('Fri');
    expect(asOfDay('2026-09-08')).toBe('Tue');
    expect(asOfDay(null)).toBe('');
    expect(asOfDay('')).toBe('');
    expect(asOfDay('not-a-date')).toBe('not-a-date');
  });
});

const BASE: MarketIv = {
  vix: 14.5, prev: 14.3, chg: 0.2, chg_pct: 1.4, pct_252: 5,
  regime: 'calm', regime_label: 'Calm',
  bands: { calm_below: 15, normal_below: 20, elevated_below: 30 },
  term: { vix9d: 16.8, vix3m: 20.4, ratio_9d_30d: 1.16, ratio_30d_3m: 0.71, shape: 'contango', as_of: '2026-09-04' },
  vvix: 84, as_of: '2026-09-04', read: 'Quiet tape.',
  generated_at: 0, age_sec: 0, disclaimer: '',
};

describe('ivTitle', () => {
  it('composes the documented one-liner', () => {
    expect(ivTitle(BASE)).toBe(
      'VIX 14.5 (▲0.2) · Calm · 5th pct of the year · 9D/30D 1.16 · 30D/3M 0.71 contango · VVIX 84 · as of Fri — Quiet tape.',
    );
  });
  it('drops every null piece instead of printing "null"', () => {
    const t = ivTitle({ ...BASE, chg: null, pct_252: null, term: null, vvix: null, as_of: null, read: '' });
    expect(t).toBe('VIX 14.5 · Calm');
    expect(t).not.toContain('null');
  });
  it('keeps the term ratios even when the shape is unknown', () => {
    const t = ivTitle({ ...BASE, term: { ...BASE.term!, shape: null } });
    expect(t).toContain('30D/3M 0.71 · VVIX 84');
    expect(t).not.toContain('contango');
  });
});

describe('spyCurveText (live SPY curve, 2026-09-06)', () => {
  const spy = { ...BASE.term!, source: 'spy_chain', iv9d: 9.89, iv30d: 12.2, iv90d: 14.06,
                ratio_9d_30d: 0.811, ratio_30d_3m: 0.868, ratio_30d_90d: 0.868, shape: 'contango' as const };
  it('prints the three tenors in percent', () => {
    expect(spyCurveText(spy)).toBe('SPY IV 9d/30d/90d 9.9/12.2/14.1%');
  });
  it('is empty for the CBOE fallback or without a 30d point', () => {
    expect(spyCurveText(BASE.term)).toBe('');
    expect(spyCurveText({ ...spy, iv30d: null })).toBe('');
    expect(spyCurveText(null)).toBe('');
  });
  it('dashes a missing tenor and rides inside the title', () => {
    expect(spyCurveText({ ...spy, iv90d: null })).toBe('SPY IV 9d/30d/90d 9.9/12.2/—%');
    const t = ivTitle({ ...BASE, term: spy });
    expect(t).toContain('SPY IV 9d/30d/90d 9.9/12.2/14.1%');
    expect(t).toContain('30D/3M 0.87 contango');
  });
});
