# The reward:risk floor — and the three filters that failed first

Ajay 2026-08-17, on SWKS:

> *"is it a falling knife? Its volume is high but are the sellers winning may be
> add another layer to this to check Buyers in control stocks only as an
> additional filter?"*

He got the filter he asked for measured, three ways. **All three failed.** What
shipped instead is the defect the measurement turned up on the way past.

Code: `backend/supply_demand/demand_reentry.py`, `backend/supply_demand/api.py`,
`frontend/src/components/DemandReentryPanel.tsx`.
Tests: `backend/tests/test_demand_reentry.py` (+15),
`backend/tests/test_supply_demand_contracts.py` (+5).

---

## 1. The premise, checked first

Two of his three assumptions about SWKS did not hold:

| claim | measured |
|---|---|
| "is it a falling knife?" | **No.** Swing lows step UP (55.42 → 57.50). The 50-day IS falling (−3.16%/10 bars), but the guard needs both. |
| "its volume is high" | **No.** 20-bar dollar volume **1.03×** its own base; 5-day rvol **0.73** — three-quarters of normal. |
| something new was needed to catch it | **No.** SWKS reads `zone_broken=True` — that morning's guard already removed it. |

The busy-looking tape was one 17M-share bar on 07-29, three weeks stale.

## 2. Three candidates, three failures

Each designed through a different lens, each swept over its own threshold range
on **737 walk-forward observations** (300 S&P names by dollar volume, decision
days 2025-07-08 → 2026-08-14).

| lens | verdict |
|---|---|
| net dollar-volume pressure | *"does not earn its place at any parameter value"* — an early n=115 result inverted at n=737 |
| effort-vs-result (high volume, no progress) | *"does not earn a place at any parameter value"* |
| structure / overhead-supply ceiling | best cell moves exSPY −0.219% → +0.013% while deleting **40% of the board**; family-wise p = **0.2107** |

An adversarial pass then re-derived everything independently and killed all
three jointly:

* **Joint family-wise p = 0.76.** ~1,000 threshold cells were searched across the
  program; ~50 clear α=0.05 by chance. The best observed result is *worse than
  what noise typically produces*.
* **Both holdouts fail in one direction.** The "optimal" threshold moves from
  −0.20 to +0.35 depending on which half you look at.
* **They agree on 3 of 680 rows (0.4%).** Pairwise Jaccard 0.06–0.20. Three
  designs produced three unrelated splits and each named it "buyers in control".
* On the live board they **contradict**: one deletes HOOD (strongest structure
  there), another keeps HOOD and deletes the top two rows.

No lookahead was found — the `_upto` firewall held, and a sentinel confirmed the
scores change on 93.6% of rows when the slice grows.

## 3. What the measurement actually found

> **131 of 363 backtested wins (36%) resolved on the ENTRY BAR**, median planned
> R:R **0.45**.

Those are plans whose "target" already sat inside the entry day's range. Strip
them from the unfiltered board:

```
                raced   win%    exp%     exSPY%   medRR
all               680   53.4   +0.02    -0.219    0.94
minus 0-bar wins  549   42.3   -0.29    -0.586    1.06
```

The board's headline +0.02% expectancy is carried by 0.45R hops. That is a
problem of **trade construction**, not of stock selection, and no buyers-in-control
layer touches it.

## 4. The floor — and why it is 1.0, not the best cell

```
floor    raced  win%   exp%    exSPY%   medRR   0-bar wins
none       680  53.4   +0.02   -0.219    0.94   131
>=0.50     524  46.2   +0.06   -0.238    1.24    59
>=0.75     423  41.4   +0.02   -0.268    1.53    37
>=1.00     326  39.9   +0.17   -0.101    1.87    27
>=1.25     257  37.4   +0.29   -0.003    2.18    16
>=1.50     215  32.6   +0.15   -0.247    2.35    12
>=1.75     179  31.8   +0.23   -0.167    2.55     9
>=2.00     147  31.3   +0.20   -0.170    2.91     8
>=2.50      95  31.6   +0.62   +0.034    3.26     3
>=3.00      66  28.8   +0.55   -0.169    3.69     2
```

**1.25 is the best exSPY cell and is deliberately NOT the default.**

Read the exSPY column down: −0.238, −0.268, −0.101, **−0.003**, −0.247, −0.167,
−0.170, +0.034, −0.169. **Four of eight steps move the wrong way.** It is not a
gradient; it is a zigzag with a high point. Choosing that high point is precisely
the in-sample fitting that disqualified the three candidates above, and applying
a stricter standard to them than to this would be dishonest.

*(An earlier agent pass claimed this sweep "at least moves in a straight line."
It does not. That claim was checked and is wrong.)*

**What IS monotone is the column that describes the defect** — 0-bar wins:
131 → 59 → 37 → 27 → 16 → 12 → 9 → 8 → 3 → 2. Every step. That is mechanical,
not statistical: a higher floor cannot help but remove targets that sit inside
the entry bar.

So the default is justified by **trade construction**: a plan that risks more
than its first objective pays is not a trade, whatever a 13.5-month sample says.
`MIN_RR_DEFAULT = 1.0` is what that sentence implies, and it needs no backtest.

### Honest limits

* **No floor makes this board beat SPY on this sample.** Unfiltered is −0.219%;
  the best cell reaches −0.003%. The floor removes bad construction; it does not
  manufacture an edge.
* **The window is 13.5 months of one bull tape, not 5 years.** `zone_backtest.run`
  reports `period="5y"` but `prices.load_prices` serves a ~500-bar cache and
  ignores the argument. The decision-day span is the honest number.
* **Survivorship.** The universe is *today's* liquid S&P names, so delisted
  tickers are absent and every figure above is biased upward.

## 5. Design decisions

| decision | why |
|---|---|
| Filters the **board**, never `is_reentry` | `is_reentry` answers the STRUCTURAL question. R:R is a fact about the plan. Folding them together makes one field mean two things — and blinds the walk-forward to the unfiltered cohort the 0.45R finding came from. |
| Applied at **read** time, not inside `scan` | One 3-hour cache entry per universe instead of one per floor value, and moving the dropdown is instant rather than a fresh 3-minute pass. |
| An **unknown** R:R fails a real floor | `rr` is None when no supply band sits above the entry band, so there is no objective to measure — and the backtest skips those rows, so there is no evidence either way. Same rule as the chart-maps liquidity tier. |
| `min_rr=0` turns it **off** | It is a house value on a board he trades daily, not a law. |
| A `bool` is rejected | `True >= 1.0` is True in Python; scoring an upstream bug as a 1.0R plan would hide it. |

Effect on the 2026-08-14 board: of 9 rows, **TJX (1.85) · IDXX (1.73) ·
HOOD (1.58) · HRL (1.08) · NKE (1.02)** stay; **MSCI (0.71) · AIG (0.40) ·
WRB (0.22) · DUK (0.16)** come off. DUK was risking six dollars to make one.

---

## Where the honesty is enforced

| Decision | Guard |
|---|---|
| A sub-1R plan fails | `test_a_plan_that_pays_less_than_it_risks_fails_the_floor` |
| Unknown R:R fails a real floor | `test_an_UNCOMPUTABLE_rr_fails_a_real_floor` |
| 0 is off and passes everything | `test_a_floor_of_zero_is_OFF_and_passes_everything` |
| A bool is not a ratio | `test_a_bool_is_not_a_reward_risk_ratio` |
| The default is not the fitted peak | `test_the_floor_default_is_the_TRADE_CONSTRUCTION_line_not_the_fitted_peak`, `test_the_documented_default_is_not_the_backtests_best_cell` |
| Omitting the param applies the default | `test_min_rr_None_means_APPLY_THE_DEFAULT_not_no_floor` |
| It reports what it removed | `test_the_filter_reports_what_it_removed_rather_than_just_shrinking` |
| It never reorders survivors | `test_the_floor_never_reorders_the_rows_it_keeps` |
| Read-time, so the cache is not fragmented | `test_the_filter_is_applied_at_READ_time_so_the_cache_is_not_fragmented` |
| It never touches `is_reentry` | `test_the_floor_does_not_touch_is_reentry`, `test_the_floor_filters_the_BOARD_and_never_the_structural_read` |

---

## 6. The room floor, and the target above the PRINT (2026-09-05)

Ajay, TRU on the Back-in-Demand board:

> *"It already gapped up very close to the resistance. Why is it still in in
> Demand page? There is only 0.5% room"*

and, the same morning:

> *"I need the same logic in Demand and deep demand zone. So that there are
> stocks that have more room atleast >5%"*

**Measured.** The scan's demand band 78.34–81.08 *contained* a supply band
80.12–82.10. `trade_plan` targeted 83.87 — the first band above the **entry
band's top** — so the plan read **1.47R** and cleared the floor. From the
79.88 print the first band overhead was 80.12: **0.3% of room, 0.09R.** The
R:R floor did exactly what section 4 says it does; it was handed the wrong
target.

### Two changes, both owner settings (S&D scope, no book cite)

| | before | after |
|---|---|---|
| target | low of the first band with `lo > max(entry_hi, print)` | low of the first **unbroken** band above the **print** (`alert_gates.first_overhead`: supply with `hi >= print` not broken under `prev_close`, plus demand with `lo > print`), the entry band excluded **by identity** |
| print inside that band | impossible by construction | `rr` **0.0**, `reward_pct` 0 — the floor removes it |
| room | not read | every row (and deep row) carries `room` from the **live** print; rows under `min_room` are dropped like the R:R floor drops |

`MIN_ROOM_DEFAULT` is **imported** from `alert_gates.ALERT_MIN_ROOM_PCT` (5.0,
his *"atleast 5% to Supply"*), so the phone and the boards can never disagree
on the number (`test_room_floor_default_IS_the_alert_gate_number_imported_not_
retyped`). `min_room=0` turns it off. `CLEAR` (nothing overhead) passes;
`IN_BAND` fails; an uncomputable room fails a real floor — the same rule as an
unknown R:R, for the same reason.

TRU under the new rules: target 80.12, `rr` ≈ 0.14 → **off the board on the R:R
floor alone**; room 0.3% (`NEAR`) → off it again on the room floor.

### What deliberately did NOT change

* `MIN_RR_DEFAULT` and everything in sections 1–5. The floor was right; the
  target was wrong.
* `is_reentry`. Room, like R:R, is a fact about the **plan**, applied at read
  time (`test_room_floor_is_read_time_like_the_rr_floor_and_the_routes_take_
  min_room`).
* Callers that read the cache without asking for the room layer (`chart_maps`,
  `signal_watch`, `trade_flash`) see the rows they always did; the Chart Maps
  zones and deep-demand boards apply their own floor on their own live print
  (`docs/sepa/chart_maps_sort.md`, update 2026-09-05).

### Honest limits

* The room is read on the **live print** when the tape has one and on the
  **scan** price otherwise, and each row says which (`room.basis`). A closed
  market reads the scan basis — the number Ajay saw on TRU was a live gap the
  16:55 scan never had.
* The broken-supply rule needs a prior close. Live: the snapshot's
  `prev_day_close`, else the scan's last close; scan basis: the record's own
  `prev_close`, which rows cached before 2026-09-05 lack — those count every
  supply band overhead, the conservative side.
* **The boundary is compared raw, shown rounded** (review 2026-09-05). `room_pct`
  is 1 dp for the card; the `ROOM`/`NEAR` split, `meets_room_floor` and the FE's
  `roomOk` compare `room_pct_raw` (new key on the room block and on
  `alert_gates.room_read`). 4.995% shows "+5.0%" and is `NEAR`, dropped on the
  boards and refused by the phone alike — `test_room_block_boundary_4_995_is_
  NEAR_and_fails_the_floor_like_the_phone`, `test_boundary_4_995_pct_rounds_to_
  5_0_but_FAILS_and_says_so_raw`. The same test found that `alert_gates.room_gate`
  rebuilt its pct from a cents-rounded target (104.995 → 105.00) and passed
  4.995%; it now compares the unrounded value. Refusal texts quote 2 dp.
* **`rr_at_entry_high` is clamped at 0.0** when the target sits under the entry
  band's top (possible now that the target is measured above the print — TRU:
  target 80.12, band top 81.08); `target_basis` appends "no reward left at the
  band top". Never a negative R on a card; the FE's `rrAtEntryHigh` guards a
  cached plan that still carries the sign.

### Where it shows (frontend, 2026-09-05)

* Back in Demand (`DemandReentryPanel`): a **Room floor** selector — `🧱 Room ≥
  5% (default)` / `🧱 any room` — sent as `min_room` on the read and the scan;
  the count line adds "N hidden: room < 5%"; each row prints the server's room
  block (`→ $80` target, band kind in the tooltip, "· scan close" when the
  basis is the scan) with `⛔ into supply` on every **measured** read under the
  floor. Exactly two states; a third number would be one Ajay did not give.
* Chart Maps zones + deep_demand: a `Room ≥ 5%` / `Any room` control inside the
  phase toggle (URL `room=any` only when off), "N hidden: room < 5%" note, and
  the tile stat `room: +12.4% -> 84.10` / `open sky` / `in band`.
* The plan line names the target's band kind — `Target $80.12 (+0.3%, supply
  band)` (`zonePlan.planLine`).
* `lib/bounceRoom.ts`: `ROOM_MIN_PCT = 5` (mirror of `ALERT_MIN_ROOM_PCT`),
  `roomOk` / `intoSupply` / `roomGroup` compare `room_pct_raw` when present and
  honour a server `NEAR` verdict; `compareBounceRoom` sorts bouncing-with-room,
  room-ok, bouncing-into-supply (⛔), rest.
* Nothing here is an edge claim. This removes plans whose first objective is
  already behind or on top of the print; it does not make the board beat SPY
  (section 4, "Honest limits", still stands).

| Decision | Guard |
|---|---|
| TRU targets 80.12 and fails the floor | `test_tru_the_target_is_the_first_band_above_the_PRINT_not_above_the_entry_band_top` |
| A print inside the first overhead band is 0R, not "no target" | `test_a_print_INSIDE_an_overhead_band_has_zero_reward_and_fails_the_floor` |
| Broken supply (closed above yesterday) is not a target | `test_a_supply_band_yesterday_CLOSED_above_is_broken_and_is_not_a_target` |
| VRT still holds (own band never the target) | `test_the_entry_band_itself_is_never_the_target_even_from_below` |
| The floor drops 0.3%, keeps CLEAR and 8% | `test_the_room_floor_drops_tru_keeps_clear_and_8_pct_and_reports_it` |
| 0 is off, None is the default | `test_min_room_zero_is_OFF_and_min_room_None_means_the_default` |
| Live first, scan as the fallback, cached rows never mutated | `test_attach_room_measures_from_the_live_print_and_says_so`, `test_attach_room_falls_back_to_the_scan_price_when_the_tape_has_nothing` |
| Deep rows measure to their broken first band | `test_attach_room_covers_deep_rows_against_their_SECOND_band` |
| Legacy cache readers are untouched | `test_cached_or_warm_applies_the_room_floor_only_when_asked` |
| The number is the alert number, imported | `test_room_floor_default_IS_the_alert_gate_number_imported_not_retyped` |
