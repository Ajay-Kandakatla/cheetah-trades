/* undervalueView — the 💎 Under Value tab's two views (2026-09-29).
 *
 * Ajay 2026-09-29, verbatim: "create me another tab where valuations are wrong
 * based on analytics, this is purely driven by wrong valuation of the stocks in
 * the whole universe we have.. What I am looking for is great sales growth,
 * annual review but Market cap and stock price is very low at least 50% low
 * compared to peers." — then "Use the same tab actually".
 *
 * So the ask is a TOGGLE on the existing 💎 tab, not a new tab: `?uv=peers`
 * asks the server for the 🏷️ vs-peers view; absent (or anything else) is the
 * 💎 P/S ÷ growth board, unchanged. Mirrors chart_maps/undervalue_peers
 * (VIEW_PARAM / VIEW_PSG / VIEW_PEERS, pinned equal by contract). The server
 * decides every pass; this file compares no number.
 */

export const UV_VIEW_PARAM = 'uv';
export const UV_VIEW_PSG = 'psg';
export const UV_VIEW_PEERS = 'peers';
export type UvView = typeof UV_VIEW_PSG | typeof UV_VIEW_PEERS;

/** `?uv=` -> 'peers' only for "peers" (any case / spacing); anything else -> 'psg'. */
export function parseUvView(v: string | null | undefined): UvView {
  return typeof v === 'string' && v.trim().toLowerCase() === UV_VIEW_PEERS
    ? UV_VIEW_PEERS : UV_VIEW_PSG;
}

/** The URL value for a view — null for the default 💎 view (no `uv` rides). */
export function uvViewParam(v: UvView): string | null {
  return v === UV_VIEW_PEERS ? UV_VIEW_PEERS : null;
}

/** One served toggle option (undervalue_peers.view_block options). */
export type CmUndervalueViewOption = { key: string; label: string };

/** The served block every 💎 Under Value payload carries. header / note /
 *  counts / constants are null on the 💎 view. */
export type CmUndervalueView = {
  param: string;
  view: string;
  default: string;
  options: CmUndervalueViewOption[];
  measured: boolean;
  header: string | null;
  note: string | null;
  counts: Record<string, number> | null;
  constants: Record<string, number> | null;
};
