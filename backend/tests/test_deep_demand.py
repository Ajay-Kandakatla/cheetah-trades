"""Deep Demand — the second-level-arrival read (supply_demand/deep_demand.py).

Why this exists (Ajay 2026-08-25): "stocks entering second level of demand
zone from the top but sales are intact ... penalized stocks that actually
have good revenue but market does not realize it." The price half must be
computed INSIDE the demand scan because these names usually fail trend_ok
and never reach the cached rows a board could read.

The sales half (Bonde gate) is board-side and tested in test_chart_maps.py.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import deep_demand as DD
from supply_demand.price_zones import NEAR_PCT
from supply_demand.demand_reentry import MIN_TOUCHES, MIN_ZONE_STRENGTH


def _band(lo, hi, touches=3, strength=60.0):
    return {"kind": "demand", "lo": lo, "hi": hi, "mid": (lo + hi) / 2,
            "touches": touches, "strength": strength}


def _rec(last, bands, top_band_read=None):
    return {"symbol": "T", "last_price": last, "demand_zones": bands,
            "top_band_read": top_band_read}


# ── geometry ────────────────────────────────────────────────────────────────
def test_inside_second_band_qualifies():
    r = DD.read(_rec(82.0, [_band(90, 95), _band(80, 85)]))
    assert r is not None
    assert r["state"] == "in"
    assert r["dist_pct"] == 0.0
    assert r["second_band"]["lo"] == 80


def test_approaching_second_band_from_above_within_near_pct_qualifies():
    # last 86.0 vs second hi 85 → ~1.16% above, inside NEAR_PCT
    r = DD.read(_rec(86.0, [_band(90, 95), _band(80, 85)]))
    assert r is not None and r["state"] == "near"
    assert 0 < r["dist_pct"] <= NEAR_PCT


def test_too_far_above_the_second_band_does_not_qualify():
    # 89.0 is below the first band's floor (90) but ~4.5% above the second's
    # top — not "entering" yet, and NEAR_PCT is the one scale for "at".
    assert DD.read(_rec(89.0, [_band(90, 95), _band(80, 85)])) is None


def test_first_band_still_holding_does_not_qualify():
    # Price inside the FIRST band — that is the ordinary zones board's case.
    assert DD.read(_rec(92.0, [_band(90, 95), _band(80, 85)])) is None


def test_broken_through_both_bands_does_not_qualify():
    # Below the second band's floor: that is a breakdown, not an entry.
    assert DD.read(_rec(78.0, [_band(90, 95), _band(80, 85)])) is None


def test_single_band_charts_never_qualify():
    assert DD.read(_rec(82.0, [_band(90, 95)])) is None
    assert DD.read(_rec(82.0, [])) is None


# ── band quality: imported thresholds, one scale ────────────────────────────
def test_flimsy_second_band_is_refused_by_the_scan_own_bar():
    weak_touch = [_band(90, 95), _band(80, 85, touches=MIN_TOUCHES - 1)]
    weak_str = [_band(90, 95), _band(80, 85, strength=MIN_ZONE_STRENGTH - 1)]
    assert DD.read(_rec(82.0, weak_touch)) is None
    assert DD.read(_rec(82.0, weak_str)) is None


def test_break_evidence_rides_along_when_present():
    """`bars_since_top_break` is the age of the FIRST close under the top band
    in the current leg — when it fell through — not the most recent one, which
    for a name still under its floor is always today (2026-09-05 fix)."""
    tb = {"bars_since_break": 0, "bars_since_first_break": 4,
          "fell_from_pct": 12.5, "broke_below": True}
    r = DD.read(_rec(82.0, [_band(90, 95), _band(80, 85)], top_band_read=tb))
    assert r["bars_since_top_break"] == 4
    assert r["fell_from_pct"] == 12.5


def test_break_evidence_is_the_real_band_break_read_not_a_hand_fed_dict():
    """Until 2026-09-05 the wiring could never carry data: decide_from_frame
    asked `reentry_read` about the top band only when price was BELOW it, and
    that read returns the empty shape whenever price is not inside. The scan
    now ships `demand_reentry.band_break_read` output; this feeds the REAL
    helper on a name that ran to 110, broke the 100-104 band 7 bars ago and
    sits inside its second band at 95. (Ajay 2026-09-05: "yes please fix the
    bugs".)"""
    from supply_demand import demand_reentry as dr
    tb = dr.band_break_read([110.0] * 32 + [95.0] * 8, zone_hi=104.0, zone_lo=100.0)
    r = DD.read(_rec(95.0, [_band(100, 104), _band(90, 95)], top_band_read=tb))
    assert r is not None and r["state"] == "in"
    assert r["bars_since_top_break"] == 7
    assert r["fell_from_pct"] == 5.8
    # And the empty shape (older cached rows) still reads as None, not a crash.
    r0 = DD.read(_rec(95.0, [_band(100, 104), _band(90, 95)], top_band_read=None))
    assert r0["bars_since_top_break"] is None and r0["fell_from_pct"] is None


def test_below_top_pct_measures_the_penalty():
    r = DD.read(_rec(82.0, [_band(90, 95), _band(80, 85)]))
    # (90 - 82) / 90 = 8.89%
    assert r["below_top_pct"] == pytest.approx(8.89, abs=0.01)


# ── ordering ────────────────────────────────────────────────────────────────
def test_sort_key_puts_in_band_before_near_and_closer_before_farther():
    in_row = {"deep_demand": {"state": "in", "dist_pct": 0.0,
                              "second_band": {"strength": 50}}}
    near_close = {"deep_demand": {"state": "near", "dist_pct": 0.5,
                                  "second_band": {"strength": 50}}}
    near_far = {"deep_demand": {"state": "near", "dist_pct": 2.5,
                                "second_band": {"strength": 90}}}
    rows = [near_far, near_close, in_row]
    rows.sort(key=DD.sort_key)
    assert [r["deep_demand"]["state"] for r in rows] == ["in", "near", "near"]
    assert rows[1]["deep_demand"]["dist_pct"] == 0.5


# ── malformed input never crashes a scan ────────────────────────────────────
def test_garbage_records_return_none_not_raise():
    assert DD.read({}) is None
    assert DD.read({"last_price": None, "demand_zones": [_band(1, 2), _band(0, 1)]}) is None
    assert DD.read(_rec(82.0, [{"lo": None, "hi": None}, _band(80, 85)])) is None


# ── inflow_read — classification only, thresholds imported ──────────────────
# Ajay 2026-08-25: "they are very bearish from institutions and retailer we
# are looking for bullish momentum stocks and inflow signals for these."
def _vol(cmf=None, acc=0, dist=0, pp=False, net=None):
    return {"cmf_20": cmf, "accumulation_days_25": acc,
            "distribution_days_25": dist, "pocket_pivot": pp,
            "net_dollar_vol_50": net}


def test_inflow_at_the_modules_own_cmf_zone():
    from sepa.volume import CMF_INFLOW_THRESHOLD, CMF_OUTFLOW_THRESHOLD
    assert DD.inflow_read(_vol(cmf=CMF_INFLOW_THRESHOLD))["state"] == "inflow"
    assert DD.inflow_read(_vol(cmf=CMF_OUTFLOW_THRESHOLD))["state"] == "distribution"


def test_weak_positive_cmf_needs_the_day_count_on_its_side():
    # +0.05 is inside the neutral CMF zone — accumulation days break the tie.
    assert DD.inflow_read(_vol(cmf=0.05, acc=9, dist=4))["state"] == "inflow"
    assert DD.inflow_read(_vol(cmf=0.05, acc=3, dist=8))["state"] == "neutral"
    assert DD.inflow_read(_vol(cmf=-0.05, acc=3, dist=8))["state"] == "distribution"
    assert DD.inflow_read(_vol(cmf=-0.05, acc=8, dist=3))["state"] == "neutral"


def test_missing_cmf_is_neutral_never_a_signal():
    r = DD.inflow_read(_vol(cmf=None, acc=10, dist=0))
    assert r["state"] == "neutral" and r["cmf_20"] is None


def test_inflow_read_of_nothing_is_none():
    assert DD.inflow_read(None) is None
    assert DD.inflow_read({}) is None


# ── ordering, 2026-09-03: closest first, CMF inside a distance bucket ───────
# Ajay 2026-09-03: "make sure in our other demand and deep demand keep the
# closest one to demand zones on the top. Of course CMF inflow too considered."
# SUPERSEDES the 2026-08-26 "highest CMF on the top" order — under it NOG,
# 2.53% ABOVE its second band, ranked over 52 in-band names (live, that day).
def _drow(sym, px, cmf=None, state=None, strength=50):
    """A deep row the way the scan ships it: last_price + second band 80-85;
    the read's state follows from the price. `state=None` = no inflow read."""
    inflow = None if state is None else {"state": state, "cmf_20": cmf}
    return {"symbol": sym, "last_price": px,
            "deep_demand": {"state": "in" if 80 <= px <= 85 else "near",
                            "dist_pct": 0.0 if px <= 85 else (px - 85) / px * 100,
                            "second_band": {"lo": 80.0, "hi": 85.0, "strength": strength},
                            "inflow": inflow}}


def _order(rows):
    return [r["symbol"] for r in sorted(rows, key=DD.sort_key)]


def test_in_band_beats_a_hotter_cmf_that_is_still_outside_the_band():
    """The worked example (live 2026-09-03): COTY inside CMF +0.248, APPF
    0.81% out CMF +0.282, NOG 2.53% out CMF +0.364 → COTY, APPF, NOG. The
    2026-08-26 key gave the reverse."""
    coty = _drow("COTY", 82.0, 0.248, "inflow")
    appf = _drow("APPF", 85.0 / (1 - 0.0081), 0.282, "inflow")     # 0.81% above
    nog = _drow("NOG", 85.0 / (1 - 0.0253), 0.364, "inflow")       # 2.53% above
    assert _order([nog, appf, coty]) == ["COTY", "APPF", "NOG"]


def test_cmf_ranks_only_inside_the_same_distance_bucket():
    """Two near rows 0.10% and 0.40% out share bucket 0 → the stronger CMF
    leads. NEGATIVE: at 0.40% vs 0.60% (buckets 0 and 1) distance wins again
    even though the farther name has the hotter CMF."""
    a = _drow("A", 85.0 / (1 - 0.0010), 0.05, "inflow")
    b = _drow("B", 85.0 / (1 - 0.0040), 0.30, "inflow")
    assert _order([a, b]) == ["B", "A"]
    c = _drow("C", 85.0 / (1 - 0.0060), 0.40, "inflow")
    assert _order([c, b]) == ["B", "C"]


def test_flow_state_then_cmf_orders_a_bucket_and_missing_sorts_last():
    """Inside one bucket: inflow > neutral > distribution > no read; within a
    state the stronger CMF (milder selling) first. NEGATIVE: a heavily-sold
    name never jumps a milder one on |CMF|, and a row with NO inflow read
    sorts after every real reading — never first."""
    rows = [_drow("SOLDHARD", 82.0, -0.40, "distribution"),
            _drow("NOREAD", 82.0),
            _drow("NEUT", 82.0, -0.02, "neutral"),
            _drow("SOLDMILD", 82.0, -0.11, "distribution"),
            _drow("IN", 82.0, 0.12, "inflow"),
            _drow("INNOCMF", 82.0, None, "inflow")]
    assert _order(rows) == ["IN", "INNOCMF", "NEUT", "SOLDMILD", "SOLDHARD", "NOREAD"]


def test_a_row_carrying_only_the_read_still_ranks_by_the_same_geometry():
    """Unit fixtures / older rows may lack last_price — the read's own
    state/dist_pct (same formula) stands in, so in-before-near still holds
    and nothing crashes."""
    in_row = {"deep_demand": {"state": "in", "dist_pct": 0.0,
                              "second_band": {"strength": 50}}}
    near = {"deep_demand": {"state": "near", "dist_pct": 1.4,
                            "second_band": {"strength": 90}}}
    junk = {"deep_demand": None}
    rows = [junk, near, in_row]
    rows.sort(key=DD.sort_key)
    assert rows[0] is in_row and rows[1] is near and rows[2] is junk


def test_sort_key_takes_a_live_price_override():
    """Chart Maps re-ranks on the live print: a name the scan saw 2% out that
    has since dropped INTO the band now leads the one that was inside and
    has drifted 1% above it."""
    was_near = _drow("WASNEAR", 87.0, 0.10, "inflow")
    was_in = _drow("WASIN", 83.0, 0.30, "inflow")
    assert _order([was_near, was_in]) == ["WASIN", "WASNEAR"]
    live = {"WASNEAR": 84.0, "WASIN": 85.9}
    rows = sorted([was_in, was_near],
                  key=lambda r: DD.sort_key(r, px=live[r["symbol"]]))
    assert [r["symbol"] for r in rows] == ["WASNEAR", "WASIN"]


# ── per-state cap (2026-09-03) ───────────────────────────────────────────────
def test_cap_trims_in_and_near_separately_preserving_order():
    """One MAX_ROWS trim after a closest-first sort would fill with in-band
    rows and empty the Chart Maps approaching toggle. Per-state caps keep
    both lists; order inside each is untouched."""
    ins = [_drow(f"I{i}", 82.0) for i in range(DD.MAX_IN + 5)]
    nears = [_drow(f"N{i}", 86.0) for i in range(DD.MAX_NEAR + 3)]
    kept = DD.cap(ins + nears)
    assert sum(1 for r in kept if r["deep_demand"]["state"] == "in") == DD.MAX_IN
    assert sum(1 for r in kept if r["deep_demand"]["state"] == "near") == DD.MAX_NEAR
    assert [r["symbol"] for r in kept][:3] == ["I0", "I1", "I2"]
    assert DD.MAX_ROWS == DD.MAX_IN + DD.MAX_NEAR
    # NEGATIVE: a short list is never padded or reordered
    few = [_drow("N1", 86.0), _drow("I1", 82.0)]
    assert DD.cap(few) == few


# ── room floor 2026-09-05 — which bands a DEEP row measures its room against ──
# Ajay 2026-09-05: "I need the same logic in Demand and deep demand zone. So
# that there are stocks that have more room atleast >5%". A deep row's entry
# band is its SECOND band; the broken first band overhead is resistance.
from supply_demand import room_floor as RF   # noqa: E402


def _deep_row():
    return {"symbol": "D", "last_price": 82.0,
            "entry_zone": {"lo": 80.0, "hi": 85.0},
            "nearest_resistance": {"kind": "demand", "lo": 90.0, "hi": 95.0},
            "supply_zones": [{"kind": "supply", "lo": 100.0, "hi": 102.0}],
            "demand_zones": [{"kind": "demand", "lo": 90.0, "hi": 95.0},
                             {"kind": "demand", "lo": 80.0, "hi": 85.0}],
            "deep_demand": {"state": "in", "top_band": {"lo": 90.0, "hi": 95.0},
                            "second_band": {"lo": 80.0, "hi": 85.0, "touches": 3}}}


def test_a_deep_row_entry_band_is_its_second_band():
    eb = RF.row_entry_band(_deep_row())
    assert (eb["lo"], eb["hi"]) == (80.0, 85.0)
    plain = {"entry_zone": {"lo": 14.0, "hi": 15.0}}
    assert RF.row_entry_band(plain) == {"lo": 14.0, "hi": 15.0}


def test_a_deep_row_measures_room_to_its_broken_first_band_not_past_it():
    r = _deep_row()
    bands = RF.row_bands(r)
    assert {"kind": "demand", "lo": 90.0, "hi": 95.0} in [
        {"kind": b["kind"], "lo": b["lo"], "hi": b["hi"]} for b in bands]
    room = RF.room_block(82.0, bands, entry_band=RF.row_entry_band(r))
    assert room["target_lo"] == 90.0 and room["target_kind"] == "demand"
    assert room["room_pct"] == pytest.approx(9.8, abs=0.01)


def test_a_deep_row_with_no_band_lists_still_counts_the_top_band_it_carries():
    r = _deep_row()
    r["demand_zones"] = []
    r["nearest_resistance"] = None
    room = RF.room_block(82.0, RF.row_bands(r), entry_band=RF.row_entry_band(r))
    assert room["target_lo"] == 90.0, "deep_demand.top_band is the ceiling this screen is about"


def test_row_bands_dedupes_the_same_band_arriving_from_two_lists():
    bands = RF.row_bands(_deep_row())
    keys = [(b["kind"], b["lo"], b["hi"]) for b in bands]
    assert len(keys) == len(set(keys))
