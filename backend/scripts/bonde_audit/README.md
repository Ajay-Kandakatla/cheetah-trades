# Bonde board — the measurement

Run 2026-09-13, the day the 📈 Bonde tab shipped. **The board's own thesis
measured inverted**, so the tab leads with these numbers rather than with the
rules. Nothing here is re-typed onto a surface: `sepa/bonde.py`,
`frontend/src/lib/chartMaps.ts` and `docs/sepa/bonde_board.md` all quote this
directory, and `backend/tests/test_bonde_measured.py` fails if the headline
figures drift out of them.

## Which script is the authority

Two passes exist. The **audit** is the authority.

| file | what |
|---|---|
| `core.py` | shared loaders, point-in-time sales state, clustered bootstrap |
| `fetch.py` | Massive quarterly financials, 10 workers **with retry** |
| `oracle.py` | validates the reconstructed EP rule vs the 63 stored `setups` docs |
| `lane1.py` | **the headline** — EP × sales gate vs a date-matched placebo |
| `lane1b.py` | brackets, date-clustered CIs, the lookahead probe |
| `lane2.py` | the sales-tier panel, 24 cross-sections |
| `attack.py` | date clustering, per-date sign test, tail trim |
| `sens.py` | four fundamentals variants, both lanes |
| `parent_ep.py`, `parent_tiers.py` | **first pass, superseded** — kept so the struck claims are visible |

## The headline

**780** Episodic Pivots reconstructed from closed bars, 2024-09-13 → 2026-09-11.
The **376** that also passed Bonde's sales gate returned a **21-day median
−3.22%** (win rate **39.8%**) against **−0.11%** (**49.6%**) for date-matched
non-EP names — a lift of **−3.11pp**, 95% CI **−5.28 to −1.16** symbol-clustered
and **−5.19 to −1.13** date-clustered. The sales gate on its own separated
nothing at any horizon (**−0.40pp**, CI −1.40 to +0.61).

The tiers do not separate on the typical name either: ≥100% and ≥25% beat the
scored universe by a **median** of +0.45pp and +0.37pp at 21 days, both CIs
spanning zero, win rates level with the market. The mean lift that does show up
is the right tail — strong falls from +5.27pp to **+0.26pp** when the top 5% of
returns are dropped.

One finding survived every attack: among names that clear the 5% floor,
requiring **2 consecutive growth quarters costs 3.3pp of win rate** over 21 days
(CI −4.7 to −1.8) and 4.1pp over 63. The floor-clearing names the gate *rejects*
for lacking character win **56.8%** against **51.2%** for the names it accepts.
`accelerating` is a null, not a negative.

## What was struck

Three first-pass claims did not reproduce and are **not** printed anywhere:

1. *"EP + sales-PASS loses to EP + sales-FAIL"* — re-measured −2.42pp
   [−4.88, +0.30], spans zero in all four variants.
2. *"Both character clauses are inverted"* — only the consistency clause is.
3. *"Coverage is 46%"* — that was the first pass's own no-retry fetcher losing
   half its requests. The audit's panel is ~2× larger.

## Re-running

Inside the api container only — it is the only place the Massive key lives, and
a throwaway container silently falls back to Yahoo and produces false negatives.

```
cd /Users/ajay/clinet-test/cheetah-market-app
docker compose exec -T api mkdir -p /root/.cheetah/aud
docker compose cp backend/scripts/bonde_audit/core.py api:/root/.cheetah/aud/core.py
docker compose exec -T api python - < backend/scripts/bonde_audit/fetch.py
docker compose exec -T api python - < backend/scripts/bonde_audit/oracle.py
docker compose exec -T api python - < backend/scripts/bonde_audit/lane1.py
docker compose exec -T api python - < backend/scripts/bonde_audit/lane1b.py
docker compose exec -T api python - < backend/scripts/bonde_audit/lane2.py
docker compose exec -T api python - < backend/scripts/bonde_audit/attack.py
docker compose exec -T api python - < backend/scripts/bonde_audit/sens.py
```

Heredoc/stdin, never `python /tmp/x.py` — that puts `/tmp` on `sys.path`
instead of `/app`.

## Limits worth knowing before quoting any of it

- **Delisting survivorship is unmeasured.** `load_universe()` is today's
  membership, so anything that went to zero between 2024-09 and 2026-09 is
  absent from every cell.
- **24 cross-sections, one bull regime.** The date cluster is the binding one
  and 24 clusters is a fragile bootstrap — reported as the honest floor, not as
  a comfortable number.
- **The derived-Q4 availability date is an assumption** (`end_date + 90d`, the
  10-K deadline). 24.3% of quarterly rows carry `filing_date: None` and 99.6% of
  events have at least one in their window, which is why every headline was
  re-run with those rows dropped.
- **24.6% of EP events are unclassifiable**, and the dropout is structural —
  212 of 255 are recent IPOs and de-SPACs, exactly the population most prone to
  episodic pivots.
- **Gross returns.** No commissions, slippage or borrow, and real fills on
  8%-gap names would be worse for the EP cohort than for the placebo.
- **Catalyst type could not be split.** `episodic_pivot._classify_catalyst`
  reads earnings dates for today only, and Bonde's own EP taxonomy is
  catalyst-named — if an edge exists it may live in a split this data cannot
  make.
