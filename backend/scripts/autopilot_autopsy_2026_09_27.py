"""Auto-Pilot money autopsy (2026-09-27) — READ-ONLY.

Where is the paper Auto-Pilot losing money, and why?

Ground truth = the BROKER (Alpaca paper) fills, not the journal: every FILL
activity since the account was created is paired FIFO into round-trips per
symbol (flat -> open -> flat). Each round-trip is then attributed to a lane by
ORDER ID against the engine's own ledger rows (entry / zone_entry /
auto_entry / catalyst_entry / hot_pullback_entry / options_entry /
zero_dte_entry / adopt_protect), current + the 2026-07-12 archive. Exit
reason comes from the closing order id (trade_closed leg, flatten*, watchdog,
distribution, lane exits) and falls back to the broker order type.

Strictly read-only:
  * broker reads go through trading.broker_alpaca's own GET helpers
    (account, positions, and its _request("GET", ...) for portfolio history,
    activities and the order list). No key is ever printed; no write verb is
    ever sent (_get() below hard-codes GET).
  * Mongo reads only (find / find_one / count). Nothing is written to Mongo.
  * daily bars via sepa.prices.load_prices(DAILY_PERIOD) — the app's own read
    path (it refreshes the shared price cache exactly as any page read does).
  * owner autopsy classes reuse trading.autopsy.compute/classify (pure).

Run (inside the api image, outside RTH for the bar loads):
    PYTHONPATH=/app python autopilot_autopsy_2026_09_27.py OUT.json [--no-bars]

Statistics: win rate with a Wilson 95% CI; expectancy ($/trade and R/trade)
with a percentile bootstrap 95% CI (fixed seed, 5,000 resamples). Buckets are
DESCRIPTIVE groupings of what happened, never rules. Small n is flagged
(n < SMALL_N) and must not be extrapolated.
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict, OrderedDict
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
SEED = 20260927
BOOT = 5000
SMALL_N = 10          # below this a bucket is printed but flagged "small n"
OCC_RE = re.compile(r"^([A-Z]{1,6})(\d{6})([CP])(\d{8})$")
MATCH_WINDOW_SEC = 900    # proximity fallback when no order id matches

# ── tiny utils ──────────────────────────────────────────────────────────────


def f(x):
    try:
        v = float(x)
        return None if (v != v or math.isinf(v)) else v
    except (TypeError, ValueError):
        return None


def to_dt(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(float(v), tz=timezone.utc)
    s = str(v).replace("Z", "+00:00")
    m = re.match(r"^(.*\.\d{6})\d+(.*)$", s)        # ns stamps -> us
    if m:
        s = m.group(1) + m.group(2)
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def et(d):
    return d.astimezone(ET) if d else None


def r2(v, nd=2):
    return None if v is None else round(v, nd)


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def boot_ci(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return (None, None)
    import numpy as np
    rng = np.random.default_rng(SEED)
    a = np.asarray(xs, dtype=float)
    means = a[rng.integers(0, len(a), size=(BOOT, len(a)))].mean(axis=1)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


STOP_RE = re.compile(r"^stop|watchdog|signal stop|band floor stop|premium -")


def stopped(t):
    return bool(STOP_RE.search(str(t.get("exit_reason") or "")))


def stats(trades):
    pn = [t["pnl"] for t in trades if t.get("pnl") is not None]
    rs = [t["r"] for t in trades if t.get("r") is not None]
    n = len(pn)
    wins = [x for x in pn if x > 0]
    losses = [x for x in pn if x <= 0]
    lo, hi = wilson(len(wins), n)
    elo, ehi = boot_ci(pn)
    rlo, rhi = boot_ci(rs)
    return OrderedDict(
        n=n, small_n=n < SMALL_N,
        win_rate=r2(len(wins) / n * 100, 1) if n else None,
        win_ci=[r2(lo * 100, 1) if lo is not None else None,
                r2(hi * 100, 1) if hi is not None else None],
        avg_win=r2(sum(wins) / len(wins)) if wins else None,
        avg_loss=r2(sum(losses) / len(losses)) if losses else None,
        exp_usd=r2(sum(pn) / n) if n else None,
        exp_usd_ci=[r2(elo), r2(ehi)],
        n_r=len(rs),
        exp_r=r2(sum(rs) / len(rs), 3) if rs else None,
        exp_r_ci=[r2(rlo, 3), r2(rhi, 3)],
        total_usd=r2(sum(pn)),
        payoff=r2(abs((sum(wins) / len(wins)) / (sum(losses) / len(losses))))
        if wins and losses and sum(losses) else None,
        stop_out_pct=r2(sum(1 for t in trades if stopped(t)) / len(trades) * 100, 1)
        if trades else None,
    )


def table(title, trades, key, out):
    groups = defaultdict(list)
    for t in trades:
        groups[str(key(t))].append(t)
    rows = []
    for k, ts in groups.items():
        s = stats(ts)
        s["bucket"] = k
        rows.append(s)
    rows.sort(key=lambda s: (s["total_usd"] if s["total_usd"] is not None else 0))
    out[title] = rows
    print("\n### %s  (sorted by total $, most lost first)" % title)
    print("%-34s %4s %6s %13s %9s %9s %6s %6s %9s %19s %7s %15s %10s" % (
        "bucket", "n", "win%", "win95CI", "avgWin", "avgLoss", "payoff", "stop%",
        "exp$", "exp$95CI", "expR", "expR95CI", "total$"))
    for s in rows:
        print("%-34s %4d %6s %13s %9s %9s %6s %6s %9s %19s %7s %15s %10s%s" % (
            s["bucket"][:34], s["n"], s["win_rate"],
            "%s-%s" % tuple(s["win_ci"]), s["avg_win"], s["avg_loss"],
            s["payoff"], s["stop_out_pct"],
            s["exp_usd"], "%s..%s" % tuple(s["exp_usd_ci"]), s["exp_r"],
            "%s..%s" % tuple(s["exp_r_ci"]), s["total_usd"],
            "  (small n)" if s["small_n"] else ""))


# ── broker reads (GET only) ─────────────────────────────────────────────────

def _get(path, params=None):
    from trading import broker_alpaca as b
    return b._request("GET", path, params=params)      # GET hard-coded


def broker_pull():
    from trading import broker_alpaca as b
    acct = b.account() or {}
    pos = b.positions() or []
    created = acct.get("created_at")
    hist = _get("/v2/account/portfolio/history",
                {"period": "1A", "timeframe": "1D"}) or {}
    acts, token = [], None
    while True:
        p = {"page_size": 100, "direction": "asc"}
        if token:
            p["page_token"] = token
        page = _get("/v2/account/activities", p) or []
        acts.extend(page)
        if len(page) < 100:
            break
        token = page[-1]["id"]
    orders, after, seen = [], created, set()
    while True:
        page = _get("/v2/orders", {"status": "all", "after": after,
                                   "direction": "asc", "limit": 500,
                                   "nested": "true"}) or []
        new = [o for o in page if o["id"] not in seen]
        for o in new:
            seen.add(o["id"])
            orders.append(o)
            for leg in o.get("legs") or []:
                if leg["id"] not in seen:
                    seen.add(leg["id"])
                    orders.append(leg)
        if len(page) < 500 or not new:
            break
        after = page[-1]["submitted_at"]
    safe_acct = {k: acct.get(k) for k in (
        "equity", "last_equity", "cash", "long_market_value",
        "short_market_value", "created_at", "status")}
    return safe_acct, pos, hist, acts, orders


# ── Mongo reads ─────────────────────────────────────────────────────────────

def mongo_pull():
    from trading.exit_engine import _db
    db = _db()
    led = []
    for coll in ("trade_ledger_archive_pre_reset_2026_07_12", "trade_ledger"):
        for d in db[coll].find({"dry_run": {"$ne": True}}):
            d.pop("_id", None)
            d["_coll"] = coll
            led.append(d)
    led.sort(key=lambda d: f(d.get("epoch")) or 0)
    opts = [dict(d, _id=None) for d in db.options_positions.find()]
    zdte = [dict(d, _id=None) for d in db.zero_dte_positions.find()]
    blocked = list(db.trade_ledger.find({"kind": "options_blocked"},
                                         {"_id": 0, "detail": 1, "ts": 1}))
    base = db.trading_account_baseline.find_one({}, {"_id": 0, "account_key": 0})
    autops = {d["trade_id"]: d for d in db.trade_autopsies.find({}, {"_id": 0})}
    zstate = list(db.zero_dte_lane_state.find({}, {"_id": 0, "symbol": 1,
                                                   "result": 1, "reason": 1}))
    misc = {
        "paper_trades_daytrading_sim": db.paper_trades.estimated_document_count(),
        "sim_orders": db.sim_orders.estimated_document_count(),
        "zero_dte_calls": db.zero_dte_calls.estimated_document_count(),
    }
    misc["zero_dte_lane_state"] = zstate
    return led, opts, zdte, blocked, base, autops, misc


# ── round trips from fills ──────────────────────────────────────────────────

def round_trips(fills):
    """FIFO per symbol: flat -> open -> flat. Options carry the x100
    multiplier. Returns closed trips and still-open trips."""
    by_sym = defaultdict(list)
    for a in fills:
        by_sym[a["symbol"]].append(a)
    closed, still_open = [], []
    for sym, rows in by_sym.items():
        rows.sort(key=lambda a: a["transaction_time"])
        mult = 100.0 if OCC_RE.match(sym) else 1.0
        pos = 0.0
        cur = None
        for a in rows:
            q = f(a["qty"]) or 0.0
            px = f(a["price"]) or 0.0
            sgn = 1.0 if a["side"] == "buy" else -1.0
            if cur is None:
                cur = {"symbol": sym, "mult": mult, "fills": [],
                       "side": "long" if sgn > 0 else "short",
                       "open_ts": a["transaction_time"]}
            cur["fills"].append(a)
            pos += sgn * q
            if abs(pos) < 1e-9:
                cur["close_ts"] = a["transaction_time"]
                closed.append(cur)
                cur, pos = None, 0.0
        if cur is not None:
            cur["open_qty"] = pos
            still_open.append(cur)
    for t in closed + still_open:
        opn = [a for a in t["fills"] if (a["side"] == "buy") == (t["side"] == "long")]
        cls = [a for a in t["fills"] if a not in opn]
        oq = sum(f(a["qty"]) for a in opn)
        cq = sum(f(a["qty"]) for a in cls)
        t["qty"] = oq
        t["entry_px"] = sum(f(a["qty"]) * f(a["price"]) for a in opn) / oq if oq else None
        t["exit_px"] = (sum(f(a["qty"]) * f(a["price"]) for a in cls) / cq) if cq else None
        t["entry_order_ids"] = sorted({a["order_id"] for a in opn})
        t["exit_order_ids"] = sorted({a["order_id"] for a in cls})
        t["last_exit_order"] = cls[-1]["order_id"] if cls else None
        if t.get("close_ts"):
            cash = sum((f(a["qty"]) * f(a["price"])) * (-1 if a["side"] == "buy" else 1)
                       for a in t["fills"])
            t["pnl"] = cash * t["mult"]
            t["cost"] = t["entry_px"] * oq * t["mult"]
    return closed, still_open


# ── attribution ─────────────────────────────────────────────────────────────

def _order_ids(detail):
    ids = set()
    if not isinstance(detail, dict):
        return ids
    for k in ("order_id", "close_order_id"):
        if detail.get(k):
            ids.add(detail[k])
    o = detail.get("order")
    if isinstance(o, dict):
        for k in ("order_id", "id"):
            if o.get(k):
                ids.add(o[k])
    return ids


ENTRY_KINDS = ("entry", "zone_entry", "auto_entry", "catalyst_entry",
               "hot_pullback_entry", "adopt_protect")


def attribute_stock(t, by_oid, by_sym):
    sym = t["symbol"]
    rows = []
    for oid in t["entry_order_ids"]:
        rows.extend(by_oid.get(oid, []))
    matched = "order_id" if rows else None
    o_ep = to_dt(t["open_ts"]).timestamp()
    if not rows:
        rows = [r for r in by_sym.get(sym, [])
                if r["kind"] in ENTRY_KINDS
                and abs((f(r.get("epoch")) or 0) - o_ep) <= MATCH_WINDOW_SEC]
        matched = "proximity" if rows else None
    day = et(to_dt(t["open_ts"])).date()
    # same-ET-day funnel rows (auto_entry / zone_entry / catalyst) enrich it
    for r in by_sym.get(sym, []):
        if r["kind"] in ("auto_entry", "zone_entry", "catalyst_entry",
                         "hot_pullback_entry") and r not in rows:
            rd = to_dt(r.get("ts") or r.get("epoch"))
            if rd and et(rd).date() == day and (f(r.get("epoch")) or 0) <= o_ep + 60:
                rows.append(r)
    kinds = {r["kind"]: r for r in rows}
    ent = kinds.get("entry")
    det = (ent or {}).get("detail") or {}
    lane = det.get("strategy")
    if not lane:
        if "auto_entry" in kinds:
            lane = "minervini"
        elif "zone_entry" in kinds:
            lane = "zone_edge"
        elif "catalyst_entry" in kinds:
            lane = "catalyst"
        elif "hot_pullback_entry" in kinds:
            lane = "hot_pullback"
        elif ent is not None:
            lane = "manual"
        elif "adopt_protect" in kinds:
            lane = "adopted_outside_engine"
        else:
            lane = "unledgered"
    signal = lane
    if "zone_entry" in kinds:
        zd = kinds["zone_entry"].get("detail") or {}
        signal = "zone:%s/%s" % (zd.get("kind"), zd.get("tier"))
    elif "auto_entry" in kinds:
        signal = "minervini:%s" % ((kinds["auto_entry"].get("detail") or {}).get("path"))
    elif "catalyst_entry" in kinds:
        cd = kinds["catalyst_entry"].get("detail") or {}
        signal = "catalyst:%s" % (cd.get("kind") or cd.get("catalyst_kind") or cd.get("event") or "?")
    elif det.get("entry_reason"):
        er = det["entry_reason"]
        if isinstance(er, dict):
            signal = "%s:%s/%s" % (lane, er.get("side"), er.get("tier"))
    t["lane"] = lane
    t["signal"] = signal
    t["matched_by"] = matched
    t["entry_row"] = ent
    t["funnel_rows"] = {k: v for k, v in kinds.items() if k != "entry"}
    t["stop_price"] = f(det.get("stop_price"))
    if t["stop_price"] is None and "adopt_protect" in kinds:
        t["stop_price"] = f((kinds["adopt_protect"].get("detail") or {}).get("stop_price"))
    t["intended_px"] = f(det.get("price"))
    t["regime_app"] = det.get("regime") or "unknown"
    t["size_multiplier"] = det.get("size_multiplier")
    t["equity_risk_pct"] = f(det.get("equity_risk_pct"))
    t["allocation"] = f(det.get("allocation"))
    t["equity_used"] = f(det.get("equity_used"))
    er = det.get("entry_reason") if isinstance(det.get("entry_reason"), dict) else {}
    zd = (kinds.get("zone_entry") or {}).get("detail") or {}
    t["gate"] = er.get("gate") or zd.get("gate")
    t["band"] = er.get("band") or zd.get("band")
    t["zone_side"] = er.get("side") or zd.get("side")
    t["cap_at_entry"] = f(zd.get("cap"))


def exit_reason_stock(t, by_oid, by_sym, orders_by_id):
    oid = t.get("last_exit_order")
    for r in by_oid.get(oid, []):
        k = r["kind"]
        if k == "trade_closed":
            return "stop" if (r.get("detail") or {}).get("leg") == "stop" else \
                (r.get("detail") or {}).get("leg") or "trade_closed"
        if k in ("flatten", "flatten_done"):
            return "flatten(manual/queue)"
        if k in ("hot_pullback_exit",):
            return "hot_pullback_exit"
    c_ep = to_dt(t["close_ts"]).timestamp()
    near = [r for r in by_sym.get(t["symbol"], [])
            if abs((f(r.get("epoch")) or 0) - c_ep) <= MATCH_WINDOW_SEC]
    for k, lab in (("trade_closed", None), ("distribution_exit", "distribution_exit(stage3)"),
                   ("watchdog_exit", "watchdog_stop(no broker stop)"),
                   ("flatten", "flatten(manual/queue)"), ("flatten_done", "flatten(manual/queue)"),
                   ("hot_pullback_exit", "hot_pullback_exit")):
        for r in near:
            if r["kind"] == k:
                if k == "trade_closed":
                    leg = (r.get("detail") or {}).get("leg")
                    return "stop" if leg == "stop" else (leg or "trade_closed")
                return lab
    for r in by_sym.get(None, []):
        if r["kind"] == "flatten_all" and abs((f(r.get("epoch")) or 0) - c_ep) <= MATCH_WINDOW_SEC:
            return "flatten_all"
    o = orders_by_id.get(oid) or {}
    typ = o.get("type") or o.get("order_type") or "?"
    ce = et(to_dt(t["close_ts"]))
    if typ == "market" and ce and (ce.hour, ce.minute) >= (15, 50):
        return "broker:market_eod"
    if typ in ("stop", "stop_limit", "trailing_stop"):
        return "stop(broker,unledgered)"
    if typ == "limit" and o.get("order_class") in ("bracket", "oco"):
        return "take_profit(broker,unledgered)"
    return "broker:%s(unledgered)" % typ


# ── market context ──────────────────────────────────────────────────────────

class Bars:
    def __init__(self, enabled):
        self.enabled = enabled
        self.cache = {}

    def daily(self, sym):
        if not self.enabled:
            return None
        if sym not in self.cache:
            try:
                from trading.autopsy import _daily_bars
                self.cache[sym] = _daily_bars(sym)
            except Exception:                      # noqa: BLE001
                self.cache[sym] = None
        return self.cache[sym]


def closes_before(bars, day):
    return [b for b in (bars or []) if b["date"] < day and not b.get("live")]


def sma(xs, n):
    return sum(xs[-n:]) / n if len(xs) >= n else None


def atr_pct(bars, day, n=14):
    """Wilder-free simple ATR% over the n closed sessions before `day`
    (the owner autopsy ATR is quoted the same way: trading.autopsy.atr_pct)."""
    try:
        from trading.autopsy import atr_pct as _a, ATR_DAYS
        prev = closes_before(bars, day)
        if not prev:
            return None
        return _a(bars, day, prev[-1]["close"], ATR_DAYS)
    except Exception:                              # noqa: BLE001
        return None


def context(t, bars):
    d = et(to_dt(t["open_ts"])).date()
    spy = closes_before(bars.daily("SPY"), d)
    t["spy_trend"] = "unknown"
    if spy:
        c = [b["close"] for b in spy]
        s50, s200 = sma(c, 50), sma(c, 200)
        if s50 and s200:
            t["spy_trend"] = "%s50/%s200" % ("above" if c[-1] > s50 else "below",
                                             "above" if c[-1] > s200 else "below")
    vix = closes_before(bars.daily("^VIX"), d)
    t["vix"] = vix[-1]["close"] if vix else None
    try:
        from sepa.iv_read import classify
        t["vix_bucket"] = classify(t["vix"]) or "unknown"
    except Exception:                              # noqa: BLE001
        t["vix_bucket"] = "unknown"
    und = t.get("underlying") or t["symbol"]
    if t["asset"] == "stock":
        sb = bars.daily(und)
        t["atr_pct"] = atr_pct(sb, d)
        cd = et(to_dt(t["close_ts"])).date()
        span = [b for b in (sb or []) if d <= b["date"] <= cd and not b.get("live")]
        if span and t.get("entry_px"):
            t["mfe_pct_daily"] = (max(b["high"] for b in span) / t["entry_px"] - 1) * 100
            t["mae_pct_daily"] = (min(b["low"] for b in span) / t["entry_px"] - 1) * 100


# Prior measured evidence for each lane's ENTRY signal, quoted from the
# project memory / docs (each has its own re-runnable script there). This
# script does NOT re-measure them; it only puts them beside the live P&L.
SIGNAL_EVIDENCE = OrderedDict([
    ("minervini", "UNMEASURED as an entry trigger in this repo (no placebo study of "
                  "auto_entry close_confirm/intraday); lid-break->prior-high 57.5% vs "
                  "placebo 24-26% is a DIFFERENT outcome (touch of prior high, not P&L)"),
    ("breakout", "zone breakout lane: S/D zones beat SPY nowhere (board = watchlist); "
                 "entry-trigger/ENTERABLE study no_signal (confirmation entries = cushion)"),
    ("zone_edge", "same signal as breakout (pre-2026-09-05 untagged rows)"),
    ("demand_zone", "same-day demand alerts = coin flip; bounce-gate baseline 24% win / "
                    "75% stop-out; deep-demand levels null; sector heat null"),
    ("catalyst", "8-K small caps = volatility not direction; index adds lose ~10pp; "
                 "promo first-tag INVERTED"),
    ("options_zone", "signal shared with zone_edge_entry (demand/breakout touch) -> "
                     "inherits the null zone evidence"),
    ("zero_dte", "signal_lab ORB+sweep+BOS 1-min tags: NO placebo study (docs/"
                 "trading_zero_dte_lane.md 'No placebo yet'); ICT study no edge "
                 "(+0.03R); raid-low entry no_signal"),
    ("hot_pullback", "corrected to null (+0.100R, CI includes 0); lane has no fills"),
])


# ── main ────────────────────────────────────────────────────────────────────

def main(argv):
    out_path = argv[1] if len(argv) > 1 else "/tmp/autopilot_autopsy.json"
    use_bars = "--no-bars" not in argv
    from trading.safety_floor import MIN_SHARE_PRICE, MIN_CAP_USD, market_cap
    from trading import risk_rules

    acct, positions, hist, acts, orders = broker_pull()
    led, opts, zdte, blocked, baseline, autops, misc = mongo_pull()
    orders_by_id = {o["id"]: o for o in orders}
    fills = [a for a in acts if a.get("activity_type") == "FILL"]
    other = defaultdict(float)
    for a in acts:
        if a.get("activity_type") != "FILL":
            other[a.get("activity_type")] += f(a.get("net_amount")) or 0.0

    by_oid, by_sym = defaultdict(list), defaultdict(list)
    for r in led:
        for oid in _order_ids(r.get("detail")):
            by_oid[oid].append(r)
        by_sym[r.get("symbol")].append(r)
    opt_by_leg = {}
    for p in opts:
        for leg in p.get("legs") or []:
            opt_by_leg.setdefault(leg["symbol"], []).append(p)
    z_by_occ = defaultdict(list)
    for p in zdte:
        if p.get("occ"):
            z_by_occ[p["occ"]].append(p)

    closed, still_open = round_trips(fills)
    out = OrderedDict()
    print("# Auto-Pilot autopsy 2026-09-27 — broker-fill ground truth (READ-ONLY)")
    print("fills=%d closed_round_trips=%d open=%d orders=%d ledger_rows=%d" % (
        len(fills), len(closed), len(still_open), len(orders), len(led)))

    # ── 1. account curve ────────────────────────────────────────────────────
    eq = [(datetime.fromtimestamp(ts, tz=timezone.utc).date(), f(e))
          for ts, e in zip(hist.get("timestamp") or [], hist.get("equity") or [])
          if f(e)]
    peak, mdd, mdd_at, peak_at = -1, 0.0, None, None
    for d, e in eq:
        if e > peak:
            peak, peak_at = e, d
        dd = (e / peak - 1) * 100
        if dd < mdd:
            mdd, mdd_at = dd, (peak_at, d)
    weekly = OrderedDict()
    for d, e in eq:
        wk = (d - timedelta(days=d.weekday())).isoformat()
        weekly[wk] = e
    prev = None
    wk_rows = []
    for wk, e in weekly.items():
        wk_rows.append({"week_of": wk, "equity_close": r2(e),
                        "chg": r2(e - prev) if prev else None})
        prev = e
    realised = sum(t["pnl"] for t in closed)
    unreal = sum(f(p.get("unrealized_pl")) or 0 for p in positions)
    start = f(hist.get("base_value")) or 100000.0
    cur = f(acct.get("equity"))
    out["account"] = OrderedDict(
        created_at=acct.get("created_at"), starting_equity=start,
        engine_baseline_doc=baseline, equity_now=cur,
        total_change=r2(cur - start), total_change_pct=r2((cur / start - 1) * 100),
        realised_closed_round_trips=r2(realised), unrealised_open=r2(unreal),
        non_fill_activity_net=dict(other),
        reconcile_residual=r2(cur - start - realised - unreal
                              - sum(v for k, v in other.items() if k != "JNLC")),
        max_drawdown_pct=r2(mdd), max_drawdown_window=[str(x) for x in (mdd_at or [])],
        weekly=wk_rows, open_positions=[{k: p.get(k) for k in (
            "symbol", "asset_class", "qty", "avg_entry_price", "current_price",
            "unrealized_pl")} for p in positions])
    a = out["account"]
    print("\n## 1. ACCOUNT")
    for k in ("created_at", "starting_equity", "equity_now", "total_change",
              "total_change_pct", "realised_closed_round_trips", "unrealised_open",
              "non_fill_activity_net", "reconcile_residual", "max_drawdown_pct",
              "max_drawdown_window", "engine_baseline_doc"):
        print("%-28s %s" % (k, a[k]))
    print("week_of      equity     chg")
    for w in wk_rows:
        print("%s %10s %8s" % (w["week_of"], w["equity_close"], w["chg"]))

    # ── build trade records ─────────────────────────────────────────────────
    from trading import autopsy as ap
    bars = Bars(use_bars)
    trades = []
    opt_groups = OrderedDict()
    for t in closed:
        m = OCC_RE.match(t["symbol"])
        t["asset"] = "option" if m else "stock"
        t["underlying"] = m.group(1) if m else t["symbol"]
        if m:
            p = None
            for cand in opt_by_leg.get(t["symbol"], []) + z_by_occ.get(t["symbol"], []):
                ce = to_dt(cand.get("entry_ts") or cand.get("fill_ts") or cand.get("order_ts"))
                if ce and abs(ce.timestamp() - to_dt(t["open_ts"]).timestamp()) < 86400 * 3:
                    p = cand
                    break
            key = (p or {}).get("pos_id") or ("unmatched:" + t["symbol"] + ":" + t["open_ts"])
            g = opt_groups.setdefault(key, {"pos": p, "legs": []})
            g["legs"].append(t)
            continue
        attribute_stock(t, by_oid, by_sym)
        t["exit_reason"] = exit_reason_stock(t, by_oid, by_sym, orders_by_id)
        trades.append(t)

    for key, g in opt_groups.items():
        p = g["pos"] or {}
        legs = g["legs"]
        t = {"symbol": key, "asset": "option",
             "underlying": legs[0]["underlying"],
             "open_ts": min(x["open_ts"] for x in legs),
             "close_ts": max(x["close_ts"] for x in legs),
             "pnl": sum(x["pnl"] for x in legs),
             "lane": p.get("strategy") or "options_unattributed",
             "legs": [x["symbol"] for x in legs],
             "structure": p.get("structure") or ("long_" + ("call" if "C" in legs[0]["symbol"][-9] else "put")),
             "exit_reason": p.get("close_reason") or "unknown",
             "pos": p}
        if p.get("strategy") == "zero_dte":
            prem = (f(p.get("fill_price")) or 0) * 100 * (f(p.get("fill_qty") or p.get("qty")) or 0)
            t["signal"] = "zero_dte:%s/%s" % (p.get("side"), (p.get("regime") or {}).get("regime"))
            t["risk"] = prem or None
            t["premium_paid"] = prem
            t["dte_entry"] = 0
        else:
            debit = f(p.get("debit"))
            ml = f(p.get("max_loss"))
            t["signal"] = "options_zone:%s" % p.get("structure")
            t["risk"] = ml
            t["premium_paid"] = debit * 100 * (f(p.get("qty")) or 0) if debit and debit > 0 else None
            t["dte_entry"] = p.get("dte")
        exp = p.get("expiry")
        t["dte_exit"] = ((date.fromisoformat(exp) - et(to_dt(t["close_ts"])).date()).days
                         if exp else None)
        t["entry_px"] = None
        t["regime_app"] = "n/a"
        trades.append(t)

    for t in trades:
        o = et(to_dt(t["open_ts"]))
        c = et(to_dt(t["close_ts"]))
        t["hold_h"] = (c - o).total_seconds() / 3600
        t["hold_bucket"] = ("same_day" if o.date() == c.date() else
                            "1-3d" if (c.date() - o.date()).days <= 3 else
                            "4-10d" if (c.date() - o.date()).days <= 10 else ">10d")
        t["entry_hour_et"] = "%02d:00" % o.hour
        mins = (o.hour * 60 + o.minute) - (9 * 60 + 30)
        t["session_bucket"] = (
            "pre/after hours" if mins < 0 or mins >= ap.SESSION_MINUTES else
            "first %d min" % ap.FIRST_MINUTES if mins < ap.FIRST_MINUTES else
            "last %d min" % (ap.SESSION_MINUTES - ap.LATE_MINUTES) if mins >= ap.LATE_MINUTES
            else "mid-session")
        t["era"] = ("pre-reset (<2026-07-13)" if o.date() < date(2026, 7, 13)
                    else "post-reset")
        eq_at = [e for d_, e in eq if d_ < o.date()]
        t["equity_at_open"] = eq_at[-1] if eq_at else start
        t["weekday"] = o.strftime("%a")
        t["week_of"] = (o.date() - timedelta(days=o.weekday())).isoformat()
        if t["asset"] == "stock":
            sp = t.get("stop_price")
            if sp and t.get("entry_px") and t["side"] == "long" and t["entry_px"] > sp:
                t["risk"] = (t["entry_px"] - sp) * t["qty"]
            else:
                t["risk"] = None
            if t.get("cap_at_entry") is None:
                t["cap_now"] = market_cap(t["symbol"])
        t["r"] = (t["pnl"] / t["risk"]) if t.get("risk") else None
        t["risk_pct_equity"] = (t["risk"] / t["equity_at_open"] * 100
                                if t.get("risk") and t.get("equity_at_open") else None)
        t["pnl_pct"] = (t["pnl"] / t["cost"] * 100) if t.get("cost") else None
        context(t, bars)

    stock = [t for t in trades if t["asset"] == "stock"]
    optn = [t for t in trades if t["asset"] == "option"]
    now_iso = datetime.now(timezone.utc).isoformat()
    spans = [(to_dt(t["open_ts"]), to_dt(t["close_ts"])) for t in stock] + \
            [(to_dt(t["open_ts"]), to_dt(now_iso)) for t in still_open
             if not OCC_RE.match(t["symbol"])]
    for t in stock:
        o = to_dt(t["open_ts"])
        t["concurrent_stock_positions"] = sum(1 for a_, b_ in spans if a_ <= o < b_)
        t["entries_same_et_day"] = sum(
            1 for x in stock if et(to_dt(x["open_ts"])).date() == et(o).date())
        t["et_day"] = et(o).date().isoformat()

    def terciles(vals):
        v = sorted(x for x in vals if x is not None)
        if len(v) < 3:
            return None
        return (v[len(v) // 3], v[2 * len(v) // 3])

    pt = terciles([t.get("entry_px") for t in stock])
    capv = [t.get("cap_at_entry") or t.get("cap_now") for t in stock]
    ct = terciles(capv)

    def pbucket(t):
        p = t.get("entry_px")
        if p is None or not pt:
            return "unknown"
        if p < MIN_SHARE_PRICE:
            return "<$%g floor" % MIN_SHARE_PRICE
        return ("T1 <$%.0f" % pt[0] if p < pt[0] else
                "T2 $%.0f-%.0f" % pt if p < pt[1] else "T3 >=$%.0f" % pt[1])

    def cbucket(t):
        c = t.get("cap_at_entry") or t.get("cap_now")
        if c is None or not ct:
            return "unknown"
        if c < MIN_CAP_USD:
            return "<$%.0fM floor" % (MIN_CAP_USD / 1e6)
        return ("T1 <$%.1fB" % (ct[0] / 1e9) if c < ct[0] else
                "T2 $%.1f-%.1fB" % (ct[0] / 1e9, ct[1] / 1e9) if c < ct[1]
                else "T3 >=$%.1fB" % (ct[1] / 1e9))

    # ── 2. P&L tables ───────────────────────────────────────────────────────
    print("\n## 2. P&L BY BUCKET — ALL CLOSED (stocks + option positions)")
    tabs = OrderedDict()
    table("lane (all)", trades, lambda t: t["lane"], tabs)
    table("signal kind (all)", trades, lambda t: t.get("signal"), tabs)
    table("exit reason (stocks)", stock, lambda t: t["exit_reason"], tabs)
    table("hold time (all)", trades, lambda t: t["hold_bucket"], tabs)
    table("entry hour ET (all)", trades, lambda t: t["entry_hour_et"], tabs)
    table("session window (autopsy FIRST/LATE_MINUTES) (all)", trades,
          lambda t: t["session_bucket"], tabs)
    table("era (all)", trades, lambda t: t["era"], tabs)
    table("lane x era", trades, lambda t: "%s | %s" % (t["lane"], t["era"][:9]), tabs)
    table("weekday (all)", trades, lambda t: t["weekday"], tabs)
    table("app regime at entry (stocks)", stock, lambda t: t.get("regime_app"), tabs)
    table("SPY vs 50/200d (all)", trades, lambda t: t.get("spy_trend"), tabs)
    table("VIX bucket iv_read.classify (all)", trades, lambda t: t.get("vix_bucket"), tabs)
    table("price tercile (stocks)", stock, pbucket, tabs)
    table("cap tercile (stocks)", stock, cbucket, tabs)
    table("entry week (all)", trades, lambda t: t["week_of"], tabs)
    table("attribution method (stocks)", stock, lambda t: t.get("matched_by"), tabs)
    table("concurrent open stock positions vs risk_rules.MAX_POSITIONS (stocks)", stock,
          lambda t: "<= MAX_POSITIONS (%d)" % risk_rules.MAX_POSITIONS
          if t["concurrent_stock_positions"] <= risk_rules.MAX_POSITIONS
          else "> MAX_POSITIONS (%d)" % risk_rules.MAX_POSITIONS, tabs)
    table("entry ET day (stocks)", stock,
          lambda t: "%s (%d entries)" % (t["et_day"], t["entries_same_et_day"]), tabs)
    out["tables"] = tabs
    print("\n### risk per trade by lane (R = entry-to-stop $ for stocks; premium / max_loss for options)")
    rk = OrderedDict()
    for lane in sorted({t["lane"] for t in trades}):
        ts = [t for t in trades if t["lane"] == lane and t.get("risk")]
        if not ts:
            continue
        rk[lane] = {"n": len(ts),
                    "mean_risk_usd": r2(sum(t["risk"] for t in ts) / len(ts)),
                    "mean_risk_pct_equity": r2(sum(t["risk_pct_equity"] or 0 for t in ts) / len(ts), 3),
                    "max_risk_usd": r2(max(t["risk"] for t in ts)),
                    "mean_loss_in_R": r2(sum(t["r"] for t in ts if t["pnl"] <= 0) /
                                         max(1, sum(1 for t in ts if t["pnl"] <= 0)), 3),
                    "mean_win_in_R": r2(sum(t["r"] for t in ts if t["pnl"] > 0) /
                                        max(1, sum(1 for t in ts if t["pnl"] > 0)), 3)}
        print("%-16s %s" % (lane, rk[lane]))
    out["risk_by_lane"] = rk
    out["overall"] = {"all": stats(trades), "stocks": stats(stock), "options": stats(optn)}
    print("\nOVERALL all=%s" % dict(out["overall"]["all"]))
    print("OVERALL stocks=%s" % dict(out["overall"]["stocks"]))
    print("OVERALL options=%s" % dict(out["overall"]["options"]))

    # ── 3. execution quality ────────────────────────────────────────────────
    print("\n## 3. EXECUTION QUALITY (stocks)")
    ex = OrderedDict()
    slips = []
    for t in stock:
        if t.get("intended_px") and t.get("entry_px"):
            slips.append(((t["entry_px"] / t["intended_px"]) - 1) * 1e4)
    ex["entry_slippage_bps"] = {"n": len(slips), "mean": r2(sum(slips) / len(slips)) if slips else None,
                                "ci": [r2(x) for x in boot_ci(slips)],
                                "worst": r2(max(slips)) if slips else None}
    gaps = []
    for t in stock:
        if t["exit_reason"].startswith("stop") or t["exit_reason"].startswith("watchdog"):
            if t.get("stop_price") and t.get("exit_px"):
                gaps.append({"symbol": t["symbol"], "stop": t["stop_price"],
                             "exit": r2(t["exit_px"], 4),
                             "through_pct": r2((t["exit_px"] / t["stop_price"] - 1) * 100),
                             "extra_usd": r2((t["exit_px"] - t["stop_price"]) * t["qty"])})
    ex["stop_exits_vs_stop_price"] = gaps
    ex["gap_through_total_usd"] = r2(sum(g["extra_usd"] for g in gaps if g["extra_usd"] < 0))
    outside = []
    for t in stock:
        b = t.get("band") or {}
        if b.get("hi") and t.get("entry_px"):
            outside.append({"symbol": t["symbol"], "signal": t["signal"],
                            "fill": r2(t["entry_px"], 3), "band": [b.get("lo"), b.get("hi")],
                            "pct_above_band_hi": r2((t["entry_px"] / b["hi"] - 1) * 100)})
    ex["fill_vs_band"] = outside
    st = defaultdict(int)
    for o in orders:
        st["%s/%s/%s" % (o.get("status"), o.get("type"), o.get("side"))] += 1
    ex["order_status_counts"] = dict(sorted(st.items(), key=lambda kv: -kv[1]))
    ex["rejected_orders"] = [{k: o.get(k) for k in ("symbol", "type", "side", "submitted_at", "status")}
                             for o in orders if o.get("status") == "rejected"]
    ex["flatten_failures"] = [{"ts": r["ts"], "symbol": r.get("symbol"), "kind": r["kind"],
                               "err": str((r.get("detail") or {}).get("error"))[:160]}
                              for r in led if r["kind"] in ("flatten_queued",)
                              or (r["kind"] == "flatten" and (r.get("detail") or {}).get("closed") is False)]
    dup = defaultdict(list)
    for t in stock:
        dup[(t["symbol"], et(to_dt(t["open_ts"])).date().isoformat())].append(t)
    ex["same_symbol_same_day_stock_trips"] = [{"symbol": k[0], "day": k[1], "n": len(v)}
                                              for k, v in dup.items() if len(v) > 1]
    zd = defaultdict(int)
    for t in optn:
        if t["lane"] == "zero_dte":
            zd[(t["underlying"], et(to_dt(t["open_ts"])).date().isoformat())] += 1
    ex["zero_dte_multi_entries_per_symbol_day"] = {"%s %s" % k: v for k, v in zd.items() if v > 1}
    ex["gate_not_ok"] = [{"symbol": t["symbol"], "lane": t["lane"], "gate": t.get("gate")}
                         for t in stock if isinstance(t.get("gate"), dict) and t["gate"].get("ok") is False]
    ex["demand_or_catalyst_without_gate_record"] = [
        {"symbol": t["symbol"], "lane": t["lane"], "open": t["open_ts"]}
        for t in stock if t["lane"] in ("demand_zone", "catalyst") and not t.get("gate")]
    ex["safety_floor_breaches"] = [
        {"symbol": t["symbol"], "lane": t["lane"], "fill": r2(t.get("entry_px"), 3),
         "cap_at_entry": t.get("cap_at_entry"), "cap_now": t.get("cap_now")}
        for t in stock if (t.get("entry_px") or 99) < MIN_SHARE_PRICE
        or ((t.get("cap_at_entry") or 1e18) < MIN_CAP_USD)]
    ex["floor_breach_by_cap_now_only"] = [
        {"symbol": t["symbol"], "lane": t["lane"], "cap_now": t.get("cap_now")}
        for t in stock if t.get("cap_at_entry") is None and t.get("cap_now") is not None
        and t["cap_now"] < MIN_CAP_USD]
    sa = []
    for t in stock:
        if t.get("stop_price") and t.get("entry_px") and t.get("atr_pct"):
            sp = (1 - t["stop_price"] / t["entry_px"]) * 100
            sa.append({"symbol": t["symbol"], "lane": t["lane"], "stop_pct": r2(sp),
                       "atr_pct": r2(t["atr_pct"]), "stop_in_atr": r2(sp / t["atr_pct"]),
                       "pnl": r2(t["pnl"])})
    ex["stop_vs_atr"] = sa
    inside = [x for x in sa if x["stop_in_atr"] is not None and x["stop_in_atr"] < 1.0]
    ex["stop_inside_1atr"] = {"n": len(inside), "of": len(sa),
                              "stats": stats([{"pnl": x["pnl"], "r": None} for x in inside]),
                              "rest_stats": stats([{"pnl": x["pnl"], "r": None} for x in sa if x not in inside])}
    sz = []
    for t in stock:
        alloc, eqd = t.get("allocation"), t.get("equity_used")
        if alloc and eqd:
            frac = alloc / eqd
            if frac > risk_rules.MAX_POSITION_FRACTION + 1e-6:
                sz.append({"symbol": t["symbol"], "frac": r2(frac, 3)})
    ex["position_over_MAX_POSITION_FRACTION"] = sz
    ex["entries_above_MAX_POSITIONS"] = [
        {"symbol": t["symbol"], "lane": t["lane"], "open": t["open_ts"][:16],
         "concurrent": t["concurrent_stock_positions"], "pnl": r2(t["pnl"])}
        for t in stock if t["concurrent_stock_positions"] > risk_rules.MAX_POSITIONS]
    ex["max_concurrent_stock_positions"] = max(
        (t["concurrent_stock_positions"] for t in stock), default=None)
    ex["unledgered_stock_trips"] = [{"symbol": t["symbol"], "open": t["open_ts"],
                                     "pnl": r2(t["pnl"])} for t in stock if t["lane"] == "unledgered"]
    out["execution"] = ex
    for k, v in ex.items():
        print("-- %s: %s" % (k, json.dumps(v, default=str)[:3000]))

    # ── 4. options ──────────────────────────────────────────────────────────
    print("\n## 4. OPTIONS (per position)")
    orows = []
    for t in sorted(optn, key=lambda t: t["open_ts"]):
        p = t.get("pos") or {}
        dirn = None
        if p.get("strategy") == "zero_dte" and p.get("contract"):
            dl = f((p.get("contract") or {}).get("delta"))
            sm = f(p.get("stock_move_pct"))
            spot = f(p.get("spot"))
            q = f(p.get("fill_qty") or p.get("qty"))
            if dl is not None and sm is not None and spot and q:
                sgn = 1 if p.get("side") == "call" else -1
                dirn = sgn * abs(dl) * spot * sm / 100 * 100 * q
        row = OrderedDict(
            pos=t["symbol"], lane=t["lane"], structure=t.get("structure"),
            open=t["open_ts"][:16], dte_entry=t.get("dte_entry"), dte_exit=t.get("dte_exit"),
            premium_paid=r2(t.get("premium_paid")), risk=r2(t.get("risk")),
            pnl=r2(t["pnl"]),
            pnl_pct_of_risk=r2(t["pnl"] / t["risk"] * 100) if t.get("risk") else None,
            stock_move_pct=p.get("stock_move_pct"),
            delta_direction_usd=r2(dirn),
            residual_theta_spread_gamma_usd=r2(t["pnl"] - dirn) if dirn is not None else None,
            engine_realized=p.get("realized_pnl"),
            exit=(t.get("exit_reason") or "")[:70])
        orows.append(row)
        print(json.dumps(row, default=str))
    out["options"] = orows
    zrows = [r for r in orows if r["lane"] == "zero_dte" and r["delta_direction_usd"] is not None]
    out["zero_dte_decomposition"] = {
        "n": len(zrows),
        "sum_pnl": r2(sum(r["pnl"] for r in zrows)),
        "sum_delta_direction": r2(sum(r["delta_direction_usd"] for r in zrows)),
        "sum_residual": r2(sum(r["residual_theta_spread_gamma_usd"] for r in zrows)),
        "stock_moved_our_way": sum(1 for r in zrows if (r["delta_direction_usd"] or 0) > 0),
        "stock_moved_our_way_but_lost": sum(1 for r in zrows if (r["delta_direction_usd"] or 0) > 0 and r["pnl"] <= 0),
    }
    zd_ = out["zero_dte_decomposition"]
    lo_, hi_ = wilson(zd_["stock_moved_our_way"], zd_["n"])
    zd_["moved_our_way_pct"] = r2(zd_["stock_moved_our_way"] / zd_["n"] * 100, 1) if zd_["n"] else None
    zd_["moved_our_way_ci"] = [r2((lo_ or 0) * 100, 1), r2((hi_ or 0) * 100, 1)]
    print("0DTE decomposition:", zd_)
    zs = defaultdict(int)
    for d in misc.get("zero_dte_lane_state") or []:
        zs["%s | %s | %s" % ("SPY" if d.get("symbol") == "SPY" else "other",
                             d.get("result"),
                             re.sub(r"[\d.]+", "#", str(d.get("reason") or ""))[:50])] += 1
    out["zero_dte_attempts"] = dict(sorted(zs.items()))
    zm = defaultdict(lambda: [0, 0])
    for r in led:
        if r["kind"] == "zero_dte_entry":
            zm[r.get("symbol")][0] += 1
        elif r["kind"] == "zero_dte_missed":
            zm[r.get("symbol")][1] += 1
    out["zero_dte_entries_vs_missed_fills"] = {k: {"orders": v[0], "missed": v[1]}
                                               for k, v in sorted(zm.items())}
    print("0DTE orders vs missed (limit never filled):", json.dumps(out["zero_dte_entries_vs_missed_fills"]))
    print("0DTE attempts (symbol|result|reason):")
    for k, v in sorted(zs.items()):
        print("  %4d  %s" % (v, k))
    table("options lane", optn, lambda t: t["lane"], tabs)
    table("options exit reason", optn, lambda t: re.sub(r"[\d.]+", "#", (t.get("exit_reason") or "?"))[:34], tabs)
    table("0DTE underlying", [t for t in optn if t["lane"] == "zero_dte"], lambda t: t["underlying"], tabs)
    table("0DTE GEX regime", [t for t in optn if t["lane"] == "zero_dte"],
          lambda t: ((t.get("pos") or {}).get("regime") or {}).get("regime"), tabs)
    br = defaultdict(int)
    for b in blocked:
        br[re.sub(r"[\d.]+", "#", str((b.get("detail") or {}).get("reason") or "?"))[:60]] += 1
    out["options_blocked_reasons"] = dict(sorted(br.items(), key=lambda kv: -kv[1])[:15])
    print("options_blocked (dry-run) top reasons:", json.dumps(out["options_blocked_reasons"]))

    # ── 5. biggest losers ───────────────────────────────────────────────────
    print("\n## 5. 15 BIGGEST LOSERS")
    losers = sorted([t for t in trades if t["pnl"] < 0], key=lambda t: t["pnl"])[:15]
    lrows = []
    for t in losers:
        cls, line = None, None
        if t["asset"] == "stock":
            ent = t.get("entry_row") or {}
            tid = "%s-%d" % (t["symbol"], int(round(f(ent.get("epoch")) or 0)))
            doc = autops.get(tid)
            if doc:
                cls, line = "owner:" + str(doc.get("classification")), doc.get("feedback")
            else:
                n = {"exit_price": t.get("exit_px"),
                     "leg": "stop" if t["exit_reason"].startswith("stop") else t["exit_reason"],
                     "mfe_r": ((t.get("mfe_pct_daily") or 0) / 100 * t["entry_px"] * t["qty"] / t["risk"])
                     if t.get("risk") and t.get("mfe_pct_daily") is not None else None,
                     "band": t.get("band")}
                cls = "owner(daily-approx):" + ap.classify(n)
            sp = t.get("stop_price")
            desc = ("%s %s %s: in %.2f out %.2f stop %s (%s ATR) hold %.0fh exit=%s MFE %s%% MAE %s%%"
                    % (t["lane"], t["signal"], t["symbol"], t["entry_px"], t["exit_px"] or 0,
                       sp, next((x["stop_in_atr"] for x in ex["stop_vs_atr"] if x["symbol"] == t["symbol"]), None),
                       t["hold_h"], t["exit_reason"], r2(t.get("mfe_pct_daily")), r2(t.get("mae_pct_daily"))))
        else:
            p = t.get("pos") or {}
            sm = p.get("stock_move_pct")
            cls = ("0dte:wrong_direction" if (sm is not None and ((sm < 0) == (p.get("side") == "call")) and sm != 0)
                   else "0dte:decay_or_spread" if p.get("strategy") == "zero_dte"
                   else "options_zone:" + (t.get("exit_reason") or "?")[:30])
            desc = "%s %s %s pnl %.0f of risk %s; exit: %s" % (
                t["lane"], t.get("structure"), t["symbol"], t["pnl"], r2(t.get("risk")),
                (t.get("exit_reason") or "")[:80])
        row = OrderedDict(symbol=t["symbol"], lane=t["lane"], pnl=r2(t["pnl"]),
                          r=r2(t.get("r"), 2), cls=cls, autopsy=desc, owner_feedback=line)
        lrows.append(row)
        print(json.dumps(row, default=str))
    out["biggest_losers"] = lrows
    cc = defaultdict(list)
    for r in lrows:
        cc[r["cls"]].append(r["symbol"])
    out["loser_classes"] = {k: v for k, v in sorted(cc.items(), key=lambda kv: -len(kv[1]))}
    print("classes:", json.dumps(out["loser_classes"]))

    out["open_round_trips"] = [{"symbol": t["symbol"], "open": t["open_ts"], "qty": t.get("open_qty")}
                               for t in still_open]
    misc.pop("zero_dte_lane_state", None)
    out["misc_counts"] = misc

    # ── 6. signal vs execution ──────────────────────────────────────────────
    print("\n## 6. SIGNAL EVIDENCE PER LANE (prior measured studies; NOT re-measured here)")
    for lane, ev in SIGNAL_EVIDENCE.items():
        s_ = next((r for r in tabs["lane (all)"] if r["bucket"] == lane), None)
        print("%-14s live: n=%s exp$=%s expR=%s total=%s | signal evidence: %s" % (
            lane, s_ and s_["n"], s_ and s_["exp_usd"], s_ and s_["exp_r"],
            s_ and s_["total_usd"], ev))
    out["signal_evidence"] = SIGNAL_EVIDENCE
    out["trades"] = [{k: v for k, v in t.items() if k not in (
        "fills", "entry_row", "funnel_rows", "pos")} for t in trades]
    with open(out_path, "w") as fh:
        json.dump(out, fh, default=str, indent=1)
    print("\nwrote", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
