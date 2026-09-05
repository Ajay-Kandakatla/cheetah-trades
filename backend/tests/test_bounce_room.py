"""supply_demand/bounce_room — bouncing off a demand level + room to the next
supply band, one read for the SEPA filter, the Back-in-Demand sort and the
Catalysts sort (Ajay 2026-09-05).

Pure tests on synthetic docs/snapshots (NEGATIVES throughout), fake Mongo
collections, a fake snapshot function, an inline fake thread for the
on-demand worker, and the two routes through FastAPI's TestClient with the
read patched. No Mongo, no network, no zone engine.

Host-runnable (py3.9):
    cd backend && .venv/bin/python -m pytest tests/test_bounce_room.py -q
"""
import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import bounce_room as BR          # noqa: E402
from supply_demand import zone_bounce_alerts as ZB   # noqa: E402
from supply_demand import zone_store as ZS           # noqa: E402

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 4, 11, 0, tzinfo=ET)          # Friday, in RTH
SAT = datetime(2026, 9, 5, 20, 0, tzinfo=ET)          # Saturday evening
STORE_DAY = "2026-09-04"

DEM = {"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 2, "strength": 50.0}
DEM2 = {"kind": "demand", "lo": 86.0, "hi": 88.0, "touches": 1, "strength": 20.0}
SUP_BROKEN = {"kind": "supply", "lo": 95.0, "hi": 97.0, "touches": 1, "strength": 18.0}
SUP_OVER = {"kind": "supply", "lo": 110.0, "hi": 112.0, "touches": 3, "strength": 40.0}
SUP_FAR = {"kind": "supply", "lo": 130.0, "hi": 133.0, "touches": 1, "strength": 15.0}


def _doc(bands, *, prev_close=100.0, atr14=2.0, high_252=120.0, recent=None, day=STORE_DAY,
         symbol="XYZ", **extra):
    d = {"_id": f"{symbol}:{day}", "symbol": symbol, "date": day, "geom": "board",
         "bands": list(bands), "atr14": atr14, "prev_close": prev_close, "high_252": high_252,
         "recent": recent if recent is not None else [], "computed_at": f"{day}T09:20:00-04:00"}
    d.update(extra)
    return d


def _recent(lows, end="2026-09-03"):
    """Closed sessions ending on `end` (business days), oldest first."""
    import pandas as pd
    days = pd.bdate_range(end=pd.Timestamp(end), periods=len(lows))
    return [{"date": d.date().isoformat(), "low": float(l), "high": float(l) + 5.0,
             "close": float(l) + 3.0} for d, l in zip(days, lows)]


def _snap(low, last, *, day=STORE_DAY, now=NOW, age_sec=30, close=None, with_last=True,
          prev_close=100.0, high=None):
    """A bulk_snapshot row. `prev_close` = Massive's prevDay.c — 100.0 matches
    _doc's prev_close (the bar before the store day) by default."""
    import pandas as pd
    ts_ns = int((now - timedelta(seconds=age_sec)).timestamp() * 1e9)
    s = {"open": low + 1, "high": high if high is not None else last + 1, "low": low,
         "close": close if close is not None else last,
         "volume": 1e6, "date": pd.Timestamp(day), "change_pct": 0.0, "prev_day_close": prev_close}
    if with_last:
        s.update(last_trade_price=last, last_trade_ts_ms=ts_ns)
    return s


class FakeStoreColl:
    """zone_store's coll: find by date/symbol + distinct('date')."""

    def __init__(self, docs=()):
        self.docs = {d["_id"]: dict(d) for d in docs}
        self.calls = []

    def find(self, q, projection=None):
        self.calls.append(("find", q))
        for d in self.docs.values():
            if "date" in q and d.get("date") != q["date"]:
                continue
            if "symbol" in q and d.get("symbol") not in q["symbol"]["$in"]:
                continue
            yield dict(d)

    def distinct(self, field):
        self.calls.append(("distinct", field))
        return sorted({d.get(field) for d in self.docs.values() if d.get(field)})


class FakeCacheColl:
    """bounce_room_zones: find by _id $in + replace_one."""

    def __init__(self, docs=()):
        self.docs = {d["_id"]: dict(d) for d in docs}
        self.writes = []

    def find(self, q, projection=None):
        for k in q["_id"]["$in"]:
            if k in self.docs:
                yield dict(self.docs[k])

    def replace_one(self, q, doc, upsert=False):
        self.writes.append(q["_id"])
        self.docs[q["_id"]] = dict(doc)

    def delete_many(self, q):
        cutoff = q["date"]["$lt"]
        gone = [k for k, d in self.docs.items() if str(d.get("date") or "") < cutoff]
        for k in gone:
            self.docs.pop(k)

        class Res:
            deleted_count = len(gone)
        return Res()


@pytest.fixture(autouse=True)
def _reset_module_state():
    BR._mem.clear()
    BR._resp_cache.clear()
    BR._bg["running"] = False
    yield
    BR._mem.clear()
    BR._resp_cache.clear()
    BR._bg["running"] = False


def _inline_thread(monkeypatch):
    started = []

    class FakeThread:
        def __init__(self, target=None, args=(), **kw):
            self.target, self.args = target, args

        def start(self):
            started.append(True)
            self.target(*self.args)
    monkeypatch.setattr(BR.threading, "Thread", FakeThread)
    return started


# ── touch_hits ───────────────────────────────────────────────────────────────
def test_touch_today_when_the_snapshot_bar_is_the_store_day():
    hits = BR.touch_hits(_doc([DEM, SUP_OVER]), 91.0, STORE_DAY, STORE_DAY)
    assert len(hits) == 1
    band, low, day, ago = hits[0]
    assert band is not None and band["lo"] == 90.0 and low == 91.0 and day == STORE_DAY and ago == 0


def test_touch_in_a_recent_closed_session_carries_its_sessions_ago():
    doc = _doc([DEM], recent=_recent([99.0, 91.5, 99.5]))            # ago 3, 2, 1
    hits = BR.touch_hits(doc, 99.0, STORE_DAY, STORE_DAY)             # today did not touch
    assert [(h[1], h[3]) for h in hits] == [(91.5, 2)]
    assert hits[0][2] == "2026-09-02"


def test_no_touch_when_every_low_stays_above_the_tolerance():
    doc = _doc([DEM], recent=_recent([93.0, 93.5, 100.0]))            # 92*1.01 = 92.92
    assert BR.touch_hits(doc, 92.93, STORE_DAY, STORE_DAY) == []
    assert BR.touch_hits(None, 91.0, STORE_DAY, STORE_DAY) == []
    assert BR.touch_hits(_doc([]), 91.0, STORE_DAY, STORE_DAY) == []


def test_wick_undercut_inside_WICK_PCT_counts_deeper_does_not():
    floor = 90.0 * (1 - ZB.WICK_PCT / 100.0)                          # 88.65
    assert BR.touch_hits(_doc([DEM]), floor + 0.01, STORE_DAY, STORE_DAY)
    assert BR.touch_hits(_doc([DEM]), floor - 0.05, STORE_DAY, STORE_DAY) == []


def test_broken_supply_is_eligible_only_when_its_top_is_below_prev_close():
    assert BR.touch_hits(_doc([SUP_BROKEN], prev_close=100.0), 96.0, STORE_DAY, STORE_DAY)
    assert BR.touch_hits(_doc([SUP_BROKEN], prev_close=96.0), 96.0, STORE_DAY, STORE_DAY) == [], \
        "hi 97 >= prev close 96: still overhead, not support"
    assert BR.touch_hits(_doc([SUP_BROKEN], prev_close=None), 96.0, STORE_DAY, STORE_DAY) == []
    assert BR.touch_hits(_doc([DEM], prev_close=None), 91.0, STORE_DAY, STORE_DAY), \
        "demand bands need no prev close"


def test_a_snapshot_bar_older_than_the_store_day_is_not_today_and_is_not_double_counted():
    doc = _doc([DEM], recent=_recent([99.0, 91.0], end="2026-09-03"))
    hits = BR.touch_hits(doc, 91.0, "2026-09-03", STORE_DAY)          # pre-open: still yesterday's bar
    assert [(h[3], h[2]) for h in hits] == [(1, "2026-09-03")]
    hits_today = BR.touch_hits(doc, 91.0, STORE_DAY, STORE_DAY)
    assert [h[3] for h in hits_today] == [0, 1]


def test_saturday_snapshot_of_fridays_bar_is_dated_saturday_and_still_reads_as_session_zero():
    """The real weekend shape (sepa/prices.bulk_snapshot: no day.t -> the bar is
    dated TODAY): Friday's OHLC arrives dated Saturday; the Friday 9:20 doc's
    `recent` ends Thursday. The bar is the store-day session because its
    prevDay close is the doc's prev_close (Thursday's close)."""
    doc = _doc([DEM], recent=_recent([99.0, 99.5], end="2026-09-03"), prev_close=100.0)
    sat = _snap(91.0, 99.0, day="2026-09-05", now=SAT, age_sec=26 * 3600, prev_close=100.0)
    assert BR.is_store_session_bar(doc, 91.0, "2026-09-05", STORE_DAY, sat) is True
    hits = BR.touch_hits(doc, 91.0, "2026-09-05", STORE_DAY, snapshot=sat)
    assert [(h[3], h[2]) for h in hits] == [(0, STORE_DAY)], \
        "sessions_ago 0 and the touch is dated the STORE day, not the snapshot's Saturday"


def test_monday_snapshot_over_a_stale_friday_store_is_not_the_store_session(monkeypatch):
    """Warm failed Monday: latest store day is Friday and Monday's bar arrives
    (prevDay = Friday's close 103 != doc.prev_close 100). Monday's low must
    NOT be filed as a Friday touch — an honest miss, never a false read."""
    doc = _doc([DEM], recent=_recent([99.0, 99.5], end="2026-09-03"), prev_close=100.0)
    mon = _snap(91.0, 99.0, day="2026-09-07", prev_close=103.0)
    assert BR.is_store_session_bar(doc, 91.0, "2026-09-07", STORE_DAY, mon) is False
    assert BR.touch_hits(doc, 91.0, "2026-09-07", STORE_DAY, snapshot=mon) == []
    # No snapshot row at all (only a low): a later date alone proves nothing.
    assert BR.touch_hits(doc, 91.0, "2026-09-07", STORE_DAY) == []


def test_holiday_warm_keeps_friday_in_recent_and_the_same_bar_in_the_snapshot_counts_once():
    """Labor Day: the 1-5 cron builds a doc dated 09-07 with Friday as
    recent[-1]; Massive still shows Friday's OHLC, dated 09-07 (== store day).
    Identical low / high / close -> it IS recent[-1]: exactly one hit, ago 1."""
    fri = _recent([99.0, 91.0], end="2026-09-04")                        # recent[-1] = Friday
    doc = _doc([DEM], recent=fri, day="2026-09-07", prev_close=100.0)
    same = _snap(91.0, 94.0, day="2026-09-07", high=96.0, close=94.0, prev_close=100.0)
    assert BR.is_store_session_bar(doc, 91.0, "2026-09-07", "2026-09-07", same) is False
    hits = BR.touch_hits(doc, 91.0, "2026-09-07", "2026-09-07", snapshot=same)
    assert [(h[3], h[2]) for h in hits] == [(1, "2026-09-04")]
    # NEGATIVE: a genuinely new bar on the store day (same low, different close)
    # is today's session and counts as 0 alongside Friday's 1.
    fresh = _snap(91.0, 95.5, day="2026-09-07", high=96.0, close=95.5, prev_close=100.0)
    assert [h[3] for h in BR.touch_hits(doc, 91.0, "2026-09-07", "2026-09-07", snapshot=fresh)] == [0, 1]
    assert BR.is_store_session_bar(doc, None, "2026-09-07", "2026-09-07", fresh) is False
    assert BR.is_store_session_bar(doc, 0.0, "2026-09-07", "2026-09-07", fresh) is False


def test_lookback_caps_how_far_back_a_recent_touch_counts():
    doc = _doc([DEM], recent=_recent([91.0, 99, 99, 99, 99, 99]))    # ago 6..1
    assert BR.touch_hits(doc, 99.0, STORE_DAY, STORE_DAY) == []
    assert BR.touch_hits(doc, 99.0, STORE_DAY, STORE_DAY, lookback=6)[0][3] == 6


def test_touch_hits_are_freshest_first():
    doc = _doc([DEM, SUP_BROKEN], recent=_recent([91.0, 99.0]))       # DEM touched ago 2
    hits = BR.touch_hits(doc, 96.0, STORE_DAY, STORE_DAY)             # SUP_BROKEN today
    assert [(h[0]["kind"], h[3]) for h in hits] == [("supply", 0), ("demand", 2)]


# ── bounce_read ──────────────────────────────────────────────────────────────
def _touches(*items):
    return [(band, low, day, ago) for band, low, day, ago in items]


def test_residence_bounce_counts_there_is_no_arrival_gate():
    """prev close 92.5 sits inside the alert's 3% ring above the band: the
    PHONE kind refuses it as residence; the FILTER must show it."""
    doc = _doc([DEM], prev_close=92.5, atr14=2.0)
    hits = BR.touch_hits(doc, 91.0, STORE_DAY, STORE_DAY)
    out = BR.bounce_read(96.0, doc, hits)
    assert out and out["bounce_pct"] == 5.49 and out["role"] == "demand"
    assert ZB.read(91.0, 96.0, 92.5, DEM, 2.0) is None, "the alert gate still says residence"


def test_print_at_or_under_the_band_top_is_not_a_bounce():
    doc = _doc([DEM])
    hits = _touches((DEM, 91.0, STORE_DAY, 0))
    assert BR.bounce_read(92.0, doc, hits) is None
    assert BR.bounce_read(91.9, doc, hits) is None
    assert BR.bounce_read(None, doc, hits) is None
    assert BR.bounce_read(96.0, doc, []) is None


def test_bounce_below_the_floor_is_not_a_bounce_and_the_floor_scales_with_atr():
    hits = _touches((DEM, 91.0, STORE_DAY, 0))
    assert BR.bounce_read(93.5, _doc([DEM], atr14=2.0), hits) is None      # +2.75% < 3%
    ok = BR.bounce_read(93.8, _doc([DEM], atr14=2.0), hits)
    assert ok and ok["bounce_pct"] == 3.08 and ok["floor_pct"] == 3.0
    assert BR.bounce_read(98.0, _doc([DEM], atr14=8.0), hits) is None      # +7.69% < 8.79% ATR floor
    big = BR.bounce_read(100.0, _doc([DEM], atr14=8.0), hits)
    assert big and big["floor_pct"] == 8.79 and big["bounce_pct"] == 9.89
    assert big["strong"] is False and big["atr_x"] == 1.1


def test_strong_flag_is_max_of_STRONG_PCT_and_twice_atr_pct():
    hits = _touches((DEM, 91.0, STORE_DAY, 0))
    weak = BR.bounce_read(95.0, _doc([DEM], atr14=2.0), hits)
    assert weak and weak["bounce_pct"] == 4.4 and weak["strong"] is False
    strong = BR.bounce_read(96.0, _doc([DEM], atr14=2.0), hits)
    assert strong["strong"] is True and strong["atr_x"] == 2.5
    assert BR.bounce_read(96.0, _doc([DEM], atr14=None), hits)["atr_x"] is None


def test_freshest_touch_wins_then_the_bigger_bounce():
    doc = _doc([DEM, SUP_BROKEN], recent=_recent([91.0, 99.0]))
    hits = BR.touch_hits(doc, 96.5, STORE_DAY, STORE_DAY)             # SUP today, DEM two ago
    out = BR.bounce_read(105.0, doc, hits)
    assert out["role"] == "broken_supply" and out["sessions_ago"] == 0 and out["touch_low"] == 96.5
    assert out["bounce_pct"] == 8.81 < 15.38, "the fresher, smaller bounce wins over the older, bigger one"
    same_day = _touches((DEM, 91.0, STORE_DAY, 1), (DEM2, 89.0, STORE_DAY, 1))
    out2 = BR.bounce_read(100.0, _doc([DEM, DEM2]), same_day)
    assert out2["band"]["lo"] == 86.0 and out2["bounce_pct"] == 12.36


def test_bounce_payload_shape():
    doc = _doc([DEM], recent=_recent([91.5]))
    out = BR.bounce_read(99.0, doc, BR.touch_hits(doc, 99.0, STORE_DAY, STORE_DAY))
    assert set(out) == {"band", "role", "touch_low", "touch_date", "sessions_ago", "bounce_pct",
                        "floor_pct", "strong", "atr_x"}
    assert set(out["band"]) == {"kind", "lo", "hi", "touches", "strength"}
    assert out["touch_date"] == "2026-09-03" and out["sessions_ago"] == 1


# ── room_read ────────────────────────────────────────────────────────────────
def test_room_CLEAR_when_nothing_is_overhead():
    out = BR.room_read(99.0, _doc([DEM, SUP_BROKEN]))
    assert out == {"state": "CLEAR", "room_pct": None, "atr_days": None, "band": None,
                   "at_highs": False}


def test_room_IN_BAND_NEAR_and_ROOM():
    doc = _doc([DEM, SUP_OVER, SUP_FAR], atr14=2.0)
    inb = BR.room_read(111.0, doc)
    assert inb["state"] == "IN_BAND" and inb["room_pct"] == 0.0 and inb["atr_days"] == 0.0
    assert inb["band"] == {"kind": "supply", "lo": 110.0, "hi": 112.0, "touches": 3}
    near = BR.room_read(108.5, doc)
    assert near["state"] == "NEAR" and near["room_pct"] == 1.38 and near["atr_days"] == 0.8
    room = BR.room_read(99.0, doc)
    assert room["state"] == "ROOM" and room["room_pct"] == 11.11 and room["atr_days"] == 5.5
    assert room["band"]["lo"] == 110.0, "the FIRST band overhead, not the strongest"
    above = BR.room_read(115.0, doc)
    assert above["state"] == "ROOM" and above["band"]["lo"] == 130.0
    assert BR.room_read(99.0, _doc([SUP_OVER], atr14=None))["atr_days"] is None
    assert BR.room_read(0, doc) is None and BR.room_read(None, doc) is None


def test_a_demand_band_above_the_print_is_broken_support_and_counts_as_resistance():
    high_dem = {"kind": "demand", "lo": 105.0, "hi": 107.0, "touches": 2, "strength": 30.0}
    out = BR.room_read(99.0, _doc([high_dem, DEM]))
    assert out["state"] == "ROOM" and out["room_pct"] == 6.06
    assert out["band"] == {"kind": "broken_support", "lo": 105.0, "hi": 107.0, "touches": 2}
    inside = BR.room_read(106.0, _doc([high_dem]))
    assert inside["state"] == "CLEAR", "a demand band that CONTAINS price is support, never overhead"


def test_at_highs_uses_zone_edge_NEW_HIGH_TOL_against_high_252():
    assert BR.room_read(99.0, _doc([], high_252=100.0))["at_highs"] is True      # 99 >= 98
    assert BR.room_read(97.9, _doc([], high_252=100.0))["at_highs"] is False
    assert BR.room_read(99.0, _doc([], high_252=None))["at_highs"] is False
    assert BR.room_read(99.0, _doc([SUP_OVER], high_252=100.0))["at_highs"] is True, \
        "at_highs is independent of the room state"


def test_overhead_rule_matches_portfolio_supply_watch_loaded_standalone():
    """Same rule, two homes (the portfolio package cannot be imported on the
    py3.9 host). Load supply_watch.py by path and compare on every print."""
    spec = importlib.util.spec_from_file_location(
        "sw_standalone", ROOT / "backend/portfolio/supply_watch.py")
    sw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sw)
    bands = [DEM, DEM2, SUP_BROKEN, SUP_OVER, SUP_FAR,
             {"kind": "demand", "lo": 105.0, "hi": 107.0, "touches": 2, "strength": 30.0}]
    supply = [b for b in bands if b["kind"] == "supply"]
    demand = [b for b in bands if b["kind"] == "demand"]
    for live in (80.0, 87.0, 91.0, 96.0, 99.0, 106.0, 111.0, 120.0, 140.0):
        theirs = {(z["kind"], z["lo"], z["hi"]) for z in sw.overhead_bands(supply, demand, live)}
        ours = {(z["kind"], z["lo"], z["hi"]) for z in BR.overhead_bands(bands, live)}
        assert ours == theirs, live
        first_theirs = sw.nearest_supply(sw.overhead_bands(supply, demand, live), live)
        first_ours = BR.first_overhead(BR.overhead_bands(bands, live), live)
        assert (first_ours or {}).get("lo") == (first_theirs or {}).get("lo"), live
    assert BR.NEAR_PCT == sw.NEAR_PCT


# ── ordering ─────────────────────────────────────────────────────────────────
def _row(sym, room=None, bounce=None, coverage="store"):
    r = {"symbol": sym, "coverage": coverage}
    if coverage in ("store", "ondemand"):
        r["room"] = room
        r["bounce"] = bounce
    return r


def _room(state, pct):
    return {"state": state, "room_pct": pct, "atr_days": None, "band": None, "at_highs": False}


def test_room_rank_puts_CLEAR_first_then_room_desc_then_unknown_last():
    rows = [_row("INB", _room("IN_BAND", 0.0)), _row("NEAR", _room("NEAR", 1.2)),
            _row("PEND", coverage="pending"), _row("R5", _room("ROOM", 5.0)),
            _row("CLR", _room("CLEAR", None)), _row("R20", _room("ROOM", 20.0)),
            _row("NONE", None), _row("UNAV", coverage="unavailable")]
    order = [r["symbol"] for r in sorted(rows, key=BR.room_rank)]
    assert order[0] == "CLR"
    assert order[1:5] == ["R20", "R5", "NEAR", "INB"]
    assert set(order[5:]) == {"PEND", "NONE", "UNAV"}
    assert BR.room_rank(_row("X", _room("CLEAR", None)))[0] == 0
    assert BR.room_rank(_row("X", _room("ROOM", None)))[0] == 2, "a ROOM without a % is unknown"
    assert BR.room_rank({})[0] == 2 and BR.room_rank(None)[0] == 2


def test_bounce_room_key_bouncing_first_then_room_then_bounce_then_symbol():
    b = lambda pct: {"bounce_pct": pct}                                     # noqa: E731
    rows = [_row("PEND", coverage="pending"),
            _row("NB_R30", _room("ROOM", 30.0)),
            _row("B_R5_A", _room("ROOM", 5.0), b(4.0)),
            _row("B_CLR", _room("CLEAR", None), b(3.5)),
            _row("NB_CLR", _room("CLEAR", None)),
            _row("B_R15", _room("ROOM", 15.0), b(6.0)),
            _row("B_R5_B", _room("ROOM", 5.0), b(9.0)),
            _row("B_R5_C", _room("ROOM", 5.0), b(9.0)),
            _row("UNAV", coverage="unavailable"),
            _row("B_INB", _room("IN_BAND", 0.0), b(12.0))]
    order = [r["symbol"] for r in sorted(rows, key=BR.bounce_room_key)]
    assert order[:6] == ["B_CLR", "B_R15", "B_R5_B", "B_R5_C", "B_R5_A", "B_INB"], \
        "bouncing: CLEAR, then room desc, then bounce desc, then symbol"
    assert order[6:8] == ["NB_CLR", "NB_R30"]
    assert set(order[8:]) == {"PEND", "UNAV"}
    k = BR.bounce_room_key(rows[2])
    assert k == (0, 1, -5.0, -4.0, "B_R5_A") and len(k) == 5
    assert BR.bounce_room_key(_row("PEND", coverage="pending")) == (1, 2, 0.0, 0.0, "PEND")


# ── print_of ─────────────────────────────────────────────────────────────────
def test_print_of_fresh_stale_and_close_fallback():
    now_ts = NOW.timestamp()
    assert BR.print_of(_snap(91.0, 99.5, age_sec=30), now_ts) == (99.5, True)
    assert BR.print_of(_snap(91.0, 99.5, age_sec=BR.STALE_PRINT_SEC + 1), now_ts) == (99.5, False), \
        "a stale print is shown with fresh=false, never dropped"
    ms = _snap(91.0, 99.5, age_sec=30)
    ms["last_trade_ts_ms"] = int(ms["last_trade_ts_ms"] / 1e6)                 # ms stamp
    assert BR.print_of(ms, now_ts) == (99.5, True)
    assert BR.print_of(_snap(91.0, 99.5, with_last=False, close=98.75), now_ts) == (98.75, False)
    no_stamp = _snap(91.0, 99.5, with_last=False, close=98.0)
    no_stamp["last_trade_price"] = 99.1                                          # price, no stamp
    assert BR.print_of(no_stamp, now_ts) == (99.1, False)
    assert BR.print_of({"low": 1.0}, now_ts) == (None, False)
    assert BR.print_of(None, now_ts) == (None, False)
    assert BR.print_of({"close": 0.0, "last_trade_price": float("nan")}, now_ts) == (None, False)


# ── read_symbol ──────────────────────────────────────────────────────────────
def test_read_symbol_rows_for_pending_tombstone_no_print_and_ondemand_coverage():
    assert BR.read_symbol("abc", None, None, NOW) == {"symbol": "ABC", "coverage": "pending"}
    tomb = {"_id": "ABC:2026-09-04", "symbol": "ABC", "date": STORE_DAY, "error": BR.NO_DATA_ERROR}
    assert BR.read_symbol("ABC", tomb, _snap(91.0, 99.0), NOW) == {
        "symbol": "ABC", "coverage": "unavailable", "error": "no / insufficient price data"}
    nop = BR.read_symbol("XYZ", _doc([DEM]), None, NOW)
    assert nop["coverage"] == "unavailable" and "print" in nop["error"]
    od = BR.read_symbol("XYZ", _doc([DEM], origin="ondemand"), _snap(91.0, 99.0), NOW)
    assert od["coverage"] == "ondemand" and od["fresh"] is True and od["print"] == 99.0
    assert set(od) == {"symbol", "print", "fresh", "coverage", "bounce", "room"}
    st = BR.read_symbol("XYZ", _doc([DEM]), _snap(91.0, 99.0), NOW)
    assert st["coverage"] == "store" and st["bounce"]["sessions_ago"] == 0
    assert st["room"]["state"] == "CLEAR"


# ── load_docs / on-demand ────────────────────────────────────────────────────
def test_load_docs_splits_store_cache_tombstone_memory_and_missing():
    store = FakeStoreColl([_doc([DEM], symbol="A"), _doc([DEM], symbol="OLD", day="2026-09-03")])
    cache = FakeCacheColl([dict(_doc([DEM], symbol="B"), origin="ondemand"),
                           {"_id": f"C:{STORE_DAY}", "symbol": "C", "date": STORE_DAY,
                            "origin": "ondemand", "error": "engine missed"}])
    BR._mem[f"E:{STORE_DAY}"] = dict(_doc([DEM], symbol="E"), origin="ondemand")
    BR._mem["F:2026-09-03"] = dict(_doc([DEM], symbol="F"), origin="ondemand")      # other day
    docs, missing = BR.load_docs(["A", "B", "C", "D", "E", "F", "OLD"], STORE_DAY,
                                 store_coll=store, ondemand_coll=cache)
    assert set(docs) == {"A", "B", "C", "E"} and missing == ["D", "F", "OLD"]
    assert BR._coverage_of(docs["A"]) == "store" and BR._coverage_of(docs["B"]) == "ondemand"
    assert docs["C"]["error"] == "engine missed"
    assert "F:2026-09-03" not in BR._mem, "memory entries for other days are dropped"
    assert BR.load_docs([], STORE_DAY, store_coll=store, ondemand_coll=cache) == ({}, [])


def test_compute_batch_builds_tags_tombstones_and_respects_the_budget():
    cache = FakeCacheColl()

    def builder(sym, day):
        assert day.isoformat() == STORE_DAY
        if sym == "X":
            return _doc([DEM], symbol="X")
        if sym == "Y":
            return None
        raise RuntimeError("provider down")

    out = BR.compute_batch(["X", "Y", "Z"], STORE_DAY, cache, builder=builder, now_ts=NOW.timestamp())
    assert out["asked"] == 3 and out["built"] == 1 and out["tombstoned"] == 1 and out["errored"] == 1
    assert out["timed_out"] is False
    assert cache.docs[f"X:{STORE_DAY}"]["origin"] == "ondemand" and cache.docs[f"X:{STORE_DAY}"]["bands"]
    assert cache.docs[f"Y:{STORE_DAY}"]["error"] == BR.NO_DATA_ERROR
    # A RAISE is not a day-long tombstone and its text never leaves the process.
    assert f"Z:{STORE_DAY}" not in cache.docs and f"Z:{STORE_DAY}" not in cache.writes
    marker = BR._mem[f"Z:{STORE_DAY}"]
    assert marker["error"] == BR.ENGINE_ERROR == "engine error" and "provider down" not in json.dumps(marker)
    assert marker["retry_after"] == NOW.timestamp() + BR.ENGINE_RETRY_SEC
    assert set(BR._mem) == {f"X:{STORE_DAY}", f"Y:{STORE_DAY}", f"Z:{STORE_DAY}"}
    # Until the retry is due the row is 'unavailable: engine error'; after it the name is missing again.
    docs, missing = BR.load_docs(["Z"], STORE_DAY, store_coll=FakeStoreColl(), ondemand_coll=cache,
                                 now_ts=NOW.timestamp() + BR.ENGINE_RETRY_SEC - 1)
    assert BR.read_symbol("Z", docs["Z"], None, NOW) == {"symbol": "Z", "coverage": "unavailable",
                                                          "error": "engine error"}
    docs, missing = BR.load_docs(["Z"], STORE_DAY, store_coll=FakeStoreColl(), ondemand_coll=cache,
                                 now_ts=NOW.timestamp() + BR.ENGINE_RETRY_SEC)
    assert docs == {} and missing == ["Z"] and f"Z:{STORE_DAY}" not in BR._mem
    late = BR.compute_batch(["X"], STORE_DAY, None, builder=builder, budget_sec=-1)
    assert late["timed_out"] is True and late["built"] == 0


def test_compute_batch_purges_on_demand_docs_older_than_KEEP_DAYS():
    old_day = (datetime.fromisoformat(STORE_DAY) - timedelta(days=ZS.KEEP_DAYS + 1)).date().isoformat()
    edge_day = (datetime.fromisoformat(STORE_DAY) - timedelta(days=ZS.KEEP_DAYS)).date().isoformat()
    cache = FakeCacheColl([dict(_doc([DEM], symbol="OLD", day=old_day), origin="ondemand"),
                           dict(_doc([DEM], symbol="EDGE", day=edge_day), origin="ondemand"),
                           {"_id": f"T:{old_day}", "symbol": "T", "date": old_day, "origin": "ondemand",
                            "error": BR.NO_DATA_ERROR}])
    out = BR.compute_batch(["X"], STORE_DAY, cache, builder=lambda s, d: _doc([DEM], symbol=s))
    assert out["purged"] == 2
    assert set(cache.docs) == {f"EDGE:{edge_day}", f"X:{STORE_DAY}"}, "the cutoff is exclusive, like zone_store.purge"
    assert BR.purge_ondemand(None, datetime.fromisoformat(STORE_DAY).date()) == 0

    class Boom:
        def delete_many(self, q):
            raise RuntimeError("mongo away")
    assert BR.purge_ondemand(Boom(), datetime.fromisoformat(STORE_DAY).date()) == 0


def test_queue_ondemand_runs_one_daemon_worker_and_drops_while_running(monkeypatch):
    started = _inline_thread(monkeypatch)
    cache = FakeCacheColl()
    built = []

    def builder(sym, day):
        built.append(sym)
        return _doc([DEM], symbol=sym)

    n = BR.queue_ondemand(["A", "B"], STORE_DAY, cache, builder=builder)
    assert n == 2 and built == ["A", "B"] and len(started) == 1 and BR._bg["running"] is False
    assert BR.queue_ondemand([], STORE_DAY, cache, builder=builder) == 0
    BR._bg["running"] = True
    assert BR.queue_ondemand(["C"], STORE_DAY, cache, builder=builder) == 0 and built == ["A", "B"]
    BR._bg["running"] = False
    many = [f"S{i}" for i in range(BR.ONDEMAND_MAX_QUEUE + 5)]
    assert BR.queue_ondemand(many, STORE_DAY, cache, builder=builder) == BR.ONDEMAND_MAX_QUEUE


def test_queue_ondemand_releases_the_flag_when_the_thread_cannot_start(monkeypatch):
    class DeadThread:
        def __init__(self, target=None, args=(), **kw):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")
    monkeypatch.setattr(BR.threading, "Thread", DeadThread)
    assert BR.queue_ondemand(["A"], STORE_DAY, FakeCacheColl(), builder=lambda s, d: None) == 0
    assert BR._bg["running"] is False, "a failed start must not wedge every later request into pending"


# ── api_payload ──────────────────────────────────────────────────────────────
def _stores():
    store = FakeStoreColl([
        _doc([DEM, SUP_OVER], symbol="A", recent=_recent([99.0, 91.0])),         # bouncing, ROOM
        _doc([DEM, SUP_OVER], symbol="B"),                                          # not bouncing
        _doc([DEM], symbol="A", day="2026-09-03"), _doc([DEM], symbol="B", day="2026-09-03")])
    cache = FakeCacheColl([{"_id": f"C:{STORE_DAY}", "symbol": "C", "date": STORE_DAY,
                            "origin": "ondemand", "error": BR.NO_DATA_ERROR}])
    return store, cache


def test_api_payload_returns_the_exact_contract_with_counts_and_prices_only_covered_names(monkeypatch):
    _inline_thread(monkeypatch)
    store, cache = _stores()
    asked = []

    def snapshot_fn(names):
        asked.append(list(names))
        return {"A": _snap(98.0, 99.0), "B": _snap(98.0, 101.0)}

    built = []
    out = BR.api_payload(["a", "B", "c", "d", "A"], now=NOW, store_coll=store, ondemand_coll=cache,
                         snapshot_fn=snapshot_fn,
                         builder=lambda s, d: built.append(s) or _doc([DEM], symbol=s))
    assert set(out) == {"as_of", "in_session", "store_date", "params", "rows", "requested",
                        "covered", "pending", "unavailable", "disclaimer"}
    assert out["requested"] == 4 and out["covered"] == 2 and out["pending"] == 1 and out["unavailable"] == 1
    assert out["store_date"] == STORE_DAY and out["in_session"] is True
    assert out["as_of"].startswith("2026-09-04T11:00:00") and out["as_of"].endswith("-04:00")
    assert out["params"] == BR.PARAMS == {
        "touch_tol_pct": 1.0, "wick_pct": 1.5, "bounce_min_pct": 3.0, "strong_pct": 5.0,
        "lookback_sessions": 5, "near_pct": 2.0, "stale_print_sec": 180, "new_high_tol": 0.98}
    assert "not advice" in out["disclaimer"]
    assert asked == [["A", "B"]], "only covered names are priced; pending/unavailable never hit the provider"
    rows = out["rows"]
    assert list(rows) == ["A", "B", "C", "D"]
    assert rows["A"]["coverage"] == "store" and rows["A"]["bounce"]["sessions_ago"] == 1
    assert rows["A"]["room"] == {"state": "ROOM", "room_pct": 11.11, "atr_days": 5.5,
                                 "band": {"kind": "supply", "lo": 110.0, "hi": 112.0, "touches": 3},
                                 "at_highs": False}
    assert rows["B"]["bounce"] is None and rows["B"]["room"]["state"] == "ROOM"
    assert rows["C"] == {"symbol": "C", "coverage": "unavailable", "error": BR.NO_DATA_ERROR}
    assert rows["D"] == {"symbol": "D", "coverage": "pending"}
    assert built == ["D"], "the miss went to the worker, the response did not wait for it"
    assert json.dumps(out)
    order = [r["symbol"] for r in sorted(rows.values(), key=BR.bounce_room_key)]
    assert order == ["A", "B", "C", "D"]


def test_response_cache_hits_within_ttl_regardless_of_order_and_case_then_expires(monkeypatch):
    _inline_thread(monkeypatch)
    store, cache = _stores()
    calls = []

    def snapshot_fn(names):
        calls.append(1)
        return {"A": _snap(98.0, 99.0), "B": _snap(98.0, 101.0)}

    first = BR.api_payload(["A", "B"], now=NOW, store_coll=store, ondemand_coll=cache,
                           snapshot_fn=snapshot_fn)
    again = BR.api_payload(["b", "a", "A"], now=NOW + timedelta(seconds=BR.RESPONSE_TTL_SEC),
                           store_coll=store, ondemand_coll=cache, snapshot_fn=snapshot_fn)
    assert again is first and calls == [1]
    other = BR.api_payload(["A"], now=NOW, store_coll=store, ondemand_coll=cache,
                           snapshot_fn=snapshot_fn)
    assert other is not first and calls == [1, 1], "a different symbol set is a different entry"
    later = BR.api_payload(["A", "B"], now=NOW + timedelta(seconds=BR.RESPONSE_TTL_SEC + 1),
                           store_coll=store, ondemand_coll=cache, snapshot_fn=snapshot_fn)
    assert later is not first and calls == [1, 1, 1]


def test_pending_names_become_covered_on_the_next_poll_after_the_worker_ran(monkeypatch):
    _inline_thread(monkeypatch)
    store, cache = _stores()
    snaps = {"A": _snap(98.0, 99.0), "B": _snap(98.0, 101.0), "D": _snap(91.0, 99.0)}
    first = BR.api_payload(["A", "D"], now=NOW, store_coll=store, ondemand_coll=cache,
                           snapshot_fn=lambda names: {k: snaps[k] for k in names},
                           builder=lambda s, d: _doc([DEM], symbol=s))
    assert first["rows"]["D"]["coverage"] == "pending" and first["pending"] == 1
    assert f"D:{STORE_DAY}" in cache.docs and cache.docs[f"D:{STORE_DAY}"]["origin"] == "ondemand"
    second = BR.api_payload(["A", "D"], now=NOW + timedelta(seconds=BR.RESPONSE_TTL_SEC + 1),
                            store_coll=store, ondemand_coll=cache,
                            snapshot_fn=lambda names: {k: snaps[k] for k in names})
    assert second["rows"]["D"]["coverage"] == "ondemand" and second["pending"] == 0
    assert second["rows"]["D"]["bounce"]["sessions_ago"] == 0 and second["covered"] == 2


def test_weekend_answers_with_the_latest_store_day_and_fridays_bar_is_session_zero(monkeypatch):
    _inline_thread(monkeypatch)
    store, cache = _stores()
    # bulk_snapshot dates the weekend bar TODAY (no day.t): Friday's OHLC dated
    # Saturday, prevDay = Thursday's close = the doc's prev_close.
    out = BR.api_payload(["A"], now=SAT, store_coll=store, ondemand_coll=cache,
                         snapshot_fn=lambda names: {"A": _snap(91.0, 99.0, day="2026-09-05", now=SAT,
                                                               age_sec=26 * 3600, prev_close=100.0)})
    assert out["store_date"] == STORE_DAY and out["in_session"] is False
    row = out["rows"]["A"]
    assert row["fresh"] is False and row["print"] == 99.0
    assert row["bounce"]["sessions_ago"] == 0 and row["bounce"]["touch_date"] == STORE_DAY, \
        "Saturday's snapshot IS Friday's bar; the store day is Friday; no double count with recent"
    # NEGATIVE: a zero day bar (Massive's other weekend shape) has no low -> no session-0 touch,
    # the print still comes from the last trade and the row stays covered.
    BR._resp_cache.clear()
    zero = dict(_snap(0.0, 99.0, day="2026-09-05", now=SAT, age_sec=26 * 3600), high=0.0, close=0.0)
    out2 = BR.api_payload(["A"], now=SAT, store_coll=store, ondemand_coll=cache,
                          snapshot_fn=lambda names: {"A": zero})
    assert out2["rows"]["A"]["coverage"] == "store" and out2["rows"]["A"]["print"] == 99.0
    assert out2["rows"]["A"]["bounce"]["sessions_ago"] == 1, "only the recent (Thursday) touch is visible"


def test_store_cold_falls_back_to_today_and_everything_is_pending(monkeypatch):
    started = _inline_thread(monkeypatch)
    calls = []
    out = BR.api_payload(["A", "B"], now=NOW, store_coll=FakeStoreColl(), ondemand_coll=FakeCacheColl(),
                         snapshot_fn=lambda names: calls.append(names) or {},
                         builder=lambda s, d: None)
    assert out["store_date"] == "2026-09-04" and out["as_of"] is None
    assert out["pending"] == 2 and out["covered"] == 0 and calls == [], "nothing covered -> no snapshot read"
    assert len(started) == 1
    assert {r["coverage"] for r in out["rows"].values()} == {"pending"}
    # Saturday with a cold store: the fallback day is FRIDAY, never a weekend
    # date (a Saturday doc would keep Friday in `recent` and see it again in
    # the snapshot). The builder is asked for Friday's doc.
    days = []
    sat = BR.api_payload(["Q"], now=SAT, store_coll=FakeStoreColl(), ondemand_coll=FakeCacheColl(),
                         snapshot_fn=lambda names: {},
                         builder=lambda s, d: days.append(d.isoformat()) or None)
    assert sat["store_date"] == "2026-09-04" and days == ["2026-09-04"]
    assert BR.last_weekday(datetime(2026, 9, 6).date()).isoformat() == "2026-09-04"
    assert BR.last_weekday(datetime(2026, 9, 7).date()).isoformat() == "2026-09-07"


def test_a_build_that_raised_reads_engine_error_then_is_retried_after_ENGINE_RETRY_SEC(monkeypatch):
    _inline_thread(monkeypatch)
    store, cache = _stores()
    calls = []

    def builder(sym, day):
        calls.append(sym)
        raise RuntimeError("mongo blip: Traceback (most recent call last)")

    first = BR.api_payload(["A", "D"], now=NOW, store_coll=store, ondemand_coll=cache,
                           snapshot_fn=lambda names: {"A": _snap(98.0, 99.0)}, builder=builder)
    assert first["rows"]["D"]["coverage"] == "pending" and calls == ["D"]
    t1 = NOW + timedelta(seconds=BR.RESPONSE_TTL_SEC + 1)
    second = BR.api_payload(["A", "D"], now=t1, store_coll=store, ondemand_coll=cache,
                            snapshot_fn=lambda names: {"A": _snap(98.0, 99.0)}, builder=builder)
    assert second["rows"]["D"] == {"symbol": "D", "coverage": "unavailable", "error": "engine error"}
    assert "Traceback" not in json.dumps(second) and f"D:{STORE_DAY}" not in cache.docs
    assert calls == ["D"], "no retry storm while the marker stands"
    t2 = NOW + timedelta(seconds=BR.ENGINE_RETRY_SEC + 1)
    third = BR.api_payload(["A", "D"], now=t2, store_coll=store, ondemand_coll=cache,
                           snapshot_fn=lambda names: {"A": _snap(98.0, 99.0)}, builder=builder)
    assert third["rows"]["D"]["coverage"] == "pending" and calls == ["D", "D"], "retried once the marker expired"


def test_snapshot_failure_degrades_to_unavailable_rows_not_an_exception(monkeypatch):
    _inline_thread(monkeypatch)
    store, cache = _stores()

    def boom(names):
        raise ConnectionError("massive down")
    out = BR.api_payload(["A"], now=NOW, store_coll=store, ondemand_coll=cache, snapshot_fn=boom)
    assert out["rows"]["A"]["coverage"] == "unavailable" and out["unavailable"] == 1
    assert out["as_of"] is not None


def test_payload_is_json_safe_with_numpy_values_in_the_doc(monkeypatch):
    _inline_thread(monkeypatch)
    store = FakeStoreColl([_doc([dict(DEM, lo=np.float64(90.0), hi=np.float64(92.0))], symbol="A",
                                atr14=np.float64(2.0), high_252=np.float64(120.0),
                                recent=[{"date": "2026-09-03", "low": np.float64(91.0),
                                         "high": np.float64(96.0), "close": np.float64(95.0)}])])
    out = BR.api_payload(["A"], now=NOW, store_coll=store, ondemand_coll=FakeCacheColl(),
                         snapshot_fn=lambda names: {"A": _snap(99.0, np.float64(99.0))})
    text = json.dumps(out)
    assert "NaN" not in text and out["rows"]["A"]["bounce"]["touch_low"] == 91.0


def test_normalize_symbols_upper_dedupe_cap():
    assert BR.normalize_symbols([" eose", "clym", "EOSE", "", None, "Clym "]) == ["EOSE", "CLYM"]
    assert len(BR.normalize_symbols([f"S{i}" for i in range(3000)])) == BR.MAX_SYMBOLS == 2500
    assert BR.normalize_symbols(None) == []


def test_in_session_is_rth_weekdays_only():
    assert BR.in_session(NOW) is True
    assert BR.in_session(datetime(2026, 9, 4, 9, 29, tzinfo=ET)) is False
    assert BR.in_session(datetime(2026, 9, 4, 16, 1, tzinfo=ET)) is False
    assert BR.in_session(SAT) is False


# ── the routes ───────────────────────────────────────────────────────────────
def _client(monkeypatch, seen):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from supply_demand.api import router

    def fake(symbols):
        seen.append(list(symbols))
        return {"rows": {s: {"symbol": s, "coverage": "pending"} for s in symbols},
                "requested": len(symbols)}
    monkeypatch.setattr(BR, "api_payload", fake)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_post_route_upper_cases_dedupes_and_422s_on_empty(monkeypatch):
    seen = []
    c = _client(monkeypatch, seen)
    r = c.post("/supply-demand/bounce-room", json={"symbols": ["eose", "clym", "EOSE", " "]})
    assert r.status_code == 200 and seen == [["EOSE", "CLYM"]]
    assert set(r.json()["rows"]) == {"EOSE", "CLYM"} and r.json()["requested"] == 2
    assert c.post("/supply-demand/bounce-room", json={"symbols": []}).status_code == 422
    assert c.post("/supply-demand/bounce-room", json={"symbols": ["", "  "]}).status_code == 422
    assert c.post("/supply-demand/bounce-room", json={}).status_code == 422
    assert c.post("/supply-demand/bounce-room", json={"symbols": "EOSE"}).status_code == 422
    assert len(seen) == 1, "no read happens on a rejected body"


def test_get_route_takes_a_comma_list_through_the_same_function(monkeypatch):
    seen = []
    c = _client(monkeypatch, seen)
    r = c.get("/supply-demand/bounce-room", params={"symbols": "eose, clym,,EOSE"})
    assert r.status_code == 200 and seen == [["EOSE", "CLYM"]]
    assert c.get("/supply-demand/bounce-room", params={"symbols": ","}).status_code == 422
    assert c.get("/supply-demand/bounce-room").status_code == 422


def test_post_route_caps_at_MAX_SYMBOLS(monkeypatch):
    seen = []
    c = _client(monkeypatch, seen)
    r = c.post("/supply-demand/bounce-room", json={"symbols": [f"S{i}" for i in range(2600)]})
    assert r.status_code == 200 and len(seen[0]) == BR.MAX_SYMBOLS == 2500


def test_routes_exist_and_offload_to_a_thread_with_the_disclaimer():
    src = (ROOT / "backend/supply_demand/api.py").read_text()
    assert '@router.post("/supply-demand/bounce-room")' in src
    assert '@router.get("/supply-demand/bounce-room")' in src
    assert "asyncio.to_thread(bounce_room_mod.api_payload, syms)" in src
    assert "not advice" in src[src.index('@router.post("/supply-demand/bounce-room")'):][:3000]
    assert "docs/supply_demand/bounce_room.md" in src


# ── integrator fixes 2026-09-05 (review of the 22-bug sweep) ─────────────────
def test_room_read_skips_a_supply_band_yesterday_closed_above():
    """Review 2026-09-05: room_for / alert_gates learned the broken-supply rule
    (hi < prev_close = support, not a ceiling) but bounce_room.first_overhead did
    not, so the 🪃 push said 'room: clear runway' while the SEPA chip / Demand
    sort still quoted room to the 173.87 shelf. Same doc, same answer now; an
    unknown prev close keeps every supply band (the conservative read)."""
    from supply_demand import alert_gates as AG
    out = BR.room_read(96.0, _doc([SUP_BROKEN, SUP_OVER], prev_close=100.0))   # 95-97 closed above yesterday
    assert out["state"] == "ROOM" and out["band"]["lo"] == 110.0 and out["room_pct"] == 14.58
    assert BR.room_read(96.0, _doc([SUP_BROKEN, SUP_OVER], prev_close=None))["state"] == "IN_BAND"
    assert BR.room_read(96.0, _doc([SUP_BROKEN, SUP_OVER], prev_close=97.0))["state"] == "IN_BAND", \
        "closed ON the top is not above it"
    bands = [DEM, SUP_BROKEN, SUP_OVER]
    for px, pc in ((96.0, 100.0), (96.0, None), (99.0, 100.0), (111.0, 100.0), (94.0, 96.0), (96.0, 97.0)):
        ours = BR.first_overhead(BR.overhead_bands(bands, px, pc), px)
        theirs = AG.first_overhead(bands, px, pc)
        assert (ours is None) == (theirs is None), (px, pc)
        assert ours is None or (ours["lo"], ours["hi"]) == (theirs["lo"], theirs["hi"]), (px, pc)


def test_overhead_rule_with_prev_close_matches_portfolio_supply_watch_loaded_standalone():
    """The broken-supply rule travels to the Portfolio 🎯 table too (same
    function pair, same fixture, every print, both prev-close states)."""
    spec = importlib.util.spec_from_file_location(
        "sw_standalone2", ROOT / "backend/portfolio/supply_watch.py")
    sw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sw)
    bands = [DEM, DEM2, SUP_BROKEN, SUP_OVER, SUP_FAR]
    supply = [b for b in bands if b["kind"] == "supply"]
    demand = [b for b in bands if b["kind"] == "demand"]
    for pc in (None, 100.0, 97.0, 111.0):
        for live in (80.0, 91.0, 96.0, 99.0, 111.0, 120.0):
            theirs = {(z["lo"], z["hi"]) for z in sw.overhead_bands(supply, demand, live, pc)}
            ours = {(z["lo"], z["hi"]) for z in BR.overhead_bands(bands, live, pc)}
            assert ours == theirs, (live, pc)
    assert [z["lo"] for z in sw.overhead_bands(supply, demand, 96.0, 100.0)] == [110.0, 130.0]
