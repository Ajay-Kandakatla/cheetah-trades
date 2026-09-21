import { describe, it, expect } from 'vitest';
import {
  PICK_CHIP_ORDER, WHY_TEXT, computedCriteria, coverageSentence, criterionOf,
  fmtValue, legChip, type BondeCriterion, type BondePickLeg,
} from './bondePicks';
import { UNVERIFIED_TITLE } from './bondeLive';

/* 📋 The pick line's formatting rules, pinned row by row.
 *
 * The negatives are the file. Three of them protect readings that would look
 * perfectly fine on screen and be wrong:
 *   · an UNKNOWN leg wearing a tick (most of these read out of caches that may
 *     never have been warmed — "we have not looked" is not "it qualifies");
 *   · a bare tick on a year-over-year pair nobody could verify;
 *   · a count of passes rendered as if it ranked the name.
 */

const crit = (over: Partial<BondeCriterion> = {}): BondeCriterion => ({
  key: 'eps_yoy_100', label: 'Earnings +100% year over year',
  quote: 'a significant earnings acceleration compared to last year same quarter',
  url: 'https://stockbee.blogspot.com/2010/02/what-are-episodic-pivots-and-how-to.html',
  date: '2010-02-12', source: 'stockbee', data: 'quarterly EPS series off the scan row',
  computed: true, not_computed_why: null, his_call: null, ...over,
});

const leg = (over: Partial<BondePickLeg> = {}): BondePickLeg =>
  ({ ok: true, value: 140, why: null, ...over });

describe('legChip — the five rows of the pinned table', () => {
  it('row 1 — a clean pass is the value, the unit and a tick', () => {
    const c = legChip('eps_yoy_100', leg(), crit())!;
    expect(c.text).toBe('EPS +140% y/y ✓');
    expect(c.glyph).toBe('✓');
    expect(c.tone).toBe('bd-pick-ok');
    expect(c.title).toContain('Earnings +100% year over year');
    expect(c.title).toContain('compared to last year same quarter');
  });

  it('row 2 — an UNVERIFIABLE pair prints the number, marked unverified', () => {
    // `period_ok: null` is not `period_ok: true`. The number is computed and
    // shown (the tiers already do), but it never wears a bare tick.
    const c = legChip('eps_yoy_100', leg({ why: 'no_period_keys' }), crit())!;
    expect(c.text).toBe('EPS +140% y/y ✓ · unverified');
    expect(c.tone).toBe('bd-pick-ok');
    expect(c.title).toContain(UNVERIFIED_TITLE);
  });

  it('row 3 — a stale read keeps its tick and says it is stale', () => {
    // Rule #7: staleness is a LABEL on the as-of date. It never flips `ok`.
    const s = legChip('surprise',
                      leg({ value: 12, as_of: '2026-03-02', stale: true, age_days: 200 }),
                      crit({ key: 'surprise', label: 'Beats analyst estimate' }))!;
    expect(s.text).toBe('Surprise +12% ✓ · stale');
    expect(s.tone).toBe('bd-pick-ok');
    expect(s.title).toMatch(/older than/);
    expect(s.title).toContain('report');
    expect(s.title).toContain('as of 2026-03-02');

    const d = legChip('short_dtc_5',
                      leg({ value: 6.1, as_of: '2026-04-15', stale: true, age_days: 158 }),
                      crit({ key: 'short_dtc_5', label: '5 plus days to cover' }))!;
    expect(d.text).toBe('DTC 6.1 ✓ · stale');
    expect(d.title).toMatch(/settlement is older than/);
  });

  it('row 4 — a fail is the value and a cross', () => {
    const c = legChip('float_25m', leg({ ok: false, value: 140_000_000 }),
                      crit({ key: 'float_25m', label: 'Float below 25 million' }))!;
    expect(c.text).toBe('Float 140M ✗');
    expect(c.glyph).toBe('✗');
    expect(c.tone).toBe('bd-pick-no');
  });

  it('row 5 — NEGATIVE: an unknown leg is an em-dash, dim, with the reason', () => {
    const c = legChip('float_25m', { ok: null, value: null, why: 'no_metrics_doc' },
                      crit({ key: 'float_25m', label: 'Float below 25 million' }))!;
    expect(c.text).toBe('Float —');
    expect(c.glyph).toBe('—');
    expect(c.tone).toBe('bd-dim');
    expect(c.title).toContain(WHY_TEXT.no_metrics_doc);
    // the thing this whole tri-state exists to prevent
    expect(c.text).not.toContain('✓');
    expect(c.text).not.toContain('✗');
  });

  it('NEGATIVE — an unknown short-interest leg says NOT WARMED, not "low"', async () => {
    const c = legChip('short_dtc_5', { ok: null, value: null, why: 'not_warmed' },
                      crit({ key: 'short_dtc_5' }))!;
    expect(c.tone).toBe('bd-dim');
    expect(c.title).toMatch(/has not been warmed/);
    expect(c.title).not.toMatch(/\bfail/i);
  });

  it('carries the served his_call sentence into the tooltip', () => {
    const c = legChip('neglect_analysts',
                      leg({ value: 0, source: 'Yahoo carries no estimate rows',
                            his_call: 'whether an empty estimate frame is his “no analyst coverage”' }),
                      crit({ key: 'neglect_analysts', label: 'No analyst coverage' }))!;
    expect(c.text).toBe('Analysts 0 ✓');
    expect(c.title).toContain('Ajay’s call:');
    expect(c.title).toContain('Yahoo carries no estimate rows');
  });

  it('a missing leg yields no chip at all', () => {
    expect(legChip('float_25m', undefined, crit())).toBeNull();
    expect(legChip('float_25m', null, crit())).toBeNull();
  });
});

describe('the six', () => {
  it('PICK_CHIP_ORDER is exactly six, in the shipped order', () => {
    expect(PICK_CHIP_ORDER.length).toBe(6);
    expect([...PICK_CHIP_ORDER]).toEqual([
      'eps_yoy_100', 'rev_39_x2', 'surprise', 'float_25m', 'ipo_10y', 'short_dtc_5',
    ]);
  });

  it('NEGATIVE — sales_5 is NOT one of the six', () => {
    // Every row the board draws has already cleared his 5% floor, so a ✓ there
    // is a fact of the section, not information about the name. It lives in
    // the expand; the two-quarter revenue leg takes the slot.
    expect([...PICK_CHIP_ORDER]).not.toContain('sales_5');
    expect([...PICK_CHIP_ORDER]).toContain('rev_39_x2');
  });
});

describe('WHY_TEXT is the backend vocabulary, one sentence each', () => {
  const CODES = [
    'no_eps_series', 'year_ago_loss', 'pair_not_a_year_apart', 'no_period_keys',
    'prior_hole', 'no_sales_read', 'no_inst_read', 'no_sector',
    'no_threshold_in_his_writing',
    'seq_base_non_positive', 'seq_base_too_small', 'seq_base_unknown',
    'seq_not_adjacent',
    'not_on_calendar', 'no_surprise_in_report',
    'no_metrics_doc', 'no_float_in_doc', 'no_cap_in_doc',
    'not_warmed', 'no_si_record',
    'no_analyst_doc', 'no_estimate_read',
    'no_listing_date', 'future_listing_date',
  ];

  it('has exactly the 24 codes', () => {
    expect(Object.keys(WHY_TEXT).sort()).toEqual([...CODES].sort());
    expect(CODES.length).toBe(24);
  });

  it('NEGATIVE — no code renders an empty tooltip', () => {
    for (const [k, v] of Object.entries(WHY_TEXT)) {
      expect(v.trim().length, k).toBeGreaterThan(10);
    }
  });
});

describe('fmtValue', () => {
  it('formats each criterion the way his sentence reads it', () => {
    expect(fmtValue('cap_10b', 1e10)).toBe('$10B');
    expect(fmtValue('float_25m', 1.8e7)).toBe('18M');
    expect(fmtValue('float_25m', 2.49e7)).toBe('24.9M');
    expect(fmtValue('ipo_10y', 3.2)).toBe('3.2y');
    expect(fmtValue('surprise', 12)).toBe('+12%');
    expect(fmtValue('short_dtc_5', 6.14)).toBe('6.1');
    expect(fmtValue('short_dtc_5', 5)).toBe('5');
    expect(fmtValue('eps_5c', 0.05)).toBe('$0.05');
    expect(fmtValue('sector_3', 'Consumer Cyclical')).toBe('Consumer Cyclical');
  });

  it('a PAIR keeps both halves, never a ratio', () => {
    expect(fmtValue('rev_39_x2', { now: 45, prior: 52 })).toBe('+45%/+52%');
    expect(fmtValue('rev_39_x2', { now: 45, prior: null })).toBe('+45%/—');
  });

  it('NEGATIVE — a null or non-finite value is an em-dash, never 0', () => {
    expect(fmtValue('float_25m', null)).toBe('—');
    expect(fmtValue('float_25m', undefined)).toBe('—');
    expect(fmtValue('surprise', NaN)).toBe('—');
    expect(fmtValue('rev_39_x2', { now: null, prior: null })).toBe('—');
  });
});

describe('the legend helpers', () => {
  const legend = {
    header: 'A pick list of his STATIC criteria — entries are yours.',
    criteria: [
      crit(),
      crit({ key: 'run_up_65d', label: '65-day run-up', computed: false,
             not_computed_why: 'price-derived; his correction asks for static info only' }),
    ],
  };

  it('computedCriteria drops the legend-only sentences', () => {
    expect(computedCriteria(legend).map((c) => c.key)).toEqual(['eps_yoy_100']);
  });

  it('NEGATIVE — a legend-only criterion yields no chip on a row', () => {
    // It has no leg, so there is nothing to draw and nothing is drawn.
    expect(legChip('run_up_65d', undefined, legend.criteria[1])).toBeNull();
  });

  it('criterionOf finds the served sentence, or null', () => {
    expect(criterionOf(legend, 'eps_yoy_100')?.date).toBe('2010-02-12');
    expect(criterionOf(legend, 'nope')).toBeNull();
    expect(criterionOf(null, 'eps_yoy_100')).toBeNull();
  });
});

describe('the coverage sentence', () => {
  it('says how many rows each chip actually knows', () => {
    const s = coverageSentence({
      eps_yoy_100: { known: 190, rows: 199 },
      rev_39_x2: { known: 188, rows: 199 },
      surprise: { known: 53, rows: 199 },
      float_25m: { known: 169, rows: 199 },
      ipo_10y: { known: 199, rows: 199 },
      short_dtc_5: { known: 0, rows: 199 },
    })!;
    expect(s).toContain('float 169 of 199');
    expect(s).toContain('earnings surprise 53 of 199');
  });

  it('NEGATIVE — an unwarmed leg says so rather than reading as a zero', () => {
    const s = coverageSentence({ short_dtc_5: { known: 0, rows: 199 } })!;
    expect(s).toContain('short interest 0 of 199 (not warmed)');
  });

  it('NEGATIVE — no coverage block means no sentence, not "0 of 0"', () => {
    expect(coverageSentence(null)).toBeNull();
    expect(coverageSentence({})).toBeNull();
  });
});

describe('NEGATIVE — the pick line is STATIC, and it is not a rank', () => {
  /* Vite's `?raw` (typed by src/test/vite-raw.d.ts): the module's own text, so
   * the rule is enforced on the source rather than on what happens to render. */
  const source = async () => (await import('./bondePicks.ts?raw')).default as string;

  it('reads no dynamic leg — his correction (2) forbids it', async () => {
    // "momentum does not need to be a criteria for his pics … I am looking fro
    // static info". Nothing here may reach a session, a price or a ranking.
    const src = await source();
    for (const token of ['today_pct', 'rs_rank', 'rel_', 'persistence',
                         'mo' + 'mentum']) {
      expect(src.includes(token), token).toBe(false);
    }
  });

  it('counts nothing — no tally, ratio or score is rendered', async () => {
    const src = await source();
    for (const token of ['n_' + 'pass', 'n_' + 'fail', 'n_' + 'unknown',
                         'pickCounts']) {
      expect(src.includes(token), token).toBe(false);
    }
  });
});
