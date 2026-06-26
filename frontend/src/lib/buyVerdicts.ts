/* Shared types + helpers for the batch Cheetah-Verdict lookup (GET /sepa/verdicts)
 * used by the Auto-Pilot positions table and the Portfolio cards. */
import type { BuyVerdict } from '../components/BuyVerdictChip';

/** The slim verdict the batch endpoint returns — a BuyVerdict plus a few
 *  display extras. Shape-compatible with BuyVerdict so it feeds BuyVerdictChip
 *  directly. */
export type SlimVerdict = BuyVerdict & {
  symbol?: string;
  rs?: number | null;
  stage?: number | null;
  score?: number | null;
  is_etf?: boolean;
};

/** Stable fetch key for a set of symbols (uppercased, de-duped, sorted) so the
 *  hook doesn't refetch on array-identity churn. */
export function verdictsKey(symbols: string[]): string {
  return Array.from(new Set((symbols || []).map((s) => String(s).trim().toUpperCase())))
    .filter(Boolean)
    .sort()
    .join(',');
}
