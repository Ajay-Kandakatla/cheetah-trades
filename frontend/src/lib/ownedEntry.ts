/** Per-share entry price for a held position, used to drive the on-card hold/sell
 *  verdict (PositionSignal → /sepa/position-lens). Preference order:
 *    1. broker / Plaid average cost (`avg_cost`)
 *    2. the user-typed entry (`entry`)
 *    3. total cost basis ÷ shares (`cost_basis / quantity`)
 *  Returns null when there is no usable cost basis, so the card renders nothing
 *  (the verdict needs an entry to measure the Minervini stop from). Ajay 2026-06-22.
 */
export function resolveOwnedEntry(
  owned: {
    avg_cost?: number | null;
    entry?: number | null;
    cost_basis?: number | null;
    quantity?: number | null;
  } | null | undefined,
): number | null {
  if (!owned) return null;
  if (owned.avg_cost && owned.avg_cost > 0) return owned.avg_cost;
  if (owned.entry && owned.entry > 0) return owned.entry;
  if (owned.cost_basis && owned.quantity && owned.quantity > 0) {
    return owned.cost_basis / owned.quantity;
  }
  return null;
}
