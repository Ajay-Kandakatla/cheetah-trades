# Intraday volume projection — methodology

How the Auto-Pilot intraday entry gate decides whether *today's* volume is on
track to confirm a breakout, before the session is over.

**Module:** `backend/sepa/intraday_volume.py` (pure, stdlib, unit-tested).
**Consumer:** `backend/sepa/live_gate.py` → `volume_live.projected_relvol` →
`trading/auto_entry.py` intraday path (`relvol >= AUTO_RELVOL_MIN`).

## The problem it fixes (CGNX, 2026-06-22)

The intraday gate projected the full day's volume as:

```
projected_relvol = (today_volume / session_fraction) / avg_vol_50      # LINEAR
```

This assumes volume accrues **evenly** through the 9:30–16:00 session. It does
not — the opening drive is the heaviest part of the day. So early in the
session `today_volume / session_fraction` **over-projects**: a stock that does
a normal opening pop reads a fake full-day surge.

CGNX cleared its pivot on an opening burst, read ~2× projected RelVol at ~10am
(`session_fraction ≈ 0.10`), the engine bought it, and it **faded to 0.72× of
average by the close** — below the 21-day high. A textbook failed breakout the
engine should never have taken.

## What the book says

- **TLSW p.229, "Extrapolating Volume Intraday":** project the day's volume
  *properly* — the morning trades heavier, so a hot open is not a hot day; do
  not assume the current pace holds flat.
- **TLSW p.203:** the volume-confirmation bar itself — a breakout wants volume
  well above average (~1.5×). That threshold is unchanged and still lives in
  the engine as `trading.auto_entry.AUTO_RELVOL_MIN = 1.5`.

This module changes **how we project**, not **the bar we project against**.

## The fix: a curve-aware, conservative projection

```
projected_relvol = (today_volume / expected_session_volume_fraction(frac)) / avg_vol_50
```

`expected_session_volume_fraction(f)` returns the *typical share of a full
day's volume already completed* by fraction `f` of the session, from a
piecewise-linear U-shaped curve (heavy open, lighter midday):

| session elapsed | ~time ET | typical volume done |
|---|---|---|
| 0.077 | ~10:00 | 13% |
| 0.154 | ~10:30 | 21% |
| 0.300 | ~11:30 | 36% |
| 0.500 | ~12:45 | 55% |
| 0.750 | ~14:25 | 78% |
| 0.900 | ~15:20 | 92% |
| 1.000 | 16:00 | 100% |

**The curve shape is NOT a Minervini number.** It is a standard, well-documented
property of U.S. equity intraday volume, encoded as an **empirical, owner-tunable
default**. Two properties make it safe:

1. **Conservative by construction** — `expected_session_volume_fraction(f) ≥ f`
   for every `f` in (0, 1). Dividing by it instead of by the raw fraction can
   only ever make the projection **smaller** in the morning, never larger — so
   the entry gate gets *harder* to clear, never easier.
2. **Converges at the close** — `expected_session_volume_fraction(1.0) = 1.0`,
   so end-of-day RelVol equals the true full-day RelVol. Nothing downstream of
   the close changes.

Worked example (the CGNX shape): at `frac = 0.10` a stock that has traded 0.20×
its 50-day average projects **2.0× linear** (0.20 / 0.10) but only **~1.3×
curve** (0.20 / 0.154) → below the 1.5× gate → **not bought**. A genuine surge
already at 0.40× average by the same time still projects > 1.5× and is taken —
the fix blocks fades, not real breakouts.

## Tests

- `tests/test_intraday_volume.py` — curve bounds/monotonicity/**conservatism**
  (≥ diagonal), anchor interpolation, None-safety (pre-open, no volume, no
  average), curve < linear in the morning, convergence at the close, and the
  **CGNX regression** (morning pop reads below 1.5× while linear passed; a real
  surge still clears; a genuine late fade is never inflated).
- `tests/test_trading_contracts.py::test_intraday_volume_projection_is_curve_aware_and_conservative`
  — locks the conservatism property and that `live_gate.py` sources the
  projection from `sepa.intraday_volume` (the naive `(today_vol / frac) /
  avg50` form must not reappear).

## Tuning

The curve anchors are an owner knob, not a book formula. Tightening them
(higher early values) makes intraday entries *more* conservative; flattening
them toward the diagonal returns toward the old linear behavior. Any change is
a Rule #4 edit: update this doc + the behavioral test, with sign-off.
