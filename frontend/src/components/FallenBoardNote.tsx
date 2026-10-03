/* FallenBoardNote — the lines above the 📉 Down 40%+ grid (2026-10-02).
 *
 * Ajay 2026-10-02, verbatim: "Can you build me a tab in chart maps about
 * stocks that dropped more than 40% lowers from like app loving company as an
 * example whcih si 60% low. But I also need you to capture informations about
 * sales like Bondes and other indicators based on Bondes formula please." then
 * "Scan the universe and bring me these stocks" and "also add things like
 * possible catalyst that made is drop like that."
 *
 * The board is read, counted and ordered on the server
 * (chart_maps/fallen_tab.py). This component prints its SERVED sentences
 * verbatim — the header, the order line, the count line, the note, the 💥
 * sources lines and the held-out names — plus the served sort buttons, the
 * served depth buttons and Bonde's criteria legend ONCE for the tab (Rule #5:
 * the legend lives here, never per card). It composes no sentence, reads no
 * count and does no maths: a number typed here could disagree with the board
 * it describes.
 *
 * THE SORT BUTTONS are the served `sorts`, one each, labels served; the
 * PRESSED button is the SERVED `sort`, never the URL. A click hands the key to
 * the page's one sort setter. THE DEPTH BUTTONS are the served `depths`;
 * pressed = the served `on`; a click hands the key to the page's depth setter.
 *
 * Renders NOTHING for an absent or malformed block. While the memo warms the
 * header is the served warming line with role="status", and neither the
 * legend nor the sources nor the held-out fold renders.
 */
import type { CmSort } from '../lib/chartMaps';
import { servedDepths, type CmFallenBoard } from '../lib/fallen';
import type { BondePickLegend } from '../lib/bondePicks';
import { BondeCriteriaLegend } from './BondeCriteriaLegend';

const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;
const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : null;

type Props = {
  board: CmFallenBoard | null | undefined;
  sorts?: CmSort[] | null;
  sort?: string | null;
  onSort: (key: string) => void;
  onDepth: (key: string) => void;
};

export default function FallenBoardNote({ board, sorts, sort, onSort, onDepth }: Props) {
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
  const depths = servedDepths(b);
  const order = text(b.order_line);
  const counts = text(b.count_line);
  const note = text(b.note);
  const legend = ready ? (obj(b.pick_legend) as BondePickLegend | null) : null;
  const cat = ready ? obj(b.catalysts) : null;
  const catLines = cat
    ? (['note', 'line', 'nothing_line'] as const).map((k) => [k, text(cat[k])] as const)
      .filter((kv): kv is readonly ['note' | 'line' | 'nothing_line', string] => !!kv[1])
    : [];
  const sus = ready ? obj(b.suspects) : null;
  const susN = sus && typeof sus.n === 'number' && Number.isFinite(sus.n) ? sus.n : 0;
  const susHead = sus ? text(sus.head) : null;
  const susLines = sus && Array.isArray(sus.lines)
    ? (sus.lines as unknown[]).filter((l): l is string => !!text(l)) : [];
  return (
    <div data-testid="cm-fallen-board" data-state={state}>
      {offered.length > 0 ? (
        <span className="cm-phase-sub" role="group" aria-label="Order the board"
              data-testid="cm-fallen-sorts">
          {offered.map((o) => {
            const key = String(o.key);
            const on = served === key;
            return (
              <button key={key} type="button" aria-pressed={on}
                      data-testid={`cm-fallen-sort-${key}`}
                      className={`cm-phase-btn${on ? ' cm-phase-on' : ''}`}
                      onClick={() => onSort(key)}>
                {String(o.label)}
              </button>
            );
          })}
        </span>
      ) : null}
      {depths.length > 0 ? (
        <span className="cm-phase-sub" role="group" aria-label="Depth under the 52-week high"
              data-testid="cm-fallen-depths">
          {depths.map((d) => (
            <button key={d.key} type="button" aria-pressed={d.on}
                    data-testid={`cm-fallen-depth-${d.key}`}
                    className={`cm-phase-btn${d.on ? ' cm-phase-on' : ''}`}
                    onClick={() => onDepth(d.key)}>
              {d.label}
            </button>
          ))}
        </span>
      ) : null}
      <p className="cm-note" data-testid="cm-fallen-header"
         role={state === 'warming' ? 'status' : undefined}>{header}</p>
      {order ? <p className="cm-note" data-testid="cm-fallen-order">{order}</p> : null}
      {counts ? <p className="cm-note cm-dim" data-testid="cm-fallen-counts">{counts}</p> : null}
      {note && note !== header ? <p className="cm-note" data-testid="cm-fallen-note">{note}</p> : null}
      {legend ? <BondeCriteriaLegend legend={legend} /> : null}
      {catLines.length > 0 ? (
        <div className="cm-note cm-dim" data-testid="cm-fallen-sources">
          {catLines.map(([k, l]) => (
            <p key={k} className="cm-note cm-dim" data-testid={`cm-fallen-sources-${k}`}>{l}</p>
          ))}
        </div>
      ) : null}
      {susN > 0 && susHead ? (
        <details className="cm-note cm-dim" data-testid="cm-fallen-suspects">
          <summary>{susHead}</summary>
          {susLines.map((l, i) => (
            <p key={`s-${i}`} className="cm-note cm-dim" data-testid="cm-fallen-suspect">{l}</p>
          ))}
        </details>
      ) : null}
    </div>
  );
}

export { FallenBoardNote };
