"""⚡ Tape scan: windowed parallel Massive paging (2026-10-18, DECISIONS14 D1–D7).

Ajay 2026-10-18: "I see a big lag in Tap reading its 30 secs this feature. Can we make it fast."

Hermetic: a thread-safe fake Massive (/v3/trades + /v3/quotes, `timestamp.gte/lt` honoured on the
first request, `next_url` cursors emulated) behind `requests.get`; `time.sleep` recorded. No network.
"""
import concurrent.futures
import io
import logging
import math
import re
import sys
import threading
import tokenize
import types
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orderflow import massive_pages as MP     # noqa: E402
from orderflow import quotes as Q             # noqa: E402
from orderflow import retail as R             # noqa: E402
from orderflow import tape as TP              # noqa: E402

ET = ZoneInfo("America/New_York")
DAY = date(2026, 10, 16)
NS = 1_000_000_000
BACKEND = Path(__file__).resolve().parents[1]


def ns_at(h, m, s=0.0, day=DAY):
    whole = int(datetime(day.year, day.month, day.day, h, m, tzinfo=ET).timestamp()) * NS
    return whole + int(round(s * NS))


def ts_at(h, m, s=0.0):
    return pd.Timestamp(ns_at(h, m, s), unit="ns", tz="UTC")


# ── synthetic day ────────────────────────────────────────────────────────────
def trade_rows(dense=0):
    """A print every 120 s from 04:00:07 to 20:00, plus edge prints at exactly 09:30:00, 09:45:00 and
    16:00:00, plus `dense` prints (1 s apart) from 10:05:00.25 inside the 10:00–10:30 window."""
    ts = list(range(ns_at(4, 0, 7), ns_at(20, 0), 120 * NS))
    ts += [ns_at(9, 30), ns_at(9, 45), ns_at(16, 0)]
    ts += [ns_at(10, 5, 0.25) + i * NS for i in range(dense)]
    ts = sorted(ts)
    return [{"sip_timestamp": t, "participant_timestamp": t - 500, "price": 10.0 + (i % 7) / 100,
             "size": 100 + i % 3, "conditions": None, "exchange": 4 if i % 2 else 10}
            for i, t in enumerate(ts)]


def quote_rows(dense=0):
    ts = list(range(ns_at(9, 30, 3), ns_at(16, 0), 120 * NS))
    ts += [ns_at(10, 5, 0.5) + i * NS for i in range(dense)]
    ts = sorted(ts)
    return [{"sip_timestamp": t, "bid_price": 9.99 + (i % 5) / 100, "ask_price": 10.01 + (i % 5) / 100}
            for i, t in enumerate(ts)]


class _Resp:
    def __init__(self, code, body=None):
        self.status_code, self._b, self.text = code, body or {}, "err" if code != 200 else ""

    def json(self):
        return self._b


class FakeMassive:
    """Thread-safe fake of Massive's paged /v3/trades and /v3/quotes."""

    def __init__(self, trades=(), quotes=(), *, page_size=None, status_for=None, n429_per_window=None,
                 on_call=None, stop_ref=None, key="k"):
        self.rows = {"trades": sorted(trades, key=lambda r: r["sip_timestamp"]),
                     "quotes": sorted(quotes, key=lambda r: r["sip_timestamp"])}
        self.page_size = page_size
        self.status_for = status_for or (lambda kind, widx, page: 200)
        self.n429 = dict(n429_per_window or {})
        self.on_call = on_call
        self.stop_ref = stop_ref            # callable -> the pull's stop event (or None)
        self.key = key
        self.lock = threading.Lock()
        self.calls = []                     # dicts: url, params, kind, widx, page, stop_set
        self.cursors = {}
        self.attempts = {}
        self.gte_idx = {"trades": {g: i for i, (g, _) in enumerate(MP.windows_for(DAY, (4, 0), (20, 0)))},
                        "quotes": {g: i for i, (g, _) in
                                   enumerate(MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END))}}

    def calls_for(self, kind=None, widx=None):
        return [c for c in self.calls if (kind is None or c["kind"] == kind)
                and (widx is None or c["widx"] == widx)]

    def __call__(self, url, params=None, timeout=None):
        params = dict(params or {})
        kind = "trades" if "/v3/trades/" in url else "quotes"
        with self.lock:
            if "cursor=" in url:
                cur = self.cursors[url.split("cursor=")[1]]
                widx, page, gte, lt, offset = cur
            else:
                gte, lt = int(params["timestamp.gte"]), int(params["timestamp.lt"])
                widx, page, offset = self.gte_idx[kind].get(gte, -1), 0, 0
            stop = self.stop_ref() if self.stop_ref else None
            self.calls.append({"url": url, "params": params, "kind": kind, "widx": widx, "page": page,
                               "stop_set": bool(stop is not None and stop.is_set())})
            n = self.attempts.get((kind, widx, page), 0)
            self.attempts[(kind, widx, page)] = n + 1
        if self.on_call:
            self.on_call(kind, widx, page)
        if page == 0 and n < self.n429.get((kind, widx), self.n429.get(widx, 0)):
            return _Resp(429)
        st = self.status_for(kind, widx, page)
        if st == "raise":
            import requests
            raise requests.ConnectionError(f"boom https://api.massive.com/v3/{kind}/X?apiKey={self.key}")
        if st == 429 or st == 500:
            return _Resp(st)
        rows = [r for r in self.rows[kind] if gte <= r["sip_timestamp"] < lt]
        ps = self.page_size or int(params.get("limit") or 50000)
        chunk = rows[offset:offset + ps]
        body = {"results": [dict(r) for r in chunk]}
        if offset + ps < len(rows):
            with self.lock:
                tok = f"c{len(self.cursors)}"
                self.cursors[tok] = (widx, page + 1, gte, lt, offset + ps)
            body["next_url"] = f"https://api.massive.com/v3/{kind}/X?cursor={tok}"
        return _Resp(200, body)


@pytest.fixture
def env(monkeypatch):
    import massive_keys
    import requests
    sleeps = []
    state = {}
    monkeypatch.setattr(massive_keys, "stocks_key", lambda: state.get("key", "k"))
    monkeypatch.setattr(MP.time, "sleep", lambda s: sleeps.append(s))

    def install(fake):
        state["key"] = fake.key
        monkeypatch.setattr(requests, "get", fake)
        return fake
    return types.SimpleNamespace(install=install, sleeps=sleeps, monkeypatch=monkeypatch)


# ── serial reference (the pre-2026-10-18 pager + frame build, copied) ────────
def _serial_rows(url, key, gte, lt, limit=50000):
    import requests
    rows, params, next_url = [], {"timestamp.gte": gte, "timestamp.lt": lt, "order": "asc",
                                  "sort": "timestamp", "limit": limit, "apiKey": key}, url
    while next_url:
        r = requests.get(next_url, params=params, timeout=10)
        assert r.status_code == 200
        body = r.json() or {}
        rows.extend(body.get("results") or [])
        nxt = body.get("next_url")
        if nxt:
            next_url, params = nxt, {"apiKey": key}
        else:
            next_url = None
    return rows


def _serial_trades_frame(rows):
    df = pd.DataFrame(rows)
    ts_col = "sip_timestamp" if "sip_timestamp" in df.columns else "participant_timestamp"
    df["ts_utc"] = pd.to_datetime(df[ts_col], unit="ns", utc=True)
    TP.label_kinds(df)
    if "participant_timestamp" in df.columns:
        df["exec_utc"] = pd.to_datetime(df["participant_timestamp"], unit="ns", utc=True)
    keep = (["ts_utc", "price", "size"] + (["exchange"] if "exchange" in df.columns else [])
            + ["kind"] + (["exec_utc"] if "exec_utc" in df.columns else []))
    df = df[keep].dropna(subset=["ts_utc", "price", "size"]).sort_values("ts_utc").set_index("ts_utc")
    df = df[(df["price"] > 0) & (df["size"] > 0)]
    df.attrs["truncated"] = False
    return df


def _serial_quotes_frame(rows):
    df = pd.DataFrame(rows)
    df["ts_utc"] = pd.to_datetime(df["sip_timestamp"], unit="ns", utc=True)
    df = df.rename(columns={"bid_price": "bid", "ask_price": "ask"})
    df = df[["ts_utc", "bid", "ask"]].dropna().sort_values("ts_utc").set_index("ts_utc")
    df = df[(df["bid"] > 0) & (df["ask"] > 0) & (df["ask"] > df["bid"])]
    df.attrs["truncated"] = False
    return df


def _reference_quote_rule_sides_d10(trades, quotes, fallback_sides):
    """An independent reference for quotes.quote_rule_sides under D10 (+ the critic MED) for frames WITHOUT
    the `covered` attr: the pre-2026-10-18 loop with the D10 coverage line and a degenerate quote counted
    uncovered. Renamed 2026-10-18 (critic LOW): it no longer is the pre-change code."""
    n = len(trades)
    fb = list(fallback_sides)
    left = trades.reset_index()[["ts_utc", "price"]]
    right = quotes.reset_index()[["ts_utc", "bid", "ask"]]
    merged = pd.merge_asof(left.sort_values("ts_utc"), right.sort_values("ts_utc"),
                           on="ts_utc", direction="backward")
    sides, n_quote, n_mid, n_fb, n_none = [], 0, 0, 0, 0
    for i, row in enumerate(merged.itertuples(index=False)):
        bid, ask = row.bid, row.ask
        if pd.isna(bid) or pd.isna(ask):
            sides.append(fb[i]); n_fb += 1; n_none += 1
            continue
        if not float(bid) or not float(ask) or float(ask) <= float(bid):   # critic MED: not a held quote
            sides.append(fb[i]); n_fb += 1; n_none += 1
            continue
        s = Q.classify_against_quote(row.price, float(bid), float(ask))
        if s == 0:
            n_mid += 1; sides.append(fb[i]); n_fb += 1
        else:
            n_quote += 1; sides.append(s)
    # CHANGED 2026-10-18 (DECISIONS14 D10): coverage = share of prints WITH a prevailing quote
    # (was 100 * n_quote / n, which also subtracted at-mid prints); n_uncovered = prints with no prior quote
    coverage = round(100.0 * (n - n_none) / n, 1) if n else 0.0
    return {"sides": sides, "coverage_pct": coverage, "n_quote_classified": n_quote,
            "n_fallback": n_fb, "n_at_mid": n_mid, "n_uncovered": n_none,
            "method": "quote" if coverage >= Q.MIN_USEFUL_COVERAGE_PCT else "mixed",
            "trustworthy": coverage >= Q.MIN_USEFUL_COVERAGE_PCT}


def _pre_d10_quote_rule_sides(trades, quotes, fallback_sides=None):
    """VERBATIM body of quotes.quote_rule_sides at 4b1873a5 (before D10), module names bound below."""
    covered_mask, classify_against_quote = Q.covered_mask, Q.classify_against_quote
    MIN_USEFUL_COVERAGE_PCT = Q.MIN_USEFUL_COVERAGE_PCT
    n = len(trades)
    fb = list(fallback_sides) if fallback_sides is not None else [0] * n
    if n == 0:
        return {"sides": [], "coverage_pct": 0.0, "n_quote_classified": 0,
                "n_fallback": 0, "n_at_mid": 0, "n_uncovered": 0, "method": "none",
                "trustworthy": False}
    if quotes is None or quotes.empty:
        return {"sides": fb, "coverage_pct": 0.0, "n_quote_classified": 0,
                "n_fallback": n, "n_at_mid": 0, "n_uncovered": n, "method": "tick",
                "trustworthy": False}

    left = trades.reset_index()[["ts_utc", "price"]]
    right = quotes.reset_index()[["ts_utc", "bid", "ask"]]
    merged = pd.merge_asof(
        left.sort_values("ts_utc"), right.sort_values("ts_utc"),
        on="ts_utc", direction="backward",
    )

    inside = covered_mask(merged["ts_utc"], quotes)

    sides, n_quote, n_mid, n_fb, n_unc = [], 0, 0, 0, 0
    for i, row in enumerate(merged.itertuples(index=False)):
        bid, ask = row.bid, row.ask
        if not inside[i]:                 # no quote held for this moment → tick rule (D5)
            sides.append(fb[i] if i < len(fb) else 0)
            n_fb += 1
            n_unc += 1
            continue
        if pd.isna(bid) or pd.isna(ask):
            sides.append(fb[i] if i < len(fb) else 0)
            n_fb += 1
            continue
        s = classify_against_quote(row.price, float(bid), float(ask))
        if s == 0:                        # exactly at mid → tick rule decides
            n_mid += 1
            sides.append(fb[i] if i < len(fb) else 0)
            n_fb += 1
        else:
            n_quote += 1
            sides.append(s)

    coverage = round(100.0 * n_quote / n, 1) if n else 0.0
    return {
        "sides": sides,
        "coverage_pct": coverage,
        "n_quote_classified": n_quote,
        "n_fallback": n_fb,
        "n_at_mid": n_mid,
        "n_uncovered": n_unc,
        "method": "quote" if coverage >= MIN_USEFUL_COVERAGE_PCT else "mixed",
        "trustworthy": coverage >= MIN_USEFUL_COVERAGE_PCT,
    }


def _compact_raw(results):
    return pd.DataFrame(results)


# ── 1. windows_for ───────────────────────────────────────────────────────────
def _contiguous(ws):
    return all(a[1] == b[0] for a, b in zip(ws, ws[1:])) and all(g < lt for g, lt in ws)


def test_windows_for_trades_is_13_contiguous_windows_over_04_to_20():
    ws = MP.windows_for(DAY, (4, 0), (20, 0))
    assert len(ws) == 13 and _contiguous(ws)
    assert ws[0][0] == ns_at(4, 0) and ws[-1][1] == ns_at(20, 0)
    assert [g for g, _ in ws] == [ns_at(*map(int, e.split(":"))) for e in MP.WINDOW_EDGES_ET[:-1]]


def test_windows_for_quotes_is_the_session_windows():
    ws = MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)
    assert len(ws) == Q.N_SESSION_WINDOWS and _contiguous(ws)
    assert ws[0][0] == ns_at(9, 30) and ws[-1][1] == ns_at(16, 0)
    inside = [e for e in MP.WINDOW_EDGES_ET if "09:30" <= e <= "16:00"]
    assert len(inside) == 12 and len(ws) == len(inside) - 1   # 12 edges inside 09:30–16:00 → 11 windows


def test_NEGATIVE_windows_for_clips_edges_outside_the_span():
    ws = MP.windows_for(DAY, (9, 30), (16, 0), edges=("04:00", "12:00", "20:00"))
    assert ws == [(ns_at(9, 30), ns_at(12, 0)), (ns_at(12, 0), ns_at(16, 0))]
    assert MP.windows_for(DAY, (9, 30), (16, 0), edges=()) == [(ns_at(9, 30), ns_at(16, 0))]
    assert MP.windows_for(DAY, (16, 0), (9, 30)) == []


def test_windows_for_a_dst_day_still_spans_16_hours():
    d = date(2026, 3, 9)
    ws = MP.windows_for(d, (4, 0), (20, 0))
    assert len(ws) == 13 and _contiguous(ws)
    assert ws[-1][1] - ws[0][0] == 16 * 3600 * NS
    assert ws[0][0] == ns_at(4, 0, day=d)


def test_windows_for_reads_the_edges_at_call_time(monkeypatch):
    monkeypatch.setattr(MP, "WINDOW_EDGES_ET", ("04:00", "20:00"))
    assert MP.windows_for(DAY, (4, 0), (20, 0)) == [(ns_at(4, 0), ns_at(20, 0))]


# ── 2. equality with the serial reference ────────────────────────────────────
def test_fetch_trades_equals_the_serial_pager_on_an_untruncated_day(env, monkeypatch):
    fake = env.install(FakeMassive(trade_rows(), page_size=40))
    monkeypatch.setattr(TP, "TRADE_PAGES_PER_WINDOW", 1000)
    serial = _serial_rows("https://api.massive.com/v3/trades/IREN", "k", ns_at(4, 0), ns_at(20, 0))
    assert len(serial) == len(trade_rows())
    n_serial_calls = len(fake.calls)
    df = TP.fetch_trades("IREN", DAY)
    assert len(fake.calls) - n_serial_calls > 13            # paging actually happened inside windows
    ref = _serial_trades_frame(serial)
    pd.testing.assert_frame_equal(df, ref)
    assert df.attrs == ref.attrs == {"truncated": False}


def test_fetch_quotes_equals_the_serial_pager_and_covers_every_window(env):
    env.install(FakeMassive(quotes=quote_rows(), page_size=25))
    serial = _serial_rows("https://api.massive.com/v3/quotes/IREN", "k", ns_at(9, 30), ns_at(16, 0))
    df = Q.fetch_quotes("IREN", DAY)
    ref = _serial_quotes_frame(serial)
    pd.testing.assert_frame_equal(df, ref)
    assert df.attrs["truncated"] is False
    ws = MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)
    assert df.attrs["covered"] == [(pd.Timestamp(g, unit="ns", tz="UTC"), pd.Timestamp(e, unit="ns", tz="UTC"))
                                   for g, e in ws]


# ── 3. no duplicates, no gaps ────────────────────────────────────────────────
def test_NEGATIVE_no_duplicates_no_gaps_and_an_edge_print_lands_once_in_the_later_window(env):
    rows = trade_rows()
    env.install(FakeMassive(rows))
    df = TP.fetch_trades("IREN", DAY)
    assert len(df) == len(rows) and not df.index.duplicated().any()
    res = MP.fetch_windowed("https://api.massive.com/v3/trades/IREN", "k",
                            windows=MP.windows_for(DAY, (4, 0), (20, 0)), limit=50000, timeout=1,
                            pages_per_window=2, compact=_compact_raw)
    # CHANGED 2026-10-18 (DECISIONS14 D11): windows hold compacted page frames, not raw rows
    held = [[int(t) for f in w.frames for t in f["sip_timestamp"]] for w in res.windows]
    for edge, later in ((ns_at(9, 30), 1), (ns_at(9, 45), 2), (ns_at(16, 0), 12)):
        where = [i for i, h in enumerate(held) if edge in h]
        assert where == [later]
    assert sum(len(h) for h in held) == len(rows)
    assert [int(t) for f in res.frames for t in f["sip_timestamp"]] == sorted(r["sip_timestamp"] for r in rows)
    assert res.n_rows == len(rows)


# ── 4. per-window bounds, pool size, real concurrency ────────────────────────
def test_every_window_requests_its_own_bounds_and_two_run_at_once(env, monkeypatch):
    sizes = []

    class RecPool(concurrent.futures.ThreadPoolExecutor):
        def __init__(self, max_workers=None, *a, **k):
            sizes.append(max_workers)
            super().__init__(max_workers, *a, **k)
    monkeypatch.setattr(MP, "ThreadPoolExecutor", RecPool)

    lock, live = threading.Lock(), {"now": 0, "max": 0}
    barrier = threading.Barrier(2, timeout=5)

    def on_call(kind, widx, page):
        with lock:
            live["now"] += 1
            live["max"] = max(live["max"], live["now"])
        try:
            if page == 0 and widx in (1, 2):
                barrier.wait()
        finally:
            with lock:
                live["now"] -= 1

    fake = env.install(FakeMassive(trade_rows(), on_call=on_call))
    assert TP.fetch_trades("IREN", DAY) is not None
    ws = MP.windows_for(DAY, (4, 0), (20, 0))
    firsts = [c for c in fake.calls if c["page"] == 0]
    assert sorted((c["params"]["timestamp.gte"], c["params"]["timestamp.lt"]) for c in firsts) == ws
    assert all(c["widx"] >= 0 for c in firsts)
    assert sizes == [min(MP.FETCH_WORKERS, len(ws))] == [8]
    assert live["max"] >= 2


def test_NEGATIVE_no_request_carries_bounds_off_the_edges(env):
    fake = env.install(FakeMassive(trade_rows(), quote_rows(), page_size=30))
    TP.fetch_trades("IREN", DAY)
    Q.fetch_quotes("IREN", DAY)
    edges = {ns_at(*map(int, e.split(":"))) for e in MP.WINDOW_EDGES_ET}
    bounded = [c for c in fake.calls if "timestamp.gte" in c["params"]]
    assert bounded and all(c["params"]["timestamp.gte"] in edges and c["params"]["timestamp.lt"] in edges
                           for c in bounded)
    assert all("timestamp.gte" not in c["params"] and set(c["params"]) == {"apiKey"}
               for c in fake.calls if "cursor=" in c["url"])


# ── 5. truncation is per window: a capped window loses ITS tail, not the afternoon ──
def test_a_dense_window_truncates_alone_and_later_windows_are_read(env):
    # CHANGED 2026-10-18 (DECISIONS14 D12): the fixture's cap is 2 pages via monkeypatch (production is 24)
    env.monkeypatch.setattr(TP, "TRADE_PAGES_PER_WINDOW", 2)
    rows = trade_rows(dense=1000)
    env.install(FakeMassive(rows, page_size=100))
    res_holder = {}
    real = TP.fetch_windowed

    def spy(*a, **k):
        res_holder["r"] = real(*a, **k)
        return res_holder["r"]
    env.monkeypatch.setattr(TP, "fetch_windowed", spy)
    df = TP.fetch_trades("IREN", DAY)
    assert df.attrs["truncated"] is True
    res = res_holder["r"]
    status = [w.status for w in res.windows]
    assert status[3] == "truncated" and res.windows[3].n_rows == 2 * 100
    assert sum(len(f) for f in res.windows[3].frames) == 200
    assert all(s == "ok" for i, s in enumerate(status) if i != 3)
    tail = [r for r in rows if r["sip_timestamp"] >= ns_at(16, 0)]
    assert len(tail) > 100
    assert (df.index >= ts_at(16, 0)).sum() == len(tail)
    assert (df.index >= ts_at(15, 30)).sum() == sum(1 for r in rows if r["sip_timestamp"] >= ns_at(15, 30))


def test_quotes_truncated_window_is_covered_up_to_its_last_quote(env):
    rows = quote_rows(dense=1000)
    env.install(FakeMassive(quotes=rows, page_size=100))
    ws = MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)
    # CHANGED 2026-10-18 (DECISIONS14 D12): a 4-page-per-window budget for the fixture (production is 8)
    df = Q.fetch_quotes("IREN", DAY, max_pages=4 * len(ws))
    assert df.attrs["truncated"] is True
    in_dense = [r["sip_timestamp"] for r in rows if ws[2][0] <= r["sip_timestamp"] < ws[2][1]]
    held = in_dense[:4 * 100]
    cov = df.attrs["covered"]
    assert len(cov) == len(ws)
    assert cov[2] == (pd.Timestamp(ws[2][0], unit="ns", tz="UTC"), pd.Timestamp(held[-1] + 1, unit="ns", tz="UTC"))
    assert cov[2][1] < pd.Timestamp(ws[2][1], unit="ns", tz="UTC")
    assert cov[-1][1] == ts_at(16, 0)
    assert (df.index >= ts_at(15, 45)).sum() == sum(1 for r in rows if r["sip_timestamp"] >= ns_at(15, 45))


def test_a_complete_window_after_a_capped_one_is_covered_from_its_own_first_quote(env):
    rows = quote_rows(dense=1000)
    env.install(FakeMassive(quotes=rows, page_size=100))
    ws = MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)
    df = Q.fetch_quotes("IREN", DAY, max_pages=4 * len(ws))
    cov = df.attrs["covered"]
    a_last = [r["sip_timestamp"] for r in rows if ws[2][0] <= r["sip_timestamp"] < ws[2][1]][399]
    b_first = min(r["sip_timestamp"] for r in rows if ws[3][0] <= r["sip_timestamp"] < ws[3][1])
    assert b_first > ws[3][0]
    U = lambda t: pd.Timestamp(t, unit="ns", tz="UTC")  # noqa: E731
    assert cov[2] == (U(ws[2][0]), U(a_last + 1))                    # capped window A
    assert cov[3] == (U(b_first), U(ws[3][1]))                       # complete window B after A
    assert cov[1] == (U(ws[1][0]), U(ws[1][1]))                      # after an "ok" window: its gte
    assert cov[0] == (U(ws[0][0]), U(ws[0][1]))                      # the first window: its gte
    probe = pd.Series([U(a_last + 1), U(ws[3][0]), U(b_first - 1), U(b_first)])
    assert Q.covered_mask(probe, df).tolist() == [False, False, False, True]


def test_NEGATIVE_a_complete_window_after_a_failed_one_starts_at_its_first_quote(env):
    rows = quote_rows()
    env.install(FakeMassive(quotes=rows, status_for=lambda k, w, p: 500 if w == 5 else 200))
    ws = MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)
    cov = Q.fetch_quotes("IREN", DAY).attrs["covered"]
    b_first = min(r["sip_timestamp"] for r in rows if ws[6][0] <= r["sip_timestamp"] < ws[6][1])
    assert (pd.Timestamp(b_first, unit="ns", tz="UTC"), pd.Timestamp(ws[6][1], unit="ns", tz="UTC")) in cov
    assert all(c[0] != pd.Timestamp(ws[6][0], unit="ns", tz="UTC") for c in cov)


def test_NEGATIVE_a_truncated_window_after_a_failed_one_starts_at_its_first_quote(env):
    rows = quote_rows(dense=1000)                              # window 2 (10:00–10:30) is dense
    ws = MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)
    env.install(FakeMassive(quotes=rows, page_size=100, status_for=lambda k, w, p: 500 if w == 1 else 200))
    df = Q.fetch_quotes("IREN", DAY, max_pages=4 * len(ws))
    U = lambda t: pd.Timestamp(t, unit="ns", tz="UTC")  # noqa: E731
    a_last = max(r["sip_timestamp"] for r in rows if ws[0][0] <= r["sip_timestamp"] < ws[0][1])
    in_b = [r["sip_timestamp"] for r in rows if ws[2][0] <= r["sip_timestamp"] < ws[2][1]]
    b_first, b_last = in_b[0], in_b[399]
    cov = df.attrs["covered"]
    assert df.attrs["truncated"] is True and b_first > ws[2][0]
    assert cov[0] == (U(ws[0][0]), U(ws[0][1]))                      # window 0 complete
    assert cov[1] == (U(b_first), U(b_last + 1))                     # B truncated after failed A (window 1)
    assert all(c[0] != U(ws[2][0]) for c in cov)
    # between the last quote held before B (window 0's tail, = a_last) and B's first quote: uncovered
    gap = [ws[0][1], (ws[1][0] + ws[1][1]) // 2, ws[2][0], b_first - 1]
    assert all(a_last < t < b_first for t in gap)
    probe = pd.Series([U(t) for t in gap] + [U(b_first), U(b_last), U(b_last + 1)])
    assert Q.covered_mask(probe, df).tolist() == [False, False, False, False, True, True, False]
    gap_tr = _tr([(U(t), 10.05, 100, 10) for t in gap])
    out = Q.quote_rule_sides(gap_tr, df, fallback_sides=[-1] * len(gap))
    assert out["n_uncovered"] == len(gap) and out["sides"] == [-1] * len(gap)
    q_held = df[df.index < U(ws[2][0])]
    assert len(q_held) and q_held.index.max() == U(a_last)          # the merge WOULD find A-side quotes


def _quotes_without(rows, lo, hi):
    return [r for r in rows if not lo <= r["sip_timestamp"] < hi]


def test_NEGATIVE_a_complete_window_with_zero_quotes_is_covered_by_the_prior_quote(env):
    ws = MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)
    rows = _quotes_without(quote_rows(), *ws[3])                   # 10:30–11:00 has zero NBBO updates
    env.install(FakeMassive(quotes=rows))
    df = Q.fetch_quotes("IREN", DAY)
    U = lambda t: pd.Timestamp(t, unit="ns", tz="UTC")  # noqa: E731
    cov = df.attrs["covered"]
    assert cov == [(U(g), U(e)) for g, e in ws]                      # 11 spans, no gap, the empty one included
    assert cov[3] == (U(ws[3][0]), U(ws[3][1])) and cov[2][1] == cov[3][0] and cov[3][1] == cov[4][0]
    prior = df[df.index < U(ws[3][0])].iloc[-1]
    t = U((ws[3][0] + ws[3][1]) // 2)
    out = Q.quote_rule_sides(_tr([(t, float(prior["ask"]), 100, 10)]), df, fallback_sides=[-1])
    assert out["sides"] == [1]                                       # the prior prevailing quote's side
    assert out["n_uncovered"] == 0 and out["n_quote_classified"] == 1


def test_NEGATIVE_a_complete_first_window_with_zero_quotes_still_falls_back_on_no_prior_quote(env):
    ws = MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)
    env.install(FakeMassive(quotes=_quotes_without(quote_rows(), *ws[0])))
    df = Q.fetch_quotes("IREN", DAY)
    U = lambda t: pd.Timestamp(t, unit="ns", tz="UTC")  # noqa: E731
    assert df.attrs["covered"][0] == (U(ws[0][0]), U(ws[0][1]))     # its span exists
    assert df.attrs["covered"][1] == (U(ws[1][0]), U(ws[1][1]))     # and the next starts at its gte
    out = Q.quote_rule_sides(_tr([(ts_at(9, 35), 10.0, 100, 10)]), df, fallback_sides=[-1])
    assert out["n_uncovered"] == 1 and out["sides"] == [-1]           # the merge finds no quote at all


def test_NEGATIVE_a_failed_then_empty_complete_window_adds_nothing_and_the_gap_carries_on(env):
    ws = MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)
    rows = _quotes_without(quote_rows(), *ws[2])                   # window 2 completes with zero quotes
    env.install(FakeMassive(quotes=rows, status_for=lambda k, w, p: 500 if w == 1 else 200))
    df = Q.fetch_quotes("IREN", DAY)
    U = lambda t: pd.Timestamp(t, unit="ns", tz="UTC")  # noqa: E731
    cov = df.attrs["covered"]
    b_first = min(r["sip_timestamp"] for r in rows if ws[3][0] <= r["sip_timestamp"] < ws[3][1])
    assert b_first > ws[3][0]
    assert cov[0] == (U(ws[0][0]), U(ws[0][1]))
    assert cov[1] == (U(b_first), U(ws[3][1]))                       # window 3 starts at its own first quote
    assert len(cov) == len(ws) - 2                                    # failed window 1 + empty window 2: nothing
    probe = pd.Series([U(ws[1][0]), U(ws[2][0]), U((ws[2][0] + ws[2][1]) // 2), U(b_first - 1), U(b_first)])
    assert Q.covered_mask(probe, df).tolist() == [False, False, False, False, True]


# ── D13: degenerate quotes are dropped per page ──────────────────────────────
def _q(t, bid, ask):
    return {"sip_timestamp": t, "bid_price": bid, "ask_price": ask}


def test_a_print_during_a_locked_market_reads_the_prior_valid_quote(env):
    rows = [_q(ns_at(10, 0), 10.00, 10.04), _q(ns_at(10, 0, 1), 10.02, 10.02), _q(ns_at(10, 20), 10.10, 10.14)]
    env.install(FakeMassive(quotes=rows))
    df = Q.fetch_quotes("IREN", DAY)
    assert not (df["ask"] <= df["bid"]).any() and len(df) == 2       # NEGATIVE: no locked / crossed row survives
    trades = _tr([(ts_at(10, 10), 10.04, 100, 10), (ts_at(10, 10, 1), 10.00, 100, 10)])
    out = Q.quote_rule_sides(trades, df, fallback_sides=[-1, 1])
    assert out["sides"] == [1, -1]                                    # against the 10:00:00 quote
    assert out["coverage_pct"] == 100.0 and out["n_uncovered"] == 0
    serial = _serial_quotes_frame(rows)                                # the pre-change serial frame
    assert out["sides"] == _pre_d10_quote_rule_sides(trades, serial, [-1, 1])["sides"]


def test_NEGATIVE_a_span_after_a_gap_starts_at_the_first_VALID_quote(env):
    ws = MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)
    dense = [_q(ns_at(9, 30, 1 + i), 10.00, 10.04) for i in range(100)]      # 09:30 window, capped below
    w2 = [_q(ns_at(10, 0, 5), 10.03, 10.03),                                   # first RAW quote: locked
          _q(ns_at(10, 0, 9), 10.10, 10.14), _q(ns_at(10, 5), 10.10, 10.14)]  # first VALID: 10:00:09
    env.install(FakeMassive(quotes=dense + w2, page_size=50))                  # 09:45 window: empty
    df = Q.fetch_quotes("IREN", DAY, max_pages=len(ws))                         # 1 page per window
    U = lambda t: pd.Timestamp(t, unit="ns", tz="UTC")  # noqa: E731
    cov = df.attrs["covered"]
    assert df.attrs["truncated"] is True
    assert cov[0] == (U(ws[0][0]), U(dense[49]["sip_timestamp"] + 1))         # capped 09:30 window
    assert cov[1] == (ts_at(10, 0, 9), U(ws[2][1]))                            # 09:45 adds nothing; 10:00 from 10:00:09
    out = Q.quote_rule_sides(_tr([(ts_at(10, 0, 7), 10.04, 100, 10)]), df, fallback_sides=[-1])
    assert out["n_uncovered"] == 1 and out["sides"] == [-1]           # NOT read against the 09:30 tail quote


def test_NEGATIVE_a_page_of_only_degenerate_quotes_is_a_zero_row_page(env, monkeypatch):
    ws = MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)
    bad = [_q(t, 10.05, 10.05 - (i % 2) * 0.01) for i, t in enumerate(range(ws[3][0] + NS, ws[3][1], 60 * NS))]
    rows = _quotes_without(quote_rows(), *ws[3]) + bad                 # window 3: locked / crossed only
    holder = {}
    real = Q.fetch_windowed

    def spy(*a, **k):
        holder["r"] = real(*a, **k)
        return holder["r"]
    monkeypatch.setattr(Q, "fetch_windowed", spy)
    env.install(FakeMassive(quotes=rows))
    df = Q.fetch_quotes("IREN", DAY)
    U = lambda t: pd.Timestamp(t, unit="ns", tz="UTC")  # noqa: E731
    w3 = holder["r"].windows[3]
    assert w3.status == "ok" and w3.n_rows == 0 and w3.frames == [] and w3.first_ts_ns is None
    assert df.attrs["covered"] == [(U(g), U(e)) for g, e in ws]        # as for a complete empty window

    env.install(FakeMassive(quotes=rows, status_for=lambda k, w, p: 500 if w == 2 else 200))
    df = Q.fetch_quotes("IREN", DAY)
    cov = df.attrs["covered"]
    b_first = min(r["sip_timestamp"] for r in rows if ws[4][0] <= r["sip_timestamp"] < ws[4][1])
    assert all(c[0] != U(ws[3][0]) for c in cov) and (U(b_first), U(ws[4][1])) in cov   # after a gap: nothing


# ── D11: pages are compacted as they arrive ──────────────────────────────────
def test_NEGATIVE_fetch_windowed_requires_compact():
    with pytest.raises(TypeError):
        MP.fetch_windowed("u", "k", windows=[(0, 1)], limit=1, timeout=1, pages_per_window=1)
    with pytest.raises(TypeError):
        MP.fetch_windowed("u", "k", windows=[(0, 1)], limit=1, timeout=1, pages_per_window=1, compact=None)


def test_windows_hold_compacted_frames_never_the_raw_dicts(env):
    env.install(FakeMassive(trade_rows(), quote_rows(), page_size=50))
    seen = {}
    real = MP.fetch_windowed

    def spy(*a, **k):
        r = real(*a, **k)
        seen.setdefault(k["label"].split()[0], r)
        return r
    env.monkeypatch.setattr(TP, "fetch_windowed", spy)
    env.monkeypatch.setattr(Q, "fetch_windowed", spy)
    TP.fetch_trades("IREN", DAY)
    Q.fetch_quotes("IREN", DAY)
    for label, cols in (("tape", {"sip_timestamp", "participant_timestamp", "price", "size", "exchange", "kind"}),
                        ("nbbo", {"sip_timestamp", "bid_price", "ask_price"})):
        r = seen[label]
        assert not hasattr(r, "rows") and all(not hasattr(w, "rows") for w in r.windows)
        assert r.frames and all(isinstance(f, pd.DataFrame) for f in r.frames)
        assert all(set(f.columns) == cols for f in r.frames), label
        assert r.n_rows == sum(len(f) for f in r.frames)
        for w in r.windows:
            if w.n_rows:
                ts = [int(t) for f in w.frames for t in f["sip_timestamp"]]
                assert (w.first_ts_ns, w.last_ts_ns) == (min(ts), max(ts))


# ── 6. 429s per window (tape_control's max_429) ──────────────────────────────
def test_NEGATIVE_a_429_storm_in_one_window_stops_the_pull(env, monkeypatch):
    events = []

    class RecEvent(threading.Event):
        def __init__(self):
            super().__init__()
            events.append(self)

        def set(self):
            super().set()
            gate.set()
    gate = threading.Event()
    monkeypatch.setattr(MP, "threading", types.SimpleNamespace(Event=RecEvent))

    def on_call(kind, widx, page):
        if widx != 0 and page == 0:
            assert gate.wait(10), "the stop was never set"

    max_429 = 3
    fake = env.install(FakeMassive(trade_rows(), page_size=5, on_call=on_call,
                                   status_for=lambda k, w, p: 429 if w == 0 else 200,
                                   stop_ref=lambda: events[-1] if events else None))
    holder = {}
    real = TP.fetch_windowed

    def spy(*a, **k):
        holder["r"] = real(*a, **k)
        return holder["r"]
    monkeypatch.setattr(TP, "fetch_windowed", spy)

    assert TP.fetch_trades("IREN", DAY, max_429=max_429) is None
    assert TP.last_fetch_fault() == "rate_limited"
    res = holder["r"]
    assert res.fault == "rate_limited"
    assert len(fake.calls_for(widx=0)) == max_429 + 1 and len(env.sleeps) == max_429
    assert res.windows[0].status == "rate_limited" and res.windows[0].n_429 == max_429 + 1
    assert all(w.status in ("ok", "stopped") for w in res.windows[1:])
    assert any(w.status == "stopped" for w in res.windows[1:])
    assert not any(c["stop_set"] for c in fake.calls)       # nobody requested after the stop
    assert all(len(fake.calls_for(widx=i)) <= 1 for i in range(1, 13))

    seen = []
    t = threading.Thread(target=lambda: seen.append(TP.last_fetch_fault()))
    t.start(); t.join()
    assert seen == [None]                                    # the thread-local is the caller's only


def test_NEGATIVE_a_fresh_pull_clears_the_fault(env):
    env.install(FakeMassive(trade_rows(), status_for=lambda k, w, p: 429 if w == 5 else 200))
    assert TP.fetch_trades("IREN", DAY, max_429=0) is None and TP.last_fetch_fault() == "rate_limited"
    env.install(FakeMassive(trade_rows()))
    assert TP.fetch_trades("IREN", DAY, max_429=0) is not None and TP.last_fetch_fault() is None


# ── 7. the default path retries 429 without a cap ────────────────────────────
def test_the_default_path_retries_429_in_two_windows_uncapped(env):
    rows = trade_rows()
    env.install(FakeMassive(rows, n429_per_window={2: 5, 9: 5}))
    df = TP.fetch_trades("IREN", DAY)
    assert df is not None and len(df) == len(rows)
    assert len(env.sleeps) == 10 and set(env.sleeps) == {MP.RETRY_429_SLEEP_SEC}
    assert TP.last_fetch_fault() is None


# ── 8. D7 error semantics ────────────────────────────────────────────────────
def test_NEGATIVE_a_trades_window_500_makes_the_pull_None(env):
    env.install(FakeMassive(trade_rows(), status_for=lambda k, w, p: 500 if w == 6 else 200))
    assert TP.fetch_trades("IREN", DAY) is None
    assert TP.last_fetch_fault() is None


def test_NEGATIVE_a_trades_window_exception_makes_the_pull_None_and_logs_no_key(env, caplog):
    caplog.set_level(logging.WARNING)
    secret = "SECRETKEY123abc"
    env.install(FakeMassive(trade_rows(), key=secret,
                            status_for=lambda k, w, p: "raise" if w == 4 else 200))
    assert TP.fetch_trades("IREN", DAY) is None
    assert caplog.records and secret not in caplog.text


def test_a_quotes_window_500_keeps_the_other_windows(env):
    rows = quote_rows()
    env.install(FakeMassive(quotes=rows, status_for=lambda k, w, p: 500 if w == 5 else 200))
    df = Q.fetch_quotes("IREN", DAY)
    ws = MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)
    assert df is not None and df.attrs["truncated"] is False
    assert len(df.attrs["covered"]) == len(ws) - 1
    bad = (pd.Timestamp(ws[5][0], unit="ns", tz="UTC"), pd.Timestamp(ws[5][1], unit="ns", tz="UTC"))
    assert bad not in df.attrs["covered"]
    assert not ((df.index >= bad[0]) & (df.index < bad[1])).any()
    assert len(df) == sum(1 for r in rows if not ws[5][0] <= r["sip_timestamp"] < ws[5][1])


def test_a_quotes_window_failing_mid_way_is_covered_up_to_what_it_held(env):
    rows = quote_rows()
    env.install(FakeMassive(quotes=rows, page_size=20,
                            status_for=lambda k, w, p: 500 if (w == 5 and p == 1) else 200))
    df = Q.fetch_quotes("IREN", DAY)
    ws = MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)
    held = [r["sip_timestamp"] for r in rows if ws[5][0] <= r["sip_timestamp"] < ws[5][1]][:20]
    cov = df.attrs["covered"]
    assert len(cov) == len(ws) and df.attrs["truncated"] is False
    assert cov[5] == (pd.Timestamp(ws[5][0], unit="ns", tz="UTC"), pd.Timestamp(held[-1] + 1, unit="ns", tz="UTC"))


# ── 9. max_pages is a TOTAL budget ───────────────────────────────────────────
def test_max_pages_is_a_total_budget_spread_over_the_windows(env):
    fake = env.install(FakeMassive(quotes=quote_rows(), page_size=5))
    df = Q.fetch_quotes("IREN", DAY, max_pages=4)
    assert max(1, math.ceil(4 / Q.N_SESSION_WINDOWS)) == 1
    n = Q.N_SESSION_WINDOWS
    assert len(fake.calls) == n and {c["page"] for c in fake.calls} == {0}
    assert df.attrs["truncated"] is True
    assert len(df) == n * 5


# ── 10. covered_mask ─────────────────────────────────────────────────────────
def test_covered_mask_inside_and_outside_the_spans():
    q = pd.DataFrame({"bid": [9.99, 9.99], "ask": [10.01, 10.01]},
                     index=pd.DatetimeIndex([ts_at(9, 31), ts_at(11, 0)], name="ts_utc"))
    q.attrs["covered"] = [(ts_at(10, 30), ts_at(16, 0)), (ts_at(9, 30), ts_at(10, 0))]
    ts = pd.Series([ts_at(9, 29, 59), ts_at(9, 30), ts_at(9, 59, 59), ts_at(10, 0), ts_at(10, 15),
                    ts_at(10, 30), ts_at(15, 59, 59), ts_at(16, 0), ts_at(16, 30)])
    assert covered_list(ts, q) == [False, True, True, False, False, True, True, False, False]
    assert covered_list(pd.DatetimeIndex(ts), q) == covered_list(ts, q)


def covered_list(ts, q):
    out = Q.covered_mask(ts, q)
    assert isinstance(out, np.ndarray) and out.dtype == bool
    return out.tolist()


def test_a_frame_without_the_covered_attr_is_unrestricted_legacy():
    q = pd.DataFrame({"bid": [9.99, 9.99], "ask": [10.01, 10.01]},
                     index=pd.DatetimeIndex([ts_at(10, 0), ts_at(11, 0)], name="ts_utc"))
    ts = pd.Series([ts_at(9, 59), ts_at(10, 0), ts_at(10, 30), ts_at(11, 0), ts_at(16, 30)])
    assert covered_list(ts, q) == [True] * 5                 # no provenance → no restriction (D5 amended)
    q.attrs["covered"] = "not a list"
    assert covered_list(ts, q) == [True] * 5


def test_NEGATIVE_an_empty_covered_list_covers_nothing():
    q = pd.DataFrame({"bid": [9.99], "ask": [10.01]},
                     index=pd.DatetimeIndex([ts_at(10, 0)], name="ts_utc"))
    q.attrs["covered"] = []
    ts = pd.Series([ts_at(9, 59), ts_at(10, 0), ts_at(10, 30)])
    assert covered_list(ts, q) == [False] * 3
    assert covered_list(ts, None) == [False] * 3
    out = Q.quote_rule_sides(_tr([(ts_at(10, 30), 10.01, 100, 10)]), q, fallback_sides=[-1])
    assert out["sides"] == [-1] and out["n_uncovered"] == 1 and out["coverage_pct"] == 0.0


# ── 11. quote_rule_sides classifies inside covered windows only ──────────────
def _tr(rows):
    df = pd.DataFrame(rows, columns=["ts_utc", "price", "size", "exchange"])
    return df.set_index("ts_utc")


def _qt(rows, covered=None):
    df = pd.DataFrame(rows, columns=["ts_utc", "bid", "ask"]).set_index("ts_utc")
    if covered is not None:
        df.attrs["covered"] = covered
    return df


def test_NEGATIVE_a_print_in_a_gap_is_not_classified_by_the_stale_quote():
    quotes = _qt([(ts_at(9, 59), 9.98, 10.00), (ts_at(10, 31), 9.98, 10.00)],
                 covered=[(ts_at(9, 30), ts_at(10, 0)), (ts_at(10, 30), ts_at(16, 0))])
    trades = _tr([(ts_at(9, 59, 30), 10.00, 100, 10), (ts_at(10, 15), 10.00, 100, 10),
                  (ts_at(10, 32), 10.00, 100, 10)])
    out = Q.quote_rule_sides(trades, quotes, fallback_sides=[-1, -1, -1])
    assert out["sides"] == [1, -1, 1]                        # 10:15 keeps the tick side
    assert out["n_uncovered"] == 1 and out["n_fallback"] == 1
    assert out["n_quote_classified"] == 2 and out["n_at_mid"] == 0
    left = pd.merge_asof(trades.reset_index()[["ts_utc"]], quotes.reset_index(), on="ts_utc")
    assert not left["bid"].isna().any()                      # merge_asof DID find a (stale) quote


def test_NEGATIVE_an_after_hours_print_falls_back_against_a_session_frame():
    quotes = _qt([(ts_at(15, 59, 59), 9.98, 10.00)], covered=[(ts_at(9, 30), ts_at(16, 0))])
    trades = _tr([(ts_at(15, 59, 59.5), 10.00, 100, 10), (ts_at(16, 30), 10.00, 100, 10)])
    out = Q.quote_rule_sides(trades, quotes, fallback_sides=[-1, -1])
    assert out["sides"] == [1, -1]
    assert out["n_uncovered"] == 1 and out["coverage_pct"] == 50.0


def test_NEGATIVE_an_attr_less_frame_still_falls_back_before_its_first_quote():
    quotes = _qt([(ts_at(10, 0), 9.98, 10.00)])               # no `covered` attr: legacy
    trades = _tr([(ts_at(9, 59), 10.00, 100, 10), (ts_at(16, 30), 10.00, 100, 10)])
    out = Q.quote_rule_sides(trades, quotes, fallback_sides=[-1, -1])
    assert out["sides"] == [-1, 1]                            # 09:59 has no prior quote → tick; 16:30 legacy merge
    # CHANGED 2026-10-18 (DECISIONS14 D10): a print before the first quote is uncovered (was n_uncovered == 0)
    assert out["n_fallback"] == 1 and out["n_uncovered"] == 1 and out["coverage_pct"] == 50.0
    assert out == _reference_quote_rule_sides_d10(trades, quotes, [-1, -1])


def test_an_untruncated_rth_tape_matches_the_d10_reference():
    """quote_rule_sides on an untruncated RTH tape equals the independent D10 reference (renamed 2026-10-18,
    critic LOW: the reference is not the pre-change code any more)."""
    rng = np.random.default_rng(7)
    qts = [ts_at(9, 30, 1) + pd.Timedelta(seconds=10 * i) for i in range(2000)]
    mid = 10 + np.cumsum(rng.normal(0, 0.002, len(qts)))
    quotes = _qt([(t, round(m - 0.01, 2), round(m + 0.01, 2)) for t, m in zip(qts, mid)],
                 covered=[(pd.Timestamp(g, unit="ns", tz="UTC"), pd.Timestamp(e, unit="ns", tz="UTC"))
                          for g, e in MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END)])
    tts = [ts_at(9, 30, 5) + pd.Timedelta(seconds=7 * i) for i in range(3000)]
    tm = 10 + np.cumsum(rng.normal(0, 0.002, len(tts)))
    trades = _tr([(t, round(p + rng.choice([-0.01, 0, 0.01]), 3), 100, 10) for t, p in zip(tts, tm)])
    assert trades.index.max() < ts_at(16, 0)
    tick = TP.tick_rule_sides(trades["price"].tolist())
    new = Q.quote_rule_sides(trades, quotes, fallback_sides=tick)
    old = _reference_quote_rule_sides_d10(trades, quotes, tick)
    # CHANGED 2026-10-18 (DECISIONS14 D10): the reference now carries n_uncovered and the D10 coverage
    assert new["n_uncovered"] == 0 and new == old
    assert new["n_at_mid"] > 0 and new["coverage_pct"] == 100.0     # at-mid prints never lower coverage
    no_attr = quotes.copy()
    no_attr.attrs = {}
    inner = trades[(trades.index >= quotes.index.min()) & (trades.index <= quotes.index.max())]
    t2 = TP.tick_rule_sides(inner["price"].tolist())
    new2 = Q.quote_rule_sides(inner, no_attr, fallback_sides=t2)
    # CHANGED 2026-10-18 (DECISIONS14 D10): compared whole, n_uncovered included
    assert new2["n_uncovered"] == 0 and new2 == _reference_quote_rule_sides_d10(inner, no_attr, t2)


def test_coverage_counts_held_quotes_not_decided_prints():
    quotes = _qt([(ts_at(10, 0), 10.00, 10.06)], covered=[(ts_at(9, 30), ts_at(16, 0))])
    trades = _tr([(ts_at(10, 1), 10.06, 100, 10),          # held, at the ask → +1 from the quote
                  (ts_at(10, 2), 10.03, 100, 10),          # held, exactly at mid → tick side
                  (ts_at(16, 30), 10.06, 100, 10)])        # after hours, outside covered → tick side
    out = Q.quote_rule_sides(trades, quotes, fallback_sides=[-1, -1, -1])
    assert out["sides"] == [1, -1, -1]
    assert out["coverage_pct"] == 66.7
    assert (out["n_quote_classified"], out["n_at_mid"], out["n_uncovered"], out["n_fallback"]) == (1, 1, 1, 2)
    # 66.7 >= MIN_USEFUL_COVERAGE_PCT (60) → "quote" by the D10 threshold rule
    assert out["coverage_pct"] >= Q.MIN_USEFUL_COVERAGE_PCT
    assert out["method"] == "quote" and out["trustworthy"] is True


def test_NEGATIVE_an_at_mid_print_never_lowers_coverage():
    quotes = _qt([(ts_at(10, 0), 10.00, 10.06)], covered=[(ts_at(9, 30), ts_at(16, 0))])
    off = _tr([(ts_at(10, 1), 10.06, 100, 10), (ts_at(10, 2), 10.00, 100, 10)])
    mid = _tr([(ts_at(10, 1), 10.03, 100, 10), (ts_at(10, 2), 10.03, 100, 10)])
    a = Q.quote_rule_sides(off, quotes, fallback_sides=[1, 1])
    b = Q.quote_rule_sides(mid, quotes, fallback_sides=[1, 1])
    assert a["coverage_pct"] == b["coverage_pct"] == 100.0
    assert b["n_at_mid"] == 2 and b["n_quote_classified"] == 0 and b["n_uncovered"] == 0
    assert b["method"] == "quote" and b["trustworthy"] is True
    assert b["sides"] == [1, 1]                              # the side still comes from the tick rule


def test_NEGATIVE_a_degenerate_quote_is_not_a_quote_we_hold():
    """critic MED on D10: a zero / locked / crossed prevailing quote is uncovered, never 'at mid'."""
    t0 = pd.Timestamp(0, unit="s", tz="UTC")
    S = lambda sec: t0 + pd.Timedelta(seconds=sec)  # noqa: E731
    quotes = _qt([(S(100), 10.00, 10.00), (S(300), 10.05, 10.00), (S(500), 0.0, 10.04)],
                 covered=[(S(0), S(2000))])
    trades = _tr([(S(150), 10.00, 100, 10), (S(350), 10.02, 100, 10), (S(550), 10.02, 100, 10),
                  (S(600), 10.03, 100, 10)])
    out = Q.quote_rule_sides(trades, quotes, fallback_sides=[1, -1, 1, -1])
    assert out["coverage_pct"] == 0.0 and out["n_at_mid"] == 0 and out["n_uncovered"] == 4
    assert out["method"] == "mixed" and out["trustworthy"] is False
    assert out["sides"] == [1, -1, 1, -1]                     # sides unchanged: the fallback side
    assert out["n_fallback"] == 4 and out["n_quote_classified"] == 0


def test_pre_d10_counts_and_sides_are_unchanged_by_d10():
    # coverage_pct / method / trustworthy are EXCLUDED here: D10 changed their definition on purpose
    # (held quotes / n, not quote-classified / n); n_uncovered too (D10 now counts pre-quote prints).
    quotes = _qt([(ts_at(10, 0), 10.00, 10.06), (ts_at(10, 31), 10.00, 10.04)],
                 covered=[(ts_at(9, 30), ts_at(10, 15)), (ts_at(10, 30), ts_at(16, 0))])
    trades = _tr([(ts_at(9, 45), 10.03, 100, 10),             # pre-quote
                  (ts_at(10, 1), 10.06, 100, 10),             # off-mid (at the ask)
                  (ts_at(10, 2), 10.03, 100, 10),             # at mid
                  (ts_at(10, 20), 10.06, 100, 10),            # uncovered gap
                  (ts_at(10, 32), 10.02, 100, 10),            # at mid
                  (ts_at(10, 33), 10.00, 100, 10)])           # off-mid (at the bid)
    fb = [1, -1, 1, -1, -1, 1]
    new, pre = Q.quote_rule_sides(trades, quotes, fb), _pre_d10_quote_rule_sides(trades, quotes, fb)
    for k in ("sides", "n_quote_classified", "n_at_mid", "n_fallback"):
        assert new[k] == pre[k], k
    assert (new["n_at_mid"], new["n_quote_classified"]) == (2, 2)


# ── 12. retail.identify signs only covered prints ────────────────────────────
def test_NEGATIVE_retail_prints_outside_covered_are_not_signed():
    quotes = _qt([(ts_at(9, 59), 10.00, 10.006), (ts_at(10, 31), 10.00, 10.006)],
                 covered=[(ts_at(9, 30), ts_at(10, 0)), (ts_at(10, 30), ts_at(16, 0))])
    trades = _tr([(ts_at(9, 59, 30), 10.0034, 500, 4),      # inside, above mid 10.003 → buy
                  (ts_at(10, 15), 10.0024, 700, 4),         # gap → NOT signed
                  (ts_at(10, 32), 10.0024, 300, 4)])        # inside, below mid → sell
    out = R.identify(trades, quotes)
    assert out["signed"] is True and out["retail_trades"] == 3
    assert out["buy_shares"] == 500 and out["sell_shares"] == 300


def test_NEGATIVE_retail_with_every_print_uncovered_says_no_quote_matched():
    quotes = _qt([(ts_at(9, 59), 10.00, 10.006)], covered=[(ts_at(9, 30), ts_at(10, 0))])
    out = R.identify(_tr([(ts_at(16, 30), 10.0034, 500, 4)]), quotes)
    assert out["signed"] is False and out["buy_shares"] is None
    assert "no quote matched" in out["read"]


# ── 13. pins ─────────────────────────────────────────────────────────────────
def test_constants_are_pinned():
    assert MP.FETCH_WORKERS == 8
    # CHANGED 2026-10-18 (DECISIONS14 D12): was 2 / 26 and 4 / 44
    assert TP.TRADE_PAGES_PER_WINDOW == 24 and TP.MAX_TRADE_PAGES == 312
    assert Q.QUOTE_PAGES_PER_WINDOW == 8
    assert Q.MAX_QUOTE_PAGES == Q.QUOTE_PAGES_PER_WINDOW * Q.N_SESSION_WINDOWS
    assert Q.N_SESSION_WINDOWS == len(MP.windows_for(DAY, Q.SESSION_START, Q.SESSION_END))
    assert Q.N_SESSION_WINDOWS == 11 and Q.MAX_QUOTE_PAGES == 88      # 12 edges inside 09:30–16:00 bound 11 windows
    assert len(MP.WINDOW_EDGES_ET) == 14
    assert MP.WINDOW_EDGES_ET[0] == "04:00" and MP.WINDOW_EDGES_ET[-1] == "20:00"
    assert list(MP.WINDOW_EDGES_ET) == sorted(MP.WINDOW_EDGES_ET)
    assert TP.WINDOW_EDGES_ET is MP.WINDOW_EDGES_ET


def _statement_text(path, name):
    src = (BACKEND / path).read_text()
    toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    for i, t in enumerate(toks):
        if t.type == tokenize.NAME and t.string == name and t.start[1] == 0 and toks[i + 1].string == "=":
            line0 = t.start[0]
            j = i
            while toks[j].type != tokenize.NEWLINE:
                j += 1
            return "\n".join(src.splitlines()[line0 - 1:toks[j].start[0]])
    raise AssertionError(f"{name} not assigned at module level in {path}")


@pytest.mark.parametrize("path,name", [
    ("orderflow/massive_pages.py", "WINDOW_EDGES_ET"),
    ("orderflow/massive_pages.py", "FETCH_WORKERS"),
    ("orderflow/tape.py", "TRADE_PAGES_PER_WINDOW"),
    ("orderflow/tape.py", "MAX_TRADE_PAGES"),
    ("orderflow/quotes.py", "QUOTE_PAGES_PER_WINDOW"),
    ("orderflow/quotes.py", "N_SESSION_WINDOWS"),
    ("orderflow/quotes.py", "MAX_QUOTE_PAGES"),
])
def test_every_new_constant_carries_its_MINE_tag(path, name):
    # CHANGED 2026-10-18 (DECISIONS14 D12): two-digit decision numbers (D12) match too
    assert re.search(r"# MINE \(DECISIONS14 D\d+\)", _statement_text(path, name)), (path, name)


def test_SOURCE_GUARD_the_fetchers_no_longer_page_serially():
    import inspect
    for fn in (TP.fetch_trades, Q.fetch_quotes):
        src = inspect.getsource(fn)
        assert "fetch_windowed(" in src and "while next_url" not in src
    assert "covered_mask(" in inspect.getsource(Q.quote_rule_sides)
    assert "covered_mask(" in inspect.getsource(R.identify)
