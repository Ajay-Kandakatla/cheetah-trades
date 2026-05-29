/**
 * SepaPoliticalChip — renders 1-3 small chips on a SEPA card when the
 * ticker matches an entry in src/lib/politicalDisclosures.ts.
 *
 * Two distinct chips per user request 2026-05-28 ("Trump or U.S.
 * government investments"):
 *
 *   🏛️ POTUS FAMILY      — gold; disclosed positions held by POTUS or
 *                          immediate family per OGE / news reporting
 *   🇺🇸 GOVT INVESTMENT   — blue; U.S. govt has equity stake (CHIPS Act
 *                          recipients) OR is a major contractor / program
 *                          participant
 *   🔍 INFERRED (dashed)  — softer treatment for scan-classified rows
 *                          that aren't directly disclosed
 *
 * All chips deep-link to the political_disclosure drill modal which
 * shows the disclosure band, source attribution, framework, pitfalls,
 * and the prominent "INFORMATIONAL, not predictive" caveat.
 */
import { getPoliticalChipFlags } from '../lib/politicalDisclosures';

interface Props {
  symbol: string;
  /** Click handler — opens the political_disclosure drill modal. */
  onOpenDrill?: () => void;
}

export function SepaPoliticalChip({ symbol, onOpenDrill }: Props) {
  const flags = getPoliticalChipFlags(symbol);
  if (!flags.entry) return null;

  // Build the shared tooltip body — same content for all chips on the
  // same card so the user can hover any of them and see the full
  // context. The drill modal goes deeper.
  const e = flags.entry;
  const cats = e.categories
    .map(c => c === 'potus_family' ? 'POTUS Family disclosed' :
              c === 'govt_investment' ? 'U.S. Govt equity / CHIPS investment' :
              c === 'govt_contractor' ? 'Govt contractor / program participant' :
              'Inferred (not directly disclosed)')
    .join(' · ');
  const tooltipBase =
    `${e.ticker} — ${e.company}\n` +
    `Sector: ${e.sector}\n` +
    `Category: ${cats}\n` +
    (e.disclosureBand ? `Disclosed band: ${e.disclosureBand}\n` : '') +
    (e.notes ? `Note: ${e.notes}\n` : '') +
    `\n` +
    `Informational only — NOT a buy or sell signal. Disclosed positions ` +
    `don't predict outcomes. Source: OGE.gov + reputable news reporting.\n\n` +
    `Click for full context.`;

  const handleClick = (ev: React.MouseEvent) => {
    ev.stopPropagation();
    onOpenDrill?.();
  };
  const handleKey = (ev: React.KeyboardEvent) => {
    if (ev.key === 'Enter' || ev.key === ' ') {
      ev.stopPropagation(); ev.preventDefault();
      onOpenDrill?.();
    }
  };

  return (
    <>
      {flags.hasPotusFamily && (
        <span
          role="button" tabIndex={0}
          className="pol-chip pol-chip--potus"
          title={tooltipBase}
          onClick={handleClick}
          onKeyDown={handleKey}
          style={{ cursor: onOpenDrill ? 'pointer' : 'default' }}
        >
          🏛️ POTUS Family{e.disclosureBand ? ` · ${e.disclosureBand}` : ''}
        </span>
      )}
      {(flags.hasGovtInvestment || flags.hasGovtContractor) && (
        <span
          role="button" tabIndex={0}
          className="pol-chip pol-chip--govt"
          title={tooltipBase}
          onClick={handleClick}
          onKeyDown={handleKey}
          style={{ cursor: onOpenDrill ? 'pointer' : 'default' }}
        >
          🇺🇸 {flags.hasGovtInvestment ? 'Govt Investment' : 'Govt Contractor'}
        </span>
      )}
      {flags.isInferred && !flags.hasPotusFamily && !flags.hasGovtInvestment && !flags.hasGovtContractor && (
        <span
          role="button" tabIndex={0}
          className="pol-chip pol-chip--inferred"
          title={tooltipBase}
          onClick={handleClick}
          onKeyDown={handleKey}
          style={{ cursor: onOpenDrill ? 'pointer' : 'default' }}
        >
          🔍 Inferred political signal
        </span>
      )}
    </>
  );
}
