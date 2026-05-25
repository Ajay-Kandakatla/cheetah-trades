import { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';


export type AlertKind = 'below' | 'above' | 'drop_pct' | 'rise_pct';

export type PriceAlert = {
  _id: string;
  symbol: string;
  kind: AlertKind;
  level: number;
  created_price: number | null;
  created_at: number;
  last_fired_at: number;
  channels: string[];
  note?: string | null;
};

export type AlertFire = {
  _id: string;
  alert_id: string;
  symbol: string;
  kind: AlertKind;
  level: number;
  price: number;
  fired_at: number;
  channels: string[];
  message: string;
};

export async function createPriceAlert(input: {
  symbol: string;
  kind: AlertKind;
  level: number;
  channels?: string[];
  note?: string;
}): Promise<PriceAlert> {
  // API is a relative path ('/api') in production, which `new URL()` rejects
  // without a base. Use URLSearchParams for query construction and append.
  const params = new URLSearchParams({
    symbol: input.symbol,
    kind: input.kind,
    level: String(input.level),
  });
  if (input.channels?.length) params.set('channels', input.channels.join(','));
  if (input.note) params.set('note', input.note);
  const r = await fetch(`${API}/sepa/alerts/price?${params}`, { method: 'POST' });
  if (!r.ok) throw new Error(`createPriceAlert ${r.status}`);
  return r.json();
}

export async function listPriceAlerts(): Promise<PriceAlert[]> {
  const r = await fetch(`${API}/sepa/alerts/price`);
  if (!r.ok) throw new Error(`listPriceAlerts ${r.status}`);
  return r.json();
}

export async function deletePriceAlert(id: string): Promise<void> {
  await fetch(`${API}/sepa/alerts/price/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export async function fetchRecentFires(since: number): Promise<AlertFire[]> {
  const r = await fetch(`${API}/sepa/alerts/recent?since=${since}`);
  if (!r.ok) return [];
  const j = await r.json();
  return j.fires ?? [];
}

/**
 * Poll for new alert fires every 30s and surface them via the browser
 * Notification API. Foreground-only — only fires while the tab is open.
 * Caller is responsible for prompting Notification.requestPermission()
 * when the user adds their first alert.
 */
export function useAlertNotifier() {
  const [latest, setLatest] = useState<AlertFire[]>([]);
  const sinceRef = useRef<number>(Math.floor(Date.now() / 1000));

  const tick = useCallback(async () => {
    const since = sinceRef.current;
    const fires = await fetchRecentFires(since);
    if (fires.length === 0) return;
    sinceRef.current = Math.max(...fires.map((f) => f.fired_at), since);
    setLatest((prev) => [...fires, ...prev].slice(0, 30));

    if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
      for (const f of fires) {
        try {
          new Notification(`Cheetah · ${f.symbol}`, {
            body: f.message,
            tag: `cheetah-${f.alert_id}-${f.fired_at}`,
            icon: '/favicon.ico',
          });
        } catch {
          // ignore — some browsers throttle or block.
        }
      }
    }
  }, []);

  useEffect(() => {
    // Initial backfill — replaces the first poll. After this we trust SSE
    // for new fires; the safety-net poll catches anything missed during
    // an SSE disconnect window.
    tick();
    // Live updates via the SSE bus. Each backend alert fire publishes
    // an `alert.fired` event with the same shape this hook used to
    // synthesize from /sepa/alerts/recent.
    let cancelled = false;
    // Lazy import to avoid pulling eventBus into modules that don't
    // need it during tree-shake.
    import('../lib/eventBus').then(({ subscribe }) => {
      if (cancelled) return;
      const off = subscribe('alert.fired', (evt) => {
        const p = evt.payload as any;
        if (!p) return;
        const fire: AlertFire = {
          // The SSE payload doesn't carry the Mongo _id (we don't need
          // round-trippable identity, only dedup), so synthesize a
          // stable key from alert_id + fired_at.
          _id:      `${p.alert_id}-${p.fired_at}`,
          alert_id: p.alert_id,
          symbol:   p.symbol,
          kind:     p.kind,
          level:    p.level,
          price:    p.price,
          fired_at: p.fired_at,
          channels: p.channels || [],
          message:  p.message || '',
        };
        sinceRef.current = Math.max(fire.fired_at, sinceRef.current);
        setLatest((prev) => [fire, ...prev].slice(0, 30));

        if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
          try {
            new Notification(`Cheetah · ${fire.symbol}`, {
              body: fire.message,
              tag:  `cheetah-${fire.alert_id}-${fire.fired_at}`,
              icon: '/favicon.ico',
            });
          } catch { /* browser may throttle/block */ }
        }
      });
      // Stash the unsubscribe so the cleanup below can run it.
      (cleanup as any).off = off;
    });
    const cleanup = () => {
      cancelled = true;
      const off = (cleanup as any).off;
      if (typeof off === 'function') off();
    };

    // 5-minute safety-net poll. Was 30s — cuts /sepa/alerts/recent traffic
    // by 10× while SSE handles the live path.
    const id = setInterval(tick, 5 * 60_000);
    return () => {
      clearInterval(id);
      cleanup();
    };
  }, [tick]);

  return { latest };
}
