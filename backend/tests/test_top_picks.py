"""SEPA top-picks ranking — behavioral (2026-06-02; conviction 2026-06-22).

The portfolio "what do I buy now" indicator must rank by ACTIONABILITY, not raw
score: a name breaking out TODAY outranks a higher-scored name that is `is_buyable`
only via an in-base pocket pivot (still below its pivot, reads WAIT). WITHIN a
tier the order is by CONVICTION (volume + dried volume + momentum,
sepa.conviction), not raw score (Ajay 2026-06-22). A climax-top distribution name
is a SELL, never a top pick (TTLAC pp.186-188) — excluded from the backfill.
Backfills with `setup_ready` so the card isn't empty on a quiet day.
"""
from sepa import top_picks, scanner


def _row(sym, score, *, buyable=False, ready=False, dsb=None,
         conviction=None, distribution_selling=False, setup_type="VCP"):
    return {
        "symbol": sym, "score": score, "conviction": conviction,
        "is_buyable": buyable, "setup_ready": ready,
        "distribution_selling": distribution_selling,
        "volume": {"days_since_breakout": dsb},
        "trend": {"passed": 8}, "rs_rank": 90,
        "entry_setup": {"type": setup_type, "pivot": 100.0, "stop": 92.0},
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


def test_within_tier_ranks_by_conviction(monkeypatch):
    # 2026-06-22: within an actionability tier the order is by CONVICTION
    # (volume + dried volume + momentum), NOT raw score. Equal score, B has the
    # higher conviction → B leads. (A would win a score sort; it must not here.)
    rows = [_row("A", 95, buyable=True, dsb=0, conviction=40),
            _row("B", 95, buyable=True, dsb=0, conviction=88)]
    monkeypatch.setattr(scanner, "load_latest", lambda: _scan(rows))
    assert [p["symbol"] for p in top_picks.top_picks(2)["picks"]] == ["B", "A"]


def test_climax_distribution_excluded_from_backfill(monkeypatch):
    # 2026-06-22 (AMAT-class): a climax-top distribution name is a SELL, never a
    # top pick (TTLAC pp.186-188). Even when buyable is thin and the climax name
    # is setup_ready with the highest score AND highest conviction, it must NOT
    # backfill the card — the same gate that blocks is_buyable blocks the pick.
    rows = [
        _row("BUY1", 90, buyable=True, dsb=0, conviction=70),
        _row("AMAT", 99, ready=True, conviction=95, distribution_selling=True),
        _row("RDY2", 60, ready=True, conviction=50),
    ]
    monkeypatch.setattr(scanner, "load_latest", lambda: _scan(rows))
    syms = [p["symbol"] for p in top_picks.top_picks(3)["picks"]]
    assert "AMAT" not in syms
    assert syms == ["BUY1", "RDY2"]


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


def test_bare_breakout_excluded_from_top_picks(monkeypatch):
    # 2026-06-22: a top pick must come from a REAL BASE (VCP / Power Play /
    # pocket pivot). A bare BREAKOUT (no detected base) is excluded even when
    # buyable with the highest conviction — the "non-VCP" names stay off the
    # premium shortlist.
    rows = [
        _row("BARE", 99, buyable=True, dsb=0, conviction=95, setup_type="BREAKOUT"),
        _row("VCP1", 80, buyable=True, dsb=0, conviction=70, setup_type="VCP"),
        _row("PP1",  75, buyable=True, dsb=0, conviction=60, setup_type="POWER_PLAY"),
    ]
    monkeypatch.setattr(scanner, "load_latest", lambda: _scan(rows))
    syms = [p["symbol"] for p in top_picks.top_picks(3)["picks"]]
    assert "BARE" not in syms
    assert syms == ["VCP1", "PP1"]    # bare breakout dropped despite top conviction


def test_pocket_pivot_counts_as_a_base(monkeypatch):
    """A pocket pivot is an in-base institutional buy → counts as a real base."""
    rows = [_row("PKT", 85, buyable=True, dsb=0, conviction=80, setup_type="POCKET_PIVOT")]
    monkeypatch.setattr(scanner, "load_latest", lambda: _scan(rows))
    assert [p["symbol"] for p in top_picks.top_picks(3)["picks"]] == ["PKT"]
