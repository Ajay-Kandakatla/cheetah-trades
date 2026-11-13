"""📅 Long Term — the list rules as LEGS, each with a KIND (spec §3.5, critique C4).

Pure. A leg reads ONE value from a category's `values` dict (built by
facts.py — WP-DATA) and returns pass / fail / unknown (info legs: "info").
None, or the string "unknown", is never a pass. Every threshold comes from
constants.py; every sentence from words.py.

KIND: fundamental (F) · market (M) · stage (S) · info (I). Only F legs raise ⚠️
on the tab; M legs (and the 🌱/🔄 non-drop stage legs) flip into a neutral
"moved" line; I legs never pass or fail.

The `values` keys each category reads (WP-DATA maps the source rows to these):
  s2_growth        qualifier, stage, sales_tier, sales_accelerating, c_strong_q_eps, a_strong_y_eps,
                   rs_rank, scan_score
  capital_quality  qualifier, roe_pct, fcf_margin_pct, net_debt_ebitda, cq_grade, moat_score, scan_score
  undervalue       ttm_revenue, q_yoy_pct, ttm_growth_pct, on_list, floor_ok, ratio
  bonde            qualifier, bonde_tier, bonde_score, scan_score
  fallen_growers   pct_below_high, pct_above_low, sales_yoy_pct, pair_blanked, floor_ok, in_served_pool
  hot              sales_tier, q_eps_yoy, ret_21d, served
  quiet_strong     stage, score, score_ranked, net_profit, ocf, opm, sales_cagr, profit_cagr,
                   liab_to_equity, sales_tier, dollar_vol_50, pct_below_high, net_debt_ebitda
  accel_after_fall market_cap, sales_tier, sales_accelerating, growth_yoy_pct, prior_yoy_pct,
                   pct_below_high, pct_above_low, stage, dollar_vol_50, net_profit
  pankaj           close, close_date, zones, tier, zt
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

from sepa import pankaj_picks as PK

from . import constants as C
from . import words as W

FUNDAMENTAL, MARKET, STAGE, INFO = "fundamental", "market", "stage", "info"
PASS, FAIL, UNKNOWN, INFO_V = "pass", "fail", "unknown", "info"


@dataclass(frozen=True)
class Leg:
    key: str
    label: str
    kind: str
    verdict: str
    value: object
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


# ── comparators (None / "unknown" -> unknown, never pass) ──
def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return float(v)


def _ge(v, thr):
    n = _num(v)
    return UNKNOWN if n is None else (PASS if n >= thr else FAIL)


def _gt(v, thr):
    n = _num(v)
    return UNKNOWN if n is None else (PASS if n > thr else FAIL)


def _le(v, thr):
    n = _num(v)
    return UNKNOWN if n is None else (PASS if n <= thr else FAIL)


def _bool(v):
    if v is True:
        return PASS
    if v is False:
        return FAIL
    return UNKNOWN


def _tier_in(v, tiers):
    if not isinstance(v, str) or not v or v == "unknown":
        return UNKNOWN
    return PASS if v in tiers else FAIL


def _eq(v, want):
    n = _num(v)
    return UNKNOWN if n is None else (PASS if n == want else FAIL)


def _in(v, opts):
    n = _num(v)
    return UNKNOWN if n is None else (PASS if n in opts else FAIL)


# ── per-category leg functions: (key, kind, fn(values) -> (verdict, value)) ──
def _s2_sales(v):
    tier, acc = v.get("sales_tier"), v.get("sales_accelerating")
    val = {"tier": tier, "accelerating": acc}
    if not isinstance(tier, str) or not tier or tier == "unknown":
        return UNKNOWN, (None if tier is None else val)
    if tier in C.S2_SALES_TIERS:
        return PASS, val
    if tier == C.S2_STEADY_TIER:
        if acc is True:
            return PASS, val
        if acc is None:
            return UNKNOWN, val
    return FAIL, val


def _uv_on_list(v, f_verdicts):
    on = v.get("on_list")
    if on is True:
        return PASS, True
    if on is False:
        # Off the list: unknown when every fundamental leg passes (the price side moved), else fail.
        return (UNKNOWN if f_verdicts and all(x == PASS for x in f_verdicts) else FAIL), False
    return UNKNOWN, None


def _score(v):
    s, ranked = v.get("score"), v.get("score_ranked")
    val = None if s is None and ranked is None else {"score": s, "ranked": ranked}
    if ranked is not True:
        return UNKNOWN, val
    return _ge(s, C.QUIET_MIN_SCORE), val


def _cap_band(v):
    n = _num(v.get("market_cap"))
    if n is None:
        return UNKNOWN, None
    return (PASS if C.ACCEL_MIN_CAP_USD <= n <= C.ACCEL_MAX_CAP_USD else FAIL), n


def _f(key, fn):
    return lambda v: (fn(v.get(key)), v.get(key))


_SPECS: dict = {
    "s2_growth": [
        ("qualifier", MARKET, _f("qualifier", _bool)),
        ("stage", STAGE, _f("stage", lambda x: _eq(x, C.S2_STAGE))),
        ("sales_tier", FUNDAMENTAL, _s2_sales),
        ("c_strong_q_eps", FUNDAMENTAL, _f("c_strong_q_eps", _bool)),
        ("a_strong_y_eps", FUNDAMENTAL, _f("a_strong_y_eps", _bool)),
    ],
    "capital_quality": [
        ("qualifier", MARKET, _f("qualifier", _bool)),
        ("roe", FUNDAMENTAL, _f("roe_pct", lambda x: _ge(x, C.CQ_MIN_ROE_PCT))),
        ("fcf_margin", FUNDAMENTAL, _f("fcf_margin_pct", lambda x: _gt(x, C.CQ_MIN_FCF_MARGIN_PCT))),
        ("net_debt_ebitda", FUNDAMENTAL, _f("net_debt_ebitda", lambda x: _le(x, C.CQ_MAX_NET_DEBT_EBITDA))),
        ("cq_grade", INFO, lambda v: (INFO_V, v.get("cq_grade"))),
    ],
    "undervalue": [
        ("ttm_revenue", FUNDAMENTAL, _f("ttm_revenue", lambda x: _ge(x, C.UV_MIN_TTM_REVENUE_USD))),
        ("q_yoy", FUNDAMENTAL, _f("q_yoy_pct", lambda x: _ge(x, C.UV_MIN_Q_YOY_PCT))),
        ("ttm_growth", FUNDAMENTAL, _f("ttm_growth_pct", lambda x: _ge(x, C.UV_MIN_TTM_GROWTH_PCT))),
        ("on_list", MARKET, None),            # special: reads the F verdicts above
        ("floor", MARKET, _f("floor_ok", _bool)),
    ],
    "bonde": [
        ("qualifier", MARKET, _f("qualifier", _bool)),
        ("bonde_tier", FUNDAMENTAL, _f("bonde_tier", lambda x: _tier_in(x, C.BONDE_TIERS))),
    ],
    "fallen_growers": [
        ("pct_below_high", MARKET, _f("pct_below_high", lambda x: _ge(x, C.FALLEN_MIN_PCT_BELOW))),
        ("pct_above_low", MARKET, _f("pct_above_low", lambda x: _ge(x, C.FALLEN_MIN_PCT_ABOVE_LOW))),
        ("sales_yoy", FUNDAMENTAL,
         lambda v: ((UNKNOWN if v.get("pair_blanked") else _ge(v.get("sales_yoy_pct"), C.FALLEN_MIN_SALES_YOY_PCT)),
                    v.get("sales_yoy_pct"))),
        ("floor", MARKET, _f("floor_ok", _bool)),
    ],
    "hot": [
        ("sales_tier", FUNDAMENTAL, _f("sales_tier", lambda x: _tier_in(x, C.HOT_SALES_TIERS))),
        ("q_eps_yoy", FUNDAMENTAL, _f("q_eps_yoy", lambda x: _gt(x, C.HOT_MIN_Q_EPS_YOY))),
        ("ret_21d", MARKET, _f("ret_21d", lambda x: _gt(x, C.HOT_MIN_RET_21D))),
        ("served", MARKET, _f("served", _bool)),
    ],
    "quiet_strong": [
        ("stage", STAGE, _f("stage", lambda x: _eq(x, C.QUIET_STAGE))),
        ("score", FUNDAMENTAL, _score),
        ("net_profit", FUNDAMENTAL, _f("net_profit", lambda x: _gt(x, C.QUIET_MIN_NET_PROFIT))),
        ("ocf", FUNDAMENTAL, _f("ocf", lambda x: _gt(x, C.QUIET_MIN_OCF))),
        ("sales_cagr", FUNDAMENTAL, _f("sales_cagr", lambda x: _ge(x, C.QUIET_MIN_SALES_CAGR_PCT))),
        ("liab_to_equity", FUNDAMENTAL, _f("liab_to_equity", lambda x: _le(x, C.QUIET_MAX_LIAB_TO_EQUITY))),
        ("sales_tier", FUNDAMENTAL, _f("sales_tier", lambda x: _tier_in(x, C.QUIET_SALES_TIERS))),
        ("dollar_vol_50", MARKET, _f("dollar_vol_50", lambda x: _ge(x, C.QUIET_MIN_DOLLAR_VOL))),
        ("pct_below_high", MARKET, _f("pct_below_high", lambda x: _ge(x, C.QUIET_MIN_PCT_BELOW_HIGH))),
        ("net_debt_ebitda", INFO, lambda v: (INFO_V, v.get("net_debt_ebitda"))),
    ],
    "accel_after_fall": [
        ("market_cap", MARKET, _cap_band),
        ("sales_tier", FUNDAMENTAL, _f("sales_tier", lambda x: _tier_in(x, C.ACCEL_SALES_TIERS))),
        ("accelerating", FUNDAMENTAL, _f("sales_accelerating", _bool)),
        ("prior_yoy", FUNDAMENTAL, _f("prior_yoy_pct", lambda x: _gt(x, C.ACCEL_MIN_PRIOR_YOY_PCT))),
        ("pct_below_high", MARKET, _f("pct_below_high", lambda x: _ge(x, C.ACCEL_MIN_PCT_BELOW_HIGH))),
        ("pct_above_low", MARKET, _f("pct_above_low", lambda x: _ge(x, C.ACCEL_MIN_PCT_ABOVE_LOW))),
        ("stage", STAGE, _f("stage", lambda x: _in(x, C.ACCEL_STAGES))),
        ("dollar_vol_50", MARKET, _f("dollar_vol_50", lambda x: _ge(x, C.ACCEL_MIN_DOLLAR_VOL))),
        ("net_profit", INFO, lambda v: (INFO_V, v.get("net_profit"))),
    ],
    "pankaj": [
        ("pankaj_tier", INFO, lambda v: (INFO_V, {"tier": v.get("tier"), "zt": v.get("zt")})),
        ("pankaj_zones", INFO, lambda v: (INFO_V, v.get("zones") or {})),
        ("zone_read", INFO, lambda v: (INFO_V, v.get("zone_read"))),
    ],
}

LEG_KINDS: dict = {cat: {key: kind for key, kind, _ in spec} for cat, spec in _SPECS.items()}


def legs(cat: str, values: Optional[dict]) -> list:
    """Every leg of `cat` over `values`, in table order."""
    v = values or {}
    out = []
    f_verdicts: list = []
    for key, kind, fn in _SPECS[cat]:
        if key == "on_list":
            verdict, value = _uv_on_list(v, f_verdicts)
        else:
            verdict, value = fn(v)
        if kind == INFO:
            verdict = INFO_V
        elif kind == FUNDAMENTAL:
            f_verdicts.append(verdict)
        if cat == "pankaj" and key == "zone_read" and value is None and v.get("zones") is not None:
            value = zone_read(v.get("zones") or {}, v.get("close"), v.get("close_date"),
                              tuple((v.get("zones") or {}).keys()))
        out.append(Leg(key=key, label=W.leg_label(key), kind=kind, verdict=verdict, value=value,
                       text=W.leg_text(cat, key, value)))
    return out


def qualifies(cat: str, values: Optional[dict]) -> Optional[bool]:
    """Over the non-info legs: True when all pass, False when any fails, None otherwise. 🧭 -> None."""
    if cat == C.PANKAJ_KEY:
        return None
    vs = [lg.verdict for lg in legs(cat, values) if lg.kind != INFO]
    if any(x == FAIL for x in vs):
        return False
    if vs and all(x == PASS for x in vs):
        return True
    return None


def in_population(cat: str, values: Optional[dict]) -> bool:
    v = values or {}
    if cat == C.PANKAJ_KEY:
        return False
    if cat == "fallen_growers":
        return v.get("in_served_pool") is True
    if cat == "hot":
        return v.get("served") is True
    return True


def _desc(x):
    n = _num(x)
    return float("inf") if n is None else -n


def _asc(x):
    n = _num(x)
    return float("inf") if n is None else n


def rank_key(cat: str, values: Optional[dict], symbol: str) -> tuple:
    v = values or {}
    sym = str(symbol or "")
    if cat == "s2_growth":
        return (_desc(v.get("rs_rank")), _desc(v.get("scan_score")), sym)
    if cat == "capital_quality":
        return (_desc(v.get("moat_score")), _desc(v.get("scan_score")), sym)
    if cat == "undervalue":
        return (_asc(v.get("ratio")), sym)
    if cat == "bonde":
        return (_desc(v.get("bonde_score")), _desc(v.get("scan_score")), sym)
    if cat == "fallen_growers":
        return (_desc(v.get("sales_yoy_pct")), sym)
    if cat == "hot":
        return (_desc(v.get("ret_21d")), sym)
    if cat == "quiet_strong":
        return (_desc(v.get("score")), sym)
    if cat == "accel_after_fall":
        g, p = _num(v.get("growth_yoy_pct")), _num(v.get("prior_yoy_pct"))
        return (float("inf") if g is None or p is None else -(g - p), sym)
    return (sym,)


def sector_cap(cat: str) -> int:
    return C.HOT_MAX_PER_SECTOR if cat == "hot" else C.MAX_PER_SECTOR


def _share_class_key(values: dict):
    vals = tuple(_num((values or {}).get(k)) for k in C.SHARE_CLASS_KEYS)
    return None if any(x is None for x in vals) else vals


def pick_top(cat: str, population, *, saved=frozenset()) -> list:
    """qualifies True AND in_population -> rank_key -> 🌱 share-class dedupe (saved symbol wins)
    -> sector cap -> first PER_CATEGORY. 🧭 -> []."""
    if cat == C.PANKAJ_KEY:
        return []
    saved = {str(s).upper() for s in (saved or ())}
    pool = []
    for cand in population or []:
        sym = str(cand.get("symbol") or "").upper()
        vals = cand.get("values") or {}
        if not sym or not in_population(cat, vals) or qualifies(cat, vals) is not True:
            continue
        pool.append((rank_key(cat, vals, sym), sym, cand.get("sector"), vals))
    pool.sort(key=lambda t: t[0])
    if cat == "quiet_strong":
        groups: dict = {}
        for i, (_, sym, _, vals) in enumerate(pool):
            k = _share_class_key(vals)
            if k is not None:
                groups.setdefault(k, []).append(i)
        drop = set()
        for idxs in groups.values():
            if len(idxs) < 2:
                continue
            winner = next((i for i in idxs if pool[i][1] in saved), idxs[0])
            keep_at = idxs[0]
            if winner != keep_at:
                pool[keep_at] = (pool[keep_at][0], pool[winner][1], pool[winner][2], pool[winner][3])
            drop.update(i for i in idxs if i != keep_at)
        pool = [p for i, p in enumerate(pool) if i not in drop]
    cap = sector_cap(cat)
    per: dict = {}
    out = []
    for _, sym, sector, _ in pool:
        if sector:
            if per.get(sector, 0) >= cap:
                continue
            per[sector] = per.get(sector, 0) + 1
        out.append(sym)
        if len(out) >= C.PER_CATEGORY:
            break
    return out


def zone_read(zones: dict, close, close_date, order) -> dict:
    """Where `close` sits against Pankaj's zones, through the /pankaj page's own
    engine `pankaj_picks.setup_status` (ONLY its state + dist_pct are read)."""
    readable = {}
    for zk in order or tuple((zones or {}).keys()):
        pair = list((zones or {}).get(zk) or (None, None)) + [None, None]
        lo, hi = _num(pair[0]), _num(pair[1])
        if lo is None or hi is None or lo > hi:
            continue
        readable[zk] = (lo, hi)
    base = {"close": _num(close), "close_date": close_date, "n_zones": len(readable), "zones": readable}
    if _num(close) is None:
        return {**base, "in": [], "nearest": None, "unknown": True}
    inside, nearest = [], None
    for zk, (lo, hi) in readable.items():
        st = PK.setup_status({"kind": "pullback", "zone": {"lo": lo, "hi": hi}}, float(close))
        state, dist = st.get("state"), st.get("dist_pct")
        if state == "in_zone":
            inside.append(zk)
            continue
        if _num(dist) is None or state not in ("above_zone", "below_zone"):
            continue
        cand = {"zone": zk, "side": "over" if state == "above_zone" else "under",
                "pct": abs(float(dist)), "edge": hi if state == "above_zone" else lo}
        if nearest is None or cand["pct"] < nearest["pct"]:
            nearest = cand
    return {**base, "in": inside, "nearest": nearest}

