import { describe, it, expect } from 'vitest';
import { marketBorderColor } from './MarketDayBorder';

describe('marketBorderColor', () => {
  it('is red on a risk-off market day', () => {
    expect(marketBorderColor('risk_off')).toBe('#ef4444');
  });
  it('is green when constructive (a positive day)', () => {
    expect(marketBorderColor('constructive')).toBe('#10b981');
  });
  it('is gray on a caution / normal day', () => {
    expect(marketBorderColor('caution')).toBe('#6b7280');
  });
  it('defaults to gray for unknown / still-loading (null/undefined)', () => {
    expect(marketBorderColor(null)).toBe('#6b7280');
    expect(marketBorderColor(undefined)).toBe('#6b7280');
  });
});
