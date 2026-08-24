# 0DTE — same-day options, as a decision board

Ajay 2026-08-24:

> *"I need a new tab for ODTE type of options calls. Where its short or
> calling.. but like day trade. Quick return type of trading.. Can you help
> please.. **Look to see of we have all the data for this**.. Create a TAB for
> options in chart maps and put two categories. May be use the supply and demand
> data points but also look for other data point you need for this setup becuz I
> think this will require a lot of accuracy and much better data like order book
> or so to some degree"*

He then chose, explicitly:

* **two categories = calls and puts**, inside a pinned/unpinned banner
* **suggest a strike AND record every call**, so it earns a track record

Code: `backend/options/zero_dte.py`, `backend/options/zero_dte_history.py`,
read at `GET /chart-maps?tab=zero_dte` via `chart_maps/board.py::zero_dte_tiles`.
Tests: `backend/tests/test_zero_dte.py` (58),
`frontend/src/lib/chartMaps.test.ts` (+5),
`frontend/src/components/PatternChart.test.tsx` (+4).

**Not a book method.** Nothing in Minervini covers 0DTE. No page is cited
because none applies.

---

## 1. The data audit he asked for, first

It ran before a line of the module was written, and it decided the design.

### Have (verified live 2026-08-24)

| | |
|---|---|
| Same-day chains | real — SPY had 358 contracts expiring that day |
| `expiration_date` filter | confirmed honoured (NVDA/TSLA/AAPL/MU/AVGO all returned only 2026-08-24) |
| Freshness | `"timeframe": "REAL-TIME"` on both `last_quote` and `last_trade` |
| Per contract | delta, gamma, theta, vega, IV, open interest, day volume/VWAP |
| Quote | NBBO top of book, with bid/ask SIZES and exchange ids |
| Dealer gamma | already computed by `options/opex.py` — walls, max pain, flip |
| History | 4,163 daily GEX snapshots since 2026-07-06 |

Of 18 liquid names probed, **13 had a same-day chain**; PLTR, SMCI, COIN, MSTR
and NFLX did not. That list is `UNIVERSE`.

### Do NOT have — and it shaped everything

* **Order-book DEPTH.** He asked for this specifically. Massive sells top of
  book; there is no level 2 for options on this plan. Every cost number here is
  NBBO plus the size at the touch, and the module says so rather than implying
  more.
* **Intraday option price history.** So a 0DTE rule **cannot be backtested**.
  Not "has not been" — cannot be. `zone_backtest` scores the demand rule because
  daily equity bars go back years; the equivalent tape for a same-day chain does
  not exist here.
* Therefore **no measured edge**. Every threshold is a house value.

That third point is the entire reason he was offered the ledger, and the reason
he took it. A track record cannot be looked up here. It can only be accrued.

## 2. The two numbers that must appear together

Measured on SPY's own 0DTE chain at the close, spot 763.71:

| strike | bid | ask | spread% | delta | theta | day volume |
|---|---|---|---|---|---|---|
| 763 | 0.68 | 0.76 | 11.1 | 0.623 | −1.65 | 369,356 |
| 764 | 0.09 | 0.10 | 10.5 | 0.214 | −0.78 | 808,305 |
| 765 | 0.01 | 0.02 | **66.7** | 0.039 | −0.26 | 828,288 |
| 766 | 0.00 | 0.01 | **200.0** | 0.028 | −0.30 | 457,143 |

Two facts, and the tile refuses to show either alone:

1. **Theta dwarfs the premium.** The 764 call decays $0.78/day against a $0.10
   ask — 7.8x its entire value. On 0DTE a position does not erode, it
   evaporates. `theta_burn_pct` routinely exceeds 100% and is **not clamped**,
   because the number that looks like a bug is the risk.
2. **That same call doubles on a 0.06% move in SPY.** This is why he wants the
   board at all.

Either number alone is propaganda. `stats` carries both.

**Volume is not tradeability.** 828,288 contracts changed hands on a strike
worth one cent at a 66.7% spread. That is why `is_tradeable` exists rather than
ranking by volume, and
`test_the_wildly_traded_penny_strike_is_REFUSED` pins it.

## 3. The house values, named as such

| knob | value | why this and not something else |
|---|---|---|
| `MIN_DELTA` | 0.20 | below it the spread explodes — 66% at 0.039δ, 200% at 0.028δ |
| `MAX_DELTA` | 0.70 | above it you are buying mostly intrinsic |
| `TARGET_DELTA` | 0.35 | enough gamma to move, not a lottery ticket |
| `MAX_SPREAD_PCT` | 25.0 | refuses a contract costing a quarter of premium to cross |
| `MIN_DAY_VOLUME` | 500 | it has to have actually traded today |
| `MIN_BID` | 0.01 | a contract with no bid cannot be exited — a hard floor, not a preference |
| `MIN_ASK` | 0.20 | 20 ticks — see §3b, added after it shipped missing |
| `FLIP_RELEVANT_SIGMAS` | 1.0 | see §5 |

The delta band's floor is set **by the observed spread curve**, not by a theory
of moneyness. That is the only evidence available, and it is stated rather than
dressed up. `test_every_house_threshold_is_declared_in_ONE_place` fails if one
of these gets forked into a second definition.

## 3b. The floor that was missing, and the board that proved it

The first ship had no minimum premium, and the live board immediately led with
this:

> **AMZN 262.5 call — bid 0.05 / ask 0.06 — reading "0.07x"**

Six ticks. It "doubles" on a **one-cent uptick**. Every floor passed it: delta
0.3328 sat mid-band, the spread was 18.2% against a 25% cap, and it had traded
90,278 contracts.

The failure was structural, not a mis-set threshold elsewhere:

```
double_move_pct = premium / (delta x spot)
```

falls as premium falls. **Ranking the board on it promotes the cheapest contract
on the tape, every time.** That is precisely the selection `pick_contract`
refuses to make *within* a chain — *"not the cheapest ... both of those select
for the strikes that expire worthless"* — and with no premium floor the board
reintroduced it *across* chains. The module contradicted its own docstring.

It is also the regime where the arithmetic stops meaning anything. At six ticks
the delta-linear double IS a single tick, so tick granularity decides the
outcome rather than the underlying.

`MIN_ASK = 0.20` is 20 ticks at the penny tick that applies below $3.00, so one
tick of slippage costs at most 5% of the position. Same board, after:

| | before | after |
|---|---|---|
| leader | AMZN 0.06 — **6 ticks** — 0.07x | QQQ put 0.58 — 58 ticks — 0.38x |
| 2nd | QQQ call 0.10 — 10 ticks — 0.07x | SPY put 0.37 — 37 ticks — 0.38x |
| 3rd | QQQ put 0.58 — 0.40x | TSLA call 1.89 — 189 ticks — 0.46x |
| names with a contract | 5 of 13 | 3 of 13 |

The floor is **deliberately inert for most of the session** — an ATM 0DTE with
hours left is worth dollars, not cents — so it bites only once contracts have
decayed into tick noise, which is exactly when they stop being rankable. That
last claim is reasoning, not measurement: there is no intraday option history
here to measure it with.

Pinned by `test_REGRESSION_a_six_tick_option_is_refused_however_good_it_looks`,
which asserts the contract clears every *other* floor before asserting it is
refused, and by `test_the_floor_bites_cheapness_NOT_low_volatility`, which keeps
TSLA's legitimate 1.89 suggestion on the board.

## 3c. The dead deep-link

The tiles first shipped pointing at `/sepa/<SYM>?tab=zero_dte`. That tab does not
exist in `SepaCandidate.tsx`'s `TABS`, so every tile click **silently fell back
to the chart tab** while every other Chart Maps board deep-links somewhere real
(`setup`, `supply`, `breakout`). They now point at the SEPA detail page's own
`options` tab, which exists and is the topically right landing spot.

`test_the_href_lands_on_a_tab_that_EXISTS` reads the real frontend source, so
the two cannot drift apart again.

## 4. `moves_needed` — the only figure comparable across names

`double_move_pct` alone is not readable. Measured the same session:

| | expected session move | needs to double | in its own sigmas |
|---|---|---|---|
| SPY | ±0.31% | 0.059% | **0.19x** |
| QQQ | ±0.44% | 0.033% | **0.08x** |
| NVDA | ±1.40% | 0.693% | **0.50x** |
| TSLA | ±1.79% | 0.944% | **0.53x** |

SPY and NVDA differ 12x in raw percent and only 2.6x in sigmas. Ranking the
board on the raw figure would put the lowest-volatility name first **every
single day**, for a reason that has nothing to do with the trade being better.

**This is also what made the missing premium floor dangerous** — see §3b. A
metric that is inverse to premium ranks tick-noise first, so the floor and the
ranking are one design, not two.

`expected_move_pct` is one session of ATM implied vol — `IV / sqrt(252)` — taken
from the strike nearest spot and averaged across the call and the put so one
stale quote cannot set the scale. The board sorts on `moves_needed`.

## 5. Two guards that only live data revealed

**The gamma flip was in the tail.** Walking strikes for a sign change found one
29% from spot on SPY and 53% on TSLA — decided by a handful of contracts of OI
in the far wing. A level a same-day expiry cannot reach is not a regime
boundary, it is trivia that looks precise. A flip beyond **one expected session
move** is suppressed and `flip_out_of_reach_pct` is reported in its place.

**The net-GEX sign was fragile.** TSLA read **+3.3M then −48.7M on two calls
seconds apart** — the verdict flipped from PINNED to AMPLIFYING — while a single
strike carried 137M. When `|net| < |largest node|` the aggregate is decided by
near-cancellation, so `fragile: true` is set and the banner says **UNSETTLED**
instead of picking a side. QQQ's profile the same session was genuinely
aggregate (1.86x) and is not flagged.

`opex`'s own caveats are carried, not dropped: `oi_coverage_pct` below 80%
downgrades the read out loud (NVDA was at 75.7%), and single names keep the
`gex_reliability` flag because the blind sign rule can invert on them.

**The sign rule is never re-derived here.** `opex` owns it and publishes its own
`regime` string; this module reads that verdict.
`test_the_gamma_SIGN_RULE_is_never_re_derived_here` fails on a second
implementation — one owner means the two can never disagree about a day.

A pin is framed as the **risk**, because this board is for someone *buying*
premium. It is good news to a seller, and borrowing the seller's reading would
invert the advice.

## 6. The ledger, and what it can honestly grade

**Graded:** did the UNDERLYING move far enough, from the daily bar's high/low.

**NOT graded:** the option's P&L. Three reasons, all real:

1. **The path is invisible.** A daily bar says the high was 766.10, not whether
   it printed at 09:45 or 15:55. Every intraday figure is an **optimistic upper
   bound**, and `path_blind: true` is stamped on every row.
2. **`double_move_pct` is delta-linear.** Gamma flatters it, theta destroys it,
   neither is modelled, and the two errors do not cancel.
3. The suggestion's own `ask` is recorded, so the cost of crossing is in the
   record rather than in a footnote.

The field is `move_outcome`, never `outcome` — pinned by a source guard — so it
cannot be quietly read as P&L.

**Day one proved the caveat.** The first two graded rows both hit their double
on the excursion and **neither held it to the close**:

| | best intraday | at the close | |
|---|---|---|---|
| NVDA 207.5c | **+3.47%** | +0.05% | doubled, then gave it all back |
| TSLA 347.5c | **+4.17%** | +0.10% | same |

So `double_move_pct` read **100%** and `held_to_close_pct` read **0%** about the
same day. Both are published; `held_to_close_pct` is the one immune to path
blindness and the one to trust. `accuracy()` cannot return a win rate without
the caveat attached — also pinned by a guard.

Recording runs at **10:00am ET**, deliberately during the session: a suggestion
frozen after the close is worthless twice over, since the chain has settled to
pennies and the grade would be blind to the whole day. Resolution runs at
5:10pm. A bar that has not printed leaves the row **open** rather than grading
it a loss — SPY and QQQ were a price-cache refresh behind on day one and
correctly waited.

## 7. Session state is part of the answer

After the close on expiry day the chain has settled. Measured 2026-08-24 at
20:20 UTC: all 13 names had a chain, and **only 4 carried any contract clearing
the floors**. That board is correct, but without saying so it reads as broken —
hence the banner, and `with_contract` vs `with_chain` stated side by side.

## 8. Where the honesty is enforced

| Decision | Guard |
|---|---|
| The cost arithmetic is what it claims | `test_the_cost_arithmetic_is_what_it_claims` |
| Theta may exceed 100% and is not clamped | `test_theta_burn_is_a_share_of_premium_and_may_exceed_100` |
| A missing delta yields None, not a partial row | `test_a_missing_delta_yields_None_not_a_partial_row` |
| Crossed / zero-ask books are refused | `test_a_crossed_book_is_refused` |
| Nothing reaches JSON as NaN | `test_no_metric_is_ever_NaN_or_inf` |
| Volume is not tradeability | `test_the_wildly_traded_penny_strike_is_REFUSED` |
| No bid ⇒ no exit ⇒ refused | `test_a_contract_with_no_bid_cannot_be_exited_so_it_is_refused` |
| Ties break on spread, not cheapness | `test_a_delta_tie_is_broken_on_the_TIGHTER_spread_not_the_cheaper_price` |
| Nothing clearing ⇒ None, not least-bad | `test_nothing_clearing_the_floors_returns_None_not_the_least_bad_row` |
| Names stay comparable | `test_moves_needed_makes_two_different_names_COMPARABLE` |
| Sigma ranking, not raw percent | `test_the_board_ranks_on_SIGMAS_not_raw_percent` |
| Missing data sorts LAST | `test_REGRESSION_a_row_with_no_tradeable_contract_sorts_LAST` |
| The sign rule has one owner | `test_the_gamma_SIGN_RULE_is_never_re_derived_here` |
| A near-cancelled net is flagged | `test_a_net_smaller_than_its_largest_node_is_flagged_FRAGILE` |
| An unreachable flip is suppressed | `test_an_out_of_reach_flip_is_SUPPRESSED_rather_than_drawn` |
| A pin is framed as the buyer's risk | `test_a_pin_is_framed_as_the_RISK_because_this_board_BUYS_premium` |
| Settled chains say so | `test_after_the_close_the_board_says_it_is_NOT_live` |
| Half-recorded suggestions are refused | `test_a_half_recorded_suggestion_is_REFUSED` |
| Every row carries its own limitation | `test_every_recorded_row_carries_its_own_limitation` |
| A missing bar leaves the row OPEN | `test_a_missing_bar_leaves_the_row_OPEN_rather_than_grading_it_a_loss` |
| Excursion and close are separate | `test_the_excursion_and_the_CLOSE_are_recorded_separately` |
| Never named `outcome` | `test_the_ledger_field_is_named_move_outcome_and_never_plain_outcome` |
| No win rate without the caveat | `test_accuracy_cannot_report_a_win_rate_without_the_caveat` |
| Tick-noise cannot lead the board | `test_REGRESSION_a_six_tick_option_is_refused_however_good_it_looks` |
| The premium floor is what refuses it | `test_the_premium_floor_is_what_refuses_it_not_some_other_gate` |
| Real contracts still survive it | `test_the_floor_bites_cheapness_NOT_low_volatility` |
| The deep-link lands somewhere real | `test_the_href_lands_on_a_tab_that_EXISTS` |
| No claimed backtest | `test_the_module_never_claims_a_backtest_it_cannot_run` |
| Pure functions stay network-free | `test_the_pure_functions_take_no_network` |

## 9. Known limits

* **No order-book depth**, which he asked for. Top of book only.
* **No backtest is possible**, so nothing here is validated. The ledger is the
  remedy and it starts empty.
* **Grading is path-blind** and therefore optimistic. `held_to_close_pct` is the
  honest column.
* **The universe is curated**, not discovered. A name losing its dailies
  degrades to absent (its chain comes back empty), never to a wrong row.
* **Single-name gamma can invert the sign rule** — `opex`'s caveat, carried
  through as a badge.
* **Decision support, not a signal, and not advice.**
