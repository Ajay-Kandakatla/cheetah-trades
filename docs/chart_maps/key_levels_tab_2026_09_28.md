# 🔑 Key Levels tab on Chart Maps (2026-09-28)

**UNMEASURED.** An order by distance, not a signal. No study in this app says a stock near its prior-week low,
prior-month low or 52-week low holds or reverses there (`key_levels.MEASURED = False`; the pre-registered break study is
§6 of `key_levels_2026_09_25.md`, not built). Nothing here gates a scan, pushes a phone, sizes a position or enters a
lane.

## The ask, verbatim

Ajay 2026-09-28:

> "Also create me tab for keylevel main. Sort them by stocks that are near lower keylevels"

Read as: a MAIN tab of its own (`/chart-maps?tab=key_levels`), rows = names whose print sits above — or inside the
`PIERCE_PCT` break buffer of — a LOWER key level not yet broken, closest first.

## What ranks, and how

| piece | where | rule |
|---|---|---|
| levels | `key_levels.closed_levels` (the frozen half of `tile_block`) | PWL / PML / 52wL = `BOARD_PERIODS` (pinned `== FRAME_PERIODS["daily"]`) × `BOARD_KINDS = ("low",)`, from CLOSED bars (`closed_frame`) |
| "lower" | `key_levels.nearest_lower` | kind `low` on the SUPPORT side (sided by the last closed close — the house rule). A low above the last close is not a lower level |
| through | `key_levels.is_through` | state `broken` / `closed_beyond`, `ah_through`, or the anchor itself `PIERCE_PCT` beyond (rth day-close `pierced`) |
| anchor | `key_levels.anchor_read` | fresh print (< `STALE_PRINT_SEC`, dated the session) → `live`; else the day close in rth/close → `day_close`; else the last close → `last_close` |
| distance | `key_levels.near_block` | `distance_pct = −dist_pct` = `(print − level) / print × 100`, 2 dp; negative = inside the break buffer; `−0.0` → `0.0` |
| order | `key_levels_tab.rank_key` | `abs(distance_pct)` asc → longer period (`PERIOD_RANK`) → symbol. No "near" cutoff |
| per name | `key_levels_tab.rank` | ranks on the nearest low it is NOT through; lows already through ride along in `through` |

Rank steps, first match wins, in EVERY phase (off-hours included):

1. no levels entry / stale by date / no ref close → `stale`
2. no snapshot row → `no_print`
3. `verify_last` sentence (the cached bar is not the final close) → `stale`; row with nothing to check against → `no_print`
4. no anchor → `no_print`
5. `nearest_lower`: every lower low through → `broken`; none below the price → `no_level`; else ranked.

**Invariant:** `scanned == ranked + broken + no_level + stale + no_print` (pinned by a test).

A snapshot outage empties the board (every name `no_print`) by design — it never ranks ~2.7k names on unverified cached
bars.

### Which print, when

| clock ET (market day) | `phase` | anchor | states | no / unverifiable row |
|---|---|---|---|---|
| 04:00–09:30 | pre | fresh pre-market trade, else last close (`· last close` on the card) | broken / intact / unknown | `no_print` |
| 09:30–16:05 | rth | fresh print, else today's day close (`· day close`) | + tested / pierced / reversal | `no_print` |
| 16:05–20:00 | close | fresh after-hours print, else day close | the CLOSE decides; `closed_beyond` + `ah_through` = through | `no_print` |
| 20:00–04:00, weekends, holidays | None | last closed close, only on a VERIFIED snapshot row | none live → `broken` = 0; the card carries `last_bar` | `no_print` |

Levels roll at 20:00 (`levels_session`); the memo key changes and the board warms once. Pre-market caveat (engine rule,
his call §7.7 of the spec): a pre-market trade older than `STALE_PRINT_SEC` ranks on last night's close even if that
trade was through the level.

### Two flags on the card

- **A low made in the last session** — `set_on == last closed bar's date` (a new 52-week low yesterday; a Friday that
  set the week's low, seen from Monday; the month's last day). Ranked, flagged `· made Mon 09-28, the last session`,
  counted in the header. `period_levels` now records `set_on` for day/week/month too (every older reader gates on
  `period == "year"`, so no card, ▸ more line or push changed).
- **The closed session, carried past the 20:00 roll** — `key_levels.last_bar_read`: ONE `member_state` close-phase call on
  the last closed bar, for a level whose period ended BEFORE that bar. `tested` / `reversal` are carried with the low's
  depth: `· Mon 09-28 tested (low went 1.18% under)` (the AA case: PWL 42.25, low 41.75, close 42.25). None for every
  52wL and for PWL on the Monday after a Friday low (the bar is inside the level's own period).

## Liquidity floor and turnover

House floor (`DEFAULT_MIN_TIER = "ok"`, $10M/day; the tier dropdown works). Turnover = the scan row's
`avg_dollar_vol`, else the closed frame's `quick_bounce.avg_dollar_vol` (50-bar close × volume — the same formula as
`sepa/adr.py::liquidity_check`). Probe 2026-09-28: 2,099 scan rows vs a 2,754-name universe → **919 (33%)** have no
scan-row turnover, every pinned ETF among them; without the fallback they would all be dropped as "thin". A name with
neither is counted `no_turnover`, never `dropped_thin`. The scan row stays first so a name shows the same "🏦 Avg daily
volume" here as on every other board.

## Payload (`GET /chart-maps?tab=key_levels`)

```
key_levels_board: {
  state: "ready" | "warming", session: "YYYY-MM-DD", phase: "pre" | "rth" | "close" | null,
  periods: ["PWL","PML","52wL"],
  counts: {scanned, ranked, broken, no_level, stale, no_print, set_last_session,
           no_turnover, dropped_thin, shown} | null,          // null while warming
  header: str, note: str, built_at: ISO str | null, measured: false }
matched: ranked − (dropped_thin + no_turnover)
note: EMPTY_NOTE | NOTE | WARMING_NOTE        warming: true (warming only)

tile.key_level_near: {
  label, name, period, price, distance_pct, state, as_of, set_on, set_last_session,
  last_bar: {date, state, low_through_pct} | null,
  print, print_basis: "live"|"day_close"|"last_close", print_session: "premarket"|"rth"|"afterhours"|null,
  through: [{label, price, state}], text }           // text == tile.badges[0].text
```

The tile also carries the standard 2026-09-25 `key_levels` block; on this tab `attach_key_levels` draws
`SUPPORT_PER_SIDE` (2) lines each way and receives the builder's clock and first-seen read (`_ctx`), so the badge and
the drawn line read the same row at the same minute. Every other tab passes `None` (unchanged). The `"default"` sort is
relabelled `🔑 Closest to a key low first` on this tab only.

## The memo (cost)

`chart_maps/key_levels_tab.py` holds an in-process memo keyed `(levels_session, universe)`: ONE `bulk_cached_frames` read,
ONE `closed_frame` cut per name, the levels, the last-bar reads and the turnover — built once per session in a background
thread (the `demand_reentry.cached_or_warm` pattern; the first request says it is warming). `MEMO_TTL_SEC` (1 h) is cache
freshness only: an older entry is served while ONE rebuild runs. It writes nothing — no Mongo, no file (source-guard
test). Per request: ONE universe `bulk_snapshot`, ONE `read_first_seen`, the rank.

Measured before build (read-only, api container): cached frames 2.0–3.0 s, levels 3.4–5.5 s, rank 0.06 s for ~2,750
names; snapshot ≈ 3.9 s (`board.FLIGHT_COST_MEASURED`).

**Measured on the branch (2026-09-28 23:28 ET, off-hours, read-only throwaway container on the branch code, prod price
cache):**

```json
{"date": "2026-09-28T23:28:31-04:00", "env": "cheetah", "n": 2754, "s_build": 8.96, "s_snapshot": 4.33, "s_rank": 0.038,
 "counts": {"scanned": 2754, "ranked": 2657, "broken": 0, "no_level": 8, "stale": 89, "no_print": 0, "set_last_session": 99}}
```

The critic's earlier branch run: build 7.36 s, snapshot 4.1 s, rank 0.052 s, and a **warm request of 7.45 s** wall time
(snapshot + first-seen + rank + tile decoration) — so a warm request costs ~7.5 s, not the ~4 s the snapshot alone
suggests; the cold first request says warming and the ~7–9 s build runs in the background. If the price-cache read comes
back empty (Mongo down), `build` raises instead of memoising a blank, so the tab keeps warming and the next poll retries
(or the previous entry keeps serving) — fix round 2026-09-28. A late rebuild of a session that has already rolled at
20:00 is dropped and never evicts the newer session's entry. Re-run off-hours:

```bash
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.key_levels_tab_cost_probe
```

(The container runs `origin/main`; run it in the branch verify container until this ships.)

## What the list skews to (critic probe, 2026-09-28)

Near a low is where downtrends sit: the top 80 were 89% under their 50-day (pool 75%) and 64% under their 200-day (pool
53%); 12 of the top 80 ranked on a 52wL set on the last closed bar. Inherent to the ask — no trend filter is invented;
fresh lows are flagged and counted, not dropped.

## His call (defaults ship; spec §7)

1. Which levels: PWL / PML / 52wL. Options: add PDL; add a prior-week/month HIGH now below the price.
2. Through a low: per level (rank on the deeper intact low); a name through every low is counted, not listed.
3. Order: pure distance. Option: the demand boards' `demand_order` key.
4. What gets listed: no near cutoff; house floor `ok`.
5. Tab slot: after 📁 My holdings.
6. A low made in the last session: ranked + flagged. Options: exclude, or list last.
7. Pre-market stale print: the engine's rule. Option: a today-dated pre-market trade through the level counts as through.
8. Trend: no filter. Option: one he names.

## Files

`backend/supply_demand/key_levels.py` (additions: `BOARD_PERIODS`, `BOARD_KINDS`, `THROUGH_STATES`, `LAST_BAR_STATES`,
`closed_levels`, `verify_last`, `anchor_read`, `row_or_none`, `last_bar_read`, `is_through`, `nearest_lower`,
`near_block`, `near_text`; `set_on` for every period), `backend/chart_maps/key_levels_tab.py` (new),
`backend/chart_maps/board.py` (`TABS`, `key_level_tiles`, dispatch, sort label, the attach call),
`backend/chart_maps/api.py` (tab description), `backend/supply_demand/rules_info.py` (one pick),
`backend/scripts/key_levels_tab_cost_probe.py`, tests `backend/tests/test_key_levels_tab.py` +
`backend/tests/test_key_levels.py`.

## 2026-09-29 — the 🧨 / 🪜 reads were missing on this tab (fixed)

`key_level_tiles` spread `tile_metrics` flat onto each tile, which carried its always-None `explosive` and
`band_structure` columns onto the tile. `attach_explosive` / `attach_band_structure` are idempotent by KEY
PRESENCE, so they skipped every tile: no 🧨 chip, no 🪜 read, and the 🧨 sort fell to an all-None column
(live 2026-09-29: "No demand-band read for these names", ordered A, AA, AAL…). The same spread hit 🌀 AMD and
Keltner (`turning_bullish_tiles`). Fix: `board.ATTACH_OWNED_KEYS` + `board.published_metrics`, the one filter
every flat spread goes through; `_m` keeps both columns for the sorts. This tab is not in
`enterable.KIND_BY_TAB`, so its 🪜 read is the honest n/a read (was a bare None) and the 🪜 sort stays off here.
Tests: `backend/tests/test_board_attach_owned_keys_2026_09_29.py` (includes an AST source guard against a new
flat spread).


## 2026-09-30 — 🧱 the 1% pad (Ajay: "if the demand zone or key level is 133, it holding at 132")

The tab ranks and counts through `key_levels.nearest_lower` / `is_through`, which now read a support low's PADDED edge: a print inside a low's 1% pad is RANKED (negative distance, the card says "inside the 1% pad"), and only a print 0.15% past the pad counts it broken. The header states it from the constants ("within the 1% pad plus the 0.15% break buffer of"). `rank_key` is unchanged (distance from the drawn level). The DM "Near a lower key level" filter inherits.

Canonical doc: `docs/supply_demand/zone_pad_2026_09_30.md` (the ask verbatim, every site, the phone-gate statement, the sell-timing list and the HIS CALL list). UNMEASURED — no study here says the pad pays.
