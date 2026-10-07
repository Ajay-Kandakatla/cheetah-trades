"""macro_calendar × the Federal Reserve's own calendar (2026-10-07).

Ajay 2026-10-07: "First today there was an FOMC event why is it not in our new
tab in chart maps. I want us to pull dynamic dates". The 10-07 event was the
FOMC MINUTES (2:00 p.m. ET). The schedule here is built from the two real
federalreserve.gov fixtures via fed_schedule.merge and injected by patching
fed_schedule.current / load — no network, no Mongo.
"""
from __future__ import annotations

import ast
import datetime as dt
import inspect
import logging
import os

import pytest
import requests

import fed_schedule as F
import macro_calendar as mc
import macro_indicators as MI
from chart_maps import news_tab as NT
from chart_maps import resiliency_tab as RT

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = dt.date(2026, 10, 7)
ET = dt.timezone(dt.timedelta(hours=-4))


def _read(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def parsed():
    return (F.parse_calendar_json(_read("fed_calendar_2026_10_07.json"), TODAY),
            F.parse_fomccalendars_htm(_read("fed_fomccalendars_2026_10_07.htm"), TODAY))


def _sched(cal, htm, floor_flag=False):
    s = F.merge(cal, htm, TODAY)
    s["status"] = {"as_of": 1000.0, "as_of_iso": "1970-01-01T00:16:40Z", "floor": floor_flag,
                   "sources": {}}
    return s


@pytest.fixture
def fed(monkeypatch, parsed):
    s = _sched(*parsed)
    monkeypatch.setattr(F, "current", lambda **k: s)
    monkeypatch.setattr(F, "load", lambda **k: s)
    monkeypatch.setattr(mc, "_fred_releases", lambda days: [])
    monkeypatch.setattr(mc, "_earnings_ahead", lambda days: [])
    monkeypatch.setattr(mc, "_today_et", lambda: TODAY)
    return s


def _at(h, m, day=TODAY):
    return dt.datetime(day.year, day.month, day.day, h, m, tzinfo=ET)


def _serve(monkeypatch, doc):
    monkeypatch.setattr(mc, "get_macro_calendar", lambda *a, **k: doc)


# ── compute(14) on 2026-10-07 ────────────────────────────────────────────────
def test_compute_has_todays_minutes_and_beige(fed):
    d = mc.compute(14)
    trip = {(e["date"], e["kind"], e["tier"]) for e in d["macro"]}
    assert ("2026-10-07", "fomc_minutes", 2) in trip
    assert ("2026-10-14", "beige_book", 3) in trip
    m = next(e for e in d["macro"] if e["kind"] == "fomc_minutes")
    assert m["time_et"] == "14:00" and m["detail"] == "Meeting of September 15-16"
    assert m["label"] == "FOMC minutes" and "Federal Reserve" in m["source"]
    # NEGATIVE: no decision inside 14 days; no Governor (non-Chair) row
    assert not any(e["kind"] == "fomc" for e in d["macro"])
    assert not any("Waller" in (e.get("detail") or "") for e in d["macro"])
    nf = d["next_fomc"]
    assert nf["date"] == "2026-10-28" and nf["label"] == "FOMC decision"
    assert "press conference 2:30 pm ET" in nf["detail"]
    assert "dot plot" not in nf["detail"]                    # October is not an SEP meeting
    assert d["fed"]["floor"] is False
    for k in ("generated_at", "days", "macro", "macro_by_tier", "next_tier1", "earnings",
              "earnings_by_day", "n_macro", "available", "tier_taxonomy"):
        assert k in d


def test_next_fomc_december_is_sep(fed, monkeypatch):
    monkeypatch.setattr(mc, "_today_et", lambda: dt.date(2026, 12, 1))
    nf = mc.next_fomc(fed)
    assert nf["date"] == "2026-12-09" and "dot plot (SEP)" in nf["detail"]


def test_compute_survives_a_raising_schedule(monkeypatch):
    # NEGATIVE: current() AND load() raising → floor decisions, no crash.
    def boom(**k):
        raise RuntimeError("x")
    monkeypatch.setattr(F, "current", boom)
    monkeypatch.setattr(F, "load", boom)
    monkeypatch.setattr(mc, "_fred_releases", lambda days: [])
    monkeypatch.setattr(mc, "_earnings_ahead", lambda days: [])
    monkeypatch.setattr(mc, "_today_et", lambda: dt.date(2026, 10, 20))
    d = mc.compute(14)
    assert [e["date"] for e in d["macro"] if e["kind"] == "fomc"] == ["2026-10-28"]
    assert not any(e["kind"] in mc.FED_KIND_TIERS for e in d["macro"])
    assert d["fed"] is None


# ── imminent_events: read-time past / time labels ────────────────────────────
@pytest.mark.parametrize("hm,past,plabel", [
    ((13, 59), False, None),
    ((14, 0), True, "released 2:00 pm ET"),
    ((23, 30), True, "released 2:00 pm ET"),
])
def test_imminent_minutes_past_flag(fed, monkeypatch, hm, past, plabel):
    doc = mc.compute(14)
    _serve(monkeypatch, doc)
    monkeypatch.setattr(mc, "_now_et", lambda: _at(*hm))
    ev = mc.imminent_events(14, max_tier=2)
    m = next(e for e in ev if e["kind"] == "fomc_minutes")
    assert m["past"] is past and m["past_label"] == plabel
    assert m["time_label"] == "2:00 pm ET" and m["when_label"] == "today"
    assert m["detail"] == "Meeting of September 15-16"


def test_imminent_untimed_row_past_is_none(fed, monkeypatch):
    monkeypatch.setattr(mc, "_fred_releases", lambda days: [
        {"date": "2026-10-07", "kind": "claims", "tier": 2, "label": "Jobless claims", "source": "FRED"}])
    _serve(monkeypatch, mc.compute(14))
    monkeypatch.setattr(mc, "_now_et", lambda: _at(15, 0))
    c = next(e for e in mc.imminent_events(14, max_tier=2) if e["kind"] == "claims")
    assert c["past"] is None and c["time_label"] is None and c["past_label"] is None


def test_imminent_chair_row_began(monkeypatch, parsed):
    s = _sched(*parsed)
    s["remarks"] = s["remarks"] + [{"date": "2026-10-07", "time_et": "10:00", "what": "Speech",
                                    "who": "Chairman Kevin Warsh", "topic": "Economic Outlook",
                                    "chair": True, "source": F.SOURCE_LABEL[F.SRC_JSON]},
                                   {"date": "2026-10-07", "time_et": "09:00", "what": "Speech",
                                    "who": "Governor Christopher J. Waller", "topic": "x",
                                    "chair": False, "source": F.SOURCE_LABEL[F.SRC_JSON]}]
    monkeypatch.setattr(F, "current", lambda **k: s)
    monkeypatch.setattr(mc, "_fred_releases", lambda days: [])
    monkeypatch.setattr(mc, "_earnings_ahead", lambda days: [])
    monkeypatch.setattr(mc, "_today_et", lambda: TODAY)
    _serve(monkeypatch, mc.compute(14))
    monkeypatch.setattr(mc, "_now_et", lambda: _at(11, 0))
    ev = mc.imminent_events(14, max_tier=2)
    ch = [e for e in ev if e["kind"] == "fed_chair"]
    assert len(ch) == 1 and ch[0]["past_label"].startswith("began")
    assert ch[0]["detail"] == "Speech · Chairman Kevin Warsh — Economic Outlook"
    # sort: the 10:00 chair row sits before the 14:00 minutes row (same day, same tier)
    kinds = [e["kind"] for e in ev if e["date"] == "2026-10-07"]
    assert kinds.index("fed_chair") < kinds.index("fomc_minutes")


def test_when_fields_engine():
    w = mc.when_fields("2026-10-08", "04:30", "fed_chair", today=TODAY, now=_at(23, 0))
    # 2026-10-07 critic fix: Chair times carry no zone (the Fed states none).
    assert w["when_label"] == "tomorrow" and w["past"] is False and w["time_label"] == "4:30 am"
    assert mc.when_fields("junk", "14:00", "x", today=TODAY) is None
    assert mc.time_label("00:15") == "12:15 am ET" and mc.time_label("12:00") == "12:00 pm ET"
    for bad in (None, "", "25:00", "2pm", 14):
        assert mc.time_label(bad) is None


# ── the ET fix on _fred_releases ─────────────────────────────────────────────
class _Late(mc.datetime):
    @classmethod
    def now(cls, tz=None):
        u = mc.datetime(2026, 10, 8, 3, 30, tzinfo=mc.timezone.utc)   # 10-07 23:30 ET
        return u.astimezone(tz) if tz else u.replace(tzinfo=None)


def test_fred_window_is_ET_not_UTC(monkeypatch):
    import sepa.fred
    calls = []

    class R:
        status_code = 200

        def json(self):
            return {"release_dates": [{"date": "2026-10-07", "release_name": "Consumer Price Index"}]}

    def g(*a, **k):
        calls.append(k.get("params") or {})
        return R()

    monkeypatch.setattr(mc, "datetime", _Late)
    monkeypatch.setattr(mc, "_today_et", lambda: TODAY)
    monkeypatch.setattr(sepa.fred, "api_key", lambda: "testkey")
    monkeypatch.setattr(requests, "get", g)
    out = mc._fred_releases(14)
    assert calls[0]["realtime_start"] == "2026-10-07"
    assert [(e["date"], e["kind"]) for e in out] == [("2026-10-07", "cpi")]   # kept (UTC dropped it)


def test_fred_log_never_carries_the_key(monkeypatch, caplog):
    import sepa.fred
    monkeypatch.setattr(sepa.fred, "api_key", lambda: "SECRET")

    def g(*a, **k):
        raise requests.ConnectionError("https://api.stlouisfed.org/fred/releases/dates?api_key=SECRET")

    monkeypatch.setattr(requests, "get", g)
    with caplog.at_level(logging.DEBUG):
        assert mc._fred_releases(14) == []
    assert caplog.records
    assert not any("SECRET" in r.getMessage() for r in caplog.records)
    assert any("ConnectionError" in r.getMessage() for r in caplog.records)


# ── past_events: decisions only, from the schedule ───────────────────────────
def _empty_fetch(path, params):
    return {}


def test_past_events_fomc_from_schedule(fed):
    out = mc.past_events("2025-01-01", "2026-10-07", fetch=_empty_fetch)
    fomc = [e for e in out["events"] if e["kind"] == "fomc"]
    want = [d["date"] for d in fed["decisions"] if "2025-01-01" <= d["date"] <= "2026-10-07"]
    assert [e["date"] for e in fomc] == want and len(want) == 14
    for e in fomc:
        assert set(e) == {"date", "kind", "tier", "label", "source", "release_id"}
        assert e["source"] == mc.HISTORY_FOMC_SOURCE and e["label"] == mc.HISTORY_FOMC_LABEL
    # NEGATIVE: minutes / Beige / Chair never enter history
    assert not {e["kind"] for e in out["events"]} & set(mc.FED_KIND_TIERS)


def test_past_events_htm_only_2024(monkeypatch, parsed):
    s = _sched(None, parsed[1])
    monkeypatch.setattr(F, "load", lambda **k: s)
    out = mc.past_events("2024-01-01", "2024-02-28", fetch=_empty_fetch)
    assert [e["date"] for e in out["events"] if e["kind"] == "fomc"] == ["2024-01-31"]
    # NEGATIVE: the floor alone (starts 2024-09) has no 2024-01-31
    monkeypatch.setattr(F, "load", lambda **k: _sched(None, None))
    out2 = mc.past_events("2024-01-01", "2024-02-28", fetch=_empty_fetch)
    assert not [e for e in out2["events"] if e["kind"] == "fomc"]


# ── source guard ─────────────────────────────────────────────────────────────
def test_no_code_iterates_the_floor_constant():
    tree = ast.parse(inspect.getsource(mc))
    for n in ast.walk(tree):
        iters = []
        if isinstance(n, ast.For):
            iters.append(n.iter)
        if isinstance(n, ast.comprehension):
            iters.append(n.iter)
        for it in iters:
            names = {x.id for x in ast.walk(it) if isinstance(x, ast.Name)}
            assert "FOMC_DECISION_DATES" not in names
    assert mc.FOMC_DECISION_DATES is F.FLOOR_DECISION_DATES
    assert 'kind == "fomc"' in inspect.getsource(mc._fred_releases)


def test_fed_tiers_pinned_and_taxonomy_built():
    assert mc.FED_KIND_TIERS == {"fomc_minutes": 2, "beige_book": 3, "fed_chair": 2}, \
        "HIS CALL (spec §7.1-7.3): change the tiers deliberately"
    assert "FOMC minutes" in mc.TIER_TAXONOMY["2"] and "Fed Chair remarks" in mc.TIER_TAXONOMY["2"]
    assert "Beige Book" in mc.TIER_TAXONOMY["3"]
    moved = mc._build_taxonomy(mc._BASE_TAXONOMY, {**mc.FED_KIND_TIERS, "fomc_minutes": 1},
                               mc.FED_KIND_LABELS)
    assert "FOMC minutes" in moved["1"] and "FOMC minutes" not in moved["2"]
    assert mc._BASE_TAXONOMY["2"][-1] == "Fed-speaker remarks"           # base never mutated
    assert not set(mc.FED_KIND_TIERS) & mc.HISTORY_KINDS


# ── 📰 News macro block ──────────────────────────────────────────────────────
def test_news_block_minutes_row_carries_time(fed, monkeypatch):
    _serve(monkeypatch, mc.compute(14))
    monkeypatch.setattr(mc, "_now_et", lambda: _at(14, 30))
    m = NT.macro_block()
    row = next(e for e in m["events"] if e["kind"] == "fomc_minutes")
    assert row["time_label"] == "2:00 pm ET" and row["past_label"] == "released 2:00 pm ET"
    assert row["detail"] == "Meeting of September 15-16" and row["past"] is True
    assert not any(e["kind"] == "beige_book" for e in m["events"])        # T3 stays off News
    assert m["next_fomc"]["date"] == "2026-10-28" and m["next_fomc"]["when_label"] == "in 21 days"
    assert m["fed"]["note"] == F.FED_NOTE_OK or m["fed"]["stale"] is True


def test_news_next_tier1_is_rederived_at_read_time(monkeypatch):
    # NEGATIVE: the doc's stale next_tier1 (yesterday's CPI) is never served.
    ev = [{"date": "2026-10-07", "kind": "fomc", "tier": 1, "label": "FOMC decision", "time_et": "14:00"},
          {"date": "2026-10-14", "kind": "cpi", "tier": 1, "label": "CPI"}]
    doc = {"macro": ev, "tier_labels": dict(mc.TIER_LABELS),
           "next_tier1": {"date": "2026-10-06", "kind": "cpi", "tier": 1, "label": "CPI"}}
    _serve(monkeypatch, doc)
    monkeypatch.setattr(mc, "_today_et", lambda: TODAY)
    monkeypatch.setattr(mc, "_now_et", lambda: _at(15, 0))
    m = NT.macro_block()
    assert m["next_tier1"]["kind"] == "cpi" and m["next_tier1"]["date"] == "2026-10-14"
    # before 2 pm the FOMC row is still the next mover
    monkeypatch.setattr(mc, "_now_et", lambda: _at(9, 0))
    assert NT.macro_block()["next_tier1"]["kind"] == "fomc"


def _doc_with_next(nf, macro=()):
    return {"macro": list(macro), "tier_labels": dict(mc.TIER_LABELS), "next_fomc": nf,
            "fed": {"as_of": None, "as_of_iso": None, "floor": True, "sources": {}}}


def test_news_next_fomc_rules(monkeypatch):
    monkeypatch.setattr(mc, "_today_et", lambda: TODAY)
    monkeypatch.setattr(mc, "_now_et", lambda: _at(9, 0))
    nf = {"date": "2026-10-28", "kind": "fomc", "tier": 1, "label": "FOMC decision",
          "time_et": "14:00", "detail": "press conference 2:30 pm ET", "sep": False}
    _serve(monkeypatch, _doc_with_next(nf))
    got = NT.macro_block()["next_fomc"]
    assert got["date"] == "2026-10-28" and got["detail"] == "press conference 2:30 pm ET"
    assert got["past"] is False and got["days_until"] == 21
    # NEGATIVE: the same decision already a served row → not pinned
    _serve(monkeypatch, _doc_with_next(nf, [{**nf}]))
    monkeypatch.setattr(mc, "_today_et", lambda: dt.date(2026, 10, 20))
    assert NT.macro_block()["next_fomc"] is None
    # NEGATIVE: a next_fomc already behind today → not served
    monkeypatch.setattr(mc, "_today_et", lambda: TODAY)
    _serve(monkeypatch, _doc_with_next({**nf, "date": "2026-10-06"}))
    assert NT.macro_block()["next_fomc"] is None


def test_news_fed_view(monkeypatch):
    monkeypatch.setattr(mc, "_today_et", lambda: TODAY)
    _serve(monkeypatch, _doc_with_next(None))
    m = NT.macro_block()
    assert m["fed"]["floor"] is True and m["fed"]["note"] == F.FED_NOTE_FLOOR
    # NEGATIVE: no `fed` in the doc → None, no crash
    _serve(monkeypatch, {"macro": [], "tier_labels": dict(mc.TIER_LABELS)})
    m2 = NT.macro_block()
    assert m2["ok"] is True and m2["fed"] is None and m2["next_fomc"] is None and m2["next_tier1"] is None


# ── 🛡️ Resiliency keeps its measured event set ────────────────────────────────
def test_resiliency_ignores_fed_calendar_kinds():
    day = dt.date(2026, 10, 7)
    cal = {"macro": [
        {"date": "2026-10-07", "kind": "fomc_minutes", "tier": 2, "label": "FOMC minutes"},
        {"date": "2026-10-07", "kind": "fed_chair", "tier": 2, "label": "Fed Chair remarks"}]}
    assert RT._session_events(cal, [], day)["tier"] is None
    cal_pos = {"macro": [{"date": "2026-10-07", "kind": "fomc", "tier": 1, "label": "FOMC decision"}]}
    assert RT._session_events(cal_pos, [], day)["tier"] == 1
    cal_next = {"macro": [
        {"date": "2026-10-08", "kind": "fomc_minutes", "tier": 1, "label": "FOMC minutes"},
        {"date": "2026-10-14", "kind": "cpi", "tier": 1, "label": "CPI"}]}
    assert RT._next_t1(cal_next, day) == {"date": "2026-10-14", "label": "CPI"}


# ── macro_indicators: Fed Funds next release ─────────────────────────────────
def test_next_releases_fomc_from_schedule(fed):
    assert MI._next_releases() == {"fomc": "2026-10-28"}


def test_next_releases_survives_next_fomc_raising(monkeypatch):
    monkeypatch.setattr(mc, "_fred_releases", lambda days: [
        {"date": "2026-10-14", "kind": "cpi", "tier": 1, "label": "CPI", "source": "FRED"}])

    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(mc, "next_fomc", boom)
    assert MI._next_releases() == {"cpi": "2026-10-14"}
