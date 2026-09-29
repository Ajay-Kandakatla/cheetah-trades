/* dmFilters — the 🏎️ Dual Momentum tab's three filter boxes (2026-09-29).
 *
 * Ajay 2026-09-29, verbatim: "Can you add AMD raided and near demand zone and
 * near lower Key level filters to dual momentum please".
 *
 * 🌀 AMD raided · 📍 Near demand zone · 🔑 Near a lower key level. The ticked
 * set lives in the URL as `?dm=amd,zone,level` and rides to the server on the
 * dual_momentum tab only (chart_maps/dual_momentum_tab.FILTER_KEYS, pinned
 * equal by contract). The server decides every pass; this file compares no
 * number — it only parses and writes the param.
 */

export const DM_FILTER_PARAM = 'dm';
export const DM_FILTER_KEYS = ['amd', 'zone', 'level'] as const;
export type DmFilterKey = typeof DM_FILTER_KEYS[number];

const KNOWN: ReadonlySet<string> = new Set(DM_FILTER_KEYS);

/** `'level,AMD, foo'` -> {amd, level}. Split on `,` and `+`, trim, lowercase,
 *  known keys only; null / empty / unknown-only -> empty set. */
export function parseDmFilters(v: string | null | undefined): Set<DmFilterKey> {
  const out = new Set<DmFilterKey>();
  if (typeof v !== 'string') return out;
  for (const raw of v.split(/[,+]/)) {
    const k = raw.trim().toLowerCase();
    if (KNOWN.has(k)) out.add(k as DmFilterKey);
  }
  return out;
}

/** The canonical param (`amd,zone,level` order), known keys only; null when
 *  nothing known is selected — the URL then carries no `dm`. */
export function dmFiltersParam(sel: Iterable<string>): string | null {
  const s = new Set<string>();
  for (const k of sel) if (typeof k === 'string') s.add(k.trim().toLowerCase());
  const keys = DM_FILTER_KEYS.filter((k) => s.has(k));
  return keys.length ? keys.join(',') : null;
}

/** One served box (chart_maps/dual_momentum_tab.filters_block items). */
export type CmDmFilterItem = {
  key: string; label: string; on: boolean;
  pass: number; fail: number; no_read: number; hidden: number; note: string;
};

/** `dual_momentum_board.filters` — ready state only; null otherwise. */
export type CmDmFilters = {
  keys: string[]; active: string[]; pool: number; passed_all: number | null;
  items: CmDmFilterItem[]; line: string | null; note: string;
  near_demand_pct: number; near_level_pct: number; measured: boolean;
};

/** The per-tile read (`tile.dm_filter`): true passes, false fails, null = not read. */
export type CmDmTileFilter = {
  amd: boolean | null; amd_grade?: string | null; amd_reason?: string | null;
  zone: boolean | null; level: boolean | null;
  level_status?: string | null; level_near?: unknown;
};
