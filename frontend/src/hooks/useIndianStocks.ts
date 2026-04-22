import { useCallback, useEffect, useState } from 'react';
import type { IndianMarketResponse } from '../types';

export function useIndianStocks() {
  const [data, setData] = useState<IndianMarketResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch('/indian-stocks', { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const json: IndianMarketResponse = await r.json();
      setData(json);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch Indian market data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
    const id = setInterval(refetch, 60_000); // refresh every 60s
    return () => clearInterval(id);
  }, [refetch]);

  return {
    stocks: data?.stocks ?? null,
    indices: data?.indices ?? [],
    fetchedAt: data?.fetchedAt ?? null,
    loading,
    error,
    refetch,
  };
}
