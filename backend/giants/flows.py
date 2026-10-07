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

Filing hygiene (2026-10-06, docs/giants_13f_dedupe_units_2026_10_06.md):
ONE canonical portfolio per (fund, period) (edgar.canonical_filings), VALUE
units normalized per filing (normalize_value_units), and quarter P = the
dominant latest period — funds without filings for P and P-1 are named in
`stale_funds`, never mixed in.

Persisted: `giants_flows` Mongo doc (_id "latest"), rebuilt by
`python -m giants.refresh` (cron, daily — cheap when no new filings) or the
self-healing kick on GET /giants/flows.
"""
from __future__ import annotations

import logging
import math
import os
import statistics
import threading
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from giants import cusips, edgar, registry

log = logging.getLogger("giants.flows")

_MIN_COUNT_MOVE_USD = 2_000_000   # below this a fund isn't counted as buyer/seller
_MIN_ROTATION_MOVE_USD = 1_000_000  # floor for showing a move in rotation views
_QUARTERS = 5                     # filings fetched per fund (→ 4 diff points)
_TOP_ROWS = 40                    # rows persisted per direction per quarter
_STALE_AFTER_SEC = 26 * 60 * 60

# VALUE-unit detection (2026-10-06). A filing's implied price per position
# (value / shares) is compared with the SAME CUSIP's implied price in the
# OTHER curated funds' filings for the same period — an exact period-end
# reference, no external price feed. The median log10 ratio sits at 0 for a
# full-dollar filer and at -3 for a filer reporting in thousands. These two
# numbers decide only the UNIT; they never gate a flow.
_UNITS_MIN_MATCHES = 10          # shared priced CUSIPs needed to call the unit
_UNITS_TOLERANCE_DECADES = 0.5   # |median log10 ratio - {0, -3}| allowed
UNITS_DOLLARS, UNITS_THOUSANDS, UNITS_UNDETERMINED = (
    "dollars", "thousands", "undetermined")


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


# --- Periods ---------------------------------------------------------------

def _q_index(period: str) -> Optional[int]:
    """'2026-06-30' → a running quarter number (consecutive quarters differ
    by exactly 1), or None for an unparseable period."""
    try:
        y, m = int(period[:4]), int(period[5:7])
        return y * 4 + (m - 1) // 3
    except Exception:
        return None


def dominant_period(periods: List[str]) -> Optional[str]:
    """The quarter most curated funds have as their LATEST filing (ties →
    the newer). A lone early filer for the next quarter, or a fund that
    stopped filing in 2023, never sets the board's quarter."""
    c = Counter(p for p in periods if p)
    if not c:
        return None
    return max(c, key=lambda p: (c[p], p))


def _doc_for_q(docs: List[dict], qi: int) -> Optional[dict]:
    for d in docs:
        if _q_index(d.get("period", "")) == qi:
            return d
    return None


def _stale_entry(fund: dict, docs: List[dict], period: str,
                 notice_periods: List[str]) -> dict:
    """Why a fund is left out of quarter `period` (named, never mixed in)."""
    q = quarter_label(period)
    latest = docs[0]["period"] if docs else None
    pi = _q_index(period)
    if period in (notice_periods or []):
        reason = ("filed a 13F-NT for %s (holdings reported by another "
                  "manager)" % q)
    elif not docs:
        reason = "no 13F-HR on file"
    elif _doc_for_q(docs, pi) is not None:
        reason = "no %s filing to compare against" % _label_for_q(pi - 1)
    else:
        reason = "not filed for %s (latest %s)" % (q, quarter_label(latest))
    return {"fund": fund["short"], "cik": fund["cik"], "tier": fund["tier"],
            "latest_period": latest,
            "latest_quarter": quarter_label(latest) if latest else None,
            "reason": reason}


def _label_for_q(qi: int) -> str:
    y, q0 = divmod(qi, 4)
    return "Q%d %d" % (q0 + 1, y)


# --- VALUE units -----------------------------------------------------------

def _implied_prices(doc: dict) -> Dict[str, float]:
    out = {}
    for h in doc.get("holdings") or []:
        v, sh = h.get("value") or 0, h.get("shares") or 0
        if v > 0 and sh > 0:
            out[h["cusip"]] = v / sh
    return out


def _prices_by_cusip(docs: List[dict]) -> Dict[str, Dict[int, float]]:
    ref: Dict[str, Dict[int, float]] = {}
    for d in docs:
        for cusip, px in _implied_prices(d).items():
            ref.setdefault(cusip, {})[d.get("cik")] = px
    return ref


def detect_value_units(doc: dict, ref: Dict[str, Dict[int, float]]
                       ) -> Tuple[str, dict]:
    """(unit, stats) for one filing against other filers' implied prices.

    Bonds (principal amounts) and odd share classes are handled by matching
    the SAME CUSIP across filers — a bond's value/principal is compared with
    another fund's value/principal for that bond. Option rows never reach
    holdings. Fewer than _UNITS_MIN_MATCHES shared CUSIPs, or a median
    ratio near neither 1 nor 1/1000 → UNDETERMINED (left as filed)."""
    own_cik = doc.get("cik")
    logs = []
    for cusip, px in _implied_prices(doc).items():
        others = [q for c, q in (ref.get(cusip) or {}).items() if c != own_cik]
        if others:
            mid = statistics.median(others)
            if mid > 0:
                logs.append(math.log10(px / mid))
    stats = {"n_matched": len(logs)}
    if len(logs) < _UNITS_MIN_MATCHES:
        return UNITS_UNDETERMINED, stats
    med = statistics.median(logs)
    stats["median_log10_ratio"] = round(med, 3)
    if abs(med) <= _UNITS_TOLERANCE_DECADES:
        return UNITS_DOLLARS, stats
    if abs(med + 3) <= _UNITS_TOLERANCE_DECADES:
        return UNITS_THOUSANDS, stats
    return UNITS_UNDETERMINED, stats


def normalize_value_units(docs: List[dict]) -> List[dict]:
    """Canonical filings of DIFFERENT funds for the SAME period → the same
    docs with VALUE in full dollars where the unit could be determined.

    Two passes: the second reference uses only filings the first pass called
    full-dollar, so a thousands filer never drags the reference. Each doc
    returned carries `value_units` (+ `value_units_stats`); a THOUSANDS doc
    is a scaled COPY (×1000), an UNDETERMINED one is left as filed and
    logged — never guessed."""
    docs = [d for d in docs if d]
    ref_all = _prices_by_cusip(docs)
    first = {id(d): detect_value_units(d, ref_all)[0] for d in docs}
    clean = [d for d in docs if first[id(d)] == UNITS_DOLLARS]
    ref = _prices_by_cusip(clean if len(clean) >= 2 else docs)
    out = []
    for d in docs:
        unit, stats = detect_value_units(d, ref)
        if unit == UNITS_THOUSANDS:
            holdings = [dict(h, value=(h.get("value") or 0) * 1000)
                        for h in d.get("holdings") or []]
            d = dict(d, holdings=holdings,
                     total_value=(d.get("total_value") or 0) * 1000)
        elif unit == UNITS_UNDETERMINED:
            log.info("13F VALUE unit undetermined cik=%s period=%s %s — "
                     "left as filed", d.get("cik"), d.get("period"), stats)
            d = dict(d)
        else:
            d = dict(d)
        d["value_units"] = unit
        d["value_units_stats"] = stats
        out.append(d)
    return out


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


def _fund_filings(cik: int, quarters: int, network: bool
                  ) -> Tuple[List[dict], List[str]]:
    """(canonical parsed filings newest first, 13F-NT notice periods).

    Every path resolves ONE portfolio per period (edgar.canonical_filings):
    the network path fetches the original AND its amendments, the cache-only
    and fallback paths read edgar.cached_filings (canonical by default)."""
    if not network:
        return edgar.cached_filings(cik)[: quarters + 1], []
    try:
        idx = edgar.filing_index(cik, max_n=quarters + 1)
    except Exception as exc:
        log.warning("submissions fetch failed cik=%s: %s", cik, exc)
        return edgar.cached_filings(cik)[: quarters + 1], []
    docs = []
    for f in idx["filings"]:
        doc = edgar.fetch_holdings(cik, f)
        if doc:
            docs.append(doc)
    return (edgar.canonical_filings(docs)[: quarters + 1],
            list(idx.get("notice_periods") or []))


def _normalize_units_across(fund_docs: List[List[dict]]) -> List[List[dict]]:
    """Per period, unit-normalize the canonical docs of ALL funds together
    (each filing's reference is the other funds' filings for that period)."""
    by_period: Dict[str, List[Tuple[int, int]]] = {}
    for fi, docs in enumerate(fund_docs):
        for di, d in enumerate(docs):
            by_period.setdefault(d.get("period", ""), []).append((fi, di))
    out = [list(docs) for docs in fund_docs]
    for slots in by_period.values():
        fixed = normalize_value_units([fund_docs[fi][di] for fi, di in slots])
        for (fi, di), d in zip(slots, fixed):
            out[fi][di] = d
    return out


def rebuild(quarters: int = _QUARTERS, network: bool = True) -> dict:
    """Fetch any new filings, recompute the aggregate flow doc, persist it.

    Quarter P (the board's quarter) = the dominant latest period across the
    curated funds. A fund's diff counts for a quarter only when it is
    between two CONSECUTIVE quarterly filings; quarter buckets older than
    the `quarters`-wide window ending at P (Greenlight's 2023 filings) or
    newer than P (a lone early filer) are not built. A fund without
    canonical filings for P and P-1 is listed in `stale_funds`."""
    cus_map, name_map = cusips.get_maps()
    funds = registry.all_funds()
    with _LOCK:
        _REFRESH.update(running=True, done_funds=0, n_funds=len(funds),
                        error=None,
                        started=datetime.now(timezone.utc).isoformat())

    # quarter → ticker → aggregate slot;  fund summaries collected as we go
    agg: Dict[str, Dict[str, dict]] = {}
    unmapped: Dict[str, Dict[str, float]] = {}
    fund_rows, stale_funds = [], []
    try:
        all_docs, notices = [], []
        for fund in funds:
            docs, notice = _fund_filings(fund["cik"], quarters, network)
            all_docs.append(docs)
            notices.append(notice)
            with _LOCK:
                _REFRESH["done_funds"] += 1
        all_docs = _normalize_units_across(all_docs)
        period_p = dominant_period([d[0]["period"] for d in all_docs if d])
        p_idx = _q_index(period_p) if period_p else None
        latest_q = quarter_label(period_p) if period_p else None

        for fund, docs, notice in zip(funds, all_docs, notices):
            diffs_by_q = {}
            for cur, prev in zip(docs, docs[1:]):
                ci, pi = _q_index(cur["period"]), _q_index(prev["period"])
                if ci is None or pi is None or ci - pi != 1:
                    continue  # a gap is not one quarter's move
                if p_idx is None or not (p_idx - quarters < ci <= p_idx):
                    continue
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
            current = latest_q is not None and latest_q in diffs_by_q
            if not current and period_p:
                stale_funds.append(_stale_entry(fund, docs, period_p, notice))
            latest_diff = (diffs_by_q.get(latest_q) if current else None) or []
            fund_rows.append({
                "cik": fund["cik"], "fund": fund["short"],
                "name": fund["name"], "tier": fund["tier"],
                "style": fund["style"], "manager": fund.get("manager") or "",
                "latest_period": latest.get("period") if latest else None,
                "latest_filed": latest.get("filed") if latest else None,
                "n_positions": latest.get("n_positions") if latest else 0,
                "total_value": latest.get("total_value") if latest else 0,
                "value_units": latest.get("value_units") if latest else None,
                "n_quarters_cached": len(docs),
                "current": current,
                "notice_periods": notice,
                "top_adds": [_slim_move(r) for r in latest_diff
                             if r["delta_usd"] > 0][:5],
                "top_trims": [_slim_move(r) for r in latest_diff
                              if r["delta_usd"] < 0][:5],
            })
    except Exception as exc:
        log.exception("giants rebuild failed")
        with _LOCK:
            _REFRESH.update(running=False, error=str(exc))
        raise
    doc = _shape_doc(agg, unmapped, fund_rows, latest_q=latest_q,
                     stale_funds=stale_funds)
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


def _shape_doc(agg, unmapped, fund_rows, latest_q: Optional[str] = None,
               stale_funds: Optional[List[dict]] = None) -> dict:
    quarters = _sort_quarters(agg.keys())          # oldest → newest
    if latest_q is None or latest_q not in agg:
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
        "n_funds_current": sum(1 for f in fund_rows if f.get("current")),
        "stale_funds": list(stale_funds or []),
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


def _notice_periods_by_cik() -> Dict[int, List[str]]:
    """13F-NT periods per fund as the last rebuild saw them (cache-only)."""
    coll = _coll()
    if coll is None:
        return {}
    try:
        doc = coll.find_one({"_id": "latest"},
                            {"funds.cik": 1, "funds.notice_periods": 1}) or {}
    except Exception as exc:
        log.warning("giants_flows notice read failed: %s", exc)
        return {}
    return {f.get("cik"): list(f.get("notice_periods") or [])
            for f in doc.get("funds") or []}


def symbol_rotation(symbol: str) -> dict:
    """For one symbol: which giants moved it in quarter P, and — for each of
    those funds — where their money WENT (top adds) or CAME FROM (top trims)
    in the very same filing. Cache-only read, no network.

    P = the dominant latest quarter across the curated funds. Only funds
    with canonical filings for P AND P-1 are diffed; the rest are named in
    `stale_funds` (Greenlight last filed Q4 2023 — its 2023 moves are not
    this quarter's buying). VALUE units are normalized across the funds'
    filings for each of the two periods (T. Rowe files in thousands)."""
    sym = (symbol or "").upper().strip()
    cus_map, name_map = cusips.get_maps()
    funds = registry.all_funds()
    fund_docs = [edgar.cached_filings(f["cik"]) for f in funds]
    period_p = dominant_period([d[0]["period"] for d in fund_docs if d])
    p_idx = _q_index(period_p) if period_p else None
    latest_q = quarter_label(period_p) if period_p else None
    notices = _notice_periods_by_cik() if period_p else {}

    pairs, stale = [], []
    for fund, docs in zip(funds, fund_docs):
        cur = _doc_for_q(docs, p_idx) if p_idx is not None else None
        prev = _doc_for_q(docs, p_idx - 1) if p_idx is not None else None
        if cur is None or prev is None:
            if period_p:
                stale.append(_stale_entry(fund, docs, period_p,
                                          notices.get(fund["cik"]) or []))
            continue
        pairs.append([fund, cur, prev])
    if pairs:
        curs = normalize_value_units([c for _, c, _ in pairs])
        prevs = normalize_value_units([p for _, _, p in pairs])
        for slot, c, p in zip(pairs, curs, prevs):
            slot[1], slot[2] = c, p

    sellers, buyers = [], []
    for fund, cur, prev in pairs:
        raw = fund_diff(cur, prev)
        _attach_tickers(raw, cus_map, name_map)
        rows = _net_by_ticker(raw)
        mine = [r for r in rows if r["ticker"] == sym
                and abs(r["delta_usd"]) >= _MIN_ROTATION_MOVE_USD]
        if not mine:
            continue
        move = mine[0]
        entry = {
            "fund": fund["short"], "name": fund["name"], "tier": fund["tier"],
            "style": fund["style"], "manager": fund.get("manager") or "",
            "quarter": latest_q,
            "delta_usd": move["delta_usd"],
            "action": move["action"],
            "pct_change_shares": move["pct_change_shares"],
            "position_now_usd": move["value_now"],
            "value_units": cur.get("value_units"),
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
        "n_funds_checked": len(funds),
        "n_funds_current": len(pairs),
        "stale_funds": stale,
        "note": ("Rotation = the SAME fund's biggest adds/trims in the SAME "
                 "quarterly filing — where the money actually moved. "
                 "Quarterly data, 45-day lag, longs only."),
    }
