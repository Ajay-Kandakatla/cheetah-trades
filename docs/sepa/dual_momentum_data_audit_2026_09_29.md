# Dual Momentum data audit + the curated foreign-head cut (2026-09-29)

Ajay, 2026-09-29, on https://pounce.ajaykandakatla.dev/dual-momentum: the page
ranked **WOLF +2,248.76%**, **BNY +1,435%** and **SPCX +474.95%** (12 months)
among its top picks. The audit below checked every name in the top 50 by 12m
return (plus AGL), then the 29 names the new Chart Maps 🏎️ Dual Momentum tab
can show beyond that set, against Massive's reference data.

**Verdict: 5 ARTEFACTS (WOLF, BNY, SPCX in the top 50; GOLD and SOLS from the
universe sweep). Every other audited name is REAL.**

## The fix (curated, never inferred)

The house rule for symbol identity (`backend/sepa/symbols.py` docstring, "WHY
THE RENAME MAP IS CURATED, NOT INFERRED") applies: a wrong entry deletes or
fabricates history on a chart real money is sized against, so every entry
names the FIGI / list_date / boundary bars it was checked against.

| Symbol | Map | Date | Evidence (short) |
|---|---|---|---|
| WOLF | `FIRST_SESSION` | 2025-09-29 | Ch.11 reorg: old FIGI BBG000BG14P4 last close 1.21 on 2025-09-26; new FIGI BBG01XLDHDP0, list_date 2025-09-29, open 18.00 |
| SPCX | `FIRST_SESSION` | 2026-06-12 | ticker reuse: SPAC ETF FIGI BBG00YJ8L8T5 to 2026-04-06, 67-day hole, SpaceX list_date 2026-06-12 |
| SOLS | `FIRST_SESSION` | 2025-10-30 | ticker reuse: 2 sub-penny OTC SOLLENSYS bars, 204-day hole, Solstice (list_date 2025-10-20, first bar 2025-10-30) |
| BK → BNY | `RENAMES` | 2026-05-21 | same FIGI BBG000BD8PN9; BK last close 137.16 (2026-05-20), BNY first open 136.46; BNY's earlier bars are the BlackRock NY Muni fund (FIGI BBG000BZF6G2) + a 104-day hole |
| AMRK → GOLD | `RENAMES` | 2025-12-02 | FIGI BBG005ZVDK48; AMRK last close 29.25 (2025-12-01), GOLD first open 30.13; GOLD's earlier bars are Barrick (FIGI BBG000BB07P9) to 2025-05-08 + a 208-day hole |

Mechanism — `sepa.prices._cut_foreign_head(df, symbol)`, PURE:

1. `symbols.first_session(symbol)` set → keep bars on/after that date, unconditionally.
2. `symbols.rename_effective(symbol)` set (the symbol is a RENAMES *target*) →
   split at `effective`; the head is **kept only if** it passes
   `splice_history`'s own two tests (gap ≤ `SPLICE_MAX_GAP_DAYS`, boundary
   ratio ≤ `SPLICE_MAX_JUMP_RATIO`). A clean BK+BNY splice and a Yahoo
   back-fill of the same company survive; a previous holder behind a hole or a
   jump is dropped. (Cutting a renamed symbol at `effective` unconditionally
   would delete the spliced BK history — rejected.)
3. Otherwise the frame comes back as the **same object**. The cut never adds,
   reorders or edits a bar.

Where it runs:

- `prices._fetch` — on the live frame **before** the splice loop. Without it
  `splice_history` keeps nothing (it keeps old bars dated before the new
  frame's first bar, and Massive's BNY/GOLD frames begin with the previous
  holder's bars in 2024).
- `prices.load_prices` — all three return paths (Mongo, parquet, fetch),
  composed as `_drop_phantom_tail(_cut_foreign_head(df, symbol))`.
- `prices.bulk_cached_frames` — per symbol (the Chart Maps frames read).

It is a **read-time self-heal** (the `_drop_phantom_tail` precedent) because
`patch_latest_closes` keeps cached frames alive past the TTL: a fetch-only fix
would never reach today's cached WOLF / SPCX / BNY. It fixes his page and the
new tab through the same reader.

### Reach — app-wide, not DM-only

The cut sits in every `load_prices` / `bulk_cached_frames` read, so the SEPA
scan, RS ranks, the 04:05 zone_store build, the lanes and the charts all see
the cut frames for these five names.

- WOLF: 252 bars after the cut → 12m `None` today, back at about +28.6% from
  2026-09-30. SPCX: 75 bars → no 6m/12m. SOLS: 12m was already `None`.
- **BNY (~90 bars) and GOLD (~208 bars) fall out of every 200-day / 52-week
  read app-wide until the one-time refetch runs.** What they read today is not
  better (BNY's 200-day and 52-week reads run on a muni fund's prices, GOLD's
  52-week read spans Barrick); the cut trades wrong numbers for an honest
  absence, and the refetch restores the real history.

### The one-time refetch (HIS CALL #6 — blocking for the two RENAMES entries)

Run right after the deploy that ships the RENAMES entries (a prod Mongo write;
precedent PPLI/DOO 2026-08-25):

    docker exec cheetah-market-app-api-1 python -c "from sepa import prices; prices.load_prices('BNY', force=True); prices.load_prices('GOLD', force=True)"

Expected: BNY becomes BK+BNY with no fund bars, 12m about +34.94%; GOLD
becomes AMRK+GOLD. If he says **no** to the refetch, the `RENAMES` block
(between the two `2026-09-29` marker comments in `symbols.py`) and the tests
named `test_renames_hunk_*` are dropped before promote; `FIRST_SESSION` and the
cut ship on their own, and BNY's +1,435% stays on his page until he decides.

### Expected effect on his page (the audit's arithmetic)

WOLF and SPCX leave the page; BNY leaves until the refetch, then sits at about
+34.9% (not a top-15 pick). LITE, ERAS and CDNA move into the top 15.

### Readers NOT covered by the read-time cut

They read frames without `load_prices` / `bulk_cached_frames`, so they still
see the raw cached frame for these five names until the refetch / next full
fetch: `supply_demand/hot_pullback.py:439,688`,
`supply_demand/premarket_entry.py:512`, `political/watch.py:208`,
`studies/*`. Not fixed here.

### Not done (HIS CALL)

- **Generic corporate-action net** (blank 12m/6m on a ≥ `_SCALE_GLITCH_RATIO`
  day or a >20-day hole): today it would catch WOLF, BNY, SPCX and GOLD and no
  REAL name (largest real day CAPR 4.71x), but it *infers* rather than curates.
- Barrick (`B`) is not in the universe; SpaceX (SPCX) and NUAI have no
  `company_names` entry (they print name None).
- The SPY-12m hurdle vs T-bill drift in `sepa/dual_momentum.py` is untouched.

### Finding the next one

`backend/scripts/dm_frame_audit.py` — read-only (one `find` over
`price_cache`, no write of any kind, no fetch). Reports every frame whose last
12m window holds a `prices._is_scale_glitch` jump or a hole longer than
`HOLE_REPORT_DAYS` (a report threshold, not a rule), and whether the curated
cut heals it. A hit is a candidate for a human check, never a verdict.

    docker exec -i -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u scripts/dm_frame_audit.py'

### Tests

`backend/tests/test_foreign_head_cut_2026_09_29.py` — maps and evidence,
the cut on every audited shape (naive, 04:00-UTC and tz-aware indexes),
NEGATIVES (unmapped symbol = same object; a REAL +177% day untouched; the five
existing renames with real boundary bars unchanged; a Yahoo back-fill kept;
output always a subset), `_fetch` cut-before-splice, every read path, the
engine end to end (WOLF/SPCX leave; an unmapped control with the same shape
keeps its return), and the audit script's read-only source guard.

## The tab's own pool (critic round) — 29/29 REAL

`compute(top_n=80)` has 29 picks outside the audited set (top 50 by 12m ∪
AGL): RXT GRAL PLSE ILMN SMTC ETON TWLO HPE APPS MRVI GH VSTS HUT NEO NTRA PENG
TER RNG PACS OKTA UCTT AMBQ CLMT PGEN CRWD IRDM ALNT ALAB NBIS. The same
Massive cross-check ran on all 29, read-only: **29/29 REAL**. No calendar hole
over 6 days in any cache; the only date where the cache and Massive's adjusted
close differ by more than 1% is 2026-09-29 (the live bar); no ticker event
inside the window. In-window split: CRWD 1:4 on 2026-07-02, adjusted. Largest
single day: RXT +226.97% on 2026-02-18, same FIGI BBG00W0JYQQ4 since 2020 and
Massive's own series agrees — a real move, not a splice. **The tab's 80 = 3
ARTEFACT (WOLF, BNY, SPCX) + 77 REAL**: every name the tab can show today was
audited.

## The audit (verbatim evidence)

Source: live `GET /sepa/dual-momentum?top_n=50&lookback_days=252&min_rs_rank=0` (4.4 s, universe 1,826, SPY 12m +16.35%, risk-on).
Per name: cached Mongo `price_cache` frame (read with find_one, no TTL gate, no writes), Massive `v2/aggs` adjusted and raw, `v3/reference/tickers/{t}` (and `?date=` as-of lookups), `v3/reference/splits`, `vX/reference/tickers/{figi}/events`.
Scripts: `dm_audit.py`, `dm_audit2.py`, `dm_audit3.py`, `dm_audit4.py` (session scratchpad, read-only). Raw output: `all.json`, `a2.json`, `a3.json`, `a4.json`, `extra.json`, `a80.json`. The re-runnable in-repo sweep is `backend/scripts/dm_frame_audit.py`.

**Result: 3 of the top 50 are ARTEFACTS (WOLF, BNY, SPCX). 47 are REAL, plus AGL (pick #13). No UNSURE.**
REAL here means one security across the whole window (same FIGI), any split correctly adjusted, and the cache matching Massive's adjusted closes to within 0.9% on every date except today's in-progress bar. The only >1% gaps (LITE, VICR, AAOI, NUAI, AEHR, VIAV) are all on 2026-09-29, the live bar.

## The five named

**WOLF +2,248.76%: ARTEFACT (Chapter 11 reorg, old equity cancelled).**
- As of 2025-09-26, Massive has old Wolfspeed equity: FIGI BBG000BG14P4, listed 1993-02-09. Its last bar that day closed at **1.21** on 118.5M shares.
- The current WOLF is FIGI **BBG01XLDHDP0**, `list_date` **2025-09-29**, with a ticker event on 2025-09-29. First bar: open 18.00, close 22.10.
- No split record exists. The +1,726% day on 2025-09-29 alone is **92% of the 12m log gain**.
- The 12m window starts on exactly 2025-09-26, the last bar of the cancelled equity. Massive's own series gives the same number (+2,238%), so the splice is at the provider, not in our cache.
- **It expires by itself next session.** On 2026-09-30 the window starts 2025-09-29, which gives about **+28.6%**. The 2y frame still holds about 250 bars of the cancelled equity (priced 1 to 2 dollars) for charts and zones.
- Real return since listing: 22.10 to 28.42 (**+28.6%**).

**BNY +1,435% (6m +1,355%): ARTEFACT (ticker reuse + unhandled rename BK->BNY).**
- As of both 2025-06-16 and 2026-02-06, BNY was **BlackRock New York Municipal Income Trust** (FUND, FIGI BBG000BZF6G2), trading around $10 on 30k to 165k shares a day.
- Our cache holds **340 fund bars** (2024-09-30 to 2026-02-06), then a **104-day hole**, then Bank of New York Mellon from 2026-05-21 (open 136.46, 3.0M shares).
- BNY Mellon is FIGI BBG000BD8PN9, with ticker event **2026-05-21 BK->BNY**. The inactive listing shows BK `delisted_utc` 2026-05-21 with the same FIGI.
- BK is **not** in the universe and not cached, so BNY Mellon's pre-May history is missing.
- Massive BK aggs: 411 bars, 2024-09-30 to 2026-05-20, last close **137.16**. BNY's first open is **136.46**: consecutive sessions, -0.5%, which passes `splice_history` (ratio 1.005, 1 day).
- Spliced BK+BNY returns: **12m +34.94%, 6m +28.32%, 3m +2.21%**. With those numbers BNY is not a top-15 pick.

**SPCX +474.95% (name None): ARTEFACT (ticker reuse).**
- As of 2025-07-22 and 2026-04-06, SPCX was **The SPAC and New Issue ETF** (ETF, FIGI BBG00YJ8L8T5), trading around $22 on 1k to 6k shares a day. Its last bar was 2026-04-06.
- Then comes a **67-day hole**. SpaceX (`list_date` **2026-06-12**, XNAS, ticker event 2026-06-12) printed its first bar at open 150.00 / close 160.95 on 522M shares, which is 302,678x the ETF's 50-day volume.
- SpaceX has only **75 bars**, so a genuine 12m or 6m return does not exist.
- Since its first close, SpaceX is **-9.56%**.
- `name None` is because `company_names` has no entry for the new security.

**AGL (6m +874.61%, 12m +187.38%, pick #13): REAL.**
- The **1:25 reverse split** on 2026-03-31 (Massive splits record, ticker event the same day) is correctly adjusted in both the cache and Massive: raw 0.3214 x 25 = 8.035 on 2026-03-30, and the cache matches Massive adjusted exactly across the split.
- The 6m window starts on **2026-03-30 at 8.035**. The move is continuous:
  - 4/1 +23%, 4/6 +30%, 4/7 +19%
  - **5/7 +117.8%** on 12.4x volume (gap-open +56.5%)
  - to 78.31
- The same FIGI BBG00HCYVQQ4 runs through the whole window. The catalyst is not in Massive news.

**SNDK +1,668.53%: REAL.**
- First bar is 2025-02-24, the regular-way spin-off from WDC (`list_date` 2025-02-13 is when-issued).
- The 12m window starts 2025-09-26 at 97.12, **seven months after the spin**, so the spin date never enters the 12m arithmetic.
- There are no splits and no events. The largest single day is +27.6% (1/6/26, 8.5% of the log gain), so this is a compounding run with no jump.
- Massive's same calculation gives +1,678.9%.

## Every top-50 name (by 12m return) + AGL
| # | Sym | 12m cache | 12m Massive | first bar | 12m start (close) | largest 1-day (date, %, vol x50, share of 12m log gain) | splits / ticker events in window | Verdict | Note |
|---|---|---|---|---|---|---|---|---|---|
| 1 | WOLF | 2248.76 | 2238.43 | 2024-09-30 | 2025-09-26 (1.21) | 2025-09-29, 1726.45%, Nonex, 0.92 | 2025-09-29 ->WOLF | ARTEFACT (Ch.11 reorg, old equity cancelled) |  |
| 2 | SNDK | 1668.53 | 1678.9 | 2025-02-24 | 2025-09-26 (97.12) | 2026-01-06, 27.56%, 2.09x, 0.085 | none | REAL | spin-off 2025-02-24 is 7 months BEFORE the window; biggest day +27.6% |
| 3 | AXTI | 1648.28 | 1641.95 | 2024-09-30 | 2025-09-26 (4.66) | 2026-04-16, 29.95%, 1.57x, 0.092 | none | REAL |  |
| 4 | BNY | 1435.2 | 1434.16 | 2024-09-30 | 2025-06-16 (9.63) | 2026-05-21, 1262.55%, 42.31x, 0.956 | 2026-05-21 ->BNY | ARTEFACT (ticker reuse + unhandled BK->BNY rename) |  |
| 5 | MRNA | 722.42 | 716.72 | 2024-09-30 | 2025-09-26 (24.49) | 2026-08-19, 176.97%, 27.47x, 0.483 | none | REAL | 8/19 +177% = Moderna/Merck phase-3 mRNA cancer vaccine (Massive news) |
| 6 | TXG | 657.81 | 656.48 | 2024-09-30 | 2025-09-26 (11.72) | 2025-11-07, 17.31%, 2.89x, 0.079 | none | REAL |  |
| 7 | SLS | 600.31 | 604.91 | 2024-09-30 | 2025-09-26 (1.63) | 2026-05-13, 25.1%, 5.05x, 0.115 | none | REAL |  |
| 8 | MU | 581.82 | 582.58 | 2024-09-30 | 2025-09-26 (157.27) | 2026-05-26, 19.29%, 1.56x, 0.092 | none | REAL |  |
| 9 | TWST | 571.07 | 572.46 | 2024-09-30 | 2025-09-26 (26.91) | 2026-08-19, 22.64%, 2.0x, 0.107 | none | REAL |  |
| 10 | ERAS | 566.11 | 564.9 | 2024-09-30 | 2025-09-26 (2.08) | 2026-04-28, -48.3%, 8.88x, -0.348 | none | REAL | run is Jan-26 (+42% 1/7); 4/28 -48% |
| 11 | IOVA | 551.18 | 563.51 | 2024-09-30 | 2025-09-26 (2.11) | 2026-08-06, 43.09%, 4.92x, 0.191 | none | REAL |  |
| 12 | LITE | 519.61 | 506.46 | 2024-09-30 | 2025-09-26 (160.75) | 2025-11-05, 23.57%, 3.55x, 0.116 | none | REAL |  |
| 13 | VICR | 501.98 | 490.5 | 2024-09-30 | 2025-09-26 (48.67) | 2025-10-22, 30.33%, 8.28x, 0.148 | none | REAL |  |
| 14 | MXL | 484.59 | 484.54 | 2024-09-30 | 2025-09-26 (16.09) | 2026-04-24, 76.12%, 18.34x, 0.321 | none | REAL | 4/24/26 +76% on 18x vol |
| 15 | SPCX | 474.95 | 476.92 | 2024-09-30 | 2025-07-22 (25.3188) | 2026-06-12, 632.26%, 302678.09x, 1.138 | 2026-06-12 ->SPCX | ARTEFACT (ticker reuse: SPAC ETF -> SpaceX IPO) |  |
| 16 | KOD | 460.92 | 458.86 | 2024-09-30 | 2025-09-26 (15.8) | 2026-09-28, 177.96%, 57.08x, 0.593 | none | REAL | 9/28 +178% on 57x vol, same FIGI, no split (catalyst not in Massive news) |
| 17 | ORKA | 445.95 | 441.88 | 2024-09-30 | 2025-09-26 (15.2) | 2025-09-29, 26.91%, Nonex, 0.14 | none | REAL |  |
| 18 | CLYM | 442.02 | 437.56 | 2024-10-03 | 2025-09-26 (2.13) | 2025-12-12, 30.43%, 12.55x, 0.157 | none | REAL | ELYM->CLYM 2024-10-03, before window |
| 19 | PRAX | 438.02 | 436.56 | 2024-09-30 | 2025-09-26 (52.44) | 2025-10-16, 183.71%, 37.85x, 0.62 | none | REAL | 10/16/25 +184% on 38x vol (data readout), same FIGI |
| 20 | SYRE | 423.37 | 423.83 | 2024-09-30 | 2025-09-26 (16.24) | 2026-04-13, 23.36%, 6.86x, 0.127 | none | REAL | AGLE->SYRE 2023, outside |
| 21 | BFLY | 376.12 | 375.64 | 2024-09-30 | 2025-09-26 (2.01) | 2026-06-18, 55.87%, 11.79x, 0.284 | none | REAL |  |
| 22 | RVMD | 360.37 | 356.72 | 2024-09-30 | 2025-09-26 (43.92) | 2026-04-13, 41.35%, 7.13x, 0.227 | none | REAL |  |
| 23 | OMER | 334.53 | 330.72 | 2024-09-30 | 2025-09-26 (4.46) | 2025-10-15, 154.15%, 133.58x, 0.635 | none | REAL | 10/15/25 +154% on 134x vol, same FIGI |
| 24 | CDNA | 329.4 | 328.04 | 2024-09-30 | 2025-09-26 (14.93) | 2026-07-16, 35.6%, 5.55x, 0.209 | none | REAL |  |
| 25 | WDC | 325.87 | 324.68 | 2024-09-30 | 2025-09-26 (106.88) | 2026-01-06, 16.77%, 1.99x, 0.107 | none | REAL |  |
| 26 | STX | 323.22 | 322.02 | 2024-09-30 | 2025-09-26 (217.51) | 2026-01-28, 19.14%, 3.91x, 0.121 | none | REAL |  |
| 27 | DELL | 319.4 | 318.45 | 2024-09-30 | 2025-09-26 (130.76) | 2026-05-29, 32.76%, 5.24x, 0.198 | none | REAL |  |
| 28 | BE | 314.05 | 315.07 | 2024-09-30 | 2025-09-26 (70.32) | 2026-04-29, 27.21%, 1.93x, 0.169 | none | REAL |  |
| 29 | ASX | 297.22 | 297.76 | 2024-09-30 | 2025-09-26 (11.17) | 2026-05-26, 11.89%, 1.86x, 0.081 | none | REAL |  |
| 30 | AAOI | 296.49 | 291.15 | 2024-09-30 | 2025-09-26 (25.77) | 2026-02-27, 56.88%, 4.97x, 0.327 | none | REAL |  |
| 31 | DOCN | 296.35 | 293.49 | 2024-09-30 | 2025-09-26 (35.1) | 2026-05-05, 40.4%, 3.25x, 0.246 | none | REAL |  |
| 32 | AMD | 289.72 | 286.81 | 2024-09-30 | 2025-09-26 (159.46) | 2025-10-06, 23.71%, Nonex, 0.156 | none | REAL |  |
| 33 | FORM | 283.39 | 280.16 | 2024-09-30 | 2025-09-26 (35.28) | 2026-07-30, 26.28%, 1.42x, 0.174 | none | REAL |  |
| 34 | ATEX | 276.95 | 277.32 | 2024-09-30 | 2025-09-26 (21.63) | 2026-06-11, 25.72%, 3.75x, 0.172 | none | REAL |  |
| 35 | NUAI | 276.36 | 270.38 | 2025-08-13 | 2025-09-26 (1.84) | 2025-10-09, 83.77%, Nonex, 0.459 | none | REAL | NEHC->NUAI 2025-08-13, before window; frame starts at rename; name None = company_names gap |
| 36 | ABSI | 254.58 | 254.58 | 2024-09-30 | 2025-09-26 (2.73) | 2026-06-24, 35.96%, 7.35x, 0.243 | none | REAL |  |
| 37 | BAND | 253.94 | 251.48 | 2024-09-30 | 2025-09-26 (17.52) | 2026-04-30, 52.11%, 8.47x, 0.332 | none | REAL |  |
| 38 | ICHR | 253.01 | 250.3 | 2024-09-30 | 2025-09-26 (17.28) | 2026-02-10, 32.72%, 7.32x, 0.224 | none | REAL |  |
| 39 | AEHR | 250.83 | 246.37 | 2024-09-30 | 2025-09-26 (30.19) | 2026-07-21, 27.86%, 2.09x, 0.196 | none | REAL |  |
| 40 | VIAV | 247.17 | 238.49 | 2024-09-30 | 2025-09-26 (12.21) | 2025-10-30, 22.32%, 6.95x, 0.162 | none | REAL |  |
| 41 | IBRX | 241.54 | 239.96 | 2024-09-30 | 2025-09-26 (2.54) | 2026-02-18, 41.86%, 2.6x, 0.285 | none | REAL |  |
| 42 | RLAY | 240.04 | 239.94 | 2024-09-30 | 2025-09-26 (5.17) | 2025-11-24, 20.68%, 1.91x, 0.154 | none | REAL |  |
| 43 | MBX | 230.61 | 230.98 | 2024-09-30 | 2025-09-26 (17.51) | 2026-06-11, 20.2%, 4.63x, 0.154 | none | REAL |  |
| 44 | COHU | 229.67 | 227.43 | 2024-09-30 | 2025-09-26 (20.56) | 2026-07-30, 18.07%, 1.69x, 0.139 | none | REAL |  |
| 45 | INTC | 227.39 | 228.42 | 2024-09-30 | 2025-09-26 (35.5) | 2026-04-24, 23.6%, 2.99x, 0.179 | none | REAL |  |
| 46 | LQDA | 227.05 | 225.37 | 2024-09-30 | 2025-09-26 (21.8) | 2026-05-11, 25.6%, 5.84x, 0.192 | none | REAL |  |
| 47 | UMC | 224.14 | 225.0 | 2024-09-30 | 2025-09-26 (7.54) | 2026-01-20, 15.91%, 2.74x, 0.126 | none | REAL |  |
| 48 | INBX | 218.79 | 220.96 | 2024-09-30 | 2025-09-26 (32.68) | 2025-10-24, 102.01%, 26.28x, 0.606 | none | REAL | 10/24/25 +102% on 26x vol |
| 49 | REPL | 215.31 | 213.33 | 2024-09-30 | 2025-09-25 (4.05) | 2026-07-31, 107.02%, 6.24x, 0.634 | none | REAL | 7/31/26 +107%; 500 bars (Massive also 1 session short) |
| 50 | MRVL | 214.54 | 213.55 | 2024-09-30 | 2025-09-26 (83.17) | 2026-06-02, 32.52%, 4.02x, 0.246 | none | REAL |  |
| pick13 | AGL | 187.38 | 186.06 | 2024-09-30 | 2025-09-26 (27.25) | 2026-05-07, 117.81%, 12.37x, 0.737 | 2026-03-31 25:1; 2026-03-31 ->AGL | REAL | 1:25 reverse split 2026-03-31 correctly adjusted (raw 0.3214 x25 = 8.035); 5/7 +118% on 12x vol |

## Found by the universe-wide sweep (outside the top 50, same defect class)
Swept all 1,826 cached frames for a 12m window containing a >+150% or <-75% day, or a calendar hole of more than 20 days.
- **GOLD (12m rank 94, +133.75%): ARTEFACT, ticker reuse.**
  - Barrick (FIGI BBG000BB07P9) is in the frame to 2025-05-08 (close 18.86), then a 208-day hole.
  - Gold.com (ex-AMRK, FIGI BBG005ZVDK48, ticker event 2025-12-02) starts 2025-12-02 at open 30.13.
  - The 12m number is Gold.com 43.15 / Barrick 18.46.
  - AMRK's last bar was 2025-12-01, close 29.25. The next session is 2025-12-02, open 30.13 (+3.0%), so it would splice cleanly.
  - Barrick has traded as `B` since 2025-05-09. `B` is not in the universe (HIS CALL).
- **SOLS (12m None): ARTEFACT at the head of the frame.**
  - Two OTC SOLLENSYS CORP bars (2025-03-31 to 2025-04, sub-penny) are followed by a 204-day hole and then Solstice Advanced Materials (Honeywell spin, `list_date` 2025-10-20, first bar 2025-10-30).
  - Gives a fake +48,739,900% day. It does not reach the DM rank because there are fewer than 253 bars.
- REAL (checked, same FIGI, no split): RXT +227% on 2026-02-18 (322x volume), CAPR +371% on 2025-12-03, SION -91% on 2026-08-10 (73x volume).

## Proposed WP-DATA (fixes his page AND the new tab, since both read `prices.load_prices`)
House pattern: curated with evidence, never inferred (`sepa/symbols.py` docstring, "WHY THE RENAME MAP IS CURATED").

1. **`sepa/symbols.py` RENAMES: add two entries with boundary evidence** (both checks run and passed):
   - `"BK": ("BNY", "2026-05-21", ...)`: BK last bar 2026-05-20 close 137.16; BNY first 2026-05-21 open 136.46; same FIGI BBG000BD8PN9.
   - `"AMRK": ("GOLD", "2025-12-02", ...)`: AMRK last 2025-12-01 close 29.25; GOLD first 2025-12-02 open 30.13; Gold.com FIGI BBG005ZVDK48.
2. **RENAMES alone does NOT heal BNY or GOLD.**
   - `splice_history` keeps `old_df[old_df.index < new_df.index[0]]`, and Massive's BNY/GOLD frames begin 2024-09-30 with the *previous holder's* bars. The head is therefore empty and the function returns the reused-ticker frame unchanged.
   - Fix: in `prices._fetch`, trim the live frame to `index >= effective` of its RENAMES entry **before** splicing.
   - Measured safe: Massive's frames for the five existing new symbols start exactly on their `effective` (ECHO 2026-06-24, XYZ 2025-01-21, DOO 2025-12-08, PPLI 2026-06-04, GTM 2025-05-13), so the trim is a no-op for them.
3. **New curated map in `sepa/symbols.py`** for bars that belong to a different security under the same ticker. Each entry is the first session of the current security plus its evidence:
   - `WOLF: 2025-09-29` (reorg, new FIGI BBG01XLDHDP0)
   - `SPCX: 2026-06-12` (ETF BBG00YJ8L8T5 -> SpaceX)
   - `SOLS: 2025-10-30`
   - A RENAMES `effective` also counts as a first session for the new symbol.
4. **Apply the cut at READ time** in `prices.load_prices` (Mongo, parquet and fetch paths) and in `prices.bulk_cached_frames` (the Chart Maps board and key-levels read path), next to `_drop_phantom_tail`.
   - Reason: `patch_latest_closes` resets the 20h TTL, so a cached frame may never be fully refetched. A fetch-time-only fix would not reach today's cached WOLF, SPCX or BNY. Precedent: `_drop_phantom_tail` is a read-time self-healing guard.
5. **One-time refetch after deploy:** `load_prices("BNY", force=True)` and `load_prices("GOLD", force=True)`. This writes to prod Mongo, so it is a deploy step for his OK. Only a full fetch can splice in the BK and AMRK history. Until it runs, the read-time cut leaves BNY at about 90 bars, which means 12m = None and it drops off the page.
6. Expected effect on his page today (top 15 by score):
   - WOLF leaves: 252 bars after the cut, so no 12m. It returns at about +28.6% from 2026-09-30.
   - BNY falls to +34.9%.
   - SPCX leaves: 75 bars.
   - Picks 16 to 18 (LITE, ERAS, CDNA) move up.
7. Tests (NEGATIVE): a symbol not in the maps comes back byte-identical. The 5 existing RENAMES are unchanged. A >1.35x boundary is still refused. The cut never adds bars. SPCX `return_12m` is None, so it cannot pass `abs_mom_pass`. BNY's pre-2026-05-21 bars all come from BK.

## HIS CALL
- **Generic safety net (not a curated entry):**
  - Proposal: withhold `return_12m`/`6m` (blank, reason `corporate_action_suspected`) when the window holds a close-to-close ratio of 5x or more (the existing `prices._SCALE_GLITCH_RATIO`) or a calendar hole of more than 20 days. This mirrors `board_metrics.SPLIT_SUSPECT_RATIO`: "blank rather than arithmetically true, economically false".
  - Today it would catch WOLF (18.3x), BNY (13.6x, 104 days), SPCX (7.3x, 67 days) and GOLD (208 days). It would touch no REAL name: the largest real day is CAPR at 4.71x, and in the top 50 it is PRAX at 2.84x.
  - It is inferred rather than curated, which is why it is his decision.
- Barrick (`B`) is missing from the universe.
- NUAI and the new SpaceX security have no `company_names` entry (they show as name None).
- NEHC->NUAI (2025-08-13) could be a RENAMES splice for older history. The 12m is unaffected, so this is low priority.
- The picks rank is by the composite `score` (50/25/15/10 blend of 12m/6m/3m/1m), not by 12m return. The new tab should print the served `rank`.
- Zone implication (inferred, not probed): the S/D zone engine reads the same daily frames. Until the cut lands, it could form demand bands from the other security's bars: SPCX around $22 (ETF), BNY around $10 (fund), WOLF around $1 to 2 (cancelled equity). The new tab must not ship ahead of WP-DATA for these three names, or it must show them as 'no demand band'.
