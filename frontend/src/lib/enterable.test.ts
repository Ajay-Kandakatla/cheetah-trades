import { describe, it, expect } from 'vitest';
import {
  blockReasons,
  enterableChipText,
  isShown,
  mergeReasonStats,
  partitionEnterable,
  measuredStatusWords,
  topHiddenReasons,
  UNLABELLED_REASON,
  type EnterableRead,
} from './enterable';
import { ENTERABLE_KIND } from './chartMaps';

/* 🎯 ENTERABLE — the frontend half of one read (2026-09-15).
 *
 * The partition and the tab→kind map are pinned against the SAME file the
 * backend test reads, backend/tests/fixtures/enterable_mirror_2026_09_15.json.
 * Edit the fixture, both suites fail — which is the point: a filter that is ON
 * by default must hide the same rows on both sides of the wire.
 *
 * The negatives carry the weight here, because every way this feature can hurt
 * him is an ABSENCE: a row with no read must never be hidden, a disabled filter
 * must return the board untouched, and the chip must render NOTHING rather than
 * imply a verdict nobody served.
 */

type Fx = {
  kind_by_tab: Record<string, string>;
  rows: { symbol: string; read: EnterableRead | null }[];
  expected_shown_enterable: string[];
  expected_hidden: number;
  expected_unread: number;
  expected_hidden_by_reason: Record<string, number>;
};

async function load(): Promise<Fx> {
  const { default: raw } = await import('../../../backend/tests/fixtures/enterable_mirror_2026_09_15.json?raw');
  return JSON.parse(raw) as Fx;
}

const mapOf = (fx: Fx) =>
  new Map<string, EnterableRead | null>(fx.rows.map((r) => [r.symbol, r.read]));

const symbolOf = (r: { symbol: string }) => r.symbol;

describe('enterable partition — the shared backend fixture (2026-09-15)', () => {
  it('reproduces the served shown list, the counts and the reason breakdown', async () => {
    const fx = await load();
    const part = partitionEnterable(fx.rows, symbolOf, mapOf(fx), true);
    expect(part.rows.map((r) => r.symbol)).toEqual(fx.expected_shown_enterable);
    expect(part.hidden).toBe(fx.expected_hidden);
    expect(part.unread).toBe(fx.expected_unread);
    expect(part.hiddenByReason).toEqual(fx.expected_hidden_by_reason);
  });

  it('mirrors the backend KIND_BY_TAB key for key', async () => {
    const fx = await load();
    expect(ENTERABLE_KIND).toEqual(fx.kind_by_tab);
  });

  it('is a stable partition, not a sort — served order inside each half', async () => {
    const fx = await load();
    const part = partitionEnterable(fx.rows, symbolOf, mapOf(fx), true);
    const served = fx.rows.map((r) => r.symbol);
    const shown = part.rows.slice(0, part.rows.length - part.unread).map((r) => r.symbol);
    const unread = part.rows.slice(part.rows.length - part.unread).map((r) => r.symbol);
    const inServedOrder = (xs: string[]) =>
      xs.every((s, i) => i === 0 || served.indexOf(xs[i - 1]) < served.indexOf(s));
    expect(inServedOrder(shown)).toBe(true);
    expect(inServedOrder(unread)).toBe(true);
    // Every unread row sits after every shown row.
    expect(unread.every((u) => served.indexOf(u) >= 0)).toBe(true);
  });

  it('NEGATIVE: hides ONLY the BLOCKED rows — nothing else ever leaves the list', async () => {
    const fx = await load();
    const part = partitionEnterable(fx.rows, symbolOf, mapOf(fx), true);
    const kept = new Set(part.rows.map((r) => r.symbol));
    for (const r of fx.rows) {
      const blocked = r.read?.verdict === 'BLOCKED';
      expect(kept.has(r.symbol)).toBe(!blocked);
    }
  });

  it('NEGATIVE: every served sentence is his wording — no "bounc" anywhere', async () => {
    const fx = await load();
    for (const r of fx.rows) {
      const text = [...(r.read?.reason_text || []), ...(r.read?.reason_short || [])].join(' ');
      expect(text.toLowerCase()).not.toContain('bounc');
      const chip = enterableChipText(r.read);
      if (chip) {
        expect(`${chip.text} ${chip.title}`.toLowerCase()).not.toContain('bounc');
        expect(`${chip.text} ${chip.title}`).not.toContain('NaN');
      }
    }
  });
});

describe('partitionEnterable — the ways it must NOT lose a row', () => {
  const read = (over: Partial<EnterableRead> = {}): EnterableRead => ({
    kind: 'demand', verdict: 'READY', reasons: [], reason_text: [], reason_short: [], ...over,
  });

  it('NEGATIVE: a row with no map entry is never hidden — it is shown LAST and counted', () => {
    const rows = [{ symbol: 'AAA' }, { symbol: 'PEND' }, { symbol: 'BLK' }];
    const map = new Map<string, EnterableRead | null>([
      ['AAA', read()],
      ['BLK', read({ verdict: 'BLOCKED', reasons: ['room'], reason_short: ['room < 5%'] })],
    ]);
    const part = partitionEnterable(rows, symbolOf, map, true);
    expect(part.rows.map((r) => r.symbol)).toEqual(['AAA', 'PEND']);
    expect(part.unread).toBe(1);
    expect(part.hidden).toBe(1);
  });

  it('NEGATIVE: a read with a null verdict (the n/a kind) is unread, never hidden', () => {
    const rows = [{ symbol: 'VCPX' }];
    const map = new Map<string, EnterableRead | null>([
      ['VCPX', read({ kind: 'n/a', verdict: null, reasons: ['na'] })],
    ]);
    const part = partitionEnterable(rows, symbolOf, map, true);
    expect(part.rows).toHaveLength(1);
    expect(part.hidden).toBe(0);
    expect(part.unread).toBe(1);
  });

  it('NEGATIVE: disabled returns the board untouched with zero counts', () => {
    const rows = [{ symbol: 'AAA' }, { symbol: 'BLK' }];
    const map = new Map<string, EnterableRead | null>([
      ['AAA', read()],
      ['BLK', read({ verdict: 'BLOCKED', reason_short: ['no band'] })],
    ]);
    const part = partitionEnterable(rows, symbolOf, map, false);
    expect(part.rows.map((r) => r.symbol)).toEqual(['AAA', 'BLK']);
    expect(part).toMatchObject({ hidden: 0, unread: 0, hiddenByReason: {} });
  });

  it('NEGATIVE: a blocked row with no served reason still counts, under a neutral label', () => {
    const rows = [{ symbol: 'BLK' }];
    const map = new Map<string, EnterableRead | null>([['BLK', read({ verdict: 'BLOCKED' })]]);
    const part = partitionEnterable(rows, symbolOf, map, true);
    expect(part.hidden).toBe(1);
    expect(Object.values(part.hiddenByReason)).toEqual([1]);
  });

  it('matches symbols case-insensitively, the way every board keys its map', () => {
    const rows = [{ symbol: 'aaa' }];
    const map = new Map<string, EnterableRead | null>([['AAA', read({ verdict: 'BLOCKED', reason_short: ['no band'] })]]);
    expect(partitionEnterable(rows, symbolOf, map, true).hidden).toBe(1);
  });

  it('counts the reasons the SERVER worded them, most first', () => {
    const by = { 'no band': 22, 'room < 5%': 8, 'floor swept': 3, 'not at band': 3 };
    expect(topHiddenReasons(by)).toEqual([
      { reason: 'no band', n: 22 }, { reason: 'room < 5%', n: 8 }, { reason: 'floor swept', n: 3 },
    ]);
    expect(topHiddenReasons(null)).toEqual([]);
  });
});

describe('isShown', () => {
  const mk = (verdict: EnterableRead['verdict']): EnterableRead =>
    ({ kind: 'demand', verdict, reasons: [], reason_text: [], reason_short: [] });

  it('hides BLOCKED under the enterable mode and nothing else', () => {
    expect(isShown(mk('READY'))).toBe(true);
    expect(isShown(mk('WATCH'))).toBe(true);
    expect(isShown(mk('BLOCKED'))).toBe(false);
    expect(isShown(mk(null))).toBe(true);
    expect(isShown(null)).toBe(true);
    expect(isShown(undefined)).toBe(true);
  });

  it('NEGATIVE: mode "all" shows everything, BLOCKED included — the escape hatch', () => {
    expect(isShown(mk('BLOCKED'), 'all')).toBe(true);
    expect(isShown(null, 'all')).toBe(true);
  });
});

describe('enterableChipText', () => {
  const mk = (over: Partial<EnterableRead> = {}): EnterableRead => ({
    kind: 'demand', verdict: 'READY', reasons: [], reason_text: [], reason_short: [],
    print: { px: 100, source: 'live' }, measured: { status: 'pending' }, ...over,
  });

  it('NEGATIVE: no read renders nothing — an unknown never wears a chip', () => {
    expect(enterableChipText(null)).toBeNull();
    expect(enterableChipText(undefined)).toBeNull();
  });

  it('NEGATIVE: a read with no verdict and a real kind renders nothing', () => {
    expect(enterableChipText(mk({ verdict: null }))).toBeNull();
  });

  it('prints READY plainly', () => {
    const chip = enterableChipText(mk())!;
    expect(chip.text).toBe('🎯 READY');
    expect(chip.tone).toBe('ready');
  });

  it('prints the SERVED reason word on WATCH, verbatim', () => {
    const chip = enterableChipText(mk({
      verdict: 'WATCH', reasons: ['reclaim', 'weak_day'],
      reason_short: ['reclaim from below', 'weak day'],
      reason_text: ['closed back under the band floor first', 'down 4.2% today'],
    }))!;
    expect(chip.text).toBe('🎯 WATCH · reclaim from below');
    expect(chip.tone).toBe('watch');
    expect(chip.title).toContain('closed back under the band floor first');
    expect(chip.title).toContain('down 4.2% today');
  });

  it('prints the SERVED reason word on BLOCKED', () => {
    const chip = enterableChipText(mk({
      verdict: 'BLOCKED', reasons: ['room'], reason_short: ['room < 5%'],
      reason_text: ['3.8% to the first proven lid'],
    }))!;
    expect(chip.text).toBe('⛔ room < 5%');
    expect(chip.tone).toBe('blocked');
  });

  it('the n/a kind says so, muted, with the served sentence in the title', () => {
    const chip = enterableChipText(mk({
      kind: 'n/a', verdict: null, reasons: ['na'],
      reason_text: ['no demand read for this tab — its rows are not demand reversals'],
      reason_short: ['n/a'],
    }))!;
    expect(chip.text).toBe('n/a');
    expect(chip.tone).toBe('na');
    expect(chip.title).toContain('not demand reversals');
  });

  it('says so when the read was taken off the closed print', () => {
    const live = enterableChipText(mk())!;
    const scan = enterableChipText(mk({ print: { px: 100, source: 'scan' } }))!;
    expect(live.title).not.toContain('closed-bar read');
    expect(scan.title).toContain('closed-bar read (no live print)');
  });

  it("carries the study's status so a verdict is never read without it", () => {
    expect(enterableChipText(mk())!.title).toContain('pending');
  });

  it('NEGATIVE: falls back to the verdict word when the server sent no reason', () => {
    expect(enterableChipText(mk({ verdict: 'WATCH' }))!.text).toBe('🎯 WATCH');
    expect(enterableChipText(mk({ verdict: 'BLOCKED' }))!.text).toBe('⛔ BLOCKED');
  });

  it('NEGATIVE: never prints a number of its own — no NaN, ever', () => {
    const chip = enterableChipText(mk({
      verdict: 'BLOCKED', reason_short: ['room < 5%'],
      room: { state: 'ROOM', room_pct: null }, band: null, print: { px: null, source: 'live' },
    }))!;
    expect(`${chip.text} ${chip.title}`).not.toContain('NaN');
    expect(chip.text).toBe('⛔ room < 5%');
  });
});

/* 🎯 m6 (2026-09-15) — the chip tooltip is PROSE, so the study's status reaches
 * it in words. `measured.status` is a machine token on the wire (`no_signal`,
 * `pending`, `separates`) because the rules section, the alert-status payload
 * and both suites key off it; pasted raw at the end of an English sentence it
 * reads as a leaked identifier. Nothing is substituted or decided here — the
 * served token's own words, or the served banner headline when the surface has
 * it. The negatives: a raw token must never reach a title again, and no
 * headline may be invented when the server sent none. */
describe('enterableChipText — the study status reaches the tooltip in words (m6)', () => {
  const mk = (over: Partial<EnterableRead> = {}): EnterableRead => ({
    kind: 'demand', verdict: 'READY', reasons: [], reason_text: [], reason_short: [],
    print: { px: 100, source: 'live' }, measured: { status: 'no_signal' }, ...over,
  });

  it('NEGATIVE: the raw token never reaches the title — no underscore word at all', () => {
    const chip = enterableChipText(mk())!;
    expect(chip.title).not.toContain('no_signal');
    expect(chip.title).not.toMatch(/[A-Za-z]_[A-Za-z]/);
    expect(chip.title).toContain('no signal');
  });

  it('NEGATIVE: not one served sentence on the shared fixture carries a token', async () => {
    const fx = await load();
    for (const row of fx.rows) {
      for (const status of ['no_signal', 'pending', 'separates']) {
        const read = row.read ? ({ ...row.read, measured: { status } } as EnterableRead) : null;
        const chip = enterableChipText(read);
        if (!chip) continue;
        expect(chip.title).not.toMatch(/[A-Za-z]_[A-Za-z]/);
        expect(`${chip.text}`).not.toMatch(/[A-Za-z]_[A-Za-z]/);
      }
    }
  });

  it('prefers the SERVED banner headline when the surface holds one', () => {
    const chip = enterableChipText(mk(), {
      headline: 'MEASURED 2026-09-15: NO ENTRY TRIGGER SEPARATES — the read stays the gates that already shipped',
    })!;
    expect(chip.title).toContain('NO ENTRY TRIGGER SEPARATES');
    expect(chip.title).not.toContain('measured: no signal');
  });

  it('NEGATIVE: an empty or absent headline falls back to the served words, never to invented prose', () => {
    expect(enterableChipText(mk(), { headline: '   ' })!.title).toContain('measured: no signal');
    expect(enterableChipText(mk(), null)!.title).toContain('measured: no signal');
    expect(enterableChipText(mk({ measured: null }))!.title).toBe('');
  });

  it('NEGATIVE: measuredStatusWords invents nothing for an absent status', () => {
    expect(measuredStatusWords(null)).toBe('');
    expect(measuredStatusWords(undefined)).toBe('');
    expect(measuredStatusWords('  ')).toBe('');
    expect(measuredStatusWords('no_signal')).toBe('measured: no signal');
    expect(measuredStatusWords('pending')).toBe('measured: pending');
  });
});

/* 🎯 UN-HIDE BY REASON (Ajay 2026-09-17: "Can you give me a toggle for the room
 * too? I am not seeing all stocks on the selected filter due to this now").
 *
 * The ignore set decides what is DRAWN and NOTHING else — no verdict is
 * computed, recomputed or overridden here. The negatives carry the weight, and
 * every one of them is about a row coming back that should not have:
 *   - a row blocked for TWO reasons stays hidden while only ONE is un-hidden,
 *     or the count line lies about what he is looking at;
 *   - a BLOCKED row the backend named nothing for, or labelled nothing for, can
 *     never be un-hidden at all — un-hiding is explicit, never silent;
 *   - a row with no read is never hidden and never un-hidden;
 *   - the chip order never moves under his cursor, and at an empty ignore set
 *     it is byte-for-byte today's line.
 */
describe('un-hide by reason (2026-09-17)', () => {
  const blocked = (codes: string[], shorts: string[]): EnterableRead => ({
    kind: 'demand', verdict: 'BLOCKED', reasons: codes,
    reason_text: shorts.map((s) => `${s} sentence`), reason_short: shorts,
  });
  const ready = (): EnterableRead => ({
    kind: 'demand', verdict: 'READY', reasons: [], reason_text: [], reason_short: [],
  });
  const ROOM = 'room < 5%';
  const PROX = 'not at band';
  const mk = (rows: [string, EnterableRead | null][]) => ({
    rows: rows.map(([symbol]) => ({ symbol })),
    map: new Map<string, EnterableRead | null>(rows),
  });
  const part = (
    rows: [string, EnterableRead | null][],
    ignore: Iterable<string> = [],
  ) => {
    const { rows: rs, map } = mk(rows);
    return partitionEnterable(rs, symbolOf, map, true, new Set(ignore));
  };

  const BOARD: [string, EnterableRead | null][] = [
    ['R1', blocked(['room'], [ROOM])],
    ['R2', blocked(['room'], [ROOM])],
    ['PR', blocked(['proximity', 'room'], [PROX, ROOM])],
    ['NB', blocked(['no_band'], ['no band'])],
    ['OK', ready()],
    ['PEND', null],
  ];

  it('the shared backend fixture is untouched at the default empty ignore set', async () => {
    const fx = await load();
    const base = partitionEnterable(fx.rows, symbolOf, mapOf(fx), true);
    const same = partitionEnterable(fx.rows, symbolOf, mapOf(fx), true, new Set());
    expect(same.rows.map((r) => r.symbol)).toEqual(base.rows.map((r) => r.symbol));
    expect(same.rows.map((r) => r.symbol)).toEqual(fx.expected_shown_enterable);
    expect(same.hidden).toBe(fx.expected_hidden);
    expect(same.unread).toBe(fx.expected_unread);
    expect(same.hiddenByReason).toEqual(fx.expected_hidden_by_reason);
    expect(same.unhidden).toBe(0);
  });

  it('blockReasons zips the SERVED code to the SERVED label by index', () => {
    expect(blockReasons(blocked(['proximity', 'room'], [PROX, ROOM])))
      .toEqual([{ code: 'proximity', label: PROX }, { code: 'room', label: ROOM }]);
  });

  it('NEGATIVE: blockReasons is empty for READY, WATCH, n/a, null and a non-array', () => {
    expect(blockReasons(ready())).toEqual([]);
    expect(blockReasons({ ...ready(), verdict: 'WATCH', reasons: ['weak_day'], reason_short: ['weak day'] })).toEqual([]);
    expect(blockReasons({ ...ready(), kind: 'n/a', verdict: null })).toEqual([]);
    expect(blockReasons(null)).toEqual([]);
    expect(blockReasons(undefined)).toEqual([]);
    expect(blockReasons({ ...blocked([], []), reasons: undefined as unknown as string[] })).toEqual([]);
    expect(blockReasons(blocked([7 as unknown as string], [ROOM]))).toEqual([]);
  });

  it('un-hiding a single-reason code shows exactly those rows, in SERVED order', () => {
    const p = part(BOARD, ['room']);
    expect(p.rows.map((r) => r.symbol)).toEqual(['R1', 'R2', 'OK', 'PEND']);
    expect(p.unhidden).toBe(2);
    expect(p.hidden).toBe(2);
  });

  it('NEGATIVE: a row blocked for proximity AND room stays hidden on room alone', () => {
    const p = part(BOARD, ['room']);
    expect(p.rows.map((r) => r.symbol)).not.toContain('PR');
    const prox = p.reasons.find((r) => r.code === 'proximity')!;
    expect(prox.hidden).toBe(1);   // still attributed to `not at band`
    expect(p.hiddenByReason[PROX]).toBe(1);
    // …and both clicked brings it back.
    expect(part(BOARD, ['room', 'proximity']).rows.map((r) => r.symbol)).toContain('PR');
  });

  it('NEGATIVE: a row with no read is never hidden and never un-hidden', () => {
    const every = ['room', 'proximity', 'no_band', 'no_break', 'break_extended',
                   'floor_swept', 'floor_broken', 'blocked'];
    for (const ig of [[], ['room'], every]) {
      const p = part(BOARD, ig);
      expect(p.rows.map((r) => r.symbol)).toContain('PEND');
      expect(p.unread).toBe(1);
    }
  });

  it('NEGATIVE: a BLOCKED row with nothing named is never shown, under any ignore set', () => {
    const rows: [string, EnterableRead | null][] = [['X', blocked([], [])]];
    for (const ig of [[], ['room'], ['blocked']]) {
      const p = part(rows, ig);
      expect(p.rows).toHaveLength(0);
      expect(p.hidden).toBe(1);
      expect(p.hiddenByReason).toEqual({ blocked: 1 });
      const syn = p.reasons.find((r) => r.code === UNLABELLED_REASON)!;
      expect(syn.toggleable).toBe(false);
      expect(syn.hidden).toBe(1);
    }
  });

  it('NEGATIVE: a short reason_short array makes the row un-hideable, even with every code clicked', () => {
    // enterable.py builds all three arrays from ONE code list, so this can only
    // arrive from a stale or truncated cached read. It must fail CLOSED.
    const rows: [string, EnterableRead | null][] = [
      ['X', { kind: 'demand', verdict: 'BLOCKED', reasons: ['proximity', 'room'],
              reason_text: [], reason_short: [PROX] }],
    ];
    for (const ig of [[], ['room'], ['proximity'], ['proximity', 'room']]) {
      const p = part(rows, ig);
      expect(p.rows).toHaveLength(0);
      expect(p.hidden).toBe(1);
    }
    const room = part(rows).reasons.find((r) => r.code === 'room')!;
    expect(room.toggleable).toBe(false);
    expect(room.label).toBe('');
  });

  it('NEGATIVE: an empty / non-string reason_short entry is never un-hideable either', () => {
    for (const shorts of [[''], [null as unknown as string], [3 as unknown as string]]) {
      const rows: [string, EnterableRead | null][] = [
        ['X', { kind: 'demand', verdict: 'BLOCKED', reasons: ['room'], reason_text: [], reason_short: shorts }],
      ];
      const p = part(rows, ['room']);
      expect(p.rows).toHaveLength(0);
      expect(p.hiddenByReason).toEqual({ blocked: 1 });
      expect(p.hidden).toBe(p.reasons.reduce((n, r) => n + r.hidden, 0));
    }
  });

  it('NEGATIVE: an unknown SERVED code gets its own chip; an unknown ignored code is inert', () => {
    const rows: [string, EnterableRead | null][] = [['G', blocked(['gremlin'], ['gremlins'])]];
    const p = part(rows);
    expect(p.reasons.map((r) => r.code)).toEqual(['gremlin']);
    expect(part(rows, ['gremlin']).rows.map((r) => r.symbol)).toEqual(['G']);
    // A code nothing carries renders no chip and un-hides nothing.
    const inert = part(BOARD, ['not_a_code']);
    expect(inert.reasons.map((r) => r.code)).not.toContain('not_a_code');
    expect(inert.rows.map((r) => r.symbol)).toEqual(part(BOARD).rows.map((r) => r.symbol));
  });

  it('ORDER: at an empty ignore set the chips ARE today’s line, number for number', async () => {
    const fx = await load();
    const p = partitionEnterable(fx.rows, symbolOf, mapOf(fx), true);
    const today = topHiddenReasons(p.hiddenByReason, Infinity);
    expect(p.reasons.filter((r) => r.hidden > 0).map((r) => [r.hidden, r.label || UNLABELLED_REASON]))
      .toEqual(today.map((t) => [t.n, t.reason]));
    for (const r of p.reasons) expect(r.baseline).toBe(r.hidden);
  });

  it('ORDER: sorts on BASELINE, not on the rows carrying the code', () => {
    // 10 rows ["A","B"] + 1 row ["B"]: `total` would order B(11) before A(10),
    // but the line prints A 10 and B 1 — so A comes first.
    const rows: [string, EnterableRead | null][] = [
      ...Array.from({ length: 10 }, (_, i) => [`AB${i}`, blocked(['a', 'b'], ['aaa', 'bbb'])] as [string, EnterableRead]),
      ['B0', blocked(['b'], ['bbb'])],
    ];
    const p = part(rows);
    expect(p.reasons.map((r) => r.code)).toEqual(['a', 'b']);
    expect(p.reasons.map((r) => [r.code, r.total, r.baseline, r.hidden]))
      .toEqual([['a', 10, 10, 10], ['b', 11, 1, 1]]);
  });

  it('ORDER: chip order never moves under his cursor — every ignore subset, same sequence', () => {
    const rows: [string, EnterableRead | null][] = [
      ['W', blocked(['w'], ['w label'])], ['W2', blocked(['w'], ['w label'])],
      ['X', blocked(['x'], ['x label'])], ['X2', blocked(['x'], ['x label'])],
      ['Y', blocked(['y'], ['y label'])], ['Z', blocked(['z'], ['z label'])],
      ['XY', blocked(['x', 'y'], ['x label', 'y label'])],
    ];
    const codes = ['w', 'x', 'y', 'z'];
    const expected = part(rows).reasons.map((r) => r.code);
    for (let mask = 0; mask < 16; mask += 1) {
      const ig = codes.filter((_, i) => mask & (1 << i));
      expect(part(rows, ig).reasons.map((r) => r.code)).toEqual(expected);
    }
  });

  it('SUM: the printed hidden numbers always add up to the partition’s hidden count', () => {
    const rows: [string, EnterableRead | null][] = [
      ...BOARD,
      ['NOTHING', blocked([], [])],
      ['FS', blocked(['floor_swept'], ['floor swept'])],
      ['FB', blocked(['floor_broken'], ['floor broken'])],
    ];
    const codes = ['room', 'proximity', 'no_band', 'floor_swept', 'floor_broken'];
    for (let mask = 0; mask < 32; mask += 1) {
      const ig = codes.filter((_, i) => mask & (1 << i));
      const p = part(rows, ig);
      const drawn = p.reasons.filter((r) => r.hidden > 0 || r.ignored);
      expect(drawn.reduce((n, r) => n + r.hidden, 0)).toBe(p.hidden);
      expect(p.reasons.reduce((n, r) => n + r.hidden, 0)).toBe(p.hidden);
      expect(p.unhidden + p.hidden).toBe(rows.filter(([, r]) => r?.verdict === 'BLOCKED').length);
    }
  });

  it('NEGATIVE: the filter OFF returns the board untouched — no chips, even with a full ignore set', () => {
    const { rows, map } = mk(BOARD);
    const p = partitionEnterable(rows, symbolOf, map, false, new Set(['room', 'proximity', 'no_band']));
    expect(p.rows.map((r) => r.symbol)).toEqual(BOARD.map(([s]) => s));
    expect(p).toMatchObject({ hidden: 0, unread: 0, unhidden: 0, hiddenByReason: {}, reasons: [] });
  });

  it('isShown: mode "all" shows everything, ignore set or not', () => {
    const b = blocked(['room'], [ROOM]);
    expect(isShown(b, 'all')).toBe(true);
    expect(isShown(b, 'all', new Set())).toBe(true);
    expect(isShown(b, 'enterable')).toBe(false);
    expect(isShown(b, 'enterable', new Set(['room']))).toBe(true);
    expect(isShown(null, 'enterable', new Set(['room']))).toBe(true);
  });

  it('mergeReasonStats sums by code, ORs ignored, ANDs toggleable, and re-sorts', () => {
    const a = part([['R1', blocked(['room'], [ROOM])], ['N1', blocked(['no_band'], ['no band'])]]);
    const b = part([['R2', blocked(['room'], [ROOM])], ['R3', blocked(['room'], [ROOM])]]);
    const merged = mergeReasonStats([a.reasons, b.reasons]);
    expect(merged.map((r) => [r.code, r.baseline, r.hidden])).toEqual([['room', 3, 3], ['no_band', 1, 1]]);
    expect(mergeReasonStats([a.reasons])).toEqual(a.reasons);
    const on = part([['R1', blocked(['room'], [ROOM])]], ['room']);
    expect(mergeReasonStats([a.reasons, on.reasons]).find((r) => r.code === 'room')!.ignored).toBe(true);
    const nolabel = part([['X', blocked([], [])]]);
    expect(mergeReasonStats([nolabel.reasons, nolabel.reasons])
      .find((r) => r.code === UNLABELLED_REASON)!.toggleable).toBe(false);
  });

  it('the ignored chip survives at zero hidden — that is the ✓ state', () => {
    const p = part(BOARD, ['room']);
    const room = p.reasons.find((r) => r.code === 'room')!;
    expect(room).toMatchObject({ ignored: true, hidden: 0, baseline: 2, total: 3, label: ROOM });
  });
});
