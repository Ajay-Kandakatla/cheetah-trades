# Deep Demand LEVELS — the study

**2026-09-16.** Status: **pending — nothing has been measured.**
`backend/supply_demand/deep_levels_measured.py` carries `MEASURED = None` /
`status() == "pending"`, and every surface that reads it prints the same
sentence:

> Depth is NOT measured yet — levels order nothing and gate nothing.

Script: `backend/scripts/deep_levels_study.py`
Tests: `backend/tests/test_deep_levels_study.py`
The read it measures: `backend/supply_demand/deep_demand.py`
(`arrival()` / `read()`), documented in `docs/supply_demand/deep_levels.md`.

---

## 1. The ask, and what it changed

> "For the deep demand stocks I need the logic to be, the stocks that crosses
> the first level of support and lying in second or third level of support.
> Like CRDO dropped after the earning it crossed multiple support level."
> — Ajay, 2026-09-16

The Deep Demand read used to be hardcoded to `demand_zones[0]` / `[1]`. It now
WALKS the served demand window and reports how many levels the print crossed
(`levels_broken`) and which level it is standing at (`level = levels_broken + 1`).

That raises two questions, and they are the only two this study answers:

| | question | feature |
|---|---|---|
| **Q1** | Does **depth** separate the outcome — is a 3rd-level arrival any different from a 2nd-level one? | `levels_bucket` ∈ `1 / 2 / 3 / 4+ / none` |
| **Q2** | Does the **arrival band's quality** separate it? | `arr_touches_bucket`, `arr_strength_side`, **`arr_gate_pass`** |

**Q2 is the cell that matters.** `arr_gate_pass` is the joint band bar
`deep_demand.read()` applies to the arrival band — `touches >=
demand_reentry.MIN_TOUCHES` **and** `strength >= demand_reentry.MIN_ZONE_STRENGTH`.
It is the *only* reason CRDO — his own example — does not appear on the board.

---

## 2. CRDO, worked

Close **150.39** on 2026-09-16. The served demand window (nearest four bands,
high→low):

| band | lo–hi | touches | strength |
|---|---|---|---|
| 1st | 161.92 – 167.68 | 1 | 28 |
| **arrival** | **146.34 – 151.55** | **1** | **31** |
| | 132.76 – 138.00 | 2 | 54 |
| | 123.87 – 128.80 | 3 | 94 |

The **geometry already qualifies**: one level crossed (161.92), price standing
inside the next one down → `levels_broken = 1`, `level = 2`, state `in`.
It is hidden only by the band bar on the arrival band: **touches 1 < 2** and
**strength 31 < 40**. Reproduced in the api container 2026-09-16:

```
CRDO: levels_broken 1 · level 2 · deep_state in · arr_touches 1.0
      arr_strength 31.0 · arr_gate_pass False
```

Pinned by `test_CRDO_geometry_qualifies_and_only_the_arrival_bands_quality_refuses_it`
and `test_CRDO_passes_the_moment_the_arrival_band_meets_the_IMPORTED_bar`.

Whether that bar earns its keep is **Ajay's call**, after Q2's number. This
study never changes it, and neither did the read.

`price_zones._strength` is **relative** — 50% normalised touches + 50%
normalised volume, normalised against **that name's own strongest band** — so
the 40 floor is a *within-name* bar. It systematically refuses the recent bands
of a name that ran a long way and then fell, because that name's own oldest
bands hold the volume. CRDO is exactly that shape. Stated here because it is
what the Q2 number has to be read against; nothing acts on it.

---

## 3. Cohort, outcome, and the rule of reading

* **Cohort** — `studies.bounce_quality_study.events()`, untouched: a demand
  band reached with both standing gates passing (room ≥ 5% to the first proven
  lid, print ≤ 1% above the band top). **Unit = EPISODES**: the first reversal
  event per symbol then a 20-bar cooldown (`ES.flag_episodes`), so forward
  windows never overlap inside a name.
* **Bands** — `price_zones.compute` on **closed bars strictly before the
  print** with the board's own `demand_reentry.zone_geom()`, drawn uncapped and
  then **cut to the served window by the engine's own cut**:
  `sorted(price_zones.nearest_first(demand_all, px)[:MAX_ZONES_PER_SIDE], key=-mid)`.
* **Primary outcome** — `hit5` at hold 20: **+5% before the stop** (the band
  floor less 0.5%), with `stop_20`, `R20` (mean / median / trimmed) and `win20`
  printed beside it. **Nothing is ever ranked on win rate.**
* **The rule of reading** is `explosive_study.RULE_TEXT` verbatim — CI excludes
  0, stop-outs not raised, room/risk kept, outside the **date-block placebo**,
  the reweighted delta keeps its sign, and the **one-per-date** and
  **one-per-symbol** point estimates both keep it. Plus three **OOS splits**
  (`entry_trigger_study.split_masks`) and the **MDL** of a random decile-sized
  keep, so a null says how big a lift it could have seen.
* **Cell floor** `MIN_CELL_N = 120` (imported). A cell under it prints
  `n<120 — not shown` and carries **no rates at all** — an under-floor cell must
  never look like a measurement.
* **Quotable** only on a full-universe run (`--stride 1`, no `--names`) with the
  cache-universe survivorship replay in hand. Anything else prints
  `NOT QUOTABLE` and sets `quotable: false`.

Not one threshold is typed in the script. Every cut arrives by import:
`FIVE_PCT`, `STOP_BUFFER_PCT`, `FLOOR_DEFAULT`, `HOLD_DEFAULT`,
`CLOCKS_DEFAULT`, `MIN_CELL_N`, `MAX_ZONES_PER_SIDE`, `NEAR_PCT`,
`MIN_TOUCHES`, `MIN_ZONE_STRENGTH`, `MAX_LEVELS_BROKEN`. A source scan test
fails the build if any of their values appears as a literal.

---

## 4. The cap, stated (it decides who is even in the study)

`rec["demand_zones"]` is a **sliding window of the four demand bands nearest
the print**, not the top of the stack. So `levels_broken` counts the levels
crossed **inside that window**: a name that fell a long way can have older
bands above the window that nobody counts.

Two controls carry that, both recorded per row and **neither ship-eligible**
(a served board cannot see them):

* `levels_broken_all` — the SAME shipped `arrival()` run with its depth cap
  widened to the window length. The cap is a parameter of the *read*
  (`levels_cap()`), never a change to the shipped constant, which is restored
  in a `finally` and pinned by a test.
* `arrival_within_cap` — would `deep_demand.MAX_LEVELS_BROKEN` have kept it?

`arr_gate_pass` is read under the widened cap too, so a row refused for being
too **deep** never reads as a **quality** failure.

Reading levels off the **uncapped band stack** instead is his call (spec §7.3)
and is not done. Q1's `4+` bucket is therefore **empty on a default run** —
four bands means at most three crossed — and exists so a `--max-zones` control
run can fill it. An empty cell prints "not shown", never 0%.

---

## 5. The prior is null

* `docs/supply_demand/band_structure.md` — the 2026-09-16 band-structure study,
  24,994 episodes: **`no_signal`** on the adjacent claim ("a second band below
  catches the name"), and a **bigger first support band measured HARMFUL**.
* `sd_bounce_gate_study_2026_09_09` — only `intact` separates.
* `cheetah_enterable_read_2026_09_15`, `sd_zone_timeframe_studies` — null.

So depth starts from a null, and **no copy, badge, note or ordering may imply
it is an edge** before this replay lands. The board stays proximity-first; the
tile draws the crossed levels because he asked to *see* them, not because deep
is good.

---

## 6. Running it

Read-only, in the api container, **never during RTH** (the hourly cache patch
rewrites frames). The container runs `origin/main`, where `deep_demand` has no
`arrival()` — and `deep_demand.py` is a *package module*, so piping the single
file does nothing. The whole package has to shadow it, and the script must be
invoked **by path** (a path invocation puts `/tmp/scripts` at `sys.path[0]` and
keeps the cwd off the path; `-m` or `-c` with `-w /app` puts `/app` first and
silently measures the OLD `dz[0]/dz[1]` read):

```bash
tar -C backend --exclude __pycache__ -cf - supply_demand studies scripts \
    | docker exec -i cheetah-market-app-api-1 sh -c 'cd /tmp && tar xf -'

docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/tmp:/app python -u \
    /tmp/scripts/deep_levels_study.py --stage replay --universe broad \
    --out /tmp/deep_events.csv > /tmp/deep_broad.log 2>&1'

docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/tmp:/app python -u \
    /tmp/scripts/deep_levels_study.py --stage replay --universe cache \
    --out /tmp/deep_events_cache.csv > /tmp/deep_cache.log 2>&1'

docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/tmp:/app python -u \
    /tmp/scripts/deep_levels_study.py --stage stats --from-csv /tmp/deep_events.csv \
    --cache-csv /tmp/deep_events_cache.csv --json /tmp/deep_levels_measured.json \
    --emit-measured' | tee report.txt
```

Then paste the emitted `MEASURED = {...}` literal **verbatim** into
`backend/supply_demand/deep_levels_measured.py`, commit
`backend/scripts/deep_levels_measured.json` beside it, and replace the
`RESULTS — pending` block in the script docstring with the printed summary.
Never hand-edit a number, never quote a point estimate without its CI.

---

## 7. What this study does NOT do

* It does not change `MIN_TOUCHES`, `MIN_ZONE_STRENGTH`, `MAX_LEVELS_BROKEN`,
  `zone_geom()` or `max_zones`. Every one of those is his call.
* It does not order, gate, size, alert or enter anything. Paper only,
  read-only probes.
* It does not re-implement the walk or the gate. `arrival()` and `read()` are
  imported from the shipped module, pinned by a source test — if the shipped
  rule changes, the study changes with it.

## RESULTS — 2026-09-16 (broad, floor 120, clocks [5,10,20], hold 20, primary hit5)

Re-run verbatim: `backend/scripts/deep_levels_study.py` (recipe above). Every
figure here is read from `backend/scripts/deep_levels_measured.json`, pasted by
`--emit-measured`; none is typed.

**BOTH QUESTIONS CAME BACK NULL.** 24,993 reversal episodes, 3,716 names, 362
dates, 2025-03-10 -> 2026-08-17. Base: **34.2%** reach +5% before the band
floor, **74.5%** stop out.

| | selected on the 3 splits | resolution (MDL) |
|---|---|---|
| Q1 — levels crossed | **none** | 2.59pp |
| Q2 — arrival-band quality | **none** | 2.63pp |

### Q1 — depth does nothing

Crossed 1 level 32.8% · 2 levels 33.1% · 3 levels 37.1% (widened-cap control,
n=3,178) · no level crossed 35.9%. Nothing clears the 2.59pp bar and nothing was
selected on any out-of-sample split. **Depth orders nothing and gates nothing.**

### Q2 — and neither does the band's own quality

Arrival band touched once 36.7% · twice 29.5% · 3+ times 31.4%. Strength under
40: 35.1%; at or above: 32.1%. Nothing clears the 2.63pp bar.

### THE GATE — it does not earn its keep

`MIN_TOUCHES = 2` AND `MIN_ZONE_STRENGTH = 40` on the arrival band is the only
thing hiding Ajay's own CRDO example. Measured over the 17,483 arrivals:

* passes the gate — n=6,821, hit5 **30.83%**, stop 76.06%
* **fails** the gate — n=10,662, hit5 **35.53%**, stop 75.37%
* passing costs **-3.37pp** of hits, CI [-4.43, -2.32] (excludes zero), and adds
  **+1.58pp** of stop-outs, CI [+0.63, +2.55]. Verdict: **harmful**.

**THE HONEST LIMIT, which is why this is a proposal and not a change.** The
(room x risk)-reweighted delta is **+0.45pp, CI [-0.96, +1.88] — it spans
zero**, and the one-per-symbol reweight is -0.25. The gate-pass rows carry less
room (11.05 vs 20.06) and tighter risk (2.07 vs 2.70), so the raw gap is partly
the gate selecting *tighter, closer* setups rather than *worse* ones. The
defensible claim is the weaker one: **the gate is not protective — it buys no
measurable safety, and what movement there is runs against it.**

### Distance, again

`arr_dist_pct` Q2: **+9.44pp**, CI [+7.82, +11.07], outside the date-block
placebo — but it "selects smaller trades" (room/risk 4.91 vs 6.09). This is the
third study in a row (lid-break 2026-09-07, band-structure 2026-09-16) in which
the only thing that moves is HOW FAR price is from the level, never what the
level looks like.

### Survivorship

Cache universe 5,285 names / 37,426 episodes: 32.73% vs 34.20% broad =
**-1.47pp**. Dead names included run BELOW the live universe, so no survivorship
bias is carrying this null.

### One limit on the run

The replay ran while `deep_demand.MAX_LEVELS_BROKEN` was still 2, so the
`levels_broken` column is capped at 2 and the literal records
`max_levels_shipped: 2`. The cap moved to 3 the same day. Q1's conclusion does
not depend on it — the widened-cap control carries the level-3-crossed cell
explicitly and it was selected on none of the three splits.

### HIS CALL

Relax or drop `MIN_TOUCHES` / `MIN_ZONE_STRENGTH` on the Deep Demand arrival
band? The measurement says the gate is not protective. Dropping it would show
CRDO and the ~414 names like it. **Not done — Rule #10: an S&D gate never moves
without his sign-off.**
