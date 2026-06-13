# Volume Trend (the SEPA card sparkline) — methodology

_Added 2026-06-12. Display-only; never feeds the scanner score (locked by
`backend/tests/test_volume_spark.py::test_vol_spark_is_display_only_not_scored`)._

## What it is

A multi-day **accumulation/distribution read** on every SEPA card and the ticker
detail page, complementing the single-day relative-volume gauge in the
PivotMeter. Two parts:

1. **Sparkline** — the last `VOL_SPARK_BARS` (20) daily bars as a mini
   histogram: bar **height** ∝ the bar's volume, bar **colour** = up-close day
   (green) vs down-close day (red), with the 50-day average volume drawn as a
   dashed reference line. Rising green bars above the line = institutions
   accumulating; heavy red = distribution.
2. **Verdict + plain-English caption** — e.g. _"▲ accumulating · 9 up-volume
   days vs 3 down (last 25) · up/down volume 1.4× · money flowing in."_ No
   field names, readable by a non-trader.

## Why (Minervini)

Volume is the one thing that can't be faked. Minervini's Stage-2 definition is
explicitly volume-based: _"There are more up days and up weeks on above-average
volume than down days and down weeks on above-average volume"_ (**Trade Like a
Stock Market Wizard**, pp.71–72). The sparkline is that footprint, visualised.

## Data — `backend/sepa/volume.py::analyze()`

Computed free off the close/volume series already loaded for the scan:

- **`vol_spark`** — `list[int]`, the last 20 bars as **signed volume**:
  magnitude = the bar's volume, sign = up-close (`+`) vs down-close (`−`). One
  compact array; the FE reads `abs()` for the bar height and the sign for the
  colour. NaN/short-history safe (the series simply shortens).
- The verdict + caption are derived FE-side from existing fields:
  `accumulation_strength`, `accumulation_days_25` / `distribution_days_25`
  (the count of up- vs down-volume days over the last 25 sessions, book
  p.71-72), `up_down_vol_ratio`, and `cmf_signal` (Chaikin Money Flow).

`vol_spark` flows through the slim scan payload, so it reaches the list cards;
it's **absent on scans taken before 2026-06-12**, in which case the FE falls
back to the verdict + caption (never blank).

## Frontend — `frontend/src/components/VolumeTrend.tsx`

Pure-props component. Verdict direction prefers the backend's
`accumulation_strength`; absent that, it infers from the up/down day counts.
Renders nothing when there's no volume data at all (no empty box). Tested in
`frontend/src/components/VolumeTrend.test.tsx` (positive + negative).

## What it is NOT

- **Not a signal.** It's display-only and contract-locked out of the scanner
  score — a regression that wires it into scoring fails the build.
- **Not a finished-goods/WIP split** or any 10-Q footnote read — just price ×
  volume off the daily bars.
