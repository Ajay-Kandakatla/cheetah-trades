"""Breakout push notifications are BUYABLE-ONLY (Ajay 2026-06-18: "kill all
random breakout push notification besides the buyable").

Both breakout-alert sources must drop names that don't pass the strict Minervini
buy gate (is_buyable) in the live scan.

  cd backend && .venv/bin/python -m pytest tests/test_breakout_alerts_buyable.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── volume-breakout alerts (sepa/breakouts.detect_volume_breakouts) ──────────

class _Coll:
    def __init__(self, docs):
        self._docs = docs

    def find_one(self, q=None, sort=None):
        return self._docs[0] if self._docs else None

    def find(self, q=None):
        return iter(self._docs)


class _DB:
    def __init__(self, runs, cands):
        self.scan_runs = _Coll(runs)
        self.candidate_snapshots = _Coll(cands)


def test_volume_breakouts_only_fire_for_buyable(monkeypatch):
    from sepa import breakouts, scanner
    run = {"_id": "run1", "generated_at": 1}
    cands = [
        {"symbol": "AAA", "score": 90, "volume": {"high_vol_breakout": True}},   # buyable
        {"symbol": "BBB", "score": 90, "volume": {"high_vol_breakout": True}},   # NOT buyable
    ]
    monkeypatch.setattr(breakouts, "_get_db", lambda: _DB([run], cands))
    monkeypatch.setattr(scanner, "load_latest", lambda: {"all_results": [
        {"symbol": "AAA", "is_buyable": True},
        {"symbol": "BBB", "is_buyable": False},     # broke out but not buyable → no push
    ]})
    fired = []
    monkeypatch.setattr(breakouts, "_record_alert",
                        lambda db, **kw: fired.append(kw["ticker"]) or "id")
    monkeypatch.setattr(breakouts, "_passes_score_floor", lambda s: True)
    monkeypatch.setattr(breakouts, "_recent_alert_exists", lambda db, t, k: False)

    out = breakouts.detect_volume_breakouts()
    assert fired == ["AAA"]                         # only the buyable breakout alerts
    assert out["alerts"] == 1


def test_volume_breakouts_suppress_all_when_scan_unavailable(monkeypatch):
    # Fail-closed: if the live scan can't be read, suppress (the user wants quiet).
    from sepa import breakouts, scanner
    run = {"_id": "r", "generated_at": 1}
    cands = [{"symbol": "AAA", "score": 90, "volume": {"high_vol_breakout": True}}]
    monkeypatch.setattr(breakouts, "_get_db", lambda: _DB([run], cands))
    monkeypatch.setattr(scanner, "load_latest", lambda: None)
    fired = []
    monkeypatch.setattr(breakouts, "_record_alert", lambda db, **kw: fired.append(kw["ticker"]))
    monkeypatch.setattr(breakouts, "_passes_score_floor", lambda s: True)
    monkeypatch.setattr(breakouts, "_recent_alert_exists", lambda db, t, k: False)
    breakouts.detect_volume_breakouts()
    assert fired == []                              # nothing buyable known → no pushes


# ── leaderboard-breakout alerts (sepa/leaderboard_breakout_watch.run) ─────────

class _LbDB:
    class _Alerts:
        def find_one(self, q): return None
        def insert_one(self, d): return None
    leaderboard_breakout_alerts = _Alerts()


def test_leaderboard_breakouts_only_fire_for_buyable(monkeypatch):
    from sepa import leaderboard_breakout_watch as lbw
    monkeypatch.setattr(lbw, "_ensure_pref_backfill", lambda db: None)
    monkeypatch.setattr(lbw.history, "_get_db", lambda: _LbDB())
    monkeypatch.setattr(lbw.lb, "leaderboard",
                        lambda *a, **k: {"leaders": [{"symbol": "AAA", "current_rank": 1},
                                                     {"symbol": "BBB", "current_rank": 2}]})
    monkeypatch.setattr(lbw.scanner, "load_latest", lambda: {"all_results": [
        {"symbol": "AAA", "is_buyable": True},
        {"symbol": "BBB", "is_buyable": False},
    ]})
    monkeypatch.setattr(lbw, "fresh_breakouts",
                        lambda ranks, live: [{"symbol": "AAA"}, {"symbol": "BBB"}])
    pushed = {}
    monkeypatch.setattr(lbw.hooks, "notify_leaderboard_breakout",
                        lambda *, broke_out, today_et: pushed.setdefault("syms", [b["symbol"] for b in broke_out]) or {})

    out = lbw.run()
    assert out["ok"] and out["broke_out"] == 1
    assert pushed["syms"] == ["AAA"]                # BBB (not buyable) filtered out
