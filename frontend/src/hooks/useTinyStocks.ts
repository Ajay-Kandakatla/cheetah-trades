import { useEffect, useState, useCallback } from 'react';
import { API } from '../lib/apiBase';

export type TinyTier = 'TINY_STRONG' | 'TINY_BUY' | 'TINY_WATCH';

export type TinyComponent =
  | 'canslim' | 'tiny_titans' | 'pioneer'
  | 'catalyst' | 'frenzy' | 'insider' | 'float';

export type TinyCandidate = {
  symbol: string;
  name: string | null;
  tiny_score: number;
  tiny_tier: TinyTier;
  tiny_components: Partial<Record<TinyComponent, number>>;
  tiny_narrative: string;
  rs_rank: number | null;
  last_close: number | null;
  day_change_pct: number | null;
  adr_pct: number | null;
  rating: string | null;
  score: number | null;
  stage: any;
  pioneer_themes: string[];
  is_pioneer: boolean;
  catalyst: any;
  entry_setup: { type?: string; pivot?: number; stop?: number } | null;
};

export type TinyMethodology = {
  name: string;
  max_score: number;
  components: { name: string; weight: number; source: string }[];
  tiers: { label: string; min_score: number; interpretation: string }[];
  hard_gates: string[];
};

export function useTinyList(minTier: TinyTier = 'TINY_WATCH', limit = 50) {
  const [rows, setRows] = useState<TinyCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generatedAt, setGeneratedAt] = useState<number | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API}/tiny/list?min_tier=${minTier}&limit=${limit}`);
      if (!r.ok) throw new Error(`tiny/list ${r.status}`);
      const j = await r.json();
      setRows(j.rows || []);
      setGeneratedAt(j.generated_at ?? null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [minTier, limit]);

  useEffect(() => { refetch(); }, [refetch]);
  return { rows, loading, error, generatedAt, refetch };
}

export function useTinyMethodology() {
  const [data, setData] = useState<TinyMethodology | null>(null);
  useEffect(() => {
    let alive = true;
    fetch(`${API}/tiny/methodology`)
      .then((r) => r.json())
      .then((j) => { if (alive) setData(j); });
    return () => { alive = false; };
  }, []);
  return data;
}
