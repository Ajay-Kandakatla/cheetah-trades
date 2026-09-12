"""The Support tab can actually ASK for the study overlays (2026-09-12).

Ajay, three times:
  "Non of these are showing up I selected AMD, Fibonacci"
  "Nope still dont see them"
  "Still not seeing, AMD or keltners indicators. Whts going on?"

My first two answers were wrong — I blamed a render bug, then a stale tab. The
third screenshot settled it: the overlay ledger on the SUPPORT surface showed
AMD phases / Fibonacci / Mean reversion / Keltner all ticked, and nothing drew.

Root cause: the ledger renders those four on EVERY surface that mounts it
(they are declared `always: true` in chartOverlays.ts), but
`GET /chart-maps/support` had no `studies` parameter at all. The payload could
not carry an AMD band or a fib line however the checkbox was set. Verified live
on DBRG before the fix: tones {neutral, now, target}, bands {demand,
order_block}, nothing else.
"""
from __future__ import annotations

import inspect

import pytest


def test_the_support_endpoint_accepts_a_studies_flag():
    from chart_maps import api as A
    sig = inspect.signature(A.chart_maps_support)
    assert "studies" in sig.parameters, (
        "without this the Support tab's four study checkboxes are decorative")


def test_studies_defaults_to_OFF_so_the_tab_costs_no_extra_frame_read():
    from chart_maps import api as A
    p = inspect.signature(A.chart_maps_support).parameters["studies"]
    default = getattr(p.default, "default", p.default)
    assert default is False


def test_it_reuses_the_BOARD_helper_so_two_surfaces_cannot_draw_different_fibs():
    """A second implementation of Fibonacci on this endpoint is how the Support
    tab and a board tab start disagreeing about one name."""
    src = inspect.getsource(__import__("chart_maps.api", fromlist=["x"]).chart_maps_support)
    assert "_attach_studies" in src
    # It must DELEGATE, not import a study module and derive its own levels.
    for mod in ("supply_demand import fib", "supply_demand import amd",
                "supply_demand import meanrev", "supply_demand import keltner",
                "RETRACEMENTS", "EMA_LEN"):
        assert mod not in src, f"the endpoint must not compute its own {mod}"


def test_NEGATIVE_a_study_failure_cannot_empty_the_tile():
    """Soft-fail: the real bands must survive a study that will not compute."""
    src = inspect.getsource(__import__("chart_maps.api", fromlist=["x"]).chart_maps_support)
    i = src.index("_attach_studies")
    assert "try:" in src[:i], "the studies call must be fenced"


def test_NEGATIVE_studies_is_gated_on_True_not_on_truthiness():
    """These handlers get called directly in the container for smoke tests, and
    a direct call receives the `Query` OBJECT — which is truthy. `if studies:`
    would attach studies on every internal call."""
    src = inspect.getsource(__import__("chart_maps.api", fromlist=["x"]).chart_maps_support)
    assert "studies is True" in src
