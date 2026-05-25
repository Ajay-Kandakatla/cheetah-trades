/* useSetupsByKind — fetches pending setups for a given backend `kind`
 * string (low_cheat, mid_cheat, bull_flag, peg, high_cheat,
 * episodic_pivot, post_earnings_drift, high_tight_flag). Used by the
 * SEPA page's setup-category tabs (Phase 2 of the Minervini setup
 * integration).
 *
 * Cache strategy: module-level Map keyed by kind so flipping back to a
 * previously-opened tab is instant. Cache survives across renders of
 * the consuming page but resets on a full reload — that's intentional;
 * the nightly cron repopulates each kind once a day, so a stale cache
 * across multiple page visits is fine.
 *
 * Pass `kind === null` for tabs that don't hit the API (the "all"
 * pass-through and the client-side "vcp" filter). The hook returns
 * an empty list with loading=false in that case.
 */
import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type Setup = {
  _id: string;
  kind: string;
  symbol: string;
  trigger: number;
  stop: number;
  target: number;
  rr: number;
  risk_pct: number;
  reward_pct: number;
  status: 'pending' | 'triggered' | 'expired' | 'stopped';
  generated_at: number;
  expires_at: number;
  meta?: Record<string, unknown>;
};

type CacheEntry = {
  setups: Setup[];
  fetchedAt: number;
};

// Module-level cache so tab flip-flopping doesn't refetch. Cleared on
// reload only; refresh() lets the user force a re-fetch from the UI.
const cache = new Map<string, CacheEntry>();

export function useSetupsByKind(kind: string | null): {
  setups: Setup[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
} {
  const [setups, setSetups] = useState<Setup[]>(() => {
    if (!kind) return [];
    return cache.get(kind)?.setups ?? [];
  });
  const [loading, setLoading] = useState<boolean>(() => {
    if (!kind) return false;
    return !cache.has(kind);
  });
  const [error, setError] = useState<string | null>(null);
  // Bump to force a re-fetch from refresh().
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => {
    if (!kind) return;
    cache.delete(kind);
    setTick((n) => n + 1);
  }, [kind]);

  useEffect(() => {
    if (!kind) {
      setSetups([]);
      setLoading(false);
      setError(null);
      return;
    }

    const cached = cache.get(kind);
    if (cached) {
      setSetups(cached.setups);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    const url = `${API}/setups/${kind}?only_pending=true&limit=100`;
    fetch(url, { credentials: 'include' })
      .then(async (r) => {
        if (!r.ok) {
          const t = await r.text().catch(() => '');
          throw new Error(t || `HTTP ${r.status}`);
        }
        return r.json();
      })
      .then((j) => {
        if (cancelled) return;
        const list = (j?.setups || []) as Setup[];
        cache.set(kind, { setups: list, fetchedAt: Date.now() });
        setSetups(list);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(String(e?.message || e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [kind, tick]);

  return { setups, loading, error, refresh };
}

/** Read-only view of cached counts. Used to render badge numbers next
 *  to tabs without forcing an extra fetch — only tabs that have been
 *  opened at least once will show a count. */
export function getCachedSetupCount(kind: string): number | null {
  return cache.get(kind)?.setups.length ?? null;
}
