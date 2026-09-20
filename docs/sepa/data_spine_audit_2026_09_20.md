# The data spine — 📈 Bonde ↔ 🚀 Explosive Growth, 2026-09-20

Ajay, 2026-09-20: *"Especially this in Bondes. I think bondes and explosive
growth are hand in hand."*

**The verdict in one line: they were not.** 164 of 1,051 Bonde passers (15.6%)
were tiered off a "year-over-year" pair that is **not four fiscal quarters
apart**, and the 🚀 growth board has refused exactly those rows since
2026-09-14. Thirteen of them read **explosive** on 📈 Bonde while the 🚀 board
refused them off the same filed quarter. That disagreement is now closed: one
guard, one home (`backend/sepa/qoq.py`), applied identically on both boards and
on the 🔥 Hottest row.

Nothing here is a measured signal. This is a data-quality reconciliation. The
Bonde thesis is still **inverted** (−3.11pp, CI −5.28…−1.16) and the growth
board's 100/100 screen is still **unbacktested** — that has not changed and is
not what this page is about.

Re-run it yourself:

```bash
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.data_spine_audit
```

---

## 1. What was measured (my own run, 2026-09-20, live container)

| | |
|---|---|
| Scan rows | 2,078 |
| Research-cache documents | 3,754 |
| Bonde passers | 1,051 |
| **YoY pair not four quarters apart** | **164 (15.6%)** |
| … by tier | **explosive 13 · strong 56 · steady 95** |
| Of those, missing a FY Q4 | 98 of 164 (**59.8%**) |
| Bonde tier rows after the guard (`n_tiered`) | 886 |
| Floor-clearers also held out of 🔎 rejected | 17 (rejected 55 → 38) |
| Rows with **no period keys at all** (unverifiable) | scan **370** · research **717** |
| Cross-source asymmetry (keyed one side, unkeyed the other) | **2** (BLMN, RNA — both research-keyed, scan-unkeyed) |
| Extra rows the character-clause pairs (2,6)/(3,7) would hold out | **266** — reported, **not applied** |

The held-out explosive thirteen: **ALSN, AXTI, BBIO, CDE, DELL, ECHO, HNI,
IOVA, KDP, KLIC, PNFP, SNDK, UNIT.**

**The shape, using IOVA.** Its period keys are
`[8105, 8104, 8102, 8101, 8100, 8098]` — a fiscal index is
`fiscal_year*4 + (quarter-1)`, so 8103 (FY2025 Q4) and 8099 (FY2024 Q4) are
simply absent from Massive's quarterly rows. Massive **omits** a quarter it
does not have rather than leaving a placeholder, so list position 4 is not the
year-ago quarter: it is **FY2025 Q1 standing in for the year-ago self of
FY2026 Q2**. The percentage printed against it is a two-season comparison.

## 2. The as-of dates agree

| Check over the 2,073 symbols in both copies | Differences |
|---|---|
| Latest quarter key | **0** |
| `sales.growth_yoy_pct` | **0** |
| `sales.tier` | **2** (BLMN, RNA) |

Both tier differences are **pending vs computed**, not a disagreement: the scan
has not enriched those two names, so Bonde reads tier `None` while the research
cache already carries `weak` / `declining`. There is no stale-data problem here.

## 3. Three adjacency behaviours lived in this app — and what they do now

| Module | Before | After |
|---|---|---|
| `growth/tracker.qualifies` | REFUSED a mismatched pair (`period_mismatch`, since 2026-09-14) | unchanged — now calls `sepa.qoq.yoy_pairs_ok`, re-exporting the pairs rather than owning a second copy |
| `sepa/board_metrics.shares_yoy` | **RE-PAIRS** by period key and refuses with `no_year_ago_quarter` | unchanged (it owns a different number) |
| `sepa/bonde` pillar, `rotation/hottest` row | **IGNORED** the keys entirely | now hold out / blank, exactly as the growth board refuses |

`sepa/qoq._adjacent` remains the ONE definition and keeps its accept-by-default
branch: refusing every legacy row would blank the board rather than improve it.
What is new is that the acceptance is no longer **invisible** — `period_ok` is a
tri-state (`true` / `false` / `null`) and `null` means *nobody could check*,
which is what 370 scan rows and 717 research documents are.

## 4. What changed on each surface

- **📈 Bonde** (`sepa/bonde.py`). A passing row whose pair is not a year apart
  is **not placed in any tier**. It is counted (`n_period_mismatch`), listed
  (`period_mismatch_symbols` — symbol, the tier it would have had, and both
  quarter labels) and explained in the served `note()`. `n_pass` is unchanged
  (it is his screen's fire rate); a new `n_tiered` counts what is actually
  shown. Every row in every section now carries `period` and `period_ok`. The
  🔎 rejected section is guarded the same way.
  - **An Episodic Pivot survives.** The EP is a gap on volume — true whatever
    the quarterly series says — so a mismatched pivot row **stays in ⚡ Pivots**
    with `tier`, `growth_yoy_pct`, `prior_yoy_pct` and `accelerating` set to
    `null` and `period_ok: false`. The event is shown; the growth **claim** is
    withheld. Holding it out entirely is the alternative — **his call** (§6).
  - **The sentence counts two cohorts** (refix, same day). A passer is held
    out of a **tier**; a floor-clearer that failed the character clause never
    passed the screen and is held out of **🔎**. Each entry carries `cohort`,
    the board serves `n_period_mismatch_pass` / `n_period_mismatch_rejected`,
    and `n_period_mismatch` stays the length of the list under the board (164
    passers + 17 floor-clearers = 181 today). The one-cohort sentence is
    byte-identical when every held-out row passed.
- **🔥 Hottest** (`rotation/hottest.py`). `sales_yoy`, `sales_prior_yoy`,
  `q_eps_yoy` and `sales_accelerating` are blanked on a mismatch and the row
  carries `period_mismatch: true`. Those legs are handed to the sector day-tag
  model as **facts**, and `sector_news_tags` drops `None` keys, so the model
  stops being told a two-season number is a year of growth.
  `sales_yoy` now reads the spine's own `sales.growth_yoy_pct` and falls back to
  `rev_growth_q_pct` — the yfinance path has no `growth_yoy_pct` at all — with
  `sales_yoy_source` (`sales` | `yfinance` | `legacy`) and `fund_source` saying
  which. **No yfinance row loses its number.**
- **`sepa/research.decision_snapshot`** now projects `fundamentals._source`.
  Without it the served path could not tell Massive (FISCAL quarter indices)
  from yfinance (CALENDAR ones), and `period_label` printed "FY2026 Q2" for a
  calendar Q2 — a year off on an NVDA-class fiscal year.
- **🚀 Explosive Growth** (`ExplosiveGrowth.tsx`) renders a `📈 Bonde: <tier>`
  chip. Bonde already carried a 🚀 chip back; this was the missing return leg.
  It claims the **source**, never the number: IPI / EVC / FF sit outside the
  scan's `full` universe (this board screens `broad`), and a scan-pending name
  is tier-less on Bonde while this board already has its figure.

## 5. The earnings-surprise 100× defect — FIXED

Two code paths read the same yfinance data in **two different units**. Measured
on the live container, 2026-09-20:

| Symbol | `catalyst._fetch_yfinance_extras` (fraction) | `earnings_watch._fetch_next` (percent) | after the fix |
|---|---|---|---|
| NVDA | 0.0616 | 6.16 | **6.16** |
| IOVA | 0.1843 | 18.43 | **18.43** |
| DELL | 0.4314 | 43.14 | **43.14** |

`sepa/catalyst.py:300` prints `f"{sup:+.1f}%"`, so **NVDA's 6.2% beat printed
"+0.1%"** on the ticker page. `AnalystPulseModal.tsx:209` falls back
`last_report.surprise_pct ?? last_surprise_pct`, mixing the two units silently
depending on which cache answered. `chart_maps/earnings.py:415` and
`growth/earnings_fresh.py:101` read the percent path.

**Nothing gates on it.** `frontend/src/lib/cheetahVerdict.ts:172` uses the value
as a NULL CHECK only — `epEarningsDriven = ep && catalystSurprisePct != null` —
and carries no threshold anywhere in the file. The ×100 therefore moves the
printed number and **no verdict**. A source-guard test
(`test_NEGATIVE_no_threshold_reads_the_surprise_on_the_ticker_page`) fails if a
comparison ever appears there, so the unit change would have to be re-argued.

NaN also passed the old `is not None` test and sailed through as a float; it is
now `None`.

## 6. What was NOT changed, and why

1. **`sepa/sales.py` is untouched.** The 5 / 25 / 100 tiers, `_yoy`'s
   `abs(base)` divide and `sales.score` are book-cited, contract-locked and read
   by the falling-knife gate on several other boards. The pair guard is a
   **BOARD** rule, applied where the board decides what to show.
2. **`canslim.py` is untouched.** Deriving FY Q4 = annual − (Q1+Q2+Q3) from the
   annual fetch would FIX the pair for roughly 15% of names — and would move
   `sales.score` and `earnings_quality` app-wide. **His call.**
3. **Re-pairing by period key inside `sales._yoy`** would change the book-cited
   module the falling-knife gate reads. **His call.**
4. **The character clause's pairs (2,6) and (3,7)** are reported (**266** extra
   rows) and not applied: the shipped guard checks exactly the two pairs the 🚀
   board checks, so the two boards agree **by construction**. **His call.**
5. **The mismatched Episodic Pivot stays in ⚡ Pivots** with the tier blanked.
   **His call** whether to hold it out entirely.
6. **`HottestSectors.tsx` does not render `period_mismatch` or
   `sales_yoy_source` yet** — the flags are served now, rendered later. **His
   call** whether those rows get a ⚠.

## 7. The residual — the guard cannot see everything

- **370 scan rows and 717 research documents have no period keys**, so
  `yoy_pairs_ok` accepts them because nothing could be checked. They are tiered
  and their `period_ok` is `null`, never a tick.
- **Cross-source asymmetry: 2 symbols** (BLMN, RNA) are keyed in the research
  cache and unkeyed in the scan, so they are checked on one board and
  accept-by-defaulted on the other. Both boards now apply the identical guard —
  to different **copies** of the series. Two is small today; the audit counts it
  on every run because the number is a property of the caches, not of the code.
- `ipo_dates`: 3,795 documents, **122** claim a listing within 2 years (a
  separate package owns that surface; quoted here because the audit reports it).

## 8. Cross-check against the boards

Bonde explosive **69** vs growth board **21 rows**; **18 shared** (ALAB, ARR,
BE, CRDO, DX, HHH, INSW, LPG, LQDA, MU, NLY, NVDA, PTGX, RKT, SITM, SM, STAA,
TER). The rest is **screen difference, not data disagreement**: three growth
rows sit outside the scan's `full` universe, and the remaining Bonde-explosive
names fail the growth board's EPS ≥100% / prior > 0 legs. The **13** in §1 were
the real disagreement, and they are gone.

## 9. The REPAIR — 2026-09-20, later the same day

Ajay, on the his-call list above: **"#2"** — repair the 164 mismatched pairs to
the true year-ago quarter rather than keep holding those rows out.

### The rule: label by densify, at the ONE place the rows become series

Massive omits a quarter it does not have, so list POSITION was never quarter
adjacency. `sepa/qoq.align_reports` now puts **one slot per fiscal index** from
the newest key down to the oldest — `None` where a filing is absent — and
`sepa/canslim._fetch_massive_financials` calls it **before** the five series
comprehensions, so `rev_q_series`, `eps_q_series`, `ni_q_series`,
`inv_q_series` and `q_period_series` all land on the same quarter. IOVA's
`[8105,8104,8102,8101,8100,8098]` becomes
`[8105,8104,null,8102,8101,8100,null,8098]` and slot 4 is FY2025 Q2 — the real
year-ago quarter of FY2026 Q2 — instead of FY2025 Q1.

Within one fiscal period the **first row in source order wins**: Massive lists
filings newest-FILING-first, so the first row for a restated quarter is the
restatement (NU files FY2024 Q2 twice, 1,892,600,000 then 1,892,590,000). The
count of ignored duplicate rows and whether the source arrived out of order are
both reported — `duplicate_periods` and `reordered` — never silently absorbed.

Nothing was recomputed and **no threshold moved**: `sepa/sales.py` is guarded
byte-for-byte against `HEAD` in `backend/tests/test_sales.py` and its
5 / 25 / 100 tiers are pinned beside it.

### The heal, for documents cached before the alignment shipped

```bash
docker exec -i -w /app cheetah-market-app-api-1 python -m sepa.qoq realign --dry-run
docker exec -i -w /app cheetah-market-app-api-1 python -m sepa.qoq realign
```

`--dry-run` computes and prints the identical counts without a write — **that
dry run is the re-tier measurement**.

### Two holes, counted apart on purpose

After the alignment, a missing quarter is a **hole at its own slot**, and the
two holes are not the same answer (`sepa/qoq.period_ok`):

| hole | `period_ok` | what it costs | where the row lands |
| --- | --- | --- | --- |
| **headline** — the year-ago quarter is absent (`headline_hole`) | `False` | the whole growth claim: `sales.score` is `None` | **pending** → off the board exactly like every pending row, marked ⚠ on 🔥 Hottest and ⚡ Pivots |
| **prior** — only slot 1 or 5 is absent (`prior_hole`) | `True` | `prior_yoy_pct` and the acceleration read only | **released** — the headline number is correct; the character clause reads an unknown prior as no character, so a floor-clearer lands in 🔎 `rejected` and a non-clearer is below the floor |

Collapsing those into one "year-ago hole" number would hide which rows the
repair actually releases, so `realign` and the audit always print them apart.
**The repair promotes nothing** — it puts each row where today's rules already
say it belongs. Whether an unknown prior should be character-NEUTRAL instead is
a rule change and stays on the his-call list.

### `retier_after` — run `scripts.data_spine_audit` and fill this in

`repair_outcome(docs)` in `backend/scripts/data_spine_audit.py` re-tiers every
keyed document through the real `sales.compute` and places it through the real
`buyable_verdict._bonde_pillar`, then emits the result under `"repair"`.

| count | value |
| --- | --- |
| `mismatched_before` | **60** (the headline holes — after `realign` the 164 slot-4 mismatches are gone; what is left is the 60 names whose year-ago quarter is not filed) |
| `retier_after.explosive` / `.strong` / `.steady` / `.weak` / `.declining` / `.unknown` | **123 / 430 / 1,107 / 425 / 696 / 288** |
| `headline_hole` / `prior_hole` | **60 / 145** |
| `placement_after.tiered` / `.rejected_character` / `.out_pending` / `.out_floor` | **1,541 / 161 / 288 / 1,079** |
| `duplicate_periods` / `reordered` / `dropped_unlabelled` (documents) | audit sample **0 / 0 / 0**; the full `realign` pass over 3,072 keyed docs: **18 / 31 / 0** |
| `still_held_out` | **0** — as expected |

Live run, 2026-09-20 15:10 ET, `python -m sepa.qoq realign --json` on the api
container: considered 3,754 research docs · keyed 3,072 · **realigned 1,160** ·
unchanged 1,912. Re-tier table (before → after, keyed docs only):
explosive→explosive 37 · explosive→strong 7 · explosive→unknown 5 ·
strong→strong 137 · strong→steady 48 · strong→explosive 2 · strong→unknown 8 ·
steady→steady 358 · steady→strong 3 · steady→weak 25 · steady→declining 14 ·
steady→unknown 19 · unknown→explosive 2 · unknown→strong 3 · unknown→steady 11 ·
unknown→unknown 73 · the rest weak/declining moves. Read it as the boards
disagreeing less, not as anyone's growth improving — a re-tier off the
correct year-ago quarter is a data fix.

The scan copy was refreshed by `POST /sepa/scan?fast=true` the same afternoon
(971 s, 240 candidates) and the audit re-run: **`pair_mismatch.total` 0**
(was 164), **`overlap.period_differs` 0 · `growth_differs` 0 · `tier_differs`
2** on 1,799 overlapping names (was 7 / 243 / 149 between the realign and the
scan — realigned at different times, exactly the case the paragraph below
describes). Bonde passers 998 (was 1,051: the 60 headline-hole names are
pending, not tiered). `shared_explosive` unchanged at 18 names.

The **0-diff check of §6 is repeated after the heal**: the scan copy and the
research copy of the series must still agree on the latest quarter, the growth
number and the tier (`overlap.period_differs / growth_differs / tier_differs`).
A non-zero there means the two copies were realigned at different times, not
that the alignment is wrong — re-run the audit after the next scan.

### What `realign` does NOT do

- It **never touches `cached_at`.** Bumping it would extend the life of stale
  fundamentals, which is the opposite of the point.
- It **does not recompute `earnings_quality`.** That score needs the inventory
  and receivables series, and `inv_q_series` is not stored on the cache
  document at all (`canslim.py` copies only period/rev/eps/ni). It is realigned
  through `canslim` by the **Sunday** research refresh, not here.
- It does not touch `recv_q_series`: that comes from yfinance, is
  calendar-quartered and positional by construction, and is never aligned.

### The `_adjacent` note

`period_ok` still calls the **module-global** `sepa.qoq._adjacent` rather than a
captured reference, so the 🚀 growth board's E1 monkeypatch keeps biting
through `yoy_pairs_ok`. There is still exactly one adjacency definition in the
app; the repair added the hole semantics around it, not a second copy.

---

*Scripts: `backend/scripts/data_spine_audit.py`, `python -m sepa.qoq realign`.
Tests: `backend/tests/test_data_spine_2026_09_20.py`,
`backend/tests/test_yoy_repair_2026_09_20.py`. Nothing on either board gates a
scan, fires an alert or buys in any lane.*

### 9.1 Trailing blanks are not a hole (2026-09-20, main session)

The repair's literal rule — "a None at slot 4 refuses the row" — reversed the
2026-09-14 growth-board pin that a legacy row with only a headline key
(`[8105, None, None, None, None, None]`) is ACCEPTED, not blanked. The two are
reconciled by reading a slot-4 None as a KNOWN hole only when a filed quarter
exists beyond it — the shape `align_reports` produces, whose last slot is always
the oldest key. Trailing blanks with nothing after are missing DATA, not a
missing QUARTER, and the row stays `unverified` (None). `_densify` can never
emit the trailing shape, so every aligned list keeps the repair's answer;
pinned by `test_a_TRAILING_run_of_Nones_is_UNVERIFIABLE_not_a_known_hole` and
the two negatives beside it. His call to reverse, not a threshold.

