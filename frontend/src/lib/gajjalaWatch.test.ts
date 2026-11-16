/* 👀 Gajjala's Watch — the FE plumbing (2026-11-15, gajjala-watch spec §3.7 / §3.8, WP-C). Ajay: "I need dashboard to add
 * tickers to Gajjalas watch dashboard. I wanna be able to remove and add remove tickers from the dashboard." The routes,
 * the parser (junk never reaches the board; owner_only keeps exactly three keys), the replay palette, the chart heights,
 * the pending-row helpers. NEGATIVES throughout. */
import { describe, expect, it } from 'vitest';
import fixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import { CM_TABS, EMA_BOLD, TAB_META, isBoardTab, nearestAxisBar, parseTab } from './chartMaps';
import { BURST_EXEMPT } from './momentumBurst';
import {
  GGW_CHART_H, GGW_CHART_H_PHONE, GGW_PANEL, GGW_PATH, GGW_PHONE_MQ, GGW_TAB, ggwChartHeight, ggwMergeRows,
  ggwPendingSymbols, ggwRowsPath, ggwSplitFrames, ggwSymbolPath, parseGgw, type GgwBoard,
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
  it('chart heights: 1-min 120, 3-/5-min 180 (viewBox units); phone 190', () => {
    expect(GGW_CHART_H).toEqual({ '1m': 120, '3m': 180, '5m': 180 });
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
    expect(CM_TABS.indexOf('luk')).toBe(CM_TABS.indexOf('gajjala_watch') + 1);
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
