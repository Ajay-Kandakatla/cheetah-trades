# Missing-data audit — SNDK and the whole universe (2026-10-07)

Ajay, 2026-10-07: *"yes please also no #s for SNDK can you do a deep analysis of data and make sure you do a sanity
chcek fo missing data pieces over all."*

Labels: **MEASURED** = a read-only probe or a code read proved it; **INFERRED** = the best explanation, not proved.
Every probe ran in a throwaway container with `scripts.resiliency_study.block_writes()` first. The probe scripts live
in the session scratchpad's `data_audit` folder and are cited by name (`audit_b.py`, `audit_b2.py`, `p1_audit.py`,
`p2_confirm.py`, `p3_dates.py`, `sndk_probe1.py`, `sndk_probe2.py`, `sndk_class_count.py`, `massive_confirm.py`,
`critic_v.py`, `fates_evidence.py`, `caly_bars.py`, `modg_yf.py`, `v3_probe.py`, `heal_select.py`); the shipped
re-runnable measurement is `backend/scripts/resiliency_tab_cost_probe.py`.

## SNDK, hop by hop (MEASURED)

Massive v1, CIK 0002023554 (quarterly):

| Quarter | Period end | Revenue | EPS | Net income |
|---|---|---|---|---|
| FY26 Q4 | 2026-07-03 | $8.965B | 43.69 | $6.903B |
| FY26 Q3 | | $5.950B | 23.03 | |
| FY26 Q2 | | $3.025B | 5.15 | |
| FY26 Q1 | | $2.308B | 0.75 | |
| FY25 Q4 | 2025-06-27 | **$1.901B** | **−0.16** | **−$23M** |
| FY25 Q3 | | $1.695B | −13.33 | |

- The cached doc (`sepa_research_cache`, `cached_at` 2026-09-27 20:14 ET) stores `rev_growth_q_pct`,
  `q_eps_growth_pct` and `sales.growth_yoy_pct` all None, beside v1 series that compute **+371.59%** sales YoY. The
  eps series has slot 4 None (the spin-off's first-year Q4 EPS is not derivable), net income slot 4 is −$23M.
- Cause: a series-only writer (`qoq.backfill`, INFERRED by elimination) spliced v1 series into a vX-era doc and never
  re-derived the % fields — the vintage mix fixed below.
- **Honest answer:** sales **+371.6%** YoY (FY2026 Q4 $8.97B vs FY2025 Q4 $1.90B); EPS — the year-ago quarter **lost
  money** (−$0.16 / −$23M), so under his rule it never ranks. SNDK is a ONE-leg name: under his YES it sits in the
  one-leg block, not the 🚀 top block (position 2,190 of 2,732 today, pending its refresh).
- Today's chip (MEASURED, V3): `Sales +371.6%* · EPS yr-ago loss YoY (FY2026 Q4)`. After the H1 heal (yfinance
  fallback path): `Sales +371.6% · EPS yr-ago loss YoY (Q2 2026)`.
- Why the doc was never rewritten: 0 research docs are dated 10-04 or 10-05; the 10-04 Sunday refresh never wrote
  (INFERRED: host sleep — pmset DarkWake 17:00–21:52 CDT; not a proven network outage). `--only-if-stale` logged
  "97% healthy" on 10-05 and 10-06. The 09-27 batch crosses the 16-day TTL on ~10-13 20:14 ET.

## Universe-wide growth gaps (MEASURED, before the fix)

Universe `demand_reentry._resolve_universe('full')` = 2,736 cards with a frame; 2,610 with a research row; 2,226
scored (2,219 sales-ranked, 1,448 EPS-ranked); **1,441 on both legs, 785 on one**. Counts are per leg and overlap.

| Cause | n (liquid) | Examples (by $/day) | Class |
|---|---|---|---|
| Stored sales % None, own series has it | 54 (54) | SNDK, CSCO, KLAC, JNJ, HD, PG, MS | defect, vintage mix |
| Stored sales % disagrees with own series | 151 (151) | JPM 27.69 vs 17.89, BRK-B, GS, BAC 19.25 vs 3.67, NU 5.82 vs 55.40 | defect, was RANKED on the stale number |
| Stored EPS % None, series has it | 61–66 | BRK-B, CSCO, KLAC, NU, MS, MDB | defect, vintage |
| Stored EPS % disagrees (shown, not ranked) | 89–111 | MSFT, LITE, WDC, NFLX −88.87 vs +11.11, SMCI | defect, vintage |
| EPS slot None but year-ago NI ≤ 0 | 25 | SNDK, SE, VTRS, KOD, XMTR | display: "year-ago loss" |
| Year-ago EPS ≤ 0 / < $0.10; year-ago rev ≤ 0 / < $1M | 610 / 145 / 81 | INTC, BE, MRNA, CRWD, DDOG, APLD | by rule, printed `—` |
| No doc, ≥ 220 bars | 53 (+6 full-not-broad, 7 past TTL) | FIG, FISV, VMRK, FROG, TTAN | defect, data |
| No doc, < 220 bars (`research.MIN_RESEARCH_BARS`) | 36 IPO/spin + 22 unspliced renames | SPCX, XE, HONA, P, MRSH | gate, his call |
| Foreign / blank yfinance on 09-27 | 42 + ~100 | ASML ('Q4 2015'), VIK, ONON, XP, AU, GFS | defect, refresh heals most |
| Latest quarter years stale (recycled ticker), RANKED | 22 (19 liquid) | AIQ (ETF, FY2017), MRX (FY2012), GLIBA (FY2020), SE, DOX | defect |
| Period mismatch | 31 | MSTR, Q, GLPI, WEN, FLO; SAP/CNQ/CNI/MGY/HIVE fail the prior pair only | unclear |
| ETF / fund | 36–43 | SPY, QQQ, SOXL, IWM, DRAM | expected, printed `—` |
| Delisted, still in universe | 7 | DBRG (delisted 10-01, was **#2 on 🚀**), QRVO, GBTG, PSKY; WBD/BLFS/SLP stop 10-05 but reference active | defect |

Non-growth gaps (MEASURED, not changed here — HIS CALLs 9–12 in the spec):

- Scan rows 1,865 of 2,736 (871 missing: 793 below the $20M floor, 59 < 220 bars, 15 full-not-broad, 3 benchmarks,
  1 stale).
- Earnings dates: 869 board names (incl. XE, his holding) are outside `earnings_watch._universe()`; 38 large names have
  `next_date` None (HPE, SNPS, WDAY, LULU…); 1,603 docs have no `last_report`.
- Market caps: 2,642 docs past their 7-day TTL; 314 drifted > 20%; 48 cross the $700M floor on drift alone.
- Sector labels come only from scan rows (857 names have none). 13F: 68 names with no doc, 15 still on Q1.
- The fast-scan liquidity gate reads the 09-27 research blob (12 names now ≥ $20M/day are skipped).

## What was fixed (branch `fix/growth-data-coverage-2026-10-07`)

1. **His YES** — the 🛡️ 🚀 order is both ranked legs, then one (EPS leg first), then none.
2. **Every leg carries a reason** and the chip never prints `—`; a shown-not-ranked figure carries `*`.
3. **His rule #7 on the sales leg** (`SALES_AGREE_REQUIRED`), an ETF never ranks, and a filing
   `STALE_FILING_QUARTERS` behind the quarter now due never ranks — HIS CALL defaults.
4. **The 🚀 coverage line + fold** (served only on the 🚀 order) count every gap class and name the most-traded.
5. **`qoq.backfill`** can no longer create a vintage mix (projection, skip reasons, all-None lists, rotation).
6. **Fates** (`sepa/symbols.py`, verified 2026-10-07 against Massive live with 8 calls + yfinance): DELISTED `DBRG`
   (delisted_utc 2026-10-01), `QRVO` (10-06), `GBTG` (09-30), `PSKY` (10-06) — each an inactive record, cached bars
   stop, and a by-CIK `active=true` search returns no successor. RENAMES `MODG → CALY` effective 2026-01-16 (same FIGI
   BBG000CPCVY1, same CIK 0000837465; CALY's first Massive bar 2026-01-16 open 14.81; Yahoo's continuous series
   2026-01-15 close 14.68 → +0.9% overnight). MODG's own Massive bars were NOT fetched (the 8-call budget); the H2
   force-fetch pulls them. WBD, BLFS, SLP not added (reference still active).
7. Supporting: `research.MIN_RESEARCH_BARS` (= 220, named), `etf_info.cached_etf_set` (one projected read, never a
   fetch).

## After the fix, before the heal (V3, MEASURED 2026-10-07 19:01 ET)

`🚀 Growth on file: 1,342 both legs · 821 one leg · 109 pending refresh · 105 blank by rule · no figure 355 (43
ETF/fund, 61 new listing, 57 not researched, 144 no quarterly figures, 7 a year past due, 31 quarters not a year
apart, 12 year-ago quarter missing) · of 2,732 · 357 figures marked * wait on a research refresh · most figures cached
2026-09-27.`

Identity `sum(classes) == scanned − no_bars` True; 0 chips with `—`; every `res_growth` legs block non-increasing.
Two-leg 1,342 sits in the spec's INFERRED range (1,300–1,441): the agreement rule unranks part of the 151.

## The heal (main session, after deploy)

`docs/sepa/keeping_data_current.md` §5: H0 selects **527** names (dry run), H1 refreshes them through the Sunday code
path (**≤ 2,108 Massive calls**), H2 splices CALY, H3–H5 re-run the earnings, caps and 13F jobs that slept.
INFERRED after H1: SNDK one-leg (sales ranked), the 205 vintage-mixed sales legs back in the ranking; the spec's
simulation puts two-leg at ~1,554.

## HIS CALL (open)

See the spec §7: the sales agreement rule (1), the stale cut (2), ranking the series figure now (3), EPS-before-sales
inside the one-leg block (4), `canslim._from_hybrid` keeping Massive revenue (5), CANSLIM C on a sign flip (6), a
missed-Sunday catch-up and keeping the laptop awake Sunday evenings (7), fundamentals under 220 bars (8), `broad` vs
`full` drift (9), earnings-date coverage (10), frozen board caps (11), and the smaller items (12). UNMEASURED — the 🚀
order is an order, not a forecast.
