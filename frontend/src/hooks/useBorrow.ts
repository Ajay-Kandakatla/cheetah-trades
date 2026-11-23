/* 💸 useBorrow — GET /short-interest/borrow?symbols=A,B,C, batched (2026-11-22, spec borrow §3.3).
 *
 * Every mounted chip / label drops its symbol into a module queue; the queue flushes on a MICROTASK (never a setTimeout),
 * so every chip of one commit lands in ONE GET, fired while a test's fetch stub is still installed. Chunks of BR_CHUNK,
 * which must equal the served `max_symbols` (the backend's MAP_MAX_SYMBOLS).
 *
 * - A symbol in flight is never re-queued: a board that re-renders while a GET is pending asks ONCE.
 * - An entry's life is Math.min of BR_TTL_MS, the served retry_after_sec (clamped) and the served keep_sec (floored at
 *   BR_FOLLOWUP_MIN_MS): an `ok` answer is re-asked the moment its words would turn stale.
 * - A failure (a failed GET, or a body parseBorrow rejects) fails quiet: an existing entry keeps its read, a missing one
 *   reads null; both are back-dated so a later render retries after BR_RETRY_MS. A kept read is returned only while
 *   it is inside the served keep_sec — past it the hook returns null (computed at render, no timer).
 * - The ONLY timer: when a VALID payload says `refreshing === true`, one re-ask after the clamped served delay, at most
 *   BR_FOLLOWUP_MAX in a row; a non-refreshing answer resets the count.
 * Display only. Every word is served; this file types none. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { borrowRead, parseBorrow, BORROW_PATH, type BorrowPayload, type BorrowRead } from '../lib/borrow';

/** Must equal backend short_interest/borrow.py MAP_MAX_SYMBOLS (the served `max_symbols`). */
export const BR_CHUNK = 200;
export const BR_TTL_MS = 600000;
export const BR_RETRY_MS = 60000;
export const BR_FOLLOWUP_MAX = 2;
export const BR_FOLLOWUP_MIN_MS = 5000;
export const BR_FOLLOWUP_MAX_MS = 120000;

type Entry = { at: number; read: BorrowRead | null; okAt: number; keepMs: number; failed?: boolean };

const cache = new Map<string, Entry>();
const pending = new Set<string>();
const inflight = new Set<string>();
const mounted = new Map<string, number>();
const listeners = new Set<() => void>();
let flushQueued = false;
let followups = 0;
let timer: ReturnType<typeof setTimeout> | null = null;
let gen = 0;

function notifyAll() {
  listeners.forEach((fn) => fn());
}

/** Tests only — the module cache outlives a test's render. */
export function _resetBorrowCache(): void {
  gen += 1;
  cache.clear();
  pending.clear();
  inflight.clear();
  flushQueued = false;
  followups = 0;
  if (timer != null) clearTimeout(timer);
  timer = null;
}

const expired = (e: Entry | undefined, now: number): boolean => e == null || now - e.at >= BR_TTL_MS;

const clampDelay = (sec: number): number => Math.min(BR_FOLLOWUP_MAX_MS, Math.max(BR_FOLLOWUP_MIN_MS, sec * 1000));

/** The entry's life in ms: Math.min over BR_TTL_MS and the bounds that were served (Math.min / Math.max only). */
function lifeMs(p: BorrowPayload, keepMs: number): number {
  const bounds = [BR_TTL_MS];
  if (p.retry_after_sec != null) bounds.push(clampDelay(p.retry_after_sec));
  if (p.keep_sec != null) bounds.push(Math.max(BR_FOLLOWUP_MIN_MS, keepMs));
  return Math.min(...bounds);
}

function fetchChunk(symbols: string[]) {
  const mine = gen;
  symbols.forEach((s) => inflight.add(s));
  // Promise.resolve().then: a stub fetch that THROWS synchronously becomes a rejection here, never an uncaught error.
  Promise.resolve()
    .then(() => fetch(`${API}${BORROW_PATH}?symbols=${encodeURIComponent(symbols.join(','))}`))
    .then((r) => (r && r.ok ? r.json() : Promise.reject(new Error(String(r?.status)))))
    .then((j: unknown) => {
      if (mine !== gen) return;
      const p = parseBorrow(j);
      if (!p) throw new Error('not a borrow payload');
      const now = Date.now();
      const keepMs = Math.max(0, (p.keep_sec ?? 0) * 1000);
      const at = now - BR_TTL_MS + lifeMs(p, keepMs);
      for (const s of symbols) cache.set(s, { at, read: borrowRead(p, s), okAt: now, keepMs });
      if (!p.refreshing) {
        followups = 0;
        return;
      }
      if (timer != null || followups === BR_FOLLOWUP_MAX) return;
      followups += 1;
      timer = setTimeout(() => {
        timer = null;
        if (mine !== gen) return;
        queueFlush();
        notifyAll();
      }, clampDelay(p.retry_after_sec ?? 0));
    })
    .catch(() => {
      if (mine !== gen) return;
      // Fail quiet. An existing entry keeps its read / okAt / keepMs (the hook drops it past keepMs); a missing one reads
      // null. Back-dated so a later render retries after BR_RETRY_MS — never a hammer.
      const at = Date.now() - BR_TTL_MS + BR_RETRY_MS;
      for (const s of symbols) {
        const hit = cache.get(s);
        cache.set(s, hit ? { ...hit, at, failed: true } : { at, read: null, okAt: 0, keepMs: 0, failed: true });
      }
    })
    .finally(() => {
      if (mine !== gen) return;
      symbols.forEach((s) => inflight.delete(s));
      notifyAll();
    });
}

function flush() {
  const now = Date.now();
  const want = new Set<string>();
  // review fix 2026-11-22: a queued symbol whose chip unmounted before the microtask is never asked for.
  pending.forEach((s) => { if (mounted.has(s) && expired(cache.get(s), now)) want.add(s); });
  pending.clear();
  mounted.forEach((_n, s) => { if (expired(cache.get(s), now)) want.add(s); });
  const list = Array.from(want).filter((s) => !inflight.has(s));
  for (let i = 0; i < list.length; i += BR_CHUNK) fetchChunk(list.slice(i, i + BR_CHUNK));
}

function queueFlush() {
  if (flushQueued) return;
  flushQueued = true;
  const mine = gen;
  Promise.resolve().then(() => {
    if (mine !== gen) return;
    flushQueued = false;
    flush();
  });
}

/** The served read for one symbol. `read` null = nothing to draw (loading, not served, failed with nothing held, or a
 *  kept read past its served keep_sec); `loaded` = the cache holds an entry; `failed` = that entry is a failed request. */
export function useBorrow(symbol: string): { read: BorrowRead | null; loaded: boolean; failed: boolean } {
  const sym = (symbol || '').trim().toUpperCase();
  const [, setTick] = useState(0);

  useEffect(() => {
    const onUpdate = () => setTick((t) => t + 1);
    listeners.add(onUpdate);
    return () => { listeners.delete(onUpdate); };
  }, []);

  useEffect(() => {
    if (!sym) return undefined;
    mounted.set(sym, (mounted.get(sym) ?? 0) + 1);
    return () => {
      const n = (mounted.get(sym) ?? 0) - 1;
      if (n > 0) mounted.set(sym, n);
      else mounted.delete(sym);
    };
  }, [sym]);

  // every render: a timestamp compare; queued only when not in flight and missing or expired
  useEffect(() => {
    if (!sym || inflight.has(sym)) return;
    if (!expired(cache.get(sym), Date.now())) return;
    pending.add(sym);
    queueFlush();
  });

  const hit = sym ? cache.get(sym) : undefined;
  if (!hit) return { read: null, loaded: false, failed: false };
  const dropped = hit.failed === true && Date.now() - hit.okAt > hit.keepMs;
  return { read: dropped ? null : hit.read, loaded: true, failed: hit.failed === true };
}
