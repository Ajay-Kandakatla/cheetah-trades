# 🎯 Ready to enter — the premarket + session entry lane

Ajay 2026-09-09: *"I would like to see you ready to enter premarket category for
me from In demand and Deep demands with crons firing in the morning to scan at 7
CT and another one regular market session but I need an entry signal with mood
considered and demand zone and other criterate we discussed I wanna see this
category in the signals page with a section for it."*

Code: `backend/supply_demand/premarket_entry.py`. Endpoint:
`GET /supply-demand/premarket-entry`. Surface: the section that leads the
⚡ Signals tab (`frontend/src/components/PremarketEntry.tsx`), which is
`/chart-maps?tab=signals` and the `/signal-lab` page.

**Owner rules on price structure. Not a book method, not advice, and nothing
here places an order.**

## The three boards, three questions

| board | question |
|---|---|
| Back in Demand / Deep Demand | which names sit at a demand level (daily) |
| Session (`session_board`) | is the tape confirming that level |
| **Ready to enter** (this) | **which of them can I enter right now, and why not the rest** |

No new zone maths. The level, band and room all come from the one
`demand_reentry` cache the two tabs read, through
`session_board.board_symbols`, so this board cannot disagree with the tabs it
is cut from.

## What decides a row

### Two gates — the standing rule, unchanged

Both come from `supply_demand/alert_gates.py`; this module holds no copy of
either threshold (pinned by `test_the_gates_are_the_standing_ones_and_are_not_relaxed_here`).

| gate | rule | constant |
|---|---|---|
| room | ≥ 5% to the first **proven** band overhead (2+ touches). CLEAR passes, IN_BAND fails. | `ALERT_MIN_ROOM_PCT` |
| proximity | the print is at the band or within 1% above its top, never under the floor | `ALERT_MAX_ABOVE_DEMAND_PCT` |

Ajay 2026-09-08: *"Make sure signals are more accurate do not mean to loosen
up."* Nothing here widens a gate. The lane only adds grading on top.

### Two drags — measured, not chosen

From the 2026-09-08 autopsy of 286 graded demand pushes
(`sd_autopsy_2026_09_08`). Every number below is a measured rate, and the row
wording is built from the same constants, so if the study is re-run the text
moves with it.

| drag | measured | constant |
|---|---|---|
| reclaiming the band from below | hit the floor stop **66%** of the time, against **11%** for arrivals from above (115/286 pushes were reclaims) | `RECLAIM_STOP_PCT` |
| a −3%..−8% day | closed above the alert print **22%** of the time (n=51), against **57%** on −3..0 days | `WEAK_DAY_*` |

A gap at or beyond −8% is **not** dragged: it measured 67% up (n=6) and is
already handled by `alert_gates.gap_day`. Dragging it here would contradict the
study.

### The grades

| grade | meaning |
|---|---|
| **READY** | clears both gates, carries no drag |
| **WATCH** | clears both gates, carries a drag — the row says which and quotes the rate |
| **BLOCKED** | fails a gate — still listed, with the reason |

Boards list everything; gates decide only what is tradable. A drag never
silently removes a name — he asked to see the distinction in writing.

## Mood is context, never a gate

Ajay 2026-09-08: *"I do want signals to sell based on Supply demand but not on
mood. But do include mood in the overall criteria of the stocks for alerts becuz
mood determins if stock grows faster from demand or not."*

`alert_gates.mood_rank` is the **third** key in `sort_key`, after the grade and
the drag count, so mood can only ever reorder rows that already share a grade.
`grade_row(room_ok, prox_ok, drags)` does not take mood as a parameter — a
signature-level guarantee, pinned by `test_grade_row_cannot_see_mood_at_all`,
which parses the function body and asserts the word does not appear. The mood
watcher was **deleted** on 2026-09-08 after a wrong DYN sell; this must not
become it again. The frontend contract "Ready-to-enter grades never read mood"
pins the same rule on the UI side.

Mood is read only for rows that clear both gates: it is context on a tradable
row, never a reason to look at an untradable one, and it costs a frame per name.

## The two passes

| pass | when | price it reads |
|---|---|---|
| `premarket` | 04:00–09:30 ET | the snapshot's extended-hours last trade (`prices.extended_print`), because the day aggregate is still empty |
| `session` | everything else | the regular-session close, falling back to the extended print |

A premarket row is a plan for the open, not a fill. The session pass adds
`confirm_read` — the follow-through since the level was reached, in the three
measured buckets:

| move | measured | state |
|---|---|---|
| ≤ −1% | 28% closed up, floor stop hit 89% | `fading` |
| 0..+1% | 61% closed up | `holding` |
| > +1% | 77% closed up, but **entering after that lift won only 23%** | `chase` |

`chase` is information, not an invitation: the lift was the gain.

## Crons

The container clock is ET, so **07:00 CT = 08:00 ET**.

```
0      8     * * 1-5   premarket-entry?pass=premarket ... &record=true
20     8     * * 1-5   (same)
0      9     * * 1-5   (same)
35,50  9     * * 1-5   premarket-entry?pass=session ... &record=true
*/15   10-15 * * 1-5   (same)
```

They **curl the endpoint** rather than running the module. The board is served
from the API process's own memory, and `python -m supply_demand.premarket_entry`
in the cron container would warm a different process and leave the page cold —
the same trap the 09:25 `demand-reentry` warm exists to avoid. `record=true`
makes that one scan also land in Mongo `premarket_entry_runs`, so the grades can
be graded forward later.

`record` is gated on `market_hours.gate.closed_reason`, so a holiday cron cannot
write a history row computed from stale prices. The **board** still renders on a
closed day, on purpose — he asked on 2026-09-05 for the bounce/room reads to
answer on a Saturday evening off the last session.

`zone_store.load_latest` (not `load`) supplies the bands, for the same reason:
before the 04:05 warm, or on a weekend, TODAY has no doc and every row would
fail the room gate for want of bands.

## Tests

`backend/tests/test_premarket_entry.py` (40): the measured constants; the gates
are the standing ones and hold no local copy; the reclaim drag reads `dir` and
not `tag`; every other direction carries none; the −3..−8% bucket edges and the
gap-day exclusion; grading truth table; blocked rows still say why; mood cannot
reach the grade and only breaks ties; the three follow-through buckets and their
float-safe edges; the pass split at 09:30; the row builder (clean, under the
floor, no room, clear runway, premarket pricing, no price, no band, derived
change, reclaim, stacked drags); every rules line built from its constant; the
closed-day and warming guards on `record`.

`frontend/src/components/PremarketEntry.test.tsx` (12): pure formatters never
print NaN; grouping; the headline; READY leads and WATCH follows; the drag is
spelled out with its rate; mood prints on every row labelled *context only*;
BLOCKED is behind a click but never dropped; the pass selector changes the
request; the rules panel; warming vs empty vs closed vs error; a row of nulls;
collapse. Frontend contracts: "Signals tab leads with the Ready-to-enter
section" and "Ready-to-enter grades never read mood".

## The regression this shipped with

The first live run graded WLDN and WLFC **READY** while both printed
"↑ reclaiming the band from below". `approach_read` returns `dir='reclaiming'`
and `tag='↑ reclaiming'` — the machine key and the display string. The drag
matched on `tag`, so it never fired and every reclaim graded READY. Fixed to
read `dir`; `test_reclaim_is_dragged_by_dir_not_tag` asserts both fields so the
next reader cannot repeat it. READY fell from 12 to 10 on that pass.

## Known limits (v1)

- The `confirm` field is populated only where a level-reached time exists; the
  first version leaves it `null` on most rows. Grading the READY/WATCH split
  forward against outcomes needs ~2 weeks of `premarket_entry_runs`.
- The drags are measured on 286 pushes over two sessions (9/4 and 9/8). That is
  a real sample but a small one — re-run the study before treating 66% and 22%
  as stable.
- No placebo yet for the grade itself: we know reclaims are worse, not that
  READY beats a random name at a level.
