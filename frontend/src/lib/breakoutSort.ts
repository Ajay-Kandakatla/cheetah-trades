/* Breakout-board default sort value — AI-ecosystem sector winners first.
 *
 * Ajay 2026-06-25: "anytime you show me a breakout list, give priority to
 * sector winners and AI sectors (chips, energy/nuclear, water/cooling, …)".
 * Composite (higher = sorts first, dir 'desc'): AI-sector priority dominates,
 * then buyable, then conviction. Non-AI names (ai_sector_rank null → 99) fall
 * below every AI-sector name. Magnitudes stay exact under 2^53.
 */
export function aiSectorSortValue(r: {
  ai_sector_rank?: number | null;
  is_buyable?: boolean | null;
  conviction?: number | null;
}): number {
  const rank = r.ai_sector_rank ?? 99;          // 0 = highest priority; 99 = not AI
  return (99 - rank) * 1e12 + (r.is_buyable ? 1e9 : 0) + (r.conviction ?? 0);
}
