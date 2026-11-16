# 📋 All strategies — nearest-to-trigger sort, "To 9 EMA" column, ➕ Watch (2026-11-16)

Ajay, verbatim: "Can you sort the table of all strategies by nearest to A+ support and then nearest to the EMA. please" ·
"Add those columns to the Table and a Add to watch button". His answers (asked 2026-11-16): "nearest to A+ support" =
closest to the trigger (the To trigger column); "the EMA" = the 9 EMA; a toggle, remembered, GG's order one click away.

## What changed (display only — no gate, count, alert or trade reads any of it)
- `backend/chart_maps/gajjala/all_table.py`
  - `ema9_of(doc, tf, v)`: the 9 EMA on the card frame's latest stored (closed) bar, off the tile's own served curve
    (tone `bars.EMA_TONES[0]`); warming / missing / zero → None (never 0).
  - Each row: `ema9`, `ema9_text`, `ema9_gap_pct` = (price − 9 EMA) / 9 EMA × 100 (+ above, − under), `ema9_gap_text`,
    `ema9_title`, and `near_rank`.
  - `near_order(rows, flags)`: |To trigger| **as printed** (one decimal, so two rows the eye reads as equally near tie),
    then |price vs the 9 EMA|, an unknown on either key after every known one, then GG's rank; his 🚫 names last
    (`tab.broker_bottom`, the 2026-11-09 invariant). GG's `rank` is untouched.
  - New head `("ema9", "To 9 EMA")` after To trigger; block `sorts` = {default "gg", options, near_text}.
- `frontend/src/components/GgAllTable.tsx`: the served sort buttons (remembered, `localStorage gg-all-sort`; a pick the
  server does not serve → GG's order); under the near order the rows are laid out by the SERVED `near_rank` and the #
  column shows it (a row without one → GG's order stands; the FE never computes an order); "GG's 18" divider under GG's
  order only; the "To 9 EMA" cell; the ONE `GgWatchButton` (owner only, one shared list GET) beside the ticker.

## Goldens
`backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json` regenerated (GG_WRITE_GOLDEN=1): 76 changed paths, ALL under
`live/all_strategies` and `shadow/all_strategies` `table` (the six new row keys × 12 rows, `heads`, `sorts`). The WRITES
golden `gg5_writes_2026_10_27.json` is byte-identical.

## Tests
`backend/tests/test_gajjala_all_table_near_sort_2026_11_16.py`, `frontend/src/components/GgAllTable.near_sort.test.tsx`
(NEGATIVES: warming / zero / 21-tone EMA never read as the 9; unknowns never sort as 0; GG's rank never moves; input never
mutated; 🚫 last; older API ignores a stored pick; a missing near_rank keeps GG's order; no button for a non-owner).

UNMEASURED — an order to look at, not a signal.
