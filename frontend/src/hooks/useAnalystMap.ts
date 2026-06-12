/**
 * Analyst-pulse map — GET /sepa/analyst-map?symbols=A,B,C (bulk).
 *
 * Mirrors useEarningsMap's module-cache approach but the endpoint is
 * symbol-keyed, so this hook adds a shared batching queue: every caller
 * (each SEPA card calls it with one symbol) drops its unknown symbols
 * into a module-level pending set; a short debounce flushes the set in
 * chunks of 50 as single-flight requests. 10-minute per-symbol TTL;
 * misses are cached as null so they don't refetch every render.
 *
 * Book context (TLSW 2013): the ±5% revision study is p.124; the
 * 30-days-earlier trend language is p.125. The book does NOT specify
 * the lookback window for the 5% study — backend computes 30d and 90d
 * and keys the verdict off 30d (ambiguity stated in the methodology
 * doc). Display + tracking only — none of this feeds the composite
 * SEPA score.
 */
import { useEffect, useMemo, useState } from 'react';
import { API } from '../lib/apiBase';

/** TLSW p.124 — "revised upward by 5 percent or more" (both directions). */
export const REVISION_BIG_PCT = 5.0;

export type AnalystVerdict =
  | 'revisions_up_big'
  | 'trending_higher'
  | 'neutral'
  | 'red_flag'
  | 'p89_trap';

export type AnalystMapEntry = {
  verdict: AnalystVerdict;
  implied_upside_pct: number | null;
  fy_rev_30d: number | null;
  /** 'both' when current-FY AND next-FY are trending higher (the
   *  p.125 "even better" case); otherwise truthy/period-string/false. */
  trending_higher: boolean | 'both' | 'fy' | 'next_fy' | null;
  big_up: boolean;
  red_flag: boolean;
  p89_trap: boolean;
  n_actions: number;
  mean_target: number | null;
};

const TTL_MS = 10 * 60 * 1000;
const RETRY_MS = 60 * 1000;     // failed fetches become retryable after 1 min
const CHUNK = 50;               // symbols per request
const FLUSH_MS = 60;            // debounce so 200 mounting cards batch together

const cache = new Map<string, { at: number; entry: AnalystMapEntry | null }>();
const inflight = new Set<string>();
const pending = new Set<string>();
let flushTimer: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<() => void>();

function notifyAll() {
  listeners.forEach((fn) => fn());
}

function fetchChunk(symbols: string[]) {
  symbols.forEach((s) => inflight.add(s));
  fetch(`${API}/sepa/analyst-map?symbols=${encodeURIComponent(symbols.join(','))}`)
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
    .then((j: { map?: Record<string, AnalystMapEntry> }) => {
      const now = Date.now();
      const got = j.map || {};
      for (const s of symbols) {
        // Misses cached as null with full TTL — "no analyst data" is a
        // valid answer; don't re-ask for 10 minutes.
        cache.set(s, { at: now, entry: got[s] ?? null });
      }
      notifyAll();
    })
    .catch(() => {
      // Fail quiet — chips just don't render. Backdate the null entries
      // so a later mount can retry after RETRY_MS without hammering.
      const at = Date.now() - TTL_MS + RETRY_MS;
      for (const s of symbols) {
        if (!cache.has(s)) cache.set(s, { at, entry: null });
      }
    })
    .finally(() => {
      symbols.forEach((s) => inflight.delete(s));
    });
}

function scheduleFlush() {
  if (flushTimer != null) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    const want: string[] = [];
    pending.forEach((s) => {
      const hit = cache.get(s);
      const fresh = hit != null && Date.now() - hit.at < TTL_MS;
      if (!fresh && !inflight.has(s)) want.push(s);
    });
    pending.clear();
    for (let i = 0; i < want.length; i += CHUNK) {
      fetchChunk(want.slice(i, i + CHUNK));
    }
  }, FLUSH_MS);
}

/**
 * Returns the symbol→entry map for the requested symbols (uppercased
 * keys). Entries appear as the batched fetches land; absent = no data
 * (or still loading) — render nothing, per house fail-quiet rule.
 */
export function useAnalystMap(symbols: string[] | undefined): Map<string, AnalystMapEntry> {
  // Stable key — callers pass fresh array literals every render.
  const key = (symbols ?? [])
    .map((s) => (s || '').toUpperCase())
    .filter(Boolean)
    .sort()
    .join(',');
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const onUpdate = () => setTick((t) => t + 1);
    listeners.add(onUpdate);
    return () => { listeners.delete(onUpdate); };
  }, []);

  useEffect(() => {
    if (!key) return;
    let queued = false;
    for (const s of key.split(',')) {
      const hit = cache.get(s);
      if (hit && Date.now() - hit.at < TTL_MS) continue;
      if (inflight.has(s) || pending.has(s)) continue;
      pending.add(s);
      queued = true;
    }
    if (queued) scheduleFlush();
  }, [key]);

  return useMemo(() => {
    const m = new Map<string, AnalystMapEntry>();
    if (!key) return m;
    for (const s of key.split(',')) {
      const hit = cache.get(s);
      if (hit?.entry) m.set(s, hit.entry);
    }
    return m;
  }, [key, tick]);
}
