"""🧬 Medical catalysts — API payloads (spec §3.10).

GET /catalysts/medical            -> board_payload
GET /catalysts/medical/{symbol}   -> symbol_payload

UNMEASURED everywhere: `labels` carries the served note and
`setup: "pending study"`; no row carries an entry, stop or target. The 🔥
roll-up is descriptive — medians of what the names did after their news, ONE
observation per (ticker, session) per group — with no placebo and no twins.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from . import reaction as R

log = logging.getLogger("catalysts.medical.board")

ROLLUP_NOTE = ("Descriptive and UNMEASURED: medians of what these names did after their news in this "
               "window, one observation per name per session. No placebo, no twins, not a signal.")
SMALL_N_TICKERS = 5
ROLL_TICKERS_MAX = 8
SOURCES = [{"key": "finnhub", "label": "Company news (Finnhub)"},
           {"key": "sec", "label": "SEC 8-K press releases (EX-99.1)"},
           {"key": "massive", "label": "Market-wide news (Massive)"},
           {"key": "fda_rss", "label": "FDA press releases"}]
_NEG_TYPES = ("fda_crl", "fda_revoked")


def _tax():
    from . import taxonomy
    return taxonomy


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


def _iso_et(ts) -> Optional[str]:
    e = R.as_et(ts)
    return e.isoformat() if e else None


def labels() -> dict:
    T = _tax()
    return {"measured": bool(T.MEASURED), "status": T.STATUS, "setup": T.SETUP_STATUS,
            "note": T.UNMEASURED_NOTE}


def taxonomy_payload() -> dict:
    T = _tax()
    return {"event_types": [{"key": k, "label": v.get("label"), "family": v.get("family"),
                             "emoji": v.get("emoji")} for k, v in T.EVENT_TYPES.items()],
            "families": [{"key": k, "label": lbl, "emoji": em} for k, lbl, em in T.EVENT_FAMILIES],
            "modalities": [{"key": k, "label": v} for k, v in T.MODALITIES.items()],
            "areas": [{"key": k, "label": v} for k, v in T.AREAS.items()],
            "high_impact_text": T.HIGH_IMPACT_TEXT}


def sign(ev: dict) -> int:
    """+1 / −1 / 0 for the roll-up's positive / negative counts."""
    t, d = ev.get("event_type"), ev.get("direction")
    if t in ("topline", "adcom", "conference_data"):
        return 1 if d == "positive" else (-1 if d == "negative" else 0)
    if t == "fda_approval":
        return 1
    if t in _NEG_TYPES or (t == "clinical_hold" and ev.get("subtype") == "placed"):
        return -1
    return 0


def row(ev: dict) -> dict:
    from .alerts import area_primary, modality_primary
    T = _tax()
    et = ev.get("event_type")
    reac = ev.get("reaction") or {}
    liq = reac.get("liquidity") or {}
    push = ev.get("push") or {}
    t = ev.get("ticker")
    det = reac.get("at_detection") or {}
    return {
        "event_key": ev.get("_id"), "ticker": t, "company": ev.get("company"),
        "event_type": et, "family": (T.EVENT_TYPES.get(et) or {}).get("family"),
        "type_dir": ev.get("type_dir"), "label": T.event_label(ev), "subtype": ev.get("subtype"),
        "direction": ev.get("direction"), "phase": ev.get("phase"), "regulator": ev.get("regulator"),
        "trials": list(ev.get("trials") or []),
        "impact": "high" if T.is_high_impact(ev) else "low",
        "modality": list(ev.get("modality") or ["unclassified"]),
        "modality_primary": modality_primary(ev.get("modality")) or "unclassified",
        "areas": list(ev.get("areas") or ["unclassified"]),
        "area_primary": area_primary(ev.get("areas")) or "unclassified",
        "headline": ev.get("headline"),
        "published_at_et": _iso_et(ev.get("published_at")),
        "first_seen_at_et": _iso_et(ev.get("first_seen_at")),
        "latency_min": det.get("latency_min"),
        "session_date": str(ev.get("session_date")), "released": ev.get("released"),
        "sources": [{"provider": s.get("provider"), "source": s.get("source"), "title": s.get("title"),
                     "url": s.get("url"), "published_et": s.get("published_et")}
                    for s in (ev.get("sources") or [])],
        "n_sources": len(ev.get("sources") or []),
        "push": {"state": push.get("state"), "reason": push.get("reason"), "at_et": _iso_et(push.get("at"))},
        # fix round 3: shadow mode's record — {value, reason, mode, title?}; None before a shadow pass
        "would_push": ({k: v for k, v in (ev.get("would_push") or {}).items() if k != "at"}
                       or None),
        "reaction": {"at_detection": reac.get("at_detection"), "at_close": reac.get("at_close"),
                     "fwd": reac.get("fwd")},
        "liquidity": {k: liq.get(k) for k in ("base_close", "base_basis", "adv50_usd", "avg_vol50",
                                              "pre_ret_20d_pct", "market_cap")},
        "dilutive": ev.get("dilutive"),
        "links": ({"supply": f"/sepa/{t}?tab=supply", "timeline": f"/sepa/{t}?tab=catalyst"}
                  if t else {"supply": None, "timeline": None}),
    }


def _move(r: dict) -> float:
    reac = r.get("reaction") or {}
    v = _f((reac.get("at_close") or {}).get("day_pct"))
    if v is None:
        v = _f((reac.get("at_detection") or {}).get("move_pct"))
    return abs(v) if v is not None else -1.0


def sort_rows(rows: list) -> list:
    rows = sorted(rows, key=lambda r: r.get("first_seen_at_et") or "", reverse=True)
    rows = sorted(rows, key=_move, reverse=True)
    rows = sorted(rows, key=lambda r: 0 if r.get("impact") == "high" else 1)
    return sorted(rows, key=lambda r: r.get("session_date") or "", reverse=True)


def _median(xs: list) -> Optional[float]:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2.0


def rollup(rows: list, field: str, label_map: dict) -> list:
    """One ROLL per key of `field` ("modality" | "areas"). Medians use ONE
    observation per (ticker, session_date) per group; small_n counts UNIQUE
    tickers; an event with two keys counts once in each."""
    groups: dict = {}
    for r in rows:
        for k in (r.get(field) or ["unclassified"]):
            groups.setdefault(k, []).append(r)
    out = []
    for k, rs in groups.items():
        obs: dict = {}
        for r in rs:
            t = r.get("ticker")
            if not t:
                continue
            key = (t, r.get("session_date"))
            reac = r.get("reaction") or {}
            cur = obs.setdefault(key, {"day": None, "r5": None, "r21": None})
            if cur["day"] is None:
                cur["day"] = _f((reac.get("at_close") or {}).get("day_pct"))
            if cur["r5"] is None:
                cur["r5"] = _f((reac.get("fwd") or {}).get("ret_5d_pct"))
            if cur["r21"] is None:
                cur["r21"] = _f((reac.get("fwd") or {}).get("ret_21d_pct"))
        tickers = sorted({r.get("ticker") for r in rs if r.get("ticker")})
        day = [o["day"] for o in obs.values() if o["day"] is not None]
        r5 = [o["r5"] for o in obs.values() if o["r5"] is not None]
        r21 = [o["r21"] for o in obs.values() if o["r21"] is not None]
        signs = [sign(r) for r in rs]
        out.append({"key": k, "label": label_map.get(k, k), "n_events": len(rs),
                    "n_high": sum(1 for r in rs if r.get("impact") == "high"),
                    "n_positive": sum(1 for s in signs if s > 0),
                    "n_negative": sum(1 for s in signs if s < 0),
                    "n_obs": len(obs), "median_day_pct": _median(day), "n_day": len(day),
                    "median_ret_5d_pct": _median(r5), "n_5d": len(r5),
                    "median_ret_21d_pct": _median(r21), "n_21d": len(r21),
                    "n_tickers": len(tickers), "small_n": len(tickers) < SMALL_N_TICKERS,
                    "tickers": tickers[:ROLL_TICKERS_MAX]})
    out.sort(key=lambda x: (-x["n_events"], str(x["label"])))
    return out


def _events(coll, since: date, query: Optional[dict] = None) -> list:
    from . import store as S
    return S.events_since(coll, since, query=query)


def _filter(rows: list, *, type: Optional[str], modality: Optional[str], area: Optional[str],
            high_only: bool) -> list:
    out = []
    for r in rows:
        if type and r.get("event_type") != type and r.get("family") != type and r.get("type_dir") != type:
            continue
        if modality and modality not in (r.get("modality") or []):
            continue
        if area and area not in (r.get("areas") or []):
            continue
        if high_only and r.get("impact") != "high":
            continue
        out.append(r)
    return out


def board_payload(days: int = 30, type: Optional[str] = None, modality: Optional[str] = None,
                  area: Optional[str] = None, high_only: bool = False, *, events_coll=None,
                  pass_coll=None, now: Optional[datetime] = None) -> dict:
    from . import store as S
    from .alerts import KIND, gate_text
    T = _tax()
    now_et = R.as_et(now) if now else datetime.now(R.ET)
    since = now_et.date() - timedelta(days=int(days))
    if events_coll is None:
        events_coll = S.colls().get(S.EVENTS)
    all_rows = sort_rows([row(e) for e in _events(events_coll, since)])
    rows = _filter(all_rows, type=type, modality=modality, area=area, high_only=high_only)
    try:
        from supply_demand import alert_status as AS
        pass_doc = AS.read_pass(KIND, pass_coll)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("medical.board: pass read failed: %s", exc)
        pass_doc = {"as_of": None, "date": None, "counts": {}}
    return {
        "as_of": now_et.isoformat(), "window_days": int(days),
        "labels": labels(), "taxonomy": taxonomy_payload(),
        "events": rows,
        "rollup": {"by_modality": rollup(all_rows, "modality", T.MODALITIES),
                   "by_area": rollup(all_rows, "areas", T.AREAS),
                   "note": ROLLUP_NOTE, "window_days": int(days)},
        "counts": {"events": len(rows), "high_impact": sum(1 for r in rows if r["impact"] == "high"),
                   "unclassified_modality": sum(1 for r in rows if r["modality"] == ["unclassified"]),
                   "unresolved_ticker": sum(1 for r in rows if not r.get("ticker"))},
        "pass": pass_doc,
        "sources": SOURCES,
        "push": {"kind": KIND, "gate_text": gate_text()},
    }


def symbol_payload(symbol: str, days: int = 180, *, events_coll=None, state_coll=None,
                   now: Optional[datetime] = None) -> dict:
    from . import store as S
    sym = (symbol or "").strip().upper()
    now_et = R.as_et(now) if now else datetime.now(R.ET)
    since = now_et.date() - timedelta(days=int(days))
    c = None
    if events_coll is None or state_coll is None:
        c = S.colls()
    events_coll = events_coll if events_coll is not None else c.get(S.EVENTS)
    state_coll = state_coll if state_coll is not None else c.get(S.STATE)
    rows = [row(e) for e in _events(events_coll, since, {"ticker": sym})]
    rows.sort(key=lambda r: (r.get("session_date") or "", r.get("first_seen_at_et") or ""), reverse=True)
    lap = (S.get_state(state_coll, "baseline") or {}).get("lap_complete_at")
    lap_et = R.as_et(lap)
    return {"symbol": sym, "as_of": now_et.isoformat(), "labels": labels(), "events": rows,
            "tracking_since": lap_et.date().isoformat() if lap_et else None}


__all__ = ["board_payload", "symbol_payload", "rollup", "row", "sort_rows", "labels", "ROLLUP_NOTE",
           "SOURCES", "sign"]
