/* useGrowthTags — the 🚀 Explosive Growth board as a symbol lookup, so every
 * OTHER Chart Maps board can show that a name is also a 100/100 grower.
 *
 * Ajay 2026-09-11: "I am hoping this new list will be considerd in all chart
 * maps. Like in Deep demand scan."
 *
 * Module-level cache with an in-flight promise: every tile on every board asks
 * for this, and without the shared promise a 40-tile grid would fire 40
 * requests on first paint. One fetch per page load, shared by all of them.
 *
 * A failure is SILENT and yields an empty map — the chip is decoration on
 * somebody else's board, and a growth-board outage must never blank a demand
 * board or make a name look like it does not qualify.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type GrowthTag = {
  sales?: number | null;
  eps?: number | null;
  /** The trading engine will refuse this name (sub-$2, or a known sub-$700M
   *  cap). Good sales must not make it look clean. */
  refused?: boolean;
};
export type GrowthTags = Record<string, GrowthTag>;

let cache: GrowthTags | null = null;
let inFlight: Promise<GrowthTags> | null = null;

export function _resetGrowthTagsCache() {   // tests only
  cache = null;
  inFlight = null;
}

export function fetchGrowthTags(): Promise<GrowthTags> {
  if (cache) return Promise.resolve(cache);
  if (inFlight) return inFlight;
  inFlight = fetch(`${API}/growth/tags`)
    .then((r) => (r.ok ? r.json() : { tags: {} }))
    .then((j) => {
      cache = (j?.tags ?? {}) as GrowthTags;
      return cache;
    })
    .catch(() => {
      cache = {};            // cache the miss too: do not retry per tile
      return cache;
    })
    .finally(() => { inFlight = null; });
  return inFlight;
}

export function useGrowthTags(): GrowthTags {
  const [tags, setTags] = useState<GrowthTags>(() => cache ?? {});
  useEffect(() => {
    let alive = true;
    void fetchGrowthTags().then((t) => { if (alive) setTags(t); });
    return () => { alive = false; };
  }, []);
  return tags;
}

/** The chip text for one symbol, or null when the name is not on the board.
 *  Sales is the headline because it is the leg he named ("genuine sales"). */
export function growthChip(tags: GrowthTags, symbol: string):
    { text: string; title: string; refused: boolean } | null {
  const t = tags[(symbol || '').toUpperCase()];
  if (!t) return null;
  const s = t.sales == null ? null : `${t.sales > 0 ? '+' : ''}${Math.round(t.sales)}%`;
  const e = t.eps == null ? null : `${t.eps > 0 ? '+' : ''}${Math.round(t.eps)}%`;
  return {
    text: s ? `🚀 ${s}` : '🚀',
    refused: !!t.refused,
    title: `On the Explosive Growth board — sales ${s ?? '—'} and quarterly EPS ${e ?? '—'} year over year, with the prior quarter also growing.`
      + (t.refused
        ? ' ⛔ The trading engine will REFUSE to buy this name (under $2 a share, or a known cap under $700M).'
        : ''),
  };
}
