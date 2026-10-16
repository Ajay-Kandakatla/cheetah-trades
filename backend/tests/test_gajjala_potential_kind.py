"""🧠 gajjala_potential — the push / alert registries (BUILD_SPEC4 WP-C, 2026-10-15).

Ajay 2026-10-15, three messages (verbatim): "In Gajjalas setup I wanna find potential stocks this shows me what has
happened I am trying to setup for this tab to act like Gajjalas brain. So create a potential category in this
section." / "In all the sub tab and add a track and alert to show me new potential is added everyday." / "Give me an
alert all continous tracker on these specifically when I get alert I will jump on to ride the wave".

DECISIONS4: a NEW kind, LIVE (not shadow), owner-only, ON for his devices; it rides the existing 5-minute Gajjala pass
(no crontab line of its own). This file pins every registry the kind must be in — and every one it must NOT be in.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_hours import gate                    # noqa: E402
from push import hooks, recent as R, sender, subs   # noqa: E402
from supply_demand import alert_status as AS     # noqa: E402

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]
KIND = "gajjala_potential"
NOW = datetime(2026, 10, 15, 10, 6, tzinfo=ET)
LABOR_DAY = datetime(2026, 9, 7, 10, 0, tzinfo=ET)
SATURDAY = datetime(2026, 9, 5, 10, 0, tzinfo=ET)
TUESDAY = datetime(2026, 9, 8, 10, 0, tzinfo=ET)


@pytest.fixture()
def no_override(monkeypatch):
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)


# ── push/subs.py ─────────────────────────────────────────────────────────────
def test_off_by_default_on_for_the_owner_through_the_keep_set():
    assert subs.default_prefs()[KIND] is False                     # everyone else starts off
    assert KIND in subs.OWNER_KEEP_SET
    assert subs.owner_prefs()[KIND] is True
    assert subs.prefs_for(subs._owner_email())[KIND] is True
    assert subs.prefs_for("someone.else@example.com")[KIND] is False


def test_NEGATIVE_not_hard_stopped_and_not_retired():
    """Registered-but-disabled would be a toggle that can never fire (he said LIVE)."""
    assert KIND not in subs.DISABLED_ALERT_KINDS
    assert KIND not in subs.RETIRED_2026_09_20


def test_owner_prefs_apply_turns_it_on_from_the_keep_set_itself():
    from scripts import owner_prefs_apply as S
    assert S.on_kinds() == sorted(subs.OWNER_KEEP_SET)
    assert KIND in S.on_kinds() and KIND not in S.off_kinds()


def test_the_a_plus_kind_is_in_the_keep_set_and_live_since_2026_10_16():
    # WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens"). default_prefs STAYS False for everyone
    # else (AMENDMENTS10 F1 — "everyone else starts off"); his devices ride OWNER_KEEP_SET.
    from chart_maps.gajjala import constants as GC
    assert "gajjala_setup" in subs.OWNER_KEEP_SET and subs.default_prefs()["gajjala_setup"] is False
    assert GC.GAJJALA_PUSH_MODE == "live"


def test_NEGATIVE_trade_flash_stays_out_of_the_keep_set():
    assert "trade_flash" not in subs.OWNER_KEEP_SET                # his 2026-09-08 "kill the tape burst"


# ── push/hooks.py ────────────────────────────────────────────────────────────
def test_hook_routes_to_the_owner_under_its_own_kind(monkeypatch):
    calls = []
    monkeypatch.setattr(sender, "send_to_user",
                        lambda email, payload, kind=None: calls.append((email, payload, kind)) or
                        {"sent": 1, "failed": 0, "total_targets": 1})
    payload = {"title": "🧠 GGA · 🚩 Bull Flag — building", "body": "x", "url": "/chart-maps?tab=gajjala"}
    r = hooks.notify_gajjala_potential(owner="owner@example.com", payload=payload)
    assert r == {"sent": 1, "failed": 0, "total_targets": 1}
    assert calls == [("owner@example.com", payload, KIND)]


def test_NEGATIVE_the_hook_never_routes_as_the_a_plus_kind(monkeypatch):
    calls = []
    monkeypatch.setattr(sender, "send_to_user",
                        lambda email, payload, kind=None: calls.append(kind) or {"sent": 0})
    hooks.notify_gajjala_potential(owner="o@example.com", payload={})
    assert calls == [KIND] and "gajjala_setup" not in calls and None not in calls


# ── market_hours/gate.py ─────────────────────────────────────────────────────
def test_a_market_kind_silent_on_weekends_and_holidays(no_override):
    assert KIND in gate.MARKET_ALERT_KINDS
    assert KIND not in gate.PERSONAL_KINDS                          # NEGATIVE: never a closed-day kind
    assert gate.should_drop_kind(KIND, LABOR_DAY) == "holiday 2026-09-07"
    assert gate.should_drop_kind(KIND, SATURDAY) == "weekend"
    assert gate.should_drop_kind(KIND, TUESDAY) is None


# ── push/recent.py ───────────────────────────────────────────────────────────
def test_push_history_item_link_opens_the_gajjala_tab_on_the_focus():
    assert R.ITEM_URL_BY_KIND[KIND] == "/chart-maps?tab=gajjala&focus={sym}"
    assert R.item_url(KIND, "NVDA") == "/chart-maps?tab=gajjala&focus=NVDA"
    assert KIND in R.ITEM_KINDS
    # NEGATIVE: not the SEPA page default
    assert R.item_url(KIND, "NVDA") != R.DEFAULT_ITEM_URL.format(sym="NVDA")


# ── the crontab: it rides chart_maps.gajjala.run ─────────────────────────────
def test_NEGATIVE_no_crontab_line_of_its_own():
    lines = [ln for ln in (ROOT / "backend/crontab").read_text().splitlines()
             if ln.strip() and not ln.lstrip().startswith("#")]
    assert not [ln for ln in lines if KIND in ln or "potential" in ln], "it rides chart_maps.gajjala.run"
    assert len([ln for ln in lines if re.search(r"-m\s+(?:market_hours\.gate\s+)?chart_maps\.gajjala\.run(\s|$)",
                                                ln)]) == 1


# ── supply_demand/alert_status.py ────────────────────────────────────────────
def test_the_typed_kind_equals_the_constant():
    from chart_maps.gajjala import constants as GC
    assert AS.GAJJALA_POTENTIAL_KIND == GC.POTENTIAL_PUSH_KIND == KIND


def test_registered_as_a_five_minute_pass_right_after_the_a_plus_pass():
    assert AS.PASS_KINDS.index(KIND) == AS.PASS_KINDS.index(AS.GAJJALA_KIND) + 1
    assert AS.CADENCE_SEC[KIND] == AS.CADENCE_SEC[AS.GAJJALA_KIND] == 300
    assert KIND not in AS.DAILY_PASS_KINDS
    assert "read_gajjala_potentials" in AS.__all__ and "GAJJALA_POTENTIAL_KIND" in AS.__all__


def test_NEGATIVE_alert_status_stays_a_module_level_leaf():
    src = (ROOT / "backend/supply_demand/alert_status.py").read_text()
    assert not re.search(r"^(from|import)\s+chart_maps", src, re.M), "chart_maps is imported lazily only"
    assert not re.search(r"^\s*(from|import)\s+catalysts", src, re.M)


def test_the_tracker_handle_uses_the_store_collection_name(monkeypatch):
    from chart_maps.gajjala import store as GS
    seen = []
    monkeypatch.setattr(GS.GajjalaStore, "coll", lambda self, name: seen.append(name) or "HANDLE")
    assert AS._gajjala_potentials_coll() == "HANDLE"
    assert seen == [GS.POTENTIALS] and GS.POTENTIALS == "gajjala_potentials"


class TrackerColl:
    def __init__(self, docs=()):
        self.docs = {d["_id"]: dict(d) for d in docs}
        self.queries = []

    def find(self, q):
        self.queries.append(dict(q))
        return [dict(d) for d in self.docs.values() if all(d.get(k) == v for k, v in q.items())]


class BrokenTracker:
    def find(self, q):
        raise RuntimeError("mongo down")


def _doc(sym, setup, *, day="2026-10-15", first_seen=datetime(2026, 10, 15, 13, 51, tzinfo=timezone.utc),
         kind="building", push=None, held=None, **kw):
    doc = {"_id": f"{day}|{sym}|{setup}", "date": day, "symbol": sym, "setup": setup, "frame": "5m",
           "first_seen": first_seen,
           "first_seen_et": first_seen.astimezone(ET).strftime("%H:%M") if isinstance(first_seen, datetime) else None,
           "first_kind": kind, "line": f"{sym} · 🚩 Bull Flag · {kind} · trigger 4.20",
           "url": f"/chart-maps?tab=gajjala&sub={setup}&focus={sym}"}
    if push is not None:
        doc["push"] = push
    if held is not None:
        doc["held"] = held
    doc.update(kw)
    return doc


def test_read_potentials_lists_today_newest_first_sighting_first():
    c = TrackerColl([
        _doc("GGA", "bull_flag", push={"state": "pushed", "at": "2026-10-15T13:51:05+00:00", "at_et": "09:51"}),
        _doc("GGB", "kiss_fly", kind="armed", first_seen=datetime(2026, 10, 15, 14, 1, tzinfo=timezone.utc),
             held=[{"at_et": "09:36", "reason": "muted"}, {"at_et": "09:41", "reason": "stale_tape"}]),
    ])
    items = AS.read_gajjala_potentials(c, NOW)
    assert c.queries == [{"date": "2026-10-15"}]
    assert [i["symbol"] for i in items] == ["GGB", "GGA"]
    b, a = items
    assert a == {"date": "2026-10-15", "symbol": "GGA", "setup": "bull_flag", "at": "2026-10-15T09:51:00-04:00",
                 "kind": "building", "text": "GGA · 🚩 Bull Flag · building · trigger 4.20",
                 "url": "/chart-maps?tab=gajjala&sub=bull_flag&focus=GGA", "push_state": "pushed",
                 "push_at": "2026-10-15T09:51:05-04:00", "held": None}
    assert b["kind"] == "armed" and b["push_state"] is None and b["push_at"] is None
    assert b["held"] == "stale_tape", "the LAST held reason"
    json.dumps(items, allow_nan=False)


@pytest.mark.parametrize("state", ["pushed", "no_target", "failed", "claimed"])
def test_every_push_state_is_served(state):
    c = TrackerColl([_doc("GGA", "bull_flag", push={"state": state, "at": "2026-10-15T13:51:05+00:00"})])
    assert AS.read_gajjala_potentials(c, NOW)[0]["push_state"] == state


def test_NEGATIVE_an_unknown_push_state_is_none_never_echoed():
    c = TrackerColl([_doc("GGA", "bull_flag", push={"state": "sent_twice"})])
    item = AS.read_gajjala_potentials(c, NOW)[0]
    assert item["push_state"] is None and item["push_at"] is None


def test_NEGATIVE_yesterdays_potentials_never_read_as_today():
    c = TrackerColl([_doc("OLD", "bull_flag", day="2026-10-14",
                          first_seen=datetime(2026, 10, 14, 19, 0, tzinfo=timezone.utc)),
                     _doc("NEW", "bull_flag")])
    assert [i["symbol"] for i in AS.read_gajjala_potentials(c, NOW)] == ["NEW"]
    # the ET day decides: 23:30 ET on the 14th is still the 14th though UTC says the 15th
    late = datetime(2026, 10, 15, 3, 30, tzinfo=timezone.utc)
    assert [i["symbol"] for i in AS.read_gajjala_potentials(c, late)] == ["OLD"]


@pytest.mark.parametrize("url", ["//evil.example/x", "https://evil.example/x", "javascript:alert(1)", "", None, 7])
def test_NEGATIVE_url_guard_only_internal_paths(url):
    c = TrackerColl([_doc("GGA", "bull_flag", url=url)])
    assert AS.read_gajjala_potentials(c, NOW)[0]["url"] is None


def test_NEGATIVE_a_dead_or_missing_tracker_is_an_empty_list_never_a_500():
    assert AS.read_gajjala_potentials(BrokenTracker(), NOW) == []
    assert AS.read_gajjala_potentials(None, NOW) == []            # no Mongo in tests
    junk = TrackerColl([_doc("GGA", "bull_flag", first_seen="not a date", line=None, first_kind=3,
                             held=["muted"], push="pushed")])
    item = AS.read_gajjala_potentials(junk, NOW)[0]
    assert item["at"] is None and item["text"] is None and item["kind"] is None
    assert item["held"] is None and item["push_state"] is None
    json.dumps(item, allow_nan=False)


class PassColl:
    def __init__(self, docs=()):
        self.docs = {d["_id"]: dict(d) for d in docs}

    def find_one(self, q):
        return self.docs.get(q["_id"])

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)


def test_status_payload_carries_the_pass_with_its_potential_items():
    pc = PassColl()
    counts = {"potential": 3, "armed": 1, "building": 2, "new": 2, "tracked_today": 2, "pushed": 1, "muted": 1}
    assert AS.record_pass(KIND, counts, NOW, coll=pc) is True
    tracker = TrackerColl([_doc("GGA", "bull_flag")])
    p = AS.status_payload(pass_coll=pc, latest_coll=PassColl(), now=NOW, potential_coll=tracker)
    row = p["passes"][KIND]
    assert row["counts"] == counts and row["cadence_sec"] == 300 and row["date"] == "2026-10-15"
    assert [i["symbol"] for i in row["potential_items"]] == ["GGA"]
    # NEGATIVE: only the 🧠 pass carries potential_items; the 🚩 pass keeps its shadow_items
    assert all("potential_items" not in v for k, v in p["passes"].items() if k != KIND)
    assert "shadow_items" in p["passes"]["gajjala_setup"] and "shadow_items" not in row
    json.dumps(p, allow_nan=False)


def test_NEGATIVE_status_payload_with_a_dead_tracker_still_serves_the_pass():
    p = AS.status_payload(pass_coll=PassColl(), latest_coll=PassColl(), now=NOW, potential_coll=BrokenTracker())
    assert p["passes"][KIND] == {"as_of": None, "date": None, "counts": {}, "cadence_sec": 300,
                                 "potential_items": []}
