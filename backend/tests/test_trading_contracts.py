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
LIVE_GATE_PATH = os.path.join(os.path.dirname(__file__), "..",
                              "sepa", "live_gate.py")

ENGINE_PARAM_TOKENS = [
    "MAX_AUTO_ENTRIES_PER_DAY = 2",
    "AUTO_RELVOL_MIN = 1.5",
    "FIRST_HALF_FRACTION = 0.5",
    # Mirrors sepa.scanner.BUYABLE_MAX_EXT_PCT (p.224 anchor, user-approved
    # 3% house value 2026-06-09) — cross-locked against the scanner below.
    "MAX_EXTENSION_PCT = 3.0",
    "DEFAULT_EQUITY_CAP = 5000.0",
    # Volume-projection trust floor (TLSW p.229; raised 60 -> 120 min with
    # Ajay sign-off 2026-07-12 to match the book's own 2-hour demonstration).
    "VOL_CONFIRM_MIN_FRAC = round(120.0 / 390.0, 4)",
    # Funnel RS floor (TLSW p.79 criterion 8: "no less than 70, and preferably
    # in the 80s or 90s" — floor sits at the book's preferred band; Ajay
    # sign-off 2026-07-12 after the low-RS audit: winners RS 87+, three of
    # four losers RS <= 82).
    "AUTO_MIN_RS = 80.0",
    # Scan-trust universe floor — rs_rank is a percentile WITHIN the scanned
    # universe, so small manual scans distort it (EIX read 64-75 across
    # same-day runs); the engine only trades market-sized scans.
    "MIN_RS_UNIVERSE = 500",
]

# Leaky-pivot suppressor constants live in sepa/pivot_leakage.py (shared
# with the scanner so the SEPA pages stamp the IDENTICAL read; Minervini X
# 2026 "pivot leakage"; owner numbers, Ajay sign-off 2026-07-12).
PIVOT_LEAKAGE_PATH = os.path.join(os.path.dirname(__file__), "..",
                                  "sepa", "pivot_leakage.py")
PIVOT_LEAK_TOKENS = [
    "PIVOT_LEAK_LOOKBACK = 10",
    "PIVOT_LEAK_MAX = 2",
    "PIVOT_LEAK_COOLOFF_DAYS = 5",
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
    # 70 -> 85 raised 2026-07-09 (failure autopsy: no winner scored under 87,
    # no loser over 84; n=6 HYPOTHESIS — config `auto_min_score` overrides
    # live so it can be tuned as the sample grows).
    assert ae.AUTO_MIN_SCORE == 85.0
    assert ae.VOL_CONFIRM_MIN_FRAC == round(120.0 / 390.0, 4)
    assert ae.AUTO_MIN_RS == 80.0
    assert ae.MIN_RS_UNIVERSE == 500


def test_rs_floor_cited_and_fails_closed_in_source():
    """The RS floor must stay anchored to TLSW p.79 criterion 8 wording AND
    keep its fail-closed shape (a row with NO rs_rank is never tradeable).
    The 2026-07-12 audit found the engine buying RS 66-79 names — both
    winners were RS 87+, so the floor sits at the book's preferred band."""
    src = _auto_entry_source()
    assert "80s or 90s" in src, (
        "the p.79 'preferably in the 80s or 90s' anchor left "
        "trading/auto_entry.py — the RS floor must keep its book cite")
    assert "rs is None or float(rs) < min_rs" in src, (
        "the fail-closed RS check changed shape — missing rs_rank MUST "
        "still be excluded (fail closed), never admitted")


def test_scan_trust_gate_locked_in_source():
    """scan_trusted() must stay wired into run() (never trade a stale or
    small-universe scan) and both floors must fail CLOSED on missing meta."""
    src = _auto_entry_source()
    assert "scan_trusted(_scan_meta())" in src, (
        "run() no longer consults scan_trusted — the engine would trade "
        "stale/small scans again (the EIX RS-66 hole)")
    assert 'out["reason"] = "untrusted_scan"' in src


def test_config_whitelist_passes_floor_overrides_through():
    """REGRESSION (2026-07-12 audit): exit_engine.get_config() whitelists its
    return keys and used to STRIP auto_min_score — the documented live
    override silently never reached the engine. Both floor overrides must
    survive the whitelist now."""
    eng_path = os.path.join(os.path.dirname(__file__), "..",
                            "trading", "exit_engine.py")
    with open(eng_path, encoding="utf-8") as fh:
        eng_src = fh.read()
    for key in ("auto_min_score", "auto_min_rs",
                "last_auto_entry_scan_warn_day", "progressive_exposure"):
        assert '"%s": doc.get("%s")' % (key, key) in eng_src, (
            "exit_engine.get_config() no longer passes `%s` through its "
            "whitelist — the live override dies silently again" % key)


# ── Progressive-exposure governor + leaky pivot (X-anchored, 2026-07-12) ─────

def test_progressive_governor_locked_and_min_composed():
    """Pilot sizing (TLSW pp.307-308 + Minervini's standing X rule) must keep
    its owner numbers, stay anchored to its sources, and compose with the
    p.304 streak multiplier via min() — never multiplication."""
    from trading import progressive as pg
    assert pg.PROGRESSIVE_WINDOW == 5
    assert pg.PROGRESSIVE_MIN_TRADES == 3
    assert pg.PILOT_MULTIPLIER == 0.5
    prog_path = os.path.join(os.path.dirname(__file__), "..",
                             "trading", "progressive.py")
    with open(prog_path, encoding="utf-8") as fh:
        src = fh.read()
    assert "pilot buys" in src and "pp.307-308" in src, (
        "the TLSW pilot-buys anchor left trading/progressive.py")
    assert "last 4 or 5 stocks" in src, (
        "the Minervini X 'last 4 or 5 stocks' quote left "
        "trading/progressive.py — the rule must keep its primary source")
    rr_path = os.path.join(os.path.dirname(__file__), "..",
                           "trading", "risk_rules.py")
    with open(rr_path, encoding="utf-8") as fh:
        rr_src = fh.read()
    assert "mult = min(mult, extra)" in rr_src, (
        "position_size no longer min()-composes the progressive governor "
        "with the p.304 streak — the two must never multiply")


def test_pyramid_add_cited_and_bounded():
    """Pyramid adds (TTLAC §3 Add and Reduce / §5 scale-up, TLSW pp.307-308)
    must stay: wired through entries.enter(top_up=...) (the ONLY buy path),
    sized as complete-to-full-NEVER-exceed (p.312 ceiling), and cited."""
    src = _auto_entry_source()
    assert "top_up=is_add" in src, (
        "run() no longer routes adds through entries.enter(top_up=...) — "
        "pyramid buys must use the single gated buy path")
    assert "Add and Reduce" in src and "pp.307-308" in src, (
        "the TTLAC/TLSW pyramid anchors left trading/auto_entry.py")
    entries_path = os.path.join(os.path.dirname(__file__), "..",
                                "trading", "entries.py")
    with open(entries_path, encoding="utf-8") as fh:
        en_src = fh.read()
    assert "add_shares = max(0, full_shares - held_qty)" in en_src, (
        "top-up sizing changed shape — adds must COMPLETE the position "
        "toward the p.312 ceiling, never exceed it")


def test_leaky_pivot_cited_and_intraday_only():
    """The leak suppressor must keep its X-post anchor, its owner numbers,
    stay wired into the INTRADAY path only (a full close above the pivot IS
    the volatility subsiding -> close-confirm stays exempt), fail OPEN on
    missing bars, and stay a SINGLE shared implementation — the engine and
    the SEPA scanner must read the identical rule."""
    with open(PIVOT_LEAKAGE_PATH, encoding="utf-8") as fh:
        leak_src = fh.read()
    assert "pivot leakage" in leak_src, (
        "the Minervini X 'pivot leakage' anchor left sepa/pivot_leakage.py")
    for token in PIVOT_LEAK_TOKENS:
        assert token in leak_src, (
            "leak parameter drifted: `%s` not in sepa/pivot_leakage.py "
            "(owner numbers — Ajay sign-off required)" % token)
    src = _auto_entry_source()
    assert "from sepa.pivot_leakage import" in src, (
        "auto_entry no longer imports the SHARED leak module — engine and "
        "scanner reads would drift apart")
    assert 'checks, "pivot_not_leaky"' in src, (
        "pivot_leaky is no longer wired into run()'s intraday path")
    from trading import auto_entry as ae
    assert ae.pivot_leaky(None, None, 100.0)[0] is False, (
        "pivot_leaky must fail OPEN on missing data")


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


# ── intraday volume projection: curve-aware, conservative (TLSW p.229) ──────

def test_intraday_volume_projection_is_curve_aware_and_conservative():
    """The engine's intraday RelVol gate must read a CURVE-AWARE projection
    (TLSW p.229), never the naive today_vol/session_fraction that bought CGNX
    on a faded opening pop. Two locks: (1) the curve is conservative
    (>= the elapsed fraction across the morning, so it never over-credits a
    hot open); (2) live_gate sources the projection from sepa.intraday_volume
    and no longer divides by the raw fraction. Changing the curve shape is an
    owner decision (docs/sepa/intraday_volume_methodology.md), never silent."""
    from sepa import intraday_volume as iv
    # (1) conservatism — the property the whole fix rests on.
    for f in (0.05, 0.10, 0.20, 0.30, 0.50):
        assert iv.expected_session_volume_fraction(f) >= f
    assert iv.expected_session_volume_fraction(1.0) == 1.0
    # a hot open reads BELOW the linear projection (CGNX 0.20x-by-frac-0.10).
    avg = 1_000_000.0
    curve = iv.projected_relvol(0.20 * avg, avg, 0.10)
    linear = round((0.20 * avg / 0.10) / avg, 2)
    assert curve < linear and curve < 1.5 <= linear

    # (2) live_gate wires it in, and the old linear form is gone.
    with open(LIVE_GATE_PATH, encoding="utf-8") as fh:
        lg = fh.read()
    assert "intraday_volume" in lg, (
        "sepa/live_gate.py must source projected RelVol from "
        "sepa.intraday_volume (TLSW p.229), not a flat ÷ session fraction.")
    assert "(today_vol / frac) / avg50" not in lg, (
        "the naive LINEAR projection is back in live_gate.py — that is the "
        "CGNX bug (over-credits a hot open). Use intraday_volume.")


ZONE_EDGE_ENTRY_PATH = os.path.join(os.path.dirname(__file__), "..",
                                    "trading", "zone_edge_entry.py")


def _zone_edge_entry_source():
    with open(ZONE_EDGE_ENTRY_PATH, encoding="utf-8") as fh:
        return fh.read()


def test_auto_entry_never_submits_to_broker_directly():
    """Invariant: entries.enter() is the ONLY buy path. Neither auto_entry.py
    (Minervini funnel) nor zone_edge_entry.py (Supply & Demand zone-edge
    funnel) may contain a single direct broker submit_*/replace/cancel/close
    call — every order flows through entries.enter so armed / sizing /
    equity cap / never-average-down / earnings always apply."""
    for name, src in (("auto_entry.py", _auto_entry_source()),
                      ("zone_edge_entry.py", _zone_edge_entry_source())):
        for forbidden in ("submit_", "replace_order", "cancel_order",
                          "close_position"):
            assert forbidden not in src, (
                f"trading/{name} contains `{forbidden}` — engine entries "
                f"must flow through entries.enter(), never the broker directly."
            )
        assert "entries.enter(" in src, (
            f"trading/{name} no longer buys through entries.enter()")


# ── Zone-edge entries: OWNER rules for the Supply & Demand strategy ──────────
# trading/zone_edge_entry.py buys the S&D board's demand arrivals + supply
# breakouts. There is NO book behind these entry rules (Ajay's playbook,
# docs/supply_demand/zone_edge_autopilot.md); the risk math is the shared
# trading/risk_rules.py contract applied by entries.enter. Locked here so a
# drift is a deliberate owner decision, never a silent tweak.

ZONE_EDGE_TOKENS = [
    "MAX_ZONE_ENTRIES_PER_DAY = 4",
    "STOP_BUFFER_PCT = 0.5",
    "MIN_TOUCHES = 2",
    "MIN_CAP_USD = 1e9",
    "SIGNAL_MAX_AGE_SEC = 180",
    "LAST_ENTRY_ET = dtime(15, 45)",
    'STATE_COLL = "zone_edge_entry_state"',
    'RACE_COLL = "execution_race"',
]


def test_zone_edge_entry_params_locked_in_source():
    src = _zone_edge_entry_source()
    for token in ZONE_EDGE_TOKENS:
        assert token in src, (
            f"zone-edge parameter drifted or was renamed: `{token}` not found "
            f"in trading/zone_edge_entry.py — owner-chosen S&D knobs "
            f"(docs/supply_demand/zone_edge_autopilot.md); update doc + tests "
            f"WITH sign-off, never silently."
        )


def test_zone_edge_entry_params_importable_and_equal():
    from datetime import time as dtime
    from trading import zone_edge_entry as ze
    assert ze.MAX_ZONE_ENTRIES_PER_DAY == 4
    assert ze.STOP_BUFFER_PCT == 0.5
    assert ze.MIN_TOUCHES == 2
    assert ze.MIN_CAP_USD == 1e9
    assert ze.SIGNAL_MAX_AGE_SEC == 180
    assert ze.LAST_ENTRY_ET == dtime(15, 45)
    assert ze.STATE_COLL == "zone_edge_entry_state"
    assert ze.RACE_COLL == "execution_race"


def test_zone_edge_entry_cites_no_book_and_defers_risk_to_risk_rules():
    """The S&D entry rules are OWNER rules: the module must not cite the
    SEPA books (no TLSW/TTLAC, no page anchors) and must defer every risk
    number to risk_rules (10% line, 2:1 floor, MAX_POSITIONS) instead of
    re-deriving it."""
    import re
    src = _zone_edge_entry_source()
    assert "TLSW" not in src and "TTLAC" not in src, (
        "trading/zone_edge_entry.py cites a SEPA book — the S&D entry rules "
        "have no book; keep the honesty note, drop the cite")
    assert re.search(r"\bpp?\.\s?\d", src) is None, (
        "a page cite crept into trading/zone_edge_entry.py")
    assert "OWNER RULES" in src
    for token in ("risk_rules.ABS_MAX_STOP_PCT", "risk_rules.MIN_REWARD_RISK",
                  "risk_rules.MAX_POSITIONS"):
        assert token in src, (
            f"`{token}` no longer read from risk_rules in zone_edge_entry.py "
            f"— risk numbers must never be re-derived locally")
    for local in ("= 10.0", "= 2.0\n"):
        assert local not in src, (
            f"a local risk constant ({local.strip()}) appeared in "
            f"zone_edge_entry.py — use risk_rules")


def test_zone_edge_entry_wired_fenced_and_configurable():
    """exit_engine: config key passes the whitelist (default OFF), tick step
    (h) calls run() inside its own try/except right after (f), status()
    carries the block; api: POST /trading/config accepts the flag and GET
    /trading/race exists behind the admin gate."""
    eng_path = os.path.join(TRADING_DIR, "exit_engine.py")
    with open(eng_path, encoding="utf-8") as fh:
        eng = fh.read()
    assert '"zone_edge_entry": bool(doc.get("zone_edge_entry", False))' in eng, (
        "get_config() no longer passes zone_edge_entry (default OFF) through")
    assert '"last_zone_entry_disabled_day": doc.get("last_zone_entry_disabled_day")' in eng
    hook = ('    try:\n'
            '        from trading import zone_edge_entry\n'
            '        summary["zone_edge_entry"] = zone_edge_entry.run(broker=broker,\n'
            '                                                         cfg=get_config())\n'
            '    except Exception as exc:')
    assert hook in eng, (
        "tick step (h) zone_edge_entry.run is missing or no longer fenced in "
        "its own try/except — a zone-entry crash could break stop protection")
    assert eng.index('summary["auto_entry"] = auto_entry.run(') \
        < eng.index('summary["zone_edge_entry"] = zone_edge_entry.run(') \
        < eng.index("summary[\"journal\"] = journal.reconcile()"), (
        "step (h) must run right after (f) auto_entry and before (g) journal")
    assert 'out["zone_edge_entry"] = zone_edge_entry.status_block(cfg)' in eng
    api_path = os.path.join(TRADING_DIR, "api.py")
    with open(api_path, encoding="utf-8") as fh:
        api = fh.read()
    assert '"zone_edge_entry" in payload' in api, (
        "POST /trading/config no longer accepts zone_edge_entry")
    assert 'updates["zone_edge_entry"] = False' in api, (
        "zone_edge_entry null must reset to OFF, never ON")
    assert '@router.get("/race")' in api and "_require_admin(email)" in api.split(
        '@router.get("/race")')[1].split("@router")[0], (
        "GET /trading/race missing or not admin-gated")


# --- Broker factory + SIM broker invariants ----------------------------------
# trading/broker.py is the ONE seam that picks the execution venue (env
# TRADING_BROKER=sim|alpaca, else Alpaca when keys exist, else the built-in
# Massive-quote sim). Engine modules must obtain the broker THROUGH it so the
# venue stays swappable — and the SIM honesty constants (docs/sepa/
# auto_entry_methodology.md, "Built-in SIM broker") are owner numbers locked
# like the engine params above.

TRADING_DIR = os.path.join(os.path.dirname(__file__), "..", "trading")
BROKER_SIM_PATH = os.path.join(TRADING_DIR, "broker_sim.py")

SIM_TOKENS = [
    # "assume you have 5k" — mirrors auto_entry.DEFAULT_EQUITY_CAP.
    "SIM_STARTING_CASH = 5000.0",
    # pessimistic stop-fill slippage (real gaps fill worse — honesty note).
    "SIM_SLIPPAGE_PCT = 0.1",
]


def test_engine_modules_use_broker_factory_not_alpaca_directly():
    """Factory invariant: exit_engine/entries/auto_entry contain NO direct
    broker_alpaca reference — the broker comes from trading.broker.get_broker()
    (BrokerError/OPEN_STATUSES re-exported there). Only broker.py and
    broker_sim.py may name the Alpaca module. Breaking this re-pins the
    engine to one venue and silently disables the sim/paper switch."""
    for fname in ("exit_engine.py", "entries.py", "auto_entry.py",
                  "zone_edge_entry.py"):
        with open(os.path.join(TRADING_DIR, fname), encoding="utf-8") as fh:
            src = fh.read()
        assert "broker_alpaca" not in src, (
            f"trading/{fname} references broker_alpaca directly — go through "
            f"trading.broker.get_broker() so the venue stays swappable."
        )
        assert "get_broker" in src, (
            f"trading/{fname} no longer obtains its broker from the factory."
        )
    with open(os.path.join(TRADING_DIR, "broker.py"), encoding="utf-8") as fh:
        factory_src = fh.read()
    assert "broker_alpaca" in factory_src and "broker_sim" in factory_src


def test_sim_constants_locked_in_source():
    """SIM_STARTING_CASH / SIM_SLIPPAGE_PCT are owner-chosen honesty knobs —
    they must never move silently (doc + sign-off, like the engine params)."""
    with open(BROKER_SIM_PATH, encoding="utf-8") as fh:
        src = fh.read()
    for token in SIM_TOKENS:
        assert token in src, (
            f"SIM constant drifted or was renamed: `{token}` not found in "
            f"trading/broker_sim.py — owner decision + doc update required."
        )


def test_sim_constants_importable_and_equal():
    from trading import auto_entry as ae
    from trading import broker_sim as bs
    assert bs.SIM_STARTING_CASH == 5000.0 == ae.DEFAULT_EQUITY_CAP
    assert bs.SIM_SLIPPAGE_PCT == 0.1
    assert bs.configured() is True
    assert bs.mode() == "sim"


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


# --- Journal analytics: book metric targets + the cardinal-sin rule ----------
# trading/analytics.py REPORTS Minervini's own descriptive stats (it changes no
# gating). The cited targets (2:1/3:1, p.301) and the cardinal-sin rule
# (avg_loss > avg_gain, p.299) are book numbers — locked here like the risk
# constants so a "report" can never silently drop or move them
# (docs/sepa/journal_analytics_methodology.md).

ANALYTICS_PATH = os.path.join(os.path.dirname(__file__), "..",
                              "trading", "analytics.py")

ANALYTICS_TOKENS = [
    # p.301: "at least a 2:1 win/loss ratio ... I shoot for 3:1."
    "TARGET_RATIO = 2.0",
    "STRETCH_RATIO = 3.0",
    # p.298: batting average "about 50 percent of the time".
    "BATTING_REF = 0.5",
    # p.299: "not allow any stock to fall more than 10 percent".
    "HALF_AVG_GAIN_CAP = 10.0",
]

ANALYTICS_PAGE_CITES = ["p.298", "p.299", "p.301"]


def _analytics_source():
    with open(ANALYTICS_PATH, encoding="utf-8") as fh:
        return fh.read()


def test_analytics_targets_locked_in_source():
    """The cited book targets must exist verbatim in trading/analytics.py.
    These are Minervini Ch.13 numbers (p.298/p.299/p.301) — Rule #4 applies
    to any change (page-cited doc + sign-off), even though analytics only
    reports them."""
    src = _analytics_source()
    for token in ANALYTICS_TOKENS:
        assert token in src, (
            f"LOCKED analytics target drifted or was renamed: `{token}` not "
            f"found in trading/analytics.py "
            f"(docs/sepa/journal_analytics_methodology.md) — Rule #4."
        )


def test_analytics_page_cites_present_in_source():
    """Every reported metric traces to a printed page (Rule #1): the p.298/
    p.299/p.301 anchors must never be stripped from analytics.py."""
    src = _analytics_source()
    for cite in ANALYTICS_PAGE_CITES:
        assert cite in src, (
            f"page cite `{cite}` missing from trading/analytics.py — the "
            f"source map to Trade Like a Stock Market Wizard Ch.13 is part of "
            f"the contract."
        )


def test_analytics_targets_importable_and_equal():
    from trading import analytics as an
    assert an.TARGET_RATIO == 2.0
    assert an.STRETCH_RATIO == 3.0
    assert an.BATTING_REF == 0.5
    assert an.HALF_AVG_GAIN_CAP == 10.0


def test_cardinal_sin_flag_fires_and_cites_p299():
    """p.299 functional lock: when the average loss exceeds the average gain
    (the trader's cardinal sin), compute() MUST emit a flag citing p.299. This
    is the red line Ajay's real money depends on seeing."""
    from trading import analytics as an

    def _losing_trade(sym, epoch, gain_pct):
        return {"trade_id": "%s-%d" % (sym, epoch), "symbol": sym,
                "status": "closed",
                "entry": {"epoch": float(epoch), "price": 100.0, "qty": 1,
                          "stop_pct": 7.0, "trigger": None},
                "exit": {"epoch": float(epoch + 86400),
                         "price": 100.0 * (1 + gain_pct / 100.0),
                         "leg": "stop"},
                "realized": {"gain_pct": gain_pct,
                             "gain_dollars": round(gain_pct, 2),
                             "r_multiple": round(gain_pct / 7.0, 2),
                             "holding_days": 1.0, "exit_reason": "x"}}

    # avg_gain 5, avg_loss 9 -> cardinal sin.
    trades = [_losing_trade("W", 1, 5.0),
              _losing_trade("L1", 2, -9.0),
              _losing_trade("L2", 3, -9.0)]
    a = an.compute(trades)
    assert a["avg_loss_pct"] > a["avg_gain_pct"]
    flags = " ".join(a["vs_book"]["flags"])
    assert "cardinal sin" in flags and "p.299" in flags, a["vs_book"]["flags"]


def test_analytics_win_loss_floor_flag_cites_p301():
    """p.301 functional lock: a win/loss ratio below the 2:1 floor must be
    flagged with the p.301 cite (the book's minimum acceptable edge)."""
    from trading import analytics as an

    def _t(sym, epoch, gain_pct):
        return {"trade_id": "%s-%d" % (sym, epoch), "symbol": sym,
                "status": "closed",
                "entry": {"epoch": float(epoch), "price": 100.0, "qty": 1,
                          "stop_pct": 7.0, "trigger": None},
                "exit": {"epoch": float(epoch + 86400), "price": 100.0,
                         "leg": "stop"},
                "realized": {"gain_pct": gain_pct, "gain_dollars": gain_pct,
                             "r_multiple": round(gain_pct / 7.0, 2),
                             "holding_days": 1.0, "exit_reason": "x"}}

    # avg_gain 8, avg_loss 7 -> win/loss 1.14 (< 2:1) but NOT the cardinal sin.
    trades = [_t("W", 1, 8.0), _t("L", 2, -7.0)]
    a = an.compute(trades)
    flags = " ".join(a["vs_book"]["flags"])
    assert "2:1 floor" in flags and "p.301" in flags, a["vs_book"]["flags"]


# ── Failed-trade autopsy: OWNER rules for the Supply & Demand strategy ──────
# trading/autopsy.py classifies every losing round-trip (zone-edge, Minervini
# or manual) with numbers + one feedback line. Every class and threshold is an
# OWNER rule (docs/supply_demand/trade_autopsy.md) — no book, no cite. Locked
# here so a drift is a deliberate owner decision, never a silent tweak; the
# module must stay read-only over the broker (never imported) and write ONLY
# trade_autopsies (+ the one 'autopsy' ledger row via exit_engine.ledger).

AUTOPSY_PATH = os.path.join(TRADING_DIR, "autopsy.py")

AUTOPSY_TOKENS = [
    "MAX_PER_RUN = 3",
    "MAX_RETRIES = 5",
    "RECHECK_SEC = 3600",
    "SESSIONS_AFTER_EXIT = 2",
    "CLAMP_TOLERANCE_PT = 0.1",
    "MARKET_DOWN_PCT = -1.0",
    "FOLLOW_THROUGH_R = 0.5",
    "CHASE_DEMAND_PCT = 1.0",
    "CHASE_BREAKOUT_PCT = 2.0",
    "SESSION_MINUTES = 390",
    "FIRST_MINUTES = 30",
    "LATE_MINUTES = 330",
    "GAP_DOWN_PCT = -1.0",
    "THIN_BAND_TOUCHES = 2",
    "WIDE_STOP_PCT = 7.0",
    "ATR_DAYS = 14",
    'COLL = "trade_autopsies"',
    # The daily-frame period MUST be the cache-wide default: load_prices
    # writes a miss back into the shared price_cache that the SEPA scanner /
    # zone store / gauge read without a period (reviewer fix 2026-09-03).
    'DAILY_PERIOD = "2y"',
]


def _autopsy_source():
    with open(AUTOPSY_PATH, encoding="utf-8") as fh:
        return fh.read()


def test_autopsy_params_locked_in_source():
    src = _autopsy_source()
    for token in AUTOPSY_TOKENS:
        assert token in src, (
            f"autopsy parameter drifted or was renamed: `{token}` not found "
            f"in trading/autopsy.py — owner-chosen S&D knobs "
            f"(docs/supply_demand/trade_autopsy.md); update doc + tests "
            f"WITH sign-off, never silently."
        )


def test_autopsy_params_importable_and_equal():
    from trading import autopsy as ap
    assert ap.MAX_PER_RUN == 3
    assert ap.MAX_RETRIES == 5
    assert ap.RECHECK_SEC == 3600
    assert ap.SESSIONS_AFTER_EXIT == 2
    assert ap.CLAMP_TOLERANCE_PT == 0.1
    assert ap.MARKET_DOWN_PCT == -1.0
    assert ap.FOLLOW_THROUGH_R == 0.5
    assert ap.CHASE_DEMAND_PCT == 1.0
    assert ap.CHASE_BREAKOUT_PCT == 2.0
    assert ap.SESSION_MINUTES == 390
    assert ap.FIRST_MINUTES == 30 and ap.LATE_MINUTES == 330
    assert ap.GAP_DOWN_PCT == -1.0
    assert ap.THIN_BAND_TOUCHES == 2
    assert ap.WIDE_STOP_PCT == 7.0
    assert ap.ATR_DAYS == 14
    assert ap.COLL == "trade_autopsies"
    assert ap.DAILY_PERIOD == "2y"
    # Priority order of the rule table IS the rule — locked as a sequence.
    assert ap.CLASSES == ("stop_clamped", "shakeout", "band_failed",
                          "market_down", "chased", "no_follow_through",
                          "unclassified")
    assert [r["class"] for r in ap.rules_list()] == list(ap.CLASSES)
    # 2026-09-05 lanes: the catalyst lane got its own autopsy label (deliberate).
    assert ap.STRATEGIES == ("zone_edge", "minervini", "catalyst", "manual")


def test_autopsy_never_touches_the_broker_and_cites_no_book():
    """Read-only invariant: no broker import, no order token, no direct
    ledger/journal/state write — the ONLY Mongo write is the single
    trade_autopsies upsert. And no book: every rule is an owner rule."""
    import re
    src = _autopsy_source()
    for forbidden in ("submit_", "replace_order", "cancel_order",
                      "close_position", "broker_alpaca", "get_broker",
                      "from trading.broker", "trading import broker",
                      "insert_one", "delete_many", "delete_one",
                      "replace_one"):
        assert forbidden not in src, (
            f"trading/autopsy.py contains `{forbidden}` — the autopsy is "
            f"read-only over the broker and writes only trade_autopsies.")
    assert src.count("update_one(") == 1, (
        "trading/autopsy.py must hold exactly ONE update_one (the "
        "trade_autopsies upsert) — no other collection may be written")
    assert 'coll.update_one({"_id": doc["_id"]}' in src
    assert "TLSW" not in src and "TTLAC" not in src, (
        "trading/autopsy.py cites a SEPA book — the autopsy rules are owner "
        "rules for the Supply & Demand strategy; keep the honesty note")
    assert re.search(r"\bpp?\.\s?\d", src) is None, (
        "a page cite crept into trading/autopsy.py")
    assert "OWNER RULES" in src
    assert 'ledger("autopsy"' in src, (
        "the one 'autopsy' ledger row per trade left trading/autopsy.py")
    # Every feedback template names the owner decision, never advice.
    from trading import autopsy as ap
    for cls in ap.CLASSES:
        assert "owner decision" in ap.feedback(cls, {}), cls


def test_autopsy_wired_fenced_after_journal_and_api_gated():
    """exit_engine.tick step (i) calls autopsy.run() inside its own
    try/except right AFTER (g) journal.reconcile; GET /trading/autopsies
    exists behind the admin gate."""
    eng_path = os.path.join(TRADING_DIR, "exit_engine.py")
    with open(eng_path, encoding="utf-8") as fh:
        eng = fh.read()
    hook = ('    try:\n'
            '        from trading import autopsy\n'
            '        summary["autopsy"] = autopsy.run()\n'
            '    except Exception as exc:')
    assert hook in eng, (
        "tick step (i) autopsy.run is missing or no longer fenced in its own "
        "try/except — an autopsy crash could break stop protection")
    assert eng.index('summary["journal"] = journal.reconcile()') \
        < eng.index('summary["autopsy"] = autopsy.run()'), (
        "step (i) must run right after (g) journal reconcile")
    api_path = os.path.join(TRADING_DIR, "api.py")
    with open(api_path, encoding="utf-8") as fh:
        api = fh.read()
    assert '@router.get("/autopsies")' in api, "GET /trading/autopsies missing"
    block = api.split('@router.get("/autopsies")')[1].split("@router")[0]
    assert "_require_admin(email)" in block, "GET /trading/autopsies not admin-gated"
    assert "autopsy.report" in block


# ── Zone-edge review fixes 2026-09-05 (Ajay: "yes please fix the bugs") ──────
# The stop is handed over as an ABSOLUTE level and the room gate counts every
# band overhead. Source guards so a refactor cannot silently drop either.

def test_zone_edge_entry_hands_entries_the_absolute_stop_level():
    """A percent-of-print stop drifts INTO the band when the tape moves up
    between the board print and the order; the engine passes the level and
    entries refuses (never clamps) when the drift makes it too wide."""
    src = _zone_edge_entry_source()
    assert "stop_price=stop_price, allow_earnings=False)" in src, (
        "zone_edge_entry no longer passes the absolute stop level to entries.enter")
    with open(os.path.join(TRADING_DIR, "entries.py"), encoding="utf-8") as fh:
        en = fh.read()
    # 2026-09-05 lanes: the signature grew strategy + reason (the journal
    # tag) — the guard moved with it, deliberately.
    assert "stop_price: Optional[float] = None," in en and \
        'strategy: str = "manual",' in en and \
        "reason: Optional[dict] = None) -> dict:" in en, (
        "entries.enter lost its absolute stop_price kwarg or the "
        "strategy/reason journal tags")
    assert "is not below the entry price" in en and "past the %g%% line" in en, (
        "entries must REFUSE an absolute stop that is through the print or "
        "wider than ABS_MAX_STOP_PCT — never clamp it back up into the band")
    assert "stop_pct = dist" in en and 'ctx["stop_level"] = level' in en


def test_zone_edge_room_gate_is_kind_agnostic_and_floors_need_at_the_placed_stop():
    """Overhead = supply bands at/above the print (containing = zero room)
    + demand bands above it (broken support); `need` uses the stop the
    engine will place, whose 1% floor is a bare literal in FROZEN
    risk_rules — pinned here to the mirrored constant."""
    src = _zone_edge_entry_source()
    assert 'if kind == "supply" and hi >= last:' in src
    assert 'elif kind == "demand" and lo > last:' in src
    assert 'detail["reason"] = "inside supply band (%g-%g): no room"' in src
    assert "max(stop_pct, RISK_STOP_FLOOR_PCT)" in src
    assert "RISK_STOP_FLOOR_PCT = 1.0" in src
    with open(os.path.join(TRADING_DIR, "risk_rules.py"), encoding="utf-8") as fh:
        rr = fh.read()
    assert "pct = max(pct, 1.0)" in rr, (
        "risk_rules.initial_stop's floor moved — update RISK_STOP_FLOOR_PCT in "
        "trading/zone_edge_entry.py with it (the room gate mirrors that literal)")
    from trading import zone_edge_entry as ze
    assert ze.RISK_STOP_FLOOR_PCT == 1.0


# ── Autopilot lanes 2026-09-05 (Ajay: "What ever rules I created for the
# alerts are the ideal conditions for a stock to be bough in Autopilot. Keep
# the minervini entries but also make sure you have demand zone and catalyst
# based entries time to time and journal it appropriately.") ─────────────────

CATALYST_ENTRY_PATH = os.path.join(TRADING_DIR, "catalyst_entry.py")


def _catalyst_entry_source():
    with open(CATALYST_ENTRY_PATH, encoding="utf-8") as fh:
        return fh.read()


def test_catalyst_entry_never_submits_to_broker_directly():
    src = _catalyst_entry_source()
    for forbidden in ("submit_", "replace_order", "cancel_order", "close_position",
                      "_full_scan(", "scan_catalysts("):
        assert forbidden not in src, (
            f"trading/catalyst_entry.py contains `{forbidden}` — buys flow through "
            f"entries.enter() only and the lane must never trigger a catalyst scan")
    assert "entries.enter(" in src and "_cache_get()" in src


def test_catalyst_entry_tick_never_reaches_the_tape_or_the_ondemand_zone_builder():
    """review 2026-09-05: the lane called bounce_room.api_payload from the
    engine tick — a synchronous provider snapshot plus on-demand 2-year price
    loads + zone builds for every funnel survivor. The tick may read Mongo
    (zone_store / bounce_room_zones via bounce_room.load_docs) and the cached
    scan, and price off the scan's own row — nothing else."""
    src = _catalyst_entry_source()
    for forbidden in ("api_payload", "queue_ondemand", "bulk_snapshot", "load_prices(",
                      "build_doc(", "sepa.prices", "from sepa", "background=",
                      "default_builder"):
        assert forbidden not in src, (
            f"trading/catalyst_entry.py reaches `{forbidden}` — the tick must read "
            f"existing zone docs only; coverage is built by the Catalysts board")
    assert "bounce_room.load_docs(" in src and "bounce_room.read_symbol(" in src
    assert "def snap_from_scan(" in src and "def zone_rows(" in src
    assert "STALE_PRINT_SEC" in src, "the phone's stale-print line must gate the print"


CATALYST_TOKENS = [
    "MAX_CATALYST_ENTRIES_PER_DAY = 1",
    "CATALYST_MIN_PRICE = 2.0",
    "CATALYST_MIN_DOLLAR_VOL = 2_000_000",
    'QUADRANTS_OK = ("REAL", "OVERLOOKED")',
    'GRADES_OK = ("A", "B")',
    'STATE_COLL = "catalyst_entry_state"',
    "SUMMARY_MAX_CHARS = 160",
    "LAST_ENTRY_ET = zone_edge_entry.LAST_ENTRY_ET",
    "STOP_BUFFER_PCT = zone_edge_entry.STOP_BUFFER_PCT",
]


def test_catalyst_entry_params_locked_and_cite_no_book():
    import re
    src = _catalyst_entry_source()
    for token in CATALYST_TOKENS:
        assert token in src, f"catalyst lane owner setting drifted: `{token}`"
    assert "TLSW" not in src and "TTLAC" not in src
    assert re.search(r"\bpp?\.\s?\d", src) is None, "a page cite crept into catalyst_entry.py"
    assert "NOT from Ajay" in src, "the two conservative defaults must say they are not his"
    from trading import catalyst_entry as ce
    assert ce.MAX_CATALYST_ENTRIES_PER_DAY == 1
    assert ce.CATALYST_MIN_PRICE == 2.0 and ce.CATALYST_MIN_DOLLAR_VOL == 2_000_000
    for token in ("risk_rules.ABS_MAX_STOP_PCT", "risk_rules.MAX_POSITIONS"):
        assert token in src


def test_zone_edge_entry_applies_both_alert_gates():
    """The phone gate is the entry gate: zone_edge_entry must call
    alert_gates.room_gate AND alert_gates.demand_proximity_gate, count the
    skips, and tag its ONE enter call with the lane."""
    src = _zone_edge_entry_source()
    assert "alert_gates.room_gate(" in src and "alert_gates.demand_proximity_gate(" in src
    assert 'out["skipped_alert_gate"]' in src
    assert 'lane = ("demand_zone" if c["kind"] == "demand" else "breakout")' in src
    # Quick Bounce day-trade variant (Ajay 2026-09-06): a demand entry on a
    # study-listed name takes the quick_bounce tag, same rules, same stop, and
    # the tick flattens it at 15:55 ET (step h2).
    assert 'if lane == "demand_zone" and sym in qb_names:' in src and "lane = QB_STRATEGY" in src
    assert 'QB_STRATEGY = "quick_bounce"' in src and "QB_EOD_FLATTEN_ET = dtime(15, 55)" in src
    assert "strategy=lane," in src
    assert "stop_price=stop_price, allow_earnings=False)" in src
    with open(os.path.join(TRADING_DIR, "auto_entry.py"), encoding="utf-8") as fh:
        ae = fh.read()
    assert 'strategy="minervini"' in ae, "auto_entry's enter call lost its lane tag"


def test_catalyst_entry_wired_fenced_and_configurable():
    eng_path = os.path.join(TRADING_DIR, "exit_engine.py")
    with open(eng_path, encoding="utf-8") as fh:
        eng = fh.read()
    assert '"catalyst_entry": bool(doc.get("catalyst_entry", False))' in eng
    assert '"last_catalyst_entry_disabled_day": doc.get("last_catalyst_entry_disabled_day")' in eng
    hook = ('    try:\n'
            '        from trading import catalyst_entry\n'
            '        summary["catalyst_entry"] = catalyst_entry.run(broker=broker,\n'
            '                                                       cfg=get_config())\n'
            '    except Exception as exc:')
    assert hook in eng, "tick step (j) catalyst_entry.run missing / not fenced"
    assert eng.index('summary["zone_edge_entry"] = zone_edge_entry.run(') \
        < eng.index('summary["catalyst_entry"] = catalyst_entry.run(') \
        < eng.index('summary["journal"] = journal.reconcile()')
    assert 'out["catalyst_entry"] = catalyst_entry.status_block(cfg)' in eng
    with open(os.path.join(TRADING_DIR, "api.py"), encoding="utf-8") as fh:
        api = fh.read()
    assert '"catalyst_entry" in payload' in api
    assert 'updates["catalyst_entry"] = False' in api, "catalyst_entry null must reset to OFF"


def test_entries_ledger_detail_carries_strategy_and_reason():
    with open(os.path.join(TRADING_DIR, "entries.py"), encoding="utf-8") as fh:
        en = fh.read()
    assert 'STRATEGIES = ("minervini", "demand_zone", "breakout", "catalyst", "manual")' in en
    assert '"strategy": ' in en and '"entry_reason": ' in en
    assert "REASON_MAX_BYTES = 2048" in en
    from trading import entries
    assert entries._strategy_tag("catalyst") == "catalyst"
    assert entries._strategy_tag("ALPHA") == "manual" and entries._strategy_tag(None) == "manual"
    assert entries._safe_reason(None) is None
    assert entries._safe_reason({"a": float("nan"), "b": 1}) == {"a": None, "b": 1}
    big = entries._safe_reason({"blob": "x" * 5000})
    assert big["truncated"] is True and len(big["preview"]) <= entries.REASON_MAX_BYTES
    assert entries._safe_reason("not a dict") is None


# ── flatten queue 2026-09-05 ─────────────────────────────────────────────────

def test_flatten_queue_2026_09_05_drain_precedes_market_gate_and_flatten_queues_on_held():
    """Owner exits Alpaca refused outside the session (HTTP 403 40310000,
    shares held for pending-cancel orders) are queued and drained by the
    tick BEFORE the market-closed early return and BEFORE the protect loop,
    which skips queued symbols; nothing runs disarmed."""
    with open(os.path.join(TRADING_DIR, "exit_engine.py"), encoding="utf-8") as fh:
        eng = fh.read()
    assert "FLATTEN_HELD_CODE = 40310000" in eng
    tick_src = eng[eng.index("def tick(force"):]
    drain_at = tick_src.index('summary["flatten_queue"] = _drain_flatten_queue()')
    assert drain_at < tick_src.index("# (b) market clock")
    assert drain_at < tick_src.index("for pos in positions:")
    assert "if sym in queued_syms:" in tick_src
    drain = eng[eng.index("def _drain_flatten_queue"):eng.index("def tick(force")]
    assert 'if not cfg["armed"]:' in drain and 'out["skipped_disarmed"]' in drain
    assert 'if (o.get("status") or "").lower() == "pending_cancel":' in drain
    flat_src = eng[eng.index("def flatten(symbol"):eng.index("def flatten_all(")]
    assert "_held_for_orders(exc)" in flat_src and "queue_flatten(sym, reason)" in flat_src
    with open(os.path.join(TRADING_DIR, "api.py"), encoding="utf-8") as fh:
        api = fh.read()
    assert '@router.post("/flatten-queue/{symbol}/cancel")' in api
    assert "exit_engine.flatten, symbol, reason" in api
    assert '"flatten_queue"' not in api[api.index('@router.post("/config")'):api.index('@router.post("/enter")')], \
        "flatten_queue must not be writable through POST /trading/config"
    with open(os.path.join(TRADING_DIR, "journal.py"), encoding="utf-8") as fh:
        jn = fh.read()
    assert "def _is_exit_row" in jn and 'det.get("closed") is False' in jn


# ── options lane 2026-09-06 ──────────────────────────────────────────────────

def test_options_lane_2026_09_06_owner_settings_locked_and_engine_seams():
    """Paper options on demand-zone touches (Ajay 2026-09-06). Owner settings
    are pinned verbatim; the tick runs the lane at step (k) AFTER the catalyst
    lane; the stock protect loop and status() skip option contracts; the flag
    is a strict boolean on POST /trading/config; the journal merges the lane."""
    from trading import options_lane as OL
    assert OL.STRATEGY == "options_zone"
    assert OL.MAX_OPTIONS_ENTRIES_PER_DAY == 1 and OL.MAX_OPEN_OPTIONS == 3
    assert OL.RISK_PCT_OF_EQUITY == 1.0 and OL.MAX_PREMIUM_PER_TRADE == 1500.0
    assert (OL.MIN_DTE, OL.MAX_DTE, OL.CLOSE_DTE) == (28, 60, 7)
    assert (OL.DELTA_LO, OL.DELTA_HI) == (0.55, 0.75)
    assert OL.IV_SPREAD_THRESHOLD == 0.45
    # put spread under the band floor (Ajay 2026-09-06 "ok please all 3"; builder defaults)
    import inspect
    assert OL.PUT_SPREAD_WIDTH_PCT == 5.0 and OL.MIN_CREDIT_PCT_OF_WIDTH == 15.0
    assert OL.TAKE_PROFIT_PCT_OF_CREDIT == 25.0
    assert OL.structure_for(0.45, False) == "short_put_spread" and OL.structure_for(0.449, True) == "long_call"
    lane_src = inspect.getsource(OL)
    assert 'if plan["structure"] in ("bull_call_spread", "short_put_spread"):' in lane_src, "one mleg package, never a naked leg"
    assert '"limit_price": round(-credit, 2)' in lane_src, "a negative mleg limit is a net credit at Alpaca"
    assert "take_profit_reason(pos, _pos_quotes(brk, pos, snaps_cache))" in lane_src
    assert OL.MAX_SPREAD_PCT_OF_MID == 10.0 and OL.MAX_SPREAD_ABS == 0.15
    assert OL.MIN_OPEN_INTEREST == 200 and OL.MIN_UNDERLYING_PRICE == 20.0
    assert OL.EARNINGS_CLOSE_DAYS == 2
    from trading import zone_edge_entry as ZEE
    assert OL.STOP_BUFFER_PCT == ZEE.STOP_BUFFER_PCT == 0.5
    assert OL.LAST_ENTRY_ET == ZEE.LAST_ENTRY_ET and OL.MIN_CAP_USD == ZEE.MIN_CAP_USD
    with open(os.path.join(TRADING_DIR, "exit_engine.py"), encoding="utf-8") as fh:
        eng = fh.read()
    assert eng.index('summary["catalyst_entry"] = catalyst_entry.run(') \
        < eng.index('summary["options_lane"] = options_lane.run(') \
        < eng.index('summary["journal"] = journal.reconcile()')
    tick_src = eng[eng.index("def tick(force"):eng.index("def _broker_mode")]
    assert 'if (pos.get("asset_class") or "") == "us_option":' in tick_src
    status_src = eng[eng.index("def status()"):eng.index("def flatten(symbol")]
    assert 'if (pos.get("asset_class") or "") == "us_option":' in status_src
    assert 'out["options_lane"] = options_lane.status_block(cfg)' in eng
    assert '"options_entry": bool(doc.get("options_entry", False))' in eng
    with open(os.path.join(TRADING_DIR, "api.py"), encoding="utf-8") as fh:
        api = fh.read()
    assert '"options_entry" in payload' in api and 'updates["options_entry"] = False' in api
    assert '@router.get("/options")' in api and '@router.post("/options/close/{underlying}")' in api
    with open(os.path.join(TRADING_DIR, "journal.py"), encoding="utf-8") as fh:
        jn = fh.read()
    assert "options_lane.journal_block()" in jn
    with open(os.path.join(TRADING_DIR, "broker_alpaca.py"), encoding="utf-8") as fh:
        ba = fh.read()
    for fn in ("def option_contracts(", "def option_snapshots(", "def submit_option_order(",
               "def submit_option_spread(", "def option_positions("):
        assert fn in ba, fn
    assert '"order_class": "mleg"' in ba
