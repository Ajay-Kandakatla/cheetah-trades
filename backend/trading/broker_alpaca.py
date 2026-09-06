"""Thin Alpaca REST client for the Auto-Pilot trading engine.

Plain `requests` (no alpaca SDK — keep the container dependency-free), 15s
timeouts, whole-share quantities only. Trading endpoints hit
paper-api.alpaca.markets unless ALPACA_PAPER=0; market data (latest trade
fallback) always hits data.alpaca.markets.

SAFETY: every exception path goes through _scrub() so the ALPACA_KEY_ID /
ALPACA_SECRET_KEY values can never reach the logs — mirrors the _scrub_key
redaction pattern in sepa/prices.py (a provider key leaked via an exception
once, 2026-06-11; never again).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests

log = logging.getLogger("trading.broker")

_TIMEOUT = 15
_DATA_URL = "https://data.alpaca.markets"

# Order statuses that mean "this order is still working / can still fill".
OPEN_STATUSES = {
    "new", "held", "accepted", "partially_filled", "pending_new",
    "pending_replace", "accepted_for_bidding", "calculated",
}


class BrokerError(RuntimeError):
    """Any Alpaca API failure. The message is always credential-scrubbed."""


def _scrub(exc) -> str:
    """Exception/response text with the Alpaca credentials redacted —
    mirrors sepa/prices.py _scrub_key. Alpaca keys travel in headers (not
    URLs), but reprs and error bodies can still echo them, so we replace
    the literal env values wherever they appear."""
    text = str(exc)
    for env in ("ALPACA_KEY_ID", "ALPACA_SECRET_KEY"):
        val = os.getenv(env) or ""
        if val and val in text:
            text = text.replace(val, "<redacted>")
    return text


def configured() -> bool:
    return bool(os.getenv("ALPACA_KEY_ID") and os.getenv("ALPACA_SECRET_KEY"))


def base_url() -> str:
    """ALPACA_PAPER default "1" -> paper; only an explicit "0" -> live."""
    if (os.getenv("ALPACA_PAPER", "1") or "1").strip() == "0":
        return "https://api.alpaca.markets"
    return "https://paper-api.alpaca.markets"


def mode() -> str:
    """"paper" | "live" — follows base_url()'s ALPACA_PAPER reading."""
    return "live" if base_url() == "https://api.alpaca.markets" else "paper"


_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({
            "APCA-API-KEY-ID": os.getenv("ALPACA_KEY_ID") or "",
            "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY") or "",
            "Accept": "application/json",
        })
        _session = s
    return _session


def _request(method: str, path: str, params=None, json_body=None, base=None):
    url = (base or base_url()) + path
    try:
        resp = _get_session().request(method, url, params=params,
                                      json=json_body, timeout=_TIMEOUT)
    except Exception as exc:                       # noqa: BLE001 — scrub all
        msg = "alpaca %s %s failed: %s" % (method, path, _scrub(exc))
        log.warning(msg)
        raise BrokerError(msg)
    if resp.status_code >= 400:
        msg = "alpaca %s %s -> HTTP %d: %s" % (
            method, path, resp.status_code, _scrub(resp.text[:500]))
        log.warning(msg)
        raise BrokerError(msg)
    if resp.status_code == 204 or not (resp.text or "").strip():
        return None
    try:
        return resp.json()
    except Exception as exc:                       # noqa: BLE001
        raise BrokerError("alpaca %s %s: bad JSON: %s" % (method, path, _scrub(exc)))


# ── Read endpoints ─────────────────────────────────────────────────────────

def account() -> dict:
    return _request("GET", "/v2/account") or {}


def clock() -> dict:
    """{is_open, next_open, next_close, timestamp}"""
    return _request("GET", "/v2/clock") or {}


def positions() -> list:
    return _request("GET", "/v2/positions") or []


def open_orders(symbol: Optional[str] = None) -> list:
    """Open orders, nested=true so unfilled-parent bracket legs ride along
    in each parent's `legs` array (active legs of a FILLED parent appear as
    top-level open orders on their own)."""
    params = {"status": "open", "nested": "true", "limit": 500}
    if symbol:
        params["symbols"] = symbol.upper()
    return _request("GET", "/v2/orders", params=params) or []


def closed_orders_since(iso_ts: str) -> list:
    """Closed (terminal) orders submitted after iso_ts, oldest first.
    Bracket legs appear as individual rows here once they reach a terminal
    state, so the exit engine's streak bookkeeping sees fills directly."""
    params = {"status": "closed", "after": iso_ts,
              "direction": "asc", "limit": 500}
    return _request("GET", "/v2/orders", params=params) or []


def latest_trade(symbol: str) -> Optional[float]:
    """Last trade price from the Alpaca data API — the entries fallback when
    sepa.prices has nothing for the symbol. None when unavailable."""
    try:
        doc = _request("GET", "/v2/stocks/%s/trades/latest" % symbol.upper(),
                       base=_DATA_URL) or {}
        px = (doc.get("trade") or {}).get("p")
        return float(px) if px else None
    except BrokerError as exc:
        log.warning("latest_trade %s unavailable: %s", symbol, exc)
        return None


# ── Order endpoints ────────────────────────────────────────────────────────

def make_client_order_id(symbol: str, intent: str) -> str:
    """Deterministic id: cheetah-{SYM}-{yyyymmdd ET}-{intent}. Alpaca rejects
    duplicate client_order_ids, which doubles as same-day idempotency."""
    try:
        from zoneinfo import ZoneInfo
        day = datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d")
    except Exception:                              # noqa: BLE001
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return "cheetah-%s-%s-%s" % (symbol.upper(), day, intent)


def _whole_qty(qty) -> int:
    q = int(qty)
    if q <= 0 or q != float(qty):
        raise BrokerError("qty must be a positive whole number (got %r)" % (qty,))
    return q


def submit_bracket(symbol: str, qty: int, take_profit_price: float,
                   stop_price: float, limit_price: Optional[float] = None,
                   client_order_id: Optional[str] = None, tif: str = "gtc",
                   order_class: str = "bracket") -> dict:
    """Buy bracket: entry + take-profit limit + stop-loss legs resting AT
    Alpaca (never only in our process). limit_price=None -> market order,
    allowed only while the market clock says open."""
    q = _whole_qty(qty)
    if limit_price is None:
        try:
            is_open = bool(clock().get("is_open"))
        except BrokerError:
            is_open = False
        if not is_open:
            raise BrokerError("market order rejected: market is closed — "
                              "use a limit_price (GTC) instead")
    body = {
        "symbol": symbol.upper(),
        "qty": str(q),
        "side": "buy",
        "type": "limit" if limit_price is not None else "market",
        "time_in_force": tif,
        "order_class": order_class,
        "take_profit": {"limit_price": str(round(float(take_profit_price), 2))},
        "stop_loss": {"stop_price": str(round(float(stop_price), 2))},
    }
    if limit_price is not None:
        body["limit_price"] = str(round(float(limit_price), 2))
    if client_order_id:
        body["client_order_id"] = client_order_id
    return _request("POST", "/v2/orders", json_body=body) or {}


def submit_stop(symbol: str, qty: int, stop_price: float,
                client_order_id: Optional[str] = None) -> dict:
    """Standalone GTC sell-stop — the adopt-and-protect order for positions
    that arrived without a protective stop."""
    body = {
        "symbol": symbol.upper(),
        "qty": str(_whole_qty(qty)),
        "side": "sell",
        "type": "stop",
        "time_in_force": "gtc",
        "stop_price": str(round(float(stop_price), 2)),
    }
    if client_order_id:
        body["client_order_id"] = client_order_id
    return _request("POST", "/v2/orders", json_body=body) or {}


def replace_order(order_id: str, stop_price: Optional[float] = None,
                  limit_price: Optional[float] = None) -> dict:
    body = {}
    if stop_price is not None:
        body["stop_price"] = str(round(float(stop_price), 2))
    if limit_price is not None:
        body["limit_price"] = str(round(float(limit_price), 2))
    if not body:
        raise BrokerError("replace_order: nothing to change")
    return _request("PATCH", "/v2/orders/%s" % order_id, json_body=body) or {}


# ── Options (paper options lane, 2026-09-06) ───────────────────────────────
# The paper account is options level 3 (verified 2026-09-06: options_approved
# _level 3, options_buying_power ~$79.7k). Contracts come from the trading
# API, quotes/greeks/IV from the data API "indicative" feed. Every helper
# returns Alpaca-shaped dicts; the lane (trading/options_lane.py) owns the
# rules. broker_sim has none of these — the lane gates itself off on a
# broker without them.

def option_contracts(underlying: str, expiration_gte: str, expiration_lte: str,
                     otype: str = "call", strike_gte=None, strike_lte=None,
                     limit: int = 1000) -> list:
    """Tradable option contracts for one underlying inside an expiry window.
    Rows carry symbol (OCC), expiration_date, strike_price, open_interest,
    close_price, tradable, status."""
    params = {"underlying_symbols": underlying.upper(),
              "expiration_date_gte": expiration_gte,
              "expiration_date_lte": expiration_lte,
              "type": otype, "status": "active", "limit": str(int(limit))}
    if strike_gte is not None:
        params["strike_price_gte"] = str(strike_gte)
    if strike_lte is not None:
        params["strike_price_lte"] = str(strike_lte)
    out, token = [], None
    for _ in range(10):                            # pagination guard
        if token:
            params["page_token"] = token
        doc = _request("GET", "/v2/options/contracts", params=params) or {}
        rows = doc.get("option_contracts") if isinstance(doc, dict) else doc
        out.extend(r for r in (rows or []) if isinstance(r, dict))
        token = doc.get("next_page_token") if isinstance(doc, dict) else None
        if not token:
            break
    return out


def option_snapshots(underlying: str, expiration_gte: str, expiration_lte: str,
                     otype: str = "call", strike_gte=None, strike_lte=None,
                     feed: str = "indicative") -> dict:
    """{OCC symbol: {"bid", "ask", "iv", "delta", "last"}} from the options
    snapshot endpoint (data API). Missing quotes/greeks come back as None."""
    params = {"feed": feed, "type": otype, "limit": "1000",
              "expiration_date_gte": expiration_gte,
              "expiration_date_lte": expiration_lte}
    if strike_gte is not None:
        params["strike_price_gte"] = str(strike_gte)
    if strike_lte is not None:
        params["strike_price_lte"] = str(strike_lte)
    out, token = {}, None
    for _ in range(10):
        if token:
            params["page_token"] = token
        doc = _request("GET", "/v1beta1/options/snapshots/%s" % underlying.upper(),
                       params=params, base=_DATA_URL) or {}
        snaps = doc.get("snapshots") or {}
        for sym, v in snaps.items():
            if not isinstance(v, dict):
                continue
            q = v.get("latestQuote") or {}
            g = v.get("greeks") or {}
            t = v.get("latestTrade") or {}
            out[sym] = {"bid": _fnum(q.get("bp")), "ask": _fnum(q.get("ap")),
                        "iv": _fnum(v.get("impliedVolatility")),
                        "delta": _fnum(g.get("delta")), "last": _fnum(t.get("p"))}
        token = doc.get("next_page_token")
        if not token:
            break
    return out


def _fnum(x):
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def submit_option_order(symbol: str, qty: int, side: str, limit_price: float,
                        position_intent: Optional[str] = None,
                        client_order_id: Optional[str] = None,
                        tif: str = "day") -> dict:
    """Single-leg option LIMIT order (buy_to_open / sell_to_close ...)."""
    body = {"symbol": symbol, "qty": str(int(qty)), "side": side,
            "type": "limit", "time_in_force": tif,
            "limit_price": str(round(float(limit_price), 2))}
    if position_intent:
        body["position_intent"] = position_intent
    if client_order_id:
        body["client_order_id"] = client_order_id
    return _request("POST", "/v2/orders", json_body=body) or {}


def submit_option_spread(legs: list, qty: int, limit_price: float,
                         client_order_id: Optional[str] = None,
                         tif: str = "day") -> dict:
    """Multi-leg (mleg) LIMIT order. `legs` = [{symbol, side, position_intent,
    ratio_qty}]; `limit_price` is the NET price of the package: positive =
    debit, NEGATIVE = credit (Alpaca POST /v2/orders: "A positive value
    indicates a debit ... A negative value signifies a credit")."""
    body = {"order_class": "mleg", "qty": str(int(qty)), "type": "limit",
            "time_in_force": tif,
            "limit_price": str(round(float(limit_price), 2)),
            "legs": [{"symbol": l["symbol"], "ratio_qty": str(int(l.get("ratio_qty") or 1)),
                      "side": l["side"], "position_intent": l["position_intent"]}
                     for l in legs]}
    if client_order_id:
        body["client_order_id"] = client_order_id
    return _request("POST", "/v2/orders", json_body=body) or {}


def option_positions() -> list:
    """Open positions whose asset_class is us_option."""
    return [p for p in positions() if (p.get("asset_class") or "") == "us_option"]


def cancel_order(order_id: str) -> None:
    _request("DELETE", "/v2/orders/%s" % order_id)


def close_position(symbol: str) -> dict:
    return _request("DELETE", "/v2/positions/%s" % symbol.upper()) or {}
