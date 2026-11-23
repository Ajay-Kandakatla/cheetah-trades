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
 * collapsed ℹ️ with the served honesty, K5 rule and push sentence — printed ONCE) and a 3-column grid of tiles,
 * newest added first, as served (the server orders; this board never re-sorts). Each tile: SYM, the served row text / session stamp / as-of, the 🔔 rang chips,
 * one Yahoo ↗, ✕ (DELETE, no confirm); the replay's dark panel with the 1-min chart full width on top and the 5-min +
 * 15-min side by side below (3-min + 5-min until 2026-11-23) — PatternChart chartOnly (no SEPA link), emaStyle bold, the served 04:00 axis.
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
 * list order orders this board — newest added first since 2026-11-19 (served; names from before 11-19 keep his order
 * below them); the 🤖 auto rows follow his, in the order they were added (the server never re-sorts them).
 * 🏷️ 2026-11-18 (spec wtags) — Ajay: "Also add Short Interest tag and other tags on top of stock ticker information for
 * me to read, like here": the chips now ride in a tags row ABOVE each tile's head, mounted by GajjalaWatchTile from its
 * own module (GajjalaWatchTags.tsx — 🚀 / 🩳 on every name, the 🚩 card's own tags on a name carded today); this
 * file mounts none of them and still orders nothing by them.
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
 * a board's 🧠 read, not an entry.
 *
 * 🆕 2026-11-19 (watch-newest spec §3.4) — Ajay: "When I add a new ticket they are gettinf added in to que but not active
 * … charts are not loading I amhaving to click on the chips again" and "The X buttons are not working". A name of his
 * (or a 🎯 A+) added since he last changed the view (`ggw.pickAt`, lib) or new to this browser (`ggw.seen`) joins his
 * pick; an ordinary 🤖 potential never does. A box add / re-add is joined (or its page shown), outlined and scrolled to
 * once; a page open outlines only a name of his this browser has not shown yet. In the pages view a list change keeps
 * the first shown name on screen (the anchor — HIS CALL #6: a card ➕ while page 2+ is open lands on page 1 unseen).
 * ✕ / × hide the name at once and are never disabled by another write: writes run one after another in a queue that
 * cannot die (`then(task, task)`, every task catches its own failure), ONE full re-GET when it drains; a served error
 * or a failed request brings the name back. A write that never answers holds the queue (no abort time — HIS CALL #12).
 * Loads are sequenced: a stale full GET or pending poll never overwrites a newer board. Out of window a pending name
 * past the cap is re-read every served `pending_late_poll_sec` and prints the served `late_text`; in window the minute
 * re-GET re-reads it. UNMEASURED — display only.
 *
 * 🗂 2026-11-22 (spec watch_org rev 4 §3.5, WP-FE-WATCH) — Ajay: "I need gajjalas watch tab little more organized. With
 * less info, I want to know previous day winner auto additions vs intraday may be a time stamp. or something figure out
 * a better way to organize that info for me.." and "Manual ones I add them need to be on top then auto intraday..".
 * ORG MODE only when the server serves sections (lib ggwSectionsOn — an older server or SECTIONS_ON = False → the board
 * above, byte for byte). The server groups and orders the rows and writes every word; this board holds NO section key
 * list — it draws whatever sections are served, in served order (a later served key needs no change here). In org mode:
 * compact tiles (served setup chip, the ONE time line, the ⋯ drawer); the pager carries the served section labels
 * inline; on the PHONE each served section gets a collapsible header (remembered in this browser, `ggw.collapsed`; desktop
 * keeps the fitted pages, no headers); a push link (?focus=), a box add, the first-load outline and a pager tap into a
 * FOLDED section open it first, then scroll once [C5]; the 🤖 title line and the EMA legend move into ℹ️ (with every
 * served section hint — the phone has no hover). Layout only: nothing rings, adds, caps or evicts differently.
 *
 * 📈📐 2026-11-23 (vwapzones spec §3.9, WP fe-watch) — Ajay: "can you add vwap and supply demand zone in the daily time
 * frame on the watch list please" · "Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15 accross board" ·
 * "Add vwap and supply demand too". The served frames are 1m / 5m / 15m (the tile draws them); the legend's swatches come
 * from lib ggwLegendSwatch (9 / 21 EMA, the VWAP line, the daily zones as a dashed outline — the look the chart draws),
 * each entry's served `title` is its hover, and ℹ️ prints the served `info.vwap_text` / `info.zones_text` (a phone has no
 * hover). Display only — nothing gates, sorts or rings on either. UNMEASURED. */
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import {
  GGW_FETCH_FAILED, GGW_FOCUS_PARAM, ggwLegendSwatch, ggwRowLive, GGW_LAYOUTS, GGW_PATH,
  ggwClampPage, ggwLiveSymbols, ggwPageCount, ggwPageOf, ggwMergeRows, ggwPendingSymbols, ggwRowsPath,
  readGgwSeen, saveGgwSeen, ggwPickGrid,
  ggwAnchorPage, ggwDropFromPick, ggwFreshNames, ggwJoinPick, ggwPendingPlan, ggwPrunePick, ggwLivePick, ggwAddedMs, ggwRowsKey, ggwUnseenOwn, ggwWithout,
  readGgwPickAt, saveGgwPickAt, ggwSymbolPath, ggwToggleShown, GGW_URL, ggwViewParams, parseGgwLayout,
  parseGgwPage, parseGgwPick, readGgwPick, saveGgwPick, parseGgw, readGgwLayout, saveGgwLayout,
  GGW_SECTION_GLYPH, ggwGroupStarts, ggwRevealGroup, ggwSectionsOn, ggwToggleCollapsed, readGgwCollapsed,
  saveGgwCollapsed,
  type GgwBoard, type GgwLayout, type GgwPayload, type GgwRow, type GgwWriteAnswer,
} from '../lib/gajjalaWatch';
import { ggwApplyBatch, ggwFrameMetas, type GgwFrameMeta, type GgwLiveMap, type GgwLiveSym } from '../lib/ggwLive';
import { useGgwLive, type GgwBatch } from '../hooks/useGgwLive';
/* 2026-11-16 (ggcard3 WP-A): the tile, its frames and the ⤢ full-screen view live in GajjalaWatchTile.tsx (a pure move)
 * so the 🚩 cards open the SAME view. */
import { GgwStretch, Tile, usePhone } from './GajjalaWatchTile';
/* 🏷️ 2026-11-18 (spec wtags §3.5): the tags row's board-level read — ONE request for the names carded on today's 🚩 board. */
import { useGgwTags } from './GajjalaWatchTags';
import { GgHardToBorrowFault } from './GgHardToBorrow';
/* 2026-11-18 (cardview WP-A): the per-screen pick, the pager and the fitted-row hook live in GajjalaWatchLayout.tsx (a
 * pure move) so the 🚩 / 🧪 card grid draws the SAME controls. */
import { GgwLayoutPick, GgwPager, useGgwFitRows } from './GajjalaWatchLayout';
import { ggwFold, loadGgwList } from '../lib/ggWatchList';
import { GgwBrokerButton, GgwBrokerHead, useGgwBrokerMark } from './GgwBrokerMark';   // 🚫 2026-11-19 (spec watchfid)
import '../styles/gajjalaWatch.css';

type Load = { phase: 'loading' } | { phase: 'failed' } | { phase: 'loaded'; p: GgwPayload };
const NO_SYMBOLS: string[] = [];

const getJson = (path: string) =>
  fetch(`${API}${path}`, { credentials: 'include', cache: 'no-store' })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))));

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
  /* 🆕 2026-11-19: HIS view actions stamp `ggw.pickAt` — never a mount, an activation pass, a box add or ?focus=. */
  const markView = () => saveGgwPickAt(Date.now());
  /* A page move by HIM (◀ ▶, a ticker, ← →) brings the board's top to the window's top, so the two tiles fill it. */
  const goPage = (pg: number) => {
    markView();
    setPick(null);
    setPage(pg);
    boardRef.current?.scrollIntoView?.({ block: 'start', behavior: 'smooth' });
  };
  const setLayout = (l: GgwLayout) => {
    markView();
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
  /* 🆕 2026-11-19 — load sequencing, the optimistic ×, the write queue, the box add, the first load, the pages anchor. */
  const [late, setLate] = useState<Set<string>>(() => new Set());
  const loadSeq = useRef(0);
  const applied = useRef(0);
  const removing = useRef<Map<string, number | null>>(new Map());
  const writeQ = useRef<Promise<void>>(Promise.resolve());
  const writesLeft = useRef(0);
  const justAdded = useRef<{ sym: string; at: number } | null>(null);
  const firstOk = useRef(true);
  const anchor = useRef<string | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<HTMLDivElement>(null);
  /* The pick (his toggled names still on the list) and its grid; no pick → the layout's own grid. */
  const rowsNow = load.phase === 'loaded' && load.p.state === 'ok' ? load.p.rows : null;
  const listNow = rowsNow ? rowsNow.map((r) => r.symbol) : [];
  /* 🗂 2026-11-22 — org mode (served sections) and the PHONE's folded sections (served keys, remembered here). */
  const orgNow = load.phase === 'loaded' && load.p.state === 'ok' && ggwSectionsOn(load.p);
  const [collapsed, setCollapsed] = useState<ReadonlyArray<string>>(() => readGgwCollapsed());
  useEffect(() => { saveGgwCollapsed(collapsed); }, [collapsed]);
  const foldOn = useRef(false);
  foldOn.current = orgNow && phone;
  /* [C5] a focus / box add / first-load outline / pager tap into a FOLDED phone section opens it first (the scroll waits
   * for the tile to be shown — the effect below checks `hidden`). Off the phone or outside org mode: nothing. */
  const reveal = (rows: ReadonlyArray<GgwRow>, sym: string) => {
    if (foldOn.current) setCollapsed((c) => ggwRevealGroup(c, rows, sym));
  };
  /* 🆕 2026-11-19: a name of his (or a 🎯 A+) new to this view joins the pick (first) — never left inactive. Keyed on
   * symbol + add time + the join bit, so a 🤖 potential turning 🎯 A+ in place joins at THAT load. */
  const rowsKey = rowsNow ? ggwRowsKey(rowsNow) : '';
  useEffect(() => {
    if (!rowsKey || !rowsNow || !rowsNow.length) return;
    const list = rowsNow.map((r) => r.symbol);
    const seen = readGgwSeen();
    const fresh = ggwFreshNames(rowsNow, { seen, pickAt: readGgwPickAt(), nowMs: Date.now() });
    /* 🐛 2026-11-22 (WETO): a pick only ever holds listed names (or one a × is still hiding) — a dead pick turns into the
     * pages at the load where it died, so a name served again joins ONLY by the fresh rule above. */
    const keep = [...list, ...Array.from(removing.current.keys())];
    /* review residual: a pick whose ONLY listed names were added AFTER this browser last set the view (`ggw.pickAt`) —
     * a card ➕ / another device re-adding a name of a dead pick before this browser reopened the Watch — cannot be his
     * pick of them → the pages. No pickAt on this browser (a shared show= link, a cold browser) → the pick is honoured. */
    const pickAtMs = readGgwPickAt();
    const after = pickAtMs == null ? [] : rowsNow
      .filter((r) => { const t = ggwAddedMs(r); return t != null && t > pickAtMs; }).map((r) => r.symbol);
    setPick((cur) => {
      const next = ggwJoinPick(ggwLivePick(ggwPrunePick(cur, keep), after), list, fresh);
      return (next ?? []).join(',') === (cur ?? []).join(',') ? cur : next;
    });
    if (firstOk.current) {
      firstOk.current = false;
      /* the first load only: a name of his this browser has NOT shown yet (a card ➕) — never one new by time alone */
      const s = focus ? null : ggwUnseenOwn(rowsNow, seen);
      if (s) {
        setOutlined(s);
        reveal(rowsNow, s);
        pendingFocus.current = s;
        const eff = !!pick && pick.some((x) => list.includes(x));
        if (!eff && Number.isFinite(size)) setPage(ggwPageOf(list.indexOf(s), size as number));
      }
    }
    /* a name hidden by × is still "seen", so a failed DELETE never re-joins it */
    saveGgwSeen([...list, ...Array.from(removing.current.keys()).filter((x) => !list.includes(x))]);
  }, [rowsKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const picked = pick ? pick.filter((s) => listNow.includes(s)) : [];
  const usePick = picked.length > 0;
  const grid = usePick ? ggwPickGrid(picked.length, GGW_LAYOUTS[layout].cols, GGW_LAYOUTS[layout].rows) : GGW_LAYOUTS[layout];
  const rowH = useGgwFitRows(gridRef, headRef, phone, load, grid.rows);
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
    /* 🆕 2026-11-19: past the cap the served late words show; out of window only, the late names are still re-read */
    const plan = ggwPendingPlan(pend, pendSince.current, now, {
      poll: b.pending_poll_sec, max: b.pending_wait_max_sec, latePoll: b.pending_late_poll_sec, refresh: b.refresh_sec,
    });
    setLate((prev) => (prev.size === plan.late.length && plan.late.every((s) => prev.has(s)) ? prev : new Set(plan.late)));
    clearPend();
    if (!plan.names.length || plan.delaySec <= 0) return;
    pendTimer.current = setTimeout(() => {
      pendTimer.current = null;
      if (typeof document !== 'undefined' && document.hidden) {           // the main-chain rule: re-arm, no fetch
        if (alive.current && board.current) armPending(board.current);
        return;
      }
      const issued = applied.current;
      getJson(ggwRowsPath(plan.names))
        .then((raw) => {
          if (!alive.current || applied.current !== issued) return;      // a newer full board landed: drop this answer
          const part = parseGgw(raw);
          const cur = board.current;
          if (!cur || !part || part.state !== 'ok') return;
          const next = ggwWithout(ggwMergeRows(cur, part), Array.from(removing.current.keys()));
          board.current = next;
          setLoad({ phase: 'loaded', p: next });
          armPending(next);
        })
        .catch(() => { if (alive.current && applied.current === issued && board.current) armPending(board.current); });
    }, plan.delaySec * 1000);
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
    const my = ++loadSeq.current;
    getJson(GGW_PATH)
      .then((raw) => {
        if (!alive.current || my !== loadSeq.current) return;          // a newer load owns the chain
        let p = parseGgw(raw);
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
          /* a × answered before this load was issued → the server's word wins; one still in flight stays hidden */
          for (const [s, seq] of Array.from(removing.current.entries())) if (seq != null && seq < my) removing.current.delete(s);
          p = ggwWithout(p, Array.from(removing.current.keys()));
          applied.current += 1;
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
        if (!alive.current || my !== loadSeq.current) return;
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
    reveal(load.p.rows, focus);
    pendingFocus.current = focus;
  }, [focus, load, size]); // eslint-disable-line react-hooks/exhaustive-deps
  /* 🆕 2026-11-19 — a name HE added from the box (added / already / replaced): joined to his pick (forced — the clocks may
   * differ), or in the pages view its page is shown; outlined and scrolled to once. The pick is never cleared. */
  useEffect(() => {
    const j = justAdded.current;
    if (!j || load.phase !== 'loaded' || load.p.state !== 'ok') return;
    const rows = load.p.rows;
    const idx = rows.findIndex((r) => ggwFold(r.symbol) === ggwFold(j.sym));
    if (idx < 0) {
      if (applied.current > j.at) justAdded.current = null;            // a newer board does not list it: give up
      return;
    }
    const s = rows[idx].symbol;
    const list = rows.map((r) => r.symbol);
    if (pick && pick.some((x) => list.includes(x))) setPick((cur) => ggwJoinPick(cur, list, [s]));
    else if (Number.isFinite(size)) setPage(ggwPageOf(idx, size as number));
    setOutlined(s);
    reveal(rows, s);
    pendingFocus.current = s;
    justAdded.current = null;
  }, [load]); // eslint-disable-line react-hooks/exhaustive-deps
  /* 🆕 2026-11-19 — the pages view keeps the first shown name on screen when the list changes (a name added on top, one
   * above removed). Skipped while a focus / box add / first-load outline is moving the view. */
  const pagedNow = !!rowsNow && Number.isFinite(size) && rowsNow.length > (size as number);
  const curNow = pagedNow && rowsNow ? ggwClampPage(page, rowsNow.length, size as number) : 0;
  useEffect(() => {
    if (!rowsNow || !pagedNow || pendingFocus.current || !anchor.current) return;
    if (pick && pick.some((x) => listNow.includes(x))) return;
    const pg = ggwAnchorPage(listNow, anchor.current, size as number);
    if (pg != null) setPage(pg);
  }, [rowsKey]); // eslint-disable-line react-hooks/exhaustive-deps
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
  /* the anchor = the first name shown on the (clamped) page; none on a pick, a phone or an unpaged board */
  useEffect(() => {
    const usingPick = !!pick && pick.some((x) => listNow.includes(x));
    anchor.current = rowsNow && pagedNow && !usingPick ? rowsNow[curNow * (size as number)]?.symbol ?? null : null;
  });

  /* ⤢ the stretched name left the list → forget it (it never re-opens by itself when the name is added back). */
  useEffect(() => {
    if (!stretched || load.phase !== 'loaded' || load.p.state !== 'ok') return;
    if (!load.p.rows.some((r) => r.symbol === stretched)) setStretched(null);
  }, [stretched, load]);

  /* ← → move the view a page (never while typing in the add box, never under the full-screen view). */
  /* 🏷️ 2026-11-18 — ONE room read for the names CARDED on today's 🚩 board (their served tags block says so); never for an
   * off-board name (no on-demand zone build for a name no Gajjala board asked about — HIS CALL #3). Empty list → no
   * request. Unconditional — hooks order. */
  const tagsOf = useGgwTags(rowsNow);
  const nRows = rowsNow?.length ?? 0;
  useEffect(() => {
    if (stretched || !Number.isFinite(size) || nRows <= (size as number)) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      const d = e.key === 'ArrowLeft' ? -1 : 1;
      markView();
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
    markView();
    setStretched(rowsNow[j].symbol);
    if (Number.isFinite(size)) setPage(ggwPageOf(j, size as number));
  }, [rowsNow, size, stretched]);

  /* 🆕 2026-11-19 — "The X buttons are not working": `busy` is the add box's own POST only; a × hides its name NOW. */
  const onAnswer = (method: 'POST' | 'DELETE', sym: string, a: GgwWriteAnswer | null) => {
    if (!alive.current) return;
    setMsg(a && typeof a.text === 'string' && a.text.trim() ? a.text : null);
    if (method === 'POST') {
      setBusy(false);
      if (a && (a.state === 'added' || a.state === 'already' || a.state === 'replaced')) {
        setDraft('');
        justAdded.current = { sym: typeof a.symbol === 'string' && a.symbol.trim() ? a.symbol : sym, at: applied.current };
      }
    } else if (a && (a.state === 'removed' || a.state === 'dismissed' || a.state === 'absent')) {
      removing.current.set(sym, loadSeq.current);
      setPick((cur) => ggwDropFromPick(cur, sym));
    } else {
      removing.current.delete(sym);                                // a served error / no answer: the drain reload brings it back
    }
  };
  const onFail = (method: 'POST' | 'DELETE', sym: string) => {
    try {
      if (method === 'DELETE') removing.current.delete(sym);
      if (!alive.current) return;
      if (method === 'POST') setBusy(false);
      setMsg(null);
    } catch { /* a task never rejects */ }
  };
  const settle = () => {
    try {
      writesLeft.current -= 1;
      if (writesLeft.current > 0) return;
      void loadGgwList(true);                                    // the ➕/➖ card buttons read the same list — even after unmount
      if (alive.current) loadAllRef.current();                   // ONE full re-GET per drain
    } catch { /* settle never throws */ }
  };
  const write = (method: 'POST' | 'DELETE', sym: string) => {
    if (method === 'POST') {
      setBusy(true);
    } else {
      removing.current.set(sym, null);
      const cur = board.current;
      if (cur) {
        const next = ggwWithout(cur, [sym]);
        if (next !== cur) { board.current = next; setLoad({ phase: 'loaded', p: next }); }
      }
    }
    writesLeft.current += 1;
    const task = (): Promise<void> =>
      Promise.resolve()
        .then(() => fetch(`${API}${ggwSymbolPath(sym)}`, { method, credentials: 'include', cache: 'no-store' }))
        .then((r) => (r.ok ? r.json() : null))
        .then((a: GgwWriteAnswer | null) => onAnswer(method, sym, a))
        .catch(() => onFail(method, sym))
        .finally(settle);
    writeQ.current = writeQ.current.then(task, task);            // a rejected link can never skip a later write
  };
  /* 🚫 2026-11-19 (spec watchfid): the tile's one-way mark — POST his 🚫 list, then the same DELETE as ✕; one re-GET. */
  const mark = useGgwBrokerMark((text) => { setMsg(text); loadAllRef.current(); });

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
  /* 🆕 past the pending cap a pending tile prints the served "still reading" words */
  const lateRow = (r: GgwRow): GgwRow => (late.has(r.symbol) && r.late_text ? { ...r, text: r.late_text } : r);
  /* 🗂 2026-11-22 — org mode: served sections only (no key list here). Phone headers + folds; desktop none. */
  const org = ggwSectionsOn(p);
  const starts = org ? ggwGroupStarts(p.rows, p.sections) : [];
  const headAt = org && phone ? new Map(starts.map((g) => [g.at, g.section] as const)) : null;
  const folded = (r: GgwRow): boolean => org && phone && !!r.org?.group && collapsed.includes(r.org.group);
  const shown = (r: GgwRow, i: number): boolean => onPage(i) && !folded(r);
  const toggle = (sym: string) => {
    const list = p.rows.map((r) => r.symbol);
    markView();
    /* 🗂 [C5] a pager tap on a name in a FOLDED phone section opens that section first and scrolls to the name once
     * (it never turns the name off); a name hidden by his pick too is then toggled on as before. */
    const at = list.indexOf(sym);
    if (at >= 0 && folded(p.rows[at])) {
      reveal(p.rows, sym);
      if (onPage(at)) { pendingFocus.current = sym; return; }
    }
    setPick(ggwToggleShown(list, list.filter((_s, i) => onPage(i)), sym));
    boardRef.current?.scrollIntoView?.({ block: 'start', behavior: 'smooth' });
  };
  const legend = p.legend.length ? (
    <span className="ggw-legend">
      {p.legend.map((l) => {
        const sw = ggwLegendSwatch(l.tone);
        return (
          <span key={l.tone} className="ggw-legend-item" data-tone={l.tone} title={l.title ?? undefined}>
            <i className={sw.cls} style={sw.style} />
            {l.label}
          </span>
        );
      })}
    </span>
  ) : null;
  const autoTitle = p.auto?.title ? (
    <span className="ggw-line ggw-auto-title" data-testid="ggw-auto-title" title={p.auto.hint ?? undefined}>
      {p.auto.title}
    </span>
  ) : null;
  const orgInfo = org && (!!autoTitle || !!legend || (p.sections ?? []).some((s) => !!s.hint));
  const tileOf = (r: GgwRow, i: number) => (
    <Tile key={r.symbol} row={lateRow(r)} phone={phone} fit={fit} removeLabel={p.remove_label} busy={false}
          focused={outlined === r.symbol} onRemove={(s) => write('DELETE', s)} onStretch={setStretched}
          offPage={!shown(r, i)} live={liveOf(r, shown(r, i))} siNote tags={tagsOf(r)} compact={org}
          actions={<GgwBrokerButton row={r} block={p.broker ?? null} busy={busy || mark.busy} onMark={mark.mark} />} />
  );
  return (
    <div className="ggw-board" data-testid="ggw-board" ref={boardRef}>
      <div className="ggw-head" ref={headRef}>
        {p.title ? <h2 className="ggw-title">{p.title}</h2> : null}
        <form className="ggw-add" onSubmit={onAdd}>
          <input className="ggw-input" type="text" value={draft} aria-label={addLabel || undefined}
                 placeholder={(p.full_blocked ? p.full_text : p.add_placeholder) ?? undefined}
                 disabled={p.full_blocked || busy} autoCapitalize="characters" autoComplete="off" spellCheck={false}
                 onChange={(e) => setDraft(e.target.value)} />
          {/* 🔁 2026-11-18 (Ajay: "For watch list when I add new ones remove the ones that are not active" → "Oldest
            * added"): at the cap the box stays OPEN — the add replaces the oldest he added; only the all-🎯 A+ case
            * (full_blocked) closes it, and its reason is the visible ggw-full line below, never a hover title. */}
          <button type="submit" className="ggw-btn ggw-add-btn" disabled={p.full_blocked || busy || !draft.trim()}>
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
        {org ? null : autoTitle}
        {/* 🎯 2026-11-17 (spec ggwaplus2): the served line naming the A+ names the last minute could not seat. */}
        {p.auto?.skipped_text ? (
          <span className="ggw-line ggw-warn" data-testid="ggw-auto-skipped">{p.auto.skipped_text}</span>
        ) : null}
        <GgwBrokerHead block={p.broker ?? null} err={mark.err} />
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
        {/* 🔒 2026-11-22: the served Hard to borrow fault line (a stock threshold list could not be read); nothing otherwise. */}
        <GgHardToBorrowFault testid="ggw-htb-fault" className="ggw-line ggw-warn" inline />
        {feedWord ? <span className="ggw-line ggw-warn" data-testid="ggw-feed-word">{feedWord}</span> : null}
        {org ? null : legend}
        {p.rows.length && !phone ? (
          <GgwLayoutPick layout={layout} onPick={setLayout} />
        ) : null}
        {orgInfo || (p.info && (p.info.honesty || p.info.uptrend_rule || p.info.push_text || p.info.auto_text
          || p.info.vwap_text || p.info.zones_text)) ? (
          <details className="ggw-info">
            <summary aria-label="info">{'ℹ️'}</summary>
            {/* 🗂 org mode: the 🤖 title (+ its served hint — no hover on a phone), the legend, every served section hint */}
            {org ? autoTitle : null}
            {org && p.auto?.title && p.auto.hint ? <p className="ggw-line" data-testid="ggw-info-auto-hint">{p.auto.hint}</p> : null}
            {org ? legend : null}
            {org ? (p.sections ?? []).map((s) => (s.hint ? (
              <p key={`hint-${s.key}`} className="ggw-line" data-testid={`ggw-info-section-${s.key}`}>{s.hint}</p>
            ) : null)) : null}
            {p.info?.honesty ? <p className="ggw-line">{p.info.honesty}</p> : null}
            {p.info?.uptrend_rule ? <p className="ggw-line">{p.info.uptrend_rule}</p> : null}
            {p.info?.push_text ? <p className="ggw-line">{p.info.push_text}</p> : null}
            {p.info?.auto_text ? <p className="ggw-line" data-testid="ggw-info-auto">{p.info.auto_text}</p> : null}
            {/* 📈📐 2026-11-23: the served VWAP / daily-zones sentences (the legend hover's words — a phone has no hover). */}
            {p.info?.vwap_text ? <p className="ggw-line" data-testid="ggw-info-vwap">{p.info.vwap_text}</p> : null}
            {p.info?.zones_text ? <p className="ggw-line" data-testid="ggw-info-zones">{p.info.zones_text}</p> : null}
          </details>
        ) : null}
      </div>
      {p.rows.length > 1 ? (
        <GgwPager rows={p.rows} onPage={onPage} paged={paged} cur={cur} pages={pages} usePick={usePick} busy={false}
                  removeLabel={p.remove_label} onToggle={toggle} onPrev={() => goPage(Math.max(0, cur - 1))}
                  onNext={() => goPage(Math.min(pages - 1, cur + 1))} onRemove={(s) => write('DELETE', s)}
                  groups={org ? starts : undefined} />
      ) : null}
      {p.rows.length ? (
        <div className={`ggw-grid ggw-grid--cols${grid.cols}${fit ? ' ggw-grid--fit' : ''}`}
             ref={gridRef} data-layout={layout} data-pick={usePick ? picked.length : undefined}
             style={fit ? ({ '--ggw-row-h': `${rowH}px` } as CSSProperties) : undefined}>
          {p.rows.map((r, i) => {
            const sec = headAt ? headAt.get(i) ?? null : null;
            if (!sec) return tileOf(r, i);
            const isFolded = collapsed.includes(sec.key);
            return [
              <h3 key={`sec-${sec.key}`} className={`ggw-section${isFolded ? ' ggw-section--folded' : ''}`}
                  data-testid={`ggw-section-${sec.key}`}>
                <button type="button" className="ggw-section-btn" aria-expanded={!isFolded} title={sec.hint ?? undefined}
                        data-testid={`ggw-section-btn-${sec.key}`}
                        onClick={() => setCollapsed((c) => ggwToggleCollapsed(c, sec.key))}>
                  {`${isFolded ? GGW_SECTION_GLYPH.closed : GGW_SECTION_GLYPH.open} ${sec.text}`}
                </button>
              </h3>,
              tileOf(r, i),
            ];
          })}
        </div>
      ) : (
        p.empty_text ? <p className="ggw-line ggw-empty" data-testid="ggw-empty">{p.empty_text}</p> : null
      )}
      {stretchRow ? (
        <GgwStretch row={lateRow(stretchRow)} phone={phone} removeLabel={p.remove_label} onClose={closeStretch}
                 onStep={p.rows.length > 1 ? stepStretch : null} live={liveOf(stretchRow, true)} siNote tags={tagsOf(stretchRow)}
                 compact={org} />
      ) : null}
    </div>
  );
}
