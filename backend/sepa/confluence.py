"""Top Confluence — the names that match the MOST of our screens at once.

A meta-screen that scores every SEPA candidate by how many of the signals we've
built it hits simultaneously, and returns the top picks. The more independent
confirmations stack up, the higher the conviction. Reuses everything; computes
nothing new about the market.

Signals scored (each adds points; SEPA candidacy is the gate):
  • is_buyable            (+3)  Stage-2 + setup + volume-confirmed breakout (p.203)
  • Pullback-to-MA        (+3)  offering a low-vol pullback entry (pullback artifact)
  • Consistent rank       (+3)  leaderboard persistence (a persistent leader)
  • STRONG_BUY / BUY      (+2/+1) rating
  • VCP tight             (+2)  tightness >= 70 (pp.198-205)
  • Accumulation          (+2)  strong/accumulating vol, pocket pivot, or hi-vol breakout
  • CMF inflow            (+1)  Chaikin money flow positive
  • Insider cluster buy   (+2)  >=2 insiders bought (SEC Form 4)
  • Whales accumulating   (+2)  many funds increasing (13F whale moves)
  • 13D activist          (+2)  SC 13D/G filed (5%+ stake)
  • Political disclosure  (+1)  on the curated POTUS/Gov list

Reads the latest scan + leaderboard + pullback artifact + whale caches; the
daily scan / scanner.py are untouched (Rule #2). NOT advice.
"""
from __future__ import annotations

import logging
import time

from . import history, scanner as sepa_scanner
from . import pullback_ma, leaderboard, political_disclosures

log = logging.getLogger("sepa.confluence")

# Configured thresholds + weights (tune here; locked by a guard test).
PERSISTENCE_FLOOR = 50
MIN_APPEARANCES = 4
VCP_TIGHT = 70
WHALES_ACCUM = 8           # >= this many funds increasing = "whales accumulating"
TOP_N = 5

WEIGHTS = {
    "buyable": 3, "pullback": 3, "consistent": 3,
    "strong_buy": 2, "buy": 1, "vcp_tight": 2, "accumulation": 2, "cmf_inflow": 1,
    "insider_cluster": 2, "whales": 2, "activist_13d": 2, "political": 1,
}


def _whale_and_13d(db):
    """ticker -> # funds increasing (whale moves) + ticker -> 13D filing count."""
    nbuy, form13 = {}, {}
    try:
        for d in db.whales_cache.find({}, {"ticker": 1, "payload.moves.n_buying": 1}):
            n = ((d.get("payload") or {}).get("moves") or {}).get("n_buying")
            if isinstance(n, int):
                nbuy[d.get("ticker")] = n
    except Exception as exc:
        log.debug("confluence whale read failed: %s", exc)
    try:
        for d in db.whales13d_cache.find({}, {"ticker": 1, "payload.filings.bucket": 1}):
            fl = ((d.get("payload") or {}).get("filings")) or []
            f13 = sum(1 for f in fl if f.get("bucket") == "form13")
            if f13:
                form13[(d.get("ticker") or "").upper()] = f13
    except Exception as exc:
        log.debug("confluence 13d read failed: %s", exc)
    return nbuy, form13


def compute(top_n: int = TOP_N) -> dict:
    t0 = time.time()
    latest = sepa_scanner.load_latest() or {}
    by_sym = {r.get("symbol"): r for r in (latest.get("all_results") or []) if r.get("symbol")}
    sepa = {s for s, r in by_sym.items() if r.get("is_candidate")}

    cons = {l["symbol"]: l for l in
            (leaderboard.leaderboard(n=300).get("leaders") or [])}

    pullback_syms: set = set()
    try:
        pbart = pullback_ma.load_latest_pullback() or {}
        pullback_syms = {r.get("symbol") for r in (pbart.get("rows") or []) if r.get("symbol")}
    except Exception:
        pass

    db = history._get_db()
    nbuy, form13 = ({}, {}) if db is None else _whale_and_13d(db)

    rows = []
    for s in sepa:
        rec = by_sym[s]
        matches, score = [], 0

        def add(key, label):
            nonlocal score
            matches.append(label)
            score += WEIGHTS[key]

        if rec.get("is_buyable"):
            add("buyable", "Buyable")
        if s in pullback_syms:
            add("pullback", "Pullback")
        c = cons.get(s, {})
        if c.get("appearances", 0) >= MIN_APPEARANCES and c.get("persistence_pct", 0) >= PERSISTENCE_FLOOR:
            add("consistent", "Consistent rank")
        rating = rec.get("rating")
        if rating == "STRONG_BUY":
            add("strong_buy", "STRONG BUY")
        elif rating == "BUY":
            add("buy", "BUY")
        if ((rec.get("vcp") or {}).get("tightness") or 0) >= VCP_TIGHT:
            add("vcp_tight", "VCP tight")
        vol = rec.get("volume") or {}
        if (vol.get("accumulation_strength") in ("strong", "accumulating")
                or vol.get("pocket_pivot") or vol.get("high_vol_breakout")):
            add("accumulation", "Accumulation")
        if vol.get("cmf_signal") == "inflow":
            add("cmf_inflow", "CMF inflow")
        if (rec.get("insider") or {}).get("cluster_buy"):
            add("insider_cluster", "Insider cluster")
        if nbuy.get(s, 0) >= WHALES_ACCUM:
            add("whales", "Whales +")
        if form13.get(s, 0) > 0:
            add("activist_13d", "13D activist")
        if political_disclosures.categories_for(s):
            add("political", "Political")

        rows.append({
            **rec,
            "confluence_score": score,
            "match_count": len(matches),
            "matches": matches,
            "consistency": {"persistence_pct": c.get("persistence_pct"),
                            "current_rank": c.get("current_rank")},
        })

    rows.sort(key=lambda r: (-r["confluence_score"], -r["match_count"], -(r.get("score") or 0)))

    return {
        "generated_at": int(time.time()),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_sec": round(time.time() - t0, 2),
        "rows": rows[: max(0, top_n)],
        "n_scored": len(rows),
        "max_score": rows[0]["confluence_score"] if rows else 0,
        "n_signals": len(WEIGHTS) - 1,   # buy/strong_buy count as one "rating" axis
        "scan_generated_at": latest.get("generated_at"),
        "disclaimer": "Confluence of independent screens — not advice or a forecast.",
    }


_CACHE: dict = {"at": 0.0, "data": None}
_TTL_SEC = 300


def get_confluence(force: bool = False) -> dict:
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["at"]) < _TTL_SEC:
        return _CACHE["data"]
    data = compute()
    _CACHE.update(at=now, data=data)
    return data
