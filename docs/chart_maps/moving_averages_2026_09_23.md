# 9 EMA · 20 SMA · 200 SMA on every chart — 2026-09-23

Ajay, 2026-09-23:

> "I need 9 EMA and 20 SMA on our charts and also 200 MA on our charts as check
> boxes.."

He answered one question before this was built: **the 200 is a 200 *SMA*
(simple)**, because Minervini's trend template and this app's SEPA gate both
read the 200-day *simple* average. The line drawn on the chart has to be the
same number as the gate that put the name on the board, or the chart argues
with the board beside it.

**These are drawings.** Nothing reads them: no board ordering, no filter, no
sort, no threshold, no alert, no gate (Rule #10). They are attached *after* the
ranking is already decided, and a test pins that a board's tile order and every
other tile key are byte-identical with and without them.

**Three periods, and they are his three** (Rule #1). No 50, no 21, no 10 "for
completeness".

---

## What ships

| | tone | label | formula |
|---|---|---|---|
| fast | `ema9` | `9 EMA` | `close.ewm(span=9, adjust=False).mean()` |
| base | `sma20` | `20 SMA` | `close.rolling(20).mean()` |
| trend | `sma200` | `200 SMA` | `close.rolling(200).mean()` |

`adjust=False` because that is what every EMA in this codebase already is
(`supply_demand/keltner.py:97`, `sepa/mood.py:157`, `chart_maps/support.py:1139`).
Matching the existing engines matters more here than any other convention: a
chart EMA that used `adjust=True` would disagree with the Keltner mid-line
drawn on the same tile.

### Backend — `backend/chart_maps/board.py`

* `MA_SPECS` — the three periods, in one place.
* `_ma_series(df)` — pure; `{"dates": [...], "<tone>": [value|None, ...]}`.
* `_ma_curves(tile, df)` — modelled on `_keltner_curves`: same by-date
  alignment, same "already present?" guard, same `try/except` that degrades to
  drawing nothing.
* `bars_for(..., frame_out=[])` — a new out-list that hands back the **full,
  untailed** frame. See below.
* Attached in `_attach_bars` (which covers `_finish`, i.e. every tab that ranks
  then loads bars) and in `turning_bullish_tiles`' own bar loop (the 🌀 KC /
  AMD tabs, which build `bars` inline). Those two are every tile board.

The MAs ride the bar load that **every** board already performs, unlike the
Keltner / AMD / Fibonacci / mean-reversion studies, which are fetched only when
one of their boxes is ticked. The reason is that those are uncited *reads* —
something claiming to tell him what a chart means — while a moving average is a
plain chart primitive he asked to see on "our charts". A drawing he cannot see
without knowing which box to tick is not a drawing he asked for.

### Frontend

* `frontend/src/lib/chartMaps.ts` — three new `CmLineTone` values, their
  `TONE_PRIORITY` (1, same as the studies: three more right-edge labels must
  never push BUY / STOP / TARGET off the gutter — `layoutLabels` drops a
  priority-1 label that cannot fit, and the coloured *line* still draws), and
  their `toneColor` cases.
* `frontend/src/lib/chartOverlays.ts` — three `OVERLAY_GROUPS` entries, one per
  period, so hiding the 200 does not take the 9 with it. All three added to
  `DEFAULT_ON`.

Colours are existing variables with existing fallbacks; no new hex is invented:

| family | swatch |
|---|---|
| `ema9` | `var(--cm-vcp, #2563eb)` |
| `sma20` | `var(--cm-mint, #6ee7b7)` |
| `sma200` | `var(--gold, #c9a227)` |

No rendering change was needed in `PatternChart.tsx`. It already draws `curves`
split on nulls, and `curveLabels()` already feeds the same `layoutLabels`
collision pass as the plan lines (that pass exists because of the 2026-09-08
"These overlap" report). `barDomain`'s `stretch` guard already ignores any
curve value more than one chart-height from the candles, so a 200 SMA far under
a name that has doubled cannot squash the price action. All four are pinned by
tests rather than left to this paragraph.

---

## The full frame, BEFORE the tail

`bars_for` builds a tile's bars as `df.tail(days)`. If the averages were
computed on that slice, a tile showing 120 bars would serve a **120-bar
average** under a "200 SMA" label — and the number would change every time he
moved the zoom dropdown.

So `_ma_series` is computed on the untailed frame, and `_ma_curves` then cuts it
down to the tile's window. `bars_for` hands the frame back through `frame_out`
precisely because the caller cannot recover it from the returned bars, and
re-reading it would mean two `prices.load_prices` calls per tile — that is a
Mongo read, not a memory read.

Pinned by `test_the_200_SMA_on_a_120_BAR_VIEW_is_the_TRUE_200_bar_average` (on a
frame where the two numbers are 130.0 and 150.0, not a rounding difference), by
`test_NEGATIVE_computing_on_the_TAILED_frame_would_have_been_wrong`, and by
`test_the_curve_does_not_move_when_he_changes_the_zoom` (60 / 120 / 250 bars,
same value).

## Alignment is BY DATE, never by position

Copied from `_keltner_curves` and for the same reason: a tile's bars can carry
today's live extended-hours bar (`prices.with_today_bar`) that the cached frame
does not have. A positional tail would shift every average one bar left across
the whole tile. A date with no value becomes a **gap** (`None`), never a guess.

## Warm-up is a gap, never a guess

* The first `period - 1` bars of every average are `None`.
* pandas gives that free on the SMA (`rolling(n)` needs n observations). It does
  **not** on the EMA: `ewm(..., adjust=False)` emits a value from the very first
  bar, so a 4-bar frame would produce a "9 EMA" of four closes. The EMA is
  masked to the same warm-up. *(See "His call" below — this is a judgement.)*
* If **every** value would be `None` — a frame shorter than the period — the
  curve is **omitted entirely**, not served as a line of nulls. A 200 SMA cannot
  exist on a 79-bar intraday frame and the chart must not imply that it does.
  The 9 and the 20 still ship on that frame.

## NaN

A pandas `rolling` / `ewm` result carries `NaN`, which breaks the frontend's
`JSON.parse` and passes every `<=` comparison on the way there. Every value goes
through the house guard `board._num`, which returns `None` for `NaN` and for the
infinities. `test_no_NaN_anywhere_in_the_served_curves` serialises the payload
with `allow_nan=False`, which is the actual wire condition.

---

## Measured latency

Read-only container probe, `cheetah-market-app-api-1`, 2026-09-23. 20 real
symbols, median frame 503 rows, tile window 130 bars, 5 repeats each (100
samples). The probe re-implements the series inside the container because the
container runs `origin/main`, not this branch.

| | ms |
|---|---|
| per tile, median | **0.895** |
| per tile, p95 | 1.102 |
| per tile, max | 1.362 |
| 60-tile board, serial | 53.7 |

Against the real thing: `board(tab="vcp", limit=24, days=130, universe="full")`
took **3,208 ms** for 13 tiles in the same container. The MAs add
13 × 0.895 ≈ **11.6 ms serial**, and `_attach_bars` runs on `BAR_WORKERS = 8`
threads, so ≈ **1.5 ms wall — about 0.05 % of that board**.

There is **no new I/O**: no extra frame load, no snapshot call, no network. It is
pandas over a frame the bar attach already holds in memory.

Re-run it with the probe in this document's sibling commit message, or simply
re-time `_ma_curves` over `prices.load_prices` frames — the script is small
enough to retype and the numbers above are what it printed.

---

## Storage key — still `cm-hidden-overlays-v2`

The key was bumped to v2 on 2026-09-12 because that change flipped an **existing**
key's default from shown to hidden, and a saved set that predated it said nothing
about the new rule.

Adding an **on-by-default** family is the opposite case. `saveHidden` writes only
the keys that *are* hidden, so a set saved before `ema9` / `sma20` / `sma200`
existed cannot contain them; `loadHidden` returns it unchanged and
`hidden.has('ema9')` is false — the three lines show. Bumping to v3 would buy
nothing and would throw away every checkbox choice he has made since 09-12.

Verified against `loadHidden` / `defaultHidden` and pinned by
`a saved v2 hidden-set from BEFORE this change > still shows all three`.

---

## Why they ship ON

`DEFAULT_ON`'s existing rule is that a **new uncited READ** must not arrive
switched on over the levels he trades. The three averages are not reads. They are
drawings he asked for by name, they say nothing, and they gate nothing — exactly
like the `position` family (his own cost and typed stop), which is on for the
same reason. Arriving off would mean he asked for three lines and got three empty
checkboxes. The reasoning is written into the comment above `DEFAULT_ON` so the
next person does not "fix" it, and
`NEGATIVE — the unmeasured study families are still OFF by default` fails if the
distinction is ever lost.

---

## Tests

Backend — `backend/tests/test_chart_moving_averages_2026_09_23.py`, **24 tests**.
Frontend — `frontend/src/lib/chartMovingAverages.test.ts`, **26 tests**.
One existing pin updated as predicted: `chartOverlays.test.ts`'s `defaultHidden`
list.

---

## His call

1. **The EMA warm-up mask.** pandas' `ewm(adjust=False)` returns a value from bar
   one, so a 9 EMA *can* be drawn on a 5-bar frame. I masked its first 8 bars to
   `None`, matching the SMA, on the reading that "warm-up is a gap, never a
   guess" applies to both families and that a 9 EMA seeded on four closes is a
   guess wearing a label. If he would rather see the seeded EMA from bar one,
   that is a one-line change. **No new number was invented either way — the mask
   is `period - 1`, and the period is his.**
2. **The Support tab's own tiles.** This package attaches the averages in
   `chart_maps/board.py`, which is every Chart Maps tile board. The Support tab
   builds its own tiles in `chart_maps/support.py` and was outside this package's
   file list. **The three checkboxes will not draw anything there yet.** If he
   wants the averages on the Support chart frames too, that is a separate,
   small change in `support.py` using the same `_ma_curves`.
3. **Intraday frames.** On the 5-minute / 60-minute frames a 200 SMA is 200
   *bars*, not 200 days, and the curve is simply omitted when the frame is
   shorter. Whether he wants the daily 200 SMA projected onto an intraday chart
   is a question nobody has asked him, and I did not invent an answer.
