"""Signal Lab — BUY/SELL tags on 1-minute candles for tickers Ajay adds
himself, from the strategies this app already computes: the opening range,
liquidity sweeps (the trap), BOS/CHoCH structure, and Brad Goh's five-step
sequence as the composite entry.

Ajay 2026-09-01: "calculate entries with a buy or sell indicator on a stock
ticker I add ... same concepts from what we build with ORB, Liquidity grab,
BOS ... custom tickers on demand like the session tab ... more real time
feedback of buy signals and sell signals on 1 mins candles."

The PRESENTATION borrows GainzAlgo's UI conventions — BUY/SELL labels
printed at the signal candle, stop/target attached, closed-bar signals —
none of their paid formula. Day-trading strategy family: SMC thresholds are
uncited convention (ICT lineage), the ORB is the app's own gap-and-go
heuristic. No Minervini/SEPA citations apply here and none are implied.

Non-repaint contract (the one signal vendors brag about, made CHECKABLE):
  * signals are computed on CLOSED bars only, and
  * a bar-i event may only use swing points fully confirmed by bar i
    (swing at j exists once bar j+SWING_WINDOW has closed).
  smc.liquidity_sweeps / structure_breaks recomputed on a full frame will
  happily match a bar against a swing confirmed AFTER it — replayed live
  that is time travel. This module therefore runs its own walk over
  smc.swing_points with the confirmation lag enforced, which makes the
  event stream PREFIX-STABLE: events(frame[:k]) == events(frame)[:k-side].
  Locked by test_signal_lab.py::test_prefix_stability.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

log = logging.getLogger("daytrading.signal_lab")

ORB_MINUTES = 15
COMPOSITE_WITHIN = 30        # sweep -> structure confirmation window (bars)
SWEEP_LOOKBACK = 60          # a swing older than this is stale liquidity (smc parity)
TARGET_R = 2.0               # composite target = entry + 2R (uncited convention)
TILE_BARS = 120              # 2 hours of 1-minute candles on screen
MAX_SYMBOLS = 12             # keep one refresh bounded; the UI enforces it too
WORKERS = 6


def events_from_frame(df, orb_minutes: int = ORB_MINUTES) -> list[dict]:
    """All signal events for ONE session's 1-minute frame, oldest first. PURE.

    Event kinds:
      orb_up / orb_dn   first close beyond a COMPLETE opening range (once each)
      sweep             wick through a confirmed swing with a close back inside
      bos / choch       close beyond the most recent opposing confirmed swing
      buy / sell        the composite: sweep, then opposite-side structure
                        break within COMPOSITE_WITHIN bars -> entry at that
                        close, stop at the sweep's wick, target at +TARGET_R.
    """
    out: list[dict] = []
    if df is None or getattr(df, "empty", True) or len(df) < 2:
        return out
    from supply_demand import patterns as pat_mod
    from supply_demand import smc

    try:
        hi = df["high"].to_numpy(dtype=float)
        lo = df["low"].to_numpy(dtype=float)
        cl = df["close"].to_numpy(dtype=float)
    except Exception:
        return out
    n = len(df)
    w = smc.SWING_WINDOW
    swing_lows, swing_highs = smc.swing_points(df, w)

    orb = pat_mod.opening_range_from_bars(df, minutes=orb_minutes)
    orb_ready = bool(orb and orb.get("complete"))
    orb_hi = float(orb["hi"]) if orb_ready else None
    orb_lo = float(orb["lo"]) if orb_ready else None
    orb_up_done = orb_dn_done = False

    trend: Optional[str] = None
    broken: set = set()
    swept: set = set()               # (side, swing_idx) already swept once
    open_sweeps: list[dict] = []     # traps awaiting structure confirmation

    for i in range(n):
        # swings CONFIRMED by bar i: pivot j needs bar j+w closed
        lows_known = [(j, p) for j, p in swing_lows if j + w <= i and j < i]
        highs_known = [(j, p) for j, p in swing_highs if j + w <= i and j < i]

        # ── opening range breaks (needs the range COMPLETE first) ──────────
        if orb_ready and i >= orb_minutes:
            if not orb_up_done and cl[i] > orb_hi:
                orb_up_done = True
                out.append({"i": i, "kind": "orb_up", "price": float(cl[i]),
                            "level": orb_hi,
                            "why": f"first close over the {orb_minutes}m opening range"})
            if not orb_dn_done and cl[i] < orb_lo:
                orb_dn_done = True
                out.append({"i": i, "kind": "orb_dn", "price": float(cl[i]),
                            "level": orb_lo,
                            "why": f"first close under the {orb_minutes}m opening range"})

        # ── liquidity sweeps (smc semantics, confirmed swings only) ────────
        # One trap per level per session, recent swings only: without both,
        # 1-minute noise printed ~100 'sweeps' per 2 hours on the first live
        # smoke (TSLA 90, IREN 121) — a board of wolf-cries, not signals.
        for j, p in reversed(lows_known):
            if i - j > SWEEP_LOOKBACK or ("sell_side", j) in swept:
                continue
            if lo[i] < p and cl[i] > p:
                ev = {"i": i, "kind": "sweep", "side": "sell_side",
                      "direction": "bullish", "level": float(p),
                      "wick": float(lo[i]), "price": float(cl[i]),
                      "why": f"swept the {p:.2f} low, closed back above — trap"}
                out.append(ev)
                open_sweeps.append(ev)
                swept.add(("sell_side", j))
                break
        for j, p in reversed(highs_known):
            if i - j > SWEEP_LOOKBACK or ("buy_side", j) in swept:
                continue
            if hi[i] > p and cl[i] < p:
                ev = {"i": i, "kind": "sweep", "side": "buy_side",
                      "direction": "bearish", "level": float(p),
                      "wick": float(hi[i]), "price": float(cl[i]),
                      "why": f"swept the {p:.2f} high, closed back below — trap"}
                out.append(ev)
                open_sweeps.append(ev)
                swept.add(("buy_side", j))
                break

        # ── structure breaks (close beyond most recent opposing swing) ─────
        struct_ev = None
        if highs_known and lows_known:
            hj, hp = highs_known[-1]
            lj, lp = lows_known[-1]
            if cl[i] > hp and ("up", hj) not in broken:
                kind = "bos" if trend == "up" else "choch"
                struct_ev = {"i": i, "kind": kind, "direction": "bullish",
                             "level": float(hp), "price": float(cl[i]),
                             "why": f"closed over the {hp:.2f} swing high"}
                trend = "up"
                broken.add(("up", hj))
            elif cl[i] < lp and ("down", lj) not in broken:
                kind = "bos" if trend == "down" else "choch"
                struct_ev = {"i": i, "kind": kind, "direction": "bearish",
                             "level": float(lp), "price": float(cl[i]),
                             "why": f"closed under the {lp:.2f} swing low"}
                trend = "down"
                broken.add(("down", lj))
        if struct_ev:
            out.append(struct_ev)

            # ── the composite: sweep then opposite structure ───────────────
            for sw in reversed(open_sweeps):
                if i - sw["i"] > COMPOSITE_WITHIN:
                    continue
                if sw["i"] >= i:
                    continue
                if sw["side"] == "sell_side" and struct_ev["direction"] == "bullish":
                    entry = float(cl[i])
                    stop = sw["wick"]
                    if entry <= stop:
                        continue
                    out.append({
                        "i": i, "kind": "buy", "price": entry, "stop": stop,
                        "target": round(entry + TARGET_R * (entry - stop), 4),
                        "why": (f"sell-side sweep at {sw['level']:.2f} then "
                                f"{struct_ev['kind'].upper()} up — five-step entry"),
                    })
                    open_sweeps.remove(sw)
                    break
                if sw["side"] == "buy_side" and struct_ev["direction"] == "bearish":
                    entry = float(cl[i])
                    stop = sw["wick"]
                    if entry >= stop:
                        continue
                    out.append({
                        "i": i, "kind": "sell", "price": entry, "stop": stop,
                        "target": round(entry - TARGET_R * (stop - entry), 4),
                        "why": (f"buy-side sweep at {sw['level']:.2f} then "
                                f"{struct_ev['kind'].upper()} down — five-step exit/short"),
                    })
                    open_sweeps.remove(sw)
                    break
    return out


# ── board: one tile per symbol Ajay added ──────────────────────────────────
def _last_session_frame(sym: str):
    """The most recent SESSION's 1-minute bars in ET, or None. One fetch."""
    try:
        from supply_demand import timeframes as TF
        import pandas as pd
        raw = TF.intraday_raw(sym, "15m")
        if raw is None or raw.empty:
            return None
        idx = raw.index
        et = (idx.tz_localize("UTC") if idx.tz is None else idx).tz_convert(
            "America/New_York")
        frame = raw.copy()
        frame.index = et
        dates = pd.Series(et.date, index=frame.index)
        return frame[dates == dates.max()]
    except Exception as exc:
        log.warning("signal-lab: bars for %s failed: %s", sym, exc)
        return None


_KIND_LABEL = {
    "buy": "BUY", "sell": "SELL", "sweep": "sweep", "bos": "BOS",
    "choch": "CHoCH", "orb_up": "ORB ↑", "orb_dn": "ORB ↓",
}


def _tile(sym: str, df, events: list[dict]) -> dict:
    win_start = max(0, len(df) - TILE_BARS)
    window = df.iloc[win_start:]
    bars = [{
        "t": ts.strftime("%Y-%m-%d %H:%M"),
        "o": round(float(r["open"]), 4), "h": round(float(r["high"]), 4),
        "l": round(float(r["low"]), 4), "c": round(float(r["close"]), 4),
        "v": int(r.get("volume") or 0),
    } for ts, r in window.iterrows()]
    markers = []
    for ev in events:
        if ev["i"] < win_start:
            continue
        markers.append({
            "date": bars[ev["i"] - win_start]["t"],
            "kind": ev["kind"],
            "label": _KIND_LABEL.get(ev["kind"], ev["kind"]),
            "price": ev.get("price"),
        })
    latest = next((e for e in reversed(events) if e["kind"] in ("buy", "sell")), None)
    lines = []
    if latest:
        lines = [
            {"price": latest["price"], "label": latest["kind"].upper(), "tone": "buy" if latest["kind"] == "buy" else "stop"},
            {"price": latest["stop"], "label": "STOP", "tone": "stop"},
            {"price": latest["target"], "label": "TARGET", "tone": "target"},
        ]
    n_buy = sum(1 for e in events if e["kind"] == "buy")
    n_sell = sum(1 for e in events if e["kind"] == "sell")
    return {
        "symbol": sym, "href": f"/sepa/{sym}?tab=supply",
        "bars": bars, "bands": [], "lines": lines, "markers": markers,
        "stats": [{"k": "Signals", "v": f"{n_buy}▲ {n_sell}▼"},
                  {"k": "Bars", "v": str(len(df))}],
        "why": latest["why"] if latest else "no composite signal this session",
    }


def board(symbols: list[str]) -> dict:
    syms = [s.strip().upper() for s in symbols if s and s.strip()][:MAX_SYMBOLS]
    t0 = time.time()

    def one(sym: str) -> dict:
        df = _last_session_frame(sym)
        if df is None or len(df) < 5:
            return {"symbol": sym, "error": "no 1-minute bars — check the ticker"}
        events = events_from_frame(df)
        feed = [{
            "t": df.index[e["i"]].strftime("%H:%M"),
            "kind": e["kind"], "label": _KIND_LABEL.get(e["kind"], e["kind"]),
            "price": e.get("price"), "stop": e.get("stop"),
            "target": e.get("target"), "why": e["why"],
        } for e in events][::-1][:20]
        latest = next((f for f in feed if f["kind"] in ("buy", "sell")), None)
        return {"symbol": sym, "tile": _tile(sym, df, events), "feed": feed,
                "latest": latest,
                "session": str(df.index[-1].date()),
                "last_bar_et": df.index[-1].strftime("%H:%M")}

    rows: list[dict] = []
    if syms:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            rows = list(ex.map(one, syms))

    from daytrading.premarket import _session_now
    return {
        "rows": rows, "count": len(rows), "session_state": _session_now(),
        "took_sec": round(time.time() - t0, 1),
        "method_note": ("Signals: ORB break (app heuristic), liquidity sweep + "
                        "BOS/CHoCH (SMC — uncited convention, ICT lineage), and "
                        "the five-step composite (sweep then structure break; "
                        "stop at the trap wick, target 2R). Closed 1-minute "
                        "bars only; a signal never appears on an earlier bar "
                        "after the fact. Presentation inspired by GainzAlgo; "
                        "the math is this app's own. Not advice."),
        "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ── the watchlist: HIS tickers, per user, a data write not a deploy ────────
def _watch_coll():
    try:
        import os
        from pymongo import MongoClient
        c = MongoClient(os.environ.get("MONGO_URL", "mongodb://mongo:27017"),
                        serverSelectionTimeoutMS=2000)
        return c.get_database("cheetah")["signal_lab_watchlist"]
    except Exception:
        return None


def get_watchlist(email: str) -> list[str]:
    coll = _watch_coll()
    if coll is None or not email:
        return []
    doc = coll.find_one({"_id": email}) or {}
    return list(doc.get("symbols") or [])


def add_symbol(email: str, symbol: str) -> list[str]:
    sym = (symbol or "").strip().upper()
    coll = _watch_coll()
    if coll is None or not email or not sym:
        return get_watchlist(email)
    syms = get_watchlist(email)
    if sym not in syms:
        syms.append(sym)
        syms = syms[-MAX_SYMBOLS:]
        coll.update_one({"_id": email}, {"$set": {"symbols": syms}}, upsert=True)
    return syms


def remove_symbol(email: str, symbol: str) -> list[str]:
    sym = (symbol or "").strip().upper()
    coll = _watch_coll()
    if coll is None or not email:
        return get_watchlist(email)
    syms = [s for s in get_watchlist(email) if s != sym]
    coll.update_one({"_id": email}, {"$set": {"symbols": syms}}, upsert=True)
    return syms
