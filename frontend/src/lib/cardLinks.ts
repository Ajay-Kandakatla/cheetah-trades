/* 🚩 Gajjala card click → the ⤢ three-chart view, and a separate SEPA page link (2026-11-16, spec ggcard3 §3.5).
 *
 * Ajay 2026-11-16: "Also when I click on a card from any of the Gajjala I would like us to open the 3 chart extension
 * like in the Watch list... Also put a SEPA page link for it separaetely on the card" and then "Actually instead of
 * 3 mins make it 15 mins timeframe".
 *
 * The structural words and test ids PatternChart prints when a board passes `onOpenView` (opt-in; every other board
 * keeps the whole card as its SEPA link). No sentence about a stock lives here. */

/** The action-row link's label — his words ("SEPA page"). */
export const SEPA_LINK_LABEL = 'SEPA page';

export const sepaLinkTitle = (sym: string): string => `Open ${sym} on the SEPA page`;

export const sepaLinkTestId = (sym: string): string => `cm-sepa-link-${sym}`;

/** The card body's title / aria-label when it opens the ⤢ view (frames 15 / 5 / 1-minute). */
export const openViewTitle = (sym: string): string => `Open ${sym} — 15, 5 and 1-minute charts (⤢)`;

export const openViewTestId = (sym: string): string => `cm-openview-${sym}`;
