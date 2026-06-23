import { describe, it, expect } from 'vitest';
import { marketPosture } from './MarketPostureBanner';

describe('marketPosture — regime-led top banner', () => {
  it('reads RED "Market in correction" in a confirmed correction', () => {
    expect(marketPosture('market_in_correction', 'caution')).toEqual({
      label: 'Market in correction', tone: 'red',
    });
  });

  it('a correction in the caution score-band is still RED', () => {
    expect(marketPosture('market_in_correction', 'caution')?.tone).toBe('red');
  });

  it('RED whenever the gauge flags risk_off', () => {
    expect(marketPosture('confirmed_uptrend', 'risk_off')?.tone).toBe('red');
  });

  it('AMBER when the uptrend is under pressure', () => {
    expect(marketPosture('uptrend_under_pressure', 'caution')).toEqual({
      label: 'Uptrend under pressure', tone: 'amber',
    });
  });

  it('GREEN in a confirmed uptrend / constructive gauge', () => {
    expect(marketPosture('confirmed_uptrend', 'constructive')?.tone).toBe('green');
    expect(marketPosture(null, 'constructive')?.tone).toBe('green');
  });

  it('hides (null) while nothing is known yet — no pill on load', () => {
    expect(marketPosture(null, null)).toBeNull();
    expect(marketPosture(undefined, undefined)).toBeNull();
  });
});
