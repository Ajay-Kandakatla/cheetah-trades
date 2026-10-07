# Portfolio poll froze the api — 2026-10-06

**Symptom:** `/health` took up to 19 s about once a minute (median 6 ms). Every page on the site waited behind it, and the Docker watchdog's 5 s health probe read "down".

**Caught by:** `py-spy dump` against the live api, run from a throwaway container (`--pid=container:cheetah-market-app-api-1 --cap-add SYS_PTRACE`) and sampled every 0.7 s while `/health` was timed. In every stall window, the event loop's MainThread was inside:

`portfolio_holdings_get` → `_format_holdings_response` → `quotes.fetch_quotes` → yfinance `fast_info.last_price`

**Why each poll was slow:** Fidelity's non-ticker holdings, `$RESTRICTED.STOCK.UNITS` and `$BTC.LP.IDX.2055.H`, have no Massive price. They fell through to yfinance on every 60 s poll. A miss was never cached, so every poll paid yfinance's full retry path again.

## Fix

- `GET /portfolio`, `GET /portfolio/holdings` and `POST /portfolio/holdings/refresh` are now plain `def`. FastAPI runs them in its threadpool, so the event loop keeps serving.
- `portfolio/quotes.py`:
  - A ticker that has **never** priced in this process is not asked again for `_MISS_TTL` (900 s) after yfinance fails on it alone (an exception or no price).
  - A `$`-prefixed position never goes to yfinance.
  - Massive is still asked on every refresh, so a real ticker recovers as soon as Massive prices it.
  - Critic fix: a ticker that has ever priced is never barred. An empty yfinance answer never overwrites its last good quote; the quote is left stale, so the next refresh asks again. A whole-batch failure (a Yahoo throttle) marks nothing.
- Only Plaid rows fall back to the broker's price when no live quote exists. Manual rows, `build_summary`, `snapshots` and the desk report show no price. That is why a held ticker must never be barred.

**Tests:** `backend/tests/test_holdings_loop_stall.py`.
