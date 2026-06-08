"""At-the-pivot — SEPA candidates sitting AT or just under their buy point today.

The low-risk Minervini entry is the breakout AT the pivot on expanding volume
(p.203) — NOT chasing an extended/climax run. This surfaces the names coiling at
the pivot RIGHT NOW (with a live-price overlay so you can see which are still at
the pivot vs. already gapped over it overnight) so the entry isn't missed.

Derived view: reuses the scan's pivot + entry_exit + stage + a live snapshot;
`scanner.py` is untouched (Rule #2). Educational, not advice.
"""
from __future__ import annotations

import logging
import time

log = logging.getLogger("sepa.at_pivot")

ZONE_PCT = 5.0          # +% above the pivot = top of the buy zone (don't chase past, p.203)
NEAR_PCT = 5.0          # -% below the pivot = "approaching the trigger"
AT_BAND_LOW = -1.0      # within this % below → treat as already AT the pivot (in the zone)

_CACHE: dict = {"at": 0.0, "data": None}
_TTL_SEC = 120          # live prices move; 2-min cache


def _pivot(r: dict):
    es = r.get("entry_setup") or {}
    return es.get("pivot") or (r.get("vcp") or {}).get("pivot_buy_price")


def _has_sell_signal(r: dict) -> bool:
    return (r.get("sell_signals") or {}).get("action") in ("REDUCE", "SELL")


def _compute() -> dict:
    from . import scanner, prices

    rows = [r for r in (scanner.load_latest() or {}).get("all_results") or [] if r.get("is_candidate")]
    cands = []
    for r in rows:
        pivot = _pivot(r)
        es = r.get("entry_setup") or {}
        st = (r.get("stage") or {}).get("stage")
        if not (pivot and es and st == 2):
            continue
        if _has_sell_signal(r):                       # climax / distribution — not a clean entry
            continue
        ee = r.get("entry_exit") or {}
        cur = ((ee.get("entry") or {}).get("current")) or r.get("last_close")
        if not cur:
            continue
        d = (cur / pivot - 1.0) * 100.0
        if d > ZONE_PCT or d < -NEAR_PCT:             # extended past the zone, or too far below
            continue
        cands.append({
            "symbol": r.get("symbol"), "name": r.get("name"),
            "pivot": round(pivot, 2), "last_close": round(cur, 2),
            "scan_dist_pct": round(d, 2),
            "rs_rank": r.get("rs_rank"), "score": r.get("score"),
            "setup_type": es.get("type"), "stop": es.get("stop"),
            "decision": ee.get("decision"),
            "vcp_tightness": (r.get("vcp") or {}).get("tightness"),
            "final_contraction_pct": (r.get("vcp") or {}).get("final_contraction_pct"),
        })

    # Live overlay — where is it RIGHT NOW vs the pivot (did it gap over overnight?)
    live = {}
    try:
        live = prices.bulk_live_prices([c["symbol"] for c in cands]) or {}
    except Exception as exc:
        log.warning("at_pivot live prices failed: %s", exc)
    for c in cands:
        L = live.get(c["symbol"]) or {}
        px = L.get("price") or L.get("last_trade_price")
        c["live_price"] = round(px, 2) if isinstance(px, (int, float)) and px else None
        ld = (px / c["pivot"] - 1.0) * 100.0 if c["live_price"] else c["scan_dist_pct"]
        c["dist_pct"] = round(ld, 2)
        if ld > ZONE_PCT:
            c["bucket"] = "gapped_over"               # already past the buy zone — missed
        elif ld >= AT_BAND_LOW:
            c["bucket"] = "at_pivot"                  # in the zone, catchable now
        else:
            c["bucket"] = "approaching"               # coiling under, set the alert/buy-stop

    order = {"at_pivot": 0, "approaching": 1, "gapped_over": 2}
    cands.sort(key=lambda c: (order.get(c["bucket"], 3), abs(c["dist_pct"])))

    counts = {"at_pivot": 0, "approaching": 0, "gapped_over": 0}
    for c in cands:
        counts[c["bucket"]] = counts.get(c["bucket"], 0) + 1

    return {
        "generated_at": int(time.time()),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rows": cands,
        "n": len(cands),
        "counts": counts,
        "config": {"zone_pct": ZONE_PCT, "near_pct": NEAR_PCT},
        "disclaimer": ("SEPA candidates at/approaching the pivot (Stage 2, not extended, "
                       "not climaxing). Buy AT the pivot, not chasing (Minervini p.203). "
                       "Educational, not advice."),
    }


def get_at_pivot(force: bool = False) -> dict:
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["at"]) < _TTL_SEC:
        return _CACHE["data"]
    data = _compute()
    _CACHE.update(at=now, data=data)
    return data
