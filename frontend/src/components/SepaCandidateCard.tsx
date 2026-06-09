import { lazy, Suspense, useState, useEffect, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
// Lazy — modal payload + per-ticker fetch only when the user clicks.
// Keeps the list-view bundle slim since most users won't tap every
// whale chip on every visit.
import type { SepaCandidate } from '../hooks/useSepa';
import type { SoirRow } from '../hooks/useOptionsPulse';
import type { WhalesFlowRow } from '../hooks/useWhalesFlow';
import type { Whales13DRow } from '../hooks/useWhales13DFlow';
import { SepaScoreBar } from './SepaScoreBar';
import { SepaTrendDots } from './SepaTrendDots';
import { PriceAlertModal } from './PriceAlertModal';
import { WatchlistButton } from './WatchlistButton';
import { useQuote } from '../hooks/useWatchlist';
import { useOwnedPosition } from '../hooks/useOwnedPositions';
import { TradePlanInline } from './TradePlanInline';
import { StopsPanel } from './StopsPanel';
import { EntryExitPlanBlock } from './EntryExitPlanBlock';
import { PivotMeter } from './PivotMeter';
import { pivotTiming } from '../lib/pivotTiming';
// Shared chip strip — renders the volume-driven signals (strong/accumulating/
// distributing, pocket pivot, hi-vol breakout, money outflow, dist days) with
// drill-in click behavior. Lives here and on the /sepa/{symbol} detail page so
// both surfaces stay in sync. Pass subset="volume_only" so it skips the chips
// that the card already renders via dedicated UI (score bar / trend dots /
// RS bar / setup pill / stage badge).
import { SepaSignalChips } from './SepaSignalChips';
// JIT-fetched cluster insider + valuation chips. Lazy via
// IntersectionObserver so the SEPA list with 100+ cards doesn't burst
// EDGAR / yfinance on first paint — cards fetch only when scrolled into
// view, backend caches 24h.
import { CardEnrichmentChips } from './CardEnrichmentChips';
import { SoirModal } from './SoirModal';
// Real-time tape (accumulation/distribution) + short-interest squeeze chips.
// Lazy via IntersectionObserver; accumulation polls while the card is visible.
import { RealtimeChips } from './RealtimeChips';
// Compact "why buy" thesis + ranking-drivers footer. Built from row data
// — volume-first per Ajay's request 2026-05-28 ("Volume is my main
// indicator"). The ranking note explains BB-style intraday rank slips
// (steady Minervini score + live day-move tie-breaker).
import { SepaWhyBuy } from './SepaWhyBuy';
// Composite "Whales + Volume" conviction chip — user's actual buy/sell
// decision signal. Combines 13F institutional flow with volume tape
// into one pill. Disagreement (whales ≠ volume) flagged as a warning.
import { SepaConvictionChip, computeConviction } from './SepaConvictionChip';
// Political-disclosure chips — surfaces POTUS-family disclosed positions
// and U.S. govt investment/contractor relationships. Informational only;
// curated list in src/lib/politicalDisclosures.ts.
import { SepaPoliticalChip } from './SepaPoliticalChip';
import { getPoliticalChipFlags } from '../lib/politicalDisclosures';
import { isMomentumLeader, MOMENTUM_LEADER_TOOLTIP } from '../lib/momentumLeader';
// Δ score + Δ rank trend chips — pure FE, reads SepaTrendContext for
// the historical maps. Added 2026-05-28 in response to user request to
// track when "points drop" and maintain a separate ranking trend.
import { SepaTrendChips } from './SepaTrendChips';
import { useSepaTrend } from './SepaTrendContext';

// Lazy — the moat-peers modal pulls a real API call and isn't needed
// until the user actually taps the chip, so don't bloat the card chunk.
const MoatPeersModal = lazy(() =>
  import('./MoatPeersModal').then(m => ({ default: m.MoatPeersModal })),
);
const ProductLaunchesChip = lazy(() =>
  import('./ProductLaunchesChip').then(m => ({ default: m.ProductLaunchesChip })),
);
const TickerAlertPresets = lazy(() =>
  import('./TickerAlertPresets').then(m => ({ default: m.TickerAlertPresets })),
);
const WhalesFlowModal = lazy(() =>
  import('./WhalesFlowModal').then(m => ({ default: m.WhalesFlowModal })),
);
const Whales13DModal = lazy(() =>
  import('./Whales13DModal').then(m => ({ default: m.Whales13DModal })),
);
const MacroContextModal = lazy(() =>
  import('./MacroContextModal').then(m => ({ default: m.MacroContextModal })),
);
// Drill-in for clickable signal chips (hi-vol breakout, pocket pivot,
// accumulation strength, money outflow, distribution-day warning).
// Lazy because the spec map is ~400 lines and only loads when the
// user actually taps a chip.
const SignalDrillModal = lazy(() =>
  import('./SignalDrillModal').then(m => ({ default: m.SignalDrillModal })),
);
import type { SignalKind } from './SignalDrillModal';
import type { LivePrice } from '../hooks/useLivePrices';
import { getMarketSession, pickDisplayPrice } from '../lib/marketSession';
import { SessionBadge } from './SessionBadge';

type Props = {
  row: SepaCandidate;
  /** Latest SOIR (Schaeffer's Open Interest Ratio) snapshot for this ticker.
   *  Optional — when present, the card shows put/call open interest + signal. */
  soir?: SoirRow;
  /** Institutional flow signal from cached 13F / whales data. Optional —
   *  chip only renders when present (i.e. ticker has been opened before
   *  in the supply/demand panel). */
  whalesFlow?: WhalesFlowRow;
  /** Recent SC 13D/G filing summary from cached SEC EDGAR data. Optional —
   *  chip only renders when present (i.e. fund has crossed 5% ownership
   *  in the lookback window). */
  whales13d?: Whales13DRow;
  /** Real-time bulk snapshot price from /sepa/live-prices (polled every 2 min
   *  during market hours). When present, overlays the card with a LIVE badge
   *  and uses live change_pct for the day-change display. */
  livePrice?: LivePrice;
  /** Optional banner rendered immediately above the card content. Used by
   *  the /sepa setup-category tabs (Phase 2) to overlay the precomputed
   *  trigger / stop / target / R:R for the active setup kind. Pass
   *  undefined (default) to preserve the existing card chrome unchanged. */
  setupOverlay?: ReactNode;
  onSelect: (e?: React.MouseEvent) => void;
};

/**
 * SepaCandidateCard — replaces the dense table row with a glance-readable card.
 * Shows: rating + score, trend dots, RS, setup pill, pivot/stop with risk %,
 * stage badge, volume/late-base flags.
 */
export function SepaCandidateCard({ row, soir, whalesFlow, whales13d, livePrice, setupOverlay, onSelect }: Props) {
  const [alertOpen, setAlertOpen] = useState(false);
  const [presetOpen, setPresetOpen] = useState(false);
  const [moatOpen,  setMoatOpen]  = useState(false);
  // Drill-in for the institutional-flow chip — full top-10 buyers
  // and top-10 sellers fetched on demand.
  const [whalesOpen, setWhalesOpen] = useState(false);
  // Drill-in for the SEC 13D/G filings chip — list of recent
  // ownership-threshold filings fetched on demand.
  const [whales13dOpen, setWhales13dOpen] = useState(false);
  // Drill-in for the macro chip — Claude-generated geopolitics +
  // futures + bear case + sector context, plus a few live headlines.
  const [macroOpen, setMacroOpen] = useState(false);
  const [soirOpen, setSoirOpen] = useState(false);
  // Lean glance-card (CX condensation 2026-06-09): the wall of secondary signal
  // chips (volume signals, JIT insider/valuation, realtime accum/dist, ADR,
  // whales 13F, SEC activity, macro, moat, pioneer themes) collapses behind a
  // one-tap toggle so the card leads with price → decision → setup. All of these
  // also live on the ticker detail page, so nothing is lost — the scan list just
  // stops being a wall of chips. Default off = lean. Bonus: the realtime/JIT
  // chips' polling + EDGAR fetches only fire when the user expands a card.
  const [showSignals, setShowSignals] = useState(false);
  const setup = row.entry_setup;
  const riskPct = setup ? Math.abs((setup.pivot - setup.stop) / setup.pivot) * 100 : null;
  const stage = row.stage?.stage;
  const lateBase = row.base_count?.is_late_stage;
  // accStrength stays as a local because signalData below feeds it to
  // the SignalDrillModal for cards where the user taps an accum chip.
  // (The other v2 volume locals — pocketPivot / cmfSignal / distDays /
  // breakout / accumulation — were inlined as chip render-conditions and
  // moved to <SepaSignalChips subset="volume_only"> on 2026-05-22.)
  const accStrength  = row.volume?.accumulation_strength;

  // One state slot for whatever signal-drill modal is open (or null).
  // Used instead of a boolean per chip because at most one is open at
  // a time. Click handlers set this; the modal at the bottom of the
  // card reads it.
  const [openSignal, setOpenSignal] = useState<SignalKind | null>(null);

  // Trend context — provides historical rank/score maps. Used by both
  // the trend chips and (when the trend drill modal opens) the modal
  // itself to render the trajectory chart.
  const trend = useSepaTrend(row.symbol);
  const owned = useOwnedPosition(row.symbol);   // your position, if you hold this name
  // Lazy fetch of per-symbol history snapshots — only triggered when
  // the trend drill modal actually opens. Avoids 200 cards × 1 fetch
  // each on page load. The hook fires its own fetch on mount; we mount
  // it conditionally below.
  const [trendHistoryRows, setTrendHistoryRows] = useState<Array<{ date_et: string; generated_at: number; score: number | null; rank: number | null; stage_label?: string | null }>>([]);
  useEffect(() => {
    if (openSignal !== 'rank_trend_history') return;
    let alive = true;
    fetch(`${(import.meta as any).env?.VITE_API_BASE || '/api'}/sepa/history/${row.symbol}?days=30`)
      .then(r => (r.ok ? r.json() : { snapshots: [] }))
      .then(j => {
        if (!alive) return;
        const snaps = (j.snapshots || []) as Array<{ date_et: string; generated_at: number; score: number | null; stage_label?: string | null }>;
        // Rank is computed by the trend context's rank-derivation logic
        // (sort by score within each date). Since per-symbol history
        // doesn't have other tickers' scores, we can only fill rank
        // for the two anchor dates (yesterday + week-ago) for which we
        // have full-leaderboard data in the context. Other dates get
        // rank: null and the chart just shows score for those.
        const ranked = snaps.map(s => ({
          ...s,
          rank: s.date_et === trend.yesterdayDate
            ? (trend.yesterday?.rank ?? null)
            : s.date_et === trend.weekAgoDate
              ? (trend.weekAgo?.rank ?? null)
              : null,
        }));
        setTrendHistoryRows(ranked);
      });
    return () => { alive = false; };
  }, [openSignal, row.symbol, trend.yesterdayDate, trend.weekAgoDate, trend.yesterday, trend.weekAgo]);
  // Snapshot of all data the modal might read — built once per render
  // from the candidate row. Includes both volume signals AND score
  // components so any chip can open into a meaningful drill view.
  const signalData = {
    symbol:                row.symbol,
    // Volume-signal fields
    last_vol:              (row.volume as any)?.last_vol ?? null,
    avg_vol_50:            (row.volume as any)?.avg_vol_50 ?? null,
    up_down_vol_ratio:     row.volume?.up_down_vol_ratio ?? null,
    last_close:            row.last_close ?? null,
    recent_21d_high:       (row.volume as any)?.recent_21d_high ?? null,
    accumulation_strength: accStrength ?? null,
    pocket_pivot_detail:   (row.volume as any)?.pocket_pivot_detail ?? null,
    cmf_20:                (row.volume as any)?.cmf_20 ?? null,
    distribution_days_25:  row.volume?.distribution_days_25 ?? null,
    accumulation_days_25:  row.volume?.accumulation_days_25 ?? null,
    // Score-component fields (added 2026-05-22 for ranking transparency)
    score:                 row.score ?? null,
    rating:                row.rating ?? null,
    trend_passed:          row.trend?.passed ?? null,
    trend_checks:          (row.trend as any)?.checks ?? null,
    rs_rank:               row.rs_rank ?? null,
    stage_num:             (row.stage as any)?.stage ?? null,
    stage_label:           (row.stage as any)?.label ?? null,
    fundamentals_passed:   (row.fundamentals as any)?.passed ?? null,
    adr_pct:               row.adr_pct ?? null,
    base_count_n:          (row.base_count as any)?.base_count ?? null,
    base_count_is_late:    lateBase ?? null,
    setup_type:            setup?.type ?? null,
    setup_pivot:           setup?.pivot ?? null,
    setup_stop:            setup?.stop ?? null,
    liquidity_liquid:      (row as any)?.liquidity?.liquid ?? null,
    avg_dollar_vol:        (row as any)?.liquidity?.avg_dollar_vol ?? null,
    high_vol_breakout:     row.volume?.high_vol_breakout ?? null,
    pocket_pivot:          row.volume?.pocket_pivot ?? null,
    cmf_signal:            row.volume?.cmf_signal ?? null,
    // Dollar flows — added 2026-05-29. Surfaces in the cmf_inflow /
    // cmf_outflow / accum_strong / accumulating / distributing drill
    // modals so users see actual $ amounts instead of just ratios.
    // Null-safe — older cached scans won't have these.
    up_dollar_vol_50:      (row.volume as any)?.up_dollar_vol_50 ?? null,
    dn_dollar_vol_50:      (row.volume as any)?.dn_dollar_vol_50 ?? null,
    net_dollar_vol_50:     (row.volume as any)?.net_dollar_vol_50 ?? null,
    cmf_dollar_flow_20:    (row.volume as any)?.cmf_dollar_flow_20 ?? null,
    // Dual momentum (Antonacci) — feeds the dual_momentum_12m drill modal
    // when the user clicks the "12m" chip. All four returns + the two
    // gate booleans live on row.dual_momentum if the scan included them.
    return_1m:             (row.dual_momentum as any)?.return_1m ?? null,
    return_3m:             (row.dual_momentum as any)?.return_3m ?? null,
    return_6m:             (row.dual_momentum as any)?.return_6m ?? null,
    return_12m:            (row.dual_momentum as any)?.return_12m ?? null,
    abs_mom_pass:          (row.dual_momentum as any)?.abs_mom_pass ?? null,
    beats_spy:             (row.dual_momentum as any)?.beats_spy ?? null,
    // Stage-classifier volume-disagreement reason — surfaced when the
    // ⚠️ Stage 3 badge is clicked. Backend embeds the full distributing /
    // CMF outflow / book citation reason as a string in row.stage.volume_reason.
    stage_volume_reason:   (row.stage as any)?.volume_reason ?? null,
    // Per-symbol trend trajectory — populated lazily when the user
    // clicks the trend chip. Empty array until the modal opens; the
    // chart degrades gracefully on empty input.
    trend_history:         trendHistoryRows,
    trend_yesterday_date:  trend.yesterdayDate,
    trend_week_ago_date:   trend.weekAgoDate,
    // Conviction inputs — pre-computed once per render so the chip
    // tooltip + drill modal show identical numbers. Cheap (few lookups
    // on row fields) so safe to recompute on every render.
    ...(() => {
      const c = computeConviction(row, whalesFlow);
      return {
        conviction_tier:          c.tier,
        conviction_label:         c.label,
        conviction_combined:      c.combined,
        conviction_whale_score:   c.whaleScore,
        conviction_vol_score:     c.volScore,
        conviction_whale_reason:  c.whaleReason,
        conviction_vol_reason:    c.volReason,
        conviction_summary:       c.summary,
        conviction_disagrees:     c.disagrees,
      };
    })(),
    // Political-disclosure context — empty fields when the ticker
    // isn't on the curated list. The drill modal degrades gracefully
    // on null entries (only opens when user clicked a rendered chip).
    ...(() => {
      const pol = getPoliticalChipFlags(row.symbol);
      if (!pol.entry) return {};
      return {
        political_categories:  pol.entry.categories,
        political_band:        pol.entry.disclosureBand ?? null,
        political_company:     pol.entry.company,
        political_sector:      pol.entry.sector,
        political_notes:       pol.entry.notes ?? null,
        political_is_inferred: pol.isInferred && !pol.hasPotusFamily && !pol.hasGovtInvestment && !pol.hasGovtContractor,
      };
    })(),
  };

  // Live intraday quote (Massive lastTrade-backed via /quote/{ticker}).
  // SEPA's `last_close` is by-design the most recent COMPLETED daily bar
  // (Minervini's templates run on EOD closes), but during regular hours
  // that's stale by today's intraday move. We show both: close stays as
  // the SEPA-honest source-of-truth, live as a "what's actually happening
  // right now" overlay so the user isn't blindsided.
  const liveQuote = useQuote(row.symbol);
  const showLive =
    liveQuote && liveQuote.ok &&
    liveQuote.last_price != null &&
    row.last_close != null &&
    Math.abs(liveQuote.last_price - row.last_close) / row.last_close > 0.001;
  const liveDeltaPct = showLive
    ? ((liveQuote!.last_price! - row.last_close!) / row.last_close!) * 100
    : null;

  // Day-change tint — color the whole card so down-days pop visually.
  // -2% threshold for "strong down" matches the chip color thresholds.
  const dayClass = (() => {
    const d = row.day_change_pct;
    if (d == null) return '';
    if (d <= -2) return 'sepa-card--day-down-strong';
    if (d < 0)   return 'sepa-card--day-down';
    if (d >= 2)  return 'sepa-card--day-up-strong';
    if (d > 0)   return 'sepa-card--day-up';
    return '';
  })();

  // When the parent passes a setup overlay (Phase 2 SEPA tabs), wrap the
  // article so the overlay sits flush against the top of the card. The
  // wrapper is display: contents-equivalent — purely structural — when
  // there's no overlay, so existing layout behavior is preserved.
  const cardBody = (
    <article
      className={`sepa-card ${row.is_candidate ? 'is-candidate' : ''} ${dayClass}`}
      onClick={(e) => onSelect(e)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.currentTarget !== e.target) return;
        if (e.key === 'Enter' || e.key === ' ') onSelect();
      }}
      title="Cmd/Ctrl-click to open in new tab"
    >
      <header className="sepa-card__head">
        <div className="sepa-card__sym">
          <div className="sepa-card__sym-line">
            {/* Real anchor so right-click → "Open in new tab", middle-click and
                Cmd/Ctrl-click all work natively. Plain click is intercepted and
                routed through the card's onSelect (which saves the list scroll
                position), so in-place drill-in behaviour is unchanged. */}
            <Link
              to={`/sepa/${encodeURIComponent(row.symbol)}`}
              className="sepa-card__sym-link"
              onClick={(e) => {
                e.stopPropagation();           // never double-fire the card onClick
                if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; // browser opens new tab
                e.preventDefault();            // suppress default; do controlled in-place nav
                onSelect();
              }}
            >
              <strong>{row.symbol}</strong>
            </Link>
            <WatchlistButton ticker={row.symbol} />
            {owned && (
              <span className="sepa-owned"
                    style={{ color: (owned.pl_pct ?? 0) >= 0 ? '#10b981' : '#ef4444' }}
                    title={`You own ${owned.quantity ?? '?'} sh${owned.avg_cost ? ` · cost $${owned.avg_cost.toFixed(2)}` : ''}${owned.current_value ? ` · value $${Math.round(owned.current_value).toLocaleString()}` : ''}`}
                    onClick={(e) => e.stopPropagation()}>
                📍 Owned{owned.pl_pct != null ? ` ${owned.pl_pct >= 0 ? '+' : ''}${owned.pl_pct.toFixed(1)}%` : ''}
              </span>
            )}
            {stage != null && (
              <span
                role="button" tabIndex={0}
                className={`sepa-stage sepa-stage--${stage}`}
                title="Tap for Weinstein stage analysis + score contribution"
                onClick={(e) => { e.stopPropagation(); setOpenSignal('stage'); }}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') {
                  e.stopPropagation(); e.preventDefault(); setOpenSignal('stage');
                }}}
                style={{ cursor: 'pointer' }}
              >
                S{stage}
                <span className="sepa-stage__label">
                  {' · '}
                  {stage === 1 ? 'Basing' :
                   stage === 2 ? 'Advancing' :
                   stage === 3 ? 'Topping' :
                   stage === 4 ? 'Declining' :
                   '—'}
                </span>
              </span>
            )}
            {/* Stage 2 → Stage 3 volume-disagreement badge — surfaced when
                stage.classify() downgraded a name because MA geometry said
                Stage 2 but accumulation/CMF tape said distributing/outflow.
                This is the ANTX case: perfect MA stack but real money is
                stepping out. Click for the book p.71-72 vs p.74-76
                framework + the specific accumulation / CMF values that
                triggered the downgrade. Added 2026-05-28 alongside the
                stage.py volume-confirmation fix. */}
            {(row.stage as any)?.volume_disagreement && (
              <span
                role="button" tabIndex={0}
                className="sepa-tag sepa-tag--warn"
                title="MA geometry says Stage 2 advancing, but volume tape says distributing / outflow. Tap for the book p.71-72 vs p.74-76 explanation."
                onClick={(e) => { e.stopPropagation(); setOpenSignal('stage_vol_disagreement'); }}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') {
                  e.stopPropagation(); e.preventDefault(); setOpenSignal('stage_vol_disagreement');
                }}}
                style={{ cursor: 'pointer' }}
              >
                ⚠️ vol disagrees
              </span>
            )}
            {/* Δ score (7d) + Δ rank (vs yesterday) chips. Pure FE,
                reads SepaTrendContext built once per page by Sepa.tsx.
                Click opens the rank_trend_history drill modal with the
                full 30-day trajectory chart + framework + pitfalls. */}
            <SepaTrendChips
              symbol={row.symbol}
              onOpenDrill={(kind) => setOpenSignal(kind)}
            />
            {/* Whales + Volume combined conviction chip — Ajay's actual
                buy decision signal per 2026-05-28 ("I am trying to
                determine which one to pick based on whales and the
                volume"). Strong tier (both bullish, agree) gets bigger
                + bolder; warning tier (signals disagree) gets red so
                it pops loudest — the "don't buy yet" case. */}
            <SepaConvictionChip
              row={row}
              whalesFlow={whalesFlow}
              onOpenDrill={() => setOpenSignal('conviction')}
            />
            {/* Political-disclosure chips — POTUS Family / Govt
                Investment / Inferred. Renders 0-2 chips depending on
                what categories the ticker matches; nothing when ticker
                isn't on the curated list. Informational only — caveat
                shown in tooltip + drill. */}
            <SepaPoliticalChip
              symbol={row.symbol}
              onOpenDrill={() => setOpenSignal('political_disclosure')}
            />
            {lateBase && (
              <span
                role="button" tabIndex={0}
                className="sepa-tag sepa-tag--warn"
                title="Tap for late-base framework + -8 penalty rationale"
                onClick={(e) => { e.stopPropagation(); setOpenSignal('base_count_late'); }}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') {
                  e.stopPropagation(); e.preventDefault(); setOpenSignal('base_count_late');
                }}}
                style={{ cursor: 'pointer' }}
              >
                late · base #{row.base_count?.base_count ?? '?'}
              </span>
            )}
            {row.is_etf && (
              <span
                className="sepa-tag sepa-tag--etf"
                title={
                  `Exchange-Traded Fund (ETF) — basket of underlying stocks. ` +
                  `CANSLIM Earnings Per Share (EPS) / fundamentals don't apply; ` +
                  `relevant metrics are Assets Under Management (AUM), expense ` +
                  `ratio, dividend yield, and holdings.` +
                  (row.etf_data?.category ? `\nCategory: ${row.etf_data.category}` : '') +
                  (row.etf_data?.fund_family ? `\nIssuer: ${row.etf_data.fund_family}` : '')
                }
              >ETF</span>
            )}
          </div>
          {row.name && <div className="sepa-card__name" title={row.name}>{row.name}</div>}
          {row.last_close != null && (
            <div className="sepa-card__price mono"
                 title="Last completed daily close — SEPA scoring runs on EOD bars, not intraday">
              <span className="sepa-card__price-num">${row.last_close.toFixed(2)}</span>
              {row.day_change_pct != null && (
                <span className={`sepa-card__price-day ${row.day_change_pct >= 0 ? 'is-up' : 'is-down'}`}>
                  {row.day_change_pct >= 0 ? '▲' : '▼'} {Math.abs(row.day_change_pct).toFixed(2)}%
                </span>
              )}
              <span className="sepa-card__price-tag mono">close</span>
            </div>
          )}
          {/* Live overlay — only renders when intraday last differs from
              the scan-time close. Uses /quote/{symbol} (Massive lastTrade
              with 60s server cache + 60s client memo). */}
          {showLive && (
            <div className={`sepa-card__price sepa-card__price--live mono ${liveDeltaPct! >= 0 ? 'is-up' : 'is-down'}`}
                 title={
                   liveQuote?._extended
                     ? `Overnight / extended-hours print (${liveQuote._ext_type ?? 'extended'}) via StockTwits. Includes Blue Ocean ATS overnight session.`
                     : `Intraday last trade as of ${liveQuote?.as_of ?? '—'}. Differs from close by ${liveDeltaPct!.toFixed(2)}% — SEPA pillars still use the close.`
                 }>
              <span className="sepa-card__price-num">${liveQuote!.last_price!.toFixed(2)}</span>
              <span className={`sepa-card__price-day ${liveDeltaPct! >= 0 ? 'is-up' : 'is-down'}`}>
                {liveDeltaPct! >= 0 ? '▲' : '▼'} {Math.abs(liveDeltaPct!).toFixed(2)}%
              </span>
              <span className="sepa-card__price-tag sepa-card__price-tag--live mono">
                {liveQuote?._extended ? '🌙 overnight' : 'live'}
              </span>
            </div>
          )}
          {/* Bulk snapshot overlay — from /sepa/live-prices, polled with a
              session-aware cadence. Shows the price for the current session
              (pre-market lastTrade, live close, after-hours lastTrade, or
              regular close when closed) with a four-state SessionBadge.
              Rendered only when the per-card useQuote didn't already cover
              it (avoids double-showing). */}
          {(() => {
            if (showLive) return null;
            const session = getMarketSession();
            const display = pickDisplayPrice(livePrice, session);
            if (!display) return null;
            return (
              <div
                className={`sepa-card__price sepa-card__price--live mono ${
                  (display.change_pct ?? 0) >= 0 ? 'is-up' : 'is-down'
                }`}
                title={
                  session === 'live'
                    ? 'Real-time regular-session price from Massive bulk snapshot. SEPA scoring still uses the official daily close.'
                    : session === 'pre'
                      ? 'Pre-market trade (4:00am–9:30am ET). Change is vs the previous regular close. SEPA scoring runs on regular-session closes only.'
                      : session === 'after'
                        ? 'After-hours trade (4:00pm–8:00pm ET). Change is vs the previous regular close. SEPA scoring runs on regular-session closes only.'
                        : 'Market closed — showing the last completed regular-session close.'
                }
              >
                <span className="sepa-card__price-num">${display.price.toFixed(2)}</span>
                {display.change_pct != null && (
                  <span className={`sepa-card__price-day ${display.change_pct >= 0 ? 'is-up' : 'is-down'}`}>
                    {display.change_pct >= 0 ? '▲' : '▼'} {Math.abs(display.change_pct).toFixed(2)}%
                  </span>
                )}
                <span className="sepa-card__price-tag sepa-card__price-tag--live mono"
                      style={{ display: 'inline-flex', alignItems: 'center' }}>
                  <SessionBadge session={session} />
                </span>
              </div>
            );
          })()}
        </div>
        <div className="sepa-card__head-right">
          <div className="sepa-card__head-right-top">
            <button
              type="button"
              className="sepa-card__bell"
              title="Quick alerts — tap a preset (-5%, -10%, +20%, etc.) instead of typing a number"
              onClick={(e) => { e.stopPropagation(); setPresetOpen(true); }}
            >
              🔔
            </button>
            {/* Score bar wrapped in a clickable button so the user can
                tap the score to see the breakdown of which components
                contributed. Same role+tabIndex pattern as the volume chips. */}
            <span
              role="button" tabIndex={0}
              title="Tap to see score breakdown — which components contributed how much"
              onClick={(e) => { e.stopPropagation(); setOpenSignal('score_breakdown'); }}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') {
                e.stopPropagation(); e.preventDefault(); setOpenSignal('score_breakdown');
              }}}
              style={{ cursor: 'pointer', display: 'inline-block' }}
            >
              <SepaScoreBar score={row.score} rating={row.rating} size="sm" />
            </span>
          </div>
          {/* Entry + Stops menu — replaces the old BUY/STOP/+1R/EXIT box
              (user 2026-05-30). Shows the buy point + every stop method
              (Structure / Minervini / ATR) tightest→widest so you pick your
              line in the sand. Falls back to the old inline plan only when
              the entry/exit stops haven't been computed for this card. */}
          {row.entry_exit?.exit?.stops?.length ? (
            <StopsPanel exit={row.entry_exit.exit} />
          ) : row.trade_plan ? (
            <TradePlanInline plan={row.trade_plan} lastClose={row.last_close} />
          ) : null}
        </div>
      </header>

      {/* Timed entry/exit decision + dated timeline — "what do I do THIS
          week." Full-width row UNDER the header (not in the score column)
          so the banner doesn't collide with the price / CLOSE button.
          Synthesis of trade_plan + stage + volume + ADX. Source:
          backend/sepa/entry_exit.py. */}
      {/* Pivot entry-timing meter — the visual "am I hopping on at the right
          time?" gauge (Minervini pp.197-205): price vs pivot + buy-zone and the
          volume dried→expanding state. GO only when price ≥ pivot AND volume
          expands. Shown for names with a setup (VCP / Power Play). */}
      {(() => {
        const t = pivotTiming(row);
        return t.hasSetup ? (
          <div style={{ padding: '0 0.2rem' }}>
            <PivotMeter t={t} />
          </div>
        ) : null;
      })()}

      {row.entry_exit && (
        <div style={{ padding: '0 0.2rem' }}>
          <EntryExitPlanBlock plan={row.entry_exit} />
        </div>
      )}

      {/* Sales Confidence (Bonde/Stockbee) — revenue growth + acceleration. */}
      {(() => {
        const s = row.fundamentals?.sales;
        if (!s || s.score == null) return null;
        const tone =
          s.tier === 'explosive' ? '#10b981' : s.tier === 'strong' ? '#34d399' :
          s.tier === 'steady' ? '#eab308' : s.tier === 'weak' ? '#94a3b8' : '#f87171';
        return (
          <div style={{ padding: '0.35rem 0.2rem 0' }}>
            <span
              className="sepa-chip"
              title={`Sales Confidence ${s.score}/100 (${s.tier}). Revenue ${s.growth_yoy_pct}% YoY${s.accelerating ? ', accelerating ⚡' : ''}${s.consecutive_growth_q ? `, ${s.consecutive_growth_q}q growth` : ''}${s.sales_led ? ', sales-led' : ''}. Pradeep Bonde / Stockbee: 5% floor · 25% preferred · 100% explosive.`}
              style={{ color: tone, borderColor: tone, cursor: 'help', fontSize: '0.72rem' }}
            >
              📈 Sales {s.score} · {s.growth_yoy_pct != null ? `${s.growth_yoy_pct > 0 ? '+' : ''}${s.growth_yoy_pct}% YoY` : '—'}
              {s.accelerating ? ' ⚡' : ''}{s.sales_led ? ' · led' : ''}
            </span>
          </div>
        );
      })()}

      {/* Earnings Quality (Minervini Ch.8, book p.140-159) — Code 33 / margins /
          red flags. Folds into the score; chip surfaces the verdict at a glance. */}
      {(() => {
        const e = (row.fundamentals as any)?.earnings_quality;
        if (!e || e.score == null) return null;
        const c = e.components || {};
        const tone =
          e.tier === 'code33' ? '#10b981' : e.tier === 'accelerating' ? '#34d399' :
          e.tier === 'steady' ? '#eab308' : e.tier === 'red_flag' ? '#f87171' : '#94a3b8';
        const pct = (v: number | null | undefined) =>
          v != null ? `${v > 0 ? '+' : ''}${v}%` : '—';
        const label =
          e.tier === 'code33' ? '🎯 Code 33' :
          e.tier === 'red_flag' ? `⚠️ EQ ${e.score}` : `💎 EQ ${e.score}`;
        const title =
          `Earnings Quality ${e.score}/100 — ${e.reason}. ` +
          `EPS ${pct(c.eps_growth_yoy_pct)} YoY${c.eps_accelerating ? ' ⚡' : ''}, ` +
          `Sales ${pct(c.rev_growth_yoy_pct)} YoY${c.rev_accelerating ? ' ⚡' : ''}, ` +
          `Net margin ${pct(c.npm_latest_pct)}${c.npm_expanding ? ' expanding ↑' : ''}. ` +
          `Minervini, Trade Like a Stock Market Wizard, Ch.8 (Assessing Earnings Quality, p.140-159).`;
        return (
          <div style={{ padding: '0.35rem 0.2rem 0' }}>
            <span
              className="sepa-chip"
              title={title}
              style={{ color: tone, borderColor: tone, cursor: 'help', fontSize: '0.72rem' }}
            >
              {label}{e.code_33 && e.tier !== 'code33' ? ' 🎯' : ''}
            </span>
          </div>
        );
      })()}

      {/* Industry-group leadership (Minervini Ch.6, p.102/108) — additive,
          DISPLAY-only. Chip only for the actionable ends: group LEADER or
          LAGGARD; mid-pack names show nothing. See group_leadership.py. */}
      {(() => {
        const ind = row.industry;
        if (!ind || (!row.group_leader && !row.is_laggard)) return null;
        const shortInd = ind.length > 22 ? ind.slice(0, 21) + '…' : ind;
        const rankTxt = row.group_rs_rank && row.group_size
          ? `#${row.group_rs_rank}/${row.group_size}` : '';
        const cite = 'Minervini, Trade Like a Stock Market Wizard, Ch.6 (p.102 "concentrate on the top two or three stocks in a group"; p.108 "stay away from the laggards").';
        if (row.group_leader) {
          return (
            <div style={{ padding: '0.35rem 0.2rem 0' }}>
              <span
                className="sepa-chip"
                title={`Group leader: RS ${rankTxt} in ${ind}. ${cite}`}
                style={{ color: '#10b981', borderColor: '#10b981', cursor: 'help', fontSize: '0.72rem' }}
              >
                👑 #{row.group_rs_rank} in {shortInd}
              </span>
            </div>
          );
        }
        return (
          <div style={{ padding: '0.35rem 0.2rem 0' }}>
            <span
              className="sepa-chip"
              title={`Laggard in ${ind} — RS ${rankTxt}, trails the group leader ${row.group_leader_symbol ?? ''}. ${cite}`}
              style={{ color: '#f59e0b', borderColor: '#f59e0b', cursor: 'help', fontSize: '0.72rem' }}
            >
              ⤵ laggard vs {row.group_leader_symbol ?? 'leader'}
            </span>
          </div>
        );
      })()}

      {presetOpen && (
        <Suspense fallback={null}>
          <TickerAlertPresets
            symbol={row.symbol}
            currentPrice={liveQuote?.last_price ?? row.last_close ?? null}
            onClose={() => setPresetOpen(false)}
            onCustomLevel={() => setAlertOpen(true)}
          />
        </Suspense>
      )}

      {alertOpen && (
        <PriceAlertModal
          symbol={row.symbol}
          currentPrice={setup?.pivot ?? null}
          onClose={() => setAlertOpen(false)}
        />
      )}

      {moatOpen && (
        <Suspense fallback={null}>
          <MoatPeersModal symbol={row.symbol} onClose={() => setMoatOpen(false)} />
        </Suspense>
      )}

      {whalesOpen && (
        <Suspense fallback={null}>
          <WhalesFlowModal symbol={row.symbol} onClose={() => setWhalesOpen(false)} />
        </Suspense>
      )}

      {whales13dOpen && (
        <Suspense fallback={null}>
          <Whales13DModal symbol={row.symbol} onClose={() => setWhales13dOpen(false)} />
        </Suspense>
      )}

      {macroOpen && (
        <Suspense fallback={null}>
          <MacroContextModal symbol={row.symbol} onClose={() => setMacroOpen(false)} />
        </Suspense>
      )}

      {/* Signal drill-in — one modal slot used by all 6 clickable volume
          chips (strong/accumulating/distributing accumulation, pocket
          pivot, hi-vol breakout, money outflow, dist-days warning).
          Pattern: chip onClick sets openSignal; modal reads it; close
          resets to null. */}
      {openSignal && (
        <Suspense fallback={null}>
          <SignalDrillModal
            kind={openSignal}
            data={signalData}
            onClose={() => setOpenSignal(null)}
          />
        </Suspense>
      )}

      <div className="sepa-card__body">
        {/* Trend row — clickable. Opens the trend_template drill showing
            which of the 8 gates passed/failed. */}
        <div
          className="sepa-card__row"
          role="button" tabIndex={0}
          title={`Trend Template — passed ${row.trend.passed} of 8. Tap for gate-by-gate breakdown.`}
          onClick={(e) => { e.stopPropagation(); setOpenSignal('trend_template'); }}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') {
            e.stopPropagation(); e.preventDefault(); setOpenSignal('trend_template');
          }}}
          style={{ cursor: 'pointer' }}
        >
          <span className="sepa-card__label">Trend</span>
          <SepaTrendDots checks={row.trend.checks} passed={row.trend.passed} />
        </div>

        {/* RS row — clickable. Opens the rs_rank drill explaining the
            ≥70 gate + score contribution. */}
        <div
          className="sepa-card__row"
          role="button" tabIndex={0}
          title="RS rank — IBD-style 1-99 percentile. Tap for ≥70 gate explanation + score contribution."
          onClick={(e) => { e.stopPropagation(); setOpenSignal('rs_rank'); }}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') {
            e.stopPropagation(); e.preventDefault(); setOpenSignal('rs_rank');
          }}}
          style={{ cursor: 'pointer' }}
        >
          <span className="sepa-card__label">RS</span>
          <div className="sepa-rs-bar">
            <div
              className="sepa-rs-bar__fill"
              style={{ width: `${row.rs_rank ?? 0}%` }}
              data-strong={row.rs_rank != null && row.rs_rank >= 80 ? 'true' : 'false'}
            />
            <span className="sepa-rs-bar__num mono">{row.rs_rank ?? '—'}</span>
          </div>
        </div>

        {setup && riskPct != null && (
          <div className="sepa-card__row sepa-card__setup">
            <span
              role="button" tabIndex={0}
              className={`sepa-pill sepa-pill--${setup.type.toLowerCase()}`}
              title="Tap for setup detail + score contribution"
              onClick={(e) => { e.stopPropagation();
                const kind: SignalKind = setup.type === 'VCP' ? 'setup_vcp' : 'setup_power_play';
                setOpenSignal(kind);
              }}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') {
                e.stopPropagation(); e.preventDefault();
                const kind: SignalKind = setup.type === 'VCP' ? 'setup_vcp' : 'setup_power_play';
                setOpenSignal(kind);
              }}}
              style={{ cursor: 'pointer' }}
            >{setup.type === 'POWER_PLAY' ? 'Power Play' : setup.type}<span style={{ fontSize: '0.7em', opacity: 0.6, marginLeft: 3 }}>↗</span></span>
            <span
              className="mono"
              title={
                `Pivot $${setup.pivot} = buy point. Stop $${setup.stop} = exit. ` +
                `Risk = (pivot − stop) / pivot × 100 = ${riskPct.toFixed(1)}%.\n\n` +
                `⚠️ Evaluate stop at CLOSE (3:00 PM CT / 4:00 PM ET).\n` +
                `Pre-close intraday touches are noise; a CLOSE below the stop is the ` +
                `actual exit signal. Exception: an intraday move of −12% or more from ` +
                `yesterday's close is a structural break — exit immediately.`
              }
            >
              ${setup.pivot} → stop ${setup.stop}{' '}
              <span className={`sepa-risk ${riskPct > 10 ? 'sepa-risk--bad' : riskPct > 7 ? 'sepa-risk--warn' : 'sepa-risk--ok'}`}>
                ({riskPct.toFixed(1)}%)
              </span>
              <span
                style={{
                  marginLeft: '0.3rem',
                  padding: '0 4px',
                  fontSize: '0.6rem',
                  border: '1px solid var(--warn, #d97706)',
                  color: 'var(--warn, #d97706)',
                  borderRadius: 3,
                  letterSpacing: '0.03em',
                  textTransform: 'uppercase',
                  whiteSpace: 'nowrap',
                  cursor: 'help',
                }}
                aria-label="Stop is evaluated at close, not intraday"
              >@ close ⓘ</span>
            </span>
          </div>
        )}

        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); setShowSignals((v) => !v); }}
          style={{ alignSelf: 'flex-start', background: 'transparent', border: 'none',
            color: 'var(--cm-slate, #94a3b8)', font: 'inherit', fontSize: '0.7rem',
            cursor: 'pointer', padding: '0.2rem 0', opacity: 0.85 }}
          title="Show/hide the full read for this name — the why-buy thesis, what's moving the rank, and all signal chips (volume, insider/valuation, realtime accum/dist, ADR, 13F whales, SEC activity, macro, moat, pioneer themes). Everything also lives on the ticker detail page."
        >
          {showSignals ? '▾ less' : '▸ why-buy & signals'}
        </button>

        {showSignals && (
        <div className="sepa-card__flags">
          {/* Volume signal chips — strong/accumulating/distributing accum,
              pocket pivot, hi-vol breakout, money outflow, dist-days warning.
              Until 2026-05-22 this was ~125 lines of inline JSX duplicated
              between here and the SEPA detail page. Now it's the shared
              <SepaSignalChips> component with `subset="volume_only"` so the
              detail-page-specific chips (score, trend, RS, stage, setup, ADR)
              don't render here — the card already shows those via its
              dedicated score bar / trend dots / RS bar / setup pill / stage
              badge UI, so re-rendering them as chips would double-up.
              The shared component manages its own SignalDrillModal slot —
              unrelated to this card's `openSignal` state which still drives
              the trend / RS / setup / stage / ADR / score-breakdown drills
              from the card-specific UI elements above and below. */}
          <SepaSignalChips row={row} subset="volume_only" />
          {isMomentumLeader(row) && (
            <span
              className="sepa-flag sepa-flag--good"
              style={{ fontWeight: 700 }}
              title={MOMENTUM_LEADER_TOOLTIP}
            >
              🚀 Momentum Leader
            </span>
          )}
          {/* JIT-loaded chips: cluster insider buying + valuation (under/fair/over).
              Lazy via IntersectionObserver — fires only when card enters viewport.
              Backend caches 24h so subsequent scrolls don't re-hit EDGAR/yfinance. */}
          <CardEnrichmentChips symbol={row.symbol} />
          {/* Real-time accumulation/distribution + short-interest squeeze.
              Live tape polls every 6s while the card is on screen. */}
          <RealtimeChips symbol={row.symbol} />
          {row.adr_pct != null && (
            <span
              role="button" tabIndex={0}
              className={`sepa-flag ${row.adr_pct >= 4 ? 'sepa-flag--good' : 'sepa-flag--neutral'}`}
              title="Tap for ADR explanation + how much it added to the score"
              onClick={(e) => { e.stopPropagation(); setOpenSignal('adr'); }}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') {
                e.stopPropagation(); e.preventDefault(); setOpenSignal('adr');
              }}}
              style={{ cursor: 'pointer' }}
            >
              ADR {row.adr_pct}%<span style={{ fontSize: '0.7em', opacity: 0.6, marginLeft: 3 }}>↗</span>
            </span>
          )}
          {row.day_change_pct != null && (
            <span
              className={`sepa-flag ${
                row.day_change_pct >= 2 ? 'sepa-flag--good' :
                row.day_change_pct <= -2 ? 'sepa-flag--bad' :
                'sepa-flag--neutral'
              }`}
              title={
                `Day % — change from yesterday's close. ` +
                (row.last_close != null ? `Last close $${row.last_close}` : '')
              }
            >
              Day {row.day_change_pct > 0 ? '+' : ''}{row.day_change_pct}%
            </span>
          )}
          {row.dual_momentum?.return_12m != null && (
            <span
              role="button" tabIndex={0}
              className={`sepa-flag ${
                row.dual_momentum.abs_mom_pass && row.dual_momentum.beats_spy
                  ? 'sepa-flag--good'
                  : row.dual_momentum.abs_mom_pass
                    ? 'sepa-flag--neutral'
                    : 'sepa-flag--bad'
              }`}
              title="Tap for Antonacci dual-momentum breakdown — returns waterfall (1m/3m/6m/12m) and the two pass/fail gates (absolute & relative momentum)"
              onClick={(e) => { e.stopPropagation(); setOpenSignal('dual_momentum_12m'); }}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') {
                e.stopPropagation(); e.preventDefault(); setOpenSignal('dual_momentum_12m');
              }}}
              style={{ cursor: 'pointer' }}
            >
              12m {row.dual_momentum.return_12m > 0 ? '+' : ''}{row.dual_momentum.return_12m}%
              {row.dual_momentum.abs_mom_pass && row.dual_momentum.beats_spy && ' ✓'}
            </span>
          )}
          {row.vcp?.tightness != null && (
            <span
              className={`sepa-flag ${row.vcp.tightness_band === 'tight' ? 'sepa-flag--good' : 'sepa-flag--neutral'}`}
              title={`VCP tightness ${row.vcp.tightness}/100 — ${row.vcp.tightness_band} (≥70 well-formed · 40–69 developing · <40 early)`
                + ((row.vcp.tightness_drivers && row.vcp.tightness_drivers.length) ? `\n${row.vcp.tightness_drivers.join(' · ')}` : '')
                + `\nHow textbook the contraction footprint is — tightening, handle, volume dry-up, depth, proximity to pivot (Minervini pp.198–205).`}
            >
              🎯 VCP {row.vcp.tightness}
              {' · '}{row.vcp.tightness_band === 'tight' ? 'Tight' : row.vcp.tightness_band === 'developing' ? 'Developing' : 'Early'}
            </span>
          )}
          {row.vcp?.has_base && row.vcp?.pivot_quality_ok && (
            <span
              className="sepa-flag sepa-flag--good"
              title="Pivot quality ✓ — the Volatility Contraction Pattern (VCP) pivot sits at the top of a meaningful prior advance, not a random flat zone. Per Minervini p.199."
            >✓ pivot quality</span>
          )}
          {/* Hedge fund / institutional flow chip from cached 13F data.
              Only renders when whales data is present in the cache for
              this ticker — drill into supply/demand panel to populate. */}
          {whalesFlow && (
            <span
              role="button"
              tabIndex={0}
              className={`sepa-flag ${
                whalesFlow.signal === 'accumulating' ? 'sepa-flag--good' :
                whalesFlow.signal === 'distributing' ? 'sepa-flag--bad' :
                'sepa-flag--neutral'
              }`}
              // Click stops propagation so we don't ALSO open the
              // candidate drill (parent card has onSelect on click).
              // Keyboard handler mirrors click for accessibility.
              onClick={(e) => { e.stopPropagation(); setWhalesOpen(true); }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.stopPropagation();
                  e.preventDefault();
                  setWhalesOpen(true);
                }
              }}
              style={{ cursor: 'pointer' }}
              title={
                `Tap for full list of buyers + sellers\n\n` +
                `Institutional flow (13F filings, 45-day lag):\n` +
                `${whalesFlow.n_buying} institution(s) BUYING\n` +
                `${whalesFlow.n_selling} institution(s) SELLING\n` +
                (whalesFlow.n_unchanged ? `${whalesFlow.n_unchanged} unchanged\n` : '') +
                (whalesFlow.top_buy  ? `\nTop buy:  ${whalesFlow.top_buy}` : '') +
                (whalesFlow.top_sell ? `\nTop sell: ${whalesFlow.top_sell}` : '')
              }
            >
              🐋 {whalesFlow.signal === 'accumulating' ? `Accumulating +${whalesFlow.n_buying}`
                  : whalesFlow.signal === 'distributing' ? `Distributing −${whalesFlow.n_selling}`
                  : `Balanced (${whalesFlow.n_buying}↑/${whalesFlow.n_selling}↓)`}
              <span style={{ fontSize: '0.7em', opacity: 0.6, marginLeft: 3 }}>↗</span>
            </span>
          )}
          {/* 📋 SEC activity chip — combined Form 4 (insider trades) +
              Form 144 (insider pre-sale notice) + SC 13D/G (5% ownership
              threshold). The 13D-only version pivoted on 2026-05-29
              because SEPA's liquid-name universe almost never triggers
              13D; Form 4/144 is the real real-time-ish signal here.
              Only renders when whales13d is in the bulk cache. */}
          {whales13d && whales13d.n_filings > 0 && (
            <span
              role="button"
              tabIndex={0}
              className="sepa-flag sepa-flag--good"
              onClick={(e) => { e.stopPropagation(); setWhales13dOpen(true); }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.stopPropagation();
                  e.preventDefault();
                  setWhales13dOpen(true);
                }
              }}
              style={{ cursor: 'pointer' }}
              title={
                `Tap for full list of recent SEC filings\n\n` +
                `Recent filings in lookback window:\n` +
                `  ${whales13d.n_form4} Form 4 (insider trades)\n` +
                `  ${whales13d.n_form144} Form 144 (insider pre-sale notice)\n` +
                `  ${whales13d.n_form13} SC 13D/G (5% ownership threshold)\n\n` +
                `Latest: ${whales13d.latest_form} on ${whales13d.latest_date}`
              }
            >
              📋 SEC · {whales13d.n_filings}
              {whales13d.n_form13 > 0 && (
                <span style={{ marginLeft: 4, opacity: 0.85 }}>· {whales13d.n_form13}×13D</span>
              )}
              <span style={{ fontSize: '0.7em', opacity: 0.6, marginLeft: 3 }}>↗</span>
            </span>
          )}
          {/* 🌍 Macro chip — Claude-generated brief on geopolitics,
              futures/commodities tied to this stock, the bear case
              right now, and sector context. Plus live headlines from
              Finnhub. Cached 6h on the backend per symbol so repeat
              clicks are free.

              Always renders (no data dependency) — every ticker gets
              a macro read. Clicking fires the modal which lazy-loads
              the chunk + hits /macro/{symbol}. */}
          <span
            role="button"
            tabIndex={0}
            className="sepa-flag sepa-flag--neutral"
            onClick={(e) => { e.stopPropagation(); setMacroOpen(true); }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.stopPropagation();
                e.preventDefault();
                setMacroOpen(true);
              }
            }}
            style={{ cursor: 'pointer' }}
            title="Macro context: geopolitics, futures, bear case, sector dynamics + recent headlines. Generated by Claude, cached 6h."
          >
            🌍 Macro
            <span style={{ fontSize: '0.7em', opacity: 0.6, marginLeft: 3 }}>↗</span>
          </span>
          {/* Put / Call open interest from latest SOIR snapshot.
              Tone: BULLISH = green, BEARISH = red, WATCH = amber, else neutral.
              Hover for full SOIR ratio + signal reason. */}
          {soir && (soir.put_oi != null || soir.call_oi != null) && (
            <span
              role="button" tabIndex={0}
              className={`sepa-flag ${
                soir.signal === 'BULLISH' ? 'sepa-flag--good' :
                soir.signal === 'BEARISH' ? 'sepa-flag--bad' :
                soir.signal === 'WATCH'   ? 'sepa-flag--warn' :
                'sepa-flag--neutral'
              }`}
              style={{ cursor: 'pointer' }}
              title="Tap for full options-sentiment (SOIR) detail"
              onClick={(e) => { e.stopPropagation(); setSoirOpen(true); }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); setSoirOpen(true); }
              }}
            >
              📊 P {((soir.put_oi ?? 0) / 1000).toFixed(0)}k / C {((soir.call_oi ?? 0) / 1000).toFixed(0)}k
              {soir.signal && soir.signal !== 'NEUTRAL' && ` · ${soir.signal[0]}`}
            </span>
          )}
          {soir && soirOpen && (
            <SoirModal soir={soir} symbol={row.symbol} onClose={() => setSoirOpen(false)} />
          )}
          {row.fundamentals && row.fundamentals.passed > 0 && (
            <span
              className="sepa-flag sepa-flag--good"
              title={`CANSLIM (William O'Neil) — ${row.fundamentals.passed} of 3 quantifiable gates passed: C (Current Quarterly Earnings ≥25%), A (Annual Earnings 3yr ≥25%), I (Institutional Sponsorship 40-80%).`}
            >CANSLIM {row.fundamentals.passed}/3</span>
          )}
          {/* Buffett-style moat chip. Tier 4 = WIDE, 3 = NARROW, 2 = SOME,
              1 = NONE, 0 = UNKNOWN (data missing — chip suppressed). */}
          {row.moat && (
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => { e.stopPropagation(); setMoatOpen(true); }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.stopPropagation();
                  e.preventDefault();
                  setMoatOpen(true);
                }
              }}
              className={`sepa-flag ${
                row.moat.tier >= 4 ? 'sepa-flag--good' :
                row.moat.tier >= 3 ? 'sepa-flag--good' :
                row.moat.tier >= 2 ? 'sepa-flag--neutral' :
                row.moat.tier >= 1 ? 'sepa-flag--bad' :
                'sepa-flag--muted'
              }`}
              title={
                row.moat.tier === 0
                  ? (`No moat data — yfinance is missing fundamentals (ROE/margins/FCF) for ${row.symbol}. ` +
                     `Common for ADRs, recent IPOs, or stocks with no analyst coverage. ` +
                     `Tap to see what data IS available.`)
                  : (`Tap to see peer comparison and why this scored ${row.moat.score}/100.\n\n` +
                     `Buffett-style economic moat — ${row.moat.label}.\n` +
                     `${row.moat.narrative}` +
                     (row.moat.is_partial
                       ? `\n\n⚠ Partial data — scored from ${row.moat.data_completeness}/6 underlying metrics. Score may understate true moat.`
                       : ''))
              }
              style={{ cursor: 'pointer', opacity: row.moat.tier === 0 ? 0.7 : 1 }}
            >
              🏰 {row.moat.tier === 0 ? 'no data' : `${row.moat.label} ${row.moat.score.toFixed(0)}`}
              {row.moat.is_partial && row.moat.tier >= 1 && (
                <span style={{ fontSize: '0.7em', opacity: 0.7, marginLeft: 3 }} title="Partial data — see tooltip">⚠</span>
              )}
              <span style={{ fontSize: '0.7em', opacity: 0.6, marginLeft: 2 }}>↗</span>
            </span>
          )}
          {/* Product launches chip — only renders if cached launches exist
              for this ticker. Lazy-loaded so the network call doesn't fire
              on cards the user never scrolls past. */}
          <Suspense fallback={null}>
            <ProductLaunchesChip symbol={row.symbol} />
          </Suspense>
          {row.pioneer_themes?.map((t) => (
            <span
              key={t.id}
              className={`sepa-flag sepa-pioneer-tag sepa-pioneer-tag--${t.id}`}
              title={
                `Pioneer theme — ${t.label}. ` +
                `This ticker is in our curated list of breakthrough categories. ` +
                `Click "Pioneers" in the nav for full theme breakdown + breakthrough news.`
              }
            >🚀 {t.label}</span>
          ))}
        </div>
        )}

        {/* "Why buy" + ranking-drivers block — sits above the staleness
            footer so the thesis is the last actionable thing the user
            reads before the disclaimer. Volume signals are the headline
            (user's primary buy signal); ranking note explains why the
            same card can move from rank 3 → 9 within minutes. */}
        {showSignals && <SepaWhyBuy row={row} signalData={signalData} />}

        {/* SEPA staleness footer — every card is rated against yesterday's
            close. Today's intraday damage doesn't reflect until tonight's
            16:00 ET / 15:00 CT close + 15:30 CT cron rescan. Spelled out
            so a stale BUY chip during a collapsing tape doesn't fool the
            user (the MU lesson). */}
        <SepaAnchorFooter scannedAt={(row as any).scanned_at} />
      </div>
    </article>
  );

  if (setupOverlay) {
    return (
      <div className="sepa-card-with-overlay">
        {setupOverlay}
        {cardBody}
      </div>
    );
  }
  return cardBody;
}

/** Tiny mono footer noting when the card's rating was computed and when
 *  it will next re-rate. CT-anchored because that's the user's timezone. */
function SepaAnchorFooter({ scannedAt }: { scannedAt?: string | null }) {
  const fmt = (iso?: string | null): string => {
    if (!iso) return 'yesterday\'s close';
    try {
      const d = new Date(iso);
      return new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/Chicago',
        month: 'short', day: 'numeric',
        hour: 'numeric', minute: '2-digit', hour12: true,
      }).format(d) + ' CT';
    } catch { return 'yesterday\'s close'; }
  };
  return (
    <div
      className="mono"
      style={{
        marginTop: '0.4rem',
        fontSize: '0.66rem',
        color: 'var(--cm-slate)',
        opacity: 0.75,
        display: 'flex',
        flexWrap: 'wrap',
        gap: '0.6rem',
      }}
      title="SEPA ratings are computed against the official daily close, not intraday prices. Today's intraday move won't flip the rating until after 4 PM ET / 3 PM CT close."
    >
      <span>Rated: {fmt(scannedAt)}</span>
      <span>· Re-rates after 3:00 PM CT (4:00 PM ET)</span>
    </div>
  );
}
