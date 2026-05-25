/* useMyFeatures — fetch the current user's allowed feature set.
 *
 * Singleton-cached so every component (NavBar desktop + mobile, every
 * Route guard, etc.) shares one HTTP call per session. Falls back to
 * "everything on" if the fetch errors — we'd rather over-show menu
 * items to a signed-in user than nag them with a broken nav while
 * Mongo is hiccuping.
 *
 * The shape is intentionally simple: ALL signed-in users have at least
 * the default trading-focused feature set even if their /me/features
 * call fails. The backend is the real gate; this hook just decides
 * what the NavBar renders.
 */
import { useEffect, useSyncExternalStore } from 'react';
import { API } from '../lib/apiBase';

export type FeatureCatalogItem = {
  id:      string;
  label:   string;
  group:   string;
  default: boolean;
};

type FeaturesState = {
  loaded:   boolean;
  features: Set<string>;
  catalog:  FeatureCatalogItem[];
  email:    string | null;
};

/* Shared store so we don't re-fetch from every consumer. */
let _state: FeaturesState = {
  loaded:   false,
  features: new Set(),
  catalog:  [],
  email:    null,
};
const listeners = new Set<() => void>();
function notify() { listeners.forEach((fn) => fn()); }
function subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn); }; }
function snapshot(): FeaturesState { return _state; }

let _fetching = false;
async function fetchOnce() {
  if (_fetching || _state.loaded) return;
  _fetching = true;
  try {
    const r = await fetch(`${API}/me/features`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    _state = {
      loaded:   true,
      features: new Set<string>(j.features || []),
      catalog:  j.catalog || [],
      email:    j.email || null,
    };
    notify();
  } catch {
    // Permissive fallback — assume everything is allowed and let the
    // backend reject anything that shouldn't be. Prevents a flaky network
    // from accidentally locking the user out of their own nav.
    _state = { loaded: true, features: new Set(), catalog: [], email: null };
    notify();
  } finally {
    _fetching = false;
  }
}

/** Force a re-fetch — used after the admin saves changes so the
 *  current user (likely the admin reviewing their own row) sees the
 *  new state immediately. */
export function refreshMyFeatures() {
  _state = { ..._state, loaded: false };
  fetchOnce();
}

/** Hook: subscribe to the feature set. Triggers a fetch on first mount
 *  if not already loaded. */
export function useMyFeatures(): FeaturesState {
  const state = useSyncExternalStore(subscribe, snapshot, snapshot);
  useEffect(() => {
    if (!state.loaded && !_fetching) fetchOnce();
  }, [state.loaded]);
  return state;
}

/** Convenience predicate. While the fetch is in flight, returns true
 *  (permissive) so the nav doesn't flash empty during the first mount. */
export function hasFeatureOrLoading(state: FeaturesState, id: string): boolean {
  if (!state.loaded) return true;
  return state.features.has(id);
}
