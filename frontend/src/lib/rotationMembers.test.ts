/* rotationMembers — the pure half of the Hot sectors member popover.
 *
 * The load-bearing test here is `sampleVsFullLine`: the panel's whole honesty
 * rests on that one sentence, so its wording is pinned rather than left to
 * drift. The rest guard the two ways this table could lie — a NaN rendered as
 * a number, and a ranking that does not match the label above it.
 */
import { describe, it, expect } from 'vitest';
import {
  compareTraction, coverageLine, fmtPts, fmtRel, membersUrl,
  normalizeMembers, sampleVsFullLine, sortLine,
  type MemberRow, type MembersPayload,
} from './rotationMembers';

const member = (over: Partial<MemberRow> & { symbol: string }): MemberRow => ({
  rel_5d: null, rel_21d: null, rel_63d: null, vs_group_21d: null,
  traction_score: null, traction: false, ...over,
});

describe('fmtRel / fmtPts — a NaN is never a number', () => {
  it('signs and rounds to one decimal', () => {
    expect(fmtRel(5.74)).toBe('+5.7%');
    expect(fmtRel(-0.24)).toBe('-0.2%');
    expect(fmtRel(0)).toBe('0.0%');
    expect(fmtPts(3.56)).toBe('+3.6');
  });
  it('NEGATIVE: null, undefined and NaN all print an em dash', () => {
    expect(fmtRel(null)).toBe('—');
    expect(fmtRel(undefined)).toBe('—');
    expect(fmtRel(NaN)).toBe('—');
    expect(fmtPts(NaN)).toBe('—');
    expect(fmtRel(Infinity)).toBe('—');
  });
});

describe('sampleVsFullLine — the sentence the panel turns on', () => {
  it('names the chip number, the sample and the full membership', () => {
    expect(sampleVsFullLine({ sample_n: 25, n_members: 348, sampled: true }, 5.7)).toBe(
      "The chip's +5.7% is the median of a 25-name sample of this group; "
      + 'this table is all 348 members — two different sets, so the two are '
      + 'not expected to reconcile.',
    );
  });
  it('stays true when the payload is missing its counts', () => {
    const line = sampleVsFullLine(null, null);
    expect(line).toMatch(/^The chip's headline number is the median of a sampled subset/);
    expect(line).toMatch(/the full membership/);
    expect(line).toMatch(/not expected to reconcile/);
  });
});

describe('sortLine — the ranking is never mysterious', () => {
  it('prints the backend definition verbatim', () => {
    expect(sortLine({ ranked_by: 'traction_score', traction_def: '21d rel minus 63d rel' } as MembersPayload))
      .toBe('Sorted by traction, strongest first — 21d rel minus 63d rel');
  });
  it('NEGATIVE: never invents a definition it does not own', () => {
    const l = sortLine({ ranked_by: 'traction_score' } as MembersPayload);
    expect(l).toBe('Sorted by `traction_score`, strongest first (backend order)');
    expect(sortLine(null)).toBe('Sorted in the order the backend returned');
  });
});

describe('coverageLine — what was dropped is counted, not swallowed', () => {
  it('prints members, priced, dropped and the band date', () => {
    expect(coverageLine({
      n_members: 348, n_priced: 342, n_dropped: 6,
      demand_covered: 180, demand_as_of: '2026-09-09',
    } as MembersPayload))
      .toBe('348 members · 342 priced · 6 dropped (dead or stale series) · 180 with zone coverage · bands 2026-09-09');
  });
  it('omits the dropped clause when nothing was dropped', () => {
    expect(coverageLine({ n_members: 12, n_priced: 12, n_dropped: 0 } as MembersPayload))
      .toBe('12 members · 12 priced');
  });
});

describe('compareTraction — unscored names sort last, never first', () => {
  it('orders strongest first', () => {
    const rows = [
      member({ symbol: 'A', traction_score: 1.2 }),
      member({ symbol: 'B', traction_score: null }),
      member({ symbol: 'C', traction_score: 9.9 }),
      member({ symbol: 'D', traction_score: -4 }),
    ].sort(compareTraction);
    expect(rows.map((r) => r.symbol)).toEqual(['C', 'A', 'D', 'B']);
  });
  it('NEGATIVE: a NaN score is not treated as a big number', () => {
    const rows = [
      member({ symbol: 'NAN', traction_score: NaN }),
      member({ symbol: 'REAL', traction_score: 0.1 }),
    ].sort(compareTraction);
    expect(rows[0].symbol).toBe('REAL');
  });
});

describe('normalizeMembers — a hostile payload still renders', () => {
  it('scrubs NaN, upper-cases symbols and applies the traction order', () => {
    const p = normalizeMembers({
      // The ENDPOINT's key names (rows / traction number / gaining bool) —
      // not the reader's old invented ones, which is how this file stayed
      // green while every live popover rendered nothing.
      grain: 'cohort', group: 'Technology · large caps',
      n_full: 348, priced: 342, unpriced: 6, n_population: 25, sampled: true,
      rows: [
        { symbol: 'msft', rel_21d: NaN, traction: 2, gaining: 1 },
        { symbol: 'NVDA', rel_21d: 8.2, traction: 7, gaining: true },
      ],
    });
    expect(p!.members.map((m) => m.symbol)).toEqual(['NVDA', 'MSFT']);
    expect(p!.members[1].rel_21d).toBeNull();
    // `traction: 1` is not `true` — the flag is the backend's, read strictly.
    expect(p!.members[1].traction).toBe(false);
  });
  it('NEGATIVE: junk in, no throw out', () => {
    expect(normalizeMembers(null)).toBeNull();
    expect(normalizeMembers('nope')).toBeNull();
    const p = normalizeMembers({ group: 'x', rows: 'not-an-array' });
    expect(p!.members).toEqual([]);
    expect(p!.n_members).toBe(0);
  });
  it('drops member entries with no symbol rather than rendering a blank row', () => {
    const p = normalizeMembers({ group: 'x', rows: [{ rel_21d: 1 }, { symbol: 'AAPL' }] });
    expect(p!.members.map((m) => m.symbol)).toEqual(['AAPL']);
  });
});

describe('membersUrl', () => {
  it('carries the clicked label plus the cohort keys', () => {
    expect(membersUrl('/api', 'cohort', { group: 'Technology · large caps', sector: 'Technology', tier: 'large' }))
      .toBe('/api/rotation/members?kind=cohort&group=Technology+%C2%B7+large+caps&sector=Technology&tier=large');
  });
  it('sends only what the row has', () => {
    expect(membersUrl('/api', 'theme', { group: 'robotics' }))
      .toBe('/api/rotation/members?kind=theme&group=robotics');
  });
});
