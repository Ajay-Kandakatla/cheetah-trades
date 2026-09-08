"""Pankaj's Market Analysis — curated picks from a trusted outside analyst.

This is the single source of truth for the `/pankaj` page. (The
`pankaj_alerts` cron that pushed his levels was removed 2026-09-08 — Ajay:
"Remove all of Pankaj's alerts"; the page keeps every level.) Each pick
carries one or more *setups* — Pankaj's own
discretionary entry triggers, demand zones, stops and targets, transcribed
verbatim from his notes. They are NOT app-derived and NOT advice; the page
surfaces them ALONGSIDE the app's own SEPA indicators so Ajay can sanity-check
each call against the engine.

Conservative vs aggressive variants differ only in:
  • entry confirmation — conservative wants a *daily* close through the trigger,
    aggressive acts on an *hourly* close (or the intraday tag); and
  • stop placement — aggressive stops tighter, conservative gives more room.

Ajay 2026-06-09: "a dude I trust — I want indicators against his stock picks …
any time I update this page account for his indicators + add alerts."

To update: edit ``PICKS`` (one entry per ticker). The endpoint and the page
read from here, so a single edit fans out to both. Keep the
``analyst`` and ``not advice`` framing — these are Pankaj's reads, surfaced for
context, never a recommendation from the app.
"""
from __future__ import annotations

from typing import Optional

ANALYST = "Pankaj"

# Status tuning --------------------------------------------------------------
APPROACH_PCT = 1.5          # "approaching" a breakout trigger: within 1.5% below it
ZONE_PAD_PCT = 0.5          # treat price within 0.5% of a demand-zone edge as "in zone"


# ---------------------------------------------------------------------------
# The picks — Pankaj's notes, verbatim levels.
# ---------------------------------------------------------------------------
PICKS: list[dict] = [
    {
        "symbol": "VG",
        "name": "Venture Global",
        "analyst": ANALYST,
        "updated": "2026-06-09",
        "horizon": "2-3 weeks",
        "thesis": "Close above 13.35 runs to 14.5-15, then 16.5-17. Otherwise the "
                  "11-11.50 demand zone is the conservative buy.",
        "setups": [
            {
                "id": "breakout",
                "kind": "breakout",
                "label": "Breakout · close above 13.35",
                "trigger": 13.35,
                "confirm": {"conservative": "daily close", "aggressive": "hourly close"},
                "targets": [{"lo": 14.5, "hi": 15.0}, {"lo": 16.5, "hi": 17.0}],
                "stops": {"aggressive": 11.90, "conservative": 11.00},
                "note": "Close above 13.35 — daily (conservative) or hourly (aggressive). "
                        "Rally to 14.5-15, then 16.5-17 over the next 2-3 weeks.",
            },
            {
                "id": "pullback",
                "kind": "pullback",
                "label": "Pullback · 11.00-11.50 demand zone",
                "zone": {"lo": 11.00, "hi": 11.50},
                "stops": {"aggressive": 11.00, "conservative": 10.00},
                "note": "Pullback into the 11-11.50 demand zone is the conservative entry.",
            },
        ],
    },
    {
        "symbol": "OKE",
        "name": "ONEOK",
        "analyst": ANALYST,
        "updated": "2026-06-09",
        "horizon": "2-3 weeks",
        "thesis": "Close above 90 runs to 95-96, then 100-102. Otherwise the 83-85 "
                  "demand zone is the conservative buy.",
        "setups": [
            {
                "id": "breakout",
                "kind": "breakout",
                "label": "Breakout · close above 90",
                "trigger": 90.0,
                "confirm": {"conservative": "daily close", "aggressive": "hourly close"},
                "targets": [{"lo": 95.0, "hi": 96.0}, {"lo": 100.0, "hi": 102.0}],
                "stops": {"aggressive": 85.0, "conservative": 82.0},
                "note": "Close above 90 — daily (conservative) or hourly (aggressive). "
                        "Rally to 95-96, then 100-102 over the next 2-3 weeks.",
            },
            {
                "id": "pullback",
                "kind": "pullback",
                "label": "Pullback · 83-85 demand zone",
                "zone": {"lo": 83.0, "hi": 85.0},
                "stops": {"aggressive": 82.0, "conservative": 80.0},
                "note": "Pullback into the 83-85 demand zone is the conservative entry.",
            },
        ],
    },
    {
        "symbol": "MRVL",
        "name": "Marvell Technology",
        "analyst": ANALYST,
        "updated": "2026-06-09",
        "horizon": "swing (extreme)",
        "thesis": "Extreme pullback into 195-210 — may not trigger, but good R:R if it "
                  "does. Target 250-260, later 300-320.",
        "setups": [
            {
                "id": "pullback",
                "kind": "pullback",
                "label": "Pullback · 195-210 demand zone (extreme)",
                "zone": {"lo": 195.0, "hi": 210.0},
                "targets": [{"lo": 250.0, "hi": 260.0}, {"lo": 300.0, "hi": 320.0}],
                "stops": {"aggressive": 194.0, "conservative": 189.0},
                "extreme": True,
                "note": "Extreme and may not get triggered — but if it happens it's good "
                        "R:R. Target 250-260, later even 300-320.",
            },
        ],
    },
]


def load_picks() -> list[dict]:
    """Return a deep-ish copy of the picks list (callers may annotate freely)."""
    import copy
    return copy.deepcopy(PICKS)


def symbols() -> list[str]:
    return [p["symbol"] for p in PICKS]


# ---------------------------------------------------------------------------
# Pure status logic (no IO — unit-tested in tests/test_pankaj.py)
# ---------------------------------------------------------------------------
def _pct(a: float, b: float) -> float:
    """Percent of a relative to b, i.e. (a/b - 1) * 100. Rounded to 1dp."""
    if not b:
        return 0.0
    return round((a / b - 1.0) * 100.0, 1)


def setup_status(setup: dict, price: Optional[float]) -> dict:
    """Where ``price`` sits relative to a setup — drives the page's live badge.

    Returns ``{"state": ..., "dist_pct": ..., "detail": ...}``. ``state`` is one
    of: unknown / below / approaching / triggered (breakout) ·
    below_zone / in_zone / above_zone (pullback)."""
    if price is None:
        return {"state": "unknown", "dist_pct": None, "detail": "no live price"}

    if setup["kind"] == "breakout":
        trig = float(setup["trigger"])
        dist = _pct(price, trig)                     # +ve = above trigger
        if price >= trig:
            return {"state": "triggered", "dist_pct": dist,
                    "detail": f"{dist:+.1f}% vs trigger — needs a close above to confirm"}
        if price >= trig * (1 - APPROACH_PCT / 100.0):
            return {"state": "approaching", "dist_pct": dist,
                    "detail": f"{abs(dist):.1f}% below the {trig:g} trigger"}
        return {"state": "below", "dist_pct": dist,
                "detail": f"{abs(dist):.1f}% below the {trig:g} trigger"}

    # pullback
    zone = setup["zone"]
    lo, hi = float(zone["lo"]), float(zone["hi"])
    pad_hi = hi * (1 + ZONE_PAD_PCT / 100.0)
    pad_lo = lo * (1 - ZONE_PAD_PCT / 100.0)
    if pad_lo <= price <= pad_hi:
        return {"state": "in_zone", "dist_pct": 0.0,
                "detail": f"in the {lo:g}-{hi:g} demand zone"}
    if price > pad_hi:
        return {"state": "above_zone", "dist_pct": _pct(price, hi),
                "detail": f"{_pct(price, hi):+.1f}% above the zone top ({hi:g})"}
    return {"state": "below_zone", "dist_pct": _pct(price, lo),
            "detail": f"{_pct(price, lo):+.1f}% — below the zone / near stop"}
