/**
 * CardEnrichmentChips — renders JIT-loaded chips on a SEPA card:
 *
 *   🟢 Cluster (N)          — ≥3 unique insiders filed Form 4 in 30d (cluster_buy)
 *   N buyer(s)              — 1-2 unique insiders filed Form 4 in 30d
 *   💰 Undervalued / Fair / Overvalued   (from P/E + P/B + P/S composite)
 *
 * Lazy-loaded per card via IntersectionObserver (see useCardEnrichment).
 * Cards that never scroll into view make zero requests.
 *
 * The wrapping div is the IntersectionObserver target — the hook
 * attaches via a forwarded ref. Without the wrapper, nothing to observe.
 *
 * Insider chip tiers + clickability ported from SepaV2.tsx so V1 cards
 * surface the same insider signal V2's table shows: cluster (≥3) is the
 * Minervini/O'Neil bullish tell; 1-2 buyer cases still get a chip so the
 * user can see partial signal at a glance. Both tiers deep-link to the
 * detail page #insider section.
 */
import { Link } from 'react-router-dom';
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
  const netWorth = data?.headline?.market_cap;
  const equity = data?.headline?.shareholder_equity;

  return (
    <div ref={ref} style={{ display: 'contents' }}>
      {insiderCluster ? (
        <Link
          to={`/sepa/${symbol}?tab=insider`}
          className="ins-chip ins-cluster"
          title={
            `Cluster insider buy — ${insiderCount} unique insiders filed Form 4 ` +
            `in the last 30 days. Multi-insider buying inside a 30-day window is ` +
            `one of Minervini's bullish tells (William O'Neil chapter 13). ` +
            `Click for the full Form 4 list on the detail page.`
          }
        >
          🟢 Cluster ({insiderCount})
        </Link>
      ) : insiderCount > 0 ? (
        <Link
          to={`/sepa/${symbol}?tab=insider`}
          className="ins-chip ins-some"
          title={
            `${insiderCount} insider${insiderCount === 1 ? '' : 's'} bought in the ` +
            `last 30 days. Not yet a cluster (≥3), but partial signal — click for ` +
            `the Form 4 detail on the detail page.`
          }
        >
          {insiderCount} buyer{insiderCount === 1 ? '' : 's'}
        </Link>
      ) : null}
      {valuation && (
        <Link
          to={`/sepa/${symbol}?tab=fundamentals`}
          className={`val-chip ${
            valuation === 'undervalued' ? 'val-under' :
            valuation === 'overvalued'  ? 'val-over'  :
                                          'val-fair'
          }`}
          title={tooltipFor(valuationLabel, pe, peg, data?.valuation?.score)}
        >
          {valuation === 'undervalued' ? '💰' :
           valuation === 'overvalued'  ? '⚠️' :
                                         '⚖️'} {valuationLabel || valuation}
        </Link>
      )}
      {netWorth != null && (
        <Link
          to={`/sepa/${symbol}?tab=fundamentals`}
          className="val-chip val-fair"
          title={`Current net worth (market capitalization): ${fmtBig(netWorth)} — what the market is paying for the whole company right now.`}
        >
          💵 {fmtBig(netWorth)} net worth
        </Link>
      )}
      {equity != null && (
        <Link
          to={`/sepa/${symbol}?tab=fundamentals`}
          className="val-chip val-fair"
          title={`Shareholders' equity (book value): ${fmtBig(equity)} — total assets minus liabilities.`}
        >
          🏛️ {fmtBig(equity)} equity
        </Link>
      )}
    </div>
  );
}

function fmtBig(v: number | null | undefined): string {
  if (v == null) return '—';
  const a = Math.abs(v);
  if (a >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (a >= 1e9)  return `$${(v / 1e9).toFixed(1)}B`;
  if (a >= 1e6)  return `$${(v / 1e6).toFixed(0)}M`;
  return `$${v.toFixed(0)}`;
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
