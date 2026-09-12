/* 🚀 GrowthChip — "this name is also on the Explosive Growth board".
 *
 * Ajay 2026-09-11: "I am hoping this new list will be considerd in all chart
 * maps. Like in Deep demand scan." then "ALL TABS IN CHART MAPS".
 *
 * ONE component, dropped into every Chart Maps renderer, so the tile boards,
 * the Hottest table, Session, Signals, Catalysts, Overnight, Patterns, Hot
 * Pullback and Support all say the same thing in the same words. It is a
 * POINTER to the growth board, never a second copy of the screen — the boards
 * cannot drift into disagreeing about what qualifies.
 *
 * Renders NOTHING when the name is not on the board (the common case), so it
 * costs a dense surface nothing. ⛔ tone when the trading engine will refuse
 * the name: good sales must never make an unbuyable row look clean.
 */
import { useGrowthTags, growthChip } from '../hooks/useGrowthTags';

export function GrowthChip({ symbol, className = 'cm-badge' }:
                           { symbol: string; className?: string }) {
  const tags = useGrowthTags();
  const chip = growthChip(tags, symbol);
  if (!chip) return null;
  return (
    <span className={`${className} ${className}-${chip.refused ? 'bad' : 'growth'}`}
          title={chip.title}>{chip.text}</span>
  );
}
