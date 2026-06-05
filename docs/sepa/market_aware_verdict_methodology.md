# Portfolio hold/sell — market-regime defensive overlay

**Code:** `backend/sepa/position_lens.py` (`_posture_from`, `_market_posture`, the `market_risk_off` trigger in `evaluate`) · endpoint `GET /market/posture` · `frontend/src/components/PortfolioPostureBanner.tsx`
**Contracts:** `backend/tests/test_position_lens_market.py`
**Books:** William O'Neil, CANSLIM — **'M' = Market Direction**: ~3 of 4 stocks follow the general market, so you go defensive when it tops. Mark Minervini, *Trade Like a Stock Market Wizard* — trade **with** the market trend (Ch.5) and **reduce exposure** in weak markets (Ch.12–13).
**Status:** added 2026-06-05 (Ajay: *"be a cautious/defensive trader — the portfolio's hold/sell should factor the whole market being red, not just per-stock signals"*).

---

## The gap it closes

`position_lens.evaluate()` judged each holding purely **bottom-up** — its own
Minervini sell signals (hard stop, close below the 200-day, Stage roll to 3/4,
climax, distribution, down-10%-from-entry) plus that name's 13F flow, Chaikin money
flow, and **options sentiment (SOIR)**. It had **zero awareness of the broad
market**, so it read HOLD on a clean leader even when the entire tape was red.

## The posture (top-down)

`_market_posture()` combines three reads we already compute:

| Read | Source |
|---|---|
| Macro regime (war / oil / rates / breadth / distribution) | `macro_risk.get_market` |
| Market trend confirmation — is the **S&P AND/OR Nasdaq** passing the 8-point Trend Template | `market_context.market_state` |
| Breadth — % of the scanned universe red today | latest scan |

→ **`risk_off`** (regime high/severe, **or** S&P/Nasdaq not confirmed, **or** ≥65%
red), **`caution`** (elevated / ≥55% red), or **`constructive`**.

## The overlay (what changes)

In a **risk-off** tape, `evaluate()` appends a `market_risk_off` **TIGHTEN** trigger:

- A **clean leader**: HOLD → **TIGHTEN** (raise the stop — the defensive baseline).
- A name **also showing weakness** (below the 50-day, distribution, bearish options,
  Stage drift, down from entry → its own TIGHTEN trigger) stacks with the market one
  and the existing **tighten-count rule** escalates the verdict to **REDUCE**.

It **never force-SELLs a clean leader** — Minervini holds names that aren't
violating; it makes the whole book defensive and steps the verdict up. Options
(SOIR) were already a trigger; this adds the **missing top-down market layer**.

## What does NOT change

- The per-stock Minervini sell signals (Ch.12–13) — untouched; this is **additive**.
- It's an analytical gauge, **not advice** — the banner states the book's defensive
  playbook (tighten stops, partial profits, raise cash) and the verdict, the user decides.
- `GET /market/posture` exposes the posture; `PortfolioPostureBanner` explains why
  the cards below stepped to TIGHTEN/REDUCE.
