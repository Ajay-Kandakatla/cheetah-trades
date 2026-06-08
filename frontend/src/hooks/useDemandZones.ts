/**
 * useDemandZones — fetch the Minervini-basing demand-zone bands for the
 * leaderboard + day-trading universe.
 *
 * Backend: GET /supply-demand/demand-zones (cached 3h server-side). Each row is
 * a name's most-recent VCP base rendered as a [zone_low … zone_high] band, with
 * where the current price sits relative to it. Educational, not advice.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type ZoneStatus = 'in' | 'above' | 'below' | null;
export type DepthClass = 'shallow' | 'constructive' | 'deep' | 'failure_prone' | null;

export type DemandZoneRow = {
  symbol: string;
  name: string | null;
  source: 'leaderboard' | 'day' | 'both';
  last_close: number;
  has_zone: boolean;
  // The band (Minervini basing).
  zone_low: number | null;        // base floor (p.205 Fig 10.8)
  zone_high: number | null;       // pivot / breakout line (p.203)
  base_high: number | null;       // left-side high of the base
  base_depth_pct: number | null;
  depth_class: DepthClass;        // shallow | constructive | deep | failure_prone (p.211)
  // VCP quality context.
  n_contractions: number | null;
  final_contraction_pct: number | null;
  tightness: number | null;
  tightness_band: string | null;
  volume_drying: boolean | null;
  has_base: boolean | null;
  pivot_buy_price: number | null;
  suggested_stop: number | null;
  // Where price sits vs the band.
  in_zone: boolean;
  zone_status: ZoneStatus;
  zone_position_pct: number | null;   // 0 floor → 100 pivot (only when inside)
  distance_to_zone_pct: number | null; // 0 inside · + above pivot · - below floor
  pulled_back: boolean;
  // Supply/demand context.
  state: 'demand' | 'supply' | 'churning' | null;
  demand_score: number | null;
  dollar_vol: number | null;
};

export type DemandZonesPayload = {
  rows: DemandZoneRow[];
  counts: { in_zone: number; near: number; no_base: number };
  n: number;
  as_of: string;
  disclaimer: string;
  cached?: boolean;
};

export function useDemandZones() {
  const [data, setData] = useState<DemandZonesPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API}/supply-demand/demand-zones`, { credentials: 'include' })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((j: DemandZonesPayload) => {
        if (!cancelled) { setData(j); setError(null); }
      })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return { data, loading, error };
}
