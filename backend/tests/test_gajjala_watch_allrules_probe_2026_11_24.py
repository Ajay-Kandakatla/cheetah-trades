"""✅ the §5.2 container probe (scripts/gajjala_watch_allrules_probe.py) == the engine (allrules.step) on ONE fixture.

Ajay 2026-11-24, verbatim: "Anytime stocks qualify all his rules should be auto added to the Watch list so I can keep
tracking them later"

The container runs main (no allrules.py), so the probe re-implements the seating rule; these pins make that copy the
engine's rule: the same fixture → the same seated set, on the session itself and on the first step of the next session
(the bounded back-fill the 11-25 04:00 step will run over 11-24). NEGATIVE controls: a probe whose floor, armed test or ×
read drifts from the engine is caught.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala_watch import allrules as R
from chart_maps.gajjala_watch import constants as C
from scripts import gajjala_watch_allrules_probe as P
from tests.test_gajjala_watch_allrules_2026_11_24 import ISO, PISO, armed, path_e, rstep, world  # noqa: F401
from tests.test_gajjala_watch_allrules_2026_11_24 import _on  # noqa: F401  (autouse: the Watch switch on)
from tests.test_gajjala_watch_auto_2026_11_17 import T0, auto_doc, entry, fake_db, scan, utc
from tests.test_gajjala_watch_build_2026_11_15 import PREV, S, at

HIS = ["OMH", "HISA"]


def _fixture(d=S):
    """Every branch of the rule: seated (scan / tracker volume, two setups, an A+ with no volume, an A+ under the
    floor), under the floor, unknown volume, building / partial only, his name, his ×, 🚫."""
    trackers = [
        armed("AAA", 2_000_000, d=d), armed("AAA", 2_000_000, d=d, setup="kiss_fly", arms=[at(d, 10, 5)]),
        armed("BBB", 1_500_000, d=d),                                         # tracker volume only
        armed("LOW", 999_999, d=d), armed("NOVOL", 0, d=d),
        armed("BLD", 5_000_000, d=d, path=[path_e(at(d, 9, 41), kind="building")]),
        armed("PRT", 5_000_000, d=d, path=[path_e(at(d, 9, 41), state="partial", kind=None)]),
        armed("HISA", 5_000_000, d=d), armed("XED", 5_000_000, d=d), armed("NOFI", 5_000_000, d=d),
        armed("APLO", 500_000, d=d),                                          # under the floor but an A+
    ]
    for t in trackers:
        if t["symbol"] == "NOVOL":
            t["last"]["session_volume"] = None
    scans = [scan("AAA", 2_000_000, d=d), scan("LOW", 999_999, d=d), scan("HISA", 5e6, d=d), scan("XED", 5e6, d=d),
             scan("NOFI", 5e6, d=d), scan("APLO", 500_000, d=d)]
    ap = [dict(entry("GP", volume=None), why=C.AUTO_APLUS_WHY, aplus_at=utc(at(d, 9, 55))),
          dict(entry("APLO"), why=C.AUTO_APLUS_WHY, aplus_at=utc(at(d, 9, 58))),
          dict(entry("XAP"), why=C.AUTO_APLUS_WHY, aplus_at=utc(at(d, 9, 59)))]
    adoc = auto_doc(ap + [entry("PLAIN")], dismissed=["XED", "XAP"], session=d.isoformat())
    return world(trackers, scans, flagged=["NOFI"]), adoc


SEATED = ["AAA", "APLO", "BBB", "GP"]


def _probe(st, adoc, iso, db=None):
    db = db if db is not None else fake_db(manual=HIS)
    return P.expected(iso, **P.read(iso, db=db, stores=st) | {"auto_doc": adoc})


def test_probe_constants_are_the_engines():
    assert P.TRACKER_FIELDS == C.RULES_TRACKER_FIELDS
    assert P.floor() == C.RULES_MIN_VOLUME == GC.K11_MIN_SESSION_VOLUME
    assert C.RULES_KINDS[0] == GC.POTENTIAL_KINDS[0]


def test_probe_rule_equals_the_engine_on_the_same_session():
    st, adoc = _fixture()
    db = fake_db(manual=HIS)
    ex = _probe(st, adoc, ISO, db)
    res = rstep(db, st, auto_prior=adoc, dry=True)
    assert res["reason"] is None and res["backfilled"] == []
    assert ex["seated"] == sorted(res["symbols"]) == SEATED
    assert ex["under_floor"] == ["LOW"] and ex["volume_unknown"] == ["NOVOL"] and ex["yours"] == ["HISA"]
    assert ex["dismissed"] == ["XAP", "XED"] and ex["not_eligible"] == ["NOFI"]
    assert "BLD" not in ex["armed"] and "PRT" not in ex["armed"] and "PLAIN" not in ex["seated"]
    sk = res["skipped"]                                         # the engine counts RECORDS: APLO's armed read under the
    assert (sk["under_floor"], sk["volume_unknown"], sk["yours"], sk["dismissed"], sk["not_eligible"]) == (2, 1, 1, 2, 1)
    # floor is counted though its A+ record seats it; the probe lists NAMES, so APLO is seated, not under_floor


def test_probe_rule_equals_the_engine_on_the_next_sessions_first_step_backfill():
    """§5.2: the 11-25 04:00 step back-fills 11-24 — the probe over PREV == what that step seats."""
    st, adoc = _fixture(PREV)
    db = fake_db(manual=HIS)
    ex = _probe(st, adoc, PISO, db)
    res = rstep(db, st, at(S, 4, 0, 30), auto_prior=adoc, dry=True)
    assert res["reason"] is None and res["backfilled"] == [PISO]
    assert ex["seated"] == sorted(res["symbols"]) == SEATED
    assert all(e["last_met_session"] == PISO for e in res["writes"]["entries"])


def test_NEGATIVE_the_probe_writes_nothing():
    st, adoc = _fixture()
    db = fake_db(manual=HIS, auto=adoc)
    before = {k: dict(v.docs) for k, v in db.items()}
    out = P.run(ISO, db=db, stores=st)
    assert out["seated"] == SEATED and out["counts"]["seated"] == len(SEATED) and out["auto_doc_session"] == ISO
    assert {k: dict(v.docs) for k, v in db.items()} == before
    assert db[C.COLL_LIST].updates == []


def test_NEGATIVE_an_unreadable_auto_doc_or_broker_list_raises_never_guesses():
    st, _adoc = _fixture()
    with pytest.raises(RuntimeError):
        P.read(ISO, db=fake_db(manual=HIS, list_fail=True), stores=st)
    with pytest.raises(RuntimeError):
        P.read(ISO, db=fake_db(manual=HIS), stores=world([], [], broker_fail=True))


def test_NEGATIVE_a_drifted_probe_floor_is_caught(monkeypatch):
    st, adoc = _fixture()
    db = fake_db(manual=HIS)
    monkeypatch.setattr(P, "floor", lambda: 0)
    ex = _probe(st, adoc, ISO, db)
    assert ex["seated"] != sorted(rstep(db, st, auto_prior=adoc, dry=True)["symbols"])


def test_NEGATIVE_a_drifted_armed_test_is_caught(monkeypatch):
    st, adoc = _fixture()
    db = fake_db(manual=HIS)
    monkeypatch.setattr(P, "armed_turn", lambda d: bool(d.get("state_path")))
    ex = _probe(st, adoc, ISO, db)
    assert ex["seated"] != sorted(rstep(db, st, auto_prior=adoc, dry=True)["symbols"])


def test_NEGATIVE_another_sessions_x_does_not_block_this_one():
    """His × of the 🤖 doc's session blocks only that session — the probe over a different session ignores it, as the
    engine does."""
    st, adoc = _fixture()
    other = dict(adoc, session=(S - timedelta(days=30)).isoformat())
    ex = _probe(st, other, ISO)
    assert "XED" in ex["seated"] and "GP" not in ex["seated"]     # × not this session; the A+ not this session's
