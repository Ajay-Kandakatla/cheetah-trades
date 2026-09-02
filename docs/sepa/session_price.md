# Session-aware price header (RTH close + extended hours)

**Ask (Ajay, 2026-09-02, TLYS):** *"Can you accurately show the AH and RTH
value"* — StockTwits shows `$3.81 ↓ $0.15 (3.79%) Today · Closed` over
`$5.12 ↑ $1.31 (34.38%) ☾ After Hours`; our header showed one number.

**Backend:** `sepa/quote_view.py::quote_view(q)` (pure, tested) over one
`sepa.prices.bulk_live_prices` entry — `price` (Massive day bar: the regular
close after the bell, the running last during RTH, `0` pre-open),
`prev_day_close`, `last_trade_price` + `last_trade_ts_ms` (nanoseconds).
Session from the trade stamp (`catalysts.promo_live.session_from_ts`).
`GET /sepa/live-price/{symbol}` now returns `view`.

| session | line 1 | line 2 |
|---|---|---|
| rth | last vs prev close · *Today · Live* | — |
| afterhours | close vs prev close · *Today · Closed $x* | AH print vs **the close** · *☾ After Hours* |
| premarket | — (no day close yet) | PRE print vs **prev close** · *☀ Pre-Market · Prev close $x* |
| closed | close vs prev close | last AH print if it differs from the close |

**Frontend:** `SessionPrice.tsx` (30 s poll) replaces the single-number block
on the SEPA candidate header; falls back to the scan's close / day % until
the view answers. Tests: `tests/test_quote_view.py` (5), `SessionPrice.test.tsx` (3).
