/* useMarketGauge — singleton-cached fetch of the Pounce Market Gauge.
 *
 * The score renders both in the nav (top-right badge, on every page) and on the
 * dedicated /market-gauge page, so we share ONE fetch + a 5-minute refresh
 * across all consumers (same pattern as useMyMenu). Backend also caches 5 min,
 * so this is cheap.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type GaugeComponent = {
  key: string;
  label: string;
  value: string | number | boolean;
  points: number;
  max: number;
  basis: string;
};

export type MarketGauge = {
  generated_at: number;
  generated_at_iso: string;
  score: number;
  state: 'constructive' | 'caution' | 'risk_off';
  state_label: string;
  exposure_band: { low: number; high: number; note: string };
  components: GaugeComponent[];
  drivers: string[];
  config?: Record<string, unknown>;
  disclaimer?: string;
};

const TTL = 5 * 60 * 1000;

let _data: MarketGauge | null = null;
let _at = 0;
let _fetching = false;
const listeners = new Set<() => void>();
function notify() { listeners.forEach((fn) => fn()); }

async function fetchGauge(force = false): Promise<void> {
  if (_fetching) return;
  if (!force && _data && Date.now() - _at < TTL) return;
  _fetching = true;
  try {
    const r = await fetch(`${API}/market/gauge`);
    if (r.ok) {
      _data = (await r.json()) as MarketGauge;
      _at = Date.now();
      notify();
    }
  } catch {
    /* keep the last good value rather than flashing empty */
  } finally {
    _fetching = false;
  }
}

export function useMarketGauge(): MarketGauge | null {
  const [, setTick] = useState(0);
  useEffect(() => {
    const fn = () => setTick((t) => t + 1);
    listeners.add(fn);
    fetchGauge();
    const id = window.setInterval(() => fetchGauge(true), TTL);
    return () => { listeners.delete(fn); window.clearInterval(id); };
  }, []);
  return _data;
}
