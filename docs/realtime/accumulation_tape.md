# Real-time accumulation / distribution tape (Phase 2)

**Status:** shipped 2026-06-01 · `backend/accumulation.py`, wired through
`backend/live_feed.py` + `backend/main.py`
**Goal (user):** *"decide in real-time on accumulations… dark pool… hedge funds moving."*

## What it answers

For a focus stock, in real time: **is institutional money lifting the offer or
hitting the bid, and how much of that is happening in dark pools?** The card
shows a single read — `accumulation` / `neutral` / `distribution` — backed by
net buyer-$ and a dark-pool buy ratio.

## How (verified against live Massive)

Every print on the **trade tape** is classified against the prevailing **NBBO**
— the *quote test*:

| Trade price vs NBBO | Side |
|---|---|
| ≥ ask | **buy** (buyer lifted the offer → accumulation) |
| ≤ bid | **sell** (seller hit the bid → distribution) |
| between | compared to the midpoint |

Flow is then split by venue. A trade with a **`trfi`** field (FINRA TRF / ADF id)
is an **off-exchange / dark-pool** print — where institutions hide size. A
rising *dark-pool buy ratio* is the stealth-accumulation tell.

Live validation (RTH): `NVDA → accumulation, buy 65%, dark-pool 49% of volume,
dark-buy 38%, net +$53k` over 25s; `AAPL → accumulation, buy 89%`.

## Data path (one socket — hard constraint)

The Massive account allows **exactly one** concurrent WebSocket. So the single
`massive_ws_consumer` carries **both** channels:

- `T.<sym>` (trades) for every tracked symbol → live price (phase 1) **and**, if
  the symbol is in focus, `tracker.on_trade(...)`
- `Q.<sym>` (NBBO quotes) for the **focus set only** → `tracker.on_quote(...)`

Reconnects wait `MASSIVE_WS_RECONNECT_COOLDOWN` (30s) after an authed drop — the
server holds a dropped socket ~20-60s and reconnecting sooner just trips
`max_connections` (1008).

## Focus set (bounded)

Quotes are a firehose, so accumulation runs only for a small **focus set**:
**portfolio holdings + top-N candidates (by score) + DEFAULT_SYMBOLS**, capped at
`ACCUM_MAX_FOCUS` (40). Seeded before the WS connects, refreshed every
`ACCUM_FOCUS_REFRESH_SEC` (300s). Opening a card for any other ticker adds it on
demand via `GET /live/accumulation/{symbol}` (subscribes its Q feed; returns
`warming_up: true` until the first prints land).

## API

```
GET /live/accumulation            → { focus:[…], accumulation: { SYM: snapshot } }
GET /live/accumulation/{symbol}   → snapshot (or { warming_up:true } on first call)
```

`snapshot` =
```json
{ "symbol":"NVDA", "signal":"accumulation",
  "session": { "trades":4210, "volume":..., "buy_ratio":0.65,
               "net_dollars":52963, "dark_pct":0.49, "dark_buy_ratio":0.38 },
  "window_sec":900,
  "window": { "buy_ratio":0.71, "net_dollars":..., "dark_pct":..., "signal":"accumulation" },
  "nbbo": { "bid":224.39, "ask":224.43 } }
```
`session` = cumulative since the feed started; `window` = rolling
`ACCUM_WINDOW_SEC` (900s / 15 min) for the *current* lean.

## Config

| Var | Default | Meaning |
|---|---|---|
| `ACCUM_TOP_N` | 5 | candidates added to focus |
| `ACCUM_MAX_FOCUS` | 40 | focus-set cap |
| `ACCUM_WINDOW_SEC` | 900 | rolling-window length |
| `ACCUM_SIGNAL_RATIO` / `DISTRIB_SIGNAL_RATIO` | 0.58 / 0.42 | buy-ratio bands for the label |
| `ACCUM_FOCUS_REFRESH_SEC` | 300 | focus recompute cadence |

## Honest limits

- Off-exchange = dark pools **+** retail internalizers (both report via TRF);
  Massive doesn't split ATS-only (that's FINRA's separate weekly ATS report), and
  never names the fund.
- The quote test uses the *latest* NBBO, not the exact at-trade quote — a real-
  time approximation of Lee-Ready, fine for a live lean.

## Tests

`backend/tests/test_accumulation.py` (10). `make contracts-realtime`.
