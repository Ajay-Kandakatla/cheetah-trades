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
def test_b9_the_note_says_depth_was_measured_and_separated_nothing(
        prices, reentry_stub, sales_stub, monkeypatch):
    """LANDED 2026-09-16 — the sentence is served by deep_levels_measured.note(),
    never typed here, so it moved on its own when the replay came back."""
    from supply_demand import deep_levels_measured as DLM
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    out = _one([_deep3()], prices, reentry_stub, sales_stub)
    assert out["note"].endswith(DLM.note())
    assert "order nothing and gate nothing" in out["note"]
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
                 {"status": "no_signal"},                     # unquotable
                 {"status": "separates", "quotable": False}):
        monkeypatch.setattr(DLM, "MEASURED", stub, raising=False)
        out = _one([_deep3()], prices, reentry_stub, sales_stub)
        assert "Depth is measured:" not in out["note"]
        assert out["note"].endswith(DLM.NOT_MEASURED_NOTE)
    # …and a QUOTABLE no_signal says it was measured and came back null — a
    # different fact from nobody having looked.
    monkeypatch.setattr(DLM, "MEASURED",
                        {"status": "no_signal", "quotable": True,
                         "run_date": "2026-09-16"}, raising=False)
    out = _one([_deep3()], prices, reentry_stub, sales_stub)
    assert out["note"].endswith(DLM.NO_SIGNAL_NOTE_FMT % "2026-09-16")
    assert "NOT measured yet" not in out["note"]


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


# ═══════════════════════════════════════════════════════════════════════════
# The per-level filter (Ajay 2026-09-16: "can you do level 4 and give me
# filters for that"). L1-L8 — the board half of the contract.
# ═══════════════════════════════════════════════════════════════════════════

def _deep4(sym="DEEP4", state="in", dist=0.0, **over):
    """A row that crossed THREE levels and is standing in the fourth — the
    deepest the served four-band window can express."""
    row = _deep_row(sym, state=state, dist=dist)
    row["last_price"] = 62.0
    b1 = _band(90.0, 95.0, oldest=150)
    b2 = _band(80.0, 85.0, oldest=150)
    b3 = _band(70.0, 75.0, oldest=150)
    row["deep_demand"].update({
        "levels_broken": 3, "level": 4,
        "top_band": b1,
        "second_band": _band(60.0, 65.0, oldest=150),
        "broken_bands": [b1, b2, b3],
        "below_top_pct": 31.1,
    })
    row["deep_demand"].update(over)
    row["plan"] = {"entry_ref": 62.5, "stop": 59.0, "target": 74.0, "rr": 2.0}
    return row


def _syms(out):
    return [t["symbol"] for t in out["tiles"]]


# ── L1. a 4th-level row reaches the board and draws all three crossed levels
def test_l1_a_fourth_level_arrival_draws_three_crossed_levels(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    t = _one([_deep4()], prices, reentry_stub, sales_stub)["tiles"][0]
    assert _labels(t) == ["1st demand · broken", "2nd demand · broken",
                          "3rd demand · broken", "4th demand · entering"]
    assert t["levels_broken"] == 3
    assert t["badges"][0]["text"] == "🩹 In 4th demand band"
    assert "now in the 4th band" in t["why"]


# ── L2. the filter hides only what it should ───────────────────────────────
def test_l2_the_level_filter_keeps_only_the_selected_arrival_levels(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    rows = [_deep_row("TWO"), _deep3("THREE"), _deep4("FOUR")]
    assert set(_syms(_one(rows, prices, reentry_stub, sales_stub))) == {
        "TWO", "THREE", "FOUR"}
    assert _syms(_one(rows, prices, reentry_stub, sales_stub, levels="4")) == ["FOUR"]
    assert set(_syms(_one(rows, prices, reentry_stub, sales_stub,
                          levels="3,4"))) == {"THREE", "FOUR"}
    assert _syms(_one(rows, prices, reentry_stub, sales_stub, levels="2")) == ["TWO"]


def test_l2_the_echoed_selection_is_normalised_not_the_raw_string(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    rows = [_deep_row("TWO"), _deep3("THREE"), _deep4("FOUR")]
    assert _one(rows, prices, reentry_stub, sales_stub)["levels"] == "all"
    assert _one(rows, prices, reentry_stub, sales_stub,
                levels=" 4 , 3 ,4")["levels"] == "3,4"
    assert _one(rows, prices, reentry_stub, sales_stub,
                levels="junk")["levels"] == "all"


# ── L3. level_counts is computed with the filter OFF ───────────────────────
def test_l3_level_counts_are_computed_with_the_filter_off_and_survive_it_on(
        prices, reentry_stub, sales_stub, monkeypatch):
    """The chips display these. Counting them AFTER the filter would zero the
    other chips the moment one is ticked — and they are the only way back."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    rows = [_deep_row("TWO"), _deep_row("TWO2"), _deep3("THREE"), _deep4("FOUR")]
    want = {"2": 2, "3": 1, "4": 1}
    for spec in ("all", "4", "3,4", "2", "junk"):
        out = _one(rows, prices, reentry_stub, sales_stub, levels=spec)
        assert out["level_counts"] == want, spec


def test_l3_hidden_by_level_matches_what_the_filter_removed(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    rows = [_deep_row("TWO"), _deep_row("TWO2"), _deep3("THREE"), _deep4("FOUR")]
    for spec, kept in (("all", 4), ("4", 1), ("3,4", 2), ("2", 2), ("junk", 4)):
        out = _one(rows, prices, reentry_stub, sales_stub, levels=spec)
        assert len(out["tiles"]) == kept, spec
        assert out["hidden_by_level"] == len(rows) - kept, spec
        assert sum(out["level_counts"].values()) == len(rows), spec


def test_l3_the_count_keys_are_derived_from_the_cap(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    out = _one([_deep4()], prices, reentry_stub, sales_stub)
    assert sorted(out["level_counts"]) == [str(n) for n in DD.LEVEL_CHOICES]
    assert sorted(out["level_counts"]) == ["2", "3", "4"]


# ── L4. NEGATIVE: an unknown spec serves the FULL board ────────────────────
def test_l4_negative_an_unknown_levels_spec_never_serves_an_empty_board(
        prices, reentry_stub, sales_stub, monkeypatch):
    """Fail open. An empty Deep Demand tab reads as 'nothing qualifies today',
    which is a lie about the market."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    rows = [_deep_row("TWO"), _deep3("THREE"), _deep4("FOUR")]
    full = set(_syms(_one(rows, prices, reentry_stub, sales_stub)))
    for junk in ("", "   ", "junk", "0", "9", "1", "5", "-1", ",", "2.5",
                 "null", "undefined"):
        out = _one(rows, prices, reentry_stub, sales_stub, levels=junk)
        assert set(_syms(out)) == full, junk
        assert out["levels"] == "all" and out["hidden_by_level"] == 0, junk


def test_l4_negative_a_non_string_levels_value_is_treated_as_all(
        prices, reentry_stub, sales_stub, monkeypatch):
    """FastAPI resolves `Query(...)` defaults at REQUEST time, so a direct
    container call hands `board()` the Query OBJECT — truthy, no `.lower()`.
    That bug shipped twice on the demand board (board.py, 2026-08-14)."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    rows = [_deep_row("TWO"), _deep4("FOUR")]
    for weird in (None, 4, 3.0, True, object(), ["3", "4"]):
        out = _one(rows, prices, reentry_stub, sales_stub, levels=weird)
        assert set(_syms(out)) == {"TWO", "FOUR"}, weird
        assert out["levels"] == "all", weird


# ── L5. NEGATIVE: the filter does NOT reorder ──────────────────────────────
def test_l5_negative_the_level_filter_does_not_reorder_the_board(
        prices, reentry_stub, sales_stub, monkeypatch):
    """Depth is unmeasured (band_structure, `no_signal`), so a 4th-level name
    must not jump a closer 2nd-level one — with the filter off OR on."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    far4 = _deep4("DEEPFAR", state="near", dist=2.5)
    far4["deep_demand"]["dist_pct"] = 2.5
    far4["last_price"] = 66.63                       # 2.5% over the 65.0 top
    near2 = _deep_row("SHALLOWNEAR", state="near", dist=0.5)
    near2["last_price"] = 85.43                      # 0.5% over the 85.0 top
    rows = [far4, near2]
    out = _one(rows, prices, reentry_stub, sales_stub, phase="approaching")
    assert _syms(out) == ["SHALLOWNEAR", "DEEPFAR"]
    # the same order survives a filter that keeps both
    out24 = _one(rows, prices, reentry_stub, sales_stub, phase="approaching",
                 levels="2,4")
    assert _syms(out24) == ["SHALLOWNEAR", "DEEPFAR"]


def test_l5_negative_the_surviving_rows_keep_their_relative_rank(
        prices, reentry_stub, sales_stub, monkeypatch):
    """Filtering must be a `continue`, never a re-sort: the kept tiles come
    back in exactly the order the unfiltered board put them in."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    rows = [_deep_row("TWO"), _deep3("THREE"), _deep4("FOUR"), _deep_row("TWO2")]
    full = _syms(_one(rows, prices, reentry_stub, sales_stub))
    kept = _syms(_one(rows, prices, reentry_stub, sales_stub, levels="2,4"))
    assert kept == [s for s in full if s in set(kept)]


def test_l5_negative_the_tile_builder_still_names_only_the_shared_rank_key():
    import inspect
    src = inspect.getsource(B.deep_demand_tiles)
    assert "rerank_live(rows, _order.deep_key, live)" in src
    # the filter must run AFTER the rank, never before it
    assert "levels_sel" in src.split("rerank_live")[1]
    assert "sorted(rows" not in src


# ── L6. the note names the selection only when it is not "all" ─────────────
def test_l6_the_note_names_the_active_selection(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    rows = [_deep_row("TWO"), _deep3("THREE"), _deep4("FOUR")]
    out = _one(rows, prices, reentry_stub, sales_stub, levels="3,4")
    assert "Showing 3rd / 4th level arrivals only — 1 hidden" in out["note"]
    one = _one(rows, prices, reentry_stub, sales_stub, levels="4")
    assert "Showing 4th level arrivals only — 2 hidden" in one["note"]


def test_l6_negative_an_all_board_says_nothing_about_a_selection(
        prices, reentry_stub, sales_stub, monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    rows = [_deep_row("TWO"), _deep4("FOUR")]
    for spec in ("all", "junk", ""):
        note = _one(rows, prices, reentry_stub, sales_stub, levels=spec)["note"]
        assert "level arrivals only" not in note, spec
        assert "hidden by the level filter" not in note, spec
    # and the depth disclaimer is still the LAST thing said, filtered or not
    from supply_demand import deep_levels_measured as DLM
    for spec in ("all", "4"):
        note = _one(rows, prices, reentry_stub, sales_stub, levels=spec)["note"]
        assert note.endswith(DLM.note()), spec


def test_l6_negative_the_note_ordinals_are_not_typed_strings():
    import inspect
    src = inspect.getsource(B.deep_demand_tiles)
    assert "DD.ordinal(n) for n in sorted(levels_sel)" in src
    for lit in ('"4th level', "'4th level", '"3rd / 4th'):
        assert lit not in src, lit


# ── L7. the filter runs AFTER the other drops ──────────────────────────────
def test_l7_the_counts_describe_what_survives_the_bonde_gate_and_the_room_floor(
        prices, reentry_stub, sales_stub, monkeypatch):
    """`level_counts` is what a chip shows, so it must be counted where the
    tiles are — after the sales gate, the reversed-already drop and the room
    floor — not off the raw scan rows."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    good, weak = _deep4("GOOD4"), _deep4("WEAK4")
    reentry_stub["deep_rows"] = [good, weak]
    for r in (good, weak):
        prices[r["symbol"]] = _frame(200)
    sales_stub["GOOD4"] = _sales("steady", 9.0)
    sales_stub["WEAK4"] = _sales("weak", 1.0)          # Bonde refuses it
    out = B.board("deep_demand", limit=5, min_tier="any", min_room=0)
    assert _syms(out) == ["GOOD4"]
    assert out["level_counts"]["4"] == 1, "the Bonde-refused row is not counted"
    assert out["dropped_weak_sales"] == 1
    assert out["hidden_by_level"] == 0


# ── L8. the gabbar `level` param is a different thing and still works ──────
def test_l8_the_gabbar_level_param_is_untouched_by_the_new_levels_param():
    """`level` (singular) is the gabbar tab's band TYPE; `levels` (plural) is
    the deep tab's arrival-level filter. Two params, two tabs, no overlap."""
    import inspect
    from chart_maps import api as A
    sig = inspect.signature(A.chart_maps)
    assert "level" in sig.parameters and "levels" in sig.parameters
    board_sig = inspect.signature(B.board)
    assert board_sig.parameters["level"].default == "all"
    assert board_sig.parameters["levels"].default == "all"
    src = inspect.getsource(B.board)
    # the gabbar branch still forwards `level`, the deep branch `levels`
    gab = src.split('t == "gabbar"')[1]
    assert "level=level" in gab and "levels=" not in gab
    deep = src.split('t == "deep_demand"')[1].split("elif")[0]
    assert "levels=levels" in deep and "level=level" not in deep


def test_l8_the_gabbar_tab_still_takes_its_own_level_and_ignores_levels(
        prices, reentry_stub, sales_stub, monkeypatch):
    """NEGATIVE: the new param must not leak into another tab's payload."""
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    out = B.board("gabbar", limit=5, min_tier="any", level="aggressive",
                  levels="4")
    assert out.get("level") == "aggressive"
    for leaked in ("levels", "level_counts", "hidden_by_level"):
        assert leaked not in out, leaked
