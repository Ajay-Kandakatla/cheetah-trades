/* useGgwLive — the 👀 Gajjala's Watch live stream (2026-11-16, watch-live spec §3.5, WP-D).
 *
 * Ajay 2026-11-16: "Can you make the watch list charts live please" · "Realtime updates.. Like the 1 min chart I need it
 * to be live live.. per sec change" · "Also on the Watch list I need live volume to be shown at the bottom" · "Of each
 * chart".
 *
 * The SAME live stack the 🚩 boards ride (one socket → backend live_hub → `gajjala.update` quotes on the house bus →
 * /events), never a second one:
 *  - (a) ONE bus subscription per `enabled` (lib/eventBus — the singleton EventSource): every `quotes` batch whose
 *    variant is the watch tab (GGW_TAB) and that carries at least one quote is handed RAW to `onBatch` (the board folds
 *    it with lib/ggwLive.ggwApplyBatch — a fold of its own, so the summed `size` of each batch is never lost the way a
 *    newer-wins quote fold would lose it). Another variant, a `pass` or a `lane` nudge → nothing.
 *  - (b) the live interest: POST GGW_LIVE_PATH {symbols} (the owner-gated watch route → live_hub.register_interest) on
 *    arm and every CARD_LIVE_MS (the renewal half of the hub's INTEREST_TTL_SEC — no new number). Keyed on the symbol
 *    LIST (`symbols.join(',')`, the useCardLive pattern): a minute GET that serves the same list re-arms nothing; a
 *    changed list POSTs at once. A tick while the page is hidden re-schedules WITHOUT a POST; back to visible with the
 *    last POST older than CARD_LIVE_MS → POST now. Unmount / disabled → timer cleared, request aborted, unsubscribed; no
 *    unregister call (the interest expires on the hub).
 *  - `word`: the served feed sentence of the last answer's `stream` block via lib/cardLive.streamFeedWord — printed only
 *    when the feed is degraded. The hook types no word.
 * Idle (no POST, no subscription) without EventSource (a test DOM — the bus would throw), when disabled, or with no
 * symbols. DISPLAY ONLY, UNMEASURED. */
import { useEffect, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { subscribe, type BusEvent } from '../lib/eventBus';
import {
  CARD_LIVE_MS, GG_UPDATE_EVENT, parseGgUpdate, streamFeedWord, type CardLiveAnswer, type GgQuotesEvent,
} from '../lib/cardLive';
import { GGW_LIVE_PATH, GGW_TAB } from '../lib/gajjalaWatch';

/** One raw `quotes` batch of the watch tab, as parsed by lib/cardLive.parseGgUpdate. */
export type GgwBatch = GgQuotesEvent;

export function useGgwLive(
  symbols: readonly string[], enabled: boolean, onBatch: (evt: GgwBatch) => void,
): { word: string | null } {
  const key = symbols.join(',');
  const symsRef = useRef(symbols);
  symsRef.current = symbols;
  const onBatchRef = useRef(onBatch);
  onBatchRef.current = onBatch;
  const [word, setWord] = useState<string | null>(null);
  const on = enabled && key.length > 0 && typeof EventSource !== 'undefined';

  /* (a) the bus — once per arm, never per GET. */
  useEffect(() => {
    if (!on) return;
    let alive = true;
    const off = subscribe(GG_UPDATE_EVENT, (evt: BusEvent) => {
      if (!alive) return;
      const u = parseGgUpdate(evt?.payload);
      if (!u || u.kind !== 'quotes' || u.variant !== GGW_TAB || !Object.keys(u.quotes).length) return;
      onBatchRef.current(u);
    });
    return () => { alive = false; off(); };
  }, [on]);

  /* (b) the live interest — keyed on the list, renewed every CARD_LIVE_MS while visible. */
  useEffect(() => {
    if (!on) { setWord(null); return; }
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let ctrl: AbortController | null = null;
    let lastPost = 0;
    const post = async () => {
      lastPost = Date.now();
      ctrl?.abort();
      const mine = new AbortController();
      ctrl = mine;
      try {
        const r = await fetch(`${API}${GGW_LIVE_PATH}`, {
          method: 'POST', credentials: 'include', cache: 'no-store',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ symbols: [...symsRef.current] }), signal: mine.signal,
        });
        if (!alive) return;
        const j: unknown = r.ok ? await r.json() : null;
        if (!alive || !j || typeof j !== 'object') return;
        setWord(streamFeedWord({ stream: (j as { stream?: unknown }).stream } as CardLiveAnswer));
      } catch {
        /* a failed renewal keeps the last served word; the hub's interest lapses on its own TTL */
      } finally {
        if (ctrl === mine) ctrl = null;
      }
    };
    const schedule = () => {
      if (!alive) return;
      if (timer != null) clearTimeout(timer);
      timer = setTimeout(tick, CARD_LIVE_MS);
    };
    const tick = () => {
      timer = null;
      if (!alive) return;
      if (!document.hidden) void post();
      schedule();
    };
    const onVisible = () => {
      if (!alive || document.hidden || Date.now() - lastPost < CARD_LIVE_MS) return;
      void post();
      schedule();
    };
    if (!document.hidden) void post();
    schedule();
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      alive = false;
      if (timer != null) clearTimeout(timer);
      ctrl?.abort();
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [key, on]);

  return { word };
}
