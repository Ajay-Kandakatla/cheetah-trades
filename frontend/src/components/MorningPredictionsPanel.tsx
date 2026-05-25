import { useNavigate } from 'react-router-dom';
import { usePredictions } from '../hooks/useCatalysts';
import type { Prediction } from '../hooks/useCatalysts';

/**
 * MorningPredictionsPanel — compact strip on the Morning Brief showing the
 * top-N HIGH/MEDIUM conviction tiny-stock predictions synthesized by the
 * catalysts predictions engine.
 *
 * Pulls from /catalysts/predictions and shows only `top_relevant` (HIGH +
 * MEDIUM tiers, capped at 8). One-line per prediction with score + bull
 * thesis + click-through to deep-dive on the Catalysts page.
 */
export function MorningPredictionsPanel() {
  const nav = useNavigate();
  const { data, loading } = usePredictions(0); // no auto-poll; fetched once

  if (loading) {
    return (
      <div className="mb-predictions">
        <div className="mb-predictions__head">
          <h2 className="mb-predictions__h">🎯 Tiny-stock predictions</h2>
        </div>
        <div className="day-empty">Synthesizing signals…</div>
      </div>
    );
  }

  if (!data || !data.top_relevant || data.top_relevant.length === 0) {
    return (
      <div className="mb-predictions">
        <div className="mb-predictions__head">
          <h2 className="mb-predictions__h">🎯 Tiny-stock predictions</h2>
          <span className="mb-predictions__sub">no high-conviction setups right now</span>
        </div>
        <div className="day-empty">
          {data ? 'No HIGH/MEDIUM tier predictions yet.' : 'Predictions unavailable.'}
        </div>
      </div>
    );
  }

  const handleClick = (ticker: string, e: React.MouseEvent) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) {
      window.open(`/sepa/${encodeURIComponent(ticker)}`, '_blank', 'noopener,noreferrer');
      return;
    }
    nav(`/sepa/${ticker}`, { state: { from: '/morning', label: 'Morning' } });
  };

  return (
    <div className="mb-predictions">
      <div className="mb-predictions__head">
        <h2 className="mb-predictions__h">🎯 Tiny-stock predictions</h2>
        <span className="mb-predictions__sub">
          {data.by_tier.HIGH} HIGH · {data.by_tier.MEDIUM} MEDIUM · synthesized from catalyst + accumulation + insider + calendar
          <button
            type="button"
            onClick={() => nav('/catalysts')}
            style={{
              background: 'transparent', border: 'none', color: 'var(--gold)',
              fontSize: 11, cursor: 'pointer', marginLeft: 8, padding: 0,
            }}
          >
            full screen →
          </button>
        </span>
      </div>

      <ul className="mb-predictions__list">
        {data.top_relevant.map((p) => (
          <PredictionRow key={p.ticker} p={p} onClick={(e) => handleClick(p.ticker, e)} />
        ))}
      </ul>
    </div>
  );
}


function PredictionRow({ p, onClick }: { p: Prediction; onClick: (e: React.MouseEvent) => void }) {
  const tierClass = p.conviction_tier.toLowerCase();
  const isUp = (p.change_pct ?? 0) > 0;
  const cap = p.market_cap;
  const capStr = cap ? (cap >= 1e9 ? `$${(cap / 1e9).toFixed(1)}B` : `$${(cap / 1e6).toFixed(0)}M`) : '—';
  const tierColor =
    p.conviction_tier === 'HIGH' ? 'var(--positive)' :
    p.conviction_tier === 'MEDIUM' ? 'var(--gold)' :
    'var(--ink-muted)';
  // Strip "Bull: " prefix for display
  const bullShort = (p.bull_thesis || '').replace(/^Bull:\s*/i, '');

  return (
    <li className={`mb-predictions__row mb-predictions__row--${tierClass}`}>
      <button
        className="mb-predictions__ticker"
        onClick={onClick}
        title="Click to open · Cmd/Ctrl-click for new tab"
      >
        {p.ticker}
      </button>
      <span className="mb-predictions__score mono" style={{ color: tierColor }}>
        +{p.conviction_score.toFixed(0)}
      </span>
      <span className="mb-predictions__tier" style={{ color: tierColor }}>
        {p.conviction_tier}
      </span>
      <span className={`mono ${isUp ? 'pos' : 'neg'}`} style={{ color: isUp ? 'var(--positive)' : 'var(--negative)' }}>
        {isUp ? '+' : ''}{(p.change_pct ?? 0).toFixed(1)}%
      </span>
      <span className="mb-predictions__bull">{bullShort || `${p.n_signals} signals`}</span>
      <span className="mb-predictions__cap mono">{capStr}</span>
    </li>
  );
}
