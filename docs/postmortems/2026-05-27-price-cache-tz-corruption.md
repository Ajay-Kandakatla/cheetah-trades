# Price-cache TZ + overwrite corruption — postmortem

**Date detected:** 2026-05-27 (evening ET)
**Root-cause commit:** `02c5a66` (2026-05-25, *"Add Minervini setup scanners + SEPA tab strip + Russell 3000 + real-time data"*)
**Fix commit:** TBD on branch `base-line-the-working-code-may-27-2026`
**Severity:** P1 — silently corrupted technical-analysis inputs for ~2 days,
collapsed SEPA candidate count from expected ~20-60 to 1 across Russell 1000.
Real-money trading decisions were being made off these signals.

---

## Symptom

The SEPA scan page reported `1 candidate / 1357 analyzed / 2070 universe`
the evening of 2026-05-27. Trend Template was passing 8/8 on 18 names
(MU, LRCX, AMAT, AMD, AEHR, ANET, NVDA, AVGO, …) and Stage 2 was
classifying the same 18, but **zero** of them had an `entry_setup` — i.e.,
VCP and Power Play detectors were returning `has_base=False` for every
trend-passing leader. User reported: *"It was working till this evening."*

## Root cause

Commit `02c5a66` (2 days prior) introduced a real-time data layer:
`bulk_snapshot()` + `patch_latest_closes()` + `bulk_live_prices()` in
`backend/sepa/prices.py`. The goal was to append today's bar to
Mongo-cached daily series mid-day instead of re-downloading 2 years of
history every TTL expiry. The path had **two distinct bugs that compounded**:

### Bug 1 — UTC normalize, not ET (latent until UTC rollover)

```python
# backend/sepa/prices.py:316 (pre-fix)
bar_date = pd.Timestamp(day_t, unit="ms", tz="UTC").normalize().tz_localize(None)
```

`.normalize()` truncates to **midnight UTC**. After ~20:00 ET each day
(= 00:00 UTC next), `bar_date` for the just-finished US session was
stored with **tomorrow's calendar date**. This produced *future-dated*
bars labelled e.g. `2026-05-28` while ET clock said `2026-05-27`.

The bug only manifested *after* UTC rollover — which is why scans during
the 2026-05-25 / -26 trading day worked fine, then "broke this evening"
when the post-close patch ran past 8 PM ET.

### Bug 2 — Overwrite skipped when today's bar already exists

```python
# backend/sepa/prices.py:399 (pre-fix)
if any(_bar_iso(b) == today_iso for b in doc["bars"]):
    # Bar exists — just bump the TTL so load_prices skips a re-fetch
    already_current += 1
    continue
```

`patch_latest_closes()` is called multiple times per day (cron + on-demand
scans). The **first** call captured the bar from `bulk_snapshot()` and
appended it. Subsequent calls — including the post-close call that should
have settled the bar to end-of-day OHLCV — just bumped `cached_at` and
returned. So a 9 AM pre-market or early-session partial snapshot got
frozen as that ticker's "daily" bar permanently. Manifest in the
corruption survey as bars with volume <10% of the symbol's 50-bar median.

### How it broke VCP

`vcp.py` reads `df["close"]` and `df["volume"]` from the cached series.
The trailing few bars had:
  - **Future-dated calendar gaps** (e.g. May 27 then May 28 then May 28
    appearing on subsequent calls) confusing the swing detector
  - **Partial-day volume** (1-5% of normal) breaking the `vol_drying`
    ratio used to qualify VCP buy points

The combined effect: every trend-passing name's most-recent contraction
appeared to have wildly anomalous volume + close, failing the
`tight_right_side <= 10%` and pivot-quality checks. VCP returned
`has_base=False` → `entry_setup=None` → `is_candidate=False`.

Critically: **no formula in `vcp.py` actually changed** (one commit in
file history). The detector was working on corrupted inputs.

## Detection

Read-only diagnostic at `backend/sepa/diagnose_price_cache.py` was
written ad-hoc during triage. It inspected the tail of 10 symbols and
revealed:
  - 9/10 had a last bar dated **2026-05-28** when ET today was 2026-05-27
  - Several had partial-volume bars 2 days earlier (the May 26 stub)

Follow-up survey `diagnose_cache_corruption.py` confirmed material blast
radius: **5,003 corrupted bars** across hundreds of symbols.

## Fix

`backend/sepa/prices.py`:

1. **`bulk_snapshot()`** — convert `Timestamp` from UTC to
   `America/New_York` *before* `.normalize()`. The ET-truncated date
   then survives the `.tz_localize(None)` strip.
2. **`patch_latest_closes()`** — when today's bar already exists,
   replace it in-place via Mongo positional update
   (`{"$set": {"bars.$": …}}`) instead of skipping. Subsequent calls
   settle the bar toward EOD.
3. **`patch_latest_closes()`** — add a defensive guard: refuse to store
   any bar whose `bar_iso > et_today_iso`. With the TZ fix in place this
   should be unreachable; the guard exists so a future regression fails
   loud instead of silently corrupting.

Companion one-shot repair script at
`backend/sepa/repair_cache_corruption.py`:
  - `$pull` every bar whose `date > today midnight ET` from the array
  - `$set cached_at: 0` on every row, forcing TTL miss → full _fetch
    → `_mongo_put()` overwrites the entire bars array clean

## Prevention

Concrete steps already taken on the fix branch:
  - The defensive `bar_iso > et_today_iso` guard in `patch_latest_closes`
  - Diagnostic scripts live in the repo for future ad-hoc inspection
  - Postmortem (this doc) cross-references the originating commit so a
    future audit will find this trail

Recommended next steps (NOT yet done, captured for follow-up):
  1. **Unit test** for `bulk_snapshot` with a fixed-clock fixture that
     verifies a 21:00 ET ingest produces a bar dated today, not tomorrow.
     Place in `backend/tests/test_prices.py`.
  2. **Integration test** for `patch_latest_closes`: simulate two calls
     in the same day with different OHLCV; assert the stored bar is the
     **second** call's values, not the first.
  3. **Data-quality canary** in the scan pipeline: log a warning (and
     optionally skip a symbol) when its most-recent bar has volume
     < 20% of its 50-bar median, or has a date in the future. Catches
     similar silent corruption faster next time.
  4. **Contracts §10** of `SEPA_CONTRACTS.md` doesn't yet mention price
     cache invariants. Worth adding a §13 "Price-cache contract" that
     freezes: bars must be ET-dated, exactly one bar per trading day,
     volume must be EOD (not intraday snapshot), monotonically increasing
     dates.

## Why the contracts doc didn't catch this

SEPA_CONTRACTS.md §6-§11 are excellent at locking *formulas* (VCP rules,
trend template, score weights). They say nothing about the *data
contract* — the implicit assumption that `prices.load_prices()` returns
a properly-dated, EOD-complete daily series. The real-time data layer
in `02c5a66` violated that implicit assumption silently. Locking the
formula tells you nothing if the inputs are wrong.

This is a general lesson: in a system where derivatives of derivatives
of price data drive money decisions, **data-shape contracts deserve
the same locking discipline as scoring contracts**.

## Lessons

1. **Real-time / mid-day data appends to a "daily" cache are fundamentally
   dangerous.** A daily bar is, by definition, EOD-complete. Anything
   else is a different data type and shouldn't share a column.
2. **`.normalize()` is timezone-naive but the world isn't.** Any time
   `.normalize()` is called, ask: which midnight?
3. **First-write-wins on a "today" record is almost always wrong** when
   the record represents a still-settling event.
4. **A silent data corruption is worse than a loud failure.** The trader
   would have caught a crashed scan immediately; the wrong-1-candidate
   list looked plausible enough to ignore for hours before being flagged.
