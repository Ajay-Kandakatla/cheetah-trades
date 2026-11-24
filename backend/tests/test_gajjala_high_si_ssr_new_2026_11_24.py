"""⛔ SSR "new today" list on the 🩳 High SI sub — high_si.ssr_new_block (2026-11-24, SPEC ssrlist §3.3, WP be-block).

Ajay 2026-11-24: "What are the SSR stocks today" · "Can you add it to short interest tab" · "The new ones".

Built against a STUB engine answer shaped per ssr.NEW_KEYS / NEW_ROW_KEYS (the engine package lands separately; the
REAL engine → REAL block pin is the main session's integration test). Negatives are named test_NEGATIVE_*.
"""
from __future__ import annotations

import ast
import inspect
import json
import re
from pathlib import Path

import pytest

from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala import tab as GT
from short_interest import read as SR
from tests.test_gajjala_high_si_2026_11_23 import (EXTR, HIGH, NOW, S, blk, board, rdoc, si,  # noqa: F401 — fixture
                                                   store)
from tests.test_gajjala_watch_hook_2026_11_15 import _watch_imports_and_wc_reads

B_WORD = re.compile("b" + "ounc", re.I)
HI, EX = SR.TIER_WORDS[SR.TIER_HIGH], SR.TIER_WORDS[SR.TIER_EXTREME]
# ssr.NEW_KEYS as frozen in the spec (§3.2) — read off the engine once it has landed
SPEC_NEW_KEYS = ("kind", "status", "day", "day_words", "prior_day", "is_today", "market_day_today", "title", "rows",
                 "n", "n_official", "n_computed", "n_retriggered", "sources_text", "retriggered_text", "withheld",
                 "withheld_text", "faults", "faults_text", "through", "off_from", "half_day", "window_text", "computed",
                 "sources", "corp_checked", "asof_text", "status_text", "partial_text", "empty_text", "fault_text",
                 "note_text", "rule_text")
SPEC_NEW_ROW_KEYS = ("symbol", "source", "exchange", "time_basis", "at_et", "at_text", "drop_pct", "drop_text",
                     "source_text", "retriggered", "mark_text")


def _ssr_mod():
    from short_interest import ssr as SSR
    return SSR


NEW_KEYS = getattr(_ssr_mod(), "NEW_KEYS", SPEC_NEW_KEYS)
NEW_ROW_KEYS = getattr(_ssr_mod(), "NEW_ROW_KEYS", SPEC_NEW_ROW_KEYS)


# ── builders ────────────────────────────────────────────────────────────────────────────────────────────────────
def erow(sym, **over):
    r = {"symbol": sym, "source": "computed", "exchange": None, "time_basis": "minute_bar", "at_et": "10:00",
         "at_text": "10:00 ET", "drop_pct": 12.3, "drop_text": "12.3%", "source_text": "computed",
         "retriggered": False, "mark_text": None}
    r.update(over)
    return r


def eng(rows=(), status="ok", **over):
    d = {k: None for k in NEW_KEYS}
    d.update(kind=HS.SSR_NEW_KIND, status=status, title="served title", window_text="served window",
             asof_text="served asof", rule_text="served rule", note_text="served note",
             sources_text="served sources", retriggered_text="served retriggered", rows=list(rows), n=len(rows))
    d.update(over)
    return d


EXA = blk("AAA", 600000, 2000000, 3000000)          # 30 % of float, confirmed — EXTREME
HIA = blk("BBB", 300000, 2000000)                   # 15 % — High
LOC = blk("CCC", 10000, 2000000)                    # 0.5 % — Low
SOD = blk("DDD", 300000, None, 2000000)             # shares-out basis — no tier
HIE = blk("EEE", 300000, 2000000)                   # High
EXF = blk("FFF", 600000, 2000000, 3000000)          # EXTREME 30 %
EXG = blk("FFG", 800000, 2000000, 3000000)          # EXTREME 40 % — sorts before FFF
LOG = blk("GGG", 10000, 2000000)                    # Low
CNT = blk("III", 153800, None)                      # count only — no tier
BLOCKS = {"AAA": EXA, "BBB": HIA, "CCC": LOC, "DDD": SOD, "EEE": HIE, "FFF": EXF, "FFG": EXG, "GGG": LOG, "III": CNT}
LISTED = {"AAA": {}, "BBB": {}, "CCC": {}, "DDD": {}}
SYMS = ["III", "HHH", "GGG", "FFG", "FFF", "EEE", "DDD", "CCC", "BBB", "AAA"]           # deliberately unsorted


def build(rows=None, *, ans=None, listed=LISTED, blocks=BLOCKS, si_calls=None, **kw):
    rows = [erow(s) for s in SYMS] if rows is None else rows
    answer = ans if ans is not None else eng(rows)

    def si_read(syms):
        if si_calls is not None:
            si_calls.append(list(syms))
        if isinstance(blocks, Exception):
            raise blocks
        return blocks
    return HS.ssr_new_block(listed, session=S, now=NOW, tf="5m", ssr_read=lambda s, n: answer, si_read=si_read, **kw)


def groups(b):
    return {g["key"]: g for g in b["groups"]}


def syms_of(g):
    return [r["symbol"] for r in g["rows"]]


def _texts(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _texts(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _texts(v)


def _keys_ok(b):
    assert tuple(b) == HS.SSR_NEW_BLOCK_KEYS
    for g in b["groups"]:
        assert tuple(g) == HS.SSR_NEW_GROUP_KEYS
        for r in g["rows"]:
            assert tuple(r) == HS.SSR_NEW_ROW_KEYS


def test_the_fixture_shapes_are_the_house_reads():
    assert EXA["tier"] == SR.TIER_EXTREME and EXF["tier"] == SR.TIER_EXTREME and EXG["tier"] == SR.TIER_EXTREME
    assert HIA["tier"] == SR.TIER_HIGH and LOC["tier"] == SR.TIER_LOW and LOG["tier"] == SR.TIER_LOW
    assert SOD["tier"] is None and SOD["headline_basis"] == "shares_out" and "shs out" in SOD["chip"]
    assert CNT["tier"] is None and CNT["chip"].startswith("🩳 SI ") and " sh · " in CNT["chip"]
    assert HS.ssr_tiered(EXA) and not HS.ssr_tiered(SOD) and not HS.ssr_tiered(None) and not HS.ssr_tiered("x")


# ── 1 · the four folds ──────────────────────────────────────────────────────────────────────────────────────────
def test_four_folds_order_summaries_counts_and_the_untiered_tail():
    b = build()
    _keys_ok(b)
    assert [g["key"] for g in b["groups"]] == list(HS.SSR_NEW_GROUPS)
    g = groups(b)
    assert syms_of(g["list_high"]) == ["AAA", "BBB"]                         # EXTREME, then High
    assert syms_of(g["list_other"]) == ["CCC", "DDD"]                        # Low, then not tiered
    assert syms_of(g["high"]) == ["FFG", "FFF", "EEE"]                       # EXTREME 40 %, EXTREME 30 %, High
    assert syms_of(g["rest"]) == ["GGG", "HHH", "III"]                       # Low, then not tiered A→Z
    assert g["list_high"]["summary"] == "🚩 on his list · %s or %s short interest — 2: AAA BBB" % (HI, EX)
    assert g["list_other"]["summary"] == "🚩 on his list · short interest under %s or not tiered — 2 (1 not tiered)" % HI
    assert g["high"]["summary"] == "🩳 %s or %s short interest · not on his list — 3" % (HI, EX)
    assert g["rest"]["summary"] == "every other name — 3 (2 not tiered)"
    assert "not tiered" not in g["high"]["summary"] and "not tiered)" not in g["list_high"]["summary"]
    assert [x["count"] for x in b["groups"]] == [2, 2, 3, 3] and all(x["open"] is False for x in b["groups"])
    assert b["counts_text"] == ("10 names · 4 on his 🚩 list (2 with %s or %s short interest) · 3 more with %s or %s "
                                "short interest · 3 others · served sources · served retriggered" % (HI, EX, HI, EX))
    assert b["n"] == 10 and b["n_untiered"] == 3
    assert b["tier_note"] == HS.SSR_NEW_TIER_NOTE.format(U=3, n=10, hi=HI, ex=EX)
    assert b["tier_note"].startswith("3 of the 10 names are not tiered")
    assert b["order_note"] == HS.SSR_NEW_ORDER_NOTE.format(hi=HI, ex=EX)
    assert b["rule_label"] == HS.SSR_NEW_RULE_LABEL and b["si_note"] is None and b["list_note"] is None
    for k in ("title", "window_text", "asof_text", "rule_text", "note_text"):
        assert b[k] == "served " + k.split("_")[0], k
    row = g["list_high"]["rows"][0]
    assert row["at_text"] == "10:00 ET" and row["drop_text"] == "12.3%" and row["source_text"] == "computed"
    assert row["href"] == GT.chart_href("AAA", "5m", None) and row["mark_text"] is None


def test_engine_texts_ride_as_served():
    b = build(ans=eng([erow("AAA", mark_text="also triggered Mon 11/23")], partial_text="served partial",
                      withheld_text="served withheld", faults_text="served faults"))
    assert b["partial_text"] == "served partial" and b["withheld_text"] == "served withheld"
    assert b["faults_text"] == "served faults" and b["fault_text"] is None and b["empty_text"] is None
    assert groups(b)["list_high"]["rows"][0]["mark_text"] == "also triggered Mon 11/23"


# ── 2 · open flag ───────────────────────────────────────────────────────────────────────────────────────────────
def test_open_flips_one_fold_and_nothing_else(monkeypatch):
    base = build()
    monkeypatch.setattr(HS, "SSR_NEW_OPEN", ("list_high",))
    flip = build()
    assert [g["open"] for g in flip["groups"]] == [True, False, False, False]
    for g in flip["groups"]:
        g["open"] = False
    assert flip == base


# ── 3 · the list fold ───────────────────────────────────────────────────────────────────────────────────────────
def test_dot_and_dash_are_one_ticker_on_the_list():
    b = build([erow("BRK.B")], listed={"BRK-B": {}}, blocks={"BRK.B": HIA})
    assert syms_of(groups(b)["list_high"]) == ["BRK.B"]
    b = build([erow("BRK.B")], listed={"BRK-B": {}}, blocks={})
    assert syms_of(groups(b)["list_other"]) == ["BRK.B"]


def test_NEGATIVE_a_name_not_on_the_list_is_never_in_a_list_fold():
    b = build([erow("ZZZ")], listed={"ZZY": {}}, blocks={"ZZZ": HIA})
    assert [g["key"] for g in b["groups"]] == ["high"]


# ── 4 / 4b · the 🩳 text and the tier ───────────────────────────────────────────────────────────────────────────
def test_si_text_is_the_house_chip_for_every_basis():
    for bk in (HIA, SOD, CNT):
        assert HS.ssr_si_text(bk) == bk["chip"]
    b = build([erow("BBB"), erow("DDD"), erow("III")], listed={"ZZZ": {}})
    texts = {r["symbol"]: r["si_text"] for g in b["groups"] for r in g["rows"]}
    assert texts == {"BBB": HIA["chip"], "DDD": SOD["chip"], "III": CNT["chip"]}


def test_NEGATIVE_si_text_none_without_a_chip():
    nr = SR.si_block({"symbol": "NRX", "fetched_at": 1.7e9}, S)
    assert nr["status"] == "no_record"
    for bk in (None, nr, dict(HIA, chip=None), dict(HIA, chip=""), dict(HIA, chip="   "), dict(HIA, chip=7), "x", 7):
        assert HS.ssr_si_text(bk) is None, bk
    b = build([erow("HHH")], blocks={})
    assert groups(b)["rest"]["rows"][0]["si_text"] is None


def test_NEGATIVE_a_nan_pct_moves_only_the_order_never_a_text():
    nan_hi = dict(HIE, pct_of_float=float("nan"))
    blocks = {"EEE": nan_hi, "FFH": blk("FFH", 200000, 2000000)}           # 10 % — High, a real %
    assert blocks["FFH"]["tier"] == SR.TIER_HIGH
    b = build([erow("EEE"), erow("FFH")], listed={"ZZZ": {}}, blocks=blocks)
    g = groups(b)["high"]
    assert syms_of(g) == ["FFH", "EEE"]                                       # no finite % → last inside High
    assert g["rows"][1]["si_text"] == HIE["chip"]
    assert HS.ssr_new_rank(nan_hi) == (-SR.TIER_ORDER.index(SR.TIER_HIGH), 1, 0)


def test_NEGATIVE_stale_and_count_only_reads_are_never_high_and_sort_after_the_tiered():
    stale = blk("STL", 1000000, 2750000, 12345679, settle="2026-09-15")
    assert stale["status"] == "stale" and stale["tier"] is None and stale.get("pct_of_float")
    blocks = {"STL": stale, "III": CNT, "CCC": LOC, "GGG": LOG}
    b = build([erow("STL"), erow("III"), erow("CCC"), erow("GGG")], listed={"STL": {}, "CCC": {}}, blocks=blocks)
    g = groups(b)
    assert set(g) == {"list_other", "rest"}
    assert syms_of(g["list_other"]) == ["CCC", "STL"] and syms_of(g["rest"]) == ["GGG", "III"]
    assert b["n_untiered"] == 2 and "(1 not tiered)" in g["list_other"]["summary"]
    assert "(1 not tiered)" in g["rest"]["summary"]
    assert g["list_other"]["rows"][1]["si_text"] == stale["chip"]


def test_NEGATIVE_every_name_tiered_serves_no_tier_note_and_no_zero_tail():
    b = build([erow("AAA"), erow("CCC"), erow("GGG"), erow("EEE")])
    assert b["tier_note"] is None and b["n_untiered"] == 0
    assert not any("not tiered)" in g["summary"] for g in b["groups"])


# ── 5 / 6 / 7 · faults and other statuses ───────────────────────────────────────────────────────────────────────
def _boom(*_a, **_k):
    raise RuntimeError("engine down")


@pytest.mark.parametrize("reader", [_boom, lambda s, n: None, lambda s, n: eng([erow("AAA")], kind="other"),
                                    lambda s, n: "junk", lambda s, n: [erow("AAA")]],
                         ids=["raises", "none", "wrong_kind", "string", "list"])
def test_NEGATIVE_a_failed_read_is_the_fault(reader):
    b = HS.ssr_new_block(LISTED, session=S, now=NOW, tf="5m", ssr_read=reader, si_read=lambda syms: BLOCKS)
    assert b == HS.ssr_new_fault()
    _keys_ok(b)
    assert b["fault_text"] == HS.SSR_NEW_FAULT and b["groups"] == [] and b["empty_text"] is None
    assert b["n"] is None and b["n_untiered"] is None


@pytest.mark.parametrize("status", ["failed", "not_read"])
def test_NEGATIVE_engine_failed_or_not_read_serves_its_fault_no_fold_no_empty(status):
    calls = []
    b = build(ans=eng([erow("AAA")], status=status, fault_text="served engine fault", empty_text="served empty"),
              si_calls=calls)
    _keys_ok(b)
    assert b["fault_text"] == "served engine fault" and b["groups"] == [] and b["empty_text"] is None
    assert b["n"] is None and b["n_untiered"] is None and b["counts_text"] is None and calls == []


def test_NEGATIVE_a_served_fault_text_forces_no_fold_even_on_ok():
    b = build(ans=eng([erow("AAA")], fault_text="served engine fault", empty_text="served empty"))
    assert b["groups"] == [] and b["empty_text"] is None and b["fault_text"] == "served engine fault"


@pytest.mark.parametrize("status", ["pre_open", "not_latest", "out_of_play"])
def test_NEGATIVE_pre_open_and_other_days_serve_the_sentence_only(status):
    calls = []
    b = build(ans=eng([erow("AAA")], status=status, status_text="served status", empty_text="served empty"),
              si_calls=calls)
    _keys_ok(b)
    assert b["status_text"] == "served status" and b["groups"] == [] and b["empty_text"] is None
    assert b["n"] is None and calls == []


# ── 8 / 9 · SI unread, list unread ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("blocks", [None, RuntimeError("si down")], ids=["none", "raises"])
def test_NEGATIVE_si_unread_splits_by_the_list_only(blocks):
    b = build(blocks=blocks)
    _keys_ok(b)
    g = groups(b)
    assert [x["key"] for x in b["groups"]] == ["list_other", "rest"]
    assert syms_of(g["list_other"]) == ["AAA", "BBB", "CCC", "DDD"]          # A→Z — no SI order
    assert len(g["rest"]["rows"]) == 6
    assert g["list_other"]["summary"] == "🚩 on his list — 4" and g["rest"]["summary"] == "every other name — 6"
    assert b["si_note"] == HS.SSR_NEW_SI_UNREAD and b["tier_note"] is None and b["n_untiered"] is None
    assert b["order_note"] is None and b["n"] == 10
    assert all(r["si_text"] is None for x in b["groups"] for r in x["rows"])
    assert b["counts_text"] == "10 names · 4 on his 🚩 list · 6 others · served sources · served retriggered"


@pytest.mark.parametrize("listed", [None, {}, "junk"], ids=["none", "empty", "junk"])
def test_NEGATIVE_list_unread_splits_by_the_tier_only(listed):
    b = build(listed=listed)
    g = groups(b)
    assert [x["key"] for x in b["groups"]] == ["high", "rest"]
    assert syms_of(g["high"]) == ["FFG", "AAA", "FFF", "BBB", "EEE"]
    assert g["high"]["summary"] == "🩳 %s or %s short interest — 5" % (HI, EX)
    assert g["rest"]["summary"] == "every other name — 5 (3 not tiered)"
    assert b["list_note"] == HS.SSR_NEW_LIST_UNREAD and b["si_note"] is None
    assert b["counts_text"].startswith("10 names · 5 with %s or %s short interest · 5 others" % (HI, EX))


def test_NEGATIVE_both_unread_serves_one_fold_and_the_bare_count():
    b = build(listed=None, blocks=None)
    assert [x["key"] for x in b["groups"]] == ["rest"]
    assert b["counts_text"] == "10 names · served sources · served retriggered"
    assert b["si_note"] and b["list_note"]


# ── 10 / 11 · empty and junk ────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_zero_rows_serves_the_engine_empty_line_and_never_reads_si():
    calls = []
    b = build([], ans=eng([], empty_text="served empty"), si_calls=calls)
    _keys_ok(b)
    assert b["empty_text"] == "served empty" and b["groups"] == [] and calls == []
    assert b["n"] == 0 and b["counts_text"] is None and b["tier_note"] is None


def test_NEGATIVE_junk_rows_are_skipped_and_a_raising_link_is_none(monkeypatch):
    rows = [None, "x", 7, {"symbol": None}, {"symbol": 7}, {"symbol": "   "}, {}, erow("AAA")]
    b = build(rows)
    assert b["n"] == 1 and [r["symbol"] for g in b["groups"] for r in g["rows"]] == ["AAA"]
    b = build(ans=eng("not a list"))
    assert b["n"] == 0 and b["groups"] == []

    def bad_href(*_a, **_k):
        raise ValueError("x")
    monkeypatch.setattr(GT, "chart_href", bad_href)
    b = build([erow("AAA")])
    assert groups(b)["list_high"]["rows"][0]["href"] is None and b["n"] == 1


# ── 12 · JSON-safe ──────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_nan_never_reaches_the_wire_or_a_served_text():
    from rotation.api import _scrub
    nan = float("nan")
    rows = [erow("AAA", drop_pct=nan, drop_text=nan, at_text=nan, mark_text=None, source_text=None),
            erow("EEE", drop_pct=float("inf"))]
    blocks = {"AAA": dict(EXA, pct_of_float=nan), "EEE": HIE}
    b = build(rows, blocks=blocks, ans=eng(rows, sources_text=nan, retriggered_text=None, title=nan))
    json.dumps(_scrub(b), allow_nan=False)
    for t in _texts(b):
        assert "nan" not in t and "None" not in t, t
    r = groups(b)["list_high"]["rows"][0]
    assert r["drop_text"] is None and r["at_text"] is None and r["source_text"] is None and b["title"] is None
    assert b["counts_text"].endswith("others")


# ── 13 / 14 · display only, at board level ──────────────────────────────────────────────────────────────────────
def _minus(out):
    hs = dict(out["high_si"])
    hs.pop(HS.SSR_NEW_KEY, None)
    return hs, out["tiles"], out["empty_note"], out["subs"]


def test_NEGATIVE_display_only_the_cards_and_texts_never_move(si, monkeypatch):
    si["blocks"] = {"HIGH": HIGH[0], "EXTR": EXTR[0]}
    st = store([rdoc("HIGH", HIGH[1]), rdoc("EXTR", EXTR[1])], volumes={"HIGH": 3e6, "EXTR": 2e6})
    seen = []
    for reader in (_boom, lambda s, n: eng(status="failed", fault_text="served fault"),
                   lambda s, n: eng([erow("S%d" % i) for i in range(700)])):
        monkeypatch.setattr(HS, "_ssr_read", reader)
        out = board(st)
        assert HS.SSR_NEW_KEY in out["high_si"]
        seen.append(_minus(out))
    assert seen[0] == seen[1] == seen[2]
    assert [t["symbol"] for t in seen[0][1]] == ["HIGH", "EXTR"]
    assert out["high_si"][HS.SSR_NEW_KEY]["n"] == 700


def test_board_serves_ssr_new_with_a_patched_read(si, monkeypatch):
    si["blocks"] = {"HIGH": HIGH[0], "EXTR": EXTR[0]}
    got = {}

    def reader(session, now):
        got["session"], got["now"] = session, now
        return eng([erow("HIGH"), erow("ZZZ")])
    monkeypatch.setattr(HS, "_ssr_read", reader)
    out = board(store([rdoc("HIGH", HIGH[1]), rdoc("EXTR", EXTR[1])]))
    sn = out["high_si"][HS.SSR_NEW_KEY]
    _keys_ok(sn)
    assert got["session"] == S and got["now"] == NOW
    assert sn["n"] == 2 and sn["fault_text"] is None and sn["groups"]
    assert {r["symbol"] for g in sn["groups"] for r in g["rows"]} == {"HIGH", "ZZZ"}
    assert json.dumps(sn, allow_nan=False)


def test_NEGATIVE_unpatched_in_the_hermetic_suite_is_a_served_fault(si):
    si["blocks"] = {"HIGH": HIGH[0], "EXTR": EXTR[0]}
    out = board(store([rdoc("HIGH", HIGH[1]), rdoc("EXTR", EXTR[1])]))
    sn = out["high_si"][HS.SSR_NEW_KEY]
    _keys_ok(sn)
    assert isinstance(sn["fault_text"], str) and sn["fault_text"].strip()
    assert sn["groups"] == [] and sn["empty_text"] is None
    assert {t["symbol"] for t in out["tiles"]} == {"HIGH", "EXTR"}


def test_NEGATIVE_a_raising_section_inside_block_is_the_fault_and_the_cards_stand(si, monkeypatch):
    si["blocks"] = {"HIGH": HIGH[0]}
    st = store([rdoc("HIGH", HIGH[1])])
    monkeypatch.setattr(HS, "_ssr_read", lambda s, n: eng([erow("HIGH")]))
    good = board(st)
    monkeypatch.setattr(HS, "ssr_new_block", _boom)
    out = board(st)
    assert out["high_si"][HS.SSR_NEW_KEY] == HS.ssr_new_fault()
    assert _minus(out) == _minus(good)


# ── 15 · source guards, scoped [C5] ─────────────────────────────────────────────────────────────────────────────
SRC = Path(HS.__file__).read_text(encoding="utf-8")
NEW_FNS = (HS._ssr_read, HS._ssr_s, HS.ssr_si_text, HS.ssr_tiered, HS.ssr_new_rank, HS.ssr_new_fault,
           HS.ssr_new_rules_line, HS.ssr_new_block)


def test_NEGATIVE_SOURCE_GUARD_the_cards_and_the_membership_never_read_ssr():
    for fn in (HS.classify, HS.evaluate, HS.closeout_order, HS._cards, HS.card):
        assert "ssr" not in inspect.getsource(fn).lower(), fn.__name__
    hx = (Path(HS.__file__).parent / "high_si_cross.py").read_text(encoding="utf-8")
    assert "ssr_new" not in hx and "new_triggers" not in hx


def test_NEGATIVE_SOURCE_GUARD_one_lazy_engine_import_and_no_write_or_refresh():
    line = "from short_interest import ssr as SSR"
    assert SRC.count(line) == 1 and line in inspect.getsource(HS._ssr_read)
    tree = ast.parse(SRC)
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not any("ssr" in (getattr(n, "module", "") or "") or any("ssr" in a.name for a in n.names) for n in top)
    body = "".join(inspect.getsource(f) for f in NEW_FNS)
    for bad in ("kick", ".payload(", "record_pass", "update_one", "insert", "replace_one", "send_", "push_mode"):
        assert bad not in body, bad
    assert B_WORD.search(SRC) is None


def test_NEGATIVE_SOURCE_GUARD_the_standing_file_pins_still_hold():
    assert "payload(kick=False" in SRC and "kick_refresh" not in SRC
    assert "reg_sho_runs" not in SRC and "backfill_history" not in SRC
    assert SRC.count("SR.si_map(") == 1
    lits = {n.value for n in ast.walk(ast.parse(SRC)) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)}
    assert lits <= {0, 1, 2, 100.0}, lits
    assert _watch_imports_and_wc_reads("high_si.py") == (["chart_maps.gajjala_watch.constants"], ["FRAME_WORDS"])
    for banned in ("gajjala_watch import colls", "WCO."):
        assert banned not in SRC


def test_new_names_are_exported():
    for name in ("SSR_NEW_KEY", "SSR_NEW_KIND", "SSR_NEW_GROUPS", "SSR_NEW_BLOCK_KEYS", "ssr_si_text", "ssr_tiered",
                 "ssr_new_rank", "ssr_new_fault", "ssr_new_rules_line", "ssr_new_block"):
        assert name in HS.__all__, name


# ── 16 · the kind ───────────────────────────────────────────────────────────────────────────────────────────────
def test_the_kind_matches_the_engine_when_it_has_landed():
    assert getattr(_ssr_mod(), "NEW_KIND", HS.SSR_NEW_KIND) == HS.SSR_NEW_KIND
    assert set(NEW_ROW_KEYS) >= {"symbol", "at_text", "drop_text", "source_text", "mark_text"}


# ── 17 · the ℹ️ line [C7a] ──────────────────────────────────────────────────────────────────────────────────────
def test_rules_line_reads_the_tier_words_at_call_time(monkeypatch):
    line = HS.ssr_new_rules_line()
    assert line.endswith("UNMEASURED.") and HI in line and EX in line
    monkeypatch.setitem(SR.TIER_WORDS, SR.TIER_HIGH, "Lofty")
    assert "Lofty" in HS.ssr_new_rules_line() and "Lofty" in build()["groups"][0]["summary"]


def test_NEGATIVE_rules_line_types_no_high_si_colon_no_digit_no_b_word():
    line = HS.ssr_new_rules_line()
    assert "🩳 High SI:" not in line
    assert not re.search(r"\d", line)
    assert B_WORD.search(line) is None
