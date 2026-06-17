# Trade Verdict — Minervini SEPA × Pradeep Bonde (Stockbee) composite

**Surface:** SEPA ticker detail page → **Analysis** tab (lead panel).
**Code:** `frontend/src/lib/tradeVerdict.ts` (pure, unit-tested in
`tradeVerdict.test.ts`) → rendered by `frontend/src/components/TradeVerdictPanel.tsx`.
**Type:** frontend-only synthesis over fields the scan payload already carries
(`trend.checks`, `rs_rank`, `volume.*`, `day_change_pct`, `stage.dist_200_pct`,
`dual_momentum.*`, `sell_signals.*`, `group_rs_rank`/`group_leader`). No backend
change, no extra fetch. If we ever want to *filter or alert* the scanner on this
verdict, promote the gate to `backend/sepa/`.

This panel is a **timing** verdict (buy & sell). It sits above the existing
**fundamental gate** (`buy_verdict` — Minervini buyable qualifier p.79 + Bonde
*sales* test), which is retained as supporting detail.

## The two frameworks

### 1. Mark Minervini — SEPA / Trend Template
*Trade Like a Stock Market Wizard*, the Trend Template.
The checks shown (all must hold for the Minervini leg to be a buy):

1. Price > 150-day MA **and** > 200-day MA
2. 50-day MA > 150-day MA > 200-day MA (stacked)
3. 200-day MA trending up ≥ ~1 month
4. Price ≥ 30% above the 52-week low
5. Price within 25% of the 52-week high
6. RS rating ≥ **70** (preferably ≥ **80**) — `RS_MIN` / `RS_PREFERRED`
7. Actionable **tight VCP / pivot breakout on volume** (`volume.high_vol_breakout`
   or `pocket_pivot`, in the buy zone)

`minervini = buy` when 1–6 hold **and** 7 fires; `watch` when 1–6 hold but no
fresh breakout; `avoid` when price is below the 150/200-MA or the name is past
Stage 2.

### 2. Pradeep Bonde — Stockbee
Episodic Pivots (2010), the 4% breakout scan, momentum bursts. Checks:

1. **Episodic Pivot** — earnings/news gap-up on a volume surge
   (`high_vol_breakout` + RVOL ≥ `BONDE_BREAKOUT_RVOL` = 1.5×; flagged
   "earnings-driven" when a catalyst surprise is present)
2. **4% breakout** — daily gain ≥ `BONDE_FOURPCT_GAIN` (4%) on volume
   > 1.5× average
3. **Momentum burst** — ≥ `BONDE_MOM_BURST_1W_PCT` (8%) in a week, or
   ≥ `BONDE_MOM_BURST_1M_PCT` (15%) in a month (8/10/15%+ runs)
4. **Constructive distance from MAs** — not extended (`dist_200_pct` <
   `EXTENDED_DIST_200_PCT` = 100% above the 200-MA)
5. **Industry / sector strength** — group leader / top of group RS
   (`group_leader`, `group_rs_rank`)
6. **No anti-thesis sell signal** — from `sell_signals`: close below 200-MA,
   50-MA breach on high volume, stop breached, down >10% from entry, climax
   run, or `action ∈ {SELL, REDUCE}` / `severity ≥ 1`

`bonde = avoid` on any **hard** sell signal; `buy` when a bullish trigger fires
**with** group strength and no soft caution; otherwise `watch`.

## Composite rule (strict 3-state)

- **AVOID** if Minervini structure is broken (below 150/200-MA, or past Stage 2)
  **or** a Bonde **hard** sell signal fires. An anti-thesis from *either*
  framework dominates — *even if the other framework is a buy*. (This is the
  locked edge case: Minervini passes but a Bonde sell fires → **not** a buy.)
- **BUY** only if **both** legs independently confirm an actionable buy.
- **WATCH** if the trend template is intact (1–6 + RS) but there's no confirmed
  buy trigger, or only a soft distribution caution.
- **NO DATA** when there's no trend-template result yet.

The `why` string names which framework(s) drove the call.

## Thresholds (published, not invented)

| Constant | Value | Source |
|---|---|---|
| `RS_MIN` / `RS_PREFERRED` | 70 / 80 | Minervini Trend Template |
| `BONDE_FOURPCT_GAIN` | 4.0% | Stockbee "4% breakout" scan |
| `BONDE_BREAKOUT_RVOL` | 1.5× | Stockbee breakout volume filter |
| `BONDE_MOM_BURST_1W_PCT` / `_1M_PCT` | 8% / 15% | Stockbee momentum bursts |
| `EXTENDED_DIST_200_PCT` | 100% | extended-from-MA caution |

## Notes / limits

- The Episodic Pivot detection approximates the intraday **gap** with
  `high_vol_breakout` + RVOL (no intraday gap field in the payload); the
  earnings-driven flag is set when a catalyst surprise is present.
- This verdict is **timing**; pair it with the fundamental gate (sales/earnings
  quality) beneath it. Bonde's calls are momentum signals, not advice.
