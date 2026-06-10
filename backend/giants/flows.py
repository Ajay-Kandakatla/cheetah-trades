"""Giant-fund flow analytics — diffs, aggregation, rotation, timeline.

Built on full per-fund 13F portfolios (giants/edgar.py). Three questions:

  1. WHERE ARE THE GIANTS BUYING — per quarter, net $ moved into each ticker
     across the curated Tier S/A funds, ranked. (Aggregate leaderboard.)
  2. THE TREND — the same net flow per ticker across the last several
     quarters (timeline series for sparklines + per-quarter top movers).
  3. ROTATION — a fund sold $14.5B of MU: what did THEY buy that same
     quarter? (fund_diff top adds for every fund that moved the symbol.)

Dollar convention (stated, not hidden): a position change is valued as
Δshares × period-end price of the LATER quarter (value_now / shares_now);
full exits use the PRIOR quarter's period-end price. This separates the
fund's actual decision (share count) from market drift (price move) — a
position whose value rose 20% on zero share change is NOT a buy.

Funds COUNT as a buyer/seller of a name only when the move is ≥ $2M
(_MIN_COUNT_MOVE_USD) — a quant's $40k rebalance is not "a giant buying".
The dollar sums include every share moved regardless.

Persisted: `giants_flows` Mongo doc (_id "latest"), rebuilt by
`python -m giants.refresh` (cron, daily — cheap when no new filings) or the
self-healing kick on GET /giants/flows.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from giants import cusips, edgar, registry

log = logging.getLogger("giants.flows")

_MIN_COUNT_MOVE_USD = 2_000_000   # below this a fund isn't counted as buyer/seller
_MIN_ROTATION_MOVE_USD = 1_000_000  # floor for showing a move in rotation views
_QUARTERS = 5                     # filings fetched per fund (→ 4 diff points)
_TOP_ROWS = 40                    # rows persisted per direction per quarter
_STALE_AFTER_SEC = 26 * 60 * 60


def quarter_label(period: str) -> str:
    """'2026-03-31' → 'Q1 2026'."""
    try:
        y, m = period.split("-")[0], int(period.split("-")[1])
        return "Q%d %s" % ((m + 2) // 3, y)
    except Exception:
        return period


# --- Mongo -----------------------------------------------------------------

def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        return client[db]["giants_flows"]
    except Exception as exc:
        log.warning("giants_flows mongo unavailable: %s", exc)
        return None


# --- Per-fund diff -----------------------------------------------------------

def fund_diff(cur: dict, prev: dict) -> List[dict]:
    """Position changes between two parsed filings of ONE fund.

    Returns rows {cusip, name, value_now, value_prev, shares_now, shares_prev,
    delta_shares, delta_usd, action} for every CUSIP whose share count moved
    (action new/add/trim/exit). Unchanged share counts are omitted — price
    drift alone is not a decision.
    """
    cur_by = {h["cusip"]: h for h in (cur.get("holdings") or [])}
    prev_by = {h["cusip"]: h for h in (prev.get("holdings") or [])}
    out = []
    for cusip in set(cur_by) | set(prev_by):
        c, p = cur_by.get(cusip), prev_by.get(cusip)
        sh_now = (c or {}).get("shares") or 0
        sh_prev = (p or {}).get("shares") or 0
        v_now = (c or {}).get("value") or 0
        v_prev = (p or {}).get("value") or 0
        d_sh = sh_now - sh_prev
        if d_sh == 0:
            continue
        price_now = (v_now / sh_now) if sh_now else None
        price_prev = (v_prev / sh_prev) if sh_prev else None
        if p is None or sh_prev == 0:
            action, delta_usd = "new", float(v_now)
        elif c is None or sh_now == 0:
            action, delta_usd = "exit", -float(v_prev)
        else:
            action = "add" if d_sh > 0 else "trim"
            delta_usd = float(d_sh) * float(price_now or price_prev or 0)
        out.append({
            "cusip": cusip,
            "name": (c or p or {}).get("name") or "",
            "value_now": v_now, "value_prev": v_prev,
            "shares_now": sh_now, "shares_prev": sh_prev,
            "delta_shares": d_sh,
            "delta_usd": round(delta_usd),
            "pct_change_shares": (round(d_sh / sh_prev * 100, 1)
                                  if sh_prev else None),
            "action": action,
        })
    out.sort(key=lambda r: -abs(r["delta_usd"]))
    return out


def _attach_tickers(rows: List[dict], cus_map: dict, name_map: dict) -> None:
    for r in rows:
        r["ticker"] = cusips.resolve(r["cusip"], r["name"], cus_map, name_map)


def _net_by_ticker(rows: List[dict]) -> List[dict]:
    """Combine moves that map to the SAME ticker (e.g. an ADR and the
    ordinary shares carry different CUSIPs) so display lists don't show
    "AZN +3.6B" and "AZN −3.4B" side by side. Unmapped rows stay keyed by
    issuer name. Aggregates already net by ticker — this is for the
    per-fund top-move lists only."""
    by_key: Dict[str, dict] = {}
    for r in rows:
        key = r["ticker"] or ("name:" + r["name"])
        cur = by_key.get(key)
        if cur is None:
            by_key[key] = dict(r)
        else:
            cur["delta_usd"] += r["delta_usd"]
            cur["value_now"] += r["value_now"]
            cur["value_prev"] += r["value_prev"]
            cur["delta_shares"] += r["delta_shares"]
            if abs(r["delta_usd"]) > abs(cur["delta_usd"] - r["delta_usd"]):
                cur["action"] = r["action"]
                cur["pct_change_shares"] = r["pct_change_shares"]
    out = [r for r in by_key.values() if r["delta_usd"] != 0]
    out.sort(key=lambda r: -abs(r["delta_usd"]))
    return out


# --- Refresh + aggregate ------------------------------------------------------

_REFRESH = {"running": False, "started": None, "done_funds": 0, "n_funds": 0,
            "error": None}
_LOCK = threading.Lock()


def refresh_status() -> dict:
    with _LOCK:
        return dict(_REFRESH)


def _fund_filings(cik: int, quarters: int, network: bool) -> List[dict]:
    """Parsed filings for a fund, newest first. network=False → cache only."""
    if not network:
        return edgar.cached_filings(cik)[: quarters + 1]
    try:
        filings = edgar.recent_13f_filings(cik, max_n=quarters + 1)
    except Exception as exc:
        log.warning("submissions fetch failed cik=%s: %s", cik, exc)
        return edgar.cached_filings(cik)[: quarters + 1]
    docs = []
    for f in filings:
        doc = edgar.fetch_holdings(cik, f)
        if doc:
            docs.append(doc)
    return docs


def rebuild(quarters: int = _QUARTERS, network: bool = True) -> dict:
    """Fetch any new filings, recompute the aggregate flow doc, persist it."""
    cus_map, name_map = cusips.get_maps()
    funds = registry.all_funds()
    with _LOCK:
        _REFRESH.update(running=True, done_funds=0, n_funds=len(funds),
                        error=None,
                        started=datetime.now(timezone.utc).isoformat())

    # quarter → ticker → aggregate slot;  fund summaries collected as we go
    agg: Dict[str, Dict[str, dict]] = {}
    unmapped: Dict[str, Dict[str, float]] = {}
    fund_rows = []
    try:
        for fund in funds:
            docs = _fund_filings(fund["cik"], quarters, network)
            diffs_by_q = {}
            for cur, prev in zip(docs, docs[1:]):
                q = quarter_label(cur["period"])
                raw = fund_diff(cur, prev)
                _attach_tickers(raw, cus_map, name_map)
                rows = _net_by_ticker(raw)
                diffs_by_q[q] = rows
                slot_q = agg.setdefault(q, {})
                for r in rows:
                    d = r["delta_usd"]
                    if r["ticker"] is None:
                        if abs(d) >= _MIN_COUNT_MOVE_USD:
                            uq = unmapped.setdefault(q, {})
                            uq[r["name"]] = uq.get(r["name"], 0) + d
                        continue
                    s = slot_q.setdefault(r["ticker"], {
                        "ticker": r["ticker"], "name": r["name"],
                        "net_usd": 0.0, "buy_usd": 0.0, "sell_usd": 0.0,
                        "n_buying": 0, "n_selling": 0,
                        "buyers": [], "sellers": [],
                    })
                    s["net_usd"] += d
                    if d > 0:
                        s["buy_usd"] += d
                    else:
                        s["sell_usd"] += -d
                    if abs(d) >= _MIN_COUNT_MOVE_USD:
                        side = "buyers" if d > 0 else "sellers"
                        s["n_buying" if d > 0 else "n_selling"] += 1
                        s[side].append({
                            "fund": fund["short"], "tier": fund["tier"],
                            "style": fund["style"], "usd": d,
                            "action": r["action"],
                            "pct_change_shares": r["pct_change_shares"],
                        })
            latest = docs[0] if docs else None
            latest_diff = (diffs_by_q.get(quarter_label(latest["period"]))
                           if latest else None) or []
            fund_rows.append({
                "cik": fund["cik"], "fund": fund["short"],
                "name": fund["name"], "tier": fund["tier"],
                "style": fund["style"], "manager": fund.get("manager") or "",
                "latest_period": latest.get("period") if latest else None,
                "latest_filed": latest.get("filed") if latest else None,
                "n_positions": latest.get("n_positions") if latest else 0,
                "total_value": latest.get("total_value") if latest else 0,
                "n_quarters_cached": len(docs),
                "top_adds": [_slim_move(r) for r in latest_diff
                             if r["delta_usd"] > 0][:5],
                "top_trims": [_slim_move(r) for r in latest_diff
                              if r["delta_usd"] < 0][:5],
            })
            with _LOCK:
                _REFRESH["done_funds"] += 1
    except Exception as exc:
        log.exception("giants rebuild failed")
        with _LOCK:
            _REFRESH.update(running=False, error=str(exc))
        raise
    doc = _shape_doc(agg, unmapped, fund_rows)
    coll = _coll()
    if coll is not None:
        try:
            coll.replace_one({"_id": "latest"}, doc, upsert=True)
        except Exception as exc:
            log.warning("giants_flows write failed: %s", exc)
    with _LOCK:
        _REFRESH.update(running=False)
    return doc


def _slim_move(r: dict) -> dict:
    return {"ticker": r.get("ticker"), "name": r["name"],
            "delta_usd": r["delta_usd"], "action": r["action"],
            "pct_change_shares": r["pct_change_shares"]}


def _sort_quarters(qs) -> List[str]:
    def key(q):
        try:
            n, y = q.split()
            return (int(y), int(n[1]))
        except Exception:
            return (0, 0)
    return sorted(qs, key=key)


def _shape_doc(agg, unmapped, fund_rows) -> dict:
    quarters = _sort_quarters(agg.keys())          # oldest → newest
    latest_q = quarters[-1] if quarters else None

    def series_for(ticker):
        return [{"q": q, "net_usd": round(agg[q].get(ticker, {}).get("net_usd", 0))}
                for q in quarters]

    rows_in, rows_out = [], []
    if latest_q:
        latest = agg[latest_q]
        for s in latest.values():
            s["net_usd"] = round(s["net_usd"])
            s["buy_usd"] = round(s["buy_usd"])
            s["sell_usd"] = round(s["sell_usd"])
            s["buyers"] = sorted(s["buyers"], key=lambda b: -b["usd"])[:6]
            s["sellers"] = sorted(s["sellers"], key=lambda b: b["usd"])[:6]
        ranked = sorted(latest.values(), key=lambda s: -s["net_usd"])
        rows_in = [dict(s, timeline=series_for(s["ticker"]))
                   for s in ranked[:_TOP_ROWS] if s["net_usd"] > 0]
        rows_out = [dict(s, timeline=series_for(s["ticker"]))
                    for s in ranked[::-1][:_TOP_ROWS] if s["net_usd"] < 0]

    by_quarter = []
    for q in quarters:
        ranked = sorted(agg[q].values(), key=lambda s: -s["net_usd"])
        by_quarter.append({
            "q": q,
            "top_in": [{"ticker": s["ticker"], "net_usd": round(s["net_usd"]),
                        "n_buying": s["n_buying"]}
                       for s in ranked[:5] if s["net_usd"] > 0],
            "top_out": [{"ticker": s["ticker"], "net_usd": round(s["net_usd"]),
                         "n_selling": s["n_selling"]}
                        for s in ranked[::-1][:5] if s["net_usd"] < 0],
            "unmapped_big_moves": sorted(
                ([{"name": n, "net_usd": round(v)}
                  for n, v in (unmapped.get(q) or {}).items()]),
                key=lambda u: -abs(u["net_usd"]))[:5],
        })

    return {
        "_id": "latest",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "quarters": quarters,
        "latest_quarter": latest_q,
        "rows_in": rows_in,
        "rows_out": rows_out,
        "by_quarter": by_quarter,
        "funds": fund_rows,
        "n_funds": len(fund_rows),
        "n_funds_with_data": sum(1 for f in fund_rows if f["n_quarters_cached"]),
        "params": {
            "min_count_move_usd": _MIN_COUNT_MOVE_USD,
            "quarters_fetched": _QUARTERS,
            "dollar_convention": "delta_shares x period-end price (later "
                                 "quarter); exits at prior quarter's price",
        },
        "disclaimer": ("13F-HR filings: quarterly, up to 45-day lag, longs "
                       "only, options excluded. Tier S/A active managers "
                       "only — index giants (Vanguard/BlackRock/State Street) "
                       "are excluded because mandate-driven flow and entity "
                       "restructurings would swamp the conviction signal."),
        "source": "SEC EDGAR 13F-HR information tables (free, full portfolio)",
    }


# --- Reads -------------------------------------------------------------------

def latest(kick_if_stale: bool = True) -> dict:
    """The persisted aggregate doc (+ refreshing status). Self-heals: kicks a
    background rebuild when missing or older than 26h."""
    coll = _coll()
    doc = None
    if coll is not None:
        try:
            doc = coll.find_one({"_id": "latest"})
        except Exception as exc:
            log.warning("giants_flows read failed: %s", exc)
    stale = True
    if doc and doc.get("as_of"):
        try:
            ts = datetime.fromisoformat(doc["as_of"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            stale = ((datetime.now(timezone.utc) - ts).total_seconds()
                     > _STALE_AFTER_SEC)
        except Exception:
            pass
    st = refresh_status()
    if kick_if_stale and stale and not st["running"]:
        start_refresh()
        st = refresh_status()
    if doc is None:
        return {"refreshing": st["running"], "rows_in": [], "rows_out": [],
                "quarters": [], "funds": [], "n_funds": 0,
                "note": "first refresh is downloading ~6 quarters of 13F "
                        "filings for each giant fund — typically 15-40 min"}
    doc.pop("_id", None)
    doc["refreshing"] = st["running"]
    doc["refresh_progress"] = ({"done": st["done_funds"], "of": st["n_funds"]}
                               if st["running"] else None)
    return doc


def start_refresh() -> dict:
    with _LOCK:
        if _REFRESH["running"]:
            return dict(_REFRESH)
        _REFRESH.update(running=True, error=None, done_funds=0)

    def run():
        try:
            rebuild()
        except Exception:
            pass  # state already captured in _REFRESH / logs

    threading.Thread(target=run, name="giants-refresh", daemon=True).start()
    return refresh_status()


def symbol_rotation(symbol: str) -> dict:
    """For one symbol: which giants moved it last quarter, and — for each of
    those funds — where their money WENT (top adds) or CAME FROM (top trims)
    in the very same filing. Cache-only read, no network."""
    sym = (symbol or "").upper().strip()
    cus_map, name_map = cusips.get_maps()
    sellers, buyers = [], []
    latest_q = None
    for fund in registry.all_funds():
        docs = edgar.cached_filings(fund["cik"])[:2]
        if len(docs) < 2:
            continue
        raw = fund_diff(docs[0], docs[1])
        _attach_tickers(raw, cus_map, name_map)
        rows = _net_by_ticker(raw)
        q = quarter_label(docs[0]["period"])
        if latest_q is None or q > latest_q:
            latest_q = q
        mine = [r for r in rows if r["ticker"] == sym
                and abs(r["delta_usd"]) >= _MIN_ROTATION_MOVE_USD]
        if not mine:
            continue
        move = mine[0]
        entry = {
            "fund": fund["short"], "name": fund["name"], "tier": fund["tier"],
            "style": fund["style"], "manager": fund.get("manager") or "",
            "quarter": q,
            "delta_usd": move["delta_usd"],
            "action": move["action"],
            "pct_change_shares": move["pct_change_shares"],
            "position_now_usd": move["value_now"],
        }
        others = [r for r in rows if r["ticker"] != sym]
        if move["delta_usd"] < 0:
            entry["their_top_adds"] = [
                _slim_move(r) for r in others if r["delta_usd"] > 0][:6]
            sellers.append(entry)
        else:
            entry["their_top_trims"] = [
                _slim_move(r) for r in others if r["delta_usd"] < 0][:6]
            buyers.append(entry)
    sellers.sort(key=lambda e: e["delta_usd"])
    buyers.sort(key=lambda e: -e["delta_usd"])
    return {
        "symbol": sym,
        "quarter": latest_q,
        "sellers": sellers,
        "buyers": buyers,
        "n_funds_checked": len(registry.all_funds()),
        "note": ("Rotation = the SAME fund's biggest adds/trims in the SAME "
                 "quarterly filing — where the money actually moved. "
                 "Quarterly data, 45-day lag, longs only."),
    }
