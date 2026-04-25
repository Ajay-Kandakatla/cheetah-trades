import { useEffect } from 'react';
import type { WatchlistStock } from '../data/watchlist';

interface Props {
  symbol: string;
  meta?: WatchlistStock;
  onClose: () => void;
}

export function StockDetailModal({ symbol, meta, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  const tvSymbol = `NASDAQ:${symbol}`;
  const chartSrc = `https://s.tradingview.com/widgetembed/?frameElementId=tv-chart&symbol=${encodeURIComponent(tvSymbol)}&interval=D&theme=dark&style=1&timezone=Etc%2FUTC&withdateranges=1&hide_side_toolbar=0&allow_symbol_change=1&save_image=0&studies=%5B%5D&locale=en`;

  return (
    <div
      className="cm-modal-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="cm-modal-title"
    >
      <div className="cm-modal" onClick={(e) => e.stopPropagation()}>
        <header className="cm-modal__head">
          <div>
            <div className="eyebrow">Detail view</div>
            <h2 id="cm-modal-title" className="cm-modal__title">
              {symbol}
              {meta && <span className="cm-modal__name"> · {meta.name}</span>}
            </h2>
            {meta && (
              <div className="cm-modal__meta">
                <span className="sector-tag">{meta.sector}</span>
                <span className="cm-modal__pill">Price ${meta.price.toFixed(2)}</span>
                <span className="cm-modal__pill">Cap {meta.cap}</span>
                <span className={`cm-modal__pill cm-modal__pill--ytd cm-modal__pill--${meta.tier.replace(/\s+/g, '-').toLowerCase()}`}>
                  YTD +{meta.ytd}%
                </span>
                <span className="muted small">{meta.tier}</span>
              </div>
            )}
          </div>
          <button type="button" className="cm-modal__close" onClick={onClose} aria-label="Close detail view">
            ×
          </button>
        </header>

        <div className="cm-modal__chart">
          <iframe
            id="tv-chart"
            title={`${symbol} price chart`}
            src={chartSrc}
            style={{ width: '100%', height: '100%', border: 0 }}
            allow="clipboard-write"
          />
        </div>

        <footer className="cm-modal__links">
          <a href={`https://finance.yahoo.com/quote/${symbol}`} target="_blank" rel="noreferrer">Yahoo Finance</a>
          <a href={`https://www.google.com/finance/quote/${symbol}:NASDAQ`} target="_blank" rel="noreferrer">Google Finance</a>
          <a href={`https://www.tradingview.com/symbols/${symbol}/`} target="_blank" rel="noreferrer">TradingView</a>
          <a href={`https://stockanalysis.com/stocks/${symbol.toLowerCase()}/`} target="_blank" rel="noreferrer">StockAnalysis</a>
          <a href={`https://news.google.com/search?q=${symbol}+stock`} target="_blank" rel="noreferrer">Google News</a>
        </footer>
      </div>
    </div>
  );
}
