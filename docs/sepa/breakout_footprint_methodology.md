# Breakout footprint — "whose hands fired it?" + the emerging read

**Module:** `backend/sepa/volume.py` (`breakout_footprint`, `emerging_breakout`)
**Surfaced:** `GET /sepa/breakout/{symbol}/history` → each marker's `footprint`
plus a top-level `emerging`; rendered on the Breakout-history chart + the SEPA
detail page's Breakout tab (`BreakoutHistoryModal.tsx`).
**Never feeds the SEPA score.** As of 2026-06-21 the `suspect` (churn) read DOES
feed the buy gate: a most-recent breakout that closed in the lower THIRD
(`BREAKOUT_GATE_CHURN_LOC = -0.30`, stricter than the lower-half display warning)
on heavy volume blocks `is_buyable` — institutions are selling into it. See
`climax_distribution_methodology.md` → "Gating". Everything else here (hands
colours, the emerging read) remains display-only.

## Why
A volume-confirmed breakout (close above the prior 21-bar high on >1.5× the
50-day average volume — *Trade Like a Stock Market Wizard*, p.203) tells you a
breakout *happened*. It does not tell you **who** was behind it. Minervini's
climax-top discussion frames the distinction precisely:

> "big institutions need buyers to absorb their large blocks of shares … as the
> stock moves from strong professional hands to weak retail hands."
> — *Think & Trade Like a Champion*, p.186

So a *genuine* breakout is institutions **accumulating** — strong hands absorbing
supply on heavy volume with the close **held near the high**. A breakout that
prints heavy volume but **closes weak** (gives the day back) is suspect "churn"
— supply meeting the demand:

> "Elevated volume without much price progress — 'churning'."
> — *Think & Trade Like a Champion*, p.188

## The footprint (per breakout bar) — `breakout_footprint(df, pos)`
Three book tells, read at and around the breakout bar:

| Tell | Computation | Book |
|---|---|---|
| **Close location** | `((c−l)−(h−c))/(h−l)` ∈ −1..+1 — where the close sat in the bar's range | accumulation-day "upper half" test, p.76 / Ch.10 |
| **Volume** | breakout-bar volume ÷ 50-day average | p.203 (the breakout gate itself) |
| **Up vs down volume** | over a `BREAKOUT_RUNUP = 10`-bar run-up ("6 to 10 days of accelerated advance", p.187), plus a pocket-pivot "big block" check (bar volume > any down-day volume in the run-up) | p.187; pocket pivot (Morales/Minervini) |

These combine into a 0–100 `strength` (volume 0.40 / close-location 0.35 /
up-down 0.25) and a `hands` label:

- **`heavy_institutional`** — strength ≥ 70 with a big block.
- **`institutional`** — strength ≥ 45.
- **`light`** — confirmed but low-conviction.
- **`suspect`** — vol ≥ 1.5× but the close landed in the **lower half**
  (`close_location < 0`) → churn (p.188), regardless of strength.

## The emerging read (forward) — `emerging_breakout(df)`
Flags a breakout **setting up right now**, and whose hands are building it: the
price is coiling within `EMERGING_NEAR_HIGH_PCT = 3%` **below** its prior 21-bar
high (the pivot, p.203) **and** accumulation is building underneath — CMF > 0, or
up/down volume ≥ the accumulation threshold, or a pocket pivot. This is the
VCP/pivot setup (*TLSW* Ch.7) where volume dries in the base and a pocket pivot
signals institutions stepping in just before the pivot. It is a **watch, not a
buy** — labelled as such in the UI; never a score input.

## What this is NOT
- Not a buy/sell signal and not a gate — it annotates the *existing*
  volume-confirmed breakout markers, nothing more.
- Not the climax-distribution sell read (that is the institutional-distribution
  detector — see `climax_distribution_methodology.md`). This module reads the
  **accumulation** side (who bought the breakout); the climax module reads the
  **distribution** side (who is selling the run).

## Tests
`backend/tests/test_breakout_history.py` — footprint key shape, institutional vs
suspect-churn classification, out-of-range guard, and the emerging read (true on
a coil-under-pivot with accumulation; false when extended above the pivot, far
below it, lacking accumulation, or on short history). FE:
`frontend/src/components/BreakoutHistoryModal.test.tsx` — marker colour by hands,
churn label, the emerging callout + dashed ring, and the negative (no emerging).
