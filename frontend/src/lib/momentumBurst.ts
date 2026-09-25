/* ⚡ Momentum burst — the Chart Maps pin + badge (Ajay 2026-09-24).
 *
 * His words are quoted verbatim in the ✨ entry (newFeatures.ts,
 * momentum-burst-2026-09-24) and the dated doc; they are not repeated here
 * because this file must carry no threshold, not even inside a quote. The gist:
 * volume, a small reversal off the low, "not enough runway" past his limit,
 * "Up moves only", "Pin + badge, hide nothing", "Use the app's numbers".
 *
 * THE READ IS SERVED. backend/supply_demand/momentum_burst.py decides every
 * verdict (relative volume projected fairly through the day, the print above
 * today's session low inside the runway limit) and writes every word of the
 * badge and the hover. Nothing in this file compares a number: a second copy
 * of the rule in TSX is a second engine that drifts the first time a constant
 * moves. This file only asks "did the server say burst?" and re-orders.
 *
 * UNMEASURED — no study behind it. It pins and badges; it gates nothing,
 * pushes nothing, sizes nothing and enters no lane.
 *
 * THE PIN IS A STABLE PARTITION, never a sort and never a filter: with the box
 * ticked the ⚡ names move to the top in the board's own order and every other
 * name follows in its own order. The ON board is a permutation of the OFF
 * board — nothing is hidden. The state lives in the URL (`?burst=1`) and
 * nowhere else, and toggling never refetches.
 */
import { BONDE_MOM_BURST_1W_PCT } from './cheetahVerdict';

export type BurstState = 'burst' | 'no' | 'unknown';

/** One served read — the keys of momentum_burst.READ_KEYS, every one optional
 *  and nullable so an older payload (or a per-tile build that failed) renders
 *  exactly as before. */
export type BurstRead = {
  state?: BurstState | string | null;
  on?: boolean | null;
  reasons?: string[] | null;
  reason_text?: string[] | null;
  rvol?: number | null;
  rvol_basis?: string | null;
  rvol_actual?: number | null;
  rvol_projected?: number | null;
  session_pct?: number | null;
  projection_early?: boolean | null;
  today_vol?: number | null;
  avg_vol_50?: number | null;
  session_day?: string | null;
  off_low_pct?: number | null;
  low?: number | null;
  low_kind?: string | null;
  print?: number | null;
  print_session?: string | null;
  print_source?: string | null;
  as_of?: string | null;
  ext_print?: number | null;
  ext_as_of?: string | null;
  prev_close?: number | null;
  day_chg_pct?: number | null;
  session?: string | null;
  half_day?: boolean | null;
  badge?: string | null;
  title?: string | null;
  measured?: boolean | null;
};

/** The board-level tally the server returns beside the tiles. */
export type BurstCounts = {
  burst?: number | null;
  no?: number | null;
  unknown?: number | null;
};

/** The one URL key. Default OFF; only the ON value is written. */
export const BURST_PARAM = 'burst';

/** True ONLY for the exact value this page writes. Anything else — a typo, a
 *  "true", an empty value — lands on the default board. */
export function parseBurstParam(v: string | null | undefined): boolean {
  return v === '1';
}

/** The value to write for a state; null = delete the key. */
export function burstParam(on: boolean): string | null {
  return on ? '1' : null;
}

/** Did the SERVER say ⚡? Both flags must agree; no number is read here. */
export function isBurst(read: BurstRead | null | undefined): read is BurstRead {
  return Boolean(read && typeof read === 'object' && read.on === true && read.state === 'burst');
}

/** Stable partition. `on` false → a copy in the incoming order. `pinned`
 *  counts the ⚡ rows in BOTH states (the checkbox shows it before it is
 *  ticked); `unknown` counts the rows the server could not read yet. */
export function pinBurst<T>(
  rows: readonly T[],
  readOf: (row: T) => BurstRead | null | undefined,
  on: boolean,
): { rows: T[]; pinned: number; unknown: number } {
  const all = (rows || []) as readonly T[];
  const hot: T[] = [];
  const rest: T[] = [];
  let unknown = 0;
  for (const row of all) {
    const read = readOf(row);
    if (isBurst(read)) hot.push(row); else rest.push(row);
    if (read && typeof read === 'object' && read.state === 'unknown') unknown += 1;
  }
  return { rows: on ? [...hot, ...rest] : all.slice(), pinned: hot.length, unknown };
}

/** The two reads this one is NOT. The ticker page's weekly figure is IMPORTED,
 *  never typed, so the sentence cannot drift from the check it names. */
export const BURST_DISAMBIGUATION =
  `Not the ticker page's Momentum burst check (≥${BONDE_MOM_BURST_1W_PCT}% in a week), and not 🧨 Burst first (the closed-bar explosive read).`;

const ROW_BOARD =
  "row board with its own renderer, fed by the per-row read route — ⚡ is not wired into it in this build; extending it is Ajay's call";

/** Every Chart Maps tab that is NOT a tile board, and why the ⚡ pin is not on
 *  it. The contract checks these keys against CM_TABS, so a new non-board tab
 *  has to be listed here with a reason before it ships. */
export const BURST_EXEMPT: Record<string, string> = {
  support: 'one symbol per view — there is no list to pin',
  news: 'no ticker rows on this tab — sectors, macro releases and headlines',
  hot_sectors: 'server-cut rows — a browser pin would rank the visible names and never reach the rest of the group',
  potus: 'a fixed editorial order, not a ranking',
  holdings: 'your positions — this tab never re-orders or hides a position',
  ema_frames: ROW_BOARD,
  bonde: ROW_BOARD,
  growth: ROW_BOARD,
  hot_pullback: ROW_BOARD,
  patterns: ROW_BOARD,
  session: ROW_BOARD,
  signals: ROW_BOARD,
  catalysts: ROW_BOARD,
  overnight: ROW_BOARD,
  gnt: ROW_BOARD,
};
