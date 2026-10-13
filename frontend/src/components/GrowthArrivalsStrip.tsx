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
 * His 2026-10-12 "yes" answers (docs/chart_maps/growth_arrivals_strip_2026_10_12.md):
 *  - the page does not mount this on ?tab=growth (the board carries it there);
 *  - every chip href and `all 🚀 →` carry `show=all`, so an arrival the 🎯
 *    enterable cut would hide is drawn on landing (URL only — it rides on
 *    every later tab click in that browser tab until he toggles 🎯 back on);
 *  - the fold opens for a viewer who never folded it and re-opens when a newer
 *    batch arrives (StudyNote `freshKey` = newest served `first_seen`);
 *  - under each chip, small per-tab links from the served `also_on[]`: the
 *    tab's emoji, its full label + "in the served top N as of …" on hover.
 *    Glyph-only and under the fold on purpose: 11 chips × up to 22 tabs is
 *    dense — a per-row drawer is where more belongs (Rule #5).
 *
 * Fed by the `/growth/tags` fetch every chip-bearing tab already makes (module
 * cached), so it costs no extra request there. Renders NOTHING when nothing
 * arrived — no box, no "0 new". Counts, order, flags and the note are SERVED;
 * nothing here re-derives them.
 */
import { Fragment } from 'react';
import { useSearchParams } from 'react-router-dom';
import { StudyNote } from './StudyNote';
import { useGrowthArrivals } from '../hooks/useGrowthTags';
import { isPlainLeftClick, tabSearch } from '../lib/chartMaps';
import {
  GROWTH_TAB, arrivalGlyph, arrivalHref, arrivalTitle, arrivalsHeadline,
} from '../lib/growthArrivals';
import {
  alsoOnLinks, newestFirstSeen, tabGlyph, withShowAll,
} from '../lib/growthArrivalsFresh';

export function GrowthArrivalsStrip() {
  const { arrivals, n, note, newDays } = useGrowthArrivals();
  const [params, setParams] = useSearchParams();
  if (!arrivals.length) return null;

  const go = (e: React.MouseEvent<HTMLAnchorElement>, search: string) => {
    if (!isPlainLeftClick(e)) return;   // the browser's click (new tab, window…)
    e.preventDefault();
    setParams(new URLSearchParams(search.slice(1)), { replace: true });
  };
  const allHref = withShowAll(`?${tabSearch(params, GROWTH_TAB)}`);

  return (
    <StudyNote id="growth-arrivals" className="cm-arrivals-strip" testId="cm-growth-arrivals"
               headline={arrivalsHeadline(n, newDays)} freshKey={newestFirstSeen(arrivals)}>
      <div className="cm-arrivals" data-testid="cm-growth-arrivals-chips">
        {arrivals.map((a) => {
          const href = withShowAll(arrivalHref(params, a.symbol));
          const glyph = arrivalGlyph(a);
          const links = alsoOnLinks(a, params);
          const chip = (
            <a key={a.symbol} href={href}
               className={`cm-badge ${a.refused ? 'cm-badge-bad' : 'cm-badge-new'}`}
               data-testid={`cm-growth-arrival-${a.symbol}`}
               title={arrivalTitle(a)}
               onClick={(e) => go(e, href)}>
              {`${a.symbol}${glyph ? ' ' + glyph : ''}`}
            </a>
          );
          if (!links.length) return chip;
          return (
            <Fragment key={a.symbol}>
              {chip}
              <span className="cm-arrival-also" data-testid={`cm-growth-also-${a.symbol}`}>
                {links.map((l) => (
                  <a key={l.tab} href={l.href} title={l.title}
                     className="cm-badge cm-badge-muted"
                     data-testid={`cm-growth-also-${a.symbol}-${l.tab}`}
                     data-stale={l.stale ? 'true' : undefined}
                     onClick={(e) => go(e, l.href)}>
                    {tabGlyph(l.label)}
                  </a>
                ))}
              </span>
            </Fragment>
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
