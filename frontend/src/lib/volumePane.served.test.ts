import { describe, it, expect } from 'vitest';
import {
  VOLUME_SMA_LEN, paneVolumeAverage, volumeSma, volumeSmaWindow,
  type ServedVolAvg,
} from './volumePane';

/* 📊 The served full-frame average (2026-10-13). The backend averages volume
 * over the WHOLE frame a tile was cut from (chart_maps/board.py `_vol_avg`);
 * the pane draws that when it lines up with the bars and falls back to its own
 * SMA over the bars in hand otherwise. One choice point: paneVolumeAverage. */

const vols = (n: number) => Array.from({ length: n }, (_, i) => 1000 + i * 10);
const served = (values: (number | null)[], period = 50): ServedVolAvg =>
  ({ period, label: '50-bar avg volume', values });

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('paneVolumeAverage', () => {
  it('the served values win when they line up one-to-one with the bars', () => {
    const v = vols(40);
    const s = v.map((x) => x * 2);
    const out = paneVolumeAverage(v, served(s));
    expect(out.served).toBe(true);
    expect(out.win).toBe(VOLUME_SMA_LEN);
    expect(out.values).toEqual(s);
    expect(out.values[0]).not.toBeNull();          // from bar 0, no warm-up
  });

  it('a served gap stays a gap (a live bar the frame lacked)', () => {
    const v = vols(5);
    const out = paneVolumeAverage(v, served([1, 2, 3, 4, null]));
    expect(out.served).toBe(true);
    expect(out.values).toEqual([1, 2, 3, 4, null]);
  });

  it('the backend period is the same 50 the fallback uses', async () => {
    const py = await readSource('../backend/chart_maps/board.py');
    const m = py.match(/^VOL_AVG_PERIOD = (\d+)/m);
    expect(m).not.toBeNull();
    expect(Number(m![1])).toBe(VOLUME_SMA_LEN);
  });

  // --- negatives: every one is the old pane, byte for byte ---
  const fallback = (v: number[]) => volumeSma(v, volumeSmaWindow(v.length));

  it('NEGATIVE: no served average → the fallback SMA over the bars in hand', () => {
    const v = vols(60);
    for (const s of [undefined, null]) {
      const out = paneVolumeAverage(v, s);
      expect(out.served).toBe(false);
      expect(out.values).toEqual(fallback(v));
      expect(out.values.slice(0, 49).every((x) => x == null)).toBe(true);
    }
  });

  it('NEGATIVE: a length mismatch → the fallback, never a shifted line', () => {
    const v = vols(60);
    const out = paneVolumeAverage(v, served(vols(59)));
    expect(out.served).toBe(false);
    expect(out.values).toEqual(fallback(v));
  });

  it('NEGATIVE: a different period → the fallback (the title would lie)', () => {
    const v = vols(60);
    const out = paneVolumeAverage(v, served(vols(60), 20));
    expect(out.served).toBe(false);
  });

  it('NEGATIVE: an all-null or junk served line → the fallback', () => {
    const v = vols(30);
    expect(paneVolumeAverage(v, served(new Array(30).fill(null))).served).toBe(false);
    const junk = served([NaN, Infinity, -1, ...new Array(27).fill(null)] as any);
    const out = paneVolumeAverage(v, junk);
    expect(out.served).toBe(false);
    expect(out.win).toBe(30);
  });

  it('NEGATIVE: non-finite / negative served points become gaps, never NaN', () => {
    const out = paneVolumeAverage(vols(5), served([5, 6, NaN, -3, Infinity] as any));
    expect(out.served).toBe(true);
    expect(out.values).toEqual([5, 6, null, null, null]);
  });

  it('NEGATIVE: a served line with ONE finite point → the fallback (no segment can draw)', () => {
    const v = vols(30);
    for (const one of [[...new Array(29).fill(null), 1100],
                        [1100, NaN, -1, ...new Array(27).fill(null)]]) {
      const out = paneVolumeAverage(v, served(one as any));
      expect(out.served).toBe(false);
      expect(out.win).toBe(30);
      expect(out.values).toEqual(fallback(v));
    }
  });

  it('NEGATIVE: finite points with no adjacent pair → the fallback (no segment can draw)', () => {
    const v = vols(8);
    for (const apart of [[5, null, 5, null, 5, null, 5, null],
                         [null, 5, NaN, 6, -1, 7, Infinity, 8]]) {
      const out = paneVolumeAverage(v, served(apart as any));
      expect(out.served).toBe(false);
      expect(out.values).toEqual(fallback(v));
    }
  });

  it('two ADJACENT finite points is the floor: served wins', () => {
    const out = paneVolumeAverage(vols(4), served([null, 7, 8, null]));
    expect(out.served).toBe(true);
    expect(out.values).toEqual([null, 7, 8, null]);
  });

  it('NEGATIVE: a malformed served object is ignored', () => {
    const v = vols(10);
    expect(paneVolumeAverage(v, { period: 50, label: 'x', values: 'no' } as any).served).toBe(false);
    expect(paneVolumeAverage(v, 'junk' as any).served).toBe(false);
    expect(paneVolumeAverage(undefined as any, null).values).toEqual([]);
  });
});
