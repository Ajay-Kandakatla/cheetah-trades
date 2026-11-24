# ⏰ Time-window glow on the 🚩 Gajjala page (2026-11-24)

Ajay 2026-11-24, verbatim: "We did some research yesterday about highest price action time 33% was after hours can you
add a reminder of that somwhere for me like radiating when we enter those timings"

**What the study actually says.** His 33% is the **first-hour burst**, not after hours. The shares below are of winners'
biggest 30-minute burst or of the day's high.
- 33.8% of the bursts start 09:30–10:30, which is 3.5× that hour's share of the clock.
- 20.8% start 09:30–09:45, inside GG's "no trades the first 15 minutes".
- 22.7% of the bursts start 15:00–17:00.
- 16:00–17:00 is the busiest hour for the day's high (15.0%).
- After hours as a whole holds 39.0% of the highs on 38.1% of the clock, which is about its fair share.

## Provenance

- **Where it comes from.** The study is in `eod-audits/research/2026-11-22_winner_time_of_day/` (report.md, prereg.md,
  tod.py, results.json).
- **What ships.** `backend/chart_maps/gajjala/data/winner_time_of_day_2026_11_22.json`, re-run from
  `backend/scripts/winner_time_of_day_2026_11_22.py`. That script is the study's tod.py plus three additive outputs per
  sample, and its logic is unchanged:
  - `burst_quarter_k` / `peak_quarter_k`: counts per 15-minute slot.
  - `first_day` / `last_day`.
  - `float_max_shares`, `burst_window_min`, `min_high_gain_pct`: the study's own 1e7 / 30 / 1.4, now named.
- **Checked.** On 2026-11-24 every original key matched the study's results.json byte for byte. The 15-minute counts
  re-add to the study's bucket counts and hourly shares (tested).
- **Why the extra outputs.** results.json alone did not carry the 09:30–09:45 share, the exact 15:00–17:00 share (its
  hourly sum rounds to 22.8), the date window or the float cap. The added outputs let every served number come from the
  file, so none is typed.

## What is served

`GET /chart-maps/gajjala/time-windows` returns
`{kind:"gajjala_time_windows", date, closed, closed_reason, half_day, state, windows:[{key,start,end,label,text}], note, source_text, fault_text}`.
It is built by `chart_maps/gajjala/time_windows.py`, which reads the file once per process.

The two windows:
- **W1 "⏰ Burst window"** is the study's first-hour bucket (09:30–10:30 ET).
- **W2 "⏰ Second wave"** is the 15:00 and 16:00 hours of the file's hourly tables (15:00–17:00 ET).

Where each part of the text comes from:
- **GG's first-15 clause** uses `GC.NO_TRADE_AFTER_OPEN_MIN` by name. If that value is not a multiple of the
  15-minute slots, the clause is dropped.
- **The 🧨 Divergence line** uses `GC.DIVERGENCE_IS["ah"]` and `GC.DIVERGENCE_IS_WINDOW`, the same source as
  `high_si.honesty()`: after-hours entries LOST MONEY, 32 trades, −8.93% net per trade.
- **The "fair share" word** follows the after-hours confidence interval against its clock share.
- **The tail** reads: "Descriptive timing, not an entry rule. UNMEASURED as a trade signal. Not advice."

How the route handles special days and errors:
- **Closed day** (`market_hours.gate.closed_reason`, weekends and holidays): returns `closed: true`. The windows are
  still listed, but the page does not glow.
- **Half day** (the house calendar `supply_demand.timeframes.HALF_DAYS`, for example 2026-11-27): the ⏰ Second wave is
  **dropped**, not cut short, because the study measured full sessions. With a 13:00 close, 15:00–17:00 no longer
  covers the close into after hours. The served `note` says so, and it is added to `source_text`. W1 is kept.
- **Missing or corrupt file, or any error:** returns 200 with `state: "fault"` and no windows, never a 500. The page
  then shows nothing.
- **Access:** the route has the same audience as the board GET, with no owner gate. It serves nothing owner-only. No
  key was added to the board payload, so no golden file moved.

## Frontend

- **Files:** `GgTimeWindow.tsx`, `hooks/useGgTimeWindows.ts`, `lib/ggTimeWindows.ts` and
  `styles/gajjala_time_window.css`.
- **Where it shows:** mounted on `GajjalaBoard.tsx` beside the ⏳ first-15 line, on 🚩 GG5 and the 🧪 audited page only.
  It is never on the 1-minute page or on Luk.
- **When it fetches:** once on mount and once when the ET date rolls over. It checks the ET clock locally every 30 s.
- **Inside a window** (start ≤ now < end): it shows the served text and source line with a soft gold box-shadow pulse.
  With `prefers-reduced-motion` it shows a static highlight with no animation.
- **Outside a window** it shows nothing. That is the quieter option, and the page is dense.
- **On a phone (430 px)** the text wraps (min-width 0, max-width 100%, wrap-anywhere).
- **Text:** the FE types no number or served word. A source guard test checks this.

Display only: it is not a gate, a push, a record or a trade. UNMEASURED as a trade signal.
