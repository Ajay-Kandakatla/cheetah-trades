# Bounce + room — `POST /supply-demand/bounce-room` (SEPA filter · Back-in-Demand sort · Catalysts sort)

**Ask (Ajay 2026-09-05, verbatim):** *"Can you help add a new filter to SEPA and In demand and
also catalyst also move catalyst tab in to Chart maps. The Filter need to check. #1 for Sepa
stocks that is bouncing off of Demand zone. #2 for in demand Make sure you sort stocks by
bouncing off of demand zone and have big gap in to supply. #3 for catalyst same deal make sure
you sort stocks by bigger gaps in to supply like EOSE stock and CLYM as an example they have
bigger gap and room to grow."*

Configured price-structure heuristic, S/D scope, **NOT a book method, no Minervini cites, no SEPA
gates**. Every threshold below is an **owner setting**. Decision support, never a buy signal, not
advice. Coverage is partial by design — a `pending` or `unavailable` row is *not* a CLEAR.

Module: `backend/supply_demand/bounce_room.py` · routes: `POST /supply-demand/bounce-room`
(`{"symbols": [...]}`) and `GET /supply-demand/bounce-room?symbols=A,B` (short lists; same
function) · tests: `backend/tests/test_bounce_room.py`, `test_zone_store.py` (`recent`,
`latest_store_day`), `test_supply_demand_contracts.py` (source guards) · frontend mirror of the
ordering: `frontend/src/lib/bounceRoom.ts`.

## Why one module

Three pages ask the same two questions of the same bands. Computed three times, "bouncing" means
three things within a week. So: pure reads here, one route, one ordering key the frontend mirrors
1:1. The bands are the **zone_store's** (board geometry, every band, both kinds, drawn BEFORE the
store day — `docs/supply_demand/zone_bounce_alerts.md` §1) — the same bands the phone's
`zone_bounce_alert` and `zone_edge` passes read. Nothing here draws a new band.

## The doc it reads (zone_store, + one additive field)

```
{_id: "SYM:2026-09-04", symbol, date, geom: "board",
 bands: [{kind: "supply"|"demand", lo, hi, touches, strength}, ...],
 atr14, prev_close, high_252,
 recent: [{date, low, high, close}, ...],     # NEW 2026-09-05: last RECENT_SESSIONS=5 CLOSED bars, oldest first
 computed_at}
```

`recent` is the tail of the frame **after `drop_today`** — today's bar never appears (a band drawn
from today's own low would be instantly "touched"). Rows with a missing/NaN low are skipped; `[]`
on any failure. `zone_edge` / `zone_bounce_alerts` never read it (source-guarded) and keep
`load(None, today)`. Docs stored before 2026-09-05 have no `recent` → only today's touch is visible
for them until the next 9:20 warm.

## The two reads (pure)

### BOUNCE — `touch_hits(doc, snapshot_low, snapshot_date, store_date, snapshot=snap)` → `bounce_read(print, doc, touches)`

| step | rule | constant · where it lives |
|---|---|---|
| eligible | demand bands always; supply bands only when `hi < prev_close` (broken supply = support). Unknown `prev_close` → supply never eligible, demand still is. | `zone_bounce_alerts.is_eligible` (imported) |
| TOUCH | a session **low** with `low <= hi·(1+1%)` **and** `low >= lo·(1−1.5%)` | `TOUCH_TOL_PCT=1.0`, `WICK_PCT=1.5` — **imported** from `zone_bounce_alerts`, never redefined |
| sessions | each `recent` closed session, newest = 1, up to `LOOKBACK_SESSIONS` (`recent[-1]` is the bar **before** the store day — `drop_today`). The snapshot's day bar is `sessions_ago 0` **only when it IS the store day's own session**, decided by **data, not by its date** (`is_store_session_bar`): (a) low / high / close equal to `recent[-1]`'s → it is that closed bar, never counted again; (b) else date == store day, **or** date later **and** the snapshot's `prev_day_close` == the doc's `prev_close`. Its `touch_date` is the store day. | `LOOKBACK_SESSIONS = zone_store.RECENT_SESSIONS = 5` (one number; a touch older than the doc's list cannot be seen) · `PX_REL_TOL = 1e-6` |
| BOUNCE | `print > band.hi` **and** `print >= touch_low·(1 + max(3%, 100·atr14/touch_low)/100)` | `BOUNCE_MIN_PCT=3.0` (imported) |
| **no arrival gate** | the alert's `ARRIVAL_PCT` is an anti-noise rule for *pushes*; a **filter** must also list a name that lived near the band and lifted off it (residence bounce). `test_residence_bounce_counts_there_is_no_arrival_gate` locks the contrast against `zone_bounce_alerts.read`. | — |
| pick | several bands/touches qualify → **freshest touch first** (smallest `sessions_ago`), then the biggest `bounce_pct` | — |
| fields | `bounce_pct=(print/touch_low−1)·100` · `floor_pct` · `strong = bounce_pct >= max(5%, 2·atr_pct)` · `atr_x=(print−touch_low)/atr14` · `role` demand \| broken_supply · `touch_low`, `touch_date`, `sessions_ago`, `band{kind,lo,hi,touches,strength}` | `STRONG_PCT=5.0` (imported) |

### ROOM — `room_read(print, doc)`

> **2026-09-06 — proven lids.** `overhead_bands` skips a band that fails
> `alert_gates.is_proven_band` (< 2 touches or strength < 40); the SEPA 🪃 chip,
> the Demand sort and the Catalysts room sort therefore measure to the first
> PROVEN lid. See `docs/supply_demand/proven_lids.md`.


| step | rule | constant |
|---|---|---|
| overhead | supply bands with `hi >= print` that are **not already broken** — a supply band with `hi < prev_close` (the doc's; yesterday **closed** above it) is support, skipped (integrator 2026-09-05, Ajay: *"yes please fix the bugs"* — the same rule `zone_bounce_alerts.is_eligible` / `alert_gates` / `zone_edge` Side B use; without it the 🪃 push said "room: clear runway" while this read still quoted room to the 173.87 NTAP shelf); unknown `prev_close` = every supply band counts — **plus demand bands with `lo > print`** (broken support = resistance, kind `broken_support`). A demand band that *contains* the print is support, never overhead. `portfolio.supply_watch.overhead_bands` took the same `prev_close` (from the quote's `prev_day_close`; the fallback quote path has none → unchanged). | same rule as `portfolio.supply_watch.overhead_bands`; re-stated here because the `portfolio` package cannot be imported on the py3.9 host — `test_overhead_rule_matches_portfolio_supply_watch_loaded_standalone` loads that file by path and compares every print |
| first | the overhead band containing the print (lowest `lo` when nested), else the lowest `lo` | = `supply_watch.nearest_supply` |
| **CLEAR** | nothing overhead in the 1y frame → `room_pct null`, `band null` | |
| **IN_BAND** | first contains the print → `room_pct 0.0`, `atr_days 0.0` | |
| **NEAR** | `room_pct = (lo/print−1)·100 <= NEAR_PCT` | `NEAR_PCT = 2.0` (= supply_watch's NEAR line) |
| **ROOM** | otherwise; `atr_days = (lo−print)/atr14` (null when ATR unknown) | |
| at_highs | `high_252` known and `print >= 0.98·high_252` — independent of the room state | `zone_edge.NEW_HIGH_TOL` (imported) |

### Print — `print_of(snap, now_ts)` → `(px, fresh)`

`last_trade_price` when its stamp (**ns** on Massive; ms/s normalised by
`zone_bounce_alerts.print_from_snapshot`) is within `STALE_PRINT_SEC = 180` of now → `fresh true`.
Older → **the same last trade, `fresh false`** — a filter shows the last known price and flags it;
only the phone alert drops stale prints. No last trade → the day `close`, `fresh false`. No price
at all → the row is `unavailable` ("no print in snapshot").

## Ordering — `room_rank(row)` and `bounce_room_key(row)` (mirrored in the frontend)

```
room_rank(row)       (0, 0.0)          CLEAR
                     (1, -room_pct)    ROOM / NEAR / IN_BAND — biggest room first (IN_BAND = 0 last of these)
                     (2, 0.0)          no room read: pending / unavailable / null
bounce_room_key(row) (0 if bouncing else 1,  *room_rank(row),  -bounce_pct,  symbol)
```

**Why CLEAR sorts first.** No supply band overhead in the 1y frame means the name is at/near its
highs — its room is *unbounded*, not zero. Ajay treats names clearing their last supply as the
ones "likely to go much higher"; EOSE and CLYM in the ask were exactly that shape. A page may
label CLEAR "at highs · no supply overhead" instead of a %, the order is the same. A `ROOM` without
a `%` is unknown (group 2), never promoted.

## How each surface uses the read

| surface | what it asks | what it does with the row |
|---|---|---|
| **SEPA scanner** (`frontend/src/components/SepaFilterBar.tsx`) | POST the visible scan's symbols (≤ 2500; the full universe is ~1,750) — **only while the 🪃 chip is on** (`Sepa.tsx` hands the hook an empty list otherwise: nothing else on the page reads the map, and the default page must not fan out a snapshot + on-demand builds every minute for zero output) | new filter chip "Bouncing off demand": keep rows whose `bounce` is non-null; chip shows the touched level, `+bounce_pct%`, `sessions_ago`, `role`; `fresh false` renders a stale tag. Never a buy signal — the SEPA verdict is untouched. |
| **Back in Demand** (`frontend/src/components/DemandReentryPanel.tsx`, "N in demand") | POST the board's symbols | sort by `bounce_room_key`: bouncing first, then CLEAR, then biggest room to the first supply band; the room column shows `room_pct` / `atr_days` / the band, `pending` rows keep their old position at the end with a "room pending" tag. |
| **Catalysts** (`frontend/src/pages/Catalysts.tsx`, a Chart Maps tab since 2026-09-05; `catalysts` and `chart-maps` are separate access grants, so `/catalysts` redirects only for users who hold `chart-maps` and the tab is offered only to users who hold `catalysts`) | POST the board's symbols (mostly *not* in the $1B+ store → `ondemand`) | same key — "bigger gaps in to supply" = `room_pct` desc under CLEAR; first poll shows most rows `pending`, the 30 s poll after the worker finishes fills them. |

Every label must be honest about coverage: `pending` = "room pending", `unavailable` = the
`error`, `fresh false` = stale print, `store_date` = the day the bands are from.

## Response contract

```
{
  "as_of": "2026-09-05T13:02:11-04:00" | null,     ISO ET of the snapshot read (null = nothing covered, no read)
  "in_session": true|false,                         9:30-16:00 ET Mon-Fri evaluated at request time
  "store_date": "2026-09-04",                        the zone_store day the bands came from
  "params": {"touch_tol_pct": 1.0, "wick_pct": 1.5, "bounce_min_pct": 3.0, "strong_pct": 5.0,
             "lookback_sessions": 5, "near_pct": 2.0, "stale_print_sec": 180, "new_high_tol": 0.98},
  "rows": {
    "AVGO": {"symbol", "print", "fresh", "coverage": "store"|"ondemand",
             "bounce": null | {"band": {kind, lo, hi, touches, strength}, "role": "demand"|"broken_supply",
                               "touch_low", "touch_date", "sessions_ago", "bounce_pct", "floor_pct", "strong", "atr_x"},
             "room": {"state": "CLEAR"|"IN_BAND"|"NEAR"|"ROOM", "room_pct": 17.0|0.0|null, "atr_days": 3.1|null,
                      "band": {"kind": "supply"|"broken_support", lo, hi, touches} | null, "at_highs": bool}},
    "XYZ":  {"symbol": "XYZ", "coverage": "pending"},
    "ABC":  {"symbol": "ABC", "coverage": "unavailable", "error": "no / insufficient price data"}
  },
  "requested": 25, "covered": 21, "pending": 3, "unavailable": 1,
  "disclaimer": "Configured price-structure heuristic ... not advice."
}
```

Rows are keyed by symbol in request order; **the page sorts** with the mirrored key. Body:
`{"symbols": [...]}`, upper-cased + de-duplicated (first occurrence wins), capped at `MAX_SYMBOLS =
2500`, **422** when empty after cleaning (or when `symbols` is missing / not a list).

## Coverage story

| coverage | meaning |
|---|---|
| `store` | the symbol has a `zone_store` doc for the **latest stored day <= today** (`zone_store.latest_store_day`, one `distinct("date")`). Saturday evening answers with Friday's bands — never "empty because today has no doc". `load(None, day)` keeps its exact this-day semantics for the intraday crons; `load_latest` is the explicit new path. |
| `ondemand` | not in the $1B+ store (small caps, foreign names, the Catalysts board). **One** daemon worker (`queue_ondemand` → `compute_batch`, pattern `catalysts/promo_live.zones_for/_bg_compute`) builds the **same doc shape** with `zone_store.build_doc(sym, prices.load_prices(sym, "2y"), store_day)` — the shared price cache, never a provider call on the request path — tags `origin: "ondemand"` and caches it in Mongo `bounce_room_zones` (`_id "SYM:date"`) plus an in-process copy. `ONDEMAND_MAX_QUEUE = 400` symbols handed over per request, `ONDEMAND_BUDGET_SEC = 240` per batch; a second request while the worker runs is not queued — its misses are re-discovered on the next poll. |
| `pending` | queued, no doc yet. The request returns **immediately**; the page polls (30 s) and the next response after the worker ran has the row. |
| `unavailable` | a Mongo tombstone `{"error": "no / insufficient price data"}` for the day when the frame cannot support a doc (missing / < 120 bars) so nothing retry-storms; **a build that raised** (Mongo / provider hiccup inside `load_prices`, pandas error) gets an **in-memory** marker `{"error": "engine error", "retry_after": now + ENGINE_RETRY_SEC (600)}` — never a day-long tombstone, never the exception text in the browser — and is re-queued once the marker expires; or a covered name with no print in the snapshot (`"no print in snapshot"`); or the snapshot call failed for the whole batch (every covered row reads unavailable, `as_of` still set). |

Store cold (no doc at all, e.g. first day / warm failed): `store_date` falls back to the **last
weekday** <= today ET (`last_weekday`; a Saturday doc would keep Friday in `recent` and see it again
in the snapshot) and everything goes on-demand. `bounce_room_zones` is purged past
`zone_store.KEEP_DAYS` (7) at the end of every batch (`purge_ondemand`) — same window as the store.

**Cost per request:** one `zone_store` read, one `bounce_room_zones` `$in` read, one chunked
`bulk_snapshot` for the **covered** names only (pending/unavailable never hit the provider). Whole
response cached `RESPONSE_TTL_SEC = 30` per **sorted symbol set** (clock = the request's `now`), so
three pages polling the same list fan out exactly one snapshot call per 30 s. Source-guarded: no
`load_prices` / `for_symbol` / `with_today_bar` / `find_one(` on the request path.

## Traps

* **The snapshot's date lies on non-session days.** `sepa.prices.bulk_snapshot` dates the day bar
  TODAY when Massive omits `day.t` (its own comment), so on a Saturday Friday's OHLC arrives dated
  Saturday and on a weekday holiday Friday's OHLC arrives dated Monday. The sessions_ago-0 test is
  therefore **not** date equality — it is `is_store_session_bar`: identical low / high / close to
  `recent[-1]` → that closed bar, not counted again; else store-day session when the date matches
  **or** the date is later and `prev_day_close == doc.prev_close` (the bar before the store day).
  Which sessions are visible: **weekday intraday** — today (0) + 5 closed; **weekend** — Friday (0,
  `touch_date` = Friday, from the snapshot) + Mon–Thu (1–4) + the Friday before (5), since the Friday
  doc's `recent` ends Thursday; **weekday holiday warm** (doc dated the holiday, Friday in `recent`) —
  Friday reads once as `sessions_ago 1`; **store a day behind** (warm failed, Monday snapshot over a
  Friday doc) — Monday's low is *not* seen (prevDay = Friday's close ≠ Thursday's): an honest miss,
  never a false touch. Massive's other weekend shape (a zero `day` bar) has no low → only `recent`
  touches show; the print still comes from the last trade.
* `snapshot.date` is a pandas Timestamp; `_iso_day` normalises str / date / Timestamp.
* Within one session every band shares the same low, so "then the bigger bounce" only decides
  between *different sessions with equal freshness* — which cannot happen — or between synthetic
  touch lists; the tie between two bands touched by the same low goes to the **higher shelf**.
* `room_pct` for `IN_BAND` is `0.0` (sorts last inside group 1); for `CLEAR` it is `null` (group
  0). Do not coerce null to 0 on the page — that would send the unbounded names to the back.
* On-demand docs are dated the **store day** (or, store cold, the last weekday), so on Saturday they
  are built with `drop_today(df, Friday)` — Friday's bar is excluded from the bands and from
  `recent`, and the weekend snapshot (Friday's bar dated Saturday, prevDay = Thursday) reads as
  `sessions_ago 0` through the prev-close identity. Consistent with the store docs.
* `_mem` also carries the `engine error` markers (memory only, `retry_after`); a Mongo tombstone is
  written only for `builder → None`. The in-process worker flag is released if the thread cannot
  start, so a resource-pressure `RuntimeError` never leaves every later miss pending forever.
* `_mem` (in-process on-demand copy) only serves the current store day; other days are dropped on
  every read. A container without Mongo still answers from it after the worker runs.

## Verify in the container (read-only)

```
docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -m supply_demand.bounce_room EOSE CLYM AVGO NTAP'
```

Prints the payload header (`as_of`, `store_date`, counts) then one JSON row per symbol in
`bounce_room_key` order. First run on names outside the store shows them `pending`; run again
after ~10 s. The route: `curl -s -X POST localhost:8000/supply-demand/bounce-room -H 'content-type:
application/json' -H 'X-User-Email: ...' -d '{"symbols":["EOSE","CLYM"]}'`.

Not a book method. Not a buy signal. Not advice.
