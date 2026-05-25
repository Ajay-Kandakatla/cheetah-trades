/**
 * House dashboard hooks.
 *
 * The /house module is owner-only on the backend (returns 403 to anyone but
 * the configured owner email). All hooks gracefully handle 403 — useHouseAccess
 * returns `allowed: false` so the page can show "not available" instead of
 * crashing.
 */
import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type HouseConfig = {
  address?: string;
  city?: string;
  state?: string;
  zip?: string;
  list_price?: number;
  listed_on?: string;        // ISO date
  redfin_url?: string;
  zillow_url?: string;
  realtor_url?: string;
  mls_id?: string;
  agent_name?: string;
  agent_phone?: string;
  beds?: number;
  baths?: number;
  sqft?: number;
  lot_sqft?: number;
  year_built?: number;
  zestimate?: number;
  redfin_estimate?: number;
  notes?: string;
};

export type HouseSnapshot = {
  date_et: string;
  redfin_views?: number;
  redfin_saves?: number;
  redfin_tours?: number;
  zillow_views?: number;
  zillow_saves?: number;
  realtor_saves?: number;
  current_list_price?: number;
  open_houses_scheduled?: number;
  showings_today?: number;
  offers_received?: number;
  source?: string;
};

export type HouseComp = {
  _id?: string;
  address: string;
  sold_price?: number;
  sold_date?: string;
  beds?: number;
  baths?: number;
  sqft?: number;
  ppsf?: number;
  distance_mi?: number;
  notes?: string;
};

export type HouseEvent = {
  _id?: string;
  kind: 'open_house' | 'showing' | 'offer' | 'price_drop' | 'feedback' | 'note';
  label: string;
  value?: number | null;
  ts: number;
  notes?: string;
};

export type HousePlaybook = {
  address?: string;
  list_price?: number;
  listed_on?: string;
  dom: number;
  phase: 'launch' | 'reset' | 'reduce' | 'pivot';
  phase_label: string;
  platforms: {
    redfin:  { views?: number; saves?: number; tours?: number; prev_views?: number; prev_saves?: number; prev_tours?: number; url?: string };
    zillow:  { views?: number; saves?: number; prev_views?: number; prev_saves?: number; url?: string };
    realtor: { saves?: number; prev_saves?: number; url?: string };
  };
  totals: {
    views: number;
    saves: number;
    tours: number;
    interested_score: number;
  };
  velocity: {
    trend: 'heating' | 'cooling' | 'stable' | 'no_baseline' | 'insufficient_data';
    current_avg: number;
    prior_avg: number;
    delta_pct?: number;
  };
  comp_signal: {
    verdict?: string;
    comp_median_ppsf?: number;
    comp_count?: number;
    comp_min_ppsf?: number;
    comp_max_ppsf?: number;
  };
  checklist: Array<{
    id: string;
    label: string;
    why: string;
    priority: 'high' | 'med' | 'low';
  }>;
  strategy: string[];
  snapshot_count: number;
};

export type HouseDashboard = {
  config: HouseConfig;
  latest: HouseSnapshot | null;
  history: HouseSnapshot[];
  comps: HouseComp[];
  events: HouseEvent[];
  playbook: HousePlaybook;
};

export function useHouseDashboard() {
  const [data, setData] = useState<HouseDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [allowed, setAllowed] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API}/house/dashboard`);
      // Both 403 and 404 mean "not the owner" — backend stealth-gates as 404.
      if (r.status === 403 || r.status === 404) { setAllowed(false); setData(null); return; }
      if (!r.ok) { setError(`HTTP ${r.status}`); return; }
      const j = await r.json();
      setData(j);
      setAllowed(true);
    } catch (e: any) {
      setError(e?.message ?? 'fetch failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  return { data, loading, allowed, error, reload };
}

export async function saveHouseConfig(cfg: HouseConfig): Promise<void> {
  await fetch(`${API}/house/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg),
  });
}

export async function saveSnapshot(s: Partial<HouseSnapshot>): Promise<void> {
  await fetch(`${API}/house/snapshot`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(s),
  });
}

export async function runScrape(): Promise<{ ok: boolean; metrics?: any; reason?: string }> {
  const r = await fetch(`${API}/house/scrape`, { method: 'POST' });
  return r.json();
}

export async function addComp(comp: HouseComp): Promise<void> {
  await fetch(`${API}/house/comps`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(comp),
  });
}

export async function removeComp(address: string): Promise<void> {
  await fetch(`${API}/house/comps?address=${encodeURIComponent(address)}`, {
    method: 'DELETE',
  });
}

export async function addEvent(event: Partial<HouseEvent>): Promise<void> {
  await fetch(`${API}/house/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(event),
  });
}

export async function removeEvent(id: string): Promise<void> {
  await fetch(`${API}/house/events/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
}
