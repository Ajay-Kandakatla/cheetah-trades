# 📐 Daily supply & demand zones on the 👀 Watch (2026-11-23)

Ajay, 2026-11-23, verbatim: "can you add vwap and supply demand zone in the daily time frame on the watch list please"
… "Add vwap and supply demand too".

He was told GG draws daily support / resistance (S8 1:19:00). **Display only — nothing gates, sorts, rings, caps or
sections on a zone. UNMEASURED.** Spec: `vwapzones` revision 2, §3.6 / §3.6b / §3.7 (work package be-zones).
The VWAP half lives in `docs/gajjala/watch_frames_vwap_2026_11_23.md`.

## Engine and geometry

- ONE engine: `supply_demand.zone_store.build_doc` = `price_zones.compute(frame, max_zones=None, **demand_reentry.zone_geom())`
  on CLOSED daily bars (the session's row dropped). `zone_geom()` is the BOARD geometry (swing window 5, merge 4.0 %,
  half-width 1.75 %) — the same bands every S&D board, alert and lane reads. Nothing in the Watch computes a zone.
- Served cut = the engine's own surfacing rule: `price_zones.nearest_first` per kind, N = `C.ZONES_PER_SIDE`
  (None → `price_zones.MAX_ZONES_PER_SIDE` = 4, read by name), sorted high → low (`levels.near`).
- Served as `ctx` bands of the two BOARD kinds (`C.ZONE_BAND_KIND` → `board_demand` / `board_supply`: the house dashed
  outline, never a fill). A served band carries exactly `kind, lo, hi, label, gutter, ctx` (never `pad_lo`).
- One served line per row: the zone price is inside, the next below (`% under`), the next above (`% over`) — over ALL
  bands, the engine's own reading (inside = lo ≤ P ≤ hi). P = the last close of the stored 1-min bars, else the stored
  prior close. Prices go through `tab._px`; the % through `runners.pct_show` (floored).

## The fresh daily read and why [C5]

`levels.default_loader` = `sepa.prices.closed_daily_frame(sym, now=<session 00:00 ET>, period=C.ZONES_PERIOD, use_cache=False)`.

- The cached frame (the default) can hold an intraday-written, unfinished bar or a pre-split history; only
  `use_cache=False` cannot reach an unfinished bar (its own docstring). `C.ZONES_PERIOD` = `"2y"` = `zone_store.warm`'s
  loader period = `index_zones`' display-zones read — a source-read test pins both.
- Cost: ONE Massive daily call per name per session (15 s timeout, one 2 s 429 retry, then the yfinance fallback);
  `build_doc` ≈ 5.8 ms / name (critic's provisional read).
- `closed_daily_frame` returns None for "no bars" and for a provider failure alike, so an empty read is stored as
  `retry` — NOT latched — and the words say "the daily read returned nothing", never "no daily bars on file".

## Storage

On the name's Watch tile doc (`gajjala_watch_tiles`), key `levels`, ONE `update_one` `$set` per read — never an
upsert, never another collection (the S&D `zone_store` collection is read by alert paths; the Watch never writes it):

| state | stored keys | latched |
|---|---|---|
| `ok` | session, bands (every band of build_doc), prev_close, through, n_bars, geom, at | yes (the session) |
| `none` | session, why = `short` (under `zone_store.MIN_BARS`) / `none` (engine found none) / `error`, n_bars, at | yes |
| `retry` | session, why = `no_daily`, tries, at | **no** |

Served `state` ∈ `C.LEVELS_STATES` (`pending` = not read for this tile's session yet).

A name whose levels were read for a LATER session than its stored tile (read today, the tile still shows the last session because the name has not printed yet) serves `pending` with `LEVELS_WAITING_TEXT` ("read for today — they show at {sym}'s first print today"), never the "in line" words; no bands are drawn on the older chart. Pinned in `test_gajjala_watch_levels_2026_11_23.py` (both `ok` and `none`; NEGATIVE: an earlier session or `retry` keeps the old words).

## When it reads (off the minute path)

- `warm()` never runs inside `run_iteration` (a 15 s provider stall would end the minute loop's slot, Z7). The loop
  child starts it on a daemon thread (`levels.spawn`); the add-time build child calls it after each build round.
- Order per call: (1) the names this build child just built — uncapped, each once; (2) listed names (owner list + the
  🤖 auto names) with a tile doc lacking this session's zones, list order; (3) this session's `retry` docs, fewest
  tries first. (2) + (3) together are cut to `C.ZONES_MAX_NEW` (= `GC.DAILY_MAX_NEW_PER_PASS`, 8) per call. Reads are
  SERIAL. A raising loader = a `retry` doc. No store → no read.
- Retry rule: a `retry` name is read again at the next call, behind every never-read name, inside the cap. It has no
  end (worst case 8 wasted reads a slot) — HIS CALL #19.

## The card ⤢ / card-grid frames (`for_card`) — never waits on a provider

The card frames GET feeds every card tile on screen at every board read, so it never reads daily bars inline:
(1) the Watch tile's stored `levels` of this session in state ok / none → served; (2) the per-process memo — ok / none
kept for the session, `retry` only for the 5-minute slot it was read in (`run_1m.slot_of`); (3) a miss → the key queued
once (single-flight, one daemon worker, serial) and "📐 Daily zones: reading now — they show at the next refresh"
served now; the next GET serves the bands. The memo clears when the session changes; nothing is written to Mongo; an
API restart re-reads once per name. A stores tuple of 2–4 elements (tests) never reads daily bars.

## Limits stated on the surface

- [C4] A high or low of the last `zone_geom()["swing_window"]` (5) closed sessions can never be a band:
  `_local_extrema` scans `range(w, n − w)`. So yesterday's high is usually not drawn. The rules sentence says so; a
  test pins the engine fact (a spike 1…5 sessions back → no band at it, 6 back → one). Prior-day high / low lines =
  HIS CALL #18 (not built).
- [C3] Under $1 the engine rounds band edges to the cent, so a band can be up to ~13 % wide or zero-width (`lo == hi`,
  e.g. HXHX 0.12–0.12). A zero-width band is KEPT, drawn as one dashed line, and printed as ONE price ("Daily demand
  0.12"). The engine is not touched (Rule #10) — HIS CALL #12.
- Names under `zone_store.MIN_BARS` (120) daily bars get none ("… the zone engine needs 120 — none drawn").

## Coverage table (PROVISIONAL)

Script: `backend/scripts/gajjala_watch_levels_coverage.py` — read-only, ONE tiles find + `prices.bulk_cached_frames`
(cached frames, NOT the fresh read), no fetch, no write, imports only modules on origin/main; its inline `near` is
pinned equal to `levels.near` by `tests/test_gajjala_watch_levels_2026_11_23.py`.

```bash
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.gajjala_watch_levels_coverage
```

Script run 2026-11-23 (read-only, cached daily frames — PROVISIONAL, not the overlay's fresh read; nothing fetched,
nothing written; `docker exec -i -w /app cheetah-market-app-api-1 python - < backend/scripts/gajjala_watch_levels_coverage.py`).
It reproduces the critic's typed read row for row. The sub-$1 width row is width over the BAND's own mid
(100 · (hi − lo) / mid, served bands with mid under $1) against the engine's 3.5 % intent for a single swing — an
earlier draft divided by the NAME's last price and printed 47,573.7 % for a far-away band of an old history; that
read measured nothing and is gone (pinned by `test_coverage_widest_sub1_band_is_width_over_its_own_mid_not_the_name_price`).

| Read | Count |
|---|---|
| Watch tiles read | 96 |
| … with no 1-min bars | 0 |
| … with no cached daily frame (never fetched) | 0 |
| Watch names under $1 | 51 of 96 |
| names carrying a zero-width served band | 7 (HXHX 0.12–0.12, GIPR 0.15–0.15, MERC 0.21–0.21, SMTK 0.23–0.23, LABT 0.17–0.17) |
| widest served sub-$1 band, % of its own mid (engine intends 3.5 %) | 13.3 % |
| names drawing NO zone inside the chart range | 32 of 88 |
| names under `zone_store.MIN_BARS` | 8 |
| names losing an in-range band to the 4-nearest cut | 8 |
| names drawing 5+ bands on one chart | 8 |
| prior-day high inside the chart range | 45 of 88 |
| … and in NO band | 34 of 88 |
| `build_doc` cost (median) | 4.5 ms / name |

## Rules panel [C7]

`supply_demand/rules_info._gg_watch_overlays_clause()` joins `vwap.rules_line()` and `levels.rules_line()` into the
Gajjala note right after the 📅 runners clause; each half in its own try (a broken module drops only its half). The
same sentence is the legend hover and the ℹ️ line.

## Files

`backend/chart_maps/gajjala_watch/levels.py` (new), `backend/chart_maps/gajjala/card_frames.py`,
`backend/supply_demand/rules_info.py`, `backend/scripts/gajjala_watch_levels_coverage.py` (new). Tests:
`test_gajjala_watch_levels_2026_11_23.py`, `test_gajjala_card_frames_overlays_2026_11_23.py`,
`test_gajjala_watch_overlays_rules_2026_11_23.py`; re-pinned `test_gajjala_card_frames_on_demand_2026_11_18.py`.

## HIS CALL

3. Zones per kind: the S&D tab's own 4 nearest (default) — or 1–2 for a cleaner chart.
4. Zones never move the price scale (default) — or let the nearest one pull it.
8. Look: the board-band dashed outline, no fill (default) — or filled.
10. Geometry: the BOARD's (default) — or the Support tab's finer one.
11. Names under 120 daily bars get none — lowering the floor is an engine change.
12. Sub-$1 cent rounding (wide / zero-width bands) — a finer grid is an engine change.
14. Zones on the card tiles as on the Watch (default) — or hidden there.
17. "across board" = the Watch + every chart the card frames feed; small 🚩 cards, 🥇 Luk, 🎬 Replays get none.
18. Prior-day high / low lines: not built.
19. A daily read that returns nothing is retried every read inside the 8-a-slot cap (default) — or once a session.
