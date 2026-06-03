"""Locks the Top-Picks tracker reconstruction (sepa/top_picks_history.py).

Two pure functions, no Mongo:
  • pickset_from_quals — re-derive a scan's top-N pick set from qualifier
    snapshots, with the SAME gate + actionability ordering top_picks.py uses live.
  • build_tracker      — streak / first-seen / score-trend / churn over a sequence
    of per-scan pick sets.
"""
from sepa.top_picks_history import build_tracker, pickset_from_quals


def _qual(sym, score, stage=2, setup=True, hv=False, pp=False, dsb=None):
    return {
        "symbol": sym, "score": score, "stage": stage,
        "entry_setup": {"pivot": 10.0} if setup else None,
        "volume": {"high_vol_breakout": hv, "pocket_pivot": pp,
                   "days_since_breakout": dsb},
    }


def test_pickset_gate_and_ordering():
    quals = [
        _qual("A", 80, hv=True, dsb=0),        # buyable tier 0 (breaking out today)
        _qual("B", 90, hv=True, dsb=3),        # buyable tier 1 (this week)
        _qual("C", 95, pp=True, dsb=None),     # buyable tier 2 (in-base pocket pivot)
        _qual("D", 99),                        # ready (stage2+setup, no breakout)
        _qual("E", 100, stage=1, hv=True),     # excluded — not stage 2
        _qual("F", 100, setup=False, hv=True), # excluded — no entry_setup
        _qual("G", None, hv=True, dsb=0),      # excluded — no score
    ]
    picks = pickset_from_quals(quals, 10)
    assert [p["symbol"] for p in picks] == ["A", "B", "C", "D"]
    assert picks[0]["status"] == "buyable" and picks[0]["tier"] == 0
    assert picks[3]["status"] == "ready"
    # buyable always ranks ahead of a higher-scoring ready name
    assert picks[0]["score"] < picks[3]["score"]


def test_pickset_respects_n():
    quals = [_qual("A", 80, hv=True, dsb=0), _qual("B", 90, hv=True, dsb=3)]
    assert [p["symbol"] for p in pickset_from_quals(quals, 1)] == ["A"]


def _set(t, date, picks):
    return {"t": t, "date": date,
            "picks": [{"symbol": s, "score": sc, "status": "buyable", "tier": 0}
                      for s, sc in picks]}


def test_build_tracker_streak_churn_trend():
    sets = [
        _set(1, "d1", [("X", 10), ("Y", 20)]),
        _set(2, "d2", [("X", 12), ("Z", 30)]),
        _set(3, "d3", [("X", 11), ("Z", 35), ("W", 40)]),
    ]
    out = build_tracker(sets, 5)
    cur = {c["symbol"]: c for c in out["current"]}

    assert cur["X"]["streak"] == 3 and cur["X"]["appearances"] == 3
    assert cur["X"]["first_date"] == "d1" and cur["X"]["score_trend"] == "▼"  # 12→11
    assert cur["X"]["is_new"] is False

    assert cur["Z"]["streak"] == 2 and cur["Z"]["first_date"] == "d2"
    assert cur["Z"]["score_trend"] == "▲"                                     # 30→35

    assert cur["W"]["streak"] == 1 and cur["W"]["is_new"] is True
    assert cur["W"]["score_trend"] == "•"                                     # first sighting

    assert out["churn"] == {"entered": ["W"], "dropped": []}                       # set3 vs set2

    tl = out["timeline"]
    assert tl[0]["entered"] == [] and tl[0]["dropped"] == []                       # no prior
    assert tl[1]["entered"] == ["Z"] and tl[1]["dropped"] == ["Y"]                 # d2 vs d1
    assert tl[2]["entered"] == ["W"] and tl[2]["dropped"] == []                    # d3 vs d2


def test_build_tracker_empty():
    out = build_tracker([], 5)
    assert out["current"] == [] and out["timeline"] == []
    assert out["churn"] == {"entered": [], "dropped": []}
