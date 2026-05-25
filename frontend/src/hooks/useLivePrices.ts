/**
 * useLivePrices — polls /sepa/live-prices every 2 minutes during market hours.
 *
 * Returns a map { SYMBOL: { price, change_pct, volume } } that gets merged
 * into SEPA card displays.  Outside market hours (9:30–16:00 ET, Mon-Fri)
 * the hook stops polling and the map stays at its last value.
 */
import { useState, useEffect, useRef } from 'react';
import { API } from '../lib/apiBase';
const POLL_MS = 2 * 60 * 1000; // 2 minutes

export interface LivePrice {
  price: number;
  change_pct: number | null;
  volume: number | null;
}

function isMarketHours(): boolean {
  const now = new Date();
  // getDay(): 0=Sun, 6=Sat
  if (now.getDay() === 0 || now.getDay() === 6) return false;
  // Approximate ET offset: UTC-4 (EDT) or UTC-5 (EST).
  // Using UTC-4 year-round is close enough for a polling guard.
  const etHour = (now.getUTCHours() - 4 + 24) % 24 + now.getUTCMinutes() / 60;
  return etHour >= 9.5 && etHour < 16.0;
}

export function useLivePrices(): Record<string, LivePrice> {
  const [prices, setPrices] = useState<Record<string, LivePrice>>({});
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchPrices = async () => {
    if (!isMarketHours()) return;
    try {
      const r = await fetch(`${API}/sepa/live-prices`, { cache: 'no-store' });
      if (!r.ok) return;
      const data = await r.json();
      if (data?.prices) setPrices(data.prices);
    } catch {
      // network hiccup — keep last known prices
    }
  };

  useEffect(() => {
    fetchPrices();

    const schedule = () => {
      timerRef.current = setTimeout(() => {
        fetchPrices();
        schedule();
      }, POLL_MS);
    };
    schedule();

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return prices;
}
