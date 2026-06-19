"""One-time SIM -> brokerage handover (Ajay 2026-06-19: "continue your previous
rodeo … if you can't use the previous portfolio in Alpaca yet that's ok").

When the Auto-Pilot engine switches its execution venue from the built-in
Massive-quote sim to a live/paper brokerage (Alpaca), the sim's still-OPEN
paper positions cannot move with it (different account). Rather than leave them
as ghost "open" round-trips that keep marking to live prices forever, we BOOK
them closed at their last simulated mark — a labelled `sim_handover` exit — so
the engine's track record captures the full sim chapter as realized history and
the only open trades going forward are the real brokerage ones.

This writes `trade_closed` ledger rows ONLY — never a broker order (the sim is
no longer the active venue; these are pure journal history). The booked exits
do NOT feed the engine's consecutive-loss streak (that reads broker fills, not
the ledger), so the sim's results never penalise live-paper sizing.

Idempotent: a symbol already booked at handover is skipped, so re-running is
safe. The journal reconstructs the round-trips from these rows on its next
reconcile() and computes the realized gain against each entry's recorded price
(the same basis as every other round-trip — single source of truth).

Run once, after the venue switch:
    docker compose exec api python -m trading.sim_handover           # book it
    docker compose exec api python -m trading.sim_handover --dry-run # preview
"""
from __future__ import annotations

import logging

from trading import broker_sim
from trading.exit_engine import _db, ledger

log = logging.getLogger("trading.sim_handover")

HANDOVER_LEG = "sim_handover"
_NOTE = ("SIM paper position booked at its last simulated mark on the Alpaca "
         "cutover — not an engine exit signal.")


def _already_booked(db, symbol: str) -> bool:
    """True if this symbol already has a sim_handover close (idempotency)."""
    if db is None:
        return False
    try:
        return db.trade_ledger.find_one(
            {"kind": "trade_closed", "symbol": symbol,
             "detail.leg": HANDOVER_LEG}) is not None
    except Exception as exc:                       # noqa: BLE001
        log.warning("sim_handover dedupe check failed %s: %s", symbol, exc)
        return False


def run(dry_run: bool = False) -> dict:
    """Book every open SIM position closed at its last mark. Returns a summary
    {ok, booked:[{symbol, qty, fill, gain_dollars_est}], skipped, errors}."""
    db = _db()
    out = {"ok": True, "booked": [], "skipped": [], "errors": []}
    try:
        positions = broker_sim.positions()
    except Exception as exc:                       # noqa: BLE001
        return {"ok": False, "booked": [], "skipped": [], "errors": [str(exc)]}

    for p in positions or []:
        sym = (p.get("symbol") or "").upper()
        if not sym:
            continue
        try:
            qty = int(float(p.get("qty") or 0))
            avg = float(p.get("avg_entry_price") or 0)
            last = float(p.get("current_price") or 0)
        except (TypeError, ValueError) as exc:
            out["errors"].append("%s: bad position fields: %s" % (sym, exc))
            continue
        if qty <= 0 or last <= 0:
            out["skipped"].append(sym)
            continue
        if _already_booked(db, sym):
            out["skipped"].append(sym)
            continue

        # Estimate the result for the run summary only; the journal recomputes
        # the canonical realized gain against the entry row's recorded price.
        gain_dollars_est = round(qty * (last - avg), 2) if avg else None
        # Leave gain_pct OUT of the detail so the journal owns it (single basis).
        detail = {"leg": HANDOVER_LEG, "fill": last, "qty": qty,
                  "avg_entry": avg, "mode": "sim", "note": _NOTE}
        rec = {"symbol": sym, "qty": qty, "fill": last,
               "gain_dollars_est": gain_dollars_est}
        if dry_run:
            out["booked"].append({**rec, "dry_run": True})
            continue
        ledger("trade_closed", symbol=sym, detail=detail, dry_run=False,
               cite="sim->brokerage handover; last simulated mark, not a signal")
        out["booked"].append(rec)

    return out


if __name__ == "__main__":
    import json
    import sys

    print(json.dumps(run(dry_run="--dry-run" in sys.argv), indent=2))
