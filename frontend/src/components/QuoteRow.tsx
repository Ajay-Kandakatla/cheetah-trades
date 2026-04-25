import { useEffect, useRef, useState } from 'react';
import type { Quote } from '../types';
import { Sparkline } from './Sparkline';

interface Props {
  quote: Quote;
  cheetahScore?: number;
  onRemove: () => void;
  onSelect?: () => void;
}

function fmtUsd(v?: number | null, digits = 2): string {
  if (v == null) return '—';
  return v.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function fmtVolume(v?: number | null): string {
  if (v == null) return '—';
  if (v >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toString();
}

function scoreClass(score?: number): string {
  if (score == null) return 'cm-score cm-score--empty';
  if (score >= 85) return 'cm-score cm-score--high';
  if (score >= 75) return 'cm-score cm-score--mid';
  if (score >= 65) return 'cm-score cm-score--low';
  return 'cm-score cm-score--poor';
}

export function QuoteRow({ quote, cheetahScore, onRemove, onSelect }: Props) {
  const [flash, setFlash] = useState<'up' | 'down' | null>(null);
  const lastPrice = useRef<number | undefined>(quote.price);

  useEffect(() => {
    if (quote.price === undefined) return;
    if (lastPrice.current !== undefined && quote.price !== lastPrice.current) {
      setFlash(quote.price > lastPrice.current ? 'up' : 'down');
      const t = setTimeout(() => setFlash(null), 500);
      lastPrice.current = quote.price;
      return () => clearTimeout(t);
    }
    lastPrice.current = quote.price;
  }, [quote.price]);

  const pct = quote.pct_change;
  const pctClass = pct == null ? '' : pct >= 0 ? 'positive' : 'negative';

  function rsiClass(rsi: number | undefined | null): string {
    if (rsi == null) return '';
    if (rsi >= 70) return 'negative';
    if (rsi <= 30) return 'positive';
    return '';
  }

  return (
    <tr className={flash ? `cm-flash cm-flash--${flash}` : ''}>
      <td className="cm-live__ticker mono">
        {onSelect ? (
          <button type="button" className="cm-live__ticker-btn" onClick={onSelect} aria-label={`Open detail for ${quote.symbol}`}>
            {quote.symbol}
          </button>
        ) : (
          quote.symbol
        )}
      </td>
      <td className="mono">{quote.price != null ? fmtUsd(quote.price) : '—'}</td>
      <td className={`mono ${pctClass}`}>
        {pct != null ? `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%` : '—'}
      </td>
      <td className={`mono ${rsiClass(quote.rsi14)}`}>
        {quote.rsi14 != null ? quote.rsi14.toFixed(0) : '—'}
      </td>
      <td className="mono">{quote.vwap != null ? fmtUsd(quote.vwap) : '—'}</td>
      <td className="cm-live__spark">
        <Sparkline values={quote.sparkline} />
      </td>
      <td>
        {cheetahScore !== undefined ? (
          <span className={scoreClass(cheetahScore)}>{cheetahScore}</span>
        ) : (
          <span className="faint">—</span>
        )}
      </td>
      <td className="mono">{quote.open != null ? fmtUsd(quote.open) : '—'}</td>
      <td className="mono">{quote.high != null ? fmtUsd(quote.high) : '—'}</td>
      <td className="mono">{quote.low != null ? fmtUsd(quote.low) : '—'}</td>
      <td className="mono">{fmtVolume(quote.volume)}</td>
      <td>
        <span className={`cm-feed cm-feed--${quote.source === 'finnhub_ws' ? 'live' : 'rest'}`}>
          {quote.source === 'finnhub_ws' ? 'Live' : 'REST'}
        </span>
      </td>
      <td className="cm-live__actions">
        <button
          type="button"
          className="cm-row-remove"
          onClick={onRemove}
          aria-label={`Remove ${quote.symbol}`}
        >
          ×
        </button>
      </td>
    </tr>
  );
}
