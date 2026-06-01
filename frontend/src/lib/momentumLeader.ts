/* Emerging Momentum Leader — the "catch the next ARM, just in time" fingerprint.
 *
 * ARM ran +95% in 9 days off an AI-demand earnings beat. The two names that ran
 * hardest (ARM, DDOG) shared a specific, rare cluster of LEADING signals that
 * the rest of the top picks didn't have — and crucially, this pattern has NO
 * VCP base and isn't a strict Power Play, so the scanner scored it "no setup"
 * (a middling 73). This detector flags that pattern from existing scan fields.
 *
 * Strict (ARM/DDOG-grade), high-conviction:
 *   • RS leader (a SEPA candidate, RS ≥ 70)
 *   • at/near new 52-wk highs — clear runway, no overhead (pct_below_high ≤ 5%)
 *   • heavy net buying — up/down dollar-volume ratio ≥ 1.9
 *   • money flowing in — CMF inflow
 *   • a pocket pivot — Minervini's pre-/continuation buy signal
 *
 * Frontend-only: all of these already ride on the candidate row, so this needs
 * no backend change and doesn't touch the contract-locked scoring.
 */
export function isMomentumLeader(row: any): boolean {
  const v = row?.volume || {};
  const tr = row?.trend || {};
  const pctBelowHigh = tr.pct_below_high;          // 0 = sitting at the 52-wk high
  const rs = row?.rs_rank ?? 0;
  return (
    rs >= 70 &&
    pctBelowHigh != null && pctBelowHigh <= 5 &&
    (v.up_down_vol_ratio ?? 0) >= 1.9 &&
    v.cmf_signal === 'inflow' &&
    v.pocket_pivot === true
  );
}

/** Tooltip text explaining why a name is (or would be) a momentum leader. */
export const MOMENTUM_LEADER_TOOLTIP =
  'Emerging Momentum Leader — the ARM/DDOG fingerprint: an RS leader at new ' +
  'highs (no overhead) with a pocket pivot, heavy net buying (up/down vol ≥ 1.9) ' +
  'and money flowing in. The pattern that runs hard but scores "no setup" ' +
  'because it has no base. Catches it just in time, before the biggest legs.';
