/* 🎯 EnterableChip — the per-name ENTERABLE read, on every Chart Maps surface.
 *
 * Ajay 2026-09-15: "I only wanna see the stocks that are enterable."
 *
 * IT RENDERS A SERVED VERDICT AND NOTHING ELSE. READY / WATCH / BLOCKED, the
 * reason word beside it and every sentence in the tooltip are built on the
 * backend from the enforcing constants — the two standing push gates, the
 * measured floor read and the two measured drags. No gate, no threshold and no
 * number is evaluated in this file; a copy of the rule in TSX is a second
 * engine that drifts the first time a constant moves.
 *
 * PROP-FED, ALWAYS (the ExplosiveChip rule): the page already asks the
 * bounce-room endpoint once for its whole list, or the read rides on the tile.
 * A per-chip fetch would fan a 24-tile grid into 24 requests.
 *
 * Renders NOTHING when there is no read. A name with no band, a pending row or
 * a legacy doc wears no chip and is never hidden by the filter — an unknown is
 * an unknown, not a rejection.
 */
import { enterableChipText, type EnterableRead } from '../lib/enterable';

export function EnterableChip({ read, className = 'cm-badge' }: {
  read?: EnterableRead | null;
  className?: string;
}) {
  const chip = enterableChipText(read);
  if (!chip) return null;
  return (
    <span className={`${className} ${className}-enterable-${chip.tone}`} title={chip.title}>
      {chip.text}
    </span>
  );
}
