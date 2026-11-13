# 💎 Under Value — growth off a near-zero year-ago quarter, and the quarter it comes from (2026-11-12)

## The ask, verbatim

> "We got wrong numbers for Joby in sales in the undervalye can you verfy"

## Verdict

**The JOBY number was wrong.** The board printed **+257,493%**: FY2026 Q2 revenue of $38.6M measured against a **$15,000** year-ago quarter. The percentage is arithmetic, not growth.

**JOBY's right number is about +144%** (FY2026 Q3, from Yahoo's TTM). The board held Q2's +257,493% off a $15K quarter. At today's P/S that is PSG ≈ 0.25, so JOBY would not be on 💎 after a refresh either.

How the +144% is built (read-only probe, 2026-11-12):

| | value |
|---|---|
| Yahoo TTM revenue (`rev_ttm`, through 2026-09-30) | $148.81M |
| Q4'25 + Q1'26 + Q2'26 (research doc) | $93.72M |
| FY2026 Q3 = TTM − those three | $55.09M |
| FY2025 Q3 (year-ago) | $22.574M |
| YoY | **+144.0%** (Yahoo `revenueGrowth` 1.44) |
| P/S at the live cap | 35.7x |
| PSG = 35.7 / 144 | **≈ 0.25** (bar is `UNDERVALUE_MAX_PSG` = 0.15) |

So two things were wrong at once: the growth came off a near-zero base, and it came from an OLDER quarter (FY2026 Q2, to 2026-06-30) than the revenue behind P/S (Yahoo TTM, to 2026-09-30). The research cache lags a quarter in earnings season; refreshing it is a cadence change and stays HIS CALL (#4 below).

`UNDERVALUE_GROWTH_CAP_PCT` (300) already capped growth for the RATIO, so JOBY's PSG was 35.7 / 300 = 0.119 — still under 0.15. The cap tamed the ratio but the tile still printed the raw %, and the 120-name screening cut still ranked on it.

## The guard — ONE helper, the app's existing floor

`sepa.bonde.headline_sales_read(f)` decides whether a stored `sales.growth_yoy_pct` may be printed or ranked as growth. It reads a research fundamentals row (`research.decision_snapshot` or `scan_row["fundamentals"]`), is pure, and never raises. Reasons, first match wins:

| reason | meaning |
|---|---|
| `no_figure` | no finite stored growth (None / NaN / inf) |
| `pair_mismatch` | the HEADLINE quarter and its year-ago quarter are not a year apart — labels not four apart, or end dates not 365 ± `capital_returns.SAME_QUARTER_DAYS` days apart |
| `base_non_positive` | year-ago revenue ≤ $0 (`sales.py` divides by `abs(base)`, so JXN's −$471M read +135.7%) |
| `base_too_small` | 0 < year-ago revenue < `bonde.MIN_MATERIAL_BASE_REV` ($1M) |
| `base_missing` | the year-ago quarter is a hole, or its revenue slot is empty |

- **The floor is `bonde.MIN_MATERIAL_BASE_REV` = $1,000,000 — his owner setting**, already used by 📈 Bonde (as a ranking flag), 📉 fallen and 🛡️ resiliency. No new number.
- **Why not `qoq.MIN_REV_BASE` ($1,000):** it is a divide-by-zero guard, not a materiality test, and JOBY's $15,000 passes it (`bonde.py` says so beside the constant).
- **Why the headline pair with end dates, not `bonde._pair_mismatch`:** the printed % uses only the headline pair (slot 0 vs slot 4). `_pair_mismatch` also refuses on the PRIOR pair, which would make the served words false, and it checks labels only, so it misses a CRDO-shape relabel (labels four apart, quarters 455 days apart). The helper calls `qoq.period_ok(periods, (HEADLINE_PAIR,), ends=ends)`, and `qoq.headline_hole` to tell a hole (`base_missing`) from a misalignment.
- A legacy row with no `rev_q_series` at all is accepted by default (the `qoq.yoy_pairs_ok` rule); measured 0 such candidates live.
- `sepa/sales.py` is untouched, so `sales.score` and the tiers do not move anywhere in the app.

## What 💎 does now (`chart_maps/board.py::undervalue_tiles`)

1. Reads `research.decision_snapshot` (it carries the quarterly series) instead of `sales_snapshot`. Same admission test as before: Bonde tier strong/explosive and a truthy growth.
2. Every admitted name goes through `headline_sales_read` **BEFORE the 120-name cut** (`UNDERVALUE_MAX_CANDIDATES`):
   - `no_figure` → skipped, uncounted — exactly like the existing `ratio is None` path. A NaN growth used to be truthy and `NaN > 0.15` is False, so it could have passed; measured 0 live.
   - not comparable → EXCLUDED with a count and its name. This is the board's existing pattern ("missing shares or revenue excludes with a count — never a made-up ratio"). A name with no comparable growth has no PSG, and PSG is the board's only admission test, so showing it with a blank growth cell would put a name on 💎 that passed nothing.
   - comparable → the same sort and cut on growth as before.
3. New served keys: `growth_not_comparable` (count) and `growth_excluded` — per name `{symbol, reason, base_state, base_rev, latest_rev, period}`, dollars only, never the arithmetic %.
4. One note sentence, inserted after the missing-data sentence (absent when nothing is excluded, so the note is byte-identical then):
   > "N more had sales growth off a year-ago quarter under $1M, at or below $0, missing on file or not a year before the latest quarter on file (NAMES) — a percentage off that base is arithmetic, not growth, so they are excluded too, never ranked."
   Only the clauses for reasons present appear. The $1M is printed from the constant.

Why before the cut: the cut itself ranked on the fake %. On 2026-11-12, 11 tiny/negative-base names held top-120 slots; excluding them first lets 11 real growers into the screen (HIVE, LPTH, DVN, WVE, MXL, PHAT, OSCR, FTK, QXO, TGTX, FEIM), and HIVE, PHAT and FTK pass PSG on cached revenue.

Live effect (probe, 2026-11-12): 15 non-comparable names across 515 candidates — JOBY, FDMT, SEPN, QUBT, SBET, CRSP, SERV, DNTH, JXN, MDWD, DJT, AVR, PDLB, IE, LWLG. Seven were ON the board only because of the fake growth: JOBY, FDMT, SEPN, SBET, SERV, JXN (negative base) and MDWD (latest quarter ended 2015-12-31).

`psg_ratio`, `_uv_band_state`, `UNDERVALUE_MAX_PSG`, `UNDERVALUE_GROWTH_CAP_PCT`, `_sales_badge` and every threshold are untouched. For a comparable name every printed number is identical.

## The `Rev quarter` stat

Each 💎 tile carries a new stat keyed `Rev quarter` (`board.UV_QUARTER_STAT_KEY`), right after `Rev YoY`. Not keyed `Growth`: `cardLadder.ts` folds that key into ▸ more. The words come from `_uv_quarter_word`, first match wins:

| state | words |
|---|---|
| unknown | `quarter not on file` |
| stale_filing | `FY2021 Q1 (to 2021-03-31) · a latest filing 4 or more quarters past due` |
| not_dated | `FY2026 Q2 · not dated on file` |
| ttm_unknown | `FY2026 Q2 · P/S revenue quarter not on file` |
| growth_older | `FY2026 Q2 (to 2026-06-30) · older than the P/S revenue (to 2026-09-30)` |
| ttm_older | `… · newer than the P/S revenue (to DATE)` |
| same | `FY2026 Q2` |

- "Same quarter" = within `capital_returns.SAME_QUARTER_DAYS` (45 days), the app's definitional rounding.
- The P/S date is Yahoo's own `mostRecentQuarter` stamp, stored beside the TTM as `ttm_q_end` (`rev_ttm.quarter_ends`), never a computed quarter.
- **Stale filing — 🛡️'s rule and words, borrowed by name.** `_uv_stale_clock()` lazily imports `chart_maps.resiliency_tab` and returns `(expected_quarter_idx(today), STALE_FILING_QUARTERS)`; a latest fiscal quarter that many or more behind the expected one gets 🛡️'s served words. Any failure returns `(None, None)` and the board still builds. The rule is one-sided (a fiscal year labelled ahead is never flagged), exactly as on 🛡️.
- It is a LABEL only. SE (tile #14 on 2026-11-12, PSG 0.010, +147%, latest quarter 2021-03-31) has a material base, so it stays ranked and now reads "a latest filing 4 or more quarters past due". Excluding it is HIS CALL #7.

## rev_ttm `ttm_q_end` rollout — no forced refresh

- `rev_ttm` now writes `ttm_q_end` beside `rev_ttm` on every fetch (`bulk` fill and the Sunday `warm`). The read path, freshness test, fill box and fill set are unchanged.
- A doc cached before this change has no date until its normal TTL refetch (≤ 7 days). On 2026-11-12, 158 of 657 docs were fresh: those tiles read "P/S revenue quarter not on file" for up to a week. Stale docs refilled by the board's 8 s fill box get dated on their first fill. Both are expected, not defects. Treating a fresh undated doc as missing would change the fill set — HIS CALL #4b.
- The cron container runs `rev_ttm.warm` (Sunday 22:30). Deploy `cron` with `api`, or Sunday's warm keeps writing undated docs that stay "fresh" for 7 days.

## Found while measuring: the warm/TTL race (pre-existing, NOT fixed)

The Sunday warm skips docs younger than exactly 7 days. The 2026-11-01 walk wrote 384 docs from 22:30:01 to 08:40 the next morning (1 s throttle), so at 2026-11-08 22:30 every one of them was seconds-to-hours under 7 days and was skipped; the warm filled only 41, and the 384 expired overnight. Net effect: most strong/explosive names are re-warmed every OTHER Sunday, with the board's 8 s fill box covering only the top 120 in between. Fixing it is a cadence change — HIS CALL #4c.

## Surfaces

- **Fixed:** 💎 P/S ÷ growth (this doc); 🏷️ vs peers (`undervalue_peers.q_yoy_pct` now delegates to the same helper — a tiny base lands in the existing `q_growth_not_read` bucket; moves nothing live today); Desk report module C, by inheritance (it reads the 💎 stats).
- **Not fixed (HIS CALL #5):** `board._sales_badge` on 🪜 Deep Demand / Gabbar Levels / 📉 topping / key-levels tiles, 🔥 Hottest, 🚀 growth tracker (guards ≤ 0 only), knife-watch push text, and a few more readers of `sales.growth_yoy_pct`. 📈 Bonde and 📉 fallen already flag the base by design.

## Tests

- `backend/tests/test_headline_sales_read_2026_11_12.py` — the helper and `rev_ttm` (engine).
- `backend/tests/test_chart_maps.py` 💎 section — JOBYX (passes PSG without the guard, excluded with it, no "257493" anywhere), a normal base unchanged byte for byte, NEGB / NULLB / SKEWX excluded with their words, PRIORX kept, NaN / inf skipped uncounted, the pre-cut proof (one slot, CHEAP keeps it), the quarter words and the 45-day boundary, the stale word and its boundary from `STALE_FILING_QUARTERS`, OLDX labelled but not excluded, `quarter_ends` failing, and a source guard.
- The 2026-09-29 golden FILE is untouched: the byte-identity test strips only the new fields after asserting their values (0 excluded, `quarter not on file`). The `psg_ratio` and `_uv_band_state` source hashes stay pinned; `undervalue_tiles` was edited on purpose and is pinned by the payload.

## HIS CALLs

1. **Exclude vs show blank** — 💎 now EXCLUDES (count + names) any name whose year-ago quarter is under $1M, ≤ $0, missing, or not a year before the latest quarter. On 📈 Bonde the same $1M is only a ranking flag.
2. **Before the 120-name cut** (11 real growers enter the screen) vs after (identical screened set, the board just loses the 7).
3. **P/S and growth from different quarters and sources** (Yahoo TTM vs Massive quarter) — only LABELLED here. Options: P/S from the same Massive quarters (moves every PSG), or exclude/blank a name whose growth quarter is older.
4. **Data freshness** — (a) refreshing the research cache in earnings season (JOBY would read ≈ +144% and still not be on 💎); (b) treat a fresh undated rev_ttm doc as missing; (c) the warm/TTL race.
5. **Roll the helper out** to the other surfaces listed above.
6. **`UNDERVALUE_GROWTH_CAP_PCT` = 300** untouched — keep, or raise the $1M floor.
7. **Stale filings** — SE is on the board on a 2021 quarter. Yes → add `stale_filing` to the exclusion list, reusing 🛡️'s `STALE_FILING_QUARTERS` + `expected_quarter_idx`.
8. **"Mid and small caps … accelerating … down in the past"** — not built; needs his definitions (accelerating = the Bonde flag? down = 📉's 40% below the 52-week high, now or at some point? the ceiling for "mid"?).
