"""Deep Demand — arrival at the 2nd, 3rd or 4th level of support (2026-09-16).

Ajay, verbatim: "For the deep demand stocks I need the logic to be, the stocks
that crosses the first level of support and lying in second or third level of
support. Like CRDO dropped after the earning it crossed multiple support
level."

Until this date `deep_demand.read()` looked at the fixed pair
`demand_zones[0]` / `demand_zones[1]`. It now WALKS the same served window and
counts every level already crossed, capped by `MAX_LEVELS_BROKEN`.

Two things these tests exist to hold:

* the LEVEL COUNT is read off the SURFACED four-band window
  (`price_zones.nearest_first(...)[:MAX_ZONES_PER_SIDE]`), which is a sliding
  window around the print, NOT the whole stack;
* the walk NEVER skips a band for quality — a flimsy arrival band refuses the
  row, it never promotes the next level down, or the reported `level` lies.

Depth is NOT a measured edge (band_structure measured `no_signal`, 2026-09-16)
and nothing here orders or gates on it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import deep_demand as DD                       # noqa: E402
from supply_demand import demand_reentry as DR                    # noqa: E402
from supply_demand import price_zones as PZ                       # noqa: E402
from supply_demand import room_floor as RF                        # noqa: E402


def _band(lo, hi, touches=3, strength=60.0, **kw):
    b = {"kind": "demand", "lo": lo, "hi": hi, "mid": (lo + hi) / 2,
         "touches": touches, "strength": strength}
    b.update(kw)
    return b


def _rec(last, bands, **kw):
    r = {"symbol": "T", "last_price": last, "demand_zones": bands,
         "top_band_read": None}
    r.update(kw)
    return r


# A four-band served window, high→low, the shape price_zones ships.
def _stack():
    return [_band(100, 105), _band(90, 95), _band(80, 85), _band(70, 75)]


# ── 1. the ask: a 3rd-level arrival qualifies ───────────────────────────────
def test_third_level_arrival_qualifies_and_reports_both_crossed_levels():
    dz = _stack()
    r = DD.read(_rec(82.0, dz))
    assert r is not None and r["state"] == "in"
    assert r["levels_broken"] == 2 and r["level"] == 3
    assert (r["second_band"]["lo"], r["second_band"]["hi"]) == (80.0, 85.0)   # = dz[2]
    assert (r["top_band"]["lo"], r["top_band"]["hi"]) == (100.0, 105.0)       # = dz[0]
    assert len(r["broken_bands"]) == 2
    assert [(b["lo"], b["hi"]) for b in r["broken_bands"]] == [(100, 105), (90, 95)]
    # high→low, and every crossed band is strictly ABOVE the print
    assert all(b["lo"] > 82.0 for b in r["broken_bands"])
    # below_top_pct still measures from the FIRST (highest) level crossed
    assert r["below_top_pct"] == pytest.approx((100 - 82) / 100 * 100, abs=0.01)


def test_third_level_arrival_also_qualifies_from_above_within_near_pct():
    dz = _stack()
    last = 85.0 / (1 - (PZ.NEAR_PCT - 0.5) / 100.0)      # just inside the near band
    r = DD.read(_rec(last, dz))
    assert r is not None and r["state"] == "near"
    assert r["level"] == 3 and 0 < r["dist_pct"] <= PZ.NEAR_PCT


# ── 2-5. NEGATIVES on the geometry ──────────────────────────────────────────
def test_a_fourth_level_arrival_now_qualifies_at_the_widened_cap():
    """2026-09-16, same day, one deeper: "can you do level 4 and give me
    filters for that". This row was refused by the cap until MAX_LEVELS_BROKEN
    moved 2 -> 3; nothing else about it changed."""
    dz = _stack()
    got = DD.arrival(dz, 72.0)
    assert got is not None
    levels_broken, arr, broken = got
    assert levels_broken == 3
    assert (arr["lo"], arr["hi"]) == (70.0, 75.0)
    assert [(b["lo"], b["hi"]) for b in broken] == [(100, 105), (90, 95), (80, 85)]
    r = DD.read(_rec(72.0, dz))
    assert r is not None and r["state"] == "in"
    assert r["level"] == 4 and r["levels_broken"] == 3 and len(r["broken_bands"]) == 3
    assert DD.MAX_LEVELS_BROKEN == 3


def test_negative_first_level_still_holding_is_not_this_screen():
    assert DD.read(_rec(102.0, _stack())) is None       # inside dz[0]
    assert DD.arrival(_stack(), 102.0) is None


def test_negative_below_every_band_is_a_breakdown_not_an_arrival():
    assert DD.read(_rec(60.0, _stack())) is None
    assert DD.arrival(_stack(), 60.0) is None


def test_negative_in_the_air_just_past_near_pct_does_not_qualify():
    """NEAR_PCT is the one scale for "at the band". A tenth of a point past it
    is not an arrival — and the walk must NOT keep looking lower, because
    every lower band is farther away."""
    dz = [_band(100, 105), _band(90, 95), _band(80, 85)]
    too_far = 85.0 / (1 - (PZ.NEAR_PCT + 0.1) / 100.0)
    assert DD.read(_rec(too_far, dz)) is None
    just_in = 85.0 / (1 - (PZ.NEAR_PCT - 0.1) / 100.0)
    assert DD.read(_rec(just_in, dz)) is not None


# ── 6. CRDO — his own example, and WHY it is still hidden ───────────────────
def _crdo_bands(touches=None, strength=None):
    """CRDO's REAL served window on 2026-09-16 (close 150.39), read off the
    zone_store: four demand bands nearest the print, high→low."""
    return [_band(161.92, 167.68, touches=1, strength=28.0),
            _band(146.34, 151.55,
                  touches=1 if touches is None else touches,
                  strength=31.0 if strength is None else strength),
            _band(132.76, 138.00, touches=2, strength=54.0),
            _band(123.87, 128.80, touches=3, strength=94.0)]


CRDO_CLOSE = 150.39


def test_negative_crdo_is_hidden_by_BAND_QUALITY_not_by_the_level_count():
    """His example, with its real numbers. The level count is NOT what hides
    CRDO: its geometry already qualified before this change and still does —
    it is standing INSIDE the 2nd level, one level crossed.

    What refuses it is the band bar on the ARRIVAL band, unchanged here:
    touches 1 < MIN_TOUCHES 2, strength 31 < MIN_ZONE_STRENGTH 40. Relaxing
    either is Ajay's call after the study measures whether the gate earns its
    keep — never a side effect of this change.
    """
    dz = _crdo_bands()
    got = DD.arrival(dz, CRDO_CLOSE)
    assert got is not None, "the GEOMETRY qualifies"
    levels_broken, arr, broken = got
    assert levels_broken == 1 and levels_broken + 1 == 2
    assert (arr["lo"], arr["hi"]) == (146.34, 151.55)
    assert [(b["lo"], b["hi"]) for b in broken] == [(161.92, 167.68)]
    # …and the read still refuses it, on quality
    assert DD.read(_rec(CRDO_CLOSE, dz)) is None
    assert arr["touches"] < DR.MIN_TOUCHES
    assert arr["strength"] < DR.MIN_ZONE_STRENGTH


def test_crdo_geometry_qualifies_the_moment_its_arrival_band_meets_the_bar():
    """Same fixture, arrival band lifted to EXACTLY the enforcing constants
    (imported, never retyped) — it shows, at level 2."""
    dz = _crdo_bands(touches=DR.MIN_TOUCHES, strength=DR.MIN_ZONE_STRENGTH)
    r = DD.read(_rec(CRDO_CLOSE, dz))
    assert r is not None
    assert r["state"] == "in" and r["levels_broken"] == 1 and r["level"] == 2
    assert r["second_band"]["lo"] == 146.34
    assert r["top_band"]["lo"] == 161.92
    # NEGATIVE: one notch under either constant and it is gone again
    assert DD.read(_rec(CRDO_CLOSE, _crdo_bands(
        touches=DR.MIN_TOUCHES - 1, strength=DR.MIN_ZONE_STRENGTH))) is None
    assert DD.read(_rec(CRDO_CLOSE, _crdo_bands(
        touches=DR.MIN_TOUCHES, strength=DR.MIN_ZONE_STRENGTH - 1))) is None


# ── 7. the walk never skips a flimsy band ──────────────────────────────────
def test_negative_a_flimsy_arrival_band_refuses_the_row_never_promotes_deeper():
    """If the walk stepped over a weak band to reach the strong one below it,
    `level` would lie AND the band gate would be silently relaxed."""
    dz = [_band(90, 95), _band(80, 85, touches=DR.MIN_TOUCHES - 1),
          _band(70, 75, touches=5, strength=99.0)]
    levels_broken, arr, _ = DD.arrival(dz, 82.0)
    assert (arr["lo"], arr["hi"]) == (80.0, 85.0), "the walk stops at the flimsy band"
    assert levels_broken == 1
    assert DD.read(_rec(82.0, dz)) is None, "and the row is refused, not deepened"


# ── 8. reclaiming reads off the ARRIVAL band ───────────────────────────────
def test_reclaiming_is_read_off_the_arrival_band_not_the_first_one():
    dz = _stack()                       # arrival at 80-85 for a print of 82
    below = DD.read(_rec(82.0, dz, prev_close=78.0))
    assert below["reclaiming"] is True          # yesterday closed UNDER 80
    above = DD.read(_rec(82.0, dz, prev_close=84.0))
    assert above["reclaiming"] is False
    # NEGATIVE: unknown prev_close is never a reclaim
    assert DD.read(_rec(82.0, dz))["reclaiming"] is False
    assert DD.read(_rec(82.0, dz, prev_close=None))["reclaiming"] is False
    assert DD.read(_rec(82.0, dz, prev_close="junk"))["reclaiming"] is False
    # and it is NOT read off the first crossed level: 91 is under dz[1].lo=90?
    # no — 91 sits inside dz[1], so a first-band reading would say False too;
    # 89 is under dz[1] but above the arrival band and must still read False.
    assert DD.read(_rec(82.0, dz, prev_close=89.0))["reclaiming"] is False


# ── 9 + 10. the level count only counts bands the print is STRICTLY below ──
def _out_of_order():
    """A window whose bands are not in canonical high→low order — the shape the
    `broken_bands[0] is dz[0]` guard exists for. The print (88) sits ABOVE
    dz[0] entirely, INSIDE dz[2], and strictly below dz[1] only."""
    return [_band(70, 80), _band(95, 105), _band(85, 90)]


def test_only_bands_strictly_above_the_print_count_as_crossed_levels():
    r = DD.read(_rec(88.0, _out_of_order()))
    assert r is not None
    assert r["levels_broken"] == 1, "the band the print sits above was NOT crossed"
    assert [(b["lo"], b["hi"]) for b in r["broken_bands"]] == [(95, 105)]
    assert r["level"] == 2


def test_negative_break_evidence_is_dropped_when_the_top_level_is_not_dz0():
    """`top_band_read` is computed for demand_zones[0] ONLY
    (demand_reentry.decide_from_frame). Carrying it onto a different band
    would attach another band's break dates to this one."""
    tb = {"bars_since_first_break": 4, "fell_from_pct": 12.5}
    r = DD.read(_rec(88.0, _out_of_order(), top_band_read=tb))
    assert r["top_band"]["lo"] == 95.0 and r["top_band"]["lo"] != 70.0
    assert r["bars_since_top_break"] is None and r["fell_from_pct"] is None
    # POSITIVE control: when the highest crossed level IS dz[0], it rides along
    ok = DD.read(_rec(82.0, _stack(), top_band_read=tb))
    assert ok["top_band"]["lo"] == 100.0
    assert ok["bars_since_top_break"] == 4 and ok["fell_from_pct"] == 12.5


# ── 11. level arithmetic + the constants (mutation guard) ──────────────────
def test_level_is_always_levels_broken_plus_one_and_never_exceeds_the_cap():
    for last in (82.0, 92.0, 150.39, 87.0, 88.0, 72.0, 102.0, 60.0):
        for dz in (_stack(), _crdo_bands(touches=DR.MIN_TOUCHES,
                                         strength=DR.MIN_ZONE_STRENGTH),
                   _out_of_order()):
            r = DD.read(_rec(last, dz))
            if r is None:
                continue
            assert r["level"] == r["levels_broken"] + 1
            assert 1 <= r["levels_broken"] <= DD.MAX_LEVELS_BROKEN
            assert len(r["broken_bands"]) == r["levels_broken"]
            assert r["level"] <= DD.MAX_LEVELS_BROKEN + 1


def test_the_enforcing_constants_are_imported_not_redeclared():
    """One scale for "a real band" across the app, and the depth cap is ONE
    named module constant (so widening it is a one-line edit)."""
    assert DD.MAX_LEVELS_BROKEN == 3
    assert DD.MIN_TOUCHES is DR.MIN_TOUCHES and DR.MIN_TOUCHES == 2
    assert DD.MIN_ZONE_STRENGTH is DR.MIN_ZONE_STRENGTH
    assert DR.MIN_ZONE_STRENGTH == 40.0
    assert DD.NEAR_PCT is PZ.NEAR_PCT
    # the served window the level count is read off is price_zones' own cap
    assert PZ.MAX_ZONES_PER_SIDE == 4


# ── 12. ordinal — one wording source ───────────────────────────────────────
def test_ordinal_table_including_the_teens():
    assert [DD.ordinal(n) for n in (1, 2, 3, 4)] == ["1st", "2nd", "3rd", "4th"]
    assert [DD.ordinal(n) for n in (11, 12, 13)] == ["11th", "12th", "13th"]
    assert [DD.ordinal(n) for n in (21, 22, 23, 111, 112)] == [
        "21st", "22nd", "23rd", "111th", "112th"]
    assert DD.ordinal(0) == "0th"
    # the board label the constant produces
    assert DD.ordinal(DD.MAX_LEVELS_BROKEN + 1) == "4th"


# ── 13. malformed input never crashes a scan ───────────────────────────────
def test_garbage_records_return_none_and_never_raise():
    assert DD.read({}) is None
    assert DD.read({"demand_zones": None, "last_price": 10.0}) is None
    assert DD.read(_rec(82.0, [None, _band(80, 85)])) is None
    assert DD.read(_rec(82.0, [_band(90, 95), None])) is None
    assert DD.read(_rec("82.0", _stack())) is not None, "a numeric string is coerced"
    assert DD.read(_rec("abc", _stack())) is None
    assert DD.read(_rec(float("nan"), _stack())) is None
    assert DD.read(_rec(0.0, _stack())) is None
    assert DD.read(_rec(-5.0, _stack())) is None
    assert DD.read(_rec(82.0, [{"lo": None, "hi": None}, _band(80, 85)])) is None
    assert DD.read(_rec(82.0, [_band(90, 95), {"lo": "x", "hi": "y"}])) is None
    assert DD.arrival(None, 82.0) is None
    assert DD.arrival([_band(90, 95)], 82.0) is None       # a single band is never deep
    assert DD.arrival("not a list", 82.0) is None


# ── 15. room floor — a deep row measures past EVERY level it crossed ───────
def _deep_row(levels: int):
    """A row the way the scan ships it, `levels` demand levels crossed."""
    dz = _stack()
    last = 82.0 if levels == 2 else 92.0
    d = DD.read(_rec(last, dz))
    assert d is not None and d["levels_broken"] == levels
    return {"symbol": "D", "last_price": last,
            "entry_zone": dict(d["second_band"]),
            "nearest_resistance": None,
            "supply_zones": [],
            "demand_zones": [],
            "deep_demand": d}


def test_a_third_level_row_measures_room_past_BOTH_crossed_levels():
    row = _deep_row(2)
    bands = RF.row_bands(row)
    keys = {(b["lo"], b["hi"]) for b in bands}
    assert (100.0, 105.0) in keys and (90.0, 95.0) in keys, "both crossed levels are ceilings"
    room = RF.room_block(82.0, bands, entry_band=RF.row_entry_band(row))
    # the FIRST ceiling overhead is the NEAREST crossed level (90), not the
    # highest one — before 2026-09-16 only the highest was carried and a
    # 3rd-level row read 22% of room where it has 9.8%.
    assert room["target_lo"] == 90.0 and room["target_kind"] == "demand"
    assert room["room_pct"] == pytest.approx(9.76, abs=0.05)


def test_negative_a_cached_row_with_only_top_band_still_measures_its_room():
    """Rows cached before 2026-09-16 carry no `broken_bands` — row_bands must
    fall back to `top_band` rather than losing the ceiling entirely."""
    row = _deep_row(2)
    row["deep_demand"] = {k: v for k, v in row["deep_demand"].items()
                          if k != "broken_bands"}
    bands = RF.row_bands(row)
    keys = {(b["lo"], b["hi"]) for b in bands}
    assert (100.0, 105.0) in keys and (90.0, 95.0) not in keys
    room = RF.room_block(82.0, bands, entry_band=RF.row_entry_band(row))
    assert room["target_lo"] == 100.0
    # NEGATIVE: an empty/garbage broken_bands never wipes the ceiling either
    row["deep_demand"]["broken_bands"] = []
    assert (100.0, 105.0) in {(b["lo"], b["hi"]) for b in RF.row_bands(row)}
    row["deep_demand"]["broken_bands"] = "junk"
    assert (100.0, 105.0) in {(b["lo"], b["hi"]) for b in RF.row_bands(row)}


def test_row_bands_still_dedupes_a_level_that_arrives_from_two_lists():
    row = _deep_row(2)
    row["demand_zones"] = [_band(100, 105), _band(90, 95)]
    keys = [(b.get("kind"), b["lo"], b["hi"]) for b in RF.row_bands(row)]
    assert len(keys) == len(set(keys))


# ── the prior stays null ───────────────────────────────────────────────────
def test_nothing_in_the_read_orders_or_gates_on_the_level_count():
    """band_structure measured `no_signal` (2026-09-16); depth is a DESCRIPTION
    on this board, never a rank and never a gate."""
    import inspect
    src = inspect.getsource(DD.sort_key)
    for forbidden in ("levels_broken", "level\"", "'level'", "MAX_LEVELS_BROKEN"):
        assert forbidden not in src, f"the deep order reaches for {forbidden}"
    from supply_demand import demand_order as O
    assert "levels_broken" not in inspect.getsource(O)
    # `cap()` DOES read the level — it budgets MAX_IN/MAX_NEAR per level so a
    # level chip can reach its own population (2026-09-16, the same reason the
    # cap went per STATE on 2026-09-03). Budgeting is not ordering: the list
    # reaching cap() is already sorted, and cap() preserves that order.
    # NB: strip the docstring before any source scan — an assertion that the
    # code never mentions "sort" matched the docstring sentence explaining why
    # the list arrives already sorted (the same trap cost a round earlier today
    # on `arrival`; test_supply_demand_contracts._code_only exists for this).
    cap_src = inspect.getsource(DD.cap).replace(DD.cap.__doc__ or "", "")
    assert 'd.get("level")' in cap_src
    assert "sort" not in cap_src and "key=" not in cap_src


# ═══════════════════════════════════════════════════════════════════════════
# LEVEL 4 + the per-level filter (Ajay 2026-09-16, same day):
# "can you do level 4 and give me filters for that"
# ═══════════════════════════════════════════════════════════════════════════

# ── L1. four is the ceiling the SERVED WINDOW can express ──────────────────
def test_the_cap_is_exactly_what_the_served_window_can_feed():
    """`rec["demand_zones"]` is `nearest_first(...)[:MAX_ZONES_PER_SIDE]`, so
    with four bands surfaced at most THREE can sit above the arrival band.
    The module asserts the relation at import; this pins it, so raising the
    window later cannot silently leave the cap behind."""
    assert PZ.MAX_ZONES_PER_SIDE == 4
    assert DD.MAX_LEVELS_BROKEN == PZ.MAX_ZONES_PER_SIDE - 1 == 3
    assert DD.LEVEL_CHOICES == (2, 3, 4)
    assert DD.ordinal(DD.LEVEL_CHOICES[-1]) == "4th"


def test_negative_a_window_longer_than_the_served_one_still_refuses_a_5th_level():
    """A hand-built window of FIVE bands (longer than price_zones will ever
    serve) must STILL be refused past the cap — the ceiling is the constant,
    not an accident of how many bands happened to arrive."""
    dz = [_band(110, 115), _band(100, 105), _band(90, 95),
          _band(80, 85), _band(70, 75)]
    assert DD.arrival(dz, 72.0) is None, "4 levels crossed > MAX_LEVELS_BROKEN"
    assert DD.read(_rec(72.0, dz)) is None
    broken_above = [z for z in dz if 72.0 < z["lo"]]
    assert len(broken_above) == 4 > DD.MAX_LEVELS_BROKEN
    # …and the row one level shallower on the same window IS served, at 4
    r = DD.read(_rec(82.0, dz))
    assert r is not None and r["level"] == 4 and r["levels_broken"] == 3


def test_negative_the_module_assertion_ties_the_cap_to_the_window():
    """The guard exists so a later MAX_ZONES_PER_SIDE change cannot leave the
    cap unreachable. Re-run the module's own condition against a shrunk
    window — it must fail."""
    assert 1 <= DD.MAX_LEVELS_BROKEN <= PZ.MAX_ZONES_PER_SIDE - 1
    shrunk = 2                                   # a 2-band window
    assert not (DD.MAX_LEVELS_BROKEN <= shrunk - 1), \
        "the assertion would have caught a shrunk window"
    import inspect
    src = inspect.getsource(DD)
    assert "MAX_ZONES_PER_SIDE - 1" in src, "the cap guard names the window cap"


# ── L2. parse_levels — the ONE parser, and it fails open ───────────────────
def test_parse_levels_reads_all_and_a_comma_list():
    assert DD.parse_levels("all") is None
    assert DD.parse_levels("ALL") is None
    assert DD.parse_levels("3,4") == frozenset({3, 4})
    assert DD.parse_levels(" 4 ") == frozenset({4})
    assert DD.parse_levels("2") == frozenset({2})
    assert DD.parse_levels(" 3 , 4 ") == frozenset({3, 4})
    assert DD.parse_levels("4,3,2") == frozenset({2, 3, 4})


def test_parse_levels_collapses_duplicates_and_drops_the_junk_parts():
    assert DD.parse_levels("4,4,4") == frozenset({4})
    assert DD.parse_levels("2,junk,4") == frozenset({2, 4})
    assert DD.parse_levels("3,,4,") == frozenset({3, 4})
    assert DD.parse_levels("4,9") == frozenset({4}), "out-of-range parts drop"


def test_negative_parse_levels_fails_open_on_everything_it_cannot_read():
    """An unknown spec must serve the FULL board, never an empty one — an
    empty Deep Demand tab reads as 'nothing qualifies today', which is a lie
    about the market."""
    for junk in ("", "   ", "junk", "0", "9", "-1", "1", "5", "2.5",
                 ",", ",,,", "null", "undefined"):
        assert DD.parse_levels(junk) is None, junk
    # only the EXACT word is "all": inside a list it is just another junk part
    assert DD.parse_levels("all,4") == frozenset({4})
    for not_a_string in (None, 4, 3.0, True, ["3", "4"], {"3": 1}, object()):
        assert DD.parse_levels(not_a_string) is None, not_a_string


def test_negative_parse_levels_never_returns_an_empty_set():
    """An empty frozenset would hide every tile. None (= all) is the only
    'nothing selected' answer this parser may give."""
    for spec in ("", "junk", "0", "9", "1", "5", None, 4):
        got = DD.parse_levels(spec)
        assert got is None and got != frozenset()


def test_parse_levels_range_is_derived_from_the_cap_not_typed():
    """Every level the cap allows parses; the one past it does not."""
    for n in DD.LEVEL_CHOICES:
        assert DD.parse_levels(str(n)) == frozenset({n})
    assert DD.parse_levels(str(DD.MAX_LEVELS_BROKEN + 2)) is None
    assert DD.parse_levels(str(DD.LEVEL_CHOICES[0] - 1)) is None


def test_levels_label_normalises_the_echo():
    assert DD.levels_label(None) == "all"
    assert DD.levels_label(frozenset()) == "all"
    assert DD.levels_label(frozenset({4})) == "4"
    assert DD.levels_label(frozenset({4, 3})) == "3,4"
    assert DD.levels_label(DD.parse_levels("4,4, junk ,3")) == "3,4"
    assert DD.levels_label(DD.parse_levels("junk")) == "all"


def test_the_filter_is_pure_and_orders_nothing():
    """`parse_levels` is a SET — it cannot carry an order, which is the point:
    depth is unmeasured and must never rank (band_structure, `no_signal`)."""
    import inspect
    src = inspect.getsource(DD.parse_levels) + inspect.getsource(DD.levels_label)
    for forbidden in ("sort_key", "deep_key", "score", "rank"):
        assert forbidden not in src, forbidden
    assert isinstance(DD.parse_levels("3,4"), frozenset)


def test_the_payload_cap_gives_every_level_its_own_budget():
    """Ajay 2026-09-16: "can you do level 4 and give me filters for that".

    The deep list is sorted closest-first and is DEPTH-BLIND, so one shared
    pair of counters fills with whichever level happens to be nearest its
    band that day — and a level chip could go EMPTY while hundreds of names
    sit at that level. Same failure the per-STATE split fixed on 2026-09-03.
    """
    def row(sym, level, state):
        return {"symbol": sym, "deep_demand": {"level": level, "state": state}}

    rows = ([row(f"A{i}", 2, "in") for i in range(DD.MAX_IN + 5)]
            + [row(f"B{i}", 4, "in") for i in range(3)]
            + [row(f"C{i}", 4, "near") for i in range(2)])
    kept = DD.cap(rows)
    lv = {}
    for r in kept:
        d = r["deep_demand"]
        lv.setdefault((d["level"], d["state"]), 0)
        lv[(d["level"], d["state"])] += 1
    assert lv[(2, "in")] == DD.MAX_IN          # level 2 still capped at its own budget
    assert lv[(4, "in")] == 3                  # …and level 4 is NOT starved by it
    assert lv[(4, "near")] == 2


def test_negative_the_cap_never_lets_one_level_exceed_its_own_budget():
    rows = [{"symbol": f"D{i}", "deep_demand": {"level": 3, "state": "near"}}
            for i in range(DD.MAX_NEAR + 7)]
    kept = DD.cap(rows)
    assert len(kept) == DD.MAX_NEAR


def test_negative_the_cap_preserves_order_and_keeps_an_unknown_level():
    """It budgets, it does not rank — the list arrives already sorted. A row
    with no level (a cache written before the walk shipped) is kept, never
    silently dropped."""
    rows = [{"symbol": "Z1", "deep_demand": {"level": 2, "state": "in"}},
            {"symbol": "Z2", "deep_demand": {"state": "in"}},
            {"symbol": "Z3", "deep_demand": {"level": 4, "state": "in"}}]
    assert [r["symbol"] for r in DD.cap(rows)] == ["Z1", "Z2", "Z3"]
