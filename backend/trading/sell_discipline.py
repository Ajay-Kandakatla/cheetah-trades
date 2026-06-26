"""Minervini SELL discipline for HELD positions — pure verdict from a SEPA row.

The Auto-Pilot exit engine already protects the downside with a stop (the
watchdog). This adds the book's *active* sell signals on top, read every tick
from the latest SEPA scan row for the held name:

All sell signals -> auto_sell (market exit, like a hit stop):
    * close below the 200-day MA — the Stage 2->4 trend break (TLSW p.74-75)
    * Stage 4 decline AND price >=3% below the 50-day MA (TLSW p.73-75)
    * Stage 3 topping / distribution (TLSW p.72,86; TTLAC §9 ebook p.161)
    * climax / blow-off top (TLSW p.82,296)
    * MVP exhaustion on an extended stock (TTLAC §9 ebook p.166)

Ajay 2026-06-25 chose AGGRESSIVE: get OUT the moment ANY topping/distribution/
exhaustion signal fires, not just the decisive Stage-4 / 200-DMA breaks ("sell
stage 3 also"). The verdict keeps a distinct reason+cite per signal for the
ledger, but every action is auto_sell. ('alert' is still a valid action the
tick handles — flip a trigger back to it if a softer warning is ever wanted.)

PURE: takes the scan row dict + last price, returns a verdict or None. No I/O,
no pandas — unit-tested standalone. All trigger conditions map to fields the
scanner ALREADY computes (sepa/sell_signals.py, stage.py, volume.py,
climax_distribution.py, mvp.py); nothing is re-derived here.
"""
from __future__ import annotations

from typing import Optional


def evaluate(row: Optional[dict], last: Optional[float]) -> Optional[dict]:
    """Sell verdict for one held position from its latest SEPA scan row.

    Returns ``{action, kind, reason, cite}`` or ``None``:
      action 'auto_sell' — decisive break, market-exit now;
      action 'alert'     — sell-into-strength warning, notify only.
    Decisive breaks are checked first so a genuine Stage-4 trumps any warning.
    """
    if not row:
        return None
    stage_blk = row.get("stage") or {}
    stage = stage_blk.get("stage")
    sig = (row.get("sell_signals") or {}).get("signals") or {}
    vol = row.get("volume") or {}
    climax = row.get("climax_distribution") or {}
    ma50 = (row.get("trend") or {}).get("ma50")

    # ── DECISIVE trend breaks (checked first; trump the topping warnings) ────
    if sig.get("close_below_200ma"):
        return {"action": "auto_sell", "kind": "distribution_exit",
                "reason": "closed below the 200-day MA (Stage-4 trend break)",
                "cite": "TLSW p.74-75"}
    if stage == 4 and ma50 and last and float(last) < float(ma50) * 0.97:
        return {"action": "auto_sell", "kind": "distribution_exit",
                "reason": "Stage 4 decline, >=3% below the 50-day MA",
                "cite": "TLSW p.73-75"}

    # ── Topping / distribution / exhaustion → auto-sell (aggressive mode) ────
    if climax.get("is_distribution"):
        return {"action": "auto_sell", "kind": "distribution_exit",
                "reason": "climax / blow-off top — sell into strength",
                "cite": "TLSW p.82, p.296"}
    if row.get("mvp_exhaustion") or row.get("mvp_read") == "exhaustion":
        return {"action": "auto_sell", "kind": "distribution_exit",
                "reason": "MVP exhaustion (extended) — sell into strength",
                "cite": "TTLAC §9 ebook p.166"}
    if stage == 3 and (
            vol.get("accumulation_strength") == "distributing"
            or vol.get("cmf_signal") == "outflow"
            or stage_blk.get("volume_disagreement")):
        return {"action": "auto_sell", "kind": "distribution_exit",
                "reason": "Stage 3 topping — distribution under way",
                "cite": "TLSW p.72, p.86; TTLAC §9 ebook p.161"}
    return None
