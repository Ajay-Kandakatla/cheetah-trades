/* /portfolio — your positions, judged hold-or-sell.
 *
 * Manual-entry holdings + a per-position HOLD / TIGHTEN / TRIM / SELL verdict
 * with the R1/R2/R3 target ladder and the Minervini stop — the same sell-signal
 * logic (backend/sepa/position_lens.py) the SEPA cards use. This page answers
 * "do I keep holding this, or sell?" — not "should I buy" (that's the scanner).
 *
 * Rewritten 2026-06-02 (user): removed the Plaid connect/labels and the CSV
 * upload, deduped the title, and made it a focused manual-holdings + hold/sell
 * page. Holdings come from /portfolio/holdings (manual rows); add via the form,
 * remove via the 🗑. Backend untouched.
 */
import { Suspense, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { InfoButton } from '../components/InfoButton';
import { usePatternVerdicts, patternRank } from '../hooks/usePatternVerdicts';
import { PatternChips } from '../components/PatternChips';
import { BuyVerdictChip } from '../components/BuyVerdictChip';
import { useBuyVerdicts } from '../hooks/useBuyVerdicts';
import { EarningsChip } from '../components/EarningsChip';
import { useEarningsMap } from '../hooks/useEarningsMap';
import { AnalystPulseChip } from '../components/AnalystPulseChip';
import { useAnalystMap } from '../hooks/useAnalystMap';

// Lazy — the analyst drill only loads when a 📊 chip is tapped.
const ChartAnalysisPanel = lazyWithReload(() =>
  import('../components/ChartAnalysisPanel').then((m) => ({ default: m.ChartAnalysisPanel })));
const AnalystPulseModal = lazyWithReload(() =>
  import('../components/AnalystPulseModal').then((m) => ({ default: m.AnalystPulseModal })),
);
import { PatternAccuracyMonthly } from '../components/PatternAccuracyMonthly';
import { AddHoldingForm } from '../components/AddHoldingForm';
import { PositionSignal } from '../components/PositionSignal';
import { HoldingDiagnosis } from '../components/HoldingDiagnosis';
import { BreakoutStats } from '../components/BreakoutStats';
import { MarketPulsePanel } from '../components/MarketPulsePanel';
import { API } from '../lib/apiBase';
import { honestDayPct } from '../lib/portfolioDay';
import { useHoldings, type HoldingRow } from '../hooks/usePortfolio';
import { useLivePortfolio } from '../hooks/useLivePortfolio';
import { Heatmap, type HeatTile } from '../components/Heatmap';
import { PortfolioPostureBanner } from '../components/PortfolioPostureBanner';
import { MarketContextStrip } from '../components/MarketContextStrip';
import { FullScanModal } from '../components/FullScanModal';
import { HoldingsSkeleton } from '../components/Skeletons';
import { TrackedSection } from '../components/TrackedSection';
import { lazyWithReload } from '../lib/lazyWithReload';

const PageInfo = (
  <>
    <p>Your holdings, judged <strong>hold or sell</strong> — not buy.</p>
    <p>
      Each position gets a verdict — <strong>HOLD / TIGHTEN / TRIM / SELL</strong> —
      from the same Minervini sell-signal logic (Ch. 12–13) the scanner uses, plus
      the open <strong>R-multiple</strong>, the recommended <strong>stop</strong>,
      and the <strong>R1 / R2 / R3</strong> target ladder measured from the price
      you paid.
    </p>
    <p>Add positions manually below — ticker, shares, and your average cost.</p>
  </>
);

function money(n: number | null | undefined, signed = false): string {
  if (n == null) return '—';
  const sign = n < 0 ? '-' : signed ? '+' : '';
  return `${sign}$${Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function pct(n: number | null | undefined): string {
  if (n == null) return '—';
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

type HoldSortKey = 'default' | 'value' | 'pl' | 'plpct' | 'day' | 'symbol' | 'pattern';
const HOLD_SORTS: { key: HoldSortKey; label: string; dir: 'asc' | 'desc' }[] = [
  { key: 'value',   label: 'Value',     dir: 'desc' },
  { key: 'pl',      label: 'P&L $',     dir: 'desc' },
  { key: 'plpct',   label: 'P&L %',     dir: 'desc' },
  { key: 'day',     label: 'Day %',     dir: 'desc' },
  { key: 'symbol',  label: 'A–Z',       dir: 'asc' },
  { key: 'pattern', label: '📐 Pattern', dir: 'asc' },
];

export default function PortfolioPage() {
  const navigate = useNavigate();
  const { data, loading, error, refresh, updatedAt } = useHoldings(true);
  const rows: HoldingRow[] = data?.rows ?? [];
  const { verdicts } = usePatternVerdicts();
  // Cheetah Verdict (Minervini SEPA + Bonde) — the same buy read the Analysis
  // tab shows, so each holding carries its buy verdict + criteria (Ajay 2026-06-26).
  const { verdicts: buyVerdicts } = useBuyVerdicts(useMemo(() => rows.map((r) => r.symbol), [rows]));
  const earningsMap = useEarningsMap();   // ⚠ ER chip on each holding row
  // 📊 Analyst Pulse — bulk map for the holdings; one modal instance for
  // the whole page, opened with the clicked symbol.
  const analystMap = useAnalystMap(rows.map((r) => r.symbol));
  const [analystSym, setAnalystSym] = useState<string | null>(null);
  // 🔮 On-demand AI chart analysis per holding (Ajay 2026-06-12, watching
  // ASYS fade min-by-min) — a structured read instead of staring at candles.
  // The panel only calls the model when ITS button is clicked (cached 10 min).
  const [analyzeSym, setAnalyzeSym] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<HoldSortKey>('default');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  // Live SSE quotes (same stream the chart uses) overlaid on the delayed
  // endpoint snapshot — so price / value / P&L / totals tick in real-time like
  // Fidelity, falling back to the snapshot when a symbol has no live tick.
  const live = useLivePortfolio(rows.map((r) => r.symbol));
  const liveView = (r: HoldingRow) => {
    const q = live.get((r.symbol || '').toUpperCase());
    const price = q?.last_price ?? r.current_price;
    const value = price != null ? price * r.quantity : r.current_value;
    const pl = value != null && r.cost_basis != null ? value - r.cost_basis : r.pl_dollars;
    const plPct = value != null && r.cost_basis ? (value / r.cost_basis - 1) * 100 : r.pl_pct;
    return { price, value, pl, plPct, isLive: q?.last_price != null };
  };

  // Honest, real-time "today %" for the Day-% sort + heatmap. A position opened
  // today (today_basis === 'cost') is measured from COST against the live price
  // — NOT the quote's close-to-close, which would count a market drop that
  // happened before you bought (the MUU −24% heatmap bug, Ajay 2026-06-23). A
  // held position (today_basis === 'prior_close') uses the live close-to-close.
  const dayPctFor = (r: HoldingRow): number | null => {
    const q = live.get((r.symbol || '').toUpperCase());
    return honestDayPct({
      today_basis: r.today_basis,
      livePrice: q?.last_price ?? r.current_price,
      quantity: r.quantity,
      costBasis: r.cost_basis,
      liveDayPct: q?.day_pct ?? null,
      backendDayPct: r.day_change_pct,
    });
  };

  const removeHolding = async (sym: string) => {
    if (!sym || !window.confirm(`Remove ${sym} from your positions?`)) return;
    try {
      const res = await fetch(`${API}/portfolio?ticker=${encodeURIComponent(sym)}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (res.ok) await refresh();
    } catch {
      /* leave the row; the user can retry */
    }
  };

  const totalValue = rows.reduce((s, r) => s + (liveView(r).value ?? 0), 0);
  const totalPL = rows.reduce((s, r) => s + (liveView(r).pl ?? 0), 0);

  // Sortable holdings (Ajay 2026-06-09) — live values feed the sort, so P&L /
  // value / day ordering tracks the stream. 'default' keeps insertion order.
  const sortedRows = useMemo(() => {
    if (sortKey === 'default') return rows;
    const val = (r: HoldingRow): number | string | null => {
      const lv = liveView(r);
      switch (sortKey) {
        case 'value':   return lv.value ?? null;
        case 'pl':      return lv.pl ?? null;
        case 'plpct':   return lv.plPct ?? null;
        case 'day':     return dayPctFor(r);
        case 'symbol':  return r.symbol || '';
        case 'pattern': return patternRank(verdicts.get((r.symbol || '').toUpperCase()));
        default:        return null;
      }
    };
    return [...rows].sort((a, b) => {
      const av = val(a), bv = val(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;                        // nulls last
      if (bv == null) return -1;
      const cmp = typeof av === 'string'
        ? av.localeCompare(String(bv))
        : (av as number) - (bv as number);
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [rows, sortKey, sortDir, live, verdicts]);

  const clickSort = (s: { key: HoldSortKey; dir: 'asc' | 'desc' }) => {
    if (s.key === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(s.key); setSortDir(s.dir); }
  };

  // Heatmap tiles — sized by live position value. Colour mode (Ajay
  // 2026-06-11: "I want this head chart to show my loss or profit, not the
  // current market"): default = YOUR P&L vs cost; 'day' = today's market
  // move. Persisted so the choice sticks.
  const [heatMode, setHeatMode] = useState<'pnl' | 'day'>(() => {
    try { return localStorage.getItem('portfolio_heat_mode') === 'day' ? 'day' : 'pnl'; }
    catch { return 'pnl'; }
  });
  const setHeat = (m: 'pnl' | 'day') => {
    setHeatMode(m);
    try { localStorage.setItem('portfolio_heat_mode', m); } catch { /* ignore */ }
  };
  const heatTiles: HeatTile[] = rows.map((r) => {
    const lv = liveView(r);
    const pct = heatMode === 'pnl'
      ? (lv.plPct ?? null)
      : dayPctFor(r);
    return {
      symbol: r.symbol,
      value: Math.max(0, lv.value ?? r.current_value ?? 0),
      pct,
      label: pct != null ? `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%` : undefined,
    };
  });

  return (
    <div className="sepa-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">Hold or sell</div>
          <h1
            className="display sepa-page__h1"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
          >
            Portfolio
            <InfoButton inline title="Portfolio">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">
            Your positions, judged <strong>hold or sell</strong> — each with a verdict,
            R-targets and a Minervini stop measured from your cost. Add what you own below.
          </p>
        </div>
        <FullScanModal />
      </div>

      <PortfolioPostureBanner />

      {rows.length > 0 && (
        <div className="portfolio-totals mono">
          <span>{rows.length} position{rows.length === 1 ? '' : 's'}</span>
          <span>· value {money(totalValue)}</span>
          <span style={{ color: totalPL >= 0 ? '#10b981' : '#ef4444' }}>
            · open P&amp;L {money(totalPL, true)}
          </span>
          <span className="rank-lb__live" title={updatedAt ? `updated ${new Date(updatedAt).toLocaleTimeString()}` : 'live'}>
            {' · '}<span className="dot">●</span> live
          </span>
        </div>
      )}

      {loading && rows.length === 0 && <HoldingsSkeleton rows={4} />}
      {error && (
        <p className="mono" style={{ color: '#f87171', marginTop: '0.8rem' }}>
          Couldn't load holdings — {error}
        </p>
      )}
      {!loading && !error && rows.length === 0 && (
        <div className="sepa-empty-card" style={{ marginTop: '0.8rem' }}>
          <div className="eyebrow">No positions yet</div>
          <p style={{ color: '#9aa8c8' }}>
            Add a stock above — ticker, shares, and the price you paid — and you'll get a
            hold/sell read with the R-target ladder.
          </p>
        </div>
      )}

      {rows.length > 1 && (
        <div className="heatmap-panel">
          <MarketContextStrip />
          <div className="heatmap-panel__head">
            <span className="heatmap-panel__title">📊 {heatMode === 'pnl' ? 'My P&L heatmap' : 'Day heatmap'}</span>
            <span className="heatmap-panel__hint">
              size = position value · colour = {heatMode === 'pnl' ? 'YOUR gain/loss vs cost' : 'today’s move'} · click to open
            </span>
            <span style={{ display: 'inline-flex', gap: 4 }}>
              {(['pnl', 'day'] as const).map((m) => (
                <button key={m} type="button" onClick={() => setHeat(m)} className="mono"
                        style={{ fontSize: '0.7rem', padding: '3px 10px', borderRadius: 6, cursor: 'pointer', minHeight: 26,
                                 background: heatMode === m ? 'var(--gold,#c9a227)' : 'transparent',
                                 color: heatMode === m ? '#1a1a1a' : 'inherit',
                                 border: `1px solid ${heatMode === m ? 'var(--gold,#c9a227)' : 'var(--hairline,#2a2a2a)'}` }}>
                  {m === 'pnl' ? 'My P&L' : 'Day %'}
                </button>
              ))}
            </span>
            <a className="heatmap-panel__finviz" href="https://finviz.com/map?t=sec&st=d1" target="_blank" rel="noreferrer" title="Open the full S&P 500 sector map on Finviz">Full market map ↗</a>
          </div>
          <Heatmap
            tiles={heatTiles}
            height={170}
            onTileClick={(s) => navigate(`/sepa/${encodeURIComponent(s)}`, { state: { from: '/portfolio', label: 'Portfolio' } })}
          />
        </div>
      )}

      {rows.length > 1 && (
        <div className="rank-lb__sortbar mono" style={{ marginTop: '0.6rem' }}>
          <span className="rank-lb__sortlabel">sort:</span>
          {HOLD_SORTS.map((s) => {
            const on = s.key === sortKey;
            return (
              <button key={s.key} className={`rank-lb__sortchip${on ? ' is-on' : ''}`} onClick={() => clickSort(s)}>
                {s.label}{on ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
              </button>
            );
          })}
        </div>
      )}

      <div className="portfolio-list">
        {sortedRows.map((r) => {
          // PER-SHARE average cost — `avg_cost` is per share; `cost_basis` is the
          // TOTAL dollars invested, so derive per-share from it as a fallback.
          const entry =
            r.avg_cost ??
            r.entry ??
            (r.cost_basis != null && r.quantity ? r.cost_basis / r.quantity : null);
          const lv = liveView(r);
          return (
            <div key={`${r.symbol}-${r.account_id || ''}`} className="portfolio-card">
              <div className="portfolio-card__top">
                <div className="portfolio-card__id">
                  <button
                    className="portfolio-card__sym"
                    onClick={() =>
                      navigate(`/sepa/${encodeURIComponent(r.symbol)}`, {
                        state: { from: '/portfolio', label: 'Portfolio' },
                      })
                    }
                    title="Open full SEPA analysis"
                  >
                    {r.symbol || '—'}
                  </button>
                  {r.name && (
                    <span className="portfolio-card__name">
                      {r.name.length > 40 ? r.name.slice(0, 40) + '…' : r.name}
                    </span>
                  )}
                  <PatternChips v={verdicts.get((r.symbol || '').toUpperCase())} />
                  {(() => {
                    const bv = buyVerdicts.get((r.symbol || '').toUpperCase());
                    return bv ? <BuyVerdictChip row={{ buy_verdict: bv, is_etf: bv.is_etf }} compact /> : null;
                  })()}
                  <EarningsChip symbol={r.symbol} info={earningsMap.get((r.symbol || '').toUpperCase())} />
                  <AnalystPulseChip
                    symbol={r.symbol}
                    entry={analystMap.get((r.symbol || '').toUpperCase())}
                    onOpenDrill={() => setAnalystSym(r.symbol)}
                  />
                </div>
                <button
                  type="button"
                  className="portfolio-card__rm"
                  title="AI chart analysis — on-demand buyable/hold read"
                  aria-label={`Analyze ${r.symbol} chart`}
                  style={{ marginRight: 2 }}
                  onClick={() => setAnalyzeSym(r.symbol)}
                >
                  🔮
                </button>
                <button
                  type="button"
                  className="portfolio-card__rm"
                  title="Remove this position"
                  onClick={() => removeHolding(r.symbol)}
                >
                  🗑
                </button>
              </div>

              <div className="portfolio-card__nums mono">
                <span>{r.quantity.toLocaleString(undefined, { maximumFractionDigits: 4 })} sh</span>
                <span>cost {money(entry)}</span>
                <span>
                  now {money(lv.price)}
                  {lv.isLive && <span className="port-live-dot" title="streaming live">●</span>}
                </span>
                <span style={{ color: (lv.pl ?? 0) >= 0 ? '#10b981' : '#ef4444' }}>
                  {money(lv.pl, true)} ({pct(lv.plPct)})
                </span>
              </div>

              <PositionSignal symbol={r.symbol} entry={entry} shares={r.quantity} stop={r.stop} />
              {/* Breakout count + actual volume (Ajay 2026-06-13) — self-fetches
                  per holding since a held name isn't always in the latest scan. */}
              <div style={{ marginTop: '0.4rem' }}>
                <BreakoutStats symbol={r.symbol} />
              </div>
              {/* Collapsed by default (2026-06-13) — open, it auto-fired a Claude
                  call per holding on mount (N essays walling the sell decision,
                  each duplicating the PositionSignal verdict above). The
                  "Why is it moving?" toggle inside opens it on demand. */}
              <HoldingDiagnosis symbol={r.symbol} />
            </div>
          );
        })}
      </div>

      {analystSym && (
        <Suspense fallback={null}>
          <AnalystPulseModal symbol={analystSym} onClose={() => setAnalystSym(null)} />
        </Suspense>
      )}

      {analyzeSym && (
        <div onClick={() => setAnalyzeSym(null)}
             style={{ position: 'fixed', inset: 0, zIndex: 1100, background: 'rgba(0,0,0,0.6)',
                      display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
                      padding: '4rem 1rem 1rem', overflowY: 'auto' }}>
          <div onClick={(e) => e.stopPropagation()}
               style={{ width: 'min(680px, 100%)', background: 'var(--bg-raised,#16181d)',
                        border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 12,
                        padding: '0.4rem 0.9rem 0.9rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.5rem 0 0' }}>
              <strong style={{ fontSize: '0.92rem' }}>🔮 {analyzeSym}</strong>
              <button onClick={() => setAnalyzeSym(null)} aria-label="Close"
                      style={{ marginLeft: 'auto', background: 'transparent', border: 'none',
                               color: '#8a93a6', cursor: 'pointer', fontSize: '1rem' }}>✕</button>
            </div>
            <Suspense fallback={<p style={{ color: '#8a93a6', fontSize: '0.78rem' }}>loading…</p>}>
              <ChartAnalysisPanel symbol={analyzeSym} />
            </Suspense>
          </div>
        </div>
      )}

      {/* Sections wrapped in TrackedSection (Ajay 2026-06-16) — record
          `section:portfolio:*` on scroll-into-view to enable a later
          usage-driven reorder. Layout-neutral. */}
      <TrackedSection name="portfolio:add_form"><AddHoldingForm onAdded={refresh} /></TrackedSection>

      {/* Buy-discovery widgets removed from Portfolio (2026-06-13 declutter):
          PatternMatchCards, EarningsReportPicks, RacingBoard, SepaRankLeaderboard,
          SepaRankCompare and SepaTopPicks are market-wide and now live ONLY on
          /leaderboard — Portfolio is the hold/sell surface, not a second discovery
          page. (They were cross-posted here over 06-04..06-12; consolidated now.) */}

      {/* Month-by-month winners' record for the paper-trading review (Ajay
          2026-06-10) — perpetual, never pruned. */}
      <TrackedSection name="portfolio:pattern_accuracy"><PatternAccuracyMonthly /></TrackedSection>

      {/* Overall market context — secondary to the per-stock reads above. */}
      <TrackedSection name="portfolio:market_pulse"><MarketPulsePanel holdings={rows} /></TrackedSection>
    </div>
  );
}
