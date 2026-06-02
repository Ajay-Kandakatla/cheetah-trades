"""SEPA rank-leaderboard aggregation — behavioral (2026-06-02).

Honourable mentions = names that scored high THROUGHOUT the window (persistence),
with rank-volatility and a 'primed' flag for catch-it-before-it-breaks. Verifies:
persistence ranking, volatility detection (was-high-then-dropped), and the
status/flag derivation from the live scan.
"""
from sepa import leaderboard as lb


def _run(ranking):
    """ranking: list of symbols best->worst → {rank, score} dicts."""
    return {
        "rank": {s: i + 1 for i, s in enumerate(ranking)},
        "score": {s: 100 - i for i, s in enumerate(ranking)},
    }


def test_persistence_orders_honourable_mentions():
    # STEADY top-3 every run; FLAKY only sometimes; LOW never near top.
    runs = [_run(["STEADY", "FLAKY", "LOW"]) for _ in range(4)]
    runs[1] = _run(["STEADY", "X1", "X2", "X3", "FLAKY"])   # FLAKY slips to #5
    rows = lb.aggregate(runs, live={}, n=10)
    syms = [r["symbol"] for r in rows]
    assert syms[0] == "STEADY"
    assert rows[0]["persistence_pct"] == 100


def test_volatility_flag_for_was_high_then_dropped():
    # WDC-like: #1 for MOST of the window (high persistence), craters in the
    # newest run — exactly the "was a leader, just cooled off" honourable mention.
    fillers = [f"F{i}" for i in range(40)]
    runs = [_run(fillers + ["MOVER"])]                       # newest: MOVER #41 (dropped)
    runs += [_run(["MOVER"] + fillers) for _ in range(5)]    # earlier: MOVER #1
    rows = lb.aggregate(runs, live={}, n=100)
    mover = next(r for r in rows if r["symbol"] == "MOVER")
    assert mover["current_rank"] == 41                       # newest run
    assert mover["best_rank"] == 1
    assert mover["worst_rank"] >= lb.VOLATILE_RANGE
    assert mover["rank_range"] >= lb.VOLATILE_RANGE
    assert mover["flag"] == "volatile"
    assert mover["persistence_pct"] >= 80                    # high through the window


def test_primed_flag_from_live_setup_ready():
    runs = [_run(["RDY", "A", "B"])]
    rows = lb.aggregate(runs, live={"RDY": {"setup_ready": True, "is_buyable": False, "rs_rank": 88}}, n=5)
    rdy = next(r for r in rows if r["symbol"] == "RDY")
    assert rdy["status"] == "ready"
    assert rdy["flag"] == "primed"            # catch-ahead candidate
    assert rdy["rs_rank"] == 88


def test_breaking_out_flag_when_buyable_now():
    runs = [_run(["BO", "A"])]
    rows = lb.aggregate(runs, live={"BO": {"is_buyable": True}}, n=5)
    assert next(r for r in rows if r["symbol"] == "BO")["flag"] == "breaking_out"


def test_current_rank_is_from_newest_run():
    # newest run first → current_rank reflects the latest, not the average.
    runs = [_run(["Z", "Q"]), _run(["Q", "Z"])]
    rows = lb.aggregate(runs, live={}, n=5)
    z = next(r for r in rows if r["symbol"] == "Z")
    assert z["current_rank"] == 1            # newest run had Z at #1
    assert z["worst_rank"] == 2
