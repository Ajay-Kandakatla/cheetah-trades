/* useScalpingSignals — live Phase-1 scalping signals (/scalping/signals) with the
 * intraday-momentum regime + spread gate + net-of-cost overlay. Polls every 45s
 * (the backend caches ~45s too). Educational, not advice.
 */
import { useEffect, useState, useCallback } from 'react';
import { API } from '../lib/apiBase';

export type ScalpSpread = {
  bid?: number | null; ask?: number | null; spread_pct?: number | null;
  state: 'tight' | 'wide' | 'too_wide' | 'unknown'; ok: boolean; note: string;
};

export type ScalpNetCost = {
  round_trip_cost_pct: number | null;
  spread_known: boolean;
  cost_breakdown: Record<string, number | null>;
  breakeven_win_rate_pct: number | null;
  verdict: string;
};

export type ScalpSignal = {
  symbol: string;
  strategy: string;
  strategy_label: string;
  side: 'long' | 'short';
  status: 'armed' | 'triggered' | string;
  entry: number; entry_price: number; stop: number; target: number; last_price?: number;
  risk_pct: number; reward_pct: number;
  rel_vol?: number; atr14?: number | null;
  move_pct?: number; sigma_multiple?: number | null; time_stop_min?: number;
  orb_high?: number; orb_low?: number; regime_aligned?: boolean;
  target_move_pct?: number;
  source: string; reasons: string[];
  spread?: ScalpSpread; tradeable?: boolean; net_of_cost?: ScalpNetCost;
};

export type ScalpRegime = {
  bias: 'long_bias' | 'short_bias' | 'stand_aside' | 'pending' | string;
  label: string; r1_pct?: number | null; source: string; note: string; as_of_et?: string;
};

export type ScalpPayload = {
  generated_at: number; as_of_et: string; market_open: boolean; profile: string;
  regime: ScalpRegime; signals: ScalpSignal[]; n: number; disclaimer: string;
};

const POLL_MS = 45 * 1000;

export function useScalpingSignals(profile: 'aggressive' | 'conservative' = 'aggressive') {
  const [data, setData] = useState<ScalpPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (force = false) => {
    try {
      const r = await fetch(`${API}/scalping/signals?profile=${profile}${force ? '&force=true' : ''}`, { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData((await r.json()) as ScalpPayload);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [profile]);

  useEffect(() => {
    setLoading(true);
    refresh();
    const id = window.setInterval(() => refresh(), POLL_MS);
    return () => window.clearInterval(id);
  }, [refresh]);

  return { data, loading, error, refresh };
}
