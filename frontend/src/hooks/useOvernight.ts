import { useEffect, useState, useCallback } from 'react';
import { API } from '../lib/apiBase';
import { readCache, writeCache } from '../lib/swrCache';


export type OvernightCatalyst = {
  category: string;
  category_key?: string;
  headline?: string | null;
  publisher?: string | null;
  url?: string | null;
  published_utc?: string | null;
  score?: number;
  all_candidates?: Array<{ category: string; headline: string; publisher?: string; url?: string }>;
};

export type NewsLink = {
  title: string;
  url: string | null;
  publisher?: string | null;
  published_utc?: string | null;
};

/** Optional SOIR snapshot decoration. Backend attaches this to each mover
 *  when the cached options scan has a record for the ticker. Lets the
 *  overnight tape show "this gapper also has a Schaeffer signal" inline. */
export type SoirPulseSlim = {
  soir?: number | null;
  soir_percentile?: number | null;
  expected_move_pct?: number | null;
  atm_iv?: number | null;
  signal?: 'BULLISH' | 'BEARISH' | 'WATCH' | 'NEUTRAL';
  reason?: string;
};

export type OvernightMover = {
  symbol: string;
  yesterday_close: number;
  yesterday_close_ts: string;
  premarket_last: number | null;
  premarket_last_ts?: string | null;
  premarket_high?: number | null;
  premarket_low?: number | null;
  premarket_bars: number;
  gap_pct: number | null;
  catalyst: OvernightCatalyst | null;
  earnings_flag?: { flagged: boolean; title?: string; url?: string; published?: string } | null;
  premarket_sparkline: { ts: string; px: number }[];
  news_links?: NewsLink[];
  soir_pulse?: SoirPulseSlim;
  _cached?: boolean;
  _cache_age_sec?: number;
};

export type OvernightResponse = {
  as_of: string;
  min_gap_pct: number;
  n_scanned: number;
  n_moved: number;
  n_cached?: number;
  cache_ttl_min?: number;
  force_used?: boolean;
  active_ttl_sec?: number;
  market_phase?: 'premarket' | 'regular_hours' | 'closed';
  movers: OvernightMover[];
};

/** Currently in active premarket (4:00–9:30am ET on a weekday)? Used to
 *  auto-bypass cache on first mount + tighten the polling interval so
 *  the user sees fresh data during the only window that matters. */
function _isPremarketET(): boolean {
  // Format the current time in NY tz, then parse hour/min/weekday.
  // Intl.DateTimeFormat is the cheapest way to get a tz-aware time on the client.
  try {
    const fmt = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      hour: 'numeric', minute: 'numeric', hour12: false, weekday: 'short',
    });
    const parts = Object.fromEntries(fmt.formatToParts(new Date()).map((p) => [p.type, p.value]));
    const dow = parts.weekday;          // "Mon" .. "Sun"
    const h = parseInt(parts.hour, 10); // 0-23
    const m = parseInt(parts.minute, 10);
    if (['Sat', 'Sun'].includes(dow)) return false;
    const minutes = h * 60 + m;
    return minutes >= 4 * 60 && minutes < 9 * 60 + 30;
  } catch { return false; }
}

export function useOvernightMovers(opts?: { minGapPct?: number; includeSepa?: boolean }) {
  const minGap = opts?.minGapPct ?? 0.5;
  const includeSepa = opts?.includeSepa ?? true;
  const cacheKey = `overnight.movers.${minGap}.${includeSepa}`;

  // SWR — render last-known movers list IMMEDIATELY from localStorage,
  // then revalidate. Phone first-paint went from "Loading..." for 5-15s
  // to instant render of yesterday's gap list.
  const [data, setData] = useState<OvernightResponse | null>(() => {
    const env = readCache<OvernightResponse>(cacheKey);
    return env?.data ?? null;
  });
  const [loading, setLoading] = useState(() => readCache<OvernightResponse>(cacheKey) === null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (force = false) => {
    if (force) setRefreshing(true);
    try {
      const url = `${API}/overnight/movers?min_gap_pct=${minGap}&include_sepa=${includeSepa}${force ? '&force=true' : ''}`;
      const r = await fetch(url, { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const fresh = await r.json();
      setData(fresh);
      writeCache(cacheKey, fresh);
      setError(null);
    } catch (e) { setError(String(e)); } finally { setLoading(false); setRefreshing(false); }
  }, [minGap, includeSepa, cacheKey]);

  useEffect(() => {
    // First load — force during premarket so the user always sees fresh
    // data when it actually matters. Outside premarket, accept cache.
    load(_isPremarketET());
    // Poll cadence — 60s during premarket (matching the 2-min backend TTL),
    // 5min everywhere else (matches old behavior).
    const intervalMs = _isPremarketET() ? 60_000 : 5 * 60_000;
    const t = setInterval(() => load(false), intervalMs);
    return () => clearInterval(t);
  }, [load]);

  return { data, loading, refreshing, error, refetch: load, forceRefresh: () => load(true) };
}
