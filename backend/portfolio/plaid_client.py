"""Plaid Investments client — link-token / public-token exchange / holdings.

Why this module exists
----------------------
The original ``portfolio`` package only knew about user-typed holdings
(symbol + shares + cost basis entered by hand). For real workflows the
user wants positions auto-imported from their broker. Plaid's Investments
product gives us a hosted login UI (the user types their Fidelity
credentials INTO Plaid — never into us) and a stable access token that
lets us pull /investments/holdings/get on a schedule.

Lazy-disable pattern
--------------------
Mirrors ``short_interest.client``: if PLAID_CLIENT_ID is unset the
module reports ``is_configured() == False`` and every public call
raises ``PlaidNotConfigured``. The /portfolio/status route catches that
and tells the frontend to render the "Setup Plaid first" CTA — the app
keeps booting even with no Plaid keys.

Environment
-----------
- ``PLAID_CLIENT_ID``  — required for any Plaid call
- ``PLAID_SECRET``     — required, paired with the env below
- ``PLAID_ENV``        — sandbox | development | production. Default
  ``development`` (Plaid's recommended starting tier for real broker
  data with a small initial user cap).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger("portfolio.plaid_client")


class PlaidNotConfigured(RuntimeError):
    """Raised by every public call when PLAID_CLIENT_ID is missing.

    Callers (the FastAPI router in api.py) catch this and surface a 503
    with a setup-instructions message rather than a stack trace. We
    don't fall back to a no-op because silent fallbacks make the
    Plaid-disabled state indistinguishable from a real broker outage.
    """


# Process-level handle so we don't rebuild the SDK client on every call.
_api_client: Optional[object] = None
_disabled_logged = False


def _plaid_env_url(env_name: str) -> str:
    """Map ``sandbox`` / ``development`` / ``production`` to the matching
    Plaid REST host. Plaid removed the SDK's `Environment` enum in v23+,
    so we resolve to the URL directly to stay forward-compatible."""
    env_name = (env_name or "").strip().lower()
    if env_name == "sandbox":
        return "https://sandbox.plaid.com"
    if env_name == "production":
        return "https://production.plaid.com"
    # Default to `development` — same tier the user is signing up for.
    return "https://development.plaid.com"


def is_configured() -> bool:
    """True iff PLAID_CLIENT_ID and PLAID_SECRET are both populated.

    Cheap env check — does NOT actually hit Plaid. Used by the /status
    route to decide between "setup Plaid" vs. "connect Fidelity" UI
    states without making a network call.
    """
    return bool(os.getenv("PLAID_CLIENT_ID") and os.getenv("PLAID_SECRET"))


def _get_client():
    """Build (or return cached) Plaid API client. Imports the SDK lazily
    so the module can be imported in environments where plaid-python
    isn't installed (e.g. unit-test runs that mock the API)."""
    global _api_client, _disabled_logged
    if not is_configured():
        if not _disabled_logged:
            log.warning("portfolio.plaid_client: PLAID_CLIENT_ID not set — plaid features disabled")
            _disabled_logged = True
        raise PlaidNotConfigured("PLAID_CLIENT_ID and PLAID_SECRET must both be set")

    if _api_client is not None:
        return _api_client

    try:
        # Imported here so the rest of the module still imports cleanly
        # if plaid-python hasn't been installed yet (e.g. fresh container
        # before `pip install` has run).
        from plaid.api import plaid_api
        from plaid.configuration import Configuration
        from plaid.api_client import ApiClient
    except ImportError as exc:  # pragma: no cover - depends on requirements install
        raise PlaidNotConfigured(f"plaid-python not installed: {exc}")

    env_name = os.getenv("PLAID_ENV", "development")
    config = Configuration(
        host=_plaid_env_url(env_name),
        api_key={
            "clientId": os.getenv("PLAID_CLIENT_ID", ""),
            "secret":   os.getenv("PLAID_SECRET", ""),
        },
    )
    _api_client = plaid_api.PlaidApi(ApiClient(config))
    return _api_client


def create_link_token(user_id: str) -> dict:
    """Mint a one-shot Link token the frontend hands to Plaid Link.

    Plaid Link is the hosted UI the user sees when they click "Connect
    Fidelity". The token tells Plaid:
      - who the user is (our internal id — opaque to Plaid)
      - which products we want (Investments — required for /holdings/get)
      - which country (US — Fidelity is US-only)

    Returns
    -------
    ``{"link_token": "...", "expiration": "ISO-8601"}``

    Raises
    ------
    PlaidNotConfigured — env vars missing.
    """
    client = _get_client()
    from plaid.model.link_token_create_request import LinkTokenCreateRequest
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
    from plaid.model.products import Products
    from plaid.model.country_code import CountryCode

    req = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
        client_name="Pounce",
        products=[Products("investments")],
        country_codes=[CountryCode("US")],
        language="en",
    )
    resp = client.link_token_create(req)
    return {
        "link_token": resp.link_token,
        "expiration": resp.expiration.isoformat() if getattr(resp, "expiration", None) else None,
    }


def exchange_public_token(public_token: str) -> dict:
    """Trade a short-lived ``public_token`` (from Link onSuccess) for the
    long-lived ``access_token`` we'll store and use for all subsequent
    holdings reads.

    Returns
    -------
    ``{"access_token": "...", "item_id": "..."}``
    """
    client = _get_client()
    from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

    resp = client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=public_token)
    )
    return {
        "access_token": resp.access_token,
        "item_id":      resp.item_id,
    }


def get_item(access_token: str) -> dict:
    """Fetch institution metadata for a linked item — used at exchange
    time so we can persist the bank name ("Fidelity") alongside the
    access token for the UI."""
    client = _get_client()
    from plaid.model.item_get_request import ItemGetRequest

    resp = client.item_get(ItemGetRequest(access_token=access_token))
    institution_id = getattr(resp.item, "institution_id", None) or ""
    institution_name = ""
    if institution_id:
        try:
            from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
            from plaid.model.country_code import CountryCode

            inst_resp = client.institutions_get_by_id(
                InstitutionsGetByIdRequest(
                    institution_id=institution_id,
                    country_codes=[CountryCode("US")],
                )
            )
            institution_name = inst_resp.institution.name or ""
        except Exception as exc:
            log.warning("portfolio.plaid_client: institution lookup failed: %s", exc)
    return {
        "item_id":          getattr(resp.item, "item_id", ""),
        "institution_id":   institution_id,
        "institution_name": institution_name,
    }


def _serialize(obj) -> object:
    """Best-effort conversion of plaid-python model objects to plain
    dicts/lists/scalars suitable for JSON. The SDK's models expose
    ``to_dict()`` but nested values may still contain Date/Decimal types
    — we coerce those to ISO strings / floats."""
    import datetime as _dt
    import decimal as _dec

    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, _dec.Decimal):
        return float(obj)
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    if isinstance(obj, tuple):
        return [_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if hasattr(obj, "to_dict"):
        return _serialize(obj.to_dict())
    # Last-resort string fallback for unknown types.
    return str(obj)


def get_holdings(access_token: str) -> dict:
    """Pull the current holdings snapshot from Plaid.

    Wraps /investments/holdings/get and serializes the response to plain
    JSON-friendly types so the rest of the backend doesn't have to know
    about plaid-python model classes.

    Returns
    -------
    ``{"accounts": [...], "holdings": [...], "securities": [...], "item": {...}}``
    """
    client = _get_client()
    from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest

    resp = client.investments_holdings_get(
        InvestmentsHoldingsGetRequest(access_token=access_token)
    )
    result = {
        "accounts":   _serialize(resp.accounts),
        "holdings":   _serialize(resp.holdings),
        "securities": _serialize(resp.securities),
        "item":       _serialize(resp.item),
    }

    # Diagnostic logging — track WHY Fidelity-Plaid sometimes returns
    # account balances without per-position holdings (e.g. TOD brokerage
    # missing positions). Logs counts + per-account breakdown + Plaid's
    # item.error field (if any). No secrets here: access_token is never
    # in the response, account IDs are Plaid-internal opaque strings.
    # Remove this block once the missing-holdings root cause is known.
    accounts = result["accounts"] or []
    holdings = result["holdings"] or []
    securities = result["securities"] or []
    item = result["item"] or {}

    holdings_per_account: dict[str, int] = {}
    for h in holdings:
        aid = h.get("account_id") or "?"
        holdings_per_account[aid] = holdings_per_account.get(aid, 0) + 1

    log.info(
        "portfolio.plaid_client: holdings response — accounts=%d holdings=%d securities=%d",
        len(accounts), len(holdings), len(securities),
    )
    log.info(
        "portfolio.plaid_client: item.error=%r available_products=%r billed_products=%r consent_expiration_time=%r",
        item.get("error"),
        item.get("available_products"),
        item.get("billed_products"),
        item.get("consent_expiration_time"),
    )
    for a in accounts:
        aid = a.get("account_id") or "?"
        bal = ((a.get("balances") or {}).get("current"))
        log.info(
            "portfolio.plaid_client:   acct %s subtype=%s mask=%s bal=%s holdings_returned=%d name=%r",
            aid[:8] + "…",
            a.get("subtype"),
            a.get("mask"),
            bal,
            holdings_per_account.get(aid, 0),
            (a.get("name") or "")[:40],
        )
    return result


def remove_item(access_token: str) -> bool:
    """Tell Plaid to invalidate this access_token and free the Item slot.

    Why we call this: Plaid's free trial caps linked Items per environment.
    Every orphaned access_token (user re-linked, password changed, etc.)
    keeps eating a slot until /item/remove is called. We use it from
    /portfolio/plaid/disconnect (explicit user action) and from the
    exchange route (silent cleanup of the prior token before overwriting).

    ITEM_NOT_FOUND from Plaid means the Item is already gone — that's the
    desired terminal state for us, so we treat it as success rather than
    bubbling the error. Any other Plaid error returns False; caller logs
    and surfaces it to the user.
    """
    client = _get_client()
    from plaid.model.item_remove_request import ItemRemoveRequest
    from plaid.exceptions import ApiException

    try:
        client.item_remove(ItemRemoveRequest(access_token=access_token))
        return True
    except ApiException as exc:
        body = getattr(exc, "body", "") or ""
        if "ITEM_NOT_FOUND" in str(body):
            return True
        log.warning("portfolio.plaid_client: item_remove failed: %s", exc)
        return False


def get_investment_transactions(access_token: str, start_date: str, end_date: str) -> dict:
    """Pull investment transactions for a date range.

    ``start_date`` / ``end_date`` are ISO date strings (YYYY-MM-DD). We
    don't paginate here for v1 — Plaid returns up to 500 transactions in
    one call which is plenty for the typical owner's history window.
    """
    client = _get_client()
    import datetime as _dt
    from plaid.model.investments_transactions_get_request import InvestmentsTransactionsGetRequest

    start = _dt.date.fromisoformat(start_date)
    end = _dt.date.fromisoformat(end_date)
    resp = client.investments_transactions_get(
        InvestmentsTransactionsGetRequest(
            access_token=access_token,
            start_date=start,
            end_date=end,
        )
    )
    return {
        "accounts":              _serialize(resp.accounts),
        "investment_transactions": _serialize(resp.investment_transactions),
        "securities":            _serialize(resp.securities),
        "total_investment_transactions": getattr(resp, "total_investment_transactions", None),
    }
