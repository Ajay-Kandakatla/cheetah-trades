"""sepa.prices whole-market snapshot + closed_daily_frame (Gajjala's tab data spine, 2026-10-13, WP1).

`market_snapshot_with_meta` is ONE no-`tickers` call (measured 2026-10-13: 0.49–0.56 s, 13,268 tickers) mapped
through the SAME `_snapshot_row` as `bulk_snapshot`; `closed_daily_frame` serves only bars dated before today and
never writes a cache (trap T5: `load_prices` caches today's partial bar). Network and Mongo are doubled.
"""
from __future__ import annotations

import logging

import pandas as pd
import pytest

from sepa import prices as P

ITEM = {
    "ticker": "AAA",
    "day": {"o": 1.0, "h": 1.5, "l": 0.9, "c": 1.4, "v": 2_000_000, "vw": 1.2, "t": 1791864000000},
    "lastTrade": {"p": 1.45, "t": 1791892800000000000},
    "prevDay": {"c": 1.0},
    "min": {"av": 2_100_000, "t": 1791892740000},
    "todaysChangePerc": 45.0,
    "todaysChange": 0.45,
}

EXPECTED_ROW = {
    "open": 1.0, "high": 1.5, "low": 0.9, "close": 1.4, "volume": 2_000_000, "vwap": 1.2,
    "date": pd.Timestamp("2026-10-13"), "change_pct": 45.0,
    "last_trade_price": 1.45, "last_trade_ts_ms": 1791892800000000000, "prev_day_close": 1.0,
    "todays_change": 0.45, "min_av": 2_100_000, "min_t_ms": 1791892740000,
}


class _Resp:
    def __init__(self, status=200, body=None, content=b"x" * 7):
        self.status_code = status
        self._body = body if body is not None else {"tickers": []}
        self.content = content

    def json(self):
        return self._body


class _Sess:
    def __init__(self, resp=None, exc=None):
        self.calls = []
        self.resp = resp or _Resp()
        self.exc = exc

    def get(self, url, **kw):
        self.calls.append((url, kw))
        if self.exc is not None:
            raise self.exc
        return self.resp


@pytest.fixture
def sess(monkeypatch):
    s = _Sess(_Resp(body={"tickers": [dict(ITEM)]}))
    monkeypatch.setattr(P, "_http", lambda: s)
    monkeypatch.setattr(P, "stocks_key", lambda: "SECRETKEY123")
    return s


def test_snapshot_row_is_the_bulk_snapshot_row(sess):
    """The extraction changed nothing: bulk_snapshot's row == _snapshot_row(item) == the pinned mapping, and the
    whole-market call serves the same row."""
    assert P._snapshot_row(dict(ITEM)) == EXPECTED_ROW
    assert P.bulk_snapshot(["AAA"]) == {"AAA": EXPECTED_ROW}
    assert P.market_snapshot() == {"AAA": EXPECTED_ROW}


def test_market_snapshot_one_call_no_tickers_param(sess):
    rows, meta = P.market_snapshot_with_meta()
    assert len(sess.calls) == 1
    url, kw = sess.calls[0]
    assert url == "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers"
    assert "tickers" not in kw["params"]
    assert kw["params"]["include_otc"] == "false"
    assert kw["timeout"] == 30
    assert meta["http"] == 200 and meta["n"] == 1 and meta["bytes"] == 7
    assert isinstance(meta["wall_s"], float)
    assert list(rows) == ["AAA"]


def test_market_snapshot_include_otc_flag_is_passed(sess):
    P.market_snapshot_with_meta(include_otc=True)
    assert sess.calls[0][1]["params"]["include_otc"] == "true"


def test_market_snapshot_class_shares_dash_form(monkeypatch):
    s = _Sess(_Resp(body={"tickers": [dict(ITEM, ticker="BRK.B"), dict(ITEM, ticker="msft")]}))
    monkeypatch.setattr(P, "_http", lambda: s)
    monkeypatch.setattr(P, "stocks_key", lambda: "k")
    rows = P.market_snapshot()
    assert set(rows) == {"BRK-B", "MSFT"}


def test_NEGATIVE_market_snapshot_skips_junk_items(monkeypatch):
    s = _Sess(_Resp(body={"tickers": [None, "x", {"ticker": ""}, dict(ITEM)]}))
    monkeypatch.setattr(P, "_http", lambda: s)
    monkeypatch.setattr(P, "stocks_key", lambda: "k")
    assert list(P.market_snapshot()) == ["AAA"]


def test_NEGATIVE_market_snapshot_non_200_is_empty_not_raise(monkeypatch):
    s = _Sess(_Resp(status=503))
    monkeypatch.setattr(P, "_http", lambda: s)
    monkeypatch.setattr(P, "stocks_key", lambda: "k")
    rows, meta = P.market_snapshot_with_meta()
    assert rows == {} and meta["http"] == 503 and meta["n"] == 0 and "503" in meta["error"]


def test_NEGATIVE_market_snapshot_no_key_never_builds_a_session(monkeypatch):
    monkeypatch.setattr(P, "stocks_key", lambda: "")
    monkeypatch.setattr(P, "_http", lambda: (_ for _ in ()).throw(AssertionError("no key -> no session")))
    rows, meta = P.market_snapshot_with_meta()
    assert rows == {} and meta["http"] is None and meta["error"] == "no stocks key"


def test_NEGATIVE_market_snapshot_never_logs_the_key(monkeypatch, caplog):
    boom = ConnectionError("HTTPSConnectionPool: Max retries exceeded with url: "
                           "/v2/snapshot/locale/us/markets/stocks/tickers?apiKey=SECRETKEY123&include_otc=false")
    s = _Sess(exc=boom)
    monkeypatch.setattr(P, "_http", lambda: s)
    monkeypatch.setattr(P, "stocks_key", lambda: "SECRETKEY123")
    with caplog.at_level(logging.DEBUG):
        rows, meta = P.market_snapshot_with_meta()
    assert rows == {} and meta["http"] is None
    assert "SECRETKEY123" not in meta["error"] and "<redacted>" in meta["error"]
    assert "SECRETKEY123" not in caplog.text


# ── closed_daily_frame ─────────────────────────────────────────────────────────────────────────────────────────
def _daily(last: str, n: int = 5) -> pd.DataFrame:
    idx = pd.bdate_range(end=last, periods=n)
    return pd.DataFrame({"open": 1.0, "high": 2.0, "low": 0.5, "close": [1.0 + i for i in range(n)],
                         "volume": [100.0 + i for i in range(n)]}, index=idx)


NOW = pd.Timestamp("2026-10-13 11:00", tz="America/New_York")


def test_closed_daily_frame_drops_today(monkeypatch):
    monkeypatch.setattr(P, "_mongo_get", lambda s: _daily("2026-10-13"))
    monkeypatch.setattr(P, "_fetch", lambda *a: pytest.fail("a fresh cache needs no fetch"))
    out = P.closed_daily_frame("AAA", now=NOW)
    assert out.index.max() == pd.Timestamp("2026-10-12")
    assert pd.Timestamp("2026-10-13") not in out.index


def test_closed_daily_frame_fetches_when_the_cache_misses_yesterday(monkeypatch):
    monkeypatch.setattr(P, "_mongo_get", lambda s: _daily("2026-10-01"))
    monkeypatch.setattr(P, "_parquet_get", lambda s: pytest.fail("mongo answered"))
    monkeypatch.setattr(P, "_fetch", lambda sym, period: _daily("2026-10-13", 10))
    out = P.closed_daily_frame("AAA", now=NOW)
    assert out.index.max() == pd.Timestamp("2026-10-12") and len(out) == 9


def test_NEGATIVE_closed_daily_frame_never_writes_cache(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("closed_daily_frame must never write a cache")
    monkeypatch.setattr(P, "_mongo_put", _boom)
    monkeypatch.setattr(P, "_parquet_put", _boom)
    monkeypatch.setattr(P, "_mongo_get", lambda s: None)
    monkeypatch.setattr(P, "_parquet_get", lambda s: None)
    monkeypatch.setattr(P, "_fetch", lambda sym, period: _daily("2026-10-13", 6))
    out = P.closed_daily_frame("AAA", now=NOW)
    assert len(out) == 5 and out.index.max() < pd.Timestamp("2026-10-13")


def test_NEGATIVE_closed_daily_frame_no_data_is_none(monkeypatch):
    monkeypatch.setattr(P, "_mongo_get", lambda s: None)
    monkeypatch.setattr(P, "_parquet_get", lambda s: None)
    monkeypatch.setattr(P, "_fetch", lambda sym, period: None)
    assert P.closed_daily_frame("AAA", now=NOW) is None
    monkeypatch.setattr(P, "_fetch", lambda sym, period: _daily("2026-10-13", 1))
    assert P.closed_daily_frame("AAA", now=NOW) is None          # only today's partial bar -> nothing closed


def test_NEGATIVE_closed_daily_frame_fetch_raising_is_none(monkeypatch):
    monkeypatch.setattr(P, "_mongo_get", lambda s: None)
    monkeypatch.setattr(P, "_parquet_get", lambda s: None)
    monkeypatch.setattr(P, "_fetch", lambda sym, period: (_ for _ in ()).throw(RuntimeError("apiKey=SECRET")))
    assert P.closed_daily_frame("AAA", now=NOW) is None


# ── closed_daily_frame(use_cache=False) — index_zones' macro rows (2026-10-15) ──────────────────────────────
def test_closed_daily_frame_use_cache_false_always_fetches(monkeypatch):
    monkeypatch.setattr(P, "_mongo_get", lambda s: pytest.fail("use_cache=False read the mongo cache"))
    monkeypatch.setattr(P, "_parquet_get", lambda s: pytest.fail("use_cache=False read the parquet cache"))
    monkeypatch.setattr(P, "_fetch", lambda sym, period: _daily("2026-10-13", 10))
    out = P.closed_daily_frame("AAA", now=NOW, use_cache=False)
    assert out.index.max() == pd.Timestamp("2026-10-12") and len(out) == 9


def test_NEGATIVE_closed_daily_frame_use_cache_false_never_writes(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("closed_daily_frame must never write a cache")
    monkeypatch.setattr(P, "_mongo_put", _boom)
    monkeypatch.setattr(P, "_parquet_put", _boom)
    monkeypatch.setattr(P, "_fetch", lambda sym, period: _daily("2026-10-13", 6))
    out = P.closed_daily_frame("AAA", now=NOW, use_cache=False)
    assert len(out) == 5 and out.index.max() < pd.Timestamp("2026-10-13")


def test_NEGATIVE_closed_daily_frame_use_cache_false_never_falls_back_to_the_cache(monkeypatch):
    seen = []
    monkeypatch.setattr(P, "_mongo_get", lambda s: seen.append(s) or _daily("2026-10-13"))
    monkeypatch.setattr(P, "_parquet_get", lambda s: seen.append(s) or _daily("2026-10-13"))
    monkeypatch.setattr(P, "_fetch", lambda sym, period: None)
    assert P.closed_daily_frame("AAA", now=NOW, use_cache=False) is None
    assert seen == [], "a failed fresh fetch is None, never the cached frame"
    assert P.closed_daily_frame("AAA", now=NOW) is not None, "the default still reads the fresh cache"


def test_NEGATIVE_closed_daily_frame_use_cache_false_fetch_raising_is_none(monkeypatch):
    monkeypatch.setattr(P, "_mongo_get", lambda s: _daily("2026-10-13"))
    monkeypatch.setattr(P, "_fetch", lambda sym, period: (_ for _ in ()).throw(RuntimeError("apiKey=SECRET")))
    assert P.closed_daily_frame("AAA", now=NOW, use_cache=False) is None
