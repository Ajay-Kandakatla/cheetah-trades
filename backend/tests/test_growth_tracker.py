"""🚀 Explosive Growth tracker — behavioral, negative, regression, source guards.

Ajay 2026-09-11: "tell me which new ones are blowing up? in Sales by 100% or
more and 100 growth Quarter over Quarter ... I wanna know when ever these are in
demand, separately just trackers" · "remove the 700M rule for this page" · "I
want real growing stocks like AXTI and SABR with genuine sales".

The two rules that must never drift:
  1. This board has NO cap floor — and says so on rows the ENGINE will refuse.
  2. The alert still carries the standing phone gates plus `intact`.
"""
from __future__ import annotations

import ast
import io
import os

import pytest

from growth import alerts as A
from growth import tracker as T
from trading import safety_floor as SF

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fundamentals(sales=145.9, prior=7.2, eps=185.0, **kw):
    f = {"sales": {"growth_yoy_pct": sales, "prior_yoy_pct": prior,
                   "tier": "explosive", "accelerating": True,
                   "consecutive_growth_q": 3},
         "q_eps_growth_pct": eps,
         "earnings_quality": {"components": {"eps_prior_yoy_pct": 75.0,
                                             "npm_latest_pct": 27.4,
                                             "npm_expanding": True}},
         "inst_ownership_pct": 73.38}
    f.update(kw)
    return f


# ---------------------------------------------------------------- behavioral
def test_the_screen_is_one_hundred_on_both_legs():
    assert T.MIN_SALES_GROWTH_PCT == 100.0
    assert T.MIN_EPS_GROWTH_PCT == 100.0


def test_axti_passes_the_screen():
    """His own named example. Real numbers from the research cache 2026-09-11:
    sales +145.9% on a +7.2% prior quarter, quarterly EPS +185.0%."""
    ok, legs = T.qualifies(fundamentals())
    assert ok is True
    assert legs["sales_growth_pct"] == 145.9
    assert legs["q_eps_growth_pct"] == 185.0
    assert legs["sales_prior_pct"] == 7.2


def test_the_boundary_passes_and_a_hair_under_fails():
    assert T.qualifies(fundamentals(sales=100.0, eps=100.0))[0] is True
    assert T.qualifies(fundamentals(sales=99.9, eps=100.0))[0] is False
    assert T.qualifies(fundamentals(sales=100.0, eps=99.9))[0] is False


# ------------------------------------------------------------------ negative
def test_one_good_quarter_is_not_enough():
    """The prior quarter must ALSO be growing. A single 100% quarter off a
    collapsed year-ago base is a comparison artifact, not a business — this is
    the leg that separates them."""
    assert T.qualifies(fundamentals(prior=0.0))[0] is False       # flat
    assert T.qualifies(fundamentals(prior=-12.0))[0] is False     # shrinking
    assert T.qualifies(fundamentals(prior=0.1))[0] is True        # barely growing


def test_missing_fundamentals_never_qualify_by_default():
    for bad in (None, {}, {"sales": {}}, {"sales": None},
                {"sales": {"growth_yoy_pct": 500.0}},              # no EPS
                {"q_eps_growth_pct": 500.0}):                      # no sales
        assert T.qualifies(bad)[0] is False, bad


def test_nan_never_passes_a_growth_gate():
    """NaN passes every >= comparison in Python."""
    nan = float("nan")
    assert T.qualifies(fundamentals(sales=nan))[0] is False
    assert T.qualifies(fundamentals(eps=nan))[0] is False
    assert T.qualifies(fundamentals(prior=nan))[0] is False


# ------------------------------------------- the no-cap-floor / warning pact
def test_the_board_has_no_cap_floor():
    """His explicit call: "remove the 700M rule for this page". A future edit
    that reinstates one on THIS board breaks the deal he made."""
    assert T.MIN_CAP_USD is None


def test_warnings_quote_the_real_entry_floors():
    """The board's warnings must be generated FROM trading/safety_floor.py, not
    retyped. If the engine's floor moves and the board keeps quoting the old
    number, it tells him a name is refused when it is not, or worse."""
    assert T.SMALL_CAP_WARN_USD == SF.MIN_CAP_USD
    w = T.row_warnings(price=10.0, cap=SF.MIN_CAP_USD - 1, dollar_vol=50e6,
                       promo_tagged=False, zone_missing=False)
    assert any("REFUSE" in x for x in w), w
    assert any("%.0fM" % (SF.MIN_CAP_USD / 1e6) in x for x in w), w


def test_a_row_the_engine_refuses_is_marked_not_hidden():
    """PROP-class: $0.45 a share. It belongs on the board (no cap floor) AND it
    must carry a ⛔ saying the engine will refuse it."""
    w = T.row_warnings(price=0.45, cap=None, dollar_vol=200_000,
                       promo_tagged=True, zone_missing=True)
    assert any(x.startswith("⛔") and "entry floor" in x for x in w), w
    assert any("cap unknown" in x for x in w), w
    assert any("thin tape" in x for x in w), w
    assert any("promo-tagged" in x for x in w), w
    assert any("no zone bands" in x for x in w), w


def test_a_clean_big_name_carries_no_warnings():
    """NEGATIVE. AXTI-class: $64.77, $3.95B, liquid, not promo-tagged, banded."""
    assert T.row_warnings(price=64.77, cap=3.95e9, dollar_vol=50e6,
                          promo_tagged=False, zone_missing=False) == []


def test_micro_cap_warns_louder_than_small_cap():
    micro = T.row_warnings(50.0, 40e6, 50e6, False, False)
    small = T.row_warnings(50.0, 600e6, 50e6, False, False)
    assert any("micro-cap" in w for w in micro), micro
    assert not any("micro-cap" in w for w in small), small
    assert all(w.startswith("⛔") for w in micro + small)


# ------------------------------------------------------------------- alerts
def row(symbol="HHH", price=61.55, intact=True, in_band=True, band=None,
        warnings=None):
    band = band if band is not None else {"lo": 60.0, "hi": 62.0, "touches": 3}
    return {"symbol": symbol, "price": price,
            "sales_growth_pct": 330.2, "q_eps_growth_pct": 1318.2,
            "warnings": warnings or [],
            "zone": {"missing": False, "in_band": in_band, "intact": intact,
                     "band": band if in_band else None, "order_block": False}}


def test_alert_fires_for_an_intact_band(monkeypatch):
    monkeypatch.setattr(A, "_bands_for", lambda s: [
        {"kind": "demand", "lo": 60.0, "hi": 62.0},
        {"kind": "supply", "lo": 80.0, "hi": 82.0}])      # +30% room
    assert [i["row"]["symbol"] for i in A.candidates([row()])] == ["HHH"]


def test_alert_is_silent_when_the_floor_was_pierced(monkeypatch):
    """NEGATIVE for the ONE gate that measured (+8.6pp, n=31,861). Loosening
    this to "in band" would be exactly the kind of accuracy-for-volume trade he
    told me never to make."""
    monkeypatch.setattr(A, "_bands_for", lambda s: [
        {"kind": "demand", "lo": 60.0, "hi": 62.0},
        {"kind": "supply", "lo": 80.0, "hi": 82.0}])
    assert A.candidates([row(intact=False)]) == []
    assert A.candidates([row(intact=None)]) == []


def test_alert_is_silent_without_room_overhead(monkeypatch):
    """NEGATIVE for his 2026-09-05 standing gate. A 100% sales grower with 2%
    of room to the first supply band is still a bad entry — growth does not
    buy an exemption from the phone gates."""
    monkeypatch.setattr(A, "_bands_for", lambda s: [
        {"kind": "demand", "lo": 60.0, "hi": 62.0},
        {"kind": "supply", "lo": 62.5, "hi": 63.0}])      # ~1.5% overhead
    assert A.candidates([row()]) == []


def test_alert_is_silent_when_the_print_left_the_band(monkeypatch):
    """NEGATIVE that ISOLATES demand_proximity_gate.

    The first version of this test used a price UNDER the band floor and passed
    even with the proximity gate deleted — the room gate was catching it, since
    a band under your feet is overhead once you fall through it. So it proved
    nothing about proximity. This case has plenty of room overhead and fails on
    proximity alone.

    The situation is real, not contrived: `zone.in_band` is computed from the
    zone doc's prev_close while `price` is the fresher last close, so a row can
    carry in_band=True while the print has already run above the band top. He
    does not want a push 5% above the level he was going to buy at."""
    monkeypatch.setattr(A, "_bands_for", lambda s: [
        {"kind": "demand", "lo": 60.0, "hi": 62.0},
        {"kind": "supply", "lo": 80.0, "hi": 82.0}])          # +23% room at $65
    assert A.candidates([row(price=65.0)]) == []              # 4.8% above the top
    assert A.candidates([row(price=62.5)]) != []              # 0.8% above — still at the level


def test_alert_is_silent_when_price_fell_through_the_floor(monkeypatch):
    """A breakdown is not an arrival. (Either gate may be the one that drops
    it — see the isolating test above for the proximity-only proof.)"""
    monkeypatch.setattr(A, "_bands_for", lambda s: [
        {"kind": "demand", "lo": 60.0, "hi": 62.0},
        {"kind": "supply", "lo": 80.0, "hi": 82.0}])
    assert A.candidates([row(price=58.0)]) == []


def test_a_refused_name_still_alerts_but_says_so(monkeypatch):
    """The board has no cap floor, so the push must reach him for a name the
    engine will not buy — LABELLED, never silently dropped."""
    monkeypatch.setattr(A, "_bands_for", lambda s: [
        {"kind": "demand", "lo": 60.0, "hi": 62.0},
        {"kind": "supply", "lo": 80.0, "hi": 82.0}])
    warn = "⛔ $218M cap is under the $700M floor every other board uses — the engine will REFUSE to buy it"
    items = A.candidates([row(warnings=[warn])])
    assert len(items) == 1
    msg = A.message(items[0]["row"], items[0]["band"], items[0]["room"])
    assert "REFUSE" in msg["body"]
    assert msg["kind"] == "growth_demand_alert"
    assert msg["ticker"] == "HHH"


def test_the_kind_is_its_own_and_is_registered_everywhere():
    """He asked for it "separately just trackers" — and a kind missing from
    default_prefs silently drops for every device."""
    from market_hours import gate
    from push import subs

    assert A.KIND == "growth_demand_alert"
    assert A.KIND in subs.default_prefs(), "missing from default_prefs → silent"
    assert A.KIND in gate.MARKET_ALERT_KINDS, "would push on holidays/weekends"
    assert A.KIND not in gate.PERSONAL_KINDS


# ------------------------------------------------------------- source guards
def _tree(*parts):
    path = os.path.join(HERE, *parts)
    return ast.parse(io.open(path, encoding="utf-8").read(), filename=path)


def test_the_alert_path_calls_all_three_gates():
    """SOURCE GUARD, by AST. `candidates` must consult room_gate,
    demand_proximity_gate and the intact flag. Dropping one is exactly the
    "loosen a gate to get more alerts" move he ruled out."""
    tree = _tree("growth", "alerts.py")
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "candidates")
    called = {n.func.attr for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "room_gate" in called, "the >=5% room gate is gone"
    assert "demand_proximity_gate" in called, "the <=1%-above gate is gone"
    src = ast.dump(fn)
    assert "'intact'" in src or '"intact"' in src, "the measured intact gate is gone"


def test_the_tracker_declares_no_cap_floor_as_a_constant():
    """SOURCE GUARD. MIN_CAP_USD must be literally None, so a reviewer reading
    the module sees the decision rather than an absence."""
    tree = _tree("growth", "tracker.py")
    assigns = [n for n in tree.body if isinstance(n, ast.Assign)
               and any(getattr(t, "id", None) == "MIN_CAP_USD" for t in n.targets)]
    assert len(assigns) == 1
    assert isinstance(assigns[0].value, ast.Constant)
    assert assigns[0].value.value is None


SELECTING_FUNCS = {("tracker.py", "qualifies"), ("tracker.py", "screen"),
                   ("tracker.py", "row_warnings"), ("alerts.py", "candidates")}


def test_the_order_block_never_gates_anything():
    """SOURCE GUARD. The 2026-09-04 ICT study measured +0.03R over 6,004
    signals — nothing. `order_block` may be READ and DISPLAYED (alerts.message
    prints it in the push body, deliberately), but it must never appear in a
    condition inside a function that decides which rows survive.

    Scoped to the SELECTING functions on purpose: the first version of this
    guard walked whole modules and fired on the display branch in message(),
    which is the behaviour we actually want."""
    for mod, fname in sorted(SELECTING_FUNCS):
        tree = _tree("growth", mod)
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == fname), None)
        assert fn is not None, "%s::%s vanished" % (mod, fname)
        for node in ast.walk(fn):
            if isinstance(node, (ast.If, ast.IfExp)):
                assert "order_block" not in ast.dump(node.test), (
                    "%s::%s gates on order_block, which measured no edge"
                    % (mod, fname))
            if isinstance(node, (ast.ListComp, ast.GeneratorExp)):
                for gen in node.generators:
                    for cond in gen.ifs:
                        assert "order_block" not in ast.dump(cond), (
                            "%s::%s filters on order_block" % (mod, fname))


def test_the_order_block_IS_still_displayed():
    """The other half: it must survive as a READ. Deleting it entirely would
    also pass the guard above, and he asked to see order blocks."""
    tree = _tree("growth", "alerts.py")
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "message")
    assert "order_block" in ast.dump(fn), \
        "the order-block note is gone from the push body"


# ------------------------------------------------- sector tree (2026-09-12)
# Ajay 2026-09-12: "I need them to be clickable in to tickers and pick the top
# 10 in each sector." The cap lives on the BACKEND so the payload never
# balloons; `n` must stay the TRUE count so the UI can say "+N more" instead
# of silently under-reporting a sector.

def _grouped(rows, totals=None, monkeypatch=None):
    from growth import api as GA
    monkeypatch.setattr(GA, "_sector_totals", lambda: (totals or {}))
    return GA._group(rows)


def r(sym, sales, sector="Technology", industry="Semiconductors"):
    return {"symbol": sym, "sales_growth_pct": sales, "q_eps_growth_pct": 150.0,
            "sector": sector, "industry": industry}


def test_a_sector_lists_at_most_ten_tickers(monkeypatch):
    rows = [r("S%02d" % i, 500.0 - i) for i in range(25)]
    g = _grouped(rows, {"Technology": 493}, monkeypatch)[0]
    assert len(g["symbols"]) == 10
    assert len(g["industries"][0]["symbols"]) == 10


def test_the_ten_are_the_RICHEST_ten_not_the_first_ten(monkeypatch):
    rows = [r("LOW", 101.0), r("TOP", 900.0), r("MID", 400.0)]
    rows += [r("F%d" % i, 150.0 + i) for i in range(12)]
    g = _grouped(rows, {"Technology": 493}, monkeypatch)[0]
    assert g["symbols"][0] == "TOP"
    assert g["symbols"][1] == "MID"
    assert "LOW" not in g["symbols"]          # weakest of 15 is cut, not kept


def test_n_stays_the_true_count_so_the_row_can_say_plus_n_more(monkeypatch):
    rows = [r("S%02d" % i, 500.0 - i) for i in range(14)]
    g = _grouped(rows, {"Technology": 493}, monkeypatch)[0]
    assert g["n"] == 14                        # NOT 10 — the cap is display-only
    assert g["n"] - len(g["symbols"]) == 4
    assert g["hit_rate_pct"] == pytest.approx(100.0 * 14 / 493, abs=0.01)


def test_NEGATIVE_a_sector_under_ten_is_not_padded(monkeypatch):
    g = _grouped([r("A", 400.0), r("B", 300.0)], {"Technology": 493},
                 monkeypatch)[0]
    assert g["symbols"] == ["A", "B"]
    assert g["n"] == 2


def test_NEGATIVE_a_missing_sales_number_sorts_last_never_crashes(monkeypatch):
    rows = [r("BLANK", None), r("REAL", 120.0)]
    g = _grouped(rows, {"Technology": 493}, monkeypatch)[0]
    assert g["symbols"] == ["REAL", "BLANK"]


def test_NEGATIVE_an_unmapped_sector_gets_its_own_bucket_never_dropped(monkeypatch):
    rows = [r("A", 400.0), r("NOSEC", 300.0, sector=None, industry=None)]
    groups = _grouped(rows, {"Technology": 493}, monkeypatch)
    assert {g["group"] for g in groups} == {"Technology", "(unmapped)"}
    assert sum(g["n"] for g in groups) == 2    # nothing vanished
    unmapped = [g for g in groups if g["group"] == "(unmapped)"][0]
    assert unmapped["n_scanned"] is None and unmapped["hit_rate_pct"] is None


def test_the_cap_is_one_named_constant_not_a_literal_in_the_loop():
    """Source guard: two levels cap the list, and both must read the same
    constant — a hand-typed 10 in one of them is how they drift apart."""
    import ast as _ast
    src = io.open(os.path.join(HERE, "growth", "api.py"),
                  encoding="utf-8").read()
    tree = _ast.parse(src)
    assert any(isinstance(n, _ast.Assign)
               and any(getattr(t, "id", None) == "TOP_N_SYMBOLS" for t in n.targets)
               for n in tree.body), "TOP_N_SYMBOLS must be a module constant"
    top = [n for n in tree.body
           if isinstance(n, _ast.FunctionDef) and n.name == "_top"]
    assert top, "_top() must be the ONE place the list is cut"
    names = {n.id for n in _ast.walk(top[0]) if isinstance(n, _ast.Name)}
    assert "TOP_N_SYMBOLS" in names
    grp = [n for n in tree.body
           if isinstance(n, _ast.FunctionDef) and n.name == "_group"][0]
    calls = {getattr(c.func, "id", None) for c in _ast.walk(grp)
             if isinstance(c, _ast.Call)}
    assert "_top" in calls, "_group must cut through _top(), not inline"


# ── the row cap is stated, not silent (2026-09-12) ──────────────────────────
# The screen caps at MAX_ROWS BEFORE the browser sees anything, and it caps by
# SALES GROWTH. That became load-bearing when the board started sorting
# client-side (Ajay: "sort this by demand intact"): at the cap, a demand sort
# ranks within the sales-growth cut, so an intact name past the cap is ABSENT,
# not merely low. 29 of 300 today — the point is that the reader can tell.
def test_the_payload_states_the_row_cap_so_a_client_sort_cannot_lie():
    from growth import api as GA, tracker as GT
    out = GA._payload({"rows": [{"symbol": "HHH"}], "built_at": None})
    assert out["max_rows"] == GT.MAX_ROWS
    assert out["capped"] is False


def test_NEGATIVE_a_full_build_reports_itself_as_capped():
    from growth import api as GA, tracker as GT
    rows = [{"symbol": f"S{i}"} for i in range(GT.MAX_ROWS)]
    out = GA._payload({"rows": rows, "built_at": None})
    assert out["capped"] is True, "a build at the cap must say the list is cut"
    assert out["n"] == GT.MAX_ROWS


def test_NEGATIVE_capped_is_never_a_truthy_row_count():
    """`capped` must be a bool, not the count — the FE renders it directly and
    a non-empty board would print the warning on every load."""
    from growth import api as GA
    out = GA._payload({"rows": [{"symbol": "A"}, {"symbol": "B"}], "built_at": None})
    assert out["capped"] is False and isinstance(out["capped"], bool)
