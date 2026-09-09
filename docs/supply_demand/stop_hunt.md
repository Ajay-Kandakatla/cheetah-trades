# Stop hunt vs falling knife

**Ajay, 2026-09-09:**

> I am trying to find bullish stocks that got in to demand zone for some reason
> in the short while where Institutions hunt for stop losses in the journey I
> been catching some falling knives do what ever is best

## The reframe

Everything built earlier in the day aimed at the wrong target. "Stationary
bottomed" describes a **base**. He is not hunting bases — he is hunting a
**strong** name whose demand band gets sliced through to take the stops resting
under it, and then bought back.

On a chart the stop hunt and the falling knife are the same picture: price dips
into the band. Exactly one thing separates them:

> **Did price CLOSE back above the floor?**

| state | what happened | verdict |
|---|---|---|
| `swept` | pierced the floor, closed back above it | **the setup** |
| `broken` | pierced, stayed under | **the knife** |
| `intact` | never pierced | ordinary bounce |

## This was already built

`sd_liquidity.find_sweep` has named those three states since 2026-08, with house
geometry that says what he said:

| constant | value | why |
|---|---|---|
| `SWEEP_MIN_PIERCE_PCT` | 0.15% | "must break the floor by this much to hit stops" |
| `SWEEP_MAX_PIERCE_PCT` | 4.0% | "deeper than this is a breakdown, not a stop-run" |
| `RECLAIM_MAX_BARS` | 12 | bars allowed to close back above the floor |
| `SWEEP_MIN_VOL_X` | 1.3 | sweep-bar volume vs local average — absorption, not a quiet dip |

`sd_sweep.py` goes further and is **entirely unused**: `analyze_symbol` returns
the swept bands, their **dark-pool prints inside the swept range**
(`darkpool.dark_in_band` — the institutional footprint he is describing), a trade
plan from the sweep low, freshness in bars, and `scan(..., allow_knives=False)`.
Nothing calls it. No route, no board, no cron. The only caller of `find_sweep` in
the whole repo is a backtest.

**That is the third piece of machinery in this app that answers his question and
was never wired to his phone** — after `is_falling_knife` and `mood`.

## What it says on real names

Last closed session, the band nearest each print:

| | state | read |
|---|---|---|
| CASY | `broken` | 🔪 broke the band and stayed under |
| MOS | `broken` | 🔪 broke the band and stayed under |
| CEG | `swept` | 🎯 swept the stops −2.6% · reclaimed in 1 bar · 1.4× vol |
| NTNX | `swept` | 🎯 swept the stops −1.6% · reclaimed in 1 bar · 1.7× vol |
| AVGO | `swept` | 🎯 swept the stops −3.2% · reclaimed in 6 bars |
| BMI | `intact` | — |

**MOS is the case that matters.** It passes every gate shipped earlier that day —
turn mood **+53.1**, not a falling knife — and its band is **broken**. The sweep
read separates names the shipped gates treat identically.

## Counted on the live board

Of **102** names past bouncing + ≥5% room + ≤1% above the band:

| state | n | share |
|---|---|---|
| `swept` | 38 | 37.3% |
| `intact` | 33 | 32.4% |
| **`broken`** | **31** | **30.4%** |

Two of the broken ones (STEP, TMP) cleared **every gate the phone had**. Those
are the knives still getting through.

*(A COUNT, not an edge.)*

## What shipped

A **read**, not a gate. He asked to be able to tell them apart; nothing here
blocks a push, and a contract test pins that no gate function mentions it.

- `alert_gates.sweep_read(band, symbol, frame)` → `{state, pierce_pct,
  reclaim_bars, vol_x, sweep_low, stop_shelf}`; `sweep_txt()` renders it.
- Rides in the **push body** (`demand_alerts.at_message`) and on **both push
  paths** on the frame already loaded — no extra price read.
- `demand_reentry` computes it per row on the band the row is about; board tiles
  carry `_sweep` and `_sweep_decor` badges **🎯 swept the stops** (good) or
  **🔪 band broken** (warn).
- Rules panel line built from `sd_liquidity`'s own constants.

### On the forming bar

`sweep_read` deliberately includes the **current** bar, unlike `knife_read` and
`reversal_mood_read` which drop it. That is not an inconsistency: a stop run that
happened *this morning* is the entire point, and both the day's low and the
print are known at the moment a push is decided. Nothing after the decision bar
is ever touched.

## MEASURED — and the hypothesis is refuted

`studies/stop_hunt_study.py`. **31,861 replayed bouncing events, 2,364 names,
192 dates** (2025-09-09 → 2026-06-12). Win rate and stop-out rate, with a
bootstrap that resamples **whole dates**.

| state | n | share | win | stop-out |
|---|---|---|---|---|
| 🎯 `swept` | 12,290 | 38.6% | **22.7%** | 76.9% |
| 🔪 `broken` | 11,990 | 37.6% | **21.5%** | 78.2% |
| ✅ `intact` | 7,581 | 23.8% | **30.7%** | **67.9%** |
| *baseline* | 31,861 | — | *24.1%* | *75.3%* |

As gates:

| gate | keeps | Δ win | 95% CI | Δ stop-out |
|---|---|---|---|---|
| **`intact`** | 23.8% | **+8.60pp** | **[+6.39, +11.06]** | **−9.58pp** |
| `swept` | 38.6% | **−2.37pp** | [−3.76, −1.01] | +2.62pp |
| `broken` | 37.6% | **−4.23pp** | [−5.50, −3.02] | +4.75pp |

**The stop hunt is the losing side.** A floor that was pierced and bought back
still underperforms one that was never tested, and the deeper the pierce the
worse it gets (2–4% sweeps: Δwin −2.80pp, CI [−4.49, −1.07]). Whatever a stop
run signals, it is not that the level will hold next time.

Stacking does not rescue it: `swept + mood ≥ 25` is −0.24pp (CI crosses zero),
`swept + not a knife` is −1.98pp (**worse**).

### Confirmed twice, independently

A different definition on a different window — the shelf study's *"no low cut
under the band floor in the last N sessions"*, K=20 — measured **+5.34pp
CI[+3.26, +7.43]** at N=3 and stayed positive at N=5 and N=8. Two
implementations, two windows, same answer: **the floor must not have been cut.**

### Why win rate and not R

On this cohort the top 1% of events carry **86.6% of total R**, max R is +101.8,
and the median R is **−1.000 in every arm including the baseline**. Mean R is a
tail statistic. Win and stop rates are binomials.

## What is gated now

`alert_gates.floor_held_gate` — `FLOOR_HELD_STATES = ("intact",)`. Wired into
`demand_alerts` and `zone_edge`, fails closed, counted as `skipped_floor` and
named on the Alerts page as *"skipped: band floor was pierced"*.

The 🎯 / 🔪 read still rides on the boards and in the push body: a swept band is
listed and labelled, it just does not ring.

### What it leaves, today

Of 102 names past bouncing + ≥5% room + ≤1% above the band:

| stack | names |
|---|---|
| the gates before this change | **12** — including 2 broken bands (STEP, TMP) |
| `intact` alone | 33 |
| `intact` + not-a-knife | 21 |
| **`intact` + not-a-knife + turn mood** | **6** — ADMA, AMTB, GKOS, IOSP, KNTK, TPC |

Both knives are gone.

## Honest limits

- One 9-month window, 192 dates.
- ~83% of the replayed cohort sits on bands the live push never sees (it takes
  board-qualified bands only: `touches ≥ 2`, `strength ≥ 40`, one entry zone per
  name). The **direction** is what two independent measurements agree on; the
  **size** on his own population is not yet confirmed.
- The sweep window is 15 bars. Sensitivity to that specific window is untested;
  the K=20 shelf definition agreeing is the closest thing to a check.
- `knife_gate` and `reversal_mood_gate`, shipped earlier the same day, still
  measure flat (Δwin −0.08pp and +0.30pp). They are kept because he asked for
  them, not because they earn their place. Stacking all three leaves ~6 names a
  day; that is the trade being made.
