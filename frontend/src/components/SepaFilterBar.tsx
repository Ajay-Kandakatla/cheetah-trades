import type { Rating } from '../hooks/useSepa';
import { InfoButton } from './InfoButton';

const FilterInfo = (
  <>
    <p>Narrow the candidate list down to what you actually want to trade.</p>
    <ul>
      <li>
        <strong>Rating tier</strong> — Strong Buy, Buy, Watch. Tier comes from the
        composite score (0-100): Strong Buy ≥ 85, Buy ≥ 70, Watch ≥ 60.
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
    | 'score' | 'rs' | 'symbol'
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

const RATINGS: Array<Rating | 'ALL'> = ['ALL', 'STRONG_BUY', 'BUY', 'WATCH'];

export function SepaFilterBar({ filters, onChange, onClear, total, shown }: Props) {
  const set = <K extends keyof SepaFilters>(k: K, v: SepaFilters[K]) =>
    onChange({ ...filters, [k]: v });

  // Decision gate selection (optional field — treat missing as 'ALL' so
  // SepaV2, which doesn't seed it, still renders the "Any signal" default).
  const decSel = filters.decision ?? 'ALL';

  // How many filters are ACTIVELY narrowing the list (non-default state).
  // Drives the "N filters on" badge. Per-control glow is handled in CSS:
  // any selected non-default chip (`.is-active` without `.sepa-chip--passive`)
  // glows amber, plus the RS slider / ticker search when engaged. Added
  // 2026-05-30 — user: "very confusing when this filter is on."
  const activeCount = [
    filters.rating !== 'ALL',
    filters.setup !== 'ALL',
    (filters.decision ?? 'ALL') !== 'ALL',
    filters.stage !== 'ALL',
    filters.moatMin !== 0,
    filters.type !== 'all',
    filters.rsMin > 0,
    filters.search.trim() !== '',
    filters.dmEligibleOnly,
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
      <div className="sepa-filterbar__group">
        {RATINGS.map((r) => (
          <button
            key={r}
            className={`sepa-chip ${filters.rating === r ? 'is-active' : ''} ${r === 'ALL' ? 'sepa-chip--passive' : ''}`}
            onClick={() => set('rating', r)}
          >
            {r === 'ALL' ? 'All' : r.replace('_', ' ').toLowerCase()}
          </button>
        ))}
        <span className="sepa-filterbar__sep" />
        {(['ALL', 'VCP', 'POWER_PLAY'] as const).map((s) => (
          <button
            key={s}
            className={`sepa-chip ${filters.setup === s ? 'is-active' : ''} ${s === 'ALL' ? 'sepa-chip--passive' : ''}`}
            // Tap an active setup chip again to clear it back to "Any setup" —
            // gives VCP / Power Play simple on/off behavior (user request
            // 2026-06-02: "a filter to turn VCP on and off").
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
        <span className="sepa-filterbar__sep" />
        {/* Timed-entry decision filter (2026-06-02) — mirrors the ENTER / WAIT /
            WATCH banner each card already shows (entry_exit.decision). Most VCP
            bases sit in WAIT until the pivot breaks: Minervini p.203 — you don't
            buy the base, you buy the breakout. ENTER = actionable now. Lets the
            user flip "show me what's basing (Wait)" vs "what's triggering now
            (Enter)" without reading every card. */}
        {([
          { v: 'ALL' as const,        label: 'Any signal', tip: 'No entry-timing gate — show every decision state (Enter, Wait, Watch, Avoid).' },
          { v: 'ENTER' as const,      label: '🟢 Enter',    tip: 'Breakout is actionable now — price at/through the pivot with the entry window open. Matches the card\'s green ENTER banner.' },
          { v: 'WAIT' as const,       label: '🟡 Wait',     tip: 'Valid base, but the pivot has not triggered yet — Minervini\'s "wait for the breakout" state (p.203). Most VCP bases live here. Tap a card\'s WAIT banner to see the trigger price + distance + valid-through date.' },
          { v: 'HOLD_WATCH' as const, label: '⚪ Watch',    tip: 'On the radar — passes trend/RS but has no setup trigger. Keep watching for a base to form.' },
        ]).map(({ v, label, tip }) => (
          <button
            key={`dec-${v}`}
            className={`sepa-chip ${decSel === v ? 'is-active' : ''} ${
              v === 'ENTER' ? 'sepa-chip--good' : ''
            } ${v === 'ALL' ? 'sepa-chip--passive' : ''}`}
            // Same toggle behavior as the setup chips — tap the active one to
            // clear back to "Any signal".
            onClick={() => set('decision', decSel === v ? 'ALL' : v)}
            title={tip}
          >
            {label}
          </button>
        ))}
        <span className="sepa-filterbar__sep" />
        {/* Weinstein stage filter — fastest way to flip from "what to buy"
            (Stage 2) to "what's topping out" (Stage 3) or "what just rolled
            over" (Stage 4). Stage 4 names are sell-now / short candidates. */}
        {([
          { v: 'ALL' as const,       label: 'Any stage', tip: 'No stage filter — all four stages mixed in the list.' },
          { v: 2 as const,           label: 'S2 Advance', tip: 'Stage 2 only — Weinstein/Minervini buy zone (price > 50 > 150 > 200 MA, 200 rising).' },
          { v: 3 as const,           label: 'S3 Topping', tip: 'Stage 3 only — distribution phase. 50-day rolled, price lost 50, still above 200. Sell-prep / tighten stops.' },
          { v: 4 as const,           label: 'S4 Decline', tip: 'Stage 4 only — confirmed downtrend (price < 50 < 150 < 200 MA, 200 falling). Sell longs / short candidate.' },
          { v: 1 as const,           label: 'S1 Basing', tip: 'Stage 1 only — sideways accumulation after a downtrend. Pre-buy zone; not yet trending.' },
        ]).map(({v, label, tip}) => (
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
        <span className="sepa-filterbar__sep" />
        {/* Buffett moat filter — minimum tier the candidate must meet.
            Tiers: 0=any, 1=NONE+, 2=SOME+, 3=NARROW+, 4=WIDE only.
            UNKNOWN (data missing) is included only when moatMin=0. */}
        {([
          { v: 0 as const, label: 'Any moat', tip: 'No moat filter — show all candidates regardless of moat score.' },
          { v: 2 as const, label: '🏰 Some+',  tip: 'At least SOME moat — score ≥ 40. Filters out commodity/cyclical names with no measurable moat.' },
          { v: 3 as const, label: '🏰 Narrow+', tip: 'NARROW moat or wider — score ≥ 60. Quality compounders only.' },
          { v: 4 as const, label: '🏰 Wide',    tip: 'WIDE moat only — score ≥ 80. Coca-Cola / Visa / Microsoft tier (Buffett\'s ideal).' },
        ] as const).map(({v, label, tip}) => (
          <button
            key={`moat-${v}`}
            className={`sepa-chip ${filters.moatMin === v ? 'is-active' : ''} ${v === 0 ? 'sepa-chip--passive' : ''}`}
            onClick={() => set('moatMin', v)}
            title={tip}
          >
            {label}
          </button>
        ))}
        <span className="sepa-filterbar__sep" />
        <button
          className={`sepa-chip ${filters.dmEligibleOnly ? 'is-active' : ''}`}
          onClick={() => set('dmEligibleOnly', !filters.dmEligibleOnly)}
          title="Antonacci's Dual Momentum two-gate filter: 12m return positive AND beats SPY"
        >
          Dual Momentum ✓
        </button>
        {/* Hide-distributing chip. When active, the list drops any name
            tagged accumulation_strength === 'distributing' or with money
            outflow (cmf). Useful because high RS + high score don't
            preclude a stock from being heavily distributed — see the
            Minervini sell-signal layer for why this matters. */}
        <button
          className={`sepa-chip ${filters.hideDistributing ? 'is-active' : ''}`}
          onClick={() => set('hideDistributing', !filters.hideDistributing)}
          title="Hide tickers being institutionally distributed (red 'Distributing' pill) or showing money outflow on CMF. Tightens the list to genuinely accumulating names."
        >
          🚫 Hide Distributing
        </button>
        {/* Whales-accumulating filter — narrows the SEPA list to names
            where 13F institutional flow over the last quarter was net
            accumulating (n_buying >> n_selling). Pairs with Hide
            Distributing for the full "whales agree + tape agrees"
            short-list: institutions adding (quarterly) AND volume
            accumulation (daily). Added 2026-05-28 per user request
            "Can you add a chip for whale only filter". */}
        <button
          className={`sepa-chip ${filters.whalesAccumOnly ? 'is-active' : ''}`}
          onClick={() => set('whalesAccumOnly', !filters.whalesAccumOnly)}
          title="Only show candidates whose 13F whales flow is 'accumulating' (n_buying > n_selling × 1.5). Tightens the list to names that passed SEPA AND have institutional capital flowing in. Pairs well with Hide Distributing for the full whales+tape agreement short-list."
        >
          🐋 Whales Accumulating
        </button>
        {/* Hedge-fund top-buyer filter — narrows further to names where
            the LEADING whale buyer is a Tier-S fund per the curated
            fundTiers.ts list (Berkshire, Tiger Global, Coatue, Citadel,
            Pershing Square, Altimeter, etc). Stacks on top of Whales
            Accumulating: the chip is most useful when both are on.
            Same honesty caveat as the fund-tier badge — historical
            reputation, not forward prediction. */}
        <button
          className={`sepa-chip ${filters.hedgeFundTopBuyer ? 'is-active' : ''}`}
          onClick={() => set('hedgeFundTopBuyer', !filters.hedgeFundTopBuyer)}
          title="Only show candidates whose top whale BUYER matches ANY hedge fund on the curated Tier-S list in src/lib/fundTiers.ts (Berkshire, Tiger Global, Coatue, Citadel, Pershing Square, Greenlight, Soros, Renaissance, D.E. Shaw, Two Sigma, Bridgewater, AQR, Millennium, Point72, Lone Pine, Viking Global, Maverick, Whale Rock, Glenview, Trian, Starboard, Icahn, ValueAct, Jana, Pelican, Altimeter, Scion, and more). Match is case-insensitive substring on the top_buy fund name — 'any hedge fund' on the curated list counts. Tier S = historical active alpha reputation, NOT a forward prediction. Pair with Whales Accumulating for the 'smart money is buying' short-list."
        >
          🦅 Hedge Fund Top Buyer
        </button>
        {/* POTUS Family filter — narrows the SEPA list to candidates
            that appear in the curated POTUS-family disclosure list
            (src/lib/politicalDisclosures.ts). Informational only —
            disclosed positions don't predict outcomes; use as one
            context layer alongside Minervini + whales + volume. */}
        <button
          className={`sepa-chip ${filters.potusFamilyOnly ? 'is-active' : ''}`}
          onClick={() => set('potusFamilyOnly', !filters.potusFamilyOnly)}
          title="Only show candidates on the curated POTUS-family disclosure list (NVDA, MSFT, AAPL, NOW, AMD, GOOGL, INTC, PLTR, HOOD, etc — full list in src/lib/politicalDisclosures.ts). Informational context flag — disclosed positions don't predict outcomes. Use as ONE signal among many."
        >
          🏛️ POTUS Family
        </button>
        {/* US Gov filter — narrows to candidates with direct U.S.
            government involvement: CHIPS Act recipients (INTC), major
            govt contractors (PLTR), or program participants (HOOD as
            Trump Accounts trustee). Caught via the political-disclosure
            list's govt_investment / govt_contractor categories. */}
        <button
          className={`sepa-chip ${filters.usGovOnly ? 'is-active' : ''}`}
          onClick={() => set('usGovOnly', !filters.usGovOnly)}
          title="Only show candidates with direct U.S. government involvement — CHIPS Act recipients (e.g., INTC), major govt contractors (e.g., PLTR), or program participants (e.g., HOOD as Trump Accounts trustee). Curated in src/lib/politicalDisclosures.ts. Same caveat as POTUS Family — informational context, not a buy signal."
        >
          🇺🇸 US Gov
        </button>
        {/* Insider cluster-buy filter — narrows to candidates with ≥3
            unique insiders filing Form 4 buys in the last 30 days.
            Minervini/O'Neil bullish tell. Data is enriched on top 20
            candidates per Full Scan + catalyst — names outside the
            enriched subset are dropped when this is on. */}
        <button
          className={`sepa-chip ${filters.insiderClusterBuy ? 'is-active' : ''}`}
          onClick={() => set('insiderClusterBuy', !filters.insiderClusterBuy)}
          title="Only show candidates where ≥3 unique insiders filed Form 4 buys in the last 30 days (cluster-buy signal — bullish tell per Minervini / O'Neil Ch 13). Insider enrichment runs on the top 20 candidates after Full Scan with 'Include catalyst' — names outside that enriched subset will be excluded when this filter is on."
        >
          🟢 Insider Cluster Buy
        </button>
        {/* Emerging Momentum Leader (2026-06-01) — the "next ARM" fingerprint:
            RS leader at new highs + pocket pivot + heavy accumulation + CMF
            inflow. Surfaces fast momentum movers that score "no setup". */}
        <button
          className={`sepa-chip ${filters.momentumLeaderOnly ? 'is-active' : ''}`}
          onClick={() => set('momentumLeaderOnly', !filters.momentumLeaderOnly)}
          title="Only show Emerging Momentum Leaders — the ARM/DDOG fingerprint: an RS leader at new highs (no overhead) with a pocket pivot, heavy net buying (up/down vol ≥ 1.9) and CMF inflow. Catches fast momentum movers that have no base, so they normally score 'no setup'."
        >
          🚀 Momentum Leader
        </button>
        <span className="sepa-filterbar__sep" />
        {/* Venky's filter stack (2026-05-29): weekly 21-SMA confirmation,
            ATR% cap, ADX floor. Layered on top of SEPA — each chip is
            independent so the user can mix/match. */}
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
        <span className="sepa-filterbar__sep" />
        <button
          className={`sepa-chip ${filters.pioneerOnly ? 'is-active' : ''}`}
          onClick={() => set('pioneerOnly', !filters.pioneerOnly)}
          title="Show only tickers tagged as part of a curated breakthrough theme (AI infra, AI storage, SMR nuclear, quantum, GLP-1, etc.). See the Pioneers nav tab for the full breakdown."
        >
          🚀 Pioneer
        </button>
        <span className="sepa-filterbar__sep" />
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
          <option value="score">Sort: Score</option>
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
