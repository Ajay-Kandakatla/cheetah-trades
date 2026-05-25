import type { CSSProperties } from 'react';

type Props = {
  ticker: string;
  /** When supplied, render direct sub-search links for each one. */
  subreddits?: string[];
  /** Compact mode = just icons + tooltips, no labels. Used in card chrome. */
  compact?: boolean;
  className?: string;
  style?: CSSProperties;
};

/**
 * ChatterDeepLinks — direct external links to live chatter sources for a
 * ticker. All open in new tabs.
 *
 * Two modes:
 *   default — labeled buttons in a horizontal row (used inside detail
 *             panels like Catalyst deep-dive, NodeThesisPanel, SEPA tabs)
 *   compact — small icon-only chips meant to sit inside card headers
 *             so the user can jump straight from a catalyst card without
 *             expanding the whole panel
 */
export function ChatterDeepLinks({ ticker, subreddits, compact, className, style }: Props) {
  const t = encodeURIComponent(ticker);
  const redditQ = encodeURIComponent(`"${ticker}" OR "$${ticker}"`);

  const links = [
    {
      key: 'st',
      href: `https://stocktwits.com/symbol/${t}`,
      label: 'Stocktwits',
      icon: '💬',
      title: `Live Stocktwits cashtag feed for $${ticker}`,
    },
    {
      key: 'reddit',
      href: `https://www.reddit.com/search/?q=${redditQ}&sort=new&t=week`,
      label: 'Reddit',
      icon: '🔥',
      title: `Reddit search for ${ticker}, sorted new, last week`,
    },
    {
      key: 'x',
      href: `https://x.com/search?q=%24${t}&src=cashtag_click&f=live`,
      label: 'Cashtag',
      icon: '𝕏',
      title: `X / Twitter cashtag $${ticker}, live`,
    },
    {
      key: 'news',
      href: `https://news.google.com/search?q=${t}+stock&hl=en-US&gl=US&ceid=US:en`,
      label: 'News',
      icon: '📰',
      title: `Google News for ${ticker}`,
    },
  ];

  if (compact) {
    return (
      <span className={`cdl cdl--compact${className ? ' ' + className : ''}`} style={style}>
        {links.map((l) => (
          <a
            key={l.key}
            href={l.href}
            target="_blank"
            rel="noreferrer"
            className="cdl__icon"
            title={l.title}
            // Don't bubble — these chips often sit inside a clickable card
            onClick={(e) => e.stopPropagation()}
          >
            {l.icon}
          </a>
        ))}
      </span>
    );
  }

  return (
    <div className={`cat-chatter-links${className ? ' ' + className : ''}`} style={style}>
      <span className="cat-chatter-links__label">Open in:</span>
      {links.map((l) => (
        <a
          key={l.key}
          href={l.href}
          target="_blank"
          rel="noreferrer"
          className={`cat-chatter-link cat-chatter-link--${l.key}`}
          title={l.title}
        >
          {l.icon} {l.label}
        </a>
      ))}
      {subreddits && subreddits.length > 0 && (
        <span className="cat-chatter-links__subs">
          <span className="cat-chatter-links__sub-label">in</span>
          {subreddits.slice(0, 4).map((s) => (
            <a
              key={s}
              href={`https://www.reddit.com/r/${s}/search/?q=${redditQ}&restrict_sr=1&sort=new`}
              target="_blank"
              rel="noreferrer"
              className="cat-chatter-link cat-chatter-link--sub"
              title={`Search r/${s} for ${ticker}`}
            >
              r/{s}
            </a>
          ))}
        </span>
      )}
    </div>
  );
}
