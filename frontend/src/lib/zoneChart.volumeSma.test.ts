import { describe, it, expect } from 'vitest';
import { toVolumeBars, toVolumeSma, type SeriesBar } from './zoneChart';
import { VOL_DOWN, VOL_UP } from './volumePane';

/* 📊 ZoneChart's volume (2026-10-13): the columns read the shared 0.7 tokens
 * and the 50-bar average walks the same bars the candles keep. */

const day = (i: number) => new Date(Date.UTC(2026, 0, 1) + i * 86_400_000).toISOString().slice(0, 10);
const series = (n: number, vol = (i: number) => 100 + i): SeriesBar[] =>
  Array.from({ length: n }, (_, i) => ({ date: day(i), open: 10, close: i % 2 ? 9 : 11, volume: vol(i) }));

describe('toVolumeSma', () => {
  it('one point per bar from bar 50 on, each the mean of the last 50 volumes', () => {
    const s = series(60);
    const pts = toVolumeSma(s);
    expect(pts).toHaveLength(11);
    expect(pts[0].time).toBe(day(49));
    expect(pts[0].value).toBeCloseTo(100 + 24.5, 9);
    expect(pts[10].time).toBe(day(59));
  });

  it('the columns read the shared tokens, alpha raised to 0.7', () => {
    const v = toVolumeBars(series(2));
    expect(v[0].color).toBe(VOL_UP);
    expect(v[1].color).toBe(VOL_DOWN);
    expect(VOL_UP).toContain('0.7');
  });

  it('fewer than 50 bars: the window is every bar (one point, the full mean)', () => {
    const pts = toVolumeSma(series(10, () => 50));
    expect(pts).toEqual([{ time: day(9), value: 50 }]);
  });

  // --- negatives ---
  it('NEGATIVE: no series / no positive volume → no line', () => {
    expect(toVolumeSma(undefined)).toEqual([]);
    expect(toVolumeSma([])).toEqual([]);
    expect(toVolumeSma(series(60, () => 0))).toEqual([]);
    expect(toVolumeSma([{ date: day(0), close: 1 }])).toEqual([]);
  });

  it('NEGATIVE: a missing volume is a hole, not a zero; duplicate dates are dropped', () => {
    const s = series(60);
    s[55] = { ...s[55], volume: null };
    s.splice(10, 0, { ...s[10] });            // a duplicate date
    const pts = toVolumeSma(s);
    // windows ending 49..54 only
    expect(pts.map((p) => p.time)).toEqual([49, 50, 51, 52, 53, 54].map(day));
    for (const p of pts) expect(Number.isFinite(p.value)).toBe(true);
  });
});
