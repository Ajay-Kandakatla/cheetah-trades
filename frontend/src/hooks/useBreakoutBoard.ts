/* useBreakoutBoard — fetches the dedicated /breakouts page feed
 * (GET /sepa/breakout-board): every name that has broken out, ranked by
 * breakout COUNT (highest first), each carrying the Minervini+Bonde buy_verdict.
 * Display-only; one fetch with a manual reload. */
import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import type { BuyVerdict } from '../components/BuyVerdictChip';

export type BreakoutBoardRow = {
  symbol: string;
  name?: string | null;
  breakout_count: number;
  window_bars?: number;
  last_vol?: number | null;
  avg_vol_50?: number | null;
  days_since_breakout: number | null;
  high_vol_breakout: boolean;
  broke_out_today: boolean;
  last_close?: number | null;
  day_change_pct?: number | null;
  rs_rank?: number | null;
  stage?: number | null;
  stage_label?: string | null;
  industry?: string | null;
  is_etf?: boolean;
  buy_verdict?: BuyVerdict | null;
};

export type BreakoutBoardSummary = {
  total: number;
  broke_out_today: number;
  minervini_pass: number;
  minervini_fail: number;
  bonde_pass: number;
  bonde_fail: number;
  both_pass: number;
};

type Board = {
  rows: BreakoutBoardRow[];
  summary: BreakoutBoardSummary | null;
  scanTs: number | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
};

const EMPTY_SUMMARY: BreakoutBoardSummary = {
  total: 0, broke_out_today: 0, minervini_pass: 0, minervini_fail: 0,
  bonde_pass: 0, bonde_fail: 0, both_pass: 0,
};

export function useBreakoutBoard(top = 250, minCount = 1): Board {
  const [rows, setRows] = useState<BreakoutBoardRow[]>([]);
  const [summary, setSummary] = useState<BreakoutBoardSummary | null>(null);
  const [scanTs, setScanTs] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fetch(`${API}/sepa/breakout-board?top=${top}&min_count=${minCount}`, { credentials: 'include' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => {
        if (!alive) return;
        setRows(Array.isArray(j.rows) ? j.rows : []);
        setSummary(j.summary ?? EMPTY_SUMMARY);
        setScanTs(j.scan_ts ?? null);
        setLoading(false);
      })
      .catch((e) => {
        if (!alive) return;
        setError(String(e?.message || e));
        setLoading(false);
      });
    return () => { alive = false; };
  }, [top, minCount, nonce]);

  return { rows, summary, scanTs, loading, error, reload };
}
