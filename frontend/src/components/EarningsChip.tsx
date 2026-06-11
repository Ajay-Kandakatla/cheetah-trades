/* EarningsChip — "⚠ ER Jun 15 · AMC" on every buy surface (Ajay 2026-06-11,
 * after entering ATEX the day it reported AMC and missed by 28%).
 *
 * Renders ONLY when the symbol's next earnings is within the warn window
 * (default 7 days, EARNINGS_WARN_DAYS) — red when today/tomorrow, amber
 * otherwise. Clicking opens the symbol on EarningsWhispers (the user's
 * preferred calendar) in a new tab; inside <Link>-wrapped cards pass
 * asLink={false} (nested anchors are invalid HTML) and it renders a span
 * with the same warning + tooltip. Dates come from our yfinance-backed
 * cache — the tooltip says to verify, dates can shift. */
import { EARNINGS_WARN_DAYS, type EarningsInfo } from '../hooks/useEarningsMap';

const RED = '#ef4444';
const AMBER = '#f59e0b';

function fmtDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${names[(m || 1) - 1]} ${d}${y ? '' : ''}`;
}

export function EarningsChip({ symbol, info, asLink = true, warnDays = EARNINGS_WARN_DAYS }: {
  symbol: string;
  info: EarningsInfo | undefined;
  asLink?: boolean;
  warnDays?: number;
}) {
  if (!info || info.days_to > warnDays) return null;
  const urgent = info.days_to <= 1;
  const color = urgent ? RED : AMBER;
  const label = info.days_to === 0
    ? `⚠ EARNINGS TODAY${info.when ? ` · ${info.when}` : ''}`
    : info.days_to === 1
      ? `⚠ ER tomorrow${info.when ? ` · ${info.when}` : ''}`
      : `⚠ ER ${fmtDate(info.date)}${info.when ? ` · ${info.when}` : ''}`;
  const title = `${symbol} reports earnings ${info.date}` +
    (info.when === 'BMO' ? ' before the open' : info.when === 'AMC' ? ' after the close' : '') +
    ` (${info.days_to} day${info.days_to === 1 ? '' : 's'}). Buying into a report is a gap bet,` +
    ' not a SEPA entry. Source: yfinance — verify on EarningsWhispers (click).';
  const style: React.CSSProperties = {
    display: 'inline-flex', alignItems: 'center',
    fontSize: '0.7rem', fontWeight: 700, lineHeight: 1.4,
    padding: '2px 8px', borderRadius: 6, whiteSpace: 'nowrap',
    color, background: `${color}1a`, border: `1px solid ${color}66`,
    textDecoration: 'none', cursor: asLink ? 'pointer' : 'default',
  };
  if (!asLink) {
    return <span style={style} title={title}>{label}</span>;
  }
  return (
    <a
      href={`https://www.earningswhispers.com/stocks/${encodeURIComponent(symbol.toLowerCase())}`}
      target="_blank"
      rel="noopener noreferrer"
      title={title}
      style={style}
      onClick={(e) => e.stopPropagation()}
    >
      {label}
    </a>
  );
}
