# 🔥 Hottest Sectors tab (2026-09-11)

Ajay, across three messages:

> *"From the sectors. Can you find the hottest of the sectors like the most growth and put
> them in to a new tab. Like in to hottest of the sectors tab.."*

> *"I am seeing a lot of new names I was not tracking before.. but hottest from last 5 days
> and current. Like ANDE was never on my list but its growing"*

> *"List needs to be hottest of the sectors and then hottest from a sector in to a table.
> Like the catalyst and keep sales and other crucial metrics for me."*

Chart Maps ▸ **🔥 Hottest**, sitting with the movers boards (Catalysts, Overnight) — it asks
the same question they do, one level up. `GET /rotation/hottest`, built by
`backend/rotation/hottest.py`, rendered by `frontend/src/components/HottestSectors.tsx`.

## What his example exposed before a line was written

He named ANDE as the kind of name he wants to find. Probing it first changed the design twice:

| ANDE, 2026-09-10 | |
|---|---|
| Today | +0.79% |
| 5 days | +1.35% |
| **21 days** | **+12.14%** |
| Its sector (Consumer Defensive) over 5 days | **−0.94%, 8th of 11** |
| Its industry (Food Distribution) | **no ranked row at all** — 6 names |
| Rank in its sector, by `traction` | **23 of 76** |
| Rank in its sector, by rel_5d / rel_21d | **3 of 76 / 2 of 76** |

So, put to him as two questions with those numbers attached, he chose:

1. **All three legs** — today / 5d / 21d. A 5-day-only board cannot see ANDE at all. This
   **reverses his 2026-09-10 instruction for this board only**; `rotation.heat.HEAT_KEY` is
   untouched and the Hot-sectors strip still ignores the 21-day, pinned by
   `test_the_hot_sectors_strip_window_is_untouched`.
2. **Sectors that expand into industries**, then into names.

## Four decisions that follow from the probe

**Every sector is listed, not just the hot end.** ANDE is a strong name in a *cold* sector.
A board that ranks sectors and then shows only the top few structurally cannot find it. All
eleven answer; the cold ones simply sort last.

**Thin industries still show.** Food Distribution has 6 names and no ranked row in the
rotation grid. Hiding it is exactly how ANDE disappears. It renders inside its sector flagged
`thin`, with `basis: "full membership"`, because a 6-name median is not a 25-name one.

**Names rank by return, never by `traction`.** Traction measures *acceleration* (`pace_5` vs
`pace_21`). ANDE is strong and decelerating, so traction ranks it 23rd while the 5-day ranks
it 3rd. Sorting this board on traction would bury the name that prompted it. `traction` still
rides in every row — the popover owns that number and two definitions would drift apart — it
just is not the sort. Both the explicit sort and `DEFAULT_SORT` are pinned.

**Two populations, both named in the payload.** Group heat is the **shipped** sampled median
— Technology measures 40 of its 305 names — reused verbatim so this board can never disagree
with the Hot-sectors strip. Name rows are the **full** membership, which is the only reason
ANDE is reachable: he is not in Consumer Defensive's sampled 40, but he is 2nd of its full 76.
Every row carries `basis`, and the sector row's tooltip prints `heat on 40 of 305`.

## The columns, and why these ones

Coverage was **measured on the live hot-group pool before the columns were chosen**, because a
column that is blank for a third of the board is worse than no column — and blanks would land
on exactly the unfamiliar names the board exists to surface.

| Column | Source | Coverage |
|---|---|---|
| Today / 5d / 21d | rotation, vs RSP | 100% |
| Sales YoY (+ ⚡ accelerating) | `fundamentals.rev_growth_q_pct` | 93.1% |
| Sales trend (Bonde tier) | `fundamentals.sales.tier` | 87.2% |
| Q EPS YoY | `fundamentals.q_eps_growth_pct` | 92.7% |
| Net margin (+ ↑ expanding) | `earnings_quality.components.npm_latest_pct` | 87.2% |
| Quality (+ 🎯 Code 33, ⚠️ inventory) | `earnings_quality` (Minervini Ch.8) | 87.2% |
| Next ER | `earnings_calendar` | 97.9% |

**Deliberately NOT shipped:** catalyst *text* (42.9%), moat (64.7%), institutional ownership
(65.1%), analyst targets (66.8%), anything from `stock_analysis_cache` (63% present but only
20% fresh — that one really is an on-visit cache). He asked for "catalyst"; the honest answer
is the earnings date plus the ⚡/⚠️ flags, with the ticker page one click away for the rest.

No new fetch was added. `sepa_research_cache` is already refreshed over the **whole universe**
by cron (`research-refresh --mode broad`, Sundays + nightly if stale), so one projected Mongo
read (`research.decision_snapshot`) covers the board. Measured live: **99.9% of 1,727 priced
names**.

### Traps this walked into

- **`earnings_calendar` is keyed by `_id`, not by a `symbol` field.** Querying
  `{"symbol": {"$in": [...]}}` returns zero documents with **no error** — a silently blank
  column that reads like "we have no earnings data".
- **Fundamentals are WEEKLY.** p50 age ~4.6 days, so a name that reports on a Monday shows
  last quarter's sales for up to six days. The board prints its `as_of` and its coverage.
- **The 13% blank is not random** — it clusters on foreign filers and off-calendar fiscal
  years (ASML, ARM, GFS), which are concentrated in semis, currently the hottest industry. A
  miss renders as an em-dash with a tooltip, never as a zero, and never wins a sort.
- **NaN passes every `<=` comparison**, so one bad bar silently reorders the whole board. The
  shared `traction_row` output is scrubbed *before* the sort, not just before serialisation.

## Sorting every column (2026-09-12)

Ajay 2026-09-12: *"Add sort in this."*

Nine sortable columns, listed in `HS_COLS` (frontend) and validated against
`SORT_KEYS` (backend) by
`test_every_printed_column_is_sortable` — a header that ranks on a key the
server rejects would silently fall back to `rel_5d`.

| Column | Sort key | Notes |
|---|---|---|
| Today / 5 days / 21 days | `rel_1d` `rel_5d` `rel_21d` | relative to RSP |
| Sales YoY | `sales_yoy` | |
| Sales trend | `sales_tier` | **ordinal**, not alphabetical: explosive 5 › strong 4 › steady 3 › weak 2 › declining 1 |
| Q EPS | `q_eps_yoy` | |
| Margin | `net_margin` | |
| Quality | `eq_score` | Minervini Ch.8 |
| Next ER | `next_earnings` | opens **ascending** — the question is who reports soonest |

### Why the sort is a server round-trip and not a client reorder

The payload keeps `names_per_group` (25) rows per sector and per industry.
Sorting in the browser would rank those 25 and **never reach the 305th
Technology name**. `_build` sorts `rows` *before* `irows[:names_per_group]`, so
the round-trip re-ranks the full membership and then truncates. Pinned by
`test_the_sort_runs_BEFORE_the_names_are_truncated` (with `names_per_group=1`,
the one row returned must be the column's top, not the return leg's).

### The trap: a blank must sort last in BOTH directions

`_sort_value` returns a `(present, value)` pair and every caller sorts
`reverse=True`. The obvious implementation scores a missing value as `-inf`,
which is **correct descending and wrong ascending** — it floats every em-dash
row to the top. `test_NEGATIVE_a_blank_sorts_LAST_in_BOTH_directions` runs all
six nullable columns × both directions.

### Group rows gained a median, because a sort has to be visible

Sector and industry rows were **blank** in the four fundamental columns, so
ranking on one of them reordered the tree with nothing on screen to explain
the new order. `_fund_medians()` computes the median of the group's **full
membership** for `sales_yoy`, `q_eps_yoy`, `net_margin`, `eq_score` and a
median tier, rendered in italics (`.hs-med`) so it never reads as a company's
own filed figure.

**The three legs are NOT recomputed.** They stay `_group_legs(shipped)` — the
rotation grid's sampled median, reused verbatim, which is what stops this board
disagreeing with the Hot-sectors strip. Only the fundamental columns are
computed here, and they carry `fund_basis` saying so. Pinned by
`test_group_legs_are_still_the_SAMPLED_median_not_recomputed`.

### The three leg chips were removed

They set the same backend `sort` the headers now set. Two controls for one
piece of state is how a board starts disagreeing with itself about its own
order; the arrow on the active header is the state, plus one line of prose
above the table.

### Mutation coverage

All 13 mutations caught — 8 backend (blank scored `-inf`, direction ignored,
tier as a string, sort after truncation, medians dropped, medians invented from
blanks, legs recomputed, unknown key accepted) and 5 frontend (active-click
stops flipping, Next ER opens desc, no arrow, medians back to a spacer,
direction never sent).

**One test initially passed for the wrong reason.** The tier test compared two
names, and `'explosive'` is both the top tier *and* the longest string — so it
survived replacing the rank with `len(tier)`. Rewritten to assert the full
five-tier order in both directions, which defeats alphabetical and
length-based impostors alike.

## What this board is not

A trailing-return ranking with **no measured edge**. Nothing here is backtested and none of it
is a buy signal — it answers "what moved, and what do its fundamentals look like". No gate was
widened to fill it. The blurb says so, and a contract fails the build if that sentence is
removed.

## Tests

- `backend/tests/test_rotation_hottest.py` (12) — cold sector still listed, shipped heat reused
  verbatim, both populations reported, thin industry flagged, return-sort over traction
  (explicit **and** default), unknown sort falls back, missing fundamental is `None` not `0`,
  NaN never reaches a row or a sort, empty payload answers an empty board, and the strip's
  window untouched.
- `frontend/src/components/HottestSectors.test.tsx` (11) — formatting (em-dash never zero,
  tone by each cell's own sign), the cold-sector → thin-industry → ANDE path, the sales block
  beside the move, a fundamentals-less name rendering dashes, the 40-of-305 disclosure, the
  leg switch refetching, and two negatives for a failed fetch and a backend `reason`.
- Contract *"Chart Maps carries the 🔥 Hottest tab, styled and wired"* — tab registered and
  excluded from `isBoardTab`, mounted in ChartMaps, reads `/rotation/hottest`, does not
  recompute traction, blurb declares it a discovery list and says all eleven sectors show, and
  **every `hs-*` class used in the TSX has a rule in `styles.css`** (jsdom loads no
  stylesheets, so no render test can catch a missing one).

All four backend mutants and three frontend mutants were caught after the guards were tightened.

### Two pre-existing contract defects fixed on the way

Both were found by mutating, not by reading:

1. **The CM_TABS tab-order contracts pinned literal substrings of a formatted array.** A
   line-wrap of `CM_TABS` failed a correct file, *and* a comment containing
   `'hot_pullback', 'patterns'` satisfied the check while the real order was wrong. They now
   parse the declaration into an array (`parseCmTabs`) and assert on positions.
2. **The `hsm-*` stylesheet guard used `css.includes('.' + cls)`** — satisfied by
   `.hsm-conameXX`, so renaming a rule passed. Both that guard and the new `hs-*` one now
   require a word boundary.
