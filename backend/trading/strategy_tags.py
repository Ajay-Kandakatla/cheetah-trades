"""Chart Maps strategy roster — which Chart Maps tab is which paper lane.

Ajay 2026-09-27: "stop minerviews use all strategies from Most used from Chart
maps. All of them and journal the," — and, the same day, "Small: 0.25% risk,
15 open max", "Top 10 most-used first".

This module is a LEAF (stdlib only). It names every Chart Maps tab once, says
whether it is a lane, which engine trades it, whether it starts ON, and what
was measured about it before the program started. Nothing here trades; the
caps live in trading/program_caps.py and the generic lane in
trading/chart_maps_lanes.py.

THE SID IS THE TAB KEY. A strategy id ("sid") is the Chart Maps tab key the
frontend counts opens under (`chart-maps:tab:<tab>` in usage_stats). The four
lanes that existed before the program keep their own journal tags —
`demand_zone`, `breakout`, `catalyst`, `zero_dte` — so their ledger and
autopsy history stays readable; `TAG_TO_SID` maps them onto the roster and
every program function normalises through `norm()` before it counts, caps or
sizes anything.

UNMEASURED. Every prior below is null, inverted, negative or unmeasured: this
program is a forward paper MEASUREMENT, not a strategy with an expected edge.
"""
from __future__ import annotations

import os
from typing import Optional

# ── The one sentence every LIST lane carries (critic 10) ─────────────────────
LIST_NOTE = ("Buys a 🎯 READY demand reversal on a name from this tab's list, "
             "not the tab's own setup.")
PATTERNS_NOTE = (LIST_NOTE + " Confirmed patterns are bought only at demand, never "
                 "on the breakout; most are cup-with-handle bases.")
PLAN_NOTE = ("Buys the tab's own served BUY/STOP plan, only when the 🎯 READY "
             "read on the live print agrees.")

LANE, NOT_A_LANE_KLASS = "lane", "not_a_lane"


def _lane(sid, tabs, lane, adapter, kind, default_on, note, label_tab=None):
    return {"sid": sid, "tabs": tuple(tabs), "label_tab": label_tab or tabs[0],
            "lane": lane, "adapter": adapter, "kind": kind, "klass": LANE,
            "reason": None, "default_on": bool(default_on), "note": note}


def _not_lane(tab, reason):
    return {"sid": tab, "tabs": (tab,), "label_tab": tab, "lane": None,
            "adapter": None, "kind": None, "klass": NOT_A_LANE_KLASS,
            "reason": reason, "default_on": False,
            "note": "Not a lane: %s." % reason}


# Roster order = the 2026-09-27 usage order (the ON set is FROZEN from it; the
# live order is re-read once per ET day by program_caps.priority_order).
ROSTER = (
    _lane("zones", ["zones"], "zone_edge_demand", None, "demand", True,
          "The zone-edge demand lane (journal tag demand_zone), now under the "
          "program's caps and journal."),
    _lane("deep_demand", ["deep_demand"], "generic", "PLAN", "demand", True, PLAN_NOTE),
    _lane("catalysts", ["catalysts"], "catalyst_entry", None, "demand", True,
          "The catalyst lane (journal tag catalyst), now under the program's caps "
          "and journal."),
    _lane("amd", ["amd"], "generic", "LIST", "demand", True, LIST_NOTE),
    _lane("bonde", ["bonde"], "generic", "LIST", "demand", True,
          LIST_NOTE + " Arrivals only (the board's own is_new)."),
    _lane("hot_pullback", ["hot_pullback"], "hot_pullback_entry", None, "demand", True,
          "Yesterday's flush into demand bought at the open; now also passes the "
          "standing alert gate (room + proximity)."),
    _lane("growth", ["growth"], "generic", "LIST", "demand", True, LIST_NOTE),
    _lane("quick_bounce", ["quick_bounce"], "zone_edge_demand", None, "demand", True,
          "The zone-edge Quick Reversal day-trade variant, flattened at 15:55 ET."),
    _lane("patterns", ["patterns"], "generic", "LIST", "demand", True, PATTERNS_NOTE),
    _lane("breaking", ["breaking"], "zone_edge_supply", None, "supply_break", True,
          "The zone-edge breakout lane (journal tag breakout), now under the "
          "program's caps and journal."),
    _lane("keltner", ["keltner"], "generic", "LIST", "demand", False, LIST_NOTE),
    _lane("signals", ["signals", "zero_dte"], "zero_dte_lane", None, "signal", False,
          "The 0DTE options lane (journal tag zero_dte). OFF while the program is "
          "ON; its open contracts are still managed every tick."),
    _lane("ict", ["ict"], "generic", "PLAN", "demand", False,
          PLAN_NOTE + " Bullish entry-state ICT tiles only."),
    _lane("gnt", ["gnt"], "generic", "LIST", "demand", False,
          LIST_NOTE + " Fresh posts only."),
    _lane("ipo", ["ipo"], "generic", "LIST", "demand", False, LIST_NOTE),
    _lane("potus", ["potus"], "generic", "LIST", "demand", False,
          LIST_NOTE + " New disclosures only."),
    _lane("gabbar", ["gabbar"], "generic", "LIST", "demand", False, LIST_NOTE),
    _lane("session", ["session"], "generic", "PLAN", "demand", False,
          PLAN_NOTE + " Only rows that carry a session trade signal."),
    _lane("undervalue", ["undervalue"], "generic", "LIST", "demand", False, LIST_NOTE),
    _lane("overnight", ["overnight"], "generic", "LIST", "demand", False,
          LIST_NOTE + " Up-gappers only."),
    _lane("earnings", ["earnings"], "generic", "LIST", "demand", False,
          LIST_NOTE + " Names that already reported only; an upcoming report is never bought."),
    _lane("hot_sectors", ["hot_sectors"], "generic", "LIST", "demand", False,
          LIST_NOTE + " A sector view; not counted in the top 10."),
    _not_lane("support", "a one-ticker tool, not a list"),
    _not_lane("holdings", "his own positions"),
    _not_lane("ema_frames", "weekly and monthly chart view, no daily demand read"),
    _not_lane("news", "no tickers"),
    _not_lane("winners", "a hindsight ledger selected by outcome"),
    _not_lane("topping", "bearish; the program is long-only"),
    _not_lane("vcp", "OFF with Minervini: the SEPA slice, whose lane is auto_entry"),
)

_BY_SID = {r["sid"]: r for r in ROSTER}

NOT_A_LANE = {r["sid"]: r["reason"] for r in ROSTER if r["klass"] == NOT_A_LANE_KLASS}

# Default ON = the 10 highest-usage long buy-list tabs on 2026-09-27 (Ajay:
# "Top 10 most-used first"), hot_sectors not counted. FROZEN: a later usage
# shift reorders dispatch priority but never switches a lane on or off.
DEFAULT_ON = frozenset(r["sid"] for r in ROSTER if r["klass"] == LANE and r["default_on"])

EXISTING_LANE_SIDS = frozenset({"zones", "breaking", "quick_bounce", "catalysts",
                                "hot_pullback", "signals"})

# Legacy journal tags -> roster sid. Every new generic tag equals its sid.
TAG_TO_SID = {"demand_zone": "zones", "breakout": "breaking", "quick_bounce": "quick_bounce",
              "catalyst": "catalysts", "hot_pullback": "hot_pullback", "zero_dte": "signals"}

# Non-roster tags: their own switches decide (Minervini auto_entry, the
# options-zone lane, manual buys from the Trading page).
NON_ROSTER_TAGS = ("minervini", "options_zone", "manual")

# Journal tags a program lane may write on an entry row, besides the five in
# entries.STRATEGIES: every generic sid plus the two existing lanes whose tags
# entries used to coerce to 'manual' (hot_pullback, quick_bounce).
PROGRAM_TAGS = tuple(r["sid"] for r in ROSTER
                     if r["klass"] == LANE and r["lane"] == "generic") + ("quick_bounce", "hot_pullback")

# Chart Maps tab opens, read live 2026-09-27 from usage_stats (count, last_seen).
FROZEN_USAGE_2026_09_27 = {
    "zones": (268, 1790562294), "deep_demand": (125, 1790528090),
    "hot_sectors": (122, 1790484057), "support": (96, 1790366773),
    "catalysts": (85, 1790355695), "amd": (72, 1790354363),
    "hot_pullback": (69, 1790357262), "bonde": (69, 1790357262),
    "growth": (59, 1790356623), "quick_bounce": (57, 1790339014),
    "patterns": (49, 1790339028), "breaking": (39, 1790339027),
    "keltner": (30, 1790339028), "signals": (27, 1789874523),
    "ict": (23, 1790312530), "gnt": (21, 1790223120), "ipo": (18, 1790354476),
    "gabbar": (17, 1790270459), "potus": (17, 1790354498),
    "session": (11, 1789651438), "holdings": (10, 1790267903),
    "ema_frames": (9, 1790310356), "vcp": (8, 1789391796),
    "undervalue": (8, 1789363567), "overnight": (6, 1790270493),
    "news": (4, 1790354267), "earnings": (1, None), "winners": (1, None),
    "zero_dte": (1, None), "topping": (0, None),
}

# ── Priors (§1.9). `source` is a repo path, verified to exist at import; a
# missing path downgrades the prior to "unmeasured" with no source. ─────────
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_PRIORS_RAW = {
    "zones": ("no_signal", "Reversal baseline 24% win / 75% stop-out; the 🎯 READY "
              "read's own replay is no_signal (base R20 median -1).",
              "backend/scripts/entry_trigger_measured.json"),
    "deep_demand": ("null", "Deep levels 2/3/4 measured null.",
                    "backend/scripts/deep_levels_measured.json"),
    "amd": ("inverted", "Turning-bullish AMD read measured INVERTED vs placebo (~3,700 names).",
            "backend/scripts/turning_bullish_amd_study.py"),
    "keltner": ("inverted", "Keltner coil read measured INVERTED vs placebo (~3,700 names).",
                "backend/scripts/turning_bullish_keltner_study.py"),
    "bonde": ("inverted", "Bonde thesis measured INVERTED (2026-09-13); the board's own "
              "MEASURED block.", "backend/sepa/bonde.py"),
    # Cites the re-runnable study, never the merged research JSON: Rule #10's
    # guard (tests/test_board_growth_*.py) forbids a served module naming it.
    "growth": ("unmeasured", "Board arrivals +7.49pp at 63 sessions (CI +0.52..+16.06), "
               "but no entry, stop or cost model was measured.",
               "backend/scripts/board_growth_study.py"),
    "hot_pullback": ("null", "+0.100R (CI -0.188..+0.405) — includes zero.",
                     "backend/studies/hot_pullback_study.py"),
    "breaking": ("negative", "Tagged lane -0.70R; -0.54R (-0.92..-0.10) outside the "
                 "clusters (autopsy plan, 2026-09-27).", None),
    "signals": ("inconclusive", "First tag inconclusive: the sign depends on the placebo "
                "(autopsy plan, 2026-09-27).", None),
    "ict": ("no_signal", "No edge vs placebo (+0.03R, 6,004 signals).",
            "backend/ict/backtest.py"),
    "hot_sectors": ("null", "Sector heat measured null (-0.57pp, CI spans 0).",
                    "backend/studies/sector_heat_study.py"),
    "gabbar": ("unmeasured", "OOS 72% recovered, but no placebo was run.", None),
}
UNMEASURED_NOTE = "UNMEASURED as an entry."


def _prior(sid: str) -> dict:
    status, note, source = _PRIORS_RAW.get(sid, ("unmeasured", UNMEASURED_NOTE, None))
    if source is not None and not os.path.exists(os.path.join(_REPO_ROOT, source)):
        return {"status": "unmeasured", "note": note, "source": None}
    if source is None and status not in ("unmeasured",):
        # A result with no re-runnable script on this branch is not a prior we
        # can point at: the note keeps the number, the status says unmeasured.
        return {"status": "unmeasured", "note": note, "source": None}
    return {"status": status, "note": note, "source": source}


PRIORS = {r["sid"]: _prior(r["sid"]) for r in ROSTER if r["klass"] == LANE}


# ── Lookups ───────────────────────────────────────────────────────────────────
def roster_entry(sid: str) -> Optional[dict]:
    return _BY_SID.get(sid)


def sid_for_tag(tag) -> Optional[str]:
    """Roster sid for a journal tag: a roster sid returns itself (not-a-lane
    tabs included, so the caller can refuse them by klass), a legacy tag maps
    through TAG_TO_SID, anything else (minervini, options_zone, manual,
    unknown) is None."""
    if not isinstance(tag, str) or not tag:
        return None
    if tag in TAG_TO_SID:
        return TAG_TO_SID[tag]
    if tag in _BY_SID:
        return tag
    return None


def norm(tag) -> str:
    """The sid every count, cap, log and size uses; the raw tag otherwise."""
    s = sid_for_tag(tag)
    if s is not None:
        return s
    return tag if isinstance(tag, str) else "manual"


def is_roster(tag) -> bool:
    """True for a tag that maps onto a roster LANE (not-a-lane tabs are not)."""
    s = sid_for_tag(tag)
    return s is not None and _BY_SID[s]["klass"] == LANE


def is_not_a_lane(tag) -> bool:
    s = sid_for_tag(tag)
    return s is not None and _BY_SID[s]["klass"] == NOT_A_LANE_KLASS


def lane_sids() -> tuple:
    return tuple(r["sid"] for r in ROSTER if r["klass"] == LANE)


def generic_sids() -> tuple:
    return tuple(r["sid"] for r in ROSTER if r["klass"] == LANE and r["lane"] == "generic")


def usage_rank(counts: dict, last_seen: Optional[dict] = None) -> list:
    """Lane sids most-opened first. A multi-tab strategy sums its tabs'
    counts (and takes the newest last_seen). Ties: newest last_seen first,
    then sid ascending. A sid with no count sorts after every counted sid, in
    ROSTER order."""
    counts = counts if isinstance(counts, dict) else {}
    last_seen = last_seen if isinstance(last_seen, dict) else {}
    counted, uncounted = [], []
    for r in ROSTER:
        if r["klass"] != LANE:
            continue
        n, ls, seen_any = 0, None, False
        for t in r["tabs"]:
            c = counts.get(t)
            try:
                c = int(c) if c is not None else None
            except (TypeError, ValueError):
                c = None
            if c is not None and c > 0:
                n += c
                seen_any = True
            v = last_seen.get(t)
            try:
                v = float(v) if v is not None else None
            except (TypeError, ValueError):
                v = None
            if v is not None and (ls is None or v > ls):
                ls = v
        if seen_any:
            counted.append((r["sid"], n, ls if ls is not None else float("-inf")))
        else:
            uncounted.append(r["sid"])
    counted.sort(key=lambda t: (-t[1], -t[2], t[0]))
    return [t[0] for t in counted] + uncounted


def frozen_counts() -> tuple:
    """(counts, last_seen) dicts from FROZEN_USAGE_2026_09_27."""
    counts = {k: v[0] for k, v in FROZEN_USAGE_2026_09_27.items()}
    seen = {k: v[1] for k, v in FROZEN_USAGE_2026_09_27.items() if v[1] is not None}
    return counts, seen
