"""Personal holding diagnosis — behavioral (2026-06-04).

The card must answer "how is MY position doing, and how do I hold it?" anchored to
the user's cost basis (not the stock's 5-day move). Verifies the pure shaping of
`position_lens` output into the personal block: P&L sign, breakeven-from-cost, R
targets %, and the Minervini hold-until-signal tripwires (nearest-first, signed
below-price), per docs/sepa/holding_diagnosis_methodology.md.

The module is loaded standalone (not via `import portfolio`) because the package
pulls in FastAPI models that the 3.9 toolchain venv can't import — these pure
helpers don't touch the package.
"""
import importlib.util
import os

import numpy as np
import pandas as pd

_PATH = os.path.join(os.path.dirname(__file__), "..", "portfolio", "diagnosis.py")
_spec = importlib.util.spec_from_file_location("diagnosis_mod", _PATH)
dg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dg)


def _df(last=336.0, n=220, start=200.0):
    """A rising close series so MA50/MA200 sit below `last` (tripwires negative)."""
    close = np.linspace(start, last, n)
    return pd.DataFrame({"close": close, "volume": np.full(n, 1_000_000.0)})


def _pos(last=336.0, verdict="HOLD", gain_pct=-1.82, triggers=None):
    return {
        "ok": True,
        "verdict": verdict,
        "summary": f"{verdict} — read.",
        "r_multiple": -0.21,
        "pnl": {"gain_pct": gain_pct, "gain_dollars": -130.0},
        "current": {"last_close": last, "stage": 2},
        "stop": {"used": 312.86, "distance_pct": 7.0},
        "targets": {"r1": 359.96, "r2": 383.51, "r3": 407.06},
        "triggers": triggers or [],
    }


ENTRY = 342.64


def test_shape_anchors_to_cost_and_breakeven_when_underwater():
    p = dg._shape_position(_pos(last=336.0, gain_pct=-1.82), ENTRY, _df(last=336.0))
    assert p["entry"] == 342.64
    assert p["gain_pct"] == -1.82                       # since THEIR entry, not the 5d move
    assert p["r_multiple"] == -0.21
    # how far price must RISE to reach cost: (342.64/336 - 1)*100
    assert p["to_breakeven_pct"] == round((ENTRY / 336.0 - 1) * 100, 2)
    assert p["to_breakeven_pct"] > 0
    assert p["verdict"] == "HOLD"


def test_no_breakeven_distance_when_in_profit():
    p = dg._shape_position(_pos(last=380.0, gain_pct=9.5), ENTRY, _df(last=380.0))
    assert p["to_breakeven_pct"] == 0.0                 # already above cost


def test_targets_carry_pct_from_here():
    last = 336.0
    p = dg._shape_position(_pos(last=last), ENTRY, _df(last=last))
    r1 = next(t for t in p["targets"] if t["label"] == "R1")
    assert r1["price"] == 359.96
    assert r1["pct_from_here"] == round((359.96 / last - 1) * 100, 1)
    assert [t["label"] for t in p["targets"]] == ["R1", "R2", "R3"]


def _df_runup(last=336.0, n=220, base=250.0, ramp=40):
    """Long base then a recent run-up — so the MAs sit FAR below price and the
    hard stop is the nearest (tightest) tripwire, as in a real Stage-2 advance."""
    close = np.concatenate([np.full(n - ramp, base), np.linspace(base, last, ramp)])
    return pd.DataFrame({"close": close, "volume": np.full(n, 1_000_000.0)})


def test_tripwires_sorted_nearest_first_and_signed_below_price():
    p = dg._shape_position(_pos(last=336.0), ENTRY, _df_runup(last=336.0))
    dists = [t["distance_pct"] for t in p["tripwires"]]
    # every tripwire sits BELOW price → negative distance, and is page-cited.
    for t in p["tripwires"]:
        assert t["distance_pct"] < 0
        assert t["cite"]
    # nearest-first: sorted by absolute distance ascending.
    assert [abs(d) for d in dists] == sorted(abs(d) for d in dists)
    # after a run-up the stop is the tightest exit; the 200-day is the deepest.
    assert p["tripwires"][0]["label"] == "Hard stop"
    assert p["tripwires"][-1]["label"] == "200-day line"
    assert next(t for t in p["tripwires"] if t["label"] == "Hard stop")["cite"] == "p.296"


def test_fired_signals_passed_through():
    trig = [{"rule": "stop_loss_breached", "verdict": "FULL_EXIT", "msg": "stop hit"}]
    p = dg._shape_position(_pos(verdict="FULL_EXIT", triggers=trig), ENTRY, _df())
    assert p["verdict"] == "FULL_EXIT"
    assert len(p["fired"]) == 1


def test_not_ok_position_returns_none():
    assert dg._shape_position({"ok": False, "reason": "no data"}, ENTRY, _df()) is None


def test_ma_needs_enough_rows():
    assert dg._ma(_df(n=220), 200) is not None
    assert dg._ma(_df(n=120), 200) is None              # < n rows → None, never NaN
    # MA50 equals the mean of the last 50 closes.
    d = _df(last=336.0, n=220)
    assert abs(dg._ma(d, 50) - float(d["close"].iloc[-50:].mean())) < 1e-6
