import { useMemo, useState } from 'react';
import { useMarketStream } from '../hooks/useMarketStream';
import { useCheetahStocks } from '../hooks/useCheetahStocks';
import { QuoteRow } from '../components/QuoteRow';
import { WatchlistSection } from '../components/WatchlistSection';
import { StockDetailModal } from '../components/StockDetailModal';
import { WATCHLIST } from '../data/watchlist';

const DEFAULT_WATCHLIST = ['NVDA', 'META', 'AAPL', 'MSFT', 'TSLA', 'AMD', 'PLTR', 'CRDO'];

const STATUS_LABEL: Record<string, string> = {
  connecting: 'Connecting',
  open: 'Live',
  closed: 'Closed',
  error: 'Error',
};

export function LiveStream() {
  const [symbols, setSymbols] = useState<string[]>(DEFAULT_WATCHLIST);
  const [input, setInput] = useState('');
  const [detail, setDetail] = useState<string | null>(null);
  const { quotes, status } = useMarketStream(symbols);
  const { stocks: cheetahStocks } = useCheetahStocks();

  const scoreLookup = useMemo(() => {
    const map: Record<string, number> = {};
    cheetahStocks?.forEach((s) => {
      map[s.ticker] = s.score;
    });
    return map;
  }, [cheetahStocks]);

  const rows = useMemo(
    () => symbols.map((s) => quotes[s] ?? { symbol: s, ts: 0 }),
    [symbols, quotes],
  );

  const detailMeta = useMemo(
    () => (detail ? WATCHLIST.find((w) => w.symbol === detail) : undefined),
    [detail],
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

  return (
    <div className="cm-page cm-page--live">
      <header className="cm-pagehead">
        <div className="cm-pagehead__col">
          <div className="eyebrow">№ 02 — Live Feed</div>
          <h1 className="display cm-pagehead__title">Market Stream</h1>
          <p className="lede">
            Real-time quotes over Server-Sent Events. RSI, VWAP, and the
            sparkline trace are computed server-side — the canvas only renders
            what the pipeline delivers.
          </p>
        </div>

        <div className="cm-pagehead__aside">
          <div className={`cm-status cm-status--${status}`} role="status" aria-live="polite">
            <span className="cm-status__dot" aria-hidden="true" />
            <span className="cm-status__label">{STATUS_LABEL[status] ?? status.toUpperCase()}</span>
          </div>
        </div>
      </header>

      <section className="cm-live__controls">
        <form onSubmit={addSymbol} className="cm-live__form">
          <label className="eyebrow" htmlFor="add-ticker">Add ticker</label>
          <input
            id="add-ticker"
            type="text"
            placeholder="e.g. AVGO"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          <button type="submit" className="cm-live__add">Add</button>
        </form>

        <div className="cm-live__count">
          <span className="eyebrow">Watching</span>
          <span className="mono">{symbols.length}</span>
        </div>
      </section>

      <div className="cm-live__table-wrap">
        <table className="cm-live__table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Price</th>
              <th>Day %</th>
              <th>RSI<sub>14</sub></th>
              <th>VWAP</th>
              <th>Trace</th>
              <th>Cheetah</th>
              <th>Open</th>
              <th>High</th>
              <th>Low</th>
              <th>Volume</th>
              <th>Feed</th>
              <th aria-label="Remove" />
            </tr>
          </thead>
          <tbody>
            {rows.map((q) => (
              <QuoteRow
                key={q.symbol}
                quote={q}
                cheetahScore={scoreLookup[q.symbol]}
                onRemove={() => removeSymbol(q.symbol)}
                onSelect={() => setDetail(q.symbol)}
              />
            ))}
          </tbody>
        </table>
      </div>

      <WatchlistSection onSelect={(sym) => setDetail(sym)} />

      <footer className="cm-disclaimer cm-disclaimer--footer">
        <span className="cm-disclaimer__label">Disclosure</span>
        <p>
          Educational and research tool. Finnhub's free tier is real-time for US
          equities during market hours and shows the last trade off-hours. RSI
          readings above 70 often signal overbought conditions and below 30
          oversold — not a buy or sell signal on their own. Not financial
          advice. Do not use for automated execution without verifying
          tick-by-tick accuracy against a licensed market-data vendor.
        </p>
      </footer>

      {detail && <StockDetailModal symbol={detail} meta={detailMeta} onClose={() => setDetail(null)} />}
    </div>
  );
}
