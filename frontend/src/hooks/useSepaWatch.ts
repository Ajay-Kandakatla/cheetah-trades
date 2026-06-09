/* useSepaWatch — the SEPA-cross tape watch payload (/scalping/watch): watched
 * names with their live 5-min candle read at levels, today's alerts, and the
 * live per-state hit-rate (self-graded vs the next 30 minutes). Polls 60s.
 */
import { useEffect, useState, useCallback } from 'react';
import { API } from '../lib/apiBase';

export type WatchRead = {
  state: string;
  verdict: 'constructive' | 'deteriorating' | 'neutral';
  severity: 'alert' | 'info';
  reasons: string[];
  metrics: {
    body_pct: number; upper_wick_pct: number; lower_wick_pct: number;
    clv: number; dir: string; vol_ratio: number | null;
    ref_level: number | null; ref_name: string | null;
  };
};

export type WatchRow = {
  symbol: string;
  tags: string[];
  pivot: number | null;
  last_price: number;
  levels: { pivot: number | null; vwap: number | null; or_high: number | null; day_high: number | null };
  bar_ts: string;
  read: WatchRead | null;
  vs_pivot_pct: number | null;
  vs_vwap_pct: number | null;
};

export type WatchAlert = {
  dedup: string; state: string; verdict: string; price: number;
  bar_ts: string; fired_at: number; fwd_pct: number | null; graded: 'hit' | 'miss' | null;
};

export type SepaWatchPayload = {
  generated_at: number; as_of_et: string; market_open: boolean;
  rows: WatchRow[]; n_watched: number;
  alerts_today: WatchAlert[];
  live_track_record: Record<string, { n: number; hit_rate_pct: number; median_fwd_30m_pct: number | null }>;
  disclaimer: string;
};

export type TapeBacktest = {
  days: number; symbols_used: number; n_events: number;
  by_state: Record<string, { n: number; verdict: string; median_fwd_30m_pct: number; mean_fwd_30m_pct: number; pct_positive_30m: number; follow_through_pct: number | null }>;
  verdict: string; caveats: string[]; error?: string;
};

export function useSepaWatch(enabled = true) {
  const [data, setData] = useState<SepaWatchPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(() => {
    fetch(`${API}/scalping/watch`, { cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => { setData(j); setError(null); })
      .catch((e) => setError(String(e)));
  }, []);
  useEffect(() => {
    if (!enabled) return;
    refresh();
    const id = window.setInterval(refresh, 60_000);
    return () => window.clearInterval(id);
  }, [enabled, refresh]);
  return { data, error, refresh };
}

export function useTapeBacktest(enabled = true, days = 15) {
  const [data, setData] = useState<TapeBacktest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setLoading(true);
    fetch(`${API}/scalping/watch/backtest?days=${days}`, { cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => { if (!cancelled) { setData(j); setError(null); } })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [enabled, days]);
  return { data, loading, error };
}
