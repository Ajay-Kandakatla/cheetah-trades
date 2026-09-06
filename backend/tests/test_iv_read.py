"""Market IV read (nav badge beside the Market Gauge, 2026-09-06). Pure
maths + a hermetic compute() over canned frames — no network, no Mongo."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from sepa import iv_read as IV


def _df(rows):
    """rows = [(date, close)] -> the frame shape sepa.prices returns."""
    idx = pd.to_datetime([d for d, _ in rows])
    return pd.DataFrame({"close": [c for _, c in rows]}, index=idx)


def test_bands_match_market_regime_cut_points():
    assert (IV.CALM_BELOW, IV.NORMAL_BELOW, IV.ELEVATED_BELOW) == (15.0, 20.0, 30.0)
    assert IV.classify(14.99) == "calm" and IV.classify(15.0) == "normal"
    assert IV.classify(19.99) == "normal" and IV.classify(20.0) == "elevated"
    assert IV.classify(29.99) == "elevated" and IV.classify(30.0) == "stress"
    assert IV.classify(None) is None and IV.classify("x") is None
    assert IV.classify(float("nan")) is None


def test_term_shape_has_a_flat_band():
    assert IV.term_shape(0.71) == "contango"
    assert IV.term_shape(1.16) == "backwardation"
    assert IV.term_shape(1.01) == "flat" and IV.term_shape(0.99) == "flat"
    assert IV.term_shape(None) is None


def test_pct_rank_is_the_share_of_closes_under_the_level():
    series = list(range(1, 101))                    # 1..100
    assert IV.pct_rank(series, 50.5) == 50.0
    assert IV.pct_rank(series, 1) == 0.0 and IV.pct_rank(series, 1000) == 100.0
    assert IV.pct_rank(series[:10], 5) is None      # too thin
    assert IV.pct_rank(series + [float("nan")], 50.5) == 50.0   # NaN ignored


def _wire(monkeypatch, vix, v9=None, v3=None, vv=None):
    frames = {"^VIX": _df(vix), "^VIX9D": _df(v9 or []), "^VIX3M": _df(v3 or []),
              "^VVIX": _df(vv or [])}
    monkeypatch.setattr(IV, "_load", lambda sym, period: frames.get(sym))


def test_compute_aligns_the_term_structure_on_one_date(monkeypatch):
    vix = [("2026-08-%02d" % d, 20.0) for d in range(1, 30)] + [("2026-09-03", 14.32), ("2026-09-04", 14.53)]
    # 9D / 3M miss the newest bar (NaN on 09-04, as seen live 2026-09-06).
    v9 = [("2026-09-03", 16.85), ("2026-09-04", float("nan"))]
    v3 = [("2026-09-03", 20.54), ("2026-09-04", float("nan"))]
    vv = [("2026-09-03", 83.8), ("2026-09-04", 84.42)]
    _wire(monkeypatch, vix, v9, v3, vv)
    out = IV.compute()
    assert out["vix"] == 14.53 and out["prev"] == 14.32 and out["chg"] == 0.21
    assert out["chg_pct"] == 1.5 and out["as_of"] == "2026-09-04"
    assert out["regime"] == "calm" and out["regime_label"] == "Calm"
    assert out["pct_252"] == pytest.approx(3.2, abs=0.1)     # 1 of 31 closes under 14.53
    t = out["term"]
    assert t["as_of"] == "2026-09-03"                        # aligned, not mixed
    assert t["vix9d"] == 16.85 and t["vix3m"] == 20.54
    assert t["ratio_9d_30d"] == round(16.85 / 14.32, 3)
    assert t["ratio_30d_3m"] == round(14.32 / 20.54, 3)
    assert t["shape"] == "contango"
    assert out["vvix"] == 84.42
    assert "options are cheap" in out["read"] and "contango" in out["read"]
    assert out["disclaimer"]


def test_compute_without_vix_is_none_safe(monkeypatch):
    _wire(monkeypatch, [])
    out = IV.compute()
    assert out["vix"] is None and out["regime"] is None and out["read"] == "VIX unavailable"
    assert out["term"]["shape"] is None and out["pct_252"] is None


def test_stress_read_and_backwardation(monkeypatch):
    vix = [("2026-08-%02d" % d, 18.0) for d in range(1, 30)] + [("2026-09-04", 34.0)]
    v3 = [("2026-09-04", 28.0)]
    _wire(monkeypatch, vix, None, v3, None)
    out = IV.compute()
    assert out["regime"] == "stress" and out["term"]["shape"] == "backwardation"
    assert "stand aside" in out["read"] and "backwardation" in out["read"]
    assert "up 16.0 on the day" in out["read"]


def test_get_caches_for_the_ttl(monkeypatch):
    calls = {"n": 0}

    def fake_compute():
        calls["n"] += 1
        return {"vix": 15.0, "generated_at": 0.0}

    monkeypatch.setattr(IV, "compute", fake_compute)
    IV._CACHE["data"], IV._CACHE["at"] = None, 0.0
    a = IV.get()
    b = IV.get()
    assert calls["n"] == 1 and a["vix"] == b["vix"] == 15.0 and "age_sec" in b
    c = IV.get(force=True)
    assert calls["n"] == 2 and c["age_sec"] == 0.0
    IV._CACHE["data"], IV._CACHE["at"] = None, 0.0


def test_route_is_registered_in_main():
    import os
    with open(os.path.join(os.path.dirname(__file__), "..", "main.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert '@app.get("/market/iv")' in src
    assert "iv_read.get, force" in src
