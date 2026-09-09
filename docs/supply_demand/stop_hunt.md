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

## Measured

`studies/stop_hunt_study.py` — replays the bouncing cohort, annotates each event
with its sweep state, and reports **win rate and stop-out rate** with intervals
that resample **whole dates**. Mean R is deliberately not the headline: on this
cohort the top 1% of events carry 86.6% of total R and the median R is −1.000 in
every arm. See `docs/supply_demand/bullish_reversal_gates.md` for why.

Results and the gate decision follow in that file once the replay lands; until
then this is a read and nothing is gated on it.
