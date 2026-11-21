/* 🔢 the Watch row float — parser + the ONE pick (2026-11-21, spec watchfloat §3.5, WP fe-float).
 * Ajay 2026-11-21: "can you add the current float value also to the tickers on the watch list."
 * Every word is a stand-in for a served one. NEGATIVES: junk → null; NaN shares → shares null but the chip KEPT [C9];
 * `suspect` only for `=== true`; neither float → null; a blank row float falls to the tags float. Display only. */
import { describe, expect, it } from 'vitest';
import autoFixture from '../components/__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import { ggwFloat, parseGgw, parseRowFloat, type GgwBoard, type GgwRowFloat, type GgwTagFloat } from './gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const SERVED = {
  shares: 1889.0, src: 'served-src', text: 'served float text 1', as_of: '2026-11-20T09:06:00+00:00', suspect: false,
  suspect_text: null, title: 'served hover title 1', read_from: 'cache',
};
const KEYS = ['as_of', 'read_from', 'shares', 'src', 'suspect', 'suspect_text', 'text', 'title'];
const TAG_FLOAT: GgwTagFloat = { text: 'served tags float text', shares: 3200000, src: 'served', as_of: '2026-11-17', suspect: false };

describe('🔢 parseRowFloat', () => {
  it('a served text → all 8 keys, values as served; a float shares 1889.0 survives as 1889', () => {
    const p = parseRowFloat(clone(SERVED))!;
    expect(Object.keys(p).sort()).toEqual(KEYS);
    expect(p).toEqual(SERVED);
    expect(p.shares).toBe(1889);
    const s = parseRowFloat({ ...SERVED, suspect: true, suspect_text: 'served suspect words' })!;
    expect(s.suspect).toBe(true);
    expect(s.suspect_text).toBe('served suspect words');
  });
  it('NEGATIVE: blank / absent text, an array, a string, a number, null, undefined → null', () => {
    for (const junk of [undefined, null, 'x', 3, [], [SERVED], {}, { ...SERVED, text: '' }, { ...SERVED, text: '  ' },
      { ...SERVED, text: 7 }, { ...SERVED, text: undefined }, { ...SERVED, text: null }]) {
      expect(parseRowFloat(junk), JSON.stringify(junk)).toBeNull();
    }
  });
  it('NEGATIVE [C9]: NaN / Infinity / string shares → shares null, the chip KEPT (text served)', () => {
    for (const bad of [NaN, Infinity, '1889', null, undefined]) {
      const p = parseRowFloat({ ...SERVED, shares: bad });
      expect(p, String(bad)).not.toBeNull();
      expect(p!.shares).toBeNull();
      expect(p!.text).toBe(SERVED.text);
    }
  });
  it('NEGATIVE: suspect is true ONLY for === true; junk strings → null', () => {
    for (const s of ['true', 1, 'yes', null, undefined, {}]) {
      expect(parseRowFloat({ ...SERVED, suspect: s })!.suspect, String(s)).toBe(false);
    }
    const p = parseRowFloat({ ...SERVED, src: 3, as_of: ' ', suspect_text: '', title: [], read_from: {} })!;
    expect([p.src, p.as_of, p.suspect_text, p.title, p.read_from]).toEqual([null, null, null, null, null]);
  });
});

describe('🔢 parseGgw sets row.float', () => {
  it('a served float on one row → that row parsed; every other row float null (the 11-17 fixture has none)', () => {
    const raw = clone(autoFixture as any);
    raw.rows[3].float = clone(SERVED);
    const b = parseGgw(raw) as GgwBoard;
    expect(b.rows[3].float).toEqual(SERVED);
    for (const r of b.rows.filter((_, i) => i !== 3)) expect(r.float, r.symbol).toBeNull();
    expect(b.rows.every((r) => 'float' in r)).toBe(true);
  });
  it('NEGATIVE: junk on a row → null (never a chip)', () => {
    const raw = clone(autoFixture as any);
    raw.rows[0].float = { text: ' ' };
    raw.rows[1].float = 'Float 3M';
    const b = parseGgw(raw) as GgwBoard;
    expect(b.rows[0].float).toBeNull();
    expect(b.rows[1].float).toBeNull();
  });
});

describe('🔢 ggwFloat', () => {
  const ROW: GgwRowFloat = parseRowFloat(clone(SERVED))!;
  it('row.float FIRST (even when the tags carry one)', () => {
    expect(ggwFloat({ float: ROW, tags: { float: TAG_FLOAT } })).toBe(ROW);
    expect(ggwFloat({ float: ROW, tags: null })).toBe(ROW);
    expect(ggwFloat({ float: ROW })).toBe(ROW);
  });
  it('the tags fallback (older server) → its five keys + title / suspect_text / read_from null', () => {
    expect(ggwFloat({ float: null, tags: { float: TAG_FLOAT } })).toEqual(
      { ...TAG_FLOAT, suspect_text: null, title: null, read_from: null });
    expect(ggwFloat({ tags: { float: TAG_FLOAT } })!.text).toBe(TAG_FLOAT.text);
  });
  it('NEGATIVE: a blank row.float text falls to the tags float', () => {
    expect(ggwFloat({ float: { ...ROW, text: '  ' }, tags: { float: TAG_FLOAT } })!.text).toBe(TAG_FLOAT.text);
  });
  it('NEGATIVE: neither → null (null / absent / blank tags text)', () => {
    expect(ggwFloat({})).toBeNull();
    expect(ggwFloat({ float: null, tags: null })).toBeNull();
    expect(ggwFloat({ float: null, tags: { float: null } })).toBeNull();
    expect(ggwFloat({ float: { ...ROW, text: '' }, tags: { float: { ...TAG_FLOAT, text: ' ' } } })).toBeNull();
  });
});
