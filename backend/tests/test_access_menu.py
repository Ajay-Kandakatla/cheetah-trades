"""Nav placement — which features land in which header section.

Ajay 2026-08-16: "Can you add the chart map to the header menu please. remove
the research and add it to Tools or something."

Placement is data (`FEATURE_CATALOG[*]["group"]`), so a one-word edit silently
moves a page between the header bar and a dropdown. These tests pin the two he
asked for, plus the invariant that makes the whole menu work: the route is
derived from the feature id, so they cannot drift apart.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from access import store  # noqa: E402


def _entry(fid: str) -> dict:
    return next(e for e in store.FEATURE_CATALOG if e["id"] == fid)


def test_chart_maps_is_in_the_primary_header_bar():
    """Ajay asked for it in the header, not behind the Scanners dropdown."""
    assert _entry("chart-maps")["group"] == "daily"
    assert store._GROUP_TO_SECTION["daily"] == "primary"


def test_research_moved_out_of_the_header_into_tools():
    assert _entry("research")["group"] == "tools"
    assert store._GROUP_TO_SECTION["tools"] == "misc"


def _frontend_src():
    """Locate frontend/src, or None — absent inside the api container, where
    only backend/ is mounted."""
    for parent in Path(__file__).resolve().parents:
        cand = parent / "frontend" / "src"
        if cand.is_dir():
            return cand
    return None


def test_research_has_a_tools_subgroup_so_it_does_not_fall_into_More():
    """NavBar buckets Tools items by TOOLS_SUBGROUP; anything unlisted lands in
    the catch-all 'More'. Research is analysis, so it belongs with Signals."""
    import pytest
    src = _frontend_src()
    if src is None:
        pytest.skip("frontend/ not mounted")
    nav = (src / "components" / "NavBar.tsx").read_text()
    subgroup = nav.split("const TOOLS_SUBGROUP")[1].split("};")[0]
    assert "research: 'Signals'" in subgroup


def test_the_route_equals_the_feature_id():
    """build_menu emits `/{fid}`, so a feature id that does not match its route
    produces a nav link to a 404. Locks both pages Ajay just moved."""
    import inspect
    src = inspect.getsource(store.build_menu)
    assert 'f"/{fid}"' in src, "build_menu no longer derives the route from the id"

    import pytest
    src = _frontend_src()
    if src is None:
        pytest.skip("frontend/ not mounted")
    app = (src / "App.tsx").read_text()
    for fid in ("chart-maps", "research"):
        assert f'path="/{fid}"' in app, f"/{fid} has no route in App.tsx"


def test_moving_a_page_did_not_change_its_grant():
    """Placement is cosmetic — it must not silently revoke access. chart-maps
    stays owner-on via added_in; research keeps its original added_in so an
    owner who already saw it is not re-granted."""
    cm, rs = _entry("chart-maps"), _entry("research")
    assert cm["added_in"] == 19 and cm["default"] is False
    assert rs["added_in"] == 3 and rs["default"] is False


def test_feature_ids_are_unique():
    ids = [e["id"] for e in store.FEATURE_CATALOG]
    assert len(ids) == len(set(ids))


def test_alerts_page_is_a_tools_feature_owner_on_at_catalog_23():
    """Ajay 2026-09-05: "can I go to a dedicated page to see the list of alerts?"
    Feature id 'alerts' -> route /alerts (build_menu derives it); label carries
    the bell; Tools group; owner-on via added_in == CATALOG_VERSION == 23."""
    e = _entry("alerts")
    assert e["label"] == "🔔 Alerts" and e["group"] == "tools" and e["default"] is False
    assert e["added_in"] == 23 == store.CATALOG_VERSION
    assert store._GROUP_TO_SECTION["tools"] == "misc"
    eff = store.effective_features({"sepa"}, is_owner=True, seen_version=22)
    assert "alerts" in eff, "an owner who saved before v23 gets the page on next load"
    assert "alerts" not in store.effective_features({"sepa"}, is_owner=False, seen_version=22)
