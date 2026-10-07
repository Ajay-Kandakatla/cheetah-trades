"""The Portfolio page's 60 s holdings poll froze the whole api (2026-10-06).

py-spy on the live api caught the event loop's MainThread inside
`portfolio_holdings_get` -> `quotes.fetch_quotes` -> yfinance, once a minute,
for 5-19 s. Every other request on the site waited behind it. Two fixes:

  * the holdings / summary routes are plain `def`, so FastAPI runs them in its
    threadpool and the event loop keeps serving;
  * a ticker yfinance could not price is not asked again for `_MISS_TTL`, and
    a broker's `$`-prefixed non-ticker position never goes to yfinance.
    Massive is still asked every refresh.
"""
import asyncio
import inspect
import sys
import time
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from portfolio import api as papi  # noqa: E402
from portfolio import quotes as Q  # noqa: E402


class _FastInfo(dict):
    pass


class _FakeYf:
    """yfinance stand-in: records every batch it is asked for."""

    def __init__(self, prices: dict, raise_for: set = frozenset()):
        self.prices = prices
        self.raise_for = set(raise_for)
        self.asked: list[list[str]] = []

    def Tickers(self, joined: str):
        names = joined.split()
        self.asked.append(names)
        outer = self

        class _Tk:
            def __init__(self, t):
                self.t = t

            @property
            def fast_info(self):
                if self.t in outer.raise_for:
                    raise RuntimeError("no price data found")
                p = outer.prices.get(self.t)
                return _FastInfo(last_price=p, previous_close=p)

        return types.SimpleNamespace(tickers={t: _Tk(t) for t in names})


@pytest.fixture
def fake(monkeypatch):
    Q._cache.clear()
    Q._cache_set_at.clear()
    Q._yf_miss_at.clear()
    Q._ever_priced.clear()
    massive = {"priced": {}, "asked": []}

    def bulk_live_prices(syms):
        massive["asked"].append(list(syms))
        return {t: {"price": p, "prev_day_close": p} for t, p in massive["priced"].items() if t in syms}

    from sepa import prices as sp
    monkeypatch.setattr(sp, "bulk_live_prices", bulk_live_prices)
    yf = _FakeYf({"AAPL": 200.0}, raise_for={"JUNK"})
    monkeypatch.setitem(sys.modules, "yfinance", yf)
    yield types.SimpleNamespace(yf=yf, massive=massive)
    Q._cache.clear()
    Q._cache_set_at.clear()
    Q._yf_miss_at.clear()
    Q._ever_priced.clear()


def _expire_cache():
    for t in list(Q._cache_set_at):
        Q._cache_set_at[t] -= Q._CACHE_TTL + 1


# ── the routes run off the event loop ────────────────────────────────────

@pytest.mark.parametrize("fn", ["portfolio_get", "portfolio_holdings_get", "portfolio_holdings_refresh"])
def test_routes_are_plain_def(fn):
    assert not inspect.iscoroutinefunction(getattr(papi, fn)), (
        f"{fn} must stay plain `def`: as `async def` its blocking quote/Plaid "
        "calls run on the event loop and stall every request")


def test_route_registered_as_sync_endpoint():
    from fastapi.routing import APIRoute
    routes = {(m, r.path): r for r in papi.router.routes if isinstance(r, APIRoute) for m in r.methods}
    for key in (("GET", "/portfolio"), ("GET", "/portfolio/holdings"), ("POST", "/portfolio/holdings/refresh")):
        assert not asyncio.iscoroutinefunction(routes[key].endpoint), key


def test_negative_awaiting_routes_untouched():
    """Routes that already await stay async (no blanket conversion)."""
    assert inspect.iscoroutinefunction(papi.portfolio_betas_get)
    assert inspect.iscoroutinefunction(papi.portfolio_attribution)


# ── the yfinance miss cache ──────────────────────────────────────────────

def test_dollar_positions_never_reach_yfinance(fake):
    out = Q.fetch_quotes(["$RESTRICTED.STOCK.UNITS", "$BTC.LP.IDX.2055.H"])
    assert out == {}
    assert fake.yf.asked == []
    assert fake.massive["asked"], "Massive is still asked"


def test_failed_ticker_not_reasked_within_ttl(fake):
    Q.fetch_quotes(["JUNK"])
    assert fake.yf.asked == [["JUNK"]]
    _expire_cache()
    Q.fetch_quotes(["JUNK"])
    Q.fetch_quotes(["JUNK"])
    assert fake.yf.asked == [["JUNK"]], "a miss is not re-asked inside _MISS_TTL"


def test_failed_ticker_reasked_after_ttl(fake):
    Q.fetch_quotes(["JUNK"])
    Q._yf_miss_at["JUNK"] -= Q._MISS_TTL + 1
    Q.fetch_quotes(["JUNK"])
    assert fake.yf.asked == [["JUNK"], ["JUNK"]]


def test_massive_still_asked_for_a_missed_ticker_and_recovers(fake):
    Q.fetch_quotes(["JUNK"])
    fake.massive["priced"]["JUNK"] = 12.5
    out = Q.fetch_quotes(["JUNK"])
    assert out["JUNK"]["last"] == 12.5
    assert len(fake.yf.asked) == 1


def test_good_ticker_priced_and_not_marked_missed(fake):
    out = Q.fetch_quotes(["AAPL"])
    assert out["AAPL"]["last"] == 200.0
    assert "AAPL" not in Q._yf_miss_at
    _expire_cache()
    Q.fetch_quotes(["AAPL"])
    assert fake.yf.asked == [["AAPL"], ["AAPL"]], "a priced ticker is refreshed every TTL"


def test_none_price_counts_as_a_miss(fake):
    fake.yf.prices["NOPX"] = None
    out = Q.fetch_quotes(["NOPX"])
    assert out["NOPX"]["last"] is None
    _expire_cache()
    Q.fetch_quotes(["NOPX"])
    assert fake.yf.asked == [["NOPX"]]


def test_mixed_batch_only_asks_eligible(fake):
    Q.fetch_quotes(["JUNK"])
    _expire_cache()
    Q.fetch_quotes(["AAPL", "JUNK", "$CASH"])
    assert fake.yf.asked[-1] == ["AAPL"]


def _boom_yf():
    class _Boom:
        def __init__(self):
            self.asked = []

        def Tickers(self, joined):
            self.asked.append(joined.split())
            raise RuntimeError("Too Many Requests")

    return _Boom()


def test_negative_whole_batch_failure_marks_nothing(fake, monkeypatch):
    boom = _boom_yf()
    monkeypatch.setitem(sys.modules, "yfinance", boom)
    assert Q.fetch_quotes(["AAPL", "MSFT"]) == {}
    assert Q._yf_miss_at == {}, "a throttle is not a per-ticker miss"
    Q.fetch_quotes(["AAPL", "MSFT"])
    assert len(boom.asked) == 2, "re-asked on the next refresh"


def test_negative_ever_priced_ticker_never_barred_or_blanked(fake):
    """Critic 2026-10-06: Massive down + one empty Yahoo answer must not
    blank a held stock for 15 min (manual rows have no broker fallback)."""
    fake.massive["priced"]["MU"] = 100.0
    assert Q.fetch_quotes(["MU"])["MU"]["last"] == 100.0
    fake.massive["priced"].clear()          # Massive outage
    fake.yf.prices["MU"] = None             # Yahoo hiccup
    _expire_cache()
    assert Q.fetch_quotes(["MU"])["MU"]["last"] == 100.0, "last good quote kept"
    assert "MU" not in Q._yf_miss_at
    fake.yf.prices["MU"] = 101.0            # Yahoo recovers next poll
    assert Q.fetch_quotes(["MU"])["MU"]["last"] == 101.0
    assert fake.yf.asked == [["MU"], ["MU"]]


def test_negative_ever_priced_ticker_raising_is_reasked(fake):
    fake.massive["priced"]["JUNK"] = 5.0
    Q.fetch_quotes(["JUNK"])
    fake.massive["priced"].clear()
    _expire_cache()
    assert Q.fetch_quotes(["JUNK"])["JUNK"]["last"] == 5.0
    _expire_cache()
    Q.fetch_quotes(["JUNK"])
    assert fake.yf.asked == [["JUNK"], ["JUNK"]]
