/* ⛔ useSsr — GET /short-interest/ssr?symbols=A,B,C, batched (2026-11-23, spec ssr §3.10; useBorrow.ts re-keyed).
 *
 * Ajay 2026-11-23: "No shorting at the bid (SEC short-sale restriction)
 * Can we check or this for other stocks too?"
 *
 * Every mounted chip / label drops its symbol into a module queue; the queue flushes on a MICROTASK (never a setTimeout),
 * so every chip of one commit lands in ONE GET, fired while a test's fetch stub is still installed. Chunks of SSR_CHUNK,
 * which must equal the served `max_symbols` (the backend's MAP_MAX_SYMBOLS).
 *
 * - A symbol in flight is never re-queued: a board that re-renders while a GET is pending asks ONCE.
 * - An entry's life is Math.min of SSR_TTL_MS, the served retry_after_sec (clamped) and the served keep_sec (floored at
 *   SSR_FOLLOWUP_MIN_MS): an answer is re-asked the moment its words would turn stale.
 * - A failure (a failed GET, or a body parseSsr rejects) fails quiet: an existing entry keeps its read, a missing one
 *   reads null; both are back-dated so a later render retries after SSR_RETRY_MS. A kept read is returned only while it
 *   is inside the served keep_sec — past it the hook returns null (computed at render, no timer).
 * - The ONLY timer: when a VALID payload says `refreshing === true`, one re-ask after the clamped served delay, at most
 *   SSR_FOLLOWUP_MAX in a row; a non-refreshing answer resets the count.
 * - useSsrFault(): the newest VALID payload's served fault_text (module state); a later valid payload without one clears
 *   it; a failed request leaves it as it was.
 * Display only. Every word is served; this file types none. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { parseSsr, ssrRead, SSR_PATH, type SsrPayload, type SsrRead } from '../lib/ssr';

/** Must equal backend short_interest/read.py MAP_MAX_SYMBOLS (the served `max_symbols`). */
export const SSR_CHUNK = 200;
export const SSR_TTL_MS = 300000;
export const SSR_RETRY_MS = 60000;
export const SSR_FOLLOWUP_MAX = 2;
export const SSR_FOLLOWUP_MIN_MS = 5000;
export const SSR_FOLLOWUP_MAX_MS = 120000;

type Entry = { at: number; read: SsrRead | null; okAt: number; keepMs: number; failed?: boolean };

const cache = new Map<string, Entry>();
const pending = new Set<string>();
const inflight = new Set<string>();
const mounted = new Map<string, number>();
const listeners = new Set<() => void>();
let flushQueued = false;
let followups = 0;
let timer: ReturnType<typeof setTimeout> | null = null;
let gen = 0;
let faultText: string | null = null;

function notifyAll() {
  listeners.forEach((fn) => fn());
}

/** Tests only — the module cache outlives a test's render. */
export function _resetSsrCache(): void {
  gen += 1;
  cache.clear();
  pending.clear();
  inflight.clear();
  flushQueued = false;
  followups = 0;
  faultText = null;
  if (timer != null) clearTimeout(timer);
  timer = null;
}

const expired = (e: Entry | undefined, now: number): boolean => e == null || now - e.at >= SSR_TTL_MS;

const clampDelay = (sec: number): number => Math.min(SSR_FOLLOWUP_MAX_MS, Math.max(SSR_FOLLOWUP_MIN_MS, sec * 1000));

/** The entry's life in ms: Math.min over SSR_TTL_MS and the bounds that were served (Math.min / Math.max only). */
function lifeMs(p: SsrPayload, keepMs: number): number {
  const bounds = [SSR_TTL_MS];
  if (p.retry_after_sec != null) bounds.push(clampDelay(p.retry_after_sec));
  if (p.keep_sec != null) bounds.push(Math.max(SSR_FOLLOWUP_MIN_MS, keepMs));
  return Math.min(...bounds);
}

function fetchChunk(symbols: string[]) {
  const mine = gen;
  symbols.forEach((s) => inflight.add(s));
  // Promise.resolve().then: a stub fetch that THROWS synchronously becomes a rejection here, never an uncaught error.
  Promise.resolve()
    .then(() => fetch(`${API}${SSR_PATH}?symbols=${encodeURIComponent(symbols.join(','))}`))
    .then((r) => (r && r.ok ? r.json() : Promise.reject(new Error(String(r?.status)))))
    .then((j: unknown) => {
      if (mine !== gen) return;
      const p = parseSsr(j);
      if (!p) throw new Error('not an ssr payload');
      faultText = p.fault_text;
      const now = Date.now();
      const keepMs = Math.max(0, (p.keep_sec ?? 0) * 1000);
      const at = now - SSR_TTL_MS + lifeMs(p, keepMs);
      for (const s of symbols) cache.set(s, { at, read: ssrRead(p, s), okAt: now, keepMs });
      if (!p.refreshing) {
        followups = 0;
        return;
      }
      if (timer != null || followups === SSR_FOLLOWUP_MAX) return;
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
      // null. Back-dated so a later render retries after SSR_RETRY_MS — never a hammer.
      const at = Date.now() - SSR_TTL_MS + SSR_RETRY_MS;
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
  // a queued symbol whose chip unmounted before the microtask is never asked for.
  pending.forEach((s) => { if (mounted.has(s) && expired(cache.get(s), now)) want.add(s); });
  pending.clear();
  mounted.forEach((_n, s) => { if (expired(cache.get(s), now)) want.add(s); });
  const list = Array.from(want).filter((s) => !inflight.has(s));
  for (let i = 0; i < list.length; i += SSR_CHUNK) fetchChunk(list.slice(i, i + SSR_CHUNK));
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

function useTick() {
  const [, setTick] = useState(0);
  useEffect(() => {
    const onUpdate = () => setTick((t) => t + 1);
    listeners.add(onUpdate);
    return () => { listeners.delete(onUpdate); };
  }, []);
}

/** The served read for one symbol. `read` null = nothing to draw (loading, not served, failed with nothing held, or a
 *  kept read past its served keep_sec); `loaded` = the cache holds an entry; `failed` = that entry is a failed request. */
export function useSsr(symbol: string): { read: SsrRead | null; loaded: boolean; failed: boolean } {
  const sym = (symbol || '').trim().toUpperCase();
  useTick();

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

/** The newest valid payload's served fault_text, or null. Asks nothing on its own: the chips on the page do. */
export function useSsrFault(): string | null {
  useTick();
  return faultText;
}
