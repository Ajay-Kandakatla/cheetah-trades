# Deep Demand — arrival at the 2nd or 3rd level of support

**2026-09-16.** What `backend/supply_demand/deep_demand.py` qualifies, why, and what it
deliberately does not claim.

---

## The ask

> "For the deep demand stocks I need the logic to be, the stocks that crosses the first level of
> support and lying in second or third level of support. Like CRDO dropped after the earning it
> crossed multiple support level."
> — Ajay, 2026-09-16

And, with a screenshot of a Deep Demand tile:

> "We are trying to catch the returning bounce touching the first level support. What I am
> expecting here is there are two level of support in this chart and the price is at the second
> level of support."

Before this date the read looked at a **fixed pair** — `demand_zones[0]` and `demand_zones[1]` —
so a name that had crossed *two* bands and was standing in the third was invisible, and the tile
could only ever draw one broken level.

---

## The rule

`deep_demand.arrival(dz, last)` walks the served demand window `rec["demand_zones"]`, high→low:

1. **The arrival band** is the first band the print is *inside* (`lo <= last <= hi`). If no band
   contains the print, it is the first band whose top is under the print and within
   `price_zones.NEAR_PCT` of it — approaching from above. The walk stops there: every lower band
   is farther away.
2. **A crossed level** is any band above the arrival band that the print is **strictly below**
   (`last < lo`). A band the print is not strictly below was not crossed and is never counted.
3. `levels_broken == 0` (the first level still holds) → refused; this is the ordinary Back in
   Demand case, not this screen.
4. `levels_broken > deep_demand.MAX_LEVELS_BROKEN` → refused. `level = levels_broken + 1`, so the
   screen shows arrivals at the 2nd and the 3rd level — his sentence read literally.
5. **The walk never skips a band for quality.** Touches and strength are read by `read()` *after*
   the band has been chosen. A flimsy arrival band refuses the row; it never promotes the level
   below it. Promoting would make the reported `level` lie and would silently relax the band bar.

Then `read()` applies the band bar **on the arrival band only**, unchanged:

| what | constant, by name | enforcing module |
|---|---|---|
| how deep the screen goes | `deep_demand.MAX_LEVELS_BROKEN` | `supply_demand/deep_demand.py` |
| "at the band" from above | `price_zones.NEAR_PCT` | `supply_demand/price_zones.py` |
| a real band — touches | `demand_reentry.MIN_TOUCHES` | `supply_demand/demand_reentry.py` |
| a real band — strength | `demand_reentry.MIN_ZONE_STRENGTH` | `supply_demand/demand_reentry.py` |
| how many bands are surfaced | `price_zones.MAX_ZONES_PER_SIDE` | `supply_demand/price_zones.py` |
| board row caps | `deep_demand.MAX_IN` / `MAX_NEAR` | `supply_demand/deep_demand.py` |

No new percentage, no new strength floor and no new stop was introduced by this change. The ℹ️
Rules panel (`supply_demand/rules_info.py`) builds its Deep Demand lines from those same
constants, so the page cannot drift from the code.

### The payload

`read()` keeps every key it had. `top_band` and `second_band` keep their **names and shapes** —
`demand_order.deep_key`, `room_floor.row_entry_band` / `row_bands`, `chart_maps/board.py` and the
frontend all key on the literals — but their meaning widened:

* `second_band` = the **arrival** band (no longer necessarily `demand_zones[1]`).
* `top_band` = the **highest level crossed** (`broken_bands[0]`).
* `broken_bands` *(new)* = every crossed level, high→low, `len == levels_broken`.
* `levels_broken` *(new)* = `1 .. MAX_LEVELS_BROKEN`; `level` *(new)* = `levels_broken + 1`.
* `below_top_pct` is still measured from the **first (highest)** crossed level.
* `bars_since_top_break` / `fell_from_pct` are carried **only when the highest crossed level is
  `demand_zones[0]`**. `demand_reentry.decide_from_frame` computes `top_band_read` for
  `demand_zones[0]` alone; attaching it to a different band would put another band's break dates
  on this one.

`room_floor.row_bands` now adds **every** crossed level back as a demand-kind ceiling (broken
support is resistance). Before this change only the highest was carried, so a row two levels deep
measured its room past the *top* band and read far more room than it has. Rows cached before
2026-09-16 carry no `broken_bands` and fall back to `top_band`.

---

## THE LEVEL COUNT IS READ OFF THE SURFACED WINDOW, NOT THE WHOLE STACK

This is the one thing to hold in mind when reading a tile.

`rec["demand_zones"]` is built by `price_zones.compute(..., max_zones=MAX_ZONES_PER_SIDE)`, and
that cut is `price_zones.nearest_first(...)[:cap]` — **the four demand bands nearest the print**,
then sorted high→low. It is a *sliding window around the price*, not the top of the stack. A name
that ran a long way and then fell can have older, higher bands that simply are not in the window.

So `levels_broken` means **"levels crossed among the bands currently surfaced"**, not "levels
crossed since the high". CRDO on 2026-09-16 truly has more demand bands above its print than the
window shows; the window shows one crossed level.

Counting off the *uncapped* stack was considered and not done: it changes the meaning of the
surfaced geometry for every board that shares `demand_reentry.zone_geom()`, invalidates the
population numbers this change was sized against, and would then exclude CRDO on *depth* instead
of on quality. That is Ajay's call, not a side effect of this ask.

---

## Worked example — CRDO, 2026-09-16

Close **150.39**. The served window, high→low (lo, hi, touches, strength):

| # | band | touches | strength |
|---|---|---|---|
| 0 | 161.92 – 167.68 | 1 | 28 |
| 1 | 146.34 – 151.55 | 1 | 31 |
| 2 | 132.76 – 138.00 | 2 | 54 |
| 3 | 123.87 – 128.80 | 3 | 94 |

The walk: 150.39 is **inside band 1**, and band 0's floor (161.92) is above the print → one level
crossed, standing at the **2nd level**. `arrival()` returns `(1, band 1, [band 0])`.

**CRDO is still hidden — and the level count is not what hides it.** Its geometry qualified under
the old fixed-pair rule too. What refuses it is the band bar on the arrival band:

* touches **1** < `demand_reentry.MIN_TOUCHES` (2)
* strength **31** < `demand_reentry.MIN_ZONE_STRENGTH` (40)

Those two constants were **not** changed here. Relaxing either is Ajay's call, after the study
measures whether the gate earns its keep — never a side effect of a geometry change (Rule #1,
Rule #10). Pinned by `backend/tests/test_deep_levels_2026_09_16.py` with the real numbers.

### Why a strength of 31 on a band that looks fine on the chart

`price_zones._strength` is **relative within the name**: 50% normalised touches + 50% normalised
volume, normalised against **that name's own strongest band**. The 40 floor is therefore a
*within-name* bar, not an absolute one. It systematically refuses the *recent* bands of a name
that ran a long way and then fell, because that name's oldest, deepest bands hold the volume —
CRDO's 123.87–128.80 band scores 94 and drags every newer band's normalised score down. Stated
here because it is the mechanism behind the CRDO refusal; acting on it is Ajay's call.

---

## Depth is NOT a measured edge

The prior is null and nothing in this change may imply otherwise.

* `docs/supply_demand/band_structure.md` (2026-09-16, 24,994 episodes) measured **`no_signal`** on
  the adjacent claim: `sup_gap_pct` inert, `sup1_touches` Q1 fails placebo and reweight,
  `sup1_strength`'s interval spans zero. A *bigger* first support band measured **harmful**.
* Ordering is **unchanged** — `demand_order.deep_key`, proximity first. A 3rd-level name does not
  rank above a closer 2nd-level one, and `levels_broken` is not in the sort key at all
  (pinned by a source assertion).
* Nothing new pushes. Deeper arrivals enter no alert and no paper lane.
* The board note and the ℹ️ panel say the depth is unmeasured until
  `backend/scripts/deep_levels_study.py` lands a number with a confidence interval and a placebo.

The level is a **description of where the price is standing**, so the tile can draw the levels it
already crossed. It is not a signal.

---

## His call, not decided here

1. `MIN_TOUCHES = 2` / `MIN_ZONE_STRENGTH = 40` on the arrival band — the only reason CRDO stays
   hidden; measured by the study's Q2 cell.
2. `MAX_LEVELS_BROKEN = 2` — 3 is the deepest a four-band window can express. One line.
3. Counting levels off the **uncapped** stack instead of the served window.
4. Ordering: should a deeper arrival rank above a closer shallower one? Unmeasured, not done.
5. Whether the Bonde sales gate and the room floor should apply unchanged to deeper arrivals.
6. `MAX_IN = 60` / `MAX_NEAR = 40` may now truncate on a broad-breakdown day.

## Files

* `backend/supply_demand/deep_demand.py` — `MAX_LEVELS_BROKEN`, `ordinal()`, `arrival()`, `read()`
* `backend/supply_demand/room_floor.py` — `row_bands` adds every crossed level
* `backend/supply_demand/rules_info.py` — the ℹ️ Deep Demand prose
* `backend/tests/test_deep_levels_2026_09_16.py`, `backend/tests/test_deep_demand.py`,
  `backend/tests/test_rules_info.py`
