"""catalysts/signal_watch — the 15m/60m buy-sell monitor reads its structure
(zones, ATR, fair value gaps) off CLOSED buckets and its price off the live
one (integrator 2026-09-05, closing the loop price_zones.for_symbol opened).

Pure: the intraday frame is synthetic, `portfolio` is stubbed in sys.modules
(the package trips the py3.9 annotation quirk on the host), the signal call is
recorded instead of computed, no push, no Mongo.
"""
import math
import sys
import types
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts import signal_watch as SW            # noqa: E402
from supply_demand import mood as mood_mod          # noqa: E402
from supply_demand import patterns as pat           # noqa: E402
from supply_demand import timeframes as TF          # noqa: E402


def _frame_15m_with_partial_bucket(n=60):
    idx = pd.date_range("2026-09-03 13:45", periods=n, freq="15min", tz="UTC")
    c = [50.0 + math.sin(i / 3.0) * 0.4 for i in range(n)]
    h = [x + 0.25 for x in c]; l = [x - 0.25 for x in c]
    h[-2], l[-2], c[-2] = 52.5, 50.3, 52.4          # displacement bar (closed)
    h[-1], l[-1], c[-1] = 52.9, 52.7, 52.8          # in-progress bucket
    return pd.DataFrame({"open": c, "high": h, "low": l, "close": c,
                         "volume": [1e5] * n}, index=idx)


def _stub_portfolio(monkeypatch):
    pkg = types.ModuleType("portfolio")
    pkg.__path__ = []                                   # a package, so submodule imports resolve here
    alerts = types.ModuleType("portfolio.alerts")
    alerts._resolve_owner = lambda: "o@x"
    store = types.ModuleType("portfolio.store")
    store._get_db = lambda: None
    monkeypatch.setitem(sys.modules, "portfolio", pkg)
    monkeypatch.setitem(sys.modules, "portfolio.alerts", alerts)
    monkeypatch.setitem(sys.modules, "portfolio.store", store)


def _watch(monkeypatch, df, partial):
    _stub_portfolio(monkeypatch)
    meta = {"label": "15 min", "bars": len(df), "available": True, "partial": partial,
            "as_of": "2026-09-04 04:37:00+00:00", "reason": None}
    monkeypatch.setattr(TF, "frame_for", lambda sym, tf, *a, **k: (df.copy(), dict(meta)))
    monkeypatch.setattr(SW, "WATCH_TFS", ("15m",))
    seen = []

    def fake_signal(frame, bands, mood_read=None, *, last_price=None, atr_value=None, **k):
        seen.append({"bands": bands, "last": last_price, "atr": atr_value, "bars": len(frame)})
        return {"action": "WAIT"}
    monkeypatch.setattr(mood_mod, "signal", fake_signal)
    out = SW.check_once(push=False, force=True, symbols=["ACME"])
    assert out["ran"] is True and out["checked"] == 1 and len(seen) == 1, out
    return seen[0]


def test_signal_watch_reads_structure_off_closed_buckets_and_prices_off_the_live_one(monkeypatch):
    df = _frame_15m_with_partial_bucket()
    s = _watch(monkeypatch, df, partial=True)
    assert s["last"] == 52.8, "the signal is still priced at the live bucket"
    gaps = [b for b in s["bands"] if b.get("source") != "swing"]
    assert not any(abs(float(b["hi"]) - 52.7) < 1e-9 for b in gaps), gaps
    assert s["atr"] == pat.atr(df.iloc[:-1]), "ATR without the partial-day true range"
    assert s["bars"] == len(df), "mood/signal keep their own closed-bar discipline on the whole frame"


def test_signal_watch_reads_a_closed_last_bucket_whole(monkeypatch):
    df = _frame_15m_with_partial_bucket()
    s = _watch(monkeypatch, df, partial=False)
    gaps = [b for b in s["bands"] if b.get("source") != "swing"]
    assert any(abs(float(b["hi"]) - 52.7) < 1e-9 for b in gaps), "a CLOSED bucket forming the gap counts"
    assert s["atr"] == pat.atr(df)
