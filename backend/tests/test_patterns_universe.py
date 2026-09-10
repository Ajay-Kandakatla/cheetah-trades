"""The pattern scan's UNIVERSE — Ajay 2026-09-10:

    "The chart patterns are only looking at qualified sepa list I want them to
     run against all"

It was true twice over. `_universe_with_context()` returned early on the latest
SEPA scan's `all_results` (2,365 non-ETF names) and never reached the universe
loader, so 286 names in `load_universe("full")` (2,650) were never scanned at
all. And `_run_scan` persisted `all_found[:200]` against a live `n_found` of
239 — with the sort putting confirmed-and-candidate first, the 39 it dropped on
the floor were disproportionately the NON-qualifiers he was asking for, and
`pattern_alerts` reads exactly that capped list.

These tests pin the widened universe and the honest cap. They must not hit
Mongo or a provider: `sepa.scanner` / `sepa.universe` / `_scan_symbol` are all
faked, so what is exercised is the universe algebra and the payload accounting,
not the detectors (those live in `test_patterns.py`).

WHAT THIS FILE DELIBERATELY DOES NOT TEST: the phone. Widening the scan widens
the BOARD. Two gates still stand between a pattern and a push — the $1B zone
floor (`zone_store.MIN_CAP_USD`, his own standing rule) and the demand-band
gate (`patterns/pattern_alerts.py`, docs/supply_demand/pattern_demand_gate.md).
Both are pinned in `test_patterns_contracts.py` so that widening the scan can
never be mistaken for loosening a gate.
"""
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# patterns/scan imports pandas + detector at module load (py3.9 host lacks
# pandas) — stub before import, like the other pattern tests.
for name in ("pandas",):
    try:
        __import__(name)
    except ImportError:
        sys.modules[name] = types.ModuleType(name)
try:
    from patterns import detector  # noqa: F401
except Exception:
    stub = types.ModuleType("patterns.detector")
    stub.VALIDATION_HORIZON = 21
    stub.DETECTORS = {}
    sys.modules["patterns.detector"] = stub

from patterns import scan


# ── fakes ────────────────────────────────────────────────────────────────────

def _row(sym, rs=50, candidate=False, buyable=False, etf=False):
    """One `all_results` row, shaped like sepa.scanner writes it."""
    return {"symbol": sym, "rs_rank": rs, "score": 60.0, "stage": {"stage": 2},
            "is_candidate": candidate, "is_buyable": buyable, "is_etf": etf}


class _Boom(RuntimeError):
    pass


def _sepa_modules(rows=None, universe=None, scan_raises=False,
                  universe_raises=False, extras=None):
    """A fake `sepa` package for mock.patch.dict(sys.modules, ...).

    `rows` is the latest SEPA scan's all_results; `universe` is what
    load_universe returns. Either side can be made to raise so the fallback
    paths are exercised without a provider or a database.
    """
    def load_latest():
        if scan_raises:
            raise _Boom("no scan doc")
        return {"all_results": list(rows or [])}

    def load_universe(mode=None):
        if universe_raises:
            raise _Boom("universe file missing")
        return list(universe or [])

    sepa = types.ModuleType("sepa")
    scanner = types.SimpleNamespace(load_latest=load_latest)
    universe_mod = types.SimpleNamespace(load_universe=load_universe,
                                         RS_ANCHORS=("SPY", "QQQ", "IWM"))
    sepa.scanner = scanner
    sepa.universe = universe_mod
    mods = {"sepa": sepa, "sepa.scanner": scanner, "sepa.universe": universe_mod}
    for k, v in (extras or {}).items():
        setattr(sepa, k.split(".")[-1], v)
        mods["sepa." + k.split(".")[-1]] = v
    return mods


class _FakeColl:
    """In-memory stand-in for the patterns_scan collection (tests/conftest.py
    refuses a real MongoClient)."""

    def __init__(self):
        self.docs = {}

    def update_one(self, flt, update, upsert=False):
        self.docs.setdefault(flt["_id"], {}).update(update["$set"])


# ── the universe itself ──────────────────────────────────────────────────────

class TestUniverseWithContext(unittest.TestCase):
    ROWS = [_row("AAA", rs=91, candidate=True, buyable=True),
            _row("BBB", rs=40)]
    FULL = ["AAA", "BBB", "ZZZZ"]          # ZZZZ = the name the SEPA scan misses

    def test_full_universe_name_absent_from_the_sepa_scan_is_still_scanned(self):
        """DEFECT 1. `ZZZZ` is in load_universe("full") and NOT in the SEPA
        scan's all_results. Before the fix the function returned on the SEPA
        rows and never looked; it must now be in the symbol list."""
        with mock.patch.dict(sys.modules, _sepa_modules(self.ROWS, self.FULL)):
            symbols, ctx = scan._universe_with_context()
        self.assertIn("ZZZZ", symbols)
        # ...and it carries an EMPTY SEPA context rather than being dropped for
        # not having one. `_run_scan` does `ctx.get(sym) or {}`, so absent and
        # empty are the same thing downstream; both are acceptable, a
        # KeyError-shaped surprise is not.
        self.assertIn(ctx.get("ZZZZ", {}), ({}, None))
        self.assertEqual(ctx.get("ZZZZ") or {}, {})

    def test_the_union_is_the_union_not_either_side(self):
        """Neither list is allowed to win outright: the scan sweeps both."""
        with mock.patch.dict(sys.modules, _sepa_modules(self.ROWS, self.FULL)):
            symbols, _ = scan._universe_with_context()
        self.assertEqual(set(symbols), {"AAA", "BBB", "ZZZZ"})
        self.assertEqual(len(symbols), len(set(symbols)), "no duplicate scans")

    def test_sepa_context_still_attached_for_names_the_scan_knows(self):
        """Widening must not cost the context — the board's rank/stage/candidate
        chips and the scan's own sort read it."""
        with mock.patch.dict(sys.modules, _sepa_modules(self.ROWS, self.FULL)):
            _, ctx = scan._universe_with_context()
        self.assertEqual(ctx["AAA"]["rs_rank"], 91)
        self.assertEqual(ctx["AAA"]["stage"], 2)
        self.assertTrue(ctx["AAA"]["is_candidate"])
        self.assertTrue(ctx["AAA"]["is_buyable"])
        self.assertFalse(ctx["BBB"]["is_candidate"])

    def test_etfs_the_sepa_scan_flagged_stay_out(self):
        """NEGATIVE. load_universe appends the RS benchmarks (SPY/QQQ/IWM) and
        carries ETFs; the board is a stock-pattern board and always dropped
        `is_etf` rows. Widening the net must not sweep them back in."""
        rows = self.ROWS + [_row("SPY", etf=True)]
        with mock.patch.dict(sys.modules, _sepa_modules(rows, self.FULL + ["SPY"])):
            symbols, ctx = scan._universe_with_context()
        self.assertNotIn("SPY", symbols)
        self.assertNotIn("SPY", ctx)

    def test_rs_anchors_stay_out_even_though_no_scan_row_flags_them(self):
        """REGRESSION (2026-09-10, caught on the first dry run of the widening).

        The `is_etf` filter can only see names the SEPA scan ROWED. SPY, QQQ
        and IWM are carried in every universe for the RS math and are never
        scanned, so they carry no row and no flag — and the first run of the
        widened sweep duly returned all three as pattern candidates. The test
        above passes for the wrong reason: it hands SPY to the scan AS an
        is_etf row, which was never the broken case. This is the broken case."""
        full = self.FULL + ["SPY", "QQQ", "IWM"]
        with mock.patch.dict(sys.modules, _sepa_modules(self.ROWS, full)):
            symbols, _ = scan._universe_with_context()
        for anchor in ("SPY", "QQQ", "IWM"):
            self.assertNotIn(anchor, symbols)
        # and the widening it guards still happened
        self.assertIn("ZZZZ", symbols)

    def test_a_universe_module_without_rs_anchors_still_widens(self):
        """NEGATIVE. The anchor list is read with getattr precisely so an older
        or stubbed sepa.universe costs us the three anchors and NOT the whole
        2,650-name widening. A hard from-import here cost exactly that."""
        mods = _sepa_modules(self.ROWS, self.FULL)
        del mods["sepa.universe"].RS_ANCHORS
        with mock.patch.dict(sys.modules, mods):
            symbols, _ = scan._universe_with_context()
        self.assertIn("ZZZZ", symbols)

    def test_falls_back_to_the_sepa_rows_when_the_universe_loader_dies(self):
        """NEGATIVE. A missing/corrupt universe file must degrade to the SEPA
        rows — a narrower scan, never a blank one."""
        with mock.patch.dict(sys.modules,
                             _sepa_modules(self.ROWS, self.FULL, universe_raises=True)):
            symbols, ctx = scan._universe_with_context()
        self.assertEqual(set(symbols), {"AAA", "BBB"})
        self.assertEqual(ctx["AAA"]["rs_rank"], 91)

    def test_falls_back_to_the_universe_when_the_sepa_scan_is_missing(self):
        """NEGATIVE. The mirror case: no SEPA scan doc yet (fresh container).
        Every name is scanned with an empty context — the patterns board does
        not depend on SEPA having run."""
        with mock.patch.dict(sys.modules,
                             _sepa_modules(self.ROWS, self.FULL, scan_raises=True)):
            symbols, ctx = scan._universe_with_context()
        self.assertEqual(set(symbols), set(self.FULL))
        self.assertEqual(ctx, {})

    def test_both_sides_failing_returns_empty_and_does_not_throw(self):
        """NEGATIVE, fail-closed. Both sources down → ([], {}). `_run_scan`
        turns that into a loud `no universe` error rather than a silent
        zero-symbol 'quiet market' scan that overwrites a good doc."""
        with mock.patch.dict(sys.modules,
                             _sepa_modules(scan_raises=True, universe_raises=True)):
            symbols, ctx = scan._universe_with_context()
        self.assertEqual((symbols, ctx), ([], {}))


# ── the results cap ──────────────────────────────────────────────────────────

class TestResultsCap(unittest.TestCase):
    """DEFECT 2. `results = all_found[:200]` against n_found=239 silently threw
    39 hits away, and the sort ahead of it (confirmed → is_candidate → rs_rank)
    meant the discards skewed NON-qualifier: exactly the names he asked for.
    ~600 B/row means 2,000 rows is 1.2 MB against Mongo's 16 MB — the cap is a
    guard rail, not a budget."""

    def _run(self, n_hits):
        found = [{"symbol": "S%04d" % i, "pattern": "double_bottom",
                  "status": "confirmed" if i % 2 else "forming"}
                 for i in range(n_hits)]
        symbols = [p["symbol"] for p in found]
        coll = _FakeColl()

        def fake_scan_symbol(sym):
            hit = next(p for p in found if p["symbol"] == sym)
            return {"symbol": sym, "found": [dict(hit)], "outcomes": {}}

        mods = _sepa_modules([_row(s) for s in symbols], symbols)
        with mock.patch.dict(sys.modules, mods), \
             mock.patch.object(scan, "_scan_symbol", fake_scan_symbol), \
             mock.patch.object(scan, "_coll", lambda: coll):
            scan._run_scan()
        self.assertIsNone(scan.status().get("error"))
        return coll.docs["latest"]           # doc id is NOT allowed to move

    def test_over_the_cap_records_what_it_dropped(self):
        """NEGATIVE. A cap that trims in silence is a blind board. n_found stays
        the HONEST pre-cap total and the drop is counted and reportable."""
        payload = self._run(scan.MAX_RESULTS + 25)
        self.assertEqual(payload["n_found"], scan.MAX_RESULTS + 25)
        self.assertEqual(len(payload["results"]), scan.MAX_RESULTS)
        self.assertEqual(payload["n_dropped"], 25)
        self.assertEqual(payload["n_dropped"],
                         payload["n_found"] - len(payload["results"]))
        # The payload alone has to be enough to recognise a truncated board —
        # what it kept, and the cap it kept it under.
        self.assertEqual(payload["n_results"], len(payload["results"]))
        self.assertEqual(payload["max_results"], scan.MAX_RESULTS)

    def test_the_cap_never_truncates_to_nothing(self):
        """NEGATIVE. An off-by-one or a falsy MAX_RESULTS turning `results` into
        [] would read on the board as 'no patterns today' — the failure mode
        that must never be quiet."""
        payload = self._run(scan.MAX_RESULTS + 25)
        self.assertTrue(payload["results"])
        self.assertEqual(len(payload["results"]), scan.MAX_RESULTS)

    def test_under_the_cap_keeps_everything_and_reports_zero_dropped(self):
        """The ordinary day: today's 239 hits all persist, drop count is 0 —
        present, not omitted, so the field can be rendered unconditionally."""
        payload = self._run(239)
        self.assertEqual(payload["n_found"], 239)
        self.assertEqual(len(payload["results"]), 239)
        self.assertEqual(payload["n_dropped"], 0)

    def test_symbols_scanned_reports_the_widened_universe(self):
        """The counter that proves the sweep was wide: it is the symbol count,
        not the hit count, and it is what a 'did it really run against all?'
        question is answered from. `symbols_with_sepa_ctx` splits it — the rest
        are the universe-only names that were invisible before 2026-09-10."""
        payload = self._run(300)
        self.assertEqual(payload["symbols_scanned"], 300)
        self.assertEqual(payload["symbols_with_sepa_ctx"], 300)   # all fake rows carry ctx

    def test_universe_only_names_are_counted_as_such(self):
        """NEGATIVE-ish: a sweep where the SEPA scan is missing must report ZERO
        names with context and still scan every symbol — the difference between
        the two counters is the answer to 'how much wider did it get?'."""
        symbols = ["S%04d" % i for i in range(10)]
        coll = _FakeColl()
        with mock.patch.dict(sys.modules,
                             _sepa_modules(universe=symbols, scan_raises=True)), \
             mock.patch.object(scan, "_scan_symbol", lambda s: None), \
             mock.patch.object(scan, "_coll", lambda: coll):
            scan._run_scan()
        payload = coll.docs["latest"]
        self.assertEqual(payload["symbols_scanned"], 10)
        self.assertEqual(payload["symbols_with_sepa_ctx"], 0)
        self.assertEqual(payload["n_found"], 0)
        self.assertEqual(payload["n_dropped"], 0)


# ── the verdict universe (the 📐 chips) ──────────────────────────────────────

class TestVerdictUniverse(unittest.TestCase):
    """DEFECT 3. `_verdict_universe()` was qualifiers ∪ holdings ∪ buyable ∪
    at_pivot ∪ leader — 313 names against a SEPA page listing 2,365 rows, so a
    📐 chip was BLANK on every row outside those 313. It now spans the full
    universe; every existing source tag must survive that."""

    ROWS = [_row("QUAL", rs=88, candidate=True),
            _row("BUY", rs=95, candidate=True, buyable=True),
            _row("PLAIN", rs=30)]
    FULL = ["QUAL", "BUY", "PLAIN", "OUTSIDER"]

    def _universe(self):
        holdings = types.SimpleNamespace(
            list_holdings=lambda owner: [{"ticker": "HELD"}])
        portfolio = types.ModuleType("portfolio")
        portfolio.store = holdings
        at_pivot = types.SimpleNamespace(
            get_at_pivot=lambda: {"rows": [{"symbol": "PIVOT", "is_etf": False},
                                           {"symbol": "SPY", "is_etf": True}]})
        leaderboard = types.SimpleNamespace(
            leaderboard=lambda n=12: {"leaders": [{"symbol": "LEAD"}]})
        mods = _sepa_modules(self.ROWS, self.FULL,
                             extras={"at_pivot": at_pivot,
                                     "leaderboard": leaderboard})
        mods.update({"portfolio": portfolio, "portfolio.store": holdings})
        with mock.patch.dict(sys.modules, mods):
            return scan._verdict_universe()

    def test_every_existing_source_tag_survives(self):
        """The Portfolio / Leaderboard cross-links render off these strings
        (SOURCE_META in PatternsPage.tsx). Renaming or dropping one blanks a
        chip, so they are pinned by name."""
        u = self._universe()
        self.assertIn("qualifier", u["QUAL"]["sources"])
        self.assertIn("buyable", u["BUY"]["sources"])
        self.assertIn("qualifier", u["BUY"]["sources"])
        self.assertIn("holding", u["HELD"]["sources"])
        self.assertIn("at_pivot", u["PIVOT"]["sources"])
        self.assertIn("leader", u["LEAD"]["sources"])

    def test_a_plain_universe_name_is_covered_and_tagged_universe(self):
        """The fix for the blank chip: a name that is nothing but a member of
        the full universe still gets a verdict row, under its own tag so the
        board can tell 'in the sweep' from 'a qualifier'."""
        u = self._universe()
        self.assertIn("OUTSIDER", u)
        self.assertIn("universe", u["OUTSIDER"]["sources"])
        self.assertEqual(u["OUTSIDER"]["ctx"], {})

    def test_a_non_qualifier_the_sepa_scan_knows_keeps_its_context(self):
        """PLAIN is in the SEPA scan but qualifies for nothing. It is now
        covered, and its rank/stage ride along."""
        u = self._universe()
        self.assertIn("PLAIN", u)
        self.assertIn("universe", u["PLAIN"]["sources"])
        self.assertEqual(u["PLAIN"]["ctx"]["rs_rank"], 30)

    def test_at_pivot_etfs_still_excluded(self):
        """NEGATIVE. The is_etf skip in the at_pivot branch predates this
        change and must outlive it."""
        self.assertNotIn("SPY", self._universe())

    def test_sources_never_duplicate(self):
        """A name reachable two ways (BUY is both qualifier and buyable, and is
        also a plain universe member) records each tag once — the chip row is
        rendered straight off this list."""
        u = self._universe()
        for sym, entry in u.items():
            self.assertEqual(len(entry["sources"]), len(set(entry["sources"])),
                             "duplicate source tag on %s" % sym)


if __name__ == "__main__":
    unittest.main()
