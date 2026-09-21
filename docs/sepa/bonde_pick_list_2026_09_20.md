# 📋 The Bonde PICK LINE — his STATIC criteria, each one cited

**2026-09-20.** Ajay: *"I need bonde for stock picks rather than deciding to
enter. I decide based on supply and demand and also based on Momentum, but show
me other things like EPS, Sales and other things"*, corrected the same day to
*"momentum does not need to be a criteria for his pics … i look at momentum and
others as dynamic info. I am looking fro static info"*.

So the 📈 Bonde tab now carries, on every row, a **pick line**: the set of
STATIC facts Pradeep Bonde has published about what goes on his list, each one
shown with the verbatim sentence, its URL and its date. Entries stay his — S&D
and momentum — and **no momentum, relative-strength, return or persistence leg
is on the pick line**, by his own correction.

Engine: `backend/sepa/bonde_picks.py`. Wired in `backend/sepa/bonde.py`
(`_row` → the scan legs, `board()` → the cache legs + the served legend).

---

## What this is NOT

- **Not measured.** No leg here is a signal, none has a placebo, none has a CI.
  The board's own thesis measured INVERTED (`sepa/bonde.py::MEASURED`); the pick
  line is newer than that measurement and has not been measured at all.
- **Not a gate, a sort or a filter.** Nothing on this line changes which rows
  the board draws or in what order. No count, ratio or score over the legs is
  rendered anywhere — `n_pass` / `n_fail` / `n_unknown` are served for this doc
  and for `coverage()` only.
- **Not sourced from the YouTube summary.** Every quote comes from a post on
  `stockbee.blogspot.com` or from his own X account. The summary Ajay shared is
  not cited anywhere in the module.
- **Not an entry decision.** He decides entries; so does Ajay.

## Tri-state, always

Every leg is `{"ok": true|false|null, "value": …, "why": …}`.

`ok: null` is **UNKNOWN and never a fail.** A cold cache, a fiscal pair that is
not a year apart, a year-ago loss and a Yahoo frame that could not be read are
all "we cannot say". A ✗ beside his sentence is a claim about the company.

`stale` and `age_days` are **labels** (Rule #7: check the reported PERIOD, not
the cache age) and they never flip `ok`.

---

## The 14 computed criteria

| leg | his sentence (verbatim, abridged here — the served quote is complete) | post | data on this board |
|-----|------------------------------------------------------------------------|------|--------------------|
| `eps_5c` | "…the earnings should be at least 5 cents." | 2007-03-30 | latest quarterly EPS, `sepa/qoq.compute` |
| `eps_yoy_100` | "a significant earnings acceleration compared to last year same quarter … 100% plus" | 2010-02-12 | `qoq.yoy_pct` slot 0 vs slot 4, positive year-ago base required |
| `eps_seq_100` | "earnings are up 100% or more quarter over quarter" | 2007-03-30 | `qoq.compute().income_qoq_pct`, refused on a non-adjacent pair |
| `eps_accel` | "Now what one is looking for is earnings acceleration." | 2007-03-30 (+2010) | this quarter's y/y EPS growth vs the previous quarter's |
| `sales_5` | "Sales/revenue should be up 5% or more." | 2007-03-30 | the pillar's own rounded seam vs `sales.SALES_FLOOR_PCT` |
| `surprise` | "Beats analyst estimate" (+2007 "An earnings surprise … will lead to breakout next day.") | 2010-02-12 | `earnings_calendar.last_report.surprise_pct` (a PERCENT) |
| `float_25m` | "Float below 25 million is ideal … best moves … below 10 million … 100 million plus float tend to have pullbacks." | 2010-02-12 (+X 2024-06-13) | yfinance `floatShares` via `board_metrics` |
| `short_dtc_5` | "high short interest ( 5 plus days to cover)" | X 2024-06-13 | FINRA short interest via Massive, `short_interest_latest` |
| `neglect_analysts` | "no analyst coverage and is neglected" | 2007-03-30 (+2010) | analyst count on Yahoo's estimate row, via `analyst_pulse` |
| `fund_holding` | "…float, fund holding" (+2025 "low fund ownership") | 2014-07-30 | institutional ownership off the scan row — a 13F LEVEL, never a flow |
| `ipo_10y` | "Gone Public in the last 10 years" | 2025-09-01 | `ipo_dates` (Finnhub profile), **uncorroborated** |
| `cap_10b` | "a capitalization of less than $ 10 billion" | 2025-09-01 | yfinance `marketCap` via `board_metrics` |
| `rev_39_x2` | "two quarters of revenue growth of 39% plus" | 2025-09-01 | this quarter's and last quarter's revenue growth, read y/y |
| `sector_3` | "focus on three sectors: technology, healthcare, and consumer discretionary" | X 2023-01-25 | the scan row's sector, in yfinance vocabulary |

### The cite mapping that matters

He names BOTH earnings bases, in two different posts, and the legs cite the post
that carries the leg:

- **`eps_yoy_100` cites 2010** — "compared to last year same quarter as well as
  quarter over quarter … earnings acceleration of 100% plus".
- **`eps_seq_100` cites 2007** — "earnings are up 100% or more quarter over
  quarter".

The 2007 sentence names **no base for sales** ("Sales/revenue should be up 5% or
more"); this app reads sales year over year, for parity with `canslim`.

### Two notes on his own numbers

- **$10B vs $11B.** His 2025 prose says "less than $ 10 billion"; his scan line
  in the same post says "below 11 billion". `cap_10b` passes at the prose bound
  and the legend states both. Which one to use is **his call**.
- **The two-quarter revenue figure is read as y/y.** His post does not say which
  base. The leg says so on the row.

## The 6 criteria that are his and are NOT computed here

| leg | why not |
|-----|---------|
| `run_up_65d` | a PRICE read over 65 days — the correction asked for static information only |
| `story_ep` | no feed decides whether a name is a story stock; inventing one is this app's judgement in his voice |
| `pead` | the anomaly his whole method rests on, not a per-name screen |
| `reactor_watchlist` | a watchlist kept over weeks, and the reaction is a price read |
| `top_sector` | no sector RANK feed reaches this board |
| `earnings_40` | one entry in his catalogue of EP catalyst CATEGORIES — he writes that he only focuses on the 100%-plus names |

They are printed in the legend anyway, with the reason, so the list on screen is
never shorter than his list.

---

## `WHY_CODES` — the ONE vocabulary

Every served `why` is a member of `bonde_picks.WHY_CODES` (24 codes). The
frontend's `WHY_TEXT` keys are pinned equal to it by the contract sweep, so a
code with no sentence beside it cannot reach the page.

| code | what it means |
|------|---------------|
| `no_eps_series` | no quarterly EPS filings on the scan row, or the series does not reach back a year |
| `year_ago_loss` | the year-ago quarter lost money; `yoy_pct` divides by \|base\|, so a loss would print as a doubling |
| `pair_not_a_year_apart` | the fiscal pair was CHECKED and is not four quarters apart — every y/y leg refuses |
| `no_period_keys` | the pair could NOT be checked (no keys on file). The number IS computed; the chip says `unverified` |
| `prior_hole` | the PRIOR quarter is absent — costs the acceleration read and the two-quarter read, nothing else |
| `no_sales_read` | no revenue growth on the row |
| `no_inst_read` | no institutional-ownership figure on the scan row |
| `no_sector` | the scan row carries no sector |
| `no_threshold_in_his_writing` | he names the criterion and publishes no number — the leg is a FACT and never a pass or a fail |
| `seq_base_non_positive` | the previous quarter lost money (from `qoq.BASE_NON_POSITIVE`) |
| `seq_base_too_small` | the previous quarter is positive but too near zero to carry a ratio (`qoq.BASE_TOO_SMALL`, `MIN_EPS_BASE`) |
| `seq_base_unknown` | the two quarters are not both on file (`qoq.BASE_UNKNOWN`) |
| `seq_not_adjacent` | the two newest filings skip a quarter (`qoq.BASE_NOT_ADJACENT`) |
| `not_on_calendar` | no `earnings_calendar` doc, or no past reported row on it |
| `no_surprise_in_report` | the last report carries no surprise figure |
| `no_metrics_doc` | no `board_metrics` doc within its TTL |
| `no_float_in_doc` | the doc exists and carries no float (cached before 2026-09-20, or yfinance had none) |
| `no_cap_in_doc` | the doc exists and carries no market cap |
| `not_warmed` | no `short_interest_latest` doc — the warm has not run |
| `no_si_record` | a doc exists with no settlement date: a REMEMBERED miss, not an un-run warm |
| `no_analyst_doc` | no `analyst_pulse` doc |
| `no_estimate_read` | a doc exists and the analyst count is unset (property raised, frame `None`, or the doc predates 2026-09-20) |
| `no_listing_date` | no date in the `ipo_dates` cache |
| `future_listing_date` | the profile date is in the future — a corrupt row, never "the youngest name on the board" |

The `qoq` base states are mapped **by name** through `INCOME_BASE_TO_WHY`, so a
rename in `sepa/qoq.py` is an ImportError here, not a silently wrong sentence.

---

## Cost: ZERO network on the board path

`legs_from_scan_row` is pure and reads the scan row it is handed.
`attach(rows, db)` makes **five bulk Mongo reads** over the distinct symbols and
nothing else:

| reader | collection |
|--------|-----------|
| `sepa.board_metrics.snapshot` | `board_metrics` |
| `sepa.earnings_watch.last_report_map` | `earnings_calendar` |
| `short_interest.client.short_interest_map` | `short_interest_latest` |
| `sepa.analyst_pulse.coverage_map` | `analyst_pulse` |
| `sepa.ipo_age.listing_dates_map` | `ipo_dates` |

They are imported **inside** `attach()`: `short_interest.client._main` imports
`sepa.bonde`, which imports this module, so a top-level import in either
direction closes the cycle. `attach` never raises — a reader that is missing,
empty or throwing leaves its legs UNKNOWN and the board is served, because
`board()` runs inside crons.

`analyst_pulse.get_map` makes a bulk LIVE price call and is **never** on this
path; `ipo_age.age()` loads prices and `listing_date()` can call Finnhub —
neither is on this path either.

## Coverage on the 199 shown names, 2026-09-20 (before the warms)

| leg | known |
|-----|-------|
| EPS series (all four earnings legs) | ~95% of scan rows carry `eps_q_series` |
| institutional ownership | 22% of scan rows |
| market cap | 169 of 199 (a `board_metrics` doc exists) |
| float | **0** until `python -m sepa.board_metrics warm --all` re-fetches (the key is new) |
| earnings surprise | 53 of 199; 63 of the 885 stored reports app-wide are older than the stale bound |
| analysts | 134 docs exist; the count itself is unset until `python -m sepa.analyst_pulse refresh --force` |
| listing date | 199 of 199 |
| short interest | **0** until `python -m short_interest.client warm-si` has run |

The board serves a `pick_coverage` block and the page prints one sentence from
it, so an unwarmed leg reads as "not warmed", never as a silent wall of dashes.

> Short interest reads unknown on every row until
> `python -m short_interest.client warm-si` has run in the api container; a
> crontab line does not ship with a deploy.

## Freshness labels — this app's numbers, never his

- `SURPRISE_STALE_DAYS = QUARTER_DAYS (91) + FILING_LAG_DAYS (45) + GRACE_DAYS (21) = 157`
  — built from the Rule #7 constants in `observability/period_freshness.py` by
  name. `QUARTER_DAYS` is a new app label.
- `SI_STALE_DAYS` (owned by `short_interest/client.py`) — FINRA settles mid- and
  end-month and publishes ~9 business days later.

Neither is his, and **neither ever changes an `ok`.**

## The one caveat on `ipo_10y`

21.4% of Finnhub profile dates on this universe are recycled tickers
(`chart_maps/ipo.py`), which reads as a RECENT date on an OLD company — a falsely
young ✓. The leg is labelled `uncorroborated` on the row.
`chart_maps.ipo.corroborate()` reaches back ~130 days only, so it cannot check a
10-year claim. Whether the leg stays among the chips is **his call**.

## The one caveat on `neglect_analysts`

Yahoo never prints a zero. An **empty** `earnings_estimate` frame is the only
evidence of no coverage there is, and reading it as his "no analyst coverage" is
a reading — labelled `Yahoo carries no estimate rows` on the leg, with the
pending-nod sentence in the legend. A frame with rows but no current-quarter row
is UNKNOWN, not zero. Whether a small count (≤2) should also read as neglected
is **his call** — his words give no number.

---

## Tests

`backend/tests/test_bonde_picks.py` — the quotes are frozen verbatim
(`ALLOWED_QUOTES`), every branch of every leg has a negative, a stubbed board is
walked end to end asserting every served `why` is in `WHY_CODES`, `requests` is
monkeypatched to raise to pin the zero-network rule, and
`n_pass + n_fail + n_unknown == 14` on every row.
