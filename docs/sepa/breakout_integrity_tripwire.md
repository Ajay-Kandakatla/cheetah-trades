# Breakout integrity tripwire — methodology

_Added 2026-06-18. Ajay invests real money off the "broke out today" flag and
asked for an automated self-check so the indicator can never silently drift from
the book._

## What it does

Every post-close, it **independently re-derives** whether each scanned name broke
out today, straight from raw price bars, and compares that to what the persisted
scan flagged. Any mismatch is logged and alerts (non-zero cron exit).

The reference definition (Minervini, *Trade Like a Stock Market Wizard*, p.203):

> a breakout = the latest **close is above the highest close of the prior 21
> bars** AND the latest **volume is > 1.5× the trailing 50-day average**.

## Why it carries its own copy of the formula

`backend/sepa/breakout_audit.py::is_breakout_today` implements the definition
**independently** — it does **not** call `volume.py`. That's deliberate: if
`volume.py`'s breakout formula ever drifts (a refactor, a threshold typo), the
audit's independent copy diverges and the tripwire trips. A self-check that
reused the same code couldn't catch a formula bug — only a stale-data bug.

`audit_latest()` returns:

```
{ok, checked, flagged_today, confirmed_today,
 false_positives: [...],   # scanner flagged it, but it's NOT a real breakout
 false_negatives: [...],   # a real breakout the scanner MISSED
 clean: bool, scan_ts, audited_at}
```

## How it runs

- **Cron** (`backend/crontab`) — `sepa.cli breakout-audit` at **4:42pm ET
  weekdays**, right after the 4:30 post-close fast-scan, so it audits today's
  fresh flags. Logs `CLEAN`, or `WARN` + exits non-zero on any discrepancy.
- **On demand** — `GET /sepa/breakout-audit` (owner-only; loads the whole
  universe's prices, ~1–2s) returns the live report.

## Baseline (the day it shipped)

Run across the live scan — **2,927 stocks, 0 false positives, 0 false
negatives.** 424 names made a new 21-day high that day; only 5 did so on >1.5×
volume (real breakouts). The other 419 (incl. BNY) were new highs on *light*
volume — correctly excluded. The flag matches the book on every name.

## Tests

`backend/tests/test_breakout_audit.py` — the reference definition (real breakout
vs light-volume new high vs no new high vs insufficient history), plus the audit
catching a planted false-positive and a planted false-negative.

## Follow-up (not done)

A push notification on a tripped wire (currently it's WARN log + non-zero cron
exit + the endpoint). The existing `notify_*` hooks are ticker-pref-keyed; an
"owner integrity alert" channel would be a clean small add if we want a phone
ping the moment it ever trips.
