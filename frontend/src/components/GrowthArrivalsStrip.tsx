/* ✨ Growth arrivals strip — the top of every Chart Maps tab (2026-10-12).
 *
 * Ajay 2026-10-12: "In the eplosive growth there are 7 new one can you gave me
 * special emphasis wiht a tag or something in the chart map pages top and then
 * a link to the repective tabs with new ticker".
 *
 * ONE folded line ("✨ N new on 🚀 Explosive Growth (last D days) · why"); the
 * chips and the served honesty note sit under the fold, and his open/closed
 * choice is remembered by StudyNote per id. Every chip links to the 🚀 board
 * focused on that name (`?tab=growth&focus=SYM`): a plain click routes in
 * place, ⌘-click opens the href in a new browser tab.
 *
 * Fed by the `/growth/tags` fetch every chip-bearing tab already makes (module
 * cached), so it costs no extra request there. Renders NOTHING when nothing
 * arrived — no box, no "0 new". Counts, order, flags and the note are SERVED;
 * nothing here re-derives them.
 */
import { useSearchParams } from 'react-router-dom';
import { StudyNote } from './StudyNote';
import { useGrowthArrivals } from '../hooks/useGrowthTags';
import { isPlainLeftClick, tabSearch } from '../lib/chartMaps';
import {
  GROWTH_TAB, arrivalGlyph, arrivalHref, arrivalTitle, arrivalsHeadline,
} from '../lib/growthArrivals';

export function GrowthArrivalsStrip() {
  const { arrivals, n, note, newDays } = useGrowthArrivals();
  const [params, setParams] = useSearchParams();
  if (!arrivals.length) return null;

  const go = (e: React.MouseEvent<HTMLAnchorElement>, search: string) => {
    if (!isPlainLeftClick(e)) return;   // the browser's click (new tab, window…)
    e.preventDefault();
    setParams(new URLSearchParams(search.slice(1)), { replace: true });
  };
  const allHref = `?${tabSearch(params, GROWTH_TAB)}`;

  return (
    <StudyNote id="growth-arrivals" className="cm-arrivals-strip" testId="cm-growth-arrivals"
               headline={arrivalsHeadline(n, newDays)}>
      <div className="cm-arrivals" data-testid="cm-growth-arrivals-chips">
        {arrivals.map((a) => {
          const href = arrivalHref(params, a.symbol);
          const glyph = arrivalGlyph(a);
          return (
            <a key={a.symbol} href={href}
               className={`cm-badge ${a.refused ? 'cm-badge-bad' : 'cm-badge-new'}`}
               data-testid={`cm-growth-arrival-${a.symbol}`}
               title={arrivalTitle(a)}
               onClick={(e) => go(e, href)}>
              {`${a.symbol}${glyph ? ' ' + glyph : ''}`}
            </a>
          );
        })}
        <a href={allHref} className="cm-badge cm-badge-muted"
           data-testid="cm-growth-arrivals-all" onClick={(e) => go(e, allHref)}>
          all 🚀 →
        </a>
      </div>
      {note ? <p className="cm-dim" data-testid="cm-growth-arrivals-note">{note}</p> : null}
    </StudyNote>
  );
}

export default GrowthArrivalsStrip;
