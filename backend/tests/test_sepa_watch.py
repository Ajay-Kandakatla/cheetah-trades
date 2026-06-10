"""Tests for the SEPA-cross tape watch — candle anatomy, level classification,
alert dedup (mark-before-send), and outcome grading. Synthetic, no network.
"""
import numpy as np
import pandas as pd
import pytest

from scalping import candles, sepa_watch


# ── anatomy arithmetic ───────────────────────────────────────────────────────
def test_anatomy_strong_up_bar():
    a = candles.anatomy(o=100.0, h=101.0, l=99.9, c=100.95)
    assert a["dir"] == "up" and a["is_strong"]
    assert a["clv"] > 0.8                      # closed near the high
    assert not a["is_doji"]


def test_anatomy_shooting_star_upper_wick_dominant():
    # long upper wick, small body near the low of the bar
    a = candles.anatomy(o=100.0, h=102.0, l=99.9, c=100.1)
    assert a["upper_wick_dominant"]
    assert a["clv"] < 0                        # closed in the lower half


def test_anatomy_doji():
    a = candles.anatomy(o=100.0, h=100.5, l=99.5, c=100.02)
    assert a["is_doji"]


def test_anatomy_degenerate_bar_none():
    assert candles.anatomy(100, 100, 100, 100) is None


# ── 5-min aggregation ────────────────────────────────────────────────────────
def _frame_1m(closes, start="2026-06-09 13:30"):
    idx = pd.date_range(start, periods=len(closes), freq="1min")
    c = np.asarray(closes, float)
    return pd.DataFrame({"open": np.r_[c[0], c[:-1]], "high": c + 0.05,
                         "low": c - 0.05, "close": c,
                         "volume": np.full(len(c), 10_000.0), "session": "rth"}, index=idx)


def test_aggregate_5min_drops_partial_bar():
    df = _frame_1m(np.linspace(100, 101, 13))   # 13 mins → 2 complete bars + partial
    df5 = candles.aggregate_5min(df)
    assert len(df5) == 2
    assert df5.iloc[0]["volume"] == 50_000.0


# ── classification at levels ─────────────────────────────────────────────────
def _df5(rows):
    """rows: list of (o,h,l,c,v). 5-min spaced index."""
    idx = pd.date_range("2026-06-09 14:00", periods=len(rows), freq="5min")
    return pd.DataFrame([{"open": o, "high": h, "low": l, "close": c, "volume": v}
                         for (o, h, l, c, v) in rows], index=idx)


def test_classify_breakout_strong_at_pivot():
    df5 = _df5([(99.0, 99.6, 98.9, 99.5, 10_000),
                (99.5, 101.2, 99.45, 101.1, 30_000)])   # strong body through 100
    read = candles.classify(df5, {"pivot": 100.0, "vwap": 99.0, "or_high": 99.6, "day_high": 99.6}, 10_000)
    assert read and read["state"] == "BREAKOUT_STRONG"
    assert read["verdict"] == "constructive" and read["severity"] == "alert"


def test_classify_rejection_wick_at_pivot():
    # pokes above 100, long upper wick, closes back under
    df5 = _df5([(99.0, 99.6, 98.9, 99.5, 10_000),
                (99.5, 100.8, 99.4, 99.55, 22_000)])
    read = candles.classify(df5, {"pivot": 100.0, "vwap": 99.0, "or_high": None, "day_high": None}, 10_000)
    assert read and read["state"] == "REJECTION"
    assert read["verdict"] == "deteriorating"


def test_classify_breakout_weak_without_volume():
    df5 = _df5([(99.0, 99.6, 98.9, 99.5, 10_000),
                (99.5, 100.4, 99.45, 100.3, 8_000)])    # crossed but 0.8× volume
    read = candles.classify(df5, {"pivot": 100.0, "vwap": 99.0, "or_high": None, "day_high": None}, 10_000)
    assert read and read["state"] == "BREAKOUT_WEAK" and read["severity"] == "info"


def test_classify_breakdown_loses_vwap():
    df5 = _df5([(100.5, 100.6, 100.2, 100.4, 10_000),
                (100.4, 100.45, 99.3, 99.4, 25_000)])   # strong red through vwap 100
    read = candles.classify(df5, {"pivot": None, "vwap": 100.0, "or_high": None, "day_high": None}, 10_000)
    assert read and read["state"] == "BREAKDOWN" and read["verdict"] == "deteriorating"


def test_classify_reclaim_vwap():
    df5 = _df5([(99.4, 99.6, 99.2, 99.5, 10_000),
                (99.5, 100.6, 99.45, 100.55, 18_000)])  # strong green through vwap 100
    read = candles.classify(df5, {"pivot": None, "vwap": 100.0, "or_high": None, "day_high": None}, 10_000)
    assert read and read["state"] == "RECLAIM" and read["verdict"] == "constructive"


def test_classify_none_when_nothing_at_levels():
    df5 = _df5([(99.0, 99.2, 98.8, 99.1, 10_000),
                (99.1, 99.3, 98.9, 99.0, 9_000)])
    read = candles.classify(df5, {"pivot": 105.0, "vwap": 99.05, "or_high": 104.0, "day_high": 104.0}, 10_000)
    assert read is None or read["severity"] == "info"


# ── daily-pattern trigger lines as levels (the daily↔intraday join) ──────────
def test_classify_breakout_at_pattern_line():
    """A forming pattern's confirmation line is watched like a pivot — and the
    read carries the close-discipline caveat (confirms only at the CLOSE)."""
    df5 = _df5([(99.0, 99.6, 98.9, 99.5, 10_000),
                (99.5, 101.2, 99.45, 101.1, 30_000)])
    read = candles.classify(df5, {"pivot": None, "pattern_line": 100.0,
                                  "pattern_name": "cup-handle line",
                                  "vwap": 99.0, "or_high": None, "day_high": None}, 10_000)
    assert read and read["state"] == "BREAKOUT_STRONG"
    joined = " ".join(read["reasons"])
    assert "cup-handle line" in joined
    assert "CLOSES above the line" in joined


def test_classify_pivot_beats_pattern_line():
    df5 = _df5([(99.0, 99.6, 98.9, 99.5, 10_000),
                (99.5, 101.2, 99.45, 101.1, 30_000)])
    read = candles.classify(df5, {"pivot": 100.0, "pattern_line": 100.4,
                                  "pattern_name": "W line",
                                  "vwap": 99.0, "or_high": None, "day_high": None}, 10_000)
    assert read and read["state"] == "BREAKOUT_STRONG"
    assert "pivot" in read["reasons"][0]
    assert "CLOSES above the line" not in " ".join(read["reasons"])


def test_lines_from_doc_forming_only_and_freshness():
    import time as _t
    now = int(_t.time())
    doc = {"generated_at": now, "verdicts": [
        {"symbol": "psx", "matches": [
            {"pattern": "cup_with_handle", "status": "forming", "neckline": 132.45}]},
        {"symbol": "CNC", "matches": [
            {"pattern": "double_bottom", "status": "confirmed", "neckline": 66.03}]},
        {"symbol": "XYZ", "matches": []},
    ]}
    lines = sepa_watch._lines_from_doc(doc)
    assert lines == {"PSX": {"line": 132.45, "label": "cup-handle line"}}
    # stale doc (>24h) yields nothing — in-the-moment only
    assert sepa_watch._lines_from_doc({**doc, "generated_at": now - 25 * 3600}) == {}


# ── on-demand single-symbol tape read (Day Trading / Scalping strip) ─────────
def test_tape_read_assembles_levels(monkeypatch):
    captured = {}

    def fake_read(entry):
        captured.update(entry)
        return {"symbol": entry["symbol"], "read": None, "levels": {}, "last_price": 1.0,
                "tags": entry["tags"], "pivot": entry.get("pivot"), "bar_ts": "t",
                "vs_pivot_pct": None, "vs_vwap_pct": None}
    monkeypatch.setattr(sepa_watch, "_read_symbol", fake_read)
    monkeypatch.setattr(sepa_watch, "_pattern_lines",
                        lambda: {"PSX": {"line": 132.45, "label": "cup-handle line"}})
    from sepa import scanner
    monkeypatch.setattr(scanner, "load_latest", lambda: {"all_results": [
        {"symbol": "PSX", "entry_setup": {"pivot": 131.2}}]})

    out = sepa_watch.tape_read("psx")
    assert out["ok"] is True
    assert captured["pivot"] == 131.2
    assert captured["pattern_line"] == 132.45
    assert captured["pattern_label"] == "cup-handle line"


def test_tape_read_no_data(monkeypatch):
    monkeypatch.setattr(sepa_watch, "_read_symbol", lambda e: None)
    monkeypatch.setattr(sepa_watch, "_pattern_lines", lambda: {})
    out = sepa_watch.tape_read("ZZZZ")
    assert out["ok"] is False and "note" in out


# ── alert dedup: mark BEFORE send ────────────────────────────────────────────
def test_fire_alert_dedups_even_when_send_fails(monkeypatch):
    sepa_watch._mem.clear()
    sent = {"n": 0}

    def _send(**k):
        sent["n"] += 1
        return False                              # delivery fails
    from sepa import notify
    monkeypatch.setattr(notify, "send_alert", _send)

    row = {"last_price": 101.1, "bar_ts": "2026-06-09T14:05:00"}
    read = {"state": "BREAKOUT_STRONG", "verdict": "constructive",
            "severity": "alert", "reasons": ["r1", "r2"], "metrics": {}}
    a1 = sepa_watch._fire_alert("AAA", row, read, None, "2026-06-09")
    a2 = sepa_watch._fire_alert("AAA", row, read, None, "2026-06-09")
    assert a1 is not None and a2 is None          # second tick deduped
    assert sent["n"] == 1                         # attempted exactly once
    sepa_watch._mem.clear()


# ── outcome grading semantics ────────────────────────────────────────────────
@pytest.mark.parametrize("verdict,fwd,expected", [
    ("constructive", 0.5, "hit"), ("constructive", -0.5, "miss"),
    ("deteriorating", -0.5, "hit"), ("deteriorating", 0.5, "miss"),
])
def test_grading_semantics(verdict, fwd, expected):
    graded = ("hit" if fwd > 0 else "miss") if verdict == "constructive" \
        else ("hit" if fwd < 0 else "miss")
    assert graded == expected
