"""📅 Long Term — every sentence the tab serves (2026-11-12).

Numbers appear only through f-strings over constants.py or engine dicts
(`bonde.MEASURED`, facts values). No sentence here says the four trading verbs
the house word rule bans; the ONE allowed sentence is NOT_A_SIGNAL. "Reversal",
never the other word. Liabilities / equity is labelled as such, never "debt".
"""
from __future__ import annotations

from typing import Optional

from . import constants as C

NOT_A_SIGNAL = "None of these lists is a buy signal."
NOTE = (f"{C.MARK} UNMEASURED — your list saved on {C.SAVED_ON}, re-read every week from the "
        f"other tabs' own data. Each list carries its own caveat. {NOT_A_SIGNAL}")
OWNER_ONLY_TEXT = f"{C.MARK} Long Term is a private list — shown to the account owner only."
DASH = "—"

CATEGORY_LABELS = {
    "s2_growth": "\U0001F680 Stage 2 growth leaders",
    "capital_quality": "\U0001F48E Capital quality",
    "undervalue": "\U0001F3F7️ Undervalue vs peers",
    "bonde": "\U0001F4C8 Bonde",
    "fallen_growers": "\U0001F4C9 Fallen growers turning up",
    "hot": "\U0001F525 Hot sectors",
    "quiet_strong": "\U0001F331 Strong but not moving yet",
    "accel_after_fall": "\U0001F504 Small & mid caps accelerating after a fall",
    "pankaj": "\U0001F9ED Pankaj's long-term list",
}
CATEGORY_MARKS = {k: v.split(" ", 1)[0] for k, v in CATEGORY_LABELS.items()}

SOURCE_TABS = {
    "s2_growth": "SEPA scan (full)",
    "capital_quality": "SEPA scan moat components (proxy) + the 💎 grade on 🚀",
    "undervalue": "Chart Maps 🏷️ vs peers",
    "bonde": "SEPA scan Bonde read",
    "fallen_growers": f"Chart Maps 📉 Down {C.FALLEN_MIN_PCT_BELOW:g}%+",
    "hot": "🔥 Hottest",
    "quiet_strong": "Ticker ▸ Fundamentals long-term doc + stage on the cached daily bars",
    "accel_after_fall": "Research sales cache (full universe) + cached daily bars + cached market caps",
    "pankaj": f"Pankaj's sheet, read {C.SAVED_ON}",
}

SOURCE_LABELS = {
    "scan": "SEPA scan", "undervalue": "🏷️ vs peers", "fallen": "📉 fallen list",
    "hottest": "🔥 Hottest", "longterm": "Long-term filings doc", "research": "Research sales cache",
    "frames": "Cached daily bars", "caps": "Cached market caps", "growth_board": "🚀 growth board",
}

STAGE_LABELS_FALLBACK = {1: "Basing", 2: "Advancing", 3: "Topping", 4: "Decline"}

CAVEAT_TAGS = {
    "s2_growth": "UNMEASURED", "capital_quality": "UNMEASURED", "undervalue": "≈ market",
    "bonde": "INVERTED", "fallen_growers": "UNMEASURED", "hot": "UNMEASURED",
    "quiet_strong": "UNMEASURED", "accel_after_fall": "UNMEASURED", "pankaj": "his picks",
}


# ── small formatters ──
def _et_label(hhmm: str) -> str:
    h, m = (int(x) for x in str(hhmm).split(":"))
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix} ET"


RUN_AFTER_TEXT = _et_label(C.RUN_AFTER_ET)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float("inf"), float("-inf"))


def money(v) -> str:
    if not _is_num(v):
        return DASH
    sign = "−" if v < 0 else ""
    a = abs(float(v))
    for div, unit in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            return f"{sign}${a / div:.3g}{unit}"
    return f"{sign}${a:.0f}"


def _tiers(tiers) -> str:
    tiers = list(tiers)
    if len(tiers) <= 1:
        return "".join(tiers)
    return ", ".join(tiers[:-1]) + " or " + tiers[-1]


def _stages(stages) -> str:
    return " or ".join(str(s) for s in stages)


def mmdd(date: Optional[str]) -> str:
    d = str(date or "")
    return d[5:10] if len(d) >= 10 else (d or DASH)


def stage_label(stage, label=None) -> str:
    if label:
        return str(label)
    return STAGE_LABELS_FALLBACK.get(stage, "") if isinstance(stage, int) else ""


# ── leg labels + texts ──
LEG_LABELS = {
    "qualifier": "Trend template", "stage": "Stage", "sales_tier": "Sales tier",
    "c_strong_q_eps": "Quarterly EPS (C)", "a_strong_y_eps": "Annual EPS (A)",
    "roe": "ROE", "fcf_margin": "FCF margin", "net_debt_ebitda": "Net debt / EBITDA",
    "cq_grade": "💎 grade on 🚀", "ttm_revenue": "TTM revenue", "q_yoy": "Latest-quarter sales",
    "ttm_growth": "TTM sales growth", "on_list": "🏷️ vs-peers list", "floor": "Liquidity floor",
    "bonde_tier": "Bonde tier", "pct_below_high": "Under the 52-week high",
    "pct_above_low": "Over the 52-week low", "sales_yoy": "Sales y/y", "q_eps_yoy": "Quarterly EPS y/y",
    "ret_21d": "One-month return", "served": "🔥 Hottest top", "score": "Long-term score",
    "net_profit": "Net profit", "ocf": "Operating cash flow", "sales_cagr": "Sales CAGR",
    "liab_to_equity": "Liabilities / equity", "dollar_vol_50": "Average daily $ volume",
    "market_cap": "Market cap", "accelerating": "Sales accelerating", "prior_yoy": "Prior-quarter sales",
    "pankaj_tier": "Pankaj tier + ZT", "pankaj_zones": "Pankaj's zones", "zone_read": "Zone read",
}

_BELOW_HIGH = {"fallen_growers": C.FALLEN_MIN_PCT_BELOW, "quiet_strong": C.QUIET_MIN_PCT_BELOW_HIGH,
               "accel_after_fall": C.ACCEL_MIN_PCT_BELOW_HIGH}
_ABOVE_LOW = {"fallen_growers": C.FALLEN_MIN_PCT_ABOVE_LOW, "accel_after_fall": C.ACCEL_MIN_PCT_ABOVE_LOW}
_DOLLAR_VOL = {"quiet_strong": C.QUIET_MIN_DOLLAR_VOL, "accel_after_fall": C.ACCEL_MIN_DOLLAR_VOL}
_TIER_SETS = {"hot": C.HOT_SALES_TIERS, "quiet_strong": C.QUIET_SALES_TIERS,
              "accel_after_fall": C.ACCEL_SALES_TIERS}


def leg_label(key: str) -> str:
    return LEG_LABELS.get(key, key)


def leg_text(cat: str, key: str, value) -> str:
    """The one sentence for a leg's value; None (or an unreadable value) -> "—"."""
    try:
        return _leg_text(cat, key, value)
    except Exception:                                           # noqa: BLE001
        return DASH


def _leg_text(cat, key, v) -> str:
    if key == "pankaj_tier":
        return pankaj_tier_text((v or {}).get("tier"), (v or {}).get("zt")) if v else DASH
    if key == "pankaj_zones":
        return pankaj_zones_text(v or {}, tuple((v or {}).keys()))
    if key == "zone_read":
        return zone_text(v, None) if v else DASH
    if key == "net_debt_ebitda" and cat != "capital_quality":
        return net_debt_text(v)
    if v is None:
        return DASH
    if key == "qualifier":
        return "Trend template: passes" if v else "Trend template: fails"
    if key == "stage":
        need = {"s2_growth": str(C.S2_STAGE), "quiet_strong": str(C.QUIET_STAGE),
                "accel_after_fall": _stages(C.ACCEL_STAGES)}.get(cat, "")
        return f"Stage {v} (needs Stage {need})" if need else f"Stage {v}"
    if key == "sales_tier":
        if cat == "s2_growth":
            tier = (v or {}).get("tier") if isinstance(v, dict) else v
            acc = (v or {}).get("accelerating") if isinstance(v, dict) else None
            if tier is None:
                return DASH
            return (f"Sales tier {tier}{', accelerating' if acc else ''} (needs {_tiers(C.S2_SALES_TIERS)}, "
                    f"or {C.S2_STEADY_TIER} and accelerating)")
        return f"Sales tier {v} (needs {_tiers(_TIER_SETS.get(cat, ()))})"
    if key == "c_strong_q_eps":
        return "Quarterly EPS strong (C)" if v else "Quarterly EPS not strong (C)"
    if key == "a_strong_y_eps":
        return "Annual EPS strong (A)" if v else "Annual EPS not strong (A)"
    if key == "roe":
        return f"ROE {v:.1f}% (needs ≥ {C.CQ_MIN_ROE_PCT:g}%)"
    if key == "fcf_margin":
        return f"FCF margin {v:.1f}% (needs > {C.CQ_MIN_FCF_MARGIN_PCT:g}%)"
    if key == "net_debt_ebitda":
        return f"{net_debt_text(v)} (needs ≤ {C.CQ_MAX_NET_DEBT_EBITDA:g})"
    if key == "cq_grade":
        return f"💎 grade on 🚀: {v}"
    if key == "ttm_revenue":
        return f"TTM revenue {money(v)} (needs ≥ {money(C.UV_MIN_TTM_REVENUE_USD)})"
    if key == "q_yoy":
        return f"Latest-quarter sales {v:+.1f}% y/y (needs ≥ {C.UV_MIN_Q_YOY_PCT:g}%)"
    if key == "ttm_growth":
        return f"TTM sales growth {v:+.1f}% (needs ≥ {C.UV_MIN_TTM_GROWTH_PCT:g}%)"
    if key == "on_list":
        return "On the 🏷️ vs-peers list" if v else "Off the 🏷️ vs-peers list (P/S vs peers)"
    if key == "floor":
        return (f"Liquidity floor: {C.FLOOR_TIER} or better" if v
                else f"Below the {C.FLOOR_TIER} liquidity floor")
    if key == "bonde_tier":
        return f"Bonde tier {v} (needs {_tiers(C.BONDE_TIERS)})"
    if key == "pct_below_high":
        return f"{v:.1f}% under its 52-week high (needs ≥ {_BELOW_HIGH.get(cat, 0):g}%)"
    if key == "pct_above_low":
        return f"{v:.1f}% over its 52-week low (needs ≥ {_ABOVE_LOW.get(cat, 0):g}%)"
    if key == "sales_yoy":
        return f"Sales {v:+.1f}% y/y (needs ≥ {C.FALLEN_MIN_SALES_YOY_PCT:g}%)"
    if key == "q_eps_yoy":
        return f"Quarterly EPS {v:+.1f}% y/y (needs > {C.HOT_MIN_Q_EPS_YOY:g}%)"
    if key == "ret_21d":
        return f"One-month return {v:+.1f}% (needs > {C.HOT_MIN_RET_21D:g}%)"
    if key == "served":
        return (f"In its group's top {C.HOT_PAGE} on 🔥 Hottest" if v
                else f"Outside its group's top {C.HOT_PAGE} on 🔥 Hottest")
    if key == "score":
        s = (v or {}).get("score") if isinstance(v, dict) else v
        ranked = (v or {}).get("ranked", True) if isinstance(v, dict) else True
        if not ranked:
            return "Long-term score not ranked"
        if s is None:
            return DASH
        return f"Long-term score {s:.1f} (needs ≥ {C.QUIET_MIN_SCORE:g})"
    if key == "net_profit":
        if cat == "accel_after_fall":
            return f"Net profit {money(v)}"
        return f"Net profit {money(v)} (needs > {money(C.QUIET_MIN_NET_PROFIT)})"
    if key == "ocf":
        return f"Operating cash flow {money(v)} (needs > {money(C.QUIET_MIN_OCF)})"
    if key == "sales_cagr":
        return f"Sales CAGR {v:.1f}% (needs ≥ {C.QUIET_MIN_SALES_CAGR_PCT:g}%)"
    if key == "liab_to_equity":
        return f"Liabilities / equity {v:.2f} (needs ≤ {C.QUIET_MAX_LIAB_TO_EQUITY:g})"
    if key == "dollar_vol_50":
        return f"Average daily $ volume {money(v)} (needs ≥ {money(_DOLLAR_VOL.get(cat, 0))})"
    if key == "market_cap":
        return (f"Market cap {money(v)} (needs {money(C.ACCEL_MIN_CAP_USD)}–"
                f"{money(C.ACCEL_MAX_CAP_USD)})")
    if key == "accelerating":
        return "Sales accelerating" if v else "Sales not accelerating"
    if key == "prior_yoy":
        return f"Prior-quarter sales {v:+.1f}% y/y (needs > {C.ACCEL_MIN_PRIOR_YOY_PCT:g}%)"
    return str(v)


def net_debt_text(v) -> str:
    if not _is_num(v):
        return DASH
    return f"Net debt / EBITDA {v:.2f}" + (" (net cash)" if v < 0 else "")


# ── 🧭 Pankaj ──
def pankaj_tier_text(tier, zt) -> str:
    return f"Pankaj: Tier {tier if tier is not None else DASH} · ZT {zt if zt is not None else DASH}"


def pankaj_zones_text(zones: dict, order) -> str:
    parts = []
    for zk in order or tuple(zones.keys()):
        lo, hi = (list(zones.get(zk) or (None, None)) + [None, None])[:2]
        if _is_num(lo) and _is_num(hi):
            parts.append(f"{zk} {lo:g}–{hi:g}")
    return " · ".join(parts) if parts else "No zones on Pankaj's sheet"


def zone_text(read: Optional[dict], zones: Optional[dict]) -> str:
    """One sentence for a criteria.zone_read result."""
    if not read:
        return "No cached close"
    if read.get("unknown"):
        return "No cached close" if read.get("n_zones") else "No zones on Pankaj's sheet"
    if not read.get("n_zones"):
        return "No zones on Pankaj's sheet"
    zones = zones or read.get("zones") or {}
    if read.get("in"):
        zk = read["in"][0]
        lo, hi = zones.get(zk) or (None, None)
        edges = f" ({lo:g}–{hi:g})" if _is_num(lo) and _is_num(hi) else ""
        return f"In Pankaj's {zk} zone{edges} at the {mmdd(read.get('close_date'))} close"
    n = read.get("nearest")
    if not n:
        return "No zones on Pankaj's sheet"
    if n["side"] == "over":
        return f"{n['pct']:.1f}% over Pankaj's {n['zone']} zone top ({n['edge']:g})"
    return f"{n['pct']:.1f}% under Pankaj's {n['zone']} zone low ({n['edge']:g})"


def zone_event_text(symbol, zone, lo, hi, date) -> str:
    edges = f" ({lo:g}–{hi:g})" if _is_num(lo) and _is_num(hi) else ""
    return f"🧭 {symbol} in Pankaj's {zone} zone{edges} at the {mmdd(date)} close"


def zones_strip_title(date) -> str:
    return f"🧭 In one of Pankaj's zones at the {mmdd(date)} close"


ZONES_ROWS_NOTE = (f"Pankaj's zones from his sheet, not re-screened. In a zone = the latest closed bar within "
                   f"{C.PANKAJ_ZONE_PAD_PCT:g}% of a zone edge (the /pankaj page's rule).")


# ── stage / sales ──
def stage_text(now, label, at_save) -> str:
    if now is None:
        head = "Stage not read this week"
    else:
        lab = stage_label(now, label)
        head = f"Stage {now}" + (f" · {lab}" if lab else "")
    if at_save is not None:
        head += f" (saved at Stage {at_save})"
    return head


def sales_text(pct=None, tier=None, q_end=None, read_on=None) -> str:
    """"Sales {pct:+.1f}% y/y · tier {tier} · quarter ended {q_end} · read {read_on}" —
    a missing part is dropped, never invented."""
    parts = []
    if _is_num(pct):
        parts.append(f"Sales {pct:+.1f}% y/y")
    if tier:
        parts.append(f"tier {tier}")
    if q_end:
        parts.append(f"quarter ended {q_end}")
    if read_on:
        parts.append(f"read {read_on}")
    if not parts:
        return DASH
    out = " · ".join(parts)
    return out[0].upper() + out[1:]


# ── status ──
STATUS_TEXTS = {
    "changed": "⚠️ Changed since it was saved — see the lines below",
    "started_moving": "🌱 → 🚀 Started moving this week",
    "not_read": "Not read this week — not dropped",
    "holding": "Holding — every list rule reads as it did",
}


def seed_only_status(first_read_date: Optional[str]) -> str:
    when = f" {first_read_date}" if first_read_date else ""
    return f"Saved {C.SAVED_ON} — first weekly read{when} after {RUN_AFTER_TEXT}"


def next_run_text(next_date) -> str:
    try:
        weekday = next_date.strftime("%A")
        iso = next_date.isoformat()
    except Exception:                                           # noqa: BLE001
        return f"Re-read weekly after the {RUN_AFTER_TEXT} re-rate on the last trading day of the week."
    return (f"Re-read weekly after the {RUN_AFTER_TEXT} re-rate on the last trading day of the week "
            f"— next: {weekday} {iso}.")


# ── events ──
def stage_drop_text(sym, n, label, last2_on) -> str:
    lab = stage_label(n, label)
    return f"⚠️ {sym} Stage 2 → Stage {n} ({lab}) — last read in Stage 2 on {last2_on}"


def sales_drop_text(sym, save_tier, now_tier, pct=None, q_end=None) -> str:
    bits = []
    if _is_num(pct):
        bits.append(f"y/y {pct:+.1f}%")
    if q_end:
        bits.append(f"quarter ended {q_end}")
    tail = f" ({', '.join(bits)})" if bits else ""
    down = " — sales now down y/y" if now_tier == "declining" else ""
    return f"⚠️ {sym} sales tier {save_tier} → {now_tier}{tail}{down}"


def fundamental_text(sym, cat, leg_texts) -> str:
    return f"⚠️ {sym} no longer meets {CATEGORY_LABELS.get(cat, cat)}: {'; '.join(leg_texts)}"


def started_moving_text(sym, label=None) -> str:
    return f"🌱 → 🚀 {sym} started moving: Stage 1 → Stage 2 ({stage_label(2, label)})"


def moved_text(sym, leg_texts) -> str:
    return f"{sym} {'; '.join(leg_texts)}"


def left_stage1_text(n, label=None) -> str:
    return f"left Stage 1 → Stage {n} · {stage_label(n, label)}"


def absent_text(sym, sources) -> str:
    names = ", ".join(SOURCE_LABELS.get(s, s) for s in sources)
    return f"{sym} not in this week's data ({names}) — not read, not dropped"


def top_new_text(cat, symbols) -> str:
    return f"✨ {CATEGORY_LABELS.get(cat, cat)} — new in this week's top: {', '.join(symbols)}"


def digest_title(session, n_dropped, n_started, n_zone) -> str:
    return (f"{C.MARK} Long Term — week of {session}: {n_dropped} dropped (stage or sales) · "
            f"{n_started} started moving · {n_zone} in Pankaj's zones")


def more_text(k) -> str:
    return f"+{k} more on the tab"


def pushed_text() -> str:
    if C.DIGEST_PUSH_MODE == "live":
        return "Sent to your phone as one weekly push."
    return "Phone push is off — this digest shows here only."


# ── strips ──
def top_text(cat, n) -> str:
    return (f"This week's top {n} from {SOURCE_TABS.get(cat, cat)} — not saved; ✨ = new to this strip. "
            f"At most {sector_cap_text(cat)} per sector.")


TOP_PENDING_TEXT = "This week's top shows after the first weekly read."


def sector_cap_text(cat) -> str:
    return str(C.HOT_MAX_PER_SECTOR if cat == "hot" else C.MAX_PER_SECTOR)


def rank_text(cat, values) -> str:
    v = values or {}
    try:
        if cat == "s2_growth":
            return f"RS rank {v['rs_rank']:g}"
        if cat == "capital_quality":
            return f"Moat score {v['moat_score']:g}"
        if cat == "undervalue":
            return f"P/S {v['ratio']:.2f}× the peer median"
        if cat == "bonde":
            return f"Bonde score {v['bonde_score']:g}"
        if cat == "fallen_growers":
            return f"Sales {v['sales_yoy_pct']:+.1f}% y/y"
        if cat == "hot":
            return f"One-month return {v['ret_21d']:+.1f}%"
        if cat == "quiet_strong":
            return f"Long-term score {v['score']:.1f}"
        if cat == "accel_after_fall":
            return f"Sales growth {v['growth_yoy_pct'] - v['prior_yoy_pct']:+.1f} points over the prior quarter"
    except Exception:                                           # noqa: BLE001
        return DASH
    return DASH


# ── caveats ──
def _ci(t) -> str:
    return f"{t[0]:+.2f}…{t[1]:+.2f}"


def bonde_caveat() -> str:
    from sepa import bonde
    m = bonde.MEASURED
    spans = all(m[k][0] < 0 < m[k][1] for k in ("tier_strong_ci", "tier_explosive_ci"))
    return (f"Bonde EP measured INVERTED: {m['lift_21d']:+.2f}pp vs placebo (CI {_ci(m['lift_ci'])}); "
            f"strong / explosive tier medians {m['tier_strong_med']:+.2f} / {m['tier_explosive_med']:+.2f}pp"
            f"{', CIs span zero' if spans else ''}. VIR/WAT/KDP sales jumps look like one-offs or acquisitions.")


def caveat(cat) -> str:
    if cat == "bonde":
        return bonde_caveat()
    if cat == "quiet_strong":
        if C.SCORE_IS_MEASURED:
            return "The long-term score has a measured read — see Ticker ▸ Fundamentals."
        return "The long-term score is UNMEASURED — it describes the filings, it does not predict the stock."
    return {
        "s2_growth": "UNMEASURED — a list of Stage 2 growers, not a measured edge.",
        "capital_quality": "UNMEASURED — moat components are proxies; the 💎 grade on 🚀 is unmeasured too.",
        "undervalue": ("UNMEASURED here; outside research (Lakonishok, Shleifer & Vishny) puts cheap and "
                       "fast-growing at about the market."),
        "fallen_growers": "UNMEASURED — no study in this app says a fallen grower comes back.",
        "hot": ("UNMEASURED as a list; the app's own sector-rotation backtest found the top sectors "
                "no better than RSP."),
        "accel_after_fall": "UNMEASURED — accelerating sales after a fall, nothing measured behind it.",
        "pankaj": (f"Pankaj's picks and Pankaj's zones from his sheet (read {C.SAVED_ON}) — not re-screened "
                   f"by this app; UNMEASURED here."),
    }.get(cat, "UNMEASURED.")


# ── criteria prose (built from the constants) ──
def criteria_text(cat) -> str:
    cap = f"{C.PER_CATEGORY} per list, at most {sector_cap_text(cat)} per sector"
    if cat == "s2_growth":
        return (f"Trend template passes · Stage {C.S2_STAGE} · sales tier {_tiers(C.S2_SALES_TIERS)} "
                f"(or {C.S2_STEADY_TIER} and accelerating) · strong quarterly and annual EPS (C and A) · "
                f"ranked by RS rank, ties by scan score · {cap}.")
    if cat == "capital_quality":
        return (f"Trend template passes · ROE ≥ {C.CQ_MIN_ROE_PCT:g}% · FCF margin > {C.CQ_MIN_FCF_MARGIN_PCT:g}% · "
                f"net debt / EBITDA known and ≤ {C.CQ_MAX_NET_DEBT_EBITDA:g} · ranked by moat score, ties by "
                f"scan score · {cap}.")
    if cat == "undervalue":
        return (f"On the 🏷️ vs-peers list (P/S at most {C.UV_PS_MAX_FRACTION:.0%} of the peer median) · "
                f"TTM revenue ≥ {money(C.UV_MIN_TTM_REVENUE_USD)} · latest-quarter sales ≥ "
                f"{C.UV_MIN_Q_YOY_PCT:g}% y/y · TTM growth ≥ {C.UV_MIN_TTM_GROWTH_PCT:g}% · "
                f"{C.FLOOR_TIER} liquidity floor · ranked by P/S vs peers · {cap}.")
    if cat == "bonde":
        return (f"Trend template passes · Bonde tier {_tiers(C.BONDE_TIERS)} · ranked by Bonde score, "
                f"ties by scan score · {cap}.")
    if cat == "fallen_growers":
        return (f"On the served 📉 page (first {C.FALLEN_PAGE}) · ≥ {C.FALLEN_MIN_PCT_BELOW:g}% under the "
                f"52-week high · ≥ {C.FALLEN_MIN_PCT_ABOVE_LOW:g}% over the 52-week low · sales ≥ "
                f"{C.FALLEN_MIN_SALES_YOY_PCT:g}% y/y · {C.FLOOR_TIER} liquidity floor · ranked by sales "
                f"growth · {cap}.")
    if cat == "hot":
        return (f"In its group's served top {C.HOT_PAGE} on 🔥 Hottest · sales tier {_tiers(C.HOT_SALES_TIERS)} · "
                f"quarterly EPS y/y > {C.HOT_MIN_Q_EPS_YOY:g}% · one-month return > {C.HOT_MIN_RET_21D:g}% · "
                f"ranked by one-month return · {cap}.")
    if cat == "quiet_strong":
        return (f"Stage {C.QUIET_STAGE} (price not moving yet) · long-term score ranked and ≥ "
                f"{C.QUIET_MIN_SCORE:g} · net profit > {money(C.QUIET_MIN_NET_PROFIT)} · operating cash flow > "
                f"{money(C.QUIET_MIN_OCF)} · sales CAGR ≥ {C.QUIET_MIN_SALES_CAGR_PCT:g}% · liabilities / equity ≤ "
                f"{C.QUIET_MAX_LIAB_TO_EQUITY:g} · current sales tier {_tiers(C.QUIET_SALES_TIERS)} · average daily "
                f"$ volume ≥ {money(C.QUIET_MIN_DOLLAR_VOL)} · ≥ {C.QUIET_MIN_PCT_BELOW_HIGH:g}% under the 52-week "
                f"high · net debt / EBITDA shown, not a rule · one share class per company · ranked by score · {cap}.")
    if cat == "accel_after_fall":
        return (f"Market cap {money(C.ACCEL_MIN_CAP_USD)}–{money(C.ACCEL_MAX_CAP_USD)} · sales tier "
                f"{_tiers(C.ACCEL_SALES_TIERS)} and accelerating · prior-quarter sales > "
                f"{C.ACCEL_MIN_PRIOR_YOY_PCT:g}% · ≥ {C.ACCEL_MIN_PCT_BELOW_HIGH:g}% under the 52-week high · ≥ "
                f"{C.ACCEL_MIN_PCT_ABOVE_LOW:g}% over the 52-week low · Stage {_stages(C.ACCEL_STAGES)} · average "
                f"daily $ volume ≥ {money(C.ACCEL_MIN_DOLLAR_VOL)} · profit shown, not a rule · ranked by sales "
                f"acceleration · {cap}.")
    if cat == "pankaj":
        return ("Pankaj's picks and his zones (Agg, C1, C2, C3) from his sheet — not screened, no list cap, "
                "no sector cap. The zone read uses the latest closed bar.")
    return DASH


def also_text(cat_doc: dict) -> Optional[str]:
    also = cat_doc.get("also_graded_on_growth_board")
    if isinstance(also, list) and also:
        return "Also graded 💎 on 🚀: " + ", ".join(str(s) for s in also)
    cons = cat_doc.get("also_considered")
    if isinstance(cons, dict) and cons:
        return "Also looked at and left out: " + "; ".join(f"{k} ({v})" for k, v in cons.items())
    return None


# ── forward ──
def forward_too_early(n, base, n_names) -> str:
    return (f"Too early — {n} of {C.FORWARD_MIN_SESSIONS} sessions since the {base} open. "
            f"Equal weight across the {n_names} screened names saved {C.SAVED_ON}.")


def forward_line(base, n, x, ci, n_rand, m, band, p, r, s) -> str:
    def f2(v):
        return f"{v:+.2f}%" if _is_num(v) else DASH
    ci_txt = f"{C.FORWARD_CI_PCT:g}% CI {ci[0]:+.2f}…{ci[1]:+.2f} across names" if ci and _is_num(ci[0]) else "no CI"
    band_txt = (f"{C.FORWARD_CI_PCT:g}% band {band[0]:+.2f}…{band[1]:+.2f}; the list sits at the {p:.0f}th percentile"
                if band and _is_num(band[0]) and _is_num(p) else "no band")
    return (f"Since the {base} open ({n} sessions): saved list {f2(x)} ({ci_txt}) · {n_rand} random names "
            f"from the same universe: median {f2(m)} ({band_txt}) · RSP {f2(r)} · SPY {f2(s)}. "
            f"One window — a tracking line, not a test.")


def forward_counts(k, s, c, base) -> str:
    return (f"{k} without a {base} price · {s} on an older close · {c} carried at their last stored price")


FORWARD_SERIES = [
    {"key": "list_pct", "label": "Saved list (equal weight)"},
    {"key": "rsp_pct", "label": C.BENCHMARK},
    {"key": "spy_pct", "label": C.BENCHMARK_ALT},
]


# ── rules ──
def _rule(key, label, text, consts) -> dict:
    srcs = sorted({C.CONSTANT_SOURCES.get(c, "APP") for c in consts}) or ["APP"]
    src = "MINE" if "MINE" in srcs else ("HIS" if "HIS" in srcs else "APP")
    return {"key": key, "label": label, "text": text, "source": src, "his_call": src == "MINE"}


_RULE_CONSTS = {
    "s2_growth": ("S2_STAGE", "S2_SALES_TIERS", "S2_EPS_CHECKS", "PER_CATEGORY", "MAX_PER_SECTOR"),
    "capital_quality": ("CQ_MIN_ROE_PCT", "CQ_MIN_FCF_MARGIN_PCT", "CQ_MAX_NET_DEBT_EBITDA"),
    "undervalue": ("UV_PS_MAX_FRACTION", "UV_MIN_Q_YOY_PCT", "UV_MIN_TTM_GROWTH_PCT", "UV_MIN_TTM_REVENUE_USD",
                   "MAX_PER_SECTOR"),
    "bonde": ("BONDE_TIERS",),
    "fallen_growers": ("FALLEN_MIN_PCT_BELOW", "FALLEN_MIN_PCT_ABOVE_LOW", "FALLEN_MIN_SALES_YOY_PCT"),
    "hot": ("HOT_SALES_TIERS", "HOT_MIN_Q_EPS_YOY", "HOT_MIN_RET_21D", "HOT_MAX_PER_SECTOR"),
    "quiet_strong": ("QUIET_MIN_SCORE", "QUIET_MIN_SALES_CAGR_PCT", "QUIET_MAX_LIAB_TO_EQUITY",
                     "QUIET_SALES_TIERS", "QUIET_MIN_DOLLAR_VOL", "QUIET_MIN_PCT_BELOW_HIGH"),
    "accel_after_fall": ("ACCEL_MIN_CAP_USD", "ACCEL_MAX_CAP_USD", "ACCEL_SALES_TIERS", "ACCEL_MIN_PCT_BELOW_HIGH",
                         "ACCEL_MIN_PCT_ABOVE_LOW", "ACCEL_STAGES", "ACCEL_MIN_DOLLAR_VOL"),
    "pankaj": ("PANKAJ_ZONE_PAD_PCT",),
}

NOTICE_TEXT = (f"Notices: Stage 2 → Stage {_stages(C.STAGE_DROP_TO)} (carried across in-between weeks), a sales "
               f"tier below its tier at save ({' < '.join(C.SALES_TIER_LADDER)}), and a 🌱 name moving Stage "
               f"{C.STARTED_MOVING_PAIR[0]} → Stage {C.STARTED_MOVING_PAIR[1]}. Only "
               f"{', '.join(C.RING_KINDS)} may ever ring; a list rule that fails shows ⚠️ here; a price rule "
               f"that flips is a plain line. Missing data is 'not read', never 'dropped'.")
SCHEDULE_TEXT = (f"Re-read weekly after the {RUN_AFTER_TEXT} re-rate on the last trading day of the week. "
                 f"The saved list never grows or shrinks; each list's weekly top is shown, not saved.")
FORWARD_METHOD_TEXT = (f"Forward record: equal weight across the screened names from the first session's open "
                       f"after {C.SAVED_ON}, against {C.BENCHMARK} and {C.BENCHMARK_ALT}; no number before "
                       f"{C.FORWARD_MIN_SESSIONS} sessions; then a {C.FORWARD_CI_PCT:g}% by-name bootstrap CI "
                       f"({C.FORWARD_BOOT_DRAWS} draws) and a random-names placebo ({C.FORWARD_PLACEBO_DRAWS} "
                       f"draws) from the same universe.")


def rules_lines(*, include_pankaj: bool = False) -> list:
    out = []
    for cat in C.SCREENED_KEYS:
        out.append(_rule(cat, CATEGORY_LABELS[cat], criteria_text(cat), _RULE_CONSTS[cat]))
    if include_pankaj:
        out.append(_rule(C.PANKAJ_KEY, CATEGORY_LABELS[C.PANKAJ_KEY],
                         criteria_text(C.PANKAJ_KEY) + " " + ZONES_ROWS_NOTE, _RULE_CONSTS["pankaj"]))
    out.append(_rule("notices", "Notices", NOTICE_TEXT, ("STAGE_DROP_PAIRS", "STARTED_MOVING_PAIR", "RING_KINDS")))
    out.append(_rule("schedule", "Schedule", SCHEDULE_TEXT, ()))
    out.append(_rule("push", "Phone push", pushed_text(), ("DIGEST_PUSH_MODE", "DIGEST_BODY_LINES")))
    out.append(_rule("forward", "Forward record", FORWARD_METHOD_TEXT,
                     ("FORWARD_BASE_KIND", "FORWARD_MIN_SESSIONS", "FORWARD_CI_PCT", "FORWARD_BOOT_DRAWS",
                      "FORWARD_PLACEBO_DRAWS")))
    return out
