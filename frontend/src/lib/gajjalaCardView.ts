/* 🚩 Gajjala card → ⤢ three-chart view — the FE plumbing (2026-11-16, ggcard3 spec §3.2, WP-A).
 *
 * Ajay 2026-11-16: "Also when I click on a card from any of the Gajjala I would like us to open the 3 chart extension like
 * in the Watch list... Also put a SEPA page link for it separaetely on the card I I want to but default its 3 chart
 * extension with 1 min, 3 min and 5 mins" and then "Actually instead of 3 mins make it 15 mins timeframe".
 *
 * ONE read-only GET (backend chart_maps/gajjala/card_frames.py, route `/chart-maps/gajjala/frames/{symbol}`) serves the
 * three frames from the docs the 🚩 5-minute pass and the 1-minute loop already store. Each frame is the 👀 Watch's frame
 * block (lib/gajjalaWatch.parseFrame reads it) plus its own served stamp / stale flag / empty words. This module holds
 * the route, the order, the parser and the overlay of the OPEN card's plan (lines, bands, markers, plan line) onto the
 * served frames. The ONE FE sentence is GGC_FETCH_FAILED (the request itself failed — there is no payload to serve one).
 * UNMEASURED — a chart view is information, not an entry. */
import type { CmBand, CmLine, CmMarker } from './chartMaps';
import type { GgTile } from './gajjala';
import {
  GGW_LAYOUT_DEFAULT, ggwClampPage, ggwPageOf, parseFrame, parseGgwLayout, parseRowLevels, type GgwFrame, type GgwLayout,
  type GgwLevels, type GgwRow,
} from './gajjalaWatch';
import { videoLayers } from './videoLook';

/** The frames route base (== backend card_frames.API_BASE — a backend source-read test pins equality). */
export const GGC_PATH = '/chart-maps/gajjala/frames';
/** 🎾 2026-11-23 (rswatch §3.1 / §3.6): the frames GET's optional card param + its one value (== backend
 *  card_frames.CARD_PARAM / CARD_SQUEEZE — a backend source-read test pins equality). Absent → today's URL exactly. */
export const GGC_CARD_PARAM = 'card';
export const GGC_CARD_SQUEEZE = 'squeeze';
export const ggcPath = (sym: string, card?: string | null): string =>
  `${GGC_PATH}/${encodeURIComponent(sym.trim())}${card ? `?${GGC_CARD_PARAM}=${encodeURIComponent(card)}` : ''}`;
/** 🎾 The setups whose card draws as the 👀 Watch tile — the board's own 🎾 predicate (GajjalaBoard.tsx gg-wide rule). */
export const GGC_SQUEEZE_SETUPS: ReadonlyArray<string> = ['reversal_squeeze'];
type GgcSetupCard = { gajjala?: { setup?: unknown } | null } | null | undefined;
/** A 🎾 card (the 🎾 sub AND a 🧠 card of a 🎾 read) — asks the squeeze shape. NEVER what the tile switches on (the row is). */
export function ggcIsSqueeze(card: GgcSetupCard): boolean {
  const setup = card?.gajjala?.setup;
  return typeof setup === 'string' && GGC_SQUEEZE_SETUPS.includes(setup);
}
/** The card param this card's frames GET carries: GGC_CARD_SQUEEZE for a 🎾 card, else undefined (today's URL). */
export function ggcCardParam(card: GgcSetupCard): string | undefined {
  return ggcIsSqueeze(card) ? GGC_CARD_SQUEEZE : undefined;
}
/** His frames 1 / 5 / 15, stacked big → small top to bottom (the Watch's convention — HIS CALL #1). Since 2026-11-23 the
 *  👀 Watch's own GGW_STRETCH_ORDER is the same 15 / 5 / 1 (Ajay: "So 1 min, 5 and 15 accross board"; a test pins equality). */
export const GGC_STRETCH_ORDER = ['15m', '5m', '1m'] as const;
/** The ONE FE sentence (the GET itself failed — no payload to serve a reason). */
export const GGC_FETCH_FAILED = 'Could not load the three charts.';

export type GgcPayload = {
  state: 'ok'; symbol: string; session: string | null; is_today: boolean; in_window: boolean;
  as_of_et: string | null; stale: boolean; text: string | null; frames: GgwFrame[];
  /** 📐 2026-11-23 (vwapzones §3.7): the served daily-zones line (lib/gajjalaWatch.parseRowLevels). The key is set ONLY when
   *  served — a payload without it parses byte-identical to before. */
  levels?: GgwLevels | null;
  /** 🎾 2026-11-23 [C2]: the served ECHO. The key is set ONLY when the server sent exactly GGC_CARD_SQUEEZE — a payload
   *  without it (an older api, a plain GET) parses byte-identical to before. */
  card?: typeof GGC_CARD_SQUEEZE;
};
/** 🎾 2026-11-23 [C2]: a card-grid row; `card` is set ONLY on a row built from a payload that echoed the squeeze card. */
export type GgcRow = GgwRow & { card?: typeof GGC_CARD_SQUEEZE };
/** 🎾 [C2] The ONE test the tile switches on: this row came from a squeeze payload (never the card's setup alone). */
export const ggcRowSplit = (row: GgwRow | null | undefined): boolean => !!row && (row as GgcRow).card === GGC_CARD_SQUEEZE;
export type GgcError = { state: 'error'; reason: string | null };

const isObj = (v: unknown): v is Record<string, any> => !!v && typeof v === 'object' && !Array.isArray(v);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v : null);

/** The served answer, a served error (its reason verbatim), or null for junk (no symbol, no frames list, another state). */
export function parseGgc(raw: unknown): GgcPayload | GgcError | null {
  if (!isObj(raw)) return null;
  if (raw.state === 'error') return { state: 'error', reason: str(raw.reason) };
  if (raw.state !== 'ok' || !str(raw.symbol) || !Array.isArray(raw.frames)) return null;
  const symbol = raw.symbol as string;
  return {
    state: 'ok',
    symbol,
    session: str(raw.session),
    is_today: raw.is_today === true,
    in_window: raw.in_window === true,
    as_of_et: str(raw.as_of_et),
    stale: raw.stale === true,
    text: str(raw.text),
    frames: raw.frames.map((f: unknown) => parseFrame(f, symbol)).filter((f: GgwFrame | null): f is GgwFrame => !!f),
    ...('levels' in raw ? { levels: parseRowLevels(raw.levels) } : {}),
    ...(raw.card === GGC_CARD_SQUEEZE ? { card: GGC_CARD_SQUEEZE } : {}),
  };
}

/** 📐 2026-11-23: a SERVED context band (the daily zones — `ctx: true`): drawn where it falls, never the card's overlay. */
export function ggcIsCtx(b: unknown): b is CmBand {
  return !!b && typeof b === 'object' && (b as { ctx?: unknown }).ctx === true;
}

/** The card's plan on the served frames: `lines` + `bands` of the card on EVERY frame (prices, frame-free); `markers`
 *  ONLY on the frame whose tf === card.tf (PatternChart maps them by date — a mark outside the frame's bars drops). The
 *  head line = the served `text` (no bars at all), else the card's served plan line, else none.
 *  📺 2026-11-17 (video view spec §3.4, his call #4): `look === 'video'` strips the overlay through the SAME
 *  lib/videoLook.videoLayers the cards use — no 🧪 band, no ➖ diamonds; BUY / STOP / now + the A+ tag kept. `look`
 *  absent → the card's own `lines` / `bands` / `markers` references, byte-identical to before.
 *  👀 2026-11-18 (card grid in the Watch layout, spec cardview §3.1): `opts` absent → byte-identical to the 11-17 row (the ⤢
 *  view passes none). `opts.plan === false` → the head text is the served `text` ONLY (the no-bars words): on the board
 *  tile the plan prints once, in the card's own CardExtras below.
 *  📐 2026-11-23 (vwapzones §3.9): the frame's SERVED `ctx` bands (the daily zones) are KEPT under both looks, drawn first
 *  (the card's own bands on top): `videoLayers` strips only the CARD's overlay. No served `ctx` band → the card's `bands`
 *  reference exactly as before. A served `levels` reaches the row (key set only when served). The 15 / 5 / 1 order is
 *  GGC_STRETCH_ORDER (unchanged). */
export function ggcRow(card: GgTile, p: GgcPayload, look?: 'video', opts?: { plan?: boolean; squeeze?: boolean }): GgcRow {
  const src = look === 'video' ? videoLayers(card) : card;
  const lines = Array.isArray(src.lines) ? src.lines : [];
  const bands = Array.isArray(src.bands) ? src.bands : [];
  const markers = Array.isArray(src.markers) ? src.markers : [];
  /* 🎾 2026-11-23 [C2]: the split needs the caller's word AND the served echo — a payload without it (an older api, a
   * plain load) takes today's path below, object for object. */
  const sq = opts?.squeeze === true && p.card === GGC_CARD_SQUEEZE;
  if (sq) return ggcSqueezeRow(card, p, lines, bands, markers, opts);
  return {
    symbol: p.symbol,
    state: p.text ? 'no_bars' : 'ok',
    text: p.text ?? (opts?.plan === false ? null : card.gajjala?.plan_text ?? null),
    from_session: p.is_today ? null : p.session,
    as_of_et: p.as_of_et,
    stale: p.stale,
    frames: p.frames.map((f) => {
      const ctx = Array.isArray(f.tile.bands) ? f.tile.bands.filter(ggcIsCtx) : [];
      return {
        ...f,
        tile: {
          ...f.tile, lines, bands: ctx.length ? [...ctx, ...bands] : bands,
          markers: card.tf != null && f.tf === card.tf ? markers : [],
        },
      };
    }),
    rang: [],
    ...(p.levels !== undefined ? { levels: p.levels } : {}),
  };
}

/* 🎾 2026-11-23 (rswatch §3.6). Ajay: "In the reversal squeeze can you make the charts same as in watch list please".
 * A squeeze payload (it echoed `card: "squeeze"`) → the row the Watch Tile's own split branch draws: the SERVED frame order
 * (1m, 5m, 15m), the served 9/21 cross diamonds kept on every frame under BOTH looks (a frame layer, not the card's
 * overlay), the card's lines on every frame (his tick 1), the card's own markers minus its cross kinds (never doubled) and
 * the card's RAW `ellipses` (his tick 2 — read off the card, never through videoLayers) on the frame of `card.tf` only.
 * Every frame-level key (uptrend, ema_cross, axis, …) passes through. Display only. UNMEASURED. */
const GGC_CROSS_KINDS: ReadonlySet<string> = new Set(['ema_cross_up', 'ema_cross_dn']);
function ggcSqueezeRow(card: GgTile, p: GgcPayload, lines: CmLine[], bands: CmBand[], markers: CmMarker[],
                       opts: { plan?: boolean } | undefined): GgcRow {
  const own = markers.filter((m) => !(m && GGC_CROSS_KINDS.has(String(m.kind))));
  const ellipses = Array.isArray(card.ellipses) && card.ellipses.length ? card.ellipses : null;
  return {
    symbol: p.symbol,
    state: p.text ? 'no_bars' : 'ok',
    text: p.text ?? (opts?.plan === false ? null : card.gajjala?.plan_text ?? null),
    from_session: p.is_today ? null : p.session,
    as_of_et: p.as_of_et,
    stale: p.stale,
    frames: p.frames.map((f) => {
      const ctx = Array.isArray(f.tile.bands) ? f.tile.bands.filter(ggcIsCtx) : [];
      const served = Array.isArray(f.tile.markers) ? f.tile.markers : [];
      const mine = card.tf != null && f.tf === card.tf;
      return {
        ...f,
        tile: {
          ...f.tile, lines, bands: ctx.length ? [...ctx, ...bands] : bands,
          markers: mine ? [...served, ...own] : served,
          ...(mine && ellipses ? { ellipses } : {}),
        },
      };
    }),
    rang: [],
    ...(p.levels !== undefined ? { levels: p.levels } : {}),
    card: GGC_CARD_SQUEEZE,
  };
}

/* 👀 2026-11-18 — the card grid in the Watch layout (spec cardview §3.1, WP-B). Ajay 2026-11-18: "I need the watch list
 * kinda chart formant view video view as default here too from the tabs pages" → his pick "Tab cards as Watch tiles": the
 * 🚩 / 🧪 card grid draws as the 👀 Watch does (big tiles, 2 per screen side by side, live 15 / 5 / 1-min stacked charts).
 * Display only — no rule, gate, ring, order or count changes. UNMEASURED. */

/** The per-device mode. His word: default. Stored '1' = ON, '0' = OFF; absent or a blocked store = the default (ON); ANY
 *  other value = OFF (the 📺 GG_LOOK_LS rule). Per viewer, per device. Display only. */
export const GGC_WATCH_LS = 'gg-card-watch';
export const GGC_WATCH_DEFAULT_ON = true;
export function loadGgcWatch(): boolean {
  try {
    const v = window.localStorage.getItem(GGC_WATCH_LS);
    return v === null || v === undefined ? GGC_WATCH_DEFAULT_ON : v === '1';
  } catch {
    return GGC_WATCH_DEFAULT_ON;
  }
}
export function saveGgcWatch(on: boolean): void {
  try { window.localStorage.setItem(GGC_WATCH_LS, on ? '1' : '0'); } catch { /* private window: the choice lasts this visit */ }
}
/** The boards that draw the Watch layout — == lib/gajjala.GG_VIDEO_LOOK_VKEYS (a test pins equality); never gajjala_1m / luk. */
export const GGC_WATCH_VKEYS: ReadonlyArray<string> = ['gajjala', 'gajjala_audited'];
/** This browser's per-screen pick for the CARD grid (its own key — the 👀 Watch keeps ggw.layout). Same parser / default. */
export const GGC_LAYOUT_KEY = 'ggc.layout';
export function readGgcLayout(): GgwLayout {
  try { return parseGgwLayout(window.localStorage.getItem(GGC_LAYOUT_KEY)); } catch { return GGW_LAYOUT_DEFAULT; }
}
export function saveGgcLayout(l: GgwLayout): void {
  try { window.localStorage.setItem(GGC_LAYOUT_KEY, String(l)); } catch { /* private window: the pick lasts this visit */ }
}
/** The control's label + hover (FE control words, the 📺 precedent — never a sentence about a stock). */
export const GGC_WATCH_LABEL = '👀 Watch layout';
export const GGC_WATCH_TITLE = 'Draw the cards as the 👀 Watch does: big tiles, 2 per screen side by side (1 · 2 · 4 · 9 to pick), each with the live 15-min, 5-min and 1-min charts and the card\'s own trigger, stop, plan, tags and chips. ◀ ▶ and the tickers move the view; ⤢ opens one stock full screen. Order, filters, counts and the 🏁 Track record are unchanged. Display only — no rule, alert or ring changes. Tap to go back to the small cards.';
/** The floor of one stacked chart in a fitted card tile (CSS px) — MINE (layout), HIS CALL to move. Below it the row
 *  grows and the page scrolls instead of the chart shrinking further. */
export const GGC_FRAME_MIN_PX = 160;
/** The frame-less part of a row (a served error, a failed GET, a load still out) — ONE definition, GgCardView reuses it. */
export const GGC_NO_FRAMES: Pick<GgwRow, 'from_session' | 'as_of_et' | 'stale' | 'frames' | 'rang'> = {
  from_session: null, as_of_et: null, stale: false, frames: [], rang: [],
};
/** The shown symbol set of a paged / picked list (pure; the Watch's onPage inlined): `size` = Infinity → all; a pick
 *  (filtered to the list) that is non-empty → the pick; else the names on the (clamped) page. */
export function ggcShown(symbols: ReadonlyArray<string>, page: number, size: number,
                         pick: ReadonlyArray<string> | null): Set<string> {
  if (!Number.isFinite(size)) return new Set(symbols);
  const picked = pick ? pick.filter((s) => symbols.includes(s)) : [];
  if (picked.length) return new Set(picked);
  const n = symbols.length;
  const cur = ggwClampPage(page, n, size);
  return new Set(symbols.filter((_, i) => ggwPageOf(i, size) === cur));
}
