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
import type { GrowthArrival } from '../lib/growthArrivals';

export type GrowthTag = {
  sales?: number | null;
  eps?: number | null;
  /** The trading engine will refuse this name (sub-$2, or a known sub-$700M
   *  cap). Good sales must not make it look clean. */
  refused?: boolean;
};
export type GrowthTags = Record<string, GrowthTag>;

/** The whole `/growth/tags` response, cached once per page. Since 2026-10-12
 *  it also carries the ✨ arrivals (backend/growth/arrivals.py) — the Chart
 *  Maps strip reads them from THIS fetch, so a tab that already mounts a
 *  GrowthChip pays no extra request for the strip. */
export type GrowthTagsPayload = {
  tags: GrowthTags;
  arrivals: GrowthArrival[];
  arrivals_n: number;
  arrivals_note: string | null;
  new_days: number | null;
};

const EMPTY: GrowthTagsPayload = Object.freeze({
  tags: {}, arrivals: [], arrivals_n: 0, arrivals_note: null, new_days: null,
}) as GrowthTagsPayload;

let cache: GrowthTagsPayload | null = null;
let inFlight: Promise<GrowthTagsPayload> | null = null;

export function _resetGrowthTagsCache() {   // tests only
  cache = null;
  inFlight = null;
}

/** Normalise whatever came back; never throws. A payload without `arrivals`
 *  (an older API, an outage) yields no arrivals — never a guessed count. */
function normalise(j: unknown): GrowthTagsPayload {
  const o = (j && typeof j === 'object' ? j : {}) as Record<string, unknown>;
  const tags = (o.tags && typeof o.tags === 'object' ? o.tags : {}) as GrowthTags;
  const arrivals = Array.isArray(o.arrivals)
    ? (o.arrivals as unknown[]).filter(
        (a): a is GrowthArrival => !!a && typeof a === 'object'
          && typeof (a as GrowthArrival).symbol === 'string' && !!(a as GrowthArrival).symbol)
    : [];
  const n = typeof o.arrivals_n === 'number' && Number.isFinite(o.arrivals_n) ? o.arrivals_n : arrivals.length;
  return {
    tags,
    arrivals,
    arrivals_n: arrivals.length ? n : 0,
    arrivals_note: typeof o.arrivals_note === 'string' && o.arrivals_note ? o.arrivals_note : null,
    new_days: typeof o.new_days === 'number' && Number.isFinite(o.new_days) ? o.new_days : null,
  };
}

/** The ONE in-flight request for `/growth/tags`, shared by every chip and the
 *  arrivals strip. */
export function fetchGrowthPayload(): Promise<GrowthTagsPayload> {
  if (cache) return Promise.resolve(cache);
  if (inFlight) return inFlight;
  inFlight = fetch(`${API}/growth/tags`)
    .then((r) => (r.ok ? r.json() : {}))
    .then((j) => {
      cache = normalise(j);
      return cache;
    })
    .catch(() => {
      cache = EMPTY;         // cache the miss too: do not retry per tile
      return cache;
    })
    .finally(() => { inFlight = null; });
  return inFlight;
}

export function fetchGrowthTags(): Promise<GrowthTags> {
  return fetchGrowthPayload().then((p) => p.tags);
}

export function useGrowthTags(): GrowthTags {
  const [tags, setTags] = useState<GrowthTags>(() => cache?.tags ?? {});
  useEffect(() => {
    let alive = true;
    void fetchGrowthTags().then((t) => { if (alive) setTags(t); });
    return () => { alive = false; };
  }, []);
  return tags;
}

export type GrowthArrivalsView = {
  arrivals: GrowthArrival[];
  n: number;
  note: string | null;
  newDays: number | null;
};

function view(p: GrowthTagsPayload | null): GrowthArrivalsView {
  const q = p ?? EMPTY;
  return { arrivals: q.arrivals, n: q.arrivals_n, note: q.arrivals_note, newDays: q.new_days };
}

/** ✨ The served arrivals, from the same cached fetch. Empty on a miss or an
 *  outage; never throws. */
export function useGrowthArrivals(): GrowthArrivalsView {
  const [v, setV] = useState<GrowthArrivalsView>(() => view(cache));
  useEffect(() => {
    let alive = true;
    void fetchGrowthPayload().then((p) => { if (alive) setV(view(p)); });
    return () => { alive = false; };
  }, []);
  return v;
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
