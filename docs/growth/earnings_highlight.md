# 📣 "Just reported" on the 🚀 Explosive Growth tab — 2026-09-18

## The ask, verbatim

> "Can you refresh all stocks also look for any new addtions to Russels 1000, 2000s
>  and 3000s and make a remindder ro scan explosive growth of new earnings stocks
>  and high light them to me in explosive growth tab"

Parts 1–2 (the refresh, the Russell diff) were done directly. This document covers
part 3: **names on the 🚀 Explosive Growth board that have JUST REPORTED are marked
on the tab, and a weekday job keeps the dates fresh.**

---

## What it is, and what it is not

| | |
|---|---|
| **is** | a CALENDAR FACT joined onto the row at read time: *this company reported on date X, N days ago* |
| **is not** | a signal, a gate, a filter, a re-rank, or a claim that the name will move |

There is **no measurement anywhere in this repo** that a just-reported grower
outperforms. The nearest prior is the **8-K event study, 2026-09-01**: 8-Ks give
small caps volatility, not direction, and there was **no chase edge after a +20%
day-0 pop**. So the badge claims nothing, the tooltip says so in capitals, and the
100%/100% screen it sits on has itself never been measured forward.

---

## MEASURED FIRST — what he will actually see

Read-only probe inside `cheetah-market-app-api-1`, against his own live
`/growth/board` and the live `earnings_calendar`, **2026-09-18**:

| measurement | value |
|---|---|
| rows on the board | **21** |
| rows with an `earnings_calendar` doc | 21 of 21 |
| rows with **no** `last_report` at all | **16 of 21** (PTGX LQDA IPI MU HHH DX SM INSW SITM EVC LPG STAA NVDA NLY RKT TER) |
| rows reported within 2 calendar days | **0** |
| rows reported within 7 / 14 days | **0 / 0** |
| rows reported within 30 days | **1** — CRDO, 2026-09-01, 17 days ago |
| next nearest | ALAB 45d · BE 52d · ARR 58d · FF 2016-11-09 (dead stamp) |

**So on the day this ships, no row wears the badge** — at 7 days or at 2. That is
the honest state of the calendar, not a broken feature, which is why the tab says
it out loud instead of looking blank.

---

## The blanks are a SKIP, not a throttle

The nightly sweep is not rate-limited. Last night's cron log:

```
2026-09-17T17:45:00  starting  job.command="python -m sepa.earnings_watch"
2026-09-17T17:45:01  sepa.earnings_watch: universe=2078 refreshed=2
2026-09-17T17:45:01  job succeeded
```

**One second. 2 of 2,078 refreshed.** The 16 blanks are skipped by the `todo`
filter in `sepa/earnings_watch.py`: `"last_report" in doc` is True (the *value* is
`None`), `next_date >= today`, `fetched_at` is fresh — so none of the four
re-fetch conditions fire and the doc is never touched again.

**`force=True` is therefore the operative fix. Scoping is the coverage fix:**
`IPI` and `FF` are not in `earnings_watch._universe()` at all (that universe is
scan rows + holdings + watchlist, universe `full` ≈2,652; the growth board screens
universe `broad` ≈3,703). A board-scoped list is the only path that ever reaches
them.

Where the all-None shape comes from: `_fetch_next` falls through
`get_earnings_dates(limit=8)` to the `Ticker.calendar` fallback, which by
construction returns `{"next_date": …, "when": None, "eps_estimate": None,
"last_report": None}`. Every one of the 16 carries that fingerprint. Proof it is
recoverable, measured the same minute with a **targeted** call:

```
NVDA  _fetch_next -> last_report {'date': '2026-08-26', 'when': 'AMC', 'eps_actual': 2.22, 'surprise_pct': 6.16}
MU    _fetch_next -> last_report {'date': '2026-06-24', 'when': 'AMC', 'eps_actual': 25.11, 'surprise_pct': 21.39}
TER   _fetch_next -> last_report {'date': '2026-07-28', 'when': 'AMC', 'eps_actual': 2.47, 'surprise_pct': 20.28}
```

---

## THE CALENDAR WRITE WAS DESTRUCTIVE — and now has a merge-safe mode

`sepa/earnings_watch.refresh` writes with a full `replace_one`:

```python
doc = {"_id": sym, "fetched_at": int(time.time()),
       **(res or {"next_date": None, "when": None,
                  "eps_estimate": None, "last_report": None})}
coll.replace_one({"_id": sym}, doc, upsert=True)
```

Two paths null a populated `last_report`: `_fetch_next` returning `None`
(exception / no data), and the `Ticker.calendar` fallback, whose dict *itself*
carries `"last_report": None`.

Repro against a **stubbed** collection (never the live one), `_fetch_next -> None`:

```
BEFORE  {'date': '2026-09-01', 'when': 'AMC', 'eps_actual': 0.41, 'surprise_pct': 6.1}
        -> {'ok': True, 'refreshed': 1}
AFTER   None
```

16 of 21 live docs on this board already carry that scar — a 76% miss rate on
these names. A daily `force=True` job **without** a fix would have industrialised
it: steady state is CRDO losing its `last_report` and the one live number on the
honesty line disappearing.

**The rule, written into the docstring:**

> A **PAST** fact is never erased by a fetch that did not see it; a **FORWARD**
> estimate is.

So `refresh(..., merge=True)` protects `last_report` **only**. `next_date`, `when`
and `eps_estimate` keep replace semantics — nulling a stale forward estimate is
the conservative read, and it is also what stops an aged `next_date` from later
looking like a report. `fetched_at` always advances, miss or hit.

**`merge=False` is the default.** The shared 17:45 sweep over 2,078 symbols is
byte-identical to today, pinned by
`tests/test_earnings_watch_merge.py::test_merge_false_still_replaces`. Flipping
that default for the shared job is **Ajay's call** (see the open questions).

---

## Why the window is `REPORT_WINDOW_DAYS = 7`, not `LOOKBACK_DAYS = 2`

No number was invented. Every earnings window constant in the repo:

| constant | value | file | direction | fit |
|---|---|---|---|---|
| **`REPORT_WINDOW_DAYS`** | **7** | `sepa/earnings_picks.py` | **backward — "calendar days back a report still counts"** | **the one that fits; shipped** |
| `LOOKBACK_DAYS` | 2 | `chart_maps/earnings.py` | backward — *bar selection* | blind to Friday AMC, see below |
| `LOOKAHEAD_DAYS` | 0 | `chart_maps/earnings.py` | forward | upcoming only |
| `WARN_WINDOW_DAYS` | 7 | `sepa/earnings_watch.py` | forward | pre-report warning |
| `EARNINGS_WINDOW_DAYS` | 7 | `desk/scoring.py` | — | desk hold window, unrelated |
| `PREEARNINGS_BLOCK_DAYS` | 3 | `sepa/entry_exit.py` | forward | entry block, unrelated |

`REPORT_WINDOW_DAYS` is the repo's own **backward recency** window, it lives in the
earnings stack, it needs no semantic flip, and it is the same window the **Earnings
report picks** list he already reads uses — so "just reported" means one thing
across the app.

`LOOKBACK_DAYS = 2` is a **bar-selection** window for a board where *every tile is
today's bar*. At 2 days a **Friday-AMC reporter — the most common slot — can never
be shown on a market day**:

| day | read | result |
|---|---|---|
| Fri 2026-09-18 | `phase_for`: `nxt == today`, `when == "AMC"` → `UPCOMING` | no chip |
| Mon 2026-09-21 | `last_report.date = 2026-09-18`, `days_ago = 3` | `3 > 2` → **no chip ever** |

Same arithmetic kills every Thursday-AMC report seen on Monday. Pinned by
`test_a_friday_amc_reporter_is_visible_on_monday`.

---

## THE TRAP: `phase_for` answers a BAR question, not a REPORT question

`chart_maps.earnings.phase_for` returns `REACTED` for **any** `next_date < today`,
which is correct for "has this bar seen the numbers" and **wrong** for "did this
company report". Live example: **IPI** carries `next_date 2026-11-04` and no
`last_report` at all, and is not in `earnings_watch._universe()`. A naive read
would have rendered "📣 reported yesterday" on 2026-11-05 for a report that may
not exist.

So in `growth/earnings_fresh.py`:

* `last_report.date <= today` is the report source, and the only source of EPS
  numbers;
* `next_date` may contribute a report dated **TODAY and nothing else** — a BMO or
  unknown-timing report whose numbers `_fetch_next` cannot yet have written into
  `last_report` (it builds its `past` list from `ts.date() < today`, strictly);
* a `next_date` **strictly in the past** is a stale estimate, never a report.

Pinned by `test_a_past_next_date_is_a_stale_estimate_not_a_report`.

---

## The served shape

Per row, `earnings_fresh`:

```python
{"known": bool,               # a date the market has already seen
 "reported_on": str | None,   # "YYYY-MM-DD"
 "when": "BMO" | "AMC" | None,
 "days_ago": int | None,      # calendar days, today_ET - reported_on
 "fresh": bool,               # known and 0 <= days_ago <= 7
 "surprise_pct": float | None,# ONLY when reported_on came from last_report
 "window_days": 7}
```

At payload level, `earnings_fresh_summary`:

```python
{"window_days": 7, "n": 21, "n_fresh": 0, "n_known": 5, "n_unknown": 16,
 "as_of": "2026-09-18",
 "most_recent": {"symbol": "CRDO", "reported_on": "2026-09-01", "days_ago": 17},
 "source": "yfinance (Yahoo Finance) via sepa.earnings_watch — verify on EarningsWhispers; dates can shift"}
```

**`last_report: None` lands on `known=False` — UNKNOWN, never "did not report".**
16 of 21 today; reading it as a negative would be a lie told 16 times a page.

Attached in `growth/api.py::_payload`, next to the existing `board_metrics`
attach, for the same reason: the board rebuilds **once a week** (Sunday 09:00 ET),
so a report date baked into `build()` would be up to seven days stale. The read
**never adds, drops, reorders or re-keys a row**.

---

## What he sees

**The chip** — a 4th badge in the symbol cell, `cm-badge cm-badge-earnings`. It
renders `null` for every row that did not just report, so on a normal day it costs
**zero pixels**.

* `days_ago === 0` → `📣 reported today` (no `when` suffix — AMC-today is
  `UPCOMING`, and `last_report.date == today` can never be written, so the only
  reachable today-case is BMO/unknown)
* `days_ago === 1` → `📣 reported yesterday` (` · BMO` / ` · AMC`)
* otherwise → `📣 reported Sep 16` (` · BMO` / ` · AMC`)

Dates are formatted by `EarningsChip.fmtDate`, imported verbatim. **`new Date(iso)`
is forbidden in this component** and pinned by a contracts check:
`TZ=America/New_York node -e "new Date('2026-09-16').toLocaleDateString('en-US',{month:'short',day:'numeric'})"`
renders **`Sep 15`**.

**Tooltip:**

> `{SYM}` reported earnings on `{reported_on}``{, before the open|, after the close|}`
> — `{n}` day(s) ago, inside this board's `{window_days}`-day just-reported window
> (the same window the Earnings report picks list uses).
> A CALENDAR FACT, NOT A SIGNAL: it does not change this row's order, its demand
> read, its flags, or whether the trading engine will buy it. Nothing on this board
> is measured. Source: yfinance via the earnings calendar — verify on
> EarningsWhispers, dates can shift.

Plus one sentence when `surprise_pct` is present: *Reported EPS beat/missed the
estimate by X.X%.*

**The honesty line**, under the no-cap-floor note, rendered **only when
`n_fresh > 0 || n_unknown > 0`** — never as a standing "0 of 21" banner on an
already-dense tab:

> 📣 **Just reported — {n_fresh} of {n}** names on this board reported within
> **{window_days} days** (calendar read {as_of}). {n_unknown} names have **no
> report date on file** — that is unknown, not "did not report". Most recent report
> on this board: **{most_recent.symbol}, {reported_on}** ({days_ago} days ago). A
> calendar fact only: it changes no order, no filter and no gate, and the
> 100%/100% screen itself has never been measured forward.

This is **this board's own** honesty line. It must not borrow, and must not be
borrowed by, any other board's measured-verdict banner.

**Ordering and membership do not move.** No new filter, no re-rank, no change to
what the screen admits, no new table column. Pinned on both sides.

---

## THIS PUSHES NOTHING

The reminder is a **data cron**. It refreshes dates; no message of any kind leaves
it.

`push/subs.py::OWNER_KEEP_SET` is unchanged and pinned byte-for-byte by
`tests/test_growth_earnings_cron.py`:

```
hot_pullback_alert · pattern_alert · demand_alert · position_alert
```

One honest note so nobody miscounts: `growth/alerts.py` already ships
`KIND = "growth_demand_alert"` (2026-09-11), which lives **outside**
`OWNER_KEEP_SET`. "Four kinds" is therefore not literally true today — said here
so nobody reads it as "there is room for a fifth". **This change adds zero kinds
and no send path**, pinned by a source scan of both the `earnings` CLI branch and
`growth/earnings_fresh.py`.

Whether he wants a phone notification on a fresh report is an open question below,
not something shipped quietly.

---

## The cron line

```
50     17    *    *    1-5  /usr/local/bin/python -m market_hours.gate growth earnings
```

Three choices, all deliberate:

1. **17:50 ET** — after the 17:45 `sepa.earnings_watch` sweep (measured: it starts
   17:45:00 and logs `universe=2078 refreshed=2` at 17:45:01) and **before**
   `sepa.earnings_picks` at 17:55, which reads the same collection. A healed
   `last_report` is therefore visible to the picks run the same evening.
2. **Gated by `market_hours.gate`**, exactly like the `growth alerts` neighbour —
   closed day, no run.
3. **It sends nothing.**

Budget: at most `tracker.MAX_ROWS` = 300 symbols at 4 workers; 21 today.

### BOTH TREES + RECREATE — mandatory

**The cron mount is the HOST tree, so a main deploy does NOT ship a crontab
change.** The line is added to `backend/crontab` in the `.wt-growth` worktree only;
it reaches the host tree when the branch is merged. After that the cron container
must be **RECREATED, not restarted**:

```bash
docker compose up -d --force-recreate cron
docker compose exec cron crontab -l | grep "growth earnings"
```

### Side effect, named rather than buried

This job changes what `sepa.earnings_picks` sees five minutes later. Healing a
blank `last_report` can **ADD** a name to the "Earnings report picks" list shown on
**Portfolio / SEPA / Leaderboard / Scalping** — the same gates, more complete
input. Last night that list reported `{'ok': True, 'n': 2, 'checked': 14}`. More
names is the expected direction; **fewer** names would mean the merge fix is not
actually holding.

---

## NOT MEASURED

* The 100%/100% growth screen has **never been measured forward** — the served
  `disclaimer` says so on the board itself.
* The "just reported" badge has **no prior at all**. The nearest study, the **8-K
  event study of 2026-09-01**, measured **no chase edge** after a fresh print, and
  found 8-Ks give small caps volatility rather than direction.
* Nothing here was backtested, and nothing here orders, filters, gates, enters or
  sizes anything.

If a measured claim is ever wanted on this badge, it needs its own study with a
placebo, a CI and an out-of-sample split — and then his sign-off — before a single
word on the surface changes.

---

## Files

| file | what |
|---|---|
| `backend/sepa/earnings_watch.py` | opt-in `merge` parameter on `refresh()` |
| `backend/growth/earnings_fresh.py` | the read: `read_one`, `attach`, `refresh_board_calendar` |
| `backend/growth/api.py` | one read-time attach + `earnings_fresh_summary` |
| `backend/growth/__main__.py` | `python -m growth earnings` |
| `backend/crontab` | the 17:50 weekday line |
| `frontend/src/components/EarningsFreshChip.tsx` | the 📣 chip |
| `frontend/src/components/ExplosiveGrowth.tsx` | chip in the symbol cell + the honesty line |
| `backend/tests/test_earnings_watch_merge.py` | the destructive-write pins |
| `backend/tests/test_growth_earnings_fresh.py` | the read pins |
| `backend/tests/test_growth_earnings_cron.py` | the cron + no-send pins |
| `frontend/src/components/EarningsFreshChip.test.tsx` | the chip + TZ pins |
