import { describe, it, expect } from 'vitest';
import { isBaseSetup, setupBadge } from './baseSetup';

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

describe('setupBadge — Breakouts board setup flag (2026-08-03)', () => {
  it('badges the three real bases with VCP detail in the tooltip', () => {
    expect(setupBadge('VCP')).toMatchObject({ icon: '📐', label: 'VCP' });
    expect(setupBadge('VCP')!.title).toContain('Volatility Contraction');
    expect(setupBadge('POWER_PLAY')!.label).toBe('PP');
    expect(setupBadge('POCKET_PIVOT')!.label).toBe('PKT');
  });

  it('quiet for bare breakouts, unknown types, and missing setups', () => {
    expect(setupBadge('BREAKOUT')).toBeNull();
    expect(setupBadge('SOMETHING_NEW')).toBeNull();
    expect(setupBadge(null)).toBeNull();
    expect(setupBadge(undefined)).toBeNull();
  });
});
