"""ops/docker_watchdog.py — the host watchdog for Docker Desktop (2026-10-06).

On 2026-10-05 Docker's backend died and its gvisor forwarder had leaked ~14,750
flows in 10.5 days; nothing told Ajay. These tests pin the parsers, the alert
rules (forwarder high / growth, Docker down / restored / restarted, battery), the
retry queue, the delivery contract with /admin/ops/alert and the safety rules
(no kill, no shell, a fixed allow-list of binaries, Python 3.9 syntax). No test
runs a subprocess or touches the network.
"""
from __future__ import annotations

import ast
import calendar
import fcntl
import importlib.util
import json
import os
import plistlib
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WD_PATH = ROOT / "ops" / "docker_watchdog.py"
PLIST = ROOT / "launchd" / "com.cheetah.docker-watchdog.plist"
BANNED = ("boun" + "ce", "fa" + "ke")

_spec = importlib.util.spec_from_file_location("docker_watchdog", WD_PATH)
wd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wd)

NOW = 1_791_338_400.0                      # 2026-10-07T02:00:00Z
SVC = (9696, NOW - 3 * 86400)
MAIN = (9693, NOW - 3 * 86400)
CFG = {"admin_email": "admin@example.test", "api_base": "http://127.0.0.1:8000",
       "auto_restart": True}


@pytest.fixture(autouse=True)
def _no_subprocess(monkeypatch):
    def boom(*a, **k):
        raise AssertionError(f"subprocess.run called: {a!r}")
    monkeypatch.setattr(subprocess, "run", boom)


def obs(*, main=(MAIN,), services=(SVC,), derr=None, count=None, ts=None, ferr=None,
        on_ac=True, percent=None, api_ok=True, paused=False):
    return {"docker": {"main": list(main), "services": list(services), "ui": True, "error": derr},
            "forwarder": {"count": count, "ts": NOW - 5 if (ts is None and count is not None) else ts,
                          "source": "monitor.log" if count is not None else None, "error": ferr},
            "battery": {"on_ac": on_ac, "percent": percent},
            "api_ok": api_ok, "paused": paused}


def conds(st):
    return [p["condition"] for p in st["pending"]]


def fwd_line(n, stamp="2026-10-07T01:56:19.927075000Z", remaining=False):
    what = (f"close with 812 bytes transferred ({n} remaining in-progress TCP connections)"
            if remaining else f"dial succeeded ({n} in-progress TCP connections)")
    return ('[' + stamp + '] {"component":"gvisor/forwarder","level":"info","msg":"198.44.194.166:443 '
            '<- 192.168.65.3:42638: ' + what + '","time":"2026-10-06T20:56:19.927054000-05:00"}')


def epoch(stamp):
    return float(calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%S")))


# --------------------------------------------------------------------------- W1-W11
def test_W1_dial_line_gives_count_and_utc_epoch():
    assert wd.parse_forwarder(fwd_line(1081)) == (1081, epoch("2026-10-07T01:56:19"))


def test_W2_close_line_remaining_count():
    assert wd.parse_forwarder(fwd_line(1080, remaining=True))[0] == 1080


def test_W3_last_valid_line_wins():
    text = "\n".join([fwd_line(10, "2026-10-07T01:00:00Z"), "noise",
                      fwd_line(12, "2026-10-07T01:00:05.1Z"), "more noise"])
    assert wd.parse_forwarder(text) == (12, epoch("2026-10-07T01:00:05"))


def test_W4_NEGATIVE_junk_lines_are_ignored():
    good = fwd_line(50, "2026-10-07T00:00:00Z")
    junk = [
        good.replace("gvisor/forwarder", "apiproxy").replace("(50 ", "(9999 "),
        "[2026-13-99T99:99:99Z] " + good.split("] ", 1)[1].replace("(50 ", "(9998 "),
        good.replace("(50 in-progress", "(lots in-progress"),
        good[40:].replace("(50 ", "(9997 "),               # a truncated first line
        "[not a stamp] " + good.split("] ", 1)[1].replace("(50 ", "(9996 "),
    ]
    assert wd.parse_forwarder("\n".join([good] + junk)) == (50, epoch("2026-10-07T00:00:00"))
    assert wd.parse_forwarder("\n".join(junk)) is None


def test_W5_NEGATIVE_empty_text_is_none():
    assert wd.parse_forwarder("") is None
    assert wd.parse_forwarder(None) is None


def test_W6_read_forwarder_from_monitor_log(tmp_path):
    (tmp_path / "monitor.log").write_text("x\n" + fwd_line(1104) + "\n")
    r = wd.read_forwarder(str(tmp_path))
    assert r == {"count": 1104, "ts": epoch("2026-10-07T01:56:19"), "source": "monitor.log",
                 "error": None}


def test_W7_just_rotated_uses_the_newest_rotated_file(tmp_path):
    (tmp_path / "monitor.log").write_text('[2026-10-07T02:00:00Z] {"component":"vm"}\n')
    (tmp_path / "monitor.log.20261006-204810.460").write_text(fwd_line(9000) + "\n")
    (tmp_path / "monitor.log.20261006-205328.584").write_text(fwd_line(1100) + "\n")
    r = wd.read_forwarder(str(tmp_path))
    assert r["count"] == 1100 and r["source"] == "monitor.log.20261006-205328.584"


def test_W8_NEGATIVE_no_line_anywhere(tmp_path):
    (tmp_path / "monitor.log").write_text("nothing here\n")
    (tmp_path / "monitor.log.20261006-205328.584").write_text("nor here\n")
    r = wd.read_forwarder(str(tmp_path))
    assert r["error"] == "no_line" and r["count"] is None


def test_W9_NEGATIVE_missing_dir(tmp_path):
    assert wd.read_forwarder(str(tmp_path / "nope"))["error"] == "missing"


def test_W10_NEGATIVE_permission_error(tmp_path, monkeypatch):
    (tmp_path / "monitor.log").write_text(fwd_line(1) + "\n")

    def denied(*a, **k):
        raise PermissionError("Operation not permitted")
    monkeypatch.setattr(wd, "_tail_text", denied)
    r = wd.read_forwarder(str(tmp_path))
    assert r["error"] == "permission" and r["count"] is None

    def ioerr(*a, **k):
        raise OSError(5, "Input/output error")
    monkeypatch.setattr(wd, "_tail_text", ioerr)
    assert wd.read_forwarder(str(tmp_path))["error"] == "io"


def test_W11_only_the_tail_is_read(tmp_path):
    big = fwd_line(4242) + "\n" + ("x" * 199 + "\n") * 10_500          # ~2 MB
    (tmp_path / "monitor.log").write_text(big)
    assert os.path.getsize(tmp_path / "monitor.log") > 2 * wd.LOG_TAIL_BYTES - 100_000
    r = wd.read_forwarder(str(tmp_path))
    assert r["count"] is None and r["error"] == "no_line"


# --------------------------------------------------------------------------- W12-W16
PS_SAMPLE = """\
  346 Thu Sep 24 12:11:07 2026     /Library/PrivilegedHelperTools/com.docker.vmnetd
 9693 Mon Oct  5 01:56:49 2026     /Applications/Docker.app/Contents/MacOS/com.docker.backend
 9696 Mon Oct  5 01:56:49 2026     /Applications/Docker.app/Contents/MacOS/com.docker.backend services
 9697 Mon Oct  5 01:56:49 2026     /Applications/Docker.app/Contents/MacOS/com.docker.backend fork
 9720 Mon Oct  5 01:56:52 2026     /Applications/Docker.app/Contents/MacOS/com.docker.virtualization --kernel x
 9801 Mon Oct  5 01:57:01 2026     /Applications/Docker.app/Contents/MacOS/Docker Desktop.app/Contents/MacOS/Docker Desktop --name=dashboard
55555 Tue Oct  6 20:00:00 2026     grep com.docker.backend
"""


def test_W12_parse_ps_classifies_main_services_ui():
    # the first 4 lines are the REAL host lines seen 2026-10-06 (ps -axo pid=,lstart=,args=)
    r = wd.parse_ps(PS_SAMPLE)
    start = time.mktime(time.strptime("Mon Oct 5 01:56:49 2026", "%a %b %d %H:%M:%S %Y"))
    assert r["main"] == [(9693, start)]
    assert r["services"] == [(9696, start)]
    assert r["ui"] is True


def test_W13_NEGATIVE_other_subcommands_and_garbage():
    text = ("9697 Mon Oct  5 01:56:49 2026 /x/com.docker.backend fork\n"
            "9698 Mon Oct  5 01:56:49 2026 /x/com.docker.backend run --foo\n"
            "garbage line\n\n  12 Xyz Oct 99 99:99:99 2026 /x/com.docker.backend\n"
            "  13 Mon Oct  5 01:56:49 2026 /x/com.docker.backendX services\n")
    r = wd.parse_ps(text)
    assert r == {"main": [], "services": [], "ui": False}
    assert wd.parse_ps("") == {"main": [], "services": [], "ui": False}


PMSET_BATT = ("Now drawing from 'Battery Power'\n"
              " -InternalBattery-0 (id=12345)\t64%; discharging; 2:02 remaining present: true\n")


def test_W14_pmset_on_battery():
    assert wd.parse_pmset(PMSET_BATT) == {"on_ac": False, "percent": 64}


def test_W15_pmset_on_ac():
    t = "Now drawing from 'AC Power'\n -InternalBattery-0 (id=1)\t80%; charging; 1:00 remaining present: true\n"
    assert wd.parse_pmset(t) == {"on_ac": True, "percent": 80}


def test_W16_NEGATIVE_desktop_has_no_battery():
    p = wd.parse_pmset("Now drawing from 'AC Power'\n")
    assert p == {"on_ac": True, "percent": None}
    st, _ = wd.evaluate(None, obs(on_ac=False, percent=None), NOW, CFG)
    assert "battery_low" not in conds(st)


# --------------------------------------------------------------------------- W17-W24
def run_seq(readings, *, start=NOW, step=120, st=None):
    """Feed forwarder readings one per run; returns (state, list of condition lists)."""
    out = []
    for i, c in enumerate(readings):
        now = start + i * step
        st, _ = wd.evaluate(st, obs(count=c, ts=now - 5), now, CFG)
        out.append(conds(st))
        st["pending"] = []
    return st, out


def test_W17_NEGATIVE_1999_twice_is_quiet():
    _, out = run_seq([1999, 1999])
    assert out == [[], []]


def test_W18_two_reads_at_2000_alert_once():
    _, out = run_seq([2000, 2000, 2000])
    assert out == [[], ["forwarder_high"], []]
    _, out = run_seq([1500, 2100])
    assert out == [[], []], "one read is not two"


def test_W19_repeat_rearm_rules():
    def conds(st):                       # growth is W21/W22's business; only "high" here
        return [p["condition"] for p in st["pending"] if p["condition"] == "forwarder_high"]
    st, out = run_seq([2000, 2000])
    assert out[-1] == ["forwarder_high"]
    t = NOW + 240
    st, _ = wd.evaluate(st, obs(count=2500, ts=t), t, CFG)
    assert conds(st) == []
    t += 120
    st, _ = wd.evaluate(st, obs(count=3000, ts=t), t, CFG)
    assert conds(st) == ["forwarder_high"] and st["alerted_count"] == 3000
    st["pending"] = []
    t2 = t + 3 * 3600
    st, _ = wd.evaluate(st, obs(count=3100, ts=t2), t2, CFG)
    assert conds(st) == []
    t3 = t + 6 * 3600
    st, _ = wd.evaluate(st, obs(count=3100, ts=t3), t3, CFG)
    assert conds(st) == ["forwarder_high"]
    st["pending"] = []
    st, _ = wd.evaluate(st, obs(count=1700, ts=t3 + 120), t3 + 120, CFG)
    assert st["alerted_count"] is None
    st, _ = wd.evaluate(st, obs(count=2000, ts=t3 + 240), t3 + 240, CFG)
    st, _ = wd.evaluate(st, obs(count=2000, ts=t3 + 360), t3 + 360, CFG)
    assert conds(st) == ["forwarder_high"]


def test_W20_NEGATIVE_a_line_from_before_this_backend_run_is_ignored():
    stale = SVC[1] - wd.STALE_LINE_TOLERANCE_SEC - 1
    st, acts = wd.evaluate(None, obs(count=5000, ts=stale), NOW, CFG)
    st, acts = wd.evaluate(st, obs(count=5000, ts=stale), NOW + 120, CFG)
    assert conds(st) == [] and st["last_count"] is None and st["samples"] == []
    assert any("predates" in a.get("msg", "") for a in acts if a["type"] == "log")


def _grow(samples_counts, now_count, *, span_h=20.0, growth_alerted_at=None, st=None):
    st = st or wd.default_state()
    st["run_id"] = f"{SVC[0]}:{int(SVC[1])}"
    st["services_start"] = SVC[1]
    n = len(samples_counts)
    st["samples"] = [[NOW - span_h * 3600 + i * (span_h * 3600 / max(1, n)), c]
                     for i, c in enumerate(samples_counts)]
    st["last_count"] = now_count
    st["growth_alerted_at"] = growth_alerted_at
    st, _ = wd.evaluate(st, obs(count=now_count, ts=NOW - 5), NOW, CFG)
    return st


def test_W21_growth_floor_to_floor_alerts():
    counts = [1000] + [1200] * 100 + [1520] * 20
    st = _grow(counts, 1530)
    assert "forwarder_growth" in conds(st)
    p = [p for p in st["pending"] if p["condition"] == "forwarder_growth"][0]
    assert "+520" in p["title"]


def test_W22_NEGATIVE_growth_quiet_cases_and_repeat():
    assert "forwarder_growth" not in conds(_grow([1000] + [1490] * 30, 1490))
    spike = [1000, 1020] * 50 + [1050, 1600, 1050, 1050, 1050, 1050]
    assert "forwarder_growth" not in conds(_grow(spike, 1050))
    ok = [1000] + [1600] * 30
    assert "forwarder_growth" not in conds(_grow(ok, 1600, growth_alerted_at=NOW - 11 * 3600))
    assert "forwarder_growth" not in conds(_grow([1000, 1600], 1600, span_h=0.5))
    assert "forwarder_growth" in conds(_grow(ok, 1600, growth_alerted_at=NOW - 12 * 3600))


def test_W23_NEGATIVE_old_run_samples_never_count_after_a_restart():
    st = wd.default_state()
    st["run_id"] = "1111:1000"
    st["samples"] = [[NOW - 20 * 3600 + i * 600, 100] for i in range(100)]
    st["last_count"] = 2500
    new_svc = (2222, NOW - 600)
    st, _ = wd.evaluate(st, obs(services=(new_svc,), count=900, ts=NOW - 5), NOW, CFG)
    assert "forwarder_growth" not in conds(st)
    assert "forwarder_high" not in conds(st)
    assert st["samples"] == [[NOW, 900]]
    assert st["run_id"] == f"2222:{int(NOW - 600)}"


def test_W24_sampling_and_pruning():
    st, _ = run_seq([500] * 61)                               # 2 h of 120 s runs
    assert len(st["samples"]) <= 13
    st = wd.default_state()
    st["run_id"] = f"{SVC[0]}:{int(SVC[1])}"
    st["samples"] = [[NOW - 27 * 3600, 1], [NOW - 25 * 3600, 2]]
    st, _ = wd.evaluate(st, obs(count=3, ts=NOW), NOW, CFG)
    assert [s[1] for s in st["samples"]] == [2, 3]


# --------------------------------------------------------------------------- W25-W34
GONE = dict(main=(), services=(), api_ok=False)


def restarts(acts):
    return sum(1 for a in acts if a["type"] == "restart")


def test_W25_NEGATIVE_one_miss_then_back_is_quiet():
    st, a1 = wd.evaluate(None, obs(), NOW, CFG)
    st, a2 = wd.evaluate(st, obs(**GONE), NOW + 120, CFG)
    st, a3 = wd.evaluate(st, obs(), NOW + 240, CFG)
    assert conds(st) == [] and restarts(a1 + a2 + a3) == 0
    assert st["down"]["checks"] == 0


def test_W26_two_misses_alert_and_restart_once():
    st, _ = wd.evaluate(None, obs(), NOW, CFG)
    st, a = wd.evaluate(st, obs(**GONE), NOW + 120, CFG)
    assert restarts(a) == 0 and conds(st) == []
    st, a = wd.evaluate(st, obs(**GONE), NOW + 240, CFG)
    assert restarts(a) == 1
    assert conds(st) == ["docker_down"]
    assert "opened Docker at" in st["pending"][0]["body"]


def test_W27_NEGATIVE_paused_alerts_but_never_restarts():
    st, _ = wd.evaluate(None, obs(**GONE, paused=True), NOW, CFG)
    st, a = wd.evaluate(st, obs(**GONE, paused=True), NOW + 120, CFG)
    assert restarts(a) == 0 and conds(st) == ["docker_down"]
    assert "paused" in st["pending"][0]["body"]


def test_W28_NEGATIVE_restart_gap_and_daily_cap():
    st, _ = wd.evaluate(None, obs(**GONE), NOW, CFG)
    t = NOW + 120
    st, a = wd.evaluate(st, obs(**GONE), t, CFG)
    assert restarts(a) == 1
    st, a = wd.evaluate(st, obs(**GONE), t + 600, CFG)
    assert restarts(a) == 0, "no second restart within 15 min"
    st, a = wd.evaluate(st, obs(**GONE), t + 900, CFG)
    assert restarts(a) == 1
    st, a = wd.evaluate(st, obs(**GONE), t + 1800, CFG)
    assert restarts(a) == 1
    st, a = wd.evaluate(st, obs(**GONE), t + 2700, CFG)
    assert restarts(a) == 0, "3 in 24 h is the cap"
    assert conds(st) == ["docker_down"], "one docker_down per episode"
    # back, then a NEW episode inside the same 24 h: the body says it gave up
    st, _ = wd.evaluate(st, obs(), t + 3000, CFG)
    st["pending"] = []
    st, _ = wd.evaluate(st, obs(**GONE), t + 3600, CFG)
    st, a = wd.evaluate(st, obs(**GONE), t + 3720, CFG)
    assert restarts(a) == 0
    assert "gave up after 3 tries in 24 h" in st["pending"][-1]["body"]
    # a day later the cap has rolled off
    st, a = wd.evaluate(st, obs(**GONE), t + 2700 + 86400, CFG)
    assert restarts(a) == 1


def test_W29_NEGATIVE_auto_restart_off():
    cfg = dict(CFG, auto_restart=False)
    st, _ = wd.evaluate(None, obs(**GONE), NOW, cfg)
    st, a = wd.evaluate(st, obs(**GONE), NOW + 120, cfg)
    assert restarts(a) == 0 and "auto-restart off" in st["pending"][0]["body"]


def test_W30_NEGATIVE_ps_error_counts_nothing():
    st = None
    for i in range(4):
        st, a = wd.evaluate(st, obs(main=(), services=(), derr="ps exit 1", api_ok=False),
                            NOW + i * 120, CFG)
        assert restarts(a) == 0
    assert st["down"]["checks"] == 0 and conds(st) == []


def test_W31_NEGATIVE_no_processes_but_api_answers():
    st = None
    for i in range(5):
        st, a = wd.evaluate(st, obs(main=(), services=(), api_ok=True), NOW + i * 120, CFG)
        assert restarts(a) == 0
    assert conds(st) == ["watchdog_error"]
    assert "can't find Docker's processes" in st["pending"][0]["body"]
    st, _ = wd.evaluate(st, obs(main=(), services=(), api_ok=True), NOW + 23 * 3600, CFG)
    assert conds(st).count("watchdog_error") == 1
    st, _ = wd.evaluate(st, obs(main=(), services=(), api_ok=True), NOW + 24 * 3600, CFG)
    assert conds(st).count("watchdog_error") == 2


def test_W32_services_gone_main_alive_says_quit_and_reopen():
    st, a1 = wd.evaluate(None, obs(services=(), api_ok=False), NOW, CFG)
    st, a2 = wd.evaluate(st, obs(services=(), api_ok=False), NOW + 120, CFG)
    assert restarts(a1 + a2) == 0
    assert conds(st) == ["docker_down"]
    assert "Quit and reopen Docker Desktop" in st["pending"][0]["body"]


def test_W33_recovery_waits_for_health_then_one_restored():
    st, _ = wd.evaluate(None, obs(**GONE), NOW, CFG)
    st, _ = wd.evaluate(st, obs(**GONE), NOW + 120, CFG)
    assert conds(st) == ["docker_down"]
    st, _ = wd.evaluate(st, obs(api_ok=False), NOW + 600, CFG)
    assert "docker_restored" not in conds(st)
    st, _ = wd.evaluate(st, obs(api_ok=True), NOW + 720, CFG)
    assert conds(st) == ["docker_restored"], "pending docker_down superseded"
    body = st["pending"][0]["body"]
    assert "about 12 min" in body and "Restart attempts: 1" in body
    st, _ = wd.evaluate(st, obs(), NOW + 840, CFG)
    assert conds(st) == ["docker_restored"], "once"
    assert st["down"]["alerted"] is False


def test_W34_backend_restarted_only_on_a_known_run_change():
    st, _ = wd.evaluate(None, obs(), NOW, CFG)
    assert conds(st) == [], "first-ever run queues nothing"
    st, _ = wd.evaluate(st, obs(), NOW + 120, CFG)
    assert conds(st) == [], "same run_id"
    st, _ = wd.evaluate(st, obs(services=((7777, NOW + 100),)), NOW + 240, CFG)
    assert conds(st) == ["backend_restarted"]
    # NEG: a restart inside an alerted down episode reports docker_restored instead
    st["pending"] = []
    st, _ = wd.evaluate(st, obs(**GONE), NOW + 360, CFG)
    st, _ = wd.evaluate(st, obs(**GONE), NOW + 480, CFG)
    st, _ = wd.evaluate(st, obs(services=((8888, NOW + 500),)), NOW + 600, CFG)
    assert "backend_restarted" not in conds(st) and "docker_restored" in conds(st)


# --------------------------------------------------------------------------- W35
def test_W35_battery_levels_fire_once_per_discharge():
    st = None
    seen = []
    for on_ac, p in [(False, 20), (False, 19), (False, 15), (False, 9), (True, 50),
                     (False, 19)]:
        st, _ = wd.evaluate(st, obs(on_ac=on_ac, percent=p), NOW, CFG)
        seen.append(conds(st).count("battery_low"))
        st["pending"] = []
    assert seen == [0, 1, 0, 1, 0, 1]
    st, _ = wd.evaluate(st, obs(on_ac=True, percent=90), NOW, CFG)
    st, _ = wd.evaluate(st, obs(on_ac=False, percent=25), NOW, CFG)
    st, _ = wd.evaluate(st, obs(on_ac=False, percent=8), NOW, CFG)
    assert conds(st) == ["battery_low"]
    assert sorted(st["battery_fired"]) == [10, 20]
    assert "under 10%" in st["pending"][0]["body"]


# --------------------------------------------------------------------------- W36-W42
class StubDeliver:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def __call__(self, item, cfg):
        self.calls.append(item)
        return self.results.pop(0) if self.results else {"delivered": True, "status": 200}


class Rec:
    def __init__(self):
        self.calls = []

    def __call__(self, *a):
        self.calls.append(a)


def _down_obs(cfg, now):
    return obs(on_ac=False, percent=5)


def test_W36_undelivered_notifies_once_and_retries_every_15_min(tmp_path):
    no = {"delivered": False, "status": 200, "reason": "no_target"}
    d, n, r = StubDeliver(no, no), Rec(), Rec()
    kw = dict(observe_fn=_down_obs, deliver_fn=d, notify_fn=n, restart_fn=r, state_dir=str(tmp_path))
    assert wd.run_once(CFG, NOW, **kw) == 1
    assert len(d.calls) == 1 and len(n.calls) == 1
    assert wd.run_once(CFG, NOW + 600, **kw) == 1
    assert len(d.calls) == 1, "no retry inside RETRY_SEC"
    assert wd.run_once(CFG, NOW + 900, **kw) == 1
    assert len(d.calls) == 2 and len(n.calls) == 1, "local notification on the FIRST failure only"
    assert wd.run_once(CFG, NOW + 1800, **kw) == 0
    assert len(d.calls) == 3
    assert wd.load_state(str(tmp_path))["pending"] == []
    assert r.calls == []


def test_W37_NEGATIVE_non_200_is_not_delivered():
    class Resp:
        def __init__(self, code, body):
            self.code, self.body = code, body

        def getcode(self):
            return self.code

        def read(self, n=-1):
            return self.body

        def close(self):
            pass

    import urllib.error

    class Op:
        def __init__(self, mode):
            self.mode = mode
            self.reqs = []

        def open(self, req, timeout=None):
            self.reqs.append(req)
            if self.mode == 429:
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, None)
            if self.mode == "ok":
                return Resp(200, b'{"ok": true, "delivered": true}')
            return Resp(200, b'{"ok": true, "delivered": false, "skipped": "quiet_hours"}')

    item = {"condition": "test", "title": "t", "body": "b"}
    r = wd.deliver(item, CFG, opener=Op(429))
    assert r["delivered"] is False and r["status"] == 429
    r = wd.deliver(item, CFG, opener=Op("held"))
    assert r["delivered"] is False and r["reason"] == "quiet_hours"
    op = Op("ok")
    r = wd.deliver(item, CFG, opener=op)
    assert r["delivered"] is True
    req = op.reqs[0]
    assert req.full_url == "http://127.0.0.1:8000/admin/ops/alert"
    assert req.get_method() == "POST"
    assert req.get_header("X-user-email") == "admin@example.test"
    assert json.loads(req.data) == item
    st = wd.default_state()
    st["pending"] = [{"id": "test:1", "condition": "test", "title": "t", "body": "b",
                      "created_at": NOW, "last_try_at": None, "tries": 0}]
    st, notify = wd.record_delivery(st, "test:1", False, NOW)
    assert notify is True and st["pending"][0]["tries"] == 1
    st, _ = wd.evaluate(st, obs(), NOW + 899, CFG)
    st2, acts = wd.evaluate(st, obs(), NOW + 900, CFG)
    assert [a["id"] for a in acts if a["type"] == "push"] == ["test:1"]


def test_W38_NEGATIVE_pending_ttl_and_cap():
    st = wd.default_state()
    st["pending"] = [{"id": f"test:{i}", "condition": "test", "title": "t", "body": "b",
                      "created_at": NOW - 25 * 3600, "last_try_at": NOW - 100, "tries": 3}
                     for i in range(2)]
    st, acts = wd.evaluate(st, obs(), NOW, CFG)
    assert st["pending"] == []
    assert sum(1 for a in acts if a.get("msg") == "pending alert expired") == 2
    st["pending"] = [{"id": f"test:{i}", "condition": "test", "title": "t", "body": "b",
                      "created_at": NOW - 1000 + i, "last_try_at": NOW, "tries": 1}
                     for i in range(25)]
    st, _ = wd.evaluate(st, obs(), NOW, CFG)
    assert len(st["pending"]) == wd.PENDING_MAX
    assert st["pending"][0]["id"] == "test:5", "the oldest are dropped"


def test_W39_NEGATIVE_deliver_refuses_non_loopback_and_missing_email():
    class Op:
        calls = 0

        def open(self, *a, **k):
            Op.calls += 1
            raise AssertionError("no request may be made")

    item = {"condition": "test", "title": "t", "body": "b"}
    for base in ("http://192.168.1.108:8000", "http://localhost:8000", "https://127.0.0.1:8000",
                 "http://127.0.0.1:8000@192.168.1.5", "http://127.0.0.1.evil.example:8000"):
        r = wd.deliver(item, dict(CFG, api_base=base), opener=Op())
        assert r == {"delivered": False, "status": None, "reason": "api_base_not_loopback"}, base
    for email in (None, "", "   "):
        r = wd.deliver(item, dict(CFG, admin_email=email), opener=Op())
        assert r["reason"] == "no_admin_email"
    assert Op.calls == 0


def test_W40_corrupt_state_starts_fresh_and_save_is_atomic(tmp_path, monkeypatch):
    (tmp_path / "state.json").write_text("{not json")
    assert wd.load_state(str(tmp_path)) is None
    st, acts = wd.evaluate(wd.load_state(str(tmp_path)), obs(), NOW, CFG)
    assert st["version"] == wd.STATE_VERSION
    assert any("fresh" in a.get("msg", "") for a in acts)
    (tmp_path / "state.json").write_text(json.dumps({"version": 999}))
    assert wd.load_state(str(tmp_path)) is None
    seen = []
    real = os.replace

    def spy(src, dst):
        seen.append((os.path.dirname(src), os.path.basename(src), os.path.basename(dst)))
        return real(src, dst)
    monkeypatch.setattr(wd.os, "replace", spy)
    wd.save_state(str(tmp_path), st)
    assert seen and seen[0][0] == str(tmp_path) and seen[0][2] == "state.json"
    assert seen[0][1] != "state.json"
    assert wd.load_state(str(tmp_path)) == st
    d = Rec()
    kw = dict(observe_fn=lambda c, n: obs(), deliver_fn=d, notify_fn=Rec(), restart_fn=Rec(),
              state_dir=str(tmp_path))
    (tmp_path / "state.json").write_text("garbage")
    assert wd.run_once(CFG, NOW, **kw) == 0


def test_W41_NEGATIVE_lock_held_exits_0_without_observing(tmp_path):
    called = []
    fd = os.open(str(tmp_path / "lock"), os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        rc = wd.run_once(CFG, NOW, observe_fn=lambda c, n: called.append(1) or obs(),
                         deliver_fn=Rec(), notify_fn=Rec(), restart_fn=Rec(),
                         state_dir=str(tmp_path))
    finally:
        os.close(fd)
    assert rc == 0 and called == []
    assert not (tmp_path / "state.json").exists()


def test_W42_dry_run_has_no_side_effects(tmp_path, monkeypatch):
    for name in ("deliver", "notify_local", "restart_docker", "save_state"):
        monkeypatch.setattr(wd, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError(name)))
    out = wd.dry_run(CFG, NOW, observe_fn=lambda c, n: obs(**GONE, on_ac=False, percent=5),
                     state_dir=str(tmp_path))
    assert set(out) == {"obs", "actions"}
    json.dumps(out, default=str)
    assert list(tmp_path.iterdir()) == []


def test_W36b_unexpected_exception_exits_3_and_notifies_once_a_day(tmp_path):
    n = Rec()

    def broken(cfg, now):
        raise RuntimeError("boom")
    kw = dict(observe_fn=broken, deliver_fn=Rec(), notify_fn=n, restart_fn=Rec(),
              state_dir=str(tmp_path))
    assert wd.run_once(CFG, NOW, **kw) == 3
    assert wd.run_once(CFG, NOW + 120, **kw) == 3
    assert len(n.calls) == 1
    assert wd.run_once(CFG, NOW + 86400, **kw) == 3
    assert len(n.calls) == 2
    assert "boom" in (tmp_path / "watchdog.log").read_text()


def test_W36c_unreadable_log_exits_2_and_says_so_once(tmp_path):
    kw = dict(observe_fn=lambda c, n: obs(ferr="permission"),
              deliver_fn=StubDeliver(), notify_fn=Rec(), restart_fn=Rec(), state_dir=str(tmp_path))
    d = kw["deliver_fn"]
    assert wd.run_once(CFG, NOW, **kw) == 2
    assert [c["condition"] for c in d.calls] == ["watchdog_error"]
    assert wd.run_once(CFG, NOW + 120, **kw) == 2
    assert len(d.calls) == 1


def test_config_unknown_keys_and_bad_types_keep_defaults(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps(
        {"admin_email": "a@b.c", "auto_restart": "yes", "whatever": 1}))
    cfg, notes = wd.load_config(str(tmp_path))
    assert cfg["admin_email"] == "a@b.c" and cfg["auto_restart"] is True
    assert cfg["api_base"] == wd.DEFAULT_API_BASE
    assert len(notes) == 2
    cfg, _ = wd.load_config(str(tmp_path / "none"))
    assert cfg["admin_email"] is None


# --------------------------------------------------------------------------- W43-W47
def test_W43_every_condition_fits_and_reads_clean():
    assert wd.CONDITIONS == frozenset({
        "forwarder_high", "forwarder_growth", "docker_down", "docker_restored",
        "backend_restarted", "battery_low", "watchdog_error", "test"})
    big = {"n": 999_999, "g": 999_999, "h": 99_999, "k": 99_999, "since": NOW, "m": 99_999,
           "t0": NOW, "t1": NOW, "t": NOW, "p": 100, "level": 20,
           "reason": "r" * 400, "outcome": "o" * 400}
    for c in sorted(wd.CONDITIONS):
        for facts in (big, dict(big, variant="services"), {}):
            title, body = wd.compose(c, facts)
            assert 0 < len(title) <= wd.TITLE_MAX and 0 < len(body) <= wd.BODY_MAX, c
            for w in BANNED:
                assert w not in (title + body).lower(), (c, w)
    t, b = wd.compose("forwarder_high", {"n": 14750})
    assert "14,750" in t and "2,000" in b
    with pytest.raises(ValueError):
        wd.compose("nope", {})


def test_W44_osascript_text_rides_as_argv(monkeypatch):
    seen = []
    monkeypatch.setattr(wd, "_run", lambda argv, timeout=20: seen.append(argv))
    title, body = 'He said "hi"', "it's \"quoted\" & done"
    wd.notify_local(title, body)
    argv = seen[0]
    assert argv[0] == "/usr/bin/osascript"
    assert argv[-2:] == [title, body]
    script = " ".join(argv[1:-2])
    assert "hi" not in script and "quoted" not in script


def test_W45_source_safety():
    src = WD_PATH.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert "signal" not in [a.name for a in node.names]
        if isinstance(node, ast.ImportFrom):
            assert node.module != "signal"
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == "os":
            assert node.attr not in ("kill", "killpg", "system", "popen"), node.attr
        if isinstance(node, ast.keyword) and node.arg == "shell":
            raise AssertionError("shell= is not allowed")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in ("kill", "pkill", "killall", "launchctl"), node.value
    # "docker" is the obs schema's own key (obs["docker"], SPEC §4.1), so it may be a
    # dict key or a subscript — never an argv element or a call argument.
    keyish = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keyish |= {id(k) for k in node.keys if k is not None}
        if isinstance(node, ast.Subscript):
            keyish.add(id(node.slice))
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) in ("get", "pop"):
            keyish |= {id(a) for a in node.args[:1]}
    docker_consts = [n for n in ast.walk(tree)
                     if isinstance(n, ast.Constant) and n.value == "docker"]
    assert docker_consts, "the obs schema key is expected"
    for n in docker_consts:
        assert id(n) in keyish, f"'docker' used outside a key at line {n.lineno}"
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(fn):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id == "subprocess":
                assert fn.name == "_run", f"subprocess.{node.attr} outside _run in {fn.name}"
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for sub in ast.walk(node):
                assert not (isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name)
                            and sub.value.id == "subprocess")
    with pytest.raises(ValueError):
        wd._run(["/bin/kill", "1"])
    with pytest.raises(ValueError):
        wd._run([])
    assert wd.ALLOWED_BINARIES == frozenset({"/bin/ps", "/usr/bin/pmset", "/usr/bin/osascript",
                                             "/usr/bin/open"})


def test_W46_python_3_9_guard():
    src = WD_PATH.read_text()
    tree = ast.parse(src, feature_version=(3, 9))
    first = tree.body[1]
    assert isinstance(first, ast.ImportFrom) and first.module == "__future__"
    assert not any(type(n).__name__ == "Match" for n in ast.walk(tree))
    annots = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            annots += [a.annotation for a in n.args.args + n.args.kwonlyargs if a.annotation]
            if n.returns:
                annots.append(n.returns)
        if isinstance(n, ast.AnnAssign):
            annots.append(n.annotation)
    for a in annots:
        assert not any(isinstance(x, ast.BitOr) for x in ast.walk(a)), ast.dump(a)
    assert "tomllib" not in src and "datetime.UTC" not in src
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "zip":
            assert not any(k.arg == "strict" for k in n.keywords)
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "dataclass":
            assert not any(k.arg in ("slots", "kw_only") for k in n.keywords)


def test_W47_plist_matches_the_script():
    p = plistlib.loads(PLIST.read_bytes())
    assert p["Label"] == "com.cheetah.docker-watchdog"
    assert p["ProgramArguments"] == ["/usr/bin/python3",
                                     "/Users/ajay/clinet-test/cheetah-deploy/ops/docker_watchdog.py"]
    assert p["StartInterval"] == wd.CHECK_INTERVAL_SEC == 120
    assert p["RunAtLoad"] is True
    assert p["LimitLoadToSessionType"] == "Aqua"
    assert "KeepAlive" not in p
    assert p["EnvironmentVariables"]["LC_ALL"] == "C"


def test_constants_are_the_reviewed_values():
    assert (wd.FORWARDER_ALERT_AT, wd.FORWARDER_CONFIRM_READS, wd.FORWARDER_REARM_BELOW,
            wd.FORWARDER_STEP, wd.FORWARDER_REPEAT_SEC) == (2000, 2, 1800, 1000, 6 * 3600)
    assert (wd.GROWTH_WINDOW_SEC, wd.GROWTH_ALERT, wd.GROWTH_FLOOR_SEC, wd.GROWTH_MIN_SPAN_SEC,
            wd.GROWTH_REPEAT_SEC) == (86400, 500, 3600, 3600, 12 * 3600)
    assert (wd.SAMPLE_EVERY_SEC, wd.SAMPLE_KEEP_SEC, wd.STALE_LINE_TOLERANCE_SEC) == (600, 26 * 3600, 120)
    assert (wd.DOWN_CHECKS_TO_ACT, wd.RESTART_MIN_GAP_SEC, wd.RESTART_MAX_PER_DAY) == (2, 900, 3)
    assert (wd.RETRY_SEC, wd.PENDING_TTL_SEC, wd.PENDING_MAX) == (900, 86400, 20)
    assert wd.BATTERY_LEVELS == (20, 10)
    assert (wd.LOG_TAIL_BYTES, wd.ROTATED_MAX_FILES, wd.OWN_LOG_MAX_BYTES) == (1048576, 3, 1000000)
    assert (wd.TITLE_MAX, wd.BODY_MAX) == (80, 280)
    assert wd.DEFAULT_API_BASE == "http://127.0.0.1:8000"
    assert wd.RETRY_SEC * 6 >= 3600, "retries stay under the server's 6/h/condition cap"


# --------------------------------------------------------------------------- critic 2026-10-06
def test_W48_two_items_queued_in_one_run_get_distinct_ids_and_one_delivery_keeps_the_other():
    st = {"pending": [], "error_alerted_at": {}}
    wd._queue(st, "watchdog_error", {"reason": "procs"}, NOW)
    wd._queue(st, "watchdog_error", {"reason": "log"}, NOW)
    ids = [p["id"] for p in st["pending"]]
    assert len(set(ids)) == 2, ids
    st, _ = wd.record_delivery(st, ids[0], True, NOW)
    assert [p["id"] for p in st["pending"]] == [ids[1]], "NEG: the undelivered one must survive"
    st, notify = wd.record_delivery(st, ids[1], False, NOW + 1)
    assert notify is True and len(st["pending"]) == 1


def test_W49_NEG_services_gone_while_the_api_answers_is_a_watchdog_error_never_docker_down():
    st, a1 = wd.evaluate(None, obs(services=(), api_ok=True), NOW, CFG)
    st, a2 = wd.evaluate(st, obs(services=(), api_ok=True), NOW + 120, CFG)
    assert restarts(a1 + a2) == 0
    assert "docker_down" not in conds(st)
    assert conds(st) == ["watchdog_error"], "once a day, not every run"
    assert "forwarder count is not being watched" in st["pending"][0]["body"]
