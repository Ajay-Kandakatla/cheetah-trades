"""Chart Maps lane program — the scoreboard and the daily loss review (PAPER).

Ajay 2026-09-27: "analayze losses everyday with a routine or something and
restategize and confirm with me". There is NO auto-pause:

  * after the close (the first exit_engine tick at/after 16:50 ET on a
    trading day, trading/tick_jobs.py; closed-day gated) this job first
    prices the day's market exits from the broker's own fills
    (journal.resolve_exit_fills, paged closed orders), reconciles the journal,
    then scores every strategy and writes one `lane_reviews` doc per day;
  * each PROPOSED change is a card on the Trading page he can Confirm or
    Dismiss (`lane_proposals`). Confirm applies CONFIG keys only
    (APPLYABLE_KEYS, validated exactly like POST /trading/config); a change
    that needs code becomes a TODO and changes nothing in the engine. Every
    decision is written to the ledger;
  * `latest(fmt="summary")` serves the Claude scheduled routine.

The review itself NEVER writes trading_config and never touches an order.

THE NUMBERS. Win rate carries a Wilson interval, expectancy in R a seeded
percentile bootstrap — never a bare point estimate, never ranked on win rate
alone. Every strategy's prior is null, inverted or unmeasured: this is an
UNMEASURED forward paper measurement, judged in R, not dollars. The kill
proposal waits for KILL_MIN_N closed trades (the autopsy plan's rule #18).

Wording: "reversal", never "bounce", on every line he reads.

CLI:
  python -m trading.lane_review [--day YYYY-MM-DD] [--dry]
  python -m trading.lane_review --backfill-fills --since YYYY-MM-DD [--dry]
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from trading import analytics
from trading import program_caps as PC
from trading import strategy_tags as ST

log = logging.getLogger("trading.lane_review")

ET = ZoneInfo("America/New_York")

REVIEW_COLL = "lane_reviews"
PROPOSALS_COLL = "lane_proposals"
REVIEW_VERSION = "lane-review-v1"
KILL_MIN_N = 20                   # autopsy plan rule #18 — no kill proposal before n = 20
CLASS_PROPOSE_MIN = 3             # Rule #9 — >= 3 losses of one class -> propose a rule
BOOT_B = 2000
BOOT_SEED = 20260927
WILSON_Z = 1.96
SMALL_N = analytics.MIN_RECORD_N
APPLYABLE_KEYS = ("cm_lanes", "cm_lane_caps", "zone_edge_rules")
BROKER_PAGE = 500                 # broker_alpaca.closed_orders_since page size
BROKER_MAX_PAGES = 40
FILLS_LOOKBACK_DAYS = 14          # = exit_engine.STREAK_LOOKBACK_DAYS window
LINK = "https://pounce.ajaykandakatla.dev/trading?view=strategies"
EXIT_KINDS = ("stop", "take_profit", "watchdog_exit", "distribution_exit",
              "hot_pullback_exit", "flatten", "premium_stop", "time")
ZONE_SIDS = ("zones", "quick_bounce")

# Rule #9 class -> what it points at. (config key, value, "only when") or a
# code-level TODO. `unclassified` proposes nothing.
_CODE_TODO = {"market_down": "index filter", "shakeout": "stop buffer",
              "no_follow_through": "time stop or confirmation wait",
              "stop_clamped": "entry width vs band"}

_TAB_LABEL = {"quick_bounce": "Quick Reversal", "zones": "Back in Demand",
              "deep_demand": "Deep Demand", "hot_pullback": "Hot Pullback",
              "amd": "AMD", "ict": "ICT", "ipo": "IPO", "gnt": "GnT",
              "potus": "POTUS", "signals": "Signals / 0DTE"}


# ── plumbing ─────────────────────────────────────────────────────────────────
def _EE():
    from trading import exit_engine
    return exit_engine


def _coll(name: str):
    db = _EE()._db()
    if db is None:
        return None
    try:
        return getattr(db, name)
    except Exception:                              # noqa: BLE001
        return None


def _now_et(now: Optional[datetime] = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc).astimezone(ET)
    return now.replace(tzinfo=ET) if now.tzinfo is None else now.astimezone(ET)


def _f(x) -> Optional[float]:
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and not math.isinf(v) else None


def _day_of(ts) -> Optional[str]:
    if ts is None:
        return None
    f = _f(ts)
    try:
        if f is not None:
            return datetime.fromtimestamp(f, tz=ET).date().isoformat()
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ET).date().isoformat()
    except Exception:                              # noqa: BLE001
        return str(ts)[:10] or None


def label(sid: str) -> str:
    """The tab's human label — 'reversal', never the other word."""
    if sid in _TAB_LABEL:
        return _TAB_LABEL[sid]
    return str(sid or "?").replace("_", " ").title()


def _no_bounce(text: str) -> str:
    def swap(m):
        word = "revers" + {"e": "al", "ed": "ed", "es": "als",
                           "ing": "ing"}[m.group(1).lower()]
        return word.capitalize() if m.group(0)[0].isupper() else word
    return re.sub(r"(?i)bounc(ing|ed|es|e)", swap, text)


# ── statistics ───────────────────────────────────────────────────────────────
def wilson(k, n) -> list:
    """95% Wilson interval for k wins of n, in percent. n < 2 -> [None, None]."""
    try:
        k, n = int(k), int(n)
    except (TypeError, ValueError):
        return [None, None]
    if n < 2 or k < 0 or k > n:
        return [None, None]
    z = WILSON_Z
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, centre - half) * 100, 1), round(min(1.0, centre + half) * 100, 1)]


def boot_mean_ci(xs, B: int = BOOT_B, seed: int = BOOT_SEED) -> list:
    """Seeded percentile bootstrap 95% CI of the mean. n < 2 -> [None, None]."""
    vals = [float(x) for x in (xs or []) if _f(x) is not None]
    n = len(vals)
    if n < 2:
        return [None, None]
    rng = random.Random(seed)
    means = []
    for _ in range(int(B)):
        means.append(sum(vals[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[int(0.025 * (B - 1))]
    hi = means[int(math.ceil(0.975 * (B - 1)))]
    return [round(lo, 3), round(hi, 3)]


# ── normalised round-trips ───────────────────────────────────────────────────
def _journal_exit_kind(x: dict) -> Optional[str]:
    kind = (x or {}).get("kind")
    leg = (x or {}).get("leg")
    if kind in ("watchdog_exit", "distribution_exit", "hot_pullback_exit"):
        return kind
    if kind in ("flatten", "flatten_all", "flatten_done"):
        return "flatten"
    if leg in ("stop", "take_profit", "flatten"):
        return leg
    return leg or kind


def _option_exit_kind(reason: str) -> str:
    r = str(reason or "").lower()
    if "premium" in r:
        return "premium_stop" if "-" in r.split("premium", 1)[1][:4] else "take_profit"
    if "stop" in r or "under the band floor" in r:
        return "stop"
    if "target" in r or "take-profit" in r or "take profit" in r:
        return "take_profit"
    if "flatten" in r or "dte" in r or "earnings" in r or "clock" in r:
        return "time"
    if "owner" in r:
        return "flatten"
    return "time" if not r else "flatten"


def _from_journal(d: dict) -> dict:
    from trading import journal
    e = d.get("entry") or {}
    x = d.get("exit") or {}
    rz = d.get("realized") or {}
    tag = e.get("strategy") or "manual"
    closed = d.get("status") == "closed"
    pnl = _f(rz.get("gain_dollars"))
    er = e.get("entry_reason") if isinstance(e.get("entry_reason"), dict) else {}
    return {"sid": ST.norm(tag), "tag": tag, "symbol": d.get("symbol"), "asset": "stock",
            "entry_ts": e.get("ts"), "exit_ts": x.get("ts"),
            "status": "closed" if closed else "open",
            "pnl_usd": pnl, "risk_usd": journal._initial_risk_dollars(e),
            "r": journal._realized_r(d) if closed else None,
            "exit_reason": rz.get("exit_reason"),
            "exit_kind": _journal_exit_kind(x) if closed else None,
            "price_source": x.get("price_source") or ("ledger" if x.get("price") is not None else None),
            "approx": bool(x.get("approx")), "trade_id": d.get("trade_id"),
            "entry_reason": er or None,
            "snapshot_ref": (e.get("program") or {}).get("snapshot_ref") or er.get("snapshot_ref"),
            "qty": e.get("qty"), "entry_price": e.get("price"),
            "stop_price": e.get("stop_price"), "unpriced": closed and x.get("price") is None}


def _from_zero_dte(d: dict) -> dict:
    from trading import zero_dte_lane
    closed = d.get("status") == "closed"
    fill = _f(d.get("fill_price")) or _f(d.get("limit_price")) or 0.0
    qty = int(d.get("fill_qty") or d.get("qty") or 0)
    risk = fill * 100.0 * qty * zero_dte_lane.PREMIUM_STOP_PCT / 100.0
    pnl = _f(d.get("realized_pnl"))
    r = round(pnl / risk, 2) if (closed and pnl is not None and risk > 0) else None
    return {"sid": ST.norm("zero_dte"), "tag": "zero_dte", "symbol": d.get("symbol"),
            "asset": "option", "entry_ts": d.get("order_ts") or d.get("seen_ts"),
            "exit_ts": d.get("closed_ts"), "status": "closed" if closed else "open",
            "pnl_usd": pnl, "risk_usd": round(risk, 2) if risk else None, "r": r,
            "exit_reason": d.get("close_reason"),
            "exit_kind": _option_exit_kind(d.get("close_reason")) if closed else None,
            "price_source": "lane", "approx": False, "trade_id": d.get("pos_id"),
            "entry_reason": None, "snapshot_ref": None, "qty": qty,
            "entry_price": fill, "stop_price": None,
            "unpriced": closed and d.get("exit_price") is None}


def _from_options(d: dict) -> dict:
    closed = d.get("status") == "closed"
    max_loss = _f(d.get("max_loss"))
    pnl = _f(d.get("realized_pnl"))
    r = round(pnl / max_loss, 2) if (closed and pnl is not None and max_loss) else None
    return {"sid": "options_zone", "tag": "options_zone", "symbol": d.get("symbol"),
            "asset": "option", "entry_ts": d.get("entry_ts"), "exit_ts": d.get("closed_ts"),
            "status": "closed" if closed else "open", "pnl_usd": pnl, "risk_usd": max_loss,
            "r": r, "exit_reason": d.get("close_reason"),
            "exit_kind": _option_exit_kind(d.get("close_reason")) if closed else None,
            "price_source": "lane", "approx": False, "trade_id": d.get("pos_id"),
            "entry_reason": None, "snapshot_ref": None, "qty": d.get("qty"),
            "entry_price": _f(d.get("debit")), "stop_price": None,
            "unpriced": closed and pnl is None}


def trades(since_day: Optional[str] = None, docs: Optional[list] = None) -> list:
    """Normalised round-trips from the stock journal (with the market-exit
    fix), the 0DTE lane's positions and the options lane's positions, entered
    on or after `since_day` (None = all)."""
    out = []
    if docs is None:
        try:
            from trading import journal
            docs = journal.load()
        except Exception as exc:                   # noqa: BLE001
            log.warning("lane_review: journal read failed: %s", exc)
            docs = []
    for d in docs or []:
        if isinstance(d, dict):
            out.append(_from_journal(d))
    for coll_name, conv in (("zero_dte_positions", _from_zero_dte),
                            ("options_positions", _from_options)):
        coll = _coll(coll_name)
        if coll is None:
            continue
        try:
            for d in coll.find({}):
                if isinstance(d, dict) and d.get("status") != "dry_run":
                    out.append(conv(d))
        except Exception as exc:                   # noqa: BLE001
            log.warning("lane_review: %s read failed: %s", coll_name, exc)
    if since_day:
        out = [t for t in out if (_day_of(t.get("entry_ts")) or "") >= since_day]
    return out


# ── the scoreboard ───────────────────────────────────────────────────────────
def empty_board() -> dict:
    return {"n_closed": 0, "n_open": 0, "wins": 0, "losses": 0, "win_pct": None,
            "win_ci": [None, None], "exp_r": None, "exp_r_ci": [None, None],
            "total_usd": 0.0, "open_risk_usd": 0.0, "n_approx": 0, "n_unpriced": 0,
            "exits_by_kind": {}, "last_trade": None, "small_n": True, "measured": False}


def _score(ts: list) -> dict:
    b = empty_board()
    rs, last = [], None
    for t in ts:
        if t["status"] != "closed":
            b["n_open"] += 1
            b["open_risk_usd"] += _f(t.get("risk_usd")) or 0.0
            continue
        b["n_closed"] += 1
        k = t.get("exit_kind") or "other"
        b["exits_by_kind"][k] = b["exits_by_kind"].get(k, 0) + 1
        if t.get("approx"):
            b["n_approx"] += 1
        if t.get("unpriced"):
            b["n_unpriced"] += 1
            continue
        pnl = _f(t.get("pnl_usd"))
        if pnl is not None:
            b["total_usd"] += pnl
            if pnl > 0:
                b["wins"] += 1
            elif pnl < 0:
                b["losses"] += 1
        r = _f(t.get("r"))
        if r is not None:
            rs.append(r)
        stamp = str(t.get("exit_ts") or "")
        if last is None or stamp > str(last.get("at") or ""):
            last = {"symbol": t.get("symbol"), "at": t.get("exit_ts"), "r": t.get("r"),
                    "pnl_usd": pnl}
    decided = b["wins"] + b["losses"]
    b["win_pct"] = round(b["wins"] / decided * 100.0, 1) if decided else None
    b["win_ci"] = wilson(b["wins"], decided)
    b["exp_r"] = round(sum(rs) / len(rs), 3) if rs else None
    b["exp_r_ci"] = boot_mean_ci(rs)
    b["total_usd"] = round(b["total_usd"], 2)
    b["open_risk_usd"] = round(b["open_risk_usd"], 2)
    b["open_risk_label"] = "risk at entry"
    b["last_trade"] = last
    b["small_n"] = b["n_closed"] < SMALL_N
    return b


def scoreboard(since_day: Optional[str] = None, *, ts: Optional[list] = None) -> dict:
    """{sid: board} over the normalised trades since `since_day` (default:
    the day the program was first switched ON; never switched on = all)."""
    if since_day is None:
        try:
            since_day = _EE().get_config().get("cm_program_started")
        except Exception:                          # noqa: BLE001
            since_day = None
    ts = trades(since_day) if ts is None else ts
    by: dict = {}
    for t in ts:
        by.setdefault(t["sid"], []).append(t)
    return {sid: _score(lst) for sid, lst in by.items()}


# ── loser lines + proposals ──────────────────────────────────────────────────
def _num(v, nd: int = 2) -> str:
    f = _f(v)
    if f is None:
        return "?"
    return ("%.*f" % (nd, f)).rstrip("0").rstrip(".") if nd else "%d" % round(f)


def _signed(v, nd: int = 2) -> str:
    f = _f(v)
    if f is None:
        return "?"
    s = _num(abs(f), nd)
    return ("−" if f < 0 else "+") + s


def loss_line(t: dict, autopsy_doc: Optional[dict], entry_snapshot: Optional[dict]) -> str:
    """A Rule #9 one-liner: what went in, what happened, how it came out."""
    sym = t.get("symbol") or "?"
    r = _f(t.get("r"))
    pnl = _f(t.get("pnl_usd"))
    head = "%s %sR %s$%s" % (sym, _signed(r) if r is not None else "?",
                             "−" if (pnl or 0) < 0 else "+", _num(abs(pnl or 0.0), 0))
    snap = entry_snapshot if isinstance(entry_snapshot, dict) else {}
    live = snap.get("live") if isinstance(snap.get("live"), dict) else {}
    er = t.get("entry_reason") if isinstance(t.get("entry_reason"), dict) else {}
    band = live.get("band") or er.get("band")
    room = live.get("room") or er.get("room")
    bits = []
    verdict = live.get("verdict")
    if verdict:
        bits.append("🎯 %s" % verdict)
    if isinstance(band, dict) and band.get("lo") is not None and band.get("hi") is not None:
        bits.append("band %s–%s" % (_num(band["lo"]), _num(band["hi"])))
    if isinstance(room, dict) and room.get("room_pct") is not None:
        seg = "room %s%%" % _signed(room.get("room_pct"), 1)
        if room.get("target") is not None:
            seg += " → %s" % _num(room.get("target"))
        bits.append(seg)
    version = snap.get("adapter_version") or er.get("adapter_version")
    where = label(t.get("sid"))
    if version:
        where += ", %s" % version
    inpart = "in: %s (%s)" % (", ".join(bits) or "no entry read recorded", where)
    ad = autopsy_doc if isinstance(autopsy_doc, dict) else {}
    cls = ad.get("classification")
    if cls:
        fb = str(ad.get("feedback") or "").split(";")[0].strip()
        what = "what happened: %s: %s" % (cls, fb) if fb else "what happened: %s" % cls
        if ad.get("status") == "preliminary":
            what += " (preliminary)"
    else:
        what = "what happened: autopsy pending"
    out_kind = {"take_profit": "take_profit", "premium_stop": "premium stop",
                "watchdog_exit": "watchdog stop", "distribution_exit": "SEPA sell",
                "hot_pullback_exit": "hot pullback exit"}.get(t.get("exit_kind"),
                                                               t.get("exit_kind") or "?")
    line = "%s · %s · %s · out: %s" % (head, inpart, what, out_kind)
    if t.get("approx"):
        line += " (≈ price)"
    return _no_bounce(line)


def _pid(sid: str, kind: str, key, value) -> str:
    raw = "%s|%s|%s|%s" % (sid, kind, key, json.dumps(value, sort_keys=True, default=str))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def propose(board: dict, class_counts: dict, cfg: Optional[dict]) -> list:
    """Deterministic proposals; every one is status 'proposed' until he
    decides. Nothing here applies anything."""
    cfg = cfg or {}
    rules = cfg.get("zone_edge_rules") if isinstance(cfg.get("zone_edge_rules"), dict) else {}
    try:
        from trading import zone_edge_entry as ZEE
        active = ZEE.active_rules(cfg)
    except Exception:                              # noqa: BLE001
        active = dict(rules)
    out = []
    for sid in sorted(set(board) | set(class_counts)):
        if not ST.is_roster(sid):
            continue
        b = board.get(sid) or empty_board()
        ci = b.get("exp_r_ci") or [None, None]
        if b.get("n_closed", 0) >= KILL_MIN_N and ci[1] is not None and ci[1] < 0:
            change = {"key": "cm_lanes", "value": {sid: False}}
            out.append({"id": _pid(sid, "pause", "cm_lanes", change["value"]), "sid": sid,
                        "kind": "pause", "level": "config", "change": change, "todo": None,
                        "title": "Pause %s: %d closed, expectancy %sR (95%% CI %s..%s) — "
                                 "the whole interval is below zero"
                                 % (label(sid), b["n_closed"], _num(b.get("exp_r"), 2),
                                    _num(ci[0], 2), _num(ci[1], 2)),
                        "evidence": {"count": b["n_closed"], "exp_r": b.get("exp_r"),
                                     "exp_r_ci": ci}, "status": "proposed"})
        for cls, n in sorted((class_counts.get(sid) or {}).items()):
            if n < CLASS_PROPOSE_MIN or cls == "unclassified":
                continue
            change, level, todo = None, "code", None
            if cls == "chased":
                if sid in ZONE_SIDS and active.get("demand_residents") is True:
                    change, level = {"key": "zone_edge_rules",
                                     "value": {"demand_residents": False}}, "config"
                elif sid in ZONE_SIDS:
                    continue                       # already strict: nothing to propose
                else:
                    todo = "entry-distance cap"
            elif cls == "band_failed":
                if sid in ZONE_SIDS + ("breaking",):
                    if int(active.get("min_touches") or 0) < 2:
                        change, level = {"key": "zone_edge_rules",
                                         "value": {"min_touches": 2}}, "config"
                    else:
                        todo = "band selection"
                else:
                    todo = "band selection"
            else:
                todo = _CODE_TODO.get(cls)
                if todo is None:
                    continue
            kind = "class:%s" % cls
            key = change["key"] if change else "todo"
            value = change["value"] if change else todo
            title = ("%s: %d %s losses — %s" % (label(sid), n, cls,
                     ("set %s %s" % (key, json.dumps(value))) if change
                     else "code change: %s (a TODO; nothing in the engine changes)" % todo))
            out.append({"id": _pid(sid, kind, key, value), "sid": sid, "kind": kind,
                        "level": level, "change": change, "todo": todo,
                        "title": _no_bounce(title), "evidence": {"count": n, "class": cls},
                        "status": "proposed"})
    return out


# ── the daily build ──────────────────────────────────────────────────────────
def _paged_closed_orders(brk, since_iso: str) -> list:
    """broker.closed_orders_since returns at most BROKER_PAGE orders, oldest
    first: page with `after` = the last row's submitted_at until a short
    page comes back."""
    out, after = [], since_iso
    for _ in range(BROKER_MAX_PAGES):
        rows = brk.closed_orders_since(after) or []
        out.extend(rows)
        if len(rows) < BROKER_PAGE:
            break
        nxt = rows[-1].get("submitted_at")
        if not nxt or nxt == after:
            break
        after = nxt
    seen, uniq = set(), []
    for o in out:
        oid = o.get("id")
        if oid and oid in seen:
            continue
        seen.add(oid)
        uniq.append(o)
    return uniq


def _autopsies(trade_ids: list) -> dict:
    coll = _coll("trade_autopsies")
    if coll is None or not trade_ids:
        return {}
    try:
        return {d.get("_id"): d for d in coll.find({"_id": {"$in": list(trade_ids)}})
                if isinstance(d, dict)}
    except Exception as exc:                       # noqa: BLE001
        log.warning("lane_review: autopsy read failed: %s", exc)
        return {}


def _entry_snapshots(refs: list) -> dict:
    from trading import chart_maps_lanes as CML
    coll = _coll(CML.ENTRY_SNAPSHOT_COLL)
    refs = [r for r in refs if r]
    if coll is None or not refs:
        return {}
    try:
        return {d.get("_id"): d for d in coll.find({"_id": {"$in": refs}})
                if isinstance(d, dict)}
    except Exception:                              # noqa: BLE001
        return {}


def _today_block(sid: str, day: str, ts: list, entries: dict, logs: dict) -> dict:
    lg = logs.get(sid) or {"skips": {}, "last": []}
    exits = [{"symbol": t.get("symbol"), "r": t.get("r"), "pnl_usd": t.get("pnl_usd"),
              "exit_kind": t.get("exit_kind"), "approx": t.get("approx")}
             for t in ts if t["status"] == "closed" and _day_of(t.get("exit_ts")) == day]
    return {"entries": entries.get(sid) or [], "skips": lg["skips"], "exits": exits}


def _stored_proposals() -> dict:
    coll = _coll(PROPOSALS_COLL)
    if coll is None:
        return {}
    try:
        return {d.get("_id"): d for d in coll.find({}) if isinstance(d, dict)}
    except Exception:                              # noqa: BLE001
        return {}


def build(day: Optional[str] = None, now: Optional[datetime] = None,
          record: bool = True, brk=None) -> dict:
    """The daily review. Closed day -> {"skipped": reason}, nothing written.
    record=False (--dry) writes NOTHING (no fills cache, no journal
    reconcile, no review, no proposals)."""
    from market_hours import gate
    from trading import chart_maps_lanes as CML
    from trading import journal
    n = _now_et(now)
    closed = gate.closed_reason(n if day is None else
                                datetime.combine(datetime.fromisoformat(day).date(),
                                                 datetime.min.time().replace(hour=12), tzinfo=ET))
    if closed:
        return {"skipped": closed}
    day = day or n.date().isoformat()
    EE = _EE()
    brk = brk if brk is not None else EE.broker
    cfg = EE.get_config()
    started = cfg.get("cm_program_started")
    lines = []
    # 1. broker fills for the market exits, then the journal
    since_day = started or (n - timedelta(days=FILLS_LOOKBACK_DAYS)).date().isoformat()
    fills_ok = True
    fills = []
    try:
        orders = _paged_closed_orders(brk, "%sT00:00:00Z" % since_day)
        fills = journal.resolve_exit_fills(orders, dry=not record)
    except Exception as exc:                       # noqa: BLE001
        fills_ok = False
        log.warning("lane_review: broker fills unavailable: %s", exc)
        lines.append("Market-exit prices are approximate today: the broker's fills "
                     "could not be read (%s)." % str(exc)[:80])
    docs = None
    if record:
        try:
            journal.reconcile()
        except Exception as exc:                   # noqa: BLE001
            log.warning("lane_review: journal reconcile failed: %s", exc)
    else:
        try:
            cached = journal._exit_fills()
            cached.update({d["_id"]: d for d in fills})
            docs = journal._build_docs(journal._ledger_rows(), journal._zone_lanes(), cached)
        except Exception as exc:                   # noqa: BLE001
            log.warning("lane_review: dry journal build failed: %s", exc)
            docs = []
    # 2. score
    ts = trades(started, docs=docs)
    board = {sid: _score([t for t in ts if t["sid"] == sid]) for sid in {t["sid"] for t in ts}}
    try:
        order = PC.priority_order(n)["order"]
    except Exception:                              # noqa: BLE001
        order = ST.usage_rank(*ST.frozen_counts())
    logs = CML._log_today(day)
    entries = CML._entries_today(day)
    losers = [t for t in ts if t["status"] == "closed" and not t.get("unpriced")
              and (_f(t.get("pnl_usd")) or 0) < 0]
    autos = _autopsies([t.get("trade_id") for t in losers])
    snaps = _entry_snapshots([t.get("snapshot_ref") for t in losers])
    class_counts: dict = {}
    for t in losers:
        cls = (autos.get(t.get("trade_id")) or {}).get("classification")
        if cls:
            cc = class_counts.setdefault(t["sid"], {})
            cc[cls] = cc.get(cls, 0) + 1
    strategies = []
    for rank, sid in enumerate(order, start=1):
        r = ST.roster_entry(sid) or {}
        lt = [t for t in losers if t["sid"] == sid and _day_of(t.get("exit_ts")) == day]
        cc = class_counts.get(sid) or {}
        strategies.append({
            "sid": sid, "label": label(sid), "rank": rank,
            "on": PC.strategy_on(sid, cfg, EE._broker_mode()),
            "today": _today_block(sid, day, [t for t in ts if t["sid"] == sid], entries, logs),
            "scoreboard": board.get(sid) or empty_board(),
            "losers_today": [loss_line(t, autos.get(t.get("trade_id")),
                                       snaps.get(t.get("snapshot_ref"))) for t in lt],
            "loss_classes": cc,
            "named_classes": sorted(c for c, k in cc.items() if k >= CLASS_PROPOSE_MIN),
            "prior": ST.PRIORS.get(sid),
            "note": r.get("note")})
    # 3. proposals (never applied here)
    fresh = propose(board, class_counts, cfg)
    stored = _stored_proposals()
    proposals = []
    for p in fresh:
        prev = stored.get(p["id"])
        if prev is not None:
            st = prev.get("status")
            if st in ("confirmed", "todo"):
                continue
            if st == "dismissed" and int((p.get("evidence") or {}).get("count") or 0) <= \
                    int((prev.get("evidence") or {}).get("count") or 0):
                continue
        p["created_day"] = (prev or {}).get("created_day") or day
        p["updated_day"] = day
        proposals.append(p)
    n_entries = sum(len(s["today"]["entries"]) for s in strategies)
    n_exits = sum(len(s["today"]["exits"]) for s in strategies)
    n_losers = sum(len(s["losers_today"]) for s in strategies)
    head = ("%s: %d entries, %d closes, %d losers across the Chart Maps lanes; %d open "
            "proposals." % (day, n_entries, n_exits, n_losers, len(proposals)))
    lines.insert(0, head)
    lines.append("UNMEASURED forward paper measurement — judge in R, not dollars; a pause "
                 "is proposed only after %d closed trades with the whole expectancy "
                 "interval below zero." % KILL_MIN_N)
    doc = {"_id": day, "day": day, "built_at": n.isoformat(timespec="seconds"),
           "version": REVIEW_VERSION,
           "program": {"enabled": PC.enabled(cfg, EE._broker_mode()), "started": started,
                       "order": order},
           "strategies": strategies, "proposals": proposals, "summary_lines": lines,
           "fills": {"ok": fills_ok, "resolved": len(fills)}, "headline": head}
    if record:
        coll = _coll(REVIEW_COLL)
        if coll is not None:
            try:
                coll.replace_one({"_id": day}, doc, upsert=True)
            except Exception as exc:               # noqa: BLE001
                log.warning("lane_review: review write failed: %s", exc)
        pcoll = _coll(PROPOSALS_COLL)
        if pcoll is not None:
            for p in proposals:
                try:
                    pcoll.update_one({"_id": p["id"]}, {"$set": dict(p, status="proposed")},
                                     upsert=True)
                except Exception as exc:           # noqa: BLE001
                    log.warning("lane_review: proposal write failed: %s", exc)
    return doc


# ── reads ────────────────────────────────────────────────────────────────────
def get(day: str) -> Optional[dict]:
    coll = _coll(REVIEW_COLL)
    if coll is None or not day:
        return None
    try:
        return coll.find_one({"_id": day})
    except Exception:                              # noqa: BLE001
        return None


def _open_proposals() -> list:
    return [p for p in _stored_proposals().values() if p.get("status") == "proposed"]


def latest(fmt: str = "full") -> dict:
    """The newest review. "summary" is the Claude routine's read."""
    coll = _coll(REVIEW_COLL)
    doc = None
    if coll is not None:
        try:
            rows = list(coll.find({}).sort("day", -1).limit(1))
            doc = rows[0] if rows else None
        except Exception as exc:                   # noqa: BLE001
            log.warning("lane_review: latest read failed: %s", exc)
    if doc is None:
        return {"day": None, "reason": "no review written yet", "link": LINK}
    props = _open_proposals()
    if fmt != "summary":
        out = dict(doc)
        out["proposals_open"] = props
        out["link"] = LINK
        return out
    strategies = []
    losers = []
    for s in doc.get("strategies") or []:
        b = s.get("scoreboard") or {}
        strategies.append({"sid": s.get("sid"), "label": s.get("label"),
                           "n_closed": b.get("n_closed"), "win_pct": b.get("win_pct"),
                           "win_ci": b.get("win_ci"), "exp_r": b.get("exp_r"),
                           "exp_r_ci": b.get("exp_r_ci"), "total_usd": b.get("total_usd"),
                           "today": {"entries": len((s.get("today") or {}).get("entries") or []),
                                     "losers": len(s.get("losers_today") or [])}})
        losers.extend(s.get("losers_today") or [])
    return {"day": doc.get("day"), "built_at": doc.get("built_at"),
            "headline": doc.get("headline"), "strategies": strategies, "losers": losers,
            "proposals_open": [{"id": p.get("_id") or p.get("id"), "sid": p.get("sid"),
                                "title": p.get("title"), "level": p.get("level")}
                               for p in props],
            "summary_lines": doc.get("summary_lines") or [], "link": LINK}


# ── decisions (his Confirm / Dismiss) ────────────────────────────────────────
def _proposal(pid: str) -> dict:
    coll = _coll(PROPOSALS_COLL)
    if coll is None:
        raise ValueError("proposals unavailable")
    doc = coll.find_one({"_id": pid})
    if not isinstance(doc, dict):
        raise KeyError(pid)
    return doc


def _set_status(pid: str, status: str, **fields) -> None:
    coll = _coll(PROPOSALS_COLL)
    coll.update_one({"_id": pid}, {"$set": dict(fields, status=status)})


def confirm(pid: str, by: str) -> dict:
    """Apply one proposal. Config level: exactly the change, validated like
    POST /trading/config (APPLYABLE_KEYS only). Code level: status 'todo' and
    NOTHING in the engine changes. Already decided -> ValueError('already
    <status>'). Ledgered either way."""
    doc = _proposal(pid)
    st = doc.get("status")
    if st != "proposed":
        raise ValueError("already %s" % st)
    EE = _EE()
    now = _now_et().isoformat(timespec="seconds")
    level = doc.get("level")
    change = doc.get("change") if isinstance(doc.get("change"), dict) else None
    if level != "config" or change is None:
        _set_status(pid, "todo", decided_by=by, decided_at=now)
        EE.ledger("lane_proposal_confirmed",
                  detail={"pid": pid, "level": "code", "change": None, "todo": doc.get("todo"),
                          "before": None, "after": None, "by": by})
        return {"id": pid, "status": "todo", "applied": None,
                "note": "Added to Claude's TODO. Nothing in the engine changed."}
    key = change.get("key")
    if key not in APPLYABLE_KEYS:
        raise ValueError("proposal key %r is not applyable" % key)
    cfg = EE.get_config()
    before = cfg.get(key)
    if key == "zone_edge_rules":
        from trading import zone_edge_entry as ZEE
        merged = dict(before or {})
        value = dict(change.get("value") or {})
        # Tighten-only: a stale card can never loosen a zone rule. min_touches
        # keeps the stricter of now / proposed (a card made when it was 1
        # must not drop a later 3 back to 2).
        if "min_touches" in value:
            try:
                value["min_touches"] = max(int(merged.get("min_touches") or 0),
                                           value["min_touches"])
            except (TypeError, ValueError):
                pass
        merged.update(value)
        updates = {"zone_edge_rules": ZEE.validate_rules(merged)}
    else:
        updates = PC.validate_updates({key: change.get("value")}, cfg)
    EE.update_config(**updates)
    _set_status(pid, "confirmed", decided_by=by, decided_at=now)
    EE.ledger("lane_proposal_confirmed",
              detail={"pid": pid, "level": "config", "change": change, "before": before,
                      "after": updates.get(key), "by": by})
    return {"id": pid, "status": "confirmed", "applied": updates}


def dismiss(pid: str, by: str) -> dict:
    doc = _proposal(pid)
    st = doc.get("status")
    if st != "proposed":
        raise ValueError("already %s" % st)
    _set_status(pid, "dismissed", decided_by=by,
                decided_at=_now_et().isoformat(timespec="seconds"))
    _EE().ledger("lane_proposal_dismissed",
                 detail={"pid": pid, "level": doc.get("level"), "change": doc.get("change"),
                         "evidence": doc.get("evidence"), "by": by})
    return {"id": pid, "status": "dismissed"}


# ── CLI ──────────────────────────────────────────────────────────────────────
def _arg(argv: list, flag: str) -> Optional[str]:
    if flag in argv:
        i = argv.index(flag)
        return argv[i + 1] if i + 1 < len(argv) else None
    return None


def _main(argv: list) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    dry = "--dry" in argv
    if "--backfill-fills" in argv:
        since = _arg(argv, "--since")
        if not since:
            print("usage: python -m trading.lane_review --backfill-fills --since YYYY-MM-DD [--dry]")
            return 2
        from trading import journal
        orders = _paged_closed_orders(_EE().broker, "%sT00:00:00Z" % since)
        docs = journal.resolve_exit_fills(orders, dry=dry)
        print(json.dumps(docs, indent=1, default=str))
        return 0
    doc = build(day=_arg(argv, "--day"), record=not dry)
    print(json.dumps(doc if dry else {k: doc.get(k) for k in ("day", "headline", "summary_lines",
                                                                "skipped")},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
