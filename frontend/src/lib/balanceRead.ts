/**
 * Balance-sheet read for the 🚀 Explosive Growth board.
 *
 * Ajay 2026-09-14: *"In the explosive growth segment add a new indicator to
 * show me balance sheet and Debt. I do not want them to have any debt."*
 *
 * WHY THIS IS NOT A LITERAL ZERO-DEBT TEST
 * ────────────────────────────────────────
 * Measured on the live board the day he asked: of 29 qualifying names,
 * **zero** carry literally no debt. A `debt === 0` filter returns an empty
 * board, every time, forever. Even FF — which prints $0M — is rounding; it
 * carries a few hundred thousand.
 *
 * What he actually means by "no debt" is what a US filer can actually be:
 * borrowings so small against its own cash that debt is not part of the story.
 * So the top tier is RELATIVE — debt under `DEBT_FREE_RATIO` of cash — and on
 * that definition the same 29-row board returns 7 names, including CRDO
 * itself (debt $26M against cash $764M, 3.4%).
 *
 * The four tiers are ordered, and `DEBT_TIER_ORDER` is the sort/filter axis:
 *
 *   debt-free  debt < 5% of cash          7 of 29 — PTGX SNDK IPI CRDO KOPN FF ALAB
 *   net cash   cash > debt                9 of 29 — MU NVDA TER STAA AXTI SITM CDE …
 *   modest     net debt inside half cash  1 of 29
 *   levered    everything past that      12 of 29 — NLY −$124.7B, RKT −$29.7B …
 *
 * THE FIFTH STATE IS NOT A TIER, AND THAT MATTERS
 * ───────────────────────────────────────────────
 * The backend already ships `balance_meaningful: false` for mortgage REITs,
 * BDCs and lenders — NLY, ARR, DX, RKT, DBRG, HHH on the live board. For those
 * businesses **debt IS the product**: leverage is how a mortgage REIT earns,
 * not a weakness in it. Grading NLY "levered" would be like grading a bank
 * "levered" — technically true, analytically meaningless, and it would push
 * six names into a red bucket for doing their job.
 *
 * So they read `n/a` and the filter EXCLUDES them rather than failing them,
 * because "I do not want them to have any debt" cannot be evaluated on a
 * balance sheet where debt is the input. The chip says so in words.
 */

export type DebtTier = 'debt-free' | 'net cash' | 'modest' | 'levered' | 'n/a' | 'unknown';

/** Debt under this fraction of cash reads as debt-free. See the note above. */
export const DEBT_FREE_RATIO = 0.05;

/** Net debt worse than this fraction of cash drops out of "modest". */
export const MODEST_NET_DEBT_RATIO = 0.5;

/** Best to worst. The filter keeps a prefix of this list. */
export const DEBT_TIER_ORDER: DebtTier[] = [
  'debt-free', 'net cash', 'modest', 'levered', 'n/a', 'unknown',
];

export const DEBT_TIER_LABEL: Record<DebtTier, string> = {
  'debt-free': 'No debt',
  'net cash': 'Net cash',
  modest: 'Some debt',
  levered: 'Levered',
  'n/a': 'Debt is the business',
  unknown: 'Not reported',
};

/**
 * The CSS class per tier, written out rather than interpolated.
 *
 * `eg-bal-${tier}` would be shorter and the frontend contract checker cannot
 * verify it — it sees the literal `.eg-bal-` and reports a class that ships
 * with no rule. Spelling them out means every class that can reach the DOM is
 * greppable in the source, which is the whole point of that contract.
 */
export const DEBT_TIER_CLASS: Record<DebtTier, string> = {
  'debt-free': 'eg-bal-debtfree',
  'net cash': 'eg-bal-netcash',
  modest: 'eg-bal-modest',
  levered: 'eg-bal-levered',
  'n/a': 'eg-bal-na',
  unknown: 'eg-bal-unknown',
};

export const DEBT_TIER_HINT: Record<DebtTier, string> = {
  'debt-free': `Borrowings under ${Math.round(DEBT_FREE_RATIO * 100)}% of cash — debt is not part of this story.`,
  'net cash': 'Holds more cash than debt, but the debt is real.',
  modest: 'Net debt, but inside half its cash pile.',
  levered: 'Net debt beyond half its cash.',
  'n/a': 'A lender, mortgage REIT or BDC — leverage is how it earns, so a debt grade would be meaningless.',
  unknown: 'The filing did not report enough to judge.',
};

export type BalanceInput = {
  cash?: number | null;
  debt?: number | null;
  cash_minus_debt?: number | null;
  balance_meaningful?: boolean | null;
};

export type BalanceRead = {
  tier: DebtTier;
  label: string;
  hint: string;
  /** The exact class to put on the chip. See DEBT_TIER_CLASS. */
  cls: string;
  /** Debt as a percent of cash. null when cash is absent or zero. */
  debtPctOfCash: number | null;
  net: number | null;
};

/**
 * Grade one row's balance sheet.
 *
 * Order matters: the `balance_meaningful === false` check runs FIRST, before
 * any arithmetic, so a mortgage REIT can never fall through into "levered" on
 * the strength of numbers that do not mean for it what they mean elsewhere.
 */
export function balanceRead(row: BalanceInput): BalanceRead {
  const mk = (tier: DebtTier, debtPctOfCash: number | null, net: number | null): BalanceRead => ({
    tier, label: DEBT_TIER_LABEL[tier], hint: DEBT_TIER_HINT[tier],
    cls: DEBT_TIER_CLASS[tier], debtPctOfCash, net,
  });

  if (row.balance_meaningful === false) return mk('n/a', null, row.cash_minus_debt ?? null);

  const cash = num(row.cash);
  const debt = num(row.debt);
  if (cash === null || debt === null) return mk('unknown', null, num(row.cash_minus_debt));

  const net = num(row.cash_minus_debt) ?? cash - debt;
  // Guard the zero-cash case explicitly: a company with no cash and no debt is
  // debt-free; one with no cash and any debt is not, and dividing would give
  // Infinity for both.
  const pctOfCash = cash > 0 ? (debt / cash) * 100 : (debt <= 0 ? 0 : null);

  if (cash > 0 && debt / cash < DEBT_FREE_RATIO) return mk('debt-free', pctOfCash, net);
  if (cash <= 0 && debt <= 0) return mk('debt-free', pctOfCash, net);
  if (net > 0) return mk('net cash', pctOfCash, net);
  if (cash > 0 && net > -MODEST_NET_DEBT_RATIO * cash) return mk('modest', pctOfCash, net);
  return mk('levered', pctOfCash, net);
}

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/**
 * Does this row pass a filter that keeps everything down to `worst`?
 *
 * TWO DELIBERATE ASYMMETRIES, and the difference between them is the whole
 * point of this function:
 *
 *   'unknown' ALWAYS PASSES. Hiding a name because the filing did not report
 *   enough to grade it is not what "I do not want them to have any debt"
 *   means — that is a silent data-quality drop dressed up as a screen result.
 *   It passes carrying its "Not reported" chip so he can see the gap and judge
 *   it himself. (Caught by the existing board tests: every fixture row lacks
 *   cash/debt, and a filter that dropped them emptied the table.)
 *
 *   'n/a' NEVER PASSES. A mortgage REIT or lender does not merely have debt,
 *   debt is its entire funding model — NLY carries $125B of it. Excluding it
 *   from a no-debt screen IS his instruction, and unlike 'unknown' it is a
 *   positive finding rather than an absence of one.
 */
export function passesDebtFilter(row: BalanceInput, worst: DebtTier): boolean {
  const t = balanceRead(row).tier;
  if (t === 'unknown') return true;
  if (t === 'n/a') return false;
  const limit = DEBT_TIER_ORDER.indexOf(worst);
  const here = DEBT_TIER_ORDER.indexOf(t);
  return here >= 0 && limit >= 0 && here <= limit;
}
