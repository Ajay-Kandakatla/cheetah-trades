import { describe, it, expect } from 'vitest';
import type { UTCTimestamp } from 'lightweight-charts';
import { liveVolumeBars, liveVolumeSma } from './LiveCandlesChart';
import { VOL_DOWN, VOL_UP } from '../lib/volumePane';

/* 📊 The live chart's volume shaping (2026-10-13). The canvas is not
 * exercised in jsdom; the data it is fed is. */

const bar = (i: number, open: number, close: number, volume?: number) => ({
  time: (1_700_000_000 + i * 60) as UTCTimestamp, open, high: Math.max(open, close) + 1,
  low: Math.min(open, close) - 1, close, volume,
});

describe('liveVolumeBars', () => {
  it('colours each column by its candle; a doji is green', () => {
    const v = liveVolumeBars([bar(0, 10, 11, 5), bar(1, 11, 10, 6), bar(2, 10, 10, 7)]);
    expect(v.map((x) => x.color)).toEqual([VOL_UP, VOL_DOWN, VOL_UP]);
    expect(v.map((x) => x.value)).toEqual([5, 6, 7]);
  });

  // --- negatives ---
  it('NEGATIVE: a non-numeric open gets no colour of its own (series default), never a guess', () => {
    const [v] = liveVolumeBars([bar(0, NaN, 11, 5)]);
    expect(v.color).toBeUndefined();
    expect('color' in v).toBe(false);
  });

  it('NEGATIVE: empty input → empty output', () => {
    expect(liveVolumeBars([])).toEqual([]);
    expect(liveVolumeSma([])).toEqual([]);
  });
});

describe('liveVolumeSma', () => {
  it('starts at bar 50 with the 50-bar mean', () => {
    const bars = Array.from({ length: 55 }, (_, i) => bar(i, 10, 11, i + 1));
    const s = liveVolumeSma(bars);
    expect(s).toHaveLength(6);
    expect(s[0].time).toBe(bars[49].time);
    expect(s[0].value).toBeCloseTo(25.5, 9);
  });

  // --- negatives ---
  it('NEGATIVE: bars without volume → no line at all (not a zero line)', () => {
    const bars = Array.from({ length: 60 }, (_, i) => bar(i, 10, 11));
    expect(liveVolumeSma(bars)).toEqual([]);
  });
});
