/* usageTracker — fire-and-forget logger for in-page FEATURE interactions
 * (filter chips, modals, toggles) that the page-view analytics never captured.
 *
 * Page views are already tracked by usePageTracking → /analytics/event. This
 * only adds the "which controls did I actually click" signal, batched and sent
 * to /usage/track. Best-effort: no retries, silent on failure.
 */
import { API } from './apiBase';

type Ev = { kind: 'feature'; key: string; weekday: number; hour: number };

let queue: Ev[] = [];
let timer: number | null = null;
const FLUSH_MS = 6000;
const MAX_QUEUE = 20;

function flush(): void {
  if (timer != null) { window.clearTimeout(timer); timer = null; }
  if (!queue.length) return;
  const events = queue;
  queue = [];
  const body = JSON.stringify({ events });
  try {
    if (navigator.sendBeacon) {
      // sendBeacon includes same-origin cookies, so the auth gate is satisfied,
      // and it survives page unload.
      navigator.sendBeacon(`${API}/usage/track`, new Blob([body], { type: 'application/json' }));
    } else {
      fetch(`${API}/usage/track`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body, keepalive: true, credentials: 'include',
      }).catch(() => {});
    }
  } catch {
    /* analytics is non-critical */
  }
}

/** Record one feature interaction, e.g. trackFeature('sepa:filter:whales'). */
export function trackFeature(key: string): void {
  if (!key) return;
  const d = new Date();
  queue.push({ kind: 'feature', key: key.slice(0, 80), weekday: d.getDay(), hour: d.getHours() });
  if (queue.length >= MAX_QUEUE) flush();
  else if (timer == null) timer = window.setTimeout(flush, FLUSH_MS);
}

if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', flush);
  window.addEventListener('beforeunload', flush);
  window.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush();
  });
}
