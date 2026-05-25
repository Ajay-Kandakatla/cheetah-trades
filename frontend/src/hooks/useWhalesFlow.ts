/**
 * Bulk lookup of institutional flow signals (accumulating / distributing /
 * balanced) across every cached whales record. Used by SEPA cards to render
 * a small 🐋 chip without firing per-card requests.
 *
 * Data is sourced from the `whales_cache` Mongo collection — only tickers
 * the user has previously opened on supply/demand pages will be present.
 * Cards without flow data simply skip the chip.
 *
 * Staleness handling (added 2026-05-21 after user reported AMD card showed
 * "2/2 balanced, top sell JPMORGAN" while the modal showed "6 buying / 1
 * selling, JPMORGAN +16%"):
 *
 *   - The per-ticker /supply-demand/whales/{T} endpoint silently REFRESHES
 *     the Mongo cache from yfinance when it's >24h old, so opening the
 *     modal often updates the underlying data.
 *   - The bulk /supply-demand/whales-flow endpoint just reads the cache;
 *     no refresh side effect.
 *   - Without invalidation hooks, this hook's 5-min module cache holds
 *     the OLD bulk response even after the modal pulled fresh per-ticker
 *     data. The card chip then renders the stale numbers.
 *
 * Fix: expose ``patchWhalesFlowRow`` (one-row patch — used by WhalesFlowModal
 * after a fresh fetch) and ``invalidateWhalesFlow`` (nuke + refetch — used
 * if larger consistency is needed). Both notify subscribed hook instances
 * so the chip behind the modal updates in real time.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type WhalesFlowSignal = 'accumulating' | 'distributing' | 'balanced';

export type WhalesFlowRow = {
  ticker: string;
  signal: WhalesFlowSignal;
  n_buying: number;
  n_selling: number;
  n_unchanged?: number;
  top_buy?: string | null;
  top_sell?: string | null;
};

const _moduleCache: { ts: number; map: Map<string, WhalesFlowRow> | null } = { ts: 0, map: null };

// Shortened from 5 min → 60s. The data really does change when modals
// trigger refreshes, and a minute of staleness is far less surprising
// than five minutes when the user is actively clicking around the
// SEPA list. Listeners + patchRow give us instant updates anyway;
// this TTL is the fallback for cross-session freshness.
const TTL_MS = 60 * 1000;

// Subscribers — set of setMap functions from every mounted instance of
// useWhalesFlow. Lets patchRow / invalidate notify all consumers
// without a full refetch.
const _listeners = new Set<(m: Map<string, WhalesFlowRow>) => void>();


/**
 * Replace a single ticker's row in the shared map. Called by
 * WhalesFlowModal after it fetches fresh per-ticker data so the chip
 * on the card behind the modal updates immediately.
 *
 * Accepts a partial row; merges into the existing entry (preserves
 * fields the modal doesn't carry, like top_buy/top_sell strings if
 * the patch source omits them).
 */
export function patchWhalesFlowRow(ticker: string, patch: Partial<WhalesFlowRow>) {
  const t = ticker.toUpperCase();
  const m = _moduleCache.map ?? new Map<string, WhalesFlowRow>();
  const existing = m.get(t);
  // Take care to construct a fresh row even when there was no prior
  // entry — every required field has to be populated for downstream
  // chip rendering. Defaults match a "no signal" empty state.
  const merged: WhalesFlowRow = {
    ticker:      t,
    signal:      (patch.signal ?? existing?.signal ?? 'balanced'),
    n_buying:    (patch.n_buying ?? existing?.n_buying ?? 0),
    n_selling:   (patch.n_selling ?? existing?.n_selling ?? 0),
    n_unchanged: (patch.n_unchanged ?? existing?.n_unchanged),
    top_buy:     (patch.top_buy ?? existing?.top_buy ?? null),
    top_sell:    (patch.top_sell ?? existing?.top_sell ?? null),
  };
  // New Map so React notices the identity change and re-renders.
  const next = new Map(m);
  next.set(t, merged);
  _moduleCache.ts  = Date.now();
  _moduleCache.map = next;
  _listeners.forEach((fn) => fn(next));
}


/**
 * Force a full refetch of the bulk endpoint. Use when you suspect
 * the entire universe might be stale (e.g. after a long page idle).
 * Almost always you want patchWhalesFlowRow instead — surgical and
 * one round-trip cheaper.
 */
export function invalidateWhalesFlow() {
  _moduleCache.map = null;
  _moduleCache.ts  = 0;
  // Force every mounted hook to refetch on its next effect tick by
  // pushing an empty map; the hook's effect will see the cache is
  // empty and re-fetch.
  _listeners.forEach((fn) => fn(new Map()));
}


export function useWhalesFlow(): Map<string, WhalesFlowRow> {
  const [map, setMap] = useState<Map<string, WhalesFlowRow>>(
    () => _moduleCache.map ?? new Map(),
  );

  useEffect(() => {
    let alive = true;
    const doFetch = () => {
      fetch(`${API}/supply-demand/whales-flow`)
        .then((r) => r.ok ? r.json() : { rows: [] })
        .then((j: { rows: WhalesFlowRow[] }) => {
          const m = new Map<string, WhalesFlowRow>();
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

    // Subscribe to patches + invalidations from other components
    // (notably WhalesFlowModal pushing fresh per-ticker data).
    const onUpdate = (next: Map<string, WhalesFlowRow>) => {
      if (!alive) return;
      // Empty map = invalidation signal → refetch from server.
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
  }, []);

  return map;
}
