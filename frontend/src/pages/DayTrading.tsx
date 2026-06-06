import { useState, useMemo } from 'react';
import { MarketGaugeBanner } from '../components/MarketGaugeBanner';
import { IntradayChart } from '../components/IntradayChart';
import { DayTradingGuide } from '../components/DayTradingGuide';
import { AiReviewModal } from '../components/AiReviewModal';
import {
  useWatchlist, useDayBars, useLiveSignals,
  useSymbolBacktest,
  useStrategies, usePaperTrading,
} from '../hooks/useDayTrading';

const STRATEGY_COLORS: Record<string, string> = {
  orb:               'var(--gold)',
  gap_and_go:        '#a855f7',
  bull_flag:         'var(--positive)',
  vwap_reversion:    '#06b6d4',
  momentum_failure:  'var(--negative)',
};

export function DayTrading() {
  const watchlist = useWatchlist();
  const strategies = useStrategies();
  const [selected, setSelected] = useState<string>('NVDA');
  const [activeStrategies, setActiveStrategies] = useState<Set<string>>(new Set(['orb', 'bull_flag', 'gap_and_go', 'momentum_failure']));
  const [reviewSymbol, setReviewSymbol] = useState<string | null>(null);

  const stratFilter = useMemo(() => Array.from(activeStrategies), [activeStrategies]);
  const { signals: liveSignals, asOf } = useLiveSignals(watchlist, stratFilter);
  const { data: bars, loading: barsLoading } = useDayBars(selected, 1);
  const { data: bt30 } = useSymbolBacktest(selected, 30);
  const { data: paper, reset: paperReset } = usePaperTrading(watchlist, stratFilter);

  const symbolSignals = liveSignals.filter((s) => s.symbol === selected);

  const toggleStrategy = (key: string) => {
    setActiveStrategies((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  return (
    <div className="cm-page day-page">
      <MarketGaugeBanner />

      <header className="cm-pagehead">
        <div className="cm-pagehead__col">
          <div className="eyebrow">№ 06 — Methodology</div>
          <h1 className="display cm-pagehead__title">Day Trading · 5 Strategies + Live Paper</h1>
          <p className="lede">
            ORB, Gap-and-Go, Bull Flag, VWAP Reversion, Momentum Failure short.
            Walk-forward backtested on 30 trading days. Paper-trades all signals
            in real time during market hours — no orders placed, just hypothetical
            P&L tracking with 1% risk per trade.
          </p>
        </div>
      </header>

      {/* Strategy filter */}
      {Object.keys(strategies).length > 0 && (
        <section className="day-section">
          <h2 className="day-section__h">Strategies</h2>
          <div className="day-strategies">
            {Object.entries(strategies).map(([key, info]) => (
              <button
                key={key}
                type="button"
                className={`day-strategy-chip ${activeStrategies.has(key) ? 'is-on' : ''}`}
                style={{ '--strategy-color': STRATEGY_COLORS[key] || 'var(--ink-muted)' } as any}
                onClick={() => toggleStrategy(key)}
                title={[info.description, info.research && `Research: ${info.research}`,
                        info['30d_baseline_winrate'] != null && `30d backtest: ${info['30d_baseline_winrate']}% win, avgR ${info['30d_baseline_avgR']}, PF ${info['30d_baseline_pf']}`,
                        info.warning && `⚠ ${info.warning}`,
                        info.note && info.note].filter(Boolean).join('\n\n')}
              >
                <span className="day-strategy-chip__dot" />
                <span className="day-strategy-chip__name">{info.name}</span>
                {info['30d_baseline_winrate'] != null && (
                  <span className="day-strategy-chip__stat mono">
                    {info['30d_baseline_winrate']}% · {info['30d_baseline_avgR'] != null && (info['30d_baseline_avgR'] > 0 ? '+' : '')}{info['30d_baseline_avgR']}R
                  </span>
                )}
                {info.warning && <span className="day-strategy-chip__warn">⚠</span>}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Paper trading panel */}
      {paper && (
        <section className="day-section">
          <div className="day-section__head-row">
            <h2 className="day-section__h">
              Live paper trading · today
              {paper.scan_summary && paper.scan_summary.scanned_symbols > 0 && (
                <span className="day-section__as-of mono"> · {paper.scan_summary.scanned_symbols} symbols scanned</span>
              )}
            </h2>
            <button
              type="button"
              className="day-paper-reset"
              onClick={() => { if (confirm('Delete all paper trades for today?')) paperReset(); }}
              title="Wipe today's paper-trading state"
            >
              ↻ Reset day
            </button>
          </div>

          <div className="day-paper-stats">
            <Stat label="Open positions" value={String(paper.open_count)} />
            <Stat label="Closed positions" value={String(paper.closed_count)} />
            <Stat label="Win rate" value={paper.stats.win_rate_pct != null ? `${paper.stats.win_rate_pct}%` : '—'}
                  highlight={paper.stats.win_rate_pct == null ? undefined : paper.stats.win_rate_pct >= 50 ? 'good' : paper.stats.win_rate_pct >= 35 ? 'warn' : 'bad'} />
            <Stat label="Today's P&L" value={paper.stats.total_pnl_pct != null ? `${paper.stats.total_pnl_pct > 0 ? '+' : ''}${paper.stats.total_pnl_pct.toFixed(2)}%` : '—'}
                  highlight={paper.stats.total_pnl_pct == null ? undefined : paper.stats.total_pnl_pct > 0 ? 'good' : paper.stats.total_pnl_pct < 0 ? 'bad' : 'warn'} />
            <Stat label="Avg R" value={paper.stats.avg_r_multiple != null ? `${paper.stats.avg_r_multiple > 0 ? '+' : ''}${paper.stats.avg_r_multiple}` : '—'}
                  highlight={paper.stats.avg_r_multiple == null ? undefined : paper.stats.avg_r_multiple > 0 ? 'good' : 'bad'}
                  sub="risk-multiple" />
          </div>

          {paper.stats.by_strategy && Object.keys(paper.stats.by_strategy).length > 0 && (
            <table className="day-bt-table">
              <thead><tr><th>Strategy</th><th className="num">Trades</th><th className="num">Win %</th><th className="num">Avg R</th><th className="num">Total P&L</th></tr></thead>
              <tbody>
                {Object.entries(paper.stats.by_strategy).map(([s, st]) => (
                  <tr key={s}>
                    <td><strong>{strategies[s]?.name ?? s}</strong></td>
                    <td className="num mono">{st.n}</td>
                    <td className="num mono">{st.win_rate_pct}%</td>
                    <td className={`num mono ${st.avg_r > 0 ? 'pos' : st.avg_r < 0 ? 'neg' : ''}`}>{st.avg_r > 0 ? '+' : ''}{st.avg_r}</td>
                    <td className={`num mono ${st.total_pnl_pct > 0 ? 'pos' : st.total_pnl_pct < 0 ? 'neg' : ''}`}>{st.total_pnl_pct > 0 ? '+' : ''}{st.total_pnl_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {paper.open.length > 0 && (
            <>
              <h3 className="day-paper-subhead">Open positions</h3>
              <div className="day-paper-grid">
                {paper.open.map((p) => (
                  <div key={p._id} className={`day-paper-card day-paper-card--${p.side}`} onClick={() => setSelected(p.symbol)} role="button" tabIndex={0}>
                    <div className="day-paper-card__head">
                      <strong>{p.symbol}</strong>
                      <span className={`day-paper-card__pill day-paper-card__pill--${p.side}`}>{p.side === 'long' ? '↑' : '↓'} {strategies[p.strategy]?.name ?? p.strategy}</span>
                      <button type="button" className="day-ai-btn"
                              onClick={(e) => { e.stopPropagation(); setReviewSymbol(p.symbol); }}
                              title="Get Gemma's read on this setup">🤖</button>
                    </div>
                    <div className="day-paper-card__row mono">Entry ${p.entry_price.toFixed(2)} · Stop ${p.stop.toFixed(2)} · Target ${p.target.toFixed(2)}</div>
                    <div className="day-paper-card__row mono">Risk {p.risk_pct?.toFixed(2)}% · Reward {p.reward_pct?.toFixed(2)}% · {p.r_multiple_potential}R</div>
                  </div>
                ))}
              </div>
            </>
          )}

          {paper.closed.length > 0 && (
            <>
              <h3 className="day-paper-subhead">Closed positions</h3>
              <table className="day-bt-table">
                <thead><tr><th>Time</th><th>Sym</th><th>Strategy</th><th>Side</th><th className="num">Entry</th><th className="num">Exit</th><th className="num">P&L</th><th className="num">R</th></tr></thead>
                <tbody>
                  {paper.closed.slice(-20).reverse().map((p) => (
                    <tr key={p._id} onClick={() => setSelected(p.symbol)} className="day-bt-row">
                      <td className="mono">{p.exit_ts ? new Date(p.exit_ts + 'Z').toLocaleTimeString() : '—'}</td>
                      <td><strong>{p.symbol}</strong></td>
                      <td>{strategies[p.strategy]?.name ?? p.strategy}</td>
                      <td><span className={`day-paper-card__pill day-paper-card__pill--${p.side}`}>{p.side === 'long' ? '↑' : '↓'} {p.side}</span></td>
                      <td className="num mono">${p.entry_price.toFixed(2)}</td>
                      <td className="num mono">${p.exit_price?.toFixed(2)}</td>
                      <td className={`num mono ${(p.pnl_pct ?? 0) > 0 ? 'pos' : (p.pnl_pct ?? 0) < 0 ? 'neg' : ''}`}>{(p.pnl_pct ?? 0) > 0 ? '+' : ''}{p.pnl_pct?.toFixed(2)}%</td>
                      <td className={`num mono ${(p.r_multiple ?? 0) > 0 ? 'pos' : 'neg'}`}>{(p.r_multiple ?? 0) > 0 ? '+' : ''}{p.r_multiple}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {paper.open_count === 0 && paper.closed_count === 0 && (
            <div className="day-empty">
              No paper trades yet today. Either market is closed, the ORB
              window hasn't completed (first 15min of RTH), or no signals
              from selected strategies have fired with their thresholds.
            </div>
          )}
        </section>
      )}

      {/* Live signals strip */}
      <section className="day-section">
        <h2 className="day-section__h">
          Live signals firing today
          {asOf && <span className="day-section__as-of mono"> · refreshed {new Date(asOf).toLocaleTimeString()}</span>}
        </h2>
        {liveSignals.length === 0 ? (
          <div className="day-empty">
            No signals firing right now from the active strategies.
          </div>
        ) : (
          <div className="day-signal-grid">
            {liveSignals.map((s, i) => (
              <div
                key={`${s.symbol}-${s.entry_ts}-${i}`}
                className={`day-signal-card day-signal-card--${s.side}`}
                style={{ '--strategy-color': STRATEGY_COLORS[s.strategy] || 'var(--ink-muted)' } as any}
                onClick={() => s.symbol && setSelected(s.symbol)}
                role="button"
                tabIndex={0}
              >
                <div className="day-signal-card__head">
                  <strong>{s.symbol}</strong>
                  <span className="day-signal-card__strategy mono">{strategies[s.strategy]?.name ?? s.strategy}</span>
                  <span className={`day-signal-card__side day-signal-card__side--${s.side}`}>
                    {s.side === 'long' ? '↑ LONG' : '↓ SHORT'}
                  </span>
                  {s.symbol && (
                    <button type="button" className="day-ai-btn"
                            onClick={(e) => { e.stopPropagation(); setReviewSymbol(s.symbol!); }}
                            title="Get Gemma's read on this setup">🤖</button>
                  )}
                </div>
                <div className="day-signal-card__row mono">
                  Entry: ${s.entry_price.toFixed(2)} · Stop ${s.stop.toFixed(2)} · Target ${s.target.toFixed(2)}
                </div>
                <div className="day-signal-card__row mono">
                  Risk {s.risk_pct.toFixed(2)}% · Reward {s.reward_pct.toFixed(2)}% · {s.r_multiple_potential}R
                </div>
                <ul className="day-signal-card__reasons">
                  {s.reasons.map((r, j) => <li key={j}>{r}</li>)}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Symbol selector + chart */}
      <section className="day-section">
        <div className="day-section__head-row">
          <h2 className="day-section__h">
            Live chart · {selected}
            <button type="button" className="day-ai-btn day-ai-btn--inline"
                    onClick={() => setReviewSymbol(selected)}
                    title={`Get Gemma's read on ${selected}`}>
              🤖 Gemma's read
            </button>
          </h2>
          <div className="day-symbol-tabs">
            {watchlist.map((s) => (
              <button key={s} type="button" className={`day-symbol-tab ${s === selected ? 'is-active' : ''}`} onClick={() => setSelected(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
        {barsLoading && <div className="day-empty">Loading {selected}…</div>}
        {bars && (
          <>
            <div className="day-chart-meta mono">
              {bars.indicators.opening_range && (
                <span>ORB: {bars.indicators.opening_range.low.toFixed(2)}–{bars.indicators.opening_range.high.toFixed(2)} ({bars.indicators.opening_range.minutes}min)</span>
              )}
              {bars.indicators.premarket && (
                <span>Premarket: {bars.indicators.premarket.low.toFixed(2)}–{bars.indicators.premarket.high.toFixed(2)} ({bars.indicators.premarket.bars} bars)</span>
              )}
              {bars.indicators.relative_volume != null && (
                <span className={bars.indicators.relative_volume >= 1.5 ? 'day-rvol day-rvol--hot' : 'day-rvol'}>
                  RelVol {bars.indicators.relative_volume}× vs 10d avg
                </span>
              )}
            </div>
            <IntradayChart data={bars} signals={symbolSignals} />
          </>
        )}
      </section>

      {/* 30-day backtest for selected */}
      {bt30 && bt30.n_trades > 0 && 'win_rate_pct' in (bt30.stats || {}) && (
        <section className="day-section">
          <h2 className="day-section__h">30-day walk-forward backtest · {selected}</h2>
          <div className="day-bt-grid">
            <Stat label="Trades" value={String(bt30.n_trades)} />
            <Stat label="Trigger rate" value={`${bt30.trigger_rate_pct}%`} sub={`${bt30.days_with_signal}/${bt30.days_evaluated} days`} />
            <Stat label="Win rate"   value={`${(bt30.stats as any).win_rate_pct}%`} highlight={(bt30.stats as any).win_rate_pct >= 45 ? 'good' : (bt30.stats as any).win_rate_pct >= 35 ? 'warn' : 'bad'} />
            <Stat label="Avg R"      value={`${(bt30.stats as any).avg_r_multiple > 0 ? '+' : ''}${(bt30.stats as any).avg_r_multiple}`} highlight={(bt30.stats as any).avg_r_multiple > 0 ? 'good' : 'bad'} />
            <Stat label="Profit factor" value={String((bt30.stats as any).profit_factor ?? '—')} highlight={((bt30.stats as any).profit_factor ?? 0) >= 1.2 ? 'good' : ((bt30.stats as any).profit_factor ?? 0) >= 1 ? 'warn' : 'bad'} />
            <Stat label="Max drawdown" value={`${(bt30.stats as any).max_consecutive_drawdown_pct}%`} highlight="warn" />
          </div>
        </section>
      )}

      {/* Daily checklist guide */}
      <section className="day-section">
        <DayTradingGuide />
      </section>

      <footer className="cm-disclaimer cm-disclaimer--footer">
        <span className="cm-disclaimer__label">Methodology</span>
        <p>
          Five strategies running on 1m bars from Massive (Polygon-rebrand). Walk-forward
          backtested on 30 trading days. Paper trading enters every detected signal
          with hypothetical 1% risk and exits on stop/target/end-of-day-flat. No
          orders are placed anywhere. References: Toby Crabel (ORB), Linda Raschke,
          Ross Cameron (Gap-and-Go), Stockbee (flag), Mike Bellafiore (VWAP), Bo Yoder
          (momentum failure).
        </p>
      </footer>

      {reviewSymbol && (
        <AiReviewModal symbol={reviewSymbol} onClose={() => setReviewSymbol(null)} />
      )}
    </div>
  );
}

function Stat({ label, value, sub, highlight }: { label: string; value: string; sub?: string; highlight?: 'good'|'warn'|'bad' }) {
  return (
    <div className={`day-stat ${highlight ? `day-stat--${highlight}` : ''}`}>
      <div className="day-stat__label">{label}</div>
      <div className="day-stat__value mono">{value}</div>
      {sub && <div className="day-stat__sub mono">{sub}</div>}
    </div>
  );
}
