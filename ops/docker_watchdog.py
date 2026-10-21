"""Cheetah host watchdog for Docker Desktop (2026-10-06). One run per call; launchd
schedules it every CHECK_INTERVAL_SEC (launchd/com.cheetah.docker-watchdog.plist).

Why it exists. On 2026-10-05 Docker's com.docker.backend (it owns every published
host port) died, and separately its gvisor network forwarder had piled up ~14,750
"in-progress TCP connections" in 10.5 days (a fresh start holds about 40-65). The
forwarder never retires a flow the far side closes first, so idle keep-alive
sockets that a provider closed became permanent entries. Nothing told Ajay.

What it watches, each run:
  * Docker's backend processes (``/bin/ps``) and the api's ``/health``;
  * the forwarder count in Docker's own ``monitor.log`` (high, and growth);
  * the Mac's battery (``/usr/bin/pmset``) — a sleeping Mac stops every scan;
  * how long the Mac slept (wall clock minus ``CLOCK_UPTIME_RAW``, the boot-relative
    clock that does not advance during sleep) since the cron container started.
    Not ``time.monotonic()``: on the host's Python 3.9 it restarts near 0 in every
    new process, and launchd starts a new process every run.

What it does: queues an alert, POSTs it to the api's ``/admin/ops/alert``
(loopback only), retries every RETRY_SEC for up to PENDING_TTL_SEC, and shows a
local macOS notification on the first failed try. When both backend processes
are gone AND the api is down it may run ``open -a Docker`` (guarded: config flag,
pause file, a 15-minute gap, 3 per day).

Cron re-sync (2026-10-11). While the Mac sleeps Docker's VM is paused, and
supercronic's timers (Go monotonic) do not advance, so every pending cron job
fires late by the total pause since its timer was armed (measured 2026-10-11:
22.4 h of pause, Monday's whole weekday schedule ~21.5 h late). Once the summed
sleep since the cron container started reaches CRON_RESYNC_AT_SEC, and ``docker
top`` shows only docker-init + supercronic (no job running), it runs ``docker
restart -t 120 cheetah-market-app-cron-1``, which re-arms every timer from the
wall clock (guarded: config flag ``cron_resync``, the pause file, a 10-minute
gap, 12 per day, and never within 3 s either side of a wall-clock minute, when
the per-minute jobs start). A running job is never interrupted: it waits, and
after CRON_BUSY_ALERT_SEC of waiting it sends one ``cron_drift_busy`` alert.

The daily cap is for a flapping host (2026-10-21): twelve short wake-ups
overnight used it up, then a 3 h 04 min pause (11,044 s) met ``cap`` on 40
consecutive runs and every in-session alert job ran 3 h late. So the cap applies
only while the summed drift is under CRON_RESYNC_CAP_EXEMPT_SEC (600 s): a longer
sleep always re-syncs, past the cap, still behind the gap, the busy wait and the
pause file, and logs ``cron_resynced_past_cap`` beside ``cron_resynced``. A
``docker restart`` that keeps failing at a large drift therefore retries every
gap until it succeeds (one ``watchdog_error`` a day), not 12 times.

It never kills anything: it sends no signal itself, and the one container it
restarts is restarted only while no cron job runs. ``-t 120`` overrides the
container's 1 s stop timeout: Docker sends SIGTERM, tini (docker-init) forwards
it to supercronic, and supercronic stops scheduling and waits for any job that
slipped in to finish before it exits; SIGKILL comes only after 120 s.

Standard library only; must run under the host's /usr/bin/python3 (3.9.6).
Runbook: ops/README.md. Tests: backend/tests/test_docker_watchdog.py.
"""
from __future__ import annotations

import argparse
import calendar
import copy
import fcntl
import glob
import json
import os
import re
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants (pinned by backend/tests/test_docker_watchdog.py)
# ---------------------------------------------------------------------------
CHECK_INTERVAL_SEC = 120            # == the plist StartInterval
FORWARDER_ALERT_AT = 2000           # Ajay's number; fresh VM 39-64, 10.5-day leak ~14,750
FORWARDER_CONFIRM_READS = 2         # two consecutive runs >= the line
FORWARDER_REARM_BELOW = 1800        # 10% hysteresis
FORWARDER_STEP = 1000               # re-alert at each further +1,000
FORWARDER_REPEAT_SEC = 6 * 3600     # or every 6 h while still high
GROWTH_WINDOW_SEC = 24 * 3600
GROWTH_ALERT = 500                  # pre-fix 500-1,400/day; post-fix should be ~0
GROWTH_FLOOR_SEC = 3600             # "now" = min of the last hour
GROWTH_MIN_SPAN_SEC = 3600
GROWTH_REPEAT_SEC = 12 * 3600
SAMPLE_EVERY_SEC = 600
SAMPLE_KEEP_SEC = 26 * 3600
STALE_LINE_TOLERANCE_SEC = 120
DOWN_CHECKS_TO_ACT = 2
RESTART_MIN_GAP_SEC = 900
RESTART_MAX_PER_DAY = 3
RETRY_SEC = 900                     # 4 tries/h < the server's 6/h cap
CRON_RESYNC_AT_SEC = 120            # summed sleep since cron started that triggers a re-sync
CRON_SLEEP_JITTER_SEC = 5           # per-run wall-minus-monotonic noise; not sleep
CRON_BUSY_ALERT_SEC = 1800          # a job has kept cron busy this long -> one alert
CRON_RESYNC_MIN_GAP_SEC = 600
CRON_RESYNC_MAX_PER_DAY = 12        # a flapping host; holds only under CRON_RESYNC_CAP_EXEMPT_SEC
CRON_RESYNC_CAP_EXEMPT_SEC = 600    # drift this large re-syncs past the daily cap (2026-10-21)
CRON_STOP_GRACE_SEC = 120           # `docker restart -t`: SIGTERM, then SIGKILL after this
CRON_RESTART_TIMEOUT_SEC = 150      # the CLI call; > CRON_STOP_GRACE_SEC
CRON_EDGE_LEAD_SEC = 3              # no restart in second 57..59 of a minute ...
CRON_EDGE_TRAIL_SEC = 3             # ... or 0..3 (per-minute jobs start at :00)
CRON_CMD_MAX = 80                   # the running command, clipped, in the busy alert
PENDING_TTL_SEC = 24 * 3600
PENDING_MAX = 20
BATTERY_LEVELS = (20, 10)
WATCHDOG_ERROR_REPEAT_SEC = 24 * 3600
LOG_TAIL_BYTES = 1048576            # a whole rotated file
ROTATED_MAX_FILES = 3
OWN_LOG_MAX_BYTES = 1000000
TITLE_MAX = 80
BODY_MAX = 280

CONDITIONS = frozenset({
    "forwarder_high", "forwarder_growth", "docker_down", "docker_restored",
    "backend_restarted", "battery_low", "watchdog_error", "cron_drift_busy", "test"})
DOCKER_CLI = "/usr/local/bin/docker"
CRON_CONTAINER = "cheetah-market-app-cron-1"
ALLOWED_BINARIES = frozenset({"/bin/ps", "/usr/bin/pmset", "/usr/bin/osascript", "/usr/bin/open",
                              DOCKER_CLI})

DEFAULT_API_BASE = "http://127.0.0.1:8000"   # not localhost: IPv6-first, refused after the lock
ALERT_PATH = "/admin/ops/alert"
DOCKER_LOG_DIR = os.path.expanduser("~/Library/Containers/com.docker.docker/Data/log/host")
STATE_DIR = os.path.expanduser("~/.cheetah/watchdog")

STATE_VERSION = 1
_DAY = 24 * 3600
_CONFIG_KEYS = ("admin_email", "api_base", "auto_restart", "cron_resync", "docker_log_dir")
_CONFIG_BOOLS = ("auto_restart", "cron_resync")
_CRON_IDLE_PROCS = ("docker-init", "supercronic")
_BACKEND_NAME = "com.docker.backend"
_UI_MARK = "/Docker Desktop.app/Contents/MacOS/Docker Desktop"

# ---------------------------------------------------------------------------
# Pure parsers
# ---------------------------------------------------------------------------
_FWD_COMPONENT = '"component":"gvisor/forwarder"'
_FWD_COUNT = re.compile(r"\((\d+) (?:remaining )?in-progress TCP connections\)")
_FWD_STAMP = re.compile(r"^\[(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.\d+)?Z\]")


def parse_forwarder(text: str) -> Optional[Tuple[int, float]]:
    """(count, utc_epoch) of the LAST valid forwarder line in ``text``, or None."""
    last = None  # type: Optional[Tuple[int, float]]
    for line in (text or "").splitlines():
        if _FWD_COMPONENT not in line:
            continue
        m = _FWD_COUNT.search(line)
        if not m:
            continue
        s = _FWD_STAMP.match(line)
        if not s:
            continue
        try:
            ts = float(calendar.timegm(time.strptime(s.group(1), "%Y-%m-%dT%H:%M:%S")))
        except ValueError:
            continue
        last = (int(m.group(1)), ts)
    return last


def _tail_text(path: str, nbytes: int) -> str:
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        start = max(0, size - nbytes)
        f.seek(start)
        data = f.read(nbytes)
    text = data.decode("utf-8", "replace")
    if start > 0:                       # the first line is cut: drop it
        nl = text.find("\n")
        text = text[nl + 1:] if nl >= 0 else ""
    return text


def read_forwarder(log_dir: str) -> dict:
    """Latest forwarder count: the tail of monitor.log, else the newest rotated files."""
    out = {"count": None, "ts": None, "source": None, "error": None}
    try:
        if not os.path.isdir(log_dir):
            out["error"] = "missing"
            return out
        live = os.path.join(log_dir, "monitor.log")
        has_live = os.path.exists(live)
        if has_live:
            hit = parse_forwarder(_tail_text(live, LOG_TAIL_BYTES))
            if hit is not None:
                out.update(count=hit[0], ts=hit[1], source="monitor.log")
                return out
        rotated = sorted(glob.glob(os.path.join(glob.escape(log_dir), "monitor.log.*")),
                         reverse=True)[:ROTATED_MAX_FILES]
        for path in rotated:
            hit = parse_forwarder(_tail_text(path, LOG_TAIL_BYTES))
            if hit is not None:
                out.update(count=hit[0], ts=hit[1], source=os.path.basename(path))
                return out
        out["error"] = "no_line" if has_live else "missing"
    except PermissionError:
        out["error"] = "permission"
    except OSError:
        out["error"] = "io"
    return out


def parse_ps(text: str) -> dict:
    """Docker's backend processes from ``ps -axo pid=,lstart=,args=`` (LC_ALL=C).

    INFERRED classification (verified on the host before install, SPEC C6):
    argv[0] basename ``com.docker.backend`` + argv[1] ``services`` = services;
    no argv[1], or a flag, = main; any other subcommand is ignored."""
    out = {"main": [], "services": [], "ui": False}  # type: dict
    for line in (text or "").splitlines():
        parts = line.split(None, 6)
        if len(parts) < 7:
            continue
        try:
            pid = int(parts[0])
            start = time.mktime(time.strptime(" ".join(parts[1:6]), "%a %b %d %H:%M:%S %Y"))
        except (ValueError, OverflowError):
            continue
        args = parts[6]
        if _UI_MARK in args:
            out["ui"] = True
        argv = args.split()
        if not argv or os.path.basename(argv[0]) != _BACKEND_NAME:
            continue
        if len(argv) == 1 or argv[1].startswith("-"):
            out["main"].append((pid, start))
        elif argv[1] == "services":
            out["services"].append((pid, start))
    return out


_PCT = re.compile(r"(\d{1,3})%;")


def parse_pmset(text: str) -> dict:
    """``pmset -g batt`` -> {on_ac, percent}; percent None on a Mac with no battery."""
    on_ac = None  # type: Optional[bool]
    pct = None  # type: Optional[int]
    m = re.search(r"Now drawing from '([^']+)'", text or "")
    if m:
        on_ac = m.group(1) == "AC Power"
    for line in (text or "").splitlines():
        if "InternalBattery" in line:
            p = _PCT.search(line)
            if p:
                pct = int(p.group(1))
                break
    return {"on_ac": on_ac, "percent": pct}


def parse_cron_inspect(text: str) -> dict:
    """``docker inspect -f '{{.State.StartedAt}} {{.State.Running}}'`` -> {started_at, running}."""
    parts = (text or "").split()
    if len(parts) != 2 or parts[1] not in ("true", "false") or "T" not in parts[0]:
        return {"started_at": None, "running": None, "error": "unparsed"}
    return {"started_at": parts[0], "running": parts[1] == "true", "error": None}


def parse_docker_top(text: str) -> Optional[List[str]]:
    """``docker top <c> -o pid,args`` -> the args of each process, or None when no
    process line is there (an empty list is not proof the scheduler is idle)."""
    procs = []  # type: List[str]
    for i, line in enumerate((text or "").splitlines()):
        parts = line.split(None, 1)
        if i == 0 and parts and parts[0] == "PID":
            continue                    # the header
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        procs.append(parts[1].strip())
    return procs or None


def cron_busy_procs(procs: List[str]) -> List[str]:
    """Every process that is not the idle scheduler (docker-init / supercronic)."""
    busy = []
    for args in procs:
        argv = args.split()
        if not argv or os.path.basename(argv[0]) not in _CRON_IDLE_PROCS:
            busy.append(args)
    return busy


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1] + "\u2026"


def _dur(sec) -> str:
    sec = float(sec or 0)
    return f"{sec / 3600.0:.1f} h" if sec >= 3600 else f"{int(round(sec / 60.0))} min"


def _hhmm(ts: Optional[float]) -> str:
    if ts is None:
        return "?"
    return time.strftime("%H:%M %Z", time.localtime(ts))


def compose(condition: str, facts: dict) -> Tuple[str, str]:
    """(title, body) for one alert, clipped to TITLE_MAX / BODY_MAX."""
    f = facts or {}
    if condition == "forwarder_high":
        n = int(f.get("n", 0))
        title = f"\U0001FA7A Docker forwarder at {n:,} flows"
        body = (f"Docker's network forwarder holds {n:,} open flows (alert line "
                f"{FORWARDER_ALERT_AT:,}; a fresh start holds about 40\u201365). It grows when a "
                "connection is closed by the far side first. Restart Docker Desktop after "
                "the close to reset it.")
    elif condition == "forwarder_growth":
        g, h, n = int(f.get("g", 0)), int(f.get("h", 0)), int(f.get("n", 0))
        title = f"\U0001FA7A Docker forwarder +{g:,} in {h} h"
        body = (f"The forwarder grew +{g:,} in {h} h (alert line +{GROWTH_ALERT:,} in 24 h) to "
                f"{n:,} flows. The 2026-10-06 leak fix should hold this near flat; check the "
                "api's CLOSE_WAIT sockets.")
    elif condition == "docker_down":
        title = "\U0001F6D1 Docker is down"
        if f.get("variant") == "services":
            body = ("Docker's services process is gone while its main process still runs. "
                    "Cheetah's api, cron and alerts are down. Quit and reopen Docker Desktop; "
                    "the watchdog does not restart this case.")
        else:
            body = (f"Docker's backend is not running (seen {int(f.get('k', 0))} checks in a row "
                    f"since {_hhmm(f.get('since'))}). Cheetah's api, cron and alerts are down. "
                    f"{f.get('outcome') or 'No restart tried'}.")
    elif condition == "docker_restored":
        title = "\u2705 Docker is back"
        body = (f"Docker was down about {int(f.get('m', 0)):,} min ({_hhmm(f.get('t0'))}\u2013"
                f"{_hhmm(f.get('t1'))}); the api answers /health. Restart attempts: "
                f"{int(f.get('k', 0))}.")
    elif condition == "backend_restarted":
        title = "\U0001F504 Docker backend restarted"
        body = (f"Docker's backend restarted at {_hhmm(f.get('t'))} (new process). The "
                "forwarder count starts over. Check the site loads.")
    elif condition == "battery_low":
        p = int(f.get("p", 0))
        title = f"\U0001F50B Mac battery {p}%"
        lvl = f.get("level")
        under = f" (under {int(lvl)}%)" if lvl is not None else ""
        body = (f"The Mac is on battery at {p}%{under}. When it sleeps, Cheetah's scans and "
                "alerts stop. Plug it in.")
    elif condition == "watchdog_error":
        title = "\u26A0\uFE0F Docker watchdog is blind"
        impact = f.get("impact") or ("It cannot see the forwarder count until this is fixed "
                                     "(see ops/README.md).")
        body = f"{f.get('reason') or 'The watchdog hit an error'}. {impact}"
    elif condition == "cron_drift_busy":
        title = f"\u23F0 Cron jobs {_dur(f.get('drift'))} late"
        body = (f"The Mac slept, so every cron job (alerts, exits, scans) fires about "
                f"{_dur(f.get('drift'))} late. The watchdog re-syncs cron only while no job runs; "
                f"one has run {_dur(f.get('waited'))}: {f.get('cmd') or '?'}. It keeps trying "
                "every 2 min (ops/README.md).")
    elif condition == "test":
        title = "\U0001FA7A Ops alert test"
        body = "Test from the Docker watchdog: ops alerts reach this device."
    else:
        raise ValueError(f"unknown condition {condition!r}")
    return _clip(title, TITLE_MAX), _clip(body, BODY_MAX)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
def default_state() -> dict:
    return {
        "version": STATE_VERSION,
        "run_id": None,             # "pid:start" of the services process last seen
        "services_start": None,
        "last_count": None,         # previous run's forwarder reading (this backend run)
        "alerted_count": None,      # forwarder_high: count at the last alert (None = armed)
        "alerted_at": None,
        "samples": [],              # [[epoch, count]] of this backend run, <= 1 per 10 min
        "growth_alerted_at": None,
        "down": {"checks": 0, "since": None, "alerted": False, "attempts": 0, "variant": None},
        "restarts": [],             # epochs of `open -a Docker`
        "battery_fired": [],
        "error_alerted_at": {},     # watchdog_error reason key -> epoch
        "crash_notified_at": None,
        "pending": [],
        # cron re-sync (2026-10-11); a version-1 file without these keys loads with
        # these defaults, so STATE_VERSION stays 1
        "last_wall": None,          # previous run's time.time() ...
        "last_mono": None,          # ... and CLOCK_UPTIME_RAW (stops while the Mac sleeps)
        "cron_started_at": None,    # the cron container's State.StartedAt last seen
        "cron_sleep_acc_sec": 0.0,  # summed sleep since that start
        "cron_busy_since": None,    # first run that found a job running with drift due
        "cron_busy_alerted": False,
        "cron_resyncs": [],         # epochs of `docker restart` attempts (the caps)
        "cron_last_resync": None,   # {"ts", "drift_sec"} of the last successful one
        "cron_last_decision": None,
        "cron_logged_at": {},       # log-once key -> epoch
    }


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _coerce_state(raw) -> Optional[dict]:
    if not isinstance(raw, dict) or raw.get("version") != STATE_VERSION:
        return None
    st = default_state()
    for k, v in st.items():
        if k in raw and (raw[k] is None or v is None or isinstance(raw[k], type(v))):
            st[k] = raw[k]
    d = default_state()["down"]
    d.update({k: v for k, v in (st.get("down") or {}).items() if k in d})
    st["down"] = d
    for k in ("last_wall", "last_mono", "cron_busy_since"):
        if st[k] is not None and not _num(st[k]):
            st[k] = None
    if not _num(st["cron_sleep_acc_sec"]) or st["cron_sleep_acc_sec"] < 0:
        st["cron_sleep_acc_sec"] = 0.0
    st["cron_sleep_acc_sec"] = float(st["cron_sleep_acc_sec"])
    if st["cron_started_at"] is not None and not isinstance(st["cron_started_at"], str):
        st["cron_started_at"] = None
    if not isinstance(st["cron_resyncs"], list):
        st["cron_resyncs"] = []
    st["cron_resyncs"] = [t for t in st["cron_resyncs"] if _num(t)]
    if not isinstance(st["error_alerted_at"], dict):    # a hand-edited null crashed _error_once
        st["error_alerted_at"] = {}
    if not isinstance(st["cron_logged_at"], dict):
        st["cron_logged_at"] = {}
    st["cron_logged_at"] = {k: v for k, v in st["cron_logged_at"].items() if _num(v)}
    lr = st["cron_last_resync"]
    if lr is not None and not (isinstance(lr, dict) and _num(lr.get("ts"))):
        st["cron_last_resync"] = None
    return st


def load_state(state_dir: str) -> Optional[dict]:
    """The saved state, or None when it is missing or corrupt (evaluate starts fresh)."""
    try:
        with open(os.path.join(state_dir, "state.json"), "r", encoding="utf-8") as f:
            return _coerce_state(json.load(f))
    except (OSError, ValueError):
        return None


def save_state(state_dir: str, state: dict) -> None:
    """Write state.json atomically: a temp file in the same dir, then os.replace."""
    path = os.path.join(state_dir, "state.json")
    tmp = os.path.join(state_dir, f".state.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def log_line(state_dir: str, level: str, msg: str, **extra) -> None:
    """Append one JSON line to watchdog.log (rotated to .1 past OWN_LOG_MAX_BYTES). Never raises."""
    try:
        path = os.path.join(state_dir, "watchdog.log")
        if os.path.exists(path) and os.path.getsize(path) > OWN_LOG_MAX_BYTES:
            os.replace(path, path + ".1")
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "level": level, "msg": msg}
        rec.update(extra)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except Exception:
        pass


def load_config(state_dir: str) -> Tuple[dict, List[str]]:
    """config.json merged over the defaults -> (cfg, notes to log)."""
    cfg = {"admin_email": None, "api_base": DEFAULT_API_BASE, "auto_restart": True,
           "cron_resync": True, "docker_log_dir": DOCKER_LOG_DIR, "state_dir": state_dir}
    notes = []  # type: List[str]
    path = os.path.join(state_dir, "config.json")
    if not os.path.exists(path):
        return cfg, notes
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as exc:
        notes.append(f"config.json unreadable ({type(exc).__name__}); using defaults")
        return cfg, notes
    if not isinstance(raw, dict):
        notes.append("config.json is not an object; using defaults")
        return cfg, notes
    for k, v in raw.items():
        if k not in _CONFIG_KEYS:
            notes.append(f"config.json: unknown key {k!r} ignored")
            continue
        if k in _CONFIG_BOOLS and not isinstance(v, bool):
            notes.append(f"config.json: {k} must be true/false; kept the default")
            continue
        if k not in _CONFIG_BOOLS and not isinstance(v, str):
            notes.append(f"config.json: {k} must be a string; kept the default")
            continue
        cfg[k] = os.path.expanduser(v) if k == "docker_log_dir" else v
    return cfg, notes


# ---------------------------------------------------------------------------
# Pure core
# ---------------------------------------------------------------------------
def _queue(st: dict, condition: str, facts: dict, now: float) -> None:
    title, body = compose(condition, facts)
    # the queue length makes the id unique inside one run (critic 2026-10-06: two
    # watchdog_error items queued in the same second shared an id, so delivering
    # one dropped the other); runs are CHECK_INTERVAL_SEC apart, so int(now) differs
    st["pending"].append({"id": f"{condition}:{int(now)}:{len(st['pending'])}",
                          "condition": condition,
                          "title": title, "body": body, "created_at": now,
                          "last_try_at": None, "tries": 0})


def _error_once(st: dict, key: str, reason: str, now: float, impact: Optional[str] = None) -> None:
    last = st["error_alerted_at"].get(key)
    if last is None or now - last >= WATCHDOG_ERROR_REPEAT_SEC:
        st["error_alerted_at"][key] = now
        facts = {"reason": reason}
        if impact:
            facts["impact"] = impact
        _queue(st, "watchdog_error", facts, now)


def _restart_block(st: dict, cfg: dict, paused: bool, now: float) -> Optional[str]:
    """None when a restart is allowed now, else the outcome sentence for the body."""
    recent = [t for t in st["restarts"] if now - t < _DAY]
    if not cfg.get("auto_restart", True):
        return "auto-restart off"
    if paused:
        return "auto-restart paused (flag file)"
    if len(recent) >= RESTART_MAX_PER_DAY:
        return f"auto-restart gave up after {RESTART_MAX_PER_DAY} tries in 24 h"
    if recent and now - max(recent) < RESTART_MIN_GAP_SEC:
        return f"auto-restart waits (last try {_hhmm(max(recent))})"
    return None


def _reset_forwarder(st: dict) -> None:
    st["last_count"] = None
    st["alerted_count"] = None
    st["alerted_at"] = None
    st["samples"] = []
    st["growth_alerted_at"] = None


def _log_once(st: dict, actions: List[dict], key: str, msg: str, now: float, **extra) -> None:
    """A log action at most once per WATCHDOG_ERROR_REPEAT_SEC per key (no push)."""
    last = st["cron_logged_at"].get(key)
    if last is None or now - last >= WATCHDOG_ERROR_REPEAT_SEC:
        st["cron_logged_at"][key] = now
        actions.append(dict({"type": "log", "msg": msg}, **extra))


def _cron_account(st: dict, obs: dict, now: float, actions: List[dict]) -> None:
    """Add this interval's sleep to cron_sleep_acc_sec. A new cron container
    (deploy, manual or Docker restart) starts the drift over at this interval's
    sleep (deploy, then the lid closes: that night's drift counts) and re-arms the
    busy alert. An unknown clock (``mono`` None) counts as 0 sleep."""
    mono = obs.get("mono")
    slept_now = 0.0
    if _num(mono):
        lw, lm = st["last_wall"], st["last_mono"]
        if lw is not None and lm is not None:
            if mono < lm or now < lw:
                # a reboot (monotonic restarts near 0) or the wall clock set back:
                # this interval says nothing about sleep, so only the baseline moves
                actions.append({"type": "log", "msg": "clock re-baselined",
                                "reason": "monotonic went back" if mono < lm else "wall clock went back"})
            else:
                slept = (now - lw) - (mono - lm)
                if slept > CRON_SLEEP_JITTER_SEC:
                    slept_now = float(slept)
                    st["cron_sleep_acc_sec"] = float(st["cron_sleep_acc_sec"]) + slept_now
        st["last_wall"], st["last_mono"] = now, float(mono)
    cron = obs.get("cron") or {}
    started = cron.get("started_at")
    if cron.get("error") is None and isinstance(started, str) and started:
        if st["cron_started_at"] != started:
            if st["cron_started_at"] is not None:
                actions.append({"type": "log", "msg": "cron container restarted; drift reset",
                                "from": st["cron_started_at"], "to": started,
                                "dropped_sec": round(st["cron_sleep_acc_sec"] - slept_now),
                                "kept_sec": round(slept_now)})
            st["cron_started_at"] = started
            st["cron_sleep_acc_sec"] = slept_now
            st["cron_busy_since"] = None
            st["cron_busy_alerted"] = False
            st["pending"] = [p for p in st["pending"] if p.get("condition") != "cron_drift_busy"]


def _cron_pre(st: dict, obs: dict, cfg: dict, now: float) -> Optional[str]:
    """The cron decision when it is settled before ``docker top``; None = look at top."""
    cron = obs.get("cron") or {}
    if cron.get("error") is not None or not cron.get("started_at"):
        return "no_cron"
    if cron.get("running") is not True:
        return "not_running"
    if st["cron_sleep_acc_sec"] < CRON_RESYNC_AT_SEC:
        return "in_sync"
    if cfg.get("cron_resync", True) is False:
        return "off"
    if obs.get("paused"):
        return "paused"
    recent = [t for t in st["cron_resyncs"] if now - t < _DAY]
    # the daily cap holds only for small drifts (a flapping host); a drift of
    # CRON_RESYNC_CAP_EXEMPT_SEC or more goes past it (2026-10-21), gap still held
    if (len(recent) >= CRON_RESYNC_MAX_PER_DAY
            and st["cron_sleep_acc_sec"] < CRON_RESYNC_CAP_EXEMPT_SEC):
        return "cap"
    if recent and now - max(recent) < CRON_RESYNC_MIN_GAP_SEC:
        return "gap"
    return None


def _cron_evaluate(st: dict, obs: dict, cfg: dict, now: float, actions: List[dict]) -> None:
    _cron_account(st, obs, now, actions)
    cron = obs.get("cron") or {}
    decision = _cron_pre(st, obs, cfg, now)
    if decision in ("no_cron", "not_running"):
        _log_once(st, actions, decision, "cron container not usable; no re-sync", now,
                  error=cron.get("error") or decision)
    top = cron.get("top") or {}
    if decision is None:
        procs = top.get("procs")
        if top.get("error") is not None or not procs:
            decision = "no_top"
            _log_once(st, actions, "no_top", "docker top unusable; no re-sync", now,
                      error=top.get("error") or "no process lines")
        else:
            busy = cron_busy_procs(procs)
            if busy:
                decision = "busy"
                if st["cron_busy_since"] is None:
                    st["cron_busy_since"] = now
                waited = now - st["cron_busy_since"]
                if waited > CRON_BUSY_ALERT_SEC and not st["cron_busy_alerted"]:
                    st["cron_busy_alerted"] = True
                    _queue(st, "cron_drift_busy", {"drift": st["cron_sleep_acc_sec"],
                                                   "waited": waited,
                                                   "cmd": _clip(busy[0], CRON_CMD_MAX)}, now)
            else:
                decision = "resync"
                recent = [t for t in st["cron_resyncs"] if now - t < _DAY]
                # every attempt counts, past the cap too: resyncs_24h stays honest
                st["cron_resyncs"] = recent + [now]
                actions.append({"type": "cron_resync",
                                "drift_sec": round(st["cron_sleep_acc_sec"], 1),
                                "past_cap": len(recent) >= CRON_RESYNC_MAX_PER_DAY,
                                "resyncs_24h": len(recent) + 1})
    if decision != "busy":
        st["cron_busy_since"] = None
    st["cron_last_decision"] = decision


def cron_wants_top(state: Optional[dict], obs: dict, now: float, cfg: dict) -> bool:
    """True when this run's cron decision needs ``docker top`` (pure; state untouched)."""
    st = _coerce_state(copy.deepcopy(state)) if state is not None else None
    st = st or default_state()
    _cron_account(st, obs, now, [])
    return _cron_pre(st, obs, cfg, now) is None


def record_cron_deferred(state: dict, now: float) -> dict:
    """The restart was skipped (minute edge): the attempt does not count toward the
    gap or the cap, and the drift stays for the next run."""
    state["cron_resyncs"] = [t for t in state["cron_resyncs"] if t != now]
    state["cron_last_decision"] = "edge"
    return state


def record_cron_resync(state: dict, ok: bool, drift_sec: float, started_at: Optional[str],
                       error: Optional[str], now: float) -> dict:
    """After ``docker restart``: success zeroes the drift and re-arms the busy alert;
    a failure keeps the drift (the next allowed run tries again) and alerts once."""
    if ok:
        state["cron_sleep_acc_sec"] = 0.0
        state["cron_started_at"] = started_at
        state["cron_last_resync"] = {"ts": now, "drift_sec": round(float(drift_sec), 1)}
        state["cron_busy_since"] = None
        state["cron_busy_alerted"] = False
        state["pending"] = [p for p in state["pending"] if p.get("condition") != "cron_drift_busy"]
    else:
        _error_once(state, "cron_resync", f"Cron re-sync failed ({error or 'unknown error'})", now,
                    impact=f"Cron jobs still fire about {_dur(drift_sec)} late; it retries in "
                           f"{CRON_RESYNC_MIN_GAP_SEC // 60} min (see ops/README.md).")
    return state


def evaluate(state: Optional[dict], obs: dict, now: float, cfg: dict) -> Tuple[dict, List[dict]]:
    """(new state, actions). Pure: no I/O; actions are push / restart / cron_resync / log dicts."""
    actions = []  # type: List[dict]
    st = _coerce_state(copy.deepcopy(state)) if state is not None else None
    if st is None:
        st = default_state()
        actions.append({"type": "log", "msg": "state missing or corrupt; starting fresh"})

    docker = obs.get("docker") or {}
    derr = docker.get("error")
    main = list(docker.get("main") or [])
    services = list(docker.get("services") or [])
    api_ok = bool(obs.get("api_ok"))
    paused = bool(obs.get("paused"))
    down = st["down"]

    # -- run identity -------------------------------------------------------
    if derr is None and services:
        run_id = f"{int(services[0][0])}:{int(services[0][1])}"
        prev = st["run_id"]
        if prev is not None and prev != run_id:
            _reset_forwarder(st)
            if not down["alerted"]:
                _queue(st, "backend_restarted", {"t": services[0][1]}, now)
            actions.append({"type": "log", "msg": "backend run changed", "from": prev, "to": run_id})
        st["run_id"] = run_id
        st["services_start"] = float(services[0][1])

    # -- Docker liveness ----------------------------------------------------
    if derr is not None:
        actions.append({"type": "log", "msg": "ps failed; liveness skipped", "error": derr})
    elif not main and not services and api_ok:
        _error_once(st, "procs", "can't find Docker's processes by name; the api still answers", now)
    elif main and not services and api_ok:
        # critic 2026-10-06: the api answering means Docker is up; a renamed
        # 'services' subcommand must not push "Docker is down", and the forwarder
        # count (keyed to the services process) is not being watched — say so
        _error_once(st, "services", "can't find Docker's 'services' process by name; the api "
                    "still answers, so the forwarder count is not being watched", now)
    elif (not main and not services) or (main and not services):
        variant = "backend" if not main else "services"
        down["checks"] += 1
        if down["since"] is None:
            down["since"] = now
        if down["checks"] >= DOWN_CHECKS_TO_ACT:
            outcome = None  # type: Optional[str]
            if variant == "backend" and not api_ok:
                block = _restart_block(st, cfg, paused, now)
                if block is None:
                    actions.append({"type": "restart"})
                    st["restarts"] = [t for t in st["restarts"] if now - t < _DAY] + [now]
                    down["attempts"] += 1
                    outcome = f"opened Docker at {_hhmm(now)}"
                else:
                    outcome = block
            if not down["alerted"]:
                down["alerted"] = True
                down["variant"] = variant
                _queue(st, "docker_down", {"variant": variant, "k": down["checks"],
                                           "since": down["since"], "outcome": outcome}, now)
    else:
        if down["alerted"]:
            if api_ok:
                since = down["since"] if down["since"] is not None else now
                _queue(st, "docker_restored", {"m": round((now - since) / 60.0), "t0": since,
                                               "t1": now, "k": down["attempts"]}, now)
                st["pending"] = [p for p in st["pending"] if p.get("condition") != "docker_down"]
                st["down"] = default_state()["down"]
        else:
            st["down"] = default_state()["down"]
    down = st["down"]

    # -- forwarder ------------------------------------------------------------
    fwd = obs.get("forwarder") or {}
    ferr = fwd.get("error")
    if ferr == "permission":
        _error_once(st, "log", "macOS blocks reading Docker's log (permission)", now)
    elif ferr == "io":
        _error_once(st, "log", "Docker's log could not be read (I/O error)", now)
    elif ferr in ("no_line", "missing"):
        actions.append({"type": "log", "msg": "no forwarder reading", "error": ferr})

    count = fwd.get("count")
    if derr is None and services and count is not None:
        count = int(count)
        ts = fwd.get("ts")
        sstart = st["services_start"]
        if ts is not None and sstart is not None and ts < sstart - STALE_LINE_TOLERANCE_SEC:
            actions.append({"type": "log", "msg": "forwarder line predates this backend run",
                            "count": count})
        else:
            prev = st["last_count"]
            st["last_count"] = count
            if count < FORWARDER_REARM_BELOW:
                st["alerted_count"] = None
                st["alerted_at"] = None
            if count >= FORWARDER_ALERT_AT and prev is not None and prev >= FORWARDER_ALERT_AT:
                ac, at = st["alerted_count"], st["alerted_at"]
                if (ac is None or count >= ac + FORWARDER_STEP
                        or (at is not None and now - at >= FORWARDER_REPEAT_SEC)):
                    st["alerted_count"] = count
                    st["alerted_at"] = now
                    _queue(st, "forwarder_high", {"n": count}, now)
            samples = [s for s in st["samples"] if now - s[0] <= SAMPLE_KEEP_SEC]
            if not samples or now - samples[-1][0] >= SAMPLE_EVERY_SEC:
                samples.append([now, count])
            st["samples"] = samples
            window = [s for s in samples if s[0] >= now - GROWTH_WINDOW_SEC]
            if window:
                base = min(c for _t, c in window)
                recent = min(c for t, c in samples + [[now, count]] if t >= now - GROWTH_FLOOR_SEC)
                span = now - min(t for t, _c in window)
                ga = st["growth_alerted_at"]
                if (recent - base > GROWTH_ALERT and span >= GROWTH_MIN_SPAN_SEC
                        and (ga is None or now - ga >= GROWTH_REPEAT_SEC)):
                    st["growth_alerted_at"] = now
                    _queue(st, "forwarder_growth", {"g": recent - base,
                                                    "h": max(1, int(round(span / 3600.0))),
                                                    "n": count}, now)

    # -- battery --------------------------------------------------------------
    bat = obs.get("battery") or {}
    if bat.get("on_ac") is False and bat.get("percent") is not None:
        pct = int(bat["percent"])
        crossed = [lv for lv in BATTERY_LEVELS if pct < lv and lv not in st["battery_fired"]]
        if crossed:
            _queue(st, "battery_low", {"p": pct, "level": min(crossed)}, now)
            st["battery_fired"] = sorted(set(st["battery_fired"]) | set(crossed), reverse=True)
    elif bat.get("on_ac") is True:
        st["battery_fired"] = []

    # -- cron drift (2026-10-11) -----------------------------------------------
    _cron_evaluate(st, obs, cfg, now, actions)

    # -- pending queue --------------------------------------------------------
    kept = []
    for p in st["pending"]:
        if now - p.get("created_at", now) > PENDING_TTL_SEC:
            actions.append({"type": "log", "msg": "pending alert expired", "id": p.get("id")})
        else:
            kept.append(p)
    kept.sort(key=lambda p: p.get("created_at", 0))
    while len(kept) > PENDING_MAX:
        gone = kept.pop(0)
        actions.append({"type": "log", "msg": "pending queue full; dropped oldest", "id": gone.get("id")})
    st["pending"] = kept
    for p in kept:
        if p.get("last_try_at") is None or now - p["last_try_at"] >= RETRY_SEC:
            actions.append({"type": "push", "id": p["id"], "condition": p["condition"],
                            "title": p["title"], "body": p["body"]})
    return st, actions


def record_delivery(state: dict, item_id: str, delivered: bool, now: float) -> Tuple[dict, bool]:
    """Delivered -> drop the item. Else count the try; notify locally on the FIRST failure."""
    notify = False
    kept = []
    for p in state.get("pending", []):
        if p.get("id") != item_id:
            kept.append(p)
            continue
        if delivered:
            continue
        p["tries"] = int(p.get("tries", 0)) + 1
        p["last_try_at"] = now
        notify = p["tries"] == 1
        kept.append(p)
    state["pending"] = kept
    return state, notify


# ---------------------------------------------------------------------------
# Side effects
# ---------------------------------------------------------------------------
def _run(argv, timeout=20):
    if not argv or argv[0] not in ALLOWED_BINARIES:
        raise ValueError(f"watchdog refuses to run {argv[:1]}")
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, "LC_ALL": "C"}, check=False)


def notify_local(title: str, body: str) -> None:
    """A macOS notification. Text rides as argv, never inside the script."""
    try:
        _run(["/usr/bin/osascript", "-e", "on run argv",
              "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
              "-e", "end run", title, body])
    except Exception:
        pass


def restart_docker() -> None:
    """The only restart there is: reopen Docker Desktop. Nothing is ever killed."""
    _run(["/usr/bin/open", "-a", "Docker"], timeout=30)


def inspect_cron() -> dict:
    """The cron container's State.StartedAt / Running. Never raises."""
    try:
        r = _run([DOCKER_CLI, "inspect", "-f", "{{.State.StartedAt}} {{.State.Running}}",
                  CRON_CONTAINER])
    except Exception as exc:
        return {"started_at": None, "running": None, "error": f"inspect {type(exc).__name__}"}
    if r.returncode != 0:
        missing = "no such" in (r.stderr or "").lower()
        return {"started_at": None, "running": None,
                "error": "missing" if missing else f"inspect exit {r.returncode}"}
    return parse_cron_inspect(r.stdout)


def top_cron() -> dict:
    """The cron container's processes (``docker top``). Never raises."""
    try:
        r = _run([DOCKER_CLI, "top", CRON_CONTAINER, "-o", "pid,args"])
    except Exception as exc:
        return {"procs": None, "error": f"top {type(exc).__name__}"}
    if r.returncode != 0:
        return {"procs": None, "error": f"top exit {r.returncode}"}
    return {"procs": parse_docker_top(r.stdout), "error": None}


def cron_minute_edge(wall: float) -> bool:
    """True in second 57..59 or 0..3 of a wall-clock minute: a per-minute job may be
    starting, so no restart now."""
    sec = int(wall) % 60
    return sec >= 60 - CRON_EDGE_LEAD_SEC or sec <= CRON_EDGE_TRAIL_SEC


def cron_edge_wait(wall: float) -> float:
    """Seconds to wait in-process until second CRON_EDGE_TRAIL_SEC + 1 when ``wall`` is
    in the minute edge (at most 7 s), else 0. launchd keeps every run on about the same
    second, so deferring to the next run could skip for ~25 min after a wake."""
    if not cron_minute_edge(wall):
        return 0.0
    sec = int(wall) % 60
    target = CRON_EDGE_TRAIL_SEC + 1
    return float((60 - sec + target) if sec > CRON_EDGE_TRAIL_SEC else (target - sec))


_sleep = time.sleep                 # patched by the tests


def restart_cron() -> None:
    """Re-arm supercronic's timers: restart the (idle) cron container. ``-t`` gives a
    job that slipped in CRON_STOP_GRACE_SEC after SIGTERM (supercronic waits for it)
    instead of the container's 1 s. Raises on failure."""
    r = _run([DOCKER_CLI, "restart", "-t", str(CRON_STOP_GRACE_SEC), CRON_CONTAINER],
             timeout=CRON_RESTART_TIMEOUT_SEC)
    if r.returncode != 0:
        raise RuntimeError(f"docker restart exit {r.returncode}: "
                           f"{_clip((r.stderr or '').strip(), 120)}")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):   # noqa: D401
        return None                     # the admin header never follows a redirect


def _plain_opener(*extra):
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect(), *extra)


def _is_loopback_base(api_base: str) -> bool:
    if not (api_base.startswith("http://127.0.0.1:") or api_base.startswith("http://[::1]:")):
        return False
    try:
        parts = urllib.parse.urlsplit(api_base)
        return parts.hostname in ("127.0.0.1", "::1") and parts.username is None
    except ValueError:
        return False


def _api_ok(api_base: str, opener=None) -> bool:
    try:
        op = opener or _plain_opener()
        resp = op.open(api_base.rstrip("/") + "/health", timeout=5)
        try:
            return resp.getcode() == 200
        finally:
            resp.close()
    except Exception:
        return False


def uptime_raw() -> Optional[float]:
    """Seconds since boot, not counting sleep (macOS CLOCK_UPTIME_RAW); None when the
    clock is unavailable. Never ``time.monotonic()``: on Python 3.9 it restarts near 0
    in every new process."""
    try:
        return float(time.clock_gettime(time.CLOCK_UPTIME_RAW))
    except (AttributeError, OSError):
        return None


def observe(cfg: dict, now: float) -> dict:
    """One look at the host. Each step's failure lands in an error field."""
    mono = uptime_raw()                 # first, next to the caller's ``now``
    docker = {"main": [], "services": [], "ui": False, "error": None}  # type: dict
    try:
        r = _run(["/bin/ps", "-axo", "pid=,lstart=,args="])
        if r.returncode != 0:
            docker["error"] = f"ps exit {r.returncode}"
        else:
            docker.update(parse_ps(r.stdout))
    except Exception as exc:
        docker["error"] = f"ps {type(exc).__name__}"
    try:
        forwarder = read_forwarder(cfg.get("docker_log_dir") or DOCKER_LOG_DIR)
    except Exception:
        forwarder = {"count": None, "ts": None, "source": None, "error": "io"}
    battery = {"on_ac": None, "percent": None}  # type: dict
    try:
        r = _run(["/usr/bin/pmset", "-g", "batt"])
        if r.returncode == 0:
            battery = parse_pmset(r.stdout)
    except Exception:
        pass
    api_base = cfg.get("api_base") or DEFAULT_API_BASE
    api_ok = _api_ok(api_base) if _is_loopback_base(api_base) else False
    state_dir = cfg.get("state_dir") or STATE_DIR
    try:
        cron = inspect_cron()
    except Exception as exc:
        cron = {"started_at": None, "running": None, "error": f"inspect {type(exc).__name__}"}
    return {"docker": docker, "forwarder": forwarder, "battery": battery,
            "api_ok": api_ok, "paused": os.path.exists(os.path.join(state_dir, "paused")),
            "mono": mono, "cron": cron}


def _add_cron_top(state: Optional[dict], obs: dict, now: float, cfg: dict, top_fn) -> None:
    """``docker top`` only when the drift is due and nothing else blocks a re-sync."""
    if not cron_wants_top(state, obs, now, cfg):
        return
    try:
        top = top_fn()
    except Exception as exc:
        top = {"procs": None, "error": f"top {type(exc).__name__}"}
    obs["cron"] = dict(obs.get("cron") or {}, top=top)


def deliver(item: dict, cfg: dict, opener=None) -> dict:
    """POST one alert to the api. Delivered ONLY on 200 with delivered: true."""
    api_base = (cfg.get("api_base") or DEFAULT_API_BASE).rstrip("/")
    if not _is_loopback_base(api_base + "/"):
        return {"delivered": False, "status": None, "reason": "api_base_not_loopback"}
    email = cfg.get("admin_email")
    if not isinstance(email, str) or not email.strip():
        return {"delivered": False, "status": None, "reason": "no_admin_email"}
    data = json.dumps({"condition": item["condition"], "title": item["title"],
                       "body": item["body"]}).encode("utf-8")
    req = urllib.request.Request(api_base + ALERT_PATH, data=data, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "X-User-Email": email.strip()})
    op = opener or _plain_opener()
    try:
        resp = op.open(req, timeout=10)
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            exc.close()
        except Exception:
            pass
        return {"delivered": False, "status": status, "reason": f"http_{status}"}
    except Exception as exc:
        return {"delivered": False, "status": None, "reason": f"error_{type(exc).__name__}"}
    try:
        status = resp.getcode()
        raw = resp.read(65536)
    finally:
        try:
            resp.close()
        except Exception:
            pass
    try:
        js = json.loads(raw.decode("utf-8") or "{}")
    except ValueError:
        js = {}
    ok = status == 200 and isinstance(js, dict) and js.get("delivered") is True
    reason = "delivered" if ok else (str(js.get("skipped") or js.get("error") or "not_delivered")
                                     if isinstance(js, dict) else "not_delivered")
    return {"delivered": ok, "status": status, "reason": reason}


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------
def _ensure_dir(state_dir: str) -> None:
    if not os.path.isdir(state_dir):
        os.makedirs(state_dir, mode=0o700, exist_ok=True)
        os.chmod(state_dir, 0o700)


def run_once(cfg: dict, now: float, *, observe_fn=None, deliver_fn=None, notify_fn=None,
             restart_fn=None, state_dir: Optional[str] = None, cron_top_fn=None,
             cron_restart_fn=None, cron_inspect_fn=None, clock_fn=None) -> int:
    """One full run. Exit: 0 ok, 1 an alert still pending, 2 Docker's log unreadable,
    3 unexpected (traceback logged, a local notification at most once per 24 h)."""
    observe_fn = observe_fn or observe
    deliver_fn = deliver_fn or deliver
    notify_fn = notify_fn or notify_local
    restart_fn = restart_fn or restart_docker
    cron_fns = (cron_top_fn or top_cron, cron_restart_fn or restart_cron,
                cron_inspect_fn or inspect_cron, clock_fn or time.time)
    state_dir = state_dir or cfg.get("state_dir") or STATE_DIR
    _ensure_dir(state_dir)
    fd = os.open(os.path.join(state_dir, "lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            log_line(state_dir, "info", "another run holds the lock; exiting")
            return 0
        try:
            return _run_locked(cfg, now, observe_fn, deliver_fn, notify_fn, restart_fn, state_dir,
                               cron_fns)
        except Exception:
            log_line(state_dir, "error", "unexpected exception", tb=traceback.format_exc())
            try:
                st = load_state(state_dir) or default_state()
                last = st.get("crash_notified_at")
                if last is None or now - last >= _DAY:
                    notify_fn("\u26A0\uFE0F Docker watchdog crashed",
                              "The Docker watchdog hit an unexpected error; see "
                              "~/.cheetah/watchdog/watchdog.log.")
                    st["crash_notified_at"] = now
                    save_state(state_dir, st)
            except Exception:
                pass
            return 3
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _run_locked(cfg, now, observe_fn, deliver_fn, notify_fn, restart_fn, state_dir,
                cron_fns=(top_cron, restart_cron, inspect_cron, time.time)) -> int:
    cron_top_fn, cron_restart_fn, cron_inspect_fn, clock_fn = cron_fns
    state = load_state(state_dir)
    obs = observe_fn(cfg, now)
    _add_cron_top(state, obs, now, cfg, cron_top_fn)
    state, actions = evaluate(state, obs, now, cfg)
    for a in actions:
        if a["type"] == "restart":
            try:
                restart_fn()
                log_line(state_dir, "warning", "opened Docker Desktop")
            except Exception as exc:
                log_line(state_dir, "error", "restart failed", error=type(exc).__name__)
        elif a["type"] == "cron_resync":
            # the wall clock NOW, not the run's start: observe can take seconds
            wait = cron_edge_wait(clock_fn())
            if wait:
                _sleep(wait)
            if cron_minute_edge(clock_fn()):
                state = record_cron_deferred(state, now)
                continue
            err = None  # type: Optional[str]
            try:
                cron_restart_fn()
            except Exception as exc:
                err = str(exc) or type(exc).__name__
            started = None  # type: Optional[str]
            if err is None:
                try:
                    started = (cron_inspect_fn() or {}).get("started_at")
                except Exception:
                    started = None      # the next run stores it (acc is 0 either way)
            state = record_cron_resync(state, err is None, a["drift_sec"], started, err, now)
            if err is None:
                log_line(state_dir, "warning", "cron_resynced", drift_sec=a["drift_sec"],
                         drift_h=round(a["drift_sec"] / 3600.0, 2), started_at=started)
                if a.get("past_cap"):
                    log_line(state_dir, "warning", "cron_resynced_past_cap",
                             drift_sec=a["drift_sec"], resyncs_24h=a.get("resyncs_24h"),
                             cap=CRON_RESYNC_MAX_PER_DAY, exempt_sec=CRON_RESYNC_CAP_EXEMPT_SEC)
            else:
                log_line(state_dir, "error", "cron resync failed", drift_sec=a["drift_sec"],
                         error=_clip(err, 200), past_cap=bool(a.get("past_cap")))
        elif a["type"] == "push":
            try:
                res = deliver_fn(a, cfg)
            except Exception as exc:
                res = {"delivered": False, "status": None, "reason": f"error_{type(exc).__name__}"}
            state, notify = record_delivery(state, a["id"], bool(res.get("delivered")), now)
            log_line(state_dir, "info" if res.get("delivered") else "warning", "push",
                     id=a["id"], status=res.get("status"), reason=res.get("reason"))
            if notify:
                try:
                    notify_fn(a["title"], a["body"])
                except Exception:
                    pass
        elif a["type"] == "log":
            extra = {k: v for k, v in a.items() if k not in ("type", "msg")}
            log_line(state_dir, "info", a.get("msg", ""), **extra)
    code = 0
    if state["pending"]:
        code = 1
    if (obs.get("forwarder") or {}).get("error") in ("permission", "io"):
        code = max(code, 2)
    save_state(state_dir, state)
    d = obs.get("docker") or {}
    log_line(state_dir, "info", "run", exit=code,
             main=len(d.get("main") or []), services=len(d.get("services") or []),
             ps_error=d.get("error"), api_ok=obs.get("api_ok"),
             forwarder=(obs.get("forwarder") or {}).get("count"),
             cron_drift_sec=round(state["cron_sleep_acc_sec"]), cron=state["cron_last_decision"],
             pending=len(state["pending"]), actions=[a["type"] for a in actions])
    return code


def _cron_summary(st: dict, now: float) -> dict:
    return {"started_at": st["cron_started_at"],
            "sleep_acc_sec": round(st["cron_sleep_acc_sec"], 1),
            "resync_at_sec": CRON_RESYNC_AT_SEC,
            "cap_exempt_sec": CRON_RESYNC_CAP_EXEMPT_SEC,
            "decision": st["cron_last_decision"],
            "busy_since": st["cron_busy_since"], "busy_alerted": st["cron_busy_alerted"],
            "resyncs_24h": len([t for t in st["cron_resyncs"] if now - t < _DAY]),
            "last_resync": st["cron_last_resync"]}


def dry_run(cfg: dict, now: float, observe_fn=None, state_dir: Optional[str] = None,
            cron_top_fn=None) -> dict:
    """Observe + evaluate only: no push, restart, notification or state write
    (``docker top`` is a read and runs when the drift is due)."""
    observe_fn = observe_fn or observe
    state_dir = state_dir or cfg.get("state_dir") or STATE_DIR
    state = load_state(state_dir) if os.path.isdir(state_dir) else None
    obs = observe_fn(cfg, now)
    _add_cron_top(state, obs, now, cfg, cron_top_fn or top_cron)
    st, actions = evaluate(state, obs, now, cfg)
    return {"obs": obs, "actions": actions, "cron": _cron_summary(st, now)}


def status(state_dir: str) -> dict:
    st = load_state(state_dir)
    if st is None:
        return {"state": "none", "paused": os.path.exists(os.path.join(state_dir, "paused"))}
    return {"run_id": st["run_id"], "last_count": st["last_count"],
            "alerted_count": st["alerted_count"], "samples": len(st["samples"]),
            "down": st["down"], "restarts_24h": len([t for t in st["restarts"]
                                                      if time.time() - t < _DAY]),
            "battery_fired": st["battery_fired"],
            "cron": _cron_summary(st, time.time()),
            "pending": [{"id": p["id"], "tries": p.get("tries", 0)} for p in st["pending"]],
            "paused": os.path.exists(os.path.join(state_dir, "paused"))}


def main(argv: Optional[List[str]] = None, deliver_fn=None) -> int:
    ap = argparse.ArgumentParser(description="Cheetah Docker watchdog (one run; see ops/README.md).")
    ap.add_argument("--dry-run", action="store_true",
                    help="observe and evaluate, print JSON (with the cron drift); no push, "
                         "restart or state write")
    ap.add_argument("--test-push", action="store_true", help="send the 'test' ops alert now")
    ap.add_argument("--status", action="store_true",
                    help="print a state summary as JSON (with the cron drift)")
    ap.add_argument("--state-dir", default=None, help=f"state directory (default {STATE_DIR})")
    args = ap.parse_args(argv)
    state_dir = os.path.expanduser(args.state_dir) if args.state_dir else STATE_DIR
    cfg, notes = load_config(state_dir)
    now = time.time()
    if args.dry_run:
        print(json.dumps(dry_run(cfg, now, state_dir=state_dir), indent=2, default=str))
        return 0
    if args.status:
        print(json.dumps(status(state_dir), indent=2, default=str))
        return 0
    _ensure_dir(state_dir)
    for n in notes:
        log_line(state_dir, "warning", n)
    if args.test_push:
        title, body = compose("test", {})
        res = (deliver_fn or deliver)({"condition": "test", "title": title, "body": body}, cfg)
        log_line(state_dir, "info", "test push", status=res.get("status"), reason=res.get("reason"))
        print(json.dumps(res))
        return 0 if res.get("delivered") else 1
    return run_once(cfg, now, deliver_fn=deliver_fn, state_dir=state_dir)


if __name__ == "__main__":
    sys.exit(main())
