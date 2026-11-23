/* 🔒 useRegSho — ONE GET /short-interest/reg-sho for the whole page (2026-11-22, spec htb §3.3).
 *
 * The served payload is the WHOLE list (~150 names), so every chip on a board reads the same module cache: N mounted
 * chips cost ONE request, called with the URL only (the useShortInterest precedent). No query string.
 *
 * - A failed request, or a body parseRegSho rejects, is cached as `failed` and back-dated, so a later render retries
 *   after RS_RETRY_MS — never a hammer. With nothing held a failed GET draws nothing; a failed REFETCH keeps the last
 *   valid payload (2026-11-22 refix: one failed GET after the TTL, e.g. an api restart, no longer wipes every tag).
 * - The TTL is checked in an effect on every render (a timestamp compare), so a tab left open picks up the next list;
 *   there is no interval.
 * - A timer exists ONLY when a VALID payload says `refreshing === true`: one re-GET after the served `retry_after_sec`
 *   (clamped to RS_FOLLOWUP_MIN_MS … RS_FOLLOWUP_MAX_MS), at most RS_FOLLOWUP_MAX in a row. No valid payload → no timer.
 * - A payload that still says `refreshing` after the follow-ups is kept for RS_RETRY_MS, not RS_TTL_MS, so an empty
 *   "still reading" answer never sits in the cache for ten minutes.
 * Display only. Every word is served; this file types none. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { parseRegSho, regShoTag, REG_SHO_PATH, type RegShoPayload, type RegShoTag } from '../lib/regSho';

export const RS_TTL_MS = 600000;
export const RS_RETRY_MS = 60000;
export const RS_FOLLOWUP_MAX = 2;
export const RS_FOLLOWUP_MIN_MS = 5000;
export const RS_FOLLOWUP_MAX_MS = 120000;

type Entry = { at: number; payload: RegShoPayload | null; failed: boolean };

let entry: Entry | null = null;
let inflight = false;
let followups = 0;
let timer: ReturnType<typeof setTimeout> | null = null;
let gen = 0;
const listeners = new Set<() => void>();

function notifyAll() {
  listeners.forEach((fn) => fn());
}

/** Tests only — the module cache outlives a test's render. */
export function _resetRegShoCache(): void {
  gen += 1;
  entry = null;
  inflight = false;
  followups = 0;
  if (timer != null) clearTimeout(timer);
  timer = null;
}

/** The served delay in ms, clamped to the two bounds (Math.min / Math.max — no compare on the served field). */
function followupDelay(p: RegShoPayload): number {
  const ms = (p.retry_after_sec ?? 0) * 1000;
  return Math.min(RS_FOLLOWUP_MAX_MS, Math.max(RS_FOLLOWUP_MIN_MS, ms));
}

function fetchNow() {
  if (inflight) return;
  inflight = true;
  const mine = gen;
  // Promise.resolve().then: a stub fetch that THROWS synchronously becomes a rejection here, never an uncaught error.
  Promise.resolve()
    .then(() => fetch(`${API}${REG_SHO_PATH}`))
    .then((r) => (r && r.ok ? r.json() : Promise.reject(new Error(String(r?.status)))))
    .then((j: unknown) => {
      if (mine !== gen) return;
      const p = parseRegSho(j);
      if (!p) throw new Error('not a reg-sho payload');
      const now = Date.now();
      if (!p.refreshing) {
        followups = 0;
        entry = { at: now, payload: p, failed: false };
        return;
      }
      // still reading: kept for RS_RETRY_MS only (back-dated), plus at most RS_FOLLOWUP_MAX timed re-GETs in a row
      entry = { at: now - RS_TTL_MS + RS_RETRY_MS, payload: p, failed: false };
      if (followups === RS_FOLLOWUP_MAX) return;
      followups += 1;
      timer = setTimeout(() => {
        timer = null;
        if (mine === gen) fetchNow();
      }, followupDelay(p));
    })
    .catch(() => {
      if (mine !== gen) return;
      // Fail quiet. A failed REFETCH keeps the last valid payload (the useShortInterest precedent: an api restart never
      // wipes the tags); a failure with nothing held draws nothing. Back-dated so a later render retries after RS_RETRY_MS.
      entry = { at: Date.now() - RS_TTL_MS + RS_RETRY_MS, payload: entry?.payload ?? null, failed: true };
    })
    .finally(() => {
      if (mine !== gen) return;
      inflight = false;
      notifyAll();
    });
}

/** The page's ONE payload. `payload` null = nothing to show (loading, failed, rejected body); `loaded` = the cache holds
 *  a finished answer; `failed` = that answer is a failed request. */
export function useRegShoPayload(): { payload: RegShoPayload | null; loaded: boolean; failed: boolean } {
  const [, setTick] = useState(0);

  useEffect(() => {
    const onUpdate = () => setTick((t) => t + 1);
    listeners.add(onUpdate);
    return () => { listeners.delete(onUpdate); };
  }, []);

  // every render: a timestamp compare; a GET only when nothing is cached or the cached answer has expired
  useEffect(() => {
    if (inflight || timer != null) return;
    if (entry && Date.now() - entry.at < RS_TTL_MS) return;
    followups = 0;
    fetchNow();
  });

  return { payload: entry?.payload ?? null, loaded: entry != null, failed: entry?.failed === true };
}

/** The served tag for one symbol (exact key), or null. */
export function useRegSho(symbol: string): { tag: RegShoTag | null; loaded: boolean; failed: boolean } {
  const { payload, loaded, failed } = useRegShoPayload();
  return { tag: regShoTag(payload, symbol), loaded, failed };
}
