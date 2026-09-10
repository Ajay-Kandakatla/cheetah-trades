# 📐 The pattern scan runs against ALL names, not the qualifier list

Ajay, 2026-09-10:

> The chart patterns are only looking at qualified sepa list I want them to run
> against all

He was right, and it was true in three separate places at once.

## What the board was actually sweeping

| # | where | the narrowing | measured 2026-09-10 |
|---|-------|---------------|---------------------|
| 1 | `patterns/scan.py::_universe_with_context` | returned on the latest SEPA scan's `all_results` and never reached the universe loader below it | **283** names in `load_universe("full")` were never scanned at all (286 before the RS anchors were excluded) |
| 2 | `patterns/scan.py::_run_scan` | persisted `all_found[:200]` | `n_found` was **239** — the cap BOUND and cut **39** |
| 3 | `patterns/scan.py::_verdict_universe` | qualifiers ∪ holdings ∪ buyable ∪ at-pivot ∪ leaders | **313** names against a SEPA page listing **2,365** rows |
| 4 | `frontend/src/pages/PatternsPage.tsx` | the gold button he actually clicks posted scope `qualifiers` | ~300 names, and it does not refresh the board below it |

Defect 2 is the one that reached the phone: the display sort is
`(confirmed first, is_candidate first, rs_rank desc)`, so the 39 rows the cap
cut were disproportionately the **non-qualifiers** — exactly the names he was
asking about — and `patterns/pattern_alerts.py` reads that same truncated list.

Defect 3 is why a 📐 chip was **blank** on most SEPA rows. A blank chip reads as
"no pattern". It meant "never looked".

## What it sweeps now

**`UNIVERSE_MODE = "full"`** — the same alias the SEPA scan, `zone_store` and
the demand boards already run (Russell 3000 ∪ S&P 1500 ∪ curated ∪ themes,
**2,650** names on 2026-09-10), **unioned** with the latest SEPA scan's rows so
the board can never be narrower than the pages that link into it.

- A name with **no SEPA row** is scanned with an **empty context dict** — a
  missing SEPA row is a missing chip, never a reason to skip the chart.
- ETFs the scan flagged stay out — but that filter alone is **not** enough, and
  assuming it was is how this shipped broken the first time. The `is_etf` flag
  only exists on names the SEPA scan **rowed**; `SPY`, `QQQ` and `IWM` ride in
  every universe for the RS math and are never scanned, so they carry no row
  and no flag. The first dry run of the widened sweep duly returned all three
  as pattern candidates. They are now excluded against
  `sepa.universe.RS_ANCHORS` — the list itself, read with `getattr` so a
  missing constant costs the three anchors and never the whole widening.
  Net symbols after the exclusion: **2,648**, of which **283** are
  universe-only (no SEPA row).
- **Fails toward the narrower list, never toward nothing.** `load_universe`
  down → sweep the SEPA rows (the pre-2026-09-10 behaviour). Both down →
  `_run_scan` raises a loud `no universe` rather than persisting an empty
  "quiet market" over a good doc.

**`MAX_RESULTS = 2000`**, and whatever it still cuts is **counted**, never
silent — `n_found` stays the honest pre-cap total, alongside `n_results`,
`n_dropped`, `max_results`, `symbols_scanned` and `symbols_with_sepa_ctx`, plus
a `log.warning` whenever the cap binds. Measured ~600 B per result row, so
2,000 rows ≈ **1.2 MB** against Mongo's 16 MB document limit.

**The verdict scan spans the universe too**, with a sixth source tag. Union
members keep their own tags (`qualifier` / `buyable` / `holding` / `at_pivot` /
`leader`, which the Portfolio and Leaderboard cross-link chips render off);
every other name is tagged **`universe`** — in the sweep, none of the above — so
the cross-link chips stay exactly as narrow as they were. ~678 B per verdict, so
2,650 ≈ **1.8 MB**.

**The gold button sweeps the universe.** The qualifier verdict scan is a
genuinely different product — an explicit answer for every qualifier including
"no pattern", which is what feeds the 📐 chips — so it keeps its button, demoted
to the outline one. Both labels and both tooltips now carry their scope and
their name count.

### Cost is a non-issue

Cached daily frames load in ~24 ms, so 2,650 names is ~63 s serial and **~8 s**
at the existing `MAX_WORKERS = 8` before the detectors run. The universe scan
was already doing 2,648.

## The two gates still standing between a pattern and his phone

A wider board is **not** more alerts. Neither gate was touched, and neither may
be loosened to make the wider sweep "work":

| gate | rule | where |
|------|------|-------|
| **$1B zone floor** | `zone_store.MIN_CAP_USD = 1_000_000_000` — Ajay 2026-09-03: *"billion or at least bigger than a billion"*. Only **1,408** of the 2,650 have zone docs; the other **1,242** are sub-$1B **by his choice** | `supply_demand/zone_store.py` |
| **demand-band gate** | a confirmation reaches the phone only `in_zone` (print inside an eligible demand band) or `reversal` (touched one in the last 5 sessions, now ≥ max(3%, 1 ATR) above it and ≤ 5% above the band top). Fails closed: `skipped_no_zone` ≠ `skipped_no_demand`, and `MAX_ZONE_BUILDS = 40` | `patterns/pattern_alerts.py`, [pattern_demand_gate.md](../supply_demand/pattern_demand_gate.md) |

So: **the board widens, the phone does not.** More names in the sweep means
more ways to be blind rather than quiet, which makes the two-counter split in
the demand gate matter more, not less.

None of this makes the patterns work either. His own ledger, 669 resolved
observations graded 21 sessions forward: cup-with-handle 45% (n=434), double
bottom 43% (n=248), triple bottom 37% (n=68), inverse H&S 10% (n=10), against a
**50% placebo**. **Not one beats chance.** Every push still carries its own rate
next to the placebo.

## Re-running the counts

```bash
docker compose exec api python -c "
from patterns import scan
syms, ctx = scan._universe_with_context()
print('swept        ', len(syms))
print('with sepa ctx', sum(1 for s in syms if s in ctx))
print('universe-only', sum(1 for s in syms if s not in ctx))
"
```

```bash
docker compose exec api python -m patterns.scan universe

docker compose exec api python -c "
from patterns import scan
d = scan.latest()
print({k: d.get(k) for k in ('symbols_scanned','symbols_with_sepa_ctx',
                             'n_found','n_results','n_dropped','max_results')})
"
```

Verdict coverage and the new tag:

```bash
docker compose exec api python -c "
from patterns import scan
u = scan._verdict_universe()
print('verdict names', len(u))
print('universe-only', sum(1 for e in u.values() if e['sources'] == ['universe']))
"
```

## Tests

```bash
docker compose exec api python -m pytest tests/test_patterns_universe.py \
                                         tests/test_patterns_contracts.py -v

cd frontend && npx vitest run src/pages/PatternsPage.scan.test.tsx
```

`tests/test_patterns_contracts.py` is the source guard: it pins the early
`return list(ctx.keys()), ctx` **out** of `_universe_with_context`, the `[:200]`
literal out of `_run_scan`, `_, ctx = _universe_with_context()` out of
`_verdict_universe`, and `MIN_CAP_USD` / `MAX_ZONE_BUILDS` / `NEAR_MAX_PCT`
**unchanged** — so the scan can never silently narrow back to the qualifier
list, and widening it can never be paid for by loosening a gate.
