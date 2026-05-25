import { Link, useLocation } from 'react-router-dom';
import type { CSSProperties, ReactNode, MouseEvent } from 'react';
import { WatchlistButton } from './WatchlistButton';
import { TickerPrice } from './TickerPrice';

type Props = {
  ticker: string;
  /** Human-readable source label for the back-button on the destination page.
   *  Defaults to "previous" if omitted. */
  fromLabel?: string;
  className?: string;
  style?: CSSProperties;
  title?: string;
  children?: ReactNode;
  /** Optional pre-click side effect — runs only on plain (no-modifier) click,
   *  before navigation. Use this to e.g. close an open panel. */
  onPlainClick?: (e: MouseEvent<HTMLAnchorElement>) => void;
  /** Set to false to hide the watchlist ★ icon next to the ticker. */
  showWatchlist?: boolean;
  /** Set to true to render a small price tag next to the ticker. */
  showPrice?: boolean;
};

/**
 * TickerLink — renders a "click here to open ticker X" CTA as a real
 * <a href="/sepa/X"> anchor, so Cmd-click / Ctrl-click / middle-click /
 * right-click → "Open in new tab" all work natively (browser handles it).
 *
 * Plain click is intercepted by React Router and turned into client-side
 * navigation, with the source page recorded in `state` so the destination's
 * "← Back" button knows where to return.
 *
 * Drop-in replacement for any `<button onClick={() => nav(`/sepa/${t}`)}>`
 * — pass the same `className` and the styling carries over (CSS rules on
 * a class apply equally to <button> and <a>).
 */
export function TickerLink({
  ticker, fromLabel, className, style, title, children, onPlainClick,
  showWatchlist = true, showPrice = false,
}: Props) {
  const location = useLocation();
  const handleClick = (e: MouseEvent<HTMLAnchorElement>) => {
    // Modifier keys (Cmd/Ctrl/Shift) → let the browser handle (new tab/window).
    // Middle-click is button=1 — also let browser handle.
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    if (onPlainClick) onPlainClick(e);
  };

  const link = (
    <Link
      to={`/sepa/${encodeURIComponent(ticker)}`}
      state={{
        from: location.pathname + location.search,
        label: fromLabel,
      }}
      onClick={handleClick}
      className={`tk-link${className ? ' ' + className : ''}`}
      style={style}
      title={title}
    >
      {children ?? ticker}
    </Link>
  );

  // If neither extra is requested, render the bare link to preserve existing
  // layouts that depend on TickerLink being a single inline element.
  if (!showWatchlist && !showPrice) return link;

  return (
    <span className="tk-wrap" onClick={(e) => e.stopPropagation()}>
      {link}
      {showPrice && <TickerPrice ticker={ticker} compact />}
      {showWatchlist && <WatchlistButton ticker={ticker} />}
    </span>
  );
}


/**
 * openTickerWithModifier — for callsites where you can't easily switch to
 * <Link> (e.g. table rows that already have onClick + other handlers,
 * or buttons inside a form).
 *
 * Usage:
 *   onClick={(e) => openTickerWithModifier(e, navigate, location, ticker, 'Pioneers')}
 *
 * Honours Cmd/Ctrl/middle/Shift-click → opens in new tab.
 */
export function openTickerWithModifier(
  e: MouseEvent | undefined,
  navigate: (path: string, opts?: any) => void,
  location: { pathname: string; search: string },
  ticker: string,
  fromLabel?: string,
) {
  const url = `/sepa/${encodeURIComponent(ticker)}`;
  if (e && (e.metaKey || e.ctrlKey || e.shiftKey || (e as any).button === 1)) {
    window.open(url, '_blank', 'noopener,noreferrer');
    return;
  }
  navigate(url, {
    state: {
      from: location.pathname + location.search,
      label: fromLabel,
    },
  });
}
