"""ⓘ Quality explainer (Ajay 2026-09-28: "can you help with info icon on the
quality?") — `sepa/earnings_quality_info.py`.

The explainer must say EXACTLY what `earnings_quality.compute()` does. The
point weights / penalties / steady cut / 5-quarter minimum are inline literals
in `compute()`, mirrored in the describer — each mirror is pinned here to the
score DELTA `compute()` actually produces for that component alone, so a
changed literal turns this file red instead of leaving the ⓘ wrong.

Series: 8 quarters newest-first `[b(1+g0), b(1+g1), b(1+g2), b, b, b, b, b]`
so `_yoy(i) == g_i`; net income = margin_i × revenue_i. `sales.compute` is
monkeypatched to a fixed `{"score": S, "accelerating": A}` to isolate.
"""
from __future__ import annotations

import ast
import inspect
import os
import re
from datetime import datetime, timezone

import pytest

from sepa import earnings_quality as EQ
from sepa import earnings_quality_info as EQI

BASE_REV = 100.0
BASE_EPS = 2.0


def _series(g, base):
    g0, g1, g2 = g
    return [base * (1 + g0 / 100.0), base * (1 + g1 / 100.0), base * (1 + g2 / 100.0),
            base, base, base, base, base]


def _score(monkeypatch, *, eps=(0, 0, 0), rev=(10, 10, 10), margins=None,
           inv=None, recv=None, surprise=None, S=0, A=False, full=False):
    monkeypatch.setattr(EQ.sales, "compute",
                        lambda *a, **k: {"score": S, "accelerating": A})
    r = _series(rev, BASE_REV)
    e = _series(eps, BASE_EPS)
    m = margins or [0.10] * 8
    ni = [r[i] * m[i] for i in range(8)]
    out = EQ.compute(e, r, ni, inv, recv, surprise_pct=surprise)
    return out if full else out["score"]


def _inv(pct):
    return [100.0 * (1 + pct / 100.0)] + [100.0] * 7


# ── every point weight == the delta compute() produces ──────────────────────
def test_eps_level_points(monkeypatch):
    lo = _score(monkeypatch, eps=(0, 0, 0))
    top = EQ.STRONG_EPS_YOY_PCT
    hi = _score(monkeypatch, eps=(top, top, top))
    half = _score(monkeypatch, eps=(top / 2, top / 2, top / 2))
    assert hi - lo == EQI.PTS["eps_level"]
    assert half - lo == EQI.PTS["eps_level"] / 2


def test_sales_points(monkeypatch):
    assert (_score(monkeypatch, S=100) - _score(monkeypatch, S=0)) == EQI.PTS["sales"]


def test_margin_points(monkeypatch):
    exp = [0.12, 0.12, 0.12, 0.10, 0.10, 0.10, 0.10, 0.10]
    con = [0.08, 0.08, 0.08, 0.10, 0.10, 0.10, 0.10, 0.10]
    flat = [0.10] * 8
    e = _score(monkeypatch, margins=exp)
    c = _score(monkeypatch, margins=con)
    f = _score(monkeypatch, margins=flat)
    assert e - c == EQI.PTS["margin"]
    assert f - c == EQI.MARGIN_FLAT_PTS


def test_eps_accel_points(monkeypatch):
    none = _score(monkeypatch, eps=(40, 40, 40))
    three = _score(monkeypatch, eps=(40, 30, 26))
    two = _score(monkeypatch, eps=(40, 30, 30))
    assert three - none == EQI.PTS["eps_accel"]
    assert two - none == EQI.EPS_ACCEL_2Q_PTS


def test_sales_accel_points(monkeypatch):
    none = _score(monkeypatch, rev=(10, 10, 10))
    three = _score(monkeypatch, rev=(30, 20, 10))
    flagged = _score(monkeypatch, rev=(10, 10, 10), A=True)
    assert three - none == EQI.PTS["sales_accel"]
    assert flagged - none == EQI.SALES_ACCEL_PTS


def test_margin_accel_points(monkeypatch):
    rising = [0.13, 0.12, 0.11, 0.10, 0.13, 0.13, 0.13, 0.13]
    flat = [0.13] * 8
    assert (_score(monkeypatch, margins=rising)
            - _score(monkeypatch, margins=flat)) == EQI.PTS["margin_accel"]


def test_surprise_points(monkeypatch):
    base = _score(monkeypatch)
    assert _score(monkeypatch, surprise=50) - base == EQI.PTS["surprise"]
    assert _score(monkeypatch, surprise=3) - base == 3


# ── every penalty == the delta compute() produces ───────────────────────────
def test_low_quality_beat_penalty(monkeypatch):
    clean = _score(monkeypatch, eps=(30, 30, 30), rev=(6, 6, 6), full=True)
    beat = _score(monkeypatch, eps=(30, 30, 30), rev=(2, 2, 2), full=True)
    assert beat["red_flags"]["low_quality_beat"] is True
    assert clean["red_flags"]["low_quality_beat"] is False
    assert clean["score"] - beat["score"] == EQI.PENALTY["low_quality_beat"]


def test_inventory_and_double_trouble_penalties(monkeypatch):
    # S=100 lifts the base clear of the 0 clamp so the whole penalty shows
    clean = _score(monkeypatch, rev=(10, 10, 10), S=100)
    inv = _score(monkeypatch, rev=(10, 10, 10), S=100, inv=_inv(40), full=True)
    both = _score(monkeypatch, rev=(10, 10, 10), S=100, inv=_inv(40), recv=_inv(40),
                  full=True)
    assert inv["red_flags"]["inventory_vs_sales"] is True
    assert both["red_flags"]["double_trouble"] is True
    assert clean - inv["score"] == EQI.PENALTY["inventory"]
    assert clean - both["score"] == EQI.PENALTY["double_trouble"]


# ── steady cut, the 5-quarter minimum, tier priority ────────────────────────
def test_steady_min_score(monkeypatch):
    exp = [0.12, 0.12, 0.12, 0.10, 0.10, 0.10, 0.10, 0.10]
    top = EQ.STRONG_EPS_YOY_PCT
    at = _score(monkeypatch, eps=(top, top, top), margins=exp, S=100, full=True)
    below = _score(monkeypatch, eps=(top, top, top), margins=exp, S=95, full=True)
    assert at["score"] == EQI.STEADY_MIN_SCORE and at["tier"] == "steady"
    assert below["score"] == EQI.STEADY_MIN_SCORE - 1 and below["tier"] == "weak"


def test_min_quarters():
    n = EQI.MIN_QUARTERS
    short = EQ.compute([2.0] * (n - 1), [100.0] * (n - 1), [10.0] * (n - 1))
    ok = EQ.compute([2.0] * n, [100.0] * n, [10.0] * n)
    assert short["score"] is None and short["tier"] == "unknown"
    assert ok["score"] is not None


def test_tier_priority_code33_beats_the_inventory_flag(monkeypatch):
    rising = [0.20, 0.18, 0.16, 0.15, 0.12, 0.12, 0.12, 0.12]
    out = _score(monkeypatch, eps=(60, 40, 20), rev=(20, 15, 10), margins=rising,
                 inv=_inv(40), full=True)
    assert out["red_flags"]["inventory_vs_sales"] is True
    assert out["code_33"] is True and out["tier"] == "code33"


def test_tiers_order_and_every_key_is_a_tier_compute_returns():
    info = EQI.describe()
    keys = [t["key"] for t in info["tiers"]]
    assert keys == ["code33", "red_flag", "accelerating", "steady", "weak", "unknown"]
    assert keys == list(EQI.TIER_ORDER)
    src = inspect.getsource(EQ.compute)
    for k in keys:
        assert f'"{k}"' in src, k


# ── the text is BUILT from the engine's constants ───────────────────────────
def _eps_rule(info):
    return next(p for p in info["points"] if p["key"] == "eps_level")["rule"]


def test_text_follows_a_patched_constant(monkeypatch):
    monkeypatch.setattr(EQ, "STRONG_EPS_YOY_PCT", 30.0)
    assert "+30%" in _eps_rule(EQI.describe())


def test_NEGATIVE_unpatched_text_never_says_30():
    assert "+30%" not in _eps_rule(EQI.describe())
    assert f"+{EQ.STRONG_EPS_YOY_PCT:g}%" in _eps_rule(EQI.describe())


def test_served_points_and_penalties_are_the_mirrors():
    info = EQI.describe()
    assert [p["key"] for p in info["points"]] == list(EQI.PTS)
    assert all(p["max"] == EQI.PTS[p["key"]] for p in info["points"])
    assert {p["key"]: p["points"] for p in info["penalties"]} == EQI.PENALTY


# ── freshness TTL (critic #5) ───────────────────────────────────────────────
_AS_OF = {"oldest": "2026-09-14", "newest": "2026-09-27", "n": 3}


def test_ttl_text_16_days():
    info = EQI.describe(fundamentals_as_of=_AS_OF, max_age_sec=16 * 86400)
    assert any("16 days" in b for b in info["blank"])
    assert "16 days" in info["fundamentals_as_of"]["note"]


def test_ttl_text_3_days():
    info = EQI.describe(fundamentals_as_of=_AS_OF, max_age_sec=3 * 86400)
    assert any("3 days" in b for b in info["blank"])
    assert "3 days" in info["fundamentals_as_of"]["note"]


def test_NEGATIVE_no_ttl_drops_the_number():
    info = EQI.describe(fundamentals_as_of=_AS_OF, max_age_sec=None)
    assert any("too old for the board to use" in b for b in info["blank"])
    assert "days" not in " ".join(info["blank"])
    assert "days" not in info["fundamentals_as_of"]["note"]
    for junk in (0, -5, "x"):
        assert "days" not in " ".join(EQI.describe(max_age_sec=junk)["blank"])


def test_NEGATIVE_no_as_of_is_None():
    assert EQI.describe()["fundamentals_as_of"] is None
    assert EQI.describe(fundamentals_as_of={})["fundamentals_as_of"] is None


def _strings(x, path=""):
    if isinstance(x, str):
        yield path, x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from _strings(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _strings(v, f"{path}[{i}]")


def _all_infos():
    return [EQI.describe(), EQI.describe(fundamentals_as_of=_AS_OF, max_age_sec=16 * 86400),
            EQI.describe(fundamentals_as_of=_AS_OF, max_age_sec=None)]


def test_NEGATIVE_no_served_string_says_week():
    for info in _all_infos():
        for p, s in _strings(info):
            assert not re.search(r"\bweek", s, re.I), (p, s)


# ── ceiling + the surprise source guard ─────────────────────────────────────
def test_ceiling_today_is_90():
    assert EQI.ceiling_today() == 90
    assert "90" in EQI.describe()["ceiling_note"]


def test_NEGATIVE_surprise_is_not_wired_in_canslim():
    """While SURPRISE_WIRED is False, no `earnings_quality.compute(` call in
    canslim may pass a surprise — or the ⓘ's "0 on every name" is false."""
    if EQI.SURPRISE_WIRED:
        pytest.skip("surprise wired — the ⓘ wording follows the flag")
    here = os.path.dirname(os.path.abspath(__file__))
    src = open(os.path.join(os.path.dirname(here), "sepa", "canslim.py")).read()
    calls = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "compute"
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "earnings_quality"]
    assert calls
    for c in calls:
        assert len(c.args) <= 5 and not any(k.arg == "surprise_pct" for k in c.keywords), (
            "surprise is wired — flip SURPRISE_WIRED and re-word the ⓘ")


# ── honesty ─────────────────────────────────────────────────────────────────
def test_measured_is_false_unless_the_study_exists():
    assert EQI.MEASURED is False
    if EQI.MEASURED:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        assert os.path.exists(os.path.join(root, EQI.STUDY_SCRIPT))
    info = EQI.describe()
    assert info["measured"] is False
    assert "not a measured predictor" in info["measured_note"]


def test_NEGATIVE_no_cites_or_attribution_in_any_served_string():
    pat = re.compile(r"\bp\.\s?\d|page \d|Minervini|TLSW|chapter|book", re.I)
    for info in _all_infos():
        for p, s in _strings(info):
            assert not pat.search(s), (p, s)


def test_NEGATIVE_no_return_claims_outside_the_measured_note():
    pat = re.compile(r"\b(edge|outperform|win rate|beats the market|predicts)\b", re.I)
    for info in _all_infos():
        for p, s in _strings(info):
            if p == ".measured_note":
                continue
            assert not pat.search(s), (p, s)


def test_NEGATIVE_the_describer_never_imports_research():
    tree = ast.parse(inspect.getsource(EQI))
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            assert not any("research" in a.name for a in n.names)
        if isinstance(n, ast.ImportFrom):
            assert "research" not in (n.module or "")
            assert not any(a.name == "research" for a in n.names)


def test_NEGATIVE_compute_reason_strings_are_never_served():
    served = " ".join(s for _, s in _strings(EQI.describe()))
    for reason in ("(p.158)", "(p.157)", "(p.143)", "(p.155)", "(p.140)", "(p.141)"):
        assert reason not in served


# ── _as_of_range (hottest.py) ───────────────────────────────────────────────
def test_as_of_range():
    from rotation import hottest as H
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    a, b = 1790000000, 1790800000

    def d(ts):
        return datetime.fromtimestamp(ts, timezone.utc).astimezone(et).strftime("%Y-%m-%d")
    got = H._as_of_range({"X": {"cached_at": b}, "Y": {"cached_at": a}, "Z": None})
    assert got == {"oldest": d(a), "newest": d(b), "n": 2}


def test_NEGATIVE_as_of_range_is_never_1970():
    from rotation import hottest as H
    assert H._as_of_range({}) is None
    assert H._as_of_range(None) is None
    assert H._as_of_range({"X": {"cached_at": None}, "Y": {"cached_at": 0},
                           "Z": {}}) is None


# ── Critic 2026-09-28 (#2): "blank" is NOT only "fewer than 5 quarters" ─────
#
# compute() leaves the score blank when NEITHER EPS nor sales has a year-ago
# comparison for the latest quarter — which also happens with 8 quarters on file
# when the year-ago quarter is missing or zero. The ⓘ must say every way.

EIGHT_EPS = [0.5, 0.4, 0.3, 0.2, 0.0, 0.1, 0.1, 0.1]
EIGHT_REV = [100.0, 90.0, 80.0, 70.0, None, 60.0, 60.0, 60.0]
EIGHT_NI = [10.0, 9.0, 8.0, 7.0, 6.0, 6.0, 6.0, 6.0]


def _blank_texts(info):
    return [next(t["rule"] for t in info["tiers"] if t["key"] == "unknown"), info["blank"][0]]


def test_eight_quarters_with_a_zero_or_missing_year_ago_is_blank():
    out = EQ.compute(EIGHT_EPS, EIGHT_REV, EIGHT_NI)
    assert len(EIGHT_EPS) == 8 and out["score"] is None and out["tier"] == "unknown"
    for text in _blank_texts(EQI.describe()):
        low = text.lower()
        assert "zero" in low and "missing" in low
        assert f"fewer than {EQI.MIN_QUARTERS} quarters" in low
        assert "neither eps nor sales" in low


def test_latest_quarter_missing_is_blank_too():
    eps = [None] + [0.2] * 7
    rev = [None] + [80.0] * 7
    assert EQ.compute(eps, rev, [8.0] * 8)["score"] is None
    assert "latest" in EQI.describe()["blank"][0]


def test_negative_one_side_comparable_is_scored_so_the_text_says_neither():
    # EPS year-ago is zero, but sales compares → a score exists. The text must
    # therefore require BOTH sides missing ("neither … nor"), never "either".
    rev = [100.0, 90.0, 80.0, 70.0, 60.0, 60.0, 60.0, 60.0]
    assert EQ.compute(EIGHT_EPS, rev, EIGHT_NI)["score"] is not None
    for text in _blank_texts(EQI.describe()):
        assert "either eps or sales" not in text.lower()


def test_negative_the_old_quarters_only_sentence_is_gone():
    info = EQI.describe()
    assert "Fewer than 5 quarters of EPS and sales on file." not in info["blank"]
    assert all("for both EPS and sales" not in t["rule"] for t in info["tiers"])


def test_no_yoy_text_matches_the_compute_guard_source():
    # the describer's reason is the guard in compute(); if the guard changes,
    # this turns red and the wording has to be revisited.
    src = inspect.getsource(EQ.compute)
    assert "if eps_g[0] is None and rev_g[0] is None:" in src
    ysrc = inspect.getsource(EQ._yoy)
    assert "len(series) <= i + 4" in ysrc and "b == 0" in ysrc
