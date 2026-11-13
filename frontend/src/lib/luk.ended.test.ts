import { describe, expect, it } from 'vitest';
import {
  lukEndedLine, lukFoldKey, lukLiveEnd, lukNewLiveEnds, lukSplitLive, type LukEnded, type LukLatch, type LukTile,
} from './luk';
import type { CardLiveAnswer, CardLiveQuote } from './cardLive';

/* 🏁 2026-11-12 — ended cards fold, the pure FE half (lukend spec §3.5 / WP-B test 1). Ajay, verbatim: "Is this still
 * good ro enter? From Luks" → "I shouldn't be seeing this" → "I want it to be realtime".
 * Every word below is a stand-in for a SERVED string (tab.LIVE_FOLD_TEXT / live_card.VS_TEXT / tab.ENDED_HEAD_TEXT); the
 * helpers only compare served values and copy served words. NEGATIVES: a wrong kind / session / until never latches; a
 * missing or blank rule never latches; an invalid vs never latches; nothing new → null; a 0 / blank line → null. */

const UNTIL = 1794517200;
const FOLD = { kind: 'k-under', session: 'rth', until_epoch: UNTIL, text: 'served fold sentence 11.98' };
const tile = (o: Partial<LukTile> = {}): LukTile => ({
  symbol: 'mstr', setup: 'pullback_reversal', state: 'triggered', state_label: 'served label', stop: 112.32,
  trade_text: 'served window words', live_fold: { ...FOLD }, ...o,
});
const quote = (vs: unknown): CardLiveQuote => ({ bar: null, prev_t: null, now: null, vs: vs as CardLiveQuote['vs'] });
const VS = { kind: 'k-under', text: 'served vs words' };
const ans = (quotes: Record<string, CardLiveQuote>, o: Partial<CardLiveAnswer> = {}): CardLiveAnswer => ({
  session: 'rth', as_of_epoch: UNTIL - 600, as_of: '10:12:00 ET', footer: { live: null, stale: null }, now_labels: [],
  cap: 250, asked: 1, served: 1, missing: [], fault: null, quotes, ...o,
});

describe('lukFoldKey', () => {
  it('symbol (upper-cased) | setup | served stop', () => {
    expect(lukFoldKey(tile())).toBe('MSTR|pullback_reversal|112.32');
  });
  it('NEGATIVE: a different stop or setup is a different key', () => {
    expect(lukFoldKey(tile({ stop: 112.3 }))).not.toBe(lukFoldKey(tile()));
    expect(lukFoldKey(tile({ setup: 'opening_range_high' }))).not.toBe(lukFoldKey(tile()));
  });
});

describe('lukLiveEnd', () => {
  const a = { session: 'rth', as_of_epoch: UNTIL - 600 };
  it('latches when the served vs.kind equals live_fold.kind, the session matches and as_of < until', () => {
    expect(lukLiveEnd(tile(), quote(VS), a)).toEqual({ text: FOLD.text, vs: VS.text });
  });
  it('NEGATIVE: a kind mismatch never latches', () => {
    for (const kind of ['k-between', 'k-over', '', 'K-UNDER']) {
      expect(lukLiveEnd(tile(), quote({ kind, text: 'w' }), a)).toBeNull();
    }
  });
  it("NEGATIVE: session 'afterhours' / 'premarket' / 'closed' / null never latches", () => {
    for (const session of ['afterhours', 'premarket', 'closed', null]) {
      expect(lukLiveEnd(tile(), quote(VS), { session, as_of_epoch: UNTIL - 600 })).toBeNull();
    }
  });
  it('NEGATIVE: as_of_epoch ≥ until_epoch never latches (equal included); a non-finite as_of never', () => {
    for (const as_of_epoch of [UNTIL, UNTIL + 1, NaN, Infinity]) {
      expect(lukLiveEnd(tile(), quote(VS), { session: 'rth', as_of_epoch })).toBeNull();
    }
    expect(lukLiveEnd(tile(), quote(VS), { session: 'rth', as_of_epoch: UNTIL - 1 })).not.toBeNull();
  });
  it('NEGATIVE: no / null / blank / partial live_fold never latches', () => {
    const bad: unknown[] = [undefined, null, 'x', [], {}, { ...FOLD, kind: ' ' }, { ...FOLD, session: '' },
      { ...FOLD, text: '   ' }, { ...FOLD, until_epoch: NaN }, { ...FOLD, until_epoch: '1794517200' }, { ...FOLD, until_epoch: null }];
    for (const lf of bad) expect(lukLiveEnd(tile({ live_fold: lf as LukTile['live_fold'] }), quote(VS), a)).toBeNull();
  });
  it('NEGATIVE: an invalid / absent vs never latches', () => {
    for (const vs of [undefined, null, 'k-under', { kind: 'k-under' }, { kind: 'k-under', text: '  ' }, { text: 'w' }]) {
      expect(lukLiveEnd(tile(), quote(vs), a)).toBeNull();
    }
    expect(lukLiveEnd(tile(), undefined, a)).toBeNull();
    expect(lukLiveEnd(tile(), quote(VS), null)).toBeNull();
  });
  it('NEGATIVE: a card the server already ended never latches', () => {
    expect(lukLiveEnd(tile({ ended: true }), quote(VS), a)).toBeNull();
  });
});

describe('lukNewLiveEnds', () => {
  it('latches only the matching card, keyed by lukFoldKey', () => {
    const t1 = tile();
    const t2 = tile({ symbol: 'ABC', stop: 5 });
    const out = lukNewLiveEnds([t1, t2], ans({ MSTR: quote(VS), ABC: quote({ kind: 'k-between', text: 'b' }) }), {});
    expect(out).toEqual({ 'MSTR|pullback_reversal|112.32': { text: FOLD.text, vs: VS.text } });
  });
  it('NEGATIVE: null when nothing new (already latched / no match / no answer)', () => {
    const t1 = tile();
    const latched: Record<string, LukLatch> = { [lukFoldKey(t1)]: { text: 'x', vs: null } };
    expect(lukNewLiveEnds([t1], ans({ MSTR: quote(VS) }), latched)).toBeNull();
    expect(lukNewLiveEnds([t1], ans({ MSTR: quote({ kind: 'k-between', text: 'b' }) }), {})).toBeNull();
    expect(lukNewLiveEnds([t1], null, {})).toBeNull();
    expect(lukNewLiveEnds([t1], ans({}), {})).toBeNull();
  });
  it('NEGATIVE: the answer session / as_of are the rule — a premarket answer or one at until never latches', () => {
    expect(lukNewLiveEnds([tile()], ans({ MSTR: quote(VS) }, { session: 'premarket' }), {})).toBeNull();
    expect(lukNewLiveEnds([tile()], ans({ MSTR: quote(VS) }, { as_of_epoch: UNTIL }), {})).toBeNull();
  });
});

describe('lukSplitLive', () => {
  it('a latched card leaves the live list with the served text, trade_text and live_fold null; order kept', () => {
    const a = tile({ symbol: 'AAA', stop: 1 });
    const m = tile();
    const z = tile({ symbol: 'ZZZ', stop: 2 });
    const { live, ended } = lukSplitLive([a, m, z], { [lukFoldKey(m)]: { text: 'served fold', vs: 'served vs' } });
    expect(live.map((t) => t.symbol)).toEqual(['AAA', 'ZZZ']);
    expect(ended).toHaveLength(1);
    expect(ended[0]).toMatchObject({ symbol: 'mstr', ended: true, ended_text: 'served fold', ended_vs_text: 'served vs',
      trade_text: null, live_fold: null });
    expect(m.ended).toBeUndefined();
  });
  it('NEGATIVE: the key carries the stop — the same symbol + setup at a new stop stays live', () => {
    const m = tile();
    const { live, ended } = lukSplitLive([tile({ stop: 110 })], { [lukFoldKey(m)]: { text: 'f', vs: null } });
    expect(live).toHaveLength(1);
    expect(ended).toHaveLength(0);
  });
  it('NEGATIVE: nothing latched → every card live', () => {
    const ts = [tile(), tile({ symbol: 'B' })];
    expect(lukSplitLive(ts, {})).toEqual({ live: ts, ended: [] });
  });
});

describe('lukEndedLine', () => {
  const E = (o: Partial<LukEnded> = {}): LukEnded => ({ n: 2, emoji: '🏁', head_text: 'served head words', ...o });
  it('served emoji, n + extra, served head', () => {
    expect(lukEndedLine(E(), 0)).toBe('🏁 2 served head words');
    expect(lukEndedLine(E(), 3)).toBe('🏁 5 served head words');
    expect(lukEndedLine(E({ n: 0 }), 1)).toBe('🏁 1 served head words');
  });
  it('NEGATIVE: 0 in all → null; a blank head → null; no block → null', () => {
    expect(lukEndedLine(E({ n: 0 }), 0)).toBeNull();
    expect(lukEndedLine(E({ head_text: '  ' }), 2)).toBeNull();
    expect(lukEndedLine(E({ head_text: null }), 2)).toBeNull();
    expect(lukEndedLine(null, 3)).toBeNull();
    expect(lukEndedLine(undefined, 0)).toBeNull();
  });
  it('NEGATIVE: a NaN / negative / non-number n counts as 0', () => {
    expect(lukEndedLine(E({ n: NaN }), 0)).toBeNull();
    expect(lukEndedLine(E({ n: NaN }), 1)).toBe('🏁 1 served head words');
    expect(lukEndedLine(E({ n: -4 }), 1)).toBe('🏁 1 served head words');
    expect(lukEndedLine(E({ n: '3' as unknown as number }), 0)).toBeNull();
  });
});

describe('luk.ts source — no fold word typed', () => {
  it('NEGATIVE: none of the served fold words and no live-kind literal in code', async () => {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    const src: string = fs.readFileSync(`${root}/src/lib/luk.ts`, 'utf8');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    for (const w of ['ended today', 'entry window', 'not an entry', 'open trade', "Luk's exit", 'traded at or under',
      'official close', 'under_stop', "'rth'"]) expect(code).not.toContain(w);
  });
});
