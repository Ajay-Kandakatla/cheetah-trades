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
  2: { cols: 2, rows: 1 },
  4: { cols: 2, rows: 2 },
  9: { cols: 3, rows: GGW_FIT_ROWS },
} as const;
export type GgwLayout = keyof typeof GGW_LAYOUTS;
export const GGW_LAYOUT_ORDER: ReadonlyArray<GgwLayout> = [2, 4, 9];
export const GGW_LAYOUT_DEFAULT: GgwLayout = 2;
/** This browser's last pick (a per-viewer convenience; a missing / blocked / junk value → the default). */
export const GGW_LAYOUT_KEY = 'ggw.layout';
export function parseGgwLayout(v: unknown): GgwLayout {
  const n = typeof v === 'string' && /^\d+$/.test(v.trim()) ? Number(v.trim()) : v;
  return n === 2 || n === 4 || n === 9 ? n : GGW_LAYOUT_DEFAULT;
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
/** ◀ ▶ — the pager's glyphs (structural). */
export const GGW_PAGER = { prev: '◀', next: '▶', prevTitle: 'Previous (←)', nextTitle: 'Next (→)' } as const;

/** ⤢ / ⤡ — the stretch control's glyphs and titles (structural, no word about a stock). */
export const GGW_STRETCH = { open: '⤢', close: '⤡', closeTitle: 'Back to the board (Esc)' } as const;
export function ggwStretchTitle(sym: string): string { return `Stretch ${sym} to full screen`; }
/** The viewBox height that makes a `viewW`-wide chart exactly fill a w × h CSS box (no distortion, no overflow);
 *  null when the box has no size yet (then the GGW_CHART_H height is used). */
export function ggwFitViewBoxH(w: number, h: number, viewW: number): number | null {
  if (!(w > 0) || !(h > 0) || !(viewW > 0)) return null;
  return Math.max(1, Math.floor((viewW * h) / w));
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
export type GgwFrame = {
  tf: string; label: string; tile: CmTile; axis: CmAxis | null;
  ema_cross: GgwCross | null; uptrend: GgwUptrend | null; held: GgwHeld | null;
  run_bases: GgwRunBases | null;
  /** 🔀 2026-11-15 (SPEC blinker §3.5): the served 9/21 EMA cross blinker of THIS frame (frame-level sibling of
   *  `ema_cross`, read off the stored curves) — the figcaption prints its dot; the chart box carries none. */
  ema_blink: CmEmaBlink | null;
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

function parseAxis(v: unknown): CmAxis | null {
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
  return { slots, x: v.x.slice(), shade, ticks };
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

function parseFrame(v: unknown, symbol: string): GgwFrame | null {
  if (!isObj(v) || !str(v.tf)) return null;
  const tile = parseTile(v.tile, symbol);
  if (!tile) return null;
  const up = isObj(v.uptrend) && typeof v.uptrend.short === 'string'
    ? { ok: typeof v.uptrend.ok === 'boolean' ? v.uptrend.ok : null, short: v.uptrend.short } : null;
  const held = isObj(v.held) && str(v.held.text) ? { text: v.held.text as string } : null;
  return {
    tf: v.tf, label: typeof v.label === 'string' ? v.label : v.tf, tile, axis: parseAxis(v.axis),
    ema_cross: isObj(v.ema_cross) ? v.ema_cross : null, uptrend: up, held,
    /* 📶 lib/gajjala's ONE reader of a served card block (trimmed text + title; blank / junk → null). The served
     * `ellipses` beside it are NOT drawn here: PatternChart's ellipse layer maps by bar index, not by the served
     * 04:00 axis this board draws on (spec ggbase WP-E — main session's call). */
    run_bases: isObj(v.run_bases) ? ggRunBasesLine(v.run_bases) : null,
    ema_blink: isObj(v.ema_blink) ? (v.ema_blink as CmEmaBlink) : null,
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
 *  1"): 5-min, 3-min, 1-min, each full width and the same height; a frame not named here follows in served order. */
export const GGW_STRETCH_ORDER = ['5m', '3m', '1m'] as const;
export function ggwStretchFrames(frames: ReadonlyArray<GgwFrame>): GgwFrame[] {
  const rank = (f: GgwFrame) => {
    const i = (GGW_STRETCH_ORDER as ReadonlyArray<string>).indexOf(f.tf);
    return i < 0 ? GGW_STRETCH_ORDER.length : i;
  };
  return frames.map((f, i) => ({ f, i })).sort((a, b) => rank(a.f) - rank(b.f) || a.i - b.i).map((x) => x.f);
}

/** The chart height for one frame (viewBox units). */
export function ggwChartHeight(tf: string, phone: boolean): number {
  if (phone) return GGW_CHART_H_PHONE;
  return (GGW_CHART_H as Record<string, number>)[tf] ?? GGW_CHART_H['3m'];
}
