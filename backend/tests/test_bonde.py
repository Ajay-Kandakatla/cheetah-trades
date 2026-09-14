"""Bonde board — his screen as its own tab (Ajay 2026-09-13).

The negatives carry this file. Three of them pin real defects caught on the live
board before it shipped, and each produced a confident, plausible, wrong row.
"""
from __future__ import annotations

import pytest

from sepa import bonde as BD
from sepa import first_seen as FS


def scan_row(symbol, rev_series, **kw):
    return {"symbol": symbol, "name": kw.get("name"),
            "last_close": kw.get("last_close", 10.0),
            "fundamentals": {"rev_q_series": rev_series,
                             "sales": kw.get("sales") or {}}}


# ─────────────────────────────────────────── the revenue-base defect
def test_a_NEGATIVE_year_ago_base_is_refused_not_rendered_as_growth():
    """THE DBRG DEFECT, caught on the live board 2026-09-13.

    `sepa/sales.py::_yoy` divides by abs(base), so a NEGATIVE prior-year quarter
    comes back as large POSITIVE growth. DBRG read +15,961% off MINUS
    $3,207,000, and APLD +877% off MINUS $33,300,000. That is a sign flip, not a
    ramp, and it ranked above every real business on the board."""
    r = BD._rev_base(scan_row("DBRG", [508_679_000, None, None, None, -3_207_000]))
    assert r["base_state"] == "non_positive"
    assert r["rev_added"] is None          # no dollar figure off a negative base


def test_an_IMMATERIAL_base_is_flagged_because_the_percentage_is_a_ratio():
    """QUBT read +9,000% off $61,000 of quarterly revenue; FCUV +1,811% off
    $35,330. A company with $61k of quarterly revenue was pre-revenue."""
    assert BD._rev_base(scan_row("QUBT", [5_551_000, 0, 0, 0, 61_000]))["base_state"] == "too_small"
    assert BD._rev_base(scan_row("FCUV", [675_170, 0, 0, 0, 35_330]))["base_state"] == "too_small"


def test_a_REAL_base_passes_and_carries_its_dollars():
    r = BD._rev_base(scan_row("PTGX", [213_475_000, 0, 0, 0, 5_546_000]))
    assert r["base_state"] == "ok"
    assert r["rev_added"] == pytest.approx(207_929_000)


def test_NEGATIVE_the_materiality_floor_is_the_BOARDS_not_Bondes():
    """SOURCE GUARD. His 5/25/100 tiers are documented in his own writing; the
    $1M base floor is this app's, and the board must never imply otherwise."""
    assert BD.MIN_MATERIAL_BASE_REV == 1_000_000.0
    src = open(BD.__file__).read()
    assert "OWNER SETTING, NOT A BONDE NUMBER" in src
    assert "+15,961%" in src and "QUBT" in src


def test_the_order_inside_a_tier_does_NOT_rank_on_a_broken_base():
    """Every name in a tier already cleared the tier's threshold, so the order
    is this board's choice — and ranking on the raw percentage put a sign flip
    and a $61k base above a company going $5.5M -> $213M."""
    real = {"symbol": "PTGX", "base_state": "ok", "growth_yoy_pct": 3749.2,
            "sales_score": 100, "rev_added": 207_929_000}
    flip = {"symbol": "DBRG", "base_state": "non_positive", "growth_yoy_pct": 15961.5,
            "sales_score": 100, "rev_added": None}
    tiny = {"symbol": "QUBT", "base_state": "too_small", "growth_yoy_pct": 9000.0,
            "sales_score": 100, "rev_added": 5_490_000}
    assert sorted([flip, tiny, real], key=BD._sales_key)[0]["symbol"] == "PTGX"


def test_a_flagged_name_is_still_SHOWN_never_filtered_out():
    """Hiding it would make the board disagree with his screen. It must appear,
    with its numbers, simply not at the top."""
    rows = sorted([
        {"symbol": "DBRG", "base_state": "non_positive", "growth_yoy_pct": 15961.5,
         "sales_score": 100, "rev_added": None},
        {"symbol": "PTGX", "base_state": "ok", "growth_yoy_pct": 3749.2,
         "sales_score": 100, "rev_added": 207_929_000},
    ], key=BD._sales_key)
    assert {r["symbol"] for r in rows} == {"DBRG", "PTGX"}


# ─────────────────────────────────────────── the duplicate-pivot defect
def test_NEGATIVE_pivots_are_DEDUPED_to_one_row_per_symbol(monkeypatch):
    """Measured live: the stored setups returned MRNA five times, PAYS three
    and ANF twice, because each scanner pass upserts a new row. Raw, one name
    would occupy five rows and a 12-name board would look like 30.

    Patched through `setups.store` itself rather than by swapping sys.modules —
    the module is imported by other tests in the suite, so a sys.modules swap
    passes alone and fails in a full run depending on import order.
    """
    import time
    from setups import store
    now = time.time()
    rows = [{"symbol": "MRNA", "generated_at": now - 100, "meta": {"gap_pct": 9.0}},
            {"symbol": "MRNA", "generated_at": now - 10, "meta": {"gap_pct": 11.0}},
            {"symbol": "ANF", "generated_at": now - 50, "meta": {"gap_pct": 8.5}}]
    monkeypatch.setattr(store, "get_setups", lambda **kw: rows)

    out = BD._pivots()
    assert set(out) == {"MRNA", "ANF"}
    # ...and the FRESHEST row wins, not whichever came back first.
    assert out["MRNA"]["meta"]["gap_pct"] == 11.0


def test_NEGATIVE_a_STALE_pivot_is_dropped(monkeypatch):
    """Every setup kind in the app is currently stale (see regime_state) —
    newest episodic_pivot 413h old. A board that rendered those would present
    a 17-day-old gap as a live entry."""
    import time
    from setups import store
    now = time.time()
    rows = [{"symbol": "OLD", "generated_at": now - (BD.MAX_PIVOT_AGE_H + 10) * 3600,
             "meta": {"gap_pct": 12.0}}]
    monkeypatch.setattr(store, "get_setups", lambda **kw: rows)
    assert BD._pivots() == {}


# ─────────────────────────────────────────── arrivals
def test_the_FIRST_cohort_is_never_badged_as_new():
    """'We have only just started looking' must never render as 'these are
    fresh finds'. Without the __meta__ guard the first build badges everything."""
    class _Coll:
        """A Mongo stand-in that honours $setOnInsert properly.

        The first version of this fake applied $setOnInsert on EVERY call, so
        `tracking_since` advanced with each build and the strict `>` excluded
        the very arrival it was meant to catch. The fake was wrong, not the
        module — but it is exactly the mistake the real guard exists to prevent,
        so it is worth the accurate double.
        """
        def __init__(self):
            self.docs = {}

        def update_one(self, q, upd, upsert=False):
            _id = q["_id"]
            is_new = _id not in self.docs
            d = self.docs.setdefault(_id, {"_id": _id})
            if is_new:
                d.update(upd.get("$setOnInsert") or {})
            d.update(upd.get("$set") or {})

        def find_one(self, q, *a, **k):
            return self.docs.get(q.get("_id"))

        def find(self, q, *a, **k):
            gt = (q.get("first_seen") or {}).get("$gt")
            for _id, d in self.docs.items():
                if _id == FS.META_ID:
                    continue
                if gt is None or str(d.get("first_seen", "")) > str(gt):
                    yield d

    class _DB:
        def __init__(self):
            self.c = _Coll()

        def __getitem__(self, name):
            return self.c

    db = _DB()
    FS.record("t", ["AAA", "BBB"], db=db)
    assert FS.newly_found("t", days=30, db=db) == set()     # the first cohort
    import time as _t
    _t.sleep(0.01)
    FS.record("t", ["AAA", "BBB", "CCC"], db=db)
    assert FS.newly_found("t", days=30, db=db) == {"CCC"}   # only the arrival


def test_NEGATIVE_no_tracking_history_means_NO_arrivals_not_all_of_them():
    class _Empty:
        def find_one(self, *a, **k): return None
        def find(self, *a, **k): return iter(())

    class _DB:
        def __getitem__(self, name): return _Empty()
    assert FS.newly_found("t", days=30, db=_DB()) == set()


# ─────────────────────────────────────────── the regime finding
def test_the_board_EXPLAINS_an_empty_pivot_section():
    """FOUND WHILE BUILDING THIS, 2026-09-13: every setup kind in the app is
    stale because `is_bull_regime()` reads False and Ajay chose to sit out bear
    markets. An empty headline section with no explanation reads as broken."""
    note = BD.pivot_pause_note({"scanners_paused": True, "label": "market_in_correction"})
    assert "PIVOTS ARE PAUSED" in note
    assert "market in correction" in note
    assert "your own rule" in note
    # ...and nothing is said when they are running.
    assert BD.pivot_pause_note({"scanners_paused": False}) == ""
    assert BD.pivot_pause_note(None) == ""


def test_the_note_leads_with_the_FIRE_RATE_not_the_mechanics():
    """His sales gate alone describes half the market. A reader who does not
    know that reads the tier sections as a selection."""
    note = BD.note(1051, 2076, {"pivot": 12})
    assert "1,051 of 2,076" in note and "50.6%" in note
    assert "sales_confidence_methodology" in note
    # whose numbers are whose
    assert "owner settings, not numbers he published" in note


def test_the_board_RE_DERIVES_nothing():
    """SOURCE GUARD, and the point of the whole module: every rule is called
    from the module that already implements and cites it."""
    src = open(BD.__file__).read()
    assert "_bonde_pillar" in src          # the pass rule
    assert "sepa/sales.py" in src          # the tiers
    assert "episodic_pivot" in src         # the entry
    assert "NOTHING HERE RE-DERIVES BONDE" in src
