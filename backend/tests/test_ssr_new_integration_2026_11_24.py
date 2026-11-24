"""⛔ SSR "new today" — the REAL engine into the REAL 🩳 block, and the ℹ️ clause (2026-11-24, SPEC ssrlist §4
main-session).

Ajay 2026-11-24, in order: "What are the SSR stocks today" · "Can you add it to short interest tab" · "The new ones".

`short_interest.ssr.new_triggers` over a fake collection (the ssr-core fakes, by import) is handed to
`chart_maps.gajjala.high_si.ssr_new_block` through its `ssr_read` seam — no stub in between. Pins: the kind and both
key tuples line up on the two sides; [C1] the block's "triggered again" count is the same at 15:00 and 20:01; [C7a]
`rules_info._gg_high_si_ssr_new_clause()` sits in the Gajjala note after the 🩳 clause and before the 🧾 line.
Every name is SYNTHETIC ("ZZ…"). Negatives are named test_NEGATIVE_*.
"""
from __future__ import annotations

import inspect
import json
import re

import pytest

from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala import tab as GT
from short_interest import read as SR
from short_interest import ssr as SSR
from short_interest import ssr_lists as SL
from supply_demand import rules_info as RI
from tests.test_gajjala_high_si_2026_11_23 import blk
from tests.test_gajjala_high_si_ssr_new_2026_11_24 import SPEC_NEW_KEYS, SPEC_NEW_ROW_KEYS
from tests.test_ssr_new_triggers_2026_11_24 import (D23, D24, Lists, _c1_fixture, fresh_day, read_corp, snap_doc)
from tests.test_ssr_rule_201_2026_11_24 import FakeColl, FakeDB, et, nasdaq_row, trig

HI, EX = SR.TIER_WORDS[SR.TIER_HIGH], SR.TIER_WORDS[SR.TIER_EXTREME]
TAIL = " UNMEASURED — no study here says these setups win. Not advice."
B_WORD = re.compile("b" + "ounc", re.I)

# the SI reads handed to the block (house `si_block` shapes, built by the 🩳 tests' own builder)
BLOCKS = {"ZZA": blk("ZZA", 600000, 2000000, 3000000),      # 30 % of float — EXTREME
          "ZZB": blk("ZZB", 10000, 2000000),                # 0.5 % — Low (tiered)
          "ZZC": blk("ZZC", 300000, 2000000),               # 15 % — High
          "ZZD": blk("ZZD", 153800, None)}                  # a share count only — no tier
LISTED = {"ZZA": {}, "ZZB": {}}


@pytest.fixture(autouse=True)
def _clean():
    SSR._reset_cache()
    SL._reset_cache()
    yield
    SSR._reset_cache()
    SL._reset_cache()


def _docs():
    """ZZA official on 11/23 + computed today (triggered again) · ZZB ZZC ZZD ZZE snapshot · ZZM minute bar ·
    ZZN an exchange row dated today with no doc."""
    return [snap_doc(D24, "ZZA", seen="11:00"), snap_doc(D24, "ZZB"), snap_doc(D24, "ZZC"), snap_doc(D24, "ZZD"),
            snap_doc(D24, "ZZE"),
            trig(D24, "ZZM", "minute_bar", at="10:00", low=2.5, drop_pct=-12.4, prev_close=2.85), fresh_day()]


def _lists():
    return Lists(rows=[nasdaq_row("ZZA", "2026-11-23", "09:31:00", file_date="2026-11-24"),
                       nasdaq_row("ZZN", "2026-11-24", "09:45:36", stamp="20261124163004")])


def real_read(docs=None, lists=None, corp=None, db="fake"):
    """The REAL engine as the block's `ssr_read` seam: (session, now) → ssr.new_triggers(session, now=now, …)."""
    calls = []

    def read(session, now):
        coll = FakeColl(_docs() if docs is None else docs)
        SSR._reset_cache()
        out = SSR.new_triggers(session, db=FakeDB(coll) if db == "fake" else db, now=now,
                               lists=lists if lists is not None else _lists(),
                               corp=corp if corp is not None else read_corp(D24))
        calls.append(out)
        return out
    read.calls = calls
    return read


def build(now=None, *, read=None, listed=LISTED, blocks=BLOCKS, si_calls=None):
    def si_read(syms):
        if si_calls is not None:
            si_calls.append(list(syms))
        return blocks
    return HS.ssr_new_block(listed, session=D24, now=now or et(D24, 15, 0), tf="5m",
                            ssr_read=read or real_read(), si_read=si_read)


def groups(b):
    return {g["key"]: g for g in b["groups"]}


def syms_of(g):
    return [r["symbol"] for r in g["rows"]]


def _texts(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _texts(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _texts(v)


# ═════════════════════════════════════════════ the two sides line up
def test_the_kind_and_both_key_tuples_are_one_contract():
    assert SSR.NEW_KIND == HS.SSR_NEW_KIND == "ssr_new_triggers"
    assert SSR.NEW_KEYS == SPEC_NEW_KEYS and SSR.NEW_ROW_KEYS == SPEC_NEW_ROW_KEYS   # the W2 stub cannot drift
    assert set(HS.SSR_NEW_COPIED) <= set(SSR.NEW_KEYS)                               # every copied text is served
    for k in ("rows", "status", "kind", "sources_text", "retriggered_text", "empty_text"):
        assert k in SSR.NEW_KEYS, k
    for k in ("symbol", "at_text", "drop_text", "source_text", "mark_text"):          # what the block reads per row
        assert k in SSR.NEW_ROW_KEYS, k
    read = real_read()
    b = build(read=read)
    eng = read.calls[-1]
    assert tuple(eng) == SSR.NEW_KEYS and all(tuple(r) == SSR.NEW_ROW_KEYS for r in eng["rows"])
    assert tuple(b) == HS.SSR_NEW_BLOCK_KEYS
    for g in b["groups"]:
        assert tuple(g) == HS.SSR_NEW_GROUP_KEYS
        assert all(tuple(r) == HS.SSR_NEW_ROW_KEYS for r in g["rows"])


# ═════════════════════════════════════════════ the real engine → the real block
def test_real_engine_into_real_block_four_folds_and_the_served_words():
    read = real_read()
    b = build(read=read)
    eng = read.calls[-1]
    assert eng["status"] == "ok" and eng["n"] == 7 and eng["n_retriggered"] == 1 and eng["n_official"] == 1
    g = groups(b)
    assert [x["key"] for x in b["groups"]] == list(HS.SSR_NEW_GROUPS)
    assert syms_of(g["list_high"]) == ["ZZA"] and syms_of(g["list_other"]) == ["ZZB"]
    assert syms_of(g["high"]) == ["ZZC"] and syms_of(g["rest"]) == ["ZZD", "ZZE", "ZZM", "ZZN"]
    assert g["list_high"]["summary"] == "🚩 on his list · %s or %s short interest — 1: ZZA" % (HI, EX)
    assert g["list_other"]["summary"] == "🚩 on his list · short interest under %s or not tiered — 1" % HI
    assert g["rest"]["summary"] == "every other name — 4 (4 not tiered)"
    assert b["counts_text"] == ("7 names · 2 on his 🚩 list (1 with %s or %s short interest) · 1 more with %s or %s "
                                "short interest · 4 others · 1 on an exchange list · 6 computed here · 1 were already "
                                "restricted and triggered again" % (HI, EX, HI, EX))
    assert b["n"] == 7 and b["n_untiered"] == 4
    assert b["tier_note"] == HS.SSR_NEW_TIER_NOTE.format(U=4, n=7, hi=HI, ex=EX)
    for k in HS.SSR_NEW_COPIED:                                                       # the engine's words, as served
        assert b[k] == (eng[k] if isinstance(eng[k], str) and eng[k].strip() else None), k
    assert b["title"] == "⛔ SSR — new today (Tue 11/24)" and b["fault_text"] is None and b["empty_text"] is None
    a = g["list_high"]["rows"][0]
    assert a["mark_text"] == "also triggered Mon 11/23" and a["at_text"] == "by 11:00 ET"
    assert a["source_text"] == "computed" and a["si_text"] == BLOCKS["ZZA"]["chip"]
    assert a["href"] == GT.chart_href("ZZA", "5m", None)
    rest = {r["symbol"]: r for r in g["rest"]["rows"]}
    assert rest["ZZN"]["source_text"] == "Nasdaq list" and rest["ZZN"]["at_text"] == "09:45:36 ET"
    assert rest["ZZN"]["drop_text"] is None and rest["ZZN"]["si_text"] is None
    assert rest["ZZM"]["at_text"] == "10:00 ET" and rest["ZZM"]["drop_text"] == "-12.4%"
    assert rest["ZZD"]["si_text"] == BLOCKS["ZZD"]["chip"]                            # the chip, untiered too [C2]
    json.dumps(b, allow_nan=False)


def test_NEGATIVE_no_served_text_carries_nan_none_or_the_b_word():
    b = build()
    for t in _texts(b):
        assert "nan" not in t.lower().split() and "None" not in t and not B_WORD.search(t), t


# ═════════════════════════════════════════════ [C1] the count never moves with the clock
@pytest.mark.parametrize("now", [et(D24, 19, 59), et(D24, 20, 1)])
def test_NEGATIVE_the_triggered_again_count_is_the_same_at_1500_and_after_2000(now):
    def run(clock):
        docs, lists, corp = _c1_fixture()
        return build(clock, read=real_read(docs=docs, lists=lists, corp=corp), listed={"ZZA": {}},
                     blocks={"ZZA": BLOCKS["ZZA"]})
    base, late = run(et(D24, 15, 0)), run(now)
    want = "1 were already restricted and triggered again"
    assert base["counts_text"].endswith(want) and late["counts_text"] == base["counts_text"]
    assert late["groups"] == base["groups"]
    assert groups(late)["list_high"]["rows"][0]["mark_text"] == "also triggered Mon 11/23"
    assert D23 not in SSR.in_play(et(D24, 20, 1))                    # the prior day left in-play; the count stands


# ═════════════════════════════════════════════ the engine's honest states ride through
def test_NEGATIVE_the_engine_failing_serves_its_fault_and_no_fold():
    si_calls = []
    b = build(read=real_read(db=None), si_calls=si_calls)
    assert b["fault_text"] == SSR.NEW_FAULT_TEXT % (SSR.GLYPH, SSR.TAG, "Tue 11/24")
    assert b["groups"] == [] and b["empty_text"] is None and b["n"] is None and b["n_untiered"] is None
    assert si_calls == []


def test_NEGATIVE_nothing_on_file_is_not_read_never_the_empty_line():
    b = build(read=real_read(docs=[], lists=Lists()))
    assert b["fault_text"] and "not read yet" in b["fault_text"] and b["empty_text"] is None and b["groups"] == []


def test_NEGATIVE_before_the_open_is_the_pre_open_sentence_and_no_si_read():
    si_calls = []
    b = build(et(D24, 8, 0), si_calls=si_calls)
    assert b["status_text"] and b["status_text"].startswith("No name can be new on Tue 11/24 yet")
    assert b["groups"] == [] and b["empty_text"] is None and b["n"] is None and si_calls == []


def test_a_fresh_scan_with_no_name_serves_the_engines_empty_line_and_no_si_read():
    si_calls = []
    b = build(read=real_read(docs=[fresh_day()], lists=Lists()), si_calls=si_calls)
    assert b["empty_text"] and b["empty_text"].startswith("No name has newly triggered it on Tue 11/24")
    assert b["groups"] == [] and b["n"] == 0 and si_calls == []


def test_NEGATIVE_the_list_read_never_writes_or_kicks():
    coll = FakeColl(_docs())
    lists = _lists()
    SSR._reset_cache()
    HS.ssr_new_block(LISTED, session=D24, now=et(D24, 15, 0), tf="5m", si_read=lambda s: BLOCKS,
                     ssr_read=lambda s, n: SSR.new_triggers(s, db=FakeDB(coll), now=n, lists=lists,
                                                            corp=read_corp(D24)))
    assert coll.writes == [] and lists.kicks == []


# ═════════════════════════════════════════════ [C7a] the ℹ️ clause
def _note():
    return RI._gajjala_section()["note"]


def test_the_clause_rides_the_note_after_the_high_si_clause_and_before_the_journal_line():
    clause = RI._gg_high_si_ssr_new_clause()
    assert clause == " " + HS.ssr_new_rules_line() and clause.startswith(" ⛔ New SSR names on the 🩳 High SI sub: ")
    note = _note()
    assert note.count(clause) == 1
    hs, journal = RI._gg_high_si_clause(), RI._gg_journal_clause()
    assert hs and journal
    assert note.index(hs) + len(hs) == note.index(clause)                 # right after the 🩳 clause
    assert note.index(clause) + len(clause) == note.index(journal)        # right before the 🧾 line
    assert note.endswith(RI._gg_audited_clause() + TAIL)


def test_the_clause_moves_with_the_tier_words(monkeypatch):
    monkeypatch.setitem(SR.TIER_WORDS, SR.TIER_HIGH, "SENTINELHIGH")
    assert "SENTINELHIGH" in RI._gg_high_si_ssr_new_clause() and "SENTINELHIGH" in _note()


def test_NEGATIVE_the_clause_types_no_digit_no_b_word_and_no_high_si_colon():
    clause = RI._gg_high_si_ssr_new_clause()
    assert not re.search(r"\d", clause) and not B_WORD.search(clause) and "🩳 High SI:" not in clause
    assert clause.endswith("UNMEASURED.")
    src = inspect.getsource(RI._gg_high_si_ssr_new_clause)
    assert "HS.ssr_new_rules_line()" in src and "four folds" not in src          # read, never retyped


def test_NEGATIVE_a_raising_rules_line_drops_only_the_clause(monkeypatch):
    before = _note()
    clause = RI._gg_high_si_ssr_new_clause()

    def boom():
        raise RuntimeError("synthetic")
    monkeypatch.setattr(HS, "ssr_new_rules_line", boom)
    assert RI._gg_high_si_ssr_new_clause() == ""
    after = _note()
    assert clause not in after and after == before.replace(clause, "", 1)
    assert after.endswith(RI._gg_audited_clause() + TAIL) and RI._gg_journal_clause() in after


@pytest.mark.parametrize("bad", [None, "", "   ", 7])
def test_NEGATIVE_an_empty_or_junk_rules_line_is_no_clause(monkeypatch, bad):
    monkeypatch.setattr(HS, "ssr_new_rules_line", lambda: bad)
    assert RI._gg_high_si_ssr_new_clause() == ""


def test_NEGATIVE_a_raising_push_text_still_leaves_no_high_si_colon_in_the_note(monkeypatch):
    def boom():
        raise RuntimeError("synthetic")
    monkeypatch.setattr(HS, "push_text", boom)
    note = _note()
    assert RI._gg_high_si_clause() == "" and "🩳 High SI:" not in note
    assert RI._gg_high_si_ssr_new_clause() in note                        # the ⛔ clause stands on its own


def test_NEGATIVE_nothing_lands_in_picks_stops_or_alerts():
    sec = RI._gajjala_section()
    body = " ".join(sec["picks"] + sec["stops"] + sec["alerts"])
    assert "New SSR names" not in body and "⛔ New" not in body


# ═════════════════════════════════════════════ the READ-ONLY report script
def _report():
    import importlib.util
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "scripts" / "ssr_new_list_report.py"
    spec = importlib.util.spec_from_file_location("ssr_new_list_report_under_test", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, p.read_text(encoding="utf-8")


def test_the_report_summary_counts_the_served_block():
    rep, _src = _report()
    read = real_read()
    b = build(read=read)
    s = rep.summary({"now": et(D24, 15, 0), "session": D24, "engine": read.calls[-1], "block": b, "ms_engine": 1.0,
                     "ms_block": 2.0, "listed_n": len(LISTED), "listed_ok": True})
    assert s["status"] == "ok" and s["n_rows"] == 7 and s["n_retriggered"] == 1 and s["n_official"] == 1
    assert s["folds"] == {"list_high": 1, "list_other": 1, "high": 1, "rest": 4}
    assert s["n_untiered"] == 4 and s["n_tiered"] == 3 and s["rows_with_si_text"] == 4
    assert [r["symbol"] for r in s["list_high_first_six"]] == ["ZZA"]
    assert s["withheld"] == {r: 0 for r in SSR.NEW_WITHHELD} and s["faults"] == 0
    assert s["block_bytes_raw"] > s["block_bytes_gzip"] > 0
    json.dumps(s, allow_nan=False)


def test_NEGATIVE_the_report_summary_of_a_faulted_block_is_counts_of_nothing():
    rep, _src = _report()
    s = rep.summary({"now": et(D24, 15, 0), "session": D24, "engine": None, "block": HS.ssr_new_fault(),
                     "ms_engine": None, "ms_block": 2.0, "listed_n": None, "listed_ok": False})
    assert s["status"] is None and s["folds"] == {} and s["n_tiered"] is None and s["rows_with_si_text"] == 0
    assert s["fault_text"] == HS.SSR_NEW_FAULT and s["ms_engine"] is None


def test_NEGATIVE_the_report_script_writes_nothing_and_kicks_nothing():
    _rep, src = _report()
    for bad in ("update_one", "update_many", "insert_one", "insert_many", "replace_one", "delete_", "kick_refresh", "refresh_one",
                "record_pass", ".payload(", "requests", "urlopen", "docker cp"):
        assert bad not in src, bad
    assert "ssr.new_triggers(" in src and "hs.ssr_new_block(" in src           # the REAL engine and the REAL block
