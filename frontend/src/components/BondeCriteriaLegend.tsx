/* 📋 The criterion legend for the 📈 Bonde tab — ONE fold, at the top.
 *
 * Every criterion on the pick line is one sentence he published, with its link
 * and its date. That sourcing is the whole point of the line: this board spent
 * 2026-09-20 removing nine claims that had been attributed to him and were not
 * his, so a criterion without a quote and a URL beside it has no business on
 * his screen.
 *
 * Since the interview arrived (2026-09-20) a criterion may carry EXTRA cites —
 * the same sentence said again on tape, linked at the second it starts. They
 * are ADDED under the criterion, never replacing the sentence it had.
 *
 * The component types none of it. `legend` is served whole
 * (`sepa/bonde_picks.legend()`), so the quotes have exactly one home and a
 * paraphrase cannot creep in on the rendering side.
 */
import { StudyNote } from './StudyNote';
import { citeLine, sourceLabel, type BondePickLegend } from '../lib/bondePicks';

export type BondeCriteriaLegendProps = { legend?: BondePickLegend | null };

export function BondeCriteriaLegend({ legend }: BondeCriteriaLegendProps) {
  if (!legend || !legend.header) return null;
  const all = legend.criteria || [];
  const computed = all.filter((c) => c && c.computed);
  const only = all.filter((c) => c && !c.computed);
  const ordered = [...computed, ...only];
  const tapeHeader = legend.tape_header || null;
  const tape = legend.tape || null;

  return (
    <StudyNote id="bonde-criteria" testId="bonde-criteria" glyph="📋" headingAs="h3"
               className="bd-pick-legend" headline={legend.header}>
      {tapeHeader
        ? (
          <p className="bd-pick-tape" data-testid="bonde-tape-header">
            “{tapeHeader.quote}”{' — '}
            <a className="bd-pick-src" href={tapeHeader.url} target="_blank" rel="noreferrer">
              on tape [{tapeHeader.ts}]
            </a>
          </p>
        )
        : null}
      {ordered.map((c) => (
        <p key={c.key} className="bd-pick-crit" data-testid={`bonde-criterion-${c.key}`}>
          <strong>{c.label}</strong>
          {' — '}
          <span className="bd-pick-quote">“{c.quote}”</span>
          {' '}
          <a className="bd-pick-src" href={c.url} target="_blank" rel="noreferrer">
            {sourceLabel(c)}
          </a>
          {c.data ? <span className="bd-vdim"> — {c.data}</span> : null}
          {c.not_computed_why
            ? <span className="bd-vdim"> — not read here: {c.not_computed_why}</span>
            : null}
          {c.his_call
            ? <span className="bd-vdim"> — Ajay’s call: {c.his_call}</span>
            : null}
          {(c.cites || []).map((cite, i) => (
            <span key={cite.url} className="bd-pick-cite"
                  data-testid={`bonde-cite-${c.key}-${i}`}>
              {citeLine(cite)}
              {' '}
              <a className="bd-pick-src" href={cite.url} target="_blank" rel="noreferrer">↗</a>
              {cite.note ? <span className="bd-vdim"> — {cite.note}</span> : null}
            </span>
          ))}
        </p>
      ))}
      {legend.not_a_source
        ? <p className="bd-vdim" data-testid="bonde-not-a-source">{legend.not_a_source}</p>
        : null}
      {tape
        ? (
          <p className="bd-vdim" data-testid="bonde-tape-source">
            Tape: {tape.show} — “{tape.title}”, published {tape.published}, recorded{' '}
            {tape.recorded}
            {tape.recorded_cite
              ? (
                <>
                  {' (his words at '}
                  <a className="bd-pick-src" href={tape.recorded_cite.url}
                     target="_blank" rel="noreferrer">
                    [{tape.recorded_cite.ts}]
                  </a>
                  {')'}
                </>
              )
              : null}
            , received {tape.received}.
          </p>
        )
        : null}
      {legend.warm_note
        ? <p className="bd-vdim" data-testid="bonde-warm-note">{legend.warm_note}</p>
        : null}
    </StudyNote>
  );
}

export default BondeCriteriaLegend;
