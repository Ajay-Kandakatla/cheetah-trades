/* De-clumping for the zone chart's price-line labels.
 *
 * Ajay 2026-08-17, on a chart where four plan levels sat inside $7:
 *   "Can you move these labels to the left or something they are all clumsy
 *    and its hard to look at the bars"
 *
 * WHY MOVING THEM LEFT IS NOT THE FIX
 * -----------------------------------
 * The labels are already right-aligned, and not by our choice: in
 * lightweight-charts 4.2.3 `PanePriceAxisView._internal_renderer()` sets the
 * title's alignment from `pane._internal_priceScalePosition(priceScale)`. Our
 * scale is on the right, so the plates are pinned there — which is also where
 * TradingView and thinkorswim put bracket tags. Moving them to the left would
 * lay them over the MIDDLE of a fitted chart, which is denser than its right
 * edge, and would make the bars harder to read, not easier.
 *
 * Two things actually went wrong, and they are different problems:
 *
 *   1. There was no empty space for the plates to sit in. `fitContent()` puts
 *      the newest candle flush against the axis, so every plate landed on the
 *      tape. Fixed in ZoneChart.tsx with a reserved right gutter.
 *   2. Three of the four plates OVERLAPPED each other. On his screenshot BUY
 *      $66.08, NOW $64.40 and STOP HIT $63.44 span $2.64 — about 27px on a
 *      340px pane — while three plates need ~60px. That is this file.
 *
 * THE RULE THAT CONSTRAINS THE ALGORITHM
 * --------------------------------------
 * A displaced label must never imply a price it does not sit at. Two things
 * enforce that, and both are required:
 *   * every plate carries its own price in its text (`STOP HIT $63.44`), so
 *     the number is stated rather than inferred from position;
 *   * a displaced plate reports `displaced: true` so the renderer draws a
 *     leader line back to the true y.
 * Neither alone is enough — text without a leader loses which line it belongs
 * to, a leader without text invites reading the price off the plate's y.
 *
 * Pure and canvas-free on purpose: this is the part with the arithmetic, and
 * jsdom has no canvas to test it through.
 *
 * NOT `zonePlan.layoutLabels`, which is a different function for a different
 * surface and stays that way. That one serves the hand-rolled SVG tiles
 * (chartMaps.ts:291) and resolves collisions by PRIORITY: plan labels keep
 * their exact y and push others away, and a low-priority band label that finds
 * no free slot is dropped. That rule leaves plan labels free to overlap EACH
 * OTHER — which is precisely the bug in Ajay's screenshot, where BUY, NOW and
 * STOP HIT are all plan labels. This function instead guarantees no overlap
 * among the labels it returns, at the cost of moving them.
 */

/** One label, positioned at the y its price maps to. `y` is null when the
 *  price is outside the visible range — `priceToCoordinate` returns null and
 *  clamping it to an edge would draw the level at a price it does not occupy. */
export type LabelInput = {
  key: string;
  text: string;
  color: string;
  y: number | null;
  /** Lower survives first when the pane cannot hold every plate. */
  priority: number;
};

export type PlacedLabel = {
  key: string;
  text: string;
  color: string;
  /** Where the LINE is. */
  y: number;
  /** Where the PLATE is drawn (its vertical centre). */
  labelY: number;
  /** labelY differs enough from y to need a leader line back to the level. */
  displaced: boolean;
};

export type LayoutOpts = {
  /** Pane height in CSS pixels. */
  height: number;
  /** Plate height including padding. */
  boxHeight?: number;
  /** Minimum blank pixels between two plates. */
  gap?: number;
  /** Keep plates this far from the top and bottom edges. */
  pad?: number;
};

export const BOX_H = 16;
export const GAP = 3;
export const PAD = 2;

/** Below this a plate is considered still ON its line and needs no leader. */
const LEADER_EPSILON = 1.5;

const finite = (v: unknown): v is number =>
  typeof v === 'number' && Number.isFinite(v);

type Cluster = { top: number; items: (LabelInput & { y: number })[] };

/**
 * Place labels so none overlap, moving each the least distance that achieves it.
 *
 * The algorithm is the standard one-dimensional cluster merge (the same shape
 * as Wilkinson's label placement, and as pool-adjacent-violators): walk the
 * labels in y order; each starts as its own cluster centred on its true y;
 * whenever the last two clusters would overlap, merge them and re-centre the
 * merged block on the MEAN of its members' true positions. Merging is
 * transitive, so one pass settles — there is no iteration limit to tune and no
 * configuration that makes it oscillate.
 *
 * Re-centring on the mean is what keeps the result honest: the block of plates
 * stays over the cluster of levels it describes, and every member moves a
 * little rather than one member absorbing the whole displacement.
 *
 * Then the whole stack is shifted (never squeezed) to fit inside the pane. If
 * even the shifted stack cannot fit, the lowest-priority labels are DROPPED —
 * squeezing would re-introduce the overlap this function exists to remove, and
 * an unreadable plate is worth less than a missing one, because the axis chip
 * still carries the price.
 */
export function layoutPlanLabels(items: LabelInput[] | null | undefined,
                             opts: LayoutOpts): PlacedLabel[] {
  const h = opts.boxHeight ?? BOX_H;
  const gap = opts.gap ?? GAP;
  const pad = opts.pad ?? PAD;
  const paneH = finite(opts.height) ? opts.height : 0;

  // A price off the visible scale has no y. It is omitted rather than pinned
  // to an edge: a plate at the top of the pane reading "TARGET $70.88" when
  // $70.88 is off-screen states a level at a place it is not.
  let live = (items || []).filter(
    (it): it is LabelInput & { y: number } => !!it && finite(it.y));
  if (!live.length || paneH <= 0) return [];

  const step = h + gap;                         // pitch between plate centres
  const top = pad + h / 2;
  const bottom = paneH - pad - h / 2;

  // Too short to hold even one plate: nothing can be drawn honestly.
  if (bottom < top) return [];

  // How many fit at all. Dropping is by priority, not by position — losing the
  // STOP because it happens to sit lowest would be the wrong label to lose.
  const capacity = Math.max(1, Math.floor((bottom - top) / step) + 1);
  if (live.length > capacity) {
    const keep = new Set(
      [...live].sort((a, b) => a.priority - b.priority)
        .slice(0, capacity).map((it) => it.key));
    live = live.filter((it) => keep.has(it.key));
  }

  const sorted = [...live].sort((a, b) => a.y - b.y || a.key.localeCompare(b.key));

  // ── cluster merge ─────────────────────────────────────────────────────────
  const clusters: Cluster[] = [];
  for (const it of sorted) {
    clusters.push({ top: it.y - h / 2, items: [it] });
    // Transitive: merging two may push the block into the one before it.
    while (clusters.length > 1) {
      const cur = clusters[clusters.length - 1];
      const prev = clusters[clusters.length - 2];
      const prevBottom = prev.top + prev.items.length * step - gap;
      if (cur.top >= prevBottom + gap) break;
      const merged = [...prev.items, ...cur.items];
      const meanY = merged.reduce((s, m) => s + m.y, 0) / merged.length;
      clusters.splice(clusters.length - 2, 2, {
        items: merged,
        top: meanY - (merged.length * step - gap) / 2,
      });
    }
  }

  // ── shift the whole stack into the pane, preserving every gap ─────────────
  const first = clusters[0];
  const last = clusters[clusters.length - 1];
  const stackTop = first.top + h / 2;
  const stackBottom = last.top + (last.items.length * step - gap) - h / 2;
  let shift = 0;
  if (stackTop < top) shift = top - stackTop;
  else if (stackBottom > bottom) shift = bottom - stackBottom;

  const out: PlacedLabel[] = [];
  for (const c of clusters) {
    c.items.forEach((it, i) => {
      const labelY = c.top + h / 2 + i * step + shift;
      out.push({
        key: it.key,
        text: it.text,
        color: it.color,
        y: it.y,
        labelY,
        displaced: Math.abs(labelY - it.y) > LEADER_EPSILON,
      });
    });
  }
  return out;
}
