"""📓 Gajjala's Playbook (chart_maps/gajjala/playbook.py, BUILD_SPEC §3.6, 2026-10-13).

Every quote must be HIS — byte-checked against the FIRST_HAND notes Ajay pasted (committed as
tests/fixtures/gajjala/first_hand_2026_10_13.md) — and tied to the video it was said in: Part 1 of the notes is the
IBD webinar (S8), Part 2 the TraderLion podcast (S9); STRATEGY_SPEC §1.4 caught 1:54:46–2:02:40 filed under the wrong
video once. Ajay 2026-10-13: "Implement his full stategy do not assume anything."
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import playbook as PB

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gajjala" / "first_hand_2026_10_13.md"
RAW = FIXTURE.read_text(encoding="utf-8")
_SPLIT = RAW.index("# PART 2")
PART = {"S8": RAW[:_SPLIT], "S9": RAW[_SPLIT:]}
_TS = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?(?:–\d{1,2}:\d{2}(?::\d{2})?)?$")
_B = re.compile("b" + "ounc", re.I)


def norm(s: str) -> str:
    """Markdown emphasis off, wrapped lines joined — the words, not the layout."""
    return re.sub(r"\s+", " ", s.replace("**", "")).strip()


NORM = {k: norm(v) for k, v in PART.items()}


def where(text: str) -> set:
    t = norm(PB.unbracket(text))
    return {k for k, v in NORM.items() if t in v}


@pytest.fixture(scope="module")
def pb():
    return PB.playbook()


def test_the_fixture_is_the_first_hand_notes_both_parts():
    assert "CI7mNvEQyms" in PART["S8"] and "10pHBNVi4Jc" in PART["S9"]
    assert "Goverdhan Gajjala" in RAW.splitlines()[0]


def test_every_item_has_a_source_and_a_timestamp_in_its_own_part(pb):
    items = PB.all_items(pb)
    assert len(items) >= 60
    for it in items:
        if it["kind"] == PB.KIND_NOT_BUILT:                          # R2-14 text, pinned in its own test below
            continue
        assert it["source"] in PB.SOURCES_FIRST_HAND, it
        if it["kind"] == PB.KIND_SUMMARY:
            assert it["ts"] is None and it.get("note")             # a list across the whole podcast, said so
            continue
        assert it["ts"] and _TS.match(it["ts"]), it
        assert it["ts"] in PART[it["source"]], (it["ts"], it["source"], it["text"][:60])


def test_every_verbatim_quote_is_in_the_first_hand_part_it_is_filed_under(pb):
    n = 0
    for it in PB.all_items(pb):
        if not it["verbatim"]:
            continue
        n += 1
        parts = where(it["text"])
        assert it["source"] in parts, (it["source"], parts, it["text"][:80])
    assert n >= 50


def test_the_tracklist_split_s9_owns_1_54_46_to_2_02_40(pb):
    """STRATEGY_SPEC §1.4: the slide segment is the TraderLion podcast, never the webinar."""
    late = [it for it in PB.all_items(pb) if it["ts"] and it["ts"].startswith(("1:54", "1:55", "1:56", "1:57",
                                                                                "1:59", "2:00", "2:01"))]
    assert late and all(it["source"] == "S9" for it in late)


def test_negative_a_quote_filed_under_the_wrong_video_is_caught():
    it = PB._q("1:59:24", "S8", "at least two big green bars (three is good) with a good price increase")
    assert it["source"] not in where(it["text"])


def test_negative_a_made_up_quote_is_not_in_the_notes():
    assert where("I always buy the first green bar of the day") == set()


def test_no_unbracketed_reversal_ban_word_anywhere(pb):
    blob = repr(pb)
    assert not _B.search(blob)
    edited = [it for it in PB.all_items(pb) if any(k in it["text"] for k in PB.BRACKET_EDITS)]
    assert len(edited) == 3                                         # S8 35:02 + the two S9 2:01:46 lines
    for it in edited:
        assert it["verbatim"] is True and _B.search(PB.unbracket(it["text"]))
        assert it["source"] in where(it["text"])


def test_negative_the_raw_caption_word_would_fail_the_ban():
    raw = PB.unbracket("whenever it hits the ground it [reverses] back hard")
    assert _B.search(raw) and not _B.search("whenever it hits the ground it [reverses] back hard")


def test_the_one_other_trader_name_is_his_own_verbatim_self_description(pb):
    hits = [it for it in PB.all_items(pb) if "minervini" in it["text"].lower()]
    assert len(hits) == 1
    it = hits[0]
    assert it["verbatim"] is True and it["ts"] == "9:45" and it["source"] == "S8"
    assert any(it["text"] in line for line in RAW.splitlines())     # BYTE-equal to one line's fragment
    for sec in pb["sections"]:
        for x in sec["items"]:
            if not x["verbatim"]:
                assert "minervini" not in x["text"].lower()


def test_the_vcp_characteristics_line_is_filed_under_the_fade(pb):
    fade = next(s for s in pb["sections"] if s["title"].endswith("Horizontal Fade"))
    vcp = next(s for s in pb["sections"] if s["title"].endswith("Intraday VCP"))
    assert any(it["ts"] == "1:57:33" and "Fade" in it.get("note", "") for it in fade["items"])
    assert not any(it["ts"] == "1:57:33" for it in vcp["items"])


def test_risk_says_0_25_is_his_own_start_and_the_5_to_10_basis_is_ambiguous(pb):
    risk = next(s for s in pb["sections"] if s["title"].startswith("Risk"))
    texts = " ".join(it["text"] + " " + it.get("note", "") for it in risk["items"])
    assert "0.25%" in texts and "his OWN starting risk" in texts
    assert "ambiguous" in texts
    blob = repr(pb).lower()
    assert "beginner" not in blob                                   # NEGATIVE (STRATEGY_SPEC §1.4 / DECISIONS A)


def test_his_stats_carry_the_expectancy_from_his_own_numbers(pb):
    doc = PB._rules_doc()
    si = doc["stats_inputs"]
    fy = round(si["full_year"]["win"] * si["full_year"]["avg_win_pct"]
               - si["full_year"]["loss"] * si["full_year"]["avg_loss_pct"], 2)
    h2 = round(si["h2"]["win"] * si["h2"]["avg_win_pct"] - si["h2"]["loss"] * si["h2"]["avg_loss_pct"], 2)
    assert fy == round(0.31 * 8.55 - 0.68 * 4.06, 2) == -0.11 and h2 == round(0.28 * 13 - 0.72 * 4, 2) == 0.76
    stats = next(s for s in pb["sections"] if s["title"].startswith("His stats"))
    blob = " ".join(it["text"] for it in stats["items"])
    assert "%+.2f%%" % fy in blob and "%+.2f%%" % h2 in blob


def test_sources_both_first_hand_videos_and_the_link_he_gave_labelled_third_party(pb):
    by = {s["key"]: s for s in pb["sources"]}
    assert "CI7mNvEQyms" in by["S8"]["url"] and by["S8"]["first_hand"] is True
    assert "10pHBNVi4Jc" in by["S9"]["url"] and by["S9"]["first_hand"] is True
    s1 = by["S1"]
    assert s1["url"] == "https://retailtradersrepository.substack.com/p/goverdhan-gajjala-a-deep-dive-into"
    assert s1["first_hand"] is False and "third-party" in s1["kind"] and "the link you gave" in s1["note"]


def test_sources_fall_back_to_the_three_spec_rows_without_the_json():
    rows = PB.sources({})
    assert [r["key"] for r in rows] == ["S8", "S9", "S1"] and rows[2]["first_hand"] is False


def test_contradicted_lists_the_f4vs_claims_dollar_wisdom_and_the_bi_lines(pb):
    c = pb["contradicted"]
    blob = " ".join(x["text"] for x in c)
    assert "30 minutes before the open" in blob                     # F4VS 30-min prep
    assert "require a catalyst" in blob                             # F4VS catalyst filter
    assert "30m" in blob and "1m" in blob                           # F4VS 30-minute Fade / 1-minute Bull Flag
    assert "Dollar Wisdom" in blob                                  # S17
    assert "≥ 2 EMA" in blob and "21-day EMA" in blob               # BI lines
    keys = {s["key"] for s in pb["sources"]}
    for x in c:
        assert x["status"] == "contradicted" and x["sources"], x["text"][:60]
        assert all(s["key"] in keys for s in x["sources"]), x["text"][:60]
        assert all(s.get("url") for s in x["sources"])


def test_negative_the_catalyst_item_cites_s8_12_00_exactly_once(pb):
    """Integration 2026-10-13 (WP7 cross-WP): U8 now carries S8 12:00 in its own sources; the hand-built item must
    not append it a second time."""
    u8 = [x for x in pb["contradicted"] if x.get("id") == "U8"]
    assert len(u8) == 1
    refs = [(s["key"], s.get("ts")) for s in u8[0]["sources"]]
    assert refs.count(("S8", "12:00")) == 1, refs
    assert len(refs) == len(set((s["key"], s.get("ts"), s.get("url")) for s in u8[0]["sources"]))


def test_negative_contradicted_is_empty_not_an_error_without_the_json():
    assert PB.contradicted({}) == [] and PB.decay({}) is None


def test_not_built_list_is_text_only_and_names_r2_14(pb):
    nb = next(s for s in pb["sections"] if s["title"].startswith("Not built"))
    blob = " ".join(it["text"] for it in nb["items"])
    for word in ("partials", "base counting", "progressive exposure", "five minutes", "mid-day", "trades-per-day",
                 "Pop & Drop", "confluence", "congruence", "30-minute Fade", "momentum breakout", "two EMA touches",
                 "journal"):
        assert word in blob, word
    for it in nb["items"]:
        assert it["kind"] == PB.KIND_NOT_BUILT and it["verbatim"] is False
        if it["ts"]:
            assert it["ts"] in PART[it["source"]]


def test_knobs_are_built_from_constants_and_move_with_them(monkeypatch):
    k = {r["key"]: r for r in PB.knobs()}
    assert "close ≥ open +%g%%" % GC.K1_BODY_GAIN_PCT in k["K1"]["text"]
    assert "%g×" % GC.K2_MAX_VOL_STEP in k["K2"]["text"] and "{:,}".format(GC.K8_MAX_FLOAT) in k["K8"]["text"]
    assert k["K1"]["value"] == PB.AJAY and k["Stays listed"]["value"] == PB.CHEETAH_DEFAULT
    assert k["🧱 Psych chip"]["value"] == PB.CHEETAH_DEFAULT
    monkeypatch.setattr(GC, "K1_BODY_GAIN_PCT", 4.5)
    monkeypatch.setattr(GC, "K10_AH_MIN_VOLUME", 333_000)
    monkeypatch.setattr(GC, "PSY_LEVELS", (2.0, 20.0))
    k2 = {r["key"]: r for r in PB.knobs()}
    assert "+4.5%" in k2["K1"]["text"] and "333,000" in k2["K10"]["text"] and "$2 / $20" in k2["🧱 Psych chip"]["text"]


def test_k4_knob_has_no_long_flag_while_the_band_is_empty():
    """2026-10-18 (DECISIONS13 D1/D4): K4_BF_LONG_FLAG_MAX None → "Bull Flag 1–5 bars · Kiss & Fly ≤ …", no long-flag
    clause and never a "waiting for your number" (the None is his answer, not a placeholder)."""
    t = {r["key"]: r["text"] for r in PB.knobs()}["K4"]
    assert GC.K4_BF_LONG_FLAG_MAX is None
    assert t.startswith("Bull Flag %d–%d bars · Kiss & Fly ≤ %d" % (GC.K4_BF_PULL_MIN, GC.K4_BF_PULL_MAX,
                                                                     GC.K4_KF_PULL_MAX))
    assert t.startswith("Bull Flag 1–5 bars · Kiss & Fly ≤ ")
    assert "long flag" not in t and "waiting for your number" not in t and "None" not in t


def test_NEGATIVE_k4_knob_names_the_long_flag_when_the_band_is_set(monkeypatch):
    monkeypatch.setattr(GC, "K4_BF_PULL_MAX", 3)
    monkeypatch.setattr(GC, "K4_BF_LONG_FLAG_MAX", 5)
    t = {r["key"]: r["text"] for r in PB.knobs()}["K4"]
    assert t.startswith("Bull Flag 1–3 bars (up to 5 = long flag, never A+) · Kiss & Fly ≤ ")


def test_k4_knob_provenance_names_his_2026_10_18_answer(monkeypatch):
    """FIX ROUND 1 (critic LOW a): the K4 range is his 2026-10-18 answer — the knob's provenance says so, built from
    the constants at call time; every other K-knob keeps PB.AJAY (NEGATIVE)."""
    k = {r["key"]: r for r in PB.knobs()}
    assert k["K4"]["value"] == "Ajay 2026-10-13 · 2026-10-18 (1–5 bars)"
    assert k["K4"]["value"] == PB.AJAY_K4_FMT % (GC.K4_BF_PULL_MIN, GC.K4_BF_PULL_MAX)
    assert all(k[x]["value"] == PB.AJAY for x in ("K1", "K2", "K3", "K5", "K6")), "only K4 carries the 10-18 date"
    monkeypatch.setattr(GC, "K4_BF_PULL_MAX", 3)
    assert {r["key"]: r for r in PB.knobs()}["K4"]["value"] == "Ajay 2026-10-13 · 2026-10-18 (1–3 bars)"


def test_a_none_placeholder_renders_waiting_never_none(monkeypatch):
    monkeypatch.setattr(GC, "HF_LEG_MIN_BARS", None)
    monkeypatch.setattr(GC, "K8_FAIL_EVENT_RULE", None)
    k = {r["key"]: r for r in PB.knobs()}
    assert "waiting for your number (H3)" in k["H3"]["text"]
    assert "waiting for your number (H2)" in k["H2"]["text"]
    assert "None" not in repr([r["text"] for r in PB.knobs()])


def test_items_are_copies_the_module_tables_cannot_be_mutated_through_a_payload(pb):
    pb["sections"][0]["items"][0]["text"] = "changed"
    assert PB.playbook()["sections"][0]["items"][0]["text"] != "changed"


# ── the knob table and the ℹ️ panel print the same numbers (2026-10-13 E2) ─────────────────────────────────────
def _panel_text() -> str:
    from supply_demand import rules_info as RI
    sec = RI.sections()["gajjala"]
    return " ".join(sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]])


def test_knob_table_and_rules_panel_agree_on_the_k10_band_and_the_price_floor():
    k = {r["key"]: r["text"] for r in PB.knobs()}
    panel = _panel_text()
    band = "top %g%% of the day's range" % (GC.K10_CLOSE_TOP_FRAC * 100)
    price = "$%.2f–$%g" % (GC.SCAN_MIN_PRICE, GC.SCAN_MAX_PRICE)
    assert band == "top 30% of the day's range" and price == "$0.10–$100"
    assert band in k["K10"] and band in panel
    assert price in k["Scanner"] and price in panel
    assert "top 0.3" not in k["K10"] and "$0.1–" not in k["Scanner"]          # NEGATIVE: the old renderings


def test_the_two_surfaces_move_together_with_the_constants(monkeypatch):
    monkeypatch.setattr(GC, "K10_CLOSE_TOP_FRAC", 0.25)
    monkeypatch.setattr(GC, "SCAN_MIN_PRICE", 0.5)
    k = {r["key"]: r["text"] for r in PB.knobs()}
    panel = _panel_text()
    for frag in ("top 25% of the day's range", "$0.50–$100"):
        assert frag in k["K10"] + k["Scanner"] and frag in panel, frag
    assert "top 30%" not in k["K10"] and "$0.10" not in k["Scanner"]          # NEGATIVE: nothing cached


def test_a_none_fraction_renders_waiting_never_none(monkeypatch):
    monkeypatch.setattr(GC, "K10_CLOSE_TOP_FRAC", None)
    t = {r["key"]: r["text"] for r in PB.knobs()}["K10"]
    assert "waiting for your number" in t and "None" not in t and "nan" not in t.lower()
