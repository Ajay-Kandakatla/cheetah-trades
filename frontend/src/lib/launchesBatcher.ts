/* launchesBatcher — debounced batcher that turns many parallel
   ProductLaunchesChip lookups into ONE POST /catalysts/launches/batch.

   How it works:
     1. A chip mounts, asks the batcher for `getCount(symbol)`.
     2. The batcher pushes the symbol into a pending set + returns a
        Promise that the chip awaits.
     3. After a 30ms debounce, the batcher fires ONE request with all
        queued symbols. Every awaiting Promise resolves from the response.
     4. Subsequent calls for the same symbol within `TTL_MS` are served
        from an in-memory cache (no network).

   The pattern avoids the browser's 6-concurrent-per-origin cap — what
   you saw in the network tab as a stack of "pending" rows. */

import { API } from './apiBase';

const DEBOUNCE_MS = 30;
const TTL_MS      = 5 * 60_000;   // 5 min in-memory cache per session

type Pending = {
  resolve: (count: number) => void;
  reject:  (err: unknown) => void;
};

const cache         = new Map<string, { count: number; at: number }>();
const queue         = new Set<string>();
const waiters       = new Map<string, Pending[]>();
let   flushTimer: ReturnType<typeof setTimeout> | null = null;

function fresh(at: number) { return Date.now() - at < TTL_MS; }

async function flush() {
  flushTimer = null;
  if (queue.size === 0) return;
  const symbols = Array.from(queue);
  queue.clear();
  const localWaiters = new Map(waiters);
  waiters.clear();

  try {
    const r = await fetch(`${API}/catalysts/launches/batch`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ symbols, days: 45 }),
    });
    if (!r.ok) throw new Error(`batch ${r.status}`);
    const j: { counts: Record<string, number> } = await r.json();
    for (const s of symbols) {
      const c = j.counts?.[s] ?? 0;
      cache.set(s, { count: c, at: Date.now() });
      (localWaiters.get(s) || []).forEach(w => w.resolve(c));
    }
  } catch (e) {
    // On failure, resolve everyone with 0 — chip just hides itself.
    for (const s of symbols) {
      cache.set(s, { count: 0, at: Date.now() });
      (localWaiters.get(s) || []).forEach(w => w.resolve(0));
    }
  }
}

export function getLaunchCount(symbol: string): Promise<number> {
  const key = symbol.toUpperCase().trim();
  const c = cache.get(key);
  if (c && fresh(c.at)) return Promise.resolve(c.count);

  return new Promise<number>((resolve, reject) => {
    const list = waiters.get(key) || [];
    list.push({ resolve, reject });
    waiters.set(key, list);
    queue.add(key);
    if (flushTimer == null) {
      flushTimer = setTimeout(flush, DEBOUNCE_MS);
    }
  });
}

/** Invalidate cache for one symbol — call after a manual refresh so the
 *  chip re-fetches the new count. */
export function invalidateLaunchCount(symbol: string) {
  cache.delete(symbol.toUpperCase().trim());
}
