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
  total: number;
  shown: number;
};

const RATINGS: Array<Rating | 'ALL'> = ['ALL', 'STRONG_BUY', 'BUY', 'WATCH'];

export function SepaFilterBar({ filters, onChange, total, shown }: Props) {
  const set = <K extends keyof SepaFilters>(k: K, v: SepaFilters[K]) =>
    onChange({ ...filters, [k]: v });

  return (
    <div className="sepa-filterbar">
      <InfoButton title="Filters">{FilterInfo}</InfoButton>
      <div className="sepa-filterbar__group">
        {RATINGS.map((r) => (
          <button
            key={r}
            className={`sepa-chip ${filters.rating === r ? 'is-active' : ''}`}
            onClick={() => set('rating', r)}
          >
            {r === 'ALL' ? 'All' : r.replace('_', ' ').toLowerCase()}
          </button>
        ))}
        <span className="sepa-filterbar__sep" />
        {(['ALL', 'VCP', 'POWER_PLAY'] as const).map((s) => (
          <button
            key={s}
            className={`sepa-chip ${filters.setup === s ? 'is-active' : ''}`}
            onClick={() => set('setup', s)}
          >
            {s === 'ALL' ? 'Any setup' : s === 'POWER_PLAY' ? 'Power Play' : s}
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
            }`}
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
            className={`sepa-chip ${filters.moatMin === v ? 'is-active' : ''}`}
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
            className={`sepa-chip ${filters.type === t ? 'is-active' : ''}`}
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
        <label className="sepa-filterbar__field">
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
          className="sepa-filterbar__search"
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
        <label className="sepa-filterbar__toggle mono">
          <input
            type="checkbox"
            checked={filters.showAll}
            onChange={(e) => set('showAll', e.target.checked)}
          />
          {' '}all analyzed
        </label>
      </div>

      <div className="sepa-filterbar__count mono">
        showing <strong>{shown}</strong> / {total}
      </div>
    </div>
  );
}
