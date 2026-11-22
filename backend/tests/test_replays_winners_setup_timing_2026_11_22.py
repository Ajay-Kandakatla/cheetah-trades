"""🏆 Past winners by setup + timing (2026-11-22).

Ajay 2026-11-22, verbatim: "can you categorize past winners like some are kiss and fly based and some might be VCP
based some might be horizontal faded.. Do we have those metrics? also reversal squeeze is mainly what I look for." →
"yes please" (filter the 🏆 list by setup, 🎾 first). First-hour runners: "dont't remove but add a tag but sort by EOD
and Intraday ones on the top". One row per stock (same day): "Just AKAN can you please bring its past winner session to
like from MAY multiday when ever a stock has multiday group it in the same role for past winners please." · "CLRO
another example add all the videos may be click them together".

The labeller writes `setups` + `timing` into each single-day sidecar; the server READS them. NEGATIVES: a sidecar with
no label is still listed (unknown timing LAST); an unknown setup / class / bucket never crashes and counts in
`skipped_label`; a 🎾 float-gated reel is never a 🎾 count; no NaN; every served word comes from constants.
"""
from __future__ import annotations

import json
import math

import pytest

import ast
from pathlib import Path

from chart_maps.gajjala import constants as GC
from chart_maps.replays import constants as C
from chart_maps.replays import store as ST
from tests.test_replays_winners_2026_11_18 import _cards, _strict, _strings, multi, put, single

ASK_SETUP = ("can you categorize past winners like some are kiss and fly based and some might be VCP based some might "
             "be horizontal faded.. Do we have those metrics? also reversal squeeze is mainly what I look for.")


def lab(primary="reversal_squeeze", cls="A+ before peak", chips=None, stopped=False, **kw):
    s = {"primary": primary, "class": cls, "chips": [primary] if chips is None and primary else (chips or []),
         "rs": None, "rs_float_gated": None, "stopped_before_peak": stopped, "peak_t": "16:02",
         "source": "label_winners 2026-11-22"}
    s.update(kw)
    return s


def tim(bucket="eod", t="16:02"):
    return {"bucket": bucket, "peak_t": t, "source": "time_of_day 2026-11-22"}


def w(sym, day, cg=120.0, setups=None, timing=None, **kw):
    s = single(sym, day, cg=cg, hp=cg + 50, **kw)
    if setups is not None:
        s["setups"] = setups
    if timing is not None:
        s["timing"] = timing
    return s


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "replays"
    put(r, "winners", w("EODA", "2026-11-10", 150.0, lab(), tim("eod", "16:30")))
    put(r, "winners", w("EODB", "2026-11-12", 110.0, lab("intraday_vcp", "armed only", stopped=True), tim("eod", "15:10")))
    put(r, "winners", w("EODC", "2026-11-12", 300.0, lab("kiss_fly", "after the peak"), tim("eod", "19:59")))
    put(r, "winners", w("INTA", "2026-11-18", 105.0, lab(None, "none", chips=[]), tim("intraday", "11:00")))
    put(r, "winners", w("FHRA", "2026-11-18", 400.0, lab("reversal_squeeze", "armed only"), tim("first_hour", "09:41")))
    put(r, "winners", w("GATE", "2026-11-11", 200.0,
                        lab(None, "🎾 float-gated", chips=[], rs_float_gated={"reason": "float over 10M"}),
                        tim("intraday", "12:00")))
    put(r, "winners", w("NOLB", "2026-11-19", 500.0))                         # no labels at all
    put(r, "winners", w("NULB", "2026-11-17", 90.0, lab(None, "no peak", chips=[]), tim(None, None)))
    put(r, "multiday", multi("BTCT"))
    return r


def _syms(p):
    return [r["symbol"] for r in p["rows"]]


def _row(p, sym):
    return next(r for r in p["rows"] if r["symbol"] == sym)


def _count(p, key):
    return next(x["count"] for x in p["setups"] if x["key"] == key)


# ── constants ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_setup_order_words_and_emoji_from_the_house():
    assert C.WIN_SETUP_ORDER == ("reversal_squeeze", "intraday_vcp", "kiss_fly", "bull_flag", "horizontal_fade")
    assert set(C.WIN_SETUP_ORDER) == set(GC.SETUPS)
    assert C.WIN_SETUP_FILTER_KEYS == C.WIN_SETUP_ORDER + ("none",)
    subs = {k: f"{e} {l}" for k, e, l in GC.SUBS}
    assert C.WIN_SETUP_WORDS == {**{k: subs[k] for k in C.WIN_SETUP_ORDER}, "none": "no Gajjala setup"}
    assert [C.WIN_SETUP_WORDS[k][:1] for k in C.WIN_SETUP_ORDER] == ["🎾", "🌀", "💋", "🚩", "➖"]
    assert C.WIN_TIMING_ORDER == ("eod", "intraday", "first_hour")
    assert set(C.WIN_CLASS_WORDS) == set(C.WIN_CLASSES_WITH_SETUP) | set(C.WIN_CLASSES_NO_SETUP)
    assert not set(C.WIN_CLASSES_WITH_SETUP) & set(C.WIN_CLASSES_NO_SETUP)


# ── the card ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_card_serves_setup_class_stopped_and_timing_words(root):
    by = {v["symbol"]: v for v in _cards(ST.winners_payload(root))}
    a = by["EODA"]
    assert (a["setup"], a["setup_text"], a["setup_class"], a["setup_class_text"]) == (
        "reversal_squeeze", "🎾 Reversal Squeeze", "A+ before peak", C.WIN_CLASS_WORDS["A+ before peak"])
    assert a["setup_chips"] == ["reversal_squeeze"]
    assert a["stopped_before_peak"] is False and a["stopped_text"] is None
    assert a["setup_chips_text"] == []                            # the primary is setup_text, never repeated
    assert a["timing"] == "eod" and a["timing_text"] == "🌙 end of day (peak 16:30)"
    b = by["EODB"]
    assert b["stopped_before_peak"] is True and b["stopped_text"] == "⛔ stopped before the peak"
    assert by["INTA"]["timing_text"] == "☀️ intraday (peak 11:00)"
    assert by["FHRA"]["timing_text"] == "🌅 first hour (peak 09:41)"
    assert by["INTA"]["setup"] == "none" and by["INTA"]["setup_text"] == "no Gajjala setup"
    assert by["INTA"]["setup_class_text"] is None                 # the setup words already say it


def test_NEGATIVE_a_sidecar_without_labels_is_still_listed_unlabelled(root):
    p = ST.winners_payload(root)
    nolb = [v for v in _cards(p) if v["symbol"] == "NOLB"]
    assert len(nolb) == 1
    v = nolb[0]
    assert v["setup"] is None and v["setup_text"] is None and v["timing"] is None and v["timing_text"] is None
    assert v["setup_chips"] == [] and v["stopped_text"] is None
    assert p["counts"]["skipped_label"] == 0                       # absent is not malformed


def test_NEGATIVE_a_labelled_null_bucket_is_unknown_not_skipped(root):
    p = ST.winners_payload(root)
    v = next(v for v in _cards(p) if v["symbol"] == "NULB")
    assert v["timing"] is None and v["setup"] == "none" and v["setup_class_text"] == C.WIN_CLASS_WORDS["no peak"]
    assert p["counts"]["skipped_label"] == 0


# ── the order (one row per stock) ─────────────────────────────────────────────────────────────────────────────
def test_rows_order_eod_then_intraday_then_first_hour_then_unknown(root):
    p = ST.winners_payload(root)
    assert "groups" not in p
    assert _syms(p) == ["EODC", "EODB", "EODA", "INTA", "GATE", "FHRA", "NOLB", "NULB", "BTCT"]
    assert [r["timing"] for r in p["rows"]] == ["eod"] * 3 + ["intraday"] * 2 + ["first_hour"] + [None] * 3
    assert _row(p, "EODA")["timing_text"] == "🌙 end of day (peak 16:30)"
    assert _row(p, "BTCT")["timing"] is None and _row(p, "BTCT")["timing_text"] is None   # multi-day only → unknown
    for r in p["rows"]:
        assert r["key"] == f"sym-{r['symbol']}" and all(v["symbol"] == r["symbol"] for v in r["videos"])
        assert all(v["date"] and v["label_date"] for v in r["videos"])   # each reel keeps its date


def test_NEGATIVE_first_hour_is_never_dropped_only_sorted_lower(root):
    p = ST.winners_payload(root)
    assert "FHRA" in [v["symbol"] for v in _cards(p)]
    assert p["counts"]["single_day"] == 8 and len(_cards(p)) == 9 and len(p["rows"]) == 9


def test_same_timing_same_day_same_gain_ties_by_symbol(tmp_path):
    for s in ("ZZ", "AA", "MM"):
        put(tmp_path, "winners", w(s, "2026-11-12", 100.0, lab(), tim("intraday", "12:00")))
    assert _syms(ST.winners_payload(tmp_path)) == ["AA", "MM", "ZZ"]


def test_same_timing_newest_win_then_best_close_gain(tmp_path):
    put(tmp_path, "winners", w("OLDBIG", "2026-11-10", 900.0, lab(), tim("eod", "16:00")))
    put(tmp_path, "winners", w("NEWSML", "2026-11-12", 50.0, lab(), tim("eod", "16:00")))
    put(tmp_path, "winners", w("NEWBIG", "2026-11-12", 300.0, lab(), tim("eod", "16:00")))
    assert _syms(ST.winners_payload(tmp_path)) == ["NEWBIG", "NEWSML", "OLDBIG"]


def test_the_NEWEST_single_day_reel_decides_the_row_timing(tmp_path):
    """NEGATIVE: an older eod reel never lifts a row whose newest single day peaked in the first hour."""
    put(tmp_path, "winners", w("MIXT", "2026-11-01", 500.0, lab(), tim("eod", "16:00")))
    put(tmp_path, "winners", w("MIXT", "2026-11-12", 100.0, lab(), tim("first_hour", "09:45")))
    put(tmp_path, "winners", w("INTR", "2026-06-01", 10.0, lab(), tim("intraday", "12:00")))
    p = ST.winners_payload(tmp_path)
    assert _syms(p) == ["INTR", "MIXT"]
    m = _row(p, "MIXT")
    assert m["timing"] == "first_hour" and m["timing_text"] == "🌅 first hour (peak 09:45)"
    assert [v["date"] for v in m["videos"]] == ["2026-11-12", "2026-11-01"]          # newest first


def test_NEGATIVE_a_newest_single_day_with_no_timing_is_unknown_even_if_an_older_one_has_eod(tmp_path):
    put(tmp_path, "winners", w("UNK", "2026-11-01", 500.0, lab(), tim("eod", "16:00")))
    put(tmp_path, "winners", w("UNK", "2026-11-12", 100.0))
    put(tmp_path, "winners", w("FH", "2026-06-01", 10.0, lab(), tim("first_hour", "09:31")))
    p = ST.winners_payload(tmp_path)
    assert _syms(p) == ["FH", "UNK"] and _row(p, "UNK")["timing"] is None


# ── one row per stock: merge + wins (Ajay: "group it in the same role" · "click them together") ───────────────────
def test_NEGATIVE_two_symbols_never_merge(tmp_path):
    for s in ("AKAN", "AKANW", "AKA"):
        put(tmp_path, "winners", w(s, "2026-11-12", 100.0, lab(), tim("eod", "16:00")))
    p = ST.winners_payload(tmp_path)
    assert sorted(_syms(p)) == ["AKA", "AKAN", "AKANW"]
    assert all(len(r["videos"]) == 1 and r["wins"] == 1 for r in p["rows"])


def test_a_multiday_run_and_its_single_days_are_ONE_win_a_later_single_day_is_a_second(tmp_path):
    put(tmp_path, "multiday", multi("MEDS", days=("2026-09-14", "2026-09-15", "2026-09-16"), cg=601.0))
    put(tmp_path, "winners", w("MEDS", "2026-09-15", 87.0, lab(None, "none", chips=[]), tim("intraday", "13:32")))
    put(tmp_path, "winners", w("MEDS", "2026-09-16", 275.0, lab(), tim("intraday", "10:58")))
    p = ST.winners_payload(tmp_path)
    r = _row(p, "MEDS")
    assert len(p["rows"]) == 1 and len(r["videos"]) == 3
    assert r["wins"] == 1 and r["wins_text"] == "1 win"
    assert r["newest_date"] == "2026-09-16" and r["newest_text"] == "newest Wed 2026-09-16"
    assert [(v["sub"], v["days"][-1]) for v in r["videos"]] == [
        ("multiday", "2026-09-16"), ("winners", "2026-09-16"), ("winners", "2026-09-15")]
    assert r["timing"] == "intraday" and r["timing_text"] == "☀️ intraday (peak 10:58)"
    assert r["best_close_gain_pct"] == 601.0
    put(tmp_path, "winners", w("MEDS", "2026-10-20", 120.0, lab(), tim("eod", "16:10")))
    r2 = _row(ST.winners_payload(tmp_path), "MEDS")
    assert r2["wins"] == 2 and r2["wins_text"] == "2 wins" and r2["newest_date"] == "2026-10-20"
    assert [v["date"] for v in r2["videos"]][0] == "2026-10-20" and r2["timing"] == "eod"


def test_NEGATIVE_a_single_day_BEFORE_the_run_is_its_own_win(tmp_path):
    put(tmp_path, "multiday", multi("RUN", days=("2026-09-14", "2026-09-15", "2026-09-16"), cg=200.0))
    put(tmp_path, "winners", w("RUN", "2026-09-10", 100.0))
    r = _row(ST.winners_payload(tmp_path), "RUN")
    assert r["wins"] == 2 and r["newest_date"] == "2026-09-16"
    assert [v["sub"] for v in r["videos"]] == ["multiday", "winners"]


def test_a_multi_day_only_row_is_listed_unknown_with_its_run_end_as_newest(root):
    r = _row(ST.winners_payload(root), "BTCT")
    assert r["wins"] == 1 and r["newest_date"] == "2026-08-24" and r["setup"] is None and r["filter_keys"] == []


def test_NEGATIVE_a_row_with_no_labels_is_still_listed(root):
    r = _row(ST.winners_payload(root), "NOLB")
    assert r["setup"] is None and r["setup_text"] is None and r["timing"] is None and r["filter_keys"] == []
    assert r["wins"] == 1 and len(r["videos"]) == 1


def test_the_row_best_setup_is_the_first_in_the_ask_order(tmp_path):
    put(tmp_path, "winners", w("BEST", "2026-11-12", 100.0, lab("bull_flag", "armed only"), tim("eod", "16:00")))
    put(tmp_path, "winners", w("BEST", "2026-11-10", 100.0, lab("intraday_vcp", "after the peak"), tim("eod", "16:00")))
    put(tmp_path, "winners", w("BEST", "2026-11-05", 100.0, lab(None, "none", chips=[]), tim("eod", "16:00")))
    r = _row(ST.winners_payload(tmp_path), "BEST")
    assert r["setup"] == "intraday_vcp" and r["setup_text"] == "🌀 Intraday VCP"
    assert r["filter_keys"] == ["intraday_vcp", "bull_flag", "none"]


# ── the filter row ────────────────────────────────────────────────────────────────────────────────────────────
def test_setup_filter_counts_all_first_then_rs_then_the_ask_order_then_none(root):
    f = ST.winners_payload(root)["setups"]
    assert [x["key"] for x in f] == ["all", "reversal_squeeze", "intraday_vcp", "kiss_fly", "bull_flag",
                                     "horizontal_fade", "none"]
    assert [x["label"] for x in f] == ["All", "🎾 Reversal Squeeze", "🌀 Intraday VCP", "💋 EMA Kiss & Fly",
                                       "🚩 Bull Flag", "➖ Horizontal Fade", "no Gajjala setup"]
    assert {x["key"]: x["count"] for x in f} == {"all": 9, "reversal_squeeze": 2, "intraday_vcp": 1, "kiss_fly": 1,
                                                 "bull_flag": 0, "horizontal_fade": 0, "none": 3}


def test_filter_rs_selects_the_rs_rows_and_all_counts_every_row(root):
    p = ST.winners_payload(root)
    assert sorted(r["symbol"] for r in p["rows"] if "reversal_squeeze" in r["filter_keys"]) == ["EODA", "FHRA"]
    assert _count(p, "all") == len(p["rows"])


def test_filter_counts_ROWS_not_reels(tmp_path):
    """Two 🎾 reels of one stock are ONE 🎾 row; 'All' counts rows."""
    put(tmp_path, "winners", w("TWO", "2026-11-12", 100.0, lab(), tim("eod", "16:00")))
    put(tmp_path, "winners", w("TWO", "2026-11-10", 100.0, lab(), tim("eod", "16:00")))
    put(tmp_path, "winners", w("ONE", "2026-11-10", 100.0, lab("kiss_fly", "armed only"), tim("eod", "16:00")))
    p = ST.winners_payload(tmp_path)
    assert _count(p, "all") == 2 and _count(p, "reversal_squeeze") == 1 and _count(p, "kiss_fly") == 1
    assert p["counts"]["videos"] == 3


def test_a_rs_SECONDARY_chip_passes_the_rs_filter_and_serves_its_words(tmp_path):
    """Review fix (a): 16 real reels carry 🎾 armed / A+ beside another primary (JZ 06-01: 💋 primary, chips 🎾 + 💋)."""
    put(tmp_path, "winners", w("JZ", "2026-06-01", 100.0, lab("kiss_fly", "A+ before peak",
                                                             chips=["kiss_fly", "reversal_squeeze"]), tim("eod", "16:00")))
    put(tmp_path, "winners", w("VCPO", "2026-06-02", 100.0, lab("intraday_vcp", "armed only",
                                                               chips=["intraday_vcp", "kiss_fly"]), tim("eod", "16:00")))
    p = ST.winners_payload(tmp_path)
    jz = _cards(p)[[v["symbol"] for v in _cards(p)].index("JZ")]
    assert jz["setup"] == "kiss_fly" and jz["setup_chips"] == ["reversal_squeeze", "kiss_fly"]
    assert jz["setup_chips_text"] == ["also 🎾 Reversal Squeeze"]
    assert _row(p, "JZ")["filter_keys"] == ["reversal_squeeze", "kiss_fly"]
    assert _row(p, "JZ")["setup"] == "reversal_squeeze"
    assert _count(p, "reversal_squeeze") == 1 and _count(p, "kiss_fly") == 1
    # NEGATIVE: only 🎾 matches as a secondary chip — a 💋 chip beside a 🌀 primary is words only, never a 💋 match
    vc = _row(p, "VCPO")
    assert vc["filter_keys"] == ["intraday_vcp"] and vc["videos"][0]["setup_chips_text"] == ["also 💋 EMA Kiss & Fly"]


def test_NEGATIVE_float_gated_is_never_a_rs_count(root):
    p = ST.winners_payload(root)
    gate = next(v for v in _cards(p) if v["symbol"] == "GATE")
    assert gate["setup"] == "none" and gate["setup_class"] == "🎾 float-gated"
    assert _count(p, "reversal_squeeze") == 2
    assert "reversal_squeeze" not in _row(p, "GATE")["filter_keys"]


def test_NEGATIVE_a_rs_primary_on_a_float_gated_class_is_malformed(tmp_path):
    put(tmp_path, "winners", w("MIX", "2026-11-12", 100.0, lab("reversal_squeeze", "🎾 float-gated")))
    p = ST.winners_payload(tmp_path)
    v = _cards(p)[0]
    assert v["setup"] is None and p["counts"]["skipped_label"] == 1
    assert _count(p, "reversal_squeeze") == 0


def test_NEGATIVE_a_rs_chip_on_a_float_gated_class_is_malformed_never_a_rs_count(tmp_path):
    put(tmp_path, "winners", w("GCHIP", "2026-11-12", 100.0, lab(None, "🎾 float-gated", chips=["reversal_squeeze"]),
                               tim("eod", "16:00")))
    p = ST.winners_payload(tmp_path)
    assert _cards(p)[0]["setup"] is None and p["counts"]["skipped_label"] == 1
    assert _count(p, "reversal_squeeze") == 0 and _row(p, "GCHIP")["filter_keys"] == []


def test_NEGATIVE_multiday_reels_carry_no_setup_even_with_a_label(tmp_path):
    put(tmp_path, "multiday", multi("BTCT", setups=lab(), timing=tim()))
    p = ST.winners_payload(tmp_path)
    v = _cards(p)[0]
    assert v["setup"] is None and v["timing"] is None and p["counts"]["skipped_label"] == 0


# ── malformed labels ──────────────────────────────────────────────────────────────────────────────────────────
BAD_SETUPS = [
    "not a dict", ["reversal_squeeze"], lab("cup_handle"), lab("REVERSAL_SQUEEZE"), lab(cls="A+ after lunch"),
    lab(cls=None), lab(None, "A+ before peak", chips=[]), lab(chips=["reversal_squeeze", "nope"]), lab(chips="x"),
    lab(stopped="yes"), lab(stopped=1), lab(primary=float("nan")), lab(cls="error"),
    lab(None, "none", chips=[], stopped=True),                    # review fix (c): stopped with no primary
    lab(None, "🎾 float-gated", chips=[], stopped=True), lab(None, "none", chips=["intraday_vcp"]),
]
BAD_TIMING = ["eod", ["eod"], tim("evening"), tim("EOD"), tim("eod", None), tim("eod", "4pm"), tim("eod", "24:00"),
              tim("first_hour", "9:41"), tim(1, "10:00"),
              # review fix (c): a bucket that disagrees with its own peak minute (bounds: lower in, upper out)
              tim("eod", "10:00"), tim("eod", "14:59"), tim("eod", "20:00"), tim("intraday", "10:29"),
              tim("intraday", "15:00"), tim("first_hour", "10:30"), tim("first_hour", "09:29"), tim("eod", "09:00")]


@pytest.mark.parametrize("setups", BAD_SETUPS)
def test_NEGATIVE_an_unknown_setup_label_never_crashes_and_counts_skipped_label(tmp_path, setups):
    put(tmp_path, "winners", w("BAD", "2026-11-12", 100.0, setups, tim("eod", "16:00")))
    p = ST.winners_payload(tmp_path)
    assert p["state"] == "ready" and p["counts"]["skipped_bad"] == 0 and p["counts"]["skipped_label"] == 1
    v = _cards(p)[0]
    assert v["setup"] is None and v["setup_text"] is None and v["setup_chips"] == []
    assert v["timing"] == "eod"                                   # the good timing label still counts
    _strict(json.dumps(p, allow_nan=True))


@pytest.mark.parametrize("timing", BAD_TIMING)
def test_NEGATIVE_an_unknown_bucket_never_crashes_counts_skipped_label_and_sorts_last(tmp_path, timing):
    put(tmp_path, "winners", w("BAD", "2026-11-19", 900.0, lab(), timing))
    put(tmp_path, "winners", w("OK", "2026-06-01", 10.0, lab(), tim("first_hour", "09:31")))
    p = ST.winners_payload(tmp_path)
    assert p["counts"]["skipped_label"] == 1 and p["counts"]["skipped_bad"] == 0
    assert _syms(p) == ["OK", "BAD"]
    bad = p["rows"][1]["videos"][0]
    assert bad["symbol"] == "BAD" and bad["timing"] is None and bad["timing_text"] is None
    assert bad["setup"] == "reversal_squeeze"                     # the good setup label still counts


def test_NEGATIVE_both_labels_bad_count_twice_and_the_card_stays(tmp_path):
    put(tmp_path, "winners", w("BAD", "2026-11-12", 100.0, lab("x"), tim("y", "10:00")))
    p = ST.winners_payload(tmp_path)
    assert p["counts"]["skipped_label"] == 2 and p["counts"]["videos"] == 1


def test_NEGATIVE_a_raw_nan_in_the_label_file_never_reaches_the_json(tmp_path):
    s = w("NAN", "2026-11-12", 100.0, lab(), tim())
    raw = json.dumps(s).replace('"stopped_before_peak": false', '"stopped_before_peak": NaN')
    put(tmp_path, "winners", s, raw=raw)
    p = ST.winners_payload(tmp_path)
    assert p["counts"]["skipped_label"] == 1
    txt = json.dumps(p, allow_nan=True)
    _strict(txt)
    assert "NaN" not in txt
    v = _cards(p)[0]
    assert v["stopped_before_peak"] is False and v["setup"] is None
    assert not any(isinstance(x, float) and math.isnan(x) for x in v.values())


def test_NEGATIVE_empty_and_no_folder_still_serve_the_filter_row(tmp_path):
    p = ST.winners_payload(tmp_path / "missing")
    assert [x["key"] for x in p["setups"]] == ["all"] + list(C.WIN_SETUP_FILTER_KEYS)
    assert all(x["count"] == 0 for x in p["setups"]) and p["counts"]["skipped_label"] == 0
    (tmp_path / "r" / C.VIDEOS_SUB).mkdir(parents=True)
    e = ST.winners_payload(tmp_path / "r")
    assert e["state"] == "empty" and [x["count"] for x in e["setups"]] == [0] * 7


def test_NEGATIVE_no_served_label_text_comes_from_the_sidecar(tmp_path):
    put(tmp_path, "winners", w("SRC", "2026-11-12", 100.0,
                               lab(source="SOURCE-TEXT", rs_float_gated={"reason": "REASON-TEXT"}),
                               {"bucket": "eod", "peak_t": "16:00", "source": "TSOURCE-TEXT"}))
    txt = json.dumps(ST.winners_payload(tmp_path))
    for t in ("SOURCE-TEXT", "REASON-TEXT", "TSOURCE-TEXT"):
        assert t not in txt


def test_the_real_sidecar_shape_is_read(tmp_path):
    """One real 11-22 labeller sidecar shape (2026-06-02 STAK: a 🎾 float-gated reel, no timing yet)."""
    s = w("STAK", "2026-06-02", 94.87, {
        "primary": None, "class": "🎾 float-gated", "chips": [], "rs": None,
        "rs_float_gated": {"reason": "float over 10M (today's float)", "class": "A+ before peak",
                           "stopped_before_peak": False},
        "stopped_before_peak": False, "peak_t": "17:01", "source": "label_winners 2026-11-22"})
    put(tmp_path, "winners", s)
    p = ST.winners_payload(tmp_path)
    v = _cards(p)[0]
    assert v["setup"] == "none" and v["setup_class_text"] == C.WIN_CLASS_WORDS["🎾 float-gated"]
    assert v["timing"] is None and p["counts"]["skipped_label"] == 0
    assert p["rows"][0]["timing"] is None


@pytest.mark.parametrize("b,t", [("first_hour", "09:30"), ("first_hour", "10:29"), ("intraday", "10:30"),
                                 ("intraday", "14:59"), ("eod", "15:00"), ("eod", "19:59")])
def test_a_bucket_on_its_own_bounds_is_accepted(tmp_path, b, t):
    put(tmp_path, "winners", w("EDGEB", "2026-11-12", 100.0, lab(), tim(b, t)))
    p = ST.winners_payload(tmp_path)
    assert p["counts"]["skipped_label"] == 0 and _cards(p)[0]["timing"] == b


def test_the_bucket_bounds_equal_the_labellers():
    src = Path(__file__).resolve().parents[3] / "eod-audits" / "research" / "2026-11-22_winner_setup_labels" / "label_winners.py"
    if not src.is_file():
        pytest.skip("labeller source not on this host")
    tree = ast.parse(src.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "TIMING_BUCKETS" for t in n.targets))
    assert ast.literal_eval(node.value) == C.WIN_TIMING_BUCKETS
    assert {b for b, _lo, _hi in C.WIN_TIMING_BUCKETS} == set(C.WIN_TIMING_ORDER)


def test_NEGATIVE_label_words_say_peak_never_high():
    """Review fix (b): the card's "+X% high" chip is the 09:30–16:00 day bar; the labels are the 09:30–20:00 peak."""
    words = [w for w in C.WIN_CLASS_WORDS.values() if w] + [C.WIN_STOPPED_WORDS, C.WIN_TIMING_TEXT]
    for x in words:
        assert "high" not in x, x
    assert "(peak {t})" in C.WIN_TIMING_TEXT and "before the peak" in C.WIN_CLASS_WORDS["A+ before peak"]
    assert "before the peak" in C.WIN_STOPPED_WORDS


def test_the_ask_is_quoted_in_constants_source():
    from pathlib import Path
    src = (Path(C.__file__)).read_text(encoding="utf-8")
    assert ASK_SETUP in src.replace("\n# ", " ")
    assert "dont't remove but add a tag but sort by EOD and Intraday ones on the top" in src.replace("\n# ", " ")
    flat = src.replace("\n# ", " ")
    assert ("Just AKAN can you please bring its past winner session to like from MAY multiday when ever a stock has "
            "multiday group it in the same role for past winners please.") in flat
    assert "CLRO another example add all the videos may be click them together" in flat
