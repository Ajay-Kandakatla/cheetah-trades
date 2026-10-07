# Whales: 13D/G form names, major holders, n_new (2026-10-06)

Three data-read defects in the institutional-flow surfaces. None changes a
gate, threshold or ranking; each one restores data that was being dropped or
stops a placeholder from reading as a fact.

## 1. SEC 5% filings were invisible after EDGAR's rename

**Defect.** `supply_demand/whales_13d.py` tracked only `SC 13D`, `SC 13D/A`,
`SC 13G`, `SC 13G/A`. EDGAR renamed these forms in Dec 2024 to
`SCHEDULE 13D`, `SCHEDULE 13D/A`, `SCHEDULE 13G`, `SCHEDULE 13G/A`, so every
filing since then was skipped and `n_form13` read 0.

**Evidence (live, read-only, 2026-10-06).** 0 of 3,458 `whales13d_cache` docs
carried a `SCHEDULE` form. VST's EDGAR list has 4 `SCHEDULE 13G` and 2
`SCHEDULE 13G/A` since 2025 (newest 2026-08-07), and its cached `n_form13`
was 0. With the fix: VST, NVDA and CEG each count 1 in the 120-day window and
5 / 5 / 6 over 430 days.

**Fix.** `_FORMS_13_DG` lists both naming generations; `_FORMS_TRACKED` and
`_form_bucket` use it (exact match, so `SCHEDULE 13E3` and other schedules
are still excluded). `Whales13DModal.tsx` gives both generations the 13D / 13G
icon.

## 2. `major` was `{}` in every cached whales doc

**Defect.** yfinance 1.2.0 (the api image) returns `major_holders` as a 4x1
frame indexed by `insidersPercentHeld`, `institutionsPercentHeld`,
`institutionsFloatPercentHeld`, `institutionsCount`, with values as fractions.
The parser read `row.iloc[1]` (a label column that no longer exists), so
`major` was `{}` in all 4,033 `whales_cache` docs. That hid "Institutional
held %", "Insider %" and "out of N reporting funds" in `WhalesFlowModal` and
`NodeThesisPanel`.

**Fix.** `whales._parse_major_holders` reads both shapes. The new shape is
formatted to the same display strings the FE already shows (`0.92015` becomes
`"92.02%"`), and the count becomes an int. The old row-wise shape still works,
and its "Number of Institutions…" row is now matched before "institution", so
it can no longer overwrite the institutional %. A NaN or zero value is left
out, never turned into a 0. Live: VST `92.02%` institutional, `0.78%` insider,
1,881 funds.

## 3. `n_new` / `n_sold_out` were hard-coded 0

A top-10 holder list cannot show that a fund opened or exited a position.
Both fields are now `null` (unknown) until a real quarter-over-quarter
comparison feeds them. No computation was made up to fill them. No FE surface
renders them today. The types now say `number | null`, and the fund-count
lines hide a 0 or missing count rather than printing "0".

## Refresh

Cached docs keep the old data until they are refetched:

- **13D/G:** the daily 19:00 `sepa.warm_whales_13d` refetches any doc older
  than 24h. They heal within 1–2 days of a deploy that includes `cron`.
- **13F `major`:** a modal open refetches a doc older than 24h. The Sunday
  06:00 `sepa.warm_whales` runs `--stale-only`, which skips tickers already on
  the current 13F quarter. So most docs keep `major={}` until the next quarter
  turns over, unless someone runs a one-off
  `python -m sepa.warm_whales --all --workers 4`. That run was measured at
  128 s for 2,611 tickers. It is safe outside RTH, and its empty-fetch guard
  keeps good docs from being overwritten. It was not run.

Tests: `backend/tests/test_whales_13g_major_holders_2026_10_06.py`,
`frontend/src/components/WhalesDataReads.test.tsx`.
