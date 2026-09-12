# Market-cap coverage — making "unknown cap" mean unknown

**Measured 2026-09-11. Shipped on `fix/cap-warm-derived-2026-09-11`.**
Module: `backend/sepa/cap_warm.py` · Cron: Saturdays 08:10 ET
Tests: `tests/test_cap_warm.py`, guards in `tests/test_supply_demand_contracts.py`
Related: `tests/test_cap_floor.py` (the floor itself — NOT changed here)

Configured cache-coverage method, not a book method. No Minervini cites; the
cap floor is Ajay's own number ("make cap 700 m", 2026-09-10), not a book gate.

---

## 1. What was wrong

`supply_demand.zone_store.big_cap_universe` keeps a name only when the weekly
shares cache carries a `market_cap` at or above `MIN_CAP_USD`:

```python
if caps.get(s) is not None and float(caps[s]) >= floor:
```

That is fail-closed on purpose, and it is correct: an unpriced name is not a
small name, but it is not a known-big one either. The defect was never the
comparison. It was that **nothing ever filled the cache over the scan
universe**, so "unknown" was overwhelmingly a fact about our fetch schedule
rather than a fact about the name.

Measured against the live cache (`load_universe("full")`, api container):

| | count |
|---|---|
| full universe | 2,651 |
| no `shares_cache` row at all | 671 |
| row present, `market_cap` is `None` | 39 |
| **TOTAL BLIND** | **710 (26.8%)** |
| kept by `big_cap_universe` | 1,728 |

331 of the blind names traded over **$50M/day**. Names with **zero**
`zone_store` docs included **MU** ($37.0B/day), **TSM, LLY, SHOP, APH, AZO,
CVNA, TGT, TEAM, TTWO, SAP, ALNY, UAL, DVN, CAH**.

No `zone_store` doc means no bands, and no bands means the whole downstream
chain is silent for that name: no `demand_alert`, no `zone_bounce_alert`, no
`supply_break_alert`, and no `zone_edge_entry` paper lane. A quarter of the
universe — including some of its most liquid names — was not being watched, and
nothing anywhere reported a number saying so.

## 2. Two causes, both real

**(a) The fetch is lazy and nothing warms it.**
`sepa.volume_movers.shares_for()` fetches a symbol only when something happens
to ask — a Volume Movers card render, or the Russell watch. There was no job
over the scan universe, so 671 names were simply never asked about. The cache
held 2,466 rows in total, accumulated by whatever the UI had touched.

**(b) A partial row was honored as if it were complete.**
`shares_for` writes the fetched payload verbatim, including a null tombstone on
a miss, and then honors any row where `any(v is not None)` for the full 7-day
TTL. MU's row was:

```json
{"float_shares": 1125620978, "shares_outstanding": null, "market_cap": null}
```

yfinance returned a float and no `marketCap`. The row therefore looked fresh and
MU stayed invisible to every zone board for a week at a time — **even though the
data needed to derive a cap was sitting in the row.**

## 3. What changed

**The gate did not.** `MIN_CAP_USD` is still $700M; the fail-closed comparison
in `big_cap_universe` is byte-for-byte what it was, and
`test_supply_demand_contracts.py::test_big_cap_universe_still_fails_closed_on_an_unknown_cap`
pins its exact source text so coverage work cannot quietly become gate work. A
name with a genuinely unknown cap is still excluded. The eligible set widens
because the **data** arrived, not because a rule moved.

### 3a. A weekly warm — `sepa.cap_warm.warm()`

Walks `load_universe("full")` and fills missing caps, cheapest path first:

1. **Row already has a usable cap** → leave it. No fetch, no write.
2. **Row exists without one** → derive from the row plus our own price cache.
   *Costs no provider call at all* — this is the whole of the 39 null-cap names.
3. **No row** → fetch shares once, then derive if the fetch still brought no cap.

Throttled: 4 workers, batches of 50, a 1s pause between batches, 30-minute
budget. It runs Saturdays 08:10 ET, after `observability.symbol_liveness`, on a
day when no scan is competing for the provider. Cache-only, so no market-day
gate.

### 3b. Derivation, and why float is the safe fallback

Last close comes from `sepa.prices.load_prices` — our own Mongo cache, **closed
bars**, never `with_today_bar` (a cap is a scale read, and an intraday snapshot
would both flicker and cost a provider call per symbol).

```
market_cap reported by the provider  ->  cap_source "reported"    (always wins)
shares_outstanding x last_close      ->  cap_source "derived_shares"
float_shares       x last_close      ->  cap_source "derived_float"
```

`derived_float` is **not** the market cap. Float excludes insider and restricted
stock, so it *understates*. That is exactly why it is safe against a gate that
only ever asks `>= floor`:

> Since `float_shares <= shares_outstanding`, a float-derived cap is a **lower
> bound** on the true cap. Clearing $700M on it proves the true cap clears
> $700M too. It can under-admit a name; it can never over-admit one.

The gate keeps failing in the same direction it always failed.
`test_cap_warm.py::test_a_float_derived_cap_is_a_lower_bound_on_the_true_cap`
is the alarm if that ever inverts.

**The bound works in one direction only, and that is enforced.** A float-derived
cap is written *only when it clears the floor*. Below the floor the
understatement is the one place it could flip a real answer — and as of the same
day (`trading/safety_floor.py`, "Safety floors on every buy"), a **known**
sub-floor cap is a HARD block on the entry path while an **unknown** cap is only
a warning:

```python
blocked  = [r for r in (price_block(price), cap_block(c)) if r]
warnings = [r for r in (cap_warning(c), liquidity_warning(dollar_vol)) if r]
```

So writing a float-derived $595M for a name whose true cap is $900M would refuse
a buy the lanes should have been allowed to take. Such a row is left blind
instead: the zone boards exclude it either way, and the entry path keeps warning
rather than blocking on a number we cannot stand behind.
`shares_outstanding x close` **is** the market cap by definition, so it is
trustworthy in both directions and is always written — including below the
floor, which is what Ajay asked for ("I dont want 10 Million Market Cap stocks
too").

Pinned by `test_cap_warm.py::test_a_sub_floor_float_derived_cap_is_never_written`.

Every filled cap is tagged `cap_source`, with `cap_derived_close` recording the
price used, so a derived number can never be mistaken for a reported one.

### 3c. The lazy writer had to stop clobbering the warm

`shares_for` and `cap_warm` both write this row, and the lazy one wins by
recency. Left alone, the next Russell-watch fetch of MU would write
`market_cap: null` straight back over the derived value and re-blind the name —
every week, forever. `shares_for` now fills the row through the **same**
`cap_fields()` helper, so both writers agree.
`test_both_cap_writers_fill_a_row_through_the_same_helper` pins that.

## 4. Coverage, not freshness — deliberately

The job fills **missing** caps. A row that already carries one is left alone
even past the 7-day TTL (`refresh_stale=True` overrides; off by default).

Two reasons. `shares_for` already re-fetches stale rows lazily. And a weekly
re-fetch of ~2,000 names to refresh numbers that only ever answer a
"`>= $700M`?" question would be provider load spent on nothing — a cap would
have to move by an order of magnitude for the answer to change.

Steady state is therefore nearly free: after the first fill, a run touches only
names that are new to the universe.

## 5. What this does NOT claim

Widening coverage from 1,728 to ~2,400 names is **not** a measured improvement
to anything. It restores names to the boards that the rules already said
belonged there. Whether the extra names produce good demand alerts is a
separate question that only forward grading answers — the same standard every
other S/D board is held to. No gate was loosened, no threshold moved, and no
claim is made here about edge.

## 6. Traps found while measuring this

* `sepa_research_cache` is keyed by an ObjectId `_id`, **not** by symbol — query
  it by `symbol` or you silently get zero docs.
* `zone_store` is keyed by `symbol` with **multiple dated docs per symbol** —
  always `sort=[("date", -1)]`.
* `shares_cache` **is** keyed by `_id` = symbol.
* A NaN cap survives `float()` and fails `>= floor` (so it fails closed), but it
  passes any `is not None` check — meaning it would look "known" and never get
  repaired. `cap_warm._pos_finite` treats NaN as missing everywhere.
* macOS caches bytecode under `~/Library/Caches/com.apple.python`; a same-size,
  same-second file restore serves the stale `.pyc`. Purge it when
  mutation-testing.
