"""📋 All strategies — "To 9 EMA" column + a second served order (2026-11-16).

Ajay, verbatim: "Can you sort the table of all strategies by nearest to A+ support and then nearest to the EMA. please" +
"Add those columns to the Table and a Add to watch button". His answers: nearest = closest to the trigger; the EMA = the 9;
a remembered toggle with GG's order one click away. The server serves BOTH orders (`rank` = GG's, untouched; `near_rank`);
the FE only picks which one. NEGATIVES: GG's rank never moves; an unknown distance / EMA never sorts as 0; a warming EMA is
None, never 0; his 🚫 names stay last; the input list is never mutated; the WRITES golden does not move (identity test).
"""
from __future__ import annotations

from chart_maps.gajjala import all_table as TBL
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import tab as GT


def doc_with(values, n_bars=None, tone=None):
    n = len(values) if n_bars is None else n_bars
    bars = [{"t": f"2026-11-16 09:{30 + i:02d}", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1} for i in range(n)]
    return {"tile": {"bars5": bars, "curves5": [{"tone": tone or B.EMA_TONES[0][0], "label": "9 EMA", "values": values}]}}


def test_ema9_of_reads_the_latest_stored_bar():
    assert TBL.ema9_of(doc_with([None, 1.5, 2.25]), "5m") == 2.25


def test_ema9_of_negatives_never_zero():
    assert TBL.ema9_of(doc_with([1.0, None]), "5m") is None                 # warming on the latest bar
    assert TBL.ema9_of(doc_with([1.0, 0.0]), "5m") is None                  # a zero EMA is no EMA
    assert TBL.ema9_of(doc_with([1.0], n_bars=3), "5m") is None             # curve shorter than the bars
    assert TBL.ema9_of(doc_with([1.0, 2.0], tone="ema21"), "5m") is None    # the 21 is never read as the 9
    assert TBL.ema9_of({}, "5m") is None
    assert TBL.ema9_of({"tile": {"bars5": [], "curves5": []}}, "5m") is None


def row(sym, rank, dist, gap, setup="bull_flag"):
    return {"symbol": sym, "setup": setup, "rank": rank, "dist_pct": dist, "ema9_gap_pct": gap}


def test_near_order_trigger_first_then_9_ema():
    rows = [row("A", 1, 3.0, 0.1), row("B", 2, -0.5, 4.0), row("C", 3, 0.5, 1.0), row("D", 4, 0.54, -0.2)]
    out = [r["symbol"] for r in TBL.near_order(rows)]
    # |0.5| = |−0.5| = |0.54| as printed (0.5%) → the 9 EMA decides: D (0.2) · C (1.0) · B (4.0) · then A (3.0%)
    assert out == ["D", "C", "B", "A"]


def test_near_order_unknowns_last_never_zero():
    rows = [row("N", 1, None, 0.0), row("E", 2, 1.0, None), row("K", 3, 1.0, 9.0), row("Z", 4, 9.0, 0.0)]
    assert [r["symbol"] for r in TBL.near_order(rows)] == ["K", "E", "Z", "N"]


def test_near_order_ties_keep_gg_rank_and_never_mutate():
    rows = [row("B", 2, 1.0, 1.0), row("A", 1, 1.0, 1.0)]
    before = [dict(r) for r in rows]
    assert [r["symbol"] for r in TBL.near_order(rows)] == ["A", "B"]
    assert rows == before                                                   # NEGATIVE: input order untouched


def test_near_order_his_broker_names_last(monkeypatch):
    monkeypatch.setattr(GT, "broker_text_for", lambda sym, flags: "🚫" if sym in flags else None)
    rows = [row("FLAG", 1, 0.0, 0.0), row("OK", 2, 5.0, 5.0)]
    assert [r["symbol"] for r in TBL.near_order(rows, {"FLAG"})] == ["OK", "FLAG"]
    assert [r["symbol"] for r in TBL.near_order(rows, None)] == ["FLAG", "OK"]


def test_served_words_and_heads():
    keys = [k for k, _ in TBL.HEADS]
    assert keys.index("ema9") == keys.index("dist") + 1
    assert dict(TBL.HEADS)["ema9"] == "To 9 EMA"
    assert [k for k, _ in TBL.SORTS] == [TBL.SORT_GG, TBL.SORT_NEAR]
    assert "b" + "ounc" not in (TBL.NEAR_ORDER_TEXT + TBL.EMA9_TITLE).lower()


def test_golden_rows_carry_both_orders():
    import json
    from pathlib import Path
    b = json.loads(Path(__file__).parent.joinpath("fixtures/gajjala/gg5_board_2026_10_27.json").read_text())
    for mode in ("live", "shadow"):
        t = b[mode]["all_strategies"]["table"]
        ranks = [r["rank"] for r in t["rows"]]
        near = [r["near_rank"] for r in t["rows"]]
        assert ranks == list(range(1, len(ranks) + 1))                      # NEGATIVE: GG's order is untouched
        assert sorted(near) == ranks                                        # a permutation, nothing dropped
        assert t["sorts"]["default"] == TBL.SORT_GG
        want = [r["symbol"] + r["setup"] for r in TBL.near_order(t["rows"])]
        got = [r["symbol"] + r["setup"] for r in sorted(t["rows"], key=lambda r: r["near_rank"])]
        assert got == want
        for r in t["rows"]:
            if r["ema9"] is not None and r["price"] is not None:
                assert abs(r["ema9_gap_pct"] - (r["price"] - r["ema9"]) / r["ema9"] * 100) < 1e-9
