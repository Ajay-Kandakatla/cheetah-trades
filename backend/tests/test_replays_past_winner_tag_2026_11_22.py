"""🏆 past-winner tag on 🎬 Replays cards (2026-11-22).

Ajay 2026-11-22, verbatim: "MEDS was a part winner that went up after hours.. Please actually add a past winner tag in
our new ones looks for past winnings please if found again.." (MEDS: 🏆 single-day 2026-09-15 and 2026-09-16, and the
multi-day run 2026-09-14 → 2026-09-16.)

ONE pure index over the ACCEPTED 🏆 cards (`read_winner_sub`, same accept rule). A day-folder card is tagged only by a
win that ENDED strictly before its own session (multi-day = its last session); a 🏆 card by an EARLIER win of the same
symbol ("won before"). NEGATIVES: same day / later / spanning runs never tag; no win → no key; malformed / skipped
sidecars never feed the index; exact upper-case symbol; > 3 wins → "+N more". A tag only: UNMEASURED, no gate.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chart_maps.replays import constants as C
from chart_maps.replays import store as ST
from tests.test_replays_store_2026_11_17 import _base, write_side
from tests.test_replays_winners_2026_11_18 import OWN, _app, _cards, _strict, _strings, multi, put, single

PKG = Path(__file__).resolve().parents[1] / "chart_maps" / "replays"
BAD_WORDS = re.compile(r"bounc|\bedge\b", re.I)
CARD_DAY = "2026-11-20"


@pytest.fixture(autouse=True)
def _fresh_caches():
    for c in (ST._DAY_CACHE, ST._WIN_CACHE, ST._PW_CACHE):
        c.clear()
    yield


def day_card(sym, day=CARD_DAY, file=None):
    return _base(file or f"{sym}_reversal_squeeze_24x.mp4", f"{day}|{sym}|reversal_squeeze|aplus", sym,
                 "reversal_squeeze", "gajjala", ["5-min A+ winner"], "W +1R", 12.0)


def meds_winners(r: Path):
    """The real MEDS shapes on the mount (2026-11-22 read): two single-day reels + one 3-session run."""
    put(r, "winners", single("MEDS", "2026-09-15", cg=87.21830578989949, hp=344.9))
    put(r, "winners", single("MEDS", "2026-09-16", cg=274.69135802469134, hp=659.9))
    put(r, "multiday", multi("MEDS", days=("2026-09-14", "2026-09-15", "2026-09-16"), cg=601.4908124349937,
                             gain_pct=1322.6, file="2026-09-15_MEDS_45x.mp4", day="2026-09-15"))


def day_root(r: Path, *syms, day=CARD_DAY):
    for s in syms:
        write_side(r / C.VIDEOS_SUB / day, day_card(s, day))
    return r


def _by_sym(p):
    return {v["symbol"]: v for v in _cards(p)}


# ── constants ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_and_no_b_word():
    assert C.PAST_WIN_MAX == 3
    assert C.PAST_WIN_DAY_WORDS == "🏆 past winner" and C.PAST_WIN_BEFORE_WORDS == "🏆 won before"
    assert C.PAST_WIN_MORE_WORDS.format(n=2) == "+2 more"
    for n in ("PAST_WIN_DAY_WORDS", "PAST_WIN_BEFORE_WORDS", "PAST_WIN_MORE_WORDS"):
        assert not BAD_WORDS.search(getattr(C, n)), n


# ── the pure index ────────────────────────────────────────────────────────────────────────────────────────────
def test_pure_index_newest_first_multi_day_by_its_last_session(tmp_path):
    meds_winners(tmp_path)
    cards = [v for sub in C.WINNER_SUB_KEYS for v in ST.read_winner_sub(sub, tmp_path)["videos"]]
    idx = ST.past_winner_index(cards)
    assert list(idx) == ["MEDS"]
    assert [(w["day"], w["kind"], round(w["close_gain_pct"], 2), w["file"], w["sub"]) for w in idx["MEDS"]] == [
        ("2026-09-16", "multi_day", 601.49, "2026-09-15_MEDS_45x.mp4", "multiday"),
        ("2026-09-16", "single_day", 274.69, "2026-09-16_MEDS_45x.mp4", "winners"),
        ("2026-09-15", "single_day", 87.22, "2026-09-15_MEDS_45x.mp4", "winners"),
    ]
    assert ST.past_winner_index([]) == {}


def test_NEGATIVE_the_legacy_high_based_gain_pct_is_never_the_index_number(tmp_path):
    meds_winners(tmp_path)
    idx = ST.past_winner_index(ST.read_winner_sub("multiday", tmp_path)["videos"])
    w = idx["MEDS"][0]
    assert "gain_pct" not in w and round(w["close_gain_pct"], 1) == 601.5


# ── the day-folder tag (the MEDS case) ────────────────────────────────────────────────────────────────────────
def test_MEDS_day_card_is_tagged_with_its_one_run(tmp_path):
    """2026-11-22 fix #2: the 09-15 and 09-16 single days sit inside the 09-14 → 09-16 run = ONE move → one entry."""
    day_root(tmp_path, "MEDS", "CENN")
    meds_winners(tmp_path)
    p = ST.payload(CARD_DAY, tmp_path)
    m = _by_sym(p)["MEDS"]
    assert [e["text"] for e in m["past_winner"]] == ["🏆 past winner 09-16 +601% multi-day"]
    assert [e["day"] for e in m["past_winner"]] == ["2026-09-16"]
    assert m["past_winner_count"] == 1 and m["past_winner_more_text"] is None
    assert m["past_winner"][0]["sub"] == "multiday"
    assert set(m["past_winner"][0]) == {"day", "kind", "close_gain_pct", "file", "sub", "text"}   # no new served key
    _strict(json.dumps(p, allow_nan=True))


def test_NEGATIVE_a_symbol_with_no_past_win_carries_no_key_at_all(tmp_path):
    day_root(tmp_path, "MEDS", "CENN")
    meds_winners(tmp_path)
    cenn = _by_sym(ST.payload(CARD_DAY, tmp_path))["CENN"]
    assert not any(k.startswith("past_winner") for k in cenn)


def test_NEGATIVE_no_winner_folders_leaves_the_day_listing_untouched(tmp_path):
    day_root(tmp_path, "MEDS")
    p = ST.payload(CARD_DAY, tmp_path)
    assert "past_winner" not in json.dumps(p)


@pytest.mark.parametrize("win_day", [CARD_DAY, "2026-11-21", "2026-12-01"])
def test_NEGATIVE_a_win_on_the_same_day_or_later_never_tags(tmp_path, win_day):
    day_root(tmp_path, "LAH")
    put(tmp_path, "winners", single("LAH", win_day, cg=150.0))
    assert "past_winner" not in _by_sym(ST.payload(CARD_DAY, tmp_path))["LAH"]


@pytest.mark.parametrize("days,tagged", [
    (("2026-11-18", "2026-11-19", "2026-11-20"), False),       # ends ON the card day → look-ahead → no tag
    (("2026-11-19", "2026-11-20", "2026-11-23"), False),       # spans the card day → no tag
    (("2026-11-17", "2026-11-18", "2026-11-19"), True),        # ended the session before → tag
])
def test_NEGATIVE_a_multi_day_run_counts_only_from_its_last_session(tmp_path, days, tagged):
    day_root(tmp_path, "RUN")
    put(tmp_path, "multiday", multi("RUN", days=days, cg=200.0, gain_pct=400.0))
    card = _by_sym(ST.payload(CARD_DAY, tmp_path))["RUN"]
    assert ("past_winner" in card) is tagged
    if tagged:
        assert card["past_winner"][0]["text"] == "🏆 past winner 11-19 +200% multi-day"


def test_only_the_earlier_wins_are_kept_when_later_ones_exist(tmp_path):
    day_root(tmp_path, "MIX")
    put(tmp_path, "winners", single("MIX", "2026-11-10", cg=110.0))
    put(tmp_path, "winners", single("MIX", CARD_DAY, cg=300.0))
    put(tmp_path, "winners", single("MIX", "2026-11-21", cg=400.0))
    card = _by_sym(ST.payload(CARD_DAY, tmp_path))["MIX"]
    assert [e["day"] for e in card["past_winner"]] == ["2026-11-10"] and card["past_winner_count"] == 1


def test_more_than_three_wins_serves_three_and_plus_n_more(tmp_path):
    day_root(tmp_path, "MANY")
    for d in ("2026-10-01", "2026-10-02", "2026-10-03", "2026-10-06", "2026-10-07"):
        put(tmp_path, "winners", single("MANY", d, cg=100.0))
    card = _by_sym(ST.payload(CARD_DAY, tmp_path))["MANY"]
    assert [e["day"] for e in card["past_winner"]] == ["2026-10-07", "2026-10-06", "2026-10-03"]
    assert card["past_winner_count"] == 5 and card["past_winner_more_text"] == "+2 more"


def test_NEGATIVE_exactly_three_wins_has_no_more_text(tmp_path):
    day_root(tmp_path, "THREE")
    for d in ("2026-10-01", "2026-10-02", "2026-10-03"):
        put(tmp_path, "winners", single("THREE", d, cg=100.0))
    card = _by_sym(ST.payload(CARD_DAY, tmp_path))["THREE"]
    assert len(card["past_winner"]) == 3 and card["past_winner_more_text"] is None


def test_NEGATIVE_symbol_match_is_exact_upper_case(tmp_path):
    write_side(tmp_path / C.VIDEOS_SUB / CARD_DAY, day_card("meds", file="meds_lower_24x.mp4"))
    meds_winners(tmp_path)
    card = _cards(ST.payload(CARD_DAY, tmp_path))[0]
    assert card["symbol"] == "meds" and "past_winner" not in card


def test_NEGATIVE_a_card_with_no_symbol_is_never_tagged():
    idx = {"MEDS": [{"day": "2026-09-15", "kind": "single_day", "close_gain_pct": 1.0, "file": "x.mp4",
                     "sub": "winners"}]}
    for sym in (None, 5, ""):
        assert ST.past_wins_before(idx, sym, CARD_DAY, C.PAST_WIN_DAY_WORDS) is None
    assert ST.past_wins_before(idx, "MEDS", "not-a-day", C.PAST_WIN_DAY_WORDS) is None
    assert ST.past_wins_before(idx, "MEDS", None, C.PAST_WIN_DAY_WORDS) is None


@pytest.mark.parametrize("mutate", [
    lambda s: s.update(close_gain_pct=float("nan")),                 # skipped_bad
    lambda s: s.update(close_gain_pct="87"),                         # skipped_bad
    lambda s: s.update(window="04:00-16:00 ET"),                     # skipped_window
    lambda s: s.update(symbol=""),                                   # skipped_bad
    lambda s: s.update(pick="other"),                                # skipped_bad
])
def test_NEGATIVE_a_malformed_or_skipped_sidecar_never_feeds_the_index(tmp_path, mutate):
    day_root(tmp_path, "BAD")
    s = single("BAD", "2026-11-10", cg=150.0)
    mutate(s)
    put(tmp_path, "winners", s, raw=json.dumps(s, allow_nan=True))
    assert ST.read_winner_sub("winners", tmp_path)["videos"] == []
    assert "past_winner" not in _by_sym(ST.payload(CARD_DAY, tmp_path))["BAD"]


def test_NEGATIVE_an_mp4_less_sidecar_and_the_non_sidecar_jsons_never_feed_the_index(tmp_path):
    day_root(tmp_path, "PART", "JOBS")
    put(tmp_path, "winners", single("PART", "2026-11-10"), mp4=False)
    d = tmp_path / C.VIDEOS_SUB / "winners"
    (d / "winners.json").write_text(json.dumps(single("JOBS", "2026-11-10")))
    (d / "jobs.json").write_text(json.dumps(single("JOBS", "2026-11-11")))
    by = _by_sym(ST.payload(CARD_DAY, tmp_path))
    assert "past_winner" not in by["PART"] and "past_winner" not in by["JOBS"]


def test_NEGATIVE_the_phone_copies_never_feed_the_index(tmp_path):
    day_root(tmp_path, "PHN")
    phone = tmp_path / C.VIDEOS_SUB / "multiday" / "phone"
    phone.mkdir(parents=True)
    s = multi("PHN", days=("2026-11-10", "2026-11-11"))
    (phone / s["file"]).write_bytes(b"x")
    (phone / s["file"].replace(".mp4", ".json")).write_text(json.dumps(s))
    assert "past_winner" not in _by_sym(ST.payload(CARD_DAY, tmp_path))["PHN"]


def test_NEGATIVE_the_cached_day_listing_is_never_mutated(tmp_path):
    day_root(tmp_path, "MEDS")
    meds_winners(tmp_path)
    assert "past_winner" in _by_sym(ST.payload(CARD_DAY, tmp_path))["MEDS"]
    assert all("past_winner" not in v for v in ST.read_day(CARD_DAY, tmp_path)["videos"])
    assert all("past_winner" not in v for sub in C.WINNER_SUB_KEYS
               for v in ST.read_winner_sub(sub, tmp_path)["videos"])


# ── cache ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_index_cached_until_a_winner_folder_key_moves(tmp_path, monkeypatch):
    day_root(tmp_path, "MEDS", "NEWW")
    meds_winners(tmp_path)
    calls = {"n": 0}
    real = ST.past_winner_index

    def counting(cards):
        calls["n"] += 1
        return real(cards)
    monkeypatch.setattr(ST, "past_winner_index", counting)
    ST.payload(CARD_DAY, tmp_path)
    ST.payload(CARD_DAY, tmp_path)
    assert calls["n"] == 1
    assert "past_winner" not in _by_sym(ST.payload(CARD_DAY, tmp_path))["NEWW"]
    d = put(tmp_path, "winners", single("NEWW", "2026-11-03", cg=130.0))
    st = os.stat(d)
    os.utime(d, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000_000))
    card = _by_sym(ST.payload(CARD_DAY, tmp_path))["NEWW"]
    assert calls["n"] == 2 and card["past_winner"][0]["text"] == "🏆 past winner 11-03 +130%"


# ── 🏆 cards: "won before" ────────────────────────────────────────────────────────────────────────────────────
def test_winner_cards_carry_their_earlier_wins_only(tmp_path):
    meds_winners(tmp_path)
    p = ST.winners_payload(tmp_path)
    by = {(v["sub"], v["date"]): v for v in _cards(p)}
    w16 = by[("winners", "2026-09-16")]
    assert [e["text"] for e in w16["past_winner"]] == ["🏆 won before 09-15 +87%"]
    assert w16["past_winner_count"] == 1 and w16["past_winner_more_text"] is None
    assert "past_winner" not in by[("winners", "2026-09-15")]        # NEGATIVE: never itself, never a later win
    assert "past_winner" not in by[("multiday", "2026-09-15")]       # NEGATIVE: the run started 09-14 — nothing earlier
    _strict(json.dumps(p, allow_nan=True))


def test_NEGATIVE_a_winner_card_never_tags_itself_or_a_same_day_twin(tmp_path):
    put(tmp_path, "winners", single("TWIN", "2026-11-12", cg=120.0))
    put(tmp_path, "multiday", multi("TWIN", days=("2026-11-12", "2026-11-13"), cg=90.0, gain_pct=150.0,
                                    file="2026-11-12_TWIN_45x.mp4"))
    assert all("past_winner" not in v for v in _cards(ST.winners_payload(tmp_path)))


def test_NEGATIVE_every_tag_string_is_free_of_the_b_word_and_edge(tmp_path):
    day_root(tmp_path, "MEDS")
    meds_winners(tmp_path)
    tagged = [v for p in (ST.payload(CARD_DAY, tmp_path), ST.winners_payload(tmp_path)) for v in _cards(p)
              if "past_winner" in v]
    assert len(tagged) == 2
    for v in tagged:
        for s in _strings({k: v[k] for k in v if k.startswith("past_winner")}):
            assert not BAD_WORDS.search(s), s


# ── route ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_owner_route_serves_the_tag_as_strict_json(tmp_path, monkeypatch):
    day_root(tmp_path, "MEDS")
    meds_winners(tmp_path)
    c = TestClient(_app(monkeypatch, tmp_path))
    body = _strict(c.get(C.API_PATH, params={"date": CARD_DAY}, headers=OWN).text)
    m = _by_sym(body)["MEDS"]
    assert m["past_winner_count"] == 1 and m["past_winner"][0]["text"] == "🏆 past winner 09-16 +601% multi-day"
    wbody = _strict(c.get(C.WINNERS_API_PATH, headers=OWN).text)
    assert any("past_winner" in v for v in _cards(wbody))


def test_source_pins_one_index_reusing_the_winner_reader():
    src = (PKG / "store.py").read_text(encoding="utf-8")
    blk = src[src.index("def past_winner_index"):src.index("def resolve_winner_video")]
    assert "read_winner_sub(" in blk and "_read_sidecar" not in blk and "open(" not in blk
    assert '"gain_pct"' not in blk and "C.PAST_WIN_MAX" in blk


# ── 2026-11-22 fixes: one entry per run · order · date (the RETO / GP / MEDS review) ─────────────────────────────
def test_RETO_single_day_inside_the_run_is_listed_once_as_the_run(tmp_path):
    day_root(tmp_path, "RETO")
    put(tmp_path, "winners", single("RETO", "2026-09-15", cg=300.0))
    put(tmp_path, "multiday", multi("RETO", days=("2026-09-14", "2026-09-15", "2026-09-16"), cg=676.27,
                                    gain_pct=5680.4, file="2026-09-15_RETO_45x.mp4", day="2026-09-15"))
    card = _by_sym(ST.payload(CARD_DAY, tmp_path))["RETO"]
    assert [e["text"] for e in card["past_winner"]] == ["🏆 past winner 09-16 +676% multi-day"]
    assert card["past_winner_count"] == 1


def test_GP_single_day_inside_a_later_ending_run_is_absorbed(tmp_path):
    day_root(tmp_path, "GP")
    put(tmp_path, "winners", single("GP", "2026-11-12", cg=120.0))
    put(tmp_path, "multiday", multi("GP", days=("2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14",
                                                "2026-11-17"), cg=484.56, gain_pct=656.36,
                                    file="2026-11-12_GP_45x.mp4", day="2026-11-12"))
    card = _by_sym(ST.payload(CARD_DAY, tmp_path))["GP"]
    assert [e["text"] for e in card["past_winner"]] == ["🏆 past winner 11-17 +485% multi-day"]


def test_NEGATIVE_a_single_day_outside_every_run_still_lists(tmp_path):
    day_root(tmp_path, "MEDS")
    meds_winners(tmp_path)
    put(tmp_path, "winners", single("MEDS", "2026-09-13", cg=110.0))          # the session BEFORE the run began
    put(tmp_path, "winners", single("MEDS", "2026-10-01", cg=150.0))
    card = _by_sym(ST.payload(CARD_DAY, tmp_path))["MEDS"]
    assert [e["text"] for e in card["past_winner"]] == ["🏆 past winner 10-01 +150%",
                                                        "🏆 past winner 09-16 +601% multi-day",
                                                        "🏆 past winner 09-13 +110%"]
    assert card["past_winner_count"] == 3 and card["past_winner_more_text"] is None


def test_NEGATIVE_two_separate_runs_list_twice(tmp_path):
    day_root(tmp_path, "OMH")
    put(tmp_path, "multiday", multi("OMH", days=("2026-08-19", "2026-08-20", "2026-08-26"), cg=25.9, gain_pct=153.9,
                                    file="2026-08-20_OMH_45x.mp4"))
    put(tmp_path, "multiday", multi("OMH", days=("2026-11-03", "2026-11-04", "2026-11-10"), cg=784.9,
                                    gain_pct=3139.7, file="2026-11-04_OMH_45x.mp4"))
    card = _by_sym(ST.payload(CARD_DAY, tmp_path))["OMH"]
    assert [e["text"] for e in card["past_winner"]] == ["🏆 past winner 11-10 +785% multi-day",
                                                        "🏆 past winner 08-26 +26% multi-day"]
    assert card["past_winner_count"] == 2


def test_NEGATIVE_a_run_not_yet_ended_absorbs_nothing(tmp_path):
    """The run ends AFTER the card day → it is not listed (no look-ahead), so its earlier single day still lists."""
    day_root(tmp_path, "GP", day="2026-11-15")
    put(tmp_path, "winners", single("GP", "2026-11-12", cg=120.0))
    put(tmp_path, "multiday", multi("GP", days=("2026-11-11", "2026-11-12", "2026-11-17"), cg=484.56,
                                    gain_pct=656.36, file="2026-11-12_GP_45x.mp4"))
    card = _by_sym(ST.payload("2026-11-15", tmp_path))["GP"]
    assert [e["text"] for e in card["past_winner"]] == ["🏆 past winner 11-12 +120%"]


def test_count_and_more_text_count_runs_not_reels(tmp_path):
    day_root(tmp_path, "CNT")
    for i, (a, b) in enumerate((("2026-10-01", "2026-10-02"), ("2026-10-05", "2026-10-06"),
                                ("2026-10-08", "2026-10-09"), ("2026-10-13", "2026-10-14"))):
        put(tmp_path, "multiday", multi("CNT", days=(a, b), cg=100.0 + i, gain_pct=900.0, file=f"{b}_CNT_45x.mp4"))
        put(tmp_path, "winners", single("CNT", b, cg=50.0))                    # inside its run → absorbed
    card = _by_sym(ST.payload(CARD_DAY, tmp_path))["CNT"]
    assert card["past_winner_count"] == 4 and card["past_winner_more_text"] == "+1 more"
    assert all(e["kind"] == "multi_day" for e in card["past_winner"])


def test_same_day_tie_orders_the_higher_close_gain_first(tmp_path):
    day_root(tmp_path, "TIE")
    put(tmp_path, "multiday", multi("TIE", days=("2026-10-08", "2026-10-09"), cg=100.0, gain_pct=900.0,
                                    file="2026-10-09_TIE_45x.mp4"))
    put(tmp_path, "multiday", multi("TIE", days=("2026-10-07", "2026-10-08", "2026-10-09"), cg=300.0, gain_pct=50.0,
                                    file="2026-10-08_TIE_45x.mp4"))
    card = _by_sym(ST.payload(CARD_DAY, tmp_path))["TIE"]
    assert [round(e["close_gain_pct"]) for e in card["past_winner"]] == [300, 100]   # NEGATIVE: never gain_pct order


def test_NEGATIVE_the_same_run_twice_is_listed_once():
    w = {"day": "2026-09-16", "kind": "multi_day", "close_gain_pct": 601.0, "sub": "multiday",
         "days": ("2026-09-14", "2026-09-15", "2026-09-16")}
    idx = {"MEDS": [{**w, "file": "a_45x.mp4"}, {**w, "file": "a_24x.mp4"}]}
    tag = ST.past_wins_before(idx, "MEDS", CARD_DAY, C.PAST_WIN_DAY_WORDS)
    assert tag["past_winner_count"] == 1 and tag["past_winner"][0]["file"] == "a_45x.mp4"


@pytest.mark.parametrize("card_day,win_day,shown", [
    ("2027-01-04", "2026-12-30", "2026-12-30"),       # another calendar year → full date
    ("2026-11-20", "2026-12-30", None),               # later → never listed
    ("2026-12-31", "2026-12-30", "12-30"),            # same year → MM-DD
])
def test_date_is_mm_dd_unless_another_year(tmp_path, card_day, win_day, shown):
    day_root(tmp_path, "YR", day=card_day)
    put(tmp_path, "winners", single("YR", win_day, cg=150.0))
    card = _by_sym(ST.payload(card_day, tmp_path))["YR"]
    if shown is None:
        assert "past_winner" not in card
    else:
        assert card["past_winner"][0]["text"] == f"🏆 past winner {shown} +150%"


def test_won_before_on_a_winner_card_uses_the_year_rule_too(tmp_path):
    put(tmp_path, "winners", single("YR", "2026-12-30", cg=150.0))
    put(tmp_path, "winners", single("YR", "2027-01-05", cg=200.0))
    by = {v["date"]: v for v in _cards(ST.winners_payload(tmp_path))}
    assert by["2027-01-05"]["past_winner"][0]["text"] == "🏆 won before 2026-12-30 +150%"
