/* 📉 Down 40%+ — the payload types and three pure helpers (2026-10-02).
 *
 * Ajay 2026-10-02, verbatim: "Can you build me a tab in chart maps about
 * stocks that dropped more than 40% lowers from like app loving company as an
 * example whcih si 60% low. But I also need you to capture informations about
 * sales like Bondes and other indicators based on Bondes formula please." then
 * "Scan the universe and bring me these stocks" and "also add things like
 * possible catalyst that made is drop like that."
 *
 * The board is read, counted and ordered on the server
 * (backend/chart_maps/fallen_tab.py + fallen_catalysts.py). Every sentence on
 * the tab is SERVED; the types below are the payload contract (fallen spec
 * §3.7) and nothing more. This module types no threshold, no depth step, no
 * Bonde word and no number: the depth buttons, the sort buttons and every
 * line come from the payload, so a changed constant on the server shows up
 * with no frontend deploy. UNMEASURED — display only.
 */
import type { BondePickCoverage, BondePickLegend } from './bondePicks';
import type { CmSort } from './chartMaps';

/** One on-file item inside a drop day's window (fallen_catalysts.items_for).
 *  Co-occurrence on a date, labelled possible on the server — never a cause. */
export type CmFallenItem = {
  kind: 'earnings' | 'filing' | 'medical' | 'index' | 'news' | 'analyst' | 'model' | string;
  date: string;
  text: string;
  url: string | null;
  source: string;
};

/** The name's sector ETF, theme median and RSP on the drop day
 *  (fallen_catalysts.group_day). No verdict word is served. */
export type CmFallenGroup = {
  sector: string | null;
  sector_etf: string | null;
  sector_etf_pct: number | null;
  theme: string | null;
  theme_median_pct: number | null;
  theme_n: number;
  rsp_pct: number | null;
  line: string | null;
};

/** One of the largest single-session drops since the 52-week high
 *  (fallen_tab.top_drops + fallen_catalysts.attach_all). */
export type CmFallenDrop = {
  date: string;
  c2c_pct: number;
  gap_pct: number | null;
  intraday_pct: number | null;
  larger_leg: 'gap' | 'intraday' | string;
  vol_x50: number | null;
  share_of_fall_pct: number | null;
  prev_close: number;
  close: number;
  window: { lo: string; hi: string };
  line: string;
  items: CmFallenItem[];
  empty: string | null;
  group: CmFallenGroup | null;
};

/** The per-tile block (`tile.fallen`, fallen_tab.tile_block). */
export type CmFallenRead = {
  pct_below: number;
  high: number;
  high_date: string;
  low: number;
  low_date: string;
  pct_above_low: number;
  close: number;
  close_date: string;
  market_cap: number | null;
  sector: string | null;
  sector_source: 'scan' | 'profile' | null | string;
  in_scan: boolean;
  scan_note: string | null;
  bonde: { n_pass: number; n_read: number; n_not_read: number; line: string };
  sales: {
    yoy_pct: number | null; prior_yoy_pct: number | null; qoq_pct: number | null;
    qoq_base: string | null; period: string | null; period_ok: boolean | null;
    base_state: string | null; pair_blanked: boolean; line: string;
  };
  hit: { text: string; class: string; date: string | null };
  drops_head: string | null;
  drops: CmFallenDrop[];
  top3_share_pct: number | null;
  /** The 🏎️ Dual Momentum zone read (dual_momentum_tab.zone_read), as served. */
  zone?: Record<string, unknown> | null;
};

/** One served depth step (fallen_tab.depths_block). */
export type CmFallenDepth = { key: string; label: string; on: boolean; default: boolean };

/** The board-level block (fallen_tab.ready_block / warming_block /
 *  error_block). `counts`, `suspects`, `pick_legend`, `pick_coverage`,
 *  `catalysts` and `built_at` are null while the memo warms or on error.
 *  Invariant (server, tested): scanned == no_bars + delisted + etf + stale +
 *  short_history + under_threshold + data_suspect + fallen. */
export type CmFallenBoard = {
  state: 'ready' | 'warming' | 'error';
  session: string;
  as_of: string | null;
  built_at: string | null;
  stale_scan: boolean;
  measured: boolean;
  threshold_pct: number;
  year_bars: number;
  glitch_ratio: number;
  depth_pct: number;
  depth_param: string;
  depths: CmFallenDepth[];
  sort: string;
  header: string;
  order_line: string | null;
  count_line: string | null;
  note: string;
  counts: {
    scanned: number; no_bars: number; delisted: number; etf: number; stale: number;
    short_history: number; under_threshold: number; data_suspect: number; fallen: number;
    at_depth: number; in_scan: number; dropped_thin: number; no_turnover: number; shown: number;
  } | null;
  suspects: { n: number; head: string; lines: string[] } | null;
  pick_legend: BondePickLegend | null;
  pick_coverage: BondePickCoverage | null;
  catalysts: {
    note: string; line: string;
    sources: Array<{ key: string; label: string; available: boolean; names: number | null;
                     first: string | null; last: string | null }>;
    drops: number; nothing_on_file: number; nothing_line: string;
  } | null;
};

const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : null;
const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;

/** The served depth steps, well-formed entries only (a string key and label),
 *  in served order. A malformed board or `depths` → []. */
export function servedDepths(board: unknown): CmFallenDepth[] {
  const b = obj(board);
  if (!b || !Array.isArray(b.depths)) return [];
  const out: CmFallenDepth[] = [];
  for (const raw of b.depths as unknown[]) {
    const d = obj(raw);
    if (!d) continue;
    const key = text(d.key);
    const label = text(d.label);
    if (!key || !label) continue;
    out.push({ key, label, on: d.on === true, default: d.default === true });
  }
  return out;
}

/** The `?depth=` value a click on `key` should write: the key itself, or null
 *  when that served step is the served default (the URL stays clean) or is
 *  not a served step at all (a step the server does not offer is never sent). */
export function depthToSend(board: unknown, key: unknown): string | null {
  const k = text(key);
  if (!k) return null;
  const hit = servedDepths(board).find((d) => d.key === k);
  if (!hit || hit.default) return null;
  return hit.key;
}

/** The keys of the served sorts, well-formed entries only, in served order. */
export function servedSortKeys(sorts: unknown): string[] {
  if (!Array.isArray(sorts)) return [];
  return (sorts as unknown[])
    .map((s) => obj(s) as Partial<CmSort> | null)
    .filter((s): s is CmSort => !!s && !!text(s.key) && !!text(s.label))
    .map((s) => s.key);
}
