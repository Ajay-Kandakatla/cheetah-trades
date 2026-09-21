# 📈 Bonde board

Ajay 2026-09-13: *"create me a Bonde tab. we already have his rules in the
analysis tab on individual ticker but I wanna see explicitly new ones getting
added in this tab … but I wanna see his stocks."*

Chart Maps tab `bonde`. **Nothing here re-derives Bonde** — every rule is called
from the module that already implements and cites it.

> **MEASURED 2026-09-13, and the board's own thesis is INVERTED.** The tab
> shipped in the morning on the reasoning in §1; by the evening two measurement
> passes had put its headline cell at a 21-day median **−3.22%** against
> **−0.11%** for date-matched non-Pivot names — a lift of **−3.11pp**
> (95% CI −5.28 to −1.16). The board leads with that verdict rather than with
> the rules. Read **§1 first**; everything after it describes a study board.
> Scripts: `backend/scripts/bonde_audit/`.

| What | Where it already lived |
|---|---|
| His 5% / 25% / 100% sales tiers | `sepa/sales.py` |
| The PASS rule | `sepa/buyable_verdict.py::_bonde_pillar` |
| The Episodic Pivot | `setups/episodic_pivot.py` |
| The sourcing | `docs/sepa/sales_confidence_methodology.md` |

---

## 1. MEASURED 2026-09-13 — and the board's own thesis is INVERTED

The tab shipped on this reasoning, measured on the live scan the day it was
built:

| Leg | Count | The reasoning at the time |
|---|---|---|
| **Sales gate alone** | **1,051 of 2,076 (50.6%)** | Half the market. A description, not a selection. |
| **Episodic Pivot alone** | 50 setups; of the 32 in the scan, **11 have DECLINING sales** | A tape pattern. On its own it selects what his screen throws away. |
| **Both** | **12** | "A board." |

That reasoning was then measured — first pass, then an **independent audit**
with its own code, its own fetch and roughly twice the panel. The intersection
is the **worst cell either pass found.**

### The headline

780 Episodic Pivots reconstructed bar by bar from **closed** bars,
2024-09-13 → 2026-09-11. The rule reproduced **62 of 63** stored setup docs;
the lookahead probe found **0 of 780** events using a quarter filed after its
own bar.

| Cell | n | 21d median | win |
|---|---|---|---|
| **A — Pivot + sales PASS** (the tab's thesis) | 376 | **−3.22%** | **39.8%** |
| B — Pivot + sales FAIL | 404 | −0.81% | 46.2% |
| C — sales PASS, no Pivot | 1,172 | −0.51% | 47.7% |
| **D — neither (placebo)** | 1,376 | −0.11% | 49.6% |

**A − D = −3.11pp**, 95% CI **−5.28 to −1.16** symbol-clustered, **−5.19 to
−1.13** date-clustered. It holds at 3d (−0.88), 5d (−1.19) and 10d (−1.89);
under a ≥$1M liquidity cut; under entry at the next **open** (worse, −4.76pp at
21d); and in all four point-in-time fundamentals variants (−3.11 / −3.45 /
−3.07 / −2.71).

**His sales gate on its own separated nothing at any horizon**: C − D is
−0.40pp, CI −1.40 to +0.61. It passes 48.2% of Pivot events against 46.0% of
date-matched non-Pivot draws — it carries no information about the pivot.

**The bracket**, which is the setup's own stated outcome: expectancy
**−0.92%** [−2.14, +0.27], and the sales gate moves it by −0.06pp
[−1.70, +1.62]. The 58% target-before-stop rate is **bracket geometry, not a
win rate** — target a fixed 6.00% away, stop a median 13.71% away. Per this
repo's ledger convention that raw rate never prints without both distances.

**This is not an inverted signal to trade the other way.** Cell A's 21d **mean**
is −2.18% with a CI that includes zero. The finding is "these bleed at the
median and win less than half the time", not "these reliably fall".

### The tiers do not separate either

24 monthly cross-sections, 54,786 symbol-bars, sales state computable on 45,425
(82.9%).

| Tier | n bars | 21d median lift vs all scored | 21d mean lift | win lift |
|---|---|---|---|---|
| explosive ≥100% | 1,563 | **+0.45pp** [−0.31, +1.36] | +2.43pp | +0.96pp [−1.40, +3.14] |
| strong ≥25% | 5,391 | **+0.37pp** [−0.16, +0.78] | +5.27pp | +0.68pp [−0.68, +1.94] |
| steady 5–25% | 17,434 | −0.01pp | — | — |
| declining <0% | 13,160 | −0.21pp | — | — |

Every median lift and every win-rate lift spans zero, at both horizons, in the
primary run and in three of four variants. **The mean is the right tail**:
strong's +5.27pp falls to +0.62pp dropping the top 1% of returns and **+0.26pp**
dropping the top 5%. Date-clustering — 3.67× wider than iid here, while symbol
clustering buys 0–15% — kills what is left. A per-date sign test has explosive
beating the day's whole cross-section 12 of 20 times. Names passing the **full**
gate are indistinguishable from any stock: +0.48pp, CI −0.47 to +2.20.

Consequences for the board, enforced in code:

- it **never sorts on `sales.compute`'s 0–100 score** (`bonde._sales_key`), and
- no tier number prints without its **median**, its **win rate** and its
  **placebo** beside any mean.

### The one finding that survived every attack — and why there is a 🔎 section

His PASS rule is *floor* **AND** *character*, where character is `accelerating`
OR ≥2 consecutive growth quarters. The **character half measures backwards.**

| Cell (scored bars) | n | 21d win | 63d |
|---|---|---|---|
| floor ✅ character ✅ → **PASS** | 19,949 | 51.2% | — |
| floor ✅ character ❌ → **gate rejects** | 3,117 | **56.8%** | — |

PASS − REJECT: **−5.64pp** [−7.52, −3.91] at 21 days and **−7.66pp**
[−10.64, −4.44] at 63. Clause by clause it is the **consistency** half: ≥2
consecutive quarters costs 3.31pp of win rate [−4.68, −1.83] at 21d and 4.13pp
at 63d. **`accelerating` is a null, not a negative** (+1.63pp mean, CI −0.85 to
+7.54) — the first pass claimed both clauses were inverted and that half is
struck. Note also the mean/win split: PASS − REJECT on the **mean** is −0.22pp
[−1.93, +2.73]. The rejected names win *more often*; they do not earn more on
average.

**The gate is not edited.** It is Bonde's, and this board exists to show his
screen. The cohort it discards is shown beside it instead, as the
🔎 **"Cleared his floor, rejected for character"** section, labelled as **not on
his screen**, capped at 40, never mixed into the tiers, and never badged ✨ NEW
(that badge means "arrived on his screen").

Caveat printed with it: this result does **not** survive date clustering at 21
days (it does at 63), and the variant matching production's raw list position
shrinks the cell to 1,030 bars with 63d CIs spanning zero.

### Struck on re-measurement — said nowhere on the tab

1. *"Pivot + sales-PASS loses to Pivot + sales-FAIL"* (first pass: −3.36pp
   [−5.84, −0.87]). Re-measured **−2.42pp [−4.88, +0.30]**, spanning zero in all
   four variants; at 5d it is +0.01pp. **Struck.**
2. *"Both character clauses measure backwards."* Only the consistency one does.
3. *"Coverage is 46%, so this is the large/mid-cap half."* That was the first
   pass's own **no-retry fetcher** losing about half its requests — 1,301 names
   it called "no financials" do return them, and the dropout was uniform across
   the alphabet. The audit's panel is ~2× larger.

### Limits that belong next to any of these numbers

- **Delisting survivorship is unmeasured.** `load_universe()` is today's
  membership, so every name that went to zero or was acquired between 2024-09
  and 2026-09 is absent from every cell. Direction: the missing population skews
  toward the declining-sales microcap end, which flatters cells B and D, so the
  A-vs-B inversion is if anything understated — A-vs-D could move either way and
  cannot be bounded.
- **24 cross-sections, ONE bull regime.** The date cluster is the binding one
  and a 24-cluster bootstrap is itself fragile. It is reported as the honest
  floor, not as a comfortable number.
- **The derived-Q4 availability date is an assumption.** 24.3% of quarterly rows
  carry `filing_date: None` and are assumed available at `end_date + 90d` (the
  10-K deadline); 99.6% of events have at least one in their window. Every
  headline was re-run with those rows dropped.
- **The availability proxy is the SEC filing date, not the press release**, so
  for about half the events the sales state is a 45+ day old quarter — what a
  trader would genuinely have had, but not "the number that caused the gap".
- **24.6% of Pivot events are unclassifiable and the dropout is structural** —
  212 of 255 are recent IPOs and de-SPACs, exactly the population most prone to
  episodic pivots.
- **Gross returns.** No commissions, slippage or borrow; real fills on 8%-gap
  names would be worse for the Pivot cohort than for the placebo.
- **Catalyst type could not be split historically** —
  `episodic_pivot._classify_catalyst` reads earnings dates for today only, and
  Bonde's own EP taxonomy is catalyst-named. If an edge exists it may live in a
  split this data cannot make.
- **Only this app's 8% / 5× Pivot thresholds were measured.** PEG's 5% / 4× and
  every other pair are unmeasured.

Scripts, re-runnable verbatim: **`backend/scripts/bonde_audit/`** — `README.md`
there carries the run recipe (inside the `api` container only; a throwaway
container falls back to Yahoo), the struck claims and these limits. The first
pass is kept alongside as `parent_ep.py` / `parent_tiers.py` so the disagreement
is visible.

---

## 2. Whose numbers are whose

- **Bonde's own**, documented in his writing: the 5% floor
  (*"Sales/revenue should be up 5% or more."*, 2007) and the 100% boundary of
  his *"Sales 100% plus but no earnings"* EP catalyst category (2010).
- **This app's, mis-attributed to him until 2026-09-20**: the 25% mid-tier
  (the first-person sentence this board carried until then was fabricated — it
  exists in none of his posts) and the character clause (accelerating OR ≥2
  consecutive growth quarters). The values are unchanged; only the labels are.
- **His own 2025 figure**: *"two quarters of revenue growth of 39% plus"*
  (2025-09-01) is his, and ships as its own pick leg on this tab.
  The methodology doc lists what is **not** his and failed source verification:
  30% and "MAGNA 53+" (Deepvue / TradeZella / TraderLion, not Stockbee).
- **This app's owner settings**, and the board says so: the Pivot's **8% gap on
  5× volume** (stricter than its PEG cousin because it has no earnings-calendar
  filter), and the **$1M base materiality floor** below.

---

## 3. The revenue-base defect

Caught on the live board before it shipped. Ranked on the raw percentage, the top
of the "explosive" tier was almost entirely arithmetic:

```
DBRG  +15,961%   year-ago quarterly revenue was MINUS $3,207,000
APLD     +877%   year-ago quarterly revenue was MINUS $33,300,000
QUBT   +9,000%   year-ago quarterly revenue was $61,000
FCUV   +1,811%   year-ago quarterly revenue was $35,330
```

`sepa/sales.py::_yoy` divides by `abs(base)`, so a **negative base returns large
positive growth** — a sign flip, not a ramp. Meanwhile the genuinely explosive
businesses ranked *below* the artifacts: PTGX $5.5M → $213M, LQDA $8.8M → $171M,
ONDS $6.3M → $83.8M.

**`sales.py` is not changed.** It is book-cited, locked by contract tests, and
read by the falling-knife gate on several other boards — moving its arithmetic
would move `sales.score` app-wide. The board handles its own ranking instead:

| `base_state` | Meaning | Effect |
|---|---|---|
| `non_positive` | Year-ago revenue ≤ 0 | Arithmetic, not a threshold. No percentage ranking, no dollar figure. |
| `too_small` | Year-ago revenue < **$1M** | This app's materiality setting, stated as such. |
| `ok` | A real base | Ranked on growth. |

Flagged names are **still shown**, with their percentage and their dollars —
hiding them would make the board disagree with his screen. They simply never
outrank a company with a real base. Every row prints `$base → $latest` beside the
percentage, because the dollars cannot lie the way a ratio can.

After the fix the tier reads: PTGX +3,749% ($5.5M → $213M), LQDA, ONDS, UMAC,
NUVB, RCAT, UUUU — real small-cap ramps, which is Bonde's territory. DBRG and
QUBT sit at the bottom with their numbers visible.

---

## 4. ✨ NEW — his explicit ask

`sepa/first_seen.py`, collection `bonde_seen`, 30-day window.

The subtle part: on the **first** build every name has a `first_seen` of now, so
a naive read badges the entire board. A `__meta__` row records when tracking
began, written with the **same timestamp** as that first cohort, and `newly_found`
uses a **strict `>`**. The first board therefore reports **zero** arrivals, which
is the honest answer — *"we have only just started looking"* must never render as
*"these are fresh finds"*.

Arrivals are recorded over **every name placed in a section**, not only those
surviving the per-section cap: a name that arrives into a capped tier has still
arrived, and recording only the visible ones would reset its clock each time the
cap pushed it off and back on.

**2026-09-20 — the ledger follows the pair guard.** It used to record every
*passer*. Since §9 holds mismatched passers out of the tiers, that stamped names
the board draws nowhere: their 30-day ✨ NEW clock ran while they were hidden, so
on the day the guard let one through — the day it actually arrives on his screen
— it would arrive silent, and `n_new` counted rows never rendered. A held-out row
is now stamped on the day it is shown. A held-out row that **keeps** its ⚡ Pivots
row is drawn, so it is recorded like any other arrival; a 🔎 rejected row is not
on his screen and is not recorded at all. Pinned by
`test_NEGATIVE_a_held_out_passer_is_NOT_stamped_into_the_arrival_ledger`,
`test_a_held_out_row_that_KEEPS_its_pivot_IS_recorded` and
`test_a_passer_pushed_off_by_the_SECTION_CAP_is_STILL_recorded`
(`backend/tests/test_data_spine_2026_09_20.py`). Names already in `bonde_seen`
from before today keep their old stamps — the ledger converges, it is not
rewritten.

`growth/tracker.py` has its own copy of this logic (written first, live on the
Explosive Growth board). It is **not** refactored — that board works and the user
gains nothing — but `tests/test_first_seen.py` asserts the two behave identically
on the same inputs, so the duplication cannot silently drift.

---

## 5. What building this found: every setup kind is stale

Not a bug — **his own rule**, finally working.

```
episodic_pivot  newest 413h    peg      newest 461h
bull_flag       newest 413h    orb      newest 326h
… zero fresh rows across all 18 setup kinds
```

`setups/universe.is_bull_regime()` gates every setup scanner. He explicitly chose
to sit out bear markets, and the gate reads `market_in_correction` (score 66.5) →
`False` → every scanner short-circuits and writes nothing.

It bites harder than it looks because **the gate was itself broken until
2026-08-31**: it imported a function that never existed in `sepa.market_regime`,
a bare `except` swallowed the ImportError, and it returned `None` ("cannot tell,
go ahead") on every call. The sit-out rule had never once fired. It was fixed,
and the fleet went quiet almost immediately after.

So the board **says so on the page**. An empty headline section with a structural
cause reads as broken otherwise, and "his entry setup is switched off because the
market is in correction" is itself the useful information.

---

## 6. What is measured and what is not

The Episodic Pivot **is now measured** — see §1, and
`backend/scripts/bonde_audit/`. That measurement is the reason this board leads
with a verdict banner rather than with the rules.

Still unmeasured: the Pivot's catalyst split (earnings vs news vs M&A vs FDA),
any threshold pair other than this app's 8% / 5×, and any holding rule other
than close-to-close and the setup's own bracket. `GET /patterns/accuracy`
tracks chart patterns (double_bottom, cup_with_handle …), not setups, so nothing
here appears in that ledger.

Nothing on this tab gates a scan, fires an alert, or buys in any lane.

---

## 7. Files

```
backend/sepa/bonde.py              the board, the base guard, the regime notice
backend/sepa/bonde_api.py          GET /bonde/board
backend/sepa/first_seen.py         the ✨ NEW ledger, generically
backend/sepa/board_metrics.py      warm list extended to Bonde names
backend/main.py                    router mount
backend/crontab                    40 17 * * 1-5 (arrivals), 45 17 (metrics)
backend/scripts/bonde_audit/       the measurement (README + 10 scripts)
backend/tests/test_bonde.py        the board + the measured-verdict guards
backend/tests/test_first_seen.py   7 tests incl. the drift guard
frontend/src/components/BondeBoard.tsx
frontend/src/components/BondeBoard.test.tsx   12 tests
frontend/src/lib/chartMaps.ts      CmTab, CM_TABS, TAB_META, isBoardTab
frontend/src/pages/ChartMaps.tsx   tab mount
frontend/src/styles.css            .bd-*
```

---

## 8. Headers and the 🎯 demand-band filter (2026-09-14)

Ajay, with a screenshot of the rows: *"Can you add headers. also sort this by
the ones close to demand zone. or give a check box to filter ones closer to
demand zones or in the demand zone from Bonde's"*.

**Headers.** Every section with rows carries a header row in the SAME grid as
a row (`.bd-row.bd-hdr`), so each head sits over its cell: Ticker · Sales YoY ·
base → latest · Character · Episodic pivot · Shares YoY · Cash − debt · EV /
sales · FCF yield. The four metric heads mirror `metricCells` in order. Each
head explains itself on hover. Hidden under 860px, where the grid collapses.

**The checkbox** "🎯 in / near a demand band only (≤ N% above) · nearest first"
does both halves of the ask: it keeps the rows whose live print is INSIDE the
board's nearest demand band or within the served near distance above its top,
and orders them in-band first, then ascending distance. Off = the served order
(his screen's own). The near distance prints from `params.demand_near_pct`
(`DEMAND_NEAR_PCT = NEAR_PCT = 2.0`, one notion of "near a band" both ways) —
never typed in the component; with no params served, no number prints.

**The read** is the shared bounce-room rule (`POST /supply-demand/bounce-room`,
one POST for every row on the tab), field `demand` on each row —
`supply_demand.bounce_room.demand_read`, documented in
`docs/supply_demand/bounce_room.md` § DEMAND. It reads the zone_store doc, i.e.
the BOARD's closed-bar geometry: the same band an alert would name. A demand
band whose floor is ABOVE the print is one price fell through — overhead, not
demand — and never qualifies (the reclaim-from-below class, 66% stop-hit in the
2026-09-08 autopsy). Nothing is computed on this tab.

**The chip.** A qualifying row wears 🎯 "in demand band" or "1.6% above demand"
in the Ticker cell, filled when inside; the tooltip carries the band, its touch
count, the print, a stale-print flag and the bands' `store_date`, and says "Not
a buy signal". Rows farther than the near distance wear nothing (Rule #5).

**Coverage is said, not hidden.** With the box on: "band read on K of N ·
P pending · read failed: …". Pending rows (no store doc yet — most names under
$1B) fill in on the next poll; a name with no demand band under its print never
qualifies. A section emptied by the box says "🎯 none in or near a demand band
right now" (or "still loading…") rather than looking broken.

Tests: `frontend/src/components/BondeBoard.test.tsx` § 🎯,
`frontend/src/lib/bounceRoom.test.ts` § demand proximity,
`backend/tests/test_bounce_room.py` § DEMAND (negatives: a band above the
print reads None; supply bands never count; a bad print reads None; an unknown
read is never near; the near distance is never typed in the component).

This is a filter on a study board whose own thesis measured inverted (§1).
Nothing here gates a scan, fires an alert or buys in any lane.

## 9. The YoY pair guard — 164 passers held out of the tiers (2026-09-20)

Ajay, 2026-09-20: *"Especially this in Bondes. I think bondes and explosive
growth are hand in hand."*

They were not, and this is where they came apart. **164 of 1,051 passers
(15.6%) — 13 explosive, 56 strong, 95 steady — were tiered off a
"year-over-year" pair that is not four fiscal quarters apart.** The 🚀 Explosive
Growth board has REFUSED exactly those rows since 2026-09-14
(`growth/tracker.qualifies`, `period_mismatch`), so thirteen names read
**explosive** here and **refused** there off the same filed quarter.

**Why it happens.** Massive OMITS a quarter it does not have rather than leaving
a placeholder, so list POSITION is not quarter adjacency. IOVA's period keys are
`[8105, 8104, 8102, 8101, 8100, 8098]`: 8103 (FY2025 Q4) and 8099 (FY2024 Q4)
are absent, so slot 4 is **FY2025 Q1 standing in for the year-ago self of
FY2026 Q2**. 98 of the 164 (59.8%) are missing a FY Q4 — the same hole this
file's own header already named.

**What the board does now.**

* A passing row that fails the guard is **not placed in any tier**. It is
  counted (`n_period_mismatch`), listed (`period_mismatch_symbols`: symbol, the
  tier it *would* have had, and both quarter labels) and the served `note()`
  says so. A board that hides must say what it hid.
* `n_pass` is **unchanged** — it is his screen's fire rate and the note quotes
  it. A new **`n_tiered`** (886 today) counts what is actually shown.
* Every row in every section carries **`period`** (`"FY2026 Q2"`, or
  `"Q2 2026"` on a yfinance-sourced row) and **`period_ok`**, a **tri-state**:
  `true` checked and fine · `false` checked and wrong · `null` **nobody could
  check** (370 of 2,078 live scan rows carry no period keys at all). A surface
  that renders `!period_ok` as a warning would flag every legacy row; render the
  tri-state as a tri-state.
* The 🔎 **rejected** section is guarded the same way — a name cannot be
  "rejected for character" off a pair that is not a year apart either. 17
  floor-clearers move out of it (55 → 38).
* An **Episodic Pivot survives**. The EP is a gap on volume, true whatever the
  quarterly series says, so a mismatched pivot row **stays in ⚡ Pivots** with
  `tier`, `growth_yoy_pct`, `prior_yoy_pct` and `accelerating` set to `null` and
  `period_ok: false`. The event is shown; the growth **claim** is withheld.

**Where the rule lives.** `sepa/qoq.py` — `YOY_GAP`, `HEADLINE_PAIR`,
`PRIOR_PAIR`, `yoy_pairs_ok`, `yoy_pairs_verifiable`, `period_ok`,
`period_label`. `growth/tracker.py` re-exports them (`T.HEADLINE_PAIR is
Q.HEADLINE_PAIR`, pinned by test) and `rotation/hottest.py` applies the same
test. **One guard, one home** — a pair typed twice is a pair that drifts, and
this one decides what both boards refuse.

**2026-09-20 (same day, refix) — the held-out sentence counts two cohorts.**
The guard holds out two DIFFERENT things and the first cut called both
"passers": a row that PASSES his sales screen is withheld from a **tier**,
while a floor-clearer that failed the character clause never passed the screen
at all and is withheld from **🔎**. Quoting the whole list as passers inflates
the fire rate of his own screen with rows it rejected. Each held-out entry now
carries `cohort` (`"passer"` | `"floor_clearer"`), the board serves
`n_period_mismatch_pass` and `n_period_mismatch_rejected` beside the unchanged
`n_period_mismatch` (which stays the LENGTH of `period_mismatch_symbols`, so
the header and the table can never disagree — 164 passers + 17 floor-clearers
= 181 rows on the run above), and `pair_guard_note` prints the split sentence
whenever the two counts differ. When every held-out row is a passer the
original one-cohort sentence is served **byte-identical** (pinned by test).

**Nothing was recomputed and no threshold moved.** `sepa/sales.py` keeps its
number and its 5 / 25 / 100 tiers; `canslim.py` and `buyable_verdict.py` are
untouched. This board declines to TIER the row; it does not disagree with the
arithmetic.

**Not fixed, on purpose (his call).** Deriving FY Q4 from the annual fetch in
`canslim` would repair the pair for ~15% of names and move `sales.score`
app-wide; re-pairing by period key inside `sales._yoy` would move the book-cited
module the falling-knife gate reads. The character clause's pairs (2,6)/(3,7)
would hold out **266** more rows and are reported, not applied.

Full report, with the before/after numbers and the re-run recipe:
`docs/sepa/data_spine_audit_2026_09_20.md`. Script:
`backend/scripts/data_spine_audit.py`. Tests:
`backend/tests/test_data_spine_2026_09_20.py`.
