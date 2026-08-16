"""Chart-ready tiles for the three Chart Maps tabs.

WHY ONE ENDPOINT INSTEAD OF N FETCHES
-------------------------------------
A 24-tile grid assembled client-side is 1 board call + 24 `/sepa/price-bars`
round-trips, and every tile pops in separately. The geometry each tile needs
(which band, which lines, which marker) is also tab-specific, so putting it in
the browser means three different assembly paths in TypeScript. Instead the
server returns ONE uniform tile shape and the frontend renders it dumbly.

THE TILE CONTRACT (identical across tabs)
-----------------------------------------
    symbol, name, href            — where the tile links (SEPA detail + tab)
    bars   [{t,o,h,l,c,v}]        — daily candles, oldest first
    bands  [{kind,lo,hi,label}]   — filled price boxes (base, demand, supply)
    lines  [{price,label,tone}]   — horizontal levels (buy/stop/target/now)
    markers[{date,label,kind}]    — dated vertical marks
    stats  [{k,v}]                — the two or three numbers worth reading
    why    str                    — one line: why this chart is on the board
    theme  str|None               — quantum/nuclear/robotics/ai_semis/ai_infra

WHAT THIS MODULE DOES NOT DO
----------------------------
It never scans. Tabs 1 and 2 read caches that other schedulers fill
(`scanner.load_latest()`, `demand_reentry.cached_or_warm()`) and tab 3 reads a
Mongo ledger that only ever accumulates. A page load can therefore never block
on a 3-minute universe pass — the 524 that took the demand board down on
2026-08-14 came from exactly that mistake.

Not advice. Tab 3 in particular shows what DID happen to a sample of past
setups; it is a study aid, not a forecast.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("chart_maps.board")

TABS = ("vcp", "zones", "winners")

BARS_DEFAULT = 130          # ~6 months of daily bars — a base plus its run-up
BARS_MAX = 400
LIMIT_DEFAULT = 24
LIMIT_MAX = 60

# A VCP is only worth studying once it has actually tightened. vcp.py bands
# tightness as tight ≥70 / developing 40-69 / early <40; "Strong VCP" is the
# top band plus the scanner independently naming VCP as the entry setup.
STRONG_TIGHTNESS = 70

# Winners: the ledger races the measure-rule target against the stop over 21
# bars (patterns/history.py::_grade_pattern). Both touched on one bar counts
# as the stop, so `target_first` is already the pessimistic reading.
WIN_OUTCOME = "target_first"
LOSS_OUTCOME = "stop_first"

DISCLAIMER = ("Study board. Past pattern outcomes are a measured sample of what "
              "happened, not a forecast — position sizing and stops still decide "
              "the result. Not financial advice.")


# ---------------------------------------------------------------------------
# bars
# ---------------------------------------------------------------------------
def _norm_frame(df):
    """Lower-case the OHLCV columns. Returns None when unusable."""
    if df is None or getattr(df, "empty", True):
        return None
    out = df.rename(columns={c: str(c).lower() for c in df.columns})
    if not {"open", "high", "low", "close"} <= set(out.columns):
        return None
    return out


def _row_date(ts) -> str:
    return ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]


def _frame_to_bars(df) -> list[dict]:
    bars: list[dict] = []
    for ts, row in df.iterrows():
        try:
            bars.append({
                "t": _row_date(ts),
                "o": round(float(row["open"]), 4),
                "h": round(float(row["high"]), 4),
                "l": round(float(row["low"]), 4),
                "c": round(float(row["close"]), 4),
                "v": float(row.get("volume") or 0.0),
            })
        except Exception:
            continue
    return bars


def bars_for(symbol: str, days: int = BARS_DEFAULT,
             around: Optional[str] = None, pad_after: int = 25) -> list[dict]:
    """Daily candles for `symbol`.

    `around` centres the window on a dated event (a pattern confirmation),
    keeping `days` bars of run-up before it and `pad_after` bars after so the
    outcome is visible. Without it, the trailing `days` bars.

    A date not in the frame falls back to the tail rather than returning empty
    — a missing session (holiday, halt, a ledger date recorded off-calendar)
    should degrade to a usable chart, not a blank tile.
    """
    from sepa import prices
    try:
        df = _norm_frame(prices.load_prices(symbol.upper()))
    except Exception as exc:
        log.debug("chart-maps: bars %s failed: %s", symbol, exc)
        return []
    if df is None:
        return []

    days = max(20, min(int(days or BARS_DEFAULT), BARS_MAX))
    if around:
        dates = [_row_date(d) for d in df.index]
        try:
            i = dates.index(str(around)[:10])
        except ValueError:
            i = -1
        if i >= 0:
            lo = max(0, i - days)
            hi = min(len(df), i + max(0, int(pad_after)) + 1)
            return _frame_to_bars(df.iloc[lo:hi])
    return _frame_to_bars(df.tail(days))


# ---------------------------------------------------------------------------
# shared tile helpers
# ---------------------------------------------------------------------------
def _name_for(symbol: str) -> Optional[str]:
    try:
        from sepa import company_names
        return company_names.name_for(symbol)
    except Exception:
        return None


def _theme(symbol: str) -> Optional[str]:
    try:
        from sepa import universe as U
        return U.theme_for(symbol)
    except Exception:
        return None


def _num(v) -> Optional[float]:
    """Coerce to a finite float, else None. Guards NaN reaching JSON."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _href(symbol: str, tab: str) -> str:
    return f"/sepa/{symbol.upper()}?tab={tab}"


def _sort_key(tile: dict, themes_first: bool):
    """Theme names lead when asked (Ajay's standing rule that any board leads
    with the AI-ecosystem winners), then the tab's own metric descending."""
    rank = 0 if (themes_first and tile.get("theme")) else 1
    return (rank, -(tile.get("_score") or 0.0))


# Spare tiles fetched beyond `limit`, to cover symbols whose price frame turns
# out to be missing or too short to chart.
BAR_BUFFER = 6
BAR_WORKERS = 8


def _finish(tiles: list[dict], limit: int, themes_first: bool, days: int) -> list[dict]:
    """Rank on metadata, THEN load bars for only the tiles that will be shown.

    Ordering matters for latency, not just tidiness. Ranking after fetching
    meant loading price frames for every match — 265 names to display 24. On a
    cold price cache that is minutes, and minutes is a 524. Sorting first caps
    the work at `limit + BAR_BUFFER` frames regardless of how many matched.
    """
    tiles.sort(key=lambda t: _sort_key(t, themes_first))
    short = tiles[:limit + BAR_BUFFER]
    _attach_bars(short, days)
    out = [t for t in short if t.get("bars")][:limit]
    for t in out:
        t.pop("_score", None)
        t.pop("_bars", None)
    return out


def _attach_bars(tiles: list[dict], days: int) -> None:
    """Fill `bars` on each tile, concurrently. Mutates in place.

    Time-boxed by the pool rather than per-task: every miss simply leaves
    `bars` empty and the tile is dropped, so a slow or delisted name costs one
    empty slot instead of the whole board.
    """
    if not tiles:
        return
    from concurrent.futures import ThreadPoolExecutor

    def _one(t: dict):
        spec = t.get("_bars") or {}
        try:
            t["bars"] = bars_for(t["symbol"],
                                 days=spec.get("days") or days,
                                 around=spec.get("around"),
                                 pad_after=spec.get("pad_after", 25))
        except Exception as exc:
            log.debug("chart-maps: bars %s failed: %s", t.get("symbol"), exc)
            t["bars"] = []

    with ThreadPoolExecutor(max_workers=BAR_WORKERS) as pool:
        list(pool.map(_one, tiles))


# ---------------------------------------------------------------------------
# tab 1 — strong VCP
# ---------------------------------------------------------------------------
def _is_strong_vcp(row: dict) -> bool:
    """VCP named as the entry setup AND the base actually tight.

    Both halves matter: `entry_setup.type` is the scanner's own read of what
    this chart IS, while tightness says the contractions have converged.
    Either alone admits charts that do not teach the pattern.
    """
    setup = row.get("entry_setup") or {}
    if (setup.get("type") or "").upper() != "VCP":
        return False
    vcp = row.get("vcp") or {}
    t = _num(vcp.get("tightness"))
    return t is not None and t >= STRONG_TIGHTNESS


def vcp_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
              themes_first: bool = True, min_tightness: int = STRONG_TIGHTNESS) -> dict:
    from sepa import scanner

    scan = scanner.load_latest()
    if not scan:
        return {"tiles": [], "note": "no SEPA scan on disk yet — run a scan first"}

    rows = scan.get("all_results") or scan.get("candidates") or []
    picked = []
    for r in rows:
        if not _is_strong_vcp(r):
            continue
        v = r.get("vcp") or {}
        if (_num(v.get("tightness")) or 0) < min_tightness:
            continue
        picked.append(r)

    tiles = []
    for r in picked:
        sym = (r.get("symbol") or "").upper()
        if not sym:
            continue
        v = r.get("vcp") or {}
        setup = r.get("entry_setup") or {}
        base_hi, base_lo = _num(v.get("base_high")), _num(v.get("base_low"))
        pivot = _num(v.get("pivot_buy_price")) or _num(setup.get("pivot"))
        stop = _num(v.get("suggested_stop")) or _num(setup.get("stop"))
        tight = _num(v.get("tightness"))

        bands = []
        if base_hi is not None and base_lo is not None and base_hi > base_lo:
            bands.append({"kind": "base", "lo": base_lo, "hi": base_hi,
                          "label": f"base {v.get('base_bars') or '?'}d"})
        lines = []
        if pivot is not None:
            lines.append({"price": pivot, "label": "PIVOT", "tone": "buy"})
        if stop is not None:
            lines.append({"price": stop, "label": "STOP", "tone": "stop"})

        drivers = [d for d in (v.get("tightness_drivers") or []) if d]
        stats = [{"k": "Tightness", "v": f"{int(tight)}" if tight is not None else "—"},
                 {"k": "Contractions", "v": str(v.get("n_contractions") or "—")},
                 {"k": "Final", "v": (f"{_num(v.get('final_contraction_pct')):.1f}%"
                                      if _num(v.get('final_contraction_pct')) is not None else "—")}]
        rs = _num(r.get("rs_rank"))
        if rs is not None:
            stats.append({"k": "RS", "v": str(int(rs))})

        tiles.append({
            "symbol": sym,
            "name": r.get("name") or _name_for(sym),
            "href": _href(sym, "setup"),
            "bars": [],
            "bands": bands,
            "lines": lines,
            "markers": [],
            "stats": stats,
            "why": " · ".join(drivers) if drivers else "VCP base tightening",
            "theme": _theme(sym),
            "badges": _vcp_badges(r),
            "_score": tight or 0.0,
        })
    return {"tiles": _finish(tiles, limit, themes_first, days),
            "matched": len(picked),
            "scanned": len(rows),
            "scan_generated_at": scan.get("generated_at")}


def _vcp_badges(row: dict) -> list[dict]:
    """Tier badges. `is_candidate` is the WATCHLIST tier (trend + liquidity,
    p.79), NOT a buy — labelling it 'buyable' is the exact mislabel the
    2026-05-28 book-alignment pass fixed, so the words stay distinct."""
    out = []
    if row.get("is_buyable"):
        out.append({"text": "Buyable", "tone": "good"})
    elif row.get("setup_ready"):
        out.append({"text": "Setup ready", "tone": "warn"})
    elif row.get("is_candidate"):
        out.append({"text": "Qualifier", "tone": "muted"})
    if (row.get("vcp") or {}).get("volume_drying"):
        out.append({"text": "Vol drying", "tone": "good"})
    return out


# ---------------------------------------------------------------------------
# tab 2 — pullbacks into demand
# ---------------------------------------------------------------------------
def zone_tiles(limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
               universe: str = "sp1500_plus", themes_first: bool = True) -> dict:
    from supply_demand import demand_reentry as D

    data = D.cached_or_warm(universe, limit=LIMIT_MAX)
    if data.get("warming"):
        # Deliberately non-blocking: the board warms in a background thread and
        # the page polls. Never wait here (see the 2026-08-14 524).
        return {"tiles": [], "warming": True,
                "universe_key": data.get("universe_key") or universe,
                "note": "scanning for demand-zone pullbacks…"}

    rows = [r for r in (data.get("rows") or []) if r.get("is_reentry")]
    tiles = []
    for r in rows:
        sym = (r.get("symbol") or "").upper()
        if not sym:
            continue
        plan = r.get("plan") or {}
        zone = r.get("entry_zone") or {}

        bands = []
        z_lo, z_hi = _num(zone.get("lo")), _num(zone.get("hi"))
        if z_lo is not None and z_hi is not None:
            bands.append({"kind": "demand", "lo": z_lo, "hi": z_hi, "label": "demand"})
        for s in (r.get("supply_zones") or [])[:2]:
            s_lo, s_hi = _num(s.get("lo")), _num(s.get("hi"))
            if s_lo is not None and s_hi is not None:
                bands.append({"kind": "supply", "lo": s_lo, "hi": s_hi, "label": "supply"})

        lines = []
        for key, label, tone in (("entry_ref", "BUY", "buy"),
                                 ("stop", "STOP", "stop"),
                                 ("target", "TARGET", "target")):
            p = _num(plan.get(key))
            if p is not None:
                lines.append({"price": p, "label": label, "tone": tone})

        rr = _num(plan.get("rr"))
        be = _num(r.get("breakeven_win_pct"))
        liq = r.get("liquidity") or {}
        stats = [{"k": "R:R", "v": f"{rr:.1f}R" if rr is not None else "—"},
                 {"k": "Break-even", "v": f"{be:.0f}%" if be is not None else "—"},
                 {"k": "Liquidity", "v": (liq.get("tier") or "—")},
                 {"k": "Back in", "v": (f"{r.get('bars_since_above')}d"
                                        if r.get("bars_since_above") is not None else "—")}]

        fell = _num(r.get("fell_from_pct"))
        why = ((r.get("verdict") or {}).get("entry_read")
               or (f"pulled back {fell:.0f}% into a demand zone it had left"
                   if fell is not None else "back inside a demand zone"))

        tiles.append({
            "symbol": sym,
            "name": r.get("name") or _name_for(sym),
            "href": _href(sym, "supply"),
            "bars": [],
            "bands": bands,
            "lines": lines,
            "markers": [],
            "stats": stats,
            "why": why,
            "theme": _theme(sym),
            "badges": _zone_badges(r),
            "_score": rr or 0.0,
        })
    return {"tiles": _finish(tiles, limit, themes_first, days),
            "matched": len(rows),
            "universe_key": data.get("universe_key"),
            "universe_label": data.get("universe_label"),
            "scanned": data.get("scanned"),
            "generated_at": data.get("generated_at")}


def _zone_badges(r: dict) -> list[dict]:
    out = []
    v = (r.get("verdict") or {}).get("state")
    if v:
        out.append({"text": str(v).title(),
                    "tone": {"enter": "good", "watch": "warn"}.get(str(v).lower(), "muted")})
    sweep = (r.get("sweep") or {}).get("state")
    if sweep == "swept":
        out.append({"text": "Liquidity swept", "tone": "good"})
    rating = (r.get("venues") or {}).get("rating")
    if rating:
        out.append({"text": f"Dark {rating}", "tone": "muted"})
    return out


# ---------------------------------------------------------------------------
# tab 3 — previously winning patterns
# ---------------------------------------------------------------------------
def _pattern_label(p: str) -> str:
    return (p or "").replace("_", " ").title()


def winner_tiles(limit: int = LIMIT_DEFAULT, days: int = 90,
                 pattern: Optional[str] = None) -> dict:
    """Past setups that reached their measure-rule target before their stop.

    HONESTY RULES BAKED IN HERE
    ---------------------------
    * The record reports wins AND the stop-first losses from the same raced
      denominator. A winners-only wall is a highlight reel.
    * Observations already at or past target when recorded are EXCLUDED: the
      move had happened before the ledger saw it, so the chart teaches nothing
      about the entry. Measured 2026-08-15: 8 of 117 raced observations.
    * Patterns are never ranked against each other by raw win-%. Their stop
      brackets differ roughly 2x (a double bottom's stop sits far below entry,
      a cup's handle stop is tight), which is exactly the comparison the
      2026-07-10 audit found broken.
    """
    from patterns import history

    coll = history._coll()
    if coll is None:
        return {"tiles": [], "note": "pattern ledger unavailable"}

    q = {"kind": "pattern", "status": "confirmed",
         "outcome": {"$in": [WIN_OUTCOME, LOSS_OUTCOME]}}
    if pattern:
        q["pattern"] = pattern
    try:
        raced = list(coll.find(q, {"_id": 0}))
    except Exception as exc:
        log.warning("chart-maps: winners query failed: %s", exc)
        return {"tiles": [], "note": "pattern ledger unavailable"}

    def _already_past(o: dict) -> bool:
        t, c = _num(o.get("target")), _num(o.get("obs_close"))
        return t is not None and c is not None and c >= t

    usable = [o for o in raced if not _already_past(o)]
    wins = [o for o in usable if o.get("outcome") == WIN_OUTCOME]
    losses = [o for o in usable if o.get("outcome") == LOSS_OUTCOME]
    wins.sort(key=lambda o: str(o.get("et_date") or ""), reverse=True)

    tiles = []
    for i, o in enumerate(wins):
        sym = (o.get("symbol") or "").upper()
        confirm = str(o.get("confirmed_date") or o.get("et_date") or "")[:10]
        if not sym or not confirm:
            continue
        neck, tgt, stp = _num(o.get("neckline")), _num(o.get("target")), _num(o.get("stop"))
        lines = []
        if neck is not None:
            lines.append({"price": neck, "label": "BREAKOUT", "tone": "buy"})
        if tgt is not None:
            lines.append({"price": tgt, "label": "TARGET", "tone": "target"})
        if stp is not None:
            lines.append({"price": stp, "label": "STOP", "tone": "stop"})

        gain = _num(o.get("max_gain_pct"))
        bto = o.get("bars_to_outcome")
        stats = [{"k": "Pattern", "v": _pattern_label(o.get("pattern"))},
                 {"k": "Confirmed", "v": confirm},
                 {"k": "Best gain", "v": f"+{gain:.1f}%" if gain is not None else "—"},
                 {"k": "Bars to target", "v": str(bto) if bto is not None else "—"}]
        rs = _num(o.get("rs_rank"))
        if rs is not None:
            stats.append({"k": "RS then", "v": str(int(rs))})

        tiles.append({
            "symbol": sym,
            "name": _name_for(sym),
            "href": _href(sym, "breakout"),
            "bars": [],
            # Enough bars after the confirmation to show the resolution.
            "_bars": {"around": confirm,
                      "pad_after": int(o.get("bars_to_outcome") or 21) + 12},
            "bands": [],
            "lines": lines,
            "markers": [{"date": confirm, "label": "confirmed", "kind": "confirm"}],
            "stats": stats,
            "why": (f"{_pattern_label(o.get('pattern'))} — hit target in "
                    f"{bto} bars" if bto is not None
                    else f"{_pattern_label(o.get('pattern'))} — reached target"),
            "theme": _theme(sym),
            "badges": [{"text": "Target hit", "tone": "good"}],
            "pattern": o.get("pattern"),
            # Already sorted newest-first; a descending score preserves that
            # order through _finish's shared sort.
            "_score": float(len(wins) - i),
        })

    return {"tiles": _finish(tiles, limit, themes_first=False, days=days),
            "record": _winner_record(usable, wins, losses),
            "excluded_already_past_target": len(raced) - len(usable),
            "patterns": sorted({o.get("pattern") for o in usable if o.get("pattern")})}


def _winner_record(usable: list, wins: list, losses: list) -> dict:
    """Per-pattern wins vs stop-firsts. Never a cross-pattern ranking."""
    by: dict[str, dict] = {}
    for o in usable:
        p = o.get("pattern") or "unknown"
        rec = by.setdefault(p, {"pattern": p, "label": _pattern_label(p),
                                "wins": 0, "losses": 0})
        rec["wins" if o.get("outcome") == WIN_OUTCOME else "losses"] += 1
    for rec in by.values():
        n = rec["wins"] + rec["losses"]
        rec["n"] = n
        rec["win_pct"] = round(100.0 * rec["wins"] / n, 1) if n else None
    return {
        "overall": {"wins": len(wins), "losses": len(losses),
                    "n": len(usable),
                    "win_pct": (round(100.0 * len(wins) / len(usable), 1)
                                if usable else None)},
        "by_pattern": sorted(by.values(), key=lambda r: -r["n"]),
        "caveat": ("Wins are target-before-stop within 21 bars. Stop brackets "
                   "differ ~2x between patterns, so these win rates are NOT "
                   "comparable across patterns — read each against its own "
                   "target and stop distance."),
    }


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------
def board(tab: str = "vcp", limit: int = LIMIT_DEFAULT, days: int = BARS_DEFAULT,
          universe: str = "sp1500_plus", themes_first: bool = True,
          pattern: Optional[str] = None) -> dict:
    """One tab's tiles. Never scans; reads caches and the pattern ledger."""
    t = tab if tab in TABS else TABS[0]
    limit = max(1, min(int(limit or LIMIT_DEFAULT), LIMIT_MAX))
    days = max(20, min(int(days or BARS_DEFAULT), BARS_MAX))

    if t == "zones":
        out = zone_tiles(limit, days, universe, themes_first)
    elif t == "winners":
        out = winner_tiles(limit, days=min(days, 120), pattern=pattern)
    else:
        out = vcp_tiles(limit, days, themes_first)

    out["tab"] = t
    out["count"] = len(out.get("tiles") or [])
    out["disclaimer"] = DISCLAIMER
    return out
