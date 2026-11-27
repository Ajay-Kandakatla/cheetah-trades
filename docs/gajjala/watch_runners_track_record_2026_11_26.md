# 📅 Runners — the nightly record (2026-11-26)

Ajay 2026-11-26 ~21:40 ET: "Ok then add them to our watch list and track them please.. I know he tracks them for two
weeks sometimes.. before he discards them.. Can you do that please"

Spec: watchrun rev 2 §3.4 (WP-2 `be-track`). Seating lives in `runseat.py` (WP-1); this file covers the record only.
**UNMEASURED** — a record, not a test. Nothing reads it to ring, gate, sort, cap or evict.

## What is recorded

- One doc per run in `gajjala_watch_runtrack` (`C.COLL_RUNTRACK`, handle `colls.runtrack_coll`), `_id` = `"<run day>|<SYM>"`,
  kept, no TTL. Module: `backend/chart_maps/gajjala_watch/runtrack.py`.
- The runs come from the 📅 runners doc: every entry's `runs`, plus every `removed[].entry` whose reason is `dismissed`,
  `aged` or `blocked`. `blocked` = it qualified and his × that day kept it off the list → `listed: false`. A run he
  removed, one that aged out and one that was blocked are all followed to day 10. The record keeps every runner,
  winners and losers alike.
- Window = the run day + the next 9 market sessions (`C.RUNNERS_KEEP_SESSIONS` = 10, his number; the run day is day 1;
  house calendar, so 2026-11-26 Thanksgiving is skipped).
- Each night, each OPEN doc's symbol costs ONE closed-daily-bar read: `sepa.prices.closed_daily_frame(sym,
  now=<midnight after the recorded session>, use_cache=False)`. These are regular-hours, provider-adjusted bars, and
  nothing is cached. The rows run from day 1 through tonight's session.
- Row: close / high / low / volume; change, high and low % vs the frame's previous close; the two run ratios; the 50-day
  average volume (`momentum_burst.avg_volume_before`; under 50 sessions → none) and volume ×; the stored reads (🧠
  tracker potential at its `first_seen`, armed at `allrules.first_armed_at`, 🎯 A+ at its ring time). Every time shown
  is the stored time. No stored read prints "no read". A store fault prints "reads not on file", never "no read". A
  session with no bar is `no_bar`, never a zero.
- A+ rings: every Track record A+ ring of the symbol dated in the window, or measured on a window session
  (`runseat.aplus_rings`). The doc lists `outcome` (the Track record's same-session grade), and `from_trigger_pct` /
  `passed` only for the seat's own ring. **A ring ON the run day is listed but never counted as "rang A+ later".**
  Only a ring dated after the run day counts.

## The base (where the peak printed)

| Seat peak | Base kind | Close-vs-run-close | Close-vs-run-high |
|---|---|---|---|
| Regular hours (< 16:00 ET) | `run_close`: the frame's run-day close | vs that close | vs the frame's run-day high |
| At or after 16:00, and the frame's run-day close == the seat's stored regular close at 4 decimals (`adjusted` false) | `run_high`: the seat's own high | **None on every row** (that close came before the run) | vs the seat's high |
| Anything else (no run-day bar, no peak time, a late peak on a re-based frame, no stored regular close) | `none` | None | None |

16:00 is `daytrading.data.ET_RTH_CLOSE`. 16:00 itself counts as late; 15:59 does not. The `adjusted` test is equality
only, with no threshold. A `run_close` doc's ratios come from one frame, so a re-based frame changes none of them.
After a late peak, the next session's plain day change still holds the after-hours run, and the base note says so.

## Closing (on the calendar)

- A doc is due when the last session of its window is the session being recorded.
- If the frame is read that night, the doc closes with `closed_by: window`.
- If the frame cannot be read and the window already ended before tonight, the doc closes with `closed_by: calendar`:
  each session with no stored row gets a `no_bar` row, and `no_price` is set when no session after the run day has a bar.
- A doc whose frame fails only on the closing night stays open, then closes `window` the next night with real rows.
- Only OPEN docs are fetched. A dead name costs at most 11 fetches (KEEP + 1).

## Summary (counts only)

`"{open} being watched · {closed} finished"`. Then, for each rule with a finished run: "ran with no A+ (n)" /
"ran after an A+ (n)", with "x of n ran again" and "x of n rang A+ on a later session". Each rule also gets
"x of n closed day 10 above the run-day close" (base `run_close`) and, kept apart, "ran after the 16:00 close: x of n
closed day 10 above the run's high" (base `run_high`), plus "n finished with no price" (only when n > 0), then the
NOTE. No rate, no rank.

## Wiring

- Nightly: `chart_maps/gajjala/nightly.py`, one fence after the 🩳 SI track record, with the import inside the fence.
  The result goes to `out["gajjala_watch_runtrack"]`; a failure is `{"error": "record: <Type>"}`. It is never in
  `errors` and never changes the exit code. STEPS and the crontab line are unchanged.
- CLI: `python -m chart_maps.gajjala_watch.runtrack --once [--dry-run]` runs the same function. `--dry-run` prints the
  ids it would write and writes nothing. Before 16:00 on a trading day it records the previous session, so a half bar
  is never recorded.
- Served (WP-1 route `GET C.API_RUNTRACK_PATH[?symbol=]` → `runtrack.payload`):
  - Without a symbol: `{state ok|empty|error|off, title, summary_text, note, asof_text, heads, rows, shown_text, open_n,
    closed_n, summary}`. Rows are the finished runs, newest run first, at most `GC.LEDGER_ROWS_MAX`. Each row is
    `{id, symbol, run_day, cells: {head key: served string}, values: {head key: raw}}`.
  - With a symbol: `{state, symbol, title, note, docs: [{run_day, seat_text, state_text, listed_text, heads, rows,
    base_note}]}`, with session rows in the same `cells` / `values` shape.
  - No NaN is ever served.
- Probe (read-only): `docker exec -i -w /app cheetah-market-app-api-1 python - < backend/scripts/gajjala_watch_runtrack_probe.py`
  reports how far the stored reads go, how many docs tonight would open, and when the first run closes. Its typed
  names, window and seat keys are pinned to the engine by `tests/test_gajjala_watch_runtrack_nightly_2026_11_26.py`.

## How far back

The stored 5-minute reads start on 2026-11-13 (the 14-day TTL). The first seatable runs are the 11-13 runs, and their
10-session window is 11-13, 16, 17, 18, 19, 20, 23, 24, 25, 27. No run has finished its 10 sessions yet. The first
closed rows are the 11-13 runs, at the **2026-11-27 nightly**. Runs before 11-13 are not rebuilt (HIS CALL #13).

## Tests

`backend/tests/test_gajjala_watch_runtrack_2026_11_26.py` covers the base (POM / BGLC shapes, re-based, 16:00 edge),
rows, reads, record (blocked / ×'d / aged / another run), closing (window / calendar / fail-then-recover), the A+
"later" count, the summary, and payload states with no NaN.
`backend/tests/test_gajjala_watch_runtrack_nightly_2026_11_26.py` covers the nightly fence, the CLI and the probe pins.
