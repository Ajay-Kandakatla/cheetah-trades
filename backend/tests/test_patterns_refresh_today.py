"""Rescan-with-today's-data wiring (Ajay 2026-06-11). The scan must call
patch_latest_closes ONLY when refresh_today is set, and on the right symbol
set — geometry still uses full history, this only freshens the trigger bar.
No network; the scan worker is monkeypatched to a no-op so the test stays on
the dispatch logic."""
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


class TestRefreshTodayWiring(unittest.TestCase):
    def setUp(self):
        # Force the universe builder + actual scan body to no-ops so we only
        # exercise the refresh dispatch.
        self._u = scan._verdict_universe
        scan._verdict_universe = lambda: {"AAA": {"ctx": {}, "sources": []},
                                          "BBB": {"ctx": {}, "sources": []}}

    def tearDown(self):
        scan._verdict_universe = self._u

    def test_refresh_calls_patch_with_universe(self):
        called = {}
        fake_prices = types.SimpleNamespace(
            patch_latest_closes=lambda syms: called.setdefault("syms", list(syms)) or
            {"patched": len(syms)})
        with mock.patch.dict(sys.modules, {"sepa.prices": fake_prices,
                                           "sepa": types.ModuleType("sepa")}):
            sys.modules["sepa"].prices = fake_prices
            scan._refresh_today(["AAA", "BBB"])
        self.assertEqual(sorted(called["syms"]), ["AAA", "BBB"])

    def test_refresh_swallows_errors(self):
        def boom(_):
            raise RuntimeError("provider down")
        fake_prices = types.SimpleNamespace(patch_latest_closes=boom)
        with mock.patch.dict(sys.modules, {"sepa.prices": fake_prices,
                                           "sepa": types.ModuleType("sepa")}):
            sys.modules["sepa"].prices = fake_prices
            scan._refresh_today(["AAA"])   # must not raise — best-effort

    def test_start_scan_threads_flag(self):
        seen = {}

        def fake_qual(refresh_today=False):
            seen["refresh"] = refresh_today

        with mock.patch.object(scan, "_run_qualifier_scan", fake_qual), \
             mock.patch.object(scan.threading, "Thread") as Thread:
            # run the lambda target synchronously instead of spawning
            Thread.side_effect = lambda target, **k: types.SimpleNamespace(
                start=target, daemon=True)
            scan._STATE["running"] = False
            scan.start_scan("qualifiers", refresh_today=True)
        self.assertTrue(seen.get("refresh"))


if __name__ == "__main__":
    unittest.main()
