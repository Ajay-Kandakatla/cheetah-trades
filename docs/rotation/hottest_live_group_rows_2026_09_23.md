# 🔥 Hottest — the sector rows go live with the names (2026-09-23)

> "I think the sector rotation is wrong..
>
> Can you show me till or current market instead of last close. Its actualy
> rotating this morning I wanna see live rotattion"
>
> — Ajay, 2026-09-23, screenshot of the Energy (curated) row reading
> **−1.7% `last close`** while the names under it were live

## He was right, and the board was arguing with itself

Since 2026-09-16 the **name** rows on this board have been live: each name's own
move so far in the session, minus RSP's own live move, out of one fan-out. The
**group** rows — every sector, industry and curated roster — stayed on the
rotation snapshot's last close, deliberately, with `D1_GROUP_BASIS = "close"`.

The reason was real: *a median over live values for the names that priced and
last-close values for the rest describes no session at all.* That is still true.
What it missed is that a board headed "rotation" whose rotation rows are a day
behind the names under them is not describing this session either.

### Measured on the live board, 2026-09-23 10:44 ET

`GET /rotation/hottest` served `d1.live: true`, `live_names: 1751` of
`symbols: 1753`, benchmark RSP at **−0.35%** live — and `group_basis: "close"`,
`close_as_of: 2026-09-22`.

Taking each roster's own members' live `rel_1d` and medianing them:

| roster | served (close) | its members, live | n live / n |
|---|---|---|---|
| `semi_materials` | **+3.94** | **−1.53** | 12 / 12 |
| `critical_minerals` | **+2.99** | **−2.99** | 19 / 19 |
| `ai_semis` | **+2.55** | **−1.29** | 22 / 22 |
| `ai_infra` | +1.78 | −0.07 | 20 / 20 |
| `rare_earth` | +1.63 | −3.71 | 4 / 4 |
| `ai_power` | +1.34 | −0.28 | 20 / 20 |
| `space` | +1.11 | −1.65 | 11 / 12 |
| `nuclear` | +0.97 | −1.25 | 18 / 18 |
| `robotics` | +0.92 | −0.89 | 19 / 19 |
| `crypto` | +0.35 | −1.61 | 14 / 14 |

**19 of the 29 group rows carried the opposite SIGN to their own members'
live median.** He was ranking a rotation that had already turned.

## What changed

`rotation/hottest.py`

* `_close_d1` is unchanged and is still the whole story when the board is not
  live, or when a row has no live member.
* **`_live_d1(legs, rows)`** is new: `rel_1d` becomes the median over the members
  of that row whose own day cell went live (`d1_source == "live"`). A member the
  fan-out missed is **left out**, never folded in at its last-close move.
* `_group_d1` picks between them on the board-wide `live_ok` flag, so the group
  rows and the names under them can never disagree about which session they show.
* `d1.group_basis` now reads `"live"` or `"close"`. It stays a **token** — the
  FE's `HsD1Source` union switches on it — and the sentence ships beside it as
  `d1.group_basis_note`.

### Four new keys on a group row

| key | what it is |
|---|---|
| `rel_1d` | the live median — what the Today column prints |
| `rel_1d_close` | **unchanged**: the close median this row has always served |
| `d1_live_n` / `d1_live_of` | how many members printed, out of how many the row has |
| `d1_live_close` | the close median over **those same members** |

### The trap: `rel_1d_close` and `rel_1d` are NOT a before/after pair

A **sector** row's close median is over the rotation grid's own **sample**
(`n_measured = 40` of `n_full = 308` for Technology). The live median is over the
full membership. Subtracting one from the other gives a number no set of names
produced. That is why `d1_live_close` exists: it is the close over the *same*
names, and it is the only close the tooltip quotes. A frontend contract fails the
build if `rel_1d_close` reaches the live sentence or if the two are differenced.

A **roster** row has no such gap — its close median is already over its full
membership — which is why the table above is a fair comparison and the sector
table is not.

### The other trap: the served `names` array is the top of the board

`names` is truncated to `names_per_group` (25) **after** the sort. Medianing over
it would be biased upward by construction — on Technology the top 25 of 308
median +3.06 on the close against the row's shipped +0.22. Every median here is
taken over the **full** member list inside `_build`, never over what is served.

## On the screen

* The Today cell on a group row prints the live median, unmarked.
* When the row went live on **fewer** members than it has, the cell prints
  `· n/of` beside the number — the same treatment the ☀️ Pre-mkt column already
  gives a partial cohort. Silent when every member printed, which is the normal
  case in session.
* A group row with **no** live member falls back to the close whole and still
  carries the words *last close*, dimmed, exactly as before.
* The tooltip names the cohort, its size, the benchmark, and what those same
  names closed at.
* The as-of line, the ↻ Re-scan tooltip and the ℹ️ panel all stop saying the
  group rows are from the close — that claim was true when written and is not now.

## What did NOT change

5 days, 21 days, Sales YoY, `pct_positive_1d`, `n_measured`, `n_full`, `thin`,
`basis` and the ☀️ pre-market leg are all untouched and still the snapshot's.
No gate, no threshold, no cohort rule and no filter moved. Nothing here is
measured or predictive — it is a return between two prints.

## Bug found on the way

The live overlay in `_build` wrote `round(mv, 2)` straight onto the row. That
runs **after** `_names`' own NaN scrub, so a NaN arriving by any road other than
`_live_move` (which already drops one) would land on the row unscrubbed — and a
NaN passes every `<=` comparison, so it reorders the board silently long before
the JSON scrub sees it. Now `_num(live_moves.get(s))`.

## Tests

* `backend/tests/test_hottest_live_groups_2026_09_23.py` — 18, including the
  negatives: a dark member is excluded not folded in; an all-dark row falls back
  whole; a close board carries no live keys at all; the median ignores the
  truncated `names` array; `group_basis` is never prose; no NaN reaches the
  payload. Five mutations of the source were run against them and all five fail.
* `frontend/src/components/HottestSectors.livegroups.test.tsx` — 16, including
  the negatives: a whole cohort prints no denominator, missing counts are not
  partial, a name row is never partial, the tooltip never quotes `rel_1d_close`,
  and a closed board's as-of line is byte-identical to what it always said.
* `frontend/scripts/contracts.mjs` — contract #92, mutation-tested five ways.
* Two existing pins were **reversed on purpose** and say so in place: the
  re-scan tooltip test (the group rows DO move now) and the pre-market
  `asOfLine` byte-pin.

## Open — his call

1. **Should the group rows re-rank live too?** They do: `rel_1d` is a sortable
   column and the board sorts on the served value, so with the day column
   selected the sector order now moves intraday. The board's default sort is
   still `rel_5d`, which does not move.
2. **A partial cohort has no floor.** A roster where 2 of 19 members printed
   still serves a median over those 2, marked `2/19`. The ☀️ pre-market leg
   dims a thin cohort at `THIN_N = 8`; the day leg does not. Whether an
   in-session row should be dimmed the same way is a rule, not a view.
