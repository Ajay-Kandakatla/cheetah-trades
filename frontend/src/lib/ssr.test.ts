/* ⛔ ssr lib (2026-11-23, spec ssr §3.10 / §4 W4). The served words pass through untouched; the lookup is an EXACT
 * own-key match; every foreign body (🔒, 💸, 🩳 map) is rejected by the `kind` discriminator; `keep_sec` /
 * `retry_after_sec` are kept only as finite numbers; `fault_text` only as a non-empty string. Bodies = the spec §3.8 shape;
 * every word is a stand-in for a served one. */
import { describe, expect, it } from 'vitest';
import { parseSsr, ssrRead, SSR_KIND, SSR_PATH } from './ssr';

const AKAN = {
  state: 'on', symbol: 'AKAN', source: 'official', exchange: 'Nasdaq', triggered_on: '2026-11-23', triggered_at_et: '09:30:47',
  time_basis: 'exchange', through: '2026-11-24', off_from: '2026-11-25', half_day: false, drop_pct: -13.0, prior_close: 4.23,
  retriggered: false, conflict: null, corp_checked: true,
  chip: '⛔ SSR · served chip AKAN', short: '⛔ SSR thru 11/24', label: '⛔ SSR on · served label AKAN', title: 'served title AKAN',
};
const PXED = { state: 'unknown', symbol: 'PXED', why: 'corp_action', chip: null, short: null, label: '⛔ SSR not read', title: 'served title PXED' };
const body = (over: Record<string, unknown> = {}) => ({
  kind: 'ssr_rule_201', status: 'ok', items: { AKAN, PXED },
  states: { AKAN: 'on', AAPL: 'off', PXED: 'unknown', ZZCO: 'unknown' }, whys: { PXED: 'corp_action', ZZCO: 'computed_only' },
  asked: 4, n: 2, max_symbols: 200, session: { now_et: '2026-11-23 22:09', in_play: ['2026-11-23'] }, sources: [],
  computed: { ok: true, last_pass_et: '20:01', final: true, text: 'served' }, note: 'served note', fault_text: null,
  refreshing: false, retry_after_sec: null, keep_sec: 300, ...over,
});

describe('parseSsr — positives', () => {
  it('the path and kind equal the backend route and discriminator', () => {
    expect(SSR_PATH).toBe('/short-interest/ssr');
    expect(SSR_KIND).toBe('ssr_rule_201');
  });

  it('the §3.8 body → an on item and an unknown item, only the five read fields', () => {
    const p = parseSsr(body())!;
    expect(p).not.toBeNull();
    expect(ssrRead(p, 'AKAN')).toEqual({ state: 'on', chip: AKAN.chip, short: AKAN.short, label: AKAN.label, title: AKAN.title });
    expect(ssrRead(p, 'PXED')).toEqual({ state: 'unknown', chip: null, short: null, label: PXED.label, title: PXED.title });
    expect(p.fault_text).toBeNull();
    expect(p.refreshing).toBe(false);
    expect(p.retry_after_sec).toBeNull();
    expect(p.keep_sec).toBe(300);
  });

  it('NEGATIVE: off (AAPL) and a quiet unknown (ZZCO) are in `states` / `whys` only → no read', () => {
    const p = parseSsr(body())!;
    expect(ssrRead(p, 'AAPL')).toBeNull();
    expect(ssrRead(p, 'ZZCO')).toBeNull();
    expect(Object.keys(p.items).sort()).toEqual(['AKAN', 'PXED']);
  });

  it('fault_text, refreshing and retry_after_sec pass through', () => {
    const p = parseSsr(body({ fault_text: 'served fault line', refreshing: true, retry_after_sec: 20 }))!;
    expect(p.fault_text).toBe('served fault line');
    expect(p.refreshing).toBe(true);
    expect(p.retry_after_sec).toBe(20);
  });

  it('lower-case and padded input still match exactly', () => {
    expect(ssrRead(parseSsr(body()), '  akan ')!.chip).toBe(AKAN.chip);
  });

  it('a valid payload with an empty items map parses (nothing to draw, still valid)', () => {
    const p = parseSsr(body({ items: {} }))!;
    expect(p).not.toBeNull();
    expect(ssrRead(p, 'AKAN')).toBeNull();
  });
});

describe('parseSsr — NEGATIVES', () => {
  const RS_BODY = { kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, items: { AKAN: { state: 'on', chip: 'x', short: 'y', label: 'z', title: 't' } },
    fault_text: 'x', refreshing: false, retry_after_sec: null };
  const BR_BODY = { kind: 'ibkr_borrow', status: 'ok', items: { AKAN: { state: 'listed', chip: 'x', short: 'y', label: 'z', title: 't', stale: false } },
    max_symbols: 200, refreshing: false, retry_after_sec: null, keep_sec: 3600 };
  const SI_MAP = { items: { AKAN: { symbol: 'AKAN', status: 'ok', chip: 'x', title: 'y', rows: [] } }, n: 1, max_symbols: 200 };
  const { kind: _k, ...NO_KIND } = body();
  void _k;
  for (const [name, j] of [
    ['the 🔒 body', RS_BODY], ['the 💸 body', BR_BODY], ['the 🩳 map body', SI_MAP], ['null', null], ['an array', [AKAN]],
    ['a string', 'x'], ['{}', {}], ['kind missing', NO_KIND], ['a wrong kind', body({ kind: 'ibkr_borrow' })],
    ['items an array', body({ items: [AKAN] })], ['items null', body({ items: null })],
  ] as const) {
    it(`foreign body (${name}) → null, no read`, () => {
      expect(parseSsr(j)).toBeNull();
      expect(ssrRead(parseSsr(j), 'AKAN')).toBeNull();
    });
  }

  for (const [name, over] of [
    ['a blank title', { title: '  ' }], ['no title', { title: undefined }], ['a title number', { title: 5 }],
    ['no chip, short or label', { chip: null, short: null, label: null }], ['blank chip, short and label', { chip: ' ', short: '', label: '  ' }],
    ['no state', { state: undefined }], ['a blank state', { state: '' }], ['a state number', { state: 1 }],
  ] as const) {
    it(`an item with ${name} → the item is dropped`, () => {
      const p = parseSsr(body({ items: { AKAN: { ...AKAN, ...over } } }))!;
      expect(p).not.toBeNull();
      expect(ssrRead(p, 'AKAN')).toBeNull();
    });
  }

  it('a blank or non-string form reads null; the item stays when another form is served', () => {
    const r = ssrRead(parseSsr(body({ items: { AKAN: { ...AKAN, chip: ' ', short: 7 } } })), 'AKAN')!;
    expect(r.chip).toBeNull();
    expect(r.short).toBeNull();
    expect(r.label).toBe(AKAN.label);
  });

  for (const [name, v] of [['the string "60"', '60'], ['NaN', Number.NaN], ['null', null], ['Infinity', Number.POSITIVE_INFINITY], ['missing', undefined]] as const) {
    it(`keep_sec / retry_after_sec of ${name} → null`, () => {
      const p = parseSsr(body({ keep_sec: v, retry_after_sec: v }))!;
      expect(p.keep_sec).toBeNull();
      expect(p.retry_after_sec).toBeNull();
    });
  }

  for (const [name, v] of [['blank', '  '], ['a number', 5], ['an object', { text: 'x' }], ['missing', undefined]] as const) {
    it(`fault_text ${name} → null`, () => {
      expect(parseSsr(body({ fault_text: v }))!.fault_text).toBeNull();
    });
  }

  it("refreshing reads true only for served === true ('yes', 1 → false)", () => {
    expect(parseSsr(body({ refreshing: 'yes' }))!.refreshing).toBe(false);
    expect(parseSsr(body({ refreshing: 1 }))!.refreshing).toBe(false);
  });

  it('constructor / __proto__ never match; a served __proto__ key is never kept', () => {
    const p = parseSsr(JSON.parse(JSON.stringify(body())))!;
    for (const k of ['constructor', '__proto__', 'CONSTRUCTOR', '__PROTO__', 'toString', 'hasOwnProperty', '']) expect(ssrRead(p, k), k).toBeNull();
    const q = parseSsr(JSON.parse(`{"kind":"ssr_rule_201","items":{"__proto__":${JSON.stringify(AKAN)}}}`))!;
    expect(q).not.toBeNull();
    expect(Object.getPrototypeOf(q.items)).toBe(Object.prototype);
    expect(Object.keys(q.items)).toEqual([]);
  });

  it('exact match: AKAN served does not read AKANW, AKA or AKANX', () => {
    const p = parseSsr(body())!;
    for (const s of ['AKANW', 'AKA', 'AKANX']) expect(ssrRead(p, s), s).toBeNull();
    expect(ssrRead(p, 'AKAN')).not.toBeNull();
  });

  it('the served numbers are never read (drop_pct NaN never throws, never kept)', () => {
    const j = body({ items: { AKAN: { ...AKAN, drop_pct: Number.NaN, prior_close: 'x', through: 5 } } });
    expect(() => parseSsr(j)).not.toThrow();
    const r = ssrRead(parseSsr(j), 'AKAN')!;
    expect(Object.keys(r).sort()).toEqual(['chip', 'label', 'short', 'state', 'title']);
  });

  it('null payload → null read', () => {
    expect(ssrRead(null, 'AKAN')).toBeNull();
  });
});
