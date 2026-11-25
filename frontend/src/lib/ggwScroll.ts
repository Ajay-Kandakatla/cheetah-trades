/* 👀 Gajjala's Watch — one scrolling grid (2026-11-25, spec ggwcols §3.1, WP scroll-lib).
 * Ajay: "When I say 2 per screen I mean 2 columns do not remove other, I need other to be avtive while I scroll.
 * Can you fix that instead of removing the other?"
 * The per-screen pick is the grid shape only; every watched tile sits in ONE grid the window scrolls. This file holds
 * the pure geometry (which tile is at the view, where ← → go) and the thin DOM adapters that feed it. It composes no
 * word and holds no rule: the two numbers below are layout tolerances (MINE), not gates. */

/** MINE (layout, not a rule): px tolerance when a tile edge is compared with the inset line. */
export const GGW_SCROLL_EPS = 1;
/** MINE: the live render gate's IntersectionObserver rootMargin (half a window above and below). null = gate OFF. */
export const GGW_NEAR_MARGIN: string | null = '50% 0px';
/** == the id GajjalaWatchTile gives a board tile (`ggw-${row.symbol}`). */
export const GGW_TILE_ID = 'ggw-';

export type GgwTileBox = { top: number; bottom: number; width: number; height: number; hidden: boolean };
type Measured = GgwTileBox & { i: number };

/** A board tile's symbol from its id; anything without the prefix (or with nothing after it) → null. */
export function ggwTileSym(id: string | null | undefined): string | null {
  if (typeof id !== 'string' || !id.startsWith(GGW_TILE_ID)) return null;
  const s = id.slice(GGW_TILE_ID.length);
  return s ? s : null;
}

/** The boxes that have a layout (not hidden, some size), each keeping its `boxes` index. */
function measured(boxes: ReadonlyArray<GgwTileBox>): Measured[] {
  const out: Measured[] = [];
  boxes.forEach((b, i) => {
    if (b && !b.hidden && (b.width > 0 || b.height > 0)) out.push({ ...b, i });
  });
  return out;
}

/** The first tile in the view once the grid has been scrolled into; null while the head is still in view. */
export function ggwViewAnchor(boxes: ReadonlyArray<GgwTileBox>, inset: number): number | null {
  const m = measured(boxes);
  if (!m.length) return null;
  if (m[0].top >= inset - GGW_SCROLL_EPS) return null;      // the grid's start is at / below the strip line
  const hit = m.find((b) => b.bottom > inset + GGW_SCROLL_EPS);
  return hit ? hit.i : null;
}

/** ← → : a `boxes` index to bring under the inset · 'top' = the board top · null = nothing to do. */
export function ggwStepTarget(boxes: ReadonlyArray<GgwTileBox>, v: { vh: number; inset: number }, per: number,
                              dir: -1 | 1): number | 'top' | null {
  if (!(Number.isInteger(per) && per >= 1)) return null;
  if (!(typeof v.vh === 'number' && Number.isFinite(v.vh) && v.vh > 0)) return null;
  const m = measured(boxes);
  const s: Measured[] = [];
  for (let k = 0; k < m.length; k += per) s.push(m[k]);     // the first tile of each screen row group
  if (s.length < 2) return null;
  const inset = v.inset;
  let c = -1;
  s.forEach((b, k) => { if (b.top <= inset + GGW_SCROLL_EPS) c = k; });
  if (c === -1 && m[Math.min(per, m.length) - 1].bottom <= v.vh + GGW_SCROLL_EPS) c = 0;
  if (dir === 1) return c + 1 < s.length ? s[c + 1].i : null;
  if (c === -1) return 'top';
  if (s[c].top < inset - GGW_SCROLL_EPS) return s[c].i;       // inside group c: back to its start
  return c >= 1 ? s[c - 1].i : 'top';
}

/** The grid's own tiles: direct `.ggw-tile` children only (never a section header, never the ⤢ portal copy). */
export function ggwGridTiles(grid: Element | null): HTMLElement[] {
  if (!grid) return [];
  return Array.from(grid.children).filter((el): el is HTMLElement => el.classList.contains('ggw-tile'));
}

/** Each tile's rect + `hidden`, and the inset = the tiles' own `scroll-margin-top` (the SAME CSS value the scroll
 *  target uses — never a typed pixel number). */
export function ggwReadTiles(grid: Element | null): { els: HTMLElement[]; boxes: GgwTileBox[]; inset: number } {
  const els = ggwGridTiles(grid);
  const boxes = els.map((el) => {
    const r = el.getBoundingClientRect();
    return { top: r.top, bottom: r.bottom, width: r.width, height: r.height, hidden: el.hidden };
  });
  let inset = 0;
  if (els.length && typeof window !== 'undefined' && typeof window.getComputedStyle === 'function') {
    inset = parseFloat(window.getComputedStyle(els[0]).scrollMarginTop) || 0;
  }
  return { els, boxes, inset };
}

/** The tile he is looking at and its top now, or null (no window / grid / anchor / symbol). */
export function ggwAnchorNow(grid: Element | null): { sym: string; top: number } | null {
  if (typeof window === 'undefined' || !grid) return null;
  const { els, boxes, inset } = ggwReadTiles(grid);
  const i = ggwViewAnchor(boxes, inset);
  if (i == null) return null;
  const sym = ggwTileSym(els[i].id);
  return sym ? { sym, top: boxes[i].top } : null;
}

/** ← → read at key time: the tile element to bring under the strip, 'top', or null. */
export function ggwStepNow(grid: Element | null, per: number, dir: -1 | 1): HTMLElement | 'top' | null {
  if (typeof window === 'undefined' || !grid) return null;
  const { els, boxes, inset } = ggwReadTiles(grid);
  const to = ggwStepTarget(boxes, { vh: window.innerHeight, inset }, per, dir);
  if (to == null || to === 'top') return to;
  return els[to] ?? null;
}
