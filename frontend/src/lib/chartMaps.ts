/* chartMaps — pure helpers for the Chart Maps study board (/chart-maps).
 *
 * Ajay 2026-08-15: "I need just maps that you are pulling show… look at
 * patterns and learn them day by day."
 *
 * Backend: backend/chart_maps/board.py (GET /chart-maps?tab=…). The server
 * returns ONE tile shape for all three tabs; everything here is geometry and
 * formatting, so the drawing component stays dumb and the numbers are testable.
 *
 * NOT advice — a study surface over scans that already exist.
 */
import { layoutLabels, type LabelItem } from './zonePlan';
import type { DemandScanProgress } from './demandScanProgress';

export type CmTab = 'vcp' | 'topping' | 'zones' | 'supply' | 'deep_demand' | 'gabbar' | 'support' | 'zero_dte' | 'winners' | 'earnings';
// `support` sits next to `zones` because it is the same structure at a
// different zoom — but it is the only tab that is NOT a board: it takes a
// ticker and computes, so the page skips its board fetch there entirely.
// `supply` sits directly after `zones`: it is the same scan read the other
// way up, and the pair is only useful side by side.
// `zero_dte` sits after the structure tabs and before the ledger ones: it is
// the only tab reading LIVE option chains rather than a cached equity scan,
// so it is deliberately not adjacent to the boards it can be confused with.
// `deep_demand` follows `supply` — it is the darkest read of the same zone
// structure: the first band already failed. `gabbar` follows it as the other
// levels-plus-sales board; both carry the Bonde sales gate.
// `topping` sits beside `vcp` — both are slices of the same SEPA scan file,
// one long-side, one short-side.
export const CM_TABS: CmTab[] = ['vcp', 'topping', 'zones', 'supply', 'deep_demand', 'gabbar', 'support', 'zero_dte', 'earnings', 'winners'];

/** Tabs driven by a scan. `support` answers one ticker on request, so the
 *  board loader, the sort/tier controls and the tile grid are all skipped for
 *  it — asking /chart-maps for an unknown tab silently returns the VCP board. */
export function isBoardTab(t: CmTab): boolean {
  return t !== 'support';
}

export const TAB_META: Record<CmTab, { label: string; blurb: string }> = {
  vcp: {
    label: 'Strong VCP',
    blurb: 'Bases whose contractions have tightened — the volatility squeeze before a breakout. Green box is the base, dashed lines the pivot and the stop.',
  },
  zones: {
    label: 'Back in Demand',
    blurb: 'Names that left a demand zone and have pulled back into it. Green band is the zone, with the buy / stop / target written on.',
  },
  earnings: {
    label: 'Earnings Flow',
    blurb: "Today only. Names that reported today and were BOUGHT — big volume, closing near the day's high — plus names reporting after today's close that institutions are already accumulating into. Amber badge means the print has not happened yet.",
  },
  supply: {
    label: 'Into Supply',
    blurb: 'The inverse of Back in Demand: names that have rallied INTO a tested band of overhead supply, or are about to. Red band is the ceiling, green the next support beneath it. Not a short list — it is where an advance is most likely to stall, so check it before you buy and watch it if you hold. "Room up:down" under 1.00 means more air below than above.',
  },
  topping: {
    label: 'S3 Topping · Shorts',
    blurb: 'The short-side slice of the SEPA scan: Stage 3 topping or Stage 4 decline (TLSW pp.73-76) with at least two independent distribution reads — more down days on above-average volume (p.76), CMF outflow, the largest drop since the Stage 2 advance (p.90), a close below the 50-day on heavy volume, climax runs, churning and high-volume reversals (TTLAC §9). Below the 200-day is Minervini\'s own Stage 4 short trigger (TTLAC §6). Ranked by how aggressive the selling reads; declining Bonde sales shown as confirmation only, because fundamentals lag at tops. Nothing here is backtested and shorting risk is unlimited — this is a study list, not an inverted buy button.',
  },
  deep_demand: {
    label: 'Deep Demand',
    blurb: 'Penalized price, intact business. Names that broke their FIRST demand band and are arriving at the second — kept only when Pradeep Bonde\'s sales tiers (his 5% YoY floor) say revenue is still growing, so a falling knife with a dying top line never shows. These fail the trend gate by design: the market has already punished them. Red band is the broken first level, green the second one being entered. 💰 marks money flowing back IN while price sits at the band — CMF-20 plus up/down volume-day counts (Minervini p.71-76) — and those sort first; 🔻 means sellers are still in control, shown so you know why it ranks last.',
  },
  gabbar: {
    label: 'Gabbar Levels',
    blurb: 'Hand-curated buy zones from Gabbar\'s Price Levels (veerenj on TradingView) — expert judgment stored as numbers, not a computation. Names touching or within 3% of a band sort first. The same Bonde sales gate applies: a covered name with declining revenue is hidden, because a hand-drawn level under a shrinking business is exactly the knife. Check the snapshot date in the note — old levels describe an old chart.',
  },
  support: {
    label: 'Support Levels',
    blurb: 'Any ticker, on demand. The zoom changes the answer on purpose — a 1-month read finds the level this week\'s trade is standing on, a 1-year read finds the structural floor. Green bands are support below, red overhead; a ● marks a level price has actually tested recently.',
  },
  zero_dte: {
    label: '0DTE Options',
    blurb: 'Same-day expiry, calls and puts. "0.4x" means the underlying needs four tenths of today\'s expected move for the contract to double — the only figure comparable across names, since a 1% day is a crash in SPY and a Tuesday in TSLA. Read the badge first: PINNED means dealers suppress movement and you are fighting them, AMPLIFYING means they push it along. Theta on a 0DTE routinely exceeds the entire premium in a day. Every suggestion here is recorded and graded, because nothing about it has been backtested — there is no intraday option history to backtest against.',
  },
  winners: {
    label: 'Past Winners',
    blurb: 'Setups from your own ledger that reached their measure-rule target before their stop. The dotted line is the confirmation bar — study what the base looked like BEFORE it.',
  },
};

export type CmBar = { t: string; o: number; h: number; l: number; c: number; v: number };
// `neutral` is a range that is neither a floor nor a lid — the 0DTE gamma
// walls, which bracket where dealer hedging is expected to contain the tape.
// Colouring it green or red would imply a direction it does not have.
export type CmBand = { kind: 'base' | 'demand' | 'supply' | 'neutral'; lo: number; hi: number; label?: string };
export type CmLineTone = 'buy' | 'stop' | 'target' | 'now' | 'neutral';
export type CmLine = { price: number; label: string; tone: CmLineTone };
export type CmMarker = { date: string; label?: string; kind?: string };
export type CmStat = { k: string; v: string };
export type CmBadge = { text: string; tone: 'good' | 'warn' | 'muted' };

export type CmTile = {
  symbol: string;
  name?: string | null;
  href: string;
  bars: CmBar[];
  bands: CmBand[];
  lines: CmLine[];
  markers: CmMarker[];
  stats: CmStat[];
  why: string;
  theme?: string | null;
  badges?: CmBadge[];
  pattern?: string | null;
};

export type CmPatternRecord = {
  pattern: string; label: string;
  wins: number; losses: number; n: number; win_pct: number | null;
};

export type CmSort = { key: string; label: string };

export type CmBoard = {
  tab: CmTab;
  count: number;
  /** The sort actually applied. The winners tabs read a ledger with no live
   *  volume, so the backend answers `theme` there and sends an empty `sorts`. */
  sort?: string;
  sorts?: CmSort[];
  /** Liquidity floor by 50-day average $ volume, same tiers as Back in Demand. */
  min_tier?: string;
  tiers?: CmSort[];
  /** How many names the floor removed. Shown so a shrunken board is explained
   *  rather than just smaller. */
  dropped_thin?: number;
  /** 0DTE only — the same-day expiry these chains are read from. */
  expiry?: string;
  /** 0DTE only — where in the trading day this read happened. After the close
   *  on expiry day the chain has SETTLED, and a board that is nearly empty is
   *  correct rather than broken. The banner says which. */
  session?: { state: string; label: string; actionable: boolean } | null;
  /** 0DTE only — names with a same-day chain, and how many of those carry any
   *  contract clearing the cost floors. The gap between them is the point. */
  with_chain?: number;
  with_contract?: number;
  cached_age_sec?: number;
  /** Sorts that need an intraday tape pull, and how far it got. */
  tape_sorts?: string[];
  tape_pool?: number;
  tape_enriched?: number;
  /** Set when the chosen sort's column came back empty for every row — the
   *  board is showing its default order and says so. */
  sort_unavailable?: string | null;
  tiles: CmTile[];
  disclaimer?: string;
  note?: string;
  warming?: boolean;
  /* The demand tab's live scan counter. Same scan the Back in Demand tab on
   * /supply-demand watches — both tabs read one demand_reentry cache, so they
   * must show one progress reading (Ajay 2026-08-17). */
  progress?: DemandScanProgress | null;
  matched?: number;
  scanned?: number;
  universe_key?: string;
  universe_label?: string;
  /** The universes the SERVER offers. Preferred over the frontend's
   *  fallback list so adding one backend-side needs no FE deploy. */
  universe_choices?: { key: string; label: string }[];
  generated_at?: string | number | null;
  scan_generated_at?: string | number | null;
  patterns?: string[];
  excluded_already_past_target?: number;
  record?: {
    overall: { wins: number; losses: number; n: number; win_pct: number | null };
    by_pattern: CmPatternRecord[];
    caveat: string;
  };
};

/* ── tab plumbing ─────────────────────────────────────────────────────────── */

/** Coerce a `?tab=` value. An unknown tab lands on the first one rather than
 *  rendering an empty board — a mistyped deep link should still show charts. */
export function parseTab(raw: string | null | undefined): CmTab {
  const t = (raw || '').trim().toLowerCase();
  return (CM_TABS as string[]).includes(t) ? (t as CmTab) : 'vcp';
}

/** Deep link to a ticker's SEPA detail page, on the tab that shows the same
 *  geometry the tile drew. SepaCandidate silently falls back to its `chart`
 *  tab on an unknown value, so a typo here is invisible — hence the test. */
export function sepaHref(symbol: string, tab: 'setup' | 'supply' | 'breakout' = 'setup'): string {
  return `/sepa/${encodeURIComponent((symbol || '').toUpperCase())}?tab=${tab}`;
}

/** Which ledger the Past Winners tab reads. Ajay 2026-08-16: "In the past
 *  winners tab I wanna see the deman zones that were successful as well." */
export type WinnerSource = 'pattern' | 'zone';

export const WINNER_SOURCES: { key: WinnerSource; label: string }[] = [
  { key: 'pattern', label: 'Chart patterns' },
  { key: 'zone', label: 'Demand zones' },
];

export function parseSource(v: string | null | undefined): WinnerSource {
  return v === 'zone' ? 'zone' : 'pattern';
}

/** Matches board.DEFAULT_SORT — the tab's own score (base tightness for VCP,
 *  R:R for demand), NOT a metric. Kept out of the query string when unchanged so
 *  a shared URL stays short and the default stays the default.
 *
 *  Was 'theme' / "🤖 AI sectors (default)" until 2026-08-17, which bundled two
 *  claims into one entry: the theme LEAD is the checkbox, this is the ordering
 *  used when no metric is chosen. Ajay: "Remove default themes checked and AI
 *  sector from drop down". */
export const DEFAULT_SORT = 'default';

/** Matches board.THEMES_FIRST_DEFAULT. The AI-ecosystem lead is now opt-in. */
export const THEMES_FIRST_DEFAULT = false;

/** Matches board.DEFAULT_MIN_TIER — "comfortably tradeable in retail size"
 *  ($10M/day). Ajay 2026-08-17: "we want to make that average turn over is high
 *  for these". A study board that teaches the shape of a $1.5M/day base is
 *  teaching a pattern he cannot actually trade. */
export const DEFAULT_MIN_TIER = 'ok';

export function parseTier(raw: string | null | undefined): string {
  const v = (raw || '').trim();
  return v || DEFAULT_MIN_TIER;
}

/** A sort the backend actually offers, or the default. The board advertises its
 *  own options, so a key retired server-side degrades instead of 404ing. */
export function parseSort(raw: string | null | undefined,
                          offered?: CmSort[] | null): string {
  const v = (raw || '').trim();
  if (!v) return DEFAULT_SORT;
  if (offered && offered.length) {
    return offered.some((o) => o.key === v) ? v : DEFAULT_SORT;
  }
  return v;
}

export function boardQuery(p: {
  tab: CmTab; limit?: number; days?: number;
  universe?: string; themesFirst?: boolean; pattern?: string | null;
  source?: WinnerSource; minerviniOnly?: boolean; sort?: string;
  minTier?: string;
}): string {
  const q = new URLSearchParams({ tab: p.tab });
  if (p.limit) q.set('limit', String(p.limit));
  if (p.days) q.set('days', String(p.days));
  // Both demand boards read ONE demand_reentry cache, so the universe
  // choice governs both or the two tabs would describe different scans.
  if ((p.tab === 'zones' || p.tab === 'supply') && p.universe) {
    q.set('universe', p.universe);
  }
  // Only sent when it differs from the shared default, so the common URL stays
  // clean. That default flipped to OFF on 2026-08-17, so this now sends `true`
  // rather than `false` — keeping it on `false` would have put the parameter on
  // every request while silently never sending the one that changes anything.
  if (p.themesFirst !== undefined && p.themesFirst !== THEMES_FIRST_DEFAULT) {
    q.set('themes_first', String(p.themesFirst));
  }
  // Sent to the BACKEND on purpose. board._finish ranks and caps before it
  // fetches bars for only the tiles it will show, so sorting in the browser
  // would reorder the ~24 tiles theme priority already chose — "highest
  // volume" would silently mean "highest volume among those 24".
  if (p.sort && p.sort !== DEFAULT_SORT) q.set('sort', p.sort);
  if (p.minTier && p.minTier !== DEFAULT_MIN_TIER) q.set('min_tier', p.minTier);
  // Winners-only params. `pattern` is meaningless for the zone ledger — zone
  // re-entries have no chart-pattern name — so it is dropped there rather than
  // sent and silently ignored.
  if (p.tab === 'winners' && p.source === 'zone') q.set('source', 'zone');
  if (p.tab === 'winners' && p.source !== 'zone' && p.pattern) q.set('pattern', p.pattern);
  if (p.tab === 'winners' && p.source !== 'zone' && p.minerviniOnly) {
    q.set('minervini_only', 'true');
  }
  return q.toString();
}

/* ── chart geometry ───────────────────────────────────────────────────────── */

export type Domain = { lo: number; hi: number };

/** Y-domain over candle highs/lows, widened for nearby bands and lines.
 *
 * The nearness guard is the same idea as zonePlan.chartDomain: a target sitting
 * 40% above the last bar is context, and stretching to it flattens the price
 * action into a streak — which defeats the whole point of a study chart. Only
 * levels within one series-height of the data pull the domain.
 */
export function barDomain(
  bars: CmBar[],
  bands: CmBand[] = [],
  lines: CmLine[] = [],
  padPct = 6,
): Domain {
  const highs = bars.map((b) => b.h).filter((n) => Number.isFinite(n));
  const lows = bars.map((b) => b.l).filter((n) => Number.isFinite(n));
  if (!highs.length || !lows.length) return { lo: 0, hi: 1 };
  let lo = Math.min(...lows);
  let hi = Math.max(...highs);
  const height = hi - lo || 1;

  const stretch = (v: number | null | undefined) => {
    if (v == null || !Number.isFinite(v)) return;
    if (v >= lo - height && v <= hi + height) {
      lo = Math.min(lo, v);
      hi = Math.max(hi, v);
    }
  };
  for (const b of bands) { stretch(b.lo); stretch(b.hi); }
  for (const l of lines) stretch(l.price);

  const pad = ((hi - lo) || hi || 1) * (padPct / 100);
  return { lo: lo - pad, hi: hi + pad };
}

/** Price → SVG y. Inverted (high price = small y). */
export function yFor(price: number, d: Domain, height: number, padY = 8): number {
  const span = d.hi - d.lo || 1e-9;
  const t = (price - d.lo) / span;
  return padY + (1 - t) * (height - 2 * padY);
}

/** Index → SVG x for the centre of bar `i`. */
export function xFor(i: number, n: number, width: number, padR: number): number {
  const w = Math.max(width - padR, 1);
  const bw = w / Math.max(n, 1);
  return i * bw + bw / 2;
}

export function barWidth(n: number, width: number, padR: number): number {
  return Math.max(width - padR, 1) / Math.max(n, 1);
}

/** Clip bands to the visible domain, dropping any that fall outside it, so we
 *  never draw an off-canvas rectangle or a zero-height sliver. */
export function clipBands(bands: CmBand[], d: Domain): CmBand[] {
  const out: CmBand[] = [];
  for (const b of bands) {
    if (!Number.isFinite(b.lo) || !Number.isFinite(b.hi)) continue;
    const lo = Math.max(Math.min(b.lo, b.hi), d.lo);
    const hi = Math.min(Math.max(b.lo, b.hi), d.hi);
    if (hi <= lo) continue;                    // entirely outside the view
    out.push({ ...b, lo, hi });
  }
  return out;
}

// HIGHER wins: layoutLabels sorts descending and pins anything >= 2 to its
// exact y. `neutral` is the earnings tiles' prior-close reference, so it sits
// at 1 — it may be nudged or dropped when the plan lines need the pixels,
// which is right, because the gap it marks is already written in the stats.
const TONE_PRIORITY: Record<CmLineTone, number> = {
  buy: 3, stop: 3, target: 2, now: 2, neutral: 1,
};

/** Right-edge labels for the plan lines, de-collided. Reuses zonePlan's
 *  layoutLabels so the two chart surfaces cannot drift apart. */
export function lineLabels(
  lines: CmLine[], d: Domain, height: number, padY = 8,
): LabelItem[] {
  const items: LabelItem[] = lines
    .filter((l) => Number.isFinite(l.price) && l.price >= d.lo && l.price <= d.hi)
    .map((l) => ({
      y: yFor(l.price, d, height, padY),
      text: l.label,
      color: toneColor(l.tone),
      bold: l.tone === 'buy',
      priority: TONE_PRIORITY[l.tone] ?? 2,
    }));
  return layoutLabels(items, { minGap: 10, top: 6, bottom: height - 4, maxShift: 22 });
}

/* ── price axis (2026-08-19) ──────────────────────────────────────────────────
 * Ajay: "can you add the #s to these graphs please?"
 *
 * Until now the ONLY numbers on a tile were the plan-line labels. A demand band
 * could be drawn as a green box with no way to read what price it sat at —
 * which is most of the point on the Support Levels tab, where the band IS the
 * answer.
 *
 * The axis goes in the SAME right gutter the plan labels already use, never
 * over the candles. Ajay 2026-08-18: "they are all clumsy and its hard to look
 * at the bars" — that complaint was about text on the price action, and this
 * must not re-create it.
 */

/** Steps a human reads without thinking, per decade. */
const STEP_MULTS = [1, 2, 2.5, 5];

/** Pick the step whose tick count lands closest to `target`.
 *
 * The naive `niceStep(span / target)` rounds UP through a 5→10 gap, which on a
 * real chart is the difference between a usable scale and a broken one: META
 * over a year spans ~$300, `300/5 = 60` rounds to 100, and the axis came back
 * 600 / 700 / 800 — while price was at 539, so every tick sat above the entire
 * lower half of the chart (measured 2026-08-19). Searching the ladder either
 * side of the estimate picks 50 instead, and the scale covers the candles.
 *
 * Ties go to the LARGER step: fewer gridlines for the same coverage.
 */
function chooseStep(span: number, target: number): number {
  if (!Number.isFinite(span) || span <= 0) return 1;
  const exp = Math.floor(Math.log10(span / Math.max(target, 1)));
  let best = Math.pow(10, exp);
  let bestScore = Infinity;
  for (const e of [exp - 1, exp, exp + 1]) {
    for (const m of STEP_MULTS) {
      const step = m * Math.pow(10, e);
      if (!Number.isFinite(step) || step <= 0) continue;
      const count = Math.floor(span / step);
      if (count < 2 || count > MAX_TICKS) continue;
      const score = Math.abs(count - target);
      if (score < bestScore || (score === bestScore && step > best)) {
        best = step;
        bestScore = score;
      }
    }
  }
  return best;
}

/** Ceiling on gridlines. Past this the chart is graph paper, not a chart. */
const MAX_TICKS = 10;

/** Roughly how many ticks to aim for. Six rather than four because some are
 *  spent on collisions with the plan labels — BRKR at the 1-month zoom lost two
 *  of four that way and the scale stopped being readable. */
const TARGET_TICKS = 6;

/** Decimals needed to print the step EXACTLY, capped at 2.
 *
 * Not derived from the step's magnitude — that was wrong, and wrong in the way
 * that matters. `-floor(log10(2.5))` is 0, so a 2.5 step printed BRKR's
 * gridlines at 52.5 and 57.5 as "53" and "58" (measured 2026-08-19): the number
 * claimed a price the line was not drawn at. An axis that misreports its own
 * position is worse than no axis, because a stop gets placed off it.
 *
 * So: the smallest decimal count that represents the step without rounding.
 * 50 → 0, 2.5 → 1, 0.25 → 2.
 */
export function tickDecimals(step: number): number {
  if (!Number.isFinite(step) || step <= 0) return 2;
  for (let d = 0; d <= 2; d++) {
    const scaled = step * Math.pow(10, d);
    if (Math.abs(scaled - Math.round(scaled)) < 1e-9) return d;
  }
  return 2;
}

export type PriceTick = { price: number; y: number; text: string };

/** Horizontal price ticks across the visible domain.
 *
 * Stepping by index rather than accumulating `p += step` keeps float error out
 * of the label text — otherwise a 0.1 step prints "1.3000000000000003".
 */
export function priceTicks(
  d: Domain, height: number, padY = 8, target = TARGET_TICKS,
): PriceTick[] {
  const span = d.hi - d.lo;
  if (!Number.isFinite(span) || span <= 0 || !Number.isFinite(height)) return [];
  const step = chooseStep(span, target);
  const dp = tickDecimals(step);
  const first = Math.ceil(d.lo / step) * step;
  const out: PriceTick[] = [];
  for (let i = 0; i <= MAX_TICKS * 2; i++) {
    const price = first + i * step;
    if (price > d.hi) break;
    const y = yFor(price, d, height, padY);
    // Keep the top and bottom labels off the chart's own edges, where they
    // would sit half-clipped or collide with the month row.
    if (y < padY + 2 || y > height - padY - 2) continue;
    out.push({ price, y, text: price.toFixed(dp) });
  }
  return out;
}

/** Which ticks may print their NUMBER. The gridline is always drawn.
 *
 * The plan labels win the text: buy / stop / target / now are the decision
 * numbers, and they are more precise than the round tick they sit next to. But
 * suppressing the whole tick left visible holes in an evenly spaced grid —
 * BRKR kept 2 of 4 — which reads as a rendering bug rather than as deference.
 * So the LINE stays and only the number yields; at that height there is still a
 * number on screen, just a better one.
 */
export function dropCollidingTicks(
  ticks: PriceTick[], labels: { y: number }[], minGap = 11,
): PriceTick[] {
  if (!labels?.length) return ticks;
  return ticks.filter((t) => !labels.some((l) => Math.abs(l.y - t.y) < minGap));
}

/* ── right gutter + hover readout (2026-08-19) ────────────────────────────────
 * Ajay, with a screenshot: the META tile rendered "overhead 553" and
 * "support 527." — both cut off at the SVG's right edge. PAD_R was a fixed 62
 * units in a 620-unit viewBox, and "overhead 553.67" needs ~78. The tab that
 * exposed it is the one where the label IS the answer.
 *
 * And: "can you give me same features like hover over prices at the level".
 */

/** Approximate advance width of a string, in viewBox units, without measuring.
 *
 * getComputedTextLength needs a laid-out DOM node, which the geometry layer
 * deliberately does not have — every number on this chart comes from a pure
 * function so it can be tested. Per-class advances for a UI sans are close
 * enough for a gutter that gets clamped anyway.
 */
export function textWidth(text: string, fontSize: number): number {
  let em = 0;
  for (const ch of text || '') {
    // DIGITS FIRST. UI sans faces ship tabular figures by default — every
    // digit carries the same advance so columns of numbers line up — so '1'
    // is NOT a narrow glyph here. Lumping it in with 'il!' under-measured
    // every label holding a 1, which is most stock prices, and let
    // "overhead 151.87" overflow the gutter it had just been widened for.
    if (ch >= '0' && ch <= '9') em += 0.55;
    else if (ch === ' ') em += 0.28;
    else if ('.,:;\'`|'.includes(ch)) em += 0.28;
    else if ('il!'.includes(ch)) em += 0.30;
    else if ('mwMW'.includes(ch)) em += 0.85;
    else if (ch >= 'A' && ch <= 'Z') em += 0.66;
    else em += 0.55;
  }
  return em * fontSize;
}

export const GUTTER_MIN = 56;
export const GUTTER_MAX = 118;

/** Width the right gutter needs so no label is clipped.
 *
 * Dynamic rather than a constant: a board tile labelled "BUY 152.30" should not
 * pay for the Support tab's "overhead 553.67". Clamped at both ends so one
 * pathological label cannot eat the plot.
 */
export function gutterWidth(
  texts: string[], fontSize = 9.5, pad = 12,
): number {
  // `pad` is real breathing room, not decoration. `textWidth` is an ESTIMATE —
  // the actual face, its kerning and the user's zoom all move the true advance
  // — so the margin has to absorb being wrong by a few percent. At pad 8 a
  // deliberately cruder estimate already overflowed the viewBox by 0.4 units,
  // which is exactly the clipped label this function exists to prevent.
  const widest = (texts || []).reduce(
    (m, t) => Math.max(m, textWidth(t, fontSize)), 0);
  return Math.min(GUTTER_MAX, Math.max(GUTTER_MIN, Math.ceil(widest + pad)));
}

/** Inverse of `yFor` — the price at a pixel row. Used by the hover crosshair. */
export function priceAt(y: number, d: Domain, height: number, padY = 8): number {
  const usable = height - 2 * padY || 1;
  const t = 1 - (y - padY) / usable;
  return d.lo + t * (d.hi - d.lo);
}

/** Inverse of `xFor` — which bar sits under a pixel column, clamped to the
 *  series so a cursor in the gutter still reads the last bar rather than
 *  falling off the end. */
export function barIndexAt(
  x: number, n: number, width: number, padR: number,
): number {
  if (!n) return -1;
  const w = Math.max(width - padR, 1);
  const bw = w / n;
  return Math.min(n - 1, Math.max(0, Math.floor(x / bw)));
}

/** The band a price falls inside, if any. Hovering a zone should name it —
 *  that is the "hover over prices at the level" ask. */
export function bandAt(price: number, bands: CmBand[]): CmBand | null {
  if (!Number.isFinite(price)) return null;
  for (const b of bands || []) {
    const lo = Math.min(b.lo, b.hi);
    const hi = Math.max(b.lo, b.hi);
    if (price >= lo && price <= hi) return b;
  }
  return null;
}

/** Compact volume — 12.4M, 903K. A raw 18011648 in a tooltip is unreadable. */
export function shortVol(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v) || v < 0) return '—';
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${Math.round(v / 1e3)}K`;
  return String(Math.round(v));
}

/** Keep a tooltip box inside the chart, flipping it rather than clipping it.
 *  A readout that runs off the right edge is the same defect as the labels
 *  this change was opened to fix. */
export function tooltipPos(
  x: number, y: number, boxW: number, boxH: number,
  width: number, height: number, gap = 10,
): { x: number; y: number } {
  const px = x + gap + boxW > width ? Math.max(2, x - gap - boxW) : x + gap;
  const py = Math.min(Math.max(2, y - boxH / 2), Math.max(2, height - boxH - 2));
  return { x: px, y: py };
}

/** The lines of the hover readout for one bar. Pure so the text is testable. */
export function hoverLines(bar: CmBar | null | undefined): string[] {
  if (!bar) return [];
  const f = (n: number) => (Number.isFinite(n) ? n.toFixed(2) : '—');
  return [
    bar.t,
    `O ${f(bar.o)}   H ${f(bar.h)}`,
    `L ${f(bar.l)}   C ${f(bar.c)}`,
    `Vol ${shortVol(bar.v)}`,
  ];
}

export function toneColor(tone: CmLineTone): string {
  if (tone === 'buy') return 'var(--positive, #22c55e)';
  if (tone === 'stop') return 'var(--negative, #ef4444)';
  if (tone === 'target') return 'var(--gold, #c9a227)';
  return 'var(--text-muted, #94a3b8)';
}

/** Sparse x-axis ticks — first bar of each new month, as {i, label}. A dense
 *  daily axis is unreadable at tile size; month boundaries are what you
 *  actually navigate by. */
export function monthTicks(bars: CmBar[], max = 6): { i: number; label: string }[] {
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const ticks: { i: number; label: string }[] = [];
  let prev = '';
  bars.forEach((b, i) => {
    const mo = (b.t || '').slice(0, 7);
    if (mo && mo !== prev) {
      prev = mo;
      const m = Number(mo.slice(5, 7));
      if (m >= 1 && m <= 12) ticks.push({ i, label: MON[m - 1] });
    }
  });
  if (ticks.length <= max) return ticks;
  const step = Math.ceil(ticks.length / max);
  return ticks.filter((_, i) => i % step === 0);
}

/** Index of a dated marker within the bar window, or -1.
 *  Joined by DATE, never by index — the ledger's indices are offsets into the
 *  full cached frame, not into the window drawn here. */
export function markerIndex(bars: CmBar[], date: string): number {
  const d = (date || '').slice(0, 10);
  if (!d) return -1;
  return bars.findIndex((b) => b.t === d);
}

/* ── formatting ───────────────────────────────────────────────────────────── */

/* Order here mirrors backend THEME_PRIORITY (sepa/universe.py) — Ajay's stated
 * priority, most-wanted first. The board already sorts by it; keeping the same
 * order here means the legend and the tiles tell the same story. */
export const THEME_LABEL: Record<string, string> = {
  space: '🛰 Space',
  quantum: '⚛ Quantum',
  ai_semis: '🔲 AI semis',
  optical: '💡 Optical',
  robotics: '🦾 Robotics',
  ai_infra: '⚡ AI infra',
  nuclear: '☢ Nuclear',
};

export function themeLabel(theme: string | null | undefined): string | null {
  if (!theme) return null;
  return THEME_LABEL[theme] || theme.replace(/_/g, ' ');
}

/** One honest line about a pattern's record.
 *
 * Always states the loss side and the sample size. Never compares patterns to
 * each other — their stop brackets differ ~2x, which is exactly the broken
 * comparison the 2026-07-10 pattern audit found. */
export function recordLine(r: CmPatternRecord | null | undefined): string {
  if (!r || !r.n) return 'no resolved observations yet';
  const pct = r.win_pct == null ? '—' : `${r.win_pct}%`;
  return `${r.wins} hit target · ${r.losses} stopped out · ${pct} of ${r.n}`;
}

/** Small-sample guard. Under this many resolved observations a win rate is a
 *  number, not a finding. */
export const MIN_SAMPLE = 20;

export function isThinSample(n: number | null | undefined): boolean {
  return !n || n < MIN_SAMPLE;
}

/* ── scan freshness ───────────────────────────────────────────────────────── */

/** Parse a backend scan timestamp — ISO string (demand `as_of`) or epoch
 *  seconds/ms (older caches) — to epoch ms, or null. */
export function parseScanTs(raw: string | number | null | undefined): number | null {
  if (raw == null) return null;
  if (typeof raw === 'number') {
    if (!Number.isFinite(raw) || raw <= 0) return null;
    return raw < 1e12 ? raw * 1000 : raw;
  }
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : null;
}

/** "Scanned just now" / "Scanned 4m ago" / "Scanned 3h ago" / "Scanned 2d ago".
 *  Null when the backend sent no timestamp — the stamp then simply doesn't
 *  render; a made-up "just now" is exactly the false reassurance this exists
 *  to prevent (Ajay 2026-08-25: same tiles two days running looked stale, and
 *  the board carried nothing that could prove otherwise). */
export function scanStamp(raw: string | number | null | undefined, nowMs: number): string | null {
  const ts = parseScanTs(raw);
  if (ts == null) return null;
  const sec = Math.max(0, (nowMs - ts) / 1000); // clock skew → clamp, not lie
  if (sec < 90) return 'Scanned just now';
  const min = Math.round(sec / 60);
  if (min < 90) return `Scanned ${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 36) return `Scanned ${hr}h ago`;
  return `Scanned ${Math.round(hr / 24)}d ago`;
}

/** "data through Aug 25" — the newest bar date any tile on the board carries.
 *  This is the half a wall-clock stamp can't answer: a scan run five minutes
 *  ago over week-old bars is still stale. Null when no tile has bars. */
export function dataThrough(tiles: { bars?: CmBar[] }[] | null | undefined): string | null {
  let best = '';
  for (const t of tiles || []) {
    const last = t.bars?.[t.bars.length - 1];
    if (last?.t && last.t > best) best = last.t;
  }
  if (!best) return null;
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const m = Number(best.slice(5, 7));
  const d = Number(best.slice(8, 10));
  if (!(m >= 1 && m <= 12) || !d) return null;
  return `data through ${MON[m - 1]} ${d}`;
}
