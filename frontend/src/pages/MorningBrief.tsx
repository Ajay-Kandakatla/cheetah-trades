import { Suspense, useEffect, useState } from 'react';
import { TickerCell } from '../components/TickerCell';
import { useNavigate } from 'react-router-dom';
import { useCurrentUser } from '../hooks/useUser';
import { MarketGaugeBanner } from '../components/MarketGaugeBanner';
import { MorningTodosCard } from '../components/MorningTodosCard';
import { HoldingsCard } from '../components/HoldingsCard';
import { useMorningBrief } from '../hooks/useMorningBrief';
import type { Verdict, OverallAction } from '../hooks/useMorningBrief';
import { useLiveSignals, useWatchlist, usePaperTrading } from '../hooks/useDayTrading';
import { lazyWithReload } from '../lib/lazyWithReload';

// Below-fold panels — defer-loaded so the trading verdict (above-fold)
// renders FIRST, then these mount once the user has the stock data they
// came for. Each is its own chunk via React.lazy.
const OvernightPanel       = lazyWithReload(() => import('../components/OvernightPanel').then(m => ({ default: m.OvernightPanel })));
const SupplyDemandSummary  = lazyWithReload(() => import('../components/SupplyDemandSummary').then(m => ({ default: m.SupplyDemandSummary })));

const VERDICT_COPY: Record<Verdict, { label: string; mood: 'good'|'warn'|'bad' }> = {
  favorable:  { label: 'GO',      mood: 'good' },
  selective:  { label: 'SELECTIVE', mood: 'warn' },
  neutral:    { label: 'NEUTRAL', mood: 'warn' },
  caution:    { label: 'CAUTION', mood: 'bad'  },
};

const ACTION_DISPLAY: Record<OverallAction, { emoji: string; phrase: string; mood: 'good'|'warn'|'bad' }> = {
  go_long:        { emoji: '🟢', phrase: 'GO LONG TODAY',          mood: 'good' },
  day_trade_only: { emoji: '🟡', phrase: 'DAY-TRADE ONLY',          mood: 'warn' },
  swing_only:     { emoji: '🟡', phrase: 'SWING SETUPS ONLY',       mood: 'warn' },
  tighten_stops:  { emoji: '🟡', phrase: 'TIGHTEN STOPS · NO NEW',  mood: 'warn' },
  sit_out:        { emoji: '🔴', phrase: 'SIT OUT TODAY',           mood: 'bad'  },
};

export function MorningBrief() {
  const nav = useNavigate();
  const { user } = useCurrentUser();
  const { data, error } = useMorningBrief();
  const watchlist = useWatchlist();
  const { signals: dayTradeSignals } = useLiveSignals(watchlist);
  const { data: paper } = usePaperTrading(watchlist);

  // Defer-mount below-fold panels so the stocks (above-fold) render FIRST.
  // Flips true after the next animation frame — well after first paint.
  // User asked: "stocks first then cooking details" — this delivers that.
  const [showBelowFold, setShowBelowFold] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setShowBelowFold(true), 100);
    return () => clearTimeout(t);
  }, []);

  if (error && !data) {
    return <div className="cm-page morning-page"><div className="day-empty">Couldn't load brief: {error}</div></div>;
  }

  // Render the SHELL even before brief data arrives — regime banner +
  // todos load on their own, day/swing cards show skeletons until data.
  const action = data ? ACTION_DISPLAY[data.overall.action] : null;
  const today = data ? new Date(data.as_of) : new Date();
  const dayLabel = today.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });

  return (
    <div className="cm-page morning-page">
      <MarketGaugeBanner />

      <header className="cm-pagehead">
        <div className="cm-pagehead__col">
          <div className="eyebrow">Today's brief · {dayLabel}</div>
          <h1 className="display cm-pagehead__title">
            Good morning{user?.given_name ? `, ${user.given_name}` : ''}
          </h1>
          <p className="lede">
            Synthesis of market regime, day-trading conditions, and swing-trade
            setups. Updates every 5 minutes.
          </p>
        </div>
      </header>

      {/* PERSONAL TODOS — promoted to the TOP (Ajay 2026-06-07: "todo list
          first, then portfolio"). Independent fetch, renders ASAP. */}
      <section className="morning-overnight-section">
        <MorningTodosCard />
      </section>

      {/* PORTFOLIO — actual holdings + live P/L, second per Ajay's order.
          Inline in the brief payload (no extra round trip). */}
      {data?.holdings && (
        <section className="morning-overnight-section">
          <HoldingsCard holdings={data.holdings} />
        </section>
      )}

      {/* HERO VERDICT — shows skeleton until brief data arrives. */}
      {data && action ? (
        <section className={`morning-hero morning-hero--${action.mood}`}>
          <div className="morning-hero__main">
            <div className="morning-hero__emoji" aria-hidden>{action.emoji}</div>
            <div>
              <div className="morning-hero__eyebrow">Today's call</div>
              <h2 className="morning-hero__phrase">{action.phrase}</h2>
              <p className="morning-hero__message">{data.overall.message}</p>
            </div>
          </div>
          <div className="morning-hero__meta mono">
            {data.scan_age_minutes != null && <span>Last scan {data.scan_age_minutes}min ago</span>}
          </div>
        </section>
      ) : (
        <section className="morning-hero morning-hero--warn">
          <div className="morning-hero__main">
            <div className="morning-hero__emoji" aria-hidden>⏳</div>
            <div>
              <div className="morning-hero__eyebrow">Today's call</div>
              <h2 className="morning-hero__phrase">Loading verdict…</h2>
              <p className="morning-hero__message">Pulling regime + day-trade conditions + SEPA setups.</p>
            </div>
          </div>
        </section>
      )}

      {/* Below-fold sections — defer-mount so the stocks (above) render
          first on phone. User asked for stocks-first, then cooking. */}
      {showBelowFold && (
        <>
          <section className="morning-overnight-section">
            <Suspense fallback={null}>
              <OvernightPanel compact={true} minGapPct={0.5} />
            </Suspense>
          </section>
          <section className="morning-overnight-section">
            <Suspense fallback={null}>
              <SupplyDemandSummary compact={true} />
            </Suspense>
          </section>
          {/* MacStudio deals panel removed 2026-05-15 — user bought their
              target Mac; deal-watching no longer relevant. The entire
              backend/lifeboard module + frontend Mac panels were
              deleted in the same change. */}
        </>
      )}

      {/* TWO-COL: DAY vs SWING — gated on data; shows skeleton until ready */}
      {!data && (
        <section className="morning-cols">
          <div className="morning-card morning-card--warn" style={{ opacity: 0.6 }}>
            <header className="morning-card__head">
              <h3 className="morning-card__title">Day Trading</h3>
              <span className="mono" style={{ fontSize: '0.7rem' }}>loading…</span>
            </header>
          </div>
          <div className="morning-card morning-card--warn" style={{ opacity: 0.6 }}>
            <header className="morning-card__head">
              <h3 className="morning-card__title">Swing Trading · SEPA</h3>
              <span className="mono" style={{ fontSize: '0.7rem' }}>loading…</span>
            </header>
          </div>
        </section>
      )}
      {data && (
      <section className="morning-cols">
        {/* Day trading */}
        <div className={`morning-card morning-card--${VERDICT_COPY[data.day_trading.verdict].mood}`}>
          <header className="morning-card__head">
            <h3 className="morning-card__title">Day Trading</h3>
            <span className={`morning-card__verdict morning-card__verdict--${VERDICT_COPY[data.day_trading.verdict].mood}`}>
              {VERDICT_COPY[data.day_trading.verdict].label}
            </span>
            <span className="morning-card__conf mono">{data.day_trading.confidence}/100</span>
          </header>
          <p className="morning-card__head-line">{data.day_trading.headline}</p>

          {data.day_trading.reasons_pro.length > 0 && (
            <ul className="morning-card__list morning-card__list--good">
              {data.day_trading.reasons_pro.map((r, i) => <li key={`d-pro-${i}`}>{r}</li>)}
            </ul>
          )}
          {data.day_trading.reasons_con.length > 0 && (
            <ul className="morning-card__list morning-card__list--bad">
              {data.day_trading.reasons_con.map((r, i) => <li key={`d-con-${i}`}>{r}</li>)}
            </ul>
          )}

          <div className="morning-card__inner">
            <div className="morning-card__inner-head">
              <span className="morning-card__inner-label">Setups firing now</span>
              <strong className="morning-card__inner-num">{dayTradeSignals.length}</strong>
            </div>
            {dayTradeSignals.slice(0, 3).map((s, i) => (
              <div key={i} className="morning-mini-row">
                <TickerCell symbol={s.symbol || ''} size="0.92rem" nameWidth={16} />
                <span className={`morning-mini-side morning-mini-side--${s.side}`}>{s.side === 'long' ? '↑' : '↓'} {s.strategy}</span>
                <span className="mono">${s.entry_price.toFixed(2)} · {s.r_multiple_potential}R</span>
              </div>
            ))}
            {dayTradeSignals.length === 0 && (
              <div className="morning-mini-empty">No setups firing yet — open at 9:30 ET, ORB completes 9:45 ET.</div>
            )}
          </div>

          {paper && (paper.open_count + paper.closed_count) > 0 && (
            <div className="morning-card__inner">
              <div className="morning-card__inner-head">
                <span className="morning-card__inner-label">Today's paper P&L</span>
                <strong className={`morning-card__inner-num ${paper.stats.total_pnl_pct != null && paper.stats.total_pnl_pct > 0 ? 'pos' : 'neg'}`}>
                  {paper.stats.total_pnl_pct != null ? (paper.stats.total_pnl_pct > 0 ? '+' : '') + paper.stats.total_pnl_pct.toFixed(2) + '%' : '—'}
                </strong>
              </div>
              <div className="morning-mini-row mono">
                <span>{paper.open_count} open · {paper.closed_count} closed</span>
                {paper.stats.win_rate_pct != null && <span>{paper.stats.win_rate_pct}% win</span>}
              </div>
            </div>
          )}

          <button type="button" className="morning-card__cta" onClick={() => nav('/day-trading')}>
            Open Day Trading →
          </button>
        </div>

        {/* Swing trading */}
        <div className={`morning-card morning-card--${VERDICT_COPY[data.swing_trading.verdict].mood}`}>
          <header className="morning-card__head">
            <h3 className="morning-card__title">Swing Trading · SEPA</h3>
            <span className={`morning-card__verdict morning-card__verdict--${VERDICT_COPY[data.swing_trading.verdict].mood}`}>
              {VERDICT_COPY[data.swing_trading.verdict].label}
            </span>
            <span className="morning-card__conf mono">{data.swing_trading.confidence}/100</span>
          </header>
          <p className="morning-card__head-line">{data.swing_trading.headline}</p>

          {data.swing_trading.reasons_pro.length > 0 && (
            <ul className="morning-card__list morning-card__list--good">
              {data.swing_trading.reasons_pro.map((r, i) => <li key={`s-pro-${i}`}>{r}</li>)}
            </ul>
          )}
          {data.swing_trading.reasons_con.length > 0 && (
            <ul className="morning-card__list morning-card__list--bad">
              {data.swing_trading.reasons_con.map((r, i) => <li key={`s-con-${i}`}>{r}</li>)}
            </ul>
          )}

          <div className="morning-card__inner">
            <div className="morning-card__inner-head">
              <span className="morning-card__inner-label">Candidates near pivot</span>
              <strong className="morning-card__inner-num">{data.swing_trading.candidates_near_pivot_count}</strong>
            </div>
            {data.swing_trading.candidates_near_pivot.slice(0, 5).map((c, i) => (
              <div
                key={i}
                className="morning-mini-row morning-mini-row--clickable"
                onClick={(e) => {
                  if (e.metaKey || e.ctrlKey || e.shiftKey) {
                    window.open(`/sepa/${encodeURIComponent(c.symbol)}`, '_blank', 'noopener,noreferrer');
                    return;
                  }
                  nav(`/sepa/${c.symbol}`, { state: { from: '/morning', label: 'Morning' } });
                }}
                title="Cmd/Ctrl-click to open in new tab"
              >
                <TickerCell symbol={c.symbol} size="0.92rem" nameWidth={16} />
                <span className={`morning-mini-rating morning-mini-rating--${c.rating?.toLowerCase()}`}>{c.rating}</span>
                <span className="mono">{c.score}/100</span>
                <span className="mono morning-mini-dist">
                  {c.distance_to_pivot_pct >= 0 ? '+' : ''}{c.distance_to_pivot_pct}% to pivot
                </span>
              </div>
            ))}
            {data.swing_trading.candidates_near_pivot_count === 0 && (
              <div className="morning-mini-empty">No SEPA candidates within 3% of pivot today.</div>
            )}
          </div>

          <button type="button" className="morning-card__cta" onClick={() => nav('/sepa')}>
            Open SEPA Screen →
          </button>
        </div>
      </section>
      )}

      {/* Options Pulse — SOIR / Schaeffer's Expectational Analysis.
          Shows top contrarian-bullish + bearish setups derived from the
          nightly SOIR cron. Click a row → SEPA candidate page. */}
      {data?.options_pulse?.available && (
        ((data.options_pulse.bullish?.length ?? 0) > 0 ||
         (data.options_pulse.bearish?.length ?? 0) > 0) && (
          <section className="morning-card morning-card--options">
            <div className="morning-card__head">
              <div>
                <div className="eyebrow">Options Pulse · SOIR</div>
                <h2 className="morning-card__title">Schaeffer signals today</h2>
              </div>
              <span className="morning-card__conf mono">
                {data.options_pulse.n_bullish ?? 0} bullish · {data.options_pulse.n_bearish ?? 0} bearish
              </span>
            </div>
            <p className="morning-card__head-line">
              Tickers where the options crowd is contrarianly positioned vs
              the underlying trend — the kind of setup Schaeffer's
              Expectational Analysis flags as fuel for a move.
            </p>
            <div className="morning-card__inner">
              {(data.options_pulse.bullish?.length ?? 0) > 0 && (
                <>
                  <strong className="morning-card__inner-num">★ Bullish</strong>
                  {data.options_pulse.bullish!.slice(0, 5).map((r) => (
                    <div key={`bull-${r.symbol}`} className="morning-mini" onClick={() => nav(`/sepa/${r.symbol}`)}>
                      <span className="mono morning-mini-sym">{r.symbol}</span>
                      <span className="mono morning-mini-meta">
                        SOIR {r.soir?.toFixed(2) ?? '—'} · {r.soir_percentile != null ? `${r.soir_percentile.toFixed(0)}th pct` : '—'}
                      </span>
                      <span className="mono morning-mini-dist">
                        ±{r.expected_move_pct?.toFixed(1) ?? '—'}% expected
                      </span>
                    </div>
                  ))}
                </>
              )}
              {(data.options_pulse.bearish?.length ?? 0) > 0 && (
                <>
                  <strong className="morning-card__inner-num" style={{ marginTop: '0.6rem' }}>Bearish</strong>
                  {data.options_pulse.bearish!.slice(0, 5).map((r) => (
                    <div key={`bear-${r.symbol}`} className="morning-mini" onClick={() => nav(`/sepa/${r.symbol}`)}>
                      <span className="mono morning-mini-sym">{r.symbol}</span>
                      <span className="mono morning-mini-meta">
                        SOIR {r.soir?.toFixed(2) ?? '—'} · {r.soir_percentile != null ? `${r.soir_percentile.toFixed(0)}th pct` : '—'}
                      </span>
                      <span className="mono morning-mini-dist">
                        ±{r.expected_move_pct?.toFixed(1) ?? '—'}% expected
                      </span>
                    </div>
                  ))}
                </>
              )}
            </div>
            <button type="button" className="morning-card__cta" onClick={() => nav('/options')}>
              Open Options Pulse →
            </button>
          </section>
        )
      )}

      {/* Quick-jump deck */}
      <section className="morning-deck">
        <button type="button" className="morning-deck__btn" onClick={() => nav('/live')}>
          📈 Live Stream
        </button>
        <button type="button" className="morning-deck__btn" onClick={() => nav('/day-trading')}>
          ⚡ Day Trading
        </button>
        <button type="button" className="morning-deck__btn" onClick={() => nav('/sepa')}>
          🎯 SEPA
        </button>
        <button type="button" className="morning-deck__btn" onClick={() => nav('/options')}>
          🎲 Options Pulse
        </button>
        <button type="button" className="morning-deck__btn" onClick={() => nav('/pioneers')}>
          🚀 Pioneers
        </button>
        <button type="button" className="morning-deck__btn" onClick={() => nav('/overnight')}>
          🌙 Overnight Tape
        </button>
        <button type="button" className="morning-deck__btn" onClick={() => nav('/supply-demand')}>
          🔗 Supply / Demand Atlas
        </button>
        <button type="button" className="morning-deck__btn" onClick={() => nav('/dual-momentum')}>
          📊 Dual Momentum
        </button>
      </section>
    </div>
  );
}
