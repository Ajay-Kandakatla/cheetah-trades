import { useMemo, useState } from 'react';
import { useMarketStream } from '../hooks/useMarketStream';
import { useCheetahStocks } from '../hooks/useCheetahStocks';
import { QuoteRow } from '../components/QuoteRow';

const DEFAULT_WATCHLIST = ['NVDA', 'META', 'AAPL', 'MSFT', 'TSLA', 'AMD', 'PLTR', 'CRDO'];

export function LiveStream() {
  const [symbols, setSymbols] = useState<string[]>(DEFAULT_WATCHLIST);
  const [input, setInput] = useState('');
  const { quotes, status } = useMarketStream(symbols);
  const { stocks: cheetahStocks } = useCheetahStocks();

  const scoreLookup = useMemo(() => {
    const map: Record<string, number> = {};
    cheetahStocks?.forEach((s) => { map[s.ticker] = s.score; });
    return map;
  }, [cheetahStocks]);

  const rows = useMemo(
    () => symbols.map((s) => quotes[s] ?? { symbol: s, ts: 0 }),
    [symbols, quotes]
  );

  function addSymbol(e: React.FormEvent) {
    e.preventDefault();
    const s = input.trim().toUpperCase();
    if (!s || symbols.includes(s)) return;
    setSymbols([...symbols, s]);
    setInput('');
  }

  function removeSymbol(s: string) {
    setSymbols(symbols.filter((x) => x !== s));
  }

  const statusColor = {
    connecting: '#fbbf24',
    open: '#10b981',
    closed: '#6b7488',
    error: '#ef4444',
  }[status];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Live Market Stream</h1>
          <div className="page-sub">
            Real-time quotes via Server-Sent Events · RSI, VWAP, and sparkline computed server-side
          </div>
        </div>
        <div className="status">
          <span className="dot" style={{ background: statusColor }} />
          <span>{status.toUpperCase()}</span>
        </div>
      </div>

      <form onSubmit={addSymbol} className="add-form">
        <input
          type="text"
          placeholder="Add ticker (e.g. AVGO)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button type="submit">Add</button>
      </form>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Price</th>
              <th>Day %</th>
              <th>RSI<sub>14</sub></th>
              <th>VWAP</th>
              <th>Spark</th>
              <th>Cheetah</th>
              <th>Open</th>
              <th>High</th>
              <th>Low</th>
              <th>Volume</th>
              <th>Feed</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((q) => (
              <QuoteRow
                key={q.symbol}
                quote={q}
                cheetahScore={scoreLookup[q.symbol]}
                onRemove={() => removeSymbol(q.symbol)}
              />
            ))}
          </tbody>
        </table>
      </div>

      <footer className="footer">
        <strong>Disclaimer:</strong> Educational/research tool. Finnhub free tier is real-time
        for US equities during market hours; off-hours shows last trade. RSI reading 70+ often
        signals overbought, 30- oversold — not a buy/sell signal by itself. Not financial advice.
        Do not use for automated execution without verifying tick-by-tick accuracy against a
        licensed market-data vendor.
      </footer>
    </div>
  );
}
