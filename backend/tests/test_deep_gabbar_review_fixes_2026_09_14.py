"""Deep Demand + Gabbar Levels — the 2026-09-14 review fixes.

Verified on the live boards earlier the same day; drawing, wording and
price-basis fixes only. No gate, threshold or hand-drawn level moved (the
two rule findings are Ajay's call and were skipped). Each block carries its
NEGATIVE: the unchanged path must read byte for byte as before.

  D1  the room stat names the 1-touch lid it skipped (room_floor)
  D2  the deep tile draws the lids price meets first overhead
  D3  the deep tile's why-line + chip price off the LIVE print the rank used
  D5  a reclaim from below is labelled a reclaim (wording, no gate)
  D8  the 2y/3y/5y windows keep the after-hours flag on the last bar
  G1  BKNG levels ÷25 for the verified 2026-04-06 split (data, not memory)
  G2  'above' / 'below' judged against the NEAREST band, never 'past'
  G3  no device subscribed to pivot_alert -> no pass, no ledger row
  G4  'x% below' / 'x% above' in the tile chip and the push body
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chart_maps import board as B  # noqa: E402
from supply_demand import room_floor as RF  # noqa: E402
from supply_demand import deep_demand as DD  # noqa: E402
from catalysts import gabbar_levels as GL  # noqa: E402
from catalysts import gabbar_watch as GW  # noqa: E402

# The board fixtures + row builders the chart-maps suite already owns —
# imported, not re-typed, so a fixture change there reaches here.
from test_chart_maps import (  # noqa: E402,F401
    _deep_row, _frame, _sales, _room_stat,
    prices, reentry_stub, sales_stub, gabbar_stub,
)


def _lid(lo, hi, touches, kind="supply"):
    return {"kind": kind, "lo": lo, "hi": hi, "touches": touches, "strength": 50.0}


# ---------------------------------------------------------------------------
# D1 — the room stat names the 1-touch lid it skipped
# ---------------------------------------------------------------------------
def test_d1_clear_room_names_the_one_touch_lid_the_rule_skipped():
    """'open sky' printed under a lid the tile drew in red (live board,
    2026-09-14). The room is still CLEAR by the proven rule; the stat now
    says which unproven lid sits there."""
    room = RF.room_block(100.0, [_lid(110.0, 112.0, touches=1)])
    assert room["state"] == "CLEAR" and room["target_lo"] is None
    assert room["weak"]["lo"] == 110.0 and room["weak"]["touches"] == 1
    assert RF.room_stat(room) == "open sky · 1-touch lid 110.00 skipped"


def test_d1_a_proven_target_keeps_the_pinned_wording_and_names_the_weak_lid_under_it():
    bands = [_lid(110.0, 112.0, touches=1), _lid(120.0, 122.0, touches=3)]
    room = RF.room_block(100.0, bands)
    assert room["state"] == "ROOM" and room["target_lo"] == 120.0
    assert RF.room_stat(room) == "+20.0% -> 120.00 · weak 110.00 first"   # 2026-09-08 wording


def test_d1_negative_the_proven_set_caller_is_unchanged():
    """A caller that still hands in row_bands(row) (the proven set) sees
    exactly the old block: no weak lid, plain 'open sky'."""
    row = {"symbol": "X", "last_price": 100.0,
           "supply_zones": [_lid(110.0, 112.0, touches=1)]}
    proven = RF.row_bands(row)
    assert proven == [], "the 1-touch lid is not a target (KLAC 2026-09-06)"
    room = RF.room_block(100.0, proven)
    assert room["state"] == "CLEAR" and room["weak"] is None
    assert RF.room_stat(room) == "open sky"
    raw = RF.row_bands(row, proven=False)
    assert [(b["lo"], b["touches"]) for b in raw] == [(110.0, 1)]


def test_d1_negative_a_proven_lid_is_the_target_never_weak_and_a_lid_under_the_print_is_never_named():
    room = RF.room_block(100.0, [_lid(110.0, 112.0, touches=3)])
    assert room["state"] == "ROOM" and room["weak"] is None
    assert RF.room_stat(room) == "+10.0% -> 110.00"
    under = RF.room_block(100.0, [_lid(90.0, 92.0, touches=1)])
    assert under["state"] == "CLEAR" and under["weak"] is None
    assert RF.room_stat(under) == "open sky"
    assert RF.room_block(0.0, [_lid(110.0, 112.0, touches=1)]) is None


def test_d1_the_target_and_the_floor_do_not_move_when_the_raw_set_is_handed_in():
    """The gate must not change: the same rows pass and fail the 5% floor
    on the raw set as on the proven set."""
    bands = [_lid(103.0, 104.0, touches=1), _lid(110.0, 112.0, touches=3)]
    on_proven = RF.room_block(100.0, RF.plan_bands(bands))
    on_raw = RF.room_block(100.0, bands)
    for k in ("state", "target_lo", "target_hi", "room_pct", "room_pct_raw"):
        assert on_proven[k] == on_raw[k]
    assert RF.meets_room_floor(on_raw, 5.0) is RF.meets_room_floor(on_proven, 5.0) is True
    assert on_raw["weak"]["lo"] == 103.0 and on_proven["weak"] is None


def test_d1_deep_tile_room_stat_names_the_one_touch_first_band(prices, reentry_stub, sales_stub):
    """The board case: a deep row whose broken FIRST band is a 1-touch swing.
    The room rule skips it (CLEAR, the floor passes) and the stat says so."""
    row = _deep_row("ONE")
    row["deep_demand"]["top_band"] = {"lo": 90.0, "hi": 95.0, "touches": 1}
    reentry_stub["deep_rows"] = [row]
    prices["ONE"] = _frame(200)
    sales_stub["ONE"] = _sales("steady", 9.0)
    out = B.board("deep_demand", limit=5, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["ONE"] and out["hidden_low_room"] == 0
    assert _room_stat(out["tiles"][0]) == "open sky · 1-touch lid 90.00 skipped"
    labels = [b["label"] for b in out["tiles"][0]["bands"]]
    assert "1st demand · broken (1-touch swing)" in labels


# ---------------------------------------------------------------------------
# D2 — the deep tile draws the lids overhead
# ---------------------------------------------------------------------------
def test_d2_deep_tile_draws_the_two_nearest_lids_above_the_live_print(
        prices, reentry_stub, sales_stub, monkeypatch):
    row = _deep_row("LIDS")
    row["supply_zones"] = [_lid(120.0, 125.0, 3), _lid(100.0, 104.0, 2),
                           _lid(140.0, 145.0, 4), _lid(70.0, 72.0, 2)]   # 70-72 is under the print
    reentry_stub["deep_rows"] = [row]
    prices["LIDS"] = _frame(200)
    sales_stub["LIDS"] = _sales("steady", 9.0)
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {"LIDS": 82.0})
    out = B.board("deep_demand", limit=5, min_tier="any", min_room=0)
    t = out["tiles"][0]
    supply = [(b["lo"], b["hi"]) for b in t["bands"] if b["kind"] == "supply" and b["label"] == "supply"]
    assert supply == [(100.0, 104.0), (120.0, 125.0)], "nearest first, never the broken one, never the third"
    kinds = [b["kind"] for b in t["bands"]]
    assert kinds[:2] == ["supply", "demand"], "the deep bands still lead"


def test_d2_negative_no_supply_zones_draws_only_the_two_deep_bands_and_a_lid_equal_to_the_top_band_is_not_drawn_twice(
        prices, reentry_stub, sales_stub, monkeypatch):
    plain = _deep_row("PLAIN")
    dup = _deep_row("DUP")
    dup["supply_zones"] = [_lid(90.0, 95.0, 3)]          # == the broken first band
    reentry_stub["deep_rows"] = [plain, dup]
    for s in ("PLAIN", "DUP"):
        prices[s] = _frame(200)
        sales_stub[s] = _sales("steady", 9.0)
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    out = B.board("deep_demand", limit=5, min_tier="any", min_room=0)
    by = {t["symbol"]: t for t in out["tiles"]}
    # The arrival band's label says where the PRINT is since 2026-09-17; the
    # DRAWING this test is about — two bands, the duplicate lid dropped — is
    # unchanged.
    assert [b["label"] for b in by["PLAIN"]["bands"]] == [
        "1st demand · broken", "2nd demand level · price inside"]
    assert [b["label"] for b in by["DUP"]["bands"]] == [
        "1st demand · broken", "2nd demand level · price inside"]


# ---------------------------------------------------------------------------
# D3 — the why-line and the chip price off the live print the rank used
# ---------------------------------------------------------------------------
def test_d3_deep_tile_distance_and_chip_follow_the_live_print(
        prices, reentry_stub, sales_stub, monkeypatch):
    """The scan said NEAR at 1.2%; the tape has moved. Rank, room and gate
    read the live print — so must the words."""
    reentry_stub["deep_rows"] = [_deep_row("MOVED", state="near", dist=1.2)]
    prices["MOVED"] = _frame(200)
    sales_stub["MOVED"] = _sales("steady", 9.0)
    # second band 80-85: 86.7 is 1.96% above its top
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {"MOVED": 86.7})
    t = B.board("deep_demand", limit=5, min_tier="any", min_room=0, phase="approaching")["tiles"][0]
    # 2026-09-17: the number keeps its basis, and a print ABOVE the band is
    # no longer described as arriving at it.
    assert "now 1.96% above its 2nd demand level on the live print" in t["why"]
    assert t["badges"][0]["text"] == "🩹 Above its 2nd demand level"
    # ...and once the live print is INSIDE the band, the chip says so even
    # though the scan's state is still 'near'.
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {"MOVED": 84.0})
    t = B.board("deep_demand", limit=5, min_tier="any", min_room=0, phase="approaching")["tiles"][0]
    assert ("now in its 2nd demand level on the live print" in t["why"]
            and "above its 2nd demand level" not in t["why"])
    assert t["badges"][0]["text"] == "🩹 In its 2nd demand level"


def test_d3_negative_no_tape_falls_back_to_the_scan_distance(
        prices, reentry_stub, sales_stub, monkeypatch):
    stale = _deep_row("STALE", state="near", dist=1.2)
    stale["last_price"] = 86.03                    # the scan's own print: 1.2% over 85
    reentry_stub["deep_rows"] = [stale, _deep_row("INSIDE", state="in")]
    for s in ("STALE", "INSIDE"):
        prices[s] = _frame(200)
        sales_stub[s] = _sales("steady", 9.0)
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    near = B.board("deep_demand", limit=5, min_tier="any", min_room=0, phase="approaching")["tiles"][0]
    # No tape: the scan's own distance, and the sentence SAYS it is the close.
    assert "now 1.2% above its 2nd demand level on the close" in near["why"]
    assert "on the live print" not in near["why"]
    assert near["badges"][0]["text"] == "🩹 Above its 2nd demand level"
    inside = B.board("deep_demand", limit=5, min_tier="any", min_room=0)["tiles"][0]
    assert "now in its 2nd demand level on the close" in inside["why"]
    assert inside["badges"][0]["text"] == "🩹 In its 2nd demand level"


# ---------------------------------------------------------------------------
# D5 — a reclaim from below is labelled a reclaim (wording, no gate)
# ---------------------------------------------------------------------------
def _band(lo, hi, touches=3, strength=60.0):
    return {"kind": "demand", "lo": lo, "hi": hi, "touches": touches, "strength": strength}


def test_d5_read_flags_a_prior_close_under_the_second_band_and_still_qualifies():
    bands = [_band(90, 95), _band(80, 85)]
    r = DD.read({"symbol": "T", "last_price": 82.0, "demand_zones": bands, "prev_close": 78.0})
    assert r is not None and r["state"] == "in" and r["reclaiming"] is True
    # NEGATIVE: from above, unknown, garbage, exactly at the floor -> not a reclaim
    assert DD.read({"symbol": "T", "last_price": 82.0, "demand_zones": bands, "prev_close": 88.0})["reclaiming"] is False
    assert DD.read({"symbol": "T", "last_price": 82.0, "demand_zones": bands})["reclaiming"] is False
    assert DD.read({"symbol": "T", "last_price": 82.0, "demand_zones": bands, "prev_close": "x"})["reclaiming"] is False
    assert DD.read({"symbol": "T", "last_price": 82.0, "demand_zones": bands, "prev_close": 80.0})["reclaiming"] is False


def test_d5_read_does_not_gate_on_prev_close_his_call():
    """Requiring prev_close >= s_lo would change who qualifies. Not made."""
    import inspect
    src = inspect.getsource(DD.read)
    assert "prev_close" in src and "reclaiming" in src
    assert "if pc is not None and pc < s_lo:\n        return None" not in src


def test_d5_deep_tile_labels_a_reclaim_from_the_scan_flag_and_from_the_live_read(
        prices, reentry_stub, sales_stub, monkeypatch):
    flagged = _deep_row("FLAG")
    flagged["deep_demand"]["reclaiming"] = True
    live_reclaim = _deep_row("LIVE")                    # no scan flag; the tape says it
    reentry_stub["deep_rows"] = [flagged, live_reclaim]
    for s in ("FLAG", "LIVE"):
        prices[s] = _frame(200)
        sales_stub[s] = _sales("steady", 9.0)
    monkeypatch.setattr(B, "_live_rows", lambda syms: {
        "LIVE": {"price": 82.0, "last_trade_price": 82.0, "prev_day_close": 78.0, "low": 79.0}})
    out = B.board("deep_demand", limit=5, min_tier="any", min_room=0)
    by = {t["symbol"]: t for t in out["tiles"]}
    for sym in ("FLAG", "LIVE"):
        t = by[sym]
        # 2026-09-17: the reclaim is still labelled — while the print is IN
        # the band — and it is said as the prior-close fact it is.
        assert ("2nd demand level · back in from below"
                in [b["label"] for b in t["bands"]])
        assert any(b["text"] == "🩹 Back in its 2nd demand level from below"
                   for b in t["badges"])
        assert "(yesterday closed under it)" in t["why"]
    assert by["LIVE"]["badges"][0]["text"].startswith("↑ Reclaiming"), "the approach chip still leads"


def test_d5_negative_an_arrival_from_above_keeps_the_entering_label(
        prices, reentry_stub, sales_stub, monkeypatch):
    row = _deep_row("TOP")
    row["deep_demand"]["reclaiming"] = False
    reentry_stub["deep_rows"] = [row]
    prices["TOP"] = _frame(200)
    sales_stub["TOP"] = _sales("steady", 9.0)
    monkeypatch.setattr(B, "_live_rows", lambda syms: {
        "TOP": {"price": 82.0, "last_trade_price": 82.0, "prev_day_close": 95.0, "low": 82.0}})
    t = B.board("deep_demand", limit=5, min_tier="any", min_room=0)["tiles"][0]
    labels = [b["label"] for b in t["bands"]]
    assert ("2nd demand level · price inside" in labels
            and "below" not in " ".join(labels))
    assert not any("Reclaiming" in b["text"] for b in t["badges"])
    assert "reclaimed" not in t["why"]


# ---------------------------------------------------------------------------
# D8 — the 2y / 3y / 5y windows keep the after-hours flag on the last bar
# ---------------------------------------------------------------------------
@pytest.fixture
def overlay_prices(monkeypatch):
    """A sepa.prices stub WITH with_today_bar: `mode` decides what the
    overlay says. Records the frames it was handed."""
    store: dict = {}
    calls: list = []
    state = {"mode": "frame"}

    class _P:
        PERIOD_DAYS = {"2y": 504}

        @staticmethod
        def load_prices(symbol, *a, **kw):
            return store.get(symbol.upper())

        @staticmethod
        def with_today_bar(df, symbol, snap=None):
            calls.append(len(df))
            last = df.index[-1].strftime("%Y-%m-%d")
            info = {"appended": False, "adjusted": False, "date": None, "source": "frame",
                    "partial": False, "session": None}
            if state["mode"] == "afterhours":
                out = df.copy()
                out.iloc[-1, out.columns.get_loc("close")] = float(out["close"].iloc[-1]) + 1.0
                info.update(adjusted=True, date=last, source="afterhours", session="afterhours")
                return out, info
            if state["mode"] == "premarket":
                day = "2030-01-02"
                if last >= day:
                    return df, info
                row = pd.DataFrame({"open": [10.0], "high": [10.5], "low": [10.0],
                                    "close": [10.5], "volume": [0.0]},
                                   index=[pd.Timestamp(f"{day} 04:00:00")])
                info.update(appended=True, date=day, source="premarket", session="premarket",
                            partial=True)
                return pd.concat([df, row]), info
            if state["mode"] == "boom":
                raise RuntimeError("snapshot down")
            return df, info

    mod = _P()
    monkeypatch.setitem(sys.modules, "sepa.prices", mod)
    import sepa
    monkeypatch.setattr(sepa, "prices", mod, raising=False)
    return store, state, calls


def test_d8_deep_window_tags_the_after_hours_print_like_the_short_window(overlay_prices):
    store, state, calls = overlay_prices
    store["AAA"] = _frame(600)
    state["mode"] = "afterhours"
    deep = B.bars_for("AAA", days=504)                  # > DEEP_BARS_FROM: the support frame
    assert len(deep) == 504 and deep[-1]["s"] == "ah"
    short = B.bars_for("AAA", days=60)
    assert short[-1]["s"] == "ah"
    assert deep[-1]["c"] == short[-1]["c"], "one price on both windows"
    assert 600 in calls, "the overlay was re-read off the closed frame"


def test_d8_deep_window_tags_a_pre_market_bar_and_keeps_the_zero_volume_fallback(overlay_prices):
    store, state, calls = overlay_prices
    store["AAA"] = _frame(600)
    state["mode"] = "premarket"
    deep = B.bars_for("AAA", days=504)
    assert deep[-1]["t"] == "2030-01-02" and deep[-1]["s"] == "pre"
    assert deep[-1]["v"] == 0.0


def test_d8_negative_nothing_live_leaves_the_last_bar_unflagged_and_a_failed_overlay_never_breaks_the_chart(overlay_prices):
    store, state, calls = overlay_prices
    store["AAA"] = _frame(600)
    state["mode"] = "frame"
    deep = B.bars_for("AAA", days=504)
    assert len(deep) == 504 and "s" not in deep[-1]
    assert "s" not in B.bars_for("AAA", days=60)[-1]
    state["mode"] = "boom"
    deep = B.bars_for("AAA", days=504)
    assert len(deep) == 504 and "s" not in deep[-1]
    assert B._overlay_info(sys.modules["sepa.prices"], None, "AAA") is None


# ---------------------------------------------------------------------------
# G1 — BKNG levels ÷25 for the verified split
# ---------------------------------------------------------------------------
def test_g1_bkng_bands_are_divided_by_the_verified_ratio_and_the_payload_says_so():
    """Evidence (api container, 2026-09-14): Massive splits 2026-04-06 1->25;
    unadjusted/adjusted close 2026-04-01 = 4184.56/167.3824 = 25.0; the
    table's aggressive 3700-3900 / 25 = 148-156 brackets the adjusted
    154.13 close on the 2026-05-17 snapshot date."""
    p = GL.get_bands("BKNG")
    assert p["split_adjusted"] == 25.0 and p["split_date"] == "2026-04-06"
    assert [(b["lo"], b["hi"], b["label"]) for b in p["bands"]] == [
        (148.0, 156.0, "aggressive"), (128.0, 136.0, "conservative 1"),
        (108.0, 116.0, "conservative 2")]
    # the author's row is untouched — the table is his, the scaling is ours
    assert GL.BANDS["BKNG"][0] == (3700.0, 3900.0)
    # 148 <= 154.13 <= 156: the snapshot-day close sits in the aggressive band
    assert p["bands"][0]["lo"] <= 154.13 <= p["bands"][0]["hi"]


def test_g1_negative_unsplit_names_are_byte_identical_and_carry_no_split_keys():
    p = GL.get_bands("AAPL")
    assert "split_adjusted" not in p and "split_date" not in p
    assert [(b["lo"], b["hi"]) for b in p["bands"]] == [(240.0, 250.0), (220.0, 230.0), (190.0, 200.0)]
    assert GL.get_bands("NOPE") is None


def test_g1_every_split_entry_is_a_dated_ratio_above_one():
    """A split is the ONE mechanical change a level may take, and it needs
    a date and a ratio > 1 verified from data — never a bare number."""
    for sym, spec in GL.SPLITS.items():
        assert sym in GL.BANDS, f"{sym} has a split but no levels"
        assert float(spec["ratio"]) > 1.0 and len(spec["date"]) == 10, spec


def test_g1_gabbar_tile_reads_bkng_off_the_adjusted_bands(prices, monkeypatch):
    """Before: '1442% past the nearest Gabbar band' on a $175 stock."""
    class _One:
        BAND_ATTRIBUTION = GL.BAND_ATTRIBUTION
        TRACKED_NO_LEVELS = GL.TRACKED_NO_LEVELS
        SPLITS = GL.SPLITS

        @staticmethod
        def list_covered_symbols():
            return ["BKNG"]

        @staticmethod
        def get_bands(sym):
            return GL.get_bands(sym) if sym == "BKNG" else None

    import catalysts
    monkeypatch.setitem(sys.modules, "catalysts.gabbar_levels", _One())
    monkeypatch.setattr(catalysts, "gabbar_levels", _One(), raising=False)
    monkeypatch.setitem(sys.modules, "sepa.research", type("R", (), {
        "sales_snapshot": staticmethod(lambda syms, max_age_sec=None: {})})())
    prices["BKNG"] = _frame(200, start=175.35 - 199 * 0.05)      # last close 175.35
    out = B.board("gabbar", limit=5, min_tier="any")
    t = out["tiles"][0]
    assert t["why"] == "11% above the nearest Gabbar band (aggressive)"
    assert any(b["text"] == "✂️ Levels ÷25 for the 2026-04-06 split" for b in t["badges"])
    assert [(b["lo"], b["hi"]) for b in t["bands"]][0] == (148.0, 156.0)
    assert "1442" not in t["why"] and "past" not in t["why"]


# ---------------------------------------------------------------------------
# G2 / G4 — side against the NEAREST band, in the chip, the why and the push
# ---------------------------------------------------------------------------
@pytest.fixture
def ladder_stub(monkeypatch):
    """One name, a three-band ladder, no sales data — the side test."""
    table = {"MID": [{"lo": 95.0, "hi": 100.0, "label": "aggressive"},
                     {"lo": 80.0, "hi": 85.0, "label": "conservative 1"},
                     {"lo": 60.0, "hi": 65.0, "label": "conservative 2"}]}

    class _GL:
        BAND_ATTRIBUTION = GL.BAND_ATTRIBUTION
        TRACKED_NO_LEVELS = GL.TRACKED_NO_LEVELS

        @staticmethod
        def list_covered_symbols():
            return sorted(table)

        @staticmethod
        def get_bands(sym):
            return {"symbol": sym, "bands": table[sym], "attribution": _GL.BAND_ATTRIBUTION} \
                if sym in table else None

    import catalysts
    monkeypatch.setitem(sys.modules, "catalysts.gabbar_levels", _GL())
    monkeypatch.setattr(catalysts, "gabbar_levels", _GL(), raising=False)
    monkeypatch.setitem(sys.modules, "sepa.research", type("R", (), {
        "sales_snapshot": staticmethod(lambda syms, max_age_sec=None: {})})())
    return table


def _tile_at(prices, last):
    prices["MID"] = _frame(200, start=last - 199 * 0.05)
    return B.board("gabbar", limit=5, min_tier="any")["tiles"][0]


def test_g2_between_two_bands_reads_below_the_nearest_never_past(prices, ladder_stub):
    """91 sits between conservative 1 (80-85) and aggressive (95-100): the
    nearest is aggressive, 4.4% BELOW it. The old read compared the print
    with the HIGHEST band and called every such name 'past' (ISRG/CRWD/CLX)."""
    t = _tile_at(prices, 91.0)
    assert t["why"] == "4% below the nearest Gabbar band (aggressive)"
    assert not any(b["text"].startswith(("🎯", "🛡️")) for b in t["badges"])


def test_g2_above_everything_reads_above_and_under_everything_reads_below(prices, ladder_stub):
    assert _tile_at(prices, 110.0)["why"] == "9% above the nearest Gabbar band (aggressive)"
    assert _tile_at(prices, 50.0)["why"] == "20% below the nearest Gabbar band (conservative 2)"


def test_g4_near_chip_and_why_carry_the_side(prices, ladder_stub):
    """NFLX after six closes under its band wore a sideless '1.2% from'."""
    below = _tile_at(prices, 94.0)                         # 1.06% under the aggressive floor
    assert below["why"] == "1.1% below Gabbar's aggressive band"
    assert below["badges"][0]["text"] == "🎯 1.1% below aggressive"
    above = _tile_at(prices, 101.0)                        # 0.99% over its top
    assert above["why"] == "1.0% above Gabbar's aggressive band"
    assert above["badges"][0]["text"] == "🎯 1.0% above aggressive"
    inside = _tile_at(prices, 97.0)
    assert inside["why"] == "inside Gabbar's aggressive band right now"
    assert inside["badges"][0]["text"] == "🎯 In Gabbar band (aggressive)"
    assert "from" not in below["why"] and "from" not in above["badges"][0]["text"]


def test_g4_push_body_says_below_or_above_never_from():
    hit = {"idx": 0, "label": "aggressive", "lo": 68.0, "hi": 72.0,
           "state": "approaching", "dist_pct": 0.9}
    assert GW.where_text(hit, 67.4, "at") == "0.9% below"
    assert GW.where_text(hit, 72.6, "at") == "0.9% above"
    assert GW.where_text({**hit, "state": "in", "dist_pct": 0.0}, 70.0, "at") == "inside"
    assert GW.where_text({**hit, "state": "near", "dist_pct": 2.4}, 73.7, "near") == "2.4% above"
    assert GW.where_text({**hit, "lo": None}, 67.4, "at") == "0.9% above", "no floor = the old side"
    import inspect
    assert "% from" not in inspect.getsource(GW.check_once)


# ---------------------------------------------------------------------------
# G3 — no device subscribed to pivot_alert -> no pass, no ledger row
# ---------------------------------------------------------------------------
def test_g3_no_subscribed_device_skips_the_pass_before_the_price_read(monkeypatch):
    from push import subs as PS
    from sepa import prices as P
    monkeypatch.setattr(GW, "in_session", lambda now=None: True)
    monkeypatch.setattr(PS, "list_subscriptions", lambda *a, **kw: [])

    def _never(*a, **kw):
        raise AssertionError("live prices must not be read when nobody is subscribed")
    monkeypatch.setattr(P, "bulk_live_prices", _never)
    out = GW.check_once()
    assert out == {"ran": False, "reason": "no devices subscribed", "kind": "pivot_alert"}


def test_g3_negative_a_subscribed_device_or_push_false_runs_the_pass(monkeypatch):
    import types
    from push import subs as PS
    from sepa import prices as P
    monkeypatch.setattr(GW, "in_session", lambda now=None: True)
    # check_once imports portfolio.alerts / portfolio.store before the price
    # read; the real package needs py3.10 (the api container) — stub it.
    pkg = types.ModuleType("portfolio")
    alerts = types.ModuleType("portfolio.alerts")
    alerts._resolve_owner = lambda: "owner@example.com"
    store = types.ModuleType("portfolio.store")
    store._get_db = lambda: None
    for name, mod in (("portfolio", pkg), ("portfolio.alerts", alerts), ("portfolio.store", store)):
        monkeypatch.setitem(sys.modules, name, mod)
    seen = {}
    monkeypatch.setattr(PS, "list_subscriptions",
                        lambda *a, **kw: seen.setdefault("kw", kw) and [{"endpoint": "x"}])

    def _boom(*a, **kw):
        raise RuntimeError("tape down")
    monkeypatch.setattr(P, "bulk_live_prices", _boom)
    out = GW.check_once()
    assert out["ran"] is False and "live prices failed" in out["reason"], \
        "the pass PROCEEDED past the device check and hit the (stubbed) tape"
    assert seen["kw"] == {"filter_kind": "pivot_alert", "honor_quiet_hours": False}
    # push=False is the smoke-test path: no device check at all
    monkeypatch.setattr(PS, "list_subscriptions", lambda *a, **kw: [])
    out = GW.check_once(push=False)
    assert "live prices failed" in out["reason"]
    # a broken subscription read counts as subscribed — never a silent skip
    def _sub_boom(*a, **kw):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(PS, "list_subscriptions", _sub_boom)
    assert GW._devices_subscribed() is True


def test_g3_the_kind_is_still_pivot_alert_and_the_skip_is_worded():
    """The keep-set itself is Ajay's (docs/supply_demand/alert_keepset_2026_09_09.md)
    and is not asserted here; what this pins is that the watcher gained no
    new kind and says why it did not run."""
    import inspect
    src = inspect.getsource(GW)
    assert 'kind="pivot_alert"' in src and "no devices subscribed" in src
    assert "gabbar_alert" not in src
