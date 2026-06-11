/**
 * Earnings-date map — GET /sepa/earnings-map, one fetch per session
 * (module-cached 10 min). {SYM: {date, days_to, when}} for names reporting
 * within 30 days. Built 2026-06-11 after ATEX reported the evening it was
 * bought: every buy surface now shows the ⚠ ER chip from this map.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type EarningsInfo = { date: string; days_to: number; when: 'BMO' | 'AMC' | null };

export const EARNINGS_WARN_DAYS = 7;

const _cache: { ts: number; map: Map<string, EarningsInfo> | null } = { ts: 0, map: null };
const TTL_MS = 10 * 60 * 1000;

export function useEarningsMap(): Map<string, EarningsInfo> {
  const [map, setMap] = useState<Map<string, EarningsInfo>>(() => _cache.map ?? new Map());

  useEffect(() => {
    let alive = true;
    if (_cache.map && Date.now() - _cache.ts < TTL_MS) {
      setMap(_cache.map);
      return;
    }
    fetch(`${API}/sepa/earnings-map`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((j: { map?: Record<string, EarningsInfo> }) => {
        if (!alive) return;
        const m = new Map(Object.entries(j.map || {}));
        _cache.ts = Date.now();
        _cache.map = m;
        setMap(m);
      })
      .catch(() => { /* silent — chips just don't render */ });
    return () => { alive = false; };
  }, []);

  return map;
}
