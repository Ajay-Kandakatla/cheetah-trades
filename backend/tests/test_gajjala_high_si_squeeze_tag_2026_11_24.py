"""🎾 tag on 🩳 High SI cards (Ajay 2026-11-24: "If the SI tab stocks have reversal squeeze action add the tag on the ticker
to for the tennis ball actions Run them against Gajjals other rules to show A+.. I wonder if we do this the other way
around to move them to Reversal squeeze by default but lets not do that").

The tag READS the name's stored 🎾 read — the same read the 🎾 card shows, graded by every GG rule in the pass. It shows
on the card's pill ("· 🎾 Reversal Squeeze A+") and as a ✓/✗ row with the 🎾 card's own words.
NEGATIVES: no 🎾 read / invalid / none / junk → no tag and no row; a triggered read never claims A+ here; nothing moves
between subs, the 🩳 order and membership are unchanged, the 🎾 sub's own cards are unchanged.
"""
from __future__ import annotations

import pytest

from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala import tab as GT

import tests.test_gajjala_high_si_2026_11_23 as B

si, board, store, rdoc, HIGH, EXTR, AKAN, HSUB = B.si, B.board, B.store, B.rdoc, B.HIGH, B.EXTR, B.AKAN, B.HSUB
_no_override = B._no_override


def with_sq(doc, state, **kw):
    doc["setups"] = {"reversal_squeeze": {"state": state, "trigger": 2.5, "stop": 2.1, **kw}}
    return doc


def tile(out, sym):
    return next(t for t in out["tiles"] if t["symbol"] == sym)


def row(t):
    return next((c for c in t["gajjala"]["criteria"] if c["key"] == "squeeze"), None)


@pytest.fixture
def two(si):
    si["blocks"] = {"HIGH": HIGH[0], "EXTR": EXTR[0]}
    return si


def test_aplus_shows_on_the_pill_and_as_a_tick_row(two):
    out = board(store([with_sq(rdoc("HIGH", HIGH[1]), "aplus"), rdoc("EXTR", EXTR[1])], volumes={"HIGH": 9e6, "EXTR": 5e6}))
    t = tile(out, "HIGH")
    assert t["gajjala"]["state_label"].endswith(" · 🎾 Reversal Squeeze A+")
    r = row(t)
    assert r["ok"] is True and r["label"] == HS.SQUEEZE_TAG and r["value"] == GT.state_label({"state": "aplus"})
    assert t["gajjala"]["high_si"]["squeeze"] == {"state": "aplus", "word": "A+"}
    e = tile(out, "EXTR")                                              # NEGATIVE: no 🎾 read → no tag, no row
    assert "🎾" not in e["gajjala"]["state_label"] and row(e) is None and e["gajjala"]["high_si"]["squeeze"] is None


@pytest.mark.parametrize("state,word,ok", [("forming", "forming", None), ("partial", "partial", False),
                                           ("stopped", "stopped", False), ("triggered", "triggered", True)])
def test_each_carded_state_has_its_word(two, state, word, ok):
    out = board(store([with_sq(rdoc("HIGH", HIGH[1]), state, entry_bar_t=B.NOW), rdoc("EXTR", EXTR[1])]))
    t = tile(out, "HIGH")
    assert t["gajjala"]["state_label"].endswith(" · 🎾 Reversal Squeeze " + word)
    assert row(t)["ok"] is ok


def test_forming_ready_says_ready(two):
    out = board(store([with_sq(rdoc("HIGH", HIGH[1]), "forming", ready=True), rdoc("EXTR", EXTR[1])]))
    assert tile(out, "HIGH")["gajjala"]["state_label"].endswith("🎾 Reversal Squeeze forming · ready")


def test_NEGATIVE_triggered_never_claims_aplus_here(two):
    out = board(store([with_sq(rdoc("HIGH", HIGH[1]), "triggered", entry_bar_t=B.NOW), rdoc("EXTR", EXTR[1])]))
    t = tile(out, "HIGH")
    assert "A+" not in row(t)["value"] and "A+" not in t["gajjala"]["state_label"].split("🎾")[1]
    assert "see the 🎾 card" in row(t)["value"]


@pytest.mark.parametrize("bad", [{"state": "invalid"}, {"state": "none"}, {"state": "awaiting"}, {}, None])
def test_NEGATIVE_no_carded_read_no_tag(two, bad):
    d = rdoc("HIGH", HIGH[1])
    d["setups"] = {"reversal_squeeze": bad}
    out = board(store([d, rdoc("EXTR", EXTR[1])]))
    t = tile(out, "HIGH")
    assert "🎾" not in t["gajjala"]["state_label"] and row(t) is None


def test_NEGATIVE_order_and_membership_unchanged_by_the_tag(two):
    vols = {"HIGH": 5e6, "EXTR": 9e6}
    plain = board(store([rdoc("HIGH", HIGH[1]), rdoc("EXTR", EXTR[1])], volumes=vols))
    tagged = board(store([with_sq(rdoc("HIGH", HIGH[1]), "aplus"), rdoc("EXTR", EXTR[1])], volumes=vols))
    assert [t["symbol"] for t in plain["tiles"]] == [t["symbol"] for t in tagged["tiles"]] == ["EXTR", "HIGH"]
    assert plain["high_si"]["n"] == tagged["high_si"]["n"] == 2


def test_NEGATIVE_the_squeeze_sub_itself_is_untouched(two):
    st = store([with_sq(rdoc("HIGH", HIGH[1]), "aplus"), rdoc("EXTR", EXTR[1])])
    out = board(st, "reversal_squeeze")
    assert "high_si" not in out
    assert all("🩳" not in (t.get("gajjala") or {}).get("state_label", "") for t in out["tiles"])


def test_squeeze_read_unit():
    assert HS.squeeze_read({"setups": {"reversal_squeeze": {"state": "aplus"}}}) == {"state": "aplus"}
    for bad in (None, {}, {"setups": None}, {"setups": {"reversal_squeeze": {"state": "invalid"}}}, {"setups": "x"}, {"setups": {"reversal_squeeze": "x"}}, {"setups": {"reversal_squeeze": 3}}):
        assert HS.squeeze_read(bad) is None
    assert set(HS.SQUEEZE_WORDS) == set(GT.TILE_STATES)
