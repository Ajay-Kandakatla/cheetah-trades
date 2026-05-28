"""HTTP routes for personal portfolio holdings.

Two ingestion paths live behind this router:

1. Manual (legacy) — user types ticker/shares/cost basis into a form.
   Routes: GET / POST / DELETE /portfolio. Backed by ``portfolio.store``.

2. Plaid Investments (new) — user logs into Fidelity via Plaid Link;
   we pull holdings from Plaid's API. Routes: /portfolio/plaid/*,
   /portfolio/holdings, /portfolio/position-meta, /portfolio/status.
   Backed by ``portfolio.plaid_store`` + ``portfolio.plaid_client``.

The two paths are intentionally separate: a future "merge user-typed
overrides with Plaid positions" view can read both stores without
either knowing about the other. All Plaid routes are owner-gated via
the FEATURE_CATALOG ``portfolio`` feature — the manual routes are not
(they predate access gating and are scoped per ``current_user_email``).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from auth import current_user_email
from portfolio import quotes, store

log = logging.getLogger("portfolio.api")

router = APIRouter()


# --------------------------------------------------------------------------
# Owner / feature gate for the Plaid routes
# --------------------------------------------------------------------------
def _require_portfolio_access(email: str) -> str:
    """Gate every /portfolio/plaid/* and Plaid-backed route on the
    ``portfolio`` feature flag.

    Returns the (normalized lowercase) caller email so the route handler
    can use it as the partition key for Mongo reads/writes. Stealth-
    gates as 404 — non-owners shouldn't even discover the page exists.
    """
    e = (email or "").strip().lower()
    if not e:
        raise HTTPException(404, "Not Found")
    try:
        from access.store import user_has_feature
    except Exception:
        # access module missing — be conservative, deny.
        raise HTTPException(404, "Not Found")
    if not user_has_feature(e, "portfolio"):
        raise HTTPException(404, "Not Found")
    return e


def _rollup(holdings: list[dict], quote_map: dict[str, dict]) -> dict:
    """Compute per-row + total $ values from holdings + live quotes.

    Returned shape feeds both the dedicated /portfolio page and the
    morning-brief Holdings card.
    """
    rows = []
    total_value = 0.0
    total_cost = 0.0
    for h in holdings:
        t = h["ticker"]
        q = quote_map.get(t) or {}
        shares = float(h.get("shares") or 0)
        cost = float(h.get("cost_basis") or 0)
        last = q.get("last")
        cur_value = (shares * last) if (last is not None) else None
        pl_dollars = (cur_value - cost) if (cur_value is not None) else None
        pl_pct = ((cur_value / cost - 1) * 100) if (cur_value is not None and cost > 0) else None
        day_dollars = (shares * (q.get("day_change") or 0)) if last is not None else None
        rows.append({
            "ticker":         t,
            "shares":         shares,
            "cost_basis":     cost,
            "avg_cost":       (cost / shares) if shares > 0 else None,
            "last":           last,
            "prev_close":     q.get("prev_close"),
            "current_value":  None if cur_value is None else round(cur_value, 2),
            "pl_dollars":     None if pl_dollars is None else round(pl_dollars, 2),
            "pl_pct":         None if pl_pct is None else round(pl_pct, 2),
            "day_change_pct": q.get("day_change_pct"),
            "day_dollars":    None if day_dollars is None else round(day_dollars, 2),
            "account":        h.get("account"),
            "tags":           h.get("tags") or [],
        })
        if cur_value is not None:
            total_value += cur_value
        total_cost += cost

    # Sort by current value desc when known, else by cost_basis.
    rows.sort(key=lambda r: -((r.get("current_value") or r.get("cost_basis") or 0)))

    # Position weights (% of total value).
    if total_value > 0:
        for r in rows:
            cv = r.get("current_value") or 0
            r["weight_pct"] = round((cv / total_value) * 100, 1)

    return {
        "rows":         rows,
        "total_value":  round(total_value, 2),
        "total_cost":   round(total_cost, 2),
        "pl_dollars":   round(total_value - total_cost, 2),
        "pl_pct":       round((total_value / total_cost - 1) * 100, 2) if total_cost > 0 else None,
        "day_dollars":  round(sum((r.get("day_dollars") or 0) for r in rows), 2),
        "count":        len(rows),
    }


def build_summary(user_email: str) -> dict:
    """Headless helper — used by morning.brief to inline holdings into
    the brief response without an HTTP round trip."""
    holdings = store.list_holdings(user_email)
    if not holdings:
        return {"available": False, "count": 0, "rows": []}
    quote_map = quotes.fetch_quotes([h["ticker"] for h in holdings])
    summary = _rollup(holdings, quote_map)
    summary["available"] = True
    return summary


@router.get("/portfolio")
async def portfolio_get(user_email: str = Depends(current_user_email)):
    return JSONResponse(build_summary(user_email))


@router.post("/portfolio")
async def portfolio_upsert(
    payload: dict = Body(...),
    user_email: str = Depends(current_user_email),
):
    """Upsert a single holding.

    Body: { ticker, shares, cost_basis, account?, tags?, notes? }
    """
    if not payload.get("ticker"):
        raise HTTPException(400, "ticker required")
    if payload.get("shares") is None:
        raise HTTPException(400, "shares required (0 = closed position; will be removed)")
    if float(payload["shares"]) == 0:
        return JSONResponse(store.remove_holding(
            user_email, payload["ticker"], payload.get("account"),
        ))
    return JSONResponse(store.upsert_holding(
        user_email,
        payload["ticker"],
        float(payload["shares"]),
        float(payload.get("cost_basis") or 0),
        account=payload.get("account"),
        tags=payload.get("tags"),
        notes=payload.get("notes"),
    ))


@router.delete("/portfolio")
async def portfolio_delete(
    ticker: str = Query(...),
    account: str | None = Query(None),
    user_email: str = Depends(current_user_email),
):
    return JSONResponse(store.remove_holding(user_email, ticker, account))


# ===========================================================================
# Plaid-backed routes (Investments product)
# ===========================================================================
def _format_holdings_response(owner_email: str, plaid_response: dict,
                                cached_at: int, fresh: bool) -> dict:
    """Shape the Plaid response for the /portfolio page.

    Joins:
      - holdings + securities → flat rows keyed by ticker/symbol
      - live prices from yfinance (the same `quotes` module the legacy
        path uses) so day-change/P&L stays current between Plaid pulls
        (Plaid only repolls the broker a few times a day)
      - user-typed entry/stop/target/notes → R-multiple math fields
    """
    from portfolio import plaid_store

    holdings = plaid_response.get("holdings") or []
    securities = plaid_response.get("securities") or []
    accounts = plaid_response.get("accounts") or []

    # Investment-only scope (2026-05-27).
    # ----------------------------------------------------------------------
    # Plaid's institution login (Fidelity) often returns more than the
    # broker account — e.g. a linked Synchrony savings account comes back
    # as type=depository, subtype=savings. We don't want those polluting
    # the portfolio totals, account cards, heatmap, or alert pipeline:
    # this page is a *stock* portfolio, not a net-worth dashboard.
    #
    # Plaid account "type" enum values: depository, credit, loan,
    # investment, brokerage (legacy), other. We accept "investment" and
    # "brokerage" defensively; both map to the same concept for Fidelity.
    _BROKER_TYPES = {"investment", "brokerage"}
    accounts = [
        a for a in accounts
        if (a.get("type") or "").lower() in _BROKER_TYPES
    ]

    # CSV-scope (2026-05-27 strict mode).
    # ----------------------------------------------------------------------
    # The user explicitly wants only the broker accounts represented in
    # their uploaded Fidelity CSV — not the 401k / RSU / HSA plans that
    # Plaid lumps in as "investment" accounts. (E.g. "Synchrony Financial
    # My Savings Plan" is Plaid's name for the user's employer 401(k)
    # administered by Fidelity — Plaid classifies it as type=investment,
    # subtype=non-taxable brokerage account, so the type filter above
    # doesn't drop it.)
    #
    # Mechanism: read the user's CSV-imported holdings, extract the
    # last-4 mask from the account label ("Individual - TOD (8361)" →
    # "8361"), and keep only Plaid accounts whose mask matches. If the
    # user hasn't imported a CSV yet, this is a no-op and all investment
    # accounts pass through (the original behavior).
    #
    # When the user expands to full net-worth view later, the toggle is:
    # drop this block, or expose a `?scope=all` query param to bypass.
    import re as _re
    try:
        csv_rows = store.list_holdings(owner_email)
    except Exception:
        csv_rows = []
    csv_masks: set[str] = set()
    for row in csv_rows:
        if "csv-import" not in (row.get("tags") or []):
            continue
        m = _re.search(r"\((\d{2,6})\)\s*$", row.get("account") or "")
        if m:
            csv_masks.add(m.group(1))
    if csv_masks:
        accounts = [a for a in accounts if (a.get("mask") or "") in csv_masks]

    # Also filter holdings to the surviving account_ids so we never show
    # a position parented to an excluded account (defense in depth).
    keep_ids = {a.get("account_id") for a in accounts if a.get("account_id")}
    if keep_ids:
        holdings = [h for h in holdings if h.get("account_id") in keep_ids]

    sec_by_id = {s.get("security_id"): s for s in securities if s.get("security_id")}

    meta_by_symbol = {m["symbol"]: m for m in plaid_store.get_position_meta(owner_email)}

    # Symbols to fetch live quotes for — only equities/ETFs Plaid tags
    # with a ticker. Skip cash / fixed-income / options-with-no-ticker.
    symbols: set[str] = set()
    for h in holdings:
        sec = sec_by_id.get(h.get("security_id")) or {}
        sym = (sec.get("ticker_symbol") or "").upper().strip()
        if sym:
            symbols.add(sym)
    live_quotes = quotes.fetch_quotes(list(symbols)) if symbols else {}

    rows = []
    for h in holdings:
        sec = sec_by_id.get(h.get("security_id")) or {}
        symbol = (sec.get("ticker_symbol") or "").upper().strip()
        name = sec.get("name") or ""
        qty = float(h.get("quantity") or 0)
        cost_basis = h.get("cost_basis")
        cost_basis = float(cost_basis) if cost_basis is not None else None
        plaid_price = h.get("institution_price")
        plaid_price = float(plaid_price) if plaid_price is not None else None

        # Prefer live quote when we have one; fall back to Plaid's last
        # recorded price (refreshed by the broker a few times a day).
        live = live_quotes.get(symbol) or {}
        current_price = live.get("last") if live.get("last") is not None else plaid_price

        current_value = (current_price * qty) if (current_price is not None) else None
        pl_dollars = None
        pl_pct = None
        if current_value is not None and cost_basis is not None and cost_basis > 0:
            pl_dollars = current_value - cost_basis
            pl_pct = (current_value / cost_basis - 1) * 100

        meta = meta_by_symbol.get(symbol) or {}
        entry = meta.get("entry")
        stop = meta.get("stop")
        target = meta.get("target")

        # R-multiple math: reward / risk per position. None when entry +
        # stop aren't both set, or when entry == stop (zero risk = invalid).
        r_multiple = None
        if (entry is not None and stop is not None and entry != stop
                and current_price is not None):
            risk = entry - stop                     # > 0 for longs
            reward = current_price - entry
            r_multiple = reward / risk

        rows.append({
            "symbol":         symbol,
            "name":           name,
            "account_id":     h.get("account_id"),
            "quantity":       qty,
            "cost_basis":     cost_basis,
            "avg_cost":       (cost_basis / qty) if (cost_basis is not None and qty > 0) else None,
            "current_price":  current_price,
            "plaid_price":    plaid_price,
            "current_value":  current_value,
            "pl_dollars":     pl_dollars,
            "pl_pct":         pl_pct,
            "day_change_pct": live.get("day_change_pct"),
            "entry":          entry,
            "stop":           stop,
            "target":         target,
            "r_multiple":     r_multiple,
            "notes":          meta.get("notes") or "",
        })

    # Tag every Plaid-derived row so the frontend can show a "via Plaid"
    # badge separately from CSV-imported rows.
    for r in rows:
        r["source"] = "plaid"

    # Merge in manually-imported holdings (from CSV uploads or the legacy
    # /portfolio POST form). These live in portfolio.store keyed by
    # (user, ticker, account). They render side-by-side with Plaid rows in
    # the same table — useful when Plaid Investments Trial tier withholds
    # per-position detail and the user pastes their Fidelity CSV instead.
    try:
        manual_rows = store.list_holdings(owner_email)
    except Exception:
        manual_rows = []

    # Skip manual rows that would duplicate a Plaid row in the same account.
    # Match is (symbol, account_id-or-account-label). Since Plaid uses
    # opaque account_id and CSV uses the human label, the dedup is
    # symbol-only — a Plaid row "wins" if both report the same ticker.
    plaid_symbols = {(r.get("symbol") or "").upper() for r in rows}

    # Fetch live quotes for any symbols not already in the Plaid set so
    # the manual rows get the same current_price + day-change treatment.
    extra_symbols = [
        (h.get("ticker") or "").upper()
        for h in manual_rows
        if (h.get("ticker") or "").upper() and (h.get("ticker") or "").upper() not in plaid_symbols
    ]
    extra_quotes = quotes.fetch_quotes(extra_symbols) if extra_symbols else {}

    for h in manual_rows:
        sym = (h.get("ticker") or "").upper().strip()
        if not sym or sym in plaid_symbols:
            continue
        qty = float(h.get("shares") or 0)
        cost_basis = float(h.get("cost_basis") or 0) or None
        live = extra_quotes.get(sym) or {}
        current_price = live.get("last")

        current_value = (current_price * qty) if (current_price is not None and qty) else None
        pl_dollars = None
        pl_pct = None
        if current_value is not None and cost_basis and cost_basis > 0:
            pl_dollars = current_value - cost_basis
            pl_pct = (current_value / cost_basis - 1) * 100

        meta = meta_by_symbol.get(sym) or {}
        entry = meta.get("entry")
        stop = meta.get("stop")
        target = meta.get("target")
        r_multiple = None
        if (entry is not None and stop is not None and entry != stop
                and current_price is not None):
            risk = entry - stop
            reward = current_price - entry
            r_multiple = reward / risk

        rows.append({
            "symbol":         sym,
            "name":           (h.get("notes") or "")[:120],
            "account_id":     h.get("account") or "manual",
            "quantity":       qty,
            "cost_basis":     cost_basis,
            "avg_cost":       (cost_basis / qty) if (cost_basis and qty > 0) else None,
            "current_price":  current_price,
            "plaid_price":    None,
            "current_value":  current_value,
            "pl_dollars":     pl_dollars,
            "pl_pct":         pl_pct,
            "day_change_pct": live.get("day_change_pct"),
            "entry":          entry,
            "stop":           stop,
            "target":         target,
            "r_multiple":     r_multiple,
            "notes":          meta.get("notes") or "",
            "source":         "csv" if "csv-import" in (h.get("tags") or []) else "manual",
        })

    rows.sort(key=lambda r: -((r.get("current_value") or 0)))

    return {
        "rows":      rows,
        "accounts":  accounts,
        "cached_at": cached_at,
        "fresh":     fresh,
    }


@router.get("/portfolio/status")
async def portfolio_status(user_email: str = Depends(current_user_email)):
    """Status check used by the frontend to choose between
    "Setup Plaid first" / "Connect Fidelity" / "Connected" UI states.

    NEVER requires Plaid keys to be present — that's the whole point.
    The page must render its CTA when keys are missing instead of
    crashing.
    """
    e = (user_email or "").strip().lower()
    if not e:
        raise HTTPException(401, "auth required")
    # Same feature gate, but with a real-ish error so the frontend can
    # tell "no access" from "not configured".
    try:
        from access.store import user_has_feature
        has_feature = user_has_feature(e, "portfolio")
    except Exception:
        has_feature = False
    if not has_feature:
        raise HTTPException(404, "Not Found")

    from portfolio import plaid_client, plaid_store

    item = plaid_store.get_item(e)
    return JSONResponse({
        "plaid_configured":   plaid_client.is_configured(),
        "has_linked_account": bool(item),
        "institution_name":   (item or {}).get("institution_name") or "",
        "last_sync":          (item or {}).get("last_sync"),
        "linked_at":          (item or {}).get("linked_at"),
    })


@router.post("/portfolio/plaid/link-token")
async def portfolio_plaid_link_token(user_email: str = Depends(current_user_email)):
    """Mint a one-shot Link token for the frontend to open Plaid Link.
    Returns 503 with setup instructions when Plaid env vars are missing.
    """
    e = _require_portfolio_access(user_email)
    from portfolio import plaid_client
    if not plaid_client.is_configured():
        raise HTTPException(503, "Plaid not configured. Add PLAID_CLIENT_ID and PLAID_SECRET to backend/.env and restart the api container.")
    # Plaid rejects emails (or anything that looks like PII) in client_user_id.
    # Hash the email to a deterministic opaque ID — same user always maps to
    # the same Plaid identity, so re-links update existing holdings instead
    # of orphaning them. Local Mongo storage stays keyed by email (unchanged).
    import hashlib
    plaid_uid = hashlib.sha256(e.encode("utf-8")).hexdigest()
    try:
        token = plaid_client.create_link_token(user_id=plaid_uid)
    except plaid_client.PlaidNotConfigured as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        log.exception("plaid link-token failed")
        raise HTTPException(502, f"plaid error: {exc}")
    return JSONResponse(token)


@router.post("/portfolio/plaid/exchange")
async def portfolio_plaid_exchange(
    payload: dict = Body(...),
    user_email: str = Depends(current_user_email),
):
    """Exchange the public_token from Plaid Link's onSuccess for a
    long-lived access_token and persist it."""
    e = _require_portfolio_access(user_email)
    public_token = (payload or {}).get("public_token")
    if not public_token:
        raise HTTPException(400, "public_token required")

    from portfolio import plaid_client, plaid_store
    try:
        exchanged = plaid_client.exchange_public_token(public_token)
        item_meta = plaid_client.get_item(exchanged["access_token"])
    except plaid_client.PlaidNotConfigured as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        log.exception("plaid exchange failed")
        raise HTTPException(502, f"plaid error: {exc}")

    # Re-link cleanup: if this owner already has a linked item, the old
    # access_token will be orphaned when we overwrite the doc below.
    # Plaid's free trial caps Items at 10 and every orphan eats one — so
    # tell Plaid to drop the old Item before we swap in the new token.
    # Best-effort: a failure here is logged but does not block the new
    # link from being saved (the user is mid-Connect and shouldn't be
    # punished for a Plaid hiccup on cleanup).
    prior = plaid_store.get_item(e)
    if prior and prior.get("access_token"):
        try:
            plaid_client.remove_item(prior["access_token"])
        except Exception as exc:
            log.warning("plaid re-link: failed to remove prior item for %s: %s", e, exc)

    plaid_store.save_item(
        owner_email=e,
        access_token=exchanged["access_token"],
        item_id=exchanged["item_id"],
        institution_name=item_meta.get("institution_name") or "",
    )
    return JSONResponse({"ok": True, "institution_name": item_meta.get("institution_name") or ""})


@router.post("/portfolio/plaid/disconnect")
async def portfolio_plaid_disconnect(user_email: str = Depends(current_user_email)):
    """Revoke the Plaid Item and wipe the local link.

    Frees the slot on Plaid's side (free trial caps Items at 10) and
    flips /portfolio/status back to ``has_linked_account: False`` so the
    page falls back to the Connect CTA.
    """
    e = _require_portfolio_access(user_email)
    from portfolio import plaid_store
    return JSONResponse(plaid_store.disconnect(e))


def _refresh_from_plaid(owner_email: str) -> Optional[dict]:
    """Hit Plaid /holdings/get for the owner and persist. Returns the
    fresh Plaid response on success, None when there's no linked item
    or Plaid is degraded."""
    from portfolio import plaid_client, plaid_store
    item = plaid_store.get_item(owner_email)
    if not item or not item.get("access_token"):
        return None
    try:
        resp = plaid_client.get_holdings(item["access_token"])
    except plaid_client.PlaidNotConfigured:
        return None
    except Exception as exc:
        log.warning("plaid holdings fetch failed: %s", exc)
        return None
    plaid_store.cache_holdings(owner_email, resp)
    plaid_store.mark_synced(owner_email)
    return resp


@router.get("/portfolio/holdings")
async def portfolio_holdings_get(
    refresh: bool = Query(False),
    user_email: str = Depends(current_user_email),
):
    """Get rolled-up holdings — cached if < 1h old, else refetch.

    ``?refresh=true`` forces a Plaid roundtrip even when the cache is
    fresh; the page UI binds this to the "↻" button next to the synced
    timestamp.
    """
    e = _require_portfolio_access(user_email)
    from portfolio import plaid_client, plaid_store

    item = plaid_store.get_item(e)
    if not item:
        return JSONResponse({
            "rows":      [],
            "accounts":  [],
            "cached_at": None,
            "fresh":     False,
            "linked":    False,
        })

    cached = None
    if not refresh:
        cached = plaid_store.get_cached_holdings(e, max_age_sec=3600)

    if cached is not None:
        rolled = _format_holdings_response(e, cached, cached["cached_at"], fresh=False)
        rolled["linked"] = True
        return JSONResponse(rolled)

    if not plaid_client.is_configured():
        # Stale cache (or never cached) + Plaid offline → return
        # whatever we have, marked as not-fresh, so the page still
        # renders something.
        stored = plaid_store.get_cached_holdings(e, max_age_sec=0)
        if stored is not None:
            rolled = _format_holdings_response(e, stored, stored["cached_at"], fresh=False)
            rolled["linked"] = True
            return JSONResponse(rolled)
        raise HTTPException(503, "Plaid not configured and no cached holdings available")

    resp = _refresh_from_plaid(e)
    if resp is None:
        # Plaid call failed AND nothing cached — surface the error so
        # the page can show a retry CTA.
        raise HTTPException(502, "Plaid holdings fetch failed; check logs")
    rolled = _format_holdings_response(e, resp, plaid_store._now(), fresh=True)
    rolled["linked"] = True
    return JSONResponse(rolled)


@router.post("/portfolio/holdings/refresh")
async def portfolio_holdings_refresh(user_email: str = Depends(current_user_email)):
    """Force a re-pull from Plaid. Used by the page's ↻ button when
    the user wants the freshest possible numbers."""
    e = _require_portfolio_access(user_email)
    resp = _refresh_from_plaid(e)
    if resp is None:
        raise HTTPException(502, "refresh failed — no linked account or Plaid offline")
    return JSONResponse({"ok": True, "refreshed_at": int(datetime.now(tz=timezone.utc).timestamp())})


@router.post("/portfolio/csv-import")
async def portfolio_csv_import(
    file: UploadFile = File(...),
    user_email: str = Depends(current_user_email),
):
    """Import positions from a Fidelity 'Download Positions' CSV.

    This is the manual fallback when Plaid Investments Trial tier
    withholds per-position detail. The user logs into Fidelity, clicks
    Download on the Positions page, and uploads the resulting CSV here.

    Behavior
    --------
    - Each uploaded CSV is treated as a complete snapshot — ALL prior
      csv-import rows for this user are wiped, then today's rows are
      inserted. This matches how Fidelity's "Download Positions" actually
      ships data (one file, all accounts) and prevents stale rows from
      yesterday's accounts lingering after a different export today.
    - Manually-typed positions (no csv-import tag) are preserved.
    - The imported rows show up in the same /portfolio/holdings response
      as Plaid-derived rows, tagged ``source: "csv"``.
    """
    e = _require_portfolio_access(user_email)

    if not file or not file.filename:
        raise HTTPException(400, "no file uploaded")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "expected a .csv file from Fidelity's Positions page Download button")

    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(400, f"could not read upload: {exc}")
    if not content:
        raise HTTPException(400, "uploaded file is empty")
    if len(content) > 5_000_000:
        raise HTTPException(413, "file too large (max 5 MB) — that's not a Fidelity positions CSV")

    from portfolio import csv_import as _csv_import
    parsed = _csv_import.parse_fidelity_csv(content)
    if not parsed.get("format_ok"):
        return JSONResponse(
            {
                "ok":      False,
                "reason":  parsed.get("error", "unrecognized CSV format"),
                "hint":    "Make sure you used the 'Download' button on Fidelity's Positions page (not Activity / History).",
                "headers": parsed.get("headers_seen") or [],
            },
            status_code=400,
        )

    result = _csv_import.apply_to_store(e, parsed, replace_account=True, wipe_all_csv=True)
    result["parsed_summary"] = {
        "imported_rows": parsed["imported"],
        "total_value":   parsed["total_value"],
        "skipped":       len(parsed.get("skipped") or []),
    }
    return JSONResponse(result)


@router.get("/portfolio/csv-import/disk")
async def portfolio_csv_disk_list(user_email: str = Depends(current_user_email)):
    """List CSV files in the backend/fidelity/ drop folder so the UI can
    show what's available before triggering an ingest."""
    _require_portfolio_access(user_email)
    from portfolio import csv_import as _csv_import
    return JSONResponse({
        "drop_dir": str(_csv_import._drop_dir()),
        "files":    _csv_import.list_csvs(),
    })


@router.post("/portfolio/csv-import/sync-disk")
async def portfolio_csv_disk_sync(
    archive: bool = Query(False, description="Move processed file to fidelity/archive/ after ingest"),
    user_email: str = Depends(current_user_email),
):
    """Ingest the most recently modified CSV from backend/fidelity/.

    Cheaper than the upload-via-form path: just save Fidelity's CSV
    into the watched folder (or cloud-sync it there) and hit this.
    Cron uses the same code path for auto-ingest.
    """
    e = _require_portfolio_access(user_email)
    from portfolio import csv_import as _csv_import
    result = _csv_import.sync_from_disk(e, archive=archive)
    if not result.get("ok"):
        # 404 if no file (so the UI can show "drop a CSV first"), 400 for
        # parse failures (so retry doesn't make sense — fix the CSV).
        status = 404 if "no CSV files" in result.get("reason", "") else 400
        return JSONResponse(result, status_code=status)
    return JSONResponse(result)


@router.get("/portfolio/alerts/state")
async def portfolio_alerts_state(user_email: str = Depends(current_user_email)):
    """Today's alert state per ticker — used by /portfolio to show
    a small "last alert · ack'd?" indicator next to each row.
    """
    e = _require_portfolio_access(user_email)
    from portfolio import alerts as _alerts
    return JSONResponse({"rows": _alerts.get_today_state(e)})


@router.post("/portfolio/alerts/ack")
async def portfolio_alerts_ack(
    payload: dict = Body(...),
    user_email: str = Depends(current_user_email),
):
    """Mark today's alerts for a ticker as acknowledged so the 15-min
    intraday re-ring stops. Called from /portfolio when the user opens
    a push notification (the push URL includes ?ack=<symbol>).
    """
    e = _require_portfolio_access(user_email)
    symbol = (payload or {}).get("symbol")
    if not symbol:
        raise HTTPException(400, "symbol required")
    from portfolio import alerts as _alerts
    return JSONResponse(_alerts.acknowledge(e, symbol))


@router.post("/portfolio/corporate-actions/scan")
async def portfolio_corp_actions_scan(
    lookback_days: int = Query(30, ge=1, le=365),
    user_email: str = Depends(current_user_email),
):
    """Manual trigger — sweep the user's holdings for unapplied splits +
    dividends. Idempotent: already-applied actions are skipped via the
    audit collection. Daily cron also runs this at 6 AM ET."""
    e = _require_portfolio_access(user_email)
    from portfolio import corporate_actions as _ca
    return JSONResponse(_ca.sweep_user(e, lookback_days=lookback_days))


@router.get("/portfolio/corporate-actions/recent")
async def portfolio_corp_actions_recent(
    limit: int = Query(25, ge=1, le=200),
    user_email: str = Depends(current_user_email),
):
    """List the most recent corp_actions (splits + dividends) the sweep
    has applied or recorded for this user. Drives the audit UI on the
    /portfolio page so you can see every share-count change that wasn't
    triggered by a CSV import."""
    e = _require_portfolio_access(user_email)
    from portfolio import corporate_actions as _ca
    return JSONResponse({"rows": _ca.recent_actions(e, limit=limit)})


@router.post("/portfolio/alerts/run")
async def portfolio_alerts_run(
    kind: str = Query("intraday", regex="^(intraday|eod_brief|eod_escalate)$"),
    user_email: str = Depends(current_user_email),
):
    """Manual trigger for the alert pipeline. Same code path as the cron;
    used for testing + the "Run alerts now" button on /portfolio. Returns
    a structured result so the UI can show "X pushed, Y skipped".
    """
    e = _require_portfolio_access(user_email)
    from portfolio import alerts as _alerts
    if kind == "intraday":
        return JSONResponse(_alerts.check_intraday(e))
    if kind == "eod_brief":
        return JSONResponse(_alerts.eod_brief(e))
    return JSONResponse(_alerts.eod_escalate(e))


@router.delete("/portfolio/csv-import")
async def portfolio_csv_clear(
    account: Optional[str] = Query(None),
    user_email: str = Depends(current_user_email),
):
    """Clear CSV-imported positions. ``?account=...`` to scope to one
    account label (e.g. "Individual - TOD (8361)"); omitting it clears
    all rows tagged ``csv-import``.
    """
    e = _require_portfolio_access(user_email)
    db = store._get_db()
    if db is None:
        return JSONResponse({"ok": False, "reason": "db unavailable"})

    q: dict = {"user_email": e, "tags": "csv-import"}
    if account:
        q["account"] = account
    res = db.portfolio_holdings.delete_many(q)
    return JSONResponse({"ok": True, "removed": res.deleted_count})


@router.put("/portfolio/position-meta")
async def portfolio_position_meta_set(
    payload: dict = Body(...),
    user_email: str = Depends(current_user_email),
):
    """Save user-typed entry/stop/target/notes for a single symbol."""
    e = _require_portfolio_access(user_email)
    symbol = (payload.get("symbol") or "").strip()
    if not symbol:
        raise HTTPException(400, "symbol required")
    from portfolio import plaid_store
    return JSONResponse(plaid_store.set_position_meta(
        owner_email=e,
        symbol=symbol,
        entry=payload.get("entry"),
        stop=payload.get("stop"),
        target=payload.get("target"),
        notes=payload.get("notes"),
    ))


@router.get("/portfolio/position-meta")
async def portfolio_position_meta_list(user_email: str = Depends(current_user_email)):
    """List all user-typed metas for the caller."""
    e = _require_portfolio_access(user_email)
    from portfolio import plaid_store
    return JSONResponse({"metas": plaid_store.get_position_meta(e)})


@router.get("/portfolio/transactions")
async def portfolio_transactions(
    days: int = Query(30, ge=1, le=365),
    user_email: str = Depends(current_user_email),
):
    """Optional helper — pull recent investment transactions. Not used
    by the main /portfolio page yet but exposed so a future "trade
    history" tab can plug in without another router change.
    """
    e = _require_portfolio_access(user_email)
    from portfolio import plaid_client, plaid_store
    item = plaid_store.get_item(e)
    if not item or not item.get("access_token"):
        raise HTTPException(404, "no linked account")
    end = date.today()
    start = end - timedelta(days=days)
    try:
        resp = plaid_client.get_investment_transactions(
            item["access_token"], start.isoformat(), end.isoformat(),
        )
    except plaid_client.PlaidNotConfigured as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        log.exception("plaid transactions failed")
        raise HTTPException(502, f"plaid error: {exc}")
    return JSONResponse(resp)
