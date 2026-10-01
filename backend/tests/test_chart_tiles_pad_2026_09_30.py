"""🧱 CHART TILES (2026-09-30) — the 1% pad rides every BOARD-geometry demand band.

Ajay 2026-09-30, verbatim: "Also increase our Demand zone and key levels sizes by
1%. becuz Generally we are missing this, I been noticing if the demand zone or key
level is 133, it holding at 132. My theory is MMs know stoplosses are beyond 133."

The tile draws the DRAWN band (lo/hi never move) plus `pad_lo` / `pad_pct` so the
chart can shade the pad as a lighter strip. Fine-geometry builders (Under Value,
the Support tab's finer levels, the zones page overlay) and Gabbar's own levels
are NOT padded — listed here, in the test, never in code. Hermetic.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "tests"))

from chart_maps import board as B                     # noqa: E402
from supply_demand import level_pad as LP             # noqa: E402
from supply_demand import demand_reentry as DR        # noqa: E402  (the real module, before any stub)
from supply_demand import deep_demand as _DD          # noqa: E402,F401  (imported before the stub)

from test_chart_maps import (  # noqa: E402,F401
    _deep_row, _frame, _reentry_row, _sales,
    prices, reentry_stub, sales_stub,
)

# Board-geometry tiles spread `LP.pad_fields(src)`; these builders draw FINE
# geometry (or Gabbar's own levels — a separate system, never padded).
FINE_GEOMETRY_BUILDERS = {
    "chart_maps/board.py": ("undervalue_tiles", "undervalue_peer_tiles", "gabbar_tiles"),
    "chart_maps/support.py": ("overlay_for_symbol", "_bands", "for_symbol"),
}
DEMAND_KINDS = ("demand", "board_demand")


@pytest.fixture
def cache_ttl(monkeypatch):
    """The shared `prices` stub predates ath_history's CACHE_TTL_SEC import."""
    monkeypatch.setattr(sys.modules["sepa.prices"], "CACHE_TTL_SEC", 3600, raising=False)


def _demand_dicts(rel):
    """(function name, statement source) for every dict literal whose "kind"
    is a demand kind, with the top-level function it sits in."""
    src = (BACKEND / rel).read_text()
    tree = ast.parse(src)
    out = []
    for fn in tree.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for stmt in ast.walk(fn):
            if not isinstance(stmt, ast.stmt) or isinstance(stmt, (ast.FunctionDef, ast.If,
                                                                      ast.For, ast.While,
                                                                      ast.With, ast.Try)):
                continue
            for node in ast.walk(stmt):
                if not isinstance(node, ast.Dict):
                    continue
                for k, v in zip(node.keys, node.values):
                    if (isinstance(k, ast.Constant) and k.value == "kind"
                            and isinstance(v, ast.Constant) and v.value in DEMAND_KINDS):
                        out.append((fn.name, ast.get_source_segment(src, stmt)))
    return out


@pytest.mark.parametrize("rel", sorted(FINE_GEOMETRY_BUILDERS))
def test_STRUCTURE_every_board_geometry_demand_band_spreads_the_pad(rel):
    found = _demand_dicts(rel)
    assert found, rel
    fine = FINE_GEOMETRY_BUILDERS[rel]
    padded = 0
    for name, stmt in found:
        if name in fine:
            assert "LP.pad_fields(" not in stmt, "%s:%s is fine geometry — never padded" % (rel, name)
            continue
        assert "LP.pad_fields(" in stmt, "%s:%s draws a demand band without its pad" % (rel, name)
        padded += 1
    assert padded >= (6 if rel.endswith("board.py") else 1)


def test_STRUCTURE_the_fine_builders_named_here_still_exist():
    for rel, names in FINE_GEOMETRY_BUILDERS.items():
        have = {n.name for n in ast.parse((BACKEND / rel).read_text()).body
                if isinstance(n, ast.FunctionDef)}
        for name in names:
            assert name in have, "%s: %s renamed — update the allowlist" % (rel, name)


def _zone_row(sym="PADX"):
    r = _reentry_row(sym)
    r["last_price"] = 134.0
    r["entry_zone"] = {"kind": "demand", "lo": 133.0, "hi": 135.0, "touches": 3}
    r["supply_zones"] = [{"kind": "supply", "lo": 150.0, "hi": 152.0}]
    r["plan"] = {"entry_ref": 134.0, "stop": 129.69, "target": 150.0, "rr": 3.9}
    return r


def test_zones_tab_demand_band_carries_the_pad_supply_does_not(prices, reentry_stub, cache_ttl):
    prices["PADX"] = _frame(200)
    reentry_stub["rows"] = [_zone_row()]
    t = B.board("zones", limit=5, min_tier="any", min_room=0)["tiles"][0]
    dem = [b for b in t["bands"] if b["kind"] == "demand"]
    sup = [b for b in t["bands"] if b["kind"] == "supply"]
    assert dem and dem[0]["lo"] == 133.0 and dem[0]["hi"] == 135.0
    assert dem[0]["pad_lo"] == 131.67 and dem[0]["pad_pct"] == 1.0
    assert sup and all("pad_lo" not in b for b in sup)


def test_zones_tab_stop_line_is_the_padded_trade_plan_stop(prices, reentry_stub, cache_ttl):
    want = DR.trade_plan(134.0, {"kind": "demand", "lo": 133.0, "hi": 135.0},
                         [{"kind": "supply", "lo": 150.0, "hi": 152.0, "touches": 3}])["stop"]
    assert want == 129.69                              # 133 x 0.99 = 131.67, x 0.985
    prices["PADX"] = _frame(200)
    row = _zone_row()
    row["plan"]["stop"] = want
    reentry_stub["rows"] = [row]
    t = B.board("zones", limit=5, min_tier="any", min_room=0)["tiles"][0]
    stop = [ln for ln in t["lines"] if ln["label"] == "STOP"]
    assert stop and stop[0]["price"] == want


def test_NEGATIVE_pad_off_the_zones_tile_has_no_pad_keys(prices, reentry_stub, cache_ttl, monkeypatch):
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 0.0)
    prices["PADX"] = _frame(200)
    reentry_stub["rows"] = [_zone_row()]
    t = B.board("zones", limit=5, min_tier="any", min_room=0)["tiles"][0]
    assert all("pad_lo" not in b for b in t["bands"])


def _deep(sym="DEEPX"):
    row = _deep_row(sym)
    row["last_price"] = 132.5
    row["deep_demand"].update({
        "levels_broken": 1, "level": 2,
        "top_band": {"kind": "demand", "lo": 140.0, "hi": 142.0, "touches": 3},
        "second_band": {"kind": "demand", "lo": 133.0, "hi": 135.0, "touches": 3,
                        "strength": 60.0, "oldest_touch_bars": 150},
        "broken_bands": [{"kind": "demand", "lo": 140.0, "hi": 142.0, "touches": 3}],
        "below_top_pct": 5.4,
    })
    row["plan"] = {"entry_ref": 132.5, "stop": 129.69, "target": 140.0, "rr": 2.6}
    return row


def test_deep_tab_arrival_band_carries_the_pad(prices, reentry_stub, sales_stub, cache_ttl,
                                               monkeypatch):
    monkeypatch.setattr(B, "_live_last", lambda syms, rows=None: {})
    reentry_stub["deep_rows"] = [_deep()]
    prices["DEEPX"] = _frame(200)
    sales_stub["DEEPX"] = _sales("steady", 9.0)
    t = B.board("deep_demand", limit=5, min_tier="any", min_room=0)["tiles"][0]
    dem = [b for b in t["bands"] if b["kind"] == "demand"]
    assert len(dem) == 1 and dem[0]["lo"] == 133.0 and dem[0]["pad_lo"] == 131.67
    # the crossed level draws as broken support (kind supply) — never padded
    assert all("pad_lo" not in b for b in t["bands"] if b["kind"] != "demand")


def test_support_board_band_carries_the_pad():
    from chart_maps import support as S
    got = S._board_bands({"demand": {"lo": 133.0, "hi": 135.0, "touches": 3},
                          "supply": {"lo": 150.0, "hi": 152.0}})
    dem = [b for b in got if b["kind"] == "board_demand"][0]
    sup = [b for b in got if b["kind"] == "board_supply"][0]
    assert dem["lo"] == 133.0 and dem["pad_lo"] == 131.67 and "pad_lo" not in sup


def test_NEGATIVE_support_board_band_pad_off(monkeypatch):
    from chart_maps import support as S
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 0.0)
    got = S._board_bands({"demand": {"lo": 133.0, "hi": 135.0, "touches": 3}})
    assert "pad_lo" not in got[0]
