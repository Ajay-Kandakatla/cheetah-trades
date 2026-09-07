/* useSignalWatchlist — ONE Signals watchlist for the whole app.
 *
 * Ajay 2026-09-07: "Give me options in Catalyst promo tab list for add
 * something to signals. Also same from Demand and deep demand. One click and
 * add to signals tab. Same from Gabbars and strong VCP and from Quick Bounce..
 * So I can add it to signals — signals is like my watch list."
 *
 * The Signal Lab board (Chart Maps ▸ ⚡ Signals and /signal-lab) used to own
 * the list inside its component state. Now every card's "+ Signals" button,
 * the promo list's button and the board itself read and write THIS store, so
 * a click on a Deep Demand card shows up on the Signals tab the moment it
 * opens — one implementation, one watchlist.
 *
 * Source of truth is the server (GET/POST/DELETE /day/signal-lab/watchlist,
 * per user, Mongo `signal_lab_watchlist`); localStorage mirrors it as the
 * offline fallback, exactly as the board did. The server merges the user's
 * PORTFOLIO into `symbols` and names those in `held` — held names ride the
 * board by default and cannot be removed here (they leave with the position).
 * The list holds MAX_SYMBOLS (backend daytrading/signal_lab.MAX_SYMBOLS = 12,
 * one 45-second refresh stays bounded); adding a 13th drops the oldest, on
 * both sides, so the two never disagree.
 */
import { useEffect, useSyncExternalStore } from 'react';
import { API } from '../lib/apiBase';

export const MAX_SYMBOLS = 12;
export const LS_KEY = 'signal-lab-symbols';

export type SignalWatchState = {
  loaded: boolean;
  symbols: string[];
  held: string[];
  error: string | null;
};

export function normalizeSymbol(s: string | null | undefined): string {
  return (s || '').trim().toUpperCase();
}

export function loadLocal(): string[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr.filter((s) => typeof s === 'string') : [];
  } catch { return []; }
}

export function saveLocal(syms: string[]): void {
  try { localStorage.setItem(LS_KEY, JSON.stringify(syms)); } catch { /* private mode */ }
}

/** Pure: append once, newest last, oldest dropped past `max` (the server does the same). */
export function addToList(list: string[], sym: string, max: number = MAX_SYMBOLS): string[] {
  const s = normalizeSymbol(sym);
  if (!s || list.includes(s)) return list;
  return [...list, s].slice(-max);
}

export function removeFromList(list: string[], sym: string): string[] {
  const s = normalizeSymbol(sym);
  return list.filter((x) => x !== s);
}

let _state: SignalWatchState = { loaded: false, symbols: loadLocal(), held: [], error: null };
let _inflight: Promise<void> | null = null;
const listeners = new Set<() => void>();

function emit() { listeners.forEach((fn) => fn()); }
function subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn); }; }
function getSnapshot() { return _state; }
function patch(p: Partial<SignalWatchState>) { _state = { ..._state, ...p }; emit(); }

function applyServer(j: any): void {
  if (!j || typeof j !== 'object') return;
  // Server wins once it answers; an EMPTY server list leaves the local list
  // standing (the board's rule since 2026-09-01 — a fresh browser keeps what
  // he typed while the account catches up).
  const next: Partial<SignalWatchState> = {};
  if (Array.isArray(j.symbols) && j.symbols.length) {
    next.symbols = j.symbols.filter((s: unknown) => typeof s === 'string');
    saveLocal(next.symbols as string[]);
  }
  if (Array.isArray(j.held)) next.held = j.held.filter((s: unknown) => typeof s === 'string');
  patch(next);
}

/** Fetch the account's list once per session (concurrent callers share the call). */
export function ensureLoaded(): Promise<void> {
  if (_state.loaded) return Promise.resolve();
  if (_inflight) return _inflight;
  _inflight = fetch(`${API}/day/signal-lab/watchlist`, { credentials: 'include' })
    .then((r) => (r.ok ? r.json() : null))
    .then((j) => { applyServer(j); patch({ loaded: true, error: null }); })
    .catch((e) => { patch({ loaded: true, error: String(e?.message ?? e) }); })
    .finally(() => { _inflight = null; });
  return _inflight;
}

export function addSymbol(sym: string): Promise<void> {
  const s = normalizeSymbol(sym);
  if (!s) return Promise.resolve();
  const next = addToList(_state.symbols, s);
  if (next !== _state.symbols) { saveLocal(next); patch({ symbols: next }); }
  return fetch(`${API}/day/signal-lab/watchlist/${encodeURIComponent(s)}`,
               { method: 'POST', credentials: 'include' })
    .then((r) => (r.ok ? r.json() : null))
    .then((j) => { applyServer(j); })
    .catch((e) => { patch({ error: String(e?.message ?? e) }); });   // optimistic list stands
}

export function removeSymbol(sym: string): Promise<void> {
  const s = normalizeSymbol(sym);
  if (!s) return Promise.resolve();
  const next = removeFromList(_state.symbols, s);
  saveLocal(next); patch({ symbols: next });
  return fetch(`${API}/day/signal-lab/watchlist/${encodeURIComponent(s)}`,
               { method: 'DELETE', credentials: 'include' })
    .then((r) => (r.ok ? r.json() : null))
    .then((j) => { applyServer(j); })
    .catch((e) => { patch({ error: String(e?.message ?? e) }); });
}

export function isWatched(sym: string): boolean {
  return _state.symbols.includes(normalizeSymbol(sym));
}

export function isHeld(sym: string): boolean {
  return _state.held.includes(normalizeSymbol(sym));
}

/** Tests only: forget everything (store + localStorage mirror); `seed` plays a
 *  browser that already holds a local list when the page loads. */
export function _resetSignalWatchlist(seed?: string[]): void {
  try {
    if (seed && seed.length) localStorage.setItem(LS_KEY, JSON.stringify(seed));
    else localStorage.removeItem(LS_KEY);
  } catch { /* private mode */ }
  _inflight = null;
  _state = { loaded: false, symbols: seed ? [...seed] : [], held: [], error: null };
  emit();
}

export function useSignalWatchlist() {
  const s = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  useEffect(() => { ensureLoaded(); }, []);
  return {
    loaded: s.loaded,
    symbols: s.symbols,
    held: s.held,
    error: s.error,
    full: s.symbols.length >= MAX_SYMBOLS,
    has: (sym: string) => s.symbols.includes(normalizeSymbol(sym)),
    isHeld: (sym: string) => s.held.includes(normalizeSymbol(sym)),
    add: addSymbol,
    remove: removeSymbol,
  };
}
