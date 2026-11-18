/* GajjalaWatchBoard — 👀 Gajjala's Watch tab on Chart Maps (2026-11-15, gajjala-watch spec §3.8, WP-C).
 *
 * Ajay 2026-11-15: "I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and add remove
 * tickers from the dashboard. When I add a ticker I need 1 min 3 min and 5 min charts... Not the SEPA and I need clear
 * distinction or may be a brighter and thicker 21 EMA and 9 EMA, from the videos I notice that when ever 9 EMA crosses
 * over 21 EMA on uptrend is where the bullish momentum started I need alerts on these from 1 min to I can be ready... I
 * think the cross over is slow but once it picks up its very rapid.." · "I have a 27 inch monitor I wanna fit 3x3 tikers
 * on watch at any given time on this tashboard" · "Any chart I view make sure you are showing me from 4 AM for
 * historical behaviour and also the right side with gaps to see where it might go".
 *
 * ONE owner-only GET (GET /chart-maps/gajjala-watch, backend chart_maps/gajjala_watch/api.py). `owner_only` → the
 * served reason only. Otherwise: the head (served title · the add box · the served pass line · the 9 / 21 legend · one
 * collapsed ℹ️ with the served honesty, K5 rule and push sentence — printed ONCE) and a 3-column grid of tiles in HIS
 * order (the server never reorders). Each tile: SYM, the served row text / session stamp / as-of, the 🔔 rang chips,
 * one Yahoo ↗, ✕ (DELETE, no confirm); the replay's dark panel with the 1-min chart full width on top and the 3-min +
 * 5-min side by side below — PatternChart chartOnly (no SEPA link), emaStyle bold, the served 04:00 axis.
 *
 * 2026-11-16, Ajay: "I need bigger may be 2 on each screen side by side its not clear and give me a strech button to
 * see full chart" — a "2 · 4 · 9 per screen" pick in the head (2 = two tiles side by side filling one screen, the
 * default; 9 = his 11-15 3 × 3), remembered in this browser; ⤢ on every tile opens it over the whole window (⤡ / Esc
 * back). Layout only: no word, order or rule changes.
 *
 * Cadence (spec C4.5 / C2.4 / C2.7): one setTimeout chain re-GETs the board at the served refresh_sec while the page is
 * visible; out of window, ONE re-GET at the served next_window_sec; while a row is pending, the pending names only
 * (?symbols=) every pending_poll_sec up to pending_wait_max_sec; one full re-GET after an add or a remove.
 *
 * LIVE (2026-11-16, watch-live spec §3.5, WP-D) — Ajay: "Can you make the watch list charts live please" ·
 * "Realtime updates.. Like the 1 min chart I need it to be live live.. per sec change" · "Also on the Watch list I need
 * live volume to be shown at the bottom" · "Of each chart". The SAME live stack as the 🚩 boards, never a second one:
 * one socket → backend live_hub (the watch tab rides it as an extra tab, never a Variant) → `gajjala.update` quotes
 * with the summed print `size` at most once a second → the house bus → /events → hooks/useGgwLive (one subscription,
 * the owner-gated live-interest POST renewed every 30 s) → lib/ggwLive.ggwApplyBatch folds the raw batches into
 * forming candles per (symbol, frame) on the SERVER's own 04:00 grid (the axis' start_epoch / frame_min) →
 * lib/ggwLive.ggwLiveFrame splices them AFTER the stored bars at render time: the last candle moves, its volume column
 * grows at the bottom, the dashed `now` line follows. DISPLAY ONLY — every cross read, blinker, 🔔 and push stays on
 * the CLOSED stored bars; the next GET wins; a stale row stops its live tail (ggwRowLive); the batches reach the owner's
 * tabs only (events audience). The 9 / 21 tips follow the forming close (GGW_LIVE_EMA_TIP, HIS CALL
 * #1 answered 11-16). An off-page tile gets no live bars (its charts never re-render on a batch). The served feed word prints in the
 * head only when the feed is degraded. docs/gajjala/watch_live_2026_11_16.md.
 *
 * The FE composes NO word about a stock: every visible string is served, except GGW_FETCH_FAILED (no payload to serve
 * one) and structural glyphs (⚠️ on a served stale flag, ✕, ℹ️, "·"). UNMEASURED — a cross is information, not an
 * entry.
 *
 * No house chips on this tab (🚀 growth, 🧨 explosive, 🩳 short interest, 🎯 enterable): each tile is the chart alone, his
 * words "Not the SEPA" (spec §3.8) — the chips live on every other Chart Maps board. No 🧨 ordering toggle either: his
 * list order orders this board (the order he added the names in, as served); the 🤖 auto rows follow his, in the order
 * they were added (the server never re-sorts them).
 *
 * 🤖 AUTO (2026-11-17, watch-auto spec §3.6, WP-C) — Ajay: "Can you add more stocks in to watch list basically I need
 * portentials from Gajjals's 1 min and regular and also Audited potentials with good volume to Watchlist on an
 * interval.. Remove as they are not progressing". The server's minute loop adds the 🧠 potentials of the 🚩 5-min,
 * 🚩 1-min and 🧪 boards with good volume and removes them when they stop progressing (backend
 * chart_maps/gajjala_watch/auto.py); this board only PRINTS what is served: the head's 🤖 title (hover = the served
 * hint), the served unreadable / empty words, a collapsed "removed today" strip whose lines are the served `text_full`
 * verbatim, the 🤖 tag + dashed outline on an auto name in the pager (its × title served), the tile's 🤖 chip
 * (GajjalaWatchTile) and the ℹ️ clause. The live interest POSTs EVERY row (ggwLiveSymbols — his names, then the auto
 * names). × on an auto name is the same DELETE (the server dismisses it for the session). UNMEASURED — an auto add is
 * a board's 🧠 read, not an entry. */
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type FormEvent, type RefObject } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { EMA_BOLD } from '../lib/chartMaps';
import {
  GGW_FETCH_FAILED, GGW_FOCUS_PARAM, ggwRowLive, GGW_LAYOUT_ORDER, GGW_LAYOUTS, GGW_PAGER, GGW_PATH,
  ggwClampPage, ggwFitRowHeight, ggwLiveSymbols, ggwPageCount, ggwPageOf, ggwMergeRows, ggwPendingSymbols, ggwRowsPath,
  ggwPickGrid, ggwSymbolPath, ggwToggleShown, GGW_URL, ggwViewParams, parseGgwLayout,
  parseGgwPage, parseGgwPick, readGgwPick, saveGgwPick, parseGgw, readGgwLayout, saveGgwLayout,
  type GgwBoard, type GgwLayout, type GgwPayload, type GgwRow, type GgwWriteAnswer,
} from '../lib/gajjalaWatch';
import { ggwApplyBatch, ggwFrameMetas, type GgwFrameMeta, type GgwLiveMap, type GgwLiveSym } from '../lib/ggwLive';
import { useGgwLive, type GgwBatch } from '../hooks/useGgwLive';
/* 2026-11-16 (ggcard3 WP-A): the tile, its frames and the ⤢ full-screen view live in GajjalaWatchTile.tsx (a pure move)
 * so the 🚩 cards open the SAME view. */
import { GgwStretch, Tile, usePhone } from './GajjalaWatchTile';
import { loadGgwList } from '../lib/ggWatchList';
import '../styles/gajjalaWatch.css';

type Load = { phase: 'loading' } | { phase: 'failed' } | { phase: 'loaded'; p: GgwPayload };
const NO_SYMBOLS: string[] = [];

const getJson = (path: string) =>
  fetch(`${API}${path}`, { credentials: 'include', cache: 'no-store' })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))));

/** The fitted grid row height (px) above the phone break, or null (phone / no layout yet / jsdom). */
function useFitRows(grid: RefObject<HTMLDivElement>, head: RefObject<HTMLDivElement>,
                    phone: boolean, deps: unknown, rows: number): number | null {
  const [rowH, setRowH] = useState<number | null>(null);
  useEffect(() => {
    if (phone || typeof window === 'undefined') { setRowH(null); return; }
    const measure = () => {
      const g = grid.current;
      if (!g) { setRowH(null); return; }
      const r = g.getBoundingClientRect();
      if (!(r.width > 0)) { setRowH(null); return; }
      const gap = parseFloat(getComputedStyle(g).rowGap) || 0;
      /* 2026-11-16: measured from the BOARD's top, not the page's — the banners above the tabs grew past one screen,
       * so a page-top measure left every row at the floor. With the board scrolled to the top, its head, the pager
       * and `rows` rows fill exactly one window (his "two stocks with 3 charts each at any given moment"). */
      const b = g.closest('.ggw-board');
      const boardTop = b ? b.getBoundingClientRect().top : r.top;
      setRowH(ggwFitRowHeight({ vh: window.innerHeight, top: r.top - boardTop, below: 0, gap }, rows));
    };
    measure();
    window.addEventListener('resize', measure);
    const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null;
    if (ro && head.current) ro.observe(head.current);
    return () => { window.removeEventListener('resize', measure); ro?.disconnect(); };
  }, [phone, grid, head, deps, rows]);
  return rowH;
}

export default function GajjalaWatchBoard() {
  const [params, setParams] = useSearchParams();
  const focus = (params.get(GGW_FOCUS_PARAM) || '').trim().toUpperCase() || null;
  const phone = usePhone();
  const [load, setLoad] = useState<Load>({ phase: 'loading' });
  const [refreshFailed, setRefreshFailed] = useState(false);
  /** A served `state: "error"` reason while a board is already up — printed verbatim in the head. */
  const [servedErr, setServedErr] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [outlined, setOutlined] = useState<string | null>(null);
  /* 🔗 2026-11-16 — the view comes from the link first (a shared link opens on the same view), else this browser. */
  const [layout, setLayoutState] = useState<GgwLayout>(() => (params.get(GGW_URL.per)
    ? parseGgwLayout(params.get(GGW_URL.per)) : readGgwLayout()));
  const [stretched, setStretched] = useState<string | null>(null);
  const [page, setPage] = useState(() => parseGgwPage(params.get(GGW_URL.page)));
  /** 2026-11-16 — the names HE toggled on (null = the pages). */
  const [pick, setPick] = useState<string[] | null>(() => (params.has(GGW_URL.show)
    ? parseGgwPick(params.get(GGW_URL.show)) : (params.has(GGW_URL.per) ? null : readGgwPick())));
  /* 🔗 every change writes the link (replace — no history step per tap) and this browser. */
  useEffect(() => {
    saveGgwPick(pick);
    setParams((prev) => ggwViewParams(prev, { layout, pick, page }), { replace: true });
  }, [layout, pick, page, setParams]);
  const closeStretch = useCallback(() => setStretched(null), []);
  /* The page size: the pick on a desktop; a phone shows every tile in one column. */
  const size = phone ? Number.POSITIVE_INFINITY : layout;
  const boardRef = useRef<HTMLDivElement>(null);
  /* A page move by HIM (◀ ▶, a ticker, ← →) brings the board's top to the window's top, so the two tiles fill it. */
  const goPage = (pg: number) => {
    setPick(null);
    setPage(pg);
    boardRef.current?.scrollIntoView?.({ block: 'start', behavior: 'smooth' });
  };
  const setLayout = (l: GgwLayout) => {
    setPick(null);
    /* keep the first SHOWN tile in view (the stored page clamped first — review fix: a stale page after removals) */
    setPage((pg) => (Number.isFinite(size) ? ggwPageOf(ggwClampPage(pg, nRows, size as number) * (size as number), l) : 0));
    setLayoutState(l);
    saveGgwLayout(l);
  };

  const alive = useRef(true);
  const board = useRef<GgwBoard | null>(null);
  const mainTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendSince = useRef<Map<string, number>>(new Map());
  const focusDone = useRef(false);
  const pendingFocus = useRef<string | null>(null);
  const loadAllRef = useRef<() => void>(() => {});
  const gridRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<HTMLDivElement>(null);
  /* The pick (his toggled names still on the list) and its grid; no pick → the layout's own grid. */
  const listNow = load.phase === 'loaded' && load.p.state === 'ok' ? load.p.rows.map((r) => r.symbol) : [];
  const picked = pick ? pick.filter((s) => listNow.includes(s)) : [];
  const usePick = picked.length > 0;
  const grid = usePick ? ggwPickGrid(picked.length, GGW_LAYOUTS[layout].cols, GGW_LAYOUTS[layout].rows) : GGW_LAYOUTS[layout];
  const rowH = useFitRows(gridRef, headRef, phone, load, grid.rows);
  const fit = rowH != null;

  /* the live tail: forming bars per (symbol, frame), folded from the raw batches against the metas of the rows that
   * may carry live bars (ggwRowLive — ok, today's, not stale). Owner + in window only: a non-owner never reaches an ok
   * board, and out of window refresh_sec is 0. */
  const [live, setLive] = useState<GgwLiveMap>({});
  const metas = useMemo<Record<string, GgwFrameMeta[]>>(
    () => (load.phase === 'loaded' && load.p.state === 'ok' ? ggwFrameMetas(load.p.rows) : {}), [load]);
  const metasRef = useRef(metas);
  metasRef.current = metas;
  const onBatch = useCallback((evt: GgwBatch) => setLive((prev) => ggwApplyBatch(prev, evt, metasRef.current)), []);
  const liveOn = load.phase === 'loaded' && load.p.state === 'ok' && load.p.rows.length > 0 && load.p.refresh_sec > 0;
  /* 🤖 2026-11-17: every row (his, then the auto names) — not `symbols` (his names only). */
  const { word: feedWord } = useGgwLive(load.phase === 'loaded' && load.p.state === 'ok' ? ggwLiveSymbols(load.p) : NO_SYMBOLS,
    liveOn, onBatch);
  const liveOf = (r: GgwRow, shown: boolean): GgwLiveSym | undefined => (shown && ggwRowLive(r) ? live[r.symbol] : undefined);

  const clearMain = () => { if (mainTimer.current) { clearTimeout(mainTimer.current); mainTimer.current = null; } };
  const clearPend = () => { if (pendTimer.current) { clearTimeout(pendTimer.current); pendTimer.current = null; } };

  /* The pending poll: the names still waiting for their first read, each for at most pending_wait_max_sec. */
  const armPending = useCallback((b: GgwBoard) => {
    const now = Date.now();
    const pend = ggwPendingSymbols(b);
    for (const s of Array.from(pendSince.current.keys())) if (!pend.includes(s)) pendSince.current.delete(s);
    for (const s of pend) if (!pendSince.current.has(s)) pendSince.current.set(s, now);
    const poll = b.pending_poll_sec ?? 0;
    const max = b.pending_wait_max_sec ?? 0;
    const due = pend.filter((s) => now - (pendSince.current.get(s) ?? now) < max * 1000);
    clearPend();
    if (!due.length || poll <= 0 || max <= 0) return;
    pendTimer.current = setTimeout(() => {
      pendTimer.current = null;
      getJson(ggwRowsPath(due))
        .then((raw) => {
          if (!alive.current) return;
          const part = parseGgw(raw);
          const cur = board.current;
          if (!cur || !part || part.state !== 'ok') return;
          const next = ggwMergeRows(cur, part);
          board.current = next;
          setLoad({ phase: 'loaded', p: next });
          armPending(next);
        })
        .catch(() => { if (alive.current && board.current) armPending(board.current); });
    }, poll * 1000);
  }, []);

  /* The main chain: the served refresh_sec while visible; out of window ONE re-GET at next_window_sec. */
  const armMain = useCallback((b: GgwBoard) => {
    clearMain();
    if (b.refresh_sec > 0) {
      const tick = () => {
        mainTimer.current = null;
        if (typeof document !== 'undefined' && document.hidden) {
          mainTimer.current = setTimeout(tick, b.refresh_sec * 1000);
          return;
        }
        loadAllRef.current();
      };
      mainTimer.current = setTimeout(tick, b.refresh_sec * 1000);
    } else if (b.next_window_sec != null && b.next_window_sec > 0) {
      mainTimer.current = setTimeout(() => { mainTimer.current = null; loadAllRef.current(); }, b.next_window_sec * 1000);
    }
  }, []);

  const loadAll = useCallback(() => {
    getJson(GGW_PATH)
      .then((raw) => {
        if (!alive.current) return;
        const p = parseGgw(raw);
        if (!p) throw new Error('junk');
        if (p.state === 'error' && board.current) {
          /* The server said why it could not build the board: keep the board up, print ITS words, keep the chain. */
          setServedErr(p.reason);
          setRefreshFailed(!p.reason);
          armMain(board.current);
          return;
        }
        setRefreshFailed(false);
        setServedErr(null);
        if (p.state === 'ok') {
          board.current = p;
          armMain(p);
          armPending(p);
        } else {
          board.current = null;
          clearMain();
          clearPend();
        }
        setLoad({ phase: 'loaded', p });
      })
      .catch(() => {
        if (!alive.current) return;
        if (board.current) {
          setRefreshFailed(true);
          armMain(board.current);
        } else {
          setLoad((l) => (l.phase === 'loaded' ? l : { phase: 'failed' }));
        }
      });
  }, [armMain, armPending]);
  loadAllRef.current = loadAll;

  useEffect(() => {
    alive.current = true;
    loadAll();
    return () => { alive.current = false; clearMain(); clearPend(); };
  }, [loadAll]);

  /* ?focus=SYM (a push deep link): scroll that tile into view and outline it, once. */
  useEffect(() => {
    if (focusDone.current || !focus || load.phase !== 'loaded' || load.p.state !== 'ok') return;
    const at = load.p.rows.findIndex((r) => r.symbol === focus);
    if (at < 0) return;
    focusDone.current = true;
    if (Number.isFinite(size)) setPage(ggwPageOf(at, size as number));
    setPick(null);
    setOutlined(focus);
    pendingFocus.current = focus;
  }, [focus, load, size]);
  /* Review fix: the scroll waits until the focused tile is SHOWN — a tile on page 2+ is still hidden (no box, so
   * scrollIntoView is a no-op) in the commit that asks for its page. */
  useEffect(() => {
    const want = pendingFocus.current;
    if (!want || typeof document === 'undefined') return;
    const el = document.getElementById(`ggw-${want}`);
    if (!el || el.hidden) return;
    pendingFocus.current = null;
    el.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
  });

  /* ⤢ the stretched name left the list → forget it (it never re-opens by itself when the name is added back). */
  useEffect(() => {
    if (!stretched || load.phase !== 'loaded' || load.p.state !== 'ok') return;
    if (!load.p.rows.some((r) => r.symbol === stretched)) setStretched(null);
  }, [stretched, load]);

  /* ← → move the view a page (never while typing in the add box, never under the full-screen view). */
  const rowsNow = load.phase === 'loaded' && load.p.state === 'ok' ? load.p.rows : null;
  const nRows = rowsNow?.length ?? 0;
  useEffect(() => {
    if (stretched || !Number.isFinite(size) || nRows <= (size as number)) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      const d = e.key === 'ArrowLeft' ? -1 : 1;
      setPick(null);
      setPage((pg) => ggwClampPage(ggwClampPage(pg, nRows, size as number) + d, nRows, size as number));
      boardRef.current?.scrollIntoView?.({ block: 'start', behavior: 'smooth' });
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [stretched, size, nRows]);
  /* Review fix: the stored page follows the list (removals, a smaller pick), so a later add never jumps the view back. */
  useEffect(() => {
    if (nRows > 0 && Number.isFinite(size)) setPage((pg) => ggwClampPage(pg, nRows, size as number));
  }, [nRows, size]);
  /* In the full-screen view ◀ ▶ / ← → step through HIS list one stock at a time (wrapping), and the board's page
   * follows, so closing it lands on the stock last viewed. */
  const stepStretch = useCallback((d: -1 | 1) => {
    if (!rowsNow || rowsNow.length < 2) return;
    const i = rowsNow.findIndex((r) => r.symbol === stretched);
    const j = ((i < 0 ? 0 : i) + d + rowsNow.length) % rowsNow.length;
    setStretched(rowsNow[j].symbol);
    if (Number.isFinite(size)) setPage(ggwPageOf(j, size as number));
  }, [rowsNow, size, stretched]);

  const write = (method: 'POST' | 'DELETE', sym: string) => {
    setBusy(true);
    fetch(`${API}${ggwSymbolPath(sym)}`, { method, credentials: 'include', cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((a: GgwWriteAnswer | null) => {
        if (!alive.current) return;
        setMsg(a && typeof a.text === 'string' && a.text.trim() ? a.text : null);
        if (method === 'POST' && a && (a.state === 'added' || a.state === 'already')) setDraft('');
      })
      .catch(() => { if (alive.current) setMsg(null); })
      .finally(() => {
        void loadGgwList(true);                                  // the ➕/➖ card buttons read the same list — even after unmount
        if (!alive.current) return;
        setBusy(false);
        loadAllRef.current();
      });
  };

  const onAdd = (e: FormEvent) => {
    e.preventDefault();
    const sym = draft.trim();
    if (!sym || busy) return;
    write('POST', sym);
  };

  if (load.phase === 'loading') return <div className="ggw-board" aria-busy="true" />;
  if (load.phase === 'failed') {
    return <div className="ggw-board"><p className="ggw-line ggw-warn">{GGW_FETCH_FAILED}</p></div>;
  }
  const p = load.p;
  if (p.state === 'owner_only') {
    return <div className="ggw-board"><p className="ggw-line ggw-owner-only">{p.reason}</p></div>;
  }
  if (p.state === 'error') {
    return (
      <div className="ggw-board">
        <p className="ggw-line ggw-warn ggw-served-error" data-testid="ggw-served-error">{p.reason ?? GGW_FETCH_FAILED}</p>
      </div>
    );
  }

  const addLabel = p.add_label ?? '';
  /* A name removed (here or on another device) while stretched simply closes the full-screen view. */
  const stretchRow = stretched ? p.rows.find((r) => r.symbol === stretched) ?? null : null;
  const paged = Number.isFinite(size) && p.rows.length > (size as number);
  const cur = paged ? ggwClampPage(page, p.rows.length, size as number) : 0;
  const pages = paged ? ggwPageCount(p.rows.length, size as number) : 1;
  const onPage = (i: number) => (usePick ? picked.includes(p.rows[i].symbol)
    : !paged || ggwPageOf(i, size as number) === cur);
  /* 2026-11-16 — a ticker button toggles that name; the names on screen now are the base. */
  const toggle = (sym: string) => {
    const list = p.rows.map((r) => r.symbol);
    setPick(ggwToggleShown(list, list.filter((_s, i) => onPage(i)), sym));
    boardRef.current?.scrollIntoView?.({ block: 'start', behavior: 'smooth' });
  };
  return (
    <div className="ggw-board" data-testid="ggw-board" ref={boardRef}>
      <div className="ggw-head" ref={headRef}>
        {p.title ? <h2 className="ggw-title">{p.title}</h2> : null}
        <form className="ggw-add" onSubmit={onAdd}>
          <input className="ggw-input" type="text" value={draft} aria-label={addLabel || undefined}
                 placeholder={(p.full ? p.full_text : p.add_placeholder) ?? undefined}
                 title={p.full ? p.full_text ?? undefined : undefined}
                 disabled={p.full || busy} autoCapitalize="characters" autoComplete="off" spellCheck={false}
                 onChange={(e) => setDraft(e.target.value)} />
          <button type="submit" className="ggw-btn ggw-add-btn" disabled={p.full || busy || !draft.trim()}>
            {addLabel}
          </button>
        </form>
        {p.full && p.full_text ? <span className="ggw-line ggw-full" data-testid="ggw-full">{p.full_text}</span> : null}
        {msg ? <span className="ggw-line ggw-msg" data-testid="ggw-msg">{msg}</span> : null}
        {p.pass?.text ? (
          <span className={`ggw-line ggw-pass${p.pass.stale ? ' ggw-warn' : ''}`} data-testid="ggw-pass">
            {p.pass.stale ? '⚠️ ' : ''}{p.pass.text}
          </span>
        ) : null}
        {/* 🤖 the served auto head: title (hover = the served hint), the unreadable word, the empty word, and the
            collapsed strip of this session's removals (each line = the served text_full, verbatim). */}
        {p.auto?.title ? (
          <span className="ggw-line ggw-auto-title" data-testid="ggw-auto-title" title={p.auto.hint ?? undefined}>
            {p.auto.title}
          </span>
        ) : null}
        {/* 🎯 2026-11-17 (spec ggwaplus2): the served line naming the A+ names the last minute could not seat. */}
        {p.auto?.skipped_text ? (
          <span className="ggw-line ggw-warn" data-testid="ggw-auto-skipped">{p.auto.skipped_text}</span>
        ) : null}
        {p.auto?.state === 'unreadable' && p.auto.text ? (
          <span className="ggw-line ggw-warn" data-testid="ggw-auto-unreadable">{p.auto.text}</span>
        ) : null}
        {p.auto && p.auto.n === 0 && p.auto.empty_text ? (
          <span className="ggw-line ggw-auto-empty" data-testid="ggw-auto-empty">{p.auto.empty_text}</span>
        ) : null}
        {p.auto && p.auto.removed.length ? (
          <details className="ggw-auto-removed" data-testid="ggw-auto-removed">
            <summary>{p.auto.removed_title ?? '🤖'}</summary>
            {p.auto.removed.map((r, i) => (
              <p key={`${r.symbol}-${r.at_et}-${i}`} className="ggw-line" data-testid="ggw-auto-removed-line">{r.text_full}</p>
            ))}
          </details>
        ) : null}
        {servedErr ? (
          <span className="ggw-line ggw-warn ggw-served-error" data-testid="ggw-served-error">{`⚠️ ${servedErr}`}</span>
        ) : null}
        {refreshFailed ? <span className="ggw-line ggw-warn">{`⚠️ ${GGW_FETCH_FAILED}`}</span> : null}
        {feedWord ? <span className="ggw-line ggw-warn" data-testid="ggw-feed-word">{feedWord}</span> : null}
        {p.legend.length ? (
          <span className="ggw-legend">
            {p.legend.map((l) => {
              const c = (EMA_BOLD as Record<string, { color: string; width: number }>)[l.tone];
              return (
                <span key={l.tone} className="ggw-legend-item" data-tone={l.tone}>
                  <i className="ggw-swatch" style={c ? { background: c.color, height: c.width } : undefined} />
                  {l.label}
                </span>
              );
            })}
          </span>
        ) : null}
        {p.rows.length && !phone ? (
          <span className="ggw-layout" role="group" aria-label="Charts per screen" data-testid="ggw-layout">
            {GGW_LAYOUT_ORDER.map((l) => (
              <button key={l} type="button" className={`ggw-btn ggw-layout-btn${l === layout ? ' is-on' : ''}`}
                      aria-pressed={l === layout} title={`${l} per screen`} data-testid={`ggw-layout-${l}`}
                      onClick={() => setLayout(l)}>
                {String(l)}
              </button>
            ))}
            <span className="ggw-layout-label">per screen</span>
          </span>
        ) : null}
        {p.info && (p.info.honesty || p.info.uptrend_rule || p.info.push_text || p.info.auto_text) ? (
          <details className="ggw-info">
            <summary aria-label="info">{'ℹ️'}</summary>
            {p.info.honesty ? <p className="ggw-line">{p.info.honesty}</p> : null}
            {p.info.uptrend_rule ? <p className="ggw-line">{p.info.uptrend_rule}</p> : null}
            {p.info.push_text ? <p className="ggw-line">{p.info.push_text}</p> : null}
            {p.info.auto_text ? <p className="ggw-line" data-testid="ggw-info-auto">{p.info.auto_text}</p> : null}
          </details>
        ) : null}
      </div>
      {p.rows.length > 1 ? (
        <nav className="ggw-pager" aria-label="Move the view" data-testid="ggw-pager">
          <button type="button" className="ggw-btn ggw-pager-btn" title={GGW_PAGER.prevTitle} aria-label={GGW_PAGER.prevTitle}
                  data-testid="ggw-pager-prev" disabled={!paged || (!usePick && cur <= 0)}
                  onClick={() => goPage(Math.max(0, cur - 1))}>
            {GGW_PAGER.prev}
          </button>
          {p.rows.map((r, i) => {
            /* 🤖 an auto name: the dashed item, the served tag before SYM, the served × title. */
            const rm = r.auto?.remove_title ?? (p.remove_label ? `${p.remove_label} ${r.symbol}` : r.symbol);
            return (
              <span key={r.symbol} className={`ggw-pager-item${r.auto ? ' ggw-pager-item--auto' : ''}${onPage(i) ? ' is-on' : ''}`}>
                {/* 🎯 a name a Gajjala board reads A+ this session: the served tag first + the --aplus outline. */}
                <button type="button"
                        className={`ggw-btn ggw-pager-sym${r.aplus ? ' ggw-pager-sym--aplus' : ''}${onPage(i) ? ' is-on' : ''}`}
                        aria-pressed={onPage(i)} data-testid={`ggw-pager-${r.symbol}`}
                        title={r.aplus?.title ?? undefined}
                        onClick={() => toggle(r.symbol)}>
                  {[r.aplus?.tag, r.auto?.tag, r.symbol].filter(Boolean).join(' ')}
                </button>
                <button type="button" className="ggw-btn ggw-pager-x" title={rm} aria-label={rm} disabled={busy}
                        data-testid={`ggw-pager-x-${r.symbol}`} onClick={() => write('DELETE', r.symbol)}>
                  {'×'}
                </button>
              </span>
            );
          })}
          <button type="button" className="ggw-btn ggw-pager-btn" title={GGW_PAGER.nextTitle} aria-label={GGW_PAGER.nextTitle}
                  data-testid="ggw-pager-next" disabled={!paged || (!usePick && cur >= pages - 1)}
                  onClick={() => goPage(Math.min(pages - 1, cur + 1))}>
            {GGW_PAGER.next}
          </button>
          {paged && !usePick ? <span className="ggw-pager-at" data-testid="ggw-pager-at">{`${cur + 1} / ${pages}`}</span> : null}
        </nav>
      ) : null}
      {p.rows.length ? (
        <div className={`ggw-grid ggw-grid--cols${grid.cols}${fit ? ' ggw-grid--fit' : ''}`}
             ref={gridRef} data-layout={layout} data-pick={usePick ? picked.length : undefined}
             style={fit ? ({ '--ggw-row-h': `${rowH}px` } as CSSProperties) : undefined}>
          {p.rows.map((r, i) => (
            <Tile key={r.symbol} row={r} phone={phone} fit={fit} removeLabel={p.remove_label} busy={busy}
                  focused={outlined === r.symbol} onRemove={(s) => write('DELETE', s)} onStretch={setStretched}
                  offPage={!onPage(i)} live={liveOf(r, onPage(i))} siNote />
          ))}
        </div>
      ) : (
        p.empty_text ? <p className="ggw-line ggw-empty" data-testid="ggw-empty">{p.empty_text}</p> : null
      )}
      {stretchRow ? (
        <GgwStretch row={stretchRow} phone={phone} removeLabel={p.remove_label} onClose={closeStretch}
                 onStep={p.rows.length > 1 ? stepStretch : null} live={liveOf(stretchRow, true)} siNote />
      ) : null}
    </div>
  );
}
