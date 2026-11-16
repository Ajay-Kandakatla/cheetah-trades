/* ➕/➖ Watch on every card — the one shared store of the owner's 👀 Gajjala's Watch names (2026-11-15).
 *
 * Ajay 2026-11-15: "can you add an add to watch list button on all the stocks to move them and also remove button from
 * watch list too."
 *
 * ONE GET per page (GET /chart-maps/gajjala-watch/symbols, concurrent callers share it), every card subscribes. The
 * server is the truth: no optimistic write — a click POSTs / DELETEs the existing routes and the answer's `symbols`
 * replaces the list. Anyone but the owner is served `owner_only` → the button renders nothing. A failing read is
 * `error` → nothing renders (an empty list would offer ➕ on a name already watched). Words are SERVED. */
import { useEffect, useSyncExternalStore } from 'react';
import { API } from './apiBase';
import { ggwSymbolPath } from './gajjalaWatch';

export const GGW_LIST_PATH = '/chart-maps/gajjala-watch/symbols';

export type GgwLabels = { add: string; remove: string; add_title: string; remove_title: string };
export type GgwListState = {
  phase: 'idle' | 'loading' | 'ok' | 'hidden';
  symbols: string[];
  full: boolean;
  full_text: string | null;
  labels: GgwLabels | null;
  busy: string | null;      // the symbol whose write is in flight
  msg: { sym: string; text: string; on: boolean } | null;   // `on` = on the list after that answer
};

const str = (x: unknown): string | null => (typeof x === 'string' && x.trim() ? x : null);

/** The served list answer → the store's fields; anything else (owner_only, error, junk) → null = hide the button. */
export function parseGgwList(j: unknown): Pick<GgwListState, 'symbols' | 'full' | 'full_text' | 'labels'> | null {
  if (!j || typeof j !== 'object') return null;
  const o = j as Record<string, unknown>;
  if (o.state !== 'ok' || !Array.isArray(o.symbols)) return null;
  const l = o.labels as Record<string, unknown> | null | undefined;
  const add = str(l?.add), remove = str(l?.remove), addT = str(l?.add_title), remT = str(l?.remove_title);
  if (!add || !remove || !addT || !remT) return null;
  return {
    symbols: o.symbols.filter((s): s is string => typeof s === 'string'),
    full: o.full === true,
    full_text: str(o.full_text),
    labels: { add, remove, add_title: addT, remove_title: remT },
  };
}

/** The backend's key (`colls.fold` → `broker_fold`): upper-case, the class separator '.' and '-' are one ticker. */
export function ggwFold(sym: string): string {
  return sym.trim().toUpperCase().split('.').join('-');
}

/** Folded membership — the server stores the house spelling (BRK.B); a card may carry BRK-B or either case. */
export function ggwHas(symbols: ReadonlyArray<string>, sym: string): boolean {
  const k = ggwFold(sym);
  return !!k && symbols.some((s) => ggwFold(s) === k);
}

/** The served title with the symbol filled in ({sym} is the only slot). */
export function ggwTitle(tpl: string, sym: string): string {
  return tpl.split('{sym}').join(sym);
}

const INITIAL: GgwListState = { phase: 'idle', symbols: [], full: false, full_text: null, labels: null, busy: null, msg: null };
let _state: GgwListState = INITIAL;
let _inflight: Promise<void> | null = null;
let _seq = 0;                                               // every read and write takes one; an older read is dropped
const listeners = new Set<() => void>();

function emit() { listeners.forEach((fn) => fn()); }
function subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn); }; }
function getSnapshot() { return _state; }
function patch(p: Partial<GgwListState>) { _state = { ..._state, ...p }; emit(); }

/** Test hook: back to a fresh page. */
export function resetGgwList(): void { _state = INITIAL; _inflight = null; _seq = 0; emit(); }

/** Read the list. Unforced: once per page, concurrent callers share the call. Forced (after a write): always a fresh
 *  GET. An answer older than the newest read or write is dropped. A served `owner_only` / `error` hides the button;
 *  a failed fetch keeps a list already shown, and before the first good read goes back to `idle` (the next mount
 *  retries) — one blip never hides every button for the life of the page. */
export function loadGgwList(force = false): Promise<void> {
  if (!force && (_inflight || _state.phase !== 'idle')) return _inflight ?? Promise.resolve();
  const my = ++_seq;
  if (_state.phase === 'idle') patch({ phase: 'loading' });
  const p: Promise<void> = Promise.resolve()
    .then(() => fetch(`${API}${GGW_LIST_PATH}`, { credentials: 'include', cache: 'no-store' }))   // a sync throw → .catch
    .then((r) => (r.ok ? r.json().then((j) => ({ served: true, j })) : { served: false, j: null }))
    .then(({ served, j }) => {
      if (my !== _seq) return;
      const parsed = served ? parseGgwList(j) : null;
      if (parsed) patch({ phase: 'ok', ...parsed });
      else if (served) patch({ phase: 'hidden', symbols: [], msg: null });
      else if (_state.phase !== 'ok') patch({ phase: 'idle' });
    })
    .catch(() => { if (my === _seq && _state.phase !== 'ok') patch({ phase: 'idle' }); })
    .finally(() => { if (_inflight === p) _inflight = null; });
  _inflight = p;
  return p;
}

/** ➕ / ➖ one name through the existing owner routes; the answer's `symbols` is the new list. Never optimistic. */
export function toggleGgw(sym: string): Promise<void> {
  const s = sym.trim();
  if (!s || _state.phase !== 'ok' || _state.busy) return Promise.resolve();
  const method = ggwHas(_state.symbols, s) ? 'DELETE' : 'POST';
  patch({ busy: s, msg: null });
  return Promise.resolve()
    .then(() => fetch(`${API}${ggwSymbolPath(s)}`, { method, credentials: 'include', cache: 'no-store' }))
    .then((r) => (r.ok ? r.json() : null))
    .then((j) => {
      const o = (j && typeof j === 'object') ? j as Record<string, unknown> : null;
      const text = str(o?.text);
      const next: Partial<GgwListState> = {};
      if (o && Array.isArray(o.symbols) && o.state !== 'error') {
        _seq += 1;                                           // a read started before this write is now stale
        next.symbols = (o.symbols as unknown[]).filter((x): x is string => typeof x === 'string');
      }
      const after = next.symbols ?? _state.symbols;
      next.msg = text ? { sym: s, text, on: ggwHas(after, s) } : null;
      patch(next);
    })
    .catch(() => { patch({ msg: null }); })
    .finally(() => {
      patch({ busy: null });
      void loadGgwList(true);                               // `full` is served by the list read, never guessed
    });
}

export function useGgwList(): GgwListState {
  const st = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  useEffect(() => { void loadGgwList(); }, []);
  return st;
}
