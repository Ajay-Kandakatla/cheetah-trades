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

**Crucially**, it is anchored ONLY to the sales numbers Bonde documents in **his
own writing**, and it deliberately **avoids** the tighter figures widely
attributed to him (30% / 39% two-quarter / "MAGNA 53+" / triple-digit-as-primary)
— a fact-checked research pass found those come from third-party platforms
(Deepvue, TradeZella, TraderLion) and **failed adversarial verification**.

## 2. Bonde's documented sales numbers (what we anchor to)

| Threshold | Meaning | Source |
|---|---|---|
| sales **≥ 5%** | his floor — *"I take 5%"* | Stockbee, *How to Trade Earnings* (2007) |
| **25%+** | his preferred/ideal — *"you can use 25% plus"* | Stockbee (2007) |
| **100%+** | his *"Sales 100% plus"* Episodic-Pivot category (high sales even with no earnings) | Stockbee, *What are Episodic Pivots* (2010) |
| **Sales Acceleration** | a named EP catalyst (growth rate rising) — no number attached | Stockbee EP process-flow (2014) |
| *"revenue growth that investors focus on"* | sales weighted alongside/over profitability | Stockbee (Sept 2025) |

Sources: `stockbee.blogspot.com/2007/03/how-to-trade-earnings.html`,
`/2010/02/what-are-episodic-pivots-and-how-to.html`,
`/2014/07/my-process-flow-for-episodic-pivots-ep.html`,
`/2025/09/find-young-episodic-pivots.html`.

### Honesty notes (from the verified research)
- Bonde's EP **entry** is a **price/volume** gate (`c/c1>1.04 and v>3*avgv50.1 and v>=300000`), NOT a sales %. Sales is the **fundamental confirmation** examined *after* a move — so this score is a **conviction/confirmation layer**, not a trigger.
- In his **2007/2010** core posts, **earnings** is the primary gate (100%+ QoQ doubling) and sales is confirming. In **2025** he leans sales-first. Both are his genuine words → we treat sales as a **standalone signal**, not "the one rule."
- The **"sales is harder to manipulate than earnings"** rationale was **NOT** found in any verified Bonde source (it's general sales-investing folklore) — so the code/doc does not attribute it to him.
- **QoQ vs YoY:** Bonde's *"up 100% quarter over quarter"* / *"sales up 5%"* phrasing is ambiguous (a commenter on his post raised this; he never resolved it). We compute **YoY** (latest quarter vs the same quarter a year earlier) to match the app's existing `canslim` metrics and the more common reading. Documented here so it can't be mistaken for a settled Bonde rule.

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
5/25/100 anchors against drift to the unverified 30/39% figures.
