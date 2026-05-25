import { useQuote } from '../hooks/useWatchlist';

/* ==========================================================================
   TickerPrice — small inline price tag for any ticker.
   Renders nothing while loading. Shows $price + day-change % once data arrives.
   ========================================================================== */

type Props = {
  ticker: string;
  /** When true, render a compact form (price only, no day %) */
  compact?: boolean;
};

export function TickerPrice({ ticker, compact = false }: Props) {
  const q = useQuote(ticker);
  if (!q || !q.ok || q.last_price == null) return null;
  return (
    <span className="ticker-price mono" title={`As of ${q.as_of ?? '—'}`}>
      <span className="ticker-price__num">${q.last_price.toFixed(2)}</span>
      {!compact && q.day_pct != null && (
        <span className={`ticker-price__day ${q.day_pct >= 0 ? 'is-up' : 'is-down'}`}>
          {q.day_pct >= 0 ? '▲' : '▼'} {Math.abs(q.day_pct).toFixed(2)}%
        </span>
      )}
    </span>
  );
}
