"""⛔ SSR on a RECENT session — `ssr.recent_triggers` + the `_rows_on` refactor (sissr WP be-ssr-words, 2026-11-24).

Ajay 2026-11-24 ~23:35 ET: "Days past little bit like AKAN is what I am mainly looking for many were so confident on
SSR..". Spec: scratchpad sissr/spec.md §3.1. Every name is SYNTHETIC ("ZZ…")
except AKAN, used as a label for his worked example (its rows here are synthetic too).

`OLD_NEW_TRIGGERS` is the VERBATIM `_new_triggers` of 5dec3c6b (before steps 3–8 moved into `_rows_on`); test 01 runs
it in the module's own namespace and pins `new_triggers` byte-identical over every branch.
"""
from __future__ import annotations

import ast
import inspect
import json
import textwrap
from datetime import date

import pytest

from short_interest import reg_sho as RS
from short_interest import ssr as SSR
from short_interest import ssr_lists as SL
from tests.test_ssr_new_triggers_2026_11_24 import Corp, Lists, fresh_day, read_corp, snap_doc
from tests.test_ssr_rule_201_2026_11_24 import (FORBIDDEN, FakeColl, FakeDB, day as day_doc, et, nasdaq_row, nyse_row,
                                                 trig)

D19, D20, D21 = date(2026, 11, 19), date(2026, 11, 20), date(2026, 11, 21)
D23, D24, D25, D27 = date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 27)
NOW = et(D24, 15, 0)


@pytest.fixture(autouse=True)
def _clean():
    SSR._reset_cache()
    SL._reset_cache()
    yield
    SSR._reset_cache()
    SL._reset_cache()


OLD_NEW_TRIGGERS = r'''
def _new_triggers(D, db, now_et, lists, corp) -> dict:
    from catalysts.medical.reaction import prev_market_day
    out = _new_base(D, now_et)
    out["status"] = "ok"

    # 2. STATUS ONLY — `days` is used for nothing else
    days = in_play(now_et)
    if D not in days:
        if D >= now_et.date() and now_et < _rth_open_dt(D):
            out["status"] = "pre_open"
            out["status_text"] = NEW_PRE_OPEN_TEXT % (_day_words(D), _rth_open_dt(D).strftime("%H:%M"))
        else:
            out["status"] = "out_of_play"
            out["status_text"] = NEW_OUT_OF_PLAY_TEXT % _day_words(D)
        return out
    if D != days[0]:
        out["status"] = "not_latest"
        out["status_text"] = NEW_NOT_LATEST_TEXT % _day_words(days[0])
        return out

    # 3. [C1] the prior market day, explicitly; the lists as of the list day's OWN files
    P = prev_market_day(D)
    iso, piso = D.isoformat(), P.isoformat()
    eval_days = [D, P]                                         # D first — `_computed_view` reads ctx.days[0]
    list_now = now_et if now_et.date() <= D else datetime.combine(D, datetime.max.time(), tzinfo=_ET)
    coll = db[lists.SSR_COLL]
    loaded = lists.load(coll, list_now)
    corp_loaded = None
    if corp is not None:
        try:
            corp_loaded = corp.load(coll, eval_days)
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr: corporate actions unread: %s", type(exc).__name__)
            corp_loaded = None
    ctx = _Ctx(lists, loaded, corp, corp_loaded, coll, eval_days, now_et)

    # 4. ONE find — the `_trig_docs` map shape; str symbols only
    trigs = {}
    for d in coll.find({"kind": "trig", "date": {"$in": [iso, piso]}}):
        s = d.get("symbol") if isinstance(d, dict) else None
        if isinstance(s, str) and s:
            trigs[(d.get("date"), s)] = d

    # 5. candidates — one name, one row
    seen, cands = set(), []

    def add(s):
        sp = _spellings(s)
        if not sp or any(k in seen for k in sp):
            return
        seen.update(sp)
        cands.append(s)

    for dt, s in sorted(trigs):
        if dt == iso:
            add(s)
    for s in lists.symbols_on(loaded, D) or []:
        if isinstance(s, str) and s:
            add(s)

    # 6–7. each name in its OWN try
    rows, faults = [], []
    withheld = {r: [] for r in NEW_WITHHELD}
    for s in cands:
        try:
            ev = _day_eval(ctx, s, D, trigs)
            if ev["on"]:
                it = _on_block(s, [ev, _day_eval(ctx, s, P, trigs)], ctx)
                if it.get("triggered_on") != iso:
                    faults.append(s)
                    continue
                rows.append(_new_row(s, it, P))
                continue
            doc = next((trigs[(iso, k)] for k in _spellings(s) if (iso, k) in trigs), None)
            if doc is None:                                    # a list name its own rows do not carry: unread, never "none"
                faults.append(s)
                continue
            why = "bars_disagree" if doc.get("void") else ("computed_only" if ev["overruled"] else "corp_action")
            withheld[why].append(s)
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr: one new name unread: %s", type(exc).__name__)
            faults.append(s)

    # 8. rows, the computed row, the sources, the as-of line
    rows.sort(key=lambda r: r["symbol"])
    computed = _computed_view(ctx)
    sources = list(lists.source_views(loaded, list_now) or [])
    if corp is not None and corp_loaded is not None:
        try:
            sources.append(corp.source_view(corp_loaded, [D], now_et))
        except Exception as exc:                               # noqa: BLE001
            log.warning("ssr: corporate-action source row failed: %s", type(exc).__name__)
    sources = [x for x in sources if isinstance(x, dict)]
    corp_checked = ctx.actions.get(iso) is not None            # [C4]
    texts = ([computed.get("text")] + [x.get("text") for x in sources if x.get("key") != "corp_actions"]
             + [x.get("text") for x in sources if x.get("key") == "corp_actions"])
    asof = "; ".join(t for t in texts if isinstance(t, str) and t)

    n_off = sum(1 for r in rows if r["source"] == "official")
    n_comp = sum(1 for r in rows if r["source"] == "computed")
    n_re = sum(1 for r in rows if r["retriggered"])
    dw = _day_words(D)
    w = window(D)
    wt = NEW_WINDOW_TEXT % (_day_words(w["through"]), _day_words(w["off_from"]))
    if w["half_day"]:
        wt += HALF_DAY_TEXT % (_day_words(w["through"]), w["rth_close"].strftime("%H:%M"))
    wparts = [NEW_WITHHELD_PART % (", ".join(withheld[r]), _why_text(r, {"T": D})) for r in NEW_WITHHELD
              if withheld[r]]
    out.update({"prior_day": piso, "corp_checked": corp_checked, "rows": rows, "n": len(rows), "n_official": n_off,
                "n_computed": n_comp, "n_retriggered": n_re,
                "sources_text": (NEW_SOURCES_TEXT % (n_off, n_comp)) if rows else None,
                "retriggered_text": (NEW_RETRIGGERED_TEXT % n_re) if n_re else None,
                "withheld": withheld, "withheld_text": (NEW_WITHHELD_TEXT % "; ".join(wparts)) if wparts else None,
                "faults": faults, "faults_text": (NEW_FAULTS_TEXT % len(faults)) if faults else None,
                "through": w["through"].isoformat(), "off_from": w["off_from"].isoformat(),
                "half_day": bool(w["half_day"]), "window_text": wt, "computed": computed, "sources": sources,
                "asof_text": asof or None})

    # 9. the honesty table, then the dividend / split sentence [C4]
    if not rows and not computed["ok"]:
        out["status"] = "not_read"
        out["fault_text"] = NEW_NOT_READ_TEXT % (GLYPH, TAG, dw, asof)
    elif not rows and not faults:                              # a faulted name is never "no name"
        out["empty_text"] = NEW_EMPTY_TEXT % (dw, computed["text"])
    parts = []
    if rows and not computed["ok"]:
        parts.append(NEW_PARTIAL_TEXT % computed["text"])
    if n_comp > 0 and not corp_checked:
        parts.append(NEW_CORP_UNREAD_TEXT % CORP_UNREAD_NOTE.strip())
    out["partial_text"] = " ".join(parts) or None
    return out
'''


def _old_new_triggers():
    """The pre-refactor `_new_triggers`, compiled in the module's own namespace."""
    ns = dict(vars(SSR))
    exec(compile(OLD_NEW_TRIGGERS, "<ssr._new_triggers before the refactor>", "exec"), ns)
    return ns["_new_triggers"]


def _scenarios():
    """(name, docs, now, lists, corp, D) — every branch of `_new_triggers` steps 2–9."""
    rows_23 = [nasdaq_row("ZZR", "2026-11-23", "09:31:00", file_date="2026-11-24")]
    corp_dz = read_corp(D24, **{"2026-11-24": {"ZZD": "dividend", "ZZT": "split"}})
    return [
        ("two_computed", [trig(D24, "ZZM", "minute_bar", at="10:00", low=2.5, drop_pct=-12.4, prev_close=2.85),
                          snap_doc(D24, "ZZS"), fresh_day()], NOW, Lists(), None, D24),
        ("official", [snap_doc(D24, "ZZN", drop=-13.0), fresh_day()], NOW,
         Lists(rows=[nasdaq_row("ZZN", "2026-11-24", "09:45:36"), nyse_row("ZZL", "2026-11-24", "13:01:02")]),
         None, D24),
        ("retrigger", [snap_doc(D24, "ZZR", seen="11:00"), fresh_day()], NOW, Lists(rows=rows_23), None, D24),
        ("corp_and_void", [snap_doc(D24, "ZZD"), snap_doc(D24, "ZZT"), snap_doc(D24, "ZZV", void=True), fresh_day()],
         NOW, Lists(rows=[nasdaq_row("ZZT", "2026-11-24", "10:10:10")]), corp_dz, D24),
        ("computed_only", [snap_doc(D24, "ZZK"), fresh_day()], NOW, Lists(complete={D24}), None, D24),
        ("list_fault", [fresh_day()], NOW, Lists(rows=[nasdaq_row("ZZO", "2026-11-24", "11:02:10")]), None, D24),
        ("not_read", [], NOW, Lists(), None, D24),
        ("empty", [fresh_day()], NOW, Lists(), None, D24),
        ("corp_unread", [fresh_day(), snap_doc(D24, "ZZS")], NOW, Lists(), Corp(load_raises=True), D24),
        ("pre_open", [snap_doc(D24, "ZZS"), fresh_day()], et(D24, 8, 0), Lists(), None, D24),
        ("saturday", [day_doc(D20, et(D20, 16, 5), final=True), snap_doc(D20, "ZZW")], et(D21, 12, 0), Lists(),
         read_corp(D20), D20),
        ("out_of_play", [fresh_day()], NOW, Lists(), None, D19),
        ("not_latest", [fresh_day()], NOW, Lists(), None, D23),
        ("half_day", [day_doc(D25, et(D25, 15, 0)), snap_doc(D25, "ZZH")], et(D25, 15, 30), Lists(),
         read_corp(D25), D25),
        ("nan_drop", [snap_doc(D24, "ZZS", drop=float("nan")), fresh_day()], NOW, Lists(), None, D24),
    ]


def _dump(out):
    return json.dumps(out, ensure_ascii=False, allow_nan=False, default=str)


@pytest.mark.parametrize("i", range(len(_scenarios())))
def test_01_new_triggers_is_byte_identical_before_and_after_the_refactor(i, monkeypatch):
    name, docs, now, lists, corp, D = _scenarios()[i]
    after = SSR.new_triggers(D, db=FakeDB(FakeColl(docs)), now=now, lists=lists,
                             corp=corp if corp is not None else read_corp(D))
    name, docs, now, lists, corp, D = _scenarios()[i]
    monkeypatch.setattr(SSR, "_new_triggers", _old_new_triggers())
    SSR._reset_cache()
    before = SSR.new_triggers(D, db=FakeDB(FakeColl(docs)), now=now, lists=lists,
                              corp=corp if corp is not None else read_corp(D))
    assert _dump(before) == _dump(after), name


def test_01_NEGATIVE_the_old_copy_is_really_the_old_body_and_rows_on_has_no_status_gate():
    assert "in_play(now_et)" in OLD_NEW_TRIGGERS and "_rows_on" not in OLD_NEW_TRIGGERS
    src = inspect.getsource(SSR._rows_on)
    assert "in_play" not in src and "status" not in src.split('"""')[-1]
    assert "_rows_on(D, db, now_et, lists, corp)" in inspect.getsource(SSR._new_triggers)


# ═════════════════════════════════════════════ POSITIVE — the recent read
def recent(docs=(), now=NOW, lists=None, corp=None, coll=None):
    coll = coll if coll is not None else FakeColl(docs)
    SSR._reset_cache()
    return SSR.recent_triggers(now, db=FakeDB(coll), lists=lists if lists is not None else Lists(),
                               corp=corp if corp is not None else all_read())


def all_read(**acts):
    """A READ corp day for every day these tests touch (no action unless given)."""
    days = {d.isoformat(): {} for d in (D19, D20, D23, D24, D25, D27, date(2026, 11, 18))}
    days.update(acts)
    return Corp(acts=days)


AKAN_ROW = nasdaq_row("AKAN", "2026-11-23", "09:30:12", file_date="2026-11-24")


def test_02_akan_triggered_1123_read_on_1124_is_day_2():
    out = recent([fresh_day()], lists=Lists(rows=[AKAN_ROW]))
    assert out["status"] == "ok" and out["kind"] == SSR.RECENT_KIND == "ssr_recent_triggers"
    assert out["today"] == "2026-11-24" and out["days"] == ["2026-11-24", "2026-11-23"] and out["faults"] == []
    a = out["by_symbol"]["AKAN"]
    assert a["triggered_on"] == "2026-11-23" and a["day_n"] == 2 and isinstance(a["day_n"], int)
    assert a["tag_text"] == "⛔ SSR 11/23 · day 2"
    assert a["source"] == "official" and a["exchange"] == "Nasdaq" and a["retriggered"] is False
    assert a["title"] == ("⛔ SSR started Mon 11/23 (Nasdaq list); today is day 2 counting the trigger day. "
                          + RS.NOT_A_SIGNAL)
    assert set(a) == set(SSR.RECENT_ROW_KEYS) and set(out) == set(SSR.RECENT_KEYS)


def test_03_a_trigger_today_is_day_1():
    out = recent([snap_doc(D24, "ZZS"), fresh_day()])
    r = out["by_symbol"]["ZZS"]
    assert r["day_n"] == 1 and r["triggered_on"] == "2026-11-24" and r["tag_text"] == "⛔ SSR 11/24 · day 1"
    assert r["source"] == "computed" and "(computed)" in r["title"]


def test_04_a_retrigger_the_newest_wins_and_is_marked():
    out = recent([snap_doc(D24, "AKAN", seen="11:00"), fresh_day()], lists=Lists(rows=[AKAN_ROW]))
    a = out["by_symbol"]["AKAN"]
    assert a["triggered_on"] == "2026-11-24" and a["day_n"] == 1 and a["retriggered"] is True
    assert a["tag_text"] == "⛔ SSR 11/24 · day 1" and list(out["by_symbol"]) == ["AKAN"]


def test_04_NEGATIVE_a_second_trigger_after_the_first_lapsed_is_new_never_retriggered(monkeypatch):
    monkeypatch.setattr(SSR, "SSR_RECENT_TRIGGER_DAYS", 2)                 # D20 in the read, its window ended D23
    lists = Lists(rows=[nasdaq_row("ZZY", "2026-11-20", "10:00:00", file_date="2026-11-23")])
    out = recent([snap_doc(D24, "ZZY"), fresh_day()], lists=lists)
    y = out["by_symbol"]["ZZY"]
    assert y["triggered_on"] == "2026-11-24" and y["day_n"] == 1 and y["retriggered"] is False
    assert list(out["by_symbol"]) == ["ZZY"]


def test_04_NEGATIVE_one_name_in_two_spellings_over_two_days_is_one_row():
    lists = Lists(rows=[nasdaq_row("ZZB.WS", "2026-11-23", "10:00:00", file_date="2026-11-24")])
    out = recent([snap_doc(D24, "ZZB-WS"), fresh_day()], lists=lists)
    assert list(out["by_symbol"]) == ["ZZB-WS"] and out["by_symbol"]["ZZB-WS"]["retriggered"] is True


def test_05_friday_to_monday_is_day_2():
    lists = Lists(rows=[nasdaq_row("ZZF", "2026-11-20", "10:00:00", file_date="2026-11-23")])
    out = recent([fresh_day(D23)], now=et(D23, 12, 0), lists=lists)
    assert out["days"] == ["2026-11-23", "2026-11-20"]
    f = out["by_symbol"]["ZZF"]
    assert f["day_n"] == 2 and f["tag_text"] == "⛔ SSR 11/20 · day 2" and "started Fri 11/20" in f["title"]


def test_05_a_holiday_is_skipped():
    lists = Lists(rows=[nasdaq_row("ZZG", "2026-11-25", "10:00:00", file_date="2026-11-27")])
    out = recent([day_doc(D27, et(D27, 12, 0))], now=et(D27, 12, 30), lists=lists)
    assert out["days"] == ["2026-11-27", "2026-11-25"]                      # Thu 11/26 Thanksgiving skipped
    assert out["by_symbol"]["ZZG"]["day_n"] == 2


def test_06_the_window_is_the_named_constant(monkeypatch):
    assert SSR.SSR_RECENT_TRIGGER_DAYS == SSR.SSR_FOLLOWING_TRADING_DAYS
    lists = Lists(rows=[nasdaq_row("ZZQ", "2026-11-20", "10:00:00", file_date="2026-11-23")])
    assert "ZZQ" not in recent([fresh_day()], lists=lists)["by_symbol"]
    monkeypatch.setattr(SSR, "SSR_RECENT_TRIGGER_DAYS", 2)
    out = recent([fresh_day()], lists=lists)
    assert out["days"] == ["2026-11-24", "2026-11-23", "2026-11-20"]
    assert out["by_symbol"]["ZZQ"]["day_n"] == 3 and out["by_symbol"]["ZZQ"]["tag_text"] == "⛔ SSR 11/20 · day 3"


# HIS CALL #1 (spec §7 #1, ASK FIRST) — his words "Days past little bit like AKAN" point at day 3 and later. These two
# pins make the as-built answer explicit so the ask is concrete; they do NOT pick a window (no number chosen here).
def test_06_NEGATIVE_his_call_1_as_built_akan_is_untagged_on_wed_1125_day_3():
    out = recent([fresh_day(D25)], now=et(D25, 12, 0), lists=Lists(rows=[AKAN_ROW]))
    assert out["status"] == "ok" and out["days"] == ["2026-11-25", "2026-11-24"]
    assert "AKAN" not in out["by_symbol"]


def test_06_his_call_1_widening_the_one_constant_keeps_akan_on_day_3(monkeypatch):
    monkeypatch.setattr(SSR, "SSR_RECENT_TRIGGER_DAYS", SSR.SSR_FOLLOWING_TRADING_DAYS + SSR.SSR_FOLLOWING_TRADING_DAYS)
    out = recent([fresh_day(D25)], now=et(D25, 12, 0), lists=Lists(rows=[AKAN_ROW]))
    assert out["days"] == ["2026-11-25", "2026-11-24", "2026-11-23"]
    a = out["by_symbol"]["AKAN"]
    assert a["triggered_on"] == "2026-11-23" and a["day_n"] == 3 and a["tag_text"] == "⛔ SSR 11/23 · day 3"
    assert "today is day 3 counting the trigger day" in a["title"]


# ═════════════════════════════════════════════ NEGATIVE — the recent read
def test_07_NEGATIVE_a_trigger_older_than_the_window_is_absent():
    lists = Lists(rows=[nasdaq_row("ZZO", "2026-11-20", "10:00:00", file_date="2026-11-23")])
    out = recent([snap_doc(D20, "ZZP"), fresh_day()], lists=lists)
    assert out["by_symbol"] == {} and out["days"] == ["2026-11-24", "2026-11-23"] and out["status"] == "ok"


def test_08_NEGATIVE_0359_pre_open_reads_no_1124_rows():
    out = recent([snap_doc(D24, "ZZS"), fresh_day()], now=et(D24, 3, 59), lists=Lists(rows=[AKAN_ROW]))
    assert out["days"] == ["2026-11-23"] and "ZZS" not in out["by_symbol"]
    assert out["by_symbol"]["AKAN"]["day_n"] == 2 and out["status"] == "ok"


def test_09_NEGATIVE_a_day_that_raises_is_a_fault_and_the_other_day_stands():
    class Half(Lists):
        def load(self, coll, now_et):
            if now_et.date() == D24:
                raise RuntimeError("synthetic: today's lists fail")
            return super().load(coll, now_et)
    out = recent([snap_doc(D24, "ZZS"), fresh_day()], lists=Half(rows=[AKAN_ROW]))
    assert out["status"] == "ok" and list(out["by_symbol"]) == ["AKAN"]
    assert out["faults"] == [{"day": "2026-11-24", "symbol": None}]


def test_09_NEGATIVE_every_day_raising_is_failed_never_empty_ok():
    coll = FakeColl([snap_doc(D24, "ZZS")])
    coll.raise_all = True
    out = recent(coll=coll)
    assert out["status"] == "failed" and out["by_symbol"] == {}
    assert [f["day"] for f in out["faults"]] == ["2026-11-24", "2026-11-23"]


def test_09_NEGATIVE_a_name_fault_is_recorded_with_its_day():
    lists = Lists(rows=[nasdaq_row("ZZX", "2026-11-24", "11:02:10")])        # a list name its rows do not carry
    real = SSR._day_eval

    def boom(ctx, s, T, trigs):
        if s == "ZZX":
            raise RuntimeError("synthetic")
        return real(ctx, s, T, trigs)
    import unittest.mock as um
    with um.patch.object(SSR, "_day_eval", boom):
        out = recent([fresh_day()], lists=lists)
    assert {"day": "2026-11-24", "symbol": "ZZX"} in out["faults"] and "ZZX" not in out["by_symbol"]


def test_10_NEGATIVE_a_corp_action_day_is_withheld():
    out = recent([snap_doc(D23, "ZZD"), snap_doc(D23, "ZZE"), fresh_day()],
                 corp=all_read(**{"2026-11-23": {"ZZD": "dividend"}}))
    assert "ZZD" not in out["by_symbol"] and out["by_symbol"]["ZZE"]["day_n"] == 2


def test_11_NEGATIVE_nan_is_none_and_the_read_is_strict_json():
    out = recent([snap_doc(D24, "ZZS", drop=float("nan")), fresh_day()])
    assert out["by_symbol"]["ZZS"]["day_n"] == 1
    json.dumps(out, allow_nan=False)
    got = SSR._rows_on(D24, FakeDB(FakeColl([snap_doc(D24, "ZZS", drop=float("nan")), fresh_day()])), NOW, Lists(),
                       all_read())
    assert got["rows"][0]["drop_pct"] is None
    for bad in (float("nan"), float("inf"), "x", None, True):
        assert SSR._finite(bad) is None


def test_12_NEGATIVE_mongo_none_is_failed():
    out = SSR.recent_triggers(NOW, db=None, lists=Lists(), corp=all_read())
    assert out["status"] == "failed" and out["by_symbol"] == {} and out["today"] == "2026-11-24"
    assert set(out) == set(SSR.RECENT_KEYS)


@pytest.mark.parametrize("bad", ["x", object(), 12])
def test_12_NEGATIVE_a_junk_clock_is_failed_never_raises(bad):
    out = SSR.recent_triggers(bad, db=FakeDB(FakeColl()), lists=Lists(), corp=all_read())
    assert out["status"] in SSR.RECENT_STATUSES and out["by_symbol"] == {}


@pytest.mark.parametrize("now", [et(D21, 12, 0), et(date(2026, 11, 26), 12, 0)])
def test_13_NEGATIVE_a_closed_day_is_closed(now):
    lists = Lists(rows=[nasdaq_row("ZZW", "2026-11-20", "10:00:00"), AKAN_ROW])
    out = recent([day_doc(D20, et(D20, 16, 5), final=True), snap_doc(D20, "ZZW"), snap_doc(D25, "ZZH")], now=now,
                 lists=lists)
    assert out["status"] == "closed" and out["by_symbol"] == {} and out["days"] == [] and out["faults"] == []


def _int_literals(fn):
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]


def test_14_NEGATIVE_no_numeric_literal_in_the_recent_read():
    for fn in (SSR.recent_triggers, SSR._recent_triggers, SSR._recent_base, SSR._recent_failed):
        assert _int_literals(fn) == [], fn.__name__


def test_15_NEGATIVE_no_writes_no_kicks_and_clean_words():
    coll = FakeColl([snap_doc(D24, "ZZS"), fresh_day()])
    lists = Lists(rows=[AKAN_ROW], due=True)
    out = recent(coll=coll, lists=lists, corp=all_read())
    assert coll.writes == [] and lists.kicks == []
    for r in out["by_symbol"].values():
        assert r["title"].endswith(RS.NOT_A_SIGNAL) and not FORBIDDEN.search(r["title"] + r["tag_text"])
        assert "squeeze" not in r["title"].lower()
    src = "\n".join(inspect.getsource(f) for f in (SSR.recent_triggers, SSR._recent_triggers, SSR._rows_on))
    for banned in ("kick_refresh", "update_one", "insert", "replace_one", "record_pass", ".payload(", "_http"):
        assert banned not in src, banned


def test_15_every_status_has_every_key():
    outs = [recent([fresh_day()]), recent(now=et(D21, 12, 0)),
            SSR.recent_triggers(NOW, db=None, lists=Lists(), corp=all_read())]
    assert sorted(o["status"] for o in outs) == ["closed", "failed", "ok"]
    for o in outs:
        assert set(o) == set(SSR.RECENT_KEYS) and o["kind"] == SSR.RECENT_KIND
        json.dumps(o, allow_nan=False)
