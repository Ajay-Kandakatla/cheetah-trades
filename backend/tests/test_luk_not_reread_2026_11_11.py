"""🥇 Luk — not-re-read cards tagged and ordered (2026-11-11, ORDER_VARIANT A: cut first, then the stable partition).

Ajay 2026-11-11 ~15:35 ET, verbatim: "I do not see an ondeman scan button for Luks

It still show HQ as the first ticker for me"

Variant A was chosen by the main session as the set-preserving default (the same cards as before the change; of the
cards shown, the ones the latest pass re-read come first). Variant B (re-read first, then the cut) = HIS CALL, not
built — test 22 proves it is not in the source.

Two fixtures: TOY (under the card limit — the live 📦 / ↩️ shape) and LIVE SHAPE (his 🔔 board: 3 old A+, more old
triggered cards than the limit, two re-read triggered cards right after the newest old break, and a limit's worth of
re-read forming cards behind the cut). Sizes come from GC.TILE_LIMIT_DEFAULT, never a typed count.
"""
from __future__ import annotations

import copy
import inspect
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as GS
from chart_maps.luk import constants as LC
from chart_maps.luk import run as RUN
from chart_maps.luk import store as LS
from chart_maps.luk import tab as T
from tests.test_gajjala_store import FakeColl
from tests.test_luk_tab import BWORD, EDGE, GS_READS, S, _pass_body, _read, _read_doc, _screens_doc

ORH = "opening_range_high"
LIM = GC.TILE_LIMIT_DEFAULT
TAB_SRC = Path(T.__file__).read_text(encoding="utf-8")
PRE_CHANGE_ORDER = "A+ first, then triggered earlier, forming, listed, stopped — the newest break first within a state"
VARIANT_A_TEXT = ("of the cards shown: the ones the latest pass re-read first, the ones it did not re-read after them")
PRE_CHANGE_TILE_KEYS = {
    "symbol", "name", "href", "tf", "bars", "curves", "vol_avg", "bands", "badges", "stats", "lines", "markers", "why",
    "setup", "state", "state_label", "frame_text", "trigger", "stop", "risk_pct", "r_usd", "trigger_text", "stop_text",
    "listed_why", "criteria", "chips", "bars5", "curves5", "vol_avg5", "as_of_bar_t5", "entry_bar_t", "read_at_text",
    "gajjala"}


def et(h: int, m: int, s: int = 0) -> datetime:
    """An ET wall time on S (2026-11-03, EST = UTC−5) as aware UTC."""
    return datetime(S.year, S.month, S.day, h, m, s, tzinfo=timezone.utc) + timedelta(hours=5)


LATEST = et(15, 36)
NOW = et(15, 40)


def _doc(sym, setup, state, *, read_at, entry=None, stamps=True):
    r = _read(setup, state, trigger=10.0, stop=9.5, risk_pct=5.0, r_usd=0.5,
              entry_bar_t=f"{S.isoformat()} {entry}" if entry else None)
    d = _read_doc(sym, {setup: r})
    if stamps:
        d["at"] = d["updated_at"] = read_at
    else:
        d.pop("at", None)
        d.pop("updated_at", None)
    return d


def toy(setup=ORH):
    return [
        _doc("HQ", setup, "aplus", read_at=et(9, 46), entry="09:45"),
        _doc("IONR", setup, "aplus", read_at=et(9, 41), entry="09:40"),
        _doc("NCEL", setup, "aplus", read_at=et(9, 36), entry="09:33"),
        _doc("ASYS", setup, "triggered", read_at=et(12, 41), entry="10:30"),
        _doc("DIOD", setup, "triggered", read_at=LATEST, entry="10:25"),
        _doc("RDDT", setup, "triggered", read_at=LATEST, entry="09:55"),
    ]


def _t(i):
    return f"T{i:02d}"


def _f(i):
    return f"F{i:02d}"


def live_shape(setup=ORH):
    """3 old A+; LIM + 1 old triggered (T01 the newest break of all); DIOD then RSSS re-read right after T01's break;
    LIM re-read forming cards — every one of them behind the cut."""
    out = [
        _doc("HQ", setup, "aplus", read_at=et(9, 46), entry="09:45"),
        _doc("IONR", setup, "aplus", read_at=et(9, 41), entry="09:40"),
        _doc("NCEL", setup, "aplus", read_at=et(9, 36), entry="09:33"),
    ]
    base = datetime(S.year, S.month, S.day, 12, 30)
    out.append(_doc(_t(1), setup, "triggered", read_at=et(12, 41), entry=base.strftime("%H:%M")))
    out.append(_doc("DIOD", setup, "triggered", read_at=LATEST, entry=(base - timedelta(minutes=1)).strftime("%H:%M")))
    out.append(_doc("RSSS", setup, "triggered", read_at=LATEST, entry=(base - timedelta(minutes=2)).strftime("%H:%M")))
    for i in range(2, LIM + 2):
        out.append(_doc(_t(i), setup, "triggered", read_at=et(12, 41),
                        entry=(base - timedelta(minutes=1 + i)).strftime("%H:%M")))
    for i in range(1, LIM + 1):
        out.append(_doc(_f(i), setup, "forming", read_at=LATEST))
    return out


def make_store(reads, *, pass_at=LATEST, passes=True):
    colls = {n: FakeColl() for n in LS.LOGICAL}
    colls[LS.SCREENS_KEY] = FakeColl()
    st = LS.LukStore(colls=colls)
    if passes:
        st.record_pass(S, pass_at, _pass_body())
    for d in reads:
        colls[GS_READS()].docs[d["_id"]] = copy.deepcopy(d)
    sd = _screens_doc()
    colls[LS.SCREENS_KEY].docs[sd["_id"]] = sd
    st._test_colls = colls
    return st


def build(reads=None, sub=ORH, *, store=None, now=NOW, **kw):
    st = store or make_store(toy() if reads is None else reads)
    return T.build(sub, now=now, store=st, **kw)


def syms(out):
    return [t["symbol"] for t in out["tiles"]]


def pre_change(reads, setup=ORH, latest_at=LATEST):
    """The `_order_key` order of every card of the sub (the board before the change, before the cut)."""
    return T.tiles_for(reads, setup, caps={}, latest_at=latest_at)


# ── Positive ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_board_under_the_card_limit():
    out = build()
    assert syms(out) == ["DIOD", "RDDT", "HQ", "IONR", "NCEL", "ASYS"]
    hq = out["tiles"][2]
    assert hq["not_reread"] is True and hq["not_reread_text"] == "not re-read since 09:46 ET"
    diod = out["tiles"][0]
    assert diod["not_reread"] is False and diod["not_reread_text"] is None
    assert hq["read_at_text"] == "read at 09:46 ET"                       # still served, unchanged


def test_the_sentence_is_the_template_on_the_cards_own_stored_stamp(monkeypatch):
    reads = toy()
    asys = next(d for d in reads if d["symbol"] == "ASYS")
    asys["updated_at"] = None                                                # falls back to `at`
    asys["at"] = et(11, 7)
    out = build(reads)
    by = {t["symbol"]: t for t in out["tiles"]}
    assert by["HQ"]["not_reread_text"] == T.NOT_REREAD_TEXT.format(hhmm="09:46")
    assert by["ASYS"]["not_reread_text"] == T.NOT_REREAD_TEXT.format(hhmm="11:07")
    monkeypatch.setattr(T, "READ_AT_TEXT", "junk without a field")
    out2 = build(reads)
    by2 = {t["symbol"]: t for t in out2["tiles"]}
    assert by2["HQ"]["read_at_text"] == "junk without a field"
    for s in by:
        assert (by2[s]["not_reread"], by2[s]["not_reread_text"]) == (by[s]["not_reread"], by[s]["not_reread_text"])


@pytest.mark.parametrize("shape", ["toy", "live"])
def test_both_groups_keep_the_served_order(shape):
    reads = toy() if shape == "toy" else live_shape()
    out = build(reads)
    order = [t["symbol"] for t in pre_change(reads)]
    shown = set(syms(out))
    fresh = [t["symbol"] for t in out["tiles"] if t["not_reread"] is False]
    old = [t["symbol"] for t in out["tiles"] if t["not_reread"] is True]
    assert fresh == [s for s in order if s in shown and s in fresh]
    assert old == [s for s in order if s in shown and s in old]
    assert syms(out) == fresh + old


def test_the_cut_runs_first():
    out = build(limit=3)
    assert syms(out) == ["HQ", "IONR", "NCEL"]
    assert [t["symbol"] for t in pre_change(toy())][:3] == ["HQ", "IONR", "NCEL"]
    assert "DIOD" not in syms(out) and "RDDT" not in syms(out)          # NEGATIVE: no re-read card is pulled in


def test_his_board_shape_at_the_default_limit():
    reads = live_shape()
    out = build(reads)
    served = syms(out)
    first_lim = [t["symbol"] for t in pre_change(reads)][:LIM]
    assert first_lim[:6] == ["HQ", "IONR", "NCEL", _t(1), "DIOD", "RSSS"]
    assert set(served) == set(first_lim)                                  # the SAME cards as before the change
    assert served[:6] == ["DIOD", "RSSS", "HQ", "IONR", "NCEL", _t(1)]
    assert served.index("HQ") == 2
    assert sum(1 for t in out["tiles"] if t["not_reread"] is False) == 2
    assert not any(s.startswith("F") for s in served)                     # the re-read forming cards stay off it
    assert len(served) == LIM
    assert {s["key"]: s["n"] for s in out["subs"]}[ORH] == LIM


def test_the_focused_card_stays_first_and_is_still_tagged():
    out = build(focus="ASYS", limit=6)
    assert syms(out) == ["ASYS", "DIOD", "RDDT", "HQ", "IONR", "NCEL"]
    assert out["tiles"][0]["not_reread"] is True
    out = build(focus="asys", limit=2)
    assert syms(out) == ["ASYS", "HQ"]
    out = build(focus="ASYS", limit=1)
    assert syms(out) == ["ASYS"] and out["tiles"][0]["not_reread"] is True
    out = build(live_shape(), focus=_f(LIM))                              # a card behind the cut opens by link
    assert syms(out)[0] == _f(LIM) and out["tiles"][0]["not_reread"] is False


def test_the_order_note_says_it():
    out = build()
    assert out["order_note"] == T.ORDER_NOTE
    assert T.REREAD_ORDER_TEXT in out["order_note"] and T.STATE_ORDER_TEXT in out["order_note"]
    assert T.fault_payload()["order_note"] == T.ORDER_NOTE
    assert T.STATE_ORDER_TEXT == PRE_CHANGE_ORDER
    assert T.REREAD_ORDER_TEXT == VARIANT_A_TEXT and T.REREAD_ORDER_TEXT.startswith("of the cards shown")
    assert T.ORDER_NOTE == VARIANT_A_TEXT + " · in each group: " + PRE_CHANGE_ORDER
    for k in ("premarket", T.TRACK_SUB, T.PLAYBOOK_SUB):
        assert build(sub=k)["order_note"] == T.ORDER_NOTE


def test_an_ok_on_demand_pass_is_the_latest():
    cron_at, od_at = et(15, 31), et(15, 34)
    reads = [_doc("HQ", ORH, "aplus", read_at=cron_at, entry="09:45"),
             _doc("ASYS", ORH, "triggered", read_at=cron_at, entry="10:30"),
             _doc("DIOD", ORH, "triggered", read_at=od_at, entry="10:25")]
    st = make_store(reads, pass_at=cron_at)
    st.record_pass(S, od_at, dict(_pass_body(), on_demand=True), hhmm="15:34:00|on_demand",
                   source=GS.LEASE_ON_DEMAND, latest_if_newer=True, move_latest=True)
    assert st.latest_pass()["at"] == od_at
    out = build(store=st)
    by = {t["symbol"]: t for t in out["tiles"]}
    assert by["DIOD"]["not_reread"] is False
    assert by["HQ"]["not_reread_text"] == "not re-read since 15:31 ET"
    assert by["ASYS"]["not_reread_text"] == "not re-read since 15:31 ET"
    assert syms(out) == ["DIOD", "HQ", "ASYS"]


@pytest.mark.parametrize("setup", list(T.SETUP_SUBS))
def test_every_setup_sub_follows_the_rule(setup):
    out = build(toy(setup), sub=setup)
    assert out["sub"] == setup
    assert syms(out) == ["DIOD", "RDDT", "HQ", "IONR", "NCEL", "ASYS"]
    assert [t["not_reread"] for t in out["tiles"]] == [False, False, True, True, True, True]


# ── NEGATIVES ────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("shape", ["toy", "live"])
def test_NEGATIVE_no_pass_no_tag_nothing_moves(shape):
    reads = toy() if shape == "toy" else live_shape()
    out = build(store=make_store(reads, passes=False))
    assert all(t["not_reread"] is False and t["not_reread_text"] is None for t in out["tiles"])
    assert syms(out) == [t["symbol"] for t in pre_change(reads, latest_at=None)][:LIM]


def test_NEGATIVE_no_read_stamp_no_tag():
    reads = toy() + [_doc("NOST", ORH, "triggered", read_at=None, entry="10:00", stamps=False)]
    out = build(reads)
    nost = next(t for t in out["tiles"] if t["symbol"] == "NOST")
    assert nost["not_reread"] is False and nost["not_reread_text"] is None and nost["read_at_text"] is None
    assert syms(out) == ["DIOD", "NOST", "RDDT", "HQ", "IONR", "NCEL", "ASYS"]


def test_NEGATIVE_a_fresh_card_is_never_tagged():
    assert T.not_reread(LATEST, LATEST) is False
    assert T.not_reread(LATEST + timedelta(seconds=1), LATEST) is False
    assert T.not_reread(LATEST - timedelta(seconds=1), LATEST) is True
    reads = toy() + [_doc("NEWR", ORH, "triggered", read_at=LATEST + timedelta(seconds=40), entry="10:01")]
    out = build(reads)
    newr = next(t for t in out["tiles"] if t["symbol"] == "NEWR")
    assert newr["not_reread"] is False and newr["not_reread_text"] is None
    assert syms(out)[:3] == ["DIOD", "NEWR", "RDDT"]


def test_NEGATIVE_naive_and_aware_stamps_agree():
    aware = build(toy())
    naive_reads = toy()
    for d in naive_reads:
        d["at"] = d["updated_at"] = d["at"].replace(tzinfo=None)
    st = make_store(naive_reads)
    for pid in (GS.LATEST_ID, GS.LATEST_CRON_ID):
        doc = st._test_colls[GS.PASSES].docs[pid]
        doc["at"] = doc["at"].astimezone(timezone.utc).replace(tzinfo=None)
    naive = build(store=st)
    assert naive == aware


@pytest.mark.parametrize("bad", ["2026-11-03T20:36:00+00:00", 0, None])
def test_NEGATIVE_a_pass_at_that_is_not_a_datetime_tags_nothing(bad):
    st = make_store(toy())
    st._test_colls[GS.PASSES].docs[GS.LATEST_ID]["at"] = bad
    out = build(store=st)
    assert all(t["not_reread"] is False and t["not_reread_text"] is None for t in out["tiles"])
    assert syms(out) == [t["symbol"] for t in pre_change(toy(), latest_at=None)]
    assert T.not_reread(et(9, 46), bad) is False and T.not_reread(bad, LATEST) is False


def _shape(out):
    return (sorted(syms(out)), [(s["key"], s["n"]) for s in out["subs"]], out["counts"], out["counts_text"],
            out["pass"])


@pytest.mark.parametrize("case", [("toy", 1, ""), ("toy", 2, ""), ("toy", 3, ""), ("toy", 6, ""),
                                  ("toy", 2, "ASYS"), ("toy", 3, "NCEL"), ("live", LIM, ""), ("live", LIM, "HQ"),
                                  ("live", LIM, _f(1))])
def test_NEGATIVE_the_served_set_is_identical_without_the_partition(monkeypatch, case):
    shape, limit, focus = case
    reads = toy() if shape == "toy" else live_shape()
    real = build(reads, limit=limit, focus=focus)
    monkeypatch.setattr(T, "_reread_first", lambda tiles, focus: tiles)
    plain = build(reads, limit=limit, focus=focus)
    assert _shape(real) == _shape(plain)


@pytest.mark.parametrize("shape", ["toy", "live"])
def test_NEGATIVE_the_tag_changes_no_other_card_key(monkeypatch, shape):
    reads = toy() if shape == "toy" else live_shape()
    real = build(reads, limit=GC.TILE_LIMIT_MAX)
    monkeypatch.setattr(T, "not_reread", lambda read_at, latest_at: False)
    plain = build(reads, limit=GC.TILE_LIMIT_MAX)
    strip = lambda t: {k: v for k, v in t.items() if k not in ("not_reread", "not_reread_text")}   # noqa: E731
    a = {t["symbol"]: strip(t) for t in real["tiles"]}
    b = {t["symbol"]: strip(t) for t in plain["tiles"]}
    assert a == b and len(a) == len(real["tiles"])
    assert all(t["not_reread"] is False for t in plain["tiles"])


def test_NEGATIVE_the_track_record_and_the_screens_never_partition(monkeypatch):
    subs = list(T.SCREEN_SUBS) + [T.TRACK_SUB, T.PLAYBOOK_SUB]
    real = {k: build(sub=k, span="all") for k in subs}
    monkeypatch.setattr(T, "_reread_first", lambda tiles, focus: list(reversed(tiles)))
    for k in subs:
        rev = build(sub=k, span="all")
        assert rev["tiles"] == [] == real[k]["tiles"]
        for key in ("screens", "playbook", "track_record"):
            assert rev[key] == real[k][key], (k, key)


def test_NEGATIVE_no_internal_key_and_no_new_top_level_key():
    out = build(live_shape())
    assert out["tiles"]
    for t in out["tiles"]:
        assert not any(k.startswith("_") for k in t)
        # WIDENED 2026-11-12 (🥇 realtime cards, SPEC lukrt §3.3): + live_level, not_rung_text
        assert set(t) == PRE_CHANGE_TILE_KEYS | {"not_reread", "not_reread_text", "live_level", "not_rung_text"}
    assert set(out) == set(T.PAYLOAD_KEYS)
    assert set(T.fault_payload()) == set(T.PAYLOAD_KEYS)


def _walk(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def test_NEGATIVE_no_b_word_no_edge_no_typed_digit():
    for name in ("NOT_REREAD_TEXT", "REREAD_ORDER_TEXT", "STATE_ORDER_TEXT", "ORDER_NOTE"):
        v = getattr(T, name)
        assert not BWORD.search(v) and not EDGE.search(v), name
        assert not re.search(r"\d", v.replace("{hhmm}", "")), name
    out = build(live_shape())
    assert any(t["not_reread"] for t in out["tiles"])
    assert [s for s in _walk(out) if BWORD.search(s) or EDGE.search(s)] == []


def test_NEGATIVE_the_read_rule_is_untouched():
    assert RUN.CARRY_STATES == ("forming", "triggered")
    assert LC.LUK_SHORTLIST_MAX == 40
    st = make_store(live_shape())
    before = {k: copy.deepcopy(c.docs) for k, c in st._test_colls.items()}
    build(store=st)
    build(store=st, focus="HQ", limit=3)
    after = {k: copy.deepcopy(c.docs) for k, c in st._test_colls.items()}
    assert before == after


def test_NEGATIVE_a_previous_session_pass_tags_nothing_today():
    st = make_store(toy())
    out = T.build(ORH, now=datetime(2026, 11, 4, 15, 0, tzinfo=timezone.utc), store=st)
    assert out["session"]["date"] == "2026-11-04"
    assert out["tiles"] == []
    assert {s["key"]: s["n"] for s in out["subs"]}[ORH] == 0


def test_NEGATIVE_the_other_variant_is_not_in_the_source():
    src = inspect.getsource(T.build)
    assert src.count("shown = ") == 1
    assert "shown = {s: _reread_first(_clip_focus(t, focus, lim), focus) for s, t in tiles_by.items()}" in src
    assert "_clip_focus(_reread_first(" not in TAB_SRC
    assert TAB_SRC.count("board_mod._href(sym)") == 2
