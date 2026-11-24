# 🕯 1-minute candles: brighter and separated (2026-11-23)

Ajay, 2026-11-23 about 21:50 ET, with a screenshot of an AHMA 👀 Watch tile (the 1-min chart on top):

> "On the 1 mins chart make the bard lil more bright please."
> "Make them more separted"

Asked what should be brighter and more separated on the 1-min chart, he picked **"The candles"**.

## What changed

There is one new opt-in prop, `candleLook="1m"`, on `PatternChart`. Only the 👀 `Frame` in
`frontend/src/components/GajjalaWatchTile.tsx` passes it, and only when the frame's served `tf` is `'1m'`. That one
`Frame` draws every surface that shows a 1-minute frame:

- the 👀 Watch tile (the 1-min chart on top);
- the 🚩 / 🧪 card grid tile (`GgCardTile` → `Tile stack`, 15 / 5 / 1);
- the ⤢ Watch full-screen view (`GgwStretch`);
- the ⤢ card view (`GgCardView` → `GgwStretch kind="card"`).

The changes apply to 1-min candles only:

| | before (every bold Watch frame) | 1-min now |
|---|---|---|
| candle opacity | `EMA_BOLD_CANDLE_OPACITY` 0.85 | 1 (no dim) |
| extended-hours candle | 0.7 × 0.85 = 0.595 | `ONE_MIN_EXT_OPACITY` **0.85** |
| up colour | `--positive` rgb(38, 186, 104) | `ONE_MIN_CANDLE_UP` **rgb(46, 214, 120)** |
| down colour | `--negative` rgb(235, 72, 72) | `ONE_MIN_CANDLE_DN` **rgb(255, 88, 88)** |
| wick | 0.9 viewBox units (≈ 1.2 px in a fitted tile), anti-aliased | `ONE_MIN_WICK_PX` **1 device px** (`1 / devicePixelRatio` css px), non-scaling, `crispEdges` |
| body width | 0.8 of the slot (`EMA_BOLD_CANDLE_BODY`), anti-aliased | whole DEVICE px = max(1, floor(slotDevPx − `ONE_MIN_CANDLE_GAP_PX`)), `crispEdges`; a slot under 2 device px keeps the 0.8-of-slot anti-aliased body |
| gap between bodies | 0.2 of the slot (≈ 0.4 px) | ≥ **1 device px** (`ONE_MIN_CANDLE_GAP_PX`) when a slot is ≥ 2 device px |

All of these are **look values, MINE, not rules**. The constants and `oneMinBodyWidth` live in
`frontend/src/lib/chartMaps.ts`, next to `EMA_BOLD_*`. The 1-min frames always sit on the dark Watch panel
(`.ggw-dark`, rgb(13, 17, 23)) in both page themes, so the brighter green and red only have to read on dark.

### How the body width is worked out

`PatternChart` measures the svg's rendered width (`getBoundingClientRect`) only under `candleLook="1m"`. It re-reads
after every render and on a window resize, and has no `ResizeObserver` of its own, so the Frame's observer count is
unchanged. The box keeps the viewBox's aspect ratio, so css px per viewBox unit = rendered width / viewBox width.

**Refined 2026-11-23 (verifier): the body is sized in DEVICE px, not css px.** Ajay uses a Retina Mac
(`window.devicePixelRatio` = 2). In a 2-column 👀 Watch tile a slot is ≈ 1.0–1.2 css px = 2.0–2.4 device px: room for
a 1 device px body and a 1 device px gap, which a css-px rule (1 css px floor = 2 device px) could not see. So:

- `dpr` = `window.devicePixelRatio`, read at render (`oneMinDpr`): not a number, not finite, under 1 or absent
  (SSR / jsdom) → 1. Only the 1m look reads it.
- slot in device px = slot units × css px per unit × dpr.
- body = max(1, floor(slotDevPx − `ONE_MIN_CANDLE_GAP_PX`)) device px, converted back to viewBox units, `crispEdges`.
  A whole number of device px, so every crisp body comes out the same width.
- wick = 1 device px (`ONE_MIN_WICK_PX / dpr` css px, non-scaling, `crispEdges`).

**Fallback: a slot under 2 device px** (1 px body + the 1 px gap do not fit) draws no crisp 1 px bodies, which would
paint over their neighbours. `oneMinBodyWidth` returns `null` and the candle keeps the previous anti-aliased body
geometry, the house `EMA_BOLD_CANDLE_BODY` (0.8) of the slot, with the new brighter colours and opacities and the
1 device px crisp wick. The 2 device px line is 1 px of body plus `ONE_MIN_CANDLE_GAP_PX`, not a new constant.

Where that lands, for a 04:00–20:00 axis of 960 slots:

| surface | css px / slot | dpr 2 (his Mac) | dpr 1 |
|---|---|---|---|
| 2-column 👀 Watch tile | ≈ 1.0–1.2 | 2.0–2.4 device px → crisp 1 px body + ≥ 1 px gap | fallback (anti-aliased) |
| ~1,800 px ⤢ view | ≈ 1.8 | 3.6 → crisp 2 px body + 1.6 px gap | fallback |
| narrow grid tile | under 1 | under 2 → fallback | fallback |

**The served axis decides how wide a slot is, not the candle.** Widening the slots, for example by zooming the 1-min
frame to fewer hours, would be a separate change and is HIS CALL.

Until the first measurement (and in jsdom) the css ratio falls back to 1 px per unit.

## What did not change

- The hover readout and the hover dim (the other candles at 0.82).
- The markers (BUY / STOP / A+ / cross diamonds), the bold 9 / 21 EMAs and VWAP, the zones and bands, the extended-hours
  shade, the price axis and gutter labels.
- The **volume pane**, including its 0.7 extended-hours dim.
- Every chart that is not a 1-min frame: the 3 / 5 / 15-min Watch frames, the small 🚩 cards (5-min, 📺 or not), 🥇 Luk
  (5-min), daily cards and every other board. Each one renders HEAD's markup byte for byte.

## Tests

- `frontend/src/components/PatternChart.one_min_candles_2026_11_23.test.tsx` covers the pure body width in device px
  (whole device px, ≥ the gap, dpr 2 at 1.1 css px per slot → 1 px body + 1.2 px gap, exactly 2 device px → 1 + 1,
  under 2 device px → `null` / the fallback, junk ratios, junk dpr NaN / 0 / undefined / < 1 → 1), the rendered Retina
  tile (crisp bodies with a gap, 0.5 css px wick), the dpr 1 fallback at the same size (anti-aliased 0.8-of-slot body,
  1m colours and opacities kept), junk dpr rendering the dpr 1 markup, a non-1m chart identical at dpr 1 and 2, full opacity, the extended-hours value, the colours, `crispEdges`,
  the 1 px wick, bodies apart by ≥ the gap, and the hover dim. Its NEGATIVES: the rest of the svg is identical with and
  without the prop, no 1m look without the prop, the look on the 1m frame only on each surface (Watch tile, card grid,
  ⤢ Watch, ⤢ card), and `candleLook` has exactly one caller.
- `frontend/src/components/PatternChart.one_min_off_2026_11_23.snapshot.test.tsx` holds the snapshot, **recorded with
  HEAD's `PatternChart.tsx`**, for a daily card, a 5-min and a 15-min Watch frame, and a 📺 video card.
- `GajjalaBoard.card_watch_off.snapshot` stays green and was not edited.
