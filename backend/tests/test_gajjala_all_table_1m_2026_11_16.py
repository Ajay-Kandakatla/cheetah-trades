"""📋 All strategies on 🚩 Gajjala's 1-minute page (2026-11-16).

Ajay, verbatim: "Can you build and all strategies in Gallajas one min too and same sort criteria and then add to watch
list I think it's there from 1 min if it's not". tab.table_on(v) = GG5 + GG1; the 1-minute page now lists 📋 first and
serves the SAME all_table.block (both orders, the To 9 EMA column — read off the 1-minute card frame). NEGATIVES: 🧪
Audited still fails open and never lists it; GG5's board is byte-identical (tests/test_gajjala_variant_gg5_identity.py);
the table is only on its own sub.
"""
from __future__ import annotations

import pytest

from chart_maps.gajjala import all_table as TBL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.test_gajjala_all_table_2026_11_13 import BF, board, store, t1_docs


@pytest.fixture(autouse=True, scope="module")
def gg1_on():
    """2026-11-18 — the page retired (GC.GAJJALA_1M_ENABLED False, Ajay: "This is good info stop 1 min tab it was a good
    experiment"); this module pins how it RAN 2026-10-27 … 2026-11-17 and how it runs again if the word flips back.
    Module scope so the module-scoped fixture day is built ON too; a test that sets the switch False still can."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(GC, "GAJJALA_1M_ENABLED", True)
        yield


def test_table_on_is_gg5_and_the_1_minute_page_only():
    assert GT.table_on(V.GG5) and GT.table_on(V.GG1) and GT.table_on(None)
    assert not GT.table_on(V.GGA)                                           # NEGATIVE: 🧪 never


def test_the_1_minute_page_lists_it_first_and_serves_the_table():
    out = board(store(t1_docs()), variant=V.GG1)
    assert out["sub"] == GC.TABLE_SUB and out["sub_resolved_from"] == "param"
    assert out["subs"][0]["key"] == GC.TABLE_SUB
    t = out["table"]
    assert t is not None and t["title"] == TBL.TITLE
    assert [h["key"] for h in t["heads"]] == [k for k, _ in TBL.HEADS]     # same columns, To 9 EMA included
    assert t["sorts"]["default"] == TBL.SORT_GG                             # same sort criteria
    assert len(t["rows"]) >= 5                                              # NEGATIVE: never a vacuous empty table
    ranks = [r["rank"] for r in t["rows"]]
    assert ranks == list(range(1, len(ranks) + 1))
    assert sorted(r["near_rank"] for r in t["rows"]) == ranks
    got = [(r["symbol"], r["setup"]) for r in sorted(t["rows"], key=lambda r: r["near_rank"])]
    assert got == [(r["symbol"], r["setup"]) for r in TBL.near_order(t["rows"])]
    for r in t["rows"]:
        assert "gajjala_1m" in (r.get("card_href") or "")                  # the card link opens the 1-minute page


def test_NEGATIVE_only_on_its_own_sub_and_never_on_audited():
    assert "table" not in board(store(t1_docs()), BF, variant=V.GG1)
    out = board(store(t1_docs()), variant=V.GGA)
    assert out["sub"] == GC.DEFAULT_SUB and "table" not in out
    assert GC.TABLE_SUB not in [s["key"] for s in out["subs"]]


def test_to_9_ema_reads_the_1_minute_card_frame():
    from chart_maps.gajjala import bars as B
    bars = [{"t": f"2026-11-16 09:{30 + i:02d}", "c": 1} for i in range(3)]
    doc = {"tile": {"bars1": bars, "curves1": [{"tone": B.EMA_TONES[0][0], "values": [None, 1.0, 1.25]}],
                    "bars5": bars, "curves5": [{"tone": B.EMA_TONES[0][0], "values": [None, 9.0, 9.5]}]}}
    assert TBL.ema9_of(doc, "1m", V.GG1) == 1.25
    assert TBL.ema9_of(doc, "5m", V.GG1) == 9.5                              # NEGATIVE: the frame asked, never mixed


# ── the 1-minute route's live fan-out (review fix 2026-11-16: the GG5 route had it, the 1-minute one did not) ────────
def _get_1m(monkeypatch, live):
    import json
    from chart_maps import api as API
    from chart_maps import board as board_mod
    from tests.test_gajjala_tab import run_route
    built = {}

    def fake_build(sub, **kw):
        built.update(kw, sub=sub)
        return {"tab": "gajjala_1m", "sub": sub, "tiles": [],
                "table": {"rows": [{"symbol": "A1", "price_text": "4.00"}, {"symbol": "B1", "price_text": "1.00"}]}}
    monkeypatch.setattr(GT, "build", fake_build)
    monkeypatch.setattr(board_mod, "_live_snapshot", live)
    body = json.loads(run_route(API.chart_maps_gajjala_1m(sub=GC.TABLE_SUB, tf="", focus="", sort="", limit=GC.TILE_LIMIT_DEFAULT,
                                                          span="", email=None)).body)
    assert built["variant"] is V.GG1 and built["sub"] == GC.TABLE_SUB
    return body


def test_the_1_minute_route_puts_the_live_print_on_its_table_rows(monkeypatch):
    body = _get_1m(monkeypatch, lambda rows: {"A1": {"last_trade_price": 4.2, "price": 4.1}})
    by = {r["symbol"]: r for r in body["table"]["rows"]}
    assert by["A1"]["live_price"] == 4.2 and by["A1"]["live_price_text"] == "4.20"
    assert "live_price" not in by["B1"]                                     # NEGATIVE: only the name that printed


def test_NEGATIVE_a_raising_snapshot_leaves_the_1_minute_rows(monkeypatch):
    def boom(rows):
        raise RuntimeError("tape down")
    body = _get_1m(monkeypatch, boom)
    assert [r["symbol"] for r in body["table"]["rows"]] == ["A1", "B1"]
    assert all("live_price" not in r for r in body["table"]["rows"])
