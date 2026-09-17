"""Deep Demand tile — every crossed demand level is drawn (2026-09-16).

Ajay, on the board: "For the deep demand stocks I need the logic to be, the
stocks that crosses the first level of support and lying in second or third
level of support." And, with a screenshot of a tile: "there are two level of
support in this chart and the price is at the second level of support" — the
CHART must show every level already crossed plus the one price is standing in.

WP-B (the tile). The qualifier lives in supply_demand/deep_demand.py (WP-A);
this file only asserts what the board draws and says off that read.

  B1  a 3-level row draws 3 bands, ordinals in order
  B2  NEGATIVE — a 1-level row is byte-identical to today's two-band tile
  B3  the straddle clamp, generalised to N crossed bands (+ the drop case)
  B4  the lid dedupe runs against EVERY crossed band
  B5  the chart window spans the OLDEST crossed level's defining swing
  B6  the tile carries `levels_broken` (+ the old-cache fallback)
  B7  the why-line and the badge — level 2 byte-identical, level 3 reworded
  B8  NEGATIVE — ordering untouched: depth never jumps a closer name
  B9  the note says depth is NOT measured, and never claims an edge

Plus the served-sentence bug from his screenshot: `_dist_text` already says
"now in …", so the deep sentence's own "now " made it read
"broke its 1st demand band (7% below it), now now in the 2nd band".
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chart_maps import board as B  # noqa: E402
from supply_demand import deep_demand as DD  # noqa: E402

# The board fixtures the chart-maps suite already owns — imported, never
# re-typed, so a fixture change there reaches here.
from test_chart_maps import (  # noqa: E402,F401
    _deep_row, _frame, _sales,
    prices, reentry_stub, sales_stub,
)


def _band(lo, hi, touches=3, strength=60.0, oldest=None):
    b = {"lo": lo, "hi": hi, "touches": touches, "strength": strength}
    if oldest is not None:
        b["oldest_touch_bars"] = oldest
    return b


def _deep3(sym="DEEP3", state="in", dist=0.0, **over):
    """A row that crossed TWO levels and is standing in the third.

    Bands mirror the shape `deep_demand.read` now emits: `top_band` is the
    HIGHEST crossed band, `second_band` is the ARRIVAL band, `broken_bands`
    lists every crossed level high->low.
    """
    row = _deep_row(sym, state=state, dist=dist)
    row["last_price"] = 72.0
    b1, b2 = _band(90.0, 95.0, oldest=150), _band(80.0, 85.0, oldest=150)
    row["deep_demand"].update({
        "levels_broken": 2, "level": 3,
        "top_band": b1,
        "second_band": _band(70.0, 75.0, oldest=150),
        "broken_bands": [b1, b2],
        "below_top_pct": 20.0,
    })
    row["deep_demand"].update(over)
    row["plan"] = {"entry_ref": 72.5, "stop": 69.0, "target": 84.0, "rr": 2.0}
    return row


def _labels(tile):
    return [b["label"] for b in tile["bands"]]


def _one(rows, prices, reentry_stub, sales_stub, **kw):
    reentry_stub["deep_rows"] = rows
    for r in rows:
        prices[r["symbol"]] = _frame(200)
        sales_stub[r["symbol"]] = _sales("steady", 9.0)
    kw.setdefault("limit", 5)
    kw.setdefault("min_tier", "any")
    kw.setdefault("min_room", 0)
    return B.board("deep_demand", **kw)


# ---------------------------------------------------------------------------
# B1 — a 3-level row draws 3 bands
# ---------------------------------------------------------------------------
def test_b1_a_third_level_arrival_draws_both_crossed_levels_and_the_one_it_is_in(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    t = _one([_deep3()], prices, reentry_stub, sales_stub)["tiles"][0]
    assert _labels(t) == ["1st demand · broken", "2nd demand · broken",
                          "3rd demand · entering"]
    assert [b["kind"] for b in t["bands"]] == ["supply", "supply", "demand"]
    # geometry untouched: the bands are drawn where the scan put them
    assert [(b["lo"], b["hi"]) for b in t["bands"]] == [
        (90.0, 95.0), (80.0, 85.0), (70.0, 75.0)]


def test_b1_the_ordinals_come_from_the_read_never_from_a_typed_string():
    """One wording source (spec §3.3). A retyped '3rd' here would drift the
    day MAX_LEVELS_BROKEN widens."""
    import inspect
    src = inspect.getsource(B.deep_demand_tiles)
    assert "DD.ordinal(" in src
    for lit in ('"1st demand', '"2nd demand', '"3rd demand',
                '"🩹 In 2nd', '"🩹 Entering 2nd', '"🩹 Reclaiming 2nd'):
        assert lit not in src, f"ordinal retyped: {lit}"


# ---------------------------------------------------------------------------
# B2 — NEGATIVE: one crossed level is exactly today's tile
# ---------------------------------------------------------------------------
def test_b2_negative_a_single_crossed_level_draws_the_two_bands_it_always_did(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    t = _one([_deep_row("ONE")], prices, reentry_stub, sales_stub)["tiles"][0]
    assert _labels(t) == ["1st demand · broken", "2nd demand · entering"]
    assert "3rd demand" not in " ".join(_labels(t))


def test_b2_negative_the_approaching_and_reclaiming_labels_are_unchanged_at_level_two(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    near = _one([_deep_row("NEAR", state="near", dist=1.2)],
                prices, reentry_stub, sales_stub, phase="approaching")["tiles"][0]
    assert "2nd demand · approaching" in _labels(near)
    rec = _deep_row("RECL")
    rec["deep_demand"]["reclaiming"] = True
    t = _one([rec], prices, reentry_stub, sales_stub)["tiles"][0]
    assert "2nd demand · reclaiming" in _labels(t)


# ---------------------------------------------------------------------------
# B3 — the straddle clamp, generalised
# ---------------------------------------------------------------------------
def test_b3_a_one_touch_middle_band_is_clamped_to_the_arrival_band_top(
        prices, reentry_stub, sales_stub, monkeypatch):
    """The 2026-09-14 clamp was written for exactly ONE broken band. With two,
    the MIDDLE one must be clamped against the ARRIVAL band under it — and say
    it is a 1-touch swing box, which is a drawing note, never a gate."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    row = _deep3("MID")
    b1 = _band(90.0, 95.0, oldest=150)
    b2 = _band(72.0, 85.0, touches=1, oldest=150)      # straddles the 70-75 arrival band
    row["deep_demand"]["top_band"] = b1
    row["deep_demand"]["broken_bands"] = [b1, b2]
    t = _one([row], prices, reentry_stub, sales_stub)["tiles"][0]
    assert _labels(t) == ["1st demand · broken",
                          "2nd demand · broken (1-touch swing)",
                          "3rd demand · entering"]
    mid = t["bands"][1]
    assert (mid["lo"], mid["hi"]) == (75.01, 85.0), "clamped to arrival.hi + 0.01"
    assert t["bands"][0]["lo"] == 90.0, "the band above clamps on the ORIGINAL 85.0, not 75.01"


def test_b3_negative_a_fully_swallowed_crossed_band_is_dropped_never_inverted(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    row = _deep3("SWAL")
    b1 = _band(90.0, 95.0, oldest=150)
    b2 = _band(71.0, 74.0, touches=1, oldest=150)      # entirely inside the 70-75 arrival band
    row["deep_demand"]["top_band"] = b1
    row["deep_demand"]["broken_bands"] = [b1, b2]
    t = _one([row], prices, reentry_stub, sales_stub)["tiles"][0]
    assert _labels(t) == ["1st demand · broken", "3rd demand · entering"]
    for b in t["bands"]:
        assert b["hi"] > b["lo"], "no inverted band ever reaches the chart"


def test_b3_negative_a_crossed_band_with_no_geometry_is_skipped_not_drawn(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    row = _deep3("NOGEO")
    b1 = _band(90.0, 95.0, oldest=150)
    row["deep_demand"]["broken_bands"] = [b1, {"lo": None, "hi": None, "touches": 3}]
    t = _one([row], prices, reentry_stub, sales_stub)["tiles"][0]
    assert _labels(t) == ["1st demand · broken", "3rd demand · entering"]


# ---------------------------------------------------------------------------
# B4 — the lid dedupe runs against EVERY crossed band
# ---------------------------------------------------------------------------
def test_b4_a_supply_lid_equal_to_any_crossed_band_is_not_drawn_twice(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {"DUP2": 72.0})
    row = _deep3("DUP2")
    row["supply_zones"] = [
        {"kind": "supply", "lo": 80.0, "hi": 85.0, "touches": 3, "strength": 50.0},
        {"kind": "supply", "lo": 100.0, "hi": 104.0, "touches": 3, "strength": 50.0},
    ]
    t = _one([row], prices, reentry_stub, sales_stub)["tiles"][0]
    plain = [(b["lo"], b["hi"]) for b in t["bands"] if b["label"] == "supply"]
    assert plain == [(100.0, 104.0)], "the 2nd crossed band is not redrawn as a lid"
    assert _labels(t).count("2nd demand · broken") == 1


def test_b4_negative_the_first_crossed_band_dedupe_still_works_on_a_one_level_row(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    row = _deep_row("DUP1")
    row["supply_zones"] = [{"kind": "supply", "lo": 90.0, "hi": 95.0,
                            "touches": 3, "strength": 50.0}]
    t = _one([row], prices, reentry_stub, sales_stub)["tiles"][0]
    assert _labels(t) == ["1st demand · broken", "2nd demand · entering"]


# ---------------------------------------------------------------------------
# B5 — the chart window spans the OLDEST crossed level
# ---------------------------------------------------------------------------
def _spy_days(monkeypatch) -> dict:
    """`_bars` is popped off the tile once the frames are loaded (board.py
    :1858), so the window is read where it is USED — the `days` handed to
    `bars_for`."""
    seen: dict = {}
    real = B.bars_for

    def _spy(symbol, days=None, around=None, pad_after=25):
        seen[symbol] = days
        return real(symbol, days=days, around=around, pad_after=pad_after)

    monkeypatch.setattr(B, "bars_for", _spy)
    return seen


def test_b5_the_window_reaches_back_to_the_oldest_crossed_levels_swing(
        prices, reentry_stub, sales_stub, monkeypatch):
    """A 3rd-level tile whose FIRST level was set 200 bars back drew that band
    off-screen while the window was sized off the arrival band alone."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    seen = _spy_days(monkeypatch)
    row = _deep3("WIDE")
    row["deep_demand"]["broken_bands"][0]["oldest_touch_bars"] = 200
    row["deep_demand"]["top_band"]["oldest_touch_bars"] = 200
    _one([row], prices, reentry_stub, sales_stub)
    assert B._zone_window(row["deep_demand"]["broken_bands"][0], B.BARS_DEFAULT) == 215
    assert seen["WIDE"] == 215, "the 1st crossed level's swing is on the screen"


def test_b5_negative_the_arrival_band_alone_still_sizes_a_one_level_tile(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    seen = _spy_days(monkeypatch)
    _one([_deep_row("SAME")], prices, reentry_stub, sales_stub)
    assert seen["SAME"] == 165, "150 oldest_touch_bars + ZONE_BARS_PAD, unchanged"


def test_b5_negative_the_window_is_still_clamped_at_one_trading_year(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    seen = _spy_days(monkeypatch)
    row = _deep3("CLAMP")
    row["deep_demand"]["broken_bands"][0]["oldest_touch_bars"] = 900
    _one([row], prices, reentry_stub, sales_stub)
    assert seen["CLAMP"] == B.ZONE_BARS_MAX == 252


# ---------------------------------------------------------------------------
# B6 — the tile carries `levels_broken`
# ---------------------------------------------------------------------------
def test_b6_the_tile_carries_levels_broken_and_it_agrees_with_the_level_drawn(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    t = _one([_deep3()], prices, reentry_stub, sales_stub)["tiles"][0]
    assert t["levels_broken"] == 2
    assert "3rd demand · entering" in _labels(t), "level == levels_broken + 1"


def test_b6_negative_a_row_cached_before_this_change_renders_as_one_crossed_level(
        prices, reentry_stub, sales_stub, monkeypatch):
    """An old payload has `top_band`/`second_band` and NO `broken_bands`. It
    must render exactly as it did, and report one crossed level — never zero,
    never a crash."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    old = _deep_row("OLD")
    assert "broken_bands" not in old["deep_demand"]
    t = _one([old], prices, reentry_stub, sales_stub)["tiles"][0]
    assert t["levels_broken"] == 1
    assert _labels(t) == ["1st demand · broken", "2nd demand · entering"]


# ---------------------------------------------------------------------------
# B7 — the why-line and the badge
# ---------------------------------------------------------------------------
def test_b7_level_two_says_exactly_what_it_said_yesterday(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {"OK": 86.7})
    t = _one([_deep_row("OK", state="near", dist=1.2)], prices, reentry_stub,
             sales_stub, phase="approaching")["tiles"][0]
    assert t["why"] == ("broke its 1st demand band (9% below it), now 1.96% above "
                        "the 2nd band — sales +9% YoY say the business didn't "
                        "break with the price")
    assert t["badges"][0]["text"] == "🩹 Entering 2nd band"


def test_b7_a_third_level_arrival_counts_the_levels_it_crossed(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    t = _one([_deep3()], prices, reentry_stub, sales_stub)["tiles"][0]
    assert t["why"].startswith("crossed 2 demand levels (20% below the first), "
                               "now in the 3rd band — sales")
    assert t["badges"][0]["text"] == "🩹 In 3rd demand band"


def test_b7_the_served_sentence_never_says_now_now(
        prices, reentry_stub, sales_stub, monkeypatch):
    """HIS SCREENSHOT, 2026-09-16: the tile read "broke its 1st demand band
    (7% below it), now now in the 2nd band". `_dist_text` already carries the
    "now" on the inside branch; the sentence prepended a second one."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {"IN2": 82.0})
    inside = _one([_deep_row("IN2")], prices, reentry_stub, sales_stub)["tiles"][0]
    assert "now now" not in inside["why"]
    assert "now in the 2nd band" in inside["why"]

    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    deep = _one([_deep3("IN3")], prices, reentry_stub, sales_stub)["tiles"][0]
    assert "now now" not in deep["why"] and "now in the 3rd band" in deep["why"]

    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {"UP3": 76.5})
    above = _one([_deep3("UP3", state="near", dist=2.0)], prices, reentry_stub,
                 sales_stub, phase="approaching")["tiles"][0]
    assert "now now" not in above["why"]
    assert "now 1.96% above the 3rd band" in above["why"]


def test_b7_negative_the_shared_dist_text_is_untouched_for_every_other_board():
    """`_dist_text` is shared with the order-block and tested-band sentences
    (board.py :2587,:2594). Fixing the duplication THERE would move their
    served strings; the deep tile carries its own wrapper instead."""
    assert B._dist_text(0.0, "it", "the block") == "now in the block"
    assert B._dist_text(1.96, "it", "the block") == "1.96% above it"
    assert B._now_dist_text(0.0, "it", "the block") == "now in the block"
    assert B._now_dist_text(1.96, "it", "the block") == "now 1.96% above it"
    assert B._now_dist_text(None, "it", "the block") == "now None% above it"


def test_b7_negative_a_reclaim_keeps_its_suffix_at_every_level(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    row = _deep3("RC3", reclaiming=True)
    t = _one([row], prices, reentry_stub, sales_stub)["tiles"][0]
    assert "now in the 3rd band (reclaimed from below)" in t["why"]
    assert t["badges"][0]["text"] == "🩹 Reclaiming 3rd band"
    assert "3rd demand · reclaiming" in _labels(t)


# ---------------------------------------------------------------------------
# B8 — NEGATIVE: ordering untouched
# ---------------------------------------------------------------------------
def test_b8_negative_a_deeper_arrival_does_not_jump_a_closer_shallower_one(
        prices, reentry_stub, sales_stub, monkeypatch):
    """Depth orders NOTHING (spec §7.4 — his call, unmeasured). The board is
    still `rerank_live(rows, _order.deep_key, live)`: proximity first."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    near3 = _deep3("DEEPFAR", state="near", dist=2.5)
    near3["deep_demand"]["dist_pct"] = 2.5
    near3["last_price"] = 76.88                      # 2.5% over the 75.0 arrival top
    near2 = _deep_row("SHALLOWNEAR", state="near", dist=0.5)
    near2["last_price"] = 85.43                      # 0.5% over the 85.0 arrival top
    out = _one([near3, near2], prices, reentry_stub, sales_stub, phase="approaching")
    assert [t["symbol"] for t in out["tiles"]] == ["SHALLOWNEAR", "DEEPFAR"]


def test_b8_negative_the_tile_builder_still_names_only_the_shared_rank_key():
    import inspect
    src = inspect.getsource(B.deep_demand_tiles)
    assert "rerank_live(rows, _order.deep_key, live)" in src
    assert "sorted(rows" not in src, "no second sort on depth"
    # the depth read happens per-tile, never before the rank
    assert "levels_broken" not in src.split("rerank_live")[0]


# ---------------------------------------------------------------------------
# B9 — the note never claims an edge
# ---------------------------------------------------------------------------
def test_b9_the_note_says_depth_is_not_measured(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    out = _one([_deep3()], prices, reentry_stub, sales_stub)
    assert out["note"].endswith(
        "Depth is NOT measured yet — levels order nothing and gate nothing.")
    assert f"up to the {DD.ordinal(DD.MAX_LEVELS_BROKEN + 1)}" in out["note"]
    assert "crossed one or more demand bands" in out["note"]


def test_b9_negative_the_note_never_claims_an_edge(
        prices, reentry_stub, sales_stub, monkeypatch):
    """The adjacent claim measured `no_signal` (band_structure, 2026-09-16).
    No copy on this board may read as an edge, and the house word is
    'reversal', never 'bounce'."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    out = _one([_deep3()], prices, reentry_stub, sales_stub)
    low = out["note"].lower()
    for banned in ("edge", "outperform", "beats", "bounce"):
        assert banned not in low, banned
    t = out["tiles"][0]
    assert "bounce" not in t["why"].lower()


def test_b9_a_measured_verdict_is_quoted_verbatim_when_the_study_lands(
        prices, reentry_stub, sales_stub, monkeypatch):
    """The note DELEGATES to `deep_levels_measured.note()` — it never reads
    MEASURED["status"] itself, because a raw read printed "Depth is measured:
    pending." Only a quotable SEPARATING run says anything else."""
    from supply_demand import deep_levels_measured as DLM
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})

    for stub in ({"status": "no_signal"}, {"status": "pending"}, None):
        monkeypatch.setattr(DLM, "MEASURED", stub, raising=False)
        out = _one([_deep3()], prices, reentry_stub, sales_stub)
        assert out["note"].endswith(DLM.NOT_MEASURED_NOTE), stub

    monkeypatch.setattr(DLM, "MEASURED",
                        {"status": DLM.STATUS_SEPARATES, "quotable": True,
                         "run_date": "2026-09-16"}, raising=False)
    out = _one([_deep3()], prices, reentry_stub, sales_stub)
    assert out["note"].endswith(DLM.note())
    assert "2026-09-16" in out["note"]


def test_b9_the_warming_note_names_the_deeper_arrivals(
        prices, reentry_stub, sales_stub):
    reentry_stub["warming"] = True
    out = B.board("deep_demand", min_tier="any")
    assert out["warming"] is True
    assert out["note"] == "scanning for deeper demand-level arrivals…"


# ── Review fixes, 2026-09-16 (both critics) ──────────────────────────────────
def test_r1_a_row_with_no_below_top_pct_does_not_take_the_whole_board_down(
        prices, reentry_stub, sales_stub, monkeypatch):
    """`below_top_pct` is absent on a row cached before this read shipped.
    Formatting it raised inside the tile LOOP, so one bad row 500'd every
    other tile on the board — not just its own. The sentence now falls back."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    good = _deep3("GOOD")
    bad = _deep3("NOBELOW")
    bad["deep_demand"].pop("below_top_pct")
    out = _one([good, bad], prices, reentry_stub, sales_stub)
    syms = [t["symbol"] for t in out["tiles"]]
    assert "GOOD" in syms and "NOBELOW" in syms
    t = next(t for t in out["tiles"] if t["symbol"] == "NOBELOW")
    assert t["why"] == "3rd-level demand arrival with Bonde-intact sales"


def test_r1_negative_the_fallback_sentence_is_never_hardcoded_second_level(
        prices, reentry_stub, sales_stub, monkeypatch):
    """`_bonde_gate` passes on score+tier alone, so sales YoY can be None on a
    3rd-level tile. The fallback used to say 'second-level' while the same
    tile's badge said 'In 3rd demand band'."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    monkeypatch.setattr(B, "_sales_badge", lambda s: {"text": "sales", "tone": "good"})
    row = _deep3("NOYOY")
    out = _one([row], prices, reentry_stub, sales_stub)
    t = out["tiles"][0]
    if "with Bonde-intact sales" in t["why"]:
        assert t["why"].startswith(f"{DD.ordinal(3)}-level")
    assert "second-level" not in t["why"]


def test_r2_the_depth_note_delegates_and_never_prints_a_raw_status(
        prices, reentry_stub, sales_stub, monkeypatch):
    """A raw MEASURED['status'] read put 'Depth is measured: pending.' on the
    board. `deep_levels_measured.note()` fails closed — pending, no_signal and
    an unquotable `separates` all read the same."""
    from supply_demand import deep_levels_measured as DLM
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    for stub in ({"status": "pending"},
                 {"status": "no_signal"},
                 {"status": "separates", "quotable": False}):
        monkeypatch.setattr(DLM, "MEASURED", stub, raising=False)
        out = _one([_deep3()], prices, reentry_stub, sales_stub)
        assert "Depth is measured:" not in out["note"]
        assert out["note"].endswith(DLM.NOT_MEASURED_NOTE)


def test_r3_the_note_says_levels_are_counted_off_the_surfaced_window(
        prices, reentry_stub, sales_stub, monkeypatch):
    """CRDO really has six demand bands above its print; the served window
    shows four. 'crossed 2 demand levels' must never read as a claim about
    the whole stack."""
    from supply_demand import price_zones as PZ
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    out = _one([_deep3()], prices, reentry_stub, sales_stub)
    assert f"{PZ.MAX_ZONES_PER_SIDE} bands nearest the print" in out["note"]
    assert "not the whole stack" in out["note"]


def test_r4_the_order_clause_names_the_arrival_band_not_the_second(
        prices, reentry_stub, sales_stub, monkeypatch):
    """The note claimed the sort ran on 'the second band' while its own tiles
    were 3rd-level arrivals, and the FE blurb said 'arrival band'."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    for phase, want in (("reached", "inside their arrival band first"),
                        ("approaching", "nearest their arrival band first")):
        rows = [_deep3(state=("near" if phase == "approaching" else "in"),
                       dist=(1.0 if phase == "approaching" else 0.0))]
        out = _one(rows, prices, reentry_stub, sales_stub, phase=phase)
        assert want in out["note"]
        assert "the second band first" not in out["note"]


def test_r5_negative_the_served_why_line_never_says_now_now(
        prices, reentry_stub, sales_stub, monkeypatch):
    """Ajay's screenshot, 2026-09-16: 'broke its 1st demand band (7% below
    it), now now in the 2nd band'. The sentence prepended 'now' and
    `_dist_text` returned 'now in ...' on the inside branch."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    for state, dist in (("in", 0.0), ("near", 1.96)):
        rows = [_deep3(state=state, dist=dist)]
        out = _one(rows, prices, reentry_stub, sales_stub,
                   phase=("approaching" if state == "near" else "reached"))
        for t in out["tiles"]:
            assert "now now" not in t["why"], t["why"]
