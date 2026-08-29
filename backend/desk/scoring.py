"""Desk scoring — the deterministic half of the daily pre-market report.

Ajay 2026-08-28: "Add a cron or daily routine use our data to do the
analysis" through a veteran momentum-trader lens (his pasted persona).
The numbers are computed HERE from the app's own signals; the LLM only
writes prose around them and is forbidden from inventing figures. That
split is the whole design: a persona can hallucinate, a scorer cannot.

Score components (persona's weights, mapped to signals we actually have):

  catalyst   25  Bonde sales tier/acceleration + EPS growth + earnings
                 quality — "catalyst" here means fundamentals the market
                 must reprice, since the app has no news feed. What we
                 cannot verify we do not score (no [unverified] points).
  technical  25  trend template, RS rank, VCP contraction quality, pivot
                 proximity, accumulation (all from the SEPA scan row)
  asymmetry  20  R multiple from the row's own trade_plan entry/stop and
                 a Minervini 20% measured move when no target exists
  liquidity  15  average dollar volume tiers
  crowding   15  starts full, pays penalties for extension past the buy
                 zone and for mega-liquidity names everyone already owns

Only names scoring >= REPORT_MIN make the book. Disqualifiers run BEFORE
scoring and are reported as the cut list — the persona's "the cut list is
part of the output".

Throttle: the regime verdict gates size and idea count. RISK_OFF means
the honest answer is mostly cash; the book is capped at one idea and the
report says so rather than manufacturing setups.
"""
from __future__ import annotations

from typing import Optional

# ── his parameters (edit here; the report prints them every run) ───────────
RISK_PCT_PER_TRADE = 0.75          # % of account risked per position
MAX_POSITIONS = 5
MIN_PRICE = 2.0
MIN_DOLLAR_VOL = 5_000_000.0       # ADV $ floor — below this, cut
EARNINGS_WINDOW_DAYS = 7           # earnings inside the hold window → cut
MAX_EXT_FROM_PIVOT_PCT = 10.0      # extended past the pivot → chase, cut
REPORT_MIN = 70.0

THROTTLE = {
    "RISK_ON":  {"max_ideas": 5, "size_factor": 1.0,
                 "note": "full size, up to 5 ideas"},
    "MIXED":    {"max_ideas": 3, "size_factor": 0.5,
                 "note": "half size, max 3 ideas, tighter stops"},
    "RISK_OFF": {"max_ideas": 1, "size_factor": 0.25,
                 "note": "cash is a position — at most 1 idea, quarter size"},
}


def regime_verdict(regime: Optional[dict]) -> dict:
    """Map sepa.market_regime output to the persona's three-state verdict.

    confirmed_uptrend → RISK_ON, pressure → MIXED, correction → RISK_OFF —
    then O'Neil's distribution count and VIX stress can each downgrade one
    notch, never upgrade: the tape gets the benefit of no doubt.
    """
    label = (regime or {}).get("label") or "unknown"
    comp = (regime or {}).get("components") or {}
    if isinstance(comp, list):                    # regime() ships a list view
        comp = {c.get("key"): c for c in comp if isinstance(c, dict)}
    base = {"confirmed_uptrend": "RISK_ON", "pressure": "MIXED",
            "correction": "RISK_OFF"}.get(label, "MIXED")
    drivers = [f"regime engine: {label}"]

    dist = ((comp.get("distribution") or {}).get("count")
            if isinstance(comp.get("distribution"), dict) else None)
    vix = ((comp.get("stress") or {}).get("vix")
           if isinstance(comp.get("stress"), dict) else None)

    order = ["RISK_ON", "MIXED", "RISK_OFF"]
    verdict = base
    if isinstance(dist, (int, float)) and dist >= 6 and verdict == "RISK_ON":
        verdict = "MIXED"
        drivers.append(f"downgraded: {int(dist)} distribution days in 25")
    elif isinstance(dist, (int, float)):
        drivers.append(f"{int(dist)} distribution days in 25")
    if isinstance(vix, (int, float)) and vix > 30 and verdict != "RISK_OFF":
        verdict = order[order.index(verdict) + 1]
        drivers.append(f"downgraded: VIX {vix:.1f} > 30")
    elif isinstance(vix, (int, float)):
        drivers.append(f"VIX {vix:.1f}")

    return {"verdict": verdict, "label": label, "drivers": drivers,
            "throttle": THROTTLE[verdict]}


# ── disqualifiers: run before any scoring, reasons travel to the cut list ──
def disqualify(row: dict, earnings_in_days: Optional[int] = None) -> list:
    """Reasons this scan row cannot be traded, [] if clean. Missing data
    only disqualifies where trading blind would be the error (liquidity);
    everywhere else absence of evidence is not a signal."""
    out = []
    last = row.get("last_close")
    if isinstance(last, (int, float)) and last < MIN_PRICE:
        out.append(f"price ${last:g} < ${MIN_PRICE:g}")
    liq = row.get("liquidity") or {}
    adv = liq.get("avg_dollar_vol")
    if not isinstance(adv, (int, float)) or adv < MIN_DOLLAR_VOL:
        out.append(f"dollar volume {_fmt_dollars(adv)} < {_fmt_dollars(MIN_DOLLAR_VOL)}/day")
    if (earnings_in_days is not None
            and 0 <= earnings_in_days <= EARNINGS_WINDOW_DAYS):
        out.append(f"earnings in {earnings_in_days}d — inside the hold window")
    ext = row.get("ext_from_pivot_pct")
    if isinstance(ext, (int, float)) and ext > MAX_EXT_FROM_PIVOT_PCT:
        out.append(f"extended {ext:+.1f}% past the pivot — chasing")
    tier = ((row.get("fundamentals") or {}).get("sales") or {}).get("tier")
    if tier in ("declining", "weak"):
        out.append(f"sales {tier} — knife discipline")
    climax = row.get("climax_distribution")
    if isinstance(climax, dict):
        if climax.get("is_distribution") or climax.get("in_climax"):
            out.append("climax/distribution flag on the chart")
    elif climax:                                   # bool form in older rows
        out.append("climax/distribution flag on the chart")
    n_sells = _count_sell_signals(row.get("sell_signals"))
    if n_sells >= 2:
        out.append(f"{n_sells} active sell signals")
    return out


def _count_sell_signals(sells) -> int:
    """Scanner ships {"signals": {name: bool}}; older rows a plain list."""
    if isinstance(sells, dict):
        return sum(1 for v in (sells.get("signals") or {}).values() if v)
    if isinstance(sells, (list, tuple)):
        return len(sells)
    return 0


# ── component scores ───────────────────────────────────────────────────────
def _catalyst(row: dict) -> float:
    f = row.get("fundamentals") or {}
    sales = f.get("sales") or {}
    pts = {"explosive": 12.0, "strong": 9.0, "steady": 5.0}.get(
        sales.get("tier"), 0.0)
    if sales.get("accelerating"):
        pts += 4.0
    q_eps = f.get("q_eps_growth_pct")
    if isinstance(q_eps, (int, float)):
        pts += 5.0 if q_eps >= 40 else (3.0 if q_eps >= 25 else 0.0)
    eq = (f.get("earnings_quality") or {})
    if eq.get("tier") == "accelerating":
        pts += 4.0
    return min(pts, 25.0)


def _technical(row: dict) -> float:
    pts = 0.0
    if (row.get("trend") or {}).get("pass_all"):
        pts += 8.0
    rs = row.get("rs_rank")
    if isinstance(rs, (int, float)):
        pts += 5.0 if rs >= 90 else (3.0 if rs >= 80 else 0.0)
    vcp = row.get("vcp") or {}
    n = vcp.get("n_contractions")
    if isinstance(n, int) and 2 <= n <= 4 and vcp.get("monotonic_shrinkage"):
        pts += 6.0
    elif vcp.get("has_base"):
        pts += 2.0
    if row.get("is_in_buy_zone"):
        pts += 4.0
    if (row.get("volume") or {}).get("accumulation"):
        pts += 2.0
    return min(pts, 25.0)


def rr_multiple(entry, stop, target) -> Optional[float]:
    """Reward-to-risk. None when the geometry is missing or nonsensical —
    an invented R multiple is how accounts die."""
    try:
        entry, stop, target = float(entry), float(stop), float(target)
    except (TypeError, ValueError):
        return None
    risk = entry - stop
    if risk <= 0 or target <= entry:
        return None
    return (target - entry) / risk


def _asymmetry(row: dict) -> tuple:
    """(points, plan) where plan carries entry/stop/targets/R for the book
    table. Entry and stop come from the row's own trade_plan; target 1 is
    the Minervini +20% measured move, target 2 the +25% 'sell into
    strength' zone (TLSW — most winners pause after 20-25%)."""
    tp = row.get("trade_plan") or {}
    entry = tp.get("entry_recommended")
    stop = (tp.get("stop") or {}).get("recommended")
    if not isinstance(entry, (int, float)) or not isinstance(stop, (int, float)):
        return 0.0, None
    t1, t2 = entry * 1.20, entry * 1.25
    r = rr_multiple(entry, stop, t1)
    if r is None:
        return 0.0, None
    pts = 20.0 if r >= 3 else (15.0 if r >= 2 else (10.0 if r >= 1.5 else 4.0))
    plan = {"entry": round(entry, 2), "stop": round(stop, 2),
            "target1": round(t1, 2), "target2": round(t2, 2),
            "rr": round(r, 2),
            "risk_pct": (tp.get("stop") or {}).get("risk_pct")}
    return pts, plan


def _liquidity(row: dict) -> float:
    adv = (row.get("liquidity") or {}).get("avg_dollar_vol")
    if not isinstance(adv, (int, float)):
        return 0.0
    for floor, pts in ((50e6, 15.0), (20e6, 12.0), (10e6, 9.0), (5e6, 6.0)):
        if adv >= floor:
            return pts
    return 2.0


def _crowding(row: dict) -> float:
    """Starts full; pays for being what everyone already owns or has
    already chased. Dollar volume is the crowding proxy the app can
    actually verify — no float or SI data, so none is scored."""
    pts = 15.0
    ext = row.get("ext_from_pivot_pct")
    if isinstance(ext, (int, float)) and ext > 5:
        pts -= 5.0
    adv = (row.get("liquidity") or {}).get("avg_dollar_vol")
    if isinstance(adv, (int, float)) and adv > 1e9:
        pts -= 4.0
    dchg = row.get("day_change_pct")
    if isinstance(dchg, (int, float)) and dchg > 8:
        pts -= 3.0
    return max(pts, 0.0)


def score_row(row: dict) -> dict:
    """Full component score for one scan row. The sub-scores ship so he
    can argue with the math — that is a persona requirement."""
    asym_pts, plan = _asymmetry(row)
    parts = {"catalyst": _catalyst(row), "technical": _technical(row),
             "asymmetry": asym_pts, "liquidity": _liquidity(row),
             "crowding": _crowding(row)}
    return {"total": round(sum(parts.values()), 1), "parts": parts,
            "plan": plan}


def position_size(account_value, entry, stop, size_factor: float = 1.0,
                  risk_pct: float = RISK_PCT_PER_TRADE) -> Optional[dict]:
    """Shares sized off the stop distance, never off conviction. None when
    the inputs cannot support honest math."""
    try:
        account_value, entry, stop = (float(account_value), float(entry),
                                      float(stop))
    except (TypeError, ValueError):
        return None
    per_share = entry - stop
    if account_value <= 0 or per_share <= 0 or entry <= 0:
        return None
    budget = account_value * (risk_pct / 100.0) * size_factor
    shares = int(budget / per_share)
    return {"shares": shares, "risk_dollars": round(shares * per_share, 2),
            "cost": round(shares * entry, 2),
            "risk_budget_pct": risk_pct, "size_factor": size_factor}


def _fmt_dollars(v) -> str:
    if not isinstance(v, (int, float)):
        return "unknown"
    for cut, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= cut:
            return f"${v / cut:.1f}{suf}"
    return f"${v:.0f}"
