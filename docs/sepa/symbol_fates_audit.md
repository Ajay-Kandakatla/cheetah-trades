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

---

## 2026-09-29 — dead-ticker triage (48 names)

**Ask (Ajay, 2026-09-29):** "Remove the dead ones please" — the 48 universe
names the latest SEPA scan skipped as stale (no bar in ~10 sessions) or
"no price data". **Branch:** `fix/delist-dead-tickers-2026-09-29`.

Each verdict checked against Massive **live** on 2026-09-29: reference
lookup (both spellings for class shares), the inactive record's
`delisted_utc`, ticker events, daily aggs 2026-08-15→09-29 and a successor
search by CIK and by name. Re-probed by the executor the same day: all 48
old symbols reference NOT_FOUND, no aggs after the listed last bar, and all
8 successors active with 19–31 aggs through 09-29.

**Result: 40 DEAD → `DELISTED`, 7 RENAME → `RENAMES`, 1 HIS CALL (VSCO),
0 ALIVE.**

`load_universe("full")` measured in the api container (branch
`symbols.py` loaded in place of the deployed one, read-only):
**2,728 → 2,685 (−43)** = 40 dead + 3 renames whose successor was already
in the universe (KEEL, VMRK, DMC collapse into one slot each). The other
4 renames swap in place (NXH, HOS, HAPN, SHOE come in).

| Symbol | Company | Verdict | Delisted / effective | Last bar | Successor / note |
|---|---|---|---|---|---|
| ADRO | Aduro Biotech (Chinook CVR row) | DEAD | 2020-10-06 | 2020-10-05 | KDNY (same CIK) also delisted 2023-08-14 |
| AKE | Akero Therapeutics CVR | DEAD | never an equity (AKRO 2025-12-10) | none | CVR row in iShares R3000 |
| AMWD | American Woodmark | DEAD | 2026-05-29 | 2026-05-27 | acquirer MBC keeps its own series |
| APGE | Apogee Therapeutics | DEAD | 2026-09-04 | 2026-09-02 | acquired by AbbVie |
| AVNS | Avanos Medical | DEAD | 2026-07-28 | 2026-07-24 | take-private |
| BBBY | Bed Bath & Beyond, Inc. | **RENAME** | eff. 2026-08-17 | 2026-08-14 | **NXH**, +4.6% boundary |
| BITF | Bitfarms Ltd. | **RENAME** | eff. 2026-04-06 | 2026-04-02 | **KEEL**, +4.5% boundary |
| CCRN | Cross Country Healthcare | DEAD | 2026-07-22 | 2026-07-20 | sold to Knox Lane |
| CEP | Cantor Equity Partners (SPAC) | DEAD | 2025-12-09 | 2025-12-08 | de-SPAC into XXI: new issuer, −24.7% boundary, never splice |
| CPRX | Catalyst Pharmaceuticals | DEAD | 2026-07-16 | 2026-07-14 | acquired by Angelini |
| CRNX | Crinetics Pharmaceuticals | DEAD | 2026-09-02 | 2026-08-31 | acquired by Vertex |
| CVGW | Calavo Growers | DEAD | 2026-05-29 | 2026-05-27 | acquirer AVO keeps its own series |
| CWAN | Clearwater Analytics | DEAD | 2026-06-29 | 2026-06-24 | take-private at $24.55 |
| EQR | Equity Residential | **RENAME** | eff. 2026-08-18 | 2026-08-17 | **VMRK**, +0.8% boundary |
| ESPR | Esperion Therapeutics | DEAD | 2026-07-14 | 2026-07-10 | ARCHIMED buyout |
| FDP | Fresh Del Monte Produce | **RENAME** | eff. 2026-06-29 | 2026-06-26 | **DMC**, −0.75% boundary |
| FFIC | Flushing Financial | DEAD | 2026-06-02 | 2026-06-01 | merged into OCFC (different CIK) |
| GTLS | Chart Industries | DEAD | 2026-07-17 | 2026-07-15 | acquired by Baker Hughes |
| GTXI | GTx Inc. CVR | DEAD | 2019-06-10 | none | CVR row in iShares R3000 / IWC |
| HLX | Helix Energy Solutions | **RENAME** | eff. 2026-09-02 | 2026-09-01 | **HOS**, +2.2% boundary |
| INH | Inhibrx Inc CVR | DEAD | never an equity | none | CVR row; INBX is a separate entity |
| KALV | KalVista Pharmaceuticals | DEAD | 2026-06-12 | 2026-06-10 | cash deal |
| KW | Kennedy-Wilson Holdings | DEAD | 2026-06-17 | 2026-06-15 | Fairfax take-private |
| LBRDA | Liberty Broadband A | DEAD | 2026-08-21 | 2026-08-19 | absorbed by CHTR (exchange ratio) |
| LBRDK | Liberty Broadband C | DEAD | 2026-08-21 | 2026-08-19 | absorbed by CHTR (exchange ratio) |
| LC | LendingClub | **RENAME** | eff. 2026-06-22 | 2026-06-18 | **HAPN**, +1.0% boundary |
| LEG | Leggett & Platt | DEAD | 2026-08-27 | 2026-08-26 | Somnigroup bid; no completion release found |
| LPRO | Open Lending | DEAD | 2026-07-31 | 2026-07-29 | cash deal |
| NFBK | Northfield Bancorp | DEAD | 2026-07-21 | 2026-07-20 | acquired by Columbia Financial |
| NUVL | Nuvalent | DEAD | 2026-07-16 | 2026-07-14 | acquired by GSK |
| OLPX | Olaplex Holdings | DEAD | 2026-07-08 | 2026-07-06 | acquired by Henkel |
| P5N994 | Petrocorp Inc Escrow | DEAD | never listed | none | iShares NNQS placeholder |
| PRA | ProAssurance | DEAD | 2026-06-29 | 2026-06-25 | cash deal at $25.00 |
| RMAX | RE/MAX Holdings | DEAD | 2026-08-25 | 2026-08-24 | acquired by Real Brokerage |
| SCVL | Shoe Carnival | **RENAME** | eff. 2026-06-12 | 2026-06-11 | **SHOE**, 0.0% boundary |
| SEM | Select Medical | DEAD | 2026-07-01 | 2026-06-30 | take-private |
| SILA | Sila Realty Trust | DEAD | 2026-07-02 | 2026-06-30 | buyout |
| SKYT | SkyWater Technology | DEAD | 2026-08-03 | 2026-07-30 | acquirer IONQ keeps its own series |
| SMLR | Semler Scientific | DEAD | 2026-01-20 | 2026-01-15 | merged into Strive |
| SNBR | Sleep Number | DEAD | 2026-06-23 | 2026-06-22 | Chapter 11; OTC SNBRQ is a shell, not a rename |
| STEL | Stellar Bancorp | DEAD | 2026-07-01 | 2026-06-30 | merged into Prosperity |
| TALK | Talkspace | DEAD | 2026-08-18 | 2026-08-14 | acquired by UHS |
| THR | Thermon Group | DEAD | 2026-06-02 | 2026-05-29 | combined into CECO |
| TMHC | Taylor Morrison Home | DEAD | 2026-07-27 | 2026-07-23 | acquired by Berkshire Hathaway |
| TWO | Two Harbors Investment | DEAD | 2026-08-26 | 2026-08-24 | TWOD (same CIK) is senior notes, never map |
| VSCO | Victoria's Secret & Co. | **HIS CALL** | ticker change 2026-06-02 | 2026-06-01 | VSXY, same FIGI/CIK, but +44.6% boundary open |
| WBS | Webster Financial | DEAD | 2026-08-20 | 2026-08-19 | acquired by Banco Santander |
| WSR | Whitestone REIT | DEAD | 2026-07-15 | 2026-07-13 | acquired by Ares |

Per-entry evidence (deal pin, volume multiple, news source) lives on each
`sepa.symbols.DELISTED` / `RENAMES` entry.

### VSCO → VSXY is HIS CALL

The identity is certain (same composite FIGI BBG01103B471, same CIK, a
Massive `ticker_change` on 2026-06-02). The boundary is not: VSCO closed
54.30 on 06-01 and VSXY opened 78.53 on 06-02, 1.45×, above
`prices.SPLICE_MAX_JUMP_RATIO` (1.35×). The premarket tape shows a real news
gap (54.30 at 04:00, then 62–80 from 07:00 on heavy volume), probably the Q1
print, but that is unconfirmed. `splice_history` would refuse the join anyway
and serve VSXY alone, so a RENAMES entry would dedup the universe and
nothing more. Until Ajay decides, VSCO stays in the universe as a stale name
beside VSXY.

### Open items (not done here)

- **Rosters still carry three of these names.** The fate filter already
  keeps them out of every `load_universe` path, but the roster guards fail:
  `supply_demand/sectors.py` crypto_equities (BITF → KEEL, SMLR dead),
  `sepa/universe.py` curated `UNIVERSE` (BITF, SMLR) and the `crypto` theme
  (BITF, SMLR, CEP), `supply_demand/equity_premium.py` treasury set (BITF,
  SMLR).
- **Ingestion filter.** AKE, GTXI, INH (CVR rows) and P5N994 (an NNQS escrow
  placeholder) come in from the iShares holdings files. A CVR/NNQS filter in
  the iShares parser would be sturdier than a DELISTED entry per row.
- **AVB** stays DELISTED. Its successor is now known (VMRK, the renamed EQR
  side of the merger), but AVB holders were paid at an exchange ratio, so it
  is not a splice.
- **LC** appears in `cheetah_data.py` tier3 as a raw literal.

### Post-deploy step

The successor caches are short or stale (NXH ends 2026-09-01, HAPN
2026-08-25, SHOE 2026-09-09). One forced fetch each lets the splice land:

    docker exec cheetah-market-app-api-1 python -c "from sepa import prices; [prices.load_prices(s, force=True) for s in ('NXH','KEEL','VMRK','DMC','HOS','HAPN','SHOE')]"

### Tests

`tests/test_delist_dead_tickers_2026_09_29.py`: every new name flagged
with dated evidence; renames resolve and splice across their real boundary
bars; VSCO's boundary refused and VSCO unmapped (negative); successors,
acquirers and TWOD untouched (negative); prior entries unchanged; every
`load_universe` mode plus the env literal and env file drop the dead and
resolve the renames; the count drops by exactly the number removed.

### 2026-09-29 — roster repair after the dead-ticker cleanup

Hard-coded rosters that still held a name from this cleanup were fixed, so no
board shows a name the scan can no longer see:

- `supply_demand/sectors.py` crypto_equities: BITF -> KEEL, SMLR dropped (roster 24 -> 23).
- `sepa/universe.py` curated `UNIVERSE`: BITF -> KEEL, SMLR dropped. `crypto` theme: BITF -> KEEL, SMLR and CEP dropped.
- `supply_demand/equity_premium.py` `treasury_set`: BITF -> KEEL (KEEL keeps the TREASURY tag), SMLR dropped.
- `cheetah_data.py` SOFI tier3 peer: LC -> HAPN.
- EQR evidence line corrected: FIGI and ticker events match, the CIK does NOT (inactive EQR record = 0000931182, ERP Operating LP; VMRK = 0000906107).
- AVB evidence line notes VMRK is the acquirer, not a successor; AVB stays DELISTED.

Known and out of scope: SATS (renamed ECHO 2026-06-24, already on main) is still in the `space` theme.
## §2026-09-29 — reused tickers and a reorg (Dual Momentum data audit)

A new fate class: the ticker is **alive**, but its frame begins with a
**different security's** bars. The Dual Momentum page ranked WOLF +2,248.76%,
BNY +1,435% and SPCX +474.95% (12m) on those heads. Full evidence and the
top-50 + 29-name pool cross-check: `docs/sepa/dual_momentum_data_audit_2026_09_29.md`.

- **`sepa/symbols.py` `FIRST_SESSION`** (new curated map, evidence per entry):
  WOLF 2025-09-29 (Ch.11 reorg, new FIGI BBG01XLDHDP0), SPCX 2026-06-12 (SPAC
  ETF → SpaceX), SOLS 2025-10-30 (OTC shell → Solstice). Disjoint from
  RENAMES keys, targets and DELISTED (test-pinned).
- **Two RENAMES entries** (boundary bars checked, same FIGI): BK → BNY
  2026-05-21 (137.16 → 136.46), AMRK → GOLD 2025-12-02 (29.25 → 30.13). Both
  new symbols' earlier bars belonged to another security (a muni fund,
  Barrick) behind a 104- / 208-day hole. **Ships only with the one-time
  refetch** (HIS CALL #6):

      docker exec cheetah-market-app-api-1 python -c "from sepa import prices; prices.load_prices('BNY', force=True); prices.load_prices('GOLD', force=True)"

- **`sepa/prices._cut_foreign_head`**: a curated, read-time cut (fetch, all
  three `load_prices` returns, `bulk_cached_frames`). A renamed symbol's head
  is kept only when it passes `splice_history`'s own gap and ratio tests. A
  symbol in neither map comes back as the same object. App-wide reach: until
  the refetch, BNY (~90 bars) and GOLD (~208 bars) drop out of every 200-day /
  52-week read. Readers that bypass `load_prices` / `bulk_cached_frames`
  (`supply_demand/hot_pullback.py`, `supply_demand/premarket_entry.py`,
  `political/watch.py`, `studies/*`) are not covered.
- **Finding the next one:** `backend/scripts/dm_frame_audit.py` (read-only).
- **Tests:** `backend/tests/test_foreign_head_cut_2026_09_29.py`.
