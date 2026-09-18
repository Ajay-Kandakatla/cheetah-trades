/* 📣 EarningsFreshChip — "this name JUST REPORTED", on the 🚀 Explosive Growth tab.
 *
 * Ajay 2026-09-17: "make a remindder ro scan explosive growth of new earnings
 * stocks and high light them to me in explosive growth tab".
 *
 * A CALENDAR FACT AND NOTHING ELSE. It does not reorder the board, does not
 * filter it, does not change a flag, a gate, or whether the trading engine will
 * buy the row. There is no measurement in this app that a just-reported grower
 * outperforms — the nearest prior, the 8-K event study of 2026-09-01, measured
 * NO chase edge after a fresh print — so the tooltip says so in capitals rather
 * than letting a badge imply an edge nobody measured.
 *
 * RENDERS NOTHING when the name did not just report (the ExplosiveChip /
 * GrowthChip pattern), so on a normal day it costs zero pixels. Measured on his
 * own board the day it shipped: 0 of 21 names qualified.
 *
 * PROP-FED, ALWAYS. The window, the day count and the BMO/AMC read all come off
 * the payload — `window_days` is the backend's own
 * sepa.earnings_picks.REPORT_WINDOW_DAYS, never a number typed here, and
 * `days_ago` is never recomputed in the browser.
 *
 * DATES ARE FORMATTED BY EarningsChip.fmtDate, imported verbatim. The Date
 * CONSTRUCTOR is FORBIDDEN in this file — a contracts check greps for it — because
 * it parses a bare ISO date as UTC and renders the PREVIOUS day in ET:
 * `TZ=America/New_York node -e "..."` on '2026-09-16' prints "Sep 15".
 */
import { fmtDate } from './EarningsChip';

export type EarningsFresh = {
  known?: boolean; reported_on?: string | null;
  when?: 'BMO' | 'AMC' | null; days_ago?: number | null;
  fresh?: boolean; surprise_pct?: number | null; window_days?: number | null;
};

export function EarningsFreshChip({ symbol, read, className = 'cm-badge' }: {
  symbol: string;
  read?: EarningsFresh | null;
  className?: string;
}) {
  if (!read?.fresh || !read.reported_on) return null;
  const days = read.days_ago;
  const when = read.when === 'BMO' || read.when === 'AMC' ? read.when : null;
  const suffix = when ? ` · ${when}` : '';
  /* No `when` suffix on the today branch: an AMC report dated today is still
   * UPCOMING (the market has not seen the numbers), and last_report.date can
   * never equal today, so the only reachable today-case is BMO/unknown. */
  const text = days === 0
    ? '📣 reported today'
    : days === 1
      ? `📣 reported yesterday${suffix}`
      : `📣 reported ${fmtDate(read.reported_on)}${suffix}`;

  const whenWords = when === 'BMO'
    ? ', before the open'
    : when === 'AMC' ? ', after the close' : '';
  const n = typeof days === 'number' ? days : 0;
  const surprise = typeof read.surprise_pct === 'number' && !Number.isNaN(read.surprise_pct)
    ? ` Reported EPS ${read.surprise_pct >= 0 ? 'beat' : 'missed'} the estimate by ` +
      `${Math.abs(read.surprise_pct).toFixed(1)}%.`
    : '';
  const title =
    `${symbol} reported earnings on ${read.reported_on}${whenWords} — ${n} day` +
    `${n === 1 ? '' : 's'} ago, inside this board's ${read.window_days ?? ''}-day ` +
    'just-reported window (the same window the Earnings report picks list uses). ' +
    "A CALENDAR FACT, NOT A SIGNAL: it does not change this row's order, its " +
    'demand read, its flags, or whether the trading engine will buy it. Nothing on ' +
    'this board is measured. Source: yfinance via the earnings calendar — verify on ' +
    'EarningsWhispers, dates can shift.' + surprise;

  return (
    <span className={`${className} ${className}-earnings`} title={title}>{text}</span>
  );
}
