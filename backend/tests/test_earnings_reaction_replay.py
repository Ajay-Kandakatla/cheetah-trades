"""📣 earnings_reaction replay — a phone-load COUNT, not an edge claim.

    .venv/bin/python -m pytest tests/test_earnings_reaction_replay.py -q

Everything here runs on synthetic frames. The replay's job is to tell Ajay how
many pushes a trading day would carry before he is asked to live with the kind
(§7.1) and what a surprise floor would do to that count (§7.2) — so the tests
pin the CLASSIFIER and the per-session arithmetic, and pin that neither
retypes a gate threshold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import earnings as E                        # noqa: E402
from growth import alerts as GA                             # noqa: E402
from scripts import earnings_reaction_replay as R           # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SESSIONS = ["2026-09-16", "2026-09-17", "2026-09-18"]


def _frame(end="2026-09-18", n=200, bump=None) -> pd.DataFrame:
    idx = pd.bdate_range(end=end, periods=n)
    df = pd.DataFrame({"open": [99.0] * n, "high": [101.0] * n, "low": [98.0] * n,
                       "close": [100.0] * n, "volume": [1_000_000.0] * n}, index=idx)
    if bump:
        for k, v in bump.items():
            df.iloc[-1, df.columns.get_loc(k)] = v
    return df


def _institutional_frame(end="2026-09-18"):
    """5x volume, close near the high, $640M, up on the day."""
    return _frame(end=end, bump={"open": 99.0, "high": 130.0, "low": 98.0,
                                 "close": 128.0, "volume": 5_000_000.0})


def _collapse_frame(end="2026-09-18"):
    """VIK's shape: the same participation, every bit of it selling."""
    return _frame(end=end, bump={"open": 99.0, "high": 130.0, "low": 98.0,
                                 "close": 98.2, "volume": 5_000_000.0})


def _bar(df):
    return E.bar_metrics(df, len(df) - 1)


# ── the classifier ──────────────────────────────────────────────────────────
def test_institutional_buying_on_a_beat_is_the_would_push_cell():
    assert R.classify(_bar(_institutional_frame()), 6.16) == R.WOULD_PUSH
    assert R.WOULD_PUSH == "institutional_and_beat"


def test_institutional_buying_on_a_MISS_is_counted_but_never_pushed():
    """TGT-style "bought the gap down" is EXCLUDED by the beat rule; the
    replay reports how often, so widening it is a decision with a number
    beside it (§7.7) rather than a guess."""
    assert R.classify(_bar(_institutional_frame()), -12.0) == "institutional_and_miss"
    assert R.classify(_bar(_institutional_frame()), 0.0) == "institutional_and_miss"


def test_a_null_surprise_with_institutional_buying_is_its_own_cell():
    assert R.classify(_bar(_institutional_frame()), None) == "institutional_null_surprise"
    assert R.classify(_bar(_institutional_frame()), float("nan")) == "institutional_null_surprise"


def test_a_beat_that_institutions_SOLD_is_not_a_push():
    assert R.classify(_bar(_collapse_frame()), 6.16) == "beat_not_institutional"


def test_neither_is_neither():
    assert R.classify(_bar(_collapse_frame()), -3.0) == "neither"
    assert R.classify(None, 6.16) == "beat_not_institutional"


# ── per-session load and the singles / digest split ─────────────────────────
def _ev(sym, date, cell=R.WOULD_PUSH, s=6.0):
    return {"symbol": sym, "reaction_date": date, "cell": cell, "surprise_pct": s}


def test_the_singles_digest_split_uses_the_passs_OWN_constant():
    n = GA.MAX_INDIVIDUAL + 3
    events = [_ev("S%d" % i, "2026-09-18") for i in range(n)]
    ps = R.per_session(events, SESSIONS)
    assert ps["2026-09-18"]["pushes"] == n
    assert ps["2026-09-18"]["singles"] == GA.MAX_INDIVIDUAL
    assert ps["2026-09-18"]["digest"] == 3
    assert ps["2026-09-16"] == {"pushes": 0, "names": [], "singles": 0, "digest": 0}


def test_only_would_push_events_count_toward_the_phone_load():
    events = [_ev("A", "2026-09-18"),
              _ev("B", "2026-09-18", cell="institutional_and_miss"),
              _ev("C", "2026-09-18", cell="beat_not_institutional")]
    assert R.per_session(events, SESSIONS)["2026-09-18"]["names"] == ["A"]


def test_an_event_outside_the_session_window_is_not_counted():
    assert R.per_session([_ev("A", "2026-05-01")], SESSIONS)["2026-09-18"]["pushes"] == 0


def test_the_summary_names_the_busiest_day():
    events = [_ev("A", "2026-09-17"), _ev("B", "2026-09-18"), _ev("C", "2026-09-18")]
    s = R.summarize(R.per_session(events, SESSIONS))
    assert s["total"] == 3 and s["max"] == 2 and s["sessions_with_any"] == 2
    assert s["busiest"] == {"date": "2026-09-18", "n": 2, "names": ["B", "C"]}


def test_the_floors_table_is_monotone_non_increasing():
    """REPORT ONLY (§7.2). A floor is a new numeric threshold — his call."""
    events = [_ev("A", "2026-09-18", s=1.0), _ev("B", "2026-09-18", s=6.0),
              _ev("C", "2026-09-17", s=30.0), _ev("D", "2026-09-16", s=80.0)]
    tbl = R.floors_table(events, SESSIONS)
    assert list(tbl) == [str(f) for f in R.FLOORS]
    totals = [tbl[str(f)]["total"] for f in R.FLOORS]
    assert totals == sorted(totals, reverse=True)
    assert tbl["0"]["total"] == 4 and tbl["50"]["total"] == 1


# ── both anchorings (critique F6) ───────────────────────────────────────────
def _doc(sym, date, lr_when, doc_when, surprise=6.16):
    return {"_id": sym, "when": doc_when, "next_date": "2026-12-17",
            "last_report": {"date": date, "when": lr_when, "surprise_pct": surprise,
                            "eps_actual": 1.05, "eps_estimate": 0.99}}


def test_the_two_anchorings_score_DIFFERENT_bars_and_both_are_reported():
    """The live pass anchors on `last_report.when`; the doc's own `when` was
    None for 1,646 of 2,071 names after the 2026-09-18 refresh and anchors
    like BMO. A count taken off the doc anchoring is not a description of the
    cron, so the JSON reports both and names the live one."""
    frames = {"AAA": _institutional_frame(end="2026-09-18")}
    docs = [_doc("AAA", "2026-09-17", "AMC", None)]
    live, _ = R.build_events(docs, SESSIONS, "last_report", load=frames.get)
    doc_side, _ = R.build_events(docs, SESSIONS, "doc", load=frames.get)
    assert live[0]["reaction_date"] == "2026-09-18"       # AMC → the next session
    assert doc_side[0]["reaction_date"] == "2026-09-17"   # None → anchored like BMO
    assert live[0]["cell"] == R.WOULD_PUSH


def test_the_replay_reports_both_anchorings_and_names_the_live_one():
    frames = {"AAA": _institutional_frame()}
    out = R.replay(docs=[_doc("AAA", "2026-09-17", "AMC", None)], sessions=SESSIONS,
                   load=frames.get)
    assert set(out["anchorings"]) == {"last_report", "doc"}
    assert out["live_anchoring"] == "last_report"
    for anchor in ("last_report", "doc"):
        blob = out["anchorings"][anchor]
        assert set(blob) == {"cells", "per_session", "summary", "floors",
                             "institutional_misses", "coverage"}
    assert out["summary"] == out["anchorings"]["last_report"]["summary"]
    assert out["per_session"] == out["anchorings"]["last_report"]["per_session"]
    assert any("COUNT, not an edge claim" in c for c in out["caveats"])
    json.dumps(out, default=str)


def test_a_name_with_no_frame_is_counted_not_silently_dropped():
    docs = [_doc("GONE", "2026-09-17", "AMC", "AMC")]
    events, cov = R.build_events(docs, SESSIONS, "last_report", load=lambda s: None)
    assert events == [] and cov["short_frame"] == 1
    assert cov["calendar_docs"] == 1 and cov["with_last_report_in_window"] == 1


def test_a_report_whose_reaction_bar_has_not_traded_yet_is_counted():
    frames = {"AAA": _institutional_frame(end="2026-09-18")}
    docs = [_doc("AAA", "2026-09-18", "AMC", "AMC")]      # AMC on the last bar
    events, cov = R.build_events(docs, SESSIONS, "last_report", load=frames.get)
    assert events == [] and cov["no_reaction_bar"] == 1


def test_cells_totals_add_up():
    events = [_ev("A", "2026-09-18"), _ev("B", "2026-09-18", cell="institutional_and_miss")]
    c = R.cells(events)
    assert c["reacted_total"] == 2 and c[R.WOULD_PUSH] == 1
    assert sum(c[k] for k in R.LABELS) == 2


# ── the shipped artefacts ───────────────────────────────────────────────────
def test_the_script_never_retypes_a_gate_threshold():
    """SOURCE GUARD: it IMPORTS `is_institutional_buy` and `bar_metrics`, so a
    change to the tab's constants moves the replay with it."""
    src = (ROOT / "backend/scripts/earnings_reaction_replay.py").read_text()
    assert "from chart_maps.earnings import bar_metrics, is_institutional_buy" in src
    for literal in ("1.5", "0.60", "50_000_000", "MIN_VOL_RATIO ="):
        assert literal not in src, literal
    assert "from growth.alerts import MAX_INDIVIDUAL" in src


def test_the_committed_JSON_parses_and_carries_the_schema_and_the_caveats():
    """The main session runs the replay in-container and replaces this file;
    until then it is an explicit placeholder, never a fabricated number."""
    blob = json.loads((ROOT / "backend/scripts/earnings_reaction_measured.json").read_text())
    for key in ("as_of", "sessions", "per_session", "summary", "floors",
                "institutional_misses", "coverage", "caveats", "anchorings",
                "live_anchoring"):
        assert key in blob, key
    assert blob["caveats"], "a count with no caveats is a claim"
    assert any("not an edge claim" in c for c in blob["caveats"])
    if blob.get("pending"):
        assert blob["summary"] == {} and blob["sessions"] == []
        assert any("PLACEHOLDER" in c for c in blob["caveats"])
    else:
        assert blob["summary"].get("total") is not None and blob["sessions"]


def test_the_replay_refuses_to_pretend_it_measured_an_edge():
    src = (ROOT / "backend/scripts/earnings_reaction_replay.py").read_text()
    assert "not an edge claim" in src
    assert "NOT MEASURED" in " ".join(R.CAVEATS)
    with pytest.raises(AttributeError):
        _ = R.expectancy            # there is no return measurement here, by design
