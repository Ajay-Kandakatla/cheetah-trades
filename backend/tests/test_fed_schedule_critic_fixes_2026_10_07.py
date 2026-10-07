"""Critic fixes on the Fed calendar (2026-10-07).

Ajay 2026-10-07: "First today there was an FOMC event why is it not in our new
tab in chart maps. I want us to pull dynamic dates". Two critics then found:
  * MEDIUM — merge() took calendar.json for a year as soon as it had ≥ 6
    meetings, so ONE json meeting row that failed to parse silently dropped a
    decision the FOMC page lists (the same bug class he reported).
  * low — weekend Chair remarks rejected as malformed; the 304 branch pinned an
    older parser's output; the floor note blamed the Fed when Mongo failed; no
    note when calendar.json never parsed; Chair times labelled ET with no
    source stating a zone; three fixes no test pinned (_earnings_ahead on ET,
    the same-day time tiebreak, the "no minutes this year" ok clause).
Every test below fails if its fix is reverted. No network, no Mongo.
"""
from __future__ import annotations

import datetime as dt
import json
import os

import pytest

import fed_schedule as F
import macro_calendar as mc

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = dt.date(2026, 10, 7)
ET = dt.timezone(dt.timedelta(hours=-4))


def _read(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as f:
        return f.read()


def _json_text():
    return _read("fed_calendar_2026_10_07.json")


def _htm_text():
    return _read("fed_fomccalendars_2026_10_07.htm")


def _events():
    return json.loads(_json_text().lstrip("﻿"))["events"]


def _dump(events):
    return json.dumps({"events": events})


class FakeStore:
    def __init__(self, docs=None):
        self.docs = {k: dict(v) for k, v in (docs or {}).items()}

    def find_one(self, q):
        d = self.docs.get(q["_id"])
        return dict(d) if d else None

    def update_one(self, q, upd, upsert=False):
        self.docs.setdefault(q["_id"], {"_id": q["_id"]}).update(upd.get("$set") or {})


def _http_ok(calls=None):
    def h(url, lm):
        if calls is not None:
            calls.append((url, lm))
        if url == F.FED_CALENDAR_JSON_URL:
            return 200, _json_text(), "Fri, 02 Oct 2026 18:30:12 GMT"
        return 200, _htm_text(), "Wed, 16 Sep 2026 19:37:22 GMT"
    return h


# ── MEDIUM: one unparsed json meeting row never drops a decision ─────────────
def _json_minus_oct_meeting():
    ev = _events()
    hit = 0
    for e in ev:
        if (e.get("type") == "FOMC" and str(e.get("title") or "").strip().lower() == "fomc meeting"
                and e.get("month") == "2026-10"):
            e["title"] = "FOMC Meeting and Press Conference"       # a title the parser does not know
            hit += 1
    assert hit == 1
    return F.parse_calendar_json(_dump(ev), TODAY)


def test_merge_keeps_htm_decision_when_a_json_meeting_row_fails():
    cal = _json_minus_oct_meeting()
    htm = F.parse_fomccalendars_htm(_htm_text(), TODAY)
    assert cal["ok"] is True and cal["years"]["2026"] == 7 and htm["years"]["2026"] == 8
    m = F.merge(cal, htm, TODAY)
    by = {d["date"]: d for d in m["decisions"]}
    assert "2026-10-28" in by                                   # reverted fix: missing
    assert by["2026-10-28"]["source"] == F.SOURCE_LABEL[F.SRC_HTM]
    assert 2026 in m["htm_years"] and 2026 not in m["json_years"]
    assert [d for d in sorted(by) if d.startswith("2026")] == \
        [d for d in F.FLOOR_DECISION_DATES if d.startswith("2026")]
    # the dates json still has keep their json time; the decision json lost has none (never invented)
    assert by["2026-09-16"]["time_et"] == "14:00" and by["2026-10-28"]["time_et"] is None


def test_next_fomc_is_oct_28_with_one_json_meeting_row_unparsed(monkeypatch):
    m = F.merge(_json_minus_oct_meeting(), F.parse_fomccalendars_htm(_htm_text(), TODAY), TODAY)
    monkeypatch.setattr(mc, "_today_et", lambda: TODAY)
    assert mc.next_fomc(m)["date"] == "2026-10-28"              # reverted fix: 2026-12-09


def test_merge_json_with_as_many_meetings_as_htm_still_wins():
    # NEGATIVE: the fix must not demote a complete calendar.json year.
    cal = F.parse_calendar_json(_json_text(), TODAY)
    m = F.merge(cal, F.parse_fomccalendars_htm(_htm_text(), TODAY), TODAY)
    assert 2026 in m["json_years"] and 2026 not in m["htm_years"]


def test_merge_json_with_more_meetings_than_htm_wins():
    # NEGATIVE: htm short for a year (its own parse slip) → json, not htm.
    cal = F.parse_calendar_json(_json_text(), TODAY)
    htm = F.parse_fomccalendars_htm(_htm_text(), TODAY)
    htm = {**htm, "meetings": [r for r in htm["meetings"] if r["date"] != "2026-12-09"]}
    m = F.merge(cal, htm, TODAY)
    assert 2026 in m["json_years"]
    assert "2026-12-09" in {d["date"] for d in m["decisions"]}


# ── weekend Chair remarks are real rows, weekend releases are not ────────────
def test_weekend_chair_speeches_are_kept():
    cal = F.parse_calendar_json(_json_text(), TODAY)
    rows = {(r["date"], r["who"]): r for r in cal["remarks"]}
    sat = rows[("2026-03-21", "Chair Jerome H. Powell")]       # MEASURED: a Saturday
    assert dt.date(2026, 3, 21).weekday() == 5
    assert sat["chair"] is True and sat["time_et"] == "13:30" and sat["what"] == "Speech"
    assert rows[("2025-05-25", "Chair Jerome H. Powell")]["chair"] is True   # a Sunday


@pytest.mark.parametrize("row", [
    {"type": "FOMC", "title": "FOMC Meeting", "month": "2026-10", "days": "10", "time": "2:00 p.m."},
    {"type": "FOMC", "title": "FOMC Minutes", "month": "2026-10", "days": "11", "time": "2:00 p.m."},
    {"type": "FOMC", "title": "FOMC Press Conference", "month": "2026-10", "days": "10", "time": "2:30 p.m."},
    {"type": "Beige", "title": "Beige Book", "month": "2026-10", "days": "17", "time": "2:00 p.m."},
])
def test_weekend_fomc_and_beige_rows_still_rejected(row):
    # NEGATIVE: the weekday bound still guards meetings, minutes, pressers and Beige.
    base = F.parse_calendar_json(_json_text(), TODAY)
    out = F.parse_calendar_json(_dump(_events() + [row]), TODAY)
    assert out["rejected"] == base["rejected"] + 1
    every = {r["date"] for k in ("meetings", "pressers", "minutes", "beige") for r in out[k]}
    assert f"{row['month']}-{int(row['days']):02d}" not in every


def test_out_of_years_remark_still_rejected():
    # NEGATIVE: remarks keep the year bound.
    row = {"type": "Speeches", "title": "Speech - Chair Jerome H. Powell", "month": "2019-03",
           "days": "8", "time": "1:30 p.m."}
    base = F.parse_calendar_json(_json_text(), TODAY)
    out = F.parse_calendar_json(_dump(_events() + [row]), TODAY)
    assert out["rejected"] == base["rejected"] + 1
    assert not any(r["date"] == "2019-03-08" for r in out["remarks"])


# ── the ok clause: no current-year minutes → not ok ──────────────────────────
def test_json_without_current_year_minutes_is_not_ok():
    ev = [e for e in _events()
          if not (e.get("type") == "FOMC" and str(e.get("title") or "").strip().lower() == "fomc minutes"
                  and str(e.get("month") or "").startswith("2026"))]
    out = F.parse_calendar_json(_dump(ev), TODAY)
    assert out["years"]["2026"] == 8                            # meetings alone would pass
    assert out["ok"] is False and out["reason"] == "no minutes in 2026"


# ── schema: an older parser's LKG is re-parsed, never pinned by a 304 ────────
def test_old_schema_lkg_is_refetched_without_if_modified_since():
    store = FakeStore()
    F.refresh_due(store=store, http=_http_ok(), now=1000.0, today=TODAY)
    for src in (F.SRC_JSON, F.SRC_HTM):
        store.docs[src]["schema"] = F._SCHEMA - 1
        store.docs[src]["parsed"] = {**store.docs[src]["parsed"], "minutes": []}   # the old output
    calls = []

    def h(url, lm):
        calls.append((url, lm))
        if lm:
            return 304, "", None
        return _http_ok()(url, lm)

    F.refresh_due(store=store, http=h, now=1000.0 + 60, today=TODAY)   # fresh by age
    assert len(calls) == 2 and all(lm is None for _u, lm in calls)    # reverted fix: 0 calls
    assert store.docs[F.SRC_JSON]["schema"] == F._SCHEMA
    assert store.docs[F.SRC_JSON]["parsed"]["minutes"]                # re-parsed


def test_old_schema_lkg_kept_when_the_refetch_fails():
    # NEGATIVE: a failed re-read keeps the old LKG (never blanks the list).
    store = FakeStore()
    F.refresh_due(store=store, http=_http_ok(), now=1000.0, today=TODAY)
    store.docs[F.SRC_JSON]["schema"] = F._SCHEMA - 1
    good = store.docs[F.SRC_JSON]["parsed"]
    out = F.refresh_due(store=store, http=lambda u, lm: (503, "", None), now=1060.0, today=TODAY)
    assert out[F.SRC_JSON]["parsed"] == good and store.docs[F.SRC_JSON]["last_error"] == "HTTP 503"
    assert F.load(store=store, today=TODAY)["minutes"]


def test_current_schema_lkg_is_not_refetched():
    # NEGATIVE: same schema + fresh → no fetch.
    store = FakeStore()
    F.refresh_due(store=store, http=_http_ok(), now=1000.0, today=TODAY)

    def boom(*a, **k):
        raise AssertionError("must not fetch")
    F.refresh_due(store=store, http=boom, now=1060.0, today=TODAY)


# ── notes: never blame the Fed for a store failure; say when json is missing ─
def test_no_store_note_does_not_blame_the_fed():
    for s in (F.load(store=None, today=TODAY), F.current(store=None, today=TODAY)):
        v = F.status_view(s["status"])
        assert v["floor"] is True and s["status"]["store_ok"] is False
        assert v["note"] == F.FED_NOTE_NO_STORE and "unreachable" not in v["note"]


def test_store_present_but_fed_never_answered_is_the_floor_note():
    # NEGATIVE: a working store whose LKG is empty → the Fed really never answered.
    s = F.load(store=FakeStore(), today=TODAY)
    v = F.status_view(s["status"])
    assert s["status"]["store_ok"] is True and v["note"] == F.FED_NOTE_FLOOR


def test_htm_only_lkg_says_minutes_not_shown():
    store = FakeStore()
    F.refresh_due(store=store, http=_http_ok(), now=1000.0, today=TODAY)
    store.docs.pop(F.SRC_JSON)
    s = F.load(store=store, today=TODAY)
    v = F.status_view(s["status"], now=1000.0 + 60)
    assert s["minutes"] == [] and v["floor"] is False and v["stale"] is False
    assert v["note"] == F.FED_NOTE_NO_JSON                      # reverted fix: FED_NOTE_OK
    assert "not shown" in v["note"]


def test_both_sources_fresh_is_the_ok_note():
    # NEGATIVE: both LKGs present → the ok note, not the no-json note.
    store = FakeStore()
    s = F.current(store=store, http=_http_ok(), now=1000.0, today=TODAY)
    assert F.status_view(s["status"], now=1060.0)["note"] == F.FED_NOTE_OK


def test_coll_closes_the_client_when_the_ping_fails(monkeypatch):
    import pymongo
    made = []

    class Admin:
        def command(self, *_a):
            raise RuntimeError("no server")

    class Client:
        def __init__(self, *a, **k):
            self.admin, self.closed = Admin(), False
            made.append(self)

        def close(self):
            self.closed = True

    monkeypatch.setattr(pymongo, "MongoClient", Client)
    monkeypatch.setattr(F, "_COLL", None)
    assert F._coll() is None
    assert len(made) == 1 and made[0].closed is True             # reverted fix: leaked


# ── Chair times carry no zone; FOMC times keep ET ────────────────────────────
def test_chair_time_label_has_no_et():
    w = mc.when_fields("2026-10-07", "10:00", "fed_chair", today=TODAY,
                       now=dt.datetime(2026, 10, 7, 11, 0, tzinfo=ET))
    assert w["time_label"] == "10:00 am" and w["past_label"] == "began 10:00 am"
    assert "ET" not in w["time_label"]


def test_fomc_minutes_time_label_keeps_et():
    # NEGATIVE: the ET-by-publication kinds keep " ET".
    w = mc.when_fields("2026-10-07", "14:00", "fomc_minutes", today=TODAY,
                       now=dt.datetime(2026, 10, 7, 15, 0, tzinfo=ET))
    assert w["time_label"] == "2:00 pm ET" and w["past_label"] == "released 2:00 pm ET"
    assert mc.time_label("14:00", et=False) == "2:00 pm" and mc.time_label("bad", et=False) is None


# ── same-day order: timed rows before untimed rows of the same tier ──────────
def _sched_today(today):
    s = F.merge(F.parse_calendar_json(_json_text(), TODAY), F.parse_fomccalendars_htm(_htm_text(), TODAY),
                TODAY)
    s["status"] = None
    return s


def test_compute_orders_fomc_14h_before_untimed_t1_same_day(monkeypatch):
    s = _sched_today(dt.date(2026, 10, 27))
    monkeypatch.setattr(F, "current", lambda **k: s)
    monkeypatch.setattr(mc, "_today_et", lambda: dt.date(2026, 10, 27))
    monkeypatch.setattr(mc, "_earnings_ahead", lambda days: [])
    monkeypatch.setattr(mc, "_fred_releases", lambda days: [
        {"date": "2026-10-28", "kind": "cpi", "tier": 1, "label": "CPI", "source": "FRED"}])
    d = mc.compute(14)
    day = [e["kind"] for e in d["macro"] if e["date"] == "2026-10-28"]
    assert day == ["fomc", "cpi"]                               # reverted tiebreak: ["cpi", "fomc"]


def test_imminent_orders_by_time_even_from_an_unsorted_doc(monkeypatch):
    doc = {"macro": [
        {"date": "2026-10-28", "kind": "cpi", "tier": 1, "label": "CPI", "source": "FRED"},
        {"date": "2026-10-28", "kind": "fomc", "tier": 1, "label": "FOMC decision", "time_et": "14:00"},
        {"date": "2026-10-28", "kind": "claims", "tier": 2, "label": "Jobless claims", "time_et": "08:30"},
    ]}
    monkeypatch.setattr(mc, "get_macro_calendar", lambda *a, **k: doc)
    monkeypatch.setattr(mc, "_today_et", lambda: dt.date(2026, 10, 27))
    monkeypatch.setattr(mc, "_now_et", lambda: dt.datetime(2026, 10, 27, 9, 0, tzinfo=ET))
    ev = mc.imminent_events(5, max_tier=2)
    # tier first (NEGATIVE: the 08:30 T2 row never jumps a T1 row), then time
    assert [e["kind"] for e in ev] == ["fomc", "cpi", "claims"]


# ── _earnings_ahead runs on the ET day, not UTC ──────────────────────────────
class _Late(mc.datetime):
    @classmethod
    def now(cls, tz=None):
        u = mc.datetime(2026, 10, 8, 3, 30, tzinfo=mc.timezone.utc)   # 10-07 23:30 ET
        return u.astimezone(tz) if tz else u.replace(tzinfo=None)


def test_earnings_ahead_uses_et_day_at_2330(monkeypatch):
    import catalysts.calendar as cc
    monkeypatch.setattr(mc, "datetime", _Late)
    monkeypatch.setattr(mc, "_earnings_universe", lambda: ["AAA", "BBB", "CCC"])
    rows = {"AAA": "2026-10-07", "BBB": "2026-10-21", "CCC": "2026-10-22"}
    monkeypatch.setattr(cc, "_next_earnings", lambda t: {"ticker": t, "date": rows[t]})
    assert mc._today_et() == TODAY
    out = mc._earnings_ahead(14)
    # today (ET) kept — the UTC day (10-08) would drop AAA. NEGATIVE: 10-22 is past the 14-day cutoff.
    assert [(e["date"], e["ticker"]) for e in out] == [("2026-10-07", "AAA"), ("2026-10-21", "BBB")]
