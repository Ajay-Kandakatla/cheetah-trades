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
import type { CmTile } from './chartMaps';

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
  /** What the chart is ACTUALLY showing — the Zoom label is daily-bar
   *  counts and does not apply on an intraday timeframe. */
  chart_span?: string;
  zoom_applies?: boolean;
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
  supports?: SupportLevel[];
  overhead?: SupportLevel[];
  standing_in?: SupportLevel | null;
  levels_capped?: boolean;
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
  { key: '1m', label: '1 month', bars: 21 },
  { key: '3m', label: '3 months', bars: 63 },
  { key: '6m', label: '6 months', bars: 126 },
  { key: '1y', label: '1 year', bars: 252 },
  { key: '5y', label: '5 years', bars: 1260 },
  // The overlay pseudo-window: every zoom at once, clustered by agreement.
  { key: 'all', label: 'All windows · overlay', bars: 0 },
];

/** Matches backend support.DEFAULT_WINDOW. */
export const DEFAULT_WINDOW = '3m';

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

/* ── timeframe (Ajay 2026-08-29) ───────────────────────────────────────────
 * The SECOND dropdown, and a different question from the zoom: the window
 * says how far back to look, the timeframe says how finely. Mirrors backend
 * supply_demand/timeframes.TIMEFRAMES. */
export type Timeframe = { key: string; label: string; span?: string; bars?: number };

export const FALLBACK_TIMEFRAMES: Timeframe[] = [
  { key: 'daily', label: 'Daily', span: '1 year of daily bars' },
  { key: '60m', label: '1 hour', span: '~47 sessions of hourly bars' },
  { key: '15m', label: '15 min', span: '~10 sessions of 15-minute bars' },
  { key: '15m_open', label: '15 min · from the open',
    span: "today's session only, from 09:30 ET" },
  { key: '5m_live', label: '5 min · live · pre/post market',
    span: 'last ~2.5 sessions of 5-minute bars incl. pre/post market' },
];

export const DEFAULT_TF = 'daily';

/* ── One control instead of two (Ajay 2026-08-29) ──────────────────────────
 * "The 15 mins chart is also so confusing ... why Am I seeing from past
 * months? ... you need to make some decisions as a UX expert."
 *
 * He was right, and the root cause was two dropdowns that could contradict
 * each other: Zoom counts DAILY bars, so "1 month" + "15 min" is not a
 * narrower 15-minute chart, it is a combination with no meaning. A control
 * that can be set to nonsense will be, and then the chart looks broken.
 *
 * So the two collapse into ONE list of views a person would actually ask
 * for. Every entry is a valid pair; no invalid combination is reachable.
 * The wire format keeps `window` and `tf` separate — the backend contract
 * does not change, only the way the choice is offered. */
export type ChartView = {
  key: string; label: string; group: 'Daily' | 'Intraday';
  window: string; tf: string; hint?: string;
};

export const CHART_VIEWS: ChartView[] = [
  { key: 'daily:1m', label: '1 month', group: 'Daily', window: '1m', tf: 'daily',
    hint: 'the level this week\'s trade is standing on' },
  { key: 'daily:3m', label: '3 months', group: 'Daily', window: '3m', tf: 'daily' },
  { key: 'daily:6m', label: '6 months', group: 'Daily', window: '6m', tf: 'daily' },
  { key: 'daily:1y', label: '1 year', group: 'Daily', window: '1y', tf: 'daily' },
  { key: 'daily:5y', label: '5 years', group: 'Daily', window: '5y', tf: 'daily',
    hint: 'the structural floor' },
  { key: 'daily:all', label: 'All windows · overlay', group: 'Daily',
    window: 'all', tf: 'daily' },
  { key: '60m', label: '1 hour · ~47 sessions', group: 'Intraday',
    window: '3m', tf: '60m' },
  { key: '15m', label: '15 min · ~10 sessions', group: 'Intraday',
    window: '1m', tf: '15m' },
  { key: '15m_open', label: '15 min · today from the open', group: 'Intraday',
    window: '1m', tf: '15m_open', hint: 'this session only, from 09:30 ET' },
  // Ajay 2026-09-02: "add live chart please ... I wanna see where things
  // bounced over night." The one view that draws pre/post-market bars and
  // refreshes itself while any extended session is open.
  // Levels come from the 6-month DAILY window (the zones he already knows);
  // only the tape is intraday — so an overnight touch is measured against a
  // real floor, not against 2.5 sessions of 5-minute swings.
  { key: '5m_live', label: '5 min · live · pre/post market', group: 'Intraday',
    window: '6m', tf: '5m_live',
    hint: 'last ~2.5 sessions incl. overnight against the 6-month daily levels; refreshes every 30s while the tape is open' },
];

export const DEFAULT_VIEW = 'daily:3m';

/** Resolve a (window, tf) pair back to the single control's value, so a
 *  shared URL written before this change still selects the right entry. */
export function viewKeyFor(window: string, tf: string): string {
  const t = parseTf(tf);
  if (t !== 'daily') {
    return CHART_VIEWS.find((v) => v.tf === t)?.key || DEFAULT_VIEW;
  }
  return CHART_VIEWS.find((v) => v.tf === 'daily' && v.window === window)?.key
    || DEFAULT_VIEW;
}

export function viewFor(key: string): ChartView {
  return CHART_VIEWS.find((v) => v.key === key)
    || CHART_VIEWS.find((v) => v.key === DEFAULT_VIEW)!;
}

export function parseTf(
  raw: string | null | undefined,
  offered: Timeframe[] = FALLBACK_TIMEFRAMES,
): string {
  const v = (raw || '').trim().toLowerCase();
  if (!v) return DEFAULT_TF;
  return offered.some((t) => t.key === v) ? v : DEFAULT_TF;
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

/** How long ago the level was last touched, in trading sessions.
 *  `bars_since_test` is a bar count, so "sessions" is the honest unit —
 *  calling them days would be wrong across every weekend and holiday. */
export function recencyLabel(lv: SupportLevel | null | undefined): string {
  if (!lv || lv.bars_since_test == null || !Number.isFinite(lv.bars_since_test)) {
    return 'not tested in this window';
  }
  const n = Math.round(lv.bars_since_test);
  if (n <= 0) return 'tested today';
  if (n === 1) return 'tested yesterday';
  return `tested ${n} sessions ago`;
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
  if (p.standing_in) {
    return `Price is INSIDE a band at ${bandLabel(p.standing_in)} — `
      + `${evidenceLabel(p.standing_in)}, ${recencyLabel(p.standing_in)}.`;
  }
  const sup = (p.supports || [])[0];
  if (!sup) return `No band below ${money(p.last_price)} in this window.`;
  const caveat = sup.tested ? '' : ' Single swing low, not a tested floor.';
  return `Nearest support ${bandLabel(sup)} · ${distanceLabel(sup)} · `
    + `${evidenceLabel(sup)} · ${recencyLabel(sup)}.${caveat}`;
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
  return `Only ${s.have} sessions of history — less than the ${s.asked} `
    + `this window asks for. Levels are read from what exists.`;
}

/** How many of the listed supports price turned at more than once.
 *  Deliberately separate from `recentCount`: neither implies the other. A level
 *  touched yesterday once is recent and untested; one turned at four times last
 *  year is tested and stale. */
export function testedCount(levels: SupportLevel[] | null | undefined): number {
  return (levels || []).filter((l) => l.tested).length;
}
