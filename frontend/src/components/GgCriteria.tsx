/* GgCriteriaList — the ONE rule-row printer of the 🚩 card, shared (2026-11-24, spec ggrun §3.5, WP fe-run).
 *
 * A PURE MOVE of the 🚩 card's inline list (GajjalaBoard.tsx) so the 👀 Watch's ▶ Rules panel prints the rows through the
 * SAME markup and the SAME text function (lib/gajjala criteriaText), never a second printer. Ajay 2026-11-24: "…for
 * giving verbatim of passed rules and failed rules of that stock like you do in other tabs..".
 * Rows in the order given (the detector's), never re-sorted. Imports no CSS: the 🚩 boards style it from gajjala.css,
 * the Watch panel from its scoped copies in styles/ggwRun.css. */
import { criteriaText, type GgCriterion } from '../lib/gajjala';

export function GgCriteriaList({ criteria }: { criteria: GgCriterion[] | null | undefined }) {
  if (!criteria?.length) return null;
  return (
    <ul className="gg-criteria" data-testid="gg-criteria">
      {criteria.map((c) => (
        <li key={c.key} className={c.ok === true ? 'gg-ok' : c.ok === false ? 'gg-miss' : 'gg-unjudged'}>
          {criteriaText(c)}
        </li>
      ))}
    </ul>
  );
}
