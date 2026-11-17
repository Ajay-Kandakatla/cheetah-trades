/* GgCardView — 🚩 Gajjala card click → the ⤢ three-chart view (15-min / 5-min / 1-min), 2026-11-16 (ggcard3 spec §3.4).
 *
 * Ajay 2026-11-16: "Also when I click on a card from any of the Gajjala I would like us to open the 3 chart extension like
 * in the Watch list... Also put a SEPA page link for it separaetely on the card I I want to but default its 3 chart
 * extension with 1 min, 3 min and 5 mins" and then "Actually instead of 3 mins make it 15 mins timeframe".
 *
 * The 👀 Watch's OWN full-screen view (components/GajjalaWatchTile GgwStretch — never a second implementation) over ONE
 * read-only GET (GGC_PATH/{symbol}, backend chart_maps/gajjala/card_frames.py) that serves the three frames from the docs
 * the 🚩 5-min pass and the 1-minute loop already store. The card's served lines / bands / markers / plan line overlay
 * the frames (lib/gajjalaCardView.ggcRow).
 *
 *  - Cadence [C1]: ONE GET in an effect whose deps are EXACTLY [at, boardSeq] — the open symbol and the board's own
 *    landed-GET counter. Never the tiles array or `card`: the board re-renders on every quotes batch (≈ 1/s in RTH) and
 *    hands a new tiles array each time. Newest wins (seq ref); the previous GET is aborted.
 *  - Live: the board's EXISTING stream (no interest POST here — the board's useCardLive holds it): every `gajjala.update`
 *    quotes batch of THIS board's variant is folded by lib/ggwLive.ggwApplyBatch(…, variant) against
 *    ggwFrameMetas([row]) — a stale frame (its own served `stale`) or a stale / prior-session row carries no forming bar.
 *  - Words: every sentence about the stock is served; the FE types only GGC_FETCH_FAILED (no payload to serve one).
 *
 * DISPLAY ONLY, UNMEASURED — a chart view is information, not an entry. Nothing here rings, gates, sizes or trades. */
import { useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { subscribe, type BusEvent } from '../lib/eventBus';
import { GG_UPDATE_EVENT, parseGgUpdate } from '../lib/cardLive';
import { ggwRowLive, type GgwRow } from '../lib/gajjalaWatch';
import { ggwApplyBatch, ggwFrameMetas, type GgwFrameMeta, type GgwLiveMap } from '../lib/ggwLive';
import { GGC_FETCH_FAILED, GGC_STRETCH_ORDER, ggcPath, ggcRow, parseGgc, type GgcPayload } from '../lib/gajjalaCardView';
import type { GgTile } from '../lib/gajjala';
import { GgwStretch, usePhone } from './GajjalaWatchTile';

type Load =
  | { at: string; kind: 'ok'; p: GgcPayload }
  | { at: string; kind: 'error'; reason: string | null }
  | { at: string; kind: 'failed' };

const NO_FRAMES = { from_session: null, as_of_et: null, stale: false, frames: [], rang: [] };

export function GgCardView({ card, at, variant, boardSeq, onClose, onStep }: {
  /** The OPEN card (the board's drawn tile) — its lines / bands / markers / plan line overlay the frames. */
  card: GgTile;
  /** The open symbol. */
  at: string;
  /** The board's variant key — the bus `variant` its quotes batches carry. */
  variant: string;
  /** GajjalaBoard's landed-GET counter — with `at`, the ONLY refetch cadence. */
  boardSeq: number;
  onClose: () => void;
  /** null with one card (the Watch rule: no ◀ ▶). */
  onStep: ((d: -1 | 1) => void) | null;
}) {
  const phone = usePhone();
  const [load, setLoad] = useState<Load | null>(null);
  const seq = useRef(0);

  useEffect(() => {
    const my = ++seq.current;
    const ctrl = typeof AbortController === 'function' ? new AbortController() : null;
    fetch(`${API}${ggcPath(at)}`, { credentials: 'include', cache: 'no-store', signal: ctrl?.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((j: unknown) => {
        if (my !== seq.current) return;
        const p = parseGgc(j);
        if (p && p.state === 'ok') setLoad({ at, kind: 'ok', p });
        else if (p && p.state === 'error') setLoad({ at, kind: 'error', reason: p.reason });
        else setLoad((prev) => (prev && prev.at === at && prev.kind === 'ok' ? prev : { at, kind: 'failed' }));
      })
      .catch(() => {
        if (my !== seq.current) return;
        /* a failed RE-read keeps the frames already on screen for this symbol; a failed first read prints the sentence */
        setLoad((prev) => (prev && prev.at === at && prev.kind === 'ok' ? prev : { at, kind: 'failed' }));
      });
    return () => { ctrl?.abort(); };
  }, [at, boardSeq]);

  const cur = load && load.at === at ? load : null;
  const payload = cur && cur.kind === 'ok' ? cur.p : null;
  const row = useMemo<GgwRow>(() => {
    if (payload) return ggcRow(card, payload);
    if (cur && cur.kind === 'error') return { symbol: at, state: 'error', text: cur.reason ?? GGC_FETCH_FAILED, ...NO_FRAMES };
    if (cur && cur.kind === 'failed') return { symbol: at, state: 'error', text: GGC_FETCH_FAILED, ...NO_FRAMES };
    return { symbol: at, state: 'loading', text: null, ...NO_FRAMES };
  }, [card, payload, cur, at]);

  /* the live tail — the board's own stream, folded per (symbol, frame) on the served grid */
  const [live, setLive] = useState<GgwLiveMap>({});
  useEffect(() => { setLive({}); }, [at]);
  const metas = useMemo<Record<string, GgwFrameMeta[]>>(() => ggwFrameMetas([row]), [row]);
  const metasRef = useRef(metas);
  metasRef.current = metas;
  useEffect(() => {
    if (typeof EventSource === 'undefined') return;
    let alive = true;
    const off = subscribe(GG_UPDATE_EVENT, (evt: BusEvent) => {
      if (!alive) return;
      const u = parseGgUpdate(evt?.payload);
      if (!u || u.kind !== 'quotes' || u.variant !== variant) return;
      setLive((prev) => ggwApplyBatch(prev, u, metasRef.current, variant));
    });
    return () => { alive = false; off(); };
  }, [variant]);

  return (
    <GgwStretch kind="card" row={row} order={GGC_STRETCH_ORDER} phone={phone} removeLabel={null}
                onClose={onClose} onStep={onStep} live={ggwRowLive(row) ? live[row.symbol] : undefined} />
  );
}

export default GgCardView;
