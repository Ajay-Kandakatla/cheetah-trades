# Climax-top institutional distribution — "selling on the way up"

**Module:** `backend/sepa/climax_distribution.py` (`detect`)
**Surfaced:** `GET /sepa/breakout/{symbol}/history` → `climax_distribution`;
rendered as the red/amber panel atop the Breakout-history chart + the SEPA detail
page's Breakout tab (`BreakoutHistoryModal.tsx`).
**Read only — never feeds the SEPA score or any buy gate.**

## Why
Ajay (2026-06-21): *"on the climax run the volume momentum and bulk purchase by
customers make institutions sell in bulk. Track the concept."* That is
Minervini's climax-top mechanic, verbatim:

> "big institutions need buyers to absorb their large blocks of shares … as a
> result, liquidation takes place on the way up when the price is advancing and
> there are buyers available, as the stock moves from strong professional hands
> to weak retail hands. Eventually, the large institutional volume overwhelms the
> retail appetite, and the stock comes crashing down."
> — *Think & Trade Like a Champion*, p.186

During a parabolic climax run the retail bulk-buying (volume momentum, a run of
up days) is the **liquidity institutions sell their big blocks into**. We detect
that syndrome while the stock is still going *up* — so the read is **sell into
strength**, *before* the breakdown that `sell_signals.evaluate` (TLSW Ch.12-13)
catches after the fact. The two are complementary: this is the top, that is the
break.

## The tells (TTLAC pp.187-188)
`detect(df, bc=None)` reads the daily tape over a 3-week climax window:

| Signal | Computation | Book |
|---|---|---|
| **Climax run** | close up ≥ `CLIMAX_GAIN_MIN = 25%` over `CLIMAX_WINDOW = 15` bars | p.187 ("+25 to 50 percent or more in one to three weeks") |
| **Up-day dominance** | ≥ `UP_DAY_RATIO_MIN = 70%` up days over the last `UP_DAY_WINDOW = 10` | p.187 ("70 percent or more up days") |
| **Heavy-volume down day** | a down close on volume > `1.5×` the 50-day avg | p.188 ("heavy volume … on a down day → large investors liquidating") |
| **Largest-volume day is DOWN** | the single biggest-volume bar of the run is a down day | p.188 |
| **Churning** | heavy volume but `|daily move| < 1%` | p.188 ("elevated volume without much price progress") |
| **High-volume reversal** | recent heavy-volume bar closing in the lower part of its range | p.188 |
| **Exhaustion gap** | a recent open ≥ 3% above the prior close | p.187-188 |

## The read
- **`distribution_underway`** (🔴) — `in_climax` **and** at least one *selling*
  tell fired (heavy-down-day / largest-vol-down / churning / reversal). The big
  boys are distributing into the run → sell into strength.
- **`climax_extended`** (🟠) — `in_climax` with up-day dominance but no selling
  tell yet → extended/exhaustion watch.
- **`none`** — not climaxing.

The `bc` base-count blob (optional) sets `late_stage` — the book reads these
tells "once the stock is extended" (p.187); late/4th-5th-stage raises conviction
but is not required to fire.

## Regression guard (real-money failure mode)
A **clean** parabolic run — all up days, rising volume, no heavy selling — must
read `climax_extended`, **never** `distribution_underway`. We don't want to
scream "institutions are selling" at a healthy strong move. Locked by
`test_clean_climax_is_not_distribution_regression`.

## Live validation (2026-06-21)
- **MRVL** (Ajay flagged "running forever"): +51.6% climax, heavy-volume down day
  → `distribution_underway`. ✅
- **WDC**: +40.5% climax, exhaustion gap, but no heavy selling → `climax_extended`.
- **NVDA** (pulled back): not climaxing → `none`.

## Relationship to other modules
- `breakout_footprint` (same endpoint) reads the **accumulation** side — *who
  bought* each breakout. This reads the **distribution** side — *who's selling*
  the run. Two halves of the strong-hands↔weak-hands transfer.
- `sell_signals.evaluate` (TLSW Ch.12-13) fires on the **breakdown** (largest
  decline since Stage 2, close below MA). This fires earlier, at the **top**,
  while price is still rising.
- `mvp.compute` / the scanner's late-stage exhaustion read flag a late-stage
  runner; this explains *why* with the specific distribution tape.

## Tests
`backend/tests/test_climax_distribution.py` — behavioral (distribution on a
heavy-down day; churn + exhaustion-gap tells), the clean-climax regression, and
negatives (not climaxing → none; short history → safe). FE:
`frontend/src/components/BreakoutHistoryModal.test.tsx` — red distribution panel +
fired tells, amber extended watch, and the no-climax negative.
