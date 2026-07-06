# Order Flow ("Tape") — methodology

**Status: industry-standard techniques, NOT book-cited.** Requested by Ajay
2026-07-06 ("order flow, bookmap, prints, trade flash, big delta and EMAs,
demand and supply and GEX") after seeing the strategies in a WhatsApp group
claiming ~70% accuracy. No source PDF was provided, so per Rule #1 every
definition below is the standard industry one, every threshold is a
**configured house value** (like `supply_demand/price_zones.py`), and the
claimed accuracy is **measured, not assumed** — see the forward ledger.

Module: `backend/orderflow/` · UI: ticker page → **Tape** tab ·
Endpoints: `GET /orderflow/{symbol}`, `POST /orderflow/{symbol}/scan`,
`GET /orderflow/ledger/accuracy`

## Data reality (what our keys can and cannot see)

| Input | Source | Notes |
|---|---|---|
| Raw trade prints | Massive `/v3/trades/{sym}` (Stocks Advanced) | full session 04:00–20:00 ET, paginated 50k/page, cap 24 pages → `truncated` flag |
| 1-min bars | Massive aggs via `daytrading/data.py` | volume profile + intraday EMAs |
| Daily bars | `sepa/prices.py` | trend gate fallback + ledger grading |
| Zones | `supply_demand/price_zones.py` (reused) | swing-cluster supply/demand bands |
| GEX / max pain | `options/opex.py` (reused) | context only, never in the verdict |
| **Level-2 order book** | **NOT AVAILABLE** | Massive sells no stock depth feed → no bookmap. Substitute: volume profile (traded volume can't be spoofed; resting orders can). |
| **NBBO quote stream** | too heavy (5-10× trade count) | → tick-rule classification instead of the quote rule |

## Trade classification — the tick rule

Uptick ⇒ buyer-aggressive (+1), downtick ⇒ seller-aggressive (−1), zero-tick
carries the last direction; leading unchanged prints are unknown (0), excluded
from delta but counted in totals. Literature puts tick-rule agreement with the
full quote rule at **~75–80%** — this error bar is inherited by delta, big
prints, and bursts, and is stated on the page.

## Derived reads (configured house values)

| Read | Rule |
|---|---|
| **Cumulative delta** | Σ(size × side); per-minute series; `late_delta` = last 30 min |
| **Big prints** | notional ≥ max($100k, day's 99.9th-pct notional); top 20 by $ |
| **Trade-flash bursts** | 10s windows with ≥ $250k, ≥ 15 prints, ≥ 75% one-sided; top 10 |
| **Volume profile** | 40 buckets over the session range; POC = heaviest; 70% value area expanding from POC |
| **Intraday EMAs** | EMA9 vs EMA21 on 5-min RTH closes |
| **Daily trend gate** | SEPA scan qualifier or Stage 2; fallback close > SMA50 ∧ close > EMA21 ∧ EMA21 rising 5 bars; **no data ⇒ fail (safe default)** |

## The verdict table (fixed — no other rule may decide)

```
AVOID  if trend_daily fails
AVOID  if zone == caution AND delta fails
BUY    if trend_daily ∧ ema_intraday ∧ delta ∧ (big_buyers ∨ zone favorable)
       ∧ zone != caution
WAIT   otherwise
BUY on < 500 prints ⇒ WAIT (thin-tape gate)
Before 09:45 ET the PRIOR session is scanned (premarket tape is noise).
```

- `delta` passes when session delta > 0 **and** last-30-min delta ≥ 0.
- `big_buyers` passes when big-print buy $ ≥ 1.25× sell $ (≥ 1 big buy print).
- `zone` favorable/neutral/caution comes from the price-zones `entry_read`.
- **GEX is context only** — pin/amplify + max pain shown, never counted
  (single-name gamma sign can invert; see `opex_methodology.md`).

## Forward accuracy ledger (`orderflow/history.py`)

Every computed snapshot records one observation per (symbol, ET date,
verdict) — all three verdicts, so BUY has a control group. Cron
(17:10 ET weekdays) grades against daily closes: `fwd_1d` at T+1, `fwd_5d`
backfilled at T+5; hit = close in the verdict's direction (BUY up, AVOID
down; WAIT tracked, not scored). Entry = last tape price at scan time.
Gross close-to-close, no costs, never pruned. `GET /orderflow/ledger/accuracy`
reports per-verdict hit rates with n — **read the n before the %**.

## Honesty caveats (also shown in the UI)

1. Tick rule ≈ 75–80% of the quote rule — delta is an estimate.
2. No Level-2 ⇒ no bookmap; the volume profile shows where volume *traded*,
   not where orders *rest*.
3. Order flow is intraday-noisy; the daily SEPA gate exists precisely so this
   page can never fight the main system.
4. The WhatsApp 70% is unverified until OUR ledger shows it. Decision-support,
   not advice.
