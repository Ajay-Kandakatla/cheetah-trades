"""Dynamic day-trade universe — today's liquid, volatile movers.

Replaces the static 10-name DEFAULT_WATCHLIST with a data-driven universe built
from the cached SEPA scan (no extra price-frame loads): every analyzed name
already carries `adr_pct` (Average Daily Range — the day-trade volatility
metric), `last_close`, and `volume.avg_vol_50`. We filter for day-tradeable
liquidity + volatility and rank by profile:

  • aggressive   — highest ADR (the biggest intraday movers), liquid enough to fill.
  • conservative — mega-liquid names with moderate ADR (steadier intraday range).

The BROWSABLE pool is large (~120). The LIVE 1-minute scan must stay bounded —
each symbol is one Massive REST call per 60-second refresh, so scanning the whole
pool live would trip the circuit breaker. `active_movers()` therefore uses ONE
batched bulk snapshot to rank the pool by today's relative volume and returns only
the top ~20 to deep-scan. When the market is closed (no live volume) it falls back
to the pool's top names by the profile sort, so the page is never empty.

Not advice — a liquidity/volatility screen for which names are day-tradeable.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("daytrading.universe")

# ── Day-tradeable filters (our codification — liquidity + volatility) ─────────
PRICE_FLOOR = 5.0                       # avoid sub-$5 noise / hard-to-short names
# Aggressive: big intraday range, liquid enough to fill.
ADR_FLOOR_AGGR        = 4.0             # ADR% ≥ 4 → genuinely moves intraday
DOLLAR_VOL_FLOOR_AGGR = 30_000_000.0    # ≥ $30M/day → fillable
# Conservative: mega-liquid, steadier range (mega-caps that still move).
ADR_FLOOR_CONS        = 2.5
ADR_CAP_CONS          = 9.0             # exclude the wildest names from "steady"
DOLLAR_VOL_FLOOR_CONS = 100_000_000.0   # ≥ $100M/day

UNIVERSE_LIMIT = 120                    # browsable pool size
LIVE_SCAN_CAP  = 20                     # how many to deep-scan live (bounded cost)

_UNIVERSE_TTL = 6 * 60 * 60             # the scan refreshes ~daily
_MOVERS_TTL   = 180                     # today's movers — 3 min intraday

VALID_PROFILES = ("aggressive", "conservative")

# Static fallback if the scan is unavailable (keeps the page working).
FALLBACK = ["TSLA", "NVDA", "COIN", "MSTR", "AMD", "PLTR", "META", "AAPL", "AVGO", "CRWD"]

_uni_cache: dict = {}
_mov_cache: dict = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_profile(profile: Optional[str]) -> str:
    p = (profile or "aggressive").strip().lower()
    return p if p in VALID_PROFILES else "aggressive"


def _dollar_vol(row: dict) -> float:
    vol = row.get("volume") or {}
    avg = vol.get("avg_vol_50")
    close = row.get("last_close")
    return float(avg) * float(close) if (avg and close) else 0.0


def _scan_rows() -> list[dict]:
    try:
        from sepa import scanner
        latest = scanner.load_latest() or {}
        return latest.get("all_results") or latest.get("candidates") or []
    except Exception as exc:
        log.warning("day-universe: scan unavailable: %s", exc)
        return []


def day_trade_universe(profile: str = "aggressive", limit: int = UNIVERSE_LIMIT,
                       force: bool = False) -> dict:
    """The browsable day-trade pool for `profile`, ranked. Cached `_UNIVERSE_TTL`."""
    profile = _norm_profile(profile)
    ck = (profile, limit)
    if not force:
        hit = _uni_cache.get(ck)
        if hit and (time.time() - hit["ts"]) < _UNIVERSE_TTL:
            return hit["data"]

    rows = _scan_rows()
    names: list[dict] = []
    for r in rows:
        adr = r.get("adr_pct")
        close = r.get("last_close")
        if not adr or not close or close < PRICE_FLOOR:
            continue
        dv = _dollar_vol(r)
        if profile == "aggressive":
            if adr < ADR_FLOOR_AGGR or dv < DOLLAR_VOL_FLOOR_AGGR:
                continue
        else:  # conservative
            if adr < ADR_FLOOR_CONS or adr > ADR_CAP_CONS or dv < DOLLAR_VOL_FLOOR_CONS:
                continue
        names.append({
            "symbol": (r.get("symbol") or "").upper(),
            "adr_pct": round(float(adr), 2),
            "dollar_vol": round(dv),
            "last_close": round(float(close), 2),
            "rs_rank": r.get("rs_rank"),
            "avg_vol_50": (r.get("volume") or {}).get("avg_vol_50"),
        })

    # Rank: aggressive → most volatile; conservative → most liquid.
    if profile == "aggressive":
        names.sort(key=lambda n: -n["adr_pct"])
    else:
        names.sort(key=lambda n: -n["dollar_vol"])
    names = names[:limit]

    if not names:
        names = [{"symbol": s, "adr_pct": None, "dollar_vol": None,
                  "last_close": None, "rs_rank": None, "avg_vol_50": None}
                 for s in FALLBACK]

    data = {
        "profile": profile,
        "names": names,
        "n": len(names),
        "as_of": _now_iso(),
        "criteria": (f"ADR ≥ {ADR_FLOOR_AGGR}% · $vol ≥ ${int(DOLLAR_VOL_FLOOR_AGGR/1e6)}M, ranked by ADR"
                     if profile == "aggressive" else
                     f"ADR {ADR_FLOOR_CONS}–{ADR_CAP_CONS}% · $vol ≥ ${int(DOLLAR_VOL_FLOOR_CONS/1e6)}M, ranked by $ volume"),
    }
    _uni_cache[ck] = {"ts": time.time(), "data": data}
    log.info("day-universe[%s]: %d names", profile, len(names))
    return data


def _bulk_snapshot(symbols: list[str]) -> dict:
    """Today's snapshot for `symbols` via Massive's bulk endpoint (≤250/call,
    so we chunk). Returns {SYMBOL: {price, prev_close, change_pct, volume,...}}."""
    out: dict = {}
    if not symbols:
        return out
    try:
        from supply_demand import flow
    except Exception as exc:
        log.warning("day-universe: flow snapshot unavailable: %s", exc)
        return out
    for i in range(0, len(symbols), 250):
        chunk = symbols[i:i + 250]
        try:
            snaps = flow._fetch_massive_bulk(chunk) or {}
            for k, v in snaps.items():
                out[(k or "").upper()] = v
        except Exception as exc:
            log.warning("day-universe: bulk snapshot chunk failed: %s", exc)
    return out


def active_movers(profile: str = "aggressive", top_n: int = LIVE_SCAN_CAP,
                  force: bool = False) -> dict:
    """Today's top movers within the pool — what the LIVE scan should deep-scan.

    One batched bulk snapshot ranks the pool by relative volume × |change|. When
    the market is closed / no snapshot is returned, falls back to the pool's top
    names by the profile sort so the page still shows day-tradeable candidates.
    Cached `_MOVERS_TTL`."""
    profile = _norm_profile(profile)
    ck = (profile, top_n)
    if not force:
        hit = _mov_cache.get(ck)
        if hit and (time.time() - hit["ts"]) < _MOVERS_TTL:
            return hit["data"]

    pool = day_trade_universe(profile)["names"]
    syms = [n["symbol"] for n in pool]
    snaps = _bulk_snapshot(syms)

    movers: list[dict] = []
    for n in pool:
        snap = snaps.get(n["symbol"])
        if not snap:
            continue
        today_vol = snap.get("volume")
        avg = n.get("avg_vol_50")
        rel = round(float(today_vol) / float(avg), 2) if (today_vol and avg) else 0.0
        chg = snap.get("change_pct")
        movers.append({
            "symbol": n["symbol"],
            "adr_pct": n["adr_pct"],
            "rel_vol": rel,
            "change_pct": round(float(chg), 2) if chg is not None else None,
            "last": snap.get("price") or n.get("last_close"),
            "_score": rel * (1.0 + abs(float(chg or 0)) / 100.0),
        })

    live = bool(movers)
    if movers:
        movers.sort(key=lambda m: -m["_score"])
        active = movers[:top_n]
    else:
        # Market closed / no snapshot — show the most day-tradeable names.
        active = [{"symbol": n["symbol"], "adr_pct": n["adr_pct"], "rel_vol": None,
                   "change_pct": None, "last": n.get("last_close")} for n in pool[:top_n]]
    for m in active:
        m.pop("_score", None)

    data = {
        "profile": profile,
        "active": active,
        "symbols": [m["symbol"] for m in active],
        "n": len(active),
        "live": live,                          # True = ranked by today's volume
        "pool_size": len(pool),
        "as_of": _now_iso(),
    }
    _mov_cache[ck] = {"ts": time.time(), "data": data}
    return data
