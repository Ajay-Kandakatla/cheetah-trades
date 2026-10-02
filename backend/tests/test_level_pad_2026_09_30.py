"""🧱 LEVEL PAD (2026-09-30) — the 1% stop-side pad under demand floors.

Ajay 2026-09-30, verbatim: "Also increase our Demand zone and key levels sizes by
1%. becuz Generally we are missing this, I been noticing if the demand zone or key
level is 133, it holding at 132. My theory is MMs know stoplosses are beyond 133."

His 133/132 case through every engine that reads a demand FLOOR, the resistance
reads that must NOT move, the kill switch (DEMAND_PAD_PCT = 0 = the pre-pad
engine, expected values computed here from the drawn-lo formula), the dedupe
keys, the measured floor-held gate (still on the DRAWN floor), and the source
guards that keep ONE constant behind every consumer. Hermetic: no network, no
Mongo, no price cache.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import math
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from supply_demand import level_pad as LP              # noqa: E402
from supply_demand import sd_liquidity as SL           # noqa: E402
from supply_demand import alert_gates as AG            # noqa: E402
from supply_demand import price_zones as PZ            # noqa: E402
from supply_demand import demand_reentry as DR         # noqa: E402
from supply_demand import zone_edge as ZE              # noqa: E402
from supply_demand import demand_alerts as DA          # noqa: E402
from supply_demand import zone_bounce_alerts as ZB     # noqa: E402
from supply_demand import bounce_room as BR            # noqa: E402
from supply_demand import deep_demand as DD            # noqa: E402
from supply_demand import quick_bounce as QB           # noqa: E402
from supply_demand import room_floor as RF             # noqa: E402
from supply_demand import rules_info as RI             # noqa: E402
from supply_demand import zone_pad_measured as ZPM     # noqa: E402
from trading import zone_edge_entry as ZEE             # noqa: E402
from trading import options_lane as OL                 # noqa: E402
from trading import catalyst_entry as CE               # noqa: E402
from trading.broker_alpaca import BrokerError          # noqa: E402
from tests.test_supply_demand_contracts import _code_only   # noqa: E402

# portfolio/__init__ trips the py3.9 annotation quirk — load the module standalone
_spec = importlib.util.spec_from_file_location(
    "supply_watch_pad_standalone", BACKEND / "portfolio" / "supply_watch.py")
SW = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SW)

ET = ZoneInfo("America/New_York")

# His band: 133.00-135.00, tested 3x. Everything below is the worked example.
B = {"kind": "demand", "lo": 133.0, "hi": 135.0, "touches": 3, "strength": 60.0}
SUP = {"kind": "supply", "lo": 150.0, "hi": 152.0, "touches": 3, "strength": 60.0}
SHELF = {"kind": "supply", "lo": 133.0, "hi": 135.0, "touches": 3, "strength": 60.0}


@pytest.fixture
def nopad(monkeypatch):
    """The kill switch: the pre-pad engine."""
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 0.0)


def _drawn_stop(lo, buf):
    """The PRE-PAD stop formula, computed here (never the engine)."""
    return lo * (1.0 - buf / 100.0)


# ═════════════════════════════════════════════════════════════════════════════
# 1. level_pad units
# ═════════════════════════════════════════════════════════════════════════════
def test_the_one_number_is_the_house_stop_shelf_by_name():
    assert LP.DEMAND_PAD_PCT is SL.STOP_SHELF_PCT
    assert LP.pad_pct() == 1.0
    assert LP.PAD_BAND_KINDS == ("demand",) and LP.PAD_KEY_KINDS == ("low",)
    assert LP.PAD_FLOOR_HELD is False


def test_padded_is_his_133_to_131_67_and_equals_the_stop_shelf_bottom():
    assert LP.padded(133.0) == 131.67
    for x in (1.23, 133.0, 5000.5):
        assert LP.padded(x) == SL.stop_shelf(x)["bottom"], x


@pytest.mark.parametrize("bad", [0, -1, "x", float("nan"), float("inf"), None])
def test_NEGATIVE_padded_garbage_is_none(bad):
    assert LP.padded(bad) is None


def test_pad_zero_is_the_identity(nopad):
    assert LP.pad_pct() == 0.0
    assert LP.padded(133.0) == 133.0
    assert LP.support_floor(B) == 133.0
    assert LP.pad_fields(B) == {}
    assert LP.key_edge(133.0, "low", "support") == 133.0


def test_NEGATIVE_a_negative_or_garbage_pad_is_off(monkeypatch):
    for v in (-1.0, "x", float("nan")):
        monkeypatch.setattr(LP, "DEMAND_PAD_PCT", v)
        assert LP.pad_pct() == 0.0 and LP.support_floor(B) == 133.0


def test_support_floor_by_kind():
    assert LP.support_floor(B) == 131.67
    assert LP.support_floor(SHELF) == 133.0                            # supply shelf: drawn
    assert LP.support_floor({"lo": 133.0, "hi": 135.0}) == 131.67      # no kind = demand
    for bad in (None, {}, {"lo": 0}, {"lo": -5}, {"lo": "x"}, "band", 7):
        assert LP.support_floor(bad) is None, bad


def test_in_band_boundaries():
    assert LP.in_band(B, 131.67) and LP.in_band(B, 135.00) and LP.in_band(B, 132.0)
    assert not LP.in_band(B, 131.66) and not LP.in_band(B, 135.01)
    assert not LP.in_band(SHELF, 132.5), "a supply shelf is never padded"
    assert LP.under_floor(B, 131.66) and not LP.under_floor(B, 131.67)
    assert not LP.in_band(B, None) and not LP.under_floor(B, "x")


def test_sweep_floor_is_drawn_by_default_padded_only_by_his_call(monkeypatch):
    assert LP.sweep_floor(B) == 133.0
    monkeypatch.setattr(LP, "PAD_FLOOR_HELD", True)
    assert LP.sweep_floor(B) == 131.67


def test_key_edge_only_pads_a_support_side_low():
    assert LP.key_edge(133.0, "low", "support") == 131.67
    assert LP.key_edge(133.0, "high", "support") == 133.0
    assert LP.key_edge(133.0, "low", "resistance") == 133.0
    assert LP.key_edge(0, "low", "support") is None


def test_same_band_is_the_2dp_grain():
    assert LP.same_band(B, {"lo": 133.001, "hi": 134.999})
    assert LP.same_band(B, {"lo": 133.0})                         # a level: no hi
    assert not LP.same_band(B, {"lo": 133.01, "hi": 135.0})
    assert not LP.same_band(B, None) and not LP.same_band("x", B)
    # room_floor's identity rule IS this one
    assert RF._same_band(B, {"lo": 133.001, "hi": 134.999}) is True
    assert RF._same_band(B, None) is False


def test_pad_fields_never_touch_lo_hi():
    assert LP.pad_fields(B) == {"pad_lo": 131.67, "pad_pct": 1.0}
    assert LP.pad_fields(SHELF) == {} and LP.pad_fields(None) == {}
    assert LP.describe()["shelf_pct"] == SL.STOP_SHELF_PCT


def test_zone_pad_measured_reports_and_pending_still_says_so(monkeypatch):
    # 2026-10-01: the full run reported no_signal (pinned to its artifact in
    # test_zone_pad_study); with no literal the panel falls back to UNMEASURED
    assert ZPM.status() == ZPM.STATUS_NO_SIGNAL
    assert ZPM.verdict_line().startswith("MEASURED 2026-10-01: no_signal")
    monkeypatch.setattr(ZPM, "MEASURED", None)
    assert ZPM.status() == ZPM.STATUS_PENDING
    assert ZPM.verdict_line() == ZPM.PENDING_NOTE
    assert "UNMEASURED" in ZPM.PENDING_NOTE


# ═════════════════════════════════════════════════════════════════════════════
# 2. His 133 -> 132 case through every engine
# ═════════════════════════════════════════════════════════════════════════════
def test_proximity_gate_reaches_the_pad_and_the_top_is_unchanged():
    assert AG.demand_proximity_gate(132.00, B) is True
    assert AG.demand_proximity_gate(131.66, B) is False
    assert AG.demand_proximity_gate(136.35, B) is True          # 135 x 1.01
    assert AG.demand_proximity_gate(136.36, B) is False         # the upper bound did NOT move
    assert AG.demand_proximity_gate(132.00, SHELF) is False     # a shelf: drawn floor


def test_zone_edge_reads_a_print_in_the_pad_as_in_the_band():
    r = ZE.read_near_demand(132.0, [B, SUP], -1.0, 136.0)
    assert r["tier"] == "in" and r["dist_pct"] == 0.0
    assert r["band"]["lo"] == 133.0 and r["band"]["pad_lo"] == 131.67


def test_demand_alerts_read_in_the_pad_and_under_it():
    assert DA.read(132.0, B) == {"tier": "at", "state": "in", "dist_pct": 0.0}
    assert DA.read(131.6, B) is None


def test_pick_entry_zone_takes_the_band_whose_pad_holds_the_print():
    z = DR._pick_entry_zone(132.0, [B, {"kind": "demand", "lo": 110.0, "hi": 112.0}])
    assert z is B


def test_trade_plan_stop_is_1_5_pct_under_the_pad():
    p = DR.trade_plan(134.0, B, [SUP])
    assert p["stop"] == 129.69
    assert p["entry_low"] == 133.0 and p["entry_high"] == 135.0      # the drawn band


def test_plan_txt_stop_is_0_5_pct_under_the_pad():
    room = AG.room_read(134.0, [B, SUP], 136.0, entry_band=B)
    txt = AG.plan_txt(134.0, B, room)
    assert "stop $131.01" in txt and "1% pad" in txt and "$131.67" in txt
    assert txt.startswith("buy $133-135 · stop $131.01 (0.5% under the 1% pad at $131.67, 2.2% risk)")
    assert "bounce" not in txt.lower()


def test_deep_arrival_in_the_pad_is_an_arrival_not_a_crossing():
    top = {"kind": "demand", "lo": 140.0, "hi": 142.0, "touches": 3, "strength": 60}
    got = DD.arrival([top, B], 132.0)
    assert got is not None
    levels, arr, broken = got
    assert levels == 1 and arr is B and broken == [top]


def test_deep_arrival_under_the_drawn_floor_is_not_one_with_the_pad_off(nopad):
    top = {"kind": "demand", "lo": 140.0, "hi": 142.0, "touches": 3, "strength": 60}
    assert DD.arrival([top, B], 132.0) is None


def test_deep_read_says_in_and_carries_the_pad():
    top = {"kind": "demand", "lo": 140.0, "hi": 142.0, "touches": 3, "strength": 60}
    rec = {"demand_zones": [top, B], "last_price": 132.0, "prev_close": 132.5}
    r = DD.read(rec)
    assert r["state"] == "in" and r["dist_pct"] == 0.0
    assert r["second_band"]["pad_lo"] == 131.67 and r["second_band"]["lo"] == 133.0
    assert r["top_band"]["pad_lo"] == 138.6 and r["top_band"]["kind"] == "demand"
    assert r["reclaiming"] is False, "a prior close inside the pad is not a reclaim"


def test_quick_bounce_stop_under_the_pad():
    doc = {"bands": [B, SUP], "prev_close": 136.0}
    r = QB.live_row("PADX", {}, doc, 132.0)
    assert r["state"] == "inside" and r["dist_pct"] == 0.0
    assert r["stop"] == 131.01
    assert r["room"]["target"] == 150.0, "its own band is never its own ceiling"


def test_zone_edge_entry_stop_request_is_4dp_under_the_pad_never_padded_twice():
    stop, pct = ZEE.stop_request(134.0, LP.support_floor(B))
    # 131.67 x 0.995 = 131.01165 exactly; the float engine rounds it to 131.0116 (4 dp)
    assert stop == round(131.67 * (1 - ZEE.STOP_BUFFER_PCT / 100.0), 4) == 131.0116
    assert pct == round((134.0 - 131.0117) / 134.0 * 100.0, 2)


class _NoChainBroker:
    def option_contracts(self, *a, **k):
        raise BrokerError("no chain in a unit test")

    def option_snapshots(self, *a, **k):
        raise BrokerError("no chain in a unit test")


def test_options_lane_stop_under_the_pad_and_the_short_put_at_or_under_it():
    c = {"symbol": "PADX", "band": B, "last": 134.0}
    out = OL.plan_entry(_NoChainBroker(), c, {"room": {"target": 150.0}}, 20_000.0,
                        date(2026, 9, 30))
    assert out["stop_underlying"] == 131.01
    contracts = [{"symbol": "P132", "strike_price": 132.0, "open_interest": 10_000},
                 {"symbol": "P131", "strike_price": 131.0, "open_interest": 10_000}]
    snaps = {"P132": {"bid": 2.0, "ask": 2.05}, "P131": {"bid": 1.6, "ask": 1.65}}
    got, _s, why = OL.pick_put_short_strike(contracts, snaps, LP.support_floor(B))
    assert why is None and got["strike_price"] == 131.0, "132 is above the 131.67 pad: refused"
    src = _code_only(ast.get_source_segment(_src("trading/options_lane.py"),
                                            _fn("trading/options_lane.py", "plan_entry")))
    assert "_plan_put_spread(brk, sym, expiry, LP.support_floor(band))" in src


def test_catalyst_stop_under_the_pad_4dp():
    row = {"coverage": "ok", "print": 134.0, "print_age_sec": 10, "bounce": None}
    doc = {"bands": [B, SUP], "prev_close": 136.0}
    ok, d = CE.zone_gate({"symbol": "PADX"}, row, doc)
    assert d["side"] == "demand"
    assert d["stop_price"] == round(131.67 * (1 - CE.STOP_BUFFER_PCT / 100.0), 4) == 131.0116


def test_supply_watch_stop_under_the_pad_and_a_supply_shelf_on_its_lo():
    assert SW.stop_for(B) == 131.01
    assert SW.stop_for(SHELF) == round(_drawn_stop(133.0, AG.STOP_BUFFER_PCT), 2)
    # a holding bought at 132 (inside the pad) is measured from THIS band
    band = SW.entry_band(132.0, [{"lo": 133.0, "hi": 135.0, "touches": 3}], [])
    assert band["lo"] == 133.0


def test_zone_bounce_room_r_is_against_the_padded_floor():
    room = ZB.room_for(134.0, [SUP], B)
    risk = (134.0 - 131.67) / 134.0 * 100.0
    raw = (150.0 - 134.0) / 134.0 * 100.0
    assert room["rr"] == round(raw / risk, 1)


def test_bounce_room_in_demand_and_demand_read_in_the_pad():
    doc = {"bands": [B, SUP], "prev_close": 136.0}
    r = BR.in_demand_read(132.0, doc)
    assert r is not None and r["band"]["lo"] == 133.0
    d = BR.demand_read(132.0, doc)
    assert d["in_band"] is True and d["distance_pct"] == 0.0
    assert BR.demand_read(131.6, doc) is None, "under the pad: fell through"


def test_price_zones_compute_opt_in_pads_demand_only():
    df = _zone_frame()
    base = PZ.compute(df)
    assert json.dumps(base, sort_keys=True, default=str) == \
        json.dumps(PZ.compute(df, demand_pad_pct=None), sort_keys=True, default=str) == \
        json.dumps(PZ.compute(df, demand_pad_pct=0), sort_keys=True, default=str)
    assert "demand_pad_pct" not in base["params"]
    dz = base["demand_zones"][0]
    px = round(dz["lo"] * 0.995, 2)                      # inside the 1% pad, under the drawn lo
    padded = PZ.compute(df, last_price=px, demand_pad_pct=1.0)
    plain = PZ.compute(df, last_price=px)
    assert padded["params"]["demand_pad_pct"] == 1.0
    d2 = next(z for z in padded["demand_zones"] if z["lo"] == dz["lo"])
    assert d2["lo"] == dz["lo"] and d2["hi"] == dz["hi"]                  # drawn edges never move
    assert d2["pad_lo"] == LP.padded(dz["lo"]) and d2["in_price"] is True
    assert padded["verdict"]["state"] == "AT_DEMAND"
    assert all("pad_lo" not in z for z in padded["supply_zones"])
    assert all(z is not d2 and not (z["kind"] == "demand" and z["lo"] == dz["lo"])
               for z in [padded["nearest_resistance"]] if z), "its own pad is never overhead"
    assert plain["verdict"]["state"] != "AT_DEMAND"


def _zone_frame():
    """A deterministic swing frame with demand bands under the last close."""
    n = 200
    t = np.arange(n)
    close = 100 + 8 * np.sin(t / 9.0) + t * 0.02
    df = pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                       "close": close, "volume": np.full(n, 1_000_000.0)},
                      index=pd.bdate_range("2025-10-01", periods=n))
    return df


# ═════════════════════════════════════════════════════════════════════════════
# 3. Resistance unchanged (NEGATIVES)
# ═════════════════════════════════════════════════════════════════════════════
def test_a_broken_demand_band_above_the_print_is_measured_to_its_drawn_lo(monkeypatch):
    got = AG.room_read(120.0, [B], None)
    assert got["target"] == 133.0 and got["state"] == "ROOM"
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 0.0)
    assert AG.room_read(120.0, [B], None) == got


@pytest.mark.parametrize("px", [133.0, 134.0, 135.0, 136.0, 140.0])
def test_resistance_reads_identical_with_the_pad_on_and_off(px, monkeypatch):
    above = {"kind": "demand", "lo": 145.0, "hi": 147.0, "touches": 3, "strength": 60.0}
    bands = [B, above, SUP]
    doc = {"bands": bands, "prev_close": 136.0}
    supply = [SUP]
    demand = [B, above]

    def reads():
        return (AG.room_read(px, bands, 136.0),
                BR.room_read(px, doc),
                ZEE.room_ok(px, 2.0, doc),
                SW.overhead_bands(supply, demand, px, 136.0),
                AG.first_weak_lid(bands, px))
    on = reads()
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 0.0)
    assert reads() == on


def test_room_gate_entry_band_is_the_only_room_change():
    ok, room = AG.room_gate(132.0, [B, SUP], entry_band=B)
    assert ok is True and room["target"] == 150.0
    ok2, room2 = AG.room_gate(132.0, [B, SUP])
    assert ok2 is False and room2["target"] == 133.0, "without entry_band its own band is a lid"


def test_NEGATIVE_entry_band_never_excludes_a_supply_shelf():
    """A shelf is not padded, so naming it changes nothing (gap day: it is overhead)."""
    ok, room = AG.room_gate(134.0, [SHELF, SUP], 136.0 * 1.2, entry_band=SHELF)
    ok0, room0 = AG.room_gate(134.0, [SHELF, SUP], 136.0 * 1.2)
    assert (ok, room) == (ok0, room0)


def test_NEGATIVE_entry_band_with_the_pad_off_is_byte_identical(nopad):
    assert AG.room_gate(132.0, [B, SUP], entry_band=B) == AG.room_gate(132.0, [B, SUP])


# ═════════════════════════════════════════════════════════════════════════════
# 4. The measured floor-held gate still reads the DRAWN floor
# ═════════════════════════════════════════════════════════════════════════════
def _sweep_frame(low_hit=None):
    """30 closed daily bars sitting on 136; bar -5 dips to `low_hit` and closes back at 134."""
    idx = pd.bdate_range("2026-08-10", periods=30)
    df = pd.DataFrame({"open": 136.0, "high": 137.0, "low": 135.2, "close": 136.0,
                       "volume": 1_000_000.0}, index=idx)
    if low_hit is not None:
        df.iloc[-5, df.columns.get_loc("low")] = low_hit
        df.iloc[-5, df.columns.get_loc("close")] = 134.0
        df.iloc[-5, df.columns.get_loc("volume")] = 3_000_000.0
    return df


def test_a_pierce_inside_the_pad_is_still_swept_and_the_gate_still_refuses():
    df = _sweep_frame(132.0)
    r = AG.sweep_read(B, frame=df)
    assert r["state"] in ("swept", "broken") and r["in_pad"] is True
    assert "· inside the 1% pad" in AG.sweep_txt(r)
    assert AG.floor_held_gate(B, frame=df, read=r) is False
    assert "bounce" not in AG.sweep_txt(r).lower()


def test_NEGATIVE_a_pierce_past_the_pad_is_not_in_pad():
    r = AG.sweep_read(B, frame=_sweep_frame(130.0))
    assert r["state"] in ("swept", "broken") and r["in_pad"] is False
    assert "pad" not in AG.sweep_txt(r)


def test_his_call_1_flips_the_floor_held_gate_to_the_pad(monkeypatch):
    monkeypatch.setattr(LP, "PAD_FLOOR_HELD", True)
    df = _sweep_frame(132.0)
    r = AG.sweep_read(B, frame=df)
    assert r["state"] == "intact" and AG.floor_held_gate(B, frame=df, read=r) is True


def test_an_intact_floor_reads_intact_either_way():
    r = AG.sweep_read(B, frame=_sweep_frame(None))
    assert r["state"] == "intact" and r["in_pad"] is False


def test_the_corner_guard_a_print_under_the_floor_with_no_day_low_is_a_pierce():
    df = _sweep_frame(None)
    r = AG.sweep_read(B, frame=df, last=132.5, day=date(2026, 9, 30))
    assert r["state"] in ("swept", "broken"), "the print IS a pierce"
    # NEGATIVE: a print above the floor with no day low changes nothing
    assert AG.sweep_read(B, frame=df, last=134.5, day=date(2026, 9, 30))["state"] == "intact"


# ═════════════════════════════════════════════════════════════════════════════
# 5. The phone set is unchanged (one zone_edge pass, pad on vs off)
# ═════════════════════════════════════════════════════════════════════════════
class _Coll:
    def __init__(self):
        self.docs = {}

    def find(self, q=None, *a, **k):
        ids = ((q or {}).get("_id") or {}).get("$in")
        return [d for k2, d in self.docs.items() if ids is None or k2 in ids]

    def find_one(self, q=None, *a, **k):
        return self.docs.get((q or {}).get("_id"))

    def insert_one(self, doc):
        if doc["_id"] in self.docs:
            from pymongo.errors import DuplicateKeyError
            raise DuplicateKeyError("dup")
        self.docs[doc["_id"]] = doc

    def update_one(self, q, u, upsert=False):
        cur = self.docs.setdefault(q["_id"], {"_id": q["_id"]})
        cur.update(u.get("$set") or {})
        return type("R", (), {"upserted_id": None, "modified_count": 1})()

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = doc

    def delete_one(self, q):
        self.docs.pop(q.get("_id"), None)

    def delete_many(self, q):
        pass


NOW = datetime(2026, 9, 3, 10, 0, tzinfo=ET)
DAY = "2026-09-03"
INT = {"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 3, "strength": 60.0}
INT_SUP = {"kind": "supply", "lo": 100.0, "hi": 102.0, "touches": 3, "strength": 60.0}


def _snap(last, prev, low):
    ts_ns = int((NOW - timedelta(seconds=30)).timestamp() * 1e9)
    return {"open": last, "high": last, "low": low, "close": last, "volume": 1e6,
            "change_pct": (last / prev - 1) * 100, "last_trade_price": last,
            "last_trade_ts_ms": ts_ns, "prev_day_close": prev}


def _daily(level):
    idx = pd.bdate_range("2026-08-01", periods=22)
    return pd.DataFrame({"open": level * 1.03, "high": level * 1.04, "low": level * 1.02,
                         "close": level * 1.03, "volume": 1_000_000.0}, index=idx)


def _one_pass(monkeypatch):
    from push import sender
    sent = []
    monkeypatch.setattr(sender, "send_to_user",
                        lambda owner, payload, kind=None: sent.append(payload) or
                        {"sent": 1, "failed": 0, "total_targets": 1})
    frames = {"PADX": _daily(133.0), "INTX": _daily(90.0)}
    monkeypatch.setattr(ZE.AG, "daily_frame", lambda sym, frame=None: frames.get(sym))
    monkeypatch.setattr(ZE.AG, "mood_read", lambda sym, frame=None: None)
    monkeypatch.setattr(ZE.AG, "knife_read",
                        lambda sym, frame=None: {"knife": False, "trend": "rising"})
    monkeypatch.setattr(ZE.AG, "reversal_mood_read",
                        lambda sym, frame=None, bars=None: {"score": 40.0, "label": "bullish",
                                                            "bars": 60, "bullish": True})
    store = {"PADX": {"_id": f"PADX:{DAY}", "symbol": "PADX", "date": DAY, "geom": "board",
                      "bands": [B, SUP], "atr14": 1.0, "prev_close": 138.0},
             "INTX": {"_id": f"INTX:{DAY}", "symbol": "INTX", "date": DAY, "geom": "board",
                      "bands": [INT, INT_SUP], "atr14": 1.0, "prev_close": 94.0}}
    # PADX: yesterday 138, the day's low 131.70 INSIDE the pad, print 132.40 (a reversal)
    # INTX: yesterday 94, low 90.5 inside the band, print 91.2 (a reversal, floor intact)
    snap = {"PADX": _snap(132.4, 138.0, 131.7), "INTX": _snap(91.2, 94.0, 90.5)}
    out = ZE.check_once(push=True, force=True, track=False, store=store, snapshot=snap,
                        caps={"PADX": 5e9, "INTX": 5e9}, names={}, owner="o@x", now=NOW,
                        coll_break=_Coll(), coll_demand=_Coll(), latest_coll=_Coll(),
                        track_coll=_Coll())
    return out, sent


def test_the_phone_set_is_identical_with_the_pad_on_and_off(monkeypatch):
    out_on, sent_on = _one_pass(monkeypatch)
    listed_on = sorted(r["symbol"] for r in out_on["near_demand"])
    titles_on = sorted(s["title"].split()[1] for s in sent_on)
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 0.0)
    out_off, sent_off = _one_pass(monkeypatch)
    titles_off = sorted(s["title"].split()[1] for s in sent_off)
    assert titles_on == titles_off == ["INTX"], "the pad changes no push"
    assert "PADX" in listed_on, "the board lists the name holding in the pad"
    assert "PADX" not in [r["symbol"] for r in out_off["near_demand"]]
    assert out_on["skipped_floor"] >= 1, "PADX: the drawn floor was pierced, the gate refuses"
    # only the plan's words differ
    assert "1% pad" in sent_on[0]["body"] and "1% pad" not in sent_off[0]["body"]


# ═════════════════════════════════════════════════════════════════════════════
# 6. Kill switch — every function returns the PRE-PAD value (computed here)
# ═════════════════════════════════════════════════════════════════════════════
def test_kill_switch_restores_every_pre_pad_value(nopad):
    assert AG.demand_proximity_gate(132.0, B) is False
    assert ZE.read_near_demand(132.0, [B, SUP], -1.0, 136.0) is None
    assert DA.read(132.0, B) is None
    p = DR.trade_plan(134.0, B, [SUP])
    assert p["stop"] == round(_drawn_stop(133.0, DR.STOP_BUFFER_PCT), 2)
    txt = AG.plan_txt(134.0, B, None)
    stop = _drawn_stop(133.0, AG.STOP_BUFFER_PCT)
    assert txt == ("buy $133-135 · stop $%.2f (0.5%% under the floor, %.1f%% risk) · "
                   "target: clear runway" % (stop, (134.0 - stop) / 134.0 * 100.0))
    r = QB.live_row("PADX", {}, {"bands": [B, SUP], "prev_close": 136.0}, 134.0)
    assert r["stop"] == round(_drawn_stop(133.0, QB.STOP_BUFFER_PCT), 2)
    assert ZEE.stop_request(134.0, LP.support_floor(B))[0] == round(_drawn_stop(133.0, ZEE.STOP_BUFFER_PCT), 4)
    assert SW.stop_for(B) == round(_drawn_stop(133.0, AG.STOP_BUFFER_PCT), 2)
    assert "pad_lo" not in ZE.read_near_demand(134.0, [B, SUP], -1.0, 136.0)["band"]
    assert AG.sweep_read(B, frame=_sweep_frame(132.0))["in_pad"] is False
    assert BR.demand_read(132.0, {"bands": [B]}) is None


# ═════════════════════════════════════════════════════════════════════════════
# 7. Dedupe keys read the DRAWN band
# ═════════════════════════════════════════════════════════════════════════════
def test_dedupe_keys_never_move():
    served = ZE.read_near_demand(132.0, [B, SUP], -1.0, 136.0)["band"]
    assert served["pad_lo"] == 131.67
    assert DA.state_key("X", served, DAY, "at") == "X:133.00-135.00:%s:at" % DAY
    assert ZE.break_state_key("X", served, DAY, "in") == "X:133.00-135.00:%s:in" % DAY
    assert ZE.first_seen_key("X", "demand", served) == "X:demand:133.00-135.00"
    assert ZEE.state_key("X", served, DAY).startswith("X:133")
    assert ZEE.race_id("X", "demand", served, DAY) == "X:demand:133-135:%s" % DAY


# ── Z5: Back in Demand's in-band read + broken-band guard on a REAL frame ──
def _z5_frame(last_close, prior_close=None):
    """test_demand_reentry's re-entry shape (tested band ~95.04-96.03, modest
    uptrend, mild dip back in) with only the last (and optionally the prior)
    close overridden — the band geometry does not move."""
    px = np.concatenate([
        np.linspace(100, 96, 40), np.linspace(96, 112, 60), np.linspace(112, 97, 30),
        np.linspace(97, 104, 100), np.linspace(104, 99.5, 10),
    ])
    n = len(px)
    df = pd.DataFrame({"open": px, "high": px * 1.01, "low": px * 0.99, "close": px,
                       "volume": [2_000_000] * n},
                      index=pd.bdate_range("2025-08-01", periods=n))
    df.iloc[-1, df.columns.get_loc("close")] = float(last_close)
    if prior_close is not None:
        df.iloc[-2, df.columns.get_loc("close")] = float(prior_close)
    return df


@pytest.fixture
def _z5_band(monkeypatch):
    monkeypatch.setattr(DR, "PINNED_ETFS", ())
    ez = DR.decide_from_frame(_z5_frame(95.5), "CTRL")["entry_zone"]
    assert ez and ez["pad_lo"] is not None and ez["pad_lo"] < ez["lo"] <= 95.5 <= ez["hi"]
    return ez


def test_z5_a_close_in_the_pad_is_in_the_band_on_a_real_frame(_z5_band):
    in_pad = round((_z5_band["pad_lo"] + _z5_band["lo"]) / 2, 2)
    rec = DR.decide_from_frame(_z5_frame(in_pad), "INPAD")
    assert rec["entry_zone"]["lo"] == _z5_band["lo"], "geometry must not move"
    assert rec["last_price"] < rec["entry_zone"]["lo"]
    assert rec["in_demand_band"] is True and rec["zone_broken"] is False


def test_z5_NEGATIVE_the_same_close_is_out_of_the_band_with_the_pad_off(_z5_band, nopad):
    in_pad = round((_z5_band["pad_lo"] + _z5_band["lo"]) / 2, 2)
    rec = DR.decide_from_frame(_z5_frame(in_pad), "INPAD0")
    assert rec["in_demand_band"] is False and rec["is_reentry"] is False


def test_z5_a_prior_close_in_the_pad_does_not_break_the_band(_z5_band):
    """The broken-band guard reads the PADDED floor: yesterday's close inside the
    pad, back inside the band today, is not a close under the floor."""
    in_pad = round((_z5_band["pad_lo"] + _z5_band["lo"]) / 2, 2)
    rec = DR.decide_from_frame(_z5_frame(95.5, prior_close=in_pad), "PRIORPAD")
    assert rec["in_demand_band"] is True and rec["zone_broken"] is False


def test_z5_NEGATIVE_the_same_prior_close_breaks_the_band_with_the_pad_off(_z5_band, nopad):
    in_pad = round((_z5_band["pad_lo"] + _z5_band["lo"]) / 2, 2)
    rec = DR.decide_from_frame(_z5_frame(95.5, prior_close=in_pad), "PRIORPAD0")
    assert rec["in_demand_band"] is True and rec["zone_broken"] is True


def test_z5_NEGATIVE_a_prior_close_under_the_pad_still_breaks_the_band(_z5_band):
    under = round(_z5_band["pad_lo"] * 0.998, 2)
    rec = DR.decide_from_frame(_z5_frame(95.5, prior_close=under), "PRIORUNDER")
    assert rec["zone_broken"] is True


# ═════════════════════════════════════════════════════════════════════════════
# 8. Source guards
# ═════════════════════════════════════════════════════════════════════════════
def _src(rel):
    return (BACKEND / rel).read_text()


def _fn(rel, name):
    tree = ast.parse(_src(rel))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError("%s: no function %s" % (rel, name))


def _fn_code(rel, name):
    return _code_only(ast.get_source_segment(_src(rel), _fn(rel, name)))


_PKGS = ("supply_demand", "trading", "portfolio", "growth", "chart_maps")


def _non_test_py():
    for pkg in _PKGS:
        for p in (BACKEND / pkg).rglob("*.py"):
            yield p


def test_GUARD_a_one_constant_nobody_else_defines_the_pad_or_reads_the_shelf():
    for p in list(_non_test_py()) + list((BACKEND / "scripts").rglob("*.py")):
        rel = p.relative_to(BACKEND).as_posix()
        if rel in ("supply_demand/level_pad.py", "supply_demand/sd_liquidity.py"):
            continue
        code = _code_only(p.read_text())
        assert not re.search(r"^\s*DEMAND_PAD_PCT\s*[:=]", code, re.M), rel
        if rel.startswith("scripts/zone_pad_study"):
            continue                                   # the study emulates arm B by the name
        assert not re.search(r"\w\.STOP_SHELF_PCT\b|import[^\n]*\bSTOP_SHELF_PCT\b", code), rel


def test_GUARD_b_no_typed_pad_anywhere():
    typed = re.compile(r"\*\s*0\.99\b|1(\.0)?\s*-\s*0\.01\b")
    for p in _non_test_py():
        code = _code_only(p.read_text())
        assert not typed.search(code), p.relative_to(BACKEND).as_posix()


SUPPORT_READS = (
    ("supply_demand/demand_reentry.py", "trade_plan"),
    ("supply_demand/demand_reentry.py", "_pick_entry_zone"),
    ("supply_demand/demand_reentry.py", "decide_from_frame"),
    ("supply_demand/alert_gates.py", "approach_read"),
    ("supply_demand/alert_gates.py", "demand_proximity_gate"),
    ("supply_demand/alert_gates.py", "plan_txt"),
    ("supply_demand/zone_edge.py", "read_near_demand"),
    ("supply_demand/demand_alerts.py", "read"),
    ("supply_demand/zone_bounce_alerts.py", "room_for"),
    ("supply_demand/bounce_room.py", "in_demand_read"),
    ("supply_demand/bounce_room.py", "demand_read"),
    ("supply_demand/deep_demand.py", "arrival"),
    ("supply_demand/deep_demand.py", "read"),
    ("supply_demand/quick_bounce.py", "nearest_demand"),
    ("supply_demand/quick_bounce.py", "closed_under"),
    ("supply_demand/quick_bounce.py", "live_row"),
    ("trading/zone_edge_entry.py", "run"),
    ("trading/zone_edge_entry.py", "alert_gate"),
    ("trading/options_lane.py", "plan_entry"),
    ("trading/options_lane.py", "narrative"),
    ("trading/catalyst_entry.py", "zone_gate"),
    ("portfolio/supply_watch.py", "entry_band"),
    ("portfolio/supply_watch.py", "stop_for"),
)
_PAD_CALL = re.compile(r"\bLP\.(support_floor|in_band|under_floor)\(")


@pytest.mark.parametrize("rel,name", SUPPORT_READS)
def test_GUARD_c_every_support_read_goes_through_the_pad(rel, name):
    assert _PAD_CALL.search(_fn_code(rel, name)), "%s:%s reads a raw floor" % (rel, name)


def test_GUARD_c_decide_from_frame_feeds_the_padded_floor_to_both_break_reads():
    """GUARD_c passes on any LP.* call in the function, so a one-line revert of
    the broken-band guard's floor argument slipped past it (2026-09-30 review).
    Every reentry_read / band_break_read call in decide_from_frame must take
    its floor (3rd positional) from LP.support_floor(...)."""
    fn = _fn("supply_demand/demand_reentry.py", "decide_from_frame")
    seen = {}
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ("reentry_read", "band_break_read")):
            seen[node.func.id] = seen.get(node.func.id, 0) + 1
            assert len(node.args) >= 3, node.func.id
            fl = node.args[2]
            assert (isinstance(fl, ast.Call) and isinstance(fl.func, ast.Attribute)
                    and isinstance(fl.func.value, ast.Name) and fl.func.value.id == "LP"
                    and fl.func.attr == "support_floor"), \
                "%s takes a raw floor: %s" % (node.func.id, ast.dump(fl))
    assert seen.get("reentry_read") and seen.get("band_break_read"), seen


RESISTANCE_READS = (
    ("supply_demand/alert_gates.py", "overhead_bands"),
    ("supply_demand/alert_gates.py", "first_weak_lid"),
    ("supply_demand/bounce_room.py", "overhead_bands"),
    ("portfolio/supply_watch.py", "overhead_bands"),
)


@pytest.mark.parametrize("rel,name", RESISTANCE_READS)
def test_GUARD_d_resistance_reads_never_read_the_pad(rel, name):
    assert not _PAD_CALL.search(_fn_code(rel, name)), "%s:%s padded a ceiling" % (rel, name)


def test_GUARD_e_the_sweep_read_takes_its_floor_from_the_switch():
    code = _fn_code("supply_demand/alert_gates.py", "sweep_read")
    assert "LP.sweep_floor(band)" in code
    assert 'float(band["lo"])' not in code


ROOM_CALLS = (
    ("supply_demand/zone_edge.py", "check_once"),
    ("supply_demand/demand_alerts.py", "_check_once"),
    ("supply_demand/quick_bounce.py", "live_row"),
    ("supply_demand/enterable.py", "assess"),
    ("supply_demand/premarket_entry.py", "_row"),
    ("growth/alerts.py", "_scan"),
)


@pytest.mark.parametrize("rel,name", ROOM_CALLS)
def test_GUARD_f_the_room_gate_names_the_band_it_is_about(rel, name):
    code = _fn_code(rel, name)
    assert "room_gate(" in code and "entry_band=" in code, "%s:%s" % (rel, name)


def test_GUARD_g_alert_gates_stays_a_leaf():
    import inspect
    imports = [l for l in inspect.getsource(AG).splitlines() if l.startswith(("from ", "import "))]
    assert imports == ["from __future__ import annotations", "import math", "from typing import Optional"]


def test_GUARD_h_the_panel_is_built_from_the_constants_and_never_says_bounce():
    sec = RI.sections()["zone_pad"]
    assert "zone_pad" in RI.SECTION_KEYS
    blob = " ".join([sec["title"]] + sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]])
    assert "bounce" not in blob.lower()
    g = lambda x: "%g" % x                                  # noqa: E731
    assert g(LP.pad_pct()) + "%" in sec["title"]
    for n in (AG.STOP_BUFFER_PCT, DR.STOP_BUFFER_PCT, SL.SWEEP_MIN_PIERCE_PCT, ZB.WICK_PCT,
              QB.BREAK_BUFFER_PCT, SL.STOP_SHELF_PCT):
        assert g(n) + "%" in blob, n
    assert RI._pct(AG.ALERT_MIN_ROOM_PCT) in blob and RI._pct(AG.ALERT_MAX_ABOVE_DEMAND_PCT) in blob
    assert ZPM.verdict_line() in blob
    for k in range(1, 13):
        assert "HIS CALL %d " % k in blob, k
    for name in ("PAD_FLOOR_HELD", "PAD_BAND_KINDS", "PAD_KEY_KINDS", "DEMAND_PAD_PCT",
                 "STOP_SHELF_PCT", "WICK_PCT", "BREAK_BUFFER_PCT"):
        assert name in blob, name
    # the worked numbers are the engine's own
    assert g(LP.padded(133.0)) in blob and "131.01" in blob and "129.69" in blob
    # every pad-touched section carries the pad line; nothing typed in rules_info
    for key in RI.PAD_LINE_SECTIONS:
        assert any(ZPM.verdict_line() in s for s in RI.sections()[key]["stops"]), key
    code = _code_only(_src("supply_demand/rules_info.py"))
    assert not re.search(r"\b0\.99\b|\b1\.495\b|\b2\.485\b|\b131\.67\b|\b1\.15\b", code)


def test_GUARD_h_the_panel_moves_with_the_constant(monkeypatch):
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 2.0)
    sec = RI.sections()["zone_pad"]
    assert sec["title"].startswith("🧱 2% pad")
    assert "130.34" in " ".join(sec["picks"])            # 133 x 0.98


# ── critic round 2 (2026-10-01) ──────────────────────────────────────────────
def _recent(*closes):
    return {"recent": [{"close": c} for c in closes]}


def test_quick_bounce_closed_under_a_close_in_the_pad_is_not_under(monkeypatch):
    """A recent close inside [pad floor, drawn lo) counts 0 with the pad on and 1 with it off —
    a one-line revert of closed_under to the drawn lo fails here."""
    doc = _recent(132.0, 134.0, 135.5)                    # 132.00 sits in [131.67, 133.00)
    assert LP.support_floor(B) <= 132.0 < B["lo"]
    assert QB.closed_under(doc, B) == 0
    assert QB.closed_under(doc, AG._slim(B)) == 0          # the slim band live_row passes
    row = QB.live_row("PADX", {}, {"bands": [B, SUP], "prev_close": 136.0, **doc}, 134.0)
    assert row["closed_under_recent"] == 0
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 0.0)
    assert QB.closed_under(doc, B) == 1
    row0 = QB.live_row("PADX", {}, {"bands": [B, SUP], "prev_close": 136.0, **doc}, 134.0)
    assert row0["closed_under_recent"] == 1


def test_quick_bounce_closed_under_negatives():
    assert QB.closed_under(_recent(131.66, 131.0, 140.0), B) == 2     # under the PADDED floor
    assert QB.closed_under(_recent(131.67), B) == 0                    # on the padded floor
    assert QB.closed_under(_recent(132.5), SHELF) == 1                 # a supply shelf keeps its lo
    assert QB.closed_under({}, B) == 0 and QB.closed_under(None, B) == 0
    assert QB.closed_under(_recent(None, float("nan"), "x"), B) == 0
    assert QB.closed_under(_recent(100.0), {"kind": "demand", "lo": 0, "hi": 1}) == 0


def _proximity_values():
    ze = [r["value"] for r in ZEE.rules_list() if "print <= band.hi" in r["value"]]
    ce = [r["value"] for r in CE.rules_list() if "print <= band.hi" in r["value"]]
    return ze, ce


def test_lane_rules_text_is_the_padded_proximity_gate():
    ze, ce = _proximity_values()
    assert len(ze) == 1 and len(ce) == 1
    want = "padded floor band.lo x (1 - %g%%) <= print" % LP.pad_pct()
    for v in ze + ce:
        assert v.startswith(want), v
        assert "band.lo <= print" not in v                 # the pre-pad words would contradict it
        assert "bounce" not in v.lower()
    assert LP.proximity_text(AG.ALERT_MAX_ABOVE_DEMAND_PCT) in ze[0]
    # the words match the gate at the padded edge (worked example: 131.67 passes, 131.66 fails)
    assert AG.demand_proximity_gate(LP.padded(133.0), B)
    assert not AG.demand_proximity_gate(LP.padded(133.0) - 0.01, B)


def test_lane_rules_text_moves_with_the_pad(monkeypatch):
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 2.0)
    ze, ce = _proximity_values()
    assert all("(1 - 2%)" in v for v in ze + ce)
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 0.0)
    ze0, ce0 = _proximity_values()
    for v in ze0 + ce0:
        assert v.startswith("band.lo <= print <= band.hi x (1 + %g%%)" % AG.ALERT_MAX_ABOVE_DEMAND_PCT)
        assert "padded" not in v


def test_rules_panel_records_his_both_sides_decision():
    blob = " ".join(RI.sections()["zone_pad"]["stops"] + RI.sections()["zone_pad"]["picks"]
                    + RI.sections()["zone_pad"]["alerts"])
    for k in (4, 5):
        line = next(s for s in RI.sections()["zone_pad"]["alerts"] + RI.sections()["zone_pad"]["stops"]
                    + RI.sections()["zone_pad"]["picks"] if s.startswith("HIS CALL %d " % k))
        assert "DECIDED 2026-10-01" in line and "Both sides" in line, k
        assert "Confirm" not in line
    nine = next(s for s in blob.split("HIS CALL ") if s.startswith("9 "))
    assert "both ways" in nine and "drops reclaims" in nine
