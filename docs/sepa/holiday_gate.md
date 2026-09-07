# Closed-day gate — no market alerts, no scans, on weekends and NYSE holidays

Ajay, 2026-09-07 (Labor Day, 11:35 ET): *"TOday is holiday so turn of alerts scans."*

## What had happened

The crontab's day-of-week field is `1-5`. A weekday holiday is still a weekday, so
on Labor Day every intraday job ran against **Friday's closing prices**:

| 09:00–09:05 ET | 16 `pivot_alert` pushes delivered to his phone (OGN, LNG, HLX "at the pivot"; EPC, C, HOPE, CVE, NEOG, IBKR, NWL, JHX, OXY, VRTX, KNTK, CNQ, TDW "approaching") |
| all day | `stage_out_alert` 180, `pankaj_alert` 64, `price_alert` 19 rows — muted kinds, so silent, but computed and logged |
| scheduled | 16:30 fast-scan, 16:42 breakout audit, 16:45 autopsy, 16:50 pullback scan, ICT levels, options scans, GEX history — all on a day with no bars |

Only the zone-edge loop already checked the holiday calendar (`zone_edge.in_session`,
fix 2026-09-05). Every other alert scan, the SEPA CLI and the paper-lane warms did not.

## The rule

**One calendar, three chokepoints.** `backend/market_hours/gate.py`.

- **Calendar:** `market_hours.reminder.ALL_HOLIDAYS` (NYSE full-closure days for 2026
  and 2027) plus weekends. `closed_reason(now)` → `"weekend"`, `"holiday YYYY-MM-DD"` or
  `None`. When the exchange publishes the next year, extend that set — nothing else.
- **Push (`push/sender.py`):** `send_to_all` / `send_to_user` drop every kind outside
  `gate.PERSONAL_KINDS` on a closed day *before* any device is touched and *before* a
  `push_history` row is written. Default is DROP: a new setup/pattern kind is
  market-driven until it is added to the personal pass-list (todos, flashcards,
  volleyball, household, sign-ins, health). Result: `{"sent": 0, "failed": 0,
  "total_targets": 0, "skipped": "holiday 2026-09-07"}` and one app-log line.
- **Jobs:**
  - `sepa.cli` commands in `MARKET_DAY_CMDS` (scan, fast-scan, alerts, breakout-audit,
    pullback-scan, trade-flash-watch, scalping-*, zero-dte-*, brief,
    market-gauge-preopen, vcp-watch, juggernauts) return 0 at dispatch on a closed day.
    `research-refresh`, `fear-greed-refresh`, `macro-indicators-refresh`, `scan-context`
    are not price reads and still run.
  - Standalone crontab modules run through `python -m market_hours.gate <module> [args]`
    (`trading.autopsy`, `trading.catalyst_entry --warm`, `supply_demand.zone_store`,
    `ict.engine`, `options.scanner`, `options.gex_history`, `catalysts.gabbar_watch`,
    `supply_demand.demand_alerts`) or `--call pkg.mod:func` (portfolio drop attribution).
    The runner exits 0 without importing the target when closed.

### Manual override

`CHEETAH_IGNORE_HOLIDAY=1 python -m sepa.cli fast-scan --mode broad` forces a run —
for a measured scan on a holiday afternoon or a backfill. Never set it in the crontab
(a test pins that).

### Where it shows

- ℹ️ Rules panel ▸ Zone alerts: "Closed days push nothing market-driven and run no
  scan … (next: YYYY-MM-DD)" — built from the same calendar.
- `/alerts` is simply quiet on those days; the app log carries
  `GATE closed (holiday 2026-09-07) — <module> skipped` per job and
  `push.sender: kind=… dropped — market closed` per push.

## Also fixed the same morning: the todo-reminder retry storm

`push_history` held **4,423,815** `todo_reminder` rows with `sent=0` (34,441 on Labor
Day alone). Vineetha's phone had dropped its push subscription, so every due todo of hers
failed to deliver, and `todos.reminder.fire_due` treated "not delivered" as "retry next
minute" — forever. Now `MAX_NOTIFY_ATTEMPTS = 3`: the todo's `notify_attempts` counter
is bumped on each failed pass and the third strike marks it notified with a WARNING line
(the todo stays on the list). The old rows are noise and can be purged
(`db.push_history.delete_many({"kind": "todo_reminder", "total": 0})`) — Ajay's call.

## Tests

`backend/tests/test_market_hours_gate.py` — calendar (Labor Day closed, Tuesday open,
Saturday weekend, override), kinds (disjoint sets, every `default_prefs` kind
classified, unknown kind drops), sender (drop before device/history, todo still
delivers, trading day delivers), CLI (dispatch order source guard, `alerts` on a
holiday returns without running), runner (module skipped/run, `--call`), crontab
(every weekday price-reading module wrapped, no override in the file), rules line.
`backend/tests/test_todos_reminder_attempts.py` — delivered marks at once, undeliverable
gives up on the third strike.
