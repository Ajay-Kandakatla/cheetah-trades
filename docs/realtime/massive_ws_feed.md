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

---

## 2026-11-09 — feed honesty + the live hub's watch set (GG LIVE spec §3.1/§3.2, WP-A)

Ajay 2026-11-09: *"I would like the autopilot to be continously monitored or live tracked … make it more live with
websockets"*. P0 makes the ONE socket observable and honest before anything rides on it. No reconnect behaviour
changes by default.

**Corrected comment.** The old `_RECONNECT_COOLDOWN` comment said the server "takes ~20-60s to release a dropped one".
Massive does not document that: connections are counted per cluster, shared by every key on the account; on Stocks
the OLDER connection is closed and the NEW one keeps streaming. After our own unclean drop, a reconnect kicks only
our own ghost. After a KICK, reconnecting kicks the other client. The 30 s wait is unchanged. Its measured need is
HIS CALL #11 (the canary, below).

### Knobs (env, read at import; every default = today)
| Var | Default | Meaning |
|---|---|---|
| `MASSIVE_WS_RECONNECT_COOLDOWN` | `30` | wait after an authed drop that is NOT a kick (today's value) |
| `MASSIVE_WS_KICK_COOLDOWN_SEC` | = the above | wait after a KICK: status `max_connections` or close code 1008 (HIS CALL #10) |
| `MASSIVE_WS_KICK_YIELD_AFTER_N` / `_WINDOW_SEC` / `_SEC` | unset = OFF | "never fight": after N kicks inside the window, stop reclaiming for YIELD seconds and say so |

Every default wait is exactly today's: a clean close reconnects at once (even right after a `max_connections`
status); an authed drop, or a failure whose text says `max_connections`, waits `_RECONNECT_COOLDOWN`; any other
failure (a 1008 before auth included) keeps the exponential backoff (2 → 60 s). A kick is always COUNTED. Where today
cools, the wait becomes `KICK_COOLDOWN_SEC`: the knob replaces the cooldown value and never adds a wait. Only the
yield guard, which is OFF by default, adds one.

### Guards
- `enabled()` in `auto` is **False when `CHEETAH_ENV == "dev"`**. An explicit `MASSIVE_WS_ENABLED=true` still wins.
  `docker-compose.dev.yml` also pins `MASSIVE_WS_ENABLED: "false"`, so a dev stack never opens a second socket on
  the prod key.
- No pytest guard: it would flip lifespan tests onto the Finnhub WS + REST poller.

### Routing order (`_handle(raw, cache, tracked)`)
1. A print on a **hub-watched** symbol goes to the hub listener FIRST. The call is synchronous, O(1) and does no I/O;
   a raising listener is logged and never stops the read loop. The print is
   `{sym, p, s, c, t_ms, recv, trfi}`.
2. A print on a **UI-tracked** symbol goes to `await cache.update` with the same payload as before.
3. A print on a symbol that is neither is dropped.

`_handle(raw, cache)` with no `tracked` keeps the old behaviour: every T goes to the cache.

### One ordered control queue
`live_hub` calls `live_feed.watch(symbols)` / `unwatch(symbols)`. These put `("sub"|"unsub", SYM)` on the SAME
`_ws_subscribe_queue` the UI uses (a `str` item is the old subscribe), and ONE pump drains it in order:
- an `unsubscribe` frame goes out only if, **at send time**, the symbol is neither UI-tracked nor hub-watched. A hub
  unsub that lands after the UI subscribed the same symbol is dropped, so the UI price never freezes;
- `("sub", s)` is skipped when `s` is already subscribed on this connection;
- a reconnect subscribes tracked ∪ hub, exactly once each.

Wiring (lifespan, only when the Massive feed is enabled):
`live_feed.set_views(tracked_symbols, live_hub.watched, _ws_subscribe_queue)`, then the consumer, then
`live_hub.run()`.

### Kick timeline + served keys
Every connect / auth / close / reconnect_wait, and the statuses that explain a drop (`max_connections`,
`auth_failed`, `auth_timeout`, `error`), is appended to an in-memory deque (`EVENTS_MAX` 500). Per-symbol subscribe
acks (`success`) and `connected` are never rows. It is
also inserted best-effort into Mongo `live_feed_events` (TTL `LIVE_FEED_EVENTS_TTL_DAYS` = `READS_TTL_DAYS` 14 d,
index on `at`). That insert is a fire-and-forget worker task, never on the read loop.

`GET /live/feed-status` adds these keys: `kicks_1h`, `kicks_today`, `last_kick_et`, `last_kick_age_s`,
`blind_s_today` (drop → next `auth_success`), `resume_s_last`, `connected_since_et`, `lag_ms_p50` / `lag_ms_p99`
(recv − SIP `t` over the last `LAG_SAMPLES` 1000 trades, linear percentile), `msgs_per_s_1m`, `hub_symbols`,
`subscribed_t`, `state`, `word`.
- Admins only (`auth.is_admin_email`) also get `admin_word` (`"lag {p50} ms · {kicks} kicks today · {blind} s
  blind"`) and, with `?events=1`, the last `EVENTS_SERVED` 50 timeline rows.
- **The stocks key never appears.** Every served string is scrubbed (`_scrub_obj`).

`state` ∈ `live | kicked | down | quiet | off`. Each state's `word` is served verbatim (`FEED_WORDS`). /alerts prints
it at the top of the status strip, plus `admin_word` when served; the page composes nothing.

### Coalesced QuoteCache persist (a declared QuoteCache change, C11)
`QuoteCache.update` used to await one Mongo upsert per trade, on the read loop. Now it parks the merged doc in a
latest-wins dict. `cache.persist_drain()` (started in the lifespan for whichever feed runs) writes one upsert per
symbol every `LIVE_CACHE_PERSIST_SEC` (1.0 s), off the loop, and flushes once more on shutdown. The payload, the
lock, the indicators and `quote.update` (0.5 s) are unchanged. The restart re-seed is unchanged, at most 1 s older.

### The hub (`backend/live_hub.py`)
See spec §3.2. Each poll reads today's pushed 🚩 A+, the lane doc view, the pass pointers and the gate snapshot. It
reads the gate from the local calendar and never calls Alpaca. It then sets the watch set, runs the bar clock
(boundary + `BAR_SETTLE_SEC`), and applies ONE print filter (`PRINT_KINDS = ("regular",)`, HIS CALL #2) before
either consumer.

Interest is keyed by (variant tab, symbol) with a 60 s TTL and at most 80 symbols per variant. Symbols over the cap
are refused, never silently cut.

2026-11-11 (entry spec §3.1, WP-BRK): `live_feed.authed_since()` returns the epoch of the current authentication
while the socket is authed (else None). It reads state only. `chart_maps/gajjala/break_watch.py` keys its ⚡
coverage on it: a changed value restarts every symbol's coverage. The hub adds break_watch's symbols to the watch set
and hands it each regular print between the lane and the screen (`tests/test_live_hub_break_2026_11_11.py`).

### Tests
`tests/test_live_feed.py` (routing + control queue appended; the original 9 unmodified),
`tests/test_live_feed_kicks_2026_11_09.py`, `tests/test_quote_cache_persist_2026_11_09.py`,
`tests/test_live_hub_2026_11_09.py`, `frontend/src/pages/Alerts.live_feed.test.tsx`.
