# 🏎️ Dual Momentum tab on Chart Maps (2026-09-29)

## The asks, verbatim

Ajay 2026-09-29:
> "Can you pull these in to chart maps and add the demand zones logic to these? https://pounce.ajaykandakatla.dev/dual-momentum"

Same minute:
> "I want a toggle and also the check boxes we have like AMD and supple and demand zones computing and also key levels"

**UNMEASURED.** No study in this app says a dual-momentum leader sitting near a demand band does better than one that is not. The tab is display only: nothing on it gates a scan, pushes a phone, sizes a position or enters a lane.

## What the tab is

- **Population:** exactly the Dual Momentum page's engine, `sepa.dual_momentum.compute(top_n=LIMIT_MAX)`, with the engine's own defaults (252-day gate, min RS 0). Those are the page's defaults. The rank does not depend on `top_n`, so ranks 1–15 on the tab are the page's ranks 1–15. The page's `rank` is printed on every tile (`🏎️ #N dual momentum`). The engine is unchanged; the SPY-12m hurdle (the T-bill drift) is still his pending call.
- **The regime** (RISK-ON / DEFENSIVE, engine label verbatim, plus `SPY 12m ±x.xx%`, or `SPY 12m —` when the engine has no SPY read) prints on top. It never hides a pick, matching the page.
- **Each tile** is the standard Chart Maps card plus the demand engine:
  - the nearest demand band at or below the print (`bounce_room.demand_read` over the stored board-geometry docs, `zone_store`);
  - the first lid from `room_floor.room_block`;
  - the `Room` stat (`room_floor.room_stat`, the demand boards' wording);
  - the floor state, passed through raw (intact / swept / broken / unknown, never collapsed);
  - the 🎯 gate read (`enterable`, kind `demand`: `alert_gates.room_gate` + `demand_proximity_gate` + the floor read, **reused, never re-implemented or loosened**).
  - The distance to the band prints once, on the PRICE-rung badge. There is no `To band` stat.
  - A leader with no band reads `→ no demand band under the price` (or `no stored bands`, or `no print`). A fake band is never drawn.
- **Stats:** `12m 6m 3m 1m RS` (the page's numbers), then `Room` and `Band`.

## Design

| Piece | Where |
|---|---|
| Memo, pure reads, words | `backend/chart_maps/dual_momentum_tab.py` |
| Builder `dual_momentum_tiles` | `backend/chart_maps/board.py`, next to `key_level_tiles` |
| `TABS` (after `key_levels`), sort coercion, dispatch, sort labels | `board.py` `board()` |
| `attach_enterable(…, docs=None)` | `board.py`; `docs` given → no store read |
| `KIND_BY_TAB["dual_momentum"] = KIND_DEMAND` | `backend/supply_demand/enterable.py` + the parity fixture |
| `tab` Query description | `backend/chart_maps/api.py` |

- **The memo.** `compute()` costs about 4–6 s. The result is memoised per `(scan generation = latest.json mtime, ET date, pool_n)` and built in a daemon thread (the key_levels_tab pattern).
  - It serves stale-while-revalidate: a held entry is served while ONE rebuild runs. A late build for an older generation never overwrites a newer one.
  - A failed or empty engine answer is never memoised. With no scan on disk the state is `no_scan` and the engine is never called.
  - `MEMO_TTL_SEC` (30 min) is cache freshness only, not a rule. The builder deep-copies the memo entry, so no request can mutate it.
- **ONE snapshot, ONE store read.** One `_bulk_snaps` for the pool is shared with `board()` through `ctx`. One `zone_store.load_latest` feeds BOTH the zone read and the 🎯 read (`attach_enterable(docs=…)`, pre-cut), so the two can never read different store generations. `board()`'s later 🎯 attach is a no-op by key presence.
- **The toggle = two served sort keys.**
  - `default`, relabelled "🏎️ Dual-momentum rank".
  - `nearest_demand`, "📍 Nearest demand first", offered **only on this tab**. Anywhere else it coerces to the default like any stale bookmark.
  - 📍 orders floor intact → unknown → swept → broken → no band. Within a group it is closest first, then the page's rank, then the symbol. Both orders are applied **pre-cut** over the ≤80 pool, so the toggle decides which tiles reach the page.
  - If no leader has a band, the board keeps the rank order and says so (`sort_unavailable`).
  - Neither key is an explicit `_finish` sort, so the theme lead still applies when its box is ticked. Every generic `SORTS` key behaves as on every tab.
- **Header counts:** pool, with_band (held / swept / broken / unknown, bucketed by the same rank the 📍 order uses; they sum to with_band), no_band, no_doc, no_print, dropped_thin, shown.

## Gating map: every checkbox on this tab

| Control | dual_momentum | How |
|---|---|---|
| Sort select | yes; `default` relabelled, `nearest_demand` right after it | served `sorts` |
| 🏎️ / 📍 toggle | yes; pressed = served `sort` | FE (WP-FE) |
| Liquidity, Window, ⊞ Expand all, ↻ | yes | generic |
| Themes first | yes (`_finish`) | generic |
| ⚡ Momentum burst | yes (board tab) | `attach_burst` |
| 🎯 Enterable only + reason chips | yes, kind `demand`, **ON by default as on every demand board** | `KIND_BY_TAB` / `ENTERABLE_KIND` |
| 🪜 sort + banner | yes (kind demand) | `band_structure.kind_for_tab` |
| 🧨 chip / sort | yes | `_finish` → `attach_explosive` |
| Support/demand, Overhead/supply overlays | yes | the builder draws the demand band + first lid |
| 🔑 Key levels overlay | yes | `attach_key_levels` (every tab ≠ ict) |
| AMD phases / Fibonacci / Mean rev / Keltner overlays (+ per-tile AMD verdict chip) | yes | `studies=true` → `_attach_studies` |
| 9 EMA / 20 SMA / 200 SMA / Now | yes | generic |
| 🧲 GEX chips | yes | the builder calls `_gex_decor(out, "demand")` |
| Server room floor (`ROOM_TABS`) | **no**; HIS CALL #2 | — |
| 🌀 AMD grade / 🔻 in-flight tab buttons | **no**; HIS CALL #4 (they pick a slice of the AMD sweep; the read MEASURED INVERTED) | — |
| 🌀 AMD raided filter (2026-09-29) | yes | `hottest_amd.attach` → grade `== TB.AMD_TURNING` (`dual_momentum_filters_2026_09_29.md`) |
| 📍 near demand filter (2026-09-29) | yes | `dm_zone.gate.prox_ok` (`demand_proximity_gate`'s own default = `ALERT_MAX_ABOVE_DEMAND_PCT`); no band under the print = fail |
| 🔑 near lower key level filter (2026-09-29) | yes | `KLT.build` (memoised) / `KLT.rank`, `KEY_LEVEL_NEAR_PCT` HIS CALL |
| 💰 market-cap order (2026-09-29) | yes; `market_cap` / `market_cap_asc`, tab-scoped like 📍 | `promo_circuit.market_caps_for(…, cap=0)` → `market_cap_key`, pre-cut |
| BUY / STOP / TARGET plan lines | **no**; HIS CALL #4 | — |

## Payload (`GET /chart-maps?tab=dual_momentum&limit=80[&sort=nearest_demand]`)

- **Top level:** the generic board keys (`tab count tiles sort sorts min_tier tiers tape_sorts studies disclaimer explosive_study enterable_kind="demand" enterable_study band_structure_kind="demand" band_structure_study band_structure_coverage burst_* key_levels_rule dropped_thin sort_unavailable`), plus `matched scanned generated_at scan_generated_at gex_as_of note dual_momentum_board`.
- **`dual_momentum_board`:** `{state: ready|warming|no_scan|error, regime, regime_line, gate_lookback_days, pool, eligible, universe, counts, sort, header, note, built_at, scan_generated_at, page_route: "/dual-momentum", measured: false}`.
- **Tile:** the standard `CmTile` plus:
  - `dual_momentum{rank, score, return_1m/3m/6m/12m, return_gate, abs_mom_pass, beats_spy, rs_rank, stage, is_sepa_candidate}`;
  - `dm_zone{reason: ok|no_band|no_doc|no_print, demand, room, room_stat, floor, floor_state, floor_held, gate{verdict, room_ok, prox_ok}, print{px, source}, text}`;
  - `enterable`, `band_structure`, `burst`, `key_levels`, `explosive`.
  - `badges[0]` is the rank chip.

**Failed builds (fix round, 2026-09-29).** A build that raises is no longer served as
`warming` forever with a fresh full `compute()` on every 10-s poll. The newest failure is
remembered per memo key: an engine `error: "no_scan"` answer (a scan file with no rows) is
served as `state: "no_scan"`; any other failure as `state: "error"` with the reason in the
served header (`error_block`), no `warming` flag, so the page stops polling. A failed key is
retried at most once per `FAIL_RETRY_SEC` (5 min, retry cadence, NOT a rule); a held entry
keeps being served meanwhile; a new scan generation or ET date is tried at once. Tests:
`test_03_NEG_a_raising_build_leaves_the_memo_empty_and_retries`,
`test_03_NEG_a_build_that_raises_three_times_runs_the_engine_once`,
`test_03_NEG_an_engine_no_scan_answer_is_served_as_no_scan_not_warming`,
`test_11_NEG_a_failed_build_payload_is_error_and_never_polls` and siblings.

## HIS CALLS (defaults shipped; each is reversible in one line)

1. **Tab slot:** right after 🔑 Key Levels.
2. **🎯 on this tab (BLOCKING before promote).** The shipped default is kind `demand` with 🎯 Enterable only ON, exactly as on every demand board. The critic's pre-build probe: 77 of 80 leaders BLOCKED, 2 READY, 1 with no stored bands, so the default view shows 2 of 80 and none of the page's top 15. Untick 🎯 to see every leader. The options are (b) open this tab with the filter OFF, (c) chip-only, (d) kind `n/a`. The server room floor is not added.
3. **Pool and liquidity:** ranks 1–80. The house liquidity floor applies and its count is printed.
4. **Not carried:** the AMD grade/flight tab buttons and the plan lines. The AMD phases overlay checkbox DOES work here. **Amended 2026-09-29:** a 🌀 raided FILTER is carried since 2026-09-29 at his ask ("Can you add AMD raided and near demand zone and near lower Key level filters to dual momentum please"); the grade/flight buttons still are not. See `dual_momentum_filters_2026_09_29.md`.
5. Beyond the curated data heal: WP-DATA, see `docs/sepa/dual_momentum_data_audit_2026_09_29.md`.
6. The BNY/GOLD refetch: WP-DATA.
7. **Declutter:** both the toggle and the Sort select show the one served sort.

## Tests

`backend/tests/test_dual_momentum_tab.py` (38 tests) covers:
- TABS order;
- `build` (one engine call, `top_n` only; an error or empty answer is never memoised);
- the memo (cold / fresh / new generation / TTL / late build / raising build / no scan);
- rank fidelity;
- one engine and ONE store read (including the race NEG);
- the gate never loosened (a `room_gate` spy sees `ALERT_MIN_ROOM_PCT`; room 4.99% gives BLOCKED; proximity is True at 1.00% and False at 1.01%; source guard);
- no fake band;
- floor words and the 📍 order (broken never becomes swept);
- the tab-scoped sort;
- the wiring of every checkbox; one snapshot; the regime never hides a pick (SPY missing);
- JSON / wording hygiene;
- the parity fixture;
- the memo never mutated.

Mutation-checked, each goes red:
- drop the `KIND_BY_TAB` entry;
- make `nearest_demand_key` ignore the floor;
- map broken → swept;
- skip the `deepcopy`;
- drop `docs=docs`;
- pass `min_room_pct=4.0` into the gate.

Pins updated deliberately: `test_key_levels_tab.py` (TABS tail) and the fixture's `kind_by_tab`.

## §FE

_Placeholder: the main session fills this from WP-FE's report._

## LIVE verification (2026-09-29, ~11:00–11:15 ET, branch API on a scratch DB)

Throwaway plain `docker run` of the worktree backend (`:ro`), `MASSIVE_WS_ENABLED=false`,
`FINNHUB_POLLER_ENABLED=false`, `MONGO_DB=cheetah_dm_scratch` (seeded by a read-only `mongodump`
of prod, the five largest tick/history collections excluded), prod scan volume `:ro`. Torn down and
the scratch DB dropped afterwards.

- **His page's query** (`/sepa/dual-momentum?top_n=15&lookback_days=252&min_rs_rank=0`), prod vs
  branch: same regime (RISK-ON, SPY 12m +16.35%), same 1,827-name universe. WOLF (#1), BNY (#2)
  and SPCX (#9) leave the picks (their 12m reads blank after the WP-DATA cut); everyone else moves
  up in the same relative order, and LITE, ERAS and CDNA enter at #13–#15.
- **The tab**: first call warming (0.3 s), ready on the next poll; a repeat call on the memo
  takes about 1.3 s. The first 15 tiles are his page's 15 picks in the same rank; ranks 1–80 in
  order. `sort=nearest_demand` is served and the order obeys `nearest_demand_key` over all 80.
  Another tab asked for `nearest_demand` is served `default`.
- **Zone engine hand-check**: for every tile with a stored doc (79 of 80) the tile's demand band =
  `bounce_room.demand_read`, `enterable.band` = the same band, `room_ok` = `alert_gates.room_gate`
  and `prox_ok` = `alert_gates.demand_proximity_gate`, recomputed in the prod (main) container:
  **0 mismatches**. SNDK, CLYM and ERAS were also checked by eye against the stored bands.
- **🎯 re-count (HIS CALL #2), post-WP-DATA pool**: 78 BLOCKED, 2 READY (CLYM #17, SYRE #18);
  15 of 15 of his page's top 15 are BLOCKED. First block reason: not at band 67, floor swept 5,
  room < 5% 3, floor broken 2, no band 1.
- **Refetch demo, scratch DB only**: `load_prices("BNY", force=True)` → 501 bars, 12m +34.46%, largest
  daily move ±8%, no fund bars. `load_prices("GOLD", force=True)` → the AMRK boundary is continuous
  (29.25 → 29.78), 12m +61.39%.
- **Bug found and fixed here**: the tile skeleton spread `tile_metrics`' own `explosive: None` and
  `band_structure: None` onto every tile. Both attachers skip a tile by KEY PRESENCE, so 80 of 80
  leaders came back with no 🪜 read and no 🧨 read, `band_structure_coverage` said "no band read for
  these names", and the 🪜 / 🧨 sorts were inert. The fix keeps those two keys in `_m` only
  (`board._DM_ATTACH_OWNED`). After it: 79 of 80 tiles carry both reads, and the 🪜 and 🧨 sorts
  reorder the board. Test 16 pins it; putting the spread back turns both test-16 cases red.
- **Real payload fixture**: `frontend/src/components/__fixtures__/dual_momentum_tab_live_2026_09_29.json`
  (12 tiles: ranks 1–9, CLYM, SYRE, NUAI with no stored bands). `DualMomentumTab.payload.test.tsx`
  runs on both fixtures. `ChartMapsDualMomentum.live.test.tsx` renders it through the real page and
  checks: every leader in rank order; regime, header and UNMEASURED; the rank chip, zone line and
  gate chip on each card; no NaN/undefined; never "bounce"; with 🎯 on, only CLYM and SYRE show.
