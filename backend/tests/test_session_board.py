"""Session board — ORB / FVG / SMC / mood across the two demand boards.

Ajay 2026-08-31: "a tab for ORB/ FVG/ Bullish sentiment or bearish for all the
onces in demand zone. and deep demand zones ... I will use this tab after
market open to figure out market sentiment."

The negatives carry the weight here (Rule #6). This board is read in the first
minutes of a session, when almost every input is incomplete: the opening range
has one bar, mood has few closed bars, and today's gaps do not exist yet. Every
one of those must render as "not yet", never as a confident reading.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import patterns as P            # noqa: E402
from supply_demand import session_board as SB      # noqa: E402
from supply_demand import timeframes as TF         # noqa: E402


def _minutes(n, start="2026-08-31 09:30", base=100.0, step=0.01):
    """n one-minute RTH bars stamped in NAIVE UTC, the way the loader returns
    them — a test that hands tz-aware bars would not exercise the localisation
    that actually runs."""
    idx = pd.date_range(pd.Timestamp(start) + pd.Timedelta(hours=4),
                        periods=n, freq="1min")   # 09:30 ET = 13:30 UTC
    px = [base + i * step for i in range(n)]
    return pd.DataFrame(
        {"open": px, "high": [p + 0.05 for p in px],
         "low": [p - 0.05 for p in px], "close": px,
         "volume": [10_000] * n}, index=idx)


# ── the opening range is FORMING before its window fills ───────────────────
def test_a_one_bar_opening_range_reports_itself_as_incomplete():
    """Verified live 2026-08-31 at 09:31 ET: one minute had printed and the
    payload was calling that single bar's high/low "the 15-minute opening
    range". It is real information; it is not yet the level."""
    orb = P.opening_range_from_bars(_minutes(1), 15)
    assert orb is not None
    assert orb["bars"] == 1
    assert orb["complete"] is False
    assert orb["bars_needed"] == 14


def test_a_full_window_is_complete():
    orb = P.opening_range_from_bars(_minutes(20), 15)
    assert orb["bars"] == 15 and orb["complete"] is True
    assert orb["bars_needed"] == 0


def test_an_incomplete_opening_range_does_not_move_the_ranking():
    """The state is REPORTED but must not vote. Ajay opens this tab inside the
    first quarter hour; scoring +/-10 on which side of one minute price sits
    would rank 99 names on noise exactly when he is reading it."""
    forming = {"complete": False}
    done = {"complete": True}
    base = {"mood": {"score": 0.0}, "smc": {"count": 0}, "session_gaps": [],
            "at_band": False}
    assert SB._session_score({**base, "orb": forming, "orb_state": "above"}) == 0.0
    assert SB._session_score({**base, "orb": done, "orb_state": "above"}) == SB.W_ORB_ABOVE
    assert SB._session_score({**base, "orb": done, "orb_state": "below"}) == SB.W_ORB_BELOW


def test_orb_state_is_none_rather_than_inside_when_we_cannot_tell():
    """"Could not determine" must never render as "inside the range"."""
    assert P.orb_state(None, 100.0) is None
    assert P.orb_state({"lo": 1, "hi": 2}, None) is None
    assert P.orb_state({"lo": 99.0, "hi": 101.0}, 100.0) == "inside"
    assert P.orb_state({"lo": 99.0, "hi": 101.0}, 102.0) == "above"
    assert P.orb_state({"lo": 99.0, "hi": 101.0}, 98.0) == "below"


# ── an unreadable row is kept, flagged, and sorted last ────────────────────
def test_a_row_with_no_mood_scores_none_not_zero():
    """Zero is a real neutral reading that rows legitimately have. A row we
    could not read must be distinguishable from a calm one."""
    assert SB._session_score({"mood": {"score": None}}) is None
    assert SB._session_score({"mood": {}}) is None
    assert SB._session_score({"mood": {"score": 0.0}, "smc": {"count": 0},
                              "session_gaps": [], "at_band": False,
                              "orb": None, "orb_state": None}) == 0.0


def test_bias_says_unknown_rather_than_neutral_when_mood_is_unavailable():
    """Neutral is a claim about the tape. Unknown is a claim about our data."""
    assert SB._bias({"mood": {"label": "unavailable", "score": None}}) == "unknown"
    assert SB._bias({"mood": {}}) == "unknown"
    assert SB._bias({"mood": {"label": "leaning bullish", "score": 40.0}}) == "bullish"
    assert SB._bias({"mood": {"label": "leaning bearish", "score": -40.0}}) == "bearish"
    assert SB._bias({"mood": {"label": "flat", "score": 0.0}}) == "neutral"


def test_unreadable_rows_sort_last_but_are_never_dropped(monkeypatch):
    """Dropping them would make a thin-data day look like a calm one."""
    rows = [{"symbol": "A", "session_score": None},
            {"symbol": "B", "session_score": -50.0},
            {"symbol": "C", "session_score": 30.0}]
    rows.sort(key=lambda r: (r.get("session_score") is None,
                             -(r.get("session_score") or 0)))
    assert [r["symbol"] for r in rows] == ["C", "B", "A"]


# ── session attribution ────────────────────────────────────────────────────
def test_a_gap_with_no_session_stamp_is_never_claimed_as_todays():
    """Ajay asked specifically for gaps left in the first minutes of THIS
    session. An unattributed gap presented as today's would be a fabrication."""
    assert SB._is_session_gap({"at": None}, "2026-08-31") is False
    assert SB._is_session_gap({}, "2026-08-31") is False
    assert SB._is_session_gap({"at": "2026-08-28 14:30:00"}, None) is False
    assert SB._is_session_gap({"at": "2026-08-28 14:30:00"}, "2026-08-31") is False
    assert SB._is_session_gap({"at": "2026-08-31 13:45:00"}, "2026-08-31") is True


# ── the board never invents names ──────────────────────────────────────────
def test_a_warming_source_reports_warming_rather_than_an_empty_board(monkeypatch):
    """An empty list and "the scan it reads has not finished" are different
    claims. Rendering the first as the second would say "no names qualify"
    on a day the answer is simply not computed yet."""
    from chart_maps import board as B
    monkeypatch.setattr(B, "board", lambda **kw: {"warming": True, "tiles": []})
    assert SB.board_symbols("full") == []

    out = SB.scan("full", "15m", limit=5)
    assert out["warming"] is True
    assert out["rows"] == [] and out["count"] == 0
    assert "warming" in (out.get("note") or "").lower()


def test_the_union_dedupes_and_keeps_both_sources(monkeypatch):
    from chart_maps import board as B

    def _fake(tab="vcp", **kw):
        if tab == "zones":
            return {"tiles": [
                {"symbol": "AAA", "name": "A Co",
                 "bands": [{"kind": "demand", "lo": 10.0, "hi": 11.0}]},
                {"symbol": "BBB", "name": "B Co", "bands": []},
            ]}
        return {"tiles": [
            {"symbol": "AAA", "name": "A Co",
             "bands": [{"kind": "demand", "lo": 9.0, "hi": 9.5}]},
            {"symbol": "CCC", "name": "C Co",
             "bands": [{"kind": "supply", "lo": 20.0, "hi": 21.0}]},
        ]}

    monkeypatch.setattr(B, "board", _fake)
    rows = {r["symbol"]: r for r in SB.board_symbols("full")}
    assert set(rows) == {"AAA", "BBB", "CCC"}
    assert rows["AAA"]["sources"] == ["demand", "deep"]
    # First band wins, so the row quotes the SAME numbers the zones tab drew.
    assert rows["AAA"]["band"]["lo"] == 10.0
    assert rows["BBB"]["band"] is None          # no band drawn => none claimed
    assert rows["CCC"]["band"] is None          # a SUPPLY band is not an entry


def test_read_symbol_never_raises_on_a_dead_symbol(monkeypatch):
    """A board that drops a row on one bad symbol lies about its coverage."""
    monkeypatch.setattr(TF, "intraday_raw", lambda *a, **k: None)
    monkeypatch.setattr(TF, "frame_for",
                        lambda *a, **k: (None, {"available": False,
                                                "reason": "no intraday bars",
                                                "bars": 0, "label": "15 min"}))
    out = SB.read_symbol("NOPE", None, tf="15m")
    assert out["symbol"] == "NOPE"
    assert out["bias"] == "unknown"
    assert out["session_score"] is None
    assert "no intraday bars" in out["unavailable"]


# ── one fetch per symbol ───────────────────────────────────────────────────
def test_frame_for_uses_handed_in_bars_instead_of_fetching_again(monkeypatch):
    """Fetching twice per symbol doubled today's live requests and drew Massive
    read timeouts at 10 workers on 2026-08-31."""
    calls = []

    def _boom(*a, **k):
        calls.append(a)
        raise AssertionError("frame_for re-fetched despite being handed raw bars")

    monkeypatch.setattr(TF, "intraday_raw", _boom)
    df, meta = TF.frame_for("X", "15m", raw=_minutes(400))
    assert not calls
    assert meta["available"] is True and meta["bars"] > 0


# ── the 2026-08-29 course-correction still holds ───────────────────────────
def test_this_board_did_not_reopen_the_no_timeframe_on_scans_decision():
    """Ajay 2026-08-29: "I do not need these on scans but on demand in the
    support levels". That lock is about bolting a timeframe knob onto the
    DAILY boards. This is a separate surface with its own intraday contract,
    and the daily boards must still be untouched."""
    import inspect

    from chart_maps import board as B
    assert "tf" not in inspect.signature(B.board).parameters
    assert "_timeframe_decor" not in inspect.getsource(B.board)


def test_the_ranking_is_labelled_convention_and_never_claims_a_citation():
    assert SB.CITED is False
    weights = (SB.W_MOOD, SB.W_SMC_SETUP, SB.W_ORB_ABOVE, SB.W_ORB_BELOW,
               SB.W_FVG_SESSION, SB.W_AT_BAND)
    assert all(isinstance(w, float) for w in weights)
    # A sum of NAMED parts: every point on a row is traceable to one fact.
    row = {"mood": {"score": 10.0}, "smc": {"count": 1}, "session_gaps": [{}],
           "at_band": True, "orb": {"complete": True}, "orb_state": "above"}
    assert SB._session_score(row) == round(
        10.0 + SB.W_SMC_SETUP + SB.W_FVG_SESSION + SB.W_AT_BAND + SB.W_ORB_ABOVE, 1)


def test_out_of_session_the_board_labels_the_session_it_is_showing():
    """A weekend read is legitimate — it shows the last session — but it must
    never imply it is today's."""
    assert isinstance(SB._is_rth_now(), bool)
    p = SB.progress_for("full", "15m")
    assert p["phase"] in ("idle", "reading", "warming_source", "error")
    assert p["tf"] == "15m"
