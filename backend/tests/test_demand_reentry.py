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
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import demand_reentry as dr
from supply_demand import price_zones as pz


# ── reentry_read — the transition test ────────────────────────────────────────
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
    """Above every band → the plan still points at where you'd want to buy."""
    zones = [{"lo": 80, "hi": 85, "strength": 50}, {"lo": 60, "hi": 65, "strength": 99}]
    assert dr._pick_entry_zone(103, zones)["hi"] == 85


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

    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: list(U.UNIVERSE))
    monkeypatch.setattr(dr, "analyze_symbol", lambda s, with_series=False: None)
    dr._cache.clear()

    out = dr.scan(force=True, universe="sp500")
    assert out["universe_is_sp500"] is False
    assert "curated" in out["universe_note"].lower()


def test_scan_marks_a_real_sp500_universe_as_such(monkeypatch):
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: [f"S{i}" for i in range(503)])
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
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: list(rows))
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

    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: ["GOOD", "BAD"])
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
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: syms)
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
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: syms)
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
    earlier resolve (or from a test double standing in for fetch_sp500). If it
    doesn't describe the list we actually got back, it must be ignored rather
    than mislabel the scan."""
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: ["AAA", "BBB"])
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
    raising or scanning nothing. (Default became sp1500 on 2026-08-14.)"""
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: ["AAA"])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp400", lambda: ["BBB"])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp600", lambda: ["CCC"])
    _, _, _, _, key = dr._resolve_universe("not-a-universe")
    assert key == dr.DEFAULT_UNIVERSE
    assert key in dr.UNIVERSES


def test_default_universe_is_the_full_sp1500():
    """Ajay 2026-08-14: "make it default scan 1500". The S&P 500 alone
    surfaced ~3 names at a tradeable R:R; the full 1500 surfaces ~12."""
    assert dr.DEFAULT_UNIVERSE == "sp1500"


def test_multi_layer_universe_reports_its_worst_staleness(monkeypatch):
    """sp1500 resolves three lists independently; one stale layer must surface,
    not be averaged away by two fresh ones."""
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: ["A"])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp400", lambda: ["B"])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp600", lambda: ["C"])
    src = {"sp500": {"source": "cache", "n": 1, "age_days": 0.0},
           "sp400": {"source": "stale-cache", "n": 1, "age_days": 91.0},
           "sp600": {"source": "wikipedia", "n": 1, "age_days": 0.0}}
    monkeypatch.setattr(dr.universe_mod, "last_source", lambda name: src.get(name))
    _, _, prov, stale, key = dr._resolve_universe("sp1500")
    assert key == "sp1500" and stale == 91
    assert set(prov) == {"sp500", "sp400", "sp600"}


def test_a_failing_layer_shrinks_the_universe_instead_of_polluting_it(monkeypatch):
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: ["A", "B"])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp400",
                        lambda: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(dr.universe_mod, "fetch_sp600", lambda: ["C"])
    monkeypatch.setattr(dr.universe_mod, "last_source", lambda name: None)
    syms, _, _, _, _ = dr._resolve_universe("sp1500")
    assert syms == ["A", "B", "C"]        # sp400 contributes nothing, no crash


def test_each_universe_is_cached_separately(monkeypatch):
    """REGRESSION: a single cache slot would serve an sp500 result to an
    sp1500 request (and vice versa) for up to 3 hours."""
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: ["A"])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp400", lambda: ["B"])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp600", lambda: ["C"])
    monkeypatch.setattr(dr.universe_mod, "last_source", lambda name: None)
    monkeypatch.setattr(dr, "analyze_symbol", lambda s, with_series=False: None)
    dr._cache.clear()

    small = dr.scan(force=True, universe="sp500")
    big = dr.scan(force=True, universe="sp1500")
    assert small["universe"] == 1 and big["universe"] == 3
    # both now cached, and must not cross-serve
    assert dr.scan(universe="sp500")["universe"] == 1
    assert dr.scan(universe="sp1500")["universe"] == 3


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
    assert dr._universe_key("  SP500  ") == "sp500"
    assert dr._universe_key("nonsense") == dr.DEFAULT_UNIVERSE


def test_scan_coerces_a_non_bool_force(monkeypatch):
    """REGRESSION (2026-08-14): FastAPI Query(...) defaults resolve at request
    time, so a direct call passed the Query OBJECT as `force`. It is truthy, so
    `if not force` never fired and every in-container call recomputed the whole
    universe instead of serving the 3h cache — which is also what made the cold
    path look far slower than it was."""
    class Weird:
        pass
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: ["AAA"])
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
def test_sp1500_plus_layers_the_themes_on_top_of_the_index(monkeypatch):
    """The S&P tiers require positive earnings and US domicile, so no quantum
    name — and none of OKLO / SMR / NNE / ARM — can be in sp1500. sp1500_plus
    is the union that puts them in front of the scanner."""
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: ["A"])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp400", lambda: ["B"])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp600", lambda: ["C"])
    monkeypatch.setattr(dr.universe_mod, "fetch_themes", lambda: ["IONQ", "OKLO"])
    monkeypatch.setattr(dr.universe_mod, "last_source", lambda name: None)

    syms, _, prov, _, key = dr._resolve_universe("sp1500_plus")
    assert key == "sp1500_plus"
    assert syms == ["A", "B", "C", "IONQ", "OKLO"]
    assert set(prov) == {"sp500", "sp400", "sp600", "themes"}


def test_sp1500_plus_dedupes_a_theme_name_already_in_the_index(monkeypatch):
    """NVDA and VST are in BOTH the index and a theme roster. A duplicate would
    scan the name twice and could show it on the board twice."""
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: ["NVDA", "A"])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp400", lambda: [])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp600", lambda: [])
    monkeypatch.setattr(dr.universe_mod, "fetch_themes", lambda: ["NVDA", "IONQ"])
    monkeypatch.setattr(dr.universe_mod, "last_source", lambda name: None)

    syms, _, _, _, _ = dr._resolve_universe("sp1500_plus")
    assert syms == ["NVDA", "A", "IONQ"]
    assert len(syms) == len(set(syms))


def test_plain_sp1500_is_unchanged_by_the_themes(monkeypatch):
    """REGRESSION: sp1500 is the existing default for /supply-demand. Adding a
    composite key must not quietly widen it for every existing caller."""
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: ["A"])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp400", lambda: ["B"])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp600", lambda: ["C"])
    monkeypatch.setattr(dr.universe_mod, "fetch_themes", lambda: ["IONQ"])
    monkeypatch.setattr(dr.universe_mod, "last_source", lambda name: None)

    syms, _, prov, _, key = dr._resolve_universe("sp1500")
    assert key == "sp1500" and syms == ["A", "B", "C"]
    assert "themes" not in prov
    assert dr.DEFAULT_UNIVERSE == "sp1500"


def test_a_failing_theme_layer_does_not_take_the_board_down(monkeypatch):
    monkeypatch.setattr(dr.universe_mod, "fetch_sp500", lambda: ["A"])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp400", lambda: [])
    monkeypatch.setattr(dr.universe_mod, "fetch_sp600", lambda: [])
    monkeypatch.setattr(dr.universe_mod, "fetch_themes",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(dr.universe_mod, "last_source", lambda name: None)

    syms, _, _, _, _ = dr._resolve_universe("sp1500_plus")
    assert syms == ["A"]


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
