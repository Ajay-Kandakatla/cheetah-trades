import { useEffect, useMemo, useState, Suspense } from 'react';
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { fetchSepaCandidate, addToWatchlist, planPosition, useSepaCandidate } from '../hooks/useSepa';
import { resolveBack } from '../lib/navSource';
// Supply/demand + flow chips — ported from the SEPA list card so the
// single-ticker research view has the same 🐋 whales / 📋 SEC / conviction /
// political / 🌍 macro / insider+valuation surface (user 2026-05-30:
// "add whales and other chips into this in the details").
import { useWhalesFlow } from '../hooks/useWhalesFlow';
import { useWhales13DFlow } from '../hooks/useWhales13DFlow';
import { SepaConvictionChip, computeConviction } from '../components/SepaConvictionChip';
const RankTrendChart = lazyWithReload(() => import('../components/RankTrendChart').then(m => ({ default: m.RankTrendChart })));
import { InsiderFilingTimeline } from '../components/InsiderFilingTimeline';
import { EarningsQualityPanel } from '../components/EarningsQualityPanel';
import { SalesPanel } from '../components/SalesPanel';
import { BuyVerdictPanel } from '../components/BuyVerdictPanel';
import { CheetahVerdictPanel } from '../components/CheetahVerdictPanel';
const BreakoutHistoryBody = lazyWithReload(() => import('../components/BreakoutHistoryModal').then(m => ({ default: m.BreakoutHistoryBody })));
import { NewsReadButton } from '../components/NewsReadButton';
import type { ChartInterval } from '../components/LiveCandlesChart';
const LiveCandlesChart = lazyWithReload(() => import('../components/LiveCandlesChart').then(m => ({ default: m.LiveCandlesChart })));
import { ChartReadingGuide } from '../components/ChartReadingGuide';
import { DelistedBanner } from '../components/DelistedBanner';
import { LivePriceTag } from '../components/LivePriceTag';
import { SepaPoliticalChip } from '../components/SepaPoliticalChip';
import { getPoliticalChipFlags } from '../lib/politicalDisclosures';
import { CardEnrichmentChips } from '../components/CardEnrichmentChips';
import type { SignalKind } from '../components/SignalDrillModal';
const WhalesFlowModal = lazyWithReload(() =>
  import('../components/WhalesFlowModal').then(m => ({ default: m.WhalesFlowModal })),
);
const Whales13DModal = lazyWithReload(() =>
  import('../components/Whales13DModal').then(m => ({ default: m.Whales13DModal })),
);
const MacroContextModal = lazyWithReload(() =>
  import('../components/MacroContextModal').then(m => ({ default: m.MacroContextModal })),
);
const SignalDrillModal = lazyWithReload(() =>
  import('../components/SignalDrillModal').then(m => ({ default: m.SignalDrillModal })),
);
import { ageHuman } from '../lib/swrCache';
import { TradePlanPanel } from '../components/TradePlanPanel';
import { PivotMeter } from '../components/PivotMeter';
import { VolumeTrend } from '../components/VolumeTrend';
import { BreakoutStats } from '../components/BreakoutStats';
import { FloatTurnover } from '../components/FloatTurnover';
import { LiveGateStrip } from '../components/LiveGateStrip';
import { SepaWhyBuy } from '../components/SepaWhyBuy';
import { SepaSignalChips } from '../components/SepaSignalChips';
import { StopsPanel } from '../components/StopsPanel';
import { EntryExitPlanBlock } from '../components/EntryExitPlanBlock';
import { pivotTiming } from '../lib/pivotTiming';
import { SepaScoreBar } from '../components/SepaScoreBar';
import { SepaTrendDots } from '../components/SepaTrendDots';
import { InfoButton } from '../components/InfoButton';
import { GlobalStockSearch } from '../components/GlobalStockSearch';
const StockAnalysisPanel = lazyWithReload(() => import('../components/StockAnalysisPanel').then(m => ({ default: m.StockAnalysisPanel })));
import { CompanyHeadline } from '../components/CompanyHeadline';
const ChatterPanel = lazyWithReload(() => import('../components/ChatterPanel').then(m => ({ default: m.ChatterPanel })));
const TickerPatternPanel = lazyWithReload(() => import('../components/TickerPatternPanel').then(m => ({ default: m.TickerPatternPanel })));
const ChartAnalysisPanel = lazyWithReload(() => import('../components/ChartAnalysisPanel').then(m => ({ default: m.ChartAnalysisPanel })));
import { PriceAlertModal } from '../components/PriceAlertModal';
import { TickerAlertPresets } from '../components/TickerAlertPresets';
const DependencyGraph = lazyWithReload(() => import('../components/DependencyGraph').then(m => ({ default: m.DependencyGraph })));
import { CompanyAbout } from '../components/CompanyAbout';
const GabbarLevels = lazyWithReload(() => import('../components/GabbarLevels').then(m => ({ default: m.GabbarLevels })));
import { useLiveQuote } from '../hooks/useLiveQuote';
import { CandleAnatomyExplainer } from '../components/CandleAnatomyExplainer';
import { NodeThesisPanel } from '../components/NodeThesisPanel';
import { useTickerSupplyDemand } from '../hooks/useSupplyDemand';
import type { TickerContext } from '../hooks/useSupplyDemand';
// Per-ticker options-flow read — Schaeffer SOIR snapshot + 90-day P/C
// trajectory. Added 2026-05-22 as a tab so the user can see what the
// options crowd is doing on the ticker they're researching, not just on
// the multi-ticker /options page.
import { OptionsFlowPanel } from '../components/OptionsFlowPanel';
import { TomorrowBiasBlock } from '../components/TomorrowBias';
import { OpExPanel } from '../components/OpExPanel';
// GEX+VEX best-case lens for the Setup tab (Ajay 2026-07-17).
import { GexSetupLens } from '../components/GexSetupLens';
import { ZoneMap } from '../components/ZoneMap';
import { TapePanel } from '../components/TapePanel';
import { API } from '../lib/apiBase';
import { leveragedEtfInfo } from '../lib/leveragedEtf';
import { useOwnedPosition } from '../hooks/useOwnedPositions';

const TREND_LABEL: Record<string, { label: string; help: string }> = {
  price_above_ma150_and_ma200: {
    label: 'Price above 150-day & 200-day Moving Average (MA)',
    help: 'Closing price is above both the 150-day and 200-day Moving Averages (MA) — confirms an intermediate and long-term uptrend.',
  },
  ma150_above_ma200: {
    label: '150-day MA above 200-day MA',
    help: 'The intermediate-term Moving Average (MA) is above the long-term MA — bullish ordering. "MA" is just an average of the closing price over the last N days.',
  },
  ma200_trending_up: {
    label: '200-day MA trending up',
    help: 'The 200-day Moving Average is rising over the last month — the long-term trend itself is up, not just the spot price.',
  },
  ma50_above_ma150_above_ma200: {
    label: '50-day > 150-day > 200-day MA',
    help: 'All three key Moving Averages are stacked in proper Stage 2 order — short above intermediate above long.',
  },
  price_above_ma50: {
    label: 'Price above 50-day MA',
    help: 'Closing price is above the 50-day Moving Average — short-term trend is also intact.',
  },
  at_least_30pct_above_52w_low: {
    label: 'At least 30% above 52-week low',
    help: 'Stock has already lifted at least 30% off its yearly low — meaning it has begun its advance, not just basing at the bottom.',
  },
  within_25pct_of_52w_high: {
    label: 'Within 25% of 52-week high',
    help: 'Stock is close enough to its yearly high to be a real breakout candidate, not a deep recovery play.',
  },
  rs_rank_at_least_70: {
    label: 'Relative Strength (RS) rank ≥ 70',
    help: 'Outperforming at least 70% of the market over the last 12 months. RS = Relative Strength rank, percentile-scored 1–99. This is Minervini\'s minimum bar.',
  },
};

const STAT_HELP: Record<string, string> = {
  Stage: 'Stan Weinstein\'s 4-stage cycle: Stage 1 Basing → Stage 2 Advancing → Stage 3 Topping → Stage 4 Declining. Only Stage 2 is a buy candidate.',
  RS: 'Relative Strength (RS) rank — percentile vs the entire market over 12 months. 99 = top 1% of all stocks. Need RS ≥ 70 to qualify as a SEPA candidate.',
  ADR: 'Average Daily Range (ADR) — the typical daily move as a percentage of price. Higher ADR means more volatility (more profit potential, more risk).',
  '$ vol': 'Average daily dollar volume traded (share price × shares traded). A liquidity check — too low and you can\'t enter or exit cleanly.',
};

const PageInfo = (
  <>
    <p>
      <strong>Stock detail view</strong> — everything the SEPA (Specific Entry Point Analysis)
      scanner found about this ticker, plus a position-sizing calculator.
    </p>
    <p>
      The big number is the <strong>composite score</strong> (0–100): a blend of
      trend strength, Relative Strength (RS) rank, base quality, fundamentals,
      and any near-term catalyst.
    </p>
    <p>
      <strong>Acronyms used on this page:</strong> SEPA = Specific Entry Point
      Analysis · RS = Relative Strength · MA = Moving Average · ADR = Average
      Daily Range · VCP = Volatility Contraction Pattern · CANSLIM = O'Neil's
      Current quarterly EPS / Annual EPS / New highs / Supply &amp; demand /
      Leader / Institutional sponsorship / Market direction · EPS = Earnings Per
      Share · TTM = Trailing 12 Months · ROE = Return on Equity · IPO = Initial
      Public Offering.
    </p>
  </>
);

type Tab = 'chart' | 'setup' | 'analysis' | 'trend' | 'breakout' | 'ranking' | 'fundamentals' | 'catalyst' | 'insider' | 'smartmoney' | 'chatter' | 'supply' | 'options' | 'tape';

// The active tab lives in the URL (?tab=insider) so it survives reload, back/
// forward, and deep-links from cards — instead of always snapping to 'chart'.
// We also accept the legacy #hash deep-links some chips still emit.
// 'analysis' moved up to 3rd (Ajay 2026-06-16: "move the analysis tab closer")
// and now leads with the Minervini+Bonde buy verdict and folds in the Sales tab.
const TABS: Tab[] = ['chart', 'setup', 'analysis', 'trend', 'breakout', 'ranking', 'fundamentals', 'options', 'tape', 'catalyst', 'insider', 'smartmoney', 'chatter', 'supply'];
const HASH_TO_TAB: Record<string, Tab> = {
  chart: 'chart', setup: 'setup', trend: 'trend', breakout: 'breakout', ranking: 'ranking',
  fundamentals: 'fundamentals', analysis: 'analysis', options: 'options',
  tape: 'tape', orderflow: 'tape',
  catalyst: 'catalyst', insider: 'insider', smartmoney: 'smartmoney',
  chatter: 'chatter', supply: 'supply',
  // legacy hashes that don't map 1:1 to a tab → nearest sensible tab.
  // 'sales' merged into 'analysis' (Ajay 2026-06-16) — old deep-links redirect.
  sales: 'analysis',
  volume: 'breakout', 'dual-momentum': 'ranking',
};

const SmartMoneyInfo = (
  <>
    <p>
      <strong>Smart Money &amp; Sentiment</strong> — three independent lanes
      telling you what credentialed analysts and credible commentators think
      about this name.
    </p>
    <ul>
      <li>
        <strong>Analyst consensus</strong> — Wall Street ratings + price
        targets from Finnhub. Look at the bullish % <em>and</em> the
        Month-over-Month (MoM) delta — a flat 60% bullish that just dropped
        from 80% is a tell.
      </li>
      <li>
        <strong>Curated commentary</strong> — body-text matches against a
        small allowlist of credible finance blogs (Aswath Damodaran, Bespoke
        Investment Group, Morningstar). Most names will have zero hits —
        that's expected.
      </li>
      <li>
        <strong>Reddit discussion</strong> — top-scored threads from a
        five-subreddit allowlist (r/SecurityAnalysis, r/ValueInvesting,
        r/investing, r/stocks, r/options). r/wallstreetbets is skipped by
        design.
      </li>
    </ul>
    <p className="sepa-note">
      Note: 13F institutional-holdings data is intentionally <em>excluded</em>.
      A 13F is the quarterly SEC filing where institutions ($100M+ in assets
      under management) disclose their long positions. The 45-day filing lag
      and the empirical track record of 13F-clone strategies make 13F net-
      misleading on a 1–12 week swing-trading timeframe.
    </p>
  </>
);

// Hardcoded TradingView prefix overrides for foreign ADRs and dual-listed
// names where Massive / Finnhub's exchange-name string isn't reliable.
// E.g. ASML's profile is sometimes returned with "NEW YORK STOCK EXCHANGE"
// even though it actually trades on NASDAQ (ASML on Nasdaq Global Select).
// Without this override TradingView gets `NYSE:ASML` and shows
// "This symbol doesn't exist".
const TV_SYMBOL_OVERRIDES: Record<string, string> = {
  // European tech
  ASML: 'NASDAQ:ASML',
  ARM:  'NASDAQ:ARM',
  // European telecom / Nordics — NOK (Nokia, Finnish) trades on NYSE.
  // Profile lookup sometimes returns NASDAQ for legacy reasons and trips
  // TradingView's "This symbol doesn't exist" empty state.
  NOK:  'NYSE:NOK',
  ERIC: 'NASDAQ:ERIC',  // Ericsson (Swedish ADR)
  // Chinese ADRs
  BABA: 'NYSE:BABA',
  JD:   'NASDAQ:JD',
  PDD:  'NASDAQ:PDD',
  BIDU: 'NASDAQ:BIDU',
  NTES: 'NASDAQ:NTES',
  NIO:  'NYSE:NIO',
  XPEV: 'NYSE:XPEV',
  LI:   'NASDAQ:LI',
  // Asian / other ADRs
  TSM:  'NYSE:TSM',
  SONY: 'NYSE:SONY',
  TM:   'NYSE:TM',
  HMC:  'NYSE:HMC',
  // European pharma
  NVO:  'NYSE:NVO',
  NVS:  'NYSE:NVS',
  AZN:  'NASDAQ:AZN',
  GSK:  'NYSE:GSK',
  // Misc
  SE:   'NYSE:SE',
  SHOP: 'NYSE:SHOP',
  SAP:  'NYSE:SAP',
};

function tvSymbolFor(symbol: string, exchange?: string): string {
  const upperSym = (symbol || '').toUpperCase();
  // Check known-bad-data override first
  if (TV_SYMBOL_OVERRIDES[upperSym]) return TV_SYMBOL_OVERRIDES[upperSym];

  const ex = (exchange || '').toUpperCase();
  // Massive / Finnhub return the full exchange name ("NEW YORK STOCK EXCHANGE,
  // INC.", "NASDAQ GLOBAL SELECT MARKET", "NYSE AMERICAN", etc.). Match on
  // both the abbreviation and the full name so we don't mis-route a NYSE-
  // listed ticker (like ALB) to NASDAQ — that triggers TradingView's
  // "This symbol doesn't exist" empty state.
  // IMPORTANT: NASDAQ check goes BEFORE NYSE so a string like
  // "NASDAQ NMS" doesn't accidentally match the broader NYSE patterns.
  if (ex.includes('NASDAQ')) return `NASDAQ:${symbol}`;
  if (ex.includes('NYSE AMERICAN') || ex.includes('AMEX')) return `AMEX:${symbol}`;
  if (ex.includes('NEW YORK STOCK EXCHANGE') || ex.includes('NYSE ARCA') ||
      ex.startsWith('NYSE')) return `NYSE:${symbol}`;
  if (ex.includes('CBOE') || ex.includes('BATS')) return `BATS:${symbol}`;
  // Unknown exchange — let TradingView's symbol-search auto-resolve it.
  // Returning bare symbol is safer than a wrong prefix.
  return symbol;
}

import { usePageContext } from '../hooks/usePageContext';
import { lazyWithReload } from '../lib/lazyWithReload';

const PivotFrameworkInfo = (
  <>
    <p>
      The <strong>pivot</strong> is the buy trigger — the high of the base's final
      tight contraction (Minervini pp.&nbsp;198–205). You buy when price crosses
      <em> above</em> the pivot on <strong>expanding volume</strong> (≥&nbsp;1.5× the
      50-day average, p.&nbsp;203), within about 1–2% of it.
    </p>
    <ul>
      <li><strong>Entry zone</strong> — pivot up to ~2.5% above. Past that = extended, don't chase.</li>
      <li><strong>Stop</strong> — ~7–8% below entry; cut losses fast (Ch.&nbsp;10–11).</li>
      <li><strong>No trigger, no entry</strong> — below the pivot, or above it on light volume → wait.</li>
    </ul>
    <p>
      The gauge shows where price sits (stop · pivot · buy-zone), today's volume vs
      the 1.5× line, and a plain-English read of what to wait for.{' '}
      <em>Educational, not advice.</em>
    </p>
  </>
);

export function SepaCandidatePage() {
  const { symbol = '' } = useParams<{ symbol: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  // Page-context registration so the floating Claude widget can ground
  // "what's this stock doing?" type questions in the actual candidate
  // data. Compact snapshot only — we send a JSON blob to the backend
  // on every chat turn, so trimming the noise keeps token costs sane.
  const { setPageContext } = usePageContext();
  // Source-tracking: when a caller passes navigate('/sepa/X', { state: { from, label } })
  // we render a contextual "← Back to Catalysts" button. Otherwise nav(-1)
  // works via browser history for the generic case.
  // `backSource` is resolved below, once searchParams exists — the source also
  // rides in ?from= so it survives a tab switch (which replaces the history
  // entry and drops state) and a reload. See lib/navSource.ts.
  const navState = (location.state as { from?: string; label?: string } | null) || null;
  // SWR-backed detail fetch — page renders cached data instantly while
  // revalidating in the background. Navigating MU → AAPL → MU brings the
  // cached MU view back without a flash of "Loading…".
  const {
    data,
    cachedAt,
    revalidating: detailRevalidating,
    error: detailError,
    setFresh: setData,
  } = useSepaCandidate(symbol);
  const err = detailError;
  // The non-data state was previously bundled into the same `data` slot
  // and reset on every symbol switch. We split out the per-symbol panels
  // so they reset cleanly while `data` itself is owned by the SWR hook.
  const [plan, setPlan] = useState<any>(null);
  const [accountSize, setAccountSize] = useState(100000);
  const [riskPct, setRiskPct] = useState(1);
  // Active tab is derived from the URL: ?tab= wins, then a legacy #hash, else
  // 'chart'. Switching tabs rewrites ?tab= in place (replace, no history spam)
  // so a reload or a shared link lands on the same tab.
  const [searchParams, setSearchParams] = useSearchParams();
  const backSource = resolveBack(navState, searchParams.get('from'),
                                 searchParams.get('from_q'));
  const handleBack = () => {
    if (backSource) navigate(backSource.path);
    else if (window.history.length > 1) navigate(-1);
    else navigate('/sepa');
  };
  const backLabel = backSource ? `← Back to ${backSource.label}` : '← Back';
  const tabParam = searchParams.get('tab');
  const hashKey = (location.hash || '').replace(/^#/, '').toLowerCase();
  const tab: Tab = TABS.includes(tabParam as Tab)
    ? (tabParam as Tab)
    : (HASH_TO_TAB[hashKey] ?? 'chart');
  const setTab = (t: Tab) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', t);
      return next;
      // `state` must be passed explicitly: setSearchParams drops it otherwise,
      // which used to make the first tab click forget the calling page.
    }, { replace: true, state: location.state });
  };
  const [added, setAdded] = useState(false);
  const [rescanState, setRescanState] = useState<'idle' | 'running' | 'error'>('idle');
  const [rescanMsg, setRescanMsg] = useState<string | null>(null);
  const [alertOpen,  setAlertOpen]  = useState(false);
  const [presetOpen, setPresetOpen] = useState(false);
  const [alertConfirm, setAlertConfirm] = useState<string | null>(null);

  // ── Supply/demand + flow chips (ported from the SEPA list card) ──────────
  // Bulk hooks return Map<ticker, row> and are shared (module-cached) with
  // the list page, so looking up this one symbol matches the card exactly.
  const whalesFlowMap = useWhalesFlow();
  const whales13dMap  = useWhales13DFlow();
  const symU          = symbol ? symbol.toUpperCase() : '';
  const whalesFlow    = symU ? whalesFlowMap.get(symU) : undefined;
  const whales13d     = symU ? whales13dMap.get(symU) : undefined;
  const [whalesOpen,    setWhalesOpen]    = useState(false);
  const [whales13dOpen, setWhales13dOpen] = useState(false);
  const [macroOpen,     setMacroOpen]     = useState(false);
  const [openSignal,    setOpenSignal]    = useState<SignalKind | null>(null);

  // Drill payload for the conviction / political chips — mirrors the card's
  // `signalData` projection so the shared SignalDrillModal shows identical
  // numbers regardless of whether the user came from the list or a search.
  const signalData = useMemo(() => {
    const r: any = (data as any)?.base ?? null;
    if (!r) return null;
    const conv = computeConviction(r, whalesFlow);
    const pol  = getPoliticalChipFlags(r.symbol);
    return {
      symbol: r.symbol,
      // conviction (whales + volume) inputs
      conviction_tier:         conv.tier,
      conviction_label:        conv.label,
      conviction_combined:     conv.combined,
      conviction_whale_score:  conv.whaleScore,
      conviction_vol_score:    conv.volScore,
      conviction_whale_reason: conv.whaleReason,
      conviction_vol_reason:   conv.volReason,
      conviction_summary:      conv.summary,
      conviction_disagrees:    conv.disagrees,
      // volume context shared by several drills
      up_down_vol_ratio:       r.volume?.up_down_vol_ratio ?? null,
      accumulation_strength:   r.volume?.accumulation_strength ?? null,
      cmf_20:                  r.volume?.cmf_20 ?? null,
      cmf_signal:              r.volume?.cmf_signal ?? null,
      distribution_days_25:    r.volume?.distribution_days_25 ?? null,
      accumulation_days_25:    r.volume?.accumulation_days_25 ?? null,
      net_dollar_vol_50:       r.volume?.net_dollar_vol_50 ?? null,
      score:                   r.score ?? null,
      rating:                  r.rating ?? null,
      rs_rank:                 r.rs_rank ?? null,
      stage_num:               r.stage?.stage ?? null,
      stage_label:             r.stage?.label ?? null,
      // Score-component fields — needed so computeScoreBreakdown (the
      // "What's moving the rank" block + the score_breakdown drill) can
      // reconstruct the FULL composite (Trend +30, Setup +15, fundamentals,
      // ADR/liquidity tiers), not just the volume/conviction slice. Mirrors
      // SepaCandidateCard's signalData projection so the detail page shows the
      // same breakdown as the list card (2026-06-09 card↔detail parity).
      trend_passed:            r.trend?.passed ?? null,
      trend_checks:            r.trend?.checks ?? null,
      fundamentals_passed:     r.fundamentals?.passed ?? null,
      adr_pct:                 r.adr_pct ?? null,
      base_count_n:            r.base_count?.base_count ?? null,
      base_count_is_late:      r.base_count?.is_late_stage ?? null,
      setup_type:              r.entry_setup?.type ?? null,
      setup_pivot:             r.entry_setup?.pivot ?? null,
      setup_stop:              r.entry_setup?.stop ?? null,
      liquidity_liquid:        r.liquidity?.liquid ?? null,
      avg_dollar_vol:          r.liquidity?.avg_dollar_vol ?? null,
      high_vol_breakout:       r.volume?.high_vol_breakout ?? null,
      pocket_pivot:            r.volume?.pocket_pivot ?? null,
      last_close:              r.last_close ?? null,
      // political-disclosure context (empty unless on the curated list)
      ...(pol.entry ? {
        political_categories:  pol.entry.categories,
        political_band:        pol.entry.disclosureBand ?? null,
        political_company:     pol.entry.company,
        political_sector:      pol.entry.sector,
        political_notes:       pol.entry.notes ?? null,
        political_is_inferred: pol.isInferred && !pol.hasPotusFamily && !pol.hasGovtInvestment && !pol.hasGovtContractor,
      } : {}),
    };
  }, [data, whalesFlow]);

  // Reset the per-symbol UI bits when the symbol changes. `data` is
  // managed by the hook above (which keeps stale across navigations).
  useEffect(() => {
    setPlan(null);
    setAdded(false);
    // Tab is URL-driven now — navigating to a new symbol without ?tab= lands on
    // 'chart' automatically; a deep-link with ?tab= is honoured. No reset here.
    setRescanState('idle');
    setRescanMsg(null);
    setAlertOpen(false);
    setAlertConfirm(null);
    setWhalesOpen(false);
    setWhales13dOpen(false);
    setMacroOpen(false);
    setOpenSignal(null);
  }, [symbol]);

  // Register page context for the ChatWidget. Re-runs when the candidate
  // data refreshes so Claude always sees the live snapshot. We send a
  // CONDENSED projection — full SEPA candidate objects can be 30+
  // nested fields, but Claude only needs the trade-relevant ones to
  // ground its answers. Adding `tab` lets the user ask things like
  // "what is the catalyst tab telling me?" and Claude knows the view.
  useEffect(() => {
    if (!symbol) return;
    if (!data) {
      setPageContext({ page: 'sepa-detail', symbol, tab });
      return;
    }
    const d = data as any;
    setPageContext({
      page:           'sepa-detail',
      symbol,
      tab,
      score:          d.score,
      rating:         d.rating,
      rs_rank:        d.rs_rank,
      last_close:     d.last_close,
      day_change_pct: d.day_change_pct,
      stage:          d.stage?.label || d.stage_label,
      trend:          d.trend,
      vcp_present:    !!d.vcp,
      entry_setup:    d.entry_setup
        ? {
            type:  d.entry_setup.type,
            pivot: d.entry_setup.pivot,
            stop:  d.entry_setup.stop,
          }
        : null,
      adr_pct:        d.adr_pct,
      pioneer_themes: d.pioneer_themes,
      catalyst_summary: d.catalyst?.headline || d.catalyst?.label,
    });
    return () => setPageContext(null);
  }, [symbol, data, tab, setPageContext]);

  // Rescan a single ticker. The backend POST /sepa/analyze/{symbol} runs full
  // SEPA analysis (price refresh + trend template + stage + VCP + Power Play +
  // base count + ADR + liquidity), and with `?with_catalyst=true` also fetches
  // CANSLIM fundamentals + earnings catalyst + insider activity. The result
  // is persisted into the latest scan, so reloading SepaCandidate picks it up.
  const rescan = async (withCatalyst: boolean) => {
    if (!symbol) return;
    setRescanState('running');
    setRescanMsg(withCatalyst ? 'Re-scanning with catalyst + fundamentals…' : 'Re-scanning…');
    try {
      const params = withCatalyst ? '?with_catalyst=true' : '';
      const r = await fetch(`${API}/sepa/analyze/${encodeURIComponent(symbol)}${params}`,
                            { method: 'POST' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      // Refetch the candidate so the page picks up the new fundamentals + setup
      const fresh = await fetchSepaCandidate(symbol);
      setData(fresh);
      setRescanState('idle');
      setRescanMsg(`Refreshed ${new Date().toLocaleTimeString()}`);
    } catch (e) {
      setRescanState('error');
      setRescanMsg(`Rescan failed: ${e}`);
    }
  };

  const setup = data?.base?.entry_setup;
  const base = data?.base;
  // Pivot buy framework — same gauge the leaderboard cards use, built from this
  // ticker's scan record (entry_setup / vcp / volume / stage).
  const pivotT = useMemo(() => (base ? pivotTiming(base as any) : null), [base]);
  const fetchedAt = useMemo(() => new Date(), [symbol, data]);

  // Live SSE-backed quote — subscribes to the bus, prefills from
  // /quote/<sym> on mount, and updates as ticks arrive. Anywhere we
  // previously fell back to ``data?.last_close`` for "current price"
  // (alert dialogs, Gabbar's buy-zone marker), we now prefer this so
  // the user sees the actual present-moment price instead of
  // yesterday's close. last_close stays as a fallback for tickers
  // Finnhub WS hasn't started streaming yet.
  const live = useLiveQuote(symbol);
  const ownedPos = useOwnedPosition(symbol);   // your portfolio position in this name, if any
  const currentLivePrice: number | null =
    (typeof live?.last_price === 'number' && live.last_price > 0 ? live.last_price : null)
    ?? data?.last_close
    ?? null;

  // Force-reload counter for the TradingView iframe. Incrementing this
  // changes the <iframe key>, React unmounts + remounts, and the embed
  // re-fetches its data. Useful because the free widgetembed has a
  // ~15-min delay for non-subscribers and sometimes doesn't auto-tick
  // when the tab regains focus — a manual reload is the cheap fix.
  const [chartReloadKey, setChartReloadKey] = useState(0);
  // TradingView widget is the DEFAULT chart (Ajay 2026-06-10: "for the chart
  // I wanted the trading view widget, not ours"). This is TV's free public
  // embed — no approval needed; the approval-gated Advanced Charting Library
  // stays removed. The native live chart remains behind the ● Live toggle.
  const [chartSource, setChartSource] = useState<'native' | 'tv'>('tv');
  const [chartInterval, setChartInterval] = useState<ChartInterval>('D');

  useEffect(() => {
    if (!setup || !accountSize) { setPlan(null); return; }
    planPosition({
      entry: setup.pivot, stop: setup.stop,
      account_size: accountSize, risk_per_trade_pct: riskPct,
    }).then(setPlan).catch(() => setPlan(null));
  }, [setup, accountSize, riskPct]);

  useEffect(() => {
    // Escape is the keyboard twin of the back button, so it honours the
    // calling page too rather than always dumping the user on the scanner.
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') handleBack(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // Depend on the resolved target, not on handleBack — otherwise the listener
    // keeps the first render's closure and Escape goes somewhere stale.
  }, [navigate, backSource?.path, backSource?.label]);

  const rMultiples = useMemo(() => {
    if (!setup) return null;
    const risk = setup.pivot - setup.stop;
    return {
      entry: setup.pivot, stop: setup.stop,
      twoR: setup.pivot + risk * 2,
      threeR: setup.pivot + risk * 3,
      risk,
    };
  }, [setup]);

  return (
    <div className="sepa-candidate-page">
      <div className="sepa-candidate-page__topbar">
        <button
          type="button"
          className="sepa-btn sepa-candidate-page__back"
          onClick={handleBack}
          title={backSource ? `Return to ${backSource.label}` : 'Go back'}
        >
          {backLabel}
        </button>
        <div className="sepa-candidate-page__asof mono">
          Data as of {fetchedAt.toLocaleString(undefined, {
            month: 'short', day: 'numeric',
            hour: 'numeric', minute: '2-digit',
          })}
          {/* Re-rate window — same note the list card carries in its footer, so
              the user knows when fresh ratings land (card↔detail parity 2026-06-09). */}
          <span style={{ opacity: 0.7 }}> · Re-rates after 3:00 PM CT (4:00 PM ET)</span>
          {/* Stale-while-revalidate indicator. When the page renders from
              cache and a background refresh is in flight, show a subtle
              "cached … refreshing" hint so the user knows the visible
              numbers might be a few seconds stale. */}
          {detailRevalidating && cachedAt && (
            <span className="sepa-candidate-page__stale" title="Showing cached data while a fresh fetch runs in background">
              {' · '}cached {ageHuman({ ts: cachedAt })} · refreshing…
            </span>
          )}
        </div>
      </div>

      <header className="sepa-candidate-page__head">
        <div>
          <div className="eyebrow">SEPA candidate</div>
          <h1 className="display sepa-candidate-page__sym">{symbol}</h1>
          {data?.profile?.name && (
            <div className="sepa-drawer__company">
              {data.profile.name}
              {data.profile.exchange && (
                <span className="sepa-drawer__exchange mono"> · {data.profile.exchange}</span>
              )}
              {data.profile.industry && (
                <span className="sepa-drawer__industry"> · {data.profile.industry}</span>
              )}
            </div>
          )}
          {(() => {
            const lev = leveragedEtfInfo(symbol, data?.profile?.name);
            return lev.isLeveraged ? (
              <div className="lev-warn" role="note">
                <b>⚡ {lev.label}</b> — a leveraged/inverse product, <b>not an individual stock</b>.
                SEPA/Minervini criteria (earnings, sponsorship, VCP) don't apply; it carries
                daily-rebalance volatility decay and 2–3× amplified drawdowns. The score/rank
                reflects price action only — <b>not a buy signal</b>.
              </div>
            ) : null;
          })()}
          {ownedPos && (
            <div className="sepa-owned-banner" role="note">
              📍 <strong>You own this</strong> — {ownedPos.quantity ?? '?'} sh
              {ownedPos.avg_cost != null && <> · cost ${ownedPos.avg_cost.toFixed(2)}</>}
              {ownedPos.current_price != null && <> · now ${ownedPos.current_price.toFixed(2)}</>}
              {ownedPos.pl_pct != null && (
                <span style={{ color: ownedPos.pl_pct >= 0 ? '#10b981' : '#ef4444', fontWeight: 700 }}>
                  {' · '}{ownedPos.pl_pct >= 0 ? '+' : ''}{ownedPos.pl_pct.toFixed(1)}%
                  {ownedPos.pl_dollars != null && ` ($${Math.round(ownedPos.pl_dollars).toLocaleString()})`}
                </span>
              )}
              <span className="sepa-owned-banner__hint"> · hold/sell read in Position Lens below ↓</span>
            </div>
          )}
          {base && (
            <SepaScoreBar score={base.score ?? 0} rating={base.rating} size="md" />
          )}
          {/* (#7) The list card's score-component chip row was re-rendered here —
              the depth page was opening by re-showing the card. Dropped; the score
              bar above + the 📈 ranking tab carry the breakdown. The research
              drills (whales / SEC / macro / conviction) stay below. */}
          {/* Supply/demand + flow chips — same surface as the SEPA list
              card: 🐋 13F whales, 📋 SEC activity, whales+volume conviction,
              political disclosure, 🌍 macro, and the insider-cluster +
              valuation enrichment chips. Ported 2026-05-30 so the
              single-ticker research view matches the card. */}
          {base && (
            <div className="sepa-card__flags" style={{ marginTop: '0.5rem' }}>
              {/* Whales + Volume combined conviction — the actual buy-decision
                  signal; warning tier (whales ≠ volume) pops red. */}
              <SepaConvictionChip
                row={base}
                whalesFlow={whalesFlow}
                onOpenDrill={() => setOpenSignal('conviction')}
              />
              {/* 🐋 Institutional flow from cached 13F (45-day lag). */}
              {whalesFlow && (
                <span
                  role="button" tabIndex={0}
                  className={`sepa-flag ${
                    whalesFlow.signal === 'accumulating' ? 'sepa-flag--good' :
                    whalesFlow.signal === 'distributing' ? 'sepa-flag--bad' :
                    'sepa-flag--neutral'
                  }`}
                  onClick={() => setWhalesOpen(true)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault(); setWhalesOpen(true);
                  }}}
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
              {/* 📋 Combined SEC activity — Form 4 + 144 + SC 13D/G. */}
              {whales13d && whales13d.n_filings > 0 && (
                <span
                  role="button" tabIndex={0}
                  className="sepa-flag sepa-flag--good"
                  onClick={() => setWhales13dOpen(true)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault(); setWhales13dOpen(true);
                  }}}
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
              {/* Political-disclosure chips — renders nothing off-list. */}
              <SepaPoliticalChip
                symbol={base.symbol}
                onOpenDrill={() => setOpenSignal('political_disclosure')}
              />
              {/* 🌍 Macro read — geopolitics / futures / bear case + headlines. */}
              <span
                role="button" tabIndex={0}
                className="sepa-flag sepa-flag--neutral"
                onClick={() => setMacroOpen(true)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault(); setMacroOpen(true);
                }}}
                style={{ cursor: 'pointer' }}
                title="Macro context: geopolitics, futures, bear case, sector dynamics + recent headlines. Generated by Claude, cached 6h."
              >
                🌍 Macro
                <span style={{ fontSize: '0.7em', opacity: 0.6, marginLeft: 3 }}>↗</span>
              </span>
              {/* Insider cluster-buy + valuation (under/fair/over) — self-fetch. */}
              <CardEnrichmentChips symbol={base.symbol} />
            </div>
          )}
          {/* Live price badge — pulls from the SSE bus (Finnhub WS feed)
              via useLiveQuote. This is the page's authoritative "what
              is MU trading at RIGHT NOW" — much fresher than the
              embedded TradingView iframe below which is ~15 min
              delayed for non-subscribers. Falls back to last_close
              when WS hasn't started streaming yet. */}
          {(currentLivePrice != null || live?.last_price != null) && (() => {
            const price = currentLivePrice;
            // A live tick of 0 (no trade yet / stale feed) is NOT a price — treat
            // only a positive last_price as live, otherwise fall back to the real
            // close and its day change instead of rendering $0.00. (NUE 2026-06-03:
            // feed sent last_price 0, header showed "$0.00 · -0.56% · close".)
            const isLive = typeof live?.last_price === 'number' && live.last_price > 0;
            const dayPct = isLive ? live?.day_pct : (data?.day_change_pct ?? null);
            const prev = data?.last_close;
            const source = live?._source || '';
            // Color the delta by direction; gray when no delta info.
            const deltaColor =
              dayPct == null ? 'var(--cm-slate)' :
              dayPct >= 0 ? 'var(--positive)' : 'var(--negative)';
            return (
              <div style={{
                display: 'inline-flex', alignItems: 'baseline', gap: '0.6rem',
                marginTop: '0.5rem', flexWrap: 'wrap',
              }}>
                <span className="mono" style={{ fontSize: '1.6rem', fontWeight: 700 }}>
                  ${price?.toFixed(2)}
                </span>
                {dayPct != null && (
                  <span className="mono" style={{ color: deltaColor, fontSize: '0.95rem', fontWeight: 600 }}>
                    {dayPct >= 0 ? '+' : ''}{dayPct.toFixed(2)}%
                    {prev != null && (
                      <span style={{ marginLeft: 4, color: 'var(--cm-slate)', fontSize: '0.78rem' }}>
                        (prev ${prev.toFixed(2)})
                      </span>
                    )}
                  </span>
                )}
                <span style={{
                  fontSize: '0.66rem', padding: '1px 6px',
                  borderRadius: 3, letterSpacing: '0.04em',
                  background: isLive ? 'rgba(16,185,129,0.1)' : 'rgba(120,120,120,0.1)',
                  color:      isLive ? 'var(--positive)' : 'var(--cm-slate)',
                  border:    `1px solid ${isLive ? 'rgba(16,185,129,0.3)' : 'var(--rule, #555)'}`,
                  textTransform: 'uppercase',
                }} title={`Source: ${source || 'fallback'}`}>
                  {isLive ? '● live' : '◯ close'}
                </span>
              </div>
            );
          })()}
          <CompanyHeadline symbol={symbol} />
        </div>
        <div className="sepa-candidate-page__head-actions">
          {/* Universe-wide typeahead — jump straight to any other ticker
              without having to go back to /sepa first. ⌘K focuses it from
              anywhere on the page. */}
          <GlobalStockSearch
            className="sepa-candidate-page__head-search"
            placeholder="Jump to ticker — ⌘K"
          />
          <button
            className="sepa-btn sepa-btn--ghost"
            onClick={() => setPresetOpen(true)}
            title={`Quick alert presets on ${symbol} — tap −7% / −12% / +20% etc. instead of typing a number.`}
          >
            🔔 Quick alerts
          </button>
          <button
            className="sepa-btn sepa-btn--ghost"
            onClick={() => setAlertOpen(true)}
            title={`Set a custom-level price alert on ${symbol} (type the exact price you want to be notified at).`}
          >
            ✎ Custom level
          </button>
          <button
            className="sepa-btn sepa-btn--ghost"
            onClick={() => rescan(false)}
            disabled={rescanState === 'running'}
            title={`Re-pull prices and rerun trend / stage / VCP / Power Play / DM for ${symbol}`}
          >
            {rescanState === 'running' ? '↻ Re-scanning…' : `↻ Re-scan ${symbol}`}
          </button>
          <button
            className="sepa-btn sepa-btn--ghost"
            onClick={() => rescan(true)}
            disabled={rescanState === 'running'}
            title="Re-scan AND fetch CANSLIM fundamentals + earnings catalyst + insider activity"
          >
            ↻ + catalyst
          </button>
          <InfoButton inline title={`${symbol} — How to read this`}>{PageInfo}</InfoButton>
        </div>
      </header>

      {/* Sticky category badges — Pioneer themes, ETF tag, exchange, industry.
          Anchors below the page header so when the user scrolls through the
          long-form sections (trend gates, supply/demand, chatter) they don't
          lose track of WHAT this ticker is. Position-sticky keeps the strip
          pinned to the top of the viewport once it scrolls there. Added
          2026-05-22 alongside the SepaSignalChips refactor — chips above
          tell you HOW the ticker scored, this strip tells you WHAT category
          it belongs to. */}
      {/* Ranking-component chip strip — score / trend / RS / stage / setup /
          accumulation / 🚀 hi-vol breakout / pocket pivot / money flow / dist
          days. Shared with the list card (SepaCandidateCard); documented as
          this page's "full strip right under the score bar" in
          SepaSignalChips.tsx but the wiring was lost — re-added 2026-06-16 so
          the breakout (and every other signal) chip renders here too. Self-
          contained: owns its own drill-modal state. */}
      {base && <SepaSignalChips row={base} />}

      {base && (
        <StickyCategoryBadges
          pioneerThemes={base.pioneer_themes}
          isEtf={base.is_etf}
          etfCategory={base.etf_data?.category ?? null}
          exchange={data?.profile?.exchange ?? null}
          industry={data?.profile?.industry ?? null}
        />
      )}

      {alertConfirm && (
        <div className="sepa-rescan-status">{alertConfirm}</div>
      )}
      {presetOpen && (
        <TickerAlertPresets
          symbol={symbol}
          currentPrice={currentLivePrice ?? base?.entry_setup?.pivot ?? null}
          onClose={() => setPresetOpen(false)}
          onCustomLevel={() => setAlertOpen(true)}
        />
      )}
      {alertOpen && (
        <PriceAlertModal
          symbol={symbol}
          currentPrice={currentLivePrice ?? base?.entry_setup?.pivot ?? null}
          onClose={() => setAlertOpen(false)}
          onCreated={() => {
            setAlertConfirm(`✓ Alert set on ${symbol} — you'll be notified when the trigger fires.`);
            // auto-clear the confirmation after 6s
            setTimeout(() => setAlertConfirm(null), 6000);
          }}
        />
      )}
      {/* Flow-chip modals — lazy, self-contained (fetch by symbol). */}
      {whalesOpen && symbol && (
        <Suspense fallback={null}>
          <WhalesFlowModal symbol={symbol} onClose={() => setWhalesOpen(false)} />
        </Suspense>
      )}
      {whales13dOpen && symbol && (
        <Suspense fallback={null}>
          <Whales13DModal symbol={symbol} onClose={() => setWhales13dOpen(false)} />
        </Suspense>
      )}
      {macroOpen && symbol && (
        <Suspense fallback={null}>
          <MacroContextModal symbol={symbol} onClose={() => setMacroOpen(false)} />
        </Suspense>
      )}
      {openSignal && signalData && (
        <Suspense fallback={null}>
          <SignalDrillModal
            kind={openSignal}
            data={signalData}
            onClose={() => setOpenSignal(null)}
          />
        </Suspense>
      )}
      {rescanMsg && rescanState !== 'running' && (
        <div className={`sepa-rescan-status ${rescanState === 'error' ? 'sepa-warn' : ''}`}>
          {rescanMsg}
        </div>
      )}

      {err && <p className="sepa-err">{err}</p>}
      {!data && !err && (
        <div className="sepa-drawer__loading">
          <div className="eyebrow">Loading</div>
          <div className="sepa-loading__dots"><span /><span /><span /></div>
        </div>
      )}

      {data && (
        <>
          {/* Page-level instruction banner (Ajay 2026-06-22) — replaces the
              Position Lens here. Sits ABOVE the tab bar so the "how to read
              this page" guidance shows on EVERY tab, not just one. The hold/
              sell evaluator lives on the Portfolio page (where you hold real
              positions); this research page is for the buy decision. */}
          <div className="sepa-tab-help">
            <strong>{symbol}</strong> — the full Minervini SEPA read. The chips above are the
            scorecard: <strong>Trend Template</strong> (8 criteria, p.79), market stage,
            RS rank, your <strong>VCP / Power-Play</strong> setup, ADR and distribution days.
            Each tab below opens one lens — chart, setup, the buy/sell{' '}
            <strong>analysis</strong> verdict, trend, breakout history, ranking, fundamentals
            and more; every tab explains itself at the top.
          </div>

          <nav className="sepa-tabs" role="tablist">
            {(['chart', 'setup', 'analysis', 'trend', 'breakout', 'ranking', 'fundamentals', 'options', 'tape', 'catalyst', 'insider', 'smartmoney', 'chatter', 'supply'] as Tab[]).map((t) => (
              <button
                key={t}
                role="tab"
                className={`sepa-tab ${tab === t ? 'is-active' : ''}`}
                onClick={() => setTab(t)}
              >{t === 'smartmoney' ? 'smart money' : t === 'supply' ? 'supply / demand' : t === 'options' ? '📊 options flow' : t === 'tape' ? '🧾 tape' : t === 'ranking' ? '📈 ranking' : t === 'analysis' ? '✅ analysis' : t === 'breakout' ? '🚀 breakout' : t}</button>
            ))}
          </nav>

          {/* "What this company does" — yfinance summary, cached 30d. Shown
              once at the top, regardless of active tab. */}
          <CompanyAbout symbol={symbol} collapsed={true} />

          <div className="sepa-candidate-page__body">
            {tab === 'chart' && (
              <section>
                {data?.stale_data && (
                  <DelistedBanner symbol={symbol} reason={data?.stale_reason}
                                  renamedTo={data?.renamed_to} />
                )}
                <div className="sepa-tab-help" style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                  <strong>Chart</strong>
                  <span className="livechart-toggle">
                    <button type="button" className={chartSource === 'native' ? 'is-active' : ''} onClick={() => setChartSource('native')}>● Live</button>
                    <button type="button" className={chartSource === 'tv' ? 'is-active' : ''} onClick={() => setChartSource('tv')}>TradingView</button>
                  </span>
                  <ChartReadingGuide />
                  {/* The TV embed is ~15-min delayed (anonymous, by TV's
                      design) — keep the REAL number on screen beside it. */}
                  {chartSource === 'tv' && <LivePriceTag symbol={symbol} />}
                  {chartSource === 'native' && (
                    <span className="livechart-toggle">
                      <button type="button" className={chartInterval === 'D' ? 'is-active' : ''} onClick={() => setChartInterval('D')}>D</button>
                      <button type="button" className={chartInterval === '1m' ? 'is-active' : ''} onClick={() => setChartInterval('1m')}>1m</button>
                    </span>
                  )}
                  <span style={{ fontSize: '0.72rem', color: 'var(--cm-slate)' }}>
                    {chartSource === 'native'
                      ? 'Real-time from your own feed — the current candle ticks live.'
                      : 'TradingView’s full toolset (embed is ~15-min delayed).'}
                  </span>
                </div>
                <div className="sepa-candidate-page__chart">
                  {data?.stale_data ? (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: 220, padding: '1rem', textAlign: 'center', color: 'var(--cm-slate)' }}>
                      {data?.renamed_to
                        ? `${symbol} trades as ${data.renamed_to} now — open ${data.renamed_to} for its live chart.`
                        : `No live chart for ${symbol} — our provider has returned no bars${data?.stale_last_bar ? ` since ${data.stale_last_bar}` : ''}.`}
                    </div>
                  ) : chartSource === 'native' ? (
                    <Suspense fallback={null}><LiveCandlesChart symbol={symbol} interval={chartInterval} /></Suspense>
                  ) : (
                    <iframe
                      key={chartReloadKey}
                      title={`${symbol} live chart`}
                      src={`https://s.tradingview.com/widgetembed/?frameElementId=tv-sepa-${symbol}&symbol=${encodeURIComponent(tvSymbolFor(symbol, data?.profile?.exchange))}&interval=D&theme=dark&style=1&timezone=America%2FNew_York&withdateranges=1&hide_side_toolbar=0&allow_symbol_change=1&save_image=0&studies=%5B%5D&locale=en`}
                      style={{ width: '100%', height: '100%', border: 0 }}
                      allow="clipboard-write"
                    />
                  )}
                </div>
                {chartSource === 'tv' && (
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  flexWrap: 'wrap', gap: '0.4rem',
                  fontSize: '0.7rem', color: 'var(--cm-slate)',
                  margin: '0.3rem 0 0.4rem', padding: '0.3rem 0.5rem',
                  background: 'rgba(255,255,255,0.02)', borderRadius: 4,
                }}>
                  <span>
                    🕐 TradingView embed is delayed ~15 min (a paid TV account can’t unlock the
                    embed — it’s anonymous). Switch to <strong>● Live</strong> for real-time from your feed.
                  </span>
                  <button
                    type="button"
                    onClick={() => setChartReloadKey((k) => k + 1)}
                    style={{
                      background: 'none', border: '1px solid var(--rule, #555)',
                      color: 'var(--ink, inherit)', padding: '2px 8px',
                      borderRadius: 3, cursor: 'pointer', fontSize: '0.7rem',
                    }}
                    title="Force-reload the chart iframe — useful when it freezes after tab refocus."
                  >
                    ↻ Reload chart
                  </button>
                </div>
                )}
                {chartSource === 'tv' && (
                  <div className="sepa-tv-canslim">
                    <a
                      className="sepa-tv-canslim__add"
                      href="https://www.tradingview.com/script/QqSTfaiF-Extended-CANSLIM-Indicator/"
                      target="_blank"
                      rel="noreferrer"
                      title="Opens the Extended CANSLIM indicator on TradingView. Click 'Add to Chart', then save it to your default layout so it loads on every chart you open there."
                    >
                      📈 Add the Extended CANSLIM indicator
                    </a>
                    <a
                      className="sepa-tv-canslim__open"
                      href={`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbolFor(symbol, data?.profile?.exchange))}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      ↗ Open {symbol} in your TradingView (full toolset · your saved indicators)
                    </a>
                    <span className="sepa-tv-canslim__note">
                      Custom indicators live on TradingView itself — the in-app embed above is anonymous, so it
                      can’t carry them. Add CANSLIM once and save it to your <strong>default layout</strong>; it
                      then shows every time you open the full chart from here.
                    </span>
                  </div>
                )}
                <div className="sepa-drawer__chart-links">
                  <a href={`https://www.tradingview.com/symbols/${symbol}/`} target="_blank" rel="noreferrer">Open in TradingView</a>
                  <a href={`https://finance.yahoo.com/quote/${symbol}`} target="_blank" rel="noreferrer">Yahoo Finance</a>
                  <a href={`https://stockanalysis.com/stocks/${symbol.toLowerCase()}/`} target="_blank" rel="noreferrer">StockAnalysis</a>
                  <a href={`https://stocktwits.com/symbol/${symbol}`} target="_blank" rel="noreferrer">StockTwits</a>
                </div>

                {/* Gabbar's buy-zone bands (ported from the Pine Script
                    of the same name — see backend/catalysts/gabbar_levels.py
                    for attribution). Renders inline if the ticker is in
                    the source table, otherwise renders nothing. */}
                <Suspense fallback={null}><GabbarLevels symbol={symbol} currentPrice={currentLivePrice} /></Suspense>

                {/* On-demand pattern scanner for THIS ticker (Ajay 2026-06-09)
                    — auto-runs on open, ↻ re-scans on demand. Which pattern it
                    matches / is closest to, or an explicit no-match, plus this
                    chart's own +21-bar record after past confirmations. */}
                <Suspense fallback={null}><TickerPatternPanel symbol={symbol} /></Suspense>

                {/* On-demand Sonnet buy-signal read (Ajay 2026-06-11) —
                    a pattern saying CONFIRMED isn't the same as buyable;
                    this answers the actual question with the facts shown. */}
                <Suspense fallback={null}><ChartAnalysisPanel symbol={symbol} /></Suspense>

                {/* Candle-reading reference — collapsed by default, expand
                    to learn what green/red bodies and wicks actually mean.
                    Tied directly to Minervini's "evaluate at close, not on
                    wicks" rule so it reinforces the framework above. */}
                <CandleAnatomyExplainer />
              </section>
            )}

            {tab === 'setup' && (
              <section>
                <div className="sepa-tab-help">
                  <strong>Setup</strong> — entry point (<strong>pivot</strong>), exit (<strong>stop</strong>),
                  and a position-sizing calculator. (Position Lens is at the top of the page —
                  use this tab for the entry-side trade plan.)
                </div>

                {/* Supply/demand zones DRAWN, with entry + exit written on the
                    bands (Ajay 2026-08-13, from a hand-marked SNDK chart).
                    Red = overhead supply, green = demand; the entry band is
                    outlined BUY and the stop/target are dashed rules. */}
                <ZoneMap symbol={symbol} />

                {/* GEX + VEX best-case read (Ajay 2026-07-17) — dealer-gamma
                    color on the entry plan: does hedging flow help this setup
                    (pinning above flip) or fight it? Renders nothing when the
                    name has no options chain. */}
                <GexSetupLens symbol={symbol} />

                {/* Why-buy thesis + "what's moving the rank" — the SAME summary
                    block the leaderboard / SEPA list card shows at the bottom of
                    each card. Lives here on the detail page (Setup tab = the
                    buy-side read) so nothing on the card is missing from detail
                    (2026-06-09 card↔detail parity). signalData is the completed
                    projection built above, so the score breakdown matches the card. */}
                {base && signalData && (
                  <div style={{ marginBottom: '1rem' }}>
                    <SepaWhyBuy row={base} signalData={signalData} />
                  </div>
                )}

                {/* Pivot buy framework — the SAME block the leaderboard cards
                    show: BUY + STOPS·PICK ONE (StopsPanel) → the pivot gauge
                    (PivotMeter) → the timed decision / WATCH line
                    (EntryExitPlanBlock). Built from this ticker's entry_exit. */}
                {base?.entry_exit && (
                  <div className="sepa-pivot-framework" style={{ marginBottom: '1rem' }}>
                    <div className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.5rem' }}>
                      Pivot · buy framework
                      <InfoButton title="Pivot buy framework" inline>{PivotFrameworkInfo}</InfoButton>
                    </div>
                    {/* Live SEPA gate (Ajay 2026-06-11) — Trend Template + RelVol
                        recomputed against the current quote, so a borderline
                        name (KIM 7/8, 0.4% from clearing) updates in real time
                        instead of waiting for the next scan. */}
                    <LiveGateStrip symbol={symbol} />
                    {base.entry_exit.exit?.stops?.length ? (
                      <StopsPanel exit={base.entry_exit.exit} />
                    ) : null}
                    {pivotT?.hasSetup && (
                      <div style={{ margin: '0.6rem 0' }}>
                        <PivotMeter t={pivotT} />
                      </div>
                    )}
                    <EntryExitPlanBlock plan={base.entry_exit} />
                  </div>
                )}

                {/* Volume trend — multi-day accumulation/distribution histogram
                    (card↔detail parity). Shown for every name, independent of a
                    setup; pairs with the PivotMeter's single-day relvol gauge. */}
                {base?.volume && (
                  <div className="sepa-pivot-framework" style={{ marginBottom: '1rem' }}>
                    <VolumeTrend vol={base.volume} />
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', marginTop: '0.5rem' }}>
                      {/* symbol fallback → self-heals if the cached row's volume
                          predates breakout_count (card↔detail parity). */}
                      <BreakoutStats vol={base.volume} symbol={base.symbol} />
                      <FloatTurnover symbol={base.symbol} lastVol={base.volume.last_vol} />
                    </div>
                  </div>
                )}

                {/* Comprehensive trade plan — entry/stop/target/levels with
                    Minervini/O'Neil/Wilder methodology. Renders for every
                    analyzed ticker, even ones without a clean VCP base.
                    Note: candidate endpoint nests the SEPA record under
                    `base`, so the path is `data.base.trade_plan`. */}
                {data?.base?.trade_plan && (
                  <div style={{ marginBottom: '1rem' }}>
                    <TradePlanPanel plan={data.base.trade_plan} />
                  </div>
                )}
                {setup ? (
                  <>
                    <div className="sepa-setup-bar">
                      <span className={`sepa-pill sepa-pill--${setup.type.toLowerCase()}`}>{setup.type}</span>
                      <span className="mono">pivot ${setup.pivot} · stop ${setup.stop}</span>
                    </div>
                    {rMultiples && (
                      <div className="sepa-rladder">
                        <div className="sepa-rladder__bar">
                          <div className="sepa-rladder__seg sepa-rladder__seg--risk" />
                          <div className="sepa-rladder__seg sepa-rladder__seg--r1" />
                          <div className="sepa-rladder__seg sepa-rladder__seg--r2" />
                          <div className="sepa-rladder__seg sepa-rladder__seg--r3" />
                        </div>
                        <div className="sepa-rladder__labels mono">
                          <span>stop ${rMultiples.stop.toFixed(2)}</span>
                          <span className="sepa-rladder__entry">entry ${rMultiples.entry.toFixed(2)}</span>
                          <span>+2R ${rMultiples.twoR.toFixed(2)}</span>
                          <span>+3R ${rMultiples.threeR.toFixed(2)}</span>
                        </div>
                      </div>
                    )}
                    {data.smart_money?.analyst?.available && data.smart_money.analyst.target_mean != null && (
                      <div className="sepa-callout mono">
                        🎯 Analyst mean target <strong>${Number(data.smart_money.analyst.target_mean).toFixed(2)}</strong>
                        {' '}(n={data.smart_money.analyst.target_n ?? '—'},
                        {' '}range ${Number(data.smart_money.analyst.target_low).toFixed(2)}–${Number(data.smart_money.analyst.target_high).toFixed(2)})
                        {rMultiples && data.smart_money.analyst.target_mean < rMultiples.twoR && (
                          <span className="sepa-warn-inline"> · below your +2R target</span>
                        )}
                      </div>
                    )}
                    <div className="sepa-planner">
                      <label className="sepa-field">
                        Account size
                        <input type="number" value={accountSize}
                               onChange={(e) => setAccountSize(Number(e.target.value))} />
                      </label>
                      <label className="sepa-field">
                        Risk per trade %
                        <input type="number" step="0.25" min="0.25" max="2" value={riskPct}
                               onChange={(e) => setRiskPct(Number(e.target.value))} />
                      </label>
                    </div>
                    {plan && (
                      <div className="sepa-plan">
                        <div className="sepa-plan__row"><span>Shares</span><strong className="mono">{plan.shares}</strong></div>
                        <div className="sepa-plan__row"><span>Position</span><strong className="mono">${plan.dollar_position?.toLocaleString?.() ?? plan.dollar_position} ({plan.position_pct_of_account}%)</strong></div>
                        <div className="sepa-plan__row"><span>$ Risk</span><strong className="mono">${plan.dollar_risk} ({plan.risk_pct}% stop)</strong></div>
                        <div className="sepa-plan__row sepa-plan__row--target"><span>2R target</span><strong className="mono">${plan.reward_target_2r}</strong></div>
                        <div className="sepa-plan__row sepa-plan__row--target"><span>3R target</span><strong className="mono">${plan.reward_target_3r}</strong></div>
                        {plan.warnings?.map((w: string, i: number) => (
                          <div key={i} className="sepa-warn">⚠ {w}</div>
                        ))}
                      </div>
                    )}
                    <button
                      className={`sepa-btn sepa-btn--primary sepa-btn--block ${added ? 'is-added' : ''}`}
                      onClick={() => { addToWatchlist(symbol, setup.pivot, setup.stop); setAdded(true); }}
                      disabled={added}
                    >
                      {added ? '✓ Added to watchlist' : '+ Add to watchlist'}
                    </button>
                  </>
                ) : (
                  <p className="sepa-empty">No qualifying entry setup detected.</p>
                )}
              </section>
            )}

            {tab === 'ranking' && (
              <section>
                <div className="sepa-tab-help">
                  <strong>Ranking</strong> — how {symbol} has moved through the SEPA
                  ranking over time (rank #1 = top). Overlay the score that drives it
                  or the price; markers show breakouts, when it became enter-ready, and
                  stage changes. Daily by default — toggle intraday for the churn.
                </div>
                <Suspense fallback={null}><RankTrendChart symbol={symbol} /></Suspense>
              </section>
            )}

            {tab === 'trend' && base && (
              <section>
                <div className="sepa-tab-help">
                  <strong>Trend Template</strong> — Minervini's 8 rules. Stage 2 only.
                  VCP flags a tightening base.
                </div>
                <div className="eyebrow">Trend Template (8 criteria)</div>
                <SepaTrendDots checks={base.trend.checks} passed={base.trend.passed} />
                <ul className="sepa-checks">
                  {Object.entries(base.trend.checks).map(([k, v]) => {
                    const meta = TREND_LABEL[k];
                    return (
                      <li key={k} className={v ? 'pass' : 'fail'}>
                        <div className="sepa-check__row">
                          <span className="sepa-check__icon">{v ? '✓' : '✗'}</span>
                          <span className="sepa-check__label">{meta?.label ?? k.replaceAll('_', ' ')}</span>
                        </div>
                        {meta?.help && <div className="sepa-check__help">{meta.help}</div>}
                      </li>
                    );
                  })}
                </ul>
                <div className="sepa-meta-grid">
                  {base.stage && (
                    <div title={STAT_HELP['Stage']}>
                      <span className="sepa-meta-label">Stage</span>
                      <strong>S{base.stage.stage} {base.stage.label}</strong>
                      <span className="sepa-meta-hint">{STAT_HELP['Stage']}</span>
                    </div>
                  )}
                  {base.rs_rank != null && (
                    <div title={STAT_HELP['RS']}>
                      <span className="sepa-meta-label">RS</span>
                      <strong>{base.rs_rank}</strong>
                      <span className="sepa-meta-hint">{STAT_HELP['RS']}</span>
                    </div>
                  )}
                  {base.adr_pct != null && (
                    <div title={STAT_HELP['ADR']}>
                      <span className="sepa-meta-label">ADR</span>
                      <strong>{base.adr_pct}%</strong>
                      <span className="sepa-meta-hint">{STAT_HELP['ADR']}</span>
                    </div>
                  )}
                  {base.liquidity?.avg_dollar_vol != null && (
                    <div title={STAT_HELP['$ vol']}>
                      <span className="sepa-meta-label">$ vol</span>
                      <strong>${(base.liquidity.avg_dollar_vol / 1e6).toFixed(1)}M</strong>
                      <span className="sepa-meta-hint">{STAT_HELP['$ vol']}</span>
                    </div>
                  )}
                </div>
                {base.vcp?.has_base && (
                  <div className="sepa-vcp">
                    <div className="eyebrow">VCP</div>
                    <div className="mono">
                      {base.vcp.n_contractions} contractions · depth {base.vcp.base_depth_pct}% · final {base.vcp.final_contraction_pct}%
                      {base.vcp.pivot_quality_ok && ' · ✓ pivot quality'}
                    </div>
                  </div>
                )}
              </section>
            )}

            {tab === 'fundamentals' && (
              <section>
                <div className="sepa-tab-help">
                  <strong>CANSLIM Fundamentals</strong>{' '}
                  <InfoButton inline title="What CANSLIM stands for">
                    <>
                      <p>
                        <strong>CANSLIM</strong> is William O'Neil's 7-letter
                        framework from <em>How to Make Money in Stocks</em>.
                        Cheetah scores the three quantitative letters
                        (<strong>C</strong>, <strong>A</strong>, <strong>I</strong>);
                        the rest are qualitative.
                      </p>
                      <ul>
                        <li><strong>C</strong> — <strong>Current Quarterly Earnings</strong>: latest-quarter Earnings Per Share (EPS) growth Year-over-Year (Y/Y) ≥ 25%.</li>
                        <li><strong>A</strong> — <strong>Annual Earnings</strong>: 3-year annual EPS growth ≥ 25% per year.</li>
                        <li><strong>N</strong> — <strong>New</strong> products / services / management / price highs (qualitative).</li>
                        <li><strong>S</strong> — <strong>Supply &amp; Demand</strong>: tight float, accumulation on volume.</li>
                        <li><strong>L</strong> — <strong>Leader</strong>: top of its industry group on Relative Strength (RS).</li>
                        <li><strong>I</strong> — <strong>Institutional Sponsorship</strong>: institutional ownership 40-80% (too low = unloved, too high = saturated).</li>
                        <li><strong>M</strong> — <strong>Market Direction</strong>: bull-trend confirmed (handled by the Market Regime banner on the SEPA page).</li>
                      </ul>
                    </>
                  </InfoButton>
                  <span> — the three quantifiable letters scored from this stock's reported fundamentals.</span>
                </div>
                <div className="eyebrow">CANSLIM fundamentals</div>
                {base?.is_etf ? (
                  <div className="sepa-etf-banner">
                    <p>
                      <strong>{symbol} is an Exchange-Traded Fund (ETF)</strong>
                      {base.etf_data?.category && (
                        <> · {base.etf_data.category}</>
                      )}
                      {base.etf_data?.fund_family && (
                        <> · {base.etf_data.fund_family}</>
                      )}
                    </p>
                    <p>
                      CANSLIM is a stock-picking framework — it scores Earnings
                      Per Share (EPS) growth, Annual Earnings, and Institutional
                      Sponsorship at the company level. ETFs are baskets of
                      stocks, not operating companies, so these gates don't
                      apply. The relevant metrics for {symbol} appear in the
                      page header above (Assets Under Management, Expense Ratio,
                      Dividend Yield, Top Holding).
                    </p>
                    {base.etf_data?.top_holdings && base.etf_data.top_holdings.length > 0 && (
                      <>
                        <div className="eyebrow" style={{ marginTop: '0.8rem' }}>
                          Top {base.etf_data.top_holdings.length} holdings
                        </div>
                        <ul className="sepa-etf-banner__holdings">
                          {base.etf_data.top_holdings.map((h: any) => (
                            <li key={h.symbol}>
                              <strong className="mono">{h.symbol}</strong>
                              {h.name && <span className="sepa-etf-banner__name"> · {h.name}</span>}
                              <span className="mono sepa-etf-banner__wt"> {(h.weight * 100).toFixed(2)}%</span>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                ) : base?.fundamentals ? (
                  <div className="sepa-fund">
                    <div className="sepa-fund__row" title="Current Quarterly Earnings — Earnings Per Share (EPS) growth, latest quarter vs same quarter last year.">
                      <span>
                        <strong>C</strong> — Current Quarterly Earnings
                        <span className="sepa-fund__sub">
                          Quarterly Earnings Per Share (EPS), Year-over-Year (Y/Y)
                        </span>
                      </span>
                      <strong className={base.fundamentals.checks.c_strong_q_eps ? 'pass' : 'fail'}>
                        {base.fundamentals.q_eps_growth_pct ?? '—'}%
                        {base.fundamentals.checks.c_strong_q_eps ? ' ✓' : ' (need ≥ 25%)'}
                      </strong>
                    </div>
                    <div className="sepa-fund__row" title="Annual Earnings — 3-year annual Earnings Per Share (EPS) growth rate.">
                      <span>
                        <strong>A</strong> — Annual Earnings
                        <span className="sepa-fund__sub">
                          3-year annual Earnings Per Share (EPS) growth
                        </span>
                      </span>
                      <strong className={base.fundamentals.checks.a_strong_y_eps ? 'pass' : 'fail'}>
                        {base.fundamentals.y_eps_growth_pct ?? '—'}%
                        {base.fundamentals.checks.a_strong_y_eps ? ' ✓' : ' (need ≥ 25%)'}
                      </strong>
                    </div>
                    <div className="sepa-fund__row" title="Institutional Sponsorship — % of float owned by mutual funds, pension funds, banks, and other institutions. 40-80% is the sweet spot.">
                      <span>
                        <strong>I</strong> — Institutional Sponsorship
                        <span className="sepa-fund__sub">
                          % of shares held by funds &amp; institutions
                        </span>
                      </span>
                      <strong className={base.fundamentals.checks.i_institutional ? 'pass' : 'fail'}>
                        {base.fundamentals.inst_ownership_pct ?? '—'}%
                        {base.fundamentals.checks.i_institutional ? ' ✓' : ' (need 40-80%)'}
                      </strong>
                    </div>
                    <div className="sepa-fund__row" title="Quarterly revenue growth Year-over-Year (Y/Y) — informational, not part of CANSLIM gates.">
                      <span>
                        Quarterly Revenue (Y/Y)
                        <span className="sepa-fund__sub">
                          revenue, latest quarter vs same quarter last year
                        </span>
                      </span>
                      <strong>{base.fundamentals.rev_growth_q_pct ?? '—'}%</strong>
                    </div>
                    {(base.fundamentals as any).earnings_quality && (
                      <EarningsQualityPanel eq={(base.fundamentals as any).earnings_quality} />
                    )}
                  </div>
                ) : (
                  <div className="sepa-empty sepa-empty--action">
                    <p>No fundamentals cached for {symbol}.</p>
                    <button
                      className="sepa-btn sepa-btn--primary"
                      onClick={() => rescan(true)}
                      disabled={rescanState === 'running'}
                    >
                      {rescanState === 'running'
                        ? 'Re-scanning…'
                        : `Re-scan ${symbol} with +catalyst (fundamentals · news · insider)`}
                    </button>
                    {rescanMsg && (
                      <p className={`sepa-empty__hint ${rescanState === 'error' ? 'sepa-warn' : ''}`}>
                        {rescanMsg}
                      </p>
                    )}
                  </div>
                )}
              </section>
            )}

            {tab === 'breakout' && (
              <section>
                <div className="sepa-tab-help">
                  <strong>Breakout</strong> — how often {symbol} has actually printed a
                  volume-confirmed breakout over the last year (close above the prior
                  21-day high on &gt;1.5× average volume — Minervini p.203), and exactly
                  WHERE each one fired on the price chart.
                </div>
                <Suspense fallback={null}><BreakoutHistoryBody symbol={symbol} /></Suspense>
              </section>
            )}

            {tab === 'analysis' && (
              <section>
                <div className="sepa-tab-help">
                  <strong>Analysis</strong> — the composite <strong>buy / sell verdict</strong> first,
                  combining <strong>Minervini's</strong> SEPA Trend Template (price/MA stack, RS,
                  pivot breakout) with <strong>Pradeep Bonde's</strong> Stockbee playbook (Episodic
                  Pivot, 4% breakout, momentum burst, group leadership — and the anti-thesis
                  <em> sell</em> signals). A full <strong>ENTER</strong> needs both; any sell signal or
                  broken trend forces <strong>AVOID</strong>. Below it: the entry/sales fundamental
                  gate, the sales-confidence detail, then the multi-panel readout.
                </div>

                {/* Institutions-selling indicator (Ajay 2026-06-21) — when the
                    tape shows distribution (climax-top or a churn breakout,
                    TTLAC p.186-188) the name is HELD OUT of the Enter/buy tier.
                    Leads the verdict so the "why not buyable" is obvious. */}
                {base?.distribution_selling && (
                  <div style={{ marginBottom: '1rem', padding: '0.6rem 0.85rem', borderRadius: 8,
                                border: '1px solid rgba(244,63,94,0.5)', background: 'rgba(244,63,94,0.10)' }}>
                    <div style={{ color: '#f43f5e', fontWeight: 700, fontSize: '0.9rem' }}>
                      🔴 Big institutions are selling — held out of Enter
                    </div>
                    <div style={{ color: '#cdd5e3', fontSize: '0.78rem', marginTop: 3, lineHeight: 1.5 }}>
                      {base.distribution_reason || 'Distribution detected on the recent tape.'} You'd be
                      buying as the big money sells into it, so this name stays on the watchlist but is
                      kept out of the buy/Enter tier (Minervini, <em>Think &amp; Trade Like a Champion</em> p.186-188).
                      {base.climax_distribution?.in_climax && base.climax_distribution?.climax_gain_pct != null
                        ? ` Climax run +${base.climax_distribution.climax_gain_pct}%.` : ''}
                    </div>
                  </div>
                )}

                {/* Composite Minervini SEPA + Bonde/Stockbee buy-&-sell verdict —
                    leads the tab (Ajay 2026-06-16). Frontend synthesis over the
                    fields the scan already carries (trend, volume, sell_signals,
                    dual_momentum, group_*). Logic: src/lib/cheetahVerdict.ts. */}
                {base && (
                  <CheetahVerdictPanel
                    row={base}
                    catalystSurprisePct={(data as any)?.catalyst?.last_earnings_surprise_pct ?? null}
                  />
                )}

                {/* Underlying fundamental gate — Minervini buyable qualifier
                    (p.79) + Bonde sales pass/fail. Kept as supporting detail
                    beneath the composite verdict, not a competing headline. */}
                {base?.buy_verdict && (
                  <div style={{ marginBottom: '1rem' }}>
                    <div className="eyebrow">Fundamental gate — entry qualifier + sales</div>
                    <BuyVerdictPanel verdict={base.buy_verdict} />
                  </div>
                )}

                {/* Sales-confidence detail (the old Sales tab, folded in here). */}
                {base?.fundamentals?.sales && (
                  <div style={{ marginBottom: '1rem' }}>
                    <div className="eyebrow">Sales confidence — Pradeep Bonde detail</div>
                    <SalesPanel sales={(base.fundamentals as any).sales} />
                  </div>
                )}

                {/* Fidelity-style multi-panel readout (free-data composite). */}
                <div className="eyebrow">Multi-source analysis</div>
                <Suspense fallback={null}><StockAnalysisPanel symbol={symbol} /></Suspense>
              </section>
            )}

            {tab === 'catalyst' && (
              <section>
                <div className="sepa-tab-help">
                  <strong>Catalyst</strong> — a just-in-time read of the latest headlines.
                  Click below and it tells you whether the news makes {symbol}{' '}
                  <strong>more buyable, less buyable, or a sell</strong>. Nothing is preloaded.
                </div>
                {/* JIT news read — summarized on click, NOT preloaded: does
                    recent news make this more/less buyable or a sell
                    (Ajay 2026-06-08). The preloaded summary/sentiment block
                    below it stayed — he asked for the AI catalyst digest the
                    very next day (2026-06-09), so both live here. */}
                <NewsReadButton symbol={symbol} />

                {data.catalyst ? (
                  <>
                    {data.catalyst.summary && (
                      <div
                        className="sepa-callout"
                        style={{ borderLeft: '3px solid var(--gold, #c9a227)', background: 'rgba(201,162,39,0.06)' }}
                      >
                        <div className="eyebrow" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span>🧠 Catalyst summary</span>
                          <span style={{ fontWeight: 400, opacity: 0.6, fontSize: '0.62rem' }}>
                            AI digest of the headlines below · verify before trading
                          </span>
                        </div>
                        <div style={{ lineHeight: 1.45, marginTop: 4 }}>{data.catalyst.summary}</div>
                      </div>
                    )}
                    {data.catalyst.earnings_upcoming && (
                      <div className="sepa-callout">
                        📅 Earnings <strong>{data.catalyst.earnings_upcoming.date}</strong>{' '}
                        ({data.catalyst.earnings_upcoming.hour ?? '—'})
                      </div>
                    )}
                    <div className="sepa-meta-grid">
                      <div><span className="sepa-meta-label">News sentiment</span><strong>{data.catalyst.news_sentiment_score ?? 0}</strong></div>
                      <div><span className="sepa-meta-label">Up revs (30d)</span><strong>{data.catalyst.analyst_up_revisions_30d ?? 0}</strong></div>
                      <div><span className="sepa-meta-label">Down revs (30d)</span><strong>{data.catalyst.analyst_down_revisions_30d ?? 0}</strong></div>
                    </div>
                    <ul className="sepa-news">
                      {data.catalyst.top_news?.slice(0, 6).map((n: any, i: number) => (
                        <li key={i}>
                          <a href={n.link} target="_blank" rel="noreferrer">{n.title}</a>
                        </li>
                      ))}
                    </ul>
                    {(data.smart_money?.reddit?.threads?.length > 0 || data.smart_money?.blogs?.length > 0) && (
                      <div className="sepa-callout">
                        <div className="eyebrow">Top discussion</div>
                        <ul className="sepa-news">
                          {data.smart_money.blogs?.slice(0, 2).map((b: any, i: number) => (
                            <li key={`b${i}`}>
                              <span className="sepa-pill sepa-pill--blog">{b.source}</span>{' '}
                              <a href={b.link} target="_blank" rel="noreferrer">{b.title}</a>
                            </li>
                          ))}
                          {data.smart_money.reddit?.threads?.slice(0, 3).map((t: any, i: number) => (
                            <li key={`r${i}`}>
                              <span className="sepa-pill sepa-pill--reddit">r/{t.subreddit}</span>{' '}
                              <a href={t.url} target="_blank" rel="noreferrer">{t.title}</a>
                              <span className="mono"> · ↑{t.score} · {t.n_comments}c</span>
                            </li>
                          ))}
                        </ul>
                        <div className="sepa-meta-hint">See full breakdown in the <strong>smart money</strong> tab.</div>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="sepa-empty">No catalyst data — run <code>+catalyst</code> scan.</p>
                )}
              </section>
            )}

            {tab === 'insider' && (
              <section>
                <div className="sepa-tab-help">
                  <strong>Insider activity</strong> from SEC filings, scoped to this issuer's
                  CIK. Form 4 = insider trades; only open-market <em>purchases</em> (code P) by
                  officers/directors count as buying — grants, option exercises and
                  tax-withholding don't. 13D = activist 5%+ stake, 13G = passive 5%+ stake.
                </div>
                {data.insider ? (
                  <ul className="sepa-kv mono">
                    <li>Form 4 (30d): <strong>{data.insider.form4_count_30d}</strong> · distinct filers: <strong>{data.insider.form4_unique_insiders_30d}</strong></li>
                    <li>
                      Open-market: <strong className={(data.insider.form4_buy_count_30d ?? 0) > 0 ? 'sepa-flag sepa-flag--good' : undefined}>{data.insider.form4_buy_count_30d ?? 0} buy</strong>
                      {(data.insider.form4_buy_count_30d ?? 0) !== 1 ? 's' : ''}
                      {' · '}{data.insider.form4_sell_count_30d ?? 0} sell{(data.insider.form4_sell_count_30d ?? 0) !== 1 ? 's' : ''}
                      {' · insider buyers: '}<strong>{data.insider.form4_insider_buyers_30d ?? 0}</strong>
                    </li>
                    {data.insider.form4_cluster_buy
                      ? <li className="sepa-flag sepa-flag--good">★ Cluster insider buying — {data.insider.form4_insider_buyers_30d} officers/directors bought open-market</li>
                      : <li className="sepa-muted">No open-market insider buying cluster</li>}
                    <li>13D (180d): {data.insider.sc13d_180d} {data.insider.has_recent_13d && '★ recent'}</li>
                    <li>13G (180d): {data.insider.sc13g_180d}</li>
                  </ul>
                ) : <p className="sepa-empty">No insider data.</p>}
                {data.insider?.recent_filings && (
                  <InsiderFilingTimeline recent={data.insider.recent_filings} />
                )}
                {data.ipo_age && (
                  <div className="sepa-callout mono">
                    IPO {data.ipo_age.first_trade_date} · {data.ipo_age.years_since_ipo}y old
                    {data.ipo_age.is_young && ' · young ✓'}
                    {data.ipo_age.is_recent_ipo && ' · recent IPO ✓'}
                  </div>
                )}
              </section>
            )}

            {tab === 'smartmoney' && (
              <section>
                <div className="sepa-tab-help">
                  <strong>Smart Money & Sentiment</strong>{' '}
                  <InfoButton inline title="What this tab shows">{SmartMoneyInfo}</InfoButton>
                  <span> — what credentialed analysts and credible commentators think.</span>
                </div>
                <SmartMoneyPanel data={data.smart_money} symbol={symbol} />
              </section>
            )}

            {tab === 'chatter' && (
              <section>
                <div className="sepa-tab-help">
                  <strong>Forum Chatter</strong>{' '}
                  <InfoButton inline title="Forum Chatter">
                    <>
                      <p>
                        Crowd discussion across four lanes — Reddit Momentum
                        (r/wallstreetbets, r/StockMarket, r/pennystocks,
                        r/Daytrading, r/swingtrading), Reddit Thoughtful
                        (r/SecurityAnalysis, r/ValueInvesting, r/investing,
                        r/stocks, r/options), StockTwits (Bullish/Bearish
                        user-tagged messages), and Hacker News (last 30 days).
                      </p>
                      <p>
                        <strong>Velocity</strong> = posts last 7 days ÷ posts
                        the prior 7 days. <strong>Sentiment %</strong> blends
                        StockTwits Bullish/Bearish counts with score-weighted
                        Reddit upvotes. <strong>Momentum label</strong>:
                        ramping (≥1.5× velocity, ≥3 posts), steady, fading
                        (≤0.6× velocity), or quiet (no signal).
                      </p>
                      <p>
                        Cached 15 minutes — click <em>Refresh</em> to bust the
                        cache and pull fresh data.
                      </p>
                    </>
                  </InfoButton>
                  <span> — Reddit, StockTwits, and Hacker News for this ticker.</span>
                </div>
                <Suspense fallback={null}><ChatterPanel symbol={symbol} /></Suspense>
              </section>
            )}

            {tab === 'options' && (
              <section>
                <div className="sepa-tab-help">
                  <strong>Options flow · SOIR (Schaeffer)</strong> — what the
                  options crowd is doing on this ticker. Put/call open
                  interest, expected move, ATM IV, and a 90-day P/C ratio
                  trajectory. Schaeffer's framework reads CROWDED puts as
                  contrarianly <em>bullish</em> (wrong-footed unwind = fuel
                  for upside) and crowded calls as bearish. If no snapshot
                  exists yet, click "Scan options flow" to fetch the chain
                  on-demand — backed by Massive Options Advanced, the scan
                  returns in ~1s (down from ~30s on the yfinance fallback).
                </div>
                <TomorrowBiasBlock symbol={symbol} />
                <OptionsFlowPanel symbol={symbol} />
                <OpExPanel symbol={symbol} />
              </section>
            )}

            {tab === 'tape' && (
              <section>
                <div className="sepa-tab-help">
                  <strong>Tape · order flow</strong> — the session's raw prints, classified
                  buyer- vs seller-aggressive: cumulative <em>delta</em> (who's in control),
                  <em> big prints</em> (institutional blocks), <em>trade-flash</em> urgency
                  bursts, the session <em>volume profile</em> (the honest bookmap substitute —
                  traded volume, not spoofable resting orders), intraday EMAs, supply/demand
                  zones and dealer-gamma context — rolled into one deterministic
                  BUY / WAIT / AVOID checklist, gated on your daily SEPA trend. Every ⓘ
                  explains its concept; every verdict is logged and graded so the hit rate
                  shown is <em>ours, measured</em>.
                </div>
                <TapePanel symbol={symbol} />
              </section>
            )}

            {tab === 'supply' && (
              <section>
                <div className="sepa-tab-help">
                  <strong>Supply / Demand context</strong> — who this company
                  depends on, who depends on it, and which global sector
                  supply/demand cycles drive its results. Hover edges for
                  evidence + recent news. Click any node to drill into that company.
                </div>
                <TickerSupplyDemandPanel symbol={symbol} />
              </section>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// --- Sticky category badges ---
//
// Pinned strip showing what KIND of ticker this is — Pioneer themes (AI,
// space, biotech-pioneer, etc.), ETF tag, exchange, industry. Anchors
// below the page header so the user keeps context while scrolling
// through long-form sections (trend gates, supply-demand, chatter,
// catalysts). Complements <SepaSignalChips> right above: chips tell
// you HOW it scored, badges tell you WHAT it is.
//
// Layout: small pill badges in a horizontal row, wrapping on narrow
// screens. CSS position:sticky with top:0 — they stay glued to the
// viewport once scrolled past. z-index above the body so iframes /
// other section content don't paint over them.
function StickyCategoryBadges({
  pioneerThemes,
  isEtf,
  etfCategory,
  exchange,
  industry,
}: {
  pioneerThemes?: { id: string; label: string }[];
  isEtf?: boolean;
  etfCategory?: string | null;
  exchange?: string | null;
  industry?: string | null;
}) {
  const hasAny =
    (pioneerThemes && pioneerThemes.length > 0) ||
    isEtf ||
    exchange ||
    industry;
  if (!hasAny) return null;

  // Compact pill style — smaller than the SignalChips above so the
  // visual hierarchy reads "score chips > category badges". Backgrounds
  // tinted per category type for at-a-glance recognition.
  const baseBadge: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 3,
    padding: '0.18rem 0.55rem',
    borderRadius: 12,
    fontSize: '0.72rem',
    fontWeight: 600,
    whiteSpace: 'nowrap',
    border: '1px solid',
  };

  return (
    <div
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        background: 'var(--cm-bg, #0a0a0a)',
        // Subtle bottom border so the strip visually detaches from the
        // section beneath when it's pinned to the viewport top.
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        padding: '0.45rem 0',
        marginBottom: '0.4rem',
        // Negative top-margin pulls it tight against the header so the
        // gap doesn't double-up before the user scrolls.
        marginTop: '-0.2rem',
      }}
      title="Category badges — stays visible as you scroll. Tells you what kind of asset this is."
    >
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center',
      }}>
        {/* Pioneer themes — curated breakthrough categories (AI, space,
            quantum, etc.). Same color as the card chip for consistency. */}
        {pioneerThemes?.map((t) => (
          <span
            key={t.id}
            style={{
              ...baseBadge,
              background:  'rgba(139,92,246,0.10)',
              borderColor: 'rgba(139,92,246,0.35)',
              color:       '#a78bfa',
            }}
            title={`Pioneer theme — ${t.label}. Click "Pioneers" in the nav for full theme breakdown.`}
          >🚀 {t.label}</span>
        ))}

        {/* ETF marker — flag this isn't a single-company stock. CANSLIM
            fundamentals don't apply; relevant metrics live in the
            etf_data block (AUM, expense ratio, top holdings). */}
        {isEtf && (
          <span
            style={{
              ...baseBadge,
              background:  'rgba(245,158,11,0.10)',
              borderColor: 'rgba(245,158,11,0.35)',
              color:       '#f59e0b',
            }}
            title={
              `Exchange-Traded Fund — basket of underlying stocks. ` +
              `CANSLIM EPS / fundamentals don't apply; relevant metrics ` +
              `are AUM, expense ratio, dividend yield, and holdings.` +
              (etfCategory ? `\nCategory: ${etfCategory}` : '')
            }
          >📊 ETF{etfCategory ? ` · ${etfCategory}` : ''}</span>
        )}

        {/* Exchange — NYSE / NASDAQ / etc. Useful for distinguishing
            ADRs (often non-NYSE/NASDAQ) at a glance. */}
        {exchange && (
          <span
            style={{
              ...baseBadge,
              background:  'rgba(255,255,255,0.04)',
              borderColor: 'rgba(255,255,255,0.12)',
              color:       '#cfcfd4',
            }}
            title="Listing exchange"
          >🏛 {exchange}</span>
        )}

        {/* Industry — yfinance/Finnhub category. Helps the user spot
            sector rotation (e.g. all my picks are software). */}
        {industry && (
          <span
            style={{
              ...baseBadge,
              background:  'rgba(59,130,246,0.10)',
              borderColor: 'rgba(59,130,246,0.35)',
              color:       '#60a5fa',
            }}
            title="Industry classification (yfinance / Finnhub)"
          >🏷 {industry}</span>
        )}
      </div>
    </div>
  );
}

// --- Embedded ticker supply/demand panel ---
function TickerSupplyDemandPanel({ symbol }: { symbol: string }) {
  const { data, loading } = useTickerSupplyDemand(symbol, 1);
  const [drillTicker, setDrillTicker] = useState<string | null>(null);

  if (loading) return <p className="sepa-empty">Loading supply chain context…</p>;
  if (!data) return <p className="sepa-empty">No supply/demand data for {symbol}.</p>;

  const sg = data.subgraph;
  return (
    <>
      {/* Per-ticker flow + accumulation/distribution panel */}
      <TickerFlowAccumPanel ctx={data} />

      {sg.edges.length > 0 ? (
        <>
          <div className="eyebrow" style={{ marginTop: 16, marginBottom: 8 }}>{sg.nodes.length} companies · {sg.edges.length} relationships · click any bubble for thesis</div>
          <Suspense fallback={<div style={{ minHeight: 460 }} aria-busy="true" />}>
            <DependencyGraph
              nodes={sg.nodes}
              edges={sg.edges}
              height={460}
              centerTicker={sg.center}
              onNodeClick={(t) => setDrillTicker(t)}
              selectedTicker={drillTicker}
            />
          </Suspense>
          <NodeThesisPanel ticker={drillTicker} onClose={() => setDrillTicker(null)} />
        </>
      ) : (
        <p className="sepa-empty">No curated dependencies for {symbol} yet — Phase 2 will auto-expand from 10-K filings.</p>
      )}

      {data.sectors.length > 0 && (
        <>
          <div className="eyebrow" style={{ marginTop: 24, marginBottom: 8 }}>Sector exposures</div>
          <ul className="sepa-news">
            {data.sectors.map((s) => {
              const c = s.classification;
              const moodClass = c.state === 'constrained' ? 'good' : c.state === 'oversupplied' ? 'bad' : 'warn';
              return (
                <li key={s.sector_id}>
                  <span className={`sepa-pill sepa-pill--${moodClass}`}>{s.label}</span>{' '}
                  <strong>{c.state}</strong> · gap {c.gap_index}/100 · trend {c.trend_direction}
                  <div className="sepa-check__help">{c.narrative}</div>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </>
  );
}

type SmartMoneyAnalyst = {
  available: boolean;
  reason?: string;
  buckets?: { strong_buy: number; buy: number; hold: number; sell: number; strong_sell: number };
  total_analysts?: number;
  bullish_pct?: number | null;
  delta_bullish_mom?: number;
  target_mean?: number | null;
  target_median?: number | null;
  target_high?: number | null;
  target_low?: number | null;
  target_n?: number | null;
  period?: string;
};

type SmartMoneyBlog = {
  source: string; title: string; link: string;
  published: string; snippet: string;
};

type SmartMoneyReddit = {
  available: boolean; reason?: string;
  threads?: Array<{
    subreddit: string; title: string; url: string;
    score: number; n_comments: number; created: number; snippet: string;
  }>;
};

type SmartMoneyData = {
  symbol: string; fetched_at: number; cached: boolean;
  analyst: SmartMoneyAnalyst;
  blogs: SmartMoneyBlog[];
  reddit: SmartMoneyReddit;
};

function SmartMoneyPanel({ data, symbol }: { data?: SmartMoneyData; symbol: string }) {
  if (!data) return <p className="sepa-empty">Smart Money data still loading…</p>;
  const a = data.analyst;
  const blogs = data.blogs || [];
  const reddit = data.reddit;

  return (
    <>
      {/* Analyst lane */}
      <div className="eyebrow">Wall Street analyst consensus</div>
      {a?.available && a.total_analysts ? (
        <>
          <div className="sepa-fund">
            <div className="sepa-fund__row">
              <span>Bullish %</span>
              <strong className={(a.bullish_pct ?? 0) >= 60 ? 'pass' : (a.bullish_pct ?? 0) <= 40 ? 'fail' : ''}>
                {a.bullish_pct ?? '—'}%
                {a.delta_bullish_mom != null && a.delta_bullish_mom !== 0 && (
                  <span className="mono"> ({a.delta_bullish_mom > 0 ? '+' : ''}{a.delta_bullish_mom} mom)</span>
                )}
              </strong>
            </div>
            <div className="sepa-fund__row">
              <span>Distribution</span>
              <strong className="mono">
                SB {a.buckets?.strong_buy ?? 0} · B {a.buckets?.buy ?? 0} · H {a.buckets?.hold ?? 0}
                {' · '}S {a.buckets?.sell ?? 0} · SS {a.buckets?.strong_sell ?? 0}
              </strong>
            </div>
            <div className="sepa-fund__row">
              <span>Total analysts</span><strong className="mono">{a.total_analysts}</strong>
            </div>
            {a.target_mean != null && (
              <>
                <div className="sepa-fund__row">
                  <span>Mean price target</span>
                  <strong className="mono">${Number(a.target_mean).toFixed(2)} (n={a.target_n ?? '—'})</strong>
                </div>
                <div className="sepa-fund__row">
                  <span>Range</span>
                  <strong className="mono">
                    ${Number(a.target_low).toFixed(2)}–${Number(a.target_high).toFixed(2)}
                    {a.target_median != null && ` · median $${Number(a.target_median).toFixed(2)}`}
                  </strong>
                </div>
              </>
            )}
          </div>
          <div className="sepa-meta-hint">
            Period {a.period ?? '—'}. Free Finnhub feed exposes aggregate ratings only —
            not per-analyst track records. Use the bullish % delta as a sentiment-shift signal.
          </div>
        </>
      ) : (
        <p className="sepa-empty">No analyst data{a?.reason ? ` (${a.reason})` : ''}.</p>
      )}

      {/* Blogs lane */}
      <div className="eyebrow" style={{ marginTop: 24 }}>Curated commentary</div>
      {blogs.length === 0 ? (
        <p className="sepa-empty">
          No mentions in Damodaran / Bespoke / Morningstar feeds.
          That's normal — most names won't show up here.
        </p>
      ) : (
        <ul className="sepa-news">
          {blogs.map((b, i) => (
            <li key={i}>
              <span className="sepa-pill sepa-pill--blog">{b.source}</span>{' '}
              <a href={b.link} target="_blank" rel="noreferrer">{b.title}</a>
              {b.published && <span className="mono sepa-meta-hint"> · {b.published.slice(0, 10)}</span>}
              {b.snippet && <div className="sepa-check__help">{b.snippet}</div>}
            </li>
          ))}
        </ul>
      )}

      {/* Reddit lane */}
      <div className="eyebrow" style={{ marginTop: 24 }}>Reddit discussion</div>
      {!reddit?.available ? (
        <p className="sepa-empty">
          Reddit lane disabled{reddit?.reason ? ` — ${reddit.reason}` : ''}.
          Set <code>REDDIT_CLIENT_ID</code> and <code>REDDIT_CLIENT_SECRET</code> in <code>backend/.env</code> to enable.
        </p>
      ) : (reddit.threads?.length ?? 0) === 0 ? (
        <p className="sepa-empty">No threads cleared the score floor in the last 30d.</p>
      ) : (
        <ul className="sepa-news">
          {reddit.threads!.map((t, i) => (
            <li key={i}>
              <span className="sepa-pill sepa-pill--reddit">r/{t.subreddit}</span>{' '}
              <a href={t.url} target="_blank" rel="noreferrer">{t.title}</a>
              <span className="mono sepa-meta-hint"> · ↑{t.score} · {t.n_comments}c</span>
              {t.snippet && <div className="sepa-check__help">{t.snippet}</div>}
            </li>
          ))}
        </ul>
      )}

      <div className="sepa-meta-hint mono" style={{ marginTop: 16 }}>
        {data.cached ? '↻ from cache' : '⟳ fresh'} · symbol {symbol} · 15-min TTL
      </div>
    </>
  );
}


/**
 * TickerFlowAccumPanel — top of the SUPPLY/DEMAND tab on SepaCandidate.
 * Shows two adjacent panels:
 *   1. Live flow — current price, today's % change, volume, market state.
 *      Same data Yahoo's "Pre-Market" line shows (from Massive's lastTrade
 *      which is extended-hours-aware).
 *   2. Multi-day accumulation/distribution — Chaikin Money Flow over 10
 *      sessions, with the score, label, and the three sub-signals it's
 *      computed from.
 */
function TickerFlowAccumPanel({ ctx }: { ctx: TickerContext }) {
  const flow = ctx.flow;
  const accum = ctx.accumulation;

  const isUp = (flow?.change_pct ?? 0) > 0.05;
  const isDown = (flow?.change_pct ?? 0) < -0.05;
  const flowColor = isUp ? 'var(--positive)' : isDown ? 'var(--negative)' : 'var(--ink-muted)';

  const accumScore = accum?.score ?? 0;
  const accumLabel = accum?.label;
  const accumColor =
    accumScore >= 30 ? '#22c55e' :
    accumScore <= -30 ? '#ef4444' :
    'var(--ink-muted)';

  // Score bar: -100 → +100, with center at 50%
  const accumPct = Math.max(0, Math.min(100, 50 + accumScore / 2));

  const marketLabel = flow?.market?.label || 'Markets closed';
  const marketState = flow?.market?.state || 'closed';

  const fmtVol = (v?: number) => {
    if (!v) return '—';
    if (v >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
    if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
    if (v >= 1e3) return `${(v / 1e3).toFixed(0)}k`;
    return v.toString();
  };

  return (
    <div className="tfa-panel">
      {/* Left: Today's flow (intraday + market state) */}
      <div className="tfa-card">
        <div className="tfa-card__h">
          <span className="eyebrow">Live flow</span>
          <span className={`tfa-state tfa-state--${marketState}`}>
            {marketState === 'open' && '🟢 LIVE DATA'}
            {marketState === 'pre' && '🌅 PRE-MKT'}
            {marketState === 'after' && '🟠 AFTER-HRS'}
            {marketState === 'closed' && '⚪️ CLOSED · stale'}
            {marketState === 'weekend' && '⚪️ WEEKEND'}
          </span>
        </div>
        {flow ? (
          <>
            <div className="tfa-price-row">
              <span className="tfa-price mono">${flow.price?.toFixed(2)}</span>
              <span className="tfa-chg mono" style={{ color: flowColor }}>
                {isUp ? '+' : ''}{flow.change_pct?.toFixed(2)}%
              </span>
              <span className="tfa-prevclose mono">vs prev ${flow.prev_close?.toFixed(2)}</span>
            </div>
            <div className="tfa-stats mono">
              <span>vol {fmtVol(flow.volume)}</span>
              <span>$ vol {fmtVol(flow.dollar_volume)}</span>
              {flow.day_high ? <span>HoD ${flow.day_high.toFixed(2)}</span> : null}
              {flow.day_low ? <span>LoD ${flow.day_low.toFixed(2)}</span> : null}
            </div>
            <div className="tfa-hint">
              {marketLabel} · price reflects {marketState === 'pre' ? 'pre-market' : marketState === 'after' ? 'after-hours' : marketState === 'open' ? 'live regular session' : "yesterday's close"}
            </div>
          </>
        ) : (
          <p className="sepa-empty">No flow data available.</p>
        )}
      </div>

      {/* Right: Multi-day accumulation/distribution */}
      <div className="tfa-card">
        <div className="tfa-card__h">
          <span className="eyebrow">Accumulation / Distribution</span>
          {accumLabel && (
            <span className="tfa-label" style={{ color: accumColor }}>
              {accumScore >= 30 && '🟢 '}
              {accumScore <= -30 && '🔴 '}
              {accumLabel}
            </span>
          )}
        </div>
        {accum ? (
          <>
            <div className="tfa-score-row">
              <span className="tfa-score-num mono" style={{ color: accumColor }}>
                {accumScore >= 0 ? '+' : ''}{accumScore.toFixed(1)}
              </span>
              <span className="tfa-score-suffix">/ 100</span>
            </div>
            <div className="tfa-score-track">
              <div className="tfa-score-axis" />
              <div
                className="tfa-score-fill"
                style={{
                  left: accumScore >= 0 ? '50%' : `${accumPct}%`,
                  width: `${Math.abs(accumScore) / 2}%`,
                  background: accumColor,
                  boxShadow: `0 0 8px ${accumColor}`,
                }}
              />
            </div>
            <div className="tfa-score-axis-labels mono">
              <span>−100 dist</span>
              <span>0</span>
              <span>+100 accum</span>
            </div>

            {/* Sub-signals */}
            <details className="tfa-subsignals">
              <summary>signals breakdown ({accum.n_days}-day window)</summary>
              <div className="tfa-sub-row">
                <span className="tfa-sub-label">Chaikin Money Flow</span>
                <span className="mono">{(accum.cmf * 100).toFixed(1)}%</span>
                <span className="tfa-sub-hint">close-vs-range × volume, normalised</span>
              </div>
              <div className="tfa-sub-row">
                <span className="tfa-sub-label">Up vs Down vol</span>
                <span className="mono">
                  {accum.up_down_vol_ratio > 0 ? '+' : ''}{(accum.up_down_vol_ratio * 100).toFixed(0)}%
                </span>
                <span className="tfa-sub-hint">net of volume on green vs red days</span>
              </div>
              <div className="tfa-sub-row">
                <span className="tfa-sub-label">Close-position (5d)</span>
                <span className="mono">{(accum.close_position_5d * 100).toFixed(0)}%</span>
                <span className="tfa-sub-hint">avg close as % of intraday range — {'>'}50% = bulls in control</span>
              </div>
            </details>
          </>
        ) : (
          <p className="sepa-empty">Not enough OHLCV history for {ctx.ticker}.</p>
        )}
      </div>
    </div>
  );
}
