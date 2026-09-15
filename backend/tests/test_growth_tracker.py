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
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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
# Since 2026-09-14 (review finding 3) the trigger is the LIVE print: the board
# row supplies the GROWTH NUMBERS only, the print comes from one bulk_snapshot
# through zone_bounce_alerts.print_from_snapshot (stale = skipped), the
# arrival rule is demand_alerts.read and the floor gate is re-read on the
# session's own low. Until then it rang on Friday's stored close from a
# Sunday-built board — HHH re-fired daily while it sat BELOW its band.
ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 14, 11, 0, tzinfo=ET)


def row(symbol="HHH", price=61.55, intact=True, in_band=True, band=None,
        warnings=None):
    """A board row as growth/tracker.build stores it. `price` / `zone` are
    Friday's state and gate NOTHING since 2026-09-14 — `snap` does."""
    band = band if band is not None else {"lo": 60.0, "hi": 62.0, "touches": 3}
    return {"symbol": symbol, "price": price,
            "sales_growth_pct": 330.2, "q_eps_growth_pct": 1318.2,
            "warnings": warnings or [],
            "zone": {"missing": False, "in_band": in_band, "intact": intact,
                     "band": band if in_band else None, "order_block": False}}


def snap(px, prev=66.0, low=None, age_sec=30, chg=None, now=NOW):
    """One bulk_snapshot entry: last trade `px` stamped `age_sec` ago,
    yesterday's close `prev` (default OUTSIDE the 60-62 ring, so today is an
    arrival), day low just under the print (never through the 60 floor)."""
    ts_ns = int((now - timedelta(seconds=age_sec)).timestamp() * 1e9)
    lo = low if low is not None else round(px * 0.995, 4)
    return {"open": px, "high": px, "low": lo, "close": px, "volume": 1e6,
            "change_pct": chg if chg is not None else (round((px / prev - 1) * 100, 2) if prev else None),
            "last_trade_price": px, "last_trade_ts_ms": ts_ns, "prev_day_close": prev}


def cands(rows, snapshot, now=NOW):
    return A.candidates(rows, snapshot=snapshot, now=now)


@pytest.fixture
def live(monkeypatch):
    """The live floor read loads daily bars; the default here is "intact" so
    a test about room / proximity / wording tests THAT. The floor tests below
    stub their own. Also pins that the pass never fetches a snapshot itself
    when one is injected."""
    monkeypatch.setattr(A.AG, "sweep_read",
                        lambda *a, **k: {"state": "intact", "pierce_pct": None,
                                         "reclaim_bars": None, "vol_x": None})
    monkeypatch.setattr(A, "_snapshot_for",
                        lambda syms: (_ for _ in ()).throw(AssertionError("network snapshot in a unit test")))


def _bands(monkeypatch, supply=(80.0, 82.0)):
    monkeypatch.setattr(A, "_bands_for", lambda s: [
        {"kind": "demand", "lo": 60.0, "hi": 62.0, "touches": 3},
        {"kind": "supply", "lo": supply[0], "hi": supply[1], "touches": 2}])


def test_alert_fires_for_an_arrival_at_an_intact_band(monkeypatch, live):
    _bands(monkeypatch)                                       # +30% room
    items = cands([row()], {"HHH": snap(61.55)})
    assert [i["row"]["symbol"] for i in items] == ["HHH"]
    assert items[0]["row"]["price"] == 61.55 and items[0]["row"]["price_source"] == "live"
    assert items[0]["hit"]["tier"] == "at" and items[0]["last"] == 61.55


def test_the_stored_row_gates_nothing_only_the_live_print_does(monkeypatch, live):
    """The board row is Friday's close and Friday's in_band/intact flags. A
    live arrival on a row whose stored flags say "not in band, not intact"
    still rings; the stored price never reaches the push."""
    _bands(monkeypatch)
    items = cands([row(price=999.0, in_band=False, intact=False)], {"HHH": snap(61.55)})
    assert len(items) == 1
    msg = A.message(items[0]["row"], items[0]["band"], items[0]["room"], hit=items[0]["hit"])
    assert msg["body"].startswith("$61.55 · in demand $60–62")
    assert "999" not in msg["body"]


def test_alert_is_silent_when_the_floor_was_pierced(monkeypatch, live):
    """NEGATIVE for the ONE gate that measured (+8.6pp, n=31,861), now read
    LIVE. Loosening this to "in band" would be exactly the kind of
    accuracy-for-volume trade he told me never to make — and the stored
    intact=True on the row must not rescue it."""
    _bands(monkeypatch)
    for state in ("swept", "broken"):
        monkeypatch.setattr(A.AG, "sweep_read", lambda *a, _s=state, **k: {"state": _s})
        assert cands([row(intact=True)], {"HHH": snap(61.55)}) == [], state
    monkeypatch.setattr(A.AG, "sweep_read", lambda *a, **k: None)
    assert cands([row(intact=True)], {"HHH": snap(61.55)}) == [], "unreadable floor fails closed"


def test_the_live_floor_read_carries_the_sessions_low_and_print(monkeypatch, live):
    """The whole point of re-reading live: the snapshot's day low and the
    print reach sweep_read (alert_gates.with_session_bar merges them in)."""
    _bands(monkeypatch)
    seen = {}

    def fake_sweep(band, symbol=None, frame=None, window=None, **kw):
        seen.update(kw, symbol=symbol)
        return {"state": "intact"}
    monkeypatch.setattr(A.AG, "sweep_read", fake_sweep)
    cands([row()], {"HHH": snap(61.55, low=60.4)})
    assert seen["symbol"] == "HHH" and seen["day_low"] == 60.4 and seen["last"] == 61.55
    assert seen["day"] == NOW.date()


def test_alert_is_silent_without_room_overhead(monkeypatch, live):
    """NEGATIVE for his 2026-09-05 standing gate. A 100% sales grower with 2%
    of room to the first supply band is still a bad entry — growth does not
    buy an exemption from the phone gates."""
    _bands(monkeypatch, supply=(62.5, 63.0))                  # ~1.5% overhead
    assert cands([row()], {"HHH": snap(61.55)}) == []


def test_alert_is_silent_when_the_print_left_the_band(monkeypatch, live):
    """NEGATIVE that ISOLATES demand_proximity_gate: plenty of room overhead,
    the print 4.8% above the top. He does not want a push 5% above the level
    he was going to buy at."""
    _bands(monkeypatch)                                       # +23% room at $65
    assert cands([row()], {"HHH": snap(65.0)}) == []          # 4.8% above the top
    assert cands([row()], {"HHH": snap(62.5)}) != []          # 0.8% above — still at the level


def test_alert_is_silent_when_price_fell_through_the_floor(monkeypatch, live):
    """A breakdown is not an arrival — HHH on 2026-09-14 sat BELOW its band
    and rang anyway on Friday's stored close. demand_alerts.read says None
    under the floor, so nothing reaches the gates."""
    _bands(monkeypatch)
    assert cands([row()], {"HHH": snap(58.0, prev=61.5)}) == []


def test_NEGATIVE_a_stale_print_never_rings(live):
    """The 5-minute siblings' freshness rule: a last trade older than
    zone_bounce_alerts.STALE_PRINT_SEC is an old price, not "now"."""
    from supply_demand import zone_bounce_alerts as ZB
    items, counts = A._scan([row()], {"HHH": snap(61.55, age_sec=ZB.STALE_PRINT_SEC + 60)}, NOW)
    assert items == [] and counts["stale_print"] == 1
    assert A._scan([row()], {"HHH": snap(61.55, age_sec=ZB.STALE_PRINT_SEC - 60)}, NOW)[1]["stale_print"] == 0


def test_NEGATIVE_residence_and_an_unknown_prior_close_are_not_arrivals(monkeypatch, live):
    """Yesterday closed INSIDE the band = residence (the board's business);
    no prior close = cannot tell, silent. The identical rule the 🧲 pass uses."""
    _bands(monkeypatch)
    items, counts = A._scan([row()], {"HHH": snap(61.55, prev=61.0)}, NOW)
    assert items == [] and counts["no_arrival"] == 1
    items, counts = A._scan([row()], {"HHH": snap(61.55, prev=None)}, NOW)
    assert items == [] and counts["unknown_prev"] == 1
    items, counts = A._scan([row()], {}, NOW)
    assert items == [] and counts["unpriced"] == 1


def test_a_refused_name_still_alerts_but_says_so(monkeypatch, live):
    """The board has no cap floor, so the push must reach him for a name the
    engine will not buy — LABELLED, never silently dropped."""
    _bands(monkeypatch)
    warn = "⛔ $218M cap is under the $700M floor every other board uses — the engine will REFUSE to buy it"
    items = cands([row(warnings=[warn])], {"HHH": snap(61.55)})
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
    """SOURCE GUARD, by AST. The selecting function (`_scan` since
    2026-09-14; `candidates` only wraps it) must consult room_gate,
    demand_proximity_gate, the LIVE floor gate (floor_held_gate — the intact
    read, no longer a stored flag) and the arrival rule (demand_alerts.read)
    on a print that went through print_from_snapshot. Dropping one is exactly
    the "loosen a gate to get more alerts" move he ruled out."""
    tree = _tree("growth", "alerts.py")
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_scan")
    called = {n.func.attr for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    plain = {n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "room_gate" in called, "the >=5% room gate is gone"
    assert "demand_proximity_gate" in called, "the <=1%-above gate is gone"
    assert "floor_held_gate" in called, "the measured intact gate is gone (or no longer live)"
    assert "read" in called, "the arrival rule (demand_alerts.read) is gone"
    assert "print_from_snapshot" in plain, "the print no longer goes through the freshness rule"
    wrapper = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "candidates")
    assert "_scan" in {n.func.id for n in ast.walk(wrapper)
                       if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    src = ast.dump(fn)
    assert "'in_band'" not in src and "'intact'" not in src, \
        "the stored Friday flags must not gate a live push"


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
                   ("tracker.py", "row_warnings"), ("alerts.py", "candidates"),
                   ("alerts.py", "_scan")}


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


# ── unreadable is NOT pierced (2026-09-12) ──────────────────────────────────
# Found by an adversarial review of the demand sort. `AG.floor_held_gate` FAILS
# CLOSED — "Unreadable = False (fails closed)" — so an unloadable price frame
# returns the same plain False a real pierce does. `_zone_read` used to do
# `bool(floor_held_gate(...))`, collapsing the two, and the board then printed
# "in band, pierced" ("the floor has been pierced in the sweep window") for a
# name nobody had checked — ranking it ABOVE every row marked honestly unknown.
#
# The alert gate is deliberately NOT changed: failing closed is correct for a
# phone push and is a standing rule. Only the BOARD's tri-state is restored.
def _band():
    return {"lo": 10.0, "hi": 11.0, "kind": "demand", "touches": 3}


def _patched_zone_read(monkeypatch, sweep, held):
    """Drive tracker._zone_read with a stubbed zone doc and gate."""
    from supply_demand import alert_gates as AG
    from growth import tracker as GT
    monkeypatch.setattr(AG, "sweep_read", lambda *a, **k: sweep, raising=False)
    monkeypatch.setattr(AG, "floor_held_gate", lambda *a, **k: held, raising=False)

    class _DB:
        class zone_store:
            @staticmethod
            def find_one(*a, **k):
                return {"symbol": "X", "prev_close": 10.5, "date": "2026-09-11",
                        "bands": [_band()]}
    monkeypatch.setattr(GT, "_db", lambda: _DB, raising=False)
    return GT._zone_read("X")


def test_an_UNREADABLE_floor_is_unknown_not_pierced(monkeypatch):
    """sweep_read returns None when the price frame will not load."""
    out = _patched_zone_read(monkeypatch, sweep=None, held=False)
    assert out["in_band"] is True
    assert out["intact"] is None, "unreadable must stay UNKNOWN, never False"


def test_a_REAL_pierce_is_still_reported_as_pierced(monkeypatch):
    out = _patched_zone_read(monkeypatch, sweep={"state": "broken"}, held=False)
    assert out["intact"] is False


def test_an_intact_floor_still_reads_intact(monkeypatch):
    out = _patched_zone_read(monkeypatch, sweep={"state": "intact"}, held=True)
    assert out["intact"] is True


def test_NEGATIVE_the_alert_gate_itself_is_untouched_and_still_fails_closed():
    """Ajay's standing rule: never loosen a gate. `floor_held_gate` must keep
    returning False for an unreadable read — the fix belongs in the BOARD's
    tri-state, not in the gate."""
    from supply_demand import alert_gates as AG
    assert AG.floor_held_gate(_band(), None, read=None) is False
    assert AG.floor_held_gate(_band(), None, read={"state": "broken"}) is False
    assert AG.floor_held_gate(_band(), None, read={"state": "intact"}) is True


def test_NEGATIVE_an_unknown_floor_still_fails_the_growth_alert(monkeypatch, live):
    """Restoring the tri-state must not let an unknown through to a push —
    and since 2026-09-14 the alert reads the floor LIVE, so "unknown" is a
    sweep_read that returns None on a live arrival."""
    from growth import alerts as A
    from supply_demand import alert_gates as AG
    monkeypatch.setattr(A, "_bands_for", lambda s: [{"kind": "demand", "lo": 60.0, "hi": 62.0},
                                                    {"kind": "supply", "lo": 80.0, "hi": 82.0}])
    monkeypatch.setattr(AG, "sweep_read", lambda *a, **k: None)
    assert not A.candidates([row()], snapshot={"HHH": snap(61.55)}, now=NOW)
