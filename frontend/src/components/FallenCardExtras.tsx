/* FallenCardExtras — the lines under one 📉 Down 40%+ card (2026-10-02).
 *
 * Ajay 2026-10-02, verbatim: "But I also need you to capture informations
 * about sales like Bondes and other indicators based on Bondes formula
 * please." and "also add things like possible catalyst that made is drop like
 * that."
 *
 * A SIBLING of the card, never inside it: PatternChart is one <Link> around
 * the whole tile, and the pick chips' fold carries its own source links — an
 * <a> inside an <a> is invalid and a click on a cite would open the chart.
 *
 * Prints, verbatim and SERVED (chart_maps/fallen_tab.tile_block):
 *   • the 💥 line (`fallen.hit.text`) — the biggest down day since the high
 *     and the most specific item on file around it, labelled possible;
 *   • the Bonde line (`fallen.bonde.line`) and his pick legs through
 *     BondePickChips — the 📈 Bonde tab's own component, unchanged;
 *   • a closed fold of the top drop days: each day's served line, its group
 *     line, every on-file item (a link only when the item carries a url) or
 *     the served "nothing on file" sentence.
 * The sales line is NOT repeated here: it is already a served stat on the
 * card face (Rule #5 — one place). The legend is NOT here either: it renders
 * once for the tab, above the grid. Nothing is composed, counted or computed.
 *
 * Renders NOTHING for a tile without a `fallen` block.
 */
import type { CmTile } from '../lib/chartMaps';
import type { BondePickLegend } from '../lib/bondePicks';
import { BondePickChips } from './BondePickChips';

const text = (v: unknown): string | null =>
  typeof v === 'string' && v.trim().length > 0 ? v : null;
const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : null;
const list = (v: unknown): Record<string, unknown>[] =>
  (Array.isArray(v) ? v : []).map(obj).filter((x): x is Record<string, unknown> => !!x);

type Props = { tile: CmTile; legend?: BondePickLegend | null };

export default function FallenCardExtras({ tile, legend }: Props) {
  const f = obj(tile?.fallen);
  if (!f) return null;
  const sym = tile.symbol;
  const hit = text(obj(f.hit)?.text);
  const bonde = text(obj(f.bonde)?.line);
  const drops = list(f.drops);
  const head = text(f.drops_head);
  return (
    <div className="cm-fallen-extras" data-testid={`cm-fallen-extras-${sym}`}>
      {hit ? <p className="cm-fallen-hit" data-testid={`cm-fallen-hit-${sym}`}>{hit}</p> : null}
      {bonde ? <p className="cm-note cm-dim" data-testid={`cm-fallen-bonde-${sym}`}>{bonde}</p> : null}
      <BondePickChips pick={tile.pick} legend={legend} symbol={sym} />
      {drops.length > 0 && head ? (
        <details className="cm-fallen-drops" data-testid={`cm-fallen-drops-${sym}`}>
          <summary>{head}</summary>
          {drops.map((d, i) => {
            const line = text(d.line);
            const group = text(obj(d.group)?.line);
            const items = list(d.items).filter((it) => !!text(it.text));
            const empty = text(d.empty);
            return (
              <div key={`${String(d.date)}-${i}`} data-testid={`cm-fallen-drop-${sym}-${i}`}>
                {line ? <p className="cm-note" data-testid={`cm-fallen-drop-line-${sym}-${i}`}>{line}</p> : null}
                {group ? <p className="cm-note cm-dim" data-testid={`cm-fallen-drop-group-${sym}-${i}`}>{group}</p> : null}
                {items.map((it, j) => {
                  const t = String(it.text);
                  const url = text(it.url);
                  return (
                    <p key={`${i}-${j}`} className="cm-note cm-dim" data-testid={`cm-fallen-item-${sym}-${i}-${j}`}>
                      {url ? <a href={url} target="_blank" rel="noreferrer">{t}</a> : t}
                    </p>
                  );
                })}
                {items.length === 0 && empty
                  ? <p className="cm-note cm-dim" data-testid={`cm-fallen-drop-empty-${sym}-${i}`}>{empty}</p>
                  : null}
              </div>
            );
          })}
        </details>
      ) : null}
    </div>
  );
}

export { FallenCardExtras };
