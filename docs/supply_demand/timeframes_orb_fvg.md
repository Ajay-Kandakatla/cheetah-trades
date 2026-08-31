# Multi-timeframe zones, ORB, Fair Value Gaps, and computed entry/stop

Shipped 2026-08-29. Ajay: *"What are the concepts or ORB and Fair value gap
and can do this in Daily, Market hourly, 15 mins time charts ... For supply
and demand zone ... Give me stop loss and Entry calculated dynamically ...
I need this in Support level and also on the supply demand zone drop downs"*
plus *"any other bullish patterns on an hourly chart ... Cup handle or
Inverse head and shoulder or Flat top"*.

## Source status — read this first

This page mixes three tiers of evidence. They are not equal and the code
labels which is which on every record.

| Concept | Source | Status |
|---|---|---|
| Opening Range Breakout | Toby Crabel, *Day Trading with Short Term Price Patterns and Opening Range Breakout* (1990); Linda Raschke, *Street Smarts* (1995) | **Cited** — already the basis of `daytrading/signals/orb.py` |
| Cup w/ handle, inverse H&S, double/triple bottom | Bulkowski (cup.html et al.), Lo-Mamaysky-Wang | **Cited**, verbatim in `patterns/detector.py` |
| Fair Value Gap | ICT (Inner Circle Trader) — video/community material | **No canonical text in the library.** Definition stated in full below so it is auditable without a source |
| Flat top (ascending triangle) | — | **CONVENTION.** Parameters are this app's choices, labelled `cited: false` |
| Zone clustering, dynamic entry/stop | `supply_demand/price_zones.py` | App's own configured method, never a book method |

**The statistics do not travel across timeframes.** Bulkowski's 62% throwback,
his 61%/74% measure-rule factors and the "47% dropped substantially within two
months" warning were all measured on *daily* bars. The shape rules are
scale-free; the hit rates are not. Every non-daily pattern record carries
`stats_transfer: false` and a caveat string, and the UI prints it. The app's own
forward ledger (`GET /patterns/accuracy`) is likewise daily-only and is not fed
by intraday scans.

## The concepts

### Fair Value Gap — a three-bar imbalance

A gap in *traded price*, not in time. Bar 2 moves so hard that bar 1 and bar 3
never overlap, leaving a price band inside which almost nothing changed hands.

```
bullish (demand):  bar1.high < bar3.low   → band = [bar1.high, bar3.low]
bearish (supply):  bar1.low  > bar3.high  → band = [bar3.high, bar1.low]
```

Why it is a zone: the band is unfinished business. If buyers ran price through
it without transacting, the resting orders that would have filled there are
still there. Price returning offers those fills — the same premise as every
supply/demand zone in this app, arrived at from the tape instead of from a
swing pivot.

Two filters keep it off noise (`supply_demand/patterns.py`):

* **Displacement** — bar 2's range must exceed `MIN_DISPLACEMENT_ATR` (0.8) ×
  ATR. A gap left by a sleepy bar is a rounding error.
* **Mitigation** — once price trades back in, the gap is filling. `fill_pct`
  tracks how much is gone; past `MAX_FILL_PCT` (50%) the zone is spent and is
  dropped. An unfilled gap is the whole signal.

### Opening Range — the session's first agreed band

High/low of the first N minutes of regular trading. Overnight orders, gap
reactions and the first institutional prints clear inside it, so it is the day's
first honest agreement on value. Above it, buyers won the auction; below,
sellers did. Window scales with the chart: 15 min on a 15m chart, 60 on hourly,
30 on daily — ORB is intrinsically intraday, and a daily chart borrows it as
"where today's auction opened", not as a daily-bar pattern.

### Dynamic entry and stop

Every band already implies the trade:

```
entry = the PROXIMAL edge (the side price reaches first)
stop  = the DISTAL edge, plus an ATR-scaled buffer beyond it
```

The buffer exists because a stop resting exactly on the level everyone can see
is the liquidity that gets taken. It scales with ATR (`STOP_BUFFER_ATR` = 0.25)
with a `MIN_STOP_BUFFER_PCT` floor of 0.10%, so a quiet name gets a tight stop
and a volatile one is not shaken out by its own noise.

Target 1 is the **next opposing band** when one exists — real structure — and
otherwise a measured `DEFAULT_TARGET_R` (2.0) multiple, labelled as such so a
computed target is never mistaken for a level. Risk is a fact of the geometry;
position size comes off the stop distance (`desk/scoring.position_size`), never
off conviction.

## Timeframes

`supply_demand/timeframes.py`. Nothing about the zone methodology changes —
only the frame it reads.

| Key | Label | Bars | Span | Source |
|---|---|---|---|---|
| `daily` | Daily | 252 | 1 year | `sepa.prices.load_prices` |
| `60m` | 1 hour | 330 | ~47 sessions | 1-min Massive bars resampled |
| `15m` | 15 min | 260 | ~10 sessions | 1-min Massive bars resampled |

Two decisions worth keeping:

* **Resampling is left-closed, right-labelled.** The bar stamped 09:45 holds
  09:30–09:44. Closing on the right instead looks equivalent and is not: it
  orphans the session's opening minute into a bucket of its own, so every
  session starts with a one-minute bar wearing a 15-minute label — a fake
  extreme the swing and gap detectors would read as structure. Locked by
  `test_resample_is_right_closed_and_drops_empty_buckets`.
* **The hourly budget is 330 bars on purpose.** Bulkowski's minimum cup is
  "7 weeks" = 245 hourly bars; a smaller budget would make the cup detector
  silently barren on this timeframe and look like a bug.

RTH only on intraday frames. A swing low made on 400 shares at 07:12 is not a
level anyone defended.

## Pattern gates scale by calendar time, not by bar count

Bulkowski cites cup duration as "7 to 65 weeks" — calendar, not bars. On a daily
chart 7 weeks is 35 bars; hourly it is 245; on 15-minute, 910. Copying the daily
bar-count to a fast chart would find a "7-week cup" inside two sessions and label
it with a citation it does not have. `patterns/timeframe.BARS_PER_SESSION`
converts, so the cited *duration* survives the timeframe change.

The consequence is honest and is surfaced rather than hidden: on 15-minute bars
the cup, double bottom and triple bottom cannot reach their own minimum inside a
10-session window, so `reachable()` reports them as out of range and the UI names
them. Only inverse head-and-shoulders and flat top fire there.

## Where it appears

* `GET /chart-maps/support?symbol=&window=&tf=` — Support tab, second dropdown
* `GET /supply-demand/price-zones/{symbol}?tf=` — per-ticker zone drill-in

Both carry `trade_levels` (every band with its entry/stop/target/R),
`fair_value_gaps`, `opening_range`, and `bullish_patterns`. Omitting `tf` is the
historical daily path, byte for byte — the intraday branch is additive.

A board-wide timeframe dropdown was **not** built: it would need intraday bars
for ~1,700 symbols per refresh. The per-ticker drill-ins are where an intraday
level is actually read.

## Tests

`backend/tests/test_timeframes_patterns.py` (24) and
`frontend/src/components/SupportLevels.test.tsx`. The negatives carry the
weight: junk timeframes fall back to daily, a filled gap is dropped, a sleepy
bar leaves no gap, nonsense geometry returns no stop rather than a fabricated
one, and an hourly shape can never claim daily statistics.

*Decision-support only. Not investment advice.*
