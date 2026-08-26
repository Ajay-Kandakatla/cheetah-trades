# Falling-knife watch (portfolio/knife_watch.py)

Ajay 2026-08-26: "Can you help add a cron job to track these and let me
know if there are any falling knives."

## Definition

A held position is a **falling knife** only when BOTH sides agree — the
same two-sided gate the Deep Demand and Gabbar boards have used since
2026-08-25:

| Side | Source | Condition |
|---|---|---|
| Business broken | `sepa/sales.py` Bonde tiers (5/25/100% anchors) | tier ∉ `BONDE_PASS_TIERS` (i.e. declining / weak) |
| Price being sold | `sepa/volume.py` | `cmf_20 ≤ CMF_OUTFLOW_THRESHOLD` (−0.10) |
| | `sepa/volume.py` (TLSW pp.71–76, count-of-days) | `up_down_vol_ratio ≤ DIST_RATIO_THRESHOLD` (0.70) |
| | `sepa/stage.py` (TLSW pp.65–77) | Stage 4 markdown |

One-sided verdicts are recorded but never pushed:
`WATCH_SALES` (business broken, chart clean), `PULLBACK` (sold, business
growing), `CLEAN`. Unknown sales = `business: unknown`, **never** flagged.

## Delivery

- Cron: 16:45 ET Mon–Fri (after the 16:30 fast-scan close refresh and
  16:40 drop-attribution — all three read the same daily bar).
- Push kind: `position_alert` — the standing keep-set gains no new kinds.
- Dedup: one push per ticker per ET day (`portfolio_knife_state`).
- Complements `sepa.position_lens` (stops / Ch.12–13 sell signals, every
  5 min RTH); this adds the sales dimension position_lens lacks.

Thresholds are IMPORTED, never re-declared. Tests:
`tests/test_knife_watch.py` (standalone importlib load — the portfolio
package `__init__` doesn't evaluate on host py3.9).
