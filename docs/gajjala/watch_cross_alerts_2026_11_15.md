# 👀 Gajjala's Watch — the minute loop and the 1-minute 9/21 EMA cross push (2026-11-15)

Ajay, verbatim: "I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and add remove
tickers from the dashboard. When I add a ticker I need 1 min 3 min and 5 min charts... Not the SEPA and I need clear
distinction or may be a brighter and thicker 21 EMA and 9 EMA, from the videos I notice that when ever 9 EMA crosses over
21 EMA on uptrend is where the bullish momentum started I need alerts on these from 1 min to I can be ready... I think the
cross over is slow but once it picks up its very rapid.."

This page covers the backend half that reads the bars and rings the phone (spec WP-B). The owner list, the routes and
the GET payload are in `watch_dashboard_2026_11_15.md`. The board is in `watch_frontend_2026_11_15.md`.

**UNMEASURED.** No study measures a 9/21 EMA cross on any frame. A cross is information, never an entry. Every push body
ends "UNMEASURED — information only, not an entry".

## Code

| File | What |
|---|---|
| `backend/chart_maps/gajjala/bars.py` | additive: `RULE_OF["3m"] = "3min"`; `build_frames(rules=)` / `frames_for(rules=, per_name=)`. With neither keyword every GG byte is unchanged (sha256 pins in `test_gajjala_watch_build_2026_11_15.py`). |
| `backend/chart_maps/gajjala_watch/build.py` | the frames (`frames_for(rules=C.FRAMES)`), one tile per frame (bars from 04:00, 9/21 curves, cross marks from `tab.ema_cross_block`, K5 at the latest bar, the 04:00 axis), the tile writes |
| `backend/chart_maps/gajjala_watch/cross_alerts.py` | the cross push, the ℹ️ line |
| `backend/chart_maps/gajjala_watch/loop.py` | the minute loop, the `--build` child, the CLI |
| `backend/chart_maps/gajjala/run.py` | `_spawn_watch()` + one call at the START of the cron path |
| `backend/supply_demand/rules_info.py` | `_gg_watch_cross_clause()` in the 🚩 section note |
| `ops/docker_watchdog.py` | the loop's argv in `CRON_DETACHED_CHILD_ARGS` (4 argv) |
| `backend/scripts/gajjala_watch_cross_count.py` | read-only frequency counts for HIS CALL #3 / #4 / #5 / #16 |

ONE engine: the 9 and 21 EMAs are the house `orderflow.signals.ema` through `bars._masked_ema`. The crosses come from
`ema_cross` and the lease from `chart_maps.gajjala.store`. K5 is `detectors.uptrend`. A source guard test fails on any
`.ewm(`, `signals.ema(`, `_masked_ema(` or `find_one_and_update` inside `gajjala_watch/`, and on any comparison that
names `ema9` or `ema21`.

## The clock

```
cron tick T (":01, :06, …", the 🚩 pass)
  run.main ── in window, cron path ──► _spawn_watch()  (detached, BEFORE the store / lease / run_pass)
                                         │
  loop:  start = max(spawn, T + 0:30)    │  a late spawn (T + 0:34) runs at once and reads the bar that closed at T
         T+0:30  T+1:30  T+2:30  T+3:30  T+4:30      (each reads the 1-min bar that closed 30 s earlier)
         ends: start + 0:30 > T+5:00 ("no time left in the slot")
               the bar to read closes after the extended close (20:00; 17:00 on a half day)
               after a sleep the wall clock is in another slot, or more than 30 s past the planned
               start ("slot passed (host sleep)")
               the watch is off
  each iteration: claim lease (GG1's 55 s / gap 0, `gajjala_watch_state` _id "lease")
                  → owner list → frames (budget min(35 s, time left in the slot)) → cross push → tile docs
                  → state doc "latest" → release
  a held lease skips THAT minute (`skipped`), never ends the loop
  loop end → state doc "loop" {tick, n, skipped, reason, ended_at}
```

An empty list claims no lease and fetches nothing (`reason: "no tickers"`). A failed, over-budget or no-print read
`$set`s only `{symbol, at, status}`. The last good charts stay and are served stale.

The `--build` child (spawned by the API when a name is added and the loop will not read it within the minute) builds
every listed name that has no tile doc, a tile from another session, or a tile that is not loaded. It re-reads the list
after each round and tries each name once. It never pushes, writes no state doc and takes no lease.

CLI: `--loop` | `--build` | `--dry-run` | `--now ISO` | `--symbols A,B`. `--now` or `--symbols` without `--dry-run`
refuses (exit 2). With `--dry-run`, `--symbols` replaces the owner list for that run, and nothing is written or sent
(loads through `run._dry_load_day`).

## Gate order (each refusal is counted; the `held` chip records the verdict of the cross minute)

| # | Check | Counted as | `held` chip |
|---|---|---|---|
| 1 | latest UP cross of the session in `watch_crosses(F)` = `ema_cross.frame_crosses(F)` minus today's first bar (the chart never marks that bar) | `cross` | — |
| 2 | frame not in `C.PUSH_FRAMES` (1m) or not in `alerts.FRAME_MINUTES` (fail closed) | `not_push_frame` | never |
| 3 | `C.PUSH_MODE` not "live" | `off` | own minute only |
| 4 | not its own minute (the cross bar is not the latest closed bar, or older than 90 s = `max_entry_age_sec(GG1)`) | `claimed_before` (claim on file) · `missed_fetch` (fresh, but the last good read never held the bar) · `late` | `missed_fetch` only |
| 5 | closed day (`alerts._closed_reason`) | `suppressed_closed` | yes |
| 6 | the A+ push window (`alerts.window_reason`): pre-market, 09:30–09:45, after the extended close | `suppressed_premarket` / `suppressed_first15` / `suppressed_window` | yes |
| 7 | GG's session-volume floor (`K11_MIN_SESSION_VOLUME`, 1,000,000 on `bars.session_volume`; unknown → held) | `under_floor` | yes |
| 8 | `C.UPTREND_FILTER` (default None = no filter; K5 recorded on the claim) | `not_uptrend` | yes |
| 9 | dry | `dry` | never |
| 10 | no alert store | `no_store` (never a claim-less send) | yes |
| 11 | insert-only claim `GGW:{date}|{SYM}|{frame}` in `gajjala_watch_alerts` (never `gajjala_alerts`, never `GG:`) BEFORE the send | `claimed_before` | never |
| 12 | send (owner-scoped, kind `gajjala_potential`) → `cross_pushed` / `cross_no_target` / `cross_failed` | `pushed` / `no_target` / `failed` | yes |

The payload has no `items`, so the /alerts row links the stored `url` `/chart-maps?tab=gajjala_watch&focus=SYM`.

## What never rings

- A cross UNDER (bearish): drawn, never pushed (HIS CALL #8).
- A 3-min or 5-min cross: drawn only (HIS CALL #2).
- Pre-market, 09:30–09:45, after the extended close, a closed day, under 1,000,000 shares.
- A second up cross the same session on the same ticker and frame (the latch, below).
- A cross on today's first bar (04:01 / 04:03 / 04:05; pre-market anyway).

## The missed-cross loss (never sent late)

The latest-bar rule is kept. If the minute that should read the cross bar fails, the cross is lost. Causes: a Massive
timeout (6 s) or the open breaker, an over-budget name, a held lease, or host sleep. The next minute sees it as
"latest − 1". It is counted `missed_fetch` (the last good read's `seen_bar_t` is older than the cross bar) and chipped
on the tile. It is never sent late. Accepting the bar before the latest while it is still fresh (≤ 90 s) is HIS CALL
#20, and it would loosen the latest-bar gate.

## The latch consequence (HIS CALL #4, word for word)

"With no trend filter and once a session, the FIRST 1-min up cross after 09:45 uses that ticker's one ring for the day —
even a small pop inside a down-trend. A later real up-trend cross the same day does NOT ring (`claimed_before`); it is
still drawn on the chart."

K5 needs both EMAs higher than 3 bars ago, which a first cross rarely shows yet. So a K5 default would hold most first
crosses. The options in code are `C.UPTREND_FILTERS`: `k5_cross_frame` and `k5_5m`. Run
`scripts/gajjala_watch_cross_count.py` to get the counts for the linked question #3 / #4 / #5.

## The ➖ Fade double ring (HIS CALL #19)

A watched name that is also on a ➖ Horizontal Fade card can ring twice on the same kind: `ggx-horizontal_fade-SYM` from
the Fade's 15- or 5-min frame, and `ggw-1m-SYM` from the watch's 1-min frame. The ℹ️ line says so.

## Watchdog

`ops/docker_watchdog.py` `CRON_DETACHED_CHILD_ARGS` gains `("-m", "chart_maps.gajjala_watch.loop", "--loop")`. Without
it, the loop would keep cron "busy" from 04:00 to 20:00, and the host-sleep re-sync would never fire (the 2026-11-09
three-hours-late incident). C38 pins the set to the backends' own argv constants (4 argv). `--build` runs in the api
container and is not exempt. A restart while the loop runs costs at most one slot (one minute read per name per minute
left). The next pass re-spawns it. The watchdog runs on the host from the repo tree, so it picks up the change at its
next launchd run (no deploy step).

## Cost

Twelve names (the `MAX_SYMBOLS` cap) cost 12 today-minute fetches a minute, about 1.8 s of wall time at 0.149 s per
name, which is one fifth of `GG1M_MAX_NAMES`. A name also on GG1's list is fetched twice. No WebSocket is used.
Measured (critique C2): one tile doc is about 210 KB of BSON, and Mongo writes are about 2.52 MB a minute (12 docs
overwritten).

## Counts script

```bash
docker exec -i -w /app <scratch api container> python -m scripts.gajjala_watch_cross_count --symbols OMH,NVDA,AMD --sessions 5 --json
```

Read-only (no cache write). Per name-session and frame, it reports: up crosses; how many fall pre-market, in the first
15 minutes or after the extended close; how many pass K5 on the cross frame and on 5-min; the latch-loss sessions; and
the same-minute bursts. It outputs medians and p90. These are frequencies only, not an edge.

## Tests

`backend/tests/test_gajjala_watch_build_2026_11_15.py`, `test_gajjala_watch_cross_2026_11_15.py`,
`test_gajjala_watch_loop_2026_11_15.py`, `test_gajjala_watch_hook_2026_11_15.py`; `test_docker_watchdog.py` C37/C38;
`tests/conftest.py` assigns `GAJJALA_WATCH_ENABLED=0` for the session.
`test_gajjala_watch_refix_2026_11_15.py` (the refix below).

## Refix 2026-11-15 (critic round)

- **The tick+4:30 iteration was lost on every slot.** The post-sleep check was `wall + 30 s > next tick`. A real
  `time.sleep` always wakes a few ms late, so at tick+4:30 that test was always true and the loop ended — the bar
  that closes at each :x0 / :x5 was never read as the latest bar, a cross on it was counted `missed_fetch`, and the
  loop state doc said "slot passed (host sleep)" with n = 4. The check after the sleep is now: the wall clock is in
  another slot, or more than `BAR_SETTLE_SEC` (30 s) past the planned start. The pre-sleep check (`start + 30 s >
  next tick` → "no time left in the slot") is unchanged. Tests: a clock that wakes 1 ms – 5 s late keeps 5
  iterations; NEGATIVES: a wake 31 s late inside the slot, or in the next slot, ends the loop; never a 6th iteration.
- **Off now stops the `--build` child.** With `GAJJALA_WATCH_ENABLED=0` an add no longer requests a build child, and
  `--build` / `build_pending` return `reason: "off"` without a minute fetch.
