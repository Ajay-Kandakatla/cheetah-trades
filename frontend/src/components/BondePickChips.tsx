/* 📋 The pick line under a name on the 📈 Bonde tab.
 *
 * Six chips, then a closed fold with every computed criterion and its link.
 * Rule #5: six is the line's whole budget — the rest is one click away, and
 * the summary says "all N" (N = the SERVED criteria count) rather than a
 * score, because no count, ratio or rank derived from these legs is ever
 * rendered. A row with nine ticks is not a better name than a row with three;
 * it is a row this app happens to know more about.
 *
 * Every sentence shown here is SERVED. The component types no quote of his.
 */
import {
  PICK_CHIP_ORDER, computedCriteria, criterionOf, fmtValue, legChip,
  type BondePick, type BondePickLegend,
} from '../lib/bondePicks';

export type BondePickChipsProps = {
  pick?: BondePick | null;
  legend?: BondePickLegend | null;
  symbol: string;
};

export function BondePickChips({ pick, legend, symbol }: BondePickChipsProps) {
  // A row the backend served no pick block for renders NOTHING — an empty
  // chip line under the ticker reads as a name that failed everything.
  if (!pick || !pick.legs) return null;
  const legs = pick.legs;
  const rows = computedCriteria(legend);

  return (
    <div className="bd-pick" data-testid={`bd-pick-${symbol}`}>
      {PICK_CHIP_ORDER.map((key) => {
        const chip = legChip(key, legs[key], criterionOf(legend, key));
        if (!chip) return null;
        return (
          <span key={key} className={`bd-pick-chip ${chip.tone}`}
                data-testid={`bd-pick-${symbol}-${key}`} title={chip.title}>
            {chip.text}
          </span>
        );
      })}

      {rows.length > 0 && (
        <details className="bd-pick-more">
          {/* The SERVED criteria count, never a tick tally: "9 of 18" would
              be a rank this line has not earned and nothing has measured. */}
          <summary>all {rows.length}</summary>
          {rows.map((c) => {
            const leg = legs[c.key];
            const chip = legChip(c.key, leg, c);
            return (
              <div key={c.key} className="bd-pick-row" data-testid={`bd-pick-row-${symbol}-${c.key}`}>
                <span className={`bd-pick-glyph ${chip ? chip.tone : 'bd-dim'}`}>
                  {chip ? chip.glyph : '—'}
                </span>
                <span className="bd-pick-label" title={c.quote}>{c.label}</span>
                <span className="bd-pick-val">
                  {leg ? fmtValue(c.key, leg.value, leg) : '—'}
                </span>
                <span className="bd-pick-src">
                  {[leg?.as_of ? `as of ${leg.as_of}` : null, leg?.source || c.data]
                    .filter(Boolean).join(' · ')}
                </span>
                <a className="bd-pick-src" href={c.url} target="_blank" rel="noreferrer"
                   title={c.quote}>
                  {c.source === 'tape' && c.ts ? `[${c.ts}]` : c.date}
                </a>
              </div>
            );
          })}
        </details>
      )}
    </div>
  );
}

export default BondePickChips;
