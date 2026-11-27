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
 * (?symbols=) every pending_poll_sec up to pending_wait_max_sec; one full re-GET after an add or a remove; back to the
 * tab with the last full GET at least one refresh_sec old → one GET at once (lib/ggwReturn).
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
 * the CLOSED stored bars; the next GET wins; a Watch row whose last minute read failed keeps its live tail (its bars are
 * today's); a prior-session row carries none (ggwRowLive); the batches reach the owner's
 * tabs only (events audience). The 9 / 21 tips follow the forming close (GGW_LIVE_EMA_TIP, HIS CALL
 * #1 answered 11-16). A hidden tile (a chip filter, a folded phone section) gets no live bars, and since 2026-11-25 on a
 * desktop neither does a tile away from the window (useGgwNear) — its charts never re-render on a batch. The served feed
 * word prints in the head only when the feed is degraded. docs/gajjala/watch_live_2026_11_16.md.
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
 * pick; an ordinary 🤖 potential never does. A box add / re-add is joined (or shown, with no pick), outlined and
 * scrolled to once; the first load outlines only a name of his this browser has not shown yet. Since 2026-11-25 (▦
 * below) nothing pages: a list change keeps the tile he is looking at where it is (the scroll hold, useGgwHold).
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
 * keeps the fitted rows, no headers — one scrolling grid since 2026-11-25); a push link (?focus=), a box add, the first-load outline and a pager tap into a
 * FOLDED section open it first, then scroll once [C5]; the 🤖 title line and the EMA legend move into ℹ️ (with every
 * served section hint — the phone has no hover). Layout only: nothing rings, adds, caps or evicts differently.
 *
 * 📈📐 2026-11-23 (vwapzones spec §3.9, WP fe-watch) — Ajay: "can you add vwap and supply demand zone in the daily time
 * frame on the watch list please" · "Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15 accross board" ·
 * "Add vwap and supply demand too". The served frames are 1m / 5m / 15m (the tile draws them); the legend's swatches come
 * from lib ggwLegendSwatch (9 / 21 EMA, the VWAP line, the daily zones as a dashed outline — the look the chart draws),
 * each entry's served `title` is its hover, and ℹ️ prints the served `info.vwap_text` / `info.zones_text` (a phone has no
 * hover). Display only — nothing gates, sorts or rings on either. UNMEASURED.
 *
 * ▶ 2026-11-24 (spec ggrun §3.5, WP fe-run) — Ajay: "On the Watch list I need a run button to run against Gajjalas rules
 * of a stock to see for patterns of 5 patterns he has especially reversal squeeze.. so can check for patterns mid day
 * when I can add a small slide in in the chart window for giving verbatim of passed rules and failed rules of that stock
 * like you do in other tabs..". ONE hook (GgwRunRules.useGgwRun) next to the 🚫 one; every tile and the ⤢ view get the
 * "▶ Rules" button and its slide-in panel through the Tile's `run` prop. A tap is ONE POST and NO board re-GET; the
 * panel prints the served words verbatim. Display only — rings nothing, records nothing. UNMEASURED.
 *
 * ✅ 2026-11-24 (spec watch_all_rules §3.6, WP fe-watch) — Ajay: "Anytime stocks qualify all his rules should be auto
 * added to the Watch list so I can keep tracking them later". The server serves a LAST section (✅ All rules met) marked
 * `folded_default`: on the PHONE it is one folded header line under his intraday names until he taps it (his opens are
 * remembered in `ggw.opened`; every other section keeps `ggw.collapsed`); a push link / pager tap / ?focus= / ➕ into it
 * opens it first. The live interest posts ✅ rows LAST and, on the phone, none while ✅ is folded (his names always
 * live). A served `rules.state "unreadable"` prints its served line once, outside ℹ️. Desktop unchanged (no headers; ✅
 * tiles follow 🤖 in served order). A ✅ row is machine-added (`row.auto`, why "rules") — it never joins his pick.
 * Display only — nothing rings, adds, caps or evicts differently. UNMEASURED.
 *
 * ▦ 2026-11-25 (spec ggwcols §3.3) — Ajay: "When I say 2 per screen I mean 2 columns do not remove other, I need other to
 * be avtive while I scroll." · "Can you fix that instead of removing the other?". On a desktop the per-screen pick is the
 * GRID SHAPE only (columns + the fitted row height): nothing on this board is paged any more — every watched tile is in
 * ONE grid the window scrolls, every ticker chip is lit, a chip tap flips that ONE name (the tap that lights the last one
 * clears the filter), ◀ ▶ are greyed and there is no page count; `page` left the state and the link. ← → scroll one
 * screen row group under the pinned tab strip (lib ggwScroll, read at key time); a scroll hold (useGgwHold) keeps the tile
 * he is looking at where it is when the list or the row height changes; the live RENDER gate is "in or near the window"
 * (useGgwNear, fail-open, off behind ⤢). The data path, the GET and the live interest are untouched.
 *
 * 📅 2026-11-26 (spec watchrun §3.5, WP fe-roster) — Ajay: "Ok then add them to our watch list and track them please.. I
 * know he tracks them for two weeks sometimes.. before he discards them.. Can you do that please" · "Make it 30% please
 * after A+". When the server serves `runners`, GgwRunRoster draws the light 📅 roster UNDER the tiles. It gets ONLY
 * `onChanged` (the served text → the head message, then ONE full re-GET — the useGgwBrokerMark precedent); its × is its
 * own hook on its own route. write('DELETE') below is not edited and is never handed to it [C4]. No `runners` key → this
 * board is byte-equal to before.
 *
 * 👀 2026-11-27 (spec watch5m rev 2 §3.7, WP board) — Ajay: "This is how I want our watch list to be designed.. So I can
 * look at 5 mins charts like 6 in one go..." · "Also on the expanded view I need 5 mins by default to look in detail and
 * not sure what the line on volume is its blocking my story.." · "Give me a drop down or multi select like button to
 * toggle 1 mins and 15 mins 5 mins by default..". ONE hook (useGgwFrames) holds the board's frames, the ⤢ frames, the
 * average-volume opt-in and the dense pick (per browser, lib/ggwFrames). The head carries the frames menu (GgwFramesMenu,
 * phone too); with exactly ONE frame on (ggwDenseMode) every tile is one chart and the per-screen pick is 6 · 9 · 12 · 16
 * · 20 — a pick this window cannot show whole at both floors is greyed (ggwDenseOffered over useGgwGridBox), never
 * removed. Two or three frames on → the tile and the 1 · 2 · 4 · 9 pick above, unchanged. ⤢ has its OWN menu and choice.
 * NOT edited: the live fold (ggwFrameMetas over every served frame — a tick never restarts a candle, spec C1) and the
 * link write (`per` keeps meaning the 3-frame layout; the dense pick never reaches the link, spec C2). Display only.
 * docs/gajjala/watch_5m_grid_2026_11_27.md. */
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import {
  GGW_FETCH_FAILED, GGW_FOCUS_PARAM, ggwLegendSwatch, ggwRowLive, GGW_LAYOUTS, GGW_PATH,
  ggwLiveSymbols, ggwMergeRows, ggwPendingSymbols, ggwRowsPath,
  readGgwSeen, saveGgwSeen, ggwPickGrid,
  ggwDropFromPick, ggwFreshNames, ggwJoinPick, ggwPendingPlan, ggwPrunePick, ggwLivePick, ggwAddedMs, ggwRowsKey, ggwUnseenOwn, ggwWithout,
  readGgwPickAt, saveGgwPickAt, ggwSymbolPath, ggwToggleShown, GGW_URL, ggwViewParams, parseGgwLayout,
  parseGgwPick, readGgwPick, saveGgwPick, parseGgw, readGgwLayout, saveGgwLayout,
  GGW_SECTION_GLYPH, ggwGroupStarts, ggwRevealGroup, ggwSectionsOn, readGgwCollapsed,
  saveGgwCollapsed,
  ggwFoldedKeys, ggwLiveSkip, ggwRevealOpened, ggwRulesWarn, ggwToggleFold, readGgwOpened, saveGgwOpened,
  type GgwBoard, type GgwLayout, type GgwPayload, type GgwRow, type GgwWriteAnswer,
} from '../lib/gajjalaWatch';
import { ggwApplyBatch, ggwFrameMetas, type GgwFrameMeta, type GgwLiveMap, type GgwLiveSym } from '../lib/ggwLive';
import { useGgwLive, type GgwBatch } from '../hooks/useGgwLive';
/* 👀 2026-11-27 (spec watch5m §3.7): the frames choice, the dense pick and the average-volume opt-in. */
import {
  GGW_DENSE_ORDER, GGW_FRAMES_WORDS, ggwDenseMaxCols, ggwDenseMaxRows, ggwDenseMode, ggwDenseOffered, ggwDenseShown,
  ggwFrameOptions, ggwFramesOn, type GgwDense,
} from '../lib/ggwFrames';
import { useGgwFrames, useGgwGridBox } from '../hooks/useGgwFrames';
import { GgwFramesMenu } from './GgwFramesMenu';
/* ▦ 2026-11-25 (spec ggwcols §3.1 / §3.2): the near-window live gate, the scroll hold and the ← → row-group step. */
import { useGgwHold, useGgwNear } from '../hooks/useGgwScroll';
import { ggwStepNow } from '../lib/ggwScroll';
import { ggwReturnRefetch } from '../lib/ggwReturn';
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
import { GgwRunButton, GgwRunPanel, useGgwRun } from './GgwRunRules';   // ▶ 2026-11-24 (spec ggrun)
import GgwRunRoster from './GgwRunRoster';   // 📅 2026-11-26 (spec watchrun)
import '../styles/gajjalaWatch.css';

type Load = { phase: 'loading' } | { phase: 'failed' } | { phase: 'loaded'; p: GgwPayload };
const NO_SYMBOLS: string[] = [];
const NO_SKIP: ReadonlySet<string> = new Set<string>();
/** ▦ 2026-11-25: the greyed ◀ ▶ (nothing on this board pages any more). */
const NOOP = () => {};
/** ▦ 2026-11-25 (refix): the ONE all-on rule — a pick that covers every listed name hides nothing now but would hide
 * every name served later (ggwJoinable) → no filter (null). A pick missing any listed name is kept as it is. Used by
 * the chip toggle, the load's join pass and the box-add join. */
const ggwCoverAll = (pick: string[] | null, list: ReadonlyArray<string>): string[] | null =>
  pick && list.length > 0 && list.every((s) => pick.includes(s)) ? null : pick;

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
  /* 👀 2026-11-27: the board's frames, the ⤢ frames, the average line and the dense pick (this browser, never the link). */
  const fx = useGgwFrames();
  const pendingFocus = useRef<string | null>(null);
  /** 2026-11-16 — the names HE toggled on (null = no filter: every name shown). */
  const [pick, setPick] = useState<string[] | null>(() => (params.has(GGW_URL.show)
    ? parseGgwPick(params.get(GGW_URL.show)) : (params.has(GGW_URL.per) ? null : readGgwPick())));
  /* 🔗 every change writes the link (replace — no history step per tap) and this browser. */
  useEffect(() => {
    saveGgwPick(pick);
    /* ▦ 2026-11-25: no page any more — an incoming `page=` (any value, junk included) is dropped by the first write. */
    setParams((prev) => ggwViewParams(prev, { layout, pick, page: 0 }), { replace: true });
  }, [layout, pick, setParams]);
  /* ▦ 2026-11-25 — ⤢ close lands on the stock last viewed (the page used to do this): a step inside ⤢ to another name
   * → that tile is scrolled to once on close (desktop only); open + close without stepping moves nothing. Stable identity
   * (GgwStretch re-binds its key listener on a new one). */
  const stretchFrom = useRef<string | null>(null);
  const stretchedRef = useRef<string | null>(null);
  stretchedRef.current = stretched;
  const openStretch = (s: string) => { stretchFrom.current = s; setStretched(s); };
  const closeStretch = useCallback(() => {
    const s = stretchedRef.current;
    /* only a SHOWN tile: ▶ walks every row, a chip-hidden one too — a focus on it would never clear (the scroll effect
     * waits for a shown tile), firing a stray scroll later and blocking the hold */
    const el = s && typeof document !== 'undefined' ? document.getElementById(`ggw-${s}`) : null;
    if (!phone && s && s !== stretchFrom.current && el && !el.hidden) pendingFocus.current = s;
    setStretched(null);
  }, [phone]);
  const boardRef = useRef<HTMLDivElement>(null);
  /* 🆕 2026-11-19: HIS view actions stamp `ggw.pickAt` — never a mount, an activation pass, a box add or ?focus=. */
  const markView = () => saveGgwPickAt(Date.now());
  const setLayout = (l: GgwLayout) => {
    markView();
    setPick(null);
    setLayoutState(l);
    saveGgwLayout(l);
  };

  const alive = useRef(true);
  const board = useRef<GgwBoard | null>(null);
  const mainTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendSince = useRef<Map<string, number>>(new Map());
  const focusDone = useRef(false);
  const loadAllRef = useRef<() => void>(() => {});
  /* 🆕 2026-11-19 — load sequencing, the optimistic ×, the write queue, the box add, the first load. */
  const [late, setLate] = useState<Set<string>>(() => new Set());
  const loadSeq = useRef(0);
  const fullAt = useRef(0);
  const applied = useRef(0);
  const removing = useRef<Map<string, number | null>>(new Map());
  const writeQ = useRef<Promise<void>>(Promise.resolve());
  const writesLeft = useRef(0);
  const justAdded = useRef<{ sym: string; at: number } | null>(null);
  const firstOk = useRef(true);
  const gridRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<HTMLDivElement>(null);
  /* The pick (his toggled names still on the list) and its grid; no pick → the layout's own grid. */
  const rowsNow = load.phase === 'loaded' && load.p.state === 'ok' ? load.p.rows : null;
  const listNow = rowsNow ? rowsNow.map((r) => r.symbol) : [];
  /* 👀 2026-11-27: the served frames (first row with frames, served labels) and THE dense rule (one frame on). */
  const opts = ggwFrameOptions(rowsNow ?? []);
  const served = opts.map((o) => o.tf);
  const dense = ggwDenseMode(served, fx.board);
  /* 🗂 2026-11-22 — org mode (served sections) and the PHONE's folded sections (served keys, remembered here). */
  const orgNow = load.phase === 'loaded' && load.p.state === 'ok' && ggwSectionsOn(load.p);
  const [collapsed, setCollapsed] = useState<ReadonlyArray<string>>(() => readGgwCollapsed());
  useEffect(() => { saveGgwCollapsed(collapsed); }, [collapsed]);
  /* ✅ 2026-11-24 (spec watch_all_rules §3.6): the served DEFAULT-FOLDED sections (✅ All rules met) he opened here,
   * remembered in `ggw.opened`; the folded set = collapsed ∪ (default-folded − opened). Phone + org mode only. */
  const [opened, setOpened] = useState<ReadonlyArray<string>>(() => readGgwOpened());
  useEffect(() => { saveGgwOpened(opened); }, [opened]);
  const sectionsNow = load.phase === 'loaded' && load.p.state === 'ok' ? load.p.sections ?? null : null;
  const foldOn = useRef(false);
  foldOn.current = orgNow && phone;
  /* [C5] a focus / box add / first-load outline / pager tap into a FOLDED phone section opens it first (the scroll waits
   * for the tile to be shown — the effect below checks `hidden`). Off the phone or outside org mode: nothing. ✅ a
   * default-folded section opens through `opened` (ggwRevealOpened) — both run, each a no-op when it does not apply. */
  const reveal = (rows: ReadonlyArray<GgwRow>, sym: string) => {
    if (!foldOn.current) return;
    setCollapsed((c) => ggwRevealGroup(c, rows, sym));
    setOpened((o) => ggwRevealOpened(o, sectionsNow, rows, sym));
  };
  /* 🆕 2026-11-19: a name of his (or a 🎯 A+) new to this view joins the pick (first) — never left inactive. Keyed on
   * symbol + add time + the join bit, so a 🤖 potential turning 🎯 A+ in place joins at THAT load. */
  const rowsKey = rowsNow ? ggwRowsKey(rowsNow) : '';
  useEffect(() => {
    if (!rowsKey || !rowsNow || !rowsNow.length) return;
    const list = rowsNow.map((r) => r.symbol);
    const seen = readGgwSeen();
    const fresh = ggwFreshNames(rowsNow, { seen, pickAt: readGgwPickAt(), nowMs: Date.now() });
    /* 🐛 2026-11-22 (WETO): a pick only ever holds listed names (or one a × is still hiding) — a dead pick turns into NO
     * pick (every name shown) at the load where it died, so a name served again joins ONLY by the fresh rule above. */
    const keep = [...list, ...Array.from(removing.current.keys())];
    /* review residual: a pick whose ONLY listed names were added AFTER this browser last set the view (`ggw.pickAt`) —
     * a card ➕ / another device re-adding a name of a dead pick before this browser reopened the Watch — cannot be his
     * pick of them → no pick (every name shown). No pickAt on this browser (a shared show= link, a cold browser) → the
     * pick is honoured. */
    const pickAtMs = readGgwPickAt();
    const after = pickAtMs == null ? [] : rowsNow
      .filter((r) => { const t = ggwAddedMs(r); return t != null && t > pickAtMs; }).map((r) => r.symbol);
    setPick((cur) => {
      /* ▦ 2026-11-25: the all-on rule (ggwCoverAll) — a pick that covers every listed name (a machine name it was hiding
       * left the list) hides nothing now but would hide the next one served → no filter. */
      const next = ggwCoverAll(ggwJoinPick(ggwLivePick(ggwPrunePick(cur, keep), after), list, fresh), list);
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
      }
    }
    /* a name hidden by × is still "seen", so a failed DELETE never re-joins it */
    saveGgwSeen([...list, ...Array.from(removing.current.keys()).filter((x) => !list.includes(x))]);
  }, [rowsKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const picked = pick ? pick.filter((s) => listNow.includes(s)) : [];
  const usePick = picked.length > 0;
  /* 👀 2026-11-27 [C3, C6]: one frame on → the dense grid that shows EXACTLY the lit pick under both floors (the grid's
   * width and free height, measured on a desktop only); else the layout's own grid, as before. */
  const box = useGgwGridBox(gridRef, headRef, !phone && dense, load);
  const maxCols = box ? ggwDenseMaxCols(box.width, box.colGap) : null;
  const maxRows = box ? ggwDenseMaxRows(box.free, box.rowGap) : null;
  const dg = ggwDenseShown(fx.dense, maxCols, maxRows);
  const base = dense ? dg : GGW_LAYOUTS[layout];
  const grid = usePick ? ggwPickGrid(picked.length, base.cols, base.rows) : base;
  /* ▦ 2026-11-25: one screen row group = the grid's columns × its fitted rows (read by ← → at key time). */
  const perRef = useRef(1);
  perRef.current = grid.cols * grid.rows;
  const rowH = useGgwFitRows(gridRef, headRef, phone, load, grid.rows);
  const fit = rowH != null;

  /* the live tail: forming bars per (symbol, frame), folded from the raw batches against the metas of the rows that
   * may carry live bars (ggwRowLive — ok and today's; a failed minute read keeps the tail since 2026-11-23). Owner + in window only: a non-owner never reaches an ok
   * board, and out of window refresh_sec is 0. */
  const [live, setLive] = useState<GgwLiveMap>({});
  const metas = useMemo<Record<string, GgwFrameMeta[]>>(
    () => (load.phase === 'loaded' && load.p.state === 'ok' ? ggwFrameMetas(load.p.rows) : {}), [load]);
  const metasRef = useRef(metas);
  metasRef.current = metas;
  const onBatch = useCallback((evt: GgwBatch) => setLive((prev) => ggwApplyBatch(prev, evt, metasRef.current)), []);
  const liveOn = load.phase === 'loaded' && load.p.state === 'ok' && load.p.rows.length > 0 && load.p.refresh_sec > 0;
  /* 🤖 2026-11-17: every row (his, then the auto names) — not `symbols` (his names only). ✅ 2026-11-24 [C4]: ✅ rows
   * last; on the phone a default-folded section still folded posts nothing (his names are never skipped). */
  const liveSkip = foldOn.current ? ggwLiveSkip(sectionsNow, collapsed, opened) : NO_SKIP;
  const { word: feedWord } = useGgwLive(load.phase === 'loaded' && load.p.state === 'ok' ? ggwLiveSymbols(load.p, liveSkip) : NO_SYMBOLS,
    liveOn, onBatch);
  const liveOf = (r: GgwRow, shown: boolean): GgwLiveSym | undefined => (shown && ggwRowLive(r) ? live[r.symbol] : undefined);
  /* ▦ 2026-11-25 — the RENDER gate is "in or near the window" on a desktop (one IntersectionObserver, fail-open: no
   * observer → every shown tile is live); while ⤢ is open no board tile redraws. The data fold above is untouched. */
  const listKey = listNow.join(',');
  const near = useGgwNear(gridRef, listKey, !phone && listNow.length > 0);
  const isNear = (sym: string) => !stretched && (near == null || near.has(sym));
  /* ▦ the scroll hold: the tile he is looking at stays put across a commit that changes the list, the row height, the
   * grid, the filter or a head line; skipped while a focus / box add / first-load outline / ⤢ close is moving the view.
   * Never `live`, `near` or `outlined` in these deps (no rect read on the per-second path). A box add is skipped from
   * its answer on (`justAdded`): its focus is only set by an effect AFTER the commit that lands the name. */
  useGgwHold(gridRef, !phone && listNow.length > 0,
    [load, rowH, grid.cols, grid.rows, pick, msg, feedWord, refreshFailed, servedErr],
    () => pendingFocus.current != null || justAdded.current != null);

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
    fullAt.current = Date.now();
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
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const onVisible = () => {
      if (!alive.current) return;
      const b = board.current;
      if (!ggwReturnRefetch({ hidden: document.hidden, refreshSec: b ? b.refresh_sec : 0,
        lastIssuedMs: fullAt.current, nowMs: Date.now() })) return;
      clearMain();
      loadAllRef.current();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* ?focus=SYM (a push deep link): scroll that tile into view and outline it, once. */
  useEffect(() => {
    if (focusDone.current || !focus || load.phase !== 'loaded' || load.p.state !== 'ok') return;
    const at = load.p.rows.findIndex((r) => r.symbol === focus);
    if (at < 0) return;
    focusDone.current = true;
    setPick(null);
    setOutlined(focus);
    reveal(load.p.rows, focus);
    pendingFocus.current = focus;
  }, [focus, load]); // eslint-disable-line react-hooks/exhaustive-deps
  /* 🆕 2026-11-19 — a name HE added from the box (added / already / replaced): joined to his pick (forced — the clocks may
   * differ; with no pick it is already shown); outlined and scrolled to once. ▦ 2026-11-25: a join that makes the pick
   * cover every listed name clears it (ggwCoverAll — no filter, every tile shown); a pick still missing a name is kept. */
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
    if (pick && pick.some((x) => list.includes(x))) setPick((cur) => ggwCoverAll(ggwJoinPick(cur, list, [s]), list));
    setOutlined(s);
    reveal(rows, s);
    pendingFocus.current = s;
    justAdded.current = null;
  }, [load]); // eslint-disable-line react-hooks/exhaustive-deps
  /* Review fix: the scroll waits until the focused tile is SHOWN — a tile hidden by a filter or a folded phone section has
   * no box (scrollIntoView is a no-op) in the commit that asks for it. */
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

  /* 🏷️ 2026-11-18 — ONE room read for the names CARDED on today's 🚩 board (their served tags block says so); never for an
   * off-board name (no on-demand zone build for a name no Gajjala board asked about — HIS CALL #3). Empty list → no
   * request. Unconditional — hooks order. */
  const tagsOf = useGgwTags(rowsNow);
  /* ▦ 2026-11-25 — ← → scroll one screen row group under the pinned tab strip, read at key time (no state, no scroll
   * listener). Never while typing in the add box, never under the full-screen view, never on a phone. A key only
   * scrolls: it never clears a chip filter, never stamps `ggw.pickAt`, never writes the link (HIS CALL #7). */
  useEffect(() => {
    if (stretched || phone) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      const to = ggwStepNow(gridRef.current, perRef.current, e.key === 'ArrowLeft' ? -1 : 1);
      if (to == null) return;
      (to === 'top' ? boardRef.current : to)?.scrollIntoView?.({ block: 'start', behavior: 'smooth' });
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [stretched, phone]);
  /* In the full-screen view ◀ ▶ / ← → step through HIS list one stock at a time (wrapping); closing it scrolls the board
   * to the stock last viewed (closeStretch). */
  const stepStretch = useCallback((d: -1 | 1) => {
    if (!rowsNow || rowsNow.length < 2) return;
    const i = rowsNow.findIndex((r) => r.symbol === stretched);
    const j = ((i < 0 ? 0 : i) + d + rowsNow.length) % rowsNow.length;
    markView();
    setStretched(rowsNow[j].symbol);
  }, [rowsNow, stretched]);

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
  /* ▶ 2026-11-24 (spec ggrun): run Gajjala's rules on one name — ONE POST per tap, never the board's load chain. */
  const runRules = useGgwRun();
  /* 📅 2026-11-26 (spec watchrun [C4]): the roster's × answered → its served text, then ONE full re-GET. */
  const onRunnersChanged = useCallback((text: string | null) => {
    if (!alive.current) return;
    setMsg(text);
    loadAllRef.current();
  }, []);

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
  /* 👀 2026-11-27: ⤢ has its OWN frames choice and menu (the row's own served frames); state lives here, so ◀ ▶ keep it. */
  const sOpts = stretchRow ? ggwFrameOptions([stretchRow]) : [];
  const stretchServed = sOpts.map((o) => o.tf);
  const stretchMenu = stretchRow ? (
    <GgwFramesMenu options={sOpts} on={fx.stretch} onToggle={(tf) => fx.toggleStretch(stretchServed, tf)}
                   volAvg={fx.volAvg} onVolAvg={fx.toggleVolAvg} testid="ggw-sframes"
                   title={GGW_FRAMES_WORDS.stretchTitle} />
  ) : null;
  /* ▦ 2026-11-25: no pages — with no filter every name is shown (the phone's rule, now the only one). */
  const onPage = (i: number) => !usePick || picked.includes(p.rows[i].symbol);
  /* 2026-11-16 — a ticker button toggles that name; the names on screen now are the base. */
  /* 🆕 past the pending cap a pending tile prints the served "still reading" words */
  const lateRow = (r: GgwRow): GgwRow => (late.has(r.symbol) && r.late_text ? { ...r, text: r.late_text } : r);
  /* 🗂 2026-11-22 — org mode: served sections only (no key list here). Phone headers + folds; desktop none. */
  const org = ggwSectionsOn(p);
  const starts = org ? ggwGroupStarts(p.rows, p.sections) : [];
  const headAt = org && phone ? new Map(starts.map((g) => [g.at, g.section] as const)) : null;
  const foldedKeys = org && phone ? ggwFoldedKeys(p.sections, collapsed, opened) : [];
  const folded = (r: GgwRow): boolean => org && phone && !!r.org?.group && foldedKeys.includes(r.org.group);
  const toggleSection = (key: string) => {
    const next = ggwToggleFold(p.sections, { collapsed, opened }, key);
    setCollapsed(next.collapsed);
    setOpened(next.opened);
  };
  /* ✅ the one all-rules fault line (served words, state "unreadable" only) — OUTSIDE ℹ️ */
  const rulesWarn = ggwRulesWarn(p);
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
    /* ▦ 2026-11-25: the tap that lights the LAST unlit chip clears the filter (ggwCoverAll) — a pick listing every name
     * hides nothing now but would hide every machine name added later (ggwJoinable). */
    setPick(ggwCoverAll(ggwToggleShown(list, list.filter((_s, i) => onPage(i)), sym), list));
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
  const runOf = (r: GgwRow) => {
    const s = runRules.stateOf(r.symbol);
    return {
      button: <GgwRunButton sym={r.symbol} state={s} onRun={runRules.run} />,
      panel: <GgwRunPanel sym={r.symbol} state={s} onClose={runRules.close} />,
      open: s != null,
    };
  };
  const tileOf = (r: GgwRow, i: number) => (
    <Tile key={r.symbol} row={lateRow(r)} phone={phone} fit={fit} removeLabel={p.remove_label} busy={false}
          focused={outlined === r.symbol} onRemove={(s) => write('DELETE', s)} onStretch={openStretch}
          offPage={!shown(r, i)} live={liveOf(r, shown(r, i) && isNear(r.symbol))} siNote tags={tagsOf(r)} compact={org}
          actions={<GgwBrokerButton row={r} block={p.broker ?? null} busy={busy || mark.busy} onMark={mark.mark} />}
          run={runOf(r)} frames={fx.board} one={dense} volAvg={fx.volAvg} />
  );
  /* 👀 2026-11-27: the dense picks this window can show whole (the rest are greyed, never removed — §6.14). */
  const offered = ggwDenseOffered(maxCols, maxRows);
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
        {rulesWarn ? <span className="ggw-line ggw-warn" data-testid="ggw-rules-unreadable">{rulesWarn}</span> : null}
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
        {/* 👀 2026-11-27: the frames menu (phone too); a tick never re-GETs, never POSTs, never writes the link. */}
        {p.rows.length ? (
          <GgwFramesMenu options={opts} on={fx.board} onToggle={(tf) => fx.toggleBoard(served, tf)}
                         volAvg={fx.volAvg} onVolAvg={fx.toggleVolAvg} testid="ggw-frames"
                         title={GGW_FRAMES_WORDS.boardTitle} />
        ) : null}
        {p.rows.length && !phone ? (dense ? (
          <GgwLayoutPick<GgwDense> layout={dg.pick} options={GGW_DENSE_ORDER}
                                   disabled={GGW_DENSE_ORDER.filter((d) => !offered.includes(d))}
                                   disabledTitle={GGW_FRAMES_WORDS.tooSmall}
                                   onPick={(d) => { markView(); setPick(null); fx.setDense(d); }} />
        ) : (
          <GgwLayoutPick layout={layout} onPick={setLayout} />
        )) : null}
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
        <GgwPager rows={p.rows} onPage={onPage} paged={false} cur={0} pages={1} usePick={usePick} busy={false}
                  removeLabel={p.remove_label} onToggle={toggle} onPrev={NOOP}
                  onNext={NOOP} onRemove={(s) => write('DELETE', s)}
                  groups={org ? starts : undefined} />
      ) : null}
      {p.rows.length ? (
        <div className={`ggw-grid ggw-grid--cols${grid.cols}${fit ? ' ggw-grid--fit' : ''}${phone ? '' : ' ggw-grid--all'}`}
             ref={gridRef} data-layout={dense ? (dg.pick ?? 'fit') : layout} data-pick={usePick ? picked.length : undefined}
             data-frames={ggwFramesOn(served, fx.board).join(',')}
             style={fit ? ({ '--ggw-row-h': `${rowH}px` } as CSSProperties) : undefined}>
          {p.rows.map((r, i) => {
            const sec = headAt ? headAt.get(i) ?? null : null;
            if (!sec) return tileOf(r, i);
            const isFolded = foldedKeys.includes(sec.key);
            return [
              <h3 key={`sec-${sec.key}`} className={`ggw-section${isFolded ? ' ggw-section--folded' : ''}`}
                  data-testid={`ggw-section-${sec.key}`}>
                <button type="button" className="ggw-section-btn" aria-expanded={!isFolded} title={sec.hint ?? undefined}
                        data-testid={`ggw-section-btn-${sec.key}`}
                        onClick={() => toggleSection(sec.key)}>
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
      {p.runners ? <GgwRunRoster block={p.runners} phone={phone} onChanged={onRunnersChanged} /> : null}
      {stretchRow ? (
        <GgwStretch row={lateRow(stretchRow)} phone={phone} removeLabel={p.remove_label} onClose={closeStretch}
                 onStep={p.rows.length > 1 ? stepStretch : null} live={liveOf(stretchRow, true)} siNote tags={tagsOf(stretchRow)}
                 compact={org} run={runOf(stretchRow)}
                 frames={fx.stretch} volAvg={fx.volAvg} framesMenu={stretchMenu} />
      ) : null}
    </div>
  );
}
