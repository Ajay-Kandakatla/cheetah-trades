import { useCallback, useEffect, useState } from 'react';
import type { CheetahResponse, CheetahStock } from '../types';

/**
 * Loads the Cheetah Score dataset from the backend /cheetah endpoint.
 * Backend recomputes scores live from FORMULA_WEIGHTS × bucket scores
 * on every request, so refetch() genuinely reruns the formulas.
 */
export function useCheetahStocks() {
  const [stocks, setStocks] = useState<CheetahStock[] | null>(null);
  const [weights, setWeights] = useState<Record<string, number> | null>(null);
  const [computedAt, setComputedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch('/cheetah', { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data: CheetahResponse = await r.json();
      setStocks(data.stocks);
      setWeights(data.weights);
      setComputedAt(data.computedAt);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { stocks, weights, computedAt, error, loading, refetch: load };
}
