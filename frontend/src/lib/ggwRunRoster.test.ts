/* 📅 lib/ggwRunRoster — routes, parsers (2026-11-26, spec watchrun rev 2 §3.5, WP fe-roster). Ajay: "Ok then add them to
 * our watch list and track them please..". Every string verbatim, served order kept, junk → null, a row without a ticker
 * dropped, nothing formatted. NEGATIVES throughout. */
import { describe, expect, it } from 'vitest';
import gold from './__fixtures__/ggwRunRoster.golden.json';
import { GGW_PATH, ggwSymbolPath } from './gajjalaWatch';
import {
  GGW_RUNSEAT_PATH, GGW_RUNTRACK_PATH, ggwRunSeatPath, ggwRunTrackPath, parseRunnerTag, parseRunRoster,
  parseRunSeatAnswer, parseRunTable, parseRunTrack, parseRunTrackSymbol,
} from './ggwRunRoster';

const G = gold as any;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

describe('routes', () => {
  it('the two paths sit under the board route (== backend API_RUNTRACK_PATH / API_RUNSEAT_PATH minus {symbol})', () => {
    expect(GGW_RUNTRACK_PATH).toBe(`${GGW_PATH}/runners/track`);
    expect(GGW_RUNSEAT_PATH).toBe(`${GGW_PATH}/runners/seat`);
    expect(ggwRunSeatPath(' BGLC ')).toBe('/chart-maps/gajjala-watch/runners/seat/BGLC');
    expect(ggwRunSeatPath('BRK/B')).toBe('/chart-maps/gajjala-watch/runners/seat/BRK%2FB');
    expect(ggwRunTrackPath()).toBe(GGW_RUNTRACK_PATH);
    expect(ggwRunTrackPath('POM')).toBe(`${GGW_RUNTRACK_PATH}?symbol=POM`);
  });
  it('NEGATIVE: the seat path is never the tile path', () => {
    expect(ggwRunSeatPath('POM')).not.toBe(ggwSymbolPath('POM'));
    expect(ggwRunSeatPath('POM')).not.toContain('/symbols/');
  });
});

describe('parseRunRoster', () => {
  it('the golden: served order, every string verbatim, counts and fold sizes kept', () => {
    const b = parseRunRoster(G.runners)!;
    expect(b.state).toBe('ok');
    expect(b.text).toBe(G.runners.text);
    expect(b.hint).toBe(G.runners.hint);
    expect(b.folded_default).toBe(true);
    expect(b.fold_at).toBe(8);
    expect(b.rows.map((r) => r.symbol)).toEqual(G.runners.rows.map((r: any) => r.symbol));
    expect(b.rows[0]).toEqual({ ...G.runners.rows[0] });
    expect(b.not_seated.map((n) => n.text)).toEqual(G.runners.not_seated.map((n: any) => n.text));
  });
  it('NEGATIVE: a row without a ticker is dropped; junk fields → null / false', () => {
    const raw = clone(G.runners);
    raw.rows = [{ symbol: '', day_text: 'x' }, { day_text: 'x' }, 7, { symbol: 'OK', on_watch: 'yes', day_n: 'two', remove_title: 3 }];
    raw.not_seated = [{ symbol: 'A' }, { text: '' }, { text: 'kept verbatim' }];
    raw.fold_at = 0;
    raw.folded_default = 'true';
    const b = parseRunRoster(raw)!;
    expect(b.rows.map((r) => r.symbol)).toEqual(['OK']);
    expect(b.rows[0].on_watch).toBe(false);
    expect(b.rows[0].day_n).toBeNull();
    expect(b.rows[0].remove_title).toBeNull();
    expect(b.not_seated.map((n) => n.text)).toEqual(['kept verbatim']);
    expect(b.fold_at).toBeNull();
    expect(b.folded_default).toBe(false);
  });
  it('NEGATIVE: junk → null', () => {
    for (const j of [null, undefined, 1, 'ok', [], {}, { state: '' }, { state: null }]) expect(parseRunRoster(j)).toBeNull();
  });
  it('"unreadable" → the served line, no rows', () => {
    const b = parseRunRoster(G.unreadable)!;
    expect(b.state).toBe('unreadable');
    expect(b.text).toBe(G.unreadable.text);
    expect(b.rows).toEqual([]);
  });
});

describe('parseRunnerTag', () => {
  it('the golden tag verbatim', () => {
    expect(parseRunnerTag(G.row_runner)).toEqual(G.row_runner);
  });
  it('NEGATIVE: junk or no chip text at all → null', () => {
    for (const j of [null, 'x', [], {}, { seat_title: 't' }, { day_text: '', seat_text: ' ' }]) expect(parseRunnerTag(j)).toBeNull();
    expect(parseRunnerTag({ seat_text: '+75% day' })!.day_text).toBeNull();
  });
});

describe('parseRunTable / track payloads', () => {
  it('house [key, label] heads + {cells: {key: text}} rows → aligned served strings', () => {
    const t = parseRunTable(G.track_all.heads, G.track_all.rows);
    expect(t.heads).toEqual(['Name', 'Ran', 'Rule', 'Base', 'Best high after', 'Day 10 close']);
    expect(t.rows[0]).toEqual(['AIMD', '2026-11-13', 'ran after an A+', 'run-day close', '+12.0% (2026-11-17)', '−8.1%']);
  });
  it('other served shapes: array rows, {key,label} heads, string heads, `<key>_text` beside a raw number', () => {
    expect(parseRunTable(['A', 'B'], [['x', { text: 'y' }]])).toEqual({ heads: ['A', 'B'], rows: [['x', 'y']] });
    expect(parseRunTable([{ key: 'p', label: 'Pct' }], [{ p: 12.34, p_text: '+12.3%' }])).toEqual({ heads: ['Pct'], rows: [['+12.3%']] });
  });
  it('NEGATIVE: a raw number is never formatted into a cell; an all-empty row is dropped; junk → empty', () => {
    expect(parseRunTable([['p', 'Pct']], [{ p: 12.34 }])).toEqual({ heads: ['Pct'], rows: [] });
    expect(parseRunTable(null, null)).toEqual({ heads: [], rows: [] });
    expect(parseRunTable('x', 5)).toEqual({ heads: [], rows: [] });
  });
  it('parseRunTrack / parseRunTrackSymbol keep every served word; junk → null', () => {
    const a = parseRunTrack(G.track_all)!;
    expect(a.summary_text).toBe(G.track_all.summary_text);
    expect(a.note).toBe(G.track_all.note);
    expect(a.open_n).toBe(14);
    const s = parseRunTrackSymbol(G.track_symbol)!;
    expect(s.symbol).toBe('BGLC');
    expect(s.docs[0].base_note).toBe(G.track_symbol.docs[0].base_note);
    expect(s.docs[0].table.rows[1][3]).toBe('🧠 potential 10:05 · armed 10:40');
    for (const j of [null, [], {}, { state: '' }]) { expect(parseRunTrack(j)).toBeNull(); expect(parseRunTrackSymbol(j)).toBeNull(); }
    expect(parseRunTrack({ state: 'owner_only' })!.state).toBe('owner_only');
  });
  it('parseRunSeatAnswer: the served state + text; junk → null', () => {
    expect(parseRunSeatAnswer(G.seat_answers.absent)).toEqual(G.seat_answers.absent);
    expect(parseRunSeatAnswer({ text: 'x' })).toBeNull();
  });
});
