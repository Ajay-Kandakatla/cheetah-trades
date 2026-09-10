# 🔥 Sector heat on demand-zone names — MEASURED, and it does not predict

Ajay, 2026-09-09:

> increase our sectors It looks like a rotation is happening every other day
> today I see oil and energy had a bunch, money got moved in to technology too
> from Semis or reduced in semis today. I want you to consider that in the
> winning criteria. Like AVGO had burst with Semis and now its down with all
> semis.. So when we are looking at newly stocks getting dropped in to demand
> zone they might be too late. What we are looking for hot sectors in demand
> zone. I know its tough but atleast give me an indicator that its in hot
> sector or not.. Becuz when money is moved from a sector its just sitting
> there stock is not reversing quick.

and minutes later:

> yeah rare earth minerals and nuclear energy, and any other hot sectors. just
> find all the hot sectors and AI related sectors and cyclical sectors track
> all of those I think its needed.

## He is right about the grain. He is wrong about the edge.

Two separable claims. Both were measured. They came out differently.

### 1. The grain — CONFIRMED, and it was a real blind spot

The rotation board tracked 11 GICS sectors × 3 cap tiers. AVGO is labelled
`Technology / Semiconductors`, and inside a 426-name Technology row a semis
rotation is diluted to nothing. Measured on the live tape, 2026-09-09:

| group | rel_21d | rel_63d | members positive |
|---|---|---|---|
| **Technology** (the sector row) | −4.72 | −11.86 | — |
| Semiconductors | −1.95 | **−13.32** | 32% |
| Semiconductor Equipment & Materials | −2.72 | −11.63 | 30% |
| Software - Infrastructure | −0.66 | **+19.10** | 76% |

A **33-point rel_63d spread inside one sector row.** "Money got moved in to
technology too from Semis" is invisible at the sector grain and obvious one
grain down. The same day, four of the eight hottest industries were oil & gas
(Refining & Marketing +25.9, E&P +9.2, Midstream +8.5, Equipment & Services
+6.3) — his "oil and energy had a bunch", exactly.

**Fix shipped:** `rotation.tracker` now builds **industry cohorts** off the
scan's own `industry` field, which nothing was reading. 143 distinct values,
73–98 clearing the 8-member floor, covering ~2,450 names — Semiconductors and
Semiconductor Equipment & Materials as separate groups, six flavours of Oil &
Gas, Uranium, Solar, Gold. Same floor, same deterministic stride and the same
liquidity population as the cap-tier cohorts, so an industry median and the
sector median above it can never be computed over different universes.

The curated themes (`ai_semis`, `ai_power`, `nuclear`, `rare_earth`, `space`,
`quantum`, `optical`, `robotics`, `ai_infra`, `defense`, `energy`) were already
computed and never surfaced. They are now ranked and rendered — that is the "AI
related sectors" and "rare earth minerals and nuclear" half.

### The follow-up that proved the point

> robotics, energy and optic fiber, constructipn like for data centers add these

Three of those four **were already tracked**: `robotics` (19 names), `energy`
(20) and `optical` (12, the optic-fibre roster — AAOI, CIEN, COHR, FN, LITE,
POET, VIAV). He asked for them because nothing ever rendered them. That is the
whole bug, and it is why the theme rows now ship.

The fourth was genuinely missing, so **`datacenter_build`** was added: EME,
FIX, IESC, STRL, MTZ, MYRG, PRIM, APG, FLR, LGN — the mechanical, electrical
and site contractors whose backlog moves with the build-out. Deliberately
narrower than the `Engineering & Construction` industry row (31 names, half of
it highway, water and environmental work driven by federal spending rather than
AI capex) and separate from `ai_infra`, which is racks, cooling and
transmission hardware. PWR (Quanta) and DY (Dycom) fit this theme on the
business but were **left in `ai_infra`** — themes must stay disjoint and
restructuring his existing rosters is his call, not mine.

Measured the day it shipped: the build-out complex is **cold** —
`datacenter_build` −6.98 (10% of members positive, −23.71 over 63d),
`ai_infra` −3.12, `optical` −3.13, `robotics` −4.19 — while `energy` is +9.03
with **90%** of its members positive.

### 2. The edge — NOT CONFIRMED. Flat on wins, and the speed claim is inverted.

`studies/sector_heat_study.py`, over `bounce_quality_study.py`'s replayed
table: **50,191 demand-zone arrivals, 192 dates, 2,243 names.** Heat is
computed **as of the event bar** — a group's median member trailing-21-session
return minus the benchmark's, evaluated at that date, never from today's map.
Hot/cold are the outer thirds of that date's own pooled cross-section.

| arm | n | share | win% | stop% | target% | median R |
|---|---|---|---|---|---|---|
| ALL (placebo) | 50,191 | 100% | 22.8 | 76.6 | 17.8 | −1.000 |
| hot | 12,507 | 24.9% | 22.4 | 76.9 | 18.1 | −1.000 |
| neutral | 17,593 | 35.1% | 22.7 | 76.7 | 17.7 | −1.000 |
| cold | 20,091 | 40.0% | **23.2** | 76.3 | 17.9 | −1.000 |

    hot   win rate      −0.57 pp   95% [−1.87, +0.71]
    hot   stop-out rate +0.44 pp   95% [−0.83, +1.78]
    cold  win rate      +0.68 pp   95% [−0.73, +2.17]

Every interval includes zero. **Sector heat does not change whether a demand-
zone arrival works.**

#### The clock claim, which is the one he actually made

"When money is moved from a sector its just sitting there, stock is not
reversing quick" predicts that hot beats cold **most at the short clock**, with
the edge decaying as the clock lengthens. The shape is exactly right. The sign
is backwards.

| clock | hot win% | cold win% | hot − cold |
|---|---|---|---|
| 5d | 28.3 | **30.8** | **−2.55 pp** |
| 10d | 24.7 | 26.0 | −1.35 pp |
| 20d | 22.4 | 23.2 | −0.83 pp |
| 60d | 20.7 | 21.1 | −0.33 pp |

    hot vs cold at 5 sessions: −2.55 pp   95% [−4.48, −0.65]   excludes zero

Monotone decay across four horizons, and the only interval in the study that
excludes zero says **cold turns faster.**

**The likely mechanism, stated as a hypothesis and not as a finding:** a name
falling into demand while its group is *hot* is falling **against** its group —
that is usually idiosyncratic damage, and idiosyncratic damage does not snap
back. A name falling into demand with a *cold* group is riding a group
drawdown, which mean-reverts. This was not tested and should not be traded on.

Caveat, stated not hidden: one interval out of nine excludes zero, and nine
comparisons buy roughly one flag at chance. The monotone decay across all four
clocks is what makes it more than a lone flag — but it is one study.

## What shipped, and what deliberately did not

**Shipped — the indicator he asked for, as CONTEXT.** A `🔥 hot sector` /
`🧊 cold sector` / `— sector flat` badge on the demand board tiles, a line in
the demand push body, and a rules-panel line carrying these numbers. The raw
`rel_21d` always rides beside the word so the rank never hides the magnitude.

**Did NOT ship — a gate.** It measured flat, and the one significant result
points the other way. `rotation.heat` cannot even be reached from
`alert_gates` (a pinned leaf module); the read lives in
`supply_demand.bullish_context`, the SEE-only module, which makes "sector heat
can never block a push" structural rather than a promise. Pinned by
`tests/test_sector_heat.py::test_sector_heat_is_structurally_incapable_of_blocking_a_push`.

## Design notes

**Hot is a rank, pooled across grains.** There is no measured number that says
"+2% relative is hot", so a group is scored by its percentile among *every*
live group on the map (95 on 2026-09-09): top third hot, bottom third cold.
The first cut ranked within a grain and was wrong — with only 11 sectors the
top third is the top three, so Utilities at **+1.16%**, a group sitting on the
benchmark, was labelled 🔥 hot while the 73-group industry scale set a far
harder bar for the same word.

**Industry decides, theme rides along.** They disagree in sign: on 2026-09-09
the curated `ai_semis` roster read +0.28 while GICS `Semiconductors` read
−1.95. "AVGO is down with all semis" is a claim about all semis, so the
provider's label answers it and a roster of 22 names we picked does not get to
overrule it. The theme read is still returned — he asked for the AI complex,
rare earths and nuclear by name — and is printed only when it *disagrees*,
because that gap is the information.

**Thin cohorts are labelled, never dropped.** `rare_earth` has 4 members,
`quantum` 5, `defense` 6, all under the 8-member floor. A median over four
names is noise wearing a number, so they carry `thin: True` and the count is
printed.

**No lookahead.** A group's heat on date D uses closes up to and including D;
the event's entry IS that bar's close. Verified separately: truncating frames
to `t <= D` and re-running the tracker's own pure helpers reproduced the live
path's `rel_21d` exactly on 16 of 16 cohort-date pairs; only D = today diverged,
which is where `prices.with_today_bar` appends the live partial bar.

**Known caveat.** Cohort membership and the sector/industry labels are
**today's** — there is no historical sector label anywhere in the database
(`candidate_snapshots` carries 581,037 dated rows and none of them has a
sector). A name that changed industry inside the window is labelled with
today's. This biases nothing toward the hypothesis, but it is survivorship in
the labels.

## Re-run

    docker run --rm --network cheetah-market-app_default \
      -e MONGO_URL="mongodb://mongo:27017" -e PYTHONPATH=/app \
      -v <repo>/backend:/app:ro -w /app \
      -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro \
      -v <scratch>:/scratch cheetah-api:latest \
      python -u /app/studies/bounce_quality_study.py --out /scratch/bq_events.csv --no-sweep

    ... then the same container with
      python -u /app/studies/sector_heat_study.py --events /scratch/bq_events.csv
