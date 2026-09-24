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
     row so the schedule is the single source. **⚠ Verify annually** — extend the
     list when the Fed publishes the next year (~1.5 yrs ahead).
   - The FOMC window is **ET** (`_today_et`, matching `imminent_events`), not UTC:
     an FOMC at 2pm ET must still read as "today" in the evening even after UTC
     has rolled past midnight.

2. **The whole calendar came back empty.** `/releases/dates` is genuinely slow
   (measured >30s); the old `(20, 25)`-second timeouts both fired → `[]` → empty
   panel. Bumped to **`(45, 60)`**. The call is `asyncio.to_thread`-wrapped and
   6h-cached, so the longer timeout only costs a cold load.

3. **Cron warm-up.** Added a `crontab` entry warming `get_macro_calendar(days=14)`
   at 4am/10am/4pm ET (TTL is 6h) so a cold regime-page load never waits on the
   slow FRED call. `days=14` matches the page's fetch so the cache key lines up.
   Deploy needs **`cron`** for this to take effect (the timeout/FOMC fixes only
   need `api`).

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
