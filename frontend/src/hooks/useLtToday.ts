/* useLtToday — the 📅 Long Term table's Today read (2026-11-13, Ajay: "Creat a table instead of cards so i can view
 * them quickly").
 *
 * ONE POST /chart-maps/live (the house card overlay: one snapshot, one cached-frames find, nothing written) over the
 * saved symbols on screen, at mount and then every CARD_LIVE_MS while the page is visible. No symbols → nothing asked
 * (owner-only / error / loading). A failed read keeps the last good answer; the poll stops on unmount. The board's own
 * GET stays ONE read on mount — this hook never touches it. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { CARD_LIVE_MS, CARD_LIVE_PATH } from '../lib/cardLive';
import type { LtLiveQuote } from '../lib/longTerm';

export type LtLive = { as_of?: string; quotes?: Record<string, LtLiveQuote> };

export function useLtToday(symbols: readonly string[]): LtLive | null {
  const key = symbols.join(',');
  const [live, setLive] = useState<LtLive | null>(null);
  useEffect(() => {
    if (!key) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const tick = () => {
      const hidden = typeof document !== 'undefined' && document.hidden;
      const go = hidden ? Promise.resolve() : fetch(`${API}${CARD_LIVE_PATH}`, {
        method: 'POST', credentials: 'include', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbols: key.split(',') }),
      }).then((r) => (r.ok ? r.json() : null)).then((j) => {
        if (alive && j && typeof j === 'object' && j.quotes && typeof j.quotes === 'object') setLive(j as LtLive);
      }).catch(() => undefined);
      go.finally(() => { if (alive) timer = setTimeout(tick, CARD_LIVE_MS); });
    };
    tick();
    return () => { alive = false; if (timer) clearTimeout(timer); };
  }, [key]);
  return live;
}
