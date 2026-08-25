/* ema — the maths under the 9/21 overlay. A wrong EMA is worse than none:
 * it draws a confident trend line that isn't the indicator anyone else sees. */
import { describe, expect, it } from 'vitest';
import { EMA_FAST, EMA_SLOW, emaAlpha, emaSeries, emaStep } from './ema';

describe('emaSeries', () => {
  it('seeds with the SMA of the first period values', () => {
    // First 3 of [2,4,6,...]: SMA = 4. Nothing before it.
    const s = emaSeries([2, 4, 6, 8], 3);
    expect(s[0]).toBeNull();
    expect(s[1]).toBeNull();
    expect(s[2]).toBe(4);
  });

  it('recurses with alpha = 2/(period+1) after the seed', () => {
    // period 3 -> a = 0.5. EMA_3 = 0.5*8 + 0.5*4 = 6.
    const s = emaSeries([2, 4, 6, 8], 3);
    expect(s[3]).toBeCloseTo(6, 10);
  });

  it('a constant series is its own EMA — no drift from the arithmetic', () => {
    const s = emaSeries(Array(50).fill(100), EMA_FAST);
    expect(s[49]).toBeCloseTo(100, 10);
  });

  it('converges toward a level change and never overshoots it', () => {
    const vals = [...Array(21).fill(100), ...Array(60).fill(110)];
    const s = emaSeries(vals, EMA_SLOW);
    const last = s[s.length - 1] as number;
    expect(last).toBeGreaterThan(109);
    expect(last).toBeLessThanOrEqual(110);
  });

  it('the fast EMA reacts before the slow one — the whole point of the pair', () => {
    const vals = [...Array(30).fill(100), ...Array(5).fill(120)];
    const fast = emaSeries(vals, EMA_FAST).at(-1) as number;
    const slow = emaSeries(vals, EMA_SLOW).at(-1) as number;
    expect(fast).toBeGreaterThan(slow);
  });

  it('too few bars means NO line, not a fake one', () => {
    expect(emaSeries([1, 2, 3], 9).every((v) => v === null)).toBe(true);
    expect(emaSeries([], 9)).toEqual([]);
  });

  it('refuses NaN input loudly instead of smoothing over a data bug', () => {
    expect(() => emaSeries([1, 2, NaN, 4], 2)).toThrow(/non-finite/);
  });

  it('refuses a nonsense period', () => {
    expect(() => emaSeries([1, 2, 3], 0)).toThrow();
    expect(() => emaSeries([1, 2, 3], 2.5)).toThrow();
  });
});

describe('emaStep', () => {
  it('matches the series recursion exactly — the live tick cannot drift', () => {
    const vals = [2, 4, 6, 8, 10, 12];
    const s = emaSeries(vals, 3);
    // Recomputing the last point from the previous one must agree.
    expect(emaStep(s[4] as number, 12, 3)).toBeCloseTo(s[5] as number, 12);
  });

  it('alpha is the textbook 2/(n+1)', () => {
    expect(emaAlpha(9)).toBeCloseTo(0.2, 12);
    expect(emaAlpha(21)).toBeCloseTo(2 / 22, 12);
  });
});
