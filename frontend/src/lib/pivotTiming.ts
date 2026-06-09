/* ==========================================================================
   pivotTiming — Minervini entry-timing math for the pivot meter.

   Encodes the book's buy rule (Trade Like a Stock Market Wizard, Ch. 10,
   pp.197-205): the right pullback is the FINAL, tightest contraction on the
   right side of the base where volume dries up; you BUY when price crosses
   ABOVE the pivot (that contraction's high) on EXPANDING volume — not during
   the dip, and not chasing far past the pivot.

   Pure, deterministic, reads only fields already on the scan row — no fetch.
   This is the single source of truth for both the per-card PivotMeter and the
   "Closest to trigger" sort, so they can never disagree.
   ========================================================================== */
import type { SepaCandidate } from '../hooks/useSepa';

/** Book-tight pivot: the final right-side contraction is a narrow 3-5% pullback
 *  on dried-up volume (pp.198, 202 — FSII 5% handle, VIVO 3% pivot). We treat
 *  ≤5% as a "textbook-tight" pivot (user 2026-06-02: "5% is good"). */
export const TIGHT_PIVOT_MAX_PCT = 5;
/** Volume-confirmed breakout: today's volume > 1.5× the 50-day average
 *  (book p.203, "on expanding volume"). Mirrors backend volume.py. */
export const BREAKOUT_VOL_MULT = 1.5;
/** Buy zone ceiling above the pivot — don't chase more than this % past it
 *  (book p.224, "a few percentage points"). MUST match the backend buyable gate
 *  scanner.BUYABLE_MAX_EXT_PCT so the meter's "Extended" line and is_buyable agree
 *  (user-approved 3%, 2026-06-09; was 5%). */
export const BUY_ZONE_PCT = 3;
/** "Close to trigger" band — within this % BELOW the pivot the name is coiling
 *  right under the buy point (about to break out). Mirror of the buy-zone width;
 *  a UX convenience around the book's buy-on-the-cross rule (pp.198-205). */
export const NEAR_PIVOT_PCT = 5;
/** A breakout counts as "recent" (≤1wk) up to this many trading days back. */
export const RECENT_BREAKOUT_MAX_DAYS = 5;

export type PivotState = 'GO' | 'AT_PIVOT' | 'COILING' | 'WAIT' | 'NOT_STAGE2' | 'EXTENDED' | 'NONE';
export type PivotTone = 'go' | 'warn' | 'wait' | 'bad' | 'none';

export type PivotTiming = {
  hasSetup: boolean;
  setupType: string | null;
  pivot: number | null;
  stop: number | null;
  current: number | null;
  zoneHi: number | null;
  /** Signed % of current vs pivot: <0 below (needs to rise), >0 above. */
  distToPivotPct: number | null;
  /** Today's volume ÷ 50-day average (null when data missing). */
  volRatio: number | null;
  /** Volume-confirmed breakout fired today or within the last ~5 trading days. */
  breakingOut: boolean;
  daysSinceBreakout: number | null;
  /** Volume dried up in the base (constructive). */
  drying: boolean;
  /** Final contraction ≤ 5% — a textbook-tight Minervini pivot. */
  pivotTight: boolean;
  finalContractionPct: number | null;
  /** Already AT/through the pivot inside the +5% buy zone (GO or AT_PIVOT) —
   *  buyable now, not extended, not a non-Stage-2 false break. */
  inBuyZone: boolean;
  /** Coiling right UNDER the pivot — within NEAR_PIVOT_PCT below it and not yet
   *  triggered. "Close to the trigger", a watch-for-the-break list. */
  nearPivot: boolean;
  state: PivotState;
  label: string;
  tone: PivotTone;
};

const LABELS: Record<PivotState, { label: string; tone: PivotTone }> = {
  GO:        { label: 'GO · at pivot on volume', tone: 'go' },
  AT_PIVOT:  { label: 'At pivot · needs volume', tone: 'warn' },
  COILING:   { label: 'Coiling · volume dried', tone: 'wait' },
  WAIT:      { label: 'Wait · below pivot', tone: 'wait' },
  NOT_STAGE2:{ label: 'Wait · not Stage 2 yet', tone: 'wait' },
  EXTENDED:  { label: 'Extended · don’t chase', tone: 'bad' },
  NONE:      { label: 'No setup', tone: 'none' },
};

export function pivotTiming(row: SepaCandidate): PivotTiming {
  const setup = row.entry_setup ?? null;
  const ee = row.entry_exit?.entry ?? null;
  const vol = row.volume ?? null;
  const vcp = row.vcp ?? null;

  const pivot = setup?.pivot ?? vcp?.pivot_buy_price ?? null;
  const stop = setup?.stop ?? vcp?.suggested_stop ?? null;
  const current = ee?.current ?? row.last_close ?? null;
  const zoneHi = ee?.zone_hi ?? (pivot != null ? pivot * (1 + BUY_ZONE_PCT / 100) : null);

  const distToPivotPct =
    pivot != null && current != null && pivot > 0 ? ((current - pivot) / pivot) * 100 : null;

  const lastVol = vol?.last_vol ?? null;
  const avgVol = vol?.avg_vol_50 ?? null;
  const volRatio = lastVol != null && avgVol && avgVol > 0 ? lastVol / avgVol : null;

  const daysSinceBreakout = vol?.days_since_breakout ?? null;
  const above = current != null && pivot != null && current >= pivot;
  const breakingOut = Boolean(
    vol?.high_vol_breakout ||
      (daysSinceBreakout != null && daysSinceBreakout <= RECENT_BREAKOUT_MAX_DAYS) ||
      (volRatio != null && volRatio >= BREAKOUT_VOL_MULT && above),
  );
  const drying = Boolean(vol?.is_drying_up || vcp?.volume_drying);

  const finalContractionPct = vcp?.final_contraction_pct ?? null;
  const pivotTight = finalContractionPct != null && finalContractionPct <= TIGHT_PIVOT_MAX_PCT;

  const hasSetup = setup != null && pivot != null;

  // Book buyable-eligibility (pp.39-71 stage analysis; pp.79-83 Trend Template):
  // Minervini buys ONLY a confirmed Stage 2 advance. Mirror the backend gate
  // (scanner._is_setup_ready, surfaced as setup_ready) so the meter can never
  // flash a green GO on a Stage 1 base that fired a one-day volume pop (the
  // SMCI-class bug, 2026-06-02). is_buyable is a strict superset → also eligible.
  const stage2 = row.stage?.stage === 2;
  const eligible =
    row.is_buyable === true ||
    row.setup_ready === true ||
    (row.setup_ready == null && stage2);

  // State machine — book pp.198-205. You buy the breakout ABOVE the pivot on
  // expanding volume (GO), after the right-side pullback tightens on dried
  // volume (COILING). In the zone but volume light = not yet (AT_PIVOT). At/above
  // the pivot but NOT a Stage 2 setup = NOT_STAGE2 (not a buy by the book).
  // Below pivot, no dry-up = WAIT. Past the buy zone = EXTENDED (don't chase).
  let state: PivotState = 'NONE';
  if (hasSetup && current != null && pivot != null) {
    const extended = zoneHi != null && current > zoneHi;
    if (extended) state = 'EXTENDED';
    else if (above && !eligible) state = 'NOT_STAGE2';
    else if (above && breakingOut) state = 'GO';
    else if (above) state = 'AT_PIVOT';
    else if (drying) state = 'COILING';
    else state = 'WAIT';
  }

  // Two actionable buckets derived from the same state machine:
  //  • inBuyZone — at/through the pivot, within the +5% zone (GO / AT_PIVOT).
  //  • nearPivot — below the pivot but within NEAR_PIVOT_PCT, coiling toward the
  //    trigger (COILING / WAIT). Excludes extended / not-Stage-2 / no-setup.
  const inBuyZone = state === 'GO' || state === 'AT_PIVOT';
  const nearPivot =
    (state === 'COILING' || state === 'WAIT') &&
    distToPivotPct != null && distToPivotPct < 0 && distToPivotPct >= -NEAR_PIVOT_PCT;

  return {
    hasSetup,
    setupType: setup?.type ?? null,
    pivot,
    stop,
    current,
    zoneHi,
    distToPivotPct,
    volRatio,
    breakingOut,
    daysSinceBreakout,
    drying,
    pivotTight,
    finalContractionPct,
    inBuyZone,
    nearPivot,
    state,
    label: LABELS[state].label,
    tone: LABELS[state].tone,
  };
}

/** "Most buyable" sort key — lower = more buyable (user 2026-06-02: "sort by
 *  enter, vcp most buyable after a scan").
 *
 *  Ranks PRIMARILY by the pivot-meter STATE — the same price-vs-pivot + volume
 *  read the user sees on the card — so a name that is `is_buyable` only via an
 *  in-base pocket pivot while still BELOW its breakout pivot (e.g. FRST: buyable,
 *  but price $14.68 < pivot $14.84, meter = WAIT) ranks as a WAIT, NOT at the top.
 *  Earlier this used raw `is_buyable`, which floated below-pivot pocket-pivots
 *  above cleaner breakouts (user 2026-06-02: "shouldn't be right").
 *
 *  State order: GO (at/through pivot on volume) → AT_PIVOT → COILING → WAIT →
 *  EXTENDED → none. VCP preferred within a state; `is_buyable` at/above the pivot
 *  (a confirmed breakout buy) gets a small nudge to the very top. Then composite
 *  score, then closeness to pivot. */
const STATE_RANK: Record<PivotState, number> = {
  GO: 0, AT_PIVOT: 1, COILING: 2, WAIT: 3, NOT_STAGE2: 4, EXTENDED: 5, NONE: 6,
};

export function buyabilityRank(row: SepaCandidate, t: PivotTiming): number {
  const vcp = row.entry_setup?.type === 'VCP';
  let base = STATE_RANK[t.state] ?? 6;
  // A confirmed breakout buy (is_buyable AND price at/through the pivot) edges
  // ahead within its state band — but a below-pivot pocket pivot does NOT.
  if (row.is_buyable && (t.state === 'GO' || t.state === 'AT_PIVOT')) base -= 0.5;
  const tier = base * 2 + (vcp ? 0 : 1);          // VCP preferred within a state
  const score = row.score ?? 0;
  const dist = t.distToPivotPct == null ? 999 : Math.abs(t.distToPivotPct);
  return tier * 1e6 - score * 100 + dist;          // state first, then score desc, then closeness
}

/** Sort key for "Closest to trigger" — lower = nearer the buy.
 *  GO first, then in-zone, then below-pivot by smallest gap (coiling beats
 *  loose wait at equal distance), extended/none last. */
export function triggerRank(t: PivotTiming): number {
  if (!t.hasSetup || t.distToPivotPct == null) return 1e9;
  switch (t.state) {
    case 'GO':       return -1000 + (t.distToPivotPct ?? 0);
    case 'AT_PIVOT': return -500 + (t.distToPivotPct ?? 0);
    case 'COILING':  return Math.abs(t.distToPivotPct) - (t.pivotTight ? 0.5 : 0);
    case 'WAIT':     return Math.abs(t.distToPivotPct) + 0.25;
    case 'NOT_STAGE2': return 5e5 + Math.abs(t.distToPivotPct);  // at pivot but not Stage 2 — not a buy
    case 'EXTENDED': return 1e6 + t.distToPivotPct;   // past the zone — bottom
    default:         return 1e9;
  }
}
