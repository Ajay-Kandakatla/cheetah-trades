import { useCallback, useEffect, useState } from 'react';

const API = (import.meta as any).env?.VITE_API_BASE ?? 'http://localhost:8000';

export type Rating = 'STRONG_BUY' | 'BUY' | 'WATCH' | 'NEUTRAL' | 'AVOID';

export type SepaCandidate = {
  symbol: string;
  name?: string | null;
  score: number;
  rating?: Rating;
  rs_rank: number | null;
  stage: { stage: number; label: string; dist_200_pct: number } | null;
  trend: {
    pass_all: boolean;
    passed: number;
    checks: Record<string, boolean>;
    price: number;
    ma50: number;
    ma150: number;
    ma200: number;
    week52_high: number;
    week52_low: number;
    pct_above_low: number;
    pct_below_high: number;
  };
  volume?: {
    up_down_vol_ratio: number | null;
    accumulation: boolean;
    vol_dryup: number | null;
    is_drying_up: boolean;
    high_vol_breakout: boolean;
  };
  vcp?: {
    has_base: boolean;
    base_depth_pct: number;
    n_contractions: number;
    tight_right_side: boolean;
    pivot_buy_price: number;
    suggested_stop: number;
    pivot_quality_ok?: boolean;
    pivot_prior_advance_pct?: number;
  };
  power_play?: { is_power_play: boolean; pivot_buy_price: number; suggested_stop: number };
  base_count?: { base_count: number; is_early_base: boolean; is_late_stage: boolean };
  entry_setup: { type: string; pivot: number; stop: number } | null;
  adr_pct?: number | null;
  liquidity?: { liquid: boolean; avg_dollar_vol: number; avg_shares: number };
  fundamentals?: {
    q_eps_growth_pct: number | null;
    y_eps_growth_pct: number | null;
    inst_ownership_pct: number | null;
    checks: { c_strong_q_eps: boolean; a_strong_y_eps: boolean; i_institutional: boolean };
    passed: number;
  };
  is_candidate: boolean;
};

export type SepaScan = {
  generated_at: number;
  duration_sec: number;
  universe_size: number;
  analyzed: number;
  candidate_count: number;
  market_context: {
    label: string;
    safe_to_long: boolean;
    spy: any;
    qqq: any;
  };
  candidates: SepaCandidate[];
  all_results: SepaCandidate[];
};

export type SepaBrief = {
  generated_at: number;
  generated_at_iso: string;
  market_context: SepaScan['market_context'];
  top_candidates: Array<{
    symbol: string;
    score: number;
    rs_rank: number;
    entry_setup: { type: string; pivot: number; stop: number } | null;
    trend_passed: number;
    vcp_summary: { n: number; depth: number; tight: boolean } | null;
    stage: { stage: number; label: string };
  }>;
  watchlist: Array<{
    symbol: string;
    entry: number;
    stop: number;
    last_price: number;
    pnl_pct: number;
    distance_to_stop_pct: number;
    action: string;
    sell_signals: any;
  }>;
  watchlist_alerts: Array<any>;
  catalyst_today: Array<any>;
  insider_today: Array<any>;
};

export function useSepaScan() {
  const [data, setData] = useState<SepaScan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/sepa/scan`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setData(j.candidates ? j : null);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const runScan = useCallback(async (withCatalyst = false, opts?: { fast?: boolean; mode?: string }) => {
    setScanning(true);
    try {
      const u = new URL(`${API}/sepa/scan`);
      u.searchParams.set('with_catalyst', String(withCatalyst));
      if (opts?.fast) u.searchParams.set('fast', 'true');
      if (opts?.mode) u.searchParams.set('mode', opts.mode);
      const r = await fetch(u.toString(), { method: 'POST' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setScanning(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, scanning, refetch: load, runScan };
}

export function useSepaBrief() {
  const [data, setData] = useState<SepaBrief | null>(null);
  const [loading, setLoading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/sepa/brief`);
      const j = await r.json();
      setData(j.top_candidates ? j : null);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const regenerate = useCallback(async () => {
    setRegenerating(true);
    try {
      const r = await fetch(`${API}/sepa/brief`, { method: 'POST' });
      setData(await r.json());
    } finally {
      setRegenerating(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, regenerating, regenerate, refetch: load };
}

export async function fetchSepaCandidate(symbol: string) {
  const r = await fetch(`${API}/sepa/candidate/${encodeURIComponent(symbol)}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function sepaRescan(symbol: string) {
  const r = await fetch(`${API}/sepa/rescan/${encodeURIComponent(symbol)}`, {
    method: 'POST',
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export type ResearchStatus = {
  available: boolean;
  total?: number;
  fresh?: number;
  stale?: number;
  oldest_age_sec?: number | null;
  newest_age_sec?: number | null;
  ttl_sec?: number;
  reason?: string;
};

export async function fetchResearchStatus(): Promise<ResearchStatus> {
  const r = await fetch(`${API}/sepa/research/status`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function refreshResearch(mode?: string): Promise<{ refreshed: string[]; failed: string[]; total: number; duration_sec: number }> {
  const u = new URL(`${API}/sepa/research/refresh`);
  if (mode) u.searchParams.set('mode', mode);
  const r = await fetch(u.toString(), { method: 'POST' });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function fetchWatchlist() {
  const r = await fetch(`${API}/sepa/watchlist`);
  return r.json();
}

export async function addToWatchlist(symbol: string, entry: number, stop: number) {
  const u = new URL(`${API}/sepa/watchlist`);
  u.searchParams.set('symbol', symbol);
  u.searchParams.set('entry', String(entry));
  u.searchParams.set('stop', String(stop));
  const r = await fetch(u.toString(), { method: 'POST' });
  return r.json();
}

export async function removeFromWatchlist(symbol: string) {
  const r = await fetch(`${API}/sepa/watchlist/${encodeURIComponent(symbol)}`, {
    method: 'DELETE',
  });
  return r.json();
}

export async function planPosition(params: {
  entry: number;
  stop: number;
  account_size: number;
  risk_per_trade_pct?: number;
}) {
  const u = new URL(`${API}/sepa/position-plan`);
  Object.entries(params).forEach(([k, v]) => u.searchParams.set(k, String(v)));
  const r = await fetch(u.toString(), { method: 'POST' });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
