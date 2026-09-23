/* tvChart — a PRE-CONFIGURED TradingView chart per symbol, as a LINK-OUT.
 *
 * Ajay 2026-08-31: "also give me a trading view pre configured chart please."
 *
 * Deliberately a plain URL to tradingview.com, NOT an embedded chart: the
 * TradingView Charting Library application was refused (2026-08-16 — they
 * require a public website and this app is auth-gated), so the licensed
 * embed is off the table. The public chart page needs no license, opens in
 * his own TV account with his own layout, and takes symbol + interval in
 * the query string — which is all "pre configured" needs to mean here.
 */

/** Session-view timeframes → TradingView interval codes. Daily otherwise.
 *
 *  Kept in step with supply_demand/timeframes.TIMEFRAMES (five frames since
 *  2026-09-22). The two RETIRED keys keep their rows on purpose: `parseTf`
 *  resolves an old `?tf=5m_live` link to `24h`, but a caller that still holds
 *  the raw key — a bookmarked TV button, a stale prop — must open the
 *  5-minute chart rather than silently dropping to daily. */
const TV_INTERVAL: Record<string, string> = {
  '5m_today': '5',
  '24h': '5',
  '15m': '15',
  '60m': '60',
  daily: 'D',
  // retired 2026-09-22 → 24h / 15m; same bar size, so same interval.
  '5m_live': '5',
  '15m_open': '15',
};

export function tvChartUrl(symbol: string, tf?: string): string {
  // TradingView writes share classes with a dot; this app's universe uses
  // the dash style (BRK-B, CWEN-A).
  const sym = symbol.trim().toUpperCase().replace(/-/g, '.');
  const interval = TV_INTERVAL[tf || 'daily'] || 'D';
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(sym)}`
    + `&interval=${interval}`;
}

/** Shared click handler: the tile is wrapped in a router <Link>, so the TV
 *  button must both stop the bubble AND cancel the tile navigation. */
export function openTvChart(
  e: { preventDefault(): void; stopPropagation(): void },
  symbol: string, tf?: string,
): void {
  e.preventDefault();
  e.stopPropagation();
  window.open(tvChartUrl(symbol, tf), '_blank', 'noopener');
}
