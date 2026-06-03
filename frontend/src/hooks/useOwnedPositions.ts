/* useOwnedPositions — connects the user's portfolio to the SEPA surfaces.
   Ajay 2026-06-03: "connect my portfolio stocks to the SEPA list to give
   relevant feedback on the card + details since I already invest in them."

   One shared /portfolio/holdings fetch is cached at module scope, so the SEPA
   list (many cards) and the detail page all resolve their "do I own this?"
   answer from a single request. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import type { HoldingRow } from './usePortfolio';

let _cache: Record<string, HoldingRow> | null = null;
let _promise: Promise<Record<string, HoldingRow>> | null = null;

function fetchOwned(): Promise<Record<string, HoldingRow>> {
  if (_cache) return Promise.resolve(_cache);
  if (!_promise) {
    _promise = fetch(`${API}/portfolio/holdings`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : { rows: [] }))
      .then((d: { rows?: HoldingRow[] }) => {
        const map: Record<string, HoldingRow> = {};
        for (const h of d.rows ?? []) {
          if (h.symbol) map[String(h.symbol).toUpperCase()] = h;
        }
        _cache = map;
        return map;
      })
      .catch(() => {
        _cache = {};
        return {} as Record<string, HoldingRow>;
      });
  }
  return _promise;
}

/** Drop the cached holdings — call after a portfolio edit so SEPA badges refresh. */
export function invalidateOwnedPositions(): void {
  _cache = null;
  _promise = null;
}

/** The user's position in `symbol` if they own it, else null. */
export function useOwnedPosition(symbol?: string | null): HoldingRow | null {
  const [pos, setPos] = useState<HoldingRow | null>(null);
  useEffect(() => {
    if (!symbol) { setPos(null); return; }
    let alive = true;
    fetchOwned().then((map) => { if (alive) setPos(map[symbol.toUpperCase()] ?? null); });
    return () => { alive = false; };
  }, [symbol]);
  return pos;
}
