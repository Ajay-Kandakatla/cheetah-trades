"""⚡ /alerts serves the break-push rows and counts (entry spec WP-ALST, critic C7, 2026-11-11).

Ajay 2026-11-11 (verbatim): "Here is how he enters please tell me to enter based on this". The ⚡ break push
(chart_maps/gajjala/break_watch.py) rides the 🧠 kind `gajjala_potential`, so the /alerts 🧠 list must say which
tracker docs carried a ⚡ break and the strip must say how many — served words only (break_watch.track_text /
summary_text), never composed in alert_status. A doc without `brk` keeps its row byte for byte.

These tests inject a stub break_watch (the engine lands in a sibling package); the `real_bw` tests run the real module
once it exists and skip until then.
"""
from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chart_maps.gajjala as GPKG                 # noqa: E402
from supply_demand import alert_status as AS     # noqa: E402

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]
KIND = "gajjala_potential"
NOW = datetime(2026, 11, 11, 10, 6, tzinfo=ET)
MOD = "chart_maps.gajjala.break_watch"


class TrackerColl:
    def __init__(self, docs=()):
        self.docs = {d["_id"]: dict(d) for d in docs}

    def find(self, q):
        return [dict(d) for d in self.docs.values() if all(d.get(k) == v for k, v in q.items())]


class PassColl:
    def __init__(self, docs=()):
        self.docs = {d["_id"]: dict(d) for d in docs}

    def find_one(self, q):
        return self.docs.get(q["_id"])

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)


def _doc(sym, setup, *, push=None, brk=None, minute=51, **kw):
    first_seen = datetime(2026, 11, 11, 14, minute, tzinfo=timezone.utc)
    doc = {"_id": f"2026-11-11|{sym}|{setup}", "date": "2026-11-11", "symbol": sym, "setup": setup, "frame": "5m",
           "first_seen": first_seen, "first_kind": "armed", "line": f"{sym} · 🚩 Bull Flag · armed · trigger 1.17",
           "url": f"/chart-maps?tab=gajjala&sub={setup}&focus={sym}"}
    if push is not None:
        doc["push"] = push
    if brk is not None:
        doc["brk"] = brk
    doc.update(kw)
    return doc


def _brk(state="shadow"):
    return {"state": state, "at": "2026-11-11T14:56:12+00:00", "at_et": "09:56:12", "print_t": 1762872972000,
            "print_px": 1.18, "last_px": 1.18, "trigger": 1.17, "stop": 1.12, "bar_t": "2026-11-11T09:50:00-04:00",
            "frame": "5m", "kind": KIND, "mode": "shadow"}


def _stub(calls=None, *, track=None, summary=None):
    mod = types.ModuleType(MOD)
    calls = calls if calls is not None else []

    def track_text(doc):
        calls.append(("track", doc.get("symbol")))
        if track is not None:
            return track(doc)
        return f"⚡ break {doc['brk'].get('state')} {doc['brk'].get('at_et')} ET"

    def summary_text(states):
        calls.append(("summary", list(states)))
        if summary is not None:
            return summary(states)
        return "⚡ break pushes today: " + ",".join(states)

    mod.track_text = track_text
    mod.summary_text = summary_text
    return mod


def _install(monkeypatch, mod):
    """Make `from chart_maps.gajjala import break_watch` resolve to `mod` (None = the import fails)."""
    monkeypatch.setitem(sys.modules, MOD, mod)
    if mod is None:
        monkeypatch.delattr(GPKG, "break_watch", raising=False)
    else:
        monkeypatch.setattr(GPKG, "break_watch", mod, raising=False)


def _payload(docs, pass_counts=None):
    pc = PassColl()
    if pass_counts is not None:
        assert AS.record_pass(KIND, pass_counts, NOW, coll=pc) is True
    return AS.status_payload(pass_coll=pc, latest_coll=PassColl(), now=NOW, potential_coll=TrackerColl(docs))


# ── A1 ───────────────────────────────────────────────────────────────────────
def test_A1_a_doc_with_a_shadow_brk_serves_brk_state_and_the_engines_words(monkeypatch):
    calls = []
    bw = _stub(calls)
    _install(monkeypatch, bw)
    doc = _doc("GGA", "bull_flag", brk=_brk("shadow"))
    p = _payload([doc])
    row = p["passes"][KIND]
    item = row["potential_items"][0]
    assert item["brk_state"] == "shadow"
    assert item["brk_text"] == bw.track_text(doc) == "⚡ break shadow 09:56:12 ET"
    assert row["brk_summary"] == bw.summary_text(["shadow"])
    assert ("summary", ["shadow"]) in calls
    json.dumps(p, allow_nan=False)


@pytest.mark.parametrize("state", AS.BRK_STATES)
def test_A1_every_brk_state_is_served(monkeypatch, state):
    _install(monkeypatch, _stub())
    item = AS.read_gajjala_potentials(TrackerColl([_doc("GGA", "bull_flag", brk=_brk(state))]), NOW)[0]
    assert item["brk_state"] == state


def test_A1_brk_states_are_the_spec_set():
    assert AS.BRK_STATES == ("claimed", "pushed", "no_target", "failed", "shadow")
    assert "BRK_STATES" in AS.__all__


# ── A2 NEGATIVE ──────────────────────────────────────────────────────────────
def test_A2_NEGATIVE_a_doc_without_brk_is_byte_equal_to_today(monkeypatch):
    doc = _doc("GGA", "bull_flag", push={"state": "pushed", "at": "2026-11-11T14:51:05+00:00"})
    _install(monkeypatch, None)
    before = AS.read_gajjala_potentials(TrackerColl([doc]), NOW)
    calls = []
    _install(monkeypatch, _stub(calls))
    after = AS.read_gajjala_potentials(TrackerColl([doc]), NOW)
    assert after == before
    assert json.dumps(after, sort_keys=True) == json.dumps(before, sort_keys=True)
    assert not any(k.startswith("brk") for k in after[0])
    assert calls == [], "no brk → the engine is never asked"


@pytest.mark.parametrize("brk", ["shadow", 1, None, ["shadow"]])
def test_A2_NEGATIVE_a_non_dict_brk_adds_no_key(monkeypatch, brk):
    _install(monkeypatch, _stub())
    doc = _doc("GGA", "bull_flag")
    doc["brk"] = brk
    item = AS.read_gajjala_potentials(TrackerColl([doc]), NOW)[0]
    assert "brk_state" not in item and "brk_text" not in item


def test_A2_NEGATIVE_no_brk_row_means_no_brk_summary_key(monkeypatch):
    calls = []
    _install(monkeypatch, _stub(calls))
    p = _payload([_doc("GGA", "bull_flag", push={"state": "pushed"})])
    assert "brk_summary" not in p["passes"][KIND]
    assert not any(c[0] == "summary" for c in calls)
    assert all("brk_summary" not in v for v in p["passes"].values())


def test_A2_NEGATIVE_empty_tracker_pass_shape_unchanged(monkeypatch):
    _install(monkeypatch, _stub())
    p = _payload([])
    assert p["passes"][KIND] == {"as_of": None, "date": None, "counts": {}, "cadence_sec": 300,
                                 "potential_items": []}


# ── A3 NEGATIVE ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("state", ["weird", "", None, 3, "Pushed"])
def test_A3_NEGATIVE_an_unknown_brk_state_is_never_echoed(monkeypatch, state):
    _install(monkeypatch, _stub())
    doc = _doc("GGA", "bull_flag", brk=_brk("shadow"))
    doc["brk"]["state"] = state
    p = _payload([doc])
    item = p["passes"][KIND]["potential_items"][0]
    assert "brk_state" not in item
    assert "brk_summary" not in p["passes"][KIND], "no brk_state row → no summary"


def test_A3_NEGATIVE_an_absent_break_watch_leaves_the_keys_absent_and_serves_every_pass(monkeypatch):
    _install(monkeypatch, None)
    p = _payload([_doc("GGA", "bull_flag", brk=_brk("pushed"))])
    row = p["passes"][KIND]
    item = row["potential_items"][0]
    assert "brk_state" not in item and "brk_text" not in item and "brk_summary" not in row
    assert item["symbol"] == "GGA"
    assert set(p["passes"]) == set(_payload([])["passes"]), "every pass still served"
    json.dumps(p, allow_nan=False)


def _boom(*a, **k):
    raise RuntimeError("break_watch exploded")


def test_A3_NEGATIVE_a_raising_track_text_leaves_the_row_keys_absent(monkeypatch):
    _install(monkeypatch, _stub(track=_boom))
    p = _payload([_doc("GGA", "bull_flag", brk=_brk("shadow")), _doc("GGB", "kiss_fly", minute=52)])
    row = p["passes"][KIND]
    assert [i["symbol"] for i in row["potential_items"]] == ["GGB", "GGA"]
    assert all(not any(k.startswith("brk") for k in i) for i in row["potential_items"])
    assert "brk_summary" not in row


def test_A3_NEGATIVE_a_raising_summary_text_keeps_the_rows_and_drops_only_the_summary(monkeypatch):
    _install(monkeypatch, _stub(summary=_boom))
    p = _payload([_doc("GGA", "bull_flag", brk=_brk("shadow"))])
    row = p["passes"][KIND]
    assert row["potential_items"][0]["brk_state"] == "shadow"
    assert "brk_summary" not in row
    json.dumps(p, allow_nan=False)


@pytest.mark.parametrize("words", [None, "", 7, ["x"]])
def test_A3_NEGATIVE_non_text_engine_words_are_never_served_as_text(monkeypatch, words):
    _install(monkeypatch, _stub(track=lambda d: words, summary=lambda s: words))
    p = _payload([_doc("GGA", "bull_flag", brk=_brk("claimed"))])
    row = p["passes"][KIND]
    item = row["potential_items"][0]
    assert item["brk_state"] == "claimed" and item["brk_text"] is None
    assert "brk_summary" not in row


# ── A4 reconciliation ────────────────────────────────────────────────────────
def test_A4_two_potential_pushes_and_one_break_push_summary_counts_only_the_break(monkeypatch):
    calls = []
    _install(monkeypatch, _stub(calls, summary=lambda s: f"⚡ break pushes today: {s.count('pushed')} sent"))
    counts = {"potential": 3, "armed": 3, "new": 3, "pushed": 2}
    docs = [_doc("GGA", "bull_flag", push={"state": "pushed", "at": "2026-11-11T14:51:05+00:00"}),
            _doc("GGB", "bull_flag", minute=52, push={"state": "pushed", "at": "2026-11-11T14:52:05+00:00"}),
            _doc("GGC", "kiss_fly", minute=53, brk=_brk("pushed"))]
    p = _payload(docs, counts)
    row = p["passes"][KIND]
    assert row["brk_summary"] == "⚡ break pushes today: 1 sent"
    assert ("summary", ["pushed"]) in calls, "only the ⚡ rows' brk_state reach the summary, never the 🧠 push"
    assert row["counts"] == counts, "the 🧠 pass counter is untouched"
    by = {i["symbol"]: i for i in row["potential_items"]}
    assert by["GGA"]["push_state"] == "pushed" and "brk_state" not in by["GGA"]
    assert by["GGC"]["brk_state"] == "pushed" and by["GGC"]["push_state"] is None


# ── source guards ────────────────────────────────────────────────────────────
def test_alert_status_stays_a_leaf_the_break_watch_import_is_lazy():
    src = (ROOT / "backend/supply_demand/alert_status.py").read_text()
    head = src.split("def ")[0]
    assert "break_watch" not in head, "a module-level break_watch import breaks the leaf rule"
    assert "from chart_maps.gajjala import break_watch as BW" in src


def test_alert_status_never_composes_break_words():
    """The ⚡ words are the engine's (track_text / summary_text); alert_status types none of them."""
    src = (ROOT / "backend/supply_demand/alert_status.py").read_text()
    body = src[src.index("def _break_watch"):src.index("def _gajjala_held_text")]
    for needle in ("break rang", "break seen", "break pushes today", "sent ·", "recorded in shadow"):
        assert needle not in body, needle


# ── the real engine, once WP-BRK has landed ──────────────────────────────────
def _real_bw():
    import importlib
    try:
        return importlib.import_module(MOD)
    except ImportError:
        pytest.skip("chart_maps.gajjala.break_watch not built yet (WP-BRK)")


def test_real_bw_A1_row_and_summary_are_the_engines_words():
    bw = _real_bw()
    doc = _doc("GGA", "bull_flag", brk=_brk("shadow"))
    p = _payload([doc])
    row = p["passes"][KIND]
    item = row["potential_items"][0]
    assert item["brk_state"] == "shadow"
    expect = bw.track_text(doc)
    assert item["brk_text"] == (expect if isinstance(expect, str) and expect else None)
    summary = bw.summary_text(["shadow"])
    if summary:
        assert row["brk_summary"] == summary
    else:
        assert "brk_summary" not in row


def test_real_bw_A4_one_break_push_reads_one_sent():
    bw = _real_bw()
    docs = [_doc("GGA", "bull_flag", push={"state": "pushed"}),
            _doc("GGB", "bull_flag", minute=52, push={"state": "pushed"}),
            _doc("GGC", "kiss_fly", minute=53, brk=_brk("pushed"))]
    row = _payload(docs, {"pushed": 2})["passes"][KIND]
    assert row["brk_summary"] == bw.summary_text(["pushed"])
    assert "1 sent" in row["brk_summary"]
    assert row["counts"] == {"pushed": 2}
