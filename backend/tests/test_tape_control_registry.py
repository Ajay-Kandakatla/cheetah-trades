"""🎚️ tape_control — the registrations (BUILD_SPEC7 §3.9 / §3.10, WP-B, 2026-10-16).

Ajay 2026-10-16: "Can you add a watcher tape for IREN please." then "I wwant you to
alert me when the Buyers are winning in tape for IREN today."

The kind lives in orderflow/tape_control.py (WP-A). This file pins every place
that has to KNOW the kind: the owner keep-set + default_prefs, the market-day
gate, GET /alerts/status, the item url, the health audit's heartbeat, the cli
help and the ℹ️ rules line. NEGATIVES marked.
"""
from __future__ import annotations

import ast
import builtins
import inspect
import json
import re
import time
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from orderflow import tape as TP
from orderflow import tape_control as TC
from orderflow import trade_flash as TF
from push import recent as R
from push import subs
from supply_demand import alert_status as AS
from supply_demand import rules_info as RI

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 16, 11, 0, tzinfo=ET)
OWNER = "owner-local-part" + chr(64) + "example.com"
OTHER = "someone-else" + chr(64) + "example.com"


# ── push/subs.py ─────────────────────────────────────────────────────────────
def test_the_kind_is_owner_only_and_on_for_him(monkeypatch):
    monkeypatch.setenv("OWNER_EMAIL", OWNER)
    # NARROWED 2026-10-29 — Ajay: "Only give me Gajjalas chart notifications from both tabs" (BUILD_SPEC29 D1: the keep-set is the six)
    assert TC.KIND not in subs.OWNER_KEEP_SET
    assert subs.default_prefs()[TC.KIND] is False
    assert subs.owner_prefs()[TC.KIND] is False
    assert subs.prefs_for(OWNER)[TC.KIND] is False


def test_NEGATIVE_prefs_for_anyone_else_is_off(monkeypatch):
    monkeypatch.setenv("OWNER_EMAIL", OWNER)
    assert subs.prefs_for(OTHER)[TC.KIND] is False
    assert subs.prefs_for(None)[TC.KIND] is False


def test_owner_prefs_apply_turns_it_on():
    from scripts import owner_prefs_apply as S
    prefs = dict(subs.default_prefs())
    prefs.pop(TC.KIND)
    doc = {"_id": 1, "user_email": OWNER, "label": "iPhone", "kind": "web",
           "endpoint": "https://push.example/aaa", "prefs": prefs}
    out = S.apply([doc], owner=OWNER, apply=False)
    assert out["rows"][0]["changes"][TC.KIND] == [None, False]      # NARROWED 2026-10-29 (the six-kind keep-set)


def test_NEGATIVE_a_non_owner_device_is_untouched():
    from scripts import owner_prefs_apply as S
    doc = {"_id": 2, "user_email": OTHER, "prefs": dict(subs.default_prefs())}
    out = S.apply([doc], owner=OWNER, apply=False)
    assert out["untouched"] == 1 and out["rows"] == [] and out["changed"] == 0


# ── market_hours/gate.py ─────────────────────────────────────────────────────
def test_a_market_kind_silent_on_closed_days(monkeypatch):
    from market_hours import gate
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    assert TC.KIND in gate.MARKET_ALERT_KINDS
    assert TC.KIND not in gate.PERSONAL_KINDS, "NEGATIVE: not a personal kind"
    assert gate.should_drop_kind(TC.KIND, datetime(2026, 9, 7, 10, 0, tzinfo=ET)) == "holiday 2026-09-07"
    assert gate.should_drop_kind(TC.KIND, datetime(2026, 10, 17, 11, 0, tzinfo=ET)) == "weekend"
    assert gate.should_drop_kind(TC.KIND, datetime(2026, 10, 13, 11, 0, tzinfo=ET)) is None


# ── supply_demand/alert_status.py ────────────────────────────────────────────
def test_the_status_kind_is_typed_equal_to_the_module():
    assert AS.TAPE_CONTROL_KIND == TC.KIND
    assert TC.KIND in AS.PASS_KINDS
    assert TC.KIND not in AS.TAPE_KINDS and TC.KIND not in AS.DAILY_PASS_KINDS
    assert AS.CADENCE_SEC[TC.KIND] == 300


class PassColl:
    def find_one(self, q):
        return None


class StateColl:
    def __init__(self, docs):
        self.docs = docs
        self.queries = []

    def find(self, q):
        self.queries.append(q)
        return [d for d in self.docs if all(d.get(k) == v for k, v in q.items())]


class Broken:
    def find(self, q):
        raise RuntimeError("mongo down")

    def find_one(self, q):
        raise RuntimeError("mongo down")


def _state_doc():
    read = {"at": "2026-10-16T10:12:00-04:00", "hhmm": "10:12", "hms": "10:12:00", "in_control": True,
            "delta": 1_250_000, "late_delta": 40_000, "pct": 4.2, "late_window_min": TP.LATE_WINDOW_MIN,
            "n_trades": 120_000, "price": 41.37, "last_print_et": "10:11:58", "method": "tick"}
    return {"_id": "IREN:2026-10-16", "symbol": "IREN", "date": "2026-10-16", "kind": TC.KIND,
            "until": "2026-10-16", "rev": 2, "in_control": True, "since": read["at"], "since_hhmm": "10:12",
            "last_read": read, "last_read_at": read["at"], "faults": 0, "last_fault": None,
            "rings": [{"at": read["at"], "hhmm": "10:12", "event_id": "IREN:2026-10-16:10:12:00",
                       "pushed": True}],
            "rang": True, "push_attempts": 0, "first_read": False}


def test_status_payload_serves_window_pins_and_note(monkeypatch):
    monkeypatch.setattr(TC, "WATCH", {"IREN": "2026-10-16"})
    doc = _state_doc()
    coll = StateColl([doc])
    p = AS.status_payload(pass_coll=PassColl(), latest_coll=PassColl(), now=NOW, tape_control_coll=coll)
    tc = p["passes"][TC.KIND]
    assert tc["cadence_sec"] == 300 and tc["window"] == AS.tape_window()
    assert tc["window"] == {"open": TF.WATCH_OPEN_ET.strftime("%H:%M"),
                            "close": TF.WATCH_CLOSE_ET.strftime("%H:%M")}
    pin = tc["pins"][0]
    pin_meta = TC.pins_for("2026-10-16")[0]
    assert pin["text"] == TC.pin_text(pin_meta, doc, NOW)[1], "served words, not recomposed"
    assert pin["state"] == "in_control" and pin["rang"] == ["10:12"]
    assert pin["url"] == TC.tape_url("IREN") == "/sepa/IREN?tab=tape&from=alerts"
    assert tc["note"] == TC.UNMEASURED_NOTE + " " + TC.RULE_NOTE
    assert tc["as_of"] is None and tc["counts"] == {}
    assert coll.queries == [{"date": "2026-10-16", "kind": TC.KIND}]
    json.dumps(p, allow_nan=False)


def test_NEGATIVE_a_dead_state_store_is_waiting_pins_never_a_500(monkeypatch):
    monkeypatch.setattr(TC, "WATCH", {"IREN": "2026-10-16"})
    p = AS.status_payload(pass_coll=Broken(), latest_coll=Broken(), now=NOW, tape_control_coll=Broken())
    tc = p["passes"][TC.KIND]
    assert [x["state"] for x in tc["pins"]] == ["waiting"]
    assert tc["note"] == TC.UNMEASURED_NOTE + " " + TC.RULE_NOTE
    assert tc["as_of"] is None and tc["counts"] == {}
    json.dumps(p, allow_nan=False)


def test_NEGATIVE_a_broken_status_block_is_no_pins_never_a_500(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("status_block blew up")
    monkeypatch.setattr(TC, "status_block", boom)
    assert AS.read_tape_control(StateColl([]), NOW) == {"pins": [], "note": None}


def test_alert_status_stays_a_leaf():
    src = (ROOT / "supply_demand" / "alert_status.py").read_text()
    head = src[:src.index("def _coll")]
    code = [ln for ln in head.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    assert not [ln for ln in code if re.match(r"\s*(from|import)\s+orderflow\b", ln)], \
        "NEGATIVE: no module-level orderflow import in alert_status.py"


# ── push/recent.py ───────────────────────────────────────────────────────────
def test_the_item_url_is_the_modules():
    assert R.item_url(TC.KIND, "IREN") == TC.tape_url("IREN") == "/sepa/IREN?tab=tape&from=alerts"
    assert R.ITEM_URL_BY_KIND[TC.KIND] == TC.URL_FMT
    assert TC.KIND in R.ITEM_KINDS


# ── observability/health_audit.py ────────────────────────────────────────────
class _HB:
    def __init__(self, docs):
        self.docs = docs

    def find_one(self, q):
        return next((d for d in self.docs if d["name"] == q["name"]), None)


class _HDB:
    def __init__(self, docs):
        self.engine_heartbeat = _HB(docs)


def test_health_audit_beats_its_own_name(monkeypatch):
    from observability import health_audit as ha
    assert ha.check_tape_control_heartbeat in ha.CHECKS
    monkeypatch.setattr(ha, "_now_et", lambda: datetime(2026, 10, 16, 12, 0))
    monkeypatch.setattr(ha, "_mongo_db", lambda: _HDB([{"name": TC.KIND, "ts": time.time() - 3 * 60}]))
    r = ha.check_tape_control_heartbeat()
    assert r["ok"] is True and r["name"] == TC.KIND
    monkeypatch.setattr(ha, "_mongo_db", lambda: _HDB([{"name": TC.KIND, "ts": time.time() - 45 * 60}]))
    r = ha.check_tape_control_heartbeat()
    assert r["ok"] is False and r["severity"] == ha.WARN and "Tape buyers-in-control" in r["detail"]
    monkeypatch.setattr(ha, "_now_et", lambda: datetime(2026, 10, 16, 17, 0))
    assert ha.check_tape_control_heartbeat()["ok"] is True, "out of session: vacuous"


def test_NEGATIVE_trade_flashs_beat_is_not_this_kinds(monkeypatch):
    from observability import health_audit as ha
    monkeypatch.setattr(ha, "_now_et", lambda: datetime(2026, 10, 16, 12, 0))
    monkeypatch.setattr(ha, "_mongo_db", lambda: _HDB([{"name": "trade_flash", "ts": time.time()},
                                                        {"name": "tape_burst_highbeta", "ts": time.time()}]))
    r = ha.check_tape_control_heartbeat()
    assert r["ok"] is False and "ever recorded" in r["detail"]


# ── sepa/cli.py ──────────────────────────────────────────────────────────────
def test_the_cli_help_names_the_kind():
    src = (ROOT / "sepa" / "cli.py").read_text()
    i = src.index('"trade-flash-watch",\n        help=')
    j = src.index('s_tf.add_argument("--dry-run"')
    block = src[i:j]
    assert "tape_burst_highbeta,tape_burst_chartmaps,tape_control" in block
    assert "orderflow/tape_control.py" in block


# ── supply_demand/rules_info.py ──────────────────────────────────────────────
def _tc_lines():
    return [ln for ln in RI.sections()["alerts"]["alerts"] if (TC.MARK + " " + TC.KIND) in ln]


@pytest.fixture
def today(monkeypatch):
    monkeypatch.setattr(TC, "et_today", lambda: "2026-10-16")
    return "2026-10-16"


def test_the_rules_line_is_built_from_the_constants(today):
    lines = _tc_lines()
    assert len(lines) == 1
    line = lines[0]
    active = [p["symbol"] for p in TC.pins_for(TC.et_today()) if p["active"]]
    assert active, "today's pin must be active for this read"
    for sym in active:
        assert sym in line
    assert "last %d minutes" % TP.LATE_WINDOW_MIN in line
    assert "every %d min" % (AS.CADENCE_SEC[TC.KIND] // 60) in line
    assert "%s–%s ET" % (TF.WATCH_OPEN_ET.strftime("%H:%M"), TF.WATCH_CLOSE_ET.strftime("%H:%M")) in line
    assert TC.RULE_WORD in line and TC.UNMEASURED_NOTE in line
    assert "ships OFF" in line and "ON for you by default" not in line   # NARROWED 2026-10-29 — read from the keep-set
    banned = "|".join(("bo" + "un", "fa" + "ke", r"\bbuy\b", r"\benter", "shadow"))
    assert not re.search(banned, line, re.I)


def test_the_rules_line_is_appended_after_the_four_non_zone_lines(today):
    alerts = RI.sections()["alerts"]["alerts"]
    assert alerts[:len(RI._non_zone_push_lines())] == RI._non_zone_push_lines()
    assert alerts[-1] == _tc_lines()[0]


@pytest.mark.parametrize("mutate, expect", [
    ("late", "last 45 minutes"),
    ("cadence", "every 10 min"),
    ("open", "09:35–"),
    ("standing", "NBIS (standing)"),
    ("ended", "no pinned name"),
])
def test_mutating_a_constant_moves_the_rules_line(today, monkeypatch, mutate, expect):
    if mutate == "late":
        monkeypatch.setattr(TP, "LATE_WINDOW_MIN", 45)
    elif mutate == "cadence":
        monkeypatch.setitem(AS.CADENCE_SEC, TC.KIND, 600)
    elif mutate == "open":
        monkeypatch.setattr(TF, "WATCH_OPEN_ET", dtime(9, 35))
    elif mutate == "standing":
        monkeypatch.setattr(TC, "WATCH", {"NBIS": None})
    elif mutate == "ended":
        monkeypatch.setattr(TC, "WATCH", {"IREN": "2000-01-03"})
    line = _tc_lines()[0]
    assert expect in line
    if mutate == "ended":
        assert "IREN" not in line, "NEGATIVE: an ended pin is never named"


def test_NEGATIVE_no_date_and_no_numeric_literal_in_the_rules_line(today):
    line = _tc_lines()[0]
    assert not re.search(r"\d{4}-\d{2}-\d{2}", line)
    tree = ast.parse(inspect.getsource(RI._tape_control_lines).lstrip())
    lits = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
    assert lits == []
    # WIDENED 2026-10-16 (AMENDMENTS7 A3): the retry clause prints TC.MAX_PUSH_ATTEMPTS — a constant's value, not a literal.
    allowed = {str(TP.LATE_WINDOW_MIN), str(AS.CADENCE_SEC[TC.KIND] // 60), str(TC.MAX_PUSH_ATTEMPTS)}
    allowed |= set(re.findall(r"\d+", TF.WATCH_OPEN_ET.strftime("%H:%M") + " " + TF.WATCH_CLOSE_ET.strftime("%H:%M")))
    allowed |= set(re.findall(r"\d+", TC.UNMEASURED_NOTE))
    assert set(re.findall(r"\d+", line)) <= allowed, set(re.findall(r"\d+", line)) - allowed


def test_NEGATIVE_a_kind_not_on_never_claims_on(today, monkeypatch):
    monkeypatch.setattr(subs, "owner_prefs", lambda: {})
    line = _tc_lines()[0]
    assert "ships OFF" in line and "ON for you" not in line


def test_NEGATIVE_a_broken_tape_control_import_drops_only_its_line(today, monkeypatch):
    real = builtins.__import__

    def stub_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "orderflow" and fromlist and "tape_control" in fromlist:
            raise ImportError("tape_control unavailable")
        if name == "orderflow.tape_control":
            raise ImportError("tape_control unavailable")
        return real(name, globals, locals, fromlist, level)
    monkeypatch.setattr(builtins, "__import__", stub_import)
    assert RI._tape_control_lines() == []
    alerts = RI.sections()["alerts"]["alerts"]
    monkeypatch.setattr(builtins, "__import__", real)
    assert alerts == RI._non_zone_push_lines()
    assert len(alerts) == 4
