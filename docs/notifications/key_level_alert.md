# 🔑 `key_level_alert` — a close through a key level (2026-09-25)

**Ask (Ajay 2026-09-25, verbatim):** *"I wanna know when key levels are broken for a stock."*

**Status: built, ON for the owner, UNMEASURED.** Asked 2026-09-25, he answered *"On: week + month +
52-week"*, scope *"Holdings + Signals list"*, and *"No, close only"* to intraday pierce pings. So the
kind is in `OWNER_KEEP_SET` (`owner_prefs()` returns it ON for his devices) and stays `False` in
`push.subs.default_prefs()` for everyone else. His already-registered phones are flipped by
`backend/scripts/owner_prefs_apply.py --apply`, a data write re-run after any new device registers. No
in-house study measures a break of these levels (`key_levels.MEASURED is False`); every push body
says "Unmeasured". Nothing here gates a scan, sizes a position or enters a lane.

Engine and chart: [`../chart_maps/key_levels_2026_09_25.md`](../chart_maps/key_levels_2026_09_25.md).
Code: `backend/supply_demand/key_level_alerts.py`; hook `zone_edge._run_key_pass`.

## What fires

A **close** through a **prior-week, prior-month or 52-week** regular-session high or low
(`key_levels.PUSH_PERIODS`) on a name in his scope:

* **Scope** — holdings ∪ Signals watchlist: `signal_lab.merge_holdings(get_watchlist(owner),
  portfolio.store.list_holdings(owner))`, owner = `portfolio.alerts._resolve_owner()`.
* **The close decides.** From `key_levels.close_confirm_at(session)` — 16:05 ET, 13:05 on the
  `timeframes.HALF_DAYS` — for `CLOSE_PUSH_WINDOW_MIN` = 25 minutes (16:05–16:30, 13:05–13:30).
  A member whose state is `closed_beyond` — the session close is through the level by
  `key_levels.PIERCE_PCT` (0.15%, the house stop-sweep minimum, reused by name) from the side the
  prior close sat on — is claimed and pushed.
* **Never pushed:** prior-day levels, pre-market levels, an intraday pierce (not built — HIS CALL
  #2 of the spec), a merged chart line (the push reads MEMBERS; a merge could hide a break).
* **Guards:** a name whose cached bars end before the prior market day, or whose last cached close
  is not the official close (`verify_last_row`), is skipped and counted `stale_frame`.

## Latch

Claimed **before** the send with the house primitive `demand_alerts.claim_key` (`$setOnInsert`)
in `key_level_alert_state`:

| level | key | rule |
|---|---|---|
| week / month | `KL:{SYM}:{period}:{kind}:{direction}:{as_of}` | **once per level LIFE and direction.** A chop under → back over → under pushes twice at most (under, back over). Next period's level is a new `as_of`, a new life. |
| 52-week | `KL:{SYM}:year:{kind}:{direction}` (doc carries the claimed `level` and `session`) | **armed latch.** Re-arms (silently, counted `rearmed`) only when a session close is back inside the CLAIMED level by `PIERCE_PCT` on the original side: an up-claim on a close < level × (1 − 0.15%), a down-claim on a close > level × (1 + 0.15%). In an uptrend the nightly-redefined 52-week high does not re-fire. |

Re-arm runs first (ONE `$in` find over the scope's year keys), then the claims.

## Delivery

* Holdings → **singles**, at most `zone_edge.MAX_SINGLES_PER_PASS` (3). Everything else, plus
  the overflow → **ONE digest** of at most `zone_edge.DIGEST_MAX` (6) lines, then `+N more`.
* Transport failure or a raise → `demand_alerts.release_key` for that message's keys; the next
  minute retries.
* **Nobody targeted (the kind is OFF) is terminal**: claims are KEPT and the pass counts `muted`,
  so the latch tracks correctly while the kind is off and switching it on never replays a backlog.
* Closed days: `in_session` already refuses them, and the kind is in `gate.MARKET_ALERT_KINDS`.
* Close messages carry no tape tag and never say "bounce".

Exact text (spec §3.7):

```
🔑 WULX closed under prior-week low $14.80
Close $14.52 (−1.9% vs the level) · first through 10:42 · your position · level frozen at the Fri 09-18 close · Unmeasured: what happened, not a buy or sell signal.

🔑 Key levels closed through — MP over prior-month high +2 more
MP closed over prior-month high $60.10 (+0.8%)
…
Unmeasured — a close through a level, not a signal.
```

A 52-week single says `level: 52-week high, set Wed 03-04`. Several levels on one name:
`closed under prior-week low $14.80 and prior-month low $14.10`, with the close's distance to each
level and a frozen note per level. Links: `/chart-maps?tab=support&symbol={SYM}` (digest: the
lead name).

## First-seen stamps

Every pass in the state window (pre-market, RTH, close) writes the first minute each member went
`through` (and the first `reversal`) into ONE `key_level_state` doc per session
(`{_id: "YYYY-MM-DD", first: {"SYM|member_id|direction|event": "HH:MM"}, updated_at}`), only
when something changed and never on a dry run. The chart chip's time ("broke PWL 95.78 ↓ 10:42")
reads it. The doc is **replaced whole** (never `$set` on `first.<key>`), because a key carries
the symbol and a symbol like `BRK.B` would otherwise read as a dotted path.

## Carrier: the zone_edge minute

`zone_edge.check_once(..., key_pass=None)`: `None` on the cron path (store not injected) runs
`run_pass` (lazy import); `None` with an injected store (tests) skips it — no network in tests;
`False` skips; a callable is called. Called at the store-empty exit (`snapshot=None`), the
snapshot-failure exit (`snapshot={}`, so the pass fetches its own prices) and the normal end,
after `_write_latest`. Its own try/except: a raising hook never changes zone_edge's sends,
latest doc or counts. No crontab line (a deploy does not ship the crontab). Cost: one extra
`bulk_snapshot` for scope names outside zone_store, one `bulk_cached_frames`, one state-doc
read (and a write when changed); in the close window one `$in` find plus one claim per
closed-through member.

## /alerts

`alert_status.PASS_KINDS` carries `key_level_alert` with `CADENCE_SEC` derived from zone_edge's;
counters and the "close verdicts push 16:05–16:30 ET" reason: [`../supply_demand/alerts_page.md`](../supply_demand/alerts_page.md) §9.

## The ON path (HIS CALL #1 — not done)

Add `"key_level_alert"` to `push.subs.OWNER_KEEP_SET`, update the two keep-set pins
(`tests/test_push_owner_keepset.py`, `tests/test_new_alert_kinds.py`), then run
`python -m scripts.owner_prefs_apply --apply` in the api container. Or flip the toggle at
/notifications for one device.

## Volume — a PROBE, not a study

From the planner's read-only sizing probe (`v2/probe_sizing_v2c.py`, his 13-name owner scope,
250 sessions 2025-09-26 → 2026-09-24, 95% CI by 5-session block bootstrap). These are counts
about push VOLUME, not an edge, and never reach a surface:

| as built, and alternatives | names/day (95% CI) | days with a digest |
|---|---|---|
| week + month + 52-week, both directions, latch per life (**as built**) | 3.01 (2.75–3.26) | 94% (91–97%) |
| same, natural direction only | 2.08 (1.89–2.27) | 82% |
| month + 52-week only | 0.90 (0.76–1.07) | 57% |
| month + 52-week, natural direction only | 0.56 (0.45–0.68) | 39% |
| holdings singles (WULX) | 0.24 | — |

## Tests

`backend/tests/test_key_level_alerts.py` — close window (16:05/16:29 push, 16:04/16:30 not;
half day 13:05–13:30), day levels never push, the per-life week latch (Mon under → Tue back over →
Wed under again silent → next week's level pushes), the armed 52-week latch (−0.14% not re-armed,
−0.16% re-armed silently), delivery (transport failure / raise release, targets 0 muted and
kept, second pass silent), routing (singles for held names only, capped; one digest with
`+N more`), exact strings, scope ∪ with ONE extra snapshot call, guards, dry run writes nothing,
first-seen doc replaced whole (BRK.B), the zone_edge hook at all three exits, prefs OFF, the
Labor Day gate, /alerts registration and the rules panel built from the constants.
`backend/tests/test_alert_status.py` — the eight passes, the derived cadence pin.
