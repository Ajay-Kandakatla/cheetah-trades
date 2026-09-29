# 🏎️ Dual Momentum: 🌀 / 📍 / 🔑 filter boxes and the 💰 market-cap order (2026-09-29)

Branch `feat/dm-tab-filters-2026-09-29`. Spec: the session scratchpad `dm_filters_spec.md`. Tab doc: `dual_momentum_tab_2026_09_29.md`.

## The asks, verbatim

> "Can you add AMD raided and near demand zone and near lower Key level filters to dual momentum please"
> "Also a sort by market cap please"
> — Ajay, 2026-09-29

Surface: https://pounce.ajaykandakatla.dev/chart-maps?tab=dual_momentum

## What each box reads (no new maths)

Each box is an existing read, run over the **whole 80-name pool** before the order and the cut. The param is `?dm=amd,zone,level`, and every ticked box must pass (AND).

| Box | Read | Pass | Fail | Not read |
|---|---|---|---|---|
| 🌀 AMD raided | `rotation.hottest_amd.attach` over the pool. This is the AMD Raided tab's own stored sweep, rename-aware and cached for 5 minutes. | grade `== TB.AMD_TURNING` | any other known grade | cell not known (`not_in_store`, `no_verdict`, `store_unavailable`) |
| 📍 Near demand zone | `dm_zone.gate.prox_ok`, which is the 🎯 read's own `alert_gates.demand_proximity_gate`. Its default bound is `ALERT_MAX_ABOVE_DEMAND_PCT`, read off the signature by `near_demand_pct()` and never retyped. | `prox_ok is True` | `prox_ok is False`, **or `dm_zone.reason == "no_band"`** (a stored doc with no demand band under the print, critic fix 3) | no stored doc (`no_doc`) or no print (`no_print`) |
| 🔑 Near a lower key level | The Key Levels tab's own `KLT.build` over the pool (memoised, see below), then `KLT.rank` per name. | status `ranked` and `abs(distance_pct) <= KEY_LEVEL_NEAR_PCT` | `broken` / `no_level`, or farther than the cut | `stale` / `no_print` / `unread` (build failed) |

- A ticked box **hides** a name it could not read and counts it as "not read". A missing read never counts as a pass.
- Counts are served per box over all 80 names, whether or not the box is ticked, so every box can show its number before he ticks it. `passed_all` counts the names that pass every ticked box.
- `filters.line` says what each ticked box hid. When nothing passes, the note is `filter_empty_note` ("untick one to see more").
- 🎯 Enterable only still applies on top of the survivors. The two lines are separate and each says what it hid.
- The filters sort, push, gate and enter nothing. The test `T15` greps that no module outside `chart_maps/` reads `dm_filter`.

## 💰 Market-cap order

- Two tab-scoped sort keys, `dual_momentum_tab.SORT_MARKET_CAP = "market_cap"` (largest first) and `SORT_MARKET_CAP_ASC = "market_cap_asc"` (smallest first). They sit in `TAB_SORTS` beside 📍 `nearest_demand`. They are honoured only on this tab. On any other tab, and for any unknown key, the sort falls back to the rank (`board()` coercion).
- The FE's 💰 button sits beside 🏎️ / 📍. The first click sends `market_cap`, and a second click sends `market_cap_asc` (`dmCapSortNext(served)`, keyed off the SERVED sort). The choice persists in `?sort=` through the page's one sort setter. Its labels are served (`MARKET_CAP_LABEL` / `MARKET_CAP_ASC_LABEL`).
- The order is applied to the **whole pool after the filters and before the cut**, in the same place as 📍. `market_cap_key` puts a name with no cached cap (None, NaN or not positive) **last in both directions**. Ties go to the page's rank, then the symbol.
- **The cap comes from ONE cached read, and only when the order is asked for.** `DMT.market_caps` → `catalysts.promo_circuit.market_caps_for(syms, {}, cap=0)` reads the weekly shares cache. That reader is also used by the demand / zone-edge cap gates and the 🪜 band note, and its stored `market_cap` is the field `trading.safety_floor` reads for the $700M floor. `cap=0` means the read never calls a provider. It fails open: every name gets None and the page keeps rank order.
- Served: `dual_momentum_board.cap_sort = {sort, largest_first, ordered, with_cap, no_cap, line}`. The line says how many leaders have no cached cap and sit last. While the order is on, each tile carries `dm_market_cap` and a `Cap` stat, and the header says "reordered 💰 by market cap".
- The order is display only. The 🎯 / 📍 / filter reads on each tile are identical under every order (test `C11`).

## Critic fixes

- **Fix 3 (📍 no band).** `tile_filter` maps `dm_zone.reason == "no_band"` to a plain `False`. Before the fix it was `None` ("not read"). The case is a leader with a stored doc and a real print but no demand band under it. That is a real read, and the read says it is not near demand. `no_doc` and `no_print` stay "not read". Today there are 0 such names in the pool, so the served counts do not change today.
- **Fix 2 (cost).** `DMT._kl_pool_entry` memoises the 🔑 pool build with key `(session ISO, scan_generation(), tuple(syms), universe)` and freshness `KLT.MEMO_TTL_SEC` (the Key Levels tab's own, cache freshness, not a rule). It holds one newest entry.
  - A raising build is never memoised.
  - The live-print `KLT.rank` still runs on every request.
  - Each tile's `level_near` is a deep copy: `near_block` embeds the entry's own `last_bar` dict, so an alias would let a tile write into the memo.
  - The per-box counts stay on every ready request because the boxes show them. They now reuse the memo, and the AMD read reuses `hottest_amd`'s own 5-min cache.

## Cost (measured 2026-09-29 ~15:05 ET)

Method: in-process and read-only in the prod api container. The branch `board.py` and `dual_momentum_tab.py` were loaded as modules from stdin, with no file copied into the container. The pool was seeded from the prod `/chart-maps?tab=dual_momentum&limit=80` payload, and the engine `compute()` was not re-run. Each figure is the median of 3 warm `dual_momentum_tiles(80, min_tier="any")` calls, including bars.

| Build | median s |
|---|---|
| origin/main (no filters) | 0.951 |
| branch, 🔑 build every request (before fix 2) | 1.237 |
| branch, 🔑 memo warm (after fix 2) | 0.921 |
| branch, memo warm, `dm=amd,zone,level` (1 survivor, so fewer bars) | 0.418 |
| branch, memo warm, `sort=market_cap` | 0.915 |
| `key_level_reads` alone: cold / memo hit | 0.332 / 0.004 |
| `market_caps` over 80 names | 0.003 |

## LIVE numbers (same run, 80-name pool)

- 🌀 AMD raided: 5 pass · 75 fail · 0 not read.
- 📍 Near demand zone: 12 pass · 67 fail · 1 not read.
- 🔑 Near a lower key level: 2 pass · 78 fail.
- Names failing 📍 because `no_band`: 0.
- 💰 names with no cached cap: **0 of 80**.
- Top 10, largest first (symbol, #rank): MU #8, AMD #27, INTC #36, DELL #19, SNDK #1, WDC #31, CRWD #67, STX #26, MRVL #37, ASX #29.
- Top 10, smallest first: CLYM #16 ($760M), NUAI #33, REPL #51, ETON #47, APPS #52, OMER #23, CDNA #15, BAND #25, ALNT #76, INBX #54.

## Honesty

- The AMD raid was MEASURED INVERTED (2026-09-14, `HA.AMD_MEASURED`), and the 🌀 note serves it.
- Key levels (`KL.MEASURED = False`), DM + demand (`DMT.MEASURED = False`) and the market-cap order are UNMEASURED.
- These are views, not signals, and no study is run or claimed here.

## Tests

- `backend/tests/test_dual_momentum_filters.py` (T1–T18, WP-BE).
- `backend/tests/test_dual_momentum_cap_sort_2026_09_29.py` covers:
  - fix 3: F3 pure + builder;
  - the memo: M1–M5 (hit, each key part + TTL, raising build, no alias, source);
  - 💰: C1–C12 (both directions, None last both ways, ties by rank, unknown key → rank, other tabs, pre-cut, filters first, served line, one read only when asked, failed read, pure key, reuse of `market_caps_for(cap=0)`, display only).
- `backend/tests/test_dual_momentum_tab.py`: the `_clean_memo` fixture also clears `_kl_memo`.
- FE:
  - `src/components/DualMomentumCapSort.test.tsx`
  - `src/pages/ChartMapsDualMomentumCapSort.test.tsx` (click → `sort=market_cap`, click again → `market_cap_asc`, both in the URL; deep link; unknown key; composes with `dm`)
  - `src/pages/ChartMapsDualMomentumFilters.live.test.tsx` (real builder payloads)
  - the WP-FE files
- Fixtures (real builder output, read-only run above): `__fixtures__/dual_momentum_filters_live_2026_09_29.json` (dm=zone, all 12 survivors) and `__fixtures__/dual_momentum_cap_sort_live_2026_09_29.json` (sort=market_cap, first 12).
- Contract: `frontend/scripts/contracts.mjs`, block "🏎️ Dual Momentum filters + 💰 order".

## HIS CALLS

1. `KEY_LEVEL_NEAR_PCT = 1.0` is a new number. Today on the 80, ≤1% → 2 names.
2. The filter scope is ranks 1–80, the tab's pool.
3. A name with no read is hidden when its box is ticked.
4. 🌀 uses the sweep's `raided` grade only.
5. 🎯 stays ON by default, so most ticked views end with "hidden by 🎯".
6. 📍 moves with the phone alert's 1%.
7. **💰 source.** The cap is the provider's market cap stored at the last weekly shares refresh (the `sepa.volume_movers` shares cache, 7-day TTL), not a live cap, so a fast mover's cap lags by up to a week. This is the same number the $700M safety floor reads. A live shares × print cap is one argument away (`market_caps_for` accepts a price map) if he wants it.
