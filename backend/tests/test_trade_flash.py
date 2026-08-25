"""Trade Flash — zone-tied burst events and the honesty around their delivery.

The dangerous failure modes here are all silent: a burst away from the zone
sneaking into the push (noise -> the kind gets retired), a duplicate window
double-pushing, and the 2026-06-24 chokepoint — a kind missing from
default_prefs drops every push while the cron logs look healthy.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orderflow import trade_flash as TF                    # noqa: E402
from supply_demand.price_zones import NEAR_PCT             # noqa: E402


# ── classify_zone ────────────────────────────────────────────────────────────
def test_a_burst_inside_the_band_is_in():
    assert TF.classify_zone(100.0, 99.0, 101.0) == "in"
    assert TF.classify_zone(99.0, 99.0, 101.0) == "in"     # edges count


def test_a_burst_just_outside_is_near_on_the_shared_scale():
    """Nearness reuses price_zones.NEAR_PCT — the same 3% that means "at" a
    zone everywhere else. A second constant would be a second scale."""
    edge = 101.0
    near = edge * (1 + (NEAR_PCT - 0.5) / 100)             # inside the near band
    far = edge * (1 + (NEAR_PCT + 2.0) / 100)              # outside it
    assert TF.classify_zone(near, 99.0, edge) == "near"
    assert TF.classify_zone(far, 99.0, edge) is None


def test_below_the_band_is_symmetric_with_above():
    lo = 99.0
    assert TF.classify_zone(lo * (1 - (NEAR_PCT - 0.5) / 100), lo, 101.0) == "near"
    assert TF.classify_zone(lo * (1 - (NEAR_PCT + 2.0) / 100), lo, 101.0) is None


def test_garbage_inputs_classify_as_nothing_not_as_in():
    """A missing band must never promote a burst to 'at the zone'."""
    assert TF.classify_zone(None, 99.0, 101.0) is None
    assert TF.classify_zone(100.0, None, 101.0) is None
    assert TF.classify_zone(100.0, 101.0, 99.0) is None    # inverted band
    assert TF.classify_zone(0.0, 99.0, 101.0) is None
    assert TF.classify_zone(True, 99.0, 101.0) is None     # bool is not a price


# ── build_events — the location gate ─────────────────────────────────────────
BURST_IN = {"time_et": "10:31:20", "side": "buy", "dollars": 412_000.0,
            "volume": 4100, "n_trades": 55, "price": 100.2}
BURST_AWAY = {"time_et": "10:33:40", "side": "buy", "dollars": 900_000.0,
              "volume": 9000, "n_trades": 80, "price": 111.0}


def test_only_bursts_at_the_zone_become_events():
    """The location gate IS the feature. The away-burst is bigger — and still
    dropped, because size was never the qualifier here."""
    evs = TF.build_events("NVDA", "demand", {"lo": 99.0, "hi": 101.0},
                          [BURST_IN, BURST_AWAY], "2026-08-24")
    assert len(evs) == 1
    assert evs[0]["price"] == 100.2
    assert evs[0]["at_zone"] == "in"
    assert evs[0]["board"] == "demand"


def test_no_band_means_no_events_not_all_events():
    assert TF.build_events("NVDA", "demand", {}, [BURST_IN], "2026-08-24") == []
    assert TF.build_events("NVDA", "demand", None, [BURST_IN], "2026-08-24") == []


def test_the_event_id_is_deterministic_so_repolling_cannot_duplicate():
    """LOOKBACK_MIN (7) deliberately overlaps the 5-min cron cadence; the
    overlap is only safe because the same window maps to the same _id."""
    a = TF.build_events("nvda", "demand", {"lo": 99, "hi": 101}, [BURST_IN], "2026-08-24")
    b = TF.build_events("NVDA", "demand", {"lo": 99, "hi": 101}, [BURST_IN], "2026-08-24")
    assert a[0]["_id"] == b[0]["_id"] == "NVDA:2026-08-24:10:31:20"


# ── headline — the meaning depends on WHICH board's band was hit ─────────────
def test_headlines_read_the_board_not_just_the_side():
    dem_buy = TF.headline({"symbol": "CR", "time_et": "10:31:20", "side": "buy",
                           "dollars": 412_000.0, "board": "demand"})
    sup_sell = TF.headline({"symbol": "FANG", "time_et": "11:02:10", "side": "sell",
                            "dollars": 1_400_000.0, "board": "supply"})
    assert "buyers stepping in AT the demand zone" in dem_buy
    assert "$412K" in dem_buy
    assert "sellers defending the supply ceiling" in sup_sell
    assert "$1.4M" in sup_sell


def test_a_sell_into_demand_is_named_as_the_warning_it_is():
    h = TF.headline({"symbol": "CR", "time_et": "10:31:20", "side": "sell",
                     "dollars": 300_000.0, "board": "demand"})
    assert "sellers hitting the demand zone" in h


# ── delivery honesty ─────────────────────────────────────────────────────────
def test_trade_flash_is_in_default_prefs_or_every_push_silently_drops():
    """THE chokepoint (2026-06-24): a kind absent from default_prefs is dropped
    for every device while the sender logs success. This test failing means
    his phone goes dark with a healthy-looking cron."""
    from push.subs import default_prefs, DISABLED_ALERT_KINDS
    assert default_prefs().get("trade_flash") is True
    assert "trade_flash" not in DISABLED_ALERT_KINDS


def test_the_watch_refuses_to_run_outside_market_hours(monkeypatch):
    """Bursts on a closed tape are stale news; the cron window is wider than
    the market on purpose and the module is the gate."""
    import datetime as dt
    from zoneinfo import ZoneInfo

    class FrozenDT(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 8, 24, 7, 30, tzinfo=ZoneInfo("America/New_York"))

    monkeypatch.setattr(TF, "_now_et",
                        lambda: dt.datetime(2026, 8, 24, 7, 30,
                                            tzinfo=ZoneInfo("America/New_York")))
    r = TF.run_watch()
    assert r.get("skipped") == "market closed"


def test_the_watch_skips_weekends(monkeypatch):
    import datetime as dt
    from zoneinfo import ZoneInfo
    monkeypatch.setattr(TF, "_now_et",
                        lambda: dt.datetime(2026, 8, 22, 11, 0,       # a Saturday
                                            tzinfo=ZoneInfo("America/New_York")))
    assert TF.run_watch().get("skipped") == "market closed"


def _no_http(monkeypatch):
    """Force board_bands down its import fallback so the fixture under test is
    the one being exercised, not a live HTTP call."""
    import requests
    monkeypatch.setattr(requests, "get",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no http")))


def test_REGRESSION_the_board_is_read_over_HTTP_not_imported():
    """demand_reentry._cache is PROCESS-LOCAL. The cron runs this as a fresh
    process, so an in-process cached_or_warm always returns warming=True and
    the watch would poll nothing while logging a healthy zero — forever.

    The crontab already records this exact lesson at the 16:55 warm
    ("OVER HTTP, NOT AS AN IMPORT (fixed 2026-08-15)"); this module walked into
    it anyway on 2026-08-24. The guard keeps the HTTP read primary."""
    import ast
    import inspect
    src = inspect.getsource(TF.board_bands)
    assert "supply-demand/demand-reentry" in src
    assert "X-User-Email" in src
    # Compare positions in the CODE, not the prose — the docstring names
    # cached_or_warm while explaining why it is the fallback, and matching that
    # is the same docstring-vs-code trap the 0DTE source guards hit earlier.
    fn = ast.parse(src.lstrip()).body[0]
    body = fn.body[1:] if (isinstance(fn.body[0], ast.Expr)
                           and isinstance(fn.body[0].value, ast.Constant)) else fn.body
    code = "\n".join(ast.dump(n) for n in body)
    assert "requests" in code and "cached_or_warm" in code
    assert code.index("requests") < code.index("cached_or_warm")


def test_a_warming_board_over_http_yields_an_empty_watch(monkeypatch):
    class R:
        status_code = 200
        @staticmethod
        def json():
            return {"warming": True, "rows": [], "supply_rows": []}
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    assert TF.board_bands() == []


def test_the_http_board_is_parsed_into_bands(monkeypatch):
    class R:
        status_code = 200
        @staticmethod
        def json():
            return {"warming": False,
                    "rows": [{"symbol": "CR", "entry_zone": {"lo": 203.9, "hi": 206.4}}],
                    "supply_rows": [{"symbol": "FANG",
                                     "supply": {"ceiling": {"lo": 210.0, "hi": 212.0}}}]}
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    bands = TF.board_bands()
    assert ("CR", "demand", {"lo": 203.9, "hi": 206.4}) in bands
    assert [b for b in bands if b[0] == "FANG"][0][1] == "supply"


def test_the_universe_is_hard_capped(monkeypatch):
    _no_http(monkeypatch)
    """A future board change must not silently turn the poll into a
    500-symbol sweep of the shared key."""
    fake = {"warming": False,
            "rows": [{"symbol": f"S{i}", "entry_zone": {"lo": 1, "hi": 2}}
                     for i in range(300)],
            "supply_rows": []}
    import supply_demand.demand_reentry as D
    monkeypatch.setattr(D, "cached_or_warm", lambda *a, **k: fake)
    assert len(TF.board_bands()) == TF.MAX_SYMBOLS


def test_a_symbol_on_both_boards_is_polled_once_with_the_demand_band(monkeypatch):
    _no_http(monkeypatch)
    fake = {"warming": False,
            "rows": [{"symbol": "CR", "entry_zone": {"lo": 99, "hi": 101}}],
            "supply_rows": [{"symbol": "CR",
                             "supply": {"ceiling": {"lo": 210, "hi": 212}}}]}
    import supply_demand.demand_reentry as D
    monkeypatch.setattr(D, "cached_or_warm", lambda *a, **k: fake)
    bands = TF.board_bands()
    assert len(bands) == 1
    assert bands[0][1] == "demand"


def test_a_warming_cache_yields_an_empty_watch_not_a_crash(monkeypatch):
    _no_http(monkeypatch)
    import supply_demand.demand_reentry as D
    monkeypatch.setattr(D, "cached_or_warm", lambda *a, **k: {"warming": True})
    assert TF.board_bands() == []


def test_REGRESSION_the_tail_fetch_takes_the_NEWEST_trades_not_the_oldest():
    """One page caps at 50,000 prints and a busy open exceeds that inside the
    lookback window — measured 2026-08-24 on 9:30-9:37: NVDA returned a full
    50,000 with next_url still set (TSLA 33,833, SPY 20,586).

    With order=asc the poll would have kept the OLDEST seven minutes and
    dropped the newest — the prints this alert exists to catch. The flash would
    then fire late, or not at all, precisely on the heaviest tape of the day.
    """
    import inspect
    src = inspect.getsource(TF.fetch_recent_trades)
    assert '"order": "desc"' in src
    assert '"order": "asc"' not in src
    # And the frame must still come back ascending for tick_rule_sides /
    # find_bursts, both of which assume time order.
    assert 'sort_values("ts_utc")' in src


@pytest.mark.parametrize("cross_time,dollars", [
    ("09:30:00", 1_085_300_000.0),      # AVGO open, measured 2026-08-21
    ("16:00:00", 1_482_900_000.0),      # AVGO close, same session
])
def test_neither_auction_cross_is_a_burst(cross_time, dollars):
    """Both crosses print as one enormous trade stamped exactly at the bell and
    find_bursts reads each as a giant one-sided burst on nearly every symbol.
    Measured 2026-08-21 — open: AVGO $1,085.3M, FANG $33.2M, ALLY $1.3M;
    close: AVGO $1,482.9M, FANG $130.1M, CR $22.1M. None is anyone aggressing.

    The OPEN filter is load-bearing for live polling: the first poll is at 9:32
    and its 7-minute lookback reaches back over 09:30:00, so unfiltered this
    would be the first push of every session — which is how a push kind earns
    itself muted."""
    cross = {"time_et": cross_time, "side": "sell", "dollars": dollars,
             "volume": 3_000_000, "n_trades": 900, "price": 100.0}
    real = {"time_et": "09:30:10", "side": "buy", "dollars": 106_900_000.0,
            "volume": 300_000, "n_trades": 400, "price": 100.0}
    evs = TF.build_events("AVGO", "demand", {"lo": 99.0, "hi": 101.0},
                          [cross, real], "2026-08-21")
    assert len(evs) == 1
    assert evs[0]["time_et"] == "09:30:10"       # the real one survives
