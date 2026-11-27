"""🩳 FLOAT SOURCES — the ONE division, a second dated float beside the one divided by, the chip warning (2026-11-26).

Ajay 2026-11-26 ~21:20 ET, verbatim: "Also the Float share count issue and SI discrepancy happened too many times need
to do something about it"

Spec: scratchpad floatguard/spec.md rev 2 §3.1 (read.pct_of, seven read.py / basis_math.py sites, bit-identical), §3.4
(short_interest/source_check.py, PURE: states incl. `window`, rank(None) = -1, neutral wording, EXTREME_CONTEST built
`flag` with off / hold / supported), §3.5 (si_block hook, the Float sources row, FLOAT_CONTESTED_NOTE, si_map
basis_over, the rules sentence). Package be-verdict, §4.1.

Inputs are REAL: tests/fixtures/si_float_captures_2026_11_26.json (a keyed extract of the planner's read-only capture
— si_record, basis_doc, the served block of main 047acbb4, the Massive free-float row — + the widened splits read) and
tests/fixtures/si_float_probe_rows_2026_11_26.json (a byte copy of the 693 probe rows joined with splits.since). The
`mfloat` sub-doc is built here from the captured Massive row by key (never a typed count); share_basis writes the
real one (package be-io). Hand-built shapes change ONE leaf of a real doc each.
"""
from __future__ import annotations

import ast
import copy
import json
import logging
import re
from datetime import date
from pathlib import Path

import pytest

from short_interest import basis_math as BM
from short_interest import client as SIC
from short_interest import read as SR
from short_interest import share_basis as SB
from short_interest import source_check as SCK
from tests.test_short_interest_read_2026_10_03 import FORBIDDEN, FakeColl, FakeDB

BACKEND = Path(__file__).resolve().parents[1]
CAP = json.loads((BACKEND / "tests" / "fixtures" / "si_float_captures_2026_11_26.json").read_text(encoding="utf-8"))
PROBE = json.loads((BACKEND / "tests" / "fixtures" / "si_float_probe_rows_2026_11_26.json").read_text(encoding="utf-8"))
TODAY = date(2026, 11, 26)                                    # the capture's serve day (captured_at 11-27 04:31Z)
NAMES = sorted(CAP["names"])
WORDING = re.compile(r"\bagree|same count|inside the|confirmed by", re.I)
SRC = (BACKEND / "short_interest" / "source_check.py").read_text(encoding="utf-8")


# ═════════════════════════════════════════════ builders (every count from the capture, by key)
def _n(sym):
    return CAP["names"][sym]


def _rec(sym):
    return copy.deepcopy(_n(sym)["si_record"])


def _doc(sym):
    d = _n(sym).get("basis_doc")
    return copy.deepcopy(d) if d is not None else None


def _mf(sym, **kw):
    """The stored `mfloat` sub-doc (spec §3.2 shape) from the captured Massive row."""
    m = _n(sym)["massive_float"]
    if m is None:
        sub = {"status": "none", "shares": None, "pct": None, "as_of": None, "read_at": CAP["captured_at"]}
    else:
        sub = {"status": "ok", "shares": m["free_float"], "pct": m["free_float_percent"], "as_of": m["effective_date"],
               "read_at": CAP["captured_at"]}
    sub.update(kw)
    return sub


def _with(sym, **over):
    d = _doc(sym)
    d["mfloat"] = _mf(sym)
    d.update(over)
    return d


def _dki_widened():
    """DKI's doc with the 11-26 widened splits read laid over: since = the second float's date, its rows on or after."""
    w, md = CAP["splits_widened"]["names"]["DKI"], _n("DKI")["massive_float"]["effective_date"]
    sp = dict(_doc("DKI")["splits"], since=md, rows=[r for r in w["rows"] if r["execution_date"] >= md])
    return _with("DKI", splits=sp)


def _clro_doc(**over):
    """CLRO-shape (no basis doc at capture): a checked doc with a CS listing and a held splits read reaching back to
    the second float's date — dates from the capture, no count typed."""
    md = _n("CLRO")["massive_float"]["effective_date"]
    d = {"_id": "CLRO", "checked_at": CAP["captured_at"], "ref": {"status": "ok", "type": "CS"},
         "splits": {"status": "ok", "since": md, "rows": []}, "sec": {"status": "none", "covers": [], "filings": []},
         "mfloat": _mf("CLRO")}
    d.update(over)
    return d


def _blk(sym, doc, today=TODAY):
    rec = _rec(sym)
    b = SR.si_block(rec, today, basis=doc)
    json.dumps(b, allow_nan=False)
    return b


def _plain(sym, doc):
    """The same block with no `mfloat` on the doc (today's path)."""
    d = copy.deepcopy(doc)
    d.pop("mfloat", None)
    return _blk(sym, d)


def _sc(b):
    return b["basis"]["sources_compared"]


def _keys(b):
    return [f.get("key") for f in (b.get("basis") or {}).get("flags") or []]


def _rows(b):
    return {r["k"]: r["v"] for r in b["rows"]}


def _strings(b) -> list:
    out = [b.get("chip") or "", b.get("title") or ""] + [r["k"] + " " + r["v"] for r in b.get("rows") or []]
    e = b.get("extreme") or {}
    out += [e.get(k) or "" for k in ("text", "short", "title")]
    out += [f.get("text") or "" for f in (b.get("basis") or {}).get("flags") or []]
    sc = (b.get("basis") or {}).get("sources_compared")
    if isinstance(sc, dict):
        out.append(sc.get("text") or "")
    return out


@pytest.fixture
def mode(monkeypatch):
    def _set(m):
        monkeypatch.setattr(SCK, "EXTREME_CONTEST", m)
    return _set


# ═════════════════════════════════════════════ the fixtures are real
def test_fixtures_are_the_real_captures():
    assert set(CAP) == {"about", "captured_at", "names", "splits_widened"} and "REAL" in CAP["about"]
    assert CAP["splits_widened"]["about"].startswith("REAL read 2026-11-26")
    assert set(PROBE) == {"about", "rows"} and PROBE["about"].startswith("REAL rows") and len(PROBE["rows"]) == 693
    for s in NAMES:
        assert set(_n(s)) == {"si_record", "basis_doc", "block", "massive_float"}
        assert "mfloat" not in (_n(s)["basis_doc"] or {})


@pytest.mark.parametrize("sym", NAMES)
def test_NEGATIVE_no_mfloat_reproduces_the_block_main_served_byte_for_byte(sym):
    """The capture's block was served by main 047acbb4: with no `mfloat` the block is today's, key for key, and the
    SOURCE_KEYS are absent (this also proves the five pct_of sites read the same numbers as before)."""
    b = _blk(sym, _doc(sym))
    assert b == _n(sym)["block"]
    assert json.dumps(b, ensure_ascii=False, sort_keys=True) == json.dumps(_n(sym)["block"], ensure_ascii=False,
                                                                          sort_keys=True)
    assert not set(SR.SOURCE_KEYS) & set(b.get("basis") or {})
    assert SCK.FLAG_SOURCES not in _keys(b)


# ═════════════════════════════════════════════ §3.1 — the ONE division
SWEEP = [(0, 1), (0, 7), (1, 3), (2, 3), (30177, 12671), (156197, 361428), (24988696, 53363881), (439732, 1403950),
         (1, 10 ** 9), (7, 9), (12.5, 7), (317810.0, 888130), (5, 2.5), (19297883, 86771374)]


@pytest.mark.parametrize("c,s", SWEEP)
def test_pct_of_equals_the_old_expression(c, s):
    assert SR.pct_of(c, s) == round(c / s * 100.0, 2)          # read.py:628-629, basis_math.py :1043 :1240 :1264
    assert SR.pct_of(c, s) == round(c / s * 100, 2)            # basis_math.py:584 (int 100)
    assert SR.pct_of(c, s, digits=None) == c / s * 100.0       # unrounded
    assert repr(SR.pct_of(c, s)) == repr(round(c / s * 100.0, 2))


@pytest.mark.parametrize("c,s", [(None, 5), (5, None), (5, 0), (5, -3), (None, None), (5, float("nan"))])
def test_NEGATIVE_pct_of_is_None_without_a_positive_denominator(c, s):
    assert SR.pct_of(c, s) is None and SR.pct_of(c, s, digits=None) is None


def _old_stale_trigger(si, base, paired, newer):
    """basis_math.stale_trigger as it stood on 047acbb4 (mode tier_moves branch), for the sweep."""
    base, paired, newer = BM._pos(base), BM._pos(paired), BM._pos(newer)
    if base is None or paired is None or newer is None:
        return False
    s = BM._num(si)
    den = base + newer - paired
    if s is None or s < 0 or den <= 0:
        return False
    return SR.tier_of(round(s / base * 100, 2)) != SR.tier_of(round(s / den * 100, 2))


@pytest.mark.parametrize("si", [0, 1, 99, 2000, 4999, 5000, 9999.5, 19999, 20000, 20001, 87654.3])
@pytest.mark.parametrize("base,paired,newer", [(100000, 100000, 100000), (100000, 100000, 150000),
                                               (100000, 120000, 400000), (99999, 1, 3), (50, 10, 9)])
def test_stale_trigger_tier_moves_is_bit_identical(monkeypatch, si, base, paired, newer):
    monkeypatch.setattr(BM, "FLOAT_STALE_WHEN", "tier_moves")
    assert BM.stale_trigger(si, base, paired, newer) is _old_stale_trigger(si, base, paired, newer)


def _fn(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def _calls(node, name):
    return sum(1 for n in ast.walk(node) if isinstance(n, ast.Call) and (
        (isinstance(n.func, ast.Name) and n.func.id == name) or
        (isinstance(n.func, ast.Attribute) and n.func.attr == name)))


def _pct_shape_divs(node):
    """Div nodes that sit under a multiplication by the constant 100 / 100.0."""
    hits = []
    for n in ast.walk(node):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult):
            sides = (n.left, n.right)
            if any(isinstance(x, ast.Constant) and x.value in (100, 100.0) for x in sides):
                hits += [x for x in sides if isinstance(x, ast.BinOp) and isinstance(x.op, ast.Div)]
    return hits


def test_the_seven_sites_call_pct_of_and_hold_no_percent_division():
    rp, bp = BACKEND / "short_interest" / "read.py", BACKEND / "short_interest" / "basis_math.py"
    assert _calls(_fn(rp, "si_block"), "pct_of") == 2
    assert _calls(_fn(bp, "stale_trigger"), "pct_of") == 2 and _calls(_fn(bp, "verdict"), "pct_of") == 3
    for p, f in ((rp, "si_block"), (bp, "stale_trigger"), (bp, "verdict")):
        assert _pct_shape_divs(_fn(p, f)) == [], f
    assert len(_pct_shape_divs(_fn(rp, "pct_of"))) == 1          # THE one
    assert len(_pct_shape_divs(_fn(bp, "change_across_split"))) == 1   # a change %, not short / shares


def test_pct_of_sits_above_the_guarded_slice():
    src = (BACKEND / "short_interest" / "read.py").read_text(encoding="utf-8")
    assert src.index("\ndef pct_of(") < src.index("EXTREME_WORD = ")
    assert src.count("_pct1(") == 2


# ═════════════════════════════════════════════ §3.4 — states, one doc each
def test_state_no_float_POM_and_SMTK_list_the_second_float_and_compare_nothing():
    for sym in ("POM", "SMTK"):
        b = _blk(sym, _with(sym))
        m = _n(sym)["massive_float"]
        assert _sc(b)["state"] == "no_float" and _sc(b)["rel"] is None
        assert _sc(b)["text"] == "No %% of float is shown, so nothing is compared · Massive %s (as of %s)." % (
            format(m["free_float"], ","), BM._md(m["effective_date"]))
        assert [r["key"] for r in b["basis"]["float_sources"]] == ["massive"]
        assert b["basis"]["extreme_contest"] is None and b["chip"] == _n(sym)["block"]["chip"]


def test_state_unread_none_units_no_splits_split_day_compared_contested():
    ncpl = _n("NCPL")["massive_float"]
    cases = {
        "unread": _with("NCPL", mfloat=_mf("NCPL", status="failed", shares=None, as_of=None,
                                           error="http_500", error_at="2026-11-27T01:00:00Z")),
        "none": _with("NCPL", mfloat=_mf("NCPL", status="none", shares=None, as_of=None)),
        "units": _with("NCPL", ref=dict(_doc("NCPL")["ref"], type="ADRC")),
        "no_splits": _with("NCPL", splits=dict(_doc("NCPL")["splits"], status="failed")),
        "split_day": _with("NCPL", splits=dict(_doc("NCPL")["splits"], rows=[
            {"execution_date": ncpl["effective_date"], "split_from": 2, "split_to": 1}])),
        "compared": _with("NCPL"),
    }
    words = {"unread": " · Massive: not read (last try failed 11/26 20:00 ET).",
             "none": " · Massive: none on file — one source only.",
             "units": " — not compared: listing type ADRC.",
             "no_splits": " — not compared: the splits read is not on file.",
             "split_day": " — not compared: a split executed the day one of them was dated."}
    for st, d in cases.items():
        b = _blk("NCPL", d)
        assert _sc(b)["state"] == st, st
        assert b["basis"]["extreme_contest"] is None and SCK.FLAG_SOURCES not in _keys(b)
        if st != "no_splits":                                  # an unheld splits read carries the verdict's ❔
            assert b["chip"] == _n("NCPL")["block"]["chip"], st
        if st in words:
            assert _sc(b)["text"].endswith(words[st]), (st, _sc(b)["text"])
            assert _sc(b)["text"].startswith("float: Yahoo 4,387,760 (read 11/18) = 10.6%")
    b = _blk("CHWY", _with("CHWY"))
    assert _sc(b)["state"] == "contested" and isinstance(b["basis"]["extreme_contest"], dict)
    assert set(SCK.STATES) == {"no_float", "unread", "none", "units", "no_splits", "window", "split_day",
                               "compared", "contested"}


@pytest.mark.parametrize("sym", ["BETR", "DKI", "WHLR"])
def test_window_as_captured_is_never_compared(sym):
    b = _blk(sym, _with(sym))
    since = _doc(sym)["splits"]["since"]
    assert _sc(b)["state"] == "window" and _sc(b)["rel"] is None
    assert _sc(b)["text"].endswith(" — not compared: the splits on file start %s, after the second float's date."
                                   % BM._md(since))
    assert b["chip"] == _n(sym)["block"]["chip"] and SCK.FLAG_SOURCES not in _keys(b)
    assert b["basis"]["extreme_contest"] is None and b["tier"] == SR.TIER_EXTREME and b["extreme"] is not None


def test_NEGATIVE_window_even_at_the_un_rebased_2317x_spread_DKI_as_captured():
    m = _n("DKI")["massive_float"]
    fl = _n("DKI")["block"]["float_shares"]
    assert SCK.spread_words(SCK.rel_of(fl, m["free_float"])) == "2,317× apart"      # what a blind compare would say
    b = _blk("DKI", _with("DKI"))
    assert _sc(b)["state"] == "window" and "2,317" not in b["title"] and "sources disagree" not in b["chip"]
    assert BM._rb(m["free_float"], m["effective_date"], b["float_asof"], []) == m["free_float"]   # un-rebased


@pytest.mark.parametrize("since", [None, "junk", 5, True])
def test_NEGATIVE_a_missing_or_junk_splits_since_is_window(since):
    d = _with("CHWY", splits=dict(_doc("CHWY")["splits"], since=since))
    b = _blk("CHWY", d)
    assert _sc(b)["state"] == "window" and _sc(b)["text"].endswith(" — not compared: the splits on file carry no "
                                                                   "start date.")
    assert SCK.FLAG_SOURCES not in _keys(b) and b["tier"] == SR.TIER_EXTREME


def test_NEGATIVE_a_float_dated_before_splits_since_is_window():
    """The second float inside the window, the float divided by before it."""
    fa = _n("NCPL")["block"]["float_asof"]
    since = BM.day_after(fa)
    d = _with("NCPL", mfloat=_mf("NCPL", as_of=BM.day_after(since)), splits=dict(_doc("NCPL")["splits"], since=since))
    b = _blk("NCPL", d)
    assert _sc(b)["state"] == "window"
    assert _sc(b)["text"].endswith("after the date of the float divided by.")


def test_SMX_rebased_across_the_splits_on_file_with_its_as_published_words():
    b = _blk("SMX", _with("SMX"))
    m = _n("SMX")["massive_float"]
    reb = BM._rb(m["free_float"], m["effective_date"], b["float_asof"], BM._rows(_doc("SMX")["splits"]["rows"]))
    assert reb == 319195 and m["free_float"] == 893747
    assert _sc(b)["state"] == "compared"
    assert "Massive 319,195 (as of 8/13; 893,747 as published, split-adjusted) = 60.7%" in _sc(b)["text"]
    other = b["basis"]["float_sources"][1]
    assert other["shares"] == reb and other["published"] == m["free_float"] and other["tier"] == SR.TIER_EXTREME
    assert b["chip"] == _n("SMX")["block"]["chip"] and SCK.FLAG_SOURCES not in _keys(b)


def test_GMEX_says_the_second_float_is_larger_than_the_shares_on_file():
    b = _blk("GMEX", _with("GMEX"))
    assert " — larger than the 752,439 shares outstanding on file" in b["title"]
    assert b["shares_outstanding"] == 752439 and _sc(b)["state"] == "contested"
    assert b["basis"]["extreme_contest"]["to"] == SR.TIER_EXTREME


def test_DKI_with_the_widened_splits_read_is_contested_at_46x():
    b = _blk("DKI", _dki_widened())
    ec = b["basis"]["extreme_contest"]
    assert _sc(b)["state"] == "contested" and ec["shares"] == 587276 and ec["pct"] == 5.14
    assert ec["from"] == SR.TIER_EXTREME and ec["to"] == SR.TIER_EXTREME and ec["mode"] == "flag"
    assert ec["as_of"] == _n("DKI")["massive_float"]["effective_date"] and ec["by"] == "any_dated"
    t = b["title"]
    assert ("Massive 587,276 (as of 10/20; 29,363,802 as published, split-adjusted) = 5.1% — larger than the 51,333 "
            "shares outstanding on file · 46× apart") in t
    assert SCK.rel_of(12671, 587276) == _sc(b)["rel"]


# ═════════════════════════════════════════════ the built default `flag`
def _built(sym):
    return _blk("DKI", _dki_widened()) if sym == "DKI+" else _blk(sym, _with(sym))


@pytest.mark.parametrize("sym", ["GMEX", "CHWY", "DKI+"])
def test_built_default_keeps_the_word_and_adds_the_warning(sym):
    base = sym.rstrip("+")
    b = _built(sym)
    before = _n(base)["block"]
    assert SCK.EXTREME_CONTEST == "flag"
    assert b["tier"] == SR.TIER_EXTREME == before["tier"]
    assert b["chip"] == before["chip"] + " · " + SCK.SHORT_SOURCES
    assert b["extreme"] is not None and b["extreme"]["short"].endswith(SCK.SHORT_SOURCES)
    assert b["extreme"]["text"] == b["chip"]
    assert b["basis"]["flags"][-1]["key"] == SCK.FLAG_SOURCES and _keys(b).count(SCK.FLAG_SOURCES) == 1
    assert b["basis"]["flags"][-1]["short"] == SCK.SHORT_SOURCES
    assert b["basis"]["flags"][:-1] == before["basis"]["flags"]
    rows = b["rows"]
    tier_row = _rows(b)["Tier"]
    assert tier_row.startswith(SR.TIER_TEXT % (SR.TIER_WORDS[SR.TIER_EXTREME], SR._range(SR.TIER_EXTREME)))
    assert "Tier: " + SR.TIER_TEXT % (SR.TIER_WORDS[SR.TIER_EXTREME], SR._range(SR.TIER_EXTREME)) in b["title"]
    assert _rows(b)["Float check"].endswith(SR.FLOAT_CONTESTED_NOTE)
    ks = [r["k"] for r in rows]
    assert ks.count(SCK.ROW_FLOAT_SOURCES) == 1
    assert ks[ks.index(BM.ROW_SHARE_COUNTS) + 1] == SCK.ROW_FLOAT_SOURCES
    assert ks == [r["k"] for r in before["rows"][:ks.index(SCK.ROW_FLOAT_SOURCES)]] + [SCK.ROW_FLOAT_SOURCES] + [
        r["k"] for r in before["rows"][ks.index(SCK.ROW_FLOAT_SOURCES):]]
    assert _rows(b)[SCK.ROW_FLOAT_SOURCES].startswith(SCK.SHORT_SOURCES + " — float: Yahoo ")
    assert _rows(b)[SCK.ROW_FLOAT_SOURCES].endswith(" Massive's float puts it under 20%, where EXTREME starts — the "
                                                    "word is not changed.")
    assert b["title"].count("sources disagree") == 1           # the flag text rides the title; no second sentence
    assert SCK.title_sentences(b) == []


def test_the_section_3_10_chips_exactly():
    assert _built("GMEX")["chip"] == "🩳 SI EXTREME 43.2% float · 0.1d · 11/13 · ✂️ split due 11/27 · ⚠️ sources disagree"
    assert _built("CHWY")["chip"] == "🩳 SI EXTREME 46.8% float · 3.9d · 11/13 · 📄 S-3ASR 9/14 · ⚠️ sources disagree"
    assert _built("DKI+")["chip"] == "🩳 SI EXTREME 238.2% float · <0.1d · 11/13 · ⚠️ sources disagree"
    assert _built("DKI")["chip"] == "🩳 SI EXTREME 238.2% float · <0.1d · 11/13"
    assert _built("BETR")["chip"] == "🩳 SI EXTREME 40.3% float · 6.5d · 11/13"


def test_FLAG_SOURCES_is_neither_the_filing_nor_the_split_key():
    assert SCK.FLAG_SOURCES not in (BM.FLAG_FILING, BM.FLAG_SPLIT, BM.FLAG_FLOAT_STALE, BM.FLAG_COUNT_STALE,
                                    BM.FLAG_COUNT_FELL, BM.FLAG_UNCHECKED, BM.FLAG_FLOAT_UPDATED)
    assert SCK.SHORT_SOURCES == BM.EMOJI_WARN + " sources disagree"


# ═════════════════════════════════════════════ hold / supported (his call #1 — built, not the default)
@pytest.mark.parametrize("sym", ["GMEX", "CHWY", "DKI+"])
def test_hold_stops_the_word_at_High(mode, sym):
    mode("hold")
    b = _built(sym)
    before = _n(sym.rstrip("+"))["block"]
    assert b["tier"] == SR.TIER_HIGH and b["extreme"] is None
    assert b["chip"] == before["chip"].replace("SI EXTREME ", "SI High ", 1) + " · " + SCK.SHORT_SOURCES
    pf = SR._pct_tier(b["pct_of_float"])
    assert "Tier: " + SR.TIER_HELD_BY_SOURCE_TEXT % ("High", pf, "EXTREME", SIC.SI_HIGH_PCT) in b["title"]
    assert b["basis"]["extreme_contest"]["to"] == SR.TIER_HIGH and b["basis"]["extreme_contest"]["mode"] == "hold"
    assert _rows(b)["Float check"].endswith(SR.FLOAT_CONTESTED_NOTE)
    assert b["basis"]["flags"][-1]["text"].endswith(" EXTREME is held at High: Massive's float puts it under 20%.")


def test_hold_chips_of_section_3_10(mode):
    mode("hold")
    assert _built("GMEX")["chip"] == "🩳 SI High 43.2% float · 0.1d · 11/13 · ✂️ split due 11/27 · ⚠️ sources disagree"
    assert _built("CHWY")["chip"] == "🩳 SI High 46.8% float · 3.9d · 11/13 · 📄 S-3ASR 9/14 · ⚠️ sources disagree"
    assert _built("DKI+")["chip"] == "🩳 SI High 238.2% float · <0.1d · 11/13 · ⚠️ sources disagree"


def test_supported_takes_the_second_floats_word(mode):
    mode("supported")
    g, d = _built("GMEX"), _built("DKI+")
    assert g["tier"] == SR.TIER_LOW and d["tier"] == SR.TIER_MODERATE
    assert g["chip"].startswith("🩳 SI Low 43.2% float") and d["chip"].startswith("🩳 SI Moderate 238.2% float")
    assert g["extreme"] is None and d["extreme"] is None
    assert g["basis"]["flags"][-1]["text"].endswith(" The word shown is the one Massive's float gives.")
    c = _built("CHWY")
    assert c["tier"] == SR.TIER_HIGH                         # 11.16% on the second float = High


# ═════════════════════════════════════════════ NCPL / AKAN — the neutral sentence, nothing on the chip
NCPL_BASE = ("float: Yahoo 4,387,760 (read 11/18) = 10.6% · Massive 4,246,497 (as of 8/14) = 10.9% · 3% apart. "
             "The % shown uses Yahoo's.")


def test_NCPL_both_floats_in_the_hover_and_the_panel_chip_unchanged():
    b = _blk("NCPL", _with("NCPL"))
    assert b["chip"] == _n("NCPL")["block"]["chip"] == "🩳 SI High 10.6% float · 0.2d · 11/13"
    assert _sc(b)["state"] == "compared" and _sc(b)["text"] == NCPL_BASE
    assert ("Float sources — " + NCPL_BASE) in b["title"]
    assert _rows(b)[SCK.ROW_FLOAT_SOURCES] == NCPL_BASE
    used, other = b["basis"]["float_sources"]
    assert used == {"key": "yahoo", "label": "Yahoo", "shares": 4387760, "published": 4387760, "as_of": "2026-11-18",
                    "date_kind": "read", "pct": 10.59, "tier": SR.TIER_HIGH, "used": True}
    assert other["key"] == "massive" and other["used"] is False and other["date_kind"] == "as_of"
    assert other["pct"] == 10.94 and other["tier"] == SR.TIER_HIGH


def test_AKAN_carries_the_filing_clause():
    b = _blk("AKAN", _with("AKAN"))
    assert b["chip"] == _n("AKAN")["block"]["chip"]
    assert _sc(b)["state"] == "compared"
    assert _sc(b)["text"].endswith(" Massive's count is dated before the 📄 F-1/A 11/20 on file.")
    assert "float: Yahoo 709,911 (read 11/20) = 22.6% · Massive 540,841 (as of 8/13) = 29.6%" in b["title"]


def test_the_filing_clause_after_both_dates_and_never_on_a_same_day():
    b = _blk("CHWY", _with("CHWY"))
    assert " Yahoo's count is dated before the 📄 S-3ASR 9/14 on file." in _sc(b)["text"]
    a = _blk("AVTX", _with("AVTX"))
    assert " Both counts are dated before the 📄 S-3ASR 11/5 on file." in _sc(a)["text"]
    n = _blk("NCPL", _with("NCPL"))
    assert "dated before the 📄" not in _sc(n)["text"]       # no filing on file


@pytest.mark.parametrize("sym", ["NCPL", "AKAN"])
def test_NEGATIVE_NCPL_AKAN_never_warn_on_the_chip(sym, mode):
    for m in SCK.EXTREME_CONTEST_MODES:
        mode(m)
        b = _blk(sym, _with(sym))
        assert "sources disagree" not in b["chip"] and SCK.FLAG_SOURCES not in _keys(b)
        assert b["basis"]["extreme_contest"] is None and b["chip"] == _n(sym)["block"]["chip"]


# ═════════════════════════════════════════════ controls — a genuine low float is not touched
def test_NEGATIVE_CLRO_shape_keeps_EXTREME_and_its_note_with_both_dates_under_1pct():
    b = _blk("CLRO", _clro_doc())
    plain = _plain("CLRO", _clro_doc())
    assert b["tier"] == SR.TIER_EXTREME and b["extreme"] == plain["extreme"] and b["chip"] == plain["chip"]
    assert b["chip"] == _n("CLRO")["block"]["chip"]
    assert SCK.FLAG_SOURCES not in _keys(b) and _sc(b)["state"] == "compared"
    assert ("float: Yahoo 888,130 (read 11/17) = 35.8% · Massive 886,631 (as of 8/25) = 35.8% · under 1% apart."
            in _sc(b)["text"])


def test_NEGATIVE_INLF_both_extreme_and_JZ_one_source_stay_EXTREME():
    i = _blk("INLF", _with("INLF"))
    assert _sc(i)["state"] == "compared" and i["tier"] == SR.TIER_EXTREME and i["extreme"] is not None
    assert i["chip"] == _n("INLF")["block"]["chip"] and SCK.FLAG_SOURCES not in _keys(i)
    assert i["basis"]["float_sources"][1]["tier"] == SR.TIER_EXTREME
    j = _blk("JZ", _with("JZ"))
    assert _sc(j)["state"] == "none" and j["tier"] == SR.TIER_EXTREME and j["extreme"] is not None
    assert j["chip"] == _n("JZ")["block"]["chip"]
    assert _sc(j)["text"].endswith(" · Massive: none on file — one source only.")


def test_NEGATIVE_two_counts_inside_SAME_VALUE_REL_print_both_dates_and_under_1pct():
    fl = _n("NCPL")["block"]["float_shares"]
    b = _blk("NCPL", _with("NCPL", mfloat=_mf("NCPL", shares=fl)))
    assert _sc(b)["rel"] == 0 and "(read 11/18)" in _sc(b)["text"] and "(as of 8/14)" in _sc(b)["text"]
    assert "under 1% apart" in _sc(b)["text"]
    assert not WORDING.search(_sc(b)["text"])


# ═════════════════════════════════════════════ rank(None) = -1 [C7]
def _gmex_zero():
    """GMEX-shape whose second % rounds to zero: the published float scaled from GMEX's own short count."""
    si = _n("GMEX")["block"]["si_shares"]
    return _with("GMEX", mfloat=_mf("GMEX", shares=si * 10 ** 6))


def test_NEGATIVE_a_second_pct_that_rounds_to_zero_is_contested_and_held_at_High(mode):
    b = _blk("GMEX", _gmex_zero())
    ec = b["basis"]["extreme_contest"]
    assert _sc(b)["state"] == "contested" and ec["pct"] == 0.0 and b["basis"]["float_sources"][1]["tier"] is None
    assert SCK.rank(None) == -1 and SCK.rank("junk") == -1 and SCK.rank(SR.TIER_LOW) == 0
    for m in ("hold", "supported"):
        mode(m)
        h = _blk("GMEX", _gmex_zero())
        assert h["basis"]["extreme_contest"]["to"] == SR.TIER_HIGH and h["tier"] == SR.TIER_HIGH, m


# ═════════════════════════════════════════════ the modes
@pytest.mark.parametrize("word", ["off", "OFF", "nonsense", None, 3])
def test_NEGATIVE_off_or_an_unknown_mode_changes_nothing_on_the_chip(mode, word):
    mode(word)
    for sym, doc in (("GMEX", _with("GMEX")), ("CHWY", _with("CHWY")), ("DKI", _dki_widened())):
        b = _blk(sym, doc)
        plain = _plain(sym, doc)
        assert b["chip"] == plain["chip"] and b["tier"] == plain["tier"] and b["extreme"] == plain["extreme"]
        assert SCK.FLAG_SOURCES not in _keys(b)
        assert _sc(b)["state"] == "contested" and b["basis"]["extreme_contest"]["mode"] == "off"
        assert ("Float sources — float: Yahoo " in b["title"]
                and b["title"].count(" Massive's float puts it under 20%, where EXTREME starts.") == 1)
    assert SCK.contest_mode() == "off"


def test_not_older_lets_only_a_second_float_dated_on_or_after_ours_contest(monkeypatch):
    monkeypatch.setattr(SCK, "EXTREME_CONTEST_BY", "not_older")
    g, c = _blk("GMEX", _with("GMEX")), _blk("CHWY", _with("CHWY"))
    assert _sc(g)["state"] == "compared" and SCK.FLAG_SOURCES not in _keys(g)
    assert _sc(c)["state"] == "contested" and c["basis"]["extreme_contest"]["by"] == "not_older"
    monkeypatch.setattr(SCK, "EXTREME_CONTEST_BY", "nonsense")
    assert SCK.contest_by() == "any_dated" and _sc(_blk("GMEX", _with("GMEX")))["state"] == "contested"


def test_CONTEST_MIN_REL_half_leaves_GENI_compared_and_CHWY_contested(monkeypatch):
    assert _sc(_blk("GENI", _with("GENI")))["state"] == "contested"         # built: any spread above rounding
    monkeypatch.setattr(SCK, "CONTEST_MIN_REL", 0.5)
    g = _blk("GENI", _with("GENI"))
    assert _sc(g)["state"] == "compared" and SCK.FLAG_SOURCES not in _keys(g) and "2% apart" in _sc(g)["text"]
    assert _sc(_blk("CHWY", _with("CHWY")))["state"] == "contested"
    for junk in (True, "0.5", float("nan")):
        monkeypatch.setattr(SCK, "CONTEST_MIN_REL", junk)
        assert SCK.min_rel() == SCK.SAME_VALUE_REL == BM.CARRY_REL_TOL


# ═════════════════════════════════════════════ never contested
def test_NEGATIVE_stale_refused_adr_unheld_split_day_failed_are_never_contested():
    late = date(2027, 1, 15)
    s = _blk("CHWY", _with("CHWY"), late)
    assert s["status"] == "stale" and s["tier"] is None and _sc(s)["state"] == "compared"
    g = _n("GMEX")["massive_float"]                          # dated before both GMEX's float and its settlement
    cases = {
        "no_float": ("SMTK", _with("SMTK")),
        "units": ("CHWY", _with("CHWY", ref=dict(_doc("CHWY")["ref"], type="ADRC"))),
        "no_splits": ("CHWY", _with("CHWY", splits={"status": "failed", "error": "http_500"})),
        "split_day": ("GMEX", _with("GMEX", splits=dict(_doc("GMEX")["splits"], rows=_doc("GMEX")["splits"]["rows"] + [
            {"execution_date": g["effective_date"], "split_from": 1, "split_to": 2}]))),
        "unread": ("CHWY", _with("CHWY", mfloat=_mf("CHWY", status="failed", shares=None, as_of=None))),
    }
    for st, (sym, d) in cases.items():
        b = _blk(sym, d)
        assert _sc(b)["state"] == st, st
        assert b["basis"]["extreme_contest"] is None and SCK.FLAG_SOURCES not in _keys(b), st


@pytest.mark.parametrize("leaf", [{"shares": True}, {"shares": float("nan")}, {"shares": "4246497"}, {"shares": -5},
                                  {"shares": 0}, {"as_of": "junk"}, {"as_of": None}, {"as_of": 20260814},
                                  {"status": None}, {"status": 7}, {"status": "weird"}])
def test_NEGATIVE_junk_mfloat_leaves_are_unread_never_a_raise_never_NaN(leaf):
    b = _blk("CHWY", _with("CHWY", mfloat=_mf("CHWY", **leaf)))
    assert _sc(b)["state"] == "unread" and b["basis"]["extreme_contest"] is None
    assert b["chip"] == _n("CHWY")["block"]["chip"]
    json.dumps(b, allow_nan=False)


@pytest.mark.parametrize("bad", ["x", 5, [], None, {"mfloat": "x"}, {"mfloat": None}])
def test_NEGATIVE_compare_is_None_without_a_dict_mfloat(bad):
    assert SCK.compare(_n("CHWY")["block"], bad) is None
    assert SCK.compare(None, _with("CHWY")) is None


def test_NEGATIVE_a_raising_compare_leaves_the_no_mfloat_block_and_logs_one_line(monkeypatch, caplog):
    def boom(*a, **k):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(SCK, "compare", boom)
    with caplog.at_level(logging.WARNING, logger="short_interest.read"):
        b = _blk("CHWY", _with("CHWY"))
    assert b == _n("CHWY")["block"]
    lines = [r.getMessage() for r in caplog.records if "source check" in r.getMessage()]
    assert lines == ["short_interest.read: source check CHWY failed: RuntimeError"]


def test_NEGATIVE_a_raising_apply_is_fenced_too(monkeypatch):
    monkeypatch.setattr(SCK, "apply", lambda *a, **k: 1 / 0)
    assert _blk("GMEX", _with("GMEX")) == _n("GMEX")["block"]


def test_NEGATIVE_apply_ignores_junk_and_never_mutates_the_verdict_flags():
    b = copy.deepcopy(_n("CHWY")["block"])
    for junk in (None, "x", {"state": "nonsense"}, {}):
        SCK.apply(b, junk)
    assert b == _n("CHWY")["block"]
    nb = copy.deepcopy(b)
    del nb["basis"]
    SCK.apply(nb, SCK.compare(b, _with("CHWY")))
    assert "basis" not in nb
    held = b["basis"]["flags"]
    SCK.apply(b, SCK.compare(b, _with("CHWY")))
    assert held == _n("CHWY")["block"]["basis"]["flags"] and b["basis"]["flags"] is not held


def test_NEGATIVE_a_contested_name_is_never_listed_lower_by_high_si(mode):
    from chart_maps.gajjala import high_si as HS
    for sym, doc in (("GMEX", _with("GMEX")), ("CHWY", _with("CHWY")), ("DKI", _dki_widened())):
        plain = _plain(sym, doc)
        fr = {"shares": plain["float_shares"]}
        was = HS.classify(plain, fr)
        for m in ("off", "flag", "hold"):
            mode(m)
            now = HS.classify(_blk(sym, doc), fr)
            assert now["listed"] is was["listed"] and now["reason"] == was["reason"], (sym, m)


# ═════════════════════════════════════════════ every served string, every mode
def test_every_new_string_in_all_four_modes_passes_the_forecast_and_wording_checks(mode):
    for m in SCK.EXTREME_CONTEST_MODES:
        mode(m)
        docs = [(s, _with(s)) for s in NAMES if _doc(s) is not None] + [("DKI", _dki_widened()),
                                                                        ("CLRO", _clro_doc()), ("GMEX", _gmex_zero())]
        new = [SR.TIER_HELD_BY_SOURCE_TEXT, SR.FLOAT_CONTESTED_NOTE, SCK.rules_sentence()]
        for sym, d in docs:
            b = _blk(sym, d)
            for t in _strings(b):
                assert not FORBIDDEN.search(t), (m, sym, t)
                assert "band" not in t.lower(), (m, sym, t)
            new.append(_sc(b)["text"])
            new += [f["text"] for f in b["basis"]["flags"] if f["key"] == SCK.FLAG_SOURCES]
            new += SCK.title_sentences(b) + [r["v"] for r in SCK.rows(b)]
        for t in new:
            assert not WORDING.search(t), (m, t)
            assert not FORBIDDEN.search(t) and "band" not in t.lower(), (m, t)
            assert "confirmed" not in t, (m, t)


# ═════════════════════════════════════════════ si_map(basis_over=) [C2]
def _map_db(syms, docs):
    return FakeDB({SIC.SI_COLL: FakeColl([dict(_rec(s), _id=s) for s in syms], name=SIC.SI_COLL),
                   SB.SB_COLL: FakeColl(docs, name=SB.SB_COLL)})


def test_si_map_lays_the_overlay_over_the_stored_doc_in_memory_only():
    stored = _doc("GMEX")
    db = _map_db(["GMEX", "NCPL"], [stored])
    before = copy.deepcopy(db.colls[SB.SB_COLL].docs)
    over = {"gmex": {"mfloat": _mf("GMEX")}, "NCPL": {"mfloat": _mf("NCPL")}}
    m = SR.si_map(["GMEX", "NCPL"], db=db, today=TODAY, basis_over=over)
    assert _sc(m["GMEX"])["state"] == "contested" and m["GMEX"]["chip"].endswith(SCK.SHORT_SOURCES)
    assert "basis" not in m["NCPL"]                            # no stored doc → no overlay
    assert db.colls[SB.SB_COLL].docs == before and db.colls[SB.SB_COLL].writes == []
    assert "mfloat" not in db.colls[SB.SB_COLL].docs["GMEX"]


def test_NEGATIVE_si_map_the_loaded_doc_object_is_not_mutated(monkeypatch):
    held = _doc("CHWY")
    snap = copy.deepcopy(held)
    monkeypatch.setattr(SR, "_basis_docs", lambda syms, db=None: {"CHWY": held})
    db = _map_db(["CHWY"], [])
    m = SR.si_map(["CHWY"], db=db, today=TODAY, basis_over={"CHWY": {"mfloat": _mf("CHWY")}})
    assert _sc(m["CHWY"])["state"] == "contested" and held == snap


@pytest.mark.parametrize("over", [None, {}, "x", {"GMEX": None}, {"GMEX": "x"}, {"GMEX": {}}])
def test_NEGATIVE_si_map_with_no_overlay_is_byte_identical(over):
    db = _map_db(["GMEX", "CHWY"], [_doc("GMEX"), _doc("CHWY")])
    plain = SR.si_map(["GMEX", "CHWY"], db=db, today=TODAY)
    got = SR.si_map(["GMEX", "CHWY"], db=db, today=TODAY, basis_over=over)
    assert json.dumps(got, ensure_ascii=False, sort_keys=True) == json.dumps(plain, ensure_ascii=False, sort_keys=True)
    assert got["GMEX"] == _n("GMEX")["block"] and got["CHWY"] == _n("CHWY")["block"]


def test_NEGATIVE_every_share_basis_fixture_name_serves_no_source_keys(monkeypatch):
    """tests/fixtures/si_share_basis_2026_11_24.json through the integration harness (real captures, fake HTTP):
    no stored doc gains `mfloat`, no block gains a SOURCE_KEY or the flag, and the blocks are byte-identical with the
    source check switched off entirely."""
    import massive_keys
    from sepa import prices
    from tests import test_si_basis_integration_2026_11_24 as IT
    monkeypatch.setattr(massive_keys, "stocks_key", lambda *a, **k: IT.KEY)
    monkeypatch.setattr(SB, "_sec_wait", lambda *a, **k: None)
    monkeypatch.setitem(SB._sec_stop, "until", None)
    monkeypatch.setattr(SB, "_http", None)
    holder = {}
    monkeypatch.setattr(prices, "_http", lambda *a, **k: holder["http"])
    monkeypatch.setattr(BM, "FLOAT_STALE_WHEN", "added_exceeds_float")
    db, _http, _old, new, _docs = IT._run(holder=holder)
    assert set(new) == set(IT.NAMES) and len(new) == 12
    for sym, b in new.items():
        assert "mfloat" not in db[SB.SB_COLL].docs[sym]
        assert not set(SR.SOURCE_KEYS) & set(b.get("basis") or {}), sym
        assert SCK.FLAG_SOURCES not in _keys(b) and SCK.ROW_FLOAT_SOURCES not in [r["k"] for r in b["rows"]]
    monkeypatch.setattr(SCK, "compare", lambda *a, **k: None)
    off = IT.blocks(db)
    assert json.dumps(off, ensure_ascii=False, sort_keys=True) == json.dumps(new, ensure_ascii=False, sort_keys=True)


def test_SOURCE_KEYS_ride_beside_BASIS_KEYS_never_inside():
    assert SR.SOURCE_KEYS == SCK.SOURCE_KEYS == ("float_sources", "sources_compared", "extreme_contest")
    assert not set(SR.SOURCE_KEYS) & set(SR.BASIS_KEYS) and len(SR.BASIS_KEYS) == 15
    b = _blk("NCPL", _with("NCPL"))
    assert set(SR.SOURCE_KEYS) <= set(b["basis"])


# ═════════════════════════════════════════════ the cut table on the 693 probe rows [C2]
def _adapt(r):
    """The test adapter of spec §4.1: state = window when md < since, else compared; tier = t; other.tier = tm."""
    return {"symbol": r["s"], "state": "window" if r["md"] < r["since"] else "compared", "tier": r["t"],
            "other": {"tier": r["tm"]}, "float_rel": r["rel"]}


def test_cut_table_on_the_probe_rows_is_pinned():
    t = SCK.cut_table([_adapt(r) for r in PROBE["rows"]])
    assert (t["n"], t["compared"], t["window"], t["not_compared"]) == (693, 569, 124, 0)
    assert [c["cut"] for c in t["cuts"]] == [None, 0.10, 0.25, 0.50]
    assert [c["differ"] for c in t["cuts"]] == [564, 148, 58, 24]
    assert [c["contested"] for c in t["cuts"]] == [11, 8, 4, 2]
    assert t["cuts"][0]["names"] == ["AVBP", "AVTX", "CHWY", "GENI", "GMEX", "LRMR", "NKTR", "PRTA", "TSHA", "VERA",
                                     "VOR"]
    assert t["cuts"][1]["names"] == ["AVTX", "CHWY", "GMEX", "NKTR", "PRTA", "TSHA", "VERA", "VOR"]
    assert t["cuts"][2]["names"] == ["AVTX", "CHWY", "GMEX", "TSHA"]
    assert t["cuts"][3]["names"] == ["CHWY", "GMEX"]
    assert SCK.EXAMPLE_CUTS == (0.10, 0.25, 0.50)


def test_NEGATIVE_cut_table_counts_no_window_or_junk_row():
    rows = [_adapt(r) for r in PROBE["rows"]]
    win = [r for r in rows if r["state"] == "window"]
    assert any(r["symbol"] == "DKI" for r in win) and any(r["symbol"] == "CWH" for r in win)
    t = SCK.cut_table(win + [None, "x", {"state": "unread", "float_rel": 9.0, "tier": "extreme"}])
    assert t["compared"] == 0 and all(c["differ"] == 0 and c["names"] == [] for c in t["cuts"])
    assert t["window"] == 124 and t["not_compared"] == 1 and t["n"] == 125
    assert SCK.cut_table(None)["n"] == 0


# ═════════════════════════════════════════════ the audit row (source_audit reads it)
def test_audit_row_names_which_float_and_count_the_chip_used():
    b = _blk("GMEX", _with("GMEX"))
    r = SCK.audit_row(b, _with("GMEX"), groups=["listed"])
    assert r["state"] == "contested" and r["contested"] is True and r["held"] is False and r["differ"] is True
    assert r["used"]["shares"] == 361428 and r["other"]["published"] == _n("GMEX")["massive_float"]["free_float"]
    assert r["count_used"] == {"shares": 752439, "as_of": b["shares_asof"], "source": b["shares_source"]}
    assert r["groups"] == ["listed"] and r["chip"] == b["chip"] and r["counts"] == b["basis"]["share_counts"]
    assert r["float_rel"] == _sc(b)["rel"] and r["checked_at"] == b["basis"]["checked_at"]
    n = SCK.audit_row(_blk("NCPL", _with("NCPL")), _with("NCPL"))
    assert n["state"] == "compared" and n["differ"] is True and n["contested"] is False
    dated = [c["shares"] for c in n["counts"] if c["key"] in ("record", "yahoo", "sec_cover") and c.get("shares")]
    assert len(dated) >= 2 and n["count_rel"] == SCK.rel_of(max(dated), min(dated))


def test_NEGATIVE_audit_row_no_si_and_unread():
    nr = SCK.audit_row(None, _with("GMEX"))
    assert nr["state"] == SCK.STATE_NO_SI and nr["si_shares"] is None and nr["used"] is None and nr["counts"] == []
    assert SCK.audit_row({"status": "no_record", "symbol": "X"}, None)["state"] == SCK.STATE_NO_SI
    u = SCK.audit_row(_n("GMEX")["block"], None)
    assert u["state"] == "unread" and u["other"] is None and u["differ"] is False


# ═════════════════════════════════════════════ spread words + rel_of
def test_spread_words_and_rel_of():
    assert SCK.spread_words(0) == "under 1% apart" and SCK.spread_words(0.004) == "under 1% apart"
    assert SCK.spread_words(0.0333) == "3% apart" and SCK.spread_words(1.5) == "2.5× apart"
    assert SCK.spread_words(45.35) == "46× apart" and SCK.spread_words(2316.4) == "2,317× apart"
    assert SCK.rel_of(4, 5) == SCK.rel_of(5, 4) == 0.25
    for a, b in ((0, 5), (None, 5), (5, -1), (True, 5), ("x", 5)):
        assert SCK.rel_of(a, b) is None
    assert SCK.spread_words(None) == "" and SCK.spread_words(float("nan")) == ""


def test_source_check_holds_one_division_and_no_io():
    tree = ast.parse(SRC)
    divs = [n for n in ast.walk(tree) if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Div, ast.FloorDiv))]
    assert len(divs) == 1 and _fn(BACKEND / "short_interest" / "source_check.py", "rel_of") is not None
    inside = [n for n in ast.walk(_fn(BACKEND / "short_interest" / "source_check.py", "rel_of"))
              if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)]
    assert [(n.lineno, n.col_offset) for n in inside] == [(n.lineno, n.col_offset) for n in divs]
    assert not re.search(r"^\s*(import|from)\s+(requests|pymongo|urllib|short_interest\.share_basis|"
                         r"short_interest import share_basis|datetime)\b", SRC, re.M)
    assert _calls(tree, "pct_of") >= 1


# ═════════════════════════════════════════════ ℹ️ rules
def test_rules_sentence_ends_with_the_source_sentence_and_names_the_warning():
    s = BM.rules_sentence()
    assert s.endswith(" " + SCK.rules_sentence())
    assert SCK.rules_sentence() == ("A second dated float (Massive's free float) is read beside Yahoo's and both are "
                                    "in the hover with their dates; when it puts an EXTREME name under the cut the "
                                    "chip adds '⚠️ sources disagree' and the word stays.")
    assert SCK.SHORT_SOURCES in s
    sec = SR.rules_section()
    assert len(sec["picks"]) == 8 and sec["picks"][1].endswith(BM.rules_sentence())
    assert not [p for p in sec["picks"] if FORBIDDEN.search(p)]


def test_rules_sentence_follows_the_mode(mode):
    mode("hold")
    assert SCK.rules_sentence().endswith(" and the word stops at High.")
    mode("supported")
    assert SCK.rules_sentence().endswith(" and the word is the second float's.")
    mode("off")
    assert SCK.rules_sentence().endswith("both are in the hover with their dates.")
    assert SCK.SHORT_SOURCES not in SCK.rules_sentence()


def test_NEGATIVE_a_raising_source_sentence_keeps_the_old_one(monkeypatch):
    monkeypatch.setattr(SCK, "rules_sentence", lambda: 1 / 0)
    s = BM.rules_sentence()
    assert s.endswith("already counted.") and "sources disagree" not in s


# ═════════════════════════════════════════════ the doc's references and its re-run block (refix 2026-11-27)
DOC = BACKEND.parent / "docs" / "short_interest" / "float_accuracy_guard_2026_11_26.md"
_MD_REF = re.compile(r"`([A-Za-z0-9_./-]+\.md)`")
_MOD_REF = re.compile(r"python -m ([A-Za-z_][A-Za-z0-9_.]*)")
_RERUN = re.compile(r'\.venv/bin/python -B -c "([^"\n]+)"')
SCRATCH = "floatguard/"


def _dangling(text):
    """Every `*.md` the text names that is not under docs/short_interest/ (or the repo), and every `python -m` module
    that has no file under backend/."""
    import importlib.util
    out = []
    for ref in _MD_REF.findall(text):
        if ref.startswith(SCRATCH):                          # the session scratch folder (the spec), not the repo
            continue
        if not ((DOC.parent / ref).is_file() or (BACKEND.parent / ref).is_file()):
            out.append(ref)
    for mod in _MOD_REF.findall(text):
        p = BACKEND.joinpath(*mod.split("."))
        if p.with_suffix(".py").is_file() or (p / "__main__.py").is_file():
            continue
        if not (BACKEND / mod.split(".")[0]).exists() and importlib.util.find_spec(mod) is not None:
            continue                                         # an installed tool (pytest), not a repo module
        out.append(mod)
    return out


def test_the_doc_names_no_page_and_no_module_that_does_not_exist():
    text = DOC.read_text(encoding="utf-8")
    assert _MD_REF.findall(text), "the checker must see the doc's page names"
    assert _dangling(text) == []


def test_NEGATIVE_the_reference_checker_catches_a_missing_page_and_module():
    # 2026-11-27: source_audit_2026_11_26.md and short_interest.source_audit landed (package be-audit), so they are
    # no longer dangling; the planted page and module below are the ones that must never exist.
    planted = ("see `nope_page_2026_11_26.md`; `massive_float_source_2026_11_26.md` · "
               "python -m short_interest.source_check · python -m pytest · "
               "`floatguard/spec.md` · python -m short_interest.nope_2026")
    assert _dangling(planted) == ["nope_page_2026_11_26.md", "short_interest.nope_2026"]


def test_the_docs_re_run_block_prints_the_pinned_counts(capsys):
    blocks = _RERUN.findall(DOC.read_text(encoding="utf-8"))
    assert len(blocks) == 1
    import os
    cwd = os.getcwd()
    try:
        os.chdir(BACKEND)
        exec(compile(blocks[0], "<doc re-run>", "exec"), {})
    finally:
        os.chdir(cwd)
    assert capsys.readouterr().out.splitlines() == [
        "693 569 124",
        "None 564 11 AVBP AVTX CHWY GENI GMEX LRMR NKTR PRTA TSHA VERA VOR",
        "0.1 148 8 AVTX CHWY GMEX NKTR PRTA TSHA VERA VOR",
        "0.25 58 4 AVTX CHWY GMEX TSHA",
        "0.5 24 2 CHWY GMEX",
    ]


def test_NEGATIVE_the_re_run_block_reads_the_frozen_fixture_and_writes_nothing():
    (block,) = _RERUN.findall(DOC.read_text(encoding="utf-8"))
    assert "tests/fixtures/si_float_probe_rows_2026_11_26.json" in block and "SCK.cut_table(" in block
    assert not re.search(r"open\([^)]*['\"][wa]['\"]|\.write|requests|http|pymongo|get_db", block)
