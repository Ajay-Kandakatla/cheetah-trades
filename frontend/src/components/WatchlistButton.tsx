import { useWatchlist } from '../hooks/useWatchlist';

/* ==========================================================================
   WatchlistButton — small star icon that toggles a ticker on the watchlist.
   Drop in next to any ticker symbol throughout the app.
   ========================================================================== */

type Props = {
  ticker: string;
  size?: 'sm' | 'md';
};

export function WatchlistButton({ ticker, size = 'sm' }: Props) {
  const { rows, add, remove } = useWatchlist();
  const t = ticker.toUpperCase();
  const onList = rows.some((r) => r.ticker === t);
  const status = rows.find((r) => r.ticker === t)?.status;

  const onClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (onList) {
      remove(t);
    } else {
      add(t);
    }
  };

  return (
    <button
      type="button"
      className={`wl-btn wl-btn--${size} ${onList ? 'is-active' : ''} ${status ? `is-${status}` : ''}`}
      onClick={onClick}
      aria-pressed={onList}
      aria-label={onList ? `Remove ${t} from watchlist` : `Add ${t} to watchlist`}
      title={onList
        ? `On watchlist (${status ?? 'unknown'}) — click to remove`
        : `Add ${t} to watchlist`}
    >
      {onList ? '★' : '☆'}
    </button>
  );
}
