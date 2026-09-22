# 📅 Since the report — the FACT column on 🚀 Explosive Growth and 📈 Bonde

Shipped 2026-09-21. Backend `backend/sepa/since_report.py`, frontend
`frontend/src/lib/sinceReport.ts`. **Nothing here sorts, filters, orders,
gates, alerts or buys.**

---

## 1. The ask

Ajay, 2026-09-21, after the board-growth research run:

> Should the boards print a "since qualifying filing" column?

→ **Yes.**

## 2. Why, in his words

The 2026-09-21 run (`docs/research/board_growth_2026_09_21.md`) measured both
boards against the date the market learned the number:

| cohort | median gain in the 126 sessions BEFORE the filing | median SINCE | positive since |
|---|---|---|---|
| 🚀 growth board (21) | **+46.40%** | **−2.21%** | 8 of 20 |
| 📈 Bonde visible (160) | +8.19% | −4.41% | 57 of 152 |
| scan universe (2,090) | +8.14% | −4.63% | 514 of 1,656 |

**The typical name on these boards had already had its run before the board
could see it, and nothing on either board said so.** This column is that
"since" leg, per name.

The Bonde board's "before" leg (+8.19%) is measured against **the scan
universe's own** +8.14% — not against RSP and not against "the market". The
RSP-relative reads live elsewhere in the artifact and are not served here.

Every number on the surface is formatted out of `since_report.RUN_MEASURED`,
which `backend/tests/test_since_report.py` pins field-for-field against
`backend/scripts/board_growth_measured.json`. No served module reads the
artifact; they cite the doc path.

## 3. THE DATE IS THE REPORT DATE, NOT THE SEC FILING DATE

The anchor comes from this app's earnings calendar (Mongo `earnings_calendar`,
`last_report.date`, yfinance via `sepa/earnings_watch`) — the date the company
**reported**. The study measured from the SEC 10-Q/10-K **`filed`** date.

On CRDO the two are one day apart: reported 2026-09-01, filed 2026-09-02.
Immaterial over a 126-session window — but they are different dates, and the
column header, every cell tooltip and this doc all say so. No surface calls
them the same thing.

`/root/.cheetah/audit_fin_v1.json.gz` (the study's SEC-filing artifact) is
**not** read: it is a one-off dated Sep 14, nothing in the crontab refreshes
it, and a board column on it would silently freeze.

## 4. The anchor rule

One engine: `sepa.earnings_picks.reaction_read`, the app's only BMO/AMC rule.

| `when` | anchor session |
|---|---|
| `BMO` | the report day itself |
| `AMC` | the next session |
| `null` (unknown timing) | the report day itself — `reaction_read` shifts only for `AMC` |

The cell is the return from that session's **close** to the latest **closed**
bar in the cached frame. That is what a board-viewer could have captured: the
day-0 gap sits in the study's BEFORE leg by construction, and he could not have
traded it (HIS CALL #1 — the alternative is anchoring on the pre-report close).

`reaction_read` gained one additive kwarg, `min_history` (default **50**,
unchanged, so the Earnings-report picks list is byte-identical). This column
passes `min_history=1`: it wants `drift_since_pct`, not the 50-day volume leg.

## 5. The in-progress bar, and the zero-length window

**The price cache is NOT closed-bars-only during the session.** `crontab:407`
runs `vcp-watch` hourly 09:00–16:00 ET and `prices.patch_latest_closes`
appends today's snapshot bar to `price_cache`, rewriting it in place on every
later run. Read at 11:00 that bar is a partial print, not a close, and
`_drop_phantom_tail` does not catch it (it only removes an exact close+volume
echo).

So `read_one` trims it:

| `prices.trade_session(EW._today_et())` | a today-dated last bar |
|---|---|
| `premarket`, `rth` | **dropped** — it is the hourly patch |
| `afterhours`, `closed`, unknown | **kept** — the day bar is complete, the same reading `prices.with_today_bar` applies |

That is the only trim in the module, and it runs before the empty check, so a
frame holding nothing but today's partial reads `no_bars`.

**A zero-length window is blank.** If the reaction close IS the latest closed
bar, no session has closed on the number yet, and `+0.0%` would read as
"unchanged" — a different and false statement. `known: true` therefore always
implies `sessions >= 1`, and a served `0.0%` can only ever be a real unchanged
close over at least one session.

Between 16:00 and 16:30 ET the today-bar is the 16:00 snapshot, not the settled
close — the same tolerance `with_today_bar` already grants; the 16:30 fast scan
settles it.

The rule is keyed to the CLOCK, not to whether that particular bar settled.
A cache document last written at 11:42 and never refreshed still gets read
after 16:00 as though its today-bar were a close. That is not a hypothetical:
**31 documents were in exactly that state at 23:10 ET on 2026-09-21**, though
only **1 of his 200 Bonde rows and 0 of his 21 growth rows** among them. The
sizes and the open question are in §7.

## 6. The seven refusals

A blank is an em-dash whose tooltip opens **"Not measured:"** and names the
refusal. It is never `0%` and never reads as flat.

| reason | what it means |
|---|---|
| `no_report` | no report date on file for this name. Unknown — not "did not report" |
| `bad_date` | the calendar carries a date this app cannot read |
| `report_predates_period` | the newest calendar report is OLDER than the quarter the board screened on, so it is not the qualifying report |
| `not_traded_yet` | the report is in the future, or no session has closed after the reaction session — **and today also a name whose cached frame stopped before the report date; see §11.10** |
| `no_bars` | no cached price history |
| `before_first_bar` | the report date precedes the first cached bar |
| `insufficient_history` | the reaction-bar read could not anchor the report, or a close was zero / non-finite |

`report_predates_period` needs `period_end` on the row. **Measured in the api
container 2026-09-21: `period_end` is `None` on every live growth row today**
(`period` carries `"FY2026 Q2"` instead), so the check never fires and the
ten-year case is caught by `before_first_bar` instead — the cell is blank
either way. Bonde rows carry no `period_end` at all, so the check is skipped
there by design.

Two guards worth naming:

* **Non-finite.** `prices._fetch_yfinance` does not filter `close > 0` the way
  `_fetch_massive` does, so a cached frame can hold a zero or NaN close, and
  `closes[k] == 0` gives numpy `inf` rather than an exception. `read_one`
  refuses `anchor_close <= 0` and any non-finite value. `known: true` with a
  null or non-finite return is unreachable; the API `_scrub` is a belt, not the
  guard. The frontend carries a second belt anyway.
* **Freshness is a LABEL, never a gate.** `stale_report` uses
  `bonde_picks.SURPRISE_STALE_DAYS` (157 days — the same rule the surprise leg
  on the very same doc uses, where "the label never changes the verdict");
  `calendar_stale` uses `earnings_watch.REFETCH_AFTER_SEC` (3 days, the
  calendar's own refetch rule). Both are imported by name. A backend test reads
  `sinceReport.ts` as text and pins its two printed literals to those
  constants, so the tooltip can never drift from the rule it describes.

## 7. The reads are O(1) per board

Two bulk queries for a whole board, never a per-name loop — the AMD lesson of
2026-09-21 (80 tiles × 1 call = 65 s; the fix was one snapshot per board).

* `earnings_watch.last_report_map(syms)` — ONE `find`, now also projecting
  `fetched_at` (additive; the five existing keys and the None-omission
  behaviour are unchanged).
* `prices.bulk_cached_frames(syms)` — ONE `find`, and **it can never fetch**.
  A cold symbol is an absent key and the cell says "no cached price history".
  No TTL check on purpose: a closed-bar frame is a fact whatever its age, and
  the caller prints the frame's own last date as its as-of (Rule #7).

### Latency, MEASURED in the api container

Read-only probe, 2026-09-21, two runs. `perf_counter` deltas.

| board | rows | calendar read | price-cache read | `attach` total |
|---|---|---|---|---|
| 🚀 growth | 21 | 0.0017–0.0018 s | 0.0193–0.0196 s | 0.0024–0.0025 s |
| 📈 Bonde | 200 distinct | 0.0023–0.0028 s | 0.163–0.169 s | 0.155–0.165 s |

For scale, `bonde.board()` itself is 0.39–0.45 s on the same runs, so the
column adds roughly **0.33 s to the Bonde request and 0.02 s to the growth
request**. Well under the 1.0 s bar; the `bars` projection fallback was not
needed.

### Session runs, MEASURED — the RTH / post-16:30 pair

Both probes ran on 2026-09-21 in the api container, read-only. The wall clock
could not be moved into market hours (the first probe ran at 22:43 ET, the
second at 23:10 ET), so the RTH leg was taken two ways that together cover it:
the **whole wall-clock path** on a frozen clock, and the **real in-progress
bars** sitting in the live cache.

`attach` was called with **no `session` argument** on every run below, so each
one exercised `prices.trade_session(EW._today_et())` → the trim, exactly as the
served endpoint does.

| run | clock (ET) | session | growth `as_of` | Bonde `as_of` | known | `known` with 0 sessions |
|---|---|---|---|---|---|---|
| A | 23:10 wall clock | `closed` | 2026-09-21 | 2026-09-21 | 19 / 65 | **0** |
| B | 11:00 frozen | `rth` | **2026-09-18** | **2026-09-18** | 19 / 65 | **0** |
| C | 06:30 frozen | `premarket` | **2026-09-18** | **2026-09-18** | 19 / 65 | **0** |
| D | 17:00 frozen | `afterhours` | 2026-09-21 | 2026-09-21 | 19 / 65 | **0** |

Run A is the genuine post-16:30 case on the real clock. Between B and D
**19 of 21 growth rows and 65 of 200 Bonde rows move their `as_of` by one
session** and no row anywhere is served `known: true` with a zero-length
window — the two assertions the plan asked of the live pair.

**The real in-progress bars.** At 23:10 ET, **31 `price_cache` documents were
still carrying a today-dated last bar whose `cached_at` stamp fell inside the
session** — written by the hourly `crontab:407` patch and never re-settled.
Those bars are genuine part-day prints, not closes, and the probe read them
with the trim on and off:

| symbol | doc written | `rth` (bar dropped) | `afterhours` (bar kept) | difference |
|---|---|---|---|---|
| AOUT | 11:42:40 | +13.40% (as-of 09-18) | +14.88% (as-of 09-21) | 1.48pp |
| FANG | 12:32:23 | **+0.29%** | **−2.13%** | a sign flip |
| INV | 13:44:12 | −63.00% | −45.26% | 17.74pp |
| BMNR | 11:30:03 | +64.60% | +73.69% | 9.09pp |

11 of the 31 read differently; none was served `known: true` with
`sessions == 0`. AOUT's frame is copied bar-for-bar into
`backend/tests/test_since_report.py::LiveUnsettledBar`, which reproduces both
served numbers from the frozen wall clock and pins the zero-window refusal at
ten different hours of the day.

**A limitation this pair exposed — HIS CALL.** The trim is keyed to the
CLOCK, not to whether the bar settled. A name whose cache document was last
written at 11:42 and never refreshed is served, after 16:00, with that 11:42
print standing in for the close. Measured on his two boards at 23:10 ET:
**0 of 21 growth rows** (the `growth earnings` cron force-refreshes them
nightly) and **1 of 200 Bonde rows** (FEIM, written 11:11:07). The alternative
rule — trim when `cached_at` itself falls inside the session — is a new rule on
a shared cache and is not invented here (Rule #1). Keep the clock rule, or
raise it?

➜ **Still owed:** one probe on the real wall clock between 09:30 and 16:00 ET.
Runs B and C move the same code down the same path on the same live data, and
`LiveUnsettledBar` plus `InProgressBar::test_attach_reads_the_session_from_the_one_clock`
pin the clock wiring, so what a wall-clock run would add is confirmation that
the container's own clock reads `rth` during the session — nothing about this
column's arithmetic.

### Coverage, MEASURED on the live boards

| board | rows | known | blank | why |
|---|---|---|---|---|
| 🚀 growth | 21 | **19** | 2 | both `before_first_bar` (EVC's latest report is 2024-05-02, FF's is **2016-11-09** — ten years old) |
| 📈 Bonde | **200 distinct** | **65** | 135 | all `no_report` — no report date on file |

44 of the 200 Bonde rows carry a calendar doc older than 3 days; 2 of the 21
growth rows are past the 157-day report label, none is calendar-stale.

The 🚀 board is near-complete because `growth earnings` (`crontab:1044`)
force-refreshes its own names nightly. **Bonde has no such line** — which is
why it is blank on 135 of 200. The repo's own bar (`sepa/research.py:154`) is
that "a column blank for a third of the board is worse than no column", so
both boards print their coverage on the surface rather than drawing a wall of
em-dashes. ➜ **HIS CALL #3:** add the Bonde names to
`growth.earnings_fresh.refresh_board_calendar`'s scope (a cron change; the
crontab was off limits this round), or leave the board saying "known for 65 of
200".

### A defect this probe caught

The first probe run read `insufficient_history` on **every row of both
boards**. Cause: a live `price_cache` frame is not stamped midnight — CRDO's
older bars carry `04:00:00` — so anchoring with
`frame.index.get_loc(Timestamp("2026-09-02"))` raised `KeyError` and blanked
the column everywhere. The lookup is now by **date**, on the normalised index.
`IntradayStampedIndex` in `backend/tests/test_since_report.py` pins it.

## 8. The served shape

Per row, key `since_report`, always these 14 keys on every branch:

```
known · pct · report_date · when · anchor_date · anchor_close · as_of ·
last_close · sessions · report_age_days · stale_report ·
calendar_fetched_at · calendar_stale · reason
```

Per board, key `since_report_summary`:

```
n · n_known · n_positive · n_blank · blank_reasons{reason: n} ·
n_stale_report · n_calendar_stale · as_of · date_basis · date_basis_note ·
measured{run_date, doc, sessions_before, benchmark, board, universe} ·
honesty · source
```

`honesty` is the board's own sentence, built entirely from `RUN_MEASURED`.
The frontend renders it verbatim and composes no number of its own — a
re-run that moves a figure moves every surface at once.

`attach` never adds, drops, reorders or re-sorts a row, and never raises: on
any failure every row still gets a shaped blank and a summary still comes
back. A ⚡ pivot row is **one dict appended to two Bonde sections**
(`bonde.py:601/605/609`), so rows are de-duplicated by `id(row)` — never by
symbol — and counted, computed and mutated once.

## 9. What does NOT carry the column

The join runs at READ time in the two API payload builders, exactly where
`earnings_fresh` and `board_metrics` attach and for the same reason (the
growth board rebuilds weekly; a return baked into `build()` would freeze for
up to seven days). So:

* `GET /growth/board`, `POST /growth/refresh` and `GET /bonde/board` carry it.
* `python -m sepa.bonde show` and every cron path do **not**. By design.

## 10. Not measured forward

**The column claims nothing.** There is no prior in this repo on the
predictive value of a name's return since its report, and this package created
none. The served sentence is a description of what the 2026-09-21 run found
about these two boards' history — a measurement over one snapshot, not a rule.

## 11. HIS CALL — open

1. **Anchor** — reaction-session close (shipped) vs the pre-report close.
2. **A report past the 157-day label** — rendered with a tooltip label
   (shipped, mirroring the surprise leg) vs blanking the cell.
3. **Bonde coverage 65 of 200** — extend the nightly calendar refresh to the
   Bonde names (a cron change), or leave it saying so.
4. **A sort on the column** — not built; the ask said it is a separate ask.
5. **The 3-day calendar-stale label** — it marks 44 of 200 Bonde rows today.
   Keep the calendar's own rule, or label only past 157 days?
6. **`period_end` is null on every live growth row**, so
   `report_predates_period` never fires today. Populate it in
   `growth/tracker.py`, or leave `before_first_bar` to catch the old-report
   case?
7. **A "newer report than the screened quarter" bound** — none is set (that
   would be an invented threshold). `bonde_picks.QUARTER_DAYS` (91) already
   exists if he wants one.
8. **Re-run cadence** for the served 2026-09-21 constants. Until re-run, both
   boards quote a 2026-09-21 snapshot and say so.
9. **One live RTH probe** during market hours — the only leg of §7's pair not
   taken on the real clock. Runs B and C cover the same path on a frozen clock
   over the same live data.
10. **The trim is clock-keyed, not settlement-keyed** (§5, §7). A cache doc
    last written mid-session serves its part-day print as a close after 16:00 —
    1 of 200 Bonde rows, 0 of 21 growth rows on 2026-09-21. Trimming on
    `cached_at` instead would be a new rule on a shared cache, so it is not
    invented here. Keep the clock rule, or raise it?
11. **A stale `price_cache` doc reads `not_traded_yet`** — 2026-09-21, LOW,
    not fixed here. A report dated in the past whose name's cached frame
    stopped updating BEFORE that date takes the `report_date >= last_bar`
    branch (`since_report.py:269-272`) and blanks as `not_traded_yet`, whose
    sentence says "no session has closed AFTER the first one the market could
    trade on this report". Sessions DID close — the cache went stale. The
    blank also carries `as_of: None`, so the surface cannot show where the
    bars stop. Telling the two apart needs either an **eighth reason** (the
    seven in `REASONS` and their sentences are frozen by the spec, and the FE
    blank map is keyed on them) or **`as_of` served on the blank** (a frozen
    key, but a new meaning for a blank, and the coverage line reads
    `max(as_of)`). Both are wording on a surface he reads → his call, not
    mine. Today's behaviour is pinned by
    `StalePriceCacheReadsAsNotTradedYet` in `backend/tests/test_since_report.py`,
    including a guard that no eighth reason lands without closing this item.
    Scale: none of the 221 live rows probed on 2026-09-21 hit it (the growth
    board is force-refreshed nightly; the Bonde blanks are all `no_report`).

## 12. Files

| file | what |
|---|---|
| `backend/sepa/since_report.py` | the engine: `read_one`, `attach`, `honesty_line`, `RUN_MEASURED` |
| `backend/sepa/prices.py` | `bulk_cached_frames` — ONE find, never a fetch |
| `backend/sepa/earnings_watch.py` | `REFETCH_AFTER_SEC` alias + `fetched_at` on the map |
| `backend/sepa/earnings_picks.py` | `reaction_read(min_history=)`, default 50 unchanged |
| `backend/growth/api.py`, `backend/sepa/bonde_api.py` | the two read-time wirings |
| `backend/tests/test_since_report.py` | the pins and every negative |
| `frontend/src/lib/sinceReport.ts` (+ `.test.ts`) | the one formatter for both boards |
| `frontend/src/components/ExplosiveGrowth.tsx`, `BondeBoard.tsx` | the column and the honesty lines |
| `frontend/src/pages/__fixtures__/since_report_{growth,bonde}_2026_09_21.json` | the REAL served payloads, rendered through the REAL components in vitest |
| `docs/research/board_growth_2026_09_21.md` | the research run every number comes from |

### 12.1 One field in the Bonde fixture was not captured — 2026-09-21

Both fixtures were probed out of the running container, and the container runs
`main`. `main` does not carry the Steady tier's measured line yet, so the Bonde
capture came back with a `measured` block of eight keys and no `measured.steady`
— the one field the render test for the Steady line needs.

Rather than leave that line proved only by a synthetic string, the field was
filled in from this branch's own `sepa.bonde.measured_verdict()` — the same pure
call `bonde.board()` makes at `bonde.py:789`, with no Mongo and no scan in it —
so the fixture is byte-for-byte the payload the API will serve once this branch
deploys. The other eight keys were verified identical to that same call before
the field was added, i.e. nothing else in the block was rewritten.

Two pins keep it honest, and both fail if anyone edits the string by hand:

- `backend/tests/test_since_report.py::FixtureContract::test_bonde_fixture_measured_block_is_the_served_one`
  — every key of the fixture's `measured`, the eight captured and the filled
  `steady`, must still equal `bonde.measured_verdict()` today.
- `…::test_NEGATIVE_bonde_fixture_steady_is_not_a_synthetic_string` — the line
  must be the real dated paragraph, not a placeholder.

On the frontend, `BondeBoard.test.tsx` renders the fixture through the real
component and asserts the Steady line equals the fixture's own served string and
sits inside the Steady `<section>`, plus a NEGATIVE that it is not the stub the
other cases use.

**Still owed (HIS CALL / main session):** re-probe both payloads from the
container after `./deploy-cheetah-main.sh api frontend` and overwrite the two
fixtures with the untouched captures. Nothing then changes in the tests —
`measured.steady` is already pinned to the served call — but the Bonde capture
becomes a pure probe again, and the row-level coverage counts (65 of 200 known,
178 calendar-stale) refresh to the deployed board's own numbers.
