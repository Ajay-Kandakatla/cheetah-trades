"""📰 News tab on Chart Maps — four served reads, one payload (Ajay 2026-09-24).

Ajay 2026-09-24: "build me a news tab in chartmaps to give me a bullish market
or bearsish market and also pull Macro calendar that has T1 and T2 tier events
in to this tab consider in to news. If bullish or beaish I need to whcih
sectors are bullish or which hotsectors are bearish. In a table."

Four blocks, each read from an engine that already ships, each budgeted on
its own and each failing on its own:

  * verdict   — the Market Gauge's daily AND weekly state (`sepa.market_gauge`),
                its word mapped ONCE in `MARKET_WORD`. Nothing is re-scored.
  * macro     — T1 + T2 rows of the FRED-scheduled calendar, read at the
                calendar's ONE cache key (`macro_calendar.DEFAULT_DAYS`). This
                module never passes a window length to the calendar: a second
                key would evict the gauge's doc and force a cold FRED fetch.
  * sectors   — the 🔥 Hottest board's sector rows (`rotation.hottest`),
                the 🔥/🧊 heat word from `rotation.heat`, the served 📰 day tag
                and the board's own `d1` block, which says whether the day
                column is the live session or the last close.
  * headlines — `news_search.core`, the app's ONE news routine.
  * model_read — 🧠 the local abliterated model's stored bull + bear read of
                the four blocks above (`news_model_read`, 2026-09-24). Served
                from Mongo; the model runs only in a background thread.

NOT A SIGNAL. Nothing here is measured to predict, nothing gates a scan,
pushes a phone, sizes a position or enters a lane. The sector-heat study is
served beside the table with its confidence intervals; the 5-session heat
that decides the word is UNMEASURED.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Optional

import macro_calendar
from news_search import core
from rotation import heat
from rotation import hottest as H
from rotation import tracker as T

from . import news_model_read

log = logging.getLogger("chart_maps.news_tab")

# THE one map from the gauge's state key to the word the tab prints.
MARKET_WORD = {"constructive": "bullish", "caution": "mixed", "risk_off": "bearish"}
UNKNOWN_WORD = "unknown"
AUDIT_TAG = "chart_maps_news"
# news.py's own Google query for the market feed, reused as a keyword through
# the ONE news routine — not a second fetcher.
MARKET_QUERY = "stock market OR Nasdaq OR S&P 500"
# ONE request budget, applied to EVERY leg. A leg past it serves ok=False with
# a reason; its thread keeps running so the module caches (gauge, 6 h
# calendar, rotation doc) still warm for the next refresh.
LEG_BUDGET_SEC = 8.0
TIMED_OUT = "still loading — timed out after {:.0f}s, refresh"
NOTE = ("A read of what the app already serves — the Market Gauge's state, the FRED-scheduled macro calendar, "
        "the rotation grid's sector medians against RSP, and the last 36 hours of market headlines. "
        "Nothing here is a forecast, nothing here is measured to predict, and nothing here gates a scan, "
        "pushes a phone, sizes a position or enters a lane. Not advice.")
SECTOR_STUDY = {
    "measured_on": "rel_21d", "shipped_on": heat.HEAT_KEY, "date": "2026-09-09",
    "arrivals": 50191, "dates": 192, "names": 2243,
    "hot_win_rate_pp": -0.57, "hot_win_rate_ci": [-1.87, 0.71],
    "hot_minus_cold_5d_pp": -2.55, "hot_minus_cold_5d_ci": [-4.48, -0.65],
    "script": "backend/studies/sector_heat_study.py", "doc": "docs/supply_demand/sector_heat.md",
    "note": ("Sector heat describes what already moved; it is not a forecast. MEASURED 2026-09-09 on the "
             "rel_21d definition over 50,191 demand-zone arrivals: a hot sector changed the win rate by "
             "−0.57pp (95% CI −1.87 to +0.71) — nothing. 'A cold sector just sits there' measured INVERTED: "
             "at 5 sessions hot minus cold was −2.55pp (95% CI −4.48 to −0.65), the one interval in the study "
             "clear of zero — cold turned faster. The 🔥/🧊 word on this table is decided on the 5-session leg "
             "(rel_5d), which is UNMEASURED; the 21-day null neither validates nor condemns it. "
             "Script: backend/studies/sector_heat_study.py."),
}
_NO_D1 = "no day block served"


def _num(v) -> Optional[float]:
    """Finite floats only; bools, junk, NaN and inf are None."""
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def market_word(state) -> str:
    """The gauge state key → bullish / mixed / bearish. Exact key only; any
    other value (a label, a word, a number, None) is UNKNOWN. Never raises."""
    if not isinstance(state, str):
        return UNKNOWN_WORD
    return MARKET_WORD.get(state, UNKNOWN_WORD)


def leg_word(v) -> str:
    """Sign of a relative-strength leg vs the benchmark. 0 is flat."""
    f = _num(v)
    if f is None:
        return UNKNOWN_WORD
    if f > 0:
        return "bullish"
    if f < 0:
        return "bearish"
    return "flat"


def _gauge_card(g: dict) -> dict:
    state = g.get("state")
    return {"score": g.get("score"), "state": state,
            "state_label": g.get("state_label"), "word": market_word(state)}


def verdict_block(gauge: Optional[dict]) -> dict:
    """The gauge's daily and weekly state, each with its word. PURE."""
    if not isinstance(gauge, dict) or not gauge:
        return {"ok": False, "reason": "market gauge unavailable"}
    daily = _gauge_card(gauge)
    wk = gauge.get("weekly")
    weekly = _gauge_card(wk) if isinstance(wk, dict) and wk else None
    outlook = gauge.get("next_day_outlook") or {}
    if not isinstance(outlook, dict):
        outlook = {}
    return {
        "ok": True,
        "as_of_label": gauge.get("as_of_label"),
        "generated_at_iso": gauge.get("generated_at_iso"),
        "daily": daily,
        "weekly": weekly,
        "agree": None if weekly is None else (daily["state"] == weekly["state"]),
        "drivers": list(gauge.get("drivers") or []),
        "outlook": {"label": outlook.get("label"), "note": outlook.get("note"),
                    "watch": list(outlook.get("watch") or [])},
        "disclaimer": gauge.get("disclaimer"),
    }


def macro_block() -> dict:
    """T1 + T2 macro rows at the calendar's ONE cache key.

    Both calls take the calendar's defaults — never a window argument (C1):
    `imminent_events` reads `get_macro_calendar()` at its default key, so a
    different key here would evict that doc and pay a second cold compute.
    """
    try:
        cal = macro_calendar.get_macro_calendar() or {}
        events = macro_calendar.imminent_events(within_days=macro_calendar.DEFAULT_DAYS,
                                                max_tier=2)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("news_tab: macro calendar unavailable: %s", exc)
        return {"ok": False, "reason": f"macro calendar unavailable ({type(exc).__name__})",
                "days": macro_calendar.DEFAULT_DAYS, "events": []}
    rows = []
    for e in events or []:
        tier = e.get("tier")
        if tier not in (1, 2):
            continue
        rows.append({"date": e.get("date"), "kind": e.get("kind"), "tier": tier,
                     "tier_label": macro_calendar.TIER_LABELS.get(tier),
                     "label": e.get("label"), "days_until": e.get("days_until"),
                     "when_label": e.get("when_label")})
    labels = cal.get("tier_labels") or macro_calendar.TIER_LABELS
    return {
        "ok": True,
        "days": macro_calendar.DEFAULT_DAYS,
        "tier_labels": {str(k): v for k, v in labels.items()},
        "next_tier1": cal.get("next_tier1"),
        "events": rows,
        "disclaimer": cal.get("disclaimer"),
    }


def d1_block(body: dict) -> dict:
    """What the day column is showing, from the board's own `d1` block. PURE.
    `moves` (one float per priced name) is never carried."""
    d1 = (body or {}).get(H.D1_KEY) if isinstance(body, dict) else None
    if not isinstance(d1, dict) or not d1:
        return {"live": False, "basis": None, "as_of": None,
                "reason": _NO_D1, "market_closed": None}
    return {"live": d1.get("live") is True, "basis": d1.get("basis"),
            "as_of": d1.get("as_of"), "reason": d1.get("reason"),
            "market_closed": d1.get("market_closed")}


def _heat_of(sector, index: dict) -> dict:
    r = None
    try:
        r = heat.read("", index, sector=sector) if sector else None
    except Exception as exc:                                   # noqa: BLE001
        log.debug("news_tab: heat read %s failed: %s", sector, exc)
    if not isinstance(r, dict):
        return {"tone": UNKNOWN_WORD, "percentile": None,
                "heat_window": heat.HEAT_WINDOW, "thin": None, "grain": None}
    return {"tone": r.get("tone") or UNKNOWN_WORD, "percentile": r.get("percentile"),
            "heat_window": r.get("heat_window"), "thin": r.get("thin"),
            "grain": r.get("grain")}


def sector_rows(body: dict, index: dict) -> list:
    """One row per served sector, in SERVED order. PURE."""
    out = []
    bench = (body or {}).get("benchmark")
    for s in (body or {}).get("sectors") or []:
        if not isinstance(s, dict):
            continue
        rel_1d = s.get("rel_1d")
        d1 = _num(rel_1d)
        h = _heat_of(s.get("group"), index)
        names = s.get("names") or []
        first = names[0] if names and isinstance(names[0], dict) else None
        out.append({
            "sector": s.get("group"), "n": s.get("n_full"), "benchmark": bench,
            "rel_1d": rel_1d, "rel_5d": s.get("rel_5d"), "rel_21d": s.get("rel_21d"),
            "pct_positive_1d": s.get("pct_positive_1d"),
            "read": {"1d": leg_word(rel_1d), "5d": leg_word(s.get("rel_5d")),
                     "21d": leg_word(s.get("rel_21d"))},
            "heat": h,
            "hot_lagging_1d": h["tone"] == "hot" and d1 is not None and d1 < 0,
            "cold_leading_1d": h["tone"] == "cold" and d1 is not None and d1 > 0,
            "leader": first.get("symbol") if first else None,
            "day_tag": s.get("day_tag"),
        })
    return out


def headlines_block(res: Optional[dict]) -> dict:
    """Trim a `core.search` result to what the tab prints. PURE."""
    if not isinstance(res, dict):
        return {"ok": False, "reason": "headlines unavailable", "items": []}
    items = []
    for it in res.get("items") or []:
        if not isinstance(it, dict):
            continue
        items.append({k: it.get(k) for k in ("title", "url", "source", "published", "provider")})
    return {"ok": True, "items": items, "window_hours": res.get("window_hours"),
            "query": res.get("query"), "counts": res.get("counts"),
            "fetched_at": res.get("fetched_at")}


def _timed_out() -> dict:
    return {"ok": False, "reason": TIMED_OUT.format(LEG_BUDGET_SEC)}


# ── the four legs (each runs in ONE worker thread) ─────────────────────────
def _gauge_leg() -> dict:
    from sepa import market_gauge
    return verdict_block(market_gauge.get_gauge())


def _macro_leg() -> dict:
    return macro_block()


def _sectors_leg() -> dict:
    """Mirrors `rotation/api.py` /rotation/hottest: never builds the member
    table, reads the persisted payload ONCE and reuses it for the heat index,
    and wraps the day-tag attach exactly as the route does."""
    from rotation import api as RA
    from rotation import sector_news_tags as SNT
    table, meta = RA._members_table()
    meta = meta if isinstance(meta, dict) else {}
    if table is None:
        return {"ok": False, "reason": meta.get("reason") or "member table unavailable",
                "rows": []}
    base = RA._members_payload() or {}
    payload = dict(base)
    payload[T.MEMBERS_KEY] = table
    body = H.build_live(payload, sort=H.DEFAULT_SORT, direction=H.DEFAULT_DIR,
                        names_per_group=1, basis=H.D1_CLOSE)
    try:
        SNT.attach(body, SNT.latest_within())
    except Exception as exc:                                   # noqa: BLE001
        log.warning("news_tab: day tags unavailable: %s", exc)
        for s in body.get("sectors") or []:
            if isinstance(s, dict):
                s.setdefault("day_tag", None)
    index = heat.build_index(base)
    rows = sector_rows(body, index)
    tags_date = next((r["day_tag"].get("date") for r in rows
                      if isinstance(r.get("day_tag"), dict) and r["day_tag"].get("date")), None)
    return {"ok": True, "as_of": body.get("as_of"), "benchmark": body.get("benchmark"),
            "ranked_by": H.DEFAULT_SORT, "heat_window": heat.HEAT_WINDOW,
            "d1": d1_block(body), "rows": rows, "tags_date": tags_date,
            "study": SECTOR_STUDY, "source": meta.get("source"),
            "built_at_iso": meta.get("built_at_iso"), "stale": meta.get("stale")}


def _news_leg() -> dict:
    # search_sync is core's own sync wrapper around core.search — the audit
    # write inside it is blocking Mongo, so it runs in this worker thread.
    return headlines_block(core.search_sync(keyword=MARKET_QUERY, audit=AUDIT_TAG))


def _settle(res) -> dict:
    if isinstance(res, asyncio.TimeoutError):
        return _timed_out()
    if isinstance(res, BaseException):
        return {"ok": False, "reason": str(res)[:200] or type(res).__name__}
    return res


async def build() -> dict:
    """The whole tab. Every leg gets `LEG_BUDGET_SEC`; a slow or broken leg
    costs its own block and never the other three."""
    legs = (_gauge_leg, _macro_leg, _sectors_leg, _news_leg)
    got = await asyncio.gather(
        *(asyncio.wait_for(asyncio.to_thread(fn), LEG_BUDGET_SEC) for fn in legs),
        return_exceptions=True)
    verdict, macro, sectors, headlines = (_settle(r) for r in got)
    body = {
        "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verdict": verdict, "macro": macro, "sectors": sectors, "headlines": headlines,
        "budget_sec": LEG_BUDGET_SEC, "note": NOTE, "measured": False,
    }
    # 🧠 the local model's stored two-sided read. A Mongo read on the request;
    # the model itself only ever runs in news_model_read's background thread.
    try:
        read = await asyncio.wait_for(asyncio.to_thread(news_model_read.served, body), LEG_BUDGET_SEC)
    except Exception as exc:                                   # noqa: BLE001
        read = _settle(exc)
    body["model_read"] = read
    return body
