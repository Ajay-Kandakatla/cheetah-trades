/* useFearGreed — singleton-cached fetch of CNN Business's Fear & Greed index
 * (mirrored by our backend at /market/fear-greed). Same shared-fetch pattern as
 * useMarketGauge so the dial + any badge share one request + a 5-min refresh.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type FGPrev = { value: number; rating: string; rating_label: string } | null;

export type FGComponent = {
  key: string;
  label: string;
  blurb: string;
  score: number;
  rating: string;
  rating_label: string;
};

export type FearGreed = {
  score: number | null;
  score_int: number | null;
  rating: string;
  rating_label: string;
  as_of_iso?: string;
  previous: { close: FGPrev; week: FGPrev; month: FGPrev; year: FGPrev };
  components: FGComponent[];
  history: { t: number; v: number; rating: string }[];
  source: string;
  source_url: string;
  disclaimer: string;
  generated_at?: number;
  error?: string;
};

const TTL = 5 * 60 * 1000;

let _data: FearGreed | null = null;
let _at = 0;
let _fetching = false;
const listeners = new Set<() => void>();
function notify() { listeners.forEach((fn) => fn()); }

async function fetchFG(force = false): Promise<void> {
  if (_fetching) return;
  if (!force && _data && Date.now() - _at < TTL) return;
  _fetching = true;
  try {
    const r = await fetch(`${API}/market/fear-greed`);
    if (r.ok) {
      const j = (await r.json()) as FearGreed;
      if (!j.error) { _data = j; _at = Date.now(); notify(); }
    }
  } catch {
    /* keep last good value rather than flashing empty */
  } finally {
    _fetching = false;
  }
}

export function useFearGreed(): FearGreed | null {
  const [, setTick] = useState(0);
  useEffect(() => {
    const fn = () => setTick((t) => t + 1);
    listeners.add(fn);
    fetchFG();
    const id = window.setInterval(() => fetchFG(true), TTL);
    return () => { listeners.delete(fn); window.clearInterval(id); };
  }, []);
  return _data;
}
