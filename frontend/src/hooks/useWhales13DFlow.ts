/**
 * Bulk lookup of recent SC 13D / 13G filings across cached tickers.
 *
 * Mirror of useWhalesFlow but for the 13D/G submissions cache (whales13d_cache
 * Mongo collection). Used by SEPA cards to render a "📜 13D" chip when a
 * ticker has had recent ownership-threshold filings within the lookback
 * window — the closest free real-time-ish institutional signal.
 *
 * Same shared-module-cache pattern: 60s TTL, listener-based invalidation,
 * silent fail (chip just doesn't render) when the endpoint is unreachable.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type Whales13DRow = {
  ticker:       string;
  n_filings:    number;       // total across all tracked forms
  n_form4:      number;       // Form 4 + 4/A (insider trades, 2-day lag)
  n_form144:    number;       // Form 144 (insider pre-sale notice)
  n_form13:     number;       // SC 13D / 13G + amendments (5% threshold)
  latest_form:  string;       // "4" | "144" | "SC 13D" | "SC 13G" | ...
  latest_date:  string;       // "YYYY-MM-DD"
  latest_url:   string | null;
};

const _moduleCache: { ts: number; map: Map<string, Whales13DRow> | null } = { ts: 0, map: null };
const TTL_MS = 60 * 1000;
const _listeners = new Set<(m: Map<string, Whales13DRow>) => void>();


export function useWhales13DFlow(windowDays: number = 90): Map<string, Whales13DRow> {
  const [map, setMap] = useState<Map<string, Whales13DRow>>(
    () => _moduleCache.map ?? new Map(),
  );

  useEffect(() => {
    let alive = true;
    const doFetch = () => {
      fetch(`${API}/supply-demand/13d-flow?days=${windowDays}`)
        .then((r) => r.ok ? r.json() : { rows: [] })
        .then((j: { rows: Whales13DRow[] }) => {
          const m = new Map<string, Whales13DRow>();
          for (const r of (j.rows || [])) {
            if (r.ticker) m.set(r.ticker.toUpperCase(), r);
          }
          _moduleCache.ts  = Date.now();
          _moduleCache.map = m;
          if (alive) setMap(m);
        })
        .catch(() => { /* silent — chip just doesn't render */ });
    };

    if (_moduleCache.map && Date.now() - _moduleCache.ts < TTL_MS) {
      setMap(_moduleCache.map);
    } else {
      doFetch();
    }

    const onUpdate = (next: Map<string, Whales13DRow>) => {
      if (!alive) return;
      if (next.size === 0 && _moduleCache.map === null) {
        doFetch();
        return;
      }
      setMap(next);
    };
    _listeners.add(onUpdate);
    return () => {
      alive = false;
      _listeners.delete(onUpdate);
    };
  }, [windowDays]);

  return map;
}
