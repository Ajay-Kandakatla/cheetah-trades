import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { readCache, writeCache } from '../lib/swrCache';


export type Rating = 'STRONG_BUY' | 'BUY' | 'WATCH' | 'NEUTRAL' | 'AVOID';

/** Trade plan — analyst-grade entry/stop/target/levels.
 *  Source: backend/analysis/trade_plan.py (Minervini / O'Neil / Wilder). */
export type TradePlan = {
  direction: 'long' | 'short';
  entries: {
    aggressive: number;
    standard:   number;
    pullback:   number | null;
  };
  entry_recommended_label: string;
  entry_recommended:       number;
  buy_zone:    { lo: number; hi: number };
  stop: {
    recommended_label: 'base_low' | 'atr_2x' | 'hard_pct';
    recommended:       number;
    candidates:        Record<string, number>;
    risk_pct?:         number;
    reason:            string;
  };
  targets: {
    r:                  number;
    r1:                 number | null;
    r2:                 number | null;
    r3:                 number | null;
    nearest_resistance: number | null;
    reward_to_risk?:    number | null;
  };
  levels: {
    ma20:        number | null;
    ma50:        number | null;
    ma200:       number | null;
    week52_high: number | null;
    week52_low:  number | null;
    swing_highs: number[];
    swing_lows:  number[];
  };
  atr:           number | null;
  setup_source:  string;
};

/** Timed entry/exit + decision plan. Source: backend/sepa/entry_exit.py */
export type EntryExitDecision = 'ENTER' | 'WAIT' | 'HOLD_WATCH' | 'AVOID' | 'CUT';
export type EntryExitPlan = {
  decision: EntryExitDecision | null;
  decision_color: 'green' | 'amber' | 'red' | null;
  decision_reason: string;
  entry: {
    status: 'actionable' | 'wait_trigger' | 'missed_extended' | 'above_zone';
    trigger: number;
    zone_lo: number;
    zone_hi: number;
    current: number;
    distance_pct: number;
    valid_through: string;   // ISO date
    valid_days: number;
  } | null;
  missed: {
    extended_pct: number;
    next_entry_lo: number;
    next_entry_hi: number;
    next_entry_basis: string;
    next_entry_note: string;
    rescan_hint: string;
  } | null;
  exit: {
    // Entry (pivot/buy point) the stops are measured from.
    entry?: number | null;
    // Unified stops comparison menu — one row per method, tightest → widest.
    stops?: Array<{
      kind: string;
      label: string;
      price: number;
      pct: number;
      risk_per_share: number;
      basis: string;
      tag?: 'tightest' | 'widest';
    }>;
    stop: number | null;
    stop_basis: string | null;
    stop_rule: string;
    intraday_floor: number;
    intraday_rule: string;
    // ATR-based dynamic stop — entry − ATR(14d)×mult; recomputes each scan.
    atr_stop?: number | null;
    atr_stop_pct?: number | null;
    atr_stop_mult?: number | null;
    atr_dollars?: number | null;
    atr_vs_fixed?: 'wider' | 'tighter' | null;
    atr_stop_rule?: string;
    // Structure-based stop — recent daily swing low − ATR×0.5.
    structure_stop?: number | null;
    structure_stop_pct?: number | null;
    structure_swing_low?: number | null;
    structure_atr_buffer?: number | null;
    structure_ma50_aligned?: boolean;
    structure_stop_rule?: string;
    targets: Array<{ label: string; price: number; horizon_days: number | null; eta: string }>;
    time_stop_days: number;
    time_stop_date: string;
    time_stop_rule: string;
  } | null;
  earnings: { date: string | null; in_days: number | null; blackout: boolean } | null;
  regime: { adx: number | null; atr_pct: number | null; chop: boolean } | null;
  timeline: Array<{ when: string; kind: string; key: string; label: string }>;
  as_of: string | null;
};

export type SepaCandidate = {
  symbol: string;
  name?: string | null;
  score: number;
  rating?: Rating;
  rs_rank: number | null;
  stage: {
    stage: number;
    label: string;
    dist_200_pct: number;
    /** Present (true) when MA-geometry said Stage 2 but volume tape
     *  (accumulation_strength=distributing OR cmf_signal=outflow) forced
     *  a downgrade to Stage 3 per Minervini p.71-72 vs p.74-76. Added
     *  2026-05-28 stage.classify() fix. Surfaced on the card as the
     *  "⚠️ Stage 3 — vol disagrees" badge. */
    volume_disagreement?: boolean;
    /** Human-readable reason for the downgrade — embedded in the drill
     *  modal so the user can see the specific accumulation_strength /
     *  cmf_signal values that triggered it. */
    volume_reason?: string;
  } | null;
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
    /** Latest bar's volume + the trailing 50-day average — used by the pivot
     *  meter's volume gauge (today vs the 1.5× breakout threshold). */
    last_vol?: number;
    avg_vol_50?: number;
    /** Bars since the most recent volume-confirmed breakout within the last 15
     *  (0 = today, null = none in window). Powers the FE 'Breakout: ≤1wk'
     *  toggle — a name may have broken out earlier in the week. Same-day value
     *  equals `high_vol_breakout`. See backend/sepa/volume.py. */
    days_since_breakout?: number | null;
    /** Added 2026-05-21 with the volume detector v2 — see
     *  backend/sepa/volume.py. Fields are optional so older cached
     *  candidate dicts without them still render. */
    accumulation_strength?: 'strong' | 'accumulating' | 'neutral' | 'distributing';
    pocket_pivot?: boolean;
    pocket_pivot_detail?: {
      is_pocket_pivot: boolean;
      today_vol?: number;
      max_down_vol_lookback?: number;
      strength_x?: number | null;
      reason?: string;
    };
    accumulation_days_25?: number;
    distribution_days_25?: number;
    cmf_20?: number | null;
    cmf_signal?: 'inflow' | 'neutral' | 'outflow';
    /** Volume-trend sparkline — last ~20 daily bars as SIGNED volume
     *  (magnitude = bar volume, sign = up-close day vs down-close day).
     *  Powers the <VolumeTrend> mini-histogram on the card + detail page.
     *  Display-only; absent on scans taken before 2026-06-12. */
    vol_spark?: number[];
    /** Count of distinct volume-confirmed breakouts over the trailing ~year
     *  (book p.203) + the window it was counted over. Powers <BreakoutStats>.
     *  Display-only; absent on scans before 2026-06-13. */
    breakout_count?: number | null;
    breakout_window_bars?: number | null;
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
    /** 0-100 VCP quality / tightness (breakoutshappen-style), banded
     *  tight ≥70 · developing 40-69 · early <40. Components book-grounded
     *  (pp.198-205); the weighting is ours. Null when <2 contractions. */
    tightness?: number | null;
    tightness_band?: 'tight' | 'developing' | 'early' | null;
    tightness_drivers?: string[];
    /** Depth of the final (right-side) contraction, %. The book's pivot forms on
     *  a narrow 3-5% pullback on dried volume (pp.198, 202) — used for the
     *  "textbook-tight pivot" (≤5%) entry-timing badge. */
    final_contraction_pct?: number;
    /** Volume dried up in the base (constructive — supply exhausted, p.203/205). */
    volume_drying?: boolean;
  };
  power_play?: { is_power_play: boolean; pivot_buy_price: number; suggested_stop: number };
  base_count?: { base_count: number; is_early_base: boolean; is_late_stage: boolean; is_avoid_stage?: boolean };
  /** David Ryan's MVP indicator (TTLAC §1 p.33 / §9 p.199) — 15-day
   *  momentum/volume/price continuation footprint + its context read. */
  mvp?: { has_mvp: boolean; up_days: number; price_pct: number; volume_pct: number;
          near_base_bottom: boolean } | null;
  mvp_read?: 'continuation' | 'exhaustion' | null;
  mvp_exhaustion?: boolean;
  entry_setup: { type: string; pivot: number; stop: number } | null;
  /** Comprehensive trade plan — entry/stop/target/levels, computed for
   *  every analyzed ticker (not just those with VCP base). See
   *  backend/analysis/trade_plan.py for methodology + source citations. */
  trade_plan?: TradePlan | null;
  /** Timed entry/exit + decision verdict — "what do I do THIS week."
   *  Computed in the scan from trade_plan + stage + volume + ATR/ADX.
   *  See backend/sepa/entry_exit.py. */
  entry_exit?: EntryExitPlan | null;
  adr_pct?: number | null;
  day_change_pct?: number | null;
  last_close?: number | null;
  dual_momentum?: {
    return_1m: number | null;
    return_3m: number | null;
    return_6m: number | null;
    return_12m: number | null;
    abs_mom_pass: boolean;
    beats_spy: boolean | null;
    dm_score: number | null;
  } | null;
  is_pioneer?: boolean;
  pioneer_themes?: { id: string; label: string }[];
  /** Industry-group leadership (Minervini Ch.6, p.102/108). Additive,
   *  DISPLAY-only — see backend/sepa/group_leadership.py. group_rs_rank is the
   *  stock's RS rank WITHIN its yfinance industry group (1=strongest). */
  industry?: string | null;
  sector?: string | null;
  group_rs_rank?: number | null;
  group_size?: number | null;
  group_leader?: boolean;
  is_laggard?: boolean;
  group_leader_symbol?: string | null;
  is_etf?: boolean;
  etf_data?: {
    is_etf: boolean;
    symbol: string;
    name?: string | null;
    category?: string | null;
    fund_family?: string | null;
    aum?: number | null;
    expense_ratio?: number | null;
    dividend_yield?: number | null;
    ytd_return?: number | null;
    nav?: number | null;
    holdings_count?: number | null;
    top_holdings?: { symbol: string; name?: string; weight: number }[];
  } | null;
  liquidity?: { liquid: boolean; avg_dollar_vol: number; avg_shares: number };
  fundamentals?: {
    q_eps_growth_pct: number | null;
    y_eps_growth_pct: number | null;
    inst_ownership_pct: number | null;
    checks: { c_strong_q_eps: boolean; a_strong_y_eps: boolean; i_institutional: boolean };
    passed: number;
    /** Sales Confidence (Bonde/Stockbee-inspired) — revenue growth +
     *  acceleration + consistency. See backend/sepa/sales.py. `score` is null
     *  when there isn't enough revenue history. */
    sales?: {
      score: number | null;
      tier: 'explosive' | 'strong' | 'steady' | 'weak' | 'declining' | 'unknown';
      growth_yoy_pct: number | null;
      prior_yoy_pct: number | null;
      accelerating: boolean | null;
      consecutive_growth_q: number;
      sales_led: boolean | null;
    };
  };
  /** Buffett-style economic moat score. tier: 4=Wide, 3=Narrow, 2=Some,
   *  1=None, 0=Unknown (insufficient data). */
  moat?: {
    score: number;
    label: 'WIDE' | 'NARROW' | 'SOME' | 'NONE' | 'UNKNOWN';
    tier: number;
    components: {
      profitability: { score: number; roe_pct: number | null };
      margins: { score: number; gross_pct: number | null; operating_pct: number | null };
      fcf:  { score: number; fcf_margin_pct: number | null };
      capital: { score: number; net_debt_ebitda: number | null };
      growth: { score: number; rev_growth_pct: number | null };
    };
    narrative: string;
    data_completeness?: number;   // 0-6, how many metrics had data
    is_partial?: boolean;         // true when <4 of 6 metrics had data
  };
  is_candidate: boolean;
  /** Minervini "Trend Template is a qualifier" (book p.79) — wider tier
   *  than `is_candidate`. True when trend.pass_all AND liquidity.liquid.
   *  Use for watchlist display; use `is_candidate` for buyable-now. */
  qualifier?: boolean;
  /** Strict book buy-now gate (backend `_is_buyable`, pp.79-83/198-203):
   *  Trend Template + Stage 2 + a setup + not late-stage + liquid + a
   *  VOLUME-CONFIRMED breakout (high_vol_breakout OR pocket_pivot). This is
   *  the "Enter = buyable" the decision filter binds to. */
  is_buyable?: boolean;
  /** `is_buyable` MINUS the same-day volume-breakout trigger — Trend Template +
   *  Stage 2 + setup + not-late + liquid. The "set up, waiting for the trigger"
   *  tier. Combined with `volume.days_since_breakout` it powers the FE
   *  'Breakout: ≤1wk / Any' Enter toggle. See backend/sepa/scanner._is_setup_ready. */
  setup_ready?: boolean;
  /** Distance from entry to the suggested stop, in %. Present when a setup
   *  with a stop exists. */
  risk_to_stop_pct?: number | null;
  /** Minervini-buyable + Bonde-sales combined PASS/PARTIAL/FAIL verdict
   *  (backend sepa/buyable_verdict.py — additive, display-only). Present on
   *  scans that ran the verdict annotation; absent on older cached scans. */
  buy_verdict?: import('../components/BuyVerdictChip').BuyVerdict | null;
};

export type SepaScan = {
  generated_at: number;
  duration_sec: number;
  universe_size: number;
  analyzed: number;
  candidate_count: number;
  /** Count of rows where `qualifier === true`. Always >= candidate_count.
   *  Surfaced in the hero so the user can see "1357 analyzed → 18
   *  qualifiers → 0 buyable" instead of just "0 candidates". */
  qualifier_count?: number;
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
  /** Comprehensive trade plan — entry/stop/target/levels, computed for
   *  every analyzed ticker (not just those with VCP base). See
   *  backend/analysis/trade_plan.py for methodology + source citations. */
  trade_plan?: TradePlan | null;
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

/** Stale-while-revalidate'd SEPA scan hook.
 *
 *  On mount: hydrates `data` synchronously from localStorage so the page
 *  renders the last-known scan instantly. Then revalidates in the
 *  background — replacing `data` once fresh JSON arrives. If the network
 *  fetch fails, the stale value stays on screen and `error` is set so the
 *  UI can show a banner.
 *
 *  `cachedAt` is the ms-epoch the visible data was stored; UI uses this
 *  to render "Showing scan from 4m ago — refreshing…".
 */
const SCAN_CACHE_KEY = 'sepa.scan';

export function useSepaScan() {
  const [data, setData] = useState<SepaScan | null>(() => {
    const env = readCache<SepaScan>(SCAN_CACHE_KEY);
    return env?.data ?? null;
  });
  const [cachedAt, setCachedAt] = useState<number | null>(() => {
    const env = readCache<SepaScan>(SCAN_CACHE_KEY);
    return env?.ts ?? null;
  });
  // `loading` reflects ONLY the case where we have nothing to show
  // (no cache + fetch in flight). When stale data is on screen the page
  // shouldn't flash a spinner — use `revalidating` for that subtle state.
  const [loading, setLoading] = useState(() => readCache<SepaScan>(SCAN_CACHE_KEY) === null);
  const [revalidating, setRevalidating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);

  // Two-phase load: hit the slim endpoint FIRST (drops `all_results`,
  // ~150KB instead of ~4MB) so the page paints fast on phone cellular.
  // If the user opens "show all analyzed", we'll fetch the full version
  // separately and merge it in (see `loadFull` below).
  const [hasFull, setHasFull] = useState(false);

  const load = useCallback(async () => {
    setRevalidating(true);
    try {
      const r = await fetch(`${API}/sepa/scan?slim=true`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      const fresh = j.candidates ? j : null;
      setData((prev) => {
        // Preserve all_results from the existing cache if we had it
        // (don't downgrade to slim mid-session).
        if (prev?.all_results && fresh) {
          return { ...fresh, all_results: prev.all_results };
        }
        return fresh;
      });
      setError(null);
      if (fresh) {
        writeCache(SCAN_CACHE_KEY, fresh);
        setCachedAt(Date.now());
      }
    } catch (e) {
      // Keep stale data on screen — only flag the error so the UI can
      // show a "couldn't refresh" banner above the cached list.
      setError(String(e));
    } finally {
      setLoading(false);
      setRevalidating(false);
    }
  }, []);

  /** On-demand fetch of the full all_results array. Called when the user
   *  toggles "show all analyzed" — we don't pay the 4MB cost upfront. */
  const loadFull = useCallback(async () => {
    if (hasFull) return;
    try {
      const r = await fetch(`${API}/sepa/scan`);
      if (!r.ok) return;
      const j = await r.json();
      if (j.all_results) {
        setData((prev) => prev ? { ...prev, all_results: j.all_results } : j);
        setHasFull(true);
        writeCache(SCAN_CACHE_KEY, j);
      }
    } catch { /* keep slim data */ }
  }, [hasFull]);

  const runScan = useCallback(async (withCatalyst = false, opts?: { fast?: boolean; mode?: string }) => {
    setScanning(true);
    try {
      const u = new URL(`${API}/sepa/scan`);
      u.searchParams.set('with_catalyst', String(withCatalyst));
      if (opts?.fast) u.searchParams.set('fast', 'true');
      if (opts?.mode) u.searchParams.set('mode', opts.mode);
      const r = await fetch(u.toString(), { method: 'POST' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const fresh = await r.json();
      setData(fresh);
      setError(null);
      if (fresh) {
        writeCache(SCAN_CACHE_KEY, fresh);
        setCachedAt(Date.now());
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setScanning(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, revalidating, cachedAt, error, scanning, refetch: load, runScan, loadFull, hasFull };
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

/** Stale-while-revalidate'd candidate detail.
 *
 *  Per-symbol cache key — keyed scoped so navigating MU → AAPL → MU brings
 *  back the last-known MU detail instantly while AAPL revalidates in the
 *  background. Prevents the blank screen we currently show on every
 *  symbol switch.
 */
const CANDIDATE_CACHE_KEY = (sym: string) => `sepa.candidate.${sym.toUpperCase()}`;

export function useSepaCandidate(symbol: string | null | undefined) {
  // Initialize state from cache so the first render already has data
  // when we have a hit. The cache key is recomputed below in the effect
  // so we have to read once for state init, then read again per symbol.
  const initial = symbol ? readCache<any>(CANDIDATE_CACHE_KEY(symbol)) : null;
  const [data, setData] = useState<any>(initial?.data ?? null);
  const [cachedAt, setCachedAt] = useState<number | null>(initial?.ts ?? null);
  const [revalidating, setRevalidating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) { setData(null); setCachedAt(null); return; }
    const key = CANDIDATE_CACHE_KEY(symbol);
    // Hydrate from cache synchronously on every symbol switch — this is
    // what makes navigation feel instant. If the cached value matches the
    // new symbol, show it; otherwise blank until fetch lands.
    const env = readCache<any>(key);
    if (env?.data) {
      setData(env.data);
      setCachedAt(env.ts);
      setError(null);
    } else {
      setData(null);
      setCachedAt(null);
    }

    let alive = true;
    setRevalidating(true);
    fetchSepaCandidate(symbol)
      .then((fresh) => {
        if (!alive) return;
        setData(fresh);
        setCachedAt(Date.now());
        setError(null);
        writeCache(key, fresh);
      })
      .catch((e) => {
        if (!alive) return;
        // Keep stale data on screen — surface the failure separately.
        setError(String(e));
      })
      .finally(() => {
        if (alive) setRevalidating(false);
      });

    return () => { alive = false; };
  }, [symbol]);

  // Manual refresh — used by the rescan flow on the detail page.
  const setFresh = useCallback((fresh: any) => {
    setData(fresh);
    setCachedAt(Date.now());
    if (symbol && fresh) writeCache(CANDIDATE_CACHE_KEY(symbol), fresh);
  }, [symbol]);

  return { data, cachedAt, revalidating, error, setFresh };
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
