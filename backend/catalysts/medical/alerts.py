"""🧬 med_catalyst push — gate, wording, claim, send (spec §3.8).

Ajay 2026-09-29: "…and add right setup and alerts". The kind ships ON for the
owner only (push.subs.OWNER_KEEP_SET — the key_level_alert precedent), False
in default_prefs for everyone else. HIS CALL #1 turns it off with one word.

UNMEASURED. A push is "this happened", never "buy this": every title ends
"UNMEASURED, not a buy signal" / "UNMEASURED, not a sell signal", and no
entry, stop or target is ever sent (setup: pending study).

Gate order (each reason is a counter; `gate()` is pure):
   1 not_high_impact      taxonomy.is_high_impact — the ONLY definition (board chip + push)
   2 unresolved_ticker    no issuer -> never pushed
   3 baseline             created before the first full roster lap / a feed's first run
   4 recap                same name + type_dir already pushed/muted/baseline within RECAP_SESSIONS
   5 closed_day           market_hours.gate.closed_reason — checked BEFORE any claim;
                          the event stays `pending` and is re-evaluated next trading day
   6 stale                the regular session has traded the news > RTH_EXPOSURE_MAX_MIN
   7 blocked_unknown_liquidity  base close or ADV unknown -> fail CLOSED
   8 blocked_price        base close < trading.safety_floor.MIN_SHARE_PRICE
   9 blocked_dollar_vol   50-session median $ volume < trading.safety_floor.THIN_DOLLAR_VOL
  10 topline claim        MC:{TICKER}|topline|{session}  (one topline push per name per session)
  11 event claim          MC:{event_key}                 (once per event)
Send: not terminal -> release BOTH claims (retry next pass); sent > 0 -> pushed;
total_targets == 0 (pref off / quiet hours / no device) -> muted, claims KEPT —
house semantics: a quiet-hours event never rings later.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from . import reaction as R

log = logging.getLogger("catalysts.medical.alerts")

KIND = "med_catalyst"
MAX_SINGLES = 3
DIGEST_MAX_LINES = 6
# The routine rides `*/5 4-19 * * 1-5 … catalysts.promo_live` (backend/crontab:459);
# supply_demand.alert_status.CADENCE_SEC["med_catalyst"] is pinned to that line.
CADENCE_SEC = 300
RTH_EXPOSURE_MAX_MIN = 2 * CADENCE_SEC / 60     # = 10 — two passes of the ride-along cadence; HIS CALL #7
RECAP_SESSIONS = R.FWD_SESSIONS[1]              # = 21 — HIS CALL #8
PUSHED_LIKE = ("pushed", "muted", "baseline")
BUY_TAIL = "UNMEASURED, not a buy signal"
SELL_TAIL = "UNMEASURED, not a sell signal"
BOARD_URL = "/chart-maps?tab=catalysts&sub=medical"

REASON_STATE = {
    "not_high_impact": "not_eligible",
    "unresolved_ticker": "not_eligible",
    "baseline": "baseline",
    "recap": "not_eligible:recap",
    "closed_day": "pending",
    "stale": "blocked:stale",
    "blocked_unknown_liquidity": "blocked:unknown_liquidity",
    "blocked_price": "blocked:price",
    "blocked_dollar_vol": "blocked:dollar_vol",
    "claimed_elsewhere": "blocked:claimed_elsewhere",
}


def _tax():
    from . import taxonomy
    return taxonomy


def _floors():
    from trading import safety_floor as SF
    return SF


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


def liquidity_of(ev: dict) -> dict:
    return ((ev.get("reaction") or {}).get("liquidity") or {})


def detection_of(ev: dict) -> dict:
    return ((ev.get("reaction") or {}).get("at_detection") or {})


def _sd(ev: dict):
    from datetime import date
    s = ev.get("session_date")
    return s if isinstance(s, date) else date.fromisoformat(str(s)[:10])


def gate(ev: dict, *, now_et: datetime, baseline: bool, prior: list) -> Optional[str]:
    """None = may push (claims next); else the reason key. PURE apart from the
    calendar tables (market_hours)."""
    T = _tax()
    if not T.is_high_impact(ev):
        return "not_high_impact"
    if not ev.get("ticker"):
        return "unresolved_ticker"
    if baseline:
        return "baseline"
    sd = _sd(ev)
    floor = R.add_market_days(sd, -RECAP_SESSIONS)
    for p in prior or []:
        if p.get("_id") == ev.get("_id"):
            continue
        if p.get("ticker") != ev.get("ticker") or p.get("type_dir") != ev.get("type_dir"):
            continue
        if ((p.get("push") or {}).get("state")) not in PUSHED_LIKE:
            continue
        try:
            psd = _sd(p)
        except (TypeError, ValueError):
            continue
        if floor <= psd < sd:
            return "recap"
    from market_hours import gate as MG
    if MG.closed_reason(R.as_et(now_et)):
        return "closed_day"
    if R.rth_minutes_between(ev.get("published_at"), now_et) > RTH_EXPOSURE_MAX_MIN:
        return "stale"
    liq = liquidity_of(ev)
    base, adv = _f(liq.get("base_close")), _f(liq.get("adv50_usd"))
    if base is None or adv is None:
        return "blocked_unknown_liquidity"
    SF = _floors()
    if base < SF.MIN_SHARE_PRICE:
        return "blocked_price"
    if adv < SF.THIN_DOLLAR_VOL:
        return "blocked_dollar_vol"
    return None


# ---------------------------------------------------------------------------
# wording (pinned by tests)
# ---------------------------------------------------------------------------
def area_primary(areas) -> Optional[str]:
    T = _tax()
    real = [a for a in (areas or []) if a and a != "unclassified"]
    for a in T.AREA_PRIORITY:
        if a in real:
            return a
    return real[0] if real else None


def modality_primary(mods) -> Optional[str]:
    T = _tax()
    real = [m for m in (mods or []) if m and m != "unclassified"]
    for m in T.MODALITY_PRIORITY:
        if m in real:
            return m
    return real[0] if real else None


def area_label(ev: dict) -> str:
    a = area_primary(ev.get("areas"))
    return _tax().AREAS.get(a, a) if a else "area unclassified"


def move_text(ev: dict) -> str:
    mv = _f(detection_of(ev).get("move_pct"))
    return f"{mv:+.0f}%" if mv is not None else "no print yet"


def tail(ev: dict) -> str:
    t = ev.get("event_type")
    d = ev.get("direction")
    if t in ("fda_crl", "clinical_hold") or (t == "topline" and d == "negative"):
        return SELL_TAIL
    return BUY_TAIL


def _hhmm(ts) -> str:
    e = R.as_et(ts)
    return e.strftime("%H:%M") if e else "—"


def single_text(ev: dict) -> dict:
    T = _tax()
    sym = str(ev["ticker"]).upper()
    title = f"🧬 {sym} · {T.event_label(ev)} · {area_label(ev)} · {move_text(ev)} · {tail(ev)}"
    det, liq = detection_of(ev), liquidity_of(ev)
    base, price = _f(liq.get("base_close")), _f(det.get("price"))
    trial = (ev.get("trials") or [None])[0]
    srcs = ev.get("sources") or []
    prov = (srcs[0].get("provider") if srcs else None) or "—"
    print_txt = (f"{det.get('session') or 'closed'} print ${price:.2f} at {_hhmm(det.get('as_of'))} ET"
                 if price is not None else "no print yet")
    base_txt = f"vs ${base:.2f} prior close" if base is not None else "prior close unknown"
    body = (f"{ev.get('company') or sym} · {trial or '—'} · {base_txt}, {print_txt} · "
            f"first seen {_hhmm(ev.get('first_seen_at'))} ET via {prov} ({len(srcs)} sources)")
    url = f"/sepa/{sym}?tab=catalyst"
    return {"title": title, "body": body, "icon": "/icon.svg", "url": url,
            "tag": f"med-{sym.lower()}-{ev.get('type_dir')}", "kind": KIND, "ticker": sym,
            "data": {"url": url, "symbol": sym, "event_key": ev.get("_id"), "source": KIND}}


def digest_text(evs: list) -> dict:
    T = _tax()
    n = len(evs)
    lines = [f"{str(e['ticker']).upper()} · {T.event_label(e)} · {move_text(e)}" for e in evs[:DIGEST_MAX_LINES]]
    k = n - min(n, DIGEST_MAX_LINES)
    if k > 0:
        lines.append(f"+{k} more on Chart Maps ▸ Catalysts ▸ 🧬 Medical")
    return {"title": f"🧬 {n} more medical catalysts", "body": "\n".join(lines), "icon": "/icon.svg",
            "url": BOARD_URL, "tag": "med-digest", "kind": KIND, "ticker": None,
            "tickers": [str(e["ticker"]).upper() for e in evs],
            "data": {"url": BOARD_URL, "source": KIND}}


def gate_text() -> str:
    """The gate in words, every number read from its constant (rules_info + board)."""
    T = _tax()
    SF = _floors()
    return (f"{T.HIGH_IMPACT_TEXT}; prior close ≥ ${SF.MIN_SHARE_PRICE:.0f} and 50-session median "
            f"dollar volume ≥ ${SF.THIN_DOLLAR_VOL / 1e6:.0f}M; only while the regular session has "
            f"traded the news ≤ {RTH_EXPOSURE_MAX_MIN:.0f} minutes; not a repeat of the same kind on "
            f"the name within {RECAP_SESSIONS} sessions; one topline push per name per session; once "
            f"per event; {MAX_SINGLES} ring individually then one digest.")


# ---------------------------------------------------------------------------
# claims + send
# ---------------------------------------------------------------------------
def _default_send(owner: str, msg: dict, kind: str) -> dict:
    from push import hooks
    return hooks.notify_med_catalyst(owner=owner, payload=msg)


def _rank(ev: dict) -> tuple:
    mv = _f(detection_of(ev).get("move_pct"))
    return (-(abs(mv) if mv is not None else -1.0), str(ev.get("_id")))


def run_push(events: list, *, now_et: datetime, prior: list, claim_coll=None, events_coll=None,
             owner: Optional[str] = None, sender: Optional[Callable] = None, act: bool = True,
             counts: Optional[dict] = None) -> dict:
    """Evaluate every `pending` event, claim, send. `act=False` (dry run / no
    push) computes reasons and texts and writes NOTHING."""
    from supply_demand import demand_alerts as DA
    from . import store as S
    counts = counts if counts is not None else {}
    for k in ("pushed", "muted", "claimed_elsewhere", "recap", "blocked_price", "blocked_dollar_vol",
              "blocked_unknown_liquidity", "stale", "closed_day", "baseline", "not_high_impact",
              "unresolved_ticker"):
        counts.setdefault(k, 0)
    out = {"decisions": [], "messages": []}
    fired = []                                                   # (ev, [claim keys])
    at = datetime.now(timezone.utc)
    for ev in events:
        reason = gate(ev, now_et=now_et, baseline=bool(ev.get("baseline")), prior=prior)
        keys = []
        if reason is None and act:
            if ev.get("event_type") == "topline":
                tk = f"MC:{ev['ticker']}|topline|{_sd(ev).isoformat()}"
                doc = {"event_key": ev["_id"], "symbol": ev["ticker"], "kind": KIND,
                       "sent_at": R.as_et(now_et).isoformat()}
                if DA.claim_key(claim_coll, tk, doc):
                    keys.append(tk)
                else:
                    reason = "claimed_elsewhere"
            if reason is None:
                ek = f"MC:{ev['_id']}"
                doc = {"event_key": ev["_id"], "symbol": ev["ticker"], "kind": KIND,
                       "sent_at": R.as_et(now_et).isoformat()}
                if DA.claim_key(claim_coll, ek, doc):
                    keys.append(ek)
                else:
                    reason = "claimed_elsewhere"
                    for k in keys:
                        DA.release_key(claim_coll, k)
                    keys = []
        out["decisions"].append({"event_key": ev.get("_id"), "reason": reason})
        if reason is None:
            fired.append((ev, keys))
            continue
        counts[reason] = counts.get(reason, 0) + 1
        if act and reason != "closed_day":
            S.set_push(events_coll, ev["_id"], REASON_STATE.get(reason, "not_eligible"), reason, at)
    if not fired:
        return out
    if owner is None and act:
        from portfolio.alerts import _resolve_owner
        owner = _resolve_owner()
    fired.sort(key=lambda x: _rank(x[0]))
    singles, rest = fired[:MAX_SINGLES], fired[MAX_SINGLES:]
    msgs = [(single_text(ev), [(ev, keys)]) for ev, keys in singles]
    if rest:
        msgs.append((digest_text([ev for ev, _k in rest]), rest))
    send = sender or _default_send
    for msg, group in msgs:
        out["messages"].append({"title": msg["title"], "body": msg["body"],
                                "events": [ev.get("_id") for ev, _k in group]})
        if not act:
            continue
        try:
            res = send(owner, msg, KIND)
        except Exception as exc:                                 # noqa: BLE001
            from .sources import redact_exc
            log.warning("medical.alerts: send failed: %s", redact_exc(exc))
            res = DA.transport_failed(exc)
        if not DA._terminal(res):
            for _ev, keys in group:
                for k in keys:
                    DA.release_key(claim_coll, k)
            continue
        state = "pushed" if (res.get("sent") or 0) > 0 else "muted"
        counts[state] += 1
        for ev, _k in group:
            S.set_push(events_coll, ev["_id"], state, None, at)
    return out


def explain(ev: dict, *, now_et: datetime, prior: list) -> dict:
    """`--explain SYM`: the gate reason and the exact title/body the phone would get."""
    reason = gate(ev, now_et=now_et, baseline=bool(ev.get("baseline")), prior=prior)
    txt = single_text(ev) if ev.get("ticker") else {"title": None, "body": None}
    return {"event_key": ev.get("_id"), "reason": reason, "title": txt["title"], "body": txt["body"]}


__all__ = ["KIND", "MAX_SINGLES", "DIGEST_MAX_LINES", "CADENCE_SEC", "RTH_EXPOSURE_MAX_MIN",
           "RECAP_SESSIONS", "gate", "single_text", "digest_text", "run_push", "explain", "gate_text",
           "area_primary", "modality_primary", "REASON_STATE"]
