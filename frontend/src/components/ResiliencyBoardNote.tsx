/* ResiliencyBoardNote — the lines above the 🛡️ Resiliency grid (2026-09-30).
 *
 * Ajay 2026-09-30, verbatim: "Can you build me a new tab- Resileincy. This is
 * to help me with #1 - Stocks that are not going to by more than 0.5% during a
 * T1 event like FOMC or any others like todays Inflation and GDP track T2s as
 * well. #3 - Tape is positive and bullish EOD or Pre market. but volume has to
 * be accounted for. We have all of this data already."
 *
 * The board is read and ordered on the server (chart_maps/resiliency_tab.py).
 * This component prints its SERVED sentences verbatim — the header, today's
 * data-day line, the 📅 market line (SPY, RSP, the median name, n up of n read;
 * 2026-10-07), the data-days line, one line per rule, each box's note, the
 * study sentences and the note — plus the five-button order toggle and the
 * four boxes. It composes no sentence, reads no count and does no maths: a
 * number typed here could disagree with the board it describes.
 *
 * THE TOGGLE is five buttons whose LABELS are the served `sorts` entries
 * `res_today`, `res_t1`, `res_t2`, `res_down` and `res_growth` (2026-10-07);
 * if any one is missing the toggle does not render (a button that asks for an
 * order the server does not offer would be a silent no-op). `default` is never
 * a button: the server RESOLVES it (📅 today's move once the session has a
 * print, else 🛡️ T1) and serves the explicit key it resolved to as `sort` — the
 * generic Sort select keeps `default`. The PRESSED button is the SERVED `sort`
 * — never the URL. A click hands the key to the page's one sort setter.
 *
 * THE BOXES are the Dual Momentum boxes, reused (DualMomentumFilters with this
 * tab's served keys and test ids): CHECKED = the served `on`, the "must match
 * all" switch only while a box is ticked, CHECKED = the served mode. Ticked
 * boxes print their served note under the boxes; the unticked boxes' notes sit
 * in the rules fold with the rule lines, the data-days line and the study
 * sentences — every one printed once, all of them in the DOM.
 *
 * 🚀 GROWTH COVERAGE (2026-10-07 b — "make sure you do a sanity chcek fo
 * missing data pieces over all"): after the market line it prints the served
 * `growth_line` and, under it, a fold of the served `growth_gaps` lines (the
 * most-traded names in each gap). The server serves both ONLY on the 🚀 order;
 * this component composes no count of its own and renders nothing for an
 * absent or malformed block.
 *
 * Renders NOTHING for an absent or malformed block. While the memo warms the
 * header is the served warming line with role="status" and no box renders.
 */
import { RES_SORT_DOWN, RES_SORT_GROWTH, RES_SORT_T1, RES_SORT_T2, RES_SORT_TODAY } from '../lib/chartMaps';
import type { CmResiliencyBoard, CmSort } from '../lib/chartMaps';
import { RES_FILTER_KEYS } from '../lib/resiliencyFilters';
import { DualMomentumFilters } from './DualMomentumBoardNote';

const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;
const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : null;

const SORT_KEYS = [RES_SORT_TODAY, RES_SORT_T1, RES_SORT_T2, RES_SORT_DOWN, RES_SORT_GROWTH] as const;
const STUDY_KEYS = ['t1', 't2', 'eod', 'pre'] as const;
const KNOWN_BOXES: ReadonlySet<string> = new Set(RES_FILTER_KEYS);

type SortProps = {
  sorts?: CmSort[] | null;
  sort?: string | null;
  onSort: (key: string) => void;
};

/** The 📅 today / 🛡️ T1 / 🛡️ T2 / 🛡️ SPY-down / 🚀 growth toggle. Labels served, pressed = served sort. */
export function ResiliencySortToggle({ sorts, sort, onSort }: SortProps) {
  const offered = Array.isArray(sorts) ? sorts : [];
  const label = (key: string): string | null => {
    const hit = offered.find((o) => !!o && typeof o === 'object' && o.key === key);
    return hit ? text(hit.label) : null;
  };
  const labels = SORT_KEYS.map((k) => [k, label(k)] as const);
  if (labels.some(([, l]) => !l)) return null;
  const served = typeof sort === 'string' ? sort : null;
  return (
    <span className="cm-phase-sub" role="group" aria-label="Order the board"
          data-testid="cm-res-toggle">
      {labels.map(([key, lab]) => {
        const on = served === key;
        return (
          <button key={key} type="button" aria-pressed={on}
                  data-testid={`cm-res-sort-${key}`}
                  className={`cm-phase-btn${on ? ' cm-phase-on' : ''}`}
                  onClick={() => onSort(key)}>
            {lab}
          </button>
        );
      })}
    </span>
  );
}

type Props = SortProps & {
  board: CmResiliencyBoard | null | undefined;
  onToggleFilter?: (key: string) => void;
  onToggleMode?: () => void;
};

export default function ResiliencyBoardNote({ board, sorts, sort, onSort, onToggleFilter, onToggleMode }: Props) {
  const b = obj(board);
  if (!b) return null;
  const header = text(b.header);
  if (!header) return null;
  const raw = b.state;
  const state = raw === 'warming' || raw === 'error' ? raw : 'ready';
  const todayLine = text(b.today_line);
  const marketLine = text(b.market_line);
  const eventsLine = text(b.events_line);
  const growthLine = text(b.growth_line);
  const gaps = obj(b.growth_gaps);
  const gapSummary = gaps ? text(gaps.summary) : null;
  const gapLines = gaps && Array.isArray(gaps.lines)
    ? (gaps.lines as unknown[]).filter((l): l is string => !!text(l)) : [];
  const showGaps = !!gapSummary && gapLines.length > 0;
  const note = text(b.note);
  const rules = obj(b.rules);
  const ruleLines = rules && Array.isArray(rules.lines)
    ? (rules.lines as unknown[]).filter((l): l is string => !!text(l)) : [];
  const filters = obj(b.filters);
  const items = filters && Array.isArray(filters.items)
    ? (filters.items as unknown[]).map(obj).filter((i): i is Record<string, unknown> =>
      !!i && typeof i.key === 'string' && KNOWN_BOXES.has(i.key) && !!text(i.label))
    : [];
  // Unticked boxes' notes live in the fold; ticked ones print under the boxes.
  const foldNotes = state === 'warming' ? []
    : items.filter((i) => i.on !== true && !!text(i.note)).map((i) => [String(i.key), String(i.note)] as const);
  const printedNotes = items.map((i) => text(i.note)).filter((n): n is string => !!n);
  const study = obj(b.study);
  // A study sentence already inside a printed box note is not printed twice.
  const studyLines = STUDY_KEYS.map((k) => [k, study ? text(obj(study[k])?.text) : null] as const)
    .filter((kv): kv is readonly [typeof STUDY_KEYS[number], string] =>
      !!kv[1] && !printedNotes.some((n) => n.includes(kv[1] as string)));
  const hasFold = !!eventsLine || ruleLines.length > 0 || foldNotes.length > 0 || studyLines.length > 0;
  return (
    <div data-testid="cm-res-board" data-state={state}>
      <ResiliencySortToggle sorts={sorts} sort={sort} onSort={onSort} />
      {onToggleFilter && state !== 'warming'
        ? <DualMomentumFilters filters={b.filters} onToggle={onToggleFilter} onToggleMode={onToggleMode}
                               knownKeys={RES_FILTER_KEYS} testIdPrefix="cm-res" />
        : null}
      <p className="cm-note" data-testid="cm-res-header"
         role={state === 'warming' ? 'status' : undefined}>{header}</p>
      {todayLine ? <p className="cm-note" data-testid="cm-res-today">{todayLine}</p> : null}
      {marketLine ? <p className="cm-note" data-testid="cm-res-market">{marketLine}</p> : null}
      {growthLine ? <p className="cm-note" data-testid="cm-res-growth">{growthLine}</p> : null}
      {showGaps ? (
        <details className="cm-note cm-dim" data-testid="cm-res-growth-gaps">
          <summary>{gapSummary}</summary>
          {gapLines.map((l, i) => (
            <p key={`g-${i}`} className="cm-note cm-dim" data-testid="cm-res-growth-gap">{l}</p>
          ))}
        </details>
      ) : null}
      {note && note !== header ? <p className="cm-note" data-testid="cm-res-note">{note}</p> : null}
      {hasFold ? (
        <details className="cm-note cm-dim" data-testid="cm-res-rules">
          <summary>The rules and the data days</summary>
          {eventsLine ? <p className="cm-note cm-dim" data-testid="cm-res-events">{eventsLine}</p> : null}
          {ruleLines.map((l, i) => (
            <p key={`r-${i}`} className="cm-note cm-dim" data-testid="cm-res-rule">{l}</p>
          ))}
          {foldNotes.map(([k, n]) => (
            <p key={`b-${k}`} className="cm-note cm-dim" data-testid={`cm-res-box-note-${k}`}>{n}</p>
          ))}
          {studyLines.map(([k, t]) => (
            <p key={`s-${k}`} className="cm-note cm-dim" data-testid={`cm-res-study-${k}`}>{t}</p>
          ))}
        </details>
      ) : null}
    </div>
  );
}

export { ResiliencyBoardNote };
