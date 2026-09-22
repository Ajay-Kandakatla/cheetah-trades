/* usePromoOriginTags — which names entered the scan universe through the
 * 🎪 promo-circuit curation lane, as a symbol lookup, so every board that
 * already shows the 🚀 growth chip can also say HOW a name got here.
 *
 * Ajay 2026-09-21: "check if we can use them and ... add them to our list as
 * they come through". The lane adds them; this chip is the honesty label on
 * the row — a promo tag is promotion, never foresight.
 *
 * Same shape as useGrowthTags: module-level cache with an in-flight promise,
 * so a 40-tile grid fires ONE request on first paint, not forty.
 *
 * A failure is SILENT and yields an empty map — the chip is decoration on
 * somebody else's board, and a catalysts outage must never blank a demand
 * board or change what a row looks like it qualifies for.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type PromoOriginTag = {
  accounts?: string[] | null;
  tier?: string | null;
  first_tagged_at?: string | null;
  added_at?: string | null;
};
export type PromoMeasured = { verdict?: string | null } & Record<string, unknown>;
export type PromoOriginPayload = {
  tags: Record<string, PromoOriginTag>;
  measured: PromoMeasured | null;
};

const EMPTY: PromoOriginPayload = { tags: {}, measured: null };

let cache: PromoOriginPayload | null = null;
let inFlight: Promise<PromoOriginPayload> | null = null;

export function _resetPromoOriginCache() {   // tests only
  cache = null;
  inFlight = null;
}

export function fetchPromoOriginTags(): Promise<PromoOriginPayload> {
  if (cache) return Promise.resolve(cache);
  if (inFlight) return inFlight;
  inFlight = fetch(`${API}/catalysts/promo-curate/tags`)
    .then((r) => (r.ok ? r.json() : EMPTY))
    .then((j) => {
      cache = {
        tags: (j?.tags ?? {}) as Record<string, PromoOriginTag>,
        measured: (j?.measured ?? null) as PromoMeasured | null,
      };
      return cache;
    })
    .catch(() => {
      cache = EMPTY;         // cache the miss too: do not retry per tile
      return cache;
    })
    .finally(() => { inFlight = null; });
  return inFlight;
}

export function usePromoOriginTags(): PromoOriginPayload {
  const [payload, setPayload] = useState<PromoOriginPayload>(() => cache ?? EMPTY);
  useEffect(() => {
    let alive = true;
    void fetchPromoOriginTags().then((p) => { if (alive) setPayload(p); });
    return () => { alive = false; };
  }, []);
  return payload;
}

/** The chip for one symbol, or null when the name did not enter through the
 *  lane (the common case). The sentence says how it entered and what that is
 *  worth — never that the tag is a reason to buy, and never that the lane is
 *  the ONLY way the name could have got here. */
export function promoOriginChip(payload: PromoOriginPayload, symbol: string):
    { text: string; title: string } | null {
  const t = payload?.tags?.[(symbol || '').toUpperCase()];
  if (!t) return null;
  const accounts = Array.isArray(t.accounts) ? t.accounts.filter(Boolean) : [];
  const who = accounts.length
    ? `@${accounts[0]}${accounts.length > 1 ? ` +${accounts.length - 1} more` : ''}`
    : 'the promo-circuit roster';
  const tier = t.tier || '—';
  const when = (t.first_tagged_at || '').slice(0, 10) || '—';
  const verdict = payload?.measured?.verdict || 'measurement pending';
  return {
    text: '🎪 promo',
    title: `Entered the scan universe through the promo-circuit lane — tagged by `
      + `${who} (tier ${tier}) on ${when}; the tag is promotion, never foresight. `
      + `Measured: ${verdict}. Not a pick.`,
  };
}
