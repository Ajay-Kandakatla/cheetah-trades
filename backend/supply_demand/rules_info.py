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
from trading import auto_entry as AE
from trading import zone_edge_entry as ZEE
from trading import catalyst_entry as CE
from trading import options_lane as OL
from . import alert_gates as AG
from . import bounce_room as BR
from . import demand_alerts as DA
from . import demand_reentry as DR
from . import deep_demand as DD
from . import price_zones as PZ
from . import zone_bounce_alerts as ZB
from . import zone_edge as ZE
from . import zone_store as ZS

SECTION_KEYS = ("in_demand", "deep_demand", "alerts", "autopilot",
                "sepa_bounce", "catalysts", "options")

_DISCLAIMER = ("Configured house rules on price structure — not a book method, "
               "not a buy signal, not financial advice.")


def _pct(x) -> str:
    x = float(x)
    return ("%d%%" % int(x)) if x == int(x) else ("%.1f%%" % x)


def _b(usd) -> str:
    return "$%dB" % int(float(usd) / 1e9)


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


def _room_lines():
    return [
        "Room floor: at least %s to the first unbroken band overhead (CLEAR counts); "
        "set Room to any to see everything." % _pct(DR.MIN_ROOM_DEFAULT),
    ]


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
            "broken band (a close below it, then a bounce back in).",
            "Approaching list: band top within %s below price and price down at least %s "
            "over the last %d sessions." % (_pct(DR.APPROACH_NEAR_PCT),
                                            _pct(DR.APPROACH_MIN_DRIFT_PCT),
                                            DR.APPROACH_DRIFT_BARS),
        ] + _room_lines() + [
            "Order: bouncing off the band with room first, then room, money-flow (CMF) as "
            "the tie-break; under %s room reads ⛔ into supply." % _pct(DR.MIN_ROOM_DEFAULT),
        ],
        "stops": _zone_lines(),
        "alerts": [
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
            "Every zone push passes the gate: ≥ %s room to the first band overhead (CLEAR "
            "ok); demand-side kinds also need the print ≤ %s above the band top and not "
            "under its floor. Boards list everything; only the phone is gated."
            % (gate_room, gate_prox),
            "🧲 demand_alert (every 5 min, %s–%s ET, cap ≥ %s): inside the band or ≤ %s above "
            "its top → push; %s–%s above and falling → digest; max %d singles per pass."
            % (_t(DA.SESSION_OPEN), _t(DA.SESSION_CLOSE), _b(DA.MIN_CAP_USD),
               _pct(DA.AT_PCT), _pct(DA.AT_PCT), _pct(DA.NEAR_PCT), DA.MAX_SINGLES_PER_PASS),
            "🪃 zone_bounce_alert (every 5 min, %s–%s ET): an arrival (prior close > %s above "
            "the top) whose low touched the band (≤ %s above the top, wick ≤ %s under the "
            "floor) and bounced ≥ max(%s, 1 ATR); a single push needs ≥ max(%s, 2 ATR), the "
            "rest ride the digest; max %d singles; print ≤ %d min old."
            % (_t(ZB.SESSION_OPEN), _t(ZB.SESSION_CLOSE), _pct(ZB.ARRIVAL_PCT),
               _pct(ZB.TOUCH_TOL_PCT), _pct(ZB.WICK_PCT), _pct(ZB.BOUNCE_MIN_PCT),
               _pct(ZB.STRONG_PCT), ZB.MAX_SINGLES_PER_PASS, ZB.STALE_PRINT_SEC // 60),
            "🚀 supply_break_alert (every minute, %s–%s ET): crossed a supply band tested ≥ %d "
            "times, at most %s through it; near tier within %s under; 'new highs' when the "
            "band top is ≥ %d%% of the 252-bar high; room measured to the next band above; "
            "max %d singles; print ≤ %d min old."
            % (_t(ZE.SESSION_OPEN), _t(ZE.SESSION_CLOSE), ZE.MIN_TOUCHES_PUSH,
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
            "residents, any-band breakout, min touches) PLUS the alert gate (≥ %s room, "
            "≤ %s above the band), ≥ 2R room over the stop, cap ≥ %s, signal ≤ %d s old, "
            "no new entry after %s ET; %d per day."
            % (gate_room, gate_prox, _b(ZEE.MIN_CAP_USD), ZEE.SIGNAL_MAX_AGE_SEC,
               _t(ZEE.LAST_ENTRY_ET), ZEE.MAX_ZONE_ENTRIES_PER_DAY),
            "🗞️ Catalyst: from the Catalysts scan — quadrant %s, evidence grade %s, no pump "
            "warning, no offering, price ≥ $%d, dollar volume ≥ $%dM — and the same gate "
            "read through bounce-room; %d per day."
            % ("/".join(CE.QUADRANTS_OK), "/".join(CE.GRADES_OK), int(CE.CATALYST_MIN_PRICE),
               int(CE.CATALYST_MIN_DOLLAR_VOL / 1e6), CE.MAX_CATALYST_ENTRIES_PER_DAY),
            "Every entry is journaled by strategy (minervini / demand_zone / breakout / "
            "catalyst / manual).",
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

    bounce = [
        "Bouncing = a session low in the last %d sessions touched a demand band (or a supply "
        "band already broken above) and the print is ≥ max(%s, 1 ATR) above it."
        % (BR.LOOKBACK_SESSIONS, _pct(BR.BOUNCE_MIN_PCT)),
        "Room = distance to the first unbroken band overhead: CLEAR, ROOM, NEAR (≤ %s), or "
        "IN_BAND; at highs = print ≥ %d%% of the 252-bar high."
        % (_pct(BR.NEAR_PCT), int(round(BR.NEW_HIGH_TOL * 100))),
        "Order: bouncing with ≥ %s room, then ≥ %s room, then bouncing but ⛔ into supply, "
        "then the rest." % (_pct(DR.MIN_ROOM_DEFAULT), _pct(DR.MIN_ROOM_DEFAULT)),
    ]
    out["sepa_bounce"] = {
        "title": "🪃 Bouncing off Demand", "emoji": "🪃",
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
            "Long call by default; bull call spread when the call's IV ≥ %d%%. No put selling in v1."
            % int(OL.IV_SPREAD_THRESHOLD * 100),
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

    return out


def payload(section: Optional[str] = None) -> dict:
    secs = sections()
    if section:
        secs = {k: v for k, v in secs.items() if k == section}
    return {"sections": secs, "keys": list(SECTION_KEYS)}
