"""🎚 Tape panel — ONE served "who's in control" line (BUILD_SPEC21 D1 / D7, 2026-10-21).

Ajay 2026-10-21 (screenshot: badge "MIXED 40.4%", session delta "−564K sh · −18.5% of volume · sellers in control"):
"Also its not very clear in the TAPE if they are buyers or sellers".

`orderflow.tape.delta_summary` adds `control` {session, late, turning, headline, detail}. The word rule is the SIGN rule
the FE's deltaTone used (delta > 0 buyers, < 0 sellers, 0 balanced) — moved server-side, NO threshold (−1 sh = sellers).
Synthetic sided tapes; no network. NEGATIVES: −1 sh is sellers (no dead band), balanced never says buyers/sellers, the
empty tape says "no prints yet", the existing keys are unchanged, and the 🎚 tape_control check reads the same signs.
"""
from __future__ import annotations

import ast
import inspect
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orderflow import tape as TP                            # noqa: E402
from orderflow.tape import delta_summary                    # noqa: E402

START = datetime(2026, 10, 21, 14, 0, tzinfo=timezone.utc)   # 10:00 ET
OLD_KEYS = {"buy_volume", "sell_volume", "delta", "delta_pct_of_volume", "classified_pct", "late_delta",
            "late_window_min", "series", "per_minute", "n_trades"}


def _df(rows):
    """rows = [(minute_offset, size, side)] → a sided tape (price constant; side is given, not derived)."""
    idx = [START + timedelta(minutes=m) for m, _s, _d in rows]
    return pd.DataFrame({"price": [10.0] * len(rows), "size": [s for _m, s, _d in rows],
                         "side": [d for _m, _s, d in rows]}, index=pd.DatetimeIndex(idx, name="ts_utc"))


def _early_late(early_delta: int, late_delta: int, late_min: int = TP.LATE_WINDOW_MIN):
    """An early print (well before the late window) + a late print at the end: session = early + late."""
    rows = [(0, 1000, 0)]                                      # unclassified volume, fixes the base
    if early_delta:
        rows.append((1, abs(early_delta), 1 if early_delta > 0 else -1))
    end = late_min * 4
    rows.append((end - 1, 1, 0))
    if late_delta:
        rows.append((end, abs(late_delta), 1 if late_delta > 0 else -1))
    else:
        rows.append((end, 1, 0))
    return _df(rows)


# ── the four headlines + empty ───────────────────────────────────────────────
def test_sellers_in_control_same_side():
    c = delta_summary(_early_late(-500_000, -14_000))["control"]
    assert (c["session"], c["late"], c["turning"]) == ("sellers", "sellers", False)
    assert c["headline"] == "SELLERS IN CONTROL"


def test_buyers_in_control_same_side():
    d = delta_summary(_early_late(900, 50))
    c = d["control"]
    assert (c["session"], c["late"], c["turning"], c["headline"]) == ("buyers", "buyers", False, "BUYERS IN CONTROL")
    assert d["late_delta"] == 50 and d["delta"] == 950


def test_turning_when_the_two_words_differ_and_neither_is_balanced():
    c = delta_summary(_early_late(-564_000, 14_000))["control"]
    assert (c["session"], c["late"], c["turning"]) == ("sellers", "buyers", True)
    assert c["headline"] == "sellers for the session · buyers in the last 30 min — turning"
    c = delta_summary(_early_late(564_000, -14_000))["control"]
    assert c["turning"] and c["headline"] == "buyers for the session · sellers in the last 30 min — turning"


def test_balanced_both_zero():
    c = delta_summary(_df([(0, 500, 0), (1, 500, 0)]))["control"]
    assert (c["session"], c["late"], c["turning"], c["headline"]) == ("balanced", "balanced", False, "BALANCED")


def test_session_balanced_late_not():
    # session delta 0 overall but the late window carries buyers: early sellers offset by late buyers
    c = delta_summary(_early_late(-300, 300))["control"]
    assert (c["session"], c["late"], c["turning"]) == ("balanced", "buyers", False)
    assert c["headline"] == "balanced for the session · buyers now"


def test_session_one_sided_late_balanced():
    # not named in the spec's list — the mirror of "balanced for the session · … now" (executor reading)
    c = delta_summary(_early_late(-300, 0))["control"]
    assert (c["session"], c["late"], c["turning"]) == ("sellers", "balanced", False)
    assert c["headline"] == "sellers for the session · balanced in the last 30 min"


def test_empty_tape_says_no_prints_yet():
    for df in (None, pd.DataFrame(columns=["price", "size", "side"])):
        d = delta_summary(df)
        c = d["control"]
        assert c["headline"] == "no prints yet"
        assert (c["session"], c["late"], c["turning"]) == ("balanced", "balanced", False)
        assert c["detail"] == "session +0 sh (+0.0% of volume) · last 30 min +0 sh"


# ── detail: signed shares, the FE's unicode minus ────────────────────────────
def test_detail_signed_with_the_unicode_minus():
    d = delta_summary(_early_late(-564_000, -14_000))
    c = d["control"]
    pct = d["delta_pct_of_volume"]
    assert pct < 0
    assert c["detail"] == ("session −578,000 sh (−%.1f%% of volume) · last 30 min −14,000 sh" % abs(pct))
    assert "-" not in c["detail"], "ASCII hyphen-minus never prints; the FE's − does"
    b = delta_summary(_early_late(900, 50))["control"]
    assert b["detail"].startswith("session +950 sh (+") and b["detail"].endswith("last 30 min +50 sh")


def test_the_late_window_is_served_not_typed(monkeypatch):
    monkeypatch.setattr(TP, "LATE_WINDOW_MIN", 15)
    d = delta_summary(_early_late(-564_000, 14_000, late_min=15))
    assert d["late_window_min"] == 15
    assert d["control"]["headline"] == "sellers for the session · buyers in the last 15 min — turning"
    assert "last 15 min" in d["control"]["detail"]


# ── NEGATIVES: the sign rule, no threshold ───────────────────────────────────
def test_negative_minus_one_share_is_sellers_no_dead_band():
    d = delta_summary(_df([(0, 1000, 0), (1, 1, -1)]))
    assert d["delta"] == -1
    c = d["control"]
    assert c["session"] == "sellers" and c["late"] == "sellers" and c["headline"] == "SELLERS IN CONTROL"
    d = delta_summary(_df([(0, 1000, 0), (1, 1, 1)]))
    assert d["control"]["headline"] == "BUYERS IN CONTROL"


def test_negative_no_threshold_constant_in_the_rule():
    src = inspect.getsource(TP._control_word)
    lits = [n.value for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
    assert lits == [0, 0], lits                               # only the sign comparisons
    assert TP._control_word(0.0001) == "buyers" and TP._control_word(-0.0001) == "sellers"
    assert TP._control_word(0) == "balanced"


def test_negative_balanced_never_names_a_side():
    for df in (_df([(0, 500, 0)]), None):
        c = delta_summary(df)["control"]
        assert "buyers" not in c["headline"].lower() and "sellers" not in c["headline"].lower()


def test_negative_turning_is_false_when_one_side_is_balanced():
    assert delta_summary(_early_late(-300, 300))["control"]["turning"] is False
    assert delta_summary(_early_late(-300, 0))["control"]["turning"] is False


def test_negative_existing_keys_are_unchanged():
    d = delta_summary(_early_late(-564_000, 14_000))
    assert set(d) == OLD_KEYS | {"control"}
    e = delta_summary(None)
    assert set(e) == OLD_KEYS | {"control"}
    assert {k: e[k] for k in OLD_KEYS} == {"buy_volume": 0, "sell_volume": 0, "delta": 0, "delta_pct_of_volume": 0.0,
                                          "classified_pct": 0.0, "late_delta": 0,
                                          "late_window_min": TP.LATE_WINDOW_MIN, "series": [], "per_minute": [],
                                          "n_trades": 0}
    assert set(d["control"]) == {"session", "late", "turning", "headline", "detail"}


def test_the_words_come_from_the_constants():
    assert TP.CONTROL_WORDS == ("buyers", "sellers", "balanced")
    assert set(TP.CONTROL_TEXT) == {"same", "turning", "balanced", "session_balanced", "late_balanced", "empty",
                                    "detail"}
    assert TP.CONTROL_TEXT["balanced"] == "BALANCED" and TP.CONTROL_TEXT["empty"] == "no prints yet"


def test_no_ban_word_and_no_edge_claim_in_the_words():
    import re
    words = " ".join(TP.CONTROL_TEXT.values())
    assert not re.search("b" + "ounc", words, re.I)
    assert not re.search(r"\bedge\b|\bbuy now\b|\bwin\b", words, re.I)


def test_the_tape_control_check_reads_the_same_signs():
    """The 🎚 push's check 3 (signals.delta_check) is untouched: it still reads delta / late_delta, not `control`."""
    from orderflow.signals import delta_check
    src = inspect.getsource(delta_check)
    assert "control" not in src
    d = delta_summary(_early_late(900, 50))
    assert delta_check(d)["pass"] is True and d["control"]["headline"] == "BUYERS IN CONTROL"
    s = delta_summary(_early_late(-900, -50))
    assert delta_check(s)["pass"] is False and s["control"]["headline"] == "SELLERS IN CONTROL"


def test_analyze_tape_serves_control_inside_delta():
    rows = [(0, 1000, 0), (1, 500, 1)]
    df = _df(rows)[["price", "size"]].copy()
    df["price"] = [10.0, 10.01]
    out = TP.analyze_tape(df)
    assert out["delta"]["control"]["headline"] == "BUYERS IN CONTROL"
