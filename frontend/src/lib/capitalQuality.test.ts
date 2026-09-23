import { describe, it, expect } from 'vitest';
import {
  capitalCoverage, componentKeys, componentLine, componentStats, gradeCell,
  failedComponent, partitionCapital, readOf,
  visibleComponentCounts, visibleCounts,
  type CapitalQuality, type CapitalQualitySummary,
} from './capitalQuality';

/* 💎 capitalQuality — the FE renderer for growth/capital_quality.py.
 *
 * The two rules the whole package rests on, tested first and hardest:
 *   UNKNOWN IS NEVER FAILED — a question the filings could not answer is not a
 *   no, and no chip may hide a row for it.
 *   NOTHING IS SILENTLY LOST — a row with no read at all is kept, put last, and
 *   counted separately.
 */

const P = (detail: string) => ({ verdict: 'pass', reason: null, detail });
const F = (detail: string) => ({ verdict: 'fail', reason: null, detail });
const U = (reason: string) => ({ verdict: 'unknown', reason, detail: null });

const ORDER = ['net_cash', 'positive_fcf', 'no_dilution', 'positive_roce',
               'roce_above_sector', 'capex_below_sector'];

function q(components: Record<string, unknown>, over: Partial<CapitalQuality> = {}): CapitalQuality {
  const vals = Object.values(components) as { verdict: string }[];
  const passed = vals.filter((v) => v.verdict === 'pass').length;
  const failed = vals.filter((v) => v.verdict === 'fail').length;
  const answered = passed + failed;
  return {
    grade: answered <= 0 ? 'unknown'
      : passed === answered ? 'all'
      : passed === 0 ? 'none'
      : passed * 2 > answered ? 'most' : 'some',
    passed, failed, unknown: vals.length - answered, answered,
    rank_key: answered > 0 ? passed : null,
    components: components as CapitalQuality['components'],
    period: 'FY2026 Q2', period_end: '2026-07-31', measured: false,
    ...over,
  };
}

const SUMMARY: CapitalQualitySummary = {
  n: 3,
  grades: { all: 1, most: 0, some: 0, none: 1, unknown: 1 },
  components: [
    { key: 'net_cash', kind: 'definitional', label: 'Holds more cash than debt',
      pass_n: 1, fail_n: 1, unknown_n: 1, hides_n: 1 },
    { key: 'positive_roce', kind: 'definitional', label: 'Earns a positive return on capital',
      pass_n: 1, fail_n: 1, unknown_n: 1, hides_n: 1 },
    { key: 'capex_below_sector', kind: 'relative', label: 'Ties up less capital than its sector',
      pass_n: 1, fail_n: 1, unknown_n: 1, hides_n: 1 },
  ],
  all_pass_n: 1, no_fail_n: 2,
  peers: { available: true, n_docs: 413, min_peers: 20, sectors: {} },
  measured: false,
  measured_note: 'It is a screen, not an edge.',
  study_script: 'backend/scripts/capital_quality_study.py',
};

describe('readOf — a row without a read is a blank, never a grade', () => {
  it('reads a served block', () => {
    const row = { capital_quality: q({ net_cash: P('cash > debt') }) };
    expect(readOf(row)?.grade).toBe('all');
  });

  it.each([
    ['no key at all', {}],
    ['null', { capital_quality: null }],
    ['a string', { capital_quality: 'all' }],
    ['a number', { capital_quality: 4 }],
    ['an object with no grade', { capital_quality: { passed: 3 } }],
    ['an empty grade', { capital_quality: { grade: '' } }],
  ])('NEGATIVE: %s reads as no read', (_label, row) => {
    expect(readOf(row)).toBeNull();
  });

  it('NEGATIVE: a null row does not throw', () => {
    expect(readOf(null)).toBeNull();
    expect(readOf(undefined)).toBeNull();
  });
});

describe('failedComponent — the one place "unknown is not failed" is spelled', () => {
  const read = q({ net_cash: F('cash <= debt'), positive_roce: U('missing_roce'),
                   capex_below_sector: P('2.4% vs 6.0%') });

  it('a fail is a fail', () => expect(failedComponent(read, 'net_cash')).toBe(true));

  it.each([
    ['an unknown question', 'positive_roce'],
    ['a passing question', 'capex_below_sector'],
    ['a question that is not on the row at all', 'no_dilution'],
  ])('NEGATIVE: %s is not a failure', (_l, key) => {
    expect(failedComponent(read, key)).toBe(false);
  });

  it('NEGATIVE: a null read fails nothing', () => {
    expect(failedComponent(null, 'net_cash')).toBe(false);
  });
});

describe('partitionCapital', () => {
  const ROWS = [
    { symbol: 'FF', capital_quality: q({ net_cash: F('cash <= debt'), positive_roce: F('ROCE -17.03%') }) },
    { symbol: 'NLY', capital_quality: q({ net_cash: U('missing_cash_or_debt'), positive_roce: U('non_operating_sector') }) },
    { symbol: 'NVDA', capital_quality: q({ net_cash: P('cash > debt'), positive_roce: P('ROCE 100.40%') }) },
    { symbol: 'ZZZZ' },                                   // never read at all
  ];
  const read = (r: { symbol: string }) => readOf(r);

  it('no chip on is the shipped board, row for row', () => {
    const p = partitionCapital(ROWS, read, new Set<string>(), ORDER);
    expect(p.rows).toEqual(ROWS);
    expect(p.hidden).toBe(0);
    expect(p.unread).toBe(0);
    expect(p.hiddenByKey).toEqual({});
  });

  it('a chip hides the failures and nothing else', () => {
    const p = partitionCapital(ROWS, read, new Set(['net_cash']), ORDER);
    expect(p.rows.map((r) => r.symbol)).toEqual(['NLY', 'NVDA', 'ZZZZ']);
    expect(p.hidden).toBe(1);
    expect(p.hiddenByKey).toEqual({ net_cash: 1 });
  });

  it('NEGATIVE: an unknown row survives every chip switched on', () => {
    const p = partitionCapital(ROWS, read, new Set(ORDER), ORDER);
    expect(p.rows.map((r) => r.symbol)).toContain('NLY');
  });

  it('NEGATIVE: an unread row is never hidden — it is placed last and counted', () => {
    const p = partitionCapital(ROWS, read, new Set(ORDER), ORDER);
    expect(p.rows[p.rows.length - 1].symbol).toBe('ZZZZ');
    expect(p.unread).toBe(1);
    expect(p.hidden).toBe(1);                              // FF only
  });

  it('a row failing two active questions is counted ONCE, under the first in served order', () => {
    const p = partitionCapital(ROWS, read, new Set(['positive_roce', 'net_cash']), ORDER);
    expect(p.hidden).toBe(1);
    expect(p.hiddenByKey).toEqual({ net_cash: 1 });        // served order wins, not Set order
    const sum = Object.values(p.hiddenByKey).reduce((a, b) => a + b, 0);
    expect(sum).toBe(p.hidden);                            // the parts sum to the whole
  });

  it('attribution does not depend on the order he clicked the chips', () => {
    const a = partitionCapital(ROWS, read, new Set(['net_cash', 'positive_roce']), ORDER);
    const b = partitionCapital(ROWS, read, new Set(['positive_roce', 'net_cash']), ORDER);
    expect(a.hiddenByKey).toEqual(b.hiddenByKey);
  });

  it('NEGATIVE: an empty list and a missing order do not throw', () => {
    expect(partitionCapital([], read, new Set(['net_cash'])).rows).toEqual([]);
    const p = partitionCapital(ROWS, read, new Set(['net_cash']));
    expect(p.hidden).toBe(1);
  });
});

describe('gradeCell — the served word, and unknown is not a verdict', () => {
  const stats = componentStats(SUMMARY);

  it('prints the served grade with the served counts', () => {
    const c = gradeCell(q({ net_cash: P('cash > debt'), positive_roce: F('ROCE -1.0%') }), stats);
    expect(c.text).toBe('some 1/2');
    expect(c.cls).toBe('eg-q-some');
    expect(c.unknown).toBe(false);
  });

  it('NEGATIVE: an unknown row renders its own word and its own tone', () => {
    const c = gradeCell(q({ net_cash: U('missing_cash_or_debt'),
                            positive_roce: U('non_operating_sector') }), stats);
    expect(c.text).toBe('unknown');
    expect(c.cls).toBe('eg-q-unknown');
    expect(c.unknown).toBe(true);
    expect(c.text).not.toContain('none');
    expect(c.text).not.toContain('0');                     // never "0/0"
    expect(c.title).toContain('unknown, not bad');
    expect(c.title).toContain('non_operating_sector');     // the SERVED reason code
  });

  it('NEGATIVE: "none" and "unknown" never share a tone or a word', () => {
    const none = gradeCell(q({ net_cash: F('cash <= debt') }), stats);
    const unk = gradeCell(q({ net_cash: U('missing_cash_or_debt') }), stats);
    expect(none.text).not.toBe(unk.text);
    expect(none.cls).not.toBe(unk.cls);
    expect(none.unknown).toBe(false);
  });

  it('NEGATIVE: no grade is ever the app\'s "measured badly" red', () => {
    for (const comps of [{ n: F('x') }, { n: P('x') }, { n: U('r') }]) {
      expect(gradeCell(q(comps), stats).cls).not.toContain('bad');
      expect(gradeCell(q(comps), stats).cls).not.toContain('err');
    }
  });

  it('Rule #7: the fiscal PERIOD is carried, and its absence is said, not guessed', () => {
    expect(gradeCell(q({ n: P('x') }), stats).period).toBe('FY2026 Q2');
    expect(gradeCell(q({ n: P('x') }), stats).title).toContain('Capital figures from FY2026 Q2');
    const none = gradeCell(q({ n: P('x') }, { period: null }), stats);
    expect(none.period).toBeNull();
    expect(none.title).toContain('No fiscal period on file');
  });

  it('NEGATIVE: no read at all is an em-dash and says it is blank, not a grade', () => {
    const c = gradeCell(null, stats);
    expect(c.text).toBe('—');
    expect(c.title).toContain('blank, not a grade');
    expect(c.unknown).toBe(true);
  });
});

describe('componentLine — served strings joined, never written', () => {
  const stat = { key: 'net_cash', kind: 'definitional', label: 'Holds more cash than debt' };

  it('an answered question carries its served evidence', () => {
    expect(componentLine(stat, F('cash <= debt')))
      .toBe('Holds more cash than debt: fail (cash <= debt)');
  });

  it('an unknown one carries its served reason code', () => {
    expect(componentLine(stat, U('missing_cash_or_debt')))
      .toBe('Holds more cash than debt: unknown (missing_cash_or_debt)');
  });

  it('NEGATIVE: a missing answer reads unknown, never fail', () => {
    expect(componentLine(stat, undefined)).toBe('Holds more cash than debt: unknown');
    expect(componentLine(stat, { verdict: null })).toBe('Holds more cash than debt: unknown');
  });

  it('NEGATIVE: with no served label it falls back to the served key, not to prose', () => {
    expect(componentLine({ key: 'net_cash' }, P('cash > debt')))
      .toBe('net_cash: pass (cash > debt)');
  });
});

describe('componentStats / componentKeys', () => {
  it('keeps served order', () => {
    expect(componentKeys(SUMMARY)).toEqual(['net_cash', 'positive_roce', 'capex_below_sector']);
  });

  it.each([
    ['no summary', null],
    ['no components', { n: 3 }],
    ['a non-array', { components: 'x' as unknown as [] }],
  ])('NEGATIVE: %s yields no chips at all', (_l, s) => {
    expect(componentStats(s as CapitalQualitySummary)).toEqual([]);
    expect(componentKeys(s as CapitalQualitySummary)).toEqual([]);
  });

  it('NEGATIVE: an entry with no key is dropped rather than rendered keyless', () => {
    expect(componentStats({ components: [{ key: '' }, { key: 'net_cash' }] } as CapitalQualitySummary))
      .toHaveLength(1);
  });
});

describe('visibleComponentCounts — the count of what a click will DO', () => {
  const GOOD = q({ net_cash: P('cash > debt'), positive_roce: P('ROCE 40%') });
  const BAD = q({ net_cash: F('cash <= debt'), positive_roce: F('ROCE -3%') });
  const UNK = q({ net_cash: U('missing_cash_or_debt'),
                  positive_roce: U('missing_roce') });
  const KEYS = ['net_cash', 'positive_roce'];

  it('counts FAILs and UNKNOWNs over the rows it is handed', () => {
    expect(visibleComponentCounts([GOOD, BAD, UNK], KEYS))
      .toEqual({ net_cash: { fail: 1, unknown: 1 },
                 positive_roce: { fail: 1, unknown: 1 } });
  });

  it('REGRESSION: a row the board already filtered out is not counted', () => {
    /* The served `hides_n` is a WHOLE-BOARD figure and the chips act on a list
     * the board has already filtered — `debtTier` ships ON and removes the
     * levered rows, which are the same ones that fail `net_cash`. */
    expect(visibleComponentCounts([GOOD], KEYS).net_cash).toEqual({ fail: 0, unknown: 0 });
  });

  it('NEGATIVE: a row with no read at all is never counted as a failure', () => {
    expect(visibleComponentCounts([GOOD, null], KEYS).net_cash)
      .toEqual({ fail: 0, unknown: 0 });
  });

  it('NEGATIVE: an ABSENT component counts as unknown, never as a fail', () => {
    const bare = q({ positive_roce: P('ROCE 40%') });
    expect(visibleComponentCounts([bare], KEYS).net_cash).toEqual({ fail: 0, unknown: 1 });
  });

  it('NEGATIVE: a key nobody served has an entry, and no row FAILS it', () => {
    // Every row "cannot answer" a question that was never asked. It is an
    // unknown, never a failure, so a chip on it could hide nothing.
    expect(visibleComponentCounts([GOOD, BAD], ['nope']))
      .toEqual({ nope: { fail: 0, unknown: 2 } });
  });

  it('counts grades and "fails nothing" over the same rows', () => {
    expect(visibleCounts([GOOD, BAD, UNK], KEYS))
      .toEqual({ n: 3, no_fail: 2,
                 grades: { all: 1, most: 0, some: 0, none: 1, unknown: 1 } });
  });

  it('NEGATIVE: an all-unknown row FAILS NOTHING — it was never judged', () => {
    expect(visibleCounts([UNK], KEYS).no_fail).toBe(1);
  });

  it('NEGATIVE: rows with no read are excluded from n, not graded as unknown', () => {
    expect(visibleCounts([GOOD, null, null], KEYS).n).toBe(1);
  });
});

describe('capitalCoverage — served numbers only', () => {
  it('states the grades, the survivor count and the peer cohort', () => {
    const t = capitalCoverage(SUMMARY)!;
    expect(t).toContain('graded 3 rows');
    expect(t).toContain('all 1 · most 0 · some 0 · none 1 · unknown 1');
    expect(t).toContain('2 of 3 fail nothing');
    expect(t).toContain('413 cached balance sheets, floor 20 per sector');
  });

  it('NEGATIVE: an unavailable peer cohort is said, and is not a fail', () => {
    const t = capitalCoverage({ ...SUMMARY, peers: { available: false } })!;
    expect(t).toContain('sector peers unavailable');
    expect(t).toContain('which is not a fail');
  });

  it.each([
    ['no summary', null],
    ['zero rows', { ...SUMMARY, n: 0 }],
    ['a missing n', { ...SUMMARY, n: undefined }],
  ])('NEGATIVE: %s prints no coverage line at all', (_l, s) => {
    expect(capitalCoverage(s as CapitalQualitySummary)).toBeNull();
  });

  it('REGRESSION: given the drawn rows it counts THEM, and says which set', () => {
    /* "2 of 3 fail nothing" printed under a one-row table describes a
     * population the reader cannot see. */
    const t = capitalCoverage(SUMMARY, { n: 1, no_fail: 1,
      grades: { all: 1, most: 0, some: 0, none: 0, unknown: 0 } })!;
    expect(t).toContain('graded 1 of 3 rows on screen');
    expect(t).toContain('1 of 1 fail nothing');
    expect(t).not.toContain('2 of 3 fail nothing');
  });

  it('says nothing about a screen when the drawn set IS the board', () => {
    const t = capitalCoverage(SUMMARY, { n: 3, no_fail: 2,
      grades: { all: 1, most: 0, some: 0, none: 1, unknown: 1 } })!;
    expect(t).toContain('graded 3 rows');
    expect(t).not.toContain('on screen');
  });

  it('NEGATIVE: an empty drawn set still prints, rather than vanishing', () => {
    const t = capitalCoverage(SUMMARY, { n: 0, no_fail: 0,
      grades: { all: 0, most: 0, some: 0, none: 0, unknown: 0 } })!;
    expect(t).toContain('graded 0 of 3 rows on screen');
  });
});
