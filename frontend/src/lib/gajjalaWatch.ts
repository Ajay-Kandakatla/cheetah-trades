/* 👀 Gajjala's Watch — the Chart Maps tab's FE plumbing (2026-11-15, gajjala-watch spec §3.7 / §3.8, WP-C).
 *
 * Ajay 2026-11-15: "I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and add remove
 * tickers from the dashboard. When I add a ticker I need 1 min 3 min and 5 min charts... Not the SEPA and I need clear
 * distinction or may be a brighter and thicker 21 EMA and 9 EMA, from the videos I notice that when ever 9 EMA crosses
 * over 21 EMA on uptrend is where the bullish momentum started I need alerts on these from 1 min to I can be ready... I
 * think the cross over is slow but once it picks up its very rapid.." and "I have a 27 inch monitor I wanna fit 3x3
 * tikers on watch at any given time on this tashboard" and "Any chart I view make sure you are showing me from 4 AM for
 * historical behaviour and also the right side with gaps to see where it might go".
 *
 * The board is ONE owner-only GET (backend chart_maps/gajjala_watch/api.py → payload.build) plus the add / remove
 * routes. This module holds the routes, the payload TYPES (spec §3.7, key for key), the parser, the replay palette and
 * the chart heights. Every word and every number the board prints is SERVED — nothing here types a rule, a threshold
 * or a sentence about a stock. The ONE FE sentence is GGW_FETCH_FAILED (the request itself failed — there is no payload
 * to serve a reason). UNMEASURED: a 9 / 21 cross is information, not an entry. */
import type { CmAxis, CmEmaBlink, CmTile } from './chartMaps';
import { ggRunBasesLine } from './gajjala';

/** The tab id (== backend chart_maps/gajjala_watch/constants.TAB). */
export const GGW_TAB = 'gajjala_watch';
/** The board route (== backend constants.API_PATH — contract-pinned by the main session). */
export const GGW_PATH = '/chart-maps/gajjala-watch';
/** The add / remove route for one ticker (== backend constants.API_SYMBOL_PATH). The server normalizes the symbol. */
export function ggwSymbolPath(sym: string): string {
  return `${GGW_PATH}/symbols/${encodeURIComponent(String(sym).trim())}`;
}
/** The board route asking only for these rows (the pending poll, spec C2.4) — head keys are still served. */
/** 👀 LIVE (2026-11-16, watch-live spec §3.4): the owner-gated live-interest route (== backend constants.API_LIVE_PATH —
 *  a backend source-read test pins equality). The board POSTs its symbols here; the hub then streams their prints. */
export const GGW_LIVE_PATH = `${GGW_PATH}/live`;
/** The 9 / 21 EMA tip on the forming live bar. */
export const GGW_LIVE_EMA_TIP = true;   // HIS CALL #1 answered 2026-11-16 "live live.. per sec change" (docs/gajjala/watch_live_2026_11_16.md) — the 9/21 tip on the forming bar
export function ggwRowsPath(syms: ReadonlyArray<string>): string {
  return `${GGW_PATH}?symbols=${encodeURIComponent(syms.join(','))}`;
}
/** The one FE sentence: the GET itself failed, so nothing was served. A served `state: "error"` prints ITS reason
 *  verbatim instead (2026-11-15 fix #4) — this sentence is only for when no reason was served. */
export const GGW_FETCH_FAILED = 'Could not load the watch.';

/** The look he liked: the replay video's dark panel (eod-audits/replays/replay_gif.py:576-581 PALETTE — bg (13,17,23),
 *  grid (38,43,52), text (225,228,232), dim (135,142,152), up (38,186,104), down (235,72,72)). The 9 / 21 EMA colours
 *  are lib/chartMaps EMA_BOLD. Mirrored in styles/gajjalaWatch.css `.ggw-dark`. */
export const GGW_PANEL = {
  bg: 'rgb(13, 17, 23)',
  grid: 'rgb(38, 43, 52)',
  text: 'rgb(225, 228, 232)',
  dim: 'rgb(135, 142, 152)',
  up: 'rgb(38, 186, 104)',
  down: 'rgb(235, 72, 72)',
} as const;

/** Chart heights in viewBox units (PatternChart W = 620) — MINE, HIS CALL #10. The first arithmetic (≈ 236 px above
 *  the grid → three rows fit) was WRONG: measured 357 px above and 56 below, the fixed-height 3×3 overflowed at both
 *  2560×1440 and 1920×1080. Above the phone break these are now the starting height and the SHARE of a fitted tile
 *  (GGW_FIT_GROW); the rows are sized from the viewport (ggwFitRowHeight; docs/gajjala/watch_frontend_2026_11_15.md). */
export const GGW_CHART_H = { '1m': 120, '3m': 180, '5m': 180 } as const;
/** 👀 3 rows on one screen (2026-11-15 fix #3; Ajay: "I have a 27 inch monitor I wanna fit 3x3 tikers on watch at any
 *  given time"). Above the phone break the grid rows are sized from the viewport: row = (innerHeight − what the board
 *  holds above the grid (2026-11-16: measured from the BOARD's top, no longer the page's) − (rows − 1) row gaps) / rows,
 *  never under GGW_FIT_ROW_MIN_PX. The charts then
 *  flex to fill the row, the 1-min and the 3-/5-min pair sharing the height in the SAME proportion GGW_CHART_H gives
 *  them at any width (the pair is half the width, so its share is GGW_CHART_H['3m'] / 2). */
export const GGW_FIT_ROWS = 3;
/** The tile floor for a short desktop window — MINE (layout, not a rule): below it the page scrolls instead of the
 *  charts shrinking further. 1920×1080 measures ≈ 213 px a row, so it still fits there. HIS CALL to move. */
export const GGW_FIT_ROW_MIN_PX = 200;
/** The flex shares of the 1-min chart and the 3-/5-min pair inside a fitted tile (derived from GGW_CHART_H). */
export const GGW_FIT_GROW = { top: GGW_CHART_H['1m'], pair: GGW_CHART_H['3m'] / 2 } as const;
/** One fitted grid row in CSS px, or null when there is nothing to fit (no viewport / junk numbers). */
export function ggwFitRowHeight(m: { vh: number; top: number; below: number; gap: number },
                                rows: number = GGW_FIT_ROWS): number | null {
  const ok = [m.vh, m.top, m.below, m.gap].every((x) => typeof x === 'number' && Number.isFinite(x));
  if (!ok || m.vh <= 0) return null;
  const n = Number.isInteger(rows) && rows >= 1 ? rows : GGW_FIT_ROWS;
  const free = m.vh - Math.max(0, m.top) - Math.max(0, m.below) - (n - 1) * Math.max(0, m.gap);
  return Math.max(GGW_FIT_ROW_MIN_PX, Math.floor(free / n));
}
/** 👀 Charts per screen (2026-11-16). Ajay: "I need bigger may be 2 on each screen side by side its not clear and give
 *  me a strech button to see full chart". 2 = two tiles side by side filling one screen (his word, the default);
 *  4 = 2 × 2; 9 = 3 × 3 (his 2026-11-15 "fit 3x3 tikers"). Layout only — the 4 and 9 options are MINE, kept so the
 *  11-15 ask is one click away. `rows` feeds ggwFitRowHeight; `cols` picks the grid class. */
export const GGW_LAYOUTS = {
  1: { cols: 1, rows: 1 },                       // 2026-11-16 — Ajay: "1 at a time instead of 2 minimum"
  2: { cols: 2, rows: 1 },
  4: { cols: 2, rows: 2 },
  9: { cols: 3, rows: GGW_FIT_ROWS },
} as const;
export type GgwLayout = keyof typeof GGW_LAYOUTS;
export const GGW_LAYOUT_ORDER: ReadonlyArray<GgwLayout> = [1, 2, 4, 9];
export const GGW_LAYOUT_DEFAULT: GgwLayout = 2;
/** This browser's last pick (a per-viewer convenience; a missing / blocked / junk value → the default). */
export const GGW_LAYOUT_KEY = 'ggw.layout';
export function parseGgwLayout(v: unknown): GgwLayout {
  const n = typeof v === 'string' && /^\d+$/.test(v.trim()) ? Number(v.trim()) : v;
  return n === 1 || n === 2 || n === 4 || n === 9 ? n : GGW_LAYOUT_DEFAULT;
}
export function readGgwLayout(): GgwLayout {
  try { return parseGgwLayout(window.localStorage.getItem(GGW_LAYOUT_KEY)); } catch { return GGW_LAYOUT_DEFAULT; }
}
export function saveGgwLayout(l: GgwLayout): void {
  try { window.localStorage.setItem(GGW_LAYOUT_KEY, String(l)); } catch { /* private window: the pick lasts this visit */ }
}
/** The pick is also the page size (Ajay 2026-11-16: "two stocks with 3 charts each at any given moment instead of 6 …
 *  but I also wanna be able to move current one in the view"): the board shows that many tiles at once; ◀ ▶, the
 *  ticker buttons and the ← → keys move the view. Page of the i-th tile, and the page clamped to the list. */
export function ggwPageCount(n: number, size: number): number {
  return size > 0 && n > 0 ? Math.ceil(n / size) : 1;
}
export function ggwClampPage(page: number, n: number, size: number): number {
  const last = ggwPageCount(n, size) - 1;
  return Number.isInteger(page) ? Math.min(Math.max(0, page), last) : 0;
}
export function ggwPageOf(index: number, size: number): number {
  return size > 0 && index > 0 ? Math.floor(index / size) : 0;
}
/** 2026-11-16 — Ajay: "make These toggleable and 1 at a time instead of 2 minimum.. I wanna be able to select or remove
 *  from these give me an x option to remove as well". A ticker button TOGGLES that name in the shown set: `shown` = the
 *  names on screen now (the page, or the last pick), `sym` flips in or out, the result keeps HIS list order; an empty
 *  result → null (back to the pages). Names no longer on the list drop out. */
export function ggwToggleShown(list: ReadonlyArray<string>, shown: ReadonlyArray<string>, sym: string): string[] | null {
  const on = new Set(shown.filter((s) => list.includes(s)));
  if (on.has(sym)) on.delete(sym); else if (list.includes(sym)) on.add(sym);
  const next = list.filter((s) => on.has(s));
  return next.length ? next : null;
}
/** The grid of a pick of `n` names under a layout of `cols` columns: never more columns than names (one name fills the
 *  width), and as many fitted rows as it takes. */
export function ggwPickGrid(n: number, cols: number, maxRows?: number): { cols: number; rows: number } {
  const c = Math.max(1, Math.min(Math.max(1, n), Math.max(1, cols)));
  const need = Math.max(1, Math.ceil(Math.max(1, n) / c));
  /* 2026-11-16 fix — Ajay: "All the charts are shrinked too much". A pick never squeezes more rows onto one screen than
   * the per-screen choice holds: "1 per screen" with 4 names = 4 full-screen tiles to scroll, never 4 quarter-screens. */
  const cap = Number.isInteger(maxRows) && (maxRows as number) >= 1 ? (maxRows as number) : need;
  return { cols: c, rows: Math.min(need, cap) };
}
/** ◀ ▶ — the pager's glyphs (structural). */
export const GGW_PAGER = { prev: '◀', next: '▶', prevTitle: 'Previous (←)', nextTitle: 'Next (→)' } as const;

/** 🔗 2026-11-16 — Ajay: "Can you make the board persist please... Like the 1 selection and the stock selection too.. So I can
 *  share with someone". The view lives in the page link — `per` = the per-screen pick, `show` = his toggled names
 *  (comma list), `page` = 1-based page — and in this browser (`ggw.layout`, `ggw.pick`). A link wins over the browser; a
 *  junk value is ignored (never throws, never an empty board — a name not on the list just drops out). */
export const GGW_URL = { per: 'per', show: 'show', page: 'page' } as const;
export const GGW_PICK_KEY = 'ggw.pick';
export function parseGgwPick(v: unknown): string[] | null {
  if (typeof v !== 'string') return null;
  const out: string[] = [];
  for (const raw of v.split(',')) {
    const s = raw.trim().toUpperCase();
    if (/^[A-Z0-9][A-Z0-9.\-]{0,9}$/.test(s) && !out.includes(s)) out.push(s);
  }
  return out.length ? out : null;
}
export function parseGgwPage(v: unknown): number {
  const n = typeof v === 'string' && /^\d+$/.test(v.trim()) ? Number(v.trim()) : NaN;
  return Number.isInteger(n) && n >= 1 ? n - 1 : 0;
}
export function readGgwPick(): string[] | null {
  try { return parseGgwPick(window.localStorage.getItem(GGW_PICK_KEY)); } catch { return null; }
}
export function saveGgwPick(p: ReadonlyArray<string> | null): void {
  try {
    if (p && p.length) window.localStorage.setItem(GGW_PICK_KEY, p.join(','));
    else window.localStorage.removeItem(GGW_PICK_KEY);
  } catch { /* private window: the pick lasts this visit */ }
}
/** The view's params on top of `prev` (every other param — tab, focus — kept): per always; show only with a pick; page
 *  only past the first page and only without a pick. */
export function ggwViewParams(prev: URLSearchParams, v: { layout: number; pick: ReadonlyArray<string> | null; page: number }): URLSearchParams {
  const n = new URLSearchParams(prev);
  n.set(GGW_URL.per, String(v.layout));
  if (v.pick && v.pick.length) n.set(GGW_URL.show, v.pick.join(',')); else n.delete(GGW_URL.show);
  if (!(v.pick && v.pick.length) && v.page > 0) n.set(GGW_URL.page, String(v.page + 1)); else n.delete(GGW_URL.page);
  return n;
}

/** ⤢ / ⤡ — the stretch control's glyphs and titles (structural, no word about a stock). */
export const GGW_STRETCH = { open: '⤢', close: '⤡', closeTitle: 'Back to the board (Esc)' } as const;
export function ggwStretchTitle(sym: string): string { return `Stretch ${sym} to full screen`; }
/** The viewBox height that makes a `viewW`-wide chart exactly fill a w × h CSS box (no distortion, no overflow);
 *  null when the box has no size yet (then the GGW_CHART_H height is used). */
export function ggwFitViewBoxH(w: number, h: number, viewW: number): number | null {
  if (!(w > 0) || !(h > 0) || !(viewW > 0)) return null;
  return Math.max(1, Math.floor((viewW * h) / w));
}
/** 2026-11-16 fix — Ajay: "All the charts are shrinked too much" + "the Diamon shapes are too big". A fixed 620-unit
 *  viewBox stretched to a full-width tile blew text and diamonds up ~3×. A fitted chart's viewBox width follows its box
 *  instead: 1 unit = GGW_TEXT_SCALE px, never under the house 620 (so a narrow tile draws exactly as before). */
export const GGW_TEXT_SCALE = 1.3;
export function ggwFitViewW(w: number, base: number): number {
  if (!(w > 0) || !(base > 0)) return base;
  return Math.max(base, Math.round(w / GGW_TEXT_SCALE));
}
/** ≤ 640 px: the house default height, one column. */
export const GGW_CHART_H_PHONE = 190;
/** The phone break (one column, GGW_CHART_H_PHONE) — the same 640 px as `.ggw-grid` in gajjalaWatch.css. */
export const GGW_PHONE_MQ = '(max-width: 640px)';
/** The `?focus=SYM` param a push deep link carries. */
export const GGW_FOCUS_PARAM = 'focus';

// ── payload types (payload.build, spec §3.7) ────────────────────────────────────────────────────────────────────────

export type GgwRowState = 'ok' | 'pending' | 'no_prints' | 'no_bars' | 'failed' | 'over_budget';
export type GgwUptrend = { ok: boolean | null; short: string };
export type GgwHeld = { text: string };
export type GgwCross = Record<string, unknown>;
/** 📶 2026-11-15 (Ajay: "There is a concept of 3 bases and climax run can you bake that in to the app please" · "I need
 *  that tracked in to Gajjala's"): the served base-count line of the 5-min frame — backend build.run_bases_keys → the ONE
 *  engine's run_bases.card_block, the same line Gajjala's cards print. `text` verbatim, `title` (GG's quotes + the
 *  definition) on hover. Information only, UNMEASURED. */
export type GgwRunBases = { text: string; title: string };
/** 👀 LIVE (2026-11-16): the served axis plus the three keys the live candle buckets on — `start_epoch` = the session's
 *  04:00 ET epoch the server's slots are measured from, `frame_min` = the frame's minutes, `from_et` = "04:00". Absent
 *  on an older stored doc → null (that frame then carries no live bar; the axis itself is kept as before). */
export type GgwAxis = CmAxis & { start_epoch: number | null; frame_min: number | null; from_et: string | null };
/** 👀 LIVE: the frame's served UNROUNDED 9 / 21 EMA at its last stored bar (backend build.tile `ema_tail`) — the seed of
 *  the forming bar's tip (GGW_LIVE_EMA_TIP, HIS CALL #1). */
export type GgwEmaTail = { ema9: number; ema21: number };
export type GgwFrame = {
  tf: string; label: string; tile: CmTile; axis: GgwAxis | null;
  ema_tail: GgwEmaTail | null;
  ema_cross: GgwCross | null; uptrend: GgwUptrend | null; held: GgwHeld | null;
  run_bases: GgwRunBases | null;
  /** 🔀 2026-11-15 (SPEC blinker §3.5): the served 9/21 EMA cross blinker of THIS frame (frame-level sibling of
   *  `ema_cross`, read off the stored curves) — the figcaption prints its dot; the chart box carries none. */
  ema_blink: CmEmaBlink | null;
  /** 2026-11-16 (ggcard3 §3.2, C3) — OPTIONAL, present only when SERVED (the 🚩 card view's frames GET); absent on every
   *  Watch frame and never defaulted to a value. `empty_text` = the served words for a frame with no stored bars;
   *  `as_of_et` / `stale` = THIS frame's own source-doc stamp and the house stale verdict for that source. */
  empty_text?: string | null;
  as_of_et?: string | null;
  stale?: boolean;
};
export type GgwRang = { frame: string; at_et: string | null; text: string };
export type GgwRow = {
  symbol: string; state: GgwRowState | string; text: string | null;
  from_session: string | null; as_of_et: string | null; stale: boolean;
  frames: GgwFrame[]; rang: GgwRang[];
};
export type GgwPass = { at_et: string | null; text: string | null; stale: boolean };
export type GgwInfo = {
  honesty: string | null; push_text: string | null; uptrend_rule: string | null;
  push_mode: string | null; push_frames: string[];
};
export type GgwLegend = { tone: 'ema9' | 'ema21' | string; label: string };
export type GgwBoard = {
  state: 'ok'; title: string; session: string | null; is_today: boolean; in_window: boolean;
  refresh_sec: number; next_window_sec: number | null;
  pending_poll_sec: number | null; pending_wait_max_sec: number | null;
  max_symbols: number | null; symbols: string[]; full: boolean; full_text: string | null;
  add_label: string | null; add_placeholder: string | null; remove_label: string | null; empty_text: string | null;
  pass: GgwPass | null; info: GgwInfo | null; legend: GgwLegend[]; rows: GgwRow[];
};
export type GgwOwnerOnly = { state: 'owner_only'; reason: string | null; title: string | null };
/** The server's own failure answer (payload.error_payload): its reason is printed verbatim (served words only). */
export type GgwServedError = { state: 'error'; reason: string | null; title: string | null };
export type GgwPayload = GgwBoard | GgwOwnerOnly | GgwServedError;
/** The add / remove answer (store.add / store.remove). */
export type GgwWriteAnswer = { state: string; symbols: string[]; symbol: string | null; text: string | null };

// ── parsing (junk never reaches the board) ─────────────────────────────────────────────────────────────────────────

const isObj = (v: unknown): v is Record<string, any> => !!v && typeof v === 'object' && !Array.isArray(v);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v : null);
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const strs = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []);

const AXIS_FROM_RE = /^\d{2}:\d{2}$/;

function parseAxis(v: unknown): GgwAxis | null {
  if (!isObj(v)) return null;
  const slots = num(v.slots);
  if (slots == null || slots <= 0 || !Array.isArray(v.x) || !v.x.every((x: unknown) => num(x) != null)) return null;
  const shade = Array.isArray(v.shade)
    ? v.shade.filter((s: unknown) => isObj(s) && num(s.from_slot) != null && num(s.to_slot) != null)
      .map((s: any) => ({ from_slot: s.from_slot, to_slot: s.to_slot, kind: str(s.kind) ?? undefined }))
    : [];
  const ticks = Array.isArray(v.ticks)
    ? v.ticks.filter((t: unknown) => isObj(t) && num(t.slot) != null && typeof t.label === 'string')
      .map((t: any) => ({ slot: t.slot, label: t.label }))
    : [];
  const se = num(v.start_epoch);
  const fm = num(v.frame_min);
  return {
    slots, x: v.x.slice(), shade, ticks,
    start_epoch: se != null && se > 0 ? se : null,
    frame_min: fm != null && Number.isInteger(fm) && fm > 0 ? fm : null,
    from_et: typeof v.from_et === 'string' && AXIS_FROM_RE.test(v.from_et) ? v.from_et : null,
  };
}

function parseEmaTail(v: unknown): GgwEmaTail | null {
  if (!isObj(v)) return null;
  const e9 = num(v.ema9);
  const e21 = num(v.ema21);
  return e9 != null && e21 != null ? { ema9: e9, ema21: e21 } : null;
}

function parseTile(v: unknown, symbol: string): CmTile | null {
  if (!isObj(v) || !Array.isArray(v.bars)) return null;
  return {
    ...(v as any),
    symbol: str(v.symbol) ?? symbol,
    href: typeof v.href === 'string' ? v.href : '',
    bars: v.bars,
    bands: Array.isArray(v.bands) ? v.bands : [],
    lines: Array.isArray(v.lines) ? v.lines : [],
    markers: Array.isArray(v.markers) ? v.markers : [],
    stats: Array.isArray(v.stats) ? v.stats : [],
    why: typeof v.why === 'string' ? v.why : '',
    curves: Array.isArray(v.curves) ? v.curves : [],
  } as CmTile;
}

/** One served frame block, or null for junk (exported 2026-11-16 for lib/gajjalaCardView — body unchanged but for the
 *  three optional keys, each kept ONLY when the server sent it). */
export function parseFrame(v: unknown, symbol: string): GgwFrame | null {
  if (!isObj(v) || !str(v.tf)) return null;
  const tile = parseTile(v.tile, symbol);
  if (!tile) return null;
  const up = isObj(v.uptrend) && typeof v.uptrend.short === 'string'
    ? { ok: typeof v.uptrend.ok === 'boolean' ? v.uptrend.ok : null, short: v.uptrend.short } : null;
  const held = isObj(v.held) && str(v.held.text) ? { text: v.held.text as string } : null;
  return {
    tf: v.tf, label: typeof v.label === 'string' ? v.label : v.tf, tile, axis: parseAxis(v.axis),
    ema_tail: parseEmaTail(v.ema_tail),
    ema_cross: isObj(v.ema_cross) ? v.ema_cross : null, uptrend: up, held,
    /* 📶 lib/gajjala's ONE reader of a served card block (trimmed text + title; blank / junk → null). The served
     * `ellipses` beside it are NOT drawn here: PatternChart's ellipse layer maps by bar index, not by the served
     * 04:00 axis this board draws on (spec ggbase WP-E — main session's call). */
    run_bases: isObj(v.run_bases) ? ggRunBasesLine(v.run_bases) : null,
    ema_blink: isObj(v.ema_blink) ? (v.ema_blink as CmEmaBlink) : null,
    ...('empty_text' in v ? { empty_text: str(v.empty_text) } : {}),
    ...('as_of_et' in v ? { as_of_et: str(v.as_of_et) } : {}),
    ...('stale' in v ? { stale: v.stale === true } : {}),
  };
}

function parseRow(v: unknown): GgwRow | null {
  if (!isObj(v) || !str(v.symbol)) return null;
  const symbol = v.symbol as string;
  return {
    symbol,
    state: str(v.state) ?? 'pending',
    text: str(v.text),
    from_session: str(v.from_session),
    as_of_et: str(v.as_of_et),
    stale: v.stale === true,
    frames: (Array.isArray(v.frames) ? v.frames : []).map((f: unknown) => parseFrame(f, symbol))
      .filter((f: GgwFrame | null): f is GgwFrame => !!f),
    rang: (Array.isArray(v.rang) ? v.rang : [])
      .filter((r: unknown) => isObj(r) && str(r.text))
      .map((r: any) => ({ frame: String(r.frame ?? ''), at_et: str(r.at_et), text: r.text })),
  };
}

/** 👀 LIVE (2026-11-16) — the ONE rule for "this row may carry live bars": a served `ok` row of TODAY's session whose
 *  last server read did not fail. A stale row (its frames are the last GOOD ones) and a prior-session row carry none —
 *  they show their stored bars only. Used by ggwLive.ggwFrameMetas and the board's Tile. */
export function ggwRowLive(row: GgwRow): boolean {
  return row.state === 'ok' && row.from_session == null && !row.stale;
}

/** The served payload, or null for junk. `owner_only` / `error` → exactly {state, reason, title} (nothing else is
 *  kept; an `error` reason is the server's sentence, printed as served). */
export function parseGgw(raw: unknown): GgwPayload | null {
  if (!isObj(raw)) return null;
  if (raw.state === 'owner_only') return { state: 'owner_only', reason: str(raw.reason), title: str(raw.title) };
  if (raw.state === 'error') return { state: 'error', reason: str(raw.reason), title: str(raw.title) };
  if (raw.state !== 'ok' || !Array.isArray(raw.rows)) return null;
  const pass = isObj(raw.pass) ? { at_et: str(raw.pass.at_et), text: str(raw.pass.text), stale: raw.pass.stale === true } : null;
  const info = isObj(raw.info) ? {
    honesty: str(raw.info.honesty), push_text: str(raw.info.push_text), uptrend_rule: str(raw.info.uptrend_rule),
    push_mode: str(raw.info.push_mode), push_frames: strs(raw.info.push_frames),
  } : null;
  return {
    state: 'ok',
    title: str(raw.title) ?? '',
    session: str(raw.session),
    is_today: raw.is_today === true,
    in_window: raw.in_window === true,
    refresh_sec: Math.max(0, num(raw.refresh_sec) ?? 0),
    next_window_sec: num(raw.next_window_sec),
    pending_poll_sec: num(raw.pending_poll_sec),
    pending_wait_max_sec: num(raw.pending_wait_max_sec),
    max_symbols: num(raw.max_symbols),
    symbols: strs(raw.symbols),
    full: raw.full === true,
    full_text: str(raw.full_text),
    add_label: str(raw.add_label),
    add_placeholder: str(raw.add_placeholder),
    remove_label: str(raw.remove_label),
    empty_text: str(raw.empty_text),
    pass,
    info,
    legend: (Array.isArray(raw.legend) ? raw.legend : [])
      .filter((l: unknown) => isObj(l) && str(l.tone) && str(l.label))
      .map((l: any) => ({ tone: l.tone, label: l.label })),
    rows: raw.rows.map(parseRow).filter((r: GgwRow | null): r is GgwRow => !!r),
  };
}

/** The rows still waiting for their first read (the pending poll asks for these only). */
export function ggwPendingSymbols(b: GgwBoard): string[] {
  return b.rows.filter((r) => r.state === 'pending').map((r) => r.symbol);
}

/** A partial answer's rows merged into the board by symbol. The board keeps its own order and head (the server never
 *  reorders; a partial answer is never a reason to re-cut the list). */
export function ggwMergeRows(b: GgwBoard, partial: GgwBoard): GgwBoard {
  const by = new Map(partial.rows.map((r) => [r.symbol, r] as const));
  return { ...b, rows: b.rows.map((r) => by.get(r.symbol) ?? r) };
}

/** The 1-min frame on top, then the rest in served order (3-min, 5-min). */
export function ggwSplitFrames(frames: ReadonlyArray<GgwFrame>): { top: GgwFrame | null; pair: GgwFrame[] } {
  const top = frames.find((f) => f.tf === '1m') ?? null;
  return { top, pair: frames.filter((f) => f !== top) };
}

/** ⤢ The full-screen order, top to bottom (Ajay 2026-11-16: "I wanna see all 3 of one stock for stretch like 5, 3 and
 *  1"): 5-min, 3-min, 1-min, each full width and the same height; a frame not named here follows in served order.
 *  2026-11-16 (ggcard3): `order` = another surface's order (the 🚩 card view's lib/gajjalaCardView.GGC_STRETCH_ORDER);
 *  absent → this Watch order, unchanged. */
export const GGW_STRETCH_ORDER = ['5m', '3m', '1m'] as const;
export function ggwStretchFrames(frames: ReadonlyArray<GgwFrame>,
                                 order: ReadonlyArray<string> = GGW_STRETCH_ORDER): GgwFrame[] {
  const rank = (f: GgwFrame) => {
    const i = order.indexOf(f.tf);
    return i < 0 ? order.length : i;
  };
  return frames.map((f, i) => ({ f, i })).sort((a, b) => rank(a.f) - rank(b.f) || a.i - b.i).map((x) => x.f);
}

/** The chart height for one frame (viewBox units). */
export function ggwChartHeight(tf: string, phone: boolean): number {
  if (phone) return GGW_CHART_H_PHONE;
  return (GGW_CHART_H as Record<string, number>)[tf] ?? GGW_CHART_H['3m'];
}
