/* 👀 Gajjala's Watch — the FE plumbing (2026-11-15, gajjala-watch spec §3.7 / §3.8, WP-C). Ajay: "I need dashboard to add
 * tickers to Gajjalas watch dashboard. I wanna be able to remove and add remove tickers from the dashboard." The routes,
 * the parser (junk never reaches the board; owner_only keeps exactly three keys), the replay palette, the chart heights,
 * the pending-row helpers. NEGATIVES throughout. */
import { describe, expect, it } from 'vitest';
import fixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import autoFixture from '../components/__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import { CM_TABS, EMA_BOLD, TAB_META, isBoardTab, nearestAxisBar, parseTab } from './chartMaps';
import { BURST_EXEMPT } from './momentumBurst';
import {
  GGW_CHART_H, GGW_CHART_H_PHONE, GGW_LIVE_EMA_TIP, GGW_LIVE_PATH, GGW_PANEL, GGW_PATH, GGW_PHONE_MQ, GGW_TAB,
  ggwChartHeight, ggwMergeRows, ggwPendingSymbols, ggwRowLive, ggwRowsPath, ggwSplitFrames, ggwSymbolPath, parseGgw,
  type GgwBoard, type GgwRow,
} from './gajjalaWatch';

const ok = () => parseGgw(JSON.parse(JSON.stringify(fixture))) as GgwBoard;

describe('👀 routes', () => {
  it('the board and the add / remove routes', () => {
    expect(GGW_TAB).toBe('gajjala_watch');
    expect(GGW_PATH).toBe('/chart-maps/gajjala-watch');
    expect(ggwSymbolPath('OMH')).toBe('/chart-maps/gajjala-watch/symbols/OMH');
    expect(ggwRowsPath(['AMD', 'OMH'])).toBe('/chart-maps/gajjala-watch?symbols=AMD%2COMH');
  });
  it('NEGATIVE: the symbol is never re-cased by the FE (the server normalizes) and is URL-encoded', () => {
    expect(ggwSymbolPath(' omh ')).toBe('/chart-maps/gajjala-watch/symbols/omh');
    expect(ggwSymbolPath('A/B')).toBe('/chart-maps/gajjala-watch/symbols/A%2FB');
  });
});

describe('👀 parseGgw', () => {
  it('the fixture parses: 4 rows in served order, frames 1m / 3m / 5m with a served axis', () => {
    const b = ok();
    expect(b.state).toBe('ok');
    expect(b.rows.map((r) => r.symbol)).toEqual(['OMH', 'AMD', 'XYZQ', 'NVDA']);
    expect(b.rows[0].frames.map((f) => f.tf)).toEqual(['1m', '3m', '5m']);
    const ax = b.rows[0].frames[0].axis!;
    expect(ax.slots).toBe(720);
    expect(ax.x[0]).toBe(0);
    expect(ax.x.length).toBe(b.rows[0].frames[0].tile.bars.length);
    expect(b.rows[0].frames[0].held?.text).toMatch(/held/);
    expect(b.rows[3].stale).toBe(true);
    expect(b.info?.uptrend_rule).toMatch(/^K5 uptrend/);
  });
  it('NEGATIVE: junk → null', () => {
    for (const junk of [null, undefined, 3, 'x', [], {}, { state: 'ok' }, { state: 'ok', rows: 'x' }, { state: 'nope', rows: [] }]) {
      expect(parseGgw(junk)).toBeNull();
    }
  });
  it('owner_only keeps exactly {state, reason, title} — NEGATIVE: no rows, no head keys survive', () => {
    const p = parseGgw({ state: 'owner_only', reason: 'Shown to the account owner only.', title: 'T', rows: [{ symbol: 'X' }], symbols: ['X'] });
    expect(p).toEqual({ state: 'owner_only', reason: 'Shown to the account owner only.', title: 'T' });
    expect(Object.keys(p!).sort()).toEqual(['reason', 'state', 'title']);
  });
  it('NEGATIVE: a row without a symbol, a frame without a tile and a bad axis are dropped, never drawn half', () => {
    const raw = JSON.parse(JSON.stringify(fixture));
    raw.rows.push({ state: 'ok' });
    raw.rows[0].frames[1].tile = null;
    raw.rows[0].frames[2].axis = { slots: 0, x: [] };
    const b = parseGgw(raw) as GgwBoard;
    expect(b.rows).toHaveLength(4);
    expect(b.rows[0].frames.map((f) => f.tf)).toEqual(['1m', '5m']);
    expect(b.rows[0].frames[1].axis).toBeNull();
  });
  it('NEGATIVE: a negative / missing refresh_sec reads 0 (no chain)', () => {
    const raw = JSON.parse(JSON.stringify(fixture));
    raw.refresh_sec = -5;
    expect((parseGgw(raw) as GgwBoard).refresh_sec).toBe(0);
    delete raw.refresh_sec;
    expect((parseGgw(raw) as GgwBoard).refresh_sec).toBe(0);
  });
});

describe('👀 pending rows, merge, frame split', () => {
  it('pending symbols are the served pending rows only', () => {
    expect(ggwPendingSymbols(ok())).toEqual(['AMD']);
  });
  it('a partial answer replaces its rows in place — NEGATIVE: the board order and head never change', () => {
    const b = ok();
    const part = ok();
    part.title = 'other';
    part.rows = [{ ...part.rows[1], state: 'ok', text: null }];
    const m = ggwMergeRows(b, part);
    expect(m.rows.map((r) => r.symbol)).toEqual(['OMH', 'AMD', 'XYZQ', 'NVDA']);
    expect(m.rows[1].state).toBe('ok');
    expect(m.title).toBe(b.title);
  });
  it('the 1-min frame on top, the rest in served order', () => {
    const { top, pair } = ggwSplitFrames(ok().rows[0].frames);
    expect(top?.tf).toBe('1m');
    expect(pair.map((f) => f.tf)).toEqual(['3m', '5m']);
    expect(ggwSplitFrames([]).top).toBeNull();
  });
});

describe('👀 look (HIS CALL #10)', () => {
  // 2026-11-23 (vwapzones §3.9 — Ajay: "Can you remove 3 mins just add 15 mins instead"): the 15-min chart takes the 3-min height.
  it('chart heights: 1-min 120, 5-/15-min 180 (viewBox units); phone 190', () => {
    expect(GGW_CHART_H).toEqual({ '1m': 120, '5m': 180, '15m': 180 });
    expect(GGW_CHART_H_PHONE).toBe(190);
    expect(ggwChartHeight('1m', false)).toBe(120);
    expect(ggwChartHeight('5m', false)).toBe(180);
    expect(ggwChartHeight('1m', true)).toBe(190);
    expect(GGW_PHONE_MQ).toBe('(max-width: 640px)');
  });
  // The 3×3-fits-one-screen pin moved to GajjalaWatchBoard.fixes.test.tsx (ggwFitRowHeight, measured 357 px above + 56 below).
  it('the replay palette (replay_gif.py:576-581) and the bold 9 / 21 (replay_gif.py:579)', () => {
    expect(GGW_PANEL.bg).toBe('rgb(13, 17, 23)');
    expect(GGW_PANEL.grid).toBe('rgb(38, 43, 52)');
    expect(GGW_PANEL.up).toBe('rgb(38, 186, 104)');
    expect(GGW_PANEL.down).toBe('rgb(235, 72, 72)');
    // WIDENED 2026-11-15 (Ajay: "make the lines a little more thick"): 2 → 3 px.
    // WIDENED 2026-11-16 (Ajay: "the lines are too thick may be reduce thick ness"): 3 → 2 px.
    expect(EMA_BOLD).toEqual({ ema9: { color: '#FACC15', width: 2 }, ema21: { color: '#BE78FF', width: 2 } });
  });
  it('nearestAxisBar snaps a slot to the nearest printed bar — NEGATIVE: no bars → -1', () => {
    expect(nearestAxisBar(5, [0, 3, 10])).toBe(1);
    expect(nearestAxisBar(700, [0, 3, 10])).toBe(2);
    expect(nearestAxisBar(5, [])).toBe(-1);
  });
});

describe('👀 tab registry', () => {
  it('sits once, right after gajjala_1m and right before luk; not a tile board; exempt from ⚡ with his reason', () => {
    expect(CM_TABS.filter((t) => t === 'gajjala_watch')).toHaveLength(1);
    expect(CM_TABS.indexOf('gajjala_watch')).toBe(CM_TABS.indexOf('gajjala_1m') + 1);
    // RE-PINNED 2026-11-18 — 🎬 replays between 👀 gajjala_watch and 🥇 luk (Ajay: "Can you put replays tab next to the Gajjala's please")
    expect(CM_TABS.indexOf('replays')).toBe(CM_TABS.indexOf('gajjala_watch') + 1);
    expect(CM_TABS.indexOf('luk')).toBe(CM_TABS.indexOf('replays') + 1);
    expect(parseTab('gajjala_watch')).toBe('gajjala_watch');
    expect(isBoardTab('gajjala_watch')).toBe(false);
    expect(BURST_EXEMPT.gajjala_watch).toBe('your own tickers in your order — never ranked');
  });
  it('NEGATIVE: the endpoint spelling is not a tab id', () => {
    expect(parseTab('gajjala-watch')).not.toBe('gajjala_watch');
    expect(parseTab('watch')).not.toBe('gajjala_watch');
  });
  it('TAB_META: label (== backend TAB_LABEL) and his ask verbatim + owner-only + UNMEASURED', () => {
    expect(TAB_META.gajjala_watch.label).toBe("\u{1F440} Gajjala's Watch");
    const b = TAB_META.gajjala_watch.blurb;
    expect(b).toContain('I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and add remove tickers from the dashboard.');
    expect(b).toContain('I think the cross over is slow but once it picks up its very rapid..');
    expect(b).toContain('Shown to the account owner only. UNMEASURED — a cross is information, not an entry. Not advice.');
    expect(b).not.toMatch(/\bbuy\b/i);
    expect(b).not.toMatch(new RegExp('b' + 'ounce', 'i'));
  });
});

/* ── 👀 Watch LIVE (2026-11-16, watch-live spec §3.4 / §4 WP-C). Ajay: "Can you make the watch list charts live please" ·
 * "Of each chart". The live route, the axis' live keys (an older payload parses EXACTLY as before — the axis is never
 * dropped for a missing key), the served EMA tail, HIS CALL #1 OFF, and the ONE live-row rule (C2). NEGATIVES. */
async function fsMod(): Promise<any> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  return mod?.default || mod;
}
const root = (globalThis as any).process?.cwd?.() || '.';

const LIVE_AXIS = { start_epoch: 1794819600.0, frame_min: 1, from_et: '04:00' };
const withLiveAxis = (over: Record<string, unknown> = {}) => {
  const raw = JSON.parse(JSON.stringify(fixture));
  Object.assign(raw.rows[0].frames[0].axis, LIVE_AXIS, over);
  return raw;
};

describe('👀 LIVE — route and HIS CALL #1', () => {
  it('GGW_LIVE_PATH is the board route + /live', () => {
    expect(GGW_LIVE_PATH).toBe(GGW_PATH + '/live');
    expect(GGW_LIVE_PATH).toBe('/chart-maps/gajjala-watch/live');
  });
  it('GGW_LIVE_EMA_TIP is ON (his 11-16 "live live"), with the HIS CALL #1 comment on its line', async () => {
    expect(GGW_LIVE_EMA_TIP).toBe(true);
    const src: string = (await fsMod()).readFileSync(`${root}/src/lib/gajjalaWatch.ts`, 'utf8');
    const line = src.split('\n').find((l) => l.includes('export const GGW_LIVE_EMA_TIP'));
    expect(line).toMatch(/GGW_LIVE_EMA_TIP = true;\s*\/\/ HIS CALL #1/);
  });
});

describe('👀 LIVE — parseAxis keeps start_epoch / frame_min / from_et', () => {
  it('served keys are kept', () => {
    const ax = (parseGgw(withLiveAxis()) as GgwBoard).rows[0].frames[0].axis!;
    expect(ax.start_epoch).toBe(1794819600);
    expect(ax.frame_min).toBe(1);
    expect(ax.from_et).toBe('04:00');
    const ax5 = (parseGgw(withLiveAxis({ frame_min: 5 })) as GgwBoard).rows[0].frames[0].axis!;
    expect(ax5.frame_min).toBe(5);
  });
  it('NEGATIVE: junk → null for that key only, the axis itself is kept', () => {
    const cases: [string, unknown][] = [
      ['start_epoch', 'x'], ['start_epoch', -1], ['start_epoch', 0], ['start_epoch', NaN], ['start_epoch', null],
      ['frame_min', 'x'], ['frame_min', -1], ['frame_min', 0], ['frame_min', 1.5], ['frame_min', '1'],
      ['from_et', '4:00'], ['from_et', 'x'], ['from_et', 400], ['from_et', '04:00 ET'],
    ];
    for (const [k, v] of cases) {
      const ax = (parseGgw(withLiveAxis({ [k]: v })) as GgwBoard).rows[0].frames[0].axis;
      expect(ax, `${k}=${String(v)}`).not.toBeNull();
      expect((ax as any)[k], `${k}=${String(v)}`).toBeNull();
      expect(ax!.slots).toBe(720);
    }
  });
  it('NEGATIVE: the 2026-11-15 fixture (no start_epoch / frame_min) parses with nulls and the SAME slots / x / shade / ticks', () => {
    const b = ok();
    for (const [ri, row] of b.rows.entries()) {
      for (const [fi, f] of row.frames.entries()) {
        const raw = (fixture as any).rows[ri].frames[fi].axis;
        const ax = f.axis!;
        expect(ax).not.toBeNull();
        expect(ax.start_epoch).toBeNull();
        expect(ax.frame_min).toBeNull();
        expect(ax.from_et).toBe(raw.from_et);                    // build.axis already served from_et on 11-15
        expect(ax.from_et).toBe('04:00');
        expect(ax.slots).toBe(raw.slots);
        expect(ax.x).toEqual(raw.x);
        expect(ax.shade).toEqual(raw.shade);
        expect(ax.ticks).toEqual(raw.ticks);
        expect(Object.keys(ax).sort()).toEqual(['frame_min', 'from_et', 'shade', 'slots', 'start_epoch', 'ticks', 'x']);
      }
    }
  });
});

describe('👀 LIVE — ema_tail (the served unrounded 9 / 21 at the last stored bar)', () => {
  const withTail = (t: unknown) => {
    const raw = JSON.parse(JSON.stringify(fixture));
    raw.rows[0].frames[0].ema_tail = t;
    return (parseGgw(raw) as GgwBoard).rows[0].frames[0];
  };
  it('finite numbers are kept verbatim', () => {
    expect(withTail({ ema9: 1.4835731234567, ema21: 1.4988891234567 }).ema_tail).toEqual({ ema9: 1.4835731234567, ema21: 1.4988891234567 });
  });
  it('NEGATIVE: absent / junk → null', () => {
    expect(ok().rows[0].frames[0].ema_tail).toBeNull();
    for (const junk of [null, 'x', 3, [], {}, { ema9: 1 }, { ema9: 'x', ema21: 2 }, { ema9: NaN, ema21: 2 }, { ema9: 1, ema21: Infinity }]) {
      expect(withTail(junk).ema_tail, JSON.stringify(junk)).toBeNull();
    }
  });
});

describe('👀 LIVE — ggwRowLive, the ONE rule (C2)', () => {
  const row = (over: Partial<GgwRow> = {}): GgwRow => ({
    symbol: 'GP', state: 'ok', text: null, from_session: null, as_of_et: null, stale: false, frames: [], rang: [], ...over,
  });
  it('true only for an ok, today\'s, not-stale row', () => {
    expect(ggwRowLive(row())).toBe(true);
    expect(ggwRowLive(ok().rows[0])).toBe(true);           // OMH in the fixture
  });
  it('NEGATIVE: stale / prior session / not ok → false', () => {
    expect(ggwRowLive(row({ stale: true }))).toBe(false);
    expect(ggwRowLive(row({ from_session: '2026-11-13' }))).toBe(false);
    for (const state of ['pending', 'failed', 'no_prints', 'no_bars', 'over_budget', 'OK', '']) {
      expect(ggwRowLive(row({ state })), state).toBe(false);
    }
    expect(ggwRowLive(ok().rows[3])).toBe(false);          // NVDA is stale in the fixture
    expect(ggwRowLive(ok().rows[1])).toBe(false);          // AMD is pending
  });
});

/* 🎯 2026-11-17 (spec ggwaplus2 §3.4) — Ajay: "Push new Apluses immediately in to watch list". Two new served fields: the
 * row's `auto.why` and the board's `auto.skipped_text`. Junk → null; an older payload → absent / null. */
describe('🎯 parseGgw — A+ seats (why / skipped_text)', () => {
  const base = () => {
    const b = JSON.parse(JSON.stringify(autoFixture));
    return b;
  };
  it('round-trips why and skipped_text', () => {
    const raw = base();
    raw.rows[12].auto.why = 'aplus';
    raw.rows[13].auto.why = 'potential';
    raw.auto.skipped_text = '🎯 A+ not seated — every seat holds an A+ or your own name: AZI';
    const b = parseGgw(raw) as GgwBoard;
    expect(b.rows[12].auto?.why).toBe('aplus');
    expect(b.rows[13].auto?.why).toBe('potential');
    expect(b.auto?.skipped_text).toBe(raw.auto.skipped_text);
  });
  it('NEGATIVE: junk why / skipped_text → null; absent → why absent, skipped_text null', () => {
    for (const junk of [null, '', ' ', 3, [], {}]) {
      const raw = base();
      raw.rows[12].auto.why = junk;
      raw.auto.skipped_text = junk;
      const b = parseGgw(raw) as GgwBoard;
      expect(b.rows[12].auto?.why).toBeNull();
      expect(b.auto?.skipped_text).toBeNull();
    }
    const b = parseGgw(base()) as GgwBoard;
    expect(b.rows[12].auto && 'why' in b.rows[12].auto).toBe(false);
    expect(b.auto?.skipped_text).toBeNull();
  });
});

