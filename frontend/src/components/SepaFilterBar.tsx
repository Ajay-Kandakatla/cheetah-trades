import type { Rating } from '../hooks/useSepa';
import { InfoButton } from './InfoButton';

const FilterInfo = (
  <>
    <p>Narrow the candidate list down to what you actually want to trade.</p>
    <p>
      The bar is grouped left→right in <strong>Minervini's order of priority</strong>:
      Trend &amp; Stage (the qualifier) → Setup → Entry timing → Volume →
      Smart money → Catalyst → Overlays → Type.
    </p>
    <ul>
      <li>
        <strong>Entry timing</strong> — the actionable verdict: <strong>Enter</strong>
        (clears the book entry gate now), <strong>Wait</strong> (setup forming), or
        <strong>Watch</strong>. Rank quality with the composite <strong>score</strong>
        (0-100) via the Sort menu — an app synthesis layered on Minervini's gates,
        not a book formula.
      </li>
      <li>
        <strong>Setup type</strong> — <strong>Volatility Contraction Pattern (VCP)</strong>
        is a tightening base with declining volume. <strong>Power Play</strong> is an
        explosive multi-week run-up off a stable base.
      </li>
      <li>
        <strong>Relative Strength (RS) minimum</strong> — only show stocks outperforming
        at least this percentile of the market over 12 months. Default 70 matches
        Minervini's Trend Template requirement.
      </li>
      <li>
        <strong>Dual Momentum ✓</strong> — Gary Antonacci's two-gate filter from{' '}
        <em>Dual Momentum Investing</em>. Only shows stocks where the 12-month
        return is positive (absolute momentum) AND beats SPY's 12-month return
        (relative momentum). A name that passes both is what the market is
        already paying for. Use the <strong>Sort: 12m / 6m / 3m / 1m return</strong>
        options to rank by momentum strength.
      </li>
    </ul>
  </>
);

export type SepaFilters = {
  rating: Rating | 'ALL';
  setup: 'ALL' | 'VCP' | 'POWER_PLAY';
  /** Timed-entry decision gate — mirrors the ENTER/WAIT/WATCH banner the
   *  card already shows (`entry_exit.decision`, backend/sepa/entry_exit.py).
   *  'ALL' = no gate. 'ENTER' = breakout actionable now; 'WAIT' = valid base,
   *  pivot not yet triggered (the Minervini "don't buy until it breaks out"
   *  state, p.203); 'HOLD_WATCH' = on the radar, no setup trigger. Optional so
   *  SepaV2's own DEFAULT_FILTERS keeps compiling. Added 2026-06-02. */
  decision?: 'ALL' | 'ENTER' | 'WAIT' | 'HOLD_WATCH';
  /** Tunes what the 🟢 Enter chip counts as a breakout (user 2026-06-02 —
   *  "it's ok to not have high volume breakout… they may have a breakout in the
   *  past week sometime"). 'TODAY' = strict same-day book gate (`is_buyable`);
   *  'WEEK' = setup_ready AND a volume breakout in the last ≤5 trading days;
   *  'ANY' = setup_ready, no breakout trigger required. Only affects Enter.
   *  Optional → SepaV2 keeps compiling; default 'TODAY' preserves strict. */
  breakoutWindow?: 'TODAY' | 'WEEK' | 'ANY';
  /** When true, keep only names with a textbook-tight pivot — final right-side
   *  contraction ≤ 5% (book pp.198/202; user 2026-06-02 "5% is good"). Optional
   *  so SepaV2 keeps compiling. */
  tightPivotOnly?: boolean;
  /** Keep only names already AT/through the pivot inside the +5% buy zone
   *  (pivotTiming GO / AT_PIVOT) — buyable now. Optional so SepaV2 keeps compiling. */
  buyZoneOnly?: boolean;
  /** Keep only names coiling within 5% BELOW the pivot (pivotTiming COILING/WAIT)
   *  — close to the trigger, a watch-for-the-break list. Optional. */
  nearPivotOnly?: boolean;
  /** Keep only names with a STRONG sales-confidence read (tier strong/explosive
   *  — ≥25% YoY revenue, Bonde's "preferred"). See lib sales score. Optional so
   *  SepaV2 keeps compiling. */
  salesStrongOnly?: boolean;
  rsMin: number;
  search: string;
  showAll: boolean;
  // Antonacci's two-gate filter: 12m return > 0 (abs mom) AND 12m return > SPY 12m.
  // When true, hides names that fail Dual Momentum.
  dmEligibleOnly: boolean;
  // Security type filter: 'all' (default), 'equity' (operating companies only),
  // 'etf' (funds only). Useful because ETFs and equities have different metrics.
  type: 'all' | 'equity' | 'etf';
  // Pioneer filter — narrows to tickers in any curated breakthrough theme
  // (AI infra, SMR nuclear, GLP-1, quantum, etc.).
  pioneerOnly: boolean;
  // Weinstein 4-stage filter. ALL = no stage gate. 1 = basing, 2 = advancing
  // (the canonical Minervini buy zone), 3 = topping (sell signal early-warn),
  // 4 = declining (red — hard sell / short candidate).
  stage: 'ALL' | 1 | 2 | 3 | 4;
  /** Minimum Buffett-style moat tier. 0 = no filter, 1 = NONE+, 2 = SOME+,
   *  3 = NARROW+, 4 = WIDE only. Tickers with no moat data are kept unless
   *  filter is ≥1 — then UNKNOWN is excluded. */
  moatMin: 0 | 1 | 2 | 3 | 4;
  /** When true, drop any candidate flagged with
   *  ``volume.accumulation_strength === 'distributing'`` OR
   *  ``volume.cmf_signal === 'outflow'``. Use this to keep the list focused
   *  on tape that's actually being accumulated by institutions — distributing
   *  names will sneak into other filters (e.g. high RS) even when they're
   *  rolling over on volume. */
  hideDistributing: boolean;
  /** When true (DEFAULT ON, Ajay 2026-06-10: "do not qualify unless we have
   *  1.5× average volume"), drop rows whose TODAY volume < 1.5× their 50-day
   *  average. Implemented as a default-on FILTER, not a change to the book's
   *  p.79 qualifier gate: 1.5× expanding volume is Minervini's ENTRY condition
   *  (p.203, already in is_buyable), while pre-breakout VCP bases are quiet by
   *  definition (pp.198–203) — one tap shows the coilers again. Rows with
   *  unknown volume are hidden while the chip is on. */
  volX15Only: boolean;
  hideEarningsSoon: boolean;
  /** When true, drop any candidate whose 13F whales signal is anything
   *  other than 'accumulating'. Tightens the list to names that BOTH
   *  passed SEPA AND have institutional capital flowing in over the last
   *  quarter — the "Whales + SEPA agree" buy-and-hold short-list. Added
   *  2026-05-28. Pure FE, reads from the existing whalesFlow map. */
  whalesAccumOnly: boolean;
  /** When true, drop any candidate whose TOP whale buyer isn't a Tier-S
   *  fund per src/lib/fundTiers.ts (legendary stock-pickers — Berkshire,
   *  Tiger, Coatue, Citadel, etc). Sits on top of whalesAccumOnly to
   *  produce the "smart money is accumulating" short-list. Same caveat
   *  as the fund-tier badge — historical reputation, not forward
   *  prediction. Added 2026-05-28. */
  hedgeFundTopBuyer: boolean;
  /** When true, drop candidates not on the POTUS-family disclosure list
   *  in src/lib/politicalDisclosures.ts (categories includes
   *  'potus_family'). Informational filter — disclosed positions don't
   *  predict outcomes; pairs well with other filters to narrow to names
   *  the user has political-context awareness about. Added 2026-05-28. */
  potusFamilyOnly: boolean;
  /** When true, drop candidates without U.S. government involvement
   *  per politicalDisclosures.ts (categories includes 'govt_investment'
   *  OR 'govt_contractor'). Catches CHIPS Act recipients, defense/govt
   *  contractors, and program participants. Added 2026-05-28. */
  usGovOnly: boolean;
  /** When true, drop candidates without insider cluster-buy activity in
   *  the last 30 days (≥3 unique insiders filed Form 4). Surfaces the
   *  Minervini/O'Neil bullish tell that multiple corporate officers are
   *  buying their own stock. Note: insider data is enriched on the top
   *  20 candidates per Full Scan with catalyst — names outside that
   *  enriched subset are dropped when the chip is on. Added 2026-05-29. */
  insiderClusterBuy: boolean;
  /** Emerging Momentum Leader filter (2026-06-01) — the "next ARM" fingerprint:
   *  RS leader at new highs + pocket pivot + heavy accumulation + CMF inflow.
   *  See lib/momentumLeader.ts. */
  momentumLeaderOnly: boolean;
  /** Venky's "weekly 21-SMA trend confirmation" filter (2026-05-29).
   *  When true, drops candidates where the latest weekly close isn't
   *  above the 21-week SMA OR where the SMA isn't sloping up. Mirrors
   *  the strategy debated in Ajay's WhatsApp trading group. */
  weekly21SmaPass: boolean;
  /** ATR%-cap filter — drops candidates whose 14-day ATR is more than
   *  `atrPctMax` % of price (too volatile to swing-trade). 0 = off. */
  atrPctMax: number;
  /** ADX-floor filter — requires 14-day ADX ≥ `adxMin` (confirms an
   *  actual trend, not chop). 0 = off. */
  adxMin: number;
  sortBy:
    | 'conviction'
    | 'score' | 'rs' | 'symbol' | 'closest_trigger' | 'most_buyable' | 'sales_confidence'
    | 'day_change' | 'day_change_abs'
    | 'dm_12m' | 'dm_6m' | 'dm_3m' | 'dm_1m' | 'dm_score'
    | 'moat'
    | 'pioneer'
    | 'price_asc' | 'price_desc'
    // Volume / setup sorts — added so the user can ask "show me the
    // names actually pumping volume + in a VCP base" instead of the
    // default composite which dilutes both signals.
    | 'vol_vcp' | 'vol_ratio' | 'vcp_first';
};

type Props = {
  filters: SepaFilters;
  onChange: (next: SepaFilters) => void;
  /** Reset every filter to defaults (clears the glow + the ticker search). */
  onClear?: () => void;
  total: number;
  shown: number;
};

const STAGE_OPTS = [
  { v: 'ALL' as const, label: 'Any stage', tip: 'No stage filter — all four stages mixed in the list.' },
  { v: 2 as const,     label: 'S2 Advance', tip: 'Stage 2 only — Weinstein/Minervini entry zone (price > 50 > 150 > 200 MA, 200 rising).' },
  { v: 3 as const,     label: 'S3 Topping', tip: 'Stage 3 only — distribution phase. 50-day rolled, price lost 50, still above 200. Sell-prep / tighten stops.' },
  { v: 4 as const,     label: 'S4 Decline', tip: 'Stage 4 only — confirmed downtrend (price < 50 < 150 < 200 MA, 200 falling). Sell longs / short candidate.' },
  { v: 1 as const,     label: 'S1 Basing', tip: 'Stage 1 only — sideways accumulation after a downtrend. Pre-entry zone; not yet trending.' },
];

const DECISION_OPTS = [
  { v: 'ALL' as const,        label: 'Any signal', tip: 'No entry-timing gate — show every decision state (Enter, Wait, Watch, Avoid).' },
  { v: 'ENTER' as const,      label: '🟢 Enter',    tip: 'ENTER NOW — the strict Minervini gate (pp.79-83/198-203): Trend Template + Stage 2 + a setup + not late-stage + liquid + a VOLUME-CONFIRMED breakout (high-volume breakout or pocket pivot). The real "you may enter this today" list, so on a quiet day it can be short — by design.' },
  { v: 'WAIT' as const,       label: '🟡 Wait',     tip: 'Valid base, but the pivot has not triggered yet — Minervini\'s "wait for the breakout" state (p.203). Most VCP bases live here. Tap a card\'s WAIT banner for the trigger price + distance + valid-through date.' },
  { v: 'HOLD_WATCH' as const, label: '⚪ Watch',    tip: 'On the radar — passes trend/RS but has no setup trigger. Keep watching for a base to form.' },
];

const BREAKOUT_OPTS = [
  { v: 'TODAY' as const, label: 'Today', tip: 'Strict Minervini entry point (p.203): Enter = a VOLUME-CONFIRMED breakout TODAY (the strict book gate). The shortest, most disciplined list.' },
  { v: 'WEEK' as const,  label: '≤1wk',  tip: 'Relax Enter to names that broke out on volume within the last ~5 trading days AND are still set up — you can buy in the days following a breakout while it holds above the pivot.' },
  { v: 'ANY' as const,   label: 'Any',   tip: 'Drop the breakout trigger entirely: Enter = setup-ready (Trend Template + Stage 2 + base + not-late + liquid). The "ready to go, no trigger required" view.' },
];

const MOAT_OPTS = [
  { v: 0 as const, label: 'Any moat', tip: 'No moat filter — show all candidates regardless of moat score.' },
  { v: 2 as const, label: '🏰 Some+',  tip: 'At least SOME moat — score ≥ 40. Filters out commodity/cyclical names with no measurable moat.' },
  { v: 3 as const, label: '🏰 Narrow+', tip: 'NARROW moat or wider — score ≥ 60. Quality compounders only.' },
  { v: 4 as const, label: '🏰 Wide',    tip: 'WIDE moat only — score ≥ 80. Coca-Cola / Visa / Microsoft tier (Buffett\'s ideal).' },
] as const;

export function SepaFilterBar({ filters, onChange, onClear, total, shown }: Props) {
  const set = <K extends keyof SepaFilters>(k: K, v: SepaFilters[K]) =>
    onChange({ ...filters, [k]: v });

  // Decision gate selection (optional field — treat missing as 'ALL' so
  // SepaV2, which doesn't seed it, still renders the "Any signal" default).
  const decSel = filters.decision ?? 'ALL';
  // Breakout-recency window for the Enter gate (default 'TODAY' = strict).
  const bwSel = filters.breakoutWindow ?? 'TODAY';

  // How many filters are ACTIVELY narrowing the list (non-default state).
  // Drives the "N filters on" badge. Per-control glow is handled in CSS:
  // any selected non-default chip (`.is-active` without `.sepa-chip--passive`)
  // glows amber, plus the RS slider / ticker search when engaged. Added
  // 2026-05-30 — user: "very confusing when this filter is on."
  const activeCount = [
    filters.setup !== 'ALL',
    (filters.decision ?? 'ALL') !== 'ALL',
    (filters.breakoutWindow ?? 'TODAY') !== 'TODAY',
    filters.tightPivotOnly,
    filters.buyZoneOnly,
    filters.nearPivotOnly,
    filters.salesStrongOnly,
    filters.stage !== 'ALL',
    filters.moatMin !== 0,
    filters.type !== 'all',
    filters.rsMin > 0,
    filters.search.trim() !== '',
    filters.dmEligibleOnly,
    filters.volX15Only,
    filters.hideEarningsSoon,
    filters.hideDistributing,
    filters.whalesAccumOnly,
    filters.hedgeFundTopBuyer,
    filters.potusFamilyOnly,
    filters.usGovOnly,
    filters.insiderClusterBuy,
    filters.momentumLeaderOnly,
    filters.weekly21SmaPass,
    filters.atrPctMax > 0,
    filters.adxMin > 0,
    filters.pioneerOnly,
    filters.showAll,
  ].filter(Boolean).length;

  return (
    <div className="sepa-filterbar">
      <InfoButton title="Filters">{FilterInfo}</InfoButton>
      {/* Chips grouped into labeled categories, ordered left→right by
          Minervini's priority (user 2026-06-02): the Trend Template qualifier
          first (p.79), then the base/setup (pp.197-205), the entry trigger
          (p.203), volume confirmation, institutional sponsorship (p.195), then
          catalyst/context and non-Minervini overlays. RS≥70 is the slider in the
          controls row below. */}
      <div className="sepa-filterbar__group">

        {/* TIER filter removed 2026-06-21 (Ajay: rely on Enter/Watch, drop the
            Buy/Strong-Buy tier). The composite score still ranks names via the
            Sort menu; the actionable verdict is the Entry-timing Enter signal. */}

        {/* 📈 TREND & STAGE — Minervini's qualifier (p.79): a Stage-2 advance
            (Weinstein 4-stage). RS≥70, the 8th Trend Template gate, is the
            slider in the controls row. */}
        <div className="sepa-filterbar__cat-group">
          <span className="sepa-filterbar__cat-label" title="Minervini's qualifier — Stage 2 + the Trend Template (book p.79). The non-negotiable foundation.">📈 Trend &amp; Stage</span>
          {STAGE_OPTS.map(({ v, label, tip }) => (
            <button
              key={String(v)}
              className={`sepa-chip ${filters.stage === v ? 'is-active' : ''} ${
                v === 3 ? 'sepa-chip--warn' : v === 4 ? 'sepa-chip--bad' : ''
              } ${v === 'ALL' ? 'sepa-chip--passive' : ''}`}
              onClick={() => set('stage', v)}
              title={tip}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 🧱 SETUP — the base: VCP / Power Play (pp.197-205) + the textbook-tight
            ≤5% pivot (pp.198/202). */}
        <div className="sepa-filterbar__cat-group">
          <span className="sepa-filterbar__cat-label" title="The base structure — Volatility Contraction Pattern / Power Play (book pp.197-205).">🧱 Setup</span>
          {(['ALL', 'VCP', 'POWER_PLAY'] as const).map((s) => (
            <button
              key={s}
              className={`sepa-chip ${filters.setup === s ? 'is-active' : ''} ${s === 'ALL' ? 'sepa-chip--passive' : ''}`}
              onClick={() => set('setup', filters.setup === s ? 'ALL' : s)}
              title={
                s === 'VCP' ? 'Show only names whose entry setup is a Volatility Contraction Pattern. Tap again to turn off.' :
                s === 'POWER_PLAY' ? 'Show only Power Play (high-tight-flag) setups. Tap again to turn off.' :
                'No setup filter — show every candidate regardless of setup.'
              }
            >
              {s === 'ALL' ? 'Any setup' : s === 'POWER_PLAY' ? 'Power Play' : s}
            </button>
          ))}
          <button
            className={`sepa-chip ${filters.tightPivotOnly ? 'is-active' : ''}`}
            onClick={() => set('tightPivotOnly', !filters.tightPivotOnly)}
            title="Only names whose FINAL contraction is ≤ 5% — the textbook-tight Minervini pivot (book pp.198/202: FSII 5% handle, VIVO 3%). The genuinely book-tight setups, where a break on volume is the cleanest entry."
          >
            ⚡ Tight pivot ≤5%
          </button>
          <button
            className={`sepa-chip ${filters.nearPivotOnly ? 'is-active' : ''}`}
            onClick={() => set('nearPivotOnly', !filters.nearPivotOnly)}
            title="Close to the trigger — coiling within 5% BELOW the pivot (not yet broken out). Your watch-for-the-break list (book pp.198-205: buy as it crosses the pivot on volume)."
          >
            ◓ Close to trigger
          </button>
          <button
            className={`sepa-chip ${filters.buyZoneOnly ? 'is-active' : ''}`}
            onClick={() => set('buyZoneOnly', !filters.buyZoneOnly)}
            title="In the entry zone now — at/through the pivot and within the +5% entry zone (not extended, not a non-Stage-2 false break). Enter today on the book's cross-the-pivot rule (p.203)."
          >
            ● In enter zone
          </button>
        </div>

        {/* 🎯 ENTRY TIMING — the trigger: buy the breakout above the pivot on
            expanding volume (p.203). Decision = Enter/Wait/Watch; the Breakout
            sub-control tunes how recent the breakout must be. */}
        <div className="sepa-filterbar__cat-group">
          <span className="sepa-filterbar__cat-label" title="The buy trigger — break above the pivot on expanding volume (book p.203).">🎯 Entry timing</span>
          {DECISION_OPTS.map(({ v, label, tip }) => (
            <button
              key={`dec-${v}`}
              className={`sepa-chip ${decSel === v ? 'is-active' : ''} ${
                v === 'ENTER' ? 'sepa-chip--good' : ''
              } ${v === 'ALL' ? 'sepa-chip--passive' : ''}`}
              onClick={() => set('decision', decSel === v ? 'ALL' : v)}
              title={tip}
            >
              {label}
            </button>
          ))}
          <span
            className="mono"
            style={{ opacity: 0.7, fontSize: '0.74rem', alignSelf: 'center' }}
            title="Tunes what the 🟢 Enter chip counts as a breakout. Only affects the Enter chip."
          >
            ⚡ Breakout
          </span>
          {BREAKOUT_OPTS.map(({ v, label, tip }) => (
            <button
              key={`bw-${v}`}
              className={`sepa-chip ${bwSel === v ? 'is-active' : ''} ${v === 'TODAY' ? 'sepa-chip--passive' : ''}`}
              onClick={() => set('breakoutWindow', v)}
              title={tip}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 📊 VOLUME & MOMENTUM — accumulation vs distribution (book p.71-72,
            203) + emerging RS leaders breaking out with no base yet. */}
        <div className="sepa-filterbar__cat-group">
          <span className="sepa-filterbar__cat-label" title="Volume confirmation — accumulation vs distribution (book p.71-72, 203).">📊 Volume</span>
          <button
            className={`sepa-chip ${filters.volX15Only ? 'is-active' : ''}`}
            onClick={() => set('volX15Only', !filters.volX15Only)}
            title="Only show names trading ≥1.5× their 50-day average volume TODAY (default ON). This is the book's ENTRY volume condition (p.203) used as a view filter — turn it OFF to see quiet pre-breakout VCP coilers, which are low-volume by definition (pp.198-203). Unknown-volume rows are hidden while on."
          >
            ⚡ ≥1.5× Volume
          </button>
          <button
            className={`sepa-chip ${filters.hideEarningsSoon ? 'is-active' : ''}`}
            onClick={() => set('hideEarningsSoon', !filters.hideEarningsSoon)}
            title="Hide names reporting earnings within 7 days (default ON — the ATEX lesson: a chart can pass every gate hours before a -28% earnings miss). Buying into a report is a gap bet, not a SEPA entry. Turn OFF to see them; each still carries the ⚠ ER chip. Dates from yfinance — verify on EarningsWhispers."
          >
            🚫 ER ≤7d
          </button>
          <button
            className={`sepa-chip ${filters.hideDistributing ? 'is-active' : ''}`}
            onClick={() => set('hideDistributing', !filters.hideDistributing)}
            title="Hide tickers being institutionally distributed (red 'Distributing' pill) or showing money outflow on CMF. Tightens the list to genuinely accumulating names."
          >
            🚫 Hide Distributing
          </button>
          <button
            className={`sepa-chip ${filters.momentumLeaderOnly ? 'is-active' : ''}`}
            onClick={() => set('momentumLeaderOnly', !filters.momentumLeaderOnly)}
            title="Only show Emerging Momentum Leaders — the ARM/DDOG fingerprint: an RS leader at new highs (no overhead) with a pocket pivot, heavy net buying (up/down vol ≥ 1.9) and CMF inflow. Catches fast movers that have no base, so they normally score 'no setup'."
          >
            🚀 Momentum Leader
          </button>
        </div>

        {/* 🐋 SMART MONEY — institutional sponsorship (book p.195: "limit your
            selections to those supported by institutional buying"). */}
        <div className="sepa-filterbar__cat-group">
          <span className="sepa-filterbar__cat-label" title="Institutional sponsorship — supported by institutional buying (book p.195).">🐋 Smart money</span>
          <button
            className={`sepa-chip ${filters.whalesAccumOnly ? 'is-active' : ''}`}
            onClick={() => set('whalesAccumOnly', !filters.whalesAccumOnly)}
            title="Only show candidates whose 13F whales flow is 'accumulating' (n_buying > n_selling × 1.5). Tightens the list to names that passed SEPA AND have institutional capital flowing in. Pairs well with Hide Distributing for the full whales+tape agreement short-list."
          >
            🐋 Whales Accumulating
          </button>
          <button
            className={`sepa-chip ${filters.hedgeFundTopBuyer ? 'is-active' : ''}`}
            onClick={() => set('hedgeFundTopBuyer', !filters.hedgeFundTopBuyer)}
            title="Only show candidates whose top whale BUYER matches ANY hedge fund on the curated Tier-S list in src/lib/fundTiers.ts (Berkshire, Tiger Global, Coatue, Citadel, Pershing Square, Greenlight, Soros, Renaissance, D.E. Shaw, Two Sigma, Bridgewater, AQR, Millennium, Point72, Lone Pine, Viking Global, Maverick, Whale Rock, Glenview, Trian, Starboard, Icahn, ValueAct, Jana, Pelican, Altimeter, Scion, and more). Match is case-insensitive substring on the top_buy fund name. Tier S = historical active alpha reputation, NOT a forward prediction. Pair with Whales Accumulating for the 'smart money is buying' short-list."
          >
            🦅 Hedge Fund Top Buyer
          </button>
        </div>

        {/* 🗞️ CATALYST & CONTEXT — insider cluster buys (O'Neil/Minervini tell),
            political-disclosure context, and breakthrough themes. */}
        <div className="sepa-filterbar__cat-group">
          <span className="sepa-filterbar__cat-label" title="Supporting context — insider buying, political disclosures, breakthrough themes.">🗞️ Catalyst</span>
          <button
            className={`sepa-chip ${filters.insiderClusterBuy ? 'is-active' : ''}`}
            onClick={() => set('insiderClusterBuy', !filters.insiderClusterBuy)}
            title="Only show candidates where ≥3 unique insiders filed Form 4 buys in the last 30 days (cluster-buy signal — bullish tell per Minervini / O'Neil Ch 13). Insider enrichment runs on the top 20 candidates after Full Scan with 'Include catalyst' — names outside that enriched subset will be excluded when this filter is on."
          >
            🟢 Insider Cluster Buy
          </button>
          <button
            className={`sepa-chip ${filters.potusFamilyOnly ? 'is-active' : ''}`}
            onClick={() => set('potusFamilyOnly', !filters.potusFamilyOnly)}
            title="Only show candidates on the curated POTUS-family disclosure list (NVDA, MSFT, AAPL, NOW, AMD, GOOGL, INTC, PLTR, HOOD, etc — full list in src/lib/politicalDisclosures.ts). Informational context flag — disclosed positions don't predict outcomes. Use as ONE signal among many."
          >
            🏛️ POTUS Family
          </button>
          <button
            className={`sepa-chip ${filters.usGovOnly ? 'is-active' : ''}`}
            onClick={() => set('usGovOnly', !filters.usGovOnly)}
            title="Only show candidates with direct U.S. government involvement — CHIPS Act recipients (e.g., INTC), major govt contractors (e.g., PLTR), or program participants (e.g., HOOD as Trump Accounts trustee). Curated in src/lib/politicalDisclosures.ts. Same caveat as POTUS Family — informational context, not a buy signal."
          >
            🇺🇸 US Gov
          </button>
          <button
            className={`sepa-chip ${filters.pioneerOnly ? 'is-active' : ''}`}
            onClick={() => set('pioneerOnly', !filters.pioneerOnly)}
            title="Show only tickers tagged as part of a curated breakthrough theme (AI infra, AI storage, SMR nuclear, quantum, GLP-1, etc.). See the Pioneers nav tab for the full breakdown."
          >
            🚀 Pioneer
          </button>
        </div>

        {/* 🧩 OVERLAYS — non-Minervini frameworks layered on top: Buffett moat,
            Antonacci Dual Momentum, Venky's 21W-SMA / ATR / ADX. */}
        <div className="sepa-filterbar__cat-group">
          <span className="sepa-filterbar__cat-label" title="Other frameworks layered on top of Minervini (Buffett moat, Antonacci dual momentum, Venky's filters).">🧩 Overlays</span>
          {MOAT_OPTS.map(({ v, label, tip }) => (
            <button
              key={`moat-${v}`}
              className={`sepa-chip ${filters.moatMin === v ? 'is-active' : ''} ${v === 0 ? 'sepa-chip--passive' : ''}`}
              onClick={() => set('moatMin', v)}
              title={tip}
            >
              {label}
            </button>
          ))}
          <button
            className={`sepa-chip ${filters.dmEligibleOnly ? 'is-active' : ''}`}
            onClick={() => set('dmEligibleOnly', !filters.dmEligibleOnly)}
            title="Antonacci's Dual Momentum two-gate filter: 12m return positive AND beats SPY"
          >
            Dual Momentum ✓
          </button>
          <button
            className={`sepa-chip ${filters.weekly21SmaPass ? 'is-active' : ''}`}
            onClick={() => set('weekly21SmaPass', !filters.weekly21SmaPass)}
            title="Venky's filter: only candidates where the latest weekly close is above the 21-week SMA AND that SMA is sloping up over the last 4 weeks. 'Trend confirmation, inclined not flat.'"
          >
            📈 21W SMA ↑
          </button>
          <button
            className={`sepa-chip ${filters.atrPctMax > 0 ? 'is-active' : ''}`}
            onClick={() => set('atrPctMax', filters.atrPctMax > 0 ? 0 : 8)}
            title={
              filters.atrPctMax > 0
                ? `Active: dropping names with ATR% > ${filters.atrPctMax}%. Tap to disable.`
                : "Cap ATR (14-day) at 8% of price — drops names too volatile for swing-trade stops. Tap to enable."
            }
          >
            📐 ATR% ≤ {filters.atrPctMax > 0 ? filters.atrPctMax : 8}
          </button>
          <button
            className={`sepa-chip ${filters.adxMin > 0 ? 'is-active' : ''}`}
            onClick={() => set('adxMin', filters.adxMin > 0 ? 0 : 25)}
            title={
              filters.adxMin > 0
                ? `Active: requiring ADX ≥ ${filters.adxMin}. Tap to disable.`
                : "Require ADX (14-day) ≥ 25 — Wilder threshold for a real trend (vs chop). Tap to enable."
            }
          >
            🎯 ADX ≥ {filters.adxMin > 0 ? filters.adxMin : 25}
          </button>
          <button
            className={`sepa-chip ${filters.salesStrongOnly ? 'is-active' : ''}`}
            onClick={() => set('salesStrongOnly', !filters.salesStrongOnly)}
            title="Pradeep Bonde / Stockbee: only names with STRONG sales — Sales-Confidence tier 'strong' or 'explosive' (≥25% YoY revenue growth, his 'preferred' bar). The 'stocks driven by sales' short-list. Sort by '📈 Sales confidence' to rank within it."
          >
            🚀 Strong Sales
          </button>
        </div>

        {/* 🔎 TYPE — utility: operating companies vs ETFs. */}
        <div className="sepa-filterbar__cat-group">
          <span className="sepa-filterbar__cat-label" title="Security type — operating companies vs ETFs.">🔎 Type</span>
          {(['all', 'equity', 'etf'] as const).map((t) => (
            <button
              key={t}
              className={`sepa-chip ${filters.type === t ? 'is-active' : ''} ${t === 'all' ? 'sepa-chip--passive' : ''}`}
              onClick={() => set('type', t)}
              title={
                t === 'all' ? 'Show both operating companies and ETFs' :
                t === 'equity' ? 'Operating companies only — Earnings Per Share / fundamentals apply' :
                'Exchange-Traded Funds (ETFs) only — show AUM / expense ratio / holdings instead of EPS'
              }
            >
              {t === 'all' ? 'All types' : t === 'equity' ? 'Equity' : 'ETF'}
            </button>
          ))}
        </div>
      </div>

      <div className="sepa-filterbar__group">
        <label className={`sepa-filterbar__field ${filters.rsMin > 0 ? 'is-filtering' : ''}`}>
          <span className="mono">RS ≥ {filters.rsMin}</span>
          <input
            type="range"
            min={0}
            max={99}
            value={filters.rsMin}
            onChange={(e) => set('rsMin', Number(e.target.value))}
          />
        </label>
        <input
          type="search"
          className={`sepa-filterbar__search ${filters.search.trim() !== '' ? 'is-filtering' : ''}`}
          placeholder="Filter ticker…"
          value={filters.search}
          onChange={(e) => set('search', e.target.value.toUpperCase())}
        />
        <select
          className="sepa-filterbar__select"
          value={filters.sortBy}
          onChange={(e) => set('sortBy', e.target.value as SepaFilters['sortBy'])}
        >
          {/* Momentum-led conviction rank (volume + dried volume + momentum,
              backend sepa/conviction.py, TLSW p.34/79). Default sort: the names
              with the most return potential first, Enter-eligible on top, climax
              names suppressed to the bottom (Ajay 2026-06-22). */}
          <option value="conviction">Sort: 🏆 Conviction (most return potential)</option>
          <option value="most_buyable">Sort: 🎯 Most ready to Enter (VCP)</option>
          <option value="sales_confidence">Sort: 📈 Sales confidence (Bonde)</option>
          <option value="score">Sort: Score</option>
          <option value="closest_trigger">Sort: ⚡ Closest to trigger</option>
          <option value="rs">Sort: RS rank</option>
          <option value="day_change">Sort: Day % (top gainers)</option>
          <option value="day_change_abs">Sort: Day % |abs| (movers)</option>
          <option value="dm_12m">Sort: 12m return</option>
          <option value="dm_6m">Sort: 6m return</option>
          <option value="dm_3m">Sort: 3m return</option>
          <option value="dm_1m">Sort: 1m return</option>
          <option value="dm_score">Sort: Dual-Momentum score</option>
          <option value="moat">Sort: Moat score (Buffett)</option>
          <option value="pioneer">Sort: Pioneer theme count</option>
          <option value="price_asc">Sort: Price ↑ (low to high)</option>
          <option value="price_desc">Sort: Price ↓ (high to low)</option>
          <option value="symbol">Sort: Ticker</option>
          {/* Volume / VCP sorts. The default "Sort: Score" hides pure
              volume + setup signal under a 100-point composite where
              they together contribute only 20% (volume 5 + setup 15).
              These three sorts let the user surface the *real* volume
              + VCP leaders without trend-template / RS / fundamentals
              diluting the ranking.

              "Volume strength" = up/down vol ratio (sum of up-day vol
              divided by down-day vol over 50 bars) plus a boost for
              high-volume breakout flag plus a boost for the accumulation
              flag. Higher = more under accumulation. */}
          <option value="vol_vcp">Sort: VCP + Accumulation (combined)</option>
          <option value="vol_ratio">Sort: Volume strength (accumulation + breakout)</option>
          <option value="vcp_first">Sort: VCP/PowerPlay setups first</option>
        </select>
        {/* Quick-access price-sort pills — same effect as the dropdown,
            one-tap access since this is a sort users hit often when
            scanning for affordable entries vs heavyweight leaders. */}
        <div className="sepa-filterbar__group" role="group" aria-label="Sort by price">
          <button
            type="button"
            className={`sepa-pill ${filters.sortBy === 'price_asc' ? 'sepa-pill--active' : ''}`}
            onClick={() => set('sortBy', filters.sortBy === 'price_asc' ? 'score' : 'price_asc')}
            title="Sort by stock price, cheapest first. Click again to reset to Score."
          >
            $ Price ↑
          </button>
          <button
            type="button"
            className={`sepa-pill ${filters.sortBy === 'price_desc' ? 'sepa-pill--active' : ''}`}
            onClick={() => set('sortBy', filters.sortBy === 'price_desc' ? 'score' : 'price_desc')}
            title="Sort by stock price, priciest first. Click again to reset to Score."
          >
            $ Price ↓
          </button>
        </div>
        <label className={`sepa-filterbar__toggle mono ${filters.showAll ? 'is-filtering' : ''}`}>
          <input
            type="checkbox"
            checked={filters.showAll}
            onChange={(e) => set('showAll', e.target.checked)}
          />
          {' '}all analyzed
        </label>
      </div>

      <div className="sepa-filterbar__count mono">
        {activeCount > 0 && (
          onClear ? (
            <button
              type="button"
              className="sepa-filterbar__active-badge sepa-filterbar__active-badge--btn"
              onClick={onClear}
              title="Clear all filters — tap to reset everything (including the ticker search) and show the full list."
            >
              ● {activeCount} filter{activeCount === 1 ? '' : 's'} on · ✕ clear
            </button>
          ) : (
            <span
              className="sepa-filterbar__active-badge"
              title="Number of filters actively narrowing the list. Glowing controls above are the ones that are on."
            >
              ● {activeCount} filter{activeCount === 1 ? '' : 's'} on
            </span>
          )
        )}
        showing <strong>{shown}</strong> / {total}
      </div>
    </div>
  );
}
