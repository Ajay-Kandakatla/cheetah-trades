"""Quarter-over-quarter institutional accumulation — what changed, and by how much.

Ajay 2026-08-16: *"Also give me updated and notification as Accumulations change
as money moving I need a comparison."*

THE COMPARISON THIS MAKES
-------------------------
For each ticker, group its 13F holders BY THEIR OWN FILING QUARTER, then compare
the two most recent quarters:

    money in      total position $ held by funds reporting the new quarter
    money out     ...minus what the prior quarter's filers held
    new buyers    funds present this quarter, absent last
    exits         funds present last quarter, gone this one

WHY GROUPING BY QUARTER IS THE WHOLE POINT
------------------------------------------
The provider returns a MIX. Measured 2026-08-16, every sampled ticker mixed two
quarters in one payload — APGE had 6 funds on Mar 31 and 4 on Jun 30 — and the
existing modal simply summed them, producing "+$2.1B bought / -$1.0B sold / net
+$1.1B" that describes no single period. Adding one fund's Q1 delta to another's
Q2 delta is not a comparison, it is a category error.

So every number here is scoped to one quarter, and a ticker whose funds have not
yet rolled reports `comparable: false` rather than a confident wrong answer.

NOT A SIGNAL
------------
13F is filed up to 45 days after quarter end, so "money moved in" describes a
position that was already built up to four and a half months ago. It is context
for a setup, never a trigger. The engine never reads this.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("supply_demand.accumulation_changes")

# Below this the "change" is rounding on an illiquid name, not money moving.
MIN_NET_CHANGE_USD = 25_000_000

# ...or a big relative swing on a smaller book.
MIN_NET_CHANGE_PCT = 15.0

# Alerts are scoped to names Ajay actually holds or watches. A universe-wide
# accumulation alert would be ~2,600 notifications a quarter, which is how a
# useful channel becomes one that gets muted.
ALERT_SCOPE = ("portfolio", "watchlist")


def _num(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def by_quarter(holders: list) -> dict:
    """Group holders by their own `date_reported`. PURE.

    Returns {quarter_iso: {"n": int, "total_value": float, "holders": {name: value}}}
    """
    out: dict = {}
    for h in holders or []:
        d = str(h.get("date_reported") or "")[:10]
        if len(d) != 10 or d[4] != "-":
            continue
        bucket = out.setdefault(d, {"n": 0, "total_value": 0.0, "holders": {}})
        val = _num(h.get("value")) or 0.0
        name = h.get("holder") or "?"
        bucket["n"] += 1
        bucket["total_value"] += val
        bucket["holders"][name] = val
    return out


# Funds that must appear in BOTH quarters before a dollar change means anything.
# The provider returns only a top-N holder list, so a thin overlap makes the
# comparison a sample-size artifact rather than a measurement.
MIN_OVERLAP_FUNDS = 3


def compare_quarters(holders: list) -> dict:
    """Like-for-like money-in / money-out between the two most recent quarters.

    THE TRAP THIS AVOIDS (found on live data 2026-08-16). The provider returns
    only the top ~10 holders, and those get split across two filing quarters.
    Naively differencing the quarter TOTALS compares "the 2 funds that still
    report Q1" against "the 8 that have filed Q2" and prints NVDA +$1,520B
    (+968%) — pure sample size, no money moved.

    So the headline number is computed on the funds present in BOTH quarters,
    and funds that entered or left are reported SEPARATELY with their own
    dollars. Those are real events, but they are not the same measurement and
    must never be added into one figure.

    PURE.
    """
    buckets = by_quarter(holders)
    quarters = sorted(buckets)
    if len(quarters) < 2:
        return {
            "comparable": False,
            "reason": ("only one filing quarter present — the funds behind this "
                       "name have not rolled yet" if quarters
                       else "no dated holdings"),
            "quarters": quarters,
        }

    prev_q, new_q = quarters[-2], quarters[-1]
    prev, new = buckets[prev_q], buckets[new_q]
    p_h, n_h = prev["holders"], new["holders"]

    both = sorted(set(p_h) & set(n_h))
    entrants = sorted(set(n_h) - set(p_h))
    leavers = sorted(set(p_h) - set(n_h))

    if len(both) < MIN_OVERLAP_FUNDS:
        return {
            "comparable": False,
            "reason": (f"only {len(both)} fund(s) report both {prev_q} and {new_q} — "
                       f"too thin to compare (the provider returns a top-N list, "
                       f"so a small overlap is a sampling artifact, not a flow)"),
            "quarters": [prev_q, new_q],
            "prev_holders": prev["n"], "new_holders": new["n"],
            "overlap_funds": len(both),
            "entrants": entrants, "exits": leavers,
        }

    base = sum(p_h[k] for k in both)
    now = sum(n_h[k] for k in both)
    net = now - base
    pct = (net / base * 100.0) if base else None

    return {
        "comparable": True,
        "prev_quarter": prev_q,
        "new_quarter": new_q,
        # Same funds, both quarters — the only honest "money moved" figure.
        "overlap_funds": len(both),
        "prev_value": round(base, 2),
        "new_value": round(now, 2),
        "net_change_usd": round(net, 2),
        "net_change_pct": round(pct, 2) if pct is not None else None,
        "direction": "accumulating" if net > 0 else ("distributing" if net < 0 else "flat"),
        "prev_holders": prev["n"],
        "new_holders": new["n"],
        # Reported alongside, never folded into net_change_usd.
        "new_buyers": entrants,
        "new_buyer_usd": round(sum(n_h[k] for k in entrants), 2),
        "exits": leavers,
        "exit_usd": round(sum(p_h[k] for k in leavers), 2),
        # The honest caveat travels WITH the number, so no caller can quote the
        # dollar figure without it.
        "caveat": (f"Change measured across the {len(both)} fund(s) reporting BOTH "
                   f"{prev_q} and {new_q}. Entrants and exits are listed separately "
                   f"and are NOT in that figure — the provider returns only a top-N "
                   f"holder list, so a fund 'leaving' may just have dropped out of "
                   f"the top N. 13F lags up to 45 days."),
    }


def is_significant(cmp: dict) -> bool:
    """Worth telling someone about? PURE."""
    if not cmp.get("comparable"):
        return False
    net = abs(_num(cmp.get("net_change_usd")) or 0.0)
    pct = abs(_num(cmp.get("net_change_pct")) or 0.0)
    return net >= MIN_NET_CHANGE_USD or pct >= MIN_NET_CHANGE_PCT


def holder_map(holders: list) -> dict:
    """{fund name: position $} across the WHOLE payload, quarter-agnostic. PURE.

    Deliberately not grouped by quarter — see compare_to_snapshot for why.
    """
    out: dict = {}
    for h in holders or []:
        name = h.get("holder")
        if not name:
            continue
        out[name] = (_num(h.get("value")) or 0.0)
    return out


def compare_maps(before: dict, after: dict) -> dict:
    """Same-fund flow between two holder maps. PURE.

    The headline is computed ONLY over funds present in both, so it measures
    positions changing rather than the holder list reshuffling. Entrants and
    exits carry their own dollars and are never folded in.
    """
    both = sorted(set(before) & set(after))
    entrants = sorted(set(after) - set(before))
    leavers = sorted(set(before) - set(after))

    base = sum(before[k] for k in both)
    now = sum(after[k] for k in both)
    net = now - base
    pct = (net / base * 100.0) if base else None

    return {
        "overlap_funds": len(both),
        "prev_value": round(base, 2),
        "new_value": round(now, 2),
        "net_change_usd": round(net, 2),
        "net_change_pct": round(pct, 2) if pct is not None else None,
        "direction": "accumulating" if net > 0 else ("distributing" if net < 0 else "flat"),
        "new_buyers": entrants,
        "new_buyer_usd": round(sum(after[k] for k in entrants), 2),
        "exits": leavers,
        "exit_usd": round(sum(before[k] for k in leavers), 2),
    }


def _snapshots():
    db = _db()
    return db.whales_snapshots if db is not None else None


def take_snapshot(symbol: str, payload: dict) -> Optional[dict]:
    """Record today's holder picture so a FUTURE run has something to compare to.

    WHY THIS IS THE ONLY WAY. Measured 2026-08-16 across every ticker sampled:
    a 13F payload lists each fund exactly ONCE, at its own latest report date,
    so the overlap between the two quarters inside a single payload is ZERO.
    There is no quarter-over-quarter comparison to be made from one payload —
    not for NVDA, not for anything. The comparison must be against a picture we
    stored ourselves, which is why this exists and why the first sweep can only
    establish a baseline.
    """
    coll = _snapshots()
    if coll is None:
        return None
    per = (payload.get("period") or {})
    # Never bank an empty picture. A snapshot with no holders and a null quarter
    # still matches the {"dominant_quarter": {"$ne": now}} lookup later, so it
    # would be selected as "the earlier quarter" and produce a comparison
    # against nothing — zero overlap, or worse, a fabricated 100% outflow.
    if not payload.get("holders") or not per.get("dominant"):
        return None
    doc = {
        "symbol": symbol.upper(),
        "taken_at": datetime.now(timezone.utc),
        "dominant_quarter": per.get("dominant"),
        "holders": holder_map(payload.get("holders") or []),
        "n_holders": len((payload.get("holders") or [])),
    }
    try:
        coll.insert_one(dict(doc))
        # Two years is plenty — eight quarters of comparisons.
        coll.delete_many({"symbol": doc["symbol"],
                          "taken_at": {"$lt": doc["taken_at"].replace(
                              year=doc["taken_at"].year - 2)}})
    except Exception as exc:
        log.warning("accumulation: snapshot failed for %s: %s", symbol, exc)
        return None
    return doc


def compare_to_snapshot(symbol: str, payload: dict) -> dict:
    """Compare today's holders against our most recent snapshot from an EARLIER
    reporting quarter."""
    coll = _snapshots()
    per = (payload.get("period") or {})
    now_q = per.get("dominant")
    if coll is None:
        return {"comparable": False, "reason": "snapshot store unavailable"}
    try:
        prior = coll.find_one(
            {"symbol": symbol.upper(),
             "dominant_quarter": {"$ne": now_q, "$exists": True}},
            sort=[("taken_at", -1)])
    except Exception as exc:
        return {"comparable": False, "reason": f"snapshot read failed: {exc}"}

    if not prior:
        return {"comparable": False,
                "reason": ("no earlier-quarter snapshot yet — baseline recorded, "
                           "comparisons begin at the next 13F roll"),
                "new_quarter": now_q}

    d = compare_maps(prior.get("holders") or {}, holder_map(payload.get("holders") or []))
    if d["overlap_funds"] < MIN_OVERLAP_FUNDS:
        return {"comparable": False, **d,
                "prev_quarter": prior.get("dominant_quarter"), "new_quarter": now_q,
                "reason": (f"only {d['overlap_funds']} fund(s) appear in both "
                           f"pictures — the provider returns a top-N list, so a "
                           f"thin overlap is a sampling artifact, not a flow")}

    return {
        "comparable": True,
        "prev_quarter": prior.get("dominant_quarter"),
        "new_quarter": now_q,
        "prev_taken_at": prior.get("taken_at").isoformat()
                         if hasattr(prior.get("taken_at"), "isoformat") else None,
        **d,
        "caveat": (f"Measured across the {d['overlap_funds']} fund(s) present in both "
                   f"our {prior.get('dominant_quarter')} snapshot and today's "
                   f"{now_q} data. Entrants and exits are listed separately and are "
                   f"NOT in that figure — a fund 'leaving' may simply have dropped "
                   f"out of the provider's top-N list. 13F lags up to 45 days."),
    }


def for_symbol(symbol: str, *, snapshot: bool = False) -> dict:
    """Today's accumulation comparison for one ticker.

    Compares against our own stored snapshot from an earlier quarter — the
    within-payload comparison is impossible (see take_snapshot).
    """
    from . import whales
    try:
        payload = whales.get_whales(symbol)
    except Exception as exc:
        return {"symbol": symbol.upper(), "comparable": False,
                "reason": f"fetch failed: {exc}"}
    cmp = compare_to_snapshot(symbol, payload)
    if snapshot:
        take_snapshot(symbol, payload)
    cmp["symbol"] = symbol.upper()
    cmp["significant"] = is_significant(cmp)
    return cmp


# ---------------------------------------------------------------------------
# scope + sweep
# ---------------------------------------------------------------------------
def _alert_symbols(email: Optional[str] = None) -> list:
    """Holdings + watchlist. Deliberately small — see ALERT_SCOPE."""
    syms: list = []
    seen = set()

    def _add(s):
        s = (s or "").upper().strip()
        if s and s not in seen:
            seen.add(s)
            syms.append(s)

    # list_holdings REQUIRES an email — calling it bare raises TypeError, which
    # the except below swallowed into a silent empty scope.
    if not email:
        try:
            from auth import HOUSE_OWNER_EMAILS
            email = HOUSE_OWNER_EMAILS[0] if HOUSE_OWNER_EMAILS else None
        except Exception:
            email = None
    try:
        from portfolio import store as pstore
        for h in (pstore.list_holdings(email) if email else []):
            _add(h.get("ticker") or h.get("symbol"))
    except Exception as exc:
        log.debug("accumulation: portfolio unavailable: %s", exc)
    try:
        from sepa import scanner
        for w in scanner.load_watchlist() or []:
            _add(w.get("symbol"))
    except Exception as exc:
        log.debug("accumulation: watchlist unavailable: %s", exc)
    return syms


def _db():
    try:
        from sepa import history
        return history._get_db()
    except Exception:
        return None


def sweep(symbols: Optional[list] = None, *, notify: bool = False,
          email: Optional[str] = None) -> dict:
    """Compare every scoped ticker and record the significant moves.

    Idempotent per (symbol, new_quarter): a quarter's move is recorded — and
    alerted — ONCE. Without that, a weekly cron would re-announce the same
    quarter every Sunday for three months.
    """
    syms = symbols if symbols is not None else _alert_symbols(email)
    db = _db()
    results, fresh = [], []

    for s in syms:
        # snapshot=True: every sweep records today's picture, so the NEXT
        # quarter has a baseline. The first sweep can only bank baselines.
        cmp = for_symbol(s, snapshot=True)
        results.append(cmp)
        if not cmp.get("significant"):
            continue
        if db is None:
            fresh.append(cmp)
            continue
        key = {"symbol": cmp["symbol"], "new_quarter": cmp.get("new_quarter")}
        try:
            if db.accumulation_changes.find_one(key, {"_id": 1}):
                continue                     # already recorded this quarter
            db.accumulation_changes.insert_one({
                **key,
                "net_change_usd": cmp.get("net_change_usd"),
                "net_change_pct": cmp.get("net_change_pct"),
                "direction": cmp.get("direction"),
                "new_buyers": cmp.get("new_buyers"),
                "exits": cmp.get("exits"),
                "detected_at": datetime.now(timezone.utc),
            })
            fresh.append(cmp)
        except Exception as exc:
            log.warning("accumulation: persist failed for %s: %s", s, exc)

    sent = 0
    if notify and fresh:
        sent = _notify(fresh)

    return {"scanned": len(syms), "compared": len(results),
            "significant": len([r for r in results if r.get("significant")]),
            "new_this_run": len(fresh), "notified": sent,
            "changes": sorted(fresh, key=lambda c: -abs(c.get("net_change_usd") or 0))}


def _fmt_usd(v: Optional[float]) -> str:
    v = _num(v) or 0.0
    a = abs(v)
    sign = "+" if v >= 0 else "-"
    if a >= 1e9:
        return f"{sign}${a/1e9:.1f}B"
    if a >= 1e6:
        return f"{sign}${a/1e6:.0f}M"
    return f"{sign}${a:,.0f}"


def alert_line(cmp: dict) -> str:
    """One phone-sized line. PURE — so the wording is testable."""
    arrow = "🟢" if cmp.get("direction") == "accumulating" else "🔴"
    pct = cmp.get("net_change_pct")
    pct_s = f" ({pct:+.0f}%)" if pct is not None else ""
    bits = [f"{arrow} {cmp.get('symbol')} {_fmt_usd(cmp.get('net_change_usd'))}{pct_s}"]
    nb, ex = cmp.get("new_buyers") or [], cmp.get("exits") or []
    if nb:
        bits.append(f"{len(nb)} new")
    if ex:
        bits.append(f"{len(ex)} out")
    bits.append(f"{cmp.get('prev_quarter')}→{cmp.get('new_quarter')}")
    return " · ".join(bits)


def _notify(changes: list) -> int:
    """One consolidated push, never one per ticker.

    Ajay asked for accumulation alerts on 2026-08-16, which adds a 4th kind to
    a deliberately-small keep-set. It stays tolerable only because 13F moves
    quarterly and the scope is holdings + watchlist: expect a handful a quarter.
    Batched into ONE message for the same reason.
    """
    try:
        from push import sender
        from auth import HOUSE_OWNER_EMAILS
    except Exception as exc:
        log.warning("accumulation: push unavailable: %s", exc)
        return 0

    top = sorted(changes, key=lambda c: -abs(c.get("net_change_usd") or 0))[:5]
    body = "\n".join(alert_line(c) for c in top)
    if len(changes) > len(top):
        body += f"\n+{len(changes) - len(top)} more"
    payload = {
        "title": f"🏦 Institutional flow changed on {len(changes)} name"
                 f"{'s' if len(changes) != 1 else ''}",
        "body": body[:300],
        "tag": "accumulation-change",
        "url": "/supply-demand",
        "kind": "accumulation_change",
    }
    try:
        owner = HOUSE_OWNER_EMAILS[0] if HOUSE_OWNER_EMAILS else None
        res = (sender.send_to_user(owner, payload, kind="accumulation_change")
               if owner else sender.send_to_all(payload, kind="accumulation_change"))
        return int((res or {}).get("sent") or 0)
    except Exception as exc:
        log.warning("accumulation: push failed: %s", exc)
        return 0


def recent(limit: int = 50) -> list:
    db = _db()
    if db is None:
        return []
    try:
        rows = list(db.accumulation_changes.find({}, {"_id": 0})
                    .sort("detected_at", -1).limit(int(limit)))
    except Exception:
        return []
    for r in rows:
        ts = r.get("detected_at")
        r["detected_at"] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
    return rows


def bank_baselines(symbols: Optional[list] = None, *, limit: int = 4000) -> dict:
    """Snapshot today's holder picture for a WIDE set of tickers.

    Alerts are scoped to holdings + watchlist, but the comparison should work
    for any ticker Ajay opens later — and it only can if a baseline was banked
    a quarter earlier. This reads the already-warmed cache (no network), so
    banking thousands costs a Mongo write each.
    """
    from . import whales
    coll = whales._cache_coll()
    if coll is None:
        return {"ok": False, "reason": "cache unavailable"}

    if symbols is None:
        try:
            rows = coll.find({}, {"ticker": 1}).limit(int(limit))
            symbols = [r["ticker"] for r in rows if r.get("ticker")]
        except Exception as exc:
            return {"ok": False, "reason": f"cache read failed: {exc}"}

    banked = skipped = 0
    for s in symbols:
        try:
            doc = coll.find_one({"ticker": s})
            payload = (doc or {}).get("payload") or {}
            if not payload.get("holders"):
                skipped += 1
                continue
            if take_snapshot(s, payload):
                banked += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
    log.info("accumulation: banked %d baselines (%d skipped)", banked, skipped)
    return {"ok": True, "banked": banked, "skipped": skipped}


if __name__ == "__main__":                                   # pragma: no cover
    import json
    # Bank broadly first (cheap, cache-only), then alert on the narrow scope.
    print(json.dumps({"baselines": bank_baselines(),
                      "sweep": sweep(notify=True)}, indent=2, default=str))
