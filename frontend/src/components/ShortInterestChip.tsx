/* 🩳 ShortInterestChip — one compact chip per card on every Chart Maps tab
 * and on the ticker page header.
 *
 * Ajay 2026-10-03: "can you add this field to all our chart maps scan. also
 * the individual tickers please".
 *
 * ONE component, dropped beside every <PromoOriginChip/> (the GrowthChip
 * precedent), so every surface prints the same served string. The text and the
 * hover sentence come verbatim from GET /short-interest/map; this file computes
 * nothing. One neutral tone, never coloured by value: a count of open short
 * positions is a data label with its FINRA settlement date, not a signal. A
 * stale read says so in its own text. Renders NOTHING when no block is cached
 * (or the block is a no-record) — never a zero.
 */
import { useShortInterest } from '../hooks/useShortInterest';
import { siChip } from '../lib/shortInterest';

export function ShortInterestChip({ symbol, className = 'cm-badge' }:
                                  { symbol: string; className?: string }) {
  const { read } = useShortInterest(symbol);
  const c = siChip(read);
  if (!c) return null;
  return (
    <span className={`${className} ${className}-muted`} title={c.title} data-testid="si-chip">{c.text}</span>
  );
}
