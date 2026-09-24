# 〰️ 9 EMA · W/M — a Chart Maps tab on weekly and monthly bars (2026-09-23)

**His ask, verbatim:** *"Also a new tab for 9EMA lines on our charts for weekly
charts and monthly charts please"* (2026-09-23, in the same message as the
three moving-average checkboxes, which are WP-1 and shipped separately in
`docs/chart_maps/moving_averages_2026_09_23.md`).

**What it is.** One Chart Maps tab, `?tab=ema_frames`, that draws each name on
his ⚡ Signals watchlist as **weekly** bars or **monthly** bars with the
9-period EMA on them. A frame toggle switches between the two.

**What it is not.** It is not measured. No study on this app's universe has
tested a 9 EMA on weekly or monthly bars — no interval, no placebo, no
out-of-sample. The blurb says so in its first sentence, the board says so above
the grid, and the served payload carries the sentence too
(`ema_frames.NOT_MEASURED`). Nothing on this tab sorts, filters, hides, gates,
enters or pushes. It draws (Rule #10).

---

## 1. One tab with a toggle, not two sections

He asked for *"a new tab"*, singular, so two tabs were never on the table. The
choice inside the package was **one toggle** vs **two stacked sections**.

| | clicks to weekly | clicks to monthly | cost |
|---|---|---|---|
| Toggle (shipped) | 0 (default) | 1 | one grid on screen |
| Two sections | 0 | 0 | the monthly copy of a name sits N tile-heights below its weekly copy |

Two sections wins on clicks and loses on the thing he is actually doing. The
comparison is *the same chart at two bar sizes*; a toggle keeps the name in the
same place on screen and swaps the bars under it, while two sections put a
name's weekly and monthly charts a full grid apart and double the scroll. One
click beats twelve tile-heights of scrolling. The tab also stays dense-safe
(Rule #5): one control strip, one grid.

The chosen frame is remembered per viewer in `localStorage`
(`cm-ema-frame`, both directions in `try/catch`). A blocked store opens on
weekly, never on nothing.

## 2. The cohort: his ⚡ Signals watchlist — and what it costs

**Reused, not new:** `GET /day/signal-lab/watchlist`, the exact list the ⚡
Signals tab already runs on (`daytrading/signal_lab.merge_holdings` — his
stored watchlist unioned with anything he holds). Signals reads those tickers
on 1-minute candles; this reads the same tickers on weekly and monthly bars.
One list, two bar sizes, at opposite ends of the timeframe range.

Why not the others:

* **📁 My holdings** — measured on the live DB: `portfolio_holdings` holds
  **1 row**. A one-tile tab is not a tab.
* **Back in Demand (`demand_reentry.cached_or_warm`)** — its only public
  accessor WARMS on a cache miss, i.e. a page open could kick off a universe
  pass. Unacceptable for a drawing board.
* **A new universe scan** — never considered. The `full` universe is ~2,650
  names and a cold pass is minutes.

**Measured cost** (read-only probe in `cheetah-market-app-api-1`, 2026-09-23,
the 12 names then on the watchlist):

| | serial | per name |
|---|---|---|
| Cohort read (`get_watchlist`) | one Mongo `find_one` | — |
| 5-year daily frames, COLD (`support._frame_for`) | 19.51 s | 1.63 s |
| the same frames, WARM (`_deep_cache`) | 6.79 s | 0.57 s |
| resample + 9 EMA, both frames | 0.053 s | 0.004 s |

The frontend fetches the names in parallel (`Promise.all`, the 📁 My holdings
pattern), so a cold open is ~2 s of wall clock and a warm one under a second.
**Zero scans are started.** The frames are the Support tab's own deep frames
with the Support tab's own cache, so a name he has already opened there costs
nothing here.

## 3. The resample convention, and why it is not the intraday one

```
weekly   df.resample("W-FRI")   # pandas defaults: label="right", closed="right"
monthly  df.resample("ME")      # pandas defaults: label="right", closed="right"
```

`supply_demand/timeframes.resample_ohlcv` resamples **1-minute** bars with
`closed="left"`, and the project has that recorded as a trap. It is correct
*there*: an intraday index stamp is the START of its interval, so the 09:30
minute covers 09:30–09:31 and must OPEN the 09:30 fifteen-minute bar.

A **daily** bar is not an interval stamp. Its index is the session DATE — a
whole day — so the week it belongs to is a calendar fact, and the natural label
for a week of sessions is the day the week ends on. That is pandas' default for
a date anchor, and it is what this codebase already does everywhere it takes
daily bars to weekly: `sepa/market_gauge._to_weekly` and `sepa/venky_filters`
both call `df.resample("W-FRI")` with the defaults.

Verified on a fixture spanning two week boundaries (Mon 2026-09-07 → Wed
2026-09-23):

```
2026-09-11  <- Mon 09-07 .. Fri 09-11   (open = Monday's, close = FRIDAY's)
2026-09-18  <- Mon 09-14 .. Fri 09-18
2026-09-25  <- Mon 09-21 .. Wed 09-23   (forming)
```

With `closed="left"` the Friday session would OPEN the next bucket and every
weekly open in the app would be one session early — that case is pinned from
both sides in `test_weekly_never_straddles_a_friday_boundary`.

**W-FRI, not W-SUN.** A Sunday anchor labels a US equity week with a day the
market was shut, and the two existing weekly readers here are Friday-anchored.
Two weekly conventions in one app is how one name gets two different weekly
closes on two pages.

**"ME", not "M".** pandas 2.x (this repo runs 2.3.3) deprecated the bare `"M"`
alias. `tv_datafeed._resample` still passes `"M"` with `label="left"`; that is
the TradingView UDF feed, it has its own label convention for a charting
client, and it is untouched here.

## 4. The forming bar

Today is mid-week and mid-month, so the last weekly bar and the last monthly
bar are INCOMPLETE. **They are shown, and they are marked.** A trader reads
where this week is trading against the line, not where last week finished — but
a forming bar drawn as a finished one is the same class of lie as a last-close
number under a live header, which this app has shipped twice.

Marked three ways that cannot drift apart:

1. the bar carries `s: "forming"` — `PatternChart` already shades and dims any
   tagged bar, so it *looks* unfinished with no new drawing code;
2. the tile carries a badge (`▱ week still forming`) and its `why` sentence
   says the period end date;
3. the payload carries `forming: {date, frame, note}`, and the board prints
   that **served** sentence under the chart. The frontend never composes it and
   never omits it (`formingNote`, pinned both ways).

**The rule:** a period is forming when its END date has not passed —
`label >= today (ET)`. It errs toward "forming": on Friday after the close the
week is still called forming until Saturday. Over-marking is the safe side of
this error; under-marking is the failure this tab was written around.

**Closed daily sessions only.** `prices.with_today_bar` is deliberately NOT
applied. Today's pre-market or after-hours print is never folded into a weekly
OHLC — the forming bar is built from the closed sessions of this week/month and
nothing else, and the tile says so.

## 5. The EMA, and the warm-up

`ewm(span=9, adjust=False)` — the house call — on the **resampled** closes. A
9-WEEK EMA, a 9-MONTH EMA. Never a 9-day EMA relabelled: that is the bug
`test_nine_week_ema_is_not_a_nine_day_ema_resampled` exists to catch, and it
pins both that the numbers differ and that the weekly line sits further from
price (nine weeks of memory, not nine days).

**9 is HIS number.** There is no 10, no 21, no 50 on this tab (Rule #1).

**Warm-up: 9 completed periods, and not one invented threshold.** The minimum
is the span itself — the fewest periods a span-9 EMA can be computed from at
all. It is arithmetic, not a quality bar:

* fewer than 9 **completed** periods → **no curve at all**, plus a served
  sentence (`"8 completed months of history — a 9-month EMA needs 9."`) shown
  under the chart. The name stays on the board: dropping it would look
  identical to the name having left his watchlist.
* the forming period does **not** count toward the warm-up (8 completed + 1
  forming is 8).
* within a long frame, the first 8 points are served as **gaps**, not seeds — a
  value computed from fewer than 9 closes is not a 9-period average and must
  not be drawn as one.

**Tone `ema9`.** The curve is emitted with the same tone as WP-1's daily 9 EMA
overlay, so his ONE "9 EMA" checkbox governs every 9 EMA this app draws on any
timeframe. The label says which frame it is (`9 EMA (weekly)` /
`9 EMA (monthly)`), because `curveLabels()` prints the right-edge label from the
last non-null value and a bare "9 EMA" there would not say what of.

On this tab the `ema9` family is **forced visible**, the 🌀 KC / AMD rule
(`chartOverlays.tabFamily`): a tab that exists to draw one overlay must not
open as bare candles because that box happens to be unticked. His saved choice
is untouched everywhere else, and the ledger shows the box locked so the reason
is on screen.

**Alignment is BY DATE**, following `board._keltner_curves`. Here the bars and
the series come off the same resampled frame, so a positional tail would happen
to work today; it is done by date anyway, because the day that stops being true
is the day every chart is silently wrong.

## 6. Where the tab sits, and why

`CM_TABS` is ordered **most-used first** and the order is meant to be measured.
A brand-new tab has no usage, so it takes a mid-pack slot and **nothing ahead
of it moves**: it lands immediately after `holdings`, with the other per-name
chart boards (🌀 KC, 🌀 AMD, 📁 My holdings), and before `bonde`. `zones`,
`deep_demand`, `quick_bounce`, `breaking`, `hot_pullback` and `patterns` — his
most-used, and the two adjacency pins the contracts enforce — are untouched, and
a bare `/chart-maps` still opens Back in Demand. `tabUsageKey` counts this tab
from its first open (`feature:chart-maps:tab:ema_frames`), exactly as it counted
🌀 KC, 🌀 AMD, 📁 My holdings and 🆕 IPOs into their slots, so the next re-cut
moves it on evidence.

## 7. Files

**Backend**
* `backend/chart_maps/ema_frames.py` — new. The resample, the forming rule, the
  EMA, the tile.
* `backend/chart_maps/api.py` — `GET /chart-maps/ema-frames?symbol=&frame=`.
* `backend/supply_demand/enterable.py` — `KIND_BY_TAB["ema_frames"] = "n/a"`
  (the tiles are weekly/monthly bars, so a daily demand read would blank the tab
  by construction; the chip says why).
* `backend/tests/fixtures/enterable_mirror_2026_09_15.json` — the same key, the
  one fixture both suites mirror.

**Frontend**
* `frontend/src/lib/emaFrames.ts` — new. Frame toggle, query, served-sentence
  readers. Nothing is recomputed here.
* `frontend/src/components/EmaFramesBoard.tsx` — new. The board.
* `frontend/src/lib/chartMaps.ts` — `CmTab`, `CM_TABS`, `TAB_META`,
  `isBoardTab`, `ENTERABLE_KIND`.
* `frontend/src/pages/ChartMaps.tsx` — mounts the board.

**Tests**
* `backend/tests/test_ema_frames_2026_09_23.py` — 24 tests.
* `frontend/src/lib/emaFrames.test.ts` — 17 tests.
* `frontend/src/components/EmaFramesBoard.test.tsx` — 10 tests.
* `frontend/src/lib/chartMaps.test.ts` — three predicted pins updated (tab
  count 28 → 29, the tab-order list, the non-board-tab list).

## 8. HIS CALL / open

1. **`frontend/scripts/contracts.mjs` needs two lines and they are not mine to
   write.** Two contracts require every non-board tab to name its renderer:
   *the 🚀 growth chip reaches EVERY Chart Maps tab* (~line 1568) and *the 🧨
   explosive chip reaches every renderer* (~line 2135). Add to **both**
   `RENDERER` maps:

   ```js
   ema_frames: 'src/components/PatternChart.tsx',
   ```

   That is the truth rather than a dodge: this board's tiles are drawn by
   `PatternChart` itself, which already renders `<GrowthChip>` and a prop-fed
   `<ExplosiveChip>`, so both chips reach the tab and the board file adds no
   second copy of either. Until those two lines land, `node scripts/contracts.mjs`
   fails with exactly two errors, both naming `ema_frames`.

2. **The ✨ NEW highlight is not written here.** `newFeatures.ts` belongs to the
   main session.

3. **The 🧨 / 🎯 / 🪜 chips are not on the board's own chrome.** They ride on
   `PatternChart` as they do on every tile. No board-level fan-out was added:
   those reads are daily-frame reads and this board is weekly/monthly.

4. **Frame windows.** The tab always resamples a **5-year** daily frame
   (`BARS_MAX`, the board's own deep window) rather than honouring the page's
   2y/3y/5y `days` control — at `days=130` a monthly frame would be 6 bars and
   below the warm-up, i.e. the default view would draw no line at all. 5 years
   gives ~261 weekly bars and ~61 monthly bars. **If he wants the window
   selectable on this tab, say so** — it is one parameter, but every shorter
   pick has to be allowed to serve no monthly line.

5. **No alert, no lane, no ordering** was wired, and none is proposed. If a 9
   EMA on weekly bars is ever to mean anything here, it goes through `/measure`
   first.
