# ✨ `board_arrival` — one push the first time a name lands on a board

**2026-09-20.** Ajay, verbatim:

> "Default on for any change of todays features Bondes or Potus or explosive
> growth or Earnings I wanna see all of them."

Module: `backend/sepa/board_arrival.py`. Tests: `backend/tests/test_board_arrival.py`.
Kind: `board_arrival` (ON by default, in `push.subs.OWNER_KEEP_SET`).
State: Mongo `board_arrival_state`.

---

## What fires

| Board | Source | The row that rings |
|---|---|---|
| 📈 Bonde | `sepa/bonde.py` → `board()["sections"]` | `is_new is True` **and** a `first_seen` stamp, walked `pivot → explosive → strong → steady` |
| 🚀 Explosive Growth | `growth/tracker.py` → `board()["rows"]` + `newly_found()` | symbol in `newly_found()`, `first_seen` read from the `growth_seen` ledger via `sepa.first_seen.first_seen_map` |

A name placed twice on Bonde (a pivot that is also `explosive`) rings once,
under its **first** placement. Served order is kept on both boards — the push
order and the digest body order are the board's own reading order.

This kind **screens nothing**. It does not re-rank, re-score, or apply a room
or proximity gate. Whatever the board placed, it rings. The gates on the S/D
kinds are about which *levels* reach his phone; an arrival is not a level.

## What never fires

1. **The first cohort.** The pass keeps its own `__meta__.tracking_since` in
   `board_arrival_state`, stamped on the first run with that run's clock **in
   UTC**, and selects on a strict `first_seen > tracking_since`. **The first
   pass records the baseline and sends nothing.** Same rule, same reason as
   `sepa/first_seen.py`: "we have only just started watching" must never read
   as "these are fresh finds". First-run backfill of everything since the
   ledgers began (bonde 2026-09-14, growth 2026-09-12) is the alternative —
   his call, spec §7.2.

   **Why UTC, and why it matters (fixed 2026-09-20).** Both ledgers stamp
   `datetime.now(timezone.utc).isoformat()` — `2026-09-21T21:40:00+00:00` for
   the 17:40 ET `sepa.bonde show`. `select()` compares those stamps against
   `tracking_since` as **strings**. A baseline stamped in ET reads
   `2026-09-21T17:42:00-04:00`, and `"21:40…" > "17:42…"` lexically — so the
   17:40 ledger stamp would sort *after* the 17:42 baseline and **the very
   first pass would push every name on the board**. The baseline is therefore
   written and compared in UTC (`_utc_iso`), and a `__meta__` doc found in any
   other offset is normalised to UTC on read. The human-facing `at` on a claim
   doc stays ET — nothing compares it. Pinned by
   `test_a_ledger_stamp_from_the_1740_run_is_not_after_the_1742_baseline`,
   `test_the_baseline_is_stamped_in_utc_not_the_et_wall_clock` and
   `test_a_baseline_stored_in_another_offset_is_compared_in_utc`.
2. **A name already rung.** One claim per `(board, symbol)` — `bonde|NVDA` —
   with **no day in the key and no TTL** on the collection.
3. **A returning name.** Because of (2), and because the ledgers' `first_seen`
   is `$setOnInsert` **forever**, a name that leaves a board for months and
   comes back is **silent**. That is deliberate: its `first_seen` is still the
   original arrival date, so a second push would claim an arrival that did not
   happen. Re-arming after N days is a data-shape change and his call
   (spec §7.11). The /notifications detail says this out loud.
4. **The 🔎 `rejected` section.** Those names are not on his screen — they are
   the cohort the character clause threw away — and a push would read as a
   pick.
5. **A Bonde arrival the per-section cap hid.** This pass rings only what
   the board **draws**, and `bonde.board()` stamps `is_new` after the cap.
   See *Known limit — the per-section cap* below; pinned by
   `test_an_arrival_the_section_cap_pushed_off_the_board_never_rings`.
6. **A closed day.** See below.
7. **A dropped push.** A closed-day drop (`push.sender` returning `skipped`)
   is **not terminal** for this kind and the claim is released. Every other
   kind's claim carries the day and expires with it; this one's is permanent,
   so keeping a dropped claim would mute the name forever on the strength of a
   push that never left the building.

## Slots, and why

```
42  17  * * 1-5   python -m market_hours.gate sepa.board_arrival bonde
 8   8  * * 1-5   python -m market_hours.gate sepa.board_arrival growth
```

`SLOTS_ET = {"bonde": "17:42", "growth": "08:08"}` lives in the module and is
what `alert_status` and `rules_info` quote — the crontab minutes are never
typed twice.

* **17:42 ET** — right after the 17:40 `sepa.bonde show` that stamps
  `first_seen`.
* **08:08 ET** — the 🚀 board rebuilds **Sunday 09:00**, a closed day, so its
  arrivals ring the next **trading** morning. The line runs every weekday and
  is a no-op when nothing arrived; a Monday holiday slides it to Tuesday by
  itself.

## Why it is a MARKET kind

Both boards are built from **closed bars**, so a weekend or holiday run would
be ringing yesterday's screen. `board_arrival` is therefore in
`market_hours.gate.MARKET_ALERT_KINDS`: the crontab wrapper exits before the
module is even imported, and `push.sender` drops the kind again on the device
path. The alternative — make it PERSONAL so growth arrivals ring on Sunday
right after the build — is his call (spec §7.1). The standing rule in
`gate.py:49` is "add a new *personal* kind here, never a market kind", so the
spec took the market side.

## What the push says about itself

Every body carries the board's own honest record, read from the serving module
rather than retyped:

* **Bonde** — `bonde.measured_verdict()["headline"]`, today
  *"MEASURED 2026-09-13 AND THIS BOARD'S OWN THESIS IS INVERTED"* (−3.11pp
  over 21 sessions against a date-matched placebo, 95% CI −5.28 to −1.16;
  the sales gate alone separated nothing).
* **Growth** — *"NOTHING HERE IS BACKTESTED: the 100/100 screen has never been
  measured forward."*

and both end on *"An arrival on his screen / on a list, not an entry — not a
recommendation."* The body also carries the ⛔ engine-refusal warnings verbatim
on the growth side, and on Bonde the pair mark when the YoY pair is not four
fiscal quarters apart (`growth claim withheld …`) or unverifiable (`pair
unverified — no period keys on file`).

Neither a title nor a body ever says "bounce" (pinned by a test).

## Known limit — the per-section cap (2026-09-20, measured on the live board)

`bonde.board()` records an arrival over every name **placed** in a section, but
sets `is_new` on the **capped** sections (`strong` 60 of 248, `steady` 40 of
582). An arrival into an over-capped tier therefore has no `is_new` row, so
neither the ✨ badge nor this push sees it. On the live board at the time of
writing that is **all three** current arrivals:

```
newly_found: CASH, EZPW, SEDG        n_new: 3
placed rows with is_new: 0           strong 60/248 · steady 40/582
```

This module reads what the board drew, by design (it never re-derives a board).
Whether an arrival that the cap hides should still ring is a board question,
not an alert question — raise it with the Bonde tab. **HIS CALL**
(2026-09-20): reading the pre-cap `arrived` set would ring names his
screen does not show, so nothing was widened here.

## Summary keys, and the one trap

```
kind · board · ran · date · first_pass · tracking_since · rows ·
since_tracking · fresh · individual · digest · claimed_elsewhere · dry_run
```

**Never** `skipped_room` / `skipped_proximity` / `skipped_direction` /
`skipped_knife` / `skipped_mood` / `skipped_floor`. `Alerts.tsx` sums those six
names over **every** recorded pass, so a counter here borrowing one of them
would silently move the S/D gate aggregate on a page he reads. Pinned by a test
that asserts the exact key set.

`alert_status.record_result("board_arrival:<board>", summary)` is written after
a **wet** pass only.

## Dry-running it

Read-only, in the api container (it needs Mongo, so it cannot run under the
repo venv):

```bash
docker exec -i -w /app cheetah-market-app-api-1 python -m sepa.board_arrival bonde --dry-run
docker exec -i -w /app cheetah-market-app-api-1 python -m sepa.board_arrival growth --dry-run
```

A dry run **reads** the state (a name already rung reports as seen, never as
fresh) and **stamps the baseline** — deliberately, so a later wet pass cannot
push the whole board — but claims nothing, sends nothing and records nothing.

Note that the **first** invocation, dry or wet, is the baseline pass: it will
report `first_pass: true`, `since_tracking: 0` and send nothing.
