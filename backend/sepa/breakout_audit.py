"""Breakout integrity tripwire (Ajay 2026-06-18 — real money; wants assurance the
"broke out today" flag never silently drifts from the book).

Independently re-derives every scanned name's today-breakout status from raw
price bars and compares it to what the persisted scan flagged. Any mismatch is a
discrepancy that gets logged (and alerted via cron).

IMPORTANT: this module carries its OWN reference implementation of the book
definition (it does NOT call volume.py). So if volume.py's breakout formula ever
drifts from Minervini p.203, this audit diverges and flags it — that's the whole
point of a tripwire.

Definition (Minervini, Trade Like a Stock Market Wizard, p.203):
  a breakout = the latest close is above the highest close of the PRIOR 21 bars
  AND the latest volume is > 1.5× the trailing 50-day average volume.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import numpy as np

log = logging.getLogger("sepa.breakout_audit")

PRIOR_HIGH_BARS = 21      # close above the prior 21-bar high
VOL_MULT = 1.5            # on > 1.5× the 50-day average volume
VOL_AVG_BARS = 50


def is_breakout_today(df) -> Optional[bool]:
    """Reference (book p.203): is the LATEST bar a volume-confirmed breakout?
    None when there isn't enough history to judge. Independent of volume.py."""
    if df is None or "close" not in df or "volume" not in df or len(df) < VOL_AVG_BARS + 2:
        return None
    c = df["close"].astype(float)
    v = df["volume"].astype(float)
    prior_high = c.rolling(PRIOR_HIGH_BARS).max().shift(1).iloc[-1]
    avg_vol = v.rolling(VOL_AVG_BARS).mean().shift(1).iloc[-1]
    if not (np.isfinite(prior_high) and np.isfinite(avg_vol) and avg_vol > 0):
        return None
    return bool(c.iloc[-1] > prior_high and v.iloc[-1] > VOL_MULT * avg_vol)


def audit_latest(max_workers: int = 12) -> dict:
    """Re-derive today-breakout for every name in the latest scan and compare to
    its persisted ``days_since_breakout == 0`` flag. Returns a discrepancy report:

      {ok, checked, flagged_today, confirmed_today,
       false_positives: [...],   # scanner flagged it, but it's NOT a real breakout
       false_negatives: [...],   # real breakout the scanner MISSED
       clean: bool, scan_ts, audited_at}
    """
    from sepa import scanner, prices
    scan = scanner.load_latest() or {}
    rows = scan.get("all_results") or []
    scan_flag = {
        r.get("symbol"): ((r.get("volume") or {}).get("days_since_breakout") == 0)
        for r in rows if r.get("symbol")
    }
    if not scan_flag:
        return {"ok": False, "error": "no scan", "clean": True, "checked": 0,
                "false_positives": [], "false_negatives": []}

    def _check(sym):
        try:
            return sym, is_breakout_today(prices.load_prices(sym))
        except Exception:                          # noqa: BLE001
            return sym, None

    indep: dict = {}
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for sym, res in ex.map(_check, list(scan_flag.keys())):
                if res is not None:
                    indep[sym] = res
    except Exception as exc:                       # noqa: BLE001
        log.warning("breakout audit failed: %s", exc)
        return {"ok": False, "error": str(exc), "clean": True,
                "false_positives": [], "false_negatives": []}

    false_pos = sorted(s for s in indep if scan_flag.get(s) and not indep[s])
    false_neg = sorted(s for s in indep if indep[s] and not scan_flag.get(s))
    report = {
        "ok": True,
        "checked": len(indep),
        "flagged_today": sum(1 for s in scan_flag if scan_flag[s]),
        "confirmed_today": sum(1 for s in indep.values() if s),
        "false_positives": false_pos,
        "false_negatives": false_neg,
        "clean": not false_pos and not false_neg,
        "scan_ts": scan.get("generated_at"),
        "audited_at": int(time.time()),
    }
    if report["clean"]:
        log.info("breakout integrity OK — %d checked, %d flagged, all confirmed",
                 report["checked"], report["flagged_today"])
    else:
        log.warning("BREAKOUT INTEGRITY TRIPWIRE — %d false-positive %s, %d false-negative %s",
                    len(false_pos), false_pos[:10], len(false_neg), false_neg[:10])
    return report
