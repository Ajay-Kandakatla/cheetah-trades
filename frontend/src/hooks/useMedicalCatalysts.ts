/* 🧬 Medical catalysts fetchers — GET /catalysts/medical (the board, polled
 * every 120 s while the tab is visible) and GET /catalysts/medical/{symbol}
 * (the ticker page's timeline, one read). Both routes are declared above the
 * /catalysts/{ticker} deep-dive route on the backend. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { useTabVisibility } from './useTabVisibility';
import type { MedBoard, MedSymbolPayload } from '../lib/medicalCatalysts';

export const MED_BOARD_POLL_MS = 120_000;

export function useMedicalBoard(days: number = 30) {
  const [data, setData] = useState<MedBoard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const visible = useTabVisibility();
  const alive = useRef(true);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/catalysts/medical?days=${days}`, { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as MedBoard;
      if (!alive.current) return;
      setData(j);
      setError(null);
    } catch (e: any) {
      if (alive.current) setError(e?.message ?? 'fetch failed');
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);

  useEffect(() => {
    if (!visible) return;
    setLoading(true);
    load();
    const t = setInterval(load, MED_BOARD_POLL_MS);
    return () => clearInterval(t);
  }, [visible, load]);

  return { data, error, loading, refetch: load };
}

export function useMedicalSymbol(symbol: string | null | undefined, days: number = 180) {
  const [data, setData] = useState<MedSymbolPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!symbol);

  useEffect(() => {
    if (!symbol) { setData(null); setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`${API}/catalysts/medical/${encodeURIComponent(symbol)}?days=${days}`, { cache: 'no-store' })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return (await r.json()) as MedSymbolPayload;
      })
      .then((j) => { if (!cancelled) setData(j); })
      .catch((e: any) => { if (!cancelled) setError(e?.message ?? 'fetch failed'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [symbol, days]);

  return { data, error, loading };
}
