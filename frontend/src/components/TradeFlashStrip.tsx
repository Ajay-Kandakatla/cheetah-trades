/* TradeFlashStrip — today's zone-tied tape bursts, on the Supply & Demand page.
 *
 * Ajay 2026-08-24: "Can you not do trade flash logic yourself? With in the
 * Demand Zone tabs and push notification I can also get it on my phone..."
 *
 * The strip is the in-app twin of the trade_flash push: every event here is a
 * >= $250k, >=75% one-sided 10-second burst that printed IN or NEAR a band on
 * the demand/supply boards (backend/orderflow/trade_flash.py — thresholds
 * imported from tape.find_bursts, one scale). Quiet by design: no events, no
 * strip — an empty ribbon announcing nothing would train him to ignore it.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';

export type FlashEvent = {
  _id: string;
  symbol: string;
  time_et: string;
  side: 'buy' | 'sell';
  dollars: number | null;
  price: number | null;
  board: 'demand' | 'supply';
  at_zone: 'in' | 'near';
};

/** What a burst MEANS depends on which board's band it hit. Pure. */
export function flashMeaning(ev: Pick<FlashEvent, 'board' | 'side'>): string {
  if (ev.board === 'demand') {
    return ev.side === 'buy' ? 'buyers stepping in at the zone' : 'sellers hitting the zone';
  }
  return ev.side === 'sell' ? 'sellers defending the ceiling' : 'buyers pushing into the ceiling';
}

export function fmtBurstDollars(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—';
  return n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : `$${(n / 1e3).toFixed(0)}K`;
}

const REFRESH_MS = 60_000;

export function TradeFlashStrip() {
  const [events, setEvents] = useState<FlashEvent[]>([]);

  useEffect(() => {
    let alive = true;
    const load = () => {
      fetch(`${API}/supply-demand/trade-flash`, { cache: 'no-store' })
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => { if (alive && j) setEvents(j.events ?? []); })
        .catch(() => { /* strip is decoration — never an error surface */ });
    };
    load();
    const t = window.setInterval(load, REFRESH_MS);
    return () => { alive = false; window.clearInterval(t); };
  }, []);

  if (!events.length) return null;

  return (
    <div className="tf-strip" role="log" aria-label="Today's tape bursts at zones">
      <span className="tf-strip__title">⚡ Tape bursts at zones today</span>
      {events.slice(0, 8).map((ev) => (
        <span key={ev._id} className={`tf-chip tf-chip--${ev.side}`}>
          <TickerLink ticker={ev.symbol} tab="tape" showWatchlist={false} />
          <span className="tf-chip__detail">
            {ev.time_et} · {fmtBurstDollars(ev.dollars)} {ev.side} · {flashMeaning(ev)}
          </span>
        </span>
      ))}
      {events.length > 8 && (
        <span className="tf-strip__more">+{events.length - 8} more</span>
      )}
    </div>
  );
}
