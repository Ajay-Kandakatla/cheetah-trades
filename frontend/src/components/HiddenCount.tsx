/* 🎯 HiddenCount — what the enterable filter removed, always on the page.
 *
 * Ajay 2026-09-15 asked for boards that show only enterable names. The risk
 * that comes with that ask is a board that empties itself and says nothing —
 * Bonde, Growth, Gabbar and ICT rows sit far from any demand band by
 * construction, and every 🚀 tile fails the room floor on a quiet day. So the
 * line is ALWAYS rendered while the filter is on, even at "0 hidden", it names
 * the top reasons in the backend's own words, and one click brings everything
 * back.
 *
 * Rows WITHOUT a read are not hidden and never counted as hidden: they are
 * shown last and reported separately. On a 2,500-name list the first ~30 s
 * after load every row is unread and the line honestly reads
 * "0 hidden · 1,800 without a read (shown last)" until the bounce-room poll
 * fills in. That is expected, and saying so beats a silently short board.
 *
 * Every word of a reason is SERVED (`reason_short`). This file counts and
 * formats; it never decides what is enterable.
 *
 * 🎯 UN-HIDE (Ajay 2026-09-17: "Can you give me a toggle for the room too? I am
 * not seeing all stocks on the selected filter due to this now"). The reasons
 * this line already prints become BUTTONS — zero new pixels, no new wording,
 * every chip's text is the SERVED `reason_short` passed in as a prop. Clicking
 * one brings back the rows blocked ONLY for that reason; a row blocked for two
 * needs both clicked, or the line would lie about what he is looking at.
 *
 * The verdict does not move. An un-hidden row is still the served BLOCKED: it
 * still wears its ⛔ chip, it is still not pushed, and no lane will enter it.
 *
 * With no `reasons` prop this component renders exactly what it rendered
 * before — the `topHiddenReasons` text, 3-capped.
 */
import { topHiddenReasons, UNLABELLED_REASON, type EnterableKind, type EnterableReasonStat } from '../lib/enterable';

/** The chip titles and the new clause, exported so the tests import the wording
 *  instead of retyping it. */
export const UNHIDE_OFF_TITLE = 'show these too — the verdict does not change: still BLOCKED, still not pushed, never entered';
export const UNHIDE_ON_TITLE = 'hide these again';
export const UNHIDDEN_TITLE = 'rows you brought back. Their verdict is unchanged — BLOCKED, not pushed, never entered.';
/** `${n} reasons un-hidden` — the filter-OFF clause. Singular at 1. */
export const unhideOffClause = (n: number) => `${n} reason${n === 1 ? '' : 's'} un-hidden`;

export function HiddenCount({
  hidden,
  unread = 0,
  hiddenByReason,
  enabled,
  kind = 'demand',
  onShowAll,
  onEnterableOnly,
  note,
  className = 'cm-hidden-count',
  reasons,
  unhidden = 0,
  onToggleReason,
  unhideCount = 0,
  reasonTitle,
}: {
  hidden: number;
  unread?: number;
  hiddenByReason?: Record<string, number> | null;
  enabled: boolean;
  /** The SERVED kind for this tab (payload `enterable_kind`). */
  kind?: EnterableKind | string | null;
  /** Turn the filter OFF — show everything. */
  onShowAll?: () => void;
  /** Turn the filter back ON. Falls back to `onShowAll` when the caller wired
   *  one toggle for both directions. */
  onEnterableOnly?: () => void;
  /** An extra clause for the title, e.g. the Hottest board's server-cut list. */
  note?: string | null;
  className?: string;
  /** The SERVED reason chips. Absent/empty → today's text line, unchanged. */
  reasons?: EnterableReasonStat[] | null;
  /** Rows drawn only because he un-hid their reason. */
  unhidden?: number;
  /** Flip one SERVED reason CODE in or out of the ignore set. */
  onToggleReason?: (code: string) => void;
  /** How many reason codes are un-hidden RIGHT NOW, even when the filter is
   *  OFF and the partition is inert. Names the state so one click on
   *  `enterable only` can never resurrect a set he cannot see. */
  unhideCount?: number;
  /** An extra sentence appended to one chip's title, keyed by CODE — the
   *  page uses it to say that the server-side room floor runs first. */
  reasonTitle?: Record<string, string> | null;
}) {
  if (kind === 'n/a') {
    return (
      <div className={className} title={note || undefined}>
        no demand read for this tab · filter off
      </div>
    );
  }

  if (!enabled) {
    /* The filter is OFF, so the partition is inert and no chip can render. The
     * line NAMES the un-hidden count instead — without it, one click on
     * `enterable only` resurrects a set he last touched on another tab. */
    return (
      <div className={className} title={note || undefined}>
        showing all ·{' '}
        {unhideCount > 0 ? (
          <><span title={UNHIDDEN_TITLE}>{unhideOffClause(unhideCount)}</span>{' · '}</>
        ) : null}
        <button type="button" className="cm-hidden-count-btn" onClick={onEnterableOnly || onShowAll}>
          enterable only
        </button>
      </div>
    );
  }

  /* A stat is drawn iff it is still holding rows back, or he has un-hidden it
   * (the `✓` state) — so a chip at zero that he has not clicked never
   * reaches the line at all. */
  const chips = (reasons || []).filter((r) => r.hidden > 0 || r.ignored);
  const useChips = Boolean(chips.length && onToggleReason);

  const top = topHiddenReasons(hiddenByReason);
  const breakdown = !useChips && top.length
    ? ` (${top.map((t) => `${t.n.toLocaleString()} ${t.reason}`).join(' · ')})`
    : '';

  return (
    <div className={className} title={note || undefined}>
      {hidden.toLocaleString()} hidden{breakdown}
      {useChips ? (
        <>
          {' ('}
          {chips.map((r, i) => (
            <span key={r.code}>
              {i ? ' · ' : ''}
              {r.toggleable && onToggleReason ? (
                <button type="button" data-reason={r.code}
                        className={`cm-hidden-reason${r.ignored ? ' cm-hidden-reason-on' : ''}`}
                        aria-pressed={r.ignored}
                        title={[r.ignored ? UNHIDE_ON_TITLE : UNHIDE_OFF_TITLE,
                                reasonTitle?.[r.code]].filter(Boolean).join(' — ')}
                        onClick={() => onToggleReason(r.code)}>
                  {r.ignored ? `✓ ${r.label}` : `${r.hidden.toLocaleString()} ${r.label}`}
                </button>
              ) : (
                <span>{`${r.hidden.toLocaleString()} ${r.label || UNLABELLED_REASON}`}</span>
              )}
            </span>
          ))}
          {')'}
        </>
      ) : null}
      {' · '}
      {useChips && unhidden > 0 ? (
        <><span title={UNHIDDEN_TITLE}>{`${unhidden.toLocaleString()} un-hidden`}</span>{' · '}</>
      ) : null}
      <button type="button" className="cm-hidden-count-btn" onClick={onShowAll}>
        show all
      </button>
      {unread > 0 ? ` · ${unread.toLocaleString()} without a read (shown last)` : ''}
    </div>
  );
}
