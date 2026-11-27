# 🚩 card display fixes — 2026-11-27 (backend)

SPEC sicheck rev 2 §3.6 D4 + B3, package `gg-display-be`. Display only: no gate, rung, count, sort, push or trade moves.
The frontend half (hover range D1, printing the stamp) is in `chart_display_fixes_frontend_2026_11_27.md`.

## D4 — "as of HH:MM" on a card whose scan row is from an earlier pass

**2026-11-27.** A card's Change and Volume come from the name's scan doc (`gajjala_scan.last`). When the shown pass did
not re-qualify the name, that row is an older pass's — NXAT's card at the 08:40 pass still showed the 08:21 volume, and
nothing said so. `tab.py` now serves `chips.row_asof = {"text": "as of HH:MM"}` when the scan doc's
`last_qualified_at` is older than the shown pass by at least `READ_AT_MIN_LAG_SEC` (= 1 s, the literal the "read at the
HH:MM ET pass" chip always used, now named and read by both rules). HH:MM is the row's own `last.last_trade_et`, else
the qualify stamp in ET. The key is ABSENT when the row is the shown pass's own, or either stamp is missing.

- `_row_asof(scan_doc, pass_at)` builds it; `_chips(..., row_asof=None)` sets the key only when given;
  `setup_tile(..., row_asof=None)` passes it; `build` hands it at both `setup_tile` call sites (the setup subs and the
  🧠 cards through `_potential_tiles(..., row_asof=_asof)`).
- The numbers are NOT replaced: the stamp says how old the volume is; the number stays the older row's. Re-ordering
  which row feeds the card (`run.py:540-541`) is HIS CALL #15 and is not touched.
- Volume, change, the 📊 sort key `_volume` and the card order are identical with and without the stamp (pinned).

## B3 — a stale float says "read", not "as of"

**2026-11-27.** `context._staled` printed `Float 3.1M (stale, as of 2026-10-04)`. That date is when Yahoo was last read
for the name (the `shares_cache` row's `as_of`), not the age of the float value. It now prints
`Float 3.1M (stale, read 2026-10-04)` with the same date string; a fresh row's text is unchanged. The `_row_as_of`
docstring says it is the READ time of the cache row. (The 👀 Watch already said "read".)

## Not built

Odd lots (D2) and whole-share volume (D3) were NOT built: their files (`live_events.py` / `live_hub.py`, and
`support.py`, whose bars feed session_board, the support tab and the 🚩 bars, not provably gate-free) are in no package
of this build — odd lots are HIS CALL #16.

## Tests

`backend/tests/test_gajjala_chart_display_2026_11_27.py`; pins moved in `test_gajjala_context.py` and
`test_gajjala_watch_float_2026_11_21.py` ("(stale, read").

**Golden regen 2026-11-27.** `frontend/src/components/__fixtures__/gajjala_potential_golden_2026_10_15.json` rewritten by
its recipe (`GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_potential_tab.py -k golden`), diffed leaf by leaf
against HEAD: 4267 -> 4278 leaves, 11 ADDED, 0 changed, 0 removed — `chips.row_asof.text` = "as of 09:21" on the 5
bull_flag and 6 potential tiles (the fixture's scan rows qualified a pass before the shown one). Nothing else moved. One
file, three pins: `test_gajjala_potential_tab::test_golden_fixture_is_the_served_payload`,
`test_gajjala_day_read_wiring_2026_11_15::test_every_golden_moves_only_by_the_added_day_read_key[potential]`,
`test_gajjala_squeeze_marks_2026_11_08::test_potential_golden_moves_only_by_rs_ellipses`.
