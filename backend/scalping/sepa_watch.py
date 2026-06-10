"""SEPA-cross tape watch — the autonomous real-time alert layer.

Watches the names that matter to Ajay's SEPA process — portfolio HOLDINGS,
BUYABLE names, AT-PIVOT names, and the rank-LEADERBOARD — and reads each new
completed 5-min candle against its levels (SEPA pivot, VWAP, opening range, day
high) via scalping.candles. On a state TRANSITION into an alertable read it
pushes ONE notification (kind="scalp_tape"), deduped per (symbol, state, ET day)
with the mark-BEFORE-send rule (pivot_alerts lesson, 2026-06-09: a delivery miss
must never cause a re-fire).

SELF-SCORING: every alert is resolved ~30 minutes later with the actual forward
return, so the page shows this alert type's LIVE hit-rate — the system grades
itself instead of asking to be trusted. Educational, not advice; verdicts are
"constructive/deteriorating", never predictions.

State in Mongo `scalping_tape_watch`, one doc per (symbol, et_date). Driven by
the `scalping-watch` cron (minutes 1,6,…,56 during RTH + a 16:01 final pass).
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd

from . import candles, engine

log = logging.getLogger("scalping.sepa_watch")

WATCH_CAP = 35
LEADERBOARD_N = 20
FWD_MIN = 30                 # self-scoring horizon (minutes)
_mem: dict = {}              # in-proc fallback when Mongo is down

ALERT_EMOJI = {
    "BREAKOUT_STRONG": "🟢", "RECLAIM": "🟢",
    "REJECTION": "🟠", "BREAKDOWN": "🔴",
}


def _now_et() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now().astimezone()    # container TZ is America/New_York


def _et_date() -> str:
    return _now_et().strftime("%Y-%m-%d")


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")].scalping_tape_watch
    except Exception:
        return None


# ── universe: the SEPA cross ─────────────────────────────────────────────────
def _pivot_of(row: dict):
    es = row.get("entry_setup") or {}
    return es.get("pivot") or (row.get("vcp") or {}).get("pivot_buy_price")


PATTERN_LINE_LABEL = {
    "double_bottom": "W line", "triple_bottom": "triple-bottom line",
    "inverse_head_shoulders": "iH&S neckline", "cup_with_handle": "cup-handle line",
}


def _lines_from_doc(doc: dict) -> dict:
    """{symbol: {line, label}} — FORMING patterns' confirmation lines from a
    verdict-scan doc. Stale docs (>24h) yield nothing: in-the-moment only."""
    if int(time.time()) - int((doc or {}).get("generated_at") or 0) > 24 * 3600:
        return {}
    out = {}
    for v in doc.get("verdicts") or []:
        sym = (v.get("symbol") or "").upper()
        for m in v.get("matches") or []:
            if m.get("status") == "forming" and m.get("neckline"):
                out[sym] = {"line": float(m["neckline"]),
                            "label": PATTERN_LINE_LABEL.get(m.get("pattern"), "pattern line")}
                break
    return out


def _pattern_lines() -> dict:
    """The daily↔intraday join (Ajay 2026-06-09): the daily pattern defines the
    trigger level; this 5-min engine watches it. Reads the latest verdict scan."""
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        doc = c[os.getenv("MONGO_DB", "cheetah")].patterns_scan.find_one(
            {"_id": "qualifier_verdicts"}) or {}
    except Exception as exc:
        log.debug("pattern lines load failed: %s", exc)
        return {}
    return _lines_from_doc(doc)


# Common leveraged/inverse ETFs — the leaderboard can surface them but they're
# not stock tape-reads (the app has the same guardrail on the frontend).
_LEV_ETFS = {"TQQQ", "SQQQ", "TECL", "TECS", "SOXL", "SOXS", "UPRO", "SPXU",
             "SPXL", "SPXS", "QLD", "SSO", "SDS", "UDOW", "SDOW", "LABU",
             "LABD", "TNA", "TZA", "FNGU", "FNGD", "UVXY", "SVXY", "VXX"}


def watch_universe() -> list:
    """holdings ∪ buyable ∪ at-pivot ∪ leaderboard, tagged, deduped, capped.
    Each entry: {symbol, tags[], pivot}. ETFs skipped."""
    out: dict = {}

    def add(sym, tag, pivot=None):
        if not sym or sym.upper() in _LEV_ETFS:
            return
        e = out.setdefault(sym.upper(), {"symbol": sym.upper(), "tags": [], "pivot": None})
        if tag not in e["tags"]:
            e["tags"].append(tag)
        if pivot and not e["pivot"]:
            e["pivot"] = round(float(pivot), 2)

    try:
        from portfolio.store import list_holdings
        owner = os.getenv("DEFAULT_USER_EMAIL", "ajaykandakatla@gmail.com")
        for h in list_holdings(owner) or []:
            add(h.get("ticker") or h.get("symbol"), "HOLDING")
    except Exception as exc:
        log.debug("watch universe holdings failed: %s", exc)

    scan_rows = {}
    try:
        from sepa import scanner
        for r in (scanner.load_latest() or {}).get("all_results") or []:
            sym = r.get("symbol")
            if not sym or r.get("is_etf"):
                continue
            scan_rows[sym] = r
            if r.get("is_buyable"):
                add(sym, "BUYABLE", _pivot_of(r))
    except Exception as exc:
        log.debug("watch universe scan failed: %s", exc)

    try:
        from sepa import at_pivot
        for r in (at_pivot.get_at_pivot() or {}).get("rows") or []:
            if not r.get("is_etf"):
                add(r.get("symbol"), "AT_PIVOT", r.get("pivot"))
    except Exception as exc:
        log.debug("watch universe at_pivot failed: %s", exc)

    try:
        from sepa import leaderboard
        for l in (leaderboard.leaderboard(n=LEADERBOARD_N) or {}).get("leaders") or []:
            sym = l.get("symbol")
            if sym and (scan_rows.get(sym) or {}).get("is_etf"):
                continue
            add(sym, "LEADER")
    except Exception as exc:
        log.debug("watch universe leaderboard failed: %s", exc)

    # Forming-pattern trigger lines: names already on the watch get their line
    # attached; forming-pattern names not otherwise watched join with PATTERN.
    lines = _pattern_lines()
    for sym in lines:
        add(sym, "PATTERN")
    for e in out.values():
        info = lines.get(e["symbol"])
        if info:
            e["pattern_line"] = info["line"]
            e["pattern_label"] = info["label"]

    # Fill missing pivots from the scan rows (holdings/leaders that are also scanned).
    for e in out.values():
        if not e["pivot"] and e["symbol"] in scan_rows:
            p = _pivot_of(scan_rows[e["symbol"]])
            if p:
                e["pivot"] = round(float(p), 2)

    # Priority: holdings first, then buyable, at-pivot, pattern lines, leaders.
    rank = {"HOLDING": 0, "BUYABLE": 1, "AT_PIVOT": 2, "PATTERN": 3, "LEADER": 4}
    rows = sorted(out.values(), key=lambda e: min(rank.get(t, 9) for t in e["tags"]))
    return rows[:WATCH_CAP]


# ── per-symbol tape read ─────────────────────────────────────────────────────
def _read_symbol(entry: dict) -> Optional[dict]:
    """Load today's 1-min bars → 5-min anatomy read vs levels. None = no data."""
    from daytrading.data import load_intraday
    from daytrading.indicators import vwap_session, opening_range
    sym = entry["symbol"]
    try:
        df = load_intraday(sym, _now_et().date(), include_premarket=False)
    except Exception as exc:
        log.debug("watch read %s failed: %s", sym, exc)
        return None
    if df is None or df.empty:
        return None
    rth = df[df["session"] == "rth"]
    if len(rth) < 11:
        return None

    df5 = candles.aggregate_5min(rth)
    if len(df5) < 2:
        return None
    vw = vwap_session(rth, session="rth")
    vwap_now = float(vw.dropna().iloc[-1]) if not vw.dropna().empty else None
    orng = opening_range(rth, minutes=5)
    last_bar_end = df5.index[-1]
    levels = {
        "pivot": entry.get("pivot"),
        "pattern_line": entry.get("pattern_line"),
        "pattern_name": entry.get("pattern_label"),
        "vwap": round(vwap_now, 4) if vwap_now else None,
        "or_high": orng.get("high") if orng else None,
        "day_high": round(float(rth["high"].max()), 4),
    }
    avg_vol = float(df5["volume"].iloc[:-1].mean()) if len(df5) > 1 else None
    read = candles.classify(df5, levels, avg_vol)

    px = float(rth["close"].iloc[-1])
    return {
        "symbol": sym, "tags": entry["tags"], "pivot": entry.get("pivot"),
        "last_price": round(px, 4), "levels": levels,
        "bar_ts": last_bar_end.isoformat(),
        "read": read,
        "vs_pivot_pct": round((px / entry["pivot"] - 1) * 100, 2) if entry.get("pivot") else None,
        "vs_vwap_pct": round((px / vwap_now - 1) * 100, 2) if vwap_now else None,
    }


# ── state + alerts ───────────────────────────────────────────────────────────
def _doc_key(sym: str, d: str) -> str:
    return f"{sym}:{d}"


def _fire_alert(sym: str, row: dict, read: dict, coll, d: str) -> Optional[dict]:
    """One push per (symbol, state, day). Mark BEFORE send — a delivery miss
    must never re-fire (pivot_alerts lesson)."""
    state = read["state"]
    dedup = f"{sym}:{state}:{d}"
    if coll is not None:
        if coll.find_one({"_id": _doc_key(sym, d), "alerts.dedup": dedup}):
            return None
    elif dedup in _mem:
        return None

    alert = {
        "dedup": dedup, "state": state, "verdict": read["verdict"],
        "price": row["last_price"], "bar_ts": row["bar_ts"],
        "fired_at": int(time.time()), "fwd_pct": None, "graded": None,
    }
    # MARK first.
    if coll is not None:
        coll.update_one({"_id": _doc_key(sym, d)},
                        {"$push": {"alerts": alert},
                         "$set": {"symbol": sym, "et_date": d}}, upsert=True)
    else:
        _mem[dedup] = 1

    emoji = ALERT_EMOJI.get(state, "🕯")
    title = f"{sym}: {state.replace('_', ' ').title()} — {read['verdict']}"
    body = " · ".join(read["reasons"][:2])
    try:
        from sepa import notify
        notify.send_alert(title=f"{emoji} {title}", body=body[:280],
                          url="/scalping", kind="scalp_tape", ticker=sym)
    except Exception as exc:
        log.warning("watch alert send failed %s: %s", sym, exc)
    return alert


def _resolve_alerts(coll, d: str) -> int:
    """Self-scoring: fill fwd_pct for alerts ≥ FWD_MIN old using the real tape,
    and grade them (constructive read → did it go up; deteriorating → down).
    Scans the last few days, not just today — an alert fired in the session's
    final 30 minutes gets graded against the close on the NEXT run/day."""
    if coll is None:
        return 0
    from daytrading.data import load_intraday
    now = int(time.time())
    n = 0
    cutoff = (_now_et().date() - timedelta(days=4)).strftime("%Y-%m-%d")
    for doc in coll.find({"et_date": {"$gte": cutoff}, "kind": {"$ne": "snapshot"},
                          "alerts.fwd_pct": None}):
        d = doc["et_date"]
        sym = doc["symbol"]
        try:
            day = datetime.strptime(d, "%Y-%m-%d").date()
            df = load_intraday(sym, day, include_premarket=False)
        except Exception:
            continue
        if df is None or df.empty:
            continue
        rth = df[df["session"] == "rth"]
        changed = False
        for a in doc.get("alerts", []):
            if a.get("fwd_pct") is not None or now - a["fired_at"] < FWD_MIN * 60:
                continue
            t0 = pd.Timestamp(a["bar_ts"])
            if t0.tzinfo is not None:
                t0 = t0.tz_convert(None)
            fwd = rth[rth.index >= t0 + pd.Timedelta(minutes=FWD_MIN)]
            base = a.get("price")
            if fwd.empty or not base:
                # Past EOD with no +30m bar → grade against the close.
                if rth.index[-1] - t0 < pd.Timedelta(minutes=FWD_MIN) and now - a["fired_at"] < 8 * 3600:
                    continue
                px = float(rth["close"].iloc[-1])
            else:
                px = float(fwd["close"].iloc[0])
            a["fwd_pct"] = round((px / base - 1) * 100, 3)
            a["graded"] = ("hit" if a["fwd_pct"] > 0 else "miss") if a["verdict"] == "constructive" \
                else ("hit" if a["fwd_pct"] < 0 else "miss") if a["verdict"] == "deteriorating" else None
            changed = True
            n += 1
        if changed:
            coll.update_one({"_id": doc["_id"]}, {"$set": {"alerts": doc["alerts"]}})
    return n


def run_watch() -> dict:
    """One cron tick: read every watched name, alert on new alertable states,
    resolve pending alert outcomes, persist the page snapshot."""
    n = _now_et()
    d = _et_date()
    coll = _coll()
    if not engine._market_open(n):
        resolved = _resolve_alerts(coll, d)
        return {"market_open": False, "resolved": resolved}

    uni = watch_universe()
    rows: list = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(_read_symbol, uni):
            if r:
                rows.append(r)

    alerts_fired = 0
    for row in rows:
        read = row.get("read")
        if not read:
            continue
        if read["severity"] == "alert":
            if _fire_alert(row["symbol"], row, read, coll, d):
                alerts_fired += 1

    resolved = _resolve_alerts(coll, d)

    # Persist the snapshot so GET /scalping/watch is instant.
    if coll is not None:
        try:
            coll.update_one({"_id": f"snapshot:{d}"},
                            {"$set": {"et_date": d, "kind": "snapshot",
                                      "generated_at": int(time.time()),
                                      "rows": rows, "n_watched": len(uni)}}, upsert=True)
        except Exception as exc:
            log.warning("watch snapshot persist failed: %s", exc)

    log.info("sepa_watch: watched=%d read=%d alerts=%d resolved=%d",
             len(uni), len(rows), alerts_fired, resolved)
    return {"market_open": True, "watched": len(uni), "read": len(rows),
            "alerts_fired": alerts_fired, "resolved": resolved}


# ── page payload ─────────────────────────────────────────────────────────────
def _hit_rate(coll, days: int = 10) -> dict:
    """LIVE per-state track record from graded alerts over the last N days —
    the system grading itself."""
    if coll is None:
        return {}
    cutoff = (_now_et().date() - timedelta(days=days)).strftime("%Y-%m-%d")
    agg: dict = {}
    for doc in coll.find({"et_date": {"$gte": cutoff}, "kind": {"$ne": "snapshot"}}):
        for a in doc.get("alerts", []):
            if a.get("graded") not in ("hit", "miss"):
                continue
            s = agg.setdefault(a["state"], {"n": 0, "hits": 0, "fwd": []})
            s["n"] += 1
            s["hits"] += 1 if a["graded"] == "hit" else 0
            s["fwd"].append(a["fwd_pct"])
    out = {}
    for state, s in agg.items():
        fwd = sorted(s["fwd"])
        out[state] = {"n": s["n"], "hit_rate_pct": round(s["hits"] / s["n"] * 100, 1),
                      "median_fwd_30m_pct": round(fwd[len(fwd) // 2], 3) if fwd else None}
    return out


def snapshot(run_if_stale: bool = False) -> dict:
    """The page payload: latest watch rows + today's alerts + the live hit-rate."""
    coll = _coll()
    d = _et_date()
    snap = coll.find_one({"_id": f"snapshot:{d}"}) if coll is not None else None
    if run_if_stale and engine._market_open(_now_et()):
        age = int(time.time()) - int((snap or {}).get("generated_at") or 0)
        if age > 420:                          # cron dead? compute inline once
            run_watch()
            snap = coll.find_one({"_id": f"snapshot:{d}"}) if coll is not None else None

    alerts_today: list = []
    if coll is not None:
        for doc in coll.find({"et_date": d, "kind": {"$ne": "snapshot"}}):
            alerts_today.extend(doc.get("alerts", []))
    alerts_today.sort(key=lambda a: a.get("fired_at", 0), reverse=True)

    return {
        "generated_at": int((snap or {}).get("generated_at") or 0),
        "as_of_et": _now_et().strftime("%Y-%m-%d %H:%M ET"),
        "market_open": engine._market_open(_now_et()),
        "rows": (snap or {}).get("rows") or [],
        "n_watched": (snap or {}).get("n_watched") or 0,
        "alerts_today": alerts_today[:40],
        "live_track_record": _hit_rate(coll),
        "disclaimer": (
            "SEPA-cross tape watch — descriptive supply/demand reads of each 5-min "
            "candle at a level (pivot/VWAP/range), with volume. Candlestick patterns "
            "standalone have weak-to-null documented predictive power; verdicts are "
            "reads, not predictions, and every alert is graded against the next 30 "
            "minutes so the live hit-rate above is the honest record. Not advice."),
    }
