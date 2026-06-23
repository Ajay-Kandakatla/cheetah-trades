/* 3-C cheat tag visibility (TTLAC §7).
 *
 * The backend tags any qualifier forming a cup-completion cheat (sepa/cheat.py).
 * Ajay's rule: only SHOW the chip in the book's actual use case — a RED
 * (risk_off) market with NO buyable pivots. Cheats develop during a general
 * market correction and the leaders that rally off them bottom first
 * (TTLAC §7 ebook p.123/p.133); when there's nothing to buy the normal
 * breakout way, the cheat is where tomorrow's leaders are setting up. The rest
 * of the time the tag stays hidden so it never clutters the lean card.
 *
 * Two pure functions: the page-level REGIME gate, and the per-row combine. */

/** The display regime: a red market with zero buyable breakouts ("no pivots").
 *  `buyableCount` is the scan's count of is_buyable names. */
export function isCheatRegime(
  marketState?: string | null,
  buyableCount?: number | null,
): boolean {
  return marketState === 'risk_off' && (buyableCount ?? 0) <= 0;
}

/** Show the cheat chip on a card: the row must BE a cheat AND the regime gate
 *  must be open (red + no pivots). */
export function isCheatVisible(
  cheatSetup?: boolean | null,
  cheatRegime?: boolean,
): boolean {
  return Boolean(cheatSetup) && Boolean(cheatRegime);
}

/** Tooltip copy for the chip — the why, with the book cite. */
export const CHEAT_TOOLTIP =
  'Forming a 3-C cheat — Minervini’s earliest (aggressive) entry, inside the ' +
  'base before a breakout. Shown only in a red market with no breakouts, ' +
  'where leaders bottom first (TTLAC §7). Informational — the engine does not ' +
  'trade it.';
