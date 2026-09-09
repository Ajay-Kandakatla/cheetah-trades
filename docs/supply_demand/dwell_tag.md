# 📌 How long has it been sitting there?

Ajay 2026-09-09: *"I wanna have dates on the chart map stocks it has to tell if
they are there form yesterday or todays scan"* … *"May be tag them to say they
are in demand zone for 3 days or so... Cuz I have seen some stocks sitting
there"*.

Code: `chart_maps/board.py` — `dwell_text()`, `_dwell_decor()`.
Tabs: **Back in Demand (`zones`)** and **Deep Demand (`deep_demand`)** only.
Tests: `backend/tests/test_dwell_tag.py` (16).

## Where the number comes from

Nothing new was computed. `supply_demand/demand_history.py` has been writing
`demand_episodes` since 2026-09 — one document per continuous stretch a name
spends on the Back in Demand board, carrying `first_seen`, `last_seen` and
`appearances`. **The frontend had never read it.** This tag is a join.

| badge | when |
|---|---|
| `🆕 new today` | `appearances == 1` |
| `📌 3 board days · since Sep 5` | `appearances >= 2` |

Plus a stat, `On board · 3d`.

## Two things it deliberately does not say

**It counts BOARD DAYS, not calendar days.** A name first seen Aug 26 with 13
appearances sat through 13 scans, not 14 days. Weekends, holidays and any day
the scan failed are simply not in the count, and the badge says "board days" so
the screen cannot imply otherwise.

**Every tier is toned `muted`.** Nothing has measured whether a long sit is
good (a base building) or bad (a zone quietly failing). Colouring day 13 amber
would put a verdict on his screen that this app has not earned, so a test
(`test_the_tag_never_carries_a_verdict_colour`) pins all tones to muted until a
study says which it is. **This is the open follow-up.**

## Why only the two demand tabs

`demand_episodes` is written from the Back in Demand board
(`demand_history.record_board`). The count is meaningless on a VCP or topping
tile — that name's episode, if any, describes a completely different board. A
source guard (`test_both_demand_tabs_tag_and_the_others_do_not`) asserts
`_dwell_decor(out)` appears exactly twice and never inside `vcp_tiles`,
`topping_tiles`, `undervalue_tiles` or `gabbar_tiles`.

## Episode boundaries

`demand_history.EPISODE_MAX_GAP_DAYS = 10` closes a stale episode, and
`EPISODE_BAND_TOL_PCT = 2.0` requires the band to be the same one. So a name
that left the board and came back reads as **day 1 again**, which is the honest
read — it is a new arrival at that band, not a continuation. Where a symbol has
several episodes the newest `last_seen` wins.

## Failure modes, all silent by design

The tag is decoration. No Mongo, a raising Mongo, a missing episode, a garbage
`appearances` (0, negative, None, NaN, a string) — every one leaves the tile
completely untouched, badge list and stats list not even created. A board that
loses its dwell tags still renders; a board that 500s because of a decoration
would be a much worse bug.

## Live at the time of writing

1,247 episodes. The longest sit is AIG — on the board since **2026-08-26, 13
board days**, which is the case he described.
