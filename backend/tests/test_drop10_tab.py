"""🔻 Down 10%+ today tab (chart_maps/drop10_tab.py) — behaviour, negatives,
memo, board wiring and source guards.

Ajay 2026-10-03, verbatim: "I would like to know about stocks that falled
intraday more than 10% new tab please."

Every number the tests assert is derived from the module's constants or from
the frames built here; the boundary tests sit exactly on THRESHOLD_PCT.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps import board as BOARD
from chart_maps import drop10_tab as D10
from chart_maps import fallen_catalysts as FC
from supply_demand import key_levels as KL

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]

FRI = date(2026, 10, 2)
THU = "2026-10-01"
NOW_RTH = datetime(2026, 10, 2, 11, 0, tzinfo=ET)
NOW_AFTER = datetime(2026, 10, 2, 17, 0, tzinfo=ET)
NOW_NIGHT = datetime(2026, 10, 5, 2, 0, tzinfo=ET)          # Monday 02:00 -> Friday closed
NOW_PRE = datetime(2026, 10, 5, 8, 0, tzinfo=ET)            # Monday pre-market -> Friday
NOW_SAT = datetime(2026, 10, 3, 12, 0, tzinfo=ET)
_BANNED = re.compile(r"bounc|fake|\bcaused\b|\bbecause\b", re.I)


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------
def _market_days(end: str, n: int) -> list:
    from market_hours.reminder import ALL_HOLIDAYS
    out, d = [], pd.Timestamp(end)
    while len(out) < n:
        if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in ALL_HOLIDAYS:
            out.append(d)
        d -= pd.Timedelta(days=1)
    return sorted(out)


def _frame(n=120, *, end=FRI.isoformat(), close=100.0, volume=1_000_000.0, day=None):
    """`n` flat bars ending `end`; `day` = the last bar's o/h/l/c/v overrides."""
    idx = pd.DatetimeIndex(_market_days(end, n))
    df = pd.DataFrame({"open": close, "high": close + 1.0, "low": close - 1.0,
                       "close": close, "volume": volume}, index=idx)
    for k, v in (day or {}).items():
        df.iloc[-1, df.columns.get_loc(k)] = v
    return df


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _snap(o, h, lo, c, *, prev=100.0, vol=2_000_000.0, at=datetime(2026, 10, 2, 10, 59, tzinfo=ET)):
    return {"open": o, "high": h, "low": lo, "close": c, "volume": vol, "prev_day_close": prev,
            "min_t_ms": _ms(at), "last_trade_ts_ms": _ms(at) * 1_000_000,
            "date": pd.Timestamp("2026-10-05")}           # the untrusted date field


def _empty_src():
    return {k: {"available": True, "error": None, "by_sym": {}, "names": 0, "first": None,
                "last": None} for k in FC.PRIORITY}


def _build(frames, now, *, snaps=None, profiles=None, src=None, splits=None, etfs=(),
           dead=(), snap_calls=None, split_calls=None):
    def snap_fn(syms):
        if snap_calls is not None:
            snap_calls.append(list(syms))
        return {s: v for s, v in (snaps or {}).items() if s in syms}

    def splits_fn(sym, since):
        if split_calls is not None:
            split_calls.append((sym, since))
        got = (splits or {}).get(sym, [])
        if isinstance(got, Exception):
            raise got
        return got

    return D10.build("full", now, universe_fn=lambda u: [s for s in frames if s not in ("RSP", "XLK")],
                     frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                     snap_fn=snap_fn, profiles_fn=lambda syms: dict(profiles or {}),
                     catalysts_load_fn=lambda syms, names=None: src or _empty_src(),
                     splits_fn=splits_fn, etf_fn=lambda: set(etfs),
                     is_delisted=lambda s: s in dead)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for m in (D10._memo, D10._base_memo, D10._splits_memo, D10._failures):
        m.clear()
    D10._warming.clear()
    spawned = []
    monkeypatch.setattr(D10, "_spawn", lambda target, name: spawned.append((target, name)))
    return spawned


def _fri_frames():
    """AAA −15% at the low, closes −12% (down); BBB −10.00% at the low exactly,
    closes −5% (reclaimed); CCC −9.99% at the low (out); RSP / XLK group."""
    return {
        "AAA": _frame(day={"open": 95.0, "high": 96.0, "low": 85.0, "close": 88.0,
                           "volume": 3_000_000.0}),
        "BBB": _frame(day={"open": 99.0, "high": 100.0, "low": 90.0, "close": 95.0}),
        "CCC": _frame(day={"open": 99.0, "high": 100.0, "low": 90.01, "close": 99.0}),
        "RSP": _frame(day={"close": 101.0}),
        "XLK": _frame(day={"close": 99.0}),
    }


# --------------------------------------------------------------------------
# 1 — which session
# --------------------------------------------------------------------------
def test_01_mode_by_the_tape_clock():
    assert D10.mode_for(NOW_RTH)[:3] == (D10.MODE_LIVE, FRI, "rth")
    assert D10.mode_for(NOW_AFTER)[:3] == (D10.MODE_AFTER, FRI, "afterhours")
    for now in (NOW_NIGHT, NOW_PRE, NOW_SAT, datetime(2026, 10, 2, 21, 0, tzinfo=ET)):
        mode, sess, tape, _half = D10.mode_for(now)
        assert (mode, sess, tape) == (D10.MODE_CLOSED, FRI, "closed"), now


def test_01b_NEG_a_half_day_after_its_13_00_close_is_after_the_close_not_live():
    from supply_demand.timeframes import HALF_DAYS
    day = date.fromisoformat(sorted(HALF_DAYS)[0])
    mode, sess, tape, half = D10.mode_for(datetime(day.year, day.month, day.day, 14, 0, tzinfo=ET))
    assert (mode, sess, tape, half) == (D10.MODE_AFTER, day, "afterhours", True)


def test_01c_NEG_a_holiday_reads_the_last_market_day():
    from market_hours.reminder import ALL_HOLIDAYS
    hol = date.fromisoformat(next(h for h in sorted(ALL_HOLIDAYS) if h >= "2026-11-01"
                                  and date.fromisoformat(h).weekday() < 5))
    mode, sess, _t, _h = D10.mode_for(datetime(hol.year, hol.month, hol.day, 11, 0, tzinfo=ET))
    assert mode == D10.MODE_CLOSED and sess < hol and sess.isoformat() not in ALL_HOLIDAYS


# --------------------------------------------------------------------------
# 2 — the per-name reads
# --------------------------------------------------------------------------
def test_02_base_read_prior_close_is_the_bar_before_the_session():
    df = _frame(day={"close": 80.0, "low": 79.0})
    b = D10.base_read(df, FRI)
    assert b["prev_close"] == 100.0 and b["prev_date"] == THU
    assert b["bar"]["close"] == 80.0 and b["bar"]["low"] == 79.0
    assert b["avg_vol50"] == 1_000_000.0 and b["adv50"] == 100.0 * 1_000_000.0
    # live: the session's bar is not in the frame -> no bar, the same prior close
    b2 = D10.base_read(_frame(end=THU), FRI)
    assert b2["bar"] is None and b2["prev_close"] == 100.0 and b2["prev_date"] == THU


def test_02b_NEG_no_bars_before_the_session_is_none():
    assert D10.base_read(None, FRI) is None
    assert D10.base_read(_frame(n=1), FRI) is None                 # only the session's own bar
    assert D10.base_read(pd.DataFrame(), FRI) is None


def test_03_snapshot_is_read_only_when_its_own_stamp_is_the_session():
    d = D10.day_from_snapshot(_snap(95, 96, 85, 88), FRI)
    assert d == {"open": 95.0, "high": 96.0, "low": 85.0, "last": 88.0, "volume": 2_000_000.0,
                 "prev_close": 100.0, "as_of_ms": _ms(datetime(2026, 10, 2, 10, 59, tzinfo=ET))}
    # the overnight shape: Friday's bar served under Monday's `date` -> never Monday's
    assert D10.day_from_snapshot(_snap(95, 96, 85, 88), date(2026, 10, 5)) is None
    # no minute stamp -> the last-trade stamp (nanoseconds) decides
    raw = _snap(95, 96, 85, 88)
    raw.pop("min_t_ms")
    assert D10.day_from_snapshot(raw, FRI)["low"] == 85.0


def test_03b_NEG_a_pre_open_zero_bar_or_no_prior_close_is_not_a_print():
    assert D10.day_from_snapshot(_snap(0, 0, 0, 0), FRI) is None
    assert D10.day_from_snapshot(_snap(95, 96, 85, 88, prev=0), FRI) is None
    assert D10.day_from_snapshot({}, FRI) is None and D10.day_from_snapshot(None, FRI) is None


def _cls(low, last, *, mode=D10.MODE_CLOSED, prev_date=THU, live_prev=None, sym="AAA",
         etfs=(), dead=()):
    base = {"prev_close": 100.0, "prev_date": prev_date, "adv50": 1e8, "avg_vol50": 1e6,
            "n_bars": 100}
    day = {"open": 99.0, "high": 100.0, "low": low, "last": last, "volume": 1e6,
           "prev_close": live_prev, "as_of_ms": None}
    return D10.classify(sym, base, day, session=FRI, mode=mode, etf_set=set(etfs),
                        is_delisted=lambda s: s in dead)


def test_04_boundary_exactly_the_threshold_is_listed_a_hair_above_is_not():
    t = D10.THRESHOLD_PCT
    st, row = _cls(100.0 - t, 100.0 - t)
    assert st == "listed" and row["low_pct"] == -t and row["state"] == D10.STATE_DOWN
    st, row = _cls(100.0 - t, 100.0 - t + 0.01)
    assert st == "listed" and row["state"] == D10.STATE_RECLAIMED
    assert _cls(100.0 - t + 0.01, 99.0)[0] == "under_threshold"


def test_04b_the_threshold_moves_the_words_and_the_list(monkeypatch):
    monkeypatch.setattr(D10, "THRESHOLD_PCT", 15.0)
    assert _cls(88.0, 88.0)[0] == "under_threshold"
    assert _cls(85.0, 88.0)[1]["state"] == D10.STATE_RECLAIMED
    assert "15% or more" in D10.header_text({"listed": 1, "scanned": 2}, mode=D10.MODE_CLOSED,
                                            session_iso="2026-10-02", as_of=None)


def test_05_NEG_stale_and_no_print():
    assert _cls(80.0, 80.0, prev_date="2026-09-30")[0] == "stale"
    base = {"prev_close": 100.0, "prev_date": THU}
    assert D10.classify("A", base, None, session=FRI, mode=D10.MODE_CLOSED, etf_set=set(),
                        is_delisted=lambda s: False)[0] == "stale"
    assert D10.classify("A", base, None, session=FRI, mode=D10.MODE_LIVE, etf_set=set(),
                        is_delisted=lambda s: False)[0] == "no_print"
    assert D10.classify("A", None, None, session=FRI, mode=D10.MODE_LIVE, etf_set=set(),
                        is_delisted=lambda s: False)[0] == "no_bars"


def test_06_NEG_etfs_and_delisted_count_only_when_they_would_list():
    assert _cls(80.0, 80.0, sym="SPY", etfs=("SPY",))[0] == "etf"
    assert _cls(99.0, 99.0, sym="SPY", etfs=("SPY",))[0] == "under_threshold"
    assert _cls(80.0, 80.0, sym="DEAD", dead=("DEAD",))[0] == "delisted"
    assert _cls(99.0, 99.0, sym="DEAD", dead=("DEAD",))[0] == "under_threshold"


def test_07_NEG_data_the_price_layer_cannot_trust_is_held_out_and_named():
    st, row = _cls(100.0 / (D10.GLITCH_RATIO + 1), 100.0 / (D10.GLITCH_RATIO + 1))
    assert st == "data_suspect" and f"{D10.GLITCH_RATIO:g}×" in row["suspect"]
    tol = D10.PREV_CLOSE_TOL_PCT
    st, row = _cls(80.0, 80.0, mode=D10.MODE_LIVE, live_prev=100.0 * (1 + (tol + 0.5) / 100))
    assert st == "data_suspect" and "disagrees with the cached" in row["suspect"]
    assert _cls(80.0, 80.0, mode=D10.MODE_LIVE,
                live_prev=100.0 * (1 + (tol - 0.5) / 100))[0] == "listed"


# --------------------------------------------------------------------------
# 3 — the build
# --------------------------------------------------------------------------
def test_08_closed_build_lists_down_and_reclaimed_and_counts_every_name():
    calls = []
    e = _build(_fri_frames(), NOW_NIGHT, snap_calls=calls,
               profiles={"AAA": {"name": "Aaa Inc", "sector": "Technology"}})
    assert calls == []                                         # closed: no snapshot at all
    assert e["mode"] == D10.MODE_CLOSED and e["session"] == FRI.isoformat()
    assert sorted(e["rows"]) == ["AAA", "BBB"]
    assert e["rows"]["AAA"]["state"] == D10.STATE_DOWN and e["rows"]["AAA"]["low_pct"] == -15.0
    assert e["rows"]["BBB"]["state"] == D10.STATE_RECLAIMED and e["rows"]["BBB"]["now_pct"] == -5.0
    c = e["counts"]
    status = ("no_bars", "stale", "no_print", "under_threshold", "delisted", "etf",
              "data_suspect", "listed")
    assert c["scanned"] == 3 == sum(c[k] for k in status)
    assert c["listed"] == 2 == c["down"] + c["reclaimed"] and c["under_threshold"] == 1
    a = e["rows"]["AAA"]
    assert a["gap_pct"] == -5.0 and a["open_to_low_pct"] == round((85 / 95 - 1) * 100, 2)
    assert a["rvol"]["rvol"] == 3.0 and a["rvol"]["basis"] == "session"
    assert e["rsp_pct"] == 1.0
    grp = a["drop"]["group"]
    assert grp["sector_etf"] == "XLK" and grp["sector_etf_pct"] == -1.0 and grp["rsp_pct"] == 1.0
    assert a["drop"]["window"] == {"lo": THU, "hi": FRI.isoformat()}


def test_09_live_build_reads_the_snapshot_never_the_cached_session_bar():
    fr = _fri_frames()
    fr = {s: df.iloc[:-1] for s, df in fr.items()}             # in RTH the frame ends Thursday
    snaps = {"AAA": _snap(95, 96, 80, 82), "BBB": _snap(99, 100, 95, 96),
             "RSP": _snap(100, 101, 99, 100.5), "XLK": _snap(100, 101, 99, 100)}
    calls = []
    e = _build(fr, NOW_RTH, snaps=snaps, snap_calls=calls)
    assert e["mode"] == D10.MODE_LIVE and sorted(e["rows"]) == ["AAA"]
    assert e["rows"]["AAA"]["low_pct"] == -20.0 and e["counts"]["no_snapshot"] == 1   # CCC: no row
    assert len(calls) == 2 and {"AAA", "RSP", "XLK"} <= set(calls[0]) and "CCC" in calls[1] and "AAA" not in calls[1]
    rv = e["rows"]["AAA"]["rvol"]
    assert rv["actual"] == 2.0 and rv["basis"] in ("actual", "projected") and rv["session_pct"]
    assert e["as_of"].startswith("2026-10-02T10:59")
    assert "live today (2026-10-02), the snapshot as of 10:59 ET" in D10.header_text(
        e["counts"], mode=e["mode"], session_iso=e["session"], as_of=e["as_of"])


def test_09b_NEG_an_empty_live_snapshot_raises_and_an_empty_frames_read_raises():
    fr = _fri_frames()
    with pytest.raises(RuntimeError, match="snapshot"):
        _build(fr, NOW_RTH, snaps={})
    D10._base_memo.clear()
    with pytest.raises(RuntimeError, match="no frames"):
        D10.build("full", NOW_NIGHT, universe_fn=lambda u: ["AAA"], frames_fn=lambda s: {},
                  etf_fn=set, is_delisted=lambda s: False)


def test_10_a_split_on_the_session_is_held_out_named_and_memoised():
    split = [{"ticker": "AAA", "execution_date": FRI.isoformat(), "split_from": 1.0,
              "split_to": 2.0}]
    calls = []
    e = _build(_fri_frames(), NOW_NIGHT, splits={"AAA": split}, split_calls=calls)
    assert sorted(e["rows"]) == ["BBB"] and [s["symbol"] for s in e["suspects"]] == ["AAA"]
    assert "2-for-1 split executed 2026-10-02" in e["suspects"][0]["suspect"]
    assert e["counts"]["data_suspect"] == 1 and e["counts"]["listed"] == 1
    assert sorted(calls) == [("AAA", FRI.isoformat()), ("BBB", FRI.isoformat())]
    _build(_fri_frames(), NOW_NIGHT, splits={"AAA": split}, split_calls=calls)
    assert len(calls) == 2                                     # one read per (name, session)


def test_10b_NEG_a_failed_split_read_is_counted_never_silent_and_retried():
    calls = []
    e = _build(_fri_frames(), NOW_NIGHT, splits={"AAA": RuntimeError("down")}, split_calls=calls)
    assert "AAA" in e["rows"] and e["counts"]["split_unchecked"] == 1
    assert "could not be checked for a split" in D10.count_line(
        e["counts"], min_tier_label="x", need_date=THU)
    _build(_fri_frames(), NOW_NIGHT, split_calls=calls)
    assert calls.count(("AAA", FRI.isoformat())) == 2          # a failure is not memoised


def test_11_catalysts_pick_the_session_before_and_never_an_item_after_the_close():
    src = _empty_src()
    src["news"]["by_sym"] = {"AAA": [
        {"kind": "news", "date": THU, "text": "headline 2026-10-01: guidance cut",
         "url": "https://example.test/a", "source": "news", "ts": None}]}
    src["earnings"]["by_sym"] = {"BBB": [
        {"kind": "earnings", "date": FRI.isoformat(), "text": "earnings 2026-10-02", "url": None,
         "source": "earnings", "when": "AMC", "ts": None}]}
    e = _build(_fri_frames(), NOW_NIGHT, src=src)
    hit_a = D10.hit_block(e["rows"]["AAA"])
    assert hit_a["class"] == "news" and "possible: headline 2026-10-01: guidance cut" in hit_a["text"]
    b = e["rows"]["BBB"]["drop"]
    assert b["items"][0]["after_drop"] is True
    assert D10.hit_block(e["rows"]["BBB"])["class"] == "nothing"
    assert "nothing on file by that close" in D10.hit_block(e["rows"]["BBB"])["text"]


class _Resp:
    def __init__(self, code, body=None):
        self.status_code, self._body = code, body

    def json(self):
        return self._body


class _Http:
    def __init__(self, resp):
        self.resp, self.calls = resp, []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        return self.resp


def test_10c_the_strict_split_read_raises_on_an_outage_never_reads_it_as_no_split(monkeypatch):
    import massive_keys
    from sepa import prices
    monkeypatch.setattr(massive_keys, "stocks_key", lambda: "k")
    ok = _Http(_Resp(200, {"results": [{"execution_date": "2026-10-02", "split_from": 1,
                                        "split_to": 4}]}))
    monkeypatch.setattr(prices, "_http", lambda: ok)
    assert D10.fetch_splits_strict("BRK-B", "2026-10-02") == [
        {"execution_date": "2026-10-02", "split_from": 1.0, "split_to": 4.0}]
    assert ok.calls[0][1]["ticker"] == "BRK.B" and ok.calls[0][1]["execution_date.gte"] == "2026-10-02"
    monkeypatch.setattr(prices, "_http", lambda: _Http(_Resp(200, {"results": []})))
    assert D10.fetch_splits_strict("AAA", "2026-10-02") == []
    monkeypatch.setattr(prices, "_http", lambda: _Http(_Resp(503, {})))
    with pytest.raises(RuntimeError, match="503"):
        D10.fetch_splits_strict("AAA", "2026-10-02")
    monkeypatch.setattr(massive_keys, "stocks_key", lambda: "")
    with pytest.raises(RuntimeError, match="no stocks key"):
        D10.fetch_splits_strict("AAA", "2026-10-02")


# --------------------------------------------------------------------------
# 4 — order and words
# --------------------------------------------------------------------------
def _r(sym, low, now, off, rvol):
    return {"symbol": sym, "low_pct": low, "now_pct": now, "off_low_pct": off,
            "rvol": {"rvol": rvol}}


def test_12_orders_are_the_served_four():
    e = {"rows": {r["symbol"]: r for r in (_r("A", -12, -11, 1.0, 2.0), _r("B", -20, -5, 18.0, None),
                                             _r("C", -15, -14, 1.1, 5.0))},
         "counts": {"listed": 3}}
    assert [r["symbol"] for r in D10.rank(e, sort="default")[0]] == ["B", "C", "A"]
    assert [r["symbol"] for r in D10.rank(e, sort=D10.SORT_NOW)[0]] == ["C", "A", "B"]
    assert [r["symbol"] for r in D10.rank(e, sort=D10.SORT_RECLAIM)[0]] == ["B", "C", "A"]
    assert [r["symbol"] for r in D10.rank(e, sort=D10.SORT_RVOL)[0]] == ["C", "A", "B"]  # None last
    assert [s["key"] for s in D10.served_sorts()] == ["default", *D10.TAB_SORTS]


def test_13_words_minus_signs_and_one_pill():
    e = _build(_fri_frames(), NOW_NIGHT)
    a = e["rows"]["AAA"]
    assert D10.tile_badges(a) == [{"text": f"{D10.MARK} −15.00% at the low · still down",
                                   "tone": "warn"}]
    assert D10.tile_badges(e["rows"]["BBB"])[0]["text"].endswith("reclaimed to −5.00%")
    h = D10.header_text(e["counts"], mode=e["mode"], session_iso=e["session"], as_of=e["as_of"],
                        rsp_pct=e["rsp_pct"])
    assert h.startswith(f"{D10.MARK} 2 of 3 stocks traded 10% or more under their prior close")
    assert "the last closed session (2026-10-02)" in h and "1 still 10%+ down, 1 reclaimed" in h
    assert "RSP +1.00%" in h
    assert [s["k"] for s in D10.tile_stats(a)] == ["Prior close", "Low", "Now", "Legs", "Volume",
                                                   "Group"]


def test_13b_NEG_a_ticker_hyphen_is_never_turned_into_a_minus():
    lines = D10.suspects_block([{"symbol": "BRK-B", "low_pct": -12.0, "prev_close": 400.0,
                                 "suspect": "x"}])["lines"]
    assert lines[0].startswith("BRK-B — low −12.00%")


def _served_words(e):
    out = [D10.NOTE, D10.WARMING_NOTE, D10.EMPTY_NOTE, D10.error_note("x")]
    out += [D10.order_line(s) for s in ("default", *D10.TAB_SORTS)]
    out += [s["label"] for s in D10.served_sorts()]
    out.append(D10.count_line(e["counts"], min_tier_label="x", need_date=THU))
    for r in e["rows"].values():
        out += [b["text"] for b in D10.tile_badges(r)] + [s["v"] for s in D10.tile_stats(r)]
        out += [D10.why_text(r, "zone"), D10.state_text(r), D10.legs_text(r), D10.rvol_text(r["rvol"])]
    return out


def test_14_NEG_no_banned_word_in_any_served_string_or_the_module():
    for s in _served_words(_build(_fri_frames(), NOW_NIGHT)):
        assert not _BANNED.search(s), s
    src = (BACKEND / "chart_maps" / "drop10_tab.py").read_text(encoding="utf-8")
    assert not _BANNED.search(src.replace("quick_bounce", ""))
    assert "UNMEASURED" in src and D10.MEASURED is False
    assert not re.search(r"insert_|update_one|update_many|replace_one|delete_|bulk_write|"
                         r"create_index|\.drop\(|open\(", src)


# --------------------------------------------------------------------------
# 5 — the memo
# --------------------------------------------------------------------------
def _patch_build(monkeypatch, frames):
    real = D10.build

    def fake(universe, now, **k):
        return real(universe, now, universe_fn=lambda u: [s for s in frames if s not in ("RSP", "XLK")],
                    frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                    profiles_fn=lambda s: {}, catalysts_load_fn=lambda s, names=None: _empty_src(),
                    splits_fn=lambda s, d: [], etf_fn=set, is_delisted=lambda s: False)
    monkeypatch.setattr(D10, "build", fake)


def test_15_warming_then_ready_spawns_once(monkeypatch, _clean):
    _patch_build(monkeypatch, _fri_frames())
    got = D10.cached_or_warm("full", now=NOW_NIGHT)
    assert got["state"] == "warming" and got["entry"] is None
    D10.cached_or_warm("full", now=NOW_NIGHT)
    assert len(_clean) == 1                                   # single flight
    _clean[0][0]()
    got = D10.cached_or_warm("full", now=NOW_NIGHT)
    assert got["state"] == "ready" and got["stale"] is False and "AAA" in got["entry"]["rows"]


def test_15b_a_live_entry_past_its_ttl_is_served_while_one_rebuild_runs(monkeypatch, _clean):
    fr = {s: df.iloc[:-1] for s, df in _fri_frames().items()}
    snaps = {"AAA": _snap(95, 96, 80, 82)}
    real = D10.build
    monkeypatch.setattr(D10, "build", lambda u, now, **k: real(
        u, now, universe_fn=lambda x: ["AAA"], frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr},
        snap_fn=lambda syms: snaps, profiles_fn=lambda s: {},
        catalysts_load_fn=lambda s, names=None: _empty_src(), splits_fn=lambda s, d: [],
        etf_fn=set, is_delisted=lambda s: False))
    D10.cached_or_warm("full", now=NOW_RTH, sync=True)
    key = (D10.MODE_LIVE, FRI.isoformat(), "full")
    D10._memo[key]["built_ts"] -= D10.LIVE_TTL_SEC + 1
    got = D10.cached_or_warm("full", now=NOW_RTH)
    assert got["state"] == "ready" and got["stale"] is True and len(_clean) == 1
    assert D10.ttl_for(D10.MODE_LIVE) == D10.LIVE_TTL_SEC < D10.ttl_for(D10.MODE_CLOSED)


def test_15c_NEG_sync_never_spawns_and_a_failure_backs_off(monkeypatch, _clean):
    _patch_build(monkeypatch, _fri_frames())
    assert D10.cached_or_warm("full", now=NOW_NIGHT, sync=True)["state"] == "ready"
    assert _clean == []
    D10._memo.clear()
    D10._base_memo.clear()
    monkeypatch.setattr(D10, "build", lambda u, now, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    D10.cached_or_warm("full", now=NOW_NIGHT)
    _clean[0][0]()
    got = D10.cached_or_warm("full", now=NOW_NIGHT)
    assert got["state"] == "error" and got["reason"] == "boom" and len(_clean) == 1   # backing off


def test_15d_NEG_a_late_older_session_build_is_dropped():
    D10._memo[(D10.MODE_CLOSED, "2026-10-05", "full")] = {"built_ts": 1.0}
    assert D10._store((D10.MODE_CLOSED, "2026-10-02", "full"), {"built_ts": 2.0}) is False
    assert list(D10._memo) == [(D10.MODE_CLOSED, "2026-10-05", "full")]


# --------------------------------------------------------------------------
# 6 — board wiring
# --------------------------------------------------------------------------
class _Fixed(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW_NIGHT.astimezone(tz) if tz else NOW_NIGHT.replace(tzinfo=None)


@pytest.fixture
def d10_board(monkeypatch):
    from supply_demand import zone_store
    state = {"snap_calls": [], "finish_tiles": []}
    frames = _fri_frames()
    frames["THIN"] = _frame(volume=100.0, day={"low": 70.0, "close": 75.0})
    _patch_build(monkeypatch, frames)

    def _snaps(syms):
        state["snap_calls"].append(list(syms))
        return {}

    def _bars(tiles, days, **k):
        for t in tiles:
            t["bars"] = [{"t": FRI.isoformat(), "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]

    real_finish = BOARD._finish

    def _finish_spy(tiles, *a, **k):
        state["finish_tiles"].append([dict(t) for t in tiles])
        return real_finish(tiles, *a, **k)

    def _enterable(tiles, kind="demand", **k):
        for t in tiles:
            t.setdefault("enterable", {"verdict": "WATCH", "kind": kind})
        return len(tiles)

    monkeypatch.setattr(BOARD, "datetime", _Fixed)
    monkeypatch.setattr(BOARD, "_bulk_snaps", _snaps)
    monkeypatch.setattr(BOARD, "_finish", _finish_spy)
    monkeypatch.setattr(BOARD, "_attach_bars", _bars)
    monkeypatch.setattr(BOARD, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(BOARD, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(BOARD, "_velocity_decor", lambda tiles: None)
    monkeypatch.setattr(BOARD, "_name_for", lambda s: f"{s} Inc")
    monkeypatch.setattr(BOARD, "attach_live_now", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(BOARD, "attach_enterable", _enterable)
    monkeypatch.setattr(BOARD, "attach_band_structure", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(BOARD, "band_structure_coverage", lambda tiles, kind="demand": {})
    monkeypatch.setattr(BOARD, "attach_burst", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(BOARD, "_burst_frames", lambda syms: {})
    monkeypatch.setattr(BOARD, "attach_key_levels", lambda tiles, out=None, **k: None)
    monkeypatch.setattr(zone_store, "load_latest", lambda syms: (None, {}))
    D10.cached_or_warm("full", now=NOW_NIGHT, sync=True)
    return state


_READY_KEYS = {"state", "mode", "session", "as_of", "built_at", "stale", "measured",
               "threshold_pct", "refresh_sec", "glitch_ratio", "sort", "header", "order_line",
               "count_line", "note", "counts", "suspects", "catalysts"}


def test_16_board_ready_envelope_tiles_and_one_snapshot(d10_board):
    out = BOARD.board(tab="drop10", limit=24)
    assert out["tab"] == "drop10" and out["sort"] == "default"
    assert out["sorts"] == D10.served_sorts()
    b = out["drop10_board"]
    assert set(b) == _READY_KEYS and b["state"] == "ready" and b["measured"] is False
    assert b["mode"] == D10.MODE_CLOSED and b["refresh_sec"] is None
    assert b["threshold_pct"] == D10.THRESHOLD_PCT and b["session"] == FRI.isoformat()
    syms = [t["symbol"] for t in out["tiles"]]
    assert syms == ["AAA", "BBB"] and "THIN" not in syms          # under the default floor
    c = b["counts"]
    assert c["dropped_thin"] == 1 and c["shown"] == 2 and c["listed"] == 3
    t = out["tiles"][0]
    assert t["drop10"]["low_pct"] == -15.0 and t["drop10"]["state"] == D10.STATE_DOWN
    assert set(t["drop10"]["zone"]) >= {"demand", "room", "text"}
    assert t["badges"][0]["text"].startswith(f"{D10.MARK} −15.00% at the low")
    assert t["markers"] == [{"date": FRI.isoformat(), "label": "low −15.0%"}]
    assert t["why"].startswith(f"{D10.MARK} −15.00% at the low vs the prior close · still")
    assert len(d10_board["snap_calls"]) == 1 and set(d10_board["snap_calls"][0]) == {"AAA", "BBB"}
    for handed in d10_board["finish_tiles"][-1]:
        for k in BOARD.ATTACH_OWNED_KEYS:
            assert k not in handed, k
    assert BOARD.board(tab="drop10", limit=24, min_tier="any")["drop10_board"]["counts"]["shown"] == 3


def test_16b_NEG_generic_sorts_fall_back_and_drop10_keys_are_tab_scoped(d10_board):
    assert BOARD.board(tab="drop10", sort="volume")["sort"] == "default"
    out = BOARD.board(tab="drop10", sort=D10.SORT_NOW)
    assert out["sort"] == D10.SORT_NOW and out["drop10_board"]["sort"] == D10.SORT_NOW
    src = (BACKEND / "chart_maps" / "board.py").read_text(encoding="utf-8")
    assert '(t == "drop10" and sort in _D10.TAB_SORTS)' in src     # tab-scoped, never global
    assert not set(D10.TAB_SORTS) & set(BOARD.SORTS)


def test_16c_NEG_the_memo_rows_are_never_mutated_by_a_request(d10_board):
    key = (D10.MODE_CLOSED, FRI.isoformat(), "full")
    before = repr(D10._memo[key]["rows"])
    BOARD.board(tab="drop10", limit=24)
    assert repr(D10._memo[key]["rows"]) == before


def test_16d_warming_and_error_envelopes(monkeypatch, _clean):
    monkeypatch.setattr(BOARD, "datetime", _Fixed)
    out = BOARD.drop10_tiles()
    assert out["warming"] is True and out["tiles"] == []
    assert out["drop10_board"]["state"] == "warming" and out["drop10_board"]["header"] == D10.WARMING_NOTE
    key = (D10.MODE_CLOSED, FRI.isoformat(), "full")
    D10._failures[key] = (9e12, "boom")
    out = BOARD.drop10_tiles()
    assert out["drop10_board"]["state"] == "error" and "boom" in out["drop10_board"]["header"]


# --------------------------------------------------------------------------
# 7 — source guards, rules panel, TABS
# --------------------------------------------------------------------------
def test_17_source_guards_reuse_never_retype():
    src = (BACKEND / "chart_maps" / "drop10_tab.py").read_text(encoding="utf-8")
    for need in ("MB.rvol_leg", "MB.avg_volume_before", "MB.session_frac", "MB.burst_session",
                 "FC.items_for", "FC.group_day", "FC.hit_text", "FC.load",
                 "prices._is_scale_glitch", "prices._SCALE_GLITCH_RATIO", "_bulk_snaps_fanout",
                 "zone_store.drop_today", "KL.prev_market_day", "fetch_splits"):
        assert need in src, need
    assert "load_latest_shared" not in src and "json.load" not in src
    body = (BACKEND / "chart_maps" / "board.py").read_text(encoding="utf-8")
    at = body.index("def drop10_tiles(")
    body = body[at:body.index("\ndef ", at + 1)]
    assert body.count("_bulk_snaps(") == 1 and "copy.deepcopy(r)" in body
    assert "_bulk_snaps_fanout" not in body and "load_latest_shared" not in body


def test_18_NEG_no_trading_push_scanner_or_alert_module_imports_the_tab():
    targets = list((BACKEND / "trading").rglob("*.py")) + list((BACKEND / "push").rglob("*.py"))
    targets.append(BACKEND / "sepa" / "scanner.py")
    targets += list((BACKEND / "supply_demand").glob("*alerts*.py"))
    hits = [p for p in targets if p.exists() and "drop10_tab" in p.read_text(encoding="utf-8")]
    assert hits == [] and len(targets) > 5


def test_19_rules_panel_section_built_from_the_constants(monkeypatch):
    from supply_demand import rules_info as RI
    keys = RI.SECTION_KEYS
    assert keys.index("drop10") == keys.index("fallen") + 1
    sec = RI.sections()["drop10"]
    text = " ".join(sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]])
    assert f"{D10.THRESHOLD_PCT:g}% or more under the prior" in text and sec["emoji"] == D10.MARK
    assert f"{D10.GLITCH_RATIO:g}×" in text and D10.order_line("default") in sec["picks"]
    assert not _BANNED.search(text)
    monkeypatch.setattr(D10, "THRESHOLD_PCT", 12.0)
    assert "12% or more" in " ".join(RI._drop10_section()["picks"])


def test_20_drop10_sits_after_fallen_and_is_not_a_demand_tab():
    assert BOARD.TABS.index("drop10") == BOARD.TABS.index("fallen") + 1
    from supply_demand import enterable as EN
    assert "drop10" not in EN.KIND_BY_TAB


# --------------------------------------------------------------------------
# critic round 2026-10-05 — regressions
# --------------------------------------------------------------------------
def test_21_rvol_is_the_projection_whenever_there_is_one_so_the_sort_never_inverts():
    from supply_demand import momentum_burst as MB
    frac = MB.session_frac("rth", NOW_RTH)
    base = {"avg_vol50": 1_000_000.0}
    a = D10.rvol_read({"volume": 2_000_000.0}, base, tape="rth", frac=frac, half_day=False)
    b = D10.rvol_read({"volume": 1_400_000.0}, base, tape="rth", frac=frac, half_day=False)
    assert a["basis"] == b["basis"] == "projected" and a["rvol"] == a["projected"]
    assert a["rvol"] > b["rvol"] > a["actual"]                 # NEG: never the so-far 2.00×
    e = {"rows": {"A": {**_r("A", -12, -11, 1, a["rvol"])}, "B": {**_r("B", -12, -11, 1, b["rvol"])}}}
    assert [r["symbol"] for r in D10.rank(e, sort=D10.SORT_RVOL)[0]] == ["A", "B"]
    assert "projected to a full session" in D10.rvol_text(a)


def test_22_NEG_a_swallowed_snapshot_chunk_is_retried_once_then_counted_never_no_print():
    fr = {s: df.iloc[:-1] for s, df in _fri_frames().items()}
    snaps = {"AAA": _snap(95, 96, 80, 82), "RSP": _snap(100, 101, 99, 100.5)}
    calls = []
    e = _build(fr, NOW_RTH, snaps=snaps, snap_calls=calls)
    assert len(calls) == 2 and {"BBB", "CCC", "XLK"} <= set(calls[1])
    assert "AAA" not in calls[1] and "RSP" not in calls[1] and e["counts"]["no_snapshot"] == 2 and e["counts"]["no_print"] == 0
    assert "2 names got no answer from the live snapshot" in D10.count_line(
        e["counts"], min_tier_label="x", need_date=THU)
    # the retry answers -> the name is read and listed
    late = {"BBB": _snap(99, 100, 88, 90)}
    seen = []

    def snap_fn(syms):
        seen.append(list(syms))
        return {s: v for s, v in (snaps if len(seen) == 1 else late).items() if s in syms}

    D10._base_memo.clear()
    e2 = D10.build("full", NOW_RTH, universe_fn=lambda u: ["AAA", "BBB", "CCC"],
                   frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr}, snap_fn=snap_fn,
                   profiles_fn=lambda s: {}, catalysts_load_fn=lambda s, names=None: _empty_src(),
                   splits_fn=lambda s, d: [], etf_fn=set, is_delisted=lambda s: False)
    assert sorted(e2["rows"]) == ["AAA", "BBB"] and e2["counts"]["no_snapshot"] == 1   # CCC


def test_23_the_hit_line_names_the_leg_that_did_the_falling_on_a_reclaimed_name():
    row = {"symbol": "X", "session": FRI.isoformat(), "prev_close": 100.0, "last": 98.0,
           "low_pct": -14.0, "now_pct": -2.0, "gap_pct": -3.0, "open_to_low_pct": -11.34,
           "open_to_now_pct": 1.03, "rvol": {"rvol": 2.0}}
    d = D10.drop_of(row)
    assert d["larger_leg"] == "intraday" and d["intraday_pct"] == -11.34 and d["c2c_pct"] == -14.0
    text = FC.hit_text(d, [], None)
    assert "What hit it: −14.0% on 2026-10-02 (intraday −11.3%" in text
    assert "gap −3.0%" not in text                             # NEG: the small gap is not the fall


def test_24_NEG_half_day_words_print_the_13_00_close_and_partial_volume_says_so_far():
    from supply_demand import momentum_burst as MB
    w = D10.session_words(D10.MODE_AFTER, "2026-11-27", None, half_day=True)
    assert f"closed at {MB.HALF_DAY_CLOSE_ET:%H:%M} ET" in w and "16:00" not in w
    assert "closed at 16:00 ET" in D10.session_words(D10.MODE_AFTER, "2026-10-02", None)
    rv = {"rvol": 0.9, "basis": "actual", "session_pct": None}
    assert D10.rvol_text(rv) == "0.90× so far — the session is not over"
    entry = {"mode": D10.MODE_AFTER, "session": "2026-11-27", "as_of": None, "half_day": True,
             "rows": {}, "counts": {}}
    blk = D10.ready_block({"listed": 0, "scanned": 1}, entry=entry, sort="default",
                          min_tier_label="x")
    assert "closed at 13:00 ET" in blk["header"]
