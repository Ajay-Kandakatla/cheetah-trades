import { useCallback, useEffect, useRef, useState } from 'react';
import { useTabVisibility } from './useTabVisibility';
import { API } from '../lib/apiBase';


export type Quadrant = 'REAL' | 'PUMP_RISK' | 'OVERLOOKED' | 'DEAD';

export type ChatterSignal = {
  ticker: string;
  stocktwits: {
    n_messages: number;
    n_24h: number;
    sentiment_pct_bullish: number | null;
    n_bullish: number;
    n_bearish: number;
    blurbs: string[];
  };
  reddit: {
    n_posts_24h: number;
    n_posts_7d: number;
    top: { title: string; url: string; subreddit: string; score: number; n_comments: number } | null;
    subreddits: string[];
    subreddit_counts?: Record<string, number>;
  };
  velocity_per_hour: number;
  sample_blurbs: string[];
};

export type NewsItem = {
  title: string;
  url?: string | null;
  publisher?: string | null;
  published_utc?: string | null;
  description?: string;
  tone?: 'bullish' | 'bearish' | 'neutral';
};

export type SecFiling = {
  form: string;
  filing_date: string;
  url?: string | null;
  tone: 'bullish' | 'bearish' | 'neutral';
  weight: number;
};

export type EvidenceSignal = {
  ticker: string;
  news: {
    n_total: number;
    n_bullish: number;
    n_bearish: number;
    n_neutral: number;
    bullish: NewsItem[];
    bearish: NewsItem[];
    neutral: NewsItem[];
  };
  sec_filings: {
    n_total: number;
    items: SecFiling[];
    has_8k: boolean;
    has_offering: boolean;
    has_13d: boolean;
    has_insider_trade: boolean;
  };
};

export type GemmaReview = {
  catalyst_summary: string;
  bull_pull: string | null;
  bear_pull: string | null;
  evidence_grade: 'A' | 'B' | 'C' | 'D' | string;
  is_pump_warning: boolean;
  _method?: string;
};

export type PumpPhase = 'ACCUMULATION' | 'BREAKOUT' | 'FRENZY' | 'DISTRIBUTION' | 'CRASH' | 'NONE';
export type PumpAction = 'WATCH' | 'ENTER_VWAP' | 'TRIM' | 'EXIT' | 'AVOID';

export type PumpAssessment = {
  phase: PumpPhase;
  action: PumpAction;
  entry_hint: string | null;
  stop_signal: string | null;
};

export type Candidate = {
  ticker: string;
  company_name?: string | null;
  sector?: string | null;
  price: number;
  prev_close: number;
  change_pct: number;
  volume: number;
  dollar_volume: number;
  day_high?: number;
  day_low?: number;
  market_cap?: number | null;
  avg_volume_10d?: number | null;
  volume_surge_ratio?: number | null;
  float?: number | null;
  chatter: ChatterSignal;
  evidence: EvidenceSignal;
  chatter_score: number;
  evidence_score: number;
  composite_score: number;
  quadrant: Quadrant;
  pump?: PumpAssessment;
  review: GemmaReview;
};

export type CatalystsScan = {
  as_of: string;
  market: { state: string; is_live: boolean; label: string; next_event: string };
  candidates: Candidate[];
  by_quadrant: Record<Quadrant, string[]>;
  n_total: number;
  n_real: number;
  n_pump_risk: number;
  n_overlooked: number;
  n_dead: number;
  filters: { max_share_price: number; max_market_cap: number; min_abs_change_pct: number };
  timing: { scan_sec: number; enrich_sec: number; review_sec: number; total_sec: number };
  cached: boolean;
  cache_age_sec: number;
};

export function useCatalystScan(pollMs: number = 60_000) {
  const [data, setData] = useState<CatalystsScan | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const visible = useTabVisibility();

  const load = useCallback(async (force = false) => {
    if (force) setRefreshing(true);
    try {
      const r = await fetch(`${API}/catalysts/scan${force ? '?force=true' : ''}`, { cache: 'no-store' });
      if (!r.ok) return;
      setData(await r.json());
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Keep latest is_live flag in a ref so the polling effect doesn't have
  // to depend on `data` (which would tear down + recreate the timer on
  // every fetch — small but wasteful churn).
  const isLiveRef = useRef(false);
  useEffect(() => { isLiveRef.current = data?.market?.is_live ?? false; }, [data]);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh during market hours; longer cadence off-hours.
  // Effect runs ONCE per mount (load + pollMs are stable). A self-rescheduling
  // setTimeout chain reads the latest is_live via ref each tick.
  useEffect(() => {
    if (!pollMs) return;
    if (!visible) return;  // pause polling when tab is hidden
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      load(false);
      const live = isLiveRef.current;
      const wait = live ? pollMs : Math.max(pollMs * 5, 5 * 60_000);
      timer = setTimeout(tick, wait);
    };
    timer = setTimeout(tick, pollMs);
    return () => clearTimeout(timer);
  }, [load, pollMs, visible]);

  return { data, loading, refreshing, refetch: load, forceRefresh: () => load(true) };
}

// --- Volume alerts (browser-notification feed) ------------------------

export type VolumeAlert = {
  ticker: string;
  fired_at: string | null;
  payload: {
    surge: number;
    price: number;
    change_pct: number;
    market_cap: number | null;
    dollar_volume: number;
    company_name: string | null;
    sent_whatsapp: boolean;
  };
};

export function useVolumeAlerts(pollMs: number = 30_000) {
  const [data, setData] = useState<{ alerts: VolumeAlert[]; session_date: string } | null>(null);
  const visible = useTabVisibility();
  // INFINITE-LOOP FIX: seenTickers must NOT live in state.
  //
  // Original bug: seenTickers was a useState, included in `load`'s
  // useCallback deps. Each fetch updated seenTickers → new `load`
  // identity → useEffect retriggered → cleared the interval and
  // immediately called load() again → infinite tight loop (~16k req).
  //
  // Fix: hold the seen-set in a useRef. Mutating .current does NOT
  // trigger a re-render, so `load` keeps a stable identity and the
  // poll interval fires exactly once every pollMs.
  const seenTickersRef = useRef<Set<string>>(new Set());

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/catalysts/alerts/history`, { cache: 'no-store' });
      if (!r.ok) return;
      const d = await r.json();
      setData(d);

      // Browser-notify on NEW alerts (tickers we haven't seen this session)
      const seen = seenTickersRef.current;
      const fresh = (d.alerts as VolumeAlert[]).filter((a) => !seen.has(a.ticker));
      if (fresh.length > 0 && 'Notification' in window && Notification.permission === 'granted') {
        fresh.forEach((a) => {
          const surge = a.payload?.surge?.toFixed(1) ?? '?';
          const chg = a.payload?.change_pct ?? 0;
          const sign = chg > 0 ? '+' : '';
          new Notification(`🚨 Volume spike: $${a.ticker}`, {
            body: `${a.payload?.company_name ?? ''}\n${surge}× avg vol · ${sign}${chg.toFixed(1)}% today · $${a.payload?.price?.toFixed(2)}`,
            icon: '/favicon.ico',
            tag: `volume-alert-${a.ticker}`,
          });
        });
      }
      // Update the ref WITHOUT triggering a re-render
      (d.alerts as VolumeAlert[]).forEach((a) => seen.add(a.ticker));
    } catch (err) {
      // best-effort
    }
  }, []);  // <-- empty deps: load is stable for the lifetime of the hook

  // Request notification permission once on mount
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {});
    }
  }, []);

  useEffect(() => {
    if (!visible) return;  // pause polling when tab is hidden
    load();
    const t = setInterval(load, pollMs);
    return () => clearInterval(t);
  }, [load, pollMs, visible]);

  return { alerts: data?.alerts ?? [], session_date: data?.session_date };
}

// --- Pre-market scan ---------------------------------------------------

export type PremarketCandidate = {
  ticker: string;
  price: number;
  prev_close: number;
  change_pct: number;
  volume: number;
  dollar_volume: number;
  market_cap?: number | null;
  avg_volume_10d?: number | null;
  company_name?: string | null;
  sector?: string | null;
};

export type PremarketScan = {
  as_of: string;
  window: { in_window: boolean; label: string; minutes_until_open: number | null };
  candidates: PremarketCandidate[];
  n_universe_scanned: number;
  n_movers_found: number;
  n_after_filter: number;
};

export function usePremarketScan() {
  const [data, setData] = useState<PremarketScan | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/catalysts/premarket`, { cache: 'no-store' });
      if (!r.ok) return;
      setData(await r.json());
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  return { data, loading, refetch: load };
}

// --- Insider Form 4 cluster -------------------------------------------

export type InsiderTx = {
  owner_name: string;
  officer_title: string | null;
  role: string;
  n_buys: number;
  n_sells: number;
  buy_value: number;
  sell_value: number;
  net_value: number;
  direction: 'buy' | 'sell' | 'neutral';
  filing_date: string | null;
  filing_url: string | null;
  transaction_date: string | null;
};

export type InsiderSignal = {
  ticker: string;
  n_buyers_7d: number;
  n_sellers_7d: number;
  net_buy_value_usd_7d: number;
  cluster_detected: boolean;
  cluster_score: number;
  recent: InsiderTx[];
};

export function useInsiderSignal(ticker: string | null) {
  const [data, setData] = useState<InsiderSignal | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ticker) { setData(null); return; }
    setLoading(true);
    fetch(`${API}/catalysts/insiders/${ticker}`, { cache: 'no-store' })
      .then((r) => r.ok ? r.json() : null)
      .then(setData)
      .finally(() => setLoading(false));
  }, [ticker]);

  return { data, loading };
}

// --- Catalyst calendar -------------------------------------------------

export type CalendarEvent = {
  type: 'earnings' | 'fda_readout' | 'macro';
  date: string;
  ticker?: string;
  title: string;
  description?: string;
  sponsor?: string;
  phase?: string;
  conditions?: string[];
  nct_id?: string;
  url?: string | null;
  subtype?: string;
};

export type CalendarPayload = {
  as_of: string;
  days_window: number;
  n_total: number;
  n_earnings: number;
  n_fda: number;
  n_macro: number;
  by_type: {
    earnings: CalendarEvent[];
    fda: CalendarEvent[];
    macro: CalendarEvent[];
  };
  timeline: CalendarEvent[];
  cached: boolean;
  cache_age_sec: number;
};

export function useCatalystCalendar(days: number = 30) {
  const [data, setData] = useState<CalendarPayload | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (force = false) => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/catalysts/calendar?days=${days}${force ? '&force=true' : ''}`, { cache: 'no-store' });
      if (!r.ok) return;
      setData(await r.json());
    } finally { setLoading(false); }
  }, [days]);

  useEffect(() => { load(); }, [load]);
  return { data, loading, refetch: () => load(false), forceRefresh: () => load(true) };
}

// --- Timeline (intraday hour-by-hour deltas) -------------------------

export type TimelineEvent = {
  from_at: string;
  at: string;
  entered: { ticker: string; company_name?: string; price?: number; change_pct?: number; quadrant?: Quadrant; chatter_score?: number; evidence_score?: number }[];
  exited: { ticker: string; company_name?: string }[];
  chatter_jumpers: { ticker: string; company_name?: string; delta: number; from_score: number; to_score: number; change_pct?: number }[];
  evidence_jumpers: { ticker: string; company_name?: string; delta: number; from_score: number; to_score: number }[];
  quadrant_transitions: { ticker: string; company_name?: string; from_quadrant: Quadrant; to_quadrant: Quadrant }[];
  phase_transitions: { ticker: string; company_name?: string; from_phase: string; to_phase: string }[];
  n_entered: number;
  n_exited: number;
  n_chatter_jumps: number;
  n_evidence_jumps: number;
  n_quadrant_transitions: number;
  n_phase_transitions: number;
};

export type CatalystTimeline = {
  session_date: string;
  n_snapshots: number;
  first_snapshot_at?: string;
  last_snapshot_at?: string;
  events: TimelineEvent[];
};

export function useCatalystTimeline() {
  const [data, setData] = useState<CatalystTimeline | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/catalysts/timeline`, { cache: 'no-store' });
      if (!r.ok) return;
      setData(await r.json());
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  return { data, loading, refetch: load };
}

// --- Stalled tickers ------------------------------------------------

export type StaleRecord = {
  ticker: string;
  company_name?: string;
  first_seen_at: string;
  hours_on_list: number;
  composite_score: number;
  score_drift: number;
  quadrant: Quadrant;
  change_pct?: number;
  chatter_score: number;
  evidence_score: number;
  volume_surge_ratio?: number;
};

export type CatalystStale = {
  session_date: string;
  min_age_hours: number;
  stable_winners: StaleRecord[];
  stalled_chatter: StaleRecord[];
  ambient_dead: StaleRecord[];
  n_snapshots: number;
};

export function useCatalystStale(minHours: number = 3) {
  const [data, setData] = useState<CatalystStale | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/catalysts/stale?min_age_hours=${minHours}`, { cache: 'no-store' });
      if (!r.ok) return;
      setData(await r.json());
    } finally { setLoading(false); }
  }, [minHours]);

  useEffect(() => { load(); }, [load]);
  return { data, loading, refetch: load };
}

// --- Multi-day accumulators ----------------------------------------

export type MultiDayAccumulator = {
  ticker: string;
  company_name?: string;
  n_session_dates_seen: number;
  first_seen_at: string;
  last_seen_at: string;
  accumulation_score: number;
  accumulation_label: string;
  cmf: number;
  up_down_vol_ratio: number;
  close_position_5d: number;
  n_days_data: number;
  latest_composite_score?: number;
  latest_quadrant?: Quadrant;
  latest_change_pct?: number;
  latest_volume_surge?: number;
  market_cap?: number;
  price?: number;
};

export type CatalystMultiDay = {
  accumulators: MultiDayAccumulator[];
  n_universe: number;
  n_with_strong_accum: number;
  min_session_appearances: number;
  lookback_days: number;
  min_accumulation_score: number;
};

export function useCatalystMultiDayAccumulators(minSessions: number = 3, lookbackDays: number = 10) {
  const [data, setData] = useState<CatalystMultiDay | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(
        `${API}/catalysts/multi-day-accumulators?min_session_appearances=${minSessions}&lookback_days=${lookbackDays}`,
        { cache: 'no-store' },
      );
      if (!r.ok) return;
      setData(await r.json());
    } finally { setLoading(false); }
  }, [minSessions, lookbackDays]);

  useEffect(() => { load(); }, [load]);
  return { data, loading, refetch: load };
}

// --- Frenzy radar (pre-frenzy detection) ---------------------------

export type FrenzyTier = 'IMMINENT' | 'SETUP' | 'EARLY' | 'QUIET';

export type FrenzySignal = {
  type: string;
  weight: number;
  detail: string;
  float_pct?: number;
};

export type FrenzyHaltInfo = {
  ticker: string;
  name?: string;
  halts: { halt_time: string; reason_code: string; resume_date?: string; resume_time?: string }[];
  n_halts: number;
  n_parabolic_halts: number;
  reasons: string[];
};

export type FrenzyCandidate = {
  ticker: string;
  company_name?: string;
  price?: number;
  change_pct?: number;
  volume?: number;
  volume_surge_ratio?: number;
  market_cap?: number;
  float?: number;
  chatter_velocity_per_hour?: number;
  stocktwits_24h?: number;
  reddit_24h?: number;
  accumulation_score?: number;
  halts_today?: FrenzyHaltInfo;
  signals: FrenzySignal[];
  score: number;
  tier: FrenzyTier;
};

export type FrenzyRadar = {
  as_of: string;
  n_total: number;
  by_tier: Record<FrenzyTier, number>;
  candidates: FrenzyCandidate[];
  snapshots_used: number;
  lookback_sessions_indexed: number;
  elapsed_sec: number;
};

export function useFrenzyRadar(pollMs: number = 2 * 60_000) {
  const [data, setData] = useState<FrenzyRadar | null>(null);
  const [loading, setLoading] = useState(true);
  const visible = useTabVisibility();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/catalysts/frenzy-radar`, { cache: 'no-store' });
      if (!r.ok) return;
      setData(await r.json());
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!pollMs || !visible) return;
    const t = setInterval(load, pollMs);
    return () => clearInterval(t);
  }, [load, pollMs, visible]);

  return { data, loading, refetch: load };
}

// --- Predictions (synthesized conviction across all signals) ----------

export type PredictionTier = 'HIGH' | 'MEDIUM' | 'WATCH' | 'AVOID';

export type PredictionSignal = {
  type: string;
  weight: number;
  detail: string;
  hard_veto?: boolean;
};

export type Prediction = {
  ticker: string;
  company_name?: string;
  sector?: string;
  price?: number;
  change_pct?: number;
  volume_surge_ratio?: number;
  market_cap?: number;
  quadrant?: Quadrant;
  pump_phase?: string;
  pump_action?: string;
  conviction_score: number;
  conviction_tier: PredictionTier;
  signals: PredictionSignal[];
  penalties: PredictionSignal[];
  bull_thesis?: string | null;
  bear_thesis?: string | null;
  entry_zone?: string | null;
  n_signals: number;
  n_penalties: number;
  has_hard_veto: boolean;
};

export type PredictionsPayload = {
  as_of: string;
  n_total: number;
  by_tier: Record<PredictionTier, number>;
  predictions: Prediction[];
  top_relevant: Prediction[];
  scan_age: number;
  elapsed_sec: number;
  cached: boolean;
  cache_age_sec: number;
};

export function usePredictions(pollMs: number = 5 * 60_000) {
  const [data, setData] = useState<PredictionsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (force = false) => {
    if (force) setRefreshing(true);
    try {
      const r = await fetch(`${API}/catalysts/predictions${force ? '?force=true' : ''}`, { cache: 'no-store' });
      if (!r.ok) return;
      setData(await r.json());
    } finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!pollMs) return;
    const t = setInterval(() => load(false), pollMs);
    return () => clearInterval(t);
  }, [load, pollMs]);

  return { data, loading, refreshing, refetch: load, forceRefresh: () => load(true) };
}

export function useDeepDive(ticker: string | null) {
  const [data, setData] = useState<Candidate | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ticker) { setData(null); return; }
    setLoading(true);
    fetch(`${API}/catalysts/${ticker}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData(d && !d.error ? d : null))
      .finally(() => setLoading(false));
  }, [ticker]);

  return { data, loading };
}
