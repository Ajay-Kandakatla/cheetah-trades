/* useResearch — fetches /research/patterns (bullish vs bearish pattern mining).
   Ajay 2026-06-04: a living research page validating the insider thesis and
   surfacing which app signals separate winners from losers. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type PatternRow = {
  key: string;
  label: string;
  family: string;
  hypothesis: 'bull' | 'bear';
  bull_pct: number | null;
  bear_pct: number | null;
  lift: number | null;
  bull_n: number;
  bear_n: number;
};

export type InsiderThesis = {
  ok: boolean;
  computed_at?: number;
  age_sec?: number;
  stale?: boolean;
  bull?: { n: number; any_form4_pct: number | null; open_market_buy_pct: number | null; cluster_buy_pct: number | null; recent_13d_pct: number | null };
  bear?: { n: number; any_form4_pct: number | null; open_market_buy_pct: number | null; cluster_buy_pct: number | null; recent_13d_pct: number | null };
  lift?: { any_form4: number | null; open_market_buy: number | null; cluster_buy: number | null; recent_13d: number | null };
} | null;

export type ResearchData = {
  ok: boolean;
  reason?: string;
  universe_n: number;
  cohort_n: number;
  universe_size?: number | null;
  scan_generated_at?: number | null;
  generated_at?: number;
  bull_return_band?: { min: number; max: number; median: number };
  bear_return_band?: { min: number; max: number; median: number };
  bull_symbols?: string[];
  bear_symbols?: string[];
  bullish_patterns: PatternRow[];
  bearish_patterns: PatternRow[];
  overlap_patterns: PatternRow[];
  all_patterns: PatternRow[];
  insider_thesis: InsiderThesis;
};

export function useResearch() {
  const [data, setData] = useState<ResearchData | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetch(`${API}/research/patterns`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j: ResearchData) => { if (alive) { setData(j); setErr(null); } })
      .catch((e) => { if (alive) setErr(String(e?.message || e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  return { data, loading, err };
}
