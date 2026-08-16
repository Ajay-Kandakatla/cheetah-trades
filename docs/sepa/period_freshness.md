# Quarterly-cadence freshness — "is this data still from the current period?"

**Code:** `backend/observability/period_freshness.py` ·
**Check:** `health_audit.check_13f_quarter_current` ·
**Cron:** 1st of the month, 8:20am ET

> Ajay 2026-08-16, seeing the APGE institutional-flow modal read *"As of Q1 2026
> (Mar 31, 2026)"*: **"The accumulations are dated now can you check… Make a
> rule to check for updated date.. Monthly"**

---

## Why the existing health checks could not catch this

Every other check in `health_audit` measures **how old a file is**. That
question is useless here. The 13F holder cache (`whales_cache`) has a 24-hour
TTL and refreshes lazily whenever a ticker is viewed — when Ajay opened APGE,
the payload had been fetched *minutes earlier*. An age check calls that green
while the **content** inside it is a whole quarter behind.

So this check asks a different question:

> Given today's date, which 13F quarter *should* be public by now — and is that
> what the data actually contains?

## The 45-day rule

SEC Rule 13f-1 gives institutions **45 calendar days** after quarter end to
file:

| Quarter ends | Filings due | + 21d grace → we expect it |
|---|---|---|
| Mar 31 | May 15 | Jun 5 |
| Jun 30 | **Aug 14** | **Sep 4** |
| Sep 30 | Nov 14 | Dec 5 |
| Dec 31 | Feb 14 | Mar 7 |

The grace period exists because funds file across the whole deadline week and
the upstream provider ingests afterwards. Flagging on day 46 would cry wolf
every single quarter.

**This is why the APGE modal was not a bug on 2026-08-16.** The Q2 deadline had
passed only two days earlier, so Q1 was still the correct headline.
`test_expected_quarter_two_days_after_the_deadline_is_still_q1` locks that.

## What it reports

`audit_whales_cache()` samples 300 cached tickers and reports:

- `expected_quarter` / `expected_label` — what should be public
- `rolled_pct` — share of tickers reporting that quarter or newer
- `newest_seen` — the newest quarter anywhere in the sample
- `mixed_quarter_payloads` — payloads containing more than one report date

It passes at **≥50% rolled**. Never 100%: small caps keep a permanent tail of
funds that file late or not at all, so a strict rule would sit red forever.

Measured 2026-08-16: 297 sampled, 100% at Q1-or-newer, newest seen Q2 2026 —
green, correctly.

## The finding worth acting on separately

**100% of sampled payloads mix quarters.** APGE alone had 6 funds reporting
Mar 31 and 4 reporting Jun 30 in one payload, and the modal sums them:

> `+$2.1B bought · −$1.0B sold · Net inflow: +$1.1B`

That total adds one fund's Q1 delta to another fund's Q2 delta, so it describes
no single period. `_summarize_period` picks the **mode** date for the headline,
which is why the label said Q1 while the span said `2026-03-31 → 2026-06-30`.

The check counts this (`mixed_quarter_payloads`) but does **not** fix it —
fixing it means deciding whether to show one quarter's funds only, or to label
each fund's row with its own quarter. That is a product call, not a bug fix,
and it is left open deliberately.

## It never pushes

Severity is **WARN**, never CRITICAL. `health_audit` only alerts on CRITICAL,
so a lagging provider shows up on `/health` and in the monthly log without ever
buzzing a phone — the push keep-set is three kinds (`todo_reminder`,
`pivot_alert`, `position_alert`) and this is not one of them.
`test_health_check_is_warn_never_critical` locks it.

## Tests

`backend/tests/test_period_freshness.py` — 21 tests, every date injected so
quarter-boundary behaviour is testable today rather than once a quarter.
Negatives: empty cache, payloads with no period block, a broken collection, a
partial roll on both sides of the floor, and the day-after-deadline case that
must *not* fire. Plus a test that the monthly cron entry actually exists —
the rule is only real if it is scheduled.
