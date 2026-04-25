import { useMemo, useState } from 'react';
import { WATCHLIST, TIER_META } from '../data/watchlist';
import type { WatchlistTier } from '../data/watchlist';

const TIERS: (WatchlistTier | 'All')[] = ['All', 'Hypersonic', 'Cheetah', 'Fast Mover', 'Strong Gainer'];
const SECTORS = ['All', 'Technology', 'Healthcare', 'Energy', 'Industrials', 'Consumer', 'Basic Materials', 'Utilities'];

type SortKey = 'rank' | 'symbol' | 'name' | 'sector' | 'ytd' | 'price';

interface Props {
  onSelect: (symbol: string) => void;
}

export function WatchlistSection({ onSelect }: Props) {
  const [search, setSearch] = useState('');
  const [tier, setTier] = useState<WatchlistTier | 'All'>('All');
  const [sector, setSector] = useState('All');
  const [sortBy, setSortBy] = useState<SortKey>('ytd');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const rows = useMemo(() => {
    let data = [...WATCHLIST];
    if (search) {
      const q = search.toLowerCase();
      data = data.filter((s) => s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q));
    }
    if (tier !== 'All') data = data.filter((s) => s.tier === tier);
    if (sector !== 'All') data = data.filter((s) => s.sector === sector);
    data.sort((a, b) => {
      let av: string | number = a[sortBy];
      let bv: string | number = b[sortBy];
      if (typeof av === 'string') av = av.toLowerCase();
      if (typeof bv === 'string') bv = bv.toLowerCase();
      return sortDir === 'desc' ? (bv > av ? 1 : -1) : av > bv ? 1 : -1;
    });
    return data;
  }, [search, tier, sector, sortBy, sortDir]);

  function toggleSort(col: SortKey) {
    if (sortBy === col) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    else {
      setSortBy(col);
      setSortDir('desc');
    }
  }

  const ariaSort = (col: SortKey): 'ascending' | 'descending' | 'none' =>
    sortBy === col ? (sortDir === 'desc' ? 'descending' : 'ascending') : 'none';

  return (
    <section className="cm-watchlist" aria-labelledby="wl-heading">
      <header className="cm-watchlist__head">
        <div>
          <div className="eyebrow">№ 03 — Watchlist</div>
          <h2 id="wl-heading" className="cm-watchlist__title">2026 Movers</h2>
          <p className="lede">
            {WATCHLIST.length} curated tickers with 30%+ YTD performance. Click any row for the TradingView chart,
            news, and fundamentals.
          </p>
        </div>
        <div className="cm-watchlist__legend" role="group" aria-label="Tier legend">
          {(Object.keys(TIER_META) as WatchlistTier[]).map((t) => (
            <span key={t} className="cm-watchlist__legend-item">
              <span role="img" aria-label={TIER_META[t].label}>{TIER_META[t].icon}</span>
              <span className={`cm-wl-tier cm-wl-tier--${t.replace(/\s+/g, '-').toLowerCase()}`}>{t}</span>
            </span>
          ))}
        </div>
      </header>

      <div className="cm-watchlist__controls">
        <label className="cm-watchlist__field">
          <span className="eyebrow">Search</span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Ticker or company"
          />
        </label>
        <label className="cm-watchlist__field">
          <span className="eyebrow">Sector</span>
          <select value={sector} onChange={(e) => setSector(e.target.value)}>
            {SECTORS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
        <div className="cm-watchlist__tiers" role="group" aria-label="Filter by tier">
          {TIERS.map((t) => (
            <button
              key={t}
              type="button"
              className={`cm-wl-tier-btn${tier === t ? ' is-active' : ''}`}
              aria-pressed={tier === t}
              onClick={() => setTier(t)}
            >
              {t}
            </button>
          ))}
        </div>
        <span className="cm-watchlist__count">
          <span className="eyebrow">Showing</span>
          <span className="mono">{rows.length}</span>
        </span>
      </div>

      <div className="cm-live__table-wrap">
        <table className="cm-live__table cm-watchlist__table">
          <caption className="sr-only">Watchlist of 2026 top YTD gainers. Click a row to view the detailed chart.</caption>
          <thead>
            <tr>
              <th aria-sort={ariaSort('rank')}>
                <button type="button" className="cm-wl-sort" onClick={() => toggleSort('rank')}>
                  # {sortBy === 'rank' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
                </button>
              </th>
              <th>Tier</th>
              <th aria-sort={ariaSort('symbol')}>
                <button type="button" className="cm-wl-sort" onClick={() => toggleSort('symbol')}>
                  Symbol {sortBy === 'symbol' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
                </button>
              </th>
              <th aria-sort={ariaSort('name')}>
                <button type="button" className="cm-wl-sort" onClick={() => toggleSort('name')}>
                  Company {sortBy === 'name' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
                </button>
              </th>
              <th aria-sort={ariaSort('sector')}>
                <button type="button" className="cm-wl-sort" onClick={() => toggleSort('sector')}>
                  Sector {sortBy === 'sector' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
                </button>
              </th>
              <th aria-sort={ariaSort('ytd')}>
                <button type="button" className="cm-wl-sort" onClick={() => toggleSort('ytd')}>
                  YTD {sortBy === 'ytd' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
                </button>
              </th>
              <th aria-sort={ariaSort('price')}>
                <button type="button" className="cm-wl-sort" onClick={() => toggleSort('price')}>
                  Price {sortBy === 'price' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
                </button>
              </th>
              <th>Cap</th>
              <th>Momentum</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s, i) => {
              const meta = TIER_META[s.tier];
              const tierClass = s.tier.replace(/\s+/g, '-').toLowerCase();
              const barWidth = Math.min(100, (s.ytd / 2400) * 100);
              return (
                <tr
                  key={s.symbol + i}
                  className="cm-wl-row"
                  tabIndex={0}
                  role="button"
                  aria-label={`Open detail view for ${s.symbol}, ${s.name}`}
                  onClick={() => onSelect(s.symbol)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelect(s.symbol);
                    }
                  }}
                >
                  <td className="muted small">{i + 1}</td>
                  <td>
                    <span role="img" aria-label={`${s.tier}: ${meta.label}`}>{meta.icon}</span>
                  </td>
                  <td><span className="cm-live__ticker mono">{s.symbol}</span></td>
                  <td className="name">{s.name}</td>
                  <td><span className="sector-tag">{s.sector}</span></td>
                  <td className="mono">
                    <span className={`cm-wl-ytd cm-wl-ytd--${tierClass}`}>+{s.ytd}%</span>
                  </td>
                  <td className="mono">${s.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                  <td className="muted small">{s.cap}</td>
                  <td>
                    <div
                      className="cm-wl-bar"
                      role="progressbar"
                      aria-valuenow={s.ytd}
                      aria-valuemin={0}
                      aria-valuemax={2400}
                      aria-label={`${s.ytd} percent YTD`}
                    >
                      <div className={`cm-wl-bar__fill cm-wl-bar__fill--${tierClass}`} style={{ width: `${barWidth}%` }} />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {rows.length === 0 && (
          <div className="muted" style={{ padding: 24, textAlign: 'center' }}>No stocks match your filters.</div>
        )}
      </div>
    </section>
  );
}
