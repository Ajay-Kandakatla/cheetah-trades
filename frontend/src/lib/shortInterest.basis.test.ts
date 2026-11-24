import { describe, it, expect } from 'vitest';
import {
  parseSiMap, siBasisPending, siFlags, siFollowupClamp, siChip,
  SI_FOLLOWUP_MIN_MS, SI_FOLLOWUP_MAX_MS, type ShortInterestRead,
} from './shortInterest';

/* 🩳 share-count check guards (2026-11-24, spec sidilute §3.7). Ajay: "Make sure we are looking for Dilution.." · "Also split
 * related events and filing so we flag them in the right way". The FE reads only `basis.pending` (strictly true) and the
 * served delay; the flags' words arrive inside the served chip. NEGATIVES: an older API (no basis), a junk `pending`, a junk
 * `retry_after_sec`, junk `flags`. */

const SMTK_FLAGS = [
  { key: 'float_stale', emoji: '⚠️', short: '⚠️ float stale', text: '⚠️ float stale — served text' },
  { key: 'split', emoji: '✂️', short: '✂️ split 11/23', text: '✂️ served split text' },
  { key: 'filing', emoji: '📄', short: '📄 S-4 11/13', text: '📄 dilution filing: S-4 11/13' },
];
const rd = (basis: unknown, extra: Record<string, unknown> = {}): ShortInterestRead =>
  ({ symbol: 'SMTK', status: 'ok', chip: '🩳 served chip', title: 'served title', rows: [], basis, ...extra }) as unknown as ShortInterestRead;

describe('🩳 siBasisPending', () => {
  it('bounds are the spec numbers', () => {
    expect(SI_FOLLOWUP_MIN_MS).toBe(5000);
    expect(SI_FOLLOWUP_MAX_MS).toBe(120000);
  });

  it('pending === true → the served delay in ms, clamped into [MIN, MAX]', () => {
    expect(siBasisPending(rd({ status: 'pending', pending: true, retry_after_sec: 20 }))).toBe(20000);
    expect(siBasisPending(rd({ status: 'pending', pending: true, retry_after_sec: 1 }))).toBe(SI_FOLLOWUP_MIN_MS);
    expect(siBasisPending(rd({ status: 'pending', pending: true, retry_after_sec: 9999 }))).toBe(SI_FOLLOWUP_MAX_MS);
  });

  it('a block carrying its OWN basis (flags, ok) AND pending → pending too [C5]', () => {
    expect(siBasisPending(rd({ status: 'ok', flags: SMTK_FLAGS, float_refused: 'diluted', pending: true, retry_after_sec: 20 }))).toBe(20000);
  });

  it('NEGATIVE: junk retry_after_sec (NaN, negative, zero, a string, Infinity, null, absent) → the minimum delay', () => {
    for (const v of [NaN, -5, 0, '20', Infinity, -Infinity, null, undefined, true, {}]) {
      expect(siBasisPending(rd({ pending: true, retry_after_sec: v })), String(v)).toBe(SI_FOLLOWUP_MIN_MS);
    }
  });

  it('NEGATIVE: pending a string / 1 / null / false / absent → not pending', () => {
    for (const v of ['true', 1, null, false, undefined, 'yes', {}]) {
      expect(siBasisPending(rd({ pending: v, retry_after_sec: 20 })), String(v)).toBeNull();
    }
  });

  it('NEGATIVE: older API (no basis key), a null / array / string basis, a null read → null', () => {
    expect(siBasisPending({ symbol: 'X', status: 'ok', chip: 'c', title: 't', rows: [] } as unknown as ShortInterestRead)).toBeNull();
    for (const b of [null, [], 'pending', 7]) expect(siBasisPending(rd(b))).toBeNull();
    expect(siBasisPending(null)).toBeNull();
    expect(siBasisPending(undefined)).toBeNull();
  });

  it('siFollowupClamp: junk → MIN, above MAX → MAX', () => {
    expect(siFollowupClamp(NaN)).toBe(SI_FOLLOWUP_MIN_MS);
    expect(siFollowupClamp('9000')).toBe(SI_FOLLOWUP_MIN_MS);
    expect(siFollowupClamp(-1)).toBe(SI_FOLLOWUP_MIN_MS);
    expect(siFollowupClamp(40000)).toBe(40000);
    expect(siFollowupClamp(160000)).toBe(SI_FOLLOWUP_MAX_MS);
  });
});

describe('🩳 siFlags', () => {
  it('well-formed flags come back in the served order', () => {
    expect(siFlags(rd({ status: 'ok', flags: SMTK_FLAGS }))).toEqual(SMTK_FLAGS);
  });

  it('NEGATIVE: flags not an array → []', () => {
    for (const f of [null, undefined, 'x', 3, { key: 'split' }]) expect(siFlags(rd({ status: 'ok', flags: f }))).toEqual([]);
    expect(siFlags(rd(undefined))).toEqual([]);
    expect(siFlags(null)).toEqual([]);
  });

  it('NEGATIVE: entries missing short / key, non-string fields, nulls, numbers → dropped', () => {
    const junk = [
      { key: 'split', emoji: '✂️', text: 'no short' },
      { key: 'split', emoji: '✂️', short: '', text: 'empty short' },
      { key: '', emoji: '✂️', short: '✂️ s', text: 't' },
      { key: 'split', emoji: 1, short: '✂️ s', text: 't' },
      { key: 'split', emoji: '✂️', short: '✂️ s', text: null },
      { key: 'split', emoji: '✂️', short: NaN, text: 't' },
      null, 7, 'flag', [],
    ];
    expect(siFlags(rd({ status: 'ok', flags: [...junk, SMTK_FLAGS[1]] }))).toEqual([SMTK_FLAGS[1]]);
    expect(siFlags(rd({ status: 'ok', flags: junk }))).toEqual([]);
  });
});

describe('🩳 parseSiMap passes `basis` through untouched', () => {
  it('the served chip stays verbatim and basis rides along', () => {
    const chip = '🩳 SI 8.9% shs out · 1.0d · 10/30 · ⚠️ float stale · ✂️ split 11/23 · 📄 S-4 11/13';
    const basis = { status: 'ok', float_refused: 'diluted', flags: SMTK_FLAGS, pending: true, retry_after_sec: 20 };
    const got = parseSiMap({ items: { smtk: { symbol: 'SMTK', status: 'ok', chip, title: 'served title', rows: [], basis } }, n: 1, max_symbols: 200 });
    expect(got.SMTK.basis).toEqual(basis);
    expect(siChip(got.SMTK)!.text).toBe(chip);
    expect(siBasisPending(got.SMTK)).toBe(20000);
    expect(siFlags(got.SMTK).map((f) => f.key)).toEqual(['float_stale', 'split', 'filing']);
  });
});
