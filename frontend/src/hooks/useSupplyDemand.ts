import { useCallback, useEffect, useRef, useState } from 'react';
import { useTabVisibility } from './useTabVisibility';
import { API } from '../lib/apiBase';


export type GraphNode = {
  ticker: string;
  name?: string;
  sector?: string;
  sub_sector?: string;
};

export type EdgeNewsLink = {
  title: string;
  url?: string | null;
  publisher?: string | null;
  published_utc?: string | null;
  tickers?: string[];
};

export type GraphEdge = {
  source: string;
  target: string;
  relation: string;
  strength: number;
  evidence: string;
  news_links?: EdgeNewsLink[];
};

export type SupplyDemandGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  n_nodes: number;
  n_edges: number;
};

export type SubGraph = {
  center: string;
  depth: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type SectorClassification = {
  state: 'constrained' | 'balanced' | 'oversupplied';
  gap_index: number;
  confidence: number;
  narrative: string;
  trend_direction: 'tightening' | 'stable' | 'loosening';
  _method?: string;
  _model?: string;
  _latency_sec?: number;
};

export type GapEconomics = {
  demand_usd_bn: number;
  supply_usd_bn: number;
  unit?: string;
  capex_to_close_usd_bn?: number;
  years_to_close?: string;
  key_constraint?: string;
  notes?: string;
  as_of?: string;
  sources?: string[];
};

export type SectorPayload = {
  sector_id: string;
  label: string;
  narrative_static?: string;
  thesis_static?: string;
  etf?: { ticker: string; last: number; change_1d_pct: number; change_30d_pct: number; change_90d_pct: number } | null;
  commodity?: { ticker: string; last: number; change_1d_pct: number; change_30d_pct: number; change_90d_pct: number } | null;
  headlines: { title: string; url?: string | null; publisher?: string | null; published_utc?: string | null }[];
  classification: SectorClassification;
  sp_tickers: string[];
  gap_economics?: GapEconomics | null;
  as_of: string;
  _cached?: boolean;
  _cache_age_sec?: number;
};

export type SectorsResponse = {
  sectors: SectorPayload[];
  as_of: string;
  n_sectors: number;
  n_cached: number;
  cache_ttl_hours: number;
};

export function useSupplyDemandGraph(enrichNews: boolean = false) {
  const [data, setData] = useState<SupplyDemandGraph | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/supply-demand/graph?enrich_news=${enrichNews}`, { cache: 'no-store' });
      if (!r.ok) return;
      setData(await r.json());
    } finally { setLoading(false); }
  }, [enrichNews]);

  useEffect(() => { load(); }, [load]);
  return { data, loading, refetch: load };
}

export function useSubGraph(ticker: string | null, depth: number = 1) {
  const [data, setData] = useState<SubGraph | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ticker) { setData(null); return; }
    setLoading(true);
    fetch(`${API}/supply-demand/graph/${ticker}?depth=${depth}&enrich_news=true`, { cache: 'no-store' })
      .then((r) => r.ok ? r.json() : null)
      .then(setData)
      .finally(() => setLoading(false));
  }, [ticker, depth]);

  return { data, loading };
}

export function useSectors() {
  const [data, setData] = useState<SectorsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (force = false) => {
    if (force) setRefreshing(true);
    try {
      const r = await fetch(`${API}/supply-demand/sectors${force ? '?force=true' : ''}`, { cache: 'no-store' });
      if (!r.ok) return;
      setData(await r.json());
    } finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  return { data, loading, refreshing, refetch: load, forceRefresh: () => load(true) };
}

export type AccumulationDetail = {
  score: number;
  label: AccumulationLabel;
  cmf: number;
  up_down_vol_ratio: number;
  close_position_5d: number;
  n_days: number;
};

export type TickerContext = {
  ticker: string;
  flow?: (FlowTicker & { market?: MarketStatus }) | null;
  accumulation?: AccumulationDetail | null;
  subgraph: SubGraph;
  sectors: SectorPayload[];
  n_dependencies: number;
  n_sector_exposures: number;
};

// --- Equity premium screen (treasury / narrative-stock detection) ------

export type EquityTag = 'TREASURY' | 'EQUITY_HEAVY' | 'NARRATIVE' | 'GROWTH_PREMIUM' | 'NORMAL';

export type EquityPremiumRow = {
  ticker: string;
  name?: string | null;
  sector?: string | null;
  market_cap?: number | null;
  book_value_total?: number | null;
  revenue_ttm?: number | null;
  enterprise_value?: number | null;
  cash?: number | null;
  cash_pct_of_mcap?: number | null;
  debt?: number | null;
  pb_ratio?: number | null;
  ps_ratio?: number | null;
  mcap_to_revenue?: number | null;
  equity_share_pct?: number | null;
  shares_growth_yoy_pct?: number;
  tag: EquityTag;
  rationale: string;
};

export type EquityPremiumScreen = {
  as_of: string;
  rows: EquityPremiumRow[];
  n_total: number;
  by_tag: Record<EquityTag, number>;
  elapsed_sec: number;
};

export function useEquityPremium() {
  const [data, setData] = useState<EquityPremiumScreen | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (force = false) => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/supply-demand/equity-premium${force ? '?force=true' : ''}`, { cache: 'no-store' });
      if (!r.ok) return;
      setData(await r.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  return { data, loading, refetch: () => load(false), forceRefresh: () => load(true) };
}

// --- Money flow (live during market hours) -----------------------------

export type MarketStatus = {
  state: 'open' | 'pre' | 'after' | 'closed' | 'weekend';
  is_live: boolean;
  label: string;
  next_event: string;
};

export type AccumulationLabel =
  | 'STRONG ACCUMULATION'
  | 'ACCUMULATION'
  | 'NEUTRAL'
  | 'DISTRIBUTION'
  | 'STRONG DISTRIBUTION';

export type FlowTicker = {
  ticker: string;
  price: number;
  prev_close: number;
  change_pct: number;
  volume: number;
  dollar_volume: number;
  day_high?: number;
  day_low?: number;
  day_open?: number;
  /** Multi-day Chaikin Money Flow score, range -100 to +100. Positive =
   *  accumulation pattern; negative = distribution. Null when we don't
   *  have enough OHLCV history for the ticker. */
  accumulation_score?: number | null;
  accumulation_label?: AccumulationLabel | null;
};

export type FlowSnapshot = {
  as_of: string;
  market: MarketStatus;
  tickers: FlowTicker[];
  leaders: {
    top_inflow: FlowTicker[];
    top_outflow: FlowTicker[];
  };
  totals: {
    n_total: number;
    n_up: number;
    n_down: number;
    n_flat: number;
    total_dollar_volume: number;
    n_accumulating?: number;
    n_strong_accumulation?: number;
    n_distributing?: number;
    n_strong_distribution?: number;
  };
  cached: boolean;
  cache_age_sec: number;
};

/** Polls /supply-demand/flow every `pollMs` during market hours,
 *  every 5min after-hours, and once on mount on weekends. */
export function useMarketFlow(pollMs: number = 30_000) {
  const [data, setData] = useState<FlowSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  // Hold latest is_live in a ref so the polling effect doesn't depend
  // on `data` (which would re-create the timer on EVERY fetch — what
  // ate the user's network tab). Effect now runs once per mount.
  const isLiveRef = useRef(true);
  const visible = useTabVisibility();

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/supply-demand/flow`, { cache: 'no-store' });
      if (!r.ok) return;
      const j = await r.json();
      setData(j);
      isLiveRef.current = j?.market?.is_live ?? false;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!visible) return;  // pause polling when tab is hidden
    load();
    // Poll during market hours; relax cadence otherwise. The tick
    // function reads the latest is_live via ref so we don't re-trigger
    // the effect (and clear/recreate the timer) on every fetch.
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      load();
      const live = isLiveRef.current;
      const next = live ? pollMs : Math.max(pollMs * 6, 5 * 60_000);
      timer = setTimeout(tick, next);
    };
    timer = setTimeout(tick, pollMs);
    return () => clearTimeout(timer);
  }, [load, pollMs, visible]);

  return { data, loading, refetch: load };
}

// --- Node thesis (rich popup) -------------------------------------------

export type NodeRelationship = {
  source: string;
  target: string;
  relation: string;
  strength: number;
  evidence: string;
  explanation: string;
  is_outbound: boolean;
};

export type NodeSectorExposure = {
  sector_id: string;
  label: string;
  thesis?: string;
  state: 'constrained' | 'balanced' | 'oversupplied';
  gap_index: number;
  trend_direction: 'tightening' | 'stable' | 'loosening';
};

export type NodeThesis = {
  ticker: string;
  name?: string;
  sector?: string;
  sub_sector?: string;
  thesis: {
    role?: string;
    moat?: string;
    watch?: string;
    bull_case?: string;
    bear_case?: string;
  };
  relationships: NodeRelationship[];
  n_relationships: number;
  sector_exposures: NodeSectorExposure[];
};

export function useNodeThesis(ticker: string | null) {
  const [data, setData] = useState<NodeThesis | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ticker) { setData(null); return; }
    setLoading(true);
    fetch(`${API}/supply-demand/thesis/${ticker}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData(d && !d.error ? d : null))
      .finally(() => setLoading(false));
  }, [ticker]);

  return { data, loading };
}

// --- Whales (13F holders) -----------------------------------------------

export type WhaleHolder = {
  holder: string;
  shares: number | null;
  value: number | null;
  pct_held: number | null;
  pct_change: number | null;
  date_reported: string | null;
  type: 'hedge_fund' | 'index_giant' | 'other';
  kind: 'institutional' | 'mutual_fund';
};

export type WhaleNotable = {
  holder: string;
  pct_change: number;
  type: string;
};

export type WhalePayload = {
  ticker: string;
  as_of: string;
  holders: WhaleHolder[];
  mutual_funds: WhaleHolder[];
  major: {
    insider_pct?: string;
    institutional_pct?: string;
    institutional_float_pct?: string;
    n_institutions?: string;
  };
  moves: {
    net_signal: 'accumulating' | 'distributing' | 'balanced';
    n_buying: number;
    n_selling: number;
    n_unchanged: number;
    notable_buys: WhaleNotable[];
    notable_sells: WhaleNotable[];
  };
  n_holders: number;
  n_mutuals: number;
  disclaimer: string;
  source: string;
  _cached?: boolean;
  _cache_age_sec?: number;
};

export function useWhales(ticker: string | null) {
  const [data, setData] = useState<WhalePayload | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ticker) { setData(null); return; }
    setLoading(true);
    fetch(`${API}/supply-demand/whales/${ticker}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then(setData)
      .finally(() => setLoading(false));
  }, [ticker]);

  return { data, loading };
}

export function useTickerSupplyDemand(ticker: string | null, depth: number = 1) {
  const [data, setData] = useState<TickerContext | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ticker) { setData(null); return; }
    setLoading(true);
    fetch(`${API}/supply-demand/ticker/${ticker}?depth=${depth}`, { cache: 'no-store' })
      .then((r) => r.ok ? r.json() : null)
      .then(setData)
      .finally(() => setLoading(false));
  }, [ticker, depth]);

  return { data, loading };
}
