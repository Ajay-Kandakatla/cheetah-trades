# 👀 Gajjala's Watch — 🤖 auto potentials (2026-11-17)

**UNMEASURED — display / selection only. No study has read what follows an auto-add; nothing here claims an edge.**

## His words

Ajay 2026-11-17: "Can you add more stocks in to watch list basically I need portentials from Gajjals's 1 min and regular
and also Audited potentials with good volume to Watchlist on an interval.. Remove as they are not progressing"

## The rule in words

Once a minute, inside the watch's own minute loop (`loop.run_iteration`, under its lease, before the frame build), the
engine `backend/chart_maps/gajjala_watch/auto.py` (`step`) reads what the three Gajjala boards already stored. It never
fetches bars for this.

- **Add** (*source and cap rule SUPERSEDED 12:55 — see "Accumulate (12:55 ET)" below*) (only inside the 🚩 pass window, `run.in_window`, 04:00–20:05 ET on a market day): a 🧠 potential
  (`potential.potential_kind`, the board's own test: forming, a base begun, no variant / grade) of a LISTED read on the
  🚩 5-min board (GG5) or the 🚩 1-min board (GG1). Today's volume must be at least `AUTO_MIN_VOLUME`, which is GG's K11
  floor of 1,000,000 shares. Names on his own list are never added. A name he × removed is not added again until the
  session changes. At most `AUTO_MAX_SYMBOLS` (18) auto names at a time. A louder potential never pushes an existing
  auto name out.
- **The 🧪 board**: the 🧪 board borrows GG5's reads and potentials (`variant.GGA.borrows`). A GG5 potential is
  therefore tagged "🚩 5-min · 🧪", and no third read set is needed. A test pins
  `"gajjala_potentials" in V.GGA.borrows`.
- **Order** [C4]: auto names stay in the order they were added. A batch added in the same minute lands in
  `potential.order_key` order: armed before building, louder volume first, then lower float. After that nothing moves.
  This is the same rule as his own list ("his list order").
- **Remove — not progressing** [C1]: a name is removed at once, with the card's own ⏸-line sentence, when every board
  reads it ↩️ back under or ✖️ stop printed. The test is `breakout_state.block` over the stored read doc's own tile
  bars. **⏸ waiting KEEPS the name.** Waiting means it is holding at or above the trigger with no new high since, which
  is the consolidation after GG's entry signal. A fresh break (no line yet), 🔊 / 🔇 / ⤴️ and a 🧠 potential on any board
  also keep the name. An unknown state (1-min `off_chart`, a read fault) keeps it too.
- **Remove — dropped** [C3] (*SUPERSEDED 12:55 — a lapsed name now stays; see "Accumulate (12:55 ET)" below*): a name that is a 🧠 potential on no board, with no broke read keeping it, gets
  `dropped_since` stamped. It is removed only after `AUTO_DROP_GRACE_SEC` (= `GC.PASS_CADENCE_SEC`, 300 s). If it is a
  potential again within that time, the stamp clears. A name gone from a non-empty listed set reads "🪦 graveyard" and
  gets the same grace.
- **Moved to his list**: when he ➕ adds an auto name to his own list, it leaves the auto section ("➕ now on your list").
- **His ×**: the DELETE route calls `auto.dismiss`. The name is pulled and recorded, and it is blocked for the rest of
  the session. A × on one of HIS names also blocks an auto re-add that session (HIS CALL #6).
- **Session**: the doc carries its session. A new session clears entries, removed and dismissed (HIS CALL #5). A ×
  landing on a stale doc does that reset itself [C7]. Before 04:00 ET, `build.session_of` is the LAST market session,
  the same session the board shows then. A × at that hour goes into that session's doc, and the 04:0x step's reset
  clears it. A × between 04:00 and the first step lands in today's doc and holds.
- **Push**: auto names never ring the 1-min 9 / 21 cross (`AUTO_PUSH_MODE "off"`). The loop gives
  `cross_alerts.run` (byte-untouched, sha-pinned) the frames of HIS names only. An auto name's own-minute up cross is
  held as `suppressed_auto` (`auto.hold_crosses`, never sent, never claimed).

## Constants (backend/chart_maps/gajjala_watch/constants.py — every number by name)

| Name | Value | From |
|---|---|---|
| `AUTO_DOC_ID` | "auto" | the second doc of `gajjala_watch_list` (his doc is `"owner"`) |
| `AUTO_MAX_SYMBOLS` | 18 | `GC.GG_WATCH_N` ("He watches 18 stocks simultaneously") — HIS CALL #1 |
| `AUTO_SOURCES` | gajjala, gajjala_1m, gga | `== (V.GG5.key, V.GG1.key, V.GGA.key)` (test pin) |
| `AUTO_READ_SOURCES` | gajjala, gajjala_1m | the two stored read sets |
| `AUTO_MIN_VOLUME` | 1,000,000 | `GC.K11_MIN_SESSION_VOLUME` — HIS CALL #2 |
| `AUTO_VOLUME_SOURCES` | scan, tracker | [C2] precedence |
| `AUTO_REMOVE_STATES` | back_under, stop_printed | `breakout_state.STATES` — HIS CALL #3 |
| `AUTO_KEEP_STATES` | waiting, broke_vol, broke_quiet, broke_unjudged | [C1] |
| `AUTO_DROP_GRACE_SEC` | 300 | `GC.PASS_CADENCE_SEC` — HIS CALL #9 |
| `AUTO_REMOVED_SHOWN` | 18 | `AUTO_MAX_SYMBOLS` (served; every event stays stored) |
| `AUTO_PUSH_MODE` | "off" | HIS CALL #4 (`AUTO_PUSH_MODES = GC.FADE_CROSS_PUSH_MODES`) |
| `AUTO_HELD_REASON` | suppressed_auto | appended LAST to `HELD_REASONS` |

## The stored doc (`gajjala_watch_list`, `_id: "auto"`)

```
{_id: "auto", session: "YYYY-MM-DD", rev: int,
 entries: [{symbol, sources, setup, kind, volume, volume_source: "scan"|"tracker", float_shares,
            added_at (UTC), added_et "HH:MM", dropped_since: UTC | null}],     # add order, frozen
 removed: [{symbol, at, at_et, reason: not_progressing|dropped|dismissed|on_your_list|made_room, state, source, text}],
 dismissed: ["SYM", …], updated_at, by}
```

Every write is ONE compare-and-set `update_one` on `{_id, rev}` with `$set`. A write that loses the race re-reads and
recomputes, up to the watch store's `_CAS_TRIES`. Nothing is written when nothing changed. His `owner` doc is never
written by the engine; a test runs 50 steps over every state and finds that doc byte-identical.

## Volume precedence and why [C2]

"Today's volume" means what K11 reads. The scan row's `last.volume` comes first, because it is the number the 🧠 board
orders by. When there is no scan row, the engine uses GG5's tracker `last.session_volume`, which `run.py` stores on
every pass for every tracked potential (`potential._last_block`). With neither number the volume is unknown: the name is
refused and counted `skipped.volume_unknown`.

The fallback matters because of the critique probe at about 11:00 ET on 11-17. GG5 listed 102 names, but only 23 had a
scan doc that day, so **79 carried names had no scan row**. XXII, the only GG5 potential at that moment, had no scan
row; its tracker number was 1,123,834, which clears the floor. GG1's tracker writes no `session_volume`
(`run_1m.py:371-376`), so a GG1-only potential with no scan row and no GG5 tracker that day stays unknown (HIS CALL #16).
Relative volume (`ctx.rvol`) is a ratio with a projection. Using it would be his number to pick (HIS CALL #2).

## Loop wiring and the counts [C6]

- The order is: his list, then `auto.current_symbols` (read-only, before the lease), then the lease, then `auto.step`.
  Next come the frames for his names + the auto names (his first, the auto names in add order), then the cross push
  (his frames only while the auto mode is off) and `hold_crosses`, then the tiles and the state doc.
- With nothing listed and nothing auto, out of the window, there is no lease (as before). IN the window, an empty list
  claims the lease once for the auto step and calls no loader when nothing is added. The test was re-pinned:
  `test_NEGATIVE_an_empty_list_claims_no_lease_and_calls_no_loader`.
- `alerts` is still the cross engine's own counts over the frames it was GIVEN. `alerts.names` counts his names only
  (manual + auto only when the auto mode is "live"). `alerts.suppressed_auto` is the held count, present only when auto
  names were read; an iteration with his names alone keeps `alerts` byte-identical. `n_names` = manual + auto, and
  `auto.n` = the auto count. The state doc `latest` gains
  `auto: {n, cap, added, removed, leaving, skipped, reason}`.
- `--dry-run --symbols` (the stub) skips the auto step. `--dry-run` without `--symbols` runs `auto.step(dry=True)`; its
  `auto.writes` shows the would-be doc and nothing is written. This is the container probe.
- A raising auto step is logged. The last stored entries stay served and the iteration completes.

## Cost (measured 11-17, read-only probes)

- Massive: the watch child grew from 12 to at most 30 minute-fetches per minute at the cap. At about 0.18 s of wall
  time per name with 8 workers (M1: 12 names, 2.169 s), 30 names take about 5.4 s of the 35 s budget. The 1-min page's
  own ≤ 60 is unchanged, so the two detached children together make **≤ 90 Massive minute calls/min on ONE key**. A 429
  earned by the watch's extra 18 is a 429 for GG1's page too: the quota is per key, the breaker per process.
- The selection itself costs zero fetches. It does 2 projected read finds, 1 scan find, 1 tracker find and one
  `find_one` per auto name per board, all on stored docs.
- Payload (M2): a 12-name board is ≈ 2.37 MB raw / 593 KB gzip per GET. At 18 auto names that adds ≈ +0.9 MB gzip per
  60-s GET (≈ 1.5 MB gzip total), about 90 MB/h on his phone in window (HIS CALL #1).

## Today's surface (probes 10:36 and ~11:00 ET, 2026-11-17)

- M3: potentials served at 10:36 — GG5 1 (VTSI 💋 building, scan-row volume none), GG1 1 (LGHL ➖ building, volume none).
  Listed 102; GG5 reads 101, GG1 reads 72.
- M4: breakout states on broke reads at 10:36 — GG5 10 ✖️ · 1 ⏸ · 1 🔇 · 4 none; GG1 12 ✖️ · 4 ⏸ · 1 ↩️ · 2 off_chart ·
  1 🔇. On the 11-12 session, 42 broke cards read 27 ✖️ · 10 ⏸ · 4 ↩️ · 1 🔊. That is why ⏸ must keep the name [C1].
- M5: GG5 ≈ 43 🧠 rings/day, GG1 ≈ 45/day (10-28). A cap of 18 binds rarely.
- M7: tracker `state_path` flips by 11:00 — GG5 36 forming-exits over 28 trackers, GG1 60 over 28 (AIMD: 11 states).
  Those flips are why "dropped" waits for the grace [C3].
- Pre-deploy dry run against the live stored boards (spec §5.3, run by the verification step in a throwaway container,
  never the running one): not run by this package. Record the would-be adds and removals here when it runs.

## Critique tags answered

C1 ⏸ keeps · C2 scan → tracker → unknown · C3 drop grace + all removals stored · C4 frozen add order · C5 the listed
filter only when non-empty · C6 `alerts` = the engine's own counts, documented + pinned · C7 dismiss resets a stale doc
· C8 a non-ticker answers `absent` without reading the auto doc · C9 (FE fixture: 18 auto rows).

## HIS CALL (nothing below decided here — defaults built as stated)

1. **Cap** `AUTO_MAX_SYMBOLS = GC.GG_WATCH_N` (18) — MINE to reuse. Alternative `MAX_SYMBOLS` (12). Cost at 18: ≤ 30
   fetches/min on the ONE Massive key, ≈ +0.9 MB gz per minute GET (≈ 1.5 MB gz total ≈ 90 MB/h on his phone in
   window), up to 30 tiles.
2. **"Good volume"** = today's volume as K11 reads it (the scan row, else GG5's stored pass number) ≥
   `K11_MIN_SESSION_VOLUME` (1,000,000, GG's floor). A multiple (2M, 5M) or relative volume (`ctx.rvol`, stored when
   the 50-day average is known) = his number.
3. **"Not progressing"** [C1] = every board reads ↩️ back_under / ✖️ stop_printed, or the name is a potential nowhere for
   the grace (#9). **⏸ waiting KEEPS** — the engine's ⏸ means "above the trigger, no new high since", i.e. the
   consolidation after GG's own entry signal. Removing on ⏸, or a "no new high for N bars" clock = his word (one tuple
   edit / a new number).
4. **Push**: auto names never ring the 1-min 9/21 cross (`AUTO_PUSH_MODE "off"`, held `suppressed_auto`); "live" = they
   ride the same engine, same floor, same claim.
5. **Session change**: the auto section clears (entries, removed, dismissed); carry-over of yesterday's auto names = his
   call.
6. **His × on a MANUAL name** also blocks an auto re-add that session — MINE.
7. **Order** [C4]: frozen add order (a batch added in one minute lands in `potential.order_key` order; nothing moves
   afterwards) — the manual board's rule. A minute re-sort by `order_key` (the 🧠 sub's behaviour) = his word.
8. **At the cap** a louder new potential never displaces an auto name — MINE. (*12:55: a LIVE name is still never displaced; the oldest LAPSED one makes room — below.*)
9. **Drop grace** [C3] (*SUPERSEDED 12:55 — nothing reads `AUTO_DROP_GRACE_SEC` for removal now*): a name that is a potential nowhere leaves after `AUTO_DROP_GRACE_SEC = GC.PASS_CADENCE_SEC` (300
   s, the GG5 pass clock) — MINE to reuse; a different number, or "out for the day once removed" = his call. Re-add after
   removal is allowed (every event recorded).
10. **➕ Watch on an auto name's card** promotes it to his list (manual cap applies); the card button still reads ➕ on an
    auto name (the list GET is his names only) — a "keep" label = his call.
11. **The 🧪 source** is tagged with GG5's ("🚩 5-min · 🧪") — one stored set (borrows), zero extra reads; the hint says so.
12. **Unknown** breakout state (1-min `off_chart`, a read fault) keeps the name — never removed on unknown — MINE.
13. **No time cap** on a potential that stays "building" for hours (no clock constant exists) — a cap = his number.
14. **Removed strip** serves the newest 18 removals of the session (every event stored), collapsed — MINE; clearing =
    session change.
15. **ℹ️ Rules clause** added (words only, from constants) — MINE.
16. **GG1 pass number** [C2]: GG1's tracker writes no `last.session_volume` (run_1m.py:371-376 passes none; potential.py:523
    "its bytes do not move"). Passing `session_volume=sv` there = one kwarg that moves GG1's tracker doc bytes
    (chart_maps/gajjala/, outside this build) — his call. Until then a GG1-only potential with no scan row and no GG5
    tracker today is refused and counted `volume_unknown`.
17. **Volume precedence** [C2]: the scan row first (the 🧠 board's own number), the tracker second (≤ 5 min old) — MINE;
    "tracker first when newer" = his call.

## Engineering choices made in the build (beyond the spec's words)

- When the write fails, or the compare-and-set loses `_CAS_TRIES` times, `step` answers `reason: "write_failed"` with
  the stored names. Nothing is lost; the next minute retries.
- The "dropped" state word comes from the entry's own setup's read state. When that is missing it is the first
  non-"none" read state in `GC.SETUPS` order, and "no setup" when the board has no read doc at all.
- `alerts.suppressed_auto` is written only when auto names were read, so an iteration with his names alone keeps
  `alerts` byte-identical to before.

## Tests

`backend/tests/test_gajjala_watch_auto_2026_11_17.py` (74 cases, NEGATIVES throughout). Re-pins:
`test_gajjala_watch_loop_2026_11_15.py` (the empty-list lease), `test_gajjala_watch_cross_2026_11_15.py`
(`HELD_REASONS ⊆ COUNT_KEYS ∪ {failed, no_target, suppressed_auto}`), `test_gajjala_watch_live_2026_11_16.py`
(`auto.py` joins the live-stack source guard).

## Accumulate (12:55 ET, 2026-11-17)

Ajay, ~12:50 ET, verbatim: "Why is NCPL not on the app and please keep adding more to watch list as they come in to
Potentials intraday".

**Why the list held 1** (live store, 12:51 ET, read-only): 47 names had a 🧠 tracker doc today (GG5 + GG1), 21 of them
with scan volume ≥ 1M. The engine added a name only at the minute it was a CURRENT 🧠 potential, so every potential
before the 11:56 ET deploy was missed; and the [C3] "dropped" rule removed a name 5 minutes after its potential lapsed —
nearly every potential lapses within minutes.

**What changed** (`auto.py`, `payload.py`; `constants.py` comment only):

- **Add source** = every name with a 🧠 tracker doc of TODAY's session in the GG5 or GG1 store (`ST.POTENTIALS` — ONE
  projected find per store per step, `date` = the session and the `_id` prefix "<iso>|"; GG5's find also feeds the
  [C2] tracker volume) UNION the current potentials (unchanged). A tracker-only name: setup = its doc with the earliest
  `first_seen`, kind = that doc's `first_kind`, sources = the stores it appears in (+ 🧪 when GG5 is present).
- **One order per step** (*SUPERSEDED by Amendment A below*): the earliest tracker doc's `first_seen` ascending (ties: symbol). A current potential with no
  tracker doc yet sorts last, by `potential.order_key`. A current potential keeps its live words (setup, kind, volume).
- **Unchanged gates**: the listed filter (non-empty listed set only), `AUTO_MIN_VOLUME`, unknown volume refused
  (`volume_unknown`), his names, his ×, names already on the list.
- **A lapsed name STAYS** all session, stamped `dropped_since` (cleared when it is a potential / progressing again),
  served "potential lapsed HH:MM ET — first out when a new one comes in". `AUTO_DROP_GRACE_SEC` is kept for the old
  docs / tests; nothing reads it for removal. `AUTO_DROPPED_TEXT` is kept for docs written before 12:55.
- **↩️ back under / ✖️ stop printed** still remove at once with the card's line; his × unchanged.
- **At the cap** (`AUTO_MAX_SYMBOLS`, unchanged; *Amendment A: only a CURRENT potential evicts*): each arrival that does not fit removes the OLDEST-ADDED name that
  lapsed THIS step — new reason `made_room` (appended to `REASONS`), text "made room for NEW — potential lapsed HH:MM
  ET". A potential, a broke-kept (⏸ / 🔊 / 🔇 / ⤴️) or an unknown name is never evicted. None lapsed → the arrival is
  skipped and counted `full` (appended to `SKIPPED_KEYS`).
- **Faults**: a tracker read fault in either store → no tracker adds and no "made room" that step (current-potential adds
  into free room still land); nothing is ever wiped.
- **Words** (*order words moved by Amendment A*): the hint and the ℹ️ rules clause say names that came into a 🧠 potential at any time today are added
  (oldest first), stay all session, leave on ↩️ / ✖️ or ×, and at the cap the oldest lapsed one makes room. No
  "minutes" clause.

**Executor's judgement (flag for HIS CALL)**: a tracker-only name removed earlier THIS session (any reason — made room,
↩️ / ✖️, ➕ moved to his list) is NOT re-added from its tracker doc alone; it comes back only as a CURRENT 🧠 potential
(the pre-12:55 rule). Without this, a name made room for would return the next minute and evict another lapsed name —
the list would churn every minute; a ✖️ name would be re-added and removed on alternate minutes.

**Not done** (*the pre-check is DONE by Amendment A4 below*): no pre-check of ↩️ / ✖️ before a tracker-only add — a backlog name that already failed its breakout is
added and leaves at the next minute with the card's line (one event each, never re-added). No FE change (served words
flow through). UNMEASURED — display / selection only; no push, no fetch, no claim.

Tests: `backend/tests/test_gajjala_watch_auto_2026_11_17.py` (`test_ACC_*`, plus the [C3] / rules-line / skipped pins
moved with dated comments) and `backend/tests/test_gajjala_watch_auto_served_2026_11_17.py` (hint pin moved, the lapsed
word, `made_room` and old `dropped` removals render).

### Amendment A (2026-11-17, main session — supersedes the one order rule above)

His words "as they come in": a CURRENT potential always goes first; the morning backlog only fills free seats.

- **Order** (`auto.arrivals`): each step's arrivals are (i) the CURRENT 🧠 potentials not on the list, in
  `potential.order_key` order, THEN (ii) the tracker-only names (came in earlier today, not a potential now),
  `first_seen` DESCENDING — newest first (ties: symbol; a doc without a `first_seen` last).
- **Eviction** (`made_room`, the oldest-added lapsed name) happens ONLY to seat a CURRENT potential. A tracker-only name
  takes a FREE seat or is skipped and counted `full` — it never evicts, so the list does not churn minute to minute.
  Cap full of live / kept names and a current potential arrives → `full` (unchanged). A tracker read fault still blocks
  every eviction that step.
- **Lapse stamp**: a tracker-only name lands with `dropped_since` = the NEWEST `last.at` across its tracker docs (both
  stores, every setup) — the served "potential lapsed HH:MM ET" is the real lapse time. A missing / bad stamp → now.
  *Executor's judgement*: when `progress` reads the name KEEP (a broke read still ⏸ waiting above its trigger) it lands
  with no stamp — the step's own rule ("cleared when progressing") applied at the add, so it never reads "lapsed".
- **Failed backlog** (`progress` before every tracker-only add): ↩️ back under / ✖️ stop printed → not added, counted in
  the new `SKIPPED_KEYS` entry `failed` (appended after `full`). `progress` runs only when a seat is free — a full list
  reads no backlog name. A name removed earlier this session is still not re-added from its tracker doc (a current
  potential again still is).
- **Words**: the hint and the ℹ️ rules clause now say "a current potential first, then today's earlier ones newest first
  into free seats only (one already ↩️ / ✖️ is not added)" and "the oldest name whose potential lapsed makes room for a
  current potential". `AUTO_LEAVING_TEXT` unchanged.

Tests (`test_AMD_*` in `backend/tests/test_gajjala_watch_auto_2026_11_17.py`): the probe_churn scenario (40 lapsed
backlog + 1 live, cap 18 → live first, 17 newest backlog names; minutes 1–3 nothing evicted / re-added; a 2nd live
potential evicts the oldest-added lapsed name, which stays out), a tracker-only name never evicts, `dropped_since` =
newest `last.at` (bad → now), a KEEP read lands unstamped, a ↩️ / ✖️ backlog name counted `failed`, a full list reads
no backlog progress. Pins moved with dated comments: the add-order test, the first tracker-only test (stamp), the
skipped-dict and `SKIPPED_KEYS` pins, the hint and rules-line words.

## A+ seats (17:20 ET, 2026-11-17)

Ajay, verbatim: "Push new Apluses immediately in to watch list and an alert for me please Missed AKAN and GP". Then: "Is
AZI A+" — **No**: 🚩 5-min 🎾 `partial` (K3 volume not dried), 🚩 1-min 🎾 `partial`, 💋 `partial`; the 🧪 K3S admit
was judged on its break pass and failed (`{admit: K3S, aplus: False}` → held). AZI is on his own list, so the 🎯 chip
appears on his row the moment it becomes A+; it is never an auto entry while it is his. Spec ggwaplus2, WP-1.

- **Which names.** Every name with a setup in `tab.MARKED_STATES` (A+, A+ triggered, A+ then stopped) on any of the three
  Gajjala boards THIS session, by THE 🎯 tag's classifier — `payload.aplus_by_symbol` (factored out of `aplus_section`,
  byte-identical) over the step's OWN read docs plus the 🧪 board's `audited_tab.overlay_reads`. `auto.aplus_sets` →
  `{FOLD: (SYM, the tag's first item, the tag's source list)}`. The read projection gained `updated_at` (the 🧪
  freshness check). 🥇 Luk is never a source. No listed-set filter (the tag has none — HIS CALL #7).
- **When.** At the next loop minute, inside the 04:00–20:00 ET pass window only (out of the window: no add, no promote,
  no refresh). "Immediately" = ≤ 60 s after the A+ read lands, never the same second.
- **Seat order (`AUTO_APLUS_EVICTS`, HIS CALL #1).** A+ arrivals go FIRST, earliest A+ clock first. A free seat; else the
  oldest-added name whose potential lapsed THIS step; else the oldest-added 🧠 potential — never another A+, never his
  name (reason `made_room_aplus`, words `AUTO_MADE_ROOM_APLUS_[LAPSED_]TEXT`). Every seat an A+ → the name is listed in
  the step's `aplus_skipped` (loop state doc `auto.aplus_skipped`, served as the board's `skipped_text` — the LAST step,
  never history). A tracker read fault → nothing evicted (the made-room guard). A potential arrival at the cap never
  evicts an A+ seat.
- **Stays (`AUTO_APLUS_STAYS`, HIS CALL #2).** An A+ seat is never `progress()`-read: ↩️ back under / ✖️ stop printed never
  remove it, it never lapses; only his × (blocks the day) or his ➕ ("on your list") take it off. With the switch False
  it is judged like a potential and, once removed, is not re-seated the same day (executor's judgement — without it the
  switch would remove and re-add every minute).
- **Words move, positions do not.** Every in-window step an A+ entry's `aplus` / `sources` / `setup` follow the live read
  (AKAN: "A+ 10:21" → "A+ (triggered) 16:44"); its seat clock never moves. A step where the name is in NO marked state
  (the day's one read per name was overwritten — CRDF) keeps the LAST block and the seat: the Watch's last sighting,
  while the live 🎯 chip is gone (HIS CALL #21).
- **Promote.** A 🧠 potential entry that becomes A+ is promoted in place: `why "aplus"`, `promoted True`, `kind None`,
  `dropped_since None`, `aplus_at` = the step; its row reads "… · seated HH:MM ET as a potential".
- **Comes back.** A name removed earlier today (↩️ / ✖️ / made room) returns as A+ — the existing board-arrival rule
  (`out_today` blocks tracker-only arrivals only); no READD switch. His × still blocks for the day.
- **Volume.** No floor: K11 (the same number as `AUTO_MIN_VOLUME`) is judged on every A+ on all three boards. The words
  come from `volume_of` (scan row, else GG5's tracker); neither → no volume words, still seated. **No numeric K11 field is
  stored on a read** (`ctx.session_volume` does not exist; the number lives only in a criterion LABEL, never parsed).
  `AUTO_VOLUME_SOURCES` unchanged.
- **The 🧪 window (K3S).** A 🧪-only A+ (the K3S admit) is visible to the ONE classifier only while the 🚩 read is on its
  break pass (`bars_since_entry == 0`) and the overlay is at least as fresh as the read (`updated_at`, fail-closed when
  missing) — ≤ one 5-min pass. A lease miss / host sleep inside that window loses it for the day, exactly as on the 🎯
  tag. Once seated it STAYS with its last block. Widening = HIS CALL #18.
- **Unaudited passes through as 🧪.** A 🚩 5-min A+ with no overlay doc carries `sources ["gajjala","gga"]` — the 🧪 board
  lists that row (audit cell "unaudited"); the Watch mirrors the tag mirrors the board (a filter = HIS CALL #19).
- **Faults.** A read fault on either board, a missing 🧪 store / overlay handle, or a raising classifier → `aplus_sets`
  None (unknown, never "none"): no A+ add, no promote, no refresh; A+ entries kept; potentials unaffected. An overlay
  FIND fault is swallowed by `store.overlays` (→ "no overlay") and cannot be told apart: 🚩 A+ names still seat (passing
  through as 🧪).
- **Served.** Row `auto.why` ("aplus" / "potential"); an A+ row's kind slot = the A+ word of its state, `added_text` =
  "🎯 A+ {at_et} ET ({source} {setup}) · seated {added_et} ET" (+ " as a potential" when promoted; HIS CALL #20),
  `leaving_text` null, remove title "auto A+". Board `auto.skipped_text`. The hint and the ℹ️ clause carry one sentence.
  Potential entries never gain a key; with no marked read the doc written is byte-identical.

Tests: `backend/tests/test_gajjala_watch_auto_aplus_2026_11_17.py`, the served key-set pins in
`test_gajjala_watch_auto_served_2026_11_17.py` (dated), `frontend/src/lib/gajjalaWatch.test.ts`,
`frontend/src/components/GajjalaWatchBoard.aplusAuto.test.tsx`. UNMEASURED — display / selection only.

## Addendum 2026-11-19 — 🚫 his broker list

2026-11-19 — on 👀 Watch only, by his word, the 🤖 auto section never seats a name on his 🚫 list
(`gajjala.store.broker_flags`): no new 🧠 or 🎯 seat, a flagged potential is never promoted in place, a seated 🧠 potential
on the list leaves at the next minute (reason `not_eligible`), a 🎯 A+ seat stays until his × (HIS CALL #3). The hover hint
gains `auto.broker_words()` before its final "UNMEASURED."; the board's `broker` block serves the names kept off. Every
other surface still tags — see docs/gajjala/watch_not_in_fidelity_2026_11_19.md.
