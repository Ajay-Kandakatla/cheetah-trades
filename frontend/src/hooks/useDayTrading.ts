import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';


export type IntradayBar = {
  ts: string;
  o: number; h: number; l: number; c: number; v: number;
  session: 'premarket' | 'rth' | 'afterhours' | 'closed';
  vwap: number | null;
  atr14: number | null;
};

export type DayBars = {
  symbol: string;
  bars: IntradayBar[];
  indicators: {
    opening_range?: { high: number; low: number; volume: number; from: string; to: string; minutes: number; complete: boolean; et_date: string } | null;
    premarket?: { high: number; low: number; volume: number; et_date: string; bars: number } | null;
    rth_hi_lo?: { high: number; low: number } | null;
    relative_volume?: number | null;
  };
};

export type DaySignal = {
  symbol?: string;
  strategy: string;
  side: 'long' | 'short';
  entry_ts: string;
  entry_price: number;
  stop: number;
  target: number;
  risk_pct: number;
  reward_pct: number;
  r_multiple_potential: number;
  orb_high: number;
  orb_low: number;
  orb_range_pct: number;
  volume_ratio_at_entry: number;
  atr14: number | null;
  reasons: string[];
  et_date?: string;
};

export type BacktestStats = {
  win_rate_pct: number;
  avg_pnl_pct: number;
  avg_r_multiple: number;
  profit_factor: number | null;
  max_consecutive_drawdown_pct: number;
  outcome_counts: Record<string, number>;
  by_side: Record<string, { n: number; win_rate_pct: number; avg_r: number }>;
};

export type SymbolBacktest = {
  symbol: string;
  strategy: string;
  days_evaluated: number;
  days_with_signal: number;
  trigger_rate_pct: number;
  n_trades: number;
  stats: BacktestStats | { note: string };
  trades?: Array<DaySignal & { outcome: string; pnl_pct: number; r_multiple: number; et_date: string }>;
};

export type UniverseBacktest = {
  strategy: string;
  days: number;
  symbols: string[];
  per_symbol: Record<string, Omit<SymbolBacktest, 'trades'>>;
  aggregate: {
    n_trades: number;
    win_rate_pct?: number;
    avg_pnl_pct?: number;
    avg_r_multiple?: number;
    profit_factor?: number | null;
  };
};

/** /day/symbols — default watchlist */
export function useWatchlist() {
  const [data, setData] = useState<string[]>([]);
  useEffect(() => {
    fetch(`${API}/day/symbols`).then((r) => r.json()).then((j) => setData(j.watchlist || []));
  }, []);
  return data;
}

export type DayProfile = 'aggressive' | 'conservative';
export type DayMover = {
  symbol: string;
  adr_pct: number | null;
  rel_vol: number | null;
  change_pct: number | null;
  last: number | null;
};

/** /day/symbols — dynamic day-trade universe (today's movers) + profile control.
 *  `symbols` is the bounded set the page charts + live-scans; `universeSize` is
 *  the full day-tradeable pool they were drawn from. */
export function useDayUniverse() {
  const [profile, setProfile] = useState<DayProfile>('aggressive');
  const [symbols, setSymbols] = useState<string[]>([]);
  const [movers, setMovers] = useState<DayMover[]>([]);
  const [live, setLive] = useState(false);
  const [universeSize, setUniverseSize] = useState(0);
  const [criteria, setCriteria] = useState('');

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/day/symbols?profile=${profile}`)
      .then((r) => r.json())
      .then((j) => {
        if (cancelled) return;
        setSymbols(j.watchlist || []);
        setMovers(j.movers || []);
        setLive(!!j.live);
        setUniverseSize(j.universe_size || 0);
        setCriteria(j.criteria || '');
      })
      .catch(() => { /* best-effort */ });
    return () => { cancelled = true; };
  }, [profile]);

  return { symbols, movers, live, universeSize, criteria, profile, setProfile };
}

export type MarketSession = 'regular' | 'premarket' | 'afterhours' | 'closed';
export type Gapper = {
  symbol: string;
  move_pct: number;                 // headline move (session-aware)
  gap_pct: number | null;           // last regular-session move
  ext_move_pct: number | null;      // live extended-hours move
  ext_label: string | null;         // PM | AH | O/N | null
  direction: 'up' | 'down';
  rel_vol: number | null;
  last: number | null;
  prev_close: number | null;
  adr_pct?: number | null;       // volatility — avg daily range %
  dollar_vol?: number | null;    // avg daily $ volume (liquidity)
  rs_rank?: number | null;
  pm_high?: number | null;
  pm_low?: number | null;
  rel_vol_10d?: number | null;
  earnings_soon?: boolean | null;
  earnings_date?: string | null;
};
export type GappersPayload = {
  gappers: Gapper[];
  n_gappers: number;
  n_enriched: number;
  gap_min_pct: number;
  rel_vol_elevated: number;
  profile: string;
  session: MarketSession;
  live: boolean;
  as_of: string;
  disclaimer: string;
};

/** /day/gappers — overnight gappers (pre-market "set the day"), polls 60s. */
export function useGappers(profile: DayProfile) {
  const [data, setData] = useState<GappersPayload | null>(null);
  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetch(`${API}/day/gappers?profile=${profile}`, { cache: 'no-store' })
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => { if (!cancelled && j) setData(j); })
        .catch(() => { /* best-effort */ });
    load();
    const t = setInterval(load, 60_000);
    return () => { cancelled = true; clearInterval(t); };
  }, [profile]);
  return data;
}

/** /day/bars/{symbol} */
export function useDayBars(symbol: string | null, days = 1) {
  const [data, setData] = useState<DayBars | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!symbol) return;
    setLoading(true);
    try {
      const r = await fetch(`${API}/day/bars/${symbol}?days=${days}&include_premarket=true`, { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
      setError(null);
    } catch (e) { setError(String(e)); } finally { setLoading(false); }
  }, [symbol, days]);

  useEffect(() => { load(); const t = setInterval(load, 60_000); return () => clearInterval(t); }, [load]);
  return { data, loading, error, refetch: load };
}

/** /day/signals/today — live signals across watchlist (filterable by strategy) */
export function useLiveSignals(symbols?: string[], strategies?: string[]) {
  const [data, setData] = useState<DaySignal[]>([]);
  const [asOf, setAsOf] = useState<string | null>(null);

  const load = useCallback(async () => {
    const qs = new URLSearchParams();
    if (symbols && symbols.length) qs.set('symbols', symbols.join(','));
    if (strategies && strategies.length) qs.set('strategies', strategies.join(','));
    try {
      const r = await fetch(`${API}/day/signals/today?${qs}`, { cache: 'no-store' });
      if (!r.ok) return;
      const j = await r.json();
      setData(j.signals || []);
      setAsOf(j.as_of);
    } catch {}
  }, [symbols?.join(','), strategies?.join(',')]);

  useEffect(() => { load(); const t = setInterval(load, 60_000); return () => clearInterval(t); }, [load]);
  return { signals: data, asOf, refetch: load };
}

/** /day/backtest/yesterday — universe summary */
export function useYesterdayBacktest(symbols?: string[]) {
  const [data, setData] = useState<UniverseBacktest | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const qs = symbols && symbols.length ? `?symbols=${symbols.join(',')}` : '';
    fetch(`${API}/day/backtest/yesterday${qs}`)
      .then((r) => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, [symbols?.join(',')]);
  return { data, loading };
}

export type StrategyInfo = {
  name: string;
  description: string;
  research?: string;
  side?: 'long' | 'short' | 'both';
  '30d_baseline_winrate'?: number;
  '30d_baseline_avgR'?: number;
  '30d_baseline_pf'?: number;
  warning?: string;
  note?: string;
};

/** /day/strategies — list of available signal types + research + baselines */
export function useStrategies() {
  const [data, setData] = useState<Record<string, StrategyInfo>>({});
  useEffect(() => {
    fetch(`${API}/day/strategies`).then((r) => r.json()).then((j) => setData(j.strategies || {}));
  }, []);
  return data;
}

export type PaperPosition = {
  _id: string;
  et_date: string;
  symbol: string;
  strategy: string;
  side: 'long' | 'short';
  entry_ts: string;
  entry_price: number;
  stop: number;
  target: number;
  risk_pct?: number;
  reward_pct?: number;
  r_multiple_potential?: number;
  reasons?: string[];
  status: 'open' | 'closed';
  outcome?: 'stop' | 'target' | 'eod_flat';
  exit_ts?: string;
  exit_price?: number;
  pnl_pct?: number;
  r_multiple?: number;
};

export type PaperState = {
  et_date: string;
  open: PaperPosition[];
  closed: PaperPosition[];
  open_count: number;
  closed_count: number;
  stats: {
    n?: number;
    n_wins?: number;
    n_losses?: number;
    win_rate_pct?: number;
    total_pnl_pct?: number;
    avg_pnl_pct?: number;
    avg_r_multiple?: number;
    equity_curve_pct?: number[];
    by_strategy?: Record<string, { n: number; win_rate_pct: number; avg_r: number; total_pnl_pct: number }>;
    risk_per_trade_pct?: number;
    note?: string;
  };
  scan_summary?: { new_signals: number; closed_positions: number; scanned_symbols: number };
};

/** /day/paper/today — live paper trading state (auto-polls 60s) */
export function usePaperTrading(symbols?: string[], strategies?: string[]) {
  const [data, setData] = useState<PaperState | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const qs = new URLSearchParams();
    if (symbols?.length) qs.set('symbols', symbols.join(','));
    if (strategies?.length) qs.set('strategies', strategies.join(','));
    try {
      const r = await fetch(`${API}/day/paper/today?${qs}`, { cache: 'no-store' });
      if (!r.ok) return;
      setData(await r.json());
    } catch {} finally { setLoading(false); }
  }, [symbols?.join(','), strategies?.join(',')]);

  useEffect(() => { load(); const t = setInterval(load, 60_000); return () => clearInterval(t); }, [load]);

  const reset = useCallback(async () => {
    await fetch(`${API}/day/paper/reset`, { method: 'POST' });
    await load();
  }, [load]);

  return { data, loading, refetch: load, reset };
}

/** /day/backtest/{symbol} — single-symbol walk-forward */
export function useSymbolBacktest(symbol: string | null, days = 30) {
  const [data, setData] = useState<SymbolBacktest | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    fetch(`${API}/day/backtest/${symbol}?days=${days}`)
      .then((r) => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, [symbol, days]);
  return { data, loading };
}


// ── Leaderboard leaders · intraday movers ────────────────────────────────────
export type DayLeader = {
  symbol: string;
  current_rank?: number | null;
  persistence_pct?: number | null;
  appearances?: number | null;
  status?: string | null;            // buyable | ready | watch (rank-tier)
  flag?: string | null;              // breaking_out | primed | volatile | steady
  coiling?: boolean | null;
  stage?: number | null;
  near_r1?: boolean | null;
  // intraday overlay
  intraday_change_pct?: number | null;
  intraday_rank?: number | null;
  last_price?: number | null;
  prev_close?: number | null;
  is_buyable?: boolean;
  setup_ready?: boolean;
  rating?: string | null;
};

export type DayLeaderboard = {
  available: boolean;
  market_session: 'premarket' | 'open' | 'afterhours' | 'closed' | 'unknown';
  is_open: boolean;
  as_of_close: boolean;
  as_of: number;
  leaders: DayLeader[];
  n: number;
  buyable_count: number;
  up_count?: number;
  scans_in_window?: number | null;
  lookback_days?: number;
};

export function useDayLeaderboard(n = 14, days = 14) {
  const [data, setData] = useState<DayLeaderboard | null>(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/day/leaderboard?n=${n}&days=${days}`, { cache: 'no-store' });
      if (r.ok) setData(await r.json());
    } catch {
      /* keep last */
    } finally {
      setLoading(false);
    }
  }, [n, days]);
  useEffect(() => { load(); const t = setInterval(load, 120_000); return () => clearInterval(t); }, [load]);
  return { data, loading, refetch: load };
}
