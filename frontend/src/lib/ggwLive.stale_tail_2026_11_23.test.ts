/* 👀 Gajjala's Watch — a failed minute read keeps the live tail (2026-11-23, spec ggconn §3.1 / §4 WP-1).
 * Ajay 2026-11-23: "Can you clean up some connection I am seeing delays price update for AKAN on the watch chart..".
 *
 * ONE rule stays (ggwRowLive). A Watch row (parseRow) carries `stale_keeps_live: true`, so a ⚠️ stale row of TODAY
 * keeps its forming candle; a 🚩 / 🧪 card-view row (ggcRow / GGC_NO_FRAMES) never carries it, so a stale card stays
 * dark. NEGATIVES: no flag → dark; the flag with from_session → dark; not-ok states → dark; a junk flag → dark; a card
 * row never carries the flag (value + source); the per-frame `stale` rule is unchanged. The tail is fed by the socket
 * only — this changes nothing while the feed is blind (that is the board test's NEGATIVE). */
import { describe, expect, it } from 'vitest';
import fixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import type { GgQuotesEvent, GgStreamQuote } from './cardLive';
import type { GgTile } from './gajjala';
import { GGC_NO_FRAMES, ggcRow, parseGgc, type GgcPayload } from './gajjalaCardView';
import { GGW_TAB, ggwRowLive, parseGgw, type GgwBoard, type GgwRow } from './gajjalaWatch';
import { ggwApplyBatch, ggwFrameMetas, type GgwLiveMap } from './ggwLive';

const START = Date.UTC(2026, 10, 13, 9, 0, 0) / 1000;
const FM: Record<string, number> = { '1m': 1, '3m': 3, '5m': 5, '15m': 15 };
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const at1 = (k1: number, sec = 5) => START + k1 * 60 + sec;
const evt = (quotes: Record<string, GgStreamQuote>, variant: string = GGW_TAB): GgQuotesEvent => ({ kind: 'quotes', variant, quotes });
const q = (price: number, asOf: number, size = 100): GgStreamQuote => ({ price, as_of_epoch: asOf, vs: null, size });

function liveRaw(mut?: (raw: any) => void): any {
  const raw = clone(fixture) as any;
  for (const r of raw.rows) {
    for (const f of r.frames || []) Object.assign(f.axis, { start_epoch: START, frame_min: FM[f.tf], from_et: '04:00' });
  }
  mut?.(raw);
  return raw;
}
const board = (mut?: (raw: any) => void) => parseGgw(liveRaw(mut)) as GgwBoard;
const nvdaOf = (b: GgwBoard) => b.rows.find((r) => r.symbol === 'NVDA')!;
const row = (over: Partial<GgwRow> = {}): GgwRow => ({
  symbol: 'GP', state: 'ok', text: null, from_session: null, as_of_et: null, stale: false, frames: [], rang: [], ...over,
});

/* The card view's own answer + card (as lib/gajjalaCardView.test builds them). */
function cardAnswer(over: Record<string, unknown> = {}): any {
  const frames = clone((fixture as any).rows[0].frames) as any[];
  for (const x of frames) {
    if (x.tf === '3m') x.tf = '15m';
    Object.assign(x, { as_of_et: '09:41', stale: false, empty_text: null });
    Object.assign(x.axis, { start_epoch: START, frame_min: FM[x.tf], from_et: '04:00' });
  }
  return {
    state: 'ok', symbol: 'OMH', session: '2026-11-13', is_today: true, in_window: true, as_of_et: '09:41', stale: false,
    text: null, frames, ...over,
  };
}
const card = (): GgTile => ({
  symbol: 'OMH', href: '/sepa/OMH?tab=supply&tf=5m_today', bars: [], stats: [], why: '',
  lines: [], bands: [], markers: [], tf: '5m', gajjala: { plan_text: 'served plan' } as any,
} as unknown as GgTile);

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');

describe('👀 ggwRowLive — a stale Watch row keeps its live tail (WP-1)', () => {
  it('a hand-built {stale: true, stale_keeps_live: true} row → true; a fresh row → true (unchanged)', () => {
    expect(ggwRowLive(row({ stale: true, stale_keeps_live: true }))).toBe(true);
    expect(ggwRowLive(row())).toBe(true);
    expect(ggwRowLive(row({ stale_keeps_live: true }))).toBe(true);
  });
  it('a parsed stale Watch row (fixture NVDA, ⚠️ served sentence) → true', () => {
    const nv = nvdaOf(parseGgw(clone(fixture)) as GgwBoard);
    expect(nv.stale).toBe(true);
    expect(nv.text!.startsWith('⚠️')).toBe(true);
    expect(nv.stale_keeps_live).toBe(true);
    expect(ggwRowLive(nv)).toBe(true);
  });
  it('parseRow sets the flag on EVERY parsed row (unconditional), stale or not', () => {
    for (const r of (parseGgw(clone(fixture)) as GgwBoard).rows) expect(r.stale_keeps_live, r.symbol).toBe(true);
  });
  it('NEGATIVE: {stale: true} without the flag (the card view) → false', () => {
    expect(ggwRowLive(row({ stale: true }))).toBe(false);
    expect(ggwRowLive(row({ stale: true, stale_keeps_live: false }))).toBe(false);
    expect(ggwRowLive(row({ stale: true, stale_keeps_live: undefined }))).toBe(false);
  });
  it('NEGATIVE: the flag with from_session set → false (stale or not)', () => {
    expect(ggwRowLive(row({ stale: true, stale_keeps_live: true, from_session: '2026-11-20' }))).toBe(false);
    expect(ggwRowLive(row({ stale_keeps_live: true, from_session: '2026-11-20' }))).toBe(false);
    const nv = nvdaOf(board((r) => { r.rows[3].from_session = '2026-11-12'; }));
    expect(nv.stale_keeps_live).toBe(true);
    expect(ggwRowLive(nv)).toBe(false);
  });
  it('NEGATIVE: pending / failed / no_prints / no_bars / over_budget with the flag → false', () => {
    for (const state of ['pending', 'failed', 'no_prints', 'no_bars', 'over_budget', 'OK', '']) {
      expect(ggwRowLive(row({ state, stale: true, stale_keeps_live: true })), state).toBe(false);
      expect(ggwRowLive(row({ state, stale_keeps_live: true })), state).toBe(false);
    }
  });
  it('NEGATIVE: a junk flag value (\'yes\' / 1 / \'true\') → false on a stale row', () => {
    for (const junk of ['yes', 1, 'true', {}, null]) {
      expect(ggwRowLive(row({ stale: true, stale_keeps_live: junk as any })), String(junk)).toBe(false);
    }
  });
});

describe('👀 the card view never carries the flag (NEGATIVE)', () => {
  it('ggcRow(…) on a stale and a fresh answer → no stale_keeps_live key; the stale card row is dark', () => {
    const stale = ggcRow(card(), parseGgc(cardAnswer({ stale: true })) as GgcPayload);
    const fresh = ggcRow(card(), parseGgc(cardAnswer()) as GgcPayload);
    for (const r of [stale, fresh]) {
      expect('stale_keeps_live' in r).toBe(false);
      expect(r.stale_keeps_live).toBeUndefined();
    }
    expect(stale.stale).toBe(true);
    expect(ggwRowLive(stale)).toBe(false);
    expect(ggwFrameMetas([stale])).toEqual({});
    expect(ggwRowLive(fresh)).toBe(true);
    expect(Object.keys(ggwFrameMetas([fresh]))).toEqual(['OMH']);
  });
  it('GGC_NO_FRAMES carries no stale_keeps_live', () => {
    expect('stale_keeps_live' in GGC_NO_FRAMES).toBe(false);
    expect(Object.keys(GGC_NO_FRAMES).sort()).toEqual(['as_of_et', 'frames', 'from_session', 'rang', 'stale']);
  });
  it('source: gajjalaCardView.ts never names stale_keeps_live; in gajjalaWatch.ts parseRow is the only setter', async () => {
    expect(await readSource('src/lib/gajjalaCardView.ts')).not.toContain('stale_keeps_live');
    const src = noComments(await readSource('src/lib/gajjalaWatch.ts'));
    expect(src.match(/stale_keeps_live\s*:\s*true/g)).toHaveLength(1);
    const parseRow = src.slice(src.indexOf('function parseRow('), src.indexOf('export function ggwRowLive('));
    expect(parseRow).toMatch(/stale_keeps_live:\s*true,/);
    expect(noComments(await readSource('src/lib/ggwLive.ts'))).not.toContain('stale_keeps_live');
  });
  it('source: ggwRowLive keeps from_session == null and reads the flag as === true (the ONE rule)', async () => {
    const src = noComments(await readSource('src/lib/gajjalaWatch.ts'));
    const body = src.slice(src.indexOf('export function ggwRowLive('), src.indexOf('export function parseGgw('));
    expect(body).toContain('row.from_session == null');
    expect(body).toContain('row.stale_keeps_live === true');
    expect(body).toContain("row.state === 'ok'");
  });
  it('NEGATIVE: the per-frame `stale` rule is unchanged — a frame served stale on a flagged row carries no meta', () => {
    const b = board((r) => { r.rows[3].frames[0].stale = true; });
    const ms = ggwFrameMetas(b.rows);
    expect(ms.NVDA.map((m) => m.tf)).toEqual(['3m', '5m']);
    const all = board((r) => { for (const f of r.rows[3].frames) f.stale = true; });
    expect(ggwFrameMetas(all.rows).NVDA).toBeUndefined();
  });
});

describe('👀 the reducer on a stale Watch row', () => {
  const metas = (b: GgwBoard = board()) => ggwFrameMetas(b.rows);
  it('metas include the stale NVDA (all three frames); a batch for it opens a forming bar', () => {
    const ms = metas();
    expect(ms.NVDA.map((m) => m.tf)).toEqual(['1m', '3m', '5m']);
    expect(ms.NVDA.find((m) => m.tf === '1m')!.last_bucket).toBe(387);
    const m = ggwApplyBatch({}, evt({ NVDA: q(170.5, at1(388), 500) }), ms);
    expect(m.NVDA.by['1m']).toEqual([{ bucket: 388, o: 170.5, h: 170.5, l: 170.5, c: 170.5, v: 500, as_of: at1(388) }]);
  });
  it('consecutive minutes add one live bar each', () => {
    const ms = metas();
    let m: GgwLiveMap = ggwApplyBatch({}, evt({ NVDA: q(170.5, at1(388)) }), ms);
    m = ggwApplyBatch(m, evt({ NVDA: q(170.6, at1(389)) }), ms);
    m = ggwApplyBatch(m, evt({ NVDA: q(170.7, at1(390)) }), ms);
    expect(m.NVDA.by['1m'].map((x) => x.bucket)).toEqual([388, 389, 390]);
  });
  it('the next GET that stores the bucket prunes it (server wins); the row stays stale and live', () => {
    const ms = metas();
    let m: GgwLiveMap = ggwApplyBatch({}, evt({ NVDA: q(170.5, at1(388)) }), ms);
    m = ggwApplyBatch(m, evt({ NVDA: q(170.6, at1(389)) }), ms);
    const next = board((r) => {
      const f = r.rows[3].frames[0];
      f.tile.bars.push({ t: '2026-11-13 10:29', o: 170.4, h: 170.6, l: 170.3, c: 170.5, v: 900 });
      f.axis.x.push(388);
      for (const c of f.tile.curves) c.values.push(c.values.at(-1));
    });
    expect(nvdaOf(next).stale).toBe(true);
    const m2 = ggwApplyBatch(m, evt({ NVDA: q(170.65, at1(389, 30)) }), metas(next));
    expect(m2.NVDA.by['1m'].map((x) => x.bucket)).toEqual([389]);
  });
  it('NEGATIVE: the same stale NVDA without the flag → no metas, a batch returns the SAME map', () => {
    const rows = board().rows.map((r) => (r.symbol === 'NVDA' ? { ...r, stale_keeps_live: undefined } : r));
    const ms = ggwFrameMetas(rows);
    expect(ms.NVDA).toBeUndefined();
    const prev: GgwLiveMap = {};
    expect(ggwApplyBatch(prev, evt({ NVDA: q(170.5, at1(388)) }), ms)).toBe(prev);
  });
  it('NEGATIVE: no batch (the feed blind) → nothing is folded; a fresh GET alone opens no live bar', () => {
    const prev: GgwLiveMap = {};
    const m = ggwApplyBatch(prev, evt({ OMH: q(4.01, at1(390)) }), metas());
    expect(m.NVDA).toBeUndefined();
  });
});
