import { describe, it, expect } from 'vitest';
import { isBaseSetup } from './baseSetup';

describe('isBaseSetup', () => {
  it('is true for the three real-base setups', () => {
    expect(isBaseSetup('VCP')).toBe(true);
    expect(isBaseSetup('POWER_PLAY')).toBe(true);
    expect(isBaseSetup('POCKET_PIVOT')).toBe(true);
  });

  it('is false for a bare breakout (no base)', () => {
    expect(isBaseSetup('BREAKOUT')).toBe(false);
  });

  it('is false for null / undefined / unknown', () => {
    expect(isBaseSetup(null)).toBe(false);
    expect(isBaseSetup(undefined)).toBe(false);
    expect(isBaseSetup('')).toBe(false);
    expect(isBaseSetup('SOMETHING')).toBe(false);
  });
});
