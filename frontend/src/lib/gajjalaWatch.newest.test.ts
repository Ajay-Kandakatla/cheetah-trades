/* 🆕 Gajjala's Watch — new names ACTIVE, ON TOP, WITH CHARTS, and a working × (2026-11-19, watch-newest spec §3.3).
 * Ajay: "When I add a new ticket they are gettinf added in to que but not active … charts are not loading I amhaving to
 * click on the chips again". The lib helpers the board runs on: pickAt, the join rule (his names + 🎯 A+ only), the
 * fresh / unseen reads, the pick join, the rows key (with the join bit), the optimistic ×, the pending plan (the late
 * poll out of window only) and the pages anchor. NEGATIVES throughout. */
import { beforeEach, describe, expect, it } from 'vitest';
import fixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import {
  GGW_NEW_FALLBACK_HOURS, GGW_PICK_AT_KEY, ggwAddedMs, ggwAnchorPage, ggwDropFromPick, ggwFreshNames, ggwJoinable,
  ggwJoinPick, ggwPendingPlan, ggwRowsKey, ggwUnseenOwn, ggwWithout, parseGgw, readGgwPickAt, saveGgwPickAt,
  type GgwBoard, type GgwRow,
} from './gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const H = 3600_000;
const NOW = Date.parse('2026-11-19T15:00:00.000Z');
const iso = (ms: number) => new Date(ms).toISOString().replace('Z', '+00:00');
const AUTO = { tag: '🤖', sources: [], source_words: [], text: '🤖 auto', volume_text: null, volume_source: null,
  added_et: null, added_text: null, leaving_text: null, remove_title: null, why: 'potential' };
const APLUS = { tag: '🎯', text: '🎯 A+', title: null, items: [] };
function row(symbol: string, o: Partial<GgwRow> = {}): GgwRow {
  return { symbol, state: 'ok', text: null, from_session: null, as_of_et: null, stale: false, frames: [], rang: [],
    auto: null, aplus: null, tags: null, added_at: null, late_text: null, ...o };
}
function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}

describe('ggw.pickAt', () => {
  beforeEach(() => { Object.defineProperty(window, 'localStorage', { configurable: true, value: memStorage() }); });
  it('round-trips', () => {
    saveGgwPickAt(NOW);
    expect(window.localStorage.getItem(GGW_PICK_AT_KEY)).toBe(String(NOW));
    expect(readGgwPickAt()).toBe(NOW);
  });
  it('NEGATIVE: junk stored values read as null', () => {
    for (const j of ['', 'abc', '-5', '0', '1.5', 'NaN']) {
      window.localStorage.setItem(GGW_PICK_AT_KEY, j);
      expect(readGgwPickAt()).toBeNull();
    }
    window.localStorage.removeItem(GGW_PICK_AT_KEY);
    expect(readGgwPickAt()).toBeNull();
  });
  it('NEGATIVE: a junk time is never written', () => {
    for (const j of [Number.NaN, 0, -5, Number.POSITIVE_INFINITY]) saveGgwPickAt(j);
    expect(window.localStorage.getItem(GGW_PICK_AT_KEY)).toBeNull();
  });
  it('NEGATIVE: blocked storage → null, no throw', () => {
    const bad = { getItem: () => { throw new Error('x'); }, setItem: () => { throw new Error('x'); },
      removeItem: () => { throw new Error('x'); } };
    Object.defineProperty(window, 'localStorage', { configurable: true, value: bad });
    expect(readGgwPickAt()).toBeNull();
    expect(() => saveGgwPickAt(NOW)).not.toThrow();
  });
});

describe('ggwAddedMs / ggwJoinable', () => {
  it('ISO → ms; NEGATIVE: null, "x", 5 → null', () => {
    expect(ggwAddedMs({ added_at: iso(NOW) })).toBe(NOW);
    expect(ggwAddedMs({ added_at: null })).toBeNull();
    expect(ggwAddedMs({ added_at: 'x' })).toBeNull();
    expect(ggwAddedMs({ added_at: 5 as unknown as string })).toBeNull();
    expect(ggwAddedMs({})).toBeNull();
  });
  it('his own → true; 🤖 potential → false; 🤖 with aplus → true; 🤖 why aplus → true', () => {
    expect(ggwJoinable(row('OWN'))).toBe(true);
    expect(ggwJoinable(row('POT', { auto: AUTO }))).toBe(false);
    expect(ggwJoinable(row('TAG', { auto: AUTO, aplus: APLUS }))).toBe(true);
    expect(ggwJoinable(row('SEAT', { auto: { ...AUTO, why: 'aplus' } }))).toBe(true);
  });
});

describe('ggwFreshNames', () => {
  const at = (h: number) => iso(NOW - h * H);
  it('strictly after pickAt; NEGATIVE: an equal time is not new', () => {
    const pickAt = NOW - 2 * H;
    const rows = [row('A', { added_at: at(1) }), row('B', { added_at: iso(pickAt) }), row('C', { added_at: at(3) })];
    expect(ggwFreshNames(rows, { seen: ['A', 'B', 'C'], pickAt, nowMs: NOW })).toEqual(['A']);
  });
  it(`no pickAt → the last ${GGW_NEW_FALLBACK_HOURS} h: 23 h new, 25 h not`, () => {
    const rows = [row('A', { added_at: at(23) }), row('B', { added_at: at(25) })];
    expect(ggwFreshNames(rows, { seen: ['A', 'B'], pickAt: null, nowMs: NOW })).toEqual(['A']);
  });
  it('the union with names not in seen, in ROW order', () => {
    const rows = [row('A'), row('B', { added_at: at(1) }), row('C')];
    expect(ggwFreshNames(rows, { seen: ['B'], pickAt: NOW - 2 * H, nowMs: NOW })).toEqual(['A', 'B', 'C']);
    expect(ggwFreshNames(rows, { seen: ['A', 'B'], pickAt: NOW - 2 * H, nowMs: NOW })).toEqual(['B', 'C']);
  });
  it('NEGATIVE: a null added_at is never new by time; no seen → only the time rule', () => {
    const rows = [row('A'), row('B', { added_at: at(1) })];
    expect(ggwFreshNames(rows, { seen: null, pickAt: NOW - 2 * H, nowMs: NOW })).toEqual(['B']);
    expect(ggwFreshNames([row('A')], { seen: null, pickAt: null, nowMs: NOW })).toEqual([]);
  });
  it('NEGATIVE: an ordinary 🤖 row new by time AND by seen is NOT returned; a 🤖 🎯 A+ is', () => {
    const rows = [row('POT', { auto: AUTO, added_at: at(1) }), row('ASEAT', { auto: { ...AUTO, why: 'aplus' }, added_at: at(1) })];
    expect(ggwFreshNames(rows, { seen: [], pickAt: NOW - 2 * H, nowMs: NOW })).toEqual(['ASEAT']);
  });
});

describe('ggwUnseenOwn', () => {
  it('the first of HIS rows not in seen', () => {
    expect(ggwUnseenOwn([row('A'), row('B'), row('C')], ['A'])).toBe('B');
  });
  it('NEGATIVE: seen null → null; a 🤖 row not in seen → never; every his-row seen → null', () => {
    expect(ggwUnseenOwn([row('A')], null)).toBeNull();
    expect(ggwUnseenOwn([row('A'), row('POT', { auto: AUTO }), row('ASEAT', { auto: AUTO, aplus: APLUS })], ['A'])).toBeNull();
    expect(ggwUnseenOwn([row('A'), row('B')], ['A', 'B'])).toBeNull();
  });
});

describe('ggwJoinPick', () => {
  const list = ['N1', 'N2', 'A', 'B', 'C'];
  it('joins first, never doubles', () => {
    expect(ggwJoinPick(['A', 'B'], list, ['N1', 'N2', 'A', 'N1'])).toEqual(['N1', 'N2', 'A', 'B']);
    expect(ggwJoinPick(['A'], list, ['A'])).toEqual(['A']);
  });
  it('NEGATIVE: no pick → null (the pages stay the pages)', () => {
    expect(ggwJoinPick(null, list, ['N1'])).toBeNull();
  });
  it('NEGATIVE: a pick of only stale names stays unchanged — never becomes [new]', () => {
    expect(ggwJoinPick(['GONE'], list, ['N1'])).toEqual(['GONE']);
  });
  it('NEGATIVE: a fresh name not on the list never joins', () => {
    expect(ggwJoinPick(['A'], list, ['ZZZ'])).toEqual(['A']);
  });
});

describe('ggwRowsKey', () => {
  const base = [row('A', { added_at: iso(NOW) }), row('POT', { auto: AUTO, added_at: iso(NOW - H) })];
  it('changes when one added_at changes', () => {
    const b = clone(base);
    b[0].added_at = iso(NOW + 1000);
    expect(ggwRowsKey(b)).not.toBe(ggwRowsKey(base));
  });
  it('[C5] changes when ONLY a row\'s joinability flips (a 🤖 potential gains aplus, same added_at)', () => {
    const b = clone(base);
    b[1].aplus = APLUS;
    expect(ggwRowsKey(b)).not.toBe(ggwRowsKey(base));
  });
  it('NEGATIVE: text / frames / state changes leave it equal', () => {
    const b = clone(base);
    b[0].text = 'other words';
    b[0].state = 'pending';
    b[0].frames = [{} as never];
    expect(ggwRowsKey(b)).toBe(ggwRowsKey(base));
  });
});

describe('ggwWithout / ggwDropFromPick', () => {
  const board = parseGgw(clone(fixture)) as GgwBoard;
  it('drops both the rows and the symbols', () => {
    const b = ggwWithout(board, ['AMD']);
    expect(b.rows.map((r) => r.symbol)).toEqual(['OMH', 'XYZQ', 'NVDA']);
    expect(b.symbols).toEqual(['OMH', 'XYZQ', 'NVDA']);
    expect(board.rows).toHaveLength(4);                                  // NEGATIVE: the input is not mutated
  });
  it('NEGATIVE: nothing removed → the SAME object', () => {
    expect(ggwWithout(board, [])).toBe(board);
    expect(ggwWithout(board, ['ZZZ'])).toBe(board);
  });
  it('a removed name leaves the pick; the last one → null', () => {
    expect(ggwDropFromPick(['A', 'B'], 'A')).toEqual(['B']);
    expect(ggwDropFromPick(['A'], 'A')).toBeNull();
    expect(ggwDropFromPick(null, 'A')).toBeNull();
    expect(ggwDropFromPick(['A'], 'Z')).toEqual(['A']);
  });
});

describe('ggwPendingPlan', () => {
  const since = new Map([['A', NOW - 10_000], ['B', NOW - 100_000]]);
  const o = { poll: 5, max: 90, latePoll: 60, refresh: 0 };
  it('due → the due names every poll s; late is returned beside it', () => {
    expect(ggwPendingPlan(['A', 'B'], since, NOW, o)).toEqual({ names: ['A'], delaySec: 5, late: ['B'] });
  });
  it('all late + latePoll + refresh 0 (out of window) → the late names every latePoll s', () => {
    expect(ggwPendingPlan(['B'], since, NOW, o)).toEqual({ names: ['B'], delaySec: 60, late: ['B'] });
  });
  it('[C7] NEGATIVE: all late + latePoll + refresh 60 (in window) → no poll, but late still lists them', () => {
    expect(ggwPendingPlan(['B'], since, NOW, { ...o, refresh: 60 })).toEqual({ names: [], delaySec: 0, late: ['B'] });
  });
  it('NEGATIVE: latePoll null (an older server) → stops at the cap exactly as before', () => {
    expect(ggwPendingPlan(['B'], since, NOW, { ...o, latePoll: null })).toEqual({ names: [], delaySec: 0, late: ['B'] });
  });
  it('NEGATIVE: poll 0 → nothing is polled', () => {
    expect(ggwPendingPlan(['A'], since, NOW, { ...o, poll: 0, latePoll: null })).toEqual({ names: [], delaySec: 0, late: [] });
  });
  it('the cap is ≥ max: exactly max s waited is late', () => {
    const m = new Map([['C', NOW - 90_000]]);
    expect(ggwPendingPlan(['C'], m, NOW, { ...o, refresh: 60 }).late).toEqual(['C']);
  });
});

describe('ggwAnchorPage', () => {
  it('the anchor on the list → its page; NEGATIVE: an anchor that left → null', () => {
    expect(ggwAnchorPage(['X', 'A', 'B', 'C', 'D'], 'C', 2)).toBe(1);
    expect(ggwAnchorPage(['A', 'B'], 'C', 2)).toBeNull();
    expect(ggwAnchorPage(['A', 'B'], null, 2)).toBeNull();
  });
});

describe('parsing', () => {
  it('parseRow keeps a good added_at / late_text; NEGATIVE: junk → null', () => {
    const raw = clone(fixture) as any;
    raw.rows[0].added_at = '2026-11-19T15:00:00.000+00:00';
    raw.rows[1].late_text = '⏳ still reading — not read yet; this tile checks again every 60 s';
    raw.rows[2].added_at = 'x';
    raw.rows[2].late_text = '   ';
    raw.rows[3].added_at = 5;
    raw.rows[3].late_text = 7;
    const b = parseGgw(raw) as GgwBoard;
    expect(b.rows[0].added_at).toBe('2026-11-19T15:00:00.000+00:00');
    expect(b.rows[1].late_text).toBe(raw.rows[1].late_text);
    expect(b.rows[0].late_text).toBeNull();
    expect(b.rows[1].added_at).toBeNull();
    expect(b.rows[2].added_at).toBeNull();
    expect(b.rows[2].late_text).toBeNull();
    expect(b.rows[3].added_at).toBeNull();
    expect(b.rows[3].late_text).toBeNull();
  });
  it('parseGgw: pending_late_poll_sec kept; NEGATIVE: junk / absent → null', () => {
    expect((parseGgw({ ...clone(fixture), pending_late_poll_sec: 60 }) as GgwBoard).pending_late_poll_sec).toBe(60);
    expect((parseGgw({ ...clone(fixture), pending_late_poll_sec: 'x' }) as GgwBoard).pending_late_poll_sec).toBeNull();
    expect((parseGgw(clone(fixture)) as GgwBoard).pending_late_poll_sec).toBeNull();
  });
});
