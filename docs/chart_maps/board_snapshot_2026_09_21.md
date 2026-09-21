# One live-quote call per board request (2026-09-21)

The 🌀 AMD tab took **64.7 s** to answer in pre-market. None of it was
computation.

`prices.with_today_bar(df, symbol, snap=None)` fetches `bulk_snapshot([sym])`
itself when nobody hands it a row. Every tile therefore opened its own HTTPS
connection, and the board opened a lot of tiles:

| where | calls per 80-tile AMD request |
|---|---|
| the builder's own tile loop (`bars_for(sym, days)`) | 80 |
| `_finish` → `_attach_bars` re-attaching the request's bars | 80 |
| the live now-line / 🎯 enterable fan-out | 1 |
| a **deep-window** tile (2y/3y/5y) — `support._frame_for` overlays the shared frame *and* the deep frame, then `bars_for` re-reads the info | up to 3 *each* |

`_attach_bars` runs in a `ThreadPoolExecutor` (`BAR_WORKERS = 8`), so those 80
handshakes are invisible to `cProfile` — they happen off the profiled thread.
That is the "another 9.8 s inside `_finish`" nobody could find.

Measured in-container (`cheetah-market-app-api-1`), 2026-09-21 ~10:05 ET, tape
`rth`, on `turning_bullish_tiles("amd", limit=80)` with `prices.bulk_snapshot`
wrapped in a counter:

| | wall | `bulk_snapshot` calls | symbols asked |
|---|---|---|---|
| BEFORE (`origin/main`) | **65.33 s** | **161** | 240 |
| AFTER (one prefetch + keep-alive) | **3.85 s** | **1** | 422 |

The AFTER run was the same code path with `bulk_snapshot` memoised over the
pool and `requests.get` swapped for a `Session.get` — an exact emulation of
§1 + §2 below, because the container runs `origin/main`, not this branch. Its
`TB.board` ran at `limit=80`; the shipped builder runs it at
`TB_FLIGHT_SCAN_LIMIT`, which is a sort of the same in-memory document and no
extra I/O.

## 1. A keep-alive session — `sepa/prices.py`

A bare `requests.get` opens a fresh TLS connection every time. Same endpoint,
same one symbol, median of 3 in-container:

| | median | samples |
|---|---|---|
| bare `requests.get` | 0.657 s | 0.657 / 0.651 / 0.679 |
| reused `Session.get` | 0.250 s | 0.265 / 0.235 / 0.250 |

**~0.41 s of every per-tile call was the handshake.** `prices._http()` returns
the calling thread's `requests.Session` with an `HTTPAdapter(pool_connections=4,
pool_maxsize=16)` mounted on `https://`. It is **thread-local** because
`bulk_snapshot` runs inside the bar-attach worker pool and `requests.Session`
is not documented as thread-safe.

Nothing else in `bulk_snapshot` moved: the 250-symbol chunking (`_SNAP_CHUNK`),
the `asked` spelling map, the row dict, the `_scrub_key` warning, the
`log.info`, and the `{}` it returns without a key (which is why every existing
board test already runs with no network).

`bulk_live_prices(syms, snaps=None)` gained one kwarg: the reshape without the
fetch. The dict comprehension inside it is **verbatim** — its
`'"low":              bar.get("low")'` line is pinned by
`test_supply_demand_contracts.py:310`.

## 2. `None` versus `{}` — the rule every new kwarg encodes

```
snap=None   nobody prefetched — fetch it yourself, and call the TWO-ARGUMENT
            with_today_bar that several long-standing stubs expect
snap={}     the bulk call ran and this symbol was not in it — "fetched,
            absent": no overlay, and NO second fetch
```

Never downgrade `{}` back to a per-call fetch. `ict/engine.py:216-218` forbids
it by name: on a failed bulk call that turns one 15 s timeout into eighty.

Where the kwarg travels:

```
chart_maps/board.py
  _bulk_snaps(symbols)            the ONE place the chart paths fetch; {} on
                                  any failure or an empty list
  _snap_for(snaps, sym)           None -> None; otherwise snaps.get(SYM) or {}
  bars_for(..., snap=)            deep branch -> support._frame_for(snap=) and
                                  _overlay_info(snap=); else branch -> the
                                  two-branch with_today_bar call
  _overlay_info(..., snap=)
  _attach_bars(tiles, days, snaps=None)
                                  fetches ONE bulk call for its own tiles when
                                  nobody handed it a map; ALWAYS passes snap=
                                  down, so workers never open a connection
  _finish(..., snaps=None)
chart_maps/support.py
  _overlay_today(mod, df, sym, snap=None)
  _frame_for(sym, need, *, with_closed=False, snap=None)
                                  hands the SAME row to both overlays
```

### Why `_finish` keeps a literal two-argument call

```python
short = tiles[:limit + BAR_BUFFER]
if snaps is None:
    _attach_bars(short, days)
else:
    _attach_bars(short, days, snaps=snaps)
```

Collapsing that into one call with a kwarg breaks four things at once:
`test_chart_maps_explosive_2026_09_15.py:257` pins the literal string
`_attach_bars(short, days)` appearing after the explosive sort, and
`test_chart_maps.py:899` plus `test_ipo_tab.py:609/665` stub `_attach_bars`
with a two-positional lambda on paths that do not prefetch. Thirteen of the
fourteen `_finish` call sites still use the two-argument shape.

The price of the explicit channel — chosen over a `ContextVar` that
`ThreadPoolExecutor` workers would have to re-set per task — was two one-line
re-pins, both in files this change owns:

* `test_chart_maps_explosive_2026_09_15.py:81` — `def _bars(tiles, days, **k)`
  (the AMD builder always prefetches, so this stub now receives `snaps=`)
* `test_deep_levels_board_2026_09_16.py:226` — `_spy(..., **k)`, forwarded to
  the real `bars_for` (it runs while the REAL `_attach_bars` drives the
  deep_demand board, so the worker's `snap=` reaches it)

And one rule that is easy to get wrong in the other direction: **never add
`snap=` to a call nobody prefetched for.** `_frame_for` briefly passed it
unconditionally and `test_zone_consistency_2026_09_14.py:155` — a
three-positional `_overlay_today` stub — turned the TypeError into "No price
data for TEST", i.e. the Support tab silently losing its board band.
`test_board_snapshot_2026_09_21.py` pins that shape.

## 3. The handoff to `board()` — `ctx`, not a payload key

The turning-bullish builders already hold the raw rows for their whole pool, so
`board()`'s live fan-out is a reshape, not a fetch. The map travels out of band:

```python
turning_bullish_tiles(..., *, ctx: Optional[dict] = None)
    ...
    if ctx is not None:
        ctx["snaps"] = raw          # the ONLY key it writes

board():
    _ctx: dict = {}
    ...
    _raw  = _ctx.get("snaps")
    _live = _live_from_snaps(_tiles, _raw) if _raw is not None else _live_snapshot(_tiles)
```

Not a payload key: raw snapshot rows carry pandas `Timestamp`s and the payload
has to survive `json.dumps` without `default=`. Not a module slot or a
`threading.local` either: `board()` runs inside `asyncio.to_thread` and is also
called synchronously from tests, so two requests would clobber each other and a
slot nobody reset would leak between tests. The `ctx` dict belongs to the one
call that made it.

`_live_from_snaps(tiles, raw)` builds the same sorted-unique upper symbol set
`_live_rows` builds and calls `prices.bulk_live_prices(syms, snaps=…)` — same
answer, zero network. `{}` on any failure.

## 4. Call count per tab, before and after

| tab | before | after |
|---|---|---|
| 🌀 amd / keltner | 80 (tile loop) + 80 (`_finish`) + 1 (live) | **1** |
| any generic `_finish` tab (zones, deep_demand, …) | 80 (`_attach_bars`) + 1 (live) | **2** |
| 📌 gabbar | 66 (60-day loop) + 72 (`_finish`) + 1 | **2** |
| a deep-window tile (2y/3y/5y) | 3 per tile | **0** |

The deep_demand / zones tabs stay at two because their builders do their own
`_live_rows` fan-out for the bounce gate, which is a *different* symbol set
(it carries the pinned SPY/QQQ index strip). `_bulk_snaps` calls
`prices.bulk_snapshot` directly rather than going through `_live_rows`, so the
two-call pin at `test_chart_maps.py:2358` is untouched.

## 5. New failure mode, accepted

A chunk-level HTTP failure now drops the live overlay for up to 250 names at
once, where per-tile calls failed one at a time. It is logged, **no tile
disappears** (the closed bars stand and the tile is still drawn), and it is the
same failure mode `_live_snapshot` has had all along.

## 6. Files

```
backend/sepa/prices.py                     _HTTP / _http(), bulk_live_prices(snaps=)
backend/chart_maps/support.py              _overlay_today(snap=), _frame_for(snap=)
backend/chart_maps/board.py                _bulk_snaps, _snap_for, bars_for(snap=),
                                           _overlay_info(snap=), _attach_bars(snaps=),
                                           _finish(snaps=), gabbar prefetch,
                                           turning_bullish_tiles(ctx=), _live_from_snaps
backend/scripts/snapshot_cost_probe.py     handshake + sweep cost, re-runnable
backend/tests/test_board_snapshot_2026_09_21.py   29 tests
backend/tests/test_amd_chips_2026_09_21.py        the read itself (see
                                           docs/supply_demand/turning_bullish.md §7)
```

## 7. Follow-ups, not done

1. The AMD tile loop still calls `bars_for` once and `_finish` reloads the same
   bars. With a prefetched row that is a parquet read, not a request, so it is
   cheap — but dropping it moves the "no frame" filter after the cut
   (`BAR_BUFFER = 6`) and could shorten a page, so it is **not** byte-identical
   and was left alone.
2. Parallelising the 250-symbol chunks inside `bulk_snapshot` would take
   `grades=all` under 1 s. `bulk_snapshot` is shared by 19 modules including
   the crons and it would change the provider rate behaviour — **his call**,
   only if 3.9 s at `grades=all` turns out to be too slow in practice.
