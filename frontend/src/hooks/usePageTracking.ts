/* usePageTracking — fire-and-forget page-view + dwell-time logger.

   On every route change:
     1. POST /analytics/event/start → get a row id
     2. Set a periodic heartbeat (every 30s) updating duration_sec on
        the open row, so we capture "user is still here" without
        constantly creating new rows.
     3. On route change or tab close, send a final end beacon.

   Uses navigator.sendBeacon() for the final close (survives unload).
   No retries, no logging if backend is down — analytics is non-critical.
*/
import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { API } from '../lib/apiBase';

// Pick a stable session id for this tab — rotates on each refresh.
const SESSION_ID = (() => {
  try {
    const k = '__pounce_session_id';
    let s = sessionStorage.getItem(k);
    if (!s) {
      s = Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
      sessionStorage.setItem(k, s);
    }
    return s;
  } catch { return 'anon'; }
})();

/** Map a route path to a coarser module name for aggregation.
 *  /sepa/MU       → "sepa"
 *  /food          → "food"
 *  /admin/usage   → "admin"
 *  unknown        → "other" */
function routeToModule(path: string): string {
  const seg = path.replace(/^\/+/, '').split('/')[0] || 'home';
  return seg.toLowerCase();
}

const HEARTBEAT_MS = 30_000;

export function usePageTracking() {
  const loc = useLocation();
  const eventIdRef = useRef<string | null>(null);
  const startedAtRef = useRef<number>(0);

  useEffect(() => {
    let cancelled = false;
    const route = loc.pathname;
    const module = routeToModule(route);
    const started = Date.now();
    startedAtRef.current = started;

    // Start a new event row.
    fetch(`${API}/analytics/event/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ module, route, session_id: SESSION_ID }),
    })
      .then(r => r.json())
      .then(j => { if (!cancelled) eventIdRef.current = j?.id || null; })
      .catch(() => { /* analytics is best-effort */ });

    // Heartbeat — extend duration on the open row.
    const tick = () => {
      const id = eventIdRef.current;
      if (!id) return;
      const dur = Math.max(0, Math.round((Date.now() - started) / 1000));
      // POST is fine here — tab is still open, request will complete.
      fetch(`${API}/analytics/event/end`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, duration_sec: dur }),
      }).catch(() => {});
    };
    const intv = setInterval(tick, HEARTBEAT_MS);

    // Final close — send via sendBeacon so it survives unload/navigation.
    const finalClose = () => {
      const id = eventIdRef.current;
      if (!id) return;
      const dur = Math.max(0, Math.round((Date.now() - started) / 1000));
      const body = JSON.stringify({ id, duration_sec: dur });
      try {
        // sendBeacon needs the body as a Blob for JSON content-type
        const blob = new Blob([body], { type: 'application/json' });
        navigator.sendBeacon(`${API}/analytics/event/end`, blob);
      } catch {
        // Fallback to keepalive fetch
        fetch(`${API}/analytics/event/end`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body,
          keepalive: true,
        }).catch(() => {});
      }
    };

    window.addEventListener('pagehide', finalClose);
    window.addEventListener('beforeunload', finalClose);

    return () => {
      cancelled = true;
      clearInterval(intv);
      finalClose();
      window.removeEventListener('pagehide', finalClose);
      window.removeEventListener('beforeunload', finalClose);
      eventIdRef.current = null;
    };
  }, [loc.pathname]);
}
