/* Hooks for the scalping page's validation tabs:
 *  - useScalpingBacktest — historical walk-forward (gross vs net-of-cost). Heavy;
 *    fetched once (cached 6h backend-side).
 *  - useScalpingPaper — the forward paper-trade track record (real captured
 *    spreads); polls every 60s as it accumulates.
 */
import { useEffect, useState, useCallback } from 'react';
import { API } from '../lib/apiBase';

export type StratStats = {
  n_trades: number; note?: string;
  gross_win_rate_pct?: number; net_win_rate_pct?: number;
  gross_expectancy_r?: number; net_expectancy_r?: number | null;
  gross_total_pnl_pct?: number; net_total_pnl_pct?: number;
  net_profit_factor?: number | null;
  outcome_counts?: Record<string, number>;
  by_side?: Record<string, { n: number; net_win_rate_pct: number }>;
  verdict?: string;
};

export type ScalpBacktest = {
  generated_at: number; days: number; profile: string; symbols_used: number;
  assumed_spread_pct: number; n_trades: number;
  by_strategy: Record<string, StratStats>; overall: StratStats;
  sample_trades: any[]; caveats: string[]; error?: string;
};

export type PaperClosedStats = {
  n: number; note?: string;
  net_win_rate_pct?: number | null; net_expectancy_r?: number | null; net_total_pnl_pct?: number | null;
  by_strategy?: Record<string, { n: number; net_win_rate_pct: number; net_total_pnl_pct: number }>;
};

export type ScalpPaper = {
  open: any[]; closed: any[]; n_open: number; n_closed: number;
  closed_stats: PaperClosedStats; disclaimer: string;
};

export function useScalpingBacktest(days = 20, profile = 'aggressive', enabled = true) {
  const [data, setData] = useState<ScalpBacktest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setLoading(true);
    fetch(`${API}/scalping/backtest?days=${days}&profile=${profile}`, { cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => { if (!cancelled) { setData(j); setError(null); } })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days, profile, enabled]);
  return { data, loading, error };
}

export function useScalpingPaper(days = 30, enabled = true) {
  const [data, setData] = useState<ScalpPaper | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(() => {
    fetch(`${API}/scalping/paper?days=${days}`, { cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => { setData(j); setError(null); })
      .catch((e) => setError(String(e)));
  }, [days]);
  useEffect(() => {
    if (!enabled) return;
    refresh();
    const id = window.setInterval(refresh, 60_000);
    return () => window.clearInterval(id);
  }, [enabled, refresh]);
  return { data, error };
}
