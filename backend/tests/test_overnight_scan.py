"""🌙 overnight.scan — the overnight-session engine (BUILD_SPEC16 §3.2–3.3 +
AMENDMENTS16 A1, WP-A).

Price rule (A1): the live quote midpoint when fresh (≤ QUOTE_FRESH_SEC) and
tight (≤ QUOTE_SPREAD_MAX), else the delayed indicative trade if it printed this
session, else dropped. Base = the Massive snapshot's regular close, pinned once.
Hermetic: `requests.get`, `sepa.prices.market_snapshot_with_meta` and
`sepa.levered_etf.fetch_reference` are faked; collections are in memory.
NEGATIVE cases throughout."""
from __future__ import annotations

import copy
import json
import logging
import math
from datetime import date, datetime, timedelta, timezone

import pytest
import requests

from overnight import scan
from overnight import session as S

ET = S.ET
NOW = datetime(2026, 10, 19, 1, 3, tzinfo=ET)          # Mon 01:03 ET = 05:03 UTC
SECRET = "PKTESTSECRET0123456789"


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------
class Cursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, key, direction=1):
        self.docs.sort(key=lambda d: d.get(key), reverse=direction < 0)
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    def __iter__(self):
        return iter(self.docs)


class Coll:
    def __init__(self):
        self.docs: dict = {}

    @staticmethod
    def _match(d, q):
        for k, v in (q or {}).items():
            if isinstance(v, dict) and "$nin" in v:
                if d.get(k) in v["$nin"]:
                    return False
            elif d.get(k) != v:
                return False
        return True

    def find(self, q=None, proj=None):
        return Cursor(copy.deepcopy(d) for d in self.docs.values() if self._match(d, q))

    def find_one(self, q):
        for d in self.docs.values():
            if self._match(d, q):
                return copy.deepcopy(d)
        return None

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = copy.deepcopy(doc)

    def insert_one(self, doc):
        self.docs[doc["_id"]] = copy.deepcopy(doc)

    def delete_many(self, q):
        for k in [k for k, d in self.docs.items() if self._match(d, q)]:
            del self.docs[k]

    def create_index(self, *a, **k):
        return None


class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._body


def iso_z(dt: datetime) -> str:
    """Alpaca's shape: UTC, nine fraction digits, 'Z'."""
    u = dt.astimezone(timezone.utc)
    return u.strftime("%Y-%m-%dT%H:%M:%S") + ".123456789Z"


def snap(*, trade_p=None, trade_t=None, bp=None, ap=None, quote_t=None,
         bar_t="2026-10-19T00:00:00Z", v=1000, vw=None, c=None, n=10):
    s = {}
    if trade_p is not None:
        s["latestTrade"] = {"p": trade_p, "t": iso_z(trade_t), "c": ["@"], "x": "B"}
    if bp is not None or ap is not None:
        s["latestQuote"] = {"bp": bp, "ap": ap, "t": iso_z(quote_t)}
    if bar_t is not None:
        s["dailyBar"] = {"t": bar_t, "v": v, "vw": vw, "c": c, "n": n, "o": 1, "h": 1, "l": 1}
    return s


SESS = S.session_for(NOW)
BASE_ROW = {"c": 100.0, "v": 1_000_000.0, "pc": 98.0, "t": "CS", "n": "Acme Corp", "lev": False, "ll": None}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    from market_hours import gate
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    monkeypatch.setenv("ALPACA_KEY_ID", SECRET)
    monkeypatch.setenv("ALPACA_SECRET_KEY", SECRET + "S")

    def _no_http(*a, **k):
        raise AssertionError("requests.get must not be called here")
    monkeypatch.setattr(requests, "get", _no_http)


# ---------------------------------------------------------------------------
# parse_ts
# ---------------------------------------------------------------------------
def test_parse_ts_reads_nine_digit_z_on_this_python():
    t = scan.parse_ts("2026-10-19T05:02:24.704579971Z")
    assert t == datetime(2026, 10, 19, 5, 2, 24, 704579, tzinfo=timezone.utc)
    assert scan.parse_ts("2026-10-19T05:02:24Z") == datetime(2026, 10, 19, 5, 2, 24, tzinfo=timezone.utc)
    assert scan.parse_ts("2026-10-19T01:02:24.5-04:00") == datetime(2026, 10, 19, 5, 2, 24, 500000,
                                                                     tzinfo=timezone.utc)
    assert scan.parse_ts("2026-10-19T00:00:00Z").tzinfo is not None


@pytest.mark.parametrize("bad", ["", "nope", None, 123, "2026-13-45T00:00:00Z", "2026-10-19", "10/19/2026 01:00"])
def test_negative_parse_ts_garbage_is_none(bad):
    assert scan.parse_ts(bad) is None


# ---------------------------------------------------------------------------
# fund_flags
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,type_,want", [
    ("Direxion Daily Semiconductor Bull 3X Shares", "ETF", (True, "3× ETF")),
    ("Direxion Daily Semiconductor Bear 3X Shares", "ETF", (True, "−3× ETF")),
    ("ProShares UltraPro QQQ", "ETF", (True, "UltraPro ETF")),
    ("ProShares UltraPro Short QQQ", "ETF", (True, "−UltraPro ETF")),
    ("ProShares UltraShort QQQ", "ETF", (True, "−UltraShort ETF")),
    ("ProShares Short S&P500", "ETF", (True, "inverse ETF")),
    ("MicroSectors FANG+ 3X Leveraged ETNs", "ETN", (True, "3× ETN")),
    ("Tradr 2X Long IREN Daily ETF", "ETF", (True, "2× ETF")),
    ("Defiance Daily Target 2X Long IREN ETF", "ETS", (True, "2× ETF")),
    ("Direxion Daily S&P 500 Bear 1X Shares", "ETF", (True, "inverse ETF")),
    ("SPDR S&P 500 ETF Trust", "ETF", (False, None)),
    ("iShares Short Treasury Bond ETF", "ETF", (False, None)),
    ("PIMCO Enhanced Short Maturity Active ETF", "ETF", (False, None)),
    ("Ultra Clean Holdings", "CS", (False, None)),
    ("Direxion Daily Semiconductor Bull 3X Shares", "CS", (False, None)),
    ("Direxion Daily Semiconductor Bull 3X Shares", None, (None, None)),
])
def test_fund_flags_fixtures(name, type_, want):
    assert scan.fund_flags(name, type_) == want


# CHANGED 2026-10-19 (critic findings 1–2): names off the 10-19 Massive fund list.
@pytest.mark.parametrize("name,type_,want", [
    # false NEGATIVES before — leveraged / inverse now
    ("AdvisorShares MSOS Daily Leveraged ETF", "ETS", (True, "leveraged ETF")),
    ("DB Gold Double Long ETN due February 15, 2038", "ETN", (True, "2× ETN")),
    ("DB Gold Double Short ETN due February 15, 2038", "ETN", (True, "\u22122× ETN")),
    ("DB Gold Short ETN due February 15, 2038", "ETN", (True, "inverse ETN")),
    ("ETRACS Monthly Pay 2xLeveraged Preferred Stock ETN", "ETN", (True, "2× ETN")),
    ("ETRACS Monthly Pay 2xLeveraged US High Dividend Low Volatility ETN Series B due October 21, 2049",
     "ETN", (True, "2× ETN")),
    ("ETRACS 2xMonthly Pay Leveraged US Small Cap High Dividend ETN Series B", "ETN", (True, "2× ETN")),
    ("Leverage Shares 100% TSLA AND 100% SPCX Daily ETF", "ETF", (True, "2× ETF")),
    ("Tidal Trust II STKd 100% Bitcoin & 100% Gold ETF", "ETF", (True, "2× ETF")),
    ("IncomeSTKd 1x Bitcoin & 1x Gold Premium ETF", "ETF", (True, "2× ETF")),
    ("Defiance Leveraged Long Income MSTR ETF", "ETF", (True, "leveraged ETF")),
    ("ProShares Trust Short MSCI EAFE", "ETF", (True, "inverse ETF")),
    ("ProShares Trust Short MSCI Emerging Markets", "ETF", (True, "inverse ETF")),
    ("ProShares Trust UltraShort MSCI Japan", "ETF", (True, "\u2212UltraShort ETF")),
    ("Proshares UltraShort Technology", "ETF", (True, "\u2212UltraShort ETF")),
    ("ProShares Ultra VIX Short-Term Futures ETF", "ETF", (True, "Ultra ETF")),
    ("ProShares Trust ProShares Ultra QQQ Mega", "ETF", (True, "Ultra ETF")),
    ("YieldMax Short TSLA Option Income Strategy ETF", "ETS", (True, "inverse ETF")),
    # CHANGED 2026-10-19 (coordinator): the noun "Leverage" counts too.
    ("Miller Value Partners Leverage ETF", "ETF", (True, "leveraged ETF")),
    ("Leverage Shares MANGOS ETF", "ETF", (True, "leveraged ETF")),
    # NEGATIVE: a stated 1X multiple governs the issuer's "Leverage" word — 1× inverse, not leveraged
    ("Leverage Shares 1X Short SPCX Daily ETF", "ETF", (True, "inverse ETF")),
    ("AdvisorShares Dorsey Wright Short ETF", "ETF", (True, "inverse ETF")),
    # false POSITIVES before — plain now (NEGATIVE)
    ("JPMorgan Ultra-Short Income ETF", "ETF", (False, None)),
    ("iShares Ultra Short Duration Bond Active ETF", "ETF", (False, None)),
    ("PGIM Ultra Short Bond ETF", "ETF", (False, None)),
    ("Vanguard Ultra-Short Bond ETF", "ETF", (False, None)),
    ("Invesco Ultra Short Duration ETF", "ETF", (False, None)),
    ("Innovator U.S. Equity Ultra Buffer ETF - April", "ETF", (False, None)),
    ("Invesco S&P Ultra Dividend Revenue ETF", "ETF", (False, None)),
    ("YieldMax Ultra Option Income Strategy ETF", "ETF", (False, None)),
    ("Angel Oak UltraShort Income ETF", "ETF", (False, None)),
    ("DoubleLine Ultrashort Income ETF", "ETF", (False, None)),
    # NEGATIVE: "Short" as a duration word, a long/short fund, leveraged LOANS, a "Double" payout
    ("iShares Short Treasury Bond ETF", "ETF", (False, None)),
    ("PIMCO Enhanced Short Maturity Active ETF", "ETF", (False, None)),
    ("Bluemonte Short Term Bond ETF", "ETF", (False, None)),
    ("BNY Mellon Municipal Short Duration ETF", "ETF", (False, None)),
    ("VanEck Short Muni ETF", "ETF", (False, None)),
    ("VanEck Short High Yield Muni ETF", "ETF", (False, None)),
    ("Twin Oak Short Horizon Absolute Return ETF", "ETF", (False, None)),
    ("Vanguard Short-Term Bond ETF", "ETF", (False, None)),
    ("ProShares VIX Short-Term Futures ETF", "ETF", (False, None)),
    ("Even Herd Long Short ETF", "ETF", (False, None)),
    ("Convergence Long/Short Equity ETF", "ETF", (False, None)),
    ("State Street SPDR S&P Leveraged Loan ETF", "ETF", (False, None)),
    ("Example Senior Leverage Loans Income ETF", "ETF", (False, None)),
    ("YieldMax U.S. Stocks Target Double Distribution ETF", "ETF", (False, None)),
    ("Xtrackers MSCI EAFE 50% Hedged Equity ETF", "ETF", (False, None)),
    ("Corgi U.S. Equities 100% Structured Buffer ETF - August Series", "ETF", (False, None)),
])
def test_fund_flags_critic_fixtures(name, type_, want):
    assert scan.fund_flags(name, type_) == want


# CHANGED 2026-10-19 (coordinator): the "Ulta" misspelling, Bearish / Bullish, the ticker override.
@pytest.mark.parametrize("name,type_,want", [
    ("ProShares Ulta SmallCap600", "ETF", (True, "Ultra ETF")),
    ("Ulta Beauty, Inc. Common Stock", "CS", (False, None)),           # NEGATIVE: the retailer
    ("Ulta Beauty Income ETF", "ETF", (False, None)),                   # NEGATIVE: "Ulta" off ProShares
    ("Invesco DB US Dollar Index Bearish Fund", "ETV", (True, "inverse ETF")),
    ("Example 2X Bearish Dollar ETF", "ETF", (True, "\u22122× ETF")),
    ("Invesco DB US Dollar Index Bullish Fund", "ETV", (False, None)),  # NEGATIVE: Bullish alone
    ("WisdomTree Bloomberg U.S. Dollar Bullish Fund", "ETF", (False, None)),
    ("Example 2X Bullish Dollar ETF", "ETF", (True, "2× ETF")),
])
def test_fund_flags_ulta_bearish_bullish(name, type_, want):
    assert scan.fund_flags(name, type_) == want


def test_inverse_ticker_override_applies_to_its_ticker_only():
    name = "ProShares Decline of the Retail Store ETF"
    assert scan.INVERSE_TICKER_OVERRIDES == frozenset({"EMTY"})
    assert scan.fund_flags(name, "ETF", "EMTY") == (True, "inverse ETF")
    assert scan.fund_flags(name, "ETF", "emty") == (True, "inverse ETF")
    # NEGATIVE: the same name on another ticker, or no ticker, is read by the name rules
    assert scan.fund_flags(name, "ETF", "XMTY") == (False, None)
    assert scan.fund_flags(name, "ETF") == (False, None)
    # NEGATIVE: the override never makes a stock a fund
    assert scan.fund_flags(name, "CS", "EMTY") == (False, None)


def test_pin_base_passes_the_ticker_to_the_override(massive, monkeypatch):
    from sepa import levered_etf, prices
    rows = copy.deepcopy(SNAP_ROWS)
    rows["EMTY"] = snap_row(12.0, 1_000_000, 12.5)
    ref = copy.deepcopy(REF_ROWS)
    ref["ETF"] = ref["ETF"] + [{"ticker": "EMTY", "name": "ProShares Decline of the Retail Store ETF", "type": "ETF"}]
    monkeypatch.setattr(prices, "market_snapshot_with_meta", lambda include_otc=False: (rows, {"http": 200}))
    monkeypatch.setattr(levered_etf, "fetch_reference",
                        lambda t, *, http=None, key=None, max_pages=12: (copy.deepcopy(ref.get(t, [])), True, 1))
    doc, _ = scan.pin_base(SESS, NOW, coll=Coll())
    assert doc["rows"]["EMTY"]["lev"] is True and doc["rows"]["EMTY"]["ll"] == "inverse ETF"


def test_fund_flags_reuses_levered_etf_constants_by_name():
    from sepa import levered_etf
    src = open(scan.__file__, encoding="utf-8").read()
    for k in ("FACTOR_RE", "SHORT_WORDS", "TOKEN_STRIP", "MIN_FACTOR_EXCLUSIVE", "FUND_TYPES", "STOCK_TYPES"):
        assert f"levered_etf.{k}" in src, k
    assert levered_etf.MIN_FACTOR_EXCLUSIVE == 1.0


# ---------------------------------------------------------------------------
# build_row — A1 price rule
# ---------------------------------------------------------------------------
def test_fresh_tight_quote_prices_the_row_and_the_math_holds():
    s = snap(trade_p=104.0, trade_t=NOW - timedelta(minutes=15),
             bp=104.9, ap=105.1, quote_t=NOW - timedelta(seconds=20), v=2000, vw=104.5, n=37)
    row, why = scan.build_row("ACME", BASE_ROW, s, SESS, NOW)
    assert why is None
    assert row["src"] == "q"
    assert row["price"] == pytest.approx(105.0)
    assert row["pct"] == pytest.approx(5.0)
    assert row["prior_pct"] == pytest.approx(100 * (100 / 98 - 1))
    assert row["on_volume"] == 2000 and row["on_bar"] is True and row["on_trades"] == 37
    assert row["on_dollar"] == pytest.approx(2000 * 104.5)
    assert row["prior_dollar_vol"] == pytest.approx(100.0 * 1_000_000)
    assert row["spread_pct"] == pytest.approx(100 * 0.2 / 105.0)
    assert 19 <= row["price_age_sec"] <= 21
    assert row["base_close"] == 100.0 and row["base_date"] == "2026-10-16"
    assert row["price_time_et"] == "Mon 1:02 ET"
    assert row["price_time"].endswith("-04:00")
    assert set(row) == {"symbol", "name", "type", "base_close", "base_date", "price", "src", "price_time",
                        "price_time_et", "price_age_sec", "spread_pct", "pct", "on_volume", "on_dollar",
                        "on_trades", "on_bar", "prior_pct", "prior_dollar_vol", "leveraged", "lev_label", "ref"}


def test_negative_a_fresh_tight_quote_beats_a_stale_trade():
    s = snap(trade_p=90.0, trade_t=NOW - timedelta(minutes=16), bp=101.0, ap=101.2,
             quote_t=NOW - timedelta(seconds=5))
    row, _ = scan.build_row("ACME", BASE_ROW, s, SESS, NOW)
    assert row["src"] == "q" and row["price"] == pytest.approx(101.1)


def test_negative_a_wide_quote_falls_back_to_the_delayed_trade():
    # 2% spread > QUOTE_SPREAD_MAX 1.5%
    s = snap(trade_p=102.0, trade_t=NOW - timedelta(minutes=15), bp=99.0, ap=101.0,
             quote_t=NOW - timedelta(seconds=5))
    row, _ = scan.build_row("ACME", BASE_ROW, s, SESS, NOW)
    assert row["src"] == "t" and row["price"] == 102.0
    assert row["spread_pct"] is None
    assert 899 <= row["price_age_sec"] <= 901
    assert row["pct"] == pytest.approx(2.0)


def test_negative_a_stale_quote_falls_back_to_the_trade_at_the_boundary():
    ok = snap(bp=101.0, ap=101.2, quote_t=NOW)
    ok["latestQuote"]["t"] = (NOW - timedelta(seconds=scan.QUOTE_FRESH_SEC)).astimezone(timezone.utc) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")                     # exactly QUOTE_FRESH_SEC old: still prices
    row, _ = scan.build_row("ACME", BASE_ROW, ok, SESS, NOW)
    assert row["src"] == "q" and row["price_age_sec"] == scan.QUOTE_FRESH_SEC
    late = snap(trade_p=99.0, trade_t=NOW - timedelta(minutes=20), bp=101.0, ap=101.2,
                quote_t=NOW - timedelta(seconds=scan.QUOTE_FRESH_SEC + 1))
    row, _ = scan.build_row("ACME", BASE_ROW, late, SESS, NOW)
    assert row["src"] == "t" and row["price"] == 99.0


def test_negative_a_crossed_or_zero_quote_never_prices():
    crossed = snap(bp=101.2, ap=101.0, quote_t=NOW - timedelta(seconds=5))
    assert scan.build_row("ACME", BASE_ROW, crossed, SESS, NOW) == (None, "no_price")
    locked = snap(bp=101.0, ap=101.0, quote_t=NOW - timedelta(seconds=5))
    assert scan.build_row("ACME", BASE_ROW, locked, SESS, NOW) == (None, "no_price")
    zero = snap(bp=0, ap=101.0, quote_t=NOW - timedelta(seconds=5))
    assert scan.build_row("ACME", BASE_ROW, zero, SESS, NOW) == (None, "no_price")
    crossed_with_trade = snap(trade_p=100.5, trade_t=NOW - timedelta(minutes=15), bp=101.2, ap=101.0,
                              quote_t=NOW - timedelta(seconds=5))
    row, _ = scan.build_row("ACME", BASE_ROW, crossed_with_trade, SESS, NOW)
    assert row["src"] == "t" and row["price"] == 100.5


def test_negative_stale_trade_and_stale_quote_drop_the_row():
    before_open = SESS["opens_at"] - timedelta(minutes=5)
    s = snap(trade_p=101.0, trade_t=before_open, bp=101.0, ap=101.2, quote_t=before_open)
    assert scan.build_row("ACME", BASE_ROW, s, SESS, NOW) == (None, "no_price")
    # a quote this session but too old, and a trade from before the session
    s2 = snap(trade_p=101.0, trade_t=before_open, bp=101.0, ap=101.2,
              quote_t=NOW - timedelta(minutes=30))
    assert scan.build_row("ACME", BASE_ROW, s2, SESS, NOW) == (None, "no_price")


def test_negative_no_base_close_and_no_snapshot():
    s = snap(bp=101.0, ap=101.2, quote_t=NOW)
    assert scan.build_row("ACME", None, s, SESS, NOW) == (None, "no_base")
    assert scan.build_row("ACME", {**BASE_ROW, "c": 0}, s, SESS, NOW) == (None, "no_base")
    assert scan.build_row("ACME", {**BASE_ROW, "c": float("nan")}, s, SESS, NOW) == (None, "no_base")
    assert scan.build_row("ACME", BASE_ROW, None, SESS, NOW) == (None, "not_on_feed")
    assert scan.build_row("ACME", BASE_ROW, {}, SESS, NOW) == (None, "not_on_feed")


def test_negative_a_daily_bar_of_another_date_carries_no_overnight_volume():
    s = snap(bp=101.0, ap=101.2, quote_t=NOW, bar_t="2026-10-16T00:00:00Z", v=5000, vw=100.0, n=9)
    row, _ = scan.build_row("ACME", BASE_ROW, s, SESS, NOW)
    assert row["on_bar"] is False
    assert row["on_volume"] == 0 and row["on_dollar"] == 0 and row["on_trades"] == 0


def test_on_dollar_falls_back_to_the_bar_close_then_the_price():
    s = snap(bp=101.0, ap=101.2, quote_t=NOW, v=100, vw=None, c=50.0)
    assert scan.build_row("ACME", BASE_ROW, s, SESS, NOW)[0]["on_dollar"] == pytest.approx(5000.0)
    s = snap(bp=101.0, ap=101.2, quote_t=NOW, v=100, vw=float("nan"), c=None)
    assert scan.build_row("ACME", BASE_ROW, s, SESS, NOW)[0]["on_dollar"] == pytest.approx(100 * 101.1)


def test_negative_nan_anywhere_is_none_and_the_row_serializes():
    b = {**BASE_ROW, "v": float("nan"), "pc": float("inf")}
    s = snap(bp=101.0, ap=101.2, quote_t=NOW, v=float("nan"), vw=float("nan"))
    row, _ = scan.build_row("ACME", b, s, SESS, NOW)
    assert row["prior_pct"] is None and row["prior_dollar_vol"] is None
    assert row["on_volume"] == 0 and row["on_dollar"] == 0
    json.dumps(row, allow_nan=False)
    nan_trade = snap(trade_p=float("nan"), trade_t=NOW - timedelta(minutes=15))
    assert scan.build_row("ACME", BASE_ROW, nan_trade, SESS, NOW) == (None, "no_price")


# ---------------------------------------------------------------------------
# alpaca_snapshots
# ---------------------------------------------------------------------------
def _ok_body(params):
    return {w: snap(bp=10.0, ap=10.02, quote_t=NOW) for w in params["symbols"].split(",")}


def test_450_symbols_go_in_calls_of_200_200_50_with_the_headers_and_feed(monkeypatch):
    seen = []

    def fake(url, params=None, headers=None, timeout=None):
        seen.append((url, dict(params), dict(headers), timeout))
        return Resp(200, _ok_body(params))
    monkeypatch.setattr(requests, "get", fake)
    syms = [f"S{i:04d}" for i in range(450)]
    out, st = scan.alpaca_snapshots(syms, t0=scan._clock())
    assert [len(p["symbols"].split(",")) for _, p, _, _ in seen] == [200, 200, 50]
    assert all(u == scan.SNAPSHOTS_URL == "https://data.alpaca.markets/v2/stocks/snapshots" for u, *_ in seen)
    assert all(p["feed"] == "overnight" == scan.FEED for _, p, _, _ in seen)
    assert all(h["APCA-API-KEY-ID"] == SECRET and h["APCA-API-SECRET-KEY"] == SECRET + "S" for _, _, h, _ in seen)
    assert all(t == scan.ALPACA_TIMEOUT_SEC for *_, t in seen)
    assert len(out) == 450 and st["calls"] == 3 and st["batches"] == 3 and st["batches_failed"] == 0


def test_class_share_goes_out_dotted_and_comes_back_dashed_and_unasked_keys_drop(monkeypatch):
    def fake(url, params=None, headers=None, timeout=None):
        assert params["symbols"] == "BRK.B,AAPL"
        return Resp(200, {"BRK.B": snap(bp=1, ap=1.01, quote_t=NOW), "AAPL": snap(bp=1, ap=1.01, quote_t=NOW),
                          "ZZZZ": snap(bp=1, ap=1.01, quote_t=NOW)})
    monkeypatch.setattr(requests, "get", fake)
    out, _ = scan.alpaca_snapshots(["BRK-B", "AAPL"], t0=scan._clock())
    assert set(out) == {"BRK-B", "AAPL"}


def test_429_retries_exactly_once_then_uses_the_200(monkeypatch):
    calls, slept = [], []

    def fake(url, params=None, headers=None, timeout=None):
        calls.append(1)
        return Resp(429) if len(calls) == 1 else Resp(200, _ok_body(params))
    monkeypatch.setattr(requests, "get", fake)
    out, st = scan.alpaca_snapshots(["AAA", "BBB"], t0=scan._clock(), sleep=slept.append)
    assert len(calls) == 2 and st["retries"] == 1 and st["calls"] == 2
    assert slept == [scan.RETRY_SLEEP_SEC]
    assert set(out) == {"AAA", "BBB"} and st["batches_failed"] == 0


def test_retry_after_is_honored_and_capped(monkeypatch):
    for hdr, want in (("2", 2.0), ("30", float(scan.RETRY_AFTER_CAP_SEC)), ("junk", float(scan.RETRY_SLEEP_SEC))):
        n = []
        slept = []

        def fake(url, params=None, headers=None, timeout=None, _h=hdr):
            n.append(1)
            return Resp(429, headers={"Retry-After": _h}) if len(n) == 1 else Resp(200, _ok_body(params))
        monkeypatch.setattr(requests, "get", fake)
        scan.alpaca_snapshots(["AAA"], t0=scan._clock(), sleep=slept.append)
        assert slept == [want], hdr
    assert scan.RETRY_AFTER_CAP_SEC == 10


def test_negative_429_twice_fails_that_batch_and_keeps_the_others(monkeypatch):
    monkeypatch.setattr(scan, "ALPACA_BATCH", 2)

    def fake(url, params=None, headers=None, timeout=None):
        if params["symbols"].startswith("AAA"):
            return Resp(429)
        return Resp(200, _ok_body(params))
    monkeypatch.setattr(requests, "get", fake)
    out, st = scan.alpaca_snapshots(["AAA", "BBB", "CCC", "DDD"], t0=scan._clock(), sleep=lambda s: None)
    assert set(out) == {"CCC", "DDD"}
    assert st["batches_failed"] == 1 and st["retries"] == 1 and st["calls"] == 3


def test_negative_the_key_never_reaches_a_log_or_an_error(monkeypatch, caplog):
    def boom(url, params=None, headers=None, timeout=None):
        raise requests.ConnectionError(f"connection refused; headers={headers}")
    monkeypatch.setattr(requests, "get", boom)
    caplog.set_level(logging.DEBUG)
    out, st = scan.alpaca_snapshots(["AAA"], t0=scan._clock())
    assert out == {} and st["batches_failed"] == 1
    assert st["errors"] and all(SECRET not in e for e in st["errors"])
    assert "<redacted>" in st["errors"][0]
    assert SECRET not in caplog.text


def test_budget_cut_counts_batches_skipped(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(scan, "_clock", lambda: clock[0])
    monkeypatch.setattr(scan, "ALPACA_BATCH", 1)

    def fake(url, params=None, headers=None, timeout=None):
        clock[0] += 200
        return Resp(200, _ok_body(params))
    monkeypatch.setattr(requests, "get", fake)
    out, st = scan.alpaca_snapshots(["AAA", "BBB", "CCC", "DDD"], t0=0.0)
    assert set(out) == {"AAA", "BBB"}
    assert st["batches_skipped"] == 2 and st["calls"] == 2


# ---------------------------------------------------------------------------
# pin_base
# ---------------------------------------------------------------------------
def snap_row(close, volume, prev, change_pct=None):
    return {"close": close, "volume": volume, "prev_day_close": prev, "change_pct": change_pct,
            "last_trade_price": None, "date": None}


REF_ROWS = {
    "ETF": [{"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust", "type": "ETF"},
            {"ticker": "QQQ", "name": "Invesco QQQ Trust", "type": "ETF"},
            {"ticker": "IWM", "name": "iShares Russell 2000 ETF", "type": "ETF"},
            {"ticker": "DIA", "name": "SPDR Dow Jones Industrial Average ETF", "type": "ETF"},
            {"ticker": "SOXL", "name": "Direxion Daily Semiconductor Bull 3X Shares", "type": "ETF"}],
    "ETS": [], "ETN": [], "ETV": [],
    "CS": [{"ticker": "TSLA", "name": "Tesla, Inc. Common Stock", "type": "CS"},
           {"ticker": "BRK.B", "name": "Berkshire Hathaway Inc. Class B", "type": "CS"},
           {"ticker": "PENNY", "name": "Penny Co", "type": "CS"},
           {"ticker": "THIN", "name": "Thin Co", "type": "CS"},
           {"ticker": "EDGE", "name": "Edge Co", "type": "CS"},
           {"ticker": "ABCDW", "name": "Abcd Warrant", "type": "WARRANT"}],
    "ADRC": [],
}

SNAP_ROWS = {
    "SPY": snap_row(660.0, 80_000_000, 670.0),
    "QQQ": snap_row(709.8, 50_000_000, 727.6),
    "IWM": snap_row(240.0, 1, 241.0),                  # below the $ floor — a ref, kept anyway
    "DIA": snap_row(460.0, 3_000_000, 465.0),
    "SOXL": snap_row(40.0, 60_000_000, 44.0),
    "TSLA": snap_row(354.72, 62_000_000, 362.43, change_pct=-2.754),
    "BRK-B": snap_row(480.0, 4_000_000, 482.0),
    "PENNY": snap_row(1.99, 900_000_000, 2.0),         # NEG $1.99
    "THIN": snap_row(10.0, 99_999.9, 10.0),            # NEG $999,999
    "EDGE": snap_row(10.0, 100_000, 10.0),             # exactly $1M — kept
    "ABCDW": snap_row(10.0, 9_000_000, 10.0),          # 5-letter W, not a stock type
    "NOREF": snap_row(10.0, 9_000_000, 10.0),          # absent from the reference list
    "XYZ.U": snap_row(10.0, 9_000_000, 10.0),          # a dotted unit
}


@pytest.fixture
def massive(monkeypatch):
    from sepa import levered_etf, prices
    calls = {"snap": 0, "ref": []}

    def fake_snap(include_otc=False):
        calls["snap"] += 1
        return copy.deepcopy(SNAP_ROWS), {"http": 200, "wall_s": 0.5, "bytes": 1, "n": len(SNAP_ROWS)}

    def fake_ref(type_, *, http=None, key=None, max_pages=12):
        calls["ref"].append(type_)
        return copy.deepcopy(REF_ROWS.get(type_, [])), True, 1
    monkeypatch.setattr(prices, "market_snapshot_with_meta", fake_snap)
    monkeypatch.setattr(levered_etf, "fetch_reference", fake_ref)
    return calls


def test_pin_base_applies_the_floors_and_the_type_filter(massive):
    bc = Coll()
    doc, why = scan.pin_base(SESS, NOW, coll=bc)
    assert why is None
    rows = doc["rows"]
    assert set(rows) == {"SPY", "QQQ", "IWM", "DIA", "SOXL", "TSLA", "BRK-B", "EDGE"}
    assert "PENNY" not in rows and "THIN" not in rows            # NEG $1.99, NEG $999,999
    assert "ABCDW" not in rows and "NOREF" not in rows and "XYZ.U" not in rows
    assert rows["SOXL"]["lev"] is True and rows["SOXL"]["ll"] == "3× ETF"
    assert rows["SPY"]["lev"] is False and rows["TSLA"]["lev"] is False
    assert rows["TSLA"] == {"c": 354.72, "v": 62_000_000, "pc": 362.43, "t": "CS",
                            "n": "Tesla, Inc. Common Stock", "lev": False, "ll": None}
    assert doc["_id"] == doc["trade_date"] == "2026-10-19" and doc["base_date"] == "2026-10-16"
    assert doc["ref"] == {"complete": True, "calls": 6, "types_incomplete": []}
    assert doc["snapshot"] == {"http": 200, "wall_s": 0.5, "n": len(SNAP_ROWS)}
    assert doc["n_universe"] == 8
    assert doc["pinned_at"].startswith("2026-10-19T01:03")
    assert massive["ref"] == list(scan.levered_etf.FUND_TYPES + scan.levered_etf.STOCK_TYPES)
    assert bc.find_one({"_id": "2026-10-19"})["n_universe"] == 8


def test_universe_floors_are_the_house_constants_by_name():
    from trading.safety_floor import MIN_SHARE_PRICE
    assert scan.UNIVERSE_MIN_PRICE == MIN_SHARE_PRICE == 2.0
    assert "UNIVERSE_MIN_PRICE = MIN_SHARE_PRICE" in open(scan.__file__, encoding="utf-8").read()
    assert scan.UNIVERSE_MIN_DOLLAR_VOL == 1_000_000
    assert scan.BOARD_MIN_ON_DOLLAR == 25_000
    assert scan.REF_SYMBOLS == ("SPY", "QQQ", "IWM", "DIA")
    assert scan.ALPACA_BATCH == 200 and scan.FEED == "overnight"
    assert scan.QUOTE_FRESH_SEC == 300 and scan.QUOTE_SPREAD_MAX == 0.015


def test_negative_ref_incomplete_tags_no_leverage_and_uses_the_fallback_filter(massive, monkeypatch):
    from sepa import levered_etf

    def partial(type_, *, http=None, key=None, max_pages=12):
        return copy.deepcopy(REF_ROWS.get(type_, [])), type_ != "CS", 1
    monkeypatch.setattr(levered_etf, "fetch_reference", partial)
    doc, why = scan.pin_base(SESS, NOW, coll=Coll())
    assert why is None
    rows = doc["rows"]
    assert all(r["lev"] is None and r["ll"] is None for r in rows.values())
    assert "NOREF" in rows                       # no type filter without the full list
    assert "ABCDW" not in rows and "XYZ.U" not in rows
    assert doc["ref"]["complete"] is False and doc["ref"]["types_incomplete"] == ["CS"]


def test_negative_the_reference_budget_cut_is_incomplete(massive, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(scan, "_clock", lambda: clock[0])
    from sepa import levered_etf

    def slow(type_, *, http=None, key=None, max_pages=12):
        clock[0] += scan.REF_BUDGET_SEC
        return copy.deepcopy(REF_ROWS.get(type_, [])), True, 1
    monkeypatch.setattr(levered_etf, "fetch_reference", slow)
    doc, _ = scan.pin_base(SESS, NOW, coll=Coll())
    assert doc["ref"]["complete"] is False
    assert doc["ref"]["types_incomplete"] == ["ETN", "ETV", "CS", "ADRC"]


def test_negative_todays_change_perc_is_never_the_prior_session(massive):
    doc, _ = scan.pin_base(SESS, NOW, coll=Coll())
    s = snap(bp=355.0, ap=355.2, quote_t=NOW)
    row, _ = scan.build_row("TSLA", doc["rows"]["TSLA"], s, SESS, NOW)
    assert row["prior_pct"] == pytest.approx(100 * (354.72 / 362.43 - 1))
    assert round(row["prior_pct"], 2) == -2.13
    assert row["prior_pct"] != pytest.approx(-2.754)


def test_negative_no_pin_after_0330(massive):
    late = datetime(2026, 10, 19, 3, 31, tzinfo=ET)
    doc, why = scan.pin_base(S.session_for(late), late, coll=Coll())
    assert doc is None and why == "base not pinned before the 03:30 ET snapshot reset"
    assert massive["snap"] == 0


def test_negative_spy_close_missing_is_refused(massive, monkeypatch):
    from sepa import prices
    rows = copy.deepcopy(SNAP_ROWS)
    rows["SPY"]["close"] = None
    monkeypatch.setattr(prices, "market_snapshot_with_meta", lambda include_otc=False: (rows, {"http": 200}))
    bc = Coll()
    doc, why = scan.pin_base(SESS, NOW, coll=bc)
    assert doc is None and why == "Massive snapshot carries no close for SPY — not pinned"
    assert bc.docs == {}


def test_negative_a_snapshot_failure_is_refused(massive, monkeypatch):
    from sepa import prices
    monkeypatch.setattr(prices, "market_snapshot_with_meta",
                        lambda include_otc=False: ({}, {"http": 500, "error": "HTTP 500"}))
    doc, why = scan.pin_base(SESS, NOW, coll=Coll())
    assert doc is None and "HTTP 500" in why


# ---------------------------------------------------------------------------
# read_once
# ---------------------------------------------------------------------------
def _feed(on_dollar_by_sym=None, refuse=None):
    on_dollar_by_sym = on_dollar_by_sym or {}

    def fake(url, params=None, headers=None, timeout=None):
        if refuse:
            return Resp(refuse, {"message": f"forbidden {headers['APCA-API-KEY-ID']}"})
        out = {}
        for w in params["symbols"].split(","):
            v = on_dollar_by_sym.get(w, 1_000)
            out[w] = snap(bp=50.0, ap=50.05, quote_t=NOW - timedelta(seconds=10), v=v, vw=50.0,
                          trade_p=49.0, trade_t=NOW - timedelta(minutes=15))
        return Resp(200, out)
    return fake


def colls():
    return {"reads_coll": Coll(), "base_coll": Coll(), "pass_coll": Coll()}


def test_read_once_happy_pass_stores_the_read_and_the_pass_doc(massive, monkeypatch):
    monkeypatch.setattr(requests, "get", _feed({"SOXL": 10_000, "TSLA": 600, "BRK.B": 400}))
    c = colls()
    res = scan.read_once(NOW, **c)
    assert res["ran"] is True and res["ok"] is True
    assert res["stored_id"] == "2026-10-19T0103"
    doc = c["reads_coll"].find_one({"_id": "2026-10-19T0103"})
    cnt = doc["counts"]
    assert set(cnt) == {"universe", "ref_complete", "batches", "batches_failed", "batches_skipped", "calls",
                        "retries", "not_on_feed", "no_price", "no_base", "priced", "on_trade", "on_quote",
                        "listed", "thin", "leveraged_tagged", "lev_unknown", "trade_age_median_sec"}
    assert cnt["universe"] == 8 and cnt["priced"] == 8 and cnt["on_quote"] == 8 and cnt["on_trade"] == 0
    assert cnt["calls"] == 1 and cnt["batches"] == 1 and cnt["ref_complete"] is True
    assert cnt["leveraged_tagged"] == 1 and cnt["lev_unknown"] == 0
    assert cnt["trade_age_median_sec"] is None
    # $ floor: SOXL 10,000×50 = $500K listed; TSLA 600×50 = $30K listed; BRK-B 400×50 = $20K thin
    listed = {r["symbol"] for r in doc["rows"]}
    assert "SOXL" in listed and "TSLA" in listed and "BRK-B" not in listed
    assert cnt["listed"] == len(doc["rows"]) and cnt["thin"] == cnt["priced"] - cnt["listed"]
    assert all(r["on_dollar"] >= scan.BOARD_MIN_ON_DOLLAR for r in doc["rows"])
    assert [r["symbol"] for r in doc["refs"]] == ["SPY", "QQQ", "IWM", "DIA"]
    assert doc["complete"] is True and doc["reason"] is None
    assert doc["as_of_et"] == "Mon 1:03 ET" and doc["trade_date"] == "2026-10-19"
    assert doc["base_date"] == "2026-10-16" and doc["session_open"] is True
    json.dumps(doc, allow_nan=False)
    p = c["pass_coll"].find_one({"_id": "latest"})
    assert p["ok"] is True and p["stored_id"] == "2026-10-19T0103" and p["ran"] is True
    assert set(p) == {"_id", "as_of", "as_of_ts", "as_of_et", "trade_date", "ran", "ok", "stored_id",
                      "reason", "counts"}


def test_the_base_is_pinned_once_across_two_passes(massive, monkeypatch):
    monkeypatch.setattr(requests, "get", _feed())
    c = colls()
    scan.read_once(NOW, **c)
    scan.read_once(NOW + timedelta(minutes=10), **c)
    assert massive["snap"] == 1
    assert len(c["reads_coll"].docs) == 2


def test_negative_closed_session_makes_no_http_at_all(massive, monkeypatch):
    from sepa import levered_etf, prices

    def boom(*a, **k):
        raise AssertionError("no HTTP on a closed session")
    monkeypatch.setattr(requests, "get", boom)
    monkeypatch.setattr(prices, "market_snapshot_with_meta", boom)
    monkeypatch.setattr(levered_etf, "fetch_reference", boom)
    c = colls()
    res = scan.read_once(datetime(2026, 10, 24, 21, 0, tzinfo=ET), **c)
    assert res["ran"] is False and "weekend" in res["reason"]
    res = scan.read_once(datetime(2026, 10, 19, 12, 0, tzinfo=ET), **c)
    assert res == {"ran": False, "reason": "between sessions"}
    assert all(not x.docs for x in c.values())


def test_negative_403_aborts_and_stores_nothing(massive, monkeypatch, caplog):
    monkeypatch.setattr(requests, "get", _feed(refuse=403))
    c = colls()
    caplog.set_level(logging.DEBUG)
    res = scan.read_once(NOW, **c)
    assert res["ok"] is False and res["reason"] == "Alpaca overnight feed refused (HTTP 403)"
    assert c["reads_coll"].docs == {}
    p = c["pass_coll"].find_one({"_id": "latest"})
    assert p["ok"] is False and p["reason"] == "Alpaca overnight feed refused (HTTP 403)"
    assert SECRET not in caplog.text and SECRET not in json.dumps(p, default=str)


def test_negative_a_failed_batch_marks_the_read_incomplete(massive, monkeypatch):
    monkeypatch.setattr(scan, "ALPACA_BATCH", 4)
    good = _feed()

    def fake(url, params=None, headers=None, timeout=None):
        if params["symbols"].startswith("BRK.B"):
            return Resp(429)
        return good(url, params=params, headers=headers, timeout=timeout)
    monkeypatch.setattr(requests, "get", fake)
    monkeypatch.setattr(scan, "RETRY_SLEEP_SEC", 0)
    c = colls()
    res = scan.read_once(NOW, **c)
    doc = c["reads_coll"].find_one({"_id": res["stored_id"]})
    assert doc["complete"] is False and "1 of 2 batches failed" in doc["reason"]
    assert doc["counts"]["batches_failed"] == 1 and doc["counts"]["retries"] == 1
    assert doc["counts"]["priced"] == 4 and doc["counts"]["not_on_feed"] == 4


def test_negative_every_batch_failed_keeps_the_batch_reason(massive, monkeypatch):
    """CHANGED 2026-10-19 (critic finding 4): not the generic "no name priced"."""
    monkeypatch.setattr(requests, "get", lambda *a, **k: Resp(500))
    c = colls()
    res = scan.read_once(NOW, **c)
    assert res["ok"] is False and res["stored_id"] is None
    assert res["reason"].startswith("1 of 1 batches failed")
    assert "no name priced" not in res["reason"]
    assert c["reads_coll"].docs == {}
    assert c["pass_coll"].find_one({"_id": "latest"})["reason"] == res["reason"]


def test_negative_nothing_priced_stores_nothing(massive, monkeypatch):
    def stale(url, params=None, headers=None, timeout=None):
        old = SESS["opens_at"] - timedelta(hours=1)
        return Resp(200, {w: snap(trade_p=1.0, trade_t=old, bp=1.0, ap=1.01, quote_t=old)
                          for w in params["symbols"].split(",")})
    monkeypatch.setattr(requests, "get", stale)
    c = colls()
    res = scan.read_once(NOW, **c)
    assert res["ok"] is False and res["stored_id"] is None
    assert res["reason"] == "no name priced this session — nothing stored"
    assert c["reads_coll"].docs == {}
    assert c["pass_coll"].find_one({"_id": "latest"})["ok"] is False


def test_negative_dry_run_writes_nothing(massive, monkeypatch):
    monkeypatch.setattr(requests, "get", _feed())
    c = colls()
    res = scan.read_once(NOW, dry_run=True, **c)
    assert res["ok"] is True and res["read"]["counts"]["priced"] == 8
    assert all(not x.docs for x in c.values())


def test_negative_no_alpaca_keys_reads_nothing(massive, monkeypatch):
    monkeypatch.delenv("ALPACA_KEY_ID")
    c = colls()
    res = scan.read_once(NOW, **c)
    assert res["ok"] is False and "not configured" in res["reason"]
    assert c["reads_coll"].docs == {}


def test_negative_no_base_writes_the_pass_doc_only(massive, monkeypatch):
    late = datetime(2026, 10, 19, 3, 40, tzinfo=ET)
    c = colls()
    res = scan.read_once(late, **c)
    assert res["ok"] is False and "03:30" in res["reason"]
    assert c["reads_coll"].docs == {} and c["base_coll"].docs == {}
    assert c["pass_coll"].find_one({"_id": "latest"})["reason"] == res["reason"]


# ---------------------------------------------------------------------------
# store / load_latest
# ---------------------------------------------------------------------------
def _doc(td, hhmm, ts):
    return {"_id": f"{td}T{hhmm}", "trade_date": td, "as_of_ts": ts, "rows": [], "refs": [], "counts": {}}


def test_store_ids_by_trade_date_and_wall_clock_and_prunes_to_two_sessions():
    rc = Coll()
    assert scan.store(_doc("2026-10-15", "0100", 1.0), rc) == "2026-10-15T0100"
    scan.store(_doc("2026-10-16", "0100", 2.0), rc)
    scan.store(_doc("2026-10-19", "0100", 3.0), rc)
    assert set(rc.docs) == {"2026-10-16T0100", "2026-10-19T0100"}
    scan.store(_doc("2026-10-19", "0110", 4.0), rc)
    assert set(rc.docs) == {"2026-10-16T0100", "2026-10-19T0100", "2026-10-19T0110"}
    assert scan.KEEP_SESSIONS == 2


def test_negative_load_latest_orders_by_as_of_ts_never_by_id():
    rc = Coll()
    sun = datetime(2026, 10, 18, 23, 50, tzinfo=ET).timestamp()
    mon = datetime(2026, 10, 19, 1, 0, tzinfo=ET).timestamp()
    scan.store(_doc("2026-10-19", "2350", sun), rc)
    scan.store(_doc("2026-10-19", "0100", mon), rc)
    assert "2026-10-19T2350" > "2026-10-19T0100"
    assert scan.load_latest("2026-10-19", rc)["_id"] == "2026-10-19T0100"
    assert scan.load_latest(None, rc)["_id"] == "2026-10-19T0100"
    assert scan.load_latest("2026-10-16", rc) is None


def test_negative_no_mongo_means_none_not_a_crash(monkeypatch):
    monkeypatch.setattr(scan, "_coll", lambda name: None)
    assert scan.store(_doc("2026-10-19", "0100", 1.0)) is None
    assert scan.load_latest() is None
    assert scan.load_base("2026-10-19") is None
    assert scan.load_pass() is None


def test_the_new_modules_never_import_the_old_movers_tracker():
    import re
    for mod in ("scan", "session", "board"):
        src = open(scan.__file__.replace("scan.py", f"{mod}.py"), encoding="utf-8").read()
        assert not re.search(r"^\s*(from \.|from overnight)\s*(import movers|\.?movers)", src, re.M), mod
        assert "import movers" not in src and "daytrading" not in src, mod


def test_negative_no_banned_words_in_the_new_backend_files():
    import io
    import re
    import tokenize
    for mod in ("scan", "session", "board"):
        path = scan.__file__.replace("scan.py", f"{mod}.py")
        src = open(path, encoding="utf-8").read()
        toks = [t.string for t in tokenize.generate_tokens(io.StringIO(src).readline)
                if t.type != tokenize.COMMENT]
        assert not re.search(r"boun|fak[e]", " ".join(toks), re.I), mod
