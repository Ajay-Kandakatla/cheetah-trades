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
* **A break stays a break until the market ANSWERS it.** A close under the floor
  is old structure only when a *later* close sits at least `MIN_RISE_ABOVE_PCT`
  (5%) above the band top — the same bar the re-entry itself has to clear. Until
  2026-09-05 the scan was scoped to "after the last close above the band", which
  let a single poke over the top re-arm a broken band (section 4).

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

Read that column carefully: it is the **deepest close below the floor since price
last left the band**, not where the stock trades today. SWKS is the extreme case
and worth spelling out, because "18%" invites the wrong reading —

```
2026-06-26  broke the 68.98–71.56 band
2026-07-14  bottomed at a 56.58 close      ← 17.98% under the floor
2026-08-14  back to 69.62, inside the band ← +23% off the low
```

It is not sitting 18% underwater. It **fell 18% through the band and has rallied
all the way back into it** — which is exactly why the old code liked it and why
the guard is the right call anyway. A band that failed by 18% and has been
reclaimed on the fourth day is a level price is fighting over, and
`price_zones` independently reads that overlap as **AT_SUPPLY**.

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

## 4. A whipsaw poke over the top does not un-break the band

S/D zone review, 2026-09-05. Ajay: *"yes please fix the bugs"*.

The old scan looked for closes under the floor only **after the last close above
the band**, so that a break from before the run-up would read as old structure.
The justification in section 1 — *"the market already answered it by rallying
5%+ through the whole band since"* — was never checked. One close a hair over
the top was enough:

```
band 100–104, forty closes
[112]*10 + [106]*19 + [101] + [97]*4 + [104.2] + [102]*5      last 102

before   is_reentry True   broke_below False   fell_from_pct 7.7   bars_since_above 5
after    is_reentry False  broke_below True    fell_from_pct 0.2   bars_since_break 6
```

Four closes 3% under the floor, one 104.2 close against a 104 top, back inside —
and the row read *"back in demand after running +7.7% above it"* with a Buy/Stop.
The +7.7% belonged to the leg **before** the break; the NBIX failure mode with
one extra day tacked on.

Two rules replace the scoping, both in `_break_scan` (one walk, shared by
`reentry_read` and the new `band_break_read`):

* **Answered, not visited.** A break is dropped only when a later close is at
  least `min_rise_pct` (`MIN_RISE_ABOVE_PCT` = 5%, the existing constant) above
  the band top. `[97]*4 + [110]*5 + [102]` against a 104 top qualifies (110/104
  = +5.8%); `104 × 1.049` does not. Live breaks drive `broke_below`,
  `bars_since_break` and `lowest_close_pct_below` — an answered 5% break followed
  by a fresh 3% one reports **3%**, the structure being traded now.
* **`fell_from_pct` is the leg AFTER the last break, never the whole window.**
  For a name back inside its band that is the rebound since the last close under
  the floor (the whole window when it never broke). NBIX's read moved from +5.3
  (the run to 163.50 *before* the 150.82 close) to **−1.7**: the 152.72 rebound
  never got back over the 155.30 top. For a name still **under** its floor —
  deep_demand's top band — it is the run-up that led into the current break.

Also fixed in the same pass, same module:

| finding | before | after |
|---|---|---|
| two price bases in `decide_from_frame` | membership on the 2dp `last_price`, `reentry_read` on raw closes → a close 0.4c over the top was INSIDE and ABOVE at once (`bars_since_above 0`) | closes rounded to 2dp — the basis every other number in the record already used |
| `top_band_read` always empty | `reentry_read` returns the empty shape outside the band, and it was only asked when price was BELOW → deep_demand's `bars_since_top_break` / `fell_from_pct` dead on every row | `band_break_read` (no in-band requirement); `bars_since_top_break` = age of the FIRST close under the top band |
| target label on the OB reads | `trade_levels` says "next supply band" for any opposing band | `_label_target_kind`: a demand-kind band overhead prints **"broken demand band overhead"**; `trade_plan`'s docstring now says "first band of either origin" like the math always did |

---

## Where the honesty is enforced

| Decision | Guard |
|---|---|
| A close below the floor refuses the re-entry | `test_a_close_below_the_floor_disqualifies_the_reentry` |
| The real NBIX bars are refused | `test_the_real_NBIX_case_is_refused` |
| …and were refused by **this** guard, not another gate | `test_NBIX_would_still_have_qualified_without_the_break` |
| A close exactly on the floor is a test, not a break | `test_a_close_exactly_ON_the_floor_is_not_a_break` |
| An old break from before the run-up still qualifies | `test_a_break_from_BEFORE_the_run_up_is_old_structure_and_still_qualifies` |
| …but only when a later close cleared the top by 5% | `test_a_break_ANSWERED_by_a_min_rise_rally_is_old_structure_and_still_qualifies` |
| One poke over the top does not re-arm a broken band | `test_a_whipsaw_poke_over_the_top_does_not_reset_the_broken_band_guard` |
| `fell_from_pct` is the leg after the last break | `test_fell_from_pct_describes_the_leg_AFTER_the_last_break_not_the_whole_window` |
| Only unanswered breaks set the depth | `test_only_the_UNANSWERED_breaks_count_toward_the_deepest_close` |
| The answer rule is the 5% constant, not a visit | `test_reentry_fix_a_break_is_answered_only_by_a_MIN_RISE_close_above_the_top` |
| One scan behind both reads | `test_reentry_fix_reentry_read_and_band_break_read_share_ONE_scan` |
| One 2dp price basis in `decide_from_frame` | `test_decide_from_frame_uses_ONE_price_basis_for_membership_and_the_reentry_read` |
| `top_band_read` carries data below the band | `test_top_band_read_carries_break_evidence_for_a_name_below_its_first_band` |
| A demand band overhead is labelled as one | `test_ob_reads_label_a_demand_kind_overhead_target_by_its_origin` |
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
