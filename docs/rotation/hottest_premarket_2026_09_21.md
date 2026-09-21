# 🔥 Hottest — ☀️ Pre-market scan (2026-09-21)

Ajay, 2026-09-21: *"In the hot sector table can I get a pre market scan please"*

He reads these boards at 7–8 am ET. Until this shipped, every column on the
🔥 Hottest tab before 09:30 was the previous close, and the ↻ Re-scan button
answered honestly that it could not help: the day bar is zero before the open,
so `_live_move` refuses to serve a same-day move, and there was nothing else to
show him.

**Nothing here is measured.** No study says a pre-market move predicts anything,
on this board or any other. This is a read of the tape before the open, and the
block, the tooltip, the InfoButton and the ✨ entry all say so.

---

## 1. What it is

A **third basis**, `D1_PREMARKET = "premarket"`, served as a **sibling block**
`pre` (`PRE_KEY`) beside `d1`. `GET /rotation/hottest?basis=premarket` adds:

* per name — `pre_raw` (its own print against its previous close), `pre_1d`
  (`pre_raw` minus RSP's own pre-market move), `pre_print`, `pre_at`,
  `pre_at_et`;
* per sector / industry / theme row — `pre_1d` (the median over the members
  that **printed**), `pre_n`, `pre_thin`, `pre_basis`;
* one extra sortable column, `pre_1d` (`PRE_SORT`), placed first among the leg
  columns and shown only while the served `pre.show` is true.

### The day column does not move

`d1` and every row's day-leg key (`rel_1d`, `rel_1d_close`, `ret_1d`,
`ret_1d_close`, `d1_source`) are **byte-identical** whether or not the
pre-market basis was requested — pinned by
`test_the_day_column_is_byte_identical_with_and_without_the_pre_leg` on both a
live and a close day leg.

That is the whole reason this is a second block and not a mutation of the first.
`hottest.py` has said since 2026-09-16 that *a raw move dropped into a relative
column is a different measurement wearing the same header*. A pre-market print
is a different measurement, so it gets a different column, a different header
and a different yardstick — never a relabelled `Today`.

## 2. The yardstick, and why its print time is on the board

`rel_1d` has always been **relative**: the name's move minus RSP's own move. The
pre-market column keeps that, so it measures each name's pre-market print
against **RSP's own pre-market print**.

RSP is an ETF and prints far less often than a name. Probe, 2026-09-21 07:27 ET
(read-only, the live api container):

| symbol | last print | `prev_day_close` |
|---|---|---|
| RSP | **05:00 ET** | 212.29 (Friday 2026-09-18's close) |
| NVDA | **07:27:01 ET** | 222.27 |

So the snapshot is one read, but the **prints inside it are not simultaneous**.
The block therefore serves `benchmark_pre_at` / `benchmark_pre_at_et` /
`benchmark_pre_print`, the as-of line prints them, and the note never claims the
two prints came from the same moment — only that they came from one snapshot.

**No staleness cut is applied to RSP's print.** A cut would be a gate on what he
sees; the existing constant (`zone_edge.STALE_PRINT_SEC = 180`) is not borrowed
here. Whether to add one is his call (§7).

**Without RSP's print, nothing relative is served at all.** The block says
`no pre-market print for RSP yet, so nothing can be measured against it`, every
row's `pre_1d` is `None`, every group's `pre_n` is `0`, and the board ranks on
the default leg (§5).

## 3. Group rows: the printed subset, with the count

Expect most names to have no pre-market print at 07:00 — pre-market passes on
`zone_edge` see roughly 80% `stale_print`. That is the truth to print, not a
bug.

So a group row's `pre_1d` is the median over **the members that printed**, and
the row carries `pre_n` beside `n_full` so the board can print `+0.80% · 12/40`.
`PRE_GROUP_BASIS` states it in the payload: *"median of the members that printed
pre-market — not the full membership"*.

`pre_thin = pre_n < THIN_N` — the board's **own** thin rule (`THIN_N = 8`),
reused by name, never retyped. It is a **second** flag: the existing `thin`
means `n_full < THIN_N` (membership) and is never overwritten. Both ride on the
same row and mean different things; pinned by
`test_the_membership_thin_flag_is_untouched_on_industry_and_theme_rows`.

`D1_GROUP_BASIS` did not move. The day leg on a group row is still the close.

## 4. What counts as a pre-market print

`_pre_print(snap, today)` returns `None` unless all of:

1. `prices.extended_print(snap)` yields a print — the ONE extractor, which
   already handles Massive's ns **and** ms stamps;
2. its session is `premarket` — 04:00 ≤ t < 09:30, `prices.trade_session`;
3. its ET **date is today** — on Monday morning the snapshot still carries
   Friday's 17:30 after-hours print, and Friday's 07:00 pre-market print has the
   right session and the wrong day;
4. `prev_day_close` is present and positive.

Boundaries pinned on both sides: 03:59 no, 04:00 yes, 09:29 yes, 09:30 no,
09:31 no. A missing print is `None` — **never** `0.0`.

## 5. The sort demotion

`pre_1d` joins `SORT_KEYS`, so it is rankable like every other printed column.
But the column is often empty, and ranking on an empty column is a total tie
dressed up as a ranking.

So `_build` computes `pre_ok` (live **and** a benchmark move **and** at least
one name's move — the same all-or-nothing rule the day leg gets) **before** the
sorter is built, and:

```
if sort_key == PRE_SORT and not pre_ok:
    sort_key = DEFAULT_SORT
_by = _sorter(sort_key, sort_dir)
```

`sorted_by` therefore tells the truth: `?sort=pre_1d` on a board that cannot
rank on it comes back `sorted_by: "rel_5d"`, ranked on `rel_5d`. This applies to
every path — RSP unprinted, nobody printed, the session ended, the scan was
never requested, `basis=close`, and the pure build. No other sort key is ever
touched.

The `_by` line moved **below** the `pre_ok` computation for this. Building it
earlier would rank the board on nothing while `sorted_by` still claimed the
column.

## 6. The cost: 7 chunks, not 14

The measured re-scan cost (2026-09-18) is 7 board chunks (1,711 names / 250).
A ☀️ scan must not raise it, or the button's own promise ("the same provider
read as reloading the page") stops being true.

`build_live(basis="premarket")` wraps ONE `_memo_fetch()` around the fetcher and
runs the **pre leg first**; both legs ask for the identical
`sorted(set(syms) | {bench})` list, so the second call is free. Pinned by
`test_both_legs_share_exactly_one_fan_out` (and its negative: a different list
is not a memo hit).

On a closed calendar day or outside 04:00–09:30 ET the pre leg spends **zero**
provider calls — it returns after three clock reads.

## 7. The stored read

`PRE_COLL = "hottest_premarket"`, one doc per ET date, `_id = "YYYY-MM-DD"`.
A stored read no older than `PRE_STORED_FRESH_SEC` (15 min — an **app label**,
not a measured number) is served without any fan-out.

Stored doc shape = the block, plus `_id` and `stored_at`. **Three keys are
never served**: `PRE_PRIVATE_KEYS = ("moves", "_id", "stored_at")` —
`moves` for the same reason `d1`'s is not (one entry per priced name, and every
row already carries its own), `_id`/`stored_at` because Mongo bookkeeping has no
business on a board. They are stripped in the ONE place the block is serialised
(`_build`), so every path is covered; pinned across the fresh, stored, ended,
idle and pure paths.

`store_premarket` **refuses** a block that is not `live` — a stored "nobody has
printed yet" would be served back for fifteen minutes as though it were an
answer.

### Stored docs are re-clocked on every serve

A doc written at 07:20 was stored with `open: True` and `session: "premarket"`.
Served unchanged at 10:05 it would re-enable the ☀️ button in the middle of the
regular session. So every stored path goes through `_served(doc, base, …)`, and
the **current** clock's `open` / `session` / `market_closed` / `pre_window`
always win over the stored ones.

After 09:30 with a stored read: `ended: True`, `live: False`, `open: False`,
`session: "rth"`, and the line reads
*"the pre-market session ended at 9:30 ET — last read 7:20 ET"*. Because
`live` is False, `pre_ok` is False, so rows carry `pre_1d: None` — the column
shows em-dashes under the ended line rather than numbers that have stopped
being true. `show` drops to False as soon as the day column goes live, so the
board never carries two "now" columns.

## 8. One clock, one format

**One instant.** `_idle_pre(now)` hands the SAME `now` to `_closed_reason(now)`,
`_session_state(now)` and `_today_et(now)`. `_closed_reason` grew an optional
`now` (passed straight through to `gate.closed_reason`, which has always
accepted one); every existing caller passes nothing and behaves identically.
Before this, an injected instant produced a block whose calendar came from the
real clock and whose session came from the test's — a block describing no moment
that ever existed.

**One format.** `_hhmm(t)` renders `"%d:%02d ET"` — the house format
`_session_window` has always used. Every served clock string goes through it:
`"4:00-9:30 ET"`, `"ended at 9:30 ET"`, `"7:42 ET"`, `"5:00 ET"`. Never
`"09:30 ET"`. Pinned by a negative sweep: no served string matches
`\b0\d:\d\d ET`. The frontend never composes a clock string — it prints the
server's.

**One zone.** `_et_zone()` is `supply_demand.zone_edge.ET`, a real `ZoneInfo`.
`market_hours.reminder` and `gate` carry fixed −5 h / −4 h offsets for their own
cron purposes; a date printed on a board has to come off the real zone or it
slips an hour across a DST boundary.

## 9. The endpoint

`GET /rotation/hottest?basis=close|premarket`. Coerced through `_coerce_str`
(the FastAPI `Query`-object trap that shipped twice on the demand board), and
anything that is not one of the two falls back to `close` — **never a 4xx on a
board**.

## 10. The CLI and the proposed cron

```
python -m rotation.hottest premarket   # scan + store, one summary line
python -m rotation.hottest show        # today's stored doc
```

`premarket` reads the persisted `scan_context` rotation doc and **never**
rebuilds — `tracker.build` is a multi-minute full refetch whose cache is
in-process, so a cron-container rebuild burns the provider quota to warm a cache
the API server never sees.

Proposed, wrapped by the closed-day gate:

```
*/10 4-9 * * 1-5 /usr/local/bin/python -m market_hours.gate rotation.hottest premarket
```

**The crontab is host-mounted — a deploy does NOT ship these lines; they are
added in-container by hand.** The cadence is his call.

## 11. What is NOT measured

Everything. There is no prior study of pre-market moves as a signal on this
board — the prior is null, not weak. The 2026-09-09 sector-heat study measured
heat as a non-predictor of demand outcomes (−0.57pp, CI spans zero); the
rotation backtest read top-3 rotation at 158.22% against RSP's 155.42% — no
edge. This scan gates nothing, alerts nothing, pushes nothing and enters
nothing. No S&D rule, gate, threshold or default was touched.

## 12. HIS CALL

1. **RSP has not printed yet** — show RAW pre-market moves labelled "raw, not vs
   RSP"? Built: nothing relative is served, the line says why, the board ranks
   on 5 days.
2. **The 15-minute stored-read label** (`PRE_STORED_FRESH_SEC`).
3. **The cron cadence** (and the host-mounted crontab edit).
4. **A staleness cut on RSP's print** — the time is shown, no cut is applied.
5. **What shows after 09:30** — built: em-dashes under the ended line, not the
   last numbers.
6. **Whether thin pre-market groups rank below full ones** — built: flagged
   (`pre_thin`), never demoted. A ranking rule is his.
7. **A pre-market push** — none exists and none was added.
8. **Whether the Hot-sectors strip gets the column too.**

## 13. Tests

`backend/tests/test_hottest_premarket_2026_09_21.py` — 68 cases, negatives
throughout: Friday's after-hours print and Friday's pre-market print both
refused, every window boundary on both sides, an unusable previous close, RSP
unprinted, no name printed, a raising fetcher, zero symbols, the `pre_thin`
boundary at `THIN_N` and `THIN_N − 1`, a stale / yesterday's / not-live stored
doc, `store_premarket` refusing a dead block, the zero-call paths at 01:00,
17:00 and on a Saturday, the one-fan-out pin and its memo-miss negative, the
day-column byte-identity on both day bases, blanks last in both sort
directions, the demotion on every pre-less path and the "no other key is
demoted" negative, the private-key sweep on all five paths, and the zero-padded
clock sweep.

Unchanged and green: `test_hot_sectors_rescan_2026_09_18.py` (including
`test_the_fan_out_still_fires_outside_rth`), `test_hot_sectors_live_today_2026_09_16.py`,
`test_rotation_hottest.py` (`test_every_printed_column_is_sortable` is a subset
check, so adding `pre_1d` does not break it).
