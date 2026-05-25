import { useMemo, useState } from 'react';
import { TickerLink } from '../components/TickerLink';
import { ChatterDeepLinks } from '../components/ChatterDeepLinks';
import { MarketRegimeBanner } from '../components/MarketRegimeBanner';
import {
  useCatalystScan,
  useDeepDive,
  useVolumeAlerts,
  usePremarketScan,
  useInsiderSignal,
  useCatalystCalendar,
  useCatalystTimeline,
  useCatalystStale,
  useCatalystMultiDayAccumulators,
  usePredictions,
  useFrenzyRadar,
} from '../hooks/useCatalysts';
import type {
  Candidate, Quadrant, PumpPhase, PumpAction,
  VolumeAlert, PremarketCandidate, CalendarEvent,
  TimelineEvent, StaleRecord, MultiDayAccumulator,
  Prediction, PredictionTier,
  FrenzyCandidate, FrenzyTier,
} from '../hooks/useCatalysts';

type TopTab = 'predictions' | 'frenzy' | 'now' | 'premarket' | 'calendar' | 'timeline';

type SortKey = 'composite' | 'change' | 'chatter' | 'evidence' | 'volume_surge';

const PHASE_LABEL: Record<PumpPhase, string> = {
  ACCUMULATION: '🌱 Accumulation',
  BREAKOUT: '🚀 Breakout',
  FRENZY: '🔥 Frenzy',
  DISTRIBUTION: '🏃‍♂️ Distribution',
  CRASH: '💥 Crash',
  NONE: '·',
};

const ACTION_LABEL: Record<PumpAction, string> = {
  WATCH: 'WATCH',
  ENTER_VWAP: 'BUY · VWAP retest',
  TRIM: 'TRIM',
  EXIT: 'EXIT',
  AVOID: 'AVOID',
};

const QUADRANT_LABEL: Record<Quadrant, string> = {
  REAL: '🎯 REAL CATALYST',
  PUMP_RISK: '⚠️ PUMP RISK',
  OVERLOOKED: '🔎 OVERLOOKED',
  DEAD: '💤 DEAD',
};

const QUADRANT_HELP: Record<Quadrant, string> = {
  REAL: 'High chatter + hard evidence. The setup is real — both crowds and SEC/news agree.',
  PUMP_RISK: 'High chatter, weak evidence. RYOJ-style. Demand more proof before sizing in.',
  OVERLOOKED: 'Hard evidence (filing, news), little buzz. Could be early — others haven\'t seen it yet.',
  DEAD: 'Move without chatter or evidence. Often microcap noise — usually skip.',
};

export function CatalystsPage() {
  const [tab, setTab] = useState<TopTab>('predictions');
  const { data, loading, refreshing, forceRefresh } = useCatalystScan(60_000);
  const [quadrantFilter, setQuadrantFilter] = useState<Quadrant | 'ALL'>('ALL');
  const [sortKey, setSortKey] = useState<SortKey>('composite');
  const [drillTicker, setDrillTicker] = useState<string | null>(null);
  const [manualTicker, setManualTicker] = useState('');
  const [playbookOpen, setPlaybookOpen] = useState(false);

  // Volume alerts feed (always polling, regardless of tab) — fires browser
  // notifications when a tiny stock crosses 5x avg vol.
  const { alerts: volumeAlerts } = useVolumeAlerts(30_000);

  const sorted = useMemo(() => {
    if (!data) return [];
    let list = data.candidates.slice();
    if (quadrantFilter !== 'ALL') {
      list = list.filter((c) => c.quadrant === quadrantFilter);
    }
    list.sort((a, b) => {
      switch (sortKey) {
        case 'change': return Math.abs(b.change_pct) - Math.abs(a.change_pct);
        case 'chatter': return b.chatter_score - a.chatter_score;
        case 'evidence': return b.evidence_score - a.evidence_score;
        case 'volume_surge': return (b.volume_surge_ratio ?? 0) - (a.volume_surge_ratio ?? 0);
        case 'composite':
        default: return b.composite_score - a.composite_score;
      }
    });
    return list;
  }, [data, quadrantFilter, sortKey]);

  return (
    <div className="cm-page cat-page">
      <MarketRegimeBanner />

      <header className="cm-pagehead">
        <div className="cm-pagehead__col">
          <div className="eyebrow">№ 10 — Catalyst Scanner</div>
          <h1 className="display cm-pagehead__title">Tiny Stocks in Motion</h1>
          <p className="lede">
            Microcaps & sub-$20 names moving on a fresh catalyst or social
            chatter. Each candidate is scored on TWO orthogonal axes —
            <strong> chatter</strong> (Stocktwits + Reddit volume) and{' '}
            <strong>evidence</strong> (SEC filings + news + insider trades) —
            so you can spot the difference between a real setup and a
            <em> RYOJ-style </em> pump where the crowd is loud but the
            paperwork is silent.
          </p>
        </div>
      </header>

      {/* Volume alert toaster — always visible regardless of tab */}
      {volumeAlerts.length > 0 && (
        <VolumeAlertToaster alerts={volumeAlerts} onClick={(t) => setDrillTicker(t)} />
      )}

      {/* Top tabs: Predictions / Now / Pre-market / Calendar / Timeline */}
      <div className="cat-tabs">
        <button
          type="button"
          className={`cat-tab cat-tab--predictions ${tab === 'predictions' ? 'is-active' : ''}`}
          onClick={() => setTab('predictions')}
        >
          🎯 Predictions
        </button>
        <button
          type="button"
          className={`cat-tab cat-tab--frenzy ${tab === 'frenzy' ? 'is-active' : ''}`}
          onClick={() => setTab('frenzy')}
        >
          🔥 Frenzy Radar
        </button>
        <button
          type="button"
          className={`cat-tab ${tab === 'now' ? 'is-active' : ''}`}
          onClick={() => setTab('now')}
        >
          🔥 Now
        </button>
        <button
          type="button"
          className={`cat-tab ${tab === 'premarket' ? 'is-active' : ''}`}
          onClick={() => setTab('premarket')}
        >
          🌅 Pre-market
        </button>
        <button
          type="button"
          className={`cat-tab ${tab === 'calendar' ? 'is-active' : ''}`}
          onClick={() => setTab('calendar')}
        >
          📅 Calendar
        </button>
        <button
          type="button"
          className={`cat-tab ${tab === 'timeline' ? 'is-active' : ''}`}
          onClick={() => setTab('timeline')}
        >
          📜 Timeline
        </button>
      </div>

      {tab === 'predictions' && (
        <PredictionsView onClickTicker={(t) => setDrillTicker(t)} />
      )}
      {tab === 'frenzy' && (
        <FrenzyRadarView onClickTicker={(t) => setDrillTicker(t)} />
      )}
      {tab === 'premarket' && (
        <PremarketView onClickTicker={(t) => setDrillTicker(t)} />
      )}
      {tab === 'calendar' && (
        <CalendarView onClickTicker={(t) => setDrillTicker(t)} />
      )}
      {tab === 'timeline' && (
        <TimelineView onClickTicker={(t) => setDrillTicker(t)} />
      )}

      {/* Original "Now" content follows — only render when on Now tab */}
      {tab !== 'now' ? null : <>

      {/* Pump Playbook — collapsible educational panel */}
      <div className={`cat-playbook ${playbookOpen ? 'is-open' : ''}`}>
        <button
          type="button"
          className="cat-playbook__toggle"
          onClick={() => setPlaybookOpen(!playbookOpen)}
        >
          <span>📖 Pump Playbook</span>
          <span className="cat-playbook__hint">
            {playbookOpen ? 'hide' : 'how to read this tab + when to enter / exit'}
          </span>
          <span className="cat-playbook__arrow">{playbookOpen ? '▲' : '▼'}</span>
        </button>
        {playbookOpen && (
          <div className="cat-playbook__body">
            <div className="cat-playbook__row">
              <h4>The 5-phase pump model</h4>
              <ul className="cat-playbook__phases">
                <li><strong>🌱 Accumulation</strong> — quiet float buying, surge ≥ 1.5×, chatter still low. <em>Watchlist only.</em></li>
                <li><strong>🚀 Breakout</strong> — first 15-50% move with surge 2.5-6×. <em>Best risk/reward — buy on VWAP retest, stop -8%.</em></li>
                <li><strong>🔥 Frenzy</strong> — chatter explodes, +50%+ on day, surge 6×+. <em>Late stage — trim 1/3 every 25%, no new entries.</em></li>
                <li><strong>🏃‍♂️ Distribution</strong> — S-3 / S-1 / 424B5 filed, insider sells, secondary coming. <em>EXIT immediately.</em></li>
                <li><strong>💥 Crash</strong> — already down 15%+ but chatter still loud (bagholders). <em>Don't catch the knife.</em></li>
              </ul>
            </div>

            <div className="cat-playbook__row cat-playbook__row--rules">
              <div>
                <h4>✅ Enter when</h4>
                <ul>
                  <li>Phase is <strong>BREAKOUT</strong> with VWAP retest holding</li>
                  <li>Surge ≥ 5× AND chatter ≥ 50 AND price &gt; $1.50</li>
                  <li>Real catalyst (8-K, FDA, earnings beat) confirms chatter</li>
                  <li>Entry between 9:30-10:00 ET (lunchtime entries get chopped)</li>
                </ul>
              </div>
              <div>
                <h4>❌ Never enter when</h4>
                <ul>
                  <li>Phase is <strong>DISTRIBUTION</strong> (S-3 / 424B5 in last 7d)</li>
                  <li>Phase is <strong>CRASH</strong> (already -15%+, chatter still loud)</li>
                  <li>Pre-market spike with no volume floor</li>
                  <li>After 2:30pm ET (no time to escape on reversal)</li>
                  <li>Evidence score = 0 AND cap &lt; $50M (RYOJ-style — wait)</li>
                </ul>
              </div>
            </div>

            <div className="cat-playbook__row cat-playbook__row--hard">
              <h4>🚨 Hard rules (never break)</h4>
              <ul>
                <li><strong>Position size</strong>: ≤ 1% of portfolio per pump. They can gap -50% overnight.</li>
                <li><strong>Stop loss</strong>: -8% from entry OR below intraday low, whichever comes first. Mental stops fail in fast markets — use real broker stops.</li>
                <li><strong>Profit-taking</strong>: 1/3 at +25%, 1/3 at +50%, ride 1/3 with trailing 10% stop.</li>
                <li><strong>Hard exit</strong>: 3:45pm ET regardless of P/L. <em>Never hold a pump overnight.</em></li>
                <li><strong>Friday rule</strong>: Don't enter pumps after 12pm ET Friday (T+1 settlement risk if it gaps Monday).</li>
              </ul>
            </div>

            <div className="cat-playbook__row cat-playbook__row--screen">
              <h4>How to use this tab</h4>
              <ol>
                <li>Open every morning at 9:25 ET, sort by <em>volume surge</em>.</li>
                <li>Filter to <strong>REAL CATALYST</strong> first — those have evidence backing chatter. Best risk/reward.</li>
                <li>Scan <strong>OVERLOOKED</strong> next — hard evidence, low buzz = early entries before chatter catches up.</li>
                <li><strong>PUMP_RISK</strong> only if surge confirms; otherwise wait for evidence. RYOJ stays here until news drops.</li>
                <li>Skip <strong>DEAD</strong> entirely — random microcap noise.</li>
              </ol>
            </div>
          </div>
        )}
      </div>

      {/* Top bar — refresh + market state + manual deep-dive */}
      <div className="cat-bar">
        <div className="cat-bar__left">
          {data && (
            <span className={`sd-market-pill sd-market-pill--${data.market.state}`}>
              {data.market.state === 'open' && '🟢 LIVE'}
              {data.market.state === 'pre' && '🟡 PRE-MKT'}
              {data.market.state === 'after' && '🟠 AFTER-HRS'}
              {data.market.state === 'closed' && '⚪️ CLOSED'}
              {data.market.state === 'weekend' && '⚪️ WEEKEND'}
            </span>
          )}
          {data && (
            <span className="cat-bar__meta">
              {data.n_total} candidates · scanned in {data.timing.total_sec}s
              {data.cached && <em> · cached {data.cache_age_sec}s ago</em>}
            </span>
          )}
        </div>
        <div className="cat-bar__right">
          <form onSubmit={(e) => { e.preventDefault(); if (manualTicker.trim()) setDrillTicker(manualTicker.trim().toUpperCase()); }}>
            <input
              type="text"
              placeholder="check a specific ticker (e.g. RYOJ)"
              className="cat-bar__input"
              value={manualTicker}
              onChange={(e) => setManualTicker(e.target.value.toUpperCase())}
            />
            <button type="submit" className="cat-bar__btn">deep-dive</button>
          </form>
          <button
            type="button"
            className="lifeboard-btn"
            onClick={() => forceRefresh()}
            disabled={refreshing}
          >
            {refreshing ? 'Scanning…' : '↻ Force refresh'}
          </button>
        </div>
      </div>

      {/* 2D quadrant overview — counts in each cell */}
      {data && (
        <div className="cat-quadrants">
          {(['REAL', 'OVERLOOKED', 'PUMP_RISK', 'DEAD'] as Quadrant[]).map((q) => {
            const n = data[`n_${q.toLowerCase()}` as keyof typeof data] as number ?? 0;
            const isActive = quadrantFilter === q;
            return (
              <button
                key={q}
                type="button"
                className={`cat-quad cat-quad--${q.toLowerCase()} ${isActive ? 'is-active' : ''}`}
                onClick={() => setQuadrantFilter(isActive ? 'ALL' : q)}
                title={QUADRANT_HELP[q]}
              >
                <div className="cat-quad__h">{QUADRANT_LABEL[q]}</div>
                <div className="cat-quad__n mono">{n}</div>
                <div className="cat-quad__hint">{QUADRANT_HELP[q]}</div>
              </button>
            );
          })}
        </div>
      )}

      {/* Sort + active-filter bar */}
      {data && (
        <div className="cat-controls">
          <div className="cat-controls__sort">
            <span className="cat-controls__label">Sort by:</span>
            {(['composite', 'change', 'chatter', 'evidence', 'volume_surge'] as SortKey[]).map((k) => (
              <button
                key={k}
                type="button"
                className={`cat-sort ${sortKey === k ? 'is-active' : ''}`}
                onClick={() => setSortKey(k)}
              >
                {k.replace('_', ' ')}
              </button>
            ))}
          </div>
          {quadrantFilter !== 'ALL' && (
            <button className="cat-controls__clear" onClick={() => setQuadrantFilter('ALL')}>
              clear filter ({quadrantFilter}) ✕
            </button>
          )}
        </div>
      )}

      {loading && <div className="day-empty">Scanning Massive gainers/losers + Stocktwits + Reddit + SEC EDGAR…</div>}

      {/* Card grid */}
      <div className="cat-grid">
        {sorted.map((c) => (
          <CandidateCard key={c.ticker} c={c} onClick={() => setDrillTicker(c.ticker)} />
        ))}
      </div>

      {data && sorted.length === 0 && (
        <div className="day-empty">
          No {quadrantFilter !== 'ALL' ? `${quadrantFilter.toLowerCase()} ` : ''}candidates
          right now. Markets quiet, or try clearing the filter.
        </div>
      )}

      </>}
      {/* end Now tab content */}

      {/* Deep-dive overlay */}
      {drillTicker && (
        <DeepDivePanel ticker={drillTicker} onClose={() => { setDrillTicker(null); setManualTicker(''); }} />
      )}

      <footer className="cm-disclaimer cm-disclaimer--footer">
        <span className="cm-disclaimer__label">Sources</span>
        <p>
          Movers via Massive (paid). Chatter via Stocktwits public stream
          (free) + Reddit search across r/pennystocks, r/wallstreetbets,
          r/smallstreetbets, r/Biotechplays, r/Shortsqueeze. Evidence via
          Massive news + SEC EDGAR (free). Reviews by local Gemma. None of
          this is investment advice. Tiny stocks gap fast — verify before
          sizing.
        </p>
      </footer>
    </div>
  );
}


// ---- CandidateCard ----------------------------------------------------

function CandidateCard({ c, onClick }: { c: Candidate; onClick: () => void }) {
  const isUp = c.change_pct > 0;
  const cap = c.market_cap;
  const capStr = cap ? (cap >= 1e9 ? `$${(cap / 1e9).toFixed(1)}B` : `$${(cap / 1e6).toFixed(0)}M`) : '—';
  const grade = c.review?.evidence_grade ?? 'D';

  return (
    <article className={`cat-card cat-card--${c.quadrant.toLowerCase()}`} onClick={onClick}>
      <header className="cat-card__head">
        <div>
          <h3 className="cat-card__ticker">{c.ticker}</h3>
          {c.company_name && <p className="cat-card__name">{c.company_name}</p>}
        </div>
        <div className="cat-card__price">
          <div className="mono cat-card__last">${c.price.toFixed(2)}</div>
          <div className={`cat-card__chg mono ${isUp ? 'pos' : 'neg'}`}>
            {isUp ? '+' : ''}{c.change_pct.toFixed(2)}%
          </div>
        </div>
      </header>

      <div className="cat-card__quadrow">
        <span className="cat-card__quad">{QUADRANT_LABEL[c.quadrant]}</span>
        {c.pump && c.pump.phase !== 'NONE' && (
          <span className={`cat-phase cat-phase--${c.pump.phase.toLowerCase()}`}>
            {PHASE_LABEL[c.pump.phase]}
          </span>
        )}
      </div>

      {/* Pump action chip — what to do right now */}
      {c.pump && c.pump.action && c.pump.phase !== 'NONE' && (
        <div className={`cat-action cat-action--${c.pump.action.toLowerCase()}`}>
          {ACTION_LABEL[c.pump.action]}
          {c.pump.entry_hint && <span className="cat-action__hint"> — {c.pump.entry_hint}</span>}
          {c.pump.stop_signal && <span className="cat-action__stop"> 🚨 {c.pump.stop_signal}</span>}
        </div>
      )}

      {/* Two score bars side-by-side — chatter vs evidence */}
      <div className="cat-card__bars">
        <ScoreBar label="Chatter" score={c.chatter_score} color="#a855f7" />
        <ScoreBar label="Evidence" score={c.evidence_score} color="#10b981" />
      </div>

      {/* Catalyst summary (Gemma) */}
      <p className="cat-card__summary">{c.review?.catalyst_summary || 'No clear catalyst.'}</p>

      {/* Quick stats row */}
      <div className="cat-card__stats mono">
        <span title="Market cap">{capStr}</span>
        {c.volume_surge_ratio && c.volume_surge_ratio > 1.2 && (
          <span className="cat-card__surge" title="Today's volume vs 10d avg">
            {c.volume_surge_ratio.toFixed(1)}× vol
          </span>
        )}
        <span className="cat-card__grade" title="Evidence grade">grade {grade}</span>
        {c.review?.is_pump_warning && (
          <span className="cat-card__warn" title="High chatter / low evidence — verify before entering">
            ⚠️ pump?
          </span>
        )}
      </div>

      {/* Evidence chips: 8K / offering / 13D / insider / news counts */}
      <div className="cat-card__chips">
        {c.evidence.sec_filings.has_8k && <span className="cat-chip cat-chip--neutral">8-K</span>}
        {c.evidence.sec_filings.has_13d && <span className="cat-chip cat-chip--bull">13D 🐋</span>}
        {c.evidence.sec_filings.has_insider_trade && <span className="cat-chip cat-chip--bull">insider</span>}
        {c.evidence.sec_filings.has_offering && <span className="cat-chip cat-chip--bear">⚠️ offering</span>}
        {c.evidence.news.n_bullish > 0 && <span className="cat-chip cat-chip--bull">📈 {c.evidence.news.n_bullish} bull news</span>}
        {c.evidence.news.n_bearish > 0 && <span className="cat-chip cat-chip--bear">📉 {c.evidence.news.n_bearish} bear news</span>}
        {c.chatter.reddit.n_posts_24h > 3 && <span className="cat-chip cat-chip--chat">🔥 {c.chatter.reddit.n_posts_24h} reddit/24h</span>}
        {c.chatter.stocktwits.n_24h > 10 && <span className="cat-chip cat-chip--chat">💬 {c.chatter.stocktwits.n_24h} ST/24h</span>}
      </div>

      {/* External chatter quick-jumps — sit in card chrome so the user
          doesn't have to expand the deep-dive to read posts */}
      <ChatterDeepLinks ticker={c.ticker} compact />
    </article>
  );
}


// ---- ScoreBar ---------------------------------------------------------

function ScoreBar({ label, score, color }: { label: string; score: number; color: string }) {
  return (
    <div className="cat-bar2">
      <div className="cat-bar2__top">
        <span className="cat-bar2__label">{label}</span>
        <span className="cat-bar2__num mono">{score.toFixed(0)}</span>
      </div>
      <div className="cat-bar2__track">
        <div className="cat-bar2__fill" style={{ width: `${Math.min(100, score)}%`, background: color }} />
      </div>
    </div>
  );
}


// ---- DeepDivePanel — slide-in for one ticker --------------------------

function DeepDivePanel({ ticker, onClose }: { ticker: string; onClose: () => void }) {
  const { data, loading } = useDeepDive(ticker);

  return (
    <>
      <div className="ntp-backdrop" onClick={onClose} />
      <aside className="ntp-drawer cat-drawer" role="dialog">
        <header className="ntp-head">
          <div className="ntp-head__main">
            <h2 className="ntp-ticker">{ticker}</h2>
            {data?.company_name && <p className="ntp-name">{data.company_name}</p>}
            {data && (
              <div className="ntp-tags">
                {data.sector && <span className="ntp-tag">{data.sector}</span>}
                <span className={`ntp-tag cat-quad-pill cat-quad-pill--${(data.quadrant ?? 'DEAD').toLowerCase()}`}>
                  {QUADRANT_LABEL[(data.quadrant ?? 'DEAD') as Quadrant]}
                </span>
              </div>
            )}
          </div>
          <button className="ntp-close" onClick={onClose}>×</button>
        </header>

        <div className="ntp-body">
          {loading && <div className="ntp-loading">Pulling chatter, news, SEC filings, and Gemma review…</div>}

          {data && (
            <>
              {/* Big stats */}
              <section className="ntp-section">
                <div className="cat-bigstats">
                  <div className="cat-bigstat">
                    <div className="cat-bigstat__label">Price</div>
                    <div className="cat-bigstat__val mono">${data.price.toFixed(2)}</div>
                  </div>
                  <div className="cat-bigstat">
                    <div className="cat-bigstat__label">Today</div>
                    <div className={`cat-bigstat__val mono ${data.change_pct > 0 ? 'pos' : 'neg'}`}>
                      {data.change_pct > 0 ? '+' : ''}{data.change_pct.toFixed(2)}%
                    </div>
                  </div>
                  <div className="cat-bigstat">
                    <div className="cat-bigstat__label">Vol surge</div>
                    <div className="cat-bigstat__val mono">{data.volume_surge_ratio ? `${data.volume_surge_ratio.toFixed(1)}×` : '—'}</div>
                  </div>
                  <div className="cat-bigstat">
                    <div className="cat-bigstat__label">Cap</div>
                    <div className="cat-bigstat__val mono">
                      {data.market_cap ? (data.market_cap >= 1e9 ? `$${(data.market_cap / 1e9).toFixed(1)}B` : `$${(data.market_cap / 1e6).toFixed(0)}M`) : '—'}
                    </div>
                  </div>
                </div>
              </section>

              {/* Score axes */}
              <section className="ntp-section">
                <h3 className="ntp-section__h">Chatter vs Evidence</h3>
                <div className="cat-card__bars cat-card__bars--big">
                  <ScoreBar label="Chatter score" score={data.chatter_score} color="#a855f7" />
                  <ScoreBar label="Evidence score" score={data.evidence_score} color="#10b981" />
                </div>
              </section>

              {/* Gemma review */}
              {data.review && (
                <section className="ntp-section">
                  <h3 className="ntp-section__h">
                    Gemma read
                    <span className="cat-grade-pill">grade {data.review.evidence_grade}</span>
                    {data.review.is_pump_warning && <span className="cat-pump-pill">⚠️ pump warning</span>}
                  </h3>
                  <p className="ntp-text">{data.review.catalyst_summary}</p>
                  {(data.review.bull_pull || data.review.bear_pull) && (
                    <div className="ntp-bullbear">
                      {data.review.bull_pull && (
                        <div className="ntp-bull"><strong>Bull:</strong> {data.review.bull_pull}</div>
                      )}
                      {data.review.bear_pull && (
                        <div className="ntp-bear"><strong>Bear:</strong> {data.review.bear_pull}</div>
                      )}
                    </div>
                  )}
                </section>
              )}

              {/* Evidence: news */}
              {(data.evidence.news.bullish.length + data.evidence.news.bearish.length + data.evidence.news.neutral.length > 0) && (
                <section className="ntp-section">
                  <h3 className="ntp-section__h">News (last 48h)</h3>
                  <ul className="cat-news-list">
                    {[
                      ...data.evidence.news.bullish.map((n) => ({ ...n, t: 'bullish' as const })),
                      ...data.evidence.news.bearish.map((n) => ({ ...n, t: 'bearish' as const })),
                      ...data.evidence.news.neutral.map((n) => ({ ...n, t: 'neutral' as const })),
                    ].slice(0, 8).map((n, i) => (
                      <li key={i} className={`cat-news cat-news--${n.t}`}>
                        {n.url ? <a href={n.url} target="_blank" rel="noreferrer">{n.title} ↗</a> : <span>{n.title}</span>}
                        {n.publisher && <span className="cat-news__pub"> · {n.publisher}</span>}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Evidence: SEC filings */}
              {data.evidence.sec_filings.items.length > 0 && (
                <section className="ntp-section">
                  <h3 className="ntp-section__h">SEC filings (last 7 days)</h3>
                  <ul className="cat-news-list">
                    {data.evidence.sec_filings.items.map((f, i) => (
                      <li key={i} className={`cat-news cat-news--${f.tone}`}>
                        {f.url ? <a href={f.url} target="_blank" rel="noreferrer"><strong>{f.form}</strong> · {f.filing_date} ↗</a> : <span><strong>{f.form}</strong> · {f.filing_date}</span>}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Chatter: Reddit + Stocktwits + external deep-links */}
              <section className="ntp-section">
                <h3 className="ntp-section__h">Chatter</h3>

                {/* External chatter sources — direct deep-links so the user
                    can dig further on each platform. All open in new tabs. */}
                <ChatterDeepLinks
                  ticker={data.ticker}
                  subreddits={data.chatter.reddit.subreddits}
                />

                <div className="cat-chatter-stats mono">
                  <span>Stocktwits: {data.chatter.stocktwits.n_24h} msgs/24h</span>
                  {data.chatter.stocktwits.sentiment_pct_bullish !== null && (
                    <span> · {data.chatter.stocktwits.sentiment_pct_bullish}% bullish</span>
                  )}
                  <span> · Reddit: {data.chatter.reddit.n_posts_24h} posts/24h ({data.chatter.reddit.n_posts_7d}/7d)</span>
                </div>
                {data.chatter.reddit.top && (
                  <p className="cat-top-thread">
                    Top thread:{' '}
                    <a href={data.chatter.reddit.top.url} target="_blank" rel="noreferrer">
                      "{data.chatter.reddit.top.title}" ↗
                    </a>{' '}
                    <span className="ntp-rel__strength mono">
                      ({data.chatter.reddit.top.score} pts · {data.chatter.reddit.top.n_comments} comments ·{' '}
                      <a
                        href={`https://www.reddit.com/r/${data.chatter.reddit.top.subreddit}/search/?q=%24${data.ticker}&restrict_sr=1&sort=new`}
                        target="_blank"
                        rel="noreferrer"
                        className="cat-sub-link"
                      >
                        r/{data.chatter.reddit.top.subreddit}
                      </a>
                      )
                    </span>
                  </p>
                )}
                {data.chatter.sample_blurbs.length > 0 && (
                  <ul className="cat-blurbs">
                    {data.chatter.sample_blurbs.map((b, i) => (
                      <li key={i}>"{b}"</li>
                    ))}
                  </ul>
                )}
              </section>

              <footer className="ntp-footer">
                <TickerLink
                  ticker={data.ticker}
                  fromLabel="Catalysts"
                  className="ntp-action ntp-action--primary"
                  title="Open full SEPA detail (Cmd/Ctrl-click for new tab)"
                >
                  Open full SEPA detail →
                </TickerLink>
              </footer>
            </>
          )}

          {!loading && !data && (
            <p className="ntp-empty">No data for {ticker}. Could be delisted or wrong symbol.</p>
          )}

          {/* Insider Form 4 cluster — embedded inside the deep-dive */}
          {data && <InsidersSection ticker={data.ticker} />}
        </div>
      </aside>
    </>
  );
}


// ====================================================================
// VolumeAlertToaster — floating banner with today's fired alerts
// ====================================================================

function VolumeAlertToaster({ alerts, onClick }: { alerts: VolumeAlert[]; onClick: (t: string) => void }) {
  const [collapsed, setCollapsed] = useState(false);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const visible = alerts.filter((a) => !dismissed.has(a.ticker));
  if (visible.length === 0) return null;

  return (
    <div className={`vat ${collapsed ? 'vat--collapsed' : ''}`}>
      <header className="vat__head">
        <strong>🚨 Volume alerts today ({visible.length})</strong>
        <button type="button" className="vat__btn" onClick={() => setCollapsed(!collapsed)}>
          {collapsed ? 'show' : 'hide'}
        </button>
      </header>
      {!collapsed && (
        <ul className="vat__list">
          {visible.slice(0, 8).map((a) => {
            const p = a.payload || {};
            return (
              <li key={a.ticker + (a.fired_at ?? '')} className="vat__item" onClick={() => onClick(a.ticker)}>
                <strong className="vat__ticker">{a.ticker}</strong>
                <span className="vat__surge mono">{p.surge?.toFixed(1)}× vol</span>
                <span className={`vat__chg mono ${(p.change_pct ?? 0) > 0 ? 'pos' : 'neg'}`}>
                  {(p.change_pct ?? 0) > 0 ? '+' : ''}{(p.change_pct ?? 0).toFixed(1)}%
                </span>
                <span className="vat__price mono">${p.price?.toFixed(2)}</span>
                <span className="vat__name">{p.company_name?.slice(0, 30)}</span>
                <button
                  type="button"
                  className="vat__dismiss"
                  onClick={(e) => { e.stopPropagation(); setDismissed((prev) => new Set(prev).add(a.ticker)); }}
                  title="Dismiss"
                >×</button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}


// ====================================================================
// PremarketView — pre-market gappers
// ====================================================================

function PremarketView({ onClickTicker }: { onClickTicker: (t: string) => void }) {
  const { data, loading, refetch } = usePremarketScan();

  return (
    <div className="cat-premarket">
      <div className="cat-bar">
        <div className="cat-bar__left">
          {data && (
            <span className={`sd-market-pill sd-market-pill--${data.window.in_window ? 'pre' : 'closed'}`}>
              {data.window.in_window ? '🟡 PRE-MKT' : '⚪️ ' + (data.window.label || 'Closed')}
            </span>
          )}
          {data?.window.minutes_until_open != null && (
            <span className="cat-bar__meta">
              opens in {Math.floor(data.window.minutes_until_open / 60)}h {data.window.minutes_until_open % 60}m
            </span>
          )}
          {data && (
            <span className="cat-bar__meta">
              · scanned {data.n_universe_scanned} tickers · found {data.n_movers_found} movers
            </span>
          )}
        </div>
        <div className="cat-bar__right">
          <button type="button" className="lifeboard-btn" onClick={refetch} disabled={loading}>
            {loading ? 'Scanning…' : '↻ Refresh'}
          </button>
        </div>
      </div>

      {loading && <div className="day-empty">Pulling pre-market gappers…</div>}

      {data && data.candidates.length > 0 && (
        <div className="cat-grid">
          {data.candidates.map((c) => <PremarketCard key={c.ticker} c={c} onClick={() => onClickTicker(c.ticker)} />)}
        </div>
      )}

      {data && data.candidates.length === 0 && !loading && (
        <div className="day-empty">
          {data.window.in_window
            ? 'No tiny stocks gapping in pre-market right now. Good — fewer pumps to chase.'
            : 'Markets are open / closed (not in pre-market window). Switch to "Now" tab for live regular-session candidates.'}
        </div>
      )}
    </div>
  );
}

function PremarketCard({ c, onClick }: { c: PremarketCandidate; onClick: () => void }) {
  const isUp = c.change_pct > 0;
  const cap = c.market_cap;
  const capStr = cap ? (cap >= 1e9 ? `$${(cap / 1e9).toFixed(1)}B` : `$${(cap / 1e6).toFixed(0)}M`) : '—';
  return (
    <article className="cat-card cat-card--premarket" onClick={onClick}>
      <header className="cat-card__head">
        <div>
          <h3 className="cat-card__ticker">{c.ticker}</h3>
          {c.company_name && <p className="cat-card__name">{c.company_name}</p>}
        </div>
        <div className="cat-card__price">
          <div className="mono cat-card__last">${c.price.toFixed(2)}</div>
          <div className={`cat-card__chg mono ${isUp ? 'pos' : 'neg'}`}>
            {isUp ? '+' : ''}{c.change_pct.toFixed(2)}%
          </div>
        </div>
      </header>
      <div className="cat-card__quad" style={{ color: 'var(--gold)' }}>🌅 PRE-MARKET GAP</div>
      <div className="cat-card__stats mono">
        <span>{capStr}</span>
        {c.sector && <span>{c.sector}</span>}
        <span>vol {(c.volume / 1e3).toFixed(0)}k</span>
      </div>
      <p className="cat-card__summary">
        Pre-market gap on {c.ticker}. Wait for market open to confirm — pre-market spikes can fake out without a volume floor. Watch first 30 min for VWAP retest.
      </p>
    </article>
  );
}


// ====================================================================
// CalendarView — forward catalyst calendar (timeline)
// ====================================================================

function CalendarView({ onClickTicker }: { onClickTicker: (t: string) => void }) {
  const { data, loading, forceRefresh } = useCatalystCalendar(30);
  const [filter, setFilter] = useState<'all' | 'earnings' | 'fda' | 'macro'>('all');

  const events = useMemo(() => {
    if (!data) return [];
    if (filter === 'all') return data.timeline;
    return data.by_type[filter];
  }, [data, filter]);

  // Group events by date for the timeline
  const byDate = useMemo(() => {
    const m: Record<string, CalendarEvent[]> = {};
    for (const e of events) {
      const d = e.date || 'unknown';
      if (!m[d]) m[d] = [];
      m[d].push(e);
    }
    return Object.entries(m).sort((a, b) => a[0].localeCompare(b[0]));
  }, [events]);

  return (
    <div className="cat-calendar">
      <div className="cat-bar">
        <div className="cat-bar__left">
          {data && (
            <span className="cat-bar__meta">
              <strong>{data.n_total}</strong> events in next {data.days_window} days
              · {data.n_earnings} earnings
              · {data.n_fda} FDA/clinical
              · {data.n_macro} macro
            </span>
          )}
        </div>
        <div className="cat-bar__right">
          <div className="cat-controls__sort">
            {(['all', 'earnings', 'fda', 'macro'] as const).map((k) => (
              <button
                key={k}
                type="button"
                className={`cat-sort ${filter === k ? 'is-active' : ''}`}
                onClick={() => setFilter(k)}
              >
                {k}
              </button>
            ))}
          </div>
          <button type="button" className="lifeboard-btn" onClick={forceRefresh}>
            ↻ Refresh
          </button>
        </div>
      </div>

      {loading && <div className="day-empty">Loading earnings + FDA + macro events…</div>}

      {!loading && byDate.length === 0 && (
        <div className="day-empty">No events in this window.</div>
      )}

      <div className="cat-timeline">
        {byDate.map(([date, evs]) => (
          <div key={date} className="cat-tl-row">
            <div className="cat-tl-date mono">{formatDate(date)}</div>
            <div className="cat-tl-events">
              {evs.map((e, i) => (
                <CalendarEventCard key={i} ev={e} onClickTicker={onClickTicker} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso + 'T12:00:00Z');
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  } catch { return iso; }
}

function CalendarEventCard({ ev, onClickTicker }: { ev: CalendarEvent; onClickTicker: (t: string) => void }) {
  const typeLabel = ev.type === 'earnings' ? '📊 Earnings'
    : ev.type === 'fda_readout' ? '🧬 FDA / Clinical'
    : '🏛️ Macro';
  return (
    <div className={`cat-tl-event cat-tl-event--${ev.type}`}>
      <div className="cat-tl-event__type">{typeLabel}</div>
      <div className="cat-tl-event__title">
        {ev.ticker ? (
          <button type="button" className="cat-tl-event__ticker" onClick={() => onClickTicker(ev.ticker!)}>
            {ev.ticker}
          </button>
        ) : null}
        {' '}
        {ev.url ? <a href={ev.url} target="_blank" rel="noreferrer">{ev.title} ↗</a> : ev.title}
      </div>
      {ev.sponsor && <div className="cat-tl-event__sub">{ev.sponsor} · phase {ev.phase}</div>}
      {ev.description && <div className="cat-tl-event__sub">{ev.description}</div>}
    </div>
  );
}


// ====================================================================
// InsidersSection — embedded in deep-dive
// ====================================================================

function InsidersSection({ ticker }: { ticker: string }) {
  const { data, loading } = useInsiderSignal(ticker);
  if (loading) return (
    <section className="ntp-section">
      <h3 className="ntp-section__h">Insider activity (Form 4)</h3>
      <div className="ntp-loading">Pulling Form 4 filings from EDGAR…</div>
    </section>
  );
  if (!data) return null;

  const fmt$ = (n: number) => n >= 1e6 ? `$${(n/1e6).toFixed(1)}M` : `$${(n/1e3).toFixed(0)}k`;
  const netClass = data.net_buy_value_usd_7d > 0 ? 'pos' : data.net_buy_value_usd_7d < 0 ? 'neg' : '';

  return (
    <section className="ntp-section">
      <h3 className="ntp-section__h">
        Insider activity (Form 4)
        {data.cluster_detected && (
          <span className="cat-cluster-pill">🐋 CLUSTER ({data.n_buyers_7d} buyers)</span>
        )}
      </h3>

      <div className="cat-insider-stats mono">
        <span>{data.n_buyers_7d} buyers · {data.n_sellers_7d} sellers (last 7 days)</span>
        <span className={`cat-insider-net ${netClass}`}>net {fmt$(data.net_buy_value_usd_7d)}</span>
        <span>cluster score: <strong>{data.cluster_score}/100</strong></span>
      </div>

      {data.recent.length > 0 ? (
        <ul className="cat-insider-list">
          {data.recent.slice(0, 8).map((tx, i) => (
            <li key={i} className={`cat-insider cat-insider--${tx.direction}`}>
              <span className="cat-insider__name">{tx.owner_name}</span>
              <span className="cat-insider__role">{tx.role}{tx.officer_title ? ` · ${tx.officer_title}` : ''}</span>
              <span className="mono cat-insider__amt">
                {tx.direction === 'buy' ? '+' : tx.direction === 'sell' ? '−' : ''}
                {fmt$(Math.abs(tx.net_value || tx.buy_value || tx.sell_value))}
              </span>
              <span className="cat-insider__date">{tx.transaction_date || tx.filing_date}</span>
              {tx.filing_url && <a href={tx.filing_url} target="_blank" rel="noreferrer" className="cat-insider__link">↗</a>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="ntp-empty">No Form 4 filings in last 14 days.</p>
      )}
    </section>
  );
}


// ====================================================================
// TimelineView — intraday hour-by-hour deltas + multi-day accumulators
// + stalled tickers
// ====================================================================

function TimelineView({ onClickTicker }: { onClickTicker: (t: string) => void }) {
  const { data: timeline, loading: tlLoading } = useCatalystTimeline();
  const { data: stale, loading: stLoading } = useCatalystStale(3);
  const { data: multiDay, loading: mdLoading } = useCatalystMultiDayAccumulators(3, 10);

  return (
    <div className="cat-timeline-view">
      {/* SECTION 1: Multi-day accumulators (the user's primary ask) */}
      <section className="cat-section">
        <header className="cat-section__head">
          <div>
            <h2 className="cat-section__h">🔮 Multi-day accumulators</h2>
            <p className="cat-section__sub">
              Tiny stocks that have appeared on the catalyst list across <strong>multiple sessions</strong>{' '}
              AND show positive Chaikin Money Flow (10-day window). Sustained signal — not one-day pumps.
            </p>
          </div>
          {multiDay && (
            <span className="cat-section__meta mono">
              {multiDay.n_with_strong_accum} of {multiDay.n_universe} sticky names accumulating
            </span>
          )}
        </header>
        {mdLoading && <div className="day-empty">Cross-referencing snapshot history with 10-day Chaikin Money Flow…</div>}
        {multiDay && multiDay.accumulators.length > 0 ? (
          <table className="cat-tl-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th className="cat-tl-num">Sessions</th>
                <th className="cat-tl-num">Accum</th>
                <th className="cat-tl-num">CMF</th>
                <th className="cat-tl-num">Cap</th>
                <th>Latest signal</th>
              </tr>
            </thead>
            <tbody>
              {multiDay.accumulators.map((a) => (
                <MultiDayAccumRow key={a.ticker} a={a} onClick={() => onClickTicker(a.ticker)} />
              ))}
            </tbody>
          </table>
        ) : (
          !mdLoading && (
            <div className="day-empty">
              No multi-day accumulators yet. Need ≥{multiDay?.min_session_appearances ?? 3} sessions of
              snapshot history before this populates. Cron is recording one snapshot per hour
              during market hours.
            </div>
          )
        )}
      </section>

      {/* SECTION 2: Intraday timeline (hour-by-hour deltas) */}
      <section className="cat-section">
        <header className="cat-section__head">
          <div>
            <h2 className="cat-section__h">📜 Today's hour-by-hour timeline</h2>
            <p className="cat-section__sub">
              What changed this session: new entries, chatter spikes, evidence-jumps, quadrant transitions.
            </p>
          </div>
          {timeline && (
            <span className="cat-section__meta mono">
              {timeline.n_snapshots} snapshots · {timeline.events.length} change events
            </span>
          )}
        </header>
        {tlLoading && <div className="day-empty">Loading timeline…</div>}
        {timeline && timeline.events.length === 0 && (
          <div className="day-empty">
            {timeline.n_snapshots <= 1
              ? `Only ${timeline.n_snapshots} snapshot(s) so far this session — need at least 2 to compute deltas. Cron records one per hour during market hours.`
              : 'No significant changes yet today.'}
          </div>
        )}
        {timeline && timeline.events.length > 0 && (
          <ol className="cat-tl-events">
            {timeline.events.slice().reverse().map((e, i) => (
              <TimelineEventRow key={i} e={e} onClick={onClickTicker} />
            ))}
          </ol>
        )}
      </section>

      {/* SECTION 3: Stalled tickers — buckets */}
      <section className="cat-section">
        <header className="cat-section__head">
          <div>
            <h2 className="cat-section__h">🐢 Stalled (≥3h, no significant move)</h2>
            <p className="cat-section__sub">
              Names on the list with a stable composite_score for hours.
              <strong> Stable winners</strong> = sustained quality;{' '}
              <strong>stalled chatter</strong> = pump fading without follow-through.
            </p>
          </div>
        </header>
        {stLoading && <div className="day-empty">Computing stale list…</div>}
        {stale && (
          <div className="cat-stale-grid">
            <StaleBucket
              title="🟢 Stable winners"
              hint="REAL or OVERLOOKED — quality signal sustained for hours"
              records={stale.stable_winners}
              borderColor="var(--positive)"
              onClick={onClickTicker}
            />
            <StaleBucket
              title="⚠️ Stalled chatter"
              hint="PUMP_RISK — chatter not converting to evidence (often means the pump is fading)"
              records={stale.stalled_chatter}
              borderColor="#fb923c"
              onClick={onClickTicker}
            />
            <StaleBucket
              title="💤 Ambient dead"
              hint="DEAD — moves with no chatter or evidence follow-up"
              records={stale.ambient_dead}
              borderColor="var(--ink-subtle)"
              onClick={onClickTicker}
            />
          </div>
        )}
      </section>
    </div>
  );
}


function MultiDayAccumRow({ a, onClick }: { a: MultiDayAccumulator; onClick: () => void }) {
  const cap = a.market_cap;
  const capStr = cap ? (cap >= 1e9 ? `$${(cap / 1e9).toFixed(1)}B` : `$${(cap / 1e6).toFixed(0)}M`) : '—';
  const labelClass = a.accumulation_score >= 60 ? 'pos strong' : a.accumulation_score >= 30 ? 'pos' : '';
  return (
    <tr onClick={onClick} className="cat-tl-row">
      <td>
        <strong className="cat-tl-ticker">{a.ticker}</strong>
        {a.company_name && <div className="cat-tl-name">{a.company_name.slice(0, 30)}</div>}
      </td>
      <td className="mono cat-tl-num">
        <strong>{a.n_session_dates_seen}</strong>
        <span className="cat-tl-sub"> days</span>
      </td>
      <td className={`mono cat-tl-num ${labelClass}`}>
        +{a.accumulation_score.toFixed(0)}
        <div className="cat-tl-sub">{a.accumulation_label}</div>
      </td>
      <td className="mono cat-tl-num">{(a.cmf * 100).toFixed(1)}%</td>
      <td className="mono cat-tl-num">{capStr}</td>
      <td>
        {a.latest_quadrant && (
          <span className={`cat-tl-quad cat-tl-quad--${(a.latest_quadrant ?? 'DEAD').toLowerCase()}`}>
            {a.latest_quadrant}
          </span>
        )}
        {' '}
        {a.latest_change_pct !== undefined && (
          <span className={`mono ${(a.latest_change_pct ?? 0) > 0 ? 'pos' : 'neg'}`}>
            {(a.latest_change_pct ?? 0) > 0 ? '+' : ''}{(a.latest_change_pct ?? 0).toFixed(1)}%
          </span>
        )}
        {a.latest_volume_surge && a.latest_volume_surge > 1.5 && (
          <span className="cat-tl-surge mono"> · {a.latest_volume_surge.toFixed(1)}× vol</span>
        )}
      </td>
    </tr>
  );
}


function TimelineEventRow({ e, onClick }: { e: TimelineEvent; onClick: (t: string) => void }) {
  const time = new Date(e.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <li className="cat-tl-event">
      <div className="cat-tl-event__time mono">{time}</div>
      <div className="cat-tl-event__body">
        {e.entered.length > 0 && (
          <div className="cat-tl-row-line">
            <span className="cat-tl-tag cat-tl-tag--enter">🆕 New ({e.n_entered})</span>
            {e.entered.slice(0, 8).map((c, i) => (
              <button key={i} type="button" className="cat-tl-chip" onClick={() => onClick(c.ticker)}>
                {c.ticker}
                {c.change_pct !== undefined && (
                  <span className={`mono ${(c.change_pct ?? 0) > 0 ? 'pos' : 'neg'}`}>
                    {' '}{(c.change_pct ?? 0) > 0 ? '+' : ''}{(c.change_pct ?? 0).toFixed(1)}%
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
        {e.chatter_jumpers.length > 0 && (
          <div className="cat-tl-row-line">
            <span className="cat-tl-tag cat-tl-tag--chatter">⬆️ Chatter ({e.n_chatter_jumps})</span>
            {e.chatter_jumpers.slice(0, 6).map((c, i) => (
              <button key={i} type="button" className="cat-tl-chip" onClick={() => onClick(c.ticker)}>
                {c.ticker} <span className="mono pos">+{c.delta.toFixed(0)}</span>
              </button>
            ))}
          </div>
        )}
        {e.evidence_jumpers.length > 0 && (
          <div className="cat-tl-row-line">
            <span className="cat-tl-tag cat-tl-tag--evidence">📈 Evidence ({e.n_evidence_jumps})</span>
            {e.evidence_jumpers.slice(0, 6).map((c, i) => (
              <button key={i} type="button" className="cat-tl-chip" onClick={() => onClick(c.ticker)}>
                {c.ticker} <span className="mono pos">+{c.delta.toFixed(0)}</span>
              </button>
            ))}
          </div>
        )}
        {e.quadrant_transitions.length > 0 && (
          <div className="cat-tl-row-line">
            <span className="cat-tl-tag cat-tl-tag--quad">🔀 Quadrant ({e.n_quadrant_transitions})</span>
            {e.quadrant_transitions.slice(0, 6).map((q, i) => (
              <button key={i} type="button" className="cat-tl-chip" onClick={() => onClick(q.ticker)}>
                {q.ticker} <span className="mono">{q.from_quadrant} → {q.to_quadrant}</span>
              </button>
            ))}
          </div>
        )}
        {e.phase_transitions.length > 0 && (
          <div className="cat-tl-row-line">
            <span className="cat-tl-tag cat-tl-tag--phase">🔁 Phase ({e.n_phase_transitions})</span>
            {e.phase_transitions.slice(0, 6).map((p, i) => (
              <button key={i} type="button" className="cat-tl-chip" onClick={() => onClick(p.ticker)}>
                {p.ticker} <span className="mono">{p.from_phase} → {p.to_phase}</span>
              </button>
            ))}
          </div>
        )}
        {e.exited.length > 0 && (
          <div className="cat-tl-row-line">
            <span className="cat-tl-tag cat-tl-tag--exit">↘️ Dropped ({e.n_exited})</span>
            {e.exited.slice(0, 8).map((c, i) => (
              <span key={i} className="cat-tl-chip cat-tl-chip--muted">{c.ticker}</span>
            ))}
          </div>
        )}
      </div>
    </li>
  );
}


function StaleBucket({ title, hint, records, borderColor, onClick }:
  { title: string; hint: string; records: StaleRecord[]; borderColor: string; onClick: (t: string) => void }) {
  return (
    <div className="cat-stale-bucket" style={{ borderLeftColor: borderColor }}>
      <div className="cat-stale-bucket__h">
        <strong>{title}</strong>
        <span className="cat-stale-bucket__count mono">{records.length}</span>
      </div>
      <p className="cat-stale-bucket__hint">{hint}</p>
      {records.length === 0 ? (
        <p className="cat-stale-bucket__empty">none</p>
      ) : (
        <ul className="cat-stale-list">
          {records.slice(0, 8).map((r) => (
            <li key={r.ticker} onClick={() => onClick(r.ticker)} className="cat-stale-row">
              <strong>{r.ticker}</strong>
              <span className="mono cat-stale-hours">{r.hours_on_list}h</span>
              <span className={`mono ${(r.change_pct ?? 0) > 0 ? 'pos' : 'neg'}`}>
                {(r.change_pct ?? 0) > 0 ? '+' : ''}{(r.change_pct ?? 0).toFixed(1)}%
              </span>
              <span className="cat-stale-comp mono">comp {r.composite_score.toFixed(0)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}


// ChatterDeepLinks moved to its own component file at
// `components/ChatterDeepLinks.tsx` so it can be reused in NodeThesisPanel,
// SepaCandidate's chatter tab, and as compact icons on catalyst cards.


// ====================================================================
// PredictionsView — synthesized conviction across all signals
// ====================================================================

const TIER_COLORS: Record<PredictionTier, string> = {
  HIGH: 'var(--positive)',
  MEDIUM: 'var(--gold)',
  WATCH: '#06b6d4',
  AVOID: 'var(--negative)',
};

const TIER_LABELS: Record<PredictionTier, string> = {
  HIGH: '🎯 HIGH CONVICTION',
  MEDIUM: '🟡 MEDIUM',
  WATCH: '👀 WATCH',
  AVOID: '🚫 AVOID',
};

const TIER_HINTS: Record<PredictionTier, string> = {
  HIGH:   'Multiple independent signals stack — best risk/reward setups today.',
  MEDIUM: 'Strong on one or two axes, partial confirmation. Verify before sizing.',
  WATCH:  'One signal showing — wait for confirmation from another axis.',
  AVOID:  'Hard veto fired (often dilutive offering) or pure-chatter without evidence.',
};


function PredictionsView({ onClickTicker }: { onClickTicker: (t: string) => void }) {
  const { data, loading, refreshing, forceRefresh } = usePredictions(5 * 60_000);
  const [tierFilter, setTierFilter] = useState<PredictionTier | 'ALL'>('ALL');

  const filtered = useMemo(() => {
    if (!data) return [];
    if (tierFilter === 'ALL') return data.predictions;
    return data.predictions.filter((p) => p.conviction_tier === tierFilter);
  }, [data, tierFilter]);

  return (
    <div className="cat-predictions">
      <header className="cat-section__head" style={{ marginTop: 12 }}>
        <div>
          <h2 className="cat-section__h">🎯 Today's high-conviction predictions</h2>
          <p className="cat-section__sub">
            Synthesizes <strong>every</strong> independent signal — catalyst quadrant + multi-day Chaikin
            Money Flow + insider Form 4 clusters + stable-winner status + volume surge + forward-calendar
            events + multi-day appearance count + news tone — into a single conviction score.
            HIGH = multiple signals stack. AVOID = hard veto (usually dilutive offering filed).
          </p>
        </div>
        <button
          type="button"
          className="lifeboard-btn"
          onClick={() => forceRefresh()}
          disabled={refreshing}
        >
          {refreshing ? 'Refreshing…' : '↻ Force refresh'}
        </button>
      </header>

      {data && (
        <div className="cat-tier-pills">
          {(['ALL', 'HIGH', 'MEDIUM', 'WATCH', 'AVOID'] as const).map((k) => {
            const count = k === 'ALL' ? data.n_total : (data.by_tier[k] ?? 0);
            const isActive = tierFilter === k;
            const color = k === 'ALL' ? 'var(--gold)' : TIER_COLORS[k];
            return (
              <button
                key={k}
                type="button"
                className={`cat-tier-pill ${isActive ? 'is-active' : ''}`}
                style={{ borderColor: color, color: isActive ? '#0a0a0a' : color, background: isActive ? color : 'transparent' }}
                onClick={() => setTierFilter(k)}
                title={k === 'ALL' ? 'All tiers' : TIER_HINTS[k]}
              >
                {k === 'ALL' ? 'All' : TIER_LABELS[k]}
                <span className="cat-tier-pill__n mono">{count}</span>
              </button>
            );
          })}
        </div>
      )}

      {loading && <div className="day-empty">Synthesizing signals across all candidates…</div>}

      {data && filtered.length === 0 && !loading && (
        <div className="day-empty">
          No predictions in this tier right now. {tierFilter === 'ALL' ? 'Markets quiet — try later in session.' : 'Switch to "All" or refresh.'}
        </div>
      )}

      <div className="cat-pred-grid">
        {filtered.map((p) => (
          <PredictionCard key={p.ticker} p={p} onClickTicker={onClickTicker} />
        ))}
      </div>
    </div>
  );
}


function PredictionCard({ p, onClickTicker }: { p: Prediction; onClickTicker: (t: string) => void }) {
  const tierColor = TIER_COLORS[p.conviction_tier];
  const isUp = (p.change_pct ?? 0) > 0;
  const cap = p.market_cap;
  const capStr = cap ? (cap >= 1e9 ? `$${(cap / 1e9).toFixed(1)}B` : `$${(cap / 1e6).toFixed(0)}M`) : '—';

  return (
    <article
      className={`cat-pred-card cat-pred-card--${p.conviction_tier.toLowerCase()}`}
      style={{ borderLeftColor: tierColor }}
    >
      <header className="cat-pred-card__head">
        <div className="cat-pred-card__main">
          <button
            type="button"
            className="cat-pred-card__ticker"
            onClick={() => onClickTicker(p.ticker)}
          >
            {p.ticker}
          </button>
          {p.company_name && <span className="cat-pred-card__name">{p.company_name.slice(0, 40)}</span>}
        </div>
        <div className="cat-pred-card__score">
          <span className="cat-pred-card__tier" style={{ color: tierColor }}>
            {TIER_LABELS[p.conviction_tier]}
          </span>
          <span className="cat-pred-card__num mono" style={{ color: tierColor }}>
            {p.conviction_score >= 0 ? '+' : ''}{p.conviction_score.toFixed(0)}
          </span>
        </div>
      </header>

      <div className="cat-pred-card__stats mono">
        {p.price && <span className="cat-pred-card__price">${p.price.toFixed(2)}</span>}
        {p.change_pct !== undefined && (
          <span className={isUp ? 'pos' : 'neg'}>
            {isUp ? '+' : ''}{(p.change_pct ?? 0).toFixed(2)}%
          </span>
        )}
        <span>{capStr}</span>
        {p.volume_surge_ratio && p.volume_surge_ratio > 1.5 && (
          <span className="cat-pred-card__surge">{p.volume_surge_ratio.toFixed(1)}× vol</span>
        )}
        {p.quadrant && <span className={`cat-tl-quad cat-tl-quad--${p.quadrant.toLowerCase()}`}>{p.quadrant}</span>}
      </div>

      {/* Bull / Bear thesis */}
      {(p.bull_thesis || p.bear_thesis) && (
        <div className="cat-pred-card__theses">
          {p.bull_thesis && <p className="cat-pred-card__bull">{p.bull_thesis}</p>}
          {p.bear_thesis && <p className="cat-pred-card__bear">{p.bear_thesis}</p>}
        </div>
      )}

      {/* Signal stack */}
      {p.signals.length > 0 && (
        <div className="cat-pred-card__signals">
          {p.signals.map((s, i) => (
            <div key={i} className="cat-pred-signal">
              <span className="cat-pred-signal__weight mono">+{s.weight}</span>
              <span className="cat-pred-signal__type">{s.type.replace(/_/g, ' ')}</span>
              <span className="cat-pred-signal__detail">{s.detail}</span>
            </div>
          ))}
        </div>
      )}

      {p.penalties.length > 0 && (
        <div className="cat-pred-card__signals cat-pred-card__signals--neg">
          {p.penalties.map((s, i) => (
            <div key={i} className={`cat-pred-signal cat-pred-signal--neg ${s.hard_veto ? 'cat-pred-signal--veto' : ''}`}>
              <span className="cat-pred-signal__weight mono">{s.weight}</span>
              <span className="cat-pred-signal__type">{s.type.replace(/_/g, ' ')}</span>
              <span className="cat-pred-signal__detail">{s.detail}</span>
            </div>
          ))}
        </div>
      )}

      {p.entry_zone && (
        <div className="cat-pred-card__entry">
          <strong>Entry:</strong> {p.entry_zone}
        </div>
      )}

      {/* Quick external chatter jumps */}
      <ChatterDeepLinks ticker={p.ticker} compact />
    </article>
  );
}


// ====================================================================
// FrenzyRadarView — pre-frenzy detector for tiny stocks
// ====================================================================

const FRENZY_TIER_COLORS: Record<FrenzyTier, string> = {
  IMMINENT: '#ef4444',  // red — already exploding
  SETUP:    '#fb923c',  // orange — best entry zone
  EARLY:    'var(--gold)',
  QUIET:    'var(--ink-muted)',
};

const FRENZY_TIER_LABELS: Record<FrenzyTier, string> = {
  IMMINENT: '🚨 IMMINENT',
  SETUP:    '🎯 SETUP',
  EARLY:    '👀 EARLY',
  QUIET:    '· QUIET',
};

const FRENZY_TIER_HINTS: Record<FrenzyTier, string> = {
  IMMINENT: 'Multiple signals stacked — already in motion. Trim if long, do NOT chase as new entry.',
  SETUP:    'Best risk/reward zone — pre-breakout positioning. Volume + accumulation building.',
  EARLY:    'One signal lit. Add to watchlist; wait for confirmation from a second axis.',
  QUIET:    'No frenzy signal yet — filter out.',
};

const FRENZY_SIGNAL_LABELS: Record<string, string> = {
  quiet_volume_surge:      '🤫 Quiet volume surge',
  chatter_acceleration:    '⚡️ Chatter accelerating',
  cross_platform_chatter:  '🔀 Cross-platform chatter',
  float_in_play:           '🎟️ Float in play',
  multi_day_accum_buildup: '🌱 Multi-day accumulation',
  fresh_appearance:        '🆕 Fresh on list',
  trading_halt_today:      '⏸️ Halted today',
  parabolic_halts:         '🚀 Parabolic halts (LUDP)',
};


function FrenzyRadarView({ onClickTicker }: { onClickTicker: (t: string) => void }) {
  const { data, loading, refetch } = useFrenzyRadar(2 * 60_000);
  const [tierFilter, setTierFilter] = useState<FrenzyTier | 'ALL'>('ALL');

  const filtered = useMemo(() => {
    if (!data) return [];
    if (tierFilter === 'ALL') return data.candidates;
    return data.candidates.filter((c) => c.tier === tierFilter);
  }, [data, tierFilter]);

  return (
    <div className="cat-frenzy">
      <header className="cat-section__head" style={{ marginTop: 12 }}>
        <div>
          <h2 className="cat-section__h">🔥 Frenzy Radar — pre-frenzy detection</h2>
          <p className="cat-section__sub">
            Detects tiny stocks at the inflection point BEFORE the parabolic move.
            Six signals: <strong>quiet volume surges</strong>, <strong>chatter velocity acceleration</strong>,
            cross-platform chatter convergence, float-in-play %, multi-day accumulation buildup,
            and fresh-on-list appearances. Plus NASDAQ halt cross-reference.
            By the time it shows up as +50% with rocket emojis everywhere, you're late —
            this catches it 1-3 hours earlier.
          </p>
        </div>
        <button
          type="button"
          className="lifeboard-btn"
          onClick={refetch}
          disabled={loading}
        >
          {loading ? 'Scanning…' : '↻ Refresh'}
        </button>
      </header>

      {data && (
        <div className="cat-tier-pills">
          {(['ALL', 'IMMINENT', 'SETUP', 'EARLY', 'QUIET'] as const).map((k) => {
            const count = k === 'ALL' ? data.n_total : (data.by_tier[k] ?? 0);
            const isActive = tierFilter === k;
            const color = k === 'ALL' ? 'var(--gold)' : FRENZY_TIER_COLORS[k];
            return (
              <button
                key={k}
                type="button"
                className={`cat-tier-pill ${isActive ? 'is-active' : ''}`}
                style={{ borderColor: color, color: isActive ? '#0a0a0a' : color, background: isActive ? color : 'transparent' }}
                onClick={() => setTierFilter(k)}
                title={k === 'ALL' ? 'All tiers' : FRENZY_TIER_HINTS[k]}
              >
                {k === 'ALL' ? 'All' : FRENZY_TIER_LABELS[k]}
                <span className="cat-tier-pill__n mono">{count}</span>
              </button>
            );
          })}
        </div>
      )}

      {data && (
        <p className="cat-section__sub" style={{ fontSize: 11 }}>
          Snapshot history: {data.snapshots_used} today · {data.lookback_sessions_indexed} sessions indexed for fresh-appearance.
          Computed in {data.elapsed_sec}s.
        </p>
      )}

      {loading && <div className="day-empty">Scanning for pre-frenzy signals…</div>}

      {data && filtered.length === 0 && !loading && (
        <div className="day-empty">
          No {tierFilter !== 'ALL' ? `${tierFilter.toLowerCase()} ` : ''}candidates with frenzy signals right now.
          Markets quiet OR signals haven't formed yet.
        </div>
      )}

      <div className="cat-pred-grid">
        {filtered.map((c) => (
          <FrenzyCard key={c.ticker} c={c} onClickTicker={onClickTicker} />
        ))}
      </div>
    </div>
  );
}


function FrenzyCard({ c, onClickTicker }: { c: FrenzyCandidate; onClickTicker: (t: string) => void }) {
  const tierColor = FRENZY_TIER_COLORS[c.tier];
  const isUp = (c.change_pct ?? 0) > 0;
  const cap = c.market_cap;
  const capStr = cap ? (cap >= 1e9 ? `$${(cap / 1e9).toFixed(1)}B` : `$${(cap / 1e6).toFixed(0)}M`) : '—';

  return (
    <article
      className={`cat-pred-card cat-frenzy-card cat-frenzy-card--${c.tier.toLowerCase()}`}
      style={{ borderLeftColor: tierColor }}
    >
      <header className="cat-pred-card__head">
        <div className="cat-pred-card__main">
          <button
            type="button"
            className="cat-pred-card__ticker"
            onClick={() => onClickTicker(c.ticker)}
          >
            {c.ticker}
          </button>
          {c.company_name && <span className="cat-pred-card__name">{c.company_name.slice(0, 40)}</span>}
        </div>
        <div className="cat-pred-card__score">
          <span className="cat-pred-card__tier" style={{ color: tierColor }}>
            {FRENZY_TIER_LABELS[c.tier]}
          </span>
          <span className="cat-pred-card__num mono" style={{ color: tierColor }}>
            +{c.score.toFixed(0)}
          </span>
        </div>
      </header>

      <div className="cat-pred-card__stats mono">
        {c.price && <span className="cat-pred-card__price">${c.price.toFixed(2)}</span>}
        {c.change_pct !== undefined && (
          <span className={isUp ? 'pos' : 'neg'}>
            {isUp ? '+' : ''}{(c.change_pct ?? 0).toFixed(2)}%
          </span>
        )}
        <span>{capStr}</span>
        {c.volume_surge_ratio && c.volume_surge_ratio > 1.5 && (
          <span className="cat-pred-card__surge">{c.volume_surge_ratio.toFixed(1)}× vol</span>
        )}
        {c.float && (
          <span title="Float">{(c.float / 1e6).toFixed(1)}M float</span>
        )}
      </div>

      {/* Halt info, if any */}
      {c.halts_today && c.halts_today.n_halts > 0 && (
        <div className="cat-frenzy-halt">
          <strong>⏸️ Halted today:</strong> {c.halts_today.n_halts} halt(s) ·
          {' '}reasons: {c.halts_today.reasons.join(', ')}
          {c.halts_today.n_parabolic_halts > 1 && (
            <span className="cat-frenzy-halt__warn"> 🚀 {c.halts_today.n_parabolic_halts} parabolic</span>
          )}
        </div>
      )}

      {/* Signal stack */}
      {c.signals.length > 0 && (
        <div className="cat-pred-card__signals">
          {c.signals.map((s, i) => (
            <div key={i} className="cat-pred-signal">
              <span className="cat-pred-signal__weight mono">+{s.weight}</span>
              <span className="cat-pred-signal__type">
                {FRENZY_SIGNAL_LABELS[s.type] || s.type.replace(/_/g, ' ')}
              </span>
              <span className="cat-pred-signal__detail">{s.detail}</span>
            </div>
          ))}
        </div>
      )}

      <ChatterDeepLinks ticker={c.ticker} compact />
    </article>
  );
}
