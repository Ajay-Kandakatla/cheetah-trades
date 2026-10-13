import { describe, it, expect } from 'vitest';
import {
  VOL_DOWN, VOL_PANE_FRAC, VOL_UP, VOLUME_SMA_LEN, volumeColor, volumePaneLayout,
  volumeSma, volumeSmaTitle, volumeSmaWindow,
} from './volumePane';
import { VOL_DOWN as ZC_DOWN, VOL_UP as ZC_UP } from './zoneChart';

/* 📊 The shared volume read (Ajay 2026-10-13: "green and red volume" + a thin
 * 50-bar average). One colour rule and one average for all three charts. */

describe('volumeColor', () => {
  it('green when the close is above the open, red when below', () => {
    expect(volumeColor(10, 11)).toBe(VOL_UP);
    expect(volumeColor(11, 10)).toBe(VOL_DOWN);
  });

  it('a doji (close == open) is GREEN, like the candle body above it', () => {
    expect(volumeColor(42, 42)).toBe(VOL_UP);
  });

  it('zoneChart re-exports the very same tokens (one colour across charts)', () => {
    expect(ZC_UP).toBe(VOL_UP);
    expect(ZC_DOWN).toBe(VOL_DOWN);
    expect(VOL_UP).not.toBe(VOL_DOWN);
  });

  // --- negatives ---
  it('NEGATIVE: a missing or non-finite price gets no side at all', () => {
    expect(volumeColor(NaN, 10)).toBeNull();
    expect(volumeColor(10, NaN)).toBeNull();
    expect(volumeColor(undefined, 10)).toBeNull();
    expect(volumeColor(10, null)).toBeNull();
    expect(volumeColor(Infinity, 10)).toBeNull();
  });
});

describe('volumeSma', () => {
  it('defaults to his 50-bar window', () => {
    expect(VOLUME_SMA_LEN).toBe(50);
    const v = Array.from({ length: 60 }, (_, i) => i + 1);
    const s = volumeSma(v);
    expect(s).toHaveLength(60);
    expect(s[48]).toBeNull();
    // bars 1..50 average to 25.5; the next window 2..51 to 26.5
    expect(s[49]).toBeCloseTo(25.5, 9);
    expect(s[50]).toBeCloseTo(26.5, 9);
  });

  it('warm-up positions are NULL, not zero', () => {
    const s = volumeSma([10, 20, 30, 40], 3);
    expect(s).toEqual([null, null, 20, 30]);
    expect(s[0]).not.toBe(0);
  });

  it('a zero-volume bar is a real zero and counts in the average', () => {
    expect(volumeSma([30, 0, 30], 3)).toEqual([null, null, 20]);
  });

  // --- negatives ---
  it('NEGATIVE: empty / non-array input → empty output, no throw', () => {
    expect(volumeSma([])).toEqual([]);
    expect(volumeSma(undefined as unknown as number[])).toEqual([]);
  });

  it('NEGATIVE: a missing / negative / NaN volume nulls every window holding it', () => {
    expect(volumeSma([10, null, 10, 10, 10], 2)).toEqual([null, null, null, 10, 10]);
    expect(volumeSma([10, -5, 10], 2)).toEqual([null, null, null]);
    expect(volumeSma([10, NaN, 10], 1)).toEqual([10, null, 10]);
  });

  it('NEGATIVE: a bad window length returns all nulls, never NaN', () => {
    for (const n of [0, -3, 2.5, NaN]) {
      const s = volumeSma([1, 2, 3], n);
      expect(s).toEqual([null, null, null]);
    }
  });

  it('NEGATIVE: fewer bars than the window → nothing but warm-up', () => {
    expect(volumeSma([5, 5, 5], 50)).toEqual([null, null, null]);
  });
});

describe('volumeSmaWindow / volumeSmaTitle', () => {
  it('uses 50 when there are enough bars, every bar when there are fewer', () => {
    expect(volumeSmaWindow(200)).toBe(50);
    expect(volumeSmaWindow(50)).toBe(50);
    expect(volumeSmaWindow(30)).toBe(30);
    expect(volumeSmaTitle(50, 200)).toBe('50-bar simple average volume');
    expect(volumeSmaTitle(30, 30)).toContain('only 30 bars on this chart; 50 wanted');
  });

  it('NEGATIVE: zero / junk bar counts still give a window of at least 1', () => {
    expect(volumeSmaWindow(0)).toBe(1);
    expect(volumeSmaWindow(NaN)).toBe(1);
  });
});

describe('volumePaneLayout', () => {
  it('takes ~22% of the tile at the bottom; the price pane ends above it', () => {
    const L = volumePaneLayout(190, 10, true);
    expect(L.volBot).toBe(180);
    expect(L.volBot - L.volTop).toBe(Math.round(190 * VOL_PANE_FRAC));
    // the price plot's bottom (priceH - padY) sits above the pane's top
    expect(L.priceH - 10).toBeLessThan(L.volTop);
    expect(L.priceH).toBeLessThan(190);
  });

  it('NEGATIVE: no volume → the price pane keeps the whole height', () => {
    expect(volumePaneLayout(190, 10, false).priceH).toBe(190);
  });
});
