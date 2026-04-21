export interface Quote {
  symbol: string;
  price?: number;
  volume?: number;
  change?: number;
  open?: number;
  high?: number;
  low?: number;
  prev_close?: number;
  pct_change?: number;
  rsi14?: number;
  vwap?: number;
  sparkline?: number[];
  source?: 'finnhub_ws' | 'finnhub_rest' | string;
  trade_ts?: number;
  ts: number;
}

export type ConnectionStatus = 'connecting' | 'open' | 'closed' | 'error';

export type SignalType =
  | 'growth'
  | 'momentum'
  | 'quality'
  | 'value'
  | 'stability';

export interface Signal {
  label: string;
  type: SignalType;
}

export interface BucketScores {
  growth: number;
  momentum: number;
  quality: number;
  stability: number;
  value: number;
}

export interface CheetahStock {
  ticker: string;
  name: string;
  sector: string;
  mcap: number;
  revGrowth: number;
  grossMargin: number;
  debtRev: number;
  peg: number;
  rs: number;
  perf3m: number;
  score: number;
  buckets?: BucketScores;
  signals: Signal[];
  tier2: string[];
  tier3: string[];
  why: string;
}

export interface CheetahResponse {
  weights: Record<string, number>;
  stocks: CheetahStock[];
  computedAt: number;
}

export interface CompetitorPeer {
  ticker: string;
  name: string;
  overlap: string;
  revGrowth: number;
  grossMargin: number;
  peg: number;
  rs: number;
  perf3m: number;
  note: string;
  status: 'growing' | 'challenger' | 'enabler' | string;
}

export interface CompetitorGroup {
  anchor: string;
  headline: string;
  sub: string;
  peers: CompetitorPeer[];
  anchorStock?: {
    ticker: string;
    name: string;
    revGrowth: number;
    grossMargin: number;
    peg: number;
    rs: number;
    perf3m: number;
    score: number;
  };
}

export interface Unicorn {
  name: string;
  sector: string;
  valuation: number;        // $B
  revGrowth: number;        // % YoY (0 if undisclosed)
  arr: number;              // $B annualized revenue
  founders: string;
  note: string;
  indirectPublic: string[]; // public tickers with exposure
}

export interface Etf {
  ticker: string;
  name: string;
  theme: string;
  expense: number;
  topHoldings: string[];
  ytd: number;
  oneYear: number;
  note: string;
}

export interface NewsItem {
  source: string;
  title: string;
  url: string;
  summary: string;
  published: number | null;
  provider: 'finnhub' | 'yahoo' | 'google' | string;
}

export interface NewsResponse {
  symbol: string | null;
  items: NewsItem[];
  fetchedAt: number;
}
