# 🌀 Every AMD raid on the daily Support tile — past (closed bars) + today (provisional)

**2026-09-24 · display only · AMD is uncited and MEASURED INVERTED.** Nothing sorts, filters, gates, alerts, sizes or enters on anything described here.

## 0. The ask, verbatim (Ajay, 2026-09-24)

On ORCL the AMD chip read "AMD raided · today" on the 🏛️ POTUS tile and "AMD marked up · 14d ago" on the ticker page.

1. *"can you tell me if there is a possibility this stock is manipulated twice? I only see one Manipulation indicator wonder why"*
2. Asked how the chip should behave: **"Show all the possible raids, past ones too and todays too."**
3. Asked which base floor the 🌀 AMD tab (stored 141.02) and the chart (fresh 139.00) should use: **"Keep both as they are."**

The answer to (1) on ORCL: **three separate low raids in five weeks** — 2026-08-19 (base 138.72–159.26 from 08-06, marked up 09-08), 2026-09-01 (base 141.02–153.99 from 08-20, marked up 09-03) and 2026-09-24 (base 139.00–153.60 from 09-14, still open). None re-sweeps another. The old chip showed one because the detector returns only the latest cycle.

## 1. Root cause of the flipping chip (ORCL)

- The daily Support tile (`/chart-maps/support?symbol=X&studies=true`, used by `SupportLevels.tsx` on `/sepa/SYM`, `PotusBoard.tsx`, `HoldingsBoard.tsx` and the Chart Maps Support tab) grades AMD per request in `backend/chart_maps/board.py::_attach_studies` (~5906-5920) → `_attach_verdicts` → `turning_bullish.verdicts` → `supply_demand/amd.py::find_cycle`.
- That frame is `prices.load_prices` = the Mongo price_cache **including today's unfinished bar**, which `patch_latest_closes` (`sepa/prices.py:1049-1079`) rewrites about hourly.
- The raid test (`amd.py:244-247`) is *low through the base edge AND close back ≥ edge*; a close under the edge is an accepted break (`amd.py:261-262`) and the detector falls back to the older completed cycle.
- ORCL 09-24: low 133.48 under the 09-14 base floor 139.00, trading ~138.4–139.8 → the single chip flipped between "raided · today" and the older "marked up" cycle every hourly patch.

**Not changed** (his "Keep both as they are"): the verdict chip still grades the cached frame; the 🌀 AMD tab still reads its stored base. Grading the verdict chip on closed bars too is HIS CALL 1 below.

## 2. Definitions

- **Raid** — exactly `find_cycle`'s scan, now extracted into `amd._through` / `amd._back` / `amd._scan_raid` (behaviour-identical, pinned by an oracle test against a verbatim copy of the old code). There is ONE copy of the through/back test in the app (AST-guarded).
- **All raids** — `amd.find_raids(df, direction=...)` runs the same walk as `find_cycle` but keeps every raid-bearing base instead of the first; the first base met walking back pairs with a raid bar (the one `find_cycle` would pair).
- **Outcome** (existing definitions, no new threshold): `marked_up` (a close beyond the opposite edge within `MAX_MARKUP_BARS`), `failed` (a close back through the swept edge, no bar limit), `live` (neither yet, fewer than `MAX_MARKUP_BARS` bars since), `expired` (neither within `MAX_MARKUP_BARS` — the ask's "stale", renamed because `AMD_GRADES` already owns "stale").
- **Direction** — bullish raids the base low; the bearish mirror raids the base high. Both are listed and counted; only low raids are circled (`board.AMD_RAID_DRAW_DIRS = ("bullish",)`, HIS CALL 3).
- **Chains / re-sweeps** — a raid whose base span contains an earlier same-direction raid bar is a re-sweep of it (`resweep_of`, `chain_root`, `sweep_seq`). The chip counts chains; every row is still listed and numbered `k`, `k·2`, `k·3`.
- **Open base** — the freshest base neither raided nor broken whose raid window still reaches the next bar; used only for today's holding / unknown text.
- **Today (provisional)** — `amd.provisional_raid`: the same walk on closed bars + ONE synthetic today row (low/high = the tile's drawn live candle, close = `tile["live_price"]`, the now line), reading only the last index. So today's read is exactly what the closed list will say if the bar closes at that print. States reuse the 🌀 tab's words:
  - `reclaimed` — through the edge and back (a raid only if it closes there) → dashed numbered circle;
  - `sweeping` — beyond the edge now (a close there breaks the base, it is not a raid) → dashed `?` ring, not counted;
  - `holding` — the session low held the edge;
  - `unknown` — no regular-session low yet (pre-market day low is 0 / absent).
  It never reads the hourly-patched cache row and never changes the past raids.
  - **Two reads at once (repair, 2026-09-24):** when today's row reclaims an OLDER base while the same print closes beyond a FRESHER base's edge, the walk finds both — a raid on the older base AND the fresher base in `last_break_base`. The entry stays `reclaimed` and carries `also_sweeping` (the fresher base: `raid_level`, `base_lo`, `base_hi`, `base_bars`, `base_date`, `base_end_date`); the line appends `· price 138.40 is still under the fresher base low 139.00 (base 139.00–153.60 from 2026-09-14) — sweeping; a close under it breaks that base` and the chip reads `today low reclaimed · sweeping (not closed)`. "Fresher" = a later base end date (a frame with no dates carries none). No new comparison: both come from the one walk. ORCL at 138.40 with low 133.48 (real closed bars, `backend/tests/fixtures/amd_orcl_daily_2026_09_23.json`): reclaimed on base 137.43–151.63 from 2026-08-17 (would re-sweep the 2026-08-19 raid) + still under 139.00. Before the fix the break was dropped and the row read only "reclaimed" while price sat under the band on the chart. At 139.00 (inclusive) and above it is a plain reclaim of the 09-14 base.

## 3. Payload — `tile["amd_raids"]` (daily Support tile only)

`raids` (closed rows, oldest first: direction, date, bars_ago, raid_level, raid_price, raid_close, depth_pct, vol_ratio, base_lo, base_hi, base_bars, base_date, base_end_date, outcome, outcome_date, outcome_bars_after, markup_bars_left, resweep_of, chain_root, sweep_seq, in_view, closed, n, mark, text) · `today` (direction, state, closed:false, date, bars_ago, raid_level, base_*, price, day_low, day_high, raid_price, depth_pct, to_edge_pct, chain tags, price_source "now_line", reason, n, mark, text) · `draw_dirs` · `chains_in_view` / `rows_in_view` / `resweeps_in_view` (per direction) · `chains_off_view` · `n_all` · `chip {text, tone:"muted", title}` · `summary` · `basis` · `verdict_basis_note` · `note` · `through` · `frame_from` · `cited:false`.

Every sentence is written on the backend (`amd.raid_row_text`, `provisional_text`, `raids_chip`, `raids_summary`, `board._amd_raids_note`). The frontend composes only `#` + the served mark.

Frontend: `frontend/src/lib/amdRaids.ts` (sanitizer, circle placement, panel alignment), `frontend/src/components/AmdRaidsChip.tsx`, `PatternChart.tsx` (chip + circles), `chartOverlays.ts::filterTile` (`amd_raids` goes with the AMD box).

## 4. UX and placement (Rule #5)

- **One muted chip**, directly after the AMD verdict badge it expands (the two read together), before + Signals. Typically ≤ 25 characters ("7 low · 5 high raids"), ≤ ~56 with today's state. Muted always — the read is measured inverted.
- **The list lives in a drill-in** inside the tile: summary, basis, today's rows (dashed left border, `#mark` when numbered), closed rows newest first (`#mark`, `—` when un-numbered; off-chart rows dimmed; re-sweeps indented), the verdict-basis note, the measured note. It opens right-anchored, left-anchored or as a fixed sheet on a narrow phone (`panelAlign`). Escape or ✕ closes it; no click inside it navigates (the tile is a link).
- **Numbered circles** under the candles for LOW raids (the single M circle is replaced; A, D, ✗, the band and the raid line stay). Circles stack rows clear of the tile's own A / ✗ / ▲ / D / ▼ glyphs and are skipped (never clamped) when a row would leave the plot; a raid with no free row stays in the list only. High raids are listed, not drawn.
- **No new checkbox** — the AMD box governs the verdict, the drawn cycle, the chip, the list and the circles.

## 5. The closed-bar clock

Past raids read `demand_reentry.split_today_partial` (the app's one "closed bars" rule): today's row counts as closed from **16:00 ET**. The hourly `vcp-watch` patch (last at 16:00) and the **16:30 ET** `fast-scan --mode broad` rewrite mean that between 16:00 and 16:30 today's closed row is still priced off an hourly patch — a raid on today's bar can appear or drop once then; `basis` says so. There is no half-day calendar: on a 13:00 half-day today still reads "not closed" until 16:00. Keeping today provisional until 16:30 is HIS CALL 7.

## 6. Unchanged (pinned by tests)

`find_cycle` output; every amd constant (`MIN_BASE_BARS`, `MAX_BASE_BARS`, `MAX_BASE_ATR`, `MAX_BASE_PCT`, `MAX_RAID_AGE`, `MAX_MARKUP_BARS`, `LOOKBACK`, `VOL_REF_BARS`, `PHASES`, `CITED=False`); `find_base`; `chart_overlay`; `turning_bullish.py` entirely (`AMD_GRADES`, `MAX_RAID_BARS_AGO`, `WINDOW_SESSIONS`); `tile["verdict"]` and the AMD badge text; the 🌀 AMD tab (documents, grades, filters, `_amd_flight`, `AMD_FLIGHT_STATES`); `board()` grid tiles; crons, alerts, lanes, scans. No `rules_info.py` line (no new rule).

## 7. Descriptive census — DESCRIPTIVE, density only, NOT a measured claim

Read-only container probes, 2026-09-24 after 16:00 ET. **No outcome shares** are quoted anywhere: they would have no CI, no placebo, and chains inflate them.

| what | value |
|---|---|
| ORCL frame | 504 bars; the walk over BOTH directions 25 ms |
| 200 random names (seed 7): one walk, both directions | median 21.7 ms, p90 26, max 40 |
| raid rows, both directions, last 252 bars (1y) | median 26, p90 36, max 47 |
| 50 liquid names: raid rows per direction, 1y | median 11, p90 17, max 22 |
| same 50: CHAINS per direction, 1y | median 7, p90 10, max 12 |
| rows that re-sweep an earlier raid's base | 36.3% (750 / 2,067) |
| longest chain per name-direction | median 4, max 8 |
| next same-direction raid within 3 bars | 24.3% |
| ORCL low, 2y / 1y | 17 rows → 11 chains / 11 rows → 7 chains |
| ORCL high, 1y | 6 rows → 5 chains |

Reproduce (read-only, in the api container, after deploy):

```bash
docker exec -i -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -m scripts.amd_raids_census --sample 200 --seed 7'
```

## 8. The measured result (the only measured claim on any surface)

The AMD Raided read was measured against a like-for-like placebo on a markup-within-21-sessions bet and came back **INVERTED**: `rotation/hottest_amd.py::AMD_MEASURED["claim"]` = **51.9% vs 56.1%, −4.2pp [−6.92, −1.89]** (2026-09-14, 3,712 names / 1,592,057 bars; script `backend/scripts/turning_bullish_amd_study.py`; see `docs/supply_demand/turning_bullish.md`). A fresh raid reached the base top LESS often than a like-for-like bar inside its own base. **His own rule — enter at the raid low — has NOT been measured** (HIS CALL 8). The served `note` quotes the claim from the constant by import; it is never retyped on a surface.

## 9. HIS CALL

1. **RECOMMENDED — grade the tile's AMD verdict chip (and its drawn cycle) on closed bars too.** Stops the hourly flip and the two-chip contradiction. Changes a chip's meaning and one pin; the 🌀 tab is unaffected. Not built.
2. **The same chip on the Chart Maps grid tiles** (studies on): +~22–45 ms per tile and a pass after the live print in `board()`. Not built.
3. **Circle high (bearish) raids too.** Built OFF — listed and counted, not drawn.
4. **Which raids count as "all":** every raid of every base the walk meets (built, a superset), or only the raids the chip showed on their own day.
5. **Chains:** built = a raid whose base span holds an earlier same-direction raid bar is a re-sweep; the chip counts chains. Alternatives: count every raid bar; link only when the floor IS the earlier wick; list re-sweeps without circles.
6. **Today "sweeping" on the chart:** built = dashed unnumbered `?` ring, not counted. Alternatives: a numbered circle, or nothing.
7. **Keep today provisional until the 16:30 rewrite** instead of the app's 16:00 clock. Not built.
8. **Measure his own rule** (enter at the raid low) as a Rule #10 study. Unmeasured; offered, not started.
9. **Which of today's two reads leads** when the print reclaims an older base but is still under a fresher one (ORCL at 138.40): built = the one-walk raid leads (`reclaimed`, numbered, `would re-sweep`) and the fresher break is appended (`also_sweeping`). Alternative: lead with the freshest base (`sweeping`, `?` ring). Today's number and base still change when price crosses the fresher floor (139.00 on ORCL) — that is the one walk reading a different bar, not a flip of past raids.
10. **A live closed raid failing intraday:** when today trades back through a live closed raid's edge, no today entry names it and its row keeps "no markup yet — N of 25 bars left". Also intraday `bars_ago` counts today while `markup_bars_left` counts closed bars (17d ago · 9 of 25 left). Options: a today "failing" note from `_resolve` on the synthetic frame; shift `markup_bars_left` or say it counts closed bars. Not built (the spec keeps outcomes on closed bars).
11. **Numbers are per chart:** chains are numbered among in-view chains, so `#6` on 1y is a different number on 2y; the chip counts chains (ORCL 1y: 7 low chains, 11 low raid bars). Option: number over the whole closed frame so marks match across zooms. Not built.

## 10. Tests

Frontend (Vitest):
- `frontend/src/lib/amdRaids.test.ts` — sanitizer (null / array / string → null; NaN, negative, unknown direction / outcome / state, bad date dropped; no string coercion; bad mark → null; junk `draw_dirs` → `[]`; chip tone forced muted); circle selection (`in_view && mark` + today with mark, `draw_dirs` only, joined by date); stacking (adjacent rows, occupied A / ▲ push to row 1, out-of-plot rows skipped and flipped, omitted when nothing is free, never outside `[top, bottom]`, 50 rows); `panelAlign`; `raidRadius`.
- `frontend/src/components/AmdRaidsChip.test.tsx` — served chip text and title (led by the verdict-basis note); opens inside `MemoryRouter` + `Link` without navigating; today first, closed newest first, `#4` / `#1·2` / `#1` / `—`; Escape and ✕; narrow viewport → `--fixed`; no NaN / undefined / null / bounce.
- `frontend/src/components/PatternChart.amdRaids.test.tsx` — the fixture draws exactly 1·2, 1·3, 2, 3, 4 (no off-view 1, no H1); below the candle; live dashed; chip right after the AMD badge; amd_a → row 1; junk / absent payload → nothing.
- `frontend/src/lib/chartOverlays.amdRaids.test.ts` — `filterTile` gating with the AMD box.
- Contract: `frontend/scripts/contracts.mjs` — "🌀 AMD raids on the Support tile — closed bars + provisional today, display only (2026-09-24)".
- Fixture: `frontend/src/components/__fixtures__/amd_raids_orcl_2026_09_24.json` (HAND-BUILT, shaped like ORCL at 11:00 ET; bars synthetic around the raid dates).
- `frontend/src/components/PatternChart.amdRaidsLive.test.tsx` — LIVE captures `__fixtures__/amd_raids_live_orcl_2026_09_24_closed.json` (17:09 ET) and `..._intraday.json` (route clock pinned to 13:00 ET, print 139.34): no `[object Object]` / NaN / undefined / Infinity / bounce; 09-01 is `#6`, marked up 2026-09-03; no `H` marks drawn; intraday today `#7` dashed and not closed; NEGATIVE closed: no dashed circle.

Backend (pytest): `backend/tests/test_amd_all_raids_2026_09_24.py` — constants source guard, `find_cycle` oracle, `find_raids` rows / outcomes / chains / bearish mirror, `provisional_raid` states and `_amd_flight` parity, the one-walk property, `_attach_studies(..., raids=True)` wiring, wording (no "bounce", the note quotes `AMD_MEASURED["claim"]`), the route guard, the one-raid-test AST guard, nothing-gates guard. Repair round: ORCL real-bars fixture (`also_sweeping` at 138.40 / 138.99; NEGATIVE plain reclaim at 139.00 inclusive, 139.715, 139.80; sweeping under every floor; bearish mirror; junk `also_sweeping`), and the `open_base` raid-window boundary on both sides (a `+1` mutation used to pass the whole suite).
