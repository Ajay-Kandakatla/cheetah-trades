# 💎 Capital quality — "very less capital and hi ROI"

**Where it lives:** `backend/growth/capital_quality.py`, served on
`GET /growth/board` as `rows[].capital_quality` and `capital_quality_summary`.

**Status: NOT MEASURED.** `MEASURED = False`. This is a screen, not an edge.

---

## The ask

Ajay, 2026-09-22:

> "Ok can you now with in the explosive growth can you add a new tab.. Where we
> look at quality I need filter tab in explosive growth tab, whcih manage
> quality like very less capital and hi ROI. ... Filter and have alerts and new
> look out for such companies where whcih have very high quality. Let me know
> where you are creating it"

Quality = **low capital employed + high return on it**.

## Where it is, in one line

| Thing | Path |
|---|---|
| The read | `backend/growth/capital_quality.py` |
| The arithmetic it reads | `backend/sepa/capital_returns.py` (ROCE / ROIC / ROE / capex intensity) |
| Where it is hung on the board | `backend/growth/api.py:_payload`, after `board_metrics.attach` |
| Served as | `rows[].capital_quality`, `capital_quality_summary` |
| Tests | `backend/tests/test_capital_quality.py` (80) |

---

## The six components

Two kinds of cut, and **there is no third kind**. No component anywhere compares
a figure against a constant somebody chose.

| Key | Kind | The rule, exactly | Reads |
|---|---|---|---|
| `net_cash` | definitional | `cash > debt` | row |
| `positive_fcf` | definitional | `fcf_yield > 0` | row |
| `no_dilution` | definitional | `shares_yoy_pct <= 0` | row |
| `positive_roce` | definitional | `roce_pct > 0` | `capital_returns` |
| `roce_above_sector` | relative | `roce_pct >` its own sector's median | `capital_returns` + peers |
| `capex_below_sector` | relative | `capex_intensity_pct <` its own sector's median | `capital_returns` + peers |

**Definitional** = a sign test or an inequality between two figures from the same
filing. `cash > debt` is a fact about a balance sheet; there is nothing to tune.
Equality is not a pass (`cash == debt` fails), except for `no_dilution`, where
"not rising" is `<= 0` because a company that issued no stock has not diluted
him.

**Relative** = above or below the name's own sector median, computed from the
cohort in hand at read time. A rank, never a target.

`capex_below_sector` is **lower-is-better** — the "less capital" half of the ask.
Getting that direction backwards would rank the most capital-hungry names
highest, which is the exact inversion the ask is about, so it is pinned by its
own test against measured figures (NVDA 2.43% vs SM 35.61%).

### Why "low capital" has no definitional form

There is no sign test for it. Every operating company has positive capex, so
unlike `cash > debt` there is no natural zero to cut at. Answering it needs
either a threshold (which this package refuses to invent) or a comparison. It
gets the comparison.

---

## The grade

A **count**, and nothing else:

```
answered = passed + failed          # UNKNOWN is excluded entirely
answered == 0            -> "unknown"     (rank_key None — not ranked at all)
passed == answered       -> "all"
passed == 0              -> "none"
passed * 2 > answered    -> "most"
otherwise                -> "some"
```

**Why this is not a fitted number.** A fitted threshold is one chosen because it
separated an outcome. Nothing here has an outcome: no study exists, `MEASURED`
is False, and there is no forward return anywhere in the module to fit against.
What is left is a count of yes-answers, and a count admits exactly three
boundaries that refer to nothing but itself — all of them, none of them, and the
line where yes outnumbers no.

`answered` is served beside the grade because **"all" over two questions and
"all" over six are the same word and different facts**. On the live board CRDO
grades `all` at 3 of 3 — it is not punished for a missing share count, and the
`3` says why.

---

## UNKNOWN is not FAILED

The single lie this module exists to make impossible.

- A component with a missing input returns `"unknown"` with a **named reason**,
  is excluded from `answered`, and never lands in `failed`.
- A name with nothing answerable grades `"unknown"` and has `rank_key: None` —
  **not ranked last, not ranked**. "We could not look" and "we looked and it was
  bad" are different facts.
- A chip's `hides_n` counts **failures only**. An unknown row is never hidden,
  because it was never judged.
- NaN and inf are stopped at `_f()` before any comparison. `nan > 0` is `False`
  in Python, so a NaN that reached the comparison would render as a quiet FAIL.

Refusal reasons: `missing_cash_or_debt`, `missing_fcf_yield`,
`missing_shares_yoy`, `missing_roce`, `missing_capex_intensity`,
`non_operating_sector`, `no_sector`, `insufficient_peers`, `peers_unavailable`.

---

## The peer cohort

**The peers are not the board.** Measured 2026-09-22: the 🚀 board is 21 rows and
its largest sector cohort is **Technology with 6 names** (Industrials has 1). A
median over 6 is the "comparing against 2 names" failure this read exists to
avoid.

The comparison is made instead against the `board_metrics` collection — every
name any board in this app has recently warmed, which already carries a `sector`
on each document, so no second collection read is needed.

Measured in the api container 2026-09-22: **485 documents, 413 fresh within
`board_metrics.TTL_SEC`, 340 of those operating and sectored** — which is the
cohort the code actually reduces over. The projected read took **2.1 ms**.

| Sector | Operating + fresh | Clears `MIN_PEERS = 20`? |
|---|---|---|
| Industrials | 87 | yes |
| Technology | 85 | yes |
| Healthcare | 50 | yes |
| Energy | 32 | yes |
| Consumer Cyclical | 30 | yes |
| Basic Materials | 29 | yes |
| Communication Services | 11 | **no — refuses** |
| Consumer Defensive | 10 | **no — refuses** |
| Utilities | 6 | **no — refuses** |

Real Estate and Financial Services do not appear at all: every one of their
documents is `balance_meaningful: False`, so the cohort excludes them before
counting. A mortgage REIT is levered by design and a bank's deposits are
liabilities; including them in a median of "capital employed" would move the
number for every operating name in the sector.

Mapped onto today's 21 board rows, that means **15 names would get a relative
verdict** once the cohort is warm (6 Technology, 3 Healthcare, 3 Energy, 2 Basic
Materials, 1 Industrials); EVC refuses on peers (Communication Services, 11),
and the 5 Real Estate / Financial Services rows refuse as non-operating.

That cohort is a **convenience sample** — "every name this app has recently
pulled a balance sheet for", not a designed universe — so
`summary["peers"]` serves its size and per-sector counts, and a refused
component names the shortfall. The reader is never shown a median without being
told what it is a median of.

`n` is counted **per field, not per document**: a sector with 99 documents but 3
usable ROCE figures has 3 peers for ROCE. Counting documents instead is how a
median over three names gets served looking like a median over ninety-nine.

### The floor is the house's

`MIN_PEERS = 20` **is** `sepa/longterm.py:MIN_SECTOR_N`, the app's existing floor
for exactly this operation — a within-sector percentile — whose own comment
reads *"Below this, a within-sector percentile is noise."* It is pinned equal to
that constant by test so the two cannot drift, and so nobody can quietly lower
this one to make the relative cut fire on a thin cohort.

### Today the relative legs are UNKNOWN

The 485 peer documents carry `capital_returns` only **after the `board_metrics`
warm cron next runs with this code**. Until then both relative components answer
`insufficient_peers` on every row — which is correct, is not a FAIL, and costs
the definitional grade nothing. This is an operational fact, not a defect.

---

## Measured on the live board, 2026-09-22

21 rows, definitional legs only (the state on first deploy):

| Grade | n | Names |
|---|---|---|
| `all` | 3 | NVDA (4/4), TER (4/4), CRDO (3/3) |
| `most` | 6 | ALAB, IPI, LQDA, MU, PTGX, STAA |
| `some` | 7 | BE, EVC, INSW, SITM, SM, FF, LPG |
| `none` | 5 | ARR, DX, HHH, NLY, RKT |

| Component | pass | fail | unknown | hides |
|---|---|---|---|---|
| `net_cash` | 11 | 10 | 0 | 10 |
| `positive_fcf` | 14 | 4 | 3 | 4 |
| `no_dilution` | 2 | 17 | 2 | 17 |
| `positive_roce` | 14 | 2 | 5 | 2 |
| `roce_above_sector` | 0 | 0 | 21 | 0 |
| `capex_below_sector` | 0 | 0 | 21 | 0 |

`no_fail_n` = **3 of 21** survive every chip switched on.

`positive_roce` is **not** a no-op: it separates SITM (−1.03%) and FF (−17.03%)
from the other 14 operating names.

### The contrast the ask is actually about

Once the peer cohort is warm, the two relative legs split names that look alike
on return alone:

| Name | ROCE | Capex intensity | Reads as |
|---|---|---|---|
| NVDA | 100.36% | 2.43% | high return, capital-light |
| LQDA | 65.90% | 4.44% | high return, capital-light |
| TER | 39.12% | 5.94% | high return, capital-light |
| CRDO | 23.31% | 4.48% | high return, capital-light |
| MU | 64.79% | 27.98% | **buys its returns with capital** |
| INSW | 31.89% | 28.94% | **buys its returns with capital** |
| SM | 13.60% | 35.61% | **buys its returns with capital** |

MU passes `roce_above_sector` and fails `capex_below_sector`. That split is the
ask, and it only became visible once both legs existed.

---

## Why nothing is stacked into one AND-gate

`frontend/src/components/ExplosiveGrowth.tsx:285` records that a literal
`debt === 0` filter returned **zero of 29 rows**, which is why `debtTier` ships
defaulted to the widest honestly debt-light tier instead of the strictest one.

The same arithmetic applies here. Measured 2026-09-22, stacking every
definitional cut as one AND-gate leaves **2 of 21** (NVDA, TER). A gate that
hides 19 of 21 is not a filter, it is a blindfold.

So the summary serves **two survivor counts**, because they answer different
questions:

- `no_fail_n` — rows with zero failures: what is still on screen with every chip
  on. This is what a warning must use.
- `all_pass_n` — rows where all six passed with nothing unknown: the strictest
  read. Sits at 0 until the peer cohort is warm.

---

## What this is NOT

**It is not `eq_score`.** `eq_score` (`sepa/scanner.py:384`) is the Minervini
Ch.8 **earnings**-quality read — are the reported earnings real, sales-backed,
margin-expanding, free of the Code 33 / double-trouble red flags. It is an
**income-statement** question, it is scored 0–100, and it **feeds the SEPA
score** through `SCORE_WEIGHTS["fundamentals"]`.

This asks a different question of a different statement: given the earnings,
**how much capital did the business tie up to produce them, and what does it earn
on that capital.** It is a **balance-sheet** question, it is not scored, and it
**feeds nothing**. Same English word, two unrelated reads.

**It does not borrow the Quality score's credibility.** `sepa/longterm.py` ships
its own `SCORE_IS_MEASURED = False`; neither read lends the other any weight.

**It changes no rule (Rule #10).** The 100/100 screen, its ordering, its rosters,
its cohorts, its alert gates and its warnings are untouched. This adds one nested
key per row and one summary block. It sorts nothing by default, gates nothing,
and hides nothing on its own.

---

## Rule #7 — the period, never the cache age

Every read carries `period` / `period_end`: the **fiscal quarter** the capital
figures came from, carried through from
`board_metrics._attach_capital_returns`. A balance sheet fetched an hour ago can
still be a quarter old, and only the period says which. The read deliberately
carries no `fetched_at` and no age.

---

## The MEASURED flag

```python
MEASURED = False
STUDY_SCRIPT = "backend/scripts/capital_quality_study.py"   # does not exist
MEASURED_NOTE = (
    "This orders names by balance-sheet quality — how much capital the business "
    "ties up and what it earns on it. Nobody has measured whether that predicts "
    "anything on your universe. It is a screen, not an edge."
)
```

`MEASURED_NOTE` rides on the summary and `measured: false` rides on **every
row**, so no surface can render a grade without the sentence beside it.

Two tests pin it:

- `test_measured_true_requires_the_study_script_to_exist` — the flag cannot
  become True while no study exists at the named path.
- `test_measured_is_false_today_because_no_study_has_been_run` — asserts the
  path is absent and the flag is False.

To flip it: write and run `backend/scripts/capital_quality_study.py`, ship the CI
with the claim ("ship the backtest with the claim", standing rule), then set
`MEASURED = True`.

---

## Cost

**One computation per board request.** One projected Mongo read for the peer
medians (`sector`, `balance_meaningful`, two `capital_returns` fields, filtered
to `board_metrics.TTL_SEC`) — **measured at 2.1 ms over 413 documents in the api
container 2026-09-22** — then pure arithmetic per row. No provider call, no
per-name fetch — the measured reason `board_metrics` exists at all (80 tiles ×
1 call = 65 s).

`attach()` never raises. A dead peer read leaves `peers.available: False`, the
two relative components answer `peers_unavailable`, and the four definitional
cuts still grade — pinned by
`test_attach_survives_a_dead_peer_read_and_still_grades_the_definitional_cuts`.

---

## Not in this package

**Alerts.** The ask includes *"have alerts and new look out for such
companies"*. This work package is the read only; no alert kind, no push, no
notification preference is touched here.
