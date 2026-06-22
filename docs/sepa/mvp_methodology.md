# MVP Indicator + base-stage-aware buy gate — methodology

**Module:** `backend/sepa/mvp.py` · wired in `backend/sepa/scanner.py`
**Source:** Minervini, *Think & Trade Like a Champion* (TTLAC) — local copy
`backend/books/ttlac.md` / `ttlac.pdf`. Cites are **Section + ebook page** (TTLAC
has no print pages). Contract locks: `backend/tests/test_sepa_contracts.py`
(`test_mvp_constants_locked`, `test_base_count_nested_shape`, `test_buyable_gate`).
Behavioral tests: `backend/tests/test_mvp.py`.

Added 2026-06-19 after a page-cited audit confirmed the app (a) had no MVP
indicator and (b) prematurely sidelined runners while letting blow-off tops pass
the buy gate. Ajay signed off on the full fix.

## 1. The MVP indicator (David Ryan's "ants") — TTLAC §1, ebook p.33

> "David told me an easy way to remember this setup is to refer to it as the
> 'MVP indicator,' which stands for momentum, volume, and price. Stocks that
> continued much higher had the following characteristics … **Momentum.** The
> stock is up 12 out of 15 days. **Volume.** The volume increases 25 percent or
> more during the 15-day period. **Price.** The stock price is up 20 percent or
> more during the 15 days." — TTLAC §1, p.33

`mvp.compute(df)` returns the footprint over the trailing 15 trading days:

| field | rule | book |
|---|---|---|
| `up_days` ≥ `MVP_UP_DAYS_MIN` (12) | up 12 of 15 days | §1 p.33 |
| `price_pct` ≥ `MVP_PRICE_PCT_MIN` (20.0) | +20% over the window | §1 p.33 |
| `volume_pct` ≥ `MVP_VOLUME_PCT_MIN` (25.0) | +25% over the window | §1 p.33 |
| `has_mvp` | all three true | §1 p.33 |

These four constants are **book numbers**, locked in the contract — Rule #4
(page-cited doc + sign-off) for any change.

### House interpretations (NOT book numbers — the book is silent on the specifics)
- **Volume baseline.** "the volume increases 25 percent" gives no baseline, so we
  read `volume_pct` as the average daily volume over the 15-day window vs. the
  average over the **prior 15 days** (volume stepped up as the move began).
- **`near_base_bottom`** (the §1 p.34 buy exception): the window's start close must
  sit within `MVP_BASE_BOTTOM_BAND_PCT` (10%) of the prior base low, where the
  base low = min low over `MVP_BASE_LOOKBACK` (50) bars before the window.

## 2. Context decides bull vs bear — TTLAC §1 p.34 + §9 p.199

The same footprint is read **oppositely** depending on stage (decided in
`scanner._mvp_context`, not in `mvp.py`):

- **Continuation (bullish).** From an early/mid-stage base it marks a runner that
  "continued much higher" (the GOOGL 2004 +625%/40-month example, §1 p.33).
- **Exhaustion (bearish / sell).** TTLAC §9 p.199 is explicit that this is a
  **late-stage-only** read: "a late-stage exhaustion move versus an early-stage
  breakout move," and "if the type of action … occurs from an early stage base …
  these actions are a **bullish** signal." So:

      mvp_exhaustion = is_late_stage (base ≥4) AND (has_mvp OR climax)

  A late-stage base showing **either** the full MVP footprint **or** a pure price
  climax (`sell_signals.climax_run_25pct_in_3w`). The climax leg catches a
  late-stage blow-off the 12/15 up-day count alone misses — e.g. MRVL: base 4,
  +52% in 3 weeks, only 10/15 up days → no full MVP, yet a blow-off. From an
  **early/mid base (≤3)** the same action is NOT a sell (the §9 caveat) — it
  stays buyable, governed only by the extension cap. *(Fixed 2026-06-19: the
  first cut flagged early-base MVP+climax as exhaustion — contradicting the §9
  caveat — and missed late-stage climaxes lacking the full up-day count.)*

`mvp_read` = `"continuation"` | `"exhaustion"` | `null` drives the card chip.

## 3. Base-stage gate — TTLAC §9, ~ebook p.200

> "bases 1 or 2 … the best time to jump onboard a new trend; bases 3 and 4 can
> also work, but are later in the cycle and should be treated more as trading
> opportunities. Bases 5 or 6 are extremely failure prone and should be viewed as
> opportunities to sell into soon after a price breakout gets extended."

`base_count` now exposes:
- `is_early_base` = base ≤ 2 (best),
- `is_late_stage` = base ≥ 4 (score penalty / label — **unchanged**),
- `is_avoid_stage` = base ≥ 5 (**new** — the buy-gate exclusion).

**Before:** `is_late_stage` (base ≥ 4) blocked the buy gate entirely — so the app
threw out the tradeable bases 3–4 the book allows. **Now** the gate excludes only
`is_avoid_stage` (≥ 5); bases 3–4 stay buyable (still penalised in score).

## 4. Buy-gate changes (`_is_setup_ready` / `_is_buyable`)

1. **Base 3–4 tradeable** — exclusion switched from `is_late_stage` to
   `is_avoid_stage` (≥ 5).
2. **MVP near-base-bottom exception** (§1 p.34: "in position to be bought
   immediately"): an MVP run whose 15-day window began near the base low
   (`mvp.near_base_bottom`) is buyable **even past** the 3% extension cap
   (`BUYABLE_MAX_EXT_PCT`, unchanged — that number is still book-consistent with
   TLSW p.224).
3. **Exhaustion safety net** — `mvp_exhaustion` (MVP extended from a late-stage
   base / during a climax) **blocks** the buy gate. This closes the "buy/sell
   disagree" hole: a blow-off top never forms a 15-bar consolidation, so
   `base_count` alone would call it base 1 (early) and let it through; the MVP
   reverse read now stops it.

Score: `mvp_exhaustion` → −8 (sell); MVP continuation off an early base → +3.

## 5. What we can't get / out of scope
- Exact base-bottom detection is a proxy (start price within 10% of the trailing
  low), not a parsed base structure. Tightening it is future work.
- P/E-expansion late-stage confirmation (TTLAC §9 p.200) is **not** implemented —
  deferred.
- The engine never consumes the RAG; this is hard-coded, page-cited math.
