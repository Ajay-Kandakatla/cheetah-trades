/* useGexBoard — the cross-sectional dealer-gamma board + on-demand refresh.
 * GET /options/gex-board is a cheap Mongo read (nightly 17:50 ET snapshot);
 * POST /options/gex-board/refresh re-sweeps the ~200-name universe over the
 * options key (~20-60s threaded) and the hook refetches when it lands. */
import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import type { BoardPayload } from '../lib/gexBoard';

export function useGexBoard() {
  const [data, setData] = useState<BoardPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const fetchBoard = useCallback(async () => {
    try {
      const r = await fetch(`${API}/options/gex-board`, { cache: 'no-store' });
      if (!r.ok) throw new Error(String(r.status));
      setData(await r.json());
      setErr(null);
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchBoard();
  }, [fetchBoard]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const r = await fetch(`${API}/options/gex-board/refresh`, { method: 'POST' });
      if (!r.ok) throw new Error(String(r.status));
      await fetchBoard();
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    } finally {
      setRefreshing(false);
    }
  }, [fetchBoard]);

  return { data, loading, refreshing, err, refresh };
}
