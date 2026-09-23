/* 💎 CapitalQualityChips — the quality filter on 🚀 Explosive Growth, and the
 * line that says what it took away.
 *
 * Ajay 2026-09-22: "I need filter tab in explosive growth tab, whcih manage
 * quality like very less capital and hi ROI."
 *
 * EVERY CHIP SHIPS OFF, AND THAT IS NOT A STYLE CHOICE. Measured on the live
 * board 2026-09-22: stacking every definitional cut as one AND-gate leaves
 * 2 of 21 names. The file next door already learned the same lesson the hard
 * way — `ExplosiveGrowth.tsx:285` records that a literal `debt === 0` filter
 * returned ZERO of 29 rows, which is why `debtTier` defaults to the widest
 * honestly debt-light tier instead. A gate that hides 19 of 21 is not a filter,
 * it is a blindfold, so nothing here is on until he clicks it, and each chip
 * says how many rows it would take BEFORE he does.
 *
 * Every word on a chip is SERVED — `label` and `kind` come off
 * `capital_quality_summary`. This file counts and formats; it decides no
 * verdict and grades nothing.
 *
 * THE PRINTED COUNT IS THE COUNT OF WHAT A CLICK WILL DO. The served `hides_n`
 * is measured over the WHOLE board, and by the time these chips are drawn the
 * page has already applied the debt tier (ON by default at "net cash"), the
 * enterable cut, the sector picker and the demand/buyable checkboxes. Those
 * filters overlap this read — the default debt tier removes the levered names,
 * which are the same rows that fail `net_cash` — so the served figure promised
 * to hide rows that were not there and a click moved nothing. The number on the
 * chip is therefore counted over the rows IN HAND (`visibleComponentCounts`,
 * still over the backend's own verdicts), and the whole-board figure is kept in
 * the hover where it explains itself.
 *
 * A CHIP HIDES FAILURES, NEVER UNKNOWNS. `hides_n` is the served failure count
 * for exactly that reason: a row whose balance sheet could not answer the
 * question was not judged badly, so it stays on the board and the chip says how
 * many such rows it is leaving alone.
 *
 * ONE CLICK BRINGS THEM BACK. The chips ARE the per-reason un-hide — clicking a
 * lit chip turns that one question off and returns its rows, and the breakdown
 * inside the count line is made of the same buttons, the way HiddenCount's
 * served reason chips work.
 */
import {
  capitalCoverage, componentStats, hiddenClause,
  type CapitalCount, type CapitalQualitySummary, type CapitalVisible,
} from '../lib/capitalQuality';

export const CHIP_ROW_TITLE =
  'Balance-sheet questions, answered from the filings. A chip hides the rows '
  + 'that FAIL its question — never the rows that could not answer it. Click a '
  + 'lit chip to bring its rows back.';

/** The reset. Named here so the test imports the wording instead of retyping it. */
export const SHOW_EVERYTHING = 'show everything';

/** Per-chip hover. `hides` and `unknown` describe the rows ON SCREEN — what a
 *  click will actually do. `servedHides` is the whole-board failure count and
 *  is named as such, and only when the two differ, which is precisely when the
 *  board's other filters have already taken some of those rows. */
export function chipTitle(
  kind: string | null | undefined,
  hides: number,
  unknown: number,
  on: boolean,
  servedHides?: number | null,
): string {
  const board = typeof servedHides === 'number' && servedHides !== hides
    ? `${servedHides} fail it on the whole board, before the other filters.`
    : null;
  return [
    kind ? `${kind} question.` : null,
    `Hides ${hides} row${hides === 1 ? '' : 's'} that FAIL it.`,
    `${unknown} row${unknown === 1 ? '' : 's'} cannot answer it and are never hidden.`,
    board,
    on ? 'Click to bring them back.' : 'Click to hide them.',
  ].filter(Boolean).join(' ');
}

/** The chip row. Renders nothing at all when the backend served no summary —
 *  an older build, or an attach that refused — rather than an empty control
 *  bar that looks like a filter with no options.
 *
 *  There is deliberately NO reset button here: the count line below carries
 *  the one `show everything`, and it is drawn the whole time any chip is on.
 *  Two identically worded resets on one board is two things to read and one
 *  more thing to get wrong. */
export function CapitalQualityChips({
  summary,
  counts,
  active,
  onToggle,
}: {
  summary?: CapitalQualitySummary | null;
  /** Per-question fail / unknown counts over the rows being DRAWN. Absent
   *  falls back to the served whole-board figures, which is only right when
   *  nothing else has filtered the board. */
  counts?: Record<string, CapitalCount> | null;
  active: ReadonlySet<string>;
  onToggle: (key: string) => void;
}) {
  const stats = componentStats(summary);
  if (!stats.length) return null;

  return (
    <div className="eg-qchips" data-testid="eg-qchips" title={CHIP_ROW_TITLE}>
      <span className="eg-qchips-lead">💎 Quality</span>
      {stats.map((c) => {
        const on = active.has(c.key);
        const served = typeof c.hides_n === 'number' ? c.hides_n : 0;
        const here = counts?.[c.key];
        const hides = here ? here.fail : served;
        const unknown = here
          ? here.unknown
          : (typeof c.unknown_n === 'number' ? c.unknown_n : 0);
        return (
          <button
            key={c.key}
            type="button"
            aria-pressed={on}
            data-testid={`eg-qchip-${c.key}`}
            className={`cm-hidden-reason${on ? ' cm-hidden-reason-on' : ''}`}
            title={chipTitle(c.kind, hides, unknown, on, served)}
            onClick={() => onToggle(c.key)}
          >
            {on ? '✓ ' : ''}{c.label || c.key} ({hides})
          </button>
        );
      })}
    </div>
  );
}

/* ───────────────────────────────────────────────────── what it took away */

/** The count line. Drawn the WHOLE time a chip is on, even at zero hidden —
 *  the HiddenCount rule, for the same reason: a board that empties itself and
 *  says nothing is the failure mode, and "0 hidden" is information too.
 *
 *  It always prints how many rows are SHOWING, so an empty table is a stated
 *  count and never an unexplained blank.
 */
export function CapitalQualityHidden({
  summary,
  shown,
  hidden,
  unread,
  hiddenByKey,
  active,
  onToggle,
  onClear,
}: {
  summary?: CapitalQualitySummary | null;
  shown: number;
  hidden: number;
  unread: number;
  hiddenByKey: Record<string, number>;
  active: ReadonlySet<string>;
  onToggle: (key: string) => void;
  onClear: () => void;
}) {
  if (!active || active.size === 0) return null;
  const stats = componentStats(summary);
  const byKey = new Map(stats.map((c) => [c.key, c]));
  /* Served order, and only the chips still holding a row back. A chip at zero
   * that he has switched on is already lit above; repeating it here at zero
   * would pad the line with nothing. */
  const parts = stats.filter((c) => (hiddenByKey[c.key] || 0) > 0);

  return (
    <div className="cm-hidden-count" data-testid="eg-qhidden">
      💎 <b>{shown.toLocaleString()} showing</b> · {hiddenClause(hidden)}
      {parts.length > 0 && (
        <>
          {' ('}
          {parts.map((c, i) => (
            <span key={c.key}>
              {i > 0 && ' · '}
              <button
                type="button"
                className="cm-hidden-reason cm-hidden-reason-on"
                data-testid={`eg-qhidden-${c.key}`}
                title={`Bring back the ${hiddenByKey[c.key]} rows this question is holding back. `
                  + 'Their verdict does not change — they still fail it.'}
                onClick={() => onToggle(c.key)}
              >
                {hiddenByKey[c.key]} {byKey.get(c.key)?.label || c.key}
              </button>
            </span>
          ))}
          {')'}
        </>
      )}
      {unread > 0 && (
        <> · <span title="No capital-quality read on these rows. Never hidden — shown last.">
          {unread.toLocaleString()} without a read (shown last)
        </span></>
      )}
      {' · '}
      <button type="button" className="cm-hidden-count-btn" onClick={onClear}>
        {SHOW_EVERYTHING}
      </button>
    </div>
  );
}

/* ───────────────────────────────────────────────────────── the honesty line */

/** The board's quality honesty line. The NOT-MEASURED sentence is SERVED
 *  (`measured_note`, pinned on the backend to `MEASURED = False` by test) and
 *  is printed verbatim — no clause of it is typed here, and none of it is
 *  edited, so the sentence on the page cannot drift from the flag that governs
 *  it. Rendered only when the summary arrived. */
export function CapitalQualityNote({ summary, visible }: {
  summary?: CapitalQualitySummary | null;
  /** Grade counts over the rows being DRAWN. Same reason as the chips: the
   *  "N of M fail nothing" clause must describe the table underneath it. */
  visible?: CapitalVisible | null;
}) {
  const note = summary?.measured_note;
  if (!summary || !note) return null;
  const coverage = capitalCoverage(summary, visible);
  return (
    <div className="eg-note eg-qnote" data-testid="eg-qnote">
      💎 {coverage ? <>{coverage}. </> : null}
      <b>{note}</b>
    </div>
  );
}
