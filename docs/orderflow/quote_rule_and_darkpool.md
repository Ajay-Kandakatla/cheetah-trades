# Quote-rule delta + off-exchange prints — methodology

_Added 2026-08-13. Ajay asked whether we can read the **order book** via the
Massive subscription: "Demand = orderbook + stoploss for smart money… I wanna
make sure I invest based on orders too that way its more deterministic."_

> **NOT a book method and NOT advice.** The classifier is Lee & Ready (1991), a
> standard academic microstructure method. The venue split is a provider fact.
> Neither feeds the SEPA score or any Auto-Pilot gate.

## The answer on the order book: we don't have one, and it wouldn't help much

Probed both keys on 2026-08-13:

| Endpoint | Result |
|---|---|
| `/v3/book/{sym}`, `/v3/depth/{sym}`, `/v3/level2/{sym}`, `/v3/orderbook/{sym}` | **404 — no such endpoint**, on the stocks *and* options keys |
| `/v3/quotes/{sym}` (NBBO, top of book) | **200** — full tick-by-tick bid/ask + sizes |
| `/v3/trades/{sym}` | **200** — every print with `exchange`, `conditions`, `trf_id` |

So **no L2/depth → no bookmap.** That is a hard limit of the data, not a
config problem.

It is also less of a loss than it looks:

- **Resting orders are not commitments.** Displayed size is overwhelmingly
  cancelled rather than executed; a bid disappears the moment it is leaned on.
- **Stops are not in any book.** A stop is a broker-side conditional. It does
  not exist as a resting order until it triggers — at which point it is already
  a market order. No feed, at any price, shows stop clusters.
- **Institutions hide from the book on purpose.** Dark pools, icebergs and
  VWAP/TWAP slicing exist precisely so size does not appear. The visible book
  therefore skews toward market makers and retail.

What *is* deterministic is an **executed print**: it happened, at a price, for
a size. Both features below are built on prints, not quotes-as-intent.

## 1. Quote-rule (Lee-Ready) trade classification

`orderflow/quotes.py`. Each print is matched to the last NBBO at or before its
timestamp (`merge_asof`, backward) and classified:

```
price >= ask      -> +1  buyer-aggressive (lifted the offer)
price <= bid      -> -1  seller-aggressive (hit the bid)
price >  mid      -> +1
price <  mid      -> -1
price == mid      ->  0  undecidable — falls back to the tick rule
```

We deliberately skip Lee-Ready's 5-second quote lag: it corrects for 1990s
reporting latency and is counterproductive on nanosecond SIP timestamps.

### Why it mattered

`tape.py` used the **tick rule** (uptick = buy) and documented the compromise:
"the proper quote rule needs the full NBBO stream — 5-10x the trade count, too
heavy to pull per page view." Measured, that turned out to be wrong about the
cost: CIEN's full regular-session NBBO is **56,611 rows, 2.8 s** — lighter than
its own tape (86,602 prints).

Measured impact on CIEN 2026-08-13:

| | tick rule | quote rule |
|---|---|---|
| session delta | **−518,754 sh** (−13.8%) | **−1,061,812 sh** (−28.3%) |
| agreement | — | **78.8%** of decided prints |

Same direction, but the tick rule understated net selling by more than **2×**.
Delta feeds the Tape tab's BUY/WAIT/AVOID checklist, so that error was live.

### The midpoint float bug (found by a test, 2026-08-13)

`(10.00 + 10.06) / 2 == 10.030000000000001` in binary float, so a print sitting
*exactly* at the midpoint compared as **below** mid and was classified a
**sell**. On a penny-spread tape that silently biases cumulative delta bearish.
On real CIEN data the fix reclassified **4,112 prints** out of "sell" and moved
session delta by ~106k shares. Guarded by `MID_EPSILON` and
`test_exactly_at_mid_is_undecidable`.

### Honesty about coverage

`classification` rides in the payload on every scan:

- `method` — `quote` (≥ `MIN_USEFUL_COVERAGE_PCT` 60% matched) · `mixed` ·
  `tick` (no NBBO) · `none`
- `coverage_pct`, `n_at_mid`, `n_fallback`, `tick_agreement_pct`

A failed or partial NBBO pull degrades to the tick rule **and says so** in the
UI badge. It never presents a tick-rule delta as a quote-rule number.
Pre/post-market prints keep the tick rule by design — that NBBO is wide, thin
and frequently crossed.

## 2. Off-exchange ("dark") print analytics

`orderflow/darkpool.py`. Every US trade reports to a lit exchange or a FINRA
facility. Per `/v3/reference/exchanges`, id **4** = "FINRA Alternative Display
Facility", `type=TRF`, `mic=XADF` — and it is the **only** id whose prints carry
a `trf_id` (verified: 24,669 of 24,669).

CIEN, 2026-08-13: **39.1% of volume printed off-exchange** (1.47M of 3.75M
shares), vs NYSE 36.7%, Nasdaq 8.3%.

### What it is NOT

That bucket mixes **dark-pool institutional crossing** with **wholesaler
internalization of retail flow** (Citadel Securities, Virtu). *The tape cannot
separate them.* So this module reports "off-exchange" and never "institutional
accumulation" — locked by `test_read_never_claims_institutional_intent`.

The one honest lever is **size**: retail internalization is small, so a
40,495-share / $18.4M off-exchange print is not retail. Hence `dark_blocks`
(≥10k shares **or** ≥$200k notional).

### `dark_in_band`

Off-exchange volume that printed *inside* a given price band — the intended
overlay on the demand zones from `supply_demand/demand_reentry.py`.

**Known limitation, stated because it bit during the build:** this reads one
session of tape. A demand band the stock is not currently trading in has no
prints today, so it correctly returns `total_shares: 0` — which is an absence
of data, not an absence of interest. It is only meaningful for a band price is
in or near. Multi-day accumulation per band would need a much heavier historical
pull and is not built.

## Surfaces

| Where | What |
|---|---|
| `/sepa/{sym}` → **Tape** tab | `quote rule` badge beside Big delta (hover for coverage + tick agreement); new **"Where it printed · off-exchange"** block with lit/dark split, block count, and the largest off-exchange prints |

Both are display + decision-support. `analyze_tape(trades, quotes=None)` keeps
its old single-argument behaviour, so every existing caller works unchanged
(`test_analyze_tape_without_quotes_still_works_and_flags_tick`).
