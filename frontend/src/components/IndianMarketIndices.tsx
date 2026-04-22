import type { IndianMarketIndex } from '../types';

interface Props {
  indices: IndianMarketIndex[];
}

function fmtINR(v: number) {
  return `₹${v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function IndianMarketIndices({ indices }: Props) {
  if (!indices || indices.length === 0) {
    return (
      <section className="card">
        <h2>Indian Market Indices</h2>
        <p className="muted">No index data available.</p>
      </section>
    );
  }

  return (
    <section className="card">
      <h2>Indian Market Indices</h2>
      <div className="indices-grid">
        {indices.map((idx) => {
          const up = idx.change >= 0;
          return (
            <div key={idx.symbol} className="index-card">
              <h3>{idx.name}</h3>
              <div className="index-value">{fmtINR(idx.value)}</div>
              <div className={`index-change ${up ? 'positive' : 'negative'}`}>
                {up ? '+' : ''}
                {idx.change.toLocaleString('en-IN', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}{' '}
                ({up ? '+' : ''}
                {idx.changePercent.toFixed(2)}%)
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
