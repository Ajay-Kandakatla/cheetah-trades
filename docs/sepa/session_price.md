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

## 2026-10-21 — the "as of" line prints served facts only

**Ask (Ajay, POLA screenshot):** *"Dated info."* At 12:0x ET the header still
read "Data as of Oct 21, 11:03 AM · Re-rates after 3:00 PM CT (4:00 PM ET)".
The 11:03 was the BROWSER's fetch time labelled as the data's age, and the
typed note named the close, not the re-rate (the crontab's
`30 16 * * 1-5 … sepa.cli fast-scan --mode broad` is 16:30 ET). The line is
now `loaded {browser clock, ET} · price live ({quote as_of}) · SEPA read from
the {as_of_close} close · {rerate_text}` (`frontend/src/lib/sepaAsOf.ts`).
`as_of_close` is stamped on every scan row by `sepa.scanner.as_of_close(df)`:
the frame's last bar when it is a CLOSED session (dated before today ET, or
today once the ET clock is at/past `SEPA_RERATE_ET` or `prices.trade_session`
says 'closed'), else null — during RTH the hourly `vcp-watch` scan reads
today's in-progress bar (`patch_latest_closes`), and its 16:00 run builds rows
seconds after the bell, before the 16:30 re-rate; neither is called a close. `rerate_text`
comes from ONE constant, `sepa.scanner.SEPA_RERATE_ET = "16:30"`, pinned to
the crontab line by a test; GET `/sepa/candidate/{symbol}` carries both
top-level and the list card's footer prints the row's `rerate_text`. An
absent fact is omitted; "Data as of" never prints. Critic fixes (2026-10-21):
a bare `YYYY-MM-DD` quote `as_of` prints "price live" with no clock (it is
UTC midnight, never a time), and "loaded" is the visible data's fetch time —
`useSepaCandidate`'s `cachedAt` (the cache envelope's ts on a cache paint,
also after a failed refresh), render time only when there is none. Tests:
`backend/tests/test_sepa_page_asof_2026_10_21.py`,
`frontend/src/pages/SepaCandidate.asOf.test.tsx`.
