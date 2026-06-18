/* perfReporter — in-house Real-User-Monitoring for page-load speed.
 *
 * Ajay 2026-06-17: capture how fast pages actually paint + how the app behaves
 * on low-bandwidth connections, so we can optimize where the numbers point.
 *
 * Captures the Core Web Vitals (LCP / INP / CLS) plus FCP + TTFB via Google's
 * web-vitals lib, tags each sample with the current route AND the user's
 * CONNECTION quality (effectiveType / downlink / saveData), and ships them to
 * OUR OWN backend (/analytics/perf) via sendBeacon. No third party, no PII —
 * just timings. Best-effort: silent on any failure, never throws.
 */
import { onLCP, onINP, onCLS, onFCP, onTTFB, type Metric } from 'web-vitals';
import { API } from './apiBase';

type Sample = {
  metric: string;
  value: number;
  route: string;
  conn: string;
  downlink?: number;
  save_data?: boolean;
  session_id: string;
};

const SESSION_ID = (() => {
  try {
    const k = '__pounce_session_id';
    let s = sessionStorage.getItem(k);
    if (!s) {
      s = Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
      sessionStorage.setItem(k, s);
    }
    return s;
  } catch {
    return 'anon';
  }
})();

/** Network-quality hints from the Network Information API (where supported —
 *  Chrome/Edge/Android). The whole point of the low-internet effort, so we can
 *  split metrics by connection later. Absent → 'unknown'. */
function connInfo(): { conn: string; downlink?: number; save_data: boolean } {
  const c = (navigator as unknown as { connection?: Record<string, unknown> }).connection;
  if (!c) return { conn: 'unknown', save_data: false };
  return {
    conn: typeof c.effectiveType === 'string' ? c.effectiveType : 'unknown',
    downlink: typeof c.downlink === 'number' ? c.downlink : undefined,
    save_data: !!c.saveData,
  };
}

let queue: Sample[] = [];

function flush(): void {
  if (!queue.length) return;
  const body = JSON.stringify({ events: queue });
  queue = [];
  try {
    if (navigator.sendBeacon) {
      navigator.sendBeacon(`${API}/analytics/perf`, new Blob([body], { type: 'application/json' }));
    } else {
      fetch(`${API}/analytics/perf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true,
        credentials: 'include',
      }).catch(() => {});
    }
  } catch {
    /* RUM is non-critical — never let it surface an error */
  }
}

function record(m: Metric): void {
  try {
    queue.push({
      metric: m.name,
      value: Math.round((m.value + Number.EPSILON) * 1000) / 1000,
      route: location.pathname,
      ...connInfo(),
      session_id: SESSION_ID,
    });
  } catch {
    /* ignore a single bad sample */
  }
}

let started = false;

/** Wire the web-vitals listeners once. web-vitals reports most metrics at
 *  page-hide / bfcache, so we flush on visibilitychange→hidden + pagehide. */
export function initPerfReporting(): void {
  if (started || typeof window === 'undefined') return;
  started = true;
  try {
    onLCP(record);
    onINP(record);
    onCLS(record);
    onFCP(record);
    onTTFB(record);
    addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') flush();
    });
    addEventListener('pagehide', flush);
  } catch {
    /* if web-vitals can't attach (ancient browser), skip silently */
  }
}

/* Exposed for tests. */
export const __test = { connInfo, flush, record, getQueue: () => queue, reset: () => { queue = []; started = false; } };
