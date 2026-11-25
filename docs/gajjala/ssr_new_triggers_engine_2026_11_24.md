# ⛔ SSR — the names NEW on one trigger day: the engine (2026-11-24)

Ajay 2026-11-24, in order:

> "What are the SSR stocks today"
> "Can you add it to short interest tab"
> "The new ones"

"The new ones" = the names whose restriction STARTED on the day shown. This doc covers the engine half only (W1).
The 🩳 High SI block and the front end have their own docs (`high_si_ssr_new_2026_11_24.md`,
`high_si_ssr_new_frontend_2026_11_24.md`).

DISPLAY ONLY: it pushes nothing, gates nothing, sorts no card and enters no lane. **UNMEASURED** as a signal.

## The functions

- `short_interest.ssr_lists.symbols_on(loaded, T) -> list`: every stored exchange-list symbol (norm spelling) with
  a row whose trigger date is T, sorted. It reads `loaded["index"]` only, with no Mongo and no outside call. An unread
  or empty load, or a T that is not a date, gives `[]`. It is the one enumerator by trigger date (`rows_for` looks up
  by symbol).
- `short_interest.ssr.new_triggers(day, db=_DEFAULT, now=None, *, lists=None, corp=None) -> dict`: every name new on
  `day`, resolved by the rules the ⛔ tag already uses (`_day_eval` + `_on_block`). It does not compute the 10% line
  a second time. Mongo reads only: it never kicks the list refresh, never writes and never raises (a raise gives the
  `failed` shape). Every key of `NEW_KEYS` is present for every status, and every row carries exactly
  `NEW_ROW_KEYS`.

How it reads:

1. `in_play(now)` decides the **status only**.
2. The evidence is always the day D and its prior market day P (`prev_market_day(D)`). It is never "the other
   in-play day". So "triggered again" (`retriggered`, `mark_text`, `n_retriggered`) does not change with the clock.
   Rev 1 read P from the other in-play day, and the count fell from 101 to 0 at 20:00 ET [C1].
3. The exchange lists are loaded as of D's own files: `list_now = now` on D, else D 23:59:59 ET. The load therefore
   always reads files `[P, D]`. After midnight it never moves on to `[D, D+1]`.
4. One `trig` find over `[D, P]`. The candidates are every trig symbol dated D, then every `symbols_on(D)` name.
   Spellings are de-duplicated, so one name gives one row.
5. Each name is read in its own try, and a raise goes to `faults`. If D is on, `_on_block([ev(D), ev(P)])` builds the
   row. If D is off but has a D doc, the name goes to `withheld` (`bars_disagree`, `computed_only`, `corp_action`).

## Statuses

| status | when | rows | served sentence |
|---|---|---|---|
| `ok` | D is the newest in-play day and something was read | the names | `empty_text` when there are none (and no fault) |
| `not_read` | no row and the computed read is not live / final | `[]` | `fault_text` = `NEW_NOT_READ_TEXT`, which carries the as-of line |
| `pre_open` | D is today or later and the clock is before D's regular open | `[]` | `status_text` = `NEW_PRE_OPEN_TEXT` (the open comes from `_rth_open_dt`) |
| `not_latest` | D is in play but is not the newest in-play day | `[]` | `status_text` = `NEW_NOT_LATEST_TEXT` |
| `out_of_play` | D's window has closed | `[]` | `status_text` = `NEW_OUT_OF_PLAY_TEXT` |
| `failed` | no Mongo, a raising store or list load, lists that cannot be resolved, a day that cannot be read | `[]` | `fault_text` = `NEW_FAULT_TEXT` |

`prior_day` and `corp_checked` are None outside `ok` / `not_read`. So are the counts and the window.

## Honesty table (first match), then the dividend / split sentence

| rows | `computed.ok` | result |
|---|---|---|
| none | False | `not_read` + `fault_text`, never the empty sentence |
| none | True | `empty_text`, but only when no name faulted (a fault is never "no name") |
| some | False | `partial_text` part 1 = `NEW_PARTIAL_TEXT % computed text` |
| some | True | — |

[C4] `partial_text` part 2 = `NEW_CORP_UNREAD_TEXT % CORP_UNREAD_NOTE.strip()`. It is added when at least one row is
computed and D's dividends and splits were not read (`corp_checked` False). An exchange row needs no dividend check.
The status stays `ok`. The corp source text joins `asof_text` (computed text; exchange list texts; corp text).

## Words (served; the FE types none; MINE, HIS CALL 11)

`NEW_TITLE_TODAY` "⛔ SSR — new today (Tue 11/24)" · `NEW_TITLE_SESSION` "… new on Mon 11/23, the last session" (+
" · the market is closed today" on a closed day) · `NEW_AT_PLAIN` "10:00 ET" / "09:45:36 ET" · `NEW_AT_SEEN` "by 10:05
ET" (the 5-minute scan's first sight) · `NEW_SRC_COMPUTED` "computed" · `NEW_RETRIGGER_MARK` "also triggered Mon 11/23"
(always the prior market day) · `NEW_WINDOW_TEXT` (+ `HALF_DAY_TEXT` when the "through" day is a half day).

`NEW_NOTE_TEXT` makes no "comes off" promise and does not use `NOT_ON_LIST_YET` [C3b]. It says that most names stay
"computed", and that a name is not taken off this list for being missing from an exchange list. Every percent prints
through `SSR_TRIGGER_DROP_PCT`. No clock time is typed. `NEW_DAY_UNREAD` ("that day", the `_why_text` fallback word)
fills the fault sentence when the asked day cannot be read.

`withheld["computed_only"]` is DEFENSIVE. It cannot occur in production: the load reads files `[P, D]`, and D is
complete only with Nasdaq file(D+1). Test 7b pins this with the real `ssr_lists` and a planted next-day file.

## Measured (read-only container probes, 2026-11-24 12:04 ET; spec §1.5)

Script: `scratchpad/ssrlist/probe_ssr_new_v2.py`. It re-implements the read and has four folds, the prior day taken
explicitly. The re-runnable repo source for the board's numbers is `backend/scripts/ssr_new_list_report.py`, which the
main session owns.

| Check | Result |
|---|---|
| trig docs dated 2026-11-24 | 756 = 706 snapshot basis + 50 minute basis; 0 void |
| trig docs dated 2026-11-23 | 0 (the computed half began writing on 11-24) |
| ON rows through `_day_eval` + `_on_block` | 751, all `computed` (701 first-seen + 50 minute-bar); 5 withheld on a dividend / split day; 0 faults |
| Official rows dated 11-24 | 0 (Nasdaq 04:15 edition, all dated 11-23; NYSE not published until 20:10) |
| "also triggered 11-23", prior day explicit | 101 at 12:04 · 101 with the clock at 19:59 · 101 at 20:01 · 101 at 00:30 on 11-25 |
| Engine time, one pass | 30 ms |

### Accuracy of the computed read (never one figure alone)

- NYSE-side commons, ONE day: 27 of 28 (95% CI ≈ 82–100%), recall 87 / 87
  (`docs/short_interest/ssr_rule_201_2026_11_24.md`). This is a selected subsample.
- Whole market, the same day: the snapshot rule flagged 493 names, and the two exchange lists carry 447 names dated
  11-23 (Nasdaq 333 + NYSE Group 114). Precision is therefore **AT MOST 447 / 493 = 90.7% (Wilson 95% 87.8–93.0%)**.
  At least 46 computed names were on neither list read; some may be Cboe-listed, a source not read. This is an upper
  bound, not a measurement. The 493 came from a one-off probe, and no computed docs are stored for 11-23.

## UNMEASURED / owed

- **Owed:** the first real both-side precision AND recall, `scripts/ssr_agreement.py 2026-11-24`, at or after 04:20 ET
  on 2026-11-25. Write it under the ≤ 90.7% bound.
- Nasdaq's rows for a day may not arrive on that day at all. On 11-23 the URL still served the 04:15 edition at 22:10
  ET. This read never kicks the refresh (HIS CALL 12), so about three quarters of the list can stay "computed" for
  its whole life. The as-of line says which lists were read.
- No new signal is proposed. Nothing here is measured as an edge.

## Tests

`backend/tests/test_ssr_new_triggers_2026_11_24.py`: spec W1 tests 1–25, including 5a–5c, 7b, 12b and 15, with the
negatives marked `NEGATIVE`. Mutation spot-checks run 2026-11-24, each turning a named test red:

- ctx over `in_play(now)` turns test 5a red.
- dropping partial part 2 turns test 12b red.
- removing the list-day anchor turns tests 7b and 15 red.
- dropping the spelling de-duplication turns test 3 red.

## 2026-11-24 (late) — `recent_triggers`: the names under it from a RECENT trigger day (sissr WP be-ssr-words)

Ajay 2026-11-24 ~23:35 ET: "Days past little bit like AKAN is what I am mainly looking for many were so confident on
SSR..". `_new_triggers` steps 3–8 moved VERBATIM into `_rows_on(D, db, now_et, lists, corp)`; `_new_triggers` keeps the
status gate (step 2) and the honesty table (step 9), so `new_triggers` is byte-identical (pinned over 15 branches
against the 5dec3c6b body). NEW `recent_triggers(now)` reads today (once regular hours have opened — the `pre_open`
rule) plus `SSR_RECENT_TRIGGER_DAYS = SSR_FOLLOWING_TRADING_DAYS` market days before it, each through `_rows_on`, and
serves `{kind: "ssr_recent_triggers", status: ok | failed | closed, today, days, by_symbol, faults}`. Each name carries
the market day it is on counting the trigger day — `day_n` = the count of market days from the trigger day through
today, no numeric literal (AKAN: triggered Mon 11/23 → "⛔ SSR 11/23 · day 2" on Tue 11/24). The newest trigger wins;
`retriggered` is the newer row's own (a second trigger after the first window ended is new, never "retriggered"). A
day whose read raises is left out and listed in `faults`; every day raising reads `failed`, never an empty `ok`. A
closed day reads `closed` with nothing in it. The window is HIS CALL #1 (one constant): as built, AKAN is untagged on
Wed 11/25, the session the restriction lifts. Mongo reads only; never kicks, never writes. UNMEASURED. Tests:
`backend/tests/test_ssr_recent_triggers_2026_11_24.py` (negatives marked `NEGATIVE`; mutation spot-checks on `day_n`,
the pre-open skip and the moved sort each turn a named test red).

**HIS CALL #1 — open, ask before shipping (verifier, 2026-11-24 late).** Not a defect: the build does what §3.1 says.
A branch probe on live Mongo read 11/24 15:00 → days [11/24, 11/23], AKAN "⛔ SSR 11/23 · day 2"; 03:59 → [11/23]
only, AKAN still day 2. With `SSR_RECENT_TRIGGER_DAYS = SSR_FOLLOWING_TRADING_DAYS` (1), an AKAN-type name drops its
tag on day 3 (Wed 11/25). His words, "Days past little bit like AKAN is what I am mainly looking for", point at day 3
and later. The question: "keep AKAN tagged through day N?" — one constant; no number is picked here (the
`2026-11-24_ssr_day_closeout` study has no outcomes yet). Before widening, check that the older days' list files are
kept in Mongo (§6). Pinned both ways: `test_06_NEGATIVE_his_call_1_as_built_akan_is_untagged_on_wed_1125_day_3` and
`test_06_his_call_1_widening_the_one_constant_keeps_akan_on_day_3`.
