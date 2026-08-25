import { Link, useLocation } from 'react-router-dom';
import type { CSSProperties, ReactNode, MouseEvent } from 'react';
import { WatchlistButton } from './WatchlistButton';
import { TickerPrice } from './TickerPrice';
import { NAV_SOURCES, sourceKeyFor, withSource } from '../lib/navSource';

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
  /** Land on a specific tab instead of the default chart tab, e.g. 'setup'.
   *  Rides in the URL as `?tab=`, so it survives reload and Cmd-click. */
  tab?: string;
  /** A `NAV_SOURCES` key, written as `?from=` so the destination's back button
   *  still works after a tab click drops the router state. */
  fromKey?: string;
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
  showWatchlist = true, showPrice = false, tab, fromKey,
}: Props) {
  const location = useLocation();
  // Built as a real query string rather than router state: state is dropped by
  // the destination's own `setSearchParams(..., {replace: true})` on the first
  // tab click, and never existed at all for a Cmd-clicked or bookmarked link.
  const qs = new URLSearchParams();
  if (tab) qs.set('tab', tab);
  // The durable source signal. Explicit fromKey wins; otherwise it is derived
  // from where this link is RENDERED. Derived rather than opt-in because the
  // opt-in version was forgotten on most Supply & Demand links, and a link
  // opened in a fresh tab (Cmd-click / middle-click) has no router state and
  // no history — without ?from= its back button hard-falls to /sepa
  // (Ajay 2026-08-24: "it goes to sepa always").
  const effectiveKey = fromKey && NAV_SOURCES[fromKey]
    ? fromKey
    : sourceKeyFor(location.pathname);
  if (effectiveKey) qs.set('from', effectiveKey);
  const to = `/sepa/${encodeURIComponent(ticker)}${qs.size ? `?${qs}` : ''}`;
  const handleClick = (e: MouseEvent<HTMLAnchorElement>) => {
    // Modifier keys (Cmd/Ctrl/Shift) → let the browser handle (new tab/window).
    // Middle-click is button=1 — also let browser handle.
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    if (onPlainClick) onPlainClick(e);
  };

  const link = (
    <Link
      to={to}
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
  // Same derivation as the component: the new-tab branch below starts with no
  // state and no history, so ?from= is the ONLY thing its back button can use.
  const url = withSource(`/sepa/${encodeURIComponent(ticker)}`,
                         sourceKeyFor(location.pathname) || '');
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
