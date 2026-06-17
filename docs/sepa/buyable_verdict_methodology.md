# Minervini + Bonde buy verdict — methodology

**Module:** `backend/sepa/buyable_verdict.py`
**Frontend:** `BuyVerdictChip` (card badge) · `BuyVerdictPanel` (detail Analysis tab)
**Contract:** `docs/SEPA_CONTRACTS.md` §3 (`buy_verdict`) · locked by
`tests/test_sepa_contracts.py::test_buyable_verdict_constants_locked_and_display_only`
**Behavioral/regression tests:** `backend/tests/test_buyable_verdict.py`
**Requested:** Ajay, 2026-06-16 — *"make the sales logic follow Minervini's
verdict of buyable stock AND Pradeep Bonde's, and give it a pass (green) or fail
per their analysis on all stocks."*

---

## What it is

A single **PASS / PARTIAL / FAIL** badge, shown on every stock, that folds the
app's two independent "should I buy this?" frameworks into one glance:

| Pillar | Question | Source of truth (already in the app, already cited) |
|---|---|---|
| **Minervini** | Is this a *buyable stock*? | `is_candidate`/`qualifier` + `is_buyable` (scanner §5) |
| **Bonde** | Is the *sales growth* there? | `fundamentals.sales` (`sepa/sales.py`) |

It **invents no new thresholds.** It only *combines* two frameworks that each
already have their own methodology doc, contract lock, and tests. This module is
**additive and DISPLAY-only** — exactly like `group_leadership`. It reads
existing row fields and never alters `score` / `is_candidate` / `is_buyable` /
`SCORE_WEIGHTS`, so the §4 sum-to-100 invariant is untouched.

---

## Pillar 1 — Minervini: "is this a buyable stock?"

Source: Mark Minervini, *Trade Like a Stock Market Wizard* (2013). The book uses
**two tiers**, and the codebase already encodes both (see SEPA_CONTRACTS §5):

- **Qualifier** — **p.79**: *"The Trend Template is a qualifier. If a stock
  doesn't meet the Trend Template criteria, I don't consider it."* This is the
  screening verdict (Stage-2 leader, RS ≥ 70, 8/8 trend, liquid) = the row's
  `is_candidate` / `qualifier` flag.
- **Buyable now** — **pp.198-203**: the *timed* buy trigger — a volume-confirmed
  breakout near the pivot (*"the point at which you want to buy is when the stock
  moves above the pivot point on expanding volume,"* p.203) = the row's
  `is_buyable` flag.

**Decision:** the Minervini pillar **passes on the qualifier (p.79)** and
*separately* reports `buyable_now` (pp.198-203). Why not gate the pass on
`is_buyable`? Because a great Minervini stock spends *most* days set up but not
triggered — gating the pass on the daily trigger would paint almost every name
red and bury the screening signal the user actually wants ("is this even a
Minervini-grade stock?"). The breakout-now state is surfaced prominently in the
label ("BUY — … breakout live") and the pillar's `buyable_now` line, so nothing
is lost. This mirrors the book's own qualifier-vs-buy-point distinction.

```
minervini.passed      = bool(is_candidate or qualifier)     # p.79
minervini.buyable_now = bool(is_buyable)                     # pp.198-203
```

## Pillar 2 — Bonde: "is the sales growth there?"

Source: Pradeep Bonde / Stockbee, sales-driven. Reads the already-computed
`fundamentals.sales` block — see `docs/sepa/sales_confidence_methodology.md` for
the full sourcing of his documented **5% floor / 25% preferred / 100% explosive**
thresholds and the QoQ-vs-YoY caveat. His two NAMED catalysts are **acceleration**
(growth rate rising) and **consistency** (consecutive growth quarters).

**Pass gate:**

```
cleared_floor = growth_yoy_pct >= SALES_FLOOR_PCT            # 5%  (his floor)
has_character = accelerating OR consecutive_growth_q >= 2     # his named catalysts
bonde.passed  = cleared_floor AND has_character
bonde.strong  = growth_yoy_pct >= SALES_PREFERRED_PCT         # 25% (his "preferred")
```

- `SALES_FLOOR_PCT` and `SALES_PREFERRED_PCT` are **re-exported from `sales.py`**
  so the verdict can never drift from the score it reads.
- `BONDE_MIN_CONSEC_Q = 2` is the one **configured** knob — Bonde names the
  consistency catalyst but publishes no consecutive-quarter count; 2 = the
  minimum that reads as a trend, not a one-quarter blip. (Stated as configured,
  not a Bonde number — Rule #1.)
- **Acceleration never rescues a name below the 5% floor** (regression test):
  a tiny +3% "accelerating" from +1% is still a Bonde fail.
- **No sales data → `passed = None` ("pending")**, never a silent fail. Sales are
  only enriched for the top-N candidates (thousands of financials calls otherwise),
  so most universe rows carry a Minervini-only verdict until enriched.

## Combined status

```
pass     — Minervini pillar passes  (both_pass when Bonde ALSO passes;
                                      sales_pending when Bonde is None)
partial  — exactly ONE pillar passes (price-side good but sales fail, OR
                                       sales good but not a Minervini setup)
fail     — neither pillar passes
```

A full green (`both_pass`) means *both* frameworks agree. When the breakout is
also live (`minervini.buyable_now`), the label escalates to **"BUY — Minervini +
sales, breakout live."** ETFs render no verdict (the Minervini gates don't apply
to baskets).

---

## What this is NOT

- **Not a scoring change.** `buy_verdict` is a post-pass annotation; the composite
  score, `is_candidate`, `is_buyable`, and `SCORE_WEIGHTS` are untouched
  (SEPA_CONTRACTS §12-safe). Confirmed by the display-only contract test.
- **Not a new gate.** It re-expresses §5's already-locked gates + `sales.py`'s
  already-locked score. Changing the *combination* logic (the pass conditions,
  `BONDE_MIN_CONSEC_Q`) is a methodology change (Rule #4): update this doc + the
  contract lock together.
- **Not universe-wide for sales.** The Bonde pillar only fills in on the enriched
  top-N (or after a `↻ + catalyst` on the detail page). This is stated in the UI
  (`sales_pending` → "n/a (not enriched)") rather than hidden.

## Where it shows

- **Every SEPA card** — `BuyVerdictChip`, always-on, under the header:
  `🟢 PASS · Minervini ✓ · Sales ✓`.
- **SEPA detail → Analysis tab** (moved up to 3rd, with the old Sales tab folded
  in) — `BuyVerdictPanel` leads with the combined headline + the two pillars
  side by side (each with its PASS/FAIL verdict and page cites), then the
  Sales-confidence detail grid, then the Fidelity-style multi-source readout.
- **`/breakouts` page** (2026-06-16) — the verdict is the overlay on the
  breakout-count ranking, so the breakout tracker shows which high-breakout names
  pass Minervini / Bonde and which don't. See `docs/sepa/breakouts_page.md`.
