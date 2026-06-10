import { useState, useMemo, useEffect } from 'react';
import { MarketGaugeBanner } from '../components/MarketGaugeBanner';
import { IntradayChart } from '../components/IntradayChart';
import { DayTradingGuide } from '../components/DayTradingGuide';
import { AiReviewModal } from '../components/AiReviewModal';
import { OvernightGappers } from '../components/OvernightGappers';
import { DayTradingSchedule } from '../components/DayTradingSchedule';
import { DayLeaderboardLeaders } from '../components/DayLeaderboardLeaders';
import { InfoButton } from '../components/InfoButton';
import { useMarketGauge } from '../hooks/useMarketGauge';
import { LiveTapeRead } from '../components/LiveTapeRead';
import { usePatternVerdicts } from '../hooks/usePatternVerdicts';
import { PatternChips } from '../components/PatternChips';
import { OnDemandPatternScan } from '../components/OnDemandPatternScan';
import { TickerCell } from '../components/TickerCell';
import {
  useDayUniverse, useDayBars, useLiveSignals,
  useSymbolBacktest, useStrategies,
  type DaySignal,
} from '../hooks/useDayTrading';

const STRATEGY_COLORS: Record<string, string> = {
  orb:            'var(--gold)',
  gap_and_go:     '#a855f7',
  bull_flag:      'var(--positive)',
  vwap_reversion: '#06b6d4',
};

// How each strategy behaves vs. the tape. In a CHOPPY/weak gauge, mean-reversion
// (VWAP) has the edge and breakouts (ORB / Gap / Flag) tend to fail.
const CHOP_FIT: Record<string, { kind: 'chop' | 'trend'; label: string }> = {
  vwap_reversion:   { kind: 'chop',  label: 'mean-reversion' },
  momentum_failure: { kind: 'chop',  label: 'fade' },
  orb:              { kind: 'trend', label: 'breakout' },
  gap_and_go:       { kind: 'trend', label: 'momentum' },
  bull_flag:        { kind: 'trend', label: 'continuation' },
};

/** Market session in US/Eastern from the browser clock (no holiday calendar). */
function marketSession(): 'premarket' | 'open' | 'afterhours' | 'closed' {
  const et = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const day = et.getDay();
  if (day === 0 || day === 6) return 'closed';
  const hm = et.getHours() * 60 + et.getMinutes();
  if (hm >= 4 * 60 && hm < 9 * 60 + 30) return 'premarket';
  if (hm >= 9 * 60 + 30 && hm < 16 * 60) return 'open';
  if (hm >= 16 * 60 && hm < 20 * 60) return 'afterhours';
  return 'closed';
}

function freshness(ts?: string): string {
  if (!ts) return '';
  const iso = ts.endsWith('Z') ? ts : `${ts}Z`;
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m ago`;
}

const StrategiesInfo = (
  <>
    <p>
      Four long-only setups, each from a documented day-trading framework. Toggle a
      chip to include/exclude it from the live scan. The “%·R” is its 30-day
      walk-forward backtest (win&nbsp;rate · average&nbsp;R).
    </p>
    <ul className="dt-strat-info">
      <li><strong>Opening Range Breakout</strong> — <em>Crabel; Raschke.</em> Break of the first-15-min range on volume. <strong>Breakout · needs trend.</strong></li>
      <li><strong>Gap and Go</strong> — <em>Cameron.</em> Premarket gap + first-bar confirmation continues. <strong>Momentum · needs a catalyst/trend.</strong></li>
      <li><strong>Bull Flag</strong> — <em>Stockbee / IBD.</em> Pole, tight low-volume flag, breakout. <strong>Continuation · needs trend.</strong></li>
      <li><strong>VWAP Reversion</strong> — <em>Steenbarger / Bellafiore.</em> Fade a ≥1.5-ATR stretch below VWAP back to VWAP. <strong>✓ Favored in choppy/range days.</strong></li>
    </ul>
    <p>
      They need <em>liquid, high-volatility</em> names — that's why the page scans
      today's liquid movers (the Aggressive/Conservative toggle), not the whole market.
    </p>
    <p className="dt-strat-info__disc">Educational, backtested on a small sample. Not advice.</p>
  </>
);

export function DayTrading() {
  const universe = useDayUniverse();
  const watchlist = universe.symbols;
  const strategies = useStrategies();
  const gauge = useMarketGauge();
  const [selected, setSelected] = useState<string>('NVDA');

  useEffect(() => {
    if (watchlist.length && !watchlist.includes(selected)) setSelected(watchlist[0]);
  }, [watchlist]);   // eslint-disable-line react-hooks/exhaustive-deps

  const [activeStrategies, setActiveStrategies] =
    useState<Set<string>>(new Set(['orb', 'bull_flag', 'gap_and_go', 'vwap_reversion']));
  const [reviewSymbol, setReviewSymbol] = useState<string | null>(null);

  const stratFilter = useMemo(() => Array.from(activeStrategies), [activeStrategies]);
  const { signals: liveSignals, asOf } = useLiveSignals(watchlist, stratFilter);
  const { data: bars, loading: barsLoading } = useDayBars(selected, 1);
  const { data: bt30 } = useSymbolBacktest(selected, 30);

  const session = marketSession();
  const choppy = !!gauge && (gauge.state === 'caution' || gauge.state === 'risk_off');
  const symbolSignals = liveSignals.filter((s) => s.symbol === selected);

  // In a choppy tape, surface the mean-reversion signals first.
  const sortedSignals = useMemo(() => {
    if (!choppy) return liveSignals;
    return [...liveSignals].sort((a, b) =>
      (CHOP_FIT[b.strategy]?.kind === 'chop' ? 1 : 0) - (CHOP_FIT[a.strategy]?.kind === 'chop' ? 1 : 0));
  }, [liveSignals, choppy]);

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
          <div className="eyebrow">№ 06 — Intraday</div>
          <h1 className="display cm-pagehead__title">Day Trading</h1>
          <p className="lede">
            Liquid movers, 4 long-only setups, your leaderboard leaders — organised by
            <strong> what's buyable right now</strong> vs. what to watch. Tuned to the tape.
          </p>

          <div className="day-universe">
            <div className="day-universe__toggle" role="group" aria-label="Universe profile">
              <button type="button"
                className={`day-universe__tg${universe.profile === 'aggressive' ? ' is-on' : ''}`}
                onClick={() => universe.setProfile('aggressive')}
                title="Highest-ADR movers (more volatile) that are still liquid enough to fill.">
                Aggressive
              </button>
              <button type="button"
                className={`day-universe__tg${universe.profile === 'conservative' ? ' is-on' : ''}`}
                onClick={() => universe.setProfile('conservative')}
                title="Mega-liquid names with a moderate daily range (steadier intraday).">
                Conservative
              </button>
            </div>
            <p className="day-universe__cap">
              <strong>{universe.universeSize}</strong> day-tradeable names →
              {' '}today's <strong>{watchlist.length}</strong>{' '}
              {universe.live ? 'active movers' : 'top names (market closed)'}.
              {universe.criteria && <span className="day-universe__crit mono"> {universe.criteria}</span>}
            </p>
          </div>
        </div>
      </header>

      {/* TAPE BANNER — session + choppy read, sets the whole page's context */}
      <div className={`dt-tape dt-tape--${choppy ? 'chop' : 'trend'}`}>
        <span className="dt-tape__sess">
          {session === 'open' ? '● Markets OPEN — live signals firing'
            : session === 'premarket' ? '○ Pre-market — signals fire at 9:30 ET'
            : session === 'afterhours' ? '○ After hours — as of the close'
            : '○ Markets closed — as of the last close'}
        </span>
        {gauge && (
          <span className="dt-tape__read">
            {choppy
              ? <>Choppy / weak tape (gauge {gauge.score}) — <strong>favor mean-reversion (VWAP)</strong>; breakouts (ORB/Gap/Flag) fail more here.</>
              : <>Constructive tape (gauge {gauge.score}) — breakouts have the wind at their back.</>}
          </span>
        )}
      </div>

      <DayTradingSchedule />

      {/* 📐 On-demand daily-pattern scan of today's movers (Ajay 2026-06-10) —
          these names are mostly OUTSIDE the stored verdict scan's universe,
          so this computes fresh verdicts for exactly what's on this page. */}
      <OnDemandPatternScan symbols={watchlist}
                           title="📐 Daily patterns — today's movers, scanned on demand" />

      {/* ① BUYABLE NOW — the live entry signals, redesigned + tape-aware */}
      <section className="day-section">
        <h2 className="day-section__h">
          <span className="dt-tier-dot dt-tier-dot--buy" /> Buyable now · live entry signals
          {asOf && <span className="day-section__as-of mono"> · refreshed {new Date(asOf).toLocaleTimeString()}</span>}
        </h2>
        {session !== 'open' ? (
          <div className="dt-wait">
            <strong>{session === 'premarket' ? 'Pre-market.' : 'Markets closed.'}</strong>{' '}
            Live entry signals fire during regular hours (9:30 ET). Use your
            <em> Leaderboard leaders</em> and <em>Overnight movers</em> below as the watch list for the open.
          </div>
        ) : sortedSignals.length === 0 ? (
          <div className="day-empty">
            No entry signals firing right now from the active strategies. Watch the leaders below for a trigger.
          </div>
        ) : (
          <div className="dt-sig-grid">
            {sortedSignals.map((s, i) => (
              <SignalCard
                key={`${s.symbol}-${s.entry_ts}-${i}`}
                s={s}
                stratName={strategies[s.strategy]?.name ?? s.strategy}
                choppy={choppy}
                onChart={() => s.symbol && setSelected(s.symbol)}
                onReview={() => s.symbol && setReviewSymbol(s.symbol)}
              />
            ))}
          </div>
        )}
      </section>

      {/* ② LEADERBOARD LEADERS · intraday movers (doubles as the last-close watch list) */}
      <DayLeaderboardLeaders onPick={setSelected} />

      {/* Strategy filter — which setups to scan, tagged by tape fit */}
      {Object.keys(strategies).length > 0 && (
        <section className="day-section">
          <h2 className="day-section__h">
            Strategies <span className="day-section__as-of mono">· tap to include/exclude</span>
            <InfoButton title="Day-trading strategies" inline>{StrategiesInfo}</InfoButton>
          </h2>
          <div className="day-strategies">
            {Object.entries(strategies).map(([key, info]) => {
              const fit = CHOP_FIT[key];
              const mismatch = choppy && fit?.kind === 'trend';
              const favored = choppy && fit?.kind === 'chop';
              return (
                <button
                  key={key}
                  type="button"
                  className={`day-strategy-chip ${activeStrategies.has(key) ? 'is-on' : ''}`}
                  style={{ '--strategy-color': STRATEGY_COLORS[key] || 'var(--ink-muted)' } as any}
                  onClick={() => toggleStrategy(key)}
                  title={[info.description, info.research && `Research: ${info.research}`,
                          info['30d_baseline_winrate'] != null && `30d backtest: ${info['30d_baseline_winrate']}% win, avgR ${info['30d_baseline_avgR']}, PF ${info['30d_baseline_pf']}`,
                          info.warning && `⚠ ${info.warning}`].filter(Boolean).join('\n\n')}
                >
                  <span className="day-strategy-chip__dot" />
                  <span className="day-strategy-chip__name">{info.name}</span>
                  {info['30d_baseline_winrate'] != null && (
                    <span className="day-strategy-chip__stat mono">
                      {info['30d_baseline_winrate']}% · {info['30d_baseline_avgR'] != null && (info['30d_baseline_avgR'] > 0 ? '+' : '')}{info['30d_baseline_avgR']}R
                    </span>
                  )}
                  {fit && (
                    <span className={`dt-chip-fit dt-chip-fit--${mismatch ? 'warn' : favored ? 'good' : 'neutral'}`}>
                      {favored ? '✓ fits chop' : mismatch ? '⚠ needs trend' : fit.label}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* Pre-market — overnight gappers */}
      <OvernightGappers profile={universe.profile} onPick={setSelected} />

      {/* Live chart */}
      <section className="day-section">
        <div className="day-section__head-row">
          <h2 className="day-section__h">
            Live chart · {selected}
            <button type="button" className="day-ai-btn day-ai-btn--inline"
                    onClick={() => setReviewSymbol(selected)} title={`Gemma's read on ${selected}`}>
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
        {/* The pattern-reading strip (Ajay 2026-06-10): latest completed 5-min
            candle vs pivot / daily-pattern line / VWAP / OR — who won the bar,
            at what level, on what volume — plus the daily pattern chip. */}
        <LiveTapeRead symbol={selected} />
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
            <Stat label="Win rate" value={`${(bt30.stats as any).win_rate_pct}%`} highlight={(bt30.stats as any).win_rate_pct >= 45 ? 'good' : (bt30.stats as any).win_rate_pct >= 35 ? 'warn' : 'bad'} />
            <Stat label="Avg R" value={`${(bt30.stats as any).avg_r_multiple > 0 ? '+' : ''}${(bt30.stats as any).avg_r_multiple}`} highlight={(bt30.stats as any).avg_r_multiple > 0 ? 'good' : 'bad'} />
            <Stat label="Profit factor" value={String((bt30.stats as any).profit_factor ?? '—')} highlight={((bt30.stats as any).profit_factor ?? 0) >= 1.2 ? 'good' : ((bt30.stats as any).profit_factor ?? 0) >= 1 ? 'warn' : 'bad'} />
            <Stat label="Max drawdown" value={`${(bt30.stats as any).max_consecutive_drawdown_pct}%`} highlight="warn" />
          </div>
        </section>
      )}

      <section className="day-section">
        <DayTradingGuide />
      </section>

      <footer className="cm-disclaimer cm-disclaimer--footer">
        <span className="cm-disclaimer__label">Methodology</span>
        <p>
          Four long-only strategies on 1m bars from Massive, walk-forward backtested on
          30 trading days; leaders crossed with live prices + the latest scan's buyable
          flag. No orders are placed anywhere — educational, not advice. References:
          Toby Crabel / Linda Raschke (ORB), Ross Cameron (Gap-and-Go), Stockbee (flag),
          Mike Bellafiore (VWAP).
        </p>
      </footer>

      {reviewSymbol && <AiReviewModal symbol={reviewSymbol} onClose={() => setReviewSymbol(null)} />}
    </div>
  );
}

// ── Redesigned signal card: scannable hierarchy, aligned levels, tape fit ─────
function SignalCard({ s, stratName, choppy, onChart, onReview }: {
  s: DaySignal; stratName: string; choppy: boolean;
  onChart: () => void; onReview: () => void;
}) {
  const fit = CHOP_FIT[s.strategy];
  const mismatch = choppy && fit?.kind === 'trend';
  const favored = choppy && fit?.kind === 'chop';
  const r = s.r_multiple_potential;
  const rClass = r >= 1.5 ? 'is-strong' : r >= 1 ? 'is-ok' : 'is-weak';
  const { verdicts } = usePatternVerdicts();
  return (
    <div className={`dt-sig${mismatch ? ' dt-sig--caution' : ''}`} onClick={onChart} role="button" tabIndex={0}>
      <div className="dt-sig__top">
        <span className="dt-sig__sym"><TickerCell symbol={s.symbol || ''} size="1rem" /></span>
        <span className={`dt-sig__side dt-sig__side--${s.side}`}>{s.side === 'long' ? '↑ LONG' : '↓ SHORT'}</span>
        <span className={`dt-sig__rr ${rClass}`}>{r}R</span>
        {/* Daily pattern confluence — an intraday entry on a name whose DAILY
            chart is also forming/confirming carries swing-tailwind context. */}
        <PatternChips v={verdicts.get((s.symbol || '').toUpperCase())} max={1} />
        <button type="button" className="day-ai-btn" onClick={(e) => { e.stopPropagation(); onReview(); }} title="Gemma's read">🤖</button>
      </div>
      <div className="dt-sig__strat">
        {stratName}
        {fit && (
          <span className={`dt-fit dt-fit--${mismatch ? 'warn' : favored ? 'good' : 'neutral'}`}>
            {fit.label}{mismatch ? ' · needs trend ⚠' : favored ? ' · fits chop ✓' : ''}
          </span>
        )}
      </div>
      <div className="dt-sig__fresh mono">
        fired {freshness(s.entry_ts)}
        {s.volume_ratio_at_entry ? ` · vol ${s.volume_ratio_at_entry.toFixed(1)}×` : ''}
      </div>
      <div className="dt-sig__levels">
        <div className="dt-lvl dt-lvl--entry">
          <span className="dt-lvl__k">ENTRY</span>
          <span className="dt-lvl__v mono">${s.entry_price.toFixed(2)}</span>
        </div>
        <div className="dt-lvl dt-lvl--stop">
          <span className="dt-lvl__k">STOP</span>
          <span className="dt-lvl__v mono">${s.stop.toFixed(2)}</span>
          <span className="dt-lvl__p mono">−{s.risk_pct.toFixed(1)}%</span>
        </div>
        <div className="dt-lvl dt-lvl--target">
          <span className="dt-lvl__k">TARGET</span>
          <span className="dt-lvl__v mono">${s.target.toFixed(2)}</span>
          <span className="dt-lvl__p mono">+{s.reward_pct.toFixed(1)}%</span>
        </div>
      </div>
      {s.reasons?.[0] && <div className="dt-sig__why">{s.reasons[0]}</div>}
    </div>
  );
}

function Stat({ label, value, sub, highlight }: { label: string; value: string; sub?: string; highlight?: 'good' | 'warn' | 'bad' }) {
  return (
    <div className={`day-stat ${highlight ? `day-stat--${highlight}` : ''}`}>
      <div className="day-stat__label">{label}</div>
      <div className="day-stat__value mono">{value}</div>
      {sub && <div className="day-stat__sub mono">{sub}</div>}
    </div>
  );
}
