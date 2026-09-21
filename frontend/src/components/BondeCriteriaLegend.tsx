/* 📋 The criterion legend for the 📈 Bonde tab — ONE fold, at the top.
 *
 * Every criterion on the pick line is one sentence he published, with its link
 * and its date. That sourcing is the whole point of the line: this board spent
 * 2026-09-20 removing nine claims that had been attributed to him and were not
 * his, so a criterion without a quote and a URL beside it has no business on
 * his screen.
 *
 * The component types none of it. `legend` is served whole
 * (`sepa/bonde_picks.legend()`), so the quotes have exactly one home and a
 * paraphrase cannot creep in on the rendering side.
 */
import { StudyNote } from './StudyNote';
import type { BondePickLegend } from '../lib/bondePicks';

export type BondeCriteriaLegendProps = { legend?: BondePickLegend | null };

export function BondeCriteriaLegend({ legend }: BondeCriteriaLegendProps) {
  if (!legend || !legend.header) return null;
  const all = legend.criteria || [];
  const computed = all.filter((c) => c && c.computed);
  const only = all.filter((c) => c && !c.computed);
  const ordered = [...computed, ...only];

  return (
    <StudyNote id="bonde-criteria" testId="bonde-criteria" glyph="📋" headingAs="h3"
               className="bd-pick-legend" headline={legend.header}>
      {ordered.map((c) => (
        <p key={c.key} className="bd-pick-crit" data-testid={`bonde-criterion-${c.key}`}>
          <strong>{c.label}</strong>
          {' — '}
          <span className="bd-pick-quote">“{c.quote}”</span>
          {' '}
          <a className="bd-pick-src" href={c.url} target="_blank" rel="noreferrer">
            {[c.source, c.date].filter(Boolean).join(' ')}
          </a>
          {c.data ? <span className="bd-vdim"> — {c.data}</span> : null}
          {c.not_computed_why
            ? <span className="bd-vdim"> — not read here: {c.not_computed_why}</span>
            : null}
          {c.his_call
            ? <span className="bd-vdim"> — Ajay’s call: {c.his_call}</span>
            : null}
        </p>
      ))}
      {legend.not_a_source
        ? <p className="bd-vdim" data-testid="bonde-not-a-source">{legend.not_a_source}</p>
        : null}
      {legend.warm_note
        ? <p className="bd-vdim" data-testid="bonde-warm-note">{legend.warm_note}</p>
        : null}
    </StudyNote>
  );
}

export default BondeCriteriaLegend;
