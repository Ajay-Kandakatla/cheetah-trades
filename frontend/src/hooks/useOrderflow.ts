/* useOrderflow — the Tape snapshot for one ticker.
 * GET /orderflow/{symbol} serves the cached snapshot instantly; scan() POSTs
 * a fresh compute (a few seconds on typical names, up to ~30s on megacap
 * tape — the caller shows progress copy). Also fetches the accuracy ledger
 * once per mount for the measured-record strip. */
import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import type { TapeData } from '../lib/orderflow';

export type TapeAccuracy = {
  ok: boolean;
  verdicts?: Record<string, { n: number; hit_1d_pct: number | null; median_fwd_1d_pct: number | null;
    n_5d: number; hit_5d_pct: number | null; median_fwd_5d_pct: number | null }>;
  pending?: number;
  since?: string | null;
  disclaimer?: string;
};

export function useOrderflow(symbol: string | null) {
  const [data, setData] = useState<TapeData | null>(null);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [accuracy, setAccuracy] = useState<TapeAccuracy | null>(null);

  useEffect(() => {
    if (!symbol) { setData(null); return; }
    let alive = true;
    setLoading(true);
    fetch(`${API}/orderflow/${encodeURIComponent(symbol)}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive) setData(j); })
      .finally(() => { if (alive) setLoading(false); });
    fetch(`${API}/orderflow/ledger/accuracy`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive) setAccuracy(j); })
      .catch(() => {});
    return () => { alive = false; };
  }, [symbol]);

  const scan = useCallback(() => {
    if (!symbol || scanning) return;
    setScanning(true);
    fetch(`${API}/orderflow/${encodeURIComponent(symbol)}/scan`, { method: 'POST' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (j) setData(j); })
      .finally(() => setScanning(false));
  }, [symbol, scanning]);

  return { data, loading, scanning, scan, accuracy };
}
