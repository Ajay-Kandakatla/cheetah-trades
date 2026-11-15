/* 🔀 9/21 EMA cross blinker — the card side (2026-11-15, SPEC blinker §3.9, WP-E).
 *
 * Ajay 2026-11-15: "On All of the charts and also the tabs I need a new blinker to show me EMA uptrends 9 crossing over
 * 21 EMA please.." · "Yes and I need some sort of urgency or fast blink for the one are closer together than approaching
 * with sort also aligned with it" · "Or atleast closing in on other tabs for me".
 *
 * The server serves ONE block per card (`ema_blink`, backend chart_maps/ema_blink.block — the engine
 * gajjala/ema_cross.blink_read over the card's own drawn 9/21 curves). This module only READS it: the tier class the dot
 * pulses at and the trimmed served sentence. Every word is SERVED — the FE types none. Information only, UNMEASURED. */
import type { CmEmaBlink } from './chartMaps';

/** The served tiers, FASTEST first (== backend ema_cross.TIERS — ONE axis: urgency = blink speed = sort rank = tab-dot
 *  pick; contract-pinned by the main session). The CSS durations are monotone in this order. */
export const EMA_BLINK_TIERS = ['fresh', 'imminent', 'near', 'closing', 'up'] as const;
export type EmaBlinkTier = typeof EMA_BLINK_TIERS[number];

const isObj = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null && !Array.isArray(x);
const trimmed = (x: unknown): string => (typeof x === 'string' ? x.trim() : '');

/** The tier the dot pulses at, or null: only a block the server marked `blink === true` with a tier it knows. */
export function emaBlinkTier(b: CmEmaBlink | null | undefined): EmaBlinkTier | null {
  if (!isObj(b) || b.blink !== true) return null;
  const tier = b.tier;
  return typeof tier === 'string' && (EMA_BLINK_TIERS as ReadonlyArray<string>).includes(tier)
    ? (tier as EmaBlinkTier) : null;
}

/** The served sentence (trimmed) + the served short title, or null when the block does not blink or carries no text. */
export function emaBlinkLine(b: CmEmaBlink | null | undefined): { text: string; title: string } | null {
  if (!emaBlinkTier(b)) return null;
  const text = trimmed((b as CmEmaBlink).text);
  if (!text) return null;
  return { text, title: trimmed((b as CmEmaBlink).title) };
}
