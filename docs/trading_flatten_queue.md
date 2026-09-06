# Auto-Pilot flatten queue

**What:** an owner exit that Alpaca refuses outside the session is queued in
`trading_config.flatten_queue` and the exit-engine tick drains it every minute
until the sell is accepted, then tracks the sell until the position is gone
and journals the fill.

**Why (Saturday 2026-09-05):** Ajay chose to exit the pre-gate cohort
(AEIS 44, APLD 466, LUNR 838, bought Friday by the zone-edge breakout lane
before the 5 % room / 1 % proximity gate existed) at Monday open.
`exit_engine.flatten()` cancelled each bracket's take-profit LIMIT (the stop
leg rides under it), then Alpaca answered

```
DELETE /v2/positions/AEIS -> HTTP 403
{"available":"0","code":40310000,"existing_qty":"44","held_for_orders":"44",
 "message":"insufficient qty available for order (requested: 44, available: 0)"}
```

The cancelled orders sit in `pending_cancel` until the next session, so the
shares stay held and the close cannot be submitted that night. Without a
queue the exit would have needed a human at 9:30.

## State machine (`backend/trading/exit_engine.py`)

| state | meaning | tick action |
|---|---|---|
| `pending` | owner asked to exit, shares still held | cancel the symbol's open orders that are not already `pending_cancel`, then `close_position`. Held again (code 40310000) → stay pending, `still_held += 1`, no ledger row. Other broker error → stay pending, error surfaced in `summary.errors`. Accepted → `sent`. |
| `sent` | Alpaca accepted the market sell | never cancel or re-sell while the order is open (`sent_waiting`). Order gone but position still there → back to `pending`. |
| dropped | position gone | `sent` + filled order found in the last 7 days of closed orders → ledger `trade_closed` (leg `flatten`, fill, entry, gain_pct, reason) + `position_alert` push; always a `flatten_done` row. |

The drain is tick step **(a2)**: after the "configured" check and **before**
the market-closed early return, because Alpaca accepts a market sell outside
hours and queues it for the open. The protect / ratchet / watchdog loop
**skips queued symbols** (a fresh protective stop would re-hold the shares
and block the close forever). Nothing runs while the engine is disarmed
(`skipped_disarmed`). The drain is fenced: an exception there is recorded
and stop protection below still runs.

### Two writers, one list

The Exit button runs in the **api** container, the drain in the **cron**
container. Every queue write is compare-and-set on `flatten_queue_rev`
(`exit_engine._queue_write`); a losing writer re-reads and re-applies its
change (`_queue_commit`). The drain merges its per-symbol results onto the
fresh list (`_apply_queue_changes`): an exit queued mid-drain survives, an
exit the owner unqueued mid-drain stays gone. A `sent` order that left the
open list is looked up in closed orders first: filled → keep waiting (the
position read lags a tick), otherwise back to `pending`.

## Ledger kinds

- `flatten_queued` — the refused close that queued the exit (reason, error).
- `flatten` with `closed: true`, `note: "drained from flatten_queue"` — the
  sell was submitted. A `flatten` row with `closed: false` is **not** an exit
  in the journal (`journal._is_exit_row`).
- `trade_closed` with `leg: "flatten"` — the fill; the journal prefers it over
  the fill-less `flatten` row and reports `exit_reason` as
  `manual flatten, <reason>`.
- `flatten_done` — entry dropped (`filled` true/false).
- `flatten_unqueued` — owner took the exit back.

## Endpoints

- `POST /trading/flatten/{symbol}` (admin) — optional body `{"reason": str}`
  (≤ 300 chars). Returns `queued: true, closed: false` when the exit was
  queued.
- `POST /trading/flatten-queue/{symbol}/cancel` (admin) — unqueue. A sell
  Alpaca already accepted is left alone (the row says so).
- `GET /trading/status` — `flatten_queue: [{symbol, reason, queued_at,
  state, sent_at}]`; each position row carries `exit_queued` and
  `exit_queue_state`; a queued row reports `stop_status: "queued"` and is not
  listed under `unprotected`.

`flatten_queue` is **not** writable through `POST /trading/config`.

## Trading page

The Stop-status cell shows `⏳ Exit queued` (pending) or
`⏳ Exit sent · fills at the open` (sent); the Exit button becomes
**Unqueue**; one line under the table lists the queued symbols with the
reason on hover. `frontend/src/lib/autopilotStop.ts` owns the labels.

## Tests

`backend/tests/test_flatten_queue.py` (engine, status, helpers, API reason),
`backend/tests/test_journal.py` (refused row is not an exit; fill lands via
`trade_closed`; legacy rows unchanged), source guard
`test_flatten_queue_2026_09_05_*` in `backend/tests/test_trading_contracts.py`,
`frontend/src/lib/autopilotStop.test.ts`.
