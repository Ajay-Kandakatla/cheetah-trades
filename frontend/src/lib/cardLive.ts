/* Live card overlay (2026-10-16) — the pure half of the Chart Maps card poll.
 *
 * Ajay 2026-10-16: "Can you make this chart more live please like when its 24
 * hour or todays entry" / "actual price is this  above but it stale value".
 *
 * POST /chart-maps/live (backend/chart_maps/live_card.py) answers, per symbol,
 * the card's today bar and the now-line price + label, composed on the backend
 * by the board's own helpers. This file only SPLICES that answer into the
 * board's tiles: it replaces the last bar, appends the first bar of a new
 * session, and moves the tone-`now` lines. It composes no words and computes
 * no price — every label and every number it writes is a served one.
 */
import type { CmBar, CmLine, CmTapeSession, CmTile } from './chartMaps';

export const CARD_LIVE_MS = 30_000;             // MINE — matches SessionPrice's 30 s poll (K1; HIS CALL Q1)
export const CARD_LIVE_CLOSED_MS = 30 * 60_000; // Cheetah default — = drop10_tab.CLOSED_TTL_SEC (HIS CALL Q5)
export const CARD_LIVE_PATH = '/chart-maps/live';

export type CardLiveNow = {
  price: number; label: string; session: 'premarket' | 'afterhours' | null;
  add_line: boolean; as_of_epoch: number | null; as_of: string | null;
};
/** 🔴 The served live-vs-levels words (2026-10-21, BUILD_SPEC20 D2): where the live print sits against the
 *  trigger / stop the tile already carries — chart_maps/live_card.VS_TEXT composes `text`; the FE prints it verbatim
 *  and types none of it. Absent = kind "none" (no now price, no levels, an unparsable level). Display only. */
export type CardLiveVs = { kind: string; text: string };
/** The optional `levels` body (BUILD_SPEC20 D2): per symbol, the numbers the tab already served — copied, never typed. */
export type CardLiveLevel = { trigger: number | null; stop: number | null; tf: string | number | null };
export type CardLiveLevels = Record<string, CardLiveLevel>;
/** A tile the live answer may carry served `vs` words on (patchTile copies `q.vs` here). */
export type LiveVsTile = { live_vs?: CardLiveVs };

/** `prev_bar` (AMENDMENTS8 C4): the closed frame's bar BEFORE `bar`, served as
 *  a closed bar (no `s` tag). On a new-session append it replaces the card's
 *  last bar first, so yesterday's extended-hours shading does not carry over. */
export type CardLiveQuote = {
  bar: CmBar | null; prev_t: string | null; prev_bar?: CmBar | null; now: CardLiveNow | null;
  /** 🔴 2026-10-21: present only when the request carried `levels` for this symbol and the print sits somewhere. */
  vs?: CardLiveVs | null;
};
export type CardLiveAnswer = {
  session: CmTapeSession | null; as_of_epoch: number; as_of: string;
  footer: { live: string | null; stale: string | null }; now_labels: string[]; cap: number; asked: number;
  served: number; missing: string[]; fault: string | null; quotes: Record<string, CardLiveQuote>;
};

const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;

const isObj = (x: unknown): x is Record<string, unknown> =>
  typeof x === 'object' && x !== null && !Array.isArray(x);

const pos = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x) && x > 0;

/** The live answer, or null for anything that is not one (a board payload, an
 *  error body, a half shape). */
export function parseCardLive(j: unknown): CardLiveAnswer | null {
  if (!isObj(j)) return null;
  if (!isObj(j.quotes) || !isObj(j.footer)) return null;
  if (!Array.isArray(j.now_labels) || !j.now_labels.every((s) => typeof s === 'string')) return null;
  return j as unknown as CardLiveAnswer;
}

/** The tickers of the tiles on screen: trimmed, upper-cased, de-duplicated,
 *  sorted — so the request body (and the hook's key) is stable per board. */
export function cardLiveSymbols(tiles: { symbol?: string }[] | null | undefined): string[] {
  const seen = new Set<string>();
  for (const t of tiles || []) {
    const s = typeof t?.symbol === 'string' ? t.symbol.trim().toUpperCase() : '';
    if (s) seen.add(s);
  }
  return Array.from(seen).sort();
}

/** The poll cadence for a served session: the closed-hours read is slow. */
export function nextCadence(session: CmTapeSession | null | undefined): number {
  return session === 'closed' ? CARD_LIVE_CLOSED_MS : CARD_LIVE_MS;
}

/** A served bar the card may draw: a pure date, positive finite OHLC, a finite
 *  non-negative volume, and no shading tag other than the board's two. */
function validBar(b: unknown): b is CmBar {
  if (!isObj(b)) return false;
  if (typeof b.t !== 'string' || !DAY_RE.test(b.t)) return false;
  if (!pos(b.o) || !pos(b.h) || !pos(b.l) || !pos(b.c)) return false;
  if (typeof b.v !== 'number' || !Number.isFinite(b.v) || b.v < 0) return false;
  if ('s' in b && b.s !== 'pre' && b.s !== 'ah') return false;
  return true;
}

function sameBar(a: CmBar, b: CmBar): boolean {
  return a.t === b.t && a.o === b.o && a.h === b.h && a.l === b.l && a.c === b.c && a.v === b.v && a.s === b.s;
}

function validNow(n: unknown): n is CardLiveNow {
  return isObj(n) && pos(n.price) && typeof n.label === 'string' && n.label.length > 0;
}

function patchBars(bars: CmBar[], q: CardLiveQuote): CmBar[] {
  const bar = q.bar;
  if (!validBar(bar) || !bars.length) return bars;
  const last = bars[bars.length - 1];
  if (!last || typeof last.t !== 'string' || !DAY_RE.test(last.t)) return bars;  // intraday tiles never patch
  if (bar.t === last.t) {
    return sameBar(last, bar) ? bars : [...bars.slice(0, -1), bar];
  }
  if (bar.t > last.t && q.prev_t === last.t) {
    /* The first print of a new session: append, never drop the first bar —
     * curves and vol_avg are aligned to bars by index. C4: the served closed
     * prior bar replaces the card's last bar first when it is that same day. */
    const prev = q.prev_bar;
    if (validBar(prev) && prev.t === last.t && !sameBar(last, prev)) {
      return [...bars.slice(0, -1), prev, bar];
    }
    return [...bars, bar];
  }
  return bars;  // older, or the tile ends on another session (a Winners window)
}

function patchLines(lines: CmLine[], now: CardLiveNow | null, nowLabels: readonly string[]): CmLine[] {
  if (!validNow(now)) return lines;
  let changed = false;
  let hasNow = false;
  const out = lines.map((l) => {
    if (l.tone !== 'now') return l;
    hasNow = true;
    const label = nowLabels.includes(l.label) ? now.label : l.label;  // custom wording kept
    if (l.price === now.price && l.label === label) return l;
    changed = true;
    return { ...l, price: now.price, label };
  });
  if (!hasNow && now.add_line) {
    return [...lines, { price: now.price, label: now.label, tone: 'now' }];
  }
  return changed ? out : lines;
}

function validVs(v: unknown): v is CardLiveVs {
  return isObj(v) && typeof v.kind === 'string' && v.kind.length > 0 && typeof v.text === 'string' && v.text.trim().length > 0;
}

/** One tile with the served quote spliced in; the SAME tile when nothing moved. 🔴 2026-10-21: the served `q.vs`
 *  rides along as `live_vs` (the served object as is — absent or invalid → no `live_vs`). */
export function patchTile<T extends CmTile>(t: T, q: CardLiveQuote | undefined, nowLabels: readonly string[]): T {
  if (!q) return t;
  const bars0 = Array.isArray(t.bars) ? t.bars : [];
  const lines0 = Array.isArray(t.lines) ? t.lines : [];
  const bars = patchBars(bars0, q);
  const lines = patchLines(lines0, q.now, nowLabels);
  const vs0 = (t as T & LiveVsTile).live_vs;
  const vs = validVs(q.vs) ? q.vs : undefined;
  const sameVs = vs0 === vs || (!!vs0 && !!vs && vs0.kind === vs.kind && vs0.text === vs.text);
  if (bars === bars0 && lines === lines0 && sameVs) return t;
  const out: T & LiveVsTile = { ...t, bars, lines };
  if (sameVs) return out;
  if (vs) out.live_vs = vs; else delete out.live_vs;
  return out;
}

/** Every tile patched with its quote; the SAME array when no tile changed. */
export function patchTiles<T extends CmTile>(tiles: T[], a: CardLiveAnswer | null): T[] {
  if (!a) return tiles;
  let changed = false;
  const out = tiles.map((t) => {
    const sym = typeof t?.symbol === 'string' ? t.symbol.trim().toUpperCase() : '';
    const q = sym && Object.prototype.hasOwnProperty.call(a.quotes, sym) ? a.quotes[sym] : undefined;
    const p = patchTile(t, q, a.now_labels);
    if (p !== t) changed = true;
    return p;
  });
  return changed ? out : tiles;
}

/** The served live-vs words on a patched tile, or null (nothing printed). */
export function liveVsText(t: unknown): string | null {
  const v = isObj(t) ? t.live_vs : undefined;
  return validVs(v) ? v.text : null;
}
