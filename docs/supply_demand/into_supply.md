# Into Supply — Back in Demand, upside down

Ajay 2026-08-20:

> *"Now in inversely give me a tab that are in or about to be in supply zones
> please..."*

Code: `backend/supply_demand/into_supply.py`, attached inside
`demand_reentry.decide_from_frame`, collected by `demand_reentry.scan`, read at
`GET /chart-maps?tab=supply` via `chart_maps/board.py::supply_tiles`.
Tests: `backend/tests/test_into_supply.py` (45),
`frontend/src/lib/chartMaps.test.ts` (+5).

---

## 1. What it is for

Not a short list. Ajay trades long. Three questions:

| situation | what the board says |
|---|---|
| about to buy this | you are buying directly under a lid |
| already hold it | this is where the advance is most likely to stall |
| waiting for an entry | the clean entry is **after** it clears, not here |

The DHI read on 2026-08-19 is the case that motivated it: overhead supply
$151.87–$152.74 **at price**, three times tested, nearest support 2% below and
the only real floor 4.4% below. Everything needed to see that was already being
computed and thrown away.

## 2. It rides the demand pass — it does not scan

`scan()` already calls `analyze_symbol` on every name (~1,600 frames, ~3
minutes) and keeps only rows where `is_reentry` is true. Every discarded record
already held `supply_zones`, `nearest_resistance`, `nearest_support` and the
structure read.

So this module **never loads a price**. It is a second predicate over the same
record in the same loop. Two consequences, and the second is the important one:

* the tab costs a page load, not a second three-minute pass
* the two boards **cannot disagree** about a name's bands, because they read one
  computation from one moment

`supply_rows` is a separate key on the cached payload, so `rows` and every
consumer of it — the page, the R:R floor, the limit, the history ledger — is
untouched by construction. Pinned by
`test_the_rr_floor_and_limit_do_not_touch_the_supply_rows`.

The attach inside `decide_from_frame` is wrapped in `try/except` with a `None`
fallback. The demand board is what he trades from every day; a defect in the
newer, secondary read must never be able to take it down.

## 3. One scale, not a second one

Every threshold is imported, never re-declared:

| knob | value | borrowed from |
|---|---|---|
| `MIN_RUN_UP_PCT` | 5.0 | `demand_reentry.MIN_RISE_ABOVE_PCT` |
| `LOOKBACK_BARS` | 40 | `demand_reentry.REENTRY_LOOKBACK_BARS` |
| touches / strength | 2 / 40 | `demand_reentry.MIN_TOUCHES` / `MIN_ZONE_STRENGTH` |
| `NEAR_CEILING_PCT` | 3.0 | `price_zones.NEAR_PCT` (its own `INTO_SUPPLY`) |

`test_the_two_boards_share_ONE_scale` fails if someone forks them.

## 4. The mirror, and the two subtle rules that come with it

`supply_read` is line-for-line the inverse of `reentry_read`, including both of
its non-obvious guards, because the failures they were written for are
symmetric:

* **Only CLOSES count.** An intraday wick into overhead supply is how a ceiling
  gets tested; failing on a wick would reject the ordinary case.

* **The broken-band guard, inverted.** `reentry_read` refuses a floor price has
  CLOSED beneath — the market rejected that support. Here, a band price has
  CLOSED above is no longer a ceiling: that is a breakout, and the band has
  become support. Without this, every successful breakout retest would be
  flagged as a warning. Verified live on NVDA (2026-08-20), which closed above
  its 212.19–216.82 band and came back — correctly refused.

**Percentages do not mirror, and asserting they did was my error.**
`fell_from_pct` measures against the band HIGH and `run_up_pct` against the band
LOW, so one 14-dollar excursion reads 13.5% from 104 and 14.0% from 100. The
verdicts mirror exactly; only the distance in *dollars* reflects. The test now
asserts the quantity that actually holds.

## 5. Room up:down

The one number worth reading:

```
room_ratio = distance to the ceiling ÷ distance to the next support
```

Under 1.00 means more air below than above. **It is NOT a trade reward:risk** —
there is no stop here and this module never proposes one. It is the asymmetry
of the two nearest structural levels, which is the thing that was invisible on
DHI: 0.01% of room above and 2.05% below is a 0.005 ratio, and no amount of a
good-looking base changes that arithmetic.

A name *inside* its ceiling has zero room up, so the ratio is 0.00 by
construction. `to_clear_pct` is reported separately for that case: how much
further before it is clear of the band entirely.

No support below means **no ratio**, not a fabricated one — the row still
publishes, because the ceiling is still real.

## 6. Measured on the live universe, 2026-08-20

| symbol | state | ceiling | run-up | support below | ratio | on the board |
|---|---|---|---|---|---|---|
| BRKR | NEAR | 61.21–63.04, 2× | 17.8% | 5.3% | 0.31 | **yes** |
| ABBV | AT | 260.96–267.47, 3× | 6.8% | 6.2% | 0.00 | **yes** |
| MOS | AT | 22.74–23.55, 5× | 9.2% | 8.1% | 0.00 | **yes** |
| NVDA | AT | 212.19–216.82, 4× | 10.5% | 2.0% | — | no — closed above it |
| META | AT | 520.26–540.18, 3× | −3.6% | — | — | no — fell in from above |
| DHI | AT | 148.22–152.74, 3× | **4.1%** | 0.1% | — | no — under the 5% bar |

BRKR and ABBV were two of the seven names the SEPA scan called **buyable** on
2026-08-19.

**DHI misses by 0.9 points** and is deliberately not rescued. The run-up bar
exists to separate *arriving at* a ceiling from *chopping around* a level, and
lowering it to admit the one example that motivated the feature is the same
in-sample fitting the R:R floor comment refuses to do. It is stated here so the
tension is visible rather than buried.

## 6b. The ordering, and the bug that only real data showed

The first `sort_key` led on `distance_pct`, then `room_ratio`. Both are **0.0
for every name already inside its ceiling** — which on the S&P 500 was all 40 of
the AT rows. Both keys degenerated, the tie-break fell through to the symbol,
and the board opened **ABBV / ACN / AJG / AON**. An alphabetical caution list is
worse than no list, because it looks ranked.

The order is now a lexicographic tuple, deliberately not a weighted score:

1. inside the band before approaching it
2. **most air beneath first** — the key that actually separates the AT rows
3. hardest lid first (touches)
4. symbol, only for stability

`supply_tiles` turns that ranking into `_score` by **position**
(`float(len(rows) - rank)`), so a four-part ordering is never squashed into one
number with invented weights. There is exactly one definition of "most urgent".

Same universe, after the fix:

| | air below | lid |
|---|---|---|
| FANG | 10.5% | 4× |
| TRMB | 8.4% | 2× |
| UBER | 8.2% | 6× |
| MOS | 7.7% | 5× |
| CRM | 7.0% | 2× |

**104 of 498 S&P names (21%) are into supply.** That is a real reading of a tape
near its highs, not a loose filter — the demand board returned 21 the same pass.
The board shows the worst 24; `matched` states the rest.

## 7. Where the honesty is enforced

| Decision | Guard |
|---|---|
| A rally into the band qualifies | `test_a_rally_up_into_the_band_is_into_supply` |
| "About to be in" is real | `test_price_just_UNDER_the_band_is_about_to_be_in_it` |
| A breakout is not a lid | `test_a_band_price_has_CLOSED_above_is_no_longer_a_ceiling` |
| Chop is not an approach | `test_a_band_price_only_HOVERED_around_is_not_an_approach` |
| The mirror stays a mirror | `test_the_two_reads_are_mirrors_on_the_same_geometry` |
| One scale for both boards | `test_the_two_boards_share_ONE_scale` |
| Truncated lists cannot hide the lid | `test_nearest_resistance_leads_because_the_lists_are_TRUNCATED` |
| Broken support above = ceiling | `test_a_broken_SUPPORT_band_above_price_counts_as_a_ceiling` |
| One touch is not a lid | `test_an_untested_band_is_not_published_as_a_ceiling` |
| No support ⇒ no ratio | `test_no_support_below_means_no_ratio_rather_than_a_fake_one` |
| It never scans | `test_this_module_never_loads_a_price_or_runs_a_scan` |
| One loop, one `analyze_symbol` | `test_the_scan_collects_both_boards_in_ONE_loop` |
| The demand board cannot break | `test_the_supply_read_can_never_break_the_demand_board` |
| `decide_from_frame` stays pure | `test_decide_from_frame_stays_pure_after_the_addition` |
| No plan lines on the tiles | `test_the_tiles_draw_NO_plan_lines` |
| The tab keeps its own disclaimer | `test_the_tab_keeps_its_OWN_disclaimer` |
| The board is not alphabetical | `test_REGRESSION_a_board_of_AT_rows_is_not_sorted_alphabetically` |
| Most air beneath leads | `test_most_air_beneath_ranks_first` |
| Missing data sorts LAST | `test_a_row_with_no_supply_block_sorts_LAST_not_first` |
| One ordering definition | `test_the_board_score_reproduces_the_sort_key_by_POSITION` |

## 8. Known limits

* **It inherits the demand scan's universe and cadence.** If the demand cache is
  cold, this tab warms with it and says so.
* **No backtest.** `zone_backtest` scores the demand rule; nothing has measured
  whether "runs into a tested ceiling" predicts a stall. It is a structural
  observation, not a measured edge, and the disclaimer says so.
* **Not a book method.** `price_zones` says so in its own header; no page is
  cited because none backs it.
