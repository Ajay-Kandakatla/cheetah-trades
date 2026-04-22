import { useEffect, useRef, useState } from 'react';
import type { Quote } from '../types';
import { Sparkline } from './Sparkline';

interface Props {
  quote: Quote;
  cheetahScore?: number;
  onRemove: () => void;
}

export function QuoteRow({ quote, cheetahScore, onRemove }: Props) {
  const [flash, setFlash] = useState<'up' | 'down' | null>(null);
  const lastPrice = useRef<number | undefined>(quote.price);

  useEffect(() => {
    if (quote.price === undefined) return;
    if (lastPrice.current !== undefined && quote.price !== lastPrice.current) {
      setFlash(quote.price > lastPrice.current ? 'up' : 'down');
      const t = setTimeout(() => setFlash(null), 500);
      return () => clearTimeout(t);
    }
    lastPrice.current = quote.price;
  }, [quote.price]);

  const pct = quote.pct_change;
  const pctClass = pct == null ? 'neutral' : pct >= 0 ? 'pos' : 'neg';

  function rsiClass(rsi: number | undefined | null) {
    if (rsi == null) return '';
    if (rsi >= 70) return 'neg';
    if (rsi <= 30) return 'pos';
    return '';
  }

  function scoreBadgeColor(score: number | undefined) {
    if (score === undefined) return '#6b7488';
    if (score >= 85) return '#10b981';
    if (score >= 75) return '#fbbf24';
    if (score >= 65) return '#f97316';
    return '#ef4444';
  }

  return (
    <tr className={flash ? `flash-${flash}` : ''}>
      <td className="ticker">{quote.symbol}</td>
      <td className="price">
        {quote.price != null ? `$${quote.price.toFixed(2)}` : '—'}
      </td>
      <td className={pctClass}>
        {pct != null ? `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%` : '—'}
      </td>
      <td className={rsiClass(quote.rsi14)}>
        {quote.rsi14 != null ? quote.rsi14.toFixed(0) : '—'}
      </td>
      <td>{quote.vwap != null ? `$${quote.vwap.toFixed(2)}` : '—'}</td>
      <td>
        <Sparkline values={quote.sparkline} />
      </td>
      <td>
        {cheetahScore !== undefined ? (
          <span className="score-badge" style={{ background: scoreBadgeColor(cheetahScore) }}>
            {cheetahScore}
          </span>
        ) : (
          <span className="muted small">—</span>
        )}
      </td>
      <td>{quote.open != null ? `$${quote.open.toFixed(2)}` : '—'}</td>
      <td>{quote.high != null ? `$${quote.high.toFixed(2)}` : '—'}</td>
      <td>{quote.low != null ? `$${quote.low.toFixed(2)}` : '—'}</td>
      <td>{quote.volume?.toLocaleString() ?? '—'}</td>
      <td className="source">{quote.source === 'finnhub_ws' ? 'LIVE' : 'REST'}</td>
      <td>
        <button className="remove" onClick={onRemove} aria-label={`Remove ${quote.symbol}`}>
          ×
        </button>
      </td>
    </tr>
  );
}
