/* ⚡ MomentumBurstChip — the served momentum-burst badge on a Chart Maps tile
 * (Ajay 2026-09-24: "Pin + badge, hide nothing").
 *
 * PROP-FED, ALWAYS (the ExplosiveChip / EnterableChip rule): the read rides on
 * the tile (chart_maps/board.attach_burst), so a 24-tile grid makes no extra
 * request. The badge text and every line of the hover are built on the
 * backend from the enforcing constants and the read's own numbers; this file
 * prints them and adds only the line that says which OTHER reads it is not.
 *
 * Renders NOTHING unless the server said ⚡ — a "no" or an "unknown" wears no
 * chip. UNMEASURED; it gates nothing.
 */
import { BURST_DISAMBIGUATION, isBurst, type BurstRead } from '../lib/momentumBurst';

export function MomentumBurstChip({ read }: { read?: BurstRead | null }) {
  if (!isBurst(read)) return null;
  return (
    <span className="cm-badge cm-badge-burst" title={`${read.title ?? ''}\n${BURST_DISAMBIGUATION}`}>
      {read.badge}
    </span>
  );
}
