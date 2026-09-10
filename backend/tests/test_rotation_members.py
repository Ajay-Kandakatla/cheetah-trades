"""The member table behind a Hot-sectors chip.

Ajay 2026-09-10: *"I would like to click on the sector category and see the
related stocks list in a pop over to see which ones are gaining traction"*.

THE ONE THING THAT WOULD MISLEAD HIM
------------------------------------
The strip's chip median is computed over a DETERMINISTIC STRIDE SAMPLE —
`COHORT_SAMPLE` / `INDUSTRY_SAMPLE` = 25 names, `sample_per_group` = 40 for the
sector grid. Technology carries hundreds of liquid members; the chip reads 25
of them. A popover that listed the sample would read as "these are the stocks
in Technology" and be wrong for most of the sector; a popover that lists the
full membership under a median computed off the sample is two answers to one
question unless the page SAYS SO. So these pin, in order:

  1. the table is the FULL membership, and the chip's number is untouched
  2. the reconciliation line exists and names both populations
  3. "gaining traction" is a defined, printed measure — two legs, both shown
  4. the vs-group figure is measured against that name's OWN group
  5. names that could not be priced are COUNTED, never silently absent
  6. the endpoint reads the persisted build and NEVER triggers one
     (a cold `tracker.build()` is ~29.5 s and one sector's full member load
     7.82 s at WORKERS=8 — neither belongs behind a click)
  7. a zone-read failure degrades the demand marker ONLY

Nothing here pushes an alert and nothing here loosens a gate. The demand
marker is read through `supply_demand.bounce_room` — the ONE shared definition
of "at demand" — never a second geometry.

All synthetic: no Mongo, no provider, no scan on disk.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rotation import api as RA  # noqa: E402
from rotation import tracker as T  # noqa: E402
from sepa import context_refresh as MC  # noqa: E402

FRESH = "2026-09-09"


def _dates(n: int, end: str = FRESH) -> list:
    y, m, d = (int(x) for x in end.split("-"))
    last = date(y, m, d)
    return [(last - timedelta(days=n - 1 - i)).isoformat() for i in range(n)]


def bars(pairs):
    """[(date, close)] -> bar dicts, the shape chart_maps.board.bars_for emits."""
    return [{"t": d, "o": c, "h": c, "l": c, "c": c, "v": 1_000_000} for d, c in pairs]


def frame(n: int = 100, first: float = 100.0, last: float = 110.0, end: str = FRESH):
    """A straight ramp of `n` sessions ending on `end`."""
    step = (last - first) / float(n - 1)
    return bars([(d, round(first + i * step, 6)) for i, d in enumerate(_dates(n, end))])


def legs(ret_5d, ret_21d, ret_63d, end: str = FRESH):
    """A frame whose trailing 5 / 21 / 63-session returns are exactly these.

    Built backwards from the last close so the three legs move independently —
    a straight ramp cannot express "flat month, hot week", which is the whole
    thing the traction flag is looking for.
    """
    n = 100
    closes = [100.0] * n
    for offset, ret in ((T.WINDOW_FAST, ret_5d), (T.WINDOW_SHORT, ret_21d),
                        (T.WINDOW_MED, ret_63d)):
        if ret is not None:
            closes[n - 1 - offset] = 100.0 / (1.0 + ret / 100.0)
    return bars(list(zip(_dates(n, end), closes)))


# ═══════════════════════════════════════════════════════════════════════════
# 1 · POPULATION — the table is the full membership, the chip is not
# ═══════════════════════════════════════════════════════════════════════════
SECT, IND = "Technology", "Semiconductors"
SYMS = [f"S{i:02d}" for i in range(30)]


@pytest.fixture
def built(monkeypatch):
    """One synthetic sector of 30 names, all in one industry. No tiers, no
    themes, no network, no zone store. `sample_per_group=10` so the sector
    chip's sample and the industry chip's 25-name stride are both visibly
    smaller than the 30 names the popover must list."""
    from sepa import universe as U

    monkeypatch.setattr(U, "THEME_UNIVERSE", {})
    monkeypatch.setattr(T, "_tier_sets", lambda: {})
    monkeypatch.setattr(T, "_sector_members", lambda dv, px: {
        SECT: list(SYMS), "_unmapped": 0,
        "_rows": [(s, SECT, IND) for s in SYMS]})
    monkeypatch.setattr(
        T, "_load",
        lambda syms: {s: frame(last=110.0 + (i % 7))
                      for i, s in enumerate(sorted(set(syms)))})
    # The demand marker is context; it must not be able to shape the maths.
    monkeypatch.setattr(T, "_zone_marks", lambda *a, **k: ({}, {
        "day": None, "covered": 0, "unmarked": 0, "at_demand": 0,
        "source": "unavailable", "error": "stubbed in tests"}))
    return T.build(start="2026-06-01", sample_per_group=10)


def test_the_member_table_is_the_full_membership_not_the_stride_sample(built):
    """A synthetic sector of 30 names: the sector chip's median is over 10 of
    them and the industry chip's over 25 — and both tables must still carry
    all 30. He clicked a sector to see its stocks, not a sample of them."""
    sec = next(r for r in built["sectors"] if r["group"] == SECT)
    ind = next(r for r in built["industries"] if r["group"] == IND)
    assert sec["n"] == 10, "the chip's own median stays on its sample — unchanged"
    assert ind["n"] == T.INDUSTRY_SAMPLE == 25

    groups = built[T.MEMBERS_KEY]["groups"]
    for grain, label in (("sector", SECT), ("industry", IND)):
        g = groups[grain][label]
        assert g["n_full"] == 30, f"{label} must span all 30 members"
        assert g["priced"] == 30 and len(g["symbols"]) == 30
        assert set(g["symbols"]) == set(SYMS)
    assert len(built[T.MEMBERS_KEY]["by_symbol"]) == 30


def test_every_group_the_strip_can_render_has_a_member_table(built):
    """A chip with no table opens an empty popover, which reads as 'this
    sector has no stocks'. Every rendered label must resolve."""
    groups = built[T.MEMBERS_KEY]["groups"]
    rendered = {"sector": {r["group"] for r in built["sectors"]},
                "cohort": {r["group"] for r in built["cohorts"]},
                "industry": {r["group"] for r in built["industries"]},
                "theme": {r["group"] for r in built["themes"]}}
    assert rendered["sector"] and rendered["industry"], "the fixture renders rows"
    for grain, labels in rendered.items():
        missing = labels - set(groups.get(grain) or {})
        assert not missing, f"{grain} chips with no member table: {sorted(missing)}"


def test_the_chip_numbers_are_untouched_by_the_member_table(built):
    """HOUSE RULE: do not change a number he already sees. The chip stays a
    sample median restated against the benchmark; the table is ADDITIVE and
    keeps its own full-membership median on its own key."""
    sec = next(r for r in built["sectors"] if r["group"] == SECT)
    for key in ("rel_window", "rel_21d", "rel_63d", "median_window",
                "median_21d", "median_63d", "n", "dropped", "pct_positive"):
        assert key in sec, f"the member table must not drop the chip's {key}"
    g = built[T.MEMBERS_KEY]["groups"]["sector"][SECT]
    assert g["median_21d"] == sec["median_21d"], "the sampled median, carried verbatim"
    assert "median_21d_full" in g, "the full-membership median gets its OWN key"
    assert "median_21d_full" not in sec, "and is never written back onto the chip"


def test_the_table_says_the_two_medians_are_two_populations(built):
    """Where the full list could be mistaken for the source of the median above
    it, the payload must say so. One sentence, shipped with the data."""
    note = built[T.MEMBERS_KEY]["note"]
    assert note == T.MEMBER_NOTE and note.strip()
    low = note.lower()
    assert "full" in low and "membership" in low
    assert "median_21d_full" in note
    assert "sample" in low and "different population" in low


def test_the_traction_definition_travels_with_the_table(built):
    """His standing rule: any per-name measure on a board he trades ships its
    definition. The formula and both thresholds ride in the payload."""
    spec = built[T.MEMBERS_KEY]["traction"]
    assert spec is T.TRACTION_SPEC or spec == T.TRACTION_SPEC
    assert "pace_5" in spec["formula"] and "pace_21" in spec["formula"]
    assert spec["min_accel_pp"] == T.TRACTION_MIN_ACCEL_PP
    assert spec["min_vs_group_pp"] == T.TRACTION_MIN_VS_GROUP_PP
    assert "not a buy signal" in spec["not_a_signal"].lower()
    assert built[T.MEMBERS_KEY]["windows"] == {
        "fast": T.WINDOW_FAST, "short": T.WINDOW_SHORT, "med": T.WINDOW_MED}


def test_the_full_table_is_stripped_off_the_rotation_page_payload(built):
    """~350 KB of member rows must not ride on every /rotation call — the page
    that pays for it is the one that opened a popover."""
    public = RA._public(built)
    assert T.MEMBERS_KEY not in public
    assert public["members_index"]["available"] is True
    assert public["members_index"]["symbols"] == 30
    assert "sector" in public["members_index"]["grains"]
    # and nothing else about the page moved
    assert public["sectors"] == built["sectors"]


# ═══════════════════════════════════════════════════════════════════════════
# 2 · "GAINING TRACTION" — a defined measure, both legs printed
# ═══════════════════════════════════════════════════════════════════════════
def test_traction_is_true_for_an_accelerating_name():
    """+8% in the last week against a +10% month: 1.600 pts/session this week
    against 0.476 over the month, so it is running 1.124 pts/session faster
    than its own trailing month — and it is ahead of its group's +5%."""
    r = T.traction_read(8.0, 10.0, 5.0)
    assert r["pace_5"] == pytest.approx(1.6)
    assert r["pace_21"] == pytest.approx(0.476, abs=0.001)
    assert r["traction"] == pytest.approx(1.124, abs=0.001)
    assert r["vs_group_21"] == pytest.approx(5.0)
    assert r["gaining"] is True


def test_traction_is_false_for_a_decaying_name():
    """+12% over the month but -4% in the last week, and behind its group.
    A popover that ranked this on top would be selling him the past."""
    r = T.traction_read(-4.0, 12.0, 16.0)
    assert r["traction"] < 0 and r["vs_group_21"] < 0
    assert r["gaining"] is False


@pytest.mark.parametrize("fast,short,median,why", [
    (2.0, 10.0, 5.0, "0.40 < the month's own 0.476 pts/session — no acceleration"),
    (8.0, 10.0, 10.0, "level with its group is not ahead of it"),
    (8.0, 10.0, 12.0, "accelerating but BEHIND its group — carried, not leading"),
    (10.0, 5.0, 5.0, "accelerating and level with the group is still not ahead"),
])
def test_both_legs_of_the_traction_flag_are_load_bearing(fast, short, median, why):
    """Drop either leg and the flag must go False. A name can accelerate while
    its whole group runs harder (it is being carried) and a name can lead a
    dead group while decelerating (it led LAST month)."""
    assert T.traction_read(fast, short, median)["gaining"] is False, why


def test_traction_fails_closed_on_anything_it_cannot_measure():
    """A name too young for 21 bars has no pace to beat, and a group with no
    median is no yardstick. NaN passes any `<=` gate on this project — every
    unknown must leave the number None and the flag False."""
    for args in ((None, 10.0, 5.0), (8.0, None, 5.0), (8.0, 10.0, None),
                 ("8", 10.0, 5.0), (8.0, 10.0, "5")):
        r = T.traction_read(*args)
        assert r["gaining"] is False, args
    assert T.traction_read(None, 10.0, 5.0)["traction"] is None
    assert T.traction_read(8.0, 10.0, None)["vs_group_21"] is None


def test_a_name_leading_a_falling_group_can_still_gain_traction():
    """-1% this week against a -20% month is a name whose selling stopped; if
    it is also ahead of its group that IS traction. The measure is relative by
    construction and must not be quietly floored at zero."""
    r = T.traction_read(-1.0, -20.0, -25.0)
    assert r["traction"] > 0 and r["vs_group_21"] > 0
    assert r["gaining"] is True


def test_the_ranking_puts_the_gaining_names_on_top_then_the_strongest():
    """'which ones are gaining traction' — the sort IS the answer, so it is
    pinned, and TRACTION_SPEC['sort'] prints it next to the table."""
    rows = [
        {"symbol": "COLD", "traction": 9.0, "vs_group_21": -1.0, "gaining": False},
        {"symbol": "HOT2", "traction": 0.3, "vs_group_21": 2.0, "gaining": True},
        {"symbol": "HOT1", "traction": 1.9, "vs_group_21": 1.0, "gaining": True},
        {"symbol": "NONE", "traction": None, "vs_group_21": None, "gaining": False},
        {"symbol": "COOL", "traction": -2.0, "vs_group_21": -3.0, "gaining": False},
    ]
    assert [r["symbol"] for r in sorted(rows, key=T.traction_sort_key)] == [
        "HOT1", "HOT2", "COLD", "COOL", "NONE"]
    assert T.TRACTION_SPEC["sort"].startswith("gaining desc")


def test_an_unmeasurable_name_never_sorts_as_the_hottest():
    """None is not a number — the 2026-08-31 hot-ends bug, one grain finer."""
    rows = [{"symbol": "A", "traction": None, "gaining": False},
            {"symbol": "B", "traction": -9.0, "gaining": False}]
    assert [r["symbol"] for r in sorted(rows, key=T.traction_sort_key)] == ["B", "A"]
    T.traction_sort_key({})          # total: no input raises


# ═══════════════════════════════════════════════════════════════════════════
# 3 · vs-OWN-GROUP — measured against the group he clicked, nothing else
# ═══════════════════════════════════════════════════════════════════════════
def test_vs_group_is_measured_against_that_names_own_group():
    """The SAME name, +10% over 21 days, read inside two groups: against a
    group median of +2 it is 8 points ahead and gaining; against +14 it is 4
    behind and not. One row builder, one median argument — the group he
    clicked. Benchmarking it against the tape would print the same number in
    both popovers and hide the rotation he opened them to see."""
    stat = T.member_stats(legs(8.0, 10.0, 20.0), FRESH)
    slow = T.traction_row("SAME", stat, 2.0)
    hot = T.traction_row("SAME", stat, 14.0)
    assert slow["ret_21d"] == hot["ret_21d"] == pytest.approx(10.0, abs=0.01)
    assert slow["vs_group_21"] == pytest.approx(8.0, abs=0.02)
    assert hot["vs_group_21"] == pytest.approx(-4.0, abs=0.02)
    assert slow["gaining"] is True and hot["gaining"] is False


def test_the_tables_own_median_is_over_the_full_membership(built):
    """`median_21d_full` is the yardstick the popover shows beside the chip's
    sampled one. It must be computed over the rows in the table — lifting the
    chip's number would carry the sampling error into every vs-group figure."""
    import statistics

    table = built[T.MEMBERS_KEY]
    g = table["groups"]["sector"][SECT]
    rets = [table["by_symbol"][s]["ret_21d"] for s in g["symbols"]]
    assert g["median_21d_full"] == pytest.approx(
        round(statistics.median(rets), 2), abs=0.01)
    assert g["n_full"] == 30 and g["n_measured"] == 10


def test_each_row_prints_all_three_windows_so_the_flag_can_be_audited():
    stat = T.member_stats(legs(4.0, 9.0, 25.0), FRESH)
    row = T.traction_row("A", stat, 5.0)
    assert row["ret_5d"] == pytest.approx(4.0, abs=0.01)
    assert row["ret_21d"] == pytest.approx(9.0, abs=0.01)
    assert row["ret_63d"] == pytest.approx(25.0, abs=0.01)
    assert {"symbol", "last_close", "pace_5", "pace_21", "traction",
            "vs_group_21", "gaining", "at_demand"} <= set(row)


# ═══════════════════════════════════════════════════════════════════════════
# 4 · NEGATIVE — a name that could not be priced is COUNTED, never absent
# ═══════════════════════════════════════════════════════════════════════════
def test_a_member_with_no_frame_is_not_priceable():
    assert T.member_stats([], FRESH) is None
    assert T.member_stats(None, FRESH) is None


def test_a_stale_frame_is_not_priceable_rather_than_read_as_flat():
    """Decision 4, one grain finer. MRO's last bar is 2024-11-21 (acquired by
    COP): a naive return off a dead frame is exactly 0.0%, which would park a
    delisted name mid-table looking merely quiet."""
    dead = bars([("2024-11-20", 28.0), ("2024-11-21", 28.55)])
    assert T.is_stale(dead, FRESH) is True
    assert T.member_stats(dead, FRESH) is None


def test_a_name_too_young_for_a_window_keeps_its_row_with_a_blank_number():
    """A recent IPO is a real member of the sector. It must appear — with None
    in the columns it cannot fill, never a number invented off its first
    bar — and it must not rank as gaining."""
    stat = T.member_stats(frame(n=9, last=140.0), FRESH)
    assert stat is not None and stat["ret_5d"] is not None
    assert stat["ret_21d"] is None and stat["ret_63d"] is None
    row = T.traction_row("IPO", stat, 5.0)
    assert row["traction"] is None and row["gaining"] is False


def test_unpriceable_members_are_counted_and_named_never_silently_absent():
    """Fail closed and count what you drop. A group that lists 4 names and
    shows 2 rows with no explanation reads as a group with 2 stocks."""
    frames = {"LIVE1": legs(2.0, 5.0, 9.0), "LIVE2": legs(1.0, 4.0, 8.0),
              "DEAD": bars([("2024-11-21", 28.55)])}
    table = T._member_table(
        {"sector": {"Energy": ["LIVE1", "LIVE2", "DEAD", "NOFRAME"]}},
        {"sector": {"Energy": {"median_21d": 4.5, "n": 2}}},
        {}, frames, FRESH)
    g = table["groups"]["sector"]["Energy"]
    assert g["n_full"] == 4
    assert g["priced"] == 2 and g["unpriced"] == 2
    assert g["priced"] + g["unpriced"] == g["n_full"], "the totals must add up"
    assert g["unpriced_symbols"] == ["DEAD", "NOFRAME"]
    assert g["symbols"] == ["LIVE1", "LIVE2"]
    assert table["coverage"]["unpriced"] == 2
    assert "DEAD" in table["coverage"]["unpriced_symbols"]


def test_a_group_where_nothing_could_be_priced_still_reports_its_size():
    frames = {"DEAD": bars([("2024-11-21", 28.55)])}
    table = T._member_table({"sector": {"Ghost": ["DEAD"]}},
                            {"sector": {"Ghost": {"median_21d": None, "n": 0}}},
                            {}, frames, FRESH)
    g = table["groups"]["sector"]["Ghost"]
    assert g["symbols"] == [] and g["priced"] == 0
    assert g["n_full"] == 1 and g["unpriced"] == 1
    assert g["median_21d_full"] is None


def test_a_group_that_did_not_survive_upstream_ships_no_orphan_table():
    """The table is built off the rows that SURVIVED the member floor and the
    dead-ticker drops, so the payload can never carry a table for a chip that
    is not on the strip."""
    frames = {"A": legs(2.0, 5.0, 9.0)}
    table = T._member_table({"sector": {"Shown": ["A"], "Dropped": ["A"]}},
                            {"sector": {"Shown": {"median_21d": 5.0, "n": 1}}},
                            {}, frames, FRESH)
    assert set(table["groups"]["sector"]) == {"Shown"}


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE ENDPOINT — reads the persisted build, NEVER triggers one
# ═══════════════════════════════════════════════════════════════════════════
class FakeColl:
    """Dict-backed stand-in — same shape as tests/test_context_refresh.py."""

    def __init__(self):
        self.docs = {}

    def update_one(self, flt, update, upsert=False):
        self.docs[flt["_id"]] = dict(update["$set"])

    def find_one(self, flt):
        d = self.docs.get(flt["_id"])
        return dict(d) if d else None


BY_SYMBOL = {
    "AAA": {"last_close": 100.0, "ret_5d": 8.0, "ret_21d": 10.0, "ret_63d": 20.0,
            "sector": "Technology", "industry": "Semiconductors",
            "at_demand": True, "zone_role": "demand", "zone_depth_pct": -1.2,
            "zone_off_floor_pct": 3.4},
    "BBB": {"last_close": 50.0, "ret_5d": 1.0, "ret_21d": 5.0, "ret_63d": 9.0,
            "sector": "Technology", "at_demand": False},
    "CCC": {"last_close": 20.0, "ret_5d": -3.0, "ret_21d": 1.0, "ret_63d": 4.0,
            "sector": "Technology", "at_demand": None},
}


def stored_table():
    return {
        "as_of": FRESH,
        "windows": {"fast": T.WINDOW_FAST, "short": T.WINDOW_SHORT, "med": T.WINDOW_MED},
        "traction": T.TRACTION_SPEC,
        "zone": {"day": FRESH, "covered": 2, "unmarked": 1, "at_demand": 1,
                 "source": "zone_store", "error": None},
        "coverage": {"symbols": 4, "priced": 3, "unpriced": 1,
                     "unpriced_symbols": ["DEAD"]},
        "by_symbol": dict(BY_SYMBOL),
        "groups": {
            "cohort": {"Technology · large caps": {
                "median_21d": 5.0, "n_measured": 2, "n_population": 2,
                "median_21d_full": 5.0,
                "n_full": 4, "priced": 3, "unpriced": 1,
                "unpriced_symbols": ["DEAD"], "at_demand": 1, "zone_unmarked": 1,
                "symbols": ["AAA", "BBB", "CCC"]}},
            # The same names inside a HOTTER group — its own median, its own
            # verdict. Nothing about AAA changed; the group it is read in did.
            "industry": {"Semiconductors": {
                "median_21d": 14.0, "n_measured": 3, "n_population": 3,
                "median_21d_full": 14.0,
                "n_full": 3, "priced": 3, "unpriced": 0, "unpriced_symbols": [],
                "at_demand": 1, "zone_unmarked": 1,
                "symbols": ["AAA", "BBB", "CCC"]}},
            "sector": {"Empty sector": {
                "median_21d": None, "n_measured": 0, "median_21d_full": None,
                "n_full": 12, "priced": 0, "unpriced": 12,
                "unpriced_symbols": ["D1", "D2"], "at_demand": 0,
                "zone_unmarked": 0, "symbols": []}},
        },
        "note": T.MEMBER_NOTE,
    }


@pytest.fixture(autouse=True)
def _cold_caches(monkeypatch):
    """Every endpoint test starts with both API caches empty — `_cache` is the
    /rotation build cache, `_members_cache` the popover's own 5-minute read."""
    monkeypatch.setattr(RA, "_cache", {})
    monkeypatch.setattr(RA, "_members_cache", {})


@pytest.fixture
def no_build(monkeypatch):
    """A spy on every path that could cost seconds. The popover fires on a
    CLICK; a cold `tracker.build()` measured ~29.5 s and one sector's full
    member load 7.82 s at WORKERS=8. Neither may run in this request."""
    calls = []
    monkeypatch.setattr(T, "build", lambda *a, **k: calls.append("build") or {})
    monkeypatch.setattr(T, "_load", lambda *a, **k: calls.append("_load") or {})
    monkeypatch.setattr(T, "_member_table",
                        lambda *a, **k: calls.append("_member_table") or {})
    monkeypatch.setattr(T, "_zone_marks",
                        lambda *a, **k: calls.append("_zone_marks") or ({}, {}))
    return calls


@pytest.fixture
def coll(monkeypatch):
    c = FakeColl()
    monkeypatch.setattr(MC, "_coll", lambda x=None: c)
    return c


def _members(**kw):
    resp = asyncio.run(RA.rotation_members(**kw))
    return resp.status_code, json.loads(resp.body)


def _save(coll, payload):
    MC.save_doc(MC.ROTATION_ID, payload, coll=coll)


def test_the_endpoint_serves_the_persisted_table_and_builds_nothing(coll, no_build):
    _save(coll, {"start": RA.DEFAULT_START, T.MEMBERS_KEY: stored_table()})
    status, body = _members(grain="cohort", group="Technology · large caps")

    assert no_build == [], f"the click triggered work: {no_build}"
    assert status == 200
    assert [r["symbol"] for r in body["rows"]] == ["AAA", "BBB", "CCC"]
    assert body["n"] == 3 and body["shown"] == 3 and body["gaining"] == 1
    assert body["rows"][0]["gaining"] is True
    assert body["source"] == "scan" and body["built_at_iso"]
    assert body["stale"] is False and body["age_sec"] < 5
    assert body.get("reason") in (None, "")
    assert body["traction"] == T.TRACTION_SPEC and body["note"] == T.MEMBER_NOTE


def test_the_endpoint_never_builds_even_when_asked_twice(coll, no_build):
    """The second click inside 5 minutes is served from `_members_cache` —
    still no build, and still the same answer."""
    _save(coll, {T.MEMBERS_KEY: stored_table()})
    first = _members(grain="cohort", group="Technology · large caps")[1]
    coll.docs.clear()                       # the doc is gone; the cache is not
    second = _members(grain="cohort", group="Technology · large caps")[1]
    assert no_build == []
    assert [r["symbol"] for r in second["rows"]] == [r["symbol"] for r in first["rows"]]


def test_the_endpoint_prints_both_populations_and_reconciles_neither(coll, no_build):
    _save(coll, {T.MEMBERS_KEY: stored_table()})
    _, body = _members(grain="cohort", group="Technology · large caps")
    assert body["sampled"] is True
    assert body["n_measured"] == 2 and body["n_full"] == 4
    assert body["median_21d"] == 5.0 and body["median_21d_full"] == 5.0
    assert "2-name sample" in body["median_note"]
    assert "all 4 members" in body["median_note"]
    assert body["priced"] == 3 and body["unpriced"] == 1
    assert body["unpriced_symbols"] == ["DEAD"]


def test_the_vs_group_figure_is_recomputed_against_the_GROUP_THAT_WAS_OPENED(coll, no_build):
    """The same three names, two groups, two medians. AAA is +5 ahead and
    gaining inside the cohort and -4 behind and not gaining inside the hotter
    industry. If the endpoint reached for any other median — the chip's, the
    benchmark's, another group's — both popovers would print one number."""
    _save(coll, {T.MEMBERS_KEY: stored_table()})
    _, cohort = _members(grain="cohort", group="Technology · large caps")
    _, industry = _members(grain="industry", group="Semiconductors")

    a_cohort = next(r for r in cohort["rows"] if r["symbol"] == "AAA")
    a_industry = next(r for r in industry["rows"] if r["symbol"] == "AAA")
    assert a_cohort["ret_21d"] == a_industry["ret_21d"] == 10.0
    assert a_cohort["vs_group_21"] == pytest.approx(5.0)
    assert a_industry["vs_group_21"] == pytest.approx(-4.0)
    assert a_cohort["gaining"] is True and a_industry["gaining"] is False
    assert cohort["gaining"] == 1 and industry["gaining"] == 0


def test_limit_trims_the_list_without_lying_about_its_size(coll, no_build):
    _save(coll, {T.MEMBERS_KEY: stored_table()})
    _, body = _members(grain="cohort", group="Technology · large caps", limit=2)
    assert body["shown"] == 2 and len(body["rows"]) == 2
    assert body["n"] == 3, "the full count survives the trim"


def test_a_missing_persisted_doc_returns_empty_WITH_A_REASON_and_no_build(coll, no_build):
    """NEGATIVE, and the important one. With nothing persisted the endpoint
    must answer 200 with an empty list AND a plain-language reason — never a
    503 the popover swallows, and never a 30-second build on a click."""
    status, body = _members(grain="cohort", group="Technology · large caps")
    assert no_build == [], f"a missing doc triggered work: {no_build}"
    assert status == 200
    assert body["rows"] == [] and body["n"] == 0
    assert isinstance(body.get("reason"), str) and body["reason"].strip()
    assert "scan" in body["reason"].lower(), "the reason must name who writes it"
    assert body["traction"] == T.TRACTION_SPEC and body["note"] == T.MEMBER_NOTE


def test_a_build_that_predates_the_member_table_says_so(coll, no_build):
    """The persisted doc from before this feature has no `members` key. That
    is a stale-build message, not an empty sector."""
    _save(coll, {"start": RA.DEFAULT_START, "sectors": []})
    status, body = _members(grain="cohort", group="Technology · large caps")
    assert no_build == [] and status == 200
    assert body["rows"] == [] and "predates" in body["reason"]


def test_an_unknown_group_says_so_and_names_what_it_does_have(coll, no_build):
    _save(coll, {T.MEMBERS_KEY: stored_table()})
    status, body = _members(grain="cohort", group="Nonexistent · large caps")
    assert no_build == [] and status == 200
    assert body["rows"] == [] and body["n"] == 0
    assert "no member table" in body["reason"]
    assert body["known_groups"] == ["Technology · large caps"]
    assert body["group"] == "Nonexistent · large caps"


def test_an_unknown_grain_and_a_blank_group_are_refused_without_a_build(coll, no_build):
    _save(coll, {T.MEMBERS_KEY: stored_table()})
    status, body = _members(grain="planet", group="Technology · large caps")
    assert status == 400 and body["reason"] == "unknown grain"
    assert body["grains"] == list(T.MEMBER_GRAINS)
    status, body = _members(grain="cohort", group="   ")
    assert status == 400 and body["reason"] == "no group asked for"
    assert no_build == []


def test_a_group_nobody_could_price_says_why_instead_of_looking_empty(coll, no_build):
    """12 members, none priceable. An empty `rows` with no explanation reads
    as a sector with no stocks."""
    _save(coll, {T.MEMBERS_KEY: stored_table()})
    status, body = _members(grain="sector", group="Empty sector")
    assert status == 200 and body["rows"] == []
    assert body["n_full"] == 12 and body["priced"] == 0 and body["unpriced"] == 12
    assert "could be priced" in body["reason"] and "12" in body["reason"]
    assert body["unpriced_symbols"] == ["D1", "D2"]


def test_a_dead_mongo_returns_the_reason_not_an_exception(monkeypatch, no_build):
    class BrokenColl(FakeColl):
        def find_one(self, *a, **k):
            raise RuntimeError("mongo down")

    monkeypatch.setattr(MC, "_coll", lambda x=None: BrokenColl())
    status, body = _members(grain="cohort", group="Technology · large caps")
    assert no_build == [] and status == 200
    assert body["rows"] == [] and isinstance(body.get("reason"), str)


def test_a_day_old_table_is_served_WITH_its_age_rather_than_withheld(coll, no_build):
    """The popover is a read of a daily build. A stale table is worth showing
    as long as it is stamped — but `stale` must say so, and the endpoint must
    still not build a fresh one to hide it."""
    _save(coll, {T.MEMBERS_KEY: stored_table()})
    coll.docs[MC.ROTATION_ID]["built_at"] = time.time() - 2 * 86400
    status, body = _members(grain="cohort", group="Technology · large caps")
    assert no_build == [] and status == 200
    assert len(body["rows"]) == 3
    assert body["stale"] is True and body["age_sec"] > 86400


# ═══════════════════════════════════════════════════════════════════════════
# 6 · THE DEMAND MARKER — one shared definition, and it degrades alone
# ═══════════════════════════════════════════════════════════════════════════
ZONE_DOC = {
    "symbol": "AAA", "prev_close": 21.0, "atr14": 0.5,
    "bands": [{"kind": "demand", "lo": 19.0, "hi": 21.0, "touches": 3,
               "strength": 80}],
    "recent": [{"date": "2026-09-08", "low": 19.5, "close": 20.0, "high": 20.4},
               {"date": "2026-09-09", "low": 19.6, "close": 20.2, "high": 20.8}],
}


def test_the_marker_is_the_shared_bounce_room_read_not_a_second_definition():
    """`in_demand_read` decides what "at demand" means everywhere else on this
    app — the SEPA 🪃 chip, the demand board, the phone's zone kinds. The
    popover must not grow a third opinion. 20.20 sits inside 19.00-21.00;
    22.50 is above the band top and therefore NOT inside it."""
    marks, meta = T._zone_marks({"AAA": 20.2}, day=FRESH, docs={"AAA": ZONE_DOC})
    assert marks["AAA"]["at_demand"] is True
    assert marks["AAA"]["zone_role"] == "demand"
    assert marks["AAA"]["zone_off_floor_pct"] == pytest.approx(6.32, abs=0.01)
    assert meta["source"] == "zone_store" and meta["at_demand"] == 1

    above, _ = T._zone_marks({"AAA": 22.5}, day=FRESH, docs={"AAA": ZONE_DOC})
    assert above["AAA"]["at_demand"] is False


def test_no_zone_coverage_is_UNMARKED_not_a_false_reading():
    """Only part of the universe has zone coverage. Absence of a doc is not
    "this name is not at demand" — printing False there would be a claim the
    app never measured. Unmarked names are COUNTED in the meta."""
    marks, meta = T._zone_marks({"AAA": 20.2, "NOZONE": 10.0}, day=FRESH,
                                docs={"AAA": ZONE_DOC})
    assert "NOZONE" not in marks
    assert meta["covered"] == 1 and meta["unmarked"] == 1
    row = T.traction_row("NOZONE", {"ret_5d": 1.0, "ret_21d": 2.0}, 1.0)
    assert row["at_demand"] is None


def test_a_tombstone_doc_is_not_coverage():
    """`bounce_room.load_docs` returns tombstones carrying "error" for names it
    could not build. Marking those "not at demand" would print a measurement
    that was never made."""
    marks, meta = T._zone_marks({"AAA": 20.2}, day=FRESH,
                                docs={"AAA": {"error": "engine error"}})
    assert marks == {} and meta["unmarked"] == 1


def test_a_zone_read_failure_degrades_the_MARKER_ONLY(monkeypatch):
    """He clicked a sector to see its stocks; a zone-store outage must not
    take the stock list with it. Every name goes unmarked, the meta says why,
    and the members still come back."""
    from supply_demand import bounce_room as BR

    monkeypatch.setattr(BR, "load_docs", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("zone store down")))
    marks, meta = T._zone_marks({"AAA": 20.2}, day=FRESH)
    assert marks == {}
    assert meta["source"] == "unavailable" and "zone store down" in meta["error"]

    frames = {"AAA": legs(8.0, 10.0, 20.0), "BBB": legs(1.0, 5.0, 9.0)}
    table = T._member_table({"sector": {"Tech": ["AAA", "BBB"]}},
                            {"sector": {"Tech": {"median_21d": 5.0, "n": 2}}},
                            {}, frames, FRESH)
    g = table["groups"]["sector"]["Tech"]
    assert g["symbols"] == ["AAA", "BBB"], "the member list survives the outage"
    assert g["priced"] == 2 and g["at_demand"] == 0 and g["zone_unmarked"] == 2
    assert table["zone"]["source"] == "unavailable"
    assert all(table["by_symbol"][s]["at_demand"] is None for s in ("AAA", "BBB"))


def test_a_cold_zone_store_is_a_reason_not_a_crash(monkeypatch):
    from supply_demand import zone_store as ZS

    monkeypatch.setattr(ZS, "latest_store_day", lambda *a, **k: None)
    marks, meta = T._zone_marks({"AAA": 20.2})
    assert marks == {} and meta["error"] == "zone store is cold"


def test_the_marker_reads_the_members_own_CLOSED_bar():
    """The live-bar trap (2026-09-03): a daily frame is a day stale intraday.
    The marker is read on the same last closed close as the returns beside it,
    so the two can never disagree about which session they describe."""
    bars_ = legs(8.0, 10.0, 20.0)
    stat = T.member_stats(bars_, FRESH)
    assert stat["last_close"] == pytest.approx(float(bars_[-1]["c"]), abs=0.01)
    # the same bar the returns are measured to, not a snapshot the popover
    # never saw — the next test pins that this is what reaches the zone read
    assert T.trailing_return(bars_, T.WINDOW_FAST) == pytest.approx(8.0, abs=0.01)


def test_zone_marks_is_handed_the_last_close_of_every_priced_member(monkeypatch):
    captured = {}

    def spy(closes, *a, **k):
        captured.update(closes)
        return {}, {"source": "unavailable", "error": None, "day": None,
                    "covered": 0, "unmarked": len(closes), "at_demand": 0}

    monkeypatch.setattr(T, "_zone_marks", spy)
    frames = {"AAA": legs(8.0, 10.0, 20.0), "DEAD": bars([("2024-11-21", 28.55)])}
    T._member_table({"sector": {"Tech": ["AAA", "DEAD"]}},
                    {"sector": {"Tech": {"median_21d": 5.0, "n": 1}}},
                    {}, frames, FRESH)
    assert captured == {"AAA": pytest.approx(100.0)}, \
        "only priced members are handed to the zone read"


# ═══════════════════════════════════════════════════════════════════════════
# 7 · THE WIRE — the popover the frontend actually ships must fit this API
# ═══════════════════════════════════════════════════════════════════════════
# A source guard, in the shape of tests/test_*_contracts.py: the browser is the
# only consumer of this endpoint, and a query parameter or a payload key that
# only one side believes in is invisible until the popover renders a table of
# em dashes.
FE = Path(__file__).resolve().parents[2] / "frontend" / "src"


def _fe_text() -> str:
    return "\n".join((FE / p).read_text() for p in
                     ("lib/rotationMembers.ts", "components/SectorMembersModal.tsx"))


@pytest.mark.skipif(not (FE / "lib" / "rotationMembers.ts").exists(),
                    reason="frontend not present")
def test_the_frontend_asks_with_the_parameter_names_this_endpoint_reads():
    """`membersUrl` builds the query string the popover fires. Every key it
    sets must be a parameter `rotation_members` actually accepts — an extra
    one is silently ignored by FastAPI and the endpoint answers about the
    DEFAULT grain, which is a different group with the same label."""
    import inspect

    accepted = set(inspect.signature(RA.rotation_members).parameters)
    src = (FE / "lib" / "rotationMembers.ts").read_text()
    sent = set()
    for line in src.splitlines():
        if "URLSearchParams({" in line:
            sent |= {p.strip().split(":")[0].strip()
                     for p in line.split("{", 1)[1].split("}")[0].split(",") if p.strip()}
        if "qs.set(" in line:
            sent.add(line.split("qs.set(", 1)[1].split(",")[0].strip().strip("'\""))
    assert sent, "membersUrl must build a query string"
    unknown = {k for k in sent if k not in accepted}
    assert not unknown, (
        "the popover sends query keys /rotation/members does not read: %s "
        "(the endpoint reads %s). FastAPI IGNORES the extras, so the request "
        "silently falls back to the default grain and answers about a "
        "different group with the same label."
        % (sorted(unknown), sorted(accepted)))


@pytest.mark.skipif(not (FE / "lib" / "rotationMembers.ts").exists(),
                    reason="frontend not present")
def test_every_payload_key_the_popover_renders_is_a_key_this_endpoint_sends():
    """The panel reads these off the payload. A key only the frontend believes
    in renders as an em dash or a missing flag — a table of blanks under a
    sector he clicked, with nothing saying it failed."""
    import re

    src = _fe_text()
    body_keys = set(re.findall(r'"([a-z_0-9]+)":', Path(RA.__file__).read_text()))
    row_keys = {"symbol", "sector", "industry", "last_close", "ret_5d", "ret_21d",
                "ret_63d", "at_demand", "zone_role", "zone_depth_pct",
                "zone_off_floor_pct", "pace_5", "pace_21", "traction",
                "vs_group_21", "gaining",
                # traction_row rebases each window against the benchmark and
                # ships these three beside the raw ret_* legs.
                "rel_5d", "rel_21d", "rel_63d"}
    served = body_keys | row_keys

    # What the frontend reads OFF THE WIRE, i.e. inside normalizeMembers --
    # NOT what its own types declare. Those types describe the shape AFTER
    # translation (rows->members, gaining->traction, traction->traction_score),
    # so checking them compares the endpoint against the UI's vocabulary and
    # passes or fails for the wrong reason.
    #
    # 2026-09-10: the earlier version checked the declared types, and the
    # declared types happened to match the reader -- both invented. The suite
    # was green while normalizeMembers read `p.members` against an endpoint
    # that sends `rows`, so EVERY popover rendered zero rows in production.
    # Pin the accesses instead; that is the contract that actually breaks.
    # Scope to the FUNCTION BODY. Running to end-of-file swept in helpers
    # defined after it and flagged their locals as wire keys.
    body = re.search(r"export function normalizeMembers\(raw: unknown\)"
                     r".*?\n\}\n", src, re.S)
    assert body, "normalizeMembers not found -- the guard cannot be silently skipped"
    reads = set(re.findall(r"\bp\.([a-z_0-9]+)", body.group(0)))
    reads |= set(re.findall(r"\bm\.([a-z_0-9]+)", body.group(0)))
    reads -= {"error", "kind"}     # `error` is universal; `kind` is a request param
    missing = {k for k in reads if k not in served}
    assert not missing, (
        "the popover reads payload keys /rotation/members never sends: %s. "
        "Either the endpoint grows them or the panel stops asking — a silent "
        "em dash is the one outcome that must not ship." % sorted(missing))
