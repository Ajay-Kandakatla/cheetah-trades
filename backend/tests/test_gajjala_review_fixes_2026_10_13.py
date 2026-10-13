"""Review fixes (2026-10-13) on the tab's own strip: the price floor prints as money ($0.10, as the playbook knob table
does) and the not-quiet line cites the same timestamp as SA_QUIET_BEST_PCT (S8 44:37). Positive + NEGATIVE cases."""
from __future__ import annotations

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import tab as GT

EMPTY = {"best_change_pct": None, "quiet": None}
NOT_QUIET = {"runners_100": 1, "runners_80": 2, "best_change_pct": 120.0, "best_symbol": "QQQX", "quiet": False}


def test_empty_strip_prints_the_price_floor_as_money():
    t = GT.strip_text(EMPTY)
    assert "$%.2f–" % GC.SCAN_MIN_PRICE in t and "$0.10–$100" in t
    assert "$0.1–" not in t                                            # NEGATIVE: the %g spelling is gone


def test_empty_strip_floor_follows_the_constant(monkeypatch):
    monkeypatch.setattr(GC, "SCAN_MIN_PRICE", 0.5)
    t = GT.strip_text(EMPTY)
    assert "$0.50–" in t and "$0.10" not in t                          # NEGATIVE: never a retyped floor


def test_not_quiet_line_cites_the_constants_timestamp():
    t = GT.strip_text(NOT_QUIET)
    assert t.endswith("best runner under %g%%, S8 44:37)" % GC.SA_QUIET_BEST_PCT)
    assert "43:39" not in t                                            # NEGATIVE: the wrong cite is gone


def test_quiet_and_not_quiet_cite_the_same_line():
    quiet = GT.strip_text(dict(NOT_QUIET, quiet=True, best_change_pct=31.0))
    assert "S8 44:37" in quiet and "S8 44:37" in GT.strip_text(NOT_QUIET)
    assert GT.strip_text({}) is None and GT.strip_text(None) is None   # NEGATIVE: no strip → no text
