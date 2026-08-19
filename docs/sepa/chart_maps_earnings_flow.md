# Earnings Flow — institutional volume around the print

Ajay 2026-08-19:

> *"I need a tracker on the Chart maps page a new tab.. Where it tracks earnings
> that had huge instituonal volume. Like BULL for example and TGT"*

Code: `backend/chart_maps/earnings.py` (detector),
`backend/chart_maps/board.py::earnings_tiles` (tiles),
`frontend/src/lib/chartMaps.ts` (tab).
Tests: `backend/tests/test_chart_maps_earnings.py` (28),
`frontend/src/lib/chartMaps.test.ts` (+5).

---

## 1. His two examples were two different events

Checked before writing anything, and they do not describe the same thing:

| | what the calendar said | what the tape did |
|---|---|---|
| **TGT** | `next_date 2026-08-19`, reported that morning | gapped **down** to 147.80 from a 152.48 close, traded as low as 146.21, closed **159.00** on 2.2x volume |
| **BULL** | `next_date 2026-08-19`, **`when: AMC`** — had not reported at all | +8.95% on 3.1x volume **into** a print landing after the close |

So one is a post-report reaction and the other is pre-report accumulation. He
then asked for *"current day only or next day earnings"*, which is exactly
those two halves — and later *"pre earnings bullish momentum is also fine.. If
Institutions are coming in I want to ride along the momentum"*.

The board therefore has two groups and never merges them: a name that has told
the market its numbers and one that has not are different risks.

## 2. Built on the existing stack, not beside it

Ajay: *"We do have a earnings tracking component on the SEPA dashboard and
multiple places.. Look at that and see where it pulls stuff from"*. Surveyed
first:

| module | role | reused? |
|---|---|---|
| `sepa/earnings_watch.py` | calendar — yfinance → Mongo `earnings_calendar`, 3,096 names with BMO/AMC | **yes** |
| `sepa/earnings_picks.py` | `reaction_read()` anchors the reaction bar for BMO vs AMC | **yes** — the one genuinely subtle thing here |
| `sepa/earnings_quality.py` | accrual read on the detail page | no, different question |
| `setups/post_earnings_drift.py` | PEAD by pure price | no |

**What that stack could not answer**, measured on the live doc rather than assumed:

* it is a **nightly** doc (cron 19:10) and was **23 hours old** when checked, so
  TGT and EL — which reported that morning — could not be in it at all;
* **no size floor**: only **12 of its 21 picks** traded ≥$50M on the reaction
  bar; the rest were CAMP $2M, DERM $5M, AURA $8M;
* it **ranks by reaction %**, so micro-caps win — CURI sat second at +42.5% on
  $81M while TGT (**$1.5B**) and EL (**$1.33B**) were absent entirely;
* **no close-location test**, so a +8% gap closing on its low passes every gate;
* nothing anywhere reads volume **before** a report.

This module adds exactly those and borrows the rest. `EarningsReportPicks` is
left untouched — it answers "what reacted well this week" for three other pages.

## 3. What "institutional" means

Three conditions on the reaction bar, each answering a different question. Size
alone is not enough: **VIK printed 2.37x volume the same day and closed at 0.01
of its range** — enormous participation, all of it selling.

| test | threshold | why |
|---|---|---|
| **Participation** | volume ≥ **1.5x** the 60-day **median** | median, not mean — one prior earnings bar in the window drags a mean up and quietly raises the bar for the next report |
| **Who won the day** | close in the top **40%** of the bar's range | the discriminator. TGT 0.81 and BULL 0.92 pass; VIK 0.01, TJX 0.30, BILL 0.23 do not |
| **Size** | ≥ **$50M** traded | a ratio is scale-free, which is exactly wrong here. COTY cleared 1.7x on **$47M**. Same constant as `demand_reentry.LIQ_DEEP_USD`, imported |

Plus: **up on the day**. Buying only — he was offered the distribution mirror
and declined it, so `is_institutional_buy` returning False for a 5x-volume
collapse is the intended answer, not an omission.

## 4. Same day only

His correction after **UI** appeared at two sessions out:

> *"remove the ones that are coming not pre earning of same day earnings and
> institutions momemtum is there. I do not want to see those on the list."*

So `LOOKAHEAD_DAYS = 0` and the scored bar must be the latest session. **Every
tile on this board is today's bar.**

The look-**back** is deliberately asymmetric (`LOOKBACK_DAYS = 2`): a report
landing after *yesterday's* close has its reaction bar **today**, and most
reports are after the close. Dropping those would hide the majority of them.

## 5. The board on 2026-08-19

```
REACTED                                                   $ traded
  TGT    +4.28%   2.2x   close-in-range 0.81  gap -3.07%   $1.50B
  EL    +16.25%   4.6x   close-in-range 0.71  gap +11.18%  $1.33B
UPCOMING (reports tonight, after the close)
  BULL   +8.95%   3.1x   close-in-range 0.92               $281M
  NDSN   +1.88%   1.8x   close-in-range 0.87               $186M
```

TGT carries a **"Bought the gap down"** badge — a gap down that closes near the
high is the most informative thing on the tile, because institutions did not
just buy, they bought what everyone else was selling.

## 6. Riding into the print

He chose to see pre-report accumulation. `earnings_watch` exists in this
codebase **because ATEX passed every technical gate, was bought, and reported
that evening at −28% surprise**. So every upcoming tile states when the print
lands — "tonight, after the close" — in an amber badge. The tile does not argue;
it makes the binary event impossible to miss so that holding through it is a
choice rather than a surprise.

## Honest limits

* **Thresholds are house values measured on one day's tape**, not a book method
  and not a backtest. No forward record exists yet.
* **Close-in-range is a daily-bar proxy for intent.** It cannot see who traded —
  a retail stampede that closes on the high looks identical. The $50M floor
  makes that unlikely, not impossible.
* **`when` is null for some names** (TGT's own row is). Unknown timing on a
  dated report is treated as already released, which is the conservative side.

---

## Where the honesty is enforced

| Decision | Guard |
|---|---|
| His two names pass on their real numbers | `test_the_two_names_he_named_pass_on_their_REAL_numbers` |
| A high-volume collapse is not a buy | `test_a_high_volume_COLLAPSE_is_not_a_buy` |
| A gap that fades to the low is not a buy | `test_a_big_gap_that_FADES_to_the_low_is_not_a_buy` |
| A thin name fails however violent | `test_a_thin_name_fails_however_violent_the_move` |
| An unmeasurable field fails, never skips | `test_a_missing_measurement_FAILS_rather_than_being_skipped` |
| A bool or a string is not a measurement | `test_a_bool_is_not_a_measurement`, `test_close_location_refuses_junk_instead_of_returning_a_number` |
| AMC today has NOT been seen by today's bar | `test_an_AFTER_CLOSE_report_dated_today_has_NOT_been_seen_by_todays_bar` |
| Unknown timing = already out | `test_unknown_timing_on_a_dated_report_is_treated_as_ALREADY_OUT` |
| No look-ahead past today | `test_the_board_does_not_look_AHEAD_past_today` |
| Still catches after-close reporters | `test_it_still_looks_BACK_far_enough_to_catch_after_close_reporters` |
| The reaction bar uses the shared reader | `test_the_reaction_bar_is_located_by_the_SHARED_reader` |
| No second calendar fetcher | `test_it_reads_the_SHARED_calendar_and_never_fetches_its_own` |
| Ranked by size, not by % move | `test_ranking_is_by_SIZE_not_by_percentage_move` |
| The tab says the print may be pending | `has copy that states the two halves AND that the print may be pending` |
