/* 🧹 ggFold — the one remembered open / closed store behind the ⓘ folds on 🚩 Gajjala's landing (2026-11-24, ggclean spec §3.1).
 *
 * Ajay 2026-11-24, three messages with screenshots:
 *   "Hide all of this nouce besides the scan button and log trade button no explantions on the landing pages anymor"
 *   "Add all of this too"
 *   "Collapse all of this too"
 *
 * One flag per key in localStorage (`gg-fold:` + key; '1' = open). Absent, junk ('0', 'true', 'open', '') or blocked
 * storage = CLOSED (GG_FOLD_DEFAULT_OPEN). Read once per key per page into a module cache; every hook on one key moves
 * together in the same document (useSyncExternalStore + module listeners, the ggWatchList.ts pattern). A blocked
 * setItem still toggles for the visit (the cache holds it). No `storage` event listener — cross-tab sync was not asked.
 * Keys written: `gg-fold:header`, `gg-fold:sub:<sub>`. Nothing here is served text: storage keys and the four served
 * scan-answer state keys only. */
import { useCallback, useSyncExternalStore } from 'react';

export const GG_FOLD_LS = 'gg-fold:';            // + key; '1' = open; absent / junk / blocked storage = CLOSED
export const GG_FOLD_HEADER = 'header';
export const GG_FOLD_SUB = 'sub:';               // + the sub key (bull_flag … high_si, all_strategies)
export const GG_FOLD_DEFAULT_OPEN = false;       // Ajay 2026-11-24: hidden by default

/** The sub's own fold key, or null (no sub → no fold). */
export const ggFoldSubKey = (sub: string | null | undefined): string | null =>
  (typeof sub === 'string' && sub ? `${GG_FOLD_SUB}${sub}` : null);

const OPEN = '1';
const SHUT = '0';

/** The stored flag: '1' → open, '0' → closed, anything else / blocked storage → GG_FOLD_DEFAULT_OPEN. */
export function readGgFold(key: string): boolean {
  try {
    const v = localStorage.getItem(GG_FOLD_LS + key);
    if (v === OPEN) return true;
    if (v === SHUT) return false;
    return GG_FOLD_DEFAULT_OPEN;
  } catch {
    return GG_FOLD_DEFAULT_OPEN;
  }
}

/** Best effort — private mode and blocked storage are fine (the cache keeps the visit's state). */
export function writeGgFold(key: string, open: boolean): void {
  try {
    localStorage.setItem(GG_FOLD_LS + key, open ? OPEN : SHUT);
  } catch {
    /* storage blocked — the fold still toggles for this visit */
  }
}

const cache = new Map<string, boolean>();
const listeners = new Set<() => void>();

function emit() { listeners.forEach((fn) => fn()); }
function subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn); }; }
function openOf(key: string): boolean {
  const hit = cache.get(key);
  if (hit !== undefined) return hit;
  const v = readGgFold(key);
  cache.set(key, v);
  return v;
}

/** Cache + write + emit: every hook on `key` re-renders. */
export function setGgFold(key: string, open: boolean): void {
  cache.set(key, open);
  writeGgFold(key, open);
  emit();
}

export type GgFoldState = { on: boolean; open: boolean; toggle: () => void };

/** The fold on `key`. A null key = no fold here: `on` false, `open` true (the text shows as today), toggle writes nothing. */
export function useGgFold(key: string | null): GgFoldState {
  const getSnap = useCallback(() => (key === null ? true : openOf(key)), [key]);
  const open = useSyncExternalStore(subscribe, getSnap, getSnap);
  const toggle = useCallback(() => { if (key !== null) setGgFold(key, !openOf(key)); }, [key]);
  return { on: key !== null, open, toggle };
}

/** Test hook: drop the cache (the next ask re-reads storage) and re-render every subscriber. */
export function resetGgFold(): void { cache.clear(); emit(); }

/* [fixed: C1] The answers to the scan ON OPEN that fold with the header. Served state keys
 * (on_demand.py:202-224 → GgScanResponse.state, lib/gajjala.ts:1230), never words. 'refused' (incl. the store
 * error, on_demand.py:336-342) and anything unknown stay OUT of the fold. */
export const GG_FOLD_SCAN_ON_OPEN: readonly string[] = ['started', 'waiting', 'reused', 'closed'];

/** True only for one of the four served state keys above (exact, case-sensitive); anything else → false. */
export function ggFoldScanAnswer(state: unknown): boolean {
  return typeof state === 'string' && GG_FOLD_SCAN_ON_OPEN.includes(state);
}
