import { useMemo, useState } from 'react';
import type { IndianStock } from '../types';

interface Props {
  stocks: IndianStock[];
}

type SortKey = keyof Pick<
  IndianStock,
  'symbol' | 'sector' | 'price' | 'changePercent' | 'volume' | 'high52' | 'low52'
>;

function fmtINR(v: number | null | undefined) {
  if (v == null) return '—';
  return `₹${v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(v: number) {
  if (v === 0) return '—';
  const cls = v > 0 ? 'pos' : 'neg';
  return (
    <span className={cls}>
      {v > 0 ? '+' : ''}
      {v.toFixed(2)}%
    </span>
  );
}

function fmtVolume(v: number) {
  if (v >= 10_000_000) return `${(v / 10_000_000).toFixed(2)} Cr`;
  if (v >= 100_000) return `${(v / 100_000).toFixed(2)} L`;
  return v.toLocaleString('en-IN');
}

export function IndianStockTable({ stocks }: Props) {
  const [sectorFilter, setSectorFilter] = useState('');
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('changePercent');
  const [sortAsc, setSortAsc] = useState(false);

  const sectors = useMemo(
    () => Array.from(new Set(stocks.map((s) => s.sector))).sort(),
    [stocks]
  );

  const rows = useMemo(() => {
    let filtered = stocks.filter((s) => {
      if (sectorFilter && s.sector !== sectorFilter) return false;
      if (!search) return true;
      const q = search.toLowerCase();
      return s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q);
    });
    filtered = [...filtered].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === 'string' && typeof bv === 'string') {
        return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      const an = (av as number) ?? 0;
      const bn = (bv as number) ?? 0;
      return sortAsc ? an - bn : bn - an;
    });
    return filtered;
  }, [stocks, sectorFilter, search, sortKey, sortAsc]);

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
          Search:
          <input
            type="text"
            value={search}
            placeholder="ticker or name"
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: 200 }}
          />
        </label>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th onClick={() => toggleSort('symbol')}>Ticker{sortIcon('symbol')}</th>
              <th onClick={() => toggleSort('sector')}>Sector{sortIcon('sector')}</th>
              <th onClick={() => toggleSort('price')}>Price{sortIcon('price')}</th>
              <th onClick={() => toggleSort('changePercent')}>Change{sortIcon('changePercent')}</th>
              <th onClick={() => toggleSort('volume')}>Volume{sortIcon('volume')}</th>
              <th onClick={() => toggleSort('high52')}>52W High{sortIcon('high52')}</th>
              <th onClick={() => toggleSort('low52')}>52W Low{sortIcon('low52')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.symbol}>
                <td>
                  <div className="ticker">{s.symbol}</div>
                  <div className="name">{s.name}</div>
                </td>
                <td>
                  <span className="sector-tag">{s.sector}</span>
                </td>
                <td>{fmtINR(s.price)}</td>
                <td>{fmtPct(s.changePercent)}</td>
                <td>{fmtVolume(s.volume)}</td>
                <td>{fmtINR(s.high52)}</td>
                <td>{fmtINR(s.low52)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
