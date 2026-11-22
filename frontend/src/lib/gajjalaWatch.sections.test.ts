/* 🗂 Watch sections — the lib (2026-11-22, spec watch_org rev 4 §3.5 / §4 WP-FE-WATCH).
 * Ajay 2026-11-22: "Manual ones I add them need to be on top then auto intraday..". The server groups, orders and words
 * everything (gajjala_watch/sections.py); the FE parses what is served, in served order, with NO key list. Every word in
 * these fixtures is a stand-in for a served one. NEGATIVES: an old payload carries no `sections` / `org` key at all; junk
 * org / sections never reach the board; a NaN number never survives; the `only` poll's `org: null` never replaces the
 * board's org; junk `ggw.collapsed` → every section open. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import {
  GGW_COLLAPSED_KEY, ggwGroupStarts, ggwMergeRows, ggwRevealGroup, ggwSectionsOn, ggwToggleCollapsed, parseGgw,
  parseGgwCollapsed, parsePastWinner, parseRan, parseRowOrg, parseSections, readGgwCollapsed, saveGgwCollapsed,
  type GgwBoard, type GgwRow,
} from './gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = fixture as any;

/* The served shapes (backend sections.sections_block / row org, spec §3.3) — words are stand-ins. */
const SECTIONS = [
  { key: 'yours', title: 'served-title-1', text: 'served-title-1 · 1', hint: 'served hint 1', n: 1, symbols: ['OMH'] },
  { key: 'aplus', title: 'served-title-2', text: 'served-title-2 · 1', hint: 'served hint 2', n: 1, symbols: ['AMD'] },
  { key: 'auto', title: 'served-title-3', text: 'served-title-3 · 2', hint: 'served hint 3', n: 2, symbols: ['XYZQ', 'NVDA'] },
];
const RAN_OK = {
  date: '2026-11-20', day: 'Fri', prev_close: 1.2, high: 3.18, run_pct: 165.2, peak_et: '17:40', timing: 'eod',
  timing_text: 'served timing words', pm_high_pct: 67.7, premarket_peak: false, counts: true, reg_close: 2.9,
  text: 'served ran chip', title: 'served ran title',
};
const ORG = (group: string, o: Record<string, unknown> = {}) => ({
  group,
  when: { bucket: 'premarket', verb: 'added', at_et: '07:12', date: '2026-11-20', text: 'served when chip', title: 'served when title' },
  setup: { text: 'served setup chip', title: 'served setup hover' },
  ran: null, past_winner: null, ...o,
});

function boardRaw(): any {
  const b = clone(RAW);
  b.rows[0].org = ORG('yours');
  b.rows[1].org = ORG('aplus');
  b.rows[2].org = ORG('auto', { ran: RAN_OK });
  b.rows[3].org = ORG('auto');
  b.sections = clone(SECTIONS);
  return b;
}

afterEach(() => { vi.unstubAllGlobals(); });

describe('🗂 parseGgw keeps the served sections and org — only when served', () => {
  it('sections in served order; every row org parsed', () => {
    const p = parseGgw(boardRaw()) as GgwBoard;
    expect(p.sections!.map((s) => s.key)).toEqual(['yours', 'aplus', 'auto']);
    expect(p.sections![0]).toEqual({ ...SECTIONS[0] });
    expect(p.rows.map((r) => r.org?.group)).toEqual(['yours', 'aplus', 'auto', 'auto']);
    expect(p.rows[2].org!.ran!.text).toBe('served ran chip');
    expect(p.rows[0].org!.when!.text).toBe('served when chip');
    expect(p.rows[0].org!.setup).toEqual({ text: 'served setup chip', title: 'served setup hover' });
    expect(ggwSectionsOn(p)).toBe(true);
  });
  it('NEGATIVE: an old payload (no sections / org) has NEITHER key — the flat board, byte for byte', () => {
    const p = parseGgw(clone(RAW)) as GgwBoard;
    expect('sections' in p).toBe(false);
    for (const r of p.rows) expect('org' in r).toBe(false);
    expect(ggwSectionsOn(p)).toBe(false);
  });
  it('NEGATIVE: served sections null / [] / junk → org mode off', () => {
    for (const s of [null, [], 'x', 7, [{ key: '' }]]) {
      const b = boardRaw();
      b.sections = s;
      expect(ggwSectionsOn(parseGgw(b) as GgwBoard)).toBe(false);
    }
  });
});

describe('🗂 parseSections — any served key, served order, no key list', () => {
  it('a FOURTH served key (the later "ran", autoadd shape) is kept in its served place', () => {
    const s = parseSections([...SECTIONS, { key: 'ran', title: 'served-4', text: 'served-4 · 2', hint: 'h4', n: 2, symbols: ['A', 'B'] }])!;
    expect(s.map((x) => x.key)).toEqual(['yours', 'aplus', 'auto', 'ran']);
    const odd = parseSections([{ key: 'zeta', text: 'z' }, { key: 'alpha', text: 'a' }])!;
    expect(odd.map((x) => x.key)).toEqual(['zeta', 'alpha']);
  });
  it('NEGATIVE: blank / non-string keys, no header words and repeated keys are dropped; junk n → null', () => {
    const s = parseSections([
      { key: '', text: 'x' }, { key: '   ', text: 'x' }, { key: 7, text: 'x' }, { key: null, text: 'x' }, 'junk', null,
      { key: 'a', text: '', title: '' }, { key: 'b', text: 'b-words', n: Number.NaN, symbols: [1, 'S', null] },
      { key: 'b', text: 'second b' }, { key: 'c', title: 'title only' },
    ])!;
    expect(s.map((x) => x.key)).toEqual(['b', 'c']);
    expect(s[0]).toEqual({ key: 'b', title: null, text: 'b-words', hint: null, n: null, symbols: ['S'] });
    expect(s[1].text).toBe('title only');
    expect(parseSections('nope')).toBeNull();
    expect(parseSections({})).toBeNull();
  });
});

describe('🗂 parseRowOrg / parseRan / parsePastWinner', () => {
  it('NEGATIVE: junk org → null (no chip): blank group, non-string group, not an object', () => {
    for (const v of [null, 7, 'x', [], {}, { group: '' }, { group: '  ' }, { group: 3 }, { group: Number.NaN }]) {
      expect(parseRowOrg(v)).toBeNull();
    }
  });
  it('NEGATIVE: junk inner blocks → null each (no chip), the group still kept', () => {
    const o = parseRowOrg({ group: 'auto', when: { text: '' }, setup: { text: 5 }, ran: { text: '', title: '' }, past_winner: { past_winner: [] } })!;
    expect(o).toEqual({ group: 'auto', when: null, setup: null, ran: null, past_winner: null });
  });
  it('a ran block with NO chip text keeps its title (the drawer line) — the premarket-peak case', () => {
    const r = parseRan({ ...RAN_OK, text: null, counts: false, premarket_peak: true, title: 'served pm-peak title' })!;
    expect(r.text).toBeNull();
    expect(r.title).toBe('served pm-peak title');
    expect(r.premarket_peak).toBe(true);
    expect(r.counts).toBe(false);
  });
  it('NEGATIVE: NaN / inf numbers → null; truthy non-true flags → false', () => {
    const r = parseRan({ ...RAN_OK, run_pct: Number.NaN, high: Number.POSITIVE_INFINITY, prev_close: 'x', counts: 1, premarket_peak: 'yes' })!;
    expect(r.run_pct).toBeNull();
    expect(r.high).toBeNull();
    expect(r.prev_close).toBeNull();
    expect(r.counts).toBe(false);
    expect(r.premarket_peak).toBe(false);
  });
  it('🏆 the replays shape: chip = the first served win, items = every served win, more = the served "+N more"', () => {
    const p = parsePastWinner({ past_winner: [{ text: 'win one' }, { text: '' }, { nope: 1 }, { text: 'win two' }], past_winner_more_text: 'more words' })!;
    expect(p).toEqual({ text: 'win one', items: ['win one', 'win two'], more: 'more words', title: null });
    const q = parsePastWinner({ text: 'chip', title: 'hover', items: ['a', 'b'] })!;
    expect(q).toEqual({ text: 'chip', items: ['a', 'b'], more: null, title: 'hover' });
  });
  it('NEGATIVE: 🏆 with no served words → null', () => {
    for (const v of [null, {}, { past_winner: [] }, { past_winner: [{ text: '' }] }, { text: '' }]) expect(parsePastWinner(v)).toBeNull();
  });
});

describe('🗂 ggwGroupStarts — ONE header per key, at its FIRST index [C6]', () => {
  const rows = (gs: Array<string | null>) => gs.map((g, i) => ({ symbol: `S${i}`, org: g ? parseRowOrg({ group: g }) : null }));
  it('[a, a, b, a] → headers at 0 and 2, never a second a', () => {
    const secs = parseSections([{ key: 'a', text: 'A' }, { key: 'b', text: 'B' }])!;
    expect(ggwGroupStarts(rows(['a', 'a', 'b', 'a']), secs).map((g) => [g.at, g.section.key])).toEqual([[0, 'a'], [2, 'b']]);
  });
  it('NEGATIVE: a row group with no served section, a row without org, no sections → no header', () => {
    const secs = parseSections([{ key: 'a', text: 'A' }])!;
    expect(ggwGroupStarts(rows([null, 'x', 'a']), secs).map((g) => g.at)).toEqual([2]);
    expect(ggwGroupStarts(rows(['a']), null)).toEqual([]);
  });
});

describe('🗂 ggwMergeRows keeps the board org [C6/C11]', () => {
  it('the only-poll row (org null) merges with the BOARD row\'s org', () => {
    const b = parseGgw(boardRaw()) as GgwBoard;
    const partRaw = clone(RAW);
    partRaw.rows = [{ ...clone(RAW.rows[2]), org: null, text: 'fresh text' }];
    const part = parseGgw(partRaw) as GgwBoard;
    const m = ggwMergeRows(b, part);
    const x = m.rows.find((r) => r.symbol === 'XYZQ') as GgwRow;
    expect(x.text).toBe('fresh text');
    expect(x.org).toBe(b.rows[2].org);
  });
  it('NEGATIVE: a board without the org key (older server) merges the partial row exactly as before', () => {
    const b = parseGgw(clone(RAW)) as GgwBoard;
    const part = parseGgw({ ...clone(RAW), rows: [clone(RAW.rows[2])] }) as GgwBoard;
    const m = ggwMergeRows(b, part);
    expect(m.rows[2]).toBe(part.rows[0]);
    expect('org' in m.rows[2]).toBe(false);
  });
});

describe('📱 ggw.collapsed — the phone\'s folded sections', () => {
  function mem(init: Record<string, string> = {}): Storage {
    const m = new Map(Object.entries(init));
    return {
      get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
      getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
      removeItem: (k: string) => { m.delete(k); },
    } as Storage;
  }
  it('a served-key list round-trips; empty removes the key', () => {
    vi.stubGlobal('localStorage', mem());
    saveGgwCollapsed(['auto', 'ran']);
    expect(window.localStorage.getItem(GGW_COLLAPSED_KEY)).toBe('["auto","ran"]');
    expect(readGgwCollapsed()).toEqual(['auto', 'ran']);
    saveGgwCollapsed([]);
    expect(window.localStorage.getItem(GGW_COLLAPSED_KEY)).toBeNull();
  });
  it('NEGATIVE: junk ggw.collapsed → [] (every section open), duplicates / odd keys dropped, a throwing store → []', () => {
    for (const v of [null, '', 'auto', '{"a":1}', '[1,2]', 'not json', '[""]']) expect(parseGgwCollapsed(v)).toEqual([]);
    expect(parseGgwCollapsed('["auto","auto","bad key!","yours"]')).toEqual(['auto', 'yours']);
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } });
    expect(readGgwCollapsed()).toEqual([]);
    expect(() => saveGgwCollapsed(['auto'])).not.toThrow();
  });
  it('fold toggles; reveal opens the target\'s group and is the SAME array when nothing changes', () => {
    expect(ggwToggleCollapsed(['a'], 'b')).toEqual(['a', 'b']);
    expect(ggwToggleCollapsed(['a', 'b'], 'a')).toEqual(['b']);
    const rows = [{ symbol: 'X', org: parseRowOrg({ group: 'auto' }) }, { symbol: 'Y', org: null }];
    const keys = ['auto', 'yours'];
    expect(ggwRevealGroup(keys, rows, 'X')).toEqual(['yours']);
    expect(ggwRevealGroup(keys, rows, 'Y')).toBe(keys);
    expect(ggwRevealGroup(keys, rows, 'NOPE')).toBe(keys);
    expect(ggwRevealGroup(['yours'], rows, 'X')).toEqual(['yours']);
  });
});
