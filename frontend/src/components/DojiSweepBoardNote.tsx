/* DojiSweepBoardNote — the lines above the 🕯️ Doji Sweep grid (2026-10-16).
 *
 * Ajay 2026-10-16, verbatim: "create me a new tab for Doji candle after a
 * sweep. For any stocks after a down trend. May be from all chart maps
 * especially on the 60% 70% down stocks" — and on the knobs: "Within 5% either
 * side counts as a test", "Yes, any read; chips narrow".
 *
 * The board is read, counted and ordered on the server
 * (backend/chart_maps/doji_sweep_tab.py). This component prints its SERVED
 * sentences verbatim, composes none, does no maths — the header, the study
 * line (directly under the header: he asked for the accuracy), the order
 * line, the count line, the note, the three downtrend reads and the held-out
 * names — plus the served sort buttons, the served body switch and the served
 * chips. A number typed here could disagree with the board it describes.
 *
 * THE SORT BUTTONS are the served `sorts`; the PRESSED one is the SERVED
 * `sort`, never the URL. THE BODY SWITCH is the served `body.steps`; pressed =
 * the served `on`. THE CHIPS are the 🏎️ boxes (DualMomentumFilters) with this
 * tab's served keys; no mode switch is passed, so none renders — every ticked
 * chip must pass (K3 "chips narrow").
 *
 * Renders NOTHING for an absent or malformed block, or one without a string
 * `header`. While the memo warms (or the build failed) only the served header
 * (role="status" while warming) and the served study line print — no
 * controls, chips, counts or folds.
 *
 * The fold label "The three downtrend reads" is the only text typed here — a
 * fold label, no number; the lines inside it are served.
 */
import type { CmSort } from '../lib/chartMaps';
import { DJ_FILTER_KEYS } from '../lib/dojiSweep';
import type { CmDojiSweepBoard } from '../lib/dojiSweep';
import { DualMomentumFilters } from './DualMomentumBoardNote';

const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;
const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : null;

type Props = {
  board: CmDojiSweepBoard | null | undefined;
  sorts?: CmSort[] | null;
  sort?: string | null;
  onSort: (key: string) => void;
  onToggleFilter: (key: string) => void;
  onBody: (key: string) => void;
};

export default function DojiSweepBoardNote({ board, sorts, sort, onSort, onToggleFilter, onBody }: Props) {
  const b = obj(board);
  if (!b) return null;
  const header = text(b.header);
  if (!header) return null;
  const raw = b.state;
  const state = raw === 'warming' || raw === 'error' ? raw : 'ready';
  const ready = state === 'ready';
  const warming = state === 'warming';
  const study = text(obj(b.study)?.text);
  const offered = ready
    ? (Array.isArray(sorts) ? sorts : [])
      .map(obj)
      .filter((s): s is Record<string, unknown> => !!s && !!text(s.key) && !!text(s.label))
    : [];
  const served = typeof sort === 'string' ? sort : (typeof b.sort === 'string' ? b.sort : null);
  const body = ready ? obj(b.body) : null;
  const steps = body && Array.isArray(body.steps)
    ? (body.steps as unknown[]).map(obj)
      .filter((s): s is Record<string, unknown> => !!s && !!text(s.key) && !!text(s.label))
    : [];
  const order = ready ? text(b.order_line) : null;
  const counts = ready ? text(b.count_line) : null;
  const note = ready ? text(b.note) : null;
  const legend = ready && Array.isArray(b.reads_legend)
    ? (b.reads_legend as unknown[]).filter((l): l is string => !!text(l)) : [];
  const sus = ready ? obj(b.suspects) : null;
  const susN = sus && typeof sus.n === 'number' && Number.isFinite(sus.n) ? sus.n : 0;
  const susHead = sus ? text(sus.head) : null;
  const susLines = sus && Array.isArray(sus.lines)
    ? (sus.lines as unknown[]).filter((l): l is string => !!text(l)) : [];
  return (
    <div data-testid="cm-dj-board" data-state={state}>
      {offered.length > 0 ? (
        <span className="cm-phase-sub" role="group" aria-label="Order the board"
              data-testid="cm-dj-sorts">
          {offered.map((o) => {
            const key = String(o.key);
            const on = served === key;
            return (
              <button key={key} type="button" aria-pressed={on}
                      data-testid={`cm-dj-sort-${key}`}
                      className={`cm-phase-btn${on ? ' cm-phase-on' : ''}`}
                      onClick={() => onSort(key)}>
                {String(o.label)}
              </button>
            );
          })}
        </span>
      ) : null}
      {steps.length > 0 ? (
        <span className="cm-phase-sub" role="group" aria-label="Doji body" data-testid="cm-dj-body">
          {steps.map((s) => {
            const key = String(s.key);
            const on = s.on === true;
            return (
              <button key={key} type="button" aria-pressed={on}
                      data-testid={`cm-dj-body-${key}`}
                      title={text(s.title) ?? undefined}
                      className={`cm-phase-btn${on ? ' cm-phase-on' : ''}`}
                      onClick={() => onBody(key)}>
                {String(s.label)}
              </button>
            );
          })}
        </span>
      ) : null}
      {ready ? (
        <DualMomentumFilters filters={b.filters} onToggle={onToggleFilter}
                             knownKeys={DJ_FILTER_KEYS} testIdPrefix="cm-dj" />
      ) : null}
      <p className="cm-note" data-testid="cm-dj-header"
         role={warming ? 'status' : undefined}>{header}</p>
      {study ? <p className="cm-note" data-testid="cm-dj-study">{study}</p> : null}
      {order ? <p className="cm-note" data-testid="cm-dj-order">{order}</p> : null}
      {counts ? <p className="cm-note cm-dim" data-testid="cm-dj-counts">{counts}</p> : null}
      {note && note !== header ? <p className="cm-note cm-dim" data-testid="cm-dj-note">{note}</p> : null}
      {legend.length > 0 ? (
        <details className="cm-note cm-dim" data-testid="cm-dj-reads">
          <summary>The three downtrend reads</summary>
          {legend.map((l, i) => (
            <p key={`r-${i}`} className="cm-note cm-dim" data-testid="cm-dj-read">{l}</p>
          ))}
        </details>
      ) : null}
      {susN > 0 && susHead ? (
        <details className="cm-note cm-dim" data-testid="cm-dj-suspects">
          <summary>{susHead}</summary>
          {susLines.map((l, i) => (
            <p key={`s-${i}`} className="cm-note cm-dim" data-testid="cm-dj-suspect">{l}</p>
          ))}
        </details>
      ) : null}
    </div>
  );
}

export { DojiSweepBoardNote };
