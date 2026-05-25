import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type CompanyInfo = {
  symbol: string;
  name: string | null;
  summary: string | null;
  sector: string | null;
  industry: string | null;
  website: string | null;
  employees: number | null;
  country: string | null;
  city: string | null;
  state: string | null;
  ceo: string | null;
  exchange: string | null;
  currency: string | null;
  ipo_year: number | null;
  refreshed_at: number | null;
};

const _cache = new Map<string, CompanyInfo>();

export function useCompany(symbol: string | null | undefined) {
  const [info, setInfo] = useState<CompanyInfo | null>(
    symbol ? _cache.get(symbol.toUpperCase()) ?? null : null,
  );
  const [loading, setLoading] = useState(!info && !!symbol);

  useEffect(() => {
    if (!symbol) return;
    const t = symbol.toUpperCase();
    const cached = _cache.get(t);
    if (cached) { setInfo(cached); setLoading(false); return; }
    let alive = true;
    setLoading(true);
    fetch(`${API}/company/${encodeURIComponent(t)}`)
      .then((r) => r.json())
      .then((j: CompanyInfo) => {
        if (!alive) return;
        _cache.set(t, j);
        setInfo(j);
      })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [symbol]);

  return { info, loading };
}
