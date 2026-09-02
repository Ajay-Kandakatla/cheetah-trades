# Promo circuit — LIVE movers + 🎪 alerts

**Ask (Ajay, 2026-09-02):** *"Give me a real time page.. with percentage and
alerting system. the alerts are broken today.. just give me alerts from the
topstock alerts only.. I need the pre market alerts as well. After hours alerts."*

**Where:** Catalysts → 🎪 Promo Circuit tab → **⚡ Live movers** (top of the tab).
`GET /catalysts/promo-circuit/live`. Code: `backend/catalysts/promo_live.py`,
`PromoLive` in `frontend/src/components/PromoCircuit.tsx`.

## Live board

- Reads the promo board already in Mongo (`promo_circuit_cache`, built by the
  30-min sweep) — never rebuilds it. Rows with status SEEDING / RAN / DUMPED.
- One `sepa.prices.bulk_live_prices` snapshot for every ticker: `last_trade_price`
  (extended hours) vs `prev_day_close` → **today %**. Session tag PRE / RTH / AH
  from the trade stamp via `daytrading.data._classify_session`.
  **Trap:** Massive's `last_trade_ts_ms` is really **nanoseconds** (19 digits);
  `_to_ms` normalises by magnitude (regression test).
- 20 s in-process cache; the page polls every 30 s while `live_state()` says the
  tape is open (0 = no polling when closed).

## Alerts (`promo_alert`, new push kind)

`check_alerts()` from cron `*/5 4-19 * * 1-5` (pre-market through after-hours):
a roster-tagged name whose |today %| ≥ **8%** pushes once per **symbol ×
direction × day** (`promo_alerts` dedupe doc). Skips when closed. Every push
says *"the tag IS the promotion — do not chase"*: the measured hit rates
(`docs/catalysts/promo_circuit.md`) give no follower an edge; this is a radar.

`promo_alert` was added to `push/subs.default_prefs()` (the backfill merges it
into existing subscriptions — a missing key is a silent drop) and to the
Notifications page kind registry with the 🎪 label.

## "Alerts are broken today" — what was actually wrong

Only ONE push subscription existed (the Mac Chrome one); the phone subscription
was gone. The last 60 pushes were 58 `todo_reminder`s to another user (no sub →
`total 0`) and 2 `scalp_tape`. Nothing was ever addressed to Ajay. Fix on his
side: re-enable notifications on the phone at `/notifications`. Noise kinds
`accumulation_change` and `trade_flash` were muted on his devices; the
money-safety keep-set (pivot / position / todo) was left ON pending his call.

## Tests

`backend/tests/test_promo_live.py` (gate table, session clock incl. ns stamps,
stale-print → closed, live rows shape, pref + cron + route guards);
`PromoLive` cases in `frontend/src/components/PromoCircuit.test.tsx` (render with
🎪 flags and session tags, poll cadence, closed = no poll, live-endpoint failure
leaves the board intact).
