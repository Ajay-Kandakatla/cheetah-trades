/* useGgLive — the 🚩 boards' `gajjala.update` listener (2026-11-09, GG LIVE §3.5).
 *
 * Ajay 2026-11-09: "same for reuglar Gajjlas tab as well need it to be more live".
 *
 * ONE subscription to the house bus (lib/eventBus — the singleton EventSource on /events) filtered to this board's
 * variant:
 *  - `quotesEvt`: every streamed price for THIS variant folded newer-wins (lib/cardLive.mergeQuotesEvt) — the board
 *    splices it into the poll's answer with lib/cardLive.patchQuotes; an older print never overwrites a newer one.
 *  - `passNudge`: a counter that moves ONCE per burst of `pass` nudges for THIS variant (two inside
 *    GG_PASS_NUDGE_DEBOUNCE_MS → one) — the board re-GETs and restarts its served-cadence interval.
 *  - `laneNudge`: the same for the data-free `lane` nudge (no variant on it; the lane tab's).
 * Composes nothing; every number and word it hands on is served. No EventSource in the runtime (a test DOM) → idle.
 */
import { useEffect, useRef, useState } from 'react';
import { subscribe, type BusEvent } from '../lib/eventBus';
import { GG_UPDATE_EVENT, mergeQuotesEvt, parseGgUpdate, type GgQuotesEvent } from '../lib/cardLive';

/** A `pass` / `lane` nudge burst is coalesced this long — two inside it → ONE re-read (spec §3.5). */
export const GG_PASS_NUDGE_DEBOUNCE_MS = 500;   // MINE — spec §3.5

export type GgLive = { quotesEvt: GgQuotesEvent | null; passNudge: number; laneNudge: number };

export function useGgLive(variant: string, enabled = true): GgLive {
  const [quotesEvt, setQuotesEvt] = useState<GgQuotesEvent | null>(null);
  const [passNudge, setPassNudge] = useState(0);
  const [laneNudge, setLaneNudge] = useState(0);
  const passTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const laneTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setQuotesEvt(null);
    if (!enabled || typeof EventSource === 'undefined') return;
    let alive = true;
    const off = subscribe(GG_UPDATE_EVENT, (evt: BusEvent) => {
      if (!alive) return;
      const u = parseGgUpdate(evt?.payload);
      if (!u) return;
      if (u.kind === 'quotes') {
        if (u.variant !== variant || !Object.keys(u.quotes).length) return;
        setQuotesEvt((prev) => mergeQuotesEvt(prev, u));
      } else if (u.kind === 'pass') {
        if (u.variant !== variant || passTimer.current != null) return;
        passTimer.current = setTimeout(() => {
          passTimer.current = null;
          if (alive) setPassNudge((n) => n + 1);
        }, GG_PASS_NUDGE_DEBOUNCE_MS);
      } else if (laneTimer.current == null) {
        laneTimer.current = setTimeout(() => {
          laneTimer.current = null;
          if (alive) setLaneNudge((n) => n + 1);
        }, GG_PASS_NUDGE_DEBOUNCE_MS);
      }
    });
    return () => {
      alive = false;
      off();
      if (passTimer.current != null) { clearTimeout(passTimer.current); passTimer.current = null; }
      if (laneTimer.current != null) { clearTimeout(laneTimer.current); laneTimer.current = null; }
    };
  }, [variant, enabled]);

  return { quotesEvt, passNudge, laneNudge };
}
