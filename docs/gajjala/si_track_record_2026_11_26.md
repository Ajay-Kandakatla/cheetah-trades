# 🏁 🩳 SI track record — backend (2026-11-26, SPEC sitrack rev 2 §3.7, WP be-track)

Ajay 2026-11-26, verbatim: "I want us to track these patters for future from SI like a track recprd with in SI stocks
itself".

A **descriptive ledger**, UNMEASURED. No push, no gate, no sort outside its own table, no lane. It never prints the
house word SHOWN, and no served string says "signal" or "edge" (a test scans the golden).

Code: `backend/chart_maps/gajjala/si_track.py` · nightly fence `backend/chart_maps/gajjala/nightly.py` (after 💧) ·
served key `si_track` on the 🩳 block (`backend/chart_maps/gajjala/high_si.py`) · backfill
`backend/scripts/gajjala_si_track_backfill.py`.
Tests: `backend/tests/test_gajjala_si_track_2026_11_26.py`, `backend/tests/test_gajjala_si_track_nightly_2026_11_26.py`,
golden `backend/tests/fixtures/gajjala_si_track_block_golden_2026_11_26.json`.

## Storage (no new collection, no `store.py` edit)

`gajjala_state` only (no TTL) — `st.get_state` / `st.set_state`, the fault-aware `state_read`, and the index's `$addToSet`:

| id | content |
|---|---|
| `si_track|YYYY-MM-DD` | `{date, rows: [row…] by symbol, excluded: {reason: n} (high_si.REASONS), n, source: nightly / late / backfill, recorded_at, version}` |
| `si_track_index` | `{dates: [iso…] ascending}` |
| `si_track_stats` | the stats block + `computed_at`, `through`, `version` |

The row's keys are frozen (`si_track.ROW_KEYS`, 74 keys). A field that cannot be read is None — never 0, never False.

**Read faults (refix, 2026-11-26).** `store.get_state` swallows a raised find into `{}`, which looks exactly like
"nothing on file". Every read that decides a write now goes through `si_track.state_read` (the store's
`_find_or_none`: None = a read fault). A faulted index read skips the night (`faults: ["index_read"]`, no stats
written); `write_stats` and `served_block` raise `ReadFault` (the 🩳 block serves `fault_text`, never "nothing
recorded yet" or "0 of 0"). The index grows by ONE `$addToSet` on `gajjala_state` (no read-then-write, so it can never
be truncated). `record_session` reads the session doc itself first and raises `OnFile` when it says source
"nightly" — the night re-adds that date to the index (`faults: ["on_file:<date>"]`) and the backfill does the same
(`error: "on_file"`); the wiped 🔒 📄 ✂️ fields could never be rebuilt. A late / backfilled doc stays re-recordable.

## The rule, every definition with its source

| What | Rule | Engine / tag |
|---|---|---|
| Cohort | exactly the names the 🩳 sub lists: `scanner.listed_symbols(st, session)` → the tab's own filter on `st.reads(session)` → `high_si.evaluate(…, si_read=<point-in-time blocks>, listed=)`; every not-listed name counted in `excluded` by reason. A listed / short-interest read that raises → the session is NOT recorded, retried next night. Reads on file but an empty listed set → `listed_empty` fault, not recorded (never "every read"). | [C1] |
| Point in time | the served block when `published_on < session` (strict); else the prior settlement rebuilt through `SR.si_block` (today = the session, no basis) when THAT was published before the session (`pit "prev"`); else no row (`no_si`). | `SR.publication_date` (FINRA_PUBLICATION_BDAYS) |
| `listed_before` | `listed[SYM].since < session` — on the list before this session's first pass. **Not** the house `carried` (= did not qualify today); a name listed before that qualifies again stays `listed_before`. | [C1] |
| `qualified_today` / `listed_at` | `last_qualified == session` / ET HH:MM of the session scan doc's `first_qualified_at` | `store.py:456` |
| Prior close | ONE order for every row: the read doc's own tail `tile.bars5_prior` → the prior session's stored read doc `tile.bars5` (the day after a half day: the tail starts 15:00, the close was 13:00) → the scan doc's `last.prev_close`. A regular bar = `s` absent AND its START before that day's regular close (`ledger._close_et`). `scan_prev_close` is stored beside it and never chosen while bars exist. None → `no_prev_close`, in no count. | [C1] |
| Split guard | `ledger._default_split_lookup(st)` memoized per run on `(sym, lo, hi)`: a split in (prior day, session] → `outcome_state "split"`, no outcome numbers; unreadable → `"split_unread"`, retried inside the look-back. | [C1] |
| `winner` | `runners.ran_of({"last": {"prev_close": <ledger prior close>}}, read_doc, session)["run_pct"] >= WC.RAN_MIN_PCT` — the SAME 📅 engine on a stand-in scan doc. 09:30–20:00 high, premarket never counts, compared at `WC.RAN_PCT_ROUND`. `winner_strict` = its `counts` (also drops a higher premarket peak); `winner_scan` = the same call on the REAL scan doc (stored, never counted). | his 11-22 answer |
| Bars | the stored read doc when its pass stamp `at` ≥ the session's extended close `alerts._closes(day)[1]` (20:00; 17:00 on a half day, whose last pass is 17:01); else the 1-minute loader → `bars.build_frames` / `tile_payload` / `tile_prior_payload` → a stand-in read doc → the same `ran_of`. Neither → `no_bars`, retried inside the look-back. | [C9a] |
| Regular vs after hours | a bar tagged regular whose START is at or after `ledger._close_et(day)` is after hours (13:00 on a half day). | `vwap.py:11-13` cut |
| `high_at` | the START of the 5-minute bar that first printed the 09:30–20:00 high (`ran_of`'s `peak_et`) — a 5-minute stamp on both bar paths. | [C9b] |
| `high_where` / `day_high_where` | first_hour (< `RC.WIN_TIMING_BUCKETS[0][2]`) / rth_rest / ah; the day's high over every bar adds `pre`. `timing` = the 📅 engine's 🌅 ☀️ 🌙 bucket. | |
| `open_930`, `gap_pct`, `gap_up` | the first bar starting at or after `ET_RTH_OPEN`; `gap_pct` vs the prior close; `gap_up = gap_pct > 0` — a SHAPE, never a pattern. | [C4] |
| `pm_vol`, `pm_vol_ratio` | Σ volume of the premarket bars (None when the day has none) ÷ `gajjala_daily.avg_vol_50` (the house 50-day average, written the night before; the 11-26 study used 20 days). | HIS CALL #14 |
| `morning_fade`, `low_after_noon`, `fade_ramp` | MINE: the last regular bar ending at or before `NOON_ET` closes under `open_930` · the regular low printed in a bar starting at or after noon · `morning_fade and high_where == "ah"`. | MINE |
| VWAP | MINE: `vwap.minute_vwap(raw, iso, sessions=vwap.sessions(), rth_close=<regular close>)`; `vwap_reclaim_at` = the start of the minute after the last 1-minute close at or under VWAP when every later close is above it. `vwap_state` reclaimed / under / never_under / not_read; `not_read` is retried inside the look-back under the load cap. | [C9c] |
| 9 / 21 cross | `tab.ema_cross_block({"tf": "5m", "bars": bars5, "curves": curves5})`: `cross_up_at` = the START of the first UP cross whose bar starts at or after 09:30; `cross_pre` = an UP cross on a premarket bar (stored apart, never "by the first hour"); `cross_by_first_hour` = `cross_up_at` before 10:30. No curves → None. | [C9c] |
| ⛔ | `ssr.payload(symbols, now=<clock>, kick=False)` in chunks of `SR.MAP_MAX_SYMBOLS`, at two clocks built from the SESSION date: `SSR_OPEN_AT` (= `ET_PREMARKET_OPEN`; `in_play` holds only the prior market day → "on at the open") and `NIGHT_AT` (= `GC.LEDGER_GRADE_AT_ET`; `in_play` holds only the session → "triggered that day", `ssr_trig_on` / `ssr_trig_at` from the item). "on" True · "off" False · "unknown", a non-ok status or a raise → None. A None is re-read on later nights inside the look-back; a True / False is never overwritten. A test pins `in_play` at both clocks on a regular day, the half day 11-27 and 11-30. | [C2] |
| 🔒 | `reg_sho.payload(kick=False, now=now)` on the session's own night only: `regsho_on`, the run's state / days / day13 / start_by, `regsho_past` = state in (passed, passed_open). Not on any list → False only when every list was read (`complete`), else None. Late / backfilled → None. | |
| 📄 ✂️ | from the served `basis`, own night only: `dilution_before` = a `basis.filings[]` entry filed BEFORE the session (None unless `sources.sec` is ok / none / units); `split_before` = an executed `basis.splits[]` entry on or before the session (None unless `sources.splits` is ok). `dilution` / `split` / `flag_shorts` = the 20:15 chip's flags (`BM.FLAG_FILING` / `BM.FLAG_SPLIT`) — stored, shown in the day table, never a pattern. | [C3] |
| `dtc` | `SR.dtc_computed(b)` (WP1's frozen name, read through `getattr`; absent or raising → None); `dtc_provider` = the provider's figure. | WP1 |
| `prev_winner` | the name's `winner` in the prior session's stored doc; else `ran_of` on the prior session's stored read doc on the same prior-close order (only when that doc is complete and no split sits in the window); nothing on file → None (never False). | [C7] |
| `next` | filled the night the next session ends: `open` = the first bar at or after 09:30; `high_pct` / `low_pct` = the 09:30–20:00 high / low vs that open; a split in (D, N] → `"split"`, no numbers. `pending` / `no_bars` retried inside the look-back. | |

## The night (`record_night`, 20:15 ET, after 💧)

Tonight's session (only once its extended close has passed), then every session of the last
`LEDGER_GRADE_LOOKBACK_SESSIONS` market days that has stored reads and is not in the index (`source "late"`), then the
retry pass on every recorded session of that window (outcome `no_bars` / `split_unread`, VWAP `not_read`, ⛔ still None,
`next` columns), then the stats over every stored row. 1-minute loads AND outside split lookups share ONE cap,
`LEDGER_BACKFILL_MAX_SYMBOL_DAYS` a night (`deferred_cap` counts the refusals; the row stays in its retry state). A
session recorded by "nightly" is never re-recorded. No Mongo handle → `{"faults": ["no_store"]}`, nothing written. Never
raises; the `nightly.main` fence keeps any failure out of `errors` and the exit code. `STEPS` and the crontab line are
unchanged.

Split calls are counted on every memo miss, including the ones the scanner's own record answers without an outside
call — conservative (the cap can bind a little early); the lookup itself is the house one.

## Stats

The counted cohort = rows with `listed_before` True and `winner` True / False. Nothing else enters a rate or an interval.

- `base`: n, names, days, winners, rate, `ci_names = cluster_ci(vals, symbols)`, `ci_days = cluster_ci(vals, dates)`
  (`scripts.gajjala_study`, imported lazily; fewer than `MIN_NAMES` (= `MIN_CLUSTERS`, pinned) → None).
- `new_today`: names first listed that day, split by `listed_at` against 09:30 — counts only, no rate, no interval.
- Seven `PATTERNS`, each known before the open: ⛔ SSR on at the open · 🩳 EXTREME (vs High) · 🔒 on a Reg SHO list ·
  🔒 past its close-out day · 📄 dilution filing dated before the day · ✂️ split in force at the open · 📅 ran the
  session before. Per pattern: with / without counts and rates, `diff_pp`, `ci_names_pp` and `ci_days_pp`
  (`cluster_delta_ci` keyed on names, then on dates; under `MIN_NAMES` names or days on either side → None),
  `verdict = gajjala_study.verdict(ci_days, ci_names)` (clear only when both clear 0), `shuffle_share` (MINE: labels
  shuffled within each session, the day's count of True kept, `BOOT_DRAWS` from `BOOT_SEED`; the share at least as
  large as observed; only when the verdict is not `no_interval`; no cut applied), `unknown` (a None value, on neither
  side), and the word: "too few names or days" · "NOT SHOWN" · "interval clear of 0 on names and on days — 1 of 7 looks,
  not corrected".
- `SHAPES` (counts among winners and the rest, no interval, no word): gap up, ⛔ triggered that day, morning fade, fade
  then after-hours ramp, VWAP reclaimed, 9 / 21 cross up in the first hour.
- The import failing → no interval anywhere, `interval_ok` False; the counts still stand.

## Served block (`high_si.block` → `si_track`)

Mongo reads only (the index, the stats doc, the last `LEDGER_SPAN_SESSIONS_LONG` session docs). Keys:
`si_track.BLOCK_KEYS`. No stored session → the empty block (`EMPTY_SUMMARY`, `EMPTY_TEXT`) — not a fault. A raise, or a
module that does not import → `{"fault_text": high_si.SIT_FAULT_TEXT}` (one copy; `si_track.FAULT_TEXT` is it) and every
🩳 card stands. Day tables newest first; inside a day the counted rows first (winners first, then `high_pct` DESC), then
the rows first listed that day under `new_label`, then the other not-counted rows under `other_label`. Rows cut at
`LEDGER_ROWS_MAX`.
`rule_text` is built from constants at call time (a test checks every number in it).

**2026-11-26 refix — the day table's labels and the flags.** Each served row carries `group`, one of
`si_track.DAY_GROUPS` = ("counted", "new", "other"), drawn in that order. "counted" = on the list before the day and
graded True / False. "new" = `listed_before` False, under `NEW_LABEL` ("first listed that day — not counted").
"other" = on the list before the day but not graded (bars pending, a split, a split check pending, no prior close), or
no listing day on file, under its own `OTHER_LABEL` ("not counted — not graded, or listing day not on file"). Before
this, a row listed before the day but not graded sat under "first listed that day" while its own Listed cell said
"before". Each day serves both `new_label` and `other_label`. Every flag now prints once, in the Flags column
(`cells.flags`). `chips` is still served, but as `[]`. It used to repeat `flag_shorts`, so every flag printed twice on
a row. Tests: `test_day_rows_split_into_counted_then_first_listed_then_other_in_that_order`,
`test_NEGATIVE_a_row_listed_before_but_not_graded_is_never_in_the_first_listed_group`,
`test_NEGATIVE_served_day_carries_both_labels_and_they_differ`,
`test_NEGATIVE_every_flag_prints_once_on_a_row_in_the_flags_column_only`; the golden is regenerated.

## MINE (labelled so in the fold)

`NOON_ET` 12:00 · morning fade · low after noon · fade-then-ramp · the VWAP reclaim definition · the within-day shuffle ·
the "known" words of each pattern · the 🔒 "False only when every list was read" rule · `pm_vol` None on a day with no
premarket bar · the `listed_empty` fault · split calls counted on every memo miss.

## The ledger's own cohort (spec §1.3, rev probe `r2.py`; today's short interest, not point in time)

| 🩳-rule name-days, 11-12 → 11-25 | n | ran +40 % |
|---|---|---|
| all | 248 | 63 |
| on the list BEFORE the session (53 qualified again that day) | 191 | 30 = 15.7 % |
| first listed that day, before 09:30 | 18 | 7 |
| first listed that day, after 09:30 | 39 | 26 |

The prior close is on file for all 248 (tail 247, scan doc 1). Where both exist (110 rows) the tail close and the scan
doc's `prev_close` differ by more than 2 % on 19; the +40 % verdict differs on 2 (GLSI 11-17, MEDS 11-18). ⛔ through
the engine's own as-of read: every name None for 11-12 → 11-20; 11-23 = 11 on + 6 unknown at the open; 11-24 = 5 on +
13 off; 11-25 = 9 on + 11 off.

**Another cohort, not this ledger's prior:** the 11-26 SI squeeze-pattern study (2026-08-03 → 11-25, every 🩳-rule name
in the market) — base rate 3.0–3.6 %; SSR on at the open +7 to +11 pp, not significant after its 19-feature
correction. The page never prints its numbers.

## HIS CALL (built defaults, none decided for him)

- #5 which winner rule and prior close head the page (built: +40 % 09:30–20:00 on the last regular bar; `winner_scan`
  stored beside it).
- #6 late bucket (built: after the regular close; his 🌙 bucket from 15:00 is stored as `timing`).
- #7 the read word (built: the three words above, never SHOWN; the shuffle has no cut).
- #8 which patterns (built: seven, gap up moved to the shapes).
- #9 where the 🏁 sits (built: inside the 🩳 sub's ⓘ fold — the FE package).
- #10 ⛔ for 11-12 → 11-20 (not built: those sessions read "not known").
- #14 premarket volume base (built: the 50-day average).
- #17 who is counted (built: only names on the list before the session).

## Re-run

```bash
docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u -m scripts.gajjala_si_track_backfill > /tmp/si_track_backfill.log 2>&1'
```

`--dry` computes and prints only; `--from YYYY-MM-DD` starts later; `--force` re-records a late / backfilled session,
never a nightly one. Outside 09:30–16:00 ET. Stored reads live `READS_TTL_DAYS` (14) days — run it the day of the deploy.

## 2026-11-26 refix — five house source guards si_track.py crosses (widened 2026-11-26)

By the spec's own design si_track.py reads the 🔒 payload (`reg_sho.payload(kick=False)`), the short-interest read
(`read.si_block`, `high_si.si_blocks`, `ssr.payload(kick=False)`), the Watch's winner rule and VWAP
(`gajjala_watch.runners.ran_of`, `gajjala_watch.vwap.minute_vwap`) and the read doc's prior tail (`tile.bars5_prior`).
Five allowlists in files this package does not own say "nothing else may join"; each was widened on 2026-11-26
with a dated note: `test_reg_sho_threshold_2026_11_22.py` (`REG_SHO_READERS_*`), `test_reg_sho_closeout_day_2026_11_24.py`
(`DISPLAY_READERS`), `test_gajjala_all_table_si_2026_11_16.py` (S10 `others` exclusions),
`test_gajjala_watch_hook_2026_11_15.py` (the hits list) and `test_gajjala_squeeze_prior_tail_2026_11_08.py`
(`PRIOR_ALLOWED`). `tests/test_gajjala_si_track_guards_2026_11_26.py` pins the narrow shape each widening admits:
🔒 one `RSH.payload(kick=False)` call, no `check`, no `reg_sho_runs` / `kick_refresh` / `backfill_history`; 🩳 only
`short_interest.read / ssr / reg_sho / basis_math` and named `SR` / `HS` attributes, `ssr.payload` always
`kick=False`; 👀 only the Watch's `constants / runners / vwap`; the tail is `bars5_prior` read, never assigned; and
only `nightly.py`, `high_si.py` and the backfill script import si_track (no rule, gate, alert or push module reads it).


## 2026-11-26 — a failed session write is never indexed

`_write_session` writes the session doc with one `$set` upsert on the collection itself. `store._upsert` logs and
swallows a raise, which would have indexed a session that was never stored and skipped it on every later night. Now a
missing collection or a raised write raises `WriteFault`, the date is not indexed, `record_night` logs
`record:<date>:WriteFault`, and the next night records it.
