/* 🔻 Down 10%+ today — the payload types and one pure helper (2026-10-05).
 *
 * Ajay 2026-10-03, verbatim: "I would like to know about stocks that falled
 * intraday more than 10% new tab please."
 *
 * The board is read, counted and ordered on the server
 * (backend/chart_maps/drop10_tab.py). Every sentence on the tab is SERVED;
 * the types below are the payload contract and nothing more. This module
 * types no threshold and no number: the sort buttons, every line and the live
 * refresh cadence come from the payload, so a changed constant on the server
 * shows up with no frontend deploy. Display only.
 */
import type { CmFallenGroup, CmFallenItem } from './fallen';

/** Volume vs normal (momentum_burst.rvol_leg): `basis` says whether `rvol`
 *  is the full session, so far, or projected to a full session. */
export type CmDrop10Rvol = {
  rvol: number | null;
  basis: 'session' | 'actual' | 'projected' | null | string;
  actual: number | null;
  projected: number | null;
  session_pct: number | null;
  code: string | null;
};

/** `tile.drop10` (drop10_tab.tile_block + the board's `zone`). */
export type CmDrop10Read = {
  session: string;
  mode: 'live' | 'after_close' | 'closed' | string;
  state: 'down' | 'reclaimed' | string;
  state_text: string;
  prev_close: number;
  prev_date: string;
  open: number;
  high: number;
  low: number;
  last: number;
  low_pct: number;
  now_pct: number;
  gap_pct: number | null;
  open_to_low_pct: number | null;
  off_low_pct: number | null;
  legs_text: string;
  rvol: CmDrop10Rvol;
  rvol_text: string;
  sector: string | null;
  hit: { text: string; class: string; date: string | null };
  items: CmFallenItem[];
  empty: string | null;
  group: CmFallenGroup | null;
  zone?: Record<string, unknown> | null;
};

/** `board.drop10_board` (drop10_tab._block). */
export type CmDrop10Board = {
  state: 'ready' | 'warming' | 'error' | string;
  mode: 'live' | 'after_close' | 'closed' | string;
  session: string;
  as_of: string | null;
  built_at: string | null;
  stale: boolean;
  measured: boolean;
  threshold_pct: number;
  refresh_sec: number | null;
  glitch_ratio: number;
  sort: string;
  header: string;
  order_line: string;
  count_line: string | null;
  note: string;
  counts: Record<string, number> | null;
  suspects: { n: number; head: string; lines: string[] } | null;
  catalysts: { note?: string; line?: string; nothing_line?: string } | null;
};

/** How often the page re-reads a LIVE board, in ms — the SERVED
 *  `refresh_sec` (the server's cache freshness), or null when the board is
 *  not live (after the close, overnight, warming, malformed). Never below
 *  15 s, whatever is served: a typo on the server must not hammer it. */
export function drop10RefreshMs(board: unknown): number | null {
  if (!board || typeof board !== 'object' || Array.isArray(board)) return null;
  const b = board as Record<string, unknown>;
  if (b.state !== 'ready' || b.mode !== 'live') return null;
  const s = b.refresh_sec;
  if (typeof s !== 'number' || !Number.isFinite(s) || s <= 0) return null;
  return Math.max(15, s) * 1000;
}
