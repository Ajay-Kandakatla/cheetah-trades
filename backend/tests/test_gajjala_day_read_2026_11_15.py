"""🌫️ Day read (2026-11-15, Ajay "yes" — information only): the served wrapper chart_maps/gajjala/day_read.py over the
recorder's ONE engine (scripts.shadow_day_tags_lib.compute over scripts.shadow_day_tags_probe.build_inputs).

Parity (the lib verbatim over the 22-session fixture; the inputs builder IS the probe), the lib code-body sha pin, the
served block (pending / missing / absent / closed-day tail / fold / note / caption / read rule), the words from the
constants by name, and the guards. NEGATIVE cases beside each."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
from datetime import date, datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import audited_rules as AR
from chart_maps.gajjala import day_read as DR
from chart_maps.gajjala import variant as V
from scripts import shadow_day_tags_lib as LIB
from tests import test_shadow_day_tags_2026_11_11 as RT

BACKEND = Path(__file__).resolve().parents[1]
MODULE = BACKEND / "chart_maps" / "gajjala" / "day_read.py"
LIB_PATH = BACKEND / "scripts" / "shadow_day_tags_lib.py"
LIB_BODY_SHA = "e7e6df818ee4a78f65b5013ca999647c499b6aa59f3f16eef513f3cc0e137d7a"
PREREG_SHA_VALUE = "f32a3ece46ae2d43e3273cc298b30a1df796467d02b49aecf6abf9d9993f9409"
ET = ZoneInfo("America/New_York")
UTC = timezone.utc
OUTCOME = re.compile(r"(?i)(win_rate|mean_r|gap|placebo|p_value|bootstrap|expectancy|r_by|by_tag)")
BWORD = re.compile("b" + "ounc", re.I)
GRADED = "2026-11-14T01:15:00.997467+00:00"            # the critique's observed shape (microseconds + offset)


@pytest.fixture(scope="module")
def fixture_inputs():
    return json.loads(RT.INPUTS_FIX.read_text())


def et_at(d: str, h: int, m: int, s: int = 0) -> datetime:
    return datetime.combine(date.fromisoformat(d), dtime(h, m, s), tzinfo=ET)


def ok(value, on, detail=None, asof=None):
    return {"status": "ok", "on": on, "value": value, "detail": detail or {}, "why": None,
            "asof": asof if asof is not None else {"gg5_last_graded_at": GRADED}}


def hand_tags():
    """GD3w on · GD4_pre off · GD4_by1030 on · GD6b_pre off · GD6b_by1030 on · GD7 MISSING · LD3i on · LD9 off."""
    return {"GD3w_pre": ok(0.6, True, {"failed": 3, "held": 2, "window": []}),
            "GD4_pre": ok(1.0, False, {"events": 0, "cut": "09:30"}),
            "GD4_by1030": ok(0.5, True, {"events": 1, "cut": "10:30"}),
            "GD6b_pre": ok(55, False, {"median": 50, "n_hist": 5, "pass": "x", "cut": "09:29"},
                           {"passes_last_id": "2026-11-13|10:25"}),
            "GD6b_by1030": ok(40, True, {"median": 50, "n_hist": 5, "pass": "x", "cut": "10:30"},
                              {"passes_last_id": "2026-11-13|10:25"}),
            "GD7_by1030": LIB.missing("QQQ/IWM bars absent by 10:30", {"qqq_last_date": "2026-11-09",
                                                                         "iwm_last_date": None}),
            "LD3i_pre": ok(-0.5, True, {"prev": "2026-11-12"},
                           {"iwm_daily_last_date": "2026-11-12", "iwm_daily_cached_at": 1794387676.0}),
            "LD9_pre": ok("2/8", False, {"weak": ["AAPL", "TSLA"], "prev": "2026-11-12"},
                          {"pillars_last_date": {"AAPL": "2026-11-12", "MSFT": None}})}


def mk_doc(session="2026-11-13", hm=(10, 31), tags=None, graded=GRADED):
    return {"session": session, "computed_at": et_at(session, *hm).astimezone(UTC),
            "tags": hand_tags() if tags is None else tags, "asof": {"gg5_last_graded_at": graded},
            "constants": {}, "inputs_sha256": "x", "forms": list(LIB.TAG_FORMS)}


FRI = date(2026, 11, 13)


def all_keys(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield str(k)
            yield from all_keys(v)
    elif isinstance(x, list):
        for v in x:
            yield from all_keys(v)


# ── parity-1: tags_of IS the lib over the 22 sessions ───────────────────────────────────────────────────────────────
def test_parity_tags_of_equals_the_lib_on_all_22_sessions(fixture_inputs):
    assert len(fixture_inputs["sessions"]) == 22
    for s in fixture_inputs["sessions"]:
        d = date.fromisoformat(s)
        assert json.dumps(DR.tags_of(fixture_inputs, d), sort_keys=True) == \
            json.dumps(LIB.compute(fixture_inputs, s), sort_keys=True), s


def test_NEGATIVE_parity_one_flipped_on_breaks_the_equality(fixture_inputs):
    s = fixture_inputs["sessions"][-1]
    got = copy.deepcopy(DR.tags_of(fixture_inputs, date.fromisoformat(s)))
    form = next(f for f in LIB.TAG_FORMS if got[f]["status"] == "ok")
    got[form]["on"] = not got[form]["on"]
    assert json.dumps(got, sort_keys=True) != json.dumps(LIB.compute(fixture_inputs, s), sort_keys=True)


def test_NEGATIVE_a_session_outside_the_inputs_raises_as_the_lib(fixture_inputs):
    with pytest.raises(ValueError):
        DR.tags_of(fixture_inputs, date(2026, 11, 14))                  # a Saturday: never a market day


# ── parity-2: the inputs builder IS the probe ───────────────────────────────────────────────────────────────────────
def _probe_env(monkeypatch):
    PR = RT._probe()
    import pymongo
    PS = RT._house_store(monkeypatch)
    from sepa import prices as P
    log = []
    s1, s2 = "2026-11-12", "2026-11-13"
    intra = [{"symbol": sym, "date": d, "bars": [{"ts_utc": RT.utc_of(d, 9, 30), "open": 1.0, "high": 1.0, "low": 1.0,
                                                   "close": 1.0, "volume": 1.0, "session": "rth"}]}
             for sym in LIB.INDEX_SYMS for d in (s1, s2)]
    docs = {"price_cache": [RT._price_doc("IWM", n=330)] + [RT._price_doc(s, n=70) for s in LIB.PILLARS],
            "intraday_cache": intra}
    client = RT._RecClient(docs, log)
    monkeypatch.setattr(PS, "_db", None)
    monkeypatch.setattr(PS, "_disabled", False)
    monkeypatch.setattr(P, "_mongo_coll", None)
    monkeypatch.setattr(P, "_mongo_disabled", False)
    monkeypatch.setattr(pymongo, "MongoClient", lambda *a, **k: client)
    monkeypatch.setattr(PR, "MongoClient", lambda *a, **k: client)
    monkeypatch.setattr(PR, "APP", str(BACKEND))
    return PR, PS, client, log


def test_parity_probe_main_prints_build_inputs_and_inputs_for_equals_it(monkeypatch, capsys):
    PR, PS, client, log = _probe_env(monkeypatch)
    orig, seen = PR.build_inputs, {}

    def spy(db, now, *, only=None):
        seen.update(db=db, now=now, only=only)
        return orig(db, now, only=only)

    monkeypatch.setattr(PR, "build_inputs", spy)
    PR.main([])
    out = capsys.readouterr().out
    assert seen["db"] is client.db and seen["only"] is None
    assert out == json.dumps(orig(client.db, seen["now"]), sort_keys=True, allow_nan=False, separators=(",", ":"))
    now = et_at("2026-11-13", 10, 31).astimezone(UTC)
    want = orig(client.db, now, only={"2026-11-13"})
    assert DR.inputs_for(now, session=FRI, db=client.db) == want
    assert RT._write_calls(log) == []


def test_NEGATIVE_only_limits_the_index_bars_to_that_session(monkeypatch, capsys):
    PR, PS, client, log = _probe_env(monkeypatch)
    now = et_at("2026-11-13", 10, 31).astimezone(UTC)
    whole = PR.build_inputs(client.db, now)
    one = DR.inputs_for(now, session=FRI, db=client.db)
    assert set(one["index_intraday"]) == {"QQQ|2026-11-13", "IWM|2026-11-13"}
    assert {"QQQ|2026-11-12", "IWM|2026-11-12"} <= set(whole["index_intraday"])
    assert {k: v for k, v in whole.items() if k != "index_intraday"} == \
        {k: v for k, v in one.items() if k != "index_intraday"}
    PR.main(["--sessions", "2026-11-12"])
    printed = json.loads(capsys.readouterr().out)
    assert set(printed["index_intraday"]) == {"QQQ|2026-11-12", "IWM|2026-11-12"}


# ── [C5] the db is never truth-tested ───────────────────────────────────────────────────────────────────────────────
class _NoBool:
    def __bool__(self):
        raise NotImplementedError("pymongo Database.__bool__")


def test_inputs_for_uses_a_given_db_without_a_truth_test(monkeypatch):
    PR = RT._probe()
    seen = []
    monkeypatch.setattr(PR, "build_inputs", lambda db, now, *, only=None: seen.append((db, only)) or {"ok": 1})
    fake = _NoBool()
    assert DR.inputs_for(datetime(2026, 11, 13, 15, 31, tzinfo=UTC), session=FRI, db=fake) == {"ok": 1}
    assert seen[0][0] is fake and seen[0][1] == {"2026-11-13"}


def test_inputs_for_none_db_asks_get_db_once(monkeypatch):
    PR = RT._probe()
    PS = RT._house_store(monkeypatch)
    fake, calls, seen = _NoBool(), [], []
    monkeypatch.setattr(PS, "_get_db", lambda: calls.append(1) or fake)
    monkeypatch.setattr(PR, "build_inputs", lambda db, now, *, only=None: seen.append(db) or {})
    DR.inputs_for(datetime(2026, 11, 13, 15, 31, tzinfo=UTC), session=FRI)
    assert calls == [1] and seen[0] is fake


def test_NEGATIVE_no_db_raises_and_never_builds(monkeypatch):
    PR = RT._probe()
    PS = RT._house_store(monkeypatch)
    seen = []
    monkeypatch.setattr(PS, "_get_db", lambda: None)
    monkeypatch.setattr(PR, "build_inputs", lambda *a, **k: seen.append(1) or {})
    with pytest.raises(RuntimeError):
        DR.inputs_for(datetime(2026, 11, 13, 15, 31, tzinfo=UTC), session=FRI)
    assert seen == []


# ── compute / run_step / load_doc ───────────────────────────────────────────────────────────────────────────────────
def test_compute_and_run_step_write_one_state_doc(monkeypatch, fixture_inputs):
    monkeypatch.setattr(DR, "inputs_for", lambda now, *, session, db=None: fixture_inputs)
    now = et_at("2026-11-11", 10, 31).astimezone(UTC)
    doc = DR.compute(now, date(2026, 11, 11))
    assert doc["session"] == "2026-11-11" and doc["computed_at"] == now and doc["computed_at"].tzinfo is not None
    assert doc["tags"] == LIB.compute(fixture_inputs, "2026-11-11") and doc["forms"] == list(LIB.TAG_FORMS)
    assert doc["inputs_sha256"] == LIB.sha256_hex(LIB.inputs_blob(fixture_inputs))
    assert doc["asof"] == fixture_inputs["asof"] and doc["constants"] == fixture_inputs["constants"]

    class St:
        def __init__(self):
            self.w = []

        def set_state(self, sid, fields):
            self.w.append((sid, fields))

        def get_state(self, sid):
            return dict(self.w[-1][1]) if self.w else {}

    st = St()
    assert DR.load_doc(st) is None                                       # {} → None
    got = DR.run_step(st, now, date(2026, 11, 11))
    assert st.w == [("day_read", got)] and DR.STATE_ID == "day_read" and DR.load_doc(st) == got


def test_NEGATIVE_run_step_never_swallows_and_writes_nothing_on_a_failure(monkeypatch):
    def boom(now, *, session, db=None):
        raise RuntimeError("day read: no db")

    monkeypatch.setattr(DR, "inputs_for", boom)

    class St:
        w = []

        def set_state(self, sid, fields):
            self.w.append(sid)

    with pytest.raises(RuntimeError):
        DR.run_step(St(), datetime(2026, 11, 13, 15, 31, tzinfo=UTC), FRI)
    assert St.w == []

    class Bad:
        def get_state(self, sid):
            return ["not", "a", "dict"]

    assert DR.load_doc(Bad()) is None


# ── pins ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_lib_code_body_sha_is_unchanged_and_the_prereg_is_frozen():
    b = LIB_PATH.read_bytes()
    assert hashlib.sha256(b[b.index(b"import gzip"):]).hexdigest() == LIB_BODY_SHA
    assert RT.PREREG_SHA.read_text().strip() == PREREG_SHA_VALUE
    assert hashlib.sha256(RT.PREREG.read_bytes()).hexdigest() == PREREG_SHA_VALUE


def test_NEGATIVE_one_changed_body_byte_breaks_the_lib_pin():
    b = bytearray(LIB_PATH.read_bytes())
    i = b.index(b"STALE_MIN, WEEK, TWO_WEEKS, PILLAR_WEAK_MIN = 30")
    b[i + len(b"STALE_MIN, WEEK, TWO_WEEKS, PILLAR_WEAK_MIN = ")] = ord("4")
    assert hashlib.sha256(bytes(b[b.index(b"import gzip"):])).hexdigest() != LIB_BODY_SHA


def test_the_lib_docstring_names_the_one_served_reader():
    head = LIB_PATH.read_text().split("\n")[:2]
    assert "chart_maps/gajjala/day_read.py" in head[1] and "RECORD + READ" in head[0]
    assert "nothing served imports this file" not in LIB_PATH.read_text()


# ── served_block ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_pending_at_1026_on_today_and_readable_at_1031():
    now = et_at("2026-11-13", 10, 27)
    b = DR.served_block(mk_doc(hm=(10, 26)), FRI, now)
    st = {c["form"]: c for c in b["chips"]}
    for f in ("GD4_by1030", "GD6b_by1030", "GD7_by1030"):
        assert st[f]["state"] == "pending" and b["tags"][f] is None and st[f]["value_text"] is None
        assert st[f]["state_text"] == "reads at 10:30 ET" and st[f]["reads_at"] == "10:30"
    assert b["counts"] == {"on": 2, "off": 3, "read": 5, "missing": 0, "pending": 3}   # GD7's MISSING is pending
    assert b["head"] == "🌫️ Day read: 2 of 5 pre-registered reads on · information only · 3 read later today"
    tags = dict(hand_tags(), LD9_pre=LIB.missing("5 pillars with a row on 2026-11-12 (< 6)"))
    both = DR.served_block(mk_doc(hm=(10, 26), tags=tags), FRI, now)
    assert both["counts"] == {"on": 2, "off": 2, "read": 4, "missing": 1, "pending": 3}
    assert both["head"] == ("🌫️ Day read: 2 of 4 pre-registered reads on · information only · 1 not read"
                            " · 3 read later today")
    later = DR.served_block(mk_doc(hm=(10, 31)), FRI, et_at("2026-11-13", 10, 32))
    assert later["counts"] == {"on": 4, "off": 3, "read": 7, "missing": 1, "pending": 0}
    assert later["head"] == "🌫️ Day read: 4 of 7 pre-registered reads on · information only · 1 not read"
    assert later["tags"]["GD4_by1030"] == hand_tags()["GD4_by1030"]


def test_pending_is_keyed_on_the_doc_clock_never_the_get_clock():
    b = DR.served_block(mk_doc(hm=(10, 26)), FRI, et_at("2026-11-13", 15, 0))   # GET at 15:00, doc at 10:26
    assert b["counts"]["pending"] == 3
    exactly = DR.served_block(mk_doc(hm=(10, 30)), FRI, et_at("2026-11-13", 10, 30))
    assert exactly["counts"]["pending"] == 0                                    # strict `<` the cut
    pre = DR.served_block(mk_doc(hm=(9, 29)), FRI, et_at("2026-11-13", 9, 29))
    assert {c["form"] for c in pre["chips"] if c["state"] == "pending"} == \
        {"GD4_pre", "GD4_by1030", "GD6b_by1030", "GD7_by1030"}
    assert {c["form"]: c["reads_at"] for c in pre["chips"]}["GD4_pre"] == "09:30"


def test_NEGATIVE_a_non_today_session_is_never_pending():
    b = DR.served_block(mk_doc(hm=(10, 26)), FRI, et_at("2026-11-14", 12, 0))   # Saturday reads Friday's 10:26 doc
    assert b["counts"]["pending"] == 0 and b["is_today"] is False
    assert all(c["state"] != "pending" for c in b["chips"])


def test_missing_is_never_on_or_off_and_serves_its_why():
    b = DR.served_block(mk_doc(), FRI, et_at("2026-11-13", 10, 32))
    c = {x["form"]: x for x in b["chips"]}["GD7_by1030"]
    assert c["state"] == "missing" and c["state_text"] == "not read" and c["value_text"] is None
    assert c["why"] == "QQQ/IWM bars absent by 10:30"
    assert b["counts"]["read"] == b["counts"]["on"] + b["counts"]["off"]
    assert b["counts"]["read"] + b["counts"]["missing"] + b["counts"]["pending"] == 8
    assert all(x["why"] is None for x in b["chips"] if x["state"] != "missing")


def test_head_when_nothing_is_read():
    tags = {f: LIB.missing("x") for f in LIB.TAG_FORMS}
    b = DR.served_block(mk_doc(tags=tags), FRI, et_at("2026-11-13", 10, 32))
    assert b["head"] == "🌫️ Day read: nothing read yet · information only · 8 not read"
    assert b["counts"] == {"on": 0, "off": 0, "read": 0, "missing": 8, "pending": 0}


def test_head_words_and_NEGATIVE_never_his_word_or_signs():
    b = DR.served_block(mk_doc(), FRI, et_at("2026-11-13", 10, 32))
    assert "pre-registered reads on · information only" in b["head"]
    blob = json.dumps(b, ensure_ascii=False).lower()
    assert "choppy" not in blob and "signs" not in blob


def test_closed_day_carries_the_last_session_tail_and_full_dates():
    sat = DR.served_block(mk_doc(), FRI, et_at("2026-11-14", 12, 0))
    assert sat["is_today"] is False and sat["head"].endswith(" · last session 2026-11-13")
    assert all(c["asof_text"].startswith("read 2026-11-13 10:31 ET") for c in sat["chips"])
    fri = DR.served_block(mk_doc(), FRI, et_at("2026-11-13", 10, 32))
    assert fri["is_today"] is True and "last session" not in fri["head"] and fri["computed_at_et"] == "10:31 ET"


@pytest.mark.parametrize("doc", [None, {}, "x", mk_doc(session="2026-11-12"),
                                 dict(mk_doc(), computed_at=None), dict(mk_doc(), tags=None)])
def test_absent_block(doc):
    b = DR.served_block(doc, FRI, et_at("2026-11-13", 10, 32))
    assert b["state"] == "absent" and b["chips"] == [] and b["tags"] == {} and b["fold_text"] is None
    assert b["note"] is None and b["computed_at_et"] is None and b["grades_through_et"] is None
    assert b["head"] == DR.HEAD_ABSENT_TEXT.format(cad=V.cadence_sec(V.GG5) // 60)
    assert "every %d-minute" % (V.cadence_sec(V.GG5) // 60) in b["head"]
    assert b["counts"] == {"on": 0, "off": 0, "read": 0, "missing": 0, "pending": 0}
    assert b["caption"] == DR.CAPTION.format(n=22) and b["read_date_text"] == DR.read_date_text()
    sat = DR.served_block(doc, FRI, et_at("2026-11-14", 12, 0))
    assert sat["head"].endswith(" · last session 2026-11-13")


def test_read_and_absent_blocks_share_one_key_set():
    a = DR.served_block(None, FRI, et_at("2026-11-13", 10, 32))
    r = DR.served_block(mk_doc(), FRI, et_at("2026-11-13", 10, 32))
    assert set(a) == set(r)


def test_fold_text_is_served_for_chips_and_none_when_absent():
    r = DR.served_block(mk_doc(), FRI, et_at("2026-11-13", 10, 32))
    assert r["fold_text"] == DR.FOLD_TEXT.format(n=8) == "the 8 reads" and len(r["chips"]) == 8
    assert [c["form"] for c in r["chips"]] == list(LIB.TAG_FORMS)


# ── [C1] the note + grades_through ──────────────────────────────────────────────────────────────────────────────────
def test_note_names_the_grades_on_file():
    b = DR.served_block(mk_doc(), FRI, et_at("2026-11-13", 10, 32))
    assert b["grades_through_et"] == "2026-11-13 20:15 ET"
    assert b["note"] == DR.NOTE_TEXT.format(grades_through="2026-11-13 20:15 ET")
    assert "GD3w and GD4" in b["note"] and "after the close" in b["note"]


def test_NEGATIVE_no_grade_on_file_and_never_claims_identical():
    b = DR.served_block(mk_doc(graded=None), FRI, et_at("2026-11-13", 10, 32))
    assert b["grades_through_et"] is None and b["note"] == DR.NOTE_NO_GRADES_TEXT
    for n in (DR.NOTE_TEXT, DR.NOTE_NO_GRADES_TEXT):
        assert "identical" not in n.lower() and "same as the record" not in n.lower()
        assert "GD3w and GD4" in n and "after the close" in n


# ── [C4] as-of strings ──────────────────────────────────────────────────────────────────────────────────────────────
def test_asof_str_renders_iso_datetimes_in_et():
    assert DR._asof_str(GRADED) == "2026-11-13 20:15 ET"
    assert DR._asof_str("2026-11-13T15:31:00Z") == "2026-11-13 10:31 ET"


def test_NEGATIVE_asof_str_leaves_dates_and_names_alone():
    assert DR._asof_str("2026-11-13") == "2026-11-13"
    assert DR._asof_str("gg5") == "gg5"
    assert DR._asof_str("TSLA") == "TSLA"
    assert DR._asof_str("2026-11-11|20:01") == "2026-11-11|20:01"
    assert DR._asof_str({"AAPL": "2026-11-13"}) == "AAPL:2026-11-13"
    assert DR._asof_str({"AAPL": "2026-11-13", "MSFT": None}) == "AAPL:2026-11-13"


def test_asof_text_from_the_fixture_has_no_microseconds_or_offset(fixture_inputs):
    s = "2026-11-11"
    asof = dict(fixture_inputs["asof"], gg5_last_graded_at=GRADED)
    tags = LIB.compute(dict(fixture_inputs, asof=asof), s)
    doc = {"session": s, "computed_at": et_at(s, 20, 55).astimezone(UTC), "tags": tags, "asof": asof}
    b = DR.served_block(doc, date(2026, 11, 11), et_at(s, 21, 0))
    assert b["tags"] == tags and b["counts"]["pending"] == 0
    for c in b["chips"]:
        assert ".997467" not in c["asof_text"] and "+00:00" not in c["asof_text"], c["asof_text"]
        want = {"ok": ("on" if tags[c["form"]]["on"] else "off"), "missing": "missing"}[tags[c["form"]]["status"]]
        assert c["state"] == want
    gd3 = {c["form"]: c for c in b["chips"]}["GD3w_pre"]
    assert "gg5_last_graded_at 2026-11-13 20:15 ET" in gd3["asof_text"]


# ── words, value words, caption, read rule ──────────────────────────────────────────────────────────────────────────
def test_chip_text_is_the_words_and_the_source_is_the_lib():
    b = DR.served_block(mk_doc(), FRI, et_at("2026-11-13", 10, 32))
    w = DR.words()
    assert set(w) == set(LIB.TAG_FORMS)
    for c in b["chips"]:
        assert c["text"] == w[c["form"]] and c["source"] == LIB.SOURCE_TAGS[c["form"]]
    assert w["GD4_pre"].endswith("before the 09:30 open)") and "the 09:29 pass" in w["GD6b_pre"]
    assert "by 10:30" in w["GD4_by1030"] and "into 10:30" in w["GD7_by1030"]


def test_NEGATIVE_cut_words_follow_the_constant(monkeypatch):
    monkeypatch.setattr(AR, "T2_FIRST_HOUR_END_ET", dtime(10, 45))
    w = DR.words()
    assert "by 10:45" in w["GD4_by1030"] and "the 10:45 pass" in w["GD6b_by1030"] and "into 10:45" in w["GD7_by1030"]
    assert "10:30" not in " ".join(w.values())
    assert DR.read_at("GD7_by1030") == (10, 45)


def test_value_words():
    t = hand_tags()
    assert DR.value_text("GD3w_pre", t["GD3w_pre"]) == "3 failed · 2 held (60% failed)"
    assert DR.value_text("GD4_by1030", t["GD4_by1030"]) == "risk ×0.5"
    assert DR.value_text("GD6b_by1030", t["GD6b_by1030"]) == "40 names at the pass · median 50"
    assert DR.value_text("GD7_by1030", ok("QQQ -0.40% IWM -0.90%", True)) == "QQQ -0.40% IWM -0.90%"
    assert DR.value_text("LD3i_pre", t["LD3i_pre"]) == "9 − 21 EMA -0.50"
    assert DR.value_text("LD9_pre", t["LD9_pre"]) == "2/8 big techs weak"


def test_NEGATIVE_value_words_none_when_not_read():
    assert DR.value_text("GD7_by1030", LIB.missing("x")) is None
    assert DR.value_text("GD3w_pre", None) is None
    assert DR.value_text("GD3w_pre", ok(0.6, True, {})) is None                # a detail without counts


def test_caption_states_the_in_sample_read_faithfully(fixture_inputs):
    assert DR.IN_SAMPLE_SESSIONS == len(fixture_inputs["sessions"]) == 22
    cap = DR.served_block(mk_doc(), FRI, et_at("2026-11-13", 10, 32))["caption"]
    assert cap == DR.CAPTION.format(n=22)
    for s in ("not a gate", "no read flagged the worse days", "GD6b read the opposite way", "too few days", "22"):
        assert s in cap
    assert "OPPOSITE way" not in cap and "being recorded" not in cap


def test_read_rule_names_the_floor_and_forward_from_and_no_other_date():
    t = DR.read_date_text()
    assert str(AR.MEASURE_FLOOR_WEEKS) in t and LIB.FORWARD_FROM in t
    assert re.findall(r"\d{4}-\d{2}-\d{2}", t) == [LIB.FORWARD_FROM]


def test_NEGATIVE_the_module_holds_no_read_date():
    src = MODULE.read_text()
    assert "2027-" not in src and "date(20" not in src and "earliest_read_monday" not in src


# ── hygiene ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _blocks(fixture_inputs):
    s = "2026-11-11"
    real = {"session": s, "computed_at": et_at(s, 10, 31).astimezone(UTC),
            "tags": LIB.compute(fixture_inputs, s), "asof": fixture_inputs["asof"]}
    return [DR.served_block(real, date(2026, 11, 11), et_at(s, 10, 32)),
            DR.served_block(mk_doc(hm=(10, 26)), FRI, et_at("2026-11-13", 10, 27)),
            DR.served_block(None, FRI, et_at("2026-11-14", 12, 0))]


def test_no_outcome_key_or_word_and_no_b_word(fixture_inputs):
    for b in _blocks(fixture_inputs):
        assert [k for k in all_keys(b) if OUTCOME.search(k)] == []
        texts = [b["head"], b["note"] or "", b["caption"], b["read_date_text"], b["fold_text"] or ""]
        texts += [c[k] or "" for c in b["chips"] for k in ("text", "state_text", "value_text", "why", "source")]
        assert [t for t in texts if OUTCOME.search(t)] == []
        assert not BWORD.search(json.dumps(b, ensure_ascii=False))
    assert not BWORD.search(MODULE.read_text())


def test_NEGATIVE_the_outcome_guard_catches_a_planted_key():
    assert [k for k in all_keys({"chips": [{"win_rate": 1}], "x": {"by_tag": 2}}) if OUTCOME.search(k)] == \
        ["win_rate", "by_tag"]


def test_the_block_is_plain_json(fixture_inputs):
    from chart_maps.gajjala import tab as GT
    for b in _blocks(fixture_inputs):
        json.dumps(GT._plain(b), allow_nan=False)


# ── guards ──────────────────────────────────────────────────────────────────────────────────────────────────────────
BANNED = re.compile(r"^(trading|push|alerts|daytrading|massive|finnhub|yfinance|alpaca|requests|httpx)(\.|$)")
BANNED_GG = re.compile(r"^chart_maps\.gajjala\.(alerts|potential|break_watch|live_events|audited_pass)(\.|$)")


def _mods(tree, nodes=None):
    out = []
    for n in (nodes if nodes is not None else ast.walk(tree)):
        if isinstance(n, ast.Import):
            out += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                base = "chart_maps.gajjala" + ("." + n.module if n.module else "")
                out += [base + "." + a.name for a in n.names] if not n.module else [base]
            else:
                out += [n.module] + [n.module + "." + a.name for a in n.names]
    return out


def test_day_read_imports_no_gate_or_provider_module():
    """2026-11-15 his "Yes" to the GD7 warm: `daytrading.data` is allowed, and ONLY inside `_fetch_bars`."""
    tree = ast.parse(MODULE.read_text())
    fetch = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_fetch_bars"]
    assert len(fetch) == 1
    inside = set(_mods(tree, list(ast.walk(fetch[0]))))
    assert inside == {"daytrading", "daytrading.data"}
    mods = _mods(tree)
    rest = [m for m in mods if m not in inside]
    assert [m for m in rest if BANNED.match(m) or BANNED_GG.match(m)] == []
    assert mods.count("daytrading.data") == 1
    assert "chart_maps.gajjala.audited_rules" in mods and "scripts.shadow_day_tags_lib" in mods


def test_NEGATIVE_the_import_guard_catches_planted_imports():
    tree = ast.parse("from . import alerts as AL\nimport trading.broker\nfrom push import send\n")
    assert [m for m in _mods(tree) if BANNED.match(m) or BANNED_GG.match(m)] == \
        ["chart_maps.gajjala.alerts", "trading.broker", "push", "push.send"]


def test_the_probe_and_portfolio_store_are_imported_lazily_inside_inputs_for():
    tree = ast.parse(MODULE.read_text())
    top = _mods(tree, tree.body)
    assert not [m for m in top if m.startswith("scripts.shadow_day_tags_probe") or m.startswith("portfolio")]
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "inputs_for")
    inner = _mods(tree, list(ast.walk(fn)))
    assert "scripts.shadow_day_tags_probe" in inner and "portfolio.store" in inner


def test_the_module_never_names_the_recorders_store():
    src = MODULE.read_text()
    for s in ("day_tags.jsonl", "STORE_NAME", "read_store", "load_store", "INPUTS_DIR"):
        assert s not in src, s


def test_module_text_never_names_the_luk_lane():
    """The 🥇 fence (test_luk_gajjala_hook / test_luk_scan_now N8 / contracts.mjs) allows the word only in run.py."""
    text = MODULE.read_text()
    assert not re.search(r"(?i)luk", text)
    assert "🥇 tab's build" in text


def test_luk_fence_regex_would_catch_the_old_docstring():
    """NEGATIVE: the pre-refix docstring line trips the same case-insensitive scan."""
    assert re.search(r"(?i)luk", "luk.tab.build to the primary owner only.")
    assert re.search(r"(?i)luk", "LUK")
