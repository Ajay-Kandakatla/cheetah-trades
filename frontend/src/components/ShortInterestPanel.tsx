/* 🩳 ShortInterestPanel — the full short-interest read on the ticker page's
 * Smart Money tab.
 *
 * Ajay 2026-10-03: "... also the individual tickers please".
 *
 * Prints the served rows verbatim (settlement and publication dates, shares
 * short, % of float and % of shares outstanding each with its own count, source
 * and as-of date, days to cover, freshness, source). The explainer under it is
 * the ℹ️ rules section `short_interest` from GET /supply-demand/rules, so every
 * definition lives next to the backend constants it describes. Nothing here
 * computes, colours, sorts or ranks.
 *
 * 🩳 2026-11-26 (spec sishares §3.6): under the rows, the served 6-K issuances whose link passed siIssuances
 * (SI_FILING_URL_PREFIX only) as links opening the SEC filing in a new tab (rel="noopener noreferrer"), each under its
 * served label. No issuance with a link → the panel is unchanged. Ajay: "Fix the POM chip and the 6-K dilution check."
 */
import { useShortInterest } from '../hooks/useShortInterest';
import { useRulesInfo } from '../hooks/useRulesInfo';
import { SI_NOT_WARMED_TEXT, SI_REQUEST_FAILED_TEXT, siIssuances } from '../lib/shortInterest';

export function ShortInterestPanel({ symbol }: { symbol: string }) {
  const { read, loaded, failed } = useShortInterest(symbol);
  const rules = useRulesInfo('short_interest');
  if (!loaded) return null;
  const picks = rules.section?.picks ?? [];
  const links = siIssuances(read).filter((x) => x.url);
  return (
    <div className="si-panel" data-testid="si-panel" style={{ margin: '0.8rem 0' }}>
      <h4 style={{ margin: '0 0 0.4rem' }}>🩳 Short interest</h4>
      {read ? (
        <dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '0.2rem 0.8rem', margin: 0 }}>
          {read.rows.map((r, i) => [
            <dt key={`k${i}`} style={{ fontWeight: 600 }}>{r.k}</dt>,
            <dd key={`v${i}`} style={{ margin: 0 }}>{r.v}</dd>,
          ])}
        </dl>
      ) : (
        <p style={{ margin: 0, opacity: 0.8 }}>{failed ? SI_REQUEST_FAILED_TEXT : SI_NOT_WARMED_TEXT}</p>
      )}
      {links.length ? (
        <ul className="si-issuances" data-testid="si-issuances" style={{ margin: '0.3rem 0 0', paddingLeft: '1.1rem' }}>
          {links.map((x, i) => (
            <li key={`${x.url}-${i}`}>
              <a href={x.url as string} target="_blank" rel="noopener noreferrer" title={x.text || undefined}>{x.label}</a>
            </li>
          ))}
        </ul>
      ) : null}
      {picks.length ? (
        <details style={{ marginTop: '0.4rem' }}>
          <summary>What this number is (and is not)</summary>
          <ul>
            {picks.map((p, i) => <li key={i}>{p}</li>)}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
