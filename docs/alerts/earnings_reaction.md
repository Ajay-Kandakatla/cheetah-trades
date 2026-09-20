# 📣 earnings_reaction — earnings beat with institutional buying

**Shipped 2026-09-20 · ON by default · NOT MEASURED**

## The ask, verbatim

Ajay, 2026-09-20:

> "Also don't forget to alert me on earnings surprises I think stock witz also
> has it. I wanna make sure we are catching those in alerts as well."

One message earlier: *"We already have an earning calendar tracker"* — so this
is the PUSH the existing stack never sent, not a new tracker, not a new
calendar, not a second copy of the Earnings Flow tab.

And, the same day, on this kind and the three others shipped beside it:

> "Default on for any change of todays features Bondes or Potus or explosive
> growth or Earnings I wanna see all of them."

So it ships ON: `earnings_reaction` is in `push/subs.OWNER_KEEP_SET` and
`default_prefs()` carries `True`. The toggle is at **/notifications**.

## What fires

A name on the Earnings Flow tab's REACTED half whose THIS-QUARTER EPS surprise
is above zero. Every threshold below is read from the constant that enforces
it — `backend/chart_maps/earnings.py` — and the push body prints them from the
same constants, so the words cannot drift from the gate.

| Condition | Constant | Value today |
|---|---|---|
| Volume vs the bar's own 60-day **median** | `MIN_VOL_RATIO` | 1.5× |
| Close inside the bar's range | `MIN_CLOSE_LOC` | ≥ 0.60 (top 40%) |
| Dollar volume | `MIN_DOLLAR_VOL` (= `demand_reentry.LIQ_DEEP_USD`) | $50M |
| Direction | `is_institutional_buy` | up on the day |
| Bars of history before the median is a median | `MIN_BARS` | 60 |
| Look-back window | `LOOKBACK_DAYS` | 2 **sessions** |
| Surprise | `earnings_watch.last_report.surprise_pct` | **> 0** |
| Dedupe | `earnings_alerts._state_key` | once per (symbol, report date) |
| Singles before the digest | `growth.alerts.MAX_INDIVIDUAL` | 4 |
| Slots | `earnings_alerts.SLOTS_ET` | 08:25 + 17:35 ET, trading days |

## What never fires

- A **miss** or an **in-line** print (surprise ≤ 0) — `skipped_not_a_beat`.
- A **null** surprise — `skipped_no_surprise`.
- The **prior quarter's** surprise, which the calendar doc still carries until
  the 17:45 refresh — `skipped_surprise_pending`.
- A **pre-report run-up** (the UPCOMING half — the ATEX/BULL shape). The
  `upcoming_ignored` counter is the proof that half is never iterated.
- A **second push** for the same report, ever.
- A **closed day**: the kind is in `market_hours.gate.MARKET_ALERT_KINDS`, so
  `push/sender.send_to_user` drops it before any device or history row.
- A name whose **timing is unknown** on the fresh read — `skipped_timing_unknown`.
- Anything at all when the price cache's last bar is not the session the slot
  expects, or when the pass is run **in session**.

## The two calendar traps, and why the slots are 08:25 and 17:35

**Wrong quarter.** On the reaction day, before the 17:45
`sepa.earnings_watch` refresh, a reporter's doc still has
`next_date = report_date` and `last_report` = the PRIOR quarter. The tab shows
that stale figure on its REACTED tiles; this pass refuses it (§ open items,
item 5 — fixing the tab is a separate decision).

**The roll.** At 17:45 the doc rolls (`next_date` → next quarter,
`last_report` → this report) and `chart_maps.earnings.phase_for` then reads an
AMC reporter as UPCOMING, so `scan()` drops it. The evening pass must therefore
run **before** 17:45.

| Slot | Catches | Why it can |
|---|---|---|
| **17:35 ET** | names that reported after yesterday's close (reaction bar = today) | the 16:30 broad fast-scan has patched today's CLOSED bar; before the 17:45 roll |
| **08:25 ET** | names that reported before yesterday's open (reaction bar = yesterday) | yfinance publishes a surprise only once the report date is past, so the evening pass could not see it |

Both slots are outside RTH: between ~10:00 and 16:30 the hourly `vcp-watch`
patch leaves today's **partial** bar as the cache's last row, and scoring a
half session as a reaction is exactly the ATEX mistake in another costume.

## The five traps the 2026-09-20 critique found, and the answer to each

| # | The trap | The answer in the code |
|---|---|---|
| F1 | The calendar's `when` is None for most near reporters (1,646 of 2,071 docs after the 2026-09-18 refresh), so an AMC reporter would be anchored like BMO and its **pre-report** bar would push — burning the dedupe key the real reaction needed | The timing comes from the **fresh** read, never the doc; `when` None → `skipped_timing_unknown`, no claim. `calendar_when_none` counts the doc side |
| F2 | `_calendar_rows` looked back 2 **calendar** days, so every Friday reporter (53 of 810 recent reports) was dropped on Monday before its phase was read | `LOOKBACK_DAYS` counts **sessions** (`chart_maps.earnings._trading_days_back`). Owner-visible change: a Friday AMC reporter now appears on the tab on **Monday** |
| F3 | A failed yfinance read looked identical to "the number is not out yet" | `this_quarter_report` returns a status; `fetch_failed` is counted separately after one retry, and at ≥ half the reacted names the pass carries a `reason` onto /alerts |
| F5 | No price-cache freshness guard — a pre-market Scan click patches today's date in, and every BMO reporter would drop silently at 08:25 | `run()` compares `load_prices("SPY").index[-1]` against the slot's expected session and records `ran: False` with the bar it found |
| F7 | An estimated report date drifts by a day, so `last_report.date == report_date` would never come true and the kind would be permanently silent | The match is on the **reaction date**: the fresh report's own date and timing are re-anchored through `earnings_picks.reaction_read` and must land on the bar `scan()` scored |
| F9 | The 08:25 title said "reacted UP" about **yesterday's** bar | The title carries the reaction date in both slots |

## 2026-09-20 — two follow-ups on the session window and the fetch cost

**`CHEETAH_IGNORE_HOLIDAY=1` no longer widens the window the wrong way.**
`market_hours.gate.closed_reason` answers None for *every* day under that env,
weekends included — right for the gate (it exists so a manual run can execute
on a closed day), wrong for a look-back, because a window is not a permission.
Un-guarded, a Monday `--dry-run --force` check would have counted Sunday and
Saturday as sessions, opened the calendar window at the Saturday, and dropped
every Friday reporter — F2 again, in the one run most likely to be read as
proof that the fix works. `_trading_days_back` now tests the weekday itself
before it asks the gate, so a Saturday or a Sunday never counts whatever the
env says. A **holiday** still counts as open under the override: the gate owns
that table and this module keeps no second copy, so the cost is one session of
window on the handful of manual runs made across a holiday. Pinned by
`test_the_override_env_never_makes_a_WEEKEND_count_as_a_session`.

**The pass no longer fetches every REACTED name.** `this_quarter_report` takes
the stored calendar doc first and only reads yfinance when the doc does not
describe *this* report, but `run()` had no way to hand it those docs, so the
`"doc"` branch was dead in cron: every reacted name paid a network read, plus
`FETCH_RETRY_SLEEP_SEC` again whenever the provider was down. `_scan` now
fills `doc_reports` once per pass from the same collection `scan()` read
(`chart_maps.earnings._calendar_rows`) when the caller injected nothing, and
the new `doc_hits` counter on the summary says how many names cost no network
read. Cost only — a doc whose `last_report.date` does not match the report
being scored is still ignored, and any failure of the read falls straight back
to fetching, so the numbers the pass publishes are unchanged.

## Sources

yfinance (calendar + surprise, via `sepa/earnings_watch.py`) and Massive
(bars, via `sepa/prices.py`). **StockTwits has no earnings or surprise feed** —
checked 2026-09-20; that connector serves sentiment, message volume and
trending symbols only.

## NOT MEASURED

The institutional read is an **owner setting**, calibrated on two names on the
2026-08-19 tape (TGT and BULL) and stated as such in the module that owns it.
There is no forward measurement of this signal and no CI. The related studies
in this tree both measured **null**: the entry-trigger study (2026-09-15 —
confirmation entries are cushion, not edge) and the 8-K event study
(2026-09-01 — no chase edge after a +20% day-0 pop). The push body says
"NOT measured · event notice, not a recommendation" on every send.

## The replay — a phone-load COUNT, not an edge claim

`backend/scripts/earnings_reaction_replay.py` counts how many pushes each of
the last N sessions would have carried, and what each candidate surprise floor
would do to that count. It measures **nothing** about what the pushed names did
next.

    docker exec -i -w /app cheetah-market-app-api-1 \
        python - --sessions 60 --out /tmp/earnings_reaction_measured.json \
        < backend/scripts/earnings_reaction_replay.py
    docker cp cheetah-market-app-api-1:/tmp/earnings_reaction_measured.json <scratch>/
    cp <scratch>/earnings_reaction_measured.json backend/scripts/

Run it **outside RTH** — the cache's last bar is a partial bar in session.
`backend/scripts/earnings_reaction_measured.json` currently holds an explicit
`{"pending": true}` placeholder; the main session replaces it with the real
output and fills the two tables below.

### Would-be pushes per session (last 60 sessions)

| | total | sessions with any | median | p90 | max | busiest day |
|---|---|---|---|---|---|---|
| (to be filled by the replay) | | | | | | |

### Surprise floors (REPORT ONLY — no floor ships)

| floor | total | median/session | max | busiest |
|---|---|---|---|---|
| 0% | | | | |
| 2% | | | | |
| 5% | | | | |
| 10% | | | | |
| 20% | | | | |
| 50% | | | | |

### Institutional buying on a MISS (excluded today)

| total | median/session | max |
|---|---|---|
| | | |

**Both anchorings.** The replay computes the reaction bar two ways —
`last_report.when` (the confirmed stamp, which the live pass uses) and the
calendar doc's own `when` (an estimate, None for most near reporters, anchored
like BMO). The JSON's `live_anchoring` names the one the cron uses; a count
taken off the other anchoring does not describe the cron.

Standing caveats, repeated in the JSON: a **census** over the calendar's
decision universe, not a sample, so there is no CI; the calendar holds only the
LAST report per name; docs nulled by the 2026-09-18 fetch-pool fallback
undercount; the ≥ 5% room gate cannot be replayed because `zone_store` keeps
only the latest bands, so `would_skip_room` comes from live passes only.

## Where it shows up

- **Phone**: the push itself, with the reaction date in the title.
- **/alerts**: a "Daily passes" row — schedule, last stamp in ET, the counters
  as chips, and a `reason` chip when the provider went dark.
- **/notifications**: the 📣 toggle and the detail text.
- **ℹ️ Rules panel ▸ Zone alerts ▸ Alerts**: one line built from the
  `chart_maps.earnings` constants (`supply_demand/rules_info.py`).
- **Board**: Chart Maps ▸ Earnings Flow — every push links to
  `/chart-maps?tab=earnings&symbol=SYM`.

## Running it by hand

    docker exec -w /app cheetah-market-app-api-1 \
        python -m chart_maps.earnings_alerts --dry-run --force

`--dry-run` reads the dedupe state and sends nothing; `--force` skips the
session and freshness guards (smoke runs only). The cron line wraps it in the
closed-day gate:

    35 17 * * 1-5  python -m market_hours.gate chart_maps.earnings_alerts
    25  8 * * 1-5  python -m market_hours.gate chart_maps.earnings_alerts

A crontab change does **not** ship with a deploy — the cron container
bind-mounts the main tree's file, so verify in-container after promotion.

## Open — HIS call, nothing decided here

1. **A surprise size floor** ("only beats above X%"). The floors table above is
   the input; choosing one is a new numeric threshold (Rule #1).
2. **Should the standing ≥ 5% room / ≤ 1% proximity gate bind this kind?**
   Today it is context only and `would_skip_room` counts how often it would
   have refused. This is an event notice, not a demand entry.
3. **The root causes behind F1/F2**: write `when` back to the calendar doc
   without rolling `next_date`, or repair the refresh pool. Both change the
   Earnings Flow tab and `earnings_picks`, not just this push.
4. **Friday AMC reporters now appear on the tab on Monday** (the sessions
   look-back). Keep?
5. **The tab still shows the PRIOR quarter's `surprise_pct`** on REACTED tiles
   until 17:45, and `phase_for` turns rolled AMC reporters UPCOMING. Fixing
   either changes what the tab lists.
6. **Three morning pings** — 08:08 ✨, 08:15 🔥📐, 08:25 📣. Fold into one?
7. **Institutional buying on a MISS** is excluded by the beat rule; the replay
   reports the count.
8. **Wording** — label "Earnings beat, institutions bought", emoji 📣, title
   "📣 SYM beat by +6.2% — reacted UP +8.4% on 3.1× volume (2026-09-18)".

## Tests

- `backend/tests/test_earnings_reaction_alerts.py` — the gate, the body, the
  pass, the guards, and every negative above.
- `backend/tests/test_earnings_reaction_replay.py` — the classifier, the
  per-session split, the floors table, both anchorings, the committed JSON.
- `backend/tests/test_chart_maps_earnings.py` — the sessions look-back and the
  three additive `scan()` counters.
- `backend/tests/test_alert_status.py` — the six-pass payload and the schedule
  strings built from `SLOTS_ET`.
- `backend/tests/test_rules_info.py` — the two panel lines and the source
  guards.
