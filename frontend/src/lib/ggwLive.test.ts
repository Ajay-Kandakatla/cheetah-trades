/* 👀 Gajjala's Watch LIVE — the pure reducer (2026-11-16, watch-live spec §3.4 / §4 WP-C).
 * Ajay 2026-11-16: "Can you make the watch list charts live please" · "Realtime updates.. Like the 1 min chart I need it
 * to be live live.. per sec change" · "Also on the Watch list I need live volume to be shown at the bottom" · "Of each
 * chart". The forming candle and its live volume column fold from the raw 1 Hz batches on the SERVER's own grid and
 * splice after the stored bars; the next GET wins. NEGATIVES throughout: a replayed / older batch never adds volume
 * twice, a stale / prior-session row carries nothing (C2), every non-bar key is the SAME reference (the cross path never
 * sees a live bar), the served average and the 9 / 21 lines end at the last CLOSED bar. */
import { describe, expect, it } from 'vitest';
import fixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import { curveLabels, type CmTile } from './chartMaps';
import type { GgQuotesEvent, GgStreamQuote } from './cardLive';
import { GGW_TAB, parseGgw, type GgwBoard, type GgwFrame } from './gajjalaWatch';
import { ggwEmaTips } from './ggwEma';
import {
  ggwApplyBatch, ggwBarStamp, ggwBucket, ggwFrameMeta, ggwFrameMetas, ggwLiveFrame, ggwShadeOf,
  type GgwFrameMeta, type GgwLiveBar, type GgwLiveMap,
} from './ggwLive';
import { paneVolumeAverage, VOLUME_SMA_LEN } from './volumePane';

/* The fixture's session is 2026-11-13 (EST): 04:00 ET = 09:00 UTC. In production the SERVER serves start_epoch
 * (build.axis); the test only stands in for that served key. */
const START = Date.UTC(2026, 10, 13, 9, 0, 0) / 1000;
const FM: Record<string, number> = { '1m': 1, '3m': 3, '5m': 5 };
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

function liveRaw(mut?: (raw: any) => void): any {
  const raw = clone(fixture) as any;
  for (const r of raw.rows) {
    for (const f of r.frames || []) Object.assign(f.axis, { start_epoch: START, frame_min: FM[f.tf], from_et: '04:00' });
  }
  mut?.(raw);
  return raw;
}
const board = (mut?: (raw: any) => void) => parseGgw(liveRaw(mut)) as GgwBoard;
const omh = (b: GgwBoard = board()) => b.rows[0];
const frameOf = (b: GgwBoard, tf: string) => omh(b).frames.find((f) => f.tf === tf)!;
const evt = (quotes: Record<string, GgStreamQuote>, variant = GGW_TAB): GgQuotesEvent => ({ kind: 'quotes', variant, quotes });
/** A print `sec` seconds into 1-minute bucket `k1` of the fixture's session. */
const at1 = (k1: number, sec = 5) => START + k1 * 60 + sec;

describe('👀 ggwBucket — closed=left on the served grid', () => {
  it('boundaries for 1 / 3 / 5 minutes: AT a boundary opens the NEW bucket; 1 ms earlier is the previous one', () => {
    for (const [fm, step] of [[1, 60], [3, 180], [5, 300]]) {
      for (const k of [1, 2, 66, 111, 143, 659]) {
        expect(ggwBucket(START + step * k, START, fm), `fm ${fm} k ${k}`).toBe(k);
        expect(ggwBucket(START + step * k - 0.001, START, fm), `fm ${fm} k ${k} −1ms`).toBe(k - 1);
      }
      expect(ggwBucket(START, START, fm)).toBe(0);
    }
  });
  it('NEGATIVE: a print before the session start is a negative bucket (never bucket 0)', () => {
    expect(ggwBucket(START - 0.001, START, 1)).toBe(-1);
  });
});

describe('👀 ggwBarStamp — the bar CLOSE label (bars.py: t = the right label)', () => {
  it('the spec cases', () => {
    expect(ggwBarStamp('2026-11-16', '04:00', 0, 1)).toBe('2026-11-16 04:01');
    expect(ggwBarStamp('2026-11-16', '04:00', 111, 3)).toBe('2026-11-16 09:36');
    expect(ggwBarStamp('2026-11-16', '04:00', 66, 5)).toBe('2026-11-16 09:35');
    expect(ggwBarStamp('2026-11-16', '04:00', 659, 1)).toBe('2026-11-16 15:00');   // the live probe's last stored stamp at x 659
    expect(ggwBarStamp('2026-11-16', '04:00', 660, 1)).toBe('2026-11-16 15:01');
    expect(ggwBarStamp('2026-11-16', '04:00', 220, 3)).toBe('2026-11-16 15:03');
    expect(ggwBarStamp('2026-11-16', '04:00', 132, 5)).toBe('2026-11-16 15:05');
  });
  it('matches every stored stamp of the fixture at its served slot (the same grid as the server)', () => {
    for (const f of omh().frames) {
      const ax = f.axis!;
      f.tile.bars.forEach((b, i) => expect(ggwBarStamp('2026-11-13', '04:00', ax.x[i], FM[f.tf])).toBe(b.t));
    }
  });
});

describe('👀 ggwShadeOf — the served span kind holding the bucket', () => {
  const shade = [{ from_slot: 0, to_slot: 330, kind: 'pre' }, { from_slot: 720, to_slot: 960, kind: 'ah' }];
  it('pre / ah / RTH, spans are [from, to)', () => {
    expect(ggwShadeOf(shade, 0)).toBe('pre');
    expect(ggwShadeOf(shade, 329)).toBe('pre');
    expect(ggwShadeOf(shade, 330)).toBeUndefined();
    expect(ggwShadeOf(shade, 500)).toBeUndefined();
    expect(ggwShadeOf(shade, 720)).toBe('ah');
  });
  it('NEGATIVE: no shade / an unknown kind → undefined', () => {
    expect(ggwShadeOf(null, 5)).toBeUndefined();
    expect(ggwShadeOf(undefined, 5)).toBeUndefined();
    expect(ggwShadeOf([{ from_slot: 0, to_slot: 10, kind: 'other' }], 5)).toBeUndefined();
    expect(ggwShadeOf([{ from_slot: 0, to_slot: 10 }], 5)).toBeUndefined();
  });
});

describe('👀 ggwFrameMeta / ggwFrameMetas (C2: only ggwRowLive rows)', () => {
  it('a live frame: the served grid, the last stored bucket, the day of the last bar', () => {
    const m = ggwFrameMeta(frameOf(board(), '1m'))!;
    expect(m).toEqual({
      tf: '1m', start_epoch: START, frame_min: 1, slots: 720, last_bucket: 389, day: '2026-11-13', from_et: '04:00',
      shade: [{ from_slot: 0, to_slot: 330, kind: 'pre' }],
    });
    expect(ggwFrameMeta(frameOf(board(), '3m'))!.last_bucket).toBe(129);
    expect(ggwFrameMeta(frameOf(board(), '5m'))!.last_bucket).toBe(77);
  });
  it('NEGATIVE: an older payload (no live keys), no axis, or no bars → null', () => {
    const old = parseGgw(clone(fixture)) as GgwBoard;
    for (const f of omh(old).frames) expect(ggwFrameMeta(f)).toBeNull();
    const f = frameOf(board(), '1m');
    expect(ggwFrameMeta({ ...f, axis: null })).toBeNull();
    expect(ggwFrameMeta({ ...f, axis: { ...f.axis!, start_epoch: null } })).toBeNull();
    expect(ggwFrameMeta({ ...f, axis: { ...f.axis!, frame_min: null } })).toBeNull();
    expect(ggwFrameMeta({ ...f, axis: { ...f.axis!, from_et: null } })).toBeNull();
    expect(ggwFrameMeta({ ...f, tile: { ...f.tile, bars: [] } })).toBeNull();
  });
  it('metas: an ok fresh row gets all three frames; stale (NVDA), pending, no_prints rows get none', () => {
    const ms = ggwFrameMetas(board().rows);
    expect(Object.keys(ms)).toEqual(['OMH']);
    expect(ms.OMH.map((m) => m.tf)).toEqual(['1m', '3m', '5m']);
  });
  it('NEGATIVE: a prior-session row contributes none; the same NVDA un-staled contributes all three', () => {
    expect(ggwFrameMetas(board((r) => { r.rows[0].from_session = '2026-11-12'; }).rows)).toEqual({});
    const ms = ggwFrameMetas(board((r) => { r.rows[3].stale = false; }).rows);
    expect(Object.keys(ms)).toEqual(['OMH', 'NVDA']);
  });
  it('NEGATIVE: an older payload → no metas at all; a frame without start_epoch is left out of its row', () => {
    expect(ggwFrameMetas((parseGgw(clone(fixture)) as GgwBoard).rows)).toEqual({});
    const ms = ggwFrameMetas(board((r) => { delete r.rows[0].frames[1].axis.start_epoch; }).rows);
    expect(ms.OMH.map((m) => m.tf)).toEqual(['1m', '5m']);
  });
});

describe('👀 ggwApplyBatch — the fold (spec §3.4 rules 1–5)', () => {
  const metas = () => ggwFrameMetas(board().rows);

  it('a first print opens {o = h = l = c = price, v = size} in every frame whose bucket is new', () => {
    const m = ggwApplyBatch({}, evt({ OMH: { price: 4.01, as_of_epoch: at1(390), vs: null, size: 500 } }), metas());
    const s = m.OMH;
    expect(s.last_epoch).toBe(at1(390));
    expect(s.by['1m']).toEqual([{ bucket: 390, o: 4.01, h: 4.01, l: 4.01, c: 4.01, v: 500, as_of: at1(390) }]);
    expect(s.by['3m']).toEqual([{ bucket: 130, o: 4.01, h: 4.01, l: 4.01, c: 4.01, v: 500, as_of: at1(390) }]);
    expect(s.by['5m']).toEqual([{ bucket: 78, o: 4.01, h: 4.01, l: 4.01, c: 4.01, v: 500, as_of: at1(390) }]);
  });

  it('a second print in the same bucket moves h / l / c and SUMS v; a later bucket opens its own candle', () => {
    const ms = metas();
    let m = ggwApplyBatch({}, evt({ OMH: { price: 4.01, as_of_epoch: at1(390, 1), vs: null, size: 500 } }), ms);
    m = ggwApplyBatch(m, evt({ OMH: { price: 4.05, as_of_epoch: at1(390, 2), vs: null, size: 100 } }), ms);
    m = ggwApplyBatch(m, evt({ OMH: { price: 3.98, as_of_epoch: at1(390, 3), vs: null, size: 50 } }), ms);
    expect(m.OMH.by['1m']).toEqual([{ bucket: 390, o: 4.01, h: 4.05, l: 3.98, c: 3.98, v: 650, as_of: at1(390, 3) }]);
    m = ggwApplyBatch(m, evt({ OMH: { price: 3.99, as_of_epoch: at1(391, 0), vs: null, size: 7 } }), ms);
    expect(m.OMH.by['1m'].map((b) => [b.bucket, b.o, b.v])).toEqual([[390, 4.01, 650], [391, 3.99, 7]]);
    // 1-min bucket 391 is still inside the 3-min bucket 130 and the 5-min bucket 78: merged there, not opened.
    expect(m.OMH.by['3m']).toEqual([{ bucket: 130, o: 4.01, h: 4.05, l: 3.98, c: 3.99, v: 657, as_of: at1(391, 0) }]);
    expect(m.OMH.by['5m']).toHaveLength(1);
  });

  it('NEGATIVE: the SAME batch twice → the SAME object, v unchanged (a replay never adds volume twice)', () => {
    const ms = metas();
    const e = evt({ OMH: { price: 4.01, as_of_epoch: at1(390), vs: null, size: 500 } });
    const m1 = ggwApplyBatch({}, e, ms);
    const m2 = ggwApplyBatch(m1, e, ms);
    expect(m2).toBe(m1);
    expect(m2.OMH.by['1m'][0].v).toBe(500);
  });

  it('NEGATIVE: an older as_of → the SAME object (price AND size skipped)', () => {
    const ms = metas();
    const m1 = ggwApplyBatch({}, evt({ OMH: { price: 4.01, as_of_epoch: at1(390, 30), vs: null, size: 500 } }), ms);
    expect(ggwApplyBatch(m1, evt({ OMH: { price: 9, as_of_epoch: at1(390, 10), vs: null, size: 999 } }), ms)).toBe(m1);
  });

  it('size null / absent / junk → the close moves, v unchanged', () => {
    const ms = metas();
    const m1 = ggwApplyBatch({}, evt({ OMH: { price: 4.01, as_of_epoch: at1(390, 1), vs: null, size: 500 } }), ms);
    const m2 = ggwApplyBatch(m1, evt({ OMH: { price: 4.02, as_of_epoch: at1(390, 2), vs: null, size: null } }), ms);
    expect(m2.OMH.by['1m'][0]).toMatchObject({ c: 4.02, h: 4.02, v: 500 });
    const m3 = ggwApplyBatch(m2, evt({ OMH: { price: 4.03, as_of_epoch: at1(390, 3), vs: null } }), ms);
    expect(m3.OMH.by['1m'][0]).toMatchObject({ c: 4.03, v: 500 });
    const m4 = ggwApplyBatch(m3, evt({ OMH: { price: 4.04, as_of_epoch: at1(390, 4), vs: null, size: 'x' as any } }), ms);
    expect(m4.OMH.by['1m'][0]).toMatchObject({ c: 4.04, v: 500 });
    const first = ggwApplyBatch({}, evt({ OMH: { price: 4.01, as_of_epoch: at1(390), vs: null, size: null } }), ms);
    expect(first.OMH.by['1m'][0].v).toBe(0);                 // a live bar with v 0 (the chart draws no column for it)
  });

  it('NEGATIVE: another variant / another kind / a symbol not on the live rows → the SAME object', () => {
    const ms = metas();
    const prev: GgwLiveMap = {};
    const q = { price: 4.01, as_of_epoch: at1(390), vs: null, size: 500 };
    expect(ggwApplyBatch(prev, evt({ OMH: q }, 'gajjala'), ms)).toBe(prev);
    expect(ggwApplyBatch(prev, evt({ OMH: q }, 'gajjala_1m'), ms)).toBe(prev);
    expect(ggwApplyBatch(prev, { kind: 'pass', variant: GGW_TAB, pass_id: 'p', finished_at_epoch: 1 } as any, ms)).toBe(prev);
    expect(ggwApplyBatch(prev, evt({ ZZZ: q }), ms)).toBe(prev);
    expect(ggwApplyBatch(prev, evt({ NVDA: q }), ms)).toBe(prev);   // NVDA is stale (C2)
    expect(ggwApplyBatch(prev, evt({ AMD: q }), ms)).toBe(prev);    // pending
  });

  it('NEGATIVE: a bucket ≤ the last stored bucket, or ≥ the served slots → the SAME object', () => {
    const ms = metas();
    const prev: GgwLiveMap = {};
    expect(ggwApplyBatch(prev, evt({ OMH: { price: 4, as_of_epoch: at1(389), vs: null, size: 5 } }), ms)).toBe(prev);
    expect(ggwApplyBatch(prev, evt({ OMH: { price: 4, as_of_epoch: at1(10), vs: null, size: 5 } }), ms)).toBe(prev);
    expect(ggwApplyBatch(prev, evt({ OMH: { price: 4, as_of_epoch: at1(720), vs: null, size: 5 } }), ms)).toBe(prev);
    expect(ggwApplyBatch(prev, evt({ OMH: { price: 4, as_of_epoch: at1(800), vs: null, size: 5 } }), ms)).toBe(prev);
  });

  it('per frame: a bucket past the 1-min slots but … only the frames whose bucket is in range move', () => {
    // 3-min slots 240 = minute 720 = the 1-min slots: the three grids end together, so check one frame cut short.
    const ms = metas();
    const cut = { ...ms, OMH: ms.OMH.map((m) => (m.tf === '5m' ? { ...m, slots: 78 } : m)) };
    const m = ggwApplyBatch({}, evt({ OMH: { price: 4, as_of_epoch: at1(390), vs: null, size: 5 } }), cut);
    expect(Object.keys(m.OMH.by).sort()).toEqual(['1m', '3m']);
  });

  it('NEGATIVE: a meta without start_epoch (an older doc) → the SAME object', () => {
    const oldMetas = ggwFrameMetas((parseGgw(clone(fixture)) as GgwBoard).rows);
    const prev: GgwLiveMap = {};
    expect(ggwApplyBatch(prev, evt({ OMH: { price: 4, as_of_epoch: at1(390), vs: null, size: 5 } }), oldMetas)).toBe(prev);
  });

  it('prune: live buckets the server now holds are dropped; symbols gone / turned stale are dropped', () => {
    const ms = metas();
    let m = ggwApplyBatch({}, evt({ OMH: { price: 4.01, as_of_epoch: at1(390), vs: null, size: 500 } }), ms);
    m = ggwApplyBatch(m, evt({ OMH: { price: 4.02, as_of_epoch: at1(391), vs: null, size: 9 } }), ms);
    expect(m.OMH.by['1m'].map((b) => b.bucket)).toEqual([390, 391]);
    // The next GET stores bucket 390 (1m) — the next batch prunes it, keeps 391.
    const ms2 = { ...ms, OMH: ms.OMH.map((x) => (x.tf === '1m' ? { ...x, last_bucket: 390 } : x)) };
    const m2 = ggwApplyBatch(m, evt({ OMH: { price: 4.03, as_of_epoch: at1(391, 30), vs: null, size: 1 } }), ms2);
    expect(m2.OMH.by['1m'].map((b) => [b.bucket, b.v])).toEqual([[391, 10]]);
    // A batch for another symbol still prunes: the row turned stale (no metas) → its live bars go.
    const m3 = ggwApplyBatch(m2, evt({ ZZZ: { price: 1, as_of_epoch: at1(392), vs: null, size: 1 } }), {});
    expect(m3).not.toBe(m2);
    expect(m3).toEqual({});
  });

  it('prune NEGATIVE: a live bar from before the frame\'s session start never survives into a new session', () => {
    const ms = metas();
    const old: GgwLiveMap = { OMH: { last_epoch: START - 3600, by: { '1m': [{ bucket: 700, o: 1, h: 1, l: 1, c: 1, v: 1, as_of: START - 3600 }] } } };
    const m = ggwApplyBatch(old, evt({ OMH: { price: 4, as_of_epoch: at1(390), vs: null, size: 5 } }), ms);
    expect(m.OMH.by['1m'].map((b) => b.bucket)).toEqual([390]);
  });

  it('identity: untouched symbols and frames keep their objects', () => {
    const ms = ggwFrameMetas(board((r) => { r.rows[3].stale = false; }).rows);
    const m1 = ggwApplyBatch({}, evt({
      OMH: { price: 4.01, as_of_epoch: at1(390), vs: null, size: 5 },
      NVDA: { price: 175, as_of_epoch: at1(390), vs: null, size: 5 },
    }), ms);
    const m2 = ggwApplyBatch(m1, evt({ NVDA: { price: 176, as_of_epoch: at1(390, 9), vs: null, size: 1 } }), ms);
    expect(m2).not.toBe(m1);
    expect(m2.OMH).toBe(m1.OMH);
    expect(m2.NVDA).not.toBe(m1.NVDA);
    expect(m1.NVDA.by['1m'][0].v).toBe(5);                    // the input is never mutated
  });
});

describe('👀 ggwLiveFrame — the splice (spec §3.4)', () => {
  const live1m = (over: Partial<GgwLiveBar> = {}): GgwLiveBar[] =>
    [{ bucket: 390, o: 4.0, h: 4.06, l: 3.99, c: 4.05, v: 500, as_of: at1(390), ...over }];

  it('NEGATIVE: no live bars, no live grid, or nothing past the stored bars → the SAME frame', () => {
    const f = frameOf(board(), '1m');
    expect(ggwLiveFrame(f, undefined)).toBe(f);
    expect(ggwLiveFrame(f, [])).toBe(f);
    const old = omh(parseGgw(clone(fixture)) as GgwBoard).frames[0];
    expect(ggwLiveFrame(old, live1m())).toBe(old);
    expect(ggwLiveFrame(f, live1m({ bucket: 389 }))).toBe(f);
    expect(ggwLiveFrame(f, live1m({ bucket: 720 }))).toBe(f);
  });

  it('bars and axis.x appended with the close stamp; the candle sits in its slot (x.length === bars.length)', () => {
    const f = frameOf(board(), '1m');
    const g = ggwLiveFrame(f, live1m());
    expect(g).not.toBe(f);
    expect(g.tile.bars).toHaveLength(f.tile.bars.length + 1);
    expect(g.tile.bars[g.tile.bars.length - 1]).toEqual({ t: '2026-11-13 10:31', o: 4.0, h: 4.06, l: 3.99, c: 4.05, v: 500 });
    expect(g.axis!.x).toEqual([...f.axis!.x, 390]);
    expect(g.axis!.x.length).toBe(g.tile.bars.length);
    expect(g.tile.bars.slice(0, -1)).toEqual(f.tile.bars);
    expect(f.tile.bars).toHaveLength(390);                    // the input is never mutated
    expect(f.axis!.x).toHaveLength(390);
  });

  it('the shading tag comes from the served span: "pre" inside the pre span, none in RTH', () => {
    const f = frameOf(board((r) => {
      const fr = r.rows[0].frames[0];
      fr.tile.bars = fr.tile.bars.slice(0, 100);
      fr.axis.x = fr.axis.x.slice(0, 100);
      for (const c of fr.tile.curves) c.values = c.values.slice(0, 100);
    }), '1m');
    const g = ggwLiveFrame(f, [{ bucket: 100, o: 4, h: 4, l: 4, c: 4, v: 1, as_of: at1(100) }]);
    expect(g.tile.bars[100]).toMatchObject({ t: '2026-11-13 05:41', s: 'pre' });
    const rth = ggwLiveFrame(frameOf(board(), '1m'), live1m());
    expect(rth.tile.bars[rth.tile.bars.length - 1]).not.toHaveProperty('s');
  });

  it('curves get a null tail of the right length; curveLabels still names the last CLOSED value', () => {
    const f = frameOf(board(), '1m');
    const g = ggwLiveFrame(f, [...live1m(), { bucket: 392, o: 4, h: 4, l: 4, c: 4, v: 2, as_of: at1(392) }]);
    for (const [i, c] of (g.tile.curves || []).entries()) {
      const c0 = f.tile.curves![i];
      expect(c.values).toHaveLength(c0.values.length + 2);
      expect(c.values.slice(-2)).toEqual([null, null]);
      expect(c.tone).toBe(c0.tone);
    }
    expect(curveLabels(g.tile.curves)).toEqual(curveLabels(f.tile.curves));
    expect(g.axis!.x.slice(-2)).toEqual([390, 392]);
  });

  it('HIS CALL #1 OFF by default: even with a served ema_tail the lines end at the last closed bar', () => {
    const f0 = frameOf(board((r) => { r.rows[0].frames[0].ema_tail = { ema9: 4.0012345678, ema21: 3.99876543 }; }), '1m');
    expect(f0.ema_tail).not.toBeNull();
    const g = ggwLiveFrame(f0, live1m());
    for (const c of g.tile.curves || []) expect(c.values[c.values.length - 1]).toBeNull();
  });

  it('with emaTip on and a served tail: the tip is ggwEmaTips from the UNROUNDED tail; NEGATIVE: no tail → null', () => {
    const tail = { ema9: 4.0012345678, ema21: 3.99876543 };
    const f0 = frameOf(board((r) => { r.rows[0].frames[0].ema_tail = tail; }), '1m');
    const bars = [...live1m(), { bucket: 391, o: 4, h: 4.1, l: 4, c: 4.08, v: 2, as_of: at1(391) }];
    const g = ggwLiveFrame(f0, bars, { emaTip: true });
    const by = Object.fromEntries((g.tile.curves || []).map((c) => [c.tone, c.values.slice(-2)]));
    expect(by.ema9).toEqual(ggwEmaTips(tail.ema9, [4.05, 4.08], 9));
    expect(by.ema21).toEqual(ggwEmaTips(tail.ema21, [4.05, 4.08], 21));
    const noTail = ggwLiveFrame(frameOf(board(), '1m'), bars, { emaTip: true });
    for (const c of noTail.tile.curves || []) expect(c.values.slice(-2)).toEqual([null, null]);
  });

  it('a served vol_avg gets a null tail: the pane still uses the SERVED average, the forming bar is never in it', () => {
    const f0 = frameOf(board((r) => {
      const t = r.rows[0].frames[0].tile;
      t.vol_avg = { period: VOLUME_SMA_LEN, label: 'Vol avg 50', values: t.bars.map((_: unknown, i: number) => 1000 + i) };
    }), '1m');
    const g = ggwLiveFrame(f0, live1m());
    const va = (g.tile as CmTile & { vol_avg: { period: number; label: string; values: (number | null)[] } }).vol_avg;
    expect(va.values).toHaveLength(g.tile.bars.length);
    expect(va.values[va.values.length - 1]).toBeNull();
    expect(va.period).toBe(VOLUME_SMA_LEN);
    expect(va.label).toBe('Vol avg 50');
    const pane = paneVolumeAverage(g.tile.bars.map((b) => b.v), va);
    expect(pane.served).toBe(true);
    expect(pane.values[pane.values.length - 1]).toBeNull();
  });

  it('NO served vol_avg → nothing added; the pane fallback includes the forming bar at its tail (HIS CALL #8)', () => {
    const f = frameOf(board(), '1m');
    expect((f.tile as any).vol_avg).toBeNull();
    const g = ggwLiveFrame(f, live1m());
    expect((g.tile as any).vol_avg).toBeNull();
    const vols = g.tile.bars.map((b) => b.v);
    const pane = paneVolumeAverage(vols, (g.tile as any).vol_avg);
    expect(pane.served).toBe(false);
    const last50 = vols.slice(-VOLUME_SMA_LEN);
    expect(last50[last50.length - 1]).toBe(500);
    expect(pane.values[pane.values.length - 1]).toBeCloseTo(last50.reduce((a, b) => a + b, 0) / VOLUME_SMA_LEN, 9);
  });

  it('NEGATIVE: every non-bar key is the SAME reference (the cross path never sees a live bar)', () => {
    const f0 = frameOf(board((r) => {
      const fr = r.rows[0].frames[0];
      fr.ema_blink = { on: true };
      fr.run_bases = { text: 'base 1', title: 't' };
      fr.tile.ellipses = [{ kind: 'k', from_t: 'a', to_t: 'b', lo: 1, hi: 2 }];
      fr.tile.lines = [{ price: 4, label: 'x', tone: 'trigger' }];
    }), '1m');
    const g = ggwLiveFrame(f0, live1m());
    expect(g).not.toBe(f0);
    for (const k of ['tf', 'label', 'ema_cross', 'ema_blink', 'held', 'uptrend', 'run_bases', 'ema_tail'] as const) {
      expect(g[k], k).toBe(f0[k]);
    }
    const t0 = f0.tile as any;
    const t1 = g.tile as any;
    for (const k of ['lines', 'markers', 'bands', 'stats', 'ellipses', 'symbol', 'href', 'why']) expect(t1[k], k).toBe(t0[k]);
    expect(g.axis!.shade).toBe(f0.axis!.shade);
    expect(g.axis!.ticks).toBe(f0.axis!.ticks);
    expect(g.axis!.start_epoch).toBe(f0.axis!.start_epoch);
    expect(t1.lines.some((l: any) => l.tone === 'now')).toBe(false);   // the now line is boldNowLines', not composed here
  });

  it('server wins: once the GET serves the live bucket, the live bar is dropped and the served bar (its v) remains', () => {
    const live = live1m({ v: 500 });
    const served = board((r) => {
      const fr = r.rows[0].frames[0];
      fr.tile.bars.push({ t: '2026-11-13 10:31', o: 4.0, h: 4.06, l: 3.99, c: 4.04, v: 123 });
      fr.axis.x.push(390);
      for (const c of fr.tile.curves) c.values.push(4.0);
    });
    const f = frameOf(served, '1m');
    const g = ggwLiveFrame(f, live);
    expect(g).toBe(f);
    expect(g.tile.bars.filter((b) => b.t === '2026-11-13 10:31')).toEqual([{ t: '2026-11-13 10:31', o: 4.0, h: 4.06, l: 3.99, c: 4.04, v: 123 }]);
    // and the reducer prunes it from storage at the next batch
    const m: GgwLiveMap = { OMH: { last_epoch: at1(390), by: { '1m': live } } };
    const m2 = ggwApplyBatch(m, evt({ OMH: { price: 4.1, as_of_epoch: at1(391), vs: null, size: 3 } }), ggwFrameMetas(served.rows));
    expect(m2.OMH.by['1m'].map((b) => [b.bucket, b.v])).toEqual([[391, 3]]);
  });

  it('a live bar with v 0 is appended (WP-D pins that the chart draws no column for it)', () => {
    const g = ggwLiveFrame(frameOf(board(), '1m'), live1m({ v: 0 }));
    expect(g.tile.bars[g.tile.bars.length - 1].v).toBe(0);
  });

  it('3-min / 5-min frames splice on their own grid', () => {
    const b = board();
    const m = ggwApplyBatch({}, evt({ OMH: { price: 4.01, as_of_epoch: at1(390), vs: null, size: 500 } }), ggwFrameMetas(b.rows));
    const g3 = ggwLiveFrame(frameOf(b, '3m'), m.OMH.by['3m']);
    const g5 = ggwLiveFrame(frameOf(b, '5m'), m.OMH.by['5m']);
    expect(g3.tile.bars[g3.tile.bars.length - 1].t).toBe('2026-11-13 10:33');
    expect(g5.tile.bars[g5.tile.bars.length - 1].t).toBe('2026-11-13 10:35');
    expect(g3.axis!.x.slice(-1)).toEqual([130]);
    expect(g5.axis!.x.slice(-1)).toEqual([78]);
  });
});

// type-only use so an unused-import lint never strips the meta type from the public surface
export type _Meta = GgwFrameMeta;
export type _Frame = GgwFrame;
