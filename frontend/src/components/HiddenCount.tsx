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
 */
import { topHiddenReasons, type EnterableKind } from '../lib/enterable';

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
}) {
  if (kind === 'n/a') {
    return (
      <div className={className} title={note || undefined}>
        no demand read for this tab · filter off
      </div>
    );
  }

  if (!enabled) {
    return (
      <div className={className} title={note || undefined}>
        showing all ·{' '}
        <button type="button" className="cm-hidden-count-btn" onClick={onEnterableOnly || onShowAll}>
          enterable only
        </button>
      </div>
    );
  }

  const top = topHiddenReasons(hiddenByReason);
  const breakdown = top.length
    ? ` (${top.map((t) => `${t.n.toLocaleString()} ${t.reason}`).join(' · ')})`
    : '';

  return (
    <div className={className} title={note || undefined}>
      {hidden.toLocaleString()} hidden{breakdown} ·{' '}
      <button type="button" className="cm-hidden-count-btn" onClick={onShowAll}>
        show all
      </button>
      {unread > 0 ? ` · ${unread.toLocaleString()} without a read (shown last)` : ''}
    </div>
  );
}
