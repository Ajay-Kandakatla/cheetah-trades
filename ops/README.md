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

Docker down rules:

- Both backend processes gone and the api down for 2 checks: one `docker_down`,
  and (if allowed) `open -a Docker`. That is the only restart; nothing is ever killed.
- Processes not found but the api answers: no restart, one `watchdog_error` a day
  (a Docker update may have renamed the processes).
- Main process alive but `services` gone: `docker_down` saying quit and reopen
  Docker Desktop; no restart.
- Back: once `/health` answers again, one `docker_restored` with the minutes down.

## Files in `~/.cheetah/watchdog/` (mode 700)

| File | What |
|---|---|
| `state.json` | counters, samples, the pending queue (written atomically) |
| `config.json` | optional settings, see below |
| `paused` | flag file: while it exists the watchdog never restarts Docker (alerts still go out) |
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
| `docker_log_dir` | Docker's `log/host` dir | where `monitor.log` lives |

Unknown keys are ignored and logged. Use `127.0.0.1`, never `localhost`: after
the 2026-10-06 port lock the api answers on IPv4 loopback only.

## Pause and unpause auto-restart

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

- `--dry-run` observes and evaluates and prints `{"obs", "actions"}`. No push,
  restart, notification or state write.
- `--test-push` sends the `test` alert now ("🩺 Ops alert test"); exit 0 when delivered.
- `--status` prints a state summary.
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
