/* 🚩 card view LIVE plumbing (2026-11-16, ggcard3 spec §3.2 / §4 WP-A). The 👀 Watch's ONE reducer, parameterised:
 * ggwApplyBatch folds another bus variant only when asked (default = the Watch's tab, unchanged), and ggwFrameMetas
 * drops a frame SERVED as stale (C3 — a stale 1-minute frame carries no forming bar while its 15m / 5m siblings stay
 * live). NEGATIVES: a 'gajjala' batch is ignored by default; a Watch row (no `stale` key on its frames) keeps all three
 * metas; a batch for the stale frame's bucket changes nothing on it. */
import { describe, expect, it } from 'vitest';
import fixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import type { GgQuotesEvent, GgStreamQuote } from './cardLive';
import { GGW_TAB, parseGgw, type GgwBoard, type GgwRow } from './gajjalaWatch';
import { ggwApplyBatch, ggwFrameMetas } from './ggwLive';

const START = Date.UTC(2026, 10, 13, 9, 0, 0) / 1000;
const FM: Record<string, number> = { '1m': 1, '3m': 3, '5m': 5 };
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const at1 = (k1: number, sec = 5) => START + k1 * 60 + sec;
const evt = (quotes: Record<string, GgStreamQuote>, variant: string): GgQuotesEvent => ({ kind: 'quotes', variant, quotes });

/** OMH's three served frames with the live axis keys; `card` → relabelled 15m / 5m / 1m as the card view serves them,
 *  `stale1m` → the 1m frame carries `stale: true` (and the others `stale: false`). */
function omh(opts: { card?: boolean; stale1m?: boolean } = {}): GgwRow {
  const raw = clone(fixture) as any;
  const r = raw.rows[0];
  for (const f of r.frames) {
    Object.assign(f.axis, { start_epoch: START, frame_min: FM[f.tf], from_et: '04:00' });
    if (opts.card) {
      if (f.tf === '3m') f.tf = '15m';
      f.as_of_et = '09:41';
      f.stale = opts.stale1m ? f.tf === '1m' : false;
    }
  }
  raw.rows = [r];
  return (parseGgw(raw) as GgwBoard).rows[0];
}

describe('🚩 ggwApplyBatch(…, variant) — the ONE reducer, another bus tab only when asked', () => {
  const q = { OMH: { price: 4.01, as_of_epoch: at1(390), vs: null, size: 500 } };
  it("NEGATIVE: a 'gajjala' batch is ignored by default (the Watch's tab) — the SAME map back", () => {
    const metas = ggwFrameMetas([omh()]);
    const prev = {};
    expect(ggwApplyBatch(prev, evt(q, 'gajjala'), metas)).toBe(prev);
  });
  it("accepted with variant='gajjala'; NEGATIVE: then the Watch's own tab is ignored", () => {
    const metas = ggwFrameMetas([omh()]);
    const m = ggwApplyBatch({}, evt(q, 'gajjala'), metas, 'gajjala');
    expect(m.OMH.by['1m']).toEqual([{ bucket: 390, o: 4.01, h: 4.01, l: 4.01, c: 4.01, v: 500, as_of: at1(390) }]);
    const prev = {};
    expect(ggwApplyBatch(prev, evt(q, GGW_TAB), metas, 'gajjala')).toBe(prev);
    expect(ggwApplyBatch(prev, evt(q, 'gajjala_1m'), metas, 'gajjala')).toBe(prev);
  });
  it('the default still folds the Watch tab exactly as before', () => {
    const m = ggwApplyBatch({}, evt(q, GGW_TAB), ggwFrameMetas([omh()]));
    expect(Object.keys(m.OMH.by).sort()).toEqual(['1m', '3m', '5m']);
  });
});

describe('🚩 ggwFrameMetas — a frame served stale carries no live bar (C3)', () => {
  it('1m stale, 15m / 5m not → metas for 15m and 5m ONLY', () => {
    const metas = ggwFrameMetas([omh({ card: true, stale1m: true })]);
    expect(metas.OMH.map((m) => m.tf).sort()).toEqual(['15m', '5m']);
  });
  it('NEGATIVE: a Watch row (no `stale` key on its frames) → all three metas as today', () => {
    const row = omh();
    for (const f of row.frames) expect('stale' in f).toBe(false);
    expect(ggwFrameMetas([row]).OMH.map((m) => m.tf).sort()).toEqual(['1m', '3m', '5m']);
  });
  it('NEGATIVE: served `stale: false` on every frame → all three metas', () => {
    expect(ggwFrameMetas([omh({ card: true })]).OMH.map((m) => m.tf).sort()).toEqual(['15m', '1m', '5m']);
  });
  it('NEGATIVE: a batch in the stale frame\'s next bucket adds nothing on 1m; 15m and 5m still fold', () => {
    const metas = ggwFrameMetas([omh({ card: true, stale1m: true })]);
    const m = ggwApplyBatch({}, evt({ OMH: { price: 4.01, as_of_epoch: at1(390), vs: null, size: 500 } }, 'gajjala'),
      metas, 'gajjala');
    expect(m.OMH.by['1m']).toBeUndefined();
    expect(m.OMH.by['5m']).toHaveLength(1);
    expect(m.OMH.by['15m']).toHaveLength(1);
  });
  /* 2026-11-23 (re-pinned, spec ggconn WP-1): omh() is built by parseGgw, which sets the Watch-only stale_keeps_live;
   * a card row (ggcRow) never carries it — strip it so this row is the card view's. */
  it('NEGATIVE: the row rule still wins — a card row served stale carries no metas', () => {
    const { stale_keeps_live: _watchOnly, ...card } = omh({ card: true });
    const row: GgwRow = { ...card, stale: true };
    expect('stale_keeps_live' in row).toBe(false);
    expect(ggwFrameMetas([row])).toEqual({});
  });
});
