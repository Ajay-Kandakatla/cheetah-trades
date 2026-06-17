"""Breakout BOARD — the dedicated /breakouts page feed (Ajay 2026-06-16: "a page
to track only breakouts and # of breakouts, highest first ... passing Minervinis
and not, and Bonde, but mainly around breakouts").

Locks: ranks by breakout COUNT descending, carries the Minervini+Bonde
buy_verdict per row, summarizes the pass/fail mix, honours min_count, and the
negatives (empty scan → empty board, never a crash).

Run in the backend venv:
  cd backend && .venv/bin/python -m pytest tests/test_breakout_board.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import breakout


def _row(symbol, count, *, today=False, m_pass=False, b_pass=None, rs=50):
    """A scan row with a breakout count + a pre-baked buy_verdict (we test the
    BOARD's ranking/summary, not the verdict logic — that has its own tests)."""
    verdict = {
        "status": "pass" if m_pass else "fail",
        "both_pass": bool(m_pass and b_pass is True),
        "minervini": {"passed": m_pass},
        "bonde": {"passed": b_pass},
    }
    return {
        "symbol": symbol,
        "name": f"{symbol} Inc",
        "rs_rank": rs,
        "last_close": 100.0,
        "day_change_pct": 1.0,
        "stage": {"stage": 2, "label": "Stage 2"},
        "is_etf": False,
        "volume": {
            "breakout_count": count,
            "breakout_window_bars": 252,
            "last_vol": 2_000_000,
            "avg_vol_50": 1_000_000,
            "days_since_breakout": 0 if today else 5,
            "high_vol_breakout": today,
        },
        "buy_verdict": verdict,
    }


def _patch_scan(monkeypatch, rows):
    from sepa import scanner
    monkeypatch.setattr(scanner, "load_latest", lambda: {"all_results": rows, "generated_at": 123})


def test_ranks_by_breakout_count_descending(monkeypatch):
    _patch_scan(monkeypatch, [
        _row("AAA", 2), _row("BBB", 9), _row("CCC", 5),
    ])
    out = breakout.board()
    syms = [r["symbol"] for r in out["rows"]]
    assert syms == ["BBB", "CCC", "AAA"]            # highest count first
    assert out["rows"][0]["breakout_count"] == 9


def test_carries_verdict_and_broke_out_today(monkeypatch):
    _patch_scan(monkeypatch, [_row("AAA", 4, today=True, m_pass=True, b_pass=True)])
    out = breakout.board()
    r = out["rows"][0]
    assert r["broke_out_today"] is True
    assert r["buy_verdict"]["both_pass"] is True
    assert r["buy_verdict"]["minervini"]["passed"] is True


def test_summary_counts_the_pass_fail_mix(monkeypatch):
    _patch_scan(monkeypatch, [
        _row("AAA", 8, today=True, m_pass=True,  b_pass=True),    # both pass
        _row("BBB", 6, m_pass=True,  b_pass=False),               # M pass, B fail
        _row("CCC", 4, m_pass=False, b_pass=True),                # M fail, B pass
        _row("DDD", 2, m_pass=False, b_pass=None),                # M fail, B pending
    ])
    s = breakout.board()["summary"]
    assert s["total"] == 4
    assert s["broke_out_today"] == 1
    assert s["both_pass"] == 1
    assert s["minervini_pass"] == 2 and s["minervini_fail"] == 2
    assert s["bonde_pass"] == 2 and s["bonde_fail"] == 1          # pending is NOT a fail


def test_min_count_filters_out_low_breakout_names(monkeypatch):
    _patch_scan(monkeypatch, [_row("AAA", 1), _row("BBB", 0), _row("CCC", 3)])
    # default min_count=1 drops the zero-breakout name
    syms = [r["symbol"] for r in breakout.board()["rows"]]
    assert "BBB" not in syms and set(syms) == {"AAA", "CCC"}
    # min_count=3 keeps only CCC
    assert [r["symbol"] for r in breakout.board(min_count=3)["rows"]] == ["CCC"]


def test_top_caps_returned_rows(monkeypatch):
    _patch_scan(monkeypatch, [_row(f"S{i}", i + 1) for i in range(10)])
    out = breakout.board(top=3)
    assert len(out["rows"]) == 3
    assert out["summary"]["total"] == 3                          # summary reflects what's shown


def test_empty_scan_is_empty_board_not_a_crash(monkeypatch):
    _patch_scan(monkeypatch, [])
    out = breakout.board()
    assert out["rows"] == [] and out["summary"]["total"] == 0


def test_row_without_breakout_count_is_skipped(monkeypatch):
    _patch_scan(monkeypatch, [
        {"symbol": "NOVOL", "volume": None},                     # no volume block
        {"symbol": "NOCNT", "volume": {"last_vol": 5}},          # volume but no count
        _row("GOOD", 3),
    ])
    assert [r["symbol"] for r in breakout.board()["rows"]] == ["GOOD"]
