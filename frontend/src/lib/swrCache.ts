/* ==========================================================================
   swrCache — tiny localStorage-backed cache for SWR (stale-while-revalidate).

   Why:
     SEPA scan + per-ticker detail responses are both expensive to fetch
     (the SEPA scan can be 3-5MB JSON for Russell 1000) and re-fetched
     every page mount. Without a cache, every navigation shows a blank
     screen for 1-3s while the network round-trip completes.

     With this cache, mounts read the last-known value from localStorage
     and render instantly, then revalidate in the background. The UI
     gets "stale data → fresh data" instead of "blank → fresh data".

   Trade-offs:
     - localStorage is per-origin and capped at ~5-10MB in modern browsers.
       We allow up to 8MB per key, with a slim-fallback writer that
       drops the heaviest fields if the full payload exceeds the cap.
     - JSON serialization for everything — no Date objects, no Maps/Sets
       at the top level. Use plain objects.
     - Sync API (localStorage is sync) — fine for small reads, never
       call this with megabyte payloads on the render path.

   Bug history:
     v1 had a 3MB cap which was too tight — the Russell 1000 SEPA scan
     serializes to ~3.4MB, so cache writes were silently dropped and the
     page always reloaded blank. v2 lifts the cap and adds a slim writer
     that keeps the lighter `candidates` subset when the full payload
     can't fit.
   ========================================================================== */

const KEY_PREFIX = 'pounce.swr.';
const MAX_BYTES = 8 * 1024 * 1024;       // ~8 MB hard limit per key

/** Hook a debug logger so we can see why writes fail. Console-only by
 *  default — surfaces the failure mode without breaking anything. */
const DEBUG = typeof window !== 'undefined'
  && (window as any).__POUNCE_SWR_DEBUG__ === true;
function _log(msg: string, extra?: unknown) {
  if (!DEBUG) return;
  // eslint-disable-next-line no-console
  console.warn('[swrCache] ' + msg, extra);
}

export type CachedEnvelope<T> = {
  v: 1;            // schema version, bump if the envelope shape changes
  ts: number;      // ms epoch when the value was stored
  data: T;
};

/** Read a cached value. Returns null on cache miss / parse error / unsupported. */
export function readCache<T>(key: string): CachedEnvelope<T> | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(KEY_PREFIX + key);
    if (!raw) return null;
    const env = JSON.parse(raw);
    if (!env || env.v !== 1 || typeof env.ts !== 'number') return null;
    return env as CachedEnvelope<T>;
  } catch {
    return null;
  }
}

/** Slim-down strategy for over-budget payloads.
 *
 *  When the full payload exceeds MAX_BYTES (or the browser rejects it),
 *  we try one fallback: drop the heaviest known fields and re-serialize.
 *  Better to cache "candidates only" than nothing at all — the user
 *  page can still render the active list instantly while a fresh fetch
 *  re-fills the heavy `all_results` array in the background.
 *
 *  Currently strips: `all_results` (the duplicate of every analyzed
 *  ticker; the `candidates` subset is what the page renders by default).
 *  Add new heavy fields here as they show up. */
function _slim<T>(data: T): T {
  if (!data || typeof data !== 'object') return data;
  const obj = data as Record<string, unknown>;
  if ('all_results' in obj) {
    const slim = { ...obj };
    delete slim.all_results;
    (slim as any)._slim = true;  // marker so UI can show "showing slim cache"
    return slim as T;
  }
  return data;
}

/** Write a value to cache. Silently no-ops on quota errors after a
 *  slim-down attempt. */
export function writeCache<T>(key: string, data: T): void {
  if (typeof window === 'undefined') return;
  const fullKey = KEY_PREFIX + key;
  const tryWrite = (envelope: CachedEnvelope<T>): boolean => {
    try {
      const s = JSON.stringify(envelope);
      if (s.length > MAX_BYTES) {
        _log(`payload exceeds MAX_BYTES (${s.length} > ${MAX_BYTES})`, { key });
        return false;
      }
      window.localStorage.setItem(fullKey, s);
      return true;
    } catch (e) {
      _log(`localStorage.setItem threw`, { key, error: String(e) });
      return false;
    }
  };

  const ts = Date.now();
  // First attempt — full payload
  if (tryWrite({ v: 1, ts, data })) return;

  // Second attempt — drop heavy fields and try again
  const slimmed = _slim(data);
  if (slimmed !== data) {
    _log('retrying with slim payload', { key });
    if (tryWrite({ v: 1, ts, data: slimmed })) return;
  }

  // Third attempt — clear any stale entry under this key + bail
  // (better to have nothing than corrupt data)
  try { window.localStorage.removeItem(fullKey); } catch { /* ignore */ }
  _log('giving up on cache write', { key });
}

/** Drop a cache entry. Useful when we know the value is invalidated
 *  (e.g. user explicitly re-ran a scan that failed). */
export function clearCache(key: string): void {
  if (typeof window === 'undefined') return;
  try { window.localStorage.removeItem(KEY_PREFIX + key); } catch { /* ignore */ }
}

/** Human-readable age of a cached envelope, e.g. "12s ago" / "3m ago". */
export function ageHuman(envelope: { ts: number } | null | undefined): string {
  if (!envelope) return '—';
  const sec = Math.floor((Date.now() - envelope.ts) / 1000);
  if (sec < 5)   return 'just now';
  if (sec < 60)  return `${sec}s ago`;
  if (sec < 3600) return `${Math.round(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
  return `${Math.round(sec / 86400)}d ago`;
}
