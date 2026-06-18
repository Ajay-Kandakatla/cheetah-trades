/* useNewFeatures — the "what's new" highlight engine.
 *
 * Reads the user's per-account SEEN set (GET /features/seen, session-cached),
 * cross-references the newFeatures registry, and exposes which features are
 * still NEW for this user. Marking seen (POST /features/seen) clears the
 * highlight + logs the first view; unseen highlights are logged as impressions
 * (POST /features/impression). Best-effort — never throws. Ajay 2026-06-18.
 */
import { useEffect, useReducer } from 'react';
import { API } from '../lib/apiBase';
import { NEW_FEATURES, isRecent, type NewFeature } from '../lib/newFeatures';

let _seen: Set<string> | null = null;       // null = not loaded yet
let _loading = false;
const _listeners = new Set<() => void>();
const _notify = () => _listeners.forEach((l) => l());

export function ensureSeenLoaded(): void {
  if (_seen || _loading) return;
  _loading = true;
  try {
    fetch(`${API}/features/seen`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : { seen: [] }))
      .then((j) => { _seen = new Set(Array.isArray(j.seen) ? j.seen : []); })
      .catch(() => { _seen = new Set(); })
      .finally(() => { _loading = false; _notify(); });
  } catch {
    _seen = new Set(); _loading = false; _notify();   // fetch unavailable (e.g. tests)
  }
}

/** Test-only: reset the module cache between cases. */
export function __resetSeenForTest(seen: string[] | null = null): void {
  _seen = seen === null ? null : new Set(seen);
  _loading = false;
  _impressionsLogged = false;
}

/** Registry entries still inside the highlight window (regardless of seen). */
function recentFeatures(now = new Date()): NewFeature[] {
  return NEW_FEATURES.filter((f) => isRecent(f.addedAt, now));
}

/** Recent + not-yet-seen by this user. */
export function unseenNewFeatures(now = new Date()): NewFeature[] {
  const seen = _seen ?? new Set<string>();
  return recentFeatures(now).filter((f) => !seen.has(f.id));
}

/** Mark a feature seen — clears its highlight everywhere + logs the first view. */
export function markFeatureSeen(id: string): void {
  if (!id) return;
  if (!_seen) _seen = new Set();
  if (_seen.has(id)) return;
  _seen.add(id);
  _notify();
  try {
    fetch(`${API}/features/seen`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ feature: id }),
    }).catch(() => { /* highlight is non-critical */ });
  } catch { /* fetch unavailable */ }
}

/** Mark every new feature that lives on `pathname` as seen (page visit = view). */
export function markRouteSeen(pathname: string): void {
  for (const f of unseenNewFeatures()) {
    if (f.route && f.route === pathname) markFeatureSeen(f.id);
  }
}

/** Log the still-unseen highlights the user is being shown (the "until I view
 *  it, log it" signal). Fire-and-forget, deduped per session. */
let _impressionsLogged = false;
export function logPendingImpressions(): void {
  if (_impressionsLogged) return;
  const pending = unseenNewFeatures().map((f) => f.id);
  if (!pending.length) return;
  _impressionsLogged = true;
  try {
    fetch(`${API}/features/impression`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ features: pending }),
    }).catch(() => {});
  } catch { /* fetch unavailable */ }
}

/** Subscribe a component to seen-set changes + expose the NEW checks. */
export function useNewFeatures() {
  const [, bump] = useReducer((n: number) => n + 1, 0);
  useEffect(() => {
    _listeners.add(bump);
    ensureSeenLoaded();
    return () => { _listeners.delete(bump); };
  }, []);

  const seen = _seen ?? new Set<string>();
  const recentIds = new Set(recentFeatures().map((f) => f.id));

  return {
    /** Is this specific feature id new + unseen? */
    isNew: (id: string) => recentIds.has(id) && !seen.has(id),
    /** Does any unseen new feature live on this route? (nav badge) */
    isNewRoute: (route?: string) =>
      !!route && unseenNewFeatures().some((f) => f.route === route),
    markSeen: markFeatureSeen,
    unseen: unseenNewFeatures(),
  };
}

// Re-export for test/consumer convenience.
export { NEW_FEATURES, isRecent };
