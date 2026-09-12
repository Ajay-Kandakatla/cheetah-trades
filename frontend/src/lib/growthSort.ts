/* Sorting the 🚀 Explosive Growth board.
 *
 * Ajay 2026-09-12: *"sort this by demand intact"*.
 *
 * WHY THIS EXISTS AT ALL: the board sorted by sales growth and nothing else,
 * so the four names actually standing at an intact demand floor (HHH, HNI,
 * ARR, RKT on the 09-12 build) sat 5th to 20th, under fifteen names that are
 * not at a band at all. The one column that carries a MEASURED edge was the
 * one column you could not order by.
 *
 * THIS SORT RUNS IN THE BROWSER, AND THAT IS CORRECT HERE — the opposite of
 * the 🔥 Hottest board, which had to round-trip. Hottest keeps only
 * `names_per_group` rows per sector, so a client sort there would reorder the
 * visible 25 and never reach the 46th name. This payload carries EVERY row the
 * screen returned (29 of a 300 cap), so sorting locally is complete. Do not
 * "fix" this into a server sort for consistency: it would add a round-trip
 * that buys nothing.
 *
 * NOTHING HERE IS A SIGNAL. Ordering changes what you look at first, not
 * whether any of it works.
 */

/** The zone read the backend attaches to each row (growth/tracker._zone_read). */
export type GrowthZoneLike = {
  missing?: boolean;
  in_band?: boolean;
  /** true = floor never pierced · false = pierced · null/undefined = the gate
   *  never answered. The third case is NOT the second one. */
  intact?: boolean | null;
};

export type GrowthRowLike = {
  symbol: string;
  sales_growth_pct?: number | null;
  sales_prior_pct?: number | null;
  q_eps_growth_pct?: number | null;
  npm_latest_pct?: number | null;
  price?: number | null;
  market_cap?: number | null;
  avg_dollar_vol?: number | null;
  zone?: GrowthZoneLike;
};

/* ── the demand ladder ─────────────────────────────────────────────────────
 * Ordered by DISTANCE FROM THE ONE GATE THAT MEASURED — `intact`, +8.6pp over
 * 31,861 events (2026-09-09 bounce-gate study). Not by how good the name is.
 *
 *   3  🧲 intact          in a demand band, floor never pierced
 *   2  in band, pierced   in the band, but the floor went. The intact edge
 *                         does NOT apply — a different, worse situation.
 *   1  out                scanned, has bands, standing in none of them
 *
 * and two states that are UNKNOWN rather than bad, which is a different thing:
 *
 *   null  no bands            outside the scan universe — no zone read exists
 *   null  in band, floor ?    the band is real, the gate threw. We do not know.
 *
 * An unknown sorts LAST IN BOTH DIRECTIONS, the same rule the 🔥 Hottest
 * columns follow. Ranking an unknown as a zero is how a name with no data
 * floats to the top of an ascending sort and reads as the worst on the board.
 */
export const DEMAND_INTACT = 3;
export const DEMAND_PIERCED = 2;
export const DEMAND_OUT = 1;

export function demandRank(z?: GrowthZoneLike): number | null {
  if (!z || z.missing) return null;              // no zone read at all
  if (!z.in_band) return DEMAND_OUT;
  if (z.intact === true) return DEMAND_INTACT;
  if (z.intact === false) return DEMAND_PIERCED;
  return null;                                   // in a band, floor unanswered
}

/** Every column the table prints, in header order. `demand` is the one he
 *  asked for; the rest ship with it because a table where exactly one column
 *  sorts is a table you click the wrong header on. */
export const SORT_KEYS = [
  'symbol', 'sales_growth_pct', 'sales_prior_pct', 'q_eps_growth_pct',
  'npm_latest_pct', 'price', 'market_cap', 'avg_dollar_vol', 'demand',
] as const;
export type GrowthSortKey = (typeof SORT_KEYS)[number];
export type SortDir = 'asc' | 'desc';

/** The board opens on DEMAND, best first — his ask. Click Sales YoY to get the
 *  old order back; the header says which one is live. */
export const DEFAULT_SORT: GrowthSortKey = 'demand';
export const DEFAULT_DIR: SortDir = 'desc';

/** A new column opens in the direction that puts the INTERESTING end on top.
 *  Every column here is "bigger is more interesting" except the symbol, which
 *  is a name and reads A→Z. */
export function initialDir(key: GrowthSortKey): SortDir {
  return key === 'symbol' ? 'asc' : 'desc';
}

/** (known, value) for a row under one key. `known:false` is the missing case
 *  and is what pushes a row to the bottom of BOTH directions. */
export function sortValue(r: GrowthRowLike, key: GrowthSortKey):
{ known: boolean; value: number | string } {
  if (key === 'symbol') return { known: true, value: r.symbol || '' };
  if (key === 'demand') {
    const rank = demandRank(r.zone);
    return rank == null ? { known: false, value: 0 } : { known: true, value: rank };
  }
  const v = r[key];
  return typeof v === 'number' && Number.isFinite(v)
    ? { known: true, value: v }
    : { known: false, value: 0 };
}

/** Sales growth desc, then symbol — the board's own original order, kept as
 *  the tiebreak so equal rows never shuffle between renders and the four
 *  intact names stay ranked among themselves the way the board ranked them. */
function tiebreak(a: GrowthRowLike, b: GrowthRowLike): number {
  const sa = typeof a.sales_growth_pct === 'number' ? a.sales_growth_pct : -Infinity;
  const sb = typeof b.sales_growth_pct === 'number' ? b.sales_growth_pct : -Infinity;
  if (sa !== sb) return sb - sa;
  return (a.symbol || '').localeCompare(b.symbol || '');
}

/** Sorted COPY — never sorts the caller's array in place, because the rows
 *  come straight off the fetched payload and mutating them would make the
 *  filter memo above this depend on click order. */
export function sortRows<T extends GrowthRowLike>(
  rows: readonly T[], key: GrowthSortKey, dir: SortDir,
): T[] {
  const sign = dir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const va = sortValue(a, key);
    const vb = sortValue(b, key);
    // Unknown last in BOTH directions — checked before the direction sign is
    // applied, which is the whole point: the sign must never flip it up.
    if (va.known !== vb.known) return va.known ? -1 : 1;
    if (va.known) {
      if (typeof va.value === 'string' || typeof vb.value === 'string') {
        const c = String(va.value).localeCompare(String(vb.value));
        if (c !== 0) return sign * c;
      } else if (va.value !== vb.value) {
        return sign * (va.value < vb.value ? -1 : 1);
      }
    }
    return tiebreak(a, b);
  });
}

/** The arrow on the live header. '' on every other column — two arrows on one
 *  table is how a board starts lying about its own order. */
export function arrow(key: GrowthSortKey, active: GrowthSortKey, dir: SortDir): string {
  return key === active ? (dir === 'desc' ? ' ▾' : ' ▴') : '';
}

/** What the caption says the order is, in words. Derived from the live state,
 *  never retyped — a label that can disagree with the sort is worse than none. */
export const SORT_LABEL: Record<GrowthSortKey, string> = {
  symbol: 'symbol',
  sales_growth_pct: 'sales YoY',
  sales_prior_pct: 'prior-quarter sales',
  q_eps_growth_pct: 'quarterly EPS',
  npm_latest_pct: 'net margin',
  price: 'price',
  market_cap: 'market cap',
  avg_dollar_vol: 'dollar volume',
  demand: 'demand — intact floors first',
};
