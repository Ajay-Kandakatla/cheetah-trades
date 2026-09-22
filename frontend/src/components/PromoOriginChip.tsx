/* 🎪 PromoOriginChip — "this name entered the scan universe through the
 * promo-circuit lane".
 *
 * Ajay 2026-09-21: "check if we can use them and ... add them to our list as
 * they come through". The lane adds them to the universe; this chip is the
 * label that travels with them, so a promo-origin row never reads like a
 * research-sourced one on a board he trades.
 *
 * ONE component, dropped beside every <GrowthChip/>, so every surface says the
 * same sentence in the same words. Renders NOTHING when the name did not come
 * through the lane (the common case), so it costs a dense board nothing.
 */
import { usePromoOriginTags, promoOriginChip } from '../hooks/usePromoOriginTags';

export function PromoOriginChip({ symbol, className = 'cm-badge' }:
                                { symbol: string; className?: string }) {
  const payload = usePromoOriginTags();
  const chip = promoOriginChip(payload, symbol);
  if (!chip) return null;
  return (
    <span className={`${className} ${className}-promo`} title={chip.title}>{chip.text}</span>
  );
}
