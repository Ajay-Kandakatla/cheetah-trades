# Per-Stock Supply / Demand Screen — Methodology & Spec (2026-05-31)

**Why this exists.** The Supply/Demand page used to be a curated dependency
atlas + sector tabs — it never measured what Minervini actually calls "supply
and demand," and it never saw the broad ~3,700-name universe. This screen adds
the book-faithful, per-stock read over the whole universe.

- **Code:** `backend/supply_demand/stock_supply_demand.py`
- **Endpoint:** `GET /supply-demand/stocks`
- **Source of truth:** Mark Minervini, *Trade Like a Stock Market Wizard*
  (2013), Chapter 10 "A Picture Is Worth a Million Dollars", **pp. 204-210**.
- **Isolation:** reuses the pure functions `sepa.volume.analyze` /
  `sepa.vcp.detect` + cached bars. It does **not** touch the contract-locked
  SEPA scanner.

---

## 1. The four forces (book → code)

| Force | What it measures | Book | Code field |
|---|---|---|---|
| **Overhead supply** *(new)* | volume that traded ABOVE the current price over the last year — "trapped buyers … now sitting with a loss … look for a rally to sell" | p.204-205 | `overhead_supply_pct` |
| **Distance from 52w high** | proximity to new-high ground — "a stock hitting a new high has no overhead supply to contend with" | p.206-207 | `pct_below_52w_high` |
| **Supply absorption** | volume drying up / price tightening — "a significant contraction in volume … signals supply has stopped coming to market" | p.205-206 (Fig 10.8) | `is_drying_up`, `vol_dryup`, `n_contractions`, `volume_drying` |
| **Demand** | accumulation, money-flow inflow, breakout/pocket-pivot volume | p.194, 203 | `accumulation_strength`, `up_down_vol_ratio`, `cmf_signal`, `high_vol_breakout`, `pocket_pivot` |

> Deep corrections are explicitly flagged failure-prone: a stock down 50-60% off
> its high "must contend with a large amount of overhead supply" (p.210).

## 2. The new metric — Overhead Supply %

```
overhead_supply_pct = 100 × Σ(volume[i]  for i in last 252 bars where close[i] > today_close)
                            ─────────────────────────────────────────────────────────────────
                                       Σ(volume[i]  for i in last 252 bars)
```

- **0** → at/above the trailing-year high: no volume traded higher, **no overhead
  supply** (p.206).
- **High (≥40)** → most of the past year traded above the current price: heavy
  trapped supply / resistance overhead.

It is the direct codification of "the trapped buyers above the current price."
Simple, close-based, robust. (Possible future refinement: weight by distance
above, or use typical price (H+L+C)/3. Not needed for v1.)

## 3. State classification (the headline read)

Evaluated top-to-bottom; first match wins.

```
SUPPLY    if  accumulation_strength == "distributing"
          OR  overhead_supply_pct ≥ 40   OR   pct_below_52w_high ≥ 50   (deep correction, p.210)

DEMAND    if  (overhead_supply_pct ≤ 15 OR pct_below_52w_high ≤ 15)     (clear runway)
          AND (accumulation in {strong, accumulating}  OR breakout OR volume drying)

CHURNING  otherwise (near highs but no active demand signal, or mixed)
```

Accumulation **is** demand, so it qualifies on its own — drying/breakout are
bonuses, not requirements (an earlier draft wrongly required drying and mislabeled
AAPL-at-new-high as churning).

## 4. Demand score (0-100, for ranking the universe)

Additive so it spreads instead of saturating at 100:

| Component | Max | Rule |
|---|---|---|
| Overhead supply | 30 | `30 × clamp(1 − overhead/40, 0, 1)` (less = better; unknown → 15) |
| Distance from 52w high | 20 | `20 × clamp(1 − pct_below/40, 0, 1)` (nearer = better; unknown → 10) |
| Demand / accumulation | 25 | strong 25 · accumulating 15 · neutral 5 · distributing 0 |
| Money flow (CMF) | 10 | inflow 10 · neutral 5 · outflow 0 |
| Absorption + breakout | 15 | drying +8 · breakout/pocket +7 |

## 5. Thresholds (locked)

`stock_supply_demand.py` constants — our codification (book gives concepts, not numbers):

| Constant | Value | Meaning |
|---|---|---|
| `LOOKBACK_DAYS` | 252 | overhead-supply / 52w window |
| `OVERHEAD_LOW_PCT` | 15 | ≤ this → clear runway |
| `OVERHEAD_HEAVY_PCT` | 40 | ≥ this → supply-burdened |
| `DEEP_CORRECTION_PCT` | 50 | ≥ this % below 52w high → deep correction (p.210) |
| `NEAR_HIGH_PCT` | 15 | within this % of the 52w high → near-high ground |

## 6. Worked examples (live, 2026-05-31)

| Symbol | overhead% | % below 52w high | accum | state | score | why |
|---|---|---|---|---|---|---|
| AAPL | 0.4 | 0.1 | strong | **demand** | 84.7 | new high, no overhead, accumulating |
| CVGI | 6.3 | 6.7 | strong | **demand** | 84.9 | clear runway + accumulation |
| MU | 0.0 | 0.0 | neutral (breakout) | **demand** | 72.0 | new high breaking out on volume |
| NVDA | 6.3 | 10.4 | neutral | **churning** | 50.1 | near high but no active demand signal |
| SMCI | 27.5 | 24.1 | accumulating | **churning** | 49.3 | meaningful overhead to work through |
| WBA | 3.5 | 7.3 | distributing | **supply** | 50.7 | active distribution |
| HOOD | 57.0 | 38.1 | accumulating | **supply** | 33.0 | heavy overhead / deep correction (p.210) — supply wins despite recent buying |

> CVGI scores high *here* (genuine demand/low-overhead) yet is still **not**
> `is_buyable` in the SEPA scanner (its breakout lacks volume, p.203). The two
> views are complementary: this page reads the supply/demand balance; the
> scanner gates the actual buy.

## 7. Performance & caching

- The broad pass loads ~3,700 cached price frames and runs `volume.analyze` +
  `vcp.detect` each — seconds of CPU, so it's cached `_CACHE_TTL_SEC` (3h) and
  warmed daily by cron. First cold call is slow; the endpoint runs in a thread
  (`asyncio.to_thread`) so it never blocks the event loop.
- `min_dollar_vol` (default $3M/day) drops illiquid noise.

## 8. Contract

`backend/tests/test_supply_demand.py` locks the overhead-supply metric
(new-high → 0, deep-correction → high, monotonic) and the state precedence
(distribution → supply; clear-runway + accumulation → demand).

## 9. Demand Zones (companion — the price BAND)

This screen answers *whether* a name is in demand (a state). The companion
**Demand Zones** feature answers *where* — it renders each name's most-recent
consolidation **base** as a price band (floor `base_low` → pivot
`pivot_buy_price`), classified by correction depth (constructive 8-35% / deep /
failure-prone ≥60%, Minervini p.210-211), with where the current price sits
relative to it (in / above / below). It is derived from the same contract-locked
`sepa.vcp.detect` and is **descriptive, not advice**.

- **Code:** `backend/supply_demand/demand_zones.py`
- **Endpoint:** `GET /supply-demand/demand-zones`
- **Page:** `/demand-zones` (leaderboard + day-trading universe)
- **Spec + page cites:** `docs/supply_demand/demand_zones_methodology.md`
- **Contract:** same file — `tests/test_supply_demand.py` (depth bands, geometry,
  base→zone mapping, source guard `vcp_mod is sepa.vcp`).
