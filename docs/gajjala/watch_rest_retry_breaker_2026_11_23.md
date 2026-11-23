# 👀 Gajjala's Watch — its own REST breaker, the failed-minute counter, the re-read (built, OFF) — 2026-11-23

Ajay, verbatim (2026-11-23 ~12:00 ET): "Can you clean up some connection I am seeing delays price update for AKAN on the
watch chart.." · "I would like us to focus on connections of Gajjala more for the rest of the tabs."

**This is NOT the delay he reported.** That delay is the live feed going blind (a second login kicks the Massive socket
about every 110 s — blind 28.8 % of today's window by 12:16 ET, HIS CALL #10–#12, not touched here). This package works
on failed minute REST reads: about 3 of about 530 Watch minutes today (spec ggconn rev 2 §1.5). Transport only — no rule,
gate, threshold or ring condition changed. UNMEASURED.

Spec: ggconn rev 2 §3.4 / §4 WP-3 (session scratchpad). Code: `backend/chart_maps/gajjala_watch/rest.py` (new),
`loop.py`, `constants.py` (`REST_*`). Tests: `backend/tests/test_gajjala_watch_rest_2026_11_23.py`.

## What is ON

- **The Watch's own breaker** (`REST_OWN_BREAKER_ON = True`). The minute loader (`rest.load_day`) hands
  `daytrading.data.load_intraday` its OWN breaker (`cb=`, WP-4's parameter). `REST.open_read()` swaps in a NEW closed one
  before every read, on the loop's own thread, before `frames_for` builds its worker pool (the pool is a `with` block, so
  no fetch is in flight at the swap). The module's trip rule (3 failures) and cooldown (60 s) still apply INSIDE a read.
  - Before: three 6 s timeouts at ~:36 opened the module breaker for 60 s → the next minute's read (:30) returned
    "failed" for every name at once (11:38:36 → the whole 11:39:30 minute, today).
  - Now: a trip costs the rest of THAT read; the next minute reads again. No cooldown number of mine.
  - Every other caller (🚩 pass, 🚩 1-min, Luk, the lane, ledger, tape …) keeps the module breaker `_CB`, byte for byte.
    `--dry-run` (`dry_deps`) keeps the module breaker. The `--build` child uses the own breaker but never renews it.
  - Revert: one line, `REST_OWN_BREAKER_ON = False` → the loader is `RUN._load_day` again and `open_read()` does nothing.
- **The counter** (always). One small doc per session, `rest:{session}` in `gajjala_watch_state`, one `$inc` per
  iteration that ran (never on `--dry-run`): `iterations`, `names` (name-minutes read) and, on a minute with a failed name,
  `failed_minutes`, `failed` (failed name-minutes), `retried`, `recovered`, `pushed`, `no_time`, `errors`, plus `last`.
  The `latest` state doc gains NO key (its key set is today's). A counter write that fails logs one line, never raises.
- **The key scrub** on the loop process's log lines: `main()` calls `observability.logsetup.install_redaction()`.

## What is built and OFF — HIS CALL (spec §7 C)

`REST_REREAD_ON = False`. When he turns it on: ONE re-read of a minute's `failed` names (never `over_budget`, `no_bars`
or a name the read did not report), after a `REST_RETRY_PAUSE_SEC` 2.0 s pause (MINE: = the minute fetch's own 429
pause), inside the same minute budget, never started with less than one fetch timeout (`_FETCH_TIMEOUT_SEC` 6 s) of
budget left (`no_time`). Order: cross push → every tile written (today's block, unchanged) → pause → re-read → cross push
for the recovered names only → their tiles. A name re-read again `failed` / `over_budget` keeps `failed` and its last good
frames; `no_bars` writes a status-only tile.

Why OFF: when on, a recovered read can ring a 🔀 Watch cross that today is lost — counted `missed_fetch` the next minute.
It is the same cross rule (latest closed bar + fresh, the claim, the latch, every gate — `cross_alerts.py` is untouched)
on a read that now succeeds, on its OWN minute only: the re-read keeps the iteration's `now` (the frame is cut at
`now − BAR_SETTLE_SEC`, so a bar that closed during the wait is not in it) and freshness is judged on the clock AFTER the
re-read. NO gate changed; HIS CALL #20 (accepting "latest − 1") untouched — a recovered read's latest − 1 is always
`late` (the pause pushes it past the 90 s window). He decides on the counter's number.

**How late a re-read ring can be:** never more than `GG1M_CADENCE_SEC` 60 s after its iteration started (`is_fresh`
refuses anything later as `late`), and ≤ `GG1M_MINUTE_BUDGET_SEC` 35 + `_FETCH_TIMEOUT_SEC` 6 = **41 s** when every GET
answers or times out (a re-read starts with ≥ one timeout of budget left; the prior day + today in sequence is the worst
case). The normal ring leaves about 4 s after the start (`wall_s` 3.9 at 12:31:30 ET, one sample).

## The count (read-only)

```bash
docker exec -i -w /app cheetah-market-app-cron-1 python -m scripts.gajjala_watch_rest_count --sessions 5
docker exec -i -w /app cheetah-market-app-cron-1 python -m scripts.gajjala_watch_rest_count --json
```

Per session: iterations, names, failed_minutes, failed, retried, recovered, pushed, no_time, errors, the share
failed / names with a Wilson 95 % interval, and `last`. No write. A frequency, not an edge. Base rate today (one session,
before the counter existed): 5 failed fetches in 2 minutes + 1 blackout minute.

Refix 2026-11-23: the script also runs by file path from `backend/` (`python scripts/gajjala_watch_rest_count.py`) —
before, that form raised `ModuleNotFoundError: No module named 'scripts'` at the Wilson import once a doc had
names > 0; the `-m` form above is still the one to use in the post-deploy check. The interval is the study helper's
`wilson`, rounded to 3 dp (0.1 pp): 5 failed of 10,600 names prints 0.05 % (Wilson 95 % 0.0 %–0.1 %). Widening that
precision is the planner's / owner's call, not changed here.

## Flip checklist (`REST_REREAD_ON` → True, only on his word)

1. `backend/chart_maps/gajjala_watch/constants.py`: `REST_REREAD_ON = True` (the one line; a test pins it literally
   `False` — re-pin it in the same change).
2. `frontend/scripts/contracts.mjs`: the "🔌 Gajjala Watch connections" line that pins `REST_REREAD_ON = False`.
3. His word on the ℹ️ sentence `cross_alerts.py:245` "A cross missed by a failed minute read is never sent late." —
   a re-read ring leaves up to 41 s (ceiling 60 s) after the normal time; his reading of "late" decides whether the
   sentence stays or changes (a wording change).
4. `tests/test_gajjala_watch_loop_2026_11_15.py:278-288` (`test_a_failed_read_keeps_the_last_good_charts`) uses the
   default `time.sleep`: with the re-read on it sleeps 2 s for real unless that test is given a recording `sleep`.
5. Trap: with `REST_OWN_BREAKER_ON` False and `REST_REREAD_ON` True, a tripped minute's re-read fails at once (the
   module breaker is still open). Documented, not handled.

## Cost

- Own breaker: in a provider outage the Watch probes EVERY minute instead of every other one — ≤ `BAR_WORKERS` 8 doomed
  fetches of ≤ 6 s per read (the third failure trips the breaker; names not yet started return at once); in a 429 storm a
  doomed fetch is up to 3 GETs. One more Mongo `$inc` a minute. ~250 counter docs a year, never pruned (HIS CALL #16).
- Re-read, when on: ≤ one extra today-fetch per failed name per minute (+ the prior day when not memoised), ≤ two reads a
  minute; the cross engine runs twice in such a minute (never on the same name twice).

## Depends on WP-4

`rest.load_day` calls `load_intraday(..., cb=)` and `open_read()` calls `daytrading.data.new_breaker()` — both are WP-4's
(`daytrading/data.py`). Ship the two together; WP-3's own tests stub both names.
