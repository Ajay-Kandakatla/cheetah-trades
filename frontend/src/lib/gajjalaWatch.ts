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
import type { CmAxis, CmTile } from './chartMaps';

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
/** The one FE sentence: the GET itself failed, so nothing was served. */
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

/** Chart heights in viewBox units (PatternChart W = 620) — MINE, HIS CALL #10. At 2560×1440 the tile is ≈ 812 px wide:
 *  1-min 812 × 120 / 620 ≈ 157 px, 3-min / 5-min ≈ 402 × 180 / 620 ≈ 117 px → a tile ≈ 353 px, three rows fit
 *  (spec §3.8 arithmetic; docs/gajjala/watch_frontend_2026_11_15.md). */
export const GGW_CHART_H = { '1m': 120, '3m': 180, '5m': 180 } as const;
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
export type GgwFrame = {
  tf: string; label: string; tile: CmTile; axis: CmAxis | null;
  ema_cross: GgwCross | null; uptrend: GgwUptrend | null; held: GgwHeld | null;
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
export type GgwPayload = GgwBoard | GgwOwnerOnly;
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

/** The served payload, or null for junk. `owner_only` → exactly {state, reason, title} (nothing else is kept). */
export function parseGgw(raw: unknown): GgwPayload | null {
  if (!isObj(raw)) return null;
  if (raw.state === 'owner_only') return { state: 'owner_only', reason: str(raw.reason), title: str(raw.title) };
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

/** The chart height for one frame (viewBox units). */
export function ggwChartHeight(tf: string, phone: boolean): number {
  if (phone) return GGW_CHART_H_PHONE;
  return (GGW_CHART_H as Record<string, number>)[tf] ?? GGW_CHART_H['3m'];
}
