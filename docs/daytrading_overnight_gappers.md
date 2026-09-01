# Overnight gappers — honesty rules (2026-09-01)

Ajay, off the board's own screen: "Will IREN and SNDK bounce then tomorrow?
based on this that is a lot of volume." Both premises were misreads the page
itself created, so the rules below are contract-tested.

## What went wrong

The night of 2026-08-31 the board showed "SNDK ▲4.4% O/N". Decoded from the
raw snapshot: Monday's REGULAR session was +4.37% (1484.98 → 1566.70) and the
actual after-hours drift was **−1.07%** (last trade 1549.94). When the
extended move is < 2% the headline falls back to the regular-session gap —
but the O/N chip was stamped from session state, so a regular-session number
wore an overnight label. "$ Vol $23.1B" was SNDK's 50-day AVERAGE dollar
volume (universe metadata), not anything that traded that night.

## The rules (backend/daytrading/premarket.py)

1. **The chip follows the number** — `_headline_move(session, gap, ext)`
   returns `(move, move_is_ext)`; the FE renders the PM/AH/O⁄N chip only when
   `move_is_ext`. Pure function, test-locked with the literal SNDK case.
2. **The drift is its own column** — `ext_move_pct` renders as "O/N drift"
   with its own sign/color, `=` when it already headlines, `—` when absent.
3. **Average is labelled average** — the liquidity column reads "$ Vol avg".
4. **Real overnight volume exists now** — `_extended_dollar_vol(df, which)`
   sums tonight's extended-session `close×volume` from the 1-min bars
   (afterhours when closed/AH, premarket in PM), top-15 enriched names only.
   Rendered as "O/N $ Vol". None ≠ zero: no extended prints → dash.
5. **ET date, not UTC date** — `_et_today()`; `utcnow().date()` named
   tomorrow for the four hours after midnight UTC (20:00–24:00 ET), which is
   exactly when the overnight board is most read, so the PM H/L and extended
   volume enrichments queried an empty day.

## Chart Maps tab

`overnight` is the third non-board tab (after `support`, `session`) —
mounts the same `OvernightGappers` component the Day Trading page uses,
row-click hands the symbol to the Support tab. Registered in
frontend/src/lib/chartMaps.ts; contract tests pin the tab list and the
exactly-three non-board set.

Tests: backend/tests/test_gappers_overnight.py (11) ·
frontend/src/components/OvernightGappers.test.tsx (4) · chartMaps contracts.
