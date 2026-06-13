# Auto-Pilot engine liveness + the UNPROTECTED alarm

_Added 2026-06-13. A safety/trust fix: a green "engine OK" light that watches the
wrong process is worse than no light at all._

## The bug

The global **"Engine stalled"** banner (`EngineStalledBanner`) polls
`/health/engine`, which reports the staleness of the **alert cron** heartbeat
(`observability/engine_heartbeat`, `name="alerts"`). It says nothing about the
**trading** engine. So on `/trading` it could read green while the
order-managing engine's adopt-protect / stop-ratchet pass was actually asleep —
and the one state that means "real risk is uncovered right now" (an open position
with **no resting stop**) was a single cell in a horizontally-scrollable table
column, off-screen-right on a phone.

## The fix

### 1. A real trading-engine heartbeat in `/trading/status`

`trading/exit_engine.status()` now returns an `engine` block derived from the
engine's **own** 1-minute `tick()` (written to `trading_config.last_tick_iso`):

```json
"engine": { "last_tick_iso": "...", "tick_age_sec": 39, "stale_after_sec": 180, "stale": true }
```

`stale` is `true` **only when the engine should be running** — market open AND
armed — and the last pass is older than `ENGINE_STALE_SEC` (180s = 3 missed
ticks), or never recorded. It is deliberately quiet when the market is closed or
the engine is disarmed (it shouldn't be ticking then). Plus an `unprotected`
list — the symbols of open positions with no resting stop.

Behaviour locked by `backend/tests/test_engine_liveness.py` (fresh→not stale,
old→stale only when open+armed, closed→not stale, disarmed→not stale,
never-ticked→stale only when active).

### 2. Trading page surfaces

- An **engine-liveness chip** next to ARMED: amber _"engine may be asleep"_ when
  `engine.stale`, green _"engine live · Ns"_ otherwise. Only asserted when the
  engine should be running.
- A loud **page-level UNPROTECTED alarm strip** above the positions table when
  `unprotected.length > 0` — promoted out of the scroll-off-right table cell.

### 3. Relabelled the global banner

`EngineStalledBanner` now says _"the alerts pipeline"_ and explicitly notes
_"(this watches the notification cron, not the Auto-Pilot trading engine — that
has its own status on the Trading page)"_, so nothing implies it covers order
management.

## Boundary reminder

This is liveness/observability only. It never places, moves, or cancels an order;
the engine still does all order management, stops still rest at the broker, and
the app never executes a trade on the user's behalf.
