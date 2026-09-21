# Sales Confidence Score — methodology & sourcing

**Code:** `backend/sepa/sales.py` (`compute`) · wired via `backend/sepa/canslim.py`
**Contracts:** `backend/tests/test_sales.py` (behavioral) · `tests/test_sepa_contracts.py::test_sales_confidence_thresholds_locked` (source guard)
**Status:** new 2026-06-02. User ask: *"stock picks should be driven by sales… I want a sales confidence score."*

---

## 1. What this is — and what it is NOT

A 0-100 **Sales Confidence Score** that ranks a stock on its **revenue growth,
acceleration, and consistency**. It is **inspired by Pradeep Bonde ("Stockbee")**,
who emphasises sales as a driver of explosive moves, but it is a **principled
score we built**, NOT a verbatim reproduction of a Bonde formula — he never
publishes a 0-100 sales score. (Per Ajay's Rule #1, this distinction is explicit
so we never present our weighting as "Bonde's rule.")

Failed source verification (not used): 30% (Deepvue / TradeZella / TraderLion) and "MAGNA 53+".
His, verified 2026-09-20: "two quarters of revenue growth of 39% plus" (2025-09-01, https://stockbee.blogspot.com/2025/09/find-young-episodic-pivots.html).
That 2025 figure was listed in the paragraph above by mistake until 2026-09-20; it is now its own pick leg on the 📈 Bonde tab.

## 2. Whose sales number is whose

| Threshold | Meaning | Source |
|---|---|---|
| sales **≥ 5%** | HIS floor — *"Sales/revenue should be up 5% or more."* | Stockbee, *How to Trade Earnings* (2007), https://stockbee.blogspot.com/2007/03/how-to-trade-earnings.html |
| **25%+** | **this app's mid-tier — NOT his**; the first-person quote attributed to him here was fabricated (removed 2026-09-20) | this app, 2026-06-02 |
| **100%+** | boundary of his *"Sales 100% plus but no earnings"* EP category | Stockbee, *What are Episodic Pivots* (2010) |
| **Earnings acceleration** | his: *"Now what one is looking for is earnings acceleration."* (2007); *"a significant earnings acceleration compared to last year same quarter as well as quarter over quarter"* (2010) | Stockbee (2007, 2010) |
| **2025 revenue** | *"Their real moves start when they start growing revenue aggressively."* | Stockbee (2025-09-01) |
| **2025 scan** | *"two quarters of revenue growth of 39% plus"* | Stockbee (2025-09-01) |

Sources: `stockbee.blogspot.com/2007/03/how-to-trade-earnings.html`,
`/2010/02/what-are-episodic-pivots-and-how-to.html`,
`/2014/07/my-process-flow-for-episodic-pivots-ep.html`,
`/2025/09/find-young-episodic-pivots.html`.

### Honesty notes (from the verified research)
- Bonde's EP **entry** is a **price/volume** gate (`c/c1>1.04 and v>3*avgv50.1 and v>=300000`), NOT a sales %. Sales is the **fundamental confirmation** examined *after* a move — so this score is a **conviction/confirmation layer**, not a trigger.
- In his **2007/2010** core posts, **earnings** is the primary gate (100%+ QoQ doubling) and sales is confirming. In **2025** he leans sales-first. Both are his genuine words → we treat sales as a **standalone signal**, not "the one rule."
- The **"sales is harder to manipulate than earnings"** rationale was **NOT** found in any verified Bonde source (it's general sales-investing folklore) — so the code/doc does not attribute it to him.
- **QoQ vs YoY:** for EARNINGS he names BOTH legs (2010 — *"compared to last year same quarter as well as quarter over quarter"*); for sales he wrote *"up 5% or more"* without a base — this app reads y/y (latest quarter vs the same quarter a year earlier) to match the app's existing `canslim` metrics. Documented here so it can't be mistaken for a settled Bonde rule.

## 3. Algorithm (`sales.compute(rev_q_series, eps_growth_q)`)

Input: newest-first **quarterly revenue series** (8 quarters, from the same
Massive financials fetch `canslim` already does — no extra API call). Needs ≥ 5
quarters for one YoY comparison, else `score = None` (we never invent a score).

- `growth_yoy_pct` = (rev[0] − rev[4]) / |rev[4]| × 100
- `accelerating` = latest YoY > prior-quarter's YoY (and > 0)
- `consecutive_growth_q` = consecutive recent quarters with positive YoY (0–4)
- `sales_led` = `growth_yoy_pct` > `eps_growth_q` (top line outpacing bottom line)

**Score (0–100):** a growth-level **base** mapped through Bonde's 5/25/100 tiers,
plus bonuses (only **above the 5% floor**):

| YoY growth | base | tier |
|---|---|---|
| < 0% | 0–20 | declining |
| 0–5% | 20–35 | weak |
| 5–25% | 35–55 | steady |
| 25–100% | 55–85 | strong |
| ≥ 100% | 85–100 | explosive |

Bonuses (g ≥ 5% only): **+10** accelerating · **+2.5 per** consecutive growth
quarter (cap +10) · **+5** sales-led. Clamped 0–100. The base mapping is
book-anchored; the bonus magnitudes are **ours** (documented, not Bonde's).

## 4. Output (on `row.fundamentals.sales`)

```jsonc
{ "score": 99, "tier": "strong", "growth_yoy_pct": 84.7, "prior_yoy_pct": 70.1,
  "accelerating": true, "consecutive_growth_q": 4, "sales_led": false }
```
`score: null` / `tier: "unknown"` when there isn't enough revenue history (or on
the yfinance fallback path, which doesn't expose a clean series).

## 5. How it feeds the app
Surfaced as a **card chip**, a **filter** (e.g. "Strong sales"), and a **sort**
("Sales confidence"). It is **NOT** folded into the composite `SCORE_WEIGHTS`
(that locked spec is unchanged) — sales drives the list via sort/filter, so the
canonical Minervini score stays intact. Folding it into the composite is a
deliberate future decision, not a silent one.

## 6. Verified-real examples (2026-06-02)
PLTR 99 (84.7% YoY, accelerating, 4q) · NVDA 82 (85% but **decelerating** → no
accel bonus, correctly) · MKSI 70 (15% steady, accelerating, sales-led).

## 7. Contracts
`test_sales.py` (explosive / strong / below-floor-stays-weak / declining /
acceleration / consistency / sales-led / insufficient-history / thresholds) via
`make contracts-sales`; `test_sales_confidence_thresholds_locked` guards the
5/25/100 anchors. `test_SOURCE_GUARD_sales_arithmetic_frozen_hash` (in
`test_sales.py`) pins the module's docstring-stripped AST;
`test_SOURCE_GUARD_bonde_attribution_2026_09_20` (in `test_sepa_contracts.py`)
pins the attribution wording across the code and these docs.

## 8. The Sales tab (SEPA detail page) — added 2026-06-16

`frontend/src/components/SalesPanel.tsx` renders this score on a dedicated
**📈 Sales** tab in `SepaCandidate.tsx`, reading `base.fundamentals.sales`
(already on the `/sepa/candidate/{symbol}` payload — no extra fetch). It leads
with **acceleration** (latest-vs-prior-quarter YoY — Bonde's core signal), then
sales growth %, consecutive growth quarters, and the sales-led flag, with the
0–100 score + tier badge. Display-only; when fundamentals aren't cached the tab
offers the same "re-scan with +catalyst" action as the Fundamentals tab. Tests:
`SalesPanel.test.tsx` (render + accelerating/decelerating + insufficient-history
+ null negatives).

## 9. Folded into the Minervini + Bonde buy verdict (2026-06-16)

The sales score is now also the **Bonde pillar** of the combined buy verdict
(`backend/sepa/buyable_verdict.py`). A name **passes** the Bonde pillar when its
YoY growth clears the 5% floor AND this app's character clause (acceleration or
≥2 consecutive growth quarters — the app's, mis-attributed to him until
2026-09-20); that pillar is paired with Minervini's buyable-stock gate into one
PASS / PARTIAL / FAIL badge shown on every card. The Sales-confidence tab was
merged into the **Analysis** tab (which moved up to 3rd) — the verdict leads, the
sales detail grid follows. Full derivation:
`docs/sepa/buyable_verdict_methodology.md`.

---

## The YoY pair guard is a BOARD rule — the tiers did not move (2026-09-20)

The 5% floor is his; 25% is this app's; 100% is his category boundary. The three
threshold values above are **unchanged**. `sepa/sales.py` — `_yoy`, its `abs(base)` divide,
`compute`, `score` and the tier boundaries — is untouched: it is book-cited,
locked by `test_sepa_contracts` and read by the falling-knife gate on several
other boards, so moving its arithmetic would move every one of them.

What shipped on 2026-09-20 sits **above** it. Massive omits a quarter it does
not have, so the list POSITIONS the year-over-year legs are computed at (0 vs 4,
and 1 vs 5 for the prior leg) are not always four fiscal quarters apart —
measured on the live board, **164 of 1,051 Bonde passers, 15.6%**. The 📈 Bonde
board and the 🔥 Hottest row now check the period keys before they TIER or
PRINT the number, exactly as the 🚀 Explosive Growth board has refused those
rows since 2026-09-14. The check lives in `sepa/qoq.py` (`yoy_pairs_ok`,
`yoy_pairs_verifiable`, `period_ok`) and nobody recomputes a growth figure: a
board declines to place the row, `sales.compute` still returns what it always
returned. Report: `docs/sepa/data_spine_audit_2026_09_20.md`.

---

## 2026-09-20 — nine attribution drifts corrected (D1-D9)

Wording only. No gate, threshold, constant or executable line moved. Each row
DESCRIBES the drift; no retracted phrase is reproduced anywhere below.

| # | What the app said | What it says now |
|---|---|---|
| D1 | his 2025 two-quarter revenue figure was listed among the figures that failed verification | it is his (2025-09-01, quoted in §1) — now a pick leg on the 📈 Bonde tab |
| D2 | a fabricated first-person sentence putting 25% in his mouth was served as his (sales.py, bonde.py, buyable_verdict.py reason + cite, rules_info, BondeBoard, SalesPanel, SepaCandidateCard, chartMaps, docs) | 25% relabelled THIS APP'S mid-tier; the value is unchanged |
| D3 | the character clause was called his | it is this app's (2026-06-16); the gate is unchanged (Rule #10) |
| D4 | "Sales Acceleration" was named as his EP catalyst | earnings acceleration is his (2007, 2010); sales acceleration is this app's read |
| D5 | a 2025 sentence he did not write was quoted | replaced by the two verbatim 2025 sentences |
| D6 | a fabricated first-person 5% sentence was quoted | his real sentence: "Sales/revenue should be up 5% or more." (2007) |
| D7 | 100% was framed as his sales tier | it is the boundary of his 2010 "Sales 100% plus but no earnings" CATEGORY |
| D8 | sales_led was framed as his | it is this app's read |
| D9 | "he never resolved QoQ vs YoY" | for EARNINGS he names both (2010); for sales he wrote no base; this app reads y/y |

Source guards: `test_SOURCE_GUARD_bonde_attribution_2026_09_20`
(`backend/tests/test_sepa_contracts.py`) and
`test_SOURCE_GUARD_sales_arithmetic_frozen_hash` (`backend/tests/test_sales.py`).
