# 🪜 Band structure — the thinnest ceiling above, the deepest floor below

*(🪜 is the icon the code actually serves — the dropdown entry is
`"🪜 Thin ceiling, layered floor"` (`chart_maps/board.py` `SORTS`), the chip
prefix is `🪜`, the ℹ️ Rules section's `emoji` is `🪜`. Nothing on his screen
says 📏.)*

Two asks on 2026-09-16, one read. Both are about the **structure of the bands
around the print**, both are answered from the same served band fields, so they
ship as one ordering and one study.

> Ajay, 2026-09-16, verbatim:
> *"Now in all chartmaps tabs, can you prioritize stock by the thinnest over
> head or Supply zone where ever is applicable"*

> Ajay, 2026-09-16, verbatim:
> *"Can you also make sure find stocks with greater support like the support
> bands are bigger and atleast another one very close if its falls below the
> first support level. Something like CRDO had at 149. It has another one right
> below it"*

In one line: **least resistance above, most catch below.** A name to put first
has a thin, weak ceiling and a deep, layered floor.

Code: `backend/supply_demand/band_structure.py` (the read, the ordering key and
the banner), `backend/scripts/band_structure_study.py` (the measurement),
`backend/scripts/band_structure_measured.json` (what the run wrote — the
`MEASURED` dict is pasted from it, never typed). Bands come from
`supply_demand/price_zones.py` through `supply_demand/zone_store.py`; the board
geometry is `demand_reentry.zone_geom()`.

**Owner rules on price structure. No book, no cites — Supply & Demand scope,
never Minervini. Not advice.** Every number below is either a field the band
engine already serves, an imported constant, or a quantile of the cohort. No
threshold, weight or score was invented for this read.

> **STATUS: `no_signal`** (run 2026-09-16). See §8 for every number; nothing
> there is typed by hand. **Neither of his two ideas separates.** The ordering
> is therefore DESCRIPTIVE and stays that way — it puts the thinnest ceiling and
> the deepest floor first because he asked for that order, not because either
> read has been shown to predict anything. Every board that carries it says so,
> and it gates nothing.

---

## 1. What this is, and what it is NOT

**It is an ordering and a chip.** It decides which tile or row he sees first and
what two sentences that tile prints. That is all.

**It is NOT a gate.** It hides nothing, pushes nothing, sizes nothing, arms
nothing. It does not touch `alert_gates`, any paper lane, `ALPACA_PAPER`, broker
keys or the crontab. A thin ceiling never makes a row enterable and a thick one
never blocks it — that verdict belongs to 🎯 ENTERABLE
([`enterable.md`](enterable.md)) and to the standing push gates
([`alert_keepset_2026_09_09.md`](alert_keepset_2026_09_09.md),
[`demand_alerts.md`](demand_alerts.md)), and neither of them reads this module.

**It is NOT a score.** There is no weighted composite of ceiling and floor.
Weights I choose are an invented formula (Rule #1), and the 🧨 read
([`explosive_read.md`](explosive_read.md)) is the precedent for what happens
instead: measure which single read separates, ship the ordering on the winner,
and if nothing separates ship a descriptive ordering with a banner that says
exactly that.

**It is NOT a new geometry.** It reads the bands the boards already draw. It
does not change `MAX_ZONES_PER_SIDE`, `SWING_WINDOW`, `MERGE_PCT` or
`HALF_WIDTH_PCT`, and it does not re-cluster anything (Rule #10). Changing any
of those reshapes every board, lane and alert at once.

---

## 2. The reads — every field, and where it comes from

Everything here is already computed. `price_zones._make_zone` returns per band
`kind, lo, hi, mid, touches, volume, bars_since_test, oldest_touch_bars,
touch_dates`; `price_zones._strength` adds `strength` = `round(100 * (0.5 *
touches/max_touch + 0.5 * volume/max_vol))`, a 0–100 number that is **half
test-count, half volume** and is relative to the other bands on that name — not
comparable across names without care (§9.4). `px` below is the row's print.

### 2.1 The CEILING — "thinnest over head or supply zone"

| id | read | how it is computed | source |
|---|---|---|---|
| `o1` | **height** of the first supply band above | `(hi - lo) / px * 100` | `_make_zone` lo/hi |
| `o2` | **strength** of that band | served | `price_zones._strength` |
| `o3` | **touches** of that band | served | `_make_zone` touches |
| `o4` | **stack** — how many supply bands sit between the print and the 52-week high | count over the band list | `zone_store` `bands` + `high_252` |
| `o5` | **distance** to that band — the CONTROL, already measured | `(band.lo - px) / px * 100` | §2.3 |

"Thin" is `o1` small: a narrow price shelf is less supply to chew through than a
wide one. `o2`/`o3` are the "weak" half of the same idea — a band that was
tested once on light volume is a thinner wall than one tested five times on
heavy volume, which is exactly what `is_proven_band` already encodes for the
alert gates (`alert_gates.is_proven_band`: 2+ touches and strength ≥ 40; this
read imports that predicate rather than restating it).

`o4` answers "how many walls, not just the first one" — the read that
`zone_edge.next_lids(bands, band)` already computes for the 🚀 supply-break
path, given the uncapped band list.

**"Supply band above" is shorthand.** What `ceiling_read` serves is
`bounce_room.room_read`'s band: the first thing price meets going up, which is
unbroken supply **or** a demand band price has already fallen through
(`broken_support` — a lost level is resistance). MTRX in §4.2 is a live case:
its ceiling is a 4-touch demand band at 10.60–11.02. Unproven bands are skipped
on the way up (§4.1 point 2, §10.9).

### 2.2 The FLOOR — "support bands are bigger and at least another one very close"

| id | read | how it is computed | source |
|---|---|---|---|
| `s1` | **height** of the first demand band below the print ("bands are bigger") | `(hi - lo) / px * 100` | `_make_zone` lo/hi |
| `s2` | **strength** of that band | served | `price_zones._strength` |
| `s3` | **touches** of that band | served | `_make_zone` touches |
| `s4` | **volume** of that band | served | `_make_zone` volume — **see §9.3, dropped by `zone_store._slim`** |
| `s5` | **GAP** to the second band ("another one right below it") | `(band1.lo - band2.hi) / px * 100` | two bands, subtraction |
| `s6` | **depth** — how many demand bands within N% below the print | count, N = a cohort quantile | §9.5 |
| `s7` | **distance** down to band 1 — the CONTROL | `(px - band1.hi) / px * 100`, 0 when the print is inside | §2.3 |

His two words map exactly: *"bands are bigger"* is `s1` (and `s2`/`s3`/`s4` as
the quality half), *"another one very close"* is `s5`, *"if it falls below the
first support level"* is what makes `s5` matter at all — the gap is the distance
price falls unsupported before the next catch.

**`s5` is undefined when there is no second demand band below.** It is served as
`null` and printed as "no 2nd band", never as `0` — a zero gap means two bands
touching, which is the opposite reading. The ordering places `null` last within
its bucket, the way `explosive_key` places an unknown read last
([`explosive_read.md`](explosive_read.md) §3.4).

### 2.3 Distance is the control, not a garnish

The 2026-09-07 last-lid study ([`lid_break_study.md`](lid_break_study.md),
`backend/supply_demand/lid_break.py`, 6,393 events on 2,597 names) found that
**distance decides**, and nothing else it tested did:

| distance from the lid to the 52-week high | reached the high within 21 sessions |
|---|---|
| ≤ 5% | **89.6%** (n=1,835) |
| 5–15% | **51.8%** (n=856) |
| > 15% | **15.3%** (n=1,276) |

against an up-day placebo of 26.4%. In the same run a **proven lid measured no
different from a single-touch lid** (57.6% vs 57.5%) and a volume-confirmed
break had **no edge** (56.7%).

Two consequences, both binding:

1. **Any thinness claim must be measured INSIDE those distance buckets**
   (`lid_break.DIST_BUCKETS`, imported, never retyped), or it is re-measuring
   distance under a new name. A thin band that happens to be near is not
   evidence that thin matters.
2. The 09-07 result is a warning about `o2`/`o3` specifically: band quality
   already failed to separate once, for a neighbouring question. That is the
   prior this study is measured against, not a reason to skip it.

The floor half has its own standing control: the 1% proximity gate
(`alert_gates.demand_proximity_gate`) that every demand push already passes.
`s7` is that same distance, carried as a stratifier.

---

## 3. The `max_zones` cap — it does NOT bite on this read

**The shipped path is uncapped.** `MAX_ZONES_PER_SIDE = 4` is the **default
argument** of `price_zones.compute`, not a property of the bands this read sees.
`zone_store.build_doc` passes `None`:

```
price_zones.compute(f, max_zones=None, **geom)        zone_store.build_doc
_cap = len(allz) if max_zones is None else max_zones  price_zones.compute
```

and `band_structure` reads **only** `doc["bands"]` — through
`bounce_room.room_read` / `bounce_room.demand_read` / `_demand_bands_below`,
never through `compute`'s capped `supply_zones` / `demand_zones` lists. So every
cluster the engine found on both sides is in front of the read.

Verified, container probe, store day 2026-09-16 (read-only):

```
docker exec -i -w /app cheetah-market-app-api-1 python - <<'EOF'
from supply_demand import zone_store
day, docs = zone_store.load_latest(["CRDO"])
b = (docs.get("CRDO") or {}).get("bands") or []
print(day, len(b), sum(1 for x in b if x["kind"] == "demand"))
EOF
```

> `2026-09-16 20 11` — **20 bands, 11 of them demand.** Four is not the number
> of bands this read is looking at.

**Why that matters, and it is the whole reason this section exists: on these
surfaces a `null` gap means there is NO second band, full stop.** It can never
mean "the cap hid it". `floor_read` serves `gap_pct: null` **and**
`bands_below`, and the chip says "no 2nd band" — that sentence is a fact about
the name, not about the read's window. Confusing the two would turn "nothing
catches this if it loses the band" into "we didn't look far enough", which is
the opposite trade. MTRX in §4.2 is exactly that case, and it is real.

Where the cap still bites — none of these feed this read, and it is listed so
nobody wires one in by accident:

| path | capped? | consequence |
|---|---|---|
| `zone_store.build_doc` → `doc["bands"]` — **the only band source this read has** | **no**, `max_zones=None` | every cluster on both sides is stored; the floor gap, the band count and the wall count are computable with no new fetch |
| `bounce_room`, `zone_edge.next_lids`, `enterable`'s supply-break room, board `_stored_band` | **no** — they all read `doc["bands"]` | same |
| the Support tab's chart bands | **no** — `chart_maps/support.py` calls `compute(..., max_zones=None)` with the FINE geometry | uncapped, different geometry (§9.2) |
| any caller that takes `compute`'s default (`board.py::undervalue_tiles` `pz.compute(df)`, `demand_reentry.decide_from_frame`, `quick_bounce`, `lid_break`, `sd_bounce`) | **yes, 4 per side** | a 5th band under the 4th is silently missing — so a band read sourced from one of those is NOT interchangeable with this one |

**If a read ever needs the capped lists, it passes a larger `max_zones` (or
`None`) explicitly at its own call site and says so.** That is a parameter on
one read. It is never a change to `MAX_ZONES_PER_SIDE` itself — that constant is
the default for every board, lane and alert in the app, and moving it reshapes
all of them at once (Rule #10).

A `null` gap is still never rendered as "no support below": there is a first
band under the print (that is what `bands_below >= 1` says), there is simply no
second one under it.

---

## 4. Worked end to end — his CRDO, and the MTRX counter-example

Both are 2026-09-16, both on the **board geometry** (`demand_reentry.zone_geom()`
— `swing_window=5, merge_pct=4.0, half_width_pct=1.75`), both **uncapped**
(`max_zones=None`, §3), both run through the shipped `band_structure.read()` on
the stored document rather than re-derived by hand. A later day moves every
number, which is why none of them is typed into code.

### 4.1 CRDO — the shape he asked for

CRDO close **162.76**. The store's 11 demand bands, high → low (all 20 bands are
in the doc; the supply side is below):

| lo – hi | height | vs the print | touches |
|---|---|---|---|
| 221.71 – 229.61 | 4.85% | 36.2% above | 1 |
| 207.80 – 215.20 | 4.55% | 27.7% above | 1 |
| 196.50 – 203.50 | 4.30% | 20.7% above | 1 |
| 182.61 – 189.12 | 4.00% | 12.2% above | 1 |
| 173.90 – 180.10 | 3.81% | 6.8% above | 1 |
| **161.92 – 167.68** | **3.54%** | the print is **inside** it | 1 |
| **146.34 – 151.55** | **3.20%** | hi 6.9% below — **his "149"** | 1 |
| 132.76 – 138.00 | 3.22% | 15.2% below | 2 |
| 123.87 – 128.80 | 3.03% | 20.9% below | 3 |
| 92.60 – 94.19 | 0.98% | 42.1% below | 2 |
| 84.97 – 88.00 | 1.86% | 45.9% below | 1 |

**Supply above the print:** 193.50 – 198.97 (2 touches), 210.97 – 213.80 (2),
241.14 – 244.46 (2), 280.50 – 286.24 (2), 303.27 – 314.07 (1) — plus
161.92 – 167.68 (**1 touch**), the band the print is standing in.

**His ask, answered:** *"Something like CRDO had at 149. It has another one
right below it."* 161.92 – 167.68 is the level price is standing on;
146.34 – 151.55 is the one right below it, and it is his 149.

The GAP:

```
(161.92 - 151.55) / 162.76 * 100  =  10.37 / 162.76 * 100  =  6.37%
```

So if CRDO loses 161.92 it falls **6.37% of price** before the next band catches
it, and that next band is 3.20% wide. That is his second ask in two numbers.

**What the shipped read actually serves** for that print — not a hand
calculation, the module's own output:

```
ceiling: state ROOM · band 193.50–198.97 · height_pct 3.36 · distance_pct 18.89
         walls_above 4 · walls_to_high 4 · at_highs false
         untested_band 161.92–167.68 (1 touch) · untested_distance_pct 0.0
         in_untested_band true
floor:   band 161.92–167.68 · in_band true · height_pct 3.54 · distance_pct 0.0
         second 146.34–151.55 · gap_pct 6.37 · bands_below 6
stat:    "ceiling 3.4% wide, 18.9% up (price inside its floor band, untested overhead) · floor 3.5% wide, 2nd band 6.4% under"
key:     (0, 1.0, 3.36, 0.0, 6.37, -3.54, 'CRDO')
```

Three things that output settles, and they are not what the brief's illustrative
wording implies:

1. **Band 1 of the floor is the band CONTAINING the print** (161.92 – 167.68),
   not the first band strictly below it — because band 1 is
   `bounce_room.demand_read` verbatim, and that is what it returns. So the floor
   height on the chip is 3.5%, not 3.2%, and the gap is measured from the
   containing band's low. §10.1 is therefore a question about **changing** a
   decision the code has already made, not an open one.
2. **The served ceiling is 193.50, 18.9% up — not the band the print is
   standing in. That band is not invisible either.**
   `ceiling_read` takes `bounce_room.room_read`, which skips bands nobody has
   tested (`alert_gates.is_proven_band`, the KLAC rule): 161.92 – 167.68 is
   **1-touch**, so it is not counted overhead here, exactly as it is not counted
   overhead by the room gate, the boards or the 🧨 chip. What it IS counted as
   is `untested_band` / `untested_distance_pct` / `in_untested_band` — three
   served fields from `band_structure._untested_overhead`, which asks
   `bounce_room.overhead_bands` the same question twice (once as it stands,
   once with the touch count lifted to `LID_MIN_TOUCHES`) and takes the
   difference — and `stat_line` says it in words, which is why the sentence
   above carries "(price inside its floor band, untested overhead)". Whether a
   rank — as opposed to a push gate — should let that band BE the ceiling is
   still **open and his**, and it is §10.9. Nothing here should be read as
   saying that question is settled.
3. The brief's illustrative sentence — *"ceiling 3.5% wide, 0.5% up · floor 3.2%
   wide, 2nd band 6.4% under"* — is the SHAPE of the chip, not this name's
   output. Only the gap survives unchanged.

**Every band around his print is 1-touch** (§9.1); the proven ones on this name
(132.76, 123.87, 92.60) are all far below.

### 4.2 MTRX — the shape his ask is trying to AVOID

Same session, same geometry, same call. MTRX print **9.90**:

| kind | lo – hi | height | vs the print | touches |
|---|---|---|---|---|
| demand | 12.63 – 13.09 | 4.65% | 27.6% above | 1 |
| demand | 12.23 – 12.57 | 3.43% | 23.5% above | 2 |
| demand | 11.54 – 12.00 | 4.65% | 16.6% above | 9 |
| demand | 10.60 – 11.02 | 4.24% | 7.1% above | 4 |
| **demand** | **9.70 – 9.88** | **1.82%** | **hi 0.2% below — the first catch** | 2 |

```
floor:   band 9.70–9.88 · in_band false · height_pct 1.82 · distance_pct 0.2
         second null · gap_pct null · bands_below 1
ceiling: state ROOM · height_pct 4.24 · distance_pct 7.07 · walls_above 7
stat:    "ceiling 4.2% wide, 7.1% up · floor 1.8% wide, no 2nd band"
key:     (0, 1.0, 4.24, 1.0, 0.0, -1.82, 'MTRX')
```

**9.70 – 9.88 is the LOWEST demand band on the name.** Below it there is
nothing: `second` is `null`, `gap_pct` is `null`, `bands_below` is `1`. The doc
carries **12 bands** and is uncapped, so that is a fact about MTRX, not a
window (§3). If price loses 9.70 there is no next catch in the read at all —
which is precisely the shape his second ask exists to sort away from, and the
reason `gap_pct` is served as `null` and printed as "no 2nd band" rather than as
`0`. A zero gap would mean two bands touching: the best possible layering, the
exact opposite of this.

Side by side, the fallback key puts CRDO first — `(0, 1.0, **3.36**, **0.0**, …)`
beats `(0, 1.0, **4.24**, **1.0**, …)` on the ceiling before the floor is even
consulted. The floor half only separates these two if the ceilings tie; that
lexicographic behaviour is stated on the banner rather than implied (§1).

**Reproduce either one** (read-only, in the container):

```
docker exec -i -w /app cheetah-market-app-api-1 python - <<'EOF'
from supply_demand import zone_store
day, docs = zone_store.load_latest(["CRDO"])
d = docs.get("CRDO") or {}
px = 162.76
for b in d.get("bands") or []:
    print(b["kind"], round(b["lo"], 2), round(b["hi"], 2),
          "h=%.2f%%" % ((b["hi"] - b["lo"]) / px * 100),
          "d=%.2f%%" % ((b["lo"] - px) / px * 100),
          "touches=%s strength=%s" % (b["touches"], b.get("strength")))
EOF
```

A name the store does not carry — under its cap floor (`zone_store.MIN_CAP_USD`,
which is where MTRX sits) or simply not warmed yet — has its doc built the same way
on demand — `zone_store.build_doc(sym, prices.load_prices(sym, "2y"), day)`,
the same shape, the same geometry. The served read above came from that call.

---

## 5. Where it shows, per tab

Chart Maps has 26 tabs (`frontend/src/lib/chartMaps.ts` `CM_TABS`). Which read a
tab's rows get is already decided by `supply_demand/enterable.py::KIND_BY_TAB`,
mirrored in `ENTERABLE_KIND` and pinned by
`backend/tests/fixtures/enterable_mirror_2026_09_15.json`. **This ordering reuses
that map rather than inventing a second one.**

**`KIND_BY_TAB` says what a tab's rows ARE. It does not say what a tab RENDERS.**
Those are two different facts and this doc kept confusing them. A tab gets the
read only if the endpoint it actually renders from serves it, and **three**
routes do:

* `chart_maps/board.py::board()` — the tile grid, via `attach_band_structure`;
* `chart_maps/api.py::chart_maps_support` — the one-symbol view, the same call;
* `POST /supply-demand/bounce-room` — `bounce_room.read_symbol` puts
  `row["band_structure"]` on every row, which is how the ten row boards get it.

The first two also serve the ordering; the bounce-room route serves the read
only (§5.0). A tab whose component renders from some fourth endpoint would get
nothing, whatever `KIND_BY_TAB` says about its rows — today there is no such
Chart Maps tab.

**What the KIND map says:**

| kind | tabs |
|---|---|
| `demand` | `zones`, `deep_demand`, `quick_bounce`, `hot_pullback`, `session`, `signals`, `overnight`, `patterns`, `bonde`, `growth`, `gnt`, `catalysts`, `hot_sectors`, `keltner`, `amd`, `gabbar`, `ict`, `holdings`, `support` |
| `supply_break` | `breaking` |
| `n/a` | `vcp`, `winners`, `topping`, `earnings`, `zero_dte`, `undervalue` |

**`supply_break` gets BOTH halves, not the ceiling only.** `read()` branches on
`kind` in exactly one place — `KIND_NA` short-circuits to an applicable-false
read — so every other kind runs the same `ceiling_read` + `floor_read` over the
same doc. Verified:

```
BS.read(doc=…, px=100.0, symbol="TEST", kind="supply_break")
  -> ceiling {...} · floor {"gap_pct": 5.0, "bands_below": 2, ...}
  -> stat "ceiling 2.0% wide, 10.0% up · floor 3.0% wide, 2nd band 5.0% under"
```

That is the right behaviour for the Breaking tab — a lid being cleared still has
a floor under it, and his second ask is about exactly that — but the doc said
the opposite, so it is written down here rather than left to the reader.

### 5.0 COVERAGE TODAY — verified against the code, 2026-09-16

Every claim in this table was re-read out of the files named beside it on this
branch. It is what the code does, not what is planned; the previous two versions
of this section were wrong in both directions and that is the only reason it is
this literal.

| surface | tabs | 🪜 chip / stat | 🪜 ordering | the study's verdict |
|---|---|---|---|---|
| tile grid, `demand` + `supply_break` | `zones` `deep_demand` `quick_bounce` `breaking` `keltner` `amd` `gabbar` `ict` (8) | **yes** — `chart_maps/board.py::attach_band_structure` puts the whole read on every tile and appends the `Bands` stat | **yes** — `?sort=band_structure`, applied AFTER the live overlay and AFTER the cut (`board.POST_CUT_SORTS` + `is_explicit_sort`, then `_band_structure_sort`) | **yes**, page-level — served `band_structure_study`, rendered in `ChartMaps.tsx` with `band_structure_scope` under it |
| tile grid, `n/a` | `vcp` `winners` `topping` `earnings` `zero_dte` `undervalue` (6) | **none, and that is correct** — `read()` short-circuits to `applicable: false` + `na_text`, and `BandStructureChip` renders `null` | **not offered** — `board()` drops the `band_structure` entry from the served `sorts` when `kind_for_tab(tab)` is `enterable.KIND_NA`, the same rule the three ledger tabs are held to. A hand-typed `?sort=band_structure` still fails closed: `board.band_structure_sort_na()` answers with the served n/a sentence, whose category list is built from `band_structure.NA_CATEGORIES` rather than retyped | **suppressed** — the page checks the served `band_structure_kind` (`ChartMaps.tsx`, `bandNa`) and prints the served per-tile `na_text` line instead (`data-testid="cm-band-structure-na"`), the 🎯 `HiddenCount` precedent |
| one-symbol view (`/chart-maps/support`) | `support` `holdings` (2) | **yes** — through the one renderer, `PatternChart` → `<BandStructureChip read={tile.band_structure}>`; when the name has no read at all these two also print the served no-read sentence (`chart_maps/api.py` → `board.py::band_structure_coverage` → `bounce_room.BAND_STRUCTURE_NO_READ`, the row boards' own wording — `SupportLevels.tsx` `data-testid="sl-band-structure-no-read"`, `HoldingsBoard.tsx` `bandNote`, per name) | n/a — one tile, nothing to order | **yes** — `SupportLevels.tsx` and `HoldingsBoard.tsx` both pass `bandStudy` and render the banner, positive **and** negative tests on each |
| row boards, own endpoints | `session` `hot_pullback` `patterns` `signals` `overnight` `hot_sectors` `bonde` `gnt` `growth` `catalysts` (10) | **yes** — `bounce_room.read_symbol` serves `row["band_structure"]` and all ten renderers mount the chip off that field | **no, deliberately** — ordering a row board is §10.7 and was not asked for; the `contracts.mjs` check named *"the 🪜 band-structure read: one ordering key, PROP-FED chips, no maths in the TSX"* FAILS a row board that imports `compareBandStructure` | in the chip **tooltip** (every mount passes `study={…band_structure_study}`), plus the served `band_structure_coverage.note` (`bounce_room.build_payload`, `BAND_STRUCTURE_NO_READ`) when not one row on the list came back with a read |

**All 26 tabs say something.** Twenty carry the read and the chip; the six
`n/a` tabs carry the served n/a sentence instead. The **ordering** exists on
**eight** — the tile-grid tabs whose `KIND_BY_TAB` kind is `demand` or
`supply_break`. Any sentence — here, in the ✨ label, or on a chip — that says
the ordering reaches "every Chart Maps tab" is false: the READ does, the ORDER
does not.

**One gap, and it is a rendering gap, not a serving one.** A name the zone store
does not carry — under `zone_store.MIN_CAP_USD`, or simply not warmed yet — gets
`band_structure: None` and the chip renders nothing. The ten
row boards and the two one-symbol views say so out loud (the
`BAND_STRUCTURE_NO_READ` sentence above). The **tile grid does not**:
`board.py` serves `band_structure_coverage` on every tile request, but
`ChartMaps.tsx` reads only `sort_unavailable` — so on those eight tabs the
"no band read for these names" line appears only when the 🪜 sort is actually
picked, and a default-sorted grid where nothing came back with a read still
shows blank chips with no reason. Rendering the served note there is a one-line
FE change and nobody has been asked for it; it is listed here rather than
claimed fixed.

`compareBandStructure` / `bandStructureOrderKey` / `bandStructureOrderUnavailable`
in `frontend/src/lib/bandStructure.ts` are mirrored against
`backend/tests/fixtures/band_structure_order_mirror_2026_09_16.json` and have
**no caller that orders anything**: outside its own test the only non-test file
that names them is `frontend/src/lib/bounceRoom.ts`, which **re-exports** them
(so every surface that already imports the bounce-room map gets them from one
place) and calls neither. That is not an unfinished edge any more: the contract
forbids the call on the ten row boards, so the key is pinned and idle until
§10.7 is answered.

### 5.1 The `n/a` tabs, by name

**`vcp`, `winners`, `topping`, `earnings`, `zero_dte`, `undervalue`.** Their rows
are pivots, ledger entries, lids, events, options and value screens — not names
standing at a demand band. A ceiling/floor ordering there would either blank the
tab or invent a band read that does not exist, so those tabs say **"no band read
for this tab"** and the 🪜 entry is not in their `sorts` list at all, exactly the
🎯 `n/a` precedent ([`enterable.md`](enterable.md) §4.3). **Never a fake ordering
on a tab that has no bands, and never a control that answers "not applicable"
when it is picked.**

His ask says *"where ever is applicable"* — this table is what "applicable"
means, and which tabs sit in which bucket stays his call (§10.6), moved with the
per-tab coverage numbers in hand, not by me.

### 5.2 The render paths, and WHERE the ordering runs

The tile grid and the row boards do not order the same way.

**Tile grid** (`ChartMaps.tsx`) — the **server** orders it, and **not inside
`_finish`**. The read keys on the LIVE print, which does not exist until
`attach_live_now` has run, and that runs after `_finish` has already sorted the
board on its default order and cut it to `limit`. So the ordering runs in
`board()`, **after the live overlay and after the cut**:

```
_finish(...)             default order (theme-first), cut to `limit`
attach_live_now(...)     the live print lands on the tiles
attach_enterable(...)    🎯, per tile, on that print
band_structure_study     the served verdict + kind — set FIRST, in its own try,
  + band_structure_kind  and the 🪜 entry dropped from `sorts` on an n/a tab
attach_band_structure()  🪜 read + stat, on that print — in the `else`, so a
                         chip can never outlive the banner that qualifies it
_band_structure_sort()   ONLY when out["sort"] == "band_structure"
```

**The rule that ordering has to obey, and the one the page has to state:**

> **It orders the tiles that reach the page. It never changes WHICH tiles reach
> the page.**

Picking 🪜 must re-rank the same set of names the board would have shown
anyway — the default theme-first cut — and nothing else. An ordering that also
re-cut the board would be a different top-N under the name of a sort, while the
payload's own note (`BAND_STRUCTURE_SORT_UNAVAILABLE` / `..._NA`, "the board is
showing its default order") said nothing had changed. That is why
`band_structure` must not be treated as an ordinary metric column by
`_finish`'s `_sort_key`: `tile_metrics` serves `"band_structure": None` for
every tile deliberately (the ceiling and the floor are two numbers, and
collapsing them into one sortable float would be the composite score this app
has not measured), and a null column must leave the default cut alone rather
than becoming an "explicit" sort that drops the theme ranking before the cut.
**This is what the backend does today** — `POST_CUT_SORTS = ("band_structure",)`
and `is_explicit_sort` keep the 🪜 key out of `_finish`'s pre-cut sort — and
`test_chart_maps.py` pins it: `?sort=band_structure` returns
the same tile SET as the default sort, in a different order.

The payload says which happened, on every request:

* `band_structure_scope` = `BOARD_SCOPE_NOTE` — "ordered on the tiles this page
  is showing … this ranks the page rather than the whole universe behind it";
* `sort_unavailable` = the n/a line on a tab with no band read, or the
  "no band read for these names" line when not one shown tile came back with a
  read — because a sort over an all-null column returns the served order, which
  looks like a working sort and is not one.

**Row boards** (`SessionBoard`, `HotPullbackBoard`, `PatternsPage`,
`SignalLabBoard`, `OvernightGappers`, `HottestSectors`, `BondeBoard`,
`GntBoard`, `ExplosiveGrowth`, `Catalysts`) — each renders from its own
endpoint, so the tile grid's server-side ordering cannot reach them. **They all
carry the READ** — `bounce_room.read_symbol` serves `row["band_structure"]` and
each renderer mounts the chip off that served field (§5.0) — **and none of them
ORDERS by it.** That is a decision, not a gap: ordering a row board is §10.7,
he did not ask for it, and the `contracts.mjs` 🪜 band-structure check
fails any of the ten that imports `compareBandStructure` or
`bandStructureOrderKey`.

If that call is ever answered yes, the ordering is the browser's job, off a
payload the page already has, the way `useExplosiveOrder` does it for 🧨 — a
hook, an opt-in toggle, no new fetch — using `compareBandStructure` so both
sides stay one ordering. **There is no `useBandStructureOrder` hook, and
`useExplosiveOrder` is the 🧨 hook, not this one.**

`HoldingsBoard` is a third shape and is easy to miscount: it is one
`/chart-maps/support` call per name he owns, so it gets the read, the chip and
the banner through `PatternChart`, while ordering there is a row-board question
like the rest.

The two paths are not interchangeable; the tile grid cannot reuse a row-board
hook, and a row board cannot reuse `?sort=`.

---

## 6. How it composes with 🎯 and 🧨

**The order is: SORT, then PARTITION.** That is already the contract and this
read does not change it.

* **🎯 ENTERABLE is a stable partition, not a sort.** `partitionEnterable`
  preserves the order the board chose and only moves hidden rows out, counting
  them. On the backend, `attach_enterable` runs after `attach_live_now`, after
  `_finish`'s sort and limit cut, on the tiles actually shown — and it runs
  *before* `_band_structure_sort` in `board()`, which changes nothing: the 🎯
  verdict is a per-tile field, so re-ordering the tiles carries it along. What
  reaches the browser is the band-structure order with each tile's verdict on
  it, and `partitionEnterable` then partitions **that** order. So the ordering
  runs **first** in the only sense that matters and the 🎯 filter runs on top of
  it unmodified. The ordering never un-hides a `BLOCKED` row and never hides one.
* **🧨 EXPLOSIVE is a sort, and so is this.** Two sorts cannot both be first.
  They are **alternatives on one control**, not layers: picking "thinnest ceiling
  first" replaces "🧨 Burst first", the way any two dropdown values replace each
  other. Whether the pair should instead compose (🧨 within ceiling buckets, or
  the reverse) is §10.5 — and any composition is a new ordering that has to be
  mirrored and pinned like the others, not a runtime toggle that quietly changes
  what the board means.
* **The chip is additive.** A tile can carry the 🧨 chip, the 🎯 verdict and the
  ceiling/floor line at once — they answer different questions (how far it can
  run, whether it can be entered, what is above and below it). The 🧨 chip's
  own banner rule applies here too: a served banner never hard-codes a measured
  figure in JSX.

---

## 7. The study — how to re-run it

`backend/scripts/band_structure_study.py`. Two questions, one replay, the
harness imported rather than rebuilt (`studies/bounce_quality_study.events`, the
helpers and the conditional-contrast machinery in `scripts/explosive_study.py`
and `scripts/entry_trigger_study.py`).

**Q1 — the ceiling.** Does a **thin first lid** predict clearing it (a close
above `lid.hi` within 20 sessions), measured **inside the 2026-09-07 distance
buckets**? (§2.3 — outside them it is re-measuring distance.)

**Q2 — the floor.** Does **layered support** predict surviving — fewer stop-outs
at the band floor, and +5% before the floor goes? `s5` read in **quantile** bins,
never hand-picked edges. The natural test is the episodes where price **closed
under band 1's low**: did the second band actually catch it?

Outcomes: clears-lid-20d · HIT5 from the print · stop-out at the band floor · R.

The rule of reading, throughout, is the one the last two studies shipped under:
date-clustered CI, date-block placebo, three out-of-sample splits, the minimum
detectable lift printed beside every claim, a one-per-date and one-per-symbol
reweight, a cell floor of 120 rows, and the survivorship replay on the cache
universe before any number is quotable. Ship-eligible means computable from
**served band fields at decision time** — no lookahead.

Smoke (never quotable, and every line says so):

```
docker exec -i cheetah-market-app-api-1 sh -c 'cat > /tmp/band_structure_study.py' < backend/scripts/band_structure_study.py
docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u /tmp/band_structure_study.py --stage both --universe broad --floor 120 --stride 18 --out /tmp/bs_smoke.csv --json /tmp/bs_smoke.json'
```

Full run — **never during RTH**, the hourly cache patch rewrites frames from
about 10:00 ET:

```
docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u /tmp/band_structure_study.py --stage replay --universe broad --floor 120 --out /tmp/bs_events.csv'
docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u /tmp/band_structure_study.py --stage replay --universe cache --floor 120 --out /tmp/bs_events_cache.csv'
docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u /tmp/band_structure_study.py --stage stats --from-csv /tmp/bs_events.csv --cache-csv /tmp/bs_events_cache.csv --json /tmp/bs_measured.json'
```

Copy the JSON **out** (never `docker cp` into `/app`):

```
docker exec -i cheetah-market-app-api-1 cat /tmp/bs_measured.json > band_structure_measured.json
```

Then paste it mechanically — the JSON beside the script, the `MEASURED` literal
in `band_structure.py`, the study's `RESULTS` docstring, §8 below and the ✨
label all come from one pass, and
`test_the_SHIPPED_JSON_and_the_MEASURED_literal_are_the_same_dict`
(`backend/tests/test_band_structure_2026_09_16.py`) fails on any drift, so **no
number here is ever typed by hand**. **That paste HAS run for the 2026-09-16
result** — §8.0.

---

## 8. MEASURED

**Run 2026-09-16 · status `no_signal` — on BOTH questions.** Every number below
is read out of `band_structure_measured.json` (the run's own output, `quotable:
true`, survivorship merged). Nothing in it is a point estimate without its CI.

**Neither of his two ideas separates.** A thin ceiling does not predict clearing
it, and a layered floor does not predict surviving. The one read that measures
**worse than the base** is the one his second ask asked for: a **bigger** first
support band. The ordering therefore stays DESCRIPTIVE (§1) and gates nothing.

### 8.0 Paste state — the run is IN the code

**Pasted and pinned.** `backend/scripts/band_structure_measured.json` ships
beside the study script, `band_structure.MEASURED` **is** that dict, and
`test_the_SHIPPED_JSON_and_the_MEASURED_literal_are_the_same_dict`
(`backend/tests/test_band_structure_2026_09_16.py`) fails on any drift between
the two. `band_structure.status()` returns **`no_signal`**, `SELECTED` is the
empty tuple, and every served string — the board banner, the chip tooltip, the
ℹ️ Rules line — is built out of that dict rather than typed, so no surface can
drift from this section without a test going red.

**One prose field in that file was corrected by hand on 2026-09-16** —
`q2.per_feature[sup_gap_pct].ship_eligible_reason` claimed the served read cuts
the band list at `price_zones.nearest_first(...)[:4]`, which §3 shows it does
not. Only that string changed; every number in the file is byte-identical and
the pin above still passes. The same stale sentence survives in the run's
`cap_note`, in `q2.capped_only.note` and in the other features' reasons because
it is emitted from `band_structure_study.CAP_NOTE`, so a re-run restores it —
fixing it for good is a one-line edit in the study script, not in the output.

**The resolution every surface quotes is 2.80 pp.** It is
`band_structure.binding_mdl()`: the **MAX over the three out-of-sample splits**
(s1 2.51 · s2 2.49 · s3 2.80), never split `s1`'s alone. Nothing was selected on
**all three**, so the binding number is the weakest split's — which is the run
file's own `q1.mdl`, 2.7950. Anything smaller than 2.80 pp is below what this
study could have seen, and no served line quotes a single split's figure.

### 8.1 The cohort and the base

| | value |
|---|---|
| cohort | 3,716 names · 158,327 events · 93,009 reversal events · **24,994 reversal episodes** · 362 dates · window **2025-03-10 → 2026-08-17** |
| episode rule | first per symbol + 20-bar cooldown; bands on CLOSED bars strictly before the print, board geometry; no costs; one regime |
| base | HIT5@20 **34.20 %** · stop@20 **74.48 %** · R20 mean +0.288, **median −1.00**, trimmed +0.068 · win@20 24.87 % · target/stop/clock 19/74/7 · room 15.63 % · risk 2.57 % |
| the lid leg's own base | **22,008** of the 24,994 episodes had a lid overhead (`base.n_lid`); the other 2,986 had clear runway and no lid at all (`base.clear_pct` **11.95 %** of the cohort — `clear` is `room is None`). Of the lid-bearing ones, **21.17 %** (`base.hit_lid_20`, a nanmean over the 22,008 — the run file's own denominator) REACHED the lid top before the stop within 20 sessions. Q1's own outcome is stricter — a CLOSE above the lid top — and the run file carries **no base rate for it**, so none is quoted here. CLEAR rows are UNDEFINED on the lid outcome, never failures |
| cell floor | 120 rows — a smaller cell is not shown |
| OOS splits | Q1 s1/s2/s3 — **NONE selected** on any (**per-split** MDL 2.51 / 2.49 / 2.80 pp) · Q2 s1/s2/s3 — **NONE selected** on any (**per-split** MDL 2.32 / 2.47 / 2.59 pp) |
| resolution | the **MAX** over the three splits, because nothing was selected on all three: **Q1 2.80 pp · Q2 2.59 pp**. `binding_mdl()` serves the 2.80 to every surface; no served line quotes one split's number. Nothing smaller than 2.80 pp is a finding here |
| survivorship | cache universe 5,284 names / 37,426 episodes · HIT5@20 32.73 % · stop@20 77.00 % · **Δ vs broad −1.46 pp**, so no survivorship bias is propping the null up |
| selected | **none**, either question | 
| quotable | true |

The rule of reading is the one the last two studies shipped under, applied
mechanically: a bucket "separates" only if the date-clustered 95 % CI excludes
0, the stop-out rate is not measurably raised, the bucket's room/risk is not
below the base's, its rate sits outside the date-block placebo band, the
(room × risk)-reweighted delta keeps its sign, and the one-per-DATE and
one-per-SYMBOL point estimates are both positive. Anything else is named
*inert* / *selects smaller trades* / *selects wider stops* / *harmful*.

### 8.2 Q1 — the thin ceiling. NOTHING selected

Q1's delta is on **that question's own outcome** — convention `CLEAR`, a close
strictly above the lid top within 20 sessions — not on HIT5. (The report labels
every delta column `ΔHIT5@20`; under `CLEAR` the column behind it is the
lid-clear one.)

| read | top bucket | n | Δ | 95 % CI | Δ stop | verdict |
|---|---|---|---|---|---|---|
| `lid_height_pct` — **his thinness read** | Q1, thinnest | 4,402 | **+6.65 pp** | [+5.40, +7.88] | +0.62 pp | **selects smaller trades** |
| `lid_strength` | Q1, weakest | 4,570 | +1.72 pp | [+0.28, +3.18] | +1.43 pp | inert |
| `lid_touches` | Q1, 1-touch (70.3 % of episodes) | 17,566 | +0.63 pp | [+0.30, +0.97] | +1.38 pp | inert |
| `lid_stack` | Q5, most walls | 4,456 | −0.04 pp | [−1.69, +1.67] | +0.54 pp | inert |
| `lid_dist_pct` — the CONTROL | Q1, nearest | 4,402 | +9.35 pp | [+7.97, +10.72] | −6.26 pp | selects smaller trades — **distance** |

**Why the thinnest bucket is not a finding even though its CI clears zero.** It
passes five of the six conditions — CI, stop-not-raised, the date placebo
([29.3, 35.2], it sits outside), the reweighted sign, and both one-per-date
(+4.42) and one-per-symbol (+16.63). It fails **room/risk**: 5.36 against the
base's 6.09. The thin-lid bucket is buying names with *less room per unit of
risk*, which is what "selects smaller trades" names. And the decision that
matters is the out-of-sample one: **all three splits selected nothing**, with a
resolution of 2.80 pp — so the in-sample contrast is not something the study is
willing to hand a board.

**Inside the 2026-09-07 distance buckets.** The study conditions the same
contrast **twice**, on the two distances the 09-07 work uses, both cut with
`lid_break.DIST_BUCKETS`:

| stratifier | what it measures | cells (n) | `lid_height_pct` conditioned | verdict |
|---|---|---|---|---|
| `lid_bucket` | print → lid.lo — the read a board has at decision time | ≤5 % **1** · 5–15 % 16,671 · >15 % 5,336 | **+6.10 pp [+4.89, +7.30]** | separates (in-sample) |
| `lid52_bucket` | lid.hi → the 52-week high — the 09-07 study's own cut | ≤5 % 1,843 · 5–15 % 1,488 · >15 % 9,481 | **+6.46 pp [+4.89, +8.12]** | separates (in-sample) |

Both survive conditioning, and neither is the largest contrast in the run — the
unconditioned thinness bucket (+6.65) and both distance controls (+9.35, +9.13)
are larger. Two things about the pair: under `lid_bucket` the **≤5 % cell has
n = 1** in this reversal cohort, so that pooled contrast is `5–15 %` + `>15 %`
only (a reversal off a demand band rarely has its lid within 5 % overhead). The
09-07 study's OWN cell is a different one and it is **not** missing here:
`lid52_bucket` is populated in all three. And on both stratifiers, the OOS
splits still selected nothing.

**`lid_dist_pct` is not a second finding.** The nearest-lid bucket separating is
the **2026-09-07 lid-break result restated** — DISTANCE decides — and it is
already on the board, in the stat sentence and in the standing proximity gate.
It is listed as a control for exactly this reason.

### 8.3 Q2 — the layered floor. NOTHING selected, and his read measures HARMFUL

Convention `P`; the delta is HIT5@20 on the 34.20 % base.

| read | top bucket | n | Δ HIT5@20 | 95 % CI | Δ stop@20 | verdict |
|---|---|---|---|---|---|---|
| `sup1_height_pct` — **"the support bands are bigger"** | Q5, **biggest** | 4,999 | **−4.01 pp** | [−5.20, −2.86] | **+4.32 pp** [+3.34, +5.28] | **harmful** |
| `sup1_strength` | Q1 | 5,538 | +0.94 pp | [−0.45, +2.36] | −3.80 pp | inert |
| `sup1_touches` | Q1, 1-touch (78.4 %) | 19,584 | +0.69 pp | [+0.36, +1.02] | +0.11 pp | selects wider stops |
| `sup1_volume` | Q1 | 4,999 | −0.55 pp | [−1.74, +0.64] | +0.30 pp | inert (and not served — §9.3) |
| `sup_gap_pct` — **"another one right below it"** | Q1, tightest gap | 4,318 | **−0.20 pp** | [−1.66, +1.25] | −3.36 pp [−4.69, −1.97] | inert |
| `sup1_dist_pct` — the CONTROL | Q5 | 4,999 | +9.13 pp | [+7.74, +10.55] | −8.86 pp | selects smaller trades — **distance** |
| `depth_q25` / `depth_q50` | Q1 | — | — | — | — | below the cell floor — not shown |
| `depth_q75` | Q1 | 23,563 | +0.37 pp | [+0.22, +0.52] | +0.06 pp | selects wider stops |

**A bigger first support band measures HARMFUL — the opposite of the
hypothesis.** The widest-band quintile takes **4.01 pp fewer** names to +5 %
before the floor and stops out **4.32 pp more often**, both CIs clear of zero,
permutation p = 1.000, and the point estimate stays negative under both the
one-per-date (−7.38) and one-per-symbol (−1.09) reweights. The same read under
the alternative `N` entry convention (open of the next bar, 22,950 episodes)
gives the same sign and the same verdict: **−3.38 pp [−4.59, −2.17]**, Δ stop
**+3.74 pp**, *harmful*. It is not an artefact of where the entry is taken.

**The gap read is inert, not harmful — and the one thing it does move is the
stop.** The tightest-gap quintile does cut stop-outs by **3.36 pp
[−4.69, −1.97]**, but it moves the primary outcome by −0.20 pp with a CI
straddling zero and sits **inside** the date placebo band, so the study names it
inert. A stop-out cut with no outcome lift is a smaller trade, not a better one.

The gap bins over the whole cohort, descriptive:

| gap bin | n | HIT5@20 | stop@20 | R20 | win@20 |
|---|---|---|---|---|---|
| Q1 tightest | 4,318 | 34.00 % | 71.12 % | +0.297 | 27.86 % |
| Q2 | 4,317 | 34.05 % | 72.37 % | +0.277 | 26.96 % |
| Q3 | 4,318 | 33.30 % | 74.29 % | +0.218 | 24.94 % |
| Q4 | 4,317 | 33.77 % | 74.77 % | +0.320 | 24.67 % |
| Q5 widest | 4,318 | 33.97 % | 79.71 % | +0.198 | 19.89 % |
| **no 2nd band** | 3,406 | **36.58 %** | 74.63 % | **+0.455** | 24.87 % |

Read the last row honestly: the names with **no second band at all** post the
best HIT5 (**36.58 %**) and the best R (**+0.455**) of the six cells — the
reverse of the layering idea. The run file carries **no room or risk figure for
that cell** (`q2.gap_bins` holds `n`, `hit5_20`, `stop_20`, `R20`,
`R20_median`, `win20` and nothing else), so the obvious confound — a name whose
first band is the lowest one on it has nothing underneath capping its room
either — is **stated, not quantified**, and must not be quoted as if the study
had measured it. `gap_pct` there is **undefined, never 0** (§9.6). It is
context, not a result.

**Cap control.** Restricted to the rows a CAPPED caller could see (the second
band inside `price_zones.nearest_first(...)[:4]` — not the served read, which
is uncapped), n 21,282, Δ −0.37 pp [−0.83, +0.08] — **inert**; 306 episodes
had a second band only outside that cut. On the path this read actually uses
the band list is **uncapped** (§3, and
`bounce_room.room_read` / `demand_read` read `doc["bands"]` directly), so the
cap control is a conservatism the study applied to itself, not the shipped
geometry.

### 8.4 The descriptive twin — and why it cannot rank anything in advance

Of the **18,135** episodes that closed **under** the first band, the share that
then held above the **next** one rises with the GAP, monotonically:

| gap bin | n under band 1 | held above band 2 |
|---|---|---|
| Q1 tightest | 3,019 | **34.45 %** |
| Q2 | 3,090 | 43.11 % |
| Q3 | 3,195 | 52.27 % |
| Q4 | 3,121 | 65.46 % |
| Q5 widest | 3,266 | **81.14 %** |
| no 2nd band | 2,444 | 0 answerable — "held" is UNDEFINED, never False |

This is the closest thing in the run to the shape his second ask describes, and
it is **not ship-eligible**. The study marks it `ship_eligible: false` for the
reason that decides it: **it conditions on a forward event.** The cohort is
"price already closed under band 1", which nothing on a board this morning
knows. A read that needs tomorrow's close to define its own population cannot
order tiles today.

It is also partly a definition rather than a finding — the further band 2 sits
below band 1, the more room price has to stop somewhere above it — and the
direction is the opposite of the ask anyway: he asked for the second band to be
**very close**, and the *tightest* gaps are where the second band held least
often (34.45 %).

### 8.5 What the run changes, and what it does not

* **The ordering stays DESCRIPTIVE.** No key was selected, so nothing moves onto
  a measured key. §1's sentence stands word for word.
* **Nothing becomes a gate.** No push, no lane, no sizing, no hiding — §1.
* **The only thing that separates on both halves is DISTANCE**, and that is the
  2026-09-07 lid-break finding restated, not a new one.
* **His second ask measures against him.** A bigger first band is worse, and the
  layered-floor gap is inert. That is worth saying to his face rather than
  burying: the descriptive order still puts the deepest floor first **because he
  asked for that order**, and the banner says it has not been shown to predict
  anything.
* **One regime, and a thin distance tail.** 362 dates on one tape, and under
  `lid_bucket` (print → lid) the **≤5 % cell is n = 1**, so the thinness
  question was never asked of a lid sitting just overhead. That is NOT the
  09-07 study's own cell: its cut is lid → 52-week high (`lid52_bucket`), which
  is fully populated here (1,843 / 1,488 / 9,481) and still selected nothing
  out of sample.

## 9. Limits

1. **Every CRDO band around his print is 1-touch.** The six demand bands from
   84.97 up through 161.92 that bracket his print in §4.1 — including the one
   price is standing in and his 149 — carry `touches == 1`, and so does the
   supply band the print is inside. A 1-touch band is a single swing low with a
   half-width drawn around it: it is a level that has been visited once, not a
   level that has been defended. `alert_gates.is_proven_band` (2+ touches and strength ≥ 40) exists
   precisely because those are different things, and the 2026-09-07 study found
   proven and single-touch lids indistinguishable for the carry question
   (§2.3). So his reference case is built on the weakest evidence a band can
   have, and any "layered floor" read on 1-touch bands is geometry, not history.
   The run split on it (§8): the 1-touch lid is **70.3 %** of the cohort's
   episodes and the 1-touch first demand band is **78.4 %**, and both buckets
   measured *inert* / *selects wider stops*. So the weakest evidence a band can
   have is also the modal case, and nothing separates on it either.
2. **Two geometries, on purpose.** The boards, alerts and lanes use the coarse
   board geometry (`zone_geom()`); the Support tab and per-ticker charts use the
   fine module defaults. They disagree by design and the disagreement was
   reconciled on 2026-09-14 by drawing the board band on every per-ticker view
   ([`zone_consistency` memory, `demand_reentry_methodology.md`](demand_reentry_methodology.md)).
   A ceiling/floor read must state which geometry it was computed on, on every
   surface, or the same name reads two ways.
3. **`zone_store._slim` drops fields.** The stored bands keep `kind, lo, hi,
   touches, strength` and sometimes `oldest_touch_bars` / `bars_since_test`;
   `mid`, **`volume`**, `touch_dates` and `in_price` are dropped. So `s4` (band
   volume) is **not** available from the stored doc — it is available only where
   `compute` is called live. Either the read drops `s4`, or the slim shape grows
   a field, and that is a schema change with its own work package. It is not
   silently recomputed.
4. **`strength` is relative, not absolute.** It normalises against the max
   touches and max volume **on that name**, so a strength of 80 on a quiet name
   and a strength of 80 on a heavy one are not the same wall. Cross-name
   ordering on `o2`/`s2` needs the study to say so, or it ranks names by their
   own internal spread.
5. **`s6` needs an N, and N is a quantile.** "How many bands within N% below the
   print" has no natural N. It was taken as a quantile of the cohort's own
   print-to-second-band span, computed by the run and never typed: **q25
   1.63 % · q50 4.08 % · q75 8.23 %**. Two of the three came back **below the
   cell floor** and are not shown; the third (`depth_q75`) measured *selects
   wider stops*. Nothing is served as a constant off the back of it.
6. **A `null` gap is a fact, not a window (§3).** On the shipped path the band
   list is uncapped (`max_zones=None`), so `gap_pct: null` means there is no
   second band under the first one — MTRX in §4.2 is that case, live. It must
   never be softened into "we only looked at four". The ambiguity this entry
   used to warn about exists only for a caller that takes `compute`'s default
   cap, and no such caller feeds this read.
7. **Closed bars.** Bands are computed on closed bars. The live print moves
   against a fixed structure during the session; the distances `o5`/`s7` move,
   the heights and the gap do not. The phantom pre-market echo bar and the
   container-UTC-vs-ET trap both apply
   ([`extended_hours.md`](extended_hours.md)).
8. **One regime, and a hole in the distance tail.** §8 is one tape's answer —
   **2025-03-10 → 2026-08-17**, 362 dates, with all three out-of-sample splits
   cut out of that same tape. And the `≤5 %` cell of `lid_bucket` — the
   print-to-lid distance, the read a board actually has — has **n = 1** in this
   reversal cohort, so the thinness question was never asked of a lid sitting
   just overhead. The 09-07 study's own cut (`lid52_bucket`, lid to the 52-week
   high) is populated in all three cells here; the two are different
   stratifiers and §8.2 quotes both.
9. **Coverage.** Bands exist for known-cap names plus on-demand builds; names
   with no cap have no bands at all, read unknown, and sort last. They are not
   "thin-ceilinged".

---

## 10. HIS CALLS — listed, not decided

1. **Which band is band 1 when the print is INSIDE a band** (the CRDO case,
   §4.1). **The code has already answered it: the CONTAINING band**, because
   band 1 is `bounce_room.demand_read` verbatim and that is what it returns
   (`in_band: true`, floor height 3.54%, the gap measured from its low). The open
   question is whether to CHANGE that to the first band strictly below — which
   would make CRDO's floor 3.20% wide and move the gap. His call; nothing should
   change it silently, because `demand_read` is the same selection the phone
   gates and the demand boards use.
2. **Whether a demand band ABOVE the print counts toward the ceiling stack**
   `o4` — CRDO has **five** (221.71, 207.80, 196.50, 182.61, 173.90). The code
   already counts them: `bounce_room.overhead_bands` treats a demand band price
   fell through as `broken_support` overhead. On CRDO none of them actually land
   in `walls_above` (4) because every one is 1-touch and unproven, so the name
   does not show what the choice costs. It is still a level price already lost
   rather than resistance proven from below, and the study can be run either
   way.
3. **The primary read — ANSWERED by the run, and the answer is "none".**
   Neither ceiling thinness nor the floor gap nor floor depth was selected on
   any of the six out-of-sample splits (§8), and the biggest first support band
   measured *harmful*. What is left for him is the label, not the key: keep the
   descriptive thinnest-ceiling / deepest-floor order because he asked for it
   (the shipped default), or drop the ordering and keep only the chip. Both are
   honest; the ordering claims nothing either way.
4. **The label.** "Band structure", "thin ceiling", "room above / catch below" —
   and the chip's exact sentence.
5. **Whether this ordering and 🧨 should compose** (one inside the other) or
   stay alternatives on the same dropdown (§6).
6. **Which tabs are applicable** — the `KIND_BY_TAB` buckets in §5 are inherited
   from the 🎯 read, and moving a tab between `demand` and `n/a` is his, with
   the coverage numbers in hand.
7. **Whether the row boards get the ordering ON by default** or behind the
   opt-in toggle, as 🧨 is.
8. **Whether a FUTURE read sourced from the capped lists may raise `max_zones`
   at its own call site** (§3). Moot for this read — it sees the uncapped stored
   bands — but it is the rule anybody wiring the row boards has to follow rather
   than reaching for `MAX_ZONES_PER_SIDE`.
9. **Whether the ceiling half should keep IGNORING an unproven band the print is
   sitting in** (§4.1, point 2). `ceiling_read` inherits
   `bounce_room.room_read`, which skips bands under
   `alert_gates.LID_MIN_TOUCHES` — the KLAC rule, and it is fail-CLOSED for a
   push (don't hold a name back for a wall nobody tested). Used as a RANK it
   fails the other way: on 2026-09-16 CRDO's print sits inside 1-touch supply at
   161.92–167.68 and the served ceiling is the 193.50 band 18.9% up.

   **What is already DONE, so it is not part of this call:** the skipped band is
   served beside the answer (`untested_band`, `untested_distance_pct`,
   `in_untested_band`) and named in the stat sentence, and the ℹ️ Rules panel's
   FLOOR bullet states the asymmetry in so many words — the floor half applies
   **no** proven-lid filter, so one stat line can legitimately call the same
   price range untested overhead and a floor 3.5% wide
   (`rules_info._band_structure_section`, built from `AG.LID_MIN_TOUCHES`).

   **What is still open is where the untested group SITS IN THE KEY. Today:
   FIRST.** `CEILING_GROUP_UNTESTED = 0.0` against
   `CEILING_GROUP_READABLE = 1.0` in `band_structure.py`, so a name with
   nothing proven overhead leads the board, ahead of every name whose ceiling
   somebody actually measured. That is the shipped default and it is the only
   judgement in the whole ordering. Whether a rank should (a) leave it there or
   (b) put the untested group **behind** every readable ceiling — give
   `CEILING_GROUP_UNTESTED` a value above `CEILING_GROUP_READABLE`, nothing else
   in the key moves, and the mirror fixture pins whichever he picks — is
   **his**, and nothing here should be read as having decided it.
