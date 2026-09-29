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
 *
 * THE FILTER BOXES (Ajay 2026-09-29: "Can you add AMD raided and near demand
 * zone and near lower Key level filters to dual momentum please"). One
 * checkbox per SERVED item (🌀 / 📍 / 🔑), label + served pass count. CHECKED
 * is the SERVED `on` — the same rule as the toggle's pressed = served sort —
 * so a box shows what the server applied. A click hands the key to the
 * page's one `?dm=` setter. The served line (what each ticked box hid) is
 * printed verbatim with role="status", then each ticked box's served note;
 * unticked notes live only in the hover. Composes no sentence, counts nothing.
 *
 * THE 💰 BUTTON (Ajay 2026-09-29: "Also a sort by market cap please"). A third
 * order beside 🏎️ / 📍: largest first, a second click smallest first — both
 * served keys, written to `?sort=` through the same one setter. The served
 * `cap_sort.line` (which way, how many had no cap and sit last) is printed
 * verbatim while the order is on.
 */
import { Link } from 'react-router-dom';
import { DEFAULT_SORT, DM_SORT_MARKET_CAP, DM_SORT_MARKET_CAP_ASC, DM_SORT_NEAREST, dmCapSortNext } from '../lib/chartMaps';
import type { CmDualMomentumBoard, CmSort } from '../lib/chartMaps';
import { DM_FILTER_KEYS } from '../lib/dmFilters';
import type { CmDmFilterItem } from '../lib/dmFilters';

const DM_PAGE_ROUTE = '/dual-momentum';

const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;

type SortProps = {
  sorts?: CmSort[] | null;
  sort?: string | null;
  onSort: (key: string) => void;
};

/** The 🏎️ rank / 📍 nearest-demand toggle + the 💰 market-cap button.
 *  Labels served, pressed = served sort. The 💰 button renders only when BOTH
 *  cap keys are served; it shows the served direction's label and a click
 *  asks for `dmCapSortNext(served)` — largest first, then smallest first. */
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
  const capHi = label(DM_SORT_MARKET_CAP);
  const capLo = label(DM_SORT_MARKET_CAP_ASC);
  const capAsc = served === DM_SORT_MARKET_CAP_ASC;
  const capOn = served === DM_SORT_MARKET_CAP || capAsc;
  return (
    <span className="cm-phase-sub" role="group" aria-label="Order the leaders"
          data-testid="cm-dm-toggle">
      {btn(DEFAULT_SORT, rank)}
      {btn(DM_SORT_NEAREST, near)}
      {capHi && capLo ? (
        <button key="market_cap" type="button" aria-pressed={capOn}
                data-testid="cm-dm-sort-market_cap" data-dir={capAsc ? 'asc' : 'desc'}
                title={capOn ? (capAsc ? capHi : capLo) : undefined}
                className={`cm-phase-btn${capOn ? ' cm-phase-on' : ''}`}
                onClick={() => onSort(dmCapSortNext(served))}>
          {capAsc ? capLo : capHi}
        </button>
      ) : null}
    </span>
  );
}

const KNOWN_KEYS: ReadonlySet<string> = new Set(DM_FILTER_KEYS);
const count = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null;

type FilterProps = { filters: unknown; onToggle: (key: string) => void };

/** The 🌀 / 📍 / 🔑 boxes. Checked = served `on`; nothing for a malformed block. */
export function DualMomentumFilters({ filters, onToggle }: FilterProps) {
  if (!filters || typeof filters !== 'object' || Array.isArray(filters)) return null;
  const f = filters as { items?: unknown; line?: unknown; note?: unknown };
  if (!Array.isArray(f.items)) return null;
  const items = (f.items as unknown[]).filter((i): i is CmDmFilterItem =>
    !!i && typeof i === 'object' && typeof (i as CmDmFilterItem).key === 'string'
    && KNOWN_KEYS.has((i as CmDmFilterItem).key) && !!text((i as CmDmFilterItem).label));
  if (!items.length) return null;
  const line = text(f.line);
  const note = text(f.note);
  const on = items.filter((i) => i.on === true);
  return (
    <>
      <span className="cm-phase-sub" role="group" aria-label="Filter the leaders"
            data-testid="cm-dm-filters">
        {items.map((i) => {
          const n = count(i.pass);
          return (
            <label key={i.key} className="cm-ctl cm-ctl-check dm-filter"
                   title={text(i.note) ?? undefined}>
              <input type="checkbox" data-testid={`cm-dm-filter-${i.key}`}
                     checked={i.on === true} onChange={() => onToggle(i.key)} />
              {i.label}
              {n !== null ? <span className="dm-filter-count"> · {n}</span> : null}
            </label>
          );
        })}
      </span>
      {line ? <p className="cm-note" data-testid="cm-dm-filter-line" role="status">{line}</p> : null}
      {on.map((i) => (text(i.note)
        ? <p key={i.key} className="cm-note cm-dim" data-testid={`cm-dm-filter-note-${i.key}`}>{i.note}</p>
        : null))}
      {on.length && note ? <p className="cm-note cm-dim" data-testid="cm-dm-filters-note">{note}</p> : null}
    </>
  );
}

type Props = SortProps & {
  board: CmDualMomentumBoard | null | undefined;
  onToggleFilter?: (key: string) => void;
};

export default function DualMomentumBoardNote({ board, sorts, sort, onSort, onToggleFilter }: Props) {
  if (!board || typeof board !== 'object' || Array.isArray(board)) return null;
  const header = text((board as { header?: unknown }).header);
  if (!header) return null;
  const regimeLine = text((board as { regime_line?: unknown }).regime_line);
  const capRaw = (board as { cap_sort?: unknown }).cap_sort;
  const capLine = capRaw && typeof capRaw === 'object' && !Array.isArray(capRaw)
    ? text((capRaw as { line?: unknown }).line) : null;
  const note = text((board as { note?: unknown }).note);
  const raw = (board as { state?: unknown }).state;
  const state = raw === 'warming' || raw === 'no_scan' || raw === 'error' ? raw : 'ready';
  return (
    <div data-testid="cm-dm-board" data-state={state}>
      {regimeLine ? <p className="cm-note" data-testid="cm-dm-regime">{regimeLine}</p> : null}
      <DualMomentumSortToggle sorts={sorts} sort={sort} onSort={onSort} />
      {capLine ? <p className="cm-note" data-testid="cm-dm-cap-line" role="status">{capLine}</p> : null}
      {onToggleFilter
        ? <DualMomentumFilters filters={(board as { filters?: unknown }).filters}
                               onToggle={onToggleFilter} />
        : null}
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
