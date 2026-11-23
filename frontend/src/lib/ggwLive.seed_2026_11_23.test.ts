/* 📈 The forming 5- / 15-min candle from the row's own 1-min chart — ggwSeedLive (2026-11-23, vwapzones spec §3.9 [O2][C8]).
 * Ajay 2026-11-23: "on the watch list I think we switch to 15 when candles are available for full chart" · "Can you remove 3
 * mins just add 15 mins instead.. So 1 min, 5 and 15 accross board". BUILT, OFF (GGW_SEED_FORMING = false — HIS CALL #13):
 * the shipped forming candle is main's (the prints seen since the fold began). The pure function: opened mid-bucket the
 * forming 15-min candle's open = the first stored 1-min bar of the bucket, high / low span it, volume = stored + live.
 * NEGATIVES: no live print → no forming candle; a stale / missing 1-min frame → `own`; a stored minute of a CLOSED bucket
 * never counts; another start_epoch → unchanged; [C8] a minute the server now stores is counted ONCE, from the store. */
import { describe, expect, it } from 'vitest';
import type { CmBar } from './chartMaps';
import type { GgQuotesEvent } from './cardLive';
import { GGW_LIVE_EMA_TIP, GGW_SEED_FORMING, GGW_TAB, type GgwFrame } from './gajjalaWatch';
import {
  ggwApplyBatch, ggwBucket, ggwFrameMeta, ggwLiveFrame, ggwSeedLive, type GgwFrameMeta, type GgwLiveBar,
} from './ggwLive';

/* 2026-11-23 is EST: 04:00 ET = 09:00 UTC. In production the SERVER serves start_epoch (build.axis). */
const START = Date.UTC(2026, 10, 23, 9, 0, 0) / 1000;
const pad = (n: number) => String(n).padStart(2, '0');
const stamp = (slot: number, fm: number) => {
  const m = 4 * 60 + (slot + 1) * fm;
  return `2026-11-23 ${pad(Math.floor(m / 60))}:${pad(m % 60)}`;
};
/** A 1-min bar of minute-slot s (deterministic numbers: o = 1 + s / 100, range ±0.005, volume 100 + s). */
const bar1 = (s: number): CmBar => {
  const o = 1 + s / 100;
  return { t: stamp(s, 1), o, h: o + 0.005, l: o - 0.004, c: o + 0.002, v: 100 + s };
};
/** A frame of `fm` minutes whose stored bars sit in `slots` (the served axis.x), with the live keys. */
function frame(tf: string, fm: number, slots: number[], bars: CmBar[], o: { start?: number; stale?: boolean } = {}): GgwFrame {
  return {
    tf, label: tf,
    tile: { symbol: 'SEED', href: '', bars, bands: [], lines: [], markers: [], stats: [], why: '', curves: [] } as any,
    axis: {
      slots: Math.round(960 / fm), x: slots, shade: [{ from_slot: 0, to_slot: Math.round(330 / fm), kind: 'pre' }], ticks: [],
      start_epoch: o.start ?? START, frame_min: fm, from_et: '04:00',
    },
    ema_tail: null, ema_cross: null, uptrend: null, held: null, run_bases: null, ema_blink: null,
    ...(o.stale != null ? { stale: o.stale } : {}),
  };
}
/** The row's 1-min frame: stored minutes 0 … last1. */
const oneMin = (last1: number, o: { start?: number; stale?: boolean } = {}) => {
  const s = Array.from({ length: last1 + 1 }, (_, i) => i);
  return frame('1m', 1, s, s.map(bar1), o);
};
/** A 15-min frame whose stored buckets are 0 … last15 (each bar = the aggregate of its 15 minutes). */
const fifteen = (last15: number, o: { start?: number } = {}) => {
  const s = Array.from({ length: last15 + 1 }, (_, i) => i);
  return frame('15m', 15, s, s.map((b) => {
    const m = Array.from({ length: 15 }, (_, j) => bar1(b * 15 + j));
    return { t: stamp(b, 15), o: m[0].o, h: Math.max(...m.map((x) => x.h)), l: Math.min(...m.map((x) => x.l)),
      c: m[14].c, v: m.reduce((a, x) => a + x.v, 0) };
  }), o);
};
const lv = (bucket: number, o: number, v: number, asOf = START + bucket * 60 + 30): GgwLiveBar =>
  ({ bucket, o, h: o + 0.01, l: o - 0.02, c: o + 0.003, v, as_of: asOf });

describe('📈 GGW_SEED_FORMING — BUILT, OFF (HIS CALL #13)', () => {
  it('the shipped value is false; the 9 / 21 tip switch beside it is untouched', () => {
    expect(GGW_SEED_FORMING).toBe(false);
    expect(GGW_LIVE_EMA_TIP).toBe(true);
  });
});

describe('📈 ggwSeedLive — the pure function', () => {
  /* Stored 1-min through minute 36 (09:36 slot = 04:36 here — the arithmetic is the same at any hour); the 15-min frame
   * holds buckets 0 and 1 (minutes 0–29); bucket 2 = minutes 30–44 is forming. The page opened at minute 37. */
  const f1 = oneMin(36);
  const f15 = fifteen(1);
  const live1 = [lv(37, 1.371, 50), lv(38, 1.385, 70)];
  const own15 = [lv(2, 1.371, 120)];   // main's forming candle: only the prints since the page opened

  it('opened mid-bucket: open = the first stored 1-min bar of the bucket; high / low span it; volume = stored + live', () => {
    const out = ggwSeedLive(f15, own15, f1, live1)!;
    expect(out).toHaveLength(1);
    const b = out[0];
    const stored = [30, 31, 32, 33, 34, 35, 36].map(bar1);
    expect(b.bucket).toBe(2);
    expect(b.o).toBe(stored[0].o);
    expect(b.h).toBe(Math.max(...stored.map((x) => x.h), ...live1.map((x) => x.h)));
    expect(b.l).toBe(Math.min(...stored.map((x) => x.l), ...live1.map((x) => x.l)));
    expect(b.c).toBe(live1[1].c);
    expect(b.v).toBe(stored.reduce((a, x) => a + x.v, 0) + 50 + 70);
    expect(b.as_of).toBe(live1[1].as_of);
    // main's own forming candle held only the prints since the page opened — the seed is the fuller one
    expect(b.v).toBeGreaterThan(own15[0].v);
    expect(b.o).not.toBe(own15[0].o);
  });
  it('ggwLiveFrame draws the seeded candle in bucket 2 (stamp 04:45), after the two stored bars', () => {
    const shown = ggwLiveFrame(f15, ggwSeedLive(f15, own15, f1, live1), { emaTip: GGW_LIVE_EMA_TIP });
    expect(shown.tile.bars).toHaveLength(3);
    expect(shown.tile.bars[2].t).toBe('2026-11-23 04:45');
    expect(shown.axis!.x).toEqual([0, 1, 2]);
  });
  it('NEGATIVE: no live print → `own` unchanged (undefined stays undefined: no forming candle)', () => {
    expect(ggwSeedLive(f15, undefined, f1, undefined)).toBeUndefined();
    expect(ggwSeedLive(f15, undefined, f1, [])).toBeUndefined();
    expect(ggwSeedLive(f15, own15, f1, [])).toBe(own15);
  });
  it('NEGATIVE: live 1-min bars only at / before the stored minutes (the server now holds them) → `own`', () => {
    expect(ggwSeedLive(f15, own15, f1, [lv(35, 1.35, 9), lv(36, 1.36, 9)])).toBe(own15);
    expect(ggwSeedLive(f15, undefined, f1, [lv(36, 1.36, 9)])).toBeUndefined();
  });
  it('NEGATIVE: a stale or missing 1-min frame → `own`', () => {
    expect(ggwSeedLive(f15, own15, oneMin(36, { stale: true }), live1)).toBe(own15);
    expect(ggwSeedLive(f15, own15, null, live1)).toBe(own15);
    expect(ggwSeedLive(f15, own15, undefined, live1)).toBe(own15);
    const noAxis = { ...f1, axis: null } as GgwFrame;
    expect(ggwSeedLive(f15, own15, noAxis, live1)).toBe(own15);
  });
  it('NEGATIVE: another start_epoch → `own` unchanged', () => {
    expect(ggwSeedLive(f15, own15, oneMin(36, { start: START + 86400 }), live1)).toBe(own15);
    expect(ggwSeedLive(fifteen(1, { start: START - 60 }), own15, f1, live1)).toBe(own15);
  });
  it('NEGATIVE: the 1-min frame never seeds itself; a non-integer ratio → `own`', () => {
    const own1 = [lv(37, 1.37, 5)];
    expect(ggwSeedLive(f1, own1, f1, live1)).toBe(own1);
    const twoMin = frame('1m', 2, [0, 1, 2], [0, 1, 2].map((s) => ({ ...bar1(s), t: stamp(s, 2) })));
    const s5 = [0, 1, 2];
    const f5 = frame('5m', 5, s5, s5.map((s) => ({ ...bar1(s), t: stamp(s, 5) })));
    expect(ggwSeedLive(f5, own15, twoMin, [lv(9, 1.1, 1)])).toBe(own15);   // 5 / 2 is not an integer
  });
  it('NEGATIVE: a stored minute of a CLOSED bucket never counts (minutes 0–29 sit in the stored buckets 0 and 1)', () => {
    const out = ggwSeedLive(f15, undefined, f1, live1)!;
    expect(out.map((b) => b.bucket)).toEqual([2]);
    const all = Array.from({ length: 37 }, (_, s) => bar1(s)).reduce((a, x) => a + x.v, 0);
    expect(out[0].v).toBeLessThan(all);
    expect(out[0].v).toBe([30, 31, 32, 33, 34, 35, 36].map(bar1).reduce((a, x) => a + x.v, 0) + 120);
  });
  it('[C8] after a refresh that now stores minute 37, the live bar for 37 still in live1 is NOT added — counted once', () => {
    const f1b = oneMin(37);
    const out = ggwSeedLive(f15, own15, f1b, live1)!;
    const storedOnly = [30, 31, 32, 33, 34, 35, 36, 37].map(bar1).reduce((a, x) => a + x.v, 0);
    expect(out[0].v).toBe(storedOnly + 70);          // minute 38 is the only live one past the store
    expect(out[0].v).not.toBe(storedOnly + 50 + 70); // never stored 37 + live 37
    // and with only the now-stored minute live → no live past the store → `own`
    expect(ggwSeedLive(f15, own15, f1b, [lv(37, 1.371, 50)])).toBe(own15);
  });
  it('a bucket of `own` the seed does not cover is kept; a bucket past the slots never appears', () => {
    const extra = [lv(2, 1.371, 120), lv(5, 1.5, 7)];
    const out = ggwSeedLive(f15, extra, f1, live1)!;
    expect(out.map((b) => b.bucket)).toEqual([2, 5]);
    expect(out[1]).toBe(extra[1]);
    const late = ggwSeedLive(f15, undefined, f1, [lv(37, 1.37, 1), lv(960, 9, 1)])!;
    expect(late.map((b) => b.bucket)).toEqual([2]);
  });
  it('5-min frame too (k = 5): bucket 7 = minutes 35–39 → stored 35, 36 + live 37, 38', () => {
    const s5 = Array.from({ length: 7 }, (_, i) => i);
    const f5 = frame('5m', 5, s5, s5.map((b) => ({ ...bar1(b * 5), t: stamp(b, 5) })));
    const out = ggwSeedLive(f5, undefined, f1, live1)!;
    expect(out.map((b) => b.bucket)).toEqual([7]);
    expect(out[0].o).toBe(bar1(35).o);
    expect(out[0].v).toBe(bar1(35).v + bar1(36).v + 50 + 70);
  });
});

describe('📈 live with the seed OFF (the shipped behaviour) on a 15-min frame', () => {
  const metas = (f: GgwFrame): Record<string, GgwFrameMeta[]> => ({ SEED: [ggwFrameMeta(f)!] });
  const evt = (asOf: number, price: number, size: number): GgQuotesEvent =>
    ({ kind: 'quotes', variant: GGW_TAB, quotes: { SEED: { price, as_of_epoch: asOf, size } as any } });
  it('a print at :14:59 lands in the :00 bucket of a 15-min frame; at :15:00 in the next', () => {
    const t0 = START + 2 * 900;   // 04:30 — bucket 2 opens
    expect(ggwBucket(t0 + 14 * 60 + 59, START, 15)).toBe(2);
    expect(ggwBucket(t0 + 15 * 60, START, 15)).toBe(3);
    const f15 = fifteen(1);
    let m = ggwApplyBatch({}, evt(t0 + 14 * 60 + 59, 1.4, 10), metas(f15));
    expect(m.SEED.by['15m'].map((b) => b.bucket)).toEqual([2]);
    m = ggwApplyBatch(m, evt(t0 + 15 * 60, 1.41, 5), metas(f15));
    expect(m.SEED.by['15m'].map((b) => b.bucket)).toEqual([2, 3]);
    expect(m.SEED.by['15m'][1].v).toBe(5);
  });
  it('the forming 15-min candle is main\'s: prints since the fold began only', () => {
    const f15 = fifteen(1);
    const m = ggwApplyBatch({}, evt(START + 37 * 60 + 5, 1.37, 11), metas(f15));
    const own = m.SEED.by['15m'];
    expect(own).toEqual([{ bucket: 2, o: 1.37, h: 1.37, l: 1.37, c: 1.37, v: 11, as_of: START + 37 * 60 + 5 }]);
    const shown = ggwLiveFrame(f15, own, { emaTip: GGW_LIVE_EMA_TIP });
    expect(shown.tile.bars[2]).toMatchObject({ o: 1.37, v: 11 });
  });
});
