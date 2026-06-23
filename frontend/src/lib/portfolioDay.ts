/* Honest "today %" for a portfolio holding — the heatmap / Day-% sort value.
 *
 * Mirrors backend portfolio.snapshots.day_change_from_baseline. The bug it fixes
 * (Ajay 2026-06-23): the Portfolio heatmap coloured each tile with the QUOTE's
 * close-to-close day move (`day_pct`). For a position BOUGHT TODAY, below
 * yesterday's close, that counts a drop that happened before you owned it —
 * MUU read −24% on the map when the real position was −1.5%.
 *
 * Rule by baseline:
 *  - today_basis === 'prior_close' (held since before today) → the live
 *    close-to-close day move is correct and real-time.
 *  - otherwise (opened today, or baseline unknown) → measure from COST against
 *    the live price, exactly like the position's live P&L %.
 */
export function honestDayPct(args: {
  today_basis?: 'prior_close' | 'cost';
  livePrice?: number | null;
  quantity?: number | null;
  costBasis?: number | null;
  liveDayPct?: number | null; // the quote's close-to-close % (held positions)
  backendDayPct?: number | null; // backend day_change_pct, already baseline-corrected
}): number | null {
  const { today_basis, livePrice, quantity, costBasis, liveDayPct, backendDayPct } = args;

  // Held since before today → the market's close-to-close move is the truth.
  if (today_basis === 'prior_close') {
    return liveDayPct ?? backendDayPct ?? null;
  }

  // Opened today (or unknown baseline) → from cost, using the live price so it
  // still ticks. Never the quote's close-to-close (the pre-purchase dip bug).
  if (livePrice != null && quantity != null && costBasis != null && costBasis > 0) {
    return ((livePrice * quantity) / costBasis - 1) * 100;
  }

  // No live price / no cost → fall back to whatever the backend computed.
  return backendDayPct ?? null;
}
