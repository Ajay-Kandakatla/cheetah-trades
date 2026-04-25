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
    </ul>
  </>
);

export type SepaFilters = {
  rating: Rating | 'ALL';
  setup: 'ALL' | 'VCP' | 'POWER_PLAY';
  rsMin: number;
  search: string;
  showAll: boolean;
  sortBy: 'score' | 'rs' | 'symbol';
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
          <option value="symbol">Sort: Ticker</option>
        </select>
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
