"""📊 volume first on every Gajjala card sub + 🚫 his names at the bottom (2026-11-09 ~10:25 / ~10:30 ET) — display order only.

Ajay 2026-11-09, verbatim: "Ok sort any stocks by volume on all Gajjala's charts" then, with a 🚫-chipped card:
"The ones I am reporting they are not on Fidelity put them at the bottom".

What is pinned:
- `GC.VOLUME_SORT_SETUPS` = the float tuple = every setup sub; `tab.setup_tile` stashes `_volume` = the card's OWN
  Volume number (`chips.volume` ← the scanner row — no new read), popped before serving.
- `tab.order_key`: inside every state the slot `sk` = (volume DESCENDING, unknown last; then float ascending), placed by
  `GC.RS_FLOAT_SORT`; ➖ keeps its EMA-gap rank first and takes the slot right after it. Today's key breaks ties.
- `potential.order_key`: trigger armed before building, then volume descending, then float ascending (the swap).
- `tab.broker_bottom`: after each card board's own order (the five setup subs, 🧠, ☀️, 🌙) the rows whose symbol is on
  his list move to the END, in the same relative order, AFTER the limit cut (the list only reorders, never drops a card)
  — the same order for EVERY viewer; the words
  stay owner-only; nothing hidden, counts untouched, the 🏁 untouched.
- The served words: `VOL_ORDER_TEXT` / `RS_ORDER_TEXT` / `HF_ORDER_TEXT` / `POT_ORDER_TEXT` as `order_note`;
  `broker_block(...)["order_text"]` = `BROKER_BOTTOM_TEXT` on the owner strip.
NEGATIVES: a setup outside the tuple keeps today's key; no stash → the float-only key byte-identical; a lower state never
rises on volume; no `_`-key is served; a non-owner gets the same order and null words; an empty list moves nothing; the
🏁 ledger does not call the partition; no word says "edge", "probability" or the b-word.
"""
from __future__ import annotations

import inspect
import json

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests import test_gajjala_potential_tab as PTT
from tests.test_gajjala_broker_flags import assert_all_null, flag, strip_broker
from tests.test_gajjala_fade_ema_rank_2026_11_08 import GGA_OWN, fade
from tests.test_gajjala_float_sort_all_setups_2026_11_09 import _ctx
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_tab import (EXPECTED, NOW, R, _pm_store, _post_store, latest, ordering_store, read_doc,
                                    scan_doc, store_with, utc)

BF, KF, HF, VCP, RS = "bull_flag", "kiss_fly", "horizontal_fade", "intraday_vcp", "reversal_squeeze"
INF = float("inf")
NON_FADE = tuple(s for s in GC.SETUPS if s != HF)
BANNED = ("edge", "probabil", "bounc")


# ── builders ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _docs(reads: dict, floats: dict):
    return [read_doc(s, {r["setup"]: r}, ctx=_ctx(floats[s]) if floats.get(s) is not None else None)
            for s, r in reads.items()]


def _scans(reads: dict, vols: dict):
    return [scan_doc(s, volume=vols.get(s)) for s in reads]


def _shared(reads: dict, vols: dict, floats: dict):
    return store_with(reads=_docs(reads, floats), scans=_scans(reads, vols), passes=[latest()])


def _store(reads: dict, vols: dict, floats: dict | None = None, v=None):
    floats = floats or {}
    if v is V.GG1:
        own = {n: FakeColl() for n in ST.OWN}
        own[ST.READS] = FakeColl(_docs(reads, floats))
        own[ST.PASSES] = FakeColl([latest()])
        return ST.GajjalaStore(colls=own, variant=V.GG1, shared=_shared(reads, vols, floats))
    if v is V.GGA:
        return ST.GajjalaStore(colls={n: FakeColl() for n in GGA_OWN}, variant=V.GGA, shared=_shared(reads, vols, floats))
    return _shared(reads, vols, floats)


def syms(out) -> list:
    return [t["symbol"] for t in out["tiles"]]


def key(setup, state, vol="absent", fl="absent", **g):
    gg = dict({"setup": setup, "state": state}, **g)
    if vol != "absent":
        gg["_volume"] = vol
    if fl != "absent":
        gg["_float_shares"] = fl
    return GT.order_key({"symbol": "X", "gajjala": gg})


def today(setup, state, **g):
    return GT._state_key(dict({"setup": setup, "state": state}, **g), "X")


FORMING = dict(base={"bars": 0}, reason="waiting")


# ── the constant ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_volume_sort_setups_is_the_float_tuple_is_every_setup_sub():
    assert GC.VOLUME_SORT_SETUPS == GC.FLOAT_SORT_SETUPS == GC.SETUPS
    for s in ("premarket", "postmarket", "playbook", GC.POTENTIAL_SUB, GC.LEDGER_SUB):    # NEGATIVE: list subs
        assert s not in GC.VOLUME_SORT_SETUPS
    assert GC.RS_FLOAT_SORT == "within_state"                                             # the ONE placement knob


# ── order_key: the volume slot ───────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("setup", NON_FADE)
def test_key_is_state_rank_then_volume_desc_then_float_then_todays_key(setup):
    t = today(setup, "aplus", entry_bar_t="2026-10-13 10:30")
    assert key(setup, "aplus", vol=5e6, fl=1e6, entry_bar_t="2026-10-13 10:30") == t[:1] + (-5e6, 1e6) + t[1:]
    assert key(setup, "aplus", vol=5e6, entry_bar_t="2026-10-13 10:30") == t[:1] + (-5e6,) + t[1:]   # volume alone
    assert key(setup, "aplus", vol=1e6, entry_bar_t="2026-10-13 10:30") > key(setup, "aplus", vol=5e6,
                                                                               entry_bar_t="2026-10-13 10:30")


@pytest.mark.parametrize("setup", NON_FADE)
def test_volume_beats_float_and_equal_volumes_fall_to_the_float(setup):
    loud_big = key(setup, "forming", vol=5e6, fl=900_000_000, **FORMING)
    quiet_tiny = key(setup, "forming", vol=1e6, fl=1_000_000, **FORMING)
    assert loud_big < quiet_tiny                                   # 2026-11-09: his volume word beats the 10-18 float
    assert key(setup, "forming", vol=5e6, fl=1e6, **FORMING) < key(setup, "forming", vol=5e6, fl=9e6, **FORMING)


@pytest.mark.parametrize("setup", NON_FADE)
def test_unknown_volume_sorts_last_within_its_state_never_below_a_lower_state(setup):
    unknown = key(setup, "forming", vol=None, **FORMING)
    known = key(setup, "forming", vol=1.0, **FORMING)
    assert unknown[1] == INF and known < unknown
    assert unknown < key(setup, "partial", vol=9e9, missed=["k3"])          # a louder PARTIAL never rises above forming


@pytest.mark.parametrize("setup", NON_FADE)
def test_aplus_stays_above_forming_whatever_the_volume(setup):
    assert (key(setup, "aplus", vol=1.0, entry_bar_t="2026-10-13 10:30", broke=True)
            < key(setup, "forming", vol=9e9, **FORMING))


@pytest.mark.parametrize("setup", NON_FADE)
def test_global_mode_puts_the_slot_above_the_state_rank(setup, monkeypatch):
    monkeypatch.setattr(GC, "RS_FLOAT_SORT", "global")
    t = today(setup, "aplus", entry_bar_t="2026-10-13 10:30")
    assert key(setup, "aplus", vol=5e6, fl=1e6, entry_bar_t="2026-10-13 10:30") == (0, -5e6, 1e6) + t
    assert key(setup, "forming", vol=9e9, **FORMING) < key(setup, "aplus", vol=1.0, entry_bar_t="2026-10-13 10:30")


@pytest.mark.parametrize("setup", GC.SETUPS)
def test_NEGATIVE_no_volume_stash_keeps_the_float_only_key(setup):
    """A card without `_volume` (an older read, the focus pick, every exact-tuple pin of this morning) is byte-identical."""
    g = {"setup": setup, "state": "aplus", "entry_bar_t": "2026-10-13 10:30", "_float_shares": 3e6}
    t = today(setup, "aplus", entry_bar_t="2026-10-13 10:30")
    assert GT.order_key({"symbol": "X", "gajjala": g}) == t[:1] + (3e6,) + t[1:]
    assert GT.order_key({"symbol": "X", "gajjala": {k: v for k, v in g.items() if k != "_float_shares"}}) == t


@pytest.mark.parametrize("setup", NON_FADE)
def test_NEGATIVE_a_setup_outside_the_tuple_keeps_todays_key(setup, monkeypatch):
    monkeypatch.setattr(GC, "VOLUME_SORT_SETUPS", tuple(s for s in GC.SETUPS if s != setup))
    monkeypatch.setattr(GC, "FLOAT_SORT_SETUPS", tuple(s for s in GC.SETUPS if s != setup))
    assert key(setup, "aplus", vol=5e6, fl=1e6, entry_bar_t="2026-10-13 10:30") == today(
        setup, "aplus", entry_bar_t="2026-10-13 10:30")


# ── ➖ the gap stays first ───────────────────────────────────────────────────────────────────────────────────────
def test_fade_gap_first_then_volume_then_float_then_todays_key():
    def g_of(gap, vol, fl):                                          # the stashes setup_tile adds (gap, volume, float)
        return dict(fade("forming", gap), _ema_gap_pct=gap, _volume=vol, _float_shares=fl)
    g = g_of(0.2, 5e6, 1e6)
    t = GT._state_key(g, "X")
    assert GT.order_key({"symbol": "X", "gajjala": g}) == (GT._PRE_BREAK_RANK, 0.2, -5e6, 1e6) + t
    # NEGATIVE: a louder name with a wider gap stays BELOW a quieter one with the tighter gap
    wide_loud = GT.order_key({"symbol": "X", "gajjala": g_of(1.0, 9e9, 1e6)})
    tight_quiet = GT.order_key({"symbol": "X", "gajjala": g_of(0.2, 1.0, 9e9)})
    assert tight_quiet < wide_loud
    # equal gaps fall to the volume, then the float
    a = GT.order_key({"symbol": "X", "gajjala": g_of(0.5, 5e6, 9e9)})
    b = GT.order_key({"symbol": "X", "gajjala": g_of(0.5, 1e6, 1e6)})
    assert a < b
    assert GT.order_key({"symbol": "X", "gajjala": g_of(0.5, 5e6, 1e6)}) < GT.order_key(
        {"symbol": "X", "gajjala": g_of(0.5, 5e6, 9e9)})


def test_fade_rung_cards_take_the_slot_like_every_setup():
    g = {"setup": HF, "state": "aplus", "entry_bar_t": "2026-10-13 10:30", "_volume": 5e6, "_float_shares": 1e6}
    t = GT._state_key(g, "X")
    assert GT.order_key({"symbol": "X", "gajjala": g}) == t[:1] + (-5e6, 1e6) + t[1:]


# ── build: the stash is the card's own Volume number, popped ────────────────────────────────────────────────────
@pytest.mark.parametrize("setup", GC.SETUPS)
def test_board_orders_by_volume_within_the_state_and_the_stash_is_the_cards_volume(setup):
    reads = {s: R(setup, "forming", **FORMING) for s in ("AAA", "BBB", "CCC")}
    vols = {"AAA": 2e6, "BBB": 9e6, "CCC": 5e6}
    out = GT.build(setup, now=NOW, store=_store(reads, vols))
    assert syms(out) == ["BBB", "CCC", "AAA"]
    for t in out["tiles"]:
        assert t["gajjala"]["chips"]["volume"] == vols[t["symbol"]]            # the served chip = the sort source
        assert any(s["k"] == "Volume" for s in t["stats"])                      # the card prints the number it sorts by
        assert not any(k.startswith("_") for k in t["gajjala"]), t["gajjala"].keys()   # popped — never served
    assert "_volume" not in json.dumps(out, default=str)


@pytest.mark.parametrize("setup", NON_FADE)
def test_equal_volumes_fall_to_the_float_and_an_unknown_volume_is_last(setup):
    reads = {s: R(setup, "forming", **FORMING) for s in ("AAA", "BBB", "CCC")}
    floats = {"AAA": 9e6, "BBB": 1e6, "CCC": 5e6}
    assert syms(GT.build(setup, now=NOW, store=_store(reads, {s: 2e6 for s in reads}, floats))) == ["BBB", "CCC", "AAA"]
    vols = {"AAA": None, "BBB": 1e6, "CCC": 5e6}                                # AAA: the scanner row has no volume
    assert syms(GT.build(setup, now=NOW, store=_store(reads, vols, floats))) == ["CCC", "BBB", "AAA"]


def test_the_spec_ordering_fixture_is_byte_identical_with_one_shared_volume():
    """ordering_store's scan docs share scan_doc's default volume → today's EXPECTED order, unmoved."""
    assert syms(GT.build(BF, now=NOW, store=ordering_store())) == EXPECTED


@pytest.mark.parametrize("v", [V.GG1, V.GGA])
@pytest.mark.parametrize("setup", GC.SETUPS)
def test_one_minute_and_audited_serve_the_same_volume_order(v, setup):
    reads = {s: R(setup, "forming", **FORMING) for s in ("AAA", "BBB", "CCC")}
    vols = {"AAA": 2e6, "BBB": 9e6, "CCC": 5e6}
    assert syms(GT.build(setup, now=NOW, store=_store(reads, vols, v=v), variant=v)) == ["BBB", "CCC", "AAA"]


# ── 🧠 potential.order_key: volume before float ──────────────────────────────────────────────────────────────────
def test_potential_order_key_volume_desc_before_float_asc():
    a = PT.order_key("armed", {"float_shares": 900_000_000, "volume": 9e6}, BF, "AAA")
    b = PT.order_key("armed", {"float_shares": 1_000_000, "volume": 1e6}, BF, "BBB")
    assert a < b                                                     # louder first, whatever the float
    assert PT.order_key("armed", {"float_shares": 1e6, "volume": 5e6}, BF, "X") < PT.order_key(
        "armed", {"float_shares": 9e6, "volume": 5e6}, BF, "X")       # equal volume → smaller float
    assert PT.order_key("building", {"float_shares": 1, "volume": 9e9}, BF, "X") > PT.order_key(
        "armed", {"float_shares": None, "volume": None}, BF, "X")     # NEGATIVE: armed first whatever the numbers


# ── 🚫 his names at the bottom ───────────────────────────────────────────────────────────────────────────────────
def test_broker_bottom_is_a_stable_partition_that_moves_nothing_without_a_list():
    rows = [{"symbol": s} for s in ("AAA", "BBB", "CCC", "DDD")]
    assert GT.broker_bottom(rows, None) is rows
    assert GT.broker_bottom(rows, frozenset()) is rows
    assert [r["symbol"] for r in GT.broker_bottom(rows, frozenset({"BBB", "AAA"}))] == ["CCC", "DDD", "AAA", "BBB"]
    assert [r["symbol"] for r in GT.broker_bottom([{"symbol": "MOG-A"}, {"symbol": "ZZZ"}], frozenset({"MOG.A"}))] == [
        "ZZZ", "MOG-A"]                                               # "." / "-" folded like the tag
    assert GT.broker_bottom([{"symbol": "ZZZ"}, None, {"x": 1}], frozenset({"ZZZ"}))[-1] == {"symbol": "ZZZ"}


def test_flagged_name_sits_last_on_the_setup_sub_for_the_owner_and_everyone_else():
    want = [s for s in EXPECTED if s != "BBB"] + ["BBB"]              # BBB = the newest A+, first in today's order
    own = GT.build(BF, now=NOW, store=flag(ordering_store(), "BBB"), owner=True)
    other = GT.build(BF, now=NOW, store=flag(ordering_store(), "BBB"))
    assert syms(own) == syms(other) == want
    assert own["tiles"][-1]["broker_text"] == GT.BROKER_FLAG_TEXT and own["tiles"][0]["broker_text"] is None
    assert_all_null(other)                                           # the words stay his
    # the nothing-hidden invariant holds with the list in play: owner minus the tags == non-owner, byte for byte
    assert json.dumps(strip_broker(own), sort_keys=True, default=str) == json.dumps(strip_broker(other),
                                                                                    sort_keys=True, default=str)
    assert own["counts"] == GT.build(BF, now=NOW, store=ordering_store())["counts"]   # counts untouched


@pytest.mark.parametrize("setup", GC.SETUPS)
def test_flagged_name_sits_last_on_every_setup_sub_after_the_volume_order(setup):
    reads = {s: R(setup, "forming", **FORMING) for s in ("AAA", "BBB", "CCC")}
    vols = {"AAA": 2e6, "BBB": 9e6, "CCC": 5e6}
    st = flag(_store(reads, vols), "BBB")                            # the loudest name is on his list
    assert syms(GT.build(setup, now=NOW, store=st, owner=True)) == ["CCC", "AAA", "BBB"]
    assert syms(GT.build(setup, now=NOW, store=st)) == ["CCC", "AAA", "BBB"]


def test_the_limit_cut_runs_first_so_the_list_never_drops_a_card():
    """Critic 2026-11-09: "put them at the bottom" is not "drop them" — the cards shown are the same set as without the
    list, only their order moves (the 🎾 board passed the 24-card limit on 4 of the last 6 sessions)."""
    reads = {s: R(BF, "forming", **FORMING) for s in ("AAA", "BBB", "CCC")}
    vols = {"AAA": 2e6, "BBB": 9e6, "CCC": 5e6}
    assert syms(GT.build(BF, now=NOW, store=_store(reads, vols), limit=2)) == ["BBB", "CCC"]
    for owner in (False, True):
        got = syms(GT.build(BF, now=NOW, store=flag(_store(reads, vols), "BBB"), limit=2, owner=owner))
        assert got == ["CCC", "BBB"], owner                 # BBB last, still shown; AAA never admitted by the list
    # the same rule on the ☀️ list and the 🧠 sub
    assert syms(GT.build("premarket", now=NOW, store=flag(_pm_store(), "BIGV"), limit=1)) == ["BIGV"]
    base = syms(GT.build(GC.POTENTIAL_SUB, now=NOW, store=PTT.day_store(), limit=1))
    assert syms(GT.build(GC.POTENTIAL_SUB, now=NOW, store=flag(PTT.day_store(), base[0]), limit=1)) == base


def test_flagged_name_sits_last_in_the_potential_strip_rows_too():
    rows = [r["symbol"] for r in GT.build(BF, now=NOW, store=PTT.day_store())["potential"]["rows"]]
    assert len(rows) >= 2
    first = rows[0]
    moved = [r["symbol"] for r in GT.build(BF, now=NOW, store=flag(PTT.day_store(), first))["potential"]["rows"]]
    assert moved == [s for s in rows if s != first] + [first]
    assert len(moved) == len(rows)                                  # NEGATIVE: never dropped


def test_flagged_names_sit_last_on_the_premarket_and_postmarket_lists_keeping_each_lists_order():
    assert syms(GT.build("premarket", now=NOW, store=_pm_store())) == ["BIGV", "BIGC", "CARY"]
    assert syms(GT.build("premarket", now=NOW, store=flag(_pm_store(), "BIGV"))) == ["BIGC", "CARY", "BIGV"]
    assert syms(GT.build("premarket", sort="change", now=NOW, store=flag(_pm_store(), "CARY"))) == ["BIGC", "BIGV", "CARY"]
    assert syms(GT.build("postmarket", now=utc(19, 58), store=_post_store())) == ["HIGG", "LOWG"]
    assert syms(GT.build("postmarket", now=utc(19, 58), store=flag(_post_store(), "HIGG"))) == ["LOWG", "HIGG"]


def test_flagged_name_sits_last_on_the_potential_sub():
    base = syms(GT.build(GC.POTENTIAL_SUB, now=NOW, store=PTT.day_store()))
    assert len(base) >= 2
    first = base[0]
    moved = syms(GT.build(GC.POTENTIAL_SUB, now=NOW, store=flag(PTT.day_store(), first), owner=True))
    assert moved == [s for s in base if s != first] + [first]


def test_NEGATIVE_the_track_record_ledger_never_calls_the_partition():
    """The 🏁 is a ledger of what rang, in its own served order (the server never reorders a row) — the list only TAGS it."""
    assert "broker_bottom" not in inspect.getsource(LG)
    assert "broker_bottom" not in inspect.getsource(GT._ledger) if hasattr(GT, "_ledger") else True


def test_NEGATIVE_a_faulting_list_read_moves_nothing_and_still_serves_the_board():
    from tests.test_gajjala_broker_flags import _with_state
    st = _with_state(ordering_store(), FakeColl(fail=True))
    assert syms(GT.build(BF, now=NOW, store=st)) == EXPECTED
    out = GT.build(BF, now=NOW, store=st, owner=True)
    assert syms(out) == EXPECTED and out["broker_flags"]["fault_text"] == GT.BROKER_FAULT_TEXT


# ── the served words ─────────────────────────────────────────────────────────────────────────────────────────────
def test_the_owner_strip_carries_the_bottom_word_and_no_one_else_does():
    assert GT.broker_block(frozenset({"ABCD"}))["order_text"] == GT.BROKER_BOTTOM_TEXT
    assert GT.broker_block(frozenset(), fault=True)["order_text"] == GT.BROKER_BOTTOM_TEXT
    own = GT.build(BF, now=NOW, store=ordering_store(), owner=True)
    assert own["broker_flags"]["order_text"] == "your 🚫 names sit at the bottom of every card board"
    assert GT.build(BF, now=NOW, store=ordering_store())["broker_flags"] is None


def test_order_note_names_the_volume_on_every_card_sub_and_says_nothing_banned():
    st = ordering_store()
    for sub in GC.SETUPS:
        note = GT.build(sub, now=NOW, store=st)["order_note"]
        assert "volume" in note, (sub, note)
        if sub == HF:
            assert note.startswith("➖ 9 and 21 EMA closest to merged on top")   # his 2026-11-07 rank stays first
    assert GT.build(GC.POTENTIAL_SUB, now=NOW, store=st)["order_note"] == GT.POT_ORDER_TEXT
    for w in (GT.VOL_ORDER_TEXT, GT.RS_ORDER_TEXT, GT.HF_ORDER_TEXT, GT.POT_ORDER_TEXT, GT.BROKER_BOTTOM_TEXT):
        assert not any(b in w.lower() for b in BANNED), w
    for sub in ("premarket", "postmarket", "playbook"):                          # NEGATIVE: the lists serve none
        assert GT.build(sub, now=NOW, store=st).get("order_note") is None, sub
