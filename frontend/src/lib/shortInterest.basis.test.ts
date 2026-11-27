import { describe, it, expect } from 'vitest';
import {
  parseSiMap, siBasisPending, siFlags, siFollowupClamp, siChip, siIssuances,
  SI_FOLLOWUP_MIN_MS, SI_FOLLOWUP_MAX_MS, SI_FILING_URL_PREFIX, type ShortInterestRead,
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

/* 🩳 siIssuances (2026-11-26, spec sishares §3.6 / §4.4). Ajay: "Fix the POM chip and the 6-K dilution check." The served
 * `basis.issuances` → {label, text, url | null}; the link is kept ONLY with SI_FILING_URL_PREFIX. NEGATIVES: http:// ·
 * another host · a look-alike host · javascript: · a missing label · a non-array → no link. */
describe('🩳 siIssuances', () => {
  const POM_URL = 'https://www.sec.gov/Archives/edgar/data/1877971/000121390026116021/ea0310863-6k_pomdoctor.htm';
  const iss = (over: Record<string, unknown> = {}) => ({ form: '6-K', filed: '2026-11-04', accn: '0001213900-26-116021',
    shares: 33185841, url: POM_URL, label: 'served 6-K 11/4 label', text: 'served 6-K issuance text', before_float: true, ...over });

  it('the prefix is the EDGAR archive path on www.sec.gov over https', () => {
    expect(SI_FILING_URL_PREFIX).toBe('https://www.sec.gov/Archives/edgar/data/');
  });

  it('a served issuance → its label, text and the served link, in the served order', () => {
    const second = iss({ url: null, label: 'served second label', text: 'served second text' });
    expect(siIssuances(rd({ status: 'ok', issuances: [iss(), second] }))).toEqual([
      { label: 'served 6-K 11/4 label', text: 'served 6-K issuance text', url: POM_URL },
      { label: 'served second label', text: 'served second text', url: null },
    ]);
  });

  it('NEGATIVE: http:// · another host · a look-alike host · javascript: · data: · protocol-relative · a non-string · a quote / space → no link', () => {
    for (const url of ['http://www.sec.gov/Archives/edgar/data/1877971/x/y.htm', 'https://evil.example/Archives/edgar/data/1/x/y.htm',
      'https://www.sec.gov.evil.com/Archives/edgar/data/1/x/y.htm', 'https://sec.gov/Archives/edgar/data/1/x/y.htm',
      'https://www.sec.gov/cgi-bin/browse-edgar?x=1', 'javascript:alert(1)', 'data:text/html,x', '//www.sec.gov/Archives/edgar/data/1/x',
      ' https://www.sec.gov/Archives/edgar/data/1/x/y.htm', 'https://www.sec.gov/Archives/edgar/data/1/x/y.htm" onclick="x',
      'https://www.sec.gov/Archives/edgar/data/1/x y.htm', 'HTTPS://WWW.SEC.GOV/Archives/edgar/data/1/x', 7, null, undefined, {}, []]) {
      const out = siIssuances(rd({ issuances: [iss({ url })] }));
      expect(out, String(url)).toHaveLength(1);
      expect(out[0].url, String(url)).toBeNull();
    }
  });

  it('NEGATIVE: a missing / empty / non-string label drops the entry; a non-string text reads ""', () => {
    for (const label of [undefined, null, '', '   ', 7, NaN, {}]) {
      expect(siIssuances(rd({ issuances: [iss({ label })] })), String(label)).toEqual([]);
    }
    expect(siIssuances(rd({ issuances: [iss({ text: NaN })] }))[0].text).toBe('');
  });

  it('NEGATIVE: a non-array issuances / junk entries / no basis / an older API / no read → []', () => {
    for (const issuances of [undefined, null, 'x', 7, {}, { 0: iss() }]) expect(siIssuances(rd({ issuances })), String(issuances)).toEqual([]);
    expect(siIssuances(rd({ issuances: [null, 'x', 3, [iss()], iss()] }))).toHaveLength(1);
    for (const basis of [undefined, null, 'x', [], [{ issuances: [iss()] }]]) expect(siIssuances(rd(basis)), String(basis)).toEqual([]);
    expect(siIssuances(null)).toEqual([]);
    expect(siIssuances(undefined)).toEqual([]);
  });
});
