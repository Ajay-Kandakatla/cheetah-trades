/* 💸 borrow lib (2026-11-22, spec borrow §3.3 / §4 fe part A). The served words pass through untouched; the lookup is an
 * EXACT own-key match; every foreign body is rejected by the `kind` discriminator; `keep_sec` / `retry_after_sec` are
 * kept only as finite numbers [C8]; the fee / share / name fields are never read. Strings = the spec's worked contract. */
import { describe, expect, it } from 'vitest';
import { borrowRead, parseBorrow, BORROW_KIND, BORROW_PATH } from './borrow';

const DBGI = {
  state: 'listed', symbol: 'DBGI', name: 'DIGITAL BRANDS GROUP INC',
  chip: '💸 Borrow 196% · 100K avail', short: '💸 196%',
  label: '💸 Borrow 196% a year · 100K shares available · IBKR file 2026.11.22 22:57:25',
  title: "Interactive Brokers borrow fee for DBGI (IBKR's row: DIGITAL BRANDS GROUP INC): served title.", stale: false,
  fee_pct: 196.2308, rebate_pct: -192.3508, available: 100000, available_floor: false,
};
const AKAN = {
  state: 'absent', symbol: 'AKAN', name: null, chip: null, short: null, label: "💸 not in IBKR's borrow file",
  title: "AKAN is not in IBKR's borrow file stamped 2026.11.22 22:57:25: served title.", stale: false,
  fee_pct: null, rebate_pct: null, available: null, available_floor: false,
};
const body = (over: Record<string, unknown> = {}) => ({
  kind: 'ibkr_borrow', status: 'ok', stale: false, items: { DBGI, AKAN }, asked: 2, n: 2, max_symbols: 200,
  file: { stamp: '2026.11.22 22:57:25', text: 'served file text' }, note: 'served note',
  refreshing: false, retry_after_sec: null, keep_sec: 3600, ...over,
});

describe('parseBorrow — positives', () => {
  it('the path and kind equal the backend route and discriminator', () => {
    expect(BORROW_PATH).toBe('/short-interest/borrow');
    expect(BORROW_KIND).toBe('ibkr_borrow');
  });

  it('a listed and an absent item pass through untouched (only the six read fields)', () => {
    const p = parseBorrow(body())!;
    expect(p).not.toBeNull();
    expect(borrowRead(p, 'DBGI')).toEqual({ state: 'listed', chip: DBGI.chip, short: DBGI.short, label: DBGI.label, title: DBGI.title, stale: false });
    expect(borrowRead(p, 'AKAN')).toEqual({ state: 'absent', chip: null, short: null, label: AKAN.label, title: AKAN.title, stale: false });
    expect(p.refreshing).toBe(false);
    expect(p.retry_after_sec).toBeNull();
    expect(p.keep_sec).toBe(3600);
  });

  it('[C8] keep_sec: 300 is kept; retry_after_sec and refreshing pass through', () => {
    const p = parseBorrow(body({ keep_sec: 300, retry_after_sec: 20, refreshing: true }))!;
    expect(p.keep_sec).toBe(300);
    expect(p.retry_after_sec).toBe(20);
    expect(p.refreshing).toBe(true);
  });

  it('lower-case and padded input still match exactly', () => {
    expect(borrowRead(parseBorrow(body()), '  dbgi ')!.chip).toBe(DBGI.chip);
  });

  it('an absent item served WITH a chip and a short keeps both (the server switch needs no FE change)', () => {
    const p = parseBorrow(body({ items: { AKAN: { ...AKAN, chip: "💸 not in IBKR's file", short: '💸 not in file' } } }))!;
    expect(borrowRead(p, 'AKAN')).toMatchObject({ chip: "💸 not in IBKR's file", short: '💸 not in file', label: AKAN.label });
  });

  it('stale passes through only when served === true', () => {
    expect(borrowRead(parseBorrow(body({ items: { DBGI: { ...DBGI, stale: true } } })), 'DBGI')!.stale).toBe(true);
    expect(borrowRead(parseBorrow(body({ items: { DBGI: { ...DBGI, stale: 'true' } } })), 'DBGI')!.stale).toBe(false);
    expect(borrowRead(parseBorrow(body({ items: { DBGI: { ...DBGI, stale: 1 } } })), 'DBGI')!.stale).toBe(false);
  });
});

describe('parseBorrow — NEGATIVES', () => {
  const RS_BODY = { kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, items: { AKAN: { state: 'on', chip: 'x', short: 'y', label: 'z', title: 't' } },
    fault_text: null, refreshing: false, retry_after_sec: null };
  const SI_MAP = { items: { AKAN: { symbol: 'AKAN', status: 'ok', chip: 'x', title: 'y', rows: [] } }, n: 1, max_symbols: 200 };
  for (const [name, j] of [
    ['the 🔒 body', RS_BODY], ['the 🩳 map body', SI_MAP], ['null', null], ['an array', [DBGI]], ['a string', 'x'], ['{}', {}],
    ['a wrong kind', body({ kind: 'reg_sho_threshold' })], ['items an array', body({ items: [DBGI] })], ['items null', body({ items: null })],
  ] as const) {
    it(`foreign body (${name}) → null, no read`, () => {
      expect(parseBorrow(j)).toBeNull();
      expect(borrowRead(parseBorrow(j), 'DBGI')).toBeNull();
      expect(borrowRead(parseBorrow(j), 'AKAN')).toBeNull();
    });
  }

  for (const [name, over] of [
    ['a blank title', { title: '  ' }], ['no title', { title: undefined }], ['a title number', { title: 5 }],
    ['no chip, short or label', { chip: null, short: null, label: null }], ['blank chip, short and label', { chip: ' ', short: '', label: '  ' }],
    ['no state', { state: undefined }], ['a blank state', { state: '' }], ['a state number', { state: 1 }],
  ] as const) {
    it(`an item with ${name} → the item is dropped`, () => {
      const p = parseBorrow(body({ items: { DBGI: { ...DBGI, ...over } } }))!;
      expect(p).not.toBeNull();
      expect(borrowRead(p, 'DBGI')).toBeNull();
    });
  }

  it('a blank or non-string form reads null; the item stays when another form is served', () => {
    const r = borrowRead(parseBorrow(body({ items: { DBGI: { ...DBGI, chip: ' ', short: 7 } } })), 'DBGI')!;
    expect(r.chip).toBeNull();
    expect(r.short).toBeNull();
    expect(r.label).toBe(DBGI.label);
  });

  for (const [name, v] of [['the string "60"', '60'], ['NaN', Number.NaN], ['null', null], ['Infinity', Number.POSITIVE_INFINITY], ['missing', undefined]] as const) {
    it(`[C8] keep_sec / retry_after_sec of ${name} → null`, () => {
      const p = parseBorrow(body({ keep_sec: v, retry_after_sec: v }))!;
      expect(p.keep_sec).toBeNull();
      expect(p.retry_after_sec).toBeNull();
    });
  }

  it("refreshing reads true only for served === true ('yes', 1 → false)", () => {
    expect(parseBorrow(body({ refreshing: 'yes' }))!.refreshing).toBe(false);
    expect(parseBorrow(body({ refreshing: 1 }))!.refreshing).toBe(false);
  });

  it('constructor / __proto__ never match; a served __proto__ key is never kept', () => {
    const p = parseBorrow(JSON.parse(JSON.stringify(body())))!;
    for (const k of ['constructor', '__proto__', 'CONSTRUCTOR', '__PROTO__', 'toString', 'hasOwnProperty', '']) expect(borrowRead(p, k), k).toBeNull();
    const q = parseBorrow(JSON.parse(`{"kind":"ibkr_borrow","items":{"__proto__":${JSON.stringify(DBGI)}}}`))!;
    expect(q).not.toBeNull();
    expect(Object.getPrototypeOf(q.items)).toBe(Object.prototype);
    expect(Object.keys(q.items)).toEqual([]);
  });

  it('exact match: DBGI listed does not read DBGIW, DBG or DBGIX', () => {
    const p = parseBorrow(body())!;
    expect(borrowRead(p, 'DBGIW')).toBeNull();
    expect(borrowRead(p, 'DBG')).toBeNull();
    expect(borrowRead(p, 'DBGIX')).toBeNull();
    expect(borrowRead(p, 'DBGI')).not.toBeNull();
  });

  it('a NaN fee_pct never throws and is never read', () => {
    const j = body({ items: { DBGI: { ...DBGI, fee_pct: Number.NaN, available: Number.NaN, rebate_pct: 'x', name: 5 } } });
    expect(() => parseBorrow(j)).not.toThrow();
    const r = borrowRead(parseBorrow(j), 'DBGI')!;
    expect(Object.keys(r).sort()).toEqual(['chip', 'label', 'short', 'stale', 'state', 'title']);
    for (const k of ['fee_pct', 'available', 'rebate_pct', 'name', 'symbol', 'available_floor']) expect(k in r, k).toBe(false);
  });

  it('null payload → null read', () => {
    expect(borrowRead(null, 'DBGI')).toBeNull();
  });
});
