# ⏱ Bar close + settle — the finality probe (2026-11-09, GG LIVE spec §3.4, WP-C)

Ajay 2026-11-09 ~01:00 ET:

> "I would like the autopilot to be continously monitored or live tracked and changed as if Gallalas makes the trades
> can you modify and make it more live with websockets or something else where there is a low latency monitoring on
> the prices action changes please?
>
> same for reuglar Gajjlas tab as well need it to be more live"

**Verdict: the pass timing does NOT change.** This package ships a *probe* that measures whether the 5-minute bar is
final 30 s after it closes. Moving the pass to close + 30 s (`on`) is HIS CALL #5, decided on the probe's numbers.

## Why

The 🚩 pass runs on the crontab's `:x1` minute (`1-56/5 4-20 * * 1-5`, `PASS_MINUTE_OFFSET = 1`): it reads the bar that
closed at `:00` / `:05` **60 s** after the close. `BAR_SETTLE_SEC` (30 s) is the closed-bar definition; the other 30 s
is pure wait. Measured (spec §1.4, every pushed live `GG:` A+ since 2026-10-01, n = 47): pass start p50 61.0 s after
the close, phone ring p50 70.6 s. A pass at close + 30 s would take ~30 s off every ring and every lane entry — but
nobody has measured whether the last minute bar is final at + 30 s (the 1-minute page already reads at + 30 s, unmeasured).

## The probe (built, `GAJJALA_BAR_CLOSE_MODE = "probe"`)

- **Spawn.** `run.main`'s CRON path only (no `--dry-run` / `--now` / `--on-demand` / `--symbols` / `--at-bar-close`)
  calls `_spawn_bar_close()` after `_spawn_1m()` and the Luk hook: ONE detached child per invocation —
  `python -m chart_maps.gajjala.run --at-bar-close` through `run_1m._popen` (new session, no inherited descriptors).
  It spawns also when the pass was lease-refused; never in mode `off`. Fenced: one log line
  (`gajjala bar-close: spawned | spawn failed | off … — not spawned | spawn step failed: …`), never changes the exit code.
- **Target.** `bar_close.next_target(now)` = the first 5-minute boundary + `BAR_SETTLE_SEC` strictly after now (ET grid,
  `PASS_CADENCE_SEC`). The 10:01 tick's child aims at 10:05:30; 10:05:30.1 → 10:10:30; 19:58 → 20:00:30.
- **Refusals** (exit 0, one log line `gajjala bar-close: <reason>`, no fetch, no lease, no pass): mode `off`; a closed
  day (`market_hours.gate.closed_reason` — weekend / holiday); a target outside the pass window; woke more than
  `BAR_CLOSE_LATE_MAX_SEC` (= `PASS_MINUTE_OFFSET * 60 − BAR_SETTLE_SEC` = 30 s) after the target (host sleep — the `:x1`
  pass reads that bar anyway); `probe complete — HIS CALL #5` once `gajjala_bar_final` holds
  `GAJJALA_BAR_FINAL_PROBE_SESSIONS` (5) session dates.
- **Read.** Names = `run_1m.names_for(GG5 store, session)` — the house "names that matter most" order, cut at
  `GG1M_MAX_NAMES` (60). At the target: today's minute bars (`load_intraday(…, force=True)`, pre-market and after-hours
  included, Massive spelling, `GAJJALA_BAR_FINAL_PROBE_WORKERS` threads) → `timeframes.resample_ohlcv` to 5 minutes →
  `bars.closed_only(df, wall)` → ONLY the bar right-labelled `target − BAR_SETTLE_SEC` → `at30`. Then sleep to
  `target + PASS_MINUTE_OFFSET·60 − BAR_SETTLE_SEC` (= close + 60 s, the cron pass's own read moment) → the same
  fetch → `at60`. The forming bar is never read (the live-bar overlay trap): a minute stamped after `wall − 30 s`
  lands in a later bucket that `closed_only` drops.
- **Row** `gajjala_bar_final` `_id "{date}|{HH:MM}|{SYM}"` (HH:MM = the bar's right label, ET):
  `{date, symbol, bar_t "YYYY-MM-DD HH:MM", session_part "regular"|"extended", at30 {o,h,l,c,v,read_at},
  at60 {o,h,l,c,v,read_at}, changed, fields_changed [o|h|l|c|v…], v_delta = at60.v − at30.v, at}`.
  `at` = the write time (UTC) — the TTL field (`LEDGER_TTL_DAYS`, 30 d), the house TTL key. Compare is exact (same
  provider both reads). `session_part` = the minute loader's own tag (`rth` → regular, else extended).
- **Failures.** A failed fetch (None, empty, raise, no such closed bar) = no row for that name, never a retry; the
  at60 read is asked only for names whose at30 answered. No lease, no `run_pass`, no push: the ONLY write is
  `gajjala_bar_final`.
- **Cost.** ≤ 2 × `GG1M_MAX_NAMES` = 120 minute-bar fetches per 5 minutes (≈ 24/min) for ≤ 5 sessions, inside the house
  429 breaker; one sleeping child process per slot in the cron container.
- **Critic review 2026-11-09 (fixed):**
  - *Stops for good.* When the 5th session date lands, a `probe_complete` marker doc is written with NO `at` (the
    rows' 30-day TTL never deletes it) and NO `date`; every child reads the marker FIRST. Before: the rows expired after
    30 days, the date count fell to 4 and the probe restarted forever.
  - *Never crowds the real pass.* At most `GAJJALA_BAR_FINAL_PROBE_WORKERS` (2, MINE) fetches at once — the second read
    lands at `:x6:00` beside the cron pass's own ~150-frame fetch (separate process, own 429 breaker). Each row's
    `read_at` stamps say when each name was actually read.
  - *Late second read.* A child that wakes > `BAR_CLOSE_LATE_MAX_SEC` late for the second read skips it: rows carry
    `late: True`, `at60: None`, `changed: None` (never counted as changed). Every row carries `late`.
  - *One child per target.* A pass that ends after `:x5:30` spawns a child aimed at the same target as the previous
    one. The first child upserts `claim|{target UTC ISO}` (`$setOnInsert`, with `at` for the TTL, no `date`); a child that
    finds it refuses (`another child owns this target`); a store error on the claim refuses too (a missed slot costs
    nothing).
- **Served.** WP-E (P4) serves "Bar finality: c of n …" split regular / extended from these rows.

## `on` (HIS CALL #5 only — implemented, tested with the constant patched, NOT shipped)

The child calls `run.run_pass(None, store=ST.default(), deps=run._cron_deps())` — the cron path's own call (one
`_cron_deps()` definition for both), on the wall clock and the CRON lease, never `now=target` (a given clock flips
`run_pass` into replay semantics, `now_given`). The child never spawns another child (no 1-minute loop, no Luk, no
bar-close child). Test pins: `target ≤ cron_start ≤ target + BAR_CLOSE_LATE_MAX_SEC`.

Sequence: 04:01 cron pass + child → 04:05:30 pass → 04:06 tick gap-refused (`LEASE_MIN_GAP_SEC` 240 s) + child →
04:10:30 pass → … → 20:00:30 pass → 20:01 tick refused + child → its 20:05:30 target is refused (outside the window) →
exits. Pass doc ids would read `:x0` / `:x5` instead of `:x1` / `:x6`.

**Fallback.** A dead / late child → no early pass that slot; the next `:x1` tick finds the gap open (last cron start
330 s ago ≥ 240 s) and runs today's pass. Nothing else depends on the child.

## The 1-minute loop arithmetic (read before switching `on`)

`run_1m.fits`: `start + GG1M_MINUTE_BUDGET_SEC (35) + GG1M_SLOT_MARGIN_SEC (20) ≤ next cron tick`. Iterations start on
the `:30` grid (`next_start`), so the last start that fits a 10:01 slot is **10:04:30**, whose bar budget ends by
**10:05:05** — 25 s before a 10:05:30 read (pinned by `test_the_1m_loop_grid_ends_before_the_next_target`).
Correction to the spec's "ends by `:x5:25`": the latest start `fits` admits is `:x6:00 − 55 s = :x5:05`; an iteration
that OVERRAN its minute can start off-grid as late as `:x5:05` and its bar budget then runs to `:x5:40` — past a
`:x5:30` read. The two never share a lease or a collection (GG1 writes `gajjala_1m_*`); the only overlap is REST load
on Massive for those seconds. Any change to the `GG1M_*` budgets must re-check this.

## Words left as is

The served pass-clock words (`potential.pass_times`, `on_demand._ticks`) still name the `:x1` grid. Display only; in
`probe` they are right. If `on` is ever switched, they need a later call.

## Implementation notes (judgement calls, open to veto)

- **The 20:05:30 target.** `run.in_window` truncates to the minute (`20:05 ≤ PASS_CLOSE_ET 20:05`), so
  `in_window(20:05:30)` is **True** — the spec's "20:05:30 `in_window` false" does not hold for the reused function.
  The child therefore also refuses with the 1-minute loop's own extended-close check (`run_1m._after_extended_close`:
  the bar right-labelled 20:05 closes after the 20:00 extended close, `alerts._closes`). No new number; on a half day
  it follows the house early close.
- **No real child under pytest.** (`tests/conftest.py` now also sets `GAJJALA_BAR_CLOSE_MODE=off` for the session.) `bar_close.spawn_child()` with no injected spawn returns False when
  `PYTEST_CURRENT_TEST` is set — every existing `RUN.main([])` test (test_gajjala_run, the 1-minute page, the Luk hook)
  would otherwise fork a real sleeping child. The Luk hook uses `LUK_ENABLED=0` in `tests/conftest.py` instead; an
  equivalent `GAJJALA_BAR_CLOSE_MODE=off` there (env can only lower) would let this guard go.
- **`--at-bar-close`** is dispatched before `main`'s own window check (the child's refusals are on the TARGET, with
  their own words); it ignores `--now` / `--dry-run` / `--symbols` (the cron spawns it with that one flag only).

## Rollout and proof (spec §5.2 step 2)

`./deploy-cheetah-main.sh api cron` between ticks (`:x2`–`:x4`). Proof: `gajjala_bar_final` rows at `:x5:30` /
`:x6:00` for the first RTH slots; pass ids still `:x1` / `:x6`; the `/alerts` 🚩 row fresh as today; the docker log
shows `gajjala bar-close: spawned` after each pass and `gajjala bar-close: probe …` per child.

## HIS CALL (verbatim from the spec §7)

5. **P2 early pass ON?** Built: `probe` (finality measured 5 sessions, pass stays at `:x1`). `on` = the pass at close +
   30 s (≈ 30 s off every ring and lane entry), only after the "Bar finality" line.
6. **`BAR_SETTLE_SEC` 30 s** (the closed-bar definition). Built: unchanged.
7. **Where P2 runs.** Built: cron container, detached child per slot. Alternatives: api-scheduled subprocess; a new
   long-running service.

## Files

`backend/chart_maps/gajjala/bar_close.py` (new) · `backend/chart_maps/gajjala/run.py` (`--at-bar-close`, `_cron_deps`,
`_spawn_bar_close`) · `backend/chart_maps/gajjala/constants.py` (`GAJJALA_BAR_CLOSE_MODE`,
`GAJJALA_BAR_FINAL_PROBE_SESSIONS`, `GAJJALA_BAR_FINAL_PROBE_WORKERS`, `BAR_CLOSE_LATE_MAX_SEC`) · `backend/tests/test_gajjala_bar_close_2026_11_09.py` ·
`backend/tests/test_gajjala_constants.py` (the new names). UNMEASURED until the probe's 5 sessions: an operational
timing, never an outcome.
