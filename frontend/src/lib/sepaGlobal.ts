/* SEPA Global — the dumbed-down, jargon-free view over the SAME Minervini scan.
 *
 * Ajay 2026-06-23: a minimal scanner for friends with little trading experience.
 * It must follow Minervini's exact rules (same backend gates — Trend Template
 * qualifier, is_buyable breakout, setup_ready base, climax/distribution = sell)
 * but present them in plain English with a traffic-light verdict and a clear
 * risk number. No VCP / ADR / CMF / stage / whales jargon.
 *
 * This is a pure presentation transform — it invents NO new signals, it only
 * relabels the gates the scanner already computed. Risk-first, like the book. */
import type { SepaCandidate } from '../hooks/useSepa';

export type GlobalTab = 'buy' | 'watch' | 'leaders';
export type GlobalVerdict = 'buy' | 'watch' | 'avoid' | 'leader';
export type Strength = 'High' | 'Medium' | 'Low';

export type GlobalCard = {
  symbol: string;
  name: string | null;
  price: number | null;
  dayChangePct: number | null;
  verdict: GlobalVerdict;
  verdictLabel: string;
  /** Traffic-light tone key the page maps to a colour. */
  tone: 'green' | 'amber' | 'red' | 'slate';
  reason: string;
  buyZone: { lo: number; hi: number } | null;
  /** "Sell if it falls to" price — the stop, in plain terms. */
  sellIf: number | null;
  /** % you'd risk from the buy point down to the stop. */
  riskPct: number | null;
  strength: Strength;
};

function num(x: unknown): number | null {
  return typeof x === 'number' && Number.isFinite(x) ? x : null;
}

/** A name institutions are selling — a SELL in the book, never a buy
 *  (climax-top distribution / churn breakout, TTLAC pp.186-188). Mirrors the
 *  scanner's own gate so the verdict can never say "buy" on one. */
export function isAvoid(row: SepaCandidate): boolean {
  return (
    row.entry_exit?.decision === 'AVOID' ||
    row.distribution_selling === true ||
    (row as any).climax_distribution?.is_distribution === true
  );
}

/** Conviction (0-100, return potential) → a friendly High / Medium / Low.
 *  A suppressed (climax/exhaustion) name is always Low — it's a sell. */
export function strengthOf(row: SepaCandidate): Strength {
  if (row.conviction_detail?.suppressed) return 'Low';
  const c = num(row.conviction) ?? 0;
  if (c >= 70) return 'High';
  if (c >= 45) return 'Medium';
  return 'Low';
}

/** The plain-English verdict + everything the card shows. Same gates as the
 *  admin SEPA page, relabelled — never a new signal. */
export function toGlobalCard(row: SepaCandidate): GlobalCard {
  const price = num(row.last_close) ?? num(row.trend?.price);
  const plan = row.trade_plan;
  const ee = row.entry_exit;

  const buyZone =
    plan?.buy_zone && num(plan.buy_zone.lo) != null && num(plan.buy_zone.hi) != null
      ? { lo: plan.buy_zone.lo, hi: plan.buy_zone.hi }
      : ee?.entry && num(ee.entry.zone_lo) != null && num(ee.entry.zone_hi) != null
      ? { lo: ee.entry.zone_lo, hi: ee.entry.zone_hi }
      : null;

  const sellIf = num(plan?.stop?.recommended) ?? num(ee?.exit?.stop ?? null);

  // % at risk from the buy reference down to the stop (risk-first framing).
  let riskPct = num(plan?.stop?.risk_pct ?? null);
  if (riskPct == null) {
    const entryRef = buyZone?.lo ?? price;
    if (entryRef != null && sellIf != null && entryRef > 0 && sellIf < entryRef) {
      riskPct = ((entryRef - sellIf) / entryRef) * 100;
    }
  }

  let verdict: GlobalVerdict;
  let verdictLabel: string;
  let tone: GlobalCard['tone'];
  let reason: string;

  if (isAvoid(row)) {
    verdict = 'avoid';
    verdictLabel = 'Avoid';
    tone = 'red';
    reason = 'Big investors look to be selling into the run — stay away for now.';
  } else if (row.is_buyable) {
    verdict = 'buy';
    verdictLabel = 'Buy zone';
    tone = 'green';
    reason = 'Confirmed breakout in a strong uptrend — it’s in the buy zone now.';
  } else if (row.setup_ready) {
    verdict = 'watch';
    verdictLabel = 'Watch';
    tone = 'amber';
    reason = 'Setting up in an uptrend — not triggered yet. Wait for the breakout.';
  } else {
    verdict = 'leader';
    verdictLabel = 'Leader';
    tone = 'slate';
    reason = 'A strong stock in a confirmed uptrend — keep it on your radar.';
  }

  return {
    symbol: row.symbol,
    name: row.name ?? null,
    price,
    dayChangePct: num(row.day_change_pct),
    verdict,
    verdictLabel,
    tone,
    reason,
    buyZone,
    sellIf,
    riskPct: riskPct == null ? null : Math.round(riskPct * 10) / 10,
    strength: strengthOf(row),
  };
}

/** Buyable-first, then by conviction — IDENTICAL ordering to the admin SEPA
 *  page so the "best ideas" float up the same way. */
export function byConviction(a: SepaCandidate, b: SepaCandidate): number {
  const ab = a.is_buyable ? 1 : 0;
  const bb = b.is_buyable ? 1 : 0;
  if (ab !== bb) return bb - ab;
  return (b.conviction ?? -1) - (a.conviction ?? -1);
}

/** The three minimal tabs map to the scanner's own gates:
 *   buy     → is_buyable (a confirmed breakout, ready now)
 *   watch   → setup_ready but not yet triggered
 *   leaders → every Trend-Template qualifier (the watch-the-best list) */
export function filterForTab(rows: SepaCandidate[], tab: GlobalTab): SepaCandidate[] {
  const base =
    tab === 'buy'
      ? rows.filter((r) => r.is_buyable === true)
      : tab === 'watch'
      ? rows.filter((r) => r.setup_ready === true && r.is_buyable !== true)
      : rows.filter((r) => r.is_candidate === true);
  return [...base].sort(byConviction);
}
