/* DualMomentumBoardNote — the lines above the 🏎️ Dual Momentum grid (2026-09-29).
 *
 * Ajay 2026-09-29, verbatim: "Can you pull these in to chart maps and add the
 * demand zones logic to these? https://pounce.ajaykandakatla.dev/dual-momentum"
 * and, the same minute, "I want a toggle and also the check boxes we have like
 * AMD and supple and demand zones computing and also key levels".
 *
 * The board is ranked on the server (chart_maps/dual_momentum_tab.py, the
 * /dual-momentum page's own engine). This component prints its SERVED
 * sentences verbatim — the regime line, the header (what was ranked, how many
 * sit above a demand band, floor states, what the order is) and the
 * UNMEASURED note — plus the 🏎️ / 📍 toggle. It composes no sentence and reads
 * no count: a number typed here could disagree with the board it describes.
 *
 * THE TOGGLE is two buttons whose LABELS are the served `sorts` entries
 * `default` and `nearest_demand`; if either is missing the toggle does not
 * render (a button that asks for an order the server does not offer would be
 * a silent no-op). The PRESSED button is the SERVED `sort` — never the URL —
 * so a `?sort=nearest_demand` the server coerced back to the rank shows the
 * rank lit. A click hands the key to the page's one sort setter, the same one
 * the Sort select uses, so the two controls can never disagree.
 *
 * Renders NOTHING for an absent or malformed block. While the memo warms the
 * header is the served warming line and carries role="status".
 */
import { Link } from 'react-router-dom';
import { DEFAULT_SORT, DM_SORT_NEAREST } from '../lib/chartMaps';
import type { CmDualMomentumBoard, CmSort } from '../lib/chartMaps';

const DM_PAGE_ROUTE = '/dual-momentum';

const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;

type SortProps = {
  sorts?: CmSort[] | null;
  sort?: string | null;
  onSort: (key: string) => void;
};

/** The 🏎️ rank / 📍 nearest-demand toggle. Labels served, pressed = served sort. */
export function DualMomentumSortToggle({ sorts, sort, onSort }: SortProps) {
  const offered = Array.isArray(sorts) ? sorts : [];
  const label = (key: string): string | null => {
    const hit = offered.find((o) => !!o && typeof o === 'object' && o.key === key);
    return hit ? text(hit.label) : null;
  };
  const rank = label(DEFAULT_SORT);
  const near = label(DM_SORT_NEAREST);
  if (!rank || !near) return null;
  const served = typeof sort === 'string' ? sort : null;
  const btn = (key: string, lab: string) => {
    const on = served === key;
    return (
      <button key={key} type="button" aria-pressed={on}
              data-testid={`cm-dm-sort-${key}`}
              className={`cm-phase-btn${on ? ' cm-phase-on' : ''}`}
              onClick={() => onSort(key)}>
        {lab}
      </button>
    );
  };
  return (
    <span className="cm-phase-sub" role="group" aria-label="Order the leaders"
          data-testid="cm-dm-toggle">
      {btn(DEFAULT_SORT, rank)}
      {btn(DM_SORT_NEAREST, near)}
    </span>
  );
}

type Props = SortProps & { board: CmDualMomentumBoard | null | undefined };

export default function DualMomentumBoardNote({ board, sorts, sort, onSort }: Props) {
  if (!board || typeof board !== 'object' || Array.isArray(board)) return null;
  const header = text((board as { header?: unknown }).header);
  if (!header) return null;
  const regimeLine = text((board as { regime_line?: unknown }).regime_line);
  const note = text((board as { note?: unknown }).note);
  const raw = (board as { state?: unknown }).state;
  const state = raw === 'warming' || raw === 'no_scan' || raw === 'error' ? raw : 'ready';
  return (
    <div data-testid="cm-dm-board" data-state={state}>
      {regimeLine ? <p className="cm-note" data-testid="cm-dm-regime">{regimeLine}</p> : null}
      <DualMomentumSortToggle sorts={sorts} sort={sort} onSort={onSort} />
      <p className="cm-note" data-testid="cm-dm-header"
         role={state === 'warming' ? 'status' : undefined}>{header}</p>
      {note && note !== header ? <p className="cm-note" data-testid="cm-dm-note">{note}</p> : null}
      <p className="cm-note cm-dim">
        <Link to={DM_PAGE_ROUTE} data-testid="cm-dm-page-link">Open the Dual Momentum page</Link>
      </p>
    </div>
  );
}

export { DualMomentumBoardNote };
