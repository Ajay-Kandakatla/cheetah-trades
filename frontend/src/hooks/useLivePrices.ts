/**
 * useLivePrices — polls /sepa/live-prices with a session-aware cadence.
 *
 * Returns a map { SYMBOL: { price, change_pct, volume, last_trade_price,
 * last_trade_ts_ms, prev_day_close } } that gets merged into SEPA card
 * displays.  The poll cadence varies by market session — pre-market and
 * after-hours are less active so we don't burn API quota on slow tape;
 * the closed session doesn't poll at all (last value freezes on screen).
 *
 * As of 2026-05-26 this returns extended-hours fields so SEPA cards,
 * Kell cards, Overnight Pulse, and Whales / Supply-Demand pages can
 * render pre-market / after-hours prints with a StockTwits-style
 * session badge.
 */
import { useState, useEffect, useRef } from 'react';
import { API } from '../lib/apiBase';
import { getMarketSession, type MarketSession, type LivePrice } from '../lib/marketSession';

// Re-export so existing imports (`import type { LivePrice } from '../hooks/useLivePrices'`)
// keep working without touching every callsite.
export type { LivePrice } from '../lib/marketSession';

// Poll cadences per session — pre-market is less active so we don't burn
// API quota on slow tape. Closed sessions don't poll at all.
const POLL_MS: Record<MarketSession, number | null> = {
  pre:    3 * 60 * 1000,   // pre-market   — every 3 min (4:00am–9:30am ET)
  live:   2 * 60 * 1000,   // regular      — every 2 min
  after:  3 * 60 * 1000,   // after-hours  — every 3 min (4:00pm–8:00pm ET)
  closed: null,            // closed       — no polling, freeze last value
};

export function useLivePrices(): Record<string, LivePrice> {
  const [prices, setPrices] = useState<Record<string, LivePrice>>({});
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchPrices = async () => {
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
    // Always do one initial fetch so the screen has data even when the
    // market is closed (we still want yesterday's close on the cards).
    fetchPrices();

    const schedule = () => {
      const session = getMarketSession();
      const cadence = POLL_MS[session];
      if (cadence == null) {
        // Market closed — don't schedule another poll. The cards keep
        // showing whatever we last fetched.
        return;
      }
      timerRef.current = setTimeout(() => {
        fetchPrices();
        schedule();
      }, cadence);
    };
    schedule();

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return prices;
}
