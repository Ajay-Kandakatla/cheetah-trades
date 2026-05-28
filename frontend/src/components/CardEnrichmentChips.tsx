/**
 * CardEnrichmentChips — renders two JIT-loaded chips on a SEPA card:
 *
 *   🟢 Cluster Insider Buy      (when ≥3 unique insiders filed Form 4 in 30d)
 *   💰 Undervalued / Fair / Overvalued   (from P/E + P/B + P/S composite)
 *
 * Lazy-loaded per card via IntersectionObserver (see useCardEnrichment).
 * Cards that never scroll into view make zero requests.
 *
 * The wrapping div is the IntersectionObserver target — the hook
 * attaches via a forwarded ref. Without the wrapper, nothing to observe.
 */
import { useCardEnrichment } from '../hooks/useCardEnrichment';

interface Props {
  symbol: string;
}

export function CardEnrichmentChips({ symbol }: Props) {
  const { ref, data } = useCardEnrichment(symbol);

  // Show nothing while loading — these chips are decorative + lazy.
  // Empty wrapper still needs to render so IntersectionObserver has a
  // DOM node to watch. (The 1px-min wrapper avoids layout shift when
  // chips appear; the chips themselves have natural flow inside it.)
  const insiderCluster = data?.insider?.cluster_buy === true;
  const insiderCount = data?.insider?.unique_insiders_30d ?? 0;
  const valuation = data?.valuation?.signal;
  const valuationLabel = data?.valuation?.label;
  const pe = data?.valuation?.pe;
  const peg = data?.valuation?.peg;

  return (
    <div ref={ref} style={{ display: 'contents' }}>
      {insiderCluster && (
        <span
          className="sepa-flag sepa-flag--good"
          title={
            `Cluster insider buy — ${insiderCount} unique insiders filed Form 4 ` +
            `in the last 30 days. Multi-insider buying inside a 30-day window is ` +
            `one of Minervini's bullish tells (William O'Neil chapter 13).`
          }
        >
          🟢 Cluster insider buy{insiderCount >= 3 ? ` (${insiderCount})` : ''}
        </span>
      )}
      {valuation && (
        <span
          className={`sepa-flag ${
            valuation === 'undervalued' ? 'sepa-flag--good' :
            valuation === 'overvalued'  ? 'sepa-flag--bad' :
                                          'sepa-flag--neutral'
          }`}
          title={tooltipFor(valuationLabel, pe, peg, data?.valuation?.score)}
        >
          {valuation === 'undervalued' ? '💰' :
           valuation === 'overvalued'  ? '⚠️' :
                                         '⚖️'} {valuationLabel || valuation}
          {pe != null && ` · P/E ${pe.toFixed(1)}`}
        </span>
      )}
    </div>
  );
}

function tooltipFor(label: string | null | undefined, pe: number | null | undefined,
                    peg: number | null | undefined, score: number | null | undefined): string {
  const parts: string[] = [];
  if (label) parts.push(label);
  if (score != null) parts.push(`composite ${score}/100`);
  if (pe != null) parts.push(`P/E ${pe.toFixed(1)}`);
  if (peg != null) parts.push(`PEG ${peg.toFixed(1)}`);
  return parts.join(' · ') +
    `\n\nValuation composite of P/E + P/B + P/S. Higher score = cheaper. ` +
    `Undervalued ≥70, Fair 40–69, Overvalued <40.`;
}
