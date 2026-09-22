# 🎪 Can we use the promo-circuit names? — MEASURED 2026-09-21

> **NOT A SIGNAL, NOT A GATE — research only (Rule #10).** This file changes no
> rule, gate, threshold or tier. An inverted read is not a short signal.

**He asked (2026-09-21), with the board's own link:** *"We have this page that
pull data from social media and chatter the keeps pulling new stocks.. Can you
please check if we can use them and make sure to do some research and add them
to our lis tas they come through please?"*

Two halves. This file answers **can we use them**. The curation lane that makes
the names visible to the scan is `docs/catalysts/promo_curation.md`.

Every number below is read out of `backend/scripts/promo_tag_measured.json`,
built from `backend/scripts/promo_tag_study.py`. Pins:
`backend/tests/test_promo_tag_measured.py`.

---

## 1. The answer

**A promo tag is a do-not-chase radar, not a source of entries.**

Entry at the first session **open strictly after** the first-ever tag, held five
sessions, against never-tagged names matched on **size and liquidity at the tag**
and entered and exited on the **same dates**:

| | tagged | matched placebo | difference |
|---|---|---|---|
| median 5-session return | **−7.30%** | −2.52% | **−4.78pp** |
| confidence interval, clustered by **date** | | | **[−7.19, −3.41]** |
| confidence interval, clustered by **name** | | | **[−6.50, −3.43]** |
| finished the week green | **29.2%** [26.8, 31.8] | | |
| median worst drawdown inside the week | **−14.18%** | | |

1,231 events over 31 entry dates and 614 distinct names. Both intervals sit
entirely below zero. The tagged name does not merely fail to beat its peers; it
**loses to them**, by about five points a week.

**Day one is a coin flip.** At one session the gap is −0.48pp and the interval
spans zero. The damage is the week that follows, not the pop.

## 2. What was measured, and against what

- **Population.** Every *first-ever* tag in `promo_circuit_tags`, 2026-07-29 to
  2026-09-21: 3,452 tag rows over 1,563 tickers and 21 accounts.
- **Entry.** The first session **open** after the tag — what a follower could
  actually get. The close-entry variant is reported and is milder (−3.63pp),
  which is itself the point: the tag-day close already carries part of the move.
- **Placebo.** Never-tagged names drawn from the same **cap-at-tag decile ×
  pre-tag liquidity tercile**, five per event, entered and exited on the same
  dates. So the comparison is not against the market; it is against names that
  looked the same before anybody posted about them.
- **Cohort.** The **shotgun-pruned** set: an account that tags more than the
  board's own distinct-name limit keeps only what it repeated. The unpruned
  cohort measures the same sign, slightly milder (−3.29pp, n 2,771).
- **Intervals.** Percentile bootstrap, 2,000 draws, clustered **twice** — by
  entry date and by symbol — and a cell is only quoted when it clears a
  20-cluster minimum. Cells that do not clear it print `n/a` rather than a
  number that looks like a measurement.

**Context.** Over the same 38 dates the equal-weight benchmark's own median
5-session return was −0.41%. The placebo's −2.52% is the small-cap tilt of this
cohort, not the market.

## 3. Where the loss is worse, and where it is milder

| cut | n | dates | Δ vs placebo | interval | green |
|---|---|---|---|---|---|
| **all, 5 sessions, open** | 1,231 | 31 | **−4.78pp** | [−7.19, −3.41] | 29.2% |
| all, 5 sessions, close entry | 1,214 | 31 | −3.63pp | [−6.18, −2.34] | 32.2% |
| all, 1 session, open | 1,483 | 35 | −0.48pp | [−1.14, +0.13] | 43.8% |
| tier A accounts | 466 | 29 | −2.25pp | [−3.96, −0.82] | 34.1% |
| tier B accounts | 751 | 22 | **−6.55pp** | [−10.62, −4.81] | 26.5% |

Tier A is meaningfully less bad than tier B and both intervals still sit below
zero. **Tier S is 14 events on a single date and is not quotable.** Neither is
the 21-session cell (65 events).

**Per account: 13 accounts have 20 or more events, all 13 point negative, and
not one clears the cluster minimum for an interval.** The sign is unanimous; the
evidence per account is not there. No account is a counter-example and none is
established as worse than the rest.

## 4. What the cohort actually is

From the same run, over all 3,452 tag events:

| | |
|---|---|
| traded under $2 at the tag | 39.6% |
| median 50-day dollar volume under $5M | 69.4% |
| known market cap under $700M | 70.3% |
| cap unknown entirely | 22.1% |
| moved 8% or more on the tag day | 38.1% |
| "ran" by the board's own definition | 36.4% |
| **dumped within 21 sessions** | **31.8%** |
| median worst drawdown over 21 sessions | **−35.3%** |

This is a microcap tape. A third of these names are down more than a third
within a month of being posted about.

## 5. Out of sample

The promo roster was itself assembled inside the earlier window, so the
in-sample leg is biased by construction. Splitting at 2026-09-03:

| leg | n | dates | Δ | interval |
|---|---|---|---|---|
| in-sample | 816 | 31 | −6.51pp | [−11.58, −3.79] |
| out-of-sample | 415 | **8** | −2.87pp | **n/a — 8 clusters** |

**The out-of-sample sign agrees and its magnitude does not.** Eight entry dates
cannot carry a percentile bootstrap, so that leg is a sign check, not a
measurement. A date-clean out-of-sample verdict needs roughly three more weeks
of tags: **re-run after 2026-10-12**.

## 6. Stability

The same script at seed 11 reproduces the point estimate exactly (−4.78pp) and
the date interval to within 0.06pp.

A third run, launched separately the same evening and re-fetching every stale
name from the provider rather than reading the price cache, reproduced **every
field of the measured literal identically** — the event count, the cluster
count, the delta, both intervals and the placebo median. The result is not an
artifact of which names happened to be cached.

## 7. What this does not say

- **It is not a short signal.** There is no entry rule, no stop, no borrow cost
  and no cost model here. A median that loses five points a week to its peers is
  a reason not to chase, not a trade.
- **It does not grade an account.** No per-account cut clears the cluster
  minimum.
- **It does not cover names with no US bars.** Those are absent by construction.
- **The placebo match falls back.** For 1,516 events the exact cap × liquidity
  cell was empty and a wider cell was used. That loosens the match; it does not
  change the sign.
- **It says nothing about the curation lane's floors.** Whether $2 and $5M are
  the right numbers at a universe gate is a separate question and his call.

## 8. His call

1. The verdict is served on the 🎪 chip as *"inverted — do-not-chase radar; not
   a source of entries"*. Does he want that wording on the board banner too?
2. Should the promo feed drive a **negative** surface — for instance suppressing
   a promo-tagged name from an entry lane for five sessions? That would be a new
   gate and is not built.
3. Re-run on 2026-10-12 for the date-clean out-of-sample leg, or sooner?
4. Tier A is measurably less bad than tier B. Worth showing the tier on the chip,
   or does that read as a quality ranking it is not?

---

*Script: `backend/scripts/promo_tag_study.py`. Artifact:
`backend/scripts/promo_tag_measured.json`. Pins:
`backend/tests/test_promo_tag_measured.py`. The curation lane it feeds:
`docs/catalysts/promo_curation.md`.*
