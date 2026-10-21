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
 *
 * 🔴 `levels` (2026-10-21, BUILD_SPEC20 D2 — Ajay: "If something is Potential
 * add min on min for pricing and other updates to make them more realtime and
 * give us a better edge"): an OPTIONAL per-symbol {trigger, stop, tf} the caller
 * copies from its own served payload. It rides the POST body (never a URL) only
 * when at least one asked symbol carries one; absent → the body is exactly
 * {symbols} as before. Read from a ref at each tick, so a board refetch with new
 * levels is never answered against the old ones. It never changes the key.
 */
import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import type { CmTapeSession } from '../lib/chartMaps';
import { CARD_LIVE_PATH, nextCadence, parseCardLive, type CardLiveAnswer, type CardLiveLevels } from '../lib/cardLive';

export type CardLiveState = { answer: CardLiveAnswer | null; footer: string | null };

export function useCardLive(
  symbols: readonly string[],
  enabled: boolean,
  opts: { resetKey: unknown; initialSession?: CmTapeSession | null; levels?: CardLiveLevels | null },
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
  const levelsRef = useRef<CardLiveLevels | null | undefined>(opts.levels);
  levelsRef.current = opts.levels;

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
    /* The POST body: {symbols} — plus `levels` for the asked symbols that carry one, read at each tick. */
    const asked = [...symsRef.current];
    const bodyNow = (): string => {
      const lv = levelsRef.current;
      const levels: CardLiveLevels = {};
      if (lv && typeof lv === 'object') {
        for (const s of asked) if (Object.prototype.hasOwnProperty.call(lv, s) && lv[s]) levels[s] = lv[s];
      }
      return JSON.stringify(Object.keys(levels).length ? { symbols: asked, levels } : { symbols: asked });
    };

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
          headers: { 'Content-Type': 'application/json' }, body: bodyNow(), signal: ctrl.signal,
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
