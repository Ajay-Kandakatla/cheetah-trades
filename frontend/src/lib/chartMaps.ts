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

export type CmTab = 'vcp' | 'topping' | 'zones' | 'supply' | 'ict' | 'deep_demand' | 'session' | 'gabbar' | 'undervalue' | 'support' | 'zero_dte' | 'winners' | 'earnings' | 'overnight' | 'signals';
// `support` sits next to `zones` because it is the same structure at a
// different zoom — but it is the only tab that is NOT a board: it takes a
// ticker and computes, so the page skips its board fetch there entirely.
// `ict` sits directly after `zones` — it TOOK the Into Supply slot (Ajay
// 2026-09-03 late: "create a new chart maps tab for ICT Strategy, replace
// supply tab with this new tab"). `supply` stays in the CmTab union so
// TAB_META keeps its copy and an old ?tab=supply deep link still renders (it
// resolves to `ict`, see parseTab); it is no longer in CM_TABS.
// `zero_dte` sits after the structure tabs and before the ledger ones: it is
// the only tab reading LIVE option chains rather than a cached equity scan,
// so it is deliberately not adjacent to the boards it can be confused with.
// `deep_demand` follows `ict` — it is the darkest read of the same zone
// structure: the first band already failed. `gabbar` follows it as the other
// levels-plus-sales board; both carry the Bonde sales gate.
// `topping` sits beside `vcp` — both are slices of the same SEPA scan file,
// one long-side, one short-side.
// `session` sits right after `deep_demand` because it READS those two tabs:
// it is the same names asked a different question (is the session confirming
// the daily band?), so it belongs beside its own inputs.
// `signals` sits beside `session` — both are intraday reads; session asks
// the demand boards' names, signals asks whatever tickers Ajay typed.
export const CM_TABS: CmTab[] = ['vcp', 'topping', 'zones', 'ict', 'deep_demand', 'session', 'signals', 'overnight', 'gabbar', 'undervalue', 'support', 'zero_dte', 'earnings', 'winners'];

/** Tabs driven by a scan. `support` answers one ticker on request, so the
 *  board loader, the sort/tier controls and the tile grid are all skipped for
 *  it — asking /chart-maps for an unknown tab silently returns the VCP board. */
export function isBoardTab(t: CmTab): boolean {
  // `session` joins `support` as a non-board tab: it has its own endpoint
  // (/supply-demand/session-board) and its own row renderer, so the tile grid
  // and the sort/tier controls are skipped for it too.
  return t !== 'support' && t !== 'session' && t !== 'overnight' && t !== 'signals';
}

export const TAB_META: Record<CmTab, { label: string; blurb: string }> = {
  signals: {
    label: '\u26A1 Signals',
    blurb: 'Your own tickers on 1-minute candles with BUY / SELL tags \u2014 opening-range breaks, liquidity sweeps and BOS/CHoCH structure composed into the five-step entry (stop at the trap wick, 2R target). Closed bars only; signals never repaint. Same board as the Signal Lab page.',
  },
  vcp: {
    label: 'Strong VCP',
    blurb: 'Bases whose contractions have tightened — the volatility squeeze before a breakout. Green box is the base, dashed lines the pivot and the stop.',
  },
  zones: {
    label: 'Back in Demand',
    blurb: 'Names that left a demand zone and have pulled back into it. Green band is the zone, with the buy / stop / target written on. Order (2026-09-03): the approaching boards rank closest to the level first; money flow (CMF) breaks ties within a 0.5% distance bucket; Back in Demand keeps reward:risk first. \ud83e\uddf2 marks dealer gamma from last night\'s close (same read as the GEX Board): helps = dealers dampen dips at your entry, hurts = they amplify moves; \ud83d\udee1\ufe0f/\ud83e\uddf1 flags a put/call wall sitting ON the drawn band. No chip just means the name is outside the nightly ~200-name gamma snapshot.',
  },
  earnings: {
    label: 'Earnings Flow',
    blurb: "Today only. Names that reported today and were BOUGHT — big volume, closing near the day's high — plus names reporting after today's close that institutions are already accumulating into. Amber badge means the print has not happened yet.",
  },
  // Not in CM_TABS since 2026-09-03 (the slot went to `ict`). Kept so an old
  // ?tab=supply bookmark still has copy to render if it ever reaches a page
  // that indexes TAB_META directly — parseTab sends it to `ict`.
  supply: {
    label: 'Into Supply',
    blurb: 'The inverse of Back in Demand: names that have rallied INTO a tested band of overhead supply, or are about to. Red band is the ceiling, green the next support beneath it. Not a short list — it is where an advance is most likely to stall, so check it before you buy and watch it if you hold. "Room up:down" under 1.00 means more air below than above. \ud83e\uddf2 marks dealer gamma from last night\'s close (same read as the GEX Board): helps = dealers dampen dips at your entry, hurts = they amplify moves; \ud83d\udee1\ufe0f/\ud83e\uddf1 flags a put/call wall sitting ON the drawn band. No chip just means the name is outside the nightly ~200-name gamma snapshot.',
  },
  // Ajay 2026-09-03 (late): "create a new chart maps tab for ICT Strategy,
  // replace supply tab with this new tab." The concepts are his own spec +
  // Jesse Rogers' video (ICT_SOURCE); everything numeric that the video does
  // not give is an OWNER setting the backend echoes in `params`, listed under
  // the board. Purely price action — no moving averages anywhere in it, and
  // nothing from the SEPA book (that is a different strategy's authority).
  ict: {
    label: 'ICT',
    blurb: 'Purely price action, two clocks. The daily chart sets the key levels — the last swing highs and lows (3-candle fractals) and the fair value gaps still open — and the 60-minute loop stays asleep until price actually taps one of them. Then it looks for the manipulation: a wick through a key low (or the accumulation range’s lows) that fails to close through it — no displacement. Confirmation is an energetic push the other way that leaves a new fair value gap AND closes past the last swing point (the market structure shift, MSS). Entry is the inverted FVG — an old bearish gap a candle closed firmly above — or the new gap itself; the stop sits under the manipulation wick and the target is the next daily swing point (external liquidity), mirrored for the bearish side. Tiles carry State → Grade → R:R so the ones with every step in place read first. The rules are Ajay’s spec plus Jesse Rogers’ walkthrough; every threshold the video does not give (how tight a consolidation, how many bars, the tap tolerance, the stop buffer) is an owner setting shown under the board, not a claim from the source. Not advice.',
  },
  topping: {
    label: 'S3 Topping · Shorts',
    blurb: 'The short-side slice of the SEPA scan: Stage 3 topping or Stage 4 decline (TLSW pp.73-76) with at least two independent distribution reads — more down days on above-average volume (p.76), CMF outflow, the largest drop since the Stage 2 advance (p.90), a close below the 50-day on heavy volume, climax runs, churning and high-volume reversals (TTLAC §9). Below the 200-day is Minervini\'s own Stage 4 short trigger (TTLAC §6). Ranked by how aggressive the selling reads; declining Bonde sales shown as confirmation only, because fundamentals lag at tops. Nothing here is backtested and shorting risk is unlimited — this is a study list, not an inverted buy button.',
  },
  deep_demand: {
    label: 'Deep Demand',
    blurb: 'Penalized price, intact business. Names that broke their FIRST demand band and are arriving at the second — kept only when Pradeep Bonde\'s sales tiers (his 5% YoY floor) say revenue is still growing, so a falling knife with a dying top line never shows. These fail the trend gate by design: the market has already punished them. Red band is the broken first level, green the second one being entered. 💰 marks money flowing back IN while price sits at the band — CMF-20 plus up/down volume-day counts (Minervini p.71-76) — and it decides ties. Order (2026-09-03): names inside the second band first, then the nearest approaching names; within a distance bucket money flow (CMF) ranks — supersedes the 2026-08-26 CMF-first order; 🔻 means sellers are still in control, shown so you know why it ranks last. \ud83e\uddf2 marks dealer gamma from last night\'s close (same read as the GEX Board): helps = dealers dampen dips at your entry, hurts = they amplify moves; \ud83d\udee1\ufe0f/\ud83e\uddf1 flags a put/call wall sitting ON the drawn band. No chip just means the name is outside the nightly ~200-name gamma snapshot.',
  },
  undervalue: {
    label: 'Under Value',
    blurb: 'Incredible sales, lagging price tag (2026-08-28). The whole universe screened for Bonde strong/explosive revenue (+25% / +100% YoY floors), kept only when price-to-sales divided by growth (PSG) is \u2264 0.15 — calibrated on LightPath at ~12x sales with +109% growth. Cheapest-for-growth ranks first, zones drawn per name so the entry is a level, not a feeling. Backlogs and contracts are not machine-readable: the screen finds the divergence, you check the story. Missing revenue or share data excludes a name — nothing here is estimated.',
  },
  session: {
    label: 'Session',
    blurb: 'After the open, for entries. Every name on Back in Demand and Deep Demand, re-read on intraday bars: market mood (bullish / bearish), where price sits against the opening range, unfilled fair-value gaps with the ones left by THIS session called out, and the complete Smart-Money sequence (liquidity sweep \u2192 BOS \u2192 order block \u2192 FVG) where one exists. The daily boards pick the names; this says whether the session is confirming the daily band that listed them \u2014 "at the daily band" plus a completed setup is the entry this tab exists to find. Mood, gaps and the SMC sequence are convention, not book methods, and the ranking is this app\'s own; the opening range says "forming" until its full window has printed. Not advice.',
  },
  overnight: {
    label: 'Overnight',
    blurb: 'The overnight movers board, in Chart Maps where the rest of the scan lives. Move = the headline change (chipped PM/AH/O\u2044N only when it IS the extended-hours move); O\u2044N drift = the actual extended-session change vs the last regular close; $ Vol avg = 50-day average liquidity for context; O\u2044N $ Vol = the dollars that actually traded in tonight\u2019s extended session (top names only \u2014 that is the real overnight volume). RelVol \u22651.5\u00d7 = elevated interest, <1\u00d7 = thin tape. Same data as the Day Trading page\u2019s scan. Not advice.',
  },
  gabbar: {
    label: 'Gabbar Levels',
    blurb: 'Hand-curated buy zones from Gabbar\'s Price Levels (veerenj on TradingView) — expert judgment stored as numbers, not a computation. Names touching or within 3% of a band sort first, and 🛡️ marks one at its CONSERVATIVE band — the author\'s deeper discount level — which leads its group over an aggressive-band touch; each tile\'s Conserv. stat shows where that deeper entry sits. The same Bonde sales gate applies: a covered name with declining revenue is hidden, because a hand-drawn level under a shrinking business is exactly the knife. Check the snapshot date in the note — old levels describe an old chart.',
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

/** `s` marks an extended-hours bar ('pre' | 'ah') on the live frame so the
 *  chart can shade it; absent on regular-hours and daily bars. */
export type CmBar = { t: string; o: number; h: number; l: number; c: number; v: number; s?: string };
// `neutral` is a range that is neither a floor nor a lid — the 0DTE gamma
// walls, which bracket where dealer hedging is expected to contain the tape.
// Colouring it green or red would imply a direction it does not have.
export type CmBand = { kind: 'base' | 'demand' | 'supply' | 'neutral'; lo: number; hi: number; label?: string };
export type CmLineTone = 'buy' | 'stop' | 'target' | 'now' | 'neutral';
export type CmLine = { price: number; label: string; tone: CmLineTone };
export type CmMarker = { date: string; label?: string; kind?: string; price?: number };
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
  /** Demand boards only — names hidden because price already ran >= bounce_done_pct
   *  off the band top (Ajay 2026-09-03: the arrival is over). */
  dropped_bounced?: number;
  bounce_done_pct?: number;
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
  /** gabbar tab: the band-type lens the server measured against, its menu,
   *  and how many covered names had no band of that type. */
  level?: string;
  level_choices?: string[];
  without_level?: number;
  touching_only?: boolean;
  away_hidden?: number;
  scanned?: number;
  universe_key?: string;
  universe_label?: string;
  /** The universes the SERVER offers. Preferred over the frontend's
   *  fallback list so adding one backend-side needs no FE deploy. */
  universe_choices?: { key: string; label: string }[];
  generated_at?: string | number | null;
  scan_generated_at?: string | number | null;
  /** ict tab (2026-09-03): when the engine last scanned, how far the dormant
   *  loop got (macro pass → tapped names → micro runs), every owner constant
   *  with its value, and the source the rules are cited to. `params` is
   *  rendered verbatim under the board so a changed threshold is visible
   *  without a frontend deploy. */
  as_of?: string | null;
  counts?: { macro_n?: number; tapped_n?: number; micro_n?: number } | null;
  /** The backend (ict/engine.py params()) sends a LIST of {key, value,
   *  from_video, note} so the two values the video actually states are never
   *  listed as house rules; a flat {key: value} map is accepted too. */
  params?: IctParamIn[] | Record<string, number | string | boolean | null> | null;
  source?: {
    video?: string | null;
    /** Plain stamps ("02:39") or {at, rule} objects — ictSource() renders both. */
    timestamps?: (string | { at?: string | null; rule?: string | null } | null)[] | null;
  } | null;
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
  // The Into Supply slot was replaced by ICT on 2026-09-03 (Ajay: "replace
  // supply tab with this new tab"). An old ?tab=supply bookmark lands on the
  // tab that took its place rather than falling back to VCP — same slot,
  // same neighbourhood, and the backend still resolves "supply" on its side.
  if (t === 'supply') return 'ict';
  return (CM_TABS as string[]).includes(t) ? (t as CmTab) : 'vcp';
}

/* ── ICT tab (Ajay 2026-09-03) ────────────────────────────────────────────── */

/** Where the rules come from — Ajay's own spec plus this walkthrough. The
 *  timestamps are the ones cited in backend/ict/ for each rule; the backend
 *  echoes the same URL in the board's `source`, this copy is for the blurb
 *  link when the board has not loaded yet. */
export const ICT_SOURCE = {
  label: 'Jesse Rogers',
  url: 'https://www.youtube.com/watch?v=Q7Ryv1M7CvI',
  timestamps: [
    { at: '02:39', rule: 'manipulation = a sweep with no displacement' },
    { at: '03:57', rule: 'stacked consolidations on the way to a higher-timeframe FVG' },
    { at: '05:30', rule: 'Power of 3 — accumulation range first, then the manipulation below it' },
  ],
} as const;

export type IctBias = 'all' | 'bullish' | 'bearish';
export type IctMicro = '60m' | '15m';

/** Server defaults — kept OUT of the query string when unchanged so the
 *  common URL stays clean and one cache key serves the default board. */
export const DEFAULT_ICT_BIAS: IctBias = 'all';
export const DEFAULT_ICT_MICRO: IctMicro = '60m';

export const ICT_BIASES: { key: IctBias; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'bullish', label: 'Bullish' },
  { key: 'bearish', label: 'Bearish' },
];

/** The trigger timeframe. 60m is the video's "micro" clock; 15m is offered
 *  because the same frame_for() resample serves it — nothing else changes. */
export const ICT_MICROS: { key: IctMicro; label: string }[] = [
  { key: '60m', label: '60m' },
  { key: '15m', label: '15m' },
];

export function parseBias(raw: string | null | undefined): IctBias {
  const v = (raw || '').trim().toLowerCase();
  return v === 'bullish' || v === 'bearish' ? v : DEFAULT_ICT_BIAS;
}

export function parseMicro(raw: string | null | undefined): IctMicro {
  const v = (raw || '').trim().toLowerCase();
  return v === '15m' ? '15m' : DEFAULT_ICT_MICRO;
}

/** Plain-language names for the owner constants the backend echoes in
 *  `params`. Every one of these is a house value — "owner rule, not from the
 *  video" — which is exactly why they are listed under the board instead of
 *  buried in code. Keys are matched case-insensitively so the backend is free
 *  to spell them either way; a key not listed here still renders, by name, so
 *  a new constant can never be hidden by an out-of-date frontend map. */
export const ICT_PARAM_LABELS: Record<string, string> = {
  fractal_window: 'swing point: bars each side (1 = 3-candle fractal)',
  stack_min: 'stacked consolidations: min count',
  atr_period: 'ATR period (the range unit every ATR rule uses)',
  consol_min_bars: 'consolidation: min bars',
  consol_max_atr: 'consolidation: max span (× ATR14)',
  displace_max_atr: 'manipulation: max close-through (× ATR, 0 = must close back above)',
  displace_min_atr: 'displacement: min body (× ATR)',
  confirm_max_bars: 'displacement: within N bars of the sweep',
  mss_fvg_within_bars: 'MSS: new gap within N bars of the close',
  stack_lookback_bars: 'stacked consolidations: bars searched',
  n_swings: 'daily swings kept as key levels',
  tap_lookback: 'tap window (daily sessions)',
  tap_tol_pct: 'tap tolerance (% of level)',
  entry_tol_pct: 'entry: within % of the zone',
  stop_buffer_atr: 'stop buffer under the wick (× micro ATR)',
  micro_max: 'micro runs per scan (cap)',
  budget_sec: 'scan budget (seconds)',
  ict_ttl_sec: 'cache TTL before a background re-scan (seconds)',
  keep_days: 'dated scans kept (days)',
  macro_min_bars: 'daily frame: min bars to read',
  micro_min_bars: 'micro frame: min bars to read',
  macro_fvg_lookback: 'daily gaps: bars searched',
  macro_fvg_keep: 'daily gaps: newest kept',
  liq_window: 'liquidity: avg $ volume window (days)',
  grade_manipulation: 'grade: manipulation found',
  grade_displacement: 'grade: opposite displacement',
  grade_mss: 'grade: market structure shift',
  grade_entry: 'grade: at the entry zone',
};

/** One entry of the backend's `params` list (ict/engine.py params()). */
export type IctParamIn = {
  key?: string | null; value?: unknown; from_video?: boolean | null; note?: string | null;
};

export type IctParamRow = { key: string; label: string; value: string; fromVideo: boolean };

/** `params` → rows for the settings list: known constants first in the
 *  order the rules are applied (levels → tap → consolidation → manipulation →
 *  displacement → entry → plan → ops), then anything unlisted, by name. A
 *  missing or malformed payload gives [] — the list simply does not draw.
 *
 *  Two shapes are accepted. The backend contract is a LIST of
 *  {key, value, from_video, note} — `from_video` is what lets the page keep
 *  the two values the video states (3-candle fractal, "two or more"
 *  consolidations) out of the "not from the video" group. A flat
 *  {key: value} map still works and counts every entry as an owner rule. */
export function ictParamRows(params: CmBoard['params']): IctParamRow[] {
  if (!params || typeof params !== 'object') return [];
  const order = Object.keys(ICT_PARAM_LABELS);
  const rows: IctParamRow[] = [];
  const push = (k: unknown, v: unknown, fromVideo: boolean) => {
    if (v === null || v === undefined) return;
    if (typeof v === 'object') return;                    // nested → not a constant
    const key = typeof k === 'string' ? k.trim() : '';
    if (!key) return;
    const norm = key.toLowerCase();
    rows.push({ key, label: ICT_PARAM_LABELS[norm] || key, value: String(v), fromVideo });
  };
  if (Array.isArray(params)) {
    for (const p of params) {
      if (!p || typeof p !== 'object' || Array.isArray(p)) continue;
      push(p.key, p.value, p.from_video === true);
    }
  } else {
    for (const [k, v] of Object.entries(params)) push(k, v, false);
  }
  rows.sort((a, b) => {
    const ia = order.indexOf(a.key.toLowerCase());
    const ib = order.indexOf(b.key.toLowerCase());
    if (ia >= 0 && ib >= 0) return ia - ib;
    if (ia >= 0) return -1;
    if (ib >= 0) return 1;
    return a.key.localeCompare(b.key);
  });
  return rows;
}

/** Tile legend for the ICT board. Mirrors what chart_maps/board.py ict_tiles
 *  draws and what PatternChart does with each kind: bands by kind, lines by
 *  tone, markers by kind (sweep / bos = small glyphs, buy / sell = candle
 *  tags). Written here rather than in the page so it is a fixed list the
 *  tests can hold to the backend contract. */
export const ICT_LEGEND: { glyph: string; label: string; hint: string }[] = [
  { glyph: '▭', label: 'accumulation', hint: 'the Power-of-3 range the manipulation dips below (grey box)' },
  { glyph: '🟩', label: 'FVG ↑', hint: 'active bullish fair value gap (Low[i+2] > High[i]) — support' },
  { glyph: '🟥', label: 'FVG ↓', hint: 'active bearish fair value gap (High[i+2] < Low[i]) — resistance' },
  { glyph: '▦', label: 'IFVG', hint: 'inverted gap: a candle CLOSED through the far edge, so it flips role (neutral box)' },
  { glyph: '🎯', label: 'entry', hint: 'the IFVG or the new gap — the zone the plan buys / sells in' },
  { glyph: '┈', label: 'key low / key high', hint: 'the daily swing levels the 60m loop is watching' },
  { glyph: '⤵', label: 'MANIP', hint: 'the sweep bar — wick through the level, close back inside (no displacement)' },
  { glyph: '↗', label: 'MSS', hint: 'market structure shift — close past the last opposing swing with a new FVG' },
  { glyph: '▲▼', label: 'IFVG tag', hint: 'the entry bar, tagged under (bullish) or over (bearish) the candle' },
  { glyph: '— —', label: 'STOP / TARGET', hint: 'stop = manipulation extreme ± buffer; target = the next daily swing (external liquidity)' },
];

/** The source line under the ICT board. The backend echoes `source` as
 *  {video, timestamps}; the stamps may arrive as plain strings ("02:39") or as
 *  {at, rule} objects (the ICT_SOURCE.timestamps shape) — both render as the
 *  bare stamps and anything else is dropped rather than printed as
 *  "[object Object]". A missing or non-http video URL falls back to the
 *  frontend copy so the name is always a working link. */
export function ictSource(source: CmBoard['source']): { url: string; stamps: string } {
  const video = source && typeof source === 'object' ? source.video : null;
  const url = typeof video === 'string' && /^https?:\/\//i.test(video.trim())
    ? video.trim() : ICT_SOURCE.url;
  const raw = source && typeof source === 'object' && Array.isArray(source.timestamps)
    ? source.timestamps : [];
  const stamps: string[] = [];
  for (const t of raw) {
    if (typeof t === 'string') { if (t.trim()) stamps.push(t.trim()); continue; }
    if (t && typeof t === 'object' && typeof t.at === 'string' && t.at.trim()) stamps.push(t.at.trim());
  }
  const shown = stamps.length ? stamps : ICT_SOURCE.timestamps.map((t) => t.at);
  return { url, stamps: shown.join(' · ') };
}

/** Deep link to a ticker's SEPA detail page. Default 'supply' (Ajay
 *  2026-09-03: "go Supply and Demand tab in all pages"; was 'setup' since
 *  2026-08-17). SepaCandidate silently falls back to Supply / Demand on an
 *  unknown value, so a typo here is invisible — hence the test.
 *  NOTE: dead at runtime — the live tiles take `href` from the backend
 *  (chart_maps/board.py _href, also defaulting to supply). Kept as the
 *  frontend statement of the same rule; tests only. */
export function sepaHref(symbol: string, tab: 'setup' | 'supply' | 'breakout' = 'supply'): string {
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
  minTier?: string; gabbarLevel?: string; gabbarTouchingOnly?: boolean;
  phase?: string; target?: string;
  bias?: string; micro?: string;
}): string {
  const q = new URLSearchParams({ tab: p.tab });
  // Reaching vs already reached (Ajay 2026-08-31, extended same day to "all
  // the tabs possible"). Demand boards: default reached, only 'approaching'
  // rides on the URL. Lens tabs (undervalue, gabbar): default ALL, so both
  // explicit phases ride. Zones alone takes the level flavour (order_block),
  // on either phase — reached+order_block = IN the block on first touch.
  if ((p.tab === 'zones' || p.tab === 'deep_demand') && p.phase === 'approaching') {
    q.set('phase', 'approaching');
  }
  if ((p.tab === 'undervalue' || p.tab === 'gabbar')
      && (p.phase === 'approaching' || p.phase === 'reached')) {
    q.set('phase', p.phase);
  }
  if (p.tab === 'zones' && p.target === 'order_block') {
    q.set('target', 'order_block');
  }
  if (p.limit) q.set('limit', String(p.limit));
  if (p.days) q.set('days', String(p.days));
  // Both demand boards read ONE demand_reentry cache, so the universe
  // choice governs both or the two tabs would describe different scans.
  if ((p.tab === 'zones' || p.tab === 'supply') && p.universe) {
    q.set('universe', p.universe);
  }
  // Gabbar band-type lens (2026-08-25). Only sent when it narrows something —
  // 'all' is the server default and would just noise up the common URL.
  if (p.tab === 'gabbar' && p.gabbarLevel && p.gabbarLevel !== 'all') {
    q.set('level', p.gabbarLevel);
  }
  // Touching-only became the opt-IN (2026-08-27: "just show me all of them
  // there") — only the narrowing value rides on the URL.
  if (p.tab === 'gabbar' && p.gabbarTouchingOnly === true) {
    q.set('touching_only', 'true');
  }
  // ICT (2026-09-03): bias narrows the board to one side of the sweep, micro
  // picks the trigger timeframe. Both are server defaults when omitted, and
  // both are ict-only — the other boards have no sweep side and no second
  // clock, so a leaked param would just split their cache keys.
  if (p.tab === 'ict' && p.bias && p.bias !== DEFAULT_ICT_BIAS) {
    q.set('bias', p.bias);
  }
  if (p.tab === 'ict' && p.micro && p.micro !== DEFAULT_ICT_MICRO) {
    q.set('micro', p.micro);
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
/** Axis ticks for whichever bars these are: intraday bars (HH:MM stamps)
 *  get session ticks — the date at each new day, 09:30 and 16:00 in between
 *  — so a two-session live chart reads "Sep 1 · 09:30 · 16:00 · Sep 2 …"
 *  instead of a single "Sep". Daily bars keep the month ticks. */
export function timeTicks(bars: CmBar[], max = 8): { i: number; label: string }[] {
  if (!bars.length || (bars[0].t || '').length <= 10) return monthTicks(bars, max);
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const ticks: { i: number; label: string; major: boolean }[] = [];
  let prevDay = '';
  let openTicked = true;
  bars.forEach((b, i) => {
    const day = b.t.slice(0, 10);
    const hm = b.t.slice(11, 16);
    if (day !== prevDay) {
      prevDay = day;
      openTicked = false;
      const m = Number(day.slice(5, 7)); const d = Number(day.slice(8, 10));
      ticks.push({ i, label: `${MON[m - 1] || ''} ${d}`, major: true });
      return;
    }
    // Bars are RIGHT-labelled by the resampler, so no bar is ever stamped
    // exactly 09:30 — the first RTH bar of the day carries 09:35/09:45/10:00.
    // Tick the first bar at or after the bell instead (and, on the live
    // frame, the first bar that is not extended-hours).
    if (!openTicked && hm >= '09:30' && !b.s) {
      openTicked = true;
      ticks.push({ i, label: 'open', major: false });
    } else if (hm === '16:00') {
      ticks.push({ i, label: '16:00', major: false });
    }
  });
  if (ticks.length <= max) return ticks.map(({ i, label }) => ({ i, label }));
  const majors = ticks.filter((t) => t.major);
  const minors = ticks.filter((t) => !t.major);
  // Day boundaries are thinned too when there are more of them than fit —
  // a 47-session hourly frame produced 48 labels smeared along the axis
  // (review 2026-09-02). Minors are dropped first, then majors are stepped.
  if (majors.length >= max) {
    const step = Math.ceil(majors.length / max);
    return majors.filter((_, k) => k % step === 0).map(({ i, label }) => ({ i, label }));
  }
  const room = max - majors.length;
  const step = room > 0 ? Math.ceil(minors.length / room) : 0;
  const kept = step > 0 ? minors.filter((_, k) => k % step === 0) : [];
  return [...majors, ...kept].sort((a, b) => a.i - b.i)
    .map(({ i, label }) => ({ i, label }));
}

export function monthTicks(bars: CmBar[], max = 6): { i: number; label: string }[] {
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const ticks: { i: number; label: string; year: string }[] = [];
  let prev = '';
  bars.forEach((b, i) => {
    const mo = (b.t || '').slice(0, 7);
    if (mo && mo !== prev) {
      prev = mo;
      const m = Number(mo.slice(5, 7));
      if (m >= 1 && m <= 12) ticks.push({ i, label: MON[m - 1], year: mo.slice(0, 4) });
    }
  });
  const shown = ticks.length <= max
    ? ticks
    : ticks.filter((_, i) => i % Math.ceil(ticks.length / max) === 0);
  // Years on the SHOWN set, decided after thinning: the first tick and every
  // year change carry theirs ("Aug '25 … Feb '26"). A year-long window reading
  // "Aug Nov Feb May Aug" left which-Aug-is-which to guesswork (Ajay
  // 2026-09-01: "add years to the calendar months at the bottom").
  let prevYear = '';
  return shown.map((t) => {
    const label = t.year && t.year !== prevYear
      ? `${t.label} '${t.year.slice(2)}` : t.label;
    prevYear = t.year || prevYear;
    return { i: t.i, label };
  });
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
  defense: '🎖 Defense',
  rare_earth: '⛏ Rare earth',
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
