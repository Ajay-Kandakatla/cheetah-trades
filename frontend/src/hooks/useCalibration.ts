import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

/* Hooks for the /learning/* endpoints — one per panel on the Calibration tab. */

export type CalibrationRow = {
  source: string;
  window_days: number;
  n: number;
  hits: number;
  partials: number;
  misses: number;
  hit_rate: number | null;
  weighted_hit_rate: number | null;
  avg_accuracy: number | null;
  recommended_weight: number;
  updated_at: number;
};

export type HistoryRow = {
  date_et: string;
  source: string;
  window_days: number;
  n: number;
  hit_rate: number | null;
  weighted_hit_rate: number | null;
};

export type ObservationRow = {
  source: string;
  ticker: string;
  ts: number;
  date_et: string;
  status: string;
  baseline_price: number | null;
  actual_price: number | null;
  actual_pct: number | null;
  predicted_pct: number;
  direction: string;
  value: number;
  accuracy_score: number | null;

  /* Enrichment fields — present when /learning/recent?enrich=true (default) */
  score?: number | null;
  rs_rank?: number | null;
  stage?: number | null;
  stage_label?: string | null;
  trend_passed?: number | null;
  failed_gates?: string[];
  vcp_summary?: string | null;
  entry_setup?: { type?: string; pivot?: number; stop?: number } | null;
  market_context?: string | null;
  tags?: string[];
  reason?: string;
};

export type TopWinner = {
  ticker: string;
  hits: number;
  avg_pct: number;
  best_pct: number;
  sources: string[];
  last_date: string;
  last_price?: number | null;
  last_price_date?: string | null;
};

export function useHeadline() {
  const [data, setData] = useState<{ by_window?: Record<number, CalibrationRow> } | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    fetch(`${API}/learning/headline`)
      .then((r) => r.json())
      .then((j) => { if (alive) setData(j); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);
  return { data, loading };
}

export function useScoreboard(window: number) {
  const [rows, setRows] = useState<CalibrationRow[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetch(`${API}/learning/scoreboard?window=${window}`)
      .then((r) => r.json())
      .then((j) => { if (alive) setRows(j.rows || []); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [window]);
  return { rows, loading };
}

export function useAccuracyHistory(source: string, window: number, days: number) {
  const [rows, setRows] = useState<HistoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetch(`${API}/learning/history?source=${encodeURIComponent(source)}&window=${window}&days=${days}`)
      .then((r) => r.json())
      .then((j) => { if (alive) setRows(j.rows || []); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [source, window, days]);
  return { rows, loading };
}

export function useObservations(opts: { status?: string; ticker?: string; source?: string; limit?: number }) {
  const [rows, setRows] = useState<ObservationRow[]>([]);
  const [loading, setLoading] = useState(true);
  const { status = 'all', ticker, source, limit = 50 } = opts;
  useEffect(() => {
    let alive = true;
    setLoading(true);
    const q = new URLSearchParams({ status, limit: String(limit) });
    if (ticker) q.set('ticker', ticker);
    if (source) q.set('source', source);
    fetch(`${API}/learning/recent?${q}`)
      .then((r) => r.json())
      .then((j) => { if (alive) setRows(j.rows || []); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [status, ticker, source, limit]);
  return { rows, loading };
}

export type MarketRow = {
  date_et: string;
  close: number;
  day_pct: number;
  cum_pct: number;
};

export type Insight = {
  kind: string;
  title: string;
  detail: string;
  tone: 'good' | 'neutral' | 'bad';
};

export function useMarketHistory(days = 60, symbol = 'SPY') {
  const [rows, setRows] = useState<MarketRow[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    fetch(`${API}/learning/market_history?days=${days}&symbol=${symbol}`)
      .then((r) => r.json())
      .then((j) => { if (alive) setRows(j.rows || []); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [days, symbol]);
  return { rows, loading };
}

export function useInsights(window: number) {
  const [data, setData] = useState<{ insights: Insight[]; total_n: number } | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    fetch(`${API}/learning/insights?window=${window}`)
      .then((r) => r.json())
      .then((j) => { if (alive) setData(j); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [window]);
  return { data, loading };
}

export function useTopWinners(days = 30, limit = 10) {
  const [rows, setRows] = useState<TopWinner[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    fetch(`${API}/learning/top_winners?days=${days}&limit=${limit}`)
      .then((r) => r.json())
      .then((j) => { if (alive) setRows(j.rows || []); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [days, limit]);
  return { rows, loading };
}
