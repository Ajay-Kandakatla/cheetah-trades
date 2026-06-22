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

## 6. Earnings-quality sell-risk (Minervini Ch.8, added 2026-06-08)

The diagnosis now carries the held name's **earnings-quality read** (`earnings_quality`,
from `sepa/earnings_quality.py` — see `docs/sepa/earnings_quality_methodology.md`) and a
derived `eq_sell_risk` list (`diagnosis._earnings_quality_sell_risk`). A heads-up fires
when the earnings story is deteriorating:

- inventory / receivables growing faster than sales — *piling up* (**p.155, 157**)
- a low-quality "beat" — EPS up on flat sales with no margin expansion (**p.143**)
- net margin contracting year-over-year (**p.146**)
- weak overall earnings quality — growth not sales-driven (**p.141**)

**This does NOT change the hold/sell verdict.** Minervini sells on **price** (broken
trend / violated stop, **Ch.12–13**), not on the fundamental story — `position_lens`
stays the authority. The earnings-quality risk is purely informational: it makes a
weakening earnings picture **visible before price confirms it**, so a subsequent price
break isn't a surprise. It is surfaced as a labeled "sell-risk heads-up," never as a
mechanical SELL/TRIM trigger. Test: `tests/test_portfolio_eq_risk.py`.

---

## 2026-06-13 — de-dup + Minervini-brain grounding

**The repetition (fixed).** The TIGHTEN-STOP/HOLD read was rendered three times on
a holding: the `PositionSignal` verdict line, its "why this read" expander, and a
third time inside `HoldingDiagnosis`. Now the verdict + reason appear **once**
(PositionSignal — verdict line shows `verdict · R · stage`, the reason lives only
in "why this read"). `HoldingDiagnosis` drops the duplicated P&L / verdict / fired
triggers / R-target ladder (all shown by the card header + PositionSignal) and
keeps only what's **unique**: the %-back-to-cost when underwater, and the
"hold until one fires" tripwire ladder (hard stop / 50-day / 200-day, **pp.295–296**).

**Brain-grounded write-up.** `_llm_writeup()` now injects retrieved Minervini
passages from the brain (BM25 over both books, `brain.retriever.search_multi`) so
the write-up's ONE hold/sell teaching point cites a **real page inline**
(e.g. _"you sell on a signal, not a clock [TLSW p.295]"_) instead of a hardcoded
page. The query set adapts to the verdict (TIGHTEN/REDUCE pulls risk-off /
partial-profit passages; EXIT pulls the 50/200-day violation rules).

- **Soft-fail, always.** `_book_passages()` returns `None` and never raises when
  the brain is absent / empty / erroring — the write-up falls back to the legacy
  prompt. Locked by `tests/test_diagnosis_brain.py` (negative + positive).
- **Condensed.** The system prompt now tells the model the page already shows the
  P&L/verdict/stop, so the write-up is ≤4 sentences (driver → what powered the move
  → one cited teaching point → what to watch), `max_tokens` 400→240.
- The write-up is cached per holding (`portfolio_diagnosis` Mongo); an existing
  holding shows its old write-up until **↻ Re-run** (force=true) or cache expiry.

## Stop is anchored to YOUR ENTRY, never widened (2026-06-22)

`position_lens._resolve_stop(entry, plan_stop, user_stop)` sets the stop the
hold/sell verdict measures against. The protective stop is **anchored to your
entry** — 7% below it (`entry × 0.93`, **p.311**) — and is only ever **raised**
as the stock advances, **never widened on a loser** (**pp.308-309**; "you sell on
a signal," **p.295**):

| Input | Stop used | Source |
|---|---|---|
| user supplied a stop | that stop (their explicit line) | `user` |
| auto, trail risen **above** entry stop (winner) | the trade-plan / trail stop | `trade_plan_trail` |
| auto, otherwise | `entry × 0.93` (the 7% floor) | `entry_7pct` |

i.e. the auto stop = **max(entry 7% stop, trade-plan stop)**.

**The bug this fixed.** The old code used the trade-plan stop *alone* — ≈7% below
the **current** price. For a holder who is underwater that sits **below** the entry
stop, so the cut line was re-derived from the falling price and a **breached entry
stop hid behind a HOLD verdict**. ARM held at **$445.43** (entry stop **$414.25**)
read **✓ HOLD** at **$404.69** because the displayed stop was **$382.39** (7% below
the falling price, ≈14% below entry). Anchoring to entry flips it to a breached
stop → **SELL** — the book's actual rule.

This keeps the verdict **deterministic and auditable** (the brain writes the
*explanation*, never the verdict). Behavioral + regression:
`tests/test_position_lens_stop.py`; contract:
`tests/test_sepa_contracts.py::test_position_lens_stop_anchored_to_entry`.
