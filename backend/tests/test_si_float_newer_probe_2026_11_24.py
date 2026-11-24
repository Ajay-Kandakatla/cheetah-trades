"""🩳 the newer-float section of scripts/si_share_basis_probe.py over the REAL captured 11-24 inputs (2026-11-24 later).

Ajay 2026-11-24, verbatim: "Is GMEX float accurate?" — every tier / 🩳 High SI list change the newer dated Yahoo float
causes must be printed by the existing probe. This drives `si_share_basis_probe.run` over the integration fixture
(tests/fixtures/si_share_basis_2026_11_24.json, the in-memory Mongo + fake HTTP of test_si_basis_integration) and pins
the BEFORE (the same basis doc with Yahoo's float removed — what the 11-24 check served) vs NOW per name.
"""
from __future__ import annotations

import copy
import json

from scripts import si_share_basis_probe as PR
from short_interest import share_basis as SB
from tests.test_si_basis_integration_2026_11_24 import (FX, NAMES, NOW1, TODAY, FakeHTTP, _harness,  # noqa: F401
                                                        _run, make_db)

FLOAT_UPDATED = {"LABT", "KITT", "WETO", "JELD", "SMX"}


def _read(sym, shares):
    return {"symbol": sym, "ctx": {"float": {"shares": shares}}}


def _probe(holder, reads=None):
    fx = copy.deepcopy(FX)
    db = make_db(fx)
    holder["http"] = http = FakeHTTP(fx)
    out = PR.run(NAMES, db=db, now=NOW1, today=TODAY, reads=reads,
                 refresh=lambda s, d, n, store: SB.refresh_symbol(s, d, n, http=http, store=store))
    return db, out


def test_the_probe_names_every_newer_float_with_before_and_now(_harness):
    db, out = _probe(_harness)
    assert set(out["newer_float"]) == FLOAT_UPDATED and out["smtk_failures"] == []
    assert db[SB.SB_COLL].writes == 0
    k = out["newer_float"]["KITT"]
    assert k["float_before"] == [5527831, "2026-09-03"] and k["float_now"] == [1612787, "2026-11-23"]
    # fix: the newer float clears KITT's split side, the dilution since 09-03 still refuses it
    assert (k["refused_before"], k["tier_before"], k["refused_now"], k["tier_now"]) == ("split", None, "diluted", None)
    la = out["newer_float"]["LABT"]
    assert (la["refused_before"], la["refused_now"], la["pct_now"], la["tier_now"]) == ("diluted", "diluted", None, None)
    assert out["newer_float"]["SMX"]["refused_before"] == "split_same_day"
    assert out["newer_float"]["SMX"]["refused_now"] == "split"
    assert out["newer_float_tier_changes"] == {"WETO": [None, "low"]}
    assert out["newer_float_high"] == {"entering": [], "leaving": []}
    assert out["newer_float_list"] == {}                                  # no stored reads given
    json.dumps(out["newer_float"], allow_nan=False)


def test_the_probe_lists_flags_gained_and_LOST_and_none_are_lost(_harness):
    _db, out = _probe(_harness)
    for s, n in out["newer_float"].items():
        assert n["flags_gained"] == ["float_updated"] and n["flags_lost"] == [], s
    assert out["newer_float_flags_lost"] == {}


def test_the_probe_reports_a_lost_flag_when_one_is_lost(_harness, monkeypatch):
    """NEGATIVE control: a verdict that drops the dilution flags under a newer float shows up in the lost list."""
    from short_interest import basis_math as BM
    real = BM.verdict

    def drop(rec, doc, today):
        v = real(rec, doc, today)
        if v and v.get("float_update"):
            v["flags"] = [f for f in v["flags"] if f["key"] != "float_stale"]
        return v
    monkeypatch.setattr(BM, "verdict", drop)
    _db, out = _probe(_harness)
    assert out["newer_float_flags_lost"] == {"KITT": ["float_stale"], "LABT": ["float_stale"]}


def test_the_probe_reports_high_si_list_membership_from_the_stored_reads(_harness):
    reads = {"KITT": _read("KITT", 1612787), "WETO": _read("WETO", 14735015), "JELD": _read("JELD", 80095874)}
    _db, out = _probe(_harness, reads)
    assert out["newer_float"]["KITT"]["list_before"] == out["newer_float"]["KITT"]["list_now"] == [False, "no_tier"]
    assert out["newer_float"]["WETO"]["list_before"] == [False, "no_tier"]
    assert out["newer_float_list"] == {"WETO": [[False, "no_tier"], [False, "not_high"]]}
    assert out["newer_float"]["JELD"]["list_now"] == out["newer_float"]["JELD"]["list_before"]


def test_NEGATIVE_a_name_with_no_stored_read_has_no_list_answer(_harness):
    _db, out = _probe(_harness, {"WETO": _read("WETO", 14735015)})
    assert out["newer_float"]["LABT"]["list_before"] is None and out["newer_float"]["LABT"]["list_now"] is None
    assert set(out["newer_float_list"]) == {"WETO"}


def test_without_newer_float_strips_only_the_yahoo_float_and_reruns_the_track():
    doc = {"yahoo": {"float_shares": 361428, "shares_outstanding": 752439, "as_of": "2026-11-19"},
           "splits": {"status": "ok", "rows": []}, "float_track": {"value": 361428, "since": "2026-11-19"}}
    rec = {"v": 2, "float_shares": 20235, "float_asof": "2026-11-02", "shares_outstanding": 752439,
           "shares_asof": "2026-11-02"}
    d = PR.without_newer_float(doc, rec, None)
    assert d["yahoo"] == {"float_shares": None, "shares_outstanding": 752439, "as_of": "2026-11-19"}
    assert d["float_track"]["value"] == 20235 and d["float_track"]["since"] == "2026-11-02"
    assert doc["yahoo"]["float_shares"] == 361428                       # the input is never mutated
    assert PR.without_newer_float({"yahoo": None}, rec, None)["yahoo"] is None


def test_NEGATIVE_refresh_stores_the_track_on_the_record_float_never_the_newer_one(_harness):
    """2026-11-24 later fix: share_basis.refresh_symbol stores the float track on the SI record's float, so a newer
    Yahoo float never moves the dilution window's start date forward."""
    _db, _http, _old, new, docs = _run(holder=_harness)
    for s in FLOAT_UPDATED:
        rec, t = FX["names"][s]["si_record"], docs[s]["float_track"]
        assert (t["value"], t["since"]) == (rec["float_shares"], rec["float_asof"]), s
        assert new[s]["float_asof"] != t["since"], s                    # the one divided by is the newer read
