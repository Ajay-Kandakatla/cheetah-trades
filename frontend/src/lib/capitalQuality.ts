/* 💎 capitalQuality — the FE renderer for backend/growth/capital_quality.py.
 *
 * Ajay 2026-09-22: "Ok can you now with in the explosive growth can you add a
 * new tab.. Where we look at quality I need filter tab in explosive growth tab,
 * whcih manage quality like very less capital and hi ROI. ... Filter and have
 * alerts and new look out for such companies where whcih have very high
 * quality. Let me know where you are creating it"
 *
 * THIS FILE GRADES NOTHING. The grade, the per-question verdicts, the reason
 * codes, the per-question hide counts and the not-measured sentence are all
 * SERVED — computed on the backend from the filings, off `GET /growth/board`
 * as `rows[].capital_quality` and `capital_quality_summary`. Everything here is
 * a renderer and a stable partition: it reads `grade`, `verdict`, `reason`,
 * `detail`, `label`, `hides_n` and `measured_note` exactly as they arrive. A
 * second copy of the rule in TSX is a second, drifting engine — the mistake
 * this app has already paid for once with the room read.
 *
 * NOT A NEW TAB, AND THAT IS THE RULE #5 PUSH-BACK. He asked for "a new tab".
 * This board is 21 rows with fifteen columns and four chips already on it;
 * splitting 21 rows across two tabs means the quality read can only be seen by
 * leaving the growth numbers behind, and the growth numbers can only be seen by
 * leaving the quality read behind. It ships as a chip row plus ONE column on
 * the board he is already reading.
 *
 * NOTHING IS EVER SILENTLY HIDDEN. Two facts force it:
 *
 *   1. `ExplosiveGrowth.tsx:285` already records that a literal `debt === 0`
 *      filter returned ZERO of 29 rows, which is why `debtTier` ships at the
 *      widest honestly debt-light tier rather than the strictest one.
 *   2. Measured on the live board 2026-09-22: stacking every definitional cut
 *      as one AND-gate leaves **2 of 21 names** (NVDA, TER).
 *
 * So every chip ships OFF, each one says how many rows it would hide BEFORE it
 * is clicked (the served `hides_n`), clicking it again brings those rows back,
 * and the count line is drawn the whole time one is on — even at zero hidden.
 *
 * UNKNOWN IS NOT FAILED. A question whose input is missing is served
 * `"unknown"` with a named reason; it is excluded from `answered`, it never
 * lands in `failed`, and **a chip never hides it** — `hides_n` counts failures
 * only, because a row nobody could judge was not judged badly. A row with no
 * read at all is never hidden either: it is kept, placed last, and counted
 * separately so the line can say so.
 *
 * NOT MEASURED. `MEASURED = False` on the backend module and `measured: false`
 * rides every row. No study has asked whether any of this predicts a return on
 * his universe, and the sentence that says so is SERVED (`measured_note`) so it
 * cannot drift from the flag that governs it.
 */

/** The three verdicts, as served (capital_quality.PASS / FAIL / UNKNOWN). */
export type CapitalVerdict = 'pass' | 'fail' | 'unknown';

/** The grades, as served (capital_quality.GRADES). A COUNT of yes-answers out
 *  of the questions that could be answered — not a fitted threshold, because
 *  there is no outcome anywhere in that module to fit one against. */
export type CapitalGrade = 'all' | 'most' | 'some' | 'none' | 'unknown';

/** One question's answer for one row. `detail` is present on an answered
 *  question, `reason` on an unknown one — never both. */
export type CapitalComponent = {
  verdict?: CapitalVerdict | string | null;
  /** The served unknown reason CODE (capital_quality.UNKNOWN_REASONS). */
  reason?: string | null;
  /** The served evidence for an answered question, e.g. "ROCE 100.40%". */
  detail?: string | null;
  /** Relative questions only: how many sector peers carried the figure. */
  peer_n?: number | null;
  sector_median?: number | null;
};

/** `rows[].capital_quality`. */
export type CapitalQuality = {
  grade?: CapitalGrade | string | null;
  passed?: number | null;
  failed?: number | null;
  unknown?: number | null;
  answered?: number | null;
  /** null = nothing could be answered. NOT ranked last — not ranked. */
  rank_key?: number | null;
  components?: Record<string, CapitalComponent> | null;
  /** Rule #7 — the FISCAL QUARTER the capital figures came from, never the
   *  cache age. A balance sheet fetched an hour ago can still be a quarter
   *  old, and only the period says which. */
  period?: string | null;
  period_end?: string | null;
  measured?: boolean | null;
};

/** One entry of `capital_quality_summary.components`. */
export type CapitalComponentStat = {
  key: string;
  /** "definitional" (a sign test or an inequality between two filed figures)
   *  or "relative" (above/below this name's own sector median). There is no
   *  third kind: no question compares a figure to a constant someone chose. */
  kind?: string | null;
  label?: string | null;
  pass_n?: number | null;
  fail_n?: number | null;
  unknown_n?: number | null;
  /** What toggling THIS question on would hide: FAILURES ONLY. */
  hides_n?: number | null;
};

/** `capital_quality_summary`. */
export type CapitalQualitySummary = {
  n?: number | null;
  grades?: Record<string, number> | null;
  components?: CapitalComponentStat[] | null;
  /** Every question a PASS with nothing unknown — the strictest read, and the
   *  "2 of 21" a stacked AND-gate measured 2026-09-22. */
  all_pass_n?: number | null;
  /** ZERO failed questions — what is still on screen with every chip on. This
   *  is the number a survivor warning must use, because a chip hides FAILURES
   *  and an unknown row was never judged. */
  no_fail_n?: number | null;
  peers?: {
    available?: boolean | null;
    n_docs?: number | null;
    min_peers?: number | null;
    sectors?: Record<string, Record<string, number>> | null;
  } | null;
  measured?: boolean | null;
  /** The sentence every surface must print. SERVED — never typed in TSX. */
  measured_note?: string | null;
  study_script?: string | null;
};

/** A missing read prints an em-dash. NEVER a zero and never a grade. */
const DASH = '—';

/** The served verdict words, so a comparison here cannot drift from the
 *  backend's own constants by a typo. */
export const PASS = 'pass';
export const FAIL = 'fail';
export const UNKNOWN = 'unknown';

const num = (v: unknown): number => (typeof v === 'number' && Number.isFinite(v) ? v : 0);

/** The served stats, in served order, with only the entries that carry a key.
 *  Order is the backend's `COMPONENTS` tuple — the chips must not reshuffle
 *  under his cursor between two polls. */
export function componentStats(
  s?: CapitalQualitySummary | null,
): CapitalComponentStat[] {
  const list = s?.components;
  if (!Array.isArray(list)) return [];
  return list.filter((c) => c && typeof c.key === 'string' && c.key);
}

/** The served question keys, in served order. */
export function componentKeys(s?: CapitalQualitySummary | null): string[] {
  return componentStats(s).map((c) => c.key);
}

/** One row's read, or null. Guards the shape rather than trusting it: a
 *  payload from an older build carries no `capital_quality` at all, and that
 *  row must render a blank, never a grade. */
export function readOf(row: unknown): CapitalQuality | null {
  const q = (row as { capital_quality?: unknown } | null)?.capital_quality;
  if (!q || typeof q !== 'object') return null;
  const g = (q as CapitalQuality).grade;
  return typeof g === 'string' && g ? (q as CapitalQuality) : null;
}

/** Did this row FAIL this question. UNKNOWN and absent are both false — the
 *  single place the "unknown is not failed" rule is spelled, so a filter and a
 *  cell cannot disagree about it. */
export function failedComponent(q: CapitalQuality | null, key: string): boolean {
  return (q?.components || {})[key]?.verdict === FAIL;
}

/* ──────────────────────────────────────────── counted on the DRAWN rows */

/** What one question does to the rows ACTUALLY ON SCREEN.
 *
 *  THE SERVED `hides_n` IS A WHOLE-BOARD FIGURE AND THE CHIPS DO NOT ACT ON
 *  THE WHOLE BOARD. By the time a chip is drawn the page has already applied
 *  the debt tier (which ships ON at "net cash"), the enterable cut, the sector
 *  picker and the demand/buyable checkboxes. Measured on the live board
 *  2026-09-22 the default debt tier alone removes precisely the levered names —
 *  which are the same rows that fail `net_cash` — so a served `(10)` chip
 *  promised to hide ten rows and hid none, and a click moved nothing.
 *
 *  A count that does not match what a click does is worse than no count: it is
 *  the `debtTier` lesson (`ExplosiveGrowth.tsx:285`) repeated with a number
 *  attached. So the printed figure is counted here, over the served verdicts of
 *  the rows in hand — pure arithmetic, no threshold, no second engine: the
 *  verdict itself is still the backend's, read through `failedComponent`.
 *
 *  Anything that is not a served PASS and not a served FAIL counts as UNKNOWN,
 *  including an absent component, which is the same rule `componentLine` uses
 *  when it renders one. */
export type CapitalCount = { fail: number; unknown: number };

export function visibleComponentCounts(
  reads: readonly (CapitalQuality | null)[],
  keys: readonly string[],
): Record<string, CapitalCount> {
  const out: Record<string, CapitalCount> = {};
  for (const k of keys) out[k] = { fail: 0, unknown: 0 };
  for (const q of reads || []) {
    if (!q) continue;                       // no read at all: never judged
    for (const k of keys) {
      const v = (q.components || {})[k]?.verdict;
      if (v === FAIL) out[k].fail += 1;
      else if (v !== PASS) out[k].unknown += 1;
    }
  }
  return out;
}

/** The same substitution for the honesty line: how many rows on screen carry a
 *  read, what they grade, and how many fail NOTHING — the number that says what
 *  is left with every chip on. `no_fail` is computed through `failedComponent`
 *  over the SERVED key order rather than read off `failed`, so it cannot
 *  disagree with what the chips actually do. */
export type CapitalVisible = {
  n: number;
  grades: Record<string, number>;
  no_fail: number;
};

export function visibleCounts(
  reads: readonly (CapitalQuality | null)[],
  keys: readonly string[],
): CapitalVisible {
  const grades: Record<string, number> = {
    all: 0, most: 0, some: 0, none: 0, unknown: 0,
  };
  let n = 0;
  let noFail = 0;
  for (const q of reads || []) {
    if (!q) continue;
    n += 1;
    const g = String(q.grade);
    grades[g] = (grades[g] || 0) + 1;
    if (!keys.some((k) => failedComponent(q, k))) noFail += 1;
  }
  return { n, grades, no_fail: noFail };
}

/* ─────────────────────────────────────────────────────────── the grade cell */

/** The column header. Describes what the column IS; it states no verdict and
 *  makes no claim about what the grade predicts — that sentence is SERVED
 *  (`measured_note`) and is printed under the board, where it cannot be
 *  missed. Same construction as `SINCE_REPORT_HEAD`, and like that column this
 *  one is deliberately NOT a sort key: the ask is a read, and an ordering on
 *  it is a separate ask (growthSort.ts is untouched). */
export const QUALITY_HEAD = {
  text: '💎 Quality',
  title:
    'How many balance-sheet questions this name answers yes, out of the ones '
    + 'its filings could answer at all: holds more cash than debt, throws off '
    + 'cash, share count not rising, earns a positive return on capital, and — '
    + 'against its own sector — earns more on capital while tying up less. '
    + 'Every question is either an inequality between two filed figures or a '
    + 'comparison against that sector\'s own median; not one of them compares a '
    + 'figure to a number somebody picked. "unknown" means the filings could '
    + 'not answer, which is NOT a fail and is never hidden by a chip. The '
    + 'quarter under the grade is the fiscal period the capital figures came '
    + 'from, not the cache age. Hover a cell for every question\'s answer.',
};

export type CapitalCell = {
  /** The SERVED grade word, with the SERVED counts beside it. "all" over two
   *  questions and "all" over six are the same word and different facts, which
   *  is why `answered` is served beside the grade and printed with it. */
  text: string;
  /** A per-grade class so `none` (answered, all no) and `unknown` (nobody could
   *  look) can never render alike. */
  cls: string;
  title: string;
  /** True when the row was never judged. The cell must not read as bad. */
  unknown: boolean;
  /** Rule #7 — the served fiscal quarter, printed under the grade. */
  period: string | null;
};

/** Per-grade class. No grade is ever red: nothing in this read has been
 *  measured against an outcome, so the colour the app gives to things that
 *  measured badly is not used here at all. */
const GRADE_CLS: Record<string, string> = {
  all: 'eg-q-all',
  most: 'eg-q-most',
  some: 'eg-q-some',
  none: 'eg-q-none',
  unknown: 'eg-q-unknown',
};

/** One question as a line of hover text: the SERVED label, the SERVED verdict
 *  word, and the SERVED evidence or the SERVED reason code. Nothing is
 *  composed — this joins served strings, it does not write one. */
export function componentLine(
  stat: CapitalComponentStat,
  c?: CapitalComponent | null,
): string {
  const label = stat.label || stat.key;
  const v = typeof c?.verdict === 'string' && c.verdict ? c.verdict : UNKNOWN;
  const tail = v === UNKNOWN ? c?.reason || '' : c?.detail || '';
  return tail ? `${label}: ${v} (${tail})` : `${label}: ${v}`;
}

/** The Quality cell. Prints the served grade word and the served counts; the
 *  hover carries every question's served answer, and an unknown one carries its
 *  served reason code. */
export function gradeCell(
  q: CapitalQuality | null,
  stats: readonly CapitalComponentStat[] = [],
): CapitalCell {
  if (!q) {
    return {
      text: DASH,
      cls: 'eg-q-blank',
      title: 'No capital-quality read on this row — blank, not a grade.',
      unknown: true,
      period: null,
    };
  }
  const grade = String(q.grade);
  const answered = num(q.answered);
  const passed = num(q.passed);
  const isUnknown = grade === UNKNOWN || answered <= 0;
  const lines = stats.map((s) => componentLine(s, (q.components || {})[s.key]));
  const period = typeof q.period === 'string' && q.period ? q.period : null;

  const head = isUnknown
    // Never "0 of 0", which reads as a failure. Nothing could be answered.
    ? 'Nothing about this balance sheet could be answered — unknown, not bad. '
      + 'It is not ranked, and no chip hides it.'
    : `${passed} of ${answered} balance-sheet questions came back yes.`;
  const tail = period
    ? ` Capital figures from ${period}.`
    : ' No fiscal period on file for the capital figures.';

  return {
    text: isUnknown ? UNKNOWN : `${grade} ${passed}/${answered}`,
    cls: GRADE_CLS[grade] || 'eg-q-unknown',
    title: [head + tail, ...lines].join('\n'),
    unknown: isUnknown,
    period,
  };
}

/* ─────────────────────────────────────────────────────────── the partition */

export type CapitalPartition<T> = {
  /** Survivors first, then the rows nothing could be read for. */
  rows: T[];
  /** Rows a chip removed. Failures only. */
  hidden: number;
  /** Rows with NO read at all — never hidden, shown last, counted here so the
   *  line can say so rather than letting the board look short. */
  unread: number;
  /** Which chip took each hidden row. A row failing two active questions is
   *  counted ONCE, under the first in served order, so the parts sum to
   *  `hidden` and the line cannot over-report. */
  hiddenByKey: Record<string, number>;
};

/** Partition a list the page already ordered. Identity and zero counts when no
 *  chip is on — the shipped board, row for row. */
export function partitionCapital<T>(
  rows: readonly T[],
  read: (row: T) => CapitalQuality | null,
  active: ReadonlySet<string>,
  order: readonly string[] = [],
): CapitalPartition<T> {
  const all = (rows || []) as readonly T[];
  if (!active || active.size === 0) {
    return { rows: all.slice(), hidden: 0, unread: 0, hiddenByKey: {} };
  }

  /* Served order first, then anything else the set holds, so attribution is
   * stable across polls and cannot depend on Set insertion order. */
  const keys = [
    ...order.filter((k) => active.has(k)),
    ...Array.from(active).filter((k) => !order.includes(k)).sort(),
  ];

  const shown: T[] = [];
  const unread: T[] = [];
  const hiddenByKey: Record<string, number> = {};
  let hidden = 0;

  for (const row of all) {
    const q = read(row);
    if (!q) {
      unread.push(row);
      continue;
    }
    const hit = keys.find((k) => failedComponent(q, k));
    if (!hit) {
      shown.push(row);
      continue;
    }
    hidden += 1;
    hiddenByKey[hit] = (hiddenByKey[hit] || 0) + 1;
  }

  return { rows: [...shown, ...unread], hidden, unread: unread.length, hiddenByKey };
}

/* ─────────────────────────────────────────────────────────── the count line */

/** `${n} hidden`, thousands-separated. */
export const hiddenClause = (n: number): string => `${n.toLocaleString()} hidden`;

/** The coverage sentence, composed from SERVED counts only — the same
 *  construction as `sinceReportCoverage`, so the two honesty lines under this
 *  table cannot describe their coverage in two different grammars.
 *
 *  It never states a verdict about a name. Every number in it arrived. */
export function capitalCoverage(
  s?: CapitalQualitySummary | null,
  visible?: CapitalVisible | null,
): string | null {
  const served = num(s?.n);
  if (!s || served <= 0) return null;
  /* Counted over the rows ON SCREEN when they were passed in, for the same
   * reason the chips are: with the debt tier and the enterable cut already
   * applied, a board-wide "2 of 21 fail nothing" printed under a four-row
   * table describes a population the reader cannot see. */
  const n = visible ? visible.n : served;
  const g = visible ? visible.grades : (s.grades || {});
  const noFail = visible ? visible.no_fail : num(s.no_fail_n);
  const bits: string[] = [
    visible && n !== served
      ? `Capital quality: graded ${n} of ${served} rows on screen`
      : `Capital quality: graded ${n} rows`,
    ['all', 'most', 'some', 'none', 'unknown']
      .map((k) => `${k} ${num(g[k])}`).join(' · '),
    `${noFail} of ${n} fail nothing (what is left with every chip on)`,
  ];
  const peers = s.peers || {};
  if (peers.available) {
    bits.push(`sector peers from ${num(peers.n_docs).toLocaleString()} cached `
      + `balance sheets, floor ${num(peers.min_peers)} per sector`);
  } else {
    bits.push('sector peers unavailable — the two "compared to its sector" '
      + 'questions answer unknown, which is not a fail');
  }
  return bits.join(' · ');
}
