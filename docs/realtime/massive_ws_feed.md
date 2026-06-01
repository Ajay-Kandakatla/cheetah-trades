# Real-time stock feed — Massive WebSocket (Phase 1)

**Status:** shipped 2026-06-01 · branch `feat/massive-websocket-realtime-2026-06-01`
**Module:** `backend/live_feed.py` · wired in `backend/main.py` lifespan
**Replaces:** the Finnhub WS + REST poller as the live-quote *source*

---

## Why

Finnhub's free tier throttles (constant 429s under the broad universe) and, on
the cancelled Stocks Developer plan, was capped at 15-min-delayed data. The user
moved to **Massive Stocks Advanced** (real-time trades + WebSocket + unlimited
calls). This phase swaps the upstream feed to Massive while leaving the rest of
the live-quote pipeline untouched.

## Architecture

```
 Massive WS  ──T(trade)──►  live_feed.massive_ws_consumer ─┐
 (socket.massive.com)                                      ├─► QuoteCache.update()
 Massive snapshot ─OHLC/prev_close─► massive_snapshot_poller┘        │
 (/v2/snapshot/...)                                                  │ publish_throttled
                                                                     ▼
                                                          events bus → SSE /events
                                                                     ▼
                                                          frontend useLiveQuote (UNCHANGED)
```

The frontend never connected to Finnhub directly — it consumes **SSE
`quote.update`** events fanned out from the in-memory `QuoteCache` in `main.py`.
The Finnhub consumer's only job was to call `cache.update(...)`. So Phase 1 adds
a Massive consumer that calls the *same* `cache.update(...)`. **No frontend or
SSE change.**

### Two coroutines

| Coroutine | Source | Writes | Cadence |
|---|---|---|---|
| `massive_ws_consumer` | `wss://socket.massive.com/stocks`, channel `T` (trades) | `price`, `volume`, `source=massive_ws`, `trade_ts` | every tick (real-time) |
| `massive_snapshot_poller` | `sepa.prices.bulk_snapshot` (`/v2/snapshot/...`) | `open`, `high`, `low`, `prev_close`, `day_volume`, `vwap`, `pct_change` — **never `price`** | `MASSIVE_SNAPSHOT_INTERVAL_SEC` (15s) |

The trade stream carries price but not the day frame; the snapshot backfills the
frame. Because the SSE payload ships **both** `price` (live) and `prev_close`
(snapshot), the browser derives a **live percent move on every tick**. The
poller is forbidden from writing `price` so it can never clobber the live tick —
enforced by `test_live_feed.py::test_snapshot_backfills_day_frame_without_price`.

## The auth handshake (load-bearing)

Polygon/Massive protocol is **auth → wait for `auth_success` → subscribe**.
Subscribing in the same instant as auth races the server's auth handler and
silently drops *part* of the subscription (observed in testing: 2 of 4 symbols
never streamed despite a clean `auth_success`). `_await_auth()` blocks for the
`auth_success` status frame before any `subscribe` is sent.

## Keys

The WS uses **`stocks_key()`** (`MASSIVE_API_KEY_STOCKS`). Options sentiment uses
a *distinct* entitlement, **`options_key()`** (`MASSIVE_API_KEY_OPTIONS`) — a
stocks key 403s on options endpoints and vice-versa. See
`backend/massive_keys.py` and `docs/realtime/` sibling notes. A stocks key is
all the WS feed needs.

## Config (env)

| Var | Default | Meaning |
|---|---|---|
| `MASSIVE_WS_ENABLED` | `auto` | `auto` = on iff a stocks key exists. `true`/`false` force. |
| `MASSIVE_WS_URL` | `wss://socket.massive.com/stocks` | Use `wss://delayed.massive.com/stocks` for the delayed cluster. |
| `MASSIVE_WS_CHANNELS` | `T` | Comma list. `T,A` adds per-second aggregates. |
| `MASSIVE_SNAPSHOT_INTERVAL_SEC` | `15` | Day-frame backfill cadence. |

When the Massive feed is enabled, the **Finnhub WS + REST poller stay off** so
15-min-capable data can't overwrite real-time prices. With no stocks key the app
falls back to the Finnhub path exactly as before (`MASSIVE_WS_ENABLED` unset →
`auto` → Finnhub).

## Verify (post-deploy)

```
curl -s localhost:8000/live/feed-status | jq
```

Healthy during RTH:

```json
{ "active_source": "massive_ws", "connected": true, "authed": true,
  "tracked": 42, "trades": 18234, "last_trade_age_s": 1.2, "reconnects": 0,
  "error": null }
```

`active_source: finnhub` or `last_trade_age_s` climbing into minutes during RTH
means the feed didn't come up — check the stocks key and `error`.

## Tests

`backend/tests/test_live_feed.py` (8) + `backend/tests/test_massive_keys.py`
(10). Run: `make contracts-realtime` (standalone until the api image is rebuilt
with `live_feed.py`, then fold into `make contracts`).

## Next phases (not in this change)

2. **Real-time intraday scanning** — run the 32-worker scan on live bars.
3. **Live re-score** — top-5 candidates + portfolio holdings only.
4. **Instant alerts** — portfolio-scoped; volume/distribution alerts only for
   holdings ("volume drops are just noise unless it's in my portfolio").
5. Re-enable the breakout-volume `is_buyable` gate + fix premarket movers.
