/* 🎢 High Beta — the payload types and the URL params (2026-10-14).
 *
 * Ajay 2026-10-14, verbatim: "Can you build me a category or filter for High
 * Beta stocks in Resilient and make a scan there were all down today
 * especially a qqq series. Can you please make sure you do a full scan." —
 * then "Can you create a new tab for High Beta stocks" — then "in the High
 * Beta tab.I wanna able to sort my most volatile stocks".
 *
 * The board is read, rated, counted and ordered on the server
 * (backend/chart_maps/high_beta_tab.py). Every sentence on the tab is SERVED;
 * the types below are the payload contract and nothing more. This module types
 * no threshold and no number: the β cuts, the down-today line, the sort
 * labels, the table's column heads and every cell's text ride in the payload,
 * so a changed constant on the server shows up with no frontend deploy.
 *
 * THE BOXES (🎢 β ≥ 1.5 · 🎢 β ≥ 2.0 · 🎢 Top 20% by β · QQQ · Nasdaq-100 ·
 * 📉 Down 5%+ today) live in the URL as `?hb=b15,b20,top20,qqq,d5` and ride
 * to the server on the high_beta tab only (high_beta_tab.FILTER_KEYS, pinned
 * equal by contract). ANY is the default; "must match all" writes
 * `?hb_mode=all` — the Dual Momentum parser, by import.
 *
 * GREEN NAMES (AMENDMENTS A1): the default list is the names RED today (his
 * ask: "all down today"); `?hb_all=1` asks the server for the up / flat names
 * too, listed after the red ones. Absent or anything else = red only.
 *
 * Display only. Not advice.
 */
import { DM_MODE_ALL, DM_MODE_ANY, parseDmMode } from './dmFilters';
import type { CmDmFilters, DmMode } from './dmFilters';
import type { HsQualityInfo } from '../components/HottestQualityInfo';

export const HB_FILTER_PARAM = 'hb';
export const HB_FILTER_KEYS = ['b15', 'b20', 'top20', 'qqq', 'd5'] as const;
export type HbFilterKey = typeof HB_FILTER_KEYS[number];
export const HB_MODE_PARAM = 'hb_mode';
/** "include green names" (A1). Written as `?hb_all=1`, removed when off. */
export const HB_ALL_PARAM = 'hb_all';
export const HB_ALL_ON = '1';

/** The tab-scoped served sort keys (high_beta_tab.SORT_SWING / SORT_DROP /
 *  SORT_VOL). The server RESOLVES `default` to β × today's drop (his K3 "you
 *  pick") and serves the resolved key as `high_beta_board.sort`. Labels are
 *  SERVED, never typed here. */
export const HB_SORT_SWING = 'hb_swing';
export const HB_SORT_DROP = 'hb_drop';
export const HB_SORT_VOL = 'hb_vol';

/* ── 2026-10-14 b — header sorts and the Price | Sales view ────────────────
 * Ajay 2026-10-14, verbatim: "Can you add sort function on the headers and
 * also 5 day and 21 days columns to show how they were reacting in price like
 * hot sectors and also add sales tab make it like hot sector with some
 * important metrics like EPS, QUAlity and other colums that show the strength
 * of the stock".
 *
 * Every column of both views sorts on a header tap (K4): its first tap opens
 * the column in its SERVED first direction (`table.columns[].first`), a tap on
 * the active column flips it. The order is the SERVER's
 * (high_beta_tab.order_rows) — the URL carries `sort` (the column's served
 * key) and `hb_dir` ONLY when the direction differs from that column's first,
 * so the default page sends neither. `hb_view` is FE-only URL state (the
 * table shows the same rows either way) and never rides to the server.
 * The four names below equal high_beta_tab.DIR_PARAM / DIRS /
 * TABLE_VIEW_PARAM / VIEW_PRICE / VIEW_SALES (pinned by a ?raw test). */
export const HB_DIR_PARAM = 'hb_dir';
export const HB_VIEW_PARAM = 'hb_view';
export const HB_VIEW_PRICE = 'price';
export const HB_VIEW_SALES = 'sales';
export type HbDir = 'asc' | 'desc';
export type HbView = typeof HB_VIEW_PRICE | typeof HB_VIEW_SALES;

/** `?hb_dir=` -> 'asc' | 'desc' (any case / spacing); anything else -> null
 *  (the server then opens the column in its own first direction). */
export function parseHbDir(v: string | null | undefined): HbDir | null {
  if (typeof v !== 'string') return null;
  const s = v.trim().toLowerCase();
  return s === 'asc' || s === 'desc' ? s : null;
}

/** `?hb_view=` -> 'sales' only for sales (any case / spacing); anything else
 *  -> 'price' (the default view). */
export function parseHbView(v: string | null | undefined): HbView {
  return typeof v === 'string' && v.trim().toLowerCase() === HB_VIEW_SALES ? HB_VIEW_SALES : HB_VIEW_PRICE;
}

/** What a tap on a column head asks for. A column with no served `sort` (or
 *  no readable served `first`) is not a sort head -> null. A column that is
 *  not the active sort -> its key in its first direction. The active column
 *  -> the flip of the served direction (`board.sort_dir`; unreadable = the
 *  column's first, the server's own resolution). `dir` is null whenever it
 *  equals the column's first, so the URL then carries no `hb_dir`. */
export function hbHeaderNext(
  col: { sort?: string | null; first?: string | null },
  board: { sort?: string | null; sort_dir?: string | null } | null,
): { sort: string; dir: HbDir | null } | null {
  const sort = typeof col?.sort === 'string' && col.sort ? col.sort : null;
  const first = parseHbDir(col?.first);
  if (!sort || !first) return null;
  if (!board || board.sort !== sort) return { sort, dir: null };
  const now = parseHbDir(board.sort_dir) ?? first;
  const flip: HbDir = now === 'desc' ? 'asc' : 'desc';
  return { sort, dir: flip === first ? null : flip };
}

/** The params this tab reads with its own meanings — dropped by
 *  chartMaps.tabSearch when a switch crosses into or out of high_beta (the
 *  🚩 Gajjala's precedent), so a ticked 🎢 box never rides to another tab's
 *  address and back. 2026-10-14 b: + `hb_dir` and `hb_view` (a 🎢 column
 *  direction or the Sales view mean nothing on another tab). */
export const HB_OWN_PARAMS: ReadonlyArray<string> = [
  HB_FILTER_PARAM, HB_MODE_PARAM, HB_ALL_PARAM, HB_DIR_PARAM, HB_VIEW_PARAM,
];

const KNOWN: ReadonlySet<string> = new Set(HB_FILTER_KEYS);

/** `'B20, d5,foo'` -> {b20, d5}. Split on `,` and `+`, trim, lowercase,
 *  known keys only; null / empty / unknown-only -> empty set. */
export function parseHbFilters(v: string | null | undefined): Set<HbFilterKey> {
  const out = new Set<HbFilterKey>();
  if (typeof v !== 'string') return out;
  for (const raw of v.split(/[,+]/)) {
    const k = raw.trim().toLowerCase();
    if (KNOWN.has(k)) out.add(k as HbFilterKey);
  }
  return out;
}

/** The canonical param (`b15,b20,top20,qqq,d5` order), known keys only;
 *  null when nothing known is selected — the URL then carries no `hb`. */
export function hbFiltersParam(sel: Iterable<string>): string | null {
  const s = new Set<string>();
  for (const k of sel) if (typeof k === 'string') s.add(k.trim().toLowerCase());
  const keys = HB_FILTER_KEYS.filter((k) => s.has(k));
  return keys.length ? keys.join(',') : null;
}

/** `?hb_mode=` -> 'all' only for "all" (any case / spacing); anything else
 *  -> 'any'. The Dual Momentum parser, by import. */
export function parseHbMode(v: string | null | undefined): DmMode {
  return parseDmMode(v);
}

/** `?hb_all=` -> true only for `1` / `true` (any case / spacing). */
export function parseHbAll(v: string | null | undefined): boolean {
  if (typeof v !== 'string') return false;
  const s = v.trim().toLowerCase();
  return s === HB_ALL_ON || s === 'true';
}

export { DM_MODE_ALL as HB_MODE_ALL, DM_MODE_ANY as HB_MODE_ANY };

/* ── the payload (BUILD_SPEC §3.3 + AMENDMENTS A1 / A14) ─────────────────── */

export type CmHighBetaState = 'read' | 'no_print' | 'no_snapshot' | 'stale' | 'suspect';

/** `tile.high_beta.today` (high_beta_tab.today_read). A name with no print is
 *  never +0.00%: `move_pct` is null and `state` says why. */
export type CmHighBetaToday = {
  state: CmHighBetaState | string;
  move_pct: number | null;
  prev_close: number | null;
  print: number | null;
  basis: 'live' | 'day_close' | 'last_session' | null | string;
  mode: 'live' | 'after_close' | 'closed' | string;
  day: string;
  reason: string | null;
};

/* ── 🔗 leveraged-ETF tags (2026-10-14, sepa/levered_etf.py) ────────────────
 * Ajay: "Can you add a short tag on these stocks for their Leverage
 * equivalents like IRE for IREN, VSTL for VST". The map, the order, the chip
 * text, its parts, the "+n" title and the board line are ALL served; the FE
 * prints the parts and composes nothing. */

/** One tagged fund (levered_etf.for_symbol): served in the served order. */
export type CmLeveredItem = { etf: string; factor: number; direction: 'long' | 'short' | string };

/** One piece of the served chip: a text run (`title` on the "+n" run = the
 *  funds not shown) or an `etf` ticker (`title` = the fund's name). */
export type CmLeveredPart = { text?: string; etf?: string; title?: string | null };

/** levered_etf.chip — `text` = the parts joined (server-side). */
export type CmLeveredChip = {
  text: string;
  parts: CmLeveredPart[];
  shown: string[];
  more: number;
  rest: string | null;
};

/** `high_beta_board.levered` (levered_etf.status_block). `line` is printed
 *  as served; `legend` is the title on every table chip. */
export type CmLeveredBoard = {
  state: 'ready' | 'stale' | 'missing' | 'error' | string;
  as_of: string | null;
  age_days: number | null;
  grouped_day: string | null;
  n_etfs: number | null;
  n_underlyings: number | null;
  n_on: number;
  line: string | null;
  legend: string | null;
};

/** `tile.high_beta` (high_beta_tab.tile_block + the board's `zone`). */
export type CmHighBetaRead = {
  beta: number;
  cats: string[];
  qqq: boolean | null;
  sigma_pct: number | null;
  swing: number | null;
  today: CmHighBetaToday;
  adv50: number | null;
  zone?: Record<string, unknown> | null;
  levered?: CmLeveredItem[];
  levered_chip?: CmLeveredChip | null;
};

/** `tile.hb_filter`: true passes, false fails, null = not read (an unread
 *  `d5`, or `qqq` when the Nasdaq-100 list could not be read). */
export type CmHbTileFilter = {
  b15: boolean | null; b20: boolean | null; top20: boolean | null;
  qqq: boolean | null; d5: boolean | null;
};

/** One compact row (`payload.rows`, high_beta_tab.compact_row, A1) — EVERY
 *  listed name left after the view, the boxes and the liquidity floor, in the
 *  served order; the charts are the first of them. `text` is the display of
 *  each number cell (the card's own stat values, tile_stats) and is printed
 *  verbatim; `red` is the server's red-today read (high_beta_tab.is_red). */
export type CmHighBetaRow = {
  symbol: string;
  beta: number | null;
  cats: string[];
  /** null = the Nasdaq-100 list could not be read this build (unknown). */
  qqq: boolean | null;
  move_pct: number | null;
  state: CmHighBetaState | string | null;
  swing: number | null;
  sigma_pct: number | null;
  prev_close: number | null;
  basis: string | null;
  /** Under the liquidity floor: a row, never a chart (the count line says so). */
  thin: boolean;
  red: boolean;
  text: {
    beta?: string; sigma?: string; today?: string; swing?: string;
    /** 2026-10-14 b — the served text of the 5 / 21-day legs and RS ("—" = not read). */
    ret_5d?: string; ret_21d?: string; rel_5d?: string; rel_21d?: string; rs_spy_63d?: string;
  } | null;
  /** 🔗 the stock's leveraged ETFs ([] when none / the map is not ready). */
  levered?: CmLeveredItem[];
  levered_chip?: CmLeveredChip | null;
  /** 2026-10-14 b (K2) — the stock's own 5 / 21-session % move and the same
   *  minus the served `rel` bench (RSP, SPY fallback), in pp; null = not read
   *  (a raw move never lands in a vs column). */
  ret_5d?: number | null;
  ret_21d?: number | null;
  rel_5d?: number | null;
  rel_21d?: number | null;
  /** K3 — the 63-session move minus SPY's, in pp; null = not read. */
  rs_spy_63d?: number | null;
  /** The 🔥 Hottest fundamentals (HOT._fundamentals_row values unchanged);
   *  null when the research cache was not read this build. */
  fund?: CmHighBetaFund | null;
};

/** `rows[].fund` — EXACTLY high_beta_tab.FUND_ROW_KEYS (the 14 keys of
 *  HOT._fundamentals_row the Sales view prints). A LOCAL structural type
 *  (AMENDMENTS2 B4: no import from components/HottestSectors); each key is
 *  typed as 🔥 Hottest's own row types it, so a fund row is assignable to the
 *  Hottest fundamentals cell's row with no cast. */
export type CmHighBetaFund = {
  sales_yoy: number | null;
  sales_prior_yoy: number | null;
  sales_accelerating: boolean | null;
  sales_tier: string | null;
  period_ok: boolean | null;
  q_eps_yoy: number | null;
  net_margin: number | null;
  margin_expanding: boolean | null;
  eq_score: number | null;
  eq_tier: string | null;
  code_33: boolean | null;
  inventory_flag: boolean | null;
  next_earnings: string | null;
  earnings_when: string | null;
};

/** The served column heads, in the served order (high_beta_tab.TABLE_COLUMNS
 *  for Price, SALES_COLUMNS for Sales). `sort` = the column's served sort key
 *  (null = not a sort head), `first` = the direction its first tap opens in
 *  (2026-10-14 b). */
export type CmHighBetaColumn = {
  key: string; label: string; title?: string | null;
  sort?: string | null; first?: HbDir | null;
};

/** `high_beta_board.table` (high_beta_tab.table_block; null unless ready):
 *  the heads of the dense table and the served category / QQQ badge words
 *  (high_beta_tab.CAT_SHORT / QQQ_ETF). */
export type CmHighBetaTable = {
  columns: CmHighBetaColumn[];
  cat_labels: Record<string, string>;
  qqq_label: string;
  /** 2026-10-14 b (K1) — the Sales view's heads, the served view labels and
   *  the URL param the switch writes (FE-only). */
  sales_columns?: CmHighBetaColumn[];
  views?: { key: HbView; label: string }[];
  view_param?: string;
};

/** `high_beta_board.fundamentals` (high_beta_tab.fundamentals_block; null
 *  unless ready). `line` and `note` are printed as served; `quality_info` is
 *  the ⓘ Quality explainer (the 🔥 Hottest sheet's payload). */
export type CmHighBetaFundamentals = {
  state: 'ready' | 'not_read' | string;
  n: number | null;
  of: number | null;
  n_earnings: number | null;
  as_of: { oldest: string; newest: string; n: number } | null;
  quality_info: HsQualityInfo | null;
  reason: string | null;
  line: string;
  note: string;
};

/** `high_beta_board.view` (A1): the "include green names" switch — `on` = the
 *  SERVED state (what the server applied), `label` served. */
export type CmHighBetaView = { param: string; on: boolean; label: string };

/** `board.high_beta_board` (high_beta_tab ready / warming / error blocks). */
export type CmHighBetaBoard = {
  state: 'ready' | 'warming' | 'error' | string;
  mode: 'live' | 'after_close' | 'closed' | string;
  session: string;
  as_of: string | null;
  built_at: string | null;
  base_built_at: string | null;
  stale: boolean;
  measured: boolean;
  refresh_sec: number | null;
  sort: string;
  header: string;
  market_line: string | null;
  qqq_line: string | null;
  order_line: string | null;
  view_line: string | null;
  count_line: string | null;
  categories_line: string | null;
  categories: Record<string, unknown> | null;
  qqq: {
    available: boolean; n: number; source: string | null; age_days: number | null;
    error: string | null; note: string | null;
  } | null;
  filters: CmDmFilters | null;
  note: string;
  study: { status: string; text: string; verdict: string | null; prereg: string | null; script: string | null } | null;
  counts: Record<string, number> | null;
  suspects: { n: number; head: string; lines: string[] } | null;
  view: CmHighBetaView | null;
  table: CmHighBetaTable | null;
  /** 🔗 the leveraged-ETF map's state + served line (null unless ready). */
  levered?: CmLeveredBoard | null;
  /** 2026-10-14 b — the resolved direction of `sort`; the preset key when the
   *  active (sort, dir) is a preset in its first direction, else null; the
   *  served 5 / 21-day header line (SPY's and RSP's own legs); the Sales
   *  view's fundamentals block. */
  sort_dir?: HbDir | string;
  sort_preset?: string | null;
  returns_line?: string | null;
  fundamentals?: CmHighBetaFundamentals | null;
};
