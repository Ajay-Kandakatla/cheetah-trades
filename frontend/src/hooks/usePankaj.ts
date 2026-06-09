/* usePankaj — fetches /pankaj/picks: a trusted outside analyst's (Pankaj's)
   curated picks, surfaced WITH the app's own SEPA indicators + a live price +
   where price sits vs each of his entry/stop/target levels. Ajay 2026-06-09:
   "a dude I trust — I want indicators against his stock picks." */
import { useEffect, useState, useCallback } from 'react';
import { API } from '../lib/apiBase';

export type SetupStatus = {
  state: 'unknown' | 'below' | 'approaching' | 'triggered' | 'below_zone' | 'in_zone' | 'above_zone';
  dist_pct: number | null;
  detail: string;
};

export type PankajSetup = {
  id: string;
  kind: 'breakout' | 'pullback';
  label: string;
  trigger?: number;
  confirm?: { conservative: string; aggressive: string };
  zone?: { lo: number; hi: number };
  targets?: { lo: number; hi: number }[];
  stops?: { aggressive: number; conservative: number };
  note?: string;
  extreme?: boolean;
  status: SetupStatus;
};

export type PankajIndicators = {
  in_scan: boolean;
  score?: number | null;
  rating?: string | null;
  rs_rank?: number | null;
  stage?: string | null;
  trend_pass_all?: boolean | null;
  trend_passed?: number | null;
  pivot?: number | null;
  is_candidate?: boolean | null;
  is_buyable?: boolean | null;
  day_change_pct?: number | null;
};

export type PankajPick = {
  symbol: string;
  name?: string | null;
  analyst?: string;
  updated?: string;
  horizon?: string;
  thesis?: string;
  price: number | null;
  indicators: PankajIndicators;
  setups: PankajSetup[];
};

export type PankajData = {
  ok: boolean;
  analyst: string;
  generated_at: number;
  scan_generated_at?: number | null;
  picks: PankajPick[];
  disclaimer: string;
};

export function usePankaj() {
  const [data, setData] = useState<PankajData | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    let alive = true;
    setLoading(true);
    fetch(`${API}/pankaj/picks`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j: PankajData) => { if (alive) { setData(j); setErr(null); } })
      .catch((e) => { if (alive) setErr(String(e?.message || e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  useEffect(() => load(), [load]);

  return { data, loading, err, refetch: load };
}
