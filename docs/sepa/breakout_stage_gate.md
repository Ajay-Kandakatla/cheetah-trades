# Breakout board — the stage gate

**Asked 2026-09-12.** Ajay: *"From the breakout remove any S3. Only S2 stocks and
if thy have explosive growth its ok to have s1 and s3. If they are newly found
explosive growth"*.

## The rule

`backend/sepa/breakout.py`

| Stage | Meaning | On the board |
|---|---|---|
| 1 | Basing / neglect | **only** if explosive grower |
| 2 | Advancing | **always** |
| 3 | Topping / distribution | **only** if explosive grower |
| 4 | Declining | **never** — not even explosive |
| unknown | classifier had no answer | **kept** |

One predicate, `_stage_ok()`; the constants `STAGE_KEEP=(2,)`,
`STAGE_EXCEPTION=(1,3)`, `STAGE_NEVER=(4,)` are the rule — nothing re-types a
stage number inline.

Two decisions he did not spell out, and why:

- **Stage 4 is never excepted.** He named 1 and 3. A name in a confirmed
  decline is in a decline whatever its income statement says, and the page has
  called S4 "avoid" since it shipped.
- **A row with no stage is KEPT.** Dropping a name because the classifier could
  not read its frame hides it for a reason that has nothing to do with the
  stock. Same discipline every other unknown in this app gets.

Stage source is the existing SEPA classifier (`sepa/stage.py`, Minervini TLSW
p.71-72 — MA geometry plus volume confirmation). The gate does not re-derive it.

## Where it runs — before the cut

This is the part that matters numerically. `board()` order:

```
build rows → AI-sector tag → explosive tag → STAGE GATE → sort by recency → rows[:top]
```

The gate runs **before** `rows[:top]`, so the 250 rows returned are 250
*qualifying* names. Filtering the already-cut 250 would have left ~80 and
silently thrown away every qualifying name ranked 251st onward.

MEASURED on the live board, 2026-09-12:

| | rows | stages |
|---|---|---|
| `stages=false` | 250 of 2,840 | {1: 111, 2: 78, 3: 35, 4: 26} |
| `stages=true` | **250 of 350 qualifying** | {1: 4, 2: 240, 3: 6, 4: 0} |

All ten S1/S3 survivors are explosive growers. No S4 survived. The page reports
the drop as a `✓ S2 only (−N)` chip — a filtered board must never read as if
the whole market were breaking out.

Off switch: `GET /sepa/breakout-board?stages=false`. Default is **on** — his ask.

## "Newly found"

He wrote *"If they are newly found explosive growth"*. The growth board doc is
`_id: "latest"` — latest-only, no arrival history — so "newly found" was not a
question the app could answer. Added `growth_seen` (`growth/tracker.py`):
`_record_seen()` stamps each symbol's first sighting on every build, and
`newly_found(days=NEW_GROWTH_DAYS)` returns arrivals inside that window.

A `__meta__` row stores `tracking_since`, so nothing counts as "new" on the
first build — otherwise every name on day one would look like an arrival.

**Interpretation, stated plainly:** the S1/S3 exception is open to *any*
explosive grower, and the ✨ badge marks the newly-found ones. The stricter
reading — exception only for newly-found names — would have dropped IPI and
NVDA on day one, because `newly_found()` returns empty until tracking has
observed an arrival. The strict variant is a one-line change if he wants it.

## Tests

`backend/tests/test_breakout_stage_gate.py` (13). Mutation-tested 2026-09-12 —
all four caught: unknown-stage dropped, S4 excepted, exception ignoring
`explosive`, gate moved after the cut.

## Not a claim

The gate is a **filter on what he sees**, not a measured edge. Nothing here says
an S2 breakout outperforms an S3 breakout in this app's own data — that study
has not been run. It implements his rule.
