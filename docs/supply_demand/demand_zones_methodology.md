# Demand Zones — Methodology & Spec (2026-06-07)

**Why this exists.** The per-stock supply/demand screen tells you *whether* a name
is in demand (a state). It never said *where* the demand zone is — the actual
price band. This adds the band: each name's most-recent consolidation **base**,
rendered floor → pivot, for the leaderboard + day-trading universe.

- **Code:** `backend/supply_demand/demand_zones.py`
- **Endpoint:** `GET /supply-demand/demand-zones`
- **Page:** `/demand-zones` (frontend `DemandZonesPage.tsx`)
- **Source of truth:** Mark Minervini, *Trade Like a Stock Market Wizard* (2013),
  Chapter 10 "A Picture Is Worth a Million Dollars", **pp. 197-213**.
- **Isolation:** the band is read straight off the contract-locked
  `sepa.vcp.detect`. This module introduces **no new base-detection thresholds** —
  only a depth classifier and the price-vs-band geometry. It does **not** touch
  the SEPA scanner.

> **Not advice.** This is a structural read of where demand previously absorbed
> supply. It is **not** a buy signal and **not** personalized advice.

---

## 1. What a "demand zone" is (book → code)

A base is "the law of supply and demand at work" as shares move from weak holders
to strong ones (p.205). The zone is that base's price band:

| Edge | Meaning | Book | Code field (from `vcp.detect`) |
|---|---|---|---|
| **zone_low** | base floor — where supply is absorbed and "bottom fishers achieve healthy gains"; strong-holder accumulation | p.205, Fig 10.8 | `base_low` |
| **zone_high** | the pivot — "the line of least resistance has been established" (p.206); the advance begins on volume above it | p.203, p.206 | `pivot_buy_price` |
| **base_high** | left-side high of the base (start of the correction) | p.205 | `base_high` |

The whole point of waiting for the base: "If the stock's price and volume don't
quiet down on the right side of the consolidation, chances are that supply is
still coming to market and the stock is too risky" (p.206).

## 2. Depth class — the validity gate (p.210-211)

The book bounds which corrections are worth trading:

> "Most constructive set-ups correct between 10 percent and 35 percent." …
> "I rarely buy a stock that has corrected 60 percent or more; a stock that is
> down that much often signals a serious problem." (p.211)

```
shallow        base_depth_pct < 8        (barely a base — flat/low-vol drift)
constructive   8 ≤ depth ≤ 35            (the book's constructive band, p.211)
deep           35 < depth < 60           (beyond ideal; higher failure risk)
failure_prone  depth ≥ 60               (rarely buyable, p.210-211)
```

The `8` shallow floor mirrors `sepa.vcp`'s existing `good_depth` lower bound (our
codification — the book gives the concept, the exact number is ours). The `35`
and `60` boundaries are the book's, cited above.

## 3. Where price sits vs the band (pure geometry)

```
in      zone_low ≤ price ≤ zone_high     pulled back into the base (actionable)
above   price > zone_high               broke out / extended; zone is support below
below   price < zone_low                base broke down
```

- `distance_to_zone_pct` — signed: `0` inside · `+` above the pivot · `-` below
  the floor.
- `zone_position_pct` — `0` at the floor → `100` at the pivot (only when inside).
- `pulled_back` — `in_zone AND depth_class ∈ {shallow, constructive}` — the
  cross-link case to the leaderboard (a leader that has pulled back into a still-
  valid base).

## 4. Universe

The two lists the user asked for, deduped (source = `leaderboard | day | both`):

- **Leaderboard** — `sepa.leaderboard.leaderboard(n=30)["leaders"]`.
- **Day-trading watchlist** — `daytrading.api.DEFAULT_WATCHLIST`.

~40 names, so the screen recomputes in seconds and is cached in-process 3h.

## 5. Locked constants

`demand_zones.py` — locked by `tests/test_supply_demand.py`:

| Constant | Value | Meaning |
|---|---|---|
| `DEPTH_SHALLOW_MAX` | 8.0 | `<` → shallow |
| `DEPTH_CONSTRUCTIVE_MAX` | 35.0 | `8-35` → constructive (p.211) |
| `DEPTH_FAILURE_PRONE` | 60.0 | `≥` → failure-prone (p.210-211) |
| `NEAR_PCT` | 8.0 | within this % of the band → counted "near" |
| `LEADERBOARD_N` | 30 | leaderboard names pulled |

## 6. Contract

`backend/tests/test_supply_demand.py` locks:
- the depth-class bands + the `8 / 35 / 60` thresholds (p.210-211);
- the price-vs-band geometry (in / above / below, signed distance, position);
- the behavioral mapping `base_low → zone_low`, `pivot_buy_price → zone_high`,
  and `pulled_back` only for an in-zone constructive base;
- the **source guard**: `demand_zones.vcp_mod is sepa.vcp` — the band must derive
  from the contract-locked detector, never a reimplementation.

## 7. Honesty note

These are **our** zones from **our** book-faithful base detection — not any third-
party indicator's exact bands (e.g. a TradingView supply/demand script draws from
its own swing rules, which we don't have). When a name has no discernible base,
the row is flagged `has_zone: false` rather than inventing a band.
