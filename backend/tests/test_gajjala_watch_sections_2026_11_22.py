"""🗂 Watch sections — group, order, the time line, the 📅 chip, the payload hook (spec watch_org rev 4 §3.3, WP-BE).

Ajay 2026-11-22, verbatim: "Manual ones I add them need to be on top then auto intraday.." · "I want to know previous day
winner auto additions vs intraday may be a time stamp".

NEGATIVES: no section key is ever "ran" [D3]; a 🤖 name that ran last session keeps its add-time place; groups never move
with the live card state, the A+ items, the entry's setup or the 📅 read [C2]; the `only` poll reads nothing new [C11];
the OFF switch serves the 11-21 payload byte for byte; every read fault fails soft per field; a sections fault leaves the
rows in their old order.
"""
from __future__ import annotations

import json
import sys
import types
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import tab
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import runners as RN
from chart_maps.gajjala_watch import sections as SE
from chart_maps.replays import constants as RC
from chart_maps.replays import store as RS
from tests.test_gajjala_watch_api_2026_11_15 import FRI_IN
from tests.test_gajjala_watch_auto_served_2026_11_17 import _entry
from tests.test_gajjala_watch_newest_2026_11_19 import _db, _syms, board  # noqa: F401 — `board` is a fixture

ET = ZoneInfo("America/New_York")
SESS = date(2026, 11, 13)                                                    # FRI_IN's session (Fri)
PREV = date(2026, 11, 12)


def _u(h, m, d=SESS):
    """An ET wall clock on `d` as the naive UTC Mongo hands back."""
    return datetime(d.year, d.month, d.day, h, m, tzinfo=ET).astimezone(timezone.utc).replace(tzinfo=None)


def _auto(sym, h, m, **kw):
    return dict(_entry(sym), added_at=_u(h, m), added_et=f"{h:02d}:{m:02d}", **kw)


def _ran(text="📅 ran Thu +97% (☀️ intraday peak)", counts=True):
    return {"date": PREV.isoformat(), "day": "Thu", "prev_close": 1.0, "high": 1.97, "run_pct": 97.0,
            "peak_et": "13:40", "timing": "intraday", "timing_text": "☀️ intraday", "pm_high_pct": 10.0,
            "premarket_peak": not counts, "counts": counts, "reg_close": 1.5, "text": text if counts else None,
            "title": "T"}


class RanSpy:
    def __init__(self, by=None, boom=False):
        self.calls, self.by, self.boom = [], by or {}, boom

    def __call__(self, names, day, st=None):
        self.calls.append((list(names), day))
        if self.boom:
            raise RuntimeError("scan store down")
        return dict(self.by)


@pytest.fixture()
def spies(monkeypatch):
    ran = RanSpy()
    past = {"n": 0, "idx": {}}

    def _pi(r):
        past["n"] += 1
        return past["idx"]
    monkeypatch.setattr(RN, "ran_for", ran)
    monkeypatch.setattr(RS, "_past_index", _pi)
    return types.SimpleNamespace(ran=ran, past=past)


# ── group_of ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_group_of_is_three_keys_only():
    assert SE.group_of(None) == "yours"
    assert SE.group_of({"why": C.AUTO_APLUS_WHY}) == "aplus"
    assert SE.group_of({"why": None}) == SE.group_of({}) == SE.group_of({"why": "ran"}) == "auto"
    assert C.SECTION_ORDER == ("yours", "aplus", "auto") and SE.RS_SETUP in GC.SETUPS


# ── when_block ────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("h,m,text,bucket", [(7, 12, "added premarket 07:12", "premarket"),
                                             (9, 30, "added 09:30", "intraday"),
                                             (15, 59, "added 15:59", "intraday"),
                                             (16, 0, "added after hours 16:00", "after_hours")])
def test_when_block_buckets(h, m, text, bucket):
    w = SE.when_block(_auto("X", h, m), None, SESS)
    assert w["text"] == text and w["bucket"] == bucket and w["verb"] == "added" and w["at_et"] == f"{h:02d}:{m:02d}"
    assert w["title"] == C.WHEN_TITLE.format(verb="added", date="11-13", at=w["at_et"], where=C.WHEN_WHERE[bucket])
    assert set(w) == {"bucket", "verb", "at_et", "date", "text", "title"}


def test_when_block_half_day_13_05_is_after_hours_and_added_et_fallback():
    half = date(2026, 11, 27)
    e = dict(_entry("X"), added_at=_u(13, 5, half))
    assert SE.when_block(e, None, half)["text"] == "added after hours 13:05"
    e2 = _entry("X", added_et="08:01")
    e2.pop("added_at")
    assert SE.when_block(e2, None, SESS)["text"] == "added premarket 08:01"
    e3 = _entry("X")
    e3.pop("added_at")
    e3["added_et"] = "junk"
    assert SE.when_block(e3, None, SESS) is None


def test_when_block_readd_and_his_names():
    w = SE.when_block(_auto("X", 10, 21), None, SESS, "09:40")
    assert w["text"] == "re-added 10:21" and w["title"].endswith(C.WHEN_READD_TITLE.format(rm_at="09:40"))
    his_today = datetime(2026, 11, 13, 8, 15, tzinfo=ET).astimezone(timezone.utc)
    assert SE.when_block(None, his_today, SESS)["text"] == "👤 added 08:15"
    his_before = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)
    assert SE.when_block(None, his_before, SESS)["text"] == "👤 added 11-11"
    assert SE.when_block(None, None, SESS)["text"] == C.WHEN_HIS_UNDATED


def test_removed_at_is_fold_matched_and_before_the_add():
    rm = [{"symbol": "brk-b", "at": _u(9, 40), "at_et": "09:40"}, {"symbol": "BRK.B", "at": _u(11, 0), "at_et": "11:00"},
          {"symbol": "OTHER", "at": _u(9, 0), "at_et": "09:00"}]
    assert SE._removed_at(rm, "BRK.B", datetime(2026, 11, 13, 10, 21, tzinfo=ET)) == "09:40"
    assert SE._removed_at(rm, "NONE", None) is None


# ── setup / past ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_setup_block_picks_the_squeeze_first():
    row = {"tags": {"setups": [{"setup": "kiss_fly", "state_label": "armed"},
                               {"setup": "reversal_squeeze", "state_label": "building"}]}}
    b = SE.setup_block(row, None)
    lab = tab._setup_label("reversal_squeeze")
    assert b == {"setup": "reversal_squeeze", "label": lab, "state_label": "building", "source": "board",
                 "text": lab, "title": "building"}
    assert SE.setup_block({"tags": None}, {"setup": "bull_flag"})["setup"] == "bull_flag"
    assert SE.setup_block({"tags": None}, {"setup": "reversal_squeeze"})["source"] == "entry"
    assert SE.setup_block({"tags": None}, None) is None and SE.setup_block({}, {"setup": "junk"}) is None


def test_past_block_wins_before_the_session_only():
    sub = RC.WINNER_SUB_KEYS[0]
    idx = RS.past_winner_index([{"symbol": "OMH", "days": [d], "kind": "single_day", "close_gain_pct": g, "file": f,
                                 "sub": sub} for d, g, f in (("2026-11-13", 300.0, "a.mp4"),
                                                             ("2026-11-10", 97.0, "b.mp4"))])
    b = SE.past_block(idx, "OMH", SESS.isoformat())
    assert b["text"] == f"{RC.PAST_WIN_DAY_WORDS} 11-10 +97%" and b["past_winner_count"] == 1
    assert "300" not in json.dumps(b, ensure_ascii=False)
    assert SE.past_block(idx, "NVDA", SESS.isoformat()) is None and SE.past_block({}, "OMH", "2026-11-13") is None


# ── order + sections ──────────────────────────────────────────────────────────────────────────────────────────────
def _rows(*syms):
    return [{"symbol": s} for s in syms]


def test_order_his_then_aplus_newest_then_auto_newest_undated_last():
    ents = {"A1": _auto("A1", 9, 0), "A2": _auto("A2", 11, 0), "U": dict(_entry("U"), added_at=None),
            "P1": _auto("P1", 7, 0, why=C.AUTO_APLUS_WHY, aplus_at=_u(10, 0)),
            "P2": _auto("P2", 8, 0, why=C.AUTO_APLUS_WHY, aplus_at=_u(10, 30))}
    rows = _rows("H2", "H1", "A1", "U", "P1", "A2", "P2")
    groups = {r["symbol"]: SE.group_of(ents.get(r["symbol"])) for r in rows}
    assert [r["symbol"] for r in SE.order(rows, groups, ents)] == ["H2", "H1", "P2", "P1", "A2", "A1", "U"]


def test_NEGATIVE_D3_a_ran_name_keeps_its_add_time_place(spies):
    spies.ran.by = {"OLD": _ran()}
    ents = {"OLD": _auto("OLD", 7, 12), "NEW": _auto("NEW", 10, 42)}
    rows, secs = SE.apply(_rows("OLD", "NEW"), entries=ents, removed=[], his_added={}, session=SESS)
    assert [r["symbol"] for r in rows] == ["NEW", "OLD"]
    assert rows[1]["org"]["group"] == "auto" and rows[1]["org"]["ran"]["text"].startswith("📅 ran Thu")
    assert [s["key"] for s in secs] == ["auto"] and all(s["key"] != "ran" for s in secs)
    assert spies.ran.calls == [(["OLD", "NEW"], PREV)]                                 # the session before the board's


def test_sections_block_words():
    rows = [{"symbol": "H", "org": {"group": "yours"}}, {"symbol": "P", "org": {"group": "aplus"}},
            {"symbol": "A", "org": {"group": "auto"}}, {"symbol": "B", "org": {"group": "auto"}}]
    secs = SE.sections_block(rows, session=SESS)
    assert [s["key"] for s in secs] == ["yours", "aplus", "auto"]
    assert secs[2] == {"key": "auto", "title": C.SECTION_WORDS["auto"], "text": "🤖 Added today · 2",
                       "hint": C.SECTION_HINTS["auto"].format(date="11-12"), "n": 2, "symbols": ["A", "B"]}
    assert SE.sections_block([], session=SESS) == []


# ── the payload hook ──────────────────────────────────────────────────────────────────────────────────────────────
def _board_db(**kw):
    autos = [_auto("ZZT", 7, 12), _auto("MMM", 10, 42), _auto("AAA", 9, 0, why=C.AUTO_APLUS_WHY, aplus_at=_u(9, 50))]
    return _db(["OMH", "NVDA"], {"OMH": datetime(2026, 11, 13, 13, 15), "NVDA": datetime(2026, 11, 11, 15, 0)},
               entries=kw.get("entries", autos))


def test_board_serves_sections_and_org(board, spies):
    spies.ran.by = {"ZZT": _ran(), "OMH": _ran(counts=False)}
    out = PL.build(FRI_IN, db=_board_db())
    assert _syms(out) == ["OMH", "NVDA", "AAA", "MMM", "ZZT"]
    assert [s["key"] for s in out["sections"]] == ["yours", "aplus", "auto"]
    assert [s["symbols"] for s in out["sections"]] == [["OMH", "NVDA"], ["AAA"], ["MMM", "ZZT"]]
    rows = {r["symbol"]: r for r in out["rows"]}
    assert set(rows["OMH"]["org"]) == {"group", "when", "setup", "ran", "past_winner"}
    assert rows["OMH"]["org"]["when"]["text"] == "👤 added 08:15"
    assert rows["NVDA"]["org"]["when"]["text"] == "👤 added 11-11"
    assert rows["ZZT"]["org"]["when"]["text"] == "added premarket 07:12"
    assert rows["MMM"]["org"]["when"]["text"] == "added 10:42"
    assert rows["ZZT"]["org"]["ran"]["text"] == "📅 ran Thu +97% (☀️ intraday peak)"
    assert rows["OMH"]["org"]["ran"]["text"] is None                                   # drawer title only, no chip
    assert rows["ZZT"]["org"]["setup"]["setup"] == "kiss_fly"
    assert len(spies.ran.calls) == 1 and spies.past["n"] == 1
    assert out["symbols"] == ["OMH", "NVDA"]                                            # his list untouched
    json.loads(json.dumps(out, default=str))


def test_readded_name_says_so(board, spies, monkeypatch):
    db = _board_db()
    db[C.COLL_LIST].docs[C.AUTO_DOC_ID]["removed"] = [{"symbol": "MMM", "at": _u(9, 40), "at_et": "09:40",
                                                       "reason": "dismissed", "text": "x"}]
    rows = {r["symbol"]: r for r in PL.build(FRI_IN, db=db)["rows"]}
    assert rows["MMM"]["org"]["when"]["text"] == "re-added 10:42"
    assert rows["ZZT"]["org"]["when"]["verb"] == "added"


def test_NEGATIVE_only_poll_reads_nothing_new(board, spies):
    out = PL.build(FRI_IN, db=_board_db(), only=["OMH", "ZZT"])
    assert out["sections"] is None and all(r["org"] is None for r in out["rows"])
    assert spies.ran.calls == [] and spies.past["n"] == 0


def test_NEGATIVE_off_is_the_11_21_payload_byte_for_byte(board, spies, monkeypatch):
    monkeypatch.setattr(C, "SECTIONS_ON", False)
    off = PL.build(FRI_IN, db=_board_db())
    assert "sections" not in off and all("org" not in r for r in off["rows"])
    assert _syms(off) == ["OMH", "NVDA", "ZZT", "MMM", "AAA"]                          # the stored 🤖 order
    assert spies.ran.calls == [] and spies.past["n"] == 0
    monkeypatch.setattr(C, "SECTIONS_ON", True)
    monkeypatch.setitem(sys.modules, PL.SECTIONS_MODULE, types.SimpleNamespace())      # no `apply` → the fault path
    on = PL.build(FRI_IN, db=_board_db())
    assert on["sections"] is None and all(r["org"] is None for r in on["rows"])
    for r in on["rows"]:
        r.pop("org")
    on.pop("sections")
    assert json.dumps(on, default=str, sort_keys=False) == json.dumps(off, default=str, sort_keys=False)


def test_NEGATIVE_read_faults_fail_soft_per_field(board, monkeypatch):
    monkeypatch.setattr(RN, "ran_for", RanSpy(boom=True))
    monkeypatch.setattr(RS, "_past_index", lambda r: 1 / 0)
    out = PL.build(FRI_IN, db=_board_db())
    assert [s["key"] for s in out["sections"]] == ["yours", "aplus", "auto"]
    assert all(r["org"]["ran"] is None and r["org"]["past_winner"] is None for r in out["rows"])
    assert _syms(out) == ["OMH", "NVDA", "AAA", "MMM", "ZZT"]


def test_NEGATIVE_C2_groups_never_move_with_live_state(board, spies, monkeypatch):
    a = PL.build(FRI_IN, db=_board_db())
    spies.ran.by = {"ZZT": _ran(), "MMM": _ran(), "AAA": _ran()}
    ents = [dict(_auto("ZZT", 7, 12), setup="reversal_squeeze", kind="armed"), _auto("MMM", 10, 42),
            _auto("AAA", 9, 0, why=C.AUTO_APLUS_WHY, aplus_at=_u(9, 50), setup="bull_flag")]
    monkeypatch.setattr(PL, "aplus_section", lambda names, siso, stores=None: {n: {"tag": "🎯", "text": "🎯 A+",
                                                                                  "items": [], "title": "t"}
                                                                              for n in names})
    monkeypatch.setattr(PL, "_tags_section", lambda names, s, t: {n: {"setups": [{"setup": "reversal_squeeze"}]}
                                                                    for n in names})
    b = PL.build(FRI_IN, db=_board_db(entries=ents))
    assert _syms(a) == _syms(b)
    assert [r["org"]["group"] for r in a["rows"]] == [r["org"]["group"] for r in b["rows"]]
    assert [s["symbols"] for s in a["sections"]] == [s["symbols"] for s in b["sections"]]


def test_NEGATIVE_no_ran_key_ever_served(board, spies):
    spies.ran.by = {s: _ran() for s in ("OMH", "NVDA", "ZZT", "MMM", "AAA")}
    out = PL.build(FRI_IN, db=_board_db())
    assert all(s["key"] != "ran" for s in out["sections"])
    assert all(r["org"]["group"] in C.SECTION_KEYS for r in out["rows"])


def test_NEGATIVE_a_grouping_fault_keeps_the_old_order(board, spies, monkeypatch):
    monkeypatch.setattr(SE, "order", lambda *a, **k: 1 / 0)
    out = PL.build(FRI_IN, db=_board_db())
    assert _syms(out) == ["OMH", "NVDA", "ZZT", "MMM", "AAA"] and out["sections"] is None
    assert all(r["org"] is None for r in out["rows"])


def test_setup_block_matches_the_fe_golden():
    """Review 11-22 finding 1: the FE's parseSetupTag needs `text`. This golden is read by
    frontend/src/lib/gajjalaWatch.setupGolden.test.ts — both sides pin the SAME served shape."""
    import json as _json
    import os as _os
    gold = _os.path.join(_os.path.dirname(__file__), "..", "..", "frontend", "src", "lib", "__fixtures__",
                         "ggwSetupBlock.golden.json")
    row = {"tags": {"setups": [{"setup": "reversal_squeeze", "state_label": "armed"}]}}
    got = SE.setup_block(row, None)
    with open(gold, encoding="utf-8") as fh:
        assert _json.load(fh) == got
    assert isinstance(got["text"], str) and got["text"]


def test_NEGATIVE_setup_block_without_a_setup_serves_no_text():
    assert SE.setup_block({"tags": {"setups": [{"setup": "junk"}]}}, {"setup": "nope"}) is None
