import { describe, it, expect } from 'vitest';
import { isCheatRegime, isCheatVisible } from './cheat';

describe('isCheatRegime (red market + no pivots)', () => {
  it('is true only in a risk_off market with zero buyable pivots', () => {
    expect(isCheatRegime('risk_off', 0)).toBe(true);
  });

  it('is false when the market is not red, even with no pivots', () => {
    expect(isCheatRegime('constructive', 0)).toBe(false);
    expect(isCheatRegime('caution', 0)).toBe(false);
  });

  it('is false in a red market that still has buyable pivots', () => {
    expect(isCheatRegime('risk_off', 3)).toBe(false);
    expect(isCheatRegime('risk_off', 1)).toBe(false);
  });

  it('treats null/undefined buyableCount as zero pivots', () => {
    expect(isCheatRegime('risk_off', null)).toBe(true);
    expect(isCheatRegime('risk_off', undefined)).toBe(true);
  });

  it('is false when the gauge state is missing', () => {
    expect(isCheatRegime(null, 0)).toBe(false);
    expect(isCheatRegime(undefined, 0)).toBe(false);
  });
});

describe('isCheatVisible (row flag + regime)', () => {
  it('shows only when the row is a cheat AND the regime is open', () => {
    expect(isCheatVisible(true, true)).toBe(true);
  });

  it('is hidden when the row is not a cheat', () => {
    expect(isCheatVisible(false, true)).toBe(false);
    expect(isCheatVisible(null, true)).toBe(false);
    expect(isCheatVisible(undefined, true)).toBe(false);
  });

  it('is hidden when the regime gate is closed (green/caution or pivots exist)', () => {
    expect(isCheatVisible(true, false)).toBe(false);
    expect(isCheatVisible(true, undefined)).toBe(false);
  });
});
