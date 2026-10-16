/* 🕯️ Doji Sweep — the payload types and three pure helpers (2026-10-16).
 *
 * Ajay 2026-10-16, verbatim: "create me a new tab for Doji candle after a
 * sweep. For any stocks after a down trend. May be from all chart maps
 * especially on the 60% 70% down stocks" — then, on the knobs: "Within 5%
 * either side counts as a test" and "Yes, any read; chips narrow".
 *
 * The board is read, counted and ordered on the server
 * (backend/chart_maps/doji_sweep_tab.py). Every sentence is served; no
 * threshold typed here. This module carries the param names, the chip keys
 * and the tab's two sort keys (each pinned equal to its backend constant by
 * the contracts) plus the payload types (doji spec §3.4 / §3.9) — the body
 * switch's steps, every chip label and every count come from the payload, so
 * a changed constant on the server shows up with no frontend deploy.
 *
 * Imports NOTHING at runtime from ./chartMaps (types only) — no cycle.
 */
export const DJ_FILTER_PARAM = 'dj';                     // == doji_sweep_tab.FILTER_PARAM (contract)
export const DJ_BODY_PARAM = 'dj_body';                  // == doji_sweep_tab.BODY_PARAM
export const DJ_FILTER_KEYS = ['w52_40', 'w52_60', 'w52_70', 'ath_60', 'mas', 'reclaimed'] as const;   // == FILTER_KEYS
export type DjFilterKey = typeof DJ_FILTER_KEYS[number];
export const DJ_SORT_TEST = 'doji_test';                 // == doji_sweep_tab.SORT_TEST
export const DJ_SORT_ATH = 'doji_ath';                   // == doji_sweep_tab.SORT_ATH
/** The params this tab reads with its own meanings — dropped at the tab
 *  border by chartMaps.tabSearch (the 🎢 rule). */
export const DJ_OWN_PARAMS: ReadonlyArray<string> = [DJ_FILTER_PARAM, DJ_BODY_PARAM];

const KNOWN: ReadonlySet<string> = new Set(DJ_FILTER_KEYS);

/** `?dj=` -> the known chip keys: split on `,` and `+`, trimmed, lowercased;
 *  unknown tokens dropped. A non-string -> the empty set. */
export function parseDjFilters(v: string | null | undefined): Set<DjFilterKey> {
  const out = new Set<DjFilterKey>();
  if (typeof v !== 'string') return out;
  for (const raw of v.split(/[,+]/)) {
    const k = raw.trim().toLowerCase();
    if (KNOWN.has(k)) out.add(k as DjFilterKey);
  }
  return out;
}

/** The canonical param (DJ_FILTER_KEYS order), known keys only; null when
 *  nothing known is selected — the URL then carries no `dj`. */
export function djFiltersParam(sel: Iterable<string>): string | null {
  const s = new Set<string>();
  for (const k of sel) if (typeof k === 'string') s.add(k.trim().toLowerCase());
  const keys = DJ_FILTER_KEYS.filter((k) => s.has(k));
  return keys.length ? keys.join(',') : null;
}

const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : null;
const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;

/** The value to put in ?dj_body= for a click on served step `key`: null (delete the param) for the served default or an
 *  unknown / malformed board; the key for any other SERVED step (the fallen.depthToSend rule). */
export function djBodyToSend(board: unknown, key: string): string | null {
  const k = text(key);
  if (!k) return null;
  const body = obj(obj(board)?.body);
  if (!body || !Array.isArray(body.steps)) return null;
  for (const raw of body.steps as unknown[]) {
    const s = obj(raw);
    if (!s || text(s.key) !== k) continue;
    return s.default === true ? null : k;
  }
  return null;
}

/** The per-tile block (`tile.doji_sweep`, doji_sweep_tab.tile_block; `zone`
 *  added by the board). Every sentence in it is served. */
export type CmDojiSweepRead = { date: string; variant: string; variant_text: string; body_pct: number; upper_wick_pct: number;
  lower_wick_pct: number; doji5: boolean; ref_low: number; ref_date: string; ref_age: number; test_pct: number; tested: boolean;
  undercut: boolean; reclaimed: boolean; test_text: string; reads: string[]; reads_text: string;
  w52: { high: number; high_date: string; pct_below: number } | null; pct_below_52w: number | null;
  ath: { hi: number; hi_date: string; proven: boolean; label: string; since: string | null; pct_below: number } | null;
  pct_below_ath: number | null; sma50: number | null; sma200: number | null; below_mas: boolean; vol_ratio: number | null;
  vol_word: string | null; range_atr: number | null; close: number; adv50: number | null; zone?: Record<string, unknown> | null };

/** One served body step (doji_sweep_tab.body_block). */
export type CmDojiSweepBodyStep = { key: string; label: string; title: string; on: boolean; default: boolean };

/** The board-level block (doji_sweep_tab.ready_block / warming_block /
 *  error_block). `count_line`, `counts`, `suspects`, `as_of` and `built_at`
 *  are null while the memo warms or on error. `filters` is the 🏎️ chip block
 *  shape (no mode switch is served: every ticked chip must pass). */
export type CmDojiSweepBoard = { state: 'ready' | 'warming' | 'error' | string; session: string; as_of: string | null;
  built_at: string | null; measured: boolean; study: { status: string; text: string; verdict: string | null; prereg: string;
  script: string }; sort: string; header: string; order_line: string; count_line: string | null; note: string;
  body: { param: string; pct: number; steps: CmDojiSweepBodyStep[] };
  filters: unknown; counts: Record<string, number> | null; suspects: { n: number; head: string; lines: string[] } | null;
  reads_legend: string[]; test_pct: number; ref_sessions: number; ref_min_age: number; down_pct: number; sma_fast: number;
  sma_slow: number; year_bars: number; filter_param: string };
