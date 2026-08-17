# The broken-band guard — a demand zone that failed is not a buy

Ajay 2026-08-17, on NBIX:

> *"There are two different buys in the NBIX stock one on chart, We fell below
> the demand zone but you still say buy in one place."*

Two separate defects, one report. Both are fixed here.

Code: `backend/supply_demand/demand_reentry.py`, `frontend/src/lib/zoneChart.ts`,
`frontend/src/lib/zonePlan.ts`.
Tests: `backend/tests/test_demand_reentry.py` (+32),
`backend/tests/test_supply_demand_contracts.py` (new, 15),
`frontend/src/lib/zoneChart.test.ts` (+11), `frontend/src/lib/zonePlan.test.ts` (+13).

Configured price-structure method — NOT a book method, NOT advice. Every
threshold below is a house value with no page cite.

---

## 1. The bug: `in_band` only ever looked at the last price

`reentry_read`'s own docstring said it:

> *"Requires price to be INSIDE the band now — a name below the floor has broken
> support, which is the opposite of this signal."*

The code checked `zone_lo <= last_price <= zone_hi` and nothing else. A name that
fell through the floor, **closed** under it, and bounced back the next session
satisfies that test perfectly.

NBIX, entry band **$152.54–155.30** (3× tested, strength 45):

```
2026-08-11  O 165.46  H 165.46  L 161.78  C 161.94    above the band
2026-08-12  O 159.74  H 159.98  L 154.86  C 156.49    above the band
2026-08-13  O 154.43  H 155.81  L 150.20  C 150.82  ← CLOSED below the floor
2026-08-14  O 149.72  H 153.42  L 148.78  C 152.72    back inside
```

Every other gate passed — in the band, not a falling knife, 3 touches, strength
45, ran +19.4% above the band inside the lookback. Measured on the real frame:

```
in_demand_band True   trend_ok True   zone_quality_ok True   is_knife False
fell_from_pct 19.4    bars_since_above 2    → is_reentry True
```

So the board said **back in demand · support is right here · entry favorable**
and quoted Buy $152.54–155.30 / Stop $150.25 / 2.0R.

### The rule now

A bar that **CLOSES** below the floor breaks the band, and a broken band cannot
be a re-entry:

```python
out["is_reentry"] = bool(rise >= min_rise_pct and above_idx
                         and not out["broke_below"])
```

Three decisions inside that:

* **Closes, not lows.** Wicking through a band is how demand zones get *tested*
  in the first place. Failing on a wick would reject the healthy case this signal
  exists to find. A close is the market's closing judgement on the level.
* **Strictly below.** A close exactly on the floor is a successful test, not a
  break. `<`, not `<=` — otherwise every zone that ever got tested disqualifies.
* **Scoped to after the last visit above the band.** A close under the floor from
  *before* the run-up is old structure, and the market already answered it by
  rallying 5%+ through the whole band since.

Bouncing back above a floor does not un-break it. It makes the band a level being
fought over, not a floor to lean on.

### Measured effect on the live board

Full S&P 500 sweep, 497 frames, 2026-08-17:

| | count |
|---|---|
| rows that stay | **9** — AIG, DUK, HOOD, HRL, IDXX, MSCI, NKE, TJX, WRB |
| rows removed as broken | **8** |

Nearly half the board. What came off, and how far under the floor each one
actually closed:

| symbol | broke | deepest close under the floor |
|---|---|---|
| **SWKS** | 3d ago | **17.98%** |
| LNT | 1d ago | 3.37% |
| KHC | 2d ago | 2.54% |
| DTE | 1d ago | 2.03% |
| TDG | 2d ago | 1.61% |
| BXP | 2d ago | 0.76% |
| AEP | 3d ago | 0.73% |
| VMC | 1d ago | 0.15% |

SWKS was reading as "back in demand" 18% below the band it had supposedly
returned to.

NBIX itself is not in the cached S&P 500 constituent list, so it reaches the
board through the sp1500 layer; on its own frame it now reads
`zone_broken True · is_reentry False`.

---

## 2. A stop the market had already run

Same report, second defect. The plan quoted **Stop $150.25** on 2026-08-14 — the
session NBIX printed a **$148.78 low**. That plan was stopped out before it was
written.

`trade_plan` now takes `recent_lows` and reports:

```
stop_recently_hit  True
bars_since_stop_hit  0        (today)
lowest_low_pct_below_stop  0.98
```

This one **warns, it does not gate** — deliberately, and the asymmetry is pinned
by `test_the_already_run_stop_WARNS_and_never_gates`. A broken band invalidates
the *zone*, which is the thing the board screens on. An already-run stop is a
fact about the *plan*; the name may still be worth watching with the caveat
attached, and that is Ajay's call rather than the scanner's.

| | broken band | already-run stop |
|---|---|---|
| evidence | **closes** — did support fail? | **lows** — would I still be in this trade? |
| wicks | ignored (a wick is a test) | counted (a wick fills a resting order) |
| window | since price last left the band above | `STOP_HIT_LOOKBACK_BARS` = **10** |
| effect | gates `is_reentry` | annotates the plan |

Two house values behind that: strictly-below on the stop too (a $98.50 stop is
not guaranteed a fill on a $98.50 print), and a two-trading-week window — a stop
taken out three months ago, against a band rebuilt and retested since, is stale
news, while one taken out in the last few sessions describes the structure being
traded right now.

`stop_recently_hit` is **`None` when it was not checked** (an older cached
payload, or a caller with no bar history), `False` only when it was checked and
came back clean. Rendering the first as the second puts a green tick on a plan
nobody verified.

---

## 3. "Two different buys ... one on chart"

`planLines()` labelled **both edges** of the entry band:

```
BUY $155.30
BUY $152.54
```

Two prices under the same word, which reads as two competing entries rather than
one range. Worse, it was pure duplication: the entry band is already outlined on
both edges by `zoneBandsPrimitive`. The price line exists for its **axis label**,
and one label carries the whole range:

```
BUY $152.54–$155.30
```

Anchored at the band **top**, not the floor — the floor sits ~1.5% above the stop
and the two axis labels would land on the same pixels.

### And a broken band never says BUY

Three surfaces stopped claiming it:

| surface | before | after |
|---|---|---|
| chart price line | `BUY $152.54–$155.30` (green, solid) | `BROKEN $152.54–$155.30` (grey, dashed) |
| chart band fill | strong fill + outline (`isEntry`) | ordinary demand band, unadvertised |
| plan line | `Buy $152.54–$155.30 · Stop $150.25 · …` | `Zone BROKEN — … failed on a close below the floor.` |
| verdict | `AT_DEMAND` / 🟢 favorable | `DEMAND_BROKEN` / 🟠 caution |
| why-line | *"Sitting in the band, but it never left it"* | *"…it BROKE first — a close below $152.54 yesterday (closed 1.13% under it)"* |

The `verdict` downgrade happens in `demand_reentry._verdict_after_break`, **not**
in `price_zones`. That split is the point and is guarded by
`test_price_zones_stays_a_pure_SNAPSHOT_with_no_break_history`:

* `price_zones._verdict` answers *"where is price relative to the bands today"*.
  It has no history, and for price inside a demand band the honest snapshot
  answer really is AT_DEMAND.
* Giving it history would make every `/zones` read, every `/chart-maps` tile and
  the stocks screen depend on the re-entry rules.

Only `AT_DEMAND` is ever rewritten. The other states never claimed support.

### Known boundary, deliberately left

The standalone **`/zones` page** (`GET /supply-demand/price-zones/{symbol}`) goes
straight to `price_zones.for_symbol` and does **not** get the downgrade. It will
still read "In a demand zone — support is right here" on a band that broke. That
page is a pure snapshot by contract; wiring the transition read into it is a
separate change to a surface Ajay did not report, and it is one function call
whenever he wants it.

---

## Where the honesty is enforced

| Decision | Guard |
|---|---|
| A close below the floor refuses the re-entry | `test_a_close_below_the_floor_disqualifies_the_reentry` |
| The real NBIX bars are refused | `test_the_real_NBIX_case_is_refused` |
| …and were refused by **this** guard, not another gate | `test_NBIX_would_still_have_qualified_without_the_break` |
| A close exactly on the floor is a test, not a break | `test_a_close_exactly_ON_the_floor_is_not_a_break` |
| An old break from before the run-up still qualifies | `test_a_break_from_BEFORE_the_run_up_is_old_structure_and_still_qualifies` |
| The break is reported even when it is the refusal reason | `test_the_break_evidence_is_reported_even_though_the_row_is_refused` |
| Break keys exist on every return path | `test_the_break_fields_exist_on_every_return_path` |
| The band check reads closes, the stop check reads lows | `test_the_stop_check_is_fed_LOWS_and_the_band_check_is_fed_CLOSES` |
| An unchecked stop reports None, never False | `test_an_UNCHECKED_stop_reports_None_not_False` |
| The stop-hit flag never moves the stop | `test_the_stop_check_never_changes_the_stop_itself` |
| The stop-hit flag warns and never gates | `test_the_already_run_stop_WARNS_and_never_gates` |
| One BUY line, not two | `draws ONE buy line carrying the whole band…` |
| A broken band never renders BUY | `a band that BROKE never says BUY` |
| A broken band loses its entry highlight | `stops highlighting it as the ENTRY band on the chart` |
| An older payload without the flag is unaffected | `only a literal true breaks it — undefined and false do not` |
| `price_zones` stays a snapshot | `test_price_zones_stays_a_pure_SNAPSHOT_with_no_break_history` |
| Only AT_DEMAND is downgraded | `test_the_downgrade_only_ever_touches_AT_DEMAND` |
