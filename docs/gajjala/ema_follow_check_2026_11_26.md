# Are we following his 9 / 21 EMAs? — ema-verify (2026-11-26)

## His words

Ajay, 2026-11-26, verbatim: "I am re checking Gajjals video on youtube and noticied that his charts are very clean in
action like the 9 EMA is not crossing over down below 21 as much and also can you verify is we are following this
properly."

## Verdict

| Check | Verdict | Evidence |
|---|---|---|
| Formula | **same** | thinkorswim `MovAvgExponential` (the study on his chart, `MovAvgExponential(CLOSE, 9, 0, no)`): EMA1 = price1, then α·price + (1 − α)·previous, α = 2 / (length + 1) — https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/M-N/MovAvgExponential (fetched 2026-11-26). The house EMA is `orderflow/signals.py:47-48`, the same recursion with the same seed — pinned to 1e-12 for 9 and 21 by `test_house_ema_is_the_thinkorswim_recursion`. (The FE `frontend/src/lib/ema.ts:12-13` seeds with an SMA instead; only `LiveCandlesChart` uses it — it differs in the first bars, pinned by the negative test.) |
| Bars | **same kind** | The 🚩 cards' 9 / 21 run over two sessions of closed 5-minute bars, extended hours included, never reset at the open (`backend/chart_maps/gajjala/bars.py:1-9`, `build_frame` at bars.py:184); his chart is "5 D 5m" with extended hours drawn. |
| Frame | **differs on the 👀 Watch** | The Watch draws the 1-MINUTE chart first (`backend/chart_maps/gajjala_watch/constants.py:19`, `FRAMES`, his 11-23 words "So 1 min, 5 and 15 accross board"); GG reads 5-minute (`GC.RUN_BASE_FRAME`, "I concluded on the five minute"). Measured below: on the same minutes the 1-minute chart prints about four times the down-crosses. |
| Time stamps | **differs by one bar label** | The house stamps a bar at its CLOSE ("the bar stamped 10:05 holds 10:00–10:04", bars.py:3-5). thinkorswim: a forum post says it stamps the OPEN; no official page found — NOT verified. Check on his chart (below). |
| Selection | **differs** | GG's video charts are winners picked afterwards. The 11-15 study: the 9-under-21 dip before the fill on 10/34 winners vs 11/27 losers, −0.11 [−0.34, +0.11] — nothing separates; the replay-video winners biased the eye. |

**In plain words:** the EMA is the same formula on the same kind of bars. What makes our chart look busier is the
frame: the Watch opens on 1-minute, GG on 5-minute. On the same minutes the 1-minute chart has about four times the
bars (thin names skip minutes, so not five) and prints about four times the down-crosses — the rate per 100 bars is
about the same on both (table: "down-crosses per 100 bars"). The placebo (scanner names that
did not run, same days) shows the same ratio, so it is the frame, not the names.

## The count (generated — `render_markdown` of `backend/scripts/ema_frame_cross_count_2026_11_26.json`)

Unit: one name-day. 9 / 21 EMAs over [the market day before, when cached] + [the day], extended hours included; crosses
by `ema_cross.frame_crosses` on the day's own bars only. Runners = the 📅 strip's rule; placebo = the same days'
scanner names that did not run, a seeded sample of as many as the day's cached runners. Read-only: minutes from the
1-minute cache only.

<!-- ema-frame-count:begin -->
Run 2026-11-26T08:52:33Z · sessions 15 ending 2026-11-25 · frames 1m, 5m, 15m (Watch first = 1m, GG = 5m) · EMA 9 / 21 · cluster bootstrap by symbol, 10,000 draws, seed 20261126, CI 95% · fewer than 10 symbols → no interval.

| Number | Runners (point) | Runners 95% CI | Placebo (point) | Placebo 95% CI |
|---|---|---|---|---|
| **PRIMARY — mean(down_1m − down_5m) per name-day** | 11.28 | [10.20, 12.36] | 12.67 | [11.32, 14.01] |
| Σdown_1m / Σdown_5m | 4.14 | [3.79, 4.51] | 4.40 | [4.02, 4.83] |
| mean(down_5m − down_15m) per name-day | 2.52 | [2.23, 2.81] | 2.45 | [2.16, 2.75] |
| mean down-crosses per name-day, 1m | 14.87 | [13.66, 16.12] | 16.39 | [14.89, 17.83] |
| mean down-crosses per name-day, 5m | 3.59 | [3.26, 3.94] | 3.72 | [3.39, 4.04] |
| mean down-crosses per name-day, 15m | 1.07 | [0.93, 1.23] | 1.27 | [1.10, 1.45] |
| down-crosses per 100 bars, 1m | 2.74 | [2.64, 2.85] | 2.66 | [2.55, 2.77] |
| down-crosses per 100 bars, 5m | 2.59 | [2.39, 2.79] | 2.46 | [2.29, 2.64] |
| down-crosses per 100 bars, 15m | 2.06 | [1.80, 2.33] | 2.31 | [2.03, 2.62] |
| mean(up_1m − up_5m) per name-day | 11.25 | [10.16, 12.36] | 12.72 | [11.34, 14.09] |
| Σup_1m / Σup_5m | 4.20 | [3.84, 4.58] | 4.50 | [4.09, 4.97] |
| warm-only: mean(down_1m − down_5m) per name-day | 11.37 | [10.29, 12.46] | 12.67 | [11.32, 14.01] |
| warm-only: Σdown_1m / Σdown_5m | 4.16 | [3.81, 4.53] | 4.40 | [4.02, 4.83] |

Runner ratio − placebo ratio (Σdown_1m / Σdown_5m): **-0.26** [-0.79, 0.24].

n — runners: 161 name-days / 130 symbols (159 warm) · placebo: 158 name-days / 122 symbols (158 warm).
Days walked: 15 (2026-11-05 → 2026-11-25); with a runner: 10 (2026-11-12 → 2026-11-25).
Skipped (counted): days_no_runner 5 · runner_not_cached 23 · other_not_cached 5 · runner_frame_no_bars 0 · other_frame_no_bars 0.
Known filter: A run day is in the cache only when some pass read the name on a LATER day; the placebo passes the same filter, so the comparison is like for like. The runner numbers describe runners that stayed on the scanner.
<!-- ema-frame-count:end -->

## What it does NOT show

- **Not an edge.** It counts crosses; it never says a cleaner chart makes more money. The 11-15 study found the
  9-under-21 dip separates nothing (10/34 winners vs 11/27 losers, −0.11 [−0.34, +0.11]). No rule, gate, sort or
  default moves on this number.
- **Winners in a video are picked afterwards.** A clean chart in a replay is partly the pick.
- **ONE run, 10 sessions with a runner** (2026-11-12 → 2026-11-25; the strip's rule finds no runner before 11-12, the
  five earlier days walked add nothing). 23 runner name-days were not in the cache (the known filter above) and are
  skipped, not guessed.
- **EMA decimals vs a card.** A card warms on 2 sessions, the 📅 chart on 6: the last decimals can differ early in a
  day — close, never "identical".

## The stamp offset — how to check it on his chart

Open one runner at 5-minute on his thinkorswim "5 D 5m". Is the first regular candle labelled **9:30** or **9:35**?

- **9:30** (open-stamped): a 🚩 card's "10:05" is his "10:00" — the card reads one label later for the same bar. The
  📅 continuous chart places a bar at its START, so its times match his directly.
- **9:35** (close-stamped): the cards' times match his; the 📅 chart reads one bar earlier.

Compare the same BAR, never the same label. Answer (his eyes or a screenshot): **not yet checked**.

## How to re-run

Outside regular hours of a market day (it reads the cache only):

```bash
docker exec -i -w /app cheetah-market-app-api-1 python - --json < backend/scripts/ema_frame_cross_count_2026_11_26.py > ema_frame_cross_count.json
```

Render a saved run into this doc's table (reads no cache):

```bash
cd backend && .venv/bin/python scripts/ema_frame_cross_count_2026_11_26.py --markdown scripts/ema_frame_cross_count_2026_11_26.json
```

Tests: `backend/tests/test_ema_frame_cross_count_2026_11_26.py` (the table above must equal `render_markdown` of the
shipped JSON). This run took 26 s in the api container, 2026-11-26 03:52 ET (Thanksgiving, market closed).

2026-11-26 refix: the "runner ratio − placebo ratio" interval now comes from ONE cluster bootstrap over the union of both groups' symbols (34 symbols sit in both groups, on different days; a drawn symbol brings its rows of both). It was two independent resamples, [-0.81, 0.27]. Re-derived from the saved rows of the same run (no cache read, same seed and draws): [-0.79, 0.24]. Every other number is unchanged; the interval still spans zero, the reading does not move.

## HIS CALL

- **#14 — the 👀 Watch's first chart.** Today 1-minute on top (his 11-23 words). GG reads 5-minute. Putting 5-minute
  first — on the Watch, the 📺 video view, anywhere — is his call; nothing moved here.
- **#15 — any rule from the count.** None proposed. It is a count of crosses, not an edge.
- **#16 — which clock a bar carries.** The 📅 chart shows a bar at its START; the cards and the Watch keep the CLOSE
  stamp. One convention everywhere would change a served time on every card.
