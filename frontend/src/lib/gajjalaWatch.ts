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
import type { CSSProperties } from 'react';
import { EMA_BOLD, toneColor, VWAP_LINE_W, type CmAxis, type CmEmaBlink, type CmLineTone, type CmTile } from './chartMaps';
import { ggRunBasesLine, type GgStages } from './gajjala';
import { parseGgwBroker, type GgwBroker } from './ggwBroker';   // 🚫 2026-11-19 (spec watchfid)

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
/** 📈 2026-11-23 (vwapzones spec §3.9 [O2]): the forming 5- / 15-min candle built from the row's OWN 1-min chart (the stored
 *  1-min bars of the bucket + the live 1-min bars past them — lib/ggwLive.ggwSeedLive). false = main's forming candle (only
 *  the prints seen since the page opened). BUILT, OFF — HIS CALL #13 (docs/gajjala/watch_vwap_zones_frontend_2026_11_23.md). */
export const GGW_SEED_FORMING = false;   // HIS CALL #13 (2026-11-23) — false = main's forming candle
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

/** Chart heights in viewBox units (PatternChart W = 620) — MINE, HIS CALL #10. 2026-11-23 (Ajay: "Can you remove 3 mins just
 *  add 15 mins instead.. So 1 min, 5 and 15 accross board"): the 15-min chart takes the height the 3-min one had. The first arithmetic (≈ 236 px above
 *  the grid → three rows fit) was WRONG: measured 357 px above and 56 below, the fixed-height 3×3 overflowed at both
 *  2560×1440 and 1920×1080. Above the phone break these are now the starting height and the SHARE of a fitted tile
 *  (GGW_FIT_GROW); the rows are sized from the viewport (ggwFitRowHeight; docs/gajjala/watch_frontend_2026_11_15.md). */
export const GGW_CHART_H = { '1m': 120, '5m': 180, '15m': 180 } as const;
/** 👀 3 rows on one screen (2026-11-15 fix #3; Ajay: "I have a 27 inch monitor I wanna fit 3x3 tikers on watch at any
 *  given time"). Above the phone break the grid rows are sized from the viewport: row = (innerHeight − what the board
 *  holds above the grid (2026-11-16: measured from the BOARD's top, no longer the page's) − (rows − 1) row gaps) / rows,
 *  never under GGW_FIT_ROW_MIN_PX. The charts then
 *  flex to fill the row, the 1-min and the 5-/15-min pair sharing the height in the SAME proportion GGW_CHART_H gives
 *  them at any width (the pair is half the width, so its share is GGW_CHART_H of the 5-min / 2). */
export const GGW_FIT_ROWS = 3;
/** The tile floor for a short desktop window — MINE (layout, not a rule): below it the page scrolls instead of the
 *  charts shrinking further. 1920×1080 measures ≈ 213 px a row, so it still fits there. HIS CALL to move. */
export const GGW_FIT_ROW_MIN_PX = 200;
/** The flex shares of the 1-min chart and the 5-/15-min pair inside a fitted tile (derived from GGW_CHART_H). */
export const GGW_FIT_GROW = { top: GGW_CHART_H['1m'], pair: GGW_CHART_H['5m'] / 2 } as const;
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
/** 🆕 2026-11-19 — Ajay: "Add things to my auto watch list please and make them active I see not active on my page. Becuz
 *  they are in query params". A saved/linked pick (`show=`) hides every name it does not list, so a name added after the
 *  pick was made sat there inactive. `ggw.seen` = the list this browser last saw; a name on the list now that was not
 *  there then is NEW and joins the pick, first. No pick (the pages) → nothing to merge; no seen list yet (a browser from
 *  before this build, or a shared link opened cold) → nothing is new; the first visit only records it. Returns the pick unchanged when nothing is new. */
export const GGW_SEEN_KEY = 'ggw.seen';
export function readGgwSeen(): string[] | null {
  try { return parseGgwPick(window.localStorage.getItem(GGW_SEEN_KEY)); } catch { return null; }
}
export function saveGgwSeen(list: ReadonlyArray<string>): void {
  try {
    if (list.length) window.localStorage.setItem(GGW_SEEN_KEY, list.join(','));
    else window.localStorage.removeItem(GGW_SEEN_KEY);
  } catch { /* private window: the next visit records it again */ }
}
export function ggwNewNames(list: ReadonlyArray<string>, seen: ReadonlyArray<string> | null): string[] {
  if (!seen) return [];
  return list.filter((s) => !seen.includes(s));
}
export function ggwActivateNew(pick: ReadonlyArray<string> | null, list: ReadonlyArray<string>,
                               seen: ReadonlyArray<string> | null): string[] | null {
  return ggwJoinPick(pick, list, ggwNewNames(list, seen));
}
/** 🆕 2026-11-19 (watch-newest spec §3.3) — Ajay: "When I add a new ticket they are gettinf added in to que but not active
 *  … charts are not loading I amhaving to click on the chips again". `ggw.pickAt` = when HE last changed the view (a
 *  ticker toggle, a page move, a per-screen pick, ← →, a full-screen step) — never written on mount, by an activation
 *  pass, a box add or `?focus=`. A row of his (or a 🎯 A+) the server says was added AFTER it is new and joins his pick. */
export const GGW_PICK_AT_KEY = 'ggw.pickAt';
/** MINE — HIS CALL #1 (2026-11-19): a browser with no ggw.pickAt yet treats rows added in the last 24 h as new. */
export const GGW_NEW_FALLBACK_HOURS = 24;   // MINE — HIS CALL #1 (2026-11-19)
export function readGgwPickAt(): number | null {
  try {
    const v = window.localStorage.getItem(GGW_PICK_AT_KEY);
    if (typeof v !== 'string' || !/^\d+$/.test(v)) return null;
    const n = Number(v);
    return Number.isInteger(n) && n > 0 ? n : null;
  } catch { return null; }
}
export function saveGgwPickAt(ms: number): void {
  if (typeof ms !== 'number' || !Number.isFinite(ms) || ms <= 0) return;
  try { window.localStorage.setItem(GGW_PICK_AT_KEY, String(Math.round(ms))); } catch { /* private window */ }
}
/** The served add time of a row in ms (null when absent / junk). */
export function ggwAddedMs(row: { added_at?: string | null }): number | null {
  const v = row?.added_at;
  if (typeof v !== 'string') return null;
  const t = Date.parse(v);
  return Number.isFinite(t) ? t : null;
}
/** A row that may join his pick: HIS own name, or a 🎯 A+ (the A+ block, or an auto seat whose served reason is A+). An
 *  ordinary 🤖 potential never joins (HIS CALL #3 — up to 18 tiles × 3 live charts). */
export function ggwJoinable(row: GgwRow): boolean {
  return row.auto == null || row.aplus != null || row.auto?.why === 'aplus';
}
/** The joinable rows that are NEW to this view: added after `pickAt` (strictly; no pickAt → the last
 *  GGW_NEW_FALLBACK_HOURS), or not in this browser's `seen` list. Row order. */
export function ggwFreshNames(rows: ReadonlyArray<GgwRow>, o: { seen: ReadonlyArray<string> | null;
  pickAt: number | null; nowMs: number }): string[] {
  const since = o.pickAt ?? (o.nowMs - GGW_NEW_FALLBACK_HOURS * 3600_000);
  const out: string[] = [];
  for (const r of rows) {
    if (!ggwJoinable(r)) continue;
    const at = ggwAddedMs(r);
    const byTime = at != null && at > since;
    const bySeen = o.seen != null && !o.seen.includes(r.symbol);
    if ((byTime || bySeen) && !out.includes(r.symbol)) out.push(r.symbol);
  }
  return out;
}
/** The first of HIS rows this browser has not shown yet (a card ➕ from another tab) — the only name a page open outlines.
 *  No seen list (a cold browser) → null. */
export function ggwUnseenOwn(rows: ReadonlyArray<GgwRow>, seen: ReadonlyArray<string> | null): string | null {
  if (!seen) return null;
  const r = rows.find((x) => x.auto == null && !seen.includes(x.symbol));
  return r ? r.symbol : null;
}
/** `fresh` names joined to the FRONT of a pick (each once, only names on the list). No pick, or a pick with no name on
 *  the list (the pages are showing) → an unchanged copy — it never collapses to the new names. */
export function ggwJoinPick(pick: ReadonlyArray<string> | null, list: ReadonlyArray<string>,
                            fresh: ReadonlyArray<string>): string[] | null {
  if (!pick || !pick.length) return pick ? [...pick] : null;
  if (!pick.some((s) => list.includes(s))) return [...pick];
  const add: string[] = [];
  for (const s of fresh) if (list.includes(s) && !pick.includes(s) && !add.includes(s)) add.push(s);
  return add.length ? [...add, ...pick] : [...pick];
}
/** 🐛 2026-11-22 — Ajay: "There is a bug, I added WETO as new one to watch list everything got de activated from watch
 *  list". A saved pick (`ggw.pick` / `show=`) whose names had all left the list sat inert; adding one of them back
 *  switched it on and hid every other tile. Each full load now keeps only the pick's names still in `keep` (the list +
 *  the names a × is still hiding), in pick order; none left (or no pick) → null (the pages). */
export function ggwPrunePick(pick: ReadonlyArray<string> | null, keep: ReadonlyArray<string>): string[] | null {
  if (!pick) return null;
  const next = pick.filter((s) => keep.includes(s));
  return next.length ? next : null;
}
/** 🐛 2026-11-22 review residual — a (pruned) pick whose names were ALL added after this browser last set the view
 *  (`after`) cannot be a pick he made of them: it is a dead pick revived by an add elsewhere (a card ➕, another device)
 *  → null (the pages). Any other name in it → the pick unchanged. */
export function ggwLivePick(pick: ReadonlyArray<string> | null, after: ReadonlyArray<string>): string[] | null {
  if (!pick || !pick.length) return null;
  return pick.some((s) => !after.includes(s)) ? [...pick] : null;
}
/** The rows' identity for the activation / anchor passes: symbol, add time and the join bit — a 🤖 potential turning
 *  🎯 A+ in place changes it; text / frames never do. */
export function ggwRowsKey(rows: ReadonlyArray<GgwRow>): string {
  return rows.map((r) => `${r.symbol}@${r.added_at ?? ''}@${ggwJoinable(r) ? 1 : 0}|`).join('');
}
/** The board without these names (rows and his symbols); the SAME object when none of them is on it. */
export function ggwWithout(b: GgwBoard, gone: ReadonlyArray<string>): GgwBoard {
  if (!gone.length) return b;
  const g = new Set(gone);
  if (!b.rows.some((r) => g.has(r.symbol)) && !b.symbols.some((s) => g.has(s))) return b;
  return { ...b, rows: b.rows.filter((r) => !g.has(r.symbol)), symbols: b.symbols.filter((s) => !g.has(s)) };
}
/** A removed name leaves the pick; the last one leaving → null (the pages). */
export function ggwDropFromPick(pick: ReadonlyArray<string> | null, sym: string): string[] | null {
  if (!pick) return null;
  const next = pick.filter((s) => s !== sym);
  return next.length ? next : null;
}
/** The pending poll's next step. `due` = waited < max s, polled every `poll` s; `late` = waited ≥ max s (always returned,
 *  so the served "still reading" words show in and out of window). After the cap the late names are polled every
 *  `latePoll` s ONLY when `refresh` is 0 (out of window — in window the minute re-GET already re-reads them). No
 *  `latePoll` (an older server) → the poll stops at the cap exactly as before. */
export function ggwPendingPlan(pend: ReadonlyArray<string>, since: ReadonlyMap<string, number>, nowMs: number,
  o: { poll: number | null; max: number | null; latePoll: number | null; refresh: number | null }):
  { names: string[]; delaySec: number; late: string[] } {
  const poll = o.poll ?? 0;
  const max = o.max ?? 0;
  const latePoll = o.latePoll ?? 0;
  const due: string[] = [];
  const late: string[] = [];
  if (max > 0) {
    for (const s of pend) {
      const waited = nowMs - (since.get(s) ?? nowMs);
      if (waited < max * 1000) due.push(s); else late.push(s);
    }
  }
  if (due.length && poll > 0) return { names: due, delaySec: poll, late };
  if (late.length && latePoll > 0 && !((o.refresh ?? 0) > 0)) return { names: late, delaySec: latePoll, late };
  return { names: [], delaySec: 0, late };
}
/** The page that keeps the anchor (the first name shown) on screen; null when it left the list. */
export function ggwAnchorPage(list: ReadonlyArray<string>, anchor: string | null, size: number): number | null {
  if (!anchor) return null;
  const i = list.indexOf(anchor);
  return i < 0 ? null : ggwPageOf(i, size);
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
/** 🤖 2026-11-17 (watch-auto spec §3.6, WP-C) — Ajay: "Can you add more stocks in to watch list basically I need
 *  portentials from Gajjals's 1 min and regular and also Audited potentials with good volume to Watchlist on an
 *  interval.. Remove as they are not progressing". The served block on a row the server ADDED from the Gajjala boards'
 *  🧠 potentials (backend chart_maps/gajjala_watch/auto.py → payload.row `auto`). Every string is served: `text` = the
 *  chip, `added_text` / `volume_text` / `leaving_text` = its hover, `remove_title` = the × title. HIS rows carry null. */
export type GgwRowAuto = {
  tag: string; sources: string[]; source_words: string[]; text: string;
  volume_text: string | null; volume_source: string | null;
  added_et: string | null; added_text: string | null; leaving_text: string | null; remove_title: string | null;
  /** 🎯 2026-11-17 (spec ggwaplus2 — Ajay: "Push new Apluses immediately in to watch list"): the served seat reason —
   *  "aplus" (an A+ seat) or "potential"; null on junk; ABSENT on an older server (the key is set only when served — the
   *  11-17 auto fixture's blocks stay byte-equal). The FE composes no word from it. */
  why?: string | null;
};
/** 🎯 2026-11-17 (spec ggwaplus) — Ajay: "Also add an A+ tag on watch list as they become A+". One served A+ read of the
 *  name on a Gajjala board this session (backend payload.aplus_items): `source_word` / `setup_label` / `word` / `at_et`
 *  are served words. Display only — UNMEASURED. */
export type GgwAplusItem = {
  source: string; source_word: string | null; setup: string; setup_label: string | null; state: string;
  word: string | null; at_et: string | null;
};
/** 🎯 The row's served A+ block: `text` = the chip (the first item's clock already inside it), `title` = its hover,
 *  `tag` = the pager prefix. null when no board reads the name A+ (and on every row of an older server). */
export type GgwRowAplus = { tag: string; text: string; title: string | null; items: GgwAplusItem[] };
/** 🏷️ 2026-11-18 (spec wtags §3.2) — Ajay: "Also add Short Interest tag and other tags on top of stock ticker
 *  information for me to read, like here". The 🚩 GG5 card's own served tags of a Watch name CARDED ON TODAY'S BOARD
 *  (backend gajjala_watch/tags.py). null = no card on the board (or the read faulted): the tile then prints only its
 *  🚀 / 🩳 chips and the existing 🤖 / 🎯. Every word served. */
export type GgwTagSetup = { setup: string; label: string; state: string; state_label: string | null };
export type GgwTagFloat = { text: string; shares: number | null; src: string | null; as_of: string | null; suspect: boolean };
export type GgwRowTags = {
  on_board: true; setups: GgwTagSetup[]; stages: GgStages | null; float: GgwTagFloat | null;
  broker_text: string | null; trader_text: string | null; promo_text: string | null;
};
/** 🔢 2026-11-21 (spec watchfloat §3.5) — Ajay: "can you add the current float value also to the tickers on the watch
 *  list." The row's own served float (backend gajjala_watch/float_read.py) on EVERY row, carded or not: the card tags'
 *  five keys plus the served hover `title`, the served `suspect_text` and where it was read (`read_from`). Every word
 *  served; display only, UNMEASURED. */
export type GgwRowFloat = GgwTagFloat & { suspect_text: string | null; title: string | null; read_from: string | null };
/** 🗂 2026-11-22 (spec watch_org rev 4 §3.3 / §3.5) — Ajay: "Manual ones I add them need to be on top then auto
 *  intraday..". The row's served organisation block (backend gajjala_watch/sections.py → row `org`). `group` = the
 *  served section key this row sits in (session-stable); every other block is a dict or null. Every word is SERVED —
 *  the FE prints `text` / `title` verbatim and composes none. Descriptive, UNMEASURED. */
export type GgwWhen = {
  bucket: string | null; verb: string | null; at_et: string | null; date: string | null; text: string; title: string | null;
};
/** The served setup chip (🎾 picked first by the server). */
export type GgwSetupTag = { text: string; title: string | null };
/** 📅 the served "ran last session" read (backend runners.ran_of). `text` = the chip — ONLY when it counts; `title` is
 *  served either way (the premarket-peak and under-the-bar lines live there, printed in the ⋯ drawer). */
export type GgwRan = {
  date: string | null; day: string | null; prev_close: number | null; high: number | null; run_pct: number | null;
  peak_et: string | null; timing: string | null; timing_text: string | null; pm_high_pct: number | null;
  premarket_peak: boolean; counts: boolean; reg_close: number | null; text: string | null; title: string | null;
};
/** 🏆 the served past-winner block, normalised: `text` = the chip, `items` = every served win's words (the drawer),
 *  `more` = the served "+N more", `title` = the served hover (null → the items). */
export type GgwPastWinner = { text: string; items: string[]; more: string | null; title: string | null };
export type GgwOrg = {
  group: string; when: GgwWhen | null; setup: GgwSetupTag | null; ran: GgwRan | null; past_winner: GgwPastWinner | null;
};
/** One served section, in served order: `key` = any non-blank served key (the FE holds NO key list — a later served
 *  key renders without an FE change), `text` = the header words, `hint` = its served explanation. */
export type GgwSection = { key: string; title: string | null; text: string; hint: string | null; n: number | null; symbols: string[] };
export type GgwRow = {
  symbol: string; state: GgwRowState | string; text: string | null;
  from_session: string | null; as_of_et: string | null; stale: boolean;
  /** 👀 2026-11-23 — set (true) ONLY by parseRow, i.e. on a row of the Watch payload. There `stale` means the last minute
   *  read failed or ran out of budget and the stored bars are still this session's, so the live tail survives it. A
   *  🚩 / 🧪 card-view row (lib/gajjalaCardView.ggcRow) never carries it: its `stale` is the house verdict on an old
   *  source doc and that row stays dark. */
  stale_keeps_live?: boolean;
  frames: GgwFrame[]; rang: GgwRang[];
  /** 🤖 null on HIS rows (and on every row of an older server). Optional ONLY so the 🚩 card view's own row builders
   *  (lib/gajjalaCardView.ggcRow, GgCardView) stay valid — parseGgw always sets it. */
  auto?: GgwRowAuto | null;
  /** 🎯 null when no A+ (optional for the same reason as `auto` — parseGgw always sets it). */
  aplus?: GgwRowAplus | null;
  /** 🏷️ 2026-11-18: null when the name is not carded on today's 🚩 board (optional for the same reason as `auto` —
   *  parseGgw always sets it). */
  tags?: GgwRowTags | null;
  /** 🚫 2026-11-19 (spec watchfid): the served broker word for ANY row (carded or not); null = not on his list. */
  broker_text?: string | null;
  /** 🆕 2026-11-19: when the name was added (ISO UTC, served; null on a name from before 11-19 and on an older server).
   *  Optional for the same reason as `auto` — parseGgw always sets it. */
  added_at?: string | null;
  /** 🆕 2026-11-19: the served "still reading" words of a pending row, shown after the pending cap (null otherwise). */
  late_text?: string | null;
  /** 🔢 2026-11-21 (spec watchfloat): the served float of ANY row (null = no float read on file — never invented).
   *  Optional for the same reason as `auto` — parseGgw always sets it. */
  float?: GgwRowFloat | null;
  /** 🗂 2026-11-22: the served organisation block. The key is set ONLY when served (an older server's rows stay
   *  byte-equal); null = served but junk / the `only` poll (no chip, no group). */
  org?: GgwOrg | null;
  /** 📐 2026-11-23: the served daily-zones line. The key is set ONLY when served (an older server's rows stay byte-equal);
   *  null = served but junk / none (no line). */
  levels?: GgwLevels | null;
};
/** 🤖 One removal of THIS session, newest first — `text_full` is printed verbatim (the FE composes nothing). */
export type GgwAutoRemoved = {
  symbol: string; at_et: string | null; reason: string | null; state: string | null; text: string | null; text_full: string;
};
/** 🤖 The board's served auto head: `title` (hover = `hint`), `text` = the unreadable word, `empty_text` when none is
 *  on, `removed` = the newest removals (of `removed_total`), `removed_title` = the strip's summary. */
export type GgwAuto = {
  state: string; cap: number | null; n: number; symbols: string[];
  title: string | null; hint: string | null; empty_text: string | null; text: string | null;
  removed: GgwAutoRemoved[]; removed_total: number | null; removed_title: string | null; push_mode: string | null;
  /** 🎯 2026-11-17 (spec ggwaplus2): the served line when the loop's last step had A+ names with no seat; null else. */
  skipped_text: string | null;
};
export type GgwPass = { at_et: string | null; text: string | null; stale: boolean };
export type GgwInfo = {
  honesty: string | null; push_text: string | null; uptrend_rule: string | null;
  push_mode: string | null; push_frames: string[];
  /** 🤖 the auto section's ℹ️ clause (backend auto.rules_line, served once); null on an older server. */
  auto_text: string | null;
  /** 📈📐 2026-11-23 (vwapzones §3.4): the served VWAP / daily-zones sentences (backend vwap.rules_line /
   *  levels.rules_line — the legend hover's words, printed in ℹ️ because a phone has no hover); null when off / older. */
  vwap_text: string | null;
  zones_text: string | null;
};
/** One served legend entry. `title` (2026-11-23) = its served hover sentence; the key is set ONLY when served. */
export type GgwLegend = { tone: 'ema9' | 'ema21' | 'vwap' | 'zone_demand' | 'zone_supply' | string; label: string; title?: string | null };
/** 📐 2026-11-23 (vwapzones §3.6 / §3.10): a row's served daily-zones line — `state` ∈ ok / none / retry / pending (the
 *  server's words for each, never composed here), `text` printed verbatim, `title` its hover, `as_of` the last daily
 *  bar the zones were read through. The bands themselves ride in each frame's `tile.bands` (`ctx: true`). */
export type GgwLevels = { state: string; text: string | null; title: string | null; as_of: string | null };
export type GgwBoard = {
  state: 'ok'; title: string; session: string | null; is_today: boolean; in_window: boolean;
  refresh_sec: number; next_window_sec: number | null;
  pending_poll_sec: number | null; pending_wait_max_sec: number | null;
  /** 🆕 2026-11-19: the poll after the pending cap, out of window only (served while a row is pending; null else). */
  pending_late_poll_sec: number | null;
  max_symbols: number | null; symbols: string[]; full: boolean; full_text: string | null;
  /** 🔁 2026-11-18: true ONLY when every one of his names is 🎯 A+ (nothing can make room) — the add box is then
   *  disabled and `full_text` is the served refusal, shown as a visible line. At the cap otherwise ➕ replaces. */
  full_blocked: boolean;
  add_label: string | null; add_placeholder: string | null; remove_label: string | null; empty_text: string | null;
  pass: GgwPass | null; info: GgwInfo | null; legend: GgwLegend[]; rows: GgwRow[];
  /** 🤖 the auto section's head (absent / junk → null — an older server serves none; the board then renders as before). */
  auto: GgwAuto | null;
  /** 🚫 2026-11-19 (spec watchfid): the served broker block (owner only; absent / junk → null — no button). */
  broker?: GgwBroker | null;
  /** 🗂 2026-11-22: the served sections in served order. The key is set ONLY when served; null / [] → the flat board. */
  sections?: GgwSection[] | null;
};
export type GgwOwnerOnly = { state: 'owner_only'; reason: string | null; title: string | null };
/** The server's own failure answer (payload.error_payload): its reason is printed verbatim (served words only). */
export type GgwServedError = { state: 'error'; reason: string | null; title: string | null };
export type GgwPayload = GgwBoard | GgwOwnerOnly | GgwServedError;
/** The add / remove answer (store.add / store.remove). */
/** 🔁 2026-11-18: `replaced` = the oldest name he added that made room (state "replaced" only). */
export type GgwWriteAnswer = { state: string; symbols: string[]; symbol: string | null; text: string | null;
  replaced?: string | null };

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

/** 🤖 A row's auto block: an object with a served `tag` and `text`, else null (junk never draws a chip). */
function parseRowAuto(v: unknown): GgwRowAuto | null {
  if (!isObj(v) || !str(v.tag) || !str(v.text)) return null;
  return {
    tag: v.tag, sources: strs(v.sources), source_words: strs(v.source_words), text: v.text,
    volume_text: str(v.volume_text), volume_source: str(v.volume_source),
    added_et: str(v.added_et), added_text: str(v.added_text), leaving_text: str(v.leaving_text),
    remove_title: str(v.remove_title),
    ...('why' in v ? { why: str(v.why) } : {}),
  };
}

/** 🎯 A row's A+ block: an object with a served `tag` and `text`, else null (junk never draws a chip). An item
 *  without a served `source` / `setup` / `state` is dropped. */
export function parseRowAplus(v: unknown): GgwRowAplus | null {
  if (!isObj(v) || !str(v.tag) || !str(v.text)) return null;
  return {
    tag: v.tag, text: v.text, title: str(v.title),
    items: (Array.isArray(v.items) ? v.items : [])
      .filter((it: unknown) => isObj(it) && str(it.source) && str(it.setup) && str(it.state))
      .map((it: any) => ({
        source: it.source, source_word: str(it.source_word), setup: it.setup, setup_label: str(it.setup_label),
        state: it.state, word: str(it.word), at_et: str(it.at_et),
      })),
  };
}

/** 🏷️ A row's tags block (2026-11-18, the parseRowAplus pattern): an object with `on_board === true`, else null (junk
 *  never draws a chip). A setup without a served `setup` / `label` is dropped; `stages` is kept only with a served
 *  `title` (GgStages renders nothing otherwise); `float` only with a served `text`; the three texts through str(). */
export function parseRowTags(v: unknown): GgwRowTags | null {
  if (!isObj(v) || v.on_board !== true) return null;
  const fl = isObj(v.float) && str(v.float.text) ? v.float : null;
  return {
    on_board: true,
    setups: (Array.isArray(v.setups) ? v.setups : [])
      .filter((it: unknown) => isObj(it) && str(it.setup) && str(it.label))
      .map((it: any) => ({ setup: it.setup, label: it.label, state: str(it.state) ?? '', state_label: str(it.state_label) })),
    stages: isObj(v.stages) && str(v.stages.title) ? (v.stages as GgStages) : null,
    float: fl ? {
      text: fl.text as string, shares: num(fl.shares), src: str(fl.src), as_of: str(fl.as_of), suspect: fl.suspect === true,
    } : null,
    broker_text: str(v.broker_text),
    trader_text: str(v.trader_text),
    promo_text: str(v.promo_text),
  };
}

/** 🔢 A row's float block (2026-11-21, spec watchfloat — the parseRowTags float rule): an object with a served `text`,
 *  else null (junk never draws a chip). `shares` through num() (NaN → null, the chip is KEPT); `suspect` true ONLY for
 *  `=== true`; the three newer strings through str(). */
export function parseRowFloat(v: unknown): GgwRowFloat | null {
  if (!isObj(v) || !str(v.text)) return null;
  return {
    text: v.text as string, shares: num(v.shares), src: str(v.src), as_of: str(v.as_of), suspect: v.suspect === true,
    suspect_text: str(v.suspect_text), title: str(v.title), read_from: str(v.read_from),
  };
}

/** 🔢 The ONE float a Watch row prints (the ggwBrokerText precedent): the row's own served float first, else the 🚩 card
 *  tags' float (an older server serves only that one — no hover, no suspect line, no read_from); blank → null. */
export function ggwFloat(row: { float?: GgwRowFloat | null; tags?: { float: GgwTagFloat | null } | null }): GgwRowFloat | null {
  const own = row?.float;
  if (own && str(own.text)) return own;
  const t = row?.tags?.float;
  if (t && str(t.text)) return { ...t, suspect_text: null, title: null, read_from: null };
  return null;
}

/** 🤖 The board's auto block: an object with a served `state`, else null. A removal without `text_full` is dropped. */
function parseAuto(v: unknown): GgwAuto | null {
  if (!isObj(v) || !str(v.state)) return null;
  const n = num(v.n);
  const total = num(v.removed_total);
  return {
    state: v.state,
    cap: num(v.cap),
    n: n != null && n >= 0 ? n : 0,
    symbols: strs(v.symbols),
    title: str(v.title), hint: str(v.hint), empty_text: str(v.empty_text), text: str(v.text),
    removed: (Array.isArray(v.removed) ? v.removed : [])
      .filter((r: unknown) => isObj(r) && str(r.text_full))
      .map((r: any) => ({
        symbol: typeof r.symbol === 'string' ? r.symbol : '', at_et: str(r.at_et), reason: str(r.reason),
        state: str(r.state), text: str(r.text), text_full: r.text_full,
      })),
    removed_total: total != null && total >= 0 ? total : null,
    removed_title: str(v.removed_title),
    push_mode: str(v.push_mode),
    skipped_text: str(v.skipped_text),
  };
}

/** 🗂 2026-11-22 — the served time line block: an object with a served `text`, else null (junk never draws a chip). */
function parseWhen(v: unknown): GgwWhen | null {
  if (!isObj(v) || !str(v.text)) return null;
  return { bucket: str(v.bucket), verb: str(v.verb), at_et: str(v.at_et), date: str(v.date), text: v.text, title: str(v.title) };
}

/** 🗂 the served setup chip: an object with a served `text`, else null. */
function parseSetupTag(v: unknown): GgwSetupTag | null {
  if (!isObj(v) || !str(v.text)) return null;
  return { text: v.text, title: str(v.title) };
}

/** 📅 the served ran block: kept when it serves a chip `text` or a drawer `title`; every number through num() (NaN /
 *  inf → null); `counts` / `premarket_peak` true ONLY for `=== true`. Neither text nor title → null. */
export function parseRan(v: unknown): GgwRan | null {
  if (!isObj(v)) return null;
  const text = str(v.text);
  const title = str(v.title);
  if (!text && !title) return null;
  return {
    date: str(v.date), day: str(v.day), prev_close: num(v.prev_close), high: num(v.high), run_pct: num(v.run_pct),
    peak_et: str(v.peak_et), timing: str(v.timing), timing_text: str(v.timing_text), pm_high_pct: num(v.pm_high_pct),
    premarket_peak: v.premarket_peak === true, counts: v.counts === true, reg_close: num(v.reg_close), text, title,
  };
}

/** 🏆 the served past-winner block, either the replays shape (`past_winner: [{text}]`, `past_winner_more_text`) or a
 *  served `{text, title, items}`. The chip = the served `text`, else the first served win's words; none → null. */
export function parsePastWinner(v: unknown): GgwPastWinner | null {
  if (!isObj(v)) return null;
  const list = Array.isArray(v.past_winner) ? v.past_winner : Array.isArray(v.items) ? v.items : [];
  const items = list
    .map((w: unknown) => (typeof w === 'string' ? str(w) : isObj(w) ? str(w.text) : null))
    .filter((s: string | null): s is string => !!s);
  const text = str(v.text) ?? items[0] ?? null;
  if (!text) return null;
  return { text, items, more: str(v.past_winner_more_text) ?? str(v.more_text), title: str(v.title) };
}

/** 📐 A row's (or a 🚩 card payload's) served daily-zones block: an object with a served `state`, else null (junk never
 *  draws a line). The three strings through str(). */
export function parseRowLevels(v: unknown): GgwLevels | null {
  if (!isObj(v) || !str(v.state)) return null;
  return { state: (v.state as string).trim(), text: str(v.text), title: str(v.title), as_of: str(v.as_of) };
}

/** 🗂 A row's served org block: an object with a non-blank string `group`, else null. Each inner block through its own
 *  parser (junk → null: no chip). */
export function parseRowOrg(v: unknown): GgwOrg | null {
  if (!isObj(v) || !str(v.group)) return null;
  return {
    group: (v.group as string).trim(),
    when: parseWhen(v.when), setup: parseSetupTag(v.setup), ran: parseRan(v.ran), past_winner: parsePastWinner(v.past_winner),
  };
}

/** 🗂 The served sections, in SERVED order: ANY non-blank string key is kept (no key list here — the server owns the
 *  keys and their order); a section without served header words, a blank / non-string key or a repeated key is
 *  dropped. Not a list → null. */
export function parseSections(v: unknown): GgwSection[] | null {
  if (!Array.isArray(v)) return null;
  const out: GgwSection[] = [];
  for (const s of v) {
    if (!isObj(s) || !str(s.key)) continue;
    const key = (s.key as string).trim();
    const text = str(s.text) ?? str(s.title);
    if (!text || out.some((x) => x.key === key)) continue;
    const n = num(s.n);
    out.push({
      key, title: str(s.title), text, hint: str(s.hint), n: n != null && n >= 0 ? n : null, symbols: strs(s.symbols),
    });
  }
  return out;
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
    stale_keeps_live: true,
    frames: (Array.isArray(v.frames) ? v.frames : []).map((f: unknown) => parseFrame(f, symbol))
      .filter((f: GgwFrame | null): f is GgwFrame => !!f),
    rang: (Array.isArray(v.rang) ? v.rang : [])
      .filter((r: unknown) => isObj(r) && str(r.text))
      .map((r: any) => ({ frame: String(r.frame ?? ''), at_et: str(r.at_et), text: r.text })),
    auto: parseRowAuto(v.auto),
    aplus: parseRowAplus(v.aplus),
    tags: parseRowTags(v.tags),
    broker_text: str(v.broker_text),
    added_at: str(v.added_at) != null && Number.isFinite(Date.parse(v.added_at)) ? v.added_at : null,
    late_text: str(v.late_text),
    float: parseRowFloat(v.float),
    ...('org' in v ? { org: parseRowOrg(v.org) } : {}),
    ...('levels' in v ? { levels: parseRowLevels(v.levels) } : {}),
  };
}

/** 👀 LIVE (2026-11-16) — the ONE rule for "this row may carry live bars": a served `ok` row of TODAY's session
 *  (`from_session` null) that is either not stale, or stale AND carries `stale_keeps_live === true`. 2026-11-23: a
 *  Watch row (parseRow sets the flag) whose last minute read failed or ran out of budget keeps its live tail — its
 *  stored bars are still this session's. A prior-session row, a not-ok row and a stale row WITHOUT the flag (the 🚩 /
 *  🧪 card view's ggcRow: an old source doc) carry none — they show their stored bars only. Used by
 *  ggwLive.ggwFrameMetas, the board's Tile and the card view. */
export function ggwRowLive(row: GgwRow): boolean {
  return row.state === 'ok' && row.from_session == null && (!row.stale || row.stale_keeps_live === true);
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
    auto_text: str(raw.info.auto_text),
    vwap_text: str(raw.info.vwap_text),
    zones_text: str(raw.info.zones_text),
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
    pending_late_poll_sec: num(raw.pending_late_poll_sec),
    max_symbols: num(raw.max_symbols),
    symbols: strs(raw.symbols),
    full: raw.full === true,
    full_text: str(raw.full_text),
    full_blocked: raw.full_blocked === true,
    add_label: str(raw.add_label),
    add_placeholder: str(raw.add_placeholder),
    remove_label: str(raw.remove_label),
    empty_text: str(raw.empty_text),
    pass,
    info,
    legend: (Array.isArray(raw.legend) ? raw.legend : [])
      .filter((l: unknown) => isObj(l) && str(l.tone) && str(l.label))
      .map((l: any) => ({ tone: l.tone, label: l.label, ...('title' in l ? { title: str(l.title) } : {}) })),
    rows: raw.rows.map(parseRow).filter((r: GgwRow | null): r is GgwRow => !!r),
    auto: parseAuto(raw.auto),
    broker: parseGgwBroker(raw.broker),
    ...('sections' in raw ? { sections: parseSections(raw.sections) } : {}),
  };
}

/** 🤖 The live-interest list (2026-11-17): EVERY row's symbol in served order — his names, then the auto names — so an
 *  auto tile's charts move live like his (the board used to POST `symbols`, his names only). */
export function ggwLiveSymbols(b: GgwBoard): string[] {
  return b.rows.map((r) => r.symbol);
}

/** The rows still waiting for their first read (the pending poll asks for these only). */
export function ggwPendingSymbols(b: GgwBoard): string[] {
  return b.rows.filter((r) => r.state === 'pending').map((r) => r.symbol);
}

/** A partial answer's rows merged into the board by symbol. The board keeps its own order and head (the server never
 *  reorders; a partial answer is never a reason to re-cut the list). */
export function ggwMergeRows(b: GgwBoard, partial: GgwBoard): GgwBoard {
  const by = new Map(partial.rows.map((r) => [r.symbol, r] as const));
  /* 🗂 2026-11-22 [C6]: the `only` poll serves `org: null` — the board row keeps ITS org (its group never changes on a
   * partial answer, so no second header). A board row without the key (an older server) merges exactly as before. */
  return {
    ...b,
    rows: b.rows.map((r) => {
      const n = by.get(r.symbol);
      if (!n) return r;
      return 'org' in r ? { ...n, org: r.org } : n;
    }),
  };
}

// ── 🗂 sections (2026-11-22, spec watch_org rev 4 §3.5) ─────────────────────────────────────────────────────────────
/* Ajay 2026-11-22: "Manual ones I add them need to be on top then auto intraday..". The server groups and orders the
 * rows and writes every word (sections.py); the FE holds NO section key list — it prints whatever sections are served,
 * in served order. Layout only: nothing here gates, pushes, caps or sorts. */

/** Org mode = the server served at least one section. An older server (no key) or `SECTIONS_ON = False` → the flat board. */
export function ggwSectionsOn(b: { sections?: GgwSection[] | null } | null | undefined): boolean {
  return !!b && Array.isArray(b.sections) && b.sections.length > 0;
}

/** The section headers: one per served key at the FIRST row index carrying it ([C6] — `[a, a, b, a]` → headers at 0 and
 *  2, never a second `a`). A row group with no served section draws no header. Row order. */
export function ggwGroupStarts(rows: ReadonlyArray<{ org?: GgwOrg | null }>,
                               sections: ReadonlyArray<GgwSection> | null | undefined): Array<{ at: number; section: GgwSection }> {
  const by = new Map((sections ?? []).map((s) => [s.key, s] as const));
  const seen = new Set<string>();
  const out: Array<{ at: number; section: GgwSection }> = [];
  rows.forEach((r, i) => {
    const g = r?.org?.group;
    if (!g || seen.has(g)) return;
    seen.add(g);
    const s = by.get(g);
    if (s) out.push({ at: i, section: s });
  });
  return out;
}

/** ⋯ the per-tile drawer control (structural glyph + control words; no word about a stock). */
export const GGW_DRAWER = { glyph: '⋯', openTitle: 'Show details', closeTitle: 'Hide details' } as const;
/** ▾ / ▸ a phone section header's fold glyphs (structural). */
export const GGW_SECTION_GLYPH = { open: '▾', closed: '▸' } as const;

/** 📱 The phone's folded sections (a per-viewer convenience): a JSON list of served section keys. Junk / blocked → [] (all
 *  open). */
export const GGW_COLLAPSED_KEY = 'ggw.collapsed';
const SECTION_KEY_RE = /^[A-Za-z0-9_-]{1,40}$/;
export function parseGgwCollapsed(v: unknown): string[] {
  if (typeof v !== 'string') return [];
  let a: unknown;
  try { a = JSON.parse(v); } catch { return []; }
  if (!Array.isArray(a)) return [];
  const out: string[] = [];
  for (const k of a) if (typeof k === 'string' && SECTION_KEY_RE.test(k) && !out.includes(k)) out.push(k);
  return out;
}
export function readGgwCollapsed(): string[] {
  try { return parseGgwCollapsed(window.localStorage.getItem(GGW_COLLAPSED_KEY)); } catch { return []; }
}
export function saveGgwCollapsed(keys: ReadonlyArray<string>): void {
  try {
    if (keys.length) window.localStorage.setItem(GGW_COLLAPSED_KEY, JSON.stringify(keys));
    else window.localStorage.removeItem(GGW_COLLAPSED_KEY);
  } catch { /* private window: the fold lasts this visit */ }
}
/** Fold / unfold one served section key (a new list; the key added or removed). */
export function ggwToggleCollapsed(keys: ReadonlyArray<string>, key: string): string[] {
  return keys.includes(key) ? keys.filter((k) => k !== key) : [...keys, key];
}
/** [C5] A push link / ➕ / first-load outline / pager tap into a FOLDED section opens that section first: the list without
 *  `sym`'s group. The SAME array when nothing changes (the name is not listed, has no group, or its group is open). */
export function ggwRevealGroup(keys: ReadonlyArray<string>, rows: ReadonlyArray<{ symbol: string; org?: GgwOrg | null }>,
                               sym: string): ReadonlyArray<string> {
  const g = rows.find((r) => r.symbol === sym)?.org?.group;
  return g && keys.includes(g) ? keys.filter((k) => k !== g) : keys;
}

/** The 1-min frame on top, then the rest in served order (5-min, 15-min since 2026-11-23; an older payload's own order). */
export function ggwSplitFrames(frames: ReadonlyArray<GgwFrame>): { top: GgwFrame | null; pair: GgwFrame[] } {
  const top = frames.find((f) => f.tf === '1m') ?? null;
  return { top, pair: frames.filter((f) => f !== top) };
}

/** ⤢ The full-screen order, top to bottom (Ajay 2026-11-16: "I wanna see all 3 of one stock for stretch like 5, 3 and
 *  1"): big → small, each full width and the same height; a frame not named here follows in served order.
 *  2026-11-23 (Ajay: "So 1 min, 5 and 15 accross board"): 15-min, 5-min, 1-min — the 🚩 card view's order
 *  (lib/gajjalaCardView.GGC_STRETCH_ORDER; a test pins equality). HIS CALL #6 (he listed 1 / 5 / 15).
 *  2026-11-16 (ggcard3): `order` = another surface's order; absent → this Watch order. */
export const GGW_STRETCH_ORDER = ['15m', '5m', '1m'] as const;
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
  return (GGW_CHART_H as Record<string, number>)[tf] ?? GGW_CHART_H['5m'];
}

/** 📈📐 2026-11-23 (vwapzones §3.9 [C9]): one legend entry's swatch — the look the chart draws for that tone: the bold 9 / 21
 *  EMA (lib/chartMaps EMA_BOLD), the VWAP line (toneColor('vwap') at VWAP_LINE_W), the daily zones as a DASHED OUTLINE box in
 *  the tone's colour (the board-band look — never a fill). Any other tone → the plain swatch (no style), as before. */
export const GGW_ZONE_TONES: ReadonlyArray<string> = ['zone_demand', 'zone_supply'];
export function ggwLegendSwatch(tone: string): { cls: string; style: CSSProperties | undefined } {
  const ema = (EMA_BOLD as Record<string, { color: string; width: number }>)[tone];
  if (ema) return { cls: 'ggw-swatch', style: { background: ema.color, height: ema.width } };
  if (tone === 'vwap') return { cls: 'ggw-swatch', style: { background: toneColor('vwap'), height: VWAP_LINE_W } };
  if (GGW_ZONE_TONES.includes(tone)) {
    return { cls: 'ggw-swatch ggw-swatch--zone', style: { borderColor: toneColor(tone as CmLineTone) } };
  }
  return { cls: 'ggw-swatch', style: undefined };
}
