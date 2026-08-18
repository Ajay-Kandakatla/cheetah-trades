/* Label de-clumping.
 *
 * Ajay 2026-08-17: "Can you move these labels to the left or something they
 * are all clumsy and its hard to look at the bars". His screenshot had BUY
 * $66.08, NOW $64.40 and STOP HIT $63.44 inside $2.64 — three plates drawn on
 * top of one another and on top of the candles.
 *
 * The invariant every test here defends: a plate may MOVE, but it may never
 * imply a price it does not sit at.
 */
import { describe, expect, it } from 'vitest';
import { BOX_H, GAP, PAD, layoutPlanLabels, type LabelInput } from './labelLayout';

const L = (key: string, y: number | null, priority = 5): LabelInput =>
  ({ key, text: `${key} $1.00`, color: '#fff', y, priority });

/** The pane the complaint came from: 340px tall. */
const PANE = { height: 340 };

const byKey = (out: ReturnType<typeof layoutPlanLabels>) =>
  Object.fromEntries(out.map((p) => [p.key, p]));

const overlaps = (out: ReturnType<typeof layoutPlanLabels>) => {
  const s = [...out].sort((a, b) => a.labelY - b.labelY);
  for (let i = 1; i < s.length; i++) {
    if (s[i].labelY - s[i - 1].labelY < BOX_H + GAP - 0.001) return true;
  }
  return false;
};

describe('the reported case', () => {
  // Prices from the screenshot mapped onto the pane at ~10.1px/$.
  const REAL: LabelInput[] = [
    L('TARGET', 90, 2),
    L('BUY', 138, 1),
    L('NOW', 155, 4),
    L('STOP', 165, 0),
  ];

  it('separates every plate that was overlapping', () => {
    const out = layoutPlanLabels(REAL, PANE);
    expect(out).toHaveLength(4);
    expect(overlaps(out)).toBe(false);
  });

  it('leaves the label that was never crowded exactly where it was', () => {
    // TARGET sits 48px clear of the cluster. Moving it would be motion with no
    // purpose, and every pixel of displacement costs line-to-plate attachment.
    const out = byKey(layoutPlanLabels(REAL, PANE));
    expect(out.TARGET.labelY).toBe(90);
    expect(out.TARGET.displaced).toBe(false);
  });

  it('flags the moved plates so a leader line is drawn back to the level', () => {
    const out = byKey(layoutPlanLabels(REAL, PANE));
    expect(out.BUY.displaced).toBe(true);
    expect(out.STOP.displaced).toBe(true);
  });

  it('keeps every plate reporting the y of its OWN price', () => {
    // `y` is the line; `labelY` is the plate. Conflating them is how a chart
    // starts lying about where the stop is.
    const out = byKey(layoutPlanLabels(REAL, PANE));
    expect(out.BUY.y).toBe(138);
    expect(out.STOP.y).toBe(165);
    expect(out.NOW.y).toBe(155);
  });

  it('spreads the displacement across the cluster instead of dumping it on one', () => {
    const out = byKey(layoutPlanLabels(REAL, PANE));
    const moves = [out.BUY, out.NOW, out.STOP].map((p) => Math.abs(p.labelY - p.y));
    expect(Math.max(...moves)).toBeLessThan(BOX_H + GAP);
  });

  it('never reorders the levels — a lower price stays below a higher one', () => {
    // Reordering would put STOP above BUY on screen. That is not clutter, it
    // is a wrong chart.
    const out = layoutPlanLabels(REAL, PANE);
    const seq = [...out].sort((a, b) => a.y - b.y).map((p) => p.labelY);
    expect(seq).toEqual([...seq].sort((a, b) => a - b));
  });
});

describe('geometry', () => {
  it('does not move anything that already fits', () => {
    const out = layoutPlanLabels([L('A', 50), L('B', 150), L('C', 250)], PANE);
    expect(out.map((p) => p.labelY)).toEqual([50, 150, 250]);
    expect(out.every((p) => !p.displaced)).toBe(true);
  });

  it('centres a merged block on the mean of its levels', () => {
    // Two plates at the same y settle symmetrically either side of it.
    const out = layoutPlanLabels([L('A', 100), L('B', 100)], PANE);
    const ys = out.map((p) => p.labelY).sort((a, b) => a - b);
    expect((ys[0] + ys[1]) / 2).toBeCloseTo(100, 5);
    expect(ys[1] - ys[0]).toBeCloseTo(BOX_H + GAP, 5);
  });

  it('merges transitively — a pushed plate can collide with the next one', () => {
    // Three levels 4px apart: resolving A/B must not leave B on top of C.
    const out = layoutPlanLabels([L('A', 100), L('B', 104), L('C', 108)], PANE);
    expect(overlaps(out)).toBe(false);
  });

  it('shifts a stack off the top edge instead of letting it hang outside', () => {
    const out = layoutPlanLabels([L('A', 1), L('B', 3), L('C', 5)], PANE);
    expect(Math.min(...out.map((p) => p.labelY))).toBeGreaterThanOrEqual(PAD + BOX_H / 2);
    expect(overlaps(out)).toBe(false);
  });

  it('shifts a stack off the bottom edge too', () => {
    const out = layoutPlanLabels([L('A', 336), L('B', 338), L('C', 340)], PANE);
    expect(Math.max(...out.map((p) => p.labelY))).toBeLessThanOrEqual(340 - PAD - BOX_H / 2);
    expect(overlaps(out)).toBe(false);
  });
});

// --- negatives -------------------------------------------------------------

describe('negatives', () => {
  it('omits a price scrolled off the visible scale rather than pinning it', () => {
    // priceToCoordinate returns null there. Clamping to an edge would draw
    // "TARGET $70.88" at a place $70.88 is not.
    const out = layoutPlanLabels([L('A', null), L('B', 100)], PANE);
    expect(out.map((p) => p.key)).toEqual(['B']);
  });

  it('returns nothing for an empty or missing input', () => {
    expect(layoutPlanLabels([], PANE)).toEqual([]);
    expect(layoutPlanLabels(null, PANE)).toEqual([]);
    expect(layoutPlanLabels(undefined, PANE)).toEqual([]);
  });

  it('returns nothing when every price is off-screen', () => {
    expect(layoutPlanLabels([L('A', null), L('B', null)], PANE)).toEqual([]);
  });

  it('rejects a non-finite y instead of drawing NaN pixels', () => {
    const out = layoutPlanLabels(
      [L('A', NaN), L('B', Infinity), L('C', 100)], PANE);
    expect(out.map((p) => p.key)).toEqual(['C']);
  });

  it('draws nothing in a pane too short to hold one plate honestly', () => {
    expect(layoutPlanLabels([L('A', 5)], { height: 8 })).toEqual([]);
    expect(layoutPlanLabels([L('A', 5)], { height: 0 })).toEqual([]);
  });

  it('survives a non-finite pane height', () => {
    expect(layoutPlanLabels([L('A', 5)], { height: NaN })).toEqual([]);
  });

  it('DROPS by priority when the pane cannot hold them all', () => {
    // Squeezing would re-create the overlap this exists to remove. A missing
    // plate still has its price on the axis chip; an unreadable one does not.
    const tiny = { height: 44 };                      // room for ~2 plates
    const out = layoutPlanLabels(
      [L('STOP', 10, 0), L('BUY', 14, 1), L('TARGET', 18, 2), L('NOW', 22, 4)],
      tiny);
    expect(out.length).toBeLessThan(4);
    expect(out.map((p) => p.key)).toContain('STOP');
    expect(out.map((p) => p.key)).not.toContain('NOW');
    expect(overlaps(out)).toBe(false);
  });

  it('handles a single label with no one to collide with', () => {
    const out = layoutPlanLabels([L('A', 120)], PANE);
    expect(out).toHaveLength(1);
    expect(out[0].labelY).toBe(120);
    expect(out[0].displaced).toBe(false);
  });

  it('is deterministic for identical inputs', () => {
    // Two plates at the same y must not swap between renders and make the
    // chart flicker on every zoom.
    const input = [L('A', 100), L('B', 100), L('C', 100)];
    const a = layoutPlanLabels(input, PANE).map((p) => `${p.key}@${p.labelY}`);
    const b = layoutPlanLabels(input, PANE).map((p) => `${p.key}@${p.labelY}`);
    expect(a).toEqual(b);
  });
});
