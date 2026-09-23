/* 🔥 Hottest — sectors ranked, opening into industries and then names.
 *
 * Ajay 2026-09-11: "From the sectors. Can you find the hottest of the sectors
 * like the most growth and put them in to a new tab" · "hottest from last 5
 * days and current. Like ANDE was never on my list but its growing" · "List
 * needs to be hottest of the sectors and then hottest from a sector in to a
 * table. Like the catalyst and keep sales and other crucial metrics for me."
 *
 * Asked which window and which grouping, he chose all three legs (today / 5d /
 * 21d) and sectors that expand into industries.
 *
 * WHY ALL ELEVEN SECTORS SHOW, not just the hot end: his own example is a
 * strong name in a COLD sector. ANDE is 2nd of Consumer Defensive's 76 over 21
 * days while the sector sits 8th of 11. A hot-sectors-only list cannot reach
 * it, so every sector is listed and the cold ones simply sort last.
 *
 * The backend owns every number (rotation/hottest.py). Nothing here recomputes
 * heat or traction — two definitions on two surfaces is how the strip and this
 * board would start disagreeing.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent as ReactMouseEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { TickerLink, openTickerWithModifier } from './TickerLink';
import { GrowthChip } from './GrowthChip';
import { PromoOriginChip } from './PromoOriginChip';
import { ExplosiveChip } from './ExplosiveChip';
import { EnterableChip } from './EnterableChip';
import { BandStructureChip } from './BandStructureChip';
import { HiddenCount } from './HiddenCount';
import { useEnterableFilter, useEnterablePartition } from '../hooks/useEnterableFilter';
import { isShown } from '../lib/enterable';
import { useBounceRoom } from '../hooks/useBounceRoom';
import type { BandStructureStudy, BounceRoomRow, ExplosiveStudy } from '../lib/bounceRoom';
import { SignalWatchButton } from './SignalWatchButton';
import { InfoButton } from './InfoButton';
import { periodMark } from '../lib/bondeLive';
import {
  AMD_COL, amdCell, amdCoverageNote, amdGroupCell, amdHeadTitle, amdToneClass, showAmdCol,
} from '../lib/hottestAmd';
import type { HsAmd, HsAmdSummary } from '../lib/hottestAmd';

/** Which session the day column on THIS row came from. `live` = the name's own
 *  move so far in the current session; `close` = the rotation snapshot's last
 *  finished session. Backend-owned (rotation/hottest.py) — never inferred here
 *  from whether a number happens to look fresh. */
export type HsD1Source = 'live' | 'close';
/** The day leg's basis for the whole board.
 *
 *  `group_basis` was pinned to `close` until 2026-09-23, when Ajay read a
 *  rotating morning off rows that were a day behind the names under them
 *  ("Its actualy rotating this morning I wanna see live rotattion" — 19 of the
 *  29 roster rows carried the opposite SIGN to their own members' live median).
 *  A group row now goes live with the board, as the median over the members of
 *  that row that have a live print — never a median mixing live members with
 *  last-close ones, which describes no session at all. */
export type HsD1 = {
  basis?: HsD1Source; live?: boolean;
  /** When the live read was taken (ISO), and which close the rest is from. */
  as_of?: string | null; close_as_of?: string | null;
  benchmark?: string | null; benchmark_move?: number | null;
  symbols?: number | null; live_names?: number | null;
  group_basis?: HsD1Source;
  /** The sentence for `group_basis`, written by the backend that enforces it —
   *  this surface never composes the cohort rule itself. */
  group_basis_note?: string | null;
  /** Plain-English why, when the board is NOT live. Must reach the screen. */
  reason?: string | null; note?: string | null;
  /** WHY a re-scan cannot help: the market calendar's own reason (weekend /
   *  holiday YYYY-MM-DD), or null on a trading day. Backend-owned, so nothing
   *  here ever string-matches prose to decide the tape is shut. */
  market_closed?: string | null;
  /** Is the REGULAR session open (supply_demand.bounce_room.in_session)?
   *  `null` when the clock could not be asked — the button then behaves as it
   *  did before this existed rather than guessing. */
  in_session?: boolean | null;
  /** "9:30-16:00 ET", rendered from the constants that enforce it — never a
   *  clock retyped on this surface. */
  session_window?: string | null;
};
/** The two day-leg fields every row carries since 2026-09-16: the snapshot
 *  value is kept whatever the live read did, and the row says which it shows. */
export type HsDayLeg = {
  rel_1d?: number | null; rel_1d_close?: number | null;
  ret_1d_close?: number | null; d1_source?: HsD1Source;
  /** GROUP ROWS ONLY (2026-09-23). How many of the row's members had a live
   *  print, out of how many it has — the live median's own denominator, which
   *  is NOT the membership `rel_1d_close` was taken over. `d1_live_close` is
   *  the close median over THOSE SAME members, so the pair is comparable;
   *  `rel_1d_close` and `rel_1d` are not, and are never subtracted here. */
  d1_live_n?: number | null; d1_live_of?: number | null;
  d1_live_close?: number | null;
};

/* ☀️ Pre-market scan (Ajay 2026-09-21: "In the hot sector table can I get a
 * pre market scan please").
 *
 * A THIRD basis, served as a SIBLING block `pre` beside `d1` — the day column
 * and every row's day-leg key are byte-identical whether or not the scan ran,
 * which is why `HsD1Source` is NOT widened to a third member: `d1Label`,
 * `dayCell` and `asOfLine` all switch on that union, and a third value would
 * quietly change what the Today column claims.
 *
 * NOTHING here is measured. Pre-market moves as a signal have never been
 * studied on this app; this is a read of the tape before the open. */
export type HsSession = 'premarket' | 'rth' | 'afterhours' | 'closed';
export type HsPre = {
  basis?: 'premarket'; live?: boolean; ran?: boolean; stored?: boolean; ended?: boolean;
  /** Backend-owned. `show` = draw the Pre-mkt column; `open` = the ☀️ button is usable.
   *  Never derived from a browser clock; on a stored read the server re-derives both
   *  from ITS clock, so a doc stored at 07:20 cannot leave the button live at 10:05. */
  show?: boolean; open?: boolean | null; session?: HsSession | null;
  pre_window?: string | null; market_closed?: string | null; date?: string | null;
  /** The yardstick's OWN pre-market print — and its TIME, because an ETF
   *  prints far less often than a name (07:27 ET probe: RSP 5:00, NVDA 7:27). */
  benchmark?: string | null; benchmark_pre_move?: number | null;
  benchmark_pre_print?: number | null; benchmark_pre_at?: string | null;
  benchmark_pre_at_et?: string | null;
  symbols?: number | null; pre_names?: number | null;
  /** SERVED pre-formatted ("7:42 ET") — this surface never composes a clock. */
  as_of?: string | null; as_of_et?: string | null;
  group_basis?: string | null; reason?: string | null; note?: string | null;
};
/** A name row's pre-market leg. Every key is null when it did not print — an
 *  absent print is never a zero move. */
export type HsPreLeg = {
  pre_1d?: number | null; pre_raw?: number | null; pre_print?: number | null;
  pre_at?: string | null; pre_at_et?: string | null;
};
/** A group row's: the median over the members that PRINTED, with that count.
 *  `pre_thin` is the board's own THIN_N rule applied to the printed subset —
 *  the existing `thin` key already means something else (the full membership). */
export type HsPreGroup = HsPreLeg & {
  pre_n?: number | null; pre_thin?: boolean | null; pre_basis?: string | null;
};

export type HsName = HsDayLeg & HsPreLeg & {
  symbol: string; name?: string | null; industry?: string | null;
  last_close?: number | null;
  rel_5d?: number | null; rel_21d?: number | null;
  ret_1d?: number | null; ret_5d?: number | null; ret_21d?: number | null;
  traction?: number | null; vs_group_21?: number | null; at_demand?: boolean;
  sales_yoy?: number | null; sales_tier?: string | null;
  sales_accelerating?: boolean | null; sales_prior_yoy?: number | null;
  q_eps_yoy?: number | null; y_eps_growth?: number | null;
  net_margin?: number | null; margin_expanding?: boolean | null;
  eq_score?: number | null; eq_tier?: string | null; code_33?: boolean | null;
  sales_backed?: boolean | null; inventory_flag?: boolean | null;
  next_earnings?: string | null; earnings_when?: string | null;
  /** The year-over-year pair check, tri-state, served per name by
   *  rotation/hottest.py::_fundamentals_row. `false` = the two quarters are
   *  not four fiscal quarters apart; `null`/absent = there were no period
   *  keys to check it with; `true` = checked and fine. */
  period_ok?: boolean | null;
  /** 🌀 The served AMD cycle read for this name (2026-09-22). A pure READ of
   *  the nightly sweep's stored document — never recomputed on the request,
   *  and it sorts, filters, colours and gates nothing. */
  amd?: HsAmd | null;
};
/** The fundamental columns a GROUP row carries: the median of its full
 *  membership, computed in rotation/hottest.py::_fund_medians. Before
 *  2026-09-12 these columns were blank on sector and industry rows, so
 *  sorting on one of them reordered the tree for no visible reason. */
export type HsFundMedians = {
  sales_yoy?: number | null; sales_tier?: string | null;
  q_eps_yoy?: number | null; net_margin?: number | null;
  eq_score?: number | null; fund_basis?: string | null;
};
export type HsIndustry = HsFundMedians & HsDayLeg & HsPreGroup & {
  group: string; n_full: number; ranked: boolean; thin: boolean; basis: string;
  rel_5d?: number | null; rel_21d?: number | null;
  names: HsName[]; names_total: number;
};
/** 📰 The day's two-sided news tag for a sector (Ajay 2026-09-19: "if you
 *  see any postive news I would like you to see a bullish and bearish case
 *  result for a stocks and add it to the sector as a tag for that day").
 *
 *  Written by the cron in backend/rotation/sector_news_tags.py, served as a
 *  pure read. `measured` is ALWAYS false and `read_by` names who wrote the
 *  prose — the surface must never present this as a measurement, and there
 *  is no sentiment score here because we do not have a measured one. */
export type HsDayTag = {
  date: string;
  sector: string;
  symbol: string;
  company?: string | null;
  positive: boolean;
  why_positive?: string | null;
  bull: string;
  bear: string;
  headline_count?: number | null;
  trigger?: { title?: string | null; url?: string | null;
              source?: string | null; published?: number | null } | null;
  /** EVERY headline the model was shown, not just the trigger — the audit
   *  trail for "grounded in the headlines". The news cache rolls within
   *  hours, so without these a number in the prose cannot be traced back. */
  headlines?: { title?: string | null; source?: string | null;
                url?: string | null; published?: number | null }[] | null;
  facts?: Record<string, unknown> | null;
  read_by?: string | null;
  measured?: boolean;
};

export type HsSector = HsFundMedians & HsDayLeg & HsPreGroup & {
  group: string; n_full: number; sampled_of?: number | null; sampled_used?: number | null;
  basis: string; n_measured?: number | null;
  rel_5d?: number | null; rel_21d?: number | null;
  industries: HsIndustry[]; names: HsName[]; names_total: number;
  /** null when today produced no tag for this sector — the board then
   *  renders exactly as it did before any of this existed. */
  day_tag?: HsDayTag | null;
};
export type HsTheme = HsFundMedians & HsDayLeg & HsPreGroup & {
  group: string; n_full: number; ranked: boolean; thin: boolean; basis: string;
  rel_5d?: number | null; rel_21d?: number | null;
  names: HsName[]; names_total: number;
};
export type HsPayload = {
  as_of?: string; sorted_by?: string; sorted_dir?: string;
  /** The endpoint answers with the tracker's benchmark OBJECT on some builds
   *  and a bare symbol on others — `benchSymbol` resolves both, because a
   *  header that prints "[object Object]" names no benchmark at all. */
  benchmark?: string | { symbol?: string | null } | null;
  /** What the day column is showing, and why (2026-09-16). */
  d1?: HsD1 | null;
  /** ☀️ The pre-market scan's own block (2026-09-21) — a SIBLING of `d1`,
   *  never nested inside it, so the day column cannot be changed by it. */
  pre?: HsPre | null;
  /** 🌀 The AMD column's board-level block (2026-09-22) — a SIBLING of `d1`
   *  and `pre`. Absent entirely on the member-table-unavailable branch, which
   *  is exactly how the column knows not to draw there. */
  amd_summary?: HsAmdSummary | null;
  sortable?: string[]; legs?: string[];
  sectors: HsSector[];
  /** Our own curated rosters — robotics, nuclear, quantum, the AI complex,
   *  crypto. They cut ACROSS the provider's sectors (robotics spans Technology,
   *  Industrials and Consumer Cyclical), so they are a FLAT list with no
   *  industry layer, and they ride alongside the sectors rather than replacing
   *  them: the two disagree and the objective label wins. */
  themes?: HsTheme[];
  coverage?: { priced?: number; with_fundamentals?: number; pct?: number | null };
  note?: string; reason?: string; built_at_iso?: string; stale?: boolean;
};

/** Readable names for the curated rosters. The payload ships the snake_case id
 *  (it is the key everything else in the app joins on); only the display
 *  changes here. An id with no entry prints as-is rather than being prettified
 *  by a rule that would one day mangle a new one. */
export const THEME_LABELS: Record<string, string> = {
  ai_semis: 'AI semis',
  semi_materials: 'Semi materials',
  ai_power: 'AI power',
  ai_infra: 'AI infra',
  datacenter_build: 'Datacenter build',
  cloud_infra: 'Cloud infra',
  optical: 'Optical',
  robotics: 'Robotics',
  nuclear: 'Nuclear',
  energy: 'Energy (curated)',
  quantum: 'Quantum',
  space: 'Space',
  defense: 'Defense',
  rare_earth: 'Rare earth',
  crypto: 'Crypto equities',
};

export type HsDir = 'desc' | 'asc';
/** Every column, in print order, with the payload key it ranks on.
 *
 *  Ajay 2026-09-12: "Add sort in this". The sort is a BACKEND round-trip, not
 *  a client-side reorder, because the payload holds only `names_per_group`
 *  rows per group — sorting in the browser would rank the visible 25 and never
 *  reach the 46th name. `asc` is the useful direction for Next ER (who reports
 *  soonest) and for hunting the weak end of a column. */
/** One printed column. `sortable: false` (only 🌀 AMD today) renders a plain
 *  header instead of a sort button — see the header block below. */
export type HsCol = { key: string; label: string; num: boolean; title?: string;
                      sortable?: boolean };
export const HS_COLS: HsCol[] = [
  { key: 'rel_1d', label: 'Today', num: true },
  { key: 'rel_5d', label: '5 days', num: true },
  { key: 'rel_21d', label: '21 days', num: true },
  { key: 'sales_yoy', label: 'Sales YoY', num: true },
  { key: 'sales_tier', label: 'Sales trend', num: false,
    title: 'ranks explosive › strong › steady › weak › declining' },
  { key: 'q_eps_yoy', label: 'Q EPS', num: true },
  { key: 'net_margin', label: 'Margin', num: true },
  { key: 'eq_score', label: 'Quality', num: true,
    title: 'Minervini Ch.8 earnings quality · 🎯 Code 33 · ⚠️ inventory vs sales' },
  { key: 'next_earnings', label: 'Next ER', num: false,
    title: 'ascending = who reports soonest' },
];

/** ☀️ The Pre-mkt column. NOT a member of HS_COLS: it is conditional on the
 *  served `pre.show`, because an always-present column full of em-dashes is
 *  furniture on a board he already called wide. */
export const PRE_COL: HsCol = {
  key: 'pre_1d', label: 'Pre-mkt', num: true,
  title: "Each name's own pre-market print against RSP's own pre-market print"
    + ' (its time is in the line above); group rows are the median of the'
    + ' members that printed, with the count',
};

/** Draw the Pre-mkt column? The SERVER decides — never a browser clock. */
export function showPreCol(d?: Pick<HsPayload, 'pre'> | null): boolean {
  return !!d?.pre?.show;
}
/** The columns actually printed, in print order. Both extras are conditional
 *  on the SERVER saying so.
 *
 *  🌀 AMD SITS IMMEDIATELY AFTER Sector / Name (Ajay 2026-09-22: *"last column
 *  is hidded"* — it shipped last, and on his window the header read "🌀 A" and
 *  the cells read "AM"). It is a STATE ABOUT THE NAME, and the Sector / Name
 *  cell already carries this row's other per-name state chips (floor-held,
 *  at-band, 🚀, 🎪). A state belongs beside the thing it describes. The move
 *  also keeps the ranked numeric legs (Pre-mkt | Today | 5 days | 21 days)
 *  CONTIGUOUS and in order, which they are not when a state column is wedged
 *  in after them.
 *
 *  Pre-mkt still leads the RANKED LEGS, the way they already read newest to
 *  oldest, and HS_COLS keeps its order untouched.
 *
 *  THIS DOES NOT MAKE THE TABLE FIT, AND NOTHING HERE DECIDES WHICH COLUMN
 *  GIVES WAY INSTEAD. `.hs-table` sets `min-width: 900px` (760px inside the
 *  720px media block) and this table prints up to TWELVE columns — Sector /
 *  Name, 🌀 AMD, ☀️ Pre-mkt and the nine in HS_COLS. On a narrow window it
 *  scrolls sideways before the move and after it. What the move buys is the
 *  SCROLL POSITION: the state is now the first thing right of the name, so he
 *  reads it without moving anything, which is what he asked for.
 *
 *  Which of his existing columns is dropped or narrowed to END the scroll is
 *  HIS decision, not ours — it is open in § His call of
 *  docs/rotation/hottest_expand_all_2026_09_22.md. Note while reading it that
 *  the day column is at its WIDEST exactly when he reads this board before the
 *  open: `d1Label` prints `Last close YYYY-MM-DD` whenever `d1.live` is false
 *  (rotation/hottest.py), i.e. every pre-market and after-hours read, the
 *  ☀️ basis=premarket board included.
 *
 *  ON A PHONE (the ≤720px block) the move pushes every ranked leg one column
 *  further right, because 🌀 now sits between the name and them. Whether a
 *  phone should wrap this cell or not draw the column at all is on the same
 *  his-call list. Nothing here picks one silently.
 *
 *  NO ESTIMATED px FIGURE IS QUOTED here or in either doc. The version that
 *  shipped with the move carried an arithmetic width model — a table floor, a
 *  box width, a per-column width for Next ER — built from measured character
 *  counts and ASSUMED per-character advances, with no browser ever opened, and
 *  Rule #1 does not take a model for a measurement. The px values above are
 *  styles.css's own `min-width` declarations, read off the source. */
export function visibleCols(d?: Pick<HsPayload, 'pre' | 'amd_summary'> | null): HsCol[] {
  return [
    ...(showAmdCol(d) ? [AMD_COL] : []),
    ...(showPreCol(d) ? [PRE_COL] : []),
    ...HS_COLS,
  ];
}
/** The full-width colSpan for every grain / "showing N of M" / news row: the
 *  symbol column plus whatever columns are printed. Hard-coded 10s are how a
 *  new column leaves five rows one cell short. */
export function colSpanOf(d?: Pick<HsPayload, 'pre' | 'amd_summary'> | null): number {
  return 1 + visibleCols(d).length;
}

/** The arrow a header shows. Inactive columns show nothing — an idle ⇅ on
 *  nine headers is nine pieces of furniture. */
export function arrow(active: boolean, dir: HsDir): string {
  return active ? (dir === 'desc' ? ' ▼' : ' ▲') : '';
}

/* ── "Today" has to mean today (Ajay 2026-09-16) ─────────────────────────────
 *
 * He read TENB at +8.3% under a column headed "Today" while his own ticker page
 * had it at −3.70%, live, the same minute. Both were right: the rotation
 * snapshot is built after the close, so the column was printing the PREVIOUS
 * session under today's word. The backend now serves the live move on the name
 * rows; these helpers make sure the header, the as-of line and any row that
 * missed the live read can never claim a number they do not have. */

/** The benchmark's symbol, whichever shape the payload used. */
export function benchSymbol(d?: Pick<HsPayload, 'benchmark'> | null): string {
  const b = d?.benchmark;
  if (typeof b === 'string' && b.trim()) return b;
  const s = b && typeof b === 'object' ? b.symbol : null;
  return typeof s === 'string' && s.trim() ? s : 'RSP';
}

/** The day column's header. "Today" ONLY when the number is today's; otherwise
 *  the session it actually came from, so the header cannot lie on its own. */
export function d1Label(d?: Pick<HsPayload, 'd1' | 'as_of'> | null): string {
  if (d?.d1?.live) return 'Today';
  const day = d?.d1?.close_as_of || d?.as_of;
  return day ? `Last close ${day}` : 'Last close';
}

/** Any column's printed header. */
export function colLabel(key: string, d?: Pick<HsPayload, 'd1' | 'as_of'> | null): string {
  if (key === 'rel_1d') return d1Label(d);
  /* The Pre-mkt column is not in HS_COLS, and the lookup below falls through
   * to the RAW KEY — so without this line the header would print `pre_1d`. */
  if (key === PRE_COL.key) return PRE_COL.label;
  /* Same trap for the 🌀 column, which is not in HS_COLS either. */
  if (key === AMD_COL.key) return AMD_COL.label;
  return HS_COLS.find((c) => c.key === key)?.label || key;
}

/** Which header the `is-sorted` mark sits on.
 *
 *  STATE wins for every key except `pre_1d`. The server DEMOTES a `pre_1d`
 *  request to the default whenever the pre leg has nothing to rank on (RSP has
 *  not printed, nobody printed, the session ended) and says so in `sorted_by`;
 *  the mark then follows the served key, so the arrow never sits on a column
 *  the rows are not ordered by.
 *
 *  PURE on purpose: no setState, no refetch, no clock. `sort` is a `load`
 *  dependency, so "fixing" the state here would fire a SECOND fan-out on the
 *  very click whose tooltip promises one. Keeping the `pre_1d` intent in state
 *  also means the next ↻ ranks on it the moment RSP prints. */
export function shownSortKey(sort: string,
                             d?: Pick<HsPayload, 'sorted_by' | 'pre'> | null): string {
  const served = d?.sorted_by;
  if (sort === PRE_COL.key && served && served !== PRE_COL.key) return served;
  return sort;
}

/** A header's hover. The day column's says which session it is, in the
 *  backend's own words, so the explanation cannot drift from the numbers. */
export function colTitle(c: { key: string; title?: string },
                         d?: Pick<HsPayload, 'd1' | 'as_of'> | null): string {
  const own = c.key === 'rel_1d' ? (d?.d1?.note || '') : (c.title || '');
  return own ? `${own} · click to sort` : 'click to sort';
}

/* ── ⊞ Expand all (Ajay 2026-09-22) ──────────────────────────────────────────
 *
 * *"Also give me toggle option to open them app on one click in stead of
 *  clicking on the carets"* — said over a screenshot of the Defense roster.
 *
 * THE DEPTH FOLLOWS THE VIEW, and that is not cosmetic. In the DEFAULT view
 * (`byIndustry` is true, see the state below) a sector renders its INDUSTRIES
 * and not its names; the names hang off the industry caret. So a rule that
 * opened only the top level would answer his ask for the rosters in his
 * screenshot and open eleven sectors into 136 empty industry headers — he
 * would still be clicking carets, in the view that actually loads. With the
 * checkbox off, the industry rows are not rendered at all, so inheriting into
 * those keys would be state with no meaning.
 *
 * The 📰 news-tag rows share this very map (`${k}|tag`). They are LLM
 * briefings, not names, and expand-all must never dump every one of them into
 * the table — that clause is the whole guard and it is a pinned negative test.
 *
 * `all` is the blanket answer, `ov` holds every caret he moved by hand, and an
 * explicit override always wins: a caret he closed under ⊞ stays closed.
 */
export type HsOpen = { all: boolean | null; ov: Record<string, boolean> };

/** The preference key, in the `pcw.capFloor` shape — this board persisted
 *  nothing before this, and one scheme is enough. */
export const HS_EXPAND_KEY = 'hs.expandAll';
/** `null` = never chosen on this browser, which is the shipped default
 *  (closed). A throwing accessor (private mode, blocked site data) is a
 *  `null`, never a crash. */
export function readExpandAllPref(): boolean | null {
  try {
    const v = localStorage.getItem(HS_EXPAND_KEY);
    return v === 'open' ? true : v === 'closed' ? false : null;
  } catch { return null; }
}
export function writeExpandAllPref(v: boolean): void {
  try { localStorage.setItem(HS_EXPAND_KEY, v ? 'open' : 'closed'); } catch { /* private mode */ }
}

/** Does the blanket `all` reach this key in THIS view? */
export function inheritsAll(k: string, byIndustry: boolean): boolean {
  if (k.endsWith('|tag')) return false;          // 📰 news briefings: NEVER
  if (k.includes('|i:')) return byIndustry;      // industry rows draw only in that view
  return true;                                   // t:* rosters and s:* sectors
}
/** An explicit per-caret choice beats the blanket one, in both views. */
export function isGroupOpen(o: HsOpen, k: string, byIndustry: boolean): boolean {
  return k in o.ov ? o.ov[k] : (o.all === true && inheritsAll(k, byIndustry));
}
/** One caret. Always flips what is on SCREEN, so the first click after ⊞
 *  closes rather than re-opening something already open. */
export function toggleKey(o: HsOpen, k: string, byIndustry: boolean): HsOpen {
  return { all: o.all, ov: { ...o.ov, [k]: !isGroupOpen(o, k, byIndustry) } };
}
/** The blanket answer, which also clears every hand-moved caret — ⊞ means all. */
export function setAll(v: boolean): HsOpen { return { all: v, ov: {} }; }

/** Every roster and sector key in this payload. */
export function topLevelKeys(d?: HsPayload | null): string[] {
  return [
    ...(d?.themes || []).map((t) => `t:${t.group}`),
    ...(d?.sectors || []).map((s) => `s:${s.group}`),
  ];
}
/** What ⊞ actually opens in THIS view — the top level, plus every industry
 *  while "Break into industries" is on. Never a `|tag` key. */
export function openedKeys(d?: HsPayload | null, byIndustry = true): string[] {
  const out = topLevelKeys(d);
  if (byIndustry) {
    for (const s of d?.sectors || []) {
      for (const ind of s.industries || []) out.push(`s:${s.group}|i:${ind.group}`);
    }
  }
  return out;
}
/** Is everything ⊞ would open already open? An empty board is never "all
 *  open" — the button would otherwise mount saying ⊟ Collapse all. */
export function allGroupsOpen(o: HsOpen, keys: string[], byIndustry: boolean): boolean {
  return keys.length > 0 && keys.every((k) => isGroupOpen(o, k, byIndustry));
}
/** How many rows one click puts on screen, counted from THIS payload — a
 *  fact for the hover, never a guess. Group rows the click reveals (the
 *  industries) plus every name row under what it opened. */
export function expandRowCount(d?: HsPayload | null, byIndustry = true): number {
  let n = 0;
  for (const t of d?.themes || []) n += (t.names || []).length;
  for (const s of d?.sectors || []) {
    if (byIndustry) {
      for (const ind of s.industries || []) n += 1 + (ind.names || []).length;
    } else {
      n += (s.names || []).length;
    }
  }
  return n;
}
/** The control's hover. Says what it opens, why the depth is what it is in
 *  this view, the real row count, and that the choice is remembered. */
export const EXPAND_ALL_TITLE = (rows: number, open: boolean, byIndustry: boolean): string =>
  (open
    ? 'Closes every roster and sector'
      + (byIndustry ? ' — and every industry under them' : '')
      + ` — back to the headers, in one click: ${rows} rows leave the table.`
    : 'Opens every roster and sector — and, while “Break into industries” is on,'
      + ' every industry under them, because that is where the names live in this'
      + ` view — in one click: ${rows} rows from this payload.`)
  + ' Your choice is remembered on this browser.';

/** One day cell, as text + whether it needs the visible "last close" mark.
 *
 *  A row is MARKED when the board is live but this row is not — its number is
 *  the previous session's and would otherwise sit silently in a live column.
 *  When the whole board is on the close the header already says so and 300
 *  identical marks would be noise, so the rows stay clean. */
export function dayCell(r: HsDayLeg, d?: Pick<HsPayload, 'd1' | 'as_of' | 'benchmark'> | null,
                        isGroup = false):
                        { text: string; marked: boolean; title: string; partial: boolean } {
  const boardLive = !!d?.d1?.live;
  const rowLive = r.d1_source === 'live';
  const day = d?.d1?.close_as_of || d?.as_of || '';
  const marked = boardLive && !rowLive;
  const why = isGroup
    ? `Not one member of this row has a live print, so this is the median over ALL of its`
      + ` members taken on the ${day || 'last'} close — a median mixing live names with`
      + ' last-close names would describe no session at all.'
    : `No live price came back for this name, so this is its ${day || 'last'} close move`
      + ' — not today.';
  /* A LIVE GROUP ROW says what it is a median OF, with the denominator, and
   * gives the same-cohort close beside it. The row's other close number
   * (`rel_1d_close`) is a median over a different set — for a sector, the
   * rotation grid's own sample — so it is deliberately NOT the one shown here
   * and the two are never differenced. */
  const n = r.d1_live_n, of = r.d1_live_of, was = r.d1_live_close;
  const groupLive = `The median over the ${n ?? '—'} of this row's ${of ?? '—'} members`
    + ` trading now, measured against ${benchSymbol(d)} the same way the other columns are.`
    + (was != null ? ` Those same ${n} names closed at ${pct(was)} on ${day || 'the last close'}.` : '');
  const nameLive = `Today's move so far, measured against ${benchSymbol(d)} the same way the other columns are.`;
  const live = isGroup ? groupLive : nameLive;
  /* PARTIAL = this row went live on fewer members than it has. `n < of` is the
   * one test and both numbers are served; a missing count is NOT partial,
   * because inventing a denominator is worse than showing none. */
  const partial = !!(rowLive && n != null && of != null && n < of);
  return { text: pct(r.rel_1d), marked, partial,
           title: marked ? why : (rowLive ? live : '') };
}

/** The line under the controls. It must say which columns are live and which
 *  are the snapshot's, because four of the nine never move intraday. */
export function asOfLine(d?: Pick<HsPayload, 'd1' | 'as_of' | 'benchmark' | 'pre'> | null): string {
  const day = d?.d1?.close_as_of || d?.as_of || '—';
  const base = d?.d1?.live
    ? `Today is live for the names AND for every sector, industry and roster row,`
      + ` measured against ${benchSymbol(d)} · 5 days, 21 days and Sales YoY are from`
      + ` the ${day} close`
    : `every column is from the ${day} close — the last finished session, not today's`
      + (d?.d1?.reason ? ` (${d.d1.reason})` : '');
  /* ☀️ The pre-market prefix, in the SERVER's own words. Three states, in this
   * order: a live scan, a scan whose session has ended, and a scan that RAN
   * and came back with nothing — the last one is why a click can change the
   * board not at all and he still sees the reason. An idle block adds nothing,
   * so every line above stays byte-identical to what it printed before this. */
  const p = d?.pre;
  if (p?.live) {
    return `Pre-market is the ${p.as_of_et} read on ${p.pre_names} of ${p.symbols} names,`
      + ` measured against ${p.benchmark || benchSymbol(d)}'s ${p.benchmark_pre_at_et}`
      + ` pre-market print (${pct(p.benchmark_pre_move, 2)}) · ${base}`;
  }
  if (p?.ended && p?.show) return `Pre-market: ${p.reason} · ${base}`;
  if (p?.ran && !p?.live && p?.reason) return `Pre-market: ${p.reason} · ${base}`;
  return base;
}

/** Why a ↻ Re-scan cannot help right now, or null when it can.
 *
 *  The calendar's reason is the BACKEND's own sentence, never composed here —
 *  two surfaces wording the same fact differently is how a board starts
 *  disagreeing with itself. */
export function rescanBlockedReason(d?: Pick<HsPayload, 'd1'> | null): string | null {
  const c = d?.d1?.market_closed;
  return typeof c === 'string' && c.trim() ? `the market is closed (${c.trim()})` : null;
}

/** Open tape, but outside the regular session: a re-scan spends the same
 *  provider reads and comes back with the same numbers, because the day bar is
 *  0 before the open and finished after the close.
 *
 *  WARNED, not blocked. He reads extended-hours prints on the Chart Maps tiles
 *  (04:00-20:00, his call), so removing the read outside 9:30-16:00 would take
 *  away a surface he asked for. Making it a block is HIS CALL. */
export function rescanQuietReason(d?: Pick<HsPayload, 'd1'> | null): string | null {
  const s = d?.d1;
  if (!s || s.in_session !== false) return null;
  const w = (s.session_window || '').trim();
  return w ? `the session is shut (${w}) — the day column will not move`
           : 'the session is shut — the day column will not move';
}

/** Does this payload have anything to DRAW? A 200 carrying only `reason` has
 *  not — and replacing a good board with that line is how a failed re-scan
 *  used to blank the whole page. */
export function hasRows(d?: HsPayload | null): boolean {
  return Boolean(d && (((d.sectors || []).length) || ((d.themes || []).length)));
}

/** What one click costs, in the same sentence everywhere it appears. MEASURED
 *  2026-09-18 on the live payload: 7 board chunks (1,721 names / 250), plus 6
 *  bounce-room chunks (1,468 unique name rows / 250) only when the re-rank
 *  changes which names each group shows — both cache keys are sorted sets, so
 *  a pure re-order is free. Never quoted as a bare 7. */
export const RESCAN_COST_SENTENCE =
  'One click is the same provider read as reloading the page — 7 snapshot calls, '
  + 'or 13 when the re-rank changes which names each group shows.';

/** An em-dash, never a zero — a missing quarter is not flat growth. */
export function pct(v: number | null | undefined, dp = 1): string {
  return typeof v === 'number' && Number.isFinite(v) ? `${v >= 0 ? '+' : ''}${v.toFixed(dp)}%` : '—';
}
/** Tone by the value's OWN sign. Ajay 2026-09-10: "what ever today is what I
 *  wanna see in green" — so today's cell is green only when today is up, even
 *  inside a row that is hot over five days. */
export function tone(v: number | null | undefined): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return 'hs-flat';
  return v > 0 ? 'hs-up' : v < 0 ? 'hs-dn' : 'hs-flat';
}
/** ☀️ Is the Pre-market scan button usable, and what does its hover say?
 *
 *  ENABLED IFF THE SERVER SAYS SO. `pre.open` is the backend's own clock —
 *  there is no browser clock anywhere in this function on purpose, and the
 *  contract pins that: a browser clock would hand a laptop in London a board
 *  that thinks the New York pre-market is open. On a STORED read the server
 *  re-derives `open` from its CURRENT clock, so a doc written at 07:20 cannot
 *  leave this button live at 10:05. */
export function premarketState(d?: Pick<HsPayload, 'pre' | 'benchmark'> | null):
  { enabled: boolean; title: string } {
  const p = d?.pre;
  if (p?.open !== true) {
    return { enabled: false,
             title: `Pre-market scan is off because ${p?.reason || 'the session could not be read'}.` };
  }
  return {
    enabled: true,
    title: `Reads every name's pre-market print (${p.pre_window}) against `
      + `${benchSymbol(d)}'s own, one read for the whole board. ${RESCAN_COST_SENTENCE}`
      + ' Group rows become the median of the members that printed, with the count.'
      + ' Not measured, not a signal.',
  };
}

/** One Pre-mkt cell: the text, whether it reads thin, and its hover.
 *
 *  A group row prints `+0.8% · 12/40` — the median AND how many of the
 *  membership actually printed, because at 07:00 most names have not (the
 *  extended-hours passes see ~80% stale prints) and a median over 12 of 40 is
 *  not the same object as the full-membership medians beside it. A name that
 *  did not print is an em-dash, never a zero. */
export function preCell(r: HsPreGroup & { n_full?: number },
                        d?: Pick<HsPayload, 'pre' | 'benchmark'> | null,
                        isGroup = false): { text: string; thin: boolean; title: string } {
  const p = d?.pre;
  const text = pct(r.pre_1d) + (isGroup && r.pre_n != null ? ` · ${r.pre_n}/${r.n_full}` : '');
  const thin = isGroup && r.pre_thin === true;
  if (isGroup) {
    const basis = r.pre_basis || p?.group_basis || 'median of the members that printed';
    return { text, thin,
             title: `${basis}: ${r.pre_n ?? 0} of ${r.n_full ?? 0} printed`
               + (thin ? ' — too few printed to read this like a full-membership median' : '') };
  }
  if (r.pre_at_et == null || r.pre_1d == null) {
    return { text, thin: false, title: 'no pre-market print for this name yet' };
  }
  return { text, thin: false,
           title: `printed ${r.pre_at_et} at ${r.pre_print} · own move ${pct(r.pre_raw, 2)}`
             + ` · ${p?.benchmark || benchSymbol(d)} ${pct(p?.benchmark_pre_move, 2)}`
             + ` at ${p?.benchmark_pre_at_et}` };
}

export function tierChip(t?: string | null): string {
  const k = (t || '').toLowerCase();
  if (k === 'explosive') return '🚀';
  if (k === 'strong') return '💪';
  if (k === 'steady') return '➖';
  if (k === 'weak') return '🐌';
  if (k === 'declining') return '🔻';
  return '';
}

/** The 📰 chip that sits beside a sector's name when the day produced a tag.
 *
 *  Says only WHO it is about and that there is a read to open — the argument
 *  itself lives in the expanded row, because a sector row is already eleven
 *  columns wide and two paragraphs of prose in it would push the returns off
 *  screen on his laptop. */
export function dayTagChipLabel(t: HsDayTag): string {
  return `📰 ${t.symbol}`;
}

/** The tooltip. Deliberately leads with what this is NOT. */
export function dayTagTitle(t: HsDayTag): string {
  return (
    `${t.symbol}${t.company ? ` — ${t.company}` : ''} · ${t.date}\n` +
    `${t.headline_count || 0} headline${t.headline_count === 1 ? '' : 's'} read` +
    `${t.read_by ? ` by ${t.read_by}` : ''}\n` +
    (t.why_positive ? `Why it reads positive: ${t.why_positive}\n` : '') +
    `\nA bull case AND a bear case, written from those headlines and the ` +
    `numbers already on this board. NOT measured, not a signal, not advice. ` +
    `Click to read both.`
  );
}

function DayTagRow({ tag, span }: { tag: HsDayTag; span: number }) {
  const when = tag.trigger?.published
    ? new Date(tag.trigger.published * 1000).toLocaleString()
    : null;
  return (
    <tr className="hs-daytag">
      <td colSpan={span}>
        <div className="hs-daytag__head">
          <strong>{tag.symbol}</strong>
          {tag.company ? <span className="hs-daytag__co">{tag.company}</span> : null}
          <span className={'hs-daytag__read' + (tag.positive ? ' is-pos' : '')}>
            {tag.positive ? 'reads positive' : 'reads neutral / mixed'}
          </span>
          <span className="hs-daytag__meta">
            {tag.date}
            {tag.headline_count ? ` · ${tag.headline_count} headlines` : ''}
            {tag.read_by ? ` · read by ${tag.read_by}` : ''}
          </span>
        </div>

        {tag.trigger?.title ? (
          <div className="hs-daytag__trigger">
            {tag.trigger.url
              ? <a href={tag.trigger.url} target="_blank" rel="noreferrer">{tag.trigger.title}</a>
              : tag.trigger.title}
            <span className="hs-daytag__src">
              {tag.trigger.source || ''}{when ? ` · ${when}` : ''}
            </span>
          </div>
        ) : null}

        {/* What else it read. Folded into a <details> because six headlines
            above two paragraphs would bury the argument — but present, because
            "grounded in the headlines" is only a claim if you can't see them. */}
        {(tag.headlines || []).length > 1 ? (
          <details className="hs-daytag__reads">
            <summary>{tag.headlines!.length} headlines read</summary>
            <ul>
              {tag.headlines!.map((h, i) => (
                <li key={h.url || h.title || i}>
                  {h.url
                    ? <a href={h.url} target="_blank" rel="noreferrer">{h.title}</a>
                    : h.title}
                  {h.source ? <span className="hs-daytag__src">{h.source}</span> : null}
                </li>
              ))}
            </ul>
          </details>
        ) : null}

        <div className="hs-daytag__cases">
          <div className="hs-daytag__case hs-daytag__case--bull">
            <span className="hs-daytag__caselbl">Bull case</span>
            <p>{tag.bull}</p>
          </div>
          <div className="hs-daytag__case hs-daytag__case--bear">
            <span className="hs-daytag__caselbl">Bear case</span>
            <p>{tag.bear}</p>
          </div>
        </div>

        {/* Both sides are always shown, which is the whole reason this is a
            briefing and not a recommendation. The line below is not boilerplate:
            this board has no measured edge, and a paragraph of fluent prose is
            exactly the kind of thing that starts reading like one. */}
        <div className="hs-daytag__foot">
          Written from the headlines above and the numbers already on this row.
          Nothing here is measured, no edge is claimed, and this gates no alert
          and enters no lane.
        </div>
      </td>
    </tr>
  );
}

function LegCells({ r, d1, isGroup }: {
  r: HsDayLeg & HsPreGroup & { rel_5d?: number | null; rel_21d?: number | null;
                               n_full?: number };
  d1?: Pick<HsPayload, 'd1' | 'as_of' | 'benchmark' | 'pre'> | null; isGroup?: boolean;
}) {
  const day = dayCell(r, d1, !!isGroup);
  const pre = preCell(r, d1, !!isGroup);
  return (
    <>
      {/* ☀️ Pre-mkt sits BEFORE the day cell — the legs already read
          newest-first, and the pre-market print is older than nothing and
          newer than today's open. Drawn only when the server says to. */}
      {showPreCol(d1) ? (
        <td className={`mono hs-num ${tone(r.pre_1d)}${pre.thin ? ' hs-pre-thin' : ''}`}
            title={pre.title}>
          {pct(r.pre_1d)}
          {isGroup && r.pre_n != null
            ? <span className="hs-pre-n"> · {r.pre_n}/{r.n_full}</span> : null}
        </td>
      ) : null}
      <td className={`mono hs-num ${tone(r.rel_1d)}${day.marked ? ' hs-d1-close' : ''}`}
          title={day.title || undefined}>
        {day.text}
        {/* Never silent: a close value standing in a live column says so on
            the row, not only in a tooltip. */}
        {day.marked ? <span className="hs-d1-mark"> last close</span> : null}
        {/* A live group median over only SOME of the row's members prints its
            denominator, exactly as the Pre-mkt column does. Silent when every
            member printed, which is the normal case in session — a count
            beside all 29 roster rows every minute is noise, a count beside the
            one row where half the names are dark is the whole point. */}
        {isGroup && day.partial
          ? <span className="hs-pre-n"> · {r.d1_live_n}/{r.d1_live_of}</span> : null}
      </td>
      {(['rel_5d', 'rel_21d'] as const).map((k) => (
        <td key={k} className={`mono hs-num ${tone(r[k])}`}>{pct(r[k])}</td>
      ))}
    </>
  );
}

/** The four fundamental cells + the trend + Next ER, for a GROUP row (sector
 *  or industry). Medians of the full membership — the row's own read on the
 *  column it may be sorted by. */
function GroupFundCells({ r }: { r: HsFundMedians }) {
  const t = r.fund_basis || 'median of full membership';
  return (
    <>
      <td className={`mono hs-num hs-med ${tone(r.sales_yoy)}`} title={t}>{pct(r.sales_yoy)}</td>
      <td className="hs-tier hs-med" title={t}>{tierChip(r.sales_tier)} {r.sales_tier || '—'}</td>
      <td className={`mono hs-num hs-med ${tone(r.q_eps_yoy)}`} title={t}>{pct(r.q_eps_yoy, 0)}</td>
      <td className={`mono hs-num hs-med ${tone(r.net_margin)}`} title={t}>{pct(r.net_margin)}</td>
      <td className="mono hs-num hs-med" title={t}>
        {typeof r.eq_score === 'number' ? r.eq_score.toFixed(0) : '—'}
      </td>
      <td className="hs-spacer" />
    </>
  );
}

/** 🌀 The AMD cell on a GROUP row — an em-dash with the served reason, always.
 *  A cycle phase has no median, and a count over the 25 names the payload
 *  carries would describe a different population from the medians beside it
 *  (those are the full membership). The counts live under the table. */
function AmdGroupCell({ s }: { s?: HsAmdSummary | null }) {
  if (!showAmdCol({ amd_summary: s })) return null;
  const cell = amdGroupCell(s);
  return (
    <td className={`hs-amd ${amdToneClass(cell.tone)}`} title={cell.title}>{cell.text}</td>
  );
}

function NameRow({ r, read, study, bandStudy, d1 }: {
  r: HsName; read?: BounceRoomRow | null; study?: ExplosiveStudy | null;
  bandStudy?: BandStructureStudy | null;
  d1?: Pick<HsPayload, 'd1' | 'as_of' | 'benchmark' | 'pre' | 'amd_summary'> | null;
}) {
  const nav = useNavigate();
  const loc = useLocation();

  /* Ajay 2026-09-19: "can you give me control click in this page for the
   * stocks so I can open new tab on the stock."
   *
   * The ticker itself was already a real <a href>, so Cmd-click worked ON THE
   * TICKER — but measured against the rendered row, that was the ONLY live
   * target: the company name was a plain <div> and all seven number cells had
   * no link at all. He was Cmd-clicking the row and hitting dead pixels.
   *
   * MODIFIER AND MIDDLE CLICK ONLY. A plain click on the row deliberately
   * still does nothing: this table is sorted, scanned and read across, and
   * making the whole row navigate would fire every time he reached for a
   * number or dragged to select one. He asked for the new tab, not for a
   * new way to leave the page by accident.
   *
   * Anything already interactive is left alone — the ticker link, the ★, the
   * + Signals button, the chips all keep their own behaviour, and the row
   * never steals a click that landed on one of them. */
  const openInNewTab = (e: ReactMouseEvent<HTMLTableRowElement>) => {
    if (!(e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1)) return;
    if ((e.target as HTMLElement).closest?.('a,button,input,label,select,textarea')) return;
    e.preventDefault();
    // TickerLink's helper types its event as React's MouseEvent, so the
    // synthetic event passes straight through — no cast, no DOM/React mixup.
    openTickerWithModifier(e, nav, loc, r.symbol, 'Hottest sectors');
  };

  const pm = periodMark(r.period_ok);
  /* 🌀 The served AMD state. Colourless on purpose — the tone that rides in
     the payload is the 🌀 AMD tab's, and the served refusal sentence is on the
     hover. Drawn only when the server served the block. */
  const amd = showAmdCol(d1) ? amdCell(r.amd, d1?.amd_summary) : null;

  return (
    <tr className="hs-name"
        onClick={openInNewTab}
        onAuxClick={openInNewTab}
        title={`\u2318/Ctrl-click (or middle-click) anywhere on this row to open ${r.symbol} in a new tab`}>
      <td className="hs-sym">
        <TickerLink ticker={r.symbol} fromLabel="Hottest sectors" />
        {/* 🚀 also on the Explosive Growth board (Ajay 2026-09-11:
            "ALL TABS IN CHART MAPS"). */}
        <GrowthChip symbol={r.symbol} className="hs-badge" />
        {/* 🎪 the promo-circuit origin label travels with the name on every
            board that shows a 🚀 chip (Ajay 2026-09-21: "add them to our
            list as they come through"). Renders nothing for the common case. */}
        <PromoOriginChip symbol={r.symbol} className="hs-badge" />
        <ExplosiveChip read={read?.explosive} study={study} className="hs-badge" />
        <EnterableChip read={read?.enterable} className="hs-badge" />
        {/* 🪜 Ajay 2026-09-16 "in all chartmaps tabs" — the row's own served
            ceiling/floor read. */}
        <BandStructureChip read={read?.band_structure} study={bandStudy} className="hs-badge" />
        {/* Ajay 2026-09-11: "add to signals button in that table I wanna pick a
            few stocks from this". NOT compact — compact prints a bare "+" which
            sits next to TickerLink's ☆ and reads as decoration rather than a
            control. The word is what makes it a button. */}
        <SignalWatchButton symbol={r.symbol} />
        {/* The company name is the widest thing in this cell and was plain
            text. As a link it gives a real Cmd-click target without the row
            handler having to fire, and it matches how the ticker behaves. */}
        <div className="hs-coname">
          {r.name
            ? <TickerLink ticker={r.symbol} fromLabel="Hottest sectors"
                          showWatchlist={false}>{r.name}</TickerLink>
            : ''}
        </div>
      </td>
      {/* 🌀 Immediately after the name, because it is a state ABOUT the name
          and the cell above already carries this row's other state chips.
          Shipped last on 2026-09-22 and clipped off the right edge the same
          morning — see visibleCols. The header map and this literal are the
          two halves of one column; they move together or the board reads a
          column off. */}
      {amd ? (
        <td className={`hs-amd ${amdToneClass(amd.tone)}`} title={amd.title}>{amd.text}</td>
      ) : null}
      <LegCells r={r} d1={d1} />
      <td className={`mono hs-num ${tone(r.sales_yoy)}`} title={
        r.sales_prior_yoy != null ? `prior quarter ${pct(r.sales_prior_yoy)}` : undefined}>
        {pct(r.sales_yoy)}{r.sales_accelerating ? ' ⚡' : ''}
      </td>
      <td className="hs-tier" title={r.sales_tier || 'no filed quarterly series from our provider'}>
        {tierChip(r.sales_tier)} {r.sales_tier || '—'}
        {/* The pair mark rides the tier it qualifies — same three states and
            same words as 📈 Bonde (periodMark owns both). `false` = checked
            and not four quarters apart; `null` = no period keys to check it
            with. A tick is never printed for a row that checked out, and the
            mark rides the em-dash too when the tier itself was withheld. */}
        {pm && (
          <span className={pm.cls} data-testid={`hs-pair-${r.symbol}`}
                title={pm.title}>{pm.text}</span>
        )}
      </td>
      <td className={`mono hs-num ${tone(r.q_eps_yoy)}`}>{pct(r.q_eps_yoy, 0)}</td>
      <td className={`mono hs-num ${tone(r.net_margin)}`}>
        {pct(r.net_margin)}{r.margin_expanding ? ' ↑' : ''}
      </td>
      <td className="mono hs-num" title={r.eq_tier || undefined}>
        {typeof r.eq_score === 'number' ? r.eq_score.toFixed(0) : '—'}
        {r.code_33 ? ' 🎯' : ''}{r.inventory_flag ? ' ⚠️' : ''}
      </td>
      <td className="hs-er">
        {r.next_earnings || '—'}{r.earnings_when ? ` ${r.earnings_when}` : ''}
      </td>
    </tr>
  );
}

export function HottestSectors() {
  const [data, setData] = useState<HsPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sort, setSort] = useState<string>('rel_5d');
  const [dir, setDir] = useState<HsDir>('desc');
  /* ⊞ One blanket answer + the carets he moved by hand. `all` starts from the
   * remembered choice on this browser (absent = closed, the shipped default). */
  const [open, setOpen] = useState<HsOpen>(() => ({ all: readExpandAllPref(), ov: {} }));
  const [byIndustry, setByIndustry] = useState(true);
  /* ☀️ Which basis the next read asks for, and a tick that makes a SECOND
   * click re-fetch: after the first ☀️ click `basis`, `sort` and `dir` are
   * already at their target values, so without the tick the deps would not
   * change and the button would go dead. */
  const [basis, setBasis] = useState<'close' | 'premarket'>('close');
  const [scanTick, setScanTick] = useState(0);

  /* ↻ Re-scan (2026-09-18). Three things this `load` has to get right that the
   * old one did not:
   *  1. LATEST WINS. A sort change fired while a re-scan is in flight must
   *     still go out, and the late first response must be discarded — or the
   *     header reads "ranked on X" over rows that came back ranked on Y.
   *  2. A FAILURE KEEPS THE BOARD. `.catch` no longer drops `data`, and a 200
   *     that came back with no rows is reported without replacing a good board.
   *  3. The in-flight guard stops the BUTTON only (two clicks in one React
   *     tick would both fire before `disabled` re-rendered), never the effect. */
  const seq = useRef(0);
  const inFlight = useRef(false);
  const dataRef = useRef<HsPayload | null>(null);

  const load = useCallback(() => {
    const id = ++seq.current;
    inFlight.current = true;
    setLoading(true);
    fetch(`${API}/rotation/hottest?sort=${encodeURIComponent(sort)}&dir=${dir}`
          + (basis === 'premarket' ? '&basis=premarket' : ''),
          { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j: HsPayload) => {
        if (id !== seq.current) return;                  // a newer sort won
        if (!hasRows(j) && hasRows(dataRef.current)) {
          setErr(j?.reason || 'the re-scan came back with no rows');
          return;                                        // keep the good board
        }
        dataRef.current = j; setData(j); setErr(null);
      })
      .catch((e) => { if (id === seq.current) setErr(String(e?.message ?? e)); })
      .finally(() => {
        if (id === seq.current) { inFlight.current = false; setLoading(false); }
      });
  }, [sort, dir, basis, scanTick]);
  useEffect(() => { load(); }, [load]);
  const onRescan = () => { if (inFlight.current) return; load(); };
  /* ☀️ One click = one read on the pre-market basis, ranked on the new column.
   * `sort` is a `load` dep, so setting all three here is still ONE fetch. */
  const onPremarket = () => {
    if (inFlight.current) return;
    setBasis('premarket');
    setSort(PRE_COL.key);
    setDir('desc');
    setScanTick((t) => t + 1);
  };

  const sectors = useMemo(() => data?.sectors || [], [data]);
  const themes = useMemo(() => data?.themes || [], [data]);
  const toggle = (k: string) => setOpen((o) => toggleKey(o, k, byIndustry));
  /* 🧨 ONE bounce-room POST for every name row this table can show (sector,
   * industry and roster groups alike) — the chip and the opt-in ordering read
   * that single map; a per-row fetch on a table this wide is out of the
   * question. */
  const rowSymbols = useMemo(() => {
    const out: string[] = [];
    const eat = (g: { names?: HsName[] }[]) => {
      for (const grp of g || []) for (const n of grp.names || []) if (n.symbol) out.push(n.symbol);
    };
    eat(sectors as { names?: HsName[] }[]);
    eat(themes as { names?: HsName[] }[]);
    for (const s2 of (sectors || []) as { industries?: { names?: HsName[] }[] }[]) {
      eat((s2.industries || []) as { names?: HsName[] }[]);
    }
    return out;
  }, [sectors, themes]);
  const room = useBounceRoom(rowSymbols);
  const readOf = (sym: string) => room.map.get(String(sym).toUpperCase());
  /* 🎯 The enterable cut (2026-09-15) is CLIENT-SIDE over the names this
   * payload carries, and the count line says exactly that: this payload is a
   * SERVER-CUT list — `names_per_group` rows per group, ranked on the server —
   * so hiding four of a group's 25 does not pull the 26th up. A server-side
   * enterable cut is HIS CALL (spec §7.9).
   *
   * WHAT THE NUMBER COUNTS (m4, 2026-09-15): the UNIQUE names in the payload,
   * across every group — themes, sectors and industries — including the groups
   * he has collapsed. Every group on this board starts collapsed, so a line
   * scoped to "rows on screen" would read "0 hidden" on arrival while the cut
   * was already live inside each group; and a name that sits in both its sector
   * and its industry is one name, counted once. The note below is worded to
   * match, because a count line that describes a different set than the one it
   * counted is the same lie as hiding rows quietly. */
  const { enterableOnly, kind, setEnterableOnly, ignoreReasons, toggleReason } = useEnterableFilter();
  const uniqueSymbols = useMemo(
    () => Array.from(new Set(rowSymbols.map((x) => String(x).toUpperCase()))), [rowSymbols]);
  const part = useEnterablePartition(uniqueSymbols, (x) => x, room.map, enterableOnly);
  const enterableCut = enterableOnly && kind !== 'n/a';
  // A plain closure, re-created every render, so it reads the CURRENT ignore
  // set with no dep array — but the set must be passed explicitly, or a name
  // un-hidden in the count line stays missing from its group.
  const showName = (sym: string) => !enterableCut
    || isShown(readOf(sym)?.enterable, 'enterable', ignoreReasons);
  /* NO 🧨 ordering toggle on this board, deliberately. Every other tab gets
   * one; here the payload keeps only `names_per_group` rows per group and the
   * column sorts are a SERVER round-trip for exactly that reason — a
   * browser-side reorder would rank the visible 25 and never reach the 305th
   * Technology name. Ranking these rows by the explosive read has to happen
   * where the truncation happens — i.e. a new `explosive` key in the backend's
   * `/rotation/hottest?sort=` set, which is HIS CALL (a tenth column-sort on a
   * board he already called wide), not a silent browser reorder. The chip
   * still rides on every name, and the omission is pinned by the explosive
   * contract's NO_TOGGLE list in frontend/scripts/contracts.mjs. */
  /** Click a new column → sort it DESC (the interesting end of every column
   *  except Next ER). Click the active column again → flip direction. */
  const clickSort = (k: string) => {
    if (k === sort) setDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    else { setSort(k); setDir(k === 'next_earnings' ? 'asc' : 'desc'); }
  };

  /* A COLD failure still shows the failure. What changed on 2026-09-18 is that
   * a failure arriving on top of a board that already rendered no longer blanks
   * it: the previous read stays on screen and the meta line says what failed. */
  if (err && !hasRows(data)) {
    return <div className="cm-note cm-note-warn">Hottest sectors unavailable: {err}</div>;
  }
  if (!data && loading) return <div className="cm-note">Reading the rotation table…</div>;
  if (data?.reason && !hasRows(data)) {
    return <div className="cm-note cm-note-warn">{data.reason}</div>;
  }

  const rescanBlocked = rescanBlockedReason(data);
  const rescanQuiet = rescanQuietReason(data);
  const preState = premarketState(data);
  const cols = visibleCols(data);
  const span = colSpanOf(data);
  /* ⊞ What one click opens in THIS view, and how many rows that really is. */
  const expandKeys = openedKeys(data, byIndustry);
  const allOpen = allGroupsOpen(open, expandKeys, byIndustry);
  const expandRows = expandRowCount(data, byIndustry);
  /* 🌀 The served line under the table: coverage + staleness, or — when the
     nightly sweep could not be read — the served sentence saying the column is
     missing rather than silently dropping it. */
  const amdNote = amdCoverageNote(data?.amd_summary);
  /* The header mark follows the SERVED order when the server demoted a
   * pre_1d request — the intent stays in `sort` for the next read. */
  const shownSort = shownSortKey(sort, data);

  return (
    <div className="hs">
      <div className="hs-controls">
        {/* The three leg chips used to live here. They set the same backend
            `sort` the column headers now do, and two controls for one piece of
            state is how a board starts lying about its own order. The header
            arrow IS the state. */}
        <div className="hs-sorts">
          <span className="hs-sorted-by">
            ranked on <b>{colLabel(shownSort, data)}</b>
            {dir === 'desc' ? ' ▼ high → low' : ' ▲ low → high'}
            <span className="hs-dim"> · click any column header</span>
          </span>
        </div>
        <label className="hs-toggle">
          <input type="checkbox" checked={byIndustry}
                 onChange={(e) => setByIndustry(e.target.checked)} />
          Break into industries
        </label>
        {/* ⊞ Expand all (Ajay 2026-09-22: "give me toggle option to open them
            app on one click in stead of clicking on the carets"). It sits
            beside "Break into industries" and NOT beside ↻ / ☀️ because both
            of these change what the table SHOWS; the other two go and fetch.
            Yes, that is six controls on one row — in the default view this
            removes ~150 caret clicks a visit, not 28. */}
        <button type="button" className="cm-rescan" data-testid="hs-expand-all"
                title={EXPAND_ALL_TITLE(expandRows, allOpen, byIndustry)}
                onClick={() => {
                  const next = !allOpen;
                  setOpen(setAll(next));
                  writeExpandAllPref(next);
                }}>
          {allOpen ? '⊟ Collapse all' : '⊞ Expand all'}
        </button>
        {/* ↻ Re-scan (Ajay 2026-09-18: "can you give me rebuild or rescan
            button in hot sectors"). Same class, label and disabled shape as the
            Chart Maps re-scan, so the two read as one control. Since
            2026-09-23 it DOES move the sector ranking: the group rows ride the
            same live read as the names. */}
        <button type="button" className="cm-rescan" data-testid="hottest-rescan"
                disabled={loading || rescanBlocked !== null}
                title={rescanBlocked
                  ? `Re-scan is off because ${rescanBlocked}. Every column here is already`
                    + ' the last finished session.'
                  : (rescanQuiet ? `${rescanQuiet}. ${RESCAN_COST_SENTENCE} ` : '')
                    + "Re-reads today's live price for every name on this board and re-ranks it "
                    + '— including the sector, industry and roster rows, which are medians over'
                    + ' their own members trading now. 5 days, 21 days and Sales YoY stay on the'
                    + ' last close.'}
                onClick={onRescan}>
          {loading ? 'Scanning…' : '↻ Re-scan'}
        </button>
        {/* ☀️ Pre-market scan (Ajay 2026-09-21: "In the hot sector table can I
            get a pre market scan please"). He reads these boards at 7-8 am ET.
            Gated ONLY by the served `pre.open` — the backend's clock, never
            this browser's. */}
        <button type="button" className="cm-rescan" data-testid="hs-premarket"
                disabled={loading || !preState.enabled}
                title={preState.title}
                onClick={onPremarket}>
          {loading && basis === 'premarket' ? 'Scanning…' : '☀️ Pre-market scan'}
        </button>
        <InfoButton inline title="🔥 Hottest — how to read this">
          <p>Every sector ranked on <b>{colLabel(shownSort, data)}</b>
            against <b>{benchSymbol(data)}</b>,
            the equal-weight benchmark — so a name is measured against the average stock, not the
            mega-caps. Open a sector for its industries, then its names.</p>
          <p><b>What &ldquo;Today&rdquo; means here.</b> While the market is open, the day column is
            this session so far, measured against <b>{benchSymbol(data)}</b> exactly like the other
            legs — on a NAME row that is the name&rsquo;s own move, and on a sector, industry or
            roster row it is the median over the members of that row <i>trading now</i>. So the
            rotation you are ranking on is the one happening this minute, not the one that finished
            last night. 5 days, 21 days and Sales YoY still come from the last close, because the
            rotation snapshot is built after the bell. Two things a live group row is careful about:
            it is never half live and half last-close — a member with no live print is left out of
            the median rather than counted at yesterday&rsquo;s move — and when it went live on
            fewer members than it has, the cell prints that count beside the number. When the tape
            is shut, or no live price comes back, the column header itself changes to the session it
            is showing, and any row that missed the live read is marked <i>last close</i> where you
            can see it.</p>
          <p><b>The ↻ Re-scan button.</b> It re-reads today&rsquo;s live price for every name on
            this board and re-ranks the table on it &mdash; the group rows included, because they
            are medians over the same live prints. What it can <i>not</i> do is move 5 days, 21 days
            or Sales YoY: those are the snapshot&rsquo;s, and the snapshot is built after the bell.
            The line above the table always says which basis you are looking at. When the tape is
            shut the button is off and says why, in the market calendar&rsquo;s own words; outside
            {' '}{data?.d1?.session_window || '9:30–16:00 ET'} it still works but warns you the day
            column will not move. {RESCAN_COST_SENTENCE} It is not free, and it is not new — the
            board already re-fetches the chip read about once a minute while it is open.</p>
          <p><b>The ☀️ Pre-market scan button.</b> Live between {data?.pre?.pre_window
            || '4:00-9:30 ET'} on a trading day, it reads every name&rsquo;s own
            pre-market print in ONE snapshot for the whole board — the same provider read
            the ↻ button costs — and adds a <b>Pre-mkt</b> column. The yardstick is
            {' '}<b>{benchSymbol(data)}</b>&rsquo;s own pre-market print, and its TIME is
            printed in the line above, because an ETF prints far less often than a name:
            on 2026-09-21 at 07:27 the benchmark&rsquo;s last print was hours older than
            NVDA&rsquo;s. Until the benchmark itself has printed, nothing relative is
            shown at all and the board ranks on 5 days instead — the line says so rather
            than showing a raw move under a relative header. Sector, industry and roster
            rows become the <b>median of the members that printed</b>, with that count
            beside it (12/40) and flagged thin under the board&rsquo;s own thin rule: at
            7 am most names have not printed, and that is the truth, not a fault. The
            column disappears once the day column goes live after the open, and the Today
            column is never touched by any of it. <b>Nothing here is measured</b> — no
            study of pre-market moves exists on this app. It is a read of the tape before
            the bell, not a signal, and it pushes nothing.</p>
          <p><b>All eleven sectors are listed, not just the hot ones.</b> A strong name often sits in
            a cold sector: ANDE is 2nd of Consumer Defensive&rsquo;s 76 over 21 days while the sector
            is 8th of 11. Listing only the hot end would hide exactly the names this board is for.</p>
          <p><b>Two populations.</b> Sector and industry heat is the rotation grid&rsquo;s sampled
            median — the same number the Hot-sectors strip prints, reused so the two can never
            disagree. Name rows are the <b>full</b> membership. Industries too small for a ranked row
            still show, flagged <i>thin</i>: a 6-name median is not a 25-name one.</p>
          <p><b>Every ranked column sorts, and it sorts on the server.</b> Click a header to rank
            on it; click it again to flip the direction. The board keeps 25 names per group, so a
            browser-side sort would only reorder those 25 — the round-trip re-ranks the FULL
            membership and then takes the top 25 of the column you picked. A blank always sorts
            LAST, in both directions. Sector and industry rows show the <b>median of their full
            membership</b> in the fundamental columns, so a sort there has something visible behind
            it; the three return legs stay the rotation grid&rsquo;s sampled median.
            {/* The 🌀 column is the one exception, and the refusal is SERVED —
                retyping it here is how a surface and its backend start saying
                two different things. */}
            {/* Gated on whether the column is DRAWN, not on whether the
                refusal sentence happens to be in the payload: an unavailable
                sweep still serves `no_sort_reason`, and describing a column
                the board is not drawing is its own small lie. */}
            {showAmdCol(data) && data?.amd_summary?.no_sort_reason
              ? <> <b>🌀 AMD is the exception.</b> {data.amd_summary.no_sort_reason}</>
              : null}</p>
          <p><b>Our rosters sit above the sectors.</b> Robotics, the AI complex, nuclear,
            quantum, rare earth, crypto — these are lists we curated, and they cut ACROSS the
            provider&rsquo;s sectors (robotics spans Technology, Industrials and Consumer
            Cyclical), so they have no industry layer. They <i>ride alongside</i> and never
            overrule: on 2026-09-09 our <code>ai_semis</code> roster read −0.28 over 21 days while
            the provider&rsquo;s <code>Semiconductors</code> cohort read −1.95 — opposite signs on
            the same question. &ldquo;How are semis doing&rdquo; is a question about all semis, so
            the objective label answers it. A roster too small for a ranked row still shows,
            flagged <i>thin</i>.</p>
          <p><b>Names are ranked by return, not by traction.</b> Traction measures acceleration, and it
            ranks ANDE 23rd of 76 while the 5-day ranks it 3rd.</p>
          {/* Every measured figure in this paragraph is SERVED — retyping
              −4.2pp here is how a surface and its study start disagreeing. */}
          {data?.amd_summary?.honesty ? (
            <p><b>The 🌀 AMD column.</b> {data.amd_summary.honesty}
              {data.amd_summary.no_colour_reason
                ? <> {data.amd_summary.no_colour_reason}</> : null}
              {data.amd_summary.group_note ? <> {data.amd_summary.group_note}</> : null}
            </p>
          ) : null}
          {/* ⊞ Expand all — what the one click opens, and why the depth
              depends on the checkbox above it. */}
          <p><b>The ⊞ Expand all button.</b> One click opens every roster and every
            sector — and, while <i>Break into industries</i> is on, every industry
            under them, because in that view the names hang off the industry caret
            and not the sector&rsquo;s. Its hover says how many rows that is for the
            board in front of you. A caret you close by hand afterwards stays closed,
            the 📰 news briefings are never opened by it, and your choice is
            remembered on this browser.</p>
          <p><b>This is a discovery list, not a signal.</b> It is trailing returns — nothing here is
            backtested and none of it is a buy signal. Sales, EPS and margin come from the weekly
            research cache, so they can be up to a week behind a fresh print. A blank prints as
            &mdash;, never as a zero.</p>
        </InfoButton>
      </div>

      <div className="hs-meta">
        {/* Which columns are today's and which are the snapshot's, in words
            (2026-09-16). He read a last-close number as the live tape because
            this line only ever said "as of". */}
        <span className={data?.d1?.live || data?.pre?.live ? 'hs-live' : 'hs-stale'}>
          {asOfLine(data)}
        </span>
        {err && hasRows(data) ? (
          <span className="hs-stale" data-testid="hottest-rescan-failed">
            {' '}· re-scan failed ({err}) — this is the previous read, not a new one
          </span>
        ) : null}
        {data?.coverage?.pct != null ? (
          <span> · sales on {data.coverage.pct}% of {data.coverage.priced} priced names</span>
        ) : null}
        {data?.stale ? <span className="hs-stale"> · build is stale</span> : null}
      </div>

      {enterableCut ? (
        <HiddenCount hidden={part.hidden} unread={part.unread}
                     hiddenByReason={part.hiddenByReason} enabled kind={kind}
                     reasons={part.reasons} unhidden={part.unhidden}
                     onToggleReason={toggleReason} unhideCount={ignoreReasons.size}
                     note="Counted across every group in this payload — themes, sectors and industries, the collapsed ones included — one count per unique name. This board is a server-cut list: the payload keeps only the top names per group, so this is what the cut removed from the names it carries, never from the full membership."
                     onShowAll={() => setEnterableOnly(false)} />
      ) : null}
      {/* 🪜 No row on this list came back with a band read — say so once, the
          way the 🎯 n/a tabs do, instead of showing no chip anywhere and
          letting it read as a board where the read silently stopped. The
          sentence is SERVED (bounce_room.BAND_STRUCTURE_NO_READ); this board
          is a server-cut list, so it describes the names it carries. */}
      {room.payload?.band_structure_coverage?.note ? (
        <div className="cm-hidden-count" data-testid="band-structure-note">
          🪜 {room.payload.band_structure_coverage.note}
        </div>
      ) : null}
      {/* 🌀 The AMD read's own line — the histogram, the coverage, the sweep's
          date and the staleness verdict, in ONE sentence the backend built
          from the counts on THIS request. A count belongs here, not on a group
          row whose other cells are full-membership medians. When the sweep
          document could not be read, this is the served line that says the
          column is missing rather than dropping it in silence. */}
      {amdNote ? (
        <div className="cm-hidden-count" data-testid="hs-amd-note">{amdNote}</div>
      ) : null}

      <div className="hs-scroll">
        <table className="hs-table">
          <thead>
            <tr>
              <th className="hs-sym">Sector / Name</th>
              {cols.map((c) => {
                /* A column that does not sort gets a plain header, not a
                   dead button: the caption above says "click any column
                   header", and a header that looks like the others and
                   does nothing is worse than one that never offered.
                   (No ordinal here on purpose — the count and the order of
                   these columns both change, the argument does not.) */
                if (c.sortable === false) {
                  return (
                    <th key={c.key} className={c.num ? 'hs-num' : ''}>
                      <span className="hs-head"
                            title={c.key === AMD_COL.key
                              ? amdHeadTitle(data?.amd_summary) : (c.title || '')}>
                        {colLabel(c.key, data)}
                      </span>
                    </th>
                  );
                }
                const on = shownSort === c.key;
                return (
                  <th key={c.key} className={`${c.num ? 'hs-num' : ''}${on ? ' is-sorted' : ''}`}
                      aria-sort={on ? (dir === 'desc' ? 'descending' : 'ascending') : 'none'}>
                    <button type="button" className="hs-sort" onClick={() => clickSort(c.key)}
                            title={colTitle(c, data)}>
                      {colLabel(c.key, data)}{arrow(on, dir)}
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {/* THEMES FIRST (Ajay 2026-09-12: "Where is Robitics and crypto
                here?"). They were tracked all along — the Hot-sectors strip has
                ranked them as chips for days — but this board only ever read
                the sector and industry grains, so a roster he asked for by name
                was invisible on the one surface built to answer "what is hot".
                Above the sectors because they are the rosters he curated; the
                provider's eleven follow underneath, unchanged. */}
            {themes.length ? (
              <tr className="hs-grain"><td colSpan={span}>
                our rosters · cut across the sectors below
              </td></tr>
            ) : null}
            {themes.map((t) => {
              const k = `t:${t.group}`;
              const isOpen = isGroupOpen(open, k, byIndustry);
              return (
                <>
                  <tr key={k} className={`hs-sector hs-theme${isOpen ? ' is-open' : ''}`}>
                    <td className="hs-sym">
                      <button type="button" className="hs-disc" aria-expanded={isOpen}
                              onClick={() => toggle(k)}>
                        {isOpen ? '▾' : '▸'} {THEME_LABELS[t.group] || t.group}
                      </button>
                      <span className="hs-n" title={
                        t.thin
                          ? `${t.n_full} names — too few for a ranked row of its own, so this median is thinner than a sector's. Kept because you asked for these rosters by name.`
                          : `${t.n_full} names · ${t.basis}`}>
                        {t.n_full}{t.thin ? ' · thin' : ''}
                      </span>
                    </td>
                    {/* 🌀 second, beside the name — see visibleCols. The
                        group row is the sneaky half of the move: its Next ER
                        stand-in is an empty <td className="hs-spacer">, so a
                        row left in the old order still has the right CELL
                        COUNT and no colSpan check would catch it. */}
                    <AmdGroupCell s={data?.amd_summary} />
                    <LegCells r={t} d1={data} isGroup />
                    <GroupFundCells r={t} />
                  </tr>
                  {isOpen ? t.names.filter((r) => showName(r.symbol)).map((r) => <NameRow key={`${k}|${r.symbol}`} r={r} read={readOf(r.symbol)} study={room.payload?.explosive_study} bandStudy={room.payload?.band_structure_study} d1={data} />) : null}
                  {isOpen && t.names_total > t.names.length ? (
                    <tr key={`${k}|more`}><td colSpan={span} className="hs-more">
                      showing {t.names.length} of {t.names_total}
                    </td></tr>
                  ) : null}
                </>
              );
            })}
            {themes.length ? (
              <tr className="hs-grain"><td colSpan={span}>
                the provider&rsquo;s sectors
              </td></tr>
            ) : null}
            {sectors.map((s) => {
              const k = `s:${s.group}`;
              const isOpen = isGroupOpen(open, k, byIndustry);
              return (
                <>
                  <tr key={k} className={`hs-sector${isOpen ? ' is-open' : ''}`}>
                    <td className="hs-sym">
                      <button type="button" className="hs-disc" aria-expanded={isOpen}
                              onClick={() => toggle(k)}>
                        {isOpen ? '▾' : '▸'} {s.group}
                      </button>
                      {/* 📰 The day's two-sided news tag. Sits beside the name
                          and opens its own row — see DayTagRow. A sector with
                          no tag renders exactly as it always did. */}
                      {s.day_tag ? (
                        <button
                          type="button"
                          className={'hs-daytag__chip' + (s.day_tag.positive ? ' is-pos' : '')}
                          aria-expanded={isGroupOpen(open, `${k}|tag`, byIndustry)}
                          title={dayTagTitle(s.day_tag)}
                          onClick={(ev) => { ev.stopPropagation(); toggle(`${k}|tag`); }}
                        >
                          {dayTagChipLabel(s.day_tag)}
                        </button>
                      ) : null}
                      <span className="hs-n" title={
                        s.sampled_used && s.sampled_of && s.sampled_used < s.sampled_of
                          ? `heat measured on ${s.sampled_used} of ${s.sampled_of} names (the rotation grid's sample); the ${s.n_full} name rows below are the full membership`
                          : `${s.n_full} names`}>
                        {s.n_full}
                        {s.sampled_used && s.sampled_of && s.sampled_used < s.sampled_of
                          ? ` · heat on ${s.sampled_used}` : ''}
                      </span>
                    </td>
                    <AmdGroupCell s={data?.amd_summary} />
                    <LegCells r={s} d1={data} isGroup />
                    <GroupFundCells r={s} />
                  </tr>
                  {s.day_tag && isGroupOpen(open, `${k}|tag`, byIndustry)
                    ? <DayTagRow key={`${k}|tagrow`} tag={s.day_tag} span={span} />
                    : null}
                  {isOpen && byIndustry ? s.industries.map((ind) => {
                    const ik = `${k}|i:${ind.group}`;
                    const iOpen = isGroupOpen(open, ik, byIndustry);
                    return (
                      <>
                        <tr key={ik} className="hs-industry">
                          <td className="hs-sym">
                            <button type="button" className="hs-disc hs-disc--ind" aria-expanded={iOpen}
                                    onClick={() => toggle(ik)}>
                              {iOpen ? '▾' : '▸'} {ind.group}
                            </button>
                            <span className="hs-n" title={`${ind.n_full} names · ${ind.basis}`}>
                              {ind.n_full}{ind.thin ? ' · thin' : ''}
                            </span>
                          </td>
                          <AmdGroupCell s={data?.amd_summary} />
                          <LegCells r={ind} d1={data} isGroup />
                          <GroupFundCells r={ind} />
                        </tr>
                        {iOpen ? ind.names.filter((r) => showName(r.symbol)).map((r) => <NameRow key={`${ik}|${r.symbol}`} r={r} read={readOf(r.symbol)} study={room.payload?.explosive_study} bandStudy={room.payload?.band_structure_study} d1={data} />) : null}
                        {iOpen && ind.names_total > ind.names.length ? (
                          <tr key={`${ik}|more`}><td colSpan={span} className="hs-more">
                            showing {ind.names.length} of {ind.names_total}
                          </td></tr>
                        ) : null}
                      </>
                    );
                  }) : null}
                  {isOpen && !byIndustry ? s.names.filter((r) => showName(r.symbol)).map((r) => <NameRow key={`${k}|${r.symbol}`} r={r} read={readOf(r.symbol)} study={room.payload?.explosive_study} bandStudy={room.payload?.band_structure_study} d1={data} />) : null}
                  {isOpen && !byIndustry && s.names_total > s.names.length ? (
                    <tr key={`${k}|more`}><td colSpan={span} className="hs-more">
                      showing {s.names.length} of {s.names_total}
                    </td></tr>
                  ) : null}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
      {data?.note ? <p className="rw__note">{data.note}</p> : null}
    </div>
  );
}
