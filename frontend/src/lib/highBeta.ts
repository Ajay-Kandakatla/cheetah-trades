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

/** The params this tab reads with its own meanings — dropped by
 *  chartMaps.tabSearch when a switch crosses into or out of high_beta (the
 *  🚩 Gajjala's precedent), so a ticked 🎢 box never rides to another tab's
 *  address and back. */
export const HB_OWN_PARAMS: ReadonlyArray<string> = [HB_FILTER_PARAM, HB_MODE_PARAM, HB_ALL_PARAM];

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
  text: { beta?: string; sigma?: string; today?: string; swing?: string } | null;
};

/** The served column heads, in the served order (high_beta_tab.TABLE_COLUMNS).
 *  Keys the table knows: symbol · beta · sigma · cats · qqq · today · swing. */
export type CmHighBetaColumn = { key: string; label: string; title?: string | null };

/** `high_beta_board.table` (high_beta_tab.table_block; null unless ready):
 *  the heads of the dense table and the served category / QQQ badge words
 *  (high_beta_tab.CAT_SHORT / QQQ_ETF). */
export type CmHighBetaTable = {
  columns: CmHighBetaColumn[];
  cat_labels: Record<string, string>;
  qqq_label: string;
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
};
