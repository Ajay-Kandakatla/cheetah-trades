# Symbol fates audit — the 69 names that never reached `all_results`

**Date:** 2026-08-25 · **Branch:** `fix/symbol-liveness-2026-08-25`

Not Minervini methodology — data plumbing, same family as
`sepa/symbols.py` (renames) and `observability/symbol_liveness.py`
(staleness). Every fate below was verified against Massive **live** on
2026-08-25; nothing here is from memory or a list off the internet.

## What the audit found

`health_audit.check_symbol_liveness` flagged SMAR, DOOO, CFLT, CWEN-A as
"stopped printing bars". A universe-vs-`all_results` diff widened that to
**69 of 1,746** symbols that never produced a scan row — and
`latest.json.permanent_failures` was `[]`, because both scan loops silently
dropped any `_analyze_symbol()` that returned `None` without raising.

Verification per symbol: Mongo price-cache state (bars, last date,
staleness) + Massive reference lookup under both spellings + daily aggs
2026-08-08→25 + an active-listings name search for successors.

## The 69, decomposed

| Bucket | Count | Fate | Action |
|---|---|---|---|
| Benchmarks (SPY/QQQ/IWM) | 3 | excluded by design | now recorded (`attempt: 0`) |
| Liquidity floor (BANF, BF-A, SMP, FWONA, GLIBA, LEN-B, 20+ small banks/utilities) | ~29 | **alive**, thinly traded | keep; skip now recorded |
| Young listings < 220 bars (FISV, P=Everpure, Q=Qnity, VMRK, …) | ~26 | **alive**, short history | keep; skip now recorded |
| Renamed | 2 | DOOO→**DOO**, IAC→**PPLI** | `RENAMES` entries; universe remapped |
| Delisted | 9 | SMAR, CFLT, CWEN-A, MASI, BLD, JHG, NSA, EA, AVB | `DELISTED` entries; leave universe |

Notable: the task hypothesized FISV / P / Q / SMP were dead — the provider
says all four are **alive** (FISV active on XNAS at ~$28B; P and Q are young
listings). The dash-class hypothesis also fell: BF-A and LEN-B fetch fine
under Massive's dot form (`for_massive` already maps them), FWONA and GLIBA
are natively dotless at Massive — all four drop on the **liquidity floor**,
which was simply invisible before.

## Rename evidence (boundary bars, splice-guard clean)

- **DOOO → DOO** effective 2025-12-08. DOOO last bar 2025-12-05 close
  76.66; DOO first bar 2025-12-08 open 81.67. Consecutive sessions,
  1.07× boundary (guard max 1.35×). Massive: DOO active XNAS
  "BRP Inc. Common Subordinate Voting Shares".
- **IAC → PPLI** effective 2026-06-04. IAC last bar 2026-06-03 close
  42.24; PPLI first bar 2026-06-04 open 42.72. Consecutive sessions,
  1.01× boundary. Massive: PPLI active XNAS "People Incorporated Common
  Stock". Both IAC and PPLI were in the universe — fate resolution
  collapses them to one PPLI.

Full delisting evidence lives on each `sepa.symbols.DELISTED` entry
(deal-close signatures: price pinned at deal level, final session on a
volume multiple).

## What changed

1. **`sepa/symbols.py`** — two `RENAMES` entries; new curated
   `DELISTED` map + `is_delisted()`. Delisting ≠ rename: no successor
   series, the symbol just leaves the universe.
2. **`sepa/universe.py`** — `_resolve_fates()` inside
   `_with_benchmarks()`: every `load_universe` path (cached fetches,
   curated, env overrides) maps renames to the live symbol, dedups
   old+new pairs, drops verified delistings. Curated list cleaned
   (CFLT/SMAR out, DOOO→DOO, SQ→XYZ).
3. **`sepa/scanner.py`** — every silent `None` now records a reason
   (`skips`), folded into `permanent_failures` with `"skipped": true`
   by `_absorb_skips()` in both scan paths. `universe_size` now
   reconciles against `all_results` exactly. Contract:
   `docs/SEPA_CONTRACTS.md` §2. `recovered_count` semantics unchanged.
4. **`catalysts/scanner.py`** — movers with a `DELISTED` ticker are
   dropped post-normalize. GFRR (a Massive snapshot ghost: reference
   NOT_FOUND, zero aggs, Yahoo 404) had been erroring the 5-minute
   volume_alerts cron since at least 2026-08-21.

## Post-deploy step

PPLI's cached series is 57 unspliced bars; DOO has no cache. One forced
fetch each makes the splice land so both can pass the 220-bar floor:

    docker exec cheetah-market-app-api-1 python -c "from sepa import prices; prices.load_prices('PPLI', force=True); prices.load_prices('DOO', force=True)"

## Tests

`tests/test_symbols.py` (fates + negatives + map-disjointness),
`tests/test_universe_resolution.py` (chokepoint behavior incl. env-var
path), `tests/test_scan_skip_accounting.py` (skip reasons, absorb rules,
recovered_count), `tests/test_catalysts_ghosts.py` (ghost drop + live
movers untouched).
