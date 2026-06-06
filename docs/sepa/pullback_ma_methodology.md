# Pullback to Moving Average — methodology

**Code:** `backend/sepa/pullback_ma.py` (`compute()` / `_evaluate_row()`)
**Cron:** `sepa.cli pullback-scan` → `run_and_persist()` (post-close weekdays)
**Endpoint:** `GET /sepa/pullback-ma`
**Page:** `frontend/src/pages/PullbackMa.tsx` (`/pullback-ma`)
**Contracts:** `backend/tests/test_pullback_ma.py` (behavioral) · `tests/test_sepa_contracts.py::test_pullback_ma_constants_locked` (source guard)
**Book:** Mark Minervini, *Trade Like a Stock Market Wizard* (2013) — **pp. 72, 79, 237–238**. (Printed page = repo-PDF page − 15.)

---

## 1. What this scanner is (the book)

A **pullback to the moving average** is Minervini's *natural reaction* — the
brief, shallow dip a healthy Stage-2 leader takes back toward its rising 50-day
line before resuming higher. He frames it as **tennis-ball vs. egg** action:

> "price reactions and pullbacks allow you to determine whether your stock is a
> tennis ball or an egg. He wanted to own tennis balls." — p.237

> "If the stock is healthy and under accumulation, the pullbacks will be **brief
> and will be met with support** that pushes the stock to new highs within just
> days, bouncing back like a tennis ball." — p.238

> "Volume should **contract during the pullback** and then expand as the stock
> moves back into new highs." — p.238

The 50-day moving average is the natural support level that pullback is measured
against, because a Stage-2 advance is *defined* by price holding above a rising
50/150/200 stack.

## 2. The defined-uptrend gate (Trend Template subset, p.79)

Every row must first be a genuine uptrending leader. We require the structural
subset of the eight Trend Template criteria (p.79):

| Gate (code) | Trend Template criterion | Page |
|---|---|---|
| `last_close > ma50` | #5 "the current stock price is trading above the 50-day moving average" | p.79 |
| `ma50 > ma150 > ma200` | #4 "the 50-day … is above both the 150-day and 200-day" + #2 | p.79 |
| `last_close > ma200` | #1 "price is above both the 150-day and the 200-day" | p.79 |

We deliberately do **not** require the full eight (no RS≥70 hard gate, no
30%-above-low). The page surfaces a *wider* watch tier than the strict SEPA
candidate list — RS shows as a column, and names that also pass full SEPA get a
`SEPA` flag. Rationale: a leader can be in a textbook pullback while its trailing
RS line has dipped during the reaction; gating it out would hide exactly the
setup the page exists to find. (p.79: "96 percent traded above their 50-day
moving averages" before their advance — the 50-day relationship is the load-
bearing one.)

## 3. The four columns

| Column | Definition (code) | Book basis |
|---|---|---|
| **Pullback %** | `(recent_high − last_close) / recent_high × 100`, where `recent_high` = max intraday high over the last 25 bars | "retraced from its recent high"; healthy reactions are shallow (pp.237–238) |
| **% from MA50** | `(last_close / ma50 − 1) × 100` | proximity to the 50-day support line; near 0 = testing support |
| **RS 3M** | 3-month price return (reuses `dual_momentum.return_3m`, i.e. `_return_pct(df, 63)`) | "in a definite uptrend before … big advances" (p.79) |
| **Vol Ratio** | `last_vol / mean(volume over last 20 bars)` | p.72: "volume **contractions** during normal price pullbacks"; < 1.0× = healthy |

## 4. Configured thresholds — NOT from the book

These operationalize the page; Minervini gives the *shape* (shallow, brief, dry,
supported) but not exact numbers. They live as named constants in
`pullback_ma.py` and are locked by a source-guard test so a silent edit trips
CI. **Tune here, not in scattered call sites.**

| Constant | Value | Meaning | Source |
|---|---|---|---|
| `BAND_TIGHT_MAX` | 5.0 | tight pullback < 5% | user spec (2026-06-05) |
| `BAND_MID_MAX` | 8.0 | mid 5–8%, deep > 8% | user spec |
| `VOL_HEALTHY_MAX` | 1.0 | vol ratio < 1× = contracting | book p.72 (the < 1× idea); the exact 1.0 cut is configured |
| `VOL_AVG_LOOKBACK` | 20 | "20-day average" volume | user spec |
| `RECENT_HIGH_LOOKBACK` | 25 | window defining the "recent high" | configured (book says "recent high", no window) |
| `PULLBACK_ZONE_CEILING` | 8.0 | include names within +8% above the 50-day | configured (the "pulled back *toward* the line" requirement) |
| `MIN_PULLBACK_PCT` | 0.5 | must have actually retraced | configured |

If Ajay wants different bands or windows, change the constant and update the
guard test in the same commit.

## 5. Ranking (heuristic, not a book formula)

Rows sort by an **actionability** score. The score itself is a heuristic, but
every input is book-grounded: proximity to the 50-day line (most actionable
zone), a tight/brief pullback (tennis ball, pp.237–238), contracting volume
(p.72), and a still-positive 3-month trend (p.79). It is a *display ordering*,
never a buy signal.

## 6. Data flow (no money-path-scan change, no second universe)

```
4:30pm ET fast-scan ──writes──▶ latest.json  (scanner.load_latest)
                                     │
4:50pm ET  sepa.cli pullback-scan ──┤ reuses universe + 50/150/200 MAs + RS
                                     │ recomputes pullback/vol/return from the
                                     ▼ same Mongo-cached bars (prices.load_prices)
                              latest_pullback.json  (shared cheetah-scans volume)
                                     │
GET /sepa/pullback-ma ───serves──────┘  (falls back to on-the-fly compute())
```

It mirrors `dual_momentum.py` exactly — a pure *derivation* of the existing
scan. `backend/sepa/scanner.py` and the daily scan are untouched (Rule #2).

## 7. Not advice

The page is educational/informational. A pattern that worked before does not
guarantee future results; nothing here is a personalized buy/sell
recommendation.
