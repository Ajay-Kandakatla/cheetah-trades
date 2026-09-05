/* NewFeatureWatcher — mounted once near the app root. Loads the user's seen
 * set, logs the unseen new-feature highlights they're shown (analytics), and
 * marks a route's features seen once they've dwelled on the page. Renders
 * nothing. Ajay 2026-06-18. */
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { ensureSeenLoaded, logPendingImpressions, markRouteSeen } from '../hooks/useNewFeatures';

/** How long the user must stay on a page before its new features count as seen
 *  (so a quick bounce-through doesn't silently clear the highlight). */
const DWELL_MS = 2500;

export function NewFeatureWatcher() {
  const loc = useLocation();

  // Once per session: load seen set, then log the unseen highlights as
  // impressions (the "until I view it, log it" signal).
  useEffect(() => {
    ensureSeenLoaded();
    const t = setTimeout(logPendingImpressions, 2000);
    return () => clearTimeout(t);
  }, []);

  // Dwelling on a page = viewing whatever's new there → clear its highlight.
  // Pathname + search: tab-shaped features ('/chart-maps?tab=catalysts') are
  // only "viewed" on their own tab (hooks/useNewFeatures.routeMatchesLocation).
  useEffect(() => {
    const t = setTimeout(() => markRouteSeen(loc.pathname + loc.search), DWELL_MS);
    return () => clearTimeout(t);
  }, [loc.pathname, loc.search]);

  return null;
}
