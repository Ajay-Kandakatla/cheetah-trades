"""Auto-Pilot risk contracts — source-guard + functional locks.

Guards backend/trading/risk_rules.py against silent drift the same way
test_sepa_contracts.py guards the scanner: the constants below are LOCKED to
docs/sepa/risk_management_methodology.md and to printed pages of Minervini,
*Trade Like a Stock Market Wizard* (2013), pp.291-315. Changing ANY of them
is a Rule #4 methodology change: page-cited doc update + behavioral test +
this contract, with explicit user sign-off BEFORE code.

Two layers:
  1. SOURCE-TEXT guard — the exact constant assignments and page-cite strings
     must exist verbatim in risk_rules.py (catches a "quick tweak" that keeps
     the import surface but moves a number).
  2. FUNCTIONAL locks — sweep the live functions: no input may ever produce a
     stop > 10% (p.299/p.301) or a profit target below 2:1 (p.301).

Host-runnable (py3.9, stdlib only):
    cd backend && python3 -m pytest tests/test_trading_contracts.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

RISK_RULES_PATH = os.path.join(os.path.dirname(__file__), "..",
                               "trading", "risk_rules.py")


def _source():
    with open(RISK_RULES_PATH, encoding="utf-8") as fh:
        return fh.read()


# --- Locked constants (docs/sepa/risk_management_methodology.md rule table) --

REQUIRED_SOURCE_TOKENS = [
    # p.299 + p.301: the absolute 10% line — no rule or override exceeds it.
    "ABS_MAX_STOP_PCT = 10.0",
    # p.311: "If you normally cut losses at 7 to 8 percent, cut them at 5 to 6".
    "NORMAL_STOP_BAND = (7.0, 8.0)",
    "DIFFICULT_STOP_BAND = (5.0, 6.0)",
    # p.301: "at least a 2:1 win/loss ratio ... I shoot for 3:1."
    "MIN_REWARD_RISK = 2.0",
    # p.308: at 3x the initial risk, move the stop to at least breakeven.
    "BREAKEVEN_AT_RISK_MULTIPLE = 3.0",
    # p.312: "between 4 and 6 stocks" (engine cap 5); optimal size 25%.
    "MAX_POSITIONS = 5",
    "MAX_POSITION_FRACTION = 0.25",
    # p.304: losing streak -> halve size after 3 consecutive stop-outs.
    "STREAK_HALVE_AFTER = 3",
]

REQUIRED_PAGE_CITES = ["p.299", "p.301", "p.308", "p.311", "p.312"]


def test_risk_constants_locked_in_source():
    """The exact assignments must exist verbatim in trading/risk_rules.py.
    If this fails, someone moved a book number — revert, or follow Rule #4
    (page-cited methodology doc + behavioral test + user sign-off) first."""
    src = _source()
    for token in REQUIRED_SOURCE_TOKENS:
        assert token in src, (
            f"LOCKED constant drifted or was renamed: `{token}` not found in "
            f"trading/risk_rules.py. This is a Minervini Ch.13 book number "
            f"(docs/sepa/risk_management_methodology.md) — Rule #4 applies."
        )


def test_page_cites_present_in_source():
    """Every formula in risk_rules.py traces to a printed page (Rule #1).
    The page anchors must never be stripped from the source."""
    src = _source()
    for cite in REQUIRED_PAGE_CITES:
        assert cite in src, (
            f"page cite `{cite}` missing from trading/risk_rules.py — the "
            f"source map to Trade Like a Stock Market Wizard pp.291-315 is "
            f"part of the contract."
        )


def test_constants_importable_and_equal():
    """Belt + suspenders: the module-level values must equal the locked
    numbers at runtime, not just in the source text."""
    from trading import risk_rules as rr
    assert rr.ABS_MAX_STOP_PCT == 10.0
    assert rr.NORMAL_STOP_BAND == (7.0, 8.0)
    assert rr.DIFFICULT_STOP_BAND == (5.0, 6.0)
    assert rr.MIN_REWARD_RISK == 2.0
    assert rr.STRETCH_REWARD_RISK == 3.0
    assert rr.BREAKEVEN_AT_RISK_MULTIPLE == 3.0
    assert rr.MAX_POSITIONS == 5
    assert rr.MAX_POSITION_FRACTION == 0.25
    assert rr.STREAK_HALVE_AFTER == 3
    assert rr.STREAK_MULTIPLIERS == (1.0, 0.5, 0.25)
    assert rr.DEFAULT_STOP_PCT == 7.0
    assert rr.HALF_AVG_GAIN_MIN_TRADES == 20
    assert rr.NORMAL_PROFIT_BAND == (15.0, 20.0)
    assert rr.DIFFICULT_PROFIT_BAND == (10.0, 12.0)


# --- Functional locks --------------------------------------------------------

def test_initial_stop_never_exceeds_10pct_any_input():
    """p.299/p.301 functional lock: sweep regimes x bases x requests — there
    is NO path to a stop wider than 10%. This is the line Ajay's real money
    sits behind; it must hold for adversarial inputs too."""
    from trading.risk_rules import ABS_MAX_STOP_PCT, initial_stop
    for entry in (0.37, 2.5, 18.66, 50.0, 100.0, 333.0, 9999.99):
        for regime in ("normal", "difficult"):
            plans = [initial_stop(entry, regime)]
            for req in (0.1, 1, 5, 7, 8, 9.99, 10, 10.01, 12, 50, 1e6):
                plans.append(initial_stop(entry, regime, requested_pct=req))
            for avg_gain in (1.0, 8.0, 15.0, 30.0, 64.0, 400.0):
                for n in (0, 19, 20, 21, 10_000):
                    plans.append(initial_stop(entry, regime,
                                              avg_gain_pct=avg_gain,
                                              closed_trades=n))
            for plan in plans:
                assert plan.stop_pct <= ABS_MAX_STOP_PCT, (
                    f"10% cap breached: {plan} (entry={entry}, "
                    f"regime={regime})"
                )
                # stop_price < entry only asserted where the cent grid can
                # represent the distance — sub-dollar entries collapse to the
                # entry price under round(,2): see the skip-marked BUG-REPORT
                # test in test_risk_rules.py (test_subdollar_stop_rounding...).
                if entry >= 1.0:
                    assert plan.stop_price < entry


def test_difficult_regime_never_wider_than_6pct():
    """p.311 + p.308-309 functional lock: in a difficult tape no basis —
    request, half-average-gain, default — may widen the stop past 6%."""
    from trading.risk_rules import DIFFICULT_STOP_BAND, initial_stop
    for req in (None, 4, 6, 7, 9, 12):
        plan = initial_stop(100.0, "difficult", requested_pct=req)
        assert plan.stop_pct <= DIFFICULT_STOP_BAND[1], plan
    plan = initial_stop(100.0, "difficult", avg_gain_pct=40.0,
                        closed_trades=100)
    assert plan.stop_pct <= DIFFICULT_STOP_BAND[1], plan


def test_profit_target_reward_risk_never_below_2():
    """p.301 functional lock: for every regime and every stop the engine can
    produce (1%..10% in 0.05 steps), reward:risk >= 2.0. The p.311 band cap
    may only apply when it does not break 2:1."""
    from trading.risk_rules import MIN_REWARD_RISK, profit_target
    for regime in ("normal", "difficult"):
        for i in range(20, 201):                       # 1.00% .. 10.05%
            stop = i * 0.05
            t = profit_target(100.0, stop, regime)
            assert t["reward_risk"] >= MIN_REWARD_RISK, (
                f"2:1 floor broken: regime={regime}, stop={stop}%, {t}"
            )
            # Unrounded cross-check so a friendly round() can't hide a breach.
            assert t["target_pct"] >= MIN_REWARD_RISK * stop - 0.005, (
                f"target_pct below 2x stop: regime={regime}, stop={stop}%, {t}"
            )


def test_breakeven_trigger_matches_book_example():
    """p.308 functional lock: buy $50, stop $47.50 -> trigger $57.50."""
    from trading.risk_rules import breakeven_trigger
    assert breakeven_trigger(50.0, 47.50) == 57.50


# --- Auto-entry: engine params (owner choices, NOT book numbers) -------------
# trading/auto_entry.py's hybrid-trigger constants are ENGINE parameters
# chosen by the owner (Ajay) — Minervini gives the setup + risk math, not an
# entries/day cap, a RelVol floor, a session-half cutoff, an extension cap
# number, or a $5k paper-trial ceiling. Locked here so a drift is a deliberate
# owner decision (docs/sepa/auto_entry_methodology.md "engine parameters vs
# book numbers"), never a silent tweak.

AUTO_ENTRY_PATH = os.path.join(os.path.dirname(__file__), "..",
                               "trading", "auto_entry.py")
SCANNER_PATH = os.path.join(os.path.dirname(__file__), "..",
                            "sepa", "scanner.py")

ENGINE_PARAM_TOKENS = [
    "MAX_AUTO_ENTRIES_PER_DAY = 2",
    "AUTO_RELVOL_MIN = 1.5",
    "FIRST_HALF_FRACTION = 0.5",
    # Mirrors sepa.scanner.BUYABLE_MAX_EXT_PCT (p.224 anchor, user-approved
    # 3% house value 2026-06-09) — cross-locked against the scanner below.
    "MAX_EXTENSION_PCT = 3.0",
    "DEFAULT_EQUITY_CAP = 5000.0",
]


def _auto_entry_source():
    with open(AUTO_ENTRY_PATH, encoding="utf-8") as fh:
        return fh.read()


def test_auto_entry_engine_params_locked_in_source():
    """The five hybrid-trigger constants must exist verbatim. If this fails,
    an engine parameter moved — that's an OWNER decision (Ajay sign-off +
    doc update), not a book change, but it must never happen silently."""
    src = _auto_entry_source()
    for token in ENGINE_PARAM_TOKENS:
        assert token in src, (
            f"engine parameter drifted or was renamed: `{token}` not found "
            f"in trading/auto_entry.py — these are owner-chosen knobs "
            f"(docs/sepa/auto_entry_methodology.md); update doc + tests "
            f"WITH sign-off, never silently."
        )


def test_auto_entry_params_importable_and_equal():
    from trading import auto_entry as ae
    assert ae.MAX_AUTO_ENTRIES_PER_DAY == 2
    assert ae.AUTO_RELVOL_MIN == 1.5
    assert ae.FIRST_HALF_FRACTION == 0.5
    assert ae.MAX_EXTENSION_PCT == 3.0
    assert ae.DEFAULT_EQUITY_CAP == 5000.0
    assert ae.AUTO_MIN_SCORE == 70.0


def test_extension_cap_mirrors_scanner_buy_zone():
    """MAX_EXTENSION_PCT deliberately MIRRORS the scanner's is_buyable
    buy-zone ceiling (sepa/scanner.py BUYABLE_MAX_EXT_PCT, book p.224
    concept, user-approved 3%). Not imported (scanner pulls pandas at
    import time), so both source tokens are locked together here — moving
    either one alone breaks this test."""
    with open(SCANNER_PATH, encoding="utf-8") as fh:
        scanner_src = fh.read()
    assert "BUYABLE_MAX_EXT_PCT = 3.0" in scanner_src, (
        "sepa/scanner.py BUYABLE_MAX_EXT_PCT moved — auto_entry."
        "MAX_EXTENSION_PCT mirrors it and must move WITH it (owner sign-off)."
    )
    assert "MAX_EXTENSION_PCT = 3.0" in _auto_entry_source()


def test_auto_entry_never_submits_to_broker_directly():
    """Invariant: entries.enter() is the ONLY buy path. auto_entry.py must
    not contain a single direct broker submit_*/replace/cancel/close call —
    every order flows through entries.enter so armed / sizing / equity cap /
    never-average-down / earnings always apply."""
    src = _auto_entry_source()
    for forbidden in ("submit_", "replace_order", "cancel_order",
                      "close_position"):
        assert forbidden not in src, (
            f"trading/auto_entry.py contains `{forbidden}` — auto entries "
            f"must flow through entries.enter(), never the broker directly."
        )
    assert "entries.enter(" in src


def test_position_never_exceeds_quarter_of_equity():
    """p.312 functional lock: allocation <= 25% of equity at every price and
    streak level (whole-share flooring only ever shrinks it)."""
    from trading.risk_rules import MAX_POSITION_FRACTION, position_size
    for equity in (1_000.0, 20_000.0, 128_000.0):
        for price in (0.9, 7.77, 50.0, 333.0, 4_900.0):
            for losses in (0, 2, 3, 5, 6, 12):
                s = position_size(equity, price, consecutive_losses=losses)
                assert s["allocation"] <= equity * MAX_POSITION_FRACTION + 1e-9, (
                    f"25% cap breached: equity={equity}, price={price}, "
                    f"losses={losses}, {s}"
                )
                assert s["shares"] == int(s["shares"])
