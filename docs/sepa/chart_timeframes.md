# How far back each chart reaches — and why it is not one number

**Code:** `backend/chart_maps/board.py` (`_zone_window`, `ZONE_BARS_MIN/MAX/PAD`,
`BARS_DEFAULT`) · `backend/supply_demand/price_zones.py` (`oldest_touch_bars`) ·
**Tests:** `backend/tests/test_theme_priority.py`, `frontend/src/lib/chartMaps.test.ts`

> Ajay 2026-08-16: *"please research what is the best timeframe to be used for
> the charts? I wonder if its has to use like 1 year or 6 months for the zone and
> update appropriately"*

## The bug he was pointing at

Zones are computed over **252 bars** (`price_zones.LOOKBACK_BARS`) but the study
board charted **130**. A band could therefore be drawn with **every touch that
defines it off-screen** — a price box with no visible reason to exist. He studies
these charts to learn the pattern, so that is worse than drawing nothing.

## The answer is per-tab, and for zones per-tile

Three reasons a single constant cannot work, each measured:

1. **It is already per-tab.** `board()` overrides with
   `winner_tiles(days=min(days, 90))`. Calling `board(tab='winners', days=130 /
   180 / 252 / 400)` returns byte-identical tiles. Raising `BARS_DEFAULT` would
   move two tabs and silently no-op the third.

2. **The same widening helps zones and hurts VCP.** `PatternChart` draws every
   band as a full-width rect — a price box with no time extent. For a demand zone
   that is right: a level is valid across all history. For a VCP the same rect is
   the base high/low, so widening to 252 makes a band that is meaningful over ~61
   bars visually claim a full year. It would manufacture the exact
   "band with no visible reason" failure on the one tab that does not have it.

3. **The tabs ask different questions.** VCP: *how tight is this base* — needs
   candle resolution. Zones: *why is this a level* — needs history. Winners:
   *what did it look like, and did it work* — needs a fixed pre-window and a
   variable post-window.

## What each tab does now

| Tab | Window | Why |
|---|---|---|
| **Strong VCP** | 130 (unchanged) | Widening actively harms it — see reason 2 |
| **Back in Demand** | **per tile**, `min(252, max(130, oldest_touch_bars + 15))` | Reach back to the oldest defining swing, clamped to what stays legible |
| **Past Winners** | 90, with `pad_after = bars_to_outcome + 12` | The dynamic pad is what puts the outcome bar on every tile |

`price_zones` now emits **`oldest_touch_bars`** — the age of the oldest swing in
the cluster — purely additively. Nothing gates on it; `LOOKBACK_BARS` and
`_strength` are untouched.

Per-tile sizing gives a median window of ~156 bars. Only 5 of 24 tiles need the
full 252.

## The legibility ceiling

**255 bars on a Retina display, 127 on a non-Retina one.** The old 130 default
was already 3 bars past the DPR-1 limit.

The arithmetic, from the component's own source: `W=620, PAD_R=62` are viewBox
units, not pixels — `.cm-svg { width: 100% }`. In the narrowest three-column
layout the viewBox maps to 393.74 CSS px, so one unit is 0.635 px and the plot is
354.35 px. `barWidth = 558/n` units → `354.35/n` CSS px, and the body has a 1.4-unit
floor that engages past n=255. Requiring at least one device pixel between candle
bodies gives n ≤ 255 at DPR 2 and n ≤ 127 at DPR 1.

That is precisely why the answer cannot be one server-side constant: **130 and 255
are the two hardware limits**, and the right window depends on the screen as much
as the tab. Hence the Window control (Default / 6m / 9m / 1y) rather than a
silently-chosen number.

## Cost

| | 130 flat | per-tile | 252 flat |
|---|---|---|---|
| zones board, warm | 69ms | ~85ms | 106ms |
| 24-tile payload | 295 KB | ~347 KB | 543 KB |
| gzipped | 78 KB | ~88 KB | 138 KB |
| SVG build (24 tiles) | 27ms | ~35ms | 53ms |

Per-tile sizing buys **24 of 24 explained zones for +52 KB** instead of +248 KB.

The VCP tab costs ~248ms regardless of bar count — its time is the fixed
2,974-row scan load, and bars are free. So there was no performance argument for
widening it either.

**GZipMiddleware was added** while measuring this: `main.py` had none. Cloudflare
normally compresses at the edge, but `/chart-maps` is auth-gated and the
`Content-Encoding` could not be observed through it, so the win is now
unconditional rather than dependent on the edge.

## Deliberately not changed

Cutting `price_zones.LOOKBACK_BARS` from 252 to 130 measured **expectancy-neutral**
(0.177 vs 0.178 over 5,371 walk-forward observations). That is a methodology
change to the zone engine under Rule #4 — it needs its own tests, its own
methodology doc and its own decision. It is not something to fold into a change
about how wide a chart is drawn.

## Not advice

Chart windows decide what you can see. They change no gate, no score and no
entry.
