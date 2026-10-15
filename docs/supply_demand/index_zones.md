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
| `computed` | no store doc, so `zone_store.build_doc` drew the bands from the symbol's own frame — same engine, same geometry, same closed-bar rule (SPY / QQQ: `sepa.prices.load_prices`; since 2026-10-15 any symbol without a store doc reads a fresh `closed_daily_frame(use_cache=False)`, see below) |
| `unavailable` | nothing readable. The symbol is **stored with a reason**, never silently dropped and never faked |

**Stored shape** (one document per ET session date, collection `index_zones`,
retention `zone_store.KEEP_DAYS`):

```
{_id: "2026-09-16", date: "2026-09-16", computed_at: <ISO>,
 source: "index_zones",
 indexes: {"SPY": <entry>, "QQQ": <entry>,
           "TLT": <entry>, "UUP": <entry>, "GLD": <entry>}}

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

`indexes` lists **five** since 2026-10-15 (`index_zones.STRIP_SYMBOLS`: SPY,
QQQ, then TLT / UUP / GLD). A doc written before that lists two.

**Served payload** (`index_zones.PAYLOAD_KEYS`):
`date`, `as_of`, `indexes`, `stale_days`, `stale_sessions`,
`default_resolution`, `note`. Since 2026-10-15 every served entry also carries
`progress`, a **serve-time** overlay in its own key (never stored, never merged
into a stored or a live key) — see the 2026-10-15 section.

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

**An open session is not an elapsed session.** A market day counts toward
`stale_sessions` only once its own bar has CLOSED — tested with
`demand_reentry._session_fraction() >= 1.0`, the same clock
`split_today_partial` uses to decide whether today's row is a real bar, so
there is no second copy of the cutoff. Found on the live wire at 00:26 ET on
2026-09-17, minutes after the first warm: with bands drawn on the 09-16 close
the note read *"Bands are 1 session old"* — the freshest the strip will ever
be, and the one line that is supposed to mean *the overnight job broke* was
firing every day. `stale_days` (calendar) still says 1 there, and the two
disagree on purpose between midnight and today's close: the calendar has turned
over, the structure has not.

`staleness()` resolves its clock three ways. Production calls it with neither
`today` nor `now` and gets the live one. A caller that passes `now` gets that.
A caller that names a bare `today` DATE and no time of day is asking a calendar
question and gets the calendar answer — every market day in the window counts —
because reading the wall clock against somebody else's date would answer about
neither.

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

## 2026-10-15 — US bonds, US dollar and gold beside SPY · QQQ

Ajay, 2026-10-15: *"how can.I check us bonds and us dollar and gold can you
add them to the SPY and QQQ please? I wanna see their progress"*

### The three instruments — ETF proxies (MINE, his to swap)

Every bar in this app is a Massive US-listed security, so the dollar index
(DXY) and Treasury yields (US10Y / ^TNX) themselves have **no bars** and no
zones. The strip uses ETF proxies, one tuple, `index_zones.MACRO`:

| symbol | stands for (label) | alternative |
|---|---|---|
| **TLT** | US bonds (20y+) | IEF (7–10y) |
| **UUP** | US dollar | USDU |
| **GLD** | Gold | IAU |

`INDEXES` stays `("SPY", "QQQ")` — the two cards. The overnight job warms
`STRIP_SYMBOLS = INDEXES + MACRO_SYMBOLS`. House precedent for two of them:
`rotation/tracker.py` `HAVEN_PROXY` already reads GLD and TLT. Swapping a proxy
is one edit to `MACRO` (the FE mirrors it under a `?raw` pin) and the
disclaimer renames itself — it is built from the constants.

### The overnight path

- **Same job, no crontab line.** The existing `15 4 * * 1-5 … market_hours.gate
  supply_demand.index_zones` warms all five because `warm()`'s default list grew.
  **A deploy must include `cron`** (`./deploy-cheetah-main.sh api frontend cron`):
  the cron worker runs the image it was created from, so without it the 04:15
  job keeps writing SPY / QQQ only and the rows fall back to "not stored yet".
- **Source `computed`.** TLT / UUP / GLD are not in the `full` universe, so
  `zone_store` never warms them. They take the existing fallback:
  `zone_store.build_doc` with board geometry (`zone_geom()`) and the fine set
  (`_fine_compute`) off ONE frame, closed bars, today dropped. They are not added
  to `zone_store`, because that would grow the universe the 09:33 zone pass and
  the demand boards read. Expected log line:
  `sources={'zone_store': 2, 'computed': 3, 'unavailable': 0}`.
- **Cost.** Three fresh 2y fetches on every run plus two or three `build_doc`
  passes over ~500 bars: **≈ 2–6 s, estimated** (the job ran < 1 s on
  2026-10-14). The first hand-run measures it; quote that, not this estimate.
- **The fresh, never-cached frame.** A symbol with no zone_store doc is read by
  `prices.closed_daily_frame(sym, now=now, period="2y", use_cache=False)`. It
  never READS the shared `price_cache` and never WRITES it. Why not the others:
  - `load_prices(sym, period="2y")`: an in-session fetch (a late job, a hand-run)
    caches today's unfinished bar under the 20 h `CACHE_TTL_SEC`; the next 04:15
    run drops only bars dated today, so it would store that partial bar as the
    prior close. TLT / UUP / GLD are not in `full`, so the 16:30 final-close
    patch never repairs it.
  - `load_prices(…, force=True)`: one fresh fetch, but it WRITES the shared
    cache with `cached_at` = 04:15, and rotation's 17:10 warm and 17:20 history
    read GLD / TLT out of that cache under the same TTL — they would lose each
    day's close (or, after a 10:00 hand-run, keep a 10:00 print as the close).
  - `closed_daily_frame` with the cache: it accepts a cached frame that holds
    the last session, and an intraday-written bar does.
  A failed fetch stores the symbol `available: false` ("nothing stored for it")
  for the day; the cached frame is never a fallback. SPY / QQQ keep
  `load_prices` (they are in `full`; their cache gets the 16:30 close).

### `progress` — the serve-time read

Served on **every** entry (SPY / QQQ included; the page draws it only on the
macro rows), built by `with_progress` after `with_live`. Never raises: a failure
serves every number `None`, `today_state` `unavailable`, every text "—".

| key | value |
|---|---|
| `through` | the last stored closed bar's date (= `as_of` on a healthy doc) |
| `ret_5d` / `ret_21d` | `rotation.tracker.trailing_return(bars, WINDOW_FAST / WINDOW_SHORT)` over the STORED closed bars (the candles the chart draws), 2 dp; `None` with too few bars or a non-positive base |
| `today_pct` | the strip's own live print (pre- and after-hours included) against `resiliency_tab.official_prev_close` — the snapshot's prior close when its day bar is dated the session and agrees within `drop10_tab.PREV_CLOSE_TOL_PCT`, else the stored close — 2 dp |
| `today_prev_close` | that base, 2 dp |
| `today_state` | below |
| `windows` | `{"ret_5d": RT.WINDOW_FAST, "ret_21d": RT.WINDOW_SHORT}` — the page prints "5d" / "21d" from these |
| `text` | `{today, ret_5d, ret_21d}` via `high_beta_tab.leg_text` ("+1.3%" / "−0.3%" / "—") |
| `note` | the today sentence + the legs sentence, built from the numbers |

| `today_state` | when | number |
|---|---|---|
| `read` | the stored close IS the prior session's close and a print dated today matches the shown `live_px` | the move |
| `no_session` | today is not a market day (`market_hours.reminder.is_market_day`) | `None` |
| `basis_behind` | `as_of` is not `key_levels.prev_market_day(today)` — the overnight job has not stored that close; "today" would be a multi-day move | `None` |
| `no_print` | no row, no positive print, a print that is not the one the row shows, or a last trade not dated today | `None` |
| `unavailable` | nothing stored for the symbol | `None` |

An unread state is **never** `0.0` and never "+0.0%". `live_chg_pct` keeps its
meaning (ungated, vs the stored close) and is never drawn on a macro row; only
the gated `today_pct` is.

**Rounding.** `progress_read` is the ONE rounding point: every number is 2 dp
of the RAW move, every text is 1 dp (`leg_text`, HALF_UP) of the RAW move,
never of the 2 dp number — a raw 1.2496 serves `1.25` and prints "+1.2%"
(a double round would print "+1.3%"). The today move uses the UNROUNDED print.

**One fetch.** The board hands the strip both the prints AND the
bulk_live_prices rows it already fetched (only the strip's symbols — a tile's
row never reaches it); the warming branch and the route take one `live_rows`
fetch, and the prints and the today read come off the same rows.

**The header's date.** The strip header's `as_of`, `stale_sessions` and note
are measured on **SPY / QQQ only** (`basis_date` over `INDEXES` first, all
reads only when neither is readable), so fresher macro rows never hide a stale
SPY / QQQ header and one stale macro row never ages a fresh one.

### The rows on the page

SPY and QQQ keep their cards unchanged. Under them sits one compact row per
macro symbol, in his order (bonds, dollar, gold): symbol · label · live print ·
today · 5d · 21d · the band it stands in or how far the nearest band is. Every
number is served; the page does no arithmetic on a move. A row whose own date
(`progress.through`, else `as_of`) differs from the header's prints
`through {date}` on the row itself (e.g. UUP's stale cache). Tapping a row
expands it in place to the SAME chart and zone ladder SPY and QQQ have, with
the served `progress.note` as its first line (a touch screen has no hover
title); one row is open at a time and the open one rides `?iz_open=SYM`, which
survives a reload and is dropped when leaving the zones tab.

**Before the first run** the stored doc has no macro entry, so the served
`indexes` lacks TLT / UUP / GLD (`served()` never warms and never invents an
entry). The row says it is not stored yet and computes overnight with SPY and
QQQ — never a zero, never blank.

### HIS CALLs (defaults shipped)

1. The proxies TLT / UUP / GLD and their labels (alternatives above).
2. Today counts pre-market and after-hours prints (the move of the price the
   row shows); the alternative is regular-session only.
3. Today is "—" with a reason on weekends / holidays and until the overnight job
   stores the prior close; the alternative is showing the last session's move.
4. 5d / 21d end at the last STORED closed session; in market hours today stays
   in Today.
5. The row's band phrase reads the fine set (the strip's default resolution).
6. Rows open collapsed, one at a time, param `iz_open`, dropped off the zones tab.
7. SPY and QQQ show no progress line although it is served for them.
8. Title "🧭 SPY · QQQ · macro zones"; the disclaimer wording is built from
   `MACRO`.
9. The percent band geometry is not retuned for UUP's low volatility.
10. One hand-run fill before the deploy vs waiting for the first 04:15 run.
11. The 2026-10-15 04:15 doc was missing — investigate separately, or not.
12. Today's reason inline in the collapsed row (default: hover title + the
    opened row's first line).
13. The throwaway API for the hand-run (default: the no-drain launcher).

Context only — it gates nothing, alerts nothing, enters no lane, and measures
nothing. Not advice.

**Tests:** `backend/tests/test_index_zones_2026_09_16.py`,
`backend/tests/test_index_zones_macro_2026_10_15.py`,
`backend/tests/test_prices_market_snapshot.py` (`use_cache=False`),
`backend/tests/test_chart_maps.py`.
