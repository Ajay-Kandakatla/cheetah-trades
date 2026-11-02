"""chart_maps/luk/tape.py — 📈 the tape per 🥇 Luk A+ row (BUILD_SPEC luk-tab §3.9, WP-B, 2026-11-01).

Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources."

The payload has 🚩's entry-tape shape (gajjala.tape.PAYLOAD_KEYS / LITE_KEYS) so GgEntryTape draws it. FakeColl stores,
injected loaders — never the network. Every bar is SYNTHETIC. NEGATIVES are marked.
"""
from __future__ import annotations

import pytest

from chart_maps.gajjala import store as GS
from chart_maps.gajjala import tape as GT
from chart_maps.luk import constants as LC
from chart_maps.luk import ledger as LL
from chart_maps.luk import tape as LT
from chart_maps.gajjala.ledger import LINES
from tests.test_luk_ledger import (B_WORD, D, D2, EDGE, FILL, _ledger_doc, _strings, _walk, alert_doc, bar, et, flat,
                                   make_store, merge, pushed_doc)

ID = "2026-11-02|ABC|pullback_reversal|aplus"


@pytest.fixture(autouse=True)
def _clean_memo():
    LT._MEMO.clear()
    yield
    LT._MEMO.clear()


class Loader:
    def __init__(self, by_day=None, boom=False):
        self.by_day = by_day or {}
        self.boom = boom
        self.calls = []

    def __call__(self, sym, d):
        self.calls.append((sym, d))
        if self.boom:
            raise RuntimeError("provider down")
        return list(self.by_day.get(d, [])), False


def _never(*_a, **_k):
    raise AssertionError("the mini tape must never fetch today")


def _store(walk=None, live=False):
    a = pushed_doc() if live else alert_doc()
    w = walk or _walk(exit="stop", state="stopped", exit_t=et(D, 10, 40).isoformat(), exit_date=D.isoformat(),
                      r=-1.0, sessions=1, reached_3r=True, reached_3r_t=et(D, 10, 20).isoformat())
    return make_store([a], [_ledger_doc(a, FILL, w)])


def _bars():
    return merge(flat(D, (9, 30), (10, 4), 9.95), [bar(D, 10, 5, 10.0, 10.1, 9.9, 10.0)],
                 flat(D, (10, 6), (10, 39), 10.2), [bar(D, 10, 40, 9.7, 9.7, 9.4, 9.5)], flat(D, (10, 41), (15, 59), 9.6))


def test_the_payload_has_gg_entry_tape_keys_and_luks_marks():
    p = LT.entry_tape(ID, now=et(D2, 12, 0), store=_store(), load_day=Loader({D: _bars()}),
                      today_load=lambda s, d: ([], False))
    assert tuple(p) == GT.PAYLOAD_KEYS and LT.PAYLOAD_KEYS is GT.PAYLOAD_KEYS
    assert p["n_bars"] == len(p["bars"]) > 0 and p["tf"] == f"{GT.GC.LEDGER_TAPE_TF_MIN}min · pre/post market"
    assert [h["key"] for h in p["hlines"]] == ["trigger", "stop", "fill"]
    assert [r["key"] for r in p["rules"]] == ["alert", "fill"]
    assert [d["key"] for d in p["dots"]] == ["fill", "r3", "exit"]
    r3 = next(d for d in p["dots"] if d["key"] == "r3")
    assert r3["px"] == pytest.approx(10.0 + 3 * 0.5) and r3["label"] == "+3R 11.50 at 10:20"
    assert p["rules"][0]["label"] == "recorded 10:00 ET — shadow, never sent"
    assert "solid line = the shadow record" in p["legend"]
    assert "stopped 10:40 · −1.0R" in p["read"] and "+3R reached" in p["read"]
    assert p["tone"] == "dn" and p["note"] is None and p["aria"] == "ABC 5-minute tape around the 🥇 A+ entry"


def _full(live):
    return LT.entry_tape(ID, now=et(D2, 12, 0), store=_store(live=live), load_day=Loader({D: _bars()}),
                         today_load=lambda s, d: ([], False))


def test_a_pushed_row_that_rang_his_phone_says_so_on_the_tape():
    """2026-11-01 go-live: LL.rows_for yields PUSHED rows (line "live"); the tape's alert rule + legend follow it."""
    p = _full(live=True)
    assert tuple(p) == GT.PAYLOAD_KEYS and p["rules"][0]["key"] == "alert"
    assert p["rules"][0]["label"] == "rang 10:00 ET — sent to your phone"
    assert "solid line = the alert that rang your phone" in p["legend"]
    assert p["read"].startswith("rang 10:00 ET") and "sent to your phone" in p["read"]


def test_NEGATIVE_a_live_tape_never_says_shadow_or_never_sent():
    p = _full(live=True)
    for s in _strings(p):
        assert "never sent" not in s and "shadow" not in s, s


def test_NEGATIVE_a_shadow_tape_never_says_it_rang_his_phone():
    p = _full(live=False)
    for s in _strings(p):
        assert "sent to your phone" not in s and "rang your phone" not in s, s


def test_the_line_maps_reuse_ggs_line_words_and_unknown_falls_back_to_shadow():
    assert set(LT.ALERT_WORD) == set(LT.RECORD_WORD) == {LINES[0], LINES[1]}
    assert LT._line({"line": LINES[0]}) == LINES[0]
    for bad in (None, "", "replayed", "LIVE", 1):                        # NEGATIVE: never upgrades to the live words
        assert LT._line({"line": bad}) == LINES[1], bad
    assert LT._line({}) == LINES[1]


def test_an_ema9_exit_draws_its_level_and_dot():
    w = _walk(exit="ema9_close", state="ema9_close", exit_date=D.isoformat(), exit_px=10.6, r=1.2, sessions=1)
    p = LT.entry_tape(ID, now=et(D2, 12, 0), store=_store(w), load_day=Loader({D: _bars()}),
                      today_load=lambda s, d: ([], False))
    ex = [h for h in p["hlines"] if h["key"] == "exit"]
    assert ex and ex[0]["label"] == f"closed below the {LC.LUK_PULLBACK_DAILY_EMA} EMA 10.60"
    assert any(d["key"] == "exit" and d["px"] == 10.6 for d in p["dots"])


def test_lite_has_lite_keys_and_never_fetches_today():
    p = LT.entry_tape(ID, lite=True, now=et(D, 12, 0), store=_store(_walk()), load_day=Loader({}),
                      today_load=_never)
    assert tuple(p) == GT.LITE_KEYS and p["lite"] is True
    assert p["note"] == LT.TAPE_WORDS["lite_today"]


def test_NEGATIVE_an_unknown_id_is_none():
    st = _store()
    for bad in (None, "", "junk", "2026-11-02|ABC|pullback_reversal|potential", "2026-11-02|ABC|bull_flag|aplus",
                "2026-11-02|abc|pullback_reversal|aplus", "2026-13-02|ABC|pullback_reversal|aplus",
                "2026-11-02|ZZZ|pullback_reversal|aplus"):
        assert LT.entry_tape(bad, now=et(D2, 12, 0), store=st, load_day=Loader({})) is None, bad


def test_NEGATIVE_a_read_fault_serves_the_fault_shape():
    st = make_store([alert_doc()], fail_alerts=True)
    p = LT.entry_tape(ID, now=et(D2, 12, 0), store=st, load_day=Loader({}))
    assert tuple(p) == GT.PAYLOAD_KEYS and p["bars"] == [] and p["note"] == GT.ENTRY_TAPE_WORDS["fault"]
    pl = LT.entry_tape(ID, lite=True, now=et(D2, 12, 0), store=st, load_day=Loader({}))
    assert tuple(pl) == GT.LITE_KEYS and pl["note"] == GT.ENTRY_TAPE_WORDS["fault"]


def test_NEGATIVE_a_raising_loader_is_a_fault_note_and_never_memoised():
    load = Loader(boom=True)
    p = LT.entry_tape(ID, now=et(D2, 12, 0), store=_store(), load_day=load, today_load=lambda s, d: ([], False))
    assert p["note"] == GT.ENTRY_TAPE_WORDS["fault"] and p["bars"] == []
    LT.entry_tape(ID, now=et(D2, 12, 0), store=_store(), load_day=load, today_load=lambda s, d: ([], False))
    assert len(load.calls) == 2


def test_NEGATIVE_a_build_that_raises_never_raises_out():
    class Boom:
        def alert_rows(self, _s):
            raise RuntimeError("boom")
    p = LT.entry_tape(ID, now=et(D2, 12, 0), store=Boom(), load_day=Loader({}))
    assert tuple(p) == GT.PAYLOAD_KEYS and p["note"] == GT.ENTRY_TAPE_WORDS["fault"]


def test_a_good_payload_is_memoised_per_mode():
    load = Loader({D: _bars()})
    ticks = iter([0.0, 1.0, 2.0, 3.0])
    clock = lambda: next(ticks)                                  # noqa: E731
    a = LT.entry_tape(ID, now=et(D2, 12, 0), store=_store(), load_day=load, clock=clock,
                      today_load=lambda s, d: (_bars(), False))
    b = LT.entry_tape(ID, now=et(D2, 12, 0), store=_store(), load_day=load, clock=clock,
                      today_load=lambda s, d: (_bars(), False))
    assert a is b and len(load.calls) == 1


def test_NEGATIVE_no_b_word_and_no_edge_in_the_payload():
    p = LT.entry_tape(ID, now=et(D2, 12, 0), store=_store(), load_day=Loader({D: _bars()}),
                      today_load=lambda s, d: ([], False))
    for s in list(_strings(p)) + list(LT.TAPE_WORDS.values()):
        assert not B_WORD.search(s) and not EDGE.search(s), s


def test_NEGATIVE_the_tape_never_writes():
    st = _store()
    LT.entry_tape(ID, now=et(D2, 12, 0), store=st, load_day=Loader({D: _bars()}), today_load=lambda s, d: ([], False))
    assert st.coll(GS.LEDGER).writes == 0 and st.coll(GS.ALERTS).writes == 0


def test_parse_id_round_trips_the_ledger_row_id():
    assert LT.parse_id(LL.row_id("2026-11-02", "ABC", "inside_day_pdh")) is not None
    assert LT.parse_id(FILL["fill_t"]) is None
