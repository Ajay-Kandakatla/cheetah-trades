"""fed_schedule — the Federal Reserve's own calendar (2026-10-07).

Ajay 2026-10-07: "First today there was an FOMC event why is it not in our new
tab in chart maps. I want us to pull dynamic dates". Fixtures are the real
federalreserve.gov pages captured 2026-10-07 by
scripts/capture_fed_calendar_fixtures.py (calendar.json trimmed by the filter
documented there; fomccalendars.htm verbatim). No network: `http` and `store`
are injected everywhere.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date

import pytest
import requests

import fed_schedule as F

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_FX = os.path.join(HERE, "fixtures", "fed_calendar_2026_10_07.json")
HTM_FX = os.path.join(HERE, "fixtures", "fed_fomccalendars_2026_10_07.htm")
TODAY = date(2026, 10, 7)


def _json_text():
    with open(JSON_FX, encoding="utf-8") as f:
        return f.read()


def _htm_text():
    with open(HTM_FX, encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def cal():
    return F.parse_calendar_json(_json_text(), TODAY)


@pytest.fixture(scope="module")
def htm():
    return F.parse_fomccalendars_htm(_htm_text(), TODAY)


def _floor(year):
    return [d for d in F.FLOOR_DECISION_DATES if d.startswith(str(year))]


class FakeStore:
    def __init__(self, docs=None):
        self.docs = {k: dict(v) for k, v in (docs or {}).items()}
        self.writes = []

    def find_one(self, q):
        d = self.docs.get(q["_id"])
        return dict(d) if d else None

    def update_one(self, q, upd, upsert=False):
        self.writes.append((q, upd))
        cur = self.docs.setdefault(q["_id"], {"_id": q["_id"]})
        cur.update(upd.get("$set") or {})


def _http_ok(calls=None):
    def h(url, lm):
        if calls is not None:
            calls.append((url, lm))
        if url == F.FED_CALENDAR_JSON_URL:
            return 200, _json_text(), "Fri, 02 Oct 2026 18:30:12 GMT"
        return 200, _htm_text(), "Wed, 16 Sep 2026 19:37:22 GMT"
    return h


def _raiser(*a, **k):
    raise AssertionError("http must not be called")


# ── calendar.json ────────────────────────────────────────────────────────────
def test_json_fixture_starts_with_bom_and_parses_ok(cal):
    assert _json_text().startswith("﻿")
    assert cal["ok"] is True and cal["reason"] is None


def test_json_2026_meetings_equal_the_floor_at_2pm(cal):
    m26 = [m for m in cal["meetings"] if m["date"].startswith("2026")]
    assert [m["date"] for m in m26] == _floor(2026)
    assert all(m["time_et"] == "14:00" for m in m26)
    assert cal["years"]["2026"] == 8


def test_json_2026_minutes(cal):
    mins = [m for m in cal["minutes"] if m["date"].startswith("2026")]
    assert [m["date"] for m in mins] == ["2026-02-18", "2026-04-08", "2026-05-20", "2026-07-08",
                                         "2026-08-19", "2026-10-07", "2026-11-18", "2026-12-30"]
    assert all(m["time_et"] == "14:00" for m in mins)
    oct7 = next(m for m in mins if m["date"] == "2026-10-07")
    assert oct7["meeting"] == "September 15-16"
    # the leading-space title ' FOMC Minutes' (2026-02-18) is in the raw fixture and parsed
    assert '" FOMC Minutes"' in _json_text() or "' FOMC Minutes'" in repr(_json_text())
    assert "2026-02-18" in [m["date"] for m in mins]


def test_json_pressers_and_beige(cal):
    pr = [p for p in cal["pressers"] if p["date"].startswith("2026")]
    assert [p["date"] for p in pr] == _floor(2026)
    assert all(p["time_et"] == "14:30" for p in pr)
    beige = {b["date"]: b["time_et"] for b in cal["beige"]}
    assert beige["2026-10-14"] == "14:00" and beige["2026-11-25"] == "14:00"


def test_json_remarks_chair_flag(cal):
    rem = cal["remarks"]
    waller = [r for r in rem if r["date"] == "2026-10-08" and "Waller" in r["who"]]
    assert waller and waller[0]["time_et"] == "04:30" and waller[0]["chair"] is False
    warsh = [r for r in rem if r["date"] == "2026-07-14" and "Warsh" in r["who"]]
    assert warsh and warsh[0]["chair"] is True and warsh[0]["what"] == "Testimony"


def test_json_vice_chairs_are_not_chair(cal):
    # NEGATIVE: "Vice Chair …" never counts as the Chair.
    jeff = [r for r in cal["remarks"] if r["who"].startswith("Vice Chair Philip N. Jefferson")]
    bow = [r for r in cal["remarks"] if r["who"].startswith("Vice Chair for Supervision Michelle W. Bowman")]
    assert jeff and bow
    assert all(r["chair"] is False for r in jeff + bow)


def test_json_ignores_other_types_and_undated_rows(cal):
    raw = json.loads(_json_text().lstrip("﻿"))
    assert any(e.get("type") == "Stat" for e in raw["events"])
    assert any(e.get("type") == "events" and not e.get("month") for e in raw["events"])
    stat_titles = {e["title"] for e in raw["events"] if e.get("type") == "Stat"}
    every = cal["meetings"] + cal["pressers"] + cal["minutes"] + cal["beige"]
    assert not any(r.get("who") in stat_titles for r in cal["remarks"])
    assert len(every) > 0


# ── fomccalendars.htm ────────────────────────────────────────────────────────
def test_htm_years_and_floor_agreement(htm):
    assert htm["ok"] is True
    assert {y: htm["years"][y] for y in map(str, range(2021, 2028))} == {str(y): 8 for y in range(2021, 2028)}
    for y in (2026, 2027):
        assert [m["date"] for m in htm["meetings"] if m["date"].startswith(str(y))] == _floor(y)


def test_htm_sep_flags(htm):
    for y in ("2026", "2027"):
        sep = sorted(m["date"][5:7] for m in htm["meetings"] if m["date"].startswith(y) and m["sep"])
        assert sep == ["03", "06", "09", "12"], (y, sep)


def test_htm_cross_month_rows(htm):
    dates = {m["date"] for m in htm["meetings"]}
    assert "2024-05-01" in dates            # Apr/May 30-1
    assert "2023-02-01" in dates            # Jan/Feb 31-1


def test_htm_notation_vote_skipped(htm):
    # NEGATIVE: a notation vote is never a decision row.
    assert any("2025 August 22 (notation vote)" == s for s in htm["skipped"])
    assert "2025-08-22" not in {m["date"] for m in htm["meetings"]}


def test_htm_minutes_released_is_not_a_fixed_offset(htm):
    nov = next(m for m in htm["meetings"] if m["date"] == "2024-11-07")
    assert nov["minutes_released"] == "2024-11-26"      # +19, so +21 is no rule


# ── to_24h ───────────────────────────────────────────────────────────────────
def test_to_24h():
    assert F.to_24h("2:00 p.m.") == "14:00"
    assert F.to_24h("12:00 p.m.") == "12:00"
    assert F.to_24h("12:15 a.m.") == "00:15"
    assert F.to_24h("4:30 a.m.") == "04:30"


@pytest.mark.parametrize("bad", ["", "13:00 p.m.", "2 p.m.", None, 14, "2:60 p.m.", "noon"])
def test_to_24h_negative(bad):
    assert F.to_24h(bad) is None


# ── merge ────────────────────────────────────────────────────────────────────
def test_merge_sources_per_year(cal, htm):
    m = F.merge(cal, htm, TODAY)
    by = {d["date"]: d for d in m["decisions"]}
    assert by["2026-10-28"]["source"] == F.SOURCE_LABEL[F.SRC_JSON]
    assert by["2027-01-27"]["source"] == F.SOURCE_LABEL[F.SRC_HTM]
    assert by["2024-09-18"]["source"] == F.SOURCE_LABEL[F.SRC_HTM]
    assert by["2026-12-09"]["sep"] is True and by["2026-10-28"]["sep"] is False
    assert by["2026-10-28"]["presser_time_et"] == "14:30" and by["2026-10-28"]["time_et"] == "14:00"
    assert by["2027-01-27"]["presser_time_et"] is None and by["2027-01-27"]["time_et"] is None
    assert 2026 in m["json_years"] and 2027 in m["htm_years"] and 2024 in m["htm_years"]
    assert m["floor_years"] == []
    assert [d for d in sorted(by) if d >= "2024-09-18"] == list(F.FLOOR_DECISION_DATES)


def test_merge_without_json_never_invents_minutes(htm):
    # NEGATIVE: no calendar.json → no minutes, Beige or remarks, ever (no +21 estimate).
    m = F.merge(None, htm, TODAY)
    assert m["minutes"] == [] and m["beige"] == [] and m["remarks"] == []
    assert all(d["presser_time_et"] is None and d["time_et"] is None for d in m["decisions"])
    m2 = F.merge(F.parse_calendar_json(_json_text(), TODAY), htm, TODAY)
    assert not any(r["date"].startswith("2027") for r in m2["minutes"])


def test_merge_both_none_is_the_floor():
    m = F.merge(None, None, TODAY)
    assert [d["date"] for d in m["decisions"]] == list(F.FLOOR_DECISION_DATES)
    assert all(d["source"] == F.SOURCE_LABEL["floor"] for d in m["decisions"])
    assert all(d["presser_time_et"] is None and d["time_et"] is None and d["sep"] is None
               for d in m["decisions"])
    assert all("Federal Reserve" in v for v in F.SOURCE_LABEL.values())


# ── sanity negatives ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("body", ["{not json", '{"events": {}}', '{"events": []}', "", "[]"])
def test_json_garbage_is_not_ok(body):
    assert F.parse_calendar_json(body, TODAY)["ok"] is False


def test_json_three_meetings_is_not_ok():
    ev = [{"type": "FOMC", "title": "FOMC Meeting", "month": m, "days": d, "time": "2:00 p.m."}
          for m, d in (("2026-01", "28"), ("2026-03", "18"), ("2026-04", "29"))]
    ev.append({"type": "FOMC", "title": "FOMC Minutes", "month": "2026-02", "days": "18", "time": "2:00 p.m."})
    out = F.parse_calendar_json(json.dumps({"events": ev}), TODAY)
    assert out["ok"] is False and "3 meetings" in out["reason"]


def test_htm_layout_change_is_not_ok():
    t = _htm_text().replace("FOMC Meetings</a></h4>", "FOMC Schedule</a></h4>")
    assert F.parse_fomccalendars_htm(t, TODAY)["ok"] is False


def test_htm_only_one_panel_is_not_ok():
    t = _htm_text()
    j = t.index('<h4><a id="42827">2025 FOMC Meetings')
    one = t[:j]                                      # the 2026 panel is first on the page
    out = F.parse_fomccalendars_htm(one, TODAY)
    assert out["years"] == {"2026": 8}
    assert out["ok"] is False


def test_json_row_bounds_dropped_and_counted():
    good = [{"type": "FOMC", "title": "FOMC Meeting", "month": d[:7], "days": str(int(d[8:])),
             "time": "2:00 p.m."} for d in _floor(2026)]
    good.append({"type": "FOMC", "title": "FOMC Minutes", "month": "2026-10", "days": "7", "time": "2:00 p.m."})
    bad = [
        {"type": "FOMC", "title": "FOMC Minutes", "month": "2026-13", "days": "1", "time": "2:00 p.m."},
        {"type": "FOMC", "title": "FOMC Minutes", "month": "2026-10", "days": "32", "time": "2:00 p.m."},
        {"type": "FOMC", "title": "FOMC Meeting", "month": "2026-10", "days": "10", "time": "2:00 p.m."},  # Saturday
        {"type": "Beige", "title": "Beige Book", "month": "2029-10", "days": "10", "time": "2:00 p.m."},
        {"type": "Beige", "title": "Beige Book", "month": "2019-10", "days": "16", "time": "2:00 p.m."},
    ]
    out = F.parse_calendar_json(json.dumps({"events": good + bad}), TODAY)
    assert out["ok"] is True and out["rejected"] == 5
    dates = {r["date"] for k in ("meetings", "minutes", "beige") for r in out[k]}
    assert not {"2026-10-10", "2029-10-10", "2019-10-16"} & dates
    assert not any(d.startswith("2026-13") for d in dates)


# ── refresh_due ──────────────────────────────────────────────────────────────
def test_refresh_writes_lkg_then_keeps_it_through_failures():
    store, calls = FakeStore(), []
    lkg = F.refresh_due(store=store, http=_http_ok(calls), now=1000.0, today=TODAY)
    assert len(calls) == 2
    for src in (F.SRC_JSON, F.SRC_HTM):
        assert lkg[src]["parsed"]["ok"] is True and lkg[src]["fetched_at"] == 1000.0
        assert store.docs[src]["parsed"]["ok"] is True and store.docs[src]["last_error"] is None
    good = {src: store.docs[src]["parsed"] for src in (F.SRC_JSON, F.SRC_HTM)}

    later = 1000.0 + F.FED_REFRESH_SEC
    failures = [
        (lambda u, lm: (500, "", None), "HTTP 500"),
        (lambda u, lm: (_ for _ in ()).throw(requests.Timeout("https://x/?api_key=SECRET")), "Timeout"),
        (lambda u, lm: (200, "{garbled", None), "parse: "),
        (lambda u, lm: (200, '{"events": []}' if u == F.FED_CALENDAR_JSON_URL else "<html></html>", None), "parse: "),
    ]
    for i, (h, err) in enumerate(failures):
        now = later + i * F.FED_REFRESH_SEC
        out = F.refresh_due(store=store, http=h, now=now, today=TODAY)
        for src in (F.SRC_JSON, F.SRC_HTM):
            assert store.docs[src]["parsed"] == good[src], (err, src)
            assert out[src]["parsed"] == good[src]
            assert store.docs[src]["last_error"].startswith(err), (err, store.docs[src]["last_error"])
            assert store.docs[src]["fetched_at"] == 1000.0          # age NOT reset by a failure
            assert store.docs[src]["last_attempt_at"] == now
            le = store.docs[src]["last_error"]
            assert not ("http" in le.lower() and "://" in le), le          # never a URL
            assert "SECRET" not in le


def test_refresh_304_bumps_age_keeps_parsed():
    store = FakeStore()
    F.refresh_due(store=store, http=_http_ok(), now=1000.0, today=TODAY)
    good = store.docs[F.SRC_JSON]["parsed"]
    seen = []

    def h304(url, lm):
        seen.append(lm)
        return 304, "", None

    now = 1000.0 + F.FED_REFRESH_SEC + 5
    F.refresh_due(store=store, http=h304, now=now, today=TODAY)
    assert store.docs[F.SRC_JSON]["parsed"] == good
    assert store.docs[F.SRC_JSON]["fetched_at"] == now
    assert seen[0] == "Fri, 02 Oct 2026 18:30:12 GMT"       # If-Modified-Since sent


def test_fresh_lkg_never_fetches():
    store = FakeStore()
    F.refresh_due(store=store, http=_http_ok(), now=1000.0, today=TODAY)
    F.refresh_due(store=store, http=_raiser, now=1000.0 + F.FED_REFRESH_SEC - 1, today=TODAY)


def test_no_store_no_fetch():
    # NEGATIVE: no store → no fetch (keeps every test hermetic).
    out = F.refresh_due(store=None, http=_raiser, now=1.0, today=TODAY)
    assert out == {F.SRC_JSON: None, F.SRC_HTM: None}
    sched = F.current(store=None, http=_raiser, today=TODAY)
    assert sched["status"]["floor"] is True
    assert [d["date"] for d in sched["decisions"]] == list(F.FLOOR_DECISION_DATES)


def test_write_failure_still_returns_fresh_doc():
    class Blocked(FakeStore):
        def update_one(self, *a, **k):
            raise RuntimeError("blocked")

    out = F.refresh_due(store=Blocked(), http=_http_ok(), now=5.0, today=TODAY)
    assert out[F.SRC_JSON]["parsed"]["ok"] is True and out[F.SRC_HTM]["parsed"]["ok"] is True


def test_default_coll_in_tests_is_none_so_load_is_floor():
    # conftest refuses MongoClient → _coll() None → floor, never a fetch.
    assert F._coll() is None
    s = F.load(today=TODAY)
    assert s["status"]["floor"] is True and s["minutes"] == []


def test_http_get_uses_requests_get_with_ua(monkeypatch):
    seen = {}

    class R:
        status_code, text, headers = 200, "x", {"Last-Modified": "lm"}

    def g(url, headers=None, timeout=None):
        seen.update(url=url, headers=headers, timeout=timeout)
        return R()

    monkeypatch.setattr(requests, "get", g)
    assert F._http_get(F.FED_CALENDAR_JSON_URL, "old") == (200, "x", "lm")
    assert seen["headers"]["User-Agent"] == F.FED_USER_AGENT
    assert seen["headers"]["If-Modified-Since"] == "old"
    assert seen["timeout"] == F.FED_TIMEOUT


# ── status_view ──────────────────────────────────────────────────────────────
def test_status_view_fresh_stale_floor():
    store = FakeStore()
    sched = F.current(store=store, http=_http_ok(), now=1000.0, today=TODAY)
    v = F.status_view(sched["status"], now=1000.0 + 3600)
    assert v["note"] == F.FED_NOTE_OK and v["stale"] is False and v["floor"] is False
    assert v["age_sec"] == 3600
    st = F.status_view(sched["status"], now=1000.0 + F.FED_STALE_SEC + 1)
    assert st["stale"] is True and st["note"] == F.FED_NOTE_STALE.format(as_of=sched["status"]["as_of_iso"])
    # 2026-10-07 critic fix: no store → the store note (never "Fed unreachable");
    # a working store whose LKG is empty → the floor note.
    fl = F.status_view(F.load(store=None, today=TODAY)["status"])
    assert fl["note"] == F.FED_NOTE_NO_STORE and fl["floor"] is True
    fl2 = F.status_view(F.load(store=FakeStore(), today=TODAY)["status"])
    assert fl2["note"] == F.FED_NOTE_FLOOR and fl2["floor"] is True
    assert F.status_view(None) is None


def test_status_sources_shape():
    store = FakeStore()
    s = F.current(store=store, http=_http_ok(), now=1000.0, today=TODAY)["status"]
    j, h = s["sources"][F.SRC_JSON], s["sources"][F.SRC_HTM]
    assert j["ok"] is True and j["n_minutes"] >= 8 and j["last_error"] is None
    assert h["ok"] is True and h["years"] == list(range(2021, 2028))
    assert s["as_of"] == 1000.0 and s["floor"] is False


def test_module_never_logs_exception_text():
    src = open(F.__file__, encoding="utf-8").read()
    assert not re.search(r"log\.\w+\([^)]*,\s*exc\)", src)
    assert "str(exc)" not in src
