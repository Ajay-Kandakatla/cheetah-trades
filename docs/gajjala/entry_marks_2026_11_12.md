# 🟢 Gajjala sub-tab entry marks + ✨ the 30-minute blinker — 2026-11-12

DISPLAY ONLY. PAPER only. No gate, threshold, push, order or count moved. UNMEASURED — nothing here claims an edge
(10-14 study null; 11-11 "A+ = coin flip"; 11-10 "A+ later = no different from a name we did not ring").

## The ask, verbatim

Ajay 2026-11-12 ~15:22 ET: "Can you show me green on these tabs some indicators to show be which ones have best potential
entries right now I am clicking through each one and figuring out... an Indicator or new tickers with in last 30 mins like
blinkers or something would be nice" — on a screenshot of the 🚩 sub strip ("🎾 Reversal Squeeze · 31 …") and
"🎯 No A+ right now · last pass 15:21 ET · UNMEASURED".

## What ships (backend)

- `backend/chart_maps/gajjala/entry_marks.py` (NEW) — the ONE engine. Read-only: no store, no I/O, no wall clock.
- `backend/chart_maps/gajjala/tab.py`:
  - `banner_clock(latest, now, *, in_window, cron, session, v)` + `read_of_pass(doc, at)` — the 🎯 banner's own
    "right now" (A10 / A11 / C6), extracted; `aplus_block` reads them (output byte-identical).
  - `is_entry_plan(read)` = `_is_entry_read` AND `ledger.plan_of == LG.PLANS[0]` (trigger above the stop); `plan_text`
    reads it (byte-identical). `_tile_lines` NOT changed (HIS CALL #10).
  - `carded` beside `n_tiles` (the chip's own names, pre-cut; `len(carded[s]) == n_tiles[s]`, tested).
  - `_entry_marks` (lazy import) and ONE `_soft("entry marks", …)` call after the sub chain, before 🔝 Focus.
- `backend/chart_maps/gajjala/constants.py`: `ENTRY_MARK_NEW_MIN = 30` (his number, tagged `# Ajay 2026-11-12`).

### Served payload

`entry_marks: {"subs": {<sub key>: {"green"?: {n, label, title}, "new"?: {n, until, title}}}}` — a sub key only when it
has a block; a missing block is ABSENT (never `n: 0`, never null). ☀️ 🌙 📓 🏁 never appear. Outside the banner's clock:
`{"subs": {}}`. Shown tiles: `new_mark: {kind, at_et, until, text, title}` (no mark → no key).

## Definitions

| mark | rule |
|---|---|
| 🟢 setup sub | carded names (pre-cut) whose read is `aplus` or forming-ready AND `is_entry_plan` (`GREEN_STATES = ("aplus", "ready")`); `triggered` only if added to the tuple (HIS CALL #1) |
| 🟢 🧠 | distinct symbols with a 🧠 armed row AND `is_entry_plan` |
| ✨ break (kind aplus) | read state in `BREAK_STATES = ("aplus", "triggered")` and entry bar close (`alerts.bar_close_et(entry_bar_t)`) within 30 min — survives the A+ → triggered turn [C1] |
| ✨ ready | kind_of == ready AND tracker `state_path[-1]` == (forming, armed), its `at` within 30 min |
| ✨ 🧠 armed | newest armed stamp over the symbol's armed rows, within 30 min |
| ✨ listed (card only) | listed `since == today` AND scanner `first_qualified_at` within 30 min |
| ✨ 🧠 first seen (card only) | only when `GC.POTENTIAL_PUSH_ARMED_ONLY` is False [C7]; min `first_seen`, none if any doc joined |
| window | `0 <= now − at < ENTRY_MARK_NEW_MIN × 60 s` (30:00 exactly → off; a future stamp → off) |
| chip pulse | `CHIP_NEW_KINDS = ("aplus", "ready", "armed")` only [C5] |
| clock | `tab.banner_clock(...)["live"]` and `read_of_pass(doc, pass at)` per read |
| 🚫 | `SKIP_BROKER`: his names out of every mark, for every viewer (order_flags); never hidden from the board |
| past the cut [C6] | on the SHOWN sub, counted names not among `out["tiles"]` → `PAST_WORD` in that block's title; `n` unchanged |
| rang | live-push pages: "alert rang HH:MM ET" / "no alert rang"; 🧪 shadow / unknown → no clause; `entries()` read at most once, only when a green A+ or a new break is met |

### Stored "first entered" times (spec §1.3)

| state | stored time | notes |
|---|---|---|
| A+ / triggered (one break) | entry bar CLOSE = `alerts.bar_close_et(read["entry_bar_t"])` | never moves after the break |
| forming-ready / 🧠 armed | tracker `state_path[-1].at` when (forming, armed) | appended only when (state, kind) changes; pass clock |
| first seen on 🧠 | tracker `first_seen` | unknown if any of the symbol's docs is joined |
| new on his list | `gajjala_scan.first_qualified_at` | honest only when listed `since == today` |
| first appeared on a SETUP sub | NOT STORED | GAP → no blinker |

Mongo hands back NAIVE UTC — every stamp goes through `tab._stamp_utc` (a naive stamp is never read as ET; tested).

## Words (served; the FE types none)

`GREEN_HEAD` "🟢 {n} close to an entry" · `GREEN_WORDS` · `RANG_WORD` "alert rang {at} ET" · `GREEN_TAIL` "display only —
no order, count or alert changes · UNMEASURED" · `PAST_WORD` "{n} not among the {lim} cards shown: {names}" · `NEW_HEAD`
"✨ new in the last {m} minutes" · `NEW_TEXT` "new {at} ET" · `NEW_WORDS` · `NEW_TAIL` "marked new for {m} minutes ·
display only". No b-word, no "buy" (tested).

## Gaps (served as NO blinker)

- First appeared on a setup sub — not stored (reads are replaced each pass).
- A ready read that never was a 🧠 potential (no tracker doc); a joined doc's first sighting.
- On-open (on-demand) passes run the 🧠 gate DRY: a name that turned ready on an open pass is green at once but blinks
  only after the next cron pass stamps it.
- ☀️ / 🌙 lists carry no marks.

## Critique ledger (spec rev 2)

C1 break blinker survives the triggered turn · C2 one `is_entry_plan` (no green / no ready mark on a no-risk plan) ·
C3 FE badge in the chip's top padding band (FE package) · C4 `banner_clock` inside apply, lazy import inside `_soft` ·
C5 chip pulses for entry kinds only · C6 pre-cut population + PAST_WORD on the shown sub · C7 🧠 first-seen only when
armed-only is off · C8 contracts count read at rebase (main session).

2026-11-12 refix (verify pass, LOW): the 🧠 armed blinker now folds a row's `ready_since` into `armed_at` only when
`is_entry_plan(read)` — a no-risk armed name (trigger == stop) gets no card ✨ mark and does not pulse the chip, the same
rule as the 🧠 green and the setup subs' "ready" mark. Tests: `test_C2_NEGATIVE_a_brain_armed_no_risk_plan_never_blinks_or_pulses_the_chip`,
`test_C2_brain_armed_mark_skips_a_newer_no_risk_setup_and_keeps_the_planned_one`,
`test_MUTATION_dropping_the_plan_check_on_the_brain_blinker_is_caught` (all three fail with the check removed).

## Goldens (key for key; every leaf ADDED, none changed or removed)

| golden | leaves | what |
|---|---|---|
| GG5 BOARD `gg5_board_2026_10_27.json` | 310 | `entry_marks` × 20 boards (12 leaves each) + `new_mark` on 14 tiles (GGA aplus 10:40, GGB ready 10:41, 🧠 GGB armed 10:41, ➖ / 💋 "listed" card-only) |
| GG5 WRITES | 0 | byte-identical (passes without the env) |
| `gajjala_potential_golden_2026_10_15.json` | 57 | `entry_marks` on two boards + `new_mark` on 3 tiles |
| `gajjala_on_open_golden_2026_10_15.json` | 23 | `entry_marks.subs.bull_flag` on 3 boards + 1 `new_mark` |
| `gajjala_1m_board_2026_10_27.json` | 51 | `entry_marks` on 3 boards + `new_mark` on 3 tiles |
| `gajjala_track_record_golden_2026_10_16.json` | 3 | `entry_marks: {"subs": {}}` on 3 span boards (no pass this session on that store) |

`plan_text`, `subs[]`, counts and tile order byte-equal everywhere.

## Tests

`backend/tests/test_gajjala_entry_marks_2026_11_12.py` (71): green per state + NEGATIVES (partial, building, stopped,
triggered, invalid, 🧪 held, no `n: 0`); C2 no-risk / stop-above / no stop / unloadable ledger; triggered switch; C1
break windows (T+1, T+5, T+29:59, T+30:00, T+31, stopped / partial / invalid); 🧠 armed / building / one symbol once;
rang words + shadow + entries-once counter; ready windows (29 / 31 / 30:00 / future); no stored time; joined; naive UTC
vs ISO; listed today vs carried vs switch off; C7; C6; clock (outside window, stale cron, no pass, stale read); banner
clock truth table (8 combos) + pre-split rule; C4 soft (clock raise, import failure, apply / new_block raise); 🚫 owner =
non-owner; byte-identity with the marks stripped (5 subs); carded == n_tiles; GG1 / GGA; JSON allow_nan=False; mutation
cases. Real source mutations, bytecode purged before each: kind_of counting partial → 3 fail; joined guard dropped → 2
fail; BREAK_STATES without triggered → 4 fail; plan check dropped in is_entry_plan → 5 fail.

## Read-count pins — MOVED 2026-11-12 (refix)

The spec's rule (rang words read `entries()` only when a green A+ or a new break exists, §3.3 / §6) moved three existing
pins whose fixture store has an A+, 0 → 1, each with a dated MOVED note:
`test_gajjala_defects_k11_words_2026_11_11.py::test_alert_rows_is_read_at_most_once_per_build` `[playbook-None-1]` and
`[premarket-variant6-1]` (GG1 ☀️), and `test_gajjala_potential_tab.py::
test_one_alert_rows_read_per_potential_build_and_none_on_another_sub` (📖 playbook). Still ONE memoized read per build;
🧪 shadow still reads 0. NEGATIVE: `test_gajjala_entry_marks_2026_11_12.py::
test_NEGATIVE_no_aplus_and_no_fresh_break_reads_alert_rows_zero_times_off_the_setup_subs` — a day of ready + partial
cards reads 0 on 📖 playbook and the 1-min ☀️ (the green is still served), the same board with an A+ reads once. Real
mutation (bytecode purged): `entries()` called eagerly in `EM.apply` → both cases fail. Not chosen: passing `entries`
only on the setup / 🧠 subs — the strip's "alert rang" words would then change with the sub that is open.

## Frontend (WP-FE, spec §3.5)

`frontend/src/lib/ggEntryMarks.ts` (types + `markLive` / validators), `frontend/src/components/GgEntryMarks.tsx`
(`GgSubMarksView` — green badge via `data-label` + `::before`, never a text node; `GgNewMark` — pulsing dot + served
"new HH:MM ET"; both vanish at `until`), `frontend/src/styles/ggEntryMarks.css` (longhands only; the badge sits in the
chip's top padding band; reduced motion → static dot), 4 lines in `GajjalaBoard.tsx`, 2 fields in `gajjala.ts`.

## HIS CALLs (defaults shipped as noted)

1. `triggered` green too? Default NOT (one tuple `GREEN_STATES`). 2. 🚫 names out of the marks? Default out
(`SKIP_BROKER`). 3. Wrap the strip on the phone? Not built. 4. Chip pulse for new-on-list names? Default card only
(`CHIP_NEW_KINDS`). 5. Gaps above — a ☀️ "new mover" blinker? 6. Keep the 🎯 banner's clock? 7. Green card outline / a
push? Not built. 8. ✨ wording. 9. 🧠 blinker tied to `POTENTIAL_PUSH_ARMED_ONLY`? 10. `_tile_lines` "BUY >" on a
no-risk ready read — switch to `is_entry_plan`? Not built.

## Deploy

```bash
./deploy-cheetah-main.sh api frontend
```
