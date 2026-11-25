"""🚫 2026-11-25 — the 🧠 Potential sub's served bottom SECTION header (spec fidsec rev 2, §3.1, package be-section).

Ajay ~10:25 ET, verbatim (line 1 of his two): "On the potential page move the no fidelity to the bottom segmented category.,"
His 🚫 cards already sit LAST on every card board (tab.broker_bottom, 2026-11-09). This build adds ONE owner-only served
block `broker_flags.section` ({key, title, text, hint, n, symbols} — the 👀 Watch section shape) naming them. A header was
added above the 🚫 cards; NOTHING moved, nothing is hidden, no order key changed; the 📈 Track rows and the 👀 line are
untouched. 0 🚫 cards → no key (byte-identical payload). ONE sub gate: tab.BROKER_SECTION_SUBS (() = off).
NEGATIVES are mandatory: nothing moved or dropped, the kill switch, a non-owner, every other sub, the tail guard, a
raising helper, the Track / 👀 blocks equal with the section on and off.
"""
from __future__ import annotations

import inspect
import json
from datetime import date

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import constants as WC
from chart_maps.gajjala_watch import sections as WS
from tests import test_gajjala_potential_tab as PTT
from tests.test_gajjala_broker_flags import _with_state, assert_all_null, flag, strip_broker
from tests.test_gajjala_fade_ema_rank_2026_11_08 import GGA_OWN
from tests.test_gajjala_store import FakeColl

POT = GC.POTENTIAL_SUB
NOW = PTT.NOW


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def build(st, sub=POT, **kw):
    return GT.build(sub, now=kw.pop("now", NOW), store=st, **kw)


def syms(out) -> list:
    return [t["symbol"] for t in out["tiles"]]


def dump(o) -> str:
    return json.dumps(o, sort_keys=True, default=str)


def base_syms() -> list:
    s = syms(build(PTT.day_store(), owner=True))
    assert len(s) >= 3, s                                   # the fixture day serves several 🧠 cards
    return s


def off(monkeypatch):
    monkeypatch.setattr(GT, "BROKER_SECTION_SUBS", ())


def without_section(o):
    """The payload with only `broker_flags.section` removed (a deep copy)."""
    o = json.loads(dump(o))
    if isinstance(o.get("broker_flags"), dict):
        o["broker_flags"].pop("section", None)
    return o


# ── 1. the words ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_words_are_the_one_served_word_and_the_watch_section_format():
    assert GT.BROKER_SECTION_TEXT == WC.SECTION_TEXT
    for n in (1, 2, 7):
        sec = GT.broker_section([{"symbol": f"S{i}"} for i in range(n)], frozenset(f"S{i}" for i in range(n)))
        assert sec["title"] == GT.BROKER_FLAG_TEXT
        assert sec["text"] == f"{GT.BROKER_FLAG_TEXT} · {n}" and sec["n"] == n
        assert sec["hint"] is None and sec["key"] == GT.BROKER_SECTION_KEY
    # the key order == the 👀 Watch section block (the ONE section shape)
    watch = WS.sections_block([{"symbol": "X", "org": {"group": WC.SECTION_KEYS[0]}}], session=date(2026, 11, 25))
    assert tuple(k for k in watch[0] if k != "folded_default") == GT.BROKER_SECTION_KEYS
    assert "broker_section" in GT.__all__ and "BROKER_SECTION_TEXT" in GT.__all__
    assert GT.BROKER_SECTION_SUBS == (POT,)


# ── 2-3. the served block ────────────────────────────────────────────────────────────────────────────────────────
def test_owner_one_flagged_card_serves_the_exact_block_naming_the_tail():
    first = base_syms()[0]
    out = build(flag(PTT.day_store(), first), owner=True)
    sec = out["broker_flags"]["section"]
    assert sec == {"key": "broker", "title": GT.BROKER_FLAG_TEXT, "text": f"{GT.BROKER_FLAG_TEXT} · 1", "hint": None,
                   "n": 1, "symbols": [first]}
    assert tuple(sec) == GT.BROKER_SECTION_KEYS
    assert syms(out)[-len(sec["symbols"]):] == sec["symbols"]
    for t in out["tiles"][-1:]:
        assert t["broker_text"] == GT.BROKER_FLAG_TEXT
    assert all(t["broker_text"] is None for t in out["tiles"][:-1])


def test_two_flagged_keep_the_board_order_in_both_blocks():
    base = base_syms()
    picked = [base[0], base[2]]
    out = build(flag(PTT.day_store(), *reversed(picked)), owner=True)   # the list's own order never leaks
    s = syms(out)
    assert s[:-2] == [x for x in base if x not in picked]                # head == base order minus the flagged
    assert s[-2:] == picked                                              # tail == the flagged in base relative order
    assert out["broker_flags"]["section"]["symbols"] == picked and out["broker_flags"]["section"]["n"] == 2


# ── 4. NEGATIVE nothing moved or dropped ─────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_nothing_moved_or_dropped_by_the_section(monkeypatch):
    base = base_syms()
    picked = [base[1], base[3]] if len(base) > 3 else [base[1]]
    on = build(flag(PTT.day_store(), *picked), owner=True)
    sec = on["broker_flags"]["section"]
    head = syms(on)[:len(on["tiles"]) - sec["n"]]
    assert not set(sec["symbols"]) & set(head)                           # no section symbol among the head tiles
    off(monkeypatch)
    killed = build(flag(PTT.day_store(), *picked), owner=True)
    assert "section" not in killed["broker_flags"]
    assert len(on["tiles"]) == len(killed["tiles"]) == len(base)
    assert set(syms(on)) == set(syms(killed)) == set(base)
    assert syms(on) == syms(killed)                                      # the ORDER is broker_bottom's, unchanged


# ── 5. NEGATIVE no names → no key ────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_empty_list_or_a_name_not_on_the_board_serves_no_key():
    base = base_syms()
    out = build(PTT.day_store(), owner=True)
    assert out["broker_flags"]["symbols"] == [] and "section" not in out["broker_flags"]
    away = build(flag(PTT.day_store(), "NOTHERE"), owner=True)
    assert "section" not in away["broker_flags"] and syms(away) == base


# ── 6. NEGATIVE byte identity + the kill switch ──────────────────────────────────────────────────────────────────
def test_NEGATIVE_byte_identity_at_zero_and_the_kill_switch(monkeypatch):
    first = base_syms()[0]
    shipped0 = dump(build(PTT.day_store(), owner=True))
    shipped1 = build(flag(PTT.day_store(), first), owner=True)
    off(monkeypatch)
    assert dump(build(PTT.day_store(), owner=True)) == shipped0          # 0 flags: byte-identical either way
    killed1 = build(flag(PTT.day_store(), first), owner=True)
    assert "section" not in killed1["broker_flags"]                      # () = nothing served
    assert "section" in shipped1["broker_flags"]
    assert dump(without_section(shipped1)) == dump(killed1)              # the ONLY difference is the key


# ── 7. NEGATIVE a non-owner ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("owner", [False, None, 1, "yes", object()], ids=["False", "None", "1", "yes", "object"])
def test_NEGATIVE_a_non_owner_gets_no_block_and_the_same_order(owner):
    first = base_syms()[0]
    own = build(flag(PTT.day_store(), first), owner=True)
    other = build(flag(PTT.day_store(), first), owner=owner)
    assert "section" in own["broker_flags"]
    assert other["broker_flags"] is None
    assert_all_null(other)
    assert syms(other) == syms(own)
    assert dump(strip_broker(own)) == dump(strip_broker(other))          # nothing hidden: owner minus the tags == other


# ── 8. NEGATIVE the ONE sub gate ─────────────────────────────────────────────────────────────────────────────────
ALL_SYMS = ("AAA", "JJJ", "BBB", "CCC", "DDD", "EEE", "GGG", "HHH", "FFF", "PMX", "ZZZ", "CARY")
OTHER_SUBS = [k for k, *_ in GC.SUBS if k != POT]


@pytest.mark.parametrize("sub", OTHER_SUBS)
def test_NEGATIVE_every_other_sub_serves_no_key(sub, monkeypatch):
    out = build(flag(PTT.day_store(), *ALL_SYMS), sub=sub, owner=True)
    blk = out.get("broker_flags")
    assert not (isinstance(blk, dict) and "section" in blk), sub
    # the gate is what blocks it: widened to this sub, a board with cards (all on the list → the tail) serves the key
    monkeypatch.setattr(GT, "BROKER_SECTION_SUBS", (POT, sub))
    wide = build(flag(PTT.day_store(), *ALL_SYMS), sub=sub, owner=True)
    tiles = [t for t in wide.get("tiles") or [] if isinstance(t, dict) and t.get("symbol")]
    has = isinstance(wide.get("broker_flags"), dict) and "section" in wide["broker_flags"]
    if not tiles:
        assert not has, sub
    elif all(t.get("broker_text") == GT.BROKER_FLAG_TEXT for t in tiles):
        assert has and wide["broker_flags"]["section"]["symbols"] == [t["symbol"] for t in tiles], sub


def test_the_gate_bites_on_at_least_one_carded_setup_sub(monkeypatch):
    """Guard on the parametrized NEGATIVE above: it must not pass on empty boards alone."""
    monkeypatch.setattr(GT, "BROKER_SECTION_SUBS", tuple(k for k, *_ in GC.SUBS))
    served = [k for k in GC.SETUPS
              if "section" in (build(flag(PTT.day_store(), *ALL_SYMS), sub=k, owner=True)["broker_flags"] or {})]
    assert served, "no setup sub carded a flagged name on the fixture day"


# ── 9. the limit ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_limit_one_with_the_first_card_flagged_still_shows_it():
    first = base_syms()[0]
    out = build(flag(PTT.day_store(), first), owner=True, limit=1)
    assert syms(out) == [first]
    assert out["broker_flags"]["section"]["symbols"] == [first]


# ── 10. broker_section unit ──────────────────────────────────────────────────────────────────────────────────────
def test_broker_section_unit_none_tail_guard_junk_and_fold():
    rows = [{"symbol": s} for s in ("AAA", "BBB", "CCC")]
    assert GT.broker_section(rows, None) is None
    assert GT.broker_section(rows, frozenset()) is None
    assert GT.broker_section(rows, frozenset({"ZZZ"})) is None                       # no card on the list
    assert GT.broker_section(rows, frozenset({"AAA"})) is None                       # NEGATIVE not the tail
    assert GT.broker_section(rows, frozenset({"AAA", "CCC"})) is None                # NEGATIVE a gap
    assert GT.broker_section(rows, frozenset({"CCC"}))["symbols"] == ["CCC"]
    assert GT.broker_section([None, {"x": 1}, {"symbol": "ZZZ"}], frozenset({"ZZZ"}))["symbols"] == ["ZZZ"]
    assert GT.broker_section([{"symbol": "ZZZ"}, None, 5], frozenset({"ZZZ"}))["symbols"] == ["ZZZ"]  # non-dicts skipped
    assert GT.broker_section([{"symbol": "ZZZ"}, {"x": 1}], frozenset({"ZZZ"})) is None   # NEGATIVE a dict row after it
    assert GT.broker_section([{"symbol": "ZZZ"}, {"symbol": "MOG-A"}], frozenset({"MOG.A"}))["symbols"] == ["MOG-A"]
    assert GT.broker_section(None, frozenset({"X"})) is None and GT.broker_section([], frozenset({"X"})) is None
    assert rows == [{"symbol": s} for s in ("AAA", "BBB", "CCC")]                    # reads nothing, moves nothing
    assert "section" not in GT.broker_block(frozenset({"AAA"}))                     # the owner block is untouched


# ── 11. folded_default ───────────────────────────────────────────────────────────────────────────────────────────
def test_folded_default_absent_at_ship_and_true_only_from_the_constant(monkeypatch):
    assert GT.BROKER_SECTION_FOLDED_DEFAULT is False
    rows = [{"symbol": "AAA"}]
    assert "folded_default" not in GT.broker_section(rows, frozenset({"AAA"}))
    monkeypatch.setattr(GT, "BROKER_SECTION_FOLDED_DEFAULT", True)
    assert GT.broker_section(rows, frozenset({"AAA"}))["folded_default"] is True
    first = base_syms()[0]
    assert build(flag(PTT.day_store(), first), owner=True)["broker_flags"]["section"]["folded_default"] is True


# ── 12. a list read fault ────────────────────────────────────────────────────────────────────────────────────────
def test_a_faulting_list_read_serves_the_section_from_the_seed(monkeypatch):
    first = base_syms()[0]
    monkeypatch.setattr(GC, "BROKER_FLAG_SEED", (first,))
    out = build(_with_state(PTT.day_store(), FakeColl(fail=True)), owner=True)
    b = out["broker_flags"]
    assert b["fault_text"] == GT.BROKER_FAULT_TEXT and b["editable"] is False
    assert b["section"]["symbols"] == [first] and syms(out)[-1] == first


# ── 13. NEGATIVE a raising helper ────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_raising_broker_section_never_takes_down_the_board(monkeypatch):
    first = base_syms()[0]
    want = syms(build(flag(PTT.day_store(), first), owner=True))

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(GT, "broker_section", boom)
    out = build(flag(PTT.day_store(), first), owner=True)
    assert "section" not in out["broker_flags"]
    assert syms(out) == want and out["tiles"][-1]["broker_text"] == GT.BROKER_FLAG_TEXT


# ── 14. NEGATIVE everything else untouched ───────────────────────────────────────────────────────────────────────
def test_NEGATIVE_counts_track_watch_and_the_strip_are_untouched(monkeypatch):
    base = base_syms()
    picked = [base[0], base[2]]
    on = build(flag(PTT.day_store(), *picked), owner=True)
    assert "section" in on["broker_flags"]
    assert on["counts"] == build(PTT.day_store(), owner=True)["counts"]
    bf_on = build(flag(PTT.day_store(), *picked), sub="bull_flag", owner=True)
    monkeypatch.setattr(GT, "BROKER_SECTION_SUBS", ())
    killed = build(flag(PTT.day_store(), *picked), owner=True)
    assert on.get("track") is not None and on.get("watch") is not None
    assert dump(on["track"]) == dump(killed["track"])                    # 📈 Track rows keep their order
    assert dump(on["watch"]) == dump(killed["watch"])                    # 👀 line keeps its order
    assert dump(on.get("all_potentials")) == dump(killed.get("all_potentials"))
    # the 🧠 strip rows on a setup sub: unchanged with the section gate widened to that sub
    monkeypatch.setattr(GT, "BROKER_SECTION_SUBS", (POT, "bull_flag"))
    bf_wide = build(flag(PTT.day_store(), *picked), sub="bull_flag", owner=True)
    assert dump(bf_on["potential"]) == dump(bf_wide["potential"])
    from chart_maps.gajjala import alerts, ledger, potential, run, scanner
    for mod in (alerts, potential, run, scanner, ledger):
        assert "broker_section" not in inspect.getsource(mod), mod.__name__


# ── 15. a deep link into the section ─────────────────────────────────────────────────────────────────────────────
def test_focus_on_a_flagged_card_serves_it_and_lists_it():
    first = base_syms()[0]
    out = build(flag(PTT.day_store(), first), owner=True, focus=first)
    assert first in syms(out)
    assert first in out["broker_flags"]["section"]["symbols"]


# ── 16. the variants + where the call sits ───────────────────────────────────────────────────────────────────────
def _variant_store(sh, v):
    if v is V.GG1:
        return ST.GajjalaStore(colls={n: sh.coll(n) for n in ST.OWN}, variant=V.GG1, shared=sh)
    return ST.GajjalaStore(colls={n: sh.coll(n) for n in GGA_OWN}, variant=V.GGA, shared=sh)


@pytest.mark.parametrize("v", [V.GG1, V.GGA], ids=["1m", "audited"])
def test_one_minute_and_audited_serve_the_key_the_same_way(v):
    base = base_syms()
    first = base[0]
    out = GT.build(POT, now=NOW, store=_variant_store(flag(PTT.day_store(), first), v), owner=True, variant=v)
    assert out["broker_flags"]["section"]["symbols"] == [first] and syms(out)[-1] == first
    plain = GT.build(POT, now=NOW, store=_variant_store(PTT.day_store(), v), owner=True, variant=v)
    assert "section" not in plain["broker_flags"]                         # NEGATIVE 0 names → no key there too
    other = GT.build(POT, now=NOW, store=_variant_store(flag(PTT.day_store(), first), v), variant=v)
    assert other["broker_flags"] is None                                  # NEGATIVE non-owner


def test_the_call_sits_in_build_right_after_the_tag_walk_outside_every_variant_guard():
    src = inspect.getsource(GT.build)
    lines = src.split("\n")
    i = next(n for n, ln in enumerate(lines) if ln.startswith("    _broker_tag(out, flags)"))
    assert lines[i + 1].startswith('    _soft("broker section", _broker_section_tag, out, flags, sub_k)')
    assert src.count("_broker_section_tag") == 1
