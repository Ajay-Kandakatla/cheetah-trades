/* 👀 Gajjala's Watch LIVE — the forming candle + live volume column, pure (2026-11-16, watch-live spec §3.4, WP-C).
 *
 * Ajay 2026-11-16: "Can you make the watch list charts live please" · "Realtime updates.. Like the 1 min chart I need it
 * to be live live.. per sec change" · "Also on the Watch list I need live volume to be shown at the bottom" · "Of each
 * chart".
 *
 * The ONE socket's prints reach the board as `gajjala.update` quote batches (variant `gajjala_watch`, ≤ 1/s, `size` =
 * the summed filtered print sizes since the last batch). This reducer folds them into forming candles per (symbol,
 * frame) on the SERVER's own 04:00 grid (the served axis' `start_epoch` / `frame_min` — the FE does no clock math of its
 * own), and ggwLiveFrame splices them AFTER the stored bars at render time. DISPLAY ONLY: every cross read, blinker, 🔔
 * and push stays on the CLOSED stored bars; the next GET wins (a live bucket the server now holds is dropped). Only rows
 * ggwRowLive passes carry live bars. Composes no word, types no threshold. */
import { EMA_FAST, EMA_SLOW } from './ema';
import type { CmBar, CmCurve, CmTile } from './chartMaps';
import type { GgQuotesEvent } from './cardLive';
import { GGW_TAB, ggwRowLive, type GgwAxis, type GgwFrame, type GgwRow } from './gajjalaWatch';
import { ggwEmaTips } from './ggwEma';

export type GgwLiveBar = { bucket: number; o: number; h: number; l: number; c: number; v: number; as_of: number };
/** tf → live bars, buckets ascending. `last_epoch` = the newest print stamp folded for this symbol. */
export type GgwLiveSym = { last_epoch: number; by: Record<string, GgwLiveBar[]> };
export type GgwLiveMap = Record<string, GgwLiveSym>;
export type GgwFrameMeta = {
  tf: string; start_epoch: number; frame_min: number; slots: number; last_bucket: number; day: string; from_et: string;
  shade: GgwAxis['shade'];
};

const fin = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
const DAY_RE = /^\d{4}-\d{2}-\d{2}/;

/** The live grid of one served frame, or null (no axis, an older doc without the live keys, no bars). */
export function ggwFrameMeta(f: GgwFrame): GgwFrameMeta | null {
  const ax = f?.axis;
  const bars = f?.tile?.bars;
  if (!ax || ax.start_epoch == null || ax.frame_min == null || ax.from_et == null) return null;
  if (!Array.isArray(bars) || !bars.length || !Array.isArray(ax.x) || !ax.x.length) return null;
  const last = bars[bars.length - 1];
  const lastBucket = ax.x[ax.x.length - 1];
  if (!last || typeof last.t !== 'string' || !DAY_RE.test(last.t) || !fin(lastBucket)) return null;
  return {
    tf: f.tf, start_epoch: ax.start_epoch, frame_min: ax.frame_min, slots: ax.slots, last_bucket: lastBucket,
    day: last.t.slice(0, 10), from_et: ax.from_et, shade: ax.shade,
  };
}

/** symbol → its frames' live grids, ONLY for rows ggwRowLive passes (a stale / prior-session / not-ok row has none, so
 *  a batch for it changes nothing and its old live bars are pruned). A row with no live-capable frame is absent. */
export function ggwFrameMetas(rows: ReadonlyArray<GgwRow>): Record<string, GgwFrameMeta[]> {
  const out: Record<string, GgwFrameMeta[]> = {};
  for (const r of rows || []) {
    if (!r || !ggwRowLive(r)) continue;
    /* 2026-11-16 (ggcard3 C3): a frame SERVED as stale carries no live bar — the per-frame twin of the row rule. A frame
     * without the key (every Watch frame) is unchanged. */
    const metas = (r.frames || []).filter((f) => !(f && f.stale === true))
      .map(ggwFrameMeta).filter((m): m is GgwFrameMeta => !!m);
    if (metas.length) out[r.symbol] = metas;
  }
  return out;
}

/** The bucket index of a print on the server's grid — closed=left: a print AT a boundary opens the NEW bucket. */
export function ggwBucket(asOf: number, startEpoch: number, frameMin: number): number {
  return Math.floor((asOf - startEpoch) / (frameMin * 60));
}

const pad2 = (n: number) => String(n).padStart(2, '0');

/** The bar's stamp = its CLOSE (backend bars.py: `t` is the bucket's right label): fromEt + (bucket + 1) × frameMin. */
export function ggwBarStamp(day: string, fromEt: string, bucket: number, frameMin: number): string {
  const [hh, mm] = fromEt.split(':').map(Number);
  const m = hh * 60 + mm + (bucket + 1) * frameMin;
  return `${day} ${pad2(Math.floor(m / 60))}:${pad2(m % 60)}`;
}

/** The served shade span kind holding the bucket ([from_slot, to_slot)), as the bar's `s` tag; undefined in RTH. */
export function ggwShadeOf(shade: GgwAxis['shade'], bucket: number): 'pre' | 'ah' | undefined {
  for (const s of shade || []) {
    if (bucket >= s.from_slot && bucket < s.to_slot && (s.kind === 'pre' || s.kind === 'ah')) return s.kind;
  }
  return undefined;
}

/** Drop the live bars the server now holds (bucket ≤ the last stored bucket), bars from before the frame's session
 *  start, frames the symbol no longer serves, and symbols gone from the live rows. The SAME object when nothing moved. */
function prune(prev: GgwLiveMap, metas: Record<string, GgwFrameMeta[]>): GgwLiveMap {
  let changed = false;
  const out: GgwLiveMap = {};
  for (const [sym, ls] of Object.entries(prev)) {
    const ms = metas[sym];
    if (!ms || !ms.length) { changed = true; continue; }
    let symChanged = false;
    const by: Record<string, GgwLiveBar[]> = {};
    for (const [tf, bars] of Object.entries(ls.by)) {
      const m = ms.find((x) => x.tf === tf);
      if (!m) { symChanged = true; continue; }
      const keep = bars.filter((b) => b.bucket > m.last_bucket && b.as_of >= m.start_epoch);
      if (keep.length !== bars.length) symChanged = true;
      if (keep.length) by[tf] = keep.length === bars.length ? bars : keep;
    }
    if (symChanged) { changed = true; out[sym] = { last_epoch: ls.last_epoch, by }; } else out[sym] = ls;
  }
  return changed ? out : prev;
}

/** One quote batch folded into the forming candles. Rules (spec §3.4, each pinned): another kind / variant → `prev`
 *  (`variant` = the bus tab whose batches this surface folds — default GGW_TAB, the Watch; the 🚩 card view passes its
 *  board's variant key, ggcard3 2026-11-16);
 *  a symbol without live metas → skipped; a quote not newer than the symbol's last folded stamp → skipped WHOLE (a
 *  replayed or older batch never adds volume twice); per frame, a bucket ≤ the last stored bucket or ≥ the served
 *  slots → skipped; the same bucket moves h / l / c and sums v; a later bucket opens at the print. A NEW map only when
 *  something changed; untouched symbols keep their object identity. */
export function ggwApplyBatch(prev: GgwLiveMap, evt: GgQuotesEvent, metas: Record<string, GgwFrameMeta[]>,
                              variant: string = GGW_TAB): GgwLiveMap {
  if (!evt || evt.kind !== 'quotes' || evt.variant !== variant || !evt.quotes) return prev;
  const base = prune(prev, metas);
  let out: GgwLiveMap | null = null;
  for (const [sym, q] of Object.entries(evt.quotes)) {
    const ms = metas[sym];
    if (!ms || !ms.length || !q) continue;
    const price = q.price;
    const at = q.as_of_epoch;
    if (!fin(price) || price <= 0 || !fin(at)) continue;
    const cur: GgwLiveSym | undefined = (out ?? base)[sym];
    if (cur && at <= cur.last_epoch) continue;
    const size = fin(q.size) && q.size > 0 ? q.size : 0;
    let by: Record<string, GgwLiveBar[]> | null = null;
    for (const m of ms) {
      const b = ggwBucket(at, m.start_epoch, m.frame_min);
      if (b <= m.last_bucket || b >= m.slots) continue;
      const bars = cur?.by[m.tf] ?? [];
      const last = bars[bars.length - 1];
      let next: GgwLiveBar[];
      if (last && b < last.bucket) continue;
      if (last && b === last.bucket) {
        next = [...bars.slice(0, -1), {
          ...last, h: Math.max(last.h, price), l: Math.min(last.l, price), c: price, v: last.v + size, as_of: at,
        }];
      } else {
        next = [...bars, { bucket: b, o: price, h: price, l: price, c: price, v: size, as_of: at }];
      }
      by = { ...(by ?? cur?.by ?? {}), [m.tf]: next };
    }
    if (!by) continue;
    out = { ...(out ?? base), [sym]: { last_epoch: at, by } };
  }
  return out ?? base;
}

const TIP_SPAN: Record<string, number> = { ema9: EMA_FAST, ema21: EMA_SLOW };
type VolAvg = { values?: unknown } & Record<string, unknown>;

/** The served frame with its live bars spliced AFTER the stored ones: bars + axis.x appended (the candle sits in its
 *  slot), curves and a served `vol_avg` get a tail (null — the lines and the served average end at the last CLOSED bar;
 *  the EMA tip only when `emaTip` is on and the served unrounded tail exists). Every other key is the SAME reference.
 *  The SAME frame when no live bar is past the stored ones. The `now` line is not composed here (boldNowLines adds it
 *  from the last bar). With NO served `vol_avg`, nothing is added: the pane's own fallback average then includes the
 *  forming bar at its tail (HIS CALL #8). */
export function ggwLiveFrame(f: GgwFrame, bars: GgwLiveBar[] | undefined, opts?: { emaTip?: boolean }): GgwFrame {
  if (!bars || !bars.length) return f;
  const meta = ggwFrameMeta(f);
  if (!meta || !f.axis) return f;
  const keep = bars.filter((b) => b.bucket > meta.last_bucket && b.bucket < meta.slots);
  if (!keep.length) return f;
  const n = keep.length;
  const added: CmBar[] = keep.map((b) => {
    const s = ggwShadeOf(meta.shade, b.bucket);
    return { t: ggwBarStamp(meta.day, meta.from_et, b.bucket, meta.frame_min), o: b.o, h: b.h, l: b.l, c: b.c, v: b.v, ...(s ? { s } : {}) };
  });
  const nulls = (): null[] => new Array(n).fill(null);
  const closes = keep.map((b) => b.c);
  const tail = (c: CmCurve): (number | null)[] => {
    const span = TIP_SPAN[c.tone];
    const seed = f.ema_tail ? (f.ema_tail as Record<string, number>)[c.tone] : undefined;
    if (!opts?.emaTip || !span || !fin(seed)) return nulls();
    return ggwEmaTips(seed, closes, span);
  };
  const t0 = f.tile;
  const tile: CmTile & { vol_avg?: unknown } = { ...t0, bars: [...t0.bars, ...added] };
  if (Array.isArray(t0.curves)) tile.curves = t0.curves.map((c) => ({ ...c, values: [...(c.values || []), ...tail(c)] }));
  const va = (t0 as CmTile & { vol_avg?: VolAvg | null }).vol_avg;
  if (va && typeof va === 'object' && Array.isArray(va.values)) tile.vol_avg = { ...va, values: [...va.values, ...nulls()] };
  return { ...f, tile, axis: { ...f.axis, x: [...f.axis.x, ...keep.map((b) => b.bucket)] } };
}

/** 📈 2026-11-23 (vwapzones spec §3.9 [O2][C8]) — the forming 5- / 15-min candle built from the row's OWN 1-min chart.
 *  BUILT, OFF: the tile folds it ONLY when lib/gajjalaWatch.GGW_SEED_FORMING is on (HIS CALL #13); off, the forming candle
 *  is main's (`own` — the prints seen since the fold began).
 *  Rule: `f1` = the row's 1-min frame with live keys on the SAME `start_epoch` as `f` (and not served stale); k =
 *  f.frame_min / f1.frame_min an integer > 1; at least ONE live 1-min bar PAST the stored 1-min bars (bucket > f1's last
 *  stored bucket and < f1's slots — ggwLiveFrame's own render-time filter, so a minute the server now stores is counted
 *  ONCE, from the store [C8]). Then for every bucket b of `f` past its last stored bucket and inside its slots: the stored
 *  1-min bars with floor(slot / k) == b, then those live 1-min bars with floor(bucket / k) == b → o first, h max, l min,
 *  c last, v sum, as_of the last live stamp (a stored-only bucket: its last minute's close on the served grid). A bucket of
 *  `own` the seed does not cover is kept as it is. Anything else → `own` unchanged (no live print → no forming candle). */
export function ggwSeedLive(f: GgwFrame, own: GgwLiveBar[] | undefined, f1: GgwFrame | null | undefined,
                            live1: GgwLiveBar[] | undefined): GgwLiveBar[] | undefined {
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
  const n1 = Math.min(bars1.length, x1.length);
  for (let i = 0; i < n1; i += 1) {
    const s = x1[i];
    const bar = bars1[i];
    if (!fin(s) || !bar || ![bar.o, bar.h, bar.l, bar.c].every(fin)) continue;
    push(Math.floor(s / k), {
      o: bar.o, h: bar.h, l: bar.l, c: bar.c, v: fin(bar.v) && bar.v > 0 ? bar.v : 0,
      as_of: m1.start_epoch + (s + 1) * m1.frame_min * 60,
    });
  }
  for (const b of past1) push(Math.floor(b.bucket / k), { o: b.o, h: b.h, l: b.l, c: b.c, v: b.v, as_of: b.as_of });
  if (!parts.size) return own;
  const seeded = new Map<number, GgwLiveBar>();
  for (const [b, ps] of parts) {
    seeded.set(b, {
      bucket: b, o: ps[0].o, h: Math.max(...ps.map((p) => p.h)), l: Math.min(...ps.map((p) => p.l)),
      c: ps[ps.length - 1].c, v: ps.reduce((a, p) => a + p.v, 0), as_of: ps[ps.length - 1].as_of ?? 0,
    });
  }
  for (const b of own || []) if (b && !seeded.has(b.bucket)) seeded.set(b.bucket, b);
  return [...seeded.values()].sort((a, b) => a.bucket - b.bucket);
}
