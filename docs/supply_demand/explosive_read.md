# 🧨 Explosive read — the per-name read for a stock in / arriving at a demand band

Ajay 2026-09-14, verbatim from the brief: a per-stock *explosiveness* read for
names in / arriving at a demand band — the likelihood of a **>= 5% move from the
demand band toward the first supply band** — built from RSI / volume burst / KC /
AMD / the stock's traded volume, **evaluated before it ranks**, and then ranked
on **every Chart Maps tab**.

Code: `backend/supply_demand/explosive.py` (the read, the ordering key and the
banner), `backend/scripts/explosive_study.py` (the measurement),
`backend/scripts/explosive_measured.json` (what the run wrote — the dict is
pasted from it, never typed), `backend/supply_demand/zone_store.py` (the
closed-bar `feat` block on the doc).

**Owner rules on price structure. No book, no cites — Supply & Demand scope,
never Minervini (`CITED = False`). Not advice.** His ONE typed number is the
`>= 5%`, and even that is imported: `alert_gates.ALERT_MIN_ROOM_PCT`.

> **STATUS: `no_signal`** (run 2026-09-15). See §7 for every number; nothing here is typed.

---

## 1. What this is, and what it is NOT

It is a **board ordering and a chip**. It gates no alert, sizes no position and
enters no lane — pinned by
`tests/test_explosive.py::test_SOURCE_GUARD_the_score_never_gates_an_alert_or_a_lane`,
which reads the source of every alert module and every paper lane and fails if
any of them so much as imports this one. Wiring it into a push has to be a
deliberate act that breaks a test.

The prior it was designed under (docs already in the repo): per-name reversal
ranking OOS rho 0.036 (`bounce_study.md`); all five `bounce_quality_study` gates
inert; KC `fired` −16.2pp and AMD `raided` −4.2pp against like-for-like placebos
(`turning_bullish.md`); mood, knife and sector heat inert (`sector_heat.md`).
The one demand-side separator in the repo is the band floor holding — `intact`,
+8.60pp win, CI +6.39..+11.06 (`stop_hunt.md`). **The deliverable is the honest
measurement; the null branch is the expected one and is fully built.**

---

## 2. The cohort, the outcomes, the features (as shipped)

### 2.1 Cohort — the engine's own events, never a second definition

`studies/bounce_quality_study.events()` is the cohort generator. Per bar `j`:
bands from `price_zones.compute` on bars **strictly before** `j` with the
board's own geometry (`demand_reentry.zone_geom()` = the `zone_store` "board"
tag), the two standing gates (`alert_gates.demand_proximity_gate` <= 1.0% above
the band top, `alert_gates.room_gate` >= `ALERT_MIN_ROOM_PCT` to the first
PROVEN lid), `alert_gates.approach_read` for the direction. Event band = the
nearest support under the print (the stop the push's plan text names); stop =
`band.lo × (1 − STOP_BUFFER_PCT/100)`.

* floor = `zone_store.MIN_BARS` (120) — the live board draws bands from there;
  a 252 floor threw away exactly the young names he means by "explosive".
* clocks = 5 / 10 / 20, 20 reported — "quick" is the ask.
* directions: all six collected, **`bouncing` is the baseline** (=
  `alert_gates.PUSH_DIRECTIONS`, what pushes today); the other five are printed
  controls and nothing is claimed on them.
* universes: `broad` (the boards' own), and `cache` as the **survivorship
  control** — names whose bands broke and then left the universe. No number is
  quoted without the `cache` line beside it.
* unit of analysis = **episodes**: the first event per symbol, then a 20-bar
  cooldown, so forward windows never overlap within a name.
* the cohort is WIDER than what pushes (no cap floor); `LIQ_OK_USD` runs as a
  liquidity control line.

### 2.2 Outcomes — three, one bar-part (the high), stop checked FIRST

| key | what it is |
|---|---|
| **HIT5@cl** (primary) | +5% from the entry on the high before the stop — the engine's own rule |
| HIT5B@cl | +5% from the **band top**, "from demand" read literally; entry-independent |
| HIT_LID@cl | the first proven lid touched before the stop; CLEAR events leave this denominator only |
| stop@cl | the stop-out rate — the guard that stops a "lift" that is really a wider stop |
| R / why / k_* | as the engine computes them |

Two entry conventions, same rows: **P** = `_pre` features, entry `close[j]` (the
intraday board and the phone at the print); **N** = `_at` features, entry
`open[j+1]` (the 08:15 ET board), which skips the event when the open gaps
through the stop.

### 2.3 Features — every one of them an existing engine

| feature | engine / constant it comes from |
|---|---|
| `rsi14` | `mood._rsi`, `mood.RSI_PERIOD = 14` |
| `rvol20` ("volume burst") | `amd._vol_ratio`'s arithmetic, `amd.VOL_REF_BARS = 20` |
| `rvol50` | the boards' `avg_vol_50`, `sepa.breakout_audit.VOL_AVG_BARS = 50` |
| `dvol50` ("the volume of the trader") | 50-bar median $-volume; tiers `demand_reentry.LIQ_DEEP_USD / LIQ_OK_USD / LIQ_THIN_USD` |
| `atr_pct` | Wilder `keltner._atr`, `keltner.ATR_LEN = 10` |
| `cmf20` | `sepa.volume._chaikin_money_flow`, thresholds `CMF_INFLOW_THRESHOLD / CMF_OUTFLOW_THRESHOLD` |
| `kc_*` | `keltner.EMA_LEN 20 / ATR_LEN 10 / MULT 2.0 / SQUEEZE_MULT 1.5 / BB_LEN 20 / BB_STD 2.0 / MIN_BARS 40`, `turning_bullish.COILED_MIN_POSITION 0.5 / MID_SLOPE_BARS 20` |
| `amd_raided` | `turning_bullish.amd_verdict`, grade `AMD_TURNING` |
| `dist_52wh_pct`, `above_52wl_pct` | `price_zones.LOOKBACK_BARS = 252`; NaN under 252 bars, its own bucket |
| **`intact`** | `alert_gates.sweep_read` itself — `SWEEP_WINDOW_BARS = 15` closed bars plus the event bar, then `sd_liquidity.find_sweep` (`SWEEP_MIN_PIERCE_PCT 0.15 / SWEEP_MAX_PIERCE_PCT 4.0 / RECLAIM_MAX_BARS 12 / SWEEP_MIN_VOL_X 1.3`) |
| `room_pct`, `clear`, `risk_pct` | already on the engine row |

**Excluded and why** — sector heat (already measured inert/inverted, and
`rotation_history` has no point-in-time per-symbol rows), velocity as a share of
shares outstanding (no point-in-time share count), live rvol / VWAP / 1-min
relative volume (needs the live tape; it may decorate a tooltip labelled with
`session_pct`, never rank). `rsi_slope5` and `vol_burst3` are **exploratory
only**: their lookbacks are typed by proxy from constants that mean something
else, so they are printed with their false-positive count and never scored.

Two definitions are re-implemented rather than imported, each pinned by a test:

* `kc_series` — transcribed from `scripts/turning_bullish_keltner_study.
  series_for`, which cannot be imported (it calls `main()` at module level).
  `test_kc_series_transcription_matches_keltner_verdict` checks it against
  `turning_bullish.keltner_verdict` at 200 random bars, coiled AND breaking,
  with the 3-dp rounding boundary.
* `_rvol` — the study's unrounded arithmetic. `amd._vol_ratio` ROUNDS to 2 dp,
  and a rounded value lands in a different quantile bucket than the one that was
  measured. `VOL_REF_BARS` is imported either way.

### 2.4 Statistics — the rule of reading

A bucket "separates" only if ALL of: the `ΔHIT5@20` date-clustered 95% CI
excludes 0 (positive); `Δstop@20`'s CI does not lie entirely above 0; the
bucket's `room/risk` is not below the base's; it is outside the **date-block**
placebo band (an i.i.d. keep understates it — volume and RSI extremes cluster on
flush days); the (room × risk) reweighted Δ keeps its sign; and the one-per-date
and one-per-symbol point estimates are both positive. The combined score must
then pass on **three** out-of-sample splits (date halves, reverse, symbol
disjoint), with the top-5% / top-10% / top-20% width sweep agreeing in sign and a
two-way (date × symbol) cluster CI excluding zero. Anything else is `no_signal`,
and a null is read as *"no lift larger than {MDL}pp"*, never as "zero".

---

## 3. What ships live

### 3.1 `feat_block(frame)` on the zone_store doc — fail-open

`zone_store.build_doc` stores `feat` on every doc, computed on the SAME closed
frame the bands came from (today's forming bar already dropped), so it costs no
extra I/O. It carries RSI / rvol20 / rvol50 / dvol50 / ATR% / CMF / the 52-week
box / the Keltner block, plus a `tail` of the last `SWEEP_WINDOW_BARS + 2` = 17
closed bars — what the live floor read needs, since `sweep_read` refuses a frame
under `window + 2` rows. It is a NEW key: `recent` stays five sessions
(`RECENT_SESSIONS`, an owner setting from 2026-09-05).

The call sits in a `try/except` **because `warm.one()` lets an exception
propagate and then writes nothing for that name** — no doc, no bands, no
`zone_edge` / `zone_bounce` / `demand` push. A board decoration must never be
able to silence a name. `feat_block` is also None-safe by itself: a short frame
reads `dvol50: None`, a zero Keltner span reads `kc: None`, under 252 bars the
52-week box reads None.

No `amd.find_cycle` in `feat_block` — a 180-bar cycle search would blow the
240 s / 6-worker warm budget. AMD and KC grades reach the read through
`turning_bullish.stored()`, and only if the study selected one of them.

### 3.2 `intact_read` — the real function, never an approximation

`alert_gates.sweep_read(band, frame=<the doc's tail>, day_low=…, last=<print>)`.
With a day low that is `with_session_bar`'s append path: the closed window plus
the session bar, whose volume is NaN **on purpose** (a partial session always
reads quiet, so a pierce today classifies on price alone). Without one it is the
documented old read — closed bars only — and the read carries
`session_low: false` so the tooltip says which.

The tile boards do not always have a day low; the bounce-room rows do. A
same-day pierce is therefore always visible on the row path and only sometimes
on the tile path, and the tooltip says so rather than the board pretending.

### 3.3 `read()` — one band selection, two surfaces

* **Row path** (`bounce_room.read_symbol`'s row): band = `row["demand"]`, room =
  `row["room"]`, print = `row["print"]`.
* **Tile path** (`chart_maps` tiles): band = `bounce_room.demand_read(px, doc)`,
  room = `bounce_room.room_read(px, doc)` — the same two functions the row path's
  `read_symbol` calls, so both surfaces key on ONE band.
  `test_row_path_and_tile_path_pick_the_same_band` pins it on nested bands.

`None` when the doc has no `feat` (a legacy doc) or no demand band sits at or
below the print. A band price fell THROUGH is not support — `demand_read` has
refused those since 2026-09-14 (the reclaim-from-below class, 66% stop-hit).

`bounce_room` is imported INSIDE `read()`: it imports `zone_store` at module top
and `zone_store.build_doc` lazily imports this module, so a top-level import
would close the circle.

### 3.4 `explosive_key` — the ONE ordering, mirrored in the FE

| branch | key |
|---|---|
| `separates` | `(0, −score, symbol)` |
| `no_signal` / `pending` | `(0 if intact else 1, *bounce_room.room_rank(row), symbol)` — the floor first, then CLEAR first, then room_pct desc |
| no read at all | `(2, 2, 0.0, symbol)` — **unknown always last** |

`room_rank` is reused, never retyped. The shared fixture
`backend/tests/fixtures/explosive_order_mirror_2026_09_15.json` holds both
expected orders and is read by the backend suite and by the frontend's
`compareExplosive` test, so the two can never drift.

**Fail-closed on a half-written measurement**: `status()` returns `separates`
only when the dict actually carries the selected features, their frozen edges
AND their orientation. A run that says "separates" but does not say which end of
a feature it oriented on cannot be ranked, and the board takes the fallback
instead of inventing a direction (`test_NEGATIVE_separates_without_orientation_
falls_back`).

A live read **never re-fits**: ranks are taken against the quantile edges frozen
from the S1 fit half and stored in `MEASURED["edges"]`. An unknown feature ranks
0.5 — no opinion, never a pass.

---

## 4. Analyst choices — named, so nobody calls this "no thresholds"

Not his, not constants, not measured:

* `hold = 20` (the engine's `HOLD_SESSIONS`) and the 20-bar episode cooldown;
* `floor = 120` (`zone_store.MIN_BARS`) chosen over the engine's default 252;
* quintile buckets; the top-**decile** decision cut (5% / 20% printed beside it
  and required to agree in sign);
* the **tercile** `grade` edges — the score is a mean of percentile ranks, so
  `GRADE_EDGES = (1/3, 2/3)` are the thirds of the rank scale itself;
* the S1-H1 half as the served edges ("edges from the first date half");
* draw counts 2,000 / 5,000 and seeds 3 / 7 (all the engine's own);
* `bouncing` as the baseline direction (the other five are controls);
* the headline runs WITHOUT a `--min-dvol` filter, with `LIQ_OK_USD` as a
  printed control line.

In the null branch the chip's two tooltip lines are **descriptive**: the floor
state and the room — the two reads the order is actually built from. The design
asked for the top two features by |z| against the cohort base; the study's JSON
carries the cohort's OUTCOME rates, not per-feature means and SDs, so there is
no z to compute and none was invented.

---

## 5. Limits (these go on the banner, not just in here)

1. **One regime.** ~340 dates; the three splits are two halves of one tape and a
   name-disjoint cut of the same tape. Three splits agreeing is one regime's
   answer.
2. **Closed-bar read.** The live session's volume is not in the ranked number. A
   live rvol is context only, labelled with `session_pct` (the 2026-09-14
   phantom-bar trap).
3. **Convention.** P enters at `close[j]`, N at `open[j+1]`; the stop is booked
   AT the stop through a gap and there are no costs — flatter than
   `zone_backtest`. The board names the convention it is serving.
4. **Coverage.** Bands exist for known-cap names (plus on-demand); microcaps and
   thin rows read unknown, the chip hides and they sort last. If a KC/AMD grade
   is ever selected, `turning_bullish.warm` covers the `full` universe while the
   study measures `broad` — those names read component `None` (unknown), never
   "not explosive", and the coverage strip says how many.
5. **Survivorship.** The `broad` cohort cannot see names whose bands broke and
   then left the universe; the `cache` line is printed beside every headline
   number and its delta rides the banner.
6. **Multiple comparisons.** Only the pre-registered sets are scored; ~1.4–1.7
   false selections per split are expected at 5% and are printed.

---

## 6. Verify in the container (read-only)

```
docker exec -i cheetah-market-app-api-1 sh -c 'cat > /tmp/explosive_study.py' < backend/scripts/explosive_study.py
docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u /tmp/explosive_study.py --stage both --universe broad --floor 120 --stride 18 --out /tmp/explosive_smoke.csv --json /tmp/explosive_smoke.json'
```

Every line of a `--stride` / `--names` run prints under the banner
`NOT QUOTABLE — smoke`. The full run (never during RTH — the hourly cache patch
rewrites frames from ~10:00 ET):

```
docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u /tmp/explosive_study.py --stage replay --universe broad --floor 120 --out /tmp/explosive_events.csv > /tmp/explosive_broad.log 2>&1'
docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u /tmp/explosive_study.py --stage replay --universe cache --floor 120 --out /tmp/explosive_events_cache.csv > /tmp/explosive_cache.log 2>&1'
docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u /tmp/explosive_study.py --stage stats --from-csv /tmp/explosive_events.csv --cache-csv /tmp/explosive_events_cache.csv --json /tmp/explosive_measured.json --emit-measured'
docker exec -i cheetah-market-app-api-1 cat /tmp/explosive_measured.json > backend/scripts/explosive_measured.json
```

The `--emit-measured` block is the `MEASURED` literal; it is pasted verbatim
into `backend/supply_demand/explosive.py` and the JSON is committed beside the
script. `test_measured_dict_equals_the_shipped_json` fails on any drift, so no
number is ever retyped by hand — not into the module, and not into TSX.

The live read, on the store doc:

```
docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -c "
from supply_demand import zone_store, explosive
d = zone_store.load_latest([\"AMD\"]).get(\"AMD\")
print(sorted((d or {}).get(\"feat\") or {}))
print(explosive.read(doc=d, px=d[\"prev_close\"]))
print(explosive.measured_verdict()[\"headline\"])"'
```

Tests: `backend/tests/test_explosive.py` (this module),
`backend/tests/test_explosive_study.py` (the study's own),
`frontend/src/lib/bounceRoom.test.ts` + `ExplosiveChip.test.tsx` (the mirror).

The one thing this module lends to the 🎯 ENTERABLE read (2026-09-15) is
`intact_read` — the floor adapter; ENTERABLE imports nothing else from here, its
own source guard pins that, and the 🧨 tile read keeps its pinned closed-bar
scan-print choice while ENTERABLE keys on the live print
([`enterable.md`](enterable.md) §3.4).

---

## 7. MEASURED

**Run 2026-09-15 · status `no_signal`** — every number below is read from
`backend/scripts/explosive_measured.json` (committed beside the script) and
pinned equal to `explosive.MEASURED` by `test_measured_dict_equals_the_shipped_json`.

| | value |
|---|---|
| cohort | 3585 names · 92732 reversal events · **24922 episodes** · 361 dates · 2025-03-10 -> 2026-08-14 |
| HIT5@5 / 10 / 20 (≥5% before the floor) | 28.5 / 32.6 / **34.2 %** |
| HIT5B@20 (+5% from the band top) · HIT_LID@20 (first proven lid) | 31.9 % · 21.2 % (n=21942) |
| stop@20 · R20 mean / median / trimmed | 74.5 % · 0.288 / -1.000 / 0.067 |
| room · risk · clear | 15.63 % · 2.57 % · 12.0 % |
| survivorship (cache universe, 5273 names) | HIT5@20 32.7 % · stop@20 77.0 % · Δhit5 vs broad -1.47pp (renames 4, delisted 8) |
| liquidity control (dvol ≥ $10000000.0) | n 14380 · HIT5@20 34.9 % · stop@20 73.1 % |
| OOS splits (S1 date halves · S2 reverse · S3 symbol-disjoint) | no_signal · no_signal · no_signal |
| resolution (MDL, best split) | **2.22 pp** |
| selected features · convention · fallback | [] · None · intact,room_rank |

Per-feature top buckets (convention P, reversal episodes, ΔHIT5@20 with the
date-clustered CI, Δstop@20, the room×risk reweighted Δ, and the §4.1 verdict):

```
  rvol20_pre         top=Q1   ΔHIT5@20 -0.41pp CI [-1.96, +1.08]  Δstop +1.25pp  reweighted -1.03pp  → inert
  rvol50_pre         top=Q1   ΔHIT5@20 +0.29pp CI [-1.07, +1.64]  Δstop +1.15pp  reweighted -0.05pp  → inert
  rsi14_pre          top=Q1   ΔHIT5@20 +2.70pp CI [+0.67, +4.83]  Δstop -0.32pp  reweighted +3.46pp  → inert (CI>0 but fails: outside_date_placebo,one_per_date_symbol)
  atr_pct_pre        top=Q5   ΔHIT5@20 -1.02pp CI [-2.64, +0.61]  Δstop +7.81pp  reweighted -2.50pp  → inert
  dvol50_pre         top=Q5   ΔHIT5@20 +0.77pp CI [-0.60, +2.12]  Δstop -2.89pp  reweighted +0.39pp  → inert
  kc_coiled_pre      top=yes  ΔHIT5@20 +1.08pp CI [-2.13, +4.21]  Δstop -2.41pp  reweighted +0.56pp  → inert
  kc_fired_pre       top=yes  ΔHIT5@20 +0.66pp CI [-2.40, +3.70]  Δstop -2.19pp  reweighted +0.17pp  → inert
  kc_pos_pre         top=Q1   ΔHIT5@20 +3.20pp CI [+1.25, +5.25]  Δstop -0.69pp  reweighted +4.12pp  → inert (CI>0 but fails: outside_date_placebo,one_per_date_symbol)
  amd_raided_pre     top=no   ΔHIT5@20 +0.15pp CI [-0.06, +0.38]  Δstop -0.11pp  reweighted +1.13pp  → inert
  cmf20_pre          top=Q1   ΔHIT5@20 +1.19pp CI [-0.46, +2.77]  Δstop +0.36pp  reweighted +1.70pp  → inert
  dist_52wh_pct_pre  top=Q5   ΔHIT5@20 +3.19pp CI [+0.03, +6.29]  Δstop -9.41pp  reweighted +0.73pp  → selects smaller trades
  above_52wl_pct_pre top=Q5   ΔHIT5@20 +0.90pp CI [-2.20, +3.83]  Δstop +5.33pp  reweighted -0.49pp  → inert
  intact_at          top=yes  ΔHIT5@20 +8.30pp CI [+6.66, +9.93]  Δstop -9.16pp  reweighted +3.79pp  → selects smaller trades
  room_pct           top=Q5   ΔHIT5@20 +1.80pp CI [+0.09, +3.53]  Δstop +8.84pp  reweighted n/a  → selects wider stops
```

Convention N (next-open read):

```
  rvol20_at          top=Q5   ΔHIT5@20 -0.46pp CI [-2.09, +1.12]  Δstop -1.13pp  reweighted -0.97pp  → inert
  rvol50_at          top=Q5   ΔHIT5@20 -0.59pp CI [-2.24, +1.03]  Δstop -0.41pp  reweighted -0.96pp  → inert
  rsi14_at           top=Q1   ΔHIT5@20 +1.20pp CI [-0.79, +3.14]  Δstop -0.50pp  reweighted +1.15pp  → inert
  atr_pct_at         top=Q5   ΔHIT5@20 +0.22pp CI [-1.45, +1.89]  Δstop +7.28pp  reweighted -2.65pp  → inert
  dvol50_pre         top=Q5   ΔHIT5@20 +0.20pp CI [-1.25, +1.59]  Δstop -3.23pp  reweighted -0.44pp  → inert
  kc_coiled_at       top=yes  ΔHIT5@20 +2.36pp CI [-2.23, +6.99]  Δstop -4.20pp  reweighted +1.89pp  → inert
  kc_fired_at        top=yes  ΔHIT5@20 +2.28pp CI [-2.25, +6.83]  Δstop -4.44pp  reweighted +1.80pp  → inert
  kc_pos_at          top=Q1   ΔHIT5@20 +1.20pp CI [-0.82, +3.25]  Δstop +0.74pp  reweighted +1.56pp  → inert
  amd_raided_at      top=yes  ΔHIT5@20 +0.95pp CI [-0.60, +2.47]  Δstop -0.49pp  reweighted +0.52pp  → inert
  cmf20_at           top=Q1   ΔHIT5@20 +0.70pp CI [-1.02, +2.30]  Δstop +0.55pp  reweighted +0.97pp  → inert
  dist_52wh_pct_pre  top=Q5   ΔHIT5@20 +2.17pp CI [-0.93, +5.05]  Δstop -8.72pp  reweighted -0.09pp  → inert
  above_52wl_pct_pre top=Q5   ΔHIT5@20 +1.89pp CI [-1.25, +4.92]  Δstop +4.48pp  reweighted +0.08pp  → inert
  intact_at          top=yes  ΔHIT5@20 +6.90pp CI [+5.44, +8.41]  Δstop -7.99pp  reweighted +3.19pp  → selects smaller trades
  room_pct           top=Q5   ΔHIT5@20 +2.77pp CI [+1.10, +4.45]  Δstop +8.95pp  reweighted n/a  → selects wider stops
  close_pos_at       top=Q1   ΔHIT5@20 +0.35pp CI [-1.46, +2.19]  Δstop +2.01pp  reweighted +0.19pp  → inert
  day_ret_at         top=Q5   ΔHIT5@20 +1.96pp CI [+0.06, +3.90]  Δstop -2.77pp  reweighted +0.06pp  → selects smaller trades
  pocket_pivot_at    top=yes  ΔHIT5@20 +0.84pp CI [-2.80, +4.29]  Δstop -4.78pp  reweighted -1.38pp  → inert
```

Reading: with `status == no_signal` the board ranks by the two reads that
measured — the band floor holding (`intact`) and the room to the first proven
lid — and every surface says so. The floor-held read's own lift is labelled by
the §4.2 guard where its top bucket also moves room or risk; that label is a
statement about trade SIZE, not a retraction of the 2026-09-09 gate.
