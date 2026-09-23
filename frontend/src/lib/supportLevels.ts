/* supportLevels — pure helpers for the Chart Maps "Support Levels" tab.
 *
 * Ajay 2026-08-19: "a new feature where I can look at support levels on demand
 * … toggle a drop down to check montly vs 3 months vs 6 months demand zones …
 * I should be able to a search of all the Ticker I do today … I want look at
 * recent support levels as well."
 *
 * Backend: backend/chart_maps/support.py (GET /chart-maps/support). Everything
 * here is formatting and coercion, so the component stays dumb and the numbers
 * are testable.
 *
 * NOT advice, and NOT a book method — `price_zones` is a configured
 * price-structure read and says so in its own header.
 */
import type { BandStructureCoverage, CmTile } from './chartMaps';
import type { BandStructureStudy } from './bandStructure';

export type SupportWindow = { key: string; label: string; bars: number };

export type SupportLevel = {
  lo: number;
  hi: number;
  mid: number;
  /** The band's ORIGIN. A level that used to be overhead supply and now sits
   *  below price is support by polarity — a weaker claim than a floor that was
   *  bought four times, so it is shown rather than flattened away. */
  origin: 'demand' | 'supply';
  touches: number;
  strength: number;
  bars_since_test: number | null;
  oldest_touch_bars: number | null;
  recent: boolean;
  /** Price turned here more than once. A single-touch band is one swing
   *  low with synthetic width painted round it — and on a short zoom it is
   *  also the commonest, so it wins the nearest-first sort. Shown, but
   *  never presented as a floor. */
  tested: boolean;
  distance_pct: number | null;
  /** Overlay mode only — which zooms found this level, and how many agree.
   *  Agreement is the signal: a level only one window can see is usually an
   *  artifact of that window. */
  windows?: string[];
  agree?: number;
};

/** "Prices as of 2h ago · bars through Aug 26" — the honesty line under the
 *  chart. Each half renders independently; BOTH missing -> null (render
 *  nothing rather than fabricate — same rule as the boards' scan stamp). */
export function priceAsOf(asOf: number | null | undefined,
                          dataThrough: string | null | undefined,
                          nowMs: number): string | null {
  const parts: string[] = [];
  if (asOf != null && Number.isFinite(asOf) && asOf > 0) {
    const sec = Math.max(0, nowMs / 1000 - asOf);   // clock skew -> clamp, not lie
    const min = Math.round(sec / 60);
    const age = sec < 90 ? 'just now'
      : min < 90 ? `${min}m ago`
      : min < 36 * 60 ? `${Math.round(min / 60)}h ago`
      : `${Math.round(min / 1440)}d ago`;
    parts.push(`Prices fetched ${age}`);
  }
  if (dataThrough) {
    const d = new Date(`${dataThrough}T12:00:00Z`);
    if (!Number.isNaN(d.getTime())) {
      parts.push(`bars through ${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })}`);
    }
  }
  return parts.length ? parts.join(' · ') : null;
}

export type SupportPayload = {
  symbol: string;
  name?: string | null;
  window: string;
  window_label: string;
  windows: SupportWindow[];
  timeframe?: string;
  timeframe_label?: string;
  timeframes?: Timeframe[];
  timeframe_meta?: { bars?: number; source?: string; reason?: string | null;
    ext_hours?: boolean } | null;
  /** Live frame only: poll cadence + session state (Ajay 2026-09-02). */
  live?: { state: string; refresh_sec: number; as_of: string } | null;
  /** Live frame only: the overnight tape read against the levels. */
  overnight?: OvernightRead | null;
  atr?: number | null;
  fair_value_gaps?: TradeLevel[];
  opening_range?: { lo: number; hi: number; minutes: number; session: string } | null;
  trade_levels?: TradeLevel[];
  mood?: MoodRead;
  signal?: TradeSignal;
  smc?: SmcRead;
  trend_read?: {
    direction?: string; label?: string; why?: string[];
    ema20?: number | null; ema50?: number | null; mood_agrees?: boolean;
  } | null;
  overlay?: { drawn?: Record<string, number>; found?: Record<string, number> } | null;
  /** What the chart is ACTUALLY showing AND where the levels came from — one
   *  served sentence in two clauses, present on every frame since 2026-09-22.
   *  The page prints it verbatim and composes nothing of its own. */
  chart_span?: string;
  /** Set ONLY when an intraday frame's own window held no level and the
   *  levels shown are the DAILY read instead (Ajay 2026-09-22). Null
   *  everywhere else. `note` is the sentence the surface prints. */
  levels_fallback?: {
    from: string; from_bars: string; to: string; note: string;
  } | null;
  /** The level read's own scope as a NOUN PHRASE — "79 x 5-minute bars" on an
   *  own-bars intraday frame, "6 months" on a daily one or on the named
   *  fallback. The same string the stats row is labelled with, so the tables
   *  and the stats cannot name two different windows (2026-09-23). */
  levels_scope?: string;
  /** The BAR SIZE the levels were read at ("5-minute" / "daily"). The recency
   *  column counts BARS, so without this one 5-minute bar rendered as "tested
   *  yesterday" (2026-09-23). */
  levels_bar_label?: string;
  /** The frame's bar size, beside `timeframe_label`'s job name. */
  timeframe_bar_label?: string;
  /** The DAILY-derived band the alerts, the gate and the paper lanes use. It
   *  does not follow the chart — two readings, each labelled, never
   *  conflated. */
  board?: {
    demand?: { lo: number; hi: number; touches?: number | null;
               distance_pct?: number | null } | null;
    supply?: { lo: number; hi: number; touches?: number | null;
               distance_pct?: number | null } | null;
  } | null;
  zoom_applies?: boolean;
  /** How many ET SESSIONS the drawn intraday frame covers, served only when a
   *  short window actually trimmed it. Null on a daily frame and on an
   *  untrimmed intraday one. Counted by session DATE, never by bar count. */
  chart_sessions?: number | null;
  bullish_patterns?: {
    patterns?: BullishPattern[];
    stats_transfer?: boolean;
    out_of_range?: string[];
    note?: string | null;
  } | null;
  recent_bars: number;
  last_price?: number;
  bars_used?: number;
  /** Set when the frame could not cover the window asked for — a recent IPO.
   *  The label still says what was asked; this says what was read. */
  short_history?: { have: number; asked: number } | null;
  /** Freshness stamp (2026-08-26, after INTU's frozen partial bar read as a
   *  blown stop): `as_of` = epoch seconds the data left the PROVIDER (parquet
   *  mtime / deep-fetch time) — null when unprovable, never fabricated;
   *  `data_through` = ISO date of the newest bar in the frame. */
  as_of?: number | null;
  data_through?: string | null;
  tile?: CmTile;
  /* 🪜 BAND STRUCTURE (2026-09-16). `chart_maps/api.py::chart_maps_support`
   * attaches the read to `tile.band_structure` and serves its VERDICT beside
   * it. Both have to be typed here or the tab renders the chip — a read of
   * bands nobody has measured — with no banner saying so, which is how an
   * unmeasured ordering starts looking validated. There is no `sort` on this
   * tab: it answers one symbol, so there is nothing to order. */
  band_structure_kind?: string | null;
  band_structure_study?: BandStructureStudy | null;
  /* 🪜 COVERAGE (2026-09-16, critique J2). Served beside the read: the counts
   * and the one sentence to print when this name came back with NO read at
   * all. A name the $1B zone store has not warmed (BTBT, one of his positions)
   * drew a tile with no Bands line and NO REASON here, while the row boards —
   * which build the doc on demand — served the read for it the same day. The
   * sentence is the row boards' own, served, never typed in the component. */
  band_structure_coverage?: BandStructureCoverage | null;
  supports?: SupportLevel[];
  overhead?: SupportLevel[];
  standing_in?: SupportLevel | null;
  levels_capped?: boolean;
  /* The CHART-ONLY zooms (Ajay 2026-09-18, 1w/2w). Set only on those two
   * windows; the key names the window every NUMBER on the tab came from.
   * Absent/null on every other window and on any payload served before
   * 2026-09-18, so a stale response simply renders as it always did. */
  levels_window?: string | null;
  levels_window_label?: string | null;
  verdict?: { state?: string; entry_read?: string; label?: string } | null;
  params?: Record<string, number> | null;
  note?: string;
  disclaimer?: string;
  error?: string;
};

/** Shown before the first response lands so the dropdown is never empty.
 *  Mirrors backend SUPPORT_WINDOWS; the server's own list replaces it as soon
 *  as one arrives, so a change there does not need a frontend deploy. */
export const FALLBACK_WINDOWS: SupportWindow[] = [
  // Ajay 2026-09-18: "Also a weekly chart for the past week and 2 week inthe
  // charting time frames in all places" — short WINDOWS, not weekly candles
  // (declined). Bars are trading days, so a week is 5 sessions and two weeks
  // is 10; never 7 or 14. Chart-only: every number stays the 1-month read.
  { key: '1w', label: '1 week', bars: 5 },
  { key: '2w', label: '2 weeks', bars: 10 },
  { key: '1m', label: '1 month', bars: 21 },
  { key: '3m', label: '3 months', bars: 63 },
  { key: '6m', label: '6 months', bars: 126 },
  { key: '1y', label: '1 year', bars: 252 },
  // Ajay 2026-09-06: "add 2 years ... I do seem sometime we have bounces off
  // the 2 years as well; also add 3 years and then keep 5 years."
  { key: '2y', label: '2 years', bars: 504 },
  { key: '3y', label: '3 years', bars: 756 },
  { key: '5y', label: '5 years', bars: 1260 },
  // The overlay pseudo-window: every zoom at once, clustered by agreement.
  { key: 'all', label: 'All windows · overlay', bars: 0 },
];

/** Matches backend support.DEFAULT_WINDOW — 1 year since 2026-09-06 (Ajay:
 *  "make support default to 1 year on all the tabs? I think its safer and
 *  more accurate"); was 3m. */
export const DEFAULT_WINDOW = '1y';
/** The ticker page's Supply / Demand tab. It diverged once (Ajay 2026-09-02:
 *  "default supply demand to 6 months in that tab"); since 2026-09-06 it is
 *  the same 1 year as every other surface ("on all the tabs"). The constant
 *  stays so the page can diverge again on his word, in one place. */
export const SEPA_SUPPLY_WINDOW = '1y';

/** Coerce a `?window=` value against the list the server actually offers, so a
 *  key retired backend-side degrades to the default instead of 404ing. */
export function parseWindow(
  raw: string | null | undefined,
  offered: SupportWindow[] = FALLBACK_WINDOWS,
): string {
  const v = (raw || '').trim().toLowerCase();
  if (!v) return DEFAULT_WINDOW;
  return offered.some((w) => w.key === v) ? v : DEFAULT_WINDOW;
}

/** Coerce a typed ticker. Upper-cased and stripped of everything a US symbol
 *  cannot contain, so a pasted "$NVDA " or "nvda," still resolves. */
export function normalizeSymbol(raw: string | null | undefined): string {
  return (raw || '').toUpperCase().replace(/[^A-Z0-9.\-]/g, '').slice(0, 12);
}

export function supportQuery(
  p: { symbol: string; window: string; tf?: string },
): string {
  const q = new URLSearchParams({ symbol: normalizeSymbol(p.symbol) });
  if (p.window && p.window !== DEFAULT_WINDOW) q.set('window', p.window);
  // Omitted when daily so the URL of an untouched tab is unchanged — the
  // surface answered on daily bars before the timeframe dropdown existed.
  if (p.tf && p.tf !== DEFAULT_TF) q.set('tf', p.tf);
  return q.toString();
}

/* ── the chart control (Ajay 2026-08-29, collapsed 2026-09-22) ─────────────
 * > "Just simpliyfy this drop down. I wanna use this for entries during the
 * >  day and it been useless for that It does help with 6 months but when it
 * >  comes to daily charts and checking support levels for daily. at any
 * >  giving point This has been useless"
 *
 * SEVENTEEN entries in one list became FIVE. Two things were wrong with the
 * old control and only one of them was the length:
 *
 *  1. The options were named by BAR SIZE ("15 min", "5 min · live · pre/post
 *     market"), so picking one meant translating a resolution into the job he
 *     was doing. They are now named by the JOB, and the SPAN rides beside the
 *     name — his "why do I need the look at the drop down" complaint was that
 *     the span was only discoverable by trying an option.
 *  2. Several entries answered the same question at different resolutions.
 *
 * The span ladder did NOT die with them: it moved to its own "How far back"
 * control that renders ONLY on the daily frame, which is the one frame whose
 * span a zoom still changes (support.py trims an intraday chart only for the
 * 1w/2w windows, and reads every NUMBER off the frame's own budget either
 * way). Two controls that cannot contradict each other, because the second
 * one does not exist where it would be inert — which is the same guarantee
 * the 2026-08-29 merge bought, at five rows instead of seventeen.
 *
 * Mirrors backend supply_demand/timeframes.TIMEFRAMES. */
export type Timeframe = {
  key: string; label: string; span?: string;
  /** Bar size ("5-minute") and calendar span ("today only, from 04:00 ET"),
   *  served separately so a surface can print either. `span` is the two of
   *  them already joined BY THE SERVER — no surface builds that sentence. */
  bar_label?: string; window_label?: string;
  bars?: number;
  /** Extended-hours frame: pre/post-market prints are in its bars. Only the
   *  Support tab may draw one — every structure endpoint refuses them, so the
   *  zone-map picker filters them out (see STRUCTURE_TIMEFRAMES). */
  ext?: boolean;
};

/** Shown until the server's own list lands. Mirrors
 *  `tf_options(include_live=True)`; a change backend-side needs no FE deploy,
 *  this only has to be a truthful stand-in for the first paint. */
export const FALLBACK_TIMEFRAMES: Timeframe[] = [
  // Ajay 2026-09-22: "support level from market open but I do not have to see
  // previous days in that" — THIS is the frame that answers it.
  { key: '5m_today', label: 'Today, for an entry',
    bar_label: '5-minute', window_label: 'today only, from 04:00 ET',
    span: '5-minute bars · today only, from 04:00 ET', bars: 192, ext: true },
  // Ajay 2026-09-22: "can you add a 24 hour window for me on the supply demand
  // chart please ... I mainly need the support levels for the last 24 hours".
  // The only TIME-windowed frame: every other one is a bar-count budget, and a
  // bar count makes the span a function of liquidity (measured 2026-09-22, the
  // retired 5m_live drew 3 sessions of NVDA and 5 of PTGX under one label
  // claiming "~2.5 sessions").
  { key: '24h', label: 'Last 24 hours',
    bar_label: '5-minute',
    window_label: 'the 24 hours up to the last print, pre-market through after-hours',
    span: '5-minute bars · the 24 hours up to the last print, pre-market through after-hours',
    bars: 288, ext: true },
  { key: '15m', label: 'The last two weeks',
    bar_label: '15-minute', window_label: 'the last ~10 sessions',
    span: '15-minute bars · the last ~10 sessions', bars: 260 },
  { key: '60m', label: 'The last two months',
    bar_label: '1-hour', window_label: 'the last ~47 sessions',
    span: '1-hour bars · the last ~47 sessions', bars: 330 },
  // Ajay 2026-09-22: "It does help with 6 months". The daily frame is the only
  // one whose span the zoom still sets, so its span text says so rather than
  // asserting a number the zoom can contradict.
  { key: 'daily', label: 'The big picture',
    bar_label: 'daily',
    window_label: '1 year by default — the Zoom dropdown sets how far back',
    span: 'daily bars · 1 year by default — the Zoom dropdown sets how far back',
    bars: 252 },
];

/** The frames a STRUCTURE surface (the ticker Setup tab's zone map) may
 *  offer. `frame_for` refuses an extended-hours frame to every caller but the
 *  Support tab — a swing low made on 400 shares at 07:12 is not a level
 *  anyone defended — so offering one there would be a dropdown entry that
 *  errors. The server's own list already excludes them; this keeps the
 *  first-paint fallback honest too. */
export const STRUCTURE_TIMEFRAMES: Timeframe[] = FALLBACK_TIMEFRAMES.filter((t) => !t.ext);

export const DEFAULT_TF = 'daily';

/** RETIRED 2026-09-22, mirroring backend `timeframes.RETIRED`.
 *
 * NOT deleted: an old bookmark or a tab he left open still carries these
 * keys, and landing it on the default Daily chart without a word is exactly
 * the silent substitution this whole change is removing. Each one resolves to
 * the nearest SURVIVING frame and the page says that it did.
 *
 *  - `15m_open` -> `15m`. Its 26-bar session budget was too thin to cluster:
 *    measured 2026-09-22, PTGX and NVDA both returned NO support band on it.
 *    `5m_today` answers the same "today only, no previous days" question with
 *    192 bars, but the alias points at `15m` because that is the nearest key
 *    that resolves on EVERY surface — an extended-hours frame is refused by
 *    the structure endpoints, so an old `/zones?tf=15m_open` link would start
 *    erroring. (Backend chose the same target, for the same reason.)
 *  - `5m_live` -> `24h`. Same bar size, same pre/post policy, a span that is
 *    true for a thin name as well as a liquid one. */
export const RETIRED_TIMEFRAMES: Record<string, { to: string; was: string }> = {
  '15m_open': { to: '15m', was: '15 min · from the open' },
  '5m_live': { to: '24h', was: '5 min · live · pre/post market' },
};

/** Spellings a URL might carry, mirroring backend `timeframes._ALIAS`. The
 *  retired keys are folded in last so an old bookmark resolves. */
const TF_ALIAS: Record<string, string> = {
  '1d': 'daily', d: 'daily', day: 'daily', '1day': 'daily',
  '1h': '60m', h: '60m', hour: '60m', hourly: '60m', '60min': '60m',
  '15': '15m', '15min': '15m', m15: '15m',
  open: '15m', session: '15m', '15open': '15m',
  '5m': '24h', '5min': '24h', live: '24h', '5m_ext': '24h',
  '24': '24h', h24: '24h', '24hr': '24h', '24hour': '24h', last24: '24h',
  '5today': '5m_today', today: '5m_today', '5m_day': '5m_today',
  '5m_open': '5m_today', '5open': '5m_today',
  ...Object.fromEntries(Object.entries(RETIRED_TIMEFRAMES).map(([k, v]) => [k, v.to])),
};

/** Coerce a `?tf=` value against the list the server actually offers. A key
 *  that was retired resolves to its successor; anything unknown degrades to
 *  daily, which is what every surface answered before timeframes existed. */
export function parseTf(
  raw: string | null | undefined,
  offered: Timeframe[] = FALLBACK_TIMEFRAMES,
): string {
  const v = (raw || '').trim().toLowerCase();
  if (!v) return DEFAULT_TF;
  if (offered.some((t) => t.key === v)) return v;
  const aliased = TF_ALIAS[v];
  return aliased && offered.some((t) => t.key === aliased) ? aliased : DEFAULT_TF;
}

/** Non-null when `raw` names a frame that no longer exists but still
 *  resolves — the one case the page has to SAY something about, because the
 *  chart he gets is not the chart his link asked for. */
export function retiredTf(
  raw: string | null | undefined,
  offered: Timeframe[] = FALLBACK_TIMEFRAMES,
): { from: string; was: string; to: string } | null {
  const v = (raw || '').trim().toLowerCase();
  const hit = RETIRED_TIMEFRAMES[v];
  if (!hit || !offered.some((t) => t.key === hit.to)) return null;
  return { from: v, was: hit.was, to: hit.to };
}

/** The daily window an intraday frame pins.
 *
 *  The window never leaves the wire, because it still decides two DAILY reads
 *  that must not follow the chart: the `board` block (what the alerts and
 *  lanes use) and the named level fallback. It is simply no longer his to
 *  pick on a frame where nothing he can see would change. Values are the pins
 *  the merged control carried before 2026-09-22, so the wire is unchanged for
 *  every surviving frame (`24h` inherits `5m_live`'s 6m). */
export const FRAME_WINDOW: Record<string, string> = {
  '5m_today': '6m',
  '24h': '6m',
  '15m': '1m',
  '60m': '3m',
};

/* WHICH ZOOMS MEAN SOMETHING ON WHICH FRAME (2026-09-23).
 *
 * Collapsing the picker to five rows first took the zoom away from every frame
 * but daily. That quietly broke something he ASKED FOR on 2026-09-18 — "Can you
 * increase the bars on the weekly chart please?" -> 1 week of HOURLY bars — and
 * it broke it the exact way the contract guarding it warned about: "the backend
 * shipped first and the picker could not express the pair, so the feature never
 * reached him."
 *
 * So the zoom is per-FRAME, not daily-only. That is what makes five rows honest
 * rather than lossy: the 17-row list was frame x zoom flattened into one
 * control, and this is the same reach expressed as five rows plus a zoom that
 * offers only what the chosen frame can answer.
 *
 * It cannot be set to nonsense — the reason the two controls were merged on
 * 2026-08-29 ("1 month" + "15 min" meant nothing) — because a frame only ever
 * offers the windows its own bars can fill. The 5-minute frames define their
 * own window, so they offer none and the control does not render.
 */
export const FRAME_WINDOWS: Record<string, readonly string[]> = {
  daily: ['1w', '2w', '1m', '3m', '6m', '1y', '2y', '3y', '5y', 'all'],
  // 330 hourly bars is ~47 sessions, so anything past 3 months is bars it does
  // not have. 1w / 2w are the two he asked for.
  '60m': ['1w', '2w', '1m', '3m'],
  // 260 bars of 15 minutes is ~10 sessions — a fortnight, no further.
  '15m': ['1w', '2w', '1m'],
  // Fixed by definition: "today" and "the last 24 hours" are the window.
  '5m_today': [],
  '24h': [],
};

/** The zooms this frame can actually answer. Unknown frames get daily's list
 *  rather than an empty one, so a frame added later is never silently
 *  zoom-less. */
export function windowsForFrame(tf: string | null | undefined): readonly string[] {
  const t = parseTf(tf);
  return FRAME_WINDOWS[t] ?? FRAME_WINDOWS.daily;
}

/** The window to send with `tf`. A zoom he is already on is KEPT when the new
 *  frame can answer it — switching from daily-2y to hourly should not silently
 *  throw the zoom away and it must not send an hourly frame a 2-year window
 *  either. Otherwise the frame's own pin. */
export function windowForFrame(tf: string | null | undefined,
                               current: string | null | undefined): string {
  const t = parseTf(tf);
  const allowed = windowsForFrame(t);
  if (!allowed.length) return FRAME_WINDOW[t] || DEFAULT_WINDOW;
  const cur = parseWindow(current);
  if (allowed.includes(cur)) return cur;
  return (t === DEFAULT_TF ? DEFAULT_WINDOW : FRAME_WINDOW[t]) || DEFAULT_WINDOW;
}

/** True where a zoom changes what is drawn AND what is read. A control that
 *  does nothing is how "1 month" + "15 min" came to mean nothing (Ajay
 *  2026-08-29), so a frame with one window or none renders no control. */
export function zoomApplies(tf: string | null | undefined): boolean {
  return windowsForFrame(tf).length > 1;
}

/** The offered frame whose key this is, for naming it in a sentence. */
export function frameFor(tf: string | null | undefined,
                         offered: Timeframe[] = FALLBACK_TIMEFRAMES): Timeframe {
  const k = parseTf(tf, offered);
  return offered.find((t) => t.key === k)
    || offered.find((t) => t.key === DEFAULT_TF)
    || offered[0];
}

export type OvernightTouch = {
  side: 'support' | 'overhead'; lo: number; hi: number; at: string;
  low?: number; high?: number; held: boolean; broke: boolean;
};
export type OvernightRead = {
  bars: number; since?: string; rth_close?: number;
  low?: number; low_at?: string; high?: number; high_at?: string;
  last?: number; change_pct?: number | null;
  touches?: OvernightTouch[]; note?: string;
};

/** One line for the overnight read, in the words a trader would use. */
export function overnightLine(o: OvernightRead | null | undefined): string {
  if (!o) return '';
  if (!o.bars) return o.note || 'Nothing has printed since the last regular close.';
  const chg = o.change_pct == null ? '' : ` (${o.change_pct >= 0 ? '+' : ''}${o.change_pct.toFixed(2)}% vs the close)`;
  const head = `Overnight: low ${money(o.low)} at ${clock(o.low_at)}, high ${money(o.high)} at ${clock(o.high_at)}, last ${money(o.last)}${chg}.`;
  const t = (o.touches || []).map((x) => {
    const band = `${money(x.lo)}–${money(x.hi)}`;
    if (x.side === 'support') {
      return x.broke ? `broke support ${band}` : x.held ? `bounced off support ${band} at ${clock(x.at)} ✓` : `sitting in support ${band}`;
    }
    return x.broke ? `cleared overhead ${band}` : x.held ? `rejected at overhead ${band} at ${clock(x.at)}` : `sitting in overhead ${band}`;
  });
  return t.length ? `${head} ${t.join('; ')}.` : `${head} No level touched.`;
}

function clock(ts?: string): string {
  if (!ts) return '?';
  const m = ts.match(/(\d{2}):(\d{2})/);
  return m ? `${m[1]}:${m[2]}` : ts;
}

/** One band with the trade its geometry implies. */
export type TradeLevel = {
  kind?: string;
  lo?: number;
  hi?: number;
  source?: string;
  touches?: number | null;
  fill_pct?: number;
  trade?: {
    side?: string; entry?: number; stop?: number; target1?: number;
    target_basis?: string; rr?: number | null; risk_pct?: number;
    distance_pct?: number; buffer_basis?: string;
  } | null;
};

export type MoodRead = {
  score?: number;
  label?: string;
  components?: Record<string, number>;
  unavailable?: string[];
  rsi?: number;
  vwap?: number;
  bars?: number;
} | null;

export type TradeSignal = {
  action?: 'BUY' | 'SELL' | 'WAIT';
  mood?: number;
  mood_label?: string;
  reasons?: string[];
  blockers?: string[];
  level?: { lo?: number; hi?: number; where?: string; distance_pct?: number } | null;
  trade?: {
    entry?: number; stop?: number; target1?: number; rr?: number | null;
    risk_pct?: number; target_basis?: string;
  } | null;
  no_repaint?: boolean;
  /** False on a frame whose BUY/SELL is NOT written to the forward ledger
   *  (the two 5-minute frames — `_record_signal` has no horizon for them).
   *  Undefined on a payload served before 2026-09-23, which is treated as
   *  recorded, because that is what every such payload was. */
  recorded?: boolean;
  recorded_note?: string;
} | null;

export type SmcSetup = {
  direction?: string;
  score?: number;
  narrative?: string;
  mitigated?: boolean;
  cited?: boolean;
  entries?: { aggressive?: number; conservative?: number };
  legs?: Record<string, { entry?: number; stop?: number; risk_pct?: number;
                          rr?: number; too_tight?: boolean; warning?: string }>;
  stop?: number; stop_tight?: number; target?: number; distance_pct?: number;
  sweep?: { side?: string; level?: number; bars_ago?: number };
  break?: { kind?: string; direction?: string; level?: number };
  order_block?: { lo?: number; hi?: number; displacement_atr?: number };
  fvg?: { lo?: number; hi?: number } | null;
};

export type SmcRead = {
  setups?: SmcSetup[];
  sweeps?: { side?: string; level?: number; bars_ago?: number }[];
  breaks?: { kind?: string; direction?: string; level?: number; bars_ago?: number }[];
  order_blocks?: { kind?: string; lo?: number; hi?: number; displacement_atr?: number }[];
  cited?: boolean;
  note?: string;
} | null;

export type BullishPattern = {
  kind?: string;
  label?: string;
  confirmed?: boolean;
  cited?: boolean;
  entry?: number;
  stop?: number;
  target?: number;
  stats_transfer?: boolean;
  stats_caveat?: string;
  distance_pct?: number;
};

/** Human label for a band row: where it came from and what it is. */
export function sourceLabel(t: TradeLevel): string {
  if (t.source === 'fvg') {
    return t.fill_pct ? `Fair value gap · ${t.fill_pct}% filled` : 'Fair value gap';
  }
  if (t.touches && t.touches > 1) return `Swing band · ${t.touches} touches`;
  return 'Swing band';
}

/* ── formatting ───────────────────────────────────────────────────────────── */

export function money(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—';
  return `$${n.toFixed(2)}`;
}

/** The band, as a range. Never a single number: a support is a zone you place a
 *  stop under, and printing only the midpoint invites a stop inside it. */
export function bandLabel(lv: SupportLevel | null | undefined): string {
  if (!lv) return '—';
  return `${money(lv.lo)} – ${money(lv.hi)}`;
}

export function distanceLabel(
  lv: SupportLevel | null | undefined,
  side: 'support' | 'overhead' = 'support',
): string {
  if (!lv || lv.distance_pct == null || !Number.isFinite(lv.distance_pct)) return '—';
  const d = lv.distance_pct;
  // Under a rounding step from price, "+0.0%" reads as a formatting bug when
  // what it means is that the level is HERE — DHI's overhead sat 0.01% above
  // price on 2026-08-19, which is the whole reason that read mattered.
  if (Math.abs(d) < 0.05) return 'at price';
  if (side === 'overhead') return `+${d.toFixed(1)}%`;
  // A "support" whose distance came back negative is price already inside or
  // under it. Saying "-0.4% below" is nonsense; say where price actually is.
  if (d < 0) return `${Math.abs(d).toFixed(1)}% above`;
  return `${d.toFixed(1)}% below`;
}

/** How long ago the level was last touched, IN THE UNIT IT WAS COUNTED IN.
 *
 *  `bars_since_test` is a BAR count. On the daily frame a bar is a session, so
 *  "sessions" was the honest unit (never "days" — that is wrong across every
 *  weekend and holiday). Since 2026-09-22 the intraday frames read their own
 *  bars, and the same counter is then five-minute or fifteen-minute buckets:
 *  measured on the branch, PTGX `5m_today` served `bars_since_test: 6` for a
 *  band touched half an hour earlier, which this printed as "tested 6 sessions
 *  ago". For a man deciding whether a level just held or is stale those are
 *  opposite answers, so the caller passes the SERVED `levels_bar_label` and
 *  nothing here guesses.
 *
 *  No conversion to minutes: that would be arithmetic this file invented. The
 *  bar size is stated instead, which is what the server actually knows. */
export function recencyLabel(lv: SupportLevel | null | undefined,
                             barLabel?: string | null): string {
  if (!lv || lv.bars_since_test == null || !Number.isFinite(lv.bars_since_test)) {
    return 'not tested in this window';
  }
  const n = Math.round(lv.bars_since_test);
  const bar = (barLabel || '').trim();
  // The daily frame (and the named fallback, which serves 'daily' too) keeps
  // the session wording it has always had.
  if (!bar || bar === 'daily') {
    if (n <= 0) return 'tested today';
    if (n === 1) return 'tested yesterday';
    return `tested ${n} sessions ago`;
  }
  if (n <= 0) return 'tested on the last bar';
  if (n === 1) return `tested 1 ${bar} bar ago`;
  return `tested ${n} × ${bar} bars ago`;
}

/** The recency window in the unit the levels were counted in — the header's
 *  "touched in the last N …" clause. Same rule as `recencyLabel`. */
export function recentWindowLabel(bars: number | null | undefined,
                                  barLabel?: string | null): string {
  const n = (bars == null || !Number.isFinite(bars)) ? 0 : Math.round(bars);
  const bar = (barLabel || '').trim();
  if (!bar || bar === 'daily') return `${n} sessions`;
  return `${n} × ${bar} bars`;
}

/** The "Support below" table's EMPTY sentence.
 *
 *  It used to be composed at the call site from `window_label` — the pinned
 *  DAILY zoom — which on the two entry frames produced, verbatim: "No band
 *  below price in the last 6 months — nothing here to place a stop under. Try
 *  a longer zoom." Three things were wrong at once (measured 2026-09-22, PTGX
 *  and NVDA both serve an EMPTY `supports` on `5m_today` and `24h`):
 *
 *   1. the emptiness came from the frame's own 5-minute bars, not from six
 *      months — and PTGX's 6-month daily read is NOT empty, it holds a band at
 *      $142.43-$144.15 and the board's own demand band is printed a few lines
 *      above on the same page;
 *   2. it said nothing about what IS known — price standing inside a band, and
 *      the board's band below it;
 *   3. "Try a longer zoom" points at the "How far back" control, which does
 *      not render on any intraday frame.
 *
 *  Every number here is SERVED. Nothing is computed.
 */
export function emptySupportNote(
  p: SupportPayload | null | undefined,
  opts: { zoomApplies?: boolean; longerFrameLabel?: string } = {},
): string {
  const scope = p?.levels_scope || p?.window_label || 'this window';
  const out = [`No band below price in ${scope} — nothing here to place a `
               + 'stop under.'];
  const inside = p?.standing_in;
  if (inside) {
    out.push(`Price is standing INSIDE ${bandLabel(inside)} — the nearest band `
             + 'on this chart is around price, not under it.');
  }
  const bd = p?.board?.demand;
  if (bd && p?.last_price != null && Number.isFinite(bd.hi) && bd.hi < p.last_price) {
    out.push(`Below this chart, the BOARD's demand band is `
             + `${money(bd.lo)} – ${money(bd.hi)} — the daily read the alert `
             + 'gate and the paper lanes use, not this chart\'s own.');
  }
  out.push(opts.zoomApplies
    ? 'Try a longer zoom.'
    : opts.longerFrameLabel
      ? `Try \u201C${opts.longerFrameLabel}\u201D — it reads a longer window.`
      : 'Try a chart that reads a longer window.');
  return out.join(' ');
}

/** The evidence behind a level, in one phrase. Touch count leads because it is
 *  the thing that makes a price a level at all; strength is relative to the
 *  other bands IN THIS WINDOW and is meaningless across zooms, so it trails. */
export function evidenceLabel(lv: SupportLevel | null | undefined): string {
  if (!lv) return '—';
  const t = lv.touches ?? 0;
  const touches = t === 1 ? '1 touch' : `${t} touches`;
  // Overlay rows lead with agreement — it outranks everything else on the row.
  // "one window only" is spelled out because in this view that IS the caveat.
  if (lv.agree != null && lv.windows?.length) {
    const who = lv.windows.join(', ');
    const head = lv.agree >= 2
      ? `${lv.agree} windows agree (${who})`
      : `one window only (${who})`;
    const weakO = lv.tested ? '' : ' · single low';
    return `${head} · ${touches}${weakO}`;
  }
  const polarity = lv.origin === 'supply' ? ' · was resistance' : '';
  // Spelled out rather than left to be inferred from "1". This is the level a
  // stop goes under, and the difference between a floor and a bar is the whole
  // question.
  const weak = lv.tested ? '' : ' · single low';
  return `${touches}${weak}${polarity}`;
}

/** One line under the ticker: where price is standing right now. */
export function headline(p: SupportPayload | null | undefined): string {
  if (!p) return '';
  if (p.error) return p.error;
  // The unit the SERVER counted the bars in, never a guess from the frame key:
  // on the named fallback the frame is 5-minute but the levels are daily.
  const bar = p.levels_bar_label;
  if (p.standing_in) {
    return `Price is INSIDE a band at ${bandLabel(p.standing_in)} — `
      + `${evidenceLabel(p.standing_in)}, ${recencyLabel(p.standing_in, bar)}.`;
  }
  const sup = (p.supports || [])[0];
  if (!sup) return `No band below ${money(p.last_price)} in this window.`;
  const caveat = sup.tested ? '' : ' Single swing low, not a tested floor.';
  return `Nearest support ${bandLabel(sup)} · ${distanceLabel(sup)} · `
    + `${evidenceLabel(sup)} · ${recencyLabel(sup, bar)}.${caveat}`;
}

/** How many of the listed supports were tested inside the recency window.
 *  Ajay asked for "recent support levels as well", so the count is stated
 *  rather than left to be counted off the table. */
export function recentCount(levels: SupportLevel[] | null | undefined): number {
  return (levels || []).filter((l) => l.recent).length;
}

/** The warning shown when the frame was shorter than the window asked for.
 *  Empty string when there is nothing to warn about — a recent IPO is ordinary,
 *  but a chart labelled "6 months" that holds 30 bars is not. */
export function shortHistoryNote(p: SupportPayload | null | undefined): string {
  const s = p?.short_history;
  if (!s || !s.have || !s.asked) return '';
  // On a chart-only zoom (1w/2w) the shortfall is against the window the
  // NUMBERS were read from, not the 5-session picture — so the sentence names
  // it. Unset everywhere else, and the original wording is unchanged there.
  const w = p?.levels_window_label;
  return `Only ${s.have} sessions of history — less than the ${s.asked} `
    + (w ? `the ${w} read asks for. ` : `this window asks for. `)
    + `Levels are read from what exists.`;
}

/** How many of the listed supports price turned at more than once.
 *  Deliberately separate from `recentCount`: neither implies the other. A level
 *  touched yesterday once is recent and untested; one turned at four times last
 *  year is tested and stale. */
export function testedCount(levels: SupportLevel[] | null | undefined): number {
  return (levels || []).filter((l) => l.tested).length;
}
