/* useMarketIv — singleton-cached fetch of the implied-volatility read.
 *
 * The IV badge renders in the nav (beside the Market Gauge, on every page) and
 * as a card on /market-gauge, so we share ONE fetch + a 3-minute refresh across
 * all consumers — the same shape as useMarketGauge (module cache, subscribe /
 * notify, refetch on TTL). The backend caches too, so this is cheap.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type IvRegime = 'calm' | 'normal' | 'elevated' | 'stress';
export type IvTermShape = 'contango' | 'backwardation' | 'flat';

export type IvTerm = {
  vix9d: number | null;
  vix3m: number | null;
  ratio_9d_30d: number | null;
  ratio_30d_3m: number | null;
  shape: IvTermShape | null;
  as_of?: string | null;
  /* 2026-09-06: live SPY curve from the option chain (source "spy_chain") —
   * ATM IV in % at 9 / 30 / 90 days. Absent on the CBOE fallback, which then
   * carries `stale` when its series stopped updating at the source. */
  source?: string | null;
  source_label?: string | null;
  iv9d?: number | null;
  iv30d?: number | null;
  iv90d?: number | null;
  ratio_30d_90d?: number | null;
  underlying?: number | null;
  stale?: boolean | null;
};

export type MarketIv = {
  vix: number | null;
  prev: number | null;
  chg: number | null;
  chg_pct: number | null;
  /** Where today's VIX sits in the last 252 sessions, 0-100. */
  pct_252: number | null;
  regime: IvRegime | null;
  regime_label: string | null;
  bands: { calm_below: number; normal_below: number; elevated_below: number } | null;
  term: IvTerm | null;
  vvix: number | null;
  as_of: string | null;          // YYYY-MM-DD
  read: string;
  generated_at: number;
  age_sec: number;
  disclaimer: string;
};

const TTL = 3 * 60 * 1000;

let _data: MarketIv | null = null;
let _at = 0;
let _fetching = false;
const listeners = new Set<() => void>();
function notify() { listeners.forEach((fn) => fn()); }

async function fetchIv(force = false): Promise<void> {
  if (_fetching) return;
  if (!force && _data && Date.now() - _at < TTL) return;
  _fetching = true;
  try {
    const r = await fetch(`${API}/market/iv`);
    if (r.ok) {
      _data = (await r.json()) as MarketIv;
      _at = Date.now();
      notify();
    }
  } catch {
    /* keep the last good value rather than flashing empty */
  } finally {
    _fetching = false;
  }
}

export function useMarketIv(): MarketIv | null {
  const [, setTick] = useState(0);
  useEffect(() => {
    const fn = () => setTick((t) => t + 1);
    listeners.add(fn);
    fetchIv();
    const id = window.setInterval(() => fetchIv(true), TTL);
    return () => { listeners.delete(fn); window.clearInterval(id); };
  }, []);
  return _data;
}
