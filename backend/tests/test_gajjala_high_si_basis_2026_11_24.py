"""🩳 High SI sub says where a name went when the house short-interest read refused its float (SPEC sidilute §3.6,
WP be-highsi, 2026-11-24).

Ajay 2026-11-24: "Make sure we are looking for Dilution.." · "Also split related events and filing so we flag them in
the right way".

The house read (short_interest.read.si_block, WP be-read) serves a refused float as `tier None` + `basis.float_refused`;
`classify` is NOT changed (→ `no_tier`). `evaluate` counts it in `ev["refused"]`, keeps it out of `no_tier_low`, and
names it in `basis_text` only when it WAS High / EXTREME on the float on file [C7]. `tier_chip` appends the block's
served flag shorts [C6]. Blocks are the house fixtures' si_block reads with the be-read leaves set by hand (§1.5 numbers).
"""
from __future__ import annotations

import inspect
import json

import pytest

from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala import high_si_cross as HSC
from short_interest import read as SR

import tests.test_gajjala_high_si_2026_11_23 as B           # the house fixtures (si_block over synthetic docs)

si, board, store, rdoc, ev_of, blk, fr = B.si, B.board, B.store, B.rdoc, B.ev_of, B.blk, B.fr
HIGH, EXTR, GMEX, LABT, KITT, SMX, AKAN = B.HIGH, B.EXTR, B.GMEX, B.LABT, B.KITT, B.SMX, B.AKAN
_no_override = B._no_override
HI, EX = SR.TIER_WORDS[SR.TIER_HIGH], SR.TIER_WORDS[SR.TIER_EXTREME]
CAP_TEXT = f"{B.CAP:,}"

SMTK_CHIP = "🩳 SI 8.9% shs out · 1.0d · 10/30 · ⚠️ float stale · ✂️ split 11/23 · 📄 S-4 11/13"
STALE = {"key": "float_stale", "emoji": "⚠️", "short": "⚠️ float stale", "text": "⚠️ float stale — 4.7× more shares"}
SPLIT = {"key": "split", "emoji": "✂️", "short": "✂️ split 11/23", "text": "✂️ 1-for-5 reverse split 11/23"}
FILING = {"key": "filing", "emoji": "📄", "short": "📄 S-4 11/13", "text": "📄 dilution filing: S-4 11/13"}
DUE = {"key": "split", "emoji": "✂️", "short": "✂️ split due 12/24", "text": "✂️ 1-for-10 reverse split due 12/24"}


def refused(sym, si, fl, so, *, pct_on_file, reason="diluted", chip=None, flags=None):
    """A house si_block with the be-read leaves of a refused float: no % of float, no tier, no EXTREME note."""
    b = blk(sym, si, fl, so)
    return dict(b, pct_of_float=None, tier=None, float_check=None, extreme=None, headline_basis="shares_out",
                chip=chip if chip is not None else b["chip"],
                basis={"status": "ok", "float_refused": reason, "refused_reasons": [reason],
                       "float_pct_on_file": pct_on_file, "flags": list(flags or [])})


# SMTK (§1.5): 432,313 short · float 546,875 on file → 79.05 % (EXTREME on file) · refused "diluted"
SMTK = (refused("SMTK", 432313, 546875, 4859369, pct_on_file=79.05, chip=SMTK_CHIP, flags=[STALE, SPLIT, FILING]),
        fr(546875))
# KITT 3.7 % (Low) and SMX 6.0 % (Moderate) on the float on file — refused for a split, counted, never named
KITTR = (refused("KITT", 203977, 5527831, 11000000, pct_on_file=3.69, reason="split", flags=[SPLIT]), fr(1612787))
SMXR = (refused("SMX", 47740, 791704, 2000000, pct_on_file=6.03, reason="split_same_day", flags=[SPLIT]), fr(282748))
# JZ-shaped: EXTREME 27.2 % float, confirmed, an upcoming split flag only — stays listed
JZ_BLK = dict(blk("JZ", 272000, 1_000_000, 1_000_000), basis={"status": "ok", "float_refused": None, "flags": [DUE]})
JZ = (JZ_BLK, fr(1_000_000))


def _ev(pairs, **kw):
    return ev_of({s: rdoc(s, p[1]) for s, p in pairs.items()}, {s: p[0] for s, p in pairs.items()}, **kw)


def _tail_sum(t):
    tail = t.split("not listed: ", 1)[1]
    return sum(int(seg.split(" ", 1)[0]) for seg in tail.split(" · "))


def test_the_shapes():
    assert SR.tier_of(79.05) == SR.TIER_EXTREME and SR.tier_of(3.69) == SR.TIER_LOW
    assert SR.tier_of(6.03) == SR.TIER_MODERATE
    assert JZ_BLK["tier"] == SR.TIER_EXTREME and JZ_BLK["pct_of_float"] == 27.2 and JZ_BLK["status"] == "ok"
    assert SMTK[0]["status"] == "ok" and SMTK[0]["si_shares"] == 432313


# ── evaluate [C7] ───────────────────────────────────────────────────────────────────────────────────────────────
def test_refused_extreme_on_file_is_counted_named_and_kept_out_of_no_tier_low():
    ev = _ev({"SMTK": SMTK, "HIGH": HIGH})
    assert [r["symbol"] for r in ev["rows"]] == ["HIGH"]
    assert ev["counts"]["no_tier"] == 1 and ev["refused"] == 1
    assert ev["no_tier_low"] == []                                               # card float 546,875 ≤ cap, still out
    assert ev["basis"] == [{"symbol": "SMTK", "chip": SMTK_CHIP, "tier_word": EX}]
    assert HS.no_tier_text(ev) is None
    assert HS.basis_text(ev) == ("⚠️ %s or %s on the float on file, but that float is stale or across a split — not "
                                 "tiered, so not listed: SMTK — %s" % (HI, EX, SMTK_CHIP))


def test_counts_words_split_the_refused_names_and_still_sum():
    ev = _ev({"SMTK": SMTK, "HIGH": HIGH})
    t = HS.counts_text(ev)
    assert "1 with no tier word (1 with a float that is stale or across a split)" in t
    assert _tail_sum(t) == ev["n_read"] - len(ev["rows"])


def test_NEGATIVE_every_no_tier_name_refused_prints_no_the_rest_clause():
    """Refix 2026-11-24: "the rest" never stands for zero names."""
    ev = _ev({"SMTK": SMTK, "KITT": KITTR, "SMX": SMXR, "HIGH": HIGH})
    assert ev["counts"]["no_tier"] == ev["refused"] == 3
    t = HS.counts_text(ev)
    assert "3 with no tier word (3 with a float that is stale or across a split)" in t
    assert "the rest" not in t and "no usable float" not in t
    assert _tail_sum(t) == ev["n_read"] - len(ev["rows"]) == 3


def test_NEGATIVE_one_plain_no_tier_name_beside_refused_keeps_the_rest_clause():
    sho = (blk("SHO", 300000, None, 2_000_000), fr(1_500_000))
    ev = _ev({"SMTK": SMTK, "SHO": sho})
    assert ev["counts"]["no_tier"] == 2 and ev["refused"] == 1
    t = HS.counts_text(ev)
    assert ("2 with no tier word (1 with a float that is stale or across a split; the rest with no usable float on "
            "the short-interest record; 1 of them with a card float at or under the cap)") in t
    assert _tail_sum(t) == ev["n_read"] - len(ev["rows"]) == 2


def test_refused_words_constant_is_head_plus_rest():
    assert HS.NO_TIER_REFUSED_WORDS == HS.NO_TIER_REFUSED_HEAD + HS.NO_TIER_REFUSED_REST
    assert HS.NO_TIER_REFUSED_REST.startswith("; the rest ")


def test_counts_words_with_refused_and_plain_no_tier_names_together():
    sho = (blk("SHO", 300000, None, 2_000_000), fr(1_500_000))
    ev = _ev({"SMTK": SMTK, "SHO": sho, "KITT": KITTR, "EXTR": EXTR})
    assert ev["counts"]["no_tier"] == 3 and ev["refused"] == 2 and ev["no_tier_low"] == ["SHO"]
    t = HS.counts_text(ev)
    assert ("3 with no tier word (2 with a float that is stale or across a split; the rest with no usable float on "
            "the short-interest record; 1 of them with a card float at or under the cap)") in t
    assert _tail_sum(t) == ev["n_read"] - len(ev["rows"]) == 3
    assert HS.no_tier_text(ev).endswith(": SHO — the tier is never worked out on the card's float here.")
    assert "SMTK" not in HS.no_tier_text(ev) and "KITT" not in HS.no_tier_text(ev)


def test_several_named_names_sort_by_symbol():
    zz = (refused("ZZZ", 300000, 1_000_000, 9_000_000, pct_on_file=30.0, chip="🩳 zz"), fr(1_000_000))
    aa = (refused("AAA", 150000, 1_000_000, 9_000_000, pct_on_file=15.0, reason="split", chip="🩳 aa"), fr(1_000_000))
    ev = _ev({"ZZZ": zz, "SMTK": SMTK, "AAA": aa})
    assert [d["symbol"] for d in ev["basis"]] == ["AAA", "SMTK", "ZZZ"]
    assert [d["tier_word"] for d in ev["basis"]] == [HI, EX, EX]
    assert HS.basis_text(ev).endswith(": AAA — 🩳 aa · SMTK — %s · ZZZ — 🩳 zz" % SMTK_CHIP)


def test_NEGATIVE_low_and_moderate_on_file_are_counted_never_named():
    ev = _ev({"KITT": KITTR, "SMX": SMXR, "HIGH": HIGH})
    assert ev["refused"] == 2 and ev["basis"] == [] and ev["no_tier_low"] == []
    assert HS.basis_text(ev) is None and HS.no_tier_text(ev) is None
    assert "2 with no tier word (2 with a float that is stale or across a split)" in HS.counts_text(ev)


def test_NEGATIVE_no_refused_name_keeps_every_word_byte_identical():
    sho = (blk("SHO", 300000, None, 2_000_000), fr(1_500_000))
    ev = _ev({"SHO": sho, "HIGH": HIGH, "GMEX": GMEX})
    assert ev["refused"] == 0 and ev["basis"] == [] and HS.basis_text(ev) is None
    want = ("3 listed names read · 1 listed here · not listed: 1 where the two float reads disagree on %s · 1 with no "
            "tier word (no usable float on the short-interest record; 1 of them with a card float at or under the cap)"
            % HI)
    assert HS.counts_text(ev) == want
    old = {k: v for k, v in ev.items() if k not in ("refused", "basis")}                # an ev from before this build
    assert HS.counts_text(old) == want and HS.no_tier_text(old) == HS.no_tier_text(ev)
    assert HS.no_tier_text(ev) == ("Short interest on file but no tier word (no usable float on the short-interest "
                                   "record), card float at or under %s: SHO — the tier is never worked out on the "
                                   "card's float here." % CAP_TEXT)
    assert HS.counts_text(dict(ev, refused=0)) == want and HS.counts_text(dict(ev, refused="x")) == want


def test_NEGATIVE_flags_only_basis_stays_listed_and_is_not_named():
    b = dict(HIGH[0], basis={"status": "ok", "float_refused": None, "flags": [FILING]})
    ev = _ev({"HIGH": (b, HIGH[1])})
    assert [r["symbol"] for r in ev["rows"]] == ["HIGH"] and ev["refused"] == 0 and ev["basis"] == []
    assert ev["rows"][0]["read"]["si_flags"] == ["📄 S-4 11/13"]
    assert HS.tier_chip(ev["rows"][0]["read"]) == "🩳 15.0%% short interest · %s · 📄 S-4 11/13" % HI


def test_NEGATIVE_a_stale_or_no_record_block_with_a_refused_basis_is_not_counted_refused():
    st = dict(SMTK[0], status="stale")
    nr = dict(SMTK[0], si_shares=None)
    ev = _ev({"ST": (st, SMTK[1]), "NR": (nr, SMTK[1])})
    assert ev["counts"]["stale"] == 1 and ev["counts"]["no_si"] == 1 and ev["refused"] == 0 and ev["basis"] == []


# ── tier_chip [C6] ──────────────────────────────────────────────────────────────────────────────────────────────
def test_listed_name_with_flags_chip_ends_with_them_jz():
    ev = _ev({"JZ": JZ})
    r = ev["rows"][0]["read"]
    assert r["si_flags"] == ["✂️ split due 12/24"]
    assert HS.tier_chip(r) == "🩳 27.2%% short interest · %s · ✂️ split due 12/24" % EX


def test_board_card_and_chartless_line_carry_the_flags(si):
    si["blocks"] = {"JZ": JZ[0], "HIGH": HIGH[0]}
    out = board(store([rdoc("JZ", JZ[1]), rdoc("HIGH", HIGH[1])]))
    lab = {t["symbol"]: t["gajjala"]["state_label"] for t in out["tiles"]}
    assert lab["JZ"] == "🩳 27.2%% short interest · %s · ✂️ split due 12/24 · float at or under %s" % (EX, CAP_TEXT)
    assert lab["HIGH"] == "🩳 15.0%% short interest · %s · float at or under %s" % (HI, CAP_TEXT)   # NEGATIVE: no flags
    assert out["high_si"]["basis_text"] is None


def test_board_serves_basis_text_and_keeps_the_refused_name_off_the_tiles(si):
    si["blocks"] = {"SMTK": SMTK[0], "HIGH": HIGH[0], "KITT": KITTR[0]}
    out = board(store([rdoc("SMTK", SMTK[1]), rdoc("HIGH", HIGH[1]), rdoc("KITT", KITTR[1])]))
    b = out["high_si"]
    assert [t["symbol"] for t in out["tiles"]] == ["HIGH"]
    assert b["basis_text"] == HS.BASIS_TEXT % (HI, EX, "SMTK — " + SMTK_CHIP)
    assert "KITT" not in b["basis_text"] and b["no_tier_text"] is None
    assert "2 with a float that is stale or across a split" in b["counts_text"]
    json.dumps(b, allow_nan=False)


def test_unconfirmed_word_then_flags_in_that_order():
    r = {"tier_word": HI, "pct_record": 36.4, "float_check": SR.FLOAT_UNCONFIRMED, "si_flags": ["⚠️ float stale"]}
    assert HS.tier_chip(r) == "🩳 36.4%% short interest · %s (%s) · ⚠️ float stale" % (HI, SR.FLOAT_UNCONFIRMED_WORD)


@pytest.mark.parametrize("bad", [None, "✂️ split due 12/24", 7, float("nan"), {"short": "x"}, [1, None, "", "  ",
                                 float("nan"), {"short": "x"}], []])
def test_NEGATIVE_junk_si_flags_add_nothing_to_the_chip(bad):
    base = {"tier_word": HI, "pct_record": 15.0}
    assert HS.tier_chip(dict(base, si_flags=bad)) == HS.tier_chip(base) == "🩳 15.0%% short interest · %s" % HI


@pytest.mark.parametrize("basis", ["x", 7, [STALE], {"flags": "⚠️ float stale"}, {"flags": [1, 2]},
                                   {"flags": [float("nan")]}, {"flags": [{"short": None}, {"short": ""},
                                                                         {"text": "no short"}, {"short": 5}]},
                                   {"flags": None}, {}])
def test_NEGATIVE_junk_basis_never_raises_and_adds_nothing(basis):
    b = dict(HIGH[0], basis=basis)
    assert HS.si_flags(b) == [] and HS.float_refused(b) is None
    ev = _ev({"HIGH": (b, HIGH[1])})
    assert [r["symbol"] for r in ev["rows"]] == ["HIGH"] and ev["faults"] == [] and ev["refused"] == 0
    assert HS.tier_chip(ev["rows"][0]["read"]) == "🩳 15.0%% short interest · %s" % HI


@pytest.mark.parametrize("pct", [None, float("nan"), float("inf"), "x", -5, 0, True])
def test_NEGATIVE_junk_pct_on_file_counts_the_refusal_but_names_nobody(pct):
    b = dict(SMTK[0], basis=dict(SMTK[0]["basis"], float_pct_on_file=pct))
    ev = _ev({"SMTK": (b, SMTK[1])})
    assert ev["faults"] == [] and ev["refused"] == 1 and ev["basis"] == [] and ev["no_tier_low"] == []
    assert HS.basis_text(ev) is None


@pytest.mark.parametrize("fr_", [None, "", "  ", 5, ["diluted"]])
def test_NEGATIVE_junk_float_refused_is_not_a_refusal(fr_):
    b = dict(SMTK[0], basis=dict(SMTK[0]["basis"], float_refused=fr_))
    ev = _ev({"SMTK": (b, SMTK[1])})
    assert ev["refused"] == 0 and ev["basis"] == [] and ev["no_tier_low"] == ["SMTK"]   # the old no-tier path


def test_NEGATIVE_basis_text_junk_entries():
    assert HS.basis_text({}) is None and HS.basis_text(None) is None and HS.basis_text({"basis": "x"}) is None
    assert HS.basis_text({"basis": [None, 3, {"chip": "c"}, {"symbol": ""}]}) is None
    assert HS.basis_text({"basis": [{"symbol": "Q", "chip": None}]}).endswith(": Q — " + HS.DASH)


# ── classify and the push step's membership — unchanged ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("pair", [HIGH, EXTR, GMEX, LABT, KITT, SMX, AKAN, JZ])
def test_classify_output_unchanged_with_a_basis_key(pair):
    b, f = pair
    plain = {k: v for k, v in b.items() if k != "basis"}
    for basis in ({"float_refused": "diluted", "float_pct_on_file": 79.05, "flags": [STALE]}, {"flags": [DUE]}, "junk"):
        assert HS.classify(dict(plain, basis=basis), f) == HS.classify(plain, f)


def test_push_membership_false_for_refused_true_for_flagged_but_listed():
    assert "HS.classify(" in inspect.getsource(HSC.run_step)                  # the function the push step calls
    c = HS.classify(*SMTK)
    assert c["listed"] is False and c["reason"] == "no_tier"
    assert HS.classify(*JZ)["listed"] is True
    assert "no_tier" in HS.REASONS and len(HS.REASONS) == 8                    # no new reason key [C7]


# ── rule_text ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_rule_text_names_the_refused_float_with_the_house_words(monkeypatch):
    t = HS.rule_text()
    assert ("A float on the short-interest record that is stale (more shares since it was read) or sits across a split "
            "from the short-interest count carries no tier word either, so that name is not listed; it is counted "
            "apart from the names with no usable float, and named above when it was %s or %s on that float." % (HI, EX)
            ) in t
    monkeypatch.setitem(SR.TIER_WORDS, SR.TIER_EXTREME, "ZZEXTREME")
    assert "when it was %s or ZZEXTREME on that float" % HI in HS.rule_text()


def test_NEGATIVE_new_words_carry_no_b_word_no_buy_no_squeeze():
    ev = _ev({"SMTK": SMTK, "KITT": KITTR})
    for t in (HS.rule_text(), HS.counts_text(ev), HS.basis_text(ev), HS.BASIS_TEXT, HS.NO_TIER_REFUSED_WORDS):
        assert not B.B_WORD.search(t) and "squeeze" not in t.lower() and " buy " not in t.lower(), t
