/* yahooLink — the external link-out top-right of every chart tile and on the Support tab head.
 *
 * Ajay 2026-11-09 (with a 🚩 card screenshot of the old ↗ button): "Instead of traderview I need yahoo finance link
 * here" / "To external ones please". It replaces lib/tvChart.ts (Ajay 2026-08-31: "also give me a trading view pre
 * configured chart please"), which is deleted; the Stock detail modal's chart embed is a different surface and is
 * unchanged.
 *
 * A plain link to Yahoo's quote page: the chart sits at the top of it and the float / shares outstanding / short
 * interest he keeps asking about are one tab away (Statistics). Yahoo has no interval parameter, so the tile's
 * timeframe is not carried.
 */
export const YAHOO_QUOTE_BASE = 'https://finance.yahoo.com/quote/';
export const YAHOO_LABEL = 'Yahoo ↗';

/** The quote page for a symbol. Yahoo writes share classes with a dash (BRK-B) — the style this app's universe
 *  already uses — so a dot class is rewritten to the dash, never the other way round. */
export function yahooQuoteUrl(symbol: string): string {
  const sym = symbol.trim().toUpperCase().replace(/\./g, '-');
  return `${YAHOO_QUOTE_BASE}${encodeURIComponent(sym)}/`;
}

export function yahooTitle(symbol: string): string {
  return `Open ${symbol} on Yahoo Finance`;
}

/** Shared click handler: the tile is wrapped in a router <Link>, so the button must both stop the bubble AND cancel
 *  the tile navigation before opening the tab. */
export function openYahoo(
  e: { preventDefault(): void; stopPropagation(): void },
  symbol: string,
): void {
  e.preventDefault();
  e.stopPropagation();
  window.open(yahooQuoteUrl(symbol), '_blank', 'noopener');
}
