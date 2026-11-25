"""🩳 in every 🧠 potential title (Ajay 2026-11-25 ~00:25 ET, verbatim: "I do need a mention of High SI stock when alerting
for potential though..").

The 🧠 title lead is EVERY source's words of the name's ctx["si_ssr"] tag (si_ssr_names.tag_block "text": the tag words
joined by LEAD_JOIN in SOURCE_KEYS order), not the first source only — so a 🩳 name carries its tier and short-interest %
also when ⛔ / 🔒 lead. A name with no tag keeps the title of before, byte for byte. No house push-title cap exists in
push/ or potential.py, so nothing is clipped and 🩳 is never dropped (pinned below). UNMEASURED.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import si_ssr_names as SSN
from tests.test_gajjala_potential import OK_SEND, Rec, at, bf_armed, ctx_for, frame_at, kf_building, seed
from tests.test_gajjala_store import fake_store

ROOT = Path(__file__).resolve().parents[1]
SSR_RECENT = "⛔ SSR 10/12 · day 2"
SHO_PAST = "🔒 day 6 past close-out"
HSI_CHIP = HS.tier_chip({"tier_word": HS.SR.TIER_WORDS["high"], "pct_record": 32.4})      # "🩳 32.4% short interest · High"
PLAIN = "🧠 AKAN · 🚩 Bull Flag — trigger armed · UNMEASURED"
# WIDENED 2026-11-25 (review: a 119-char lead in FRONT pushed the ticker off the lock screen): the ticker leads, the
# lead sits right after "🧠 AKAN · " — where the lead sits is HIS CALL.
HEAD, REST = "🧠 AKAN", "🚩 Bull Flag — trigger armed · UNMEASURED"


def titled(*leads) -> str:
    return SSN.LEAD_JOIN.join((HEAD,) + leads + (REST,))


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def tag_of(src: dict, hsi_text=None, *, add=False):
    """The ctx tag run.py stores — built by the module's own tag_block, never by hand."""
    return SSN.tag_block("AKAN", src, {"text": hsi_text} if hsi_text else None, add=add)


def ring(tag, reads=None, *, hold=None):
    """One live pass for AKAN; -> (out, the sent payloads)."""
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    now = at(10, 6)
    reads = reads or {"AKAN": {"bull_flag": bf_armed()}}
    ctx = {s: dict(ctx_for(), **({"si_ssr": tag} if tag is not None else {})) for s in reads}
    out = PT.run_pass(reads, {s: frame_at(now) for s in reads}, now, now.astimezone(PT.ET).date(), store=st, ctx=ctx,
                      rows={s: {"volume": 2_000_000, "price": 11.2} for s in reads}, send=send,
                      owner="owner@example.com", dry=False, tape="rth", si_ssr_hold=hold)
    return out, [p for (_o, p), _k in send.calls]


def test_the_chip_is_the_high_si_engines_own_words():
    assert HSI_CHIP == "🩳 32.4% short interest · High"


# ── POSITIVE ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_akan_like_ssr_recent_plus_hsi_has_both_in_the_title_ssr_first():
    t = tag_of({"ssr_recent": {"text": SSR_RECENT, "day_n": 2, "triggered_on": "2026-10-12"}}, HSI_CHIP)
    assert t["keys"] == ["ssr_recent", "hsi"] and t["lead"] == SSR_RECENT                 # the old lead: ⛔ only
    _out, (p,) = ring(t)
    assert p["title"] == titled(SSR_RECENT, HSI_CHIP)
    assert p["title"] == "🧠 AKAN · ⛔ SSR 10/12 · day 2 · 🩳 32.4% short interest · High · 🚩 Bull Flag — trigger armed · UNMEASURED"
    assert p["title"].index("🧠") < p["title"].index("⛔") < p["title"].index("🩳") < p["title"].index("🚩")
    assert HSI_CHIP not in p["body"] and SSR_RECENT not in p["body"]                   # the title carries them, once


def test_sho_past_plus_hsi_has_both_in_the_title():
    t = tag_of({"sho_past": {"text": SHO_PAST}}, HSI_CHIP)
    _out, (p,) = ring(t)
    assert p["title"] == titled(SHO_PAST, HSI_CHIP)


def test_every_source_in_source_keys_order():
    t = tag_of({"ssr_today": {"text": "⛔ SSR 10/13 · day 1", "day_n": 1}, "sho_past": {"text": SHO_PAST},
                "ssr_recent": {"text": SSR_RECENT, "day_n": 2}}, HSI_CHIP)
    assert t["keys"] == list(SSN.SOURCE_KEYS)
    _out, (p,) = ring(t)
    assert p["title"] == titled(SSR_RECENT, SHO_PAST, "⛔ SSR 10/13 · day 1", HSI_CHIP)


def test_hsi_only_leads_with_the_chip():
    t = tag_of({}, HSI_CHIP)
    _out, (p,) = ring(t)
    assert p["title"] == titled(HSI_CHIP)
    assert p["title"] == "🧠 AKAN · 🩳 32.4% short interest · High · 🚩 Bull Flag — trigger armed · UNMEASURED"


def test_a_title_cap_case_keeps_hsi_nothing_is_clipped():
    long_sho = "🔒 day 6 past close-out " + "x" * 400
    t = tag_of({"ssr_recent": {"text": SSR_RECENT + " " + "y" * 400, "day_n": 2}, "sho_past": {"text": long_sho}},
               HSI_CHIP)
    _out, (p,) = ring(t)
    assert HSI_CHIP in p["title"] and p["title"].startswith(HEAD + " · ") and p["title"].endswith(REST)
    assert len(p["title"]) > 800


def test_title_lead_prefers_every_source_then_the_lead():
    assert PT.title_lead({"text": "a · b", "lead": "a"}) == "a · b"
    assert PT.title_lead({"text": None, "lead": "a"}) == "a"
    assert PT.title_lead({"text": "", "lead": "a"}) == "a"


# ── NEGATIVES ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_tag_is_byte_identical_to_main():
    _out, (p,) = ring(None)
    plain = PT.compose("AKAN", "bull_flag", bf_armed(), "armed", {}, first_seen_et="10:06", tape="rth")
    assert p["title"] == plain["title"] == PLAIN
    assert json.dumps(p, sort_keys=True) == json.dumps(ring(None)[1][0], sort_keys=True)


@pytest.mark.parametrize("bad", [None, {}, {"text": None, "lead": None}, {"text": "", "lead": ""}, "⛔", 3,
                                 {"text": 5, "lead": ["⛔"]}])
def test_NEGATIVE_title_lead_junk_is_none(bad):
    assert PT.title_lead(bad) is None


def test_NEGATIVE_a_lapsed_add_tag_with_no_words_keeps_the_plain_title():
    t = tag_of({}, None, add=True)                                                    # keys [] / lead None / text None
    assert t["keys"] == [] and t["text"] is None
    _out, sent = ring(t)
    assert [p["title"] for p in sent] == [PLAIN]


def test_NEGATIVE_unknown_si_is_never_tagged():
    """An unread or unclassifiable short-interest block never lists → no 🩳 key → no 🩳 in the title."""
    assert SSN.hsi_tags(["AKAN"], {}, si_read=lambda syms: {}, today=at(10, 6).date()) == {}
    assert SSN.hsi_tags(["AKAN"], {}, si_read=lambda syms: {"AKAN": None}, today=at(10, 6).date()) == {}
    with pytest.raises(RuntimeError):
        SSN.hsi_tags(["AKAN"], {}, si_read=lambda syms: None, today=at(10, 6).date())
    t = tag_of({"ssr_recent": {"text": SSR_RECENT, "day_n": 2}}, None)
    _out, (p,) = ring(t)
    assert "🩳" not in p["title"] and p["title"] == titled(SSR_RECENT)


def test_NEGATIVE_building_hsi_never_rings_the_gate_is_unchanged():
    _out, sent = ring(tag_of({}, HSI_CHIP), {"AKAN": {"kiss_fly": kf_building()}})
    assert sent == []


def test_NEGATIVE_a_held_add_never_rings_even_with_words():
    t = tag_of({"ssr_recent": {"text": SSR_RECENT, "day_n": 2}}, None, add=True)
    out, sent = ring(t, hold=frozenset({"AKAN"}))
    assert sent == [] and out[PT.SI_SSR_COUNT_KEY] == 1


def test_NEGATIVE_no_house_push_title_cap_exists_to_clip_hsi():
    """The 00:25 ask said to shorten ⛔ / 🔒 rather than drop 🩳 when over the house title cap. No such named cap exists
    in push/ or potential.py, so none is invented and nothing is clipped. If one is ever added, this fails first."""
    pat = re.compile(r"^\s*[A-Z_]*TITLE[A-Z_]*(MAX|CAP|LIMIT|LEN|CHARS)[A-Z_]*\s*=", re.M)
    files = [ROOT / "chart_maps" / "gajjala" / "potential.py", *sorted((ROOT / "push").glob("*.py"))]
    assert [f.name for f in files if pat.search(f.read_text(encoding="utf-8"))] == []
