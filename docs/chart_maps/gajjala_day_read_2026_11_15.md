# 🌫️ Day read on the Gajjala tabs — information only (2026-11-15)

**Information only.** Not a gate, not a push, not a sort, not a filter, not a lane input, not measured. The prior on
every read is **NULL** (the in-sample study, `docs/gajjala/shadow_day_tags_2026_11_11.md` "In-sample prior").

## His words

2026-11-14: "Also lately I am seeing very choppy market but Gajjals examples are very bullish".

2026-11-15, asked "do you want a 'choppy day' label on the Gajjala tab now, just as information? Making it a gate would
wait for that recorder's result." — he answered: **"yes"**.

"Choppy" is his word and lives in the ✨ label and here only. The prereg defines no chop measure, so the served head
says "{on} of {read} pre-registered reads on · information only".

## ONE engine

`backend/chart_maps/gajjala/day_read.py` builds the recorder's `inputs` through the probe's own
`scripts.shadow_day_tags_probe.build_inputs(db, now, only=…)` (the probe's `main()` body moved verbatim into it; `main()`
keeps the argv parse, the Mongo handle and the two presets, then prints `build_inputs(...)` — byte-identical stdout) and
calls `scripts.shadow_day_tags_lib.compute(inputs, session)` verbatim. No formula is copied, moved or changed: the lib's
code body (bytes from `import gzip` to EOF) hashes to `e7e6df818ee4a78f65b5013ca999647c499b6aa59f3f16eef513f3cc0e137d7a`,
pinned by a test. Only the lib's 2-line docstring changed (it now names this ONE served reader). The probe and
`portfolio.store` are imported lazily inside `inputs_for()`; `db` is never truth-tested (`if db is None`; a pymongo
`Database` raises on `bool`), `None` from `_get_db()` → `RuntimeError`.

Computed ONCE per 🚩 GG5 5-minute pass (its own try in `run.py`, the A8 token check first on an on-demand pass) into ONE
`gajjala_state` doc `_id="day_read"`: `{session, computed_at (UTC), tags (the lib's, verbatim), asof, constants,
inputs_sha256, forms}`. Served as `day_read` on `/chart-maps/gajjala`, `/chart-maps/gajjala-1m` (GG5's doc through
`st.shared`) and `/chart-maps/luk`, **to the primary owner only**; `null` for anyone else and on 🧪 Audited. The recorder's
store is never read — by this code or by its verification.

## The eight chips (the lib's `TAG_FORMS` order)

Cut times are formatted from the constants by name (`T2_FIRST_HOUR_END_ET`, the lib's `PRE_CUT` / `GD4_PRE_CUT`); the
THEIRS / MINE note is the lib's `SOURCE_TAGS`, served per chip.

| form | chip words (ON means) | read at | THEIRS / MINE |
|---|---|---|---|
| GD3w_pre | most setups failed this week (GD3w) | prior 5 sessions | 5 sessions + 50 % MINE |
| GD4_pre | risk halved after losses (GD4, before the 09:30 open) | 09:30 | halving THEIRS; win reset MINE (lane HIS CALL #18) |
| GD4_by1030 | risk halved after losses (GD4, by 10:30) | 10:30 | halving THEIRS; win reset MINE |
| GD6b_pre | fewer runners than usual (GD6b, the 09:29 pass) | 09:29 | median + window MINE |
| GD6b_by1030 | fewer runners than usual (GD6b, the 10:30 pass) | 10:30 | median + window MINE |
| GD7_by1030 | QQQ and IWM both red into 10:30 (GD7) | 10:30 | both red MINE |
| LD3i_pre | IWM 9 EMA under 21 (LD3i) | previous close | 9/21 THEIRS |
| LD9_pre | big techs under 9 & 21 (LD9) | previous close | 9/21 THEIRS; list + 4 MINE |

Value words: GD3w "{failed} failed · {held} held ({share} failed)"; GD4 "risk ×{mult}"; GD6b "{n} names at the pass ·
median {m}"; GD7 the lib's value verbatim; LD3i "9 − 21 EMA {±x.xx}"; LD9 "{weak}/{n} big techs weak".

## States

- **on / off** — the lib's `status: ok`; counted in `read` (`read = on + off`).
- **not read** (`missing`) — the lib's MISSING, its `why` served; never counted as on or off.
- **reads at HH:MM ET** (`pending`) — the session is today ET **and** the doc was computed before the form's read cut.
  Keyed on the doc's own `computed_at`, never the GET clock; a non-today session is never pending; the cut is strict
  (a doc computed at exactly 10:30 reads). Its tag is served `null`, no value words.
- **absent** — no doc, the doc's session is not the board's, or the doc has no readable compute clock: "🌫️ Day read: no
  read on file for this session yet — it is read on every 5-minute 🚩 pass" (the cadence from `PASS_CADENCE_SEC`).
- **Closed days** — the board carries the last session (`tab.session_for`); the head gains " · last session
  YYYY-MM-DD" and every chip's `asof_text` carries the full read date ("read 2026-11-13 10:31 ET · …"). ISO datetimes
  in `asof_text` render in ET (`%Y-%m-%d %H:%M ET`, no microseconds, no offset); date-only and non-ISO strings stay as
  they are.

Default view (Rule #5): head + caption visible; the eight chips, the note and the read rule fold under the served
`fold_text` "the 8 reads".

**GD7 reads "not read" on every session day by construction.** `daytrading/data.py` `load_intraday` caches a day's
minute bars only when that day is not today, so `intraday_cache` never holds the live session's QQQ / IWM bars; the
nightly recorder sees the same MISSING when no reader asked for them. Warming them = a scheduled provider fetch = HIS
CALL.

## The intraday read vs the nightly record [C1]

The CODE is the record's; the INPUTS are not. `ledger._cell(...)` with `provisional=False` (the probe's `gg5_rows`)
writes a 🏁 cell only after the EOD grader runs (`gg5_last_graded_at` ≈ 20:15 ET): until then an A+ whose next-day exit
landed earlier in the session is `pending`. The lib's `ap_events` takes only `bucket in ("win", "loss")`, so that exit
is left out of a 10:31 pass's GD4 walk and is in the 20:55 recorder's. **GD4_by1030 and GD3w_pre can therefore read
differently intraday than in the nightly record** (same lib bytes, different `inputs_sha256`); GD4_pre is stable (its
09:30 cut precedes any of the day's exits). The served `note` says so, naming the grades on file:
"Read during the session from the grades on file (through {grades_through}). The nightly record is taken after the
close, so GD3w and GD4 can read differently there once the day's grades land." Pre-grading pending cells in the pass
would be a 🏁 rule change — not done (HIS CALL #12).

## The read date — a RULE, never a served date [C2]

Served: "Read once, when every page holds 30 recorded entry weeks forward from 2026-11-12 (the prereg's
MEASURE_FLOOR_WEEKS rule); nothing is read before then." (`AR.MEASURE_FLOOR_WEEKS`, `LIB.FORWARD_FROM`, by name.)

The arithmetic, kept here as a **lower bound only**: FORWARD_FROM's ISO week is 2026-W46 (Monday 2026-11-09); + 29
weeks → Monday 2027-05-31. Valid only if W46 is back-filled (`python3 backend/scripts/shadow_day_tags.py --recompute
2026-11-12..2026-11-13`, HIS step) and no week is missed. The rule counts weeks WITH a recorded session; on 2026-11-14
the recorder's directory did not exist yet, so the bound moves with every missed week (without the W46 back-fill:
2027-06-07). Nothing served changes either way.

## Caption [C10]

"Information only — not a gate, not measured. In the 22 sessions studied no read flagged the worse days; GD6b read the
opposite way (not significant after correction); LD3i and LD9 had too few days." (`IN_SAMPLE_SESSIONS = 22`, pinned to
the recorder fixture's session count.) No served sentence claims a forward record exists.

## Parity proof

`backend/tests/test_gajjala_day_read_2026_11_15.py`:

- `DR.tags_of(inputs, d)` == `LIB.compute(inputs, d)` byte-for-byte (sorted JSON) on all 22 fixture sessions; NEGATIVE
  one flipped `on` breaks it; a non-market session raises as the lib does.
- The inputs builder IS the probe: on the recorder test's fake Mongo, `PR.main([])` stdout == `json.dumps(build_inputs
  (db, now))` with the recorder's own dump settings, and `DR.inputs_for(now, session=…, db=db)` ==
  `PR.build_inputs(db, now, only={session})`; NEGATIVE `only` limits the QQQ / IWM bars to that session and nothing
  else moves; no Mongo write.
- The lib code-body sha pin (NEGATIVE: one changed byte breaks it); the prereg sha unchanged.
- [C5] a `__bool__`-raising db is used without a truth test; `None` → `_get_db()` once; `_get_db()` → `None` →
  `RuntimeError` and no build.
- The served block: pending at 10:26 / readable at 10:31 / strict cut / keyed on the doc clock; non-today never pending;
  missing never on or off; exact heads; closed-day tail; absent (six shapes); fold text; note + `grades_through_et`;
  ET as-of strings (NEGATIVE date-only and names untouched); words from the constants (NEGATIVE 10:45 moves them);
  value words; caption; read rule names 30 and 2026-11-12 and no other date; the module holds no `2027-` literal.
- Guards: no outcome key or word in the block; no b-word; `tab._plain` → JSON with `allow_nan=False`; `day_read.py`
  imports no trading / push / provider / gate module; the probe and `portfolio.store` only inside `inputs_for`; the
  module never names the recorder's store.

`backend/tests/test_shadow_day_tags_2026_11_11.py` (recorder guards amended 2026-11-15): nothing outside `scripts/` and
`tests/` names the package EXCEPT `chart_maps/gajjala/day_read.py`; both probe presets precede `build_inputs(` in
`main()`. The 22 × 8 pin, the prereg pins and every other recorder test are unchanged.

Live parity (after deploy, §5.4 of the spec): (a) same-window probe + `LIB.compute` vs the served `tags`, 8 / 8
expected equal; (b) after the close, a FRESH probe + compute vs the day's last `gajjala_state.day_read` — GD4_by1030 /
GD3w_pre may differ for the [C1] reason. The recorder's store is never opened.

## HIS CALLs

1. The guard relaxation — the lib's "nothing served imports this file" became "ONE served importer, day_read.py".
2. Who sees it — owner-only on all three surfaces; widening = his word.
3. 🧪 Gajjala · Audited — no day read there by default.
4. GD7 "not read" by construction — warming QQQ / IWM minute bars = 2 scheduled Massive fetches per session.
5. The recorder has written no forward record yet (directory absent 2026-11-14) — confirm the scheduled task runs.
6. The fold — head + caption visible, chips folded; unfolding by default is one line.
7. BOARD golden dated regen (ADDED leaves only); WRITES golden untouched by design. Done 2026-11-15, checked
   key-for-key against the pre-regen bytes: 0 changed, 0 removed, every added leaf under `day_read` — GG5 BOARD 374
   (22 `absent` blocks), FE 1m board 51, on_open 51, potential 34, track_record 51, Luk golden 3 (`null`, not the
   owner); WRITES byte-identical. The two "owner minus the 🚫 tags == non-owner" tests now also drop `day_read`
   (owner-only by the same rule) and assert the non-owner's is `None`.
8. Cost — resolved: 0.99 s wall per pass for the whole inputs build (critique, container, 2026-11-13 inputs).
9. Words — "choppy" only in the ✨ label; every chip / value / note / caption word is MINE.
10. Two IWM 9/21 words on Luk's tab (🧭 vs LD3i) may disagree on a day.
11. Back-fill W46 (`--recompute 2026-11-12..2026-11-13`) — HIS step.
12. The intraday read vs the record (GD3w / GD4_by1030) — hide until graded, or pre-grade in the pass: both his call;
    neither built.
