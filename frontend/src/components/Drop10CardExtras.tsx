/* Drop10CardExtras — the lines under one 🔻 Down 10%+ today card (2026-10-05).
 *
 * Ajay 2026-10-03, verbatim: "I would like to know about stocks that falled
 * intraday more than 10% new tab please."
 *
 * A SIBLING of the card, never inside it: PatternChart is one <Link> around
 * the whole tile, and an on-file item's source is a link of its own — an <a>
 * inside an <a> is invalid and a click on a source would open the chart.
 *
 * Prints, verbatim and SERVED (chart_maps/drop10_tab.tile_block):
 *   • the 💥 line (`drop10.hit.text`) — the day's move, its larger leg, the
 *     volume against normal and the most specific item on file, labelled
 *     possible;
 *   • a closed fold: the group line (sector ETF / theme median / RSP that
 *     session) and every on-file item (a link only when the item carries a
 *     url), or the served "nothing on file" sentence.
 * The low, the state, the legs and the volume are already served stats and
 * the pill on the card face (Rule #5 — one place). Nothing is composed,
 * counted or computed.
 *
 * Renders NOTHING for a tile without a `drop10` block.
 */
import type { CmTile } from '../lib/chartMaps';

const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;
const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : null;
const list = (v: unknown): Record<string, unknown>[] =>
  (Array.isArray(v) ? v : []).map(obj).filter((x): x is Record<string, unknown> => !!x);

type Props = { tile: CmTile };

export default function Drop10CardExtras({ tile }: Props) {
  const d = obj(tile?.drop10);
  if (!d) return null;
  const sym = tile.symbol;
  const hit = text(obj(d.hit)?.text);
  const group = text(obj(d.group)?.line);
  const items = list(d.items).filter((it) => !!text(it.text));
  const empty = text(d.empty);
  const fold = group || items.length > 0 || empty;
  return (
    <div className="cm-fallen-extras" data-testid={`cm-drop10-extras-${sym}`}>
      {hit ? <p className="cm-fallen-hit" data-testid={`cm-drop10-hit-${sym}`}>{hit}</p> : null}
      {fold ? (
        <details className="cm-fallen-drops" data-testid={`cm-drop10-fold-${sym}`}>
          <summary>What is on file, and what its group did</summary>
          {group ? <p className="cm-note cm-dim" data-testid={`cm-drop10-group-${sym}`}>{group}</p> : null}
          {items.map((it, j) => {
            const t = String(it.text);
            const url = text(it.url);
            return (
              <p key={j} className="cm-note cm-dim" data-testid={`cm-drop10-item-${sym}-${j}`}>
                {url ? <a href={url} target="_blank" rel="noreferrer">{t}</a> : t}
              </p>
            );
          })}
          {items.length === 0 && empty
            ? <p className="cm-note cm-dim" data-testid={`cm-drop10-empty-${sym}`}>{empty}</p>
            : null}
        </details>
      ) : null}
    </div>
  );
}

export { Drop10CardExtras };
