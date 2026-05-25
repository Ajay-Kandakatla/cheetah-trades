import { useEffect, useState, useCallback } from 'react';
import type { MarketRegime } from './useMarketRegime';
import { API } from '../lib/apiBase';


export type Verdict = 'favorable' | 'selective' | 'neutral' | 'caution';
export type OverallAction = 'go_long' | 'day_trade_only' | 'swing_only' | 'tighten_stops' | 'sit_out';

export type CandidateNearPivot = {
  symbol: string;
  name?: string;
  score: number;
  rating: string;
  price: number;
  pivot: number;
  stop: number;
  setup_type: string;
  distance_to_pivot_pct: number;
  rs_rank?: number;
};

/** Slim per-row payload from the morning brief's options pulse section.
 *  Full SOIR record lives at /options/soir — this is just enough to render
 *  the morning summary card. */
export type MorningOptionsPulseRow = {
  symbol: string;
  soir?: number;
  soir_percentile?: number | null;
  expected_move_pct?: number | null;
  atm_iv?: number | null;
  signal?: 'BULLISH' | 'BEARISH' | 'WATCH' | 'NEUTRAL';
  reason?: string;
};

export type MorningOptionsPulse = {
  available: boolean;
  reason?: string;
  n_bullish?: number;
  n_bearish?: number;
  bullish?: MorningOptionsPulseRow[];
  bearish?: MorningOptionsPulseRow[];
  as_of?: string | null;
};

export type MorningBrief = {
  as_of: string;
  regime: MarketRegime;
  day_trading: {
    verdict: Verdict;
    headline: string;
    confidence: number;
    reasons_pro: string[];
    reasons_con: string[];
  };
  swing_trading: {
    verdict: Verdict;
    headline: string;
    confidence: number;
    reasons_pro: string[];
    reasons_con: string[];
    candidates_near_pivot: CandidateNearPivot[];
    candidates_near_pivot_count: number;
  };
  options_pulse?: MorningOptionsPulse;
  holdings?: HoldingsSummary;
  overall: { action: OverallAction; message: string };
  scan_age_minutes?: number | null;
};

export type HoldingsRow = {
  ticker: string;
  shares: number;
  cost_basis: number;
  avg_cost: number | null;
  last: number | null;
  prev_close: number | null;
  current_value: number | null;
  pl_dollars: number | null;
  pl_pct: number | null;
  day_change_pct: number | null;
  day_dollars: number | null;
  weight_pct?: number;
  account?: string;
  tags?: string[];
  alerts?: string[];
};

export type HoldingsSummary = {
  available: boolean;
  count?: number;
  total_value?: number;
  total_cost?: number;
  pl_dollars?: number;
  pl_pct?: number | null;
  day_dollars?: number;
  headline?: string;
  rows?: HoldingsRow[];
  reason?: string;
};

/** Are we currently in the morning decision window (06:00 – 10:00 ET, weekdays)?
 *  When true, the morning brief auto-forces a regime recompute on first
 *  open so the user gets a fresh read at the moment they care about it,
 *  not yesterday's snapshot. */
function _isMorningWindowET(): boolean {
  try {
    const fmt = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      hour: 'numeric', minute: 'numeric', hour12: false, weekday: 'short',
    });
    const parts = Object.fromEntries(fmt.formatToParts(new Date()).map((p) => [p.type, p.value]));
    if (['Sat', 'Sun'].includes(parts.weekday)) return false;
    const h = parseInt(parts.hour, 10);
    return h >= 6 && h < 10;
  } catch { return false; }
}

export function useMorningBrief() {
  const [data, setData] = useState<MorningBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (force = false) => {
    try {
      const url = `${API}/morning/brief${force ? '?force=true' : ''}`;
      const r = await fetch(url, { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
      setError(null);
    } catch (e) { setError(String(e)); } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    // First mount — force during the morning decision window so the user
    // always sees fresh regime + day/swing classification at decision time.
    load(_isMorningWindowET());
    const t = setInterval(() => load(false), 5 * 60_000);
    return () => clearInterval(t);
  }, [load]);
  return { data, loading, error, refetch: () => load(true) };
}
