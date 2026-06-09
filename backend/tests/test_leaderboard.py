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


def test_earnings_quality_passes_through_from_live():
    # Ch.8 earnings quality is carried from the live candidate's fundamentals so
    # the leaderboard can show the chip; absent (non-enriched name) -> None.
    runs = [_run(["EQ", "NONE"])]
    live = {"EQ": {"fundamentals": {"earnings_quality": {"score": 80, "tier": "code33", "code_33": True}}}}
    rows = lb.aggregate(runs, live=live, n=5)
    eq = next(r for r in rows if r["symbol"] == "EQ")
    assert eq["earnings_quality"]["score"] == 80
    assert eq["earnings_quality"]["code_33"] is True
    assert next(r for r in rows if r["symbol"] == "NONE")["earnings_quality"] is None


def test_current_rank_is_from_newest_run():
    # newest run first → current_rank reflects the latest, not the average.
    runs = [_run(["Z", "Q"]), _run(["Q", "Z"])]
    rows = lb.aggregate(runs, live={}, n=5)
    z = next(r for r in rows if r["symbol"] == "Z")
    assert z["current_rank"] == 1            # newest run had Z at #1
    assert z["worst_rank"] == 2


# ── resilient_picks — "still qualifies despite the macro" (Ajay 2026-06-04) ──

def test_resilient_picks_prefers_buyable_sorted_by_score():
    # When ANY name clears the full buy gate, that's the tier — buyable only,
    # best score first. macro=None keeps it pure (no overlay).
    rows = [
        {"symbol": "AAA", "is_buyable": True,  "is_candidate": True, "score": 70, "stage": 2},
        {"symbol": "BBB", "is_buyable": True,  "is_candidate": True, "score": 90, "stage": 2},
        {"symbol": "CCC", "is_buyable": False, "is_candidate": True, "score": 99, "stage": 2},
    ]
    out = lb.resilient_picks({"all_results": rows}, None, k=5)
    assert out["tier"] == "buyable"
    assert [p["symbol"] for p in out["picks"]] == ["BBB", "AAA"]   # buyable only, score desc
    assert out["count"] == 2
    assert "Clean entry" in out["picks"][0]["why"]


def test_resilient_picks_falls_back_to_qualifiers_when_no_buyable():
    # Risk-off: nothing's a clean buy → closest QUALIFIERS (book p.79), with a
    # reason each isn't a buy. Non-candidates are excluded even at higher score.
    rows = [
        {"symbol": "Q1", "is_buyable": False, "is_candidate": True,  "score": 80, "stage": 2, "setup_ready": False},
        {"symbol": "Q2", "is_buyable": False, "is_candidate": True,  "score": 88, "stage": 3, "setup_ready": False},
        {"symbol": "NO", "is_buyable": False, "is_candidate": False, "score": 99, "stage": 2},
    ]
    out = lb.resilient_picks({"all_results": rows}, None, k=5)
    assert out["tier"] == "qualified"
    assert [p["symbol"] for p in out["picks"]] == ["Q2", "Q1"]     # candidates only, score desc
    assert "NO" not in [p["symbol"] for p in out["picks"]]         # never blur the gate
    why = {p["symbol"]: p["why"] for p in out["picks"]}
    assert "Stage-2" in why["Q2"]                                  # stage 3 → wait for stage 2
    assert "pivot" in why["Q1"].lower()                            # stage 2, no setup → wait on pivot


def test_resilient_picks_respects_k_limit():
    rows = [{"symbol": f"S{i}", "is_buyable": True, "is_candidate": True, "score": i, "stage": 2}
            for i in range(10)]
    out = lb.resilient_picks({"all_results": rows}, None, k=3)
    assert len(out["picks"]) == 3
    assert out["count"] == 10                                      # pool size, not the cap


# ── buyable note must defer to active sell-signals (Ajay 2026-06-08) ─────────
def test_buyable_note_caveats_climax_run():
    # A name that clears the full buy gate but is ALSO in a climax run is kept in
    # the buyable tier (user: "keep it, flag it") but its note flips from "Clean
    # entry" to the climax caveat — so "Buyable now" can't contradict the position
    # card's REDUCE. Minervini Ch.13 (don't initiate into a climax/parabolic).
    clean = {"symbol": "CLN", "is_buyable": True, "is_candidate": True, "score": 80, "stage": 2}
    climax = {"symbol": "CLX", "is_buyable": True, "is_candidate": True, "score": 90, "stage": 2,
              "sell_signals": {"action": "REDUCE",
                               "signals": {"climax_run_25pct_in_3w": True},
                               "climax_15d_gain_pct": 31.41}}
    out = lb.resilient_picks({"all_results": [clean, climax]}, None, k=5)
    assert out["tier"] == "buyable" and out["count"] == 2          # still listed, not dropped
    why = {p["symbol"]: p["why"] for p in out["picks"]}
    assert "Clean entry" in why["CLN"]
    assert "Clean entry" not in why["CLX"]
    assert "climax run" in why["CLX"].lower() and "31" in why["CLX"] and "Ch.13" in why["CLX"]


def test_buyable_note_caveats_extended_pivot():
    # KNX case: is_buyable fired on a LATE pocket pivot but price is +22.9% past the
    # pivot (entry_exit status missed_extended, no sell-signal). Must read
    # "extended — missed", not "Clean entry" (Ajay 2026-06-08).
    knx = {"symbol": "KNX", "is_buyable": True, "is_candidate": True, "score": 85, "stage": 2,
           "entry_setup": {"pivot": 65.77}, "last_close": 80.80,
           "entry_exit": {"entry": {"status": "missed_extended"}}}
    note = lb._buyable_note(knx)
    assert "extended" in note.lower() and "Clean entry" not in note
    assert "23" in note                                           # +23% past pivot


def test_buyable_note_helper_direct():
    assert lb._buyable_note({}) == "Clean entry — clears the full buy gate"
    assert lb._buyable_note({"sell_signals": {"action": "REDUCE", "signals": {}}}).startswith("⚠")
    assert "stop breached" in lb._buyable_note(
        {"sell_signals": {"action": "REDUCE", "signals": {"stop_loss_breached": True}}}).lower()
    # a benign/no-action sell_signals block still reads clean
    assert "Clean entry" in lb._buyable_note({"sell_signals": {"action": "HOLD", "signals": {}}})


def test_why_not_buyable_and_stage_of():
    assert "Stage-2" in lb._why_not_buyable({"stage": 3})
    assert "pivot" in lb._why_not_buyable({"stage": 2, "setup_ready": False}).lower()
    assert lb._why_not_buyable({"stage": 2, "setup_ready": True})  # non-empty
    assert lb._stage_of({"stage": 2}) == 2
    assert lb._stage_of({"stage": {"stage": 3}}) == 3              # dict form from scanner
