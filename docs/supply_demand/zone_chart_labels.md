# Zone chart: the plan labels

Ajay 2026-08-17, with a screenshot of MOS:

> *"Can you move these labels to the left or something they are all clumsy and
> its hard to look at the bars"*

Code: `frontend/src/lib/labelLayout.ts` (the arithmetic),
`frontend/src/components/planLabelsPrimitive.ts` (the drawing),
`frontend/src/components/ZoneChart.tsx` (wiring + the gutter),
`frontend/src/lib/zoneChart.ts` (`planLines`, `planGutterPx`, `gutterBars`).
Tests: `labelLayout.test.ts` (20), `zoneChart.test.ts` (+16),
`ZoneChart.labels.test.tsx` (12).

---

## 1. "Move them left" is the one thing that would have made it worse

The labels were already right-aligned, and not by our choice. In
lightweight-charts 4.2.3, `PanePriceAxisView._internal_renderer()` takes the
title's alignment from `pane._internal_priceScalePosition(priceScale)` — the
side the series' price scale is on. Ours is the right, so the plates were pinned
there. That is also where TradingView and thinkorswim put bracket tags.

On a `fitContent()` chart the **middle is denser than the right edge**, so
moving the plates left would have laid them across more bars, not fewer.

What was actually wrong were two separate things:

| | problem | fix |
|---|---|---|
| 1 | **No empty space to sit in.** `fitContent()` puts the newest candle flush against the axis, so every plate landed on the tape. | A reserved right gutter. |
| 2 | **The plates overlapped each other.** BUY $66.08, NOW $64.40 and STOP HIT $63.44 span $2.64 — ~27px on a 340px pane, where three plates need ~60px. | De-clumping. |

And two things nobody asked about, found while verifying in a browser:

| | problem | fix |
|---|---|---|
| 3 | **Two chips both read 64.40.** The candlestick series draws its own last-price rule *and* its own axis chip (`priceLineVisible` and `lastValueVisible`, both defaulting to true), duplicating our NOW line exactly. | Both off. Ours is the one that says which it is. |
| 4 | **BUY and TARGET were the same green** (`DEMAND` #22c55e). A chip is a colour and a number and nothing else, so on the axis — the surface that survives when a plate is displaced — entry and objective were indistinguishable. | `TARGET_C` #38bdf8. |

## 2. The gutter

`planGutterPx` sizes a blank right margin from the widest title, capped at a
third of the pane so a long label like `BUY $1,485.00–$1,514.00` cannot eat the
chart to pay for itself. `gutterBars` converts that to the only unit the time
scale accepts, solving `b / (n + b) = g / w` for `b`.

`rightOffset` is then set and `fitContent()` is **kept**, because
`_internal_fitContent` sets the visible range to `(first, last + rightOffset)` —
verified in the library source. The two compose. (An earlier design pass claimed
`fitContent` ignores `rightOffset` and proposed replacing it with
`setVisibleLogicalRange`; that was checked and is wrong, and the replacement
would also have thrown against the existing test mock.)

Recomputed in the `ResizeObserver`: the gutter is a fraction of the width, and a
margin sized for 900px leaves a plate hanging off a 400px pane.

## 3. De-clumping, and the rule it must not break

> **A displaced label must never imply a price it does not sit at.**

`layoutPlanLabels` is the standard one-dimensional cluster merge (the shape of
Wilkinson's label placement): walk labels in y order, each its own cluster
centred on its true y; whenever the last two would overlap, merge and re-centre
the block on the **mean** of its members' true positions. Merging is transitive,
so one pass settles — no iteration limit to tune, no configuration that
oscillates. Re-centring on the mean keeps the block over the levels it describes
and spreads the displacement instead of dumping it all on one member.

Three things enforce the rule, and all three are needed:

* every plate carries its own price in its text (`STOP HIT $63.44`), so the
  number is stated rather than read off a pixel row;
* a moved plate reports `displaced: true`, and the renderer draws a leader elbow
  plus a dot **on** the line;
* the axis chip never moves, so the true price is always readable at its true y.

Edges: a price off the visible scale has no coordinate and is **omitted**, never
pinned to an edge. A pane too short for the whole stack **drops** by priority
(stop → buy → target → now) rather than squeezing, because squeezing
re-introduces the overlap the function exists to remove, and NOW is redundant
with both the newest candle and its chip.

## 4. Not merged with the function that already existed

`zonePlan.layoutLabels` stays scoped to the hand-rolled SVG tiles
(`chartMaps.ts:291`). It resolves collisions by priority — plan labels keep
their exact y and push others away — which by construction lets two *plan*
labels overlap each other. That is exactly the reported bug, since BUY, NOW and
STOP HIT are all plan labels. Both files carry a comment pointing at the other.

## 5. Verified visually, not just by test

jsdom has no canvas, so the tests cover the arithmetic and the wiring. The
drawing was checked by bundling the real modules into a standalone page and
rendering three panes side by side — before, after at 340px, and a cramped 170px
pane to force displacement and prove the leader elbows draw. That is where
defects 3 and 4 were found; neither is visible from a unit test.

## Where the honesty is enforced

| Decision | Guard |
|---|---|
| Overlapping plates get separated | `separates every plate that was overlapping` |
| An uncrowded plate does not move | `leaves the label that was never crowded exactly where it was` |
| A moved plate gets a leader | `flags the moved plates so a leader line is drawn back to the level` |
| Plate y and line y stay distinct | `keeps every plate reporting the y of its OWN price` |
| Levels never reorder | `never reorders the levels — a lower price stays below a higher one` |
| Off-screen prices are omitted, not pinned | `omits a price scrolled off the visible scale rather than pinning it` |
| A short pane drops instead of squeezing | `DROPS by priority when the pane cannot hold them all` |
| Deterministic across renders | `is deterministic for identical inputs` |
| Every level has its own colour | `gives TARGET a colour of its own, not the BUY band green` |
| Nothing is drawn twice | `silences the series own last-price rule AND its axis chip` |
| The library's plate stays off, the chip stays on | `creates every price line with an EMPTY title`, `keeps the axis chip` |
| The gutter is reserved and re-applied | `reserves right-hand bar slots…`, `still calls fitContent` |
