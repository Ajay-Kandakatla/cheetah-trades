"""🧬 Medical catalysts API (catalysts/api.py + catalysts/medical/board.py, spec §3.10).

Route order is the trap: `/catalysts/medical` declared below
`/catalysts/{ticker}` is served by `deep_dive`. NEGATIVES: no key named
entry / stop / target anywhere in either payload; NaN serialises as null; the
roll-up counts ONE observation per (ticker, session) per group.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts.medical import board as B   # noqa: E402
from catalysts.medical import store as S   # noqa: E402
from tests.test_med_store import FakeColl  # noqa: E402

ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 29, 8, 0, tzinfo=ET)


def ev(key, ticker, et_, td, sd, **kw):
    d = {"_id": key, "ticker": ticker, "company": ticker, "event_type": et_, "type_dir": td, "subtype": None,
         "direction": None, "phase": None, "regulator": None, "trials": [], "modality": ["unclassified"],
         "areas": ["unclassified"], "session_date": sd, "headline": key,
         "published_at": datetime(2026, 9, 28, 6, 34, tzinfo=timezone.utc),
         "first_seen_at": datetime(2026, 9, 28, 11, 25, tzinfo=timezone.utc),
         "sources": [{"provider": "finnhub", "source": "Benzinga", "title": key, "url": "https://x",
                      "published_et": "2026-09-28T02:34:00-04:00"}],
         "push": {"state": "pending", "reason": None, "at": None},
         "reaction": {"at_detection": {"move_pct": 72.0}, "liquidity": {"base_close": 32.35, "adv50_usd": 22.7e6},
                      "at_close": {"day_pct": 178.0}, "fwd": {"ret_5d_pct": None, "ret_21d_pct": None}}}
    d.update(kw)
    return d


def events():
    return FakeColl([
        ev("KOD|topline_positive|2026-09-28", "KOD", "topline", "topline_positive", "2026-09-28",
           direction="positive", phase="3", trials=["DAYBREAK"], modality=["antibody_bispecific"],
           areas=["ophthalmology"]),
        ev("MIRM|fda_approval|2026-09-28", "MIRM", "fda_approval", "fda_approval", "2026-09-28",
           subtype="novel", regulator="FDA", areas=["rare_disease"],
           reaction={"at_detection": {"move_pct": -1.0}, "liquidity": {}, "at_close": {"day_pct": -1.9},
                     "fwd": {}}),
        ev("MIRM|topline_positive|2026-09-28", "MIRM", "topline", "topline_positive", "2026-09-28",
           direction="positive", phase="3", areas=["infectious_disease", "rare_disease"],
           reaction={"at_detection": {"move_pct": float("nan")}, "liquidity": {}, "at_close": {"day_pct": -1.9},
                     "fwd": {}}),
        ev("MNOV|topline_unknown|2026-09-28", "MNOV", "topline", "topline_unknown", "2026-09-28",
           direction="unknown"),
        ev("UNRESOLVED:elevar|fda_approval|2026-09-24", None, "fda_approval", "fda_approval", "2026-09-24",
           company="Elevar Therapeutics", subtype="novel", regulator="FDA", areas=["oncology"]),
        ev("OLD|fda_approval|2026-06-01", "OLD", "fda_approval", "fda_approval", "2026-06-01", subtype="novel"),
    ])


def keys_of(o, acc=None):
    acc = acc if acc is not None else set()
    if isinstance(o, dict):
        for k, v in o.items():
            acc.add(str(k))
            keys_of(v, acc)
    elif isinstance(o, list):
        for v in o:
            keys_of(v, acc)
    return acc


def test_board_payload_shape_labels_and_order():
    p = B.board_payload(30, events_coll=events(), pass_coll=FakeColl(), now=NOW)
    assert p["labels"]["setup"] == "pending study" and p["labels"]["measured"] is False
    assert p["labels"]["status"] == "unmeasured" and "UNMEASURED" in p["labels"]["note"]
    keys = [r["event_key"] for r in p["events"]]
    assert "OLD|fda_approval|2026-06-01" not in keys, "outside the 30-day window"
    assert keys[0] == "KOD|topline_positive|2026-09-28", "newest session, high impact, biggest move first"
    kod = p["events"][0]
    assert kod["impact"] == "high" and kod["label"] == "Phase 3 topline positive"
    assert kod["links"] == {"supply": "/sepa/KOD?tab=supply", "timeline": "/sepa/KOD?tab=catalyst"}
    assert kod["area_primary"] == "ophthalmology" and kod["n_sources"] == 1
    un = [r for r in p["events"] if r["ticker"] is None][0]
    assert un["links"] == {"supply": None, "timeline": None} and un["company"] == "Elevar Therapeutics"
    assert p["counts"]["unresolved_ticker"] == 1 and p["counts"]["events"] == 5
    assert p["push"]["kind"] == "med_catalyst" and "$2" in p["push"]["gate_text"]
    assert p["pass"] == {"as_of": None, "date": None, "counts": {}}
    assert {s["key"] for s in p["sources"]} == {"finnhub", "sec", "massive", "fda_rss"}
    assert [f["key"] for f in p["taxonomy"]["families"]][:2] == ["fda", "trial"]


def test_filters():
    c = events()
    only_high = B.board_payload(30, high_only=True, events_coll=c, pass_coll=FakeColl(), now=NOW)["events"]
    assert {r["ticker"] for r in only_high} == {"KOD", "MIRM", None}
    assert all(r["impact"] == "high" for r in only_high)
    fam = B.board_payload(30, type="trial", events_coll=c, pass_coll=FakeColl(), now=NOW)["events"]
    assert {r["event_type"] for r in fam} == {"topline"}
    area = B.board_payload(30, area="rare_disease", events_coll=c, pass_coll=FakeColl(), now=NOW)["events"]
    assert {r["ticker"] for r in area} == {"MIRM"}
    unc = B.board_payload(30, modality="unclassified", events_coll=c, pass_coll=FakeColl(), now=NOW)["events"]
    assert "KOD" not in {r["ticker"] for r in unc}


def test_rollup_one_observation_per_ticker_session_and_small_n_by_unique_tickers():
    p = B.board_payload(30, events_coll=events(), pass_coll=FakeColl(), now=NOW)
    rare = [r for r in p["rollup"]["by_area"] if r["key"] == "rare_disease"][0]
    assert rare["n_events"] == 2 and rare["n_obs"] == 1, "MIRM's approval + Ph3 data = ONE observation"
    assert rare["median_day_pct"] == pytest.approx(-1.9) and rare["n_tickers"] == 1 and rare["small_n"] is True
    assert rare["n_positive"] == 2 and rare["n_negative"] == 0
    onc = [r for r in p["rollup"]["by_area"] if r["key"] == "oncology"][0]
    assert onc["n_obs"] == 0 and onc["median_day_pct"] is None, "an unresolved row has no price"
    assert p["rollup"]["note"].startswith("Descriptive and UNMEASURED")
    assert [r["n_events"] for r in p["rollup"]["by_area"]] == sorted(
        [r["n_events"] for r in p["rollup"]["by_area"]], reverse=True)


def test_sign_counts():
    assert B.sign({"event_type": "fda_crl"}) == -1 and B.sign({"event_type": "fda_revoked"}) == -1
    assert B.sign({"event_type": "clinical_hold", "subtype": "placed"}) == -1
    assert B.sign({"event_type": "clinical_hold", "subtype": "lifted"}) == 0
    assert B.sign({"event_type": "conference_data", "direction": "positive"}) == 1
    assert B.sign({"event_type": "financing"}) == 0


def test_symbol_payload_and_tracking_since():
    st = FakeColl([{"_id": "baseline", "lap_complete_at": datetime(2026, 9, 29, 9, 0, tzinfo=timezone.utc)}])
    p = B.symbol_payload("mirm", 180, events_coll=events(), state_coll=st, now=NOW)
    assert p["symbol"] == "MIRM" and len(p["events"]) == 2 and p["tracking_since"] == "2026-09-29"
    assert p["labels"]["setup"] == "pending study"
    empty = B.symbol_payload("ZZZZ", 180, events_coll=events(), state_coll=FakeColl(), now=NOW)
    assert empty["events"] == [] and empty["tracking_since"] is None


def test_NEGATIVE_no_entry_stop_or_target_key_anywhere():
    p = B.board_payload(30, events_coll=events(), pass_coll=FakeColl(), now=NOW)
    q = B.symbol_payload("KOD", 180, events_coll=events(), state_coll=FakeColl(), now=NOW)
    for payload in (p, q):
        ks = {k.lower() for k in keys_of(payload)}
        assert not ks & {"entry", "stop", "target", "entry_price", "stop_price", "target_price"}


# ── the routes ──────────────────────────────────────────────────────────────
@pytest.fixture
def client(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from catalysts import api
    c = events()
    monkeypatch.setattr(S, "colls", lambda injected=None: {S.EVENTS: c, S.STATE: FakeColl(),
                                                           S.ARTICLES: FakeColl(), S.ALERTS: FakeColl()})
    from supply_demand import alert_status as AS
    monkeypatch.setattr(AS, "_coll", lambda: FakeColl())
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_route_order_the_board_route_is_not_swallowed_by_deep_dive(client):
    tc = client
    r = tc.get("/catalysts/medical?days=180")
    assert r.status_code == 200
    body = r.json()
    assert "labels" in body and "deep_dive" not in body and "events" in body
    from catalysts import api
    paths = [getattr(rt, "path", "") for rt in api.router.routes]
    assert paths.index("/catalysts/medical") < paths.index("/catalysts/{ticker}")


def test_symbol_route_and_nan_is_null(client):
    tc = client
    r = tc.get("/catalysts/medical/MIRM?days=730")
    assert r.status_code == 200
    raw = r.text
    assert "NaN" not in raw
    body = json.loads(raw)
    assert body["symbol"] == "MIRM" and len(body["events"]) == 2
    ph3 = [e for e in body["events"] if e["type_dir"] == "topline_positive"][0]
    assert ph3["reaction"]["at_detection"]["move_pct"] is None
    assert body["labels"]["setup"] == "pending study"


def test_NEGATIVE_query_bounds(client):
    tc = client
    assert tc.get("/catalysts/medical?days=0").status_code == 422
    assert tc.get("/catalysts/medical?days=181").status_code == 422
    assert tc.get("/catalysts/medical/KOD?days=731").status_code == 422
