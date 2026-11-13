# 📅 Long Term — the data layer (sources, facts, baseline) — 2026-11-12

Ajay 2026-11-12 ~21:00 ET: *"Save this entire list for me. In a New tab - Long Term - Remember this analays criteria I am asking you to for this tab and keep updating it from all the other tabs info.. Weekly and if something gets dropped let me know when to like is Sales drop or Stage 2 to Stage 3 or stage 4 changes."*
Then ~21:20 ET: *"Yeah I wanna find out the ones that are actually great in fundamentals and growth and sales and no debt but not growing in price action yet.."*

Files (WP-DATA of the planner spec, revision 2):
`backend/long_term_list/sources.py` (IO, fenced) · `backend/long_term_list/facts.py` (pure mapping) ·
`backend/long_term_list/data/baseline_2026_11_12.json` (generated once) ·
`backend/scripts/long_term_list_baseline_2026_11_12.py` · `backend/chart_maps/board.py` (`fallen_pool` extract).

UNMEASURED. Nothing here ranks, gates or rings anything by itself; it only reads what the other tabs already serve.

## 1. Sources — one in-process read per source tab, cache only

| key | engine (the source tab's own) | as-of served | feeds |
|---|---|---|---|
| `scan` | `scanner.load_latest()` → `all_results` + `candidates` (`is_candidate`) | ET time of the scan's `generated_at` (the 16:30 `fast-scan --mode broad`) | 🚀 💎 📈, 🏷️ floor + sector, display name/sector |
| `undervalue` | `undervalue_peers._load_inputs()` → `build(**inputs)` → `passed` (ratio asc); floor `board.passes_liquidity(board.tile_metrics(scan_row)["avg_turnover"], "ok")`; `build_failure` → not read | ET date of the scan | 🏷️ |
| `fallen` | `fallen_tab.cached_or_warm("full", now, sync=True)` → `board.fallen_pool(entry, sort=DEFAULT_SORT, depth=40, min_tier="ok")[0][:LIMIT_MAX]`; the same floor at depth 0 for a saved name above the line | the memo's `as_of`; its session rolls at **20:00 ET** (`fallen_tab.session_for`) | 📉 |
| `hottest` | `rotation.api._members_table()` + `_members_payload()` → `hottest._build(..., names_per_group=len(syms), live=None, pre=_idle_pre())`; served = first `NAMES_PER_GROUP` (25) per sector | Hottest `as_of` | 🔥 |
| `longterm` | `longterm.stored()` rows + `longterm._sector_map()` (🔄 sector fallback, display) | `built_at_iso` (Sunday warm) | 🌱, 🔄 net profit (info) |
| `research` | `research.decision_snapshot(saved)` (sales + `q_end_series` + `cached_at`) ∪ `research.sales_snapshot(universe "full")` | per name: `cached_at` (TTL 16 d) | every sales tier, 🌱 tier leg, 🔄, sales text |
| `frames` | `prices.bulk_cached_frames(saved ∪ 🌱/🔄 pre-candidates ∪ {RSP, SPY})` — ONE find | RSP's last closed bar | stage, close, 52-week distance, 50-day $ volume, 🧭 close |
| `caps` | `promo_circuit.market_caps_for(🔄 pre ∪ saved, closes, cap=0)` | — | 🔄 cap band |
| `growth_board` | `growth.api._board_payload()["rows"]` → `capital_quality.grade` | — | 💎 grade (info only) |

Each read is fenced: an exception, an empty doc or a not-ready memo returns `{"ok": False, "reason": …, "as_of": None, "n": 0}`. A category whose source is not ok is `ok: False` with the reason and **no population** — never an empty pass; its saved names still get a lookup whose missing values are `None`, which `criteria` reads as "unknown" (never a pass, never a fail).

Category → required sources (`facts.CATEGORY_SOURCES`): 🚀💎📈 scan · 🏷️ undervalue + scan · 📉 fallen · 🔥 hottest · 🌱 longterm + frames + research · 🔄 research + frames + caps · 🧭 frames.

Pre-candidates (cheap pre-filters on constants by name; `criteria` decides every leg): 🌱 = long-term rows `score.ranked` and `score ≥ QUIET_MIN_SCORE`; 🔄 = research tier in `ACCEL_SALES_TIERS`, accelerating, prior y/y > `ACCEL_MIN_PRIOR_YOY_PCT`.

### Bar reads (closed bars only)
`sources.closed_frame` applies the `scanner.as_of_close` rule: a last bar dated today before `SEPA_RERATE_ET` (16:30) while the session is not closed is the hourly in-progress patch and is dropped. Then `stage.classify(df, vol=volume.analyze(df))` (< 220 bars → `None`), `trend_template.evaluate` → `pct_below_high` / `pct_above_low`, `adr.liquidity_check` → `avg_dollar_vol` (< 50 bars → `None`, never adr's 0).

### Stage on the scan lists
🚀's stage leg reads the name's closed-bar stage when the name was bar-read (every saved name), else the scan row's own stage (population names) — equal after the 16:30 re-rate.

## 2. The 📉 pool extract
`board.fallen_pool(entry, *, sort, depth, min_tier) -> (kept, counts, dropped_thin, no_turnover)` is the selection `fallen_tiles` ran inline (rank at depth, then the liquidity floor on a copy of the metrics, `adv50` standing in for a missing scan row). `fallen_tiles` now calls it; it still calls `fallen_tab.rank` once more for the rows of the 📋 pick-coverage line (the spec's 4-tuple has no `rows`; rank is deterministic). `tests/test_board_fallen_pool.py` pins the whole `fallen_tiles` payload byte-identical against the verbatim pre-extract loop.

### A saved 📉 name back above the line (refix 2026-11-12)
`fallen_tab` stores only rows whose status is `fallen` (`THRESHOLD_PCT` = 40% or more under the 52-week high), so a saved 📉 name that climbs back has no row in `entry['rows']`. Without a fill every 📉 leg read "unknown" and the week said "not read" instead of the neutral `moved` line. `sources.fill_fallen_from_bars` (called in `load_all` after `frames`) gives such a name a row from its own closed-bar read: `pct_below` / `pct_above_low` = `bar_read`'s `trend_template` distances (52 weeks of closes; `fallen_tab` measures from the year's high/low levels, so the bar read can only sit at or nearer the high), sales = the research cache's sales block through `FAL.sales_block`, `in_served_pool` False (never a top-strip candidate), `floor_ok` None (the floor leg reads "unknown", never a fail by absence). A real 📉 row is never overwritten; a name with no 52-week distance (short or missing frame) stays "not read", never a zero; a 📉 source that is not ok comes back unchanged. The filled names are listed in the source's `filled_from_frames`. Tests: `tests/test_long_term_list_sources.py` `test_fallen_fill_*`, `test_NEG_fallen_fill_*`, `test_load_all_fills_a_recovered_saved_fallen_name_from_its_frame`.

## 3. Facts (`facts.build(sources, saved, seed)`)
Shape per spec §3.4. The `values_*` mappers are the one place a source row becomes a category's values (keys = `criteria.py`'s docstring). Display sector: scan → long-term row → companies map. `sales_q_end` = `decision_snapshot[SYM]["q_end_series"][0]` (None when absent — never invented); `sales_read_on` = the ET date of `cached_at`. 🏷️ off-list saved names read their own snapshot through the vs-peers helpers (`ttm_revenue`, `q_yoy_pct`, `ttm_growth_pct`); a yfinance-sourced snapshot (currency unverified — the vs-peers funnel does not read it) leaves those `None`.

## 4. The baseline (`data/baseline_2026_11_12.json`)
Built once from the 11-12 scratch dumps by the script (pure JSON, host python, no Mongo, no network; `allow_nan=False`). Every dump row goes through `facts`' own mappers, the legs through `criteria.legs`, the 🧭 read through `criteria.zone_read` (→ `pankaj_picks.setup_status`), the flags through `notices.initial_flags(notices.at_save(...))`. Keys: `saved_on, built_from {arg: {file, sha256}}, names {SYM: {stage, stage_label, stage_bar_date, close_at_save, sales_tier, sales_yoy_pct, sales_q_end, sales_read_on, sector, name}}, categories {cat: {SYM: {values, legs}}}` (each name under the lists it carries), `pankaj {SYM: {zone_read}}, flags {SYM}`.

Provenance (the dumps the main session wrote on 11-12): scan `sepa1112/full.json` (16:31 ET fast scan) · bars `sc1112/sweep.json` (stage.classify on cached closed bars; 52-week close high/low; 50-bar $ volume at $0.1M) · sales `sc1112/snap.json` + quarter end / read date from `longterm/dec1112.json` (see the C11 refix below) · long-term `sc1112/lt_rows.json` · Hottest `hot1112/h.json` · 📉 `val1112/fallen2.json` (80 served tiles) · 🏷️ `val1112/uvp.json` (24 of 37 served tiles; ratio recomputed as Mkt cap ÷ TTM rev ÷ Peer P/S from the printed stats — the whole-% "below" text ties AVT/ARW; the order holds through the first 20 tiles, AIR/HHH swap on the rounded peer P/S) · caps `sc1112/acc_caps.json` (`cap=0`) · 🔄 sector fallback `sc1112/acc_rows.json` `sec`. The 💎 growth-board grade is not in the dumps (info only; `growth_board` reads not-ok in the baseline build).

Spot facts at save: AMD Stage 2 strong · ANET 3 · NVDA 1 · XPEL 1 (no scan row) · SATL 1 · BRK-B 2 · stages over the 109: 1 = 53, 2 = 32, 3 = 17, 4 = 7. 🧭 at the 11-12 close: TSM in Agg (405.49), META in C1 (623.61), NVDA in C2 (166.19); INTU 23.7% over its Agg top. `flags.last_stage2_on = "2026-11-12"` for exactly the 32 Stage 2 names.

### 2026-11-12 23:40 ET — C11 refix: quarter end + read date in the baseline
The first baseline carried no quarter end and no read date (`snap.json` has neither), so until the first Friday 16:30 run every `seed_only` row read e.g. "Sales +56.5% y/y · tier strong" with no dates. Fix: one read-only `research.decision_snapshot(the 109 saved)` in the api container (one projected find, outside RTH) → `longterm/dec1112.json` `{read_at, n_asked, rows: {SYM: {sales, q_end_series, cached_at}}}`, passed to the script as `--dec`. A name's `q_end_series` / `cached_at` ride along only when its decision_snapshot `sales` block equals the `snap.json` block (same read) — all 109 matched. Result: `names[SYM].sales_q_end` on 107 names (BRK-B and TSM have no `q_end_series` in the cache → `None`, dropped from the text, never invented), `sales_read_on = 2026-11-08` on all 109 (the cache's `cached_at`, ET date). Nothing else in the file moved (categories, legs, flags, 🧭 reads, every other name key identical; `built_from` gains `dec`). `seed_only` AMD now reads "Sales +44.7% y/y · tier strong · quarter ended 2026-09-26 · read 2026-11-08". Pinned in `tests/test_long_term_list_baseline.py` (`test_c11_*`, incl. the NEG: a different sales block → no dates; no `--dec` → `None`).

### `--check` — the seed reproduced from the dumps (generated 2026-11-12)

| category | qualify | verdict | pick_top (capped) |
|---|---|---|---|
| s2_growth | 22 | EXACT | AMC APPN FIGS MGNI AMD PRCH GCT PGNY VCEL IDT |
| capital_quality | 52 | EXACT | SLDE ANET MANH EXEL HNGE PAYC CBOE MA ABNB CDNA |
| undervalue | 24 | differs only by the sector cap | AVT ARW SMCI WKC BTSG CSTM CRBG CTRI STC KALU |
| ↳ seed | | | AVT ARW SMCI WKC RUN DELL BTSG CSTM CRBG CTRI |
| ↳ uncapped | | | AVT ARW SMCI WKC RUN DELL BTSG CSTM CRBG CTRI |
| bonde | 58 | EXACT | XNCR KDP WAT VIR JXN SKWD ANET NIC LNG WELL |
| fallen_growers | 56 | EXACT | NRIX ASTS PGEN ONDS SNDK EOSE LUNR SATL URGN AUR |
| hot | 34 | EXACT | LQDA XNCR APP KRMN BKSY LBTYA CLX FIGS HHH FROG |
| quiet_strong | 20 | EXACT | HLNE NVDA META GOOGL NXT MPWR XPEL EPRT MGY CTRE |
| accel_after_fall | 46 | EXACT | UMAC SATL AXTI LUNR VOYG AUR KLIC RUM HIMS SBET |
| pankaj | — | n/a (his sheet's first 40 rows, not a screen) | — |

The 🏷️ seed holds five Technology names (AVT ARW SMCI RUN DELL); the tab's sector cap (3) would hold AVT ARW SMCI and reach STC KALU instead. Reported, not "fixed" — the saved list stays his 10; whether the 🏷️ strip is capped is in the spec's his-call list.

Re-run: `.venv/bin/python scripts/long_term_list_baseline_2026_11_12.py --seed … --scan … --sweep … --snap … --lt … --hot … --fallen … --uvp … --acc … --caps … [--dec …] [--check]` (full argument list in the script's docstring).

## 5. Cache-only proof
- `sources.py` never calls `load_prices`, `build_live`, `_shares_outstanding`, `requests`/`httpx`/`urlopen`; `market_caps_for` is called with `cap=0` (its provider loop is `missing[:0]`). Pinned by source-grep and monkeypatch tests.
- `tests/test_long_term_list_sources.py::test_NEG_every_source_failing_never_raises_and_never_reaches_the_network` runs `load_all` with Mongo refused (conftest) and `socket.socket` / `create_connection` raising: every source reads `ok: False` with a reason, nothing raises, no socket opens.

## 6. The 🧭 request-time read
`sources.pankaj_closes(symbols, now)` — the ONE read on the owner's GET: `bulk_cached_frames` (one find, never a fetch) → `closed_frame` (a today bar before 16:30 ET dropped) → `{SYM: {close, date}}`. A symbol the cache does not hold is absent (never a zero); a cache failure returns `{}`. The weekly run reads the same closes through `frames`; the zone read itself is `criteria.zone_read`.

## 7. Not done here
No run, no Mongo write, no push, no endpoint (WP-RUN). The forward record's universe pool frames (placebo) are not part of `load_all` — the forward step reads them. The `growth_board` 💎 grade is absent from the baseline (not in the dumps).
