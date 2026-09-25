"""The "just reported" refresh job — cron line + CLI (Ajay 2026-09-17).

The reminder he asked for is DATA, and this suite is what keeps it that way:
the job must be gated like its neighbours, must land between the 17:45 calendar
sweep and the 17:55 picks rebuild, must never rebuild the board, and must never
grow a send path. HIS PHONE'S KEEP-SET IS PINNED HERE BYTE FOR BYTE.
"""
import io
import json
import os
import re
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BACKEND = Path(__file__).resolve().parents[1]
CRONTAB = (BACKEND / "crontab").read_text()


def _job_lines():
    return [ln for ln in CRONTAB.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def _fields(line):
    return line.split()[:5]


def _find(pattern):
    rx = re.compile(pattern)
    return [ln for ln in _job_lines() if rx.search(ln)]


class CrontabTest(unittest.TestCase):
    def test_crontab_has_the_growth_earnings_line_exactly_once(self):
        hits = _find(r"-m market_hours\.gate growth earnings")
        self.assertEqual(len(hits), 1, hits)

    def test_the_line_is_gated_like_its_neighbour(self):
        line = _find(r"-m market_hours\.gate growth earnings")[0]
        neighbour = _find(r"-m market_hours\.gate growth alerts")[0]
        self.assertIn("market_hours.gate", line)
        self.assertIn("market_hours.gate", neighbour)

    def test_the_line_runs_weekdays_at_1750_between_earnings_watch_and_earnings_picks(self):
        line = _find(r"-m market_hours\.gate growth earnings")[0]
        self.assertEqual(_fields(line), ["50", "17", "*", "*", "1-5"])
        watch = _fields(_find(r"-m sepa\.earnings_watch\b")[0])
        picks = _fields(_find(r"-m sepa\.earnings_picks\b")[0])
        # read the neighbours out of the file — never retype their times
        as_min = lambda f: int(f[1]) * 60 + int(f[0])
        self.assertLess(as_min(watch), as_min(_fields(line)))
        self.assertLess(as_min(_fields(line)), as_min(picks))
        for f in (watch, picks):
            self.assertEqual(f[4], "1-5")

    def test_the_new_cron_block_does_not_contain_the_word_pankaj(self):
        """NEGATIVE — mirrors tests/test_pankaj.py."""
        self.assertNotIn("pankaj", CRONTAB.lower())

    def test_growth_build_and_alerts_lines_are_untouched(self):
        build = _find(r"-m growth build")
        alerts = _find(r"-m market_hours\.gate growth alerts")
        self.assertEqual(len(build), 1)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(_fields(build[0]), ["0", "9", "*", "*", "0"])
        self.assertEqual(_fields(alerts[0]), ["*/15", "9-16", "*", "*", "1-5"])


class NoSendPathTest(unittest.TestCase):
    def _earnings_branch(self):
        src = (BACKEND / "growth" / "__main__.py").read_text()
        start = src.index('if cmd == "earnings"')
        tail = src[start:]
        end = tail.index("print(__doc__)")
        return tail[:end]

    def test_the_growth_earnings_path_pushes_nothing(self):
        """NEGATIVE — THE PIN. No send vocabulary anywhere on this path, and
        the keep-set his phone runs on is byte-identical."""
        fresh = (BACKEND / "growth" / "earnings_fresh.py").read_text()
        for blob, label in ((self._earnings_branch(), "__main__ earnings branch"),
                            (fresh, "earnings_fresh.py")):
            for word in ("push", "notify", "send_to_all", "send_to_user",
                         "KIND", "alerts"):
                self.assertNotIn(word, blob, "%s mentions %r" % (label, word))
        from push import subs
        # WIDENED 2026-09-20 ("Default on for any change of todays features
        # Bondes or Potus or explosive growth or Earnings I wanna see all of
        # them") — still pinned here, because what this test is really for is
        # that the growth EARNINGS path never touches the keep-set.
        # WIDENED AGAIN 2026-09-21 — 🔔 price_alert ("Yes to all.."), which
        # this path also never touches. WIDENED 2026-09-25 — 🔑
        # key_level_alert (his "On: week + month + 52-week"), also untouched here.
        self.assertEqual(set(subs.OWNER_KEEP_SET),
                         {"hot_pullback_alert", "pattern_alert",
                          "demand_alert", "position_alert",
                          "potus_investment", "growth_demand_alert",
                          "earnings_reaction", "board_arrival",
                          "price_alert", "key_level_alert"})

    def test_the_kinds_under_growth_are_the_two_that_were_asked_for(self):
        """NEGATIVE — no kind reaches his phone from this package by accident.

        WIDENED 2026-09-22 — 💎 `capital_quality_upgrade`
        (growth/quality_alerts.py), on his ask: "Filter and have alerts and new
        look out for such companies where whcih have very high quality."

        What this guard is really for is unchanged and is asserted separately
        above: the growth EARNINGS refresh path still sends nothing. The new
        kind lives in its own module, has its own cron line, and — unlike every
        other kind in this app — ships OFF, which the next assertion pins.
        """
        kinds = set()
        for p in (BACKEND / "growth").glob("*.py"):
            kinds |= set(re.findall(r'^KIND\s*=\s*"([^"]+)"',
                                    p.read_text(), re.M))
        self.assertEqual(kinds, {"growth_demand_alert", "capital_quality_upgrade"})

    def test_the_new_growth_kind_ships_muted(self):
        """NEGATIVE — a kind he has not seen fire must not start ringing on a
        deploy. It is registered (or it would target zero devices AND render no
        toggle) and it is OFF, in default_prefs and for the owner."""
        from push import subs
        self.assertIn("capital_quality_upgrade", subs.default_prefs())
        self.assertIs(subs.default_prefs()["capital_quality_upgrade"], False)
        self.assertNotIn("capital_quality_upgrade", subs.OWNER_KEEP_SET)
        self.assertIs(subs.owner_prefs()["capital_quality_upgrade"], False)


class CliTest(unittest.TestCase):
    def setUp(self):
        from growth import __main__ as M
        from growth import earnings_fresh as EF
        from growth import tracker as T
        self.M, self.EF, self.T = M, EF, T
        self._orig = (EF.refresh_board_calendar, EF.attach, T.board, T.build)

    def tearDown(self):
        (self.EF.refresh_board_calendar, self.EF.attach,
         self.T.board, self.T.build) = self._orig

    def _run(self, rows, refresh=None):
        self.T.board = lambda: {"rows": rows}
        self.T.build = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("the earnings job must never rebuild the board"))
        self.EF.refresh_board_calendar = refresh or (
            lambda **k: {"ok": True, "symbols": len(rows), "refreshed": len(rows)})
        self.EF.attach = lambda r, **k: {"n": len(r), "n_fresh": 0}
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.M.main(["earnings"])
        return rc, buf.getvalue()

    def test_cli_earnings_subcommand_returns_zero_and_prints_json(self):
        rc, out = self._run([{"symbol": "CRDO"}])
        self.assertEqual(rc, 0)
        doc = json.loads(out)
        self.assertEqual(doc["refresh"]["refreshed"], 1)
        self.assertEqual(doc["summary"]["n"], 1)

    def test_cli_earnings_returns_zero_when_the_board_is_empty(self):
        """NEGATIVE."""
        rc, out = self._run([], refresh=lambda **k: {
            "ok": True, "symbols": 0, "refreshed": 0, "reason": "empty board"})
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["refresh"]["reason"], "empty board")

    def test_cli_earnings_does_not_rebuild_the_board(self):
        """NEGATIVE — tracker.build raises if called."""
        rc, _ = self._run([{"symbol": "CRDO"}])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
