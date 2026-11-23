/* useGgCardWatch — the 🚩 / 🧪 card grid in the 👀 Watch layout: the state the Watch board holds, for the card grid
 * (2026-11-18, spec cardview §3.2, WP-B).
 *
 * Ajay 2026-11-18: "I need the watch list kinda chart formant view video view as default here too from the tabs pages" →
 * his pick "Tab cards as Watch tiles": the card grid itself switches to the Watch layout — big tiles, 2 per screen side by
 * side, each with the live 15 / 5 / 1-min stacked charts. The small cards are no longer the default.
 *
 *  - Mode: `gg-card-watch` per device (lib/gajjalaCardView.loadGgcWatch — absent → ON). `allowed` = the 🚩 5-min tab and
 *    🧪 Audited only. `active` = on && enabled && a tile to draw — the ONLY flag the board switches on [C7]. While NOT
 *    active the hook fetches nothing, subscribes to nothing, measures nothing and holds nothing.
 *  - Frames: the ⤢ view's own read-only GET (GGC_PATH/{symbol}), ONLY for the tiles on screen, ONCE per symbol per landed
 *    board read (`boardSeq`). Paging back to a page already read for this `boardSeq` → zero GETs; a quotes batch, a new
 *    tiles array, a 📺 flip → zero GETs. Newest wins per symbol; a failed RE-read keeps the frames on screen [C1, C5].
 *  - Live: ONE bus subscription; every quotes batch of THIS board's variant folds into ONE map against the frame metas of
 *    EVERY loaded row still listed (an off-page card keeps its forming bar) — the DISPLAY is gated by `shown` [C2].
 *  - `?focus=`: the page holding the focused card is derived in render with no ref write (StrictMode-safe), then
 *    committed by an effect — the card is SHOWN in the very commit the board's once-only scroll runs in [C3].
 *
 *  - 🎾 2026-11-23 (rswatch §3.7 [C2]; Ajay: "In the reversal squeeze can you make the charts same as in watch list
 *    please"): a 🎾 card asks `?card=squeeze`; every load carries the ask it was GOT with (`ask`, absent for the plain GET),
 *    a card never draws a load asked for the other shape (the loading row instead) and a failed re-read keeps only a
 *    load of the SAME ask. The split itself is the served echo's call (lib/gajjalaCardView.ggcRow).
 *
 * DISPLAY ONLY, UNMEASURED — nothing here rings, gates, sizes, orders or trades. */
import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { API } from '../lib/apiBase';
import { subscribe, type BusEvent } from '../lib/eventBus';
import { GG_UPDATE_EVENT, parseGgUpdate } from '../lib/cardLive';
import type { GgTile } from '../lib/gajjala';
import {
  GGW_LAYOUTS, ggwClampPage, ggwPageCount, ggwPageOf, ggwPickGrid, ggwRowLive, ggwToggleShown,
  type GgwLayout, type GgwRow,
} from '../lib/gajjalaWatch';
import { ggwApplyBatch, ggwFrameMetas, type GgwFrameMeta, type GgwLiveMap, type GgwLiveSym } from '../lib/ggwLive';
import {
  GGC_FETCH_FAILED, GGC_NO_FRAMES, GGC_WATCH_VKEYS, ggcCardParam, ggcIsSqueeze, ggcPath, ggcRow, ggcShown, loadGgcWatch,
  parseGgc, readGgcLayout, saveGgcLayout, saveGgcWatch, type GgcPayload,
} from '../lib/gajjalaCardView';
import { usePhone } from '../components/GajjalaWatchTile';
import { useGgwFitRows } from '../components/GajjalaWatchLayout';

export type GgcLoad =
  | { seq: number; kind: 'ok'; p: GgcPayload; ask?: string }
  | { seq: number; kind: 'error'; reason: string | null; ask?: string }
  | { seq: number; kind: 'failed'; ask?: string };
/* 🎾 [C2] `ask` = the card param of the GET that produced this load. The key is ABSENT for the plain GET, so a plain load is
 * today's object. */
const askOf = (ld: GgcLoad | undefined): string => ld?.ask ?? '';

export type GgCardWatch = {
  /** The stored mode on an allowed board (the toggle's aria-pressed). */
  on: boolean;
  /** This board offers the layout (GGC_WATCH_VKEYS). */
  allowed: boolean;
  toggle: () => void;
  /** on && enabled && tiles.length > 0 — the ONLY flag the frame / card / tile switch on [C7]. */
  active: boolean;
  phone: boolean;
  layout: GgwLayout;
  setLayout: (l: GgwLayout) => void;
  page: number;
  pages: number;
  paged: boolean;
  goPage: (pg: number) => void;
  pick: string[] | null;
  usePick: boolean;
  togglePick: (sym: string) => void;
  shown: (sym: string) => boolean;
  rowOf: (card: GgTile) => GgwRow;
  liveOf: (sym: string) => GgwLiveSym | undefined;
  grid: { cols: number; rows: number };
  fit: boolean;
  rowH: number | null;
  boardRef: RefObject<HTMLDivElement>;
  headRef: RefObject<HTMLDivElement>;
  gridRef: RefObject<HTMLDivElement>;
};

type Inflight = { ctrl: AbortController | null; my: number; seqAt: number };
type RowCache = { card: GgTile; load: GgcLoad | undefined; look: 'video' | undefined; row: GgwRow };

export function useGgCardWatch(a: {
  tiles: GgTile[]; vkey: string; boardSeq: number; look?: 'video'; focus: string | null; stretched: boolean; enabled: boolean;
}): GgCardWatch {
  const { tiles, vkey, boardSeq, look, focus, stretched, enabled } = a;

  /* §3.2.1 the mode */
  const allowed = GGC_WATCH_VKEYS.includes(vkey);
  const [stored, setStored] = useState<boolean>(loadGgcWatch);
  const on = stored && allowed;
  const toggle = useCallback(() => {
    const next = !stored;
    setStored(next);
    saveGgcWatch(next);
  }, [stored]);
  const active = on && enabled && tiles.length > 0;

  /* the names, in the served order — a new tiles array with the same names is the same key */
  const tilesKey = tiles.map((t) => t.symbol).join(',');
  const symbols = useMemo(() => (tilesKey ? tilesKey.split(',') : []), [tilesKey]);
  const n = symbols.length;

  /* §3.2.5 the per-screen pick + the page (his "1 tile per screen" on the phone) */
  const phone = usePhone();
  const [layout, setLayoutState] = useState<GgwLayout>(readGgcLayout);
  const size: number = phone ? 1 : layout;
  const [page, setPage] = useState(0);
  const [pick, setPick] = useState<string[] | null>(null);

  /* §3.2.6 `?focus=` [C3]: derived in render, NO ref write here — both StrictMode renders derive the same page. */
  const focusSeen = useRef<string | null>(null);
  const focusIdx = focus ? symbols.indexOf(focus) : -1;
  const focusPending = !!focus && focusSeen.current !== focus && focusIdx >= 0;
  const effPage = focusPending ? ggwPageOf(focusIdx, size) : page;
  const effPick = focusPending ? null : pick;
  useEffect(() => {
    if (!focus) { focusSeen.current = null; return; }
    if (!focusPending) return;
    focusSeen.current = focus;
    setPage(effPage);
    setPick(null);
  }, [focus, focusPending, effPage]);

  const picked = effPick ? effPick.filter((s) => symbols.includes(s)) : [];
  const usePick = picked.length > 0;
  const paged = n > size;
  const cur = paged ? ggwClampPage(effPage, n, size) : 0;
  const pages = paged ? ggwPageCount(n, size) : 1;
  const shownSet = useMemo(() => ggcShown(symbols, cur, size, effPick), [symbols, cur, size, effPick]);
  const shown = useCallback((sym: string) => shownSet.has(sym), [shownSet]);

  const boardRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<HTMLDivElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const goPage = useCallback((pg: number) => {
    setPick(null);
    setPage(pg);
    boardRef.current?.scrollIntoView?.({ block: 'start', behavior: 'smooth' });
  }, []);
  const togglePick = useCallback((sym: string) => {
    setPick(ggwToggleShown(symbols, symbols.filter((s) => shownSet.has(s)), sym));
  }, [symbols, shownSet]);
  const setLayout = useCallback((l: GgwLayout) => {
    setPick(null);
    /* keep the first SHOWN tile in view (the Watch's rule) */
    setPage((pg) => ggwPageOf(ggwClampPage(pg, n, size) * size, l));
    setLayoutState(l);
    saveGgcLayout(l);
  }, [n, size]);

  /* the stored page follows the list (a shorter list, a bigger pick) */
  useEffect(() => {
    if (n > 0) setPage((pg) => ggwClampPage(pg, n, size));
  }, [n, size]);

  /* ← → move the view a page (never while typing, never under the ⤢ view, never with one page) */
  useEffect(() => {
    if (!active || stretched || n <= size) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      const d = e.key === 'ArrowLeft' ? -1 : 1;
      setPick(null);
      setPage((pg) => ggwClampPage(ggwClampPage(pg, n, size) + d, n, size));
      boardRef.current?.scrollIntoView?.({ block: 'start', behavior: 'smooth' });
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [active, stretched, n, size]);

  const grid = usePick
    ? ggwPickGrid(picked.length, GGW_LAYOUTS[layout].cols, GGW_LAYOUTS[layout].rows)
    : GGW_LAYOUTS[layout];
  /* [C1] the key re-runs the measure on every landed read AND every OFF ↔ ON flip (OFF: no grid node → null) */
  const fitKey = `${boardSeq}:${active ? 1 : 0}`;
  const rowH = useGgwFitRows(gridRef, headRef, phone, fitKey, grid.rows);
  const fit = rowH != null;

  /* §3.2.2 the frames GETs — the names on screen only, once per symbol per landed board read */
  const [loads, setLoads] = useState<Record<string, GgcLoad>>({});
  const [live, setLive] = useState<GgwLiveMap>({});
  const done = useRef(new Map<string, number>());
  /* 🎾 [C2] the ask each name was last GOT with — a card whose setup flips inside one boardSeq is asked again, once */
  const asked = useRef(new Map<string, string>());
  const inflight = useRef(new Map<string, Inflight>());
  const reqSeq = useRef(0);
  /* a bar-less card (☀️ / 🌙 mover) keeps its Link and draws no tile → it is never asked for frames. 🎾 [C2]: an entry is
   * `SYM` (the plain GET) or `SYM?squeeze` (a 🎾 card) — a board with no 🎾 card is today's string character for character */
  const shownKey = active
    ? tiles.filter((t) => t.bars?.length && shownSet.has(t.symbol))
        .map((t) => { const c = ggcCardParam(t); return c ? `${t.symbol}?${c}` : t.symbol; }).join(',')
    : '';

  useEffect(() => {
    if (!active) {
      /* [C5] OFF / the 🏁 / 📋 sub / an empty list: nothing in flight, nothing held */
      done.current.clear();
      asked.current.clear();
      setLoads((prev) => (Object.keys(prev).length ? {} : prev));
      setLive((prev) => (Object.keys(prev).length ? {} : prev));
      return;
    }
    const want = shownKey ? shownKey.split(',') : [];
    for (const entry of want) {
      const q = entry.indexOf('?');
      const sym = q < 0 ? entry : entry.slice(0, q);
      const ask = q < 0 ? '' : entry.slice(q + 1);
      if (done.current.get(sym) === boardSeq && (asked.current.get(sym) ?? '') === ask) continue;
      inflight.current.get(sym)?.ctrl?.abort();
      const ctrl = typeof AbortController === 'function' ? new AbortController() : null;
      const my = ++reqSeq.current;
      const seqAt = boardSeq;
      done.current.set(sym, seqAt);
      asked.current.set(sym, ask);
      inflight.current.set(sym, { ctrl, my, seqAt });
      const mine = () => inflight.current.get(sym)?.my === my;
      const tag = ask ? { ask } : {};
      /* a failed RE-read keeps an ok load of the SAME ask only; a failed first read of this shape prints the sentence */
      const keepOk = () => setLoads((prev) => (prev[sym]?.kind === 'ok' && askOf(prev[sym]) === ask
        ? prev : { ...prev, [sym]: { seq: seqAt, kind: 'failed', ...tag } }));
      fetch(`${API}${ggcPath(sym, ask || undefined)}`, { credentials: 'include', cache: 'no-store', signal: ctrl?.signal })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((j: unknown) => {
          if (!mine()) return;
          inflight.current.delete(sym);
          const p = parseGgc(j);
          if (p && p.state === 'ok') setLoads((prev) => ({ ...prev, [sym]: { seq: seqAt, kind: 'ok', p, ...tag } }));
          else if (p && p.state === 'error') setLoads((prev) => ({ ...prev, [sym]: { seq: seqAt, kind: 'error', reason: p.reason, ...tag } }));
          else keepOk();
        })
        .catch(() => {
          if (!mine()) return;
          inflight.current.delete(sym);
          /* a failed RE-read keeps the frames already on screen; a failed first read prints the sentence */
          keepOk();
        });
    }
    return () => {
      /* every GET still out is aborted; its name is unmarked, so the next run (the shown names) asks again */
      for (const [sym, f] of inflight.current) {
        f.ctrl?.abort();
        if (done.current.get(sym) === f.seqAt) done.current.delete(sym);
      }
      inflight.current.clear();
    };
  }, [shownKey, boardSeq, active, vkey]);

  /* a name gone from the list loses its load (→ its metas → its live bucket on the next batch) */
  useEffect(() => {
    const listed = new Set(symbols);
    for (const s of Array.from(done.current.keys())) if (!listed.has(s)) done.current.delete(s);
    for (const s of Array.from(asked.current.keys())) if (!listed.has(s)) asked.current.delete(s);
    setLoads((prev) => {
      const gone = Object.keys(prev).filter((s) => !listed.has(s));
      if (!gone.length) return prev;
      const next = { ...prev };
      for (const s of gone) delete next[s];
      return next;
    });
  }, [symbols]);

  /* §3.2.3 rows — the SAME row object while the card, its load and the look are unchanged (a quotes batch that patches
   * card A never redraws card B's three svgs) */
  const rowCache = useRef(new Map<string, RowCache>());
  const rowOf = (card: GgTile): GgwRow => {
    const sym = card.symbol;
    /* 🎾 [C2] a load asked for another shape is not this card's load → the loading row until ITS shape lands */
    const held = loads[sym];
    const ld = held && askOf(held) === (ggcCardParam(card) ?? '') ? held : undefined;
    const hit = rowCache.current.get(sym);
    if (hit && hit.card === card && hit.load === ld && hit.look === look) return hit.row;
    let row: GgwRow;
    if (ld && ld.kind === 'ok') row = ggcRow(card, ld.p, look, ggcIsSqueeze(card) ? { plan: false, squeeze: true } : { plan: false });
    else if (ld && ld.kind === 'error') row = { symbol: sym, state: 'error', text: ld.reason ?? GGC_FETCH_FAILED, ...GGC_NO_FRAMES };
    else if (ld && ld.kind === 'failed') row = { symbol: sym, state: 'error', text: GGC_FETCH_FAILED, ...GGC_NO_FRAMES };
    else row = { symbol: sym, state: 'loading', text: null, ...GGC_NO_FRAMES };
    rowCache.current.set(sym, { card, load: ld, look, row });
    return row;
  };

  /* §3.2.4 live [C2] — metas over EVERY loaded ok row still listed (all visited pages); from the payload only, so a
   * quotes batch recomputes nothing */
  const metas = useMemo<Record<string, GgwFrameMeta[]>>(() => {
    const rows: GgwRow[] = [];
    for (const sym of symbols) {
      const ld = loads[sym];
      if (ld && ld.kind === 'ok') rows.push(ggcRow({ symbol: sym } as GgTile, ld.p));
    }
    return ggwFrameMetas(rows);
  }, [loads, symbols]);
  const metasRef = useRef(metas);
  metasRef.current = metas;
  useEffect(() => {
    if (!active || typeof EventSource === 'undefined') return;
    let alive = true;
    const off = subscribe(GG_UPDATE_EVENT, (evt: BusEvent) => {
      if (!alive) return;
      const u = parseGgUpdate(evt?.payload);
      if (!u || u.kind !== 'quotes' || u.variant !== vkey) return;
      setLive((prev) => ggwApplyBatch(prev, u, metasRef.current, vkey));
    });
    return () => { alive = false; off(); };
  }, [active, vkey]);
  const liveOf = (sym: string): GgwLiveSym | undefined => {
    if (!shownSet.has(sym)) return undefined;
    const ld = loads[sym];
    if (!ld || ld.kind !== 'ok') return undefined;
    const card = tiles.find((t) => t.symbol === sym);
    const row = card ? rowOf(card) : null;
    return row && ggwRowLive(row) ? live[sym] : undefined;
  };

  return {
    on, allowed, toggle, active, phone, layout, setLayout,
    page: cur, pages, paged, goPage,
    pick: usePick ? picked : null, usePick, togglePick,
    shown, rowOf, liveOf, grid, fit, rowH, boardRef, headRef, gridRef,
  };
}

export default useGgCardWatch;
