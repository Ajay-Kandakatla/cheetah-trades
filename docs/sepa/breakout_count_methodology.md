# Breakout count + actual volume — methodology

_Added 2026-06-13 (Ajay: "give me a trend and count and volume and its actual
number instead of 2.x and expanding… how many breakouts actually happen per
stock"). Display-only; never feeds the scanner score (locked by
`tests/test_volume_spark.py::test_breakout_count_is_display_only_not_scored`)._

## What a "breakout" is (book p.203)

A bar is a **volume-confirmed breakout** when its **close exceeds the prior
21-bar high** AND its **volume is > 1.5× the trailing 50-day average** AND —
added 2026-08-03 — **the close HELD the upper half of the day's range**
(`close_location ≥ BREAKOUT_CHURN_LOC`, the −1..+1 scale).

> **Why the held-close clause (GSAT regression, Ajay 2026-08-03: "heavy sell
> off is being tracked as breakout"):** GSAT 2026-03-25 closed +10.3% above
> its prior high on 4× volume — but 7 points off the session high, deep in
> the lower half of the range: an institution selling into the spike. TTLAC
> p.188 calls this churn ("elevated volume without much price progress").
> Previously such days were counted AND boarded (with only a "suspect"
> footprint flag); now they are excluded from the count, the recency read,
> and the chart markers entirely. One shared series
> (`volume.breakout_series`) drives all three so they can never disagree.
> The SAME-DAY `is_buyable` trigger keeps its own stricter churn handling
> via the distribution gate — unchanged.

This is
the same close-above-high + volume gate the strict `is_buyable` path uses (Minervini, *Trade Like a Stock
Market Wizard*, p.203) — we just count it across history instead of only
checking the last bar.

## The count — `backend/sepa/volume.py::analyze()`

- **`breakout_count`** — the number of **distinct** breakouts over the trailing
  `BREAKOUT_COUNT_LOOKBACK` (252 ≈ 1 trading year, or available history).
  Counts **rising edges** of the per-bar breakout series, so a multi-day push
  above the prior high counts as **one** breakout, not many. Lets you see active
  breakout names (e.g. a volatile small-cap at 25/yr) vs quiet ones (a mega-cap
  at 2/yr).
- **`breakout_window_bars`** — the window it was counted over (for the "·1y" /
  "·Nmo" label).
- Paired with `last_vol` and `avg_vol_50` — the **actual share volume**, today's
  bar and the 50-day average — so the UI shows real numbers (e.g. *"vol 1.2M /
  341K avg (3.4×)"*), not just a "2.4×" ratio or an "expanding" word.

## Surfaces

| Where | Component | Source |
|---|---|---|
| SEPA card + detail | `<BreakoutStats vol={row.volume} />` | the scan payload (no fetch) |
| SEPA pivot gauge | `PivotMeter` vol label now leads with `last_vol / avg_vol (×)` | `pivotTiming.lastVol/avgVol` |
| Portfolio holding | `<BreakoutStats symbol={sym} />` | `GET /sepa/breakout/{symbol}` (held names aren't always in the scan) |
| Leaderboard | `<BreakoutLeaders />` | `GET /sepa/breakout-leaders` (top names by count) |

Endpoints live in `backend/sepa/breakout.py` (+ `main.py`).

## Populating

`breakout_count` rides in each candidate's `volume` dict, so the **card chips +
the Leaderboard board fill in on the next scan** (cron, or a manual Full Scan) —
they render nothing on scans taken before 2026-06-13. The **per-symbol endpoint**
(Portfolio) computes live, so holdings show it immediately.

## Seeing WHERE each breakout fired — the history modal

_Added 2026-06-15 (Ajay: "add a modal of the breakouts when clicked on the
breakout chip… to see where the breakout occurred")._

Clicking the 🚀 chip opens **BreakoutHistoryModal** — the trailing-year close
line with a 🟢 pinned at every breakout bar, plus a dated list (price + volume
surge). It is fed by:

- `sepa.volume.breakout_points(df)` — the **rising edges** of the *same*
  `bo_series` that `breakout_count` counts (a multi-day push above the prior
  high is ONE breakout). Returns `{date, close, volume, vol_ratio}` per breakout.
  Kept right next to the count so the **markers can never drift from the chip
  number** — locked by
  `tests/test_breakout_history.py::test_markers_cannot_drift_from_count`.
- `sepa.breakout.history_for_symbol(symbol)` — assembles the ~252-bar
  `{date, close, volume}` series + the markers. Soft-fails to `{ok: False}`.
- `GET /sepa/breakout/{symbol}/history` — the endpoint the modal fetches.

Still **display-only**: `breakout_points` reads prices, never the score, and
the modal is opened from the chip, not from any gate.

## What it is NOT

A frequency statistic, not a signal. A high breakout count is **not** a buy —
the strict `is_buyable` gate still decides "buyable now." It just answers "how
often does this name break out?"
