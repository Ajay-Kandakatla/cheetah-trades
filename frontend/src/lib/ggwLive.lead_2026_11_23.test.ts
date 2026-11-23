/* 🎾 ggwLive learns the served `axis.lead` — ONE convention (2026-11-23, rswatch spec §3.5 [C1], WP fe-live tests 2–9).
 * Ajay 2026-11-23: "In the reversal squeeze can you make the charts same as in watch list please".
 * The 🎾 card's 5-minute frame serves yesterday's tail in `lead` slots AHEAD of today's 04:00. Live buckets, a meta's
 * `slots` and `last_bucket` are ALWAYS on today's grid (slot 0 = start_epoch): ggwFrameMeta takes the lead OFF,
 * ggwLiveFrame puts it BACK on the appended axis.x and the shade lookup only; prune / ggwApplyBatch are not edited — so a
 * name's forming candle survives a 🎾 ↔ other-setup switch (the shared live map is keyed by symbol).
 * Fixture: ONE set of today's 5-minute bars served two ways — `plain` (no lead) and `squeeze` (lead 60, a hand-built
 * prior tail ahead). NEGATIVES: a junk lead → the no-lead meta; only tail bars → null; prints before start / ≤ last /
 * ≥ today's slots / replayed / another variant → skipped; after the flip no bucket ≥ the plain slots; no lead → the
 * pre-change seed exactly; the reducer bodies never name `lead`. */
import { describe, expect, it } from 'vitest';
import type { CmBar } from './chartMaps';
import type { GgQuotesEvent, GgStreamQuote } from './cardLive';
import { GGW_TAB, parseFrame, type GgwFrame, type GgwRow } from './gajjalaWatch';
import {
  ggwApplyBatch, ggwFrameMeta, ggwFrameMetas, ggwLiveFrame, ggwSeedLive, type GgwFrameMeta, type GgwLiveBar, type GgwLiveMap,
} from './ggwLive';

/* 2026-11-23 is EST: 04:00 ET = 09:00 UTC. */
const START = Date.UTC(2026, 10, 23, 9, 0, 0) / 1000;
const SYM = 'LEAD';
const LEAD = 60;
const DAY = '2026-11-23';
const PRIOR = '2026-11-20';
const pad = (n: number) => String(n).padStart(2, '0');
const clock = (fromMin: number, slot: number, fm: number) => {
  const m = fromMin + (slot + 1) * fm;
  return `${pad(Math.floor(m / 60))}:${pad(m % 60)}`;
};
const bar = (t: string, o: number, v = 100): CmBar => ({ t, o, h: o + 0.01, l: o - 0.01, c: o + 0.005, v });

/* Today's 5-min bars: slots 0 … 29 (04:05 … 06:30); the forming bucket is 30 (06:30 → 06:35). */
const TODAY5 = Array.from({ length: 30 }, (_, i) => i);
const TAIL5 = [3, 7, 12, 20, 33, 47, 59];
const todayBars5 = TODAY5.map((s) => bar(`${DAY} ${clock(240, s, 5)}`, 2 + s / 100));
const tailBars5 = TAIL5.map((s) => bar(`${PRIOR} ${clock(900, s, 5)}`, 1 + s / 100));
const SHADE5 = [{ from_slot: 0, to_slot: 66, kind: 'pre' }, { from_slot: 144, to_slot: 192, kind: 'ah' }];
const curve = (n: number) => [{ tone: 'ema9', values: Array.from({ length: n }, (_, i) => 2 + i / 100) }];

const raw5 = (squeeze: boolean, o: { bars?: CmBar[]; x?: number[] } = {}) => {
  const bars = o.bars ?? (squeeze ? [...tailBars5, ...todayBars5] : todayBars5);
  return {
    tf: '5m', label: '5-min',
    tile: { symbol: SYM, bars, curves: curve(bars.length), vol_avg: { values: bars.map(() => 50) } },
    axis: squeeze ? {
      slots: 192 + LEAD, x: o.x ?? [...TAIL5, ...TODAY5.map((s) => s + LEAD)],
      shade: [{ from_slot: 12, to_slot: LEAD, kind: 'ah' }, ...SHADE5.map((s) => ({ ...s, from_slot: s.from_slot + LEAD,
        to_slot: s.to_slot + LEAD }))],
      ticks: [{ slot: 0, label: 'Nov 20' }, { slot: LEAD, label: '04:00' }],
      start_epoch: START, frame_min: 5, from_et: '04:00', to_et: '20:00', lead: LEAD,
    } : {
      slots: 192, x: o.x ?? TODAY5, shade: SHADE5, ticks: [{ slot: 0, label: '04:00' }],
      start_epoch: START, frame_min: 5, from_et: '04:00', to_et: '20:00',
    },
  };
};
const plain = parseFrame(raw5(false), SYM)!;
const squeeze = parseFrame(raw5(true), SYM)!;
const metasOf = (f: GgwFrame): Record<string, GgwFrameMeta[]> => ({ [SYM]: [ggwFrameMeta(f)!] });
const M_PL = metasOf(plain);
const M_SQ = metasOf(squeeze);

const q = (price: number, at: number, size = 10): GgStreamQuote => ({ price, as_of_epoch: at, vs: null, size });
const evt = (quotes: Record<string, GgStreamQuote>, variant = GGW_TAB): GgQuotesEvent => ({ kind: 'quotes', variant, quotes });
const print = (prev: GgwLiveMap, price: number, at: number, metas: Record<string, GgwFrameMeta[]>, size = 10) =>
  ggwApplyBatch(prev, evt({ [SYM]: q(price, at, size) }), metas);
/** `sec` seconds into 5-min bucket b of today's grid. */
const at5 = (b: number, sec = 10) => START + b * 300 + sec;

describe('🎾 fixture sanity', () => {
  it('both frames parse, the squeeze one with lead 60', () => {
    expect(plain.axis!.lead).toBeUndefined();
    expect(squeeze.axis!.lead).toBe(LEAD);
    expect(squeeze.tile.bars).toHaveLength(squeeze.axis!.x.length);
  });
});

describe('🎾 ggwFrameMeta [C1] — the lead taken OFF (today\'s grid)', () => {
  it('the squeeze meta has lead 60 and the SAME slots / last_bucket as the plain meta', () => {
    const ms = ggwFrameMeta(squeeze)!;
    const mp = ggwFrameMeta(plain)!;
    expect(ms.lead).toBe(LEAD);
    expect(ms.slots).toBe(mp.slots);
    expect(ms.last_bucket).toBe(mp.last_bucket);
    expect(ms.slots).toBe(192);
    expect(ms.last_bucket).toBe(29);
    expect(ms.start_epoch).toBe(mp.start_epoch);
    expect(ms.day).toBe(DAY);
    expect(ms.shade).toEqual(squeeze.axis!.shade);   // the served (led) spans
    const { lead: _l, shade: _s, ...rest } = ms;
    const { shade: _s2, ...restP } = mp;
    expect(rest).toEqual(restP);
  });

  it('NEGATIVE the plain meta is the exact pre-change object, no lead key', () => {
    const mp = ggwFrameMeta(plain)!;
    expect(mp).toEqual({
      tf: '5m', start_epoch: START, frame_min: 5, slots: 192, last_bucket: 29, day: DAY, from_et: '04:00', shade: SHADE5,
    });
    expect('lead' in mp).toBe(false);
  });

  it('NEGATIVE a lead axis whose last x sits in the lead (only tail bars) → null', () => {
    const f = parseFrame(raw5(true, { bars: tailBars5, x: TAIL5 }), SYM)!;
    expect(f.axis!.lead).toBe(LEAD);
    expect(ggwFrameMeta(f)).toBeNull();
    /* and ggwLiveFrame then draws nothing new */
    expect(ggwLiveFrame(f, [{ bucket: 30, o: 1, h: 1, l: 1, c: 1, v: 1, as_of: at5(30) }])).toBe(f);
  });

  it.each([0, -1, 1.5, NaN, '60'])('NEGATIVE a hand-built junk lead %s → the meta of a no-lead axis', (junk) => {
    const f = { ...plain, axis: { ...plain.axis!, lead: junk as any } } as GgwFrame;
    const m = ggwFrameMeta(f)!;
    expect(m).toEqual(ggwFrameMeta(plain));
    expect('lead' in m).toBe(false);
  });
});

describe('🎾 ggwApplyBatch under the squeeze metas — today\'s grid', () => {
  it('a print 150 min 10 s after start_epoch → a live bar at bucket 30 (never 90)', () => {
    const live = print({}, 2.5, START + 150 * 60 + 10, M_SQ);
    expect(live[SYM].by['5m']).toHaveLength(1);
    expect(live[SYM].by['5m'][0].bucket).toBe(30);
  });

  it('NEGATIVE a print before start_epoch → nothing', () => {
    const prev: GgwLiveMap = {};
    expect(print(prev, 2.5, START - 30, M_SQ)).toBe(prev);
  });

  it('NEGATIVE a bucket ≤ last_bucket → skipped', () => {
    const prev: GgwLiveMap = {};
    expect(print(prev, 2.5, at5(29), M_SQ)).toBe(prev);
    expect(print(prev, 2.5, at5(5), M_SQ)).toBe(prev);
  });

  it('NEGATIVE a bucket ≥ today\'s slots → skipped (192, and 200 — inside the LED slots, still off today\'s grid)', () => {
    const prev: GgwLiveMap = {};
    expect(print(prev, 2.5, at5(192), M_SQ)).toBe(prev);
    expect(print(prev, 2.5, at5(200), M_SQ)).toBe(prev);
  });

  it('NEGATIVE a replayed stamp adds no volume', () => {
    const a = print({}, 2.5, at5(30), M_SQ, 40);
    const b = print(a, 2.6, at5(30), M_SQ, 40);
    expect(b).toBe(a);
    expect(b[SYM].by['5m'][0].v).toBe(40);
  });

  it('NEGATIVE another variant → prev', () => {
    const prev: GgwLiveMap = {};
    expect(ggwApplyBatch(prev, evt({ [SYM]: q(2.5, at5(30)) }, 'gajjala_audited'), M_SQ)).toBe(prev);
  });
});

describe('🎾 ggwLiveFrame — the lead put BACK on axis.x and the shade lookup', () => {
  const live = print({}, 2.5, at5(30), M_SQ);
  it('squeeze frame: stamp 06:35, axis.x gains 90, bars == x, shade tag of the served span holding slot 90', () => {
    const out = ggwLiveFrame(squeeze, live[SYM].by['5m']);
    const last = out.tile.bars[out.tile.bars.length - 1];
    expect(last.t).toBe(`${DAY} 06:35`);
    expect(out.axis!.x[out.axis!.x.length - 1]).toBe(90);
    expect(out.axis!.x).toEqual([...squeeze.axis!.x, 90]);
    expect(out.tile.bars).toHaveLength(out.axis!.x.length);
    /* slot 90 sits in the served pre span 60..126; slot 30 (no lead put back) would read the tail's 'ah' span */
    expect((last as CmBar & { s?: string }).s).toBe('pre');
    expect(out.tile.curves![0].values).toHaveLength(out.tile.bars.length);
  });

  it('NEGATIVE the plain frame with the SAME live bar → stamp 06:35, axis.x gains 30', () => {
    const out = ggwLiveFrame(plain, live[SYM].by['5m']);
    const last = out.tile.bars[out.tile.bars.length - 1];
    expect(last.t).toBe(`${DAY} 06:35`);
    expect(out.axis!.x).toEqual([...TODAY5, 30]);
    expect((last as CmBar & { s?: string }).s).toBe('pre');
  });
});

describe('🎾 [C1] the flip, both ways, one symbol', () => {
  const lastX = (f: GgwFrame) => f.axis!.x.slice(-2);
  const lastT = (f: GgwFrame) => f.tile.bars.slice(-2).map((b) => b.t);

  it('squeeze → plain → squeeze: both prints fold, each frame draws them at its own slots, same stamps', () => {
    let live = print({}, 2.5, at5(30, 10), M_SQ, 10);
    live = print(live, 2.7, at5(30, 50), M_PL, 5);
    live = print(live, 2.4, at5(31, 10), M_PL, 7);
    const bars = live[SYM].by['5m'];
    expect(bars.map((b) => b.bucket)).toEqual([30, 31]);
    expect(bars[0]).toMatchObject({ o: 2.5, h: 2.7, l: 2.5, c: 2.7, v: 15 });
    expect(bars[1]).toMatchObject({ o: 2.4, v: 7 });
    const p = ggwLiveFrame(plain, bars);
    expect(lastX(p)).toEqual([30, 31]);
    expect(lastT(p)).toEqual([`${DAY} 06:35`, `${DAY} 06:40`]);
    live = print(live, 2.45, at5(31, 40), M_SQ, 3);
    const bars2 = live[SYM].by['5m'];
    expect(bars2.map((b) => b.bucket)).toEqual([30, 31]);
    expect(bars2[1].v).toBe(10);
    const s = ggwLiveFrame(squeeze, bars2);
    expect(lastX(s)).toEqual([90, 91]);
    expect(lastT(s)).toEqual([`${DAY} 06:35`, `${DAY} 06:40`]);
  });

  it('plain → squeeze → plain: the reverse order', () => {
    let live = print({}, 2.5, at5(30, 10), M_PL, 10);
    live = print(live, 2.7, at5(30, 50), M_SQ, 5);
    live = print(live, 2.4, at5(31, 10), M_SQ, 7);
    const bars = live[SYM].by['5m'];
    expect(bars.map((b) => b.bucket)).toEqual([30, 31]);
    expect(bars[0]).toMatchObject({ h: 2.7, c: 2.7, v: 15 });
    const s = ggwLiveFrame(squeeze, bars);
    expect(lastX(s)).toEqual([90, 91]);
    expect(lastT(s)).toEqual([`${DAY} 06:35`, `${DAY} 06:40`]);
    live = print(live, 2.45, at5(31, 40), M_PL, 3);
    const p = ggwLiveFrame(plain, live[SYM].by['5m']);
    expect(lastX(p)).toEqual([30, 31]);
    expect(lastT(p)).toEqual([`${DAY} 06:35`, `${DAY} 06:40`]);
  });

  it('the map folded under the squeeze metas equals the map folded under the plain metas for the same prints', () => {
    const prints: Array<[number, number, number]> = [
      [2.5, at5(30, 10), 10], [2.7, at5(30, 50), 5], [2.4, at5(31, 10), 7], [2.45, at5(33, 1), 3], [2.2, at5(192), 9],
    ];
    let a: GgwLiveMap = {};
    let b: GgwLiveMap = {};
    for (const [p, t, v] of prints) { a = print(a, p, t, M_SQ, v); b = print(b, p, t, M_PL, v); }
    expect(a).toEqual(b);
    expect(a[SYM].by['5m'].map((x) => x.bucket)).toEqual([30, 31, 33]);
  });

  it('NEGATIVE after the flip no live bar is ever left with a bucket ≥ the plain frame\'s slots', () => {
    let live: GgwLiveMap = {};
    const plainSlots = ggwFrameMeta(plain)!.slots;
    for (let b = 25; b < 260; b += 7) {
      live = print(live, 2 + b / 1000, at5(b), b % 2 ? M_SQ : M_PL);
      for (const x of live[SYM]?.by['5m'] ?? []) expect(x.bucket).toBeLessThan(plainSlots);
    }
    /* the plain frame draws every kept bar inside its own axis */
    const p = ggwLiveFrame(plain, live[SYM].by['5m']);
    for (const x of p.axis!.x) expect(x).toBeLessThan(plain.axis!.slots);
  });
});

describe('🎾 the chain: parseFrame(served lead frame) → ggwFrameMetas → ggwApplyBatch → ggwLiveFrame', () => {
  it('a served lead frame folds on today\'s grid and draws at slot + lead', () => {
    const f = parseFrame(JSON.parse(JSON.stringify(raw5(true))), SYM)!;
    const row = { symbol: SYM, state: 'ok', text: null, from_session: null, as_of_et: null, stale: false,
      frames: [f], rang: [] } as GgwRow;
    const metas = ggwFrameMetas([row]);
    expect(metas[SYM]).toHaveLength(1);
    expect(metas[SYM][0]).toMatchObject({ lead: LEAD, slots: 192, last_bucket: 29 });
    const live = ggwApplyBatch({}, evt({ [SYM]: q(2.5, START + 150 * 60 + 10) }), metas);
    expect(live[SYM].by['5m'][0].bucket).toBe(30);
    const out = ggwLiveFrame(f, live[SYM].by['5m']);
    expect(out.axis!.x[out.axis!.x.length - 1]).toBe(30 + LEAD);
    expect(out.tile.bars[out.tile.bars.length - 1].t).toBe(`${DAY} 06:35`);
  });
});

/* ── ggwSeedLive (flag OFF — the function is called directly) ───────────────────────────────────────────────────── */

/** main's ggwSeedLive, transcribed as the pre-change oracle (a no-lead call must equal it exactly). */
function seedMain(f: GgwFrame, own: GgwLiveBar[] | undefined, f1: GgwFrame | null | undefined,
                  live1: GgwLiveBar[] | undefined): GgwLiveBar[] | undefined {
  const fin = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
  if (!f || !f1 || f1 === f || f1.stale === true || !Array.isArray(live1) || !live1.length) return own;
  const m = ggwFrameMeta(f);
  const m1 = ggwFrameMeta(f1);
  if (!m || !m1 || m.start_epoch !== m1.start_epoch) return own;
  const k = m.frame_min / m1.frame_min;
  if (!Number.isInteger(k) || k <= 1) return own;
  const past1 = live1.filter((b) => b && fin(b.bucket) && b.bucket > m1.last_bucket && b.bucket < m1.slots);
  if (!past1.length) return own;
  type Part = { o: number; h: number; l: number; c: number; v: number; as_of: number | null };
  const parts = new Map<number, Part[]>();
  const push = (b: number, p: Part) => {
    if (!(b > m.last_bucket && b < m.slots)) return;
    const arr = parts.get(b);
    if (arr) arr.push(p); else parts.set(b, [p]);
  };
  const bars1 = f1.tile.bars;
  const x1 = f1.axis?.x ?? [];
  for (let i = 0; i < Math.min(bars1.length, x1.length); i += 1) {
    const s = x1[i];
    const bar1 = bars1[i];
    if (!fin(s) || !bar1 || ![bar1.o, bar1.h, bar1.l, bar1.c].every(fin)) continue;
    push(Math.floor(s / k), { o: bar1.o, h: bar1.h, l: bar1.l, c: bar1.c, v: fin(bar1.v) && bar1.v > 0 ? bar1.v : 0,
      as_of: m1.start_epoch + (s + 1) * m1.frame_min * 60 });
  }
  for (const b of past1) push(Math.floor(b.bucket / k), { o: b.o, h: b.h, l: b.l, c: b.c, v: b.v, as_of: b.as_of });
  if (!parts.size) return own;
  const seeded = new Map<number, GgwLiveBar>();
  for (const [b, ps] of parts) {
    seeded.set(b, { bucket: b, o: ps[0].o, h: Math.max(...ps.map((p) => p.h)), l: Math.min(...ps.map((p) => p.l)),
      c: ps[ps.length - 1].c, v: ps.reduce((a, p) => a + p.v, 0), as_of: ps[ps.length - 1].as_of ?? 0 });
  }
  for (const b of own || []) if (b && !seeded.has(b.bucket)) seeded.set(b.bucket, b);
  return [...seeded.values()].sort((a, b) => a.bucket - b.bucket);
}

/* The 1-min frame: stored minutes 0 … 152 (bucket 30 of the 5-min grid holds minutes 150–152); live minute 153. */
const STORED1 = Array.from({ length: 153 }, (_, i) => i);
const bars1 = STORED1.map((s) => bar(`${DAY} ${clock(240, s, 1)}`, 2 + s / 1000, 100 + s));
const LEAD1 = 300;
const TAIL1 = [4, 100, 299];
const tailBars1 = TAIL1.map((s) => bar(`${PRIOR} ${clock(900, s, 1)}`, 9 + s / 1000, 5000));
const frame1 = (lead: boolean): GgwFrame => parseFrame({
  tf: '1m', label: '1-min',
  tile: { symbol: SYM, bars: lead ? [...tailBars1, ...bars1] : bars1, curves: [] },
  axis: {
    slots: 960 + (lead ? LEAD1 : 0), x: lead ? [...TAIL1, ...STORED1.map((s) => s + LEAD1)] : STORED1,
    shade: [], ticks: [], start_epoch: START, frame_min: 1, from_et: '04:00', to_et: '20:00', ...(lead ? { lead: LEAD1 } : {}),
  },
}, SYM)!;
const live1: GgwLiveBar[] = [{ bucket: 153, o: 2.2, h: 2.25, l: 2.15, c: 2.21, v: 40, as_of: START + 153 * 60 + 30 }];

describe('🎾 ggwSeedLive — the lead on the 5-minute frame / the 1-minute frame', () => {
  it('lead on the 5-min frame only: the seeded bucket == floor(1-min slot / 5) on today\'s grid; ggwLiveFrame draws it at + 60', () => {
    const f1 = frame1(false);
    const out = ggwSeedLive(squeeze, undefined, f1, live1)!;
    expect(out.map((b) => b.bucket)).toEqual([Math.floor(150 / 5)]);
    expect(out).toEqual(ggwSeedLive(plain, undefined, f1, live1));
    expect(out[0].o).toBe(bars1[150].o);
    expect(out[0].v).toBe(bars1[150].v + bars1[151].v + bars1[152].v + 40);
    const drawn = ggwLiveFrame(squeeze, out);
    expect(drawn.axis!.x[drawn.axis!.x.length - 1]).toBe(30 + LEAD);
    expect(drawn.tile.bars[drawn.tile.bars.length - 1].t).toBe(`${DAY} 06:35`);
  });

  it('a lead on the 1-MINUTE frame too: its tail bars seed nothing, its today bars seed the same buckets', () => {
    const f1L = frame1(true);
    expect(f1L.axis!.lead).toBe(LEAD1);
    expect(ggwFrameMeta(f1L)).toMatchObject({ slots: 960, last_bucket: 152, lead: LEAD1 });
    const led = ggwSeedLive(squeeze, undefined, f1L, live1)!;
    const flat = ggwSeedLive(plain, undefined, frame1(false), live1)!;
    expect(led).toEqual(flat);
    expect(led.some((b) => b.v >= 5000)).toBe(false);   // no tail minute's volume reached a bucket
    expect(led[0].as_of).toBe(live1[0].as_of);
  });

  it('NEGATIVE no lead → deep-equals the pre-change function', () => {
    const f1 = frame1(false);
    const own = [{ bucket: 30, o: 2.1, h: 2.3, l: 2.0, c: 2.2, v: 7, as_of: START + 9000 }];
    for (const args of [
      [plain, undefined, f1, live1],
      [plain, own, f1, live1],
      [plain, own, f1, []],
      [plain, own, null, live1],
      [plain, own, f1, [{ ...live1[0], bucket: 100 }]],
    ] as const) {
      expect(ggwSeedLive(...(args as unknown as Parameters<typeof ggwSeedLive>)))
        .toEqual(seedMain(...(args as unknown as Parameters<typeof seedMain>)));
    }
  });
});

/* ── source read: the reducer is not edited ──────────────────────────────────────────────────────────────────────── */

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const bodyOf = (src: string, head: string): string => {
  const i = src.indexOf(head);
  expect(i).toBeGreaterThanOrEqual(0);
  const j = src.indexOf('\n}\n', i);
  expect(j).toBeGreaterThan(i);
  return src.slice(i, j + 2);
};

describe('🎾 NEGATIVE (source read) — prune and ggwApplyBatch never name the lead', () => {
  it('their bodies hold no `lead` token; ggwFrameMeta / ggwLiveFrame do', async () => {
    const src = await readSource('src/lib/ggwLive.ts');
    const prune = bodyOf(src, 'function prune(');
    const apply = bodyOf(src, 'export function ggwApplyBatch(');
    expect(prune).toContain('last_bucket');
    expect(apply).toContain('ggwBucket(');
    expect(prune).not.toMatch(/lead/i);
    expect(apply).not.toMatch(/lead/i);
    expect(bodyOf(src, 'export function ggwFrameMeta(')).toMatch(/\.lead\b/);
    expect(bodyOf(src, 'export function ggwLiveFrame(')).toMatch(/meta\.lead/);
  });
});
