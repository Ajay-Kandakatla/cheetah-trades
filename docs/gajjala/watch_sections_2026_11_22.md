# 🗂 Watch, organized + 📅 Previous day runners (2026-11-22, spec watch_org rev 4)

## His words

Ajay, 2026-11-22: "I need gajjalas watch tab little more organized.

With less info, I want to know previous day winner auto additions vs intraday may be a time stamp. or something figure out a better way to organize that info for me.."

His answers the same day:

| Question | His answer |
|---|---|
| Build it? | "Build it (Recommended)" |
| What counts as ran yesterday (📅)? | "+40% vs prior close (Recommended)". The 09:30–20:00 high is at least +40% over the prior close, and the day's peak was not premarket (his 11-21 winner rule). |
| Where do your own names sit? | "Manual ones I add them need to be on top then auto intraday.. every month I want previous say winners sorted and  remove hot sectors mess from Gajjalas top view I need a new thing there.. use that space between the parent tab of Gajjala and watch tab to be for previous day runners but remove them if they don’t run the current day" |
| 04:00 auto-add of last session's winners onto the Watch? | "Yes, spec it". This is a spec only (`autoadd_spec.md`). Nothing is built. |

How his words are read:
- **"every month" is read as "every morning".** The strip is rebuilt every session. Nothing monthly is built.
- "previous say winners sorted" means last session's runners, biggest gain first.
- "remove them if they don’t run the current day" means the leave rule below.

Display only, everywhere in this note. No gate, push, cap, eviction or add rule reads any of it. Descriptive and UNMEASURED (the 11-10 study found A+ names in later sessions no different from names we did not ring).

## 1. Watch sections (built)

The Watch has three sections, in his order:

1. 👤 **Your names.** Your own names, newest added first. This order did not change.
2. 🎯 **A+.** The 🤖 A+ seats, newest A+ first.
3. 🤖 **Added today.** The other 🤖 names: premarket, intraday and after-hours adds in ONE section, newest added first, undated last.

How a name gets its group:
- The group comes only from facts that stay fixed for the session: whether the name is his or a 🤖 entry, and the entry's `why` (`sections.group_of`).
- Live card state, the A+ items, the entry's setup and the 📅 read never move a name. A test pins this.
- Your own A+ names stay in 👤.
- **📅 is a chip on the tile, not a section [D3].** A 🤖 name that ran last session keeps its place by add time. The "📅 Ran {day}" section comes only with the 04:00 auto-add (autoadd_spec, which appends `"ran"` to `SECTION_KEYS`). HIS CALL #12.

The time line on each tile:
- 🤖 names: "added 10:42", "added premarket 07:12", "added after hours 17:48", or "re-added 10:21" (when a removal of the same name exists earlier this session).
- Your names: "👤 added 08:15" (today), "👤 added 11-19" (an earlier day), or "👤 yours" (no add time on file).
- On a half day the close is `rth_close_time`, so an add at 13:05 reads after hours.

The pending poll (`?symbols=`) reads nothing new. Every `org` it serves is null, and `sections` is null. `C.SECTIONS_ON = False` serves the 11-21 payload byte for byte, in the old order (pinned).

## 2. The 📅 rule (`runners.ran_of`), the ONE engine

Inputs are stored docs only:
- Gajjala's scanner of that day: the non-held `gajjala_scan` docs.
- The read docs' `tile.bars5` (5-minute bars, 04:05→20:00, `s` = `pre` / `ah` / absent).

The rule:
- `pc` = `last.prev_close`.
- `hi` = the highest `h` of the regular and after-hours bars (09:30–20:00).
- **The peak minute is the START of the first bar that prints `hi`.** The bars are right-labelled: the bar stamped 10:05 holds 10:00–10:04.
- `run_pct = round((hi/pc − 1)·100, RAN_PCT_ROUND = 4)`.
- **Counts** when `run_pct ≥ RAN_MIN_PCT (40)` AND the premarket high is not above `hi`. A tie is not a premarket peak (AKAN 11-20).
- The peak bucket comes from 🎬's own `replays.store.bucket_of` and `WIN_TIMING_WORDS`. Its docstring now says the Watch assigns with it.
- Chip: "📅 ran Fri +165% (🌙 end of day peak)". Whole percent; this is safe only because a chip exists only when the name counts (≥ 40).
- Every % printed beside its bar goes through `pct_show`, which FLOORS it: 39.96 prints "+39.9%", never "+40.0%" [D5].

## 3. The strip (`GET /chart-maps/gajjala-watch/runners`, owner only)

- `runner_day(now)`:
  - In the pass window of a market day: the market day before today, live, with the cut.
  - Otherwise (after 20:05, before 04:00, closed days): the last completed session, nothing cut.
- **Order:** 🚫 last (tagged, never dropped), then biggest `run_pct` first, then symbol.
- **Leave rule** (HIS CALL #3), from `cut_at` = 09:30 + GG's 15 minutes = 09:45 ET (`potential._mute_end`):
  - A name leaves while today's high since 09:30 is under `RUNNERS_LEAVE_PCT = GC.SCAN_MIN_CHANGE_PCT` (+25%) vs its last-session REGULAR close (`last.day_c` when the tape says after hours, else the last regular bar's close).
  - The compare runs at 4 places: 24.96 is not running and prints "+24.9%".
  - It is stateless: a removed name comes back on the next GET.
- **Fresh reads only [D6]:** a name is judged only when its today read doc's pass stamp `at` is within `RUNNERS_STALE_SEC = 2 × GC.PASS_CADENCE_SEC` (10 minutes) and its bars already hold the 09:45 bar. Otherwise it is `not_read` and KEPT. The count then says "· n not read yet". When the newest stamp is stale it also says "· today's read is from 10:02 ET — nothing removed".
- **The count [D4]** counts only `running` names: "3 running today of 14 · 2 not read yet".
- Float comes from the read doc's own `ctx.float` (today's after the cut, else last session's), through `tab._float_chip` and the `float_read.title` words.
- 🏆 comes from `replays.store.past_wins_before`, for wins that ENDED strictly before the run day.
- 🚫 comes from ONE `store.broker_flags` read. On a fault nobody is tagged and nobody is hidden.
- `RUNNERS_STRIP_ON = False` returns `{state: "off"}` and reads nothing.

### Payload (the FE contract for `lib/ggRunners.ts`)

```
{state: "ok"|"empty"|"error"|"off"|"owner_only",
 title, text, hint, day, day_word, today, live, cut_active, cut_at, refresh_sec, fold_at, fold_at_phone, more_text,
 less_text, n, n_running, n_not_read, no_bars, as_of_et, stale,
 rows: [{symbol, run_pct, run_text, timing, timing_text, peak_et, float_text, float_title, past_winner_text,
         past_winner_title, broker_text, today_state, today_pct, today_text, title}],
 removed: [{symbol, run_text, today_pct, text}], removed_text}
```

`error` serves `{state, text, title, hint, day}`. A route-level fault serves `{state: "error", text}`. `today_state` ∈ `running` / `not_running` / `not_read`, and is null before the cut. The FE types no number and no word.

### Watch payload additions (the FE contract for `lib/gajjalaWatch.ts`)

- `sections: [{key, title, text, hint, n, symbols}] | null`. Keys come in served order. Today they are `yours`, `aplus`, `auto`; render ANY served key.
- `rows[].org: {group, when, setup, ran, past_winner} | null`:
  - `when`: `{bucket, verb, at_et, date, text, title}`. `bucket` / `verb` / `title` are null on his names.
  - `setup`: `{setup, label, state_label, source, text, title}`. 🎾 Reversal Squeeze is picked first. `source` is `board` (today's 🚩 card) or `entry`. The chip prints `text` (= `label`); `title` (= the state words) is the hover. One golden, `frontend/src/lib/__fixtures__/ggwSetupBlock.golden.json`, is pinned by a test on each side (review 11-22: the chip drew nothing while `text` was missing).
  - `ran`: `{date, day, prev_close, high, run_pct, peak_et, timing, timing_text, pm_high_pct, premarket_peak, counts, reg_close, text, title}`. `text` is null unless it counts; the drawer prints `title` always.
  - `past_winner`: 🎬's `{past_winner: [...], past_winner_count, past_winner_more_text}` plus `text` (the newest) and `title` (every item).

## 4. Probe (read-only, 2026-11-22, api container, this code loaded in-process)

The Monday 11-23 strip (it ran Fri 11-20) has **18 rows**:
- MEDS +165% 🌙 17:40 🏆 09-16 +601% multi-day
- MSS +151%, CIGL +128%, MRM +125%, ZJK +106% 🌅
- … down to AZIO +40% (the edge, 0.4015 → 0.5621)
- YOUL 🚫 last
- NXAT and RAYA absent (premarket peak)
- `no_bars` 0

Fri 11-20 (it ran Thu 11-19):
- 14 rows before 09:45, with CHSN and RAYA 🚫 last.
- At 20:04: "5 running today of 14", removed 9.
- At 11:00, with every `at` frozen at 10:02: "0 running today of 14 · 14 not read yet · today's read is from 10:02 ET — nothing removed", nothing removed.

Watch 📅 reads for Thu 11-19:

| Name | Watch 📅 read |
|---|---|
| MRKR | "📅 ran Thu +97% (☀️ intraday peak)" |
| SVRE | "📅 ran Thu +48% (🌙 end of day peak)" |
| GMM | no chip (premarket peak) |
| INHD | no chip (premarket peak) |

Measured cost:

| Read | Time |
|---|---|
| Strip, warm | 17.5–21 ms |
| Strip, first call in a fresh process (imports + 🏆 index) | 548 ms |
| `ran_for`, 9 names | 2.5 ms |

The 🚩 board GET pays nothing for the strip. The Watch GET pays ONE `ran_for` (1 scan find + 1 reads find) and the cached 🏆 index.

## 5. The strip's mount is HELD (HIS CALL #1)

`GgRunnersStrip` is built without a page mount. Three places fit his words:
- (a) the 🔥 slot ABOVE the Chart Maps tab bar;
- (b) below the tab bar, above 🚩's sub-tabs;
- (c) a 📅 tab between 🚩 Gajjala's and 👀 Gajjala's Watch.

🔥 is hidden (never unmounted) on 🚩 for him with the mount. Package `runners-mount-fe` waits for his answer.

## 6. HIS CALLs (defaults built, each flagged)

1. Strip placement: (a), (b) or (c).
2. 🔥 hidden on 🚩 only, or on 👀 / 🧪 too.
3. The leave rule: 09:45, +25%, comes back; the 10-minute stale guard. Or should a removal stick for the day?
4. Strip order: by gain, or by 🌙 → ☀️ → 🌅 then gain.
5. Fold: 8 on desktop, 3 on the phone line.
6. After 20:05 the strip already shows that day's runners.
7. Every word (all mine).
8. Your A+ names stay in 👤 (other items are kept from rev 2).
9. Switches `SECTIONS_ON` / `RUNNERS_STRIP_ON`.
10. Align the 🚩 board's "📅 on his scanner … +303%" tell to this rule.
11. The 04:00 auto-add and the 11-18 multi-day ask are NOT built.
12. A 📅 section on the Watch now.

## 7. Tests

New:
- `backend/tests/test_gajjala_watch_runners_2026_11_22.py`: the engine, the strip, D4 / D5 / D6, faults, source guards.
- `backend/tests/test_gajjala_watch_sections_2026_11_22.py`: group, order, words, the payload hook, the OFF byte-equal, the poll, C2 stability, D3.
- `backend/tests/test_gajjala_watch_runners_api_2026_11_22.py`: owner only, zero reads for anyone else, error words, NaN scrub.

Re-pinned:
- aplus row keys (+ `org`, with an OFF twin);
- newest (an OFF twin plus the ON order);
- tags (finder defaults);
- the api route list (+ GET runners).

## 8. Payload — ✅ All rules met (2026-11-24, spec watchall rev 2 §3.5, WP be-payload)

Ajay 2026-11-24, verbatim: "Anytime stocks qualify all his rules should be auto added to the Watch list so I can keep
tracking them later".

- A FOURTH section `rules` ("✅ All rules met"), served LAST: 👤 → 🎯 → 🤖 → ✅. `payload.rules_section` makes ONE read of the
  ✅ doc (`allrules.read_doc` + `entries_in_window`, imported lazily) and serves the names after his and the 🤖 / 🎯 names.
- One row per name: 👤 his > 🎯 A+ seat > 🤖 potential > ✅. A name that leaves 🤖 (↩️/✖️, made room, the 04:00 reset) is
  then served in ✅. `rules.n` = the rows served in ✅.
- A ✅ row's block sits under `row.auto` in the 🤖 shape with `why: "rules"`, the ✅ tag, "first met … · last met …" and
  the ✅ × title, so the FE treats it as machine-added with no parse change. `org.when` = "✅ all rules HH:MM" today,
  "✅ all rules MM-DD" on an earlier day, plus " · k sessions" when it met them in more than one. Inside ✅: newest-met
  first (`last_met_at`), undated last.
- The ✅ section block alone carries `folded_default: true` (`C.SECTIONS_FOLDED_DEFAULT`). Every other section is
  byte-identical. The ✅ hint is filled with the board words, the K11 floor, `C.RULES_KEEP_SESSIONS` and the 🚫 count
  of the loop's last step this session (`state.rules.not_eligible`).
- The board key `rules` = {state ok|unreadable, n, keep_sessions, text (unreadable only), not_seated_n}. It is absent
  while `C.RULES_ON` is False, and the payload is then the 11-24 one byte for byte. A read fault gives `unreadable`. The
  other rows stay intact and the board is never `error`.
- Every number goes through `potential._num` (a NaN / inf / bool volume serves no volume words). The tests dump with
  `allow_nan=False`. The held chip on a ✅ row is `held_text(C.AUTO_HELD_REASON)` under whatever PUSH_MODE says. It is
  tested with the push off and on.
- Goldens (BE writes, FE reads): `frontend/src/lib/__fixtures__/ggwAllRules.golden.json` and
  `ggwAllRules90.golden.json` (90 rows: 8 👤 + 2 🎯 + 10 🤖 + 70 ✅, so the live hub's refused tail past 80 is all ✅).
  To regenerate them, run `GGW_GOLDEN_WRITE=1` with `tests/test_gajjala_watch_allrules_payload_2026_11_24.py`.
- Display only. The list rings nothing. UNMEASURED.
