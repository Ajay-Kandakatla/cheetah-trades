"""WP-E feed-blind-probe (spec §3.6, critique C7, 2026-11-16) — the blind fraction of THE one Massive socket, replayed
from the feed's own timeline rows with the feed's own rule (`live_feed._on_drop` / `_on_auth` / `_is_kick`).

Pure: hand-made row lists, and rows the real feed functions emit. No Mongo, no network, nothing written.
"""
from __future__ import annotations

import ast
from collections import deque
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import live_feed
from chart_maps.gajjala import constants as GC
from market_hours import gate as MH_GATE
from scripts import live_feed_blind_fraction as P

ET = ZoneInfo("America/New_York")
SRC = (Path(__file__).resolve().parents[1] / "scripts" / "live_feed_blind_fraction.py").read_text()
MON = date(2026, 11, 16)
SAT = date(2026, 11, 14)
T0 = datetime(2026, 11, 16, 10, 0, tzinfo=ET).timestamp()
OPEN, CLOSE = P.day_window(MON)


def conn(ts):
    return {"ts": ts, "kind": "connect"}


def auth(ts):
    return {"ts": ts, "kind": "auth", "status": "auth_success"}


def close(ts, code=1006, message=None):
    return {"ts": ts, "kind": "close", "close_code": code, "message": message}


def kick_status(ts):
    return {"ts": ts, "kind": "status", "status": live_feed.KICK_STATUS, "message": "limit"}


def authed_link(ts):
    return [conn(ts), auth(ts + 0.3)]


# ── blind_windows: the feed's pairing rule ─────────────────────────────────────────────────────────────────────────
def test_one_authed_close_then_auth_is_one_30s_window():
    rows = authed_link(T0) + [close(T0 + 100), conn(T0 + 129.7), auth(T0 + 130)]
    w = P.blind_windows(rows, OPEN, CLOSE)
    assert w == [(T0 + 100, T0 + 130)]
    assert sum(b - a for a, b in w) == pytest.approx(30.0)


@pytest.mark.parametrize("second", [close(T0 + 110, code=None, message="timed out"),
                                    close(T0 + 110, code=1008)])
def test_second_close_before_auth_does_not_reopen(second):
    rows = authed_link(T0) + [close(T0 + 100), conn(T0 + 105), second, conn(T0 + 129.7), auth(T0 + 130)]
    assert P.blind_windows(rows, OPEN, CLOSE) == [(T0 + 100, T0 + 130)]


def test_negative_auth_without_open_window_adds_nothing():
    assert P.blind_windows(authed_link(T0), OPEN, CLOSE) == []
    assert P.blind_windows([auth(T0)], OPEN, CLOSE) == []


def test_negative_failed_connect_opens_nothing():
    rows = [conn(T0), close(T0 + 20, code=None, message="timed out during opening handshake"),
            conn(T0 + 40), auth(T0 + 40.3)]
    assert P.blind_windows(rows, OPEN, CLOSE) == []
    assert P.blind_windows([close(T0 + 5, code=None, message="refused"), conn(T0 + 9), auth(T0 + 9.3)],
                           OPEN, CLOSE) == []


def test_negative_auth_belongs_to_its_connection_only():
    rows = authed_link(T0) + [close(T0 + 50), conn(T0 + 80), close(T0 + 90, code=None, message="boom"),
                              conn(T0 + 95), auth(T0 + 96)]
    assert P.blind_windows(rows, OPEN, CLOSE) == [(T0 + 50, T0 + 96)]


def test_kicked_close_without_auth_opens_like_the_feed():
    rows = [conn(T0), kick_status(T0 + 0.2), close(T0 + 0.2, code=1008), conn(T0 + 30), auth(T0 + 30.3)]
    assert P.blind_windows(rows, OPEN, CLOSE) == [(T0 + 0.2, T0 + 30.3)]


def test_negative_rows_outside_the_window_are_ignored():
    before = OPEN - 3600
    after = CLOSE + 60
    rows = (authed_link(before) + [close(before + 10), conn(before + 39), auth(before + 40)]
            + authed_link(after) + [close(after + 10), conn(after + 39), auth(after + 40)])
    assert P.blind_windows(rows, OPEN, CLOSE) == []


def test_window_straddling_open_is_clipped_at_open():
    rows = authed_link(OPEN - 100) + [close(OPEN - 20), conn(OPEN + 9), auth(OPEN + 10)]
    assert P.blind_windows(rows, OPEN, CLOSE) == [(OPEN, OPEN + 10)]


def test_window_still_open_is_clipped_at_close_epoch():
    rows = authed_link(CLOSE - 100) + [close(CLOSE - 30)]
    assert P.blind_windows(rows, OPEN, CLOSE) == [(CLOSE - 30, CLOSE)]
    assert P.blind_windows(rows, OPEN, CLOSE - 30) == []


# ── kicks: one per kicked drop (= live_feed._is_kick), constants read from live_feed ───────────────────────────────
def test_kick_status_then_close_counts_one():
    assert P.kicks(authed_link(T0) + [kick_status(T0 + 5), close(T0 + 5, code=1000)]) == 1


def test_kick_close_code_counts_one():
    assert P.kicks(authed_link(T0) + [close(T0 + 5, code=live_feed.KICK_CLOSE_CODE)]) == 1


def test_kick_text_in_close_message_counts_one():
    msg = f"server said {live_feed.KICK_STATUS.upper()}"
    assert P.kicks(authed_link(T0) + [close(T0 + 5, code=None, message=msg)]) == 1


def test_negative_status_plus_kick_close_is_one_kick_not_two():
    rows = authed_link(T0) + [kick_status(T0 + 5), close(T0 + 5, code=live_feed.KICK_CLOSE_CODE)]
    assert P.kicks(rows) == 1


def test_negative_clean_close_counts_no_kick():
    assert P.kicks(authed_link(T0) + [close(T0 + 5, code=1000)]) == 0
    assert P.kicks(authed_link(T0) + [close(T0 + 5, code=None)]) == 0


def test_negative_kick_status_with_no_drop_yet_counts_nothing():
    assert P.kicks(authed_link(T0) + [kick_status(T0 + 5)]) == 0


def test_negative_kick_status_does_not_leak_into_next_connection():
    rows = authed_link(T0) + [kick_status(T0 + 5), close(T0 + 5, code=1008)] + authed_link(T0 + 35) + \
        [close(T0 + 90, code=1000)]
    assert P.kicks(rows) == 1


def test_kicks_constants_are_read_at_call_time(monkeypatch):
    monkeypatch.setattr(live_feed, "KICK_CLOSE_CODE", 4242)
    assert P.kicks(authed_link(T0) + [close(T0 + 5, code=4242)]) == 1
    assert P.kicks(authed_link(T0) + [close(T0 + 5, code=1008)]) == 0


def test_kicks_counted_inside_the_day_window_only():
    rows = authed_link(OPEN - 100) + [close(OPEN - 50, code=1008), conn(OPEN - 20), auth(OPEN - 19),
                                      close(OPEN + 50, code=1008)]
    assert P.kicks(rows, OPEN, CLOSE) == 1


# ── the feed itself agrees: rows the real live_feed emits, replayed, give the feed's own counters ─────────────────
@pytest.fixture
def fresh_feed(monkeypatch):
    monkeypatch.setattr(live_feed, "_events", deque(maxlen=live_feed.EVENTS_MAX))
    monkeypatch.setattr(live_feed, "_kick_times", deque(maxlen=live_feed.EVENTS_MAX))
    monkeypatch.setattr(live_feed, "_today", {"day": None, "kicks": 0, "blind_s": 0.0})
    monkeypatch.setattr(live_feed, "_link", {"conn_ts": None, "trades": 0, "kicked": False, "auth_ts": None,
                                             "drop_ts": None, "kick_pending": False, "yielding_wait": None,
                                             "last_kick_ts": None, "resume_s_last": None})
    monkeypatch.setattr(live_feed, "_persist_event", lambda row: None)
    return live_feed


def _feed_connect(f, ts, *, auth_ok=True, kick_at=None, drop_at, code, text="", clean=False):
    f._link.update(conn_ts=ts, trades=0, kicked=False)
    f._timeline("connect", ts)
    authed = False
    if auth_ok:
        f._note_status("auth_success", "authenticated", ts + 0.3)
        f._on_auth(ts + 0.3)
        authed = True
    if kick_at is not None:
        f._note_status(f.KICK_STATUS, "limit", kick_at)
    f._on_drop(was_authed=authed, exc_text=text, close_code=code, backoff=2, clean=clean, now=drop_at)


def test_replay_equals_the_feeds_own_blind_s_and_kicks(fresh_feed):
    f = fresh_feed
    _feed_connect(f, T0, kick_at=T0 + 80, drop_at=T0 + 80, code=f.KICK_CLOSE_CODE)
    _feed_connect(f, T0 + 110, auth_ok=False, drop_at=T0 + 112, code=None, text="handshake timed out")
    _feed_connect(f, T0 + 130, drop_at=T0 + 300, code=1006, text="no close frame")
    _feed_connect(f, T0 + 330, drop_at=T0 + 400, code=1000, clean=True)
    _feed_connect(f, T0 + 400.5, kick_at=T0 + 500, drop_at=T0 + 500, code=f.KICK_CLOSE_CODE)
    _feed_connect(f, T0 + 530, drop_at=T0 + 900, code=1000, clean=True)
    f._timeline("connect", T0 + 901)
    f._note_status("auth_success", "authenticated", T0 + 901.3)
    f._on_auth(T0 + 901.3)
    rows = list(f._events)
    w = P.blind_windows(rows, OPEN, CLOSE)
    assert sum(b - a for a, b in w) == pytest.approx(f._today["blind_s"], abs=0.01)
    assert P.kicks(rows, OPEN, CLOSE) == f._today["kicks"] == 2
    assert len(w) == 5


# ── day rows, summary, markdown ────────────────────────────────────────────────────────────────────────────────────
def test_negative_empty_day_is_no_rows_never_zero_pct():
    d = P.day_row([], MON)
    assert d["blind_s"] == 0.0 and d["kicks"] == 0 and d["note"] == P.NO_ROWS
    assert d["blind_pct"] is None
    assert d["blind_pct"] != 0.0


def test_day_with_rows_and_no_drop_is_zero_pct_not_none():
    d = P.day_row(authed_link(T0), MON)
    assert d["blind_pct"] == 0.0 and d["note"] is None


def test_day_row_numbers():
    rows = authed_link(T0) + [kick_status(T0 + 100), close(T0 + 100, code=1008), conn(T0 + 129.7), auth(T0 + 130)]
    d = P.day_row(rows, MON)
    assert d["window_s"] == round(CLOSE - OPEN, 1)
    assert d["blind_s"] == 30.0 and d["kicks"] == 1 and d["gaps_s"] == [30.0]
    assert d["blind_pct"] == round(100 * 30 / (CLOSE - OPEN), 2)


def test_today_is_clipped_at_now():
    now = T0 + 200
    rows = authed_link(T0) + [close(T0 + 100)]
    d = P.day_row(rows, MON, now=now)
    assert d["window_s"] == round(now - OPEN, 1)
    assert d["blind_s"] == 100.0


def test_day_window_reads_the_pass_constants_by_name(monkeypatch):
    lo, hi = P.day_window(MON)
    assert lo == datetime.combine(MON, datetime.strptime(GC.PASS_OPEN_ET, "%H:%M").time(), tzinfo=ET).timestamp()
    assert hi == datetime.combine(MON, datetime.strptime(GC.PASS_CLOSE_ET, "%H:%M").time(), tzinfo=ET).timestamp()
    monkeypatch.setattr(GC, "PASS_OPEN_ET", "05:00")
    assert P.day_window(MON)[0] == lo + 3600
    assert "GC.PASS_OPEN_ET" in SRC and "GC.PASS_CLOSE_ET" in SRC


def test_negative_weekend_with_rows_is_skipped():
    sat_t = datetime(2026, 11, 14, 10, 0, tzinfo=ET).timestamp()
    rows = authed_link(sat_t) + [close(sat_t + 100)] + authed_link(T0)
    days = P.build_days(rows, SAT, MON)
    assert [d["day"] for d in days] == ["2026-11-16"]


def test_negative_stubbed_closed_day_is_skipped(monkeypatch):
    calls = []

    def stub(now=None):
        calls.append(now.date())
        return "holiday 2026-11-16" if now.date() == MON else None
    monkeypatch.setattr(MH_GATE, "closed_reason", stub)
    days = P.build_days(authed_link(T0), date(2026, 11, 13), MON)
    assert [d["day"] for d in days] == ["2026-11-13", "2026-11-14", "2026-11-15"]
    assert calls == [date(2026, 11, 13), date(2026, 11, 14), date(2026, 11, 15), MON]


def test_summary_median_over_days_with_rows_only():
    days = [{"day": "a", "blind_pct": 10.0, "kicks": 4, "gaps_s": [30.0, 40.0]},
            {"day": "b", "blind_pct": 20.0, "kicks": 2, "gaps_s": [50.0]},
            {"day": "c", "blind_pct": None, "kicks": 0, "gaps_s": [], "note": P.NO_ROWS}]
    s = P.summarize(days)
    assert s["sessions"] == 2
    assert s["blind_pct_median"] == 15.0 and s["blind_pct_mean"] == 15.0
    assert s["kicks_per_session"] == 3.0
    assert s["gap_s_p50"] == 40.0 and s["gap_s_p90"] == 48.0


def test_negative_summary_with_no_rows_is_none_not_zero():
    s = P.summarize([P.day_row([], MON)])
    assert s["sessions"] == 0
    assert s["blind_pct_median"] is None and s["blind_pct_mean"] is None and s["gap_s_p50"] is None


def test_md_table_columns_and_one_row_per_day():
    rows = authed_link(T0) + [close(T0 + 100, code=1008), conn(T0 + 129.7), auth(T0 + 130)]
    days = [P.day_row(rows, MON), P.day_row([], date(2026, 11, 13))]
    md = P.render_md(days).splitlines()
    assert md[0] == "| day | kicks | blind s | blind % | p50 gap |"
    assert len(md) == 2 + len(days)
    assert md[2].startswith("| 2026-11-16 | 1 | 30.0 |") and md[2].endswith("| 30.0 s |")
    assert md[3] == "| 2026-11-13 | — | — | no rows | — |"


# ── source pins ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_never_retyped():
    assert "max_connections" not in SRC
    assert "1008" not in SRC
    for name in ("live_feed.KICK_STATUS", "live_feed.KICK_CLOSE_CODE", "live_feed.LIVE_FEED_EVENTS_COLL",
                 "live_feed.LIVE_FEED_EVENTS_TTL_DAYS", "live_feed._pctl", "MH_GATE.closed_reason"):
        assert name in SRC, name
    assert "live_feed_events" not in SRC.replace("LIVE_FEED_EVENTS", "")


def test_no_pymongo_at_module_top():
    tree = ast.parse(SRC)
    top = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            top.append(node.module or "")
    assert not any(m.split(".")[0] == "pymongo" for m in top)
    assert "from pymongo import MongoClient" in SRC


def test_never_writes():
    for bad in ("insert_", "update_", "delete_", "replace_", "create_index", "drop(", "bulk_write"):
        assert bad not in SRC, bad
    tree = ast.parse(SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open":
            pytest.fail("the probe opens a file")
