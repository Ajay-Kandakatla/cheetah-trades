import { useEffect, useState, useCallback } from 'react';
import { API } from '../lib/apiBase';

/* SEPA history hook — wraps the four /sepa/history/* endpoints the
   backend already exposes (see backend/sepa/history.py). */

export type RunSummary = {
  _id: string;
  generated_at: number;
  generated_at_iso: string;
  date_et: string;
  candidate_count: number | null;
  analyzed: number | null;
  universe_size: number | null;
  duration_sec: number | null;
  has_catalyst: boolean;
  market_context?: { label?: string; safe_to_long?: boolean } | null;
};

export type ScoreDelta = {
  symbol: string;
  delta: number;
  from: number | null;
  to: number | null;
};

export type DiffResult = {
  from_date: string;
  to_date: string;
  entered: string[];
  exited: string[];
  score_deltas: ScoreDelta[];
};

export type TickerSnapshot = {
  generated_at: number;
  date_et: string;
  symbol: string;
  score: number | null;
  rating: string | null;
  rs_rank: number | null;
  stage: number | null;
  stage_label: string | null;
  adr_pct: number | null;
};

export type DateScanCandidate = TickerSnapshot & {
  trend?: any;
  vcp?: any;
  entry_setup?: any;
  fundamentals?: any;
};

export type DateScan = {
  date_et: string;
  generated_at: number;
  candidate_count: number;
  analyzed: number;
  universe_size: number;
  market_context?: any;
  candidates: DateScanCandidate[];
};

/** List of historical scan runs (each has its date_et + candidate_count). */
export function useSepaRuns(limit = 60) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API}/sepa/history/runs?limit=${limit}`);
      if (!r.ok) throw new Error(`runs ${r.status}`);
      const j = await r.json();
      setRuns(j.runs || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => { refetch(); }, [refetch]);
  return { runs, loading, error, refetch };
}

/** Diff between two scan dates — entered / exited / score deltas. */
export function useSepaDiff(fromDate: string | null, toDate: string | null) {
  const [diff, setDiff] = useState<DiffResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (!fromDate || !toDate) { setDiff(null); return; }
    setLoading(true);
    setError(null);
    try {
      // Endpoint validates query params as `from` / `to` (aliased), not `from_date` / `to_date`.
      const url = `${API}/sepa/history/diff?from=${fromDate}&to=${toDate}`;
      const r = await fetch(url);
      if (!r.ok) throw new Error(`diff ${r.status}`);
      const j = await r.json();
      setDiff(j);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [fromDate, toDate]);

  useEffect(() => { refetch(); }, [refetch]);
  return { diff, loading, error, refetch };
}

/** Full scan from a given Eastern date — for the SEPA list date scrubber. */
export function useSepaScanByDate(date: string | null) {
  const [scan, setScan] = useState<DateScan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (!date) { setScan(null); return; }
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API}/sepa/history/date/${date}`);
      if (r.status === 404) { setScan(null); return; }
      if (!r.ok) throw new Error(`date scan ${r.status}`);
      setScan(await r.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => { refetch(); }, [refetch]);
  return { scan, loading, error, refetch };
}

/** Single-ticker score timeline (for sparkline + history view). */
export function useTickerHistory(symbol: string, days = 30) {
  const [snapshots, setSnapshots] = useState<TickerSnapshot[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!symbol) return;
    let alive = true;
    fetch(`${API}/sepa/history/${symbol}?days=${days}`)
      .then((r) => (r.ok ? r.json() : { snapshots: [] }))
      .then((j) => { if (alive) setSnapshots(j.snapshots || []); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [symbol, days]);

  return { snapshots, loading };
}
