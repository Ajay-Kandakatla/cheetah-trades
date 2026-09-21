/* 📋 The Bonde PICK LINE — pure formatting for a served, cited criterion set.
 *
 * Ajay 2026-09-20: "I need bonde for stock picks rather than deciding to enter.
 * I decide based on supply and demand … show me other things like EPS, Sales
 * and other things … He looks at earnings surprise too" and, correcting it,
 * "look for thing she said from a stock pic pov … I am looking fro static
 * info".
 *
 * So: STATIC criteria only. Nothing in this module reads a price-derived or
 * session-derived field, and nothing here counts, ranks or scores the legs —
 * the pick line is a list of facts with their sources, not a verdict. Every
 * sentence a chip's tooltip shows is SERVED (`pick_legend.criteria`), because
 * a quote typed into the frontend is a quote nobody can re-verify.
 *
 * THREE STATES, never two. `ok: null` is UNKNOWN and must never render as a
 * fail: most of these legs read out of caches that may not have been warmed
 * yet, and "we have not looked" is not "it does not qualify". The `why` code
 * says which, in the backend's own vocabulary (`sepa/bonde_picks.WHY_CODES`).
 *
 * Nothing on this line is measured, nothing on it is a signal, and it gates,
 * sorts and filters nothing.
 */
import { UNVERIFIED_TITLE } from './bondeLive';

/* ── Types ──────────────────────────────────────────────────────────────── */

/** The backend's ONE vocabulary (`sepa/bonde_picks.WHY_CODES`), copied exactly.
 *  A contract sweep diffs these against the Python frozenset as sets, so a code
 *  added on one side and not the other fails the build rather than rendering an
 *  empty tooltip. */
export type WhyCode =
  // scan-derived legs
  | 'no_eps_series' | 'year_ago_loss' | 'pair_not_a_year_apart' | 'no_period_keys'
  | 'prior_hole' | 'no_sales_read' | 'no_inst_read' | 'no_sector'
  | 'no_threshold_in_his_writing'
  // sequential base states, mapped from qoq by name
  | 'seq_base_non_positive' | 'seq_base_too_small' | 'seq_base_unknown'
  | 'seq_not_adjacent'
  // cache-derived legs
  | 'not_on_calendar' | 'no_surprise_in_report'
  | 'no_metrics_doc' | 'no_float_in_doc' | 'no_cap_in_doc'
  | 'not_warmed' | 'no_si_record'
  | 'no_analyst_doc' | 'no_estimate_read'
  | 'no_listing_date' | 'future_listing_date'
  // theme lookup
  | 'no_symbol';

/** A pair leg (`eps_accel`, `rev_39_x2`) carries both halves, never a ratio. */
export type BondeLegPair = { now?: number | null; prior?: number | null };

export type BondePickLeg = {
  /** TRI-state. `null` = unknown, and unknown is never a fail. */
  ok: boolean | null;
  value?: number | string | BondeLegPair | null;
  why?: WhyCode | string | null;
  /** ISO date the value is as of (a report date, a settlement, a listing). */
  as_of?: string | null;
  /** A LABEL, never a gate: a stale read never flips `ok` (Rule #7). */
  stale?: boolean | null;
  age_days?: number | null;
  source?: string | null;
  tier?: string | null;
  value_note?: string | null;
  his_call?: string | null;
  /** The app's freshness BOUND in days (a served constant), never the row's own
   *  age: the stale hover prints this, so a 200-day report reads "older than
   *  157 days" rather than "older than 200 days". */
  stale_after?: number | null;
  /** The revenue-growth counter stopped at its own cap — "4" means "4 or more". */
  capped?: boolean | null;
  /** The counter ran out of HISTORY before the growth ran out. */
  history_ended?: boolean | null;
  n_pairs_available?: number | null;
  /** The theme lookup found this name on the app's own map. */
  mapped?: boolean | null;
  ids?: string[] | null;
  /** The SEQUENTIAL flip (qoq's own read), carried beside a year-ago turnaround
   *  and never confused with it. */
  seq_turn?: string | null;
  latest?: number | null;
  year_ago?: number | null;
  recorded?: string | null;
};

/** What the row carries. The backend also serves per-row tallies for its own
 *  documentation; they are deliberately not typed here, because no count,
 *  ratio or score derived from these legs is ever rendered. */
export type BondePick = { legs: Record<string, BondePickLeg> };

/** A SECOND sentence of his for a criterion that already has one — added,
 *  never replacing the primary. A tape cite carries two dates: `date` is when
 *  the episode was published and `recorded` is when he spoke, and the cite line
 *  prints neither (the tape-source line in the legend does). */
export type BondeCite = {
  quote: string;
  url: string;
  date?: string | null;
  recorded?: string | null;
  source?: string | null;
  ts?: string | null;
  note?: string | null;
};

export type BondeCriterion = {
  key: string;
  label: string;
  /** His sentence, verbatim, served. */
  quote: string;
  url: string;
  date: string;
  source: string;
  /** Where this app gets the number from. */
  data: string;
  computed: boolean;
  not_computed_why?: string | null;
  /** The §7 item when the reading is still Ajay's to make. */
  his_call?: string | null;
  /** Extra sentences of his for the same criterion, in served order. */
  cites?: BondeCite[] | null;
  /** A FACT criterion: his words give no line for it, so its leg is shown as a
   *  value and a dash — never a tick and never a cross. */
  fact?: boolean | null;
  /** When the primary source is the tape: the second it starts. */
  ts?: string | null;
  recorded?: string | null;
};

export type BondePickLegend = {
  header: string;
  criteria: BondeCriterion[];
  computed_keys?: string[];
  why_codes?: string[];
  not_a_source?: string;
  warm_note?: string;
  /** A second header line, served: one sentence of his off the tape. */
  tape_header?: BondeCite | null;
  tape?: {
    url?: string;
    title?: string;
    show?: string;
    published?: string;
    recorded?: string;
    recorded_cite?: BondeCite | null;
    received?: string;
  } | null;
  /** The keys whose legs are facts, served — never a list typed here. */
  fact_keys?: string[] | null;
};

export type BondePickCoverage = Record<string, { known?: number | null; rows?: number | null }>;

/* ── The six ────────────────────────────────────────────────────────────── */

/** SIX chips, in this order (Rule #5 — the rest live behind the "all N" fold).
 *
 *  `sales_5` is deliberately NOT here: every row the board draws has already
 *  cleared his 5% floor by construction, so a ✓ on it is a fact of the section
 *  rather than information about the name. It stays in the expand.
 *  Which criterion fills this slot, and whether the listing-date leg earns one
 *  at all, are Ajay's calls — the defaults are what shipped. */
export const PICK_CHIP_ORDER = [
  'eps_yoy_100', 'rev_39_x2', 'surprise', 'float_25m', 'ipo_10y', 'short_dtc_5',
] as const;

export type PickChipKey = typeof PICK_CHIP_ORDER[number];

/* ── Why a leg reads unknown, in one sentence each ───────────────────────── */

export const WHY_TEXT: Record<WhyCode, string> = {
  no_eps_series:
    'No quarterly EPS series on the scan row, so the earnings legs could not be read.',
  year_ago_loss:
    'The year-ago quarter was a loss, so a year-over-year percentage here would be a sign flip rather than growth.',
  pair_not_a_year_apart:
    'This name’s newest quarter and its “year-ago” slot are NOT four fiscal quarters apart, so the year-over-year legs cannot be stated.',
  no_period_keys:
    'No fiscal-period keys on file — the pair could not be checked. The number is shown, marked unverified.',
  prior_hole:
    'The quarter before the comparison is missing, so the earlier half of this pair could not be read.',
  no_sales_read:
    'No revenue-growth read on this row.',
  no_inst_read:
    'No institutional-ownership figure on this row.',
  no_sector:
    'No sector on the scan row.',
  no_threshold_in_his_writing:
    'He names this as something he looks at, but publishes no level — so it is shown as a fact, never as a pass or a fail.',
  seq_base_non_positive:
    'The prior quarter’s earnings base was not positive, so a sequential percentage would be a sign flip rather than growth.',
  seq_base_too_small:
    'The prior quarter’s earnings base is under this app’s materiality floor, so the sequential percentage would be a ratio off a tiny base.',
  seq_base_unknown:
    'Not enough quarterly earnings history to state the sequential base.',
  seq_not_adjacent:
    'The two quarters on file are not adjacent, so there is no sequential pair to compare.',
  not_on_calendar:
    'No earnings-calendar row for this name, so there is no reported surprise to read.',
  no_surprise_in_report:
    'The last report on file carries no surprise percentage.',
  no_metrics_doc:
    'No cached balance-metrics document for this name yet.',
  no_float_in_doc:
    'The cached metrics document carries no float — it predates the field, or the provider has none for this name.',
  no_cap_in_doc:
    'The cached metrics document carries no market capitalisation for this name.',
  not_warmed:
    'Short interest has not been warmed for this name yet. Until the warm runs, this leg reads unknown on every row — it is not a low reading.',
  no_si_record:
    'The short-interest cache remembers a MISS for this name: the provider returned no settlement.',
  no_analyst_doc:
    'No analyst document for this name yet.',
  no_estimate_read:
    'The analyst document carries no estimate count — the provider’s estimate frame could not be read. Absence of a row is not proof of no coverage.',
  no_listing_date:
    'No listing date on file for this name.',
  future_listing_date:
    'The listing date on file is in the future, so the age could not be read.',
  no_symbol:
    'No symbol on the scan row, so the theme map could not be looked up.',
};

/** The four turnaround tokens the backend serves, in plain words. Only
 *  `to_profit` is his own word; the other three are the same read's other
 *  outcomes, carried so a row never reads as a blank. */
export const TURN_TEXT: Record<string, string> = {
  to_profit: 'loss → profit',
  to_loss: 'profit → loss',
  loss_both: 'loss both years',
  profit_both: 'profit both years',
};

/* ── Formatting ─────────────────────────────────────────────────────────── */

const num = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null;

/** Drop a trailing `.0` so $10.0B reads $10B and 18.0M reads 18M. */
const trim = (s: string): string => s.replace(/\.0$/, '');

const signed = (v: number, dp = 0): string =>
  `${v > 0 ? '+' : ''}${trim(v.toFixed(dp))}%`.replace('-', '−');

const shares = (v: number): string => {
  const a = Math.abs(v);
  const [u, d] = a >= 1e9 ? ['B', 1e9] as const
    : a >= 1e6 ? ['M', 1e6] as const
    : a >= 1e3 ? ['K', 1e3] as const : ['', 1] as const;
  return `${trim((v / d).toFixed(1))}${u}`;
};

const dollars = (v: number): string => {
  const a = Math.abs(v);
  const [u, d] = a >= 1e9 ? ['B', 1e9] as const
    : a >= 1e6 ? ['M', 1e6] as const
    : a >= 1e3 ? ['K', 1e3] as const : ['', 1] as const;
  const body = `$${trim((a / d).toFixed(a / d >= 100 ? 0 : 1))}${u}`;
  return v < 0 ? `−${body}` : body;
};

const isPair = (v: unknown): v is BondeLegPair =>
  typeof v === 'object' && v !== null && ('now' in (v as object) || 'prior' in (v as object));

const PCT_KEYS = new Set([
  'eps_yoy_100', 'eps_seq_100', 'sales_5', 'surprise', 'fund_holding',
]);

/** One value, formatted the way his sentence for that criterion reads it.
 *
 *  `leg` is OPTIONAL so every existing two-argument call still compiles; only
 *  the two callers that hold a leg pass it, and today it is read for one thing:
 *  a revenue-growth streak sitting on the counter's own cap prints `4+ q`. */
export function fmtValue(
  key: string, value: unknown, leg?: Pick<BondePickLeg, 'capped'> | null,
): string {
  if (isPair(value)) {
    const a = num(value.now); const b = num(value.prior);
    if (a == null && b == null) return '—';
    return `${a == null ? '—' : signed(a)}/${b == null ? '—' : signed(b)}`;
  }
  // BEFORE the string early-return below: the turnaround value is a served
  // TOKEN, not a sentence, so it is the one string this line translates.
  if (key === 'turnaround' && typeof value === 'string') {
    return TURN_TEXT[value] ?? value;
  }
  if (typeof value === 'string') return value.trim() || '—';
  const x = num(value);
  if (x == null) return '—';
  if (key === 'report_age') return `${Math.round(x)} d ago`;
  if (key === 'growth_streak') return `${Math.round(x)}${leg?.capped === true ? '+' : ''} q`;
  if (key === 'eps_5c') return `$${x.toFixed(2)}`;
  if (key === 'float_25m') return shares(x);
  if (key === 'cap_10b') return dollars(x);
  if (key === 'ipo_10y') return `${trim(x.toFixed(1))}y`;
  if (key === 'short_dtc_5') return trim(x.toFixed(1));
  if (key === 'neglect_analysts') return String(Math.round(x));
  if (PCT_KEYS.has(key)) return signed(x);
  return trim(x.toFixed(1));
}

/** The word in front of the value on a chip. Short by design: six of these sit
 *  under a ticker, and a sentence there is a wall, not a read. */
const CHIP_PREFIX: Record<string, string> = {
  eps_5c: 'EPS',
  eps_yoy_100: 'EPS',
  eps_seq_100: 'EPS',
  eps_accel: 'EPS accel',
  sales_5: 'Sales',
  rev_39_x2: 'Sales 2q',
  surprise: 'Surprise',
  float_25m: 'Float',
  short_dtc_5: 'DTC',
  neglect_analysts: 'Analysts',
  fund_holding: 'Funds',
  ipo_10y: 'IPO',
  cap_10b: 'Cap',
  sector_3: 'Sector',
  report_age: 'Reported',
  turnaround: 'Turnaround',
  growth_streak: 'Streak',
  theme: 'Theme',
};

/** The unit word that belongs AFTER the number, where his sentence names one. */
const CHIP_SUFFIX: Record<string, string> = {
  eps_yoy_100: ' y/y',
  eps_seq_100: ' q/q',
  eps_accel: ' now/prior',
  sales_5: ' y/y',
  rev_39_x2: '',
};

export type BondeChip = { text: string; tone: string; title: string; glyph: string };

function titleOf(key: string, leg: BondePickLeg, crit?: BondeCriterion | null): string {
  const parts: string[] = [];
  if (crit?.label) parts.push(crit.label);
  if (crit?.quote) parts.push(`“${crit.quote}”`);
  if (crit?.date || crit?.source || crit?.ts) {
    parts.push(
      crit.source === 'tape' && crit.ts
        ? `on tape [${crit.ts}]${crit.recorded ? `, recorded ${crit.recorded}` : ''}`
        : [crit.source, crit.date].filter(Boolean).join(' '),
    );
  }
  if (key === 'surprise') {
    const age = num(leg.age_days);
    if (age != null) parts.push(`reported ${Math.round(age)} d ago`);
  }
  if (leg.ok === null && leg.why) parts.push(WHY_TEXT[leg.why as WhyCode] || String(leg.why));
  if (leg.ok === true && leg.why === 'no_period_keys') parts.push(UNVERIFIED_TITLE);
  if (leg.stale === true) {
    // The BOUND, never the row's own age: "older than 157 days" is the app's
    // freshness constant; a 200-day report is not a 200-day bound. The age
    // fallback survives only for legs that serve no bound.
    const bound = num(leg.stale_after);
    const n = num(leg.age_days);
    const said = bound != null ? `${Math.round(bound)} days`
      : n != null ? `${Math.round(n)} days` : 'the app’s freshness bound';
    const what = key === 'short_dtc_5' ? 'settlement' : 'report';
    parts.push(`Shown, labelled stale: the ${what} is older than ${said}. A stale read never flips the tick.`);
  }
  if (leg.as_of) parts.push(`as of ${leg.as_of}`);
  if (leg.value_note) parts.push(String(leg.value_note));
  if (leg.source) parts.push(String(leg.source));
  if (leg.his_call) parts.push(`Ajay’s call: ${leg.his_call}`);
  else if (crit?.his_call) parts.push(`Ajay’s call: ${crit.his_call}`);
  return parts.filter(Boolean).join(' · ');
}

/** ONE chip. The five rows of the table this build pinned:
 *
 *  | ok    | why             | stale | text                          | tone       |
 *  | true  | —               | —     | `EPS +140% y/y ✓`             | bd-pick-ok |
 *  | true  | no_period_keys  | —     | `EPS +140% y/y ✓ · unverified`| bd-pick-ok |
 *  | true  | —               | true  | `DTC 6.1 ✓ · stale`           | bd-pick-ok |
 *  | false | any             | any   | `Float 140M ✗`                | bd-pick-no |
 *  | null  | any code        | —     | `Float —`                     | bd-dim     |
 *
 *  An unknown leg NEVER wears a tick and never wears a cross. */
export function legChip(
  key: string,
  leg: BondePickLeg | null | undefined,
  crit?: BondeCriterion | null,
): BondeChip | null {
  if (!leg) return null;
  const prefix = CHIP_PREFIX[key] || key;
  // A FACT criterion never wears a tick or a cross, whatever arrives on the
  // leg: his words give no line for it, so there is nothing to pass or fail.
  // (The backend builds these legs with `ok: None`; this is the second belt.)
  if (crit?.fact === true || leg.ok === null || leg.ok === undefined) {
    return {
      text: `${prefix} —`,
      tone: 'bd-dim',
      glyph: '—',
      title: titleOf(key, { ...leg, ok: null }, crit),
    };
  }
  const body = `${prefix} ${fmtValue(key, leg.value)}${CHIP_SUFFIX[key] || ''}`;
  if (leg.ok === false) {
    return { text: `${body} ✗`, tone: 'bd-pick-no', glyph: '✗', title: titleOf(key, leg, crit) };
  }
  const marks = [
    leg.why === 'no_period_keys' ? ' · unverified' : '',
    leg.stale === true ? ' · stale' : '',
  ].join('');
  return { text: `${body} ✓${marks}`, tone: 'bd-pick-ok', glyph: '✓', title: titleOf(key, leg, crit) };
}

/** One EXTRA sentence of his under a criterion: "— also, on tape [1:07:04]: …".
 *  The word is "also" because a cite is added to a criterion, never replacing
 *  the sentence it already had. Neither date is printed here. */
export function citeLine(c: BondeCite): string {
  if (c.source === 'tape') return `— also, on tape [${c.ts ?? '?'}]: “${c.quote}”`;
  return `— also, ${[c.source, c.date].filter(Boolean).join(' ')}: “${c.quote}”`;
}

/** The link text for a criterion's PRIMARY source: a timestamp when he said it
 *  on tape, the publisher and the date when he wrote it. */
export function sourceLabel(c: BondeCriterion): string {
  if (c.source === 'tape' && c.ts) return `on tape [${c.ts}]`;
  return [c.source, c.date].filter(Boolean).join(' ');
}

/** The criterion behind a leg, by key. */
export function criterionOf(
  legend: BondePickLegend | null | undefined, key: string,
): BondeCriterion | null {
  return (legend?.criteria || []).find((c) => c && c.key === key) || null;
}

/** The criteria the board actually computes, in served order — the rows behind the
 *  "all N" fold. A legend-only criterion (a sentence of his this app does not read
 *  a number for) never becomes a chip. */
export function computedCriteria(legend: BondePickLegend | null | undefined): BondeCriterion[] {
  return (legend?.criteria || []).filter((c) => c && c.computed);
}

const COVERAGE_LABEL: Record<string, string> = {
  eps_yoy_100: 'EPS y/y',
  rev_39_x2: 'two-quarter revenue',
  surprise: 'earnings surprise',
  float_25m: 'float',
  ipo_10y: 'listing date',
  short_dtc_5: 'short interest',
};

/** One sentence under the basis line: what the pick chips actually KNOW.
 *  A board that shows six dashes without saying why reads as broken; this says
 *  "not warmed" where that is the reason. */
export function coverageSentence(cov: BondePickCoverage | null | undefined): string | null {
  if (!cov) return null;
  const parts: string[] = [];
  for (const key of PICK_CHIP_ORDER) {
    const c = cov[key];
    if (!c) continue;
    const known = num(c.known) ?? 0;
    const rows = num(c.rows) ?? 0;
    const tail = key === 'short_dtc_5' && known === 0 ? ' (not warmed)' : '';
    parts.push(`${COVERAGE_LABEL[key]} ${known} of ${rows}${tail}`);
  }
  if (!parts.length) return null;
  return `Pick line known on: ${parts.join(' · ')}.`;
}
