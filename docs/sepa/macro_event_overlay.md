# Macro-event overlay — methodology

_Added 2026-06-16. Ajay: "add a macro into my portfolio analysis — consider macro
news that would impact the stock in the advice. If tomorrow is FOMC readout, with
our FRED access consider it, and allude to it in the Market Gauge hold vs sell."_

## What it is (and isn't)

An **informational binary-event heads-up** — the exact same discipline as the
Minervini Ch.8 earnings-quality overlay (`eq_sell_risk`):

> Minervini sells on **PRICE** (broken trend / stops, Ch.12-13), not on a calendar.
> So an imminent macro event does **NOT** change the price-based hold/sell verdict.
> It's surfaced so a tape-wide move (a FOMC/CPI readout can gap everything) isn't a
> surprise and stops/sizing get the attention they deserve.

We never predict the event's outcome or how the market will react — only that a
high-impact event is **near**.

## The single source — `macro_calendar.imminent_events()`

```
imminent_events(within_days=5, max_tier=1) -> [{date, kind, tier, label, days_until, when_label}]
```

- Reuses the **cached** macro calendar (FRED `/releases/dates`, the same free key
  the gauge uses) — **no extra FRED calls**. Soft-fails to `[]`.
- Tier 1 = market movers only: **FOMC decision, CPI, jobs report (NFP), Core PCE**.
- `days_until` / `when_label` ("today" / "tomorrow" / "in N days") computed in
  **ET** (events are ET-scheduled: FOMC 2pm, CPI 8:30am).

Both surfaces below read from this one function, so they can never disagree.

## Surface 1 — holding diagnosis (`portfolio/diagnosis.py`)

- `_macro_events_heads_up(events, sector)` → list of plain-text heads-ups
  (mirrors `_earnings_quality_sell_risk`). Adds a sector line when the holding's
  sector is rate/inflation-sensitive (financials, REITs, homebuilders, semis,
  utilities, growth) **and** the event is FOMC/CPI/PCE.
- New output field **`macro_events`** (list of strings), informational — sits
  next to `eq_sell_risk`, does not touch `position.verdict`.
- The LLM write-up payload gets `upcoming_macro_events`, and the system prompt
  now weaves in ONE clause naming the nearest event as binary event risk (never
  predicting its outcome). Grounding/citation rules are unchanged.
- Rendered in `HoldingDiagnosis.tsx` as a blue **📅 Macro event ahead** box,
  labelled "binary event risk, not a sell signal (Minervini sells on price)".

## Surface 2 — Market Gauge hold-vs-add (`sepa/market_gauge.py`)

`_outlook()` now **leads its watch list** with imminent tier-1 events:

> 📅 FOMC decision tomorrow (2026-06-17) — binary macro event; reduce NEW risk
> into it and let the readout confirm before adding.

This is the gauge's "hold vs add" guidance (the exposure-band context). It is
**presentational only** — the gauge **score, pillars and exposure band are
unchanged** (SEPA contracts + gauge tests still green). It renders on the Market
Gauge page's next-day-outlook section automatically.

## "FRED alerts"

The user's "fred alerts" = the FRED-backed scheduled-release calendar we already
have (next FOMC/CPI/jobs/PCE dates). A threshold-crossing alert system ("CPI YoY
> 6% → notify") does **not** exist yet — that would be a separate feature.

## FOMC sourcing + reliability (2026-06-17)

_Ajay, on the Regime (Market Gauge) page: "pull any events that might affect the
stock market like FOMC today as an example."_ Two defects were hiding the
calendar — both fixed in `macro_calendar.py`:

1. **FOMC was never shown.** FRED's `/releases/dates` carries a *"FOMC Press
   Release"* row, but it has **no firm scheduled date** — FRED pads a row onto
   **every day** of the realtime window. So (a) it can't tell us the real meeting
   day, and (b) the no-data-padding filter (`date_count[source] <= 3`) drops it
   entirely. Net: FOMC never appeared.
   - **Fix:** source FOMC from the **authoritative Fed calendar** —
     `FOMC_DECISION_DATES` (a hardcoded list from
     federalreserve.gov/monetarypolicy/fomccalendars.htm, the statement lands on
     the **last day** of each two-day meeting). `_fomc_events()` injects the
     real decision days; `_fred_releases()` now **skips** any `kind == "fomc"`
     row so the schedule is the single source. **Since 2026-10-07 the list is
     the FLOOR only** (`fed_schedule.FLOOR_DECISION_DATES`) — the Fed's own pages
     are read dynamically (see "Dynamic Fed calendar" below); verify the list
     only if the News block's stale/floor note shows.
   - The FOMC window is **ET** (`_today_et`, matching `imminent_events`), not UTC:
     an FOMC at 2pm ET must still read as "today" in the evening even after UTC
     has rolled past midnight.

2. **The whole calendar came back empty.** `/releases/dates` is genuinely slow
   (measured >30s); the old `(20, 25)`-second timeouts both fired → `[]` → empty
   panel. Bumped to **`(45, 60)`**. The call is `asyncio.to_thread`-wrapped and
   6h-cached, so the longer timeout only costs a cold load.

3. **Cron warm-up.** Added a `crontab` entry warming `get_macro_calendar(days=14)`
   at 4am/10am/4pm ET (TTL is 6h). **Corrected 2026-10-07:** that warm runs in
   the separate **cron** container, so it cannot fill the api's in-process
   `_CACHE` (INFERRED from the topology; the api computes its own doc on its
   first read after the TTL). Since 2026-10-07 the warm's `compute()` also
   refreshes the shared Mongo Fed LKG (`macro_fed_calendar`), which the api
   then reads. Deploy needs **`cron`** for that (no crontab edit).

## Dynamic Fed calendar (2026-10-07)

_Ajay 2026-10-07, with a screenshot of the 📰 News macro block: "First today
there was an FOMC event why is it not in our new tab in chart maps. I want us to
pull dynamic dates"._

**Why it was missing (MEASURED):** the 10-07 event was the **FOMC minutes** of
the Sep 15-16 meeting at 2:00 p.m. ET — not a decision. The calendar knew only
decision days (a hand-typed constant), and FRED has no minutes release, so no
code path could emit it. The decision days themselves were correct.

**Sources** (`backend/fed_schedule.py`, stdlib `re` + `html` parsers, never raise):

| source | what it gives | horizon (MEASURED 10-07) |
|---|---|---|
| `federalreserve.gov/json/calendar.json` (UTF-8 BOM, descriptions HTML-escaped twice) | FOMC meetings (decision day + 2:00 p.m.), press conferences (2:30 p.m.), **minutes**, **Beige Book**, speeches + testimony with times | current year only |
| `federalreserve.gov/monetarypolicy/fomccalendars.htm` | decision days per year panel, `*` = SEP (dot plot), "(Released …)" minutes dates; notation votes skipped | 2021 .. next year |

**Merge, per year:** calendar.json if it parsed ≥ `FED_MIN_MEETINGS_PER_YEAR`
(6; the Fed schedules 8) meetings that year, else fomccalendars.htm, else the
floor `FLOOR_DECISION_DATES` (re-exported as `macro_calendar.FOMC_DECISION_DATES`).
Minutes, Beige Book and remarks come from calendar.json only.

**Never invents:** no minutes date estimated from decision + 21 (MEASURED Nov
2024 was +19), no presser time, SEP flag or time of day filled in by
assumption, no ISM business-day rule.

**LKG + refresh:** each source's last good parse lives in Mongo
`macro_fed_calendar` (`{_id, parsed, fetched_at, last_modified,
last_attempt_at, last_error, schema}`). `macro_calendar.compute()` is the only
caller of `fed_schedule.current()`, which re-reads a source when its LKG is
older than `FED_REFRESH_SEC` (6 h, with `If-Modified-Since`). A non-200, a
timeout or a parse failure keeps the last good copy and records `last_error`
(class / HTTP code only, never a URL). Every other reader (`past_events`,
`next_fomc`, macro_indicators) uses `load()` = LKG ∪ floor and never fetches.
The News block footer says "checked … ago"; past `FED_STALE_SEC` (24 h) it says
the copy is stale, and with no LKG at all it says it fell back to the built-in
decision days.

**New rows** (tiers are **HIS CALL**, `macro_calendar.FED_KIND_TIERS`):
`fomc_minutes` T2 ("FOMC minutes", detail "Meeting of …"), `fed_chair` T2
("Fed Chair remarks", Chair only — Vice Chairs and Governors excluded),
`beige_book` T3 (gauge page only). The decision row keeps the label "FOMC
decision"; dot plot (SEP) and "press conference 2:30 pm ET" go in its `detail`.
Each row carries `time_et`; `imminent_events` adds the read-time `time_label`,
`past` and `past_label` ("released 2:00 pm ET", "began …" for the Chair), and
`when_label` stays today / tomorrow / in N days. The 📰 block also pins the
next FOMC decision when it is past the 14-day window, and re-derives
`next_tier1` at read time (first T1 row not yet out).

**Unchanged by design:** 🛡️ Resiliency counts only `HISTORY_KINDS` (FRED kinds
+ decisions) — minutes and Chair days are not T1/T2 days there; history rows
are decisions only.

**Fixes on the way:** `_fred_releases` and `_earnings_ahead` use the ET date
(a compute between 20:00 and 23:59 ET dropped that day's FRED rows under UTC);
the FRED retry log line goes through `_safe_reason` (the exception text carried
the `api_key` URL); the Fed Funds "next release" on macro_indicators is now the
next decision (it was always None).

Fixtures: `backend/tests/fixtures/fed_calendar_2026_10_07.json` (trimmed, filter
documented in `backend/scripts/capture_fed_calendar_fixtures.py`) and
`fed_fomccalendars_2026_10_07.htm` (verbatim). Tests:
`backend/tests/test_fed_schedule_2026_10_07.py`,
`backend/tests/test_macro_calendar_fed_2026_10_07.py`,
`frontend/src/components/NewsTabBoard.fed.live.test.tsx`.

**Critic fixes (2026-10-07, `backend/tests/test_fed_schedule_critic_fixes_2026_10_07.py`;
each test fails if its fix is reverted):**
- *Merge (medium):* a year takes calendar.json only when it has ≥
  `FED_MIN_MEETINGS_PER_YEAR` meetings **and** at least as many as
  fomccalendars.htm lists for that year. Before, one json meeting row that
  failed to parse silently dropped that decision (MEASURED by retitling the
  2026-10 row: 2026-10-28 vanished and `next_fomc` jumped to 12-09).
- *Weekend remarks:* the weekday bound applies only to FOMC and Beige rows. The
  Fed lists Chair speeches on weekends (Powell 2026-03-21 Sat, 2025-05-25 Sun),
  which used to be counted as `rejected`. The year bound still applies.
- *Parser schema:* an LKG whose `schema` ≠ `_SCHEMA` is re-read without
  `If-Modified-Since`, so a 304 can no longer pin an older parser's output. A
  failed re-read keeps the old copy.
- *Notes:* with no Mongo store the footer says `FED_NOTE_NO_STORE` ("store
  unavailable"), not "Fed calendar unreachable". When the FOMC page parsed but
  calendar.json never did, it says `FED_NOTE_NO_JSON` (minutes and Chair remarks
  not shown). `_coll()` closes the client when its ping fails.
- *Chair times:* the Fed states no time zone for speeches and testimony, so
  `fed_chair` labels read "10:00 am" with no " ET"
  (`macro_calendar.TIME_ZONE_UNSTATED_KINDS`). FOMC decision, presser and
  minutes times keep ET.
- Pinned with tests: `_earnings_ahead` on the ET day at 23:30 ET; the same-day
  time tiebreak in `compute()` and `imminent_events`; calendar.json with no
  current-year minutes is not ok.
- Not done (spec §3.2 hermetic rule): with no store, `current()` still does not
  fetch. A Mongo outage at the first compute after a restart therefore serves
  the floor for one 6 h TTL, and the footer now says so plainly.

## Tests

- `backend/tests/test_macro_events.py` — window/tier filtering + day labels +
  soft-fail; heads-up strings + sector sensitivity; gauge outlook surfaces /
  omits the event.
- `frontend/src/components/HoldingDiagnosis.test.tsx` — the 📅 box renders when
  events present, omitted when not.

## 2026-09-24 — FRED shadow releases printed as the print

**Symptom.** "Jobless claims" showed twice a week (Thursday AND Friday) from
2026-06-17, and a phantom T2 "Retail sales" row showed on 2026-10-08 in the
14-day window.

**Cause.** `_RELEASE_TIERS` is a first-match *substring* table. Several FRED
releases whose names CONTAIN a needle are state / industry / research cuts of a
print, not the print ("shadows"). `_fred_releases` dedupes on `(kind, date)`,
which hides a shadow only when it lands on the print's own date. Two did not:
469 (Fridays) and 494 (10-08).

Measured on FRED `/releases/dates`, realtime 2026-09-24 → 2026-10-24, every
name that matched a tier before the fix:

| kind | tier | FRED id | release name | dates | role |
|---|---|---|---|---|---|
| claims | 2 | 180 | Unemployment Insurance Weekly Claims Report | Thu 09-24, 10-01, 10-08, 10-15, 10-22 | **the print** |
| claims | 2 | 469 | State Unemployment Insurance Weekly Claims Report | Fri 09-25, 10-02, 10-09, 10-16, 10-23 | shadow (state detail) |
| cpi | 1 | 10 | Consumer Price Index | 10-14 | **the print** |
| cpi | 1 | 345 | Research Consumer Price Index | 10-14 | shadow (hidden by date luck) |
| gdp | 2 | 53 | Gross Domestic Product | 09-30 | **the print** |
| gdp | 2 | 140 | Gross Domestic Product by State | 09-30 | shadow |
| gdp | 2 | 263 | Debt to Gross Domestic Product Ratios | 09-30 | shadow |
| gdp | 2 | 331 | Gross Domestic Product by Industry | 09-30 | shadow |
| pce | 1 | 54 | Personal Income and Outlays | 09-30 | **the print** |
| pce | 1 | 391 | Personal Consumption Expenditures by State | 09-30 | shadow |
| retail | 2 | 9 | Advance Monthly Sales for Retail and Food Services | 10-15 | **the print** |
| retail | 2 | 436 | Monthly Retail Trade and Food Services | 10-15 | shadow (revised report) |
| retail | 2 | 494 | Chicago Fed Advance Retail Trade Summary | 10-08, 10-15 | shadow — 10-08 shipped as a phantom |

Single-source kinds in the same window (unchanged): adp 194 (09-30), jobs 50
(10-02), jolts 192 (09-29), ppi 46 (10-15), housing 27 (09-24, 10-20),
confidence 91 (09-25, 10-23), regional_fed 321 (10-15), trade 51 (10-06),
fomc 101 padded on all 31 days (already skipped; FOMC comes from
`FOMC_DECISION_DATES`).

**Fix (at the source, never a tab-side dedupe).** `macro_calendar._RELEASE_EXCLUDE`
— checked in `_match_tier` BEFORE the needle table, so an excluded name matches
no tier:

```python
_RELEASE_EXCLUDE = (
    "state unemployment insurance weekly claims",
    " by state", " by industry",
    "debt to gross domestic product",
    "research consumer price index",
    "monthly retail trade and food services",
    "chicago fed advance retail trade",
)
```

The `:87 "retail trade"` needle is left in place (it matches nothing real in
this window; 9 is caught by the `advance monthly sales for retail` needle) —
exclusion is additive and measured; removing a needle vs. a release-id
allow-list is Ajay's call (spec §7.4).

**Lock.** `get_macro_calendar` now holds a module-level `_CACHE_LOCK`
(`threading.Lock`) around the cold compute, with a double-checked cache: two
concurrent cold callers share ONE FRED fetch (45–105 s) instead of each
spawning their own. `force=True` still always recomputes; the cache key is
still `days`. Nothing served changes — a second cold caller now waits for the
in-flight fetch.

**OPEN — padding filter at `days >= 21`.** `_fred_releases` drops any source
seen on > 3 distinct dates (FOMC-style padding). From a Thursday, `days=21`
covers 4 Thursdays, so the weekly claims print is dropped entirely (≤ 14 days:
3, kept; 21: 4, dropped; 30: 5, dropped). `/macro/calendar` (`le=30`) can
reach it; the 14-day default cannot. NOT changed — his call (spec §7.5).
Pinned by `test_fred_releases_21_keeps_the_weekly_claims_print`,
`xfail(strict=True)`: an XPASS means someone fixed it and the marker must be
removed deliberately.

**Tests.** `backend/tests/test_macro_calendar_claims_2026_09_24.py` on the
fixture `backend/tests/fixtures/fred_release_dates_2026_09_24.json` (66 FRED
response rows: every pre-fix tier match, the 31 FOMC padding rows, 3 unmatched
negatives; no key), clock frozen at 2026-09-24 (`mc.datetime` subclass +
`_today_et`): per-name exclusions (upper-cased too) and the 8 real prints;
one source per `(kind, date)` across the fixture with the matched-kind set
unchanged; `_fred_releases(14)` exact rows (claims Thursdays only, no retail,
one gdp / pce source, no fomc); `compute(14)` one claims row per ISO week; the
lock (concurrent cold callers → one compute; `force=True` and `days=7`
recompute; a raising compute releases the lock); the strict xfail above.

## 2026-09-30 — past_events (history)

**Why.** The 🛡️ Resiliency tab on Chart Maps (Ajay 2026-09-30, "Stocks that are not
going to by more than 0.5% during a T1 event like FOMC … track T2s as well") needs the
PAST T1/T2 data days. No historical event list existed: `_fred_releases` reads UPCOMING
dates only (`realtime_start = today`) and its >3-dates padding filter drops every
claims week, so it cannot be widened to the past.

**What.** `macro_calendar.past_events(start, end, *, max_tier=2, fetch=None, force=False)`:

- FRED per-release `/fred/release` (the NAME) + `/fred/release/dates`
  (`realtime_start=start`, `realtime_end=9999-12-31`, `include_release_dates_with_no_data=false`,
  `sort_order=asc`, `limit=10000`) for `HISTORY_RELEASE_IDS = (50, 10, 54, 53, 9, 192, 194, 180, 46)`.
  Each id only SELECTS a fetch; the release NAME is classified by `_match_tier` — the one
  classifier (a renamed or shadow name classifies to nothing and contributes nothing).
- FOMC rows from `FOMC_DECISION_DATES` (label "FOMC decision", source "Federal Reserve FOMC
  calendar", `release_id None`). FRED 101 is never fetched. The constant gained the three
  2024 decision days **2024-09-18, 2024-11-07, 2024-12-18** (meetings Sep 17-18, Nov 6-7,
  Dec 17-18 on federalreserve.gov/monetarypolicy/fomccalendars.htm, re-fetched 2026-09-30)
  so the 2-year price cache has its full FOMC history.
- Rows `{date, kind, tier, label, source, release_id}`, sorted `(date, tier)`, deduped on
  `(kind, date)`, `start <= date <= end`, `tier <= max_tier`. PPI is tier 2 (the module's own
  tiering; `TIER_TAXONOMY` omits it — his call #7 in the tab doc).
- `HISTORY_UNSOURCED = ("ISM mfg & services", "Fed-speaker remarks")` — taxonomy kinds with no
  FRED release, so no dated history; returned with every answer and printed on the tab.
- Soft-fails PER release: an error row `{release_id, reason}` where reason is `"HTTP <code>"`
  (`FredHTTPError`), `"no FRED key"`, or the exception CLASS — **never `str(exc)`**: a requests
  error string carries the request URL with the `api_key` (the `:165` leak in
  `_fred_releases` is untouched here). `available` = at least one release answered.
- Cached in-process per `(start, end, max_tier)` for `HISTORY_TTL_SEC` (= `TTL_SEC`, 6 h)
  behind its own `_HISTORY_LOCK` (double-checked, like `get_macro_calendar`); only a clean
  read (available, no error rows) is cached. An injected `fetch` bypasses the cache.
- `_fred_releases`, `compute`, `get_macro_calendar` and `imminent_events` are unchanged.

**Measured 2026-09-30 ~09:25 ET** (api container, read-only, key never printed; realtime
2024-09-01 → now; the fixture `backend/tests/fixtures/fred_release_history_2026_09_30.json`
is this capture):

| id | FRED name | `_match_tier` | dates | last | sec |
|---|---|---|---|---|---|
| 50 | Employment Situation | jobs, 1 | 24 | 2026-09-04 | 1.5 |
| 10 | Consumer Price Index | cpi, 1 | 24 | 2026-09-11 | 2.7 |
| 54 | Personal Income and Outlays | pce, 1 | 25 | 2026-09-30 | 1.5 |
| 53 | Gross Domestic Product | gdp, 2 | 25 | 2026-09-30 | 1.4 |
| 9 | Advance Monthly Sales for Retail and Food Services | retail, 2 | 27 | 2026-09-28 | 1.5 |
| 192 | Job Openings and Labor Turnover Survey | jolts, 2 | 25 | 2026-09-29 | 1.4 |
| 194 | ADP National Employment Report | adp, 2 | 26 | 2026-09-30 | 1.4 |
| 180 | Unemployment Insurance Weekly Claims Report | claims, 2 | 101 | 2026-09-24 | 1.6 |
| 46 | Producer Price Index | ppi, 2 | 24 | 2026-09-10 | 1.4 |

FRED revision-date rows count (retail 2026-09-28 Mon, GDP 2024-10-02) — his call #9 in the tab
doc. One cold read = 18 FRED calls ≈ 15–27 s; it runs only in the tab's background build.

**Tests.** `backend/tests/test_macro_calendar_history_2026_09_30.py` (17): exact per-kind
counts from the fixture, T1/T2 kinds, PPI tier 2, the 2024 FOMC rows, claims on Thursdays,
inclusive window + `max_tier`, dedupe, the cache and `force`; NEGATIVE: 101 never fetched,
one release HTTP 500 → one error row and no key in payload or logs (caplog), a requests-style
error string carrying `api_key=` → only the class name, all releases failing → unavailable,
never raises, a failed read is not cached, no key → "no FRED key", a name matching no tier or
a shadow name ignored, a release named "FOMC …" contributes nothing, `_fred_releases` untouched.
