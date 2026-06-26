import { describe, it, expect } from 'vitest';
import { LEAN_VISUAL, TIER_COLOR, flagLabel, confLabel } from './tomorrowBias';

describe('tomorrowBias presentation helpers', () => {
  it('every lean has a visual; up is green, down is red', () => {
    expect(LEAN_VISUAL.LEAN_UP.color).toBe('#10b981');
    expect(LEAN_VISUAL.LEAN_DOWN.color).toBe('#ef4444');
    expect(LEAN_VISUAL.NEUTRAL.arrow).toBe('●');
  });

  it('tier colors exist for all three tiers', () => {
    expect(TIER_COLOR.HIGH).toBeTruthy();
    expect(TIER_COLOR.MEDIUM).toBeTruthy();
    expect(TIER_COLOR.LOW).toBeTruthy();
  });

  it('known flags map to a human caveat', () => {
    expect(flagLabel('thin_print')).toMatch(/thin after-hours/i);
    expect(flagLabel('event_risk')).toMatch(/event|earnings/i);
    expect(flagLabel('fighting_the_tape')).toMatch(/tape/i);
  });

  it('earnings_source flag is decoded with its source', () => {
    expect(flagLabel('earnings_source:iv_inferred')).toMatch(/implied volatility/i);
  });

  it('unknown flags never render raw snake_case', () => {
    // negative: a brand-new backend flag must still be readable
    expect(flagLabel('some_new_backend_flag')).toBe('some new backend flag');
  });

  it('confLabel shows tier alone when no number, tier · n with one', () => {
    expect(confLabel('LOW')).toBe('LOW');
    expect(confLabel('HIGH', 78)).toBe('HIGH · 78');
    expect(confLabel('MEDIUM', 0)).toBe('MEDIUM · 0');   // 0 is a real value, not missing
  });
});
