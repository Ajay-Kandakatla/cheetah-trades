import { useMemo, useState } from 'react';
import { TickerLink } from '../components/TickerLink';
import { MarketGaugeBanner } from '../components/MarketGaugeBanner';
import { DependencyGraph } from '../components/DependencyGraph';
import { NodeThesisPanel } from '../components/NodeThesisPanel';
import { MoneyFlowLeaderboard } from '../components/MoneyFlowLeaderboard';
import { StockSupplyDemandPanel } from '../components/StockSupplyDemandPanel';
import { DemandReentryPanel } from '../components/DemandReentryPanel';
import { TradeFlashStrip } from '../components/TradeFlashStrip';
import { useSupplyDemandGraph, useSectors, useMarketFlow, useEquityPremium } from '../hooks/useSupplyDemand';
import type { SectorPayload, FlowTicker, EquityTag } from '../hooks/useSupplyDemand';
import { useSepaScan } from '../hooks/useSepa';

type Tab = 'stocks' | 'reentry' | 'graph' | 'sectors' | 'equity';

/* Mega-cap tickers — when "highlight tradeable names only" mode is on,
   these get their SEPA gold ring stripped even if they're on the list.
   Reason: the user trades small/mid-caps; mega-caps clutter the focus.
   Threshold ≈ $500B mcap as of typical 2026 levels.
   Edit this list when companies cross the threshold. */
const MEGACAP_EXCLUDE = new Set([
  'NVDA', 'MSFT', 'AAPL', 'GOOGL', 'GOOG', 'AMZN', 'META', 'TSLA',
  'BRK.A', 'BRK.B', 'BRK-A', 'BRK-B',
  'LLY', 'AVGO', 'WMT', 'JPM', 'V', 'MA',
  'TSM',          // foreign ADR but $700B+
  'UNH', 'XOM', 'ORCL',
]);

export function SupplyDemandPage() {
  // Back in Demand is the landing tab (Ajay 2026-08-14) — it is the only
  // surface here with an actionable, R:R-sorted list, so it leads.
  const [tab, setTab] = useState<Tab>('reentry');
  const [enrichNews, setEnrichNews] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [showFlow, setShowFlow] = useState(true);
  // SEPA highlight scope — default to "tradeable only" (excludes mega-caps).
  // Click the toggle in the help row to flip and include the big stocks.
  const [tradeableOnly, setTradeableOnly] = useState(true);
  const { data: graphData, loading: graphLoading } = useSupplyDemandGraph(enrichNews);
  const { data: sectorsData, loading: sectorsLoading, refreshing: sectorsRefreshing, forceRefresh: refreshSectors } = useSectors();
  const { data: flowData } = useMarketFlow(30_000);
  // SEPA candidate list — drives the gold-ring emphasis on graph nodes.
  // Updates dynamically: when SEPA scan finishes, the graph re-tags + re-sizes.
  const { data: sepaData } = useSepaScan();

  const flowMap = useMemo(() => {
    if (!flowData) return undefined;
    const m: Record<string, FlowTicker> = {};
    for (const t of flowData.tickers) m[t.ticker] = t;
    return m;
  }, [flowData]);

  /* Build a Set of tickers on the SEPA list + a tier map for sizing.
     Only positive-tier names (STRONG_BUY/BUY/WATCH) get the gold ring.
     When tradeableOnly is true (the default), mega-caps are excluded —
     the user trades small/mid-caps, not NVDA/MSFT. */
  const { sepaTickers, sepaTiers, megacapsHidden } = useMemo(() => {
    const set = new Set<string>();
    const tiers: Record<string, 'STRONG_BUY' | 'BUY' | 'WATCH'> = {};
    const positive = new Set(['STRONG_BUY', 'BUY', 'WATCH']);
    let hiddenCount = 0;
    for (const c of sepaData?.candidates ?? []) {
      const r = c.rating;
      if (!r || !positive.has(r)) continue;
      const sym = c.symbol;
      if (tradeableOnly && MEGACAP_EXCLUDE.has(sym)) {
        hiddenCount++;
        continue;
      }
      set.add(sym);
      tiers[sym] = r as 'STRONG_BUY' | 'BUY' | 'WATCH';
    }
    return { sepaTickers: set, sepaTiers: tiers, megacapsHidden: hiddenCount };
  }, [sepaData, tradeableOnly]);

  return (
    <div className="cm-page sd-page">
      <MarketGaugeBanner />

      <header className="cm-pagehead">
        <div className="cm-pagehead__col">
          <div className="eyebrow">Supply & Demand</div>
          <h1 className="display cm-pagehead__title">S&P Supply Chain Atlas</h1>
          <p className="lede">
            Curated dependency graph of who depends on whom — NVIDIA's chips
            come from TSMC, TSMC's lithography comes from ASML, Microsoft buys
            NVIDIA's GPUs to power Azure AI. Plus a daily-refreshed sector
            view classifying global supply vs. demand state for 15 industries
            the S&P leans on. Click any company to drill in.
          </p>
        </div>
      </header>

      {/* Tab switcher */}
      <div className="sd-tabs">
        <button type="button" className={`sd-tab ${tab === 'reentry' ? 'is-active' : ''}`}
                onClick={() => setTab('reentry')}>
          🟢 Back in Demand
        </button>
        <button type="button" className={`sd-tab ${tab === 'stocks' ? 'is-active' : ''}`}
                onClick={() => setTab('stocks')}>
          📊 Stocks (Supply / Demand)
        </button>
        <button type="button" className={`sd-tab ${tab === 'graph' ? 'is-active' : ''}`}
                onClick={() => setTab('graph')}>
          Dependency Graph
        </button>
        <button type="button" className={`sd-tab ${tab === 'sectors' ? 'is-active' : ''}`}
                onClick={() => setTab('sectors')}>
          Sector Supply / Demand
        </button>
        <button type="button" className={`sd-tab ${tab === 'equity' ? 'is-active' : ''}`}
                onClick={() => setTab('equity')}>
          💎 External Equity
        </button>
      </div>

      {tab === 'stocks' && <StockSupplyDemandPanel />}

      {tab === 'reentry' && (
        <>
          <TradeFlashStrip />
          <DemandReentryPanel />
        </>
      )}

      {tab === 'equity' && <EquityPremiumPanel onClickTicker={(t) => setSelectedTicker(t)} />}

      {/* Graph tab */}
      {tab === 'graph' && (
        <section className="sd-section">
          <div className="sd-section__head">
            <div>
              <h2 className="day-section__h">Company dependency graph</h2>
              <p className="sd-meta">
                {graphData ? `${graphData.n_nodes} companies · ${graphData.n_edges} relationships` : 'Loading…'}
                {' · '}
                <label className="sd-toggle-inline">
                  <input type="checkbox" checked={enrichNews}
                         onChange={(e) => setEnrichNews(e.target.checked)} />
                  attach recent news to each edge
                </label>
                {' · '}
                <label className="sd-toggle-inline">
                  <input type="checkbox" checked={showFlow}
                         onChange={(e) => setShowFlow(e.target.checked)} />
                  show live money flow
                </label>
                {flowData && (
                  <span className={`sd-market-pill sd-market-pill--${flowData.market.state}`}
                        title={`Last updated: ${new Date(flowData.as_of).toLocaleString()}`}>
                    {flowData.market.state === 'open'    && '🟢 LIVE DATA'}
                    {flowData.market.state === 'pre'     && '🌅 PRE-MKT'}
                    {flowData.market.state === 'after'   && '🟠 AFTER-HRS · stale'}
                    {flowData.market.state === 'closed'  && '⚪️ CLOSED · stale'}
                    {flowData.market.state === 'weekend' && '⚪️ WEEKEND · stale'}
                  </span>
                )}
                {flowData && flowData.cached && flowData.cache_age_sec > 30 && (
                  <span className="sd-cache-pill" title="Data age vs last fetch">
                    {flowData.cache_age_sec < 60 ? `${flowData.cache_age_sec}s` : `${Math.round(flowData.cache_age_sec / 60)}m`} ago
                  </span>
                )}
              </p>
            </div>
          </div>

          {/* Accumulation / Distribution + flow legend */}
          {showFlow && flowData && (
            <div className="sd-flow-legend">
              <span className="sd-flow-legend__group">
                <span className="sd-flow-swatch sd-flow-swatch--accum" />
                <strong className="sd-flow-legend__label">Accumulation</strong>
                <span className="sd-flow-legend__count mono">
                  {flowData.totals.n_strong_accumulation ?? 0} strong · {flowData.totals.n_accumulating ?? 0} total
                </span>
              </span>
              <span className="sd-flow-legend__group">
                <span className="sd-flow-swatch sd-flow-swatch--dist" />
                <strong className="sd-flow-legend__label">Distribution</strong>
                <span className="sd-flow-legend__count mono">
                  {flowData.totals.n_strong_distribution ?? 0} strong · {flowData.totals.n_distributing ?? 0} total
                </span>
              </span>
              <span className="sd-flow-legend__hint">
                rings emit ripples · steady = ≥10 days CMF · pulse = today's $ vol
              </span>
            </div>
          )}

          {/* Money flow leaderboard — inflow / outflow strip */}
          {showFlow && flowData && (
            <MoneyFlowLeaderboard flow={flowData} onTickerClick={(t) => setSelectedTicker(t)} />
          )}

          {graphLoading && <div className="day-empty">Loading graph…</div>}
          {graphData && (
            <DependencyGraph
              nodes={graphData.nodes}
              edges={graphData.edges}
              height={820}
              onNodeClick={(t) => setSelectedTicker(t)}
              selectedTicker={selectedTicker}
              flowMap={showFlow ? flowMap : undefined}
              flowLive={showFlow && (flowData?.market?.is_live ?? false)}
              sepaTickers={sepaTickers}
              sepaTiers={sepaTiers}
            />
          )}
          {(sepaTickers.size > 0 || megacapsHidden > 0) && (
            <div className="sd-graph-help mono" style={{ fontSize: '0.78rem',
                  display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'baseline' }}>
              <span>
                <span style={{ color: 'var(--gold-strong)' }}>★</span>{' '}
                <strong>{sepaTickers.size}</strong> SEPA{' '}
                {tradeableOnly ? 'tradeable' : ''} name(s) gold-ringed.
                STRONG_BUY = largest + glow · BUY · WATCH = smallest.
              </span>
              {megacapsHidden > 0 && tradeableOnly && (
                <span style={{ color: 'var(--ink-faint)' }}>
                  · {megacapsHidden} mega-cap(s) on SEPA list — not highlighted
                  (NVDA/MSFT-class, outside your trading range)
                </span>
              )}
              <button
                type="button"
                onClick={() => setTradeableOnly(!tradeableOnly)}
                style={{
                  marginLeft: 'auto',
                  padding: '3px 9px',
                  fontSize: '0.72rem',
                  background: 'transparent',
                  border: '1px solid var(--hairline)',
                  color: 'var(--ink-muted)',
                  borderRadius: 3,
                  cursor: 'pointer',
                }}
                title={tradeableOnly
                  ? 'Currently hiding mega-cap SEPA names. Click to show all.'
                  : 'Currently showing all SEPA names including mega-caps. Click to hide them.'}
              >
                {tradeableOnly ? '✓ Tradeable only' : '○ Tradeable only'}
              </button>
            </div>
          )}

          <div className="sd-graph-help">
            <strong>How to read this:</strong> Each circle is a public S&P company,
            colored by sector — same-color bubbles cluster into sector regions.
            Arrows show direction of dependency — e.g.{' '}
            <code>NVDA →foundry_for→ TSM</code> means NVDA's chips are
            manufactured at TSMC. Edge thickness encodes strength (1.0 =
            sole-source).{' '}
            <strong>Money flow:</strong> green/red rings around nodes show
            today's % move (pulse intensity = $ volume). Particles flow{' '}
            <em>source → target</em> along edges — green if the chain is
            healthy (both up), red if both down, amber if divergent. Faster
            particles = more dollar volume on the source name.{' '}
            <strong>Click any node</strong> for thesis + 13F holdings.
            <strong> Drag</strong> nodes to reposition.
          </div>
        </section>
      )}

      {/* Sectors tab */}
      {tab === 'sectors' && (
        <section className="sd-section">
          <div className="sd-section__head">
            <div>
              <h2 className="day-section__h">Sector supply / demand state</h2>
              <p className="sd-meta">
                {sectorsData
                  ? `${sectorsData.n_sectors} sectors · ${sectorsData.n_cached} from ${sectorsData.cache_ttl_hours}h cache · refreshed ${new Date(sectorsData.as_of).toLocaleTimeString()}`
                  : 'Loading…'}
              </p>
            </div>
            <button type="button" className="lifeboard-btn"
                    onClick={refreshSectors} disabled={sectorsRefreshing}>
              {sectorsRefreshing ? 'Refreshing…' : '↻ Force refresh'}
            </button>
          </div>

          {sectorsLoading && !sectorsData && <div className="day-empty">Classifying 15 sectors with Gemma…</div>}
          {sectorsData && (
            <div className="sd-sector-grid">
              {sectorsData.sectors.map((s) => <SectorCard key={s.sector_id} sector={s} />)}
            </div>
          )}
        </section>
      )}

      <footer className="cm-disclaimer cm-disclaimer--footer">
        <span className="cm-disclaimer__label">Data sources</span>
        <p>
          Dependencies are hand-curated from 10-K filings, press releases, and
          earnings calls — each edge cites its source. Sector classification
          combines yfinance ETF/commodity prices + Massive news headlines +
          local Gemma analysis (cached 6h). 13F institutional holdings via
          yfinance/Yahoo Finance, sourced from SEC Form 13F-HR filings (45-day
          lag, cached 24h).
        </p>
      </footer>

      {/* Node thesis side drawer */}
      <NodeThesisPanel ticker={selectedTicker} onClose={() => setSelectedTicker(null)} />
    </div>
  );
}

function SectorCard({ sector }: { sector: SectorPayload }) {
  const c = sector.classification;
  const moodClass =
    c.state === 'constrained' ? 'sd-card--constrained' :
    c.state === 'oversupplied' ? 'sd-card--oversupplied' : 'sd-card--balanced';

  const trendIcon =
    c.trend_direction === 'tightening' ? '↑' :
    c.trend_direction === 'loosening'  ? '↓' : '→';

  const etfChange = sector.etf?.change_30d_pct;
  const etfMood = etfChange != null ? (etfChange > 0 ? 'pos' : etfChange < 0 ? 'neg' : '') : '';

  return (
    <div className={`sd-card ${moodClass}`}>
      <header className="sd-card__head">
        <h3 className="sd-card__title">{sector.label}</h3>
        <span className={`sd-card__state sd-card__state--${c.state}`}>
          {trendIcon} {c.state.toUpperCase()}
        </span>
      </header>

      <div className="sd-card__gap-row">
        <div className="sd-card__gap-bar">
          <div
            className="sd-card__gap-fill"
            style={{
              width: `${c.gap_index}%`,
              background: c.gap_index >= 70 ? 'var(--positive)' : c.gap_index >= 40 ? 'var(--gold)' : 'var(--negative)',
            }}
          />
        </div>
        <span className="sd-card__gap-num mono">{c.gap_index}/100</span>
      </div>

      <p className="sd-card__narrative">{c.narrative}</p>

      <div className="sd-card__metrics mono">
        {sector.etf && (
          <span className={`sd-card__metric ${etfMood}`}>
            {sector.etf.ticker} {etfChange != null && etfChange > 0 ? '+' : ''}{etfChange}% (30d)
          </span>
        )}
        {sector.commodity && (
          <span className="sd-card__metric">
            {sector.commodity.ticker} {sector.commodity.change_30d_pct != null && sector.commodity.change_30d_pct > 0 ? '+' : ''}{sector.commodity.change_30d_pct}% (30d)
          </span>
        )}
        <span className="sd-card__conf">conf {c.confidence}%</span>
        {c._method && <span className="sd-card__method">via {c._method}</span>}
      </div>

      {sector.thesis_static && (
        <div className="sd-card__thesis">
          <span className="sd-card__thesis-label">Thesis:</span> {sector.thesis_static}
        </div>
      )}

      {sector.gap_economics && <GapEconomicsBlock g={sector.gap_economics} />}

      {sector.sp_tickers.length > 0 && (
        <div className="sd-card__tickers">
          {sector.sp_tickers.map((t) => (
            <TickerLink
              key={t}
              ticker={t}
              fromLabel="Supply / Demand"
              className="sd-card__ticker"
              title={`open ${t} (Cmd/Ctrl-click for new tab)`}
            >
              {t}
            </TickerLink>
          ))}
        </div>
      )}

      {sector.headlines.length > 0 && (
        <details className="sd-card__news">
          <summary>{sector.headlines.length} headlines</summary>
          <ul>
            {sector.headlines.slice(0, 5).map((h, i) => (
              <li key={i}>
                {h.url ? (
                  <a href={h.url} target="_blank" rel="noreferrer">{h.title} ↗</a>
                ) : <span>{h.title}</span>}
                {h.publisher && <span className="sd-card__news-pub"> — {h.publisher}</span>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}


/**
 * GapEconomicsBlock — visualises the dollar-denominated supply/demand gap
 * for a single sector. Shows demand vs supply as a side-by-side bar with
 * the shortfall (or oversupply) called out in dollars, plus the capex
 * required to close the gap and the time it takes.
 */
function GapEconomicsBlock({ g }: { g: import('../hooks/useSupplyDemand').GapEconomics }) {
  const demand = g.demand_usd_bn;
  const supply = g.supply_usd_bn;
  const gap = demand - supply;                 // + = shortfall; − = oversupply
  const isShortfall = gap > 0;
  const isOversupply = gap < 0;

  // Bar widths normalised to the larger of demand / supply
  const maxBar = Math.max(demand, supply, 1);
  const demandPct = (demand / maxBar) * 100;
  const supplyPct = (supply / maxBar) * 100;

  const fmt$ = (n: number) =>
    n >= 1000 ? `$${(n / 1000).toFixed(1)}T`
    : n >= 1   ? `$${n.toFixed(0)}B`
    : `$${(n * 1000).toFixed(0)}M`;

  const capex = g.capex_to_close_usd_bn;

  return (
    <div className={`sd-gap ${isShortfall ? 'sd-gap--short' : isOversupply ? 'sd-gap--over' : 'sd-gap--balanced'}`}>
      <div className="sd-gap__h">
        <span className="sd-gap__h-label">$ Gap analysis</span>
        <span className="sd-gap__h-headline mono">
          {isShortfall && <>shortfall <strong>{fmt$(gap)}/yr</strong></>}
          {isOversupply && <>oversupply <strong>{fmt$(Math.abs(gap))}/yr</strong></>}
          {!isShortfall && !isOversupply && <>balanced</>}
        </span>
      </div>

      {/* Two stacked bars: Demand (full) and Supply (partial) */}
      <div className="sd-gap__bars">
        <div className="sd-gap__row">
          <span className="sd-gap__row-label">Demand</span>
          <div className="sd-gap__track">
            <div className="sd-gap__fill sd-gap__fill--demand" style={{ width: `${demandPct}%` }} />
          </div>
          <span className="sd-gap__row-num mono">{fmt$(demand)}</span>
        </div>
        <div className="sd-gap__row">
          <span className="sd-gap__row-label">Supply</span>
          <div className="sd-gap__track">
            <div className="sd-gap__fill sd-gap__fill--supply" style={{ width: `${supplyPct}%` }} />
            {/* If shortfall, render a dashed segment showing the missing chunk */}
            {isShortfall && (
              <div
                className="sd-gap__fill sd-gap__fill--gap"
                style={{
                  left: `${supplyPct}%`,
                  width: `${demandPct - supplyPct}%`,
                }}
              />
            )}
          </div>
          <span className="sd-gap__row-num mono">{fmt$(supply)}</span>
        </div>
      </div>

      {/* Capex + time-to-close + binding constraint */}
      <div className="sd-gap__meta">
        {capex !== undefined && capex !== null && capex !== 0 && (
          <div className="sd-gap__meta-row">
            <span className="sd-gap__meta-label">Capex to close:</span>
            <span className="mono">
              {capex > 0 ? `${fmt$(capex)} new investment` : `${fmt$(Math.abs(capex))} idle / over-investment`}
            </span>
            {g.years_to_close && (
              <span className="sd-gap__meta-time"> · over {g.years_to_close} yrs</span>
            )}
          </div>
        )}
        {g.key_constraint && (
          <div className="sd-gap__meta-row">
            <span className="sd-gap__meta-label">Bottleneck:</span>
            <span>{g.key_constraint}</span>
          </div>
        )}
        {g.notes && (
          <details className="sd-gap__notes">
            <summary>more · {g.as_of}</summary>
            <p>{g.notes}</p>
            {g.sources && g.sources.length > 0 && (
              <p className="sd-gap__sources">
                <em>sources: {g.sources.join(' · ')}</em>
              </p>
            )}
          </details>
        )}
      </div>
    </div>
  );
}


/**
 * EquityPremiumPanel — sortable table of names whose value is largely
 * external shareholders' equity rather than operating fundamentals.
 *
 * The signature signal is `equity_share_pct` = book equity / mcap.
 * When it's high (>50%), the market cap is mostly tangible equity that
 * was issued and accumulated — not earnings retained from operations.
 * MSTR is the canonical example.
 */
function EquityPremiumPanel({ onClickTicker }: { onClickTicker: (t: string) => void }) {
  const { data, loading, refreshing, forceRefresh } = useEquityPremium() as
    ReturnType<typeof useEquityPremium> & { refreshing?: boolean };
  const [tagFilter, setTagFilter] = useState<EquityTag | 'ALL'>('ALL');

  const TAG_LABELS: Record<EquityTag, string> = {
    TREASURY:       '🪙 Treasury',
    EQUITY_HEAVY:   '💎 Equity-heavy',
    NARRATIVE:      '📖 Narrative',
    GROWTH_PREMIUM: '🚀 Growth premium',
    NORMAL:         '⚙️ Normal',
  };
  const TAG_COLORS: Record<EquityTag, string> = {
    TREASURY:       '#fbbf24',
    EQUITY_HEAVY:   '#22c55e',
    NARRATIVE:      '#a855f7',
    GROWTH_PREMIUM: '#06b6d4',
    NORMAL:         'var(--ink-muted)',
  };

  const rows = useMemo(() => {
    if (!data) return [];
    if (tagFilter === 'ALL') return data.rows;
    return data.rows.filter((r) => r.tag === tagFilter);
  }, [data, tagFilter]);

  const fmt$ = (n?: number | null) => {
    if (n == null) return '—';
    if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
    if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
    return `$${n.toFixed(0)}`;
  };
  const fmt = (n?: number | null, d = 1, suffix = '') => n == null ? '—' : `${n.toFixed(d)}${suffix}`;

  return (
    <section className="sd-section">
      <div className="sd-section__head">
        <div>
          <h2 className="day-section__h">External-equity-driven names</h2>
          <p className="sd-meta">
            {data ? `${data.n_total} companies · ` : 'Loading… '}
            book-equity / market-cap = how much of the value is{' '}
            <strong>external shareholders' equity</strong> vs operating premium.
            High = treasury / value play; low = pure narrative / growth multiple.
          </p>
        </div>
        <button type="button" className="lifeboard-btn" onClick={forceRefresh} disabled={loading || refreshing}>
          {loading || refreshing ? 'Refreshing…' : '↻ Force refresh'}
        </button>
      </div>

      {/* Tag filter chips */}
      {data && (
        <div className="ep-tags">
          {(['ALL', 'TREASURY', 'EQUITY_HEAVY', 'NARRATIVE', 'GROWTH_PREMIUM', 'NORMAL'] as const).map((k) => {
            const isActive = tagFilter === k;
            const count = k === 'ALL' ? data.n_total : (data.by_tag[k] ?? 0);
            return (
              <button
                key={k}
                type="button"
                className={`ep-tag ${isActive ? 'is-active' : ''}`}
                onClick={() => setTagFilter(k)}
              >
                {k === 'ALL' ? 'All' : TAG_LABELS[k]}
                <span className="ep-tag__n mono">{count}</span>
              </button>
            );
          })}
        </div>
      )}

      {loading && <div className="day-empty">Pulling balance sheets + market caps for 56 names…</div>}

      {data && rows.length > 0 && (
        <div className="ep-table-wrap">
          <table className="ep-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Tag</th>
                <th className="ep-th-num">Equity / Cap</th>
                <th className="ep-th-num">Mcap</th>
                <th className="ep-th-num">Book equity</th>
                <th className="ep-th-num">Cash %</th>
                <th className="ep-th-num">P/B</th>
                <th className="ep-th-num">P/S</th>
                <th className="ep-th-num">Δ shares YoY</th>
                <th>Why</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const eqPct = r.equity_share_pct;
                const intensity = eqPct == null ? 0 : Math.min(100, Math.max(0, eqPct)) / 100;
                return (
                  <tr key={r.ticker}>
                    <td>
                      <button
                        type="button"
                        className="ep-ticker"
                        onClick={() => onClickTicker(r.ticker)}
                        title={r.name ?? r.ticker}
                      >
                        {r.ticker}
                      </button>
                      {r.name && <div className="ep-name">{r.name.slice(0, 40)}</div>}
                    </td>
                    <td>
                      <span className="ep-tag-pill mono" style={{ color: TAG_COLORS[r.tag], borderColor: TAG_COLORS[r.tag] }}>
                        {TAG_LABELS[r.tag]}
                      </span>
                    </td>
                    <td className="mono ep-num">
                      {eqPct == null ? '—' : (
                        <div className="ep-bar-cell">
                          <span>{eqPct.toFixed(0)}%</span>
                          <div className="ep-bar">
                            <div
                              className="ep-bar__fill"
                              style={{
                                width: `${Math.min(100, Math.max(0, eqPct))}%`,
                                background: `color-mix(in srgb, ${TAG_COLORS[r.tag]} ${50 + intensity * 50}%, transparent)`,
                              }}
                            />
                          </div>
                        </div>
                      )}
                    </td>
                    <td className="mono ep-num">{fmt$(r.market_cap)}</td>
                    <td className="mono ep-num">{fmt$(r.book_value_total)}</td>
                    <td className="mono ep-num">{fmt(r.cash_pct_of_mcap, 1, '%')}</td>
                    <td className="mono ep-num">{fmt(r.pb_ratio, 1)}</td>
                    <td className="mono ep-num">{fmt(r.ps_ratio, 1)}</td>
                    <td className={`mono ep-num ${(r.shares_growth_yoy_pct ?? 0) > 5 ? 'ep-warn' : ''}`}>
                      {fmt(r.shares_growth_yoy_pct, 1, '%')}
                    </td>
                    <td className="ep-rationale">{r.rationale}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="ep-disclaimer">
            <strong>How to read:</strong> "Equity / Cap" is the fraction of market cap backed by tangible
            shareholders' equity (book value). 80%+ = MSTR-style — value is mostly an equity-pile, not earnings.
            10-30% = typical operating company. Sub-10% = pure premium (growth or narrative trade).
            Δ shares YoY {'>'} 8% means heavy stock issuance — the company is funding itself with new
            equity rather than retained earnings.
          </p>
        </div>
      )}
    </section>
  );
}
