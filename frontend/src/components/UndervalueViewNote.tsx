/* UndervalueViewNote — the 💎 / 🏷️ toggle above the Under Value grid (2026-09-29).
 *
 * Ajay 2026-09-29, verbatim: "create me another tab where valuations are wrong
 * based on analytics …" then "Use the same tab actually".
 *
 * Every word here is SERVED (chart_maps/undervalue_peers.view_block): the two
 * button labels, the header and the note. This component composes no sentence,
 * reads no count and does no arithmetic — a number typed here could disagree
 * with the board.
 *
 * THE TOGGLE: the PRESSED button is the SERVED `view`, never the URL, so a
 * `?uv=` the server did not honour shows the view it actually served. A click
 * hands the key to the page's one setter. Renders NOTHING unless the block is
 * an object whose options carry both views with non-empty labels.
 */
import { UV_VIEW_PEERS, UV_VIEW_PSG } from '../lib/undervalueView';
import type { CmUndervalueView } from '../lib/undervalueView';

const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;

type Props = {
  block: CmUndervalueView | null | undefined;
  onView: (key: string) => void;
};

export default function UndervalueViewNote({ block, onView }: Props) {
  if (!block || typeof block !== 'object' || Array.isArray(block)) return null;
  const options = Array.isArray((block as { options?: unknown }).options)
    ? (block as { options: unknown[] }).options : [];
  const label = (key: string): string | null => {
    const hit = options.find((o) => !!o && typeof o === 'object' && !Array.isArray(o)
      && (o as { key?: unknown }).key === key) as { label?: unknown } | undefined;
    return hit ? text(hit.label) : null;
  };
  const psg = label(UV_VIEW_PSG);
  const alt = label(UV_VIEW_PEERS);
  if (!psg || !alt) return null;
  const served = text((block as { view?: unknown }).view);
  const header = text((block as { header?: unknown }).header);
  const note = text((block as { note?: unknown }).note);
  const btn = (key: string, lab: string) => {
    const on = served === key;
    return (
      <button key={key} type="button" aria-pressed={on}
              data-testid={`cm-uv-view-${key}`}
              className={`cm-phase-btn${on ? ' cm-phase-on' : ''}`}
              onClick={() => onView(key)}>
        {lab}
      </button>
    );
  };
  return (
    <div data-testid="cm-uv-board" data-view={served ?? undefined}>
      <span className="cm-phase-sub" role="group" aria-label="Pick the view"
            data-testid="cm-uv-toggle">
        {btn(UV_VIEW_PSG, psg)}
        {btn(UV_VIEW_PEERS, alt)}
      </span>
      {header ? <p className="cm-note" data-testid="cm-uv-header">{header}</p> : null}
      {note && note !== header ? <p className="cm-note" data-testid="cm-uv-note">{note}</p> : null}
    </div>
  );
}
