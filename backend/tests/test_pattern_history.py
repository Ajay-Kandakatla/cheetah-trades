"""Tests for the pattern observation ledger (patterns/history) — event-keyed
dedup, pessimistic grading math, and the accuracy aggregation. Synthetic
frames + a fake Mongo collection; no network.
"""
import numpy as np
import pandas as pd

from patterns import history


# ── fake Mongo collection (just enough surface for the module) ───────────────
class FakeColl:
    def __init__(self):
        self.docs: dict = {}

    def update_one(self, q, u, upsert=False):
        _id = q["_id"]
        class R:  # noqa: N801
            upserted_id = None
        r = R()
        if "$setOnInsert" in u:
            if _id not in self.docs:
                self.docs[_id] = {"_id": _id, **u["$setOnInsert"]}
                r.upserted_id = _id
        if "$set" in u and _id in self.docs:
            self.docs[_id].update(u["$set"])
        return r

    def find(self, q=None):
        q = q or {}
        for d in list(self.docs.values()):
            if "resolved" in q and d.get("resolved") != q["resolved"]:
                continue
            yield d

    def limit_find(self, q):
        return self.find(q)


class _Cursor(list):
    def limit(self, n):
        return self[:n]


def _coll_with_limit(fake):
    orig_find = fake.find
    def find(q=None):
        return _Cursor(orig_find(q))
    fake.find = find
    return fake


def _df(closes, start="2026-01-05"):
    idx = pd.bdate_range(start, periods=len(closes))
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"open": np.r_[c[0], c[:-1]], "high": c + 0.5, "low": c - 0.5,
                         "close": c, "volume": np.full(len(c), 1e6)}, index=idx)


def _verdicts():
    return [{
        "symbol": "AAA",
        "sepa": {"rs_rank": 90, "stage": 2, "is_buyable": True, "is_candidate": True},
        "matches": [{"pattern": "double_bottom", "status": "confirmed",
                     "confirmed_date": "2026-06-09", "neckline": 100.0,
                     "target": 110.0, "stop": 95.0, "last_close": 101.0}],
        "candles": {"formations": [
            {"name": "hammer", "read": "bullish_reversal_setup", "date": "2026-06-09"},
            {"name": "doji", "read": "indecision", "date": "2026-06-09"}],
            "last_bar": {}},
    }, {
        "symbol": "BBB", "sepa": {},
        "matches": [{"pattern": "cup_with_handle", "status": "forming",
                     "neckline": 50.0, "target": 55.0, "stop": 46.0,
                     "last_close": 48.5, "to_confirm_pct": 3.1}],
        "candles": None,
    }]


def test_record_dedups_by_event(monkeypatch):
    fake = FakeColl()
    monkeypatch.setattr(history, "_coll", lambda: fake)
    n1 = history.record_observations(_verdicts(), et_date="2026-06-10")
    n2 = history.record_observations(_verdicts(), et_date="2026-06-11")  # re-scan next day
    assert n1 == 3                       # confirmed W + forming cup + hammer (doji skipped)
    assert n2 == 0                       # same events — nothing recounted
    kinds = sorted(d["kind"] for d in fake.docs.values())
    assert kinds == ["candle", "pattern", "pattern"]


def test_grade_confirmed_target_first():
    # entry 101 → climbs to 115 (target 110 hit inside the 21-bar window)
    # without touching stop 95
    df = _df(list(np.linspace(100, 101, 30)) + list(np.linspace(101, 115, 25)))
    obs = {"et_date": df.index[29].strftime("%Y-%m-%d"), "status": "confirmed",
           "obs_close": 101.0, "target": 110.0, "stop": 95.0, "neckline": 100.0}
    res = history._grade_pattern(df, obs)
    assert res["outcome"] == "target_first"
    assert res["bars_to_outcome"] is not None


def test_grade_confirmed_stop_wins_ambiguity():
    # one violent bar whose range touches BOTH target and stop → stop (pessimistic)
    closes = list(np.linspace(100, 101, 30)) + [101.0] * 25
    df = _df(closes)
    j = 32
    df.iloc[j, df.columns.get_loc("high")] = 120.0
    df.iloc[j, df.columns.get_loc("low")] = 90.0
    obs = {"et_date": df.index[29].strftime("%Y-%m-%d"), "status": "confirmed",
           "obs_close": 101.0, "target": 110.0, "stop": 95.0, "neckline": 100.0}
    res = history._grade_pattern(df, obs)
    assert res["outcome"] == "stop_first"


def test_grade_confirmed_unresolved_until_window_or_hit():
    # nothing hit and only 5 bars after the observation → stays unresolved
    df = _df(list(np.linspace(100, 101, 30)) + [101.0] * 5)
    obs = {"et_date": df.index[29].strftime("%Y-%m-%d"), "status": "confirmed",
           "obs_close": 101.0, "target": 110.0, "stop": 95.0, "neckline": 100.0}
    assert history._grade_pattern(df, obs) is None


def test_grade_forming_confirms_later():
    # forming under line 102; closes cross it 4 bars after the observation
    df = _df(list(np.linspace(98, 100, 30)) + [100.5, 101.0, 101.5, 103.0] + [104.0] * 20)
    obs = {"et_date": df.index[29].strftime("%Y-%m-%d"), "status": "forming",
           "obs_close": 100.0, "neckline": 102.0, "stop": 93.0}
    res = history._grade_pattern(df, obs)
    assert res["outcome"] == "confirmed"
    assert res["bars_to_outcome"] == 4


def test_grade_candle_direction():
    df = _df(list(np.linspace(100, 100, 20)) + [100, 101, 102, 103, 104, 105] + [105] * 5)
    obs = {"et_date": df.index[20].strftime("%Y-%m-%d"),
           "read": "bullish_reversal_setup", "obs_close": 100.0}
    res = history._grade_candle(df, obs)
    assert res["outcome"] == "hit" and res["fwd_5_pct"] > 0
    obs_bear = {**obs, "read": "bearish_warning"}
    assert history._grade_candle(df, obs_bear)["outcome"] == "miss"


def test_accuracy_aggregates(monkeypatch):
    fake = _coll_with_limit(FakeColl())
    monkeypatch.setattr(history, "_coll", lambda: fake)
    fake.docs = {
        "a": {"_id": "a", "kind": "pattern", "pattern": "double_bottom", "status": "confirmed",
              "et_date": "2026-06-01", "resolved": True, "outcome": "target_first",
              "fwd_21_pct": 6.0, "is_buyable": True,
              "obs_close": 100.0, "target": 110.0, "stop": 95.0},
        "b": {"_id": "b", "kind": "pattern", "pattern": "double_bottom", "status": "confirmed",
              "et_date": "2026-06-02", "resolved": True, "outcome": "stop_first",
              "fwd_21_pct": -4.0, "is_buyable": False,
              "obs_close": 100.0, "target": 108.0, "stop": 90.0},
        "c": {"_id": "c", "kind": "pattern", "pattern": "cup_with_handle", "status": "forming",
              "et_date": "2026-06-03", "resolved": True, "outcome": "confirmed"},
        "d": {"_id": "d", "kind": "candle", "formation": "hammer",
              "et_date": "2026-06-03", "resolved": True, "outcome": "hit", "fwd_5_pct": 2.0},
        "e": {"_id": "e", "kind": "pattern", "pattern": "double_bottom", "status": "confirmed",
              "et_date": "2026-06-09", "resolved": False},
    }
    acc = history.accuracy()
    db = acc["patterns"]["double_bottom"]["confirmed"]
    assert db["n"] == 2
    assert db["target_before_stop_pct"] == 50.0
    assert db["buyable_n"] == 1 and db["buyable_target_before_stop_pct"] == 100.0
    # Bracket-context fields (2026-07-10 audit): distances + gross expectancy
    # per decided trade — the numbers that make hit-% comparable across patterns.
    # a: tgt 10% / stp 5% away, won +10; b: tgt 8% / stp 10% away, lost −10.
    assert db["median_target_dist_pct"] == 10.0
    assert db["median_stop_dist_pct"] == 10.0
    assert db["expectancy_pct"] == 0.0             # (+10 − 10) / 2 decided
    assert "never compare the raw %" in acc["conventions"]["bracket_note"]
    forming = acc["patterns"]["cup_with_handle"]["forming"]
    assert forming["went_on_to_confirm_pct"] == 100.0
    assert "expectancy_pct" not in forming         # forming rows race no bracket
    assert acc["candles"]["hammer"]["direction_hit_pct"] == 100.0
    assert acc["pending"] == 1
    assert "not a promise" in acc["disclaimer"]
