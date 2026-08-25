import { useLocation, useNavigate } from 'react-router-dom';
import type { FlowSnapshot } from '../hooks/useSupplyDemand';
import type { MouseEvent } from 'react';
import { sourceKeyFor, withSource } from '../lib/navSource';
import { useLivePrices } from '../hooks/useLivePrices';
import { getMarketSession, pickDisplayPrice } from '../lib/marketSession';
import { SessionBadge } from './SessionBadge';

type Props = {
  flow: FlowSnapshot;
  onTickerClick?: (ticker: string) => void;
};

/**
 * MoneyFlowLeaderboard — three-column strip showing today's biggest
 * inflow and outflow names from the dependency graph universe.
 * Updates as the parent's `useMarketFlow` polls.
 */
export function MoneyFlowLeaderboard({ flow, onTickerClick }: Props) {
  const nav = useNavigate();
  const location = useLocation();
  // Session-aware extended-hours overlay. Cheap: useLivePrices is a
  // single hook that the SEPA + Kell pages already mount, so adding it
  // here is a no-op when the same component is also displayed on those
  // pages, and a single fetch otherwise.
  const livePrices = useLivePrices();
  const session = getMarketSession();
  const fromLabel = location.pathname.startsWith('/supply-demand') ? 'Supply / Demand'
    : location.pathname.startsWith('/morning') ? 'Morning'
    : location.pathname.startsWith('/overnight') ? 'Overnight'
    : 'previous';

  const handleClick = (t: string, e?: MouseEvent) => {
    // ?from= on BOTH branches. The new-tab branch has no router state and no
    // history, so without it the destination's back button hard-falls to
    // /sepa — the exact "goes to sepa always" Ajay reported from this page.
    const url = withSource(`/sepa/${encodeURIComponent(t)}`,
                           sourceKeyFor(location.pathname) || '');
    // Cmd / Ctrl / Shift / middle-click → always open in a new tab,
    // regardless of whether onTickerClick is set
    if (e && (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1)) {
      window.open(url, '_blank', 'noopener,noreferrer');
      return;
    }
    if (onTickerClick) onTickerClick(t);
    else nav(url, {
      state: { from: location.pathname + location.search, label: fromLabel },
    });
  };

  const fmtDV = (n: number) => {
    if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
    return `$${n.toFixed(0)}`;
  };

  const totals = flow.totals;
  const breadthPct = totals.n_total ? Math.round((totals.n_up / totals.n_total) * 100) : 0;

  return (
    <div className="mfl">
      <header className="mfl__head">
        <div className="mfl__title">
          <span className={`mfl__pulse mfl__pulse--${flow.market.state}`} />
          <strong>Money flow · {flow.market.label}</strong>
          <SessionBadge session={session} />
          <span className="mfl__sub">
            {totals.n_up} up · {totals.n_down} down · {totals.n_flat} flat ·
            {' '}breadth {breadthPct}% · ${(totals.total_dollar_volume / 1e9).toFixed(1)}B traded
          </span>
        </div>
        <div className="mfl__refreshed">
          {flow.cached
            ? `cached ${flow.cache_age_sec}s ago`
            : `refreshed ${new Date(flow.as_of).toLocaleTimeString()}`}
        </div>
      </header>

      <div className="mfl__cols">
        <section className="mfl__col mfl__col--in">
          <div className="mfl__col-h">📈 BIGGEST INFLOWS</div>
          <ul>
            {flow.leaders.top_inflow.map((t) => {
              // Session-aware override — when extended-hours data is
              // available for this ticker we show the live pre/after-hours
              // price + % change vs prev close, otherwise fall back to
              // the FlowSnapshot value (which is the regular-session change).
              const live = pickDisplayPrice(livePrices[t.ticker.toUpperCase()], session);
              const pctText = live?.change_pct != null
                ? `${live.change_pct >= 0 ? '+' : ''}${live.change_pct.toFixed(2)}%`
                : `+${t.change_pct.toFixed(2)}%`;
              return (
                <li key={t.ticker} onClick={(e) => handleClick(t.ticker, e)}>
                  <strong className="mfl__ticker">{t.ticker}</strong>
                  <span className="mfl__pct mono">{pctText}</span>
                  <span className="mfl__dv mono">{fmtDV(t.dollar_volume)}</span>
                </li>
              );
            })}
          </ul>
        </section>

        <section className="mfl__col mfl__col--out">
          <div className="mfl__col-h">📉 BIGGEST OUTFLOWS</div>
          <ul>
            {flow.leaders.top_outflow.map((t) => {
              const live = pickDisplayPrice(livePrices[t.ticker.toUpperCase()], session);
              const pctText = live?.change_pct != null
                ? `${live.change_pct >= 0 ? '+' : ''}${live.change_pct.toFixed(2)}%`
                : `${t.change_pct.toFixed(2)}%`;
              return (
                <li key={t.ticker} onClick={(e) => handleClick(t.ticker, e)}>
                  <strong className="mfl__ticker">{t.ticker}</strong>
                  <span className="mfl__pct mono">{pctText}</span>
                  <span className="mfl__dv mono">{fmtDV(t.dollar_volume)}</span>
                </li>
              );
            })}
          </ul>
        </section>
      </div>
    </div>
  );
}
