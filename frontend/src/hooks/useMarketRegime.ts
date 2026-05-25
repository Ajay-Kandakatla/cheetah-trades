import { useEffect, useState, useCallback } from 'react';
import { API } from '../lib/apiBase';


export type RegimeLabel =
  | 'confirmed_uptrend'
  | 'uptrend_under_pressure'
  | 'market_in_correction';

export type MarketRegime = {
  label: RegimeLabel;
  tagline: string;
  score: number;
  as_of: string;
  components: {
    trend_spy: { symbol: string; score: number; passed: number; of: number; price: number; ma200: number; pct_above_200ma: number | null; weight: number };
    trend_qqq: { symbol: string; score: number; passed: number; of: number; price: number; ma200: number; pct_above_200ma: number | null; weight: number };
    breadth: { pct_above_200ma: number | null; above?: number; total?: number; score: number; weight: number; reason?: string };
    distribution: { count: number | null; lookback_sessions?: number; score: number; weight: number };
    stress: { vix: number | null; percentile_252d: number | null; score: number; weight: number };
  };
  follow_through?: { detected: boolean; days_ago: number | null; ftd_date?: string; low_date?: string };
  narrative?: {
    headline: string;
    drivers_positive: string[];
    drivers_negative: string[];
    what_to_watch: string[];
  };
  methodology?: {
    summary: string;
    components: Array<{
      key: string;
      name: string;
      weight_pct: number;
      what: string;
      why_it_matters: string;
      source: string;
    }>;
    decision_rules: string[];
    backtested_accuracy: {
      window: string;
      by_label: Record<string, { share_pct: number; fwd_20d_hit_rate_pct: number; worst_20d_drawdown_pct: number; fwd_20d_mean_pct: number }>;
      baseline_fwd_20d_hit_rate_pct: number;
      honest_caveat: string;
    };
    what_we_dont_use_yet: string[];
  };
};

/**
 * useMarketRegime — polls /market/regime every 5 minutes (server caches 15min).
 * Returns the composite IBD-style regime label + all subscores for tooltip use.
 */
export function useMarketRegime() {
  const [data, setData] = useState<MarketRegime | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/market/regime`, { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setData(j);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(t);
  }, [load]);

  return { data, error, loading, refetch: load };
}
