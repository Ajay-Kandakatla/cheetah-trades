"""📅 Long Term — the FACTS mapping (spec §3.4, WP-DATA, 2026-11-12). PURE.

Ajay 2026-11-12: "Yeah I wanna find out the ones that are actually great in
fundamentals and growth and sales and no debt but not growing in price action
yet.."

`build(sources, saved, seed)` turns one weekly read (`sources.load_all`) into
the shape `criteria` / `notices` / the run doc consume:

  {"session", "sources": {key: {ok, reason, as_of, n}},
   "names": {SYM: {symbol, name, sector, stage, stage_label, stage_bar_date, close,
                   close_date, sales_tier, sales_yoy_pct, sales_prior_yoy_pct,
                   sales_q_end, sales_read_on, in: [source keys]}},
   "categories": {cat: {ok, reason, population: [cand], lookup: {SYM: cand}}}}
  cand = {"symbol", "sector", "values": {... the keys criteria.py reads ...}}

The `values_*` mappers are the ONE place a source row becomes a category's
values; the baseline script (`scripts/long_term_list_baseline_2026_11_12.py`)
maps the 11-12 dumps through these same functions. A value the source did not
give is None (criteria reads it "unknown", never a pass, never a fail).
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from long_term_list import constants as C

ET = ZoneInfo("America/New_York")

# which sources each category needs whole (any not ok -> the category is not read)
CATEGORY_SOURCES = {
    "s2_growth": ("scan",),
    "capital_quality": ("scan",),
    "undervalue": ("undervalue", "scan"),
    "bonde": ("scan",),
    "fallen_growers": ("fallen",),
    "hot": ("hottest",),
    "quiet_strong": ("longterm", "frames", "research"),
    "accel_after_fall": ("research", "frames", "caps"),
    "pankaj": ("frames",),
}
SOURCE_META = ("ok", "reason", "as_of", "n")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _f(v) -> Optional[float]:
    if isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _g(d, *path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _bool(v) -> Optional[bool]:
    return v if isinstance(v, bool) else None


def _int(v) -> Optional[int]:
    x = _f(v)
    return int(x) if x is not None else None


def read_on(cached_at) -> Optional[str]:
    """ET date of a research `cached_at` epoch."""
    x = _f(cached_at)
    if x is None:
        return None
    try:
        return datetime.fromtimestamp(x, tz=ET).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def sales_facts(rrow: Optional[dict]) -> dict:
    """Sales tier / y/y / prior / accelerating from a research row, with the
    newest quarter's END (`q_end_series[0]`, decision_snapshot only) and the
    cache read date. Missing -> None (never invented)."""
    r = rrow if isinstance(rrow, dict) else {}
    sa = r.get("sales") if isinstance(r.get("sales"), dict) else {}
    ends = r.get("q_end_series")
    q_end = ends[0] if isinstance(ends, (list, tuple)) and ends and ends[0] else None
    return {"sales_tier": sa.get("tier") or None,
            "sales_yoy_pct": _f(sa.get("growth_yoy_pct")),
            "sales_prior_yoy_pct": _f(sa.get("prior_yoy_pct")),
            "sales_accelerating": _bool(sa.get("accelerating")),
            "sales_q_end": str(q_end)[:10] if q_end else None,
            "sales_read_on": read_on(r.get("cached_at"))}


def scan_stage(row: Optional[dict]) -> Optional[int]:
    return _int(_g(row, "stage", "stage"))


# ---------------------------------------------------------------------------
# the values mappers — one per category (keys = criteria.py's docstring)
# ---------------------------------------------------------------------------
def values_s2(row: Optional[dict], stage: Optional[int] = None) -> dict:
    """🚀 from a scan row. `stage` = the closed-bar stage when read, else the
    scan row's own (equal after the 16:30 re-rate)."""
    r = row or {}
    st = stage if stage is not None else scan_stage(r)
    return {"qualifier": _bool(r.get("qualifier")), "stage": st,
            "sales_tier": _g(r, "fundamentals", "sales", "tier"),
            "sales_accelerating": _bool(_g(r, "fundamentals", "sales", "accelerating")),
            "c_strong_q_eps": _bool(_g(r, "fundamentals", "checks", C.S2_EPS_CHECKS[0])),
            "a_strong_y_eps": _bool(_g(r, "fundamentals", "checks", C.S2_EPS_CHECKS[1])),
            "rs_rank": _f(r.get("rs_rank")), "scan_score": _f(r.get("score"))}


def values_cq(row: Optional[dict], grade: Optional[str] = None) -> dict:
    """💎 from a scan row's moat components (+ the growth board's 💎 grade, info)."""
    r = row or {}
    comp = _g(r, "moat", "components") or {}
    return {"qualifier": _bool(r.get("qualifier")),
            "roe_pct": _f(_g(comp, "profitability", "roe_pct")),
            "fcf_margin_pct": _f(_g(comp, "fcf", "fcf_margin_pct")),
            "net_debt_ebitda": _f(_g(comp, "capital", "net_debt_ebitda")),
            "cq_grade": grade or None,
            "moat_score": _f(_g(r, "moat", "score")), "scan_score": _f(r.get("score"))}


def values_bonde(row: Optional[dict]) -> dict:
    """📈 from a scan row's `buy_verdict.bonde`."""
    r = row or {}
    return {"qualifier": _bool(r.get("qualifier")),
            "bonde_tier": _g(r, "buy_verdict", "bonde", "tier"),
            "bonde_score": _f(_g(r, "buy_verdict", "bonde", "score")),
            "scan_score": _f(r.get("score"))}


def floor_ok_from_scan(row: Optional[dict]) -> Optional[bool]:
    """The 🏷️ liquidity floor on a scan row (board.tile_metrics + passes_liquidity)."""
    from chart_maps import board as B
    if not isinstance(row, dict) or not row:
        return None
    return bool(B.passes_liquidity(B.tile_metrics(row).get("avg_turnover"), C.FLOOR_TIER))


def values_uv(passed: Optional[dict] = None, snap: Optional[dict] = None,
              scan_row: Optional[dict] = None) -> dict:
    """🏷️ — a row on the vs-peers list (`undervalue_peers.build` passed), else
    the name's own research snapshot through the SAME pure helpers
    (`ttm_revenue`, `q_yoy_pct`, `ttm_growth_pct`) with `on_list` False. A
    snapshot the vs-peers funnel would not read (no snapshot, or yfinance-sourced
    = currency unverified) leaves the fundamentals None."""
    from chart_maps import undervalue_peers as UVP
    if isinstance(passed, dict):
        return {"ttm_revenue": _f(passed.get("ttm_revenue")),
                "q_yoy_pct": _f(passed.get("q_yoy_pct")),
                "ttm_growth_pct": _f(passed.get("ttm_growth_pct")),
                "on_list": True, "floor_ok": _bool(passed.get("floor_ok")),
                "ratio": _f(passed.get("ratio"))}
    out = {"ttm_revenue": None, "q_yoy_pct": None, "ttm_growth_pct": None,
           "on_list": False, "floor_ok": floor_ok_from_scan(scan_row), "ratio": None}
    if isinstance(snap, dict) and snap.get("_source") != "yfinance":
        rev, per = snap.get("rev_q_series"), snap.get("q_period_series")
        out.update(ttm_revenue=_f(UVP.ttm_revenue(rev, per, 0)), q_yoy_pct=_f(UVP.q_yoy_pct(snap)),
                   ttm_growth_pct=_f(UVP.ttm_growth_pct(rev, per)))
    return out


def values_fallen(row: Optional[dict]) -> dict:
    """📉 from a fallen row (`sources.read_fallen`, or a served tile's `fallen` block)."""
    r = row or {}
    sales = r.get("sales") if isinstance(r.get("sales"), dict) else {}
    return {"pct_below_high": _f(r.get("pct_below")), "pct_above_low": _f(r.get("pct_above_low")),
            "sales_yoy_pct": _f(sales.get("yoy_pct")),
            "pair_blanked": bool(sales.get("pair_blanked")),
            "floor_ok": _bool(r.get("floor_ok")),
            "in_served_pool": r.get("in_served_pool") is True}


def values_hot(row: Optional[dict]) -> dict:
    """🔥 from a Hottest name row."""
    r = row or {}
    return {"sales_tier": r.get("sales_tier") or None, "q_eps_yoy": _f(r.get("q_eps_yoy")),
            "ret_21d": _f(r.get("ret_21d")),
            "served": (r.get("served") is True) if r else None}


def values_quiet(lt_row: Optional[dict], bar: Optional[dict], rrow: Optional[dict],
                 scan_row: Optional[dict]) -> dict:
    """🌱 from the long-term row (`m.*`, `score`), the closed-bar read, the
    research sales tier and the scan row's net debt / EBITDA (info)."""
    m = _g(lt_row, "m") or {}
    sc = _g(lt_row, "score") or {}
    b = bar or {}
    return {"stage": _int(b.get("stage")), "score": _f(sc.get("score")),
            "score_ranked": _bool(sc.get("ranked")) if lt_row else None,
            "net_profit": _f(m.get("net_profit")), "ocf": _f(m.get("ocf")),
            "opm": _f(m.get("opm")), "sales_cagr": _f(m.get("sales_cagr")),
            "profit_cagr": _f(m.get("profit_cagr")), "liab_to_equity": _f(m.get("de")),
            "sales_tier": sales_facts(rrow)["sales_tier"],
            "dollar_vol_50": _f(b.get("dollar_vol_50")),
            "pct_below_high": _f(b.get("pct_below_high")),
            "net_debt_ebitda": _f(_g(scan_row, "moat", "components", "capital", "net_debt_ebitda"))}


def values_accel(rrow: Optional[dict], bar: Optional[dict], cap, lt_row: Optional[dict]) -> dict:
    """🔄 from the research sales block, the closed-bar read, the cache-only
    market cap and the long-term net profit (info)."""
    sa = _g(rrow, "sales") or {}
    b = bar or {}
    return {"market_cap": _f(cap), "sales_tier": sa.get("tier") or None,
            "sales_accelerating": _bool(sa.get("accelerating")),
            "growth_yoy_pct": _f(sa.get("growth_yoy_pct")),
            "prior_yoy_pct": _f(sa.get("prior_yoy_pct")),
            "pct_below_high": _f(b.get("pct_below_high")),
            "pct_above_low": _f(b.get("pct_above_low")),
            "stage": _int(b.get("stage")), "dollar_vol_50": _f(b.get("dollar_vol_50")),
            "net_profit": _f(_g(lt_row, "m", "net_profit"))}


def values_pankaj(entry: Optional[dict], bar: Optional[dict]) -> dict:
    """🧭 his tier / ZT / zones (from the seed) + the closed close."""
    e = entry or {}
    b = bar or {}
    return {"close": _f(b.get("close")), "close_date": b.get("close_date"),
            "zones": e.get("zones") or {}, "tier": e.get("tier"), "zt": e.get("zt")}


def cand(symbol: str, sector, values: dict) -> dict:
    return {"symbol": symbol, "sector": sector or None, "values": values}


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def _src(sources: dict, key: str) -> dict:
    s = (sources or {}).get(key)
    return s if isinstance(s, dict) and s.get("ok") is True else {}


def _meta(sources: dict) -> dict:
    from long_term_list import sources as SRC
    out = {}
    for k in SRC.SOURCE_KEYS:
        s = (sources or {}).get(k)
        if not isinstance(s, dict):
            out[k] = {"ok": False, "reason": "not read", "as_of": None, "n": 0}
        else:
            out[k] = {m: s.get(m) for m in SOURCE_META}
            out[k]["ok"] = s.get("ok") is True
    return out


def build(sources: dict, saved, seed=None) -> dict:
    """The facts of one weekly read. `saved` = the seed's symbols (109)."""
    from long_term_list import seed as SEED
    from long_term_list import sources as SRC

    saved = [str(s).strip().upper() for s in (saved or []) if str(s).strip()]
    meta = _meta(sources)
    scan, uv, fal, hot = (_src(sources, k) for k in ("scan", "undervalue", "fallen", "hottest"))
    lt, res, fr, caps_s, gb = (_src(sources, k) for k in ("longterm", "research", "frames",
                                                            "caps", "growth_board"))
    scan_rows = scan.get("rows") or {}
    passed = {p["symbol"]: p for p in (uv.get("passed") or [])}
    uv_snaps = uv.get("snaps") or {}
    fal_rows = fal.get("rows") or {}
    hot_rows = hot.get("rows") or {}
    lt_rows = lt.get("rows") or {}
    sector_map = lt.get("sector_map") or {}
    r_rows = res.get("rows") or {}
    bars = fr.get("reads") or {}
    caps = caps_s.get("caps") or {}
    grades = gb.get("grades") or {}
    pk = SEED.pankaj_entries(seed) if seed else {}

    def stage_of(s):
        return _int((bars.get(s) or {}).get("stage"))

    def uv_snap(s):
        return uv_snaps.get(s) or r_rows.get(s)

    makers = {
        "s2_growth": lambda s: cand(s, _g(scan_rows.get(s), "sector"),
                                    values_s2(scan_rows.get(s), stage_of(s))),
        "capital_quality": lambda s: cand(s, _g(scan_rows.get(s), "sector"),
                                          values_cq(scan_rows.get(s), grades.get(s))),
        "bonde": lambda s: cand(s, _g(scan_rows.get(s), "sector"), values_bonde(scan_rows.get(s))),
        "undervalue": lambda s: cand(s, (passed.get(s) or {}).get("sector")
                                     or _g(scan_rows.get(s), "sector"),
                                     values_uv(passed.get(s), uv_snap(s), scan_rows.get(s))),
        "fallen_growers": lambda s: cand(s, (fal_rows.get(s) or {}).get("sector"),
                                         values_fallen(fal_rows.get(s))),
        "hot": lambda s: cand(s, (hot_rows.get(s) or {}).get("group"), values_hot(hot_rows.get(s))),
        "quiet_strong": lambda s: cand(s, (lt_rows.get(s) or {}).get("sector"),
                                       values_quiet(lt_rows.get(s), bars.get(s), r_rows.get(s),
                                                    scan_rows.get(s))),
        "accel_after_fall": lambda s: cand(s, _g(scan_rows.get(s), "sector") or sector_map.get(s),
                                           values_accel(r_rows.get(s), bars.get(s), caps.get(s),
                                                        lt_rows.get(s))),
    }
    populations = {
        "s2_growth": list(scan.get("candidates") or []),
        "capital_quality": list(scan.get("candidates") or []),
        "bonde": list(scan.get("candidates") or []),
        "undervalue": list(passed),
        "fallen_growers": list(fal.get("pool") or []),
        "hot": [s for s, r in hot_rows.items() if r.get("served")],
        "quiet_strong": [s for s in SRC.quiet_pre(lt) if s in lt_rows],
        "accel_after_fall": SRC.accel_pre(res),
    }
    cats: dict = {}
    for cat in C.SCREENED_KEYS:
        bad = [k for k in CATEGORY_SOURCES[cat] if not meta[k]["ok"]]
        reason = ("not read: " + "; ".join(f"{k} — {meta[k]['reason']}" for k in bad)) if bad else None
        mk = makers[cat]
        cats[cat] = {"ok": not bad, "reason": reason,
                     "population": [] if bad else [mk(s) for s in populations[cat]],
                     "lookup": {s: mk(s) for s in saved}}
    bad = [k for k in CATEGORY_SOURCES[C.PANKAJ_KEY] if not meta[k]["ok"]]
    cats[C.PANKAJ_KEY] = {
        "ok": not bad,
        "reason": ("not read: " + "; ".join(f"{k} — {meta[k]['reason']}" for k in bad)) if bad else None,
        "population": [],
        "lookup": {s: {"symbol": s, "sector": None,
                       "values": values_pankaj(pk[s], bars.get(s))} for s in pk}}

    names = {}
    for s in saved:
        row = scan_rows.get(s) or {}
        b = bars.get(s) or {}
        sf = sales_facts(r_rows.get(s))
        found = [k for k, hit in (
            ("scan", s in scan_rows), ("undervalue", s in passed or s in uv_snaps),
            ("fallen", s in fal_rows), ("hottest", s in hot_rows), ("longterm", s in lt_rows),
            ("research", s in r_rows), ("frames", b.get("close") is not None),
            ("caps", caps.get(s) is not None), ("growth_board", s in grades)) if hit]
        names[s] = {"symbol": s,
                    "name": row.get("name") or (fal_rows.get(s) or {}).get("name"),
                    "sector": row.get("sector") or (lt_rows.get(s) or {}).get("sector")
                    or sector_map.get(s),
                    "stage": _int(b.get("stage")), "stage_label": b.get("stage_label"),
                    "stage_bar_date": b.get("stage_bar_date"),
                    "close": _f(b.get("close")), "close_date": b.get("close_date"),
                    "sales_tier": sf["sales_tier"], "sales_yoy_pct": sf["sales_yoy_pct"],
                    "sales_prior_yoy_pct": sf["sales_prior_yoy_pct"],
                    "sales_q_end": sf["sales_q_end"], "sales_read_on": sf["sales_read_on"],
                    "in": found}
    return {"session": (sources or {}).get("session"), "sources": meta, "names": names,
            "categories": cats}
