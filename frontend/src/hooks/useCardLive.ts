/* useCardLive — the Chart Maps card poll (2026-10-16).
 *
 * Ajay 2026-10-16: "Can you make this chart more live please like when its 24
 * hour or todays entry" / "actual price is this  above but it stale value".
 *
 * POSTs the tickers on screen to /chart-maps/live on CARD_LIVE_MS while the
 * page is visible (CARD_LIVE_CLOSED_MS when the session is closed) and hands
 * back the last good answer plus the served footer word. It composes nothing:
 * the footer is `footer.live` / `footer.stale` exactly as served.
 *
 * Cadence rules (BUILD_SPEC8 §3.5 as amended by AMENDMENTS8):
 *  - C1: the session that paces the poll is the BOARD's stamp first
 *    (`initialSession`), then the last good overlay answer — a board refetch
 *    is newer than the overlay, so a tab left open across the close resumes
 *    the fast cadence at the next session.
 *  - C3: one tick right after every board refetch (a new `resetKey` once the
 *    poll has run before); the first board read waits one cadence.
 *  - D3 outranks C3 while closed: a refetch stamped "closed" waits out the rest
 *    of CARD_LIVE_CLOSED_MS since the last POST (the time lives in a ref that
 *    survives refetches), so the 5-min board refetch never turns the closed
 *    read into 12 POSTs an hour. Any other session ticks at once.
 *  - no request while `document.hidden`; none while one is in flight; the
 *    poll stops on unmount and an answer from a previous run is dropped.
 */
import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import type { CmTapeSession } from '../lib/chartMaps';
import { CARD_LIVE_PATH, nextCadence, parseCardLive, type CardLiveAnswer } from '../lib/cardLive';

export type CardLiveState = { answer: CardLiveAnswer | null; footer: string | null };

export function useCardLive(
  symbols: readonly string[],
  enabled: boolean,
  opts: { resetKey: unknown; initialSession?: CmTapeSession | null },
): CardLiveState {
  const key = symbols.join(',');
  const [answer, setAnswer] = useState<CardLiveAnswer | null>(null);
  const [footer, setFooter] = useState<string | null>(null);
  const lastGood = useRef<CardLiveAnswer | null>(null);
  const armed = useRef(false);
  const lastTickAt = useRef(0);  // the last POST (or the first arm): survives board refetches
  const symsRef = useRef(symbols);
  symsRef.current = symbols;
  const sessionRef = useRef<CmTapeSession | null | undefined>(opts.initialSession);
  sessionRef.current = opts.initialSession;

  // A new symbol set is a new board: forget the previous board's answer.
  useEffect(() => {
    lastGood.current = null;
    setFooter(null);
  }, [key]);

  useEffect(() => {
    setAnswer(null);  // the board refetch wins
    if (!enabled || !key) return;
    const refetch = armed.current;
    if (!armed.current) lastTickAt.current = Date.now();
    armed.current = true;

    let alive = true;
    let inFlight = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let ctrl: AbortController | null = null;
    let session: CmTapeSession | null = sessionRef.current ?? lastGood.current?.session ?? null;
    const body = JSON.stringify({ symbols: [...symsRef.current] });

    const schedule = (ms: number) => {
      if (!alive) return;
      if (timer != null) clearTimeout(timer);
      timer = setTimeout(() => { void tick(); }, ms);
    };

    const fail = () => {
      if (alive) setFooter(lastGood.current?.footer.stale ?? null);
    };

    const tick = async () => {
      timer = null;
      if (!alive) return;
      if (document.hidden || inFlight) { schedule(nextCadence(session)); return; }
      inFlight = true;
      lastTickAt.current = Date.now();
      ctrl = new AbortController();
      try {
        const r = await fetch(`${API}${CARD_LIVE_PATH}`, {
          method: 'POST', credentials: 'include', cache: 'no-store',
          headers: { 'Content-Type': 'application/json' }, body, signal: ctrl.signal,
        });
        if (!alive) return;
        const j = r.ok ? parseCardLive(await r.json()) : null;
        if (!alive) return;
        if (j && !j.fault) {
          lastGood.current = j;
          session = j.session ?? null;
          setAnswer(j);
          setFooter(j.footer.live ?? j.footer.stale ?? null);
        } else {
          fail();
        }
      } catch {
        fail();
      } finally {
        inFlight = false;
        ctrl = null;
        schedule(nextCadence(session));
      }
    };

    const onVisible = () => {
      if (!alive || document.hidden || inFlight) return;
      if (Date.now() - lastTickAt.current < nextCadence(session)) return;
      if (timer != null) { clearTimeout(timer); timer = null; }
      void tick();
    };

    const cadence = nextCadence(session);
    const first = refetch
      ? (session === 'closed' ? Math.max(0, cadence - (Date.now() - lastTickAt.current)) : 0)
      : cadence;
    schedule(first);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      alive = false;
      if (timer != null) clearTimeout(timer);
      ctrl?.abort();
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [key, enabled, opts.resetKey]);

  return { answer, footer };
}
