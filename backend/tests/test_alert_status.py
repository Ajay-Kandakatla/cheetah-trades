"""supply_demand/alert_status + GET /alerts/status — WHY the phone was quiet.

Ajay 2026-09-05: "Do we have the same logic in back end demand for the ones that
I get alerts. Would it be the same list of stocks.. Also can I go to a dedicated
page to see the list of alerts?" No — so the page shows each pass's counters.

Pure: fake collections; the route through a bare FastAPI app with the module's
status_payload patched (the same pattern as tests/test_bounce_room.py).
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import alert_status as AS   # noqa: E402
from supply_demand import alert_gates as AG    # noqa: E402

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 3, 10, 0, tzinfo=ET)


class FakeColl:
    def __init__(self):
        self.docs = {}
        self.writes = 0

    def find_one(self, q):
        return self.docs.get(q["_id"])

    def replace_one(self, q, doc, upsert=False):
        self.writes += 1
        self.docs[q["_id"]] = dict(doc)


class Broken:
    def find_one(self, q):
        raise RuntimeError("mongo down")

    def replace_one(self, q, doc, upsert=False):
        raise RuntimeError("mongo down")


# ── counts hygiene ───────────────────────────────────────────────────────────
def test_clean_counts_ints_only_lists_become_lengths_garbage_drops():
    out = AS.clean_counts({"a": 1, "b": np.int64(2), "c": 3.0, "d": True, "hits": [1, 2, 3],
                           "e": "x", "f": None, "g": float("nan"), "h": float("inf"), 9: 4})
    assert out == {"a": 1, "b": 2, "c": 3, "d": 1, "hits": 3, "9": 4}
    assert all(type(v) is int for v in out.values())
    assert AS.clean_counts(None) == {} and AS.clean_counts({}) == {}


def test_counts_from_result_drops_bookkeeping_keys():
    res = {"ran": True, "date": "2026-09-03", "reason": None, "candidates": 4, "hits": [1, 2],
           "pushed": 1, "skipped_room": 2, "seconds": 3.2, "payload": {"x": 1},
           "breaking": [{"symbol": "A"}], "near_demand": [], "as_of": "t", "latest_written": True}
    assert AS.counts_from_result(res) == {"candidates": 4, "hits": 2, "pushed": 1, "skipped_room": 2}


# ── record / read ────────────────────────────────────────────────────────────
def test_record_pass_writes_one_doc_per_kind_in_et_and_replaces_it():
    c = FakeColl()
    assert AS.record_pass("zone_bounce_alert", {"candidates": 3, "pushed": np.int64(1)}, NOW, coll=c) is True
    assert c.docs == {"zone_bounce_alert": {"_id": "zone_bounce_alert", "as_of": "2026-09-03T10:00:00-04:00",
                                            "date": "2026-09-03", "counts": {"candidates": 3, "pushed": 1}}}
    utc = datetime(2026, 9, 3, 18, 5, tzinfo=ZoneInfo("UTC"))                     # 14:05 ET
    AS.record_pass("zone_bounce_alert", {"candidates": 0}, utc, coll=c, reason="zone store empty for today")
    assert c.writes == 2 and list(c.docs) == ["zone_bounce_alert"]
    d = c.docs["zone_bounce_alert"]
    assert d["as_of"] == "2026-09-03T14:05:00-04:00" and d["date"] == "2026-09-03"
    assert d["counts"] == {"candidates": 0} and d["reason"] == "zone store empty for today"
    naive = datetime(2026, 9, 3, 23, 30)                                          # naive = ET wall clock
    AS.record_pass("demand_alert", {}, naive, coll=c)
    assert c.docs["demand_alert"]["date"] == "2026-09-03"


def test_record_pass_is_best_effort_never_raises():
    assert AS.record_pass("demand_alert", {"a": 1}, NOW, coll=Broken()) is False
    assert AS.record_pass("demand_alert", {"a": 1}, NOW, coll=None) is False, "no Mongo in tests: quiet False"
    assert AS.record_result("demand_alert", {}, NOW, coll=FakeColl()) is False
    assert AS.record_result("demand_alert", None, NOW, coll=FakeColl()) is False
    c = FakeColl()
    assert AS.record_result("demand_alert", {"ran": False, "reason": "live prices failed: x", "candidates": 9},
                            NOW, coll=c) is True
    assert c.docs["demand_alert"]["reason"] == "live prices failed: x"
    assert c.docs["demand_alert"]["counts"] == {"candidates": 9}


def test_read_pass_empty_shape_on_missing_unreadable_or_no_coll():
    empty = {"as_of": None, "date": None, "counts": {}}
    assert AS.read_pass("demand_alert", FakeColl()) == empty
    assert AS.read_pass("demand_alert", Broken()) == empty
    assert AS.read_pass("demand_alert", None) == empty
    c = FakeColl()
    c.docs["demand_alert"] = {"_id": "demand_alert", "as_of": "2026-09-03T10:00:00-04:00", "date": "2026-09-03",
                              "counts": {"candidates": 4.0, "pushed": "1", "hits": [1]}, "reason": ""}
    got = AS.read_pass("demand_alert", c)
    assert got == {"as_of": "2026-09-03T10:00:00-04:00", "date": "2026-09-03",
                   "counts": {"candidates": 4, "pushed": 1, "hits": 1}}
    assert "reason" not in got, "an empty reason is no reason"


def test_read_zone_edge_uses_the_latest_doc_and_passes_old_counts_through_unpadded():
    lc = FakeColl()
    assert AS.read_zone_edge(lc) == {"as_of": None, "date": None, "counts": {}}
    assert AS.read_zone_edge(Broken()) == {"as_of": None, "date": None, "counts": {}}
    lc.docs["latest"] = {"_id": "latest", "as_of": "2026-09-03T10:00:00-04:00", "date": "2026-09-03",
                         "counts": {"breaking": 3, "near_demand": 2, "candidates": 5, "priced": 5,
                                    "stale_print": 0}, "breaking": [{"symbol": "A"}]}
    got = AS.read_zone_edge(lc)
    assert got["as_of"] == "2026-09-03T10:00:00-04:00" and got["date"] == "2026-09-03"
    assert got["counts"] == {"breaking": 3, "near_demand": 2, "candidates": 5, "priced": 5, "stale_print": 0}
    assert "skipped_room" not in got["counts"], "a pre-2026-09-05 doc: absent, never invented as 0"
    lc.docs["latest"] = {"_id": "latest", "as_of": None, "date": "2026-09-03", "reason": "zone store empty for today",
                         "counts": {"breaking": 0, "pushed": 0}}
    got = AS.read_zone_edge(lc)
    assert got["as_of"] is None and got["reason"] == "zone store empty for today" and got["counts"]["pushed"] == 0
    # the empty-store self-heal write (2026-09-05) keeps as_of None for the board /
    # paper engine but stamps ran_at: for THIS payload that IS the pass time
    lc.docs["latest"]["ran_at"] = "2026-09-03T09:35:00-04:00"
    got = AS.read_zone_edge(lc)
    assert got["as_of"] == "2026-09-03T09:35:00-04:00" and got["reason"] == "zone store empty for today"
    # a REAL pass's as_of always wins over any ran_at
    lc.docs["latest"] = {"_id": "latest", "as_of": "2026-09-03T10:00:00-04:00", "ran_at": "2026-09-03T09:35:00-04:00",
                         "date": "2026-09-03", "counts": {"pushed": 1}}
    assert AS.read_zone_edge(lc)["as_of"] == "2026-09-03T10:00:00-04:00"


# ── the status payload (contract B) ──────────────────────────────────────────
def test_status_payload_contract_shape_gate_numbers_and_in_session_at_request_time():
    pc, lc = FakeColl(), FakeColl()
    AS.record_pass("zone_bounce_alert", {"candidates": 1100, "hits": 4, "skipped_room": 2, "skipped_proximity": 1,
                                         "skipped_cap": 0, "unknown_cap": 1, "pushed": 0}, NOW, coll=pc)
    AS.record_pass("demand_alert", {"candidates": 40, "hits": 3, "at": 1, "near": 2, "skipped_room": 1,
                                    "skipped_proximity": 2, "pushed": 0}, NOW, coll=pc)
    lc.docs["latest"] = {"_id": "latest", "as_of": NOW.isoformat(), "date": "2026-09-03",
                         "counts": {"candidates": 1124, "priced": 1100, "stale_print": 24, "breaking": 6,
                                    "near_demand": 9, "skipped_room": 3, "skipped_cap": 2, "unknown_cap": 5,
                                    "pushed": 1}}
    p = AS.status_payload(pass_coll=pc, latest_coll=lc, now=NOW)
    assert set(p) == {"in_session", "now_et", "gate", "passes", "disclaimer"}
    assert p["in_session"] is True and p["now_et"] == "2026-09-03T10:00:00-04:00"
    assert p["gate"] == {"min_room_pct": 5.0, "max_above_demand_pct": 1.0}
    assert p["gate"] == {"min_room_pct": AG.ALERT_MIN_ROOM_PCT, "max_above_demand_pct": AG.ALERT_MAX_ABOVE_DEMAND_PCT}
    assert set(p["passes"]) == {"zone_edge", "zone_bounce_alert", "demand_alert"}
    ze = p["passes"]["zone_edge"]
    assert ze["as_of"] == NOW.isoformat() and ze["date"] == "2026-09-03"
    assert set(ze["counts"]) == {"candidates", "priced", "stale_print", "breaking", "near_demand",
                                 "skipped_room", "skipped_cap", "unknown_cap", "pushed"}
    zb = p["passes"]["zone_bounce_alert"]
    assert set(zb["counts"]) == {"candidates", "hits", "skipped_room", "skipped_proximity", "skipped_cap",
                                 "unknown_cap", "pushed"} and zb["as_of"] == NOW.isoformat()
    assert p["passes"]["demand_alert"]["counts"]["skipped_room"] == 1
    # cadence rides along per pass so the page can call a same-day stamp stale
    assert ze["cadence_sec"] == 60 and zb["cadence_sec"] == 300 and p["passes"]["demand_alert"]["cadence_sec"] == 300
    assert "not advice" in p["disclaimer"] and "closed-bar" in p["disclaimer"]
    json.dumps(p, allow_nan=False)
    # request-time clock: the same stored docs read as out-of-session on a Saturday and after the close
    sat = datetime(2026, 9, 5, 11, 0, tzinfo=ET)
    p2 = AS.status_payload(pass_coll=pc, latest_coll=lc, now=sat)
    assert p2["in_session"] is False and p2["now_et"] == "2026-09-05T11:00:00-04:00"
    assert p2["passes"]["zone_edge"]["as_of"] == NOW.isoformat(), "stale as_of stays visible, never hidden"
    assert AS.status_payload(pass_coll=pc, latest_coll=lc,
                             now=datetime(2026, 9, 3, 16, 1, tzinfo=ET))["in_session"] is False
    utc = datetime(2026, 9, 3, 14, 0, tzinfo=ZoneInfo("UTC"))                        # 10:00 ET
    assert AS.status_payload(pass_coll=pc, latest_coll=lc, now=utc)["now_et"] == "2026-09-03T10:00:00-04:00"


def test_status_payload_with_nothing_recorded_is_three_empty_passes_not_a_500():
    p = AS.status_payload(pass_coll=FakeColl(), latest_coll=FakeColl(), now=NOW)
    for k in ("zone_edge", "zone_bounce_alert", "demand_alert"):
        assert p["passes"][k] == {"as_of": None, "date": None, "counts": {}, "cadence_sec": AS.CADENCE_SEC[k]}
    p = AS.status_payload(pass_coll=Broken(), latest_coll=Broken(), now=NOW)
    assert all(v["as_of"] is None and v["counts"] == {} for v in p["passes"].values())
    p = AS.status_payload(now=NOW)                                     # module resolvers, no Mongo in tests
    assert all(v["as_of"] is None for v in p["passes"].values()) and p["gate"]["min_room_pct"] == 5.0


# ── the route ────────────────────────────────────────────────────────────────
def test_route_offloads_status_payload_to_a_thread(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from supply_demand import api as sd_api
    calls = []

    def fake(**kw):
        calls.append(kw)
        return {"in_session": False, "now_et": "x", "gate": {"min_room_pct": 5.0, "max_above_demand_pct": 1.0},
                "passes": {}, "disclaimer": "d"}
    monkeypatch.setattr(sd_api.alert_status_mod, "status_payload", fake)
    app = FastAPI()
    app.include_router(sd_api.router)
    r = TestClient(app).get("/alerts/status")
    assert r.status_code == 200 and r.json()["gate"] == {"min_room_pct": 5.0, "max_above_demand_pct": 1.0}
    assert calls == [{}], "the route passes nothing; every input is resolved inside"


def test_route_source_guard_and_docs():
    src = (ROOT / "backend/supply_demand/api.py").read_text()
    assert '@router.get("/alerts/status")' in src
    assert "asyncio.to_thread(alert_status_mod.status_payload)" in src
    seg = src[src.index('@router.get("/alerts/status")'):][:2500]
    assert "not advice" in seg and "docs/supply_demand/alerts_page.md" in seg
    assert (ROOT / "docs/supply_demand/alerts_page.md").exists()
    doc = (ROOT / "docs/supply_demand/alerts_page.md").read_text()
    for needle in ("Do we have the same logic in back end demand", "dedicated page to see the list of alerts",
                   "/alerts/status", "/notifications/recent", "skipped_room", "alert_pass_latest"):
        assert needle in doc, needle


def test_alert_gates_stays_a_pure_leaf_and_alert_status_imports_no_sibling_at_module_level():
    gates = (ROOT / "backend/supply_demand/alert_gates.py").read_text()
    assert "pymongo" not in gates and "_get_db" not in gates and "alert_status" not in gates
    status = (ROOT / "backend/supply_demand/alert_status.py").read_text()
    head = status.split("def _coll")[0]
    assert "from . import alert_gates as AG" in head
    for sib in ("zone_edge", "zone_bounce_alerts", "demand_alerts", "bounce_room"):
        assert f"from . import {sib}" not in head and f"from .{sib}" not in head, \
            f"{sib} imports alert_status: a module-level import back would be a cycle"


def test_cadence_sec_matches_the_crontab():
    """CADENCE_SEC is what the page measures staleness against; if the crontab
    moves a pass, this must move with it (review 2026-09-05)."""
    import re
    lines = (ROOT / "backend/crontab").read_text().splitlines()

    def minute_field(module: str) -> str:
        hits = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")
                and re.search(rf"-m\s+{re.escape(module)}(\s|$)", ln)]
        assert len(hits) == 1, f"{module}: expected one crontab line, got {hits}"
        return hits[0].split()[0]

    def seconds(field: str) -> int:
        if field == "*":
            return 60
        m = re.fullmatch(r"\d+-\d+/(\d+)", field)
        assert m, f"unexpected minute field {field!r}"
        return int(m.group(1)) * 60

    assert AS.CADENCE_SEC == {"zone_edge": seconds(minute_field("supply_demand.zone_edge")),
                              "zone_bounce_alert": seconds(minute_field("supply_demand.zone_bounce_alerts")),
                              "demand_alert": seconds(minute_field("supply_demand.demand_alerts"))}
    assert AS.CADENCE_SEC == {"zone_edge": 60, "zone_bounce_alert": 300, "demand_alert": 300}
