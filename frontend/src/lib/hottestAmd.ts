/* 🌀 The AMD column on 🔥 Hottest — the SERVED read, printed, nothing composed.
 *
 * Ajay 2026-09-22, with a screenshot of the Defense roster open:
 *   "Add an AMD tag for these. like a column for me to see which one are
 *    getting manipulated."
 *
 * WHAT THIS FILE IS ALLOWED TO DO: turn a served `amd` cell into text, a tone
 * and a title. It composes no sentence, formats no number, parses no date and
 * never constructs a `Date` (banned in every FE file in this app — it parses an
 * ISO date as UTC and prints the previous ET day). Every word comes from
 * `backend/rotation/hottest_amd.py`, which reuses
 * `supply_demand.turning_bullish.verdict_text` — the ONE wording engine the
 * 🌀 AMD tab in Chart Maps already draws from.
 *
 * TWO RULES THE READ ITSELF MADE NECESSARY
 * ----------------------------------------
 * 1. NO COLOUR. The AMD read is MEASURED INVERTED on its own claim
 *    (re-measured 2026-09-14: 51.9% vs 56.1%, −4.2pp [−6.92, −1.89], negative
 *    in all seven distance buckets). The 🌀 AMD tab paints "raided" green;
 *    doing that here would paint the inverted state green on a board he ranks
 *    and scans, and a green cell read at a glance down 600 rows IS a ranking.
 *    So `amdCell` returns tone `dim` for EVERY grade — the served tone rides in
 *    the payload for fidelity, and the served `no_colour_reason` is appended to
 *    the cell's hover so the refusal is readable rather than silent.
 * 2. WHOLE TOKENS, NEVER A PREFIX + A VARIABLE. `contracts.mjs:1729-1746`
 *    harvests every `hs-[a-z0-9-]+` out of HottestSectors.tsx's raw text and
 *    fails unless styles.css holds a matching rule; `'hs-amd-' + tone` would
 *    ship `hs-amd-` as a class with no rule and turn the build red. The map
 *    below is the only place a tone becomes a class, and it holds whole tokens.
 * 3. TWO SERVED WORDINGS, NO SURGERY (2026-09-22, after *"last column is
 *    hidded"*). The cell prints the served `short`, the hover keeps the served
 *    `text`. Both are built by the backend from the one table
 *    (`turning_bullish.grade_label` + the shared age rule). This file CHOOSES
 *    between two strings that came back; it never slices the "AMD " prefix off
 *    one to make the other, because then the board and the backend's own
 *    coverage histogram could word the same grade two different ways.
 *
 * A blank is NEVER a zero and never the words of a real read: the backend
 * refuses to lend an ungradeable row the `table["none"]` fallback wording
 * ("AMD no cycle"), and this file prints the refusal's own sentence.
 */
import type { Cell } from './boardMetrics';

/** One name row's served AMD cell. Every key is always present on the wire;
 *  they are optional here because a payload from an older build has none.
 *
 *  TWO WORDINGS, BOTH SERVED, ONE ENGINE. `short` is what the BOARD cell
 *  prints; `text` is what the HOVER carries and what every other consumer
 *  (the 🌀 AMD tab, the coverage histogram) already reads. Both come out of
 *  `supply_demand.turning_bullish`'s one table via `grade_label` + the shared
 *  age rule — `short` is NOT `text` with a prefix sliced off here. This file
 *  chooses between two served strings and never manufactures a third. */
export type HsAmd = {
  known?: boolean; grade?: string | null; phase?: string | null;
  text?: string | null; short?: string | null;
  tone?: string | null; title?: string | null;
  bars_ago?: number | null; base_bars?: number | null;
  reason?: string | null; reason_text?: string | null;
};

/** The board-level block, a sibling of `d1` / `pre`. Carries every word this
 *  surface prints about the column, plus the counts computed on the very
 *  request that prints them. */
export type HsAmdSummary = {
  available?: boolean; n?: number; n_known?: number; n_blank?: number;
  blank_reasons?: Record<string, number>; grades?: Record<string, number>;
  grade_order?: string[];
  /** grade → the SHORT word the board cell prints for it, served so a consumer
   *  that needs to name a grade (a legend, a test proving a group row carries
   *  none of them) reads the words off the wire instead of typing them. */
  grade_labels?: Record<string, string>;
  built_at?: string | null;
  /* A MARKER, not a stamp: the backend serves `true` beside a naive-UTC
   * `built_at`, and null when there is no stamp to mark. Typing it as a
   * string invited `built_at_utc` to be printed as if it were a date. */
  built_at_utc?: boolean | null;
  built_at_et?: string | null;
  built_at_date?: string | null; last_session?: string | null; due_session?: string | null;
  stale?: boolean | null; stale_note?: string | null;
  n_scanned?: number | null; n_rows?: number | null;
  source?: string; cron?: string; honesty?: string; head_title?: string;
  group_note?: string; no_sort_reason?: string; sortable?: boolean;
  no_colour_reason?: string; coloured?: boolean;
  coverage_note?: string; unavailable_note?: string | null; label?: string;
  measured?: Record<string, string>;
};

/** The column itself. `sortable: false` is the whole reason it is not a member
 *  of HS_COLS: ranking the board on a read measured −4.2pp against its own
 *  placebo would order names by something measured to go the wrong way. */
export const AMD_COL: { key: string; label: string; num: boolean; sortable: boolean } =
  { key: 'amd', label: '🌀 AMD', num: false, sortable: false };

/** tone → class. WHOLE tokens only (see rule 2 above). `hs-amd-good` and
 *  `hs-amd-warn` exist so that turning colour on later (his call) is a
 *  one-line change with no class ever built by concatenation — `amdCell`
 *  itself never reaches them, because it always serves `dim`. */
export const AMD_TONE_CLASS = {
  good: 'hs-amd-good', warn: 'hs-amd-warn', dim: 'hs-amd-dim',
} as const;

/** Always a whole token, for every input — junk, blank and undefined land on
 *  `dim` rather than on a bare prefix. */
export function amdToneClass(tone?: string | null): string {
  const t = String(tone ?? '').trim().toLowerCase();
  if (t === 'good') return AMD_TONE_CLASS.good;
  if (t === 'warn') return AMD_TONE_CLASS.warn;
  return AMD_TONE_CLASS.dim;
}

const DASH = '—';

/** The FE's own belt, used only when the backend served no sentence. The
 *  backend owns the wording (`REASON_TEXT`); these exist so a blank can never
 *  reach the screen with an empty hover. */
/* The words "no cycle" and "clean" are deliberately NOT in this sentence.
 * They are the words of a REAL read (the backend's own "AMD no cycle"), and a
 * blank must never wear them even inside a denial — a hover skimmed at speed
 * reads the words, not the negation. Same wording the backend uses in
 * `REASON_TEXT`, so both belts say one thing. */
const GENERIC_BLANK =
  'Not read: this app has no AMD cycle for this name. A blank here means '
  + 'UNKNOWN — it is not a verdict, and it does not say the name is '
  + 'un-manipulated.';
const EMPTY_TEXT_BLANK =
  'Not read: the served AMD cell carried no wording, so there is nothing to print.';
const GROUP_BLANK =
  'No AMD state on a sector, industry or roster row. A cycle phase has no median.';
const HEAD_FALLBACK =
  'Which AMD cycle phase this name is in, from the nightly sweep. — = not read; '
  + 'hover the cell for why.';

/** Draw the 🌀 column at all? The SERVER decides, twice over: the block has to
 *  be there (it is absent entirely on the member-table-unavailable branch) and
 *  it has to say the read is available. 1,476 em-dashes is furniture. */
export function showAmdCol(d?: { amd_summary?: HsAmdSummary | null } | null): boolean {
  const s = d?.amd_summary;
  if (!s) return false;
  return s.available !== false;
}

/** One name row's cell. The tone is ALWAYS `dim` — see rule 1.
 *
 *  THE CELL PRINTS THE SHORT, THE HOVER CARRIES THE LONG (Ajay 2026-09-22:
 *  *"last column is hidded"*). Every one of the ~1,900 cells opened with the
 *  literal "AMD " while the header two rows up already said 🌀 AMD, so the
 *  widest column on the board spent four characters per row repeating its own
 *  name. The backend now serves BOTH wordings out of the one table; this
 *  function picks the short one for the cell and leaves the long one on the
 *  hover, where the whole sentence is still readable.
 *
 *  THE FALLBACK IS THE SERVED LONG STRING, NEVER A COMPOSED ONE. A payload
 *  from a build without `short` prints `text` exactly as it came back. This
 *  file does not slice "AMD " off anything — if it did, the board and the
 *  backend's own histogram could word the same grade two different ways, and
 *  a served sentence would be edited on the way to the screen. */
export function amdCell(r?: HsAmd | null, s?: HsAmdSummary | null): Cell {
  const why = s?.no_colour_reason ? ` ${s.no_colour_reason}` : '';
  if (!r) return { text: DASH, tone: 'dim', title: GENERIC_BLANK };
  if (!r.known) {
    return { text: DASH, tone: 'dim', title: r.reason_text || GENERIC_BLANK };
  }
  const text = typeof r.text === 'string' ? r.text.trim() : '';
  // THE FE BELT for the backend guard: a served `known: true` with no wording
  // is a backend bug, and it must still render as a blank with a reason rather
  // than as an empty cell that reads like a column that stopped working. The
  // LONG form is what that belt tests, because it is the wording every other
  // consumer reads — a row with a short and no long is a broken row.
  if (!text) return { text: DASH, tone: 'dim', title: EMPTY_TEXT_BLANK };
  const short = typeof r.short === 'string' ? r.short.trim() : '';
  return { text: short || text, tone: 'dim', title: `${r.title || text}${why}` };
}

/** A sector / industry / roster row. ALWAYS an em-dash, with the served reason.
 *  The group row's other cells are medians over the FULL membership; a count
 *  over the 25 names the payload carries would describe a different
 *  population. The counts live in one line above the table. */
export function amdGroupCell(s?: HsAmdSummary | null): Cell {
  return { text: DASH, tone: 'dim', title: s?.group_note || GROUP_BLANK };
}

/** The column header's hover — the SERVED sentence, verbatim. */
export function amdHeadTitle(s?: HsAmdSummary | null): string {
  return s?.head_title || HEAD_FALLBACK;
}

/** The line above the table: the served coverage sentence, plus the served
 *  staleness sentence when the sweep that was DUE is missing. When the read
 *  itself is unavailable this is the served line that says so instead — the
 *  column then does not draw at all, and silence would be a lie. */
export function amdCoverageNote(s?: HsAmdSummary | null): string | null {
  if (!s) return null;
  if (s.available === false) return s.unavailable_note || null;
  const parts = [s.coverage_note, s.stale ? s.stale_note : null]
    .filter((x): x is string => typeof x === 'string' && x.trim() !== '');
  return parts.length ? parts.join(' ') : null;
}
