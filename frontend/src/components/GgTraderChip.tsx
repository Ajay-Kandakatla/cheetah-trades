/* ---- 📌 trader tag (2026-10-27, BUILD_SPEC26 §3.4) — a clone of GgBrokerChip; every word SERVED (trader_names.text_for),
 * served to every viewer. A TAG: nothing hides, filters or mutes a row.
 * 🎪 2026-10-29 (BUILD_SPEC32 D4): the SAME component prints the served Promo-circuit tag (`promo_text`, promo_names)
 * right after the 📌 chip — one component, one mount per surface, both chips when a row carries both. Every word served;
 * the component types none.
 * 2026-10-29: chip module — moved verbatim out of GajjalaBoard.tsx into its own file (like GrowthChip / EnterableChip)
 * so /alerts imports the chip without pulling the whole board chunk (PatternChart, the hooks, gajjala.css). It imports
 * nothing from GajjalaBoard or PatternChart; its one rule lives in ggTraderChip.css. ---- */
import '../styles/ggTraderChip.css';

/** One served source tag — nothing unless the server sent a non-empty string. */
function servedChip(text: unknown, cls: string, testid: string | undefined) {
  if (!testid || typeof text !== 'string' || !text.trim()) return null;
  return <span className={`cm-badge cm-badge-muted ${cls}`} data-testid={testid}>{text}</span>;
}

/** 📌 the served trader tag beside a symbol, then 🎪 the served promo tag — each only when served. */
function GgTraderChip({ text, testid, promoText, promoTestid }: {
  text?: unknown; testid?: string; promoText?: unknown; promoTestid?: string;
}) {
  const t = servedChip(text, 'gg-trader', testid);
  const p = servedChip(promoText, 'gg-promo', promoTestid);
  if (!t && !p) return null;
  return <>{t}{p}</>;
}
export { GgTraderChip };
