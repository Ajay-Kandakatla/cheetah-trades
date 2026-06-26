/* useOpex — OpEx mechanics for one ticker (GET /options/opex/{symbol}):
 * nearest expiration + max-pain magnet + dealer-gamma pin/amplify read. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import type { ExpiryType } from '../lib/opex';

export type OpexData = {
  found: boolean;
  symbol: string;
  spot?: number | null;
  expiration_date: string;
  expiration_type: ExpiryType;
  days_to_expiry: number;
  max_pain: {
    max_pain_strike: number;
    max_pain_total_dollars?: number | null;
    strike_count: number;
    total_oi: number;
    max_pain_tie: boolean;
    pct_from_spot?: number | null;
  } | null;
  gamma: {
    net_gex_dollars: number;
    regime: 'pinning' | 'amplifying';
    call_wall?: number | null;
    put_wall?: number | null;
    magnet_strike?: number | null;
    oi_coverage_pct: number;
  } | null;
  gex_reliability: 'index' | 'single_name';
  as_of?: string;
  note?: string;
  message?: string;
};

export function useOpex(symbol: string | null) {
  const [data, setData] = useState<OpexData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!symbol) { setData(null); return; }
    let alive = true;
    setLoading(true);
    fetch(`${API}/options/opex/${encodeURIComponent(symbol)}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive) setData(j); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [symbol]);

  return { data, loading };
}
