import { useEffect, useMemo, useRef, useState } from 'react';
import { EarningsReportPicks } from '../components/EarningsReportPicks';
import { useNavigate, useNavigationType } from 'react-router-dom';
import { useSepaScan } from '../hooks/useSepa';
import { ageHuman } from '../lib/swrCache';
import { useSepaScanStream } from '../hooks/useSepaScanStream';
import { useAlertNotifier } from '../hooks/usePriceAlerts';
import type { SepaCandidate, Rating } from '../hooks/useSepa';
import { SepaBriefBanner } from '../components/SepaBriefBanner';
import { MarketGaugeBanner } from '../components/MarketGaugeBanner';
import { MarketClockStrip } from '../components/MarketClockStrip';
import { MinerviniLesson } from '../components/MinerviniLesson';
import { SepaHero } from '../components/SepaHero';
import { SepaFilterBar, type SepaFilters } from '../components/SepaFilterBar';
import { useEarningsMap, EARNINGS_WARN_DAYS, type EarningsInfo } from '../hooks/useEarningsMap';
import { SepaCandidateCard } from '../components/SepaCandidateCard';
import { SepaCardGridSkeleton } from '../components/SepaCardSkeleton';
import { pivotTiming, triggerRank, buyabilityRank } from '../lib/pivotTiming';
// Provides per-card historical rank/score deltas to every SepaCandidateCard
// rendered below. Single fetch per page (yesterday's + 5d-ago full scans
// from /sepa/history/date/{date}) — see SepaTrendContext for details.
import { SepaTrendProvider } from '../components/SepaTrendContext';
// Tier lookup for the 🦅 Hedge-Fund-Top-Buyer filter — same curated list
// the WhalesFlowModal uses for the per-fund ⭐⭐⭐ badge.
import { getFundTier } from '../lib/fundTiers';
import { isMomentumLeader } from '../lib/momentumLeader';
import { isBaseSetup } from '../lib/baseSetup';
import { isCheatRegime } from '../lib/cheat';
import { useMarketGauge } from '../hooks/useMarketGauge';
// Political-disclosure flag lookup for 🏛️ POTUS Family + 🇺🇸 US Gov filters.
import { getPoliticalChipFlags } from '../lib/politicalDisclosures';
import { SepaScanProgress } from '../components/SepaScanProgress';
import { SepaDateScrubber } from '../components/SepaDateScrubber';
import { useSepaScanByDate } from '../hooks/useSepaHistory';
import { InfoButton } from '../components/InfoButton';
import { SiteTour, TOUR_DONE_KEY } from '../components/SiteTour';
import { GlobalStockSearch } from '../components/GlobalStockSearch';
import { useOptionsPulse, type SoirRow } from '../hooks/useOptionsPulse';
import { useWhalesFlow, type WhalesFlowRow } from '../hooks/useWhalesFlow';
import { useWhales13DFlow } from '../hooks/useWhales13DFlow';
import { prefillBulkQuotes } from '../hooks/useLiveQuote';
import { registerSymbolInterest } from '../lib/eventBus';
import { useLivePrices } from '../hooks/useLivePrices';
import {
  SepaSetupTabs,
  TAB_TO_KIND,
  tabLabel,
  type SepaTab,
} from '../components/SepaSetupTabs';
import { SepaSetupInfoPanel } from '../components/SepaSetupInfoPanel';
import { SepaSetupInfoBanner } from '../components/SepaSetupInfoBanner';
import {
  useSetupsByKind,
  getCachedSetupCount,
  type Setup,
} from '../hooks/useSetupsByKind';
import { SetupOverlayStrip } from '../components/SetupOverlayStrip';

const PageInfo = (
  <>
    <p>
      <strong>Specific Entry Point Analysis (SEPA)</strong> is Mark Minervini's framework
      for finding stocks with the highest probability of a sharp upward move.
    </p>
    <p>Every candidate has to clear five gates before it shows up here.</p>
    <ul>
      <li>
        <strong>Trend Template</strong> — eight rules on price and moving averages,
        including price above the 50-day, 150-day, and 200-day averages, and a rising
        200-day average.
      </li>
      <li>
        <strong>Relative Strength (RS) ≥ 70</strong> — outperforming 70% of the
        market over the last twelve months.
      </li>
      <li>
        <strong>Stage 2</strong> — the advancing phase of the four-stage cycle
        (Stage 1 Basing, Stage 2 Advancing, Stage 3 Topping, Stage 4 Declining).
      </li>
      <li>
        <strong>Tight base</strong> — a Volatility Contraction Pattern or Power Play
        showing institutional accumulation.
      </li>
      <li>
        <strong>Risk-managed entry</strong> — a defined pivot point with a stop loss
        no more than 7-8% below entry.
      </li>
    </ul>
  </>
);

const TopPicksInfo = (
  <>
    <p>
      The five highest-conviction candidates from today's scan, regardless of your
      filters.
    </p>
    <p>
      Ranked by <strong>composite score</strong> (0-100). The
      composite blends Trend Template strength, Relative Strength rank, base
      quality, fundamentals (Capital, Annual earnings, Numbers, New highs,
      Supply/demand, Leader, Institutional sponsorship — together CANSLIM),
      and any near-term catalyst. The actionable call is the
      <strong> Enter / Wait / Watch</strong> entry signal on each card.
    </p>
    <p>Click a card to see the full breakdown for that ticker.</p>
  </>
);

const ResultsInfo = (
  <>
    <p>The full filtered list. Each card shows, at a glance:</p>
    <ul>
      <li><strong>Composite score (0-100)</strong> — overall conviction.</li>
      <li>
        <strong>Relative Strength (RS) rank</strong> — percentile vs. the market
        over 12 months.
      </li>
      <li>
        <strong>Stage</strong> — 1 Basing, 2 Advancing, 3 Topping, 4 Declining.
        Only Stage 2 is an entry candidate.
      </li>
      <li>
        <strong>Trend Template criteria</strong> — how many of the eight rules pass.
      </li>
      <li>
        <strong>Entry setup</strong> — Volatility Contraction Pattern or Power Play,
        plus the pivot price and stop loss.
      </li>
    </ul>
    <p>Click a card for full chart, fundamentals, and position-sizing math.</p>
  </>
);

const RATING_ORDER: Record<Rating, number> = {
  STRONG_BUY: 5, BUY: 4, WATCH: 3, NEUTRAL: 2, AVOID: 1,
};

function defaultRating(score: number): Rating {
  if (score >= 85) return 'STRONG_BUY';
  if (score >= 70) return 'BUY';
  if (score >= 60) return 'WATCH';
  if (score >= 40) return 'NEUTRAL';
  return 'AVOID';
}

/** How recent a volume-confirmed breakout the 🟢 Enter chip will accept. */
const BREAKOUT_WEEK_MAX_DAYS = 5;   // "past week" = ≤5 trading days

/** Decision-gate filter. Shared by both apply paths so they never drift.
 *  - 'ALL'   → no gate.
 *  - 'ENTER' → buyable, with the breakout-recency requirement tuned by
 *    `breakoutWindow` (user 2026-06-02):
 *      • 'TODAY' (default) → STRICT book gate `is_buyable` — a SAME-DAY
 *        volume-confirmed breakout (pp.79-83/198-203).
 *      • 'WEEK'  → `setup_ready` AND a breakout fired in the last ≤5 trading
 *        days (still in/near the buy range — buy the days following a breakout).
 *      • 'ANY'   → `setup_ready` (Stage 2 + base + not-late + liquid), no
 *        breakout trigger required.
 *  - 'WAIT' / 'HOLD_WATCH' → match the `entry_exit.decision` banner the card shows. */
function passesDecision(
  r: SepaCandidate,
  decision: SepaFilters['decision'],
  breakoutWindow: SepaFilters['breakoutWindow'],
): boolean {
  const d = decision ?? 'ALL';
  if (d === 'ALL') return true;
  if (d === 'ENTER') {
    const w = breakoutWindow ?? 'TODAY';
    if (w === 'ANY') return r.setup_ready === true;
    if (w === 'WEEK') {
      const dsb = r.volume?.days_since_breakout;
      return r.setup_ready === true && dsb != null && dsb <= BREAKOUT_WEEK_MAX_DAYS;
    }
    return r.is_buyable === true;   // 'TODAY' — strict book gate
  }
  return (r.entry_exit?.decision ?? null) === d;
}

/** Reactive inputs the filter predicate reads beyond the row + filters
 *  themselves: the two async Maps the page loads (earnings calendar, whale
 *  13F flow). Passed in explicitly so `passesSepaFilters` stays a pure
 *  module-level function with no closure over component state — and so every
 *  call site is forced to list the SAME inputs in its useMemo dependency
 *  array (see both call sites below). */
type SepaFilterDeps = {
  earningsMap: Map<string, EarningsInfo>;
  whalesFlow: Map<string, WhalesFlowRow>;
};

/** Single source of truth for the SepaFilterBar gate chain.
 *
 *  Applied in two render paths that must behave identically:
 *    1. the main "all candidates" list  → the `filtered` useMemo, and
 *    2. the setup-category tabs (VCP / Bull Flag) → the `passesFilters`
 *       useMemo callback.
 *
 *  These were previously hand-copied and had drifted — the setup-tab path was
 *  silently missing the `momentumLeaderOnly` gate, so the 🚀 chip filtered the
 *  main list but not the VCP/Power Play tabs. Collapsing both onto this one
 *  function makes that class of drift impossible.
 *
 *  Every clause is an AND that returns false on a miss, so clause ORDER never
 *  affects the boolean result. */
function passesSepaFilters(
  r: SepaCandidate,
  filters: SepaFilters,
  deps: SepaFilterDeps,
): boolean {
  const { earningsMap, whalesFlow } = deps;

  // Tier (Buy/Strong Buy) filter removed 2026-06-21 — rely on Enter/Watch.
  // Setup gate. 'BASE' (the default, Ajay 2026-06-22) keeps real-base setups
  // (VCP / Power Play / pocket pivot) and hides bare breakouts with no base;
  // 'VCP'/'POWER_PLAY' match exactly; 'ALL' shows everything.
  if (filters.setup === 'BASE') {
    if (!isBaseSetup(r.entry_setup?.type)) return false;
  } else if (filters.setup !== 'ALL' && r.entry_setup?.type !== filters.setup) {
    return false;
  }
  // Timed-entry decision gate. "Enter" binds to the STRICT book buyable
  // gate (is_buyable, pp.79-83/198-203) per user 2026-06-02 ("enter = buyable
  // at all cost"); Wait/Watch match the entry_exit.decision banner the card
  // shows. (Helper passesDecision keeps the two apply paths in sync.)
  if (!passesDecision(r, filters.decision, filters.breakoutWindow)) return false;
  if (filters.tightPivotOnly && !pivotTiming(r).pivotTight) return false;
  if (filters.buyZoneOnly && !pivotTiming(r).inBuyZone) return false;
  if (filters.nearPivotOnly && !pivotTiming(r).nearPivot) return false;

  if (filters.salesStrongOnly && !['strong','explosive'].includes(r.fundamentals?.sales?.tier ?? '')) return false;
  if (filters.rsMin > 0 && (r.rs_rank ?? 0) < filters.rsMin) return false;
  if (filters.search && !r.symbol.includes(filters.search)) return false;
  if (filters.dmEligibleOnly) {
    const dm = r.dual_momentum;
    if (!dm) return false;
    if (!dm.abs_mom_pass) return false;
    if (dm.beats_spy === false) return false;
  }
  if (filters.type === 'equity' && r.is_etf) return false;
  if (filters.type === 'etf' && !r.is_etf) return false;
  if (filters.pioneerOnly && !r.is_pioneer) return false;
  // Stage filter — gate by Weinstein stage (1/2/3/4). When ALL, no gate.
  if (filters.stage !== 'ALL' && r.stage?.stage !== filters.stage) return false;
  // Moat filter — Buffett tier minimum. When 0, no gate. UNKNOWN
  // (tier 0) gets excluded as soon as the user opts into any minimum.
  if (filters.moatMin > 0) {
    const tier = r.moat?.tier ?? 0;
    if (tier < filters.moatMin) return false;
  }
  // ≥1.5× volume chip (default ON) — today's volume must be ≥1.5× the
  // 50-day average; unknown volume hides while on.
  if (filters.volX15Only) {
    const v = r.volume;
    if (!v?.last_vol || !v?.avg_vol_50 || v.last_vol < 1.5 * v.avg_vol_50) return false;
  }
  // Earnings-soon gate (ATEX lesson 2026-06-11). Unknown dates pass (fail
  // open; the chip's absence is honest about coverage).
  if (filters.hideEarningsSoon) {
    const er = earningsMap.get(r.symbol?.toUpperCase());
    if (er && er.days_to <= EARNINGS_WARN_DAYS) return false;
  }
  // Hide-Distributing chip — drop institutional-distribution tape OR
  // Chaikin money-outflow names. Opposite of "accumulation", so if
  // the user enables this they don't want them at all, regardless of score.
  if (filters.hideDistributing) {
    const v = r.volume;
    if (v?.accumulation_strength === 'distributing') return false;
    if (v?.cmf_signal === 'outflow') return false;
  }
  // Whales-accumulating filter — pure-FE narrow to candidates whose
  // 13F flow over the last quarter was institutionally net-buying.
  // Reads from the whalesFlow Map already loaded for the page; rows
  // without whales data (most tickers don't have 13F coverage) are
  // dropped because the user explicitly opted to see whales-only.
  // The pairing of this chip with Hide Distributing produces the
  // "whales + tape both bullish" short-list — closest the UI gets
  // to surfacing the user's actual decision criteria ("based on
  // whales and the volume").
  if (filters.whalesAccumOnly) {
    const wf = whalesFlow.get(r.symbol.toUpperCase());
    if (!wf || wf.signal !== 'accumulating') return false;
  }
  // Hedge-fund-top-buyer filter — strictest of the whale chips.
  // The top buying fund name must match a Tier-S entry in the
  // curated fundTiers.ts list (legendary stock-pickers: Berkshire,
  // Tiger, Coatue, Citadel, Pershing, Altimeter, etc). When the
  // top buyer is an index giant (🏛 Vanguard / BlackRock) or an
  // unknown LP, the row is dropped. Same caveat as the tier badge —
  // historical reputation, not forward prediction.
  if (filters.hedgeFundTopBuyer) {
    const wf = whalesFlow.get(r.symbol.toUpperCase());
    if (!wf || !wf.top_buy) return false;
    const tier = getFundTier(wf.top_buy);
    if (tier?.tier !== 'S') return false;
  }
  // POTUS Family filter — narrow to symbols on the curated POTUS-
  // family disclosure list. Pure FE lookup via politicalDisclosures.ts.
  if (filters.potusFamilyOnly) {
    if (!getPoliticalChipFlags(r.symbol).hasPotusFamily) return false;
  }
  // US Gov filter — narrow to symbols with U.S. government
  // involvement (CHIPS Act recipient, govt contractor, program
  // participant). Either category counts as a US Gov tag.
  if (filters.usGovOnly) {
    const flags = getPoliticalChipFlags(r.symbol);
    if (!flags.hasGovtInvestment && !flags.hasGovtContractor) return false;
  }
  // Insider cluster-buy filter — narrow to candidates where ≥3
  // unique insiders filed Form 4 buys in the last 30 days. Reads
  // row.insider populated by scanner.py's catalyst-enrichment path
  // (top 20 candidates after Full Scan + catalyst). Names outside
  // that enriched subset have no row.insider data and are dropped
  // — documented in the chip tooltip so users know coverage.
  if (filters.insiderClusterBuy) {
    const ins = (r as any).insider;
    if (!ins?.form4_cluster_buy) return false;
  }
  // Emerging Momentum Leader — the "next ARM" fingerprint.
  if (filters.momentumLeaderOnly) {
    if (!isMomentumLeader(r)) return false;
  }
  // Venky's filter stack (2026-05-29) — independent toggles layered
  // on top of SEPA's qualifier gate.
  const venky = (r as any).venky;
  if (filters.weekly21SmaPass) {
    if (!venky?.weekly_21sma?.pass) return false;
  }
  if (filters.atrPctMax > 0) {
    const a = venky?.atr?.atr_pct;
    if (a == null || a > filters.atrPctMax) return false;
  }
  if (filters.adxMin > 0) {
    const adx = venky?.adx?.adx;
    if (adx == null || adx < filters.adxMin) return false;
  }
  return true;
}

import { usePageContext } from '../hooks/usePageContext';

export function SepaPage() {
  const {
    data: liveData,
    scanning: legacyScanning,
    revalidating,
    cachedAt,
    refetch,
    loadFull,
    hasFull,
  } = useSepaScan();
  const stream = useSepaScanStream();
  useAlertNotifier();
  const { setPageContext } = usePageContext();

  // Date scrubber: when set, the candidate list comes from the historical
  // snapshot at that date instead of the live scan. Persists in URL hash so
  // links to historical states are shareable.
  const [historicalDate, setHistoricalDate] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    const m = window.location.hash.match(/date=(\d{4}-\d{2}-\d{2})/);
    return m ? m[1] : null;
  });

  // Onboarding tour — auto-start for first-time visitors (no done-flag), and
  // replayable via the 🎓 Tour button. Delay so the page has rendered the
  // elements the tour points at. (2026-05-30)
  const [tourOpen, setTourOpen] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    let done = false;
    try { done = !!localStorage.getItem(TOUR_DONE_KEY); } catch { /* ignore */ }
    if (done) return;
    const t = setTimeout(() => setTourOpen(true), 900);
    return () => clearTimeout(t);
  }, []);

  // Replay trigger from the global 🧭 floating tour launcher (TourLauncher.tsx).
  // It works two ways so it fires whether or not /sepa is already mounted:
  //   • same page  → a 'cheetah:start-tour' window event, and
  //   • navigation → a sessionStorage flag this effect reads on mount.
  // Either path opens the tour after a short delay so the target elements exist.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const open = () => setTimeout(() => setTourOpen(true), 350);
    let viaFlag = false;
    try {
      if (sessionStorage.getItem('cheetah_start_tour') === '1') {
        sessionStorage.removeItem('cheetah_start_tour');
        viaFlag = true;
      }
    } catch { /* ignore */ }
    if (viaFlag) open();
    window.addEventListener('cheetah:start-tour', open);
    return () => window.removeEventListener('cheetah:start-tour', open);
  }, []);

  // Cap how many candidate cards we render at once. Under the broad universe a
  // scan returns 500+ candidates; rendering them all (each card is heavy —
  // stops panel + entry/exit + chips) freezes phones and can render NOTHING
  // at all (user 2026-05-31: "no cards on phone after scan"). Show the top
  // CARD_PAGE, with a "show more" button for the rest.
  const CARD_PAGE = 60;
  const [visibleCount, setVisibleCount] = useState(CARD_PAGE);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (historicalDate) {
      window.location.hash = `date=${historicalDate}`;
    } else if (window.location.hash.startsWith('#date=')) {
      window.location.hash = '';
    }
  }, [historicalDate]);

  const { scan: histScan } = useSepaScanByDate(historicalDate);

  // Page context is set further down (after all useMemos for filtered /
  // tabCounts / setupTabPairs are computed) so the chat assistant has
  // visibility into the active tab, current filters, and visible names —
  // not just the static candidate list.

  // Adapt the historical-snapshot shape to the live-scan shape so the rest
  // of the page renders against either source without branching.
  const data = useMemo(() => {
    if (!historicalDate) return liveData;
    if (!histScan) return null;
    const cands = (histScan.candidates as any[]) || [];
    const isCandidate = (c: any) => ['STRONG_BUY', 'BUY', 'WATCH'].includes(c?.rating);
    return {
      generated_at: histScan.generated_at,
      universe_size: histScan.universe_size,
      analyzed: histScan.analyzed,
      candidate_count: cands.filter(isCandidate).length,
      market_context: histScan.market_context,
      candidates: cands.filter(isCandidate),
      all_results: cands,
    } as any;
  }, [historicalDate, liveData, histScan]);
  const navigate = useNavigate();
  const navType = useNavigationType();
  const restoredRef = useRef(false);
  const openSymbol = (sym: string, e?: React.MouseEvent) => {
    const url = `/sepa/${encodeURIComponent(sym)}`;
    if (e && (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1)) {
      window.open(url, '_blank', 'noopener,noreferrer');
      return;
    }
    // Remember the list position so returning from the detail page lands on the
    // same card + scroll (restored below, gated on POP / a recent save).
    try {
      sessionStorage.setItem('sepa_list_pos', JSON.stringify({
        y: window.scrollY, vc: visibleCount, sym, t: Date.now(),
      }));
    } catch { /* sessionStorage unavailable — non-fatal */ }
    navigate(url, { state: { from: '/sepa', label: 'SEPA' } });
  };
  // Filters persist across reloads — reading the page should always pick up
  // where you left off (rating tier, RS slider, sort, hide-quiet toggle, etc.)
  const FILTER_DEFAULTS: SepaFilters = {
    // Default to Minervini's BUYABLE gate (Ajay 2026-06-12): the page opens
    // showing only names that are actually buyable right now — `decision: 'ENTER'`
    // + `breakoutWindow: 'TODAY'` binds to the strict book gate `is_buyable`
    // (Stage 2 + base + not-late + liquid + a SAME-DAY volume-confirmed breakout,
    // Trade Like a Stock Market Wizard pp.79-83/198-203). On days when nothing is
    // buyable the empty state offers one tap to the qualifier watchlist. Widen the
    // 🟢 decision chip (Enter→All) to see the full list.
    rating: 'ALL', setup: 'BASE', decision: 'ENTER', breakoutWindow: 'TODAY',
    tightPivotOnly: false, buyZoneOnly: false, nearPivotOnly: false,
    salesStrongOnly: false, rsMin: 70, search: '', showAll: true,
    dmEligibleOnly: false, type: 'all', pioneerOnly: false, stage: 'ALL',
    moatMin: 0,
    // Default ON (Ajay 2026-06-10: "do not qualify unless we have 1.5×
    // average volume"). A FILTER, deliberately not a change to the book's
    // p.79 qualifier gate — 1.5× is the ENTRY volume condition (p.203,
    // already enforced in is_buyable), and quiet pre-breakout VCP coilers
    // (pp.198-203) reappear with one tap.
    volX15Only: true,
    // Default ON (Ajay 2026-06-11, the ATEX lesson: bought it hours before
    // an AMC report that missed by 28%). Hides names whose next earnings is
    // within 7 days — buying into a report is a gap bet, not a SEPA entry.
    // One tap shows them again (the ⚠ ER chip still marks each name).
    hideEarningsSoon: true,
    // Default OFF — opt-in toggle. Some users want to see distributing
    // names too (shorting, planning exits on owned positions). Chip
    // flips it on for a cleaner accumulation-only view. Persists via
    // localStorage with the other filters below.
    hideDistributing: false,
    // Default OFF — opt-in toggle. When the user is hunting for short-
    // term Minervini setups, they may want to see candidates without
    // 13F data too. Flip on to restrict to "whales actively buying"
    // for buy-and-hold conviction. Added 2026-05-28.
    whalesAccumOnly: false,
    // Default OFF — strictest of the whale-filter chips. When on, the
    // top buyer name from each candidate's 13F flow must match a
    // Tier-S entry in fundTiers.ts. Added 2026-05-28.
    hedgeFundTopBuyer: false,
    // Default OFF — POTUS Family filter, uses politicalDisclosures.ts.
    // When on, narrows to symbols on the curated POTUS-family list.
    potusFamilyOnly: false,
    // Default OFF — US Gov filter, uses politicalDisclosures.ts.
    // When on, narrows to symbols with govt_investment OR
    // govt_contractor category (CHIPS Act recipients, contractors).
    usGovOnly: false,
    // Default OFF — insider cluster-buy filter. Uses row.insider data
    // populated by scanner's catalyst enrichment on top 20 candidates.
    insiderClusterBuy: false,
    // Default OFF — Emerging Momentum Leader (2026-06-01). The "next ARM"
    // fingerprint: RS leader at new highs + pocket pivot + heavy accumulation
    // + CMF inflow. Computed from existing row fields (lib/momentumLeader.ts).
    momentumLeaderOnly: false,
    // Venky's filter stack (2026-05-29) — all default OFF, layered on
    // top of SEPA. 21-week SMA gate is boolean; ATR%/ADX gates are
    // numeric (0 means disabled, >0 means active with that threshold).
    weekly21SmaPass: false,
    atrPctMax: 0,
    adxMin: 0,
    // Default after-scan ordering — rank by CONVICTION (volume + dried volume +
    // momentum, backend sepa/conviction.py): Enter-eligible names with the most
    // return potential at the top, climax names suppressed to the bottom (Ajay
    // 2026-06-22). Pick "Sort: 🎯 Most ready to Enter" or "Score" to revert.
    sortBy: 'conviction',
  };
  const earningsMap = useEarningsMap();
  const [filters, setFilters] = useState<SepaFilters>(() => {
    if (typeof window === 'undefined') return FILTER_DEFAULTS;
    try {
      // v3 (Ajay 2026-06-22): bumped so the new 'Base only' setup default
      // (hide bare breakouts) actually applies — a one-time reset to the
      // current defaults rather than inheriting a stale persisted setup='ALL'.
      const raw = localStorage.getItem('sepa_filters_v3');
      if (!raw) return FILTER_DEFAULTS;
      return { ...FILTER_DEFAULTS, ...JSON.parse(raw) };
    } catch { return FILTER_DEFAULTS; }
  });
  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem('sepa_filters_v3', JSON.stringify(filters));
  }, [filters]);

  // Phase 2 — setup-category tab strip. "all" is the default (existing
  // behavior). "vcp" is a client-side filter on already-loaded rows.
  // Every other tab maps to a backend /setups/{kind} endpoint via
  // TAB_TO_KIND and is fetched lazily on tab open.
  const [activeTab, setActiveTab] = useState<SepaTab>('all');
  // Reset the visible-card window back to the first page whenever the filters,
  // tab, or scan date change — so re-filtering shows the top of the new set.
  useEffect(() => { setVisibleCount(CARD_PAGE); }, [filters, activeTab, historicalDate]);
  const activeKind = TAB_TO_KIND[activeTab];
  const {
    setups: tabSetups,
    loading: tabLoading,
    error: tabError,
  } = useSetupsByKind(activeKind);

  // When the streaming scan completes, refetch the canonical /sepa/scan
  // endpoint so the candidate cards reflect the just-persisted result.
  useEffect(() => {
    if (stream.phase === 'done' && stream.result) {
      refetch();
    }
  }, [stream.phase, stream.result, refetch]);

  // Unified "scanning" boolean — either legacy POST or the SSE stream
  const scanning = legacyScanning || stream.scanning;

  // Lazy-load the full all_results array only when the user enables
  // "show all analyzed". Saves ~4MB / 5-15sec on phone first paint.
  // Falls back to candidates while the full payload is in flight.
  useEffect(() => {
    if (filters.showAll && !hasFull && !data?.all_results) {
      loadFull();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.showAll, hasFull, data?.all_results]);
  const source: SepaCandidate[] =
    (filters.showAll ? (data?.all_results ?? data?.candidates) : data?.candidates) ?? [];

  // 3-C cheat chip gate (TTLAC §7): show the cheat tag ONLY in a red (risk_off)
  // market with NO buyable pivots — the book's use case (leaders bottom first in
  // a correction). buyable_count is over the candidate set, independent of the
  // current display filters. See src/lib/cheat.ts.
  const cheatGauge = useMarketGauge();
  const buyablePivotCount =
    ((data?.candidates as SepaCandidate[]) ?? []).filter((c) => c.is_buyable).length;
  const cheatRegime = isCheatRegime(cheatGauge?.state, buyablePivotCount);

  // True cold load — no scan data yet AND a fetch is in flight. Drives the
  // card-grid skeleton instead of a false "Nothing matches" flash before the
  // first payload lands. Gated on revalidating/scanning so an errored fetch
  // (no cache) falls through to the empty state rather than spinning forever.
  const coldLoading = !data && (revalidating || legacyScanning);

  // Pull the latest SOIR scan once and build a per-symbol lookup so each
  // candidate card can show put/call open interest + signal without firing
  // a per-card request. Cached at module level by useOptionsPulse.
  const { data: optionsScan } = useOptionsPulse();
  const optionsBySymbol = useMemo(() => {
    const map = new Map<string, SoirRow>();
    for (const r of optionsScan?.rows || []) {
      if (r.symbol) map.set(r.symbol.toUpperCase(), r);
    }
    return map;
  }, [optionsScan]);

  // Institutional flow — only renders chip on cards where the ticker has
  // a cached whales record (previously visited supply/demand panel).
  const whalesFlow = useWhalesFlow();
  // Recent SC 13D/G filings (5% ownership threshold) — fed from the
  // whales13d_cache Mongo collection. Only renders chip on tickers
  // with filings in the lookback window (default 90 days).
  const whales13d = useWhales13DFlow(90);

  // Real-time intraday prices — polled every 2 min during market hours.
  // Overlaid on SEPA cards so the user sees live price + change_pct without
  // a full re-scan. Polling is a no-op outside 9:30–16:00 ET Mon-Fri.
  const livePrices = useLivePrices();

  // Bulk prefill + SSE subscription whenever the candidate list changes.
  //
  // Two HTTP requests for the entire SEPA list:
  //   1. prefillBulkQuotes  → POST /quotes — fills server-side cache
  //      AND seeds the client-side `_quoteState`, so every card's
  //      useQuote/useLiveQuote skips its individual GET.
  //   2. registerSymbolInterest → POST /events/subscribe — adds all
  //      visible symbols to the Finnhub WebSocket feed so subsequent
  //      price changes arrive as live `quote.update` SSE frames.
  //
  // After this useEffect: zero per-card HTTP requests, one persistent
  // SSE stream, and prices update in real time as Finnhub pushes them.
  // Replaces the old N×GET /quote/<sym> stack that used to fill the
  // network tab with "pending" rows.
  useEffect(() => {
    const syms = source.map((r) => r.symbol).filter(Boolean);
    if (syms.length === 0) return;
    // Prefill prices for EVERY rendered card via batched bulk POSTs (HTTP has
    // no live-feed limit). This is what suppresses the per-card GET /quote —
    // critical under the broad universe (500+ cards), where the old 200 cap
    // left ~300 cards firing their own GETs → net::ERR_INSUFFICIENT_RESOURCES.
    // 150/batch keeps each POST reasonable; a handful of POSTs replaces
    // hundreds of GETs.
    for (let i = 0; i < syms.length; i += 150) {
      void prefillBulkQuotes(syms.slice(i, i + 150));
    }
    // Live SSE push stays bounded to the top ~40 names — Finnhub's free tier
    // caps both WS subscriptions and REST quote-rate, and 200 tripped constant
    // 429s (2026-05-31). The rest show their bulk-prefilled price, refreshed
    // each scan; the visible leaders get the live stream.
    registerSymbolInterest(syms.slice(0, 40));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source.length, source[0]?.symbol]);  // re-run on list change

  const filtered = useMemo(() => {
    // Single shared gate chain — see passesSepaFilters (module scope). The
    // setup-tab path (`passesFilters` below) calls the SAME function so the
    // two filter surfaces can never drift.
    const deps = { earningsMap, whalesFlow };
    const out = source.filter((r) => passesSepaFilters(r, filters, deps));
    out.sort((a, b) => {
      // ── Minervini risk guard (applies to ALL sorts) ──────────────────
      // User policy (2026-05-25): "If anything is risky, do not put it
      // at the top of the list." Late-stage bases (#4+) are flagged risky
      // — they sink to the bottom of the list regardless of which sort
      // criterion the user picked. Within early-vs-late buckets the
      // user's sort then applies normally.
      //
      // Exception: 'symbol' (alphabetical) — A→Z ordering is fully
      // user-driven; respecting it across base stage matters more than
      // pushing risky names down. The chip is still visible.
      if (filters.sortBy !== 'symbol') {
        const aLate = a.base_count?.is_late_stage ? 1 : 0;
        const bLate = b.base_count?.is_late_stage ? 1 : 0;
        if (aLate !== bLate) return aLate - bLate; // early (0) before late (1)
      }

      // "Conviction (most return potential)" — the default. Enter-eligible
      // (is_buyable) names float to the top, then by the momentum-led conviction
      // rank (volume + dried volume + momentum, backend sepa/conviction.py).
      // A climax-top distribution name is already suppressed in the conviction
      // number, so it sinks here. 2026-06-22.
      if (filters.sortBy === 'conviction') {
        const ab = a.is_buyable ? 1 : 0;
        const bb = b.is_buyable ? 1 : 0;
        if (ab !== bb) return bb - ab;
        return (b.conviction ?? -1) - (a.conviction ?? -1);
      }
      if (filters.sortBy === 'symbol') return a.symbol.localeCompare(b.symbol);
      if (filters.sortBy === 'rs') return (b.rs_rank ?? 0) - (a.rs_rank ?? 0);
      // "Closest to trigger" — floats names nearest their pivot buy point (and
      // confirming on volume) to the top; extended/no-setup sink. See
      // lib/pivotTiming.triggerRank. The watch-list-for-today ordering.
      if (filters.sortBy === 'closest_trigger') {
        return triggerRank(pivotTiming(a)) - triggerRank(pivotTiming(b));
      }
      // "Most buyable (Enter + VCP)" — the default after-scan ordering: the
      // most actionable buys (Stage-2 VCP breaking out on volume) float to the
      // top, then Enter, then coiling VCP bases, by score. See buyabilityRank.
      if (filters.sortBy === 'most_buyable') {
        return buyabilityRank(a, pivotTiming(a)) - buyabilityRank(b, pivotTiming(b));
      }
      // Sales Confidence (Bonde/Stockbee) — highest sales-driven conviction first.
      // Names with no sales data sink (null score → -1).
      if (filters.sortBy === 'sales_confidence') {
        return (b.fundamentals?.sales?.score ?? -1) - (a.fundamentals?.sales?.score ?? -1);
      }
      if (filters.sortBy === 'day_change') {
        // Top gainers descending. Nulls land at the bottom.
        const av = a.day_change_pct ?? -Infinity;
        const bv = b.day_change_pct ?? -Infinity;
        return bv - av;
      }
      if (filters.sortBy === 'day_change_abs') {
        // Biggest movers regardless of direction (useful for spotting catalysts).
        const av = Math.abs(a.day_change_pct ?? 0);
        const bv = Math.abs(b.day_change_pct ?? 0);
        return bv - av;
      }
      // Dual Momentum sorts — descending; nulls sink to the bottom
      const dmKey: Record<string, keyof NonNullable<SepaCandidate['dual_momentum']>> = {
        dm_12m:   'return_12m',
        dm_6m:    'return_6m',
        dm_3m:    'return_3m',
        dm_1m:    'return_1m',
        dm_score: 'dm_score',
      };
      if (filters.sortBy in dmKey) {
        const k = dmKey[filters.sortBy as keyof typeof dmKey];
        const av = (a.dual_momentum?.[k] as number | null | undefined) ?? -Infinity;
        const bv = (b.dual_momentum?.[k] as number | null | undefined) ?? -Infinity;
        return (bv as number) - (av as number);
      }
      if (filters.sortBy === 'moat') {
        // Higher moat score wins. Tie-break by SEPA composite score.
        const av = a.moat?.score ?? -1;
        const bv = b.moat?.score ?? -1;
        if (bv !== av) return bv - av;
        return b.score - a.score;
      }
      if (filters.sortBy === 'pioneer') {
        // More themes = stronger pioneer signal. Tie-break by SEPA score.
        const av = a.pioneer_themes?.length ?? 0;
        const bv = b.pioneer_themes?.length ?? 0;
        if (bv !== av) return bv - av;
        return b.score - a.score;
      }
      if (filters.sortBy === 'price_asc' || filters.sortBy === 'price_desc') {
        // Sort by stock price (yesterday's close). Nulls always last so
        // missing-data rows don't poison the head of the list. Tie-break
        // by SEPA score so equal-priced names keep quality ranking.
        const av = a.last_close ?? null;
        const bv = b.last_close ?? null;
        if (av == null && bv == null) return b.score - a.score;
        if (av == null) return 1;
        if (bv == null) return -1;
        const cmp = filters.sortBy === 'price_asc' ? av - bv : bv - av;
        if (cmp !== 0) return cmp;
        return b.score - a.score;
      }

      // ── Volume / VCP sorts ───────────────────────────────────────
      // Backend `candidate.volume` (see backend/sepa/volume.py) exposes:
      //   up_down_vol_ratio : numeric  — sum(up-day vol) / sum(down-day vol)
      //                                  over last 50 bars. >1 = accumulation,
      //                                  <1 = distribution.
      //   high_vol_breakout : bool     — latest bar > 1.5× 50d avg AND
      //                                  closed above prior 22-day high.
      //   accumulation      : bool     — up_down_vol_ratio above threshold.
      //   vol_dryup         : numeric  — 10d/50d avg volume; <0.7 = drying
      //                                  up (constructive on a base RHS).
      //
      // These sorts surface volume signal the default composite-score
      // sort *dilutes* — volume contributes only 5/100, so MU's
      // top-of-list position is driven by trend template + RS, not
      // by actual volume character. Users asking "rank by volume +
      // VCP" want this view.
      const volStrength = (x: SepaCandidate): number => {
        // Composite "is this stock under institutional accumulation"
        // score. Refactored 2026-05-21 alongside the volume detector v2.
        //
        // The old version was: ratio + (breakout ? 1.0 : 0) + (accum ? 0.3 : 0)
        // — but `accumulation` tripped for 49% of universe so the +0.3
        // boost was noise, and the ratio alone misled when CMF disagreed
        // (e.g. OGN ratio 3.57 but cmf -0.23 = real distribution).
        //
        // New formula stacks the graded signals so a name with multiple
        // accumulation confirmations sorts above one with just a high
        // ratio. Distribution days subtract — Minervini's 4-distribution-
        // days rule actively penalizes the score.
        const v = x.volume;
        if (!v) return 0;
        // Hard guard (2026-05-26): a stock tagged `distributing` or with
        // money `outflow` is the LITERAL OPPOSITE of "accumulation +
        // breakout" — it shouldn't surface in this sort at all. Return
        // a very negative score so these sink to the bottom regardless
        // of how high their up/down-vol ratio is. Previously a -0.5
        // penalty was drowned out by ratios of 3+ on thin distributed
        // tickers like CPIX (ratio 3.x but accumulation=distributing →
        // ranked above truly accumulating names with lower ratios).
        if (v.accumulation_strength === 'distributing') return -100;
        if (v.cmf_signal === 'outflow')                  return -100;
        const ratio = v.up_down_vol_ratio ?? 0;
        let score = ratio;
        // Strength tier — replaces the loose binary accumulation flag.
        if (v.accumulation_strength === 'strong')        score += 1.0;
        else if (v.accumulation_strength === 'accumulating') score += 0.5;
        // Pocket pivot — Minervini's pre-breakout signal.
        if (v.pocket_pivot) score += 0.6;
        // Confirmed high-volume breakout.
        if (v.high_vol_breakout) score += 1.0;
        // Chaikin Money Flow — independent confirmation that close-position
        // weighted by volume is bullish.
        if (v.cmf_signal === 'inflow') score += 0.4;
        // Distribution-day penalty (institutional selling).
        const distDays = v.distribution_days_25 ?? 0;
        if (distDays >= 4) score -= 0.5 * (distDays - 3);  // -0.5 per dist day above 3
        return score;
      };
      const setupRank = (x: SepaCandidate): number => {
        // 2 = vcp, 1 = powerplay, 0 = neither. Higher = "more like
        // an actionable base," which is what the user wants pinned
        // at the top of the list.
        //
        // Case-normalize: backend (sepa/scanner.py) writes "VCP" and
        // "POWER_PLAY" (uppercase, with underscore) when a setup is
        // detected. Earlier code here compared to 'vcp'/'powerplay'
        // lowercase, so setupRank always returned 0 — the
        // "VCP/PowerPlay setups first" sort was silently a no-op.
        // Discovered 2026-05-21 when the current universe has 0
        // detected bases so the bug was invisible; fixed before any
        // future base shows up and ranks wrong.
        const t = (x.entry_setup?.type || '').toLowerCase().replace(/_/g, '');
        if (t === 'vcp') return 2;
        if (t === 'powerplay') return 1;
        return 0;
      };

      if (filters.sortBy === 'vol_ratio') {
        // Pure volume-strength descending — accumulation + breakout
        // signal stacked into one number. Tickers being heavily
        // accumulated rise to the top regardless of composite score.
        const av = volStrength(a);
        const bv = volStrength(b);
        if (bv !== av) return bv - av;
        return b.score - a.score;
      }
      if (filters.sortBy === 'vcp_first') {
        // VCP setups first (then PowerPlay), with score as tie-break
        // within each tier. No volume signal mixed in.
        const ar = setupRank(a);
        const br = setupRank(b);
        if (br !== ar) return br - ar;
        return b.score - a.score;
      }
      if (filters.sortBy === 'vol_vcp') {
        // Combined: VCP/PowerPlay setups pinned to the top, sorted
        // within each tier by volume strength descending, with score
        // as a final tiebreaker. The "show me the actionable bases
        // AND under-accumulation" sort.
        const ar = setupRank(a);
        const br = setupRank(b);
        if (br !== ar) return br - ar;
        const av = volStrength(a);
        const bv = volStrength(b);
        if (bv !== av) return bv - av;
        return b.score - a.score;
      }

      // Default: SEPA composite score, descending. The Minervini late-base
      // guard at the top of the sort already pushed risky names below the
      // early-base pool, so within the early-vs-late buckets the score
      // order is honest.
      return b.score - a.score;
    });
    return out;
    // whalesFlow added 2026-06-12: the gate chain reads it (whalesAccumOnly /
    // hedgeFundTopBuyer), so the list must recompute when whale 13F flow loads
    // after a scan. It was previously omitted — a latent staleness bug surfaced
    // while extracting passesSepaFilters.
  }, [source, filters, earningsMap, whalesFlow]);

  // Build a fast lookup: symbol → SepaCandidate. Used when a setup tab is
  // active to match incoming /setups/{kind} setups to the existing SEPA
  // candidate rows (the card data lives on `source`, the trigger/stop/
  // target lives on each `setup`). Built off `source` (all loaded rows)
  // because setups can reference symbols that don't pass the strict SEPA
  // gates but still have valid bases.
  const candidateBySymbol = useMemo(() => {
    const m = new Map<string, SepaCandidate>();
    for (const r of source) {
      m.set(r.symbol.toUpperCase(), r);
    }
    return m;
  }, [source]);

  // Reuse the same predicate the filter bar applies so RS slider,
  // pioneer toggle, etc. continue to gate the visible setup matches.
  // Pulled into a callback so we can apply it in two different render
  // paths (default and setup-tab) without copying the logic.
  const passesFilters = useMemo(() => {
    // Same gate chain as the main `filtered` list — both delegate to the one
    // module-level passesSepaFilters so the setup tabs (VCP / Bull Flag) and
    // the all-candidates list stay byte-for-byte identical.
    const deps = { earningsMap, whalesFlow };
    return (r: SepaCandidate): boolean => passesSepaFilters(r, filters, deps);
  }, [filters, earningsMap, whalesFlow]);

  // VCP-tab list — client-side filter on the already-loaded SEPA list.
  // Composes with the existing SepaFilterBar so RS, pioneer, etc. still
  // gate the result.
  const vcpFiltered = useMemo<SepaCandidate[]>(() => {
    if (activeTab !== 'vcp') return [];
    return filtered.filter((r) => r.vcp?.has_base === true);
  }, [activeTab, filtered]);

  // Setup-tab list — pair each fetched setup to its matching SEPA row
  // (when one exists). Filter bar predicates apply to the matched rows.
  // When a setup has no matching row in `source` we still surface a
  // minimal placeholder pair (candidate=null) so the user sees the match.
  // Dedupe the setup matches by symbol FIRST — the setup scanner can return a
  // symbol more than once (multiple sub-pattern hits), which rendered duplicate
  // cards (EVC×2, CYRX×2 …) and inflated the tab count vs what's shown.
  const dedupedSetups = useMemo<Setup[]>(() => {
    const seen = new Set<string>();
    return tabSetups.filter((s) => {
      const k = (s.symbol || '').toUpperCase();
      if (!k || seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }, [tabSetups]);

  const setupTabPairs = useMemo<Array<{ setup: Setup; candidate: SepaCandidate | null }>>(() => {
    if (!activeKind) return [];
    const q = filters.search.trim().toUpperCase();
    return dedupedSetups
      .map((s) => ({
        setup: s,
        candidate: candidateBySymbol.get(s.symbol.toUpperCase()) ?? null,
      }))
      .filter(({ setup, candidate }) => {
        // Always honor the ticker search — searching "ARM" must not leave
        // EVC/CYRX placeholders on screen.
        if (q && !setup.symbol.toUpperCase().includes(q)) return false;
        // Placeholder rows (no live SEPA candidate) bypass the data-dependent
        // filter bar — they're edge cases worth surfacing regardless.
        if (!candidate) return true;
        return passesFilters(candidate);
      });
  }, [activeKind, dedupedSetups, candidateBySymbol, passesFilters, filters.search]);

  // Tab counts — only show numbers for tabs whose data we already have.
  // `all` and `vcp` come from local data (cheap to compute always).
  // Backend-kind tabs use the cached count from useSetupsByKind so we
  // don't fan out 7 fetches just to populate badges.
  const tabCounts = useMemo<Partial<Record<SepaTab, number | null>>>(() => {
    const out: Partial<Record<SepaTab, number | null>> = {
      all: source.length,
      vcp: source.filter((r) => r.vcp?.has_base === true).length,
    };
    (Object.keys(TAB_TO_KIND) as SepaTab[]).forEach((t) => {
      const kind = TAB_TO_KIND[t];
      if (!kind) return;
      // Currently-active tab uses live state (covers the during-load case
      // where the cache hasn't been written yet but setups are in hand).
      if (t === activeTab) {
        out[t] = dedupedSetups.length;   // unique symbols, matches what renders
      } else {
        out[t] = getCachedSetupCount(kind);
      }
    });
    return out;
  }, [source, activeTab, dedupedSetups]);

  // ──────────────────────────────────────────────────────────────────────
  // Page context for ChatWidget — rich snapshot of the SEPA list page so
  // the in-app chat assistant can answer questions like:
  //   "why is NVDA not in the top 10?"
  //   "what's in the Bull Flag tab today?"
  //   "should I take FCEL?"
  //   "why are there 0 candidates?"
  //
  // Includes: active tab, filter state, universe stats, top visible names
  // with full setup context. Capped to keep system-prompt under the 4000-
  // char limit enforced by backend/chat/prompt.py.
  // ──────────────────────────────────────────────────────────────────────
  // Restore list scroll + how many cards were expanded when the user returns
  // from a detail page. Gated on a back-nav (POP) or a very recent save so a
  // fresh visit doesn't jump. Grows visibleCount first (so the target card is
  // rendered), then scrolls after paint. Runs at most once per mount.
  useEffect(() => {
    if (restoredRef.current) return;
    let saved: { y: number; vc: number; t: number } | null = null;
    try { saved = JSON.parse(sessionStorage.getItem('sepa_list_pos') || 'null'); } catch { saved = null; }
    if (!saved) { restoredRef.current = true; return; }
    const recent = Date.now() - (saved.t || 0) < 5 * 60 * 1000;
    if (!(navType === 'POP' || recent)) { restoredRef.current = true; return; }
    if (saved.vc && saved.vc > visibleCount) { setVisibleCount(saved.vc); return; } // grow, then re-run
    if (filtered.length === 0) return;                                              // wait for data
    restoredRef.current = true;
    const y = saved.y || 0;
    requestAnimationFrame(() => requestAnimationFrame(() => window.scrollTo(0, y)));
  }, [navType, visibleCount, filtered.length]);

  useEffect(() => {
    const allResults = (data as any)?.all_results || [];
    const cands = (data as any)?.candidates || [];

    // Determine which rows are CURRENTLY visible (depends on active tab).
    let visibleRows: SepaCandidate[];
    if (activeTab === 'all') {
      visibleRows = filtered;
    } else if (activeTab === 'vcp') {
      visibleRows = vcpFiltered;
    } else {
      visibleRows = setupTabPairs.map(p => p.candidate || ({
        symbol: p.setup.symbol,
      } as SepaCandidate));
    }

    const top_visible = visibleRows.slice(0, 12).map((c) => ({
      symbol:     c.symbol,
      score:      c.score,
      rating:     c.rating,
      rs_rank:    c.rs_rank,
      stage:      c.stage?.stage,
      day_pct:    c.day_change_pct,
      base_n:     c.base_count?.base_count,
      late_base:  c.base_count?.is_late_stage || false,
      has_vcp:    c.vcp?.has_base || false,
    }));

    // Setup tab counts — show only tabs that have been opened (have
    // a non-null count). Skips the "All" and "VCP" pseudo-tabs which
    // are always client-computed.
    const tab_counts: Record<string, number | null> = {};
    (Object.keys(tabCounts) as SepaTab[]).forEach((t) => {
      const v = tabCounts[t];
      if (v != null) tab_counts[t] = v;
    });

    // If on a setup tab, attach the active setup's entry/stop/target
    // for the top 5 names so the chat can answer "should I take MU?"
    let active_setups: Array<Record<string, unknown>> | undefined;
    if (activeTab !== 'all' && activeTab !== 'vcp' && setupTabPairs.length > 0) {
      active_setups = setupTabPairs.slice(0, 5).map(({ setup }) => ({
        symbol:  setup.symbol,
        trigger: setup.trigger,
        stop:    setup.stop,
        target:  setup.target,
        rr:      setup.rr,
        kind:    setup.kind,
      }));
    }

    setPageContext({
      page:             'sepa-list',
      historical_date:  historicalDate,
      universe_size:    (data as any)?.universe_size,
      analyzed_count:   allResults.length,
      candidate_count:  cands.length,
      visible_count:    visibleRows.length,
      active_setup_tab: activeTab,
      tab_counts,
      filters: {
        rating:       filters.rating,
        rs_min:       filters.rsMin,
        sort_by:      filters.sortBy,
        search:       filters.search || undefined,
        setup:        filters.setup,
        decision:     (filters.decision ?? 'ALL') !== 'ALL' ? filters.decision : undefined,
        stage:        filters.stage,
        type:         filters.type,
        moat_min:     filters.moatMin,
        pioneer_only: filters.pioneerOnly || undefined,
        show_all:     filters.showAll || undefined,
      },
      top_visible,
      active_setups,
      market_context: (data as any)?.market_context
        ? {
            label:        (data as any).market_context.label,
            safe_to_long: (data as any).market_context.safe_to_long,
          }
        : undefined,
    });
    return () => setPageContext(null);
  }, [
    data, historicalDate, activeTab, filters,
    filtered, vcpFiltered, setupTabPairs, tabCounts,
    setPageContext,
  ]);

  // Hero rail — top 5 by rating then score (always from candidates, ignores filters)
  const topPicks = useMemo<SepaCandidate[]>(() => {
    const c = ((data?.candidates as SepaCandidate[]) ?? []).slice();
    c.sort((a: SepaCandidate, b: SepaCandidate) => {
      const ra = RATING_ORDER[(a.rating ?? defaultRating(a.score)) as Rating];
      const rb = RATING_ORDER[(b.rating ?? defaultRating(b.score)) as Rating];
      if (rb !== ra) return rb - ra;
      return b.score - a.score;
    });
    return c.slice(0, 5);
  }, [data]);

  // Build the inputs for the trend provider: the full leaderboard the
  // ranking is computed against (prefer all_results so rank is honest),
  // and the current scan's date in YYYY-MM-DD ET so historical lookups
  // strictly precede it. en-CA locale produces YYYY-MM-DD; America/
  // New_York timezone matches what the backend uses to compute date_et.
  const trendCandidates = (data as any)?.all_results || (data as any)?.candidates || [];
  const trendDateEt = (data as any)?.generated_at
    ? new Date(((data as any).generated_at as number) * 1000).toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
    : null;

  return (
    <SepaTrendProvider currentCandidates={trendCandidates} currentDateEt={trendDateEt}>
    <div className="sepa-page">
      {tourOpen && <SiteTour onClose={() => setTourOpen(false)} />}
      <MarketGaugeBanner />
      {/* Secondary strips (clock + a lesson card) — hidden on phones (#5) so the
          first candidate is within a swipe; the gauge banner + hero already carry
          market status. They still render on desktop. */}
      <div className="sepa-secondary-strips">
        <MarketClockStrip />
        <MinerviniLesson />
      </div>
      <SepaBriefBanner />

      {/* Good reports the tape endorsed (Ajay 2026-06-11, ATEX lesson). */}
      <EarningsReportPicks limit={6} />

      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">Methodology</div>
          <h1 className="display sepa-page__h1" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            SEPA Screen
            <InfoButton inline title="SEPA Screen">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">
            Minervini's Specific Entry Point Analysis. Trend Template + RS + Stage 2 +
            tight base + risk-managed entry. Market-context aware.
            {' '}
            <button
              type="button"
              className="sepa-tour-btn"
              onClick={() => setTourOpen(true)}
              title="Replay the guided walkthrough of the screen"
            >🎓 Tour</button>
          </p>
          {/* Cards / Table view toggle (#6) — surfaces the sortable table that
              was previously reachable only by typing /sepa-v2. Persists choice. */}
          <div style={{ display: 'inline-flex', marginTop: '0.4rem', border: '1px solid var(--hairline,#2a2a2a)',
                        borderRadius: 8, overflow: 'hidden' }}>
            <button type="button" disabled aria-pressed="true" title="Card view (current)"
                    style={{ padding: '4px 12px', fontSize: '0.76rem', border: 'none', cursor: 'default',
                             background: 'var(--gold-faint, rgba(201,162,39,0.14))', color: 'var(--gold, #c9a227)', fontWeight: 700 }}>
              ▤ Cards
            </button>
            <button type="button" title="Switch to the sortable table — better for triaging 100+ names"
                    onClick={() => { try { localStorage.setItem('sepa_view', 'table'); } catch { /* ignore */ } navigate('/sepa-v2'); }}
                    style={{ padding: '4px 12px', fontSize: '0.76rem', border: 'none', cursor: 'pointer',
                             background: 'transparent', color: 'var(--cm-slate, #94a3b8)' }}>
              ▦ Table
            </button>
          </div>
        </div>
        {/* Universe-wide typeahead — search ANY US ticker, not just SEPA picks. */}
        <div className="sepa-page__title-search">
          <GlobalStockSearch />
        </div>
      </div>

      <SepaDateScrubber value={historicalDate} onChange={setHistoricalDate} />

      {/* Stale-while-revalidate indicator — shown only on the live view
          (historical scrubs are immutable so they don't revalidate). When
          the page is rendering from localStorage cache while a fresh fetch
          is in flight, surface "cached … refreshing" so the user knows
          the visible numbers might be a few minutes old. */}
      {!historicalDate && revalidating && cachedAt && data && (
        <div className="sepa-stale-banner mono">
          Showing cached scan from <strong>{ageHuman({ ts: cachedAt })}</strong>
          {' · '}refreshing in background…
        </div>
      )}

      <SepaHero
        data={data}
        scanning={scanning}
        onScan={(withCat, opts) => {
          // On a FULL scan (not Fast Scan), clear every filter and switch to
          // "all analyzed" so the fresh results show the whole universe with
          // no leftover filters (user 2026-05-31). Fast Scan leaves your
          // filters alone.
          if (!opts?.fast) {
            setFilters({ ...FILTER_DEFAULTS, showAll: true });
          }
          stream.start({
            fast: opts?.fast,
            mode: opts?.mode,
            with_catalyst: withCat,
          });
        }}
      />

      {/* Live progress — shown whenever a stream is in flight or has just finished */}
      {(stream.scanning || stream.phase === 'done' || stream.phase === 'error') && (
        <SepaScanProgress {...stream} />
      )}

      {topPicks.length > 0 && (
        <section className="sepa-toppicks">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.35rem' }}>
            <span className="eyebrow">Top picks</span>
            <InfoButton inline title="Top Picks">{TopPicksInfo}</InfoButton>
          </div>
          <div className="sepa-toppicks__rail">
            {topPicks.map((p) => (
              <button
                key={p.symbol}
                className={`sepa-toppick sepa-toppick--${(p.rating ?? defaultRating(p.score)).toLowerCase()}`}
                onClick={(e) => openSymbol(p.symbol, e)}
                title="Cmd/Ctrl-click to open in new tab"
              >
                <div className="sepa-toppick__sym">{p.symbol}</div>
                <div className="sepa-toppick__score">{Math.round(p.score)}</div>
                <div className="sepa-toppick__sub mono">
                  RS {p.rs_rank ?? '—'} · {p.entry_setup?.type ?? 'no setup'}
                </div>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Phase 2 — setup-category tabs. Filter the SEPA list by Minervini
          setup type (VCP / Cheat / Bull Flag / PEG / Episodic Pivot / HTF /
          etc.) ranked safest → most aggressive. "All Candidates" is the
          default and preserves the original behavior 1:1. */}
      <SepaSetupTabs
        activeTab={activeTab}
        onTabChange={setActiveTab}
        tabCounts={tabCounts}
      />

      {/* Inline info banner — explains the currently-selected setup at a
          glance. Hidden on the 'all' tab. Complements the right-side
          SepaSetupInfoPanel which has the full breakdown. */}
      <SepaSetupInfoBanner activeTab={activeTab} />

      <SepaFilterBar
        filters={filters}
        onChange={setFilters}
        onClear={() => setFilters(FILTER_DEFAULTS)}
        total={source.length}
        shown={
          activeTab === 'all'
            ? filtered.length
            : activeTab === 'vcp'
              ? vcpFiltered.length
              : setupTabPairs.length
        }
      />

      <div
        style={{
          display:        'flex',
          gap:            '1rem',
          alignItems:     'flex-start',
          flexWrap:       'wrap',
        }}
      >
        <div style={{ flex: '1 1 600px', minWidth: 0 }}>

      {activeTab === 'all' && (
        coldLoading ? (
          <SepaCardGridSkeleton n={6} />
        ) : filtered.length === 0 ? (
          <div className="sepa-empty-card">
            {filters.decision === 'ENTER' ? (
              <>
                <div className="eyebrow">🎯 Nothing to enter right now</div>
                <p>
                  No name in the <strong>{source.length}</strong> scanned clears the
                  Enter gate today by Minervini's strict rule (Stage 2 + base
                  + a same-day volume-confirmed breakout). That's normal — most days
                  there's nothing to enter. The watchlist below passed the Trend
                  Template and is worth tracking for when one fires.
                </p>
                <button
                  className="sepa-btn sepa-btn--primary"
                  style={{ marginTop: '0.6rem' }}
                  onClick={() => setFilters((f) => ({ ...f, decision: 'ALL' }))}
                >
                  👀 Show watchlist (qualifiers)
                </button>
              </>
            ) : (
              <>
                <div className="eyebrow">Nothing matches</div>
                <p>
                  None of the <strong>{source.length}</strong> scanned names match your
                  current filters{filters.search ? <> (including the ticker search “<strong>{filters.search}</strong>”)</> : null}.
                  {' '}Clear them to see the full list.
                </p>
                <button
                  className="sepa-btn sepa-btn--primary"
                  style={{ marginTop: '0.6rem' }}
                  onClick={() => setFilters(FILTER_DEFAULTS)}
                >
                  ✕ Clear all filters
                </button>
              </>
            )}
          </div>
        ) : (
          <section className="sepa-results">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.5rem' }}>
              <span className="eyebrow">Results</span>
              <InfoButton inline title="Results">{ResultsInfo}</InfoButton>
            </div>
            <div className="sepa-grid">
              {filtered.slice(0, visibleCount).map((r) => (
                <SepaCandidateCard
                  key={r.symbol}
                  row={r}
                  soir={optionsBySymbol.get(r.symbol.toUpperCase())}
                  whalesFlow={whalesFlow.get(r.symbol.toUpperCase())}
                  whales13d={whales13d.get(r.symbol.toUpperCase())}
                  livePrice={livePrices[r.symbol.toUpperCase()]}
                  cheatRegime={cheatRegime}
                  onSelect={(e) => openSymbol(r.symbol, e)}
                />
              ))}
            </div>
            {filtered.length > visibleCount && (
              <div style={{ textAlign: 'center', margin: '1rem 0' }}>
                <button
                  className="sepa-btn"
                  onClick={() => setVisibleCount((c) => c + CARD_PAGE)}
                >
                  Show {Math.min(CARD_PAGE, filtered.length - visibleCount)} more
                  {' '}· {visibleCount} of {filtered.length}
                </button>
                {filtered.length - visibleCount > CARD_PAGE && (
                  <button
                    className="sepa-btn sepa-btn--ghost"
                    style={{ marginLeft: '0.5rem' }}
                    onClick={() => setVisibleCount(filtered.length)}
                  >
                    Show all {filtered.length}
                  </button>
                )}
              </div>
            )}
          </section>
        )
      )}

      {activeTab === 'vcp' && (
        coldLoading ? (
          <SepaCardGridSkeleton n={6} />
        ) : vcpFiltered.length === 0 ? (
          <div className="sepa-empty-card">
            <div className="eyebrow">No {tabLabel(activeTab)} setups</div>
            <p>
              No {tabLabel(activeTab)} setups today. Common reasons: regime is
              cautious, no symbols meet the strict pattern requirements, or
              the scanner hasn't run yet (refreshes nightly at 6:40–7:00 PM ET).
            </p>
          </div>
        ) : (
          <section className="sepa-results">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.5rem' }}>
              <span className="eyebrow">Results</span>
              <InfoButton inline title="Results">{ResultsInfo}</InfoButton>
            </div>
            <div className="sepa-grid">
              {vcpFiltered.map((r) => (
                <SepaCandidateCard
                  key={r.symbol}
                  row={r}
                  soir={optionsBySymbol.get(r.symbol.toUpperCase())}
                  whalesFlow={whalesFlow.get(r.symbol.toUpperCase())}
                  whales13d={whales13d.get(r.symbol.toUpperCase())}
                  livePrice={livePrices[r.symbol.toUpperCase()]}
                  cheatRegime={cheatRegime}
                  onSelect={(e) => openSymbol(r.symbol, e)}
                />
              ))}
            </div>
          </section>
        )
      )}

      {activeTab !== 'all' && activeTab !== 'vcp' && (
        tabLoading ? (
          <SepaCardGridSkeleton n={6} />
        ) : tabError ? (
          <div className="sepa-empty-card">
            <div className="eyebrow">Couldn't load setups</div>
            <p style={{ color: '#fca5a5' }}>{tabError}</p>
          </div>
        ) : setupTabPairs.length === 0 ? (
          <div className="sepa-empty-card">
            <div className="eyebrow">No {tabLabel(activeTab)} setups</div>
            <p>
              No {tabLabel(activeTab)} setups today. Common reasons: regime is
              cautious, no symbols meet the strict pattern requirements, or
              the scanner hasn't run yet (refreshes nightly at 6:40–7:00 PM ET).
            </p>
          </div>
        ) : (
          <section className="sepa-results">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.5rem' }}>
              <span className="eyebrow">Results</span>
              <InfoButton inline title="Results">{ResultsInfo}</InfoButton>
            </div>
            <div className="sepa-grid">
              {setupTabPairs.map(({ setup, candidate }) => {
                const sym = setup.symbol.toUpperCase();
                if (candidate) {
                  return (
                    <SepaCandidateCard
                      key={candidate.symbol}
                      row={candidate}
                      soir={optionsBySymbol.get(sym)}
                      whalesFlow={whalesFlow.get(sym)}
                      whales13d={whales13d.get(sym)}
                      livePrice={livePrices[sym]}
                      setupOverlay={<SetupOverlayStrip setup={setup} />}
                      cheatRegime={cheatRegime}
                      onSelect={(e) => openSymbol(candidate.symbol, e)}
                    />
                  );
                }
                // Placeholder when the setup's symbol isn't in the
                // currently-loaded SEPA source array — surface the match
                // anyway so the user knows the scanner saw it.
                return (
                  <div
                    key={setup._id || setup.symbol}
                    className="sepa-card-with-overlay"
                  >
                    <SetupOverlayStrip setup={setup} />
                    <article
                      className="sepa-card"
                      role="button"
                      tabIndex={0}
                      onClick={(e) => openSymbol(setup.symbol, e)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') openSymbol(setup.symbol);
                      }}
                      title="Cmd/Ctrl-click to open in new tab"
                      style={{ cursor: 'pointer' }}
                    >
                      <header className="sepa-card__head">
                        <div className="sepa-card__sym">
                          <div className="sepa-card__sym-line">
                            <strong>{setup.symbol}</strong>
                          </div>
                          <div
                            className="sepa-card__name"
                            style={{ color: '#9a9aa3', fontSize: '0.78rem', marginTop: 4 }}
                          >
                            Setup match — no live SEPA row loaded for this symbol
                          </div>
                        </div>
                      </header>
                    </article>
                  </div>
                );
              })}
            </div>
          </section>
        )
      )}

        </div>
        <SepaSetupInfoPanel activeTab={activeTab} />
      </div>

    </div>
    </SepaTrendProvider>
  );
}
