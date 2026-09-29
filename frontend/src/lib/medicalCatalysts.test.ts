/* 🧬 medicalCatalysts helpers — grouping keeps the SERVED family order, an
 * unknown family never vanishes, filters match served keys only, and every
 * push state reads as words (never a raw state id, never "bounce"). */
import { describe, expect, it } from 'vitest';
import {
  OTHER_FAMILY, directionClass, etClock, filterEvents, fmtMovePct, fmtUsd, groupByFamily, labelFor,
  pushChipText, pushChipTone, sortRollup, type MedEventRow, type RollRow,
} from './medicalCatalysts';
import { KOD_ROW, MED_BOARD, MED_EVENTS } from './__fixtures__/medicalCatalysts';

const FAMS = MED_BOARD.taxonomy.families;

describe('groupByFamily', () => {
  it('keeps the served family order and drops empty families', () => {
    const g = groupByFamily(MED_EVENTS, FAMS);
    expect(g.map((x) => x.key)).toEqual(['fda', 'trial', 'conference']);
    expect(g[0].events.map((e) => e.ticker)).toEqual(['HUMA', 'MIRM', null]);
    expect(g[1].events.map((e) => e.event_key)).toEqual([
      'KOD|topline_positive|2026-09-28', 'MIRM|topline_positive|2026-09-28', 'MNOV|topline_unknown|2026-09-28']);
  });

  it('a reversed served order is followed, not re-sorted', () => {
    const g = groupByFamily(MED_EVENTS, [...FAMS].reverse());
    expect(g.map((x) => x.key)).toEqual(['conference', 'trial', 'fda']);
  });

  it('NEGATIVE: an unknown family lands in one trailing `other` bucket, never disappears', () => {
    const odd: MedEventRow = { ...KOD_ROW, event_key: 'X|new_kind|2026-09-28', family: 'brand_new_family' };
    const g = groupByFamily([...MED_EVENTS, odd], FAMS);
    expect(g[g.length - 1].key).toBe(OTHER_FAMILY.key);
    expect(g[g.length - 1].events).toEqual([odd]);
    expect(g.flatMap((x) => x.events)).toHaveLength(MED_EVENTS.length + 1);
  });

  it('no events → no groups', () => {
    expect(groupByFamily([], FAMS)).toEqual([]);
  });
});

describe('filterEvents', () => {
  it('modality "unclassified" matches only rows the backend could not classify', () => {
    const out = filterEvents(MED_EVENTS, { modality: 'unclassified' });
    expect(out.map((e) => e.ticker).sort()).toEqual(['HUMA', 'MNOV']);
  });

  it('area "unclassified" never returns a classified row (NEGATIVE)', () => {
    const out = filterEvents(MED_EVENTS, { area: 'unclassified' });
    expect(out.every((e) => e.areas.includes('unclassified'))).toBe(true);
    expect(out.map((e) => e.ticker)).not.toContain('KOD');
  });

  it('highOnly keeps impact === "high" only', () => {
    const out = filterEvents(MED_EVENTS, { highOnly: true });
    expect(out.every((e) => e.impact === 'high')).toBe(true);
    expect(out.map((e) => e.ticker)).not.toContain('MNOV');
    expect(out.map((e) => e.ticker)).not.toContain('MRNA');
  });

  it('families: empty = all; a list = only those', () => {
    expect(filterEvents(MED_EVENTS, { families: [] })).toHaveLength(MED_EVENTS.length);
    expect(filterEvents(MED_EVENTS, { families: ['conference'] }).map((e) => e.ticker)).toEqual(['MRNA']);
  });

  it('filters combine (AND)', () => {
    expect(filterEvents(MED_EVENTS, { area: 'ophthalmology', highOnly: true }).map((e) => e.ticker)).toEqual(['KOD']);
    expect(filterEvents(MED_EVENTS, { area: 'ophthalmology', families: ['fda'] })).toEqual([]);
  });
});

describe('formatting', () => {
  it('fmtMovePct', () => {
    expect(fmtMovePct(178)).toBe('+178.0%');
    expect(fmtMovePct(-1.94)).toBe('-1.9%');
    expect(fmtMovePct(0)).toBe('+0.0%');
  });
  it('NEGATIVE: fmtMovePct(null / undefined / NaN) → "—", never "+NaN%"', () => {
    expect(fmtMovePct(null)).toBe('—');
    expect(fmtMovePct(undefined)).toBe('—');
    expect(fmtMovePct(Number.NaN)).toBe('—');
  });
  it('fmtUsd', () => {
    expect(fmtUsd(22_700_000)).toBe('$22.7M');
    expect(fmtUsd(3_449_331_200)).toBe('$3.45B');
    expect(fmtUsd(null)).toBe('—');
  });
  it('etClock reads HH:MM off the served ET stamp, no timezone shift', () => {
    expect(etClock('2026-09-28T04:05:40-04:00')).toBe('04:05');
    expect(etClock(null)).toBeNull();
    expect(etClock('not a stamp')).toBeNull();
  });
  it('labelFor uses the served label, else the readable key (never a guess)', () => {
    expect(labelFor({ mrna: 'mRNA' }, 'mrna')).toBe('mRNA');
    expect(labelFor(undefined, 'rare_disease')).toBe('rare disease');
  });
  it('directionClass', () => {
    expect(directionClass('positive')).toBe('mc-dir--pos');
    expect(directionClass('negative')).toBe('mc-dir--neg');
    expect(directionClass('mixed')).toBe('mc-dir--mixed');
    expect(directionClass('unknown')).toBe('mc-dir--unknown');
    expect(directionClass(null)).toBe('mc-dir--unknown');
  });
});

describe('pushChipText — every state', () => {
  const cases: Array<[any, string]> = [
    [{ state: 'pushed', at_et: '2026-09-28T04:05:40-04:00' }, '🔔 pushed 04:05'],
    [{ state: 'pushed' }, '🔔 pushed'],
    [{ state: 'muted' }, 'muted'],
    [{ state: 'baseline' }, 'baseline'],
    [{ state: 'pending' }, 'pending'],
    [{ state: 'not_eligible' }, 'not a push type'],
    [{ state: 'not_eligible', reason: 'not_high_impact' }, 'not a push type'],
    [{ state: 'not_eligible', reason: 'unresolved_ticker' }, 'not rung: no ticker'],
    [{ state: 'not_eligible:recap' }, 'not rung: repeat of the same kind'],
    [{ state: 'blocked:blocked_price' }, 'blocked: under $2'],
    [{ state: 'blocked:price' }, 'blocked: under $2'],
    [{ state: 'blocked:blocked_dollar_vol' }, 'blocked: thin'],
    [{ state: 'blocked:blocked_unknown_liquidity' }, 'blocked: liquidity unknown'],
    [{ state: 'blocked:stale' }, 'not rung: the session already traded it'],
    [{ state: 'blocked:closed_day' }, 'held: market closed'],
    [{ state: 'blocked:claimed_elsewhere' }, 'already rung'],
    [{ state: 'blocked', reason: 'blocked_price' }, 'blocked: under $2'],
  ];
  it.each(cases)('%j → %s', (push, text) => {
    expect(pushChipText(push)).toBe(text);
  });
  it('NEGATIVE: a missing push record and an unknown blocked reason still read as words', () => {
    expect(pushChipText(null)).toBe('no push record');
    expect(pushChipText({ state: '' })).toBe('no push record');
    expect(pushChipText({ state: 'blocked:brand_new_gate' })).toBe('blocked: brand new gate');
    for (const [p] of cases) expect(pushChipText(p)).not.toMatch(/bounce|_/i);
  });
  it('tone: pushed is on, pending / closed-day held, everything else off', () => {
    expect(pushChipTone({ state: 'pushed' })).toBe('on');
    expect(pushChipTone({ state: 'pending' })).toBe('held');
    expect(pushChipTone({ state: 'blocked:closed_day' })).toBe('held');
    expect(pushChipTone({ state: 'blocked:blocked_price' })).toBe('off');
    expect(pushChipTone(null)).toBe('off');
  });
});

describe('sortRollup', () => {
  const rows = MED_BOARD.rollup.by_area;
  it("'n_events' keeps the served order", () => {
    expect(sortRollup(rows, 'n_events').map((r) => r.key)).toEqual(rows.map((r) => r.key));
  });
  it('a median sort is descending with nulls last', () => {
    const withNull: RollRow[] = [...rows, { ...rows[0], key: 'nullrow', median_ret_5d_pct: null }];
    const five = withNull.map((r, i) => (r.key === 'nullrow' ? r : { ...r, median_ret_5d_pct: i }));
    const out = sortRollup(five, 'median_ret_5d_pct');
    expect(out[out.length - 1].key).toBe('nullrow');
    const vals = out.slice(0, -1).map((r) => r.median_ret_5d_pct as number);
    expect(vals).toEqual([...vals].sort((a, b) => b - a));
    expect(sortRollup(rows, 'median_day_pct')[0].key).toBe('ophthalmology');
  });
  it('NEGATIVE: sorting never mutates the served array', () => {
    const before = rows.map((r) => r.key);
    sortRollup(rows, 'median_day_pct');
    expect(rows.map((r) => r.key)).toEqual(before);
  });
});
