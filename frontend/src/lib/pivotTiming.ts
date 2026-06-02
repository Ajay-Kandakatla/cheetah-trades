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
/** Buy zone ceiling above the pivot — don't chase more than ~5% past it. */
export const BUY_ZONE_PCT = 5;
/** A breakout counts as "recent" (≤1wk) up to this many trading days back. */
export const RECENT_BREAKOUT_MAX_DAYS = 5;

export type PivotState = 'GO' | 'AT_PIVOT' | 'COILING' | 'WAIT' | 'EXTENDED' | 'NONE';
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
  state: PivotState;
  label: string;
  tone: PivotTone;
};

const LABELS: Record<PivotState, { label: string; tone: PivotTone }> = {
  GO:       { label: 'GO · at pivot on volume', tone: 'go' },
  AT_PIVOT: { label: 'At pivot · needs volume', tone: 'warn' },
  COILING:  { label: 'Coiling · volume dried', tone: 'wait' },
  WAIT:     { label: 'Wait · below pivot', tone: 'wait' },
  EXTENDED: { label: 'Extended · don’t chase', tone: 'bad' },
  NONE:     { label: 'No setup', tone: 'none' },
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

  // State machine — book pp.198-205. You buy the breakout ABOVE the pivot on
  // expanding volume (GO), after the right-side pullback tightens on dried
  // volume (COILING). In the zone but volume light = not yet (AT_PIVOT).
  // Below pivot, no dry-up = WAIT. Past the buy zone = EXTENDED (don't chase).
  let state: PivotState = 'NONE';
  if (hasSetup && current != null && pivot != null) {
    const extended = zoneHi != null && current > zoneHi;
    if (extended) state = 'EXTENDED';
    else if (above && breakingOut) state = 'GO';
    else if (above) state = 'AT_PIVOT';
    else if (drying) state = 'COILING';
    else state = 'WAIT';
  }

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
    state,
    label: LABELS[state].label,
    tone: LABELS[state].tone,
  };
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
    case 'EXTENDED': return 1e6 + t.distToPivotPct;   // past the zone — bottom
    default:         return 1e9;
  }
}
