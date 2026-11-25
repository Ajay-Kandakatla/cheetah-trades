"""✅ All rules met → 👀 Watch — the served ✅ section: payload rows, the board's `rules` key, the section words and the FE
goldens (spec watchall rev 2 §3.5, WP be-payload, 2026-11-24).

Ajay 2026-11-24, verbatim: "Anytime stocks qualify all his rules should be auto added to the Watch list so I can keep
tracking them later".

The ✅ ENGINE (`chart_maps.gajjala_watch.allrules`, WP be-engine) is the real module: the payload reads it lazily through
sys.modules (`read_doc` + `entries_in_window`), so a test that wants a fault replaces that module entry.

NEGATIVES: his name that is also ✅ is served once, in 👤; a 🎯 A+ seat / 🤖 potential that is also ✅ is served once, in
its seat — and in ✅ once the auto doc drops it; an entry outside the keep window (a weekend board included) is never
served; an unreadable / raising / missing engine serves `rules.state "unreadable"` + every other row — never `error`;
RULES_ON False serves no `rules` key and the payload of the 11-24 build byte for byte; no other section carries
`folded_default`; a NaN volume / count serves no number (`allow_nan=False` dumps); a ✅ row never fills his ➕ cap.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import types
from datetime import date, datetime

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import sections as SE
from tests.test_gajjala_watch_api_2026_11_15 import FRI_IN, SESSION, SUN, RecColl, _doc
from tests.test_gajjala_watch_newest_2026_11_19 import _db, _syms, board  # noqa: F401 — `board` is a fixture
from tests.test_gajjala_watch_sections_2026_11_22 import PREV, SESS, _auto, _u, spies  # noqa: F401 — `spies` too

GOLD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "lib", "__fixtures__")
GOLD = os.path.join(GOLD_DIR, "ggwAllRules.golden.json")
GOLD90 = os.path.join(GOLD_DIR, "ggwAllRules90.golden.json")
GOLD_WRITE = os.environ.get("GGW_GOLDEN_WRITE") == "1"                     # regenerate: GGW_GOLDEN_WRITE=1 pytest …
PIN_KEYS = ("state", "session", "symbols", "rows", "sections", "rules", "auto")   # the keys both sides pin
WED, MON, PREV_FRI = date(2026, 11, 11), date(2026, 11, 9), date(2026, 11, 6)    # SESS = Fri 11-13; window Mon–Fri


def _rule(sym, h=10, m=42, *, day=SESS, first=None, sessions=None, kind="armed", setup="kiss_fly",
          volume=2_000_000.0, volume_source="tracker", sources=("gajjala", "gga")):
    """One stored ✅ entry (spec §3.2) — last met at h:m ET on `day`; `first` = (h, m, day) of the first met."""
    fh, fm, fd = first if first is not None else (h, m, day)
    return {"symbol": sym, "kind": kind, "setup": setup, "setups": [setup], "sources": list(sources),
            "volume": volume, "volume_source": volume_source,
            "first_met_at": _u(fh, fm, fd), "first_met_session": fd.isoformat(),
            "last_met_at": _u(h, m, day), "last_met_session": day.isoformat(),
            "sessions": sessions if sessions is not None else sorted({fd.isoformat(), day.isoformat()}),
            "added_at": _u(fh, fm, fd)}


def _with_rules(db, entries, **extra):
    db[C.COLL_LIST].docs[C.RULES_DOC_ID] = dict({"_id": C.RULES_DOC_ID, "rev": 1, "entries": list(entries),
                                                  "dismissed": [], "removed": []}, **extra)
    return db


def _state(db, **blk):
    db[C.COLL_STATE] = RecColl([{"_id": C.STATE_LATEST_ID, "session": blk.pop("session", SESSION), "rules": blk}])
    return db


def _quiet_broker(out, state_doc, siso):
    for r in out.get("rows") or []:
        r["broker_text"] = None
    out["broker"] = None


@pytest.fixture(autouse=True)
def quiet(monkeypatch, board, spies):
    """Every other display read stubbed (deterministic, hermetic): tags / float / levels {} and no broker list read."""
    monkeypatch.setattr(PL, "_tags_section", lambda names, s, t: {})
    monkeypatch.setattr(PL, "_float_section", lambda names, s, now, tags: {})
    monkeypatch.setattr(PL, "_levels_section", lambda *a, **k: {})
    monkeypatch.setattr(PL, "_broker_section", _quiet_broker)
    return board


def _board_db(rules=(), *, autos=None, his=("OMH", "NVDA")):
    autos = autos if autos is not None else [_auto("ZZT", 7, 12), _auto("MMM", 10, 42),
                                             _auto("AAA", 9, 0, why=C.AUTO_APLUS_WHY, aplus_at=_u(9, 50))]
    db = _db(list(his), {"OMH": datetime(2026, 11, 13, 13, 15), "NVDA": datetime(2026, 11, 11, 15, 0)}, entries=autos)
    return _with_rules(db, rules)


def _rows(out):
    return {r["symbol"]: r for r in out["rows"]}


def _dumps(out):
    return json.dumps(out, ensure_ascii=False, allow_nan=False)


# ── the constants this package codes against (be-engine owns them) ─────────────────────────────────────────────────
def test_section_keys_and_seams():
    # RE-PINNED 2026-11-24 (spec sissr §3.6) — ⛔🩳🔒 "sissr" appended after "rules" (folded too)
    assert C.SECTION_KEYS == ("yours", "aplus", "auto", "rules", "sissr") and C.SECTION_ORDER == C.SECTION_KEYS
    assert PL.RULES_WHY == C.SECTION_KEYS[3] == "rules"                       # the FE reads `auto.why === 'rules'`
    assert C.SECTIONS_FOLDED_DEFAULT == (C.SECTION_KEYS[3], C.SECTION_KEYS[4])
    assert PL.RULES_STATES[:2] == PL.AUTO_STATES and PL.RULES_MODULE == "chart_maps.gajjala_watch.allrules"
    assert importlib.import_module(PL.RULES_MODULE).read_doc is not None


# ── POSITIVE: served rows, order, words ──────────────────────────────────────────────────────────────────────────────
def test_rules_rows_served_last_newest_met_first():
    rules = [_rule("RON", 9, 41), _rule("RTW", 11, 5), _rule("ROLD", 15, 0, day=WED)]
    out = PL.build(FRI_IN, db=_board_db(rules))
    assert out["state"] == "ok"
    assert _syms(out) == ["OMH", "NVDA", "AAA", "MMM", "ZZT", "RTW", "RON", "ROLD"]
    assert [s["key"] for s in out["sections"]] == ["yours", "aplus", "auto", "rules"]
    assert out["sections"][-1]["symbols"] == ["RTW", "RON", "ROLD"] and out["sections"][-1]["n"] == 3
    rows = _rows(out)
    for s in ("RTW", "RON", "ROLD"):
        assert rows[s]["org"]["group"] == "rules" and rows[s]["auto"]["why"] == "rules"
    assert out["symbols"] == ["OMH", "NVDA"] and out["full"] is False                # his list / cap untouched
    _dumps(out)


def test_rules_row_block_is_the_auto_shape():
    out = PL.build(FRI_IN, db=_board_db([_rule("RON", 9, 41, first=(8, 5, WED), sessions=["2026-11-11", "2026-11-13"])]))
    r = _rows(out)["RON"]
    auto_keys = set(_rows(out)["MMM"]["auto"])
    assert set(r["auto"]) == auto_keys
    assert r["auto"] == {
        "tag": C.RULES_TAG, "sources": ["gajjala", "gga"],
        "source_words": [C.AUTO_SOURCE_WORDS["gajjala"], C.AUTO_SOURCE_WORDS["gga"]],
        "text": PL.RULES_ROW_TEXT.format(tag=C.RULES_TAG, sources=" · ".join([C.AUTO_SOURCE_WORDS["gajjala"],
                                                                             C.AUTO_SOURCE_WORDS["gga"]]),
                                         setup=PL._setup_word("kiss_fly")),
        "volume_text": PL.auto_volume_text(2_000_000.0, "tracker"), "volume_source": "tracker",
        "added_et": "2026-11-11 08:05", "added_text": PL.RULES_ADDED_TEXT.format(first="2026-11-11 08:05", last="09:41"),
        "leaving_text": None, "remove_title": PL.RULES_REMOVE_TITLE.format(sym="RON"), "why": "rules"}
    assert r["added_at"] == "2026-11-11T13:05:00.000+00:00"
    assert r["aplus"] is None


def test_when_today_earlier_day_and_sessions():
    rules = [_rule("RON", 10, 42), _rule("ROLD", 15, 0, day=WED),
             _rule("RTWO", 9, 31, first=(10, 0, MON), sessions=["2026-11-09", "2026-11-13", "2026-11-13"])]
    rows = _rows(PL.build(FRI_IN, db=_board_db(rules)))
    assert rows["RON"]["org"]["when"]["text"] == "✅ all rules 10:42"
    assert rows["ROLD"]["org"]["when"]["text"] == "✅ all rules 11-11"
    assert rows["RTWO"]["org"]["when"]["text"] == "✅ all rules 09:31 · 2 sessions"              # distinct sessions
    w = rows["RTWO"]["org"]["when"]
    assert w["title"] == C.RULES_WHEN_TITLE.format(first="11-09 10:00", kind="trigger armed",
                                                   setup=SE._rules_setup_word("kiss_fly"), last="11-13 09:31")
    assert set(w) == {"bucket", "verb", "at_et", "date", "text", "title"} and w["date"] == "2026-11-13"
    assert rows["RON"]["org"]["setup"]["setup"] == "kiss_fly" and rows["RON"]["org"]["setup"]["source"] == "entry"


def test_aplus_kind_words_in_the_title():
    w = SE.rules_when_block(_rule("X", 10, 0, kind=C.RULES_KINDS[1]), SESS)
    assert "(" + C.SECTION_WORDS["aplus"] + ")" in w["title"]
    assert SE.rules_when_block(_rule("X", 10, 0, kind="junk", setup="nope"), SESS)["title"].count("—") >= 2


def test_rules_board_key_and_section_folded_default():
    db = _state(_board_db([_rule("RON")]), not_eligible=["HUHU", "MRM", "huhu"])
    out = PL.build(FRI_IN, db=db)
    # RE-PINNED 2026-11-24 (spec sissr §3.6) — ⛔🩳🔒 the head gains sissr_n / sissr_not_eligible_n [C5]
    assert out["rules"] == {"state": "ok", "n": 1, "keep_sessions": C.RULES_KEEP_SESSIONS, "text": None,
                            "not_seated_n": 2, "sissr_n": 0, "sissr_not_eligible_n": 0}
    sec = {s["key"]: s for s in out["sections"]}
    assert sec["rules"]["folded_default"] is True
    assert all("folded_default" not in sec[k] for k in ("yours", "aplus", "auto"))
    hint = sec["rules"]["hint"]
    assert hint == C.SECTION_HINTS["rules"].format(
        boards=PL._and([C.AUTO_SOURCE_WORDS.get(k) for k in PL._active_sources()]),
        floor=int(C.RULES_MIN_VOLUME), keep=C.RULES_KEEP_SESSIONS, not_seated=C.RULES_NOT_SEATED.format(n=2))
    assert f"{int(C.RULES_MIN_VOLUME):,}" in hint and "{" not in hint
    assert sec["rules"]["title"] == C.SECTION_WORDS["rules"] and sec["rules"]["text"] == "✅ All rules met · 1"


def test_not_seated_count_forms():
    assert PL.rules_not_seated({"session": SESSION, "rules": {"not_eligible": 3}}, SESSION) == 3
    assert PL.rules_not_seated({"session": SESSION, "rules": {"not_eligible": ["A", "a", "", 4]}}, SESSION) == 1


# ── NEGATIVE: one row per name (precedence) ──────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_his_name_also_rules_is_once_in_yours():
    out = PL.build(FRI_IN, db=_board_db([_rule("omh"), _rule("RON")]))
    assert _syms(out).count("OMH") == 1 and _rows(out)["OMH"]["auto"] is None
    assert _rows(out)["OMH"]["org"]["group"] == "yours"
    assert out["rules"]["n"] == 1 and out["sections"][-1]["symbols"] == ["RON"]


def test_NEGATIVE_aplus_and_auto_seats_win_over_rules_then_rules_after_the_drop():
    out = PL.build(FRI_IN, db=_board_db([_rule("AAA"), _rule("MMM"), _rule("RON")]))
    rows = _rows(out)
    assert _syms(out).count("AAA") == 1 and rows["AAA"]["org"]["group"] == "aplus" and rows["AAA"]["auto"]["why"] == "aplus"
    assert _syms(out).count("MMM") == 1 and rows["MMM"]["org"]["group"] == "auto"
    assert rows["MMM"]["auto"]["why"] == "potential" and out["rules"]["n"] == 1
    dropped = PL.build(FRI_IN, db=_board_db([_rule("AAA"), _rule("MMM"), _rule("RON")],
                                            autos=[_auto("ZZT", 7, 12)]))           # ↩️/✖️ / 04:00 reset: 🤖 lost them
    rows = _rows(dropped)
    assert [s["key"] for s in dropped["sections"]] == ["yours", "auto", "rules"]
    assert all(rows[s]["org"]["group"] == "rules" and rows[s]["auto"]["why"] == "rules" for s in ("AAA", "MMM", "RON"))
    assert dropped["rules"]["n"] == 3 and len(_syms(dropped)) == len(set(_syms(dropped)))


def test_NEGATIVE_fold_duplicates_in_the_rules_doc_serve_once():
    out = PL.build(FRI_IN, db=_board_db([_rule("BRK-B", 10, 0), _rule("BRK.B", 11, 0), {"symbol": ""}, "junk"]))
    assert [s for s in _syms(out) if s.startswith("BRK")] == ["BRK.B"]


def test_NEGATIVE_outside_the_window_is_never_served():
    out = PL.build(FRI_IN, db=_board_db([_rule("RIN", day=MON), _rule("ROUT", day=PREV_FRI)]))
    assert "RIN" in _syms(out) and "ROUT" not in _syms(out)
    sun = PL.build(SUN, db=_board_db([_rule("RIN", day=MON), _rule("ROUT", day=PREV_FRI)]))   # weekend: loop not run
    assert sun["state"] == "ok" and "RIN" in _syms(sun) and "ROUT" not in _syms(sun)
    assert _rows(sun)["RIN"]["org"]["when"]["text"] == "✅ all rules 11-09"


@pytest.mark.parametrize("how", ["none", "raises", "missing_engine"])
def test_NEGATIVE_unreadable_rules_doc_keeps_every_other_row(monkeypatch, how):
    db = _board_db([_rule("RON")])
    if how == "none":
        mod = importlib.import_module(PL.RULES_MODULE)
        monkeypatch.setattr(mod, "read_doc", lambda cs: None)
    elif how == "raises":
        mod = importlib.import_module(PL.RULES_MODULE)
        monkeypatch.setattr(mod, "entries_in_window", lambda d, s: 1 / 0)
    else:
        monkeypatch.setitem(sys.modules, PL.RULES_MODULE, types.SimpleNamespace())
    out = PL.build(FRI_IN, db=db)
    assert out["state"] == "ok"
    assert _syms(out) == ["OMH", "NVDA", "AAA", "MMM", "ZZT"]
    # RE-PINNED 2026-11-24 (spec sissr §3.6) — ⛔🩳🔒 the head gains sissr_n / sissr_not_eligible_n [C5]
    assert out["rules"] == {"state": "unreadable", "n": 0, "keep_sessions": C.RULES_KEEP_SESSIONS,
                            "text": PL.RULES_UNREADABLE_TEXT, "not_seated_n": 0, "sissr_n": 0,
                            "sissr_not_eligible_n": 0}
    assert [s["key"] for s in out["sections"]] == ["yours", "aplus", "auto"]


def test_NEGATIVE_a_list_read_fault_on_the_rules_doc_only():
    db = _board_db([_rule("RON")])

    class Flaky(type(db[C.COLL_LIST])):
        def find_one(self, q=None, projection=None):
            if (q or {}).get("_id") == C.RULES_DOC_ID:
                raise RuntimeError("rules doc down")
            return super().find_one(q, projection)
    flaky = Flaky(list(db[C.COLL_LIST].docs.values()))
    db[C.COLL_LIST] = flaky
    out = PL.build(FRI_IN, db=db)
    assert out["state"] == "ok" and out["rules"]["state"] == "unreadable" and "RON" not in _syms(out)


def test_NEGATIVE_missing_rules_doc_is_ok_and_empty():
    db = _board_db()
    db[C.COLL_LIST].docs.pop(C.RULES_DOC_ID)
    out = PL.build(FRI_IN, db=db)
    # RE-PINNED 2026-11-24 (spec sissr §3.6) — ⛔🩳🔒 the head gains sissr_n / sissr_not_eligible_n [C5]
    assert out["rules"] == {"state": "ok", "n": 0, "keep_sessions": C.RULES_KEEP_SESSIONS, "text": None,
                            "not_seated_n": 0, "sissr_n": 0, "sissr_not_eligible_n": 0}
    assert [s["key"] for s in out["sections"]] == ["yours", "aplus", "auto"]


def test_NEGATIVE_rules_off_is_the_11_24_payload_byte_for_byte(monkeypatch):
    base = PL.build(FRI_IN, db=_board_db())                     # no ✅ entry: the 11-24 board + the `rules` key
    assert base["rules"]["n"] == 0
    base.pop("rules")
    monkeypatch.setattr(C, "RULES_ON", False)
    monkeypatch.setattr(PL, "rules_section", lambda *a, **k: 1 / 0)     # never called while off
    off = PL.build(FRI_IN, db=_state(_board_db([_rule("RON"), _rule("RTW")]), not_eligible=["X"]))
    assert off["state"] == "ok" and "rules" not in off
    assert _syms(off) == ["OMH", "NVDA", "AAA", "MMM", "ZZT"]
    assert all("folded_default" not in s for s in off["sections"])
    off.pop("pass", None)
    base.pop("pass", None)
    assert _dumps(off) == _dumps(base)


def test_NEGATIVE_no_rules_row_on_the_only_poll_without_org():
    out = PL.build(FRI_IN, db=_board_db([_rule("RON")]), only=["RON", "OMH", "NOPE"])
    assert _syms(out) == ["OMH", "RON"] and out["sections"] is None
    assert _rows(out)["RON"]["auto"]["why"] == "rules" and _rows(out)["RON"]["org"] is None
    assert out["rules"]["n"] == 1


def test_NEGATIVE_nan_volume_and_count_serve_no_number():
    rules = [_rule("RNAN", volume=float("nan")), _rule("RINF", volume=float("inf"), volume_source="scan"),
             _rule("RJUNK", volume="lots", volume_source="nope"), _rule("RBOOL", volume=True)]
    db = _state(_board_db(rules), not_eligible=float("nan"))
    out = PL.build(FRI_IN, db=db)
    s = _dumps(out)                                              # allow_nan=False: raises on any NaN / inf
    assert "NaN" not in s and "Infinity" not in s
    rows = _rows(out)
    assert rows["RNAN"]["auto"]["volume_text"] is None and rows["RINF"]["auto"]["volume_text"] is None
    assert rows["RJUNK"]["auto"]["volume_source"] is None and rows["RJUNK"]["auto"]["volume_text"] is None
    assert rows["RBOOL"]["auto"]["volume_text"] is None                    # potential._num: a bool is no number
    assert out["rules"]["not_seated_n"] == 0
    hint = {x["key"]: x for x in out["sections"]}["rules"]["hint"]
    assert "🚫" not in hint


def test_NEGATIVE_not_seated_from_another_session_or_junk_is_zero():
    out = PL.build(FRI_IN, db=_state(_board_db([_rule("RON")]), session="2026-11-12", not_eligible=["A", "B"]))
    assert out["rules"]["not_seated_n"] == 0
    for junk in (None, True, -3, "7", {"a": 1}):
        assert PL.rules_not_seated({"session": SESSION, "rules": {"not_eligible": junk}}, SESSION) in (0, 7)
    assert PL.rules_not_seated({"session": SESSION, "rules": {"not_eligible": True}}, SESSION) == 0
    assert PL.rules_not_seated(None, SESSION) == 0 and PL.rules_not_seated({"session": SESSION}, None) == 0


@pytest.mark.parametrize("mode_ix", [0, 1])
def test_held_chip_on_a_rules_row_reads_held_text_under_push_mode(monkeypatch, mode_ix):
    """[C10] ✅ names are held `suppressed_auto` by the loop; the chip is whatever `held_text` says under PUSH_MODE
    (".wt-cleanalerts" may reword it while the watch push is off) — never a second word map."""
    monkeypatch.setattr(C, "PUSH_MODE", C.PUSH_MODES[mode_ix])
    x = f"{SESSION} 09:33"
    db = _board_db([_rule("RON")])
    db[C.COLL_TILES] = RecColl([_doc("RON", ups=(x,), held={"1m": {"bar_t": x, "reason": C.AUTO_HELD_REASON}})])
    out = PL.build(FRI_IN, db=db)
    r = _rows(out)["RON"]
    assert r["state"] == "ok" and r["org"]["group"] == "rules"
    f1 = next(f for f in r["frames"] if f["tf"] == "1m")
    want = PL.held_text(C.AUTO_HELD_REASON)
    assert isinstance(want, str) and want and f1["held"] == {"text": want}
    assert want in (PL.HELD_TEXT[C.AUTO_HELD_REASON], PL.held_text(C.PUSH_MODES[0]))
    assert all(f["held"] is None for f in r["frames"] if f["tf"] != "1m")
    _dumps(out)


# ── sections.py units ────────────────────────────────────────────────────────────────────────────────────────────────
def test_group_of_rules_and_precedence():
    assert SE.group_of(None) == SE.group_of(None, None) == "yours"
    assert SE.group_of(None, {}) == SE.group_of(None, _rule("X")) == "rules"
    assert SE.group_of({"why": C.AUTO_APLUS_WHY}, _rule("X")) == "aplus"
    assert SE.group_of({}, _rule("X")) == "auto"
    assert SE.group_of(None, "junk") == "yours"


def test_order_rules_newest_met_first_undated_last():
    rents = {"R1": _rule("R1", 9, 0), "R2": _rule("R2", 11, 0), "RU": dict(_rule("RU"), last_met_at=None),
             "RW": _rule("RW", 15, 0, day=WED)}
    rows = [{"symbol": s} for s in ("RU", "H", "R1", "RW", "R2")]
    groups = {r["symbol"]: SE.group_of(None, rents.get(r["symbol"])) for r in rows}
    assert [r["symbol"] for r in SE.order(rows, groups, {}, rents)] == ["H", "R2", "R1", "RW", "RU"]


def test_NEGATIVE_rules_when_block_without_a_time_and_apply_without_rules():
    assert SE.rules_when_block(dict(_rule("X"), last_met_at="10:00"), SESS) is None
    assert SE.rules_when_block({}, SESS) is None
    rows, secs = SE.apply([{"symbol": "H"}], entries={}, removed=[], his_added={}, session=SESS)
    assert [s["key"] for s in secs] == ["yours"] and "folded_default" not in secs[0]
    rows, secs = SE.apply([{"symbol": "R"}], entries={}, removed=[], his_added={}, session=SESS,
                          rules={"entries": {"R": _rule("R")}, "boards": None, "not_seated": 5})
    assert secs[0]["key"] == "rules" and secs[0]["folded_default"] is True and "—" in secs[0]["hint"]


# ── goldens (frontend/src/lib/__fixtures__ — the FE tests read the SAME files) ─────────────────────────────────────
def _golden_db():
    rules = [_rule("RON", 9, 41), _rule("RTW", 11, 5, first=(10, 0, WED), sessions=["2026-11-11", "2026-11-13"]),
             _rule("ROLD", 15, 0, day=WED, kind=C.RULES_KINDS[1], setup="reversal_squeeze"),
             _rule("MMM", 12, 0)]                                                          # 🤖 seat wins → once in 🤖
    return _state(_board_db(rules), not_eligible=["HUHU"])


def _golden_db90():
    his = [f"H{chr(65 + i)}" for i in range(8)]
    autos = ([_auto(f"P{chr(65 + i)}", 7, i, why=C.AUTO_APLUS_WHY, aplus_at=_u(9, 10 + i)) for i in range(2)]
             + [_auto(f"A{chr(65 + i)}", 8, i) for i in range(10)])
    rules = [_rule(f"R{chr(65 + i // 26)}{chr(65 + i % 26)}", 4 + i // 60, i % 60) for i in range(70)]
    db = _db(his, {s: datetime(2026, 11, 13, 13, i) for i, s in enumerate(his)}, entries=autos)
    return _with_rules(db, rules)


def _check_golden(path, out):
    if GOLD_WRITE:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1, allow_nan=False)
            fh.write("\n")
    with open(path, encoding="utf-8") as fh:
        gold = json.load(fh)
    for k in PIN_KEYS:
        assert gold.get(k) == json.loads(_dumps(out)).get(k), k
    return gold


def test_golden_all_rules_board():
    out = PL.build(FRI_IN, db=_golden_db())
    gold = _check_golden(GOLD, out)
    assert [s["key"] for s in gold["sections"]] == ["yours", "aplus", "auto", "rules"]
    assert gold["sections"][-1]["folded_default"] is True and gold["sections"][-1]["symbols"] == ["RTW", "RON", "ROLD"]
    assert gold["rules"]["n"] == 3 and gold["rules"]["not_seated_n"] == 1
    assert [r["symbol"] for r in gold["rows"]].count("MMM") == 1


def test_golden_90_rows_rules_are_the_tail():
    out = PL.build(FRI_IN, db=_golden_db90())
    gold = _check_golden(GOLD90, out)
    rows = gold["rows"]
    assert len(rows) == 90 and len({r["symbol"] for r in rows}) == 90
    whys = [(r["auto"] or {}).get("why") for r in rows]
    assert whys[:20].count("rules") == 0 and all(w == "rules" for w in whys[20:])
    assert all(w == "rules" for w in whys[80:])                         # past the hub's 80: ✅ only
    assert [s["n"] for s in gold["sections"]] == [8, 2, 10, 70] and gold["rules"]["n"] == 70
