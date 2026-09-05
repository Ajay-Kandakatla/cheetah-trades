# Support Levels — one ticker, on demand, at a chosen zoom

Ajay 2026-08-19:

> *"Can you help me with a new feature where I can look at support levels on
> demand may be a new tab in the chart maps. Where I can toggle a drop down to
> check montly vs 3 months vs 6 months demand zones please. I should be able to
> a search of all the Ticker I do today and then drop down or something to check
> supports... I want look at recent support levels as well."*

Code: `backend/chart_maps/support.py`, read at `GET /chart-maps/support`.
Zones from `supply_demand/price_zones.py` (new `lookback_bars` knob).
FE: `frontend/src/components/SupportLevels.tsx`,
`frontend/src/lib/supportLevels.ts`, tab registered in `lib/chartMaps.ts`.
Tests: `backend/tests/test_chart_maps_support.py` (48),
`backend/tests/test_price_zones.py` (+7),
`frontend/src/lib/supportLevels.test.ts` (33),
`frontend/src/components/SupportLevels.test.tsx` (14).

---

## 1. Not a book method, and it says so

`price_zones` opens with the line that governs this whole feature:

> a **PRAGMATIC** price-structure read, **not** a named book methodology — every
> threshold below is a CONFIGURED house value.

No Minervini page backs a single number here and none is cited. Nothing in the
SEPA engine reads this tab. It is decision support for a stop, not a signal.

## 2. Why a new zoom knob instead of a new module

`price_zones` has only ever answered at 252 bars. That is the right lookback for
*"where is the structural floor"* and the wrong one for *"where is support for
the trade I'm in this week"* — a level turned at four times in the last three
weeks does not survive a year-long clustering pass, it gets merged into whatever
larger band contains it.

So the dropdown drives `compute(lookback_bars=…)` and **nothing else about the
rule changes**. Two knobs move, and only two:

| knob | 1M | 3M | 6M | 1Y |
|---|---|---|---|---|
| `bars` | 21 | 63 | 126 | 252 |
| `swing_window` | 2 | 3 | 4 | 4 |

`swing_window` **has** to move. At the module default of 4 a swing low must be
the lowest of nine consecutive bars; over a 21-bar month that is 43% of the
entire window, and the shortest option would return one band or none. Scaling it
holds swing *density* roughly constant, which is what makes the four views
comparable at all.

`merge_pct` and `half_width_pct` are deliberately **left alone**. Widening the
bands at short zooms was the obvious next move and it is wrong: the four views
would then differ for three reasons at once, and "why does 1M disagree with 6M"
would have no answer. One rule, four zooms, one explanation.

**1Y is not in the request.** It is offered because `/supply-demand/price-zones`
and the /zones page both read 252 bars, and a tab that could not reproduce their
answer would look like it *disagreed* with them rather than zoomed differently.

## 3. The floor had to move with the window

`compute` gated on a 60-bar frame. A 21-bar month cannot clear that, so before
this change the dropdown's first option could only ever have returned `None` —
which the UI would have rendered as "no structure found".

```
need = MIN_BARS (60)                         when lookback_bars is not passed
need = max(MIN_BARS_ABS (12), 2*w + 3)       when it is
```

The conditional is the point: **every pre-existing caller passes no window**, so
the /zones page, `orderflow.signals`, `sd_sweep`, `sd_backtest`, `sd_bounce` and
`demand_reentry` are byte-for-byte unaffected. `2w + 3` is the smallest frame
that can hold a swing at all — `_local_extrema` scans `range(w, n - w)` and
compares `w` bars either side.

## 4. Position decides the column, not origin

`price_zones` keeps the supply/demand label for **colour**. Broken support
trades as resistance and reclaimed resistance trades as support, so the table
splits by where a band sits relative to price, and carries the origin as
evidence (`· was resistance`) rather than as the sort.

`nearest_support` is merged into the pool explicitly. It is computed over
**every** band while the returned lists keep only the strongest four per side, so
building the table from the lists alone could put a top row on screen that
disagreed with the verdict's own `support_pct`.

## 5. What the live smoke test changed

The synthetic fixture proved the zoom works. Running it against real tickers
found something the fixture could not:

| ticker | zoom | nearest support | touches |
|---|---|---|---|
| NVDA | 1m / 3m / 6m | 214.90–217.50, **0.03% below price** | **1** |
| BRKR | 1m / 3m / 6m | every listed level | **1** |
| DHI | 6m | 146.97–148.75, 2.05% below | **1** |

A one-touch "band" is a single swing low with `half_width_pct` of synthetic
width painted around it — the weakest evidence the clustering pass can emit. On
a short frame it is also the **commonest**, because 21 bars rarely contain two
turns at the same price. Nearest-first sorting therefore promoted noise to the
top row on almost every read, and NVDA's "support" was functionally *yesterday's
low*.

They are still shown — a recent swing low **is** where the next bid sat, and
filtering them would empty the short windows. They are **labelled**:

* `MIN_TOUCHES_TESTED = 2` → per-level `tested` flag
* table prints `1 touch · single low`, at lower contrast
* the headline appends *"Single swing low, not a tested floor."*
* the stats separate **touched in last month** from **turned at more than once**

That separation is the honest one, because neither implies the other: a level
touched yesterday once is recent and untested; one turned at four times last
year is tested and stale.

After the change, DHI at 6M reads correctly — nearest is a 1-touch low at 2.05%,
but the real floor is the **4×-tested** band at 4.41%. That is the read that
was previously buried.

## 6. Where the honesty is enforced

| Decision | Guard |
|---|---|
| The zoom actually changes the answer | `test_a_one_month_read_finds_the_RECENT_floor_and_not_the_old_one`, `test_a_six_month_read_reaches_the_DEEPER_floor`, `test_the_two_zooms_disagree_on_purpose` |
| A short window is reachable at all | `test_the_shortest_window_is_actually_reachable` (regression) |
| Existing callers are untouched | `test_the_default_lookback_is_unchanged_and_still_gated_at_60_bars`, `test_price_zones_globals_are_untouched_by_this_module` |
| Only two knobs vary | `test_the_band_geometry_knobs_are_deliberately_NOT_varied_per_window` |
| A short frame is declared, not mislabelled | `test_a_frame_shorter_than_the_window_is_ANSWERED_but_declared` |
| The chart shows what was read | `test_the_chart_shows_the_bars_actually_read_not_the_bars_requested` |
| A single low is not a floor | `test_a_single_touch_band_is_flagged_as_NOT_tested`, `test_the_why_line_says_so_when_the_nearest_support_is_one_touch` |
| …but is still listed | `test_a_single_touch_level_is_STILL_listed_not_filtered_away` |
| Polarity, not origin, picks the column | `test_a_broken_supply_band_below_price_is_listed_as_SUPPORT` |
| The table cannot contradict the verdict | `test_the_nearest_support_is_never_dropped_by_the_strength_cap` |
| Recency is a flag, never the ordering | `test_recency_is_a_FLAG_not_an_ordering` |
| Distance is to the edge price touches | `test_distance_is_measured_to_the_EDGE_price_touches_not_the_midpoint` |
| No universe scan behind a page load | `test_this_module_never_scans_a_universe` |
| Tile helpers reused, not reimplemented | `test_it_reuses_the_boards_tile_helpers_rather_than_reimplementing_them` |
| A miss keeps the controls usable | `test_an_unknown_ticker_answers_an_error_not_an_exception`, `keeps the zoom dropdown usable after a miss` |
| Never prints NaN | `never prints NaN when the backend omits a distance` |

## 7. Known limits

* **Bands are capped at four per origin** by `price_zones.MAX_ZONES_PER_SIDE`,
  so the table sees at most eight candidates below price. `levels_capped` says
  when more structure existed than was listed.
* **`strength` is relative to the other bands in the same window.** It is not
  comparable across zooms and is deliberately not surfaced in the table.
* **No stop rule is computed.** Placing a stop is methodology, `demand_reentry`
  already owns that question, and inventing a second rule here would be a drift
  with no source behind it. The band's low is printed; the stop is the reader's.
* **Nothing feeds back.** No scan, no alert, no ledger reads this tab.

## Stale-response race (fixed 2026-08-31)

Ajay: "The months at the bottom do not change when I try to change to 1
year from 6 months." A cold window computes for ~5s (measured on GEV)
while a warm one answers in ~50ms, so the request you switched AWAY from
routinely resolved last and repainted the old bars under the new dropdown
value. Fix: a request sequence counter — whoever asked last owns the
screen; late responses are dropped, in-flight fetches aborted on switch.
The same guard now protects the Chart Maps board fetch (tab/phase/target
flips) and the Session board (a quiet poll could overwrite a timeframe
switch). A switch over an existing chart also now says "updating the
view…" instead of looking dead while a cold window computes.
Regression tests are mutation-verified: removing either guard fails
SupportLevels.test.tsx / SessionBoard.test.tsx.

## Live view (2026-09-02)

The Chart control's Intraday group gained **"5 min · live · pre/post market"**:
the overnight tape (shaded) drawn against the 6-month daily levels, a `● LIVE`
chip with the session state and as-of time, quiet 30-second re-reads while the
extended session is open, and a one-line 🌙 overnight read ("broke support
$198.80–$201.20 at 16:30; bounced off support $184.75–$186.98 at 17:35 ✓").
Method and contracts: `timeframes_orb_fvg.md` → *Live frame*.

## 2026-09-05 — structure off the closed frame (Ajay: *"yes please fix the bugs"*)

The tab computes its swings, fair value gaps and ATR on the frame **without** today's live
bar (`_frame_for(sym, bars, with_closed=True)` returns both; on an intraday timeframe the
`partial` last bucket is dropped the same way) and still **prices** the levels at the live
print (`pz.compute(closed, last_price=live_last, ...)`). Before this a displacement bar plus
the live bar printed a demand FVG whose top was the live bar's low-so-far, and a partial-day
true range leaked into the ATR the entry/stop buffer is scaled by. Same rule as
`price_zones.for_symbol` (`price_zones_methodology.md` → 2026-09-05). Test:
`test_chart_maps_support.py::test_the_support_tab_reads_structure_off_the_closed_frame_not_the_live_bar`.
