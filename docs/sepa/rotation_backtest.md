# Sector rotation — does acting on it pay?

**Answer: no.** Over 116 monthly rebalances back to 2016, buying the three
leading sectors returned **158.22%** against **163.23%** for simply holding all
eleven. The ranking lost to doing nothing.

Ajay 2026-08-16: *"Yes also back test and add the rotation tracker"* — asked
after the tracker showed money leaving his build-out themes for healthcare,
banks and then energy. The tracker measures what **already** moved. This is the
only question that matters for using it.

Not a book method. Nothing in Minervini prescribes a sector-rotation rule; this
is our own construction, tested so the page can say what it is worth.

Code: `backend/rotation/backtest.py`.
Tests: `backend/tests/test_rotation_backtest.py` (17).
Served at `GET /rotation/backtest`, rendered as the verdict banner on `/rotation`.

---

## The rule under test

| | |
|---|---|
| Universe | the 11 GICS sector ETFs — XLK XLV XLF XLE XLI XLY XLP XLU XLB XLRE XLC |
| Rank by | trailing 63-day return **minus the benchmark's**, on bars up to and including the decision bar |
| Hold | top 3, equal weight |
| Rebalance | every 21 trading days (~monthly) |
| Entry / exit | the **next session's open**, both sides |
| Cost | 2 bps per side, charged on the fraction of the book that actually turned over |
| Benchmark | **RSP** (equal-weight S&P), with SPY reported beside it |

### Why relative ranking, not absolute

In a falling market every sector has a negative trailing return, and an absolute
rank still buys the least-bad three. That is a different — and worse — strategy
than owning the leaders. `rank_at()` subtracts the benchmark's return over the
same window, so a sector that falls less than the benchmark scores positive.
Guarded by `test_ranking_is_relative_to_the_benchmark_not_absolute`.

### Why RSP and not SPY

A rule holding 3 of 11 equally-weighted sleeves is structurally closer to
equal-weight than to cap-weight. Benchmarking it against SPY would credit the
rule with equal-weight's spread, which it did not earn. SPY is reported because
it is the number everyone quotes, not because it is the fair comparison.
Guarded by `test_the_benchmark_is_equal_weight`.

---

## Ten years, not one regime

`prices.load_prices` serves a 500-bar cache and its `period` argument is a
**no-op** — that is what silently limited the demand-zone backtest to 13
bull-market months before it was caught. `force=True` bypasses the cache and
returns ~2,510 bars back to 2016. Thirteen ETFs is a small enough refetch to do
properly.

The window therefore covers the 2018 Q4 selloff, the 2020 COVID crash and the
2022 bear as well as three bull runs. **A momentum rule measured only in a bull
market has not been measured.** Guarded by
`test_the_backtest_forces_a_full_refetch`, which asserts `force=True` is still
in `run()`.

Every frame is reindexed onto the benchmark's calendar and forward-filled, so a
positional index means the same date for every symbol. A sector missing a bar
the benchmark has would otherwise shift its whole return series by one day.

---

## No-lookahead firewall

1. Ranking for rebalance bar `i` uses returns computed from bars **up to and
   including `i`**, nothing after.
2. The position is entered at the **next** session's open and held to the open of
   the next rebalance. You cannot rank on a close and also trade that close.
3. The benchmark and the all-11 sleeve are bought and sold on exactly the same
   bars, so date-alignment slippage cannot favour either side.
4. Costs are charged on every rebalance, both sides.

`test_ranking_uses_only_bars_up_to_the_rebalance` inserts a 5x spike **after**
the decision bar and asserts the ranking is byte-identical.
`test_sleeve_return_is_open_to_open` pins entry to the open by making the close
of the same bar wildly different (100 → 999 close, 120 open; the measured return
must be 20%).

---

## Result

Measured 2026-08-16, span **2016-11-21 → 2026-07-06**, 116 rebalances:

| | total |
|---|---|
| Top-3 rotation | **158.22%** |
| RSP equal-weight | 155.42% |
| **Holding all 11 sectors** | **163.23%** |

| | |
|---|---|
| Mean excess per period | **−0.013%** |
| 95% interval | **[−0.549, +0.522]** — straddles zero |
| Beat RSP | 51.7% of months (a coin flip) |
| Average turnover | 0.43 of the book per rebalance |

Two readings matter and they agree:

* The interval **straddles zero**, so the +2.8pp of compounded outperformance
  over RSP is a sample, not an edge.
* The do-nothing alternative — holding all 11 sectors, rebalanced on the same
  dates — **beat the rule outright**. Whatever the ranking is doing, it is
  subtracting value net of turnover.

### By year — one regime nearly carried it

| year | strategy | RSP | excess |
|---|---|---|---|
| 2016 (2) | +2.97% | +3.22% | −0.16pp |
| 2017 | +22.26% | +21.38% | +0.81pp |
| 2018 | −7.96% | −7.64% | −1.47pp |
| 2019 | +8.75% | +16.57% | **−7.09pp** |
| 2020 | +15.90% | +14.70% | −0.50pp |
| 2021 | +13.25% | +15.37% | −1.61pp |
| 2022 | +6.28% | −1.25% | **+7.58pp** |
| 2023 | +18.07% | +4.79% | **+11.38pp** |
| 2024 | +18.35% | +15.57% | +2.20pp |
| 2025 | −1.28% | +8.72% | **−9.47pp** |
| 2026 (6) | +6.50% | +10.06% | −3.21pp |

**Six of eleven years are negative.** Essentially all of the rule's lifetime
excess comes from 2022–2023 — the energy-leadership bear and the year the
ranking happened to sit in tech. Strip those two years and the rule is behind in
every remaining regime but one. `test_by_year_splits_so_one_regime_cannot_carry_the_result`
exists so nobody can quietly drop this table.

---

## What this does and does not license

**Licensed.** Reading `/rotation` as a description of what already moved — which
groups are leading, which have turned, whether money is hiding in defensives.
That is measurement, and it is accurate.

**Not licensed.** Treating the top of that table as a shopping list. The banner
on the page says so in one sentence, sourced from this run, because a ranked
table reads as a recommendation unless the evidence sits next to it.

The tracker was built to describe, not predict. That is a fine thing for it to
be — but only if the page says which one it is.

---

## Honest limits

* **One rule, one parameter set.** 63-day lookback, 21-day rebalance, top 3. A
  grid search over those three knobs would find a combination that "works", and
  it would be curve-fitting on 116 observations. Not doing that is the point.
* **116 observations is not many.** The interval is wide *because* the sample is
  small; this measures "no detectable edge", not "proven to be worthless".
* **Sector ETFs only.** No survivorship problem (all 11 are still listed), but
  also no stock-level selection — this tests the rotation decision, not the
  scanner that picks names inside a sector.
* **Cost is a flat 2 bps/side.** Generous for these ETFs. Real slippage on a
  large book would make the result worse, not better.
* **Refetches on a cold cache**, ~5s. Endpoint caches for 12 hours; the answer
  moves on the scale of months.

## Where the honesty is enforced

| Decision | Guard |
|---|---|
| Relative, not absolute, ranking | `test_ranking_is_relative_to_the_benchmark_not_absolute` |
| RSP is the benchmark | `test_the_benchmark_is_equal_weight` |
| Full history, not the 500-bar cache | `test_the_backtest_forces_a_full_refetch` |
| No lookahead | `test_ranking_uses_only_bars_up_to_the_rebalance` |
| Entry at the next open | `test_sleeve_return_is_open_to_open` |
| Do-nothing line always reported | `test_the_do_nothing_alternative_is_always_reported` |
| Interval spanning zero stays visible | `test_the_interval_straddling_zero_is_reported` |
| Compounding, not summation | `test_compounding_is_not_summation` |
| Per-year breakdown survives | `test_by_year_splits_so_one_regime_cannot_carry_the_result` |
| Banner drops the edge claim when the CI straddles zero | `frontend/src/lib/rotation.test.ts` → `isEdgeSayable` |

See also: [`rotation_tracker`](../../backend/rotation/tracker.py) for the
measurement itself, and
[`../supply_demand/zone_backtest.md`](../supply_demand/zone_backtest.md) — the
demand-zone backtest, which reached the same verdict (no edge) by a different
route, and whose 500-bar cache trap is why this one forces a full refetch.
