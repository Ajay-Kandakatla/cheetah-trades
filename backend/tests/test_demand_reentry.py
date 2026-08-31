"""Behavioral + negative tests for the demand-zone RE-ENTRY scan.

Ajay 2026-08-13: "stocks that entering back in to demand zones … scan only
S&P 500 stocks."

The pure helpers (`reentry_read`, `trade_plan`, `_pick_entry_zone`) carry the
whole decision, so they are tested directly on synthetic data — no network, no
price cache. The regression tests lock the two bugs found while building this:

  1. `fetch_sp500()` silently returned the 158-name CURATED list (a different
     universe) whenever Wikipedia 403'd, so "S&P 500 only" scanned the wrong
     names. Fixed by falling back to the stale-but-real cached constituents.
  2. The /zones page's default band geometry produces ~1%-wide bands, which
     made "re-entry" fire on noise. This module must pass its own wider
     geometry and must NOT mutate the shared module defaults.
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import demand_reentry as dr
from supply_demand import price_zones as pz


# ── reentry_read — the transition test ────────────────────────────────────────
# Captured at file-import time, BEFORE the autouse fixture below nulls it —
# the roster-integrity test reads this.
_REAL_PINNED_ETFS = dr.PINNED_ETFS


@pytest.fixture(autouse=True)
def _no_pinned_etfs(monkeypatch):
    """Neutralise the pinned-ETF tail (GLD/SLV + the AI-infra roster,
    2026-08-28) for the legacy scan tests: they assert exact universe
    sizes/symbol lists against stubbed loaders and predate the pin. Tests
    ABOUT the pin re-enable it explicitly."""
    monkeypatch.setattr(dr, "PINNED_ETFS", ())


def test_reentry_true_when_price_left_the_band_and_came_back():
    """Ran to 120 (well above the 106 band top), now back at 103 inside it."""
    out = dr.reentry_read([100, 110, 120, 105], zone_hi=106, zone_lo=100, last_price=103)
    assert out["is_reentry"] is True
    assert out["in_band"] is True
    assert out["fell_from_pct"] == pytest.approx(13.2, abs=0.2)
    assert out["bars_since_above"] == 1


def test_not_a_reentry_when_price_never_left_the_band():
    """Sitting inside a band for the whole window is NOT 'entering back in' —
    this is the distinction the whole feature rests on."""
    out = dr.reentry_read([101, 102, 103, 104], zone_hi=106, zone_lo=100, last_price=103)
    assert out["is_reentry"] is False
    assert out["in_band"] is True
    assert out["bars_since_above"] is None


def test_not_a_reentry_when_price_is_below_the_band():
    """Below the floor = support broke. That is the opposite signal and must
    never be reported as demand."""
    out = dr.reentry_read([100, 110, 120, 95], zone_hi=106, zone_lo=100, last_price=95)
    assert out["is_reentry"] is False
    assert out["in_band"] is False


def test_not_a_reentry_when_the_rise_above_was_too_small():
    """Poking 1% above a band and falling back is noise, not a pullback."""
    out = dr.reentry_read([100, 106.5, 103], zone_hi=106, zone_lo=100, last_price=103)
    assert out["fell_from_pct"] < dr.MIN_RISE_ABOVE_PCT
    assert out["is_reentry"] is False


def test_reentry_read_handles_empty_and_degenerate_input():
    assert dr.reentry_read([], 106, 100, 103)["is_reentry"] is False
    assert dr.reentry_read([100, 110], 0, 0, 103)["is_reentry"] is False
    # inverted band (hi <= lo) must not blow up or qualify
    assert dr.reentry_read([100, 110], 100, 106, 103)["is_reentry"] is False


def test_lookback_window_is_respected():
    """The run-up must be INSIDE the lookback window — an old high does not
    make today's position a fresh re-entry."""
    closes = [130] + [103] * 60          # spike far in the past, flat since
    out = dr.reentry_read(closes, 106, 100, 103, lookback=40)
    assert out["is_reentry"] is False


# ── trade_plan — the written entry/exit ───────────────────────────────────────
def test_trade_plan_levels_and_reward_risk():
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0})
    assert p["entry_low"] == 100.0 and p["entry_high"] == 106.0
    # stop sits UNDER the floor by the buffer, never inside the band
    assert p["stop"] < 100.0
    assert p["stop"] == pytest.approx(98.5, abs=0.01)
    assert p["target"] == 120.0
    assert p["rr"] == pytest.approx((120 - 103) / (103 - 98.5), abs=0.02)
    assert p["risk_exceeds_max"] is False


def test_trade_plan_without_overhead_supply_has_no_target_or_rr():
    """No resistance above = no honest target. We must not invent one."""
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, None)
    assert p["target"] is None
    assert p["reward_pct"] is None
    assert p["rr"] is None


def test_trade_plan_ignores_resistance_that_is_below_price():
    """A 'resistance' under the current price is already broken — not a target."""
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 90.0})
    assert p["target"] is None


def test_trade_plan_flags_a_stop_wider_than_the_hard_cap():
    """Band far below price → the stop is undefendable. Flag, don't silently
    hand him a 30% risk trade."""
    p = dr.trade_plan(100.0, {"lo": 70.0, "hi": 75.0}, {"lo": 120.0})
    assert p["risk_pct"] > p["max_stop_pct"]
    assert p["risk_exceeds_max"] is True


def test_trade_plan_returns_none_without_a_zone():
    assert dr.trade_plan(103.0, None, None) is None
    assert dr.trade_plan(0.0, {"lo": 100.0, "hi": 106.0}, None) is None
    # degenerate band
    assert dr.trade_plan(103.0, {"lo": 106.0, "hi": 100.0}, None) is None


# ── entry-zone selection ──────────────────────────────────────────────────────
def test_entry_zone_prefers_the_band_price_is_inside():
    zones = [{"lo": 100, "hi": 106, "strength": 60}, {"lo": 80, "hi": 85, "strength": 99}]
    assert dr._pick_entry_zone(103, zones)["lo"] == 100


def test_entry_zone_falls_back_to_the_nearest_band_below():
    """Above every band → the NEAREST one wins, not the strongest.

    INTENT CHANGED 2026-08-16. This used to assert that a price above every band
    still returned one, on the reasoning that "the plan still points at where
    you'd want to buy". Ajay found what that produces in practice: ELVN at
    $58.82 drawing BUY $24.89-$25.29. A band you would have to fall 20%+ to
    reach is support, not an entry, so selection still prefers the nearest band
    over the stronger far one — but the result is only returned if the plan it
    implies is inside the house max stop. See the ELVN tests below.
    """
    zones = [{"lo": 95, "hi": 99, "strength": 50}, {"lo": 60, "hi": 65, "strength": 99}]
    assert dr._pick_entry_zone(103, zones)["hi"] == 99, "nearest must beat strongest"


def test_entry_zone_is_none_when_there_is_no_demand_below():
    assert dr._pick_entry_zone(50, [{"lo": 80, "hi": 85, "strength": 50}]) is None


# ── geometry contract — must not leak into the shared /zones defaults ─────────
def test_module_uses_wider_bands_than_the_zones_page_default():
    """The thin defaults made re-entry fire on noise (measured 2026-08-13).
    If someone narrows these back, this test says why they must not."""
    g = dr.zone_geom()
    assert g["merge_pct"] > pz.ZONE_MERGE_PCT
    assert g["half_width_pct"] > pz.ZONE_HALF_WIDTH_PCT


def test_price_zones_defaults_are_untouched_by_this_module():
    """REGRESSION: an earlier prototype mutated price_zones module globals to
    widen the bands, which would silently change the /zones page and
    orderflow.signals. The knobs must be per-call arguments."""
    assert pz.ZONE_MERGE_PCT == 1.75
    assert pz.ZONE_HALF_WIDTH_PCT == 0.6
    assert pz.SWING_WINDOW == 4


def test_price_zones_compute_accepts_geometry_without_changing_defaults():
    import pandas as pd

    n = 120
    df = pd.DataFrame({
        "open": [100.0] * n, "high": [101.0] * n,
        "low": [99.0] * n, "close": [100.0] * n, "volume": [1_000] * n,
    })
    before = (pz.ZONE_MERGE_PCT, pz.ZONE_HALF_WIDTH_PCT, pz.SWING_WINDOW)
    pz.compute(df, **dr.zone_geom())
    assert (pz.ZONE_MERGE_PCT, pz.ZONE_HALF_WIDTH_PCT, pz.SWING_WINDOW) == before


# ── universe contract — "S&P 500 only" must mean the S&P 500 ──────────────────
def _isolate_cache(tmp_path, monkeypatch, U):
    """Point the universe cache at tmp_path and clear source provenance."""
    monkeypatch.setattr(U, "UNIV_CACHE_DIR", tmp_path)
    monkeypatch.setattr(U, "_cache_path", lambda name: tmp_path / f"{name}.txt")
    U._LAST_SOURCE.clear()


def _dead(monkeypatch, U):
    """Make every live network loader fail, hermetically."""
    def boom(*a, **k):
        raise RuntimeError("403 Forbidden")
    monkeypatch.setattr(U, "_read_html_ua", boom)
    monkeypatch.setattr(U, "_fetch_text", boom)


def _expire(tmp_path, U, name):
    import os
    import time as _t
    old = _t.time() - (U.UNIV_CACHE_TTL_SEC + 86_400)
    os.utime(tmp_path / f"{name}.txt", (old, old))


def test_sp500_fetch_sends_a_real_user_agent(monkeypatch):
    """ROOT CAUSE (2026-08-13): `pandas.read_html(url)` fetches with the
    default urllib UA, and Wikipedia 403s that — verified in-container, where
    the default UA got 126 bytes of error page and a descriptive UA got the
    full 568 KB article. Every HTML fetch must therefore carry a real,
    non-empty, non-python-default User-Agent."""
    from sepa import universe as U

    seen = {}

    class _Resp:
        text = "<html><body><table><tr><th>Symbol</th></tr></table></body></html>"
        def raise_for_status(self): pass

    import requests
    def fake_get(url, timeout=None, headers=None):
        seen["headers"] = headers or {}
        return _Resp()
    monkeypatch.setattr(requests, "get", fake_get)

    U._fetch_text("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    ua = seen["headers"].get("User-Agent", "")
    assert ua, "no User-Agent sent — this is exactly what Wikipedia 403s"
    assert "python" not in ua.lower() and "urllib" not in ua.lower()


def test_sp500_never_hands_a_bare_url_to_pandas(monkeypatch):
    """NEGATIVE / regression lock: if anyone reverts to `pd.read_html(url)`,
    pandas does the fetching with the default UA and the 403 returns. pandas
    must only ever be given already-fetched markup."""
    from sepa import universe as U

    import pandas as pd
    captured = {}
    monkeypatch.setattr(U, "_fetch_text", lambda url, **k: "<table></table>")
    monkeypatch.setattr(pd, "read_html", lambda src, *a, **k: captured.setdefault("src", src) or [])

    U._read_html_ua("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    assert not isinstance(captured["src"], str), \
        "pandas was handed a URL/string — it will fetch it itself and get 403'd"


def test_sp500_falls_through_to_the_datahub_mirror_when_wikipedia_dies(tmp_path, monkeypatch):
    """Wikipedia is one delivery path. When it 403s again, the GitHub-raw CSV
    mirror must keep the list FRESH rather than dropping to the stale cache."""
    from sepa import universe as U
    _isolate_cache(tmp_path, monkeypatch, U)

    def boom(*a, **k):
        raise RuntimeError("403 Forbidden")
    monkeypatch.setattr(U, "_read_html_ua", boom)
    rows = "Symbol,Security\n" + "\n".join(f"SYM{i},Co {i}" for i in range(503))
    monkeypatch.setattr(U, "_fetch_text", lambda url, **k: rows)

    out = U.fetch_sp500()
    assert len(out) == 503
    assert U.last_source("sp500")["source"] == "datahub"
    # …and it must be cached, so the next call doesn't re-hit the network.
    assert (tmp_path / "sp500.txt").exists()


def test_sp500_rejects_a_truncated_parse_and_keeps_the_stale_cache(tmp_path, monkeypatch):
    """NEGATIVE: a source that parses "successfully" into 12 names (column
    renamed, interstitial page with a stray table) must NOT be cached and must
    NOT be served as the S&P 500. A real 503-name snapshot outranks it even
    when expired."""
    from sepa import universe as U
    _isolate_cache(tmp_path, monkeypatch, U)

    real = [f"SYM{i}" for i in range(503)]
    (tmp_path / "sp500.txt").write_text("\n".join(real))
    _expire(tmp_path, U, "sp500")

    monkeypatch.setattr(U, "_sp500_from_wikipedia", lambda: ["AAPL", "MSFT", "NVDA"])
    monkeypatch.setattr(U, "_sp500_from_datahub", lambda: ["AAPL", "MSFT", "NVDA"])

    out = U.fetch_sp500()
    assert len(out) == 503
    assert U.last_source("sp500")["source"] == "stale-cache"
    # the 3-name garbage must not have overwritten the good cache
    assert len((tmp_path / "sp500.txt").read_text().splitlines()) == 503


def test_sp500_prefers_a_fresh_fetch_over_the_stale_cache(tmp_path, monkeypatch):
    """The whole point of the fix: with the UA in place the live fetch works
    again, so a stale cache must be REPLACED, not preferred."""
    from sepa import universe as U
    _isolate_cache(tmp_path, monkeypatch, U)

    (tmp_path / "sp500.txt").write_text("\n".join(f"OLD{i}" for i in range(503)))
    _expire(tmp_path, U, "sp500")
    monkeypatch.setattr(U, "_sp500_from_wikipedia", lambda: [f"NEW{i}" for i in range(503)])

    out = U.fetch_sp500()
    assert out[0] == "NEW0"
    assert U.last_source("sp500")["source"] == "wikipedia"
    assert (tmp_path / "sp500.txt").read_text().startswith("NEW0")


def test_sp400_falls_back_to_stale_cache_and_never_to_curated(tmp_path, monkeypatch):
    """sp400.txt aged out alongside sp500.txt (both frozen 2026-05-29). It
    gets the same stale-cache rescue — but NEVER the curated fallback: curated
    is large-caps, and leaking those into the mid-cap layer of a union would
    silently corrupt `broad`."""
    from sepa import universe as U
    _isolate_cache(tmp_path, monkeypatch, U)

    real = [f"MID{i}" for i in range(400)]
    (tmp_path / "sp400.txt").write_text("\n".join(real))
    _expire(tmp_path, U, "sp400")
    _dead(monkeypatch, U)

    out = U.fetch_sp400()
    assert len(out) == 400
    assert out != list(U.UNIVERSE)
    assert U.last_source("sp400")["source"] == "stale-cache"


def test_sp400_returns_empty_not_curated_when_there_is_no_cache(tmp_path, monkeypatch):
    """NEGATIVE: with no cache at all, the mid-cap layer must vanish rather
    than substitute mega-caps."""
    from sepa import universe as U
    _isolate_cache(tmp_path, monkeypatch, U)
    _dead(monkeypatch, U)

    assert U.fetch_sp400() == []
    assert U.last_source("sp400")["source"] == "empty"


def test_sp500_falls_back_to_stale_cache_not_the_curated_list(tmp_path, monkeypatch):
    """REGRESSION (2026-08-13): Wikipedia answers 403, and the old fallback
    returned the 158-name curated momentum list. Scanning that and calling it
    'S&P 500' is wrong data, not a degraded mode. A stale real snapshot wins."""
    from sepa import universe as U

    monkeypatch.setattr(U, "UNIV_CACHE_DIR", tmp_path)
    monkeypatch.setattr(U, "_cache_path", lambda name: tmp_path / f"{name}.txt")
    real = [f"SYM{i}" for i in range(503)]
    (tmp_path / "sp500.txt").write_text("\n".join(real))
    # make the cache look expired, and the live fetch fail
    import os, time as _t
    old = _t.time() - (U.UNIV_CACHE_TTL_SEC + 86_400)
    os.utime(tmp_path / "sp500.txt", (old, old))

    # Kill every live loader (Wikipedia + the datahub mirror) at the network
    # seam, so the test is hermetic and doesn't depend on either being up.
    _dead(monkeypatch, U)

    out = U.fetch_sp500()
    assert len(out) == 503
    assert out != list(U.UNIVERSE)
    assert U.last_source("sp500")["source"] == "stale-cache"


# The six tests below exercise the SINGLE-LAYER sp500 path — provenance,
# staleness, curated fallback, per-symbol error handling. They pass
# universe="sp500" explicitly so they keep testing that path after the default
# moved to sp1500 (2026-08-14); a bare scan() would now resolve three layers
# and call fetchers these tests do not stub.
def test_scan_reports_when_the_universe_is_not_actually_sp500(monkeypatch):
    """If we ever DO fall through to curated, the payload must say so — the
    page must never silently claim 'S&P 500' over the wrong names."""
    from sepa import universe as U

    monkeypatch.setattr(dr.universe_mod, "load_universe", lambda mode=None: list(U.UNIVERSE))
    monkeypatch.setattr(dr, "analyze_symbol", lambda s, with_series=False: None)
    dr._cache.clear()

    out = dr.scan(force=True, universe="sp500")
    assert out["universe_is_sp500"] is False
    assert "curated" in out["universe_note"].lower()


def test_scan_marks_a_real_sp500_universe_as_such(monkeypatch):
    monkeypatch.setattr(dr.universe_mod, "load_universe", lambda mode=None: [f"S{i}" for i in range(503)])
    monkeypatch.setattr(dr, "analyze_symbol", lambda s, with_series=False: None)
    dr._cache.clear()

    out = dr.scan(force=True, universe="sp500")
    assert out["universe_is_sp500"] is True
    assert out["universe"] == 503


def test_falling_knife_is_excluded_even_with_a_clean_reentry(monkeypatch):
    """REGRESSION (2026-08-13): the Minervini trend template passed CIEN at 7/8
    while its swing lows read 424 -> 404 -> 359 -> 323 and its 50-day was
    falling. Three of that day's four board names were knives. The guard is now
    swing-lows + 50-day slope, and it must veto the whole re-entry."""
    from supply_demand import sd_liquidity as liq

    falling = {"trend": "falling", "swing_lows": [424, 404, 359, 323],
               "last_two": [359, 323]}
    assert liq.is_falling_knife(falling, 330.0, ma50=340.0, ma50_prior=380.0) is True
    # one shakeout low inside an uptrend must NOT disqualify: both must agree
    assert liq.is_falling_knife(falling, 330.0, ma50=380.0, ma50_prior=340.0) is False
    rising = {"trend": "rising", "swing_lows": [300, 320], "last_two": [300, 320]}
    assert liq.is_falling_knife(rising, 330.0, ma50=340.0, ma50_prior=380.0) is False


def test_module_no_longer_imports_the_minervini_trend_template():
    """Ajay 2026-08-13: "Oh ignore the minervini for this please in the S/D."
    Supply/demand is a separate strategy; this coupling must not come back."""
    import inspect
    from supply_demand import demand_reentry as _dr
    src = inspect.getsource(_dr)
    assert "trend_template" not in src
    assert "MIN_TREND_CHECKS" not in src


def test_scan_only_keeps_reentry_hits_and_ranks_freshest_first(monkeypatch):
    rows = {
        "AAA": {"is_reentry": True, "bars_since_above": 5,
                "entry_zone": {"strength": 90}, "fell_from_pct": 10},
        "BBB": {"is_reentry": True, "bars_since_above": 1,
                "entry_zone": {"strength": 50}, "fell_from_pct": 20},
        "CCC": {"is_reentry": False, "bars_since_above": 0,
                "entry_zone": {"strength": 99}, "fell_from_pct": 30},
    }
    monkeypatch.setattr(dr.universe_mod, "load_universe", lambda mode=None: list(rows))
    monkeypatch.setattr(dr, "analyze_symbol",
                        lambda s, with_series=False: {**rows[s], "symbol": s})
    dr._cache.clear()

    out = dr.scan(force=True)
    assert [r["symbol"] for r in out["rows"]] == ["BBB", "AAA"]   # CCC excluded
    assert out["scanned"] == 3 and out["n"] == 2


def test_scan_survives_a_symbol_that_raises(monkeypatch):
    """One bad ticker must not kill the whole scan."""
    def boom(sym, with_series=False):
        if sym == "BAD":
            raise ValueError("no data")
        return {"symbol": sym, "is_reentry": True, "bars_since_above": 1,
                "entry_zone": {"strength": 80}, "fell_from_pct": 9}

    monkeypatch.setattr(dr.universe_mod, "load_universe", lambda mode=None: ["GOOD", "BAD"])
    monkeypatch.setattr(dr, "analyze_symbol", boom)
    dr._cache.clear()

    out = dr.scan(force=True, universe="sp500")
    assert out["errors"] == 1
    assert [r["symbol"] for r in out["rows"]] == ["GOOD"]


def test_scan_reports_how_stale_the_constituent_list_is(monkeypatch):
    """THE SILENT-DEGRADE HOLE (2026-08-13): falling through to curated is
    loud (`universe_is_sp500` goes False), but a stale cache holds the REAL
    constituents and so looked identical to a fresh list at the call site.
    It sat 76 days out of date with nothing on the page saying so."""
    from sepa import universe as U

    syms = [f"S{i}" for i in range(503)]
    monkeypatch.setattr(dr.universe_mod, "load_universe", lambda mode=None: syms)
    monkeypatch.setattr(dr.universe_mod, "last_source",
                        lambda name: {"source": "stale-cache", "n": 503, "age_days": 76.4})
    monkeypatch.setattr(dr, "analyze_symbol", lambda s, with_series=False: None)
    dr._cache.clear()

    out = dr.scan(force=True, universe="sp500")
    assert out["universe_is_sp500"] is True      # still the real names…
    assert out["universe_stale_days"] == 76      # …but 76 days frozen
    assert out["universe_source"] == "stale-cache"
    assert "76-day-old" in out["universe_note"]


def test_scan_reports_no_staleness_when_the_list_is_fresh(monkeypatch):
    """NEGATIVE: a fresh list must not raise a false staleness warning."""
    syms = [f"S{i}" for i in range(503)]
    monkeypatch.setattr(dr.universe_mod, "load_universe", lambda mode=None: syms)
    monkeypatch.setattr(dr.universe_mod, "last_source",
                        lambda name: {"source": "wikipedia", "n": 503, "age_days": 0.0})
    monkeypatch.setattr(dr, "analyze_symbol", lambda s, with_series=False: None)
    dr._cache.clear()

    out = dr.scan(force=True, universe="sp500")
    assert out["universe_stale_days"] is None
    assert out["universe_source"] == "wikipedia"
    assert "old" not in out["universe_note"]


def test_scan_ignores_a_provenance_record_that_does_not_match(monkeypatch):
    """NEGATIVE: `last_source` is module-global and can be left over from an
    earlier resolve (or from a test double standing in for the loader). If it
    doesn't describe the list we actually got back, it must be ignored rather
    than mislabel the scan."""
    monkeypatch.setattr(dr.universe_mod, "load_universe", lambda mode=None: ["AAA", "BBB"])
    monkeypatch.setattr(dr.universe_mod, "last_source",
                        lambda name: {"source": "stale-cache", "n": 503, "age_days": 99.0})
    monkeypatch.setattr(dr, "analyze_symbol", lambda s, with_series=False: None)
    dr._cache.clear()

    out = dr.scan(force=True, universe="sp500")
    assert out["universe_stale_days"] is None
    assert out["universe_source"] is None


# ── universe expansion (2026-08-13) ──────────────────────────────────────────
def test_sp1500_is_the_union_of_the_three_layers_deduped(monkeypatch):
    """Ajay: "expand the scan to best companies beyond S and p 500 increase in
    to 1000 others". S&P 400 + 600 add ~1,000 index-quality names."""
    from sepa import universe as U
    monkeypatch.setattr(U, "fetch_sp500", lambda: ["A", "B"])
    monkeypatch.setattr(U, "fetch_sp400", lambda: ["B", "C"])     # B overlaps
    monkeypatch.setattr(U, "fetch_sp600", lambda: ["D"])
    out = U.fetch_sp1500()
    assert out == ["A", "B", "C", "D"]                            # order-stable, deduped


def test_sp600_never_falls_back_to_the_curated_list(tmp_path, monkeypatch):
    """A large-cap list leaking into the small-cap layer would corrupt any
    union, so the last resort for sp600 is [] — same rule as sp400."""
    from sepa import universe as U
    monkeypatch.setattr(U, "_cache_path", lambda name: tmp_path / f"{name}.txt")
    monkeypatch.setattr(U, "_read_html_ua",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("403")))
    U._LAST_SOURCE.clear()
    assert U.fetch_sp600() == []
    assert U.last_source("sp600")["source"] == "empty"


def test_unknown_universe_key_falls_back_to_the_default(monkeypatch):
    """Whatever DEFAULT_UNIVERSE is, a bogus key must land on it rather than
    raising or scanning nothing. (Default became the SEPA `full` alias on
    2026-08-25.)"""
    monkeypatch.setattr(dr.universe_mod, "load_universe", lambda mode=None: ["AAA"])
    _, _, _, _, key = dr._resolve_universe("not-a-universe")
    assert key == dr.DEFAULT_UNIVERSE
    assert key in dr.UNIVERSES


def test_default_universe_is_the_sepa_full_alias():
    """Ajay 2026-08-25: "Remove all these themes and just do default universe
    scan" + "I need full universe scanned for this". One universe, the same
    `full` alias the SEPA scanner runs, so the two engines can never fish
    different waters again."""
    assert dr.DEFAULT_UNIVERSE == "full"
    assert set(dr.UNIVERSES) == {"full"}


def test_universe_staleness_still_surfaces_through_the_full_alias(monkeypatch):
    """The layering moved into sepa/universe.load_universe("full") on
    2026-08-25, but a frozen constituent list must STILL stamp the payload —
    that was the 76-day silent hole of 2026-08-13."""
    monkeypatch.setattr(dr.universe_mod, "load_universe", lambda mode=None: ["A", "B"])
    monkeypatch.setattr(dr.universe_mod, "last_source",
                        lambda name: {"source": "stale-cache", "n": 2, "age_days": 91.0})
    _, _, prov, stale, key = dr._resolve_universe("sp1500")
    assert key == "full" and stale == 91
    assert set(prov) == {"full"}


def test_a_failing_loader_yields_an_empty_universe_not_a_crash(monkeypatch):
    monkeypatch.setattr(dr.universe_mod, "load_universe",
                        lambda mode=None: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(dr.universe_mod, "last_source", lambda name: None)
    syms, _, _, _, _ = dr._resolve_universe("full")
    assert syms == []                     # empty and loud upstream, not a 500


def test_legacy_universe_keys_share_the_one_full_cache(monkeypatch):
    """FLIP of the 2026-08-14 per-universe-cache regression: with ONE universe
    (2026-08-25), every legacy key — sp500 bookmarks, sp1500 cron lines,
    qqq history — must land on the SAME cached scan, not warm five."""
    calls = {"n": 0}

    def load(mode=None):
        calls["n"] += 1
        return ["A", "B", "C"]

    monkeypatch.setattr(dr.universe_mod, "load_universe", load)
    monkeypatch.setattr(dr.universe_mod, "last_source", lambda name: None)
    monkeypatch.setattr(dr, "analyze_symbol", lambda s, with_series=False: None)
    dr._cache.clear()

    first = dr.scan(force=True, universe="sp500")
    assert first["universe"] == 3 and first["cached"] is False
    assert dr.scan(universe="sp1500")["cached"] is True
    assert dr.scan(universe="sp1500_plus")["cached"] is True
    assert calls["n"] == 1, "a legacy key re-resolved the universe"


def test_entry_zone_does_not_fall_off_a_cliff_four_cents_below_a_band():
    """REGRESSION (VRT, 2026-08-13): price $287.07 against a $287.11-293.88
    band — four cents under the floor, so the band did not count as "inside"
    and the picker fell through to the next band down at $159-163, 45% away.
    The resulting plan quoted a 45.5% stop and a target at the current price."""
    zones = [{"lo": 287.11, "hi": 293.88, "strength": 80},
             {"lo": 159.0, "hi": 163.0, "strength": 50},
             {"lo": 148.0, "hi": 149.0, "strength": 40}]
    assert dr._pick_entry_zone(287.07, zones)["lo"] == 287.11


def test_entry_zone_still_prefers_a_band_at_or_below_price():
    """The near-miss tolerance must not start preferring overhead bands when a
    perfectly good one sits just under price."""
    zones = [{"lo": 101.0, "hi": 103.0, "strength": 90},   # just ABOVE
             {"lo": 97.0, "hi": 99.5, "strength": 50}]     # just BELOW
    assert dr._pick_entry_zone(100.0, zones)["lo"] == 97.0


def test_entry_zone_rejects_a_band_beyond_the_near_miss_tolerance():
    """Price 5% under the only band is a breakdown, not an approach."""
    assert dr._pick_entry_zone(273.0, [{"lo": 287.11, "hi": 293.88, "strength": 80}]) is None


def test_target_is_never_inside_or_below_the_entry_band():
    """REGRESSION (VRT, 2026-08-13): the target came from
    `nearest_resistance` = "first band above SPOT". With price four cents under
    its own entry band, that band was the nearest thing above, so the plan
    targeted its own floor — a 0.01R trade."""
    zone = {"lo": 287.11, "hi": 293.88, "touches": 3, "strength": 80}
    supply = [{"lo": 287.11, "hi": 293.88}, {"lo": 277.0, "hi": 282.0},
              {"lo": 305.0, "hi": 310.0}]
    p = dr.trade_plan(287.07, zone, supply)
    assert p["target"] == 305.0                 # NOT 287.11, NOT 277.0
    assert p["target"] > zone["hi"]
    assert p["rr"] and p["rr"] > 1


def test_trade_plan_still_accepts_a_single_resistance_band():
    """Back-compat: the older call passed one band, not a list."""
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0, "hi": 122.0})
    assert p["target"] == 120.0


def test_universe_key_tolerates_a_non_string(monkeypatch):
    """REGRESSION (2026-08-14): FastAPI resolves Query(...) defaults at request
    time, so calling a handler directly hands `scan` the Query OBJECT and
    `(universe or DEFAULT).lower()` raised AttributeError. HTTP was fine; the
    in-container smoke check was not. Anything unusable falls back."""
    class Weird:                       # stands in for fastapi.Query
        pass
    assert dr._universe_key(Weird()) == dr.DEFAULT_UNIVERSE
    assert dr._universe_key(None) == dr.DEFAULT_UNIVERSE
    assert dr._universe_key("") == dr.DEFAULT_UNIVERSE
    assert dr._universe_key("  FULL  ") == "full"
    assert dr._universe_key("sp500") == dr.DEFAULT_UNIVERSE   # legacy keys collapse
    assert dr._universe_key("nonsense") == dr.DEFAULT_UNIVERSE


def test_scan_coerces_a_non_bool_force(monkeypatch):
    """REGRESSION (2026-08-14): FastAPI Query(...) defaults resolve at request
    time, so a direct call passed the Query OBJECT as `force`. It is truthy, so
    `if not force` never fired and every in-container call recomputed the whole
    universe instead of serving the 3h cache — which is also what made the cold
    path look far slower than it was."""
    class Weird:
        pass
    monkeypatch.setattr(dr.universe_mod, "load_universe", lambda mode=None: ["AAA"])
    monkeypatch.setattr(dr.universe_mod, "last_source", lambda name: None)
    monkeypatch.setattr(dr, "analyze_symbol", lambda s, with_series=False: None)
    monkeypatch.setattr(dr, "_attach_venues", lambda rows, **k: None)
    dr._cache.clear()

    first = dr.scan(force=True, universe="sp500")
    assert first["cached"] is False
    second = dr.scan(force=Weird(), universe="sp500")   # must NOT be read as force
    assert second["cached"] is True


# ---------------------------------------------------------------------------
# Theme universe (Ajay 2026-08-15: "make sure the new companies like Quantum
# based and Power based and robotics based and then Semis all are considered")
# ---------------------------------------------------------------------------
def test_pinned_etfs_ride_the_demand_universe_with_their_own_seat(monkeypatch):
    """Ajay 2026-08-28: "add gold and silve ... with their supply demand
    zones" + SPY/QQQ/TQQQ/SOXL and the AI-infra roster. Pinned ETFs are
    appended AFTER the loader, deduped, and carry a "pinned" provenance
    record so nothing mistakes them for index constituents."""
    monkeypatch.setattr(dr, "PINNED_ETFS", ("GLD", "SLV"))
    monkeypatch.setattr(dr.universe_mod, "load_universe",
                        lambda mode=None: ["A", "GLD"])   # GLD already present
    monkeypatch.setattr(dr.universe_mod, "last_source", lambda name: None)
    syms, _, prov, _, key = dr._resolve_universe("full")
    assert syms == ["A", "GLD", "SLV"]                    # deduped, order kept
    assert prov["pinned"] == {"source": "pinned", "n": 1}  # only SLV was new


def test_the_roster_is_liquidity_screened_and_clean():
    """The real PINNED_ETFS roster: his explicit asks present, the known
    dead/thin tickers absent, no dupes, all uppercase. FIVG died twice
    (→SIXG→UFOX) and SRVR loses to DTCR on every timeframe — resurrecting
    either would mean someone pasted an old list over the vetted one."""
    real = _REAL_PINNED_ETFS
    for must in ("GLD", "SLV", "SPY", "QQQ", "TQQQ", "SOXL", "QTUM", "REMX",
                 "LYTE", "KOID", "IBIT", "NUKZ", "AIPO", "DRAM"):
        assert must in real, f"{must} fell off the roster"
    for dead in ("FIVG", "SRVR", "HUMN", "BOAT", "IVEP", "NCLD"):
        assert dead not in real, f"{dead} is dead/thin and must stay out"
    assert len(real) == len(set(real))
    assert all(s == s.upper() and s.strip() == s for s in real)


def test_pinned_etfs_never_reach_the_sepa_universe_alias():
    """The one-definition rule holds for STOCKS: sepa/universe.py's `full`
    alias must NOT grow ETFs — the fundamental scanner never sees them."""
    from sepa import universe as U
    assert "pinned" not in U._UNIVERSE_ALIASES.get("full", ())
    import inspect
    assert "PINNED_ETFS" not in inspect.getsource(U)


def test_curated_fallthrough_detection_survives_the_pin(monkeypatch):
    """REGRESSION GUARD: looks_curated used a bare length equality; the
    pinned tail would have shifted it by len(PINNED_ETFS) and silently
    broken the loud fallthrough warning."""
    from sepa import universe as U
    monkeypatch.setattr(dr, "PINNED_ETFS", ("GLD", "SLV"))
    monkeypatch.setattr(dr.universe_mod, "load_universe",
                        lambda mode=None: list(U.UNIVERSE))
    monkeypatch.setattr(dr.universe_mod, "last_source", lambda name: None)
    monkeypatch.setattr(dr, "analyze_symbol", lambda s, with_series=False: None)
    dr._cache.clear()
    out = dr.scan(force=True, universe="full")
    assert out["universe_is_sp500"] is False
    assert "curated" in out["universe_note"]


def test_legacy_alias_resolves_through_the_sepa_full_loader(monkeypatch):
    """sp1500_plus / qqq / sp500 lived in a demand-side composite map until
    2026-08-25. They now normalise to the SEPA `full` alias so both engines
    fish the same waters; the union/dedupe itself is tested where it lives,
    in test_universe_resolution.py."""
    seen = {}

    def load(mode=None):
        seen["mode"] = mode
        return ["A", "IONQ"]

    monkeypatch.setattr(dr.universe_mod, "load_universe", load)
    monkeypatch.setattr(dr.universe_mod, "last_source", lambda name: None)
    syms, _, prov, _, key = dr._resolve_universe("sp1500_plus")
    assert key == "full" and syms == ["A", "IONQ"]
    assert seen["mode"] == "full"
    assert set(prov) == {"full"}


def test_theme_rosters_actually_contain_the_names_ajay_asked_for():
    """The point of the list. If someone prunes it, this fails loudly."""
    from sepa import universe as U
    names = set(U.fetch_themes())
    for t in ("IONQ", "RGTI", "QBTS", "QUBT",      # quantum
              "OKLO", "SMR", "NNE",                 # power / nuclear
              "SERV", "RR", "SYM",                  # robotics
              "ARM", "ALAB", "CRDO"):               # semis outside the indices
        assert t in names, f"{t} dropped out of the theme rosters"
    assert len(names) == len(set(names)), "theme rosters emit a duplicate"


def test_traction_smallcaps_joined_the_rosters_2026_08_28():
    """Ajay: "Companies like Fermi, Indi Semis and Light path, UI path, oust
    ... research this list and add it to Universe please. but categorize
    them or add a chip." His five resolve to a theme, the
    outside-every-index adds now reach `full` via the themes layer, and the
    two new policy themes exist with priorities."""
    from sepa import universe as U
    for sym, theme in (("FRMI", "ai_power"), ("INDI", "robotics"),
                       ("LPTH", "optical"), ("PATH", "robotics"),
                       ("OUST", "robotics"),
                       ("ONDS", "defense"), ("RCAT", "defense"),
                       ("KTOS", "defense"), ("UUUU", "rare_earth"),
                       ("MP", "rare_earth"), ("VOYG", "space"),
                       ("AMBA", "robotics"), ("VIAV", "optical"),
                       ("UCTT", "ai_semis"), ("MIR", "nuclear")):
        assert U.theme_for(sym) == theme, f"{sym} != {theme}"
    names = set(U.fetch_themes())
    for outside_index in ("INDI", "LPTH", "ONDS", "RCAT", "VOYG",
                          "USAR", "UUUU", "METC", "AMBA", "ALNT"):
        assert outside_index in names, f"{outside_index} not reaching full"
    assert U.THEME_PRIORITY["defense"] > U.THEME_PRIORITY["ai_infra"]
    assert U.THEME_PRIORITY["rare_earth"] > U.THEME_PRIORITY["defense"]


def test_theme_lookup_is_total_and_never_raises():
    from sepa import universe as U
    assert U.theme_for("IONQ") == "quantum"
    assert U.theme_for("  ionq ") == "quantum"
    assert U.theme_for("KO") is None
    assert U.theme_for("") is None
    assert U.theme_for(None) is None
    assert U.theme_for(123) is None


def test_broad_universe_includes_the_theme_rosters(monkeypatch):
    """Ajay 2026-08-15: "make sure the new companies ... all are considered."

    The nightly fast-scan runs `--mode broad`, which feeds the Strong VCP
    board. Measured 2026-08-15: 40 of 42 theme names already arrived via
    curated + russell1000, but ARQQ and SYM reached NO layer, so those two
    could never appear. Broad must union the rosters explicitly.
    """
    from sepa import universe as U
    monkeypatch.setattr(U, "fetch_sp500", lambda: ["SPX1"])
    monkeypatch.setattr(U, "fetch_sp400", lambda: ["MID1"])
    monkeypatch.setattr(U, "fetch_russell3000", lambda: ["R1"])
    monkeypatch.setattr(U, "fetch_microcap", lambda: [])
    monkeypatch.setattr(U, "fetch_etf_universe", lambda: ["SPY"])

    broad = set(U.fetch_broad())
    for t in U.fetch_themes():
        assert t in broad, f"{t} is in no broad-mode layer"
    # and the pre-existing layers are untouched
    assert {"SPX1", "MID1", "R1", "SPY"} <= broad


def test_broad_universe_has_no_duplicates(monkeypatch):
    """NVDA is in curated AND ai_semis AND sp500. A duplicate means the
    scanner analyses the same name several times per run."""
    from sepa import universe as U
    monkeypatch.setattr(U, "fetch_sp500", lambda: ["NVDA", "SPX1"])
    monkeypatch.setattr(U, "fetch_sp400", lambda: [])
    monkeypatch.setattr(U, "fetch_russell3000", lambda: ["NVDA"])
    monkeypatch.setattr(U, "fetch_microcap", lambda: [])
    monkeypatch.setattr(U, "fetch_etf_universe", lambda: [])

    broad = U.fetch_broad()
    assert len(broad) == len(set(broad))
    assert broad.count("NVDA") == 1


# ── entry zone must be an ENTRY, not distant support ──────────────────────────
# Ajay 2026-08-16, on the ELVN Setup tab: "For the SEPA list why are the zones
# all messed up?"
#
# ELVN traded at $58.82 and the page drew BUY $24.89-$25.29, STOP $24.52 — a buy
# zone 57% below spot. The plan mixed two reference prices: entry_low/high from
# the band, but entry_ref/risk_pct/rr from SPOT, giving risk_pct 58.3% and
# rr 0.07 against a target lifted from resistance just above spot.
def test_a_band_far_below_price_is_support_not_an_entry():
    """The ELVN case, to the cent."""
    assert dr._pick_entry_zone(58.82, [{"lo": 24.89, "hi": 25.29, "strength": 45}]) is None


def test_the_gate_is_measured_to_the_stop_not_the_band_top():
    """SYRE showed why. At $103.63 with a band at $90.75-93.99 the band TOP is
    9.3% away — inside a 10% tolerance — while the stop under the band FLOOR is
    13.7% away. A band-distance gate would have passed a plan carrying a risk
    the house cap forbids."""
    band = {"lo": 90.75, "hi": 93.99, "strength": 60}
    assert (103.63 - band["hi"]) / 103.63 * 100 < 10.0      # band top looks fine
    assert dr._pick_entry_zone(103.63, [band]) is None       # the stop does not


def test_a_band_within_the_stop_cap_is_still_an_entry():
    """Negative: the guard must not eat legitimate pullback entries. PNC at
    $256.97 against a band at $242.29-250.93 is a 7.1% plan — inside the cap."""
    band = {"lo": 242.29, "hi": 250.93, "strength": 60}
    assert dr._pick_entry_zone(256.97, [band]) == band


def test_price_inside_the_band_is_never_gated():
    """The Back in Demand board requires price INSIDE the band, so this guard
    can never remove a row from it."""
    band = {"lo": 68.98, "hi": 71.56, "strength": 65}
    assert dr._pick_entry_zone(69.62, [band]) == band


def test_the_near_miss_above_price_still_works():
    """Regression on the VRT four-cent case the ABOVE tolerance exists for —
    the new BELOW tolerance must not disturb it."""
    band = {"lo": 287.11, "hi": 293.88, "strength": 70}
    assert dr._pick_entry_zone(287.07, [band]) == band


def test_the_tolerance_is_the_house_max_stop_not_a_new_number():
    """Anchored to the p.299/p.301 cap rather than an invented constant, so it
    moves with the risk rules instead of drifting from them."""
    from trading.risk_rules import ABS_MAX_STOP_PCT
    assert dr._entry_below_tol_pct() == float(ABS_MAX_STOP_PCT)


def test_the_bands_themselves_are_untouched_by_the_gate():
    """Only the BUY/STOP lines go away. The demand bands are read from
    `demand_zones`, which the entry picker never filters."""
    import inspect
    src = inspect.getsource(dr._pick_entry_zone)
    assert "demand_zones" in src
    assert "return None" in src


# ---------------------------------------------------------------------------
# The Setup-tab chart series — Ajay 2026-08-16
# ---------------------------------------------------------------------------
# Two asks in one message: "is there any way we can use trading view charts? ...
# I wanna be able to hover on the pricing" and "can you also add volume please".
# The series was `{date, close}` only, so neither a candle nor a volume bar
# could be drawn. It also carried a fixed 180 bars while zones are computed over
# 252 (price_zones.LOOKBACK_BARS), which put a band's own defining touches off
# the left edge of the chart that was supposed to justify it.
def _ohlc_frame(n=300, start=100.0):
    pd = pytest.importorskip("pandas")
    idx = pd.bdate_range("2024-01-01", periods=n)
    close = [start + i * 0.1 for i in range(n)]
    return pd.DataFrame({
        "open":   [c - 0.5 for c in close],
        "high":   [c + 1.0 for c in close],
        "low":    [c - 1.0 for c in close],
        "close":  close,
        "volume": [1_000_000 + i for i in range(n)],
    }, index=idx)


def test_series_carries_ohlc_and_volume():
    """A candlestick chart needs open/high/low and a volume histogram needs
    volume. The payload had neither."""
    out = dr._series_for_chart(_ohlc_frame(), 10)
    assert len(out) == 10
    bar = out[-1]
    assert set(bar) == {"date", "open", "high", "low", "close", "volume"}
    assert bar["high"] >= bar["close"] >= bar["low"]
    assert isinstance(bar["volume"], int), "volume is a count, not a price"


def test_close_is_still_present_so_nothing_downstream_breaks():
    out = dr._series_for_chart(_ohlc_frame(), 5)
    assert all(isinstance(b["close"], float) for b in out)


def test_volume_is_not_rounded_to_cents():
    pd = pytest.importorskip("pandas")
    df = _ohlc_frame(3)
    df.loc[df.index[-1], "volume"] = 531_156
    assert dr._series_for_chart(df, 1)[0]["volume"] == 531_156


def test_a_bar_missing_ohl_degenerates_to_a_doji_rather_than_vanishing():
    """A hole would shift every later bar and silently mis-place the bands
    against the price. A flat candle is visibly odd; a shifted chart is not."""
    pd = pytest.importorskip("pandas")
    df = _ohlc_frame(4)
    for col in ("open", "high", "low"):
        df.loc[df.index[-1], col] = float("nan")
    out = dr._series_for_chart(df, 4)
    assert len(out) == 4
    last = out[-1]
    assert last["open"] == last["high"] == last["low"] == last["close"]


def test_a_bar_with_no_close_is_dropped():
    pd = pytest.importorskip("pandas")
    df = _ohlc_frame(4)
    df.loc[df.index[-1], "close"] = float("nan")
    assert len(dr._series_for_chart(df, 4)) == 3


def test_missing_volume_is_null_not_zero():
    """A zero column reads as 'nobody traded', which a missing field does not
    support."""
    pd = pytest.importorskip("pandas")
    df = _ohlc_frame(3)
    df.loc[df.index[-1], "volume"] = float("nan")
    assert dr._series_for_chart(df, 1)[0]["volume"] is None


# --- the window ---
def test_the_window_reaches_back_past_the_bands_oldest_touch():
    """A band whose oldest defining swing is 200 bars back was drawn on a
    180-bar chart, so it appeared to rest on nothing."""
    assert dr.series_window({"oldest_touch_bars": 200}) == 215


def test_the_window_never_drops_below_the_legibility_floor():
    assert dr.series_window({"oldest_touch_bars": 3}) == dr.SERIES_BARS_MIN


def test_the_window_never_exceeds_one_trading_year():
    assert dr.series_window({"oldest_touch_bars": 900}) == dr.SERIES_BARS_MAX


def test_the_window_matches_the_chart_maps_rule():
    """The Setup tab and the /chart-maps tiles must frame the same band the
    same way, or the two surfaces disagree about the same stock."""
    from chart_maps import board
    for oldest in (0, 50, 120, 200, 300):
        assert dr.series_window({"oldest_touch_bars": oldest}) == \
            board._zone_window({"oldest_touch_bars": oldest})


# --- negatives ---
def test_a_zone_without_the_field_falls_back_to_the_default():
    """Older cached payloads have no oldest_touch_bars."""
    assert dr.series_window({}) == dr.SERIES_BARS_DEFAULT
    assert dr.series_window(None) == dr.SERIES_BARS_DEFAULT
    assert dr.series_window({"oldest_touch_bars": None}) == dr.SERIES_BARS_DEFAULT
    assert dr.series_window({"oldest_touch_bars": "junk"}) == dr.SERIES_BARS_DEFAULT


def test_asking_for_more_bars_than_exist_is_not_an_error():
    out = dr._series_for_chart(_ohlc_frame(20), 250)
    assert len(out) == 20


# ═════════════════════════════════════════════════════════════════════════════
# THE BROKEN-BAND GUARD  (Ajay 2026-08-17, on NBIX)
#
#   "There are two different buys in the NBIX stock one on chart, We fell below
#    the demand zone but you still say buy in one place."
#
# `reentry_read`'s docstring already said "a name below the floor has broken
# support, which is the opposite of this signal" — but `in_band` only tested the
# LAST price, so a name that fell through the floor, CLOSED under it, and bounced
# back the next session read as a clean re-entry. Spec:
#   docs/supply_demand/broken_band_guard.md
# ═════════════════════════════════════════════════════════════════════════════

def test_a_close_below_the_floor_disqualifies_the_reentry():
    """The behavioural case. Ran to 120, fell back through the 100 floor and
    CLOSED at 96, then bounced to 103 — inside the band again, but the band
    failed on the way there."""
    out = dr.reentry_read([100, 110, 120, 96, 103], zone_hi=106, zone_lo=100,
                          last_price=103)
    assert out["in_band"] is True, "price really is inside the band"
    assert out["broke_below"] is True
    assert out["is_reentry"] is False, "a band that broke is not a buy"


def test_the_break_evidence_is_reported_even_though_the_row_is_refused():
    """The page has to be able to say WHY a name sitting in its band is not a
    buy — a bare False sends him back to the chart to work it out."""
    out = dr.reentry_read([100, 110, 120, 96, 103], zone_hi=106, zone_lo=100,
                          last_price=103)
    assert out["bars_since_break"] == 1, "broke yesterday, back inside today"
    assert out["lowest_close_pct_below"] == 4.0, "96 is 4% under the 100 floor"


def test_bars_since_break_counts_from_the_LAST_break_not_the_first():
    out = dr.reentry_read([100, 120, 95, 103, 97, 103], zone_hi=106, zone_lo=100,
                          last_price=103)
    assert out["bars_since_break"] == 1


def test_the_deepest_close_is_reported_not_the_most_recent_one():
    """How badly it failed is the useful number; the last break may be shallow."""
    out = dr.reentry_read([100, 120, 90, 99, 103], zone_hi=106, zone_lo=100,
                          last_price=103)
    assert out["lowest_close_pct_below"] == 10.0


def test_a_break_from_BEFORE_the_run_up_is_old_structure_and_still_qualifies():
    """Scoping matters. A close under the floor, then a 20% run above the whole
    band, then a pullback into it is the healthy case this signal exists to
    find — the market already answered that old break by rallying through it."""
    out = dr.reentry_read([95, 100, 120, 103], zone_hi=106, zone_lo=100,
                          last_price=103)
    assert out["broke_below"] is False
    assert out["is_reentry"] is True


def test_a_close_exactly_ON_the_floor_is_not_a_break():
    """A test of support IS the band working. Strictly below, or the guard
    rejects every zone that ever got tested — which is all of them."""
    out = dr.reentry_read([100, 120, 100.0, 103], zone_hi=106, zone_lo=100,
                          last_price=103)
    assert out["broke_below"] is False
    assert out["is_reentry"] is True


def test_the_guard_reads_CLOSES_so_an_intraday_wick_does_not_disqualify():
    """Deliberate. Wicking through a band is how demand zones get tested in the
    first place; failing on a wick rejects the healthy case. `reentry_read`
    takes closes only — this pins that the caller never starts handing it lows.
    (The mirror-image rule, `stop_recently_hit`, DOES read lows: see below.)"""
    import inspect
    src = inspect.getsource(dr.decide_from_frame)
    assert 'reentry_read(closes,' in src, "reentry_read must be fed closes"
    assert 'reentry_read(lows' not in src


def test_the_break_fields_exist_on_every_return_path():
    """The FE reads these keys unconditionally; a missing key is a crash, and a
    short-circuit return is exactly where one goes missing."""
    keys = {"broke_below", "bars_since_break", "lowest_close_pct_below"}
    for out in (dr.reentry_read([], 106, 100, 103),          # no closes
                dr.reentry_read([100, 110], 0, 0, 103),      # degenerate band
                dr.reentry_read([100, 110], 100, 106, 103),  # inverted band
                dr.reentry_read([100, 110], 106, 100, 999),  # not in band
                dr.reentry_read([100, 110, 120, 103], 106, 100, 103)):  # clean
        assert keys <= set(out), f"missing break keys: {keys - set(out)}"


def test_the_break_defaults_to_False_not_None_when_it_was_checked():
    """False = checked and clean. The UI branches on it, so it must not be
    falsy-by-absence."""
    out = dr.reentry_read([100, 110, 120, 103], 106, 100, 103)
    assert out["broke_below"] is False
    assert out["bars_since_break"] is None
    assert out["lowest_close_pct_below"] is None


def test_a_break_outside_the_lookback_window_is_not_counted():
    """Same window the rest of the read uses — a break 200 bars ago against a
    band that has been retested since is not today's structure."""
    closes = [80] + [120] * 5 + [103] * 40
    out = dr.reentry_read(closes, 106, 100, 103, lookback=40)
    assert out["broke_below"] is False


# ── the real NBIX bars — the regression ──────────────────────────────────────
def test_the_real_NBIX_case_is_refused():
    """NBIX, 2026-08-14, on the live board. Entry band $152.54-155.30
    (3x tested, strength 45), plan Buy $152.54-155.30 / Stop $150.25 / 2.0R,
    verdict AT_DEMAND "support is right here", entry read FAVORABLE:

        2026-08-12  close 156.49                 above the band
        2026-08-13  close 150.82   <- CLOSED below the 152.54 floor
        2026-08-14  close 152.72                 back inside

    It bounced back over the floor, so `in_band` was true and every other gate
    passed. The band had already failed."""
    closes = [140.0, 150.0, 163.5, 158.0, 156.49, 150.82, 152.72]
    out = dr.reentry_read(closes, zone_hi=155.30, zone_lo=152.54, last_price=152.72)
    assert out["in_band"] is True
    assert out["fell_from_pct"] == 5.3, "it really did run 5%+ above the band"
    assert out["broke_below"] is True
    assert out["bars_since_break"] == 1
    assert out["lowest_close_pct_below"] == 1.13
    assert out["is_reentry"] is False, "NBIX must not read as back-in-demand"


def test_NBIX_would_still_have_qualified_without_the_break():
    """Proves the guard is what refused it, not some other gate that was
    already failing — otherwise this regression test would pass for the wrong
    reason and go on passing if the guard were deleted."""
    closes = [140.0, 150.0, 163.5, 158.0, 156.49, 153.90, 152.72]
    out = dr.reentry_read(closes, zone_hi=155.30, zone_lo=152.54, last_price=152.72)
    assert out["is_reentry"] is True


# ═════════════════════════════════════════════════════════════════════════════
# THE ALREADY-RUN STOP  (same NBIX report)
#
# The board offered a $150.25 stop on the morning NBIX printed a $148.78 low.
# A stop the market has already traded through is not a stop — the plan it
# belongs to was stopped out before it was quoted. WARNS, does not gate.
# ═════════════════════════════════════════════════════════════════════════════

def test_a_low_under_the_proposed_stop_is_flagged():
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0},
                      recent_lows=[102.0, 101.0, 97.0, 102.5])
    assert p["stop"] == 98.5
    assert p["stop_recently_hit"] is True
    assert p["bars_since_stop_hit"] == 1
    assert p["lowest_low_pct_below_stop"] == 1.52


def test_the_stop_check_reads_LOWS_not_closes():
    """A stop is a resting order: a wick that reaches it fills it. This is the
    exact opposite of the broken-band rule, which ignores wicks on purpose —
    'did support fail?' and 'would I still be in this trade?' are different
    questions with different evidence."""
    # Every CLOSE is comfortably above the 98.5 stop; one LOW is not.
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0},
                      recent_lows=[103.0, 97.0, 104.0])
    assert p["stop_recently_hit"] is True


def test_an_UNCHECKED_stop_reports_None_not_False():
    """None = 'not checked' (an older cached payload, or a caller with no bar
    history). False = 'checked and clean'. Rendering the first as the second
    puts a green tick on a plan nobody verified."""
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0})
    assert p["stop_recently_hit"] is None
    assert p["bars_since_stop_hit"] is None
    assert p["lowest_low_pct_below_stop"] is None


def test_a_clean_stop_reports_False_with_no_depth():
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0},
                      recent_lows=[101.0, 100.5, 102.0])
    assert p["stop_recently_hit"] is False
    assert p["bars_since_stop_hit"] is None
    assert p["lowest_low_pct_below_stop"] is None


def test_a_low_exactly_AT_the_stop_is_not_a_hit():
    """Strictly below. A stop order at $98.50 is not guaranteed a fill on a
    $98.50 print, and claiming it was is the kind of detail that makes him stop
    trusting the column."""
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0},
                      recent_lows=[98.5, 99.0])
    assert p["stop_recently_hit"] is False


def test_an_OLD_stop_hit_falls_out_of_the_window():
    """A stop run three months ago, against a band that has been rebuilt and
    retested since, is stale news."""
    lows = [50.0] + [102.0] * dr.STOP_HIT_LOOKBACK_BARS
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0},
                      recent_lows=lows)
    assert p["stop_recently_hit"] is False
    assert p["stop_hit_lookback_bars"] == dr.STOP_HIT_LOOKBACK_BARS


def test_bars_since_stop_hit_is_measured_from_the_LAST_bar_given():
    """The lows list is oldest-first and includes today, so 0 means today."""
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0},
                      recent_lows=[102.0, 102.0, 97.0])
    assert p["bars_since_stop_hit"] == 0


def test_junk_lows_do_not_crash_or_fabricate_a_hit():
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0},
                      recent_lows=[None, float("nan"), 102.0])
    assert p["stop_recently_hit"] is False
    p2 = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0},
                       recent_lows=[])
    assert p2["stop_recently_hit"] is False


def test_the_real_NBIX_stop_was_already_run():
    """Stop $150.25 quoted the same session NBIX printed a $148.78 low."""
    p = dr.trade_plan(152.72, {"lo": 152.54, "hi": 155.30}, {"lo": 165.0},
                      recent_lows=[158.0, 155.0, 149.90, 148.78])
    assert p["stop"] == 150.25
    assert p["stop_recently_hit"] is True
    assert p["bars_since_stop_hit"] == 0, "run today"
    assert p["lowest_low_pct_below_stop"] == 0.98


def test_the_stop_check_never_changes_the_stop_itself():
    """It annotates the plan. Widening a stop because it was hit would be the
    single worst thing this code could do."""
    clean = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0})
    hit = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0},
                        recent_lows=[90.0])
    for k in ("stop", "entry_low", "entry_high", "target", "rr", "risk_pct"):
        assert clean[k] == hit[k], f"{k} moved because the stop was hit"


# ═════════════════════════════════════════════════════════════════════════════
# THE VERDICT DOWNGRADE — "you still say buy in one place"
# ═════════════════════════════════════════════════════════════════════════════

BROKE = {"broke_below": True, "lowest_close_pct_below": 1.13}
CLEAN = {"broke_below": False, "lowest_close_pct_below": None}
AT_DEMAND = {"state": "AT_DEMAND", "entry_read": "favorable",
             "support_pct": 0.0, "label": "In a demand zone — support is right here."}


def test_a_broken_band_stops_reading_as_favorable():
    out = dr._verdict_after_break(AT_DEMAND, {"lo": 152.54, "hi": 155.30}, BROKE)
    assert out["state"] == "DEMAND_BROKEN"
    assert out["entry_read"] == "caution"
    assert "support is right here" not in out["label"]
    assert "BROKE" in out["label"]


def test_the_downgraded_verdict_stops_claiming_support_is_underfoot():
    """support_pct 0.0 means 'support is exactly here'. On a broken band that
    is the claim being withdrawn."""
    out = dr._verdict_after_break(AT_DEMAND, {"lo": 152.54, "hi": 155.30}, BROKE)
    assert out["support_pct"] is None


def test_an_unbroken_band_is_returned_untouched():
    out = dr._verdict_after_break(AT_DEMAND, {"lo": 100.0, "hi": 106.0}, CLEAN)
    assert out is AT_DEMAND


def test_only_AT_DEMAND_is_downgraded():
    """The other states never claimed support, so rewriting them would be
    inventing a reading the snapshot module never made."""
    at_supply = {"state": "AT_SUPPLY", "entry_read": "caution", "label": "x"}
    assert dr._verdict_after_break(at_supply, {"lo": 1.0, "hi": 2.0}, BROKE) is at_supply


def test_a_missing_verdict_stays_missing():
    assert dr._verdict_after_break(None, {"lo": 1.0, "hi": 2.0}, BROKE) is None
    assert dr._verdict_after_break(None, None, CLEAN) is None


def test_the_downgrade_keeps_the_rest_of_the_verdict():
    """resistance_pct and friends are still true — only the support claim
    changed."""
    v = {**AT_DEMAND, "resistance_pct": 4.2}
    out = dr._verdict_after_break(v, {"lo": 152.54, "hi": 155.30}, BROKE)
    assert out["resistance_pct"] == 4.2


def test_the_snapshot_module_is_NOT_given_history():
    """The split is the point: price_zones answers 'where is price now', this
    module answers the transition question. If the break check ever migrates
    into price_zones, every /zones read starts depending on the re-entry rules."""
    import inspect
    src = inspect.getsource(pz)
    assert "broke_below" not in src
    assert "DEMAND_BROKEN" not in src


# ═════════════════════════════════════════════════════════════════════════════
# LIVE SCAN PROGRESS  (Ajay 2026-08-17)
#
#   "Are you updating both pages when supply demand is getting updated I am
#    looking at this and its hard to tell if its scanning or now"
#
# The board's counters (`n`, `scanned`) only exist in the FINAL payload, so for
# the ~2-3 minutes of a cold sp1500 pass the page showed "0 in demand · 0/0
# scanned" under a static sentence — indistinguishable from a hung request.
# Spec: docs/supply_demand/scan_progress.md
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=False)
def clean_progress():
    dr._progress.clear()
    yield
    dr._progress.clear()


def test_progress_answers_even_when_nothing_is_running():
    """One shape to render, always. A page that has to branch on presence is a
    page that renders nothing on the first paint."""
    dr._progress.pop("full", None)
    out = dr.progress_for("full")
    assert out["phase"] == "idle"
    assert out["running"] is False
    assert out["current"] == 0 and out["total"] == 0
    assert out["pct"] is None and out["eta_sec"] is None


def test_progress_reports_the_running_ticker_and_a_live_hit_count():
    dr._publish_progress("full", "scanning", started_at=time.time() - 10,
                         current=250, total=500, hits=7, symbol="NVDA")
    out = dr.progress_for("full")
    assert out["phase"] == "scanning" and out["running"] is True
    assert (out["current"], out["total"], out["hits"]) == (250, 500, 7)
    assert out["symbol"] == "NVDA"
    assert out["pct"] == 50.0


def test_the_eta_is_projected_from_the_measured_rate_not_a_constant():
    """A warm price cache runs an order of magnitude faster than a cold one, so
    any fixed per-symbol cost would be wrong on one of the two paths."""
    dr._publish_progress("full", "scanning", started_at=time.time() - 20.0,
                         current=100, total=500, hits=1, symbol="A")
    out = dr.progress_for("full")
    # 20s bought 100 names; 400 left -> ~80s.
    assert 70 <= out["eta_sec"] <= 90


def test_no_eta_before_the_first_symbol_finishes():
    """Dividing by a zero count would either crash or print a fabricated wait."""
    dr._publish_progress("full", "scanning", started_at=time.time(),
                         current=0, total=500, hits=0)
    assert dr.progress_for("full")["eta_sec"] is None


def test_no_percentage_until_the_universe_size_is_known():
    """Resolving sp1500 is three network calls. 0% during them reads as stuck."""
    dr._publish_progress("full", "universe", started_at=time.time(),
                         current=0, total=0, hits=0)
    out = dr.progress_for("full")
    assert out["phase"] == "universe"
    assert out["pct"] is None
    assert out["running"] is True


def test_every_legacy_alias_reads_the_one_counter():
    """One universe (2026-08-25) means one scan job. A tab polling under an
    old bookmark key must see the live counter, not a parallel idle."""
    dr._publish_progress("full", "scanning", current=10, total=500, hits=1)
    assert dr.progress_for("sp500")["current"] == 10
    assert dr.progress_for("sp1500_plus")["current"] == 10


def test_a_snapshot_is_swapped_wholesale_never_mutated_in_place():
    """The scan thread writes while the request thread reads, with no lock on
    the read path. Swapping a fresh dict is atomic in CPython; mutating a shared
    one would let a reader see a half-updated record."""
    dr._publish_progress("full", "scanning", current=1, total=500)
    first = dr._progress["full"]
    dr._publish_progress("full", "scanning", current=2)
    assert dr._progress["full"] is not first, "the snapshot was mutated in place"
    assert first["current"] == 1, "the old snapshot was written through"


def test_publishing_carries_prior_fields_forward():
    """The per-symbol publish only sends what changed; total and started_at must
    survive or the bar loses its denominator mid-scan."""
    dr._publish_progress("full", "scanning", started_at=123.0, total=500,
                         universe_label="S&P 500")
    dr._publish_progress("full", "scanning", current=7, symbol="AAPL")
    out = dr.progress_for("full")
    assert out["total"] == 500
    assert out["universe_label"] == "S&P 500"
    assert out["current"] == 7


def test_publishing_never_raises_on_junk():
    """It runs inside the scan loop. A progress bug must never kill a scan."""
    dr._publish_progress("full", "scanning", current=object())
    dr.progress_for("full")          # must not raise


def test_a_failed_scan_is_reported_not_left_frozen():
    """Otherwise the bar stops at 47% and the page says 'scanning' forever —
    the exact complaint, reintroduced by the fix for it."""
    dr._publish_progress("full", "failed", current=200, total=500, error="boom")
    out = dr.progress_for("full")
    assert out["phase"] == "failed"
    assert out["running"] is False
    assert out["error"] == "boom"


def test_done_is_not_running():
    dr._publish_progress("full", "done", current=500, total=500, hits=9)
    out = dr.progress_for("full")
    assert out["running"] is False
    assert out["pct"] == 100.0


def test_progress_resolves_the_universe_key_the_same_way_the_scan_does():
    """Asking under an unresolved alias must not return a permanent idle."""
    for alias in ("full", "FULL", " full ", "sp500"):
        assert dr.progress_for(alias)["universe_key"] == dr._universe_key("sp500")


# --- the real loop, end to end ---
def test_a_real_scan_publishes_universe_then_scanning_then_done(monkeypatch):
    """Behavioural. The phases must actually fire in order from `scan()` — the
    unit tests above only prove the publisher works if something calls it."""
    seen = []
    real = dr._publish_progress

    def spy(ukey, phase, **f):
        seen.append(phase)
        real(ukey, phase, **f)

    monkeypatch.setattr(dr, "_publish_progress", spy)
    monkeypatch.setattr(dr, "_resolve_universe",
                        lambda k: (["AAA", "BBB"], "Test", {}, None, "full"))
    monkeypatch.setattr(dr, "analyze_symbol", lambda s: None)
    monkeypatch.setattr(dr, "_attach_venues", lambda rows, **kw: None)

    dr.scan(force=True, universe="sp500")
    assert seen[0] == "universe"
    assert "scanning" in seen
    assert seen[-1] == "done"
    # One publish per symbol, so the bar moves rather than jumping.
    assert seen.count("scanning") >= 3        # the opener + one per symbol
    assert dr.progress_for("full")["total"] == 2


def test_a_symbol_that_throws_still_advances_the_bar(monkeypatch):
    """A universe with a few bad tickers must not stall the counter — that reads
    as a hang, which is the thing being fixed."""
    monkeypatch.setattr(dr, "_resolve_universe",
                        lambda k: (["AAA", "BBB", "CCC"], "Test", {}, None, "full"))

    def boom(sym):
        raise RuntimeError("no prices")

    monkeypatch.setattr(dr, "analyze_symbol", boom)
    monkeypatch.setattr(dr, "_attach_venues", lambda rows, **kw: None)
    dr.scan(force=True, universe="sp500")
    out = dr.progress_for("full")
    assert out["current"] == 3, "the bar must reach the end even when every name fails"
    assert out["errors"] == 3
    assert out["phase"] == "done"


def test_the_warming_payload_carries_the_counter():
    """So a page polling only the board still gets a moving number."""
    import inspect
    src = inspect.getsource(dr.cached_or_warm)
    assert '"progress": progress_for(ukey)' in src


def test_chart_maps_shows_the_SAME_counter_not_its_own():
    """Both tabs read one demand_reentry cache, so they are watching ONE job.
    Two independently-derived readings of one scan is how the two pages start
    disagreeing — which is what Ajay was asking about."""
    import inspect
    from chart_maps import board
    src = inspect.getsource(board.zone_tiles)
    assert 'D.cached_or_warm(' in src, "chart-maps must read the shared cache"
    assert '"progress": data.get("progress")' in src, \
        "chart-maps must forward the shared counter, never compute its own"


# ═════════════════════════════════════════════════════════════════════════════
# THE REWARD:RISK FLOOR  (Ajay 2026-08-17)
#
# Chosen AFTER three "buyers in control" candidates were designed and measured
# and all three failed (joint family-wise p = 0.76, holdouts failing in opposite
# directions, 0.4% agreement between them). The measured defect they all missed:
#
#   36% of this board's backtested wins (131 of 363) resolved on the ENTRY BAR,
#   median planned R:R 0.45 — the "target" was already inside the entry day's
#   range. Strip them and the whole rule reads exp -0.29%, exSPY -0.586%.
#
# Spec: docs/supply_demand/rr_floor.md
# ═════════════════════════════════════════════════════════════════════════════

def test_a_plan_that_pays_less_than_it_risks_fails_the_floor():
    """The behavioural case, and the whole justification in one line: DUK on the
    2026-08-14 board offered 0.16R — risking six dollars to make one."""
    assert dr.meets_rr_floor({"rr": 0.16}) is False
    assert dr.meets_rr_floor({"rr": 1.85}) is True


def test_the_floor_is_INCLUSIVE_at_its_own_value():
    assert dr.meets_rr_floor({"rr": 1.0}, 1.0) is True
    assert dr.meets_rr_floor({"rr": 0.999}, 1.0) is False


def test_an_UNCOMPUTABLE_rr_fails_a_real_floor():
    """`rr` is None when no supply band sits above the entry band, so there is
    no first objective to measure. The backtest SKIPS those rows entirely — so
    there is no evidence they work either way, and letting them through would
    make the one we could not measure the one that shows up unfiltered. Same
    rule the chart-maps liquidity tier uses for an unknown turnover."""
    assert dr.meets_rr_floor({"rr": None}) is False
    assert dr.meets_rr_floor({}) is False
    assert dr.meets_rr_floor(None) is False


def test_a_floor_of_zero_is_OFF_and_passes_everything():
    for plan in ({"rr": 0.01}, {"rr": None}, {}, None):
        assert dr.meets_rr_floor(plan, 0) is True


def test_a_bool_is_not_a_reward_risk_ratio():
    """`True >= 1.0` is True in Python. A bool reaching this field means an
    upstream bug, and silently scoring it as a 1.0R plan would hide it."""
    assert dr.meets_rr_floor({"rr": True}) is False


def test_the_floor_default_is_the_TRADE_CONSTRUCTION_line_not_the_fitted_peak():
    """1.25 was the best exSPY cell in the sweep (-0.003% vs 1.0's -0.101%).
    It is deliberately NOT the default: exSPY is NOT monotone across the sweep
    (it falls at 0.75, 1.50, 2.00 and 3.00), so the peak of a nine-cell search
    is a fitted number. Picking it would be exactly the in-sample fitting that
    disqualified the three buyers-in-control candidates — and applying a
    stricter standard to those than to this would be dishonest.

    1.0 is what "never risk more than the first objective pays" implies, and
    that claim needs no backtest at all."""
    assert dr.MIN_RR_DEFAULT == 1.0


# --- the payload filter ---
def _row(rr):
    return {"symbol": "X", "plan": ({"rr": rr} if rr is not None else None)}


def test_the_filter_reports_what_it_removed_rather_than_just_shrinking():
    data = {"rows": [_row(1.85), _row(0.16), _row(0.71), _row(2.4)], "n": 4}
    out = dr._apply_rr_floor(data, 1.0)
    assert [r["plan"]["rr"] for r in out["rows"]] == [1.85, 2.4]
    assert out["n"] == 2
    assert out["dropped_low_rr"] == 2
    assert out["min_rr"] == 1.0
    assert out["min_rr_default"] == dr.MIN_RR_DEFAULT


def test_min_rr_None_means_APPLY_THE_DEFAULT_not_no_floor():
    """A caller that omits the parameter must get the house behaviour, or the
    default silently stops applying the moment anyone forgets to pass it."""
    data = {"rows": [_row(1.85), _row(0.16)], "n": 2}
    assert dr._apply_rr_floor(data, None)["dropped_low_rr"] == 1


def test_a_floor_of_zero_leaves_every_row_and_says_so():
    data = {"rows": [_row(0.16), _row(None)], "n": 2}
    out = dr._apply_rr_floor(data, 0)
    assert len(out["rows"]) == 2
    assert out["min_rr"] == 0.0 and out["dropped_low_rr"] == 0


def test_the_floor_never_reorders_the_rows_it_keeps():
    """The board is sorted by R:R before this runs; a filter that resorted would
    silently change which row leads."""
    data = {"rows": [_row(3.0), _row(0.2), _row(1.2), _row(0.9), _row(2.0)]}
    out = dr._apply_rr_floor(data, 1.0)
    assert [r["plan"]["rr"] for r in out["rows"]] == [3.0, 1.2, 2.0]


def test_the_filter_is_applied_at_READ_time_so_the_cache_is_not_fragmented():
    """One 3-hour cache entry per universe, not one per floor value — and
    changing the floor on the page must be instant, not a fresh 3-minute pass."""
    import inspect
    scan_src = inspect.getsource(dr.scan)
    assert "_apply_rr_floor" not in scan_src, \
        "the floor must not run inside scan(), or the cache holds a filtered set"
    assert "_apply_rr_floor" in inspect.getsource(dr.cached_or_warm)


def test_the_floor_does_not_touch_is_reentry():
    """`is_reentry` answers the STRUCTURAL question — did price come back into a
    band it had left, with the trend intact. R:R is a fact about the PLAN. Mixing
    them would make one field mean two things AND would stop the walk-forward
    from measuring the unfiltered cohort, which is where the 0.45R finding came
    from in the first place."""
    import inspect
    assert "min_rr" not in inspect.getsource(dr.decide_from_frame)
    assert "meets_rr_floor" not in inspect.getsource(dr.decide_from_frame)


def test_an_empty_board_survives_the_filter():
    out = dr._apply_rr_floor({"rows": [], "n": 0}, 1.0)
    assert out["rows"] == [] and out["dropped_low_rr"] == 0


def test_a_warming_payload_carries_the_floor_fields():
    """The page renders them unconditionally; a missing key is a crash."""
    import inspect
    src = inspect.getsource(dr.cached_or_warm)
    for key in ('"min_rr"', '"min_rr_default"', '"dropped_low_rr"'):
        assert key in src, f"warming payload is missing {key}"


# ---------------------------------------------------------------------------
# venue enrichment must DEGRADE on a hung fetch, never kill the scan
# ---------------------------------------------------------------------------
def _venue_row(sym, rr=3.0):
    return {"symbol": sym, "plan": {"rr": rr}, "liquidity": {}}


def test_attach_venues_survives_a_hung_future(monkeypatch):
    """as_completed(timeout=...) RAISES concurrent.futures.TimeoutError at the
    deadline; it does not just stop iterating. Before 2026-08-25 that exception
    escaped _attach_venues and killed the whole 1,500-name scan it was
    decorating — the warm thread logged "background warm failed for sp1500:
    1 (of 15) futures unfinished" every ~90s and the board said "Scanning…"
    forever (trigger: the shared Massive key at max_connections, one fetch
    hung). Detail is decoration; the scan landing is the product."""
    import threading

    release = threading.Event()

    def fake_enrich(r, *a, **k):
        if r["symbol"] == "HUNG":
            release.wait(10)  # far past the test's budget+slack
            return None
        return {"venues": {"rating": "A"}, "retail": None,
                "total_shares": 0, "tape_is_today": False}

    monkeypatch.setattr(dr, "_enrich_one", fake_enrich)
    monkeypatch.setattr(dr, "_VENUE_SLACK_SEC", 0.3)

    rows = [_venue_row("HUNG", rr=9.9), _venue_row("AAA"), _venue_row("BBB")]
    t0 = time.time()
    dr._attach_venues(rows, top_n=3, budget_sec=0.3)  # must NOT raise
    took = time.time() - t0
    release.set()  # let the worker thread die

    assert took < 5, f"_attach_venues blocked {took:.1f}s on the hung future"
    got = {r["symbol"] for r in rows if r.get("venues")}
    assert got == {"AAA", "BBB"}
    assert not rows[0].get("venues"), "the hung row must simply lack detail"


def test_attach_venues_still_enriches_when_nothing_hangs(monkeypatch):
    """The except-path fix must not change the happy path."""
    def fake_enrich(r, *a, **k):
        return {"venues": {"rating": "B"}, "retail": None,
                "total_shares": 0, "tape_is_today": False}

    monkeypatch.setattr(dr, "_enrich_one", fake_enrich)
    rows = [_venue_row("AAA"), _venue_row("BBB")]
    dr._attach_venues(rows, top_n=2, budget_sec=5)
    assert all(r.get("venues") for r in rows)


# ---------------------------------------------------------------------------
# deep_rows — second-level arrivals survive the scan even when trend fails
# ---------------------------------------------------------------------------
def test_scan_collects_deep_rows_that_is_reentry_refuses(monkeypatch):
    """The whole reason deep-demand lives IN the scan (2026-08-25): a name
    that broke its first band is usually a knife, fails trend_ok, and never
    reaches `rows` — but must reach `deep_rows`."""
    def _bands():
        return [{"kind": "demand", "lo": 90.0, "hi": 95.0, "mid": 92.5,
                 "touches": 3, "strength": 70.0},
                {"kind": "demand", "lo": 80.0, "hi": 85.0, "mid": 82.5,
                 "touches": 3, "strength": 60.0}]

    rows = {
        # In its second band, trend gate failed → deep_rows only.
        "KNIFE": {"is_reentry": False, "last_price": 82.0,
                  "demand_zones": _bands(), "bars_since_above": 2,
                  "entry_zone": {"strength": 60}, "fell_from_pct": 15},
        # Ordinary reentry, first band holding → rows only.
        "CALM": {"is_reentry": True, "last_price": 92.0,
                 "demand_zones": _bands(), "bars_since_above": 3,
                 "entry_zone": {"strength": 90}, "fell_from_pct": 8},
    }
    monkeypatch.setattr(dr.universe_mod, "load_universe", lambda mode=None: list(rows))
    monkeypatch.setattr(dr, "analyze_symbol",
                        lambda s, with_series=False: {**rows[s], "symbol": s})
    # No real price frames for fake symbols — the inflow block must degrade
    # to None, not reach for the network.
    monkeypatch.setattr(dr.prices, "load_prices", lambda s: None)
    dr._cache.clear()

    out = dr.scan(force=True)
    assert [r["symbol"] for r in out["rows"]] == ["CALM"]
    assert [r["symbol"] for r in out["deep_rows"]] == ["KNIFE"]
    assert out["deep_n"] == 1
    d = out["deep_rows"][0]["deep_demand"]
    assert d["state"] == "in" and d["second_band"]["lo"] == 80.0


def test_scan_deep_rows_capped_but_count_honest(monkeypatch):
    """No silent caps: a bad-breadth day trims deep_rows to MAX_ROWS but
    deep_n reports how many actually qualified."""
    from supply_demand import deep_demand as DD
    n = DD.MAX_ROWS + 7
    syms = [f"S{i:03d}" for i in range(n)]

    def fake(s, with_series=False):
        return {"symbol": s, "is_reentry": False, "last_price": 82.0,
                "demand_zones": [
                    {"kind": "demand", "lo": 90.0, "hi": 95.0, "mid": 92.5,
                     "touches": 3, "strength": 70.0},
                    {"kind": "demand", "lo": 80.0, "hi": 85.0, "mid": 82.5,
                     "touches": 3, "strength": 60.0}],
                "entry_zone": {"strength": 60}}

    monkeypatch.setattr(dr, "_resolve_universe",
                        lambda k: (syms, "S&P 500", {}, None, "sp500"))
    monkeypatch.setattr(dr, "analyze_symbol", fake)
    monkeypatch.setattr(dr.prices, "load_prices", lambda s: None)
    dr._cache.clear()

    out = dr.scan(force=True)
    assert len(out["deep_rows"]) == DD.MAX_ROWS
    assert out["deep_n"] == n


def test_scan_attaches_the_inflow_verdict_to_deep_rows(monkeypatch):
    """The flow read rides the scan row (Ajay 2026-08-25) — computed from the
    canonical sepa/volume.analyze, and a failure there degrades to
    inflow=None, never a crashed scan."""
    from sepa import volume as vol_mod
    from sepa import prices as prices_mod

    def fake(s, with_series=False):
        return {"symbol": s, "is_reentry": False, "last_price": 82.0,
                "demand_zones": [
                    {"kind": "demand", "lo": 90.0, "hi": 95.0, "mid": 92.5,
                     "touches": 3, "strength": 70.0},
                    {"kind": "demand", "lo": 80.0, "hi": 85.0, "mid": 82.5,
                     "touches": 3, "strength": 60.0}],
                "entry_zone": {"strength": 60}}

    monkeypatch.setattr(dr, "_resolve_universe",
                        lambda k: (["GOODF", "BADF"], "S&P 500", {}, None, "sp500"))
    monkeypatch.setattr(dr, "analyze_symbol", fake)
    monkeypatch.setattr(prices_mod, "load_prices", lambda s: object())
    monkeypatch.setattr(vol_mod, "analyze", lambda df: {
        "cmf_20": 0.2, "accumulation_days_25": 8, "distribution_days_25": 2,
        "pocket_pivot": False, "net_dollar_vol_50": 5e8})
    dr._cache.clear()

    out = dr.scan(force=True)
    infl = out["deep_rows"][0]["deep_demand"]["inflow"]
    assert infl["state"] == "inflow" and infl["cmf_20"] == 0.2


def test_scan_deep_rows_survive_a_crashing_volume_read(monkeypatch):
    from sepa import prices as prices_mod

    def fake(s, with_series=False):
        return {"symbol": s, "is_reentry": False, "last_price": 82.0,
                "demand_zones": [
                    {"kind": "demand", "lo": 90.0, "hi": 95.0, "mid": 92.5,
                     "touches": 3, "strength": 70.0},
                    {"kind": "demand", "lo": 80.0, "hi": 85.0, "mid": 82.5,
                     "touches": 3, "strength": 60.0}],
                "entry_zone": {"strength": 60}}

    def boom(s):
        raise RuntimeError("no frame")

    monkeypatch.setattr(dr, "_resolve_universe",
                        lambda k: (["X"], "S&P 500", {}, None, "sp500"))
    monkeypatch.setattr(dr, "analyze_symbol", fake)
    monkeypatch.setattr(prices_mod, "load_prices", boom)
    dr._cache.clear()

    out = dr.scan(force=True)
    assert out["deep_rows"][0]["deep_demand"]["inflow"] is None


# ---------------------------------------------------------------------------
# R:R across the entry BAND, not just at spot (Ajay 2026-08-31).
#
# The card says "Buy $16.92-$17.41" but `rr` was measured only at `entry_ref`
# (spot). On the live board that day the two disagreed on 41 of 96 rows.
# ---------------------------------------------------------------------------

def test_rr_at_entry_high_is_measured_at_the_worst_permitted_fill():
    """R:R filled at the top of the band, which the plan explicitly permits."""
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0})
    # stop sits under 100, so the band top is the worst entry the plan allows.
    assert p["rr_at_entry_high"] == round(
        (p["target"] - p["entry_high"]) / (p["entry_high"] - p["stop"]), 2)
    assert p["rr_at_entry_high"] < p["rr"], (
        "buying higher against the same stop and target must be worse")


def test_qbts_the_target_one_cent_above_the_entry_band_is_flagged():
    """QBTS 2026-08-31: 1.34R at spot, 0.01R at the top of its own entry band.

    The 2026-08-13 VRT fix stopped a target landing INSIDE the entry band. It
    did not stop one landing a cent above it, which produces the same defect:
    the reward is spent before the entry range ends. The plan is still returned
    — Ajay decides — but it must not present 1.34R without saying that the
    number holds only at the bottom of the band.
    """
    p = dr.trade_plan(16.99, {"lo": 16.92, "hi": 17.41}, {"lo": 17.42})
    assert p["rr"] >= 1.0                      # passes the floor at spot
    assert p["rr_at_entry_high"] < 0.1         # and is worthless at the top
    assert p["thin_across_band"] is True


def test_a_genuinely_wide_target_is_not_flagged_thin():
    """The negative: a real first objective must not trip the flag."""
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 140.0})
    assert p["thin_across_band"] is False
    assert p["rr_at_entry_high"] >= dr.THIN_BAND_RR


def test_no_target_means_not_computable_not_fine():
    """No supply above => no first objective => the flag must not read False.

    "We could not measure this" and "we measured it and it is fine" are
    different claims; rendering the first as the second is how an unmeasured
    plan gets to look safe.
    """
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, None)
    assert p["target"] is None
    assert p["rr_at_entry_high"] is None
    assert p["thin_across_band"] is False   # flag is off, but rr_* says why


def test_thin_flag_does_not_change_which_rows_the_floor_keeps():
    """Reported, not enforced.

    The floor still gates on `rr`. Flipping the band-top number must not
    silently drop rows from a board Ajay reads every morning — that is his call
    to make, not a side effect of adding an annotation.
    """
    thin = {"plan": {"rr": 1.4, "rr_at_entry_high": 0.01,
                     "thin_across_band": True}}
    kept = dr._apply_rr_floor({"rows": [thin]}, 1.0)
    assert kept["rows"] == [thin]
