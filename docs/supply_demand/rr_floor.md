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
