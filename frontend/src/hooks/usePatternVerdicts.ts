/* usePatternVerdicts — shared symbol→verdict lookup from the latest 🎯 pattern
 * verdict scan (GET /patterns/qualifiers). Powers the pattern chips/columns on
 * Portfolio, Leaderboard and Top Picks (Ajay 2026-06-09: "cross linking of the
 * stock tickers in to the patterns and the other way around"). Fails quiet —
 * pages render unchanged when no verdict scan has been run yet. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type PatternMatch = {
  symbol?: string; pattern: string; status: 'confirmed' | 'forming';
  neckline: number; pattern_low: number; target: number; stop: number; last_close: number;
  confirmed_date?: string; bars_since_confirm?: number; ext_past_confirm_pct?: number;
  to_confirm_pct?: number;
};
export type PatternFormation = { name: string; date: string; read: string; note: string; stat?: string };
export type PatternVerdict = {
  symbol: string;
  matches: PatternMatch[];
  candles?: { formations: PatternFormation[]; last_bar?: { read?: string } | null } | null;
  no_match: boolean;
  sources?: string[];
};

let cache: { at: number; map: Map<string, PatternVerdict>; generatedAt: number | null } | null = null;
const CACHE_MS = 60_000;   // verdicts only change when the owner re-scans

export function usePatternVerdicts(): { verdicts: Map<string, PatternVerdict>; generatedAt: number | null } {
  const [state, setState] = useState<{ map: Map<string, PatternVerdict>; generatedAt: number | null }>(
    cache ? { map: cache.map, generatedAt: cache.generatedAt } : { map: new Map(), generatedAt: null },
  );

  useEffect(() => {
    let alive = true;
    if (cache && Date.now() - cache.at < CACHE_MS) return;
    fetch(`${API}/patterns/qualifiers`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => {
        const map = new Map<string, PatternVerdict>();
        for (const v of d?.verdicts || []) map.set((v.symbol || '').toUpperCase(), v);
        cache = { at: Date.now(), map, generatedAt: d?.generated_at || null };
        if (alive) setState({ map, generatedAt: cache.generatedAt });
      })
      .catch(() => undefined);   // fail quiet
    return () => { alive = false; };
  }, []);

  return { verdicts: state.map, generatedAt: state.generatedAt };
}

export function patternRank(v?: PatternVerdict | null): number {
  /* sortable strength: 0 confirmed pattern, 1 forming, 2 candle read only, 3 nothing */
  if (!v) return 3;
  if (v.matches?.some((m) => m.status === 'confirmed')) return 0;
  if (v.matches?.length) return 1;
  if (v.candles?.formations?.length) return 2;
  return 3;
}
