# Docker watchdog (2026-10-06)

`ops/docker_watchdog.py` runs on the Mac (host `/usr/bin/python3`, standard
library only) every 2 minutes under launchd
(`launchd/com.cheetah.docker-watchdog.plist`). Each run is one shot: look, decide,
push, save state, exit.

## Why

On 2026-10-05 Docker's `com.docker.backend` (it owns every published host port)
died, and separately its gvisor network forwarder had piled up about 14,750
"in-progress TCP connections" in 10.5 days. A fresh start holds about 40–65.

The forwarder rule: Docker never retires a flow that the **far side closes
first**. Idle keep-alive sockets that a provider later closed became permanent
entries, about 1,400 a day. The 2026-10-06 leak fix makes Cheetah close idle
connections itself; this watchdog tells Ajay if the count climbs again, or if
Docker's backend dies, so the next one is not found by accident.

## What it watches

| Check | Source | Alert (condition) |
|---|---|---|
| Docker's backend processes | `/bin/ps -axo pid=,lstart=,args=` | `docker_down`, `docker_restored`, `backend_restarted` |
| The api answers | `GET http://127.0.0.1:8000/health` (5 s) | part of `docker_down` / `docker_restored` |
| Forwarder count | tail of `~/Library/Containers/com.docker.docker/Data/log/host/monitor.log` (and the newest rotated `monitor.log.*`) | `forwarder_high`, `forwarder_growth` |
| Battery | `/usr/bin/pmset -g batt` | `battery_low` |
| Cron drift after a sleep | wall clock minus `CLOCK_UPTIME_RAW`; `docker inspect` / `docker top` of `cheetah-market-app-cron-1` | `cron_drift_busy` (and a `docker restart` of the cron container, below) |
| Its own blind spots | the above failing | `watchdog_error` |

Every alert is a web push of kind `ops_alert` (🩺 Docker / host watch on
/notifications, admin only) through `POST http://127.0.0.1:8000/admin/ops/alert`.
While the api is unreachable (Docker down) the push cannot leave the Mac: the
watchdog shows a macOS notification on the first failed try and retries every
15 minutes for 24 hours.

## Thresholds (constants in the script, pinned by tests)

| Constant | Value | Meaning |
|---|---|---|
| `CHECK_INTERVAL_SEC` | 120 | equals the plist `StartInterval` |
| `FORWARDER_ALERT_AT` | 2,000 | two runs in a row at or above it → `forwarder_high` |
| `FORWARDER_REARM_BELOW` | 1,800 | below it the high alert re-arms |
| `FORWARDER_STEP` / `FORWARDER_REPEAT_SEC` | +1,000 / 6 h | repeat while still high |
| `GROWTH_ALERT` | +500 in 24 h | last-hour floor minus the 24 h floor, same backend run, ≥ 1 h of samples |
| `GROWTH_REPEAT_SEC` | 12 h | |
| `DOWN_CHECKS_TO_ACT` | 2 | both backend processes gone AND /health failing, two runs in a row |
| `RESTART_MIN_GAP_SEC` / `RESTART_MAX_PER_DAY` | 15 min / 3 | guards on `open -a Docker` |
| `RETRY_SEC` / `PENDING_TTL_SEC` / `PENDING_MAX` | 15 min / 24 h / 20 | the delivery queue |
| `BATTERY_LEVELS` | 20%, 10% | once each per discharge, re-armed on AC |
| `CRON_RESYNC_AT_SEC` | 120 | summed sleep since the cron container started that triggers a re-sync |
| `CRON_SLEEP_JITTER_SEC` | 5 | per-run wall-minus-uptime noise, not counted |
| `CRON_BUSY_ALERT_SEC` | 30 min | a job keeps cron busy this long → one `cron_drift_busy` |
| `CRON_RESYNC_MIN_GAP_SEC` / `CRON_RESYNC_MAX_PER_DAY` | 10 min / 12 | guards on `docker restart cheetah-market-app-cron-1`; the cap holds only under `CRON_RESYNC_CAP_EXEMPT_SEC` of drift |
| `CRON_RESYNC_CAP_EXEMPT_SEC` | 600 | a drift this large re-syncs past the daily cap (2026-10-21); the gap, the busy wait and the pause file still hold |
| `CRON_STOP_GRACE_SEC` / `CRON_RESTART_TIMEOUT_SEC` | 120 s / 150 s | `docker restart -t 120` (SIGTERM, SIGKILL only after 120 s) / the CLI call's timeout |
| `CRON_EDGE_LEAD_SEC` / `CRON_EDGE_TRAIL_SEC` | 3 / 3 | no restart in second 57–59 or 0–3 of a minute (per-minute jobs start at :00) |

Docker down rules:

- Both backend processes gone and the api down for 2 checks: one `docker_down`,
  and (if allowed) `open -a Docker`. That is the only restart; nothing is ever killed.
- Processes not found but the api answers: no restart, one `watchdog_error` a day
  (a Docker update may have renamed the processes).
- Main process alive but `services` gone: `docker_down` saying quit and reopen
  Docker Desktop; no restart.
- Back: once `/health` answers again, one `docker_restored` with the minutes down.

## Cron re-sync after a sleep (2026-10-11)

While the Mac sleeps, Docker's VM is paused. supercronic (the cron container)
waits on Go monotonic timers, which do not move while the VM is paused, so
**every pending cron job fires late by the total pause** since its timer was
armed. Measured 2026-10-11: cron up 74.6 h of wall time but 52.2 h of VM time
(22.4 h paused); the hourly 11:00 job fired at 21:42 and Monday's whole weekday
schedule (zone_edge, SEPA alerts, the exit engine, the desk report) was due
~21.5 h late. `docker restart cheetah-market-app-cron-1` re-arms every timer
from the wall clock.

What the watchdog does, each run:

1. Sleep: it saves `time.time()` and `time.clock_gettime(CLOCK_UPTIME_RAW)`
   (seconds since boot, not counting sleep). Next run, `slept = wall delta −
   uptime delta`; more than `CRON_SLEEP_JITTER_SEC` (5 s) is added to
   `cron_sleep_acc_sec` in `state.json`. Not `time.monotonic()`: on the host's
   Python 3.9.6 it restarts near 0 in every new process (measured 0.0056 s), and
   launchd starts a new process every run, so every awake run would count ~120 s
   as sleep. Measured 2026-10-11: 52.70 h of uptime vs 75.10 h of wall time since
   boot = the real 22.4 h pause. Uptime or wall going backwards (a reboot, a clock
   change) only moves the baseline; an unavailable clock counts as 0 sleep.
2. Identity: `docker inspect` gives the cron container's `State.StartedAt`. A new
   value (a deploy, a manual or Docker restart) starts the drift over at this
   interval's sleep (a deploy, then the lid closes: that night still counts),
   re-arms the busy alert and drops a pending `cron_drift_busy`.
3. When the drift is at least `CRON_RESYNC_AT_SEC` (120 s): `docker top` must
   show only `docker-init` and `supercronic`. If a job is running it waits (it
   never interrupts a job) and, after `CRON_BUSY_ALERT_SEC` (30 min) of waiting,
   sends ONE `cron_drift_busy` push naming the drift and the running command; it
   re-arms after a successful re-sync or a new cron `StartedAt`.
4. Idle: `docker restart -t 120 cheetah-market-app-cron-1` (150 s timeout), never
   in second 57–59 or 0–3 of a wall-clock minute (read just before the restart;
   inside that window it waits in-process until second 4, at most 7 s, because
   launchd keeps each run on about the same second; if the clock still reads the
   edge it defers to the next run, not counted toward the caps). `-t 120` overrides
   the container's 1 s stop timeout: Docker sends SIGTERM, tini forwards it to
   supercronic, which stops scheduling and waits for a running job before it
   exits (supercronic README: SIGTERM is a graceful shutdown; main.go
   `wg.Wait()` after the signal; jobs run via `exec.Command` in their own
   process group, so the job itself gets no signal). At most one
   per `CRON_RESYNC_MIN_GAP_SEC` (10 min); `CRON_RESYNC_MAX_PER_DAY` (12) per
   24 h holds only while the drift is under `CRON_RESYNC_CAP_EXEMPT_SEC`
   (600 s). The cap is for a flapping host. 2026-10-21: twelve short wake-ups
   overnight used it up, then a 3 h 04 min pause (11,044 s) met `cap` on 40
   consecutive runs, supercronic ran every job 3 h 05 min late and the in-session
   alert jobs (SEPA alerts, tape_control, demand_alerts, the Auto-Pilot tick) had
   not started by 11:50 ET. So a sleep of ten minutes or more always re-syncs,
   past the cap, still behind the gap, the busy wait and the pause file; the
   attempt is counted (`resyncs_24h` stays honest) and `cron_resynced_past_cap`
   is logged beside `cron_resynced`. Success: drift back to 0, the new
   `StartedAt` stored, no push (it happens at every wake). Failure: logged, one
   `watchdog_error` a day, the drift is kept and the next allowed run tries
   again (past the cap that means every gap until it succeeds, not 12 times).

Docker CLI trouble (the container missing or stopped, `docker` failing, an
unreadable `docker top`): no action, one log line a day per reason, no push.

Turn it off: `"cron_resync": false` in `config.json`, or the `paused` flag file
(which also stops `open -a Docker`).

Reading the log:

```bash
grep -E 'cron_resynced|cron resync failed|drift reset' ~/.cheetah/watchdog/watchdog.log | tail -5
```

- `"msg": "cron_resynced", "drift_sec": 80640.0, "drift_h": 22.4, "started_at": "…"`:
  the cron container was restarted after 22.4 h of summed sleep.
- `"msg": "cron_resynced_past_cap", "drift_sec": 11044.0, "resyncs_24h": 13, "cap": 12,
  "exempt_sec": 600`: that re-sync went through although the day's cap was used
  up, because the drift was at least `CRON_RESYNC_CAP_EXEMPT_SEC`. A
  `"cron resync failed"` line carries `past_cap` too.
- `"msg": "cron container restarted; drift reset"`: someone else restarted it
  (deploy or by hand); `dropped_sec` is the drift that restart cleared,
  `kept_sec` the sleep of that same interval, which still counts.
- every `"msg": "run"` line carries `cron_drift_sec` and `cron` (the decision:
  `in_sync`, `busy`, `resync`, `edge` (skipped at a minute boundary), `off`,
  `paused`, `gap`, `cap`, `no_cron`, `not_running`, `no_top`).

## Files in `~/.cheetah/watchdog/` (mode 700)

| File | What |
|---|---|
| `state.json` | counters, samples, the pending queue (written atomically) |
| `config.json` | optional settings, see below |
| `paused` | flag file: while it exists the watchdog never restarts Docker or the cron container (alerts still go out) |
| `watchdog.log` | JSON lines, rotated to `watchdog.log.1` past 1 MB |
| `lock` | one run at a time |
| `launchd.out.log` / `launchd.err.log` | launchd's stdout / stderr |

## `config.json`

```json
{"admin_email": "<push.hooks.ADMIN_EMAIL>", "auto_restart": true}
```

| Key | Default | Meaning |
|---|---|---|
| `admin_email` | none | sent as `X-User-Email`; without it no push is attempted |
| `api_base` | `http://127.0.0.1:8000` | must be `http://127.0.0.1:` or `http://[::1]:`; anything else is refused |
| `auto_restart` | `true` | `false` = never run `open -a Docker` |
| `cron_resync` | `true` | `false` = never restart the cron container after a sleep |
| `docker_log_dir` | Docker's `log/host` dir | where `monitor.log` lives |

Unknown keys are ignored and logged. Use `127.0.0.1`, never `localhost`: after
the 2026-10-06 port lock the api answers on IPv4 loopback only.

## Pause and unpause auto-restart (Docker and the cron re-sync)

```bash
touch ~/.cheetah/watchdog/paused
```

```bash
rm ~/.cheetah/watchdog/paused
```

## Manual runs

```bash
/usr/bin/python3 /Users/ajay/clinet-test/cheetah-deploy/ops/docker_watchdog.py --dry-run
```

```bash
/usr/bin/python3 /Users/ajay/clinet-test/cheetah-deploy/ops/docker_watchdog.py --test-push
```

```bash
/usr/bin/python3 /Users/ajay/clinet-test/cheetah-deploy/ops/docker_watchdog.py --status
```

- `--dry-run` observes and evaluates and prints `{"obs", "actions", "cron"}`
  (`cron` = the drift, the decision, re-syncs in 24 h). No push, restart,
  notification or state write; `docker top` (a read) runs when the drift is due.
- `--test-push` sends the `test` alert now ("🩺 Ops alert test"); exit 0 when delivered.
- `--status` prints a state summary, with the same `cron` block.
- `--state-dir PATH` uses another state directory.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | an alert is still pending (not delivered yet) |
| 2 | Docker's log could not be read (permission or I/O) |
| 3 | unexpected exception: traceback in `watchdog.log`, a Mac notification at most once a day |

## macOS log access

Docker's log sits under `~/Library/Containers/com.docker.docker`. macOS may ask
whether `python3` may "access data from other apps" the first time the job
reads it (INFERRED: expected, not yet seen). Click Allow. If the log shows
`permission` (exit 2, a "Docker watchdog is blind" push), the other option is
Full Disk Access for `/usr/bin/python3` in System Settings → Privacy & Security.
That is a security setting and Ajay's call.

## Where it runs from

The plist points at `/Users/ajay/clinet-test/cheetah-deploy/ops/docker_watchdog.py`,
the deploy worktree. The script therefore exists only after a main deploy, and a
deploy rewrites it in place (a run that overlaps a deploy may fail once; harmless).
A main deploy does not install or reload the launchd job.

## Install

```bash
mkdir -p ~/.cheetah/watchdog
chmod 700 ~/.cheetah/watchdog
cp /Users/ajay/clinet-test/cheetah-deploy/launchd/com.cheetah.docker-watchdog.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cheetah.docker-watchdog.plist
```

```bash
launchctl print gui/$(id -u)/com.cheetah.docker-watchdog | grep -E 'state|last exit code'
tail -3 ~/.cheetah/watchdog/watchdog.log
```

## Uninstall

```bash
launchctl bootout gui/$(id -u)/com.cheetah.docker-watchdog
rm ~/Library/LaunchAgents/com.cheetah.docker-watchdog.plist
```

Tests: `backend/tests/test_docker_watchdog.py` (watchdog), `backend/tests/test_ops_alert.py`
(the push kind and `/admin/ops/alert`).
