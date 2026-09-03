"""0DTE — the board, the strike picker, the regime read and the ledger.

Every threshold in `zero_dte` is a house value with no study behind it, and the
module says so. These tests therefore do NOT assert that the rule is good. They
assert the things that can be true or false regardless:

  * the arithmetic is right and never emits NaN into JSON
  * a row that cannot support a number publishes None instead of guessing
  * the ordering never lets missing data look like the best row
  * the honesty stays attached — the caveats are load-bearing, not decoration

Fixtures are hand-built chain rows, not recordings, so a shape change in the
feed surfaces as a failing contract test rather than a silently empty board.
"""
import math
import os
import sys

import pytest

_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, ".."))

from options import zero_dte as Z            # noqa: E402
from options import zero_dte_history as H    # noqa: E402


def mk(strike, bid, ask, delta, *, typ="call", theta=-1.0, iv=0.20,
       vol=10_000, oi=1_000, gamma=0.05):
    """One snapshot contract in the shape Massive/Polygon actually returns."""
    return {
        "details": {"ticker": f"O:X{strike}", "strike_price": strike,
                    "contract_type": typ, "expiration_date": "2026-08-24"},
        "last_quote": {"bid": bid, "ask": ask, "bid_size": 10, "ask_size": 10},
        "greeks": {"delta": delta, "gamma": gamma, "theta": theta},
        "implied_volatility": iv,
        "open_interest": oi,
        "day": {"volume": vol},
    }


# ── contract_metrics ─────────────────────────────────────────────────────────
def test_the_cost_arithmetic_is_what_it_claims():
    # SPY's real 764 call, 2026-08-24: 0.09/0.10, delta 0.214, spot 763.71.
    m = Z.contract_metrics(mk(764, 0.09, 0.10, 0.214), 763.71)
    assert m["spread"] == pytest.approx(0.01, abs=1e-9)
    assert m["spread_pct"] == pytest.approx(10.5, abs=0.1)
    # Breakeven: 0.01 of option = 0.01/0.214 = $0.0467 of underlying = 0.006%.
    assert m["breakeven_move_pct"] == pytest.approx(0.006, abs=0.001)
    # Double: 0.10/0.214 = $0.467 of underlying = 0.061%.
    assert m["double_move_pct"] == pytest.approx(0.061, abs=0.002)


def test_theta_burn_is_a_share_of_premium_and_may_exceed_100():
    """The headline risk. Measured at 787% on SPY's own suggestion — a number
    that looks like a bug and is not, so it must not be clamped."""
    m = Z.contract_metrics(mk(764, 0.09, 0.10, 0.214, theta=-0.78), 763.71)
    assert m["theta_burn_pct"] == pytest.approx(780.0, abs=1.0)


def test_a_missing_delta_yields_None_not_a_partial_row():
    """Every derived number divides by delta. A row that silently defaulted it
    would publish confident nonsense in four fields at once."""
    c = mk(764, 0.09, 0.10, 0.214)
    c["greeks"]["delta"] = None
    assert Z.contract_metrics(c, 763.71) is None


def test_a_crossed_book_is_refused():
    """ask < bid is bad data, not a free trade."""
    assert Z.contract_metrics(mk(764, 0.50, 0.10, 0.30), 763.71) is None


def test_a_zero_ask_is_refused_rather_than_dividing_by_it():
    assert Z.contract_metrics(mk(770, 0.0, 0.0, 0.02), 763.71) is None


def test_no_metric_is_ever_NaN_or_inf():
    """NaN reaching JSON is how the SSE stream broke the scanner FE once."""
    m = Z.contract_metrics(mk(764, 0.09, 0.10, 0.214), 763.71)
    for k, v in m.items():
        if isinstance(v, float):
            assert math.isfinite(v), k


def test_a_put_uses_ABSOLUTE_delta_so_its_moves_are_positive():
    """A put's delta is negative; a negative 'move to double' is meaningless."""
    m = Z.contract_metrics(mk(760, 0.20, 0.22, -0.30, typ="put"), 763.71)
    assert m["double_move_pct"] > 0
    assert m["breakeven_move_pct"] > 0


# ── is_tradeable — the floors, and the negative cases ────────────────────────
def test_the_wildly_traded_penny_strike_is_REFUSED():
    """SPY's 765 call did 828,288 contracts at a 66% spread on 2026-08-24.
    Volume is not tradeability, which is the entire reason a floor exists."""
    m = Z.contract_metrics(mk(765, 0.01, 0.02, 0.039, vol=828_288), 763.71)
    assert m["spread_pct"] > 60
    assert Z.is_tradeable(m) is False


def test_a_contract_with_no_bid_cannot_be_exited_so_it_is_refused():
    m = Z.contract_metrics(mk(766, 0.0, 0.01, 0.25), 763.71)
    assert Z.is_tradeable(m) is False


def test_deep_ITM_is_refused_as_mostly_intrinsic():
    m = Z.contract_metrics(mk(700, 63.0, 63.5, 0.97), 763.71)
    assert Z.is_tradeable(m) is False


def test_an_untraded_strike_is_refused_however_tight_the_quote():
    m = Z.contract_metrics(mk(764, 0.50, 0.52, 0.35, vol=3), 763.71)
    assert Z.is_tradeable(m) is False


def test_REGRESSION_a_six_tick_option_is_refused_however_good_it_looks():
    """The bug that shipped on 2026-08-24 and led the live board.

    AMZN 262.5 call, bid 0.05 / ask 0.06, delta 0.3328, 90,278 contracts traded.
    It cleared EVERY other floor — mid-band delta, 18.2% spread against a 25%
    cap, deep volume — and ranked #1 at "0.07x", because a six-tick option
    doubles on a one-cent uptick.
    """
    m = Z.contract_metrics(mk(262.5, 0.05, 0.06, 0.3328, vol=90_278), 262.0)
    assert MIN_DELTA_OK(m) and m["spread_pct"] < Z.MAX_SPREAD_PCT
    assert m["day_volume"] > Z.MIN_DAY_VOLUME
    assert Z.is_tradeable(m) is False        # refused on premium alone


def MIN_DELTA_OK(m):
    return Z.MIN_DELTA <= abs(m["delta"]) <= Z.MAX_DELTA


def test_the_premium_floor_is_what_refuses_it_not_some_other_gate():
    """Pinning WHY it is refused. If a future edit loosens MIN_ASK, this fails
    rather than the board quietly promoting tick-noise again."""
    cheap = Z.contract_metrics(mk(262.5, 0.05, 0.06, 0.3328, vol=90_278), 262.0)
    dear = Z.contract_metrics(mk(262.5, 0.95, 1.00, 0.3328, vol=90_278), 262.0)
    assert Z.is_tradeable(cheap) is False
    assert Z.is_tradeable(dear) is True       # identical but for the premium


def test_a_contract_at_exactly_the_premium_floor_is_allowed():
    """A floor excludes what is BELOW it. An off-by-one here would silently
    shrink an already-thin board."""
    m = Z.contract_metrics(mk(100, 0.19, Z.MIN_ASK, 0.35), 100.0)
    assert m["ask"] == Z.MIN_ASK
    assert Z.is_tradeable(m) is True


def test_the_floor_bites_cheapness_NOT_low_volatility():
    """TSLA's 1.89 suggestion must survive — the floor targets tick-noise, not
    expensive names. Refusing it would gut the board it exists to protect."""
    m = Z.contract_metrics(mk(347.5, 1.53, 1.89, 0.5925, vol=12_781), 348.66)
    assert Z.is_tradeable(m) is True


def test_the_board_can_no_longer_be_LED_by_the_cheapest_contract():
    """The structural version of the bug. `double_move_pct` is
    premium/(delta*spot), so it falls as premium falls — ranking on it promotes
    the cheapest contract on the tape every time. The floor is what stops that
    reaching the board at all."""
    chain = [mk(262.5, 0.05, 0.06, 0.3328, vol=90_278),      # the offender
             mk(263, 0.95, 1.00, 0.3400, vol=50_000)]
    m = [x for x in (Z.contract_metrics(c, 262.0) for c in chain) if x]
    # The cheap one genuinely scores "better" on the raw metric...
    assert m[0]["double_move_pct"] < m[1]["double_move_pct"]
    # ...and is still not what gets suggested.
    assert Z.pick_contract(m, "call")["ask"] == 1.00


def test_is_tradeable_on_None_is_False_not_an_exception():
    assert Z.is_tradeable(None) is False


# ── pick_contract ────────────────────────────────────────────────────────────
def _chain(spot=100.0):
    rows = [mk(98, 2.0, 2.1, 0.62), mk(100, 1.0, 1.05, 0.36),
            mk(101, 0.7, 0.74, 0.34), mk(105, 0.02, 0.06, 0.05)]
    return [Z.contract_metrics(c, spot) for c in rows]


def test_the_pick_is_nearest_to_the_target_delta():
    m = [x for x in _chain() if x]
    got = Z.pick_contract(m, "call")
    assert got["delta"] in (0.36, 0.34)


def test_a_delta_tie_is_broken_on_the_TIGHTER_spread_not_the_cheaper_price():
    """0.36 and 0.34 are equidistant from 0.35. The 101 is cheaper in dollars
    and wider in percent; cheapness is not the tie-break."""
    m = [x for x in _chain() if x]
    got = Z.pick_contract(m, "call")
    assert got["strike"] == 100        # 4.9% spread vs the 101's 5.6%
    assert got["spread_pct"] < 5.5


def test_nothing_clearing_the_floors_returns_None_not_the_least_bad_row():
    """The after-close case, measured live: 5 of 13 names had no tradeable
    contract at all. None is the honest answer; a 200%-spread penny is not."""
    m = [Z.contract_metrics(mk(105, 0.00, 0.01, 0.02), 100.0)]
    assert Z.pick_contract([x for x in m if x], "call") is None


def test_the_href_lands_on_a_tab_that_EXISTS():
    """Shipped once pointing at ?tab=zero_dte, which is not in SepaCandidate's
    TABS — every tile silently fell back to the chart tab. Read from the real
    frontend source so the two cannot drift apart again."""
    # TABS moved to lib/sepaTabs.ts on 2026-09-03 (Supply / Demand default).
    tsx = os.path.join(_HERE, "..", "..", "frontend", "src", "lib", "sepaTabs.ts")
    if not os.path.exists(tsx):                    # backend-only checkout
        pytest.skip("frontend not present")
    with open(tsx) as fh:
        src = fh.read()
    marker = "const TABS: Tab[] = ["
    i = src.index(marker) + len(marker)      # past the `Tab[]` brackets
    tabs = src[i:src.index("]", i)]
    from chart_maps import board as B
    href = B._href("NVDA", "options")
    assert "tab=options" in href
    assert "'options'" in tabs
    assert "'zero_dte'" not in tabs                 # the tab that never existed


def test_the_picker_never_returns_the_other_side():
    m = [x for x in _chain() if x]
    assert Z.pick_contract(m, "put") is None      # this chain is calls only


# ── expected move — the cross-symbol scale ───────────────────────────────────
def test_expected_move_is_one_session_of_implied_vol():
    m = [x for x in [Z.contract_metrics(mk(100, 1.0, 1.05, 0.36, iv=0.32), 100.0)] if x]
    # 32% annualised / sqrt(252) = 2.016% for one session.
    assert Z.expected_move_pct(m, 100.0) == pytest.approx(2.016, abs=0.01)


def test_expected_move_averages_the_ATM_call_and_put():
    """One stale quote must not set the scale for the whole row."""
    m = [Z.contract_metrics(mk(100, 1.0, 1.05, 0.36, iv=0.20), 100.0),
         Z.contract_metrics(mk(100, 1.0, 1.05, -0.36, typ="put", iv=0.40), 100.0)]
    got = Z.expected_move_pct([x for x in m if x], 100.0)
    assert got == pytest.approx(100 * 0.30 / (252 ** 0.5), abs=0.01)


def test_expected_move_with_no_iv_is_None_not_zero():
    """Zero would make `moves_needed` divide by it and report infinity."""
    m = [Z.contract_metrics(mk(100, 1.0, 1.05, 0.36, iv=0), 100.0)]
    assert Z.expected_move_pct([x for x in m if x], 100.0) is None


def test_moves_needed_makes_two_different_names_COMPARABLE():
    """The whole point. Measured 2026-08-24: SPY needed 0.059% and NVDA 0.693%
    — a 12x gap in raw percent that is only 2.6x in each name's own sigma."""
    spy = {"double_move_pct": 0.059}
    nvda = {"double_move_pct": 0.693}
    assert Z.moves_needed(spy, 0.307) == pytest.approx(0.19, abs=0.01)
    assert Z.moves_needed(nvda, 1.396) == pytest.approx(0.50, abs=0.01)


def test_moves_needed_with_no_expected_move_is_None_not_infinity():
    assert Z.moves_needed({"double_move_pct": 0.5}, None) is None
    assert Z.moves_needed({"double_move_pct": 0.5}, 0.0) is None


# ── the regime banner ────────────────────────────────────────────────────────
def _gex(net, cw=101.0, pw=99.0, flip=None, cov=95.0, nodes=None):
    return {"net_gex_dollars": net,
            "regime": "pinning" if net > 0 else "amplifying",
            "call_wall": cw, "put_wall": pw, "flip_strike": flip,
            "magnet_strike": cw, "oi_coverage_pct": cov,
            "top_nodes": nodes if nodes is not None
            else [{"strike": cw, "gex_dollars": net / 4.0}]}


def test_the_regime_is_TAKEN_from_opex_not_re_derived():
    """One owner for the sign rule. If opex ever flips its convention this must
    follow it, not silently disagree — so the verdict is read, never recomputed."""
    g = _gex(-500.0)
    g["regime"] = "pinning"            # deliberately contradicts the sign
    out = Z.regime_from_gex(g, 100.0)
    assert out["regime"] == Z.REGIME_PINNED


def test_a_net_smaller_than_its_largest_node_is_flagged_FRAGILE():
    """Demonstrated, not assumed: TSLA read +3.3M then -48.7M seconds apart on
    2026-08-24 — PINNED to AMPLIFYING — while one strike carried 137M."""
    g = _gex(48.7, nodes=[{"strike": 100.0, "gex_dollars": -137.0}])
    out = Z.regime_from_gex(g, 100.0)
    assert out["fragile"] is True
    assert out["net_vs_largest_node"] == pytest.approx(0.36, abs=0.01)
    assert "UNSETTLED" in out["note"]


def test_a_net_LARGER_than_its_largest_node_is_not_flagged():
    """QQQ's real profile, 2026-08-24: net 2.36B against a 1.27B top node."""
    g = _gex(-2360.0, nodes=[{"strike": 100.0, "gex_dollars": -1271.0}])
    out = Z.regime_from_gex(g, 100.0)
    assert out["fragile"] is False
    assert "UNSETTLED" not in (out["note"] or "")


def test_an_out_of_reach_flip_is_SUPPRESSED_rather_than_drawn():
    """SPY's raw flip sat 29% from spot on a same-day expiry. The tape cannot
    reach it, so it is not a regime boundary — it is trivia that looks precise."""
    out = Z.regime_from_gex(_gex(-500.0, flip=71.0), 100.0, 0.31)
    assert out["flip_strike"] is None
    assert out["flip_out_of_reach_pct"] == pytest.approx(29.0, abs=0.1)
    assert out["below_flip"] is None


def test_a_reachable_flip_IS_kept_and_says_which_side():
    out = Z.regime_from_gex(_gex(-500.0, flip=100.2), 100.0, 1.0)
    assert out["flip_strike"] == 100.2
    assert out["below_flip"] is True
    assert "amplified" in out["note"]


def test_low_oi_coverage_downgrades_the_read_out_loud():
    """NVDA priced gamma on 75.7% of OI on 2026-08-24. A net computed from a
    fraction of the book is a guess wearing a number's clothes."""
    out = Z.regime_from_gex(_gex(-500.0, cov=75.7), 100.0)
    assert "low confidence" in out["note"]


def test_no_gamma_read_is_UNKNOWN_not_a_coin_flip():
    for bad in (None, {}, {"net_gex_dollars": None, "regime": ""}):
        assert Z.regime_from_gex(bad, 100.0)["regime"] == Z.REGIME_UNKNOWN


def test_a_pin_is_framed_as_the_RISK_because_this_board_BUYS_premium():
    """A pin is good news to a seller and bad news to a buyer. This board is
    for a buyer, and the wording must not borrow the seller's reading."""
    note = Z.regime_from_gex(_gex(500.0), 100.0)["note"]
    assert "fights that" in note and "theta is on the other side" in note


# ── ordering ─────────────────────────────────────────────────────────────────
def test_REGRESSION_a_row_with_no_tradeable_contract_sorts_LAST():
    """The Into Supply board shipped this bug: a degenerate key let missing
    data lead an alphabetical list that looked ranked."""
    rows = [{"symbol": "ZZZZ", "call": None, "put": None},
            {"symbol": "AAAA", "call": {"moves_needed": 0.5}, "put": None}]
    rows.sort(key=Z.sort_key)
    assert [r["symbol"] for r in rows] == ["AAAA", "ZZZZ"]


def test_the_board_ranks_on_SIGMAS_not_raw_percent():
    """Sorting on raw `double_move_pct` puts the lowest-vol name first every
    day for a reason that has nothing to do with the trade being better."""
    spy = {"symbol": "SPY", "call": {"double_move_pct": 0.059, "moves_needed": 0.19}}
    qqq = {"symbol": "QQQ", "put": {"double_move_pct": 0.033, "moves_needed": 0.08}}
    nvda = {"symbol": "NVDA", "call": {"double_move_pct": 0.693, "moves_needed": 0.50}}
    rows = sorted([spy, nvda, qqq], key=Z.sort_key)
    assert [r["symbol"] for r in rows] == ["QQQ", "SPY", "NVDA"]


def test_the_better_of_the_two_sides_ranks_the_row():
    r = {"symbol": "X", "call": {"moves_needed": 2.0}, "put": {"moves_needed": 0.1}}
    assert Z.sort_key(r)[1] == pytest.approx(0.1)


# ── session state ────────────────────────────────────────────────────────────
class _T:
    def __init__(self, h, m, wd=2):
        self.hour, self.minute, self._wd = h, m, wd

    def weekday(self):
        return self._wd


def test_after_the_close_the_board_says_it_is_NOT_live():
    """Measured 2026-08-24 after the bell: only 4 of 13 names carried any
    tradeable contract. Correct, but it must not read as broken."""
    st = Z.session_state(_T(16, 30))
    assert st["actionable"] is False and st["state"] == "post"
    assert "settled" in st["label"]


def test_the_final_hour_is_called_out_because_theta_goes_vertical():
    st = Z.session_state(_T(15, 10))
    assert st["state"] == "power" and st["actionable"] is True


def test_regular_hours_are_actionable():
    assert Z.session_state(_T(11, 0))["actionable"] is True


def test_the_weekend_is_never_actionable():
    assert Z.session_state(_T(11, 0, wd=5))["actionable"] is False


def test_before_the_open_is_not_actionable():
    assert Z.session_state(_T(8, 0))["state"] == "pre"


# ── the ledger ───────────────────────────────────────────────────────────────
def _row():
    return {"symbol": "NVDA", "expiry": "2026-08-24", "spot": 208.38,
            "gex_reliability": "single_name", "max_pain_pct": 4.38,
            "regime": {"regime": "AMPLIFYING", "net_gex": -5.0e7,
                       "inside_walls": True},
            "call": {"strike": 207.5, "bid": 0.9, "ask": 1.0, "spread_pct": 10.5,
                     "delta": 0.6945, "theta": -1.7, "theta_burn_pct": 166.0,
                     "iv": 0.35, "day_volume": 45349,
                     "breakeven_move_pct": 0.069, "double_move_pct": 0.691}}


def test_a_recorded_call_freezes_what_the_board_SAID():
    d = H._call_doc(_row(), "call", "2026-08-24")
    assert d["strike"] == 207.5 and d["ask"] == 1.0
    assert d["spot_at_call"] == 208.38
    assert d["double_move_pct"] == 0.691
    assert d["regime"] == "AMPLIFYING"


def test_a_half_recorded_suggestion_is_REFUSED():
    """It would enter the denominator and never leave it."""
    r = _row()
    r["call"]["double_move_pct"] = None
    assert H._call_doc(r, "call", "2026-08-24") is None


def test_the_id_is_idempotent_on_symbol_date_side_and_strike():
    a = H._call_doc(_row(), "call", "2026-08-24")["_id"]
    b = H._call_doc(_row(), "call", "2026-08-24")["_id"]
    assert a == b and "NVDA" in a and "207.5" in a


def test_every_recorded_row_carries_its_own_limitation():
    """Any future reader of this collection must see the caveat without having
    to find the module that wrote it."""
    d = H._call_doc(_row(), "call", "2026-08-24")
    assert d["path_blind"] is True
    assert d["graded_on"] == "underlying_daily_bar"


def test_a_missing_side_records_nothing_rather_than_an_empty_row():
    assert H._call_doc(_row(), "put", "2026-08-24") is None


# ── grading ──────────────────────────────────────────────────────────────────
def _doc(side="call", spot=100.0, be=0.5, dbl=2.0):
    return {"side": side, "spot_at_call": spot,
            "breakeven_move_pct": be, "double_move_pct": dbl}


def test_a_call_is_graded_on_the_HIGH_measured_from_the_recorded_spot():
    g = H.grade(_doc(), {"high": 103.0, "low": 99.0, "close": 101.0})
    assert g["move_outcome"] == H.MOVE_DOUBLE
    assert g["best_move_pct"] == pytest.approx(3.0)
    assert g["close_move_pct"] == pytest.approx(1.0)


def test_a_put_is_graded_on_the_LOW_and_its_move_is_positive():
    g = H.grade(_doc(side="put"), {"high": 101.0, "low": 97.0, "close": 99.0})
    assert g["move_outcome"] == H.MOVE_DOUBLE
    assert g["best_move_pct"] == pytest.approx(3.0)
    assert g["close_move_pct"] == pytest.approx(1.0)


def test_clearing_the_spread_but_not_the_double_is_its_own_outcome():
    g = H.grade(_doc(), {"high": 101.0, "low": 99.0, "close": 100.5})
    assert g["move_outcome"] == H.MOVE_BREAKEVEN
    assert g["hit_breakeven"] is True and g["hit_double"] is False


def test_never_covering_the_cost_of_entry_is_no_move():
    g = H.grade(_doc(), {"high": 100.2, "low": 99.0, "close": 99.5})
    assert g["move_outcome"] == H.MOVE_NONE


def test_a_missing_bar_leaves_the_row_OPEN_rather_than_grading_it_a_loss():
    """A holiday, a data gap or a stale cache must not become a `no_move` in
    the denominator. Hit live on 2026-08-24: SPY and QQQ were a refresh behind
    and correctly stayed open while NVDA and TSLA graded."""
    assert H.grade(_doc(), None) is None
    assert H.grade(_doc(), {"high": None, "low": 99.0, "close": 100.0}) is None


def test_the_excursion_and_the_CLOSE_are_recorded_separately():
    """The number that survives path blindness. Demonstrated on day one: NVDA
    ran 3.47% intraday and closed +0.05% — 'hit the double' and 'held it' gave
    opposite answers about the same day."""
    g = H.grade(_doc(), {"high": 103.5, "low": 99.0, "close": 100.05})
    assert g["hit_double"] is True
    assert g["close_beat_breakeven"] is False


def test_a_zero_or_missing_spot_is_refused_rather_than_dividing_by_it():
    assert H.grade(_doc(spot=0.0), {"high": 1.0, "low": 1.0, "close": 1.0}) is None
    assert H.grade(_doc(spot=None), {"high": 1.0, "low": 1.0, "close": 1.0}) is None


def test_num_refuses_bool_so_True_never_becomes_a_price():
    assert H._num(True) is None and Z._f(True) is None


# ── source guards ────────────────────────────────────────────────────────────
# The caveats on this feature are load-bearing: it ships with no backtest, no
# measured edge and a grading rule that cannot see the intraday path. A future
# edit that quietly drops one of those would leave a board that looks measured
# and is not. These fail when that happens.
import ast as _ast    # noqa: E402
import io             # noqa: E402
import tokenize       # noqa: E402

_HERE = os.path.dirname(__file__)
_SRC = os.path.join(_HERE, "..", "options")


def _text(name: str) -> str:
    with open(os.path.join(_SRC, name)) as fh:
        return fh.read()


def _code(name: str) -> str:
    """Source with docstrings and comments BLANKED IN PLACE.

    Four contract tests were written once that substring-matched prose in a
    docstring and passed while the code said the opposite. Guards must read the
    code, so the prose is removed first.

    Blanked in place rather than re-joined: a token list joined by whitespace
    breaks adjacency, so `MIN_DELTA =` stops matching `MIN_DELTA` `=`. Writing
    spaces over each prose token leaves every other character at its original
    offset, so what remains reads exactly as it was written.
    """
    src = _text(name)
    starts = [0]
    for ln in src.splitlines(keepends=True):
        starts.append(starts[-1] + len(ln))

    buf = list(src)
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except tokenize.TokenError:
        return src
    for tok in toks:
        stripped = tok.line.strip()
        is_doc = tok.type == tokenize.STRING and (
            stripped[:3] in ('"""', "'''") or stripped[:4] in ('r"""', "r'''"))
        if tok.type != tokenize.COMMENT and not is_doc:
            continue
        a = starts[tok.start[0] - 1] + tok.start[1]
        b = starts[tok.end[0] - 1] + tok.end[1]
        for i in range(a, min(b, len(buf))):
            if buf[i] != "\n":
                buf[i] = " "
    return "".join(buf)


def test_the_gamma_SIGN_RULE_is_never_re_derived_here():
    """`opex` owns it and pins it in its own docstring. A second implementation
    is a second chance to disagree about a day."""
    code = _code("zero_dte.py")
    assert "net > 0" not in code and "net_gex > 0" not in code
    assert '"pinning"' in code            # it reads opex's verdict instead


def test_the_module_never_claims_a_backtest_it_cannot_run():
    for name in ("zero_dte.py", "zero_dte_history.py"):
        t = _text(name).lower()
        assert "backtest" in t, name      # it must ADDRESS the absence
        assert "cannot be backtested" in t or "no intraday option" in t, name


def test_the_disclaimer_states_there_is_no_measured_edge():
    d = Z.DISCLAIMER.lower()
    assert "no measured edge" in d
    assert "not advice" in d
    assert "recorded" in d                # the ledger is the stated remedy


def test_the_ledger_field_is_named_move_outcome_and_never_plain_outcome():
    """`outcome` would be read as P&L. It is not P&L — it is whether the
    UNDERLYING travelled far enough, which is necessary and not sufficient."""
    code = _code("zero_dte_history.py")
    assert '"move_outcome"' in code
    assert '"outcome"' not in code


def test_accuracy_cannot_report_a_win_rate_without_the_caveat():
    code = _code("zero_dte_history.py")
    i = code.index("def accuracy")
    body = code[i:]
    assert '"caveat"' in body
    assert '"held_to_close_pct"' in body   # the number immune to path blindness


def test_every_house_threshold_is_declared_in_ONE_place():
    """Scattered magic numbers are how two boards end up on two scales. Into
    Supply imports every threshold from the demand scan for the same reason."""
    code = _code("zero_dte.py")
    for const in ("MIN_DELTA", "MAX_DELTA", "TARGET_DELTA", "MAX_SPREAD_PCT",
                  "MIN_DAY_VOLUME", "MIN_BID", "MIN_ASK",
                  "FLIP_RELEVANT_SIGMAS"):
        assert code.count(f"{const} =") == 1, const


def test_the_pure_functions_take_no_network():
    """metrics / picking / regime / grading must stay testable without a feed,
    which is what let all 50 tests above run in 0.11s."""
    tree = _ast.parse(_text("zero_dte.py"))
    pure = {"contract_metrics", "is_tradeable", "pick_contract",
            "expected_move_pct", "moves_needed", "regime_from_gex", "sort_key"}
    for node in _ast.walk(tree):
        if isinstance(node, _ast.FunctionDef) and node.name in pure:
            body = _ast.dump(node)
            assert "requests" not in body, node.name
            assert "_fetch_contracts" not in body, node.name


def test_the_ledger_grades_from_the_daily_bar_and_says_so_on_the_row():
    code = _code("zero_dte_history.py")
    assert '"path_blind": True' in code
    assert '"graded_on": "underlying_daily_bar"' in code
