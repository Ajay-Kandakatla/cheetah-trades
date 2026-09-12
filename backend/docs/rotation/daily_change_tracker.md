# Daily rotation change tracker — 2026-09-12

> Ajay, on the six-row ~35-chip Hot-sectors strip:
> *"this whole thing is super messay ... I am trying to see what changed if
> there is no change continously same sectors continue to show the top for
> example energy has been continous."*
> and, on the screenshot: *"this is what I mean when I said messy"*.

## The idea in one line

**Energy at #1 for eight days is ONE fact, not eight.**

The strip reprinted the same wall of chips every session, so the reader had to
diff it by eye, and nothing could tell him the answer was simply *no change*.

## What was actually missing

Nothing in the app stored a rotation history. `scan_context` holds exactly
three documents (`iv`, `rotation`, `summary`), **latest-only** — yesterday's
ranking was gone the moment today's scan finished. No amount of frontend work
could have produced a delta; the data did not exist.

## Storage

| | |
|---|---|
| Collection | `rotation_history` |
| Document id | the payload's **own `as_of`**, never "today" |
| Grains stored | `sectors`, `industries`, `themes`, `cohorts` |
| Ranked by | `rel_5d` (the leg the strip itself ranks by) |
| Retention | `KEEP_DAYS = 400` |

Per group: `rank`, `rel_1d`, `rel_5d`, `rel_21d`, `n`.

**A payload with no `as_of` is REFUSED, not stamped with today.** A document
keyed to the wrong day corrupts every delta computed after it, which is far
worse than a missing day. Pinned by
`test_NEGATIVE_a_payload_with_no_as_of_is_REFUSED_not_stamped_with_today`.

A missing rank leg sorts **last**, never first — a blank must not read as 0.0
and take rank 1 in a down week
(`test_NEGATIVE_a_missing_leg_sorts_LAST_and_never_wins_rank_one`).

## What is computed — `changes()` / `changes_all()`

| Field | Meaning |
|---|---|
| `entered` | crossed **into** the top band (`TOP_N = 6`) |
| `left` | crossed **out** of it |
| `moved` | rank delta ≥ `MIN_MOVE = 2`, biggest first; positive delta = climbed |
| `streaks` | consecutive **stored** sessions a group has held its *current* rank |
| `top` | the current top band, in order |
| `quiet` | nothing crossed and nothing moved by `MIN_MOVE` |
| `baseline` | the previous **different** session compared against |

`quiet: true` **is the answer**, not an empty result. It is what lets the strip
collapse from ~35 chips to one line, and it is why the component prints
"no rank change since 2026-09-11" rather than rendering nothing — an empty
strip reads as a broken scan.

### `changes_all` and why the strip uses it

The strip below the line renders **cohorts, industries AND themes**. A
single-grain answer would let it print a confident *"no change"* on a session
where themes reshuffled underneath — a false sentence, which is worse than the
chip wall it replaced. `changes_all` therefore ANDs `quiet` across every grain
and keeps each grain's own answer under `grains`, so a mover can be named with
the grain it moved in. The history is read **once** and handed to every grain,
so four grains can never end up with four different baselines if a scan lands
mid-request. Pinned by
`test_NEGATIVE_quiet_is_FALSE_when_ANY_grain_moved_even_if_the_headline_did_not`.

### The streak bug that was caught

The first implementation marked a broken streak by setting the **count itself**
to `None` and then restoring it as `1` — silently discarding the sessions
already counted, so a genuine 2-day streak reported as 1. The fix tracks a
`live` set separately from the count. Pinned by
`test_a_streak_BREAKS_when_the_rank_changed_and_does_not_count_past_it`.

## API

```
GET /rotation/changes?grain=all&top_n=6&min_move=2
```

`grain` defaults to `all`; `sectors` | `industries` | `themes` | `cohorts`
return that one grain's answer.

## When it is written

1. **Every scan** — `sepa.context_refresh.refresh_rotation()` stores the
   session's ranking after it persists the rotation doc. Fenced in
   `try/except`: a history write must never fail the scan refresh that
   produced the data.
2. **17:20 CT weekdays** — `market_hours.gate rotation.history snapshot`
   stores the session's final ranking off the **persisted** doc and prunes.
   It reads Mongo and **never rebuilds**: `tracker.build` is a multi-minute
   full refetch whose cache is in-process, so a cron-container rebuild would
   burn provider quota to warm a cache the API never sees.

Both are idempotent — the `_id` is the payload's `as_of`, so a re-run upserts
the same day rather than inventing a second one.

## The frontend

`frontend/src/components/RotationChanges.tsx` renders one line above the board:

- **quiet** → `no rank change since 2026-09-11 · Energy #1 · 8d still leading`
- **moved** → crossings first (`＋ robotics 9→2`, `－ quantum 5→11`), then
  re-orderings inside the band (`▲ Utilities 7→3`), capped at
  `MAX_MOVERS = 4` with the remainder **counted** as `+N more` — never
  silently truncated — and the steady leader kept on the end.

The ~35 chips are **kept**, folded behind a `full board (N chips)` toggle that
defaults closed. This is a declutter, not a deletion; the contract
*"the Hot-sectors strip leads with what CHANGED, board folded (2026-09-12)"*
checks every chip group is still inside the fold.

Nothing here recomputes a rank — two definitions on two surfaces is exactly how
the strip and the board would start disagreeing.

## Day-one limit

There is no stored history until a second session lands, so the first render
honestly says **"first snapshot — no prior session to compare"**. Streaks count
**stored** sessions only and start from today — `Energy #1 · 8d` cannot appear
until Energy has actually held #1 for eight stored sessions.

## What this does NOT claim

A change detector over a ranking with **no measured forward edge**:

- sector heat did **not** predict demand outcomes (2026-09-09: −0.57pp, the
  interval spanning zero), and **cold** sectors beat hot ones over 5 days by
  2.55pp;
- the rotation backtest gives top-3 rotation **158.22%** against RSP
  **155.42%**.

**A shift being visible is not a reason to trade it.** This makes the board
readable in two seconds; it does not make it profitable. Nothing here gates a
scan, an alert or a lane.

## Re-run

```
docker compose exec cron python -m rotation.history show 10
docker compose exec cron python -m rotation.history snapshot
```
