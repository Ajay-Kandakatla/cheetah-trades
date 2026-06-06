/* useMyMenu — singleton-cached fetch of the backend-built nav menu.
 *
 * Replaces the hardcoded PRIMARY/SECONDARY/PROFILE arrays in NavBar.
 * The backend (/me/menu, in backend/access/api.py) builds the menu
 * from the FEATURE_CATALOG filtered by the caller's accessible
 * features, so the menu is GUARANTEED to never surface a link the
 * user can't reach. No more "click misc → 404."
 *
 * Cache strategy: same singleton-with-listeners pattern as useMyFeatures.
 * One HTTP call per session, shared across NavBar (desktop + mobile)
 * and any future menu consumers.
 */
import { useEffect, useSyncExternalStore } from 'react';
import { API } from '../lib/apiBase';

export type MenuItem = {
  to:       string;
  label:    string;
  /** Catalog feature id for non-admin items; absent for admin entries
   *  (admin routes are gated by the server-side ``is_admin`` flag from
   *  /auth/me, not by feature flags). */
  feature?: string;
};

export type Menu = {
  primary:  MenuItem[];
  scanners: MenuItem[];
  misc:     MenuItem[];
  profile:  MenuItem[];
  admin:    MenuItem[];
  is_owner: boolean;
  is_admin: boolean;
};

type MenuState = {
  loaded: boolean;
  menu:   Menu;
};

const EMPTY_MENU: Menu = {
  primary:  [],
  scanners: [],
  misc:     [],
  profile:  [],
  admin:    [],
  is_owner: false,
  is_admin: false,
};

let _state: MenuState = { loaded: false, menu: EMPTY_MENU };

const listeners = new Set<() => void>();
function notify() { listeners.forEach((fn) => fn()); }
function subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn); }; }
function snapshot(): MenuState { return _state; }

let _fetching = false;
async function fetchOnce() {
  if (_fetching || _state.loaded) return;
  _fetching = true;
  try {
    const r = await fetch(`${API}/me/menu`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = (await r.json()) as Menu;
    _state = { loaded: true, menu: { ...EMPTY_MENU, ...j } };
    notify();
  } catch {
    // Don't broadcast a guess — if the menu fetch fails we leave the
    // nav empty rather than surfacing items the user can't reach.
    // This is the inverse of useMyFeatures' permissive fallback: the
    // *menu* is supposed to be the safe-by-construction surface, and
    // a transient network blip showing nothing for a second beats
    // showing trade signals to a friend.
    _state = { loaded: true, menu: EMPTY_MENU };
    notify();
  } finally {
    _fetching = false;
  }
}

/** Force a re-fetch — handy after the admin saves an access change
 *  so the affected user sees the new menu without reloading. */
export function refreshMyMenu() {
  _state = { ..._state, loaded: false };
  fetchOnce();
}

export function useMyMenu(): MenuState {
  const state = useSyncExternalStore(subscribe, snapshot, snapshot);
  useEffect(() => {
    if (!state.loaded && !_fetching) fetchOnce();
  }, [state.loaded]);
  return state;
}
