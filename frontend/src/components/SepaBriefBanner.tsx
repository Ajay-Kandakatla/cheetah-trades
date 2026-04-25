import { useSepaBrief } from '../hooks/useSepa';
import { InfoButton } from './InfoButton';

const BriefInfo = (
  <>
    <p>
      The <strong>Morning Brief</strong> is a daily summary generated before market open
      (8:30 AM Eastern). It captures three things you need at a glance.
    </p>
    <ul>
      <li>
        <strong>Market regime</strong> — whether the broad market is in a Confirmed Uptrend,
        Mixed, or Caution state, based on the S&amp;P 500 ETF (SPY) and Nasdaq-100 ETF (QQQ).
      </li>
      <li>
        <strong>Top candidates</strong> — the three highest-scoring stocks from the latest
        Specific Entry Point Analysis (SEPA) scan.
      </li>
      <li>
        <strong>Watchlist alerts</strong> — positions that crossed a stop loss, hit a profit
        target, or showed weakness overnight.
      </li>
    </ul>
    <p>Click <strong>Refresh</strong> to regenerate using the latest scan data.</p>
  </>
);

/* ==========================================================================
   SepaBriefBanner — morning brief summary at the top of the dashboard.
   Renders: market state, top 3 SEPA picks, and any watchlist alerts.
   ========================================================================== */
export function SepaBriefBanner() {
  const { data, loading, regenerating, regenerate } = useSepaBrief();

  if (loading && !data) return null;

  if (!data) {
    return (
      <section className="sepa-brief sepa-brief--empty">
        <InfoButton title="Morning Brief">{BriefInfo}</InfoButton>
        <div className="sepa-brief__head">
          <span className="eyebrow">Morning Brief</span>
          <span className="sepa-brief__hint">
            No brief yet — run scan first, then click below.
          </span>
        </div>
        <button className="sepa-btn" onClick={regenerate} disabled={regenerating}>
          {regenerating ? 'Generating…' : 'Generate brief'}
        </button>
      </section>
    );
  }

  const mkt = data.market_context;
  const top = data.top_candidates?.slice(0, 3) ?? [];
  const alerts = data.watchlist_alerts ?? [];
  const when = new Date(data.generated_at * 1000).toLocaleString();

  return (
    <section className="sepa-brief">
      <InfoButton title="Morning Brief">{BriefInfo}</InfoButton>
      <header className="sepa-brief__head">
        <div>
          <div className="eyebrow">Morning Brief</div>
          <div className="sepa-brief__meta mono">{when}</div>
        </div>
        {mkt?.label && (
          <div className={`sepa-brief__market sepa-brief__market--${mkt.label}`}>
            <span className="mono">MARKET</span>{' '}
            <strong>{mkt.label.replace('_', ' ')}</strong>
            {mkt.safe_to_long ? ' · safe to long' : ' · caution'}
          </div>
        )}
        <button className="sepa-btn" onClick={regenerate} disabled={regenerating}>
          {regenerating ? 'Refreshing…' : 'Refresh'}
        </button>
      </header>

      {alerts.length > 0 && (
        <div className="sepa-brief__alerts">
          <span className="eyebrow">Watchlist alerts</span>
          {alerts.map((a) => (
            <span key={a.symbol} className={`sepa-pill sepa-pill--${a.action}`}>
              {a.symbol}: {a.action.replace('_', ' ')} · {a.pnl_pct?.toFixed(1)}%
            </span>
          ))}
        </div>
      )}

      <div className="sepa-brief__top">
        {top.map((c) => (
          <article key={c.symbol} className="sepa-pick">
            <div className="sepa-pick__sym">{c.symbol}</div>
            <div className="sepa-pick__score mono">
              score {c.score?.toFixed(0)} · RS {c.rs_rank ?? '—'}
            </div>
            {c.entry_setup && (
              <div className="sepa-pick__setup mono">
                {c.entry_setup.type} pivot ${c.entry_setup.pivot} · stop ${c.entry_setup.stop}
              </div>
            )}
          </article>
        ))}
        {top.length === 0 && (
          <div className="sepa-brief__empty">No SEPA candidates today.</div>
        )}
      </div>
    </section>
  );
}
