"""SEPA top-picks ranking — behavioral (2026-06-02).

The portfolio "what do I buy now" indicator must rank by ACTIONABILITY, not raw
score: a name breaking out TODAY outranks a higher-scored name that is `is_buyable`
only via an in-base pocket pivot (still below its pivot, reads WAIT). Backfills
with `setup_ready` so the card isn't empty on a quiet day.
"""
from sepa import top_picks, scanner


def _row(sym, score, *, buyable=False, ready=False, dsb=None):
    return {
        "symbol": sym, "score": score, "is_buyable": buyable, "setup_ready": ready,
        "volume": {"days_since_breakout": dsb},
        "trend": {"passed": 8}, "rs_rank": 90,
        "entry_setup": {"pivot": 100.0, "stop": 92.0},
        "entry_exit": {"decision": "ENTER", "entry": {"zone_lo": 100.0}},
    }


def _scan(rows, **kw):
    base = {"candidates": rows, "analyzed": len(rows), "buyable_count": sum(1 for r in rows if r["is_buyable"]), "generated_at": 1}
    base.update(kw)
    return base


def test_fresh_breakout_outranks_higher_score_in_base(monkeypatch):
    rows = [
        _row("INBASE", 99, buyable=True, dsb=None),  # higher score, in-base pocket pivot (tier 2)
        _row("FRESH", 80, buyable=True, dsb=0),       # lower score, breaking out today (tier 0)
    ]
    monkeypatch.setattr(scanner, "load_latest", lambda: _scan(rows))
    picks = top_picks.top_picks(2)["picks"]
    assert picks[0]["symbol"] == "FRESH"
    assert picks[0]["tier"] == 0


def test_within_tier_ranks_by_score(monkeypatch):
    rows = [_row("A", 70, buyable=True, dsb=0), _row("B", 95, buyable=True, dsb=0)]
    monkeypatch.setattr(scanner, "load_latest", lambda: _scan(rows))
    assert [p["symbol"] for p in top_picks.top_picks(2)["picks"]] == ["B", "A"]


def test_backfills_with_setup_ready(monkeypatch):
    rows = [
        _row("BUY1", 90, buyable=True, dsb=0),
        _row("RDY1", 85, ready=True),
        _row("RDY2", 80, ready=True),
    ]
    monkeypatch.setattr(scanner, "load_latest", lambda: _scan(rows))
    picks = top_picks.top_picks(3)["picks"]
    st = {p["symbol"]: p["status"] for p in picks}
    assert st == {"BUY1": "buyable", "RDY1": "ready", "RDY2": "ready"}


def test_empty_when_no_scan(monkeypatch):
    monkeypatch.setattr(scanner, "load_latest", lambda: None)
    out = top_picks.top_picks(3)
    assert out["picks"] == []
