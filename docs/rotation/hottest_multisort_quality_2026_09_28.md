# 🔥 Hottest — multi-column sort + ⓘ Quality (backend) — 2026-09-28

Ajay 2026-09-28, with a screenshot of the 🔥 Hottest name rows:

> "Can you fix the horizontal columns hiding and also can you help me with
> multi column sort also can you help with info icon on the quality?"

This doc covers the BACKEND half: the wire format and ordering rules of the
multi-column sort, and the served `quality_info` block behind the ⓘ. The
column-visibility fix is frontend-only
([`hottest_columns_visible_2026_09_28.md`](hottest_columns_visible_2026_09_28.md)).

## Wire format

`GET /rotation/hottest?sort=<key>&dir=<desc|asc>&then_by=<key:dir,key:dir>`

* `sort` + `dir` are the PRIMARY key, exactly as before. Without `then_by` the
  board is **order-identical to the pre-change module at every level** — pinned
  for every key in `SORT_KEYS` × both directions by a golden captured from the
  unmodified module (`backend/tests/fixtures/hottest_single_sort_order_golden_2026_09_28.json`).
* `then_by` — comma-separated `key:dir`; a bare `key` means `desc`.
* Served: `sorted_by` / `sorted_dir` (unchanged), `sorted_then_by:
  [{key, dir}]` = what was **applied**, `sort_max_keys` = `MAX_SORT_KEYS` (3).

Examples:

| request | `sorted_then_by` |
|---|---|
| `sort=rel_5d&dir=desc` | `[]` |
| `sort=eq_score&then_by=q_eps_yoy:desc,net_margin:asc` | `[q_eps_yoy desc, net_margin asc]` |
| `sort=sales_tier&then_by=bogus:asc,sales_tier:asc,rel_5d:sideways,amd:desc,q_eps_yoy` | `[rel_5d desc, q_eps_yoy desc]` |
| `sort=pre_1d&then_by=rel_5d:asc` with no pre-market leg | `[]` (primary demoted to `rel_5d`; the tie-break is its duplicate) |

## Plan rules (`rotation/hottest.py`)

* `parse_then_by(raw)` — syntax only; a non-string (a FastAPI Query object on a
  direct call) or empty string is `[]`.
* `_sort_plan(...)` — THE one validator, run after the primary's validation and
  the `pre_1d` demotion. A tie-break must be in `SORT_KEYS` (🌀 AMD is not, so it
  can never break a tie either — it was measured INVERTED); `pre_1d` is dropped
  while the pre-market leg is idle; a duplicate (of the primary or an earlier
  tie-break) is dropped, first mention wins; a bad dir becomes `desc`. An
  invalid entry never consumes a slot. The plan stops at `MAX_SORT_KEYS`.
  Never a 4xx — the served list is the truth.
* `_multi_sorter(plan)` — a one-key plan IS `_sorter(key, dir)`; longer plans
  concatenate each key's `(present, value)` pair, so a missing value sorts
  LAST within the tie of the keys before it, per key, in both directions.
* ONE comparator for all four levels: names, industries, sectors, rosters.
  Truncation to `names` per group still happens after the sort.

## Exact ties

* **Name rows → symbol A→Z** (`_rank_names`: pre-sort by symbol, then the
  stable `reverse=True` sort). A no-op in prod — `tracker` already serves every
  grain's `symbols` A→Z — so single-key order is unchanged. Never flips with
  the direction.
* **Group rows (sector / industry / roster) → their stored input order**, as
  they always have. Group rows never carry 5 of the 14 sort keys
  (`next_earnings`, `traction`, `ret_1d`, `ret_5d`, `ret_21d`), so a **Next ER**
  sort (the only one of those five with a visible header) leaves sectors and
  rosters in their stored order — exactly as today.
* Categorical Sales trend and integer Quality tie often (captured live
  2026-09-28 in the spec: `sort=sales_tier` has 9 of 11 sectors at `steady`;
  `sort=eq_score` has several names at exactly 90.0). A tie-break is what
  separates them now.

## ⓘ Quality — `quality_info` (one source of truth)

`backend/sepa/earnings_quality_info.py` `describe(fundamentals_as_of,
max_age_sec)` — pure, no I/O, does not import `sepa.research`.

* Every named threshold (`STRONG_EPS_YOY_PCT`, `MARGIN_FLAT_BAND_PCT`,
  `INV_OVER_SALES_GAP_PCT`, `INV_REDFLAG_ABS_FLOOR_PCT`,
  `INV_REDFLAG_SALES_STRONG_PCT`, `LOWQ_EPS_MIN_PCT`, `LOWQ_SALES_MAX_PCT`,
  `sales.SALES_FLOOR_PCT`) is read from the engine inside `describe()`.
* The point weights (20 / 20 / 15-7-0 / 12-6 / 12-6 / 11 / ≤10), penalties
  (25; 10 or 20), the `steady` cut (55) and the 5-quarter minimum are inline
  literals in `compute()`. They are mirrored as `PTS`, `PENALTY`, … and each
  mirror is pinned BEHAVIOURALLY in `tests/test_earnings_quality_info.py`: it
  must equal the score delta `compute()` produces for that component alone.
  `earnings_quality.py` itself is untouched.
* `surprise_pct` is never passed by `canslim` → the 10 surprise points never
  arrive → today's ceiling is **90** (`ceiling_today()`); `SURPRISE_WIRED =
  False`, guarded by an `ast` check of every `earnings_quality.compute(` call in
  `canslim.py`.
* Freshness: the board reads fundamentals through `_decision_map` →
  `research.decision_snapshot(symbols)` with its default `max_age_sec =
  CACHE_TTL_SEC` (16 days today). `_research_ttl_sec()` reads that constant at
  request time and the ⓘ states it ("older than 16 days … not used"); a source
  guard pins that `_decision_map` passes no other age. No refresh cadence
  number is stated — none exists as a constant.
* `fundamentals_as_of` = oldest / newest research-cache `cached_at` (ET dates)
  over the rows this board read, with the count; `null` when there are none.
* No page numbers, no quotes, no attribution in any served string;
  `compute()`'s `reason` strings are never served. The header's hover title is
  unchanged.

## What is NOT measured

`MEASURED = False`. No study on this app has tested `eq_score`, its tiers or
🎯 Code 33 against forward returns (grep of `docs/`, `scripts/`, every `*.py`,
2026-09-28). The ⓘ opens with that sentence (`MEASURED_NOTE`). It may flip only
when a study exists at `STUDY_SCRIPT`. The tie-break feature ranks nothing new:
it only orders ties the board already had.

## HIS CALL (defaults shipped)

1. `MAX_SORT_KEYS = 3` (primary + 2). Alternative: 2 or 4.
2. Exact ties: names A→Z, groups stored order (both = today). Alternative:
   group ties A→Z, or an implicit 5-days tie-break.
3. The 10 surprise points never arrive — disclosed, nothing changed. Wiring a
   surprise feed would change `eq_score` on every SEPA surface.

## Tests

* `backend/tests/test_hottest_multisort_2026_09_28.py` — parser, plan
  validator (every negative), name / group ordering, missing-last per key,
  truncation after sort, the single-key golden for every key × dir, the API
  (Query-object direct call, forwarding, bad input = 200, early return), the
  freshness source guard.
* `backend/tests/test_earnings_quality_info.py` — every mirrored weight /
  penalty / cut pinned to `compute()`'s own deltas, text built from patched
  constants, TTL wording, ceiling + surprise guard, honesty negatives.

## 2026-09-28 — critic fix round

1. **A failed re-rank no longer mixes two plans in the header.** `sortBasis`
   (`frontend/src/lib/hottestSort.ts`) now takes the settled PRIMARY from the
   served `sorted_by` too, not only the direction and tie-breaks; the header
   marks, `aria-sort`, `is-sorted` and the "ranked on" line all read that plan.
   After a click whose read failed (HTTP error or a no-rows 200 over a good
   board), a plain click also builds on the board on screen, and clicking the
   failed column (or ✕ clear) again RETRIES the read instead of going dead.
   Pinned in `HottestSectors.multisort.test.tsx` ("a FAILED re-rank …"),
   `hottestSort.test.ts` and the 2026-09-28 contract block.
2. **The ⓘ's "blank" sentence says every way a score is blank.** `compute()`
   returns no score when NEITHER EPS nor sales has a year-ago comparison for
   the latest quarter — fewer than 5 quarters, the latest or year-ago quarter
   missing, or a year-ago value of zero — so a name with 8 quarters on file can
   be blank. `NO_YOY_TEXT` in `sepa/earnings_quality_info.py` carries that, and
   `test_earnings_quality_info.py` pins it (8-quarter case, one-side-comparable
   negative, source guard on the `compute()` / `_yoy` conditions).
3. `GET /rotation/hottest` docstring: Next ER keeps the sectors in stored order
   only when it is the sole key; a tie-break after it ranks the group rows
   (`test_next_er_primary_then_a_group_key_still_ranks_group_rows`).
4. The Quality header hover still reads "Minervini Ch.8 earnings quality" —
   `earnings_quality.py` itself is written as the Chapter 8 verdict; kept
   (HIS CALL).
