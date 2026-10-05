/* Drop10BoardNote — the lines above the 🔻 Down 10%+ today grid (2026-10-05).
 *
 * Ajay 2026-10-03, verbatim: "I would like to know about stocks that falled
 * intraday more than 10% new tab please."
 *
 * The board is read, counted and ordered on the server
 * (chart_maps/drop10_tab.py). This component prints its SERVED sentences
 * verbatim — the header, the order line, the count line, the note, the 💥
 * sources lines and the held-out names — plus the served sort buttons. It
 * composes no sentence, reads no count and does no maths: a number typed here
 * could disagree with the board it describes.
 *
 * THE SORT BUTTONS are the served `sorts`, one each, labels served; the
 * PRESSED button is the SERVED `sort`, never the URL. A click hands the key to
 * the page's one sort setter.
 *
 * Renders NOTHING for an absent or malformed block. While the memo warms the
 * header is the served warming line with role="status", and neither the
 * sources nor the held-out fold renders.
 */
import type { CmSort } from '../lib/chartMaps';
import type { CmDrop10Board } from '../lib/drop10';

const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;
const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : null;

type Props = {
  board: CmDrop10Board | null | undefined;
  sorts?: CmSort[] | null;
  sort?: string | null;
  onSort: (key: string) => void;
};

export default function Drop10BoardNote({ board, sorts, sort, onSort }: Props) {
  const b = obj(board);
  if (!b) return null;
  const header = text(b.header);
  if (!header) return null;
  const raw = b.state;
  const state = raw === 'warming' || raw === 'error' ? raw : 'ready';
  const ready = state === 'ready';
  const offered = (Array.isArray(sorts) ? sorts : [])
    .map(obj)
    .filter((s): s is Record<string, unknown> => !!s && !!text(s.key) && !!text(s.label));
  const served = typeof sort === 'string' ? sort : (typeof b.sort === 'string' ? b.sort : null);
  const order = text(b.order_line);
  const counts = text(b.count_line);
  const note = text(b.note);
  const cat = ready ? obj(b.catalysts) : null;
  const catLines = cat
    ? (['note', 'line'] as const).map((k) => [k, text(cat[k])] as const)
      .filter((kv): kv is readonly ['note' | 'line', string] => !!kv[1])
    : [];
  const sus = ready ? obj(b.suspects) : null;
  const susN = sus && typeof sus.n === 'number' && Number.isFinite(sus.n) ? sus.n : 0;
  const susHead = sus ? text(sus.head) : null;
  const susLines = sus && Array.isArray(sus.lines)
    ? (sus.lines as unknown[]).filter((l): l is string => !!text(l)) : [];
  return (
    <div data-testid="cm-drop10-board" data-state={state}
         data-mode={typeof b.mode === 'string' ? b.mode : undefined}>
      {offered.length > 0 ? (
        <span className="cm-phase-sub" role="group" aria-label="Order the board"
              data-testid="cm-drop10-sorts">
          {offered.map((o) => {
            const key = String(o.key);
            const on = served === key;
            return (
              <button key={key} type="button" aria-pressed={on}
                      data-testid={`cm-drop10-sort-${key}`}
                      className={`cm-phase-btn${on ? ' cm-phase-on' : ''}`}
                      onClick={() => onSort(key)}>
                {String(o.label)}
              </button>
            );
          })}
        </span>
      ) : null}
      <p className="cm-note" data-testid="cm-drop10-header"
         role={state === 'warming' ? 'status' : undefined}>{header}</p>
      {order ? <p className="cm-note" data-testid="cm-drop10-order">{order}</p> : null}
      {counts ? <p className="cm-note cm-dim" data-testid="cm-drop10-counts">{counts}</p> : null}
      {note && note !== header ? <p className="cm-note cm-dim" data-testid="cm-drop10-note">{note}</p> : null}
      {catLines.length > 0 ? (
        <details className="cm-note cm-dim" data-testid="cm-drop10-sources">
          <summary>{catLines[0][1]}</summary>
          {catLines.slice(1).map(([k, l]) => (
            <p key={k} className="cm-note cm-dim" data-testid={`cm-drop10-sources-${k}`}>{l}</p>
          ))}
        </details>
      ) : null}
      {susN > 0 && susHead ? (
        <details className="cm-note cm-dim" data-testid="cm-drop10-suspects">
          <summary>{susHead}</summary>
          {susLines.map((l, i) => (
            <p key={`s-${i}`} className="cm-note cm-dim" data-testid="cm-drop10-suspect">{l}</p>
          ))}
        </details>
      ) : null}
    </div>
  );
}

export { Drop10BoardNote };
