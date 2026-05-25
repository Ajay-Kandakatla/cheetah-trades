/* eventBus — singleton SSE client.
 *
 * One persistent EventSource for the whole tab. Components subscribe
 * to event types they care about; the bus dispatches each incoming
 * frame to matching handlers.
 *
 * Why a singleton: EventSource counts against the browser's 6-per-
 * origin connection cap. We want exactly one stream open regardless
 * of how many components are subscribed.
 *
 * Reconnect: EventSource handles this automatically with a 3s default
 * delay. We override the readyState transitions only to log + emit a
 * synthetic `bus.connected` / `bus.disconnected` event that the UI
 * can render if useful.
 *
 * Replaces per-resource polls (e.g. /catalysts/alerts/recent every
 * 30s). Backend events live in backend/events/. Event types are free-
 * form strings; payload shapes are documented at the publish site.
 */
import { useEffect } from 'react';
import { API } from './apiBase';

export type BusEvent<T = any> = {
  type:    string;
  ts:      number;
  payload: T;
};

type Handler = (evt: BusEvent) => void;

const handlers = new Map<string, Set<Handler>>();
let   source: EventSource | null = null;
let   started = false;

/** Track which event types we've attached native listeners for, so we
 *  add at most one EventSource listener per type even when many React
 *  components subscribe to the same type. */
const wiredTypes = new Set<string>();

function ensureSource() {
  // Idempotent — start() may be called from many components on mount.
  if (started) return;
  started = true;

  source = new EventSource(`${API}/events`);

  source.onopen = () => {
    // Helpful in DevTools; harmless in prod.
    console.debug('[eventBus] connected');
  };
  source.onerror = () => {
    // EventSource auto-retries; nothing to do here except log. The
    // readyState will be CONNECTING (0) while it reconnects.
    console.debug('[eventBus] disconnected, EventSource will retry');
  };

  // Wire any types that were subscribed BEFORE the source existed.
  for (const t of handlers.keys()) wireType(t);
}

function wireType(type: string) {
  if (!source || wiredTypes.has(type)) return;
  wiredTypes.add(type);
  // SSE dispatches by the `event:` line. The backend sets it to the
  // bus event type, so we can attach native listeners per type and
  // avoid a `switch` on every frame.
  source.addEventListener(type, (e: MessageEvent) => {
    let evt: BusEvent;
    try {
      evt = JSON.parse(e.data);
    } catch {
      return;
    }
    const set = handlers.get(type);
    if (!set) return;
    for (const fn of set) {
      try { fn(evt); } catch (err) { console.error('[eventBus] handler error', err); }
    }
  });
}

/** Subscribe to one event type. Returns an unsubscribe fn. Safe to
 *  call before the connection is open — pending subscriptions are
 *  wired when ensureSource() runs. */
export function subscribe(type: string, fn: Handler): () => void {
  let set = handlers.get(type);
  if (!set) {
    set = new Set();
    handlers.set(type, set);
  }
  set.add(fn);
  ensureSource();
  wireType(type);

  return () => {
    const s = handlers.get(type);
    if (!s) return;
    s.delete(fn);
    if (s.size === 0) handlers.delete(type);
    // We intentionally do NOT remove the native listener — the
    // overhead of a listener with no Set members is one Map lookup
    // per frame. Keeps the wire-up simple and the unsubscribe path
    // O(1) without any teardown race.
  };
}

/** React-friendly wrapper. Subscribes on mount, unsubscribes on unmount.
 *  The handler is captured in a ref via the deps array, so callers don't
 *  need to memoize it themselves for the common case. */
export function useBusEvent<T = any>(
  type: string,
  handler: (evt: BusEvent<T>) => void,
  deps: React.DependencyList = [],
) {
  useEffect(() => {
    return subscribe(type, handler as Handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type, ...deps]);
}

/* ------------------------------------------------------------------ *
 * Symbol-interest registry
 *
 * Pages call `registerSymbolInterest(symbols)` when they mount with a
 * set of tickers they want live quotes for. We dedupe across pages,
 * debounce, and POST the union to /events/subscribe so the backend
 * adds them to the Finnhub WS feed.
 *
 * No unregister path — symbol set on the backend is monotonic for the
 * duration of the session (cap is enforced server-side at 300). Cost
 * of leaving a stale symbol subscribed is one stream of unused frames
 * that React components ignore. Cheap.
 * ------------------------------------------------------------------ */
const interestedSymbols = new Set<string>();
let interestFlushTimer: ReturnType<typeof setTimeout> | null = null;
const INTEREST_DEBOUNCE_MS = 80;

async function flushInterest() {
  interestFlushTimer = null;
  // Send the FULL current set, not just the delta — keeps the protocol
  // idempotent and resilient to backend restarts (which would wipe
  // tracked_symbols and need a re-register on next interest change).
  const symbols = Array.from(interestedSymbols);
  if (!symbols.length) return;
  try {
    await fetch(`${API}/events/subscribe`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ symbols }),
    });
  } catch {
    // Network blip — next interest update retries automatically.
    // If the user just sits there with stale symbols, the SSE itself
    // is unaffected; only fresh tickers won't push until next call.
  }
}

/** Add symbols to the live-stream registration. Safe to call on every
 *  mount/render — debounced and deduped. The SSE connection itself is
 *  unaffected; this only tells the backend which symbols should fan
 *  out via `quote.update`. */
export function registerSymbolInterest(symbols: string[]) {
  let added = false;
  for (const raw of symbols) {
    if (!raw) continue;
    const s = raw.toUpperCase().trim();
    if (!s || interestedSymbols.has(s)) continue;
    interestedSymbols.add(s);
    added = true;
  }
  // Ensure the stream itself is up — without it, registering is moot.
  ensureSource();
  if (!added) return;
  if (interestFlushTimer == null) {
    interestFlushTimer = setTimeout(flushInterest, INTEREST_DEBOUNCE_MS);
  }
}
