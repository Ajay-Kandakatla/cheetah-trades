/**
 * Aggregated giant-fund 13F flows — GET /giants/flows, module-cached.
 *
 * The backend doc is rebuilt nightly (cron 17:35) from full SEC EDGAR
 * 13F-HR portfolios of the curated Tier S/A funds, and self-heals when
 * stale. The FIRST ever build downloads ~6 quarters × 38 funds and takes
 * 15-40 min — while `refreshing` is true this hook re-polls every 45s so
 * the section fills in without a manual reload.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type GiantMove = {
  fund: string;
  tier: 'S' | 'A';
  style: 'picker' | 'quant' | 'activist';
  usd: number;
  action: 'new' | 'add' | 'trim' | 'exit';
  pct_change_shares: number | null;
};

export type GiantsFlowRow = {
  ticker: string;
  name: string;
  net_usd: number;
  buy_usd: number;
  sell_usd: number;
  n_buying: number;
  n_selling: number;
  buyers: GiantMove[];
  sellers: GiantMove[];
  timeline: { q: string; net_usd: number }[];
};

export type GiantsFundRow = {
  cik: number;
  fund: string;
  name: string;
  tier: 'S' | 'A';
  style: string;
  manager: string;
  latest_period: string | null;
  latest_filed: string | null;
  n_positions: number;
  total_value: number;
  n_quarters_cached: number;
  top_adds: { ticker: string | null; name: string; delta_usd: number }[];
  top_trims: { ticker: string | null; name: string; delta_usd: number }[];
};

export type GiantsFlowsDoc = {
  as_of?: string;
  quarters: string[];
  latest_quarter?: string | null;
  rows_in: GiantsFlowRow[];
  rows_out: GiantsFlowRow[];
  by_quarter?: {
    q: string;
    top_in: { ticker: string; net_usd: number; n_buying: number }[];
    top_out: { ticker: string; net_usd: number; n_selling: number }[];
  }[];
  funds: GiantsFundRow[];
  n_funds: number;
  n_funds_with_data?: number;
  refreshing?: boolean;
  refresh_progress?: { done: number; of: number } | null;
  disclaimer?: string;
  note?: string;
};

const _cache: { ts: number; doc: GiantsFlowsDoc | null } = { ts: 0, doc: null };
const TTL_MS = 5 * 60 * 1000;
const RETRY_WHILE_REFRESHING_MS = 45 * 1000;

export function useGiantsFlows(): { doc: GiantsFlowsDoc | null; error: boolean } {
  const [doc, setDoc] = useState<GiantsFlowsDoc | null>(_cache.doc);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const doFetch = () => {
      fetch(`${API}/giants/flows`)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((j: GiantsFlowsDoc) => {
          if (!alive) return;
          _cache.ts = Date.now();
          _cache.doc = j;
          setDoc(j);
          if (j.refreshing) timer = setTimeout(doFetch, RETRY_WHILE_REFRESHING_MS);
        })
        .catch(() => alive && setError(true));
    };

    if (_cache.doc && Date.now() - _cache.ts < TTL_MS && !_cache.doc.refreshing) {
      setDoc(_cache.doc);
    } else {
      doFetch();
    }
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, []);

  return { doc, error };
}
