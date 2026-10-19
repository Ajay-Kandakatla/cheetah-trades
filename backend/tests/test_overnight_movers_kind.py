"""🌙 overnight_movers — the push / alert registries (BUILD_SPEC16 WP-B, 2026-10-19).

Ajay 2026-10-19 (verbatim): "Can you do an over night scan for all the stocks they are all growing over night".

D8 + AMENDMENTS16 A2 (HIS CALL #1): a NEW kind, owner-only, one per session at 06:45 ET — and it ships OFF: False in
default_prefs and NOT in OWNER_KEEP_SET (he asked for a scan, not an alert; the capital_quality_upgrade precedent).
This file pins every registry the kind must be in — and every one it must NOT be in (the test_gajjala_potential_kind
shape).
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_hours import gate                    # noqa: E402
from overnight import push as OP                 # noqa: E402
from push import hooks, recent as R, sender, subs   # noqa: E402
from supply_demand import alert_status as AS     # noqa: E402

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]
KIND = "overnight_movers"
LABOR_DAY = datetime(2026, 9, 7, 6, 45, tzinfo=ET)
SATURDAY = datetime(2026, 10, 17, 6, 45, tzinfo=ET)
MONDAY = datetime(2026, 10, 19, 6, 45, tzinfo=ET)
WP_A_LANDED = (ROOT / "backend/overnight/scan.py").exists()


@pytest.fixture()
def no_override(monkeypatch):
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)


# ── the constants ────────────────────────────────────────────────────────────
def test_the_kind_and_its_constants():
    from trading.safety_floor import MIN_SHARE_PRICE
    assert OP.KIND == KIND
    assert OP.SLOT_ET == "06:45" and OP.PUSH_TOP_N == 5 and OP.PUSH_MIN_ON_DOLLAR == 250_000
    assert OP.PUSH_MIN_PRICE is MIN_SHARE_PRICE                      # the house floor BY NAME
    assert OP.URL == "/chart-maps?tab=overnight&on_sub=session"


def test_NEGATIVE_push_module_never_imports_the_scan_at_module_level():
    """alert_status.schedule_map imports overnight.push lazily on every /alerts/status; the scan pulls the Massive /
    Alpaca stack. It is imported inside the functions that need it, never at the top."""
    src = (ROOT / "backend/overnight/push.py").read_text()
    top = [ln for ln in src.splitlines() if re.match(r"(from|import)\s", ln)]
    assert top, "the module has top-level imports"
    assert not [ln for ln in top if "overnight" in ln or ln.startswith("from .")], top
    # NEGATIVE: never the pre-market gap tracker (pandas / daytrading), anywhere in the module
    assert not re.search(r"import\s+movers|overnight\.movers|from\s+\.movers", src)


# ── push/subs.py ─────────────────────────────────────────────────────────────
def test_ships_off_for_everyone_and_for_the_owner(monkeypatch):
    monkeypatch.setenv("OWNER_EMAIL", "ajaykandakatla@gmail.com")
    assert subs.default_prefs()[KIND] is False
    assert subs.owner_prefs()[KIND] is False
    assert subs.prefs_for("ajaykandakatla@gmail.com")[KIND] is False
    assert subs.prefs_for("someone.else@example.com")[KIND] is False


def test_NEGATIVE_not_in_the_keep_set_not_hard_stopped_not_retired():
    """HIS CALL #1 = OFF: not in OWNER_KEEP_SET. Registered-but-disabled would be a toggle that can never fire."""
    assert KIND not in subs.OWNER_KEEP_SET
    assert KIND not in subs.DISABLED_ALERT_KINDS
    assert KIND not in subs.RETIRED_2026_09_20


def test_NEGATIVE_owner_prefs_apply_neither_turns_it_on_nor_off():
    from scripts import owner_prefs_apply as S
    assert KIND not in S.on_kinds() and KIND not in S.off_kinds()


# ── push/hooks.py ────────────────────────────────────────────────────────────
def test_hook_routes_to_the_owner_under_its_own_kind(monkeypatch):
    calls = []
    monkeypatch.setattr(sender, "send_to_user",
                        lambda email, payload, kind=None: calls.append((email, payload, kind)) or
                        {"sent": 0, "failed": 0, "total_targets": 0})
    payload = {"title": "🌙 Overnight movers — AAA +3.1%", "body": "x", "url": OP.URL}
    r = hooks.notify_overnight_movers(owner="owner@example.com", payload=payload)
    assert r == {"sent": 0, "failed": 0, "total_targets": 0}
    assert calls == [("owner@example.com", payload, KIND)]


def test_NEGATIVE_the_hook_never_routes_untyped(monkeypatch):
    calls = []
    monkeypatch.setattr(sender, "send_to_user", lambda email, payload, kind=None: calls.append(kind) or {"sent": 0})
    hooks.notify_overnight_movers(owner="o@example.com", payload={})
    assert calls == [KIND] and None not in calls


# ── market_hours/gate.py ─────────────────────────────────────────────────────
def test_a_market_kind_silent_on_weekends_and_holidays(no_override):
    assert KIND in gate.MARKET_ALERT_KINDS
    assert KIND not in gate.PERSONAL_KINDS                          # NEGATIVE: never a closed-day kind
    assert gate.should_drop_kind(KIND, LABOR_DAY) == "holiday 2026-09-07"
    assert gate.should_drop_kind(KIND, SATURDAY) == "weekend"
    assert gate.should_drop_kind(KIND, MONDAY) is None


# ── push/recent.py ───────────────────────────────────────────────────────────
def test_push_history_item_link_opens_the_support_tab():
    assert R.ITEM_URL_BY_KIND[KIND] == "/chart-maps?tab=support&symbol={sym}"
    assert R.item_url(KIND, "NVDA") == "/chart-maps?tab=support&symbol=NVDA"
    assert KIND in R.ITEM_KINDS
    # NEGATIVE: not the SEPA page default
    assert R.item_url(KIND, "NVDA") != R.DEFAULT_ITEM_URL.format(sym="NVDA")


# ── supply_demand/alert_status.py ────────────────────────────────────────────
def test_the_typed_kind_equals_the_constant():
    assert AS.OVERNIGHT_KIND == OP.KIND == KIND
    assert "OVERNIGHT_KIND" in AS.__all__


def test_a_daily_pass_never_an_intraday_cadence():
    assert KIND in AS.DAILY_PASS_KINDS and KIND in AS.PASS_KINDS
    assert AS.DAILY_PASS_KINDS[-1] == KIND
    assert KIND not in AS.CADENCE_SEC                               # NEGATIVE: a daily pass is never "stale"


def test_schedule_is_read_from_the_slot():
    assert AS.schedule_map()[KIND] == "06:45 ET, trading days"


def test_moving_the_slot_moves_the_schedule(monkeypatch):
    """MUTATION GUARD: a retyped minute would keep telling him the old slot."""
    monkeypatch.setattr(OP, "SLOT_ET", "07:10")
    assert AS.schedule_map()[KIND] == "07:10 ET, trading days"


def test_NEGATIVE_alert_status_imports_no_overnight_at_module_level():
    src = (ROOT / "backend/supply_demand/alert_status.py").read_text()
    assert not re.search(r"^(from|import)\s+overnight", src, re.M), "overnight is imported lazily only"
    assert re.search(r"^\s+from overnight import push as OP", src, re.M)


class PassColl:
    def __init__(self):
        self.docs = {}

    def find_one(self, q):
        return self.docs.get(q["_id"])

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)


def test_status_payload_serves_the_daily_strip_with_schedule_and_reason():
    pc = PassColl()
    assert AS.record_result(KIND, {"ran": True, "candidates": 40, "passed": 0, "skipped_thin": 31,
                                   "reason": "no name passed the gate"}, MONDAY, coll=pc) is True
    p = AS.status_payload(pass_coll=pc, latest_coll=PassColl(), now=MONDAY)
    row = p["passes"][KIND]
    assert row["cadence_sec"] is None and row["schedule"] == "06:45 ET, trading days"
    assert row["reason"] == "no name passed the gate"
    assert row["counts"] == {"candidates": 40, "passed": 0, "skipped_thin": 31}


def test_NEGATIVE_no_pass_recorded_reads_empty_never_zeros():
    p = AS.status_payload(pass_coll=PassColl(), latest_coll=PassColl(), now=MONDAY)
    assert p["passes"][KIND]["as_of"] is None and p["passes"][KIND]["counts"] == {}


# ── the crontab push line (WP-A writes it) ───────────────────────────────────
@pytest.mark.skipif(not WP_A_LANDED, reason="WP-A (overnight/scan.py + the crontab lines) not landed yet")
def test_the_crontab_push_line_rings_at_the_slot():
    lines = [ln for ln in (ROOT / "backend/crontab").read_text().splitlines()
             if ln.strip() and not ln.lstrip().startswith("#")]
    push = [ln for ln in lines if re.search(r"-m\s+market_hours\.gate\s+overnight\.push(\s|$)", ln)]
    assert len(push) == 1, push
    m, h = push[0].split()[:2]
    assert f"{int(h):02d}:{int(m):02d}" == OP.SLOT_ET
    # NEGATIVE: the push is never run unwrapped (a closed day must not run it)
    assert not [ln for ln in lines if re.search(r"-m\s+overnight\.push", ln)]
