/* KeyLevelsBoardNote — the line above the 🔑 Key Levels grid (2026-09-28).
 *
 * Ajay 2026-09-28, verbatim: "Also create me tab for keylevel main. Sort them
 * by stocks that are near lower keylevels". The board is ranked on the server
 * (chart_maps/key_levels_tab.py); this component prints its two SERVED
 * sentences verbatim — the header (how many names were ranked, how many were
 * not and why, what the order is) and the UNMEASURED note. It composes no
 * sentence and reads no count: a number typed here could disagree with the
 * board it describes.
 *
 * Renders NOTHING unless `board.header` is a non-empty string, so an older
 * payload, a malformed block or another tab's payload draws no empty box.
 * While the memo warms the header is the served warming line and carries
 * role="status" so a screen reader announces it.
 */
import type { CmKeyLevelsBoard } from '../lib/chartMaps';

const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;

export default function KeyLevelsBoardNote(
  { board }: { board: CmKeyLevelsBoard | null | undefined },
) {
  if (!board || typeof board !== 'object') return null;
  const header = text((board as { header?: unknown }).header);
  if (!header) return null;
  const note = text((board as { note?: unknown }).note);
  const state = (board as { state?: unknown }).state === 'warming' ? 'warming' : 'ready';
  return (
    <div data-testid="cm-keylevels-board" data-state={state}>
      <p className="cm-note" role={state === 'warming' ? 'status' : undefined}>{header}</p>
      {note && note !== header ? <p className="cm-note">{note}</p> : null}
    </div>
  );
}

export { KeyLevelsBoardNote };
