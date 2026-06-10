import { useEffect } from 'react';
import type { WatchlistStock } from '../data/watchlist';
// Native live chart (lightweight-charts, our own data feed). The TradingView
// widget embed was removed 2026-06-10 — no embed approval, and it was ~15-min
// delayed anyway. External TV links below are plain hyperlinks and stay.
import { LiveCandlesChart } from './LiveCandlesChart';

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
          <LiveCandlesChart symbol={symbol} interval="D" />
        </div>

        <footer className="cm-modal__links">
          <a href={`https://finance.yahoo.com/quote/${symbol}`} target="_blank" rel="noreferrer">Yahoo Finance</a>
          <a href={`https://www.google.com/finance/quote/${symbol}:NASDAQ`} target="_blank" rel="noreferrer">Google Finance</a>
          <a href={`https://www.tradingview.com/symbols/${symbol}/`} target="_blank" rel="noreferrer">TradingView</a>
          <a href={`https://stockanalysis.com/stocks/${symbol.toLowerCase()}/`} target="_blank" rel="noreferrer">StockAnalysis</a>
          <a href={`https://stocktwits.com/symbol/${symbol}`} target="_blank" rel="noreferrer">StockTwits</a>
          {/* One-time install for Gabbar's aggressive / 3-conservative
              entry levels. See SepaCandidate.tsx for the install flow. */}
          <a
            href="https://www.tradingview.com/script/hcLOuzBX-Gabbar-s-Price-Levels-script/"
            target="_blank"
            rel="noreferrer"
            title="Open the indicator on TradingView → 'Add to Chart' → save as default layout, then it overlays on every chart you open from Pounce."
          >
            📊 Gabbar's Levels
          </a>
          <a href={`https://news.google.com/search?q=${symbol}+stock`} target="_blank" rel="noreferrer">Google News</a>
        </footer>
      </div>
    </div>
  );
}
