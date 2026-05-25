import { useEffect, useState, useCallback } from 'react';
import { API } from '../lib/apiBase';

export type SoirSignal = 'BULLISH' | 'BEARISH' | 'WATCH' | 'NEUTRAL';

export type SoirRow = {
  symbol: string;
  spot?: number;
  put_oi?: number;
  call_oi?: number;
  put_vol?: number;
  call_vol?: number;
  soir?: number;
  soir_volume?: number;
  soir_percentile?: number | null;
  expected_move_pct?: number | null;
  atm_iv?: number | null;
  atm_straddle_premium?: number | null;
  trend?: 'up' | 'down' | 'neutral' | null;
  sepa_score?: number | null;
  signal?: SoirSignal;
  reason?: string;
  pillars?: {
    trend?: string | null;
    sentiment_pct?: number | null;
    fundamental_score?: number | null;
  };
  scanned_at?: string;
  percentile_source?: 'time_series' | 'cross_section';
  /** Which data feed sourced this row's chain. */
  _source?: 'massive' | 'yfinance';
  /** Trade plan from the SEPA scan when this ticker is also analyzed
   *  there. Lets the Options Pulse card show entry/stop levels without
   *  duplicating the chart-analysis logic. */
  trade_plan?: import('./useSepa').TradePlan | null;
};

export type SoirScan = {
  as_of: string | null;
  rows: SoirRow[];
  n: number;
  filter_signal?: string | null;
  message?: string;
};

/** Fetch the latest SOIR scan results, optionally filtered by signal. */
export function useOptionsPulse(signal?: SoirSignal) {
  const [data, setData] = useState<SoirScan | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const url = signal
        ? `${API}/options/soir?signal=${signal}&limit=200`
        : `${API}/options/soir?limit=200`;
      const r = await fetch(url, { cache: 'no-store' });
      if (!r.ok) {
        setData(null);
        return;
      }
      setData(await r.json());
    } finally {
      setLoading(false);
    }
  }, [signal]);

  useEffect(() => { load(); }, [load]);
  return { data, loading, refetch: load };
}

/** Single-ticker SOIR snapshot for the SEPA candidate page panel. */
export function useOptionsPulseForSymbol(symbol: string | null) {
  const [data, setData] = useState<SoirRow | null>(null);
  const [loading, setLoading] = useState(false);
  const [found, setFound] = useState<boolean>(true);

  useEffect(() => {
    if (!symbol) { setData(null); return; }
    setLoading(true);
    fetch(`${API}/options/soir/${encodeURIComponent(symbol)}`, { cache: 'no-store' })
      .then((r) => r.ok ? r.json() : null)
      .then((r) => {
        if (!r) { setData(null); setFound(false); return; }
        setFound(!!r.found);
        setData(r.found ? r : null);
      })
      .finally(() => setLoading(false));
  }, [symbol]);

  return { data, loading, found };
}

/** Synchronously scan ONE ticker's options chain and return the SOIR
 *  snapshot. With the $200 Massive Options Advanced plan (2026-05-24)
 *  a chain pull is ~200ms, so we can block on the request and get the
 *  result back in one round-trip — no polling needed. Returns the
 *  fully-classified SoirRow with `found: true` on success.
 *
 *  Used by `OptionsFlowPanel` for the "Scan options flow" CTA. The older
 *  `refreshOptionsPulse(symbols?)` fire-and-forget path stays below for
 *  the nightly cron's full-universe scan. */
export async function scanOneSymbolOptions(
  symbol: string,
): Promise<SoirRow & { found: boolean; message?: string }> {
  const r = await fetch(
    `${API}/options/soir/scan_one/${encodeURIComponent(symbol)}`,
    { method: 'POST', cache: 'no-store' },
  );
  if (!r.ok) throw new Error(`scan_one failed: ${r.status}`);
  return r.json();
}


/** Trigger a background SOIR refresh. Resolves immediately — poll the
 *  list endpoint to see results once the scan finishes. */
export async function refreshOptionsPulse(symbols?: string[]): Promise<{ status: string; message: string }> {
  const url = symbols && symbols.length
    ? `${API}/options/soir/refresh?symbols=${encodeURIComponent(symbols.join(','))}`
    : `${API}/options/soir/refresh`;
  const r = await fetch(url, { method: 'POST' });
  if (!r.ok) throw new Error(`refresh failed: ${r.status}`);
  return r.json();
}


/* --------------------------------------------------------------------------
   Historical scrub — mirrors useSepaRuns / useSepaScanByDate shape.
   -------------------------------------------------------------------------- */

export type SoirRun = {
  date: string;          // ISO YYYY-MM-DD
  n_symbols: number;
};

export type SoirHistoricalScan = {
  date: string;
  n_symbols: number;
  rows: SoirRow[];
  n_bullish: number;
  n_bearish: number;
  n_watch: number;
};

/** List of dates we have SOIR history for. Newest first. */
export function useSoirRuns(limit = 60) {
  const [runs, setRuns] = useState<SoirRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/options/soir/history/runs?limit=${limit}`, { cache: 'no-store' })
      .then((r) => r.ok ? r.json() : { runs: [] })
      .then((d) => { if (!cancelled) setRuns(d.runs || []); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [limit]);

  return { runs, loading };
}

/** Pull the full SOIR snapshot for a given date. null = live (today). */
export function useSoirScanByDate(date: string | null) {
  const [scan, setScan] = useState<SoirHistoricalScan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!date) { setScan(null); return; }
    setLoading(true);
    setError(null);
    fetch(`${API}/options/soir/history/date/${date}`, { cache: 'no-store' })
      .then(async (r) => {
        if (r.status === 404) { setScan(null); setError(`No SOIR history for ${date}`); return; }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        setScan(await r.json());
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [date]);

  return { scan, loading, error };
}

/** Per-ticker SOIR trajectory for charting on the SEPA candidate page. */
export function useSoirSymbolHistory(symbol: string | null, days = 90) {
  const [snapshots, setSnapshots] = useState<SoirRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!symbol) { setSnapshots([]); return; }
    setLoading(true);
    fetch(`${API}/options/soir/history/${encodeURIComponent(symbol)}?days=${days}`, { cache: 'no-store' })
      .then((r) => r.ok ? r.json() : { snapshots: [] })
      .then((d) => setSnapshots(d.snapshots || []))
      .finally(() => setLoading(false));
  }, [symbol, days]);

  return { snapshots, loading };
}
