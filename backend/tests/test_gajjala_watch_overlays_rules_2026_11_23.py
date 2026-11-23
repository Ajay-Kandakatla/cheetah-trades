"""📈📐 ℹ️ rules panel: the Watch's VWAP + daily zones clause (spec vwapzones §3.6b [C7], WP be-zones, 2026-11-23).

Ajay 2026-11-23, verbatim: "Add vwap and supply demand too".

Pins: `vwap.rules_line()` and `levels.rules_line()` are both in the Gajjala section note, right after the 📅 runners
clause; NEGATIVES: one half raising (or its module absent) drops only that half and the panel answers; both off → the
note equals the note without the clause.
"""
from __future__ import annotations

import inspect
import sys

from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import levels as LV
from chart_maps.gajjala_watch import vwap as VW
from supply_demand import rules_info as RI


def _note():
    return RI._gajjala_section()["note"]


def test_both_sentences_are_in_the_gajjala_note_after_the_runners_clause():
    note = _note()
    v, z = VW.rules_line(), LV.rules_line()
    assert v and z and v in note and z in note
    assert RI._gg_watch_overlays_clause() == " " + v + " " + z
    src = inspect.getsource(RI._gajjala_section)
    assert src.index("_gg_watch_runners_clause()") < src.index("_gg_watch_overlays_clause()") \
        < src.index("_gg_divergence_clause()")


def test_NEGATIVE_a_raising_zones_half_keeps_the_vwap_half(monkeypatch):
    monkeypatch.setattr(LV, "rules_line", lambda: 1 / 0)
    note = _note()
    assert VW.rules_line() in note and "📐 Daily zones on" not in note
    assert RI._gg_watch_overlays_clause() == " " + VW.rules_line()


def test_NEGATIVE_a_raising_vwap_half_keeps_the_zones_half(monkeypatch):
    monkeypatch.setattr(VW, "rules_line", lambda: 1 / 0)
    note = _note()
    assert LV.rules_line() in note and "📈 VWAP on" not in note
    assert RI._gg_watch_overlays_clause() == " " + LV.rules_line()


def test_NEGATIVE_an_absent_module_drops_only_its_half(monkeypatch):
    import chart_maps.gajjala_watch as PKG
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.vwap", None)          # import → ImportError
    monkeypatch.delattr(PKG, "vwap", raising=False)
    assert RI._gg_watch_overlays_clause() == " " + LV.rules_line()
    assert "📐 Daily zones on" in _note()


def test_NEGATIVE_both_off_the_note_equals_the_note_without_the_clause(monkeypatch):
    monkeypatch.setattr(C, "VWAP_ON", False)
    monkeypatch.setattr(C, "ZONES_ON", False)
    assert RI._gg_watch_overlays_clause() == ""
    off = _note()
    monkeypatch.setattr(RI, "_gg_watch_overlays_clause", lambda: "")
    assert off == _note() and "📈 VWAP on" not in off and "📐 Daily zones on" not in off
