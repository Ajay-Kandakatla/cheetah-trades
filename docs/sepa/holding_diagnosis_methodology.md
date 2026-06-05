# Holding diagnosis — personal P&L + hold-until-signal

**Code:** `backend/portfolio/diagnosis.py` (`_position_read` → `_shape_position`, `diagnose(entry=…)`) · reuses `backend/sepa/position_lens.py` (the Minervini sell engine) · `frontend/src/components/HoldingDiagnosis.tsx`
**Contracts:** `backend/tests/test_holding_diagnosis_personal.py` (behavioral, pure `_shape_position`)
**Book:** Mark Minervini, *Trade Like a Stock Market Wizard* (2013) — printed pages; the repo PDF (`docs/TradeLikeaStockMarketWizard(2013).pdf`) is offset **+15**.
**Status:** added 2026-06-04 (Ajay: *"make it personal to my P/L … tell me how long to hold by Minervini's principles, and what accumulation needs to continue."*)

---

## 1. The problem

The card read **"LRCX surged +6.49% (5d)"** while the user was **down** on the
position. The 6.49% is the *stock's* 5-day move; it is not the user's trade. A
holding read must answer **"how is MY position doing, and how do I hold it?"** —
anchored to the user's **cost basis**, not an arbitrary window.

## 2. What it computes (all from the user's entry)

`diagnose(symbol, entry=<per-share cost>, shares=…)` calls
`position_lens.evaluate(symbol, entry, shares)` — the **same** engine the Portfolio
hold/sell card uses — and shapes it into a `position` block:

| Field | Meaning |
|---|---|
| `gain_pct`, `gain_dollars` | change **since the user's entry** (not the 5d move) |
| `r_multiple` | open profit in **R**, where `R = entry − stop` |
| `to_breakeven_pct` | how far price must **rise** to reach cost (only when underwater) |
| `verdict`, `verdict_summary` | HOLD / TIGHTEN / REDUCE / EXIT from `position_lens` |
| `targets` | R1/R2/R3 with the **% from here** |
| `tripwires` | the exits to **watch**, nearest-first, each with live distance |
| `fired` | any sell signal **already** firing |

The cache is keyed **per cost basis** (`{SYM}|{entry}`) so two owners at different
costs get different reads.

## 3. The Minervini principles it encodes (with page cites)

The user asked *"how long do I hold?"* Minervini's answer is **not a date** — you
hold a Stage-2 advance until a **sell signal** fires, raising the stop as it climbs:

- **Hold the Stage-2 advance; raise the stop as it advances** — *"Once a stock
  advances, the sell point should be raised to protect your profit with the use of
  a trailing stop or back stop."* — **p.295** ("The Initial Stop-Loss").
- **Never let a winner turn into a loser** — *"Once a stock amasses a … gain that
  is a multiple of your stop loss, you should rarely allow that position to turn
  into a loss … move up your stop loss to breakeven."* — **p.296** ("Selling at a
  Profit"). This is the `up_3r_move_stop_to_breakeven` trigger in `position_lens`.
- **Sell into strength, or at the first sign of weakness** — the two sell modes —
  **p.296**.
- **Risk < average gain** — *"always keep your risk at a level that is less than
  that of your average gain"* — **p.298**. This is why R-multiples (not raw %) frame
  the position.
- **Stage 2 is the only hold zone**; Stage 3 = topping/distribution, Stage 4 =
  decline → sell / stand aside — **pp.69–76** (stage analysis), Trend Template
  **p.79**.

The **tripwires** map to these: `Hard stop` (p.296), `50-day line` lost on volume
(distribution, Ch.13), `200-day line` / stage roll = Stage-2 trend broken (pp.69–76,
p.295). These are surfaced, **not invented** — `position_lens` already evaluates the
firing logic (Ch.12–13); this layer only lists them with distances.

## 4. "How much more accumulation, at what rate?" — what we will and won't say

Minervini supports an advance with **accumulation** (up days on heavier volume than
down days; buy the breakout on volume, **p.203**). The book gives a *signature*, not
a numeric **rate**, and we do **not** fabricate one. The read shows the **measurable
accumulation to keep seeing** — `up_down_vol_ratio`, `accumulation_days_25`,
`pocket_pivots_12d`, RS holding — and frames progress toward the next R-target. It
makes **no price or date forecast** and gives **no buy/sell advice** beyond the
book's mechanical rules. Analytical gauge, not advice.

## 5. What does NOT change

- `position_lens` sell logic and its Ch.12–13 grounding — unchanged; this layer
  only *reads* it.
- The scanner gates (`is_buyable` / `is_candidate`), VCP, stage, distribution — untouched.
- Stock-only diagnosis (no `entry`) behaves exactly as before — the `position`
  block is simply absent.
