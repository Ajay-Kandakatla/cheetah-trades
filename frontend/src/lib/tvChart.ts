/* tvChart — the TradingView link-out, BESIDE Yahoo ↗ (never instead of it).
 *
 * Ajay 2026-11-23 ~21:40 ET (verbatim): "Also add traderview charts on charts please.. Yahoo has been hard to configure"
 * · "Does trading view allow configurable chart with EMA and VWAP and also duration to 5 days?" · "I was see a 5 day
 * chart something on our 1 min, 5min and 15 min location". His answer on the question card: "TV ↗ button only" — a
 * `TV ↗` button right BEFORE `Yahoo ↗` that opens HIS OWN TradingView chart for that stock (and that frame when the
 * surface knows it). He saves the EMAs / VWAP / 5-day range in his TradingView layout himself; nothing of ours (lines,
 * zones, levels) travels to TradingView.
 *
 * History: Ajay 2026-08-31 "also give me a trading view pre configured chart please" built this file; 2026-11-09
 * (commit 70a625b9, "Instead of traderview I need yahoo finance link here") deleted it for lib/yahooLink.ts. Recreated
 * 2026-11-23 from that history with ONE change: a frame this file does not know now sends NO interval (TradingView then
 * opens his last-used interval) instead of falling back to daily.
 *
 * A plain URL to tradingview.com, never an embed (the Charting Library licence was refused 2026-08-16). Only the symbol
 * and the interval ride in the query string — never any user data.
 */
export const TV_CHART_BASE = 'https://www.tradingview.com/chart/';
export const TV_LABEL = 'TV ↗';

/** Frame keys (supply_demand/timeframes, the served `tf` on a tile href / the Support tab's `?tf=`) → TradingView
 *  interval codes — the 2026-08-31 map unchanged. The two RETIRED keys keep their rows: a stale holder of the raw key
 *  must still open the same bar size. A key not in this map → no interval param at all. */
export const TV_INTERVAL: Readonly<Record<string, string>> = {
  '1min': '1',
  '5m_today': '5',
  '24h': '5',
  '15m': '15',
  '60m': '60',
  daily: 'D',
  weekly: 'W',
  // retired 2026-09-22 → 24h / 15m; same bar size, so same interval.
  '5m_live': '5',
  '15m_open': '15',
};

/** The interval for a frame key, or null when the frame is unknown / absent. */
export function tvInterval(tf?: string | null): string | null {
  if (!tf) return null;
  return Object.prototype.hasOwnProperty.call(TV_INTERVAL, tf) ? TV_INTERVAL[tf] : null;
}

/** His TradingView chart for a symbol. TradingView writes share classes with a dot; this app's universe uses the dash
 *  style (BRK-B, CWEN-A), so a dash is rewritten to the dot (the 2026-08-31 rule). `&interval=` only when known. */
export function tvChartUrl(symbol: string, tf?: string | null): string {
  const sym = symbol.trim().toUpperCase().replace(/-/g, '.');
  const interval = tvInterval(tf);
  return `${TV_CHART_BASE}?symbol=${encodeURIComponent(sym)}`
    + (interval ? `&interval=${interval}` : '');
}

export function tvTitle(symbol: string): string {
  return `Open ${symbol} on your TradingView chart`;
}

export function tvLinkTestId(symbol: string): string {
  return `tv-link-${symbol.trim().toUpperCase()}`;
}

/** The frame a served tile href carries (`…?tab=supply&tf=5m_today`), or null. A junk href → null. */
export function tvTfFromHref(href?: string | null): string | null {
  if (!href) return null;
  const q = href.indexOf('?');
  if (q < 0) return null;
  try {
    return new URLSearchParams(href.slice(q + 1)).get('tf');
  } catch {
    return null;
  }
}

/** Shared click handler: a tile is wrapped in a router <Link>, so the button must both cancel the tile navigation AND
 *  stop the bubble before opening the new tab. */
export function openTvChart(
  e: { preventDefault(): void; stopPropagation(): void },
  symbol: string, tf?: string | null,
): void {
  e.preventDefault();
  e.stopPropagation();
  window.open(tvChartUrl(symbol, tf), '_blank', 'noopener,noreferrer');
}
