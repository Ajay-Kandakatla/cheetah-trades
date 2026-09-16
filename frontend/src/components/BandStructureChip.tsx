/* 🪜 BandStructureChip — the ceiling above the print and the floor under it,
 * on every Chart Maps surface that carries the read (2026-09-16).
 *
 * Ajay's two asks, one minute apart: "prioritize stock by the thinnest over
 * head or Supply zone" and "the support bands are bigger and atleast another
 * one very close if its falls below the first support level. Something like
 * CRDO had at 149. It has another one right below it". The chip is where those
 * two facts show up per name — the ceiling's width and how far up it is, then
 * the first support band's width and the gap down to the second one.
 *
 * IT PRINTS THE SERVED SENTENCE. `read.stat` is built in
 * backend/supply_demand/band_structure.py::stat_line out of numbers that
 * module already served; this component formats nothing and derives nothing,
 * so no surface can drift from another (the GrowthChip / ExplosiveChip rule,
 * pinned by frontend/scripts/contracts.mjs).
 *
 * MUTED IS THE EXPECTED TONE. `MEASURED.status` is `no_signal`: the ordering
 * behind this chip is DESCRIPTIVE, not a prediction, so the chip stays grey
 * and the tooltip carries the study's own headline saying so. It wears the
 * lit tone only in the `separates` branch, and only with a served score.
 *
 * PROP-FED, ALWAYS. It never fetches: `chart_maps/board.attach_band_structure`
 * puts the whole read on every tile the board returns, whatever the sort.
 *
 * Renders NOTHING when there is no read, when the tab has no band read at all
 * (the 🎯 n/a precedent — the board-level note says that once), or when the
 * server sent no stat. Coverage stays honest: no chip beats a chip implying a
 * measurement nobody made.
 */
import {
  bandStructureChipText,
  type BandStructureRead,
  type BandStructureStudy,
} from '../lib/bandStructure';

export function BandStructureChip({ read, study, className = 'cm-badge' }: {
  read?: BandStructureRead | null;
  /** The served verdict (board.band_structure_study) — the tooltip carries it
   *  so the stat is never read without its status. */
  study?: BandStructureStudy | null;
  className?: string;
}) {
  const chip = bandStructureChipText(read, study);
  if (!chip) return null;
  const tone = chip.tone === 'muted'
    ? `${className}-band ${className}-band-muted`
    : `${className}-band`;
  return <span className={`${className} ${tone}`} title={chip.title}>{chip.text}</span>;
}
