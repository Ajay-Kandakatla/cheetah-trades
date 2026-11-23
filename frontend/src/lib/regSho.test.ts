/* 🔒 regSho lib (2026-11-22, spec htb §3.3 / §4 fe). The served words pass through untouched; the lookup is an EXACT key
 * match; every foreign body is rejected by the `kind` discriminator. Stand-in strings = the spec's worked AKAN contract. */
import { describe, expect, it } from 'vitest';
import { parseRegSho, regShoTag, REG_SHO_KIND, REG_SHO_PATH } from './regSho';

const AKAN = {
  state: 'on', symbol: 'AKAN', market: 'nasdaq', exchange: 'Nasdaq', as_of: '2026-11-20', stale: false,
  chip: '🔒 Hard to borrow · threshold security · 11/20',
  short: '🔒 Hard to borrow · 11/20',
  label: '🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20',
  title: '🔒 Hard to borrow — AKAN is a Reg SHO threshold security on the Nasdaq list for 2026-11-20: served hover.',
};
const body = (over: Record<string, unknown> = {}) => ({
  kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, n: 1,
  items: { AKAN: AKAN }, sources: [], note: 'served note', fault_text: null, refreshing: false, retry_after_sec: null,
  ...over,
});

describe('parseRegSho — positives', () => {
  it('the path and kind equal the backend route and discriminator', () => {
    expect(REG_SHO_PATH).toBe('/short-interest/reg-sho');
    expect(REG_SHO_KIND).toBe('reg_sho_threshold');
  });

  it('a valid payload → the AKAN tag with the served strings untouched', () => {
    const p = parseRegSho(body())!;
    expect(p).not.toBeNull();
    const t = regShoTag(p, 'AKAN')!;
    expect(t).toEqual({ chip: AKAN.chip, short: AKAN.short, label: AKAN.label, title: AKAN.title, stale: false,
                        market: 'nasdaq', asOf: '2026-11-20' });
    expect(p.complete).toBe(true);
    expect(p.refreshing).toBe(false);
    expect(p.fault_text).toBeNull();
    expect(p.as_of).toBe('2026-11-20');
  });

  it('lower-case and padded input still match exactly; the served fault_text and retry pass through', () => {
    const p = parseRegSho(body({ fault_text: 'served fault', refreshing: true, retry_after_sec: 20 }))!;
    expect(regShoTag(p, '  akan ')!.chip).toBe(AKAN.chip);
    expect(p.fault_text).toBe('served fault');
    expect(p.refreshing).toBe(true);
    expect(p.retry_after_sec).toBe(20);
  });

  it('stale passes through only when served === true', () => {
    expect(regShoTag(parseRegSho(body({ items: { AKAN: { ...AKAN, stale: true } } })), 'AKAN')!.stale).toBe(true);
    expect(regShoTag(parseRegSho(body({ items: { AKAN: { ...AKAN, stale: 'true' } } })), 'AKAN')!.stale).toBe(false);
  });
});

describe('parseRegSho — NEGATIVES', () => {
  for (const [name, j] of [
    ['{}', {}], ['an array', []], ['null', null], ['a string', 'x'],
    ['the SI map body', { items: { AKAN: { symbol: 'AKAN', status: 'ok', chip: 'x', title: 'y', rows: [] } }, n: 1, max_symbols: 200 }],
    ['a Watch board body', { title: 'Watch', rows: [{ symbol: 'AKAN' }], remove_label: 'x' }],
    ['a wrong kind', body({ kind: 'short_interest' })],
    ['items an array', body({ items: [AKAN] })],
    ['items null', body({ items: null })],
  ] as const) {
    it(`foreign body (${name}) → null, no tag`, () => {
      expect(parseRegSho(j)).toBeNull();
      expect(regShoTag(parseRegSho(j), 'AKAN')).toBeNull();
    });
  }

  for (const [name, over] of [
    ["state 'off'", { state: 'off' }], ["state 'unknown'", { state: 'unknown' }], ['no state', { state: undefined }],
    ['blank chip', { chip: '  ' }], ['blank short', { short: '' }], ['blank label', { label: ' ' }],
    ['blank title', { title: '' }], ['chip a number', { chip: 5 }], ['title null', { title: null }],
  ] as const) {
    it(`an item with ${name} → no tag`, () => {
      const p = parseRegSho(body({ items: { AKAN: { ...AKAN, ...over } } }))!;
      expect(p).not.toBeNull();
      expect(regShoTag(p, 'AKAN')).toBeNull();
    });
  }

  it('exact match: AKAN listed does not tag AKANW; ACONW listed does not tag ACON', () => {
    const p = parseRegSho(body({ items: { AKAN, ACONW: { ...AKAN, symbol: 'ACONW' } } }))!;
    expect(regShoTag(p, 'AKANW')).toBeNull();
    expect(regShoTag(p, 'AKA')).toBeNull();
    expect(regShoTag(p, 'ACON')).toBeNull();
    expect(regShoTag(p, 'ACONW')).not.toBeNull();
    expect(regShoTag(p, '')).toBeNull();
    expect(regShoTag(p, 'constructor')).toBeNull();
    expect(regShoTag(p, '__proto__')).toBeNull();
  });

  it('unknown (complete false, name absent) → no tag; the payload never said off', () => {
    const j = body({ complete: false, items: {} });
    const p = parseRegSho(j)!;
    expect(p.complete).toBe(false);
    expect(regShoTag(p, 'AKAN')).toBeNull();
    expect(JSON.stringify(j)).not.toContain('"off"');
  });

  it('a blank fault_text and a non-finite retry read as null; a non-true refreshing reads false', () => {
    const p = parseRegSho(body({ fault_text: '  ', retry_after_sec: 'NaN', refreshing: 'yes', as_of: '' }))!;
    expect(p.fault_text).toBeNull();
    expect(p.retry_after_sec).toBeNull();
    expect(p.refreshing).toBe(false);
    expect(p.as_of).toBeNull();
  });
});
