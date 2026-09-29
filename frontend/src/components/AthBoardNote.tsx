/* AthBoardNote — the lines above the 🏔️ ATH grid (2026-09-29).
 *
 * Ajay 2026-09-29, verbatim: "Can you give me a new tab - for all the stocks
 * that are reaching all time highs? call it ATH. Once some of them are going
 * below their ATH or 52 Week Highs.."
 *
 * The board is grouped and ordered on the server (chart_maps/ath_tab.py). This
 * component prints its SERVED sentences verbatim — the header (how many names,
 * how many proven all-time, what was not listed and why) and the UNMEASURED
 * note — plus the 🏔️ At ATH / ↘️ Slipping toggle. It composes no sentence and
 * reads no count: a number typed here could disagree with the board.
 *
 * THE TOGGLE is two buttons whose LABELS are the served `sorts` entries
 * `default` and `slipping`; if either is missing the toggle does not render.
 * The PRESSED button is the SERVED `sort` — never the URL — so a
 * `?sort=slipping` the server coerced back to the default shows 🏔️ lit. A
 * click hands the key to the page's one sort setter.
 *
 * Renders NOTHING for an absent or malformed block. While the memo warms the
 * header is the served warming line and carries role="status".
 */
import { ATH_SORT_SLIPPING, DEFAULT_SORT } from '../lib/chartMaps';
import type { CmAthBoard, CmSort } from '../lib/chartMaps';

const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;

type SortProps = {
  sorts?: CmSort[] | null;
  sort?: string | null;
  onSort: (key: string) => void;
};

/** The 🏔️ At ATH / ↘️ Slipping toggle. Labels served, pressed = served sort. */
export function AthSortToggle({ sorts, sort, onSort }: SortProps) {
  const offered = Array.isArray(sorts) ? sorts : [];
  const label = (key: string): string | null => {
    const hit = offered.find((o) => !!o && typeof o === 'object' && o.key === key);
    return hit ? text(hit.label) : null;
  };
  const at = label(DEFAULT_SORT);
  const slip = label(ATH_SORT_SLIPPING);
  if (!at || !slip) return null;
  const served = typeof sort === 'string' ? sort : null;
  const btn = (key: string, lab: string) => {
    const on = served === key;
    return (
      <button key={key} type="button" aria-pressed={on}
              data-testid={`cm-ath-sort-${key}`}
              className={`cm-phase-btn${on ? ' cm-phase-on' : ''}`}
              onClick={() => onSort(key)}>
        {lab}
      </button>
    );
  };
  return (
    <span className="cm-phase-sub" role="group" aria-label="Pick the group"
          data-testid="cm-ath-toggle">
      {btn(DEFAULT_SORT, at)}
      {btn(ATH_SORT_SLIPPING, slip)}
    </span>
  );
}

type Props = SortProps & { board: CmAthBoard | null | undefined };

export default function AthBoardNote({ board, sorts, sort, onSort }: Props) {
  if (!board || typeof board !== 'object' || Array.isArray(board)) return null;
  const header = text((board as { header?: unknown }).header);
  if (!header) return null;
  const note = text((board as { note?: unknown }).note);
  const state = (board as { state?: unknown }).state === 'warming' ? 'warming' : 'ready';
  return (
    <div data-testid="cm-ath-board" data-state={state}>
      <AthSortToggle sorts={sorts} sort={sort} onSort={onSort} />
      <p className="cm-note" data-testid="cm-ath-header"
         role={state === 'warming' ? 'status' : undefined}>{header}</p>
      {note && note !== header ? <p className="cm-note" data-testid="cm-ath-note">{note}</p> : null}
    </div>
  );
}

export { AthBoardNote };
