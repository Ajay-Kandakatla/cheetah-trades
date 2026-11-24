"""🩳 High SI order: an upcoming Reg SHO close-out date lifts a name (Ajay 2026-11-24: "Please sort the short interest tab
based on that if this date is available put that ticker higher up").

A name whose 🔒 tag carries a day-13 date still ahead (run state counting) or today's (reached) sits first, the nearest
date first; inside one date and among the undated the house order (volume → float) holds; 🚫 his names still go last.
NEGATIVES: a passed date, a stale list, an unknown day count, no tag, a junk date, a raising read → no lift; a raising read
says so in the served order note and never takes the sub down.
"""
from __future__ import annotations

import pytest

from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala import store as ST

import tests.test_gajjala_high_si_2026_11_23 as B

si, board, store, rdoc, HIGH, EXTR, AKAN = B.si, B.board, B.store, B.rdoc, B.HIGH, B.EXTR, B.AKAN
_no_override = B._no_override


def item(state="counting", day13="2026-11-27", *, on="on", stale=False):
    return {"state": on, "stale": stale, "short": "🔒", "run": {"state": state, "day13": day13}}


def pay(items):
    return lambda now: {"items": items, "complete": True, "sources": []}


READS = lambda: [rdoc("HIGH", HIGH[1]), rdoc("EXTR", EXTR[1]), rdoc("AKAN", AKAN[1])]
VOLS = {"HIGH": 9e6, "EXTR": 5e6, "AKAN": 2e6}                     # house order: HIGH, EXTR, AKAN


def syms(out):
    return [t["symbol"] for t in out["tiles"]]


@pytest.fixture
def three(si):
    si["blocks"] = {"HIGH": HIGH[0], "EXTR": EXTR[0], "AKAN": AKAN[0]}
    return si


def test_house_order_without_any_date(three, monkeypatch):
    monkeypatch.setattr(HS, "_sho_payload", pay({}))
    out = board(store(READS(), volumes=VOLS))
    assert syms(out) == ["HIGH", "EXTR", "AKAN"]
    assert out["high_si"]["order_note"] == HS.ORDER_NOTE


def test_an_upcoming_date_lifts_the_name_to_the_top(three, monkeypatch):
    monkeypatch.setattr(HS, "_sho_payload", pay({"AKAN": item("counting", "2026-12-09")}))
    assert syms(board(store(READS(), volumes=VOLS))) == ["AKAN", "HIGH", "EXTR"]


def test_nearest_date_first_and_reached_counts(three, monkeypatch):
    monkeypatch.setattr(HS, "_sho_payload", pay({"AKAN": item("counting", "2026-12-09"),
                                                 "EXTR": item("reached", "2026-11-13")}))
    assert syms(board(store(READS(), volumes=VOLS))) == ["EXTR", "AKAN", "HIGH"]


def test_same_date_keeps_the_house_order(three, monkeypatch):
    monkeypatch.setattr(HS, "_sho_payload", pay({"AKAN": item(), "EXTR": item()}))
    assert syms(board(store(READS(), volumes=VOLS))) == ["EXTR", "AKAN", "HIGH"]


@pytest.mark.parametrize("bad", [
    item("passed", "2026-11-13"), item("passed_open", "2026-11-13"), item("unknown", None),
    item("counting", "2026-11-27", stale=True), item("counting", "2026-11-27", on="off"),
    item("counting", "not-a-date"), item("counting", 20261127), {"state": "on"}, None, "x",
])
def test_NEGATIVE_no_lift_without_an_upcoming_date(three, monkeypatch, bad):
    monkeypatch.setattr(HS, "_sho_payload", pay({"AKAN": bad}))
    assert syms(board(store(READS(), volumes=VOLS))) == ["HIGH", "EXTR", "AKAN"]


def test_NEGATIVE_a_raising_read_keeps_the_house_order_and_says_so(three, monkeypatch):
    def boom(now):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(HS, "_sho_payload", boom)
    out = board(store(READS(), volumes=VOLS))
    b = out["high_si"]
    assert syms(out) == ["HIGH", "EXTR", "AKAN"] and b["sho_text"] is None
    assert b["order_note"] == HS.ORDER_NOTE + HS.ORDER_SHO_UNREAD


def test_broker_names_still_go_last_even_with_a_date(three, monkeypatch):
    monkeypatch.setattr(HS, "_sho_payload", pay({"AKAN": item(), "HIGH": item("counting", "2026-11-25")}))
    monkeypatch.setattr(ST, "broker_flags", lambda st: (("HIGH",), False))
    assert syms(board(store(READS(), volumes=VOLS))) == ["AKAN", "EXTR", "HIGH"]


def test_a_dated_name_survives_the_limit_cut(three, monkeypatch):
    monkeypatch.setattr(HS, "_sho_payload", pay({"AKAN": item()}))
    assert syms(board(store(READS(), volumes=VOLS), limit=1)) == ["AKAN"]


def test_the_reg_sho_payload_is_read_once_per_build(three, monkeypatch):
    calls = []

    def once(now):
        calls.append(now)
        return {"items": {"AKAN": item()}, "complete": True, "sources": []}
    monkeypatch.setattr(HS, "_sho_payload", once)
    board(store(READS(), volumes=VOLS))
    assert len(calls) == 1


def test_closeout_date_unit():
    assert HS.closeout_date(item()) == "2026-11-27"
    assert HS.closeout_date(item("reached", "2026-11-23")) == "2026-11-23"
    for bad in (item("passed", "2026-11-13"), item(stale=True), item(day13=None), {}, None, 3):
        assert HS.closeout_date(bad) is None
    assert HS.CLOSEOUT_UPCOMING_STATES == ("counting", "reached")


def test_NEGATIVE_a_partial_read_is_said_in_the_order_note(three, monkeypatch):
    monkeypatch.setattr(HS, "_sho_payload", lambda now: {"items": {"AKAN": item()}, "complete": False, "sources": []})
    out = board(store(READS(), volumes=VOLS))
    assert syms(out) == ["AKAN", "HIGH", "EXTR"]                   # what WAS read still lifts
    assert out["high_si"]["order_note"] == HS.ORDER_NOTE + HS.ORDER_SHO_PARTIAL
