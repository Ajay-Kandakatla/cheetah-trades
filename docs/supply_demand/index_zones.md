# Index zones — SPY and QQQ structure, pinned on Back in Demand

## 2026-09-16 — built

Ajay, 2026-09-16: *"Can you create a SPY demand and supply zone please for me?
and also QQQ supply and demand zone and keep them always in the in demand zone
page. I need everything calculation overnight."*

**What shipped.** A pinned strip at the top of the Chart Maps **Back in Demand**
tab (tab key `zones`) carrying SPY and QQQ supply/demand structure. It is not a
tile and not a row: it is never filtered, ordered or gated by the board's
controls (phase / room floor / liquidity tier / limit), and it renders on the
**warming** branch too — a strip that vanishes while the board scans is not
pinned. Backend: `backend/supply_demand/index_zones.py`, served on the zones
board payload under `index_zones` and on `GET /supply-demand/index-zones`.

## 2026-09-16 — follow-up: two resolutions, and a chart

Same day, after the first cut, with a screenshot of Pankaj Kenjale's SPX note:

> *"I wanna see charts with multiple zones"* → *"For both QQQ and SPY"* →
> *"Sorry SPY only my bad"*

Final scope: **SPY and QQQ** (not SPX — `^GSPC` has no intraday bars here
anyway). Two things were added: a **chart** per index with every band drawable
on it, and **more bands** than the seven the board geometry draws.

### The two resolutions

Each index is now served at **both** existing geometries. Neither is a new
number — both are constants that already own a surface in this app:

| resolution | geometry | constants | measured 2026-09-16 | median band |
|---|---|---|---|---|
| `board` | `demand_reentry.zone_geom()` | `SWING_WINDOW` 5 / `ZONE_MERGE_PCT` 4.0 / `ZONE_HALF_WIDTH_PCT` 1.75 | **SPY 7 bands, QQQ 7** | 3.0% / 2.8% |
| `fine` | `supply_demand.price_zones` **module defaults** | `SWING_WINDOW` 4 / `ZONE_MERGE_PCT` 1.75 / `ZONE_HALF_WIDTH_PCT` 0.6 | **SPY 14 bands, QQQ 13** | ~1.1% |

The board set is read straight out of the `zone_store` doc (the geometry every
demand board, push and zone tile already runs on). The fine set is computed in
`index_zones.warm()` by calling

```python
price_zones.compute(frame, max_zones=None)   # NO geometry kwargs
```

through `zone_store.build_doc`, so it is slimmed, dated and closed-bar exactly
like the board doc. **Passing no geometry kwargs IS the fine setting** — the
knobs fall through to `price_zones`' own constants, the same ones the
per-ticker `/zones` page has used since 2026-06-09. Nothing here retypes
`1.75` / `0.6` / `4`, and `test_NEGATIVE_the_module_types_no_threshold_of_its_own`
fails the build if it ever does.

`default_resolution` is served on the payload and is **`fine`** — he asked for
*multiple* zones and the board set is seven. The constant is
`index_zones.DEFAULT_RESOLUTION`; the string is not scattered.

The **board** read stays at the top level of each index entry (`bands`,
`in_band`, `ceiling`, `floor`, `room_pct`, `drop_pct`, `sentence`, …) so every
consumer built against the first cut keeps reading the same keys, and
`resolutions.board` is the same read again.

### Pankaj's note — what we took and what we did not

His SPX levels are ~0.13% wide: hand-drawn intraday marks for a day trade.
**We do not copy them.** Hand-drawn levels are contaminated as a measurement
here — that is the `gabbar_backtest_2026_08_31` finding (in-sample 84% on
hand-drawn levels vs 72% out-of-sample on ours). We draw **our** bands, at our
two configured resolutions.

His rule —

> *"when a demand zone is broken, it becomes a supply zone and similarly when a
> supply zone is broken, it becomes a demand zone"*

— is **already how this engine reads**, and **no code was changed for it**. A
band's `kind` records where it came FROM (colour only); `ceiling` and `floor`
are the nearest band above and below of **either kind**, computed over every
band in the set. A demand band price has fallen through is the ceiling
overhead; a supply band price has broken above is the floor underneath. Since
2026-09-16 the `sentence` also **names the kind** (*"next demand band above
…"*), so the flip is visible on the strip instead of implied.

### The bars

Each index entry carries `bars`: **closed** daily candles in the
`{t, o, h, l, c, v}` shape `chart_maps.board._frame_to_bars` already emits for
every tile — the same shape, imported, not a second one. The window is
`chart_maps.board._zone_window` (`ZONE_BARS_MIN` 130 / `ZONE_BARS_MAX` 252 /
`ZONE_BARS_PAD` 15) taken over **every band in both sets**, widest wins, so the
oldest swing defining any band on screen is on screen. `bars_basis` says
`"closed"` on the wire; today's bar is dropped by `zone_store.drop_today`
before the frame is read.

## Everything is calculated overnight

`supply_demand.zone_store` warms at 04:05 ET on weekdays and already carries
SPY, QQQ and IWM with *every* band uncapped (`max_zones=None`) in board
geometry, drawn on **closed bars** with today's bar dropped. `index_zones.warm()`
runs after it and writes **one day document** carrying, per symbol, both
resolutions and the bars. The endpoint and the board then only *read* —
`test_NEGATIVE_serving_never_recomputes_a_band_or_touches_a_frame` makes
`price_zones.compute` and `zone_store.build_doc` raise during `served()` and
still expects a full payload. Run the job with
`python -m supply_demand.index_zones` (under `market_hours.gate`, weekdays).

Per symbol the job records **which source the board set came from**:

| source | meaning |
|---|---|
| `zone_store` | the overnight store had the doc — the normal path |
| `computed` | no store doc, so `zone_store.build_doc` drew the bands from `sepa.prices.load_prices` — same engine, same geometry, same closed-bar rule |
| `unavailable` | nothing readable. The symbol is **stored with a reason**, never silently dropped and never faked |

**Stored shape** (one document per ET session date, collection `index_zones`,
retention `zone_store.KEEP_DAYS`):

```
{_id: "2026-09-16", date: "2026-09-16", computed_at: <ISO>,
 source: "index_zones",
 indexes: {"SPY": <entry>, "QQQ": <entry>}}

<entry> = <board read>
        + {resolutions: {"board": <read>, "fine": <read>},
           bars: [{t,o,h,l,c,v}, …], bars_basis: "closed"}
```

**Each read** (`index_zones.READ_KEYS`) carries `symbol`, `name`, `source`,
`as_of`, `close`, `atr14`, `high_252`, `bands`, `in_band`, `ceiling`, `floor`,
`room_pct`, `drop_pct`, `available`, `reason`, `sentence`. Bands read
**high → low** and each one says `kind`, `side` (`above` / `below` / `in`) and
`dist_pct` from the stored close. `room_pct` is the ceiling's distance,
`drop_pct` the floor's.

**Served payload** (`index_zones.PAYLOAD_KEYS`):
`date`, `as_of`, `indexes`, `stale_days`, `stale_sessions`,
`default_resolution`, `note`.

## The basis rules

*Structure is read off closed bars.* `as_of`, `close`, `bands`, `ceiling`,
`floor`, `room_pct`, `drop_pct`, `sentence` and `bars` come from the last closed
session and do not move during the day. A live print says only **where price
is** inside that structure and lands in its own keys via `with_live()`, on the
entry **and on each resolution**, so the chart and the line beside it can never
disagree about the tape. A read built at 04:20 and the same read served at 15:00
differ in nothing else — pinned by `test_a_read_is_identical_at_0420_and_at_1500`.
This is the 2026-09-16 hot-sectors correction applied up front: a column
labelled with today that carried a snapshot was the worst bug of that week.

**`date` vs `as_of`.** `date` is the day the **job** ran (the doc `_id`).
`as_of` is the session the **bands** are drawn from — `zone_store` drops today's
bar, so it is the prior session, and a `zone_store` that failed days ago still
gets its old bands re-stored under today's date. Staleness is therefore measured
on **`as_of`**, never on the job day; a stale underlying store is visible
instead of masked, and the note names both dates when they differ
(*"…Stored by the 2026-09-16 job run."*).

**Staleness is served, not inferred.** `stale_days` is calendar days and
`stale_sessions` is market days (`market_hours.reminder.is_market_day` — one
holiday calendar, never a second copy). The page prints the word *session*, so
the number under it is `stale_sessions`. Friday's structure read on a Sunday
says *"drawn on closed bars, as of the 2026-09-18 session"* rather than crying
stale: the job is weekdays-only and the bands are closed-bar, so a weekend read
is the last close.

**The live vocabulary**, documented once in the module docstring and pinned as
`index_zones.LIVE_SIDES`:

| key | meaning |
|---|---|
| `live_side` | `in` / `above` (above every band) / `below` (below every band) / `between` (outside every band, in a gap between two) |
| `live_in_band` | the band the print is **in**, and only that. `None` for every other side — there is no "the band it was last in" |
| `live_dist_pct` | distance from the **live print** to the **nearest band edge**, as a percent of the print, **magnitude only** (`0.0` inside a band, `None` with no bands). Direction is `live_side`'s job, never a sign — the same convention every band `dist_pct` uses |
| `live_chg_pct` | the live print against the **stored close**, signed. The day move, not a structural distance |
| `price_basis` | `live` when a usable print was overlaid, `close` otherwise |

The live print comes from the board's **existing** bulk fetch — the strip's
symbols ride the `_live_rows` call the bounce gate and the room floor already
make, so pinning the strip costs zero extra provider calls per board load.

## Failure behaviour, all of it deliberate

A cold store returns the full empty shape (`index_zones.empty_payload` — one
builder, used by the endpoint, the board's failure branch and the cold-store
path) with HTTP 200, never a 500 and never a blank strip with no explanation. A
symbol with no usable close, no bands or garbage geometry reads
`available: false` with a reason. A provider outage costs the chart and the fine
set but not the board read the store already holds — `bars: []`, the fine
resolution `available: false` with its reason, the board read intact. A failure
anywhere in the index read is swallowed by the board, which still renders its
tiles.

## What this is not

It gates nothing, alerts nothing, orders nothing, enters no lane and claims
**no edge** — **nothing on this strip is measured as an edge.** Every measured
structural S/D read this month came back null: `band_structure` no_signal,
`deep_levels` no_signal, `enterable` no_signal, `explosive` no_signal. So the
`sentence` states position, kind and distance and stops there: no verdict, no
entry read, no target, no advice. The user-facing word for a turn is
**reversal**, never "bounce", and
`test_NEGATIVE_no_sentence_says_bounce_or_claims_an_edge` enforces it.

Configured price-structure method, **not** a book method — no Minervini cites.

**Tests:** `backend/tests/test_index_zones_2026_09_16.py`,
`backend/tests/test_chart_maps.py`.
