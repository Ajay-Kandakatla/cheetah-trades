import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { OvernightMover } from '../hooks/useOvernight';
import { useOvernightMovers } from '../hooks/useOvernight';
import { useLivePrices } from '../hooks/useLivePrices';
import { getMarketSession, pickDisplayPrice, type LivePrice } from '../lib/marketSession';
import { SessionBadge } from './SessionBadge';

const CATEGORY_COLORS: Record<string, string> = {
  Earnings:       '#10b981',
  Analyst:        '#3b82f6',
  'M&A':          '#a855f7',
  ma:             '#a855f7',
  FDA:            '#06b6d4',
  Filing:         '#64748b',
  Litigation:     '#ef4444',
  Insider:        '#f59e0b',
  Macro:          '#ec4899',
  Sector:         '#84cc16',
  Geopolitical:   '#dc2626',
  Crypto:         '#f97316',
  Product:        '#8b5cf6',
  Partnership:    '#14b8a6',
  'Stock action': '#a3a3a3',
  Other:          '#94a3b8',
};

type Props = { compact?: boolean; minGapPct?: number };

export function OvernightPanel({ compact = false, minGapPct = 0.5 }: Props) {
  const nav = useNavigate();
  const location = useLocation();
  const navLabel = location.pathname.startsWith('/morning') ? 'Morning' : 'Overnight';
  const navState = { from: location.pathname + location.search, label: navLabel };
  const { data, loading, refreshing, forceRefresh } = useOvernightMovers({ minGapPct, includeSepa: true });
  // Pre-market is THIS page's primary use case — extended-hours data
  // is the feature. The session-aware poll cadence in useLivePrices
  // handles the 4am-9:30am pre-market window automatically.
  const livePrices = useLivePrices();

  if (loading) {
    return <div className="overnight-panel overnight-panel--loading">Scanning overnight tape…</div>;
  }
  if (!data || data.n_moved === 0) {
    return (
      <div className="overnight-panel">
        <header className="overnight-panel__head">
          <h2 className="overnight-panel__h">Overnight movers</h2>
          <span className="overnight-panel__meta">{data?.n_scanned ?? 0} scanned · 0 moved ≥{minGapPct}%</span>
          <button type="button" className="overnight-refresh" onClick={forceRefresh} disabled={refreshing} aria-busy={refreshing}>
            {refreshing ? 'Refreshing…' : '↻ Force refresh'}
          </button>
        </header>
        <div className="day-empty">
          Quiet overnight — no symbols crossed the {minGapPct}% threshold.
        </div>
      </div>
    );
  }

  const visible = compact ? data.movers.slice(0, 5) : data.movers;

  return (
    <div className="overnight-panel">
      <header className="overnight-panel__head">
        <h2 className="overnight-panel__h">Overnight movers</h2>
        <span className="overnight-panel__meta mono">
          {data.n_moved} of {data.n_scanned} symbols moved ≥{data.min_gap_pct}%
          {data.n_cached != null && data.n_cached > 0 && (
            <> · <span className="overnight-cache-tag" title={`${data.n_cached} of ${data.n_moved} from ${data.cache_ttl_min ?? 30}min cache`}>
              {data.n_cached === data.n_moved ? 'cached' : `${data.n_cached} cached`}
            </span></>
          )}
          {data.as_of && <> · {new Date(data.as_of).toLocaleTimeString()}</>}
        </span>
        <button type="button" className="overnight-refresh" onClick={forceRefresh} disabled={refreshing} aria-busy={refreshing}
                title="Bypass 30min cache and re-scrape every symbol">
          {refreshing ? 'Refreshing…' : '↻ Force refresh'}
        </button>
      </header>

      <div className="overnight-grid">
        {visible.map((m) => (
          <OvernightCard
            key={m.symbol}
            m={m}
            livePrice={livePrices[m.symbol.toUpperCase()]}
            onClick={(e?: React.MouseEvent) => {
              if (e && (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1)) {
                window.open(`/sepa/${encodeURIComponent(m.symbol)}`, '_blank', 'noopener,noreferrer');
                return;
              }
              nav(`/sepa/${m.symbol}`, { state: navState });
            }}
          />
        ))}
      </div>

      {compact && data.n_moved > visible.length && (
        <button type="button" className="overnight-more" onClick={() => nav('/overnight')}>
          See all {data.n_moved} movers →
        </button>
      )}
    </div>
  );
}

function OvernightCard({
  m,
  livePrice,
  onClick,
}: {
  m: OvernightMover;
  livePrice?: LivePrice;
  onClick: (e?: React.MouseEvent) => void;
}) {
  const gap = m.gap_pct ?? 0;
  const dir = gap > 0 ? 'up' : gap < 0 ? 'down' : 'flat';
  const cat = m.catalyst?.category ?? null;
  const catColor = cat ? CATEGORY_COLORS[cat] ?? '#94a3b8' : 'var(--ink-subtle)';
  const [newsOpen, setNewsOpen] = useState(false);

  // Session-aware live price overlay. Pre-market is the primary use
  // case here, but the same component handles after-hours + closed.
  const session = getMarketSession();
  const liveDisplay = pickDisplayPrice(livePrice, session);
  const liveDir = liveDisplay
    ? (liveDisplay.change_pct ?? 0) > 0
      ? 'up'
      : (liveDisplay.change_pct ?? 0) < 0
        ? 'down'
        : 'flat'
    : 'flat';

  const newsLinks = m.news_links ?? [];
  // Avoid duplicating the catalyst headline inside the news list
  const additionalNews = m.catalyst?.url
    ? newsLinks.filter((n) => n.url && n.url !== m.catalyst!.url)
    : newsLinks;

  return (
    <article className={`overnight-card overnight-card--${dir}`} role="group">
      <header className="overnight-card__head" onClick={(e) => onClick(e)}
              role="button" tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClick(); }}
              style={{ cursor: 'pointer' }}
              title="Cmd/Ctrl-click to open in new tab">
        <strong className="overnight-card__sym">{m.symbol}</strong>
        <span className={`overnight-card__gap overnight-card__gap--${dir} mono`}>
          {gap > 0 ? '+' : ''}{gap.toFixed(2)}%
        </span>
        <SessionBadge session={session} />
      </header>

      {/* Live extended-hours quote — pre-market is THE primary use case
          of this page, so the live print + session badge get prominent
          placement. Falls through to the regular close-vs-y_close strip
          below when no live data is available. */}
      {liveDisplay && (
        <div className="overnight-card__prices mono"
             title={
               session === 'pre'
                 ? 'Live pre-market trade. Change is vs the previous regular close.'
                 : session === 'after'
                   ? 'Live after-hours trade. Change is vs the previous regular close.'
                   : session === 'live'
                     ? 'Live regular-session price.'
                     : 'Market closed — last regular-session close.'
             }>
          <span className={`overnight-card__pre ${liveDir === 'up' ? 'pos' : liveDir === 'down' ? 'neg' : ''}`}
                style={{ fontSize: '0.95rem', fontWeight: 600 }}>
            ${liveDisplay.price.toFixed(2)}
          </span>
          {liveDisplay.change_pct != null && (
            <span className={`overnight-card__gap overnight-card__gap--${liveDir} mono`}
                  style={{ marginLeft: '0.4rem' }}>
              {liveDisplay.change_pct >= 0 ? '+' : ''}{liveDisplay.change_pct.toFixed(2)}%
            </span>
          )}
        </div>
      )}

      <div className="overnight-card__prices mono">
        <span className="overnight-card__y-close">y close ${m.yesterday_close.toFixed(2)}</span>
        <span className="overnight-card__arrow">→</span>
        <span className={`overnight-card__pre ${dir === 'up' ? 'pos' : dir === 'down' ? 'neg' : ''}`}>
          pre ${m.premarket_last?.toFixed(2) ?? '—'}
        </span>
      </div>

      {/* Sparkline */}
      <div className="overnight-card__spark">
        <Sparkline points={m.premarket_sparkline} dir={dir} />
      </div>

      {/* SOIR / Schaeffer signal badge — only when the cached options scan
          has a record for this ticker. Tells you if the options crowd is
          contrarianly positioned vs the gap direction. */}
      {m.soir_pulse?.signal && m.soir_pulse.signal !== 'NEUTRAL' && (
        <div className={`overnight-card__soir overnight-card__soir--${m.soir_pulse.signal.toLowerCase()}`}>
          <span className="overnight-card__soir-tag mono">SOIR</span>
          <span className="overnight-card__soir-signal mono">
            {m.soir_pulse.signal}
          </span>
          <span className="overnight-card__soir-meta mono">
            {m.soir_pulse.soir != null && `ratio ${m.soir_pulse.soir.toFixed(2)}`}
            {m.soir_pulse.soir_percentile != null && ` · ${m.soir_pulse.soir_percentile.toFixed(0)}th pct`}
            {m.soir_pulse.expected_move_pct != null && ` · ±${m.soir_pulse.expected_move_pct.toFixed(1)}% expected`}
          </span>
        </div>
      )}

      {/* Catalyst — headline is now clickable + opens source in new tab */}
      {m.catalyst && m.catalyst.headline ? (
        <div className="overnight-card__catalyst">
          <span className="overnight-card__cat-pill" style={{ background: catColor }}>{cat}</span>
          {m.catalyst.url ? (
            <a className="overnight-card__hdl overnight-card__hdl--link"
               href={m.catalyst.url} target="_blank" rel="noreferrer"
               title={`Open: ${m.catalyst.headline}`}
               onClick={(e) => e.stopPropagation()}>
              {m.catalyst.headline}
              <span className="overnight-card__hdl-icon" aria-hidden> ↗</span>
            </a>
          ) : (
            <span className="overnight-card__hdl" title={m.catalyst.headline}>
              {m.catalyst.headline}
            </span>
          )}
          {m.catalyst.publisher && <span className="overnight-card__pub">— {m.catalyst.publisher}</span>}
        </div>
      ) : (
        <div className="overnight-card__catalyst overnight-card__catalyst--none">
          No clear catalyst — could be sector flow, macro futures, or thin overnight tape.
        </div>
      )}

      {/* More-news drawer — shows the rest of the headlines we fetched */}
      {additionalNews.length > 0 && (
        <div className="overnight-card__news">
          <button type="button" className="overnight-card__news-toggle"
                  onClick={(e) => { e.stopPropagation(); setNewsOpen(!newsOpen); }}>
            {newsOpen ? '− Hide' : '+ Show'} {additionalNews.length} more headline{additionalNews.length !== 1 ? 's' : ''}
          </button>
          {newsOpen && (
            <ul className="overnight-card__news-list">
              {additionalNews.map((n, i) => (
                <li key={i}>
                  {n.url ? (
                    <a href={n.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                      {n.title}
                      <span className="overnight-card__hdl-icon" aria-hidden> ↗</span>
                    </a>
                  ) : (
                    <span>{n.title}</span>
                  )}
                  {n.publisher && <span className="overnight-card__news-pub"> — {n.publisher}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {m.earnings_flag?.flagged && m.earnings_flag.url ? (
        <a href={m.earnings_flag.url} target="_blank" rel="noreferrer"
           className="overnight-card__earnings overnight-card__earnings--link"
           onClick={(e) => e.stopPropagation()}>
          ⚠ Earnings flagged in last 24h
        </a>
      ) : m.earnings_flag?.flagged ? (
        <div className="overnight-card__earnings">⚠ Earnings flagged in last 24h</div>
      ) : null}

      {m.premarket_high != null && m.premarket_low != null && (
        <div className="overnight-card__levels mono">
          Pre H/L: {m.premarket_low.toFixed(2)} – {m.premarket_high.toFixed(2)}
          {m._cached && m._cache_age_sec != null && (
            <span className="overnight-card__cache-age"
                  title={`Cached ${Math.floor(m._cache_age_sec / 60)}min ago — click 'Force refresh' above for fresh data`}>
              · cached {Math.floor(m._cache_age_sec / 60)}m
            </span>
          )}
        </div>
      )}
    </article>
  );
}

function Sparkline({ points, dir }: { points: { ts: string; px: number }[]; dir: 'up'|'down'|'flat' }) {
  if (!points || points.length < 2) {
    return <div className="overnight-card__spark-empty">no premarket data</div>;
  }
  const W = 220, H = 36;
  const xs = points.map((p) => p.px);
  let lo = Math.min(...xs), hi = Math.max(...xs);
  if (lo === hi) { lo -= 0.5; hi += 0.5; }
  const range = hi - lo || 1;
  const pad = 2;
  const xOf = (i: number) => pad + (points.length === 1 ? W / 2 : (i / (points.length - 1)) * (W - pad * 2));
  const yOf = (p: number) => pad + (1 - (p - lo) / range) * (H - pad * 2);

  let path = '';
  points.forEach((p, i) => {
    path += (i === 0 ? 'M' : 'L') + xOf(i).toFixed(1) + ',' + yOf(p.px).toFixed(1);
  });
  const fill = path + ` L${xOf(points.length - 1).toFixed(1)},${(H - pad).toFixed(1)} L${xOf(0).toFixed(1)},${(H - pad).toFixed(1)} Z`;
  const color = dir === 'up' ? 'var(--positive)' : dir === 'down' ? 'var(--negative)' : 'var(--ink-muted)';

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="overnight-spark">
      <path d={fill} fill={color} opacity={0.18} />
      <path d={path} fill="none" stroke={color} strokeWidth={1.4} strokeLinejoin="round" />
    </svg>
  );
}
