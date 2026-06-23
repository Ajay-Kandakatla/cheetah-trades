/* Breakout "marching toward R1 / R2" computation (Ajay 2026-06-16: "add the
 * stages to these columns now if they are s2 and if they marching towards r1 or
 * r2").
 *
 * R1 / R2 are the trade-plan R-multiple targets (entry + 1R / +2R — see
 * backend/analysis/trade_plan._targets) carried on each breakout-board row. We
 * answer: which overhead level is the stock climbing toward next, and how far
 * (%) above the current price is it?
 *
 *   price < R1        → "→ R1 (+x%)"   marching toward the first target
 *   R1 ≤ price < R2   → "→ R2 (+x%)"   cleared R1, climbing to the second
 *   price ≥ R2        → "Past R2"      extended beyond both targets
 *
 * Distance % = (target − price) / price × 100. Pure + display-only; never feeds
 * the score. */

export type MarchState = 'to_r1' | 'to_r2' | 'past_r2' | 'none';

export type March = {
  state: MarchState;
  label: string;        // "→ R1" | "→ R2" | "Past R2" | "—"
  pct: number | null;   // % above price to the ACTIVE target; null when none/past
  toR1Pct: number | null;
  toR2Pct: number | null;
};

const NONE: March = { state: 'none', label: '—', pct: null, toR1Pct: null, toR2Pct: null };

export function marchToTarget(
  price?: number | null,
  r1?: number | null,
  r2?: number | null,
): March {
  if (price == null || price <= 0) return NONE;

  const toR1Pct = r1 != null ? ((r1 - price) / price) * 100 : null;
  const toR2Pct = r2 != null ? ((r2 - price) / price) * 100 : null;

  // Still below R1 → marching toward the first target.
  if (r1 != null && price < r1) {
    return { state: 'to_r1', label: '→ R1', pct: toR1Pct, toR1Pct, toR2Pct };
  }
  // Cleared R1, still below R2 → marching toward the second target.
  if (r2 != null && price < r2) {
    return { state: 'to_r2', label: '→ R2', pct: toR2Pct, toR1Pct, toR2Pct };
  }
  // At/above R2 → extended past both targets.
  if (r2 != null && price >= r2) {
    return { state: 'past_r2', label: 'Past R2', pct: null, toR1Pct, toR2Pct };
  }
  // No usable target data (no R1/R2 on the row).
  return { ...NONE, toR1Pct, toR2Pct };
}

/** True when the name has already cleared its first target (R1) and is marching
 *  to — or past — R2: extended, no longer a fresh breakout. The Breakouts
 *  "fresh only" filter hides these to keep the board breakout-focused (Ajay
 *  2026-06-23, "do not show me the ones with r2"). A row with no R1/R2 data
 *  (state 'none') is NOT extended — it stays visible. */
export function isExtendedToR2(
  price?: number | null,
  r1?: number | null,
  r2?: number | null,
): boolean {
  const s = marchToTarget(price, r1, r2).state;
  return s === 'to_r2' || s === 'past_r2';
}

/* Stage tone/label for the breakouts table — Stan Weinstein / Minervini stage
 * analysis. Stage 2 (the advancing phase) is the only buyable stage (TLSW
 * "must be in Stage 2"); Stage 4 (decline) is avoid; 1/3 are muted. */
export type StageMeta = { label: string; tone: string; isStage2: boolean };

export function stageMeta(stage?: number | null, label?: string | null): StageMeta {
  const txt = label || (stage != null ? `Stage ${stage}` : '—');
  if (stage === 2) return { label: txt, tone: 'var(--positive, #10b981)', isStage2: true };
  if (stage === 4) return { label: txt, tone: 'var(--negative, #f87171)', isStage2: false };
  return { label: txt, tone: 'var(--cm-slate, #94a3b8)', isStage2: false };
}
