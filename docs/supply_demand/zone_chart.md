# The zone chart — candles, volume, and a hover readout

Ajay 2026-08-16, on the Setup tab:

> *"is there any way we can use trading view charts? Or configure them with
> formula.. I wanna be able to hover on the pricing at for some points but too
> vague right now. Its not bad hoping the to improve it a lil more.. But may be
> static makes sense I know it would break the zones"*

and, a moment later:

> *"can you also add volume please"*

Code: `frontend/src/components/ZoneChart.tsx`,
`frontend/src/components/zoneBandsPrimitive.ts`, `frontend/src/lib/zoneChart.ts`,
`backend/supply_demand/demand_reentry.py` (`_series_for_chart`, `series_window`).
Tests: 38 (`zoneChart.test.ts`) + 18 (`zoneBandsPrimitive.test.tsx`) +
12 backend (`test_demand_reentry.py`).

---

## Why not TradingView

Three options, and only one of them was available.

| | verdict |
|---|---|
| **The TradingView embed already on the Chart tab** | Dead end. Anonymous widget, no drawing API, ~15-min delayed. It can never show our bands. |
| **TradingView Charting Library** | Can draw bands (`createMultipointShape`). The datafeed (`/tv/udf/*`) and the FE adapter are already built and dormant — see `docs/tradingview_charting_library.md`. Blocked on a license Ajay has applied for before and **was not granted**: they require a public website and his is private. |
| **lightweight-charts** | The engine TradingView open-sourced. Already a dependency (`^4.2.3`, used by `LiveCandlesChart.tsx`). No license, no approval. |

So: lightweight-charts.

## The trade-off he expected does not exist

> *"may be static makes sense I know it would break the zones"*

It does not break them. A band is a **price range**, and this primitive places it
by asking the series where those prices sit:

```ts
const yHi = series.priceToCoordinate(b.hi);
const yLo = series.priceToCoordinate(b.lo);
```

So the band is re-derived from the live price scale on every frame. Zoom, pan
and the band stays glued to $39.02–$40.11. The bands survive **because** the
chart is live, not despite it.

---

## What it draws

| | source |
|---|---|
| Candlesticks | `toCandles()` |
| Volume histogram, coloured by the bar's own direction | `toVolumeBars()` |
| Supply / demand bands, entry band outlined | `ZoneBandsPrimitive` |
| BUY band edges, STOP, TARGET, NOW as labelled price lines | `planLines()` |
| Hover readout: date, O/H/L/C, % change, volume | `hoverRow()` |

This is the **first `ISeriesPrimitive` in the codebase**. `PatternChart.tsx:8`
notes that v4 has no filled-box primitive and that a custom one is something
"the app has never written". This is that custom one, and it is deliberately
small — it converts prices to y-coordinates and fills rectangles. Every number
it draws comes from `lib/zoneChart.ts`, which is pure and tested, matching the
split `PatternChart` argues for in its own header.

### The readout sits above the canvas, not on it

A tooltip that follows the cursor covers the candles you are reading, and on a
band chart it lands on the band. The strip is height-reserved so hovering never
reflows the page.

### % change is against the previous CLOSE

Not against the bar's own open. Both are one subtraction and they disagree — on
the HASI bar of 2026-08-14 it is **+0.41%** against the prior close and −0.45%
against its own open. The first is what a quote screen means by "change".

---

## Two backend changes it needed

### 1. The series had no OHLC and no volume

`_series_for_chart` emitted `{date, close}` only. You cannot draw a candle or a
volume bar from a close. It now emits `{date, open, high, low, close, volume}`;
`close` is kept so nothing that already read the payload has to change.

* A bar missing o/h/l **degenerates to a doji at the close** rather than being
  dropped — a hole would shift every later bar and silently mis-place the bands
  against the price. A flat candle is visibly odd; a shifted chart is not.
* A bar with no close is dropped: that is not a bar.
* Missing volume is `null`, **never 0** — a zero column reads as "nobody
  traded", which a missing field does not support. The FE omits those bars.

### 2. The window cut off the evidence for the band

Zones are computed over **252** bars (`price_zones.LOOKBACK_BARS`); the chart
series was hardcoded to **180**. Any band whose oldest defining swing sat
between 181 and 252 bars back was drawn with its own touches off the left edge —
the band appeared to rest on nothing.

`series_window()` now sizes the window from the band's `oldest_touch_bars`,
using the same rule as `chart_maps.board._zone_window` so the Setup tab and the
chart-maps tiles frame the same band the same way:

```
min(252, max(130, oldest_touch_bars + 15))
```

130 is the non-Retina legibility floor; 252 is one trading year.
`test_the_window_matches_the_chart_maps_rule` compares the two functions
directly, so they cannot drift.

---

## Verified

Measured in the browser against the live HASI payload, 2026-08-16:

* 7 canvases at DPR 2 (2136×624 bitmap for a 1068×312 pane) — the chart is real.
* 470,107 opaque pixels: 256,651 green (demand bands, up candles, volume),
  130,192 red (supply bands, down candles).
* Hover produced `2026-04-21 · O $40.87 · H $41.19 · L $40.21 · C $40.54 ·
  −0.34% · Vol 495K`, and leaving the pane cleared it.
* No chart-related console errors.

Band **geometry** is pinned by unit test rather than by a browser poke: a fake
series with a known price→coordinate mapping asserts that a $30–$40 band lands
at y=240 with height 40, spans the full pane width, asks the series for both
edges, and scales correctly into retina bitmap space.

---

## Honest limits

* **A payload cached before today has closes only.** The chart falls back to a
  line series and says so in the legend, rather than rendering 130 identical
  dojis that look like a broken chart instead of an old one.
* **Bands are drawn, not interactive.** No dragging a level to re-plan. The
  levels come from the backend; editing them on the chart would mean two sources
  of truth for a stop.
* **No indicators.** No moving averages, no drawing tools. Those are what the
  Charting Library would have added, and it is the one that needs the license.
* **The primitive skips a band the price scale cannot place** (`priceToCoordinate`
  returns `null` off-range) rather than clamping it to an edge — a clamped band
  would draw a zone at a price it does not occupy.

## Where the honesty is enforced

| Decision | Guard |
|---|---|
| Bands follow the price scale | `asks the series for BOTH edges, so zoom and pan move the band with them` |
| An unplaceable band is skipped, not clamped | `SKIPS a band the price scale cannot place rather than pinning it to an edge` |
| A detached chart is never painted | `draws nothing after detach` |
| A missing o/h/l is a doji, not a hole | `test_a_bar_missing_ohl_degenerates_to_a_doji_rather_than_vanishing` |
| Missing volume is null, not zero | `test_missing_volume_is_null_not_zero`, `OMITS a bar with no volume` |
| Volume is never rounded to cents | `test_volume_is_not_rounded_to_cents` |
| The window reaches the band's oldest touch | `test_the_window_reaches_back_past_the_bands_oldest_touch` |
| Setup tab and chart-maps frame alike | `test_the_window_matches_the_chart_maps_rule` |
| % change is vs the previous close | `computes the change against the PREVIOUS CLOSE, not the open` |
| Broker levels keep their cents | `always keeps cents — these are numbers he types into a broker` |
| Old payloads degrade to a line | `recognises a pre-2026-08-16 cached payload as line-only` |
