import { describe, it, expect } from 'vitest';
import { marketBorderColor } from './MarketDayBorder';

const RED = '#ef4444', AMBER = '#f59e0b', GREEN = '#10b981', GRAY = '#6b7280';

describe('marketBorderColor — regime-led', () => {
  it('is RED in a confirmed correction (defensive — sit out new buys)', () => {
    expect(marketBorderColor('market_in_correction', 'caution')).toBe(RED);
  });

  it('REGRESSION: a correction that still scores in the "caution" band is RED, not gray', () => {
    // Ajay 2026-06-23: the gauge sat at 59 (caution) during a market_in_correction
    // with the portfolio -8.7%; the old score-only border rendered gray.
    expect(marketBorderColor('market_in_correction', 'caution')).toBe(RED);
    expect(marketBorderColor('market_in_correction', 'constructive')).toBe(RED);
  });

  it('is RED whenever the gauge itself flags risk_off, regardless of regime', () => {
    expect(marketBorderColor('confirmed_uptrend', 'risk_off')).toBe(RED);
    expect(marketBorderColor(null, 'risk_off')).toBe(RED);
  });

  it('is AMBER when the uptrend is under pressure', () => {
    expect(marketBorderColor('uptrend_under_pressure', 'caution')).toBe(AMBER);
  });

  it('is GREEN in a confirmed uptrend', () => {
    expect(marketBorderColor('confirmed_uptrend', 'constructive')).toBe(GREEN);
    expect(marketBorderColor('confirmed_uptrend', 'caution')).toBe(GREEN);
  });

  it('falls back to the gauge (green on constructive) before the regime loads', () => {
    expect(marketBorderColor(null, 'constructive')).toBe(GREEN);
  });

  it('is GRAY when nothing is known yet (loading)', () => {
    expect(marketBorderColor(null, null)).toBe(GRAY);
    expect(marketBorderColor(undefined, undefined)).toBe(GRAY);
  });
});
