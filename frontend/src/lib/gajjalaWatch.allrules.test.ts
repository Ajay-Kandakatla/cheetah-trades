/* ✅ 👀 Watch — All rules met, the lib (2026-11-24, spec watch_all_rules §3.6 / §4 WP fe-watch).
 * Ajay 2026-11-24: "Anytime stocks qualify all his rules should be auto added to the Watch list so I can keep tracking
 * them later". The server serves a LAST section `rules` with `folded_default: true` and ✅ rows under `row.auto` with
 * `why: "rules"`. Here: the parse (folded_default only when served true; the `rules` head), the folded set
 * (collapsed ∪ default-folded − opened), the toggle and reveal paths, `ggw.opened`, the live list (✅ last; skipped while
 * folded on the phone; his names always live) and his pick (a ✅ row never joins). Every word is a stand-in for a served
 * one. NEGATIVES: junk folded_default / junk ggw.opened → open / []; a ✅ row never joins his pick nor ggwUnseenOwn; a
 * `skip` holding 'yours' never drops his names; no ✅ row → the old live list exactly. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import gold from './__fixtures__/ggwAllRules.golden.json';
import gold90 from './__fixtures__/ggwAllRules90.golden.json';
import {
  GGW_COLLAPSED_KEY, GGW_OPENED_KEY, GGW_RULES_WHY, ggwDefaultFolded, ggwFoldedKeys, ggwFreshNames, ggwIsRulesRow,
  ggwJoinable, ggwLiveSkip, ggwLiveSymbols, ggwRevealGroup, ggwRevealOpened, ggwRulesWarn, ggwToggleFold, ggwUnseenOwn,
  parseGgw, parseGgwOpened, parseRulesHead, parseSections, readGgwOpened, saveGgwOpened,
  type GgwBoard, type GgwRow, type GgwSection,
} from './gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = fixture as any;

/* ✅ the goldens BE writes (be-payload) — the FE pins the same files. */
const GOLD: Record<string, any> = { 'ggwAllRules.golden.json': gold, 'ggwAllRules90.golden.json': gold90 };
const golden = (name: string): any => clone(GOLD[name]);

const SEC = (key: string, n: number, syms: string[], o: Record<string, unknown> = {}) => ({
  key, title: `served-title-${key}`, text: `served-head-${key} · ${n}`, hint: `served-hint-${key}`, n, symbols: syms, ...o,
});
const AUTO = (why: string) => ({ tag: why === 'rules' ? '✅' : '🤖', text: `served-auto-${why}`, why });
const ORG = (group: string) => ({ group, when: { text: `served-when-${group}` }, setup: null, ran: null, past_winner: null });
function rowRaw(sym: string, group: string, o: Record<string, unknown> = {}): any {
  const base = clone(RAW.rows[2]);
  base.symbol = sym;
  return { ...base, auto: null, aplus: null, added_at: null, org: ORG(group), ...o };
}
/** 👤 H1 H2 · 🎯 AP1 · 🤖 AU1 · ✅ R1 R2 — the served order 👤 → 🎯 → 🤖 → ✅. */
function boardRaw(o: Record<string, unknown> = {}): any {
  const b = clone(RAW);
  b.rows = [
    rowRaw('H1', 'yours'), rowRaw('H2', 'yours'),
    rowRaw('AP1', 'aplus', { auto: AUTO('aplus'), aplus: { tag: '🎯', text: 'served-aplus', title: null, items: [] } }),
    rowRaw('AU1', 'auto', { auto: AUTO('potential') }),
    rowRaw('R1', 'rules', { auto: AUTO('rules') }),
    rowRaw('R2', 'rules', { auto: AUTO('rules') }),
  ];
  b.sections = [
    SEC('yours', 2, ['H1', 'H2']), SEC('aplus', 1, ['AP1']), SEC('auto', 1, ['AU1']),
    SEC('rules', 2, ['R1', 'R2'], { folded_default: true }),
  ];
  b.rules = { state: 'ok', n: 2, keep_sessions: 5, text: null, not_seated_n: 0 };
  return { ...b, ...o };
}
const parsed = (raw: any = boardRaw()) => parseGgw(raw) as GgwBoard;

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('✅ parse: folded_default and the rules head', () => {
  it('folded_default kept ONLY when served true; other sections carry no key (byte-equal to the 11-22 shape)', () => {
    const s = parseSections(boardRaw().sections)!;
    expect(s.map((x) => x.key)).toEqual(['yours', 'aplus', 'auto', 'rules']);
    expect(s[3].folded_default).toBe(true);
    for (const x of s.slice(0, 3)) expect('folded_default' in x).toBe(false);
  });
  it('NEGATIVE: junk folded_default ("yes", 1, "true", {}, null, false) → no key → the section is open', () => {
    for (const junk of ['yes', 1, 'true', {}, null, false]) {
      const s = parseSections([SEC('rules', 1, ['R1'], { folded_default: junk })])!;
      expect('folded_default' in s[0]).toBe(false);
      expect(ggwDefaultFolded(s)).toEqual([]);
      expect(ggwFoldedKeys(s, [], [])).toEqual([]);
    }
  });
  it('the rules head: served → kept; absent → no key; junk → null; negative / NaN numbers → null', () => {
    expect(parsed().rules).toEqual({ state: 'ok', n: 2, keep_sessions: 5, text: null, not_seated_n: 0 });
    const old = boardRaw();
    delete old.rules;
    expect('rules' in parsed(old)).toBe(false);
    for (const junk of [null, 'x', 1, [], {}, { state: '' }, { state: 3 }]) expect(parseRulesHead(junk)).toBeNull();
    expect(parseRulesHead({ state: 'ok', n: -1, keep_sessions: NaN, not_seated_n: 'x' }))
      .toEqual({ state: 'ok', n: null, keep_sessions: null, text: null, not_seated_n: null });
  });
  it('ggwRulesWarn: the served text ONLY on state "unreadable" — NEGATIVE: ok / off / no text / absent → null', () => {
    const t = 'served-rules-unreadable';
    expect(ggwRulesWarn(parsed(boardRaw({ rules: { state: 'unreadable', text: t } })))).toBe(t);
    expect(ggwRulesWarn(parsed(boardRaw({ rules: { state: 'unreadable', text: null } })))).toBeNull();
    expect(ggwRulesWarn(parsed(boardRaw({ rules: { state: 'ok', text: t } })))).toBeNull();
    expect(ggwRulesWarn(parsed(boardRaw({ rules: { state: 'off', text: t } })))).toBeNull();
    expect(ggwRulesWarn(parsed(boardRaw({ rules: 'junk' })))).toBeNull();
    expect(ggwRulesWarn(null)).toBeNull();
  });
});

describe('✅ the folded set, the toggle and ggw.opened', () => {
  const S = (): GgwSection[] => parseSections(boardRaw().sections)!;
  it('folded = collapsed ∪ (default-folded − opened)', () => {
    expect(ggwFoldedKeys(S(), [], [])).toEqual(['rules']);
    expect(ggwFoldedKeys(S(), ['auto'], [])).toEqual(['auto', 'rules']);
    expect(ggwFoldedKeys(S(), ['auto'], ['rules'])).toEqual(['auto']);
    expect(ggwFoldedKeys(S(), ['rules'], [])).toEqual(['rules']);           // never twice
  });
  it('NEGATIVE: a section without folded_default → open as before (folded only by collapsed)', () => {
    const s = parseSections([SEC('yours', 1, ['H1']), SEC('auto', 1, ['AU1'])])!;
    expect(ggwFoldedKeys(s, [], [])).toEqual([]);
    expect(ggwFoldedKeys(s, [], ['auto', 'yours'])).toEqual([]);
    expect(ggwFoldedKeys(null, ['auto'], [])).toEqual(['auto']);
  });
  it('a tap on ✅ flips `opened`; a tap on any other key flips `collapsed` (unchanged)', () => {
    let st = { collapsed: [] as string[], opened: [] as string[] };
    st = ggwToggleFold(S(), st, 'rules');
    expect(st).toEqual({ collapsed: [], opened: ['rules'] });
    expect(ggwFoldedKeys(S(), st.collapsed, st.opened)).toEqual([]);
    st = ggwToggleFold(S(), st, 'rules');
    expect(st).toEqual({ collapsed: [], opened: [] });
    st = ggwToggleFold(S(), st, 'auto');
    expect(st).toEqual({ collapsed: ['auto'], opened: [] });
    st = ggwToggleFold(S(), st, 'auto');
    expect(st).toEqual({ collapsed: [], opened: [] });
  });
  it('a stale ggw.collapsed holding ✅ still opens on ONE tap (the key leaves collapsed, joins opened)', () => {
    const st = ggwToggleFold(S(), { collapsed: ['rules', 'auto'], opened: [] }, 'rules');
    expect(st).toEqual({ collapsed: ['auto'], opened: ['rules'] });
    expect(ggwFoldedKeys(S(), st.collapsed, st.opened)).toEqual(['auto']);
  });
  it('ggw.opened round-trips; empty → the key removed', () => {
    vi.stubGlobal('localStorage', memStorage());
    saveGgwOpened(['rules']);
    expect(window.localStorage.getItem(GGW_OPENED_KEY)).toBe('["rules"]');
    expect(readGgwOpened()).toEqual(['rules']);
    saveGgwOpened([]);
    expect(window.localStorage.getItem(GGW_OPENED_KEY)).toBeNull();
    expect(GGW_OPENED_KEY).not.toBe(GGW_COLLAPSED_KEY);
  });
  it('NEGATIVE: junk ggw.opened → [] (✅ stays folded)', () => {
    for (const junk of [null, 'not json', '{"rules":1}', '[1,2]', 'rules', '[" bad key "]', 42]) {
      expect(parseGgwOpened(junk)).toEqual([]);
    }
    vi.stubGlobal('localStorage', memStorage());
    window.localStorage.setItem(GGW_OPENED_KEY, 'not json');
    expect(readGgwOpened()).toEqual([]);
    expect(ggwFoldedKeys(S(), [], readGgwOpened())).toEqual(['rules']);
  });
  it('NEGATIVE: a blocked localStorage → read [] and save never throws', () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); },
      removeItem: () => { throw new Error('blocked'); } });
    expect(readGgwOpened()).toEqual([]);
    expect(() => saveGgwOpened(['rules'])).not.toThrow();
  });
});

describe('✅ [C5] a reveal into ✅ opens it', () => {
  it('ggwRevealOpened adds ✅ to opened for a ✅ name; ggwRevealGroup leaves collapsed alone', () => {
    const b = parsed();
    expect(ggwRevealOpened([], b.sections, b.rows, 'R2')).toEqual(['rules']);
    const keys: string[] = [];
    expect(ggwRevealGroup(keys, b.rows, 'R2')).toBe(keys);
  });
  it('NEGATIVE: the SAME array when nothing changes (not listed / not default-folded / already opened)', () => {
    const b = parsed();
    const o: string[] = [];
    expect(ggwRevealOpened(o, b.sections, b.rows, 'NOPE')).toBe(o);
    expect(ggwRevealOpened(o, b.sections, b.rows, 'AU1')).toBe(o);
    expect(ggwRevealOpened(o, b.sections, b.rows, 'H1')).toBe(o);
    const op = ['rules'];
    expect(ggwRevealOpened(op, b.sections, b.rows, 'R1')).toBe(op);
    const noDefault = parseSections([SEC('rules', 2, ['R1', 'R2'])]);
    expect(ggwRevealOpened(o, noDefault, b.rows, 'R1')).toBe(o);
  });
});

describe('✅ [C4] the live list: ✅ last, skipped while folded on the phone, his names always live', () => {
  it('rows NOT in ✅ first in served order, then ✅ rows — even when the server interleaves them', () => {
    const raw = boardRaw();
    raw.rows = [raw.rows[4], raw.rows[0], raw.rows[5], raw.rows[3]];          // R1 H1 R2 AU1
    expect(ggwLiveSymbols(parsed(raw))).toEqual(['H1', 'AU1', 'R1', 'R2']);
    expect(ggwLiveSymbols(parsed())).toEqual(['H1', 'H2', 'AP1', 'AU1', 'R1', 'R2']);
  });
  it('NEGATIVE: no ✅ row and no skip → exactly every row in served order (the 11-17 list)', () => {
    const old = parseGgw(clone(RAW)) as GgwBoard;
    expect(ggwLiveSymbols(old)).toEqual(old.rows.map((r) => r.symbol));
    expect(ggwLiveSymbols(old, new Set())).toEqual(old.rows.map((r) => r.symbol));
  });
  it('phone with ✅ folded → no ✅ symbol posted; opened → posted (last)', () => {
    const b = parsed();
    const foldedSkip = ggwLiveSkip(b.sections, [], []);
    expect(Array.from(foldedSkip)).toEqual(['rules']);
    expect(ggwLiveSymbols(b, foldedSkip)).toEqual(['H1', 'H2', 'AP1', 'AU1']);
    const openSkip = ggwLiveSkip(b.sections, [], ['rules']);
    expect(openSkip.size).toBe(0);
    expect(ggwLiveSymbols(b, openSkip)).toEqual(['H1', 'H2', 'AP1', 'AU1', 'R1', 'R2']);
  });
  it('NEGATIVE: a section HE folded (collapsed 🤖 / 👤) is never in skip — those names keep ticking (11-22 behaviour)', () => {
    const b = parsed();
    const skip = ggwLiveSkip(b.sections, ['auto', 'yours'], ['rules']);
    expect(skip.size).toBe(0);
    expect(ggwLiveSymbols(b, skip)).toEqual(['H1', 'H2', 'AP1', 'AU1', 'R1', 'R2']);
  });
  it("NEGATIVE: a skip holding 'yours' (never passed by the board) still keeps every one of his names live", () => {
    const b = parsed();
    expect(ggwLiveSymbols(b, new Set(['yours', 'rules']))).toEqual(['H1', 'H2', 'AP1', 'AU1']);
    /* even a server that marked 👤 default-folded cannot take his names off the live list */
    const raw = boardRaw();
    raw.sections[0].folded_default = true;
    const b2 = parsed(raw);
    const skip = ggwLiveSkip(b2.sections, [], []);
    expect(skip.has('yours')).toBe(true);
    expect(ggwLiveSymbols(b2, skip)).toEqual(['H1', 'H2', 'AP1', 'AU1']);
  });
  it('90 rows (past the hub cap of 80): every 👤/🎯/🤖 name comes before any ✅, so the refused tail is all ✅', () => {
    const raw = boardRaw();
    const mk = (n: number, pre: string, group: string, auto: any) =>
      Array.from({ length: n }, (_x, i) => rowRaw(`${pre}${i}`, group, { auto }));
    const rules = mk(60, 'R', 'rules', AUTO('rules'));
    const others = [...mk(8, 'H', 'yours', null), ...mk(4, 'P', 'aplus', AUTO('aplus')), ...mk(18, 'A', 'auto', AUTO('potential'))];
    raw.rows = [...others.slice(0, 10), ...rules.slice(0, 30), ...others.slice(10), ...rules.slice(30)];
    const live = ggwLiveSymbols(parsed(raw));
    expect(live).toHaveLength(90);
    const firstRules = live.findIndex((s) => s.startsWith('R'));
    expect(firstRules).toBe(30);
    expect(live.slice(80).every((s) => s.startsWith('R'))).toBe(true);
    expect(live.slice(0, 30).some((s) => s.startsWith('R'))).toBe(false);
  });
  it('the 90-row golden: no ✅ name before the last non-✅ name', () => {
    const b = parseGgw(golden('ggwAllRules90.golden.json')) as GgwBoard;
    const live = ggwLiveSymbols(b);
    const isR = new Set(b.rows.filter(ggwIsRulesRow).map((r) => r.symbol));
    const lastOther = live.map((s) => !isR.has(s)).lastIndexOf(true);
    expect(live.slice(0, lastOther + 1).some((s) => isR.has(s))).toBe(false);
    expect(live).toHaveLength(b.rows.length);
  });
});

describe('✅ his pick: a ✅ row never joins', () => {
  const R = (): GgwRow => parsed().rows.find((r) => r.symbol === "R1")!;
  it('ggwIsRulesRow / ggwJoinable false — even when a board reads it A+ today (its aplus block served)', () => {
    const r = R();
    expect(GGW_RULES_WHY).toBe('rules');
    expect(ggwIsRulesRow(r)).toBe(true);
    expect(ggwJoinable(r)).toBe(false);
    expect(ggwJoinable({ ...r, aplus: { tag: '🎯', text: 'served-aplus', title: null, items: [] } })).toBe(false);
    /* POS controls: his row and a 🎯 A+ seat still join */
    const b = parsed();
    expect(ggwJoinable(b.rows[0])).toBe(true);
    expect(ggwJoinable(b.rows[2])).toBe(true);
    expect(ggwJoinable(b.rows[3])).toBe(false);
  });
  it('NEGATIVE: a ✅ row is never fresh, never ggwUnseenOwn', () => {
    const b = parsed();
    const fresh = ggwFreshNames(b.rows.map((r) => ({ ...r, added_at: '2026-11-24T15:00:00Z' })),
      { seen: [], pickAt: null, nowMs: Date.parse('2026-11-24T15:01:00Z') });
    expect(fresh).toEqual(['H1', 'H2', 'AP1']);
    expect(ggwUnseenOwn(b.rows, ['H1', 'H2'])).toBeNull();
    expect(ggwUnseenOwn(b.rows.filter((r) => ggwIsRulesRow(r)), [])).toBeNull();
  });
});

describe('✅ the BE golden (be-payload writes it)', () => {
  it('parses: ✅ is the LAST served section and the only one folded by default; its rows are ✅ rows', () => {
    const b = parseGgw(golden('ggwAllRules.golden.json')) as GgwBoard;
    expect(b.state).toBe('ok');
    const keys = (b.sections ?? []).map((s) => s.key);
    expect(keys[keys.length - 1]).toBe('rules');
    expect(ggwDefaultFolded(b.sections)).toEqual(['rules']);
    const rulesRows = b.rows.filter((r) => r.org?.group === 'rules');
    expect(rulesRows.length).toBeGreaterThan(0);
    for (const r of rulesRows) { expect(ggwIsRulesRow(r)).toBe(true); expect(ggwJoinable(r)).toBe(false); }
  });
});
