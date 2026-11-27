/* 🧘 lib/ggLike — strict parsers, the display-filter split, the count / label / line templates, the one LS key
 * (2026-11-27, spec gglike §3.9, WP fe-core). Strings are stand-ins shaped like the served ones (spec §3.5). */
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  GG_LIKE_LS, GG_LIKE_VERDICTS, ggLikeCount, ggLikeLabel, ggLikeLine, ggLikeSplit, loadGgLikeOnly, parseGgLike,
  parseGgLikeBoard, saveGgLikeOnly,
} from './ggLike';
import type { GgLike, GgLikeBoard, GgLikeSplit } from './ggLike';

const NOT = {
  verdict: 'not', tone: 'no', chip: '🧘 23% under high +2', title: 'served title DKI',
  reason: { code: 'near_high', label: '23% under high' }, keep: false,
  checks: [
    { key: 'base_bars', ok: true, info: false, mark: '✓', label: 'served base label', value: '9 bars', need: '4 or more' },
    { key: 'near_high', ok: false, info: false, mark: '✗', label: 'served high label', value: '22.7% under 1.67', need: 'within 15%' },
    { key: 'lower_highs', ok: null, info: true, mark: 'ⓘ', label: 'served info label', value: 'served few swings', need: null },
  ],
  info: null, source: 'read', source_text: null,
};
const served = (over: Record<string, unknown> = {}) => ({ ...JSON.parse(JSON.stringify(NOT)), ...over });

const BOARD = {
  label: '🧘 L', label_n_text: '{label} · {n}', hint: 'served hint',
  hidden_text: '{n} hidden', reason_text: '{n} {label}', kept_text: '{n} kept-served', unknown_text: '{n} unknown-served',
  none_text: '{n} none-served', all_hidden_text: 'ALL-HIDDEN-SERVED', show_all_text: 'show-all-served',
  note: 'note-served', separation_text: 'sep-served', census_text: 'census-served', rows: ['r1', 'r2'], source: 'READ.md',
};
const board = (over: Record<string, unknown> = {}) => parseGgLikeBoard({ ...BOARD, ...over }) as GgLikeBoard;

type Row = { symbol: string; gg?: unknown };
const of = (r: Row) => parseGgLike(r.gg);
const like = (sym: string, verdict: string, code?: string, label?: string, keep?: unknown): Row => ({
  symbol: sym,
  gg: served({ verdict, tone: verdict === 'gg_like' ? 'ok' : verdict === 'not' ? 'no' : 'unknown',
    reason: code ? { code, label } : null, ...(keep === undefined ? {} : { keep }) }),
});

describe('parseGgLike — strict', () => {
  it('accepts the served shape verbatim', () => {
    const p = parseGgLike(served())!;
    expect(p.verdict).toBe('not');
    expect(p.tone).toBe('no');
    expect(p.chip).toBe(NOT.chip);
    expect(p.title).toBe(NOT.title);
    expect(p.reason).toEqual({ ...NOT.reason, count_label: null });
    expect(p.keep).toBe(false);
    expect(p.checks).toHaveLength(3);
    expect(p.checks[2]).toEqual({ key: 'lower_highs', ok: null, info: true, mark: 'ⓘ', label: 'served info label', value: 'served few swings', need: null });
    expect(p.source).toBe('read');
    expect(p.source_text).toBeNull();
  });

  it('keep is true only for a literal true', () => {
    expect(parseGgLike(served({ keep: true }))!.keep).toBe(true);
    for (const k of ['true', 1, 'yes', {}, null, undefined]) expect(parseGgLike(served({ keep: k }))!.keep, String(k)).toBe(false);
  });

  it('every served verdict parses; GG_LIKE_VERDICTS is exactly the three', () => {
    expect([...GG_LIKE_VERDICTS]).toEqual(['gg_like', 'not', 'unknown']);
    for (const v of GG_LIKE_VERDICTS) expect(parseGgLike(served({ verdict: v }))!.verdict).toBe(v);
  });

  it('NEGATIVE: a foreign verdict, an empty / missing chip, a non-object → null', () => {
    for (const v of ['GG_LIKE', 'pass', '', null, 1]) expect(parseGgLike(served({ verdict: v })), String(v)).toBeNull();
    for (const c of ['', '   ', null, 3]) expect(parseGgLike(served({ chip: c })), String(c)).toBeNull();
    const noChip = served(); delete noChip.chip;
    expect(parseGgLike(noChip)).toBeNull();
    for (const x of [null, undefined, 'not', 3, [], [served()]]) expect(parseGgLike(x)).toBeNull();
  });

  it('NEGATIVE: malformed check rows are dropped, info is true only for a literal true, ok only true / false / null', () => {
    const p = parseGgLike(served({ checks: [
      { key: 'a', ok: 'yes', label: 'L' }, { key: '', ok: true, label: 'L' }, { key: 'b', ok: true, label: '' }, 'row', null,
      { key: 'c', ok: false, info: 'true', mark: '✗', label: 'L', value: 3, need: 'n' },
    ] }))!;
    expect(p.checks).toEqual([{ key: 'c', ok: false, info: false, mark: '✗', label: 'L', value: null, need: 'n' }]);
    expect(parseGgLike(served({ checks: 'x' }))!.checks).toEqual([]);
  });

  it('NEGATIVE: a half reason → null reason; a foreign tone draws the muted tone', () => {
    expect(parseGgLike(served({ reason: { code: 'near_high' } }))!.reason).toBeNull();
    expect(parseGgLike(served({ reason: 'near_high' }))!.reason).toBeNull();
  });

  it('reason.count_label: a served non-blank string is carried; NEGATIVE: blank / non-string / missing → null', () => {
    const r = (count_label: unknown) => parseGgLike(served({ reason: { code: 'near_high', label: '23% under high', count_label } }))!.reason;
    expect(r('served under-high')).toEqual({ code: 'near_high', label: '23% under high', count_label: 'served under-high' });
    for (const bad of ['', '  ', 3, null, undefined, { x: 1 }]) expect(r(bad)!.count_label, String(bad)).toBeNull();
    expect(r(3)!.label).toBe('23% under high');
    expect(parseGgLike(served({ tone: 'red' }))!.tone).toBe('unknown');
    expect(parseGgLike(served({ tone: 'ok' }))!.tone).toBe('ok');
  });
});

describe('parseGgLikeBoard — strict', () => {
  it('accepts the served shape; rows keep only non-blank strings', () => {
    const b = parseGgLikeBoard({ ...BOARD, rows: ['r1', 2, '', 'r2'] })!;
    expect(b.label).toBe('🧘 L');
    expect(b.rows).toEqual(['r1', 'r2']);
    expect(b.separation_text).toBe('sep-served');
    expect(b.census_text).toBe('census-served');
    expect(b.all_hidden_text).toBe('ALL-HIDDEN-SERVED');
  });

  it('NEGATIVE: no label, a missing count template or a non-object → null', () => {
    expect(parseGgLikeBoard({ ...BOARD, label: '' })).toBeNull();
    for (const k of ['hidden_text', 'reason_text', 'kept_text', 'unknown_text', 'none_text', 'show_all_text']) {
      const b: Record<string, unknown> = { ...BOARD }; delete b[k];
      expect(parseGgLikeBoard(b), k).toBeNull();
    }
    for (const x of [null, 'b', 1, [BOARD]]) expect(parseGgLikeBoard(x)).toBeNull();
  });
});

describe('ggLikeSplit', () => {
  const rows: Row[] = [
    like('A', 'not', 'base_bars', '1-bar base'),
    like('B', 'gg_like'),
    like('C', 'unknown'),
    { symbol: 'D' },
    like('E', 'not', 'near_high', '23% under high'),
    like('F', 'not', 'base_bars', '1-bar base'),
    { symbol: 'G', gg: { verdict: 'weird', chip: 'x' } },
  ];

  it('OFF → every row in place, zero counts, like still counted', () => {
    const s = ggLikeSplit(rows, of, false);
    expect(s.visible.map((r) => r.symbol)).toEqual(['A', 'B', 'C', 'D', 'E', 'F', 'G']);
    expect(s.visible).not.toBe(rows);
    expect({ hidden: s.hidden, kept: s.kept, unknown: s.unknown, none: s.none, reasons: s.reasons }).toEqual(
      { hidden: 0, kept: 0, unknown: 0, none: 0, reasons: [] });
    expect(s.like).toBe(1);
  });

  it('ON → only un-kept not rows leave, order kept; unknown and no-block rows stay and are counted apart', () => {
    const s = ggLikeSplit(rows, of, true);
    expect(s.visible.map((r) => r.symbol)).toEqual(['B', 'C', 'D', 'G']);
    expect(s.hidden).toBe(3);
    expect(s.unknown).toBe(1);
    expect(s.none).toBe(2);
    expect(s.like).toBe(1);
    expect(s.kept).toBe(0);
  });

  it('reasons: hidden rows by code, most first, ties by label', () => {
    const s = ggLikeSplit(rows, of, true);
    expect(s.reasons).toEqual([{ code: 'base_bars', label: '1-bar base', n: 2 }, { code: 'near_high', label: '23% under high', n: 1 }]);
    const tie = ggLikeSplit([like('X', 'not', 'z', 'zz'), like('Y', 'not', 'a', 'aa')], of, true);
    expect(tie.reasons.map((r) => r.label)).toEqual(['aa', 'zz']);
  });

  const lie = (sym: string, code: string, label: string, count_label?: unknown): Row => ({
    symbol: sym,
    gg: served({ reason: { code, label, ...(count_label === undefined ? {} : { count_label }) } }),
  });

  it('[refix] one code, three numbers, served count_label → counted once under the per-code label (no card number)', () => {
    const r = [lie('A', 'near_high', '23% under high', 'CL-high'), lie('B', 'near_high', '51% under high', 'CL-high'),
      lie('C', 'near_high', '16% under high', 'CL-high'), lie('D', 'base_bars', '1-bar base', 'CL-base'),
      lie('E', 'base_bars', '3-bar base', 'CL-base')];
    const s = ggLikeSplit(r, of, true);
    expect(s.reasons).toEqual([{ code: 'near_high', label: 'CL-high', n: 3 }, { code: 'base_bars', label: 'CL-base', n: 2 }]);
    expect(ggLikeLine(board(), s)).toBe('ALL-HIDDEN-SERVED · 5 hidden (3 CL-high · 2 CL-base)');
  });

  it('[refix] NEGATIVE: no count_label → never prints one card\'s number for another (the spec defect input)', () => {
    const r = [lie('A', 'near_high', '23% under high'), lie('B', 'near_high', '51% under high'),
      lie('C', 'near_high', '16% under high'), lie('D', 'base_bars', '1-bar base'), lie('E', 'base_bars', '3-bar base')];
    const s = ggLikeSplit(r, of, true);
    const line = ggLikeLine(board(), s);
    expect(line).not.toContain('3 23% under high');
    expect(line).not.toContain('2 1-bar base');
    expect(s.reasons.every((x) => x.n === 1)).toBe(true);
    expect(s.reasons.reduce((a, x) => a + x.n, 0)).toBe(s.hidden);
    for (const x of s.reasons) expect(r.filter((t) => of(t)!.reason!.label === x.label)).toHaveLength(x.n);
  });

  it('[refix] same code, same served label, no count_label → still one group (identical labels never split)', () => {
    const s = ggLikeSplit([lie('X', 'base_bars', '1-bar base'), lie('Y', 'base_bars', '1-bar base')], of, true);
    expect(s.reasons).toEqual([{ code: 'base_bars', label: '1-bar base', n: 2 }]);
  });

  it('[refix] NEGATIVE: two codes serving the same count_label stay two groups (the code is part of the key)', () => {
    const s = ggLikeSplit([lie('X', 'near_high', 'a', 'SAME'), lie('Y', 'ema_hold', 'b', 'SAME')], of, true);
    expect(s.reasons.map((x) => x.code).sort()).toEqual(['ema_hold', 'near_high']);
  });

  it('[refix] NEGATIVE: a blank count_label falls back to the exact label, never merges different numbers', () => {
    const s = ggLikeSplit([lie('X', 'near_high', '23% under high', ' '), lie('Y', 'near_high', '51% under high', '')], of, true);
    expect(s.reasons.map((x) => x.label).sort()).toEqual(['23% under high', '51% under high']);
  });

  it('NEGATIVE: unknown is never in hidden or reasons', () => {
    const s = ggLikeSplit([like('U', 'unknown', 'near_high', 'x'), like('V', 'unknown')], of, true);
    expect(s.hidden).toBe(0);
    expect(s.reasons).toEqual([]);
    expect(s.unknown).toBe(2);
    expect(s.visible).toHaveLength(2);
  });

  it('[C1] a ✗ row served keep:true stays; a ✗ row the keep callback names stays; both counted kept, never hidden', () => {
    const r = [like('R', 'not', 'near_high', 'h', true), like('FOC', 'not', 'base_bars', 'b'), like('Z', 'not', 'ema_hold', 'e')];
    const s = ggLikeSplit(r, of, true, (t) => t.symbol === 'FOC');
    expect(s.visible.map((t) => t.symbol)).toEqual(['R', 'FOC']);
    expect(s.kept).toBe(2);
    expect(s.hidden).toBe(1);
    expect(s.reasons).toEqual([{ code: 'ema_hold', label: 'e', n: 1 }]);
  });

  it('[C1] NEGATIVE: a ✗ row with keep:false and no callback hit is hidden; a non-true keep never keeps', () => {
    for (const k of [false, 'true', 1, null]) {
      const s = ggLikeSplit([like('Z', 'not', 'near_high', 'h', k)], of, true, (t) => t.symbol === 'OTHER');
      expect(s.visible, String(k)).toEqual([]);
      expect(s.hidden).toBe(1);
      expect(s.kept).toBe(0);
    }
    const truthy = ggLikeSplit([like('Z', 'not', 'near_high', 'h')], of, true, (() => 1) as unknown as () => boolean);
    expect(truthy.hidden).toBe(1);
  });

  it('NEGATIVE: kept rows are never counted hidden or in reasons; gg_like rows are never kept', () => {
    const s = ggLikeSplit([like('K', 'not', 'near_high', 'h', true), like('G', 'gg_like', undefined, undefined, true)], of, true);
    expect(s.hidden).toBe(0);
    expect(s.reasons).toEqual([]);
    expect(s.kept).toBe(1);
  });

  it('a not row with no served reason is hidden and adds no reason', () => {
    const s = ggLikeSplit([like('N', 'not')], of, true);
    expect(s.hidden).toBe(1);
    expect(s.reasons).toEqual([]);
  });
});

describe('ggLikeCount / ggLikeLabel', () => {
  it('counts gg_like only', () => {
    expect(ggLikeCount([like('A', 'gg_like'), like('B', 'not', 'x', 'y'), like('C', 'unknown'), { symbol: 'D' }, like('E', 'gg_like')], of)).toBe(2);
  });
  it('NEGATIVE: a board of ✗ / unknown / no-block cards counts 0', () => {
    expect(ggLikeCount([like('B', 'not', 'x', 'y'), like('C', 'unknown'), { symbol: 'D' }], of)).toBe(0);
    expect(ggLikeCount([], of)).toBe(0);
  });
  it('fills the served template; a missing template falls back to the label', () => {
    expect(ggLikeLabel(board(), 0)).toBe('🧘 L · 0');
    expect(ggLikeLabel(board(), 6)).toBe('🧘 L · 6');
    expect(ggLikeLabel(board({ label_n_text: null }), 6)).toBe('🧘 L');
    expect(ggLikeLabel(board({ label_n_text: '  ' }), 6)).toBe('🧘 L');
  });
});

describe('ggLikeLine', () => {
  const split = (o: Partial<GgLikeSplit<unknown>>): GgLikeSplit<unknown> =>
    ({ visible: [1], hidden: 0, kept: 0, like: 0, reasons: [], unknown: 0, none: 0, ...o });

  it('the served parts in order: hidden (reasons), kept, unknown, none', () => {
    const s = split({ hidden: 5, kept: 2, unknown: 4, none: 1,
      reasons: [{ code: 'b', label: '1-bar base', n: 3 }, { code: 'h', label: '23% under high', n: 2 }] });
    expect(ggLikeLine(board(), s)).toBe('5 hidden (3 1-bar base · 2 23% under high) · 2 kept-served · 4 unknown-served · 1 none-served');
  });

  it('every zero part is dropped; nothing hidden → no hidden part', () => {
    expect(ggLikeLine(board(), split({ unknown: 1 }))).toBe('1 unknown-served');
    expect(ggLikeLine(board(), split({ kept: 1 }))).not.toMatch(/hidden/);
    expect(ggLikeLine(board(), split({}))).toBe('');
  });

  it('[C3] every row hidden → the line STARTS with all_hidden_text', () => {
    const s = split({ visible: [], hidden: 2, reasons: [{ code: 'h', label: 'x', n: 2 }] });
    expect(ggLikeLine(board(), s)).toBe('ALL-HIDDEN-SERVED · 2 hidden (2 x)');
    expect(ggLikeLine(board(), s).startsWith(BOARD.all_hidden_text)).toBe(true);
  });

  it('NEGATIVE: all_hidden_text only when nothing is visible AND something is hidden', () => {
    expect(ggLikeLine(board(), split({ visible: [1], hidden: 2 }))).not.toContain(BOARD.all_hidden_text);
    expect(ggLikeLine(board(), split({ visible: [], hidden: 0 }))).not.toContain(BOARD.all_hidden_text);
    expect(ggLikeLine(board({ all_hidden_text: null }), split({ visible: [], hidden: 1 }))).toBe('1 hidden');
  });

  it('an OFF split prints nothing', () => {
    expect(ggLikeLine(board(), ggLikeSplit([like('A', 'not', 'x', 'y'), like('B', 'unknown')], of, false))).toBe('');
  });
});

function mem(init: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries(init));
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(),
  };
}

describe('localStorage — ONE key, only "1" is ON', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('GG_LIKE_LS has exactly one key (the board); no Watch key', () => {
    expect(Object.keys(GG_LIKE_LS)).toEqual(['board']);
    expect(GG_LIKE_LS.board).toBe('gg-like-only:board');
    expect(JSON.stringify(GG_LIKE_LS)).not.toMatch(/watch/i);
  });

  it('only "1" is ON; save writes 1 / 0 and round-trips', () => {
    const store = mem({ [GG_LIKE_LS.board]: '1' });
    vi.stubGlobal('localStorage', store);
    const k = GG_LIKE_LS.board;
    expect(loadGgLikeOnly(k)).toBe(true);
    saveGgLikeOnly(k, false);
    expect(store.getItem(k)).toBe('0');
    expect(loadGgLikeOnly(k)).toBe(false);
    saveGgLikeOnly(k, true);
    expect(store.getItem(k)).toBe('1');
    expect(loadGgLikeOnly(k)).toBe(true);
  });

  it('NEGATIVE: "true", "0", "", absent and blocked storage → OFF; a blocked save does not throw', () => {
    const k = GG_LIKE_LS.board;
    for (const v of ['true', '0', '', ' 1', 'on']) {
      vi.stubGlobal('localStorage', mem({ [k]: v }));
      expect(loadGgLikeOnly(k), v).toBe(false);
    }
    vi.stubGlobal('localStorage', mem());
    expect(loadGgLikeOnly(k)).toBe(false);
    vi.stubGlobal('localStorage', {
      getItem: () => { throw new Error('blocked'); },
      setItem: () => { throw new Error('blocked'); },
    });
    expect(loadGgLikeOnly(k)).toBe(false);
    expect(() => saveGgLikeOnly(k, true)).not.toThrow();
    vi.stubGlobal('localStorage', undefined);
    expect(loadGgLikeOnly(k)).toBe(false);
    expect(() => saveGgLikeOnly(k, true)).not.toThrow();
  });
});

/* type-level: a null input parses to a null block */
const _t: GgLike | null = parseGgLike(null);
void _t;
