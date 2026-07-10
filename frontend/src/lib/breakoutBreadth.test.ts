/* Breakout Breadth strip helpers — pure-logic tests incl. negatives. */
import { describe, expect, it } from 'vitest';
import { countLine, ftSplit, readColor } from './breakoutBreadth';

describe('readColor', () => {
  it('green when expanding/healthy, red when hostile, amber otherwise', () => {
    expect(readColor('EXPANDING')).toBe('#10b981');
    expect(readColor('HEALTHY')).toBe('#10b981');
    expect(readColor('HOSTILE')).toBe('#ef4444');
    expect(readColor('MIXED')).toBe('#d97706');
    expect(readColor(undefined)).toBe('#d97706');
  });
});

describe('countLine', () => {
  it('labels expansion, contraction and steady honestly', () => {
    expect(countLine(60, 40)).toContain('expanding');
    expect(countLine(36, 121)).toContain('contracting');   // the live 7/09 read
    expect(countLine(40, 42)).toContain('steady');
  });
  it('degrades without data', () => {
    expect(countLine(undefined, 40)).toBe('—');
    expect(countLine(25, 0)).toBe('25 breakouts today');
  });
});

describe('ftSplit', () => {
  it('fractions sum to ~1', () => {
    const s = ftSplit({ n: 100, followed_through: 55, failed: 40, stalled: 5,
                        failure_rate: 0.4, window_bars: 5 })!;
    expect(s.ft + s.fail + s.stall).toBeCloseTo(1, 6);
    expect(s.fail).toBeCloseTo(0.4, 6);
  });
  it('null when nothing graded yet', () => {
    expect(ftSplit(undefined)).toBeNull();
    expect(ftSplit({ n: 0, followed_through: 0, failed: 0, stalled: 0,
                     failure_rate: null, window_bars: 5 })).toBeNull();
  });
});
