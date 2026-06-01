/**
 * useRealtimeSignals — JIT real-time signals for a SEPA card:
 *
 *   • Accumulation/distribution from the live trade tape (Massive WS), polled
 *     every 6s WHILE the card is visible. Stops polling when it scrolls away.
 *   • Short interest (FINRA bi-monthly settlement) — one-shot on first view.
 *
 * Same IntersectionObserver discipline as useCardEnrichment: cards that never
 * scroll into view make zero requests. Accumulation only populates for focus
 * symbols (portfolio + top-N); opening any other card triggers an on-demand
 * subscribe server-side and returns `warming_up` until prints land.
 */
import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';

export type ShortInterest = {
  available: boolean;
  settlement_date?: string;
  short_interest?: number;
  days_to_cover?: number | null;
  pct_of_shares?: number | null;
  si_change_pct?: number | null;
  squeeze?: 'low' | 'elevated' | 'high';
};

export type Accumulation = {
  symbol: string;
  warming_up?: boolean;
  signal?: 'accumulation' | 'neutral' | 'distribution';
  session?: {
    trades?: number;
    net_dollars?: number;
    buy_ratio?: number | null;
    dark_pct?: number | null;
    dark_buy_ratio?: number | null;
  };
  nbbo?: { bid: number; ask: number } | null;
};

const POLL_MS = 6000;

export function useRealtimeSignals(symbol: string | null | undefined) {
  const [shortInterest, setShortInterest] = useState<ShortInterest | null>(null);
  const [accumulation, setAccumulation] = useState<Accumulation | null>(null);
  const elementRef = useRef<HTMLDivElement | null>(null);
  const siFetchedRef = useRef(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    siFetchedRef.current = false;
    setShortInterest(null);
    setAccumulation(null);
  }, [symbol]);

  useEffect(() => {
    const el = elementRef.current;
    if (!el || !symbol) return;

    const fetchSI = async () => {
      if (siFetchedRef.current) return;
      siFetchedRef.current = true;
      try {
        const r = await fetch(`${API}/short/${encodeURIComponent(symbol)}/interest`, { credentials: 'include' });
        if (r.ok) setShortInterest(await r.json());
      } catch { /* chip just stays absent */ }
    };
    const fetchAccum = async () => {
      try {
        const r = await fetch(`${API}/live/accumulation/${encodeURIComponent(symbol)}`, { credentials: 'include' });
        if (r.ok) setAccumulation(await r.json());
      } catch { /* chip just stays absent */ }
    };
    const startPoll = () => {
      if (pollRef.current) return;
      void fetchAccum();
      pollRef.current = setInterval(() => { void fetchAccum(); }, POLL_MS);
    };
    const stopPoll = () => {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };

    if (typeof IntersectionObserver === 'undefined') {
      void fetchSI();
      startPoll();
      return stopPoll;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            void fetchSI();
            startPoll();
          } else {
            stopPoll();
          }
        }
      },
      { threshold: 0.1 },
    );
    observer.observe(el);
    return () => { observer.disconnect(); stopPoll(); };
  }, [symbol]);

  return { ref: elementRef, shortInterest, accumulation };
}
