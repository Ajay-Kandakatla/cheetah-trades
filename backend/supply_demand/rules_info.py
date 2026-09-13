"""Rules info — the house rules behind each Supply & Demand board, the phone
alerts and the paper Auto-Pilot lanes, as short lines for an ℹ️ panel on the
pages themselves (Ajay 2026-09-06: "I need these page in an info section of
those pages ... categorize like stock picks rules and stop loss rules").

Every number is READ FROM the module that enforces it (never retyped here),
so the panel can not drift from the code. Configured owner rules, S/D scope:
no book cites (feedback_sepa_book_scope). Decision support, not advice."""
from __future__ import annotations

from typing import Optional

from trading import risk_rules as RR
from trading import safety_floor as SFL
from growth import alerts as GA
from growth import tracker as GT
from trading import auto_entry as AE
from trading import zone_edge_entry as ZEE
from trading import zero_dte_lane as ZDL
from . import premarket_entry as PME
from trading import catalyst_entry as CE
from trading import options_lane as OL
from . import alert_gates as AG
from . import bounce_room as BR
from . import demand_alerts as DA
from . import demand_reentry as DR
from . import deep_demand as DD
from . import quick_bounce as QB
from . import price_zones as PZ
from . import zone_bounce_alerts as ZB
from . import zone_edge as ZE
from . import zone_store as ZS

SECTION_KEYS = ("in_demand", "deep_demand", "alerts", "autopilot",
                # 🚀 Explosive Growth (2026-09-11) — its own section because the
                # board has NO cap floor while everything above it does, and
                # that difference is the thing he needs the panel to state.
                "growth",
                "sepa_bounce", "catalysts", "options", "quick_bounce",
                # 🌀 Turning Bullish (2026-09-13) — the two Chart Maps tabs.
                # Its own section for the reason the panel exists: these are
                # the only boards in the app built from UNCITED studies that
                # gate nothing, and the reader has to be told that before the
                # rules and not after them.
                "turning_bullish")

_DISCLAIMER = ("Configured house rules on price structure — not a book method, "
               "not a buy signal, not financial advice.")


def _pct(x) -> str:
    x = float(x)
    return ("%d%%" % int(x)) if x == int(x) else ("%.1f%%" % x)


def _b(usd) -> str:
    """A cap floor in words. Integer-billions ONLY worked while the floor was a
    round billion: the moment Ajay moved it to $700M (2026-09-10) this printed
    "$0B" on the ℹ️ panel — the rule telling him there is no floor at all."""
    v = float(usd)
    if v >= 1e9:
        b = v / 1e9
        return "$%dB" % int(b) if abs(b - round(b)) < 1e-9 else "$%.1fB" % b
    m = v / 1e6
    return "$%dM" % int(m) if abs(m - round(m)) < 1e-9 else "$%.0fM" % m


def _t(t) -> str:
    return "%d:%02d" % (t.hour, t.minute)


def _zone_lines():
    """Shared plan lines (Back in Demand and Deep Demand read the same
    trade_plan)."""
    return [
        "Stop = %s under the band floor; flagged when wider than %s or already run "
        "inside the last %d bars." % (_pct(DR.STOP_BUFFER_PCT), _pct(RR.ABS_MAX_STOP_PCT),
                                      DR.STOP_HIT_LOOKBACK_BARS),
        "Target = the low of the first unbroken band above the print (never inside the "
        "entry band); reward:risk must be at least %.1f." % DR.MIN_RR_DEFAULT,
    ]


def _sweep_line():
    """Built from sd_liquidity's geometry and the measured gate, never retyped."""
    from . import sd_liquidity as liq
    return ("PHONE: the demand band's FLOOR MUST HAVE HELD \u2014 %s only (Ajay 2026-09-09: "
            "\"bullish stocks that got in to demand zone .. where Institutions hunt for stop "
            "losses .. I been catching some falling knives\"). MEASURED, and it is the OPPOSITE of "
            "what he expected: over 31,861 replayed bounces on 192 dates, a band never pierced won "
            "30.7%% of the time against 22.7%% for one swept and bought back and 21.5%% for one that "
            "broke (baseline 24.1%%) \u2014 +8.60pp with a date-clustered interval of +6.39 to "
            "+11.06, and 9.6pp fewer stop-outs. THE RECLAIM DOES NOT SAVE IT: the stop hunt "
            "measures WORSE than average, and the deeper the pierce the worse it gets. Boards "
            "still list every arrival and say which it was \u2014 \U0001F3AF swept (pierced %s\u2013%s "
            "on \u2265%.1f\u00d7 volume and closed back above within %d bars) or \U0001F52A broken "
            "(pierced and stayed under, CASY's own read)."
            % (" / ".join(AG.FLOOR_HELD_STATES), _pct(liq.SWEEP_MIN_PIERCE_PCT),
               _pct(liq.SWEEP_MAX_PIERCE_PCT), liq.SWEEP_MIN_VOL_X, liq.RECLAIM_MAX_BARS))


def _room_lines():
    return [
        "Room floor: at least %s to the first unbroken PROVEN band overhead (CLEAR counts); "
        "set Room to any to see everything." % _pct(DR.MIN_ROOM_DEFAULT),
        _proven_line(),
        _direction_line(),
    ]


def _direction_line():
    """Built from the enforcing constant, never retyped."""
    from . import bullish_context as BC
    return ("PHONE: only %s reaches it, and only as a BULLISH REVERSAL (Ajay 2026-09-09, after "
            "CASY: \"only bouncing off alerts\", then \"mood has to be bullish too with "
            "reversal. After a stationary bottommed stocks as I caught a fallig knife\"). "
            "Falling into, settling into, reclaiming from below and resting inside all still LIST "
            "and send nothing. On top of that reversal — which is an INTRADAY read, and CASY "
            "satisfied it at 08:13 ET while in free-fall — two DAILY-structure gates: NOT a "
            "falling knife (swing lows stepping down AND the %d-day falling, both required, "
            "neutral structure, no book) and the mood of the TURN ≥ %+g over the last %d sessions. "
            "The turn, not the two-year read, which scores a genuinely bottomed name −45 on trend, "
            "location and structure before momentum and so could never call a real reversal "
            "bullish. Both FAIL CLOSED. GEX, named bullish patterns and the latest StockTwits "
            "sentiment ride in the body and NEVER gate — across %d resolved pattern observations "
            "not one beat the %d%% placebo, and flat_top fired on 120 of 120 random names."
            % (" / ".join(AG.direction_label(d) for d in AG.PUSH_DIRECTIONS),
               AG.KNIFE_MA_LEN, AG.REVERSAL_MOOD_FLOOR,
               AG.REVERSAL_MOOD_BARS, BC.PATTERN_PLACEBO[0], BC.PATTERN_PLACEBO[1]))




def _sector_heat_line():
    """Built from the enforcing constants, never retyped."""
    from rotation import heat as RH
    # The WINDOW is read from heat, never retyped: it moved from 21 sessions to
    # the week on 2026-09-10 and this line went on claiming 21 until it was
    # caught. The study caveat below is the important half — see heat's own
    # docstring.
    return ("\U0001F525 Sector flow rides the body and the board tiles and GATES NOTHING: the "
            "name's industry cohort (or its sector when the industry is too thin) "
            "median-member %s return minus %s, ranked against every group on the "
            "rotation map — top %g%% reads hot, bottom %g%%%s cold. Ajay 2026-09-10: "
            "\"Lately sector rotation is with in a week since its bear market... Ignore "
            "the 21 day\" — Aerospace & Defense read -11.9%% over 21 sessions while it "
            "was GREEN over 5, so the old window printed the inverse of the tape. "
            "NOT MEASURED ON THIS WINDOW: the -0.57pp flat result (50,191 replayed "
            "arrivals, hot 22.4%% vs cold 23.2%%, 95%% -1.87..+0.71) and the backwards "
            "5-session read (COLD 30.8%% vs 28.3%%) both measured the 21-SESSION "
            "definition. They do not describe what ships now; re-running the study on "
            "the new window is what honesty requires before anyone leans on it."
            % (RH.HEAT_WINDOW, "RSP", 100.0 - RH.HOT_PCTL, RH.COLD_PCTL, ""))


def _proven_line():
    return ("A lid counts only when it is tested ≥ %d× (touches only since 2026-09-08 — FSLR); a "
            "one-touch band overhead is skipped and room is measured to the next real one "
            "(the KLAC lesson, 2026-09-06). Gap day (print ≥ %s under yesterday's close, 2026-09-08 "
            "DYN): every shelf between the print and that close is trapped supply — never "
            "support, always counted for room." % (AG.LID_MIN_TOUCHES, _pct(AG.GAP_DOWN_PCT)))


def _closed_day_line() -> str:
    """Ajay 2026-09-07 (Labor Day): 'turn of alerts scans' — built from the gate."""
    from market_hours import gate
    from market_hours.reminder import ALL_HOLIDAYS
    today = gate._now_et().strftime("%Y-%m-%d")
    nxt = sorted(d for d in ALL_HOLIDAYS if d >= today)
    return ("Closed days push nothing market-driven and run no scan: weekends and NYSE holidays "
            "(next: %s). Personal reminders (%d kinds: todos, flashcards, household) still deliver."
            % (nxt[0] if nxt else "none loaded", len(gate.PERSONAL_KINDS)))


def sections() -> dict:
    gate_room, gate_prox = _pct(AG.ALERT_MIN_ROOM_PCT), _pct(AG.ALERT_MAX_ABOVE_DEMAND_PCT)
    out = {}

    out["in_demand"] = {
        "title": "Back in Demand", "emoji": "🧲",
        "picks": [
            "A demand band tested at least %d times with strength ≥ %d, drawn on the wide "
            "board geometry." % (DR.MIN_TOUCHES, int(DR.MIN_ZONE_STRENGTH)),
            "Price was above the band inside the last %d bars and is back in it, or within "
            "%s above its top (re-entry, not a resident)." % (DR.REENTRY_LOOKBACK_BARS,
                                                             _pct(DR.ENTRY_ABOVE_TOL_PCT)),
            "Not a falling knife (swing lows stepping down AND a falling 50-day) and not a "
            "broken band (a close below it, then a reversal back in).",
            "Approaching list: band top within %s below price and price down at least %s "
            "over the last %d sessions." % (_pct(DR.APPROACH_NEAR_PCT),
                                            _pct(DR.APPROACH_MIN_DRIFT_PCT),
                                            DR.APPROACH_DRIFT_BARS),
        ] + _room_lines() + [
            "Order: a reversal off the band with room first, then room, money-flow (CMF) as "
            "the tie-break; under %s room reads ⛔ into supply." % _pct(DR.MIN_ROOM_DEFAULT),
        ],
        "stops": _zone_lines(),
        "alerts": [
            _sweep_line(),
            _sector_heat_line(),
            "\U0001F3AF Ready to enter (\u26A1 Signals tab, pre-market 08:00 ET and every 15 min in "
            "session): the same two gates decide READY; a name that clears them still grades "
            "WATCH if it is reclaiming the band from below (measured %s floor-stop rate vs %s "
            "for arrivals from above) or is down %s\u2013%s on the day (%s closed above the "
            "print vs %s). BLOCKED rows stay on the board with the gate they failed. Mood "
            "orders rows inside a grade and never decides one."
            % (_pct(PME.RECLAIM_STOP_PCT), _pct(PME.ARRIVAL_STOP_PCT),
               _pct(abs(PME.WEAK_DAY_HI_PCT)), _pct(abs(PME.WEAK_DAY_LO_PCT)),
               _pct(PME.WEAK_DAY_UP_PCT), _pct(PME.NORMAL_DAY_UP_PCT)),
            "🧲 demand_alert pushes only names ≥ %s cap that are inside the band or ≤ %s "
            "above its top, with ≥ %s room (see Alerts)." % (_b(DA.MIN_CAP_USD),
                                                             _pct(DA.AT_PCT), gate_room),
        ],
        "note": _DISCLAIMER,
    }

    out["deep_demand"] = {
        "title": "Deep Demand", "emoji": "🕳️",
        "picks": [
            "Price fell through the top demand band and is arriving at the SECOND band from "
            "the top: inside it, or ≤ %s above it and entering from above." % _pct(PZ.NEAR_PCT),
            "Same band bar as Back in Demand: ≥ %d touches, strength ≥ %d."
            % (DR.MIN_TOUCHES, int(DR.MIN_ZONE_STRENGTH)),
            "Sales intact: the revenue snapshot is joined at board time (penalized names "
            "whose sales still grow).",
            "Closest-first order; the board keeps up to %d in-band and %d approaching names."
            % (DD.MAX_IN, DD.MAX_NEAR),
        ] + _room_lines(),
        "stops": _zone_lines(),
        "alerts": [],
        "note": _DISCLAIMER,
    }

    out["alerts"] = {
        "title": "Zone alerts", "emoji": "🔔",
        "picks": [
            "Every zone push passes the gate: ≥ %s room to the first PROVEN band overhead "
            "(CLEAR ok); demand-side kinds also need the print ≤ %s above the band top and not "
            "under its floor. Boards list everything; only the phone is gated."
            % (gate_room, gate_prox),
            _closed_day_line(),
            _proven_line(),
            "🧲 and 🪃 bodies carry the plan: buy = the band, stop = %s under its floor with the "
            "risk from the print, target = the first proven lid with the R multiple."
            % _pct(AG.STOP_BUFFER_PCT),
            "🧲 demand_alert (every 5 min, %s–%s ET, cap ≥ %s): inside the band or ≤ %s above "
            "its top → push; %s–%s above and falling → digest; max %d singles per pass."
            % (_t(DA.SESSION_OPEN), _t(DA.SESSION_CLOSE), _b(DA.MIN_CAP_USD),
               _pct(DA.AT_PCT), _pct(DA.AT_PCT), _pct(DA.NEAR_PCT), DA.MAX_SINGLES_PER_PASS),
            "🪃 zone_bounce_alert (every 5 min, %s–%s ET): an arrival (prior close > %s above "
            "the top) whose low touched the band (≤ %s above the top, wick ≤ %s under the "
            "floor) and reversed ≥ max(%s, 1 ATR); a single push needs ≥ max(%s, 2 ATR), the "
            "rest ride the digest; max %d singles; print ≤ %d min old."
            % (_t(ZB.SESSION_OPEN), _t(ZB.SESSION_CLOSE), _pct(ZB.ARRIVAL_PCT),
               _pct(ZB.TOUCH_TOL_PCT), _pct(ZB.WICK_PCT), _pct(ZB.BOUNCE_MIN_PCT),
               _pct(ZB.STRONG_PCT), ZB.MAX_SINGLES_PER_PASS, ZB.STALE_PRINT_SEC // 60),
            "🚀 supply_break_alert (pass every minute %s–%s ET incl. pre-market and after-hours; "
            "phone pushes %s–%s ET): crossed a supply band tested ≥ %d "
            "times, at most %s through it; near tier within %s under; 'new highs' when the "
            "band top is ≥ %d%% of the 252-bar high; room measured to the next band above; "
            "max %d singles; print ≤ %d min old."
            % (_t(ZE.SESSION_OPEN), _t(ZE.SESSION_CLOSE), _t(ZE.PUSH_OPEN), _t(ZE.PUSH_CLOSE),
               ZE.MIN_TOUCHES_PUSH,
               _pct(ZE.BROKE_MAX_PCT), _pct(ZE.EDGE_PCT), int(ZE.NEW_HIGH_TOL * 100),
               ZE.MAX_SINGLES_PER_PASS, ZE.STALE_PRINT_SEC // 60),
            "Near demand (within %s of a band) rides the same minute pass as a demand_alert."
            % _pct(ZE.EDGE_PCT),
        ],
        "stops": [
            "Alerts carry no stop: the board's trade plan does (stop %s under the band floor, "
            "target the first unbroken band above the print)." % _pct(DR.STOP_BUFFER_PCT),
            "Positions: 🎯 position_alert fires once per band per day when a holding nears "
            "the first supply band overhead, and on every Auto-Pilot stop / exit.",
        ],
        "alerts": [],
        "note": _DISCLAIMER + " Zone bands come from zone_store (cap ≥ %s, ≥ %d bars)."
                % (_b(ZS.MIN_CAP_USD), ZS.MIN_BARS),
    }

    out["autopilot"] = {
        "title": "Auto-Pilot lanes (paper)", "emoji": "🤖",
        "picks": [
            "📈 Minervini: scanner is_buyable (trend template + Stage 2 + setup), score ≥ %d, "
            "RS ≥ %d, relative volume ≥ %.1f with first-half volume confirmation, at most %s "
            "past the pivot; %d buys per day."
            % (int(AE.AUTO_MIN_SCORE), int(AE.AUTO_MIN_RS), AE.AUTO_RELVOL_MIN,
               _pct(AE.MAX_EXTENSION_PCT), AE.MAX_AUTO_ENTRIES_PER_DAY),
            "🧲 Demand-zone / 🚀 breakout: the zone-edge board's rules (owner switches: "
            "residents, any-band breakout, min touches) PLUS the alert gate (≥ %s room to the "
            "first proven lid, ≤ %s above the band), ≥ 2R room over the stop, cap ≥ %s, "
            "signal ≤ %d s old, no new entry after %s ET; %d+%d per day (breakouts + demand "
            "arrivals, each side its own cap since 2026-09-08)."
            % (gate_room, gate_prox, _b(ZEE.MIN_CAP_USD), ZEE.SIGNAL_MAX_AGE_SEC,
               _t(ZEE.LAST_ENTRY_ET), ZEE.MAX_ZONE_ENTRIES_PER_SIDE_PER_DAY,
               ZEE.MAX_ZONE_ENTRIES_PER_SIDE_PER_DAY),
            "🗞️ Catalyst: from the Catalysts scan — quadrant %s, evidence grade %s, no pump "
            "warning, no offering, price ≥ $%d, dollar volume ≥ $%dM — and the same gate "
            "read through bounce-room; %d per day."
            % ("/".join(CE.QUADRANTS_OK), "/".join(CE.GRADES_OK), int(CE.CATALYST_MIN_PRICE),
               int(CE.CATALYST_MIN_DOLLAR_VOL / 1e6), CE.MAX_CATALYST_ENTRIES_PER_DAY),
            "⏱️ 0DTE paper lane: Signal Lab's 1-min BUY / SELL tag (≤ %d s old) on the 0DTE tab's "
            "names with a SAME-DAY chain → the tab's call / put pick; entries %s–%s ET, "
            "min(%g%% of equity, $%d) a trade, %d a day, exits on the stock first (signal stop / "
            "2R), then the premium (+%d%% / −%d%%), flat by %s. Paper only."
            % (ZDL.SIGNAL_MAX_AGE_SEC, _t(ZDL.ENTRY_OPEN_ET), _t(ZDL.LAST_ENTRY_ET),
               ZDL.RISK_PCT_OF_EQUITY, int(ZDL.MAX_PREMIUM_PER_TRADE), ZDL.MAX_ENTRIES_PER_DAY,
               int(ZDL.PREMIUM_TAKE_PCT), int(ZDL.PREMIUM_STOP_PCT), _t(ZDL.FLATTEN_ET)),
            "\U0001F6E1\uFE0F Safety floors — EVERY lane, no exceptions (they all buy through "
            "the one entry function): share price ≥ $%.2f and, when the cap is known, market "
            "cap ≥ %s. An unknown cap or a tape under $%dM/day WARNS instead of blocking."
            % (SFL.MIN_SHARE_PRICE, _b(SFL.MIN_CAP_USD), int(SFL.MIN_DOLLAR_VOL / 1e6)),
            "Every entry is journaled by strategy (minervini / demand_zone / breakout / "
            "catalyst / options_zone / zero_dte / manual).",
            # Ajay 2026-09-12 chose "charts and scans only" for the robotics
            # ETFs once this limit surfaced. It is invisible from the board —
            # an ETF just quietly never alerts — so the rules panel says it.
            "\U0001F4CA ETFs chart and scan but NEVER alert. The provider reports no market "
            "cap for a fund, only AUM, and the zone store keeps only a KNOWN cap \u2265 %s \u2014 "
            "so an ETF gets no zone bands and therefore no demand, reversal or supply-break "
            "push. Affects KOID, BOTZ, ROBO, ARKQ, ROBT and every index anchor."
            % _b(SFL.MIN_CAP_USD),
        ],
        "stops": [
            "Minervini stop: %s–%s of entry in a normal tape, %s–%s when difficult, never "
            "over %s; half the average gain once %d trades exist."
            % (_pct(RR.NORMAL_STOP_BAND[0]), _pct(RR.NORMAL_STOP_BAND[1]),
               _pct(RR.DIFFICULT_STOP_BAND[0]), _pct(RR.DIFFICULT_STOP_BAND[1]),
               _pct(RR.ABS_MAX_STOP_PCT), RR.HALF_AVG_GAIN_MIN_TRADES),
            "Minervini target %s–%s (difficult %s–%s), reward:risk ≥ %.0f; stop moves to "
            "breakeven at %.0f× the initial risk."
            % (_pct(RR.NORMAL_PROFIT_BAND[0]), _pct(RR.NORMAL_PROFIT_BAND[1]),
               _pct(RR.DIFFICULT_PROFIT_BAND[0]), _pct(RR.DIFFICULT_PROFIT_BAND[1]),
               RR.MIN_REWARD_RISK, RR.BREAKEVEN_AT_RISK_MULTIPLE),
            "Zone and catalyst lanes: stop %s under the band floor as an absolute price, "
            "floored at %s, never over %s; same breakeven ratchet."
            % (_pct(ZEE.STOP_BUFFER_PCT), _pct(ZEE.RISK_STOP_FLOOR_PCT),
               _pct(RR.ABS_MAX_STOP_PCT)),
            "Sizing: at most %d positions, %d%% of equity each; after %d straight stop "
            "losses size drops to ×%.2g then ×%.2g."
            % (RR.MAX_POSITIONS, int(RR.MAX_POSITION_FRACTION * 100), RR.STREAK_HALVE_AFTER,
               RR.STREAK_MULTIPLIERS[1], RR.STREAK_MULTIPLIERS[2]),
            "Exits the broker refuses outside the session queue and go out at the open.",
        ],
        "alerts": [
            "position_alert on every stop hit, target fill, watchdog exit and queued exit.",
        ],
        "note": "Paper account. Minervini numbers are TLSW pp.291-315 (trading/risk_rules.py); "
                "zone and catalyst lanes are owner rules, no book.",
    }

    out["growth"] = {
        "title": "\U0001F680 Explosive Growth", "emoji": "\U0001F680",
        "picks": [
            "Sales up %d%%+ AND quarterly EPS up %d%%+ year-over-year on the latest "
            "reported quarter — and the quarter BEFORE it also growing. That last leg is "
            "what separates a real ramp from a name lapping one bad quarter."
            % (int(GT.MIN_SALES_GROWTH_PCT), int(GT.MIN_EPS_GROWTH_PCT)),
            "NO market-cap floor on this board (his call, 2026-09-11). Every other board "
            "and the trading engine use %s, so a row marked \u26D4 is on the list here and "
            "REFUSED at the broker — the row says which." % _b(SFL.MIN_CAP_USD),
            "Rebuilt Sundays 09:00 ET, after the weekly research refresh writes the "
            "fundamentals it screens on — new Russell entrants join on their own.",
            "Screened over the weekly research cache (the `broad` universe, ~3,700 names), "
            "which is WIDER than the ~2,650 the zone bands are built from — so a row can "
            "qualify and carry no demand read at all. That prints as \u201Cno zone bands\u201D, "
            "never as an empty one.",
        ],
        "stops": [
            "Nothing on this board is a stop or a size. It is a discovery list: the "
            "100/100 screen has never been measured forward.",
        ],
        "alerts": [
            "\U0001F680 %s fires when a board name is inside a tested demand band whose "
            "floor has NEVER been pierced (the one gate that measured, +8.6pp over 31,861 "
            "events), with \u2265 %s room to the first band overhead and the print between "
            "the band floor and %s above its top. One push per name per band per day."
            % (GA.KIND, gate_room, gate_prox),
            "An order block is carried in the push body and gates NOTHING — the ICT study "
            "measured +0.03R over 6,004 signals.",
            "A name the engine will refuse still alerts, labelled \u26D4 — the board has no "
            "cap floor, so silence would hide it.",
        ],
        "note": "Owner screen, no book. Not backtested.",
    }

    bounce = [
        "Bouncing = a session low in the last %d sessions touched a demand band (or a supply "
        "band already broken above) and the print is ≥ max(%s, 1 ATR) above it."
        % (BR.LOOKBACK_SESSIONS, _pct(BR.BOUNCE_MIN_PCT)),
        "Room = distance to the first unbroken PROVEN band overhead: CLEAR, ROOM, NEAR (≤ %s), or "
        "IN_BAND; at highs = print ≥ %d%% of the 252-bar high."
        % (_pct(BR.NEAR_PCT), int(round(BR.NEW_HIGH_TOL * 100))),
        _proven_line(),
        "Order: a reversal off demand with ≥ %s room, then ≥ %s room, then a reversal "
        "heading ⛔ into supply, "
        "then the rest." % (_pct(DR.MIN_ROOM_DEFAULT), _pct(DR.MIN_ROOM_DEFAULT)),
    ]
    out["sepa_bounce"] = {
        "title": "🪃 Reversal from Demand", "emoji": "🪃",
        "picks": bounce,
        "stops": ["A filter, not an entry: the plan (stop, target) lives on the Back in "
                  "Demand board."],
        "alerts": [],
        "note": _DISCLAIMER,
    }
    out["catalysts"] = {
        "title": "Catalysts room sort", "emoji": "⚡",
        "picks": bounce,
        "stops": ["The 🗞️ catalyst lane buys at most %d per day with a stop %s under the "
                  "demand band floor." % (CE.MAX_CATALYST_ENTRIES_PER_DAY,
                                          _pct(CE.STOP_BUFFER_PCT))],
        "alerts": [],
        "note": _DISCLAIMER,
    }
    out["options"] = {
        "title": "Options lane (paper)", "emoji": "🎛️",
        "picks": [
            "Signal = the same demand-zone touch the stock lane buys: zone-edge near/in row "
            "passing the alert gate (≥ %s room, ≤ %s above the band top), cap ≥ %s, print ≥ $%d."
            % (gate_room, gate_prox, _b(OL.MIN_CAP_USD), int(OL.MIN_UNDERLYING_PRICE)),
            "Long call strike = highest strike at or under the band top with delta %.2f–%.2f; "
            "spread short strike = lowest strike at or above the first supply band (the room target)."
            % (OL.DELTA_LO, OL.DELTA_HI),
            "Expiry %d–%d days out; skip if earnings sits inside the window." % (OL.MIN_DTE, OL.MAX_DTE),
            "Long call by default. IV ≥ %d%%: sell a put SPREAD under the band floor — short put = "
            "highest strike at or under the floor, long put ~%g%% lower, credit ≥ %d%% of the width, "
            "bought back at ≤ %d%% of the credit; no liquid put spread → bull call spread → long call. "
            "Never a naked put."
            % (int(OL.IV_SPREAD_THRESHOLD * 100), OL.PUT_SPREAD_WIDTH_PCT,
               int(OL.MIN_CREDIT_PCT_OF_WIDTH), int(OL.TAKE_PROFIT_PCT_OF_CREDIT)),
            "Liquidity: open interest ≥ %d, bid-ask ≤ %d%% of mid (or ≤ $%.2f)."
            % (OL.MIN_OPEN_INTEREST, int(OL.MAX_SPREAD_PCT_OF_MID), OL.MAX_SPREAD_ABS),
            "%d entry per day, %d open names, one position per underlying; %d contracts sized to "
            "min(%g%% of equity, $%d) premium." % (OL.MAX_OPTIONS_ENTRIES_PER_DAY, OL.MAX_OPEN_OPTIONS,
                                                    1, OL.RISK_PCT_OF_EQUITY, int(OL.MAX_PREMIUM_PER_TRADE)),
        ],
        "stops": [
            "Exit on the underlying, never on the premium: a print under the band floor − %s closes it."
            % _pct(OL.STOP_BUFFER_PCT),
            "Take profit when the underlying reaches the first supply band (the short strike on a spread).",
            "Time exit at %d DTE; close %d days before earnings." % (OL.CLOSE_DTE, OL.EARNINGS_CLOSE_DAYS),
            "Max loss per trade = the premium paid (long call / debit spread).",
        ],
        "alerts": ["position_alert on every options entry, close sent and close filled."],
        "note": "Paper account (Alpaca options level 3). Owner rules from the 2026-09-06 chat, no book.",
    }

    out["quick_bounce"] = {
        "title": "Quick Reversal", "emoji": "🪃",
        "picks": [
            "Historical: a name is on the list when ≥ %d visits to a proven demand band "
            "(tested ≥ %d×) turned QUICK at least %d%% of the time — quick = "
            "the close lifted ≥ max(%s, 1 ATR) off the low on one of the first %d touch days, "
            "or the next session opened ≥ %s above the touch-day close (the KLAC gap)."
            % (QB.MIN_EVENTS, AG.LID_MIN_TOUCHES, int(QB.MIN_QUICK_RATE_PCT),
               _pct(QB.BOUNCE_MIN_PCT), QB.QUICK_MAX_TOUCH_DAYS, _pct(QB.GAP_MIN_PCT)),
            "Live: the print is inside a proven demand band or ≤ %s above its top (under the "
            "band = fell through, not listed), with ≥ %s room to the first proven lid (the "
            "alert gate). Nearest to the band first, most room as the tie-break."
            % (_pct(QB.NEAR_MAX_PCT), _pct(QB.ROOM_MIN_PCT)),
            "Every rate is shown next to the name's own any-day base rate, and the study's "
            "first-half → second-half persistence is printed under the board: a list, not a forecast.",
        ],
        "stops": [
            "Stop %s under the band floor (the paper lane's stop); target = the first proven lid."
            % _pct(QB.STOP_BUFFER_PCT),
            "Paper Auto-Pilot: a demand-zone entry on a Quick Reversal name is journaled as the "
            "quick_bounce lane and flattened at %s ET the same day (day-trade variant)."
            % "15:55",
        ],
        "alerts": ["No separate push: the 🧲 / 🪃 alerts already cover these names."],
        "note": _DISCLAIMER,
    }

    from supply_demand import turning_bullish as TB
    from supply_demand import keltner as KC
    from supply_demand import amd as AMD
    out["turning_bullish"] = {
        "title": "Turning Bullish — Keltner coil & AMD raid", "emoji": "🌀",
        "picks": [
            "Keltner tab: the Bollinger band sits INSIDE a %.1f× Keltner channel "
            "(the squeeze) or released it on the last bar, AND price is in the "
            "upper half of the %.1f× channel (position ≥ %.2f), AND the EMA-%d "
            "midline is higher than it was %d bars ago. All three, or the name "
            "grades 'upper half' and is context rather than a turn."
            % (KC.SQUEEZE_MULT, KC.MULT, TB.COILED_MIN_POSITION, KC.EMA_LEN,
               TB.MID_SLOPE_BARS),
            "AMD tab: a base of %d+ bars whose range fits inside %.1f× its own "
            "median true range (and under %.0f%% of price) had its LOW traded "
            "through and the bar CLOSED back inside it — the stops under the "
            "base are gone and the markup through the top has not happened. "
            "The raid must be within %d sessions: 'turning', his word, taken "
            "literally." % (AMD.MIN_BASE_BARS, AMD.MAX_BASE_ATR,
                            AMD.MAX_BASE_PCT, TB.MAX_RAID_BARS_AGO),
            "'Recent 6 months' = %d trading sessions; a cycle dated older than "
            "that reads as context and never as a turn." % TB.WINDOW_SESSIONS,
            "Both boards print their own FIRE RATE — what share of the scanned "
            "universe the state describes — under the tab. A state that fires "
            "on half the market is a description of the market, and the number "
            "is there so you can see that for yourself. Keltner fires on 5.4%% "
            "of names; AMD on 22.7%% at the %d-session bound and 45.8%% at ten "
            "sessions." % TB.MAX_RAID_BARS_AGO,
        ],
        "stops": [
            "No stop, no target and no size: neither board proposes a trade. "
            "The drawn levels are the channel bands and the base edges, which "
            "are where the chart's own structure is, not an entry plan.",
        ],
        "alerts": [
            "MEASURED 2026-09-13 AND BOTH CLAIMS CAME BACK INVERTED — not "
            "null, inverted. Keltner, 2,660 names / 1,200,755 closed daily "
            "bars: coiled bars returned LESS than every other bar of the same "
            "names (21d median lift −0.33pp, 95% CI −0.57 to −0.12), and a "
            "coiled name closes above its upper band within 21 sessions 40.0% "
            "of the time against 55.0% for a name in the same upper half with "
            "the same rising EMA and no squeeze — the squeeze makes that "
            "break 14.8pp LESS likely. AMD, 2,666 names / 1,150,446 bars: "
            "forward returns span zero leaning negative (21d lift −0.25%, CI "
            "−1.30 to +0.72), and against a like-for-like bar inside its own "
            "base at the same distance below the top a fresh raid makes the "
            "close above that top LESS likely — 42.7% vs 51.6%, −8.9pp (CI "
            "−11.4 to −5.9), negative in all seven distance buckets. Scripts: "
            "backend/scripts/turning_bullish_keltner_study.py and "
            "..._amd_study.py.",
            "NOTHING HERE PUSHES, GATES OR BUYS, and after that measurement "
            "nothing should without a new study saying otherwise. "
            "`keltner.CITED` and `amd.CITED` are both False. The app measured "
            "AMD's nearest relative, the ICT tab, at +0.03R over 6,004 "
            "signals against placebo (2026-09-04) — flat; these two are worse "
            "than flat.",
            "A squeeze is compression, NOT a direction — the Keltner module "
            "says so itself and this board does not overrule it. Direction "
            "here comes from the position and the midline slope, which is a "
            "convention too.",
        ],
        "note": _DISCLAIMER,
    }
    return out


def payload(section: Optional[str] = None) -> dict:
    secs = sections()
    if section:
        secs = {k: v for k, v in secs.items() if k == section}
    return {"sections": secs, "keys": list(SECTION_KEYS)}
