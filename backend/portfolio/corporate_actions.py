"""Corporate actions sweep — keep portfolio shares + cost basis correct
across stock splits and (optionally) dividends.

Why this exists
---------------
After a 2-for-1 split on a portfolio holding, the user owns DOUBLE the
shares at HALF the per-share price. If we don't apply the split:

  - The Heatmap shows P&L of -50% on a position that didn't actually
    move (Plaid/Fidelity will eventually correct, but with a 24-48 hour
    lag depending on the source).
  - The alerts pipeline (alerts.py) fires a 50% drawdown push because
    live_price ≤ avg_cost × 0.5 — a false alarm that wakes you at 6am.
  - R-multiple math breaks (entry × ratio no longer equals current).

Source of truth
---------------
Massive's reference data, mirroring Polygon. The endpoints surface every
split + dividend execution with `ex_date`/`execution_date` so we can ask
"any corporate actions on this ticker since 2026-05-26?" and get an
authoritative answer.

  - GET /v3/reference/splits?ticker=<T>&execution_date.gte=<ISO>
  - GET /v3/reference/dividends?ticker=<T>&ex_dividend_date.gte=<ISO>

Apply semantics
---------------
**Splits**: idempotent rewrite of (shares, avg_cost). Total cost basis
is preserved exactly — only the per-share unit and share count change.
Forward split (2-for-1): shares × 2, avg_cost ÷ 2. Reverse split (1-for-10):
shares × 0.1, avg_cost × 10.

**Dividends**: NOT auto-adjusted (cash dividend is income, not a position
change). We record them in the audit log so the user can see total
dividend income per position, but `shares`/`cost_basis` stay untouched.

Audit + dedup
-------------
Every applied action gets a row in ``portfolio_corp_actions_applied``:
``{user_email, symbol, action_type, ex_date, applied_at, before, after}``.
The dedup check is on (user_email, symbol, action_type, ex_date) — the
same split is never re-applied even if the cron runs twice or this
function is invoked manually on the same day.
"""
from __future__ import annotations

import logging
import os
from massive_keys import stocks_key
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger("portfolio.corp_actions")


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def _get_db():
    from portfolio import store as _store
    return _store._get_db()


# --------------------------------------------------------------------------
# Massive client — splits + dividends
# --------------------------------------------------------------------------
def _massive_get(path: str, params: dict) -> dict:
    """Thin wrapper around requests.get with API key injection. Returns
    {} on any non-200 so callers can rely on a stable shape."""
    key = stocks_key()
    if not key:
        return {}
    try:
        import requests
    except ImportError:
        return {}
    try:
        r = requests.get(
            f"https://api.massive.com{path}",
            params={**params, "apiKey": key},
            timeout=15,
        )
        if r.status_code != 200:
            log.warning("massive %s -> HTTP %s", path, r.status_code)
            return {}
        return r.json() or {}
    except Exception as exc:
        log.warning("massive %s fetch failed: %s", path, exc)
        return {}


def fetch_splits(symbol: str, since_iso_date: str) -> list[dict]:
    """Fetch every stock split for ``symbol`` with execution_date ≥
    ``since_iso_date`` (format YYYY-MM-DD). Returns a list of dicts:

    .. code-block:: python

       [{
         "ticker": "AAPL",
         "execution_date": "2024-08-25",
         "split_from": 1.0,
         "split_to":   2.0,    # so 2-for-1 forward split
       }, ...]
    """
    data = _massive_get(
        "/v3/reference/splits",
        {
            "ticker":             symbol.upper(),
            "execution_date.gte": since_iso_date,
            "order":              "asc",
            "limit":              50,
        },
    )
    out: list[dict] = []
    for r in (data.get("results") or []):
        out.append({
            "ticker":         r.get("ticker"),
            "execution_date": r.get("execution_date"),
            "split_from":     float(r.get("split_from") or 1),
            "split_to":       float(r.get("split_to") or 1),
        })
    return out


def fetch_dividends(symbol: str, since_iso_date: str) -> list[dict]:
    """Fetch dividends with ex_dividend_date ≥ ``since_iso_date``."""
    data = _massive_get(
        "/v3/reference/dividends",
        {
            "ticker":               symbol.upper(),
            "ex_dividend_date.gte": since_iso_date,
            "order":                "asc",
            "limit":                50,
        },
    )
    out: list[dict] = []
    for r in (data.get("results") or []):
        out.append({
            "ticker":             r.get("ticker"),
            "ex_dividend_date":   r.get("ex_dividend_date"),
            "cash_amount":        float(r.get("cash_amount") or 0),
            "dividend_type":      r.get("dividend_type"),
            "frequency":          r.get("frequency"),
        })
    return out


# --------------------------------------------------------------------------
# Audit / dedup
# --------------------------------------------------------------------------
def _already_applied(user_email: str, symbol: str, action_type: str, ex_date: str) -> bool:
    db = _get_db()
    if db is None:
        return False
    return db.portfolio_corp_actions_applied.find_one({
        "user_email":  user_email.lower(),
        "symbol":      symbol.upper(),
        "action_type": action_type,
        "ex_date":     ex_date,
    }) is not None


def _record_action(*, user_email: str, symbol: str, action_type: str, ex_date: str,
                   before: dict, after: dict, details: dict) -> None:
    db = _get_db()
    if db is None:
        return
    db.portfolio_corp_actions_applied.update_one(
        {
            "user_email":  user_email.lower(),
            "symbol":      symbol.upper(),
            "action_type": action_type,
            "ex_date":     ex_date,
        },
        {"$set": {
            "user_email":  user_email.lower(),
            "symbol":      symbol.upper(),
            "action_type": action_type,
            "ex_date":     ex_date,
            "before":      before,
            "after":       after,
            "details":     details,
            "applied_at":  _now(),
        }},
        upsert=True,
    )


# --------------------------------------------------------------------------
# Apply a split to ALL holdings of a symbol for one user
# --------------------------------------------------------------------------
def _apply_split_to_holdings(user_email: str, symbol: str, split: dict) -> list[dict]:
    """Mutate every (user, symbol, account) holding row for the split.
    Returns the list of {before, after, account} dicts so we can record
    them in the audit collection.

    Per-share math:
      ratio = split_to / split_from
      new_shares    = old_shares × ratio
      new_avg_cost  = old_avg_cost ÷ ratio
      cost_basis    = unchanged (preserved exactly across the action)
    """
    db = _get_db()
    if db is None:
        return []
    from_n = split["split_from"]
    to_n = split["split_to"]
    if from_n <= 0 or to_n <= 0:
        return []
    ratio = to_n / from_n

    changes: list[dict] = []
    cursor = db.portfolio_holdings.find({
        "user_email": user_email.lower(),
        "ticker":     symbol.upper(),
    })
    for h in cursor:
        old_shares = float(h.get("shares") or 0)
        old_cost   = float(h.get("cost_basis") or 0)
        if old_shares <= 0:
            continue
        new_shares = round(old_shares * ratio, 6)
        # cost_basis is total $ in — stays the same across a split.
        new_cost   = old_cost
        new_avg    = (new_cost / new_shares) if new_shares > 0 else None

        db.portfolio_holdings.update_one(
            {"_id": h["_id"]},
            {"$set": {
                "shares":     new_shares,
                "cost_basis": new_cost,
                "updated_at": _now(),
            }},
        )
        changes.append({
            "account":    h.get("account"),
            "before":     {"shares": old_shares, "cost_basis": old_cost,
                           "avg_cost": (old_cost / old_shares) if old_shares > 0 else None},
            "after":      {"shares": new_shares, "cost_basis": new_cost, "avg_cost": new_avg},
        })
    return changes


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------
def sweep_user(user_email: str, *, lookback_days: int = 30) -> dict:
    """Scan all of one user's holdings for unapplied corporate actions.

    For each held symbol:
      1. Fetch splits since `now - lookback_days`
      2. For each split not already applied → apply + record
      3. Fetch dividends since same window
      4. For each dividend not already recorded → record (no adjustment)

    Returns a summary dict for cron logging.
    """
    if not user_email:
        return {"ok": False, "reason": "no user_email"}

    from portfolio import store as _store
    holdings = _store.list_holdings(user_email)
    if not holdings:
        return {"ok": True, "symbols": 0, "splits_applied": 0, "dividends_recorded": 0}

    # Dedup symbols (same ticker can sit in multiple accounts).
    symbols = sorted({(h.get("ticker") or "").upper() for h in holdings if h.get("ticker")})
    since = (datetime.now(tz=timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    splits_applied = 0
    dividends_recorded = 0
    details: list[dict] = []

    for sym in symbols:
        # ---- Splits ----
        for split in fetch_splits(sym, since):
            ex_date = split.get("execution_date") or ""
            if not ex_date:
                continue
            if _already_applied(user_email, sym, "split", ex_date):
                continue
            changes = _apply_split_to_holdings(user_email, sym, split)
            if not changes:
                continue
            _record_action(
                user_email=user_email,
                symbol=sym,
                action_type="split",
                ex_date=ex_date,
                before={"changes_count": len(changes)},
                after={"split_ratio": f"{split['split_to']:g}-for-{split['split_from']:g}"},
                details={"split": split, "per_account": changes},
            )
            splits_applied += 1
            details.append({
                "type":   "split",
                "symbol": sym,
                "ratio":  f"{split['split_to']:g}-for-{split['split_from']:g}",
                "ex_date": ex_date,
                "accounts_touched": len(changes),
            })
            log.info(
                "corp_actions: applied %s split on %s (ex %s) — %d account row(s)",
                f"{split['split_to']:g}-for-{split['split_from']:g}",
                sym, ex_date, len(changes),
            )

        # ---- Dividends (record only, no balance adjustment) ----
        for div in fetch_dividends(sym, since):
            ex_date = div.get("ex_dividend_date") or ""
            if not ex_date:
                continue
            if _already_applied(user_email, sym, "dividend", ex_date):
                continue
            # Compute approx total cash received: shares_on_ex × cash_amount.
            # Shares are taken AFTER any earlier split apply (same loop),
            # which matches reality since the holder of record is set by
            # the ex_date. We pull current shares as a proxy.
            current_shares = sum(
                float(h.get("shares") or 0)
                for h in _store.list_holdings(user_email)
                if (h.get("ticker") or "").upper() == sym
            )
            cash_received = round(current_shares * float(div.get("cash_amount") or 0), 2)
            _record_action(
                user_email=user_email,
                symbol=sym,
                action_type="dividend",
                ex_date=ex_date,
                before={"shares_on_ex": current_shares},
                after={"cash_received": cash_received},
                details={"dividend": div},
            )
            dividends_recorded += 1
            details.append({
                "type":          "dividend",
                "symbol":        sym,
                "ex_date":       ex_date,
                "per_share":     div.get("cash_amount"),
                "cash_received": cash_received,
            })
            log.info(
                "corp_actions: recorded dividend %s on %s (ex %s) — ~$%.2f received",
                div.get("cash_amount"), sym, ex_date, cash_received,
            )

    return {
        "ok":                 True,
        "user_email":         user_email,
        "symbols_checked":    len(symbols),
        "splits_applied":     splits_applied,
        "dividends_recorded": dividends_recorded,
        "details":            details,
        "lookback_days":      lookback_days,
    }


def recent_actions(user_email: str, *, limit: int = 25) -> list[dict]:
    """Return the most recent corp_actions applied for this user. Used
    by the /portfolio/corporate-actions/recent route + audit views."""
    db = _get_db()
    if db is None:
        return []
    rows = list(
        db.portfolio_corp_actions_applied
          .find({"user_email": user_email.lower()}, {"_id": 0})
          .sort("applied_at", -1)
          .limit(limit)
    )
    return rows


# --------------------------------------------------------------------------
# Cron entry point — sweep the deployment owner's holdings
# --------------------------------------------------------------------------
def run_default() -> dict:
    owner = (
        os.getenv("PORTFOLIO_ALERT_OWNER")
        or os.getenv("HOUSE_OWNER_EMAIL")
        or "ajaykandakatla@gmail.com"
    ).lower()
    return sweep_user(owner)
