import { IndianStockTable } from '../components/IndianStockTable';
import { IndianNewsPanel } from '../components/IndianNewsPanel';
import { IndianMarketIndices } from '../components/IndianMarketIndices';
import { RefreshButton } from '../components/RefreshButton';
import { useIndianStocks } from '../hooks/useIndianStocks';

export function IndianMarket() {
  const { stocks, indices, fetchedAt, loading, error, refetch } = useIndianStocks();

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Indian Stocks Dashboard</h1>
          <div className="page-sub">
            Live NSE / BSE quotes · Nifty 50, Sensex, Bank Nifty indices · Real-time news
          </div>
        </div>
        <RefreshButton onClick={refetch} loading={loading} computedAt={fetchedAt ? fetchedAt * 1000 : null} />
      </div>

      <div className="disclaimer">
        <strong>Not financial advice.</strong> Quotes via Yahoo Finance's free public
        endpoint — may lag by 15 minutes and can rate-limit without warning. Always
        verify with your broker before trading.
      </div>

      <IndianMarketIndices indices={indices} />

      {error && (
        <div className="error-card">
          Failed to load Indian market data: {error}. Make sure the backend is running at{' '}
          <code>localhost:8000</code>.
        </div>
      )}
      {!stocks && !error && <div className="loading">Loading…</div>}
      {stocks && <IndianStockTable stocks={stocks} />}

      <IndianNewsPanel />
    </div>
  );
}
