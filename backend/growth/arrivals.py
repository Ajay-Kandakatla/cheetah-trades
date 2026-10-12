"""✨ Arrivals on the 🚀 Explosive Growth board — the LIST EVENT, served.

Ajay 2026-10-12: "In the eplosive growth there are 7 new one can you gave me
special emphasis wiht a tag or something in the chart map pages top ..." and
"I saw an alert for 7 in explosive growth".

The 7 was board_arrival's digest spill (MAX_INDIVIDUAL singles + one digest);
11 names arrived. The surfaces therefore show the SERVED `arrivals_n`, never a
typed count.

Reads the ONE ledger (`tracker.SEEN_COLL` via `tracker.arrivals_map`) — no
second ledger, no recompute from `built_at`. Sorts nothing, filters nothing,
gates nothing, pushes nothing (Rule #10). The honesty line is built ONLY from
`ARRIVALS_MEASURED` (pinned field-for-field to the 2026-09-21 replay by
`tests/test_growth_arrivals.py`) plus `sepa.board_arrival.NOT_A_RECOMMENDATION`.
`board_arrival.NOT_BACKTESTED` ("the 100/100 screen has never been measured
forward") is deliberately NOT appended: this line opens "MEASURED 2026-09-21"
on that very screen's arrivals, and the two sentences side by side contradict.
"""
from __future__ import annotations

import logging

from growth import tracker as T
# Read-only reuse of the push's own wording. `sepa.board_arrival` imports
# `growth.alerts`, never `growth.api`, so `growth.api -> growth.arrivals ->
# sepa.board_arrival` is a DAG (pinned by a subprocess test).
from sepa.board_arrival import NOT_A_RECOMMENDATION

log = logging.getLogger("growth.arrivals")

HORIZONS = ("h21", "h63", "h126")

ARRIVALS_MEASURED = {
    "run_date": "2026-09-21",
    "doc": "docs/research/board_growth_2026_09_21.md",
    "script": "backend/scripts/board_growth_replay.py",
    "panel_dates": 24,                               # repro.n_dates_panel
    "cell": "G100_ARRIVE",
    # MEDIAN lift vs the scored universe, BOTH clusterings, EVERY horizon (2dp).
    "lift": {
        "h21":  {"n": 64, "n_symbols": 62, "n_dates": 7, "median_lift_pp": 3.69,
                 "ci_symbol": (-0.22, 10.13), "ci_date": (-0.43, 11.77)},
        "h63":  {"n": 62, "n_symbols": 60, "n_dates": 6, "median_lift_pp": 5.58,
                 "ci_symbol": (-2.25, 12.44), "ci_date": (-0.22, 15.40)},
        "h126": {"n": 39, "n_symbols": 38, "n_dates": 4, "median_lift_pp": 8.93,
                 "ci_symbol": (-5.45, 15.04), "ci_date": (-4.29, 11.80)},
    },
    # Excess over the trailing-momentum-quintile mean of all-scored. The CI is
    # on the MEAN and is symbol-clustered ONLY — the artifact carries no
    # date-clustered interval for this read — so the MEDIAN rides beside it
    # (the bonde.STEADY_MEASURED shape, pinned the same way).
    "momentum_control": {
        "h21":  {"n": 64, "mean_excess_pp": 6.61, "median_excess_pp": 1.37,
                 "ci_symbol": (1.65, 11.83)},
        "h63":  {"n": 62, "mean_excess_pp": 6.50, "median_excess_pp": -1.10,
                 "ci_symbol": (-3.86, 16.72)},
        "h126": {"n": 39, "mean_excess_pp": 5.89, "median_excess_pp": -6.38,
                 "ci_symbol": (-11.90, 24.00)},
    },
}


def _sgn(v, d: int = 2) -> str:
    """'+3.69' / '−0.22' — always signed, with a REAL minus (U+2212).

    The `sepa/bonde.py` helper, copied (it is private there). Applied per
    NUMBER only — never a sentence-wide replace, which would eat the hyphens
    in '2026-09-21', 'point-in-time' and 'symbol-clustered'."""
    return ("%s%%.%df" % ("+" if v >= 0 else "−", d)) % abs(v)


def refused(row: dict) -> bool:
    """True when the trading engine will refuse the name (a ⛔ warning — sub-$2
    or a known sub-$700M cap). The ONE rule, shared by `/growth/tags` and the
    arrivals list; the warnings themselves come from `tracker.row_warnings`."""
    return any(str(w).startswith("⛔") for w in ((row or {}).get("warnings") or []))


def _ci(pair) -> str:
    return "%s to %s" % (_sgn(pair[0]), _sgn(pair[1]))


def honesty_line() -> str:
    """The served sentence under every ✨ arrivals surface — lift AND the
    momentum-matched control, both clusterings, every horizon. Every number
    comes from ARRIVALS_MEASURED through `_sgn`; the count of negative
    control medians is computed, so 'two of three' can never go stale."""
    m = ARRIVALS_MEASURED
    L, C = m["lift"], m["momentum_control"]
    neg = sum(1 for h in HORIZONS if C[h]["median_excess_pp"] < 0)
    return (
        "MEASURED %s — AN ARRIVAL ON THIS BOARD IS A LIST EVENT, NOT A SIGNAL. "
        "In a point-in-time replay over %d monthly cross-sections, names ARRIVING "
        "on the 100/100 screen beat the scored universe by a MEDIAN %spp over the "
        "next 21 sessions (%d symbol-bars, %d symbols, %d dates) — 95%% CI %s "
        "symbol-clustered and %s date-clustered, both spanning zero; %spp at 63 "
        "days (CI %s symbol-clustered, %s date-clustered, both span zero); %spp "
        "at 126 days (CI %s and %s, both span zero). No lift interval clears zero "
        "on either clustering. Against a momentum-matched control the MEDIAN "
        "excess is %spp at 21 days, %spp at 63 and %spp at 126 — negative at %d "
        "of 3 horizons; the control's interval is on the MEAN and symbol-clustered "
        "only (%s, %s, %s) — no date-clustered interval exists for that read, and "
        "date clustering is the binding axis on this board. A lean, not a finding. "
        "%s"
    ) % (
        m["run_date"], int(m["panel_dates"]),
        _sgn(L["h21"]["median_lift_pp"]),
        int(L["h21"]["n"]), int(L["h21"]["n_symbols"]), int(L["h21"]["n_dates"]),
        _ci(L["h21"]["ci_symbol"]), _ci(L["h21"]["ci_date"]),
        _sgn(L["h63"]["median_lift_pp"]),
        _ci(L["h63"]["ci_symbol"]), _ci(L["h63"]["ci_date"]),
        _sgn(L["h126"]["median_lift_pp"]),
        _ci(L["h126"]["ci_symbol"]), _ci(L["h126"]["ci_date"]),
        _sgn(C["h21"]["median_excess_pp"]), _sgn(C["h63"]["median_excess_pp"]),
        _sgn(C["h126"]["median_excess_pp"]),
        neg,
        _ci(C["h21"]["ci_symbol"]), _ci(C["h63"]["ci_symbol"]),
        _ci(C["h126"]["ci_symbol"]),
        NOT_A_RECOMMENDATION["growth"],
    )


def attach(rows: list, db=None, days: int = T.NEW_GROWTH_DAYS) -> list:
    """Set row["is_new"] (bool) and row["first_seen"] (ISO str | None) on EVERY
    row, from ONE ledger read; return the arrivals in SERVED ROW ORDER (the
    board's own order), only for rows ON THE BOARD with a ledger stamp:
    [{"symbol", "first_seen", "liquid", "refused", "warnings"}].

    `liquid` and `warnings` are the row's own served fields — passed through,
    never re-derived. Never raises: no db / any error → every row is_new=False,
    first_seen=None, and []."""
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    for r in rows:
        r["is_new"] = False
        r["first_seen"] = None
    try:
        amap = T.arrivals_map(days=days, db=db) or {}
        amap = {str(k).upper(): v for k, v in amap.items() if v}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("growth.arrivals: ledger read failed: %s", exc)
        return []
    out = []
    seen = set()
    for r in rows:
        sym = str(r.get("symbol") or "").upper()
        stamp = amap.get(sym)
        if not sym or not stamp:
            continue
        r["is_new"] = True
        r["first_seen"] = stamp
        if sym in seen:
            continue
        seen.add(sym)
        out.append({"symbol": sym,
                    "first_seen": stamp,
                    "liquid": bool(r.get("liquid")),
                    "refused": refused(r),
                    "warnings": list(r.get("warnings") or [])})
    return out


def summary(arrivals: list, days: int = T.NEW_GROWTH_DAYS) -> dict:
    """The four payload keys. Touches no db, so it can sit outside the
    try/except that guards the ledger read."""
    arrivals = list(arrivals or [])
    return {"arrivals": arrivals, "arrivals_n": len(arrivals),
            "new_days": int(days), "arrivals_note": honesty_line()}
