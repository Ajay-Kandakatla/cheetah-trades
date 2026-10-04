/* useShortInterest — GET /short-interest/map?symbols=A,B,C (bulk), batched.
 *
 * Ajay 2026-10-03: "can you add this field to all our chart maps scan. also
 * the individual tickers please". One 🩳 chip per card on every tab, so a board
 * of 24–80 tiles must cost ONE request, never one per tile.
 *
 * Mirrors useAnalystMap (module cache + shared batching queue): every chip
 * drops its symbol into a module-level pending set; a short debounce flushes
 * the set in chunks of SI_CHUNK as single-flight requests. SI_CHUNK equals the
 * backend's MAP_MAX_SYMBOLS (contract), so no chunk is ever cut server-side.
 * Misses are cached as null (a valid answer: "nothing cached for this name");
 * a failed request is cached as null with `failed: true` and back-dates its entries so a later mount retries after
 * SI_RETRY_MS without hammering. Never a per-symbol provider fetch: the
 * endpoint reads one Mongo cache, and this hook reads the endpoint.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { parseSiMap, type ShortInterestRead } from '../lib/shortInterest';

export const SI_FLUSH_MS = 60;
/** Must equal backend short_interest/read.py MAP_MAX_SYMBOLS (contract). */
export const SI_CHUNK = 200;
export const SI_TTL_MS = 600000;
export const SI_RETRY_MS = 60000;

const cache = new Map<string, { at: number; read: ShortInterestRead | null; failed?: boolean }>();
const inflight = new Set<string>();
const pending = new Set<string>();
let flushTimer: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<() => void>();

function notifyAll() {
  listeners.forEach((fn) => fn());
}

/** Tests only — the module cache outlives a test's render. */
export function _resetShortInterestCache(): void {
  cache.clear();
  inflight.clear();
  pending.clear();
  if (flushTimer != null) clearTimeout(flushTimer);
  flushTimer = null;
}

function fetchChunk(symbols: string[]) {
  symbols.forEach((s) => inflight.add(s));
  // Promise.resolve().then: a stub fetch that THROWS synchronously becomes a
  // rejection here, never an uncaught error inside the flush timer.
  Promise.resolve()
    .then(() => fetch(`${API}/short-interest/map?symbols=${encodeURIComponent(symbols.join(','))}`))
    .then((r) => (r && r.ok ? r.json() : Promise.reject(new Error(String(r?.status)))))
    .then((j: unknown) => {
      const now = Date.now();
      const got = parseSiMap(j);
      for (const s of symbols) cache.set(s, { at: now, read: got[s] ?? null });
    })
    .catch(() => {
      // Fail quiet — the chip renders nothing. Back-date so a later mount
      // retries after SI_RETRY_MS; an older good read already cached is kept
      // (its read stays, only its clock moves so a remount waits too).
      const at = Date.now() - SI_TTL_MS + SI_RETRY_MS;
      for (const s of symbols) {
        const hit = cache.get(s);
        if (!hit) cache.set(s, { at, read: null, failed: true });
        else cache.set(s, { ...hit, at: Math.max(hit.at, at) });
      }
    })
    .finally(() => {
      symbols.forEach((s) => inflight.delete(s));
      notifyAll();
    });
}

function scheduleFlush() {
  if (flushTimer != null) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    const want: string[] = [];
    pending.forEach((s) => {
      const hit = cache.get(s);
      const fresh = hit != null && Date.now() - hit.at < SI_TTL_MS;
      if (!fresh && !inflight.has(s)) want.push(s);
    });
    pending.clear();
    for (let i = 0; i < want.length; i += SI_CHUNK) {
      fetchChunk(want.slice(i, i + SI_CHUNK));
    }
  }, SI_FLUSH_MS);
}

/** The served block for one symbol. `read` null = nothing to show (loading,
 *  no record cached, or the request failed); `loaded` = the cache holds an
 *  entry for the name (a finished answer, including a back-dated failure);
 *  `failed` = that entry is a failed request, NOT a "nothing cached" answer,
 *  so the ticker page never claims there is no record when it could not ask. */
export function useShortInterest(symbol: string): { read: ShortInterestRead | null; loaded: boolean; failed: boolean } {
  const sym = (symbol || '').trim().toUpperCase();
  const [, setTick] = useState(0);

  useEffect(() => {
    const onUpdate = () => setTick((t) => t + 1);
    listeners.add(onUpdate);
    return () => { listeners.delete(onUpdate); };
  }, []);

  useEffect(() => {
    if (!sym) return;
    const hit = cache.get(sym);
    if (hit && Date.now() - hit.at < SI_TTL_MS) return;
    if (inflight.has(sym) || pending.has(sym)) return;
    pending.add(sym);
    scheduleFlush();
  }, [sym]);

  const hit = sym ? cache.get(sym) : undefined;
  return { read: hit?.read ?? null, loaded: hit != null, failed: hit?.failed === true };
}
