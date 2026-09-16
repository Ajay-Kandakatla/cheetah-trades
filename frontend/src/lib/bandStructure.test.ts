/* 🪜 band structure — the frontend half of the mirror (2026-09-16).
 *
 * The ordering is pinned against the SAME file the backend suite sorts,
 * backend/tests/fixtures/band_structure_order_mirror_2026_09_16.json, in BOTH
 * study branches, because the two branches key on completely different things
 * (a measured score vs. the descriptive ceiling/floor order) and only one of
 * them will ever be live.
 *
 * The negatives carry the weight, as everywhere else in this codebase:
 *   • a row with no read must sort LAST and print NOTHING;
 *   • an n/a tab must be INERT — every pair compares equal, so the served
 *     order survives, and no chip appears;
 *   • `pending` must behave exactly like `no_signal`;
 *   • a missing SECOND band must SAY so and must never render as 0.
 */
import { describe, it, expect } from 'vitest';
import {
  BAND_STRUCTURE_KIND_NA,
  BAND_STRUCTURE_NA_TEXT,
  bandStructureChipText,
  bandStructureOrderKey,
  bandStructureOrderUnavailable,
  bandStructureSeparates,
  bandStructureSortNote,
  compareBandStructure,
  type BandStructureRead,
  type BandStructureStudy,
} from './bandStructure';

type Row = { symbol: string; read: BandStructureRead | null };
type Fx = { rows: Row[]; expected_separates: string[]; expected_no_signal: string[] };

/* Vite's `?raw` import (typed by src/test/vite-raw.d.ts): the file is read off
 * disk at transform time, so a jsdom `import.meta.url` and the absent
 * @types/node are both beside the point. */
async function load(): Promise<Fx> {
  const { default: raw } = await import(
    '../../../backend/tests/fixtures/band_structure_order_mirror_2026_09_16.json?raw');
  return JSON.parse(raw) as Fx;
}

describe('band-structure ordering mirror — the shared backend fixture (2026-09-16)', () => {
  it('every fixture row is exercised by BOTH expected orders — a new row cannot be smuggled past this suite', async () => {
    const fx = await load();
    const syms = fx.rows.map((r) => r.symbol);
    expect(syms.length).toBeGreaterThan(0);
    // The backend lane extends this fixture with divergence-catching rows. If a
    // row lands here and is not in an expected order, the mirror is pinning
    // less than the file claims — say so loudly rather than pass on a subset.
    expect([...fx.expected_no_signal].sort()).toEqual([...syms].sort());
    expect([...fx.expected_separates].sort()).toEqual([...syms].sort());
  });

  it('reproduces the fixture order in the no_signal branch, from either starting order', async () => {
    const fx = await load();
    const sort = (rows: Row[]) =>
      [...rows].sort((a, b) => compareBandStructure(a, b, 'no_signal')).map((r) => r.symbol);
    expect(sort(fx.rows)).toEqual(fx.expected_no_signal);
    expect(sort([...fx.rows].reverse())).toEqual(fx.expected_no_signal);
  });

  it('reproduces the fixture order in the separates branch, from either starting order', async () => {
    const fx = await load();
    const sort = (rows: Row[]) =>
      [...rows].sort((a, b) => compareBandStructure(a, b, 'separates')).map((r) => r.symbol);
    expect(sort(fx.rows)).toEqual(fx.expected_separates);
    expect(sort([...fx.rows].reverse())).toEqual(fx.expected_separates);
  });

  it('NEGATIVE: `pending` orders exactly like `no_signal` — nothing waits on a number that may never land', async () => {
    const fx = await load();
    const order = [...fx.rows].sort((a, b) => compareBandStructure(a, b, 'pending')).map((r) => r.symbol);
    expect(order).toEqual(fx.expected_no_signal);
  });

  it('NEGATIVE: the n/a row and the no-read row sort LAST in every branch, never first', async () => {
    const fx = await load();
    for (const st of ['separates', 'no_signal', 'pending', 'nonsense-status'] as const) {
      const order = [...fx.rows].sort((a, b) => compareBandStructure(a, b, st)).map((r) => r.symbol);
      expect(order.slice(-2)).toEqual(['NA', 'NONE']);
    }
  });

  it("his ask #1 leads: a CLEAR ceiling beats a thin band, and a thin band beats a thick one", async () => {
    const fx = await load();
    const by = Object.fromEntries(fx.rows.map((r) => [r.symbol, r]));
    expect(compareBandStructure(by.CLR, by.THIN, 'no_signal')).toBeLessThan(0);
    expect(compareBandStructure(by.THIN, by.THICK, 'no_signal')).toBeLessThan(0);
  });

  it("his ask #2 breaks the tie: identical ceiling and gap — the BIGGER first support band wins", async () => {
    const fx = await load();
    const by = Object.fromEntries(fx.rows.map((r) => [r.symbol, r]));
    expect(compareBandStructure(by.TIE_B, by.TIE_A, 'no_signal')).toBeLessThan(0);
  });

  it('NEGATIVE: one support band and NO second sorts behind every row that has a second catch', async () => {
    const fx = await load();
    const by = Object.fromEntries(fx.rows.map((r) => [r.symbol, r]));
    expect(by.NOSEC.read?.floor?.gap_pct ?? null).toBeNull();
    expect(compareBandStructure(by.TIE_A, by.NOSEC, 'no_signal')).toBeLessThan(0);
    expect(compareBandStructure(by.NOSEC, by.NOFLOOR, 'no_signal')).toBeLessThan(0);
  });

  it('NEGATIVE: an unreadable ceiling is not a thin one — it sorts behind every readable ceiling', async () => {
    const fx = await load();
    const by = Object.fromEntries(fx.rows.map((r) => [r.symbol, r]));
    expect(compareBandStructure(by.THICK, by.UNKC, 'no_signal')).toBeLessThan(0);
  });

  it('a separates read with no score of its own sorts after every scored row, before the unreadable ones', async () => {
    const fx = await load();
    const order = [...fx.rows].sort((a, b) => compareBandStructure(a, b, 'separates')).map((r) => r.symbol);
    expect(order.indexOf('NOFLOOR')).toBeLessThan(order.indexOf('NA'));
    expect(order.indexOf('NOSEC')).toBeLessThan(order.indexOf('NOFLOOR'));
  });
});

describe('bandStructureOrderKey / bandStructureSeparates', () => {
  const read = (over: Partial<BandStructureRead> = {}): BandStructureRead => ({
    symbol: 'AAA', kind: 'demand', applicable: true, score: null, stat: 'ceiling 2.0% wide, 1.0% up',
    ceiling: { state: 'ROOM', height_pct: 2, distance_pct: 1, walls_above: 1 },
    floor: { height_pct: 3, gap_pct: 4, bands_below: 2, in_band: false, distance_pct: 1 },
    measured: { status: 'pending' },
    ...over,
  });

  it('is always a 7-tuple, in every branch — the backend says why', () => {
    expect(bandStructureOrderKey(read(), 'AAA')).toHaveLength(7);
    expect(bandStructureOrderKey(read({ applicable: false }), 'AAA')).toHaveLength(7);
    expect(bandStructureOrderKey(null, 'AAA')).toHaveLength(7);
    expect(bandStructureOrderKey(read({ score: 0.5, measured: { status: 'separates' } }), 'AAA')).toHaveLength(7);
  });

  it('NEGATIVE: no read, not applicable, and a malformed read all head the LAST group', () => {
    expect(bandStructureOrderKey(null, 'A')[0]).toBe(2);
    expect(bandStructureOrderKey(undefined, 'A')[0]).toBe(2);
    expect(bandStructureOrderKey(read({ applicable: false }), 'A')[0]).toBe(2);
    expect(bandStructureOrderKey({} as BandStructureRead, 'A')[0]).toBe(2);
  });

  it('NEGATIVE: a NaN / Infinity height is not a height — it falls to the unreadable group, never to 0%', () => {
    const bad = read({ ceiling: { state: 'ROOM', height_pct: Number.NaN, distance_pct: 1 } });
    expect(bandStructureOrderKey(bad, 'A')[1]).toBe(2);
    const inf = read({ ceiling: { state: 'ROOM', height_pct: Number.POSITIVE_INFINITY } });
    expect(bandStructureOrderKey(inf, 'A')[1]).toBe(2);
  });

  it('NEGATIVE: a null gap is UNKNOWN, not zero — it must not outrank a real 0.5% gap', () => {
    const noSecond = read({ floor: { height_pct: 3, gap_pct: null, bands_below: 1 } });
    const tight = read({ floor: { height_pct: 3, gap_pct: 0.5, bands_below: 2 } });
    expect(bandStructureOrderKey(noSecond, 'A')[3]).toBe(1);
    expect(bandStructureOrderKey(tight, 'B')[3]).toBe(0);
    expect(compareBandStructure({ symbol: 'B', read: tight }, { symbol: 'A', read: noSecond }, 'pending'))
      .toBeLessThan(0);
  });

  it('bandStructureSeparates is true for exactly one string', () => {
    expect(bandStructureSeparates('separates')).toBe(true);
    for (const s of ['no_signal', 'pending', '', null, undefined, 'SEPARATES']) {
      expect(bandStructureSeparates(s as string)).toBe(false);
    }
  });

  it('takes the status off the read when the caller passes none', () => {
    const scored = read({ score: 0.9, measured: { status: 'separates' } });
    expect(bandStructureOrderKey(scored, 'A')[1]).toBeCloseTo(-0.9);
    const pending = read({ score: 0.9, measured: { status: 'pending' } });
    expect(bandStructureOrderKey(pending, 'A')[1]).toBe(1);   // ceiling group, not the score
  });
});

describe('bandStructureSortNote — the served order kept, and the reason shown', () => {
  const na: BandStructureRead = { applicable: false, na_text: 'no band read for this tab', ceiling: null, floor: null };
  const ok: BandStructureRead = {
    applicable: true, stat: 'ceiling clear · floor 3.0% wide, no 2nd band',
    ceiling: { state: 'CLEAR' }, floor: { height_pct: 3, gap_pct: null }, measured: { status: 'pending' },
  };
  const rowsOf = (read: BandStructureRead | null) =>
    [{ symbol: 'ZZZ', read }, { symbol: 'AAA', read }, { symbol: 'MMM', read }];

  it("NEGATIVE: an n/a tab's control is INERT — the note says 'na' and the caller must not sort at all", () => {
    const rows = rowsOf(na);
    expect(bandStructureSortNote(rows, 'n/a')).toBe('na');
    expect(BAND_STRUCTURE_KIND_NA).toBe('n/a');
    // The served order is what the page keeps, because it never runs the sort.
    expect(rows.map((r) => r.symbol)).toEqual(['ZZZ', 'AAA', 'MMM']);
  });

  it("NEGATIVE: a board where no name has a read reports 'unavailable' — the reason is shown, never swallowed", () => {
    expect(bandStructureSortNote(rowsOf(null), 'demand')).toBe('unavailable');
    expect(bandStructureSortNote(rowsOf(na), 'demand')).toBe('unavailable');
    expect(bandStructureOrderUnavailable(rowsOf(null))).toBe(true);
  });

  it('NEGATIVE: an n/a KIND wins even when some row carries a read — the tab, not the row, decides', () => {
    expect(bandStructureSortNote([{ symbol: 'A', read: ok }], 'n/a')).toBe('na');
  });

  it('one readable row is enough for the ordering to be a real one', () => {
    expect(bandStructureSortNote([{ symbol: 'A', read: na }, { symbol: 'B', read: ok }], 'demand')).toBeNull();
    expect(bandStructureOrderUnavailable([{ symbol: 'A', read: na }, { symbol: 'B', read: ok }])).toBe(false);
    expect(bandStructureOrderUnavailable([])).toBe(true);
    expect(bandStructureSortNote([], 'demand')).toBe('unavailable');
  });

  it('mirrors the backend: rows with no read share one group and settle by symbol, never ahead of a read', () => {
    const rows = [{ symbol: 'ZZZ', read: null }, { symbol: 'AAA', read: null }, { symbol: 'MMM', read: ok }];
    expect([...rows].sort((a, b) => compareBandStructure(a, b, 'pending')).map((r) => r.symbol))
      .toEqual(['MMM', 'AAA', 'ZZZ']);
  });
});

describe('bandStructureChipText — BOTH halves, in his words, every number served', () => {
  const study: BandStructureStudy = {
    headline: 'MEASURED: pending — ordered by ceiling thickness, floor layering as the tiebreak',
    fallback_note: 'a DESCRIPTIVE ordering of what the bands look like',
    status: 'pending',
  };
  const read = (over: Partial<BandStructureRead> = {}): BandStructureRead => ({
    applicable: true, score: null,
    stat: 'ceiling 3.5% wide, 0.5% up · floor 3.2% wide, 2nd band 6.4% under',
    measured: { status: 'pending' }, ...over,
  });

  it('prints the SERVED stat verbatim — the ceiling half and the floor half, both', () => {
    const chip = bandStructureChipText(read(), study)!;
    expect(chip.text).toBe('🪜 ceiling 3.5% wide, 0.5% up · floor 3.2% wide, 2nd band 6.4% under');
    expect(chip.tone).toBe('muted');
    expect(chip.title).toContain(study.headline);
  });

  it('NEGATIVE: the pending branch never wears the scored tone, even with a score on the read', () => {
    const chip = bandStructureChipText(read({ score: 0.91 }), study)!;
    expect(chip.tone).toBe('muted');
    expect(chip.text).not.toContain('0.91');
  });

  it('scores only in the separates branch, and keeps both halves beside the number', () => {
    const chip = bandStructureChipText(
      read({ score: 0.82, measured: { status: 'separates' } }),
      { ...study, status: 'separates' },
    )!;
    expect(chip.text.startsWith('🪜 0.82 · ')).toBe(true);
    expect(chip.text).toContain('2nd band 6.4% under');
    expect(chip.tone).toBe('band');
  });

  it('NEGATIVE: a missing second band SAYS so — it never renders as 0', () => {
    const chip = bandStructureChipText(
      read({ stat: 'ceiling 3.5% wide, 0.5% up · floor 3.2% wide, no 2nd band' }), study)!;
    expect(chip.text).toContain('no 2nd band');
    expect(chip.text).not.toContain('2nd band 0');
    expect(chip.text).not.toMatch(/2nd band 0(\.0)?%/);
  });

  it('NEGATIVE: renders NOTHING for no read, an n/a tab, or a read the server gave no stat', () => {
    expect(bandStructureChipText(null, study)).toBeNull();
    expect(bandStructureChipText(undefined, study)).toBeNull();
    expect(bandStructureChipText({ applicable: false, na_text: 'no band read for this tab' }, study)).toBeNull();
    expect(bandStructureChipText(read({ stat: null }), study)).toBeNull();
    expect(bandStructureChipText(read({ stat: '   ' }), study)).toBeNull();
  });

  it('NEGATIVE: with no stat and no score there is nothing to print — this file will not build a sentence', () => {
    expect(bandStructureChipText({ applicable: true, stat: null, score: null }, study)).toBeNull();
  });

  /* WHICH PRINT the distances were measured on (2026-09-16), AGAINST THE SHAPE
   * THE SERVER ACTUALLY SENDS.
   *
   * `band_structure._print_block` serves it nested — `read["print"]["source"]`,
   * the same block `enterable.assess` serves and `lib/enterable.ts` already
   * reads. For one round this file declared a TOP-LEVEL `print_source` and the
   * tests fed it `{print_source:'live'}`, a shape no server sends: both
   * branches were dead on every real payload and the suite was green anyway.
   * A test that invents a server shape is worse than no test, so every case
   * below is built from the served block and the top-level spelling is pinned
   * INERT.
   *
   * Both paths into the read fall back to a STORED CLOSE when the snapshot is
   * stale (`bounce_room.print_of` → `fresh=False`, `board._explosive_px`), so
   * an unknown source must name the rule rather than claim a live number. */
  const served = (source: unknown, px = 162.76): Partial<BandStructureRead> =>
    ({ print: { px, source } as BandStructureRead['print'] });

  it('says LIVE only when the SERVED print block says live — read.print.source', () => {
    const chip = bandStructureChipText(read(served('live')), study)!;
    expect(chip.title).toMatch(/read against the live print/);
    expect(chip.title).toContain('closed-bar board geometry');
  });

  it('NEGATIVE: the SERVED scan block reads as a closed-bar read, never as live', () => {
    for (const src of ['scan', 'SCAN', ' scan ', 'stored']) {
      const chip = bandStructureChipText(read(served(src)), study)!;
      expect(chip.title).toMatch(/the stored scan close, not a live print/);
      expect(chip.title).not.toMatch(/read against the live print/);
    }
  });

  it('NEGATIVE: the ROW-BOARD shape — a print block whose source the caller could not fill names the rule', () => {
    // `bounce_room` hands the row boards a read; a caller that cannot say which
    // print it passed serves `{"px": …, "source": None}`, and null must never
    // be read as "live".
    const chip = bandStructureChipText(read(served(null)), study)!;
    expect(chip.title).not.toMatch(/read against the live print/);
    expect(chip.title).toMatch(/the live trade when the snapshot is fresh, the stored close when it is not/);
  });

  it('NEGATIVE: a blank or junk served source falls back to the rule, not to "live"', () => {
    for (const src of ['', '   ', undefined, 42]) {
      const chip = bandStructureChipText(read(served(src)), study)!;
      expect(chip.title).not.toMatch(/read against the live print/);
      expect(chip.title).toMatch(/the live trade when the snapshot is fresh/);
    }
  });

  it('NEGATIVE: no print block at all — a payload from before the block existed names the rule', () => {
    const chip = bandStructureChipText(read(), study)!;
    expect(chip.title).not.toMatch(/read against the live print/);
    expect(chip.title).toMatch(/the live trade when the snapshot is fresh, the stored close when it is not/);
    expect(chip.title).toContain('closed-bar board geometry');
    const nulled = bandStructureChipText(read({ print: null }), study)!;
    expect(nulled.title).toMatch(/the live trade when the snapshot is fresh/);
  });

  it('NEGATIVE: a TOP-LEVEL print_source is INERT — the field the server sends is the field this file reads', () => {
    // The exact shape the previous round fabricated. It must change nothing:
    // if this ever starts asserting a live print, the FE is reading a spelling
    // no backend serves.
    const chip = bandStructureChipText(
      read({ print_source: 'live' } as Partial<BandStructureRead>), study)!;
    expect(chip.title).not.toMatch(/read against the live print/);
    expect(chip.title).toMatch(/the live trade when the snapshot is fresh/);
    // …and the served block still wins over it.
    const both = bandStructureChipText(
      read({ print_source: 'live', ...served('scan') } as Partial<BandStructureRead>), study)!;
    expect(both.title).toMatch(/the stored scan close, not a live print/);
  });
});

/* THE n/a SENTENCE HAS ONE HOME (2026-09-16).
 *
 * `BAND_STRUCTURE_NA_TEXT` is the last-resort mirror the page prints when an
 * n/a tab comes back with zero tiles, so nothing carried the served sentence.
 * The backend constant stays canonical: this reads the module off disk and
 * pins the two equal, so a reworded backend sentence turns this suite red
 * instead of shipping two different n/a lines. */
describe('the n/a fallback sentence mirrors band_structure.NA_TEXT', () => {
  async function backendSource(): Promise<string> {
    const { default: raw } = await import(
      '../../../backend/supply_demand/band_structure.py?raw');
    return raw as string;
  }

  it('is the backend NA_TEXT, character for character', async () => {
    const src = await backendSource();
    const cats = /^NA_CATEGORIES = "([^"]+)"/m.exec(src);
    const na = /^NA_TEXT = \("([^"]*)"\s*\n\s*"([^"]*)" % NA_CATEGORIES\)/m.exec(src);
    expect(cats).not.toBeNull();
    expect(na).not.toBeNull();
    const expected = (na![1] + na![2]).replace('%s', cats![1]);
    expect(BAND_STRUCTURE_NA_TEXT).toBe(expected);
  });

  it('NEGATIVE: says BAND, never bounce, and claims no ordering', async () => {
    expect(BAND_STRUCTURE_NA_TEXT.toLowerCase()).not.toContain('bounc');
    expect(BAND_STRUCTURE_NA_TEXT.toLowerCase()).toContain('band');
    expect(BAND_STRUCTURE_NA_TEXT).not.toMatch(/thinnest|ranked|ordered|sort/i);
  });
});


/* THE THREE PLACES THE TWO SIDES COULD DISAGREE (2026-09-16).
 *
 * None is reachable from today's payload — `applicable` is a bool, the metrics
 * are rounded floats and the symbols are uppercase tickers — so all three are
 * LATENT: a producer change would split the backend ordering from the frontend
 * one with every suite green. The BACKEND IS CANONICAL
 * (`supply_demand/band_structure.py::band_structure_key`), so these pin the FE
 * to Python's behaviour, not the other way round:
 *
 *   • `_f()` is `float(x)` — a STRING numeric and a bool both coerce;
 *   • `if not read.get("applicable")` is TRUTHINESS, not `is True`;
 *   • the symbol leg is a Python tuple comparison — CODEPOINT order, which
 *     `localeCompare` is not ('_' and case both diverge).
 */
describe('backend parity — the latent divergences, pinned', () => {
  const base = (over: Partial<BandStructureRead> = {}): BandStructureRead => ({
    applicable: true, score: null, measured: { status: 'pending' },
    ceiling: { state: 'ROOM', height_pct: 5 },
    floor: { height_pct: 2, gap_pct: 4 },
    ...over,
  });

  it('a STRING numeric is a number, exactly as float("5.0") is — never the unreadable group', () => {
    const str = base({ ceiling: { state: 'ROOM', height_pct: '5.0' as unknown as number } });
    expect(bandStructureOrderKey(str, 'A')[1]).toBe(1);     // readable ceiling
    expect(bandStructureOrderKey(str, 'A')[2]).toBe(5);
    const gap = base({ floor: { height_pct: '2.0' as unknown as number, gap_pct: '4.0' as unknown as number } });
    expect(bandStructureOrderKey(gap, 'A')[3]).toBe(0);     // a real second catch
    expect(bandStructureOrderKey(gap, 'A')[4]).toBe(4);
    expect(bandStructureOrderKey(gap, 'A')[5]).toBe(-2);
  });

  it('a bool coerces the way float(True) does — 1, not unreadable', () => {
    const b = base({ ceiling: { state: 'ROOM', height_pct: true as unknown as number } });
    expect(bandStructureOrderKey(b, 'A')[1]).toBe(1);
    expect(bandStructureOrderKey(b, 'A')[2]).toBe(1);
  });

  it('NEGATIVE: junk that float() would REJECT stays unreadable — never silently 0', () => {
    for (const junk of ['', '   ', 'wide', '0x10', [] as unknown, {} as unknown, [3] as unknown]) {
      const r = base({ ceiling: { state: 'ROOM', height_pct: junk as unknown as number } });
      expect(bandStructureOrderKey(r, 'A')[1]).toBe(2);
      expect(bandStructureOrderKey(r, 'A')[2]).toBe(0);
    }
  });

  it('`applicable` is TRUTHINESS, not `=== true` — the backend asks `if not read.get(...)`', () => {
    for (const yes of [true, 1, 'yes', 3.5, [0] as unknown, { a: 1 } as unknown]) {
      expect(bandStructureOrderKey(base({ applicable: yes as unknown as boolean }), 'A')[0]).toBe(0);
    }
  });

  it('NEGATIVE: every value Python calls FALSY is not applicable — and sorts last', () => {
    for (const no of [false, 0, '', null, undefined, [] as unknown, {} as unknown]) {
      expect(bandStructureOrderKey(base({ applicable: no as unknown as boolean }), 'A')[0]).toBe(2);
      expect(bandStructureChipText(base({ applicable: no as unknown as boolean, stat: 'x' }))).toBeNull();
    }
  });

  it('the symbol tiebreak is CODEPOINT order, which is what a Python tuple does', () => {
    const r = base();
    const cmp = (x: string, y: string) =>
      compareBandStructure({ symbol: x, read: r }, { symbol: y, read: r }, 'pending');
    // '_' (U+005F) sits BETWEEN 'Z' (U+005A) and 'a' (U+0061). localeCompare
    // puts 'A_B' before 'AB'; Python — and now this comparator — does not.
    expect(cmp('AB', 'A_B')).toBeLessThan(0);
    // Upper case before lower: 'AB' < 'aB' by codepoint, the reverse of most
    // locales' collation.
    expect(cmp('AB', 'aB')).toBeLessThan(0);
    expect(cmp('BRK.B', 'BF-B')).toBeGreaterThan(0);   // real tickers agree either way
    expect(cmp('AAA', 'AAA')).toBe(0);
  });
});
