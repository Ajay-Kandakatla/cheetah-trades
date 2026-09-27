/* 🧲 GexChip — the served GEX chip(s) on a Chart Maps tile (Ajay 2026-09-27:
 * "Can you add gex exposure bullish or bearish signal to the stocks in our
 * chartmaps").
 *
 * PROP-FED, ALWAYS (the MomentumBurstChip rule): the nightly read rides on the
 * tile (chart_maps/board.attach_gex) and the live read arrives in the page's
 * ONE batched request (hooks/useGexLive), so a grid of tiles makes no extra
 * request here. Every word — the text, the tone and every line of the hover —
 * is built by backend/chart_maps/gex_read.compose; this file prints them in the
 * served order. Two chips when last close and now disagree, one otherwise.
 *
 * It lives in the card's PRICE row: it describes dealer positioning around the
 * current print. UNMEASURED — it gates, sizes and alerts nothing.
 */
import type { GexTileRead } from '../lib/gexRead';

export function GexChip({ read }: { read?: GexTileRead | null }) {
  const chips = read && Array.isArray(read.chips)
    ? read.chips.filter((chip) => chip && typeof chip.text === 'string' && chip.text)
    : [];
  if (!chips.length) return null;
  return (
    <>
      {chips.map((chip, i) => (
        <span key={`${chip.kind}-${i}`}
              className={`cm-badge cm-badge-${typeof chip.tone === 'string' && chip.tone ? chip.tone : 'muted'} cm-gex`}
              title={typeof chip.title === 'string' ? chip.title : undefined}>
          {chip.text}
        </span>
      ))}
    </>
  );
}
