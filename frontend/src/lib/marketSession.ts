/**
 * marketSession — shared market-session detector + display-price picker.
 *
 * Replaces the boolean `isMarketHours()` guard with a four-state enum
 * (`pre` / `live` / `after` / `closed`) and a helper that decides which
 * price to render based on session + the available extended-hours fields
 * from /sepa/live-prices.
 *
 * The US_MARKET_HOLIDAYS calendar is the single source of truth for
 * non-trading-day detection — MarketClockStrip.tsx re-exports its copy
 * but new callers should import from here.
 */

export type MarketSession = 'pre' | 'live' | 'after' | 'closed';

export interface LivePrice {
  price:             number;
  change_pct:        number | null;
  volume:            number | null;
  /** Most recent trade price across ALL sessions (regular + extended). */
  last_trade_price?: number | null;
  /** Trade timestamp in ms epoch — use to tell if it was a regular-session
   *  or extended-hours print. */
  last_trade_ts_ms?: number | null;
  /** Previous regular session's close — the baseline for computing the
   *  extended-hours % change. */
  prev_day_close?:   number | null;
}

// ============================================================================
// US market holidays — full closures only (NYSE + NASDAQ).
// Mirrors backend/market_hours/reminder.py HOLIDAYS_2026/2027. Update yearly
// when NYSE publishes the next year's calendar:
// https://www.nyse.com/markets/hours-calendars
// Keys are YYYY-MM-DD; values are human-readable holiday names for display.
// ============================================================================
export const US_MARKET_HOLIDAYS: Record<string, string> = {
  // 2026
  '2026-01-01': "New Year's Day",
  '2026-01-19': 'MLK Jr Day',
  '2026-02-16': 'Presidents Day',
  '2026-04-03': 'Good Friday',
  '2026-05-25': 'Memorial Day',
  '2026-06-19': 'Juneteenth',
  '2026-07-03': 'Independence Day (observed)',
  '2026-09-07': 'Labor Day',
  '2026-11-26': 'Thanksgiving',
  '2026-12-25': 'Christmas',
  // 2027
  '2027-01-01': "New Year's Day",
  '2027-01-18': 'MLK Jr Day',
  '2027-02-15': 'Presidents Day',
  '2027-03-26': 'Good Friday',
  '2027-05-31': 'Memorial Day',
  '2027-06-18': 'Juneteenth (observed)',
  '2027-07-05': 'Independence Day (observed)',
  '2027-09-06': 'Labor Day',
  '2027-11-25': 'Thanksgiving',
  '2027-12-24': 'Christmas (observed)',
};

/** Get YYYY-MM-DD for the given Date in US Eastern (the market's TZ). */
export function dateKeyET(d: Date): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York',
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(d);
  const y = parts.find(p => p.type === 'year')?.value;
  const m = parts.find(p => p.type === 'month')?.value;
  const da = parts.find(p => p.type === 'day')?.value;
  return `${y}-${m}-${da}`;
}

/** Returns the current US market session based on the time and the
 *  holiday calendar. Sessions (US Eastern):
 *    pre    — 04:00–09:30
 *    live   — 09:30–16:00
 *    after  — 16:00–20:00
 *    closed — 20:00–04:00, weekends, US market holidays
 */
export function getMarketSession(now: Date = new Date()): MarketSession {
  // Weekend
  const wday = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', weekday: 'short',
  }).format(now);
  if (wday === 'Sat' || wday === 'Sun') return 'closed';
  // Holiday
  if (US_MARKET_HOLIDAYS[dateKeyET(now)]) return 'closed';
  // ET hour+minute as a single decimal number
  const etParts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(now);
  // hour12:false sometimes yields "24" for midnight — normalize to 0
  const hourRaw = etParts.find(p => p.type === 'hour')?.value || '0';
  const hh = hourRaw === '24' ? 0 : parseInt(hourRaw, 10);
  const mm = parseInt(etParts.find(p => p.type === 'minute')?.value || '0', 10);
  const t = hh + mm / 60;
  if (t >= 4.0  && t <  9.5)  return 'pre';
  if (t >= 9.5  && t < 16.0)  return 'live';
  if (t >= 16.0 && t < 20.0)  return 'after';
  return 'closed';
}

/** Decide which price to display + how to compute change. Rules:
 *    - Regular session: day.close + day's % change
 *    - Pre-market / After-hours: lastTrade.p with change vs prevDay.c
 *    - Closed: prefer regular close (with day-change pct), else null.
 *
 *  Returns null when the LivePrice is missing or has no usable price for
 *  the current session.
 */
export function pickDisplayPrice(
  livePrice: LivePrice | undefined,
  session:   MarketSession,
): { price: number; change_pct: number | null; source: 'live' | 'extended' | 'close' } | null {
  if (!livePrice) return null;
  if (session === 'live') {
    if (livePrice.price == null) return null;
    return {
      price:      livePrice.price,
      change_pct: livePrice.change_pct ?? null,
      source:     'live',
    };
  }
  if (session === 'pre' || session === 'after') {
    const p = livePrice.last_trade_price ?? livePrice.price;
    const prev = livePrice.prev_day_close ?? livePrice.price;
    if (p == null) return null;
    const change = prev ? ((p - prev) / prev) * 100 : null;
    return { price: p, change_pct: change, source: 'extended' };
  }
  // Closed — prefer regular close. If price is null, fall through to
  // last_trade_price (e.g. weekend display of Friday's last extended print).
  if (livePrice.price != null) {
    return {
      price:      livePrice.price,
      change_pct: livePrice.change_pct ?? null,
      source:     'close',
    };
  }
  if (livePrice.last_trade_price != null) {
    const prev = livePrice.prev_day_close;
    const change = prev ? ((livePrice.last_trade_price - prev) / prev) * 100 : null;
    return {
      price:      livePrice.last_trade_price,
      change_pct: change,
      source:     'extended',
    };
  }
  return null;
}
