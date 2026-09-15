/* 🧨 ExplosiveChip — the per-name explosive read, on every Chart Maps surface.
 *
 * Ajay 2026-09-14: a read of how likely a name in / arriving at a demand band
 * is to make >= 5% toward the first supply band, "evaluated before it ranks".
 *
 * THE CHIP LEADS WITH WHAT WAS MEASURED, and the null branch is the expected
 * one. When the study says `no_signal` (or has not run yet: `pending`) there
 * IS no explosiveness score, so the chip goes MUTED and says only what the
 * tape says — the room to the first supply band and whether the band floor
 * held. It never wears the `good` tone in that branch: a fallback ordering
 * dressed as a signal is the exact mistake the Keltner and AMD tabs made.
 *
 * PROP-FED, ALWAYS. It never fetches: the page already asks the bounce-room
 * endpoint once for its whole list (or, on tile boards, the read rides on the
 * tile). A per-chip fetch would fan a 24-tile grid into 24 requests, and the
 * rev-1 batcher that would have hidden that fan-out is deliberately absent.
 *
 * Renders NOTHING when there is no read (GrowthChip pattern) — coverage is
 * honest: names with no band, pending rows and legacy docs show no chip and
 * sort LAST, never a chip that implies a measurement nobody made.
 */
import { explosiveChipText, type ExplosiveRead, type ExplosiveStudy } from '../lib/bounceRoom';

export function ExplosiveChip({ read, study, className = 'cm-badge' }: {
  read?: ExplosiveRead | null;
  /** The served verdict (payload.explosive_study / board.explosive_study) —
   *  the tooltip carries it so the number is never read without its status. */
  study?: ExplosiveStudy | null;
  className?: string;
}) {
  const chip = explosiveChipText(read, study);
  if (!chip) return null;
  const tone = chip.tone === 'muted'
    ? `${className}-explosive ${className}-explosive-muted`
    : `${className}-explosive`;
  return <span className={`${className} ${tone}`} title={chip.title}>{chip.text}</span>;
}
