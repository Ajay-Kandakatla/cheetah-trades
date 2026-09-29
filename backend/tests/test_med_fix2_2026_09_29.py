"""🧬 medical catalysts — fix round 2 (2026-09-29), the non-classifier defects
the live dry run and the full suites found:

  * reaction: a snapshot print of 0.0 read as a price -> 110 of 115 events had
    move_pct −100 and the KOD push title read "· -100% ·";
  * store: a DIRECTED topline arriving after a `topline_unknown` made a SECOND
    event (CLDX, ALKS) instead of lifting the first one's direction;
  * sources: Finnhub article keys ignored the ticker, so a joint release
    ("Mirum … and Incyte Announce U.S. FDA Approval") reached only one issuer;
  * routine: the direct `companies` Healthcare read skipped the sector override
    (tests/test_sector_overrides_2026_09_19).
NEGATIVE cases for each. Purge the bytecode caches before running.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts.medical import reaction as R    # noqa: E402
from catalysts.medical import routine as RT    # noqa: E402
from catalysts.medical import sources as SRC   # noqa: E402
from catalysts.medical import store as S       # noqa: E402
from catalysts.medical import taxonomy as T    # noqa: E402
from tests.test_med_store import FakeColl      # noqa: E402

ET = ZoneInfo("America/New_York")
MON = date(2026, 9, 28)


# ── reaction: 0.0 is "no print" ─────────────────────────────────────────────
@pytest.mark.parametrize("snap", [
    {"last_trade_price": 0.0, "price": 0.0},
    {"last_trade_price": 0.0},
    {"price": 0.0},
    {"last_trade_price": -1.0, "price": None},
])
def test_NEGATIVE_a_zero_snapshot_print_is_no_price_and_no_move(snap):
    d = R.at_detection(snap, (32.35, "frame"), datetime(2026, 9, 28, 7, 31, tzinfo=ET), session_date=MON)
    assert d["price"] is None and d["move_pct"] is None


def test_a_zero_last_trade_falls_back_to_a_real_snapshot_price():
    d = R.at_detection({"last_trade_price": 0.0, "price": 40.0}, (32.35, "frame"),
                       datetime(2026, 9, 28, 7, 31, tzinfo=ET), session_date=MON)
    assert d["price"] == 40.0 and d["move_pct"] == pytest.approx((40.0 / 32.35 - 1) * 100)


def test_the_push_title_says_no_print_yet_instead_of_minus_100():
    from catalysts.medical import alerts as A
    det = R.at_detection({"price": 0.0}, (32.35, "frame"), datetime(2026, 9, 28, 7, 31, tzinfo=ET),
                         session_date=MON)
    assert A.move_text({"reaction": {"at_detection": det}}) == "no print yet"


# ── store: a directed topline lifts an earlier topline_unknown ───────────────
def _ev(td="topline_unknown", trials=(), phase="3", **kw):
    d = {"_id": S.event_key("CLDX", td, "2026-09-22"), "ticker": "CLDX", "type_dir": td, "event_type": "topline",
         "direction": td.split("_")[1], "session_date": "2026-09-22", "trials": list(trials), "phase": phase,
         "modality": ["unclassified"], "areas": ["immunology"],
         "sources": [{"provider": "finnhub", "title": "t", "article_key": "a"}],
         "published_at": datetime(2026, 9, 22, 7, 5, tzinfo=timezone.utc),
         "last_seen_at": datetime(2026, 9, 22, 7, 5, tzinfo=timezone.utc),
         "push": {"state": "not_eligible", "reason": "not_high_impact", "at": None}, "impact": "low",
         "label": "Topline results (direction not stated)"}
    d.update(kw)
    return d


WIN = dict(lo_date=date(2026, 9, 17), hi_date=date(2026, 9, 25))


def test_a_directed_topline_merges_into_the_earlier_unknown_and_lifts_it():
    first = _ev()
    c = FakeColl([first])
    pos = _ev(td="topline_positive", _id="CLDX|topline_positive|2026-09-22", secondary_missed=False,
              sources=[{"provider": "finnhub", "title": "Positive … Met Primary", "article_key": "b"}])
    t = S.find_merge_target(c, pos, **WIN)
    assert t is not None and t["_id"] == first["_id"]
    key = S.merge_into(c, t, pos, impact_fn=T.is_high_impact, label_fn=T.event_label)
    d = c.docs[key]
    assert key == "CLDX|topline_unknown|2026-09-22", "the key never changes"
    assert d["direction"] == "positive" and d["type_dir"] == "topline_positive"
    assert d["impact"] == "high" and d["label"] == "Phase 3 topline positive"
    assert d["push"]["state"] == "pending", "a lift to HIGH re-arms a not_high_impact push"
    assert len(d["sources"]) == 2


def test_NEGATIVE_an_unknown_on_a_different_trial_is_not_lifted():
    c = FakeColl([_ev(trials=("EMBARQ-CSU1",))])
    pos = _ev(td="topline_positive", trials=("OTHER-2",))
    assert S.find_merge_target(c, pos, **WIN) is None


def test_NEGATIVE_an_unknown_source_never_overwrites_a_directed_target():
    first = _ev(td="topline_positive", impact="high", push={"state": "pushed", "reason": None, "at": None})
    c = FakeColl([first])
    unk = _ev()
    t = S.find_merge_target(c, unk, **WIN)
    S.merge_into(c, t, unk, impact_fn=T.is_high_impact, label_fn=T.event_label)
    d = c.docs[first["_id"]]
    assert d["direction"] == "positive" and d["type_dir"] == "topline_positive" and d["push"]["state"] == "pushed"


def test_NEGATIVE_other_tickers_and_non_toplines_never_lift():
    c = FakeColl([_ev()])
    assert S.find_merge_target(c, _ev(td="topline_positive", ticker="ALKS"), **WIN) is None
    appr = {"ticker": "CLDX", "event_type": "fda_approval", "type_dir": "fda_approval", "trials": []}
    assert S.find_merge_target(c, appr, **WIN) is None


def test_a_phase_lift_relabels_the_event():
    first = _ev(td="topline_positive", phase=None, label="Topline positive")
    c = FakeColl([first])
    S.merge_into(c, c.find_one({"_id": first["_id"]}), _ev(td="topline_positive", phase="3"),
                 impact_fn=T.is_high_impact, label_fn=T.event_label)
    assert c.docs[first["_id"]]["label"] == "Phase 3 topline positive"


# ── sources: one Finnhub story, one article PER TICKER ───────────────────────
def test_finnhub_key_carries_the_ticker_so_a_joint_release_reaches_both_issuers():
    a = SRC.article_key({"provider": "finnhub", "id": 142500001, "ticker": "INCY"})
    b = SRC.article_key({"provider": "finnhub", "id": 142500001, "ticker": "mirm"})
    assert a == "fh:INCY:142500001" and b == "fh:MIRM:142500001" and a != b


def test_NEGATIVE_the_same_ticker_and_id_is_still_one_key_and_other_providers_are_unchanged():
    assert SRC.article_key({"provider": "finnhub", "id": 7, "ticker": "KOD"}) == \
        SRC.article_key({"provider": "finnhub", "id": 7, "ticker": "KOD"})
    assert SRC.article_key({"provider": "finnhub", "id": 7}) == "fh:7"
    assert SRC.article_key({"provider": "massive", "id": "x", "ticker": "KOD"}) == "mv:x"
    assert SRC.article_key({"provider": "sec", "adsh": "0001", "ticker": "KOD"}) == "sec:0001"


def test_two_tickers_same_story_are_two_new_articles_in_the_store():
    c = FakeColl([])
    base = {"provider": "finnhub", "title": "Mirum Pharmaceuticals and Incyte Announce U.S. FDA Approval of Atebrioz",
            "published": 1_790_380_800.0, "url": "u"}
    a1 = dict(base, ticker="INCY", key=SRC.article_key(dict(base, id=9, ticker="INCY")))
    a2 = dict(base, ticker="MIRM", key=SRC.article_key(dict(base, id=9, ticker="MIRM")))
    assert S.insert_article(c, a1)[0] == "new" and S.insert_article(c, a2)[0] == "new"
    assert S.insert_article(c, dict(a2))[0] == "dup"


# ── routine: the Healthcare read heals the sector ────────────────────────────
def test_healthcare_symbols_applies_the_override_both_ways(monkeypatch):
    from companies import sector_overrides as SO
    monkeypatch.setitem(SO.SECTOR_OVERRIDES, "ZZIN", ("Healthcare", "Biotechnology", "test: moved in"))
    monkeypatch.setitem(SO.SECTOR_OVERRIDES, "ZZOUT", ("Technology", "Software", "test: moved out"))
    docs = [{"symbol": "KOD", "sector": "Healthcare"}, {"symbol": "ZZIN", "sector": "Industrials"},
            {"symbol": "ZZOUT", "sector": "Healthcare"}, {"symbol": "AAPL", "sector": "Technology"},
            {"sector": "Healthcare"}]
    assert RT.healthcare_symbols(docs) == {"KOD", "ZZIN"}


def test_NEGATIVE_healthcare_symbols_never_mutates_the_docs_and_handles_empty():
    docs = [{"symbol": "WULF", "sector": "Financial Services"}]
    RT.healthcare_symbols(docs)
    assert docs == [{"symbol": "WULF", "sector": "Financial Services"}]
    assert RT.healthcare_symbols([]) == set() and RT.healthcare_symbols(None) == set()


def test_the_default_healthcare_reader_queries_the_override_names_too(monkeypatch):
    seen = {}

    class _Coll:
        def find(self, q, proj):
            seen["q"] = q
            return [{"symbol": "KOD", "sector": "Healthcare"}]

    class _DB:
        companies = _Coll()

    import companies.store as CS
    monkeypatch.setattr(CS, "_get_db", lambda: _DB())
    assert RT._default_healthcare() == {"KOD"}
    ors = seen["q"]["$or"]
    assert {"sector": "Healthcare"} in ors and any("symbol" in o for o in ors)
