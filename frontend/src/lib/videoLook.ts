/* 📺 The replay-video look on the 🚩 Gajjala cards (spec ggvideo 2026-11-17, WP-B pc-video-look).
 *
 * Ajay 2026-11-16: "Also the graphs in the videos are so clear like I can easily identify the trend
 * Why aren't our regular ones like that" · 2026-11-17 on the spec's defaults: "Yes to all defaults".
 *
 * What PatternChart `look="video"` reads from here: which SVG layers survive (candles, the 9 / 21 EMA,
 * BUY · STOP · now, the A+ tag, volume + its 50-bar average), the video's chart height, and the replay's
 * dark panel as inline custom properties. Display only — nothing sorts, filters, gates or pushes on it.
 * A clearer chart is display, not evidence: UNMEASURED. */
import type { CSSProperties } from 'react';
import type { CmTile } from './chartMaps';
import { GGW_PANEL } from './gajjalaWatch';

/** The video's lines: trigger + stop (tab._tile_lines tones 'buy' / 'stop'); 'now' = his 11-16 "cannot tell where … is now"
 *  (boldNowLines adds one under the bold look; cardLive may serve one). */
export const VIDEO_LOOK_LINE_TONES = ['buy', 'stop', 'now'] as const;
/** The video's two curves, drawn bold over the candles (21 then 9). */
export const VIDEO_LOOK_CURVE_TONES = ['ema9', 'ema21'] as const;
/** The A+ / 🧪 held tag = the video's ring mark. ➖ 'ema_cross_up' / 'ema_cross_dn' are dropped (his call #4). */
export const VIDEO_LOOK_MARKER_KINDS = ['buy'] as const;
/** viewBox height giving the price pane the video's h/w (306/831 = 0.368, replay_video.py:271) at a typical 85-unit gutter:
 *  volumePaneLayout(283, PAD_Y 10, true) → volTop 211, priceH 217, drawable 197; 197 / (620 − 85) = 0.368. MINE (layout) — spec
 *  default #7, his "Yes to all defaults". 🎾 .gg-wide cards keep 190 (a full-row × 283 card is ~800 px tall on a desktop). */
export const VIDEO_LOOK_H = 283;
/** The replay's dark panel as inline custom properties — ONE source, GGW_PANEL (= .ggw-dark's set, --ink included: the light
 *  theme's --ink is #1A1A1A). A module constant, so a memo'd PatternChart gets the same reference every render. */
export const VIDEO_PANEL_STYLE: CSSProperties = {
  background: GGW_PANEL.bg,
  ['--surface' as string]: GGW_PANEL.bg, ['--bg-raised' as string]: GGW_PANEL.bg, ['--bg-sunken' as string]: GGW_PANEL.bg,
  ['--cm-card' as string]: GGW_PANEL.bg, ['--rule' as string]: GGW_PANEL.grid, ['--ink' as string]: GGW_PANEL.text,
  ['--text-muted' as string]: GGW_PANEL.dim, ['--positive' as string]: GGW_PANEL.up, ['--negative' as string]: GGW_PANEL.down,
} as CSSProperties;

const LINE_TONES: ReadonlySet<string> = new Set(VIDEO_LOOK_LINE_TONES);
const CURVE_TONES: ReadonlySet<string> = new Set(VIDEO_LOOK_CURVE_TONES);
const MARKER_KINDS: ReadonlySet<string> = new Set(VIDEO_LOOK_MARKER_KINDS);

/** The SVG layers of a tile under the video look — a NEW object, the input never mutated: lines ∈ LINE_TONES, curves ∈ CURVE_TONES,
 *  markers ∈ MARKER_KINDS, bands [], ellipses [], amd_raids absent. Every other key (bars, vol_avg, stats, href, gajjala, …) is
 *  the SAME reference, so the ladder / head / chips read the tile unchanged. */
export function videoLayers<T extends CmTile>(tile: T): T {
  const out = { ...tile } as T & { amd_raids?: unknown };
  out.lines = (Array.isArray(tile.lines) ? tile.lines : []).filter((l) => !!l && LINE_TONES.has(String(l.tone)));
  out.curves = (Array.isArray(tile.curves) ? tile.curves : []).filter((c) => !!c && CURVE_TONES.has(String(c.tone)));
  out.markers = (Array.isArray(tile.markers) ? tile.markers : []).filter((m) => !!m && MARKER_KINDS.has(String(m.kind)));
  out.bands = [];
  out.ellipses = [];
  delete out.amd_raids;
  return out;
}
