"""Progressive-exposure governor — pilot-size entries until recent trades
prove out (Ajay sign-off 2026-07-12).

Book anchor — TLSW pp.307-308, verbatim:

    "You should start off with 'pilot buys' by initiating smaller positions
    than normal; if they work out, larger positions should be added to the
    portfolio soon thereafter. This toe-in-the-water approach helps keep you
    out of trouble and building on your successes. If you're not profitable
    at 25 percent or 50 percent invested, why move up to 75 percent or 100
    percent invested or use margin? Wait for confirmation and require that
    at least a few trades work out before getting more aggressive.
    Conversely, if your trades are not working as expected, cut back."

Recent primary-source restatements (Mark Minervini on X — his words, found
in the 2026-07-12 research sweep; NOT book pages):

  * standing rule: "are your last 4 or 5 stocks profitable on balance. If
    no, then you have no business increasing your exposure."
    https://x.com/markminervini/status/1331694910899179524
  * 2025-01 dated ledger demonstrating pilot -> quarter/half -> full-size
    builds across two weeks, going full only after the first week's buys
    worked. https://x.com/markminervini/status/1884705597402059074

Mechanization (the numbers are OWNER choices; the book gives the concept,
not a window or a fraction):

  * Every entry sizes at PILOT_MULTIPLIER (0.5x) by default.
  * Full size (1.0x) only when the last PROGRESSIVE_WINDOW closed trades
    are profitable ON BALANCE (net gain_pct > 0).
  * Fewer than PROGRESSIVE_MIN_TRADES closed trades = unproven = pilot
    ("earned the right to get aggressive").
  * Composes with the p.304 streak governor via min() inside
    risk_rules.position_size — the most conservative governor wins; the
    two never multiply into an unowned number.
  * `progressive_exposure` trading-config key (default ON when absent)
    disables it live — data write or POST /trading/config, no deploy.

Closed trades are read from trade_ledger `trade_closed` rows (non-dry),
newest first. A multi-leg exit counts each leg — documented approximation
of "last 4 or 5 stocks"; engine exits are single-leg in practice.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("trading.progressive")

# "last 4 or 5 stocks profitable on balance" — the 5-trade reading.
PROGRESSIVE_WINDOW = 5
# Below this many closed trades the account is unproven -> pilot size.
PROGRESSIVE_MIN_TRADES = 3
# "pilot buys ... smaller positions than normal" — the book gives no
# fraction; Minervini's X ledger shows quarter and half pilots. 0.5 chosen
# so a $5k-cap paper account still clears 1 share on most candidates.
PILOT_MULTIPLIER = 0.5


def enabled(cfg: Optional[dict] = None) -> bool:
    """Default ON; only an explicit stored False turns it off."""
    v = (cfg or {}).get("progressive_exposure")
    return True if v is None else bool(v)


def on_balance_multiplier(gains: Optional[list]) -> tuple:
    """The pure rule. `gains` = closed-trade gain_pct floats, NEWEST FIRST
    (only the first PROGRESSIVE_WINDOW are read). Returns (mult, detail).

    unproven (n < PROGRESSIVE_MIN_TRADES)      -> PILOT_MULTIPLIER
    net of last window <= 0 ("not on balance") -> PILOT_MULTIPLIER
    net > 0                                    -> 1.0 (full size)
    """
    clean = []
    for g in (gains or [])[:PROGRESSIVE_WINDOW]:
        try:
            v = float(g)
        except (TypeError, ValueError):
            continue
        if v == v:                       # NaN guard
            clean.append(v)
    detail = {"window": PROGRESSIVE_WINDOW, "gains": clean,
              "n": len(clean), "pilot": PILOT_MULTIPLIER}
    if len(clean) < PROGRESSIVE_MIN_TRADES:
        detail["basis"] = "unproven"
        detail["net_pct"] = round(sum(clean), 2) if clean else None
        return PILOT_MULTIPLIER, detail
    net = round(sum(clean), 2)
    detail["net_pct"] = net
    if net <= 0:
        detail["basis"] = "last_%d_negative_on_balance" % len(clean)
        return PILOT_MULTIPLIER, detail
    detail["basis"] = "last_%d_positive_on_balance" % len(clean)
    return 1.0, detail


def last_gains(db, window: int = PROGRESSIVE_WINDOW) -> list:
    """gain_pct of the newest `window` non-dry trade_closed ledger rows,
    newest first. Python re-sort on epoch so fakes without a working
    cursor-sort still order correctly. Unreadable ledger -> [] (which the
    pure rule reads as unproven -> pilot — fail conservative)."""
    if db is None:
        return []
    try:
        rows = list(db.trade_ledger
                    .find({"kind": "trade_closed", "dry_run": {"$ne": True}})
                    .sort("epoch", -1).limit(window * 3))
    except Exception as exc:                       # noqa: BLE001
        log.debug("progressive: ledger unavailable: %s", exc)
        return []
    rows.sort(key=lambda r: r.get("epoch") or 0, reverse=True)
    out = []
    for r in rows:
        g = (r.get("detail") or {}).get("gain_pct")
        if g is not None:
            out.append(g)
        if len(out) >= window:
            break
    return out


def multiplier(db, cfg: Optional[dict] = None) -> tuple:
    """(size multiplier, detail) for the current ledger + config."""
    if not enabled(cfg):
        return 1.0, {"enabled": False}
    mult, detail = on_balance_multiplier(last_gains(db))
    detail["enabled"] = True
    return mult, detail
