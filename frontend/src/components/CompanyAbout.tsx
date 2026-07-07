import { useState } from 'react';
import { useCompany } from '../hooks/useCompany';

/* ==========================================================================
   CompanyAbout — "What this company does" panel for ticker detail pages.
   Uses yfinance longBusinessSummary, cached 30 days in Mongo.
   ========================================================================== */

type Props = {
  symbol: string;
  /** When true, summary text starts collapsed at ~3 lines with a Show more toggle. */
  collapsed?: boolean;
};

function fmtEmployees(n: number | null | undefined): string {
  if (!n) return '';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M employees`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K employees`;
  return `${n.toLocaleString()} employees`;
}

export function CompanyAbout({ symbol, collapsed = true }: Props) {
  const { info, loading } = useCompany(symbol);
  const [expanded, setExpanded] = useState(!collapsed);

  if (loading || !info) return null;
  if (!info.summary) return null;

  const summary = info.summary;
  const isLong = summary.length > 280;
  const shown = expanded || !isLong ? summary : summary.slice(0, 280) + '…';

  return (
    <section className="company-about">
      <header className="company-about__head">
        <h3 className="company-about__title">About {info.name || symbol}</h3>
        <div className="company-about__meta mono">
          {info.industry && <span>{info.industry}</span>}
          {info.sector && info.industry !== info.sector && <span>· {info.sector}</span>}
          {info.employees != null && <span>· {fmtEmployees(info.employees)}</span>}
          {info.ipo_year != null && <span>· IPO {info.ipo_year}</span>}
        </div>
      </header>

      <p id={`company-about-summary-${symbol}`} className="company-about__summary">{shown}</p>

      {isLong && (
        <button type="button"
                className="company-about__toggle"
                aria-expanded={expanded}
                aria-controls={`company-about-summary-${symbol}`}
                onClick={() => setExpanded(!expanded)}>
          {expanded ? '▴ Show less' : '▾ Show more'}
        </button>
      )}

      <div className="company-about__footer mono">
        {info.ceo && <span>CEO {info.ceo}</span>}
        {info.city && info.country && (
          <span>· {info.city}{info.state ? `, ${info.state}` : ''}, {info.country}</span>
        )}
        {info.website && (
          <a href={info.website} target="_blank" rel="noopener noreferrer"
             className="company-about__link">{info.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}</a>
        )}
      </div>
    </section>
  );
}
