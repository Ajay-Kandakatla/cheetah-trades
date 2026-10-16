# 🎚️ tape_control — buyers in control on the tape, for pinned names (IREN, 2026-10-16)

## The ask

Ajay, 2026-10-16 ~06:48–06:52 ET, two messages (his spelling kept):

> "Can you add a watcher tape for IREN please."

> "I wwant you to alert me when the Buyers are winning in tape for IREN today."

**Status: LIVE since 12:19 ET 2026-10-16 (main `b2a0604b`), owner-only, ON for him. UNMEASURED.** No study in this app
measures this check alone. The Tape verdict's forward ledger (`GET /orderflow/ledger/accuracy`) grades the five-check
verdict, not check 3. A ring is a read of the tape, not an entry. Not advice.

Module: `backend/orderflow/tape_control.py`. Spec: BUILD_SPEC7 + AMENDMENTS7 (A1–A12) + DECISIONS7 (D1–D9) in the
session scratchpad.

## What fires

The Tape tab's own check 3, **by call** (no new tape math, no new provider):

- `signals.delta_check` over `tape.analyze_tape(trades)["delta"]`.
- In control = the session's cumulative delta **> 0** AND the last `tape.LATE_WINDOW_MIN` (30) minutes' delta **>= 0**.
- Regular prints only (`tape.split_by_kind(...)["flow"]`). Form T and odd lots count as regular flow, so pre-market
  prints are in the session delta — the same base the Tape tab reads.
- Sides by the **tick rule**: `analyze_tape` is called with no quotes. The Tape tab classifies against the NBBO where it
  can, so the two reads can differ. Every push ends "tick rule (the Tape tab's quote-rule read can differ)".
- "Last 30 min" is cut from the LAST print, not the clock (`tape.delta_summary`). During a halt the window freezes and
  each poll repeats the pre-halt read, so a halt never makes a flip.

One push when the read turns to buyers in control. The day's first read rings too when buyers already lead (A6, his call
Q13). Never again while it holds. Again only after a poll reads it lost.

## What never fires

- A poll that cannot read the tape. That is a **fault, never a False**: no ring, no re-arm, `faults` +1. Faults are
  `no_prints`, `no_regular`, `truncated` (the pull hit `tape.MAX_TRADE_PAGES` 24 × 50k, newest prints missing),
  `rate_limited` (more than `MAX_429` HTTP 429s), `error`, `budget` (the read would start after `START_BY_SEC`) and
  `no_mongo`.
- Sellers taking over (True → False): no push. The /alerts row shows it (his call Q7).
- An expired pin: never fetched.
- Outside 09:32–16:00 ET (`trade_flash.WATCH_OPEN_ET` / `WATCH_CLOSE_ET`). `run_pass` checks `trade_flash.in_window`
  itself.
- A closed day: `tape_control` is in `market_hours/gate.MARKET_ALERT_KINDS`, and `sepa.cli` skips `trade-flash-watch` on
  closed days.

## "Today" and pre-market

- `day` = the ET date of the poll clock (`trade_flash._now_et()`). It is never `date.today()` (the container clock),
  never a walk-back, and never `engine.compute`'s 09:45 prior-session rule.
- `tape.fetch_trades` reads the ET day 04:00–20:00. The first poll (09:32) therefore reads 04:00–09:32. Its "last 30 min"
  is mostly pre-market.
- Before 09:45 the Tape tab itself shows the PRIOR session (`engine.SESSION_MEANINGFUL_AFTER`). A ring at 09:32–09:42 can
  open onto yesterday's tape. This only matters if a pin becomes standing (his call Q5).

## Constants

| name | value | tag |
|---|---|---|
| `WATCH` | `{"IREN": "2026-10-16"}` — symbol → the LAST session (inclusive) it is read and rings; `None` = standing | `# Ajay 2026-10-16` |
| `KIND` | `"tape_control"` | `# MINE` |
| `EVENTS_COLL` / `STATE_COLL` | `"tape_control_events"` / `"tape_control_state"` | `# MINE` |
| `MARK` | 🎚️ (U+1F39A, not 🎛️ U+1F39B `scalp_tape`) | `# MINE` |
| `RULE_WORD` | `"tick rule"` | Cheetah default |
| `START_BY_SEC` | `= tape_burst_kinds.KINDS_BUDGET_SEC` (200 s) | `# MINE` (reuse) |
| `MAX_429` | `3` | `# MINE` (A4) |
| `MAX_PUSH_ATTEMPTS` | `2` | `# MINE` (A3) |
| `tape.LATE_WINDOW_MIN` | `30` | Cheetah default (reused, never retyped) |
| `trade_flash.WATCH_OPEN_ET` / `WATCH_CLOSE_ET` | 09:32 / 16:00 ET | `# Ajay 2026-10-14` (reused) |
| `alert_status.CADENCE_SEC["tape_control"]` | `300` (the trade-flash line's `2-57/5`) | derived |

## Where it runs and what it costs

- On the EXISTING `2-57/5 9-15 * * 1-5 /usr/local/bin/python -m sepa.cli trade-flash-watch` line. There is no crontab
  line of its own, because a deploy never ships the host-mounted crontab.
- `sepa/cli.py` calls `tape_control.run_pass` AFTER `trade_flash.run_watch` and AFTER the zone and burst heartbeats, in
  its own try (A1). `trade_flash.py` is not edited. A fault here never touches the zone or burst passes.
- It beats `engine_heartbeat` `tape_control` only when the pass returns `ran: True`. `ran` = no active pin, or at least
  one good read (A5). A day of all-fault polls beats nothing, and `health_audit.check_tape_control_heartbeat` goes amber.
- `--kinds tape_control` runs it alone among the kinds (the zone pass always runs). `--dry-run` reads the tape and writes
  nothing.
- Cost per poll, per active pin: ONE `tape.fetch_trades(sym, day, max_429=MAX_429)`. That is ⌈prints so far / 50,000⌉
  pages, each ≤ `tape.FETCH_TIMEOUT_SEC` 10 s. Then `analyze_tape`'s pure math. No NBBO, no bars, no snapshot write, no
  ledger write.
  - Measured 2026-10-16: 173,803 trade rows fetched in 18.2 s at 11:11:40 ET (the Q1 read below).
  - The 12:13 ET dry pass read 220,984 prints.
  - A full IREN session is ≈ 301,460 prints (the 10-09 snapshot), ~25% of the page cap.

## State machine — `decide(prev_state, read)` (pure)

One `tape_control_state` doc per pin per ET day, `_id` `SYM:day`.

| prev `in_control` | read | ring | after |
|---|---|---|---|
| no doc today / None (faults only) | fault | no | unchanged, `faults` +1 |
| no doc / None | True | **YES** — the day's first read rings; W2 ends " · first read today" and W6 reads "buyers led at the first read today HH:MM ET" (A6) | in control, `since` = this read |
| no doc / None | False | no | not in control (armed) |
| False (armed) | True | **YES** (the flip) | in control, `since` = this read |
| False | False | no | unchanged |
| False | fault | no — stays armed | unchanged, `faults` +1 |
| True (holding) | True | **no**. One exception, the A3 retry: the last ring reached no device and `push_attempts < MAX_PUSH_ATTEMPTS` | holding |
| True | False | no — RE-ARM; the delivery bookkeeping resets | not in control |
| True | fault | **no, and NOT re-armed** (a fault is not a False) | holding, `faults` +1 |
| expired pin | — | `decide` is never called, nothing is fetched | counted `expired` |
| a new ET day | — | a new `_id` — starts at "no doc" | — |

**Delivery (A3).** The pass claims the state BEFORE the send, then patches it AFTER the send with the outcome.

- The claim uses an optimistic `rev`. A lost claim = `lost_race`, no ring. A `DuplicateKeyError` on the first upsert is
  also a `lost_race` (A9).
- `record_and_push` reached ≥ 1 device → `rang`.
- Otherwise `push_attempts` +1 and `not_pushed_reason` is set to one of `no_device` / `not_sent` / `no_mongo` /
  `insert_failed` / `error`.
- The next poll that still reads buyers in control rings again, up to `MAX_PUSH_ATTEMPTS`. At the cap the flip is
  `exhausted`.
- A False read resets the attempts.

## Collections and the /alerts row

- `tape_control_state` — the state machine above: `rev`, `in_control`, `since`, `since_hhmm`, `last_read`,
  `last_read_at`, `faults`, `last_fault`, `rings[]` (`at`, `hhmm`, `event_id`, `pushed`, `first_read`, `retry`,
  `not_pushed_reason`), `rang`, `push_attempts`, `not_pushed_reason`, `exhausted`, `first_read`.
- `tape_control_events` — one doc per ring, `_id` = `trade_flash.event_id(sym, day, hms)`, `$setOnInsert`. This is its
  own collection: a ring id can collide with a burst window second in `tape_burst_events`.
- `alert_pass_latest` `_id "tape_control"` — the `COUNT_KEYS` counters (`pins`, `active`, `expired`, `read`, `faults`,
  `in_control`, `rang`, `pushed`, `lost_race`, `skipped_budget`) and the `reason`.
- `GET /alerts/status` → `passes.tape_control` holds:
  - the counts, `cadence_sec` 300 and `window`;
  - `pins[]`, each with `symbol`, `date`, `until`, `active`, `state`, the served `text`, `url` and `rang`;
  - the `note`.

  These come from `alert_status.read_tape_control` → `tape_control.status_block`.
- The page's 🎚️ row sits under the 🎢 🗺️ TAPE strip. It prints each of today's pins' `text` and the `note` verbatim
  and composes no pin sentence.
- The push opens `/sepa/IREN?tab=tape&from=alerts`.
- Keep-set: in `push/subs.OWNER_KEEP_SET`. `default_prefs` is False for everyone else.

## Served words — the W-table (verbatim from `tape_control.py`)

`{…}` is computed. Signs come from `{:+,}` / `{:+.1f}` (ASCII `+` / `-`), as in `signals.delta_check`.

| W | where | exact format |
|---|---|---|
| W1 | push title (`TITLE_FMT`) | `🎚️ {lead} — buyers in control on the tape`, plus `trade_flash.MORE_FMT` ` +{n} more` when 2+ pins ring in one poll |
| W2 | push body line = the /alerts item (`headline`) | `{SYM} · session delta {pct:+.1f}% of volume ({delta:+,} shares), last {n} min {late:+,} shares · ${price:.2f} · {hhmm} ET{FIRST} · tick rule (the Tape tab's quote-rule read can differ)` |
| FIRST | inside W2 | ` · first read today` when the ring is the day's first read (A6), else empty |
| W3 | push / item url (`URL_FMT`) | `/sepa/{sym}?tab=tape&from=alerts` |
| W4 | pin `waiting` | `watched {open}–{close} ET on trading days · no read yet today` |
| W5 | pin `no_read` | `no read yet today · {hhmm} ET poll not read: {FAULT_WORDS[why]}` |
| W6 | pin `in_control` | `{LEAD} · {NUM} · read {hhmm} ET{RANG}{EXH}{FTAIL} · tick rule` |
| LEAD | inside W6 | `buyers led at the first read today {since_hhmm} ET` (first read) / `buyers in control since {since_hhmm} ET` |
| EXH | inside W6 | ` · rang {once\|twice} to no device — check Notifications` when the flip is `exhausted` |
| W7 | pin `not_in_control` | `{WHO} since {since_hhmm} ET · {NUM} · read {hhmm} ET · rings when buyers take control{RANG}{FTAIL} · tick rule` |
| WHO | inside W7 | delta < 0 → `sellers in control for the session`; delta == 0 → `session delta flat`; delta > 0 and last 30 min < 0 → `sellers took the last {n} min` |
| W8 | pin `expired` | `pin ended at the close of {until} · not read` |
| NUM | inside W6 / W7 | `session delta {pct:+.1f}% of volume ({delta:+,} shares), last {n} min {late:+,} shares · ${price:.2f} · last print {last_print_et} ET` |
| RANG | W6 / W7 | ` · rang {h1}, {h2} ET`; each `h` gets ` ({NOT_PUSHED_WORDS[reason]})` when its `pushed` is False |
| FTAIL | W6 / W7 | ` · {hhmm} ET poll not read: {FAULT_WORDS[why]}` when the last fault is newer than the last read |
| W9 | pass `note` | `UNMEASURED — the Tape verdict's forward ledger (GET /orderflow/ledger/accuracy) measures the five-check verdict, not this check alone. Not advice. Sides by the tick rule (the Tape tab's quote-rule read can differ).` |
| W10 | pass `reason` | `no pin active — every pin has ended` / `state store unreachable — no read, no ring` / `outside the watch window — not read` (returned, not recorded) / the fault words joined by `; ` when no pin was read |
| W11 | ℹ️ rules line | `rules_info._tape_control_lines`, built from `tape.LATE_WINDOW_MIN`, `RULE_WORD`, `MAX_PUSH_ATTEMPTS`, `CADENCE_SEC`, `WATCH_*`, `UNMEASURED_NOTE` |
| W12 | log | `TAPE-CONTROL: {counts…, reason}` |

`FAULT_WORDS`:

| key | words |
|---|---|
| `no_prints` | no prints from the provider |
| `no_regular` | no regular prints yet |
| `truncated` | the pull hit the page cap — the newest prints were missing |
| `rate_limited` | the provider kept answering HTTP 429 (rate limited) |
| `error` | the tape read failed |
| `budget` | the poll ran out of time |
| `no_mongo` | the state store was unreachable |

`NOT_PUSHED_WORDS`:

| key | words |
|---|---|
| `no_device` / `not_sent` | reached no device |
| `no_mongo` | not sent: the push store was unreachable |
| `insert_failed` | not sent: the ring was not recorded |
| `error` | not sent: the send failed |

The live row at 12:22 ET (the WP-M capture,
`frontend/src/pages/__fixtures__/alerts_status_tape_control_2026_10_16.json`) read:

> `sellers in control for the session since 12:22 ET · session delta -8.7% of volume (-2,588,125 shares), last 30 min -451,184 shares · $27.75 · last print 12:22:42 ET · read 12:22 ET · rings when buyers take control · tick rule`

## Deploy — the house order for any new LIVE kind (A2)

The devices get the key BEFORE the cron carries the code. The day's first ring can then never go to zero devices. This
order was used on 2026-10-16:

1. api + frontend.
2. `owner_prefs_apply`: read the dry diff, then `--apply`. His 4 devices went `tape_control` None → True.
3. Verify every owner device reads `true`.
4. Cron.

```bash
./deploy-cheetah-main.sh api frontend
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.owner_prefs_apply
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.owner_prefs_apply --apply
docker exec cheetah-market-app-mongo-1 mongosh cheetah --quiet --eval 'db.push_subscriptions.find({user_email:"ajaykandakatla@gmail.com"},{label:1,"prefs.tape_control":1,_id:0}).toArray()'
./deploy-cheetah-main.sh cron
```

`scripts/owner_prefs_apply.py` needs no edit: it reads `OWNER_KEEP_SET`. The live proof is the cron log line
`TAPE-CONTROL: {...}` and `passes.tape_control.as_of` on `GET /alerts/status`. The first live pass was stamped
12:22:00 ET: `pins 1, active 1, read 1, faults 0`.

## The tick-vs-quote read for IREN (Q1's numbers — facts, not a forecast)

**One read at 11:11:40 ET, 2026-10-16** (session so far; 173,803 trade rows / 335,881 quote rows; fetch 18.2 s /
39.7 s; 171,030 regular prints):

| | tick rule (what the push uses) | quote rule (`analyze_tape(tr, quotes=q)`, method "mixed", 53.7% quote coverage) |
|---|---|---|
| session delta | −1,771,997 sh = −8.1% of volume | −1,298,403 sh = −5.9% of volume |
| last 30 min | −670,568 sh (negative) | −663,090 sh (negative) |
| check 3 | false | false |

On the prints the quote rule classified, the tick rule agreed on 90.3% (`tick_agreement_pct`).

Two more reads, same shape:

- The 12:13 ET dry pass (`run_pass(dry_run=True)`) read 220,984 prints: sellers in control, −8.9% of volume, $27.65,
  zero writes.
- The spec critic's print-level agreement from the STORED IREN snapshots: 86.6% (2026-10-07) and 88.5% (2026-10-09).

These are stored-snapshot facts about those days, not a rate for any other day.

The one-time read, re-runnable inside the api image (`PYTHONPATH=/app`) — the same calls as the run that produced
the numbers above:

```python
import json, time
from datetime import datetime
from zoneinfo import ZoneInfo
from orderflow import tape, quotes, signals
ET = ZoneInfo("America/New_York")
now = datetime.now(ET)
day = now.date()
t0 = time.time()
tr = tape.fetch_trades("IREN", day)
t1 = time.time()
q = quotes.fetch_quotes("IREN", day)
t2 = time.time()
out = {"as_of_et": now.strftime("%H:%M:%S"), "trades_rows": len(tr), "quotes_rows": len(q),
       "fetch_trades_s": round(t1 - t0, 1), "fetch_quotes_s": round(t2 - t1, 1)}
for name, a in (("tick", tape.analyze_tape(tr)), ("quote", tape.analyze_tape(tr, quotes=q))):
    d = a["delta"]
    out[name] = {"classification": a.get("classification"), "delta": d["delta"], "late_delta": d["late_delta"],
                 "delta_pct_of_volume": d["delta_pct_of_volume"], "check3": signals.delta_check(d)}
print(json.dumps(out, default=str))
```

## HIS CALLS (each ships with the default shown; nothing here is decided for him)

- **Q1 Side classification.**
  - **Default: the tick rule** (D2; cheap, said on every push).
  - Alternative: the quote rule his Tape tab uses — one NBBO pull per poll (up to `quotes.MAX_QUOTE_PAGES` 40 pages),
    so the push agrees with the panel.
  - Today's read: 11:11:40 ET, tick −8.1% vs quote −5.9% of volume, check 3 false on both; 90.3% tick agreement on the
    quote-classified prints; stored snapshots 86.6% (10-07) and 88.5% (10-09). The NBBO pull took 39.7 s.
- **Q2 The definition (K1).**
  - **Default: the Tape tab's check 3** — session delta > 0 AND last 30 min ≥ 0.
  - Alternatives: the session delta alone; the last 30 min alone.
- **Q3 The edges.**
  - **Default: `>` on the session** (flat = not in control), **`>=` on the last 30 min** (flat = still in control) —
    `signals.delta_check:119`.
  - Changing them changes the Tape tab's verdict too (one engine).
- **Q4 When it rings (K2).**
  - **Default: on the flip, re-armed after a poll that reads it lost** (a flicker rings again).
  - Alternatives: every 5-min poll while it holds; once a day.
- **Q5 The window.**
  - **Default: 09:32–16:00 ET** (the trade-flash line, `trade_flash.WATCH_*`).
  - Alternatives: start at 09:45 like the Tape tab's own session read (`engine.SESSION_MEANINGFUL_AFTER`, R2);
    04:00–20:00 ET (extended hours — needs its own crontab line, the trade-flash line is `2-57/5 9-15`).
- **Q6 Expiry (K3).**
  - **Default: IREN through today's close (2026-10-16).**
  - Alternatives: standing until removed (`None`); more names.
- **Q7 Sellers taking over.**
  - **Default: no push on a flip True → False** (his ask is buyers winning; the row shows it).
  - Alternative: a second push "sellers took control".
- **Q8 An editable pin list.**
  - **Default: not built** — the list is the `WATCH` constant (a deploy per change).
  - Follow-up: a 📌 on the Tape tab backed by Mongo (the Signal Lab watchlist precedent
    `daytrading/signal_lab.py:294-335`).
- **Q9 Thin tape.**
  - **Default: no thin-tape gate** (check 3 has none; `engine.MIN_TRADES_FOR_VERDICT` 500 only downgrades the
    composite BUY).
  - Alternative: no ring below 500 regular prints.
- **Q10 A ring that reached no device.**
  - **Default (AMENDMENTS7 A3): retried.** The next poll that still reads buyers in control rings again, up to
    `MAX_PUSH_ATTEMPTS` = 2 sends per flip. At the cap the row says "rang twice to no device — check Notifications".
  - Alternative: consumed after one send (the original D4), shown "(reached no device)" on /alerts.
- **Q11 The start guard.**
  - **Default: no tape read starts later than `KINDS_BUDGET_SEC`** (200 s, MINE) into the poll; a cut read is a fault.
  - Alternative: always read (the pass may overrun into the next tick).
- **Q12 The tap.**
  - **Default: `/sepa/IREN?tab=tape&from=alerts`** (back link "← Alerts").
  - Alternative: `from=chart-maps` like the burst kinds.
- **Q13 The first read of the day (AMENDMENTS7 A6).** Should the first read of the day ring at all, or only a flip
  observed during the day?
  - **Default: it rings** — "alert me when the Buyers are winning". Its push says " · first read today".

## Tests

- Backend: `backend/tests/test_tape_control.py` (the state machine, the pass, the words, `fetch_trades` `max_429`),
  `backend/tests/test_tape_control_registry.py`, `backend/tests/test_cli_trade_flash_watch.py` (the hook order and
  isolation).
- Frontend: `Alerts.test.tsx` (the 🎚️ row block); `Alerts.tape_control_live.test.tsx`, which renders the real /alerts
  page on the live capture and checks pins[0].text and the note verbatim, plus no NaN / undefined / None / the b-word.
- `scripts/contracts.mjs` block "🎚️ tape_control".

## Files

- `backend/orderflow/tape_control.py` (NEW), `backend/orderflow/tape.py` (`max_429` only), `backend/sepa/cli.py` (the
  hook, the beat, the `--kinds` help)
- `backend/push/subs.py`, `backend/push/recent.py`, `backend/market_hours/gate.py`,
  `backend/supply_demand/alert_status.py`, `backend/supply_demand/rules_info.py`,
  `backend/observability/health_audit.py`
- FE: `lib/alertKinds.ts`, `hooks/useNotificationPrefs.ts`, `pages/Alerts.tsx`, `pages/Notifications.tsx`,
  `lib/newFeatures.ts`, `scripts/contracts.mjs`
