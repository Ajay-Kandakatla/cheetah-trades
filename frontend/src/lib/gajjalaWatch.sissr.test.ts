/* ⛔🩳🔒 👀 Watch — the tagged-potentials section, the lib (2026-11-25, spec sissr §3.7 / §4 WP fe-watch).
 * Ajay 2026-11-24 ~23:20 ET (verbatim in spec sissr §0): the 🩳 / ⛔ / 🔒 tagged names that become 🧠 potentials go on the
 * Watch "and give them a time stamp of the day"; 2026-11-25 ~00:25 ET: "I do need a mention of High SI stock when
 * alerting for potential though..". The server serves a section `sissr` AFTER ✅ (`folded_default: true`) and its rows
 * under `row.auto` with `why: "sissr"`. Here: the marker, his pick (a ⛔🩳🔒 row NEVER joins — verifier HIGH, even with a
 * served `aplus` block), the live order (👤 / 🎯 / 🤖 → ✅ → ⛔🩳🔒 — verifier HIGH), the head's counts (parsed only, keyed
 * only when served), the fold / reveal on the BE golden. NEGATIVES: a junk `why` → an ordinary 🤖 row; no ⛔🩳🔒 row → the
 * 11-24 live list exactly; junk counts → null; no word literal / admin email in the lib's new block. */
import { describe, expect, it } from 'vitest';
import fixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import goldSissr from './__fixtures__/ggwSiSsr.golden.json';
import goldRules from './__fixtures__/ggwAllRules.golden.json';
import {
  GGW_RULES_WHY, GGW_SISSR_WHY, ggwDefaultFolded, ggwFoldedKeys, ggwFreshNames, ggwGroupStarts, ggwIsRulesRow,
  ggwIsSissrRow, ggwJoinable, ggwLiveSkip, ggwLiveSymbols, ggwRevealOpened, ggwRowsKey, ggwToggleFold, ggwUnseenOwn,
  parseGgw, parseRulesHead,
  type GgwBoard, type GgwRow,
} from './gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = fixture as any;
const G = (): any => clone(goldSissr as any);
const gb = (raw: any = G()) => parseGgw(raw) as GgwBoard;
const APLUS = { tag: '🎯', text: 'served-aplus', title: null, items: [] };

const AUTO = (why: unknown) => ({ tag: '🤖', text: `served-auto-${String(why)}`, why });
const ORG = (group: string) => ({ group, when: { text: `served-when-${group}` }, setup: null, ran: null, past_winner: null });
function rowRaw(sym: string, group: string, o: Record<string, unknown> = {}): any {
  const base = clone(RAW.rows[2]);
  base.symbol = sym;
  return { ...base, auto: null, aplus: null, added_at: null, org: ORG(group), ...o };
}
/** 👤 H1 · 🎯 AP1 · 🤖 AU1 · ✅ R1 · ⛔🩳🔒 S1 S2 — interleaved on purpose (S1 R1 H1 S2 AU1 AP1). */
function mixedRaw(): any {
  const b = clone(RAW);
  b.rows = [
    rowRaw('S1', 'sissr', { auto: AUTO('sissr') }), rowRaw('R1', 'rules', { auto: AUTO('rules') }),
    rowRaw('H1', 'yours'), rowRaw('S2', 'sissr', { auto: AUTO('sissr') }),
    rowRaw('AU1', 'auto', { auto: AUTO('potential') }),
    rowRaw('AP1', 'aplus', { auto: AUTO('aplus'), aplus: APLUS }),
  ];
  return b;
}

describe('⛔🩳🔒 the served marker', () => {
  it('GGW_SISSR_WHY is the served "sissr"; the golden ⛔🩳🔒 rows read true, every other row false', () => {
    expect(GGW_SISSR_WHY).toBe('sissr');
    expect(GGW_SISSR_WHY).not.toBe(GGW_RULES_WHY);
    const b = gb();
    const by = (s: string) => b.rows.find((r) => r.symbol === s)!;
    for (const s of ['AKAN', 'GMEX']) { expect(ggwIsSissrRow(by(s))).toBe(true); expect(ggwIsRulesRow(by(s))).toBe(false); }
    for (const s of ['OMH', 'NVDA', 'AAA', 'MMM', 'ZZT', 'RON']) expect(ggwIsSissrRow(by(s))).toBe(false);
    expect(b.rows.filter(ggwIsSissrRow).map((r) => r.org?.group)).toEqual(['sissr', 'sissr']);
  });
  it('NEGATIVE: a junk why ("SISSR", " sissr", "sissr ", 3, null, absent) → NOT ⛔🩳🔒 — an ordinary 🤖 row', () => {
    for (const junk of ['SISSR', ' sissr', 'sissr ', 3, null, undefined]) {
      const raw = mixedRaw();
      const auto: any = { tag: '🤖', text: 'served-auto-junk' };
      if (junk !== undefined) auto.why = junk;
      raw.rows[0] = rowRaw('S1', 'sissr', { auto });
      const b = gb(raw);
      const r = b.rows.find((x) => x.symbol === 'S1')!;
      expect(ggwIsSissrRow(r)).toBe(false);
      expect(ggwJoinable(r)).toBe(false);                                         // a 🤖 potential never joins either
      /* treated as 🤖: it rides with 👤 / 🎯 / 🤖 in served order, before ✅ and the real ⛔🩳🔒 row */
      expect(ggwLiveSymbols(b)).toEqual(['S1', 'H1', 'AU1', 'AP1', 'R1', 'S2']);
    }
  });
  it('NEGATIVE: his row (auto null) is never ⛔🩳🔒', () => {
    expect(ggwIsSissrRow({ auto: null })).toBe(false);
    expect(ggwIsSissrRow({})).toBe(false);
  });
});

describe('⛔🩳🔒 his pick: a ⛔🩳🔒 row NEVER joins (verifier HIGH)', () => {
  const S = (): GgwRow => gb().rows.find((r) => r.symbol === 'AKAN')!;
  it('ggwJoinable false — with and without a served aplus block, and even with why "aplus"-like fields elsewhere', () => {
    const r = S();
    expect(ggwJoinable(r)).toBe(false);
    expect(ggwJoinable({ ...r, aplus: APLUS })).toBe(false);
    /* POS controls on the same golden: his names and the 🎯 A+ seat still join; 🤖 / ✅ do not */
    const b = gb();
    const j = Object.fromEntries(b.rows.map((x) => [x.symbol, ggwJoinable(x)]));
    expect(j).toEqual({ OMH: true, NVDA: true, AAA: true, MMM: false, ZZT: false, RON: false, AKAN: false, GMEX: false });
  });
  it('NEGATIVE (mutation guard): the same row with why "potential" + aplus WOULD join — so the ⛔🩳🔒 check is what refuses it', () => {
    const r = S();
    const asPotential: GgwRow = { ...r, auto: { ...r.auto!, why: 'potential' }, aplus: APLUS };
    expect(ggwJoinable(asPotential)).toBe(true);
    expect(ggwJoinable({ ...asPotential, auto: { ...asPotential.auto!, why: GGW_SISSR_WHY } })).toBe(false);
  });
  it('NEGATIVE: a ⛔🩳🔒 row (aplus served, just added, unseen) is never fresh, never ggwUnseenOwn; its join bit is 0', () => {
    const raw = G();
    for (const r of raw.rows) r.added_at = '2026-11-13T19:31:00Z';
    for (const r of raw.rows) if (r.auto?.why === 'sissr') r.aplus = clone(APLUS);
    const b = gb(raw);
    const fresh = ggwFreshNames(b.rows, { seen: [], pickAt: null, nowMs: Date.parse('2026-11-13T19:32:00Z') });
    expect(fresh).toEqual(['OMH', 'NVDA', 'AAA']);
    expect(ggwUnseenOwn(b.rows.filter(ggwIsSissrRow), [])).toBeNull();
    expect(ggwRowsKey(b.rows.filter(ggwIsSissrRow))).toMatch(/^AKAN@[^@|]*@0\|GMEX@[^@|]*@0\|$/);
  });
});

describe('⛔🩳🔒 the live list: 👤 / 🎯 / 🤖 → ✅ → ⛔🩳🔒 (verifier HIGH)', () => {
  it('interleaved served rows → the rest in served order, then ✅, then ⛔🩳🔒', () => {
    expect(ggwLiveSymbols(gb(mixedRaw()))).toEqual(['H1', 'AU1', 'AP1', 'R1', 'S1', 'S2']);
  });
  it('the golden: OMH NVDA AAA MMM ZZT → RON → AKAN GMEX', () => {
    expect(ggwLiveSymbols(gb())).toEqual(['OMH', 'NVDA', 'AAA', 'MMM', 'ZZT', 'RON', 'AKAN', 'GMEX']);
  });
  it('a ⛔🩳🔒 row served BEFORE ✅ still posts after it', () => {
    const raw = G();
    const i = raw.rows.findIndex((r: any) => r.symbol === 'GMEX');
    const [gm] = raw.rows.splice(i, 1);
    raw.rows.unshift(gm);
    expect(ggwLiveSymbols(gb(raw))).toEqual(['OMH', 'NVDA', 'AAA', 'MMM', 'ZZT', 'RON', 'GMEX', 'AKAN']);
  });
  it('NEGATIVE: no ⛔🩳🔒 row → exactly the 11-24 list (✅ golden, and the 11-15 board)', () => {
    const r = parseGgw(clone(goldRules as any)) as GgwBoard;
    const rest = r.rows.filter((x) => !ggwIsRulesRow(x)).map((x) => x.symbol);
    expect(ggwLiveSymbols(r)).toEqual([...rest, ...r.rows.filter(ggwIsRulesRow).map((x) => x.symbol)]);
    const old = parseGgw(clone(RAW)) as GgwBoard;
    expect(ggwLiveSymbols(old)).toEqual(old.rows.map((x) => x.symbol));
  });
  it('past the hub cap of 80: every 👤/🎯/🤖 and ✅ name comes before any ⛔🩳🔒 — the refused tail is ⛔🩳🔒 first', () => {
    const b = clone(RAW);
    const mk = (n: number, pre: string, group: string, auto: any) =>
      Array.from({ length: n }, (_x, i) => rowRaw(`${pre}${i}`, group, { auto }));
    const s = mk(30, 'S', 'sissr', AUTO('sissr'));
    const r = mk(40, 'R', 'rules', AUTO('rules'));
    const o = [...mk(5, 'H', 'yours', null), ...mk(15, 'A', 'auto', AUTO('potential'))];
    b.rows = [...s.slice(0, 15), ...o.slice(0, 10), ...r.slice(0, 20), ...s.slice(15), ...o.slice(10), ...r.slice(20)];
    const live = ggwLiveSymbols(gb(b));
    expect(live).toHaveLength(90);
    expect(live.slice(0, 20).every((x) => /^[HA]/.test(x))).toBe(true);
    expect(live.slice(20, 60).every((x) => x.startsWith('R'))).toBe(true);
    expect(live.slice(60).every((x) => x.startsWith('S'))).toBe(true);
    expect(live.slice(80).every((x) => x.startsWith('S'))).toBe(true);
  });
  it('phone: ✅ and ⛔🩳🔒 folded → neither posts; ⛔🩳🔒 opened alone → it posts last; both open → ✅ then ⛔🩳🔒', () => {
    const b = gb();
    expect(Array.from(ggwLiveSkip(b.sections, [], [])).sort()).toEqual(['rules', 'sissr']);
    expect(ggwLiveSymbols(b, ggwLiveSkip(b.sections, [], []))).toEqual(['OMH', 'NVDA', 'AAA', 'MMM', 'ZZT']);
    expect(ggwLiveSymbols(b, ggwLiveSkip(b.sections, [], ['sissr']))).toEqual(['OMH', 'NVDA', 'AAA', 'MMM', 'ZZT', 'AKAN', 'GMEX']);
    expect(ggwLiveSymbols(b, ggwLiveSkip(b.sections, [], ['rules', 'sissr'])))
      .toEqual(['OMH', 'NVDA', 'AAA', 'MMM', 'ZZT', 'RON', 'AKAN', 'GMEX']);
  });
});

describe('⛔🩳🔒 the head counts (parsed only, keyed only when served)', () => {
  it('the golden head keeps sissr_n / sissr_not_eligible_n', () => {
    expect(gb().rules).toEqual({ state: 'ok', n: 1, keep_sessions: 5, text: null, not_seated_n: 1, sissr_n: 2, sissr_not_eligible_n: 2 });
  });
  it('NEGATIVE: absent → no key (the 11-24 head byte-equal); junk / negative / NaN → null', () => {
    const h = parseRulesHead({ state: 'ok', n: 2, keep_sessions: 5, text: null, not_seated_n: 0 })!;
    expect('sissr_n' in h).toBe(false);
    expect('sissr_not_eligible_n' in h).toBe(false);
    /* the ✅ golden (re-written by be-watch) serves the counts as 0 → kept as 0, never dropped */
    const cur = parseGgw(clone(goldRules as any)) as GgwBoard;
    expect(cur.rules?.sissr_n).toBe(0);
    expect(cur.rules?.sissr_not_eligible_n).toBe(0);
    for (const junk of [-1, NaN, 'x', null, {}, []]) {
      const j = parseRulesHead({ state: 'ok', sissr_n: junk, sissr_not_eligible_n: junk })!;
      expect(j.sissr_n).toBeNull();
      expect(j.sissr_not_eligible_n).toBeNull();
    }
    expect(parseRulesHead({ sissr_n: 2 })).toBeNull();                          // no served state → no head at all
  });
});

describe('⛔🩳🔒 sections on the BE golden (be-watch writes it)', () => {
  it('⛔🩳🔒 is served right after ✅, both folded by default; its header sits at the first ⛔🩳🔒 row', () => {
    const b = gb();
    const keys = (b.sections ?? []).map((s) => s.key);
    expect(keys.indexOf('sissr')).toBe(keys.indexOf('rules') + 1);
    expect(ggwDefaultFolded(b.sections)).toEqual(['rules', 'sissr']);
    const starts = ggwGroupStarts(b.rows, b.sections);
    expect(starts.map((g) => g.section.key)).toEqual(['yours', 'aplus', 'auto', 'rules', 'sissr']);
    expect(b.rows[starts[4].at].symbol).toBe('AKAN');
    expect(starts[4].section.text).toBe((G().sections as any[]).find((s) => s.key === 'sissr').text);
  });
  it('a tap opens ⛔🩳🔒 through `opened`; a reveal of AKAN opens it; ✅ untouched', () => {
    const b = gb();
    expect(ggwToggleFold(b.sections, { collapsed: [], opened: [] }, 'sissr')).toEqual({ collapsed: [], opened: ['sissr'] });
    expect(ggwFoldedKeys(b.sections, [], ['sissr'])).toEqual(['rules']);
    expect(ggwRevealOpened([], b.sections, b.rows, 'AKAN')).toEqual(['sissr']);
    const o: string[] = ['sissr'];
    expect(ggwRevealOpened(o, b.sections, b.rows, 'GMEX')).toBe(o);
  });
  it('NEGATIVE: an empty ⛔🩳🔒 section (served, no rows) draws no header; not served → none either', () => {
    const raw = G();
    raw.rows = raw.rows.filter((r: any) => r.auto?.why !== 'sissr');
    raw.sections.find((s: any) => s.key === 'sissr').n = 0;
    raw.sections.find((s: any) => s.key === 'sissr').symbols = [];
    const b = gb(raw);
    expect(ggwGroupStarts(b.rows, b.sections).map((g) => g.section.key)).not.toContain('sissr');
    raw.sections = raw.sections.filter((s: any) => s.key !== 'sissr');
    const b2 = gb(raw);
    expect(ggwGroupStarts(b2.rows, b2.sections).map((g) => g.section.key)).not.toContain('sissr');
  });
});

describe('⛔🩳🔒 source guards on the lib', () => {
  async function src(): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/src/lib/gajjalaWatch.ts`, 'utf8');
  }
  const block = (s: string): string => {
    const a = s.indexOf('// ── ⛔🩳🔒 potentials');
    const b = s.indexOf('// ── end ⛔🩳🔒 ──');
    expect(a).toBeGreaterThan(0);
    expect(b).toBeGreaterThan(a);
    return s.slice(a, b);
  };
  const literals = (code: string): string[] =>
    (code.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '').match(/'[^'\n]*'|"[^"\n]*"|`[^`]*`/g) ?? []);
  it('NEGATIVE: the new block types no word literal — its only literal is the served key', async () => {
    const lits = literals(block(await src()));
    expect(lits).toEqual(["'sissr'"]);
    for (const l of lits) expect(l).not.toMatch(/SSR|[Ss]hort|[Cc]lose-out|[Bb]ounce/);
    /* the guard bites: a typed word would fail */
    expect(literals("const x = 'SSR day';")[0]).toMatch(/SSR/);
  });
  it('NEGATIVE: no admin email in the lib', async () => {
    const s = await src();
    expect(s).not.toContain('@gmail');
    expect(s).not.toMatch(/[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}/);
  });
});
