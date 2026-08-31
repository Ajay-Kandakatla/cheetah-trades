"""The bull-regime gate on the setup scanners.

Ajay 2026-08-31: "there is a problem with setup tab and Supply demand tab..
Can you make sure logic is intact". It was not: `is_bull_regime` imported
`sepa.market_regime.classify_regime`, which has never existed. The ImportError
was swallowed and the gate returned None ("go ahead") on every call, so the
sit-out-bear-markets rule Ajay explicitly asked for had never fired once.

The source guard is the point of this file. A behavioural test alone would not
have caught the original bug, because a gate that always fails open still
returns a legal value.
"""
import importlib
import inspect

import pytest

from setups import universe


# --------------------------------------------------------------------------
# Source guard — the bug was a name that did not resolve.
# --------------------------------------------------------------------------

def test_is_bull_regime_calls_a_function_that_actually_exists():
    """Every `sepa.market_regime` name this module imports must be real.

    This is the regression test for the actual defect. It reads the source of
    `is_bull_regime` and resolves each name it pulls out of the regime module,
    so a rename on either side fails here instead of silently degrading the
    gate to "always allow".
    """
    mod = importlib.import_module("sepa.market_regime")
    src = inspect.getsource(universe.is_bull_regime)

    imported = [
        line.split("import")[1].strip()
        for line in src.splitlines()
        if "from sepa.market_regime import" in line
    ]
    assert imported, "is_bull_regime no longer imports from sepa.market_regime"

    for name in imported:
        for part in (n.strip().split(" as ")[0] for n in name.split(",")):
            assert hasattr(mod, part), (
                f"is_bull_regime imports sepa.market_regime.{part}, which does "
                f"not exist. This is exactly the 2026-08-31 bug: the ImportError "
                f"is swallowed and the gate silently returns None forever."
            )


# --------------------------------------------------------------------------
# Behaviour — the three labels the regime module can actually emit.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("label,expected", [
    ("confirmed_uptrend", True),
    ("uptrend_under_pressure", True),
    ("market_in_correction", False),
])
def test_each_real_regime_label_maps_deliberately(monkeypatch, label, expected):
    """The three labels `_label_from_score` emits are mapped explicitly.

    `uptrend_under_pressure` is the one that matters: it contains the substring
    "uptrend", so the old heuristic matched the BULL branch by accident. The
    answer is unchanged (cracks forming is not a bear) but it is now a decision
    rather than a coincidence of string matching.
    """
    import sepa.market_regime as mr
    monkeypatch.setattr(mr, "regime", lambda *a, **k: {"label": label})
    assert universe.is_bull_regime() is expected


def test_the_gate_is_what_actually_stops_a_bear_scan(monkeypatch):
    """A bearish regime must produce zero setups, not a smaller list.

    The scanners are documented as short-circuiting to a no-op. This asserts the
    contract end-to-end on a real scanner rather than trusting the docstring.
    """
    from setups import bull_flag
    monkeypatch.setattr(bull_flag.universe, "is_bull_regime", lambda: False)

    def _boom(*a, **k):
        raise AssertionError("scan reached the universe in a bear regime")

    monkeypatch.setattr(bull_flag.universe, "get_sepa_candidates", _boom)
    assert bull_flag.scan() == []


def test_unknown_labels_resolve_the_bearish_word_first(monkeypatch):
    """When guessing, caution wins.

    A label carrying both families of word ("uptrend losing ground to a
    correction") is ambiguous. Guessing bullish on an ambiguous label is the
    failure mode that costs money, so the bear words are tested first.
    """
    import sepa.market_regime as mr
    monkeypatch.setattr(
        mr, "regime",
        lambda *a, **k: {"label": "uptrend_giving_way_to_correction"})
    assert universe.is_bull_regime() is False


def test_safe_to_long_outranks_any_label_guess(monkeypatch):
    """If the regime module ever states it outright, the label is not consulted."""
    import sepa.market_regime as mr
    monkeypatch.setattr(
        mr, "regime",
        lambda *a, **k: {"label": "confirmed_uptrend", "safe_to_long": False})
    assert universe.is_bull_regime() is False


def test_an_unreadable_regime_is_none_not_a_guess(monkeypatch):
    """None is reserved for "could not determine" and must stay reachable."""
    import sepa.market_regime as mr
    monkeypatch.setattr(mr, "regime", lambda *a, **k: "not a dict")
    assert universe.is_bull_regime() is None

    def _raise(*a, **k):
        raise RuntimeError("regime source down")

    monkeypatch.setattr(mr, "regime", _raise)
    assert universe.is_bull_regime() is None
