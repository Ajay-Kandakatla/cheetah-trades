"""Money Movement — where the giants are putting money, FUND-centric.

Inverts our per-ticker 13F whale cache (`whales_cache`, stock -> holders) into
**fund -> [stocks they're moving money into]**, grouped into three sections by
the holder classification we already compute
(`supply_demand.whales._classify_holder`, surfaced as each holder's `type`):

  • hedge_fund    — "Hedge Funds"   (Two Sigma, Renaissance, Citadel, …)
  • index_giant   — "Institutional" (Vanguard, BlackRock, State Street, Fidelity)
  • other         — "Whales"        (other large 13F holders — Morgan Stanley, …)

Each fund row lists the stocks it holds/bought from OUR scan universe, ranked
with SEPA/Pullback overlaps first then by $ added last quarter. A stock that is
also a SEPA candidate or a Pullback-to-MA candidate is flagged so the FE chips
it. Funds are ranked by net $ moved IN (the "money movement").

Reads `whales_cache` + the latest scan + the pullback artifact. No scanner
change. Coverage = whichever tickers have a cached 13F record (warmed lazily by
the whale views; run `sepa.warm_whales` for fuller coverage). NOT advice.
"""
from __future__ import annotations

import logging
import time

from . import history, scanner as sepa_scanner
from . import pullback_ma

log = logging.getLogger("sepa.money_movement")

# Map the holder `type` -> our three sections.
SECTION_OF = {"hedge_fund": "hedge_fund", "index_giant": "institutional", "other": "whales"}
SECTIONS = ("hedge_fund", "institutional", "whales")

PER_SECTION = 25            # funds kept per section (FE shows ~10 + "expand")
MAX_STOCKS_PER_FUND = 25    # stocks kept per fund row (top buys/overlaps)


def _added_usd(value, pct_change):
    """$ the fund ADDED last quarter, from current position + QoQ % change:
    ΔPosition = value · pct_change / (1 + pct_change). None if unknown."""
    if not isinstance(value, (int, float)) or not isinstance(pct_change, (int, float)):
        return None
    denom = 1.0 + pct_change
    if denom == 0:
        return None
    return value * pct_change / denom


def _fund_row(name: str, f: dict, sepa_syms: set, pullback_syms: set) -> dict:
    stocks = list(f["stocks"].values())
    total_added = sum(s["added"] for s in stocks
                      if isinstance(s["added"], (int, float)) and s["added"] > 0)
    n_sepa = sum(1 for s in stocks if s["is_sepa"])
    n_pullback = sum(1 for s in stocks if s["is_pullback"])

    def _key(s):
        overlap = 1 if (s["is_sepa"] or s["is_pullback"]) else 0
        added = s["added"] if isinstance(s["added"], (int, float)) else -1e18
        val = s["value"] if isinstance(s["value"], (int, float)) else 0
        return (overlap, added, val)

    stocks.sort(key=_key, reverse=True)
    return {
        "fund": name,
        "type": f["type"],
        "total_added": round(total_added) if total_added else 0,
        "n_stocks": len(stocks),
        "n_sepa": n_sepa,
        "n_pullback": n_pullback,
        "stocks": stocks[:MAX_STOCKS_PER_FUND],
    }


def _empty(t0, reason=None):
    return {
        "generated_at": int(t0),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
        "duration_sec": 0.0,
        "sections": {s: [] for s in SECTIONS},
        "section_labels": {"hedge_fund": "Hedge Funds", "institutional": "Institutional", "whales": "Whales"},
        "tickers_covered": 0, "funds_total": 0,
        "error": reason,
    }


def compute() -> dict:
    t0 = time.time()
    db = history._get_db()
    if db is None:
        return _empty(t0, "mongo_unavailable")

    latest = sepa_scanner.load_latest() or {}
    by_sym = {r.get("symbol"): r for r in (latest.get("all_results") or []) if r.get("symbol")}
    sepa_syms = {s for s, r in by_sym.items() if r.get("is_candidate")}

    pullback_syms: set = set()
    try:
        pbart = pullback_ma.load_latest_pullback() or {}
        pullback_syms = {r.get("symbol") for r in (pbart.get("rows") or []) if r.get("symbol")}
    except Exception:
        pass

    # ── Invert whales_cache -> fund -> {stocks} ──────────────────────────────
    funds: dict = {}
    covered = 0
    for doc in db.whales_cache.find({}, {"ticker": 1, "payload": 1}):
        tkr = doc.get("ticker")
        payload = doc.get("payload") or {}
        holders = payload.get("holders") or []
        if not tkr or not holders:
            continue
        covered += 1
        for h in holders:
            nm = h.get("holder")
            if not nm:
                continue
            val, pc = h.get("value"), h.get("pct_change")
            added = _added_usd(val, pc)
            f = funds.setdefault(nm, {"type": h.get("type") or "other", "stocks": {}})
            if h.get("type") and h.get("type") != "other":
                f["type"] = h["type"]                      # strongest type signal wins
            ph = h.get("pct_held")
            f["stocks"][tkr] = {
                "ticker": tkr,
                "name": (by_sym.get(tkr) or {}).get("name") or tkr,
                "value": round(val) if isinstance(val, (int, float)) else None,
                "pct_change": round(pc * 100, 1) if isinstance(pc, (int, float)) else None,
                "pct_held": round(ph * 100, 2) if isinstance(ph, (int, float)) else None,
                "added": round(added) if added is not None else None,
                "is_sepa": tkr in sepa_syms,
                "is_pullback": tkr in pullback_syms,
            }

    # ── Build + group + rank fund rows ───────────────────────────────────────
    buckets: dict = {s: [] for s in SECTIONS}
    for nm, f in funds.items():
        row = _fund_row(nm, f, sepa_syms, pullback_syms)
        # Keep funds that are MOVING money in, or that touch our SEPA/Pullback names.
        if row["total_added"] <= 0 and (row["n_sepa"] + row["n_pullback"]) == 0:
            continue
        sec = SECTION_OF.get(f["type"], "whales")
        buckets[sec].append(row)

    for s in SECTIONS:
        # Most money moved IN first; ties -> more overlaps with our names.
        buckets[s].sort(key=lambda r: (r["total_added"], r["n_sepa"] + r["n_pullback"]), reverse=True)
        buckets[s] = buckets[s][:PER_SECTION]

    return {
        "generated_at": int(time.time()),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_sec": round(time.time() - t0, 2),
        "sections": buckets,
        "section_labels": {"hedge_fund": "Hedge Funds", "institutional": "Institutional", "whales": "Whales"},
        "tickers_covered": covered,
        "funds_total": len(funds),
        "scan_generated_at": latest.get("generated_at"),
        "disclaimer": "13F holdings are quarter-lagged; informational, not advice.",
    }


# ── In-process cache (the Money Movement section hits this) ──────────────────
_CACHE: dict = {"at": 0.0, "data": None}
_TTL_SEC = 600


def get_money_movement(force: bool = False) -> dict:
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["at"]) < _TTL_SEC:
        return _CACHE["data"]
    data = compute()
    _CACHE.update(at=now, data=data)
    return data
