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
    assert set(out) == {"obs", "actions", "cron"}          # 2026-10-11: + the cron drift
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
        "backend_restarted", "battery_low", "watchdog_error", "cron_drift_busy", "test"})
    big = {"n": 999_999, "g": 999_999, "h": 99_999, "k": 99_999, "since": NOW, "m": 99_999,
           "t0": NOW, "t1": NOW, "t": NOW, "p": 100, "level": 20,
           "reason": "r" * 400, "outcome": "o" * 400,
           "drift": 9e9, "waited": 9e9, "cmd": "c" * 400}
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
                                             "/usr/bin/open", "/usr/local/bin/docker"})


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


# --------------------------------------------------------------------------- cron re-sync 2026-10-11
# The Mac sleeps -> Docker's VM pauses -> supercronic's monotonic timers stop, so
# every pending job fires late by the summed pause (measured 2026-10-11: 22.4 h).
# The watchdog sums host sleep (wall minus monotonic) since the cron container
# started and restarts that container only while no job runs.
STARTED = "2026-10-08T23:26:34.123456789Z"
IDLE = ["/sbin/docker-init -- supercronic /app/crontab", "supercronic /app/crontab"]
JOB = "/bin/sh -c cd /app && python -m supply_demand.zone_edge"
BUSY = IDLE + [JOB, "python -m supply_demand.zone_edge"]
TOP_SAMPLE = """\
PID                 COMMAND
81252               /sbin/docker-init -- supercronic /app/crontab
81277               supercronic /app/crontab
"""


def cobs(mono, *, started=STARTED, running=True, cerr=None, procs=IDLE, top_err=None, **kw):
    o = obs(**kw)
    o["mono"] = mono
    o["cron"] = {"started_at": None if cerr else started, "running": None if cerr else running,
                 "error": cerr}
    if procs is not None or top_err is not None:
        o["cron"]["top"] = {"procs": procs, "error": top_err}
    return o


def resyncs(acts):
    return [a for a in acts if a["type"] == "cron_resync"]


def slept_state(acc, *, started=STARTED, t=NOW, mono=1000.0):
    """A state that already carries ``acc`` seconds of drift on the current cron."""
    st = wd.default_state()
    st.update(last_wall=t, last_mono=mono, cron_started_at=started, cron_sleep_acc_sec=float(acc))
    return st


def test_C1_sleep_accumulates_across_runs():
    st, a = wd.evaluate(None, cobs(1000.0, procs=BUSY), NOW, CFG)
    assert st["cron_sleep_acc_sec"] == 0.0 and st["cron_started_at"] == STARTED
    # 120 s of awake time + 60 s asleep: wall moves 180, monotonic 120
    st, a = wd.evaluate(st, cobs(1120.0, procs=BUSY), NOW + 180, CFG)
    assert st["cron_sleep_acc_sec"] == pytest.approx(60.0)
    assert st["cron_last_decision"] == "in_sync" and resyncs(a) == []
    st, a = wd.evaluate(st, cobs(1240.0, procs=BUSY), NOW + 180 + 210, CFG)
    assert st["cron_sleep_acc_sec"] == pytest.approx(150.0)
    assert st["cron_last_decision"] == "busy" and resyncs(a) == []


def test_C2_measured_case_22_4_h_drift_resyncs_once():
    wall_h, mono_h = 74.6, 52.2                                   # 2026-10-11, cron started 10-08
    st, _ = wd.evaluate(None, cobs(0.0), NOW, CFG)
    st, a = wd.evaluate(st, cobs(mono_h * 3600), NOW + wall_h * 3600, CFG)
    assert [round(r["drift_sec"] / 3600.0, 1) for r in resyncs(a)] == [22.4]
    assert st["cron_last_decision"] == "resync"
    assert conds(st) == [], "no push for a resync"


def test_C3_NEGATIVE_small_jitter_is_ignored():
    st, _ = wd.evaluate(None, cobs(0.0), NOW, CFG)
    t, m = NOW, 0.0
    for _ in range(200):                                          # 200 runs, 5 s off each
        t, m = t + 125.0, m + 120.0
        st, a = wd.evaluate(st, cobs(m), t, CFG)
        assert resyncs(a) == []
    assert st["cron_sleep_acc_sec"] == 0.0
    st, _ = wd.evaluate(st, cobs(m + 120.0), t + 126.0, CFG)
    assert st["cron_sleep_acc_sec"] == pytest.approx(6.0), "past the tolerance it counts"


def test_C4_NEGATIVE_reboot_or_wall_clock_back_rebaselines_without_action():
    st = slept_state(50, mono=500_000.0)
    st, a = wd.evaluate(st, cobs(30.0), NOW + 9 * 3600, CFG)       # monotonic restarted
    assert st["cron_sleep_acc_sec"] == 50.0 and resyncs(a) == []
    assert any(x.get("msg") == "clock re-baselined" for x in a)
    assert (st["last_wall"], st["last_mono"]) == (NOW + 9 * 3600, 30.0)
    st, a = wd.evaluate(st, cobs(150.0), NOW + 8 * 3600, CFG)      # wall clock set back
    assert st["cron_sleep_acc_sec"] == 50.0 and resyncs(a) == []
    assert any(x.get("reason") == "wall clock went back" for x in a)


def test_C5_NEGATIVE_a_new_cron_container_resets_the_drift():
    st = slept_state(5000)
    # verifier 2026-10-11: the reset keeps this interval's sleep (C31); awake here, so 0
    st, a = wd.evaluate(st, cobs(1000.0 + 3720, started="2026-10-12T02:13:42.197244003Z"),
                        NOW + 3720, CFG)                           # awake 3,720 s, new start
    assert st["cron_sleep_acc_sec"] == 0.0 and resyncs(a) == []
    assert st["cron_started_at"] == "2026-10-12T02:13:42.197244003Z"
    assert any(x.get("msg") == "cron container restarted; drift reset" for x in a)


def test_C6_NEGATIVE_under_the_line_never_resyncs_or_reads_top():
    st = slept_state(wd.CRON_RESYNC_AT_SEC - 10)
    o = cobs(1120.0, procs=None)
    assert wd.cron_wants_top(st, o, NOW + 120 + 9, CFG) is False
    st, a = wd.evaluate(st, cobs(1120.0), NOW + 129, CFG)
    assert resyncs(a) == [] and st["cron_last_decision"] == "in_sync"
    o = cobs(1240.0, procs=None)
    assert wd.cron_wants_top(st, o, NOW + 129 + 130, CFG) is True, "119 + 10 >= 120"


def test_C7_idle_and_due_gives_exactly_one_restart_action():
    st = slept_state(wd.CRON_RESYNC_AT_SEC)
    st, a = wd.evaluate(st, cobs(1120.0), NOW + 120, CFG)
    assert resyncs(a) == [{"type": "cron_resync", "drift_sec": 120.0}]
    assert st["cron_resyncs"] == [NOW + 120]
    assert [x["type"] for x in a].count("restart") == 0, "Docker itself is never touched"


def test_C8_busy_cron_never_restarts_and_alerts_once_after_1800_s():
    st = slept_state(8 * 3600)
    t, m = NOW, 1000.0
    alerts = []
    for _ in range(40):                                           # 40 runs x 120 s = 80 min
        t, m = t + 120, m + 120
        st, a = wd.evaluate(st, cobs(m, procs=BUSY), t, CFG)
        assert resyncs(a) == []
        alerts.append(conds(st).count("cron_drift_busy"))
    # run i waits 120 * (i - 1) s; the first wait past 1,800 s is run 17 (1,920 s)
    assert alerts.index(1) == 16 and alerts[:16] == [0] * 16
    assert alerts[-1] == 1, "ONE alert, not one per run"
    body = [p for p in st["pending"] if p["condition"] == "cron_drift_busy"][0]
    assert "8.0 h" in body["title"] and "supply_demand.zone_edge" in body["body"]
    # job done -> one restart; success re-arms the alert and drops the stale pending one
    t, m = t + 120, m + 120
    st, a = wd.evaluate(st, cobs(m), t, CFG)
    assert len(resyncs(a)) == 1 and st["cron_busy_since"] is None
    st = wd.record_cron_resync(st, True, resyncs(a)[0]["drift_sec"], "2026-10-12T00:00:00Z",
                               None, t)
    assert st["cron_busy_alerted"] is False and conds(st) == []


def test_C9_NEGATIVE_busy_alert_not_rearmed_without_a_resync():
    st = slept_state(3600)
    st.update(cron_busy_alerted=True)                     # alerted in an earlier episode
    for i in range(1, 40):
        st, a = wd.evaluate(st, cobs(1000.0 + i * 120, procs=BUSY), NOW + i * 120, CFG)
        assert resyncs(a) == []
    assert st["cron_busy_since"] == NOW + 120 and "cron_drift_busy" not in conds(st)


def test_C10_NEGATIVE_config_off_never_resyncs_or_reads_top():
    cfg = dict(CFG, cron_resync=False)
    st = slept_state(10 * 3600)
    for i in range(1, 20):
        o = cobs(1000.0 + i * 120)
        assert wd.cron_wants_top(st, o, NOW + i * 120, cfg) is False
        st, a = wd.evaluate(st, o, NOW + i * 120, cfg)
        assert resyncs(a) == []
    assert st["cron_last_decision"] == "off" and "cron_drift_busy" not in conds(st)


def test_C11_NEGATIVE_pause_file_never_resyncs():
    st = slept_state(10 * 3600)
    for i in range(1, 20):
        o = cobs(1000.0 + i * 120, paused=True)
        assert wd.cron_wants_top(st, o, NOW + i * 120, CFG) is False
        st, a = wd.evaluate(st, o, NOW + i * 120, CFG)
        assert resyncs(a) == []
    assert st["cron_last_decision"] == "paused"


def test_C12_NEGATIVE_min_gap_and_daily_cap():
    st = slept_state(3600)
    st, a = wd.evaluate(st, cobs(1120.0), NOW + 120, CFG)
    assert len(resyncs(a)) == 1                                    # restart "failed": acc kept
    t = NOW + 120
    st, a = wd.evaluate(st, cobs(1120.0 + 599), t + 599, CFG)
    assert resyncs(a) == [] and st["cron_last_decision"] == "gap"
    st, a = wd.evaluate(st, cobs(1120.0 + 600), t + 600, CFG)
    assert len(resyncs(a)) == 1
    st = slept_state(3600)
    st["cron_resyncs"] = [NOW - 86000 + i * 700 for i in range(wd.CRON_RESYNC_MAX_PER_DAY)]
    st, a = wd.evaluate(st, cobs(1120.0), NOW + 120, CFG)
    assert resyncs(a) == [] and st["cron_last_decision"] == "cap"
    st, a = wd.evaluate(st, cobs(1120.0 + 400), NOW + 520, CFG)    # the oldest rolled off
    assert len(resyncs(a)) == 1


@pytest.mark.parametrize("kw", [dict(cerr="missing"), dict(cerr="inspect exit 1"),
                                dict(cerr="inspect TimeoutExpired"), dict(running=False),
                                dict(started=None), dict(procs=None, top_err="top exit 1"),
                                dict(procs=[])])
def test_C13_NEGATIVE_docker_cli_trouble_means_no_action_and_one_log(kw):
    st = slept_state(10 * 3600)
    logs = []
    for i in range(1, 6):
        st, a = wd.evaluate(st, cobs(1000.0 + i * 120, **kw), NOW + i * 120, CFG)
        assert resyncs(a) == [] and "cron_drift_busy" not in conds(st)
        logs += [x for x in a if x["type"] == "log" and "re-sync" in x.get("msg", "")]
    assert len(logs) == 1, "logged once, not every run"
    assert conds(st) == [], "no push for it"


def test_C14_inspect_and_top_never_raise(monkeypatch):
    class R:
        def __init__(self, rc, out="", err=""):
            self.returncode, self.stdout, self.stderr = rc, out, err
    seen = []

    def run(argv, timeout=20):
        seen.append(argv)
        return R(1, "", "Error response from daemon: No such object: cheetah-market-app-cron-1")
    monkeypatch.setattr(wd, "_run", run)
    assert wd.inspect_cron()["error"] == "missing"
    assert wd.top_cron() == {"procs": None, "error": "top exit 1"}
    monkeypatch.setattr(wd, "_run", lambda argv, timeout=20: R(1, "", "Cannot connect"))
    assert wd.inspect_cron()["error"] == "inspect exit 1"

    def boom(argv, timeout=20):
        raise subprocess.TimeoutExpired(argv, timeout)
    monkeypatch.setattr(wd, "_run", boom)
    assert wd.inspect_cron()["error"] == "inspect TimeoutExpired"
    assert wd.top_cron()["error"] == "top TimeoutExpired"
    monkeypatch.setattr(wd, "_run", lambda argv, timeout=20: R(0, STARTED + " true\n"))
    assert wd.inspect_cron() == {"started_at": STARTED, "running": True, "error": None}
    monkeypatch.setattr(wd, "_run", lambda argv, timeout=20: R(0, TOP_SAMPLE))
    assert wd.top_cron() == {"procs": IDLE, "error": None}
    assert seen[0] == ["/usr/local/bin/docker", "inspect", "-f",
                       "{{.State.StartedAt}} {{.State.Running}}", "cheetah-market-app-cron-1"]
    assert seen[1] == ["/usr/local/bin/docker", "top", "cheetah-market-app-cron-1", "-o", "pid,args"]


def test_C15_parsers():
    assert wd.parse_docker_top(TOP_SAMPLE) == IDLE
    assert wd.cron_busy_procs(IDLE) == []
    assert wd.cron_busy_procs(BUSY) == [JOB, "python -m supply_demand.zone_edge"]
    assert wd.parse_docker_top("PID   COMMAND\n") is None, "NEG: no lines is not idle"
    assert wd.parse_docker_top("") is None and wd.parse_docker_top(None) is None
    assert wd.cron_busy_procs(["[python] <defunct>", "/usr/bin/supercronicX x"]) == \
        ["[python] <defunct>", "/usr/bin/supercronicX x"]
    assert wd.parse_cron_inspect("2026-10-12T02:13:42.1Z false") == \
        {"started_at": "2026-10-12T02:13:42.1Z", "running": False, "error": None}
    for junk in ("", "true", "<no value> true", "2026-10-12T02:13:42Z maybe", "a b c"):
        assert wd.parse_cron_inspect(junk)["error"] == "unparsed", junk


def _cron_kw(tmp_path, obs_fn, *, restart=None, inspect=None, top=None):
    calls = {"top": 0, "restart": 0, "inspect": 0}

    def top_fn():
        calls["top"] += 1
        return top() if top else {"procs": IDLE, "error": None}

    def restart_fn():
        calls["restart"] += 1
        if restart:
            restart()

    def inspect_fn():
        calls["inspect"] += 1
        return inspect() if inspect else {"started_at": "2026-10-12T03:00:00.5Z", "running": True,
                                          "error": None}
    d = StubDeliver()
    kw = dict(observe_fn=obs_fn, deliver_fn=d, notify_fn=Rec(), restart_fn=Rec(),
              state_dir=str(tmp_path), cron_top_fn=top_fn, cron_restart_fn=restart_fn,
              cron_inspect_fn=inspect_fn,
              clock_fn=lambda: NOW + 30)       # second 30: clear of the minute edge (C30)
    return kw, calls, d


def test_C16_run_once_resync_success_zeroes_drift_logs_and_pushes_nothing(tmp_path):
    wd.save_state(str(tmp_path), slept_state(8 * 3600))
    kw, calls, d = _cron_kw(tmp_path, lambda c, n: cobs(1120.0, procs=None))
    assert wd.run_once(CFG, NOW + 120, **kw) == 0
    assert calls == {"top": 1, "restart": 1, "inspect": 1}
    st = wd.load_state(str(tmp_path))
    assert st["cron_sleep_acc_sec"] == 0.0
    assert st["cron_started_at"] == "2026-10-12T03:00:00.5Z"
    assert st["cron_last_resync"] == {"ts": NOW + 120, "drift_sec": 28800.0}
    assert d.calls == [], "no push on success"
    lines = [json.loads(x) for x in (tmp_path / "watchdog.log").read_text().splitlines()]
    hit = [x for x in lines if x["msg"] == "cron_resynced"]
    assert len(hit) == 1 and hit[0]["drift_sec"] == 28800.0 and hit[0]["drift_h"] == 8.0
    # the next run sees the new container and stays in sync: no second restart
    kw2, calls2, _ = _cron_kw(tmp_path, lambda c, n: cobs(1240.0, procs=None,
                                                         started="2026-10-12T03:00:00.5Z"))
    assert wd.run_once(CFG, NOW + 240, **kw2) == 0
    assert calls2 == {"top": 0, "restart": 0, "inspect": 0}


def test_C17_NEGATIVE_restart_failure_keeps_drift_and_alerts_once(tmp_path):
    wd.save_state(str(tmp_path), slept_state(3 * 3600))

    def fail():
        raise RuntimeError("docker restart exit 1: daemon not ready")
    d = StubDeliver()
    t, m = NOW, 1000.0
    for _ in range(4):                                             # every 10 min, 4 failures
        t, m = t + 600, m + 600
        kw, calls, _d = _cron_kw(tmp_path, lambda c, n, m=m: cobs(m, procs=None), restart=fail)
        kw["deliver_fn"] = d
        wd.run_once(CFG, t, **kw)
        assert calls["restart"] == 1 and calls["inspect"] == 0
        st = wd.load_state(str(tmp_path))
        assert st["cron_sleep_acc_sec"] == 3 * 3600, "drift kept for the next try"
        assert st["cron_last_resync"] is None
    assert [c["condition"] for c in d.calls] == ["watchdog_error"], "one alert for 4 failures"
    assert "Cron re-sync failed" in d.calls[0]["body"]
    assert (tmp_path / "watchdog.log").read_text().count('"cron resync failed"') == 4


def test_C17b_restart_failure_alert_text_and_once_a_day():
    st = slept_state(3 * 3600)
    st = wd.record_cron_resync(st, False, 3 * 3600, None, "TimeoutExpired", NOW)
    st = wd.record_cron_resync(st, False, 3 * 3600, None, "TimeoutExpired", NOW + 600)
    assert conds(st) == ["watchdog_error"]
    body = st["pending"][0]["body"]
    assert "Cron re-sync failed (TimeoutExpired)" in body and "3.0 h late" in body
    assert "forwarder" not in body
    assert st["cron_sleep_acc_sec"] == 3 * 3600
    st = wd.record_cron_resync(st, False, 3 * 3600, None, "x", NOW + 86400)
    assert conds(st) == ["watchdog_error", "watchdog_error"]


def test_C18_NEGATIVE_run_once_never_calls_docker_when_inspect_failed(tmp_path):
    wd.save_state(str(tmp_path), slept_state(9 * 3600))
    kw, calls, d = _cron_kw(tmp_path, lambda c, n: cobs(1120.0, cerr="missing", procs=None))
    assert wd.run_once(CFG, NOW + 120, **kw) == 0
    assert calls == {"top": 0, "restart": 0, "inspect": 0} and d.calls == []
    kw, calls, _ = _cron_kw(tmp_path, lambda c, n: cobs(1240.0, procs=None),
                            top=lambda: (_ for _ in ()).throw(OSError("gone")))
    assert wd.run_once(CFG, NOW + 240, **kw) == 0
    assert calls["top"] == 1 and calls["restart"] == 0
    kw, calls, _ = _cron_kw(tmp_path, lambda c, n: cobs(1360.0, procs=None),
                            top=lambda: {"procs": BUSY, "error": None})
    assert wd.run_once(CFG, NOW + 360, **kw) == 0
    assert calls["top"] == 1 and calls["restart"] == 0, "a running job is never interrupted"


def test_C19_old_v1_state_json_loads(tmp_path):
    live = {"alerted_at": None, "alerted_count": None, "battery_fired": [],
            "crash_notified_at": None,
            "down": {"alerted": False, "attempts": 0, "checks": 0, "since": None, "variant": None},
            "error_alerted_at": {}, "growth_alerted_at": None, "last_count": 57,
            "pending": [], "restarts": [], "run_id": "9696:1791079009",
            "samples": [[NOW - 600, 55], [NOW, 57]], "services_start": 1791079009.0, "version": 1}
    (tmp_path / "state.json").write_text(json.dumps(live))
    st = wd.load_state(str(tmp_path))
    assert st is not None and st["last_count"] == 57 and st["samples"] == live["samples"]
    assert st["cron_sleep_acc_sec"] == 0.0 and st["last_mono"] is None
    assert st["cron_started_at"] is None and st["cron_resyncs"] == []
    st, a = wd.evaluate(st, cobs(1000.0), NOW + 120, CFG)
    assert resyncs(a) == [] and st["cron_started_at"] == STARTED
    bad = dict(live, cron_sleep_acc_sec="lots", last_mono="x", cron_started_at=5,
               cron_resyncs=["a", NOW], cron_last_resync={"ts": "x"}, cron_busy_since=[1])
    (tmp_path / "state.json").write_text(json.dumps(bad))
    st = wd.load_state(str(tmp_path))
    assert (st["cron_sleep_acc_sec"], st["last_mono"], st["cron_started_at"]) == (0.0, None, None)
    assert st["cron_resyncs"] == [NOW] and st["cron_last_resync"] is None
    assert st["cron_busy_since"] is None
    assert wd.STATE_VERSION == 1


def test_C20_restart_argv_is_exact_and_never_a_shell(monkeypatch):
    seen = []

    def spy(argv, **kw):
        seen.append((argv, kw))
        return subprocess.CompletedProcess(argv, 0, "", "")
    monkeypatch.setattr(subprocess, "run", spy)
    wd.restart_cron()
    argv, kw = seen[0]
    assert argv == ["/usr/local/bin/docker", "restart", "-t", "120", "cheetah-market-app-cron-1"]
    assert kw["timeout"] == 150 and kw["timeout"] > wd.CRON_STOP_GRACE_SEC and "shell" not in kw
    monkeypatch.setattr(subprocess, "run",
                        lambda argv, **kw: subprocess.CompletedProcess(argv, 1, "", "no daemon"))
    with pytest.raises(RuntimeError):
        wd.restart_cron()


def test_C21_dry_run_and_status_show_the_drift(tmp_path, monkeypatch):
    wd.save_state(str(tmp_path), slept_state(5 * 3600))
    for name in ("restart_cron", "save_state", "deliver"):
        monkeypatch.setattr(wd, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError(name)))
    out = wd.dry_run(CFG, NOW + 120, observe_fn=lambda c, n: cobs(1120.0, procs=None),
                     state_dir=str(tmp_path), cron_top_fn=lambda: {"procs": IDLE, "error": None})
    assert resyncs(out["actions"]) == [{"type": "cron_resync", "drift_sec": 18000.0}]
    assert out["cron"]["sleep_acc_sec"] == 18000.0 and out["cron"]["decision"] == "resync"
    assert out["cron"]["resync_at_sec"] == wd.CRON_RESYNC_AT_SEC
    json.dumps(out, default=str)
    s = wd.status(str(tmp_path))
    assert s["cron"]["sleep_acc_sec"] == 18000.0 and s["cron"]["started_at"] == STARTED
    assert set(s["cron"]) == {"started_at", "sleep_acc_sec", "resync_at_sec", "decision",
                              "busy_since", "busy_alerted", "resyncs_24h", "last_resync"}


def test_C22_config_cron_resync_key(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"cron_resync": False}))
    cfg, notes = wd.load_config(str(tmp_path))
    assert cfg["cron_resync"] is False and notes == []
    (tmp_path / "config.json").write_text(json.dumps({"cron_resync": "no"}))
    cfg, notes = wd.load_config(str(tmp_path))
    assert cfg["cron_resync"] is True and notes == ["config.json: cron_resync must be true/false; "
                                                     "kept the default"]
    assert wd.load_config(str(tmp_path / "none"))[0]["cron_resync"] is True


def test_C23_NEGATIVE_obs_without_cron_fields_changes_nothing():
    st, a = wd.evaluate(slept_state(9 * 3600), obs(), NOW + 120, CFG)
    assert resyncs(a) == [] and st["cron_sleep_acc_sec"] == 9 * 3600
    assert (st["last_wall"], st["last_mono"]) == (NOW, 1000.0), "no monotonic -> no baseline move"


def test_C24_compose_cron_drift_busy_and_watchdog_error_default():
    t, b = wd.compose("cron_drift_busy", {"drift": 22.4 * 3600, "waited": 1900, "cmd": JOB})
    assert "22.4 h" in t and "22.4 h" in b and "32 min" in b and "zone_edge" in b
    assert len(t) <= wd.TITLE_MAX and len(b) <= wd.BODY_MAX
    _, b = wd.compose("watchdog_error", {"reason": "x"})
    assert b == "x. It cannot see the forwarder count until this is fixed (see ops/README.md)."


def test_C25_server_accepts_every_watchdog_condition():
    src = (ROOT / "backend" / "push" / "hooks.py").read_text()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "OPS_CONDITIONS":
            server = {e.value for e in node.value.args[0].elts}
            break
    else:
        raise AssertionError("OPS_CONDITIONS not found")
    assert server == set(wd.CONDITIONS)


def test_C26_cron_constants_are_the_reviewed_values():
    assert (wd.CRON_RESYNC_AT_SEC, wd.CRON_SLEEP_JITTER_SEC, wd.CRON_BUSY_ALERT_SEC,
            wd.CRON_RESYNC_MIN_GAP_SEC, wd.CRON_RESYNC_MAX_PER_DAY, wd.CRON_RESTART_TIMEOUT_SEC,
            wd.CRON_CMD_MAX) == (120, 5, 1800, 600, 12, 150, 80)
    assert (wd.CRON_STOP_GRACE_SEC, wd.CRON_EDGE_LEAD_SEC, wd.CRON_EDGE_TRAIL_SEC) == (120, 3, 3)
    assert (wd.DOCKER_CLI, wd.CRON_CONTAINER) == ("/usr/local/bin/docker",
                                                  "cheetah-market-app-cron-1")


# --------------------------------------------------------------------------- verifier 2026-10-11
# 1 time.monotonic() restarts near 0 in every launchd process on Python 3.9 -> the
#   boot-relative CLOCK_UPTIME_RAW; 2 `docker restart -t 120` + no restart at a
#   minute edge; 3 a new StartedAt keeps this interval's sleep; 4 ... and re-arms
#   the busy alert; 5 null cron_resyncs / cron_logged_at in state.json.
def _quiet_observe(monkeypatch):
    def no_run(argv, timeout=20):
        raise OSError("no subprocess in tests")
    monkeypatch.setattr(wd, "_run", no_run)
    monkeypatch.setattr(wd, "read_forwarder", lambda d: {"count": None, "ts": None,
                                                         "source": None, "error": "missing"})
    monkeypatch.setattr(wd, "_api_ok", lambda base, opener=None: True)
    monkeypatch.setattr(wd, "inspect_cron", lambda: {"started_at": STARTED, "running": True,
                                                     "error": None})


def test_C27_observe_reads_clock_uptime_raw_never_monotonic(monkeypatch, tmp_path):
    _quiet_observe(monkeypatch)
    monkeypatch.setattr(wd.time, "CLOCK_UPTIME_RAW", 8, raising=False)
    seen = []

    def gettime(clk):
        seen.append(clk)
        return 189_720.5
    monkeypatch.setattr(wd.time, "clock_gettime", gettime)
    monkeypatch.setattr(wd.time, "monotonic",
                        lambda: (_ for _ in ()).throw(AssertionError("time.monotonic used")))
    o = wd.observe(dict(CFG, state_dir=str(tmp_path)), NOW)
    assert o["mono"] == 189_720.5 and seen == [8]
    tree = ast.parse(WD_PATH.read_text())
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                and n.attr == "monotonic"], "NEG: no time.monotonic() anywhere"


def test_C27b_NEGATIVE_unavailable_uptime_clock_gives_mono_none(monkeypatch, tmp_path):
    _quiet_observe(monkeypatch)
    monkeypatch.setattr(wd.time, "CLOCK_UPTIME_RAW", 8, raising=False)
    monkeypatch.setattr(wd.time, "clock_gettime",
                        lambda clk: (_ for _ in ()).throw(OSError(22, "EINVAL")))
    assert wd.uptime_raw() is None
    assert wd.observe(dict(CFG, state_dir=str(tmp_path)), NOW)["mono"] is None
    monkeypatch.delattr(wd.time, "CLOCK_UPTIME_RAW", raising=False)      # Linux / old Python
    monkeypatch.setattr(wd.time, "clock_gettime", lambda clk: 5.0)
    assert wd.uptime_raw() is None


@pytest.mark.parametrize("bad", [None, "x", True])
def test_C28_NEGATIVE_mono_none_never_accumulates(bad):
    st = slept_state(100)
    for i in range(1, 300):                                # 10 h of wall, clock unknown
        o = cobs(bad, procs=None)
        assert wd.cron_wants_top(st, o, NOW + i * 120 + 3600, CFG) is False
        st, a = wd.evaluate(st, cobs(bad), NOW + i * 120 + 3600, CFG)
        assert resyncs(a) == []
    assert st["cron_sleep_acc_sec"] == 100.0 and st["cron_last_decision"] == "in_sync"


def test_C29_minute_edge_seconds():
    base = NOW - NOW % 60
    skip = [s for s in range(60) if wd.cron_minute_edge(base + s + 0.9)]
    assert skip == [0, 1, 2, 3, 57, 58, 59]
    assert wd.cron_minute_edge(base + 4) is False and wd.cron_minute_edge(base + 56.99) is False


def test_C30_NEGATIVE_minute_edge_defers_the_restart_and_the_next_run_does_it(tmp_path, monkeypatch):
    assert NOW % 60 == 0
    wd.save_state(str(tmp_path), slept_state(8 * 3600))
    kw, calls, d = _cron_kw(tmp_path, lambda c, n: cobs(1120.0, procs=None))
    kw["clock_fn"] = lambda: NOW + 120 + 58                 # second 58, a stuck clock
    slept = []
    monkeypatch.setattr(wd, "_sleep", slept.append)
    assert wd.run_once(CFG, NOW + 120, **kw) == 0
    assert slept == [6.0], "waited in-process for second 4 before deferring"
    assert calls == {"top": 1, "restart": 0, "inspect": 0}, "no restart at :58"
    st = wd.load_state(str(tmp_path))
    assert st["cron_resyncs"] == [], "a deferred try does not count toward gap / cap"
    assert st["cron_sleep_acc_sec"] == 8 * 3600 and st["cron_last_decision"] == "edge"
    assert d.calls == []
    runs = [json.loads(x) for x in (tmp_path / "watchdog.log").read_text().splitlines()
            if '"run"' in x]
    assert runs[-1]["cron"] == "edge"
    kw, calls, _ = _cron_kw(tmp_path, lambda c, n: cobs(1240.0, procs=None))
    kw["clock_fn"] = lambda: NOW + 240 + 2                  # second 2: still skipped
    wd.run_once(CFG, NOW + 240, **kw)
    assert calls["restart"] == 0
    kw, calls, _ = _cron_kw(tmp_path, lambda c, n: cobs(1360.0, procs=None))
    kw["clock_fn"] = lambda: NOW + 360 + 4                  # second 4: restart
    wd.run_once(CFG, NOW + 360, **kw)
    assert calls["restart"] == 1
    assert wd.load_state(str(tmp_path))["cron_sleep_acc_sec"] == 0.0


def test_C31_deploy_then_8_h_sleep_resyncs_once_when_idle():
    st, _ = wd.evaluate(None, cobs(1000.0), NOW, CFG)             # old container, in sync
    new = "2026-10-12T02:13:42.197244003Z"                        # deploy at +60, lid at +90
    t = NOW + 8 * 3600 + 120
    st, a = wd.evaluate(st, cobs(1120.0, started=new), t, CFG)    # wall +8 h 2 min, uptime +2 min
    assert st["cron_started_at"] == new
    assert st["cron_sleep_acc_sec"] == pytest.approx(8 * 3600)
    assert [round(r["drift_sec"]) for r in resyncs(a)] == [8 * 3600]
    hit = [x for x in a if x.get("msg") == "cron container restarted; drift reset"]
    assert hit and hit[0]["kept_sec"] == 8 * 3600 and hit[0]["dropped_sec"] == 0
    st = wd.record_cron_resync(st, True, resyncs(a)[0]["drift_sec"], "2026-10-12T10:16:00Z",
                               None, t)
    st, a = wd.evaluate(st, cobs(1240.0, started="2026-10-12T10:16:00Z"), t + 120, CFG)
    assert resyncs(a) == [], "one re-sync, not two"


def test_C31b_NEGATIVE_deploy_then_sleep_with_a_job_running_waits():
    st, _ = wd.evaluate(None, cobs(1000.0), NOW, CFG)
    st, a = wd.evaluate(st, cobs(1120.0, started="2026-10-12T02:13:42Z", procs=BUSY),
                        NOW + 8 * 3600 + 120, CFG)
    assert resyncs(a) == [] and st["cron_last_decision"] == "busy"
    assert st["cron_sleep_acc_sec"] == pytest.approx(8 * 3600)


def test_C32_new_started_at_rearms_the_busy_alert_and_drops_the_pending_one():
    st = slept_state(3600)
    st["cron_busy_alerted"] = True
    st["cron_busy_since"] = NOW - 4000
    wd._queue(st, "cron_drift_busy", {"drift": 3600, "waited": 1900, "cmd": JOB}, NOW - 100)
    wd._queue(st, "watchdog_error", {"reason": "other"}, NOW - 100)
    same, _ = wd.evaluate(copy_state(st), cobs(1120.0, procs=BUSY), NOW + 120, CFG)
    assert same["cron_busy_alerted"] is True, "NEG: same container keeps the latch"
    assert conds(same) == ["cron_drift_busy", "watchdog_error"]
    st, _ = wd.evaluate(st, cobs(1120.0, started="2026-10-12T02:13:42Z", procs=BUSY),
                        NOW + 120, CFG)
    assert st["cron_busy_alerted"] is False and conds(st) == ["watchdog_error"]
    assert st["cron_busy_since"] is None or st["cron_busy_since"] == NOW + 120


def copy_state(st):
    return json.loads(json.dumps(st))


@pytest.mark.parametrize("bad", [dict(cron_resyncs=None), dict(cron_logged_at=None),
                                 dict(cron_resyncs=None, cron_logged_at=None),
                                 dict(cron_resyncs="x", cron_logged_at=[1]),
                                 dict(cron_logged_at={"no_top": "x", "paused": NOW})])
def test_C33_NEGATIVE_null_or_wrong_cron_lists_in_state_json_never_crash(tmp_path, bad):
    raw = dict(slept_state(9 * 3600), **bad)
    (tmp_path / "state.json").write_text(json.dumps(raw))
    st = wd.load_state(str(tmp_path))
    assert isinstance(st["cron_resyncs"], list) and isinstance(st["cron_logged_at"], dict)
    assert all(isinstance(v, float) for v in st["cron_logged_at"].values())
    tops = [lambda: {"procs": None, "error": "top exit 1"},      # no_top -> _log_once
            lambda: {"procs": IDLE, "error": None}]               # resync -> cron_resyncs
    for i, top in enumerate(tops, 1):
        kwr, calls, _ = _cron_kw(tmp_path, lambda c, n, i=i: cobs(1000.0 + i * 120, procs=None),
                                 top=top)
        assert wd.run_once(CFG, NOW + i * 120, **kwr) == 0, "exit 3 = crashed"
        assert calls["top"] == 1
    assert calls["restart"] == 1
    assert "unexpected exception" not in (tmp_path / "watchdog.log").read_text()


# ── C34: the minute edge waits in-process instead of skipping the run ─────
# (critic 2026-10-11: launchd keeps each run on ~the same second, so "retry next run"
#  could skip ~12 runs / ~25 min after a wake.)

def test_C34_edge_wait_seconds():
    base = NOW - NOW % 60
    waits = {s: wd.cron_edge_wait(base + s + 0.2) for s in (56, 57, 58, 59, 0, 1, 3, 4, 30)}
    assert waits == {56: 0.0, 57: 7.0, 58: 6.0, 59: 5.0, 0: 4.0, 1: 3.0, 3: 1.0, 4: 0.0, 30: 0.0}
    assert max(wd.cron_edge_wait(base + s) for s in range(60)) <= 7.0


def test_C34b_edge_wait_then_restart_in_the_same_run(tmp_path, monkeypatch):
    wd.save_state(str(tmp_path), slept_state(8 * 3600))
    kw, calls, d = _cron_kw(tmp_path, lambda c, n: cobs(1120.0, procs=None))
    clock = {"t": NOW + 120 + 58}                           # second 58 ...
    slept = []

    def fake_sleep(sec):
        slept.append(sec)
        clock["t"] += sec                                   # ... then second 4
    monkeypatch.setattr(wd, "_sleep", fake_sleep)
    kw["clock_fn"] = lambda: clock["t"]
    assert wd.run_once(CFG, NOW + 120, **kw) == 0
    assert slept == [6.0] and calls["restart"] == 1
    st = wd.load_state(str(tmp_path))
    assert st["cron_sleep_acc_sec"] == 0.0 and st["cron_last_decision"] != "edge"


def test_C34c_NEGATIVE_clear_second_never_sleeps(tmp_path, monkeypatch):
    wd.save_state(str(tmp_path), slept_state(8 * 3600))
    kw, calls, _ = _cron_kw(tmp_path, lambda c, n: cobs(1120.0, procs=None))
    slept = []
    monkeypatch.setattr(wd, "_sleep", slept.append)
    wd.run_once(CFG, NOW + 120, **kw)                       # helper clock: second 30
    assert slept == [] and calls["restart"] == 1


def test_C35_NEGATIVE_null_error_alerted_at_loads(tmp_path):
    st = wd.default_state()
    st["error_alerted_at"] = None
    (tmp_path / "state.json").write_text(json.dumps(st))
    got = wd.load_state(str(tmp_path))
    assert got is not None and got["error_alerted_at"] == {}
