# 🥇 Luk's 🏁: the R of a stop is now measured from the actual fill (2026-11-11)

Ajay 2026-11-11, relayed by the main session: **"Do your receommendations"**. This answered the line "say yes to 1, 5
and 7 now. The first fixes a wrong number you read…". Item 1 is this change. Spec: rec157 WP-1. The approval came
through the main session's relay (HIS CALL #12 of the spec). If he meant less than all three items, this served change
is the one to hold.

## What changed

| | before | after |
|---|---|---|
| a stopped row's R | booked at **−1.0** whatever the fill | **(stop − fill) / (trigger − stop)**, measured from the actual fill |
| exit price of a stop | the alert's stop | the alert's stop (unchanged: no slippage model, no gap-through-the-stop model, no new number) |
| R = | trigger − stop (the alert's plan) | unchanged |
| win / loss buckets | a stop is a loss | unchanged (fill ≥ trigger > stop, so R ≤ −1.0, still a loss) |

The fill is max(trigger, the fill bar's open). A fill on the trigger still gives exactly −1.0R. A fill that opened
above the trigger now loses more than one R. Before this change every other number on the row already used the fill:
the 9 EMA close exit `r_of(close)`, `r_now`, `best_r` and the +3R / +5R targets. Only the stop used the trigger.

## The helper (one rule, no Mongo write)

`backend/chart_maps/luk/ledger.py`:

```python
def stop_r(trigger, stop, fill_px) -> Optional[float]:
    plan, r = plan_of(trigger, stop)
    f, s = _num(fill_px), _num(stop)
    if plan != PLAN_OK or f is None or s is None or f <= s:
        return None
    return round(float((_D(s) - _D(f)) / _D(r)), 4)
```

- `walk()` writes `r = stop_r(...)` on a NEW stop. `exit_px` stays the alert's stop and the signature is unchanged.
- `cells()` ALWAYS derives a stopped row's R from `stop_r(row trigger, row stop, doc fill.fill_px)`. It never reads
  the stored `walk.r`, so legacy docs and new docs go through one rule. Every served reader (`counts_of`'s
  `mean_r_closed` and counts line, the row's `exit_text` / `exit` cell, the tape read line `luk/tape.py`, the charts
  through the buckets) reads the served cell.
- `stop_r` answers None (never −1.0 by default, never NaN) when the plan is not ok, the fill is missing / not finite,
  or the fill is at or under the stop. That cannot happen on a graded row. The row then reads
  `EXIT_STOP_NO_R_TEXT` = "stopped HH:MM · R not known — the fill is missing" (wording MINE). It stays a ❌ loss
  (`bucket_of("stopped", None)`) and stays out of the mean.
- **Legacy docs keep `walk.r = −1.0` in Mongo.** No migration and no `LUK_GRADE_VERSION` bump (the relayed "no
  migration"). After this change nothing served reads that stored value. A later cleanup is HIS CALL #11.
- Served words changed: the module docstring STOP line, the `walk` docstring, `RULE_TEXT` ("Stop = the alert's stop,
  a touch; the R of a stop is measured from the actual fill, so a fill above the trigger loses more than one R."),
  `CHARTS_HONESTY` ("(a stop is one R down or more, measured from the actual fill)"), and the `bucket_of` docstring
  ("every stop is −1.0 or lower, from the fill"). The two served sentences are MINE (HIS CALL #3).

## Grading runs under cron. The deploy needs api + cron + frontend

New grades are written by `chart_maps/luk/run.py:462-469`. That grade step runs only when `not dry and not
on_demand`, inside the Luk child the 🚩 5-minute pass spawns (`gajjala/run.py`). That pass runs from `backend/crontab`
in the `cron` compose service. Serving (the `cells()` derivation) runs in the api.

```bash
./deploy-cheetah-main.sh api cron frontend
```

The nightly champions audit reads Luk only through the served GET `/chart-maps/luk?sub=track_record&span=5d`. The
deploy corrects it and the workflow file needs no edit.

## Before / after (read-only, re-runnable)

Script: `backend/scripts/luk_stop_r_before_after.py`. It runs in the api container on origin/main engines. It never
imports `stop_r`: `probe_stop_r` re-implements the helper, and `tests/test_luk_stop_r_from_fill_2026_11_11.py` pins
the two equal over a grid that includes the six worst live stops. The script reads the UNCAPPED pipeline (`record_sessions → rows_for →
ledger_docs → track_row → mark_dups → counts_of`), never the 400-row capped day list. It asserts that its counts equal
`served_block(span="all")["counts"]` (exit 1 on a mismatch) and refuses any write (dry recording store).

```bash
docker exec -i -w /app cheetah-market-app-api-1 python - < backend/scripts/luk_stop_r_before_after.py > luk_stop_r_before_after.json
python3 backend/scripts/luk_stop_r_before_after.py --md luk_stop_r_before_after.json > luk_stop_r_before_after.md
```

This package was built at 12:00 ET on 2026-11-12, inside RTH, so the live run waited for the close. The table below
is the reproduction TARGET: the critic's read-only probe as of the 2026-11-11 close (spec rec157 §1.2), recomputed by
the planner. The script's own run (2026-11-12 16:23 ET, after the close) and every row that moved since the target are
in the section that follows. Rows of the 11-12 session are reported separately.

| as of the 2026-11-11 close (target) | served today | from the fill |
|---|---|---|
| closed n | 68 | 68 |
| stops | 48 (9 exactly −1.0 from the fill) | 48 |
| sum R (derived from the rows; the page serves no per-day R) | −4.93 | −107.59 |
| mean R | −0.073 | −1.582 |
| median R | −1.0 | −1.559 |
| buckets changed | — | 0 |

| the 68 counted closed rows, R from the fill (target) | n | sum R | mean R |
|---|---|---|---|
| all | 68 | −107.59 | −1.582 |
| without the 3 rows under `GC.LEDGER_MIN_R_PCT` (RC, FFTT, EP) | 65 | −74.63 | −1.148 |
| fill-over-trigger quartile 1 (0.00–0.46 %) | 17 | −8.02 | −0.472 |
| quartile 2 (0.72–2.14 %) | 17 | −29.50 | −1.735 |
| quartile 3 (2.23–3.96 %) | 17 | −26.91 | −1.583 |
| quartile 4 (4.14–10.11 %) | 17 | −43.17 | −2.540 |
| fill exactly on the trigger | 12 | −3.69 | −0.307 |
| fill above the trigger by at most `LC.LUK_NO_CHASE_PCT` (3.0) % | 31 | −33.36 | −1.076 |
| fill above the trigger by more than `LC.LUK_NO_CHASE_PCT` % | 25 | −70.55 | −2.822 |
| R taken as fill − stop (every stop −1.0R): a display of another convention, NOT the page's R | 68 | −29.13 | −0.428 |

At the 11-11 close the fills more than `LUK_NO_CHASE_PCT` % over the trigger carried −70.55R of −107.59R, and RC
2026-11-06 (−16.96R) and FFTT 2026-11-09 (−15.0R) were 29.7 % of the sum. The live run below moves both numbers
(the required line is printed there). RC and FFTT sit under `GC.LEDGER_MIN_R_PCT`, and Luk has no thin-R rule (HIS CALL #1). The `LUK_NO_CHASE_PCT` cut
is a display cut by name. His listed no-chase measures the trigger vs the low of the day, never the fill, and nothing
on the 🏁 applies it (HIS CALL #2).

Worst stops from the fill (stored plan + fill, read 2026-11-12 read-only):

| row | trigger | stop | fill | R from the fill |
|---|---|---|---|---|
| RC 2026-11-06 opening range | 1.11 | 1.105 | 1.1898 | −16.96 |
| FFTT 2026-11-09 opening range | 3.71 | 3.70 | 3.85 | −15.0 |
| PRCT 2026-11-05 opening range | 21.76 | 21.5201 | 23.575 | −8.5657 |
| HIHO 2026-11-02 opening range | 0.85 | 0.8392 | 0.924501 | −7.8982 |
| RSI 2026-11-02 pullback reversal | 11.56 | 11.50 | 11.79 | −4.8333 |
| CVM 2026-11-10 opening range | 1.44 | 1.43 | 1.475 | −4.5 |

### The script's run after the close

Run once, read-only, in the api container at 2026-11-12 16:23 ET (after the close) by the critic. The `--md` output
of that JSON, pasted verbatim (copies: scratch `rec157/luk_stop_r_before_after.json`, `.md`, `.py`):

Generated 2026-11-12T21:23:55.471311+00:00 · record 2026-11-02 → 2026-11-12 (read-only, the uncapped pipeline; served-block counts assert: held)

| | served (before) | from the fill (after) |
|---|---|---|
| closed n | 88 | 88 |
| wins / losses | 21 / 67 | 21 / 67 |
| sum R (derived from rows) | -29.55 | -138.48 |
| mean R | -0.336 | -1.574 |
| median R | -1.000 | -1.288 |

Stops 62 · exactly −1.0 from the fill 15 · buckets changed 0 · served equals fill-based: False

| session | n | served sum R | from-the-fill sum R |
|---|---|---|---|
| 2026-11-02 | 17 | +1.91 | -20.30 |
| 2026-11-04 | 6 | -1.15 | -9.67 |
| 2026-11-05 | 11 | -12.65 | -31.42 |
| 2026-11-06 | 11 | +12.75 | -13.09 |
| 2026-11-09 | 10 | +7.23 | -8.67 |
| 2026-11-10 | 13 | -25.54 | -34.94 |
| 2026-11-11 | 15 | -9.82 | -16.21 |
| 2026-11-12 | 5 | -2.29 | -4.17 |

| worst stops from the fill | trigger | stop | fill | fill over trigger % | R % | after R |
|---|---|---|---|---|---|---|
| 2026-11-06|RC|opening_range_high|aplus | 1.11 | 1.105 | 1.1898 | +7.19 | 0.4505 | -16.96 |
| 2026-11-09|FFTT|opening_range_high|aplus | 3.71 | 3.7 | 3.85 | +3.77 | 0.2695 | -15.00 |
| 2026-11-05|PRCT|opening_range_high|aplus | 21.76 | 21.5201 | 23.575 | +8.34 | 1.1025 | -8.57 |
| 2026-11-02|HIHO|opening_range_high|aplus | 0.85 | 0.8392 | 0.924501 | +8.76 | 1.2706 | -7.90 |
| 2026-11-02|RSI|pullback_reversal|aplus | 11.56 | 11.5 | 11.79 | +1.99 | 0.519 | -4.83 |
| 2026-11-10|CVM|opening_range_high|aplus | 1.44 | 1.43 | 1.475 | +2.43 | 0.6944 | -4.50 |

| the counted closed rows, R from the fill | n | sum R | mean R |
|---|---|---|---|
| all | 88 | -138.48 | -1.574 |
| without the rows under GC.LEDGER_MIN_R_PCT (0.5) %: 2026-11-06|RC|opening_range_high|aplus, 2026-11-09|FFTT|opening_range_high|aplus, 2026-11-10|ATGL|opening_range_high|aplus, 2026-11-10|EP|opening_range_high|aplus | 84 | -86.52 | -1.030 |
| fill-over-trigger quartile 1 (+0.00 to +0.24 %) | 22 | -3.35 | -0.152 |
| fill-over-trigger quartile 2 (+0.29 to +1.91 %) | 22 | -25.35 | -1.152 |
| fill-over-trigger quartile 3 (+1.94 to +3.77 %) | 22 | -44.21 | -2.010 |
| fill-over-trigger quartile 4 (+3.81 to +10.11 %) | 22 | -65.57 | -2.981 |
| fill exactly on the trigger | 19 | -1.72 | -0.090 |
| fill above the trigger by at most LC.LUK_NO_CHASE_PCT (3.0) % | 41 | -41.52 | -1.013 |
| fill above the trigger by more than LC.LUK_NO_CHASE_PCT % | 28 | -95.25 | -3.402 |
| R taken as fill − stop (every stop −1.0R) — a display of another convention, not the page's R | 88 | -34.26 | -0.389 |

The two worst rows carry 25.97 % of the sum. A reading, not a rule — HIS CALL.

**Most of the −1.57R a trade is the fill distance: fills more than `LUK_NO_CHASE_PCT` % over the trigger carry
−95.25R of −138.48R. That is a reading, not a rule. HIS CALL.** (At the 11-11 close: −1.58R, −70.55R of −107.59R.)
RC and FFTT are now 23.08 % of the sum; the two worst rows (ATGL −19.0, RC −16.96) carry 25.97 %.

**The served-block `counts` assert held. 0 buckets changed. The 68 rows of the target are unchanged, value for value
(same id, same served R, same R from the fill).** Every move is one of 20 rows that closed after the 11-11 probe:
15 rows of sessions up to 11-11 that closed on 11-12, and 5 rows of the 11-12 session. Read from one read-only GET
of the served 🏁 (`span=all`, 16:31 ET, counts equal to the run's); R from the fill re-derived with the same
arithmetic, and the sums tie to the run to 4 dp.

| session | 11-11 target: n · served · from the fill | 11-12 run: n · served · from the fill | the rows that closed since (served R → R from the fill) |
|---|---|---|---|
| 11-02 | 16 · −6.06 · −28.28 | 17 · +1.91 · −20.30 | NXT opening range, 9 EMA exit 11-12 after 9 sessions: +7.97R (a 9 EMA exit, unchanged by this change) |
| 11-04 | 6 · −1.15 · −9.67 | same | none |
| 11-05 | 10 · −10.0 · −28.77 | 11 · −12.65 · −31.42 | DNUT opening range, 9 EMA exit 11-12: −2.65R (unchanged by this change) |
| 11-06 | 11 · +12.75 · −13.09 | same | none |
| 11-09 | 10 · +7.23 · −8.67 | same | none |
| 11-10 | 11 · −5.54 · −14.10 | 13 · −25.54 · −34.94 | ATGL opening range, 9 EMA exit 11-12: −19.0R (unchanged by this change; R % 0.1189, under `GC.LEDGER_MIN_R_PCT`, the 4th thin row beside RC, FFTT, EP); EMBJ stop −1.0 → −1.84 |
| 11-11 | 4 · −2.16 · −5.01 | 15 · −9.82 · −16.21 | TH 9 EMA exit +2.34R; 10 stops: AVX, CORZ, NVTS, SKHY, WOLF, WULF −1.0 → −1.0 (fill on the trigger); BLZE −1.0 → −2.13, ELMT −1.0 → −3.05, EPRX −1.0 → −1.25, VSH −1.0 → −1.12 |
| 11-12 (new session, reported separately) | — | 5 · −2.29 · −4.17 | ASST stop −1.0 → −1.44, FLD stop −1.0 → −1.09, GDS stop −1.0 → −2.35, ASX 9 EMA exit +0.66R, FLX 9 EMA exit +0.05R |

- Stops 48 → 62 (+1 on 11-10, +10 on 11-11, +3 on 11-12); exactly −1.0 from the fill 9 → 15 (the six 11-11 stops
  filled on the trigger). Six new −1.0 rows pull the median from −1.559 to −1.288.
- As of the 11-11 session (the 83 closed rows dated up to 11-11, without the 5 rows of 11-12): served −27.26R, from
  the fill −134.31R.
- The worst six are the same six rows with the same R. The thin rows are 4 now (ATGL joined by its 9 EMA exit, not
  by a stop).
- 7 of the 10 new 11-11 stops print "stopped 09:30": the 11-12 open gapped through the stop. They are booked AT the
  stop (no gap-through-the-stop model, as decided above), so the real loss on those rows is larger than printed.
- `served_equals_fill_based: False` is expected before the deploy (the container serves origin/main). After the
  deploy the same script must answer `true`.

## Every reader of a Luk R (grep 2026-11-12, `backend/` + `frontend/src/`)

| hit | verdict |
|---|---|
| `luk/ledger.py` `walk` (the stop write) | FIXED: writes `stop_r` |
| `luk/ledger.py` `cells` stopped branch | FIXED: always `stop_r`, never the stored `walk.r` |
| `luk/ledger.py` `cells` 9 EMA branch (`float(w["r"])`) | unchanged, already `r_of(close)` from the fill |
| `luk/ledger.py` `counts_of` (`mean_r_closed`, closed ±) | reads the SERVED cells, so it is corrected |
| `luk/ledger.py` `bucket_of`, `charts_block`, `_categories` | tally buckets, not R. Buckets cannot move |
| `luk/ledger.py` `served_block` | serves no per-day R sum. The sums in the table are derived from the rows |
| `luk/tape.py:148` (`LL.cells` → the read line) | reads the served cell, so it is corrected (test pins "−1.6R" on a legacy doc) |
| `luk/tab.py:639, :687` | the only ledger call sites (`served_block`, the 🏁 sub count). No R |
| `chart_maps/api.py`, `push/hooks.py`, `push/subs.py`, `supply_demand/rules_info.py`, `supply_demand/alert_status.py`, `market_hours/gate.py`, `push/recent.py`, `gajjala/run.py` | import Luk for the tab / push / constants / spawn. No Luk R |
| `rules_info.py` | carries no Luk stop-R wording. No change |
| `frontend/src/lib/luk.ts:109` (`r`, `r_now`, `best_r` types) | types only. Nothing composes an R |
| `frontend/src/components/LukTrackRecord.tsx` | prints served cells / counts verbatim (pinned by `LukTrackRecord.stop_r.test.tsx`) |
| `frontend/src/components/LukTrackRecord.test.tsx:43, :49` ("−1.0R") | fills 0.01 over the trigger. `_r_text` prints one decimal, so it stays "−1.0R". Unchanged |
| `SPECS.md:1436` ("exit = the stop (−1.0R)") | the main session's file. Wanted words: "exit = the stop (R from the actual fill: −1.0R when the fill is the trigger, lower when it filled above)" |
| `~/.claude/workflows/champions-eod-audit.js` | reads the served GET only, so the deploy corrects it |

## Test pins

Moved (re-derived by hand):

| pin | old | new |
|---|---|---|
| `test_luk_ledger.py` served fixture: STP stopped, fill 12.41, trigger 10.00, stop 9.50 → `exit_text` | "stopped 10:12 · −1.0R" | "stopped 10:12 · −5.8R" ((9.50 − 12.41) / 0.50 = −5.82) |
| same: `mean_r_closed` | +0.65 | −1.76 ((−5.82 + 2.3) / 2) |
| same: `counts_text` mean | "mean +0.65R over 2 closed" | "mean -1.76R over 2 closed" |

Did not move (the fill is on the trigger): `test_luk_ledger.py` `r == -1.0` walk / grade pins, the `_vg_store` VG
duplicate fixtures (both fills on their triggers), the `bucket_of` pin, `test_luk_tape.py` "stopped 10:40 · −1.0R",
and `LukTrackRecord.test.tsx:43, :49`.

New: `backend/tests/test_luk_stop_r_from_fill_2026_11_11.py` (helper, walk, grade_step, legacy serve, tape line, the
NEGATIVES, the script units, the script main) and `frontend/src/components/LukTrackRecord.stop_r.test.tsx`.

## Golden (`backend/tests/fixtures/luk/luk_board_golden_2026_11_01.json`)

Regenerated by its recipe in the api image
(`LUK_WRITE_GOLDEN=1 python -m pytest tests/test_luk_tab.py -q -k golden -p no:cacheprovider`). Key-for-key diff:
exactly two keys moved, both the planned sentences. No other key moved and the golden holds no stopped row.

| key | change |
|---|---|
| `track_record.track_record.charts.honesty` (line 1297) | "(every stop is one R down)" → "(a stop is one R down or more, measured from the actual fill)" |
| `track_record.track_record.rule_text` (line 1418) | "Stop = the alert's stop, a touch." → "Stop = the alert's stop, a touch; the R of a stop is measured from the actual fill, so a fill above the trigger loses more than one R." |

## HIS CALL (nothing below is decided here)

1. Luk has no thin-R rule. RC and FFTT now print about −17.0R and −15.0R (ATGL's 9 EMA exit already prints −19.0R).
   A thin rule, a cap, or leaving them is his call.
2. Most of the −1.57R is the fill distance (−95.25R of −138.48R as of the 11-12 close). Two separate calls: apply the
   listed no-chase to the FILL (an entry rule), or measure R as fill − stop (a semantic, mean −0.39R). This change builds the relayed "same `r_of()`". Whether the
   served change waits until he reads the decomposition is also his call.
3. The three new sentences (`RULE_TEXT` clause, `CHARTS_HONESTY` clause, `EXIT_STOP_NO_R_TEXT`) are MINE.
11. Stored legacy `walk.r` stays −1.0 in Mongo. A cleanup is his call.
