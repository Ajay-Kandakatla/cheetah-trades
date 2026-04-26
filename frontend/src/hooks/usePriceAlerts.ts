import { useCallback, useEffect, useRef, useState } from 'react';

const API = (import.meta as any).env?.VITE_API_BASE ?? 'http://localhost:8000';

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
  const u = new URL(`${API}/sepa/alerts/price`);
  u.searchParams.set('symbol', input.symbol);
  u.searchParams.set('kind', input.kind);
  u.searchParams.set('level', String(input.level));
  if (input.channels?.length) u.searchParams.set('channels', input.channels.join(','));
  if (input.note) u.searchParams.set('note', input.note);
  const r = await fetch(u, { method: 'POST' });
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
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, [tick]);

  return { latest };
}
