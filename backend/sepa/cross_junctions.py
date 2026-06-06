"""Cross Junctions — confluence of Pullback-to-MA ∩ SEPA ∩ consistent rank.

A "cross junction" is a name where THREE independent signals meet at once:

  1. SEPA candidate     — passes the Trend Template qualifier + liquidity
                          (book p.79): a real Stage-2 leader, on the SEPA list.
  2. Consistently ranked — has held a top-tier SEPA rank across recent scans
                          (leaderboard persistence) — a PERSISTENT leader, not a
                          one-day flash.
  3. Pullback-to-MA     — is offering a low-risk pullback entry toward the rising
                          50-day MA on contracting volume (Minervini "natural
                          reaction" / tennis ball, pp.72, 237-238).

That confluence is the high-conviction setup: a proven, persistent leader that is
*also* giving you a pullback entry right now.

Universe order (Ajay 2026-06-06): **S&P 500 first**; if the S&P intersection is
thin (< MIN_SP500_RESULTS), broaden the pullback leg to the **Russell 1000**.

Derived view (like dual_momentum / pullback_ma): reads the latest scan + the rank
leaderboard; `scanner.py` and the daily scan are untouched (Rule #2). Configured
thresholds are labelled and locked by a source-guard test. NOT advice.
"""
from __future__ import annotations

import logging
import time

from . import scanner as sepa_scanner
from . import pullback_ma, leaderboard
from .universe import load_universe

log = logging.getLogger("sepa.cross_junctions")

# ── Configured thresholds (Ajay 2026-06-06) — tune here; locked by a guard. ──
LOOKBACK_DAYS = 14            # rank-history window (≈ 10 trading days)
MIN_APPEARANCES = 4          # must appear in >= this many of the window's days
PERSISTENCE_FLOOR = 50       # >= this % of appearances in the top-20 = "consistent"
MIN_SP500_RESULTS = 6        # if fewer S&P junctions than this, add the Russell
TOP_N = 24

# Junction score weights (sum = 1.0): leader quality / pullback entry / persistence
W_SEPA = 0.45
W_PULLBACK = 0.30
W_PERSIST = 0.25


def _universe_set(mode: str) -> set:
    try:
        return {str(s).upper() for s in load_universe(mode)}
    except Exception as exc:
        log.warning("cross_junctions: %s universe load failed: %s", mode, exc)
        return set()


def _junction_score(rec: dict, pb: dict, cons: dict) -> float:
    """Blend the three legs into one 0-100-ish score (configured weights)."""
    sepa = float(rec.get("score") or 0)                       # 0-100 SEPA composite
    pbs = min(float(pb.get("score") or 0), 100.0)             # pullback actionability
    pers = float(cons.get("persistence_pct") or 0)            # 0-100 rank persistence
    return round(W_SEPA * sepa + W_PULLBACK * pbs + W_PERSIST * pers, 1)


def compute(top_n: int = TOP_N) -> dict:
    """Find the cross junctions — pure derivation of the latest scan + leaderboard."""
    t0 = time.time()
    latest = sepa_scanner.load_latest() or {}
    rows = latest.get("all_results") or []
    by_sym = {r.get("symbol"): r for r in rows if r.get("symbol")}

    # ── 1) SEPA leg — the qualifier/candidate list (book p.79) ───────────────
    sepa_syms = {s for s, r in by_sym.items() if r.get("is_candidate")}

    # ── 2) Consistency leg — rank persistence from the leaderboard history ───
    lb = leaderboard.leaderboard(n=300, lookback_days=LOOKBACK_DAYS)
    cons_map = {l["symbol"]: l for l in (lb.get("leaders") or [])}
    base = {
        s for s in sepa_syms
        if (cons_map.get(s, {}).get("appearances", 0) >= MIN_APPEARANCES
            and cons_map.get(s, {}).get("persistence_pct", 0) >= PERSISTENCE_FLOOR)
    }

    # ── 3) Pullback leg — S&P 500 first, Russell 1000 fallback ───────────────
    sp500 = _universe_set("sp500")
    russell = _universe_set("russell1000")

    _memo: dict = {}
    def _eval(sym):
        if sym in _memo:
            return _memo[sym]
        try:
            r = pullback_ma._evaluate_row(by_sym.get(sym))
        except Exception:
            r = None
        _memo[sym] = r
        return r

    junctions: dict = {}
    for s in base:
        if s in sp500:
            pb = _eval(s)
            if pb:
                junctions[s] = pb
    universe_used = "sp500"
    if len(junctions) < MIN_SP500_RESULTS:
        for s in base:
            if s in russell and s not in junctions:
                pb = _eval(s)
                if pb:
                    junctions[s] = pb
                    universe_used = "sp500+russell1000"

    # ── 4) Build rows: full candidate (for the chips) + junction metrics ─────
    out = []
    for s, pb in junctions.items():
        rec = by_sym[s]
        c = cons_map.get(s, {})
        out.append({
            **rec,                                            # full SEPA candidate row -> all the chips
            "junction_score": _junction_score(rec, pb, c),
            "junction_universe": "sp500" if s in sp500 else "russell1000",
            "pullback": {
                "pct_from_ma50": pb.get("pct_from_ma50"),
                "pullback_pct": pb.get("pullback_pct"),
                "band": pb.get("pullback_band"),
                "vol_ratio": pb.get("vol_ratio"),
                "vol_healthy": pb.get("vol_healthy"),
                "score": round(min(float(pb.get("score") or 0), 100.0), 1),
            },
            "consistency": {
                "persistence_pct": c.get("persistence_pct"),
                "appearances": c.get("appearances"),
                "current_rank": c.get("current_rank"),
                "best_rank": c.get("best_rank"),
                "rank_range": c.get("rank_range"),
                "flag": c.get("flag"),
            },
        })

    out.sort(key=lambda r: -(r["junction_score"] or 0))
    out = out[: max(0, top_n)]

    return {
        "generated_at": int(time.time()),
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_sec": round(time.time() - t0, 2),
        "rows": out,
        "count": len(out),
        "universe_used": universe_used,
        "sepa_count": len(sepa_syms),
        "consistent_count": len(base),
        "scans_in_window": lb.get("scans_in_window", 0),
        "scan_generated_at": latest.get("generated_at"),
        "config": {
            "lookback_days": LOOKBACK_DAYS,
            "min_appearances": MIN_APPEARANCES,
            "persistence_floor": PERSISTENCE_FLOOR,
            "min_sp500_results": MIN_SP500_RESULTS,
            "weights": {"sepa": W_SEPA, "pullback": W_PULLBACK, "persistence": W_PERSIST},
        },
        "disclaimer": "Confluence screen, not advice or a forecast.",
    }


# ── In-process cache (the Leaderboard section hits this) ─────────────────────
_CACHE: dict = {"at": 0.0, "data": None}
_TTL_SEC = 300


def get_cross_junctions(force: bool = False) -> dict:
    now = time.time()
    if not force and _CACHE["data"] is not None and (now - _CACHE["at"]) < _TTL_SEC:
        return _CACHE["data"]
    data = compute()
    _CACHE.update(at=now, data=data)
    return data
