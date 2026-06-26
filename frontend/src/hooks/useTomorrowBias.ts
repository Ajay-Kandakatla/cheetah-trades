/* useTomorrowBias — the overnight/after-hours → next-session "Tomorrow Bias".
 *
 * Per-ticker (GET /options/bias/{symbol}) for the options-flow tab, and
 * market-level (GET /options/market-bias) for the Overnight page panel.
 *
 * Both lean (LEAN_UP / LEAN_DOWN / NEUTRAL) + a confluence-gated confidence.
 * The whole thing TILTS probability for reacting at the open — it does not
 * predict the overnight. NEUTRAL is the honest default. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type Lean = 'LEAN_UP' | 'LEAN_DOWN' | 'NEUTRAL';
export type ConfTier = 'HIGH' | 'MEDIUM' | 'LOW';

export type ExpectedMoveBand = {
  center: number; low_pct: number; high_pct: number; low: number; high: number;
};

export type BiasPillars = {
  stock?: { score: number | null; gap_pct?: number | null; session?: string | null;
            bars?: number | null; gap_holding?: boolean | null };
  options?: { score: number | null; soir_volume?: number | null;
              soir_percentile?: number | null; schaeffer_signal?: string | null };
  backdrop?: { score: number | null; regime_label?: string | null;
               spy_gap_pct?: number | null; qqq_gap_pct?: number | null; vix?: number | null };
};

export type TickerBias = {
  symbol: string;
  beta?: number;
  lean: Lean;
  confidence: number;
  confidence_tier: ConfTier;
  raw_score?: number;
  agree_count?: number;
  reason: string;
  expected_move_band: ExpectedMoveBand | null;
  flags: string[];
  pillars: BiasPillars;
  as_of?: string | null;
  computed_at?: string;
  caveat: string;
};

export type MarketBias = {
  lean: Lean;
  confidence_tier: ConfTier;
  agreement_count: number;
  spy_gap_pct?: number | null;
  qqq_gap_pct?: number | null;
  gap_state?: 'HOLDING' | 'FADING' | null;
  vix?: number | null;
  regime_label?: string | null;
  confirmers: Record<string, 'agree' | 'disagree' | 'neutral'>;
  what_to_watch: string;
  flags: string[];
  read_session?: string;
  computed_at?: string;
  caveat: string;
};

/** Per-ticker Tomorrow Bias. Cheap (no chain pull) — safe to fetch on tab open. */
export function useTomorrowBias(symbol: string | null) {
  const [data, setData] = useState<TickerBias | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) { setData(null); return; }
    let alive = true;
    setLoading(true);
    setError(null);
    fetch(`${API}/options/bias/${encodeURIComponent(symbol)}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j) => { if (alive) setData(j); })
      .catch((e) => { if (alive) setError(String(e?.message || e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [symbol]);

  return { data, loading, error };
}

/** Market-level Tomorrow Bias for the Overnight page panel. */
export function useMarketBias() {
  const [data, setData] = useState<MarketBias | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    fetch(`${API}/options/market-bias`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive) setData(j); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  return { data, loading };
}
