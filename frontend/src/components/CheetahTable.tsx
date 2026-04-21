import { useMemo, useState } from 'react';
import type { CheetahStock } from '../types';

interface Props {
  stocks: CheetahStock[];
}

type SortKey = keyof Pick<
  CheetahStock,
  'ticker' | 'sector' | 'mcap' | 'revGrowth' | 'grossMargin' | 'debtRev' | 'peg' | 'rs' | 'perf3m' | 'score'
>;

function scoreColor(score: number) {
  if (score >= 85) return '#10b981';
  if (score >= 75) return '#fbbf24';
  if (score >= 65) return '#f97316';
  return '#ef4444';
}

function fmtMcap(v: number) {
  return v >= 1000 ? `${(v / 1000).toFixed(1)}T` : `${v}B`;
}

function fmtPct(v: number) {
  if (v === 0) return '—';
  const cls = v > 0 ? 'pos' : 'neg';
  return <span className={cls}>{v > 0 ? '+' : ''}{v}%</span>;
}

export function CheetahTable({ stocks }: Props) {
  const [sectorFilter, setSectorFilter] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortAsc, setSortAsc] = useState(false);

  const sectors = useMemo(
    () => Array.from(new Set(stocks.map((s) => s.sector))).sort(),
    [stocks]
  );

  const rows = useMemo(() => {
    let filtered = stocks.filter((s) => {
      if (sectorFilter && s.sector !== sectorFilter) return false;
      if (s.score < minScore) return false;
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        s.ticker.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q) ||
        s.tier2.some((t) => t.toLowerCase().includes(q)) ||
        s.tier3.some((t) => t.toLowerCase().includes(q))
      );
    });
    filtered = [...filtered].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === 'string' && typeof bv === 'string') {
        return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortAsc ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return filtered;
  }, [stocks, sectorFilter, minScore, search, sortKey, sortAsc]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) setSortAsc(!sortAsc);
    else {
      setSortKey(key);
      setSortAsc(false);
    }
  }

  function sortIcon(key: SortKey) {
    if (key !== sortKey) return '';
    return sortAsc ? ' ↑' : ' ↓';
  }

  return (
    <section className="card">
      <div className="controls">
        <label>
          Sector:
          <select value={sectorFilter} onChange={(e) => setSectorFilter(e.target.value)}>
            <option value="">All</option>
            {sectors.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          Min Score:
          <input
            type="number"
            value={minScore}
            min={0}
            max={100}
            onChange={(e) => setMinScore(parseFloat(e.target.value) || 0)}
            style={{ width: 70 }}
          />
        </label>
        <label>
          Search:
          <input
            type="text"
            value={search}
            placeholder="ticker, name, or competitor"
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: 200 }}
          />
        </label>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th onClick={() => toggleSort('ticker')}>Tier 1{sortIcon('ticker')}</th>
              <th onClick={() => toggleSort('sector')}>Sector{sortIcon('sector')}</th>
              <th onClick={() => toggleSort('mcap')}>Mkt Cap{sortIcon('mcap')}</th>
              <th onClick={() => toggleSort('revGrowth')}>Rev YoY{sortIcon('revGrowth')}</th>
              <th onClick={() => toggleSort('grossMargin')}>GM{sortIcon('grossMargin')}</th>
              <th onClick={() => toggleSort('debtRev')}>D/R{sortIcon('debtRev')}</th>
              <th onClick={() => toggleSort('peg')}>PEG{sortIcon('peg')}</th>
              <th onClick={() => toggleSort('rs')}>RS{sortIcon('rs')}</th>
              <th onClick={() => toggleSort('perf3m')}>3M{sortIcon('perf3m')}</th>
              <th onClick={() => toggleSort('score')}>Score{sortIcon('score')}</th>
              <th>Key Signals (formulas driving score)</th>
              <th>Tier 2 Competitors</th>
              <th>Tier 3 Competitors</th>
              <th>Why It's Running</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.ticker}>
                <td>
                  <div className="ticker">{s.ticker}</div>
                  <div className="name">{s.name}</div>
                </td>
                <td>
                  <span className="sector-tag">{s.sector}</span>
                </td>
                <td>${fmtMcap(s.mcap)}</td>
                <td>{fmtPct(s.revGrowth)}</td>
                <td>{s.grossMargin ? `${s.grossMargin}%` : '—'}</td>
                <td>{s.debtRev.toFixed(2)}</td>
                <td>{s.peg ? s.peg.toFixed(2) : '—'}</td>
                <td>{s.rs}</td>
                <td>{fmtPct(s.perf3m)}</td>
                <td className="score-cell">
                  <span style={{ color: scoreColor(s.score), fontWeight: 700, fontSize: 15 }}>
                    {s.score}
                  </span>
                  <span className="score-bar">
                    <span style={{ width: `${s.score}%` }} />
                  </span>
                </td>
                <td>
                  {s.signals.map((sig, i) => (
                    <span key={i} className={`signal-pill ${sig.type}`}>
                      {sig.label}
                    </span>
                  ))}
                </td>
                <td className="competitor-cell">
                  {s.tier2.map((t) => (
                    <span key={t} className="comp-tag t2">
                      {t}
                    </span>
                  ))}
                </td>
                <td className="competitor-cell">
                  {s.tier3.map((t) => (
                    <span key={t} className="comp-tag t3">
                      {t}
                    </span>
                  ))}
                </td>
                <td className="why-col">{s.why}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
