/* useMacroIndicators — singleton-cached fetch of the FRED macro dashboard
 * (/market/macro-indicators): CPI & Core CPI (YoY), unemployment, Fed funds and
 * the 10y-3m curve, each with a trend + next-release date. 30-min refresh — the
 * underlying FRED data updates daily at most.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type MacroIndicator = {
  id: string;
  label: string;
  blurb: string;
  series: string;
  unit: string;
  good: 'up' | 'down' | 'neutral';
  transform: 'yoy' | 'level';
  value: number;
  prev: number | null;
  change: number | null;
  direction: 'up' | 'down' | 'flat';
  as_of: string;
  as_of_label: string;
  trend: number[];
  next_release: string | null;
  next_release_label: string | null;
};

export type MacroIndicators = {
  generated_at: number;
  generated_at_iso: string;
  indicators: MacroIndicator[];
  fred_available: boolean;
  disclaimer: string;
};

const TTL = 30 * 60 * 1000;

let _data: MacroIndicators | null = null;
let _at = 0;
let _fetching = false;
const listeners = new Set<() => void>();
function notify() { listeners.forEach((fn) => fn()); }

async function fetchMacro(force = false): Promise<void> {
  if (_fetching) return;
  if (!force && _data && Date.now() - _at < TTL) return;
  _fetching = true;
  try {
    const r = await fetch(`${API}/market/macro-indicators`);
    if (r.ok) {
      _data = (await r.json()) as MacroIndicators;
      _at = Date.now();
      notify();
    }
  } catch {
    /* keep last good value */
  } finally {
    _fetching = false;
  }
}

export function useMacroIndicators(): MacroIndicators | null {
  const [, setTick] = useState(0);
  useEffect(() => {
    const fn = () => setTick((t) => t + 1);
    listeners.add(fn);
    fetchMacro();
    const id = window.setInterval(() => fetchMacro(true), TTL);
    return () => { listeners.delete(fn); window.clearInterval(id); };
  }, []);
  return _data;
}
