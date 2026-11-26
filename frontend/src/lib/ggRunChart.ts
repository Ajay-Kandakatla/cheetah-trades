/* 📅 Runners on one continuous chart — the pure lib (2026-11-26, spec runcharts rev 2 §3.6, package fe-chart).
 *
 * Ajay 2026-11-26: "I want you to have continous charts for previous day runners we have some examples with traderview
 * charts with couple of indicators can you set that up? I wanna able to horizontal scroll tp check continuity like he does"
 *
 * The server is the ONE engine (backend chart_maps/gajjala_watch/runchart.py): it picks the days, builds the bars, the
 * 9 / 21 EMA (the cards' engine, never restarted at a session), the volume average, the shading runs, the session
 * separators and EVERY word. This file parses the payload, shapes it for lightweight-charts, does the range and pixel
 * arithmetic of the overlay, and holds the open / closed store. It types no clock time and no sentence that a payload
 * carries. `time` on every series is the served `x`: the ET wall clock of the bar's START written as if UTC, so a
 * UTC-drawing chart prints ET with no timezone code here. Display only — nothing here rings, gates, sorts or adds a
 * name. UNMEASURED. */
import { useSyncExternalStore } from 'react';
import { pxText } from './chartMaps';
import { volumeColor } from './volumePane';
import { hoverRow, vol } from './zoneChart';

/** == backend `API_RUNCHART_PATH` minus '/{symbol}' — the contract pins the equality. */
export const GG_RUNCHART_PATH = '/chart-maps/gajjala-watch/runners/chart';

/** Upper-cased, URI-encoded symbol; `?tf=` only when a frame is given (absent → the server's default frame). */
export const ggrcPath = (sym: string, tf?: string | null): string => {
  const s = encodeURIComponent(String(sym ?? '').trim().toUpperCase());
  const base = `${GG_RUNCHART_PATH}/${s}`;
  return typeof tf === 'string' && tf ? `${base}?tf=${encodeURIComponent(tf)}` : base;
};

/** A control's title (the tvTitle rule). */
export const ggrcOpenTitle = (sym: string): string => `${sym} — the last sessions on one chart`;

/** Typed only because no payload exists to serve one. */
export const GGRC_FETCH_FAILED = 'The chart could not be loaded.';
export const GGRC_LOADING = 'Loading…';
export const GGRC_CTRL = {
  prevDay: '◀ day', nextDay: 'day ▶', all: 'all', latest: 'latest', close: '✕',
  prevSym: '‹', nextSym: '›', hint: 'ⓘ', retry: '↻ try again',
} as const;
export const GGRC_KEY_PAN_FRAC = 0.25;         // DRAWING — ← → move a quarter of the screen
export const GGRC_MIN_BAR_SPACING = 0.2;       // DRAWING
export const GGRC_DEBOUNCE_MS = 250;           // TRANSPORT — a ‹ › step waits this long before it fetches (a name stepped past is never asked)
export const GGRC_BUSY_TRIES = 5;              // TRANSPORT — `busy` answers re-asked in a row before the chart stops and offers ↻
export const GGRC_Z = 5100;                    // above .ggw-stretch (5000)
export const GGRC_UP = '#22c55e';              // = LiveCandlesChart UP
export const GGRC_DOWN = '#ef4444';            // = LiveCandlesChart DOWN
export const GGRC_SHADE = 'rgba(148,163,184,0.13)';   // DRAWING — one grey for pre and after, his thinkorswim look
export const GGRC_SEP = 'rgba(148,163,184,0.55)';
export const GGRC_TEXT = '#94a3b8';            // DRAWING — the chart's axis text (= ZoneChart's textColor); the separators' date labels
export const GGRC_VWAP_COLOR = '#38bdf8';      // = the hex inside toneColor('vwap') (a test reads the source)

export type GgrcState = 'ok' | 'empty' | 'error' | 'busy' | 'off' | 'bad_symbol' | 'owner_only';   // == backend RUNCHART_STATES
const STATES: ReadonlyArray<GgrcState> = ['ok', 'empty', 'error', 'busy', 'off', 'bad_symbol', 'owner_only'];
export type GgrcBar = { t: string; x: number; o: number; h: number; l: number; c: number; v: number; s: 'pre' | 'ah' | null };
export type GgrcSession = { date: string; label: string; from: number; to: number; half_day: boolean; ran: boolean };
export type GgrcShade = { from: number; to: number; kind: 'pre' | 'ah' };
export type GgrcTone = 'ema9' | 'ema21' | 'vwap';
const TONES: ReadonlyArray<GgrcTone> = ['ema9', 'ema21', 'vwap'];
export type GgrcCurve = { tone: GgrcTone; label: string; values: (number | null)[] };
export type GgrcNote = { kind: string; text: string };
export type GgrcView = { sessions: number; sessions_phone: number; right_gap_bars: number };
export type GgrcPayload = {
  state: GgrcState; symbol: string | null; tf: string | null; frame_min: number | null;
  frames: { key: string; label: string }[]; title: string | null; text: string | null; notes: GgrcNote[];
  as_of_text: string | null; live: boolean; refresh_sec: number; retry_sec: number; hint: string | null;
  words: { pre: string | null; ah: string | null; regular: string | null };
  ran: { date: string | null; text: string; title: string | null } | null;
  sessions: GgrcSession[]; bars: GgrcBar[]; curves: GgrcCurve[];
  vol_avg: { period: number; label: string; values: (number | null)[] } | null; shade: GgrcShade[];
  view: GgrcView;
};
export type GgrcRange = { from: number; to: number };
export type GgrcPoint = { time: number; value: number };
export type GgrcHud = {
  when: string; session: string | null;
  open: string | null; high: string | null; low: string | null; close: string | null;
  changePct: string | null; up: boolean; volume: string;
  ema9: string | null; ema21: string | null; vwap: string | null;
};

/* ── parse ─────────────────────────────────────────────────────────────── */

/** A non-finite number anywhere means the server's scrub failed — the whole payload is not trusted. */
class Junk extends Error {}

const str = (x: unknown): string | null => (typeof x === 'string' && x.trim() ? x : null);
const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);
const fin = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
const isIdx = (x: unknown, n: number): x is number => Number.isInteger(x) && (x as number) >= 0 && (x as number) < n;

/** Throws Junk on any number in the tree that is not finite. */
function scan(x: unknown, depth = 0): void {
  if (typeof x === 'number') { if (!Number.isFinite(x)) throw new Junk(); return; }
  if (depth > 8 || !x || typeof x !== 'object') return;
  if (Array.isArray(x)) { for (const v of x) scan(v, depth + 1); return; }
  for (const v of Object.values(x as Record<string, unknown>)) scan(v, depth + 1);
}

/** One bar or Junk: a string `t`, an integer `x`, finite o/h/l/c > 0, finite v ≥ 0. Dropping a bar would shift every
 *  index-aligned list, so ONE bad bar makes the whole payload untrusted. */
function parseBar(x: unknown): GgrcBar {
  if (!isObj(x)) throw new Junk();
  const { t, x: bx, o, h, l, c, v, s } = x;
  if (typeof t !== 'string' || !Number.isInteger(bx)) throw new Junk();
  for (const p of [o, h, l, c]) if (!fin(p) || p <= 0) throw new Junk();
  if (!fin(v) || v < 0) throw new Junk();
  return { t, x: bx as number, o: o as number, h: h as number, l: l as number, c: c as number, v,
           s: s === 'pre' || s === 'ah' ? s : null };
}

function parseValues(x: unknown, n: number): (number | null)[] | null {
  if (!Array.isArray(x) || x.length !== n) return null;
  const out: (number | null)[] = [];
  for (const v of x) {
    if (v === null || v === undefined) out.push(null);
    else if (fin(v)) out.push(v);
    else return null;
  }
  return out;
}

function parseCurve(x: unknown, n: number): GgrcCurve | null {
  if (!isObj(x)) return null;
  const tone = x.tone as GgrcTone;
  if (typeof x.tone !== 'string' || !TONES.includes(tone)) return null;
  const label = str(x.label);
  const values = parseValues(x.values, n);
  if (!label || !values) return null;
  return { tone, label, values };
}

function parseSession(x: unknown, n: number): GgrcSession | null {
  if (!isObj(x)) return null;
  const date = str(x.date), label = str(x.label);
  if (!date || !label || !isIdx(x.from, n) || !isIdx(x.to, n) || x.from > x.to) return null;
  return { date, label, from: x.from, to: x.to, half_day: x.half_day === true, ran: x.ran === true };
}

function parseShade(x: unknown, n: number): GgrcShade | null {
  if (!isObj(x)) return null;
  if (x.kind !== 'pre' && x.kind !== 'ah') return null;
  if (!isIdx(x.from, n) || !isIdx(x.to, n) || x.from > x.to) return null;
  return { from: x.from, to: x.to, kind: x.kind };
}

/** A view count: a whole number ≥ 0, else 0 (0 sessions → the caller fits the content). */
const viewN = (x: unknown): number => (Number.isInteger(x) && (x as number) >= 0 ? (x as number) : 0);

/** The served answer → the chart's payload, or null when it is not trusted (the `parseGgRunners` posture).
 *  Not an object / unknown `state` / a non-finite number anywhere / one invalid bar / `x` not strictly ascending /
 *  a negative or non-number `retry_sec` → null. A curve or `vol_avg` whose length ≠ the bars' → dropped; a session or
 *  shade entry with a bad index or `from > to` → dropped; an unknown tone → dropped. */
export function parseGgrc(raw: unknown): GgrcPayload | null {
  if (!isObj(raw)) return null;
  const state = raw.state as GgrcState;
  if (typeof raw.state !== 'string' || !STATES.includes(state)) return null;
  try {
    scan(raw);
    let retry = 0;
    if (raw.retry_sec !== undefined && raw.retry_sec !== null) {
      if (!fin(raw.retry_sec) || raw.retry_sec < 0) return null;
      retry = raw.retry_sec;
    }
    const bars = Array.isArray(raw.bars) ? raw.bars.map(parseBar) : [];
    for (let i = 1; i < bars.length; i += 1) if (bars[i].x <= bars[i - 1].x) return null;
    const n = bars.length;
    const curves = Array.isArray(raw.curves)
      ? raw.curves.map((c) => parseCurve(c, n)).filter((c): c is GgrcCurve => c !== null) : [];
    let volAvg: GgrcPayload['vol_avg'] = null;
    if (isObj(raw.vol_avg)) {
      const values = parseValues(raw.vol_avg.values, n);
      const label = str(raw.vol_avg.label);
      const period = raw.vol_avg.period;
      if (values && label && fin(period)) volAvg = { period, label, values };
    }
    const sessions = Array.isArray(raw.sessions)
      ? raw.sessions.map((s) => parseSession(s, n)).filter((s): s is GgrcSession => s !== null) : [];
    const shade = Array.isArray(raw.shade)
      ? raw.shade.map((s) => parseShade(s, n)).filter((s): s is GgrcShade => s !== null) : [];
    const frames = Array.isArray(raw.frames)
      ? raw.frames.filter(isObj).map((f) => ({ key: str(f.key), label: str(f.label) }))
        .filter((f): f is { key: string; label: string } => !!f.key && !!f.label) : [];
    const notes = Array.isArray(raw.notes)
      ? raw.notes.filter(isObj).map((x) => ({ kind: str(x.kind), text: str(x.text) }))
        .filter((x): x is GgrcNote => !!x.kind && !!x.text) : [];
    const words = isObj(raw.words) ? raw.words : {};
    const ranText = isObj(raw.ran) ? str(raw.ran.text) : null;
    const ran = isObj(raw.ran) && ranText ? { date: str(raw.ran.date), text: ranText, title: str(raw.ran.title) } : null;
    const view = isObj(raw.view) ? raw.view : {};
    return {
      state,
      symbol: str(raw.symbol), tf: str(raw.tf), frame_min: fin(raw.frame_min) ? raw.frame_min : null,
      frames, title: str(raw.title), text: str(raw.text), notes,
      as_of_text: str(raw.as_of_text), live: raw.live === true,
      refresh_sec: fin(raw.refresh_sec) && raw.refresh_sec > 0 ? raw.refresh_sec : 0,
      retry_sec: retry, hint: str(raw.hint),
      words: { pre: str(words.pre), ah: str(words.ah), regular: str(words.regular) },
      ran, sessions, bars, curves, vol_avg: volAvg, shade,
      view: { sessions: viewN(view.sessions), sessions_phone: viewN(view.sessions_phone),
              right_gap_bars: viewN(view.right_gap_bars) },
    };
  } catch (e) {
    if (e instanceof Junk) return null;
    throw e;
  }
}

/* ── shaping for lightweight-charts (time = bar.x, seconds) ────────────── */

export function ggrcCandles(p: GgrcPayload): { time: number; open: number; high: number; low: number; close: number }[] {
  return p.bars.map((b) => ({ time: b.x, open: b.o, high: b.h, low: b.l, close: b.c }));
}

export function ggrcVolume(p: GgrcPayload): { time: number; value: number; color?: string }[] {
  return p.bars.map((b) => {
    const color = volumeColor(b.o, b.c);
    return color ? { time: b.x, value: b.v, color } : { time: b.x, value: b.v };
  });
}

function points(p: GgrcPayload, values: (number | null)[], from = 0, to = p.bars.length - 1): GgrcPoint[] {
  const out: GgrcPoint[] = [];
  for (let i = from; i <= to; i += 1) {
    const v = values[i];
    if (v !== null && v !== undefined) out.push({ time: p.bars[i].x, value: v });
  }
  return out;
}

/** The served curve of that tone, nulls omitted (the warm-up is a gap, never a guess). Absent → []. */
export function ggrcLine(p: GgrcPayload, tone: GgrcTone): GgrcPoint[] {
  const c = p.curves.find((k) => k.tone === tone);
  return c ? points(p, c.values) : [];
}

/** ONE array per session that holds a VWAP value — never joined across the overnight (the VWAP restarts each session). */
export function ggrcVwapSegments(p: GgrcPayload): GgrcPoint[][] {
  const c = p.curves.find((k) => k.tone === 'vwap');
  if (!c) return [];
  return p.sessions.map((s) => points(p, c.values, s.from, s.to)).filter((seg) => seg.length > 0);
}

export function ggrcVolAvg(p: GgrcPayload): GgrcPoint[] {
  return p.vol_avg ? points(p, p.vol_avg.values) : [];
}

/** pxText's rule: |p| < 1 → 3 decimals, else 2. */
export function ggrcPrecision(px: number | null): { precision: number; minMove: number } {
  const t = pxText(px);
  const precision = t && t.includes('.') ? t.split('.')[1].length : 2;
  return { precision, minMove: Number((10 ** -precision).toFixed(precision)) };
}

/* ── ranges (logical = bar index) ──────────────────────────────────────── */

/** The served last `view.sessions` (phone: `view.sessions_phone`) sessions on screen, plus the served right gap.
 *  No session (or a view of 0) → null: the caller fits the content. */
export function ggrcInitialRange(p: GgrcPayload, phone: boolean): GgrcRange | null {
  const k = phone ? p.view.sessions_phone : p.view.sessions;
  if (!p.sessions.length || !(k > 0)) return null;
  const s = p.sessions[Math.max(0, p.sessions.length - k)];
  return { from: s.from - 0.5, to: p.bars.length - 1 + p.view.right_gap_bars };
}

/** After a refresh: when the newest bar was in view, both ends follow the new bars; else his range stays. */
export function ggrcKeepRange(prev: GgrcRange | null, oldLen: number, newLen: number): GgrcRange | null {
  if (!prev) return null;
  if (prev.to >= oldLen - 1) {
    const d = newLen - oldLen;
    return { from: prev.from + d, to: prev.to + d };
  }
  return prev;
}

/** Both ends moved by dir × frac × the visible width. */
export function ggrcPan(range: GgrcRange, dir: -1 | 1, frac: number = GGRC_KEY_PAN_FRAC): GgrcRange {
  const d = dir * frac * (range.to - range.from);
  return { from: range.from + d, to: range.to + d };
}

/** ◀ day / day ▶: the left edge jumps to the previous / next session's first bar, the width kept; none → unchanged. */
export function ggrcStepSession(range: GgrcRange, sessions: ReadonlyArray<GgrcSession>, dir: -1 | 1): GgrcRange {
  let hit: GgrcSession | null = null;
  if (dir < 0) {
    for (const s of sessions) if (s.from - 0.5 < range.from - 0.01) hit = s;
  } else {
    hit = sessions.find((s) => s.from - 0.5 > range.from + 0.01) ?? null;
  }
  if (!hit) return range;
  const w = range.to - range.from;
  const from = hit.from - 0.5;
  return { from, to: from + w };
}

/* ── geometry (pixels; toX = the time scale's logical → x) ─────────────── */

export type GgrcToX = (logical: number) => number | null;

/** One full-height rect per shade run, clipped to [0, width]; a null edge or a zero width → skipped. */
export function ggrcShadeRects(shade: ReadonlyArray<GgrcShade>, toX: GgrcToX, width: number):
  { x: number; w: number; kind: 'pre' | 'ah' }[] {
  const out: { x: number; w: number; kind: 'pre' | 'ah' }[] = [];
  for (const r of shade) {
    const x1 = toX(r.from - 0.5), x2 = toX(r.to + 0.5);
    if (x1 === null || x2 === null || !Number.isFinite(x1) || !Number.isFinite(x2)) continue;
    const a = Math.max(0, Math.min(x1, x2)), b = Math.min(width, Math.max(x1, x2));
    if (b - a <= 0) continue;
    out.push({ x: a, w: b - a, kind: r.kind });
  }
  return out;
}

/** Per visible session: its date label at its left edge (pinned at 0 for the session under the left edge, so the day
 *  on screen is always named) and a dashed line at its start — never for the first session, never off screen. */
export function ggrcSeparators(sessions: ReadonlyArray<GgrcSession>, toX: GgrcToX, width: number):
  { x: number; line: boolean; label: string }[] {
  const out: { x: number; line: boolean; label: string }[] = [];
  sessions.forEach((s, j) => {
    const xs = toX(s.from - 0.5), xe = toX(s.to + 0.5);
    if (xs === null || xe === null || !Number.isFinite(xs) || !Number.isFinite(xe)) return;
    if (xe <= 0 || xs >= width) return;
    out.push({ x: Math.max(xs, 0), line: j > 0 && xs >= 0 && xs <= width, label: s.label });
  });
  return out;
}

/* ── hover readout ─────────────────────────────────────────────────────── */

const two = (n: number): string => String(n).padStart(2, '0');

/** The readout of bar `i`: `when` = the session label · the bar's START (the clock the axis prints, read with UTC
 *  getters because `x` is the ET wall clock written as UTC); `session` = the served word for its `s`; prices via
 *  pxText; volume via `vol`; the change against the PRIOR bar's close via hoverRow (none for the first bar). */
export function ggrcHover(p: GgrcPayload | null, i: number): GgrcHud | null {
  if (!p || !Number.isInteger(i) || i < 0 || i >= p.bars.length) return null;
  const b = p.bars[i];
  const d = new Date(b.x * 1000);
  const hm = `${two(d.getUTCHours())}:${two(d.getUTCMinutes())}`;
  const sess = p.sessions.find((s) => s.from <= i && i <= s.to);
  const prev = i > 0 ? p.bars[i - 1].c : null;
  const row = hoverRow({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c }, b.v, prev);
  const at = (tone: GgrcTone): string | null => {
    const c = p.curves.find((k) => k.tone === tone);
    return c ? pxText(c.values[i]) : null;
  };
  return {
    when: sess ? `${sess.label} · ${hm}` : hm,
    session: b.s === 'pre' ? p.words.pre : b.s === 'ah' ? p.words.ah : p.words.regular,
    open: pxText(b.o), high: pxText(b.h), low: pxText(b.l), close: pxText(b.c),
    changePct: row ? row.changePct : null, up: row ? row.up : b.c >= b.o,
    volume: vol(b.v),
    ema9: at('ema9'), ema21: at('ema21'), vwap: at('vwap'),
  };
}

/** The re-ask delay of a `busy` answer, in ms; null = stop (not busy, `tries` used up, or no usable retry_sec). */
export function ggrcBusyDelayMs(p: GgrcPayload | null, tries: number): number | null {
  if (!p || p.state !== 'busy') return null;
  if (tries >= GGRC_BUSY_TRIES) return null;
  if (!(p.retry_sec > 0)) return null;
  return p.retry_sec * 1000;
}

/* ── the open store (module state + useSyncExternalStore, the lib/ggFold.ts pattern) ── */

export type GgrcOpen = { symbol: string; list: string[] } | null;

let current: GgrcOpen = null;
const listeners = new Set<() => void>();
const emit = () => { listeners.forEach((fn) => fn()); };
const subscribe = (fn: () => void) => { listeners.add(fn); return () => { listeners.delete(fn); }; };
const snap = (): GgrcOpen => current;

/** Open the chart on `symbol`; `list` is the ‹ › order (absent, or not holding the symbol → the symbol alone). */
export function openGgRunChart(symbol: string, list?: ReadonlyArray<string>): void {
  const sym = typeof symbol === 'string' ? symbol.trim() : '';
  if (!sym) return;
  const names = (list ?? []).filter((s): s is string => typeof s === 'string' && !!s.trim()).map((s) => s.trim());
  current = { symbol: sym, list: names.includes(sym) ? names : [sym] };
  emit();
}

export function closeGgRunChart(): void {
  if (current === null) return;
  current = null;
  emit();
}

/** Inside `list`, clamped at both ends (no wrap). */
export function stepGgRunChart(d: -1 | 1): void {
  if (!current) return;
  const i = current.list.indexOf(current.symbol);
  const j = Math.max(0, Math.min(current.list.length - 1, i + d));
  if (i < 0 || j === i) return;
  current = { symbol: current.list[j], list: current.list };
  emit();
}

export function useGgRunChartOpen(): GgrcOpen {
  return useSyncExternalStore(subscribe, snap, snap);
}
